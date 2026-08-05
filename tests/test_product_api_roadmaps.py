from pathlib import Path

from fastapi.testclient import TestClient

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.authorized_project_context import (
    AuthorizedProjectContext,
)
from execution_evidence.project_access_service import (
    ProjectAccessNotFoundError,
)
from execution_evidence.request_authenticator import (
    RequestAuthenticationRequiredError,
)
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
    get_project_access_service,
    get_request_authenticator,
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



PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174000"
)
PROVIDER_ID = (
    "idp_123e4567-e89b-42d3-a456-426614174001"
)
LINK_ID = (
    "pil_123e4567-e89b-42d3-a456-426614174002"
)
MEMBERSHIP_ID = (
    "wsm_123e4567-e89b-42d3-a456-426614174003"
)


def _lifecycle_principal(
) -> AuthenticatedRequestPrincipal:
    return AuthenticatedRequestPrincipal(
        principal_id=PRINCIPAL_ID,
        identity_provider_id=PROVIDER_ID,
        identity_link_id=LINK_ID,
        issuer="https://issuer.example",
        subject="subject-123",
    )


class _LifecycleAuthenticator:
    def __init__(
        self,
        *,
        principal=None,
        error=None,
    ):
        self.principal = (
            principal
            if principal is not None
            else _lifecycle_principal()
        )
        self.error = error
        self.headers = []

    def authenticate(self, header):
        self.headers.append(header)

        if self.error is not None:
            raise self.error

        return self.principal


class _LifecycleProjectAccessService:
    def __init__(
        self,
        context: AuthorizedProjectContext,
        *,
        error=None,
    ):
        self.context = context
        self.error = error
        self.calls = []

    def authorize(
        self,
        *,
        principal,
        workspace_id,
        project_id,
    ):
        self.calls.append(
            (
                principal,
                workspace_id,
                project_id,
            )
        )

        if self.error is not None:
            raise self.error

        return self.context


def _install_lifecycle_auth(
    runtime,
    *,
    project_id: str,
):
    if runtime.roadmap_registry is None:
        raise ValueError(
            "Lifecycle auth helper requires a "
            "workspace-bound roadmap registry."
        )

    workspace_id = (
        runtime.roadmap_registry.workspace_id
    )

    context = AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        workspace_id=workspace_id,
        project_id=project_id,
    )

    access_service = (
        _LifecycleProjectAccessService(
            context
        )
    )

    app.dependency_overrides[
        get_execution_evidence_storage_runtime
    ] = lambda: runtime
    app.dependency_overrides[
        get_request_authenticator
    ] = lambda: _LifecycleAuthenticator()
    app.dependency_overrides[
        get_project_access_service
    ] = lambda: access_service

    return workspace_id, access_service


def _install_lifecycle_auth_for_scope(
    runtime,
    *,
    workspace_id: str,
    project_id: str,
):
    context = AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        workspace_id=workspace_id,
        project_id=project_id,
    )

    access_service = (
        _LifecycleProjectAccessService(
            context
        )
    )

    app.dependency_overrides[
        get_execution_evidence_storage_runtime
    ] = lambda: runtime
    app.dependency_overrides[
        get_request_authenticator
    ] = lambda: _LifecycleAuthenticator()
    app.dependency_overrides[
        get_project_access_service
    ] = lambda: access_service

    return access_service


def _lifecycle_status_path(
    workspace_id: str,
    project_id: str,
) -> str:
    return (
        f"/v1/workspaces/{workspace_id}/"
        f"projects/{project_id}/status"
    )


def _lifecycle_history_path(
    workspace_id: str,
    project_id: str,
) -> str:
    return (
        f"/v1/workspaces/{workspace_id}/"
        f"projects/{project_id}/"
        "status-transitions"
    )


