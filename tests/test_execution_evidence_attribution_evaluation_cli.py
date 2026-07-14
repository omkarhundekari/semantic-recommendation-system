import json
from pathlib import Path

import pytest

from execution_evidence.attribution_evaluation import (
    ATTRIBUTION_EVALUATION_DATASET_VERSION,
    AttributionEvaluationDataset,
)
from execution_evidence.attribution_evaluation_cli import (
    load_attribution_evaluation_dataset,
    main,
    serialize_attribution_evaluation_report,
    write_attribution_evaluation_report,
)


DATASET_PATH = Path(
    "data/attribution_eval_v1.json"
)


def test_tracked_dataset_is_valid_and_versioned():
    dataset = load_attribution_evaluation_dataset(
        DATASET_PATH
    )

    assert isinstance(
        dataset,
        AttributionEvaluationDataset,
    )
    assert dataset.dataset_version == (
        ATTRIBUTION_EVALUATION_DATASET_VERSION
    )
    assert len(dataset.cases) >= 8
    assert len(
        {
            case.repository_id
            for case in dataset.cases
        }
    ) >= 2
    assert {
        case.evidence.evidence_type
        for case in dataset.cases
    } == {
        "commit",
        "pull_request",
        "release",
        "workflow_run",
    }


def test_loader_rejects_unsupported_dataset_version(
    tmp_path,
):
    payload = json.loads(
        DATASET_PATH.read_text(
            encoding="utf-8"
        )
    )
    payload["dataset_version"] = 999

    path = tmp_path / "unsupported.json"
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported attribution evaluation",
    ):
        load_attribution_evaluation_dataset(path)


def test_report_serialization_is_byte_stable():
    dataset = load_attribution_evaluation_dataset(
        DATASET_PATH
    )

    first_path = Path(
        "outputs/test-attribution-eval-first.json"
    )
    second_path = Path(
        "outputs/test-attribution-eval-second.json"
    )

    try:
        first = write_attribution_evaluation_report(
            dataset_path=DATASET_PATH,
            output_path=first_path,
        )
        second = write_attribution_evaluation_report(
            dataset_path=DATASET_PATH,
            output_path=second_path,
        )

        assert first == second
        assert (
            first_path.read_bytes()
            == second_path.read_bytes()
        )
        assert (
            first_path.read_text(encoding="utf-8")
            == serialize_attribution_evaluation_report(
                first
            )
        )
    finally:
        first_path.unlink(missing_ok=True)
        second_path.unlink(missing_ok=True)


def test_cli_writes_requested_report(tmp_path):
    output_path = tmp_path / "report.json"

    exit_code = main(
        [
            "--dataset-path",
            str(DATASET_PATH),
            "--output-path",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert output_path.exists()

    payload = json.loads(
        output_path.read_text(
            encoding="utf-8"
        )
    )

    assert payload["dataset_version"] == (
        ATTRIBUTION_EVALUATION_DATASET_VERSION
    )
    assert payload["overall"]["case_count"] >= 8
    assert "attribution_policy_version" in payload
    assert "roadmap_hashes" in payload
