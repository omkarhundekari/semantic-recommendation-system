import json
from pathlib import Path

from decision_trace_debug import write_decision_trace_artifact
from schemas.decision_trace_models import ProjectDecisionTrace


def build_trace():
    return ProjectDecisionTrace(
        idea_id="direction-1",
        idea_title="RAG Evaluation Studio",
        research_support_scope="planning_domain",
        buildable_gap="Inspect RAG pipeline failures.",
        confidence_level="strong",
        confidence_reason="Direct evidence is the majority.",
        planning_domain="rag_llm",
        planning_domain_reason="Registered RAG anchor selected the domain.",
        idea_specific_rationale="Evaluate retrieval and grounding quality.",
    )


def test_writes_trace_artifact_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITE_DECISION_TRACES", "1")

    output_path = write_decision_trace_artifact(
        query="Build a retrieval augmented generation project",
        traces=[build_trace()],
        output_dir=tmp_path,
    )

    assert output_path is not None
    assert output_path.exists()

    payload = json.loads(output_path.read_text())
    assert payload["query"] == "Build a retrieval augmented generation project"
    assert payload["traces"][0]["idea_id"] == "direction-1"


def test_does_not_write_trace_artifact_when_disabled(tmp_path, monkeypatch):
    monkeypatch.delenv("WRITE_DECISION_TRACES", raising=False)

    output_path = write_decision_trace_artifact(
        query="Build a retrieval augmented generation project",
        traces=[build_trace()],
        output_dir=tmp_path,
    )

    assert output_path is None
    assert list(tmp_path.iterdir()) == []


def test_does_not_break_when_trace_file_cannot_be_written(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("WRITE_DECISION_TRACES", "1")

    def raise_permission_error(self, *args, **kwargs):
        raise PermissionError("Writing trace artifacts is blocked.")

    monkeypatch.setattr(
        Path,
        "write_text",
        raise_permission_error,
    )

    output_path = write_decision_trace_artifact(
        query="Build a retrieval augmented generation project",
        traces=[build_trace()],
        output_dir=tmp_path,
    )

    assert output_path is None
