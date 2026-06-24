import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from evaluation_candidate_export import build_candidate_export


def load_json(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export document-ID-based pooled retrieval candidates."
    )
    parser.add_argument(
        "--queries",
        default="data/retrieval_eval_queries.json",
    )
    parser.add_argument(
        "--query-id",
        default=None,
        help="Export one specific query ID, for example ml_01.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--candidate-k",
        type=int,
        default=50,
    )
    parser.add_argument(
        "--output",
        default="outputs/retrieval_eval_candidates_v2.json",
    )

    args = parser.parse_args()

    if args.top_k < 1:
        raise ValueError("--top-k must be at least 1.")

    query_data = load_json(args.queries)
    queries: List[Dict[str, Any]] = query_data["queries"]

    if args.query_id:
        queries = [
            query
            for query in queries
            if query["id"] == args.query_id
        ]

        if not queries:
            raise ValueError(
                f"No evaluation query found with ID: {args.query_id}"
            )

    export = build_candidate_export(
        queries=queries,
        top_k=args.top_k,
        candidate_k=args.candidate_k,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(export, indent=2))

    print(
        f"Exported {len(export['queries'])} query pools "
        f"to {output_path}"
    )


if __name__ == "__main__":
    main()
