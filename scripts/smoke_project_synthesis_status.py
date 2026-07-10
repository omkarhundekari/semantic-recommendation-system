import json

from product_api import generate_project_intelligence
from schemas.product_models import ProjectIntelligenceRequest


def main():
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
    print("Live evidence cards:")
    print(json.dumps(
        synthesis_status.get("live_evidence_cards", {}),
        indent=2,
        sort_keys=True,
    ))
    print()
    print("Preview validation:")
    print(json.dumps(
        synthesis_status.get("live_final_synthesis_preview_validation", {}),
        indent=2,
        sort_keys=True,
        default=str,
    ))


if __name__ == "__main__":
    main()
