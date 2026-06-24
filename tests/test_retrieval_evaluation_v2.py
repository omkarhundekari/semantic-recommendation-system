from retrieval_evaluation_v2 import evaluate_candidate_export


def make_export():
    return {
        "schema_version": 2,
        "queries": [
            {
                "id": "query_01",
                "method_rankings": {
                    "semantic": [
                        {"document_id": "arxiv:1", "rank": 1},
                        {"document_id": "arxiv:2", "rank": 2},
                    ],
                    "bm25": [
                        {"document_id": "arxiv:1", "rank": 1},
                        {"document_id": "arxiv:3", "rank": 2},
                    ],
                },
            }
        ],
    }


def test_scores_only_fully_covered_method_query_pairs():
    report = evaluate_candidate_export(
        candidate_export=make_export(),
        labels_by_query={
            "query_01": {
                "arxiv:1": 2,
                "arxiv:2": 1,
            }
        },
        top_k=2,
    )

    semantic = report["methods"]["semantic"]
    bm25 = report["methods"]["bm25"]

    assert semantic["evaluated_queries"] == 1
    assert semantic["excluded_queries"] == 0
    assert semantic["precision_at_k"] == 1.0

    assert bm25["evaluated_queries"] == 0
    assert bm25["excluded_queries"] == 1
    assert bm25["precision_at_k"] is None
    assert bm25["query_details"]["query_01"]["missing_document_ids"] == [
        "arxiv:3"
    ]


def test_reports_method_query_coverage():
    report = evaluate_candidate_export(
        candidate_export=make_export(),
        labels_by_query={
            "query_01": {
                "arxiv:1": 2,
                "arxiv:2": 1,
                "arxiv:3": 0,
            }
        },
        top_k=2,
    )

    assert report["methods"]["semantic"]["method_query_coverage"] == 1.0
    assert report["methods"]["bm25"]["method_query_coverage"] == 1.0
