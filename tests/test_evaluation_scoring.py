from evaluation_scoring import score_ranking_if_covered


def ranking(*document_ids):
    return [{"document_id": document_id} for document_id in document_ids]


def test_scores_fully_covered_ranking():
    result = score_ranking_if_covered(
        ranking("arxiv:1", "arxiv:2", "arxiv:3"),
        {
            "arxiv:1": 2,
            "arxiv:2": 0,
            "arxiv:3": 1,
        },
        top_k=3,
    )

    assert result["eligible"] is True
    assert result["relevances"] == [2, 0, 1]
    assert result["precision_at_k"] == 2 / 3
    assert result["reciprocal_rank"] == 1.0
    assert 0 < result["ndcg_at_k"] <= 1.0


def test_does_not_score_incomplete_ranking():
    result = score_ranking_if_covered(
        ranking("arxiv:1", "arxiv:2"),
        {
            "arxiv:1": 2,
        },
        top_k=2,
    )

    assert result["eligible"] is False
    assert result["relevances"] is None
    assert result["precision_at_k"] is None
    assert result["reciprocal_rank"] is None
    assert result["ndcg_at_k"] is None
    assert result["missing_document_ids"] == ["arxiv:2"]


def test_uses_requested_top_k_only():
    result = score_ranking_if_covered(
        ranking("arxiv:1", "arxiv:2", "arxiv:3"),
        {
            "arxiv:1": 0,
            "arxiv:2": 2,
            "arxiv:3": 2,
        },
        top_k=2,
    )

    assert result["relevances"] == [0, 2]
    assert result["precision_at_k"] == 0.5
    assert result["reciprocal_rank"] == 0.5
