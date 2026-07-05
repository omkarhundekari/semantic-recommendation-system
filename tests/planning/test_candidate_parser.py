import pytest

from planning.candidate_parser import parse_candidate_payload


def valid_payload():
    return {
        "candidates": [
            {
                "title": "Incident Correlation Workbench",
                "problem_statement": "Incident evidence is fragmented.",
                "target_user": "Platform engineers",
                "core_workflow": [
                    "Ingest service events.",
                    "Correlate related incidents.",
                ],
                "mvp_scope": [
                    "Load sample events.",
                    "Correlate related records.",
                    "Render an investigation timeline.",
                ],
                "success_metrics": [
                    "Time to identify related events.",
                ],
                "evidence_relationship": (
                    "Uses evidence-supported event-correlation workflows."
                ),
                "source_ids": ["paper-1"],
                "assumptions": ["Use synthetic incident data."],
                "suggested_stack": ["Python", "FastAPI"],
            }
        ]
    }


def test_parser_builds_candidate_direction():
    candidates = parse_candidate_payload(valid_payload())

    assert len(candidates) == 1
    assert candidates[0].title == "Incident Correlation Workbench"
    assert candidates[0].source_ids == ["paper-1"]


def test_parser_rejects_invalid_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_candidate_payload("{not-json")


def test_parser_rejects_missing_required_fields():
    payload = valid_payload()
    del payload["candidates"][0]["mvp_scope"]

    with pytest.raises(ValueError, match="missing required fields"):
        parse_candidate_payload(payload)


def test_parser_builds_single_regenerated_candidate():
    from planning.candidate_parser import (
        parse_single_candidate_payload,
    )

    candidate = parse_single_candidate_payload(
        {
            "candidate": valid_payload()["candidates"][0],
        }
    )

    assert candidate.title == "Incident Correlation Workbench"
    assert candidate.source_ids == ["paper-1"]


def test_parser_rejects_regeneration_without_candidate_object():
    from planning.candidate_parser import (
        parse_single_candidate_payload,
    )

    with pytest.raises(ValueError, match="candidate object"):
        parse_single_candidate_payload({"candidates": []})
