import pytest

from evaluation_coverage import assess_label_coverage


def ranking(*document_ids):
    return [{"document_id": document_id} for document_id in document_ids]


def test_marks_fully_labeled_ranking_as_eligible():
    result = assess_label_coverage(
        ranking("arxiv:1", "arxiv:2"),
        {"arxiv:1": 2, "arxiv:2": 1},
        top_k=2,
    )

    assert result == {
        "eligible": True,
        "requested_count": 2,
        "labeled_count": 2,
        "missing_document_ids": [],
        "coverage": 1.0,
    }


def test_excludes_ranking_with_missing_labels():
    result = assess_label_coverage(
        ranking("arxiv:1", "arxiv:2", "arxiv:3"),
        {"arxiv:1": 2, "arxiv:3": 0},
        top_k=3,
    )

    assert result["eligible"] is False
    assert result["labeled_count"] == 2
    assert result["coverage"] == 2 / 3
    assert result["missing_document_ids"] == ["arxiv:2"]


def test_rejects_invalid_top_k():
    with pytest.raises(ValueError, match="top_k"):
        assess_label_coverage(
            ranking("arxiv:1"),
            {"arxiv:1": 2},
            top_k=0,
        )


def test_rejects_missing_document_id():
    with pytest.raises(ValueError, match="document_id"):
        assess_label_coverage(
            [{"title": "No ID"}],
            {},
            top_k=1,
        )
