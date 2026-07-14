from pathlib import Path

from fastapi.testclient import TestClient

from execution_evidence.json_store import (
    JsonRepositoryEvidenceStore,
)
from product_api import (
    app,
    get_execution_evidence_store,
)


def test_storage_readiness_endpoint_reports_active_backend(
    tmp_path: Path,
):
    store = JsonRepositoryEvidenceStore(
        tmp_path / "repositories.json"
    )

    app.dependency_overrides[
        get_execution_evidence_store
    ] = lambda: store

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/execution-evidence/storage/readiness"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "ready"
    assert payload["backend"] == "json"
    assert "path" not in payload
    assert payload["errors"] == []
