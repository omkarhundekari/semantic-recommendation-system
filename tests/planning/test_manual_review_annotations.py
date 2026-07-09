import pytest

from planning.manual_review_annotations import (
    append_manual_review_annotation,
    build_manual_review_annotation,
    build_manual_review_annotation_summary,
    load_manual_review_annotations,
)


def _annotation(**overrides):
    values = {
        "review_id": "a" * 32,
        "artifact_id": "b" * 32,
        "fixture_id": "sparse_evidence_cloud_cost",
        "annotator_id": "reviewer_a",
        "packet_generator_version": "v1",
        "reviewer_confidence": "high",
        "reviewer_confidence_reason": "",
        "both_weak_diagnosis": "evidence_sparse",
        "both_weak_diagnosis_reason": (
            "Only weak evidence supports root-cause cost explanation."
        ),
        "relevance_trace_assessment": "traces_match_reviewer_judgment",
        "relevance_trace_assessment_notes": (
            "No suspicious trace false positives were observed."
        ),
        "annotation_id": "c" * 32,
        "annotated_at_utc": "20260709T023500Z",
    }
    values.update(overrides)
    return build_manual_review_annotation(**values)


def test_builds_manual_review_annotation_record():
    annotation = _annotation()

    payload = annotation.to_dict()

    assert payload["schema_version"] == "v1"
    assert payload["review_id"] == "a" * 32
    assert payload["artifact_id"] == "b" * 32
    assert payload["fixture_id"] == "sparse_evidence_cloud_cost"
    assert payload["packet_generator_version"] == "v1"
    assert payload["reviewer_confidence"] == "high"
    assert payload["both_weak_diagnosis"] == "evidence_sparse"
    assert (
        payload["relevance_trace_assessment"]
        == "traces_match_reviewer_judgment"
    )


def test_appends_and_loads_annotations_without_mutating_prior_rows(tmp_path):
    path = tmp_path / "manual_review_annotations.jsonl"

    first = _annotation(
        annotation_id="c" * 32,
        review_id="a" * 32,
        artifact_id="b" * 32,
    )
    second = _annotation(
        annotation_id="d" * 32,
        review_id="e" * 32,
        artifact_id="f" * 32,
    )

    append_manual_review_annotation(first, path)
    original_contents = path.read_text()

    append_manual_review_annotation(second, path)
    annotations = load_manual_review_annotations(path)

    assert len(annotations) == 2
    assert path.read_text().startswith(original_contents)
    assert annotations[0].review_id == "a" * 32
    assert annotations[1].review_id == "e" * 32


def test_rejects_duplicate_review_annotation(tmp_path):
    path = tmp_path / "manual_review_annotations.jsonl"

    annotation = _annotation()

    append_manual_review_annotation(annotation, path)

    with pytest.raises(ValueError, match="already has an annotation"):
        append_manual_review_annotation(
            _annotation(annotation_id="d" * 32),
            path,
        )


def test_requires_confidence_reason_for_low_confidence():
    with pytest.raises(ValueError, match="confidence_reason"):
        _annotation(
            reviewer_confidence="low",
            reviewer_confidence_reason="",
        )


def test_requires_both_weak_reason_when_diagnosis_is_specific():
    with pytest.raises(ValueError, match="both_weak_diagnosis_reason"):
        _annotation(
            both_weak_diagnosis="query_underspecified",
            both_weak_diagnosis_reason="",
        )


def test_rejects_invalid_relevance_trace_assessment():
    with pytest.raises(ValueError, match="relevance_trace_assessment"):
        _annotation(relevance_trace_assessment="bad_value")


def test_summarizes_annotation_metadata():
    summary = build_manual_review_annotation_summary(
        [
            _annotation(
                annotation_id="c" * 32,
                review_id="a" * 32,
                reviewer_confidence="high",
                relevance_trace_assessment=(
                    "traces_match_reviewer_judgment"
                ),
            ),
            _annotation(
                annotation_id="d" * 32,
                review_id="e" * 32,
                artifact_id="f" * 32,
                reviewer_confidence="medium",
                reviewer_confidence_reason=(
                    "One candidate score was somewhat subjective."
                ),
                both_weak_diagnosis=None,
                both_weak_diagnosis_reason=None,
                relevance_trace_assessment="not_assessed",
            ),
        ]
    )

    assert summary["annotation_count"] == 2
    assert summary["confidence_counts"] == {
        "high": 1,
        "medium": 1,
    }
    assert summary["both_weak_diagnosis_counts"] == {
        "evidence_sparse": 1,
    }
    assert summary["relevance_trace_assessment_counts"] == {
        "not_assessed": 1,
        "traces_match_reviewer_judgment": 1,
    }
