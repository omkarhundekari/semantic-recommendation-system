from pathlib import Path

from fastapi.testclient import TestClient

from execution_evidence.json_store import (
    JsonRepositoryEvidenceStore,
)
from execution_evidence.storage_service import (
    ExecutionEvidenceStorageRuntime,
)
from execution_evidence.trusted_store import (
    initialize_fresh_trusted_store,
)
from product_api import (
    app,
    build_roadmap,
    generate_project_intelligence,
    get_execution_evidence_storage_runtime,
)
from execution_evidence.storage_service import (
    TrustedSQLiteStorageService,
)


def test_rag_idea_receives_a_rag_specific_problem_definition_stage():
    idea = {
        "project_title": "RAG Evaluation Studio",
        "detected_domain": "rag_llm",
        "evidence_buildable_gap": (
            "Students and small teams need a practical way to inspect "
            "where a RAG pipeline is failing."
        ),
        "mvp_scope": ["Implement a small evaluation workflow."],
        "advanced_extensions": ["Add reranking comparison."],
    }

    roadmap = build_roadmap(idea)

    first_stage = roadmap[0]

    assert first_stage.title == "Define the RAG evaluation question"
    assert first_stage.purpose == (
        "Choose a narrow RAG workflow, a constrained document set, "
        "and measurable evaluation targets."
    )

    roadmap_text = " ".join(
        f"{stage.title} {stage.purpose} {' '.join(stage.tasks)}"
        for stage in roadmap
    ).lower()

    assert "turn the recommendation" not in roadmap_text
    assert "rag" in roadmap_text


def test_project_api_returns_playbook_aware_rag_roadmap_missions():
    from product_api import generate_project_intelligence
    from schemas.product_models import ProjectIntelligenceRequest

    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal="Build a RAG evaluation project for question answering",
        )
    )

    assert response.status == "ready"
    assert response.resolved_planning_domain == "rag_llm"
    assert response.directions

    roadmap = response.directions[0].roadmap
    roadmap_text = " ".join(
        " ".join(
            [
                stage.objective or "",
                " ".join(stage.commands),
                " ".join(stage.expected_outputs),
                " ".join(stage.validation_checks),
                stage.portfolio_artifact or "",
            ]
        )
        for stage in roadmap
    ).lower()

    assert "retrieval_precision_at_3" in roadmap_text
    assert "data/documents/" in roadmap_text
    assert "data/eval_questions.json" in roadmap_text
    assert "retrieved chunks with source metadata" in roadmap_text
    assert "outputs/retrieval_results.json" in roadmap_text


def test_project_api_returns_playbook_aware_frontend_roadmap_missions():
    from product_api import generate_project_intelligence
    from schemas.product_models import ProjectIntelligenceRequest

    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal="Build a React frontend portfolio project with loading and error states",
        )
    )

    assert response.status == "ready"
    assert response.resolved_planning_domain == "frontend"
    assert response.directions

    roadmap = response.directions[0].roadmap
    roadmap_text = " ".join(
        " ".join(
            [
                stage.objective or "",
                " ".join(stage.commands),
                " ".join(stage.expected_outputs),
                " ".join(stage.validation_checks),
                stage.portfolio_artifact or "",
            ]
        )
        for stage in roadmap
    ).lower()

    assert "frontend/app/" in roadmap_text
    assert "loading, empty, success, and error states" in roadmap_text
    assert "lighthouse_accessibility_score" in roadmap_text
    assert "component architecture" in roadmap_text
    assert "react" in roadmap_text
    assert "python, fastapi, postgresql" not in roadmap_text



def test_direct_generation_does_not_mint_uncommitted_identity():
    from schemas.product_models import (
        ProjectIntelligenceRequest,
    )

    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal=(
                "Build a RAG evaluation project "
                "for question answering"
            ),
        )
    )

    assert response.status == "ready"
    assert (
        response.persistence.roadmap_registry.status
        == "unavailable_error"
    )
    assert all(
        direction.project_id is None
        and direction.roadmap_snapshot_id is None
        and direction.project_direction_id is None
        for direction in response.directions
    )


def test_endpoint_atomically_registers_ready_roadmaps(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
    )
    service = TrustedSQLiteStorageService(
        database_path
    )
    runtime = ExecutionEvidenceStorageRuntime(
        evidence_store=(
            service.build_repository_evidence_store()
        ),
        trusted_sqlite_service=service,
        roadmap_registry=(
            service.build_roadmap_snapshot_registry()
        ),
        roadmap_registry_status="ready",
        remediation=None,
    )

    app.dependency_overrides[
        get_execution_evidence_storage_runtime
    ] = lambda: runtime

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/project-intelligence",
                json={
                    "goal": (
                        "Build a RAG evaluation project "
                        "for question answering"
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()

    assert payload["response_schema_version"] == 3
    assert payload["status"] == "ready"
    assert payload["persistence"] == {
        "roadmap_registry": {
            "status": "ready",
            "remediation": None,
        }
    }

    response_identities = {
        direction["project_direction_id"]: {
            "project_id": direction["project_id"],
            "roadmap_snapshot_id": (
                direction["roadmap_snapshot_id"]
            ),
        }
        for direction in payload["directions"]
    }

    assert len(response_identities) == 3
    assert all(response_identities)
    assert all(
        identity["project_id"]
        for identity in response_identities.values()
    )
    assert all(
        identity["roadmap_snapshot_id"]
        for identity in response_identities.values()
    )

    stored = runtime.roadmap_registry.list_snapshots()

    assert len(stored) == 3

    stored_identities = {
        record.project_direction_id: {
            "project_id": record.project_id,
            "roadmap_snapshot_id": (
                record.roadmap_snapshot_id
            ),
        }
        for record in stored
    }

    assert response_identities == stored_identities


def test_endpoint_reports_legacy_registry_unavailable(
    tmp_path: Path,
):
    json_store = JsonRepositoryEvidenceStore(
        tmp_path / "repositories.json"
    )
    runtime = ExecutionEvidenceStorageRuntime(
        evidence_store=json_store,
        trusted_sqlite_service=None,
        roadmap_registry=None,
        roadmap_registry_status=(
            "unavailable_legacy_store"
        ),
        remediation=(
            "Migrate the legacy JSON store."
        ),
    )

    app.dependency_overrides[
        get_execution_evidence_storage_runtime
    ] = lambda: runtime

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/project-intelligence",
                json={
                    "goal": (
                        "Build a React frontend "
                        "portfolio project"
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()

    assert (
        payload["persistence"]["roadmap_registry"][
            "status"
        ]
        == "unavailable_legacy_store"
    )
    assert all(
        direction["project_id"] is None
        and direction["roadmap_snapshot_id"] is None
        and direction["project_direction_id"] is None
        for direction in payload["directions"]
    )
