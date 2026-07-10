from product_api import run_synthesis_demo_endpoint
from schemas.product_models import SynthesisDemoRequest


ARTIFACT_PATH = (
    "data/manual_fixture_artifacts/deterministic_template_risk/"
    "1bc94b0f56984302922f13d42dcb2a2e.json"
)


def test_synthesis_demo_endpoint_exposes_safe_final_synthesis():
    response = run_synthesis_demo_endpoint(
        SynthesisDemoRequest(
            artifact_path=ARTIFACT_PATH,
            provider="fake",
            dry_run=True,
            mode="deep",
        )
    )

    assert response["status"] == "ready"
    assert response["provider"] == "fake-dry-run"
    assert response["dry_run"] is True
    assert response["api_call_attempted"] is False

    assert response["saved_output_validation"]["is_valid"] is False
    assert response["final_synthesis"]["source"] == "deterministic_fallback"
    assert response["final_synthesis"]["fallback_used"] is True
    assert response["final_synthesis_validation"]["is_valid"] is True
    assert response["final_synthesis_validation"]["failure_categories"] == ()
    assert all(
        trace["is_grounded"]
        for trace in response["final_synthesis_validation"][
            "direction_grounding_traces"
        ]
    )
