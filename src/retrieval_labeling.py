import argparse
import json
from pathlib import Path
from typing import Dict, List


def load_json(path: str) -> Dict:
    file_path = Path(path)

    if not file_path.exists():
        return {}

    return json.loads(file_path.read_text())


def save_json(path: str, data: Dict) -> None:
    Path(path).write_text(json.dumps(data, indent=2))


def build_pooled_candidates(
    query_entry: Dict,
    max_candidates: int = 10,
) -> List[Dict]:
    pooled = {}

    for mode_name, results in query_entry["results"].items():
        for result in results:
            title = result["title"]

            if title not in pooled:
                pooled[title] = {
                    **result,
                    "seen_in": [],
                }

            pooled[title]["seen_in"].append(
                f"{mode_name} #{result['rank']}"
            )

    ranked_candidates = sorted(
        pooled.values(),
        key=lambda item: min(
            int(reference.split("#")[-1])
            for reference in item["seen_in"]
        ),
    )

    return ranked_candidates[:max_candidates]


def label_query(
    query_entry: Dict,
    labels: Dict[str, Dict[str, int]],
) -> bool:
    query_id = query_entry["id"]
    query_labels = labels.setdefault(query_id, {})

    print("\n" + "=" * 88)
    print(f"Query ID: {query_id}")
    print(f"Domain:   {query_entry['domain']}")
    print(f"Query:    {query_entry['query']}")
    print("=" * 88)
    print("Label each candidate: 2 = highly relevant, 1 = partially relevant, 0 = irrelevant")
    print("Type s to skip one candidate, or q to save and stop.\n")

    for position, candidate in enumerate(
        build_pooled_candidates(query_entry),
        start=1,
    ):
        title = candidate["title"]

        if title in query_labels:
            continue

        print(f"[{position}] {title}")
        print(f"Category: {candidate.get('category', 'Unknown')}")
        print(f"Published: {candidate.get('published', 'Unknown')}")
        print(f"Retrieved by: {', '.join(candidate['seen_in'])}")
        print(f"Preview: {candidate.get('preview', 'No preview available')}\n")

        while True:
            answer = input("Label [2/1/0/s/q]: ").strip().lower()

            if answer == "q":
                return False

            if answer == "s":
                print("Skipped.\n")
                break

            if answer in {"0", "1", "2"}:
                query_labels[title] = int(answer)
                print("Saved.\n")
                break

            print("Please enter 2, 1, 0, s, or q.\n")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactively label pooled retrieval candidates."
    )
    parser.add_argument(
        "--candidates",
        default="outputs/retrieval_eval_candidates.json",
    )
    parser.add_argument(
        "--labels",
        default="data/retrieval_eval_labels.json",
    )
    parser.add_argument(
        "--query-id",
        default=None,
        help="Label one specific query ID, for example cyber_01.",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=1,
        help="Maximum unlabeled queries to label in this session.",
    )

    args = parser.parse_args()

    candidate_data = load_json(args.candidates)
    label_data = load_json(args.labels) or {"labels": {}}
    labels = label_data.setdefault("labels", {})

    queries: List[Dict] = candidate_data.get("queries", [])

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
