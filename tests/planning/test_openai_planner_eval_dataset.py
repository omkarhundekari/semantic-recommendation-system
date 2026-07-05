import json
from pathlib import Path


DATASET_PATH = Path("data/openai_planner_eval_v1.json")
REQUIRED_CASE_FIELDS = {
    "id",
    "user_goal",
    "skill_level",
    "time_available",
    "target_roles",
    "preferred_stack",
    "review_focus",
    "manual_review",
}


def test_openai_planner_evaluation_manifest_is_valid():
    dataset = json.loads(DATASET_PATH.read_text())

    assert dataset["schema_version"] == 1
    assert dataset["cases"]
    assert len(dataset["cases"]) >= 5

    case_ids = [case["id"] for case in dataset["cases"]]
    assert len(case_ids) == len(set(case_ids))

    for case in dataset["cases"]:
        assert REQUIRED_CASE_FIELDS <= set(case)
        assert case["id"].strip()
        assert case["user_goal"].strip()
        assert case["skill_level"].strip()
        assert case["time_available"].strip()

        assert isinstance(case["target_roles"], list)
        assert case["target_roles"]
        assert all(role.strip() for role in case["target_roles"])

        assert isinstance(case["preferred_stack"], list)
        assert case["preferred_stack"]
        assert all(stack.strip() for stack in case["preferred_stack"])

        assert isinstance(case["review_focus"], list)
        assert case["review_focus"]

        manual_review = case["manual_review"]
        assert set(manual_review) == {"verdict", "reason"}
        assert manual_review["verdict"] in {
            None,
            "openai",
            "deterministic",
            "tie"
        }
        assert manual_review["reason"] is None or isinstance(
            manual_review["reason"],
            str,
        )
