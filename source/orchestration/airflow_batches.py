"""Durable CSV inbox for one sequential Airflow task. Standard library only."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_json(path, value):
    atomic_bytes(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))


def atomic_bytes(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".writing-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        Path(name).replace(path)
    finally:
        Path(name).unlink(missing_ok=True)


@dataclass(frozen=True)
class QueueConfig:
    root: Path
    python: str
    collection: str
    url: str
    model: str = "logreg"
    revision: str = "1"
    max_batches: int = 4

    @classmethod
    def from_env(cls):
        config = cls(
            root=Path(os.getenv("TIKI_PROJECT_ROOT", "/opt/tiki")).resolve(),
            python=os.getenv("TIKI_ML_PYTHON", "/opt/tiki-venv/bin/python"),
            collection=os.environ["QDRANT_COLLECTION"], url=os.environ["QDRANT_URL"],
            model=os.getenv("KB_ABSA_MODEL", "logreg"),
            revision=os.getenv("KB_PIPELINE_REVISION", "1"),
            max_batches=int(os.getenv("KB_MAX_BATCHES", "4")),
        )
        if config.max_batches < 1 or config.model not in {"logreg", "phobert", "phobert_onnx"}:
            raise ValueError("Invalid KB_MAX_BATCHES or KB_ABSA_MODEL")
        return config

    @property
    def queue(self):
        return self.root / "data" / "airflow_queue"


def submit_batch(input_path, root):
    """Atomically publish only a complete CSV; immutable processing copies follow."""
    source = Path(input_path).resolve()
    if not source.is_file() or source.suffix.lower() != ".csv":
        raise ValueError("Batch must be an existing .csv file")
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"product_id", "content", "rating"} <= set(reader.fieldnames or []):
            raise ValueError("CSV requires product_id, content, rating")
        if next(reader, None) is None:
            raise ValueError("CSV contains no rows")
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    target = Path(root) / "data" / "airflow_queue" / "inbox" / f"{digest}.csv"
    if target.exists() and target.read_bytes() != content:
        raise RuntimeError("Inbox hash collision or modified file")
    atomic_bytes(target, content)
    return target


def execute_batch(config, input_path, *, dry_run=False):
    result_path = config.queue / "results" / (digest_file(input_path) + ".json")
    result_path.unlink(missing_ok=True)
    command = [config.python, "-u", "-m", "scripts.airflow_worker", "--input", str(input_path),
               "--model", config.model, "--collection", config.collection, "--url", config.url,
               "--revision", config.revision, "--result", str(result_path)]
    if dry_run:
        command.append("--dry-run")
    # No shell, no keys in command arguments. ML logs stream into Airflow task logs.
    subprocess.run(command, cwd=config.root, check=True)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not dry_run and not result.get("completed_at"):
        raise RuntimeError("Worker did not report a completed batch")
    return result


def queue_summary(config):
    pending = config.root / "data" / "processed" / "kb_batches" / "pending.json"
    return {"inbox_files": len(list((config.queue / "inbox").glob("*.csv"))),
            "processing_files": len(list((config.queue / "processing").glob("*.csv"))),
            "pipeline_pending": pending.exists(), "collection": config.collection}


def process_queue(config, executor=execute_batch):
    """Retry unfinished processing files before claiming new inbox files."""
    if config.max_batches < 1:
        raise ValueError("max_batches must be positive")
    queue = config.queue
    for name in ("inbox", "processing", "archive", "receipts", "results"):
        (queue / name).mkdir(parents=True, exist_ok=True)
    # OS lock prevents manual helper invocations from competing with the DAG.
    lock = (queue / ".queue.lock").open("a+b")
    try:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _process_locked(config, executor)
    finally:
        lock.close()


def _process_locked(config, executor):
    queue = config.queue
    pending_path = config.root / "data" / "processed" / "kb_batches" / "pending.json"
    candidates = []
    if pending_path.exists():
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
        original = Path(pending["input"])
        # Windows and Linux use different paths and Qdrant URLs. Never silently
        # re-identify a pending Windows batch as a new container batch.
        if not original.is_file() or not original.resolve().is_relative_to(config.root):
            raise RuntimeError("Finish the pending batch in its original environment before using Airflow")
        identity = pending["identity"]
        if (identity["url"].rstrip("/") != config.url.rstrip("/")
                or identity["collection"] != config.collection
                or identity["model"] != config.model
                or str(identity["revision"]) != config.revision):
            raise RuntimeError("Pending batch configuration differs from Airflow; finish it in its original environment")
        candidates.append(original.resolve())
    candidates.extend(sorted((queue / "processing").glob("*.csv")))
    candidates.extend(sorted((queue / "inbox").glob("*.csv")))
    results, seen = [], set()
    for source in candidates:
        if len(results) >= config.max_batches:
            break
        # Processing a durable copy may already have archived/removed its inbox
        # twin, which was included in this same discovery snapshot.
        if not source.exists() and source.parent == queue / "inbox":
            continue
        digest = digest_file(source)
        if digest in seen:
            continue
        seen.add(digest)
        working = queue / "processing" / f"{digest}.csv"
        receipt_path = queue / "receipts" / f"{digest}.json"
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            target = receipt["target"]
            if target != {"collection": config.collection, "url": config.url}:
                raise RuntimeError("Queue receipt target differs; use a separate project data directory for another KB")
            # Successful receipts are archival records, not instructions to
            # reprocess all history when a model or configuration changes.
            if source.parent == queue / "inbox":
                source.unlink()
            continue
        # Preserve pending input path exactly: it participates in recovery.
        is_pending = candidates and source.resolve() == candidates[0] and pending_path.exists()
        if not is_pending:
            if working.exists() and digest_file(working) != digest:
                raise RuntimeError("Processing copy was modified")
            if not working.exists():
                atomic_bytes(working, source.read_bytes())
            source_for_worker = working
        else:
            source_for_worker = source
        result = executor(config, source_for_worker)
        save_json(receipt_path, {"input_sha256": digest, "result": result,
                                "target": {"collection": config.collection, "url": config.url}})
        atomic_bytes(queue / "archive" / f"{digest}.csv", source_for_worker.read_bytes())
        inbox = queue / "inbox" / f"{digest}.csv"
        if inbox.exists():
            if digest_file(inbox) != digest:
                raise RuntimeError("Inbox changed during processing")
            inbox.unlink()
        results.append({"input_sha256": digest, "new_reviews": result.get("new_reviews", 0),
                        "batch_id": result.get("batch_id"), "metrics": result.get("metrics", {})})
    return {"completed_batches": len(results), "results": results,
            "remaining_inbox": len(list((queue / "inbox").glob("*.csv")))}
