import pytest

from evaluation_pooling import build_union_pool


def make_result(document_id, title, content="Abstract"):
    return {
        "document_id": document_id,
        "title": title,
        "content": content,
        "category": "cs.IR",
        "published": "2024-01-01T00:00:00Z",
        "url": f"https://arxiv.org/abs/{document_id.split(':', 1)[1]}v1",
        "source": "arXiv",
    }


def test_builds_union_and_deduplicates_by_document_id():
    results_by_method = {
        "semantic": [
            make_result("arxiv:1111.11111", "Paper A"),
            make_result("arxiv:2222.22222", "Paper B"),
        ],
        "bm25": [
            make_result("arxiv:2222.22222", "Paper B"),
            make_result("arxiv:3333.33333", "Paper C"),
        ],
    }

    pool = build_union_pool(results_by_method, top_k=2)

    assert [item["document_id"] for item in pool] == [
        "arxiv:1111.11111",
        "arxiv:2222.22222",
        "arxiv:3333.33333",
    ]

    shared_candidate = next(
        item for item in pool
        if item["document_id"] == "arxiv:2222.22222"
    )

    assert shared_candidate["provenance"] == [
        {"method": "bm25", "rank": 1},
        {"method": "semantic", "rank": 2},
    ]


def test_keeps_distinct_documents_with_same_title():
    results_by_method = {
        "semantic": [
            make_result("arxiv:1111.11111", "Same Title"),
        ],
        "bm25": [
            make_result("arxiv:2222.22222", "Same Title"),
        ],
    }

    pool = build_union_pool(results_by_method, top_k=1)

    assert len(pool) == 2


def test_uses_only_top_k_from_each_method():
    results_by_method = {
        "semantic": [
            make_result("arxiv:1111.11111", "First"),
            make_result("arxiv:2222.22222", "Second"),
        ],
    }

    pool = build_union_pool(results_by_method, top_k=1)

    assert [item["document_id"] for item in pool] == [
        "arxiv:1111.11111",
    ]


def test_rejects_missing_document_id():
    with pytest.raises(ValueError, match="missing document_id"):
        build_union_pool(
            {
                "semantic": [
                    {
                        "title": "Invalid candidate",
                    }
                ]
            },
            top_k=1,
        )


def test_rejects_invalid_top_k():
    with pytest.raises(ValueError, match="top_k"):
        build_union_pool(
            {"semantic": []},
            top_k=0,
        )
