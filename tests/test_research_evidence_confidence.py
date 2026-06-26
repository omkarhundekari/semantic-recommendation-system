from research_evidence_confidence import classify_evidence_confidence


def test_marks_broad_direct_support_as_strong():
    result = classify_evidence_confidence(
        {
            "paper_count": 5,
            "alignment_summary": {
                "direct": 4,
                "adjacent": 1,
                "weak": 0,
            },
            "evidence_tags": {
                "method": 5,
                "application": 4,
                "benchmark": 2,
            },
        }
    )

    assert result["level"] == "strong"
    assert "direct evidence" in result["reason"].lower()


def test_marks_some_direct_support_as_limited():
    result = classify_evidence_confidence(
        {
            "paper_count": 5,
            "alignment_summary": {
                "direct": 1,
                "adjacent": 3,
                "weak": 1,
            },
            "evidence_tags": {
                "method": 4,
                "application": 2,
            },
        }
    )

    assert result["level"] == "limited"


def test_marks_adjacent_only_support_as_exploratory():
    result = classify_evidence_confidence(
        {
            "paper_count": 5,
            "alignment_summary": {
                "direct": 0,
                "adjacent": 3,
                "weak": 2,
            },
            "evidence_tags": {
                "method": 3,
            },
        }
    )

    assert result["level"] == "exploratory"
    assert "no direct" in result["reason"].lower()


def test_downgrades_direct_only_evidence_without_method_and_application_support():
    result = classify_evidence_confidence(
        {
            "paper_count": 4,
            "alignment_summary": {
                "direct": 4,
                "adjacent": 0,
                "weak": 0,
            },
            "evidence_tags": {
                "trend": 4,
            },
        }
    )

    assert result["level"] == "limited"
    assert "method" in result["reason"].lower()
    assert "application" in result["reason"].lower()


def test_does_not_use_adjacent_tags_to_upgrade_direct_evidence_to_strong():
    result = classify_evidence_confidence(
        {
            "paper_count": 4,
            "alignment_summary": {
                "direct": 3,
                "adjacent": 1,
                "weak": 0,
            },
            "evidence_tags": {
                "method": 1,
                "application": 1,
            },
            "supporting_papers": [
                {
                    "alignment": "direct",
                    "evidence_tags": ["trend"],
                },
                {
                    "alignment": "direct",
                    "evidence_tags": ["trend"],
                },
                {
                    "alignment": "direct",
                    "evidence_tags": ["trend"],
                },
                {
                    "alignment": "adjacent",
                    "evidence_tags": ["method", "application"],
                },
            ],
        }
    )

    assert result["level"] == "limited"
    assert "direct papers" in result["reason"].lower()
