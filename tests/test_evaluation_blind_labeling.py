import pytest

from evaluation_blind_labeling import (
    build_blind_candidates,
    build_label_record,
)


def test_blind_candidates_hide_retrieval_metadata():
    query_entry = {
        "candidate_pool": [
            {
                "document_id": "arxiv:2009.08553",
                "title": "Generation-Augmented Retrieval",
                "abstract": "A retrieval-augmented QA paper.",
                "category": "cs.CL",
                "published": "2020-09-17",
                "source": "arXiv",
                "provenance": [
                    {"method": "semantic", "rank": 1},
                    {"method": "bm25", "rank": 3},
                ],
                "rerank_score": 8.2,
            }
        ]
    }

    candidates = build_blind_candidates(query_entry)

    assert candidates == [
        {
            "document_id": "arxiv:2009.08553",
            "title": "Generation-Augmented Retrieval",
            "abstract": "A retrieval-augmented QA paper.",
            "category": "cs.CL",
            "published": "2020-09-17",
            "source": "arXiv",
        }
    ]


def test_builds_valid_label_record():
    assert build_label_record(
        "arxiv:2009.08553",
        2,
    ) == {
        "document_id": "arxiv:2009.08553",
        "relevance": 2,
    }


def test_rejects_invalid_relevance_value():
    with pytest.raises(ValueError, match="Relevance"):
        build_label_record("arxiv:2009.08553", 3)


def test_rejects_blank_document_id():
    with pytest.raises(ValueError, match="document_id"):
        build_label_record("   ", 1)
