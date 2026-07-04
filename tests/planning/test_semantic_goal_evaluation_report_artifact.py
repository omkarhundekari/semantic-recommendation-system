import json

from planning.semantic_goal_evaluation_report import (
    write_semantic_goal_evaluation_report,
)


def test_write_semantic_goal_evaluation_report_creates_json_artifact(
    tmp_path,
):
    report = {
        "schema_version": "1.0",
        "summary": {
            "evaluated_case_count": 1,
            "escalated_case_count": 0,
        },
    }

    output_path = write_semantic_goal_evaluation_report(
        report=report,
        output_dir=tmp_path,
    )

    assert output_path.parent == tmp_path
    assert output_path.name.startswith("semantic_goal_evaluation_")
    assert output_path.suffix == ".json"
    assert json.loads(output_path.read_text()) == report
