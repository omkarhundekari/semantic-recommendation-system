import argparse
import json
import warnings

warnings.filterwarnings(
    "ignore",
    message="urllib3 v2 only supports OpenSSL.*",
)

from product_api import generate_project_intelligence
from schemas.product_models import ProjectIntelligenceRequest


def parse_args():
    parser = argparse.ArgumentParser(
        description="Smoke test project synthesis status payload."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full validation payload.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal=(
                "Build a retrieval augmented generation project for "
                "question answering for ML engineer roles in 3 weeks"
            ),
            selected_direction="AI / ML",
        )
    )

    payload = response.model_dump()
    synthesis_status = payload.get("synthesis_status", {})
    summary = synthesis_status.get("synthesis_summary", {})

    print("Status:", payload.get("status"))
    print("Resolved planning domain:", payload.get("resolved_planning_domain"))
    print("Direction count:", len(payload.get("directions", [])))
    print()
    print("Synthesis summary:")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print()
    print("Frontend project directions:")
    for index, direction in enumerate(
        synthesis_status.get("frontend_project_directions", []),
        start=1,
    ):
        print(
            f"{index}. "
            f"{direction.get('level')} / "
            f"{direction.get('estimated_time')}: "
            f"{direction.get('title')}"
        )
        if direction.get("tier"):
            print(f"   Tier: {direction.get('tier')}")
        print(f"   Badge: {direction.get('evidence_badge')}")
        print(f"   Summary: {direction.get('summary')}")
        print(f"   Why: {direction.get('why_it_matters')}")
        print(f"   Skills: {', '.join(direction.get('skills_shown', [])[:3])}")
        print(f"   Talking point: {direction.get('interview_talking_point')}")

    print()
    print("Live evidence cards:")
    print(json.dumps(
        synthesis_status.get("live_evidence_cards", {}),
        indent=2,
        sort_keys=True,
    ))
    validation = synthesis_status.get(
        "live_final_synthesis_preview_validation",
        {},
    )
    print()
    print("Preview validation:")
    print("is_valid:", validation.get("is_valid"))
    print("invented_source_ids:", validation.get("invented_source_ids"))
    print("failure_categories:", validation.get("failure_categories"))
    print(
        "grounded_direction_count:",
        sum(
            1
            for trace in validation.get("direction_grounding_traces", [])
            if trace.get("is_grounded")
        ),
    )

    if args.verbose:
        print()
        print("Full preview validation:")
        print(json.dumps(
            validation,
            indent=2,
            sort_keys=True,
            default=str,
        ))


if __name__ == "__main__":
    main()
