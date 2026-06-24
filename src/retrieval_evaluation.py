import argparse
import json
from pathlib import Path
from typing import Dict, List

from research_retrieval_service import retrieve_ranked_evidence


MODES = (
    "semantic",
    "bm25",
    "hybrid_rrf",
    "hybrid_reranked",
)


def precision_at_k(relevances: List[int], k: int) -> float:
    values = relevances[:k]

    if not values:
        return 0.0

    return sum(1 for value in values if value > 0) / len(values)


def reciprocal_rank(relevances: List[int]) -> float:
    for rank, value in enumerate(relevances, start=1):
        if value > 0:
            return 1.0 / rank

    return 0.0


def dcg_at_k(relevances: List[int], k: int) -> float:
    total = 0.0

    for rank, relevance in enumerate(relevances[:k], start=1):
        total += relevance / __import__("math").log2(rank + 1)

    return total


def ndcg_at_k(relevances: List[int], k: int) -> float:
    actual = dcg_at_k(relevances, k)
    ideal = dcg_at_k(sorted(relevances, reverse=True), k)

    if ideal == 0:
        return 0.0

    return actual / ideal


def load_json(path: str) -> Dict:
    return json.loads(Path(path).read_text())


def retrieve_for_mode(
    mode_name: str,
    query: str,
    top_k: int,
) -> List[Dict]:
    if mode_name not in MODES:
        raise ValueError(f"Unsupported retrieval mode: {mode_name}")

    return retrieve_ranked_evidence(
        query=query,
        top_k=top_k,
        strategy=mode_name,
        candidate_k=50,
    )


def export_candidates(
    queries: List[Dict],
    top_k: int,
    output_path: str,
) -> None:
    exported = {"queries": []}

    for query_spec in queries:
        query_entry = {
            "id": query_spec["id"],
            "domain": query_spec["domain"],
            "query": query_spec["query"],
            "results": {},
        }

        for mode_name in MODES:
            results = retrieve_for_mode(
                mode_name,
                query_spec["query"],
                top_k,
            )

            query_entry["results"][mode_name] = [
                {
                    "rank": rank,
                    "title": result["title"],
                    "category": result.get("category"),
                    "published": result.get("published"),
                    "url": result.get("url"),
                    "score": (
                        result.get("rerank_score")
                        or result.get("rrf_score")
                        or result.get("semantic_score")
                        or result.get("bm25_score")
                    ),
                    "preview": " ".join(
                        result.get("content", "").split()
                    )[:500],
                }
                for rank, result in enumerate(results, start=1)
            ]

        exported["queries"].append(query_entry)

    Path(output_path).parent.mkdir(exist_ok=True)
    Path(output_path).write_text(json.dumps(exported, indent=2))

    print(f"Exported candidate rankings to {output_path}")


def score_modes(
    queries: List[Dict],
    labels: Dict,
    top_k: int,
) -> Dict:
    report = {"modes": {}}

    for mode_name in MODES:
        p5_scores = []
        p10_scores = []
        mrr_scores = []
        ndcg_scores = []
        labeled_queries = 0

        for query_spec in queries:
            query_labels = labels.get(query_spec["id"], {})

            if not query_labels:
                continue

            results = retrieve_for_mode(
                mode_name,
                query_spec["query"],
                top_k,
            )

            relevances = [
                int(query_labels.get(result["title"], 0))
                for result in results
            ]

            p5_scores.append(precision_at_k(relevances, 5))
            p10_scores.append(precision_at_k(relevances, 10))
            mrr_scores.append(reciprocal_rank(relevances))
            ndcg_scores.append(ndcg_at_k(relevances, 10))
            labeled_queries += 1

        report["modes"][mode_name] = {
            "labeled_queries": labeled_queries,
            "precision_at_5": round(
                sum(p5_scores) / len(p5_scores), 4
            ) if p5_scores else None,
            "precision_at_10": round(
                sum(p10_scores) / len(p10_scores), 4
            ) if p10_scores else None,
            "mrr": round(
                sum(mrr_scores) / len(mrr_scores), 4
            ) if mrr_scores else None,
            "ndcg_at_10": round(
                sum(ndcg_scores) / len(ndcg_scores), 4
            ) if ndcg_scores else None,
        }

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate semantic, BM25, hybrid RRF, and reranked retrieval."
    )
    parser.add_argument(
        "--queries",
        default="data/retrieval_eval_queries.json",
    )
    parser.add_argument(
        "--labels",
        default="data/retrieval_eval_labels.json",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--export-candidates",
        action="store_true",
    )
    parser.add_argument(
        "--output",
        default="outputs/retrieval_eval_candidates.json",
    )

    args = parser.parse_args()

    query_data = load_json(args.queries)
    queries = query_data["queries"]

    if args.export_candidates:
        export_candidates(
            queries=queries,
            top_k=args.top_k,
            output_path=args.output,
        )
        return

    label_data = load_json(args.labels)
    report = score_modes(
        queries=queries,
        labels=label_data.get("labels", {}),
        top_k=args.top_k,
    )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
