"""Publish a complete CSV to the Airflow inbox; does not run inference or update KB."""
import argparse
from pathlib import Path
from source.orchestration.airflow_batches import submit_batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    print(submit_batch(args.input, Path(__file__).resolve().parents[1]))


if __name__ == "__main__":
    main()
