from query_expander import get_query_metadata


def test_medium_confidence_typos_are_recorded_but_not_applied():
    metadata = get_query_metadata(
        "Build a developer productivity project that helps engineers "
        "identify flaky tests and connect failures with code changes."
    )

    assert "flaky" in metadata["corrected_query"]
    assert "flask" not in metadata["corrected_query"]
    assert "that" in metadata["corrected_query"]
    assert "threat" not in metadata["corrected_query"]

    suggested_pairs = {
        (item["original"], item["corrected"])
        for item in metadata["medium_confidence_corrections"]
    }

    assert ("flaky", "flask") in suggested_pairs
    assert ("that", "threat") in suggested_pairs


def test_explicit_domain_tokens_take_priority():
    from query_expander import detect_domain, get_query_metadata

    assert detect_domain("DevOps observability dashboard project") == "devops"
    assert detect_domain("React portfolio project for frontend roles") == "frontend"
    assert detect_domain("FinTech fraud detection project") == "fintech"
    assert detect_domain("MLOps experiment tracking project") == "mlops"

    metadata = get_query_metadata("MLOps experiment tracking project")
    assert metadata["query_requires_confirmation"] is False
    assert metadata["query_corrections"] == []
