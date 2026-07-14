import pytest

from planning.roadmap_snapshot import (
    ROADMAP_CANONICALIZATION_VERSION,
    ROADMAP_SNAPSHOT_VERSION,
    build_roadmap_snapshot,
)
from schemas.product_models import (
    GuidedMissionStep,
    RoadmapStage,
)


def _stages():
    return [
        RoadmapStage(
            id="define",
            title="Define the problem",
            purpose="Choose a measurable scope.",
            tasks=["Write the problem statement."],
            objective="Define the project scope.",
            commands=["mkdir -p docs"],
            expected_outputs=["docs/problem.md"],
        ),
        RoadmapStage(
            id="mvp",
            title="Build the MVP",
            purpose="Implement one complete workflow.",
            tasks=["Create the first workflow."],
            objective="Build one input-to-output path.",
            commands=["python -m app"],
            expected_outputs=["outputs/result.json"],
            guided_steps=[
                GuidedMissionStep(
                    step_id="run-workflow",
                    title="Run the workflow",
                    explanation="Confirm the main path works.",
                    action="Execute the application.",
                    starter_command="python -m app",
                    starter_files=["app.py"],
                    done_when="A result file exists.",
                    common_confusion="A partial run is not complete.",
                    proof_type="output_paste",
                    proof_prompt="Paste the command output.",
                    expected_output_patterns=["result"],
                    interview_takeaway=(
                        "I built and validated one complete workflow."
                    ),
                )
            ],
        ),
    ]


def test_snapshot_is_deterministic():
    first = build_roadmap_snapshot(_stages())
    second = build_roadmap_snapshot(_stages())

    assert first == second
    assert len(first.roadmap_hash) == 64
    assert all(
        len(stage.content_hash) == 64
        for stage in first.stages
    )
    assert first.snapshot_version == (
        ROADMAP_SNAPSHOT_VERSION
    )
    assert first.canonicalization_version == (
        ROADMAP_CANONICALIZATION_VERSION
    )


def test_snapshot_preserves_stable_stage_ids_and_positions():
    snapshot = build_roadmap_snapshot(_stages())

    assert [
        stage.stage_id
        for stage in snapshot.stages
    ] == ["define", "mvp"]

    assert [
        stage.position
        for stage in snapshot.stages
    ] == [0, 1]


def test_stage_content_change_invalidates_only_affected_stage():
    original = build_roadmap_snapshot(_stages())

    changed_stages = _stages()
    changed_stages[1].tasks[0] = (
        "Create and validate the first workflow."
    )

    changed = build_roadmap_snapshot(changed_stages)

    assert (
        original.stages[0].content_hash
        == changed.stages[0].content_hash
    )
    assert (
        original.stages[1].content_hash
        != changed.stages[1].content_hash
    )
    assert original.roadmap_hash != changed.roadmap_hash


def test_guided_step_change_invalidates_stage_hash():
    original = build_roadmap_snapshot(_stages())

    changed_stages = _stages()
    changed_stages[1].guided_steps[0].done_when = (
        "A validated result file exists."
    )

    changed = build_roadmap_snapshot(changed_stages)

    assert (
        original.stages[1].content_hash
        != changed.stages[1].content_hash
    )


def test_stage_reordering_invalidates_roadmap_hash():
    stages = _stages()

    original = build_roadmap_snapshot(stages)
    reordered = build_roadmap_snapshot(
        list(reversed(stages))
    )

    assert original.roadmap_hash != reordered.roadmap_hash


def test_snapshot_preserves_unicode_deterministically():
    stages = _stages()
    stages[0].title = "समस्या परिभाषित करें"
    stages[0].tasks = ["문제 범위를 정의합니다."]

    snapshot = build_roadmap_snapshot(stages)

    assert (
        snapshot.stages[0].content["title"]
        == "समस्या परिभाषित करें"
    )
    assert (
        snapshot.stages[0].content["tasks"][0]
        == "문제 범위를 정의합니다."
    )


def test_duplicate_stage_ids_are_rejected():
    stages = _stages()
    stages[1].id = "define"

    with pytest.raises(
        ValueError,
        match="stage IDs must be unique",
    ):
        build_roadmap_snapshot(stages)