def _trusted_lifecycle_runtime(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-14T12:00:00+00:00",
    )
    service = TrustedSQLiteStorageService(
        database_path
    )

    return ExecutionEvidenceStorageRuntime(
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


def _create_lifecycle_project(
    runtime,
):
    from datetime import datetime, timezone

    from planning.roadmap_registry import (
        create_stored_roadmap_snapshot,
    )
    from planning.roadmap_snapshot import (
        RoadmapSnapshot,
        RoadmapStageSnapshot,
    )

    snapshot = RoadmapSnapshot(
        roadmap_hash="a" * 64,
        stages=[
            RoadmapStageSnapshot(
                stage_id="mvp",
                position=0,
                content_hash="b" * 64,
                content={
                    "id": "mvp",
                    "title": "Build",
                    "purpose": "Build the project.",
                    "tasks": [
                        "Implement the MVP."
                    ],
                },
            )
        ],
    )

    return runtime.roadmap_registry.create(
        create_stored_roadmap_snapshot(
            project_id="proj_lifecycle",
            response_direction_id="direction-one",
            title="Lifecycle project",
            snapshot=snapshot,
            created_at=datetime(
                2026,
                7,
                14,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        )
    )


def test_project_status_endpoint_archives_project(
    tmp_path: Path,
):
    runtime = _trusted_lifecycle_runtime(
        tmp_path
    )
    stored = _create_lifecycle_project(runtime)

    workspace_id, access = (
        _install_lifecycle_auth(
            runtime,
            project_id=stored.project_id,
        )
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                _lifecycle_status_path(
                    workspace_id,
                    stored.project_id,
                ),
                headers={
                    "Authorization": "Bearer token",
                },
                json={
                    "status": "archived",
                    "reason": "Paused temporarily.",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()

    assert payload["changed"] is True
    assert payload["project_id"] == stored.project_id
    assert payload["previous_status"] == "active"
    assert payload["current_status"] == "archived"
    assert payload["transition"]["reason"] == (
        "Paused temporarily."
    )

    assert len(access.calls) == 1
    assert access.calls[0][1:] == (
        workspace_id,
        stored.project_id,
    )


def test_project_status_endpoint_is_idempotent(
    tmp_path: Path,
):
    runtime = _trusted_lifecycle_runtime(
        tmp_path
    )
    stored = _create_lifecycle_project(runtime)

    workspace_id, _ = _install_lifecycle_auth(
        runtime,
        project_id=stored.project_id,
    )

    status_path = _lifecycle_status_path(
        workspace_id,
        stored.project_id,
    )
    history_path = _lifecycle_history_path(
        workspace_id,
        stored.project_id,
    )

    headers = {
        "Authorization": "Bearer token",
    }

    try:
        with TestClient(app) as client:
            first = client.post(
                status_path,
                headers=headers,
                json={
                    "status": "archived",
                    "expected_revision": 0,
                },
            )
            second = client.post(
                status_path,
                headers=headers,
                json={
                    "status": "archived",
                    "expected_revision": 1,
                },
            )
            history = client.get(
                history_path,
                headers=headers,
            )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == {
        "changed": False,
        "project_id": stored.project_id,
        "previous_status": "archived",
        "current_status": "archived",
        "revision": 1,
        "transition": None,
    }
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_deleted_project_cannot_be_reactivated_via_api(
    tmp_path: Path,
):
    runtime = _trusted_lifecycle_runtime(
        tmp_path
    )
    stored = _create_lifecycle_project(runtime)

    workspace_id, _ = _install_lifecycle_auth(
        runtime,
        project_id=stored.project_id,
    )

    path = _lifecycle_status_path(
        workspace_id,
        stored.project_id,
    )

    headers = {
        "Authorization": "Bearer token",
    }

    try:
        with TestClient(app) as client:
            deleted = client.post(
                path,
                headers=headers,
                json={
                    "status": "deleted",
                    "expected_revision": 0,
                },
            )
            restored = client.post(
                path,
                headers=headers,
                json={
                    "status": "active",
                    "expected_revision": 1,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert deleted.status_code == 200
    assert restored.status_code == 409
    assert "deleted -> active" in (
        restored.json()["detail"]
    )


def test_project_status_endpoint_returns_404(
    tmp_path: Path,
):
    runtime = _trusted_lifecycle_runtime(
        tmp_path
    )

    # Deliberately authorize a nonexistent project so this
    # regression exercises the registry's ProjectNotFoundError
    # branch rather than failing in project authorization.
    workspace_id, _ = _install_lifecycle_auth(
        runtime,
        project_id="proj_missing",
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                _lifecycle_status_path(
                    workspace_id,
                    "proj_missing",
                ),
                headers={
                    "Authorization": "Bearer token",
                },
                json={
                    "status": "archived",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_project_status_history_is_newest_first(
    tmp_path: Path,
):
    runtime = _trusted_lifecycle_runtime(
        tmp_path
    )
    stored = _create_lifecycle_project(runtime)

    workspace_id, _ = _install_lifecycle_auth(
        runtime,
        project_id=stored.project_id,
    )

    status_path = _lifecycle_status_path(
        workspace_id,
        stored.project_id,
    )
    history_path = _lifecycle_history_path(
        workspace_id,
        stored.project_id,
    )

    headers = {
        "Authorization": "Bearer token",
    }

    try:
        with TestClient(app) as client:
            archived = client.post(
                status_path,
                headers=headers,
                json={
                    "status": "archived",
                    "expected_revision": 0,
                },
            )
            active = client.post(
                status_path,
                headers=headers,
                json={
                    "status": "active",
                    "expected_revision": 1,
                },
            )
            response = client.get(
                history_path,
                headers=headers,
            )
    finally:
        app.dependency_overrides.clear()

    assert archived.status_code == 200
    assert active.status_code == 200
    assert response.status_code == 200

    history = response.json()

    assert len(history) == 2
    assert history[0]["previous_status"] == (
        "archived"
    )
    assert history[0]["new_status"] == "active"
    assert history[1]["previous_status"] == "active"
    assert history[1]["new_status"] == "archived"


def test_project_lifecycle_api_requires_trusted_sqlite(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-14T12:00:00+00:00",
    )

    service = TrustedSQLiteStorageService(
        database_path
    )

    runtime = ExecutionEvidenceStorageRuntime(
        evidence_store=(
            service.build_repository_evidence_store()
        ),
        trusted_sqlite_service=service,
        roadmap_registry=None,
        roadmap_registry_status=(
            "unavailable_legacy_store"
        ),
        remediation="Migrate the legacy store.",
    )

    workspace_id = "local"

    _install_lifecycle_auth_for_scope(
        runtime,
        workspace_id=workspace_id,
        project_id="proj_any",
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                _lifecycle_status_path(
                    workspace_id,
                    "proj_any",
                ),
                headers={
                    "Authorization": "Bearer token",
                },
                json={
                    "status": "archived",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Trusted project lifecycle storage is "
        "unavailable. Migrate execution evidence "
        "storage to trusted SQLite first."
    )


def test_project_status_endpoint_requires_revision(
    tmp_path: Path,
):
    runtime = _trusted_lifecycle_runtime(
        tmp_path
    )
    stored = _create_lifecycle_project(runtime)

    workspace_id, _ = _install_lifecycle_auth(
        runtime,
        project_id=stored.project_id,
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                _lifecycle_status_path(
                    workspace_id,
                    stored.project_id,
                ),
                headers={
                    "Authorization": "Bearer token",
                },
                json={
                    "status": "archived",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422

    loaded = runtime.roadmap_registry.load(
        stored.project_direction_id
    )

    assert loaded is not None
    assert loaded.project_status == "active"
    assert loaded.project_revision == 0
    assert runtime.roadmap_registry.list_project_status_transitions(
        stored.project_id
    ) == []


def test_project_status_endpoint_rejects_stale_revision(
    tmp_path: Path,
):
    runtime = _trusted_lifecycle_runtime(
        tmp_path
    )
    stored = _create_lifecycle_project(runtime)

    workspace_id, _ = _install_lifecycle_auth(
        runtime,
        project_id=stored.project_id,
    )

    status_path = _lifecycle_status_path(
        workspace_id,
        stored.project_id,
    )
    history_path = _lifecycle_history_path(
        workspace_id,
        stored.project_id,
    )

    headers = {
        "Authorization": "Bearer token",
    }

    try:
        with TestClient(app) as client:
            first = client.post(
                status_path,
                headers=headers,
                json={
                    "status": "archived",
                    "expected_revision": 0,
                },
            )
            stale = client.post(
                status_path,
                headers=headers,
                json={
                    "status": "deleted",
                    "expected_revision": 0,
                },
            )
            history = client.get(
                history_path,
                headers=headers,
            )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert first.json()["revision"] == 1

    assert stale.status_code == 409
    assert stale.json() == {
        "detail": (
            "Project revision conflict: "
            "expected 0, found 1."
        )
    }

    assert history.status_code == 200
    transitions = history.json()
    assert len(transitions) == 1
    assert transitions[0]["new_status"] == "archived"


def test_project_lifecycle_requires_authentication(
    tmp_path: Path,
):
    runtime = _trusted_lifecycle_runtime(
        tmp_path
    )
    stored = _create_lifecycle_project(runtime)

    workspace_id = (
        runtime.roadmap_registry.workspace_id
    )

    access = _LifecycleProjectAccessService(
        AuthorizedProjectContext(
            principal_id=PRINCIPAL_ID,
            membership_id=MEMBERSHIP_ID,
            workspace_id=workspace_id,
            project_id=stored.project_id,
        )
    )

    authenticator = _LifecycleAuthenticator(
        error=RequestAuthenticationRequiredError(
            "missing"
        )
    )

    app.dependency_overrides[
        get_execution_evidence_storage_runtime
    ] = lambda: runtime
    app.dependency_overrides[
        get_request_authenticator
    ] = lambda: authenticator
    app.dependency_overrides[
        get_project_access_service
    ] = lambda: access

    try:
        with TestClient(app) as client:
            response = client.post(
                _lifecycle_status_path(
                    workspace_id,
                    stored.project_id,
                ),
                json={
                    "status": "archived",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.headers[
        "www-authenticate"
    ] == "Bearer"
    assert access.calls == []


def test_inaccessible_project_lifecycle_is_404(
    tmp_path: Path,
):
    runtime = _trusted_lifecycle_runtime(
        tmp_path
    )
    stored = _create_lifecycle_project(runtime)

    workspace_id = (
        runtime.roadmap_registry.workspace_id
    )

    context = AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        workspace_id=workspace_id,
        project_id=stored.project_id,
    )

    access = _LifecycleProjectAccessService(
        context,
        error=ProjectAccessNotFoundError(
            "Project does not exist."
        ),
    )

    app.dependency_overrides[
        get_execution_evidence_storage_runtime
    ] = lambda: runtime
    app.dependency_overrides[
        get_request_authenticator
    ] = lambda: _LifecycleAuthenticator()
    app.dependency_overrides[
        get_project_access_service
    ] = lambda: access

    try:
        with TestClient(app) as client:
            response = client.post(
                _lifecycle_status_path(
                    workspace_id,
                    stored.project_id,
                ),
                headers={
                    "Authorization": "Bearer token",
                },
                json={
                    "status": "archived",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Project does not exist."
    )


def test_lifecycle_uses_authorized_context_project_id(
    tmp_path: Path,
):
    runtime = _trusted_lifecycle_runtime(
        tmp_path
    )
    stored = _create_lifecycle_project(runtime)

    workspace_id = (
        runtime.roadmap_registry.workspace_id
    )

    context = AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        workspace_id=workspace_id,
        project_id=stored.project_id,
    )

    access = _LifecycleProjectAccessService(
        context
    )

    app.dependency_overrides[
        get_execution_evidence_storage_runtime
    ] = lambda: runtime
    app.dependency_overrides[
        get_request_authenticator
    ] = lambda: _LifecycleAuthenticator()
    app.dependency_overrides[
        get_project_access_service
    ] = lambda: access

    path_project_id = "proj_untrusted_path_value"

    try:
        with TestClient(app) as client:
            response = client.post(
                _lifecycle_status_path(
                    workspace_id,
                    path_project_id,
                ),
                headers={
                    "Authorization": "Bearer token",
                },
                json={
                    "status": "archived",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["project_id"] == (
        stored.project_id
    )

    assert len(access.calls) == 1
    assert access.calls[0][1:] == (
        workspace_id,
        path_project_id,
    )

    loaded = runtime.roadmap_registry.load(
        stored.project_direction_id
    )

    assert loaded is not None
    assert loaded.project_status == "archived"


def test_old_project_lifecycle_routes_are_unregistered(
    tmp_path: Path,
):
    runtime = _trusted_lifecycle_runtime(
        tmp_path
    )
    stored = _create_lifecycle_project(runtime)

    workspace_id, _ = _install_lifecycle_auth(
        runtime,
        project_id=stored.project_id,
    )

    assert workspace_id

    try:
        with TestClient(app) as client:
            mutation = client.post(
                f"/v1/projects/"
                f"{stored.project_id}/status",
                headers={
                    "Authorization": "Bearer token",
                },
                json={
                    "status": "archived",
                    "expected_revision": 0,
                },
            )
            history = client.get(
                f"/v1/projects/"
                f"{stored.project_id}/"
                "status-transitions",
                headers={
                    "Authorization": "Bearer token",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert mutation.status_code == 404
    assert history.status_code == 404
