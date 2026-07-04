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
