from fastapi.testclient import TestClient

from product_api import app


def test_storage_readiness_endpoint_reports_active_backend():
    with TestClient(app) as client:
        response = client.get(
            "/v1/execution-evidence/storage/readiness"
        )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "ready"
    assert payload["backend"] == "json"
    assert "path" not in payload
    assert payload["errors"] == []
