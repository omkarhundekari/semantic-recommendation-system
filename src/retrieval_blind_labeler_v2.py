import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from evaluation_blind_labeling import (
    build_blind_candidates,
    build_label_record,
)


def load_json(path: str) -> Dict[str, Any]:
    file_path = Path(path)

    if not file_path.exists():
        return {}

    return json.loads(file_path.read_text())


def save_json(path: str, data: Dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, indent=2))


def get_existing_labels(
    labels: Dict[str, Any],
    query_id: str,
) -> Dict[str, int]:
    query_labels = labels.setdefault(query_id, {})

    return {
        str(document_id): int(relevance)
        for document_id, relevance in query_labels.items()
    }


def label_query(
    query_entry: Dict[str, Any],
    labels: Dict[str, Any],
) -> bool:
    query_id = str(query_entry["id"])
    existing_labels = get_existing_labels(labels, query_id)

    print("\n" + "=" * 88)
    print(f"Query ID: {query_id}")
    print(f"Domain:   {query_entry.get('domain', 'Unknown')}")
    print(f"Query:    {query_entry['query']}")
    print("=" * 88)
    print("Label each candidate: 2 = highly relevant, 1 = partially relevant, 0 = irrelevant")
    print("Type s to skip one candidate, or q to save and stop.\n")

    for position, candidate in enumerate(
        build_blind_candidates(query_entry),
        start=1,
    ):
        document_id = candidate["document_id"]

        if document_id in existing_labels:
            continue

        print(f"[{position}] {candidate['title']}")
        print(f"Category: {candidate['category']}")
        print(f"Published: {candidate['published'] or 'Unknown'}")
        print(f"Source: {candidate['source'] or 'Unknown'}")
        print(f"Preview: {candidate['abstract'][:500] or 'No preview available'}\n")

        while True:
            answer = input("Label [2/1/0/s/q]: ").strip().lower()

            if answer == "q":
                return False

            if answer == "s":
                print("Skipped.\n")
                break

            if answer in {"0", "1", "2"}:
                record = build_label_record(
                    document_id=document_id,
                    relevance=int(answer),
                )
                labels.setdefault(query_id, {})[
                    record["document_id"]
                ] = record["relevance"]
                print("Saved.\n")
                break

            print("Please enter 2, 1, 0, s, or q.\n")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Blind relevance labeling for pooled retrieval candidates."
    )
    parser.add_argument(
        "--candidates",
        default="outputs/retrieval_eval_candidates_v2.json",
    )
    parser.add_argument(
        "--labels",
        default="data/retrieval_eval_labels_v2.json",
    )
    parser.add_argument(
        "--query-id",
        default=None,
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=1,
    )

    args = parser.parse_args()

    candidate_data = load_json(args.candidates)
    label_data = load_json(args.labels) or {
        "schema_version": 2,
        "labels": {},
    }
    labels = label_data.setdefault("labels", {})

    queries: List[Dict[str, Any]] = candidate_data.get("queries", [])

    if args.query_id:
        queries = [
            query
            for query in queries
            if query["id"] == args.query_id
        ]

    processed = 0

    for query_entry in queries:
        if processed >= args.max_queries:
            break

        complete = label_query(query_entry, labels)
        save_json(args.labels, label_data)

        if not complete:
            print(f"\nSaved progress to {args.labels}")
            return

        processed += 1

    print(f"\nSaved progress to {args.labels}")


if __name__ == "__main__":
    main()
