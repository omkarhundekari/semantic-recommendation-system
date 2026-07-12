import github_corpus_search


def test_search_returns_empty_results_when_optional_corpus_is_missing(
    monkeypatch,
):
    monkeypatch.setattr(
        github_corpus_search,
        "GITHUB_CORPUS_PATH",
        "data/nonexistent_github_project_corpus.csv",
    )

    results = github_corpus_search.search_github_project_corpus(
        "RAG evaluation project",
        top_k=5,
    )

    assert results == []
