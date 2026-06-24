import json
from pathlib import Path
from typing import Any, Dict, List, Mapping

from evaluation_scoring import score_ranking_if_covered


def load_json(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text())


def evaluate_candidate_export(
    candidate_export: Mapping[str, Any],
    labels_by_query: Mapping[str, Mapping[str, int]],
    top_k: int,
) -> Dict[str, Any]:
    """
    Evaluate each retrieval method only for queries whose top-K results
    are completely covered by document-ID-based relevance labels.
    """
    method_reports: Dict[str, Dict[str, Any]] = {}

    for query_entry in candidate_export.get("queries", []):
        query_id = str(query_entry["id"])
        query_labels = labels_by_query.get(query_id, {})

        for method_name, ranking in query_entry.get(
            "method_rankings",
            {},
        ).items():
            result = score_ranking_if_covered(
                ranking=ranking,
                labels=query_labels,
                top_k=top_k,
            )

            report = method_reports.setdefault(
                method_name,
                {
                    "evaluated_queries": 0,
                    "excluded_queries": 0,
                    "coverage_values": [],
                    "precision_values": [],
                    "mrr_values": [],
                    "ndcg_values": [],
                    "query_details": {},
                },
            )

            report["coverage_values"].append(result["coverage"])
            report["query_details"][query_id] = result

            if result["eligible"]:
                report["evaluated_queries"] += 1
                report["precision_values"].append(
                    result["precision_at_k"]
                )
                report["mrr_values"].append(
                    result["reciprocal_rank"]
                )
                report["ndcg_values"].append(
                    result["ndcg_at_k"]
                )
            else:
                report["excluded_queries"] += 1

    summary = {"methods": {}}

    for method_name, report in method_reports.items():
        evaluated = report["evaluated_queries"]
        total = evaluated + report["excluded_queries"]

        summary["methods"][method_name] = {
            "evaluated_queries": evaluated,
            "excluded_queries": report["excluded_queries"],
            "method_query_coverage": round(
                evaluated / total,
                4,
            ) if total else 0.0,
            "average_label_coverage": round(
                sum(report["coverage_values"])
                / len(report["coverage_values"]),
                4,
            ) if report["coverage_values"] else 0.0,
            "precision_at_k": round(
                sum(report["precision_values"])
                / len(report["precision_values"]),
                4,
            ) if report["precision_values"] else None,
            "mrr": round(
                sum(report["mrr_values"])
                / len(report["mrr_values"]),
                4,
            ) if report["mrr_values"] else None,
            "ndcg_at_k": round(
                sum(report["ndcg_values"])
                / len(report["ndcg_values"]),
                4,
            ) if report["ndcg_values"] else None,
            "query_details": report["query_details"],
        }

    return summary


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Evaluate retrieval methods with strict label coverage."
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
        "--top-k",
        type=int,
        default=5,
    )

    args = parser.parse_args()

    candidate_export = load_json(args.candidates)
    label_data = load_json(args.labels)

    report = evaluate_candidate_export(
        candidate_export=candidate_export,
        labels_by_query=label_data.get("labels", {}),
        top_k=args.top_k,
    )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
