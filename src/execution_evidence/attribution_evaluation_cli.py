from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from execution_evidence.attribution_evaluation import (
    ATTRIBUTION_EVALUATION_DATASET_VERSION,
    AttributionEvaluationDataset,
    AttributionEvaluationReport,
    evaluate_deterministic_attribution,
)


DEFAULT_DATASET_PATH = Path(
    "data/attribution_eval_v1.json"
)
DEFAULT_OUTPUT_PATH = Path(
    "outputs/execution_evidence/"
    "deterministic_attribution_eval_v1.json"
)


def load_attribution_evaluation_dataset(
    path: Path,
) -> AttributionEvaluationDataset:
    try:
        raw_document = path.read_text(
            encoding="utf-8"
        )
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"Attribution evaluation dataset was not found: "
            f"{path}"
        ) from error

    dataset = (
        AttributionEvaluationDataset
        .model_validate_json(raw_document)
    )

    if (
        dataset.dataset_version
        != ATTRIBUTION_EVALUATION_DATASET_VERSION
    ):
        raise ValueError(
            "Unsupported attribution evaluation dataset "
            f"version: {dataset.dataset_version}. "
            "Expected version "
            f"{ATTRIBUTION_EVALUATION_DATASET_VERSION}."
        )

    return dataset


def serialize_attribution_evaluation_report(
    report: AttributionEvaluationReport,
) -> str:
    payload = report.model_dump(
        mode="json",
        exclude_none=False,
    )

    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def write_attribution_evaluation_report(
    *,
    dataset_path: Path,
    output_path: Path,
) -> AttributionEvaluationReport:
    dataset = load_attribution_evaluation_dataset(
        dataset_path
    )
    report = evaluate_deterministic_attribution(
        dataset
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    output_path.write_text(
        serialize_attribution_evaluation_report(
            report
        ),
        encoding="utf-8",
    )

    return report


def main(
    argv: Optional[Sequence[str]] = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate deterministic execution-evidence "
            "attribution against a labeled dataset."
        )
    )
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=DEFAULT_DATASET_PATH,
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
    )

    args = parser.parse_args(argv)

    report = write_attribution_evaluation_report(
        dataset_path=args.dataset_path,
        output_path=args.output_path,
    )

    print(
        json.dumps(
            report.overall.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
    )
    print(
        f"Wrote attribution evaluation report: "
        f"{args.output_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
