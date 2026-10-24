"""ML subprocess entry point. Airflow itself never imports pandas/torch."""
import argparse
from scripts.update_kb import run
from source.knowledge_base.incremental_io import write_json


def main():
    parser = argparse.ArgumentParser()
    for name in ("input", "collection", "url", "result"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--model", default="logreg")
    parser.add_argument("--revision", default="1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run(args.input, model=args.model, collection=args.collection, url=args.url,
                 revision=args.revision, dry_run=args.dry_run)
    write_json(result, args.result)
    print(f"KB worker completed: {result.get('batch_id')}", flush=True)


if __name__ == "__main__":
    main()
