"""Read-only runtime checks in the ML venv; no embedding or KB writes."""
import json
import os
from pathlib import Path
import importlib.metadata

from qdrant_client import QdrantClient
from source.knowledge_base.index_qdrant_delta import check_collection
from source.knowledge_base.incremental_io import read_csv, validate_labels
from source.knowledge_base.build_delta_documents import validate_documents
from source.knowledge_base.incremental_io import read_jsonl


def main():
    root = Path(os.getenv("TIKI_PROJECT_ROOT", "/opt/tiki"))
    required = ["data/raw/products_detail.csv", "data/processed/labeled_processed_products_reviews.csv",
                "data/processed/product_aspect_scores.parquet", "data/processed/documents.jsonl"]
    for name in required:
        if not (root / name).is_file():
            raise FileNotFoundError(root / name)
    validate_labels(read_csv(root / required[1]))
    docs = read_jsonl(root / required[3])
    validate_documents(docs)
    collection = os.environ["QDRANT_COLLECTION"]
    client = QdrantClient(url=os.environ["QDRANT_URL"], timeout=15)
    try:
        check_collection(client, collection)
        points = client.count(collection, exact=True).count
    finally:
        client.close()
    from source.absa.inference import get_logreg
    prediction = get_logreg().predict(["sản phẩm tốt"])
    print(json.dumps({"collection": collection, "points": points, "documents": len(docs),
                      "logreg_smoke": prediction,
                      "versions": {name: importlib.metadata.version(name) for name in
                                   ["scikit-learn", "FlagEmbedding", "torch", "transformers"]}},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
