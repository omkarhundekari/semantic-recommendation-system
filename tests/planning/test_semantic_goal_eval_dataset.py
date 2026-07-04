import json
from pathlib import Path


DATASET_PATH = Path("data/semantic_goal_eval_v1.json")
REQUIRED_CANDIDATE_FIELDS = {
    "id",
    "label",
    "title",
    "problem_statement",
    "target_user",
}


def test_semantic_goal_evaluation_dataset_has_valid_labeled_cases():
    dataset = json.loads(DATASET_PATH.read_text())

    assert dataset["schema_version"] == 1
    assert dataset["cases"]

    case_ids = [case["id"] for case in dataset["cases"]]
    assert len(case_ids) == len(set(case_ids))

    for case in dataset["cases"]:
        assert case["id"].strip()
        assert case["user_goal"].strip()

        target_roles = case.get("target_roles", [])
        assert isinstance(target_roles, list)
        assert all(role.strip() for role in target_roles)

        candidates = case["candidates"]
        assert len(candidates) >= 3

        candidate_ids = [candidate["id"] for candidate in candidates]
        assert len(candidate_ids) == len(set(candidate_ids))

        labels = {candidate["label"] for candidate in candidates}
        assert 2 in labels
        assert 0 in labels

        for candidate in candidates:
            assert REQUIRED_CANDIDATE_FIELDS <= set(candidate)
            assert candidate["label"] in {0, 1, 2}
            assert candidate["id"].strip()
            assert candidate["title"].strip()
            assert candidate["problem_statement"].strip()
            assert candidate["target_user"].strip()
