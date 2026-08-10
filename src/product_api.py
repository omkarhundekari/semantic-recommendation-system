from dataclasses import asdict
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
)
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from pydantic import ConfigDict, ValidationError, field_validator, model_validator
from fastapi.middleware.cors import CORSMiddleware

from feasibility_scorer import score_project_feasibility
from plan_repair import repair_project_plan
from plan_verifier import verify_project_ideas
from decision_trace_debug import write_decision_trace_artifact
from portfolio_ladder import apply_portfolio_ladder
from project_decision_trace import build_project_decision_trace
from project_idea_generator import generate_project_ideas
from query_expander import get_query_metadata
from query_understanding import understand_query
from research_evidence_assessment import build_evidence_assessment
from research_query_anchors import extract_required_anchor_terms
from product_plan_readiness import assess_product_plan_readiness
from planning.evidence_brief import build_evidence_brief
from planning.evidence_coverage_classifier import (
    classify_evidence_coverage,
)
from planning.live_evidence_cards import build_live_evidence_cards_from_brief
from planning.mission_context import build_mission_context
from planning.product_synthesis_status import (
    build_project_intelligence_synthesis_status,
)
from planning.coverage_aware_direction_notes import (
    apply_coverage_notes_to_ideas,
)
from planning.product_enrichment import enrich_product_ideas
from planning.query_anchor_direction_adapter import (
    adapt_ideas_to_query_anchors,
)
from planning.roadmap_execution_enrichment import (
    enrich_roadmap_for_execution,
)
from planning.roadmap_registry import (
    SQLiteRoadmapSnapshotRegistry,
    ProjectNotFoundError,
    ProjectRevisionConflictError,
    ProjectStatus,
    ProjectStatusMutationResult,
    ProjectStatusTransition,
    ProjectStatusTransitionError,
    RoadmapRegistryError,
    RoadmapSnapshotRegistry,
    create_stored_roadmap_snapshot,
)
from planning.roadmap_snapshot import (
    build_roadmap_snapshot,
)
from planning.llm_synthesis_demo import (
    build_default_output_path,
    build_default_validation_report_path,
    run_llm_synthesis_demo,
)
from schemas.product_models import (
    EvidenceReference,
    PipelineStep,
    ProjectDirection,
    ProjectIntelligencePersistence,
    ProjectIntelligenceRequest,
    ProjectIntelligenceResponse,
    RoadmapRegistryPersistenceStatus,
    RoadmapStage,
    VerificationResult,
    SynthesisDemoRequest,
)
from source_router import retrieve_evidence

from execution_evidence.workspace_discovery import (
    DiscoveredWorkspace,
    SQLiteWorkspaceDiscoveryService,
    WorkspaceDiscoveryStoreError,
)
from execution_evidence.workspace_provisioning import (
    SQLiteWorkspaceProvisioningService,
    WorkspaceProvisioningIdempotencyConflictError,
    WorkspaceProvisioningIdentityCollisionError,
    WorkspaceProvisioningPrincipalUnavailableError,
    WorkspaceProvisioningResult,
    WorkspaceProvisioningStateError,
    WorkspaceProvisioningUnavailableError,
)
from execution_evidence.api_models import (
    EvidenceAttributionAttachRequest,
    EvidenceAttributionDetachRequest,
    EvidenceAttributionDetachResponse,
    EvidenceAttributionListQuery,
    ExecutionEventLineageConflictResponse,
    ExecutionEventLineageResponse,
    ExecutionEventRecordResponse,
    RepositoryEvidenceSyncRequest,
)
from execution_evidence.execution_event import (
    ExecutionEventAppendResult,
)
from execution_evidence.execution_event_store import (
    ExecutionEventIdempotencyConflictError,
    ExecutionEventProjectHistoryTooLargeError,
    ExecutionEventProjectNotFoundError,
    ExecutionEventStore,
    ExecutionEventStoreError,
)
from execution_evidence.execution_event_projection import (
    ExecutionEventProjectionError,
)
from execution_evidence.execution_event_projection_service import (
    ExecutionEventProjectionService,
    ExecutionEventProjectionUnsupportedStoreError,
)
from execution_evidence.github_webhook_adapter import (
    GitHubWebhookPayloadError,
)
from execution_evidence.github_source_routing_service import (
    GitHubSourceRoutingService,
)
from execution_evidence.sqlite_github_source_binding_store import (
    SQLiteGitHubSourceBindingStore,
)
from execution_evidence.github_webhook_authentication_service import (
    GitHubWebhookAuthenticationService,
    GitHubWebhookAuthenticationStoreError,
    GitHubWebhookCredentialAuthorityNotFoundError,
    GitHubWebhookEndpointNotFoundError,
    GitHubWebhookRepositoryIdentityError,
    GitHubWebhookSecretResolutionError,
)
from execution_evidence.github_webhook_ingestion import (
    GitHubWebhookIngestionService,
    GitHubWebhookMalformedJSONError,
    GitHubWebhookPayloadShapeError,
    GitHubWebhookRoutingNotFoundError,
    GitHubWebhookRoutingStoreError,
)
from execution_evidence.github_webhook_signature import (
    GitHubWebhookSignatureError,
)
from execution_evidence.sqlite_github_webhook_credential_store import (
    SQLiteGitHubWebhookCredentialStore,
)
from execution_evidence.sqlite_github_webhook_credential_authority_store import (
    SQLiteGitHubWebhookCredentialAuthorityStore,
)
from execution_evidence.environment_github_webhook_secret_resolver import (
    EnvironmentGitHubWebhookSecretResolver,
)
from execution_evidence.coordinator import (
    StatefulGitHubSyncCoordinator,
    StatefulGitHubSyncResult,
)
from execution_evidence.attribution import (
    AttributionMutationResult,
    EvidenceAttributionService,
    ExecutionEvidenceNotFoundError,
    RepositoryEvidenceNotFoundError,
)
from execution_evidence.github_client import (
    GitHubExecutionEvidenceClient,
)
from execution_evidence.models import (
    EvidenceAttribution,
    RoadmapAttributionContext,
)
from execution_evidence.service import (
    GitHubExecutionEvidenceService,
)
from execution_evidence.json_store import (
    JsonRepositoryEvidenceStore,
)
from execution_evidence.sqlite_store import (
    SQLiteRepositoryEvidenceStore,
)
from execution_evidence.storage_readiness import (
    ExecutionEvidenceStorageReadiness,
    assess_execution_evidence_storage_readiness,
    assess_sqlite_database_readiness,
)
from execution_evidence.storage_service import (
    ExecutionEvidenceStorageRuntime,
    TrustedSQLiteStorageService,
    TrustedSQLiteStorageServiceError,
)
from execution_evidence.store import (
    RepositoryEvidenceConflictError,
    RepositoryEvidenceStore,
    StoredRepositoryEvidence,
)
from execution_evidence.trusted_store import (
    TrustedStoreInitializationError,
    initialize_fresh_trusted_store,
)
from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.authorized_project_context import (
    AuthorizedProjectContext,
)
from execution_evidence.authorized_workspace_context import (
    AuthorizedWorkspaceContext,
)
from execution_evidence.sqlite_workspace_membership_store import (
    SQLiteWorkspaceMembershipStore,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembership,
    WorkspaceMembershipMutationResult,
    WorkspaceMembershipRole,
    WorkspaceMembershipRoleMutationResult,
    WorkspaceMembershipRoleTransition,
    WorkspaceMembershipStatus,
    WorkspaceMembershipTransition,
)
from execution_evidence.workspace_membership_store import (
    WorkspaceMembershipInactiveError,
    WorkspaceMembershipLastManagerError,
    WorkspaceMembershipNotFoundError,
    WorkspaceMembershipRevisionConflictError,
    WorkspaceMembershipRoleAuthorizationError,
    WorkspaceMembershipStoreError,
    WorkspaceMembershipTransitionError,
)
from execution_evidence.workspace_capability import (
    WorkspaceCapability,
    WorkspaceCapabilityDeniedError,
    require_workspace_capability,
)
from execution_evidence.project_capability import (
    ProjectCapability,
    ProjectCapabilityDeniedError,
    require_capability,
)
from execution_evidence.request_authenticator import (
    RequestAuthenticationFailedError,
    RequestAuthenticationRequiredError,
    RequestAuthenticationUnavailableError,
    RequestAuthenticator,
)
from execution_evidence.project_access_service import (
    ProjectAccessNotFoundError,
    ProjectAccessService,
    ProjectAccessStoreError,
)
from execution_evidence.workspace_access_service import (
    WorkspaceAccessNotFoundError,
    WorkspaceAccessService,
    WorkspaceAccessStoreError,
)
from execution_evidence.sqlite_workspace_access_service import (
    SQLiteWorkspaceAccessService,
)
from execution_evidence.sqlite_project_access_service import (
    SQLiteProjectAccessService,
)
from execution_evidence.authentication_runtime import (
    AuthenticationRuntime,
    build_authentication_runtime,
)
from execution_evidence.environment_oidc_provider_config_source import (
    EnvironmentOIDCProviderConfigSource,
)


logger = logging.getLogger(__name__)


app = FastAPI(
    title="Solvyn API",
    description=(
        "Evidence-grounded project planning API that converts user goals into "
        "evidence-aware project directions and structured execution roadmaps."
    ),
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


MAX_GITHUB_WEBHOOK_BODY_BYTES = 25 * 1024 * 1024


EXECUTION_EVIDENCE_STORE_BACKEND_ENV = (
    "SOLVYN_EXECUTION_EVIDENCE_STORE_BACKEND"
)

EXECUTION_EVIDENCE_STORE_PATH_ENV = (
    "SOLVYN_EXECUTION_EVIDENCE_STORE_PATH"
)

DEFAULT_EXECUTION_EVIDENCE_STORE_BACKEND = "auto"

DEFAULT_EXECUTION_EVIDENCE_STORE_PATH = Path(
    "data/execution_evidence/repositories.json"
)

DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH = Path(
    "data/execution_evidence/solvyn.db"
)

SUPPORTED_EXECUTION_EVIDENCE_STORE_BACKENDS = {
    "auto",
    "json",
    "sqlite",
}


def build_execution_evidence_storage_runtime(
    path: Optional[str] = None,
    *,
    backend: Optional[str] = None,
) -> ExecutionEvidenceStorageRuntime:
    configured_backend = (
        backend
        or os.getenv(
            EXECUTION_EVIDENCE_STORE_BACKEND_ENV
        )
        or DEFAULT_EXECUTION_EVIDENCE_STORE_BACKEND
    )
    resolved_backend = (
        configured_backend.strip().lower()
    )

    if (
        resolved_backend
        not in SUPPORTED_EXECUTION_EVIDENCE_STORE_BACKENDS
    ):
        supported = ", ".join(
            sorted(
                SUPPORTED_EXECUTION_EVIDENCE_STORE_BACKENDS
            )
        )
        raise ValueError(
            "Unsupported execution evidence store "
            f"backend: {configured_backend}. "
            f"Supported backends: {supported}."
        )

    configured_path = (
        path
        or os.getenv(
            EXECUTION_EVIDENCE_STORE_PATH_ENV
        )
    )

    if resolved_backend == "auto":
        if configured_path:
            resolved_path = Path(configured_path)
            suffix = resolved_path.suffix.lower()

            if suffix == ".json":
                resolved_backend = "json"
            elif suffix == ".db":
                resolved_backend = "sqlite"
            else:
                raise ValueError(
                    "Automatic execution evidence storage "
                    "requires a .json or .db path."
                )
        elif (
            DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH
            .exists()
        ):
            resolved_backend = "sqlite"
            resolved_path = (
                DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH
            )
        elif (
            DEFAULT_EXECUTION_EVIDENCE_STORE_PATH
            .exists()
        ):
            resolved_backend = "json"
            resolved_path = (
                DEFAULT_EXECUTION_EVIDENCE_STORE_PATH
            )
        else:
            resolved_backend = "sqlite"
            resolved_path = (
                DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH
            )

            try:
                initialize_fresh_trusted_store(
                    resolved_path
                )
            except TrustedStoreInitializationError as error:
                raise ValueError(
                    "Could not initialize fresh trusted "
                    "SQLite execution evidence storage: "
                    f"{resolved_path}."
                ) from error
    elif configured_path:
        resolved_path = Path(configured_path)
    elif resolved_backend == "sqlite":
        resolved_path = (
            DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH
        )
    else:
        resolved_path = (
            DEFAULT_EXECUTION_EVIDENCE_STORE_PATH
        )

    if resolved_backend == "json":
        if resolved_path.suffix.lower() != ".json":
            raise ValueError(
                "JSON execution evidence storage "
                "requires a .json path."
            )

        evidence_store = (
            JsonRepositoryEvidenceStore(
                resolved_path
            )
        )

        return ExecutionEvidenceStorageRuntime(
            evidence_store=evidence_store,
            trusted_sqlite_service=None,
            roadmap_registry=None,
            roadmap_registry_status=(
                "unavailable_legacy_store"
            ),
            remediation=(
                "Migrate the legacy JSON execution "
                "evidence store to trusted SQLite "
                "storage before using roadmap "
                "attribution features."
            ),
        )

    if resolved_path.suffix.lower() != ".db":
        raise ValueError(
            "SQLite execution evidence storage "
            "requires a .db path."
        )

    if not resolved_path.is_file():
        raise ValueError(
            "SQLite execution evidence storage "
            "requires an existing promoted database: "
            f"{resolved_path}."
        )

    readiness = assess_sqlite_database_readiness(
        resolved_path
    )

    trusted_storage_usable = (
        readiness.status == "ready"
        or (
            readiness.status == "degraded"
            and readiness.checks.get(
                "trusted_receipt_compatible",
                False,
            )
        )
    )

    if not trusted_storage_usable:
        details = "; ".join(readiness.errors)
        raise ValueError(
            "SQLite execution evidence storage "
            "failed readiness validation"
            + (
                f": {details}"
                if details
                else "."
            )
        )

    try:
        storage_service = (
            TrustedSQLiteStorageService(
                resolved_path
            )
        )
        evidence_store = (
            storage_service
            .build_repository_evidence_store()
        )
        roadmap_registry = (
            storage_service
            .build_roadmap_snapshot_registry()
        )
    except TrustedSQLiteStorageServiceError as error:
        raise ValueError(
            "SQLite execution evidence storage "
            "could not initialize its trusted "
            "runtime service."
        ) from error

    return ExecutionEvidenceStorageRuntime(
        evidence_store=evidence_store,
        trusted_sqlite_service=storage_service,
        roadmap_registry=roadmap_registry,
        roadmap_registry_status="ready",
        remediation=None,
    )


def build_execution_evidence_store(
    path: Optional[str] = None,
    *,
    backend: Optional[str] = None,
) -> RepositoryEvidenceStore:
    return build_execution_evidence_storage_runtime(
        path,
        backend=backend,
    ).evidence_store


_execution_evidence_storage_runtime = (
    build_execution_evidence_storage_runtime()
)


_authentication_runtime = build_authentication_runtime(
    config_source=EnvironmentOIDCProviderConfigSource(),
    trusted_sqlite_service=(
        _execution_evidence_storage_runtime
        .trusted_sqlite_service
    ),
)


def get_execution_evidence_storage_runtime(
) -> ExecutionEvidenceStorageRuntime:
    return _execution_evidence_storage_runtime


def get_execution_evidence_store(
) -> RepositoryEvidenceStore:
    return (
        get_execution_evidence_storage_runtime()
        .evidence_store
    )


def get_execution_event_store(
    runtime: ExecutionEvidenceStorageRuntime = Depends(
        get_execution_evidence_storage_runtime
    ),
) -> ExecutionEventStore:
    if runtime.trusted_sqlite_service is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Durable execution event storage is "
                "unavailable. Migrate execution evidence "
                "storage to trusted SQLite."
            ),
        )

    return (
        runtime.trusted_sqlite_service
        .build_execution_event_store()
    )




def get_execution_event_projection_service(
    event_store: ExecutionEventStore = Depends(
        get_execution_event_store
    ),
) -> ExecutionEventProjectionService:
    return ExecutionEventProjectionService(
        store=event_store
    )


def get_authentication_runtime(
) -> AuthenticationRuntime:
    return _authentication_runtime


def get_request_authenticator(
    runtime: AuthenticationRuntime = Depends(
        get_authentication_runtime
    ),
) -> RequestAuthenticator:
    if not runtime.ready:
        raise HTTPException(
            status_code=503,
            detail=(
                "Request authentication runtime is "
                "temporarily unavailable."
            ),
        )

    authenticator = runtime.authenticator

    if authenticator is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Request authentication runtime is "
                "temporarily unavailable."
            ),
        )

    return authenticator


@app.get(
    "/v1/authentication/readiness"
)
def get_authentication_readiness(
    runtime: AuthenticationRuntime = Depends(
        get_authentication_runtime
    ),
):
    # This endpoint is intentionally public so operators
    # can distinguish authentication-runtime health even
    # when interactive authentication itself is unavailable.
    # Internal provider IDs and diagnostic details remain
    # available through runtime logging, not this response.
    return {
        "status": runtime.status,
    }


def get_authenticated_request_principal(
    authorization: Optional[str] = Header(
        default=None,
        alias="Authorization",
    ),
    authenticator: RequestAuthenticator = Depends(
        get_request_authenticator
    ),
) -> AuthenticatedRequestPrincipal:
    try:
        return authenticator.authenticate(
            authorization
        )
    except RequestAuthenticationRequiredError as error:
        raise HTTPException(
            status_code=401,
            detail="Authentication is required.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from error
    except RequestAuthenticationFailedError as error:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from error
    except RequestAuthenticationUnavailableError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Request authentication is temporarily "
                "unavailable."
            ),
        ) from error



# === workspace provisioning API ===
class WorkspaceProvisioningRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    reason: Optional[str] = None


def get_workspace_provisioning_service(
    runtime: ExecutionEvidenceStorageRuntime = Depends(
        get_execution_evidence_storage_runtime
    ),
) -> SQLiteWorkspaceProvisioningService:
    trusted_service = runtime.trusted_sqlite_service

    if trusted_service is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Workspace provisioning storage is "
                "temporarily unavailable."
            ),
        )

    return SQLiteWorkspaceProvisioningService(
        trusted_service.path
    )


@app.post(
    "/v1/workspaces",
    response_model=WorkspaceProvisioningResult,
    status_code=201,
)
def provision_workspace_endpoint(
    request: WorkspaceProvisioningRequest,
    response: Response,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
    ),
    principal: AuthenticatedRequestPrincipal = Depends(
        get_authenticated_request_principal
    ),
    provisioning_service: (
        SQLiteWorkspaceProvisioningService
    ) = Depends(
        get_workspace_provisioning_service
    ),
) -> WorkspaceProvisioningResult:
    """Create one self-service provisioned workspace.

    The target workspace does not exist yet, so this route
    is authorized by the authenticated request principal
    rather than by workspace authorization.
    """

    try:
        provisioning = (
            provisioning_service.provision_idempotent(
                principal_id=principal.principal_id,
                idempotency_key=idempotency_key,
                created_at=datetime.now(timezone.utc),
                reason=request.reason,
            )
        )
    except (
        WorkspaceProvisioningPrincipalUnavailableError
    ) as error:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from error
    except (
        WorkspaceProvisioningIdempotencyConflictError
    ) as error:
        raise HTTPException(
            status_code=409,
            detail=(
                "Idempotency-Key was reused with "
                "different workspace provisioning "
                "request content."
            ),
        ) from error
    except WorkspaceProvisioningUnavailableError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Workspace provisioning storage is "
                "temporarily unavailable."
            ),
        ) from error
    except (
        WorkspaceProvisioningIdentityCollisionError,
        WorkspaceProvisioningStateError,
    ) as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Workspace provisioning is temporarily "
                "unavailable."
            ),
        ) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    response.status_code = (
        200
        if provisioning.replayed
        else 201
    )

    response.headers[
        "Idempotency-Replayed"
    ] = (
        "true"
        if provisioning.replayed
        else "false"
    )

    return provisioning.result

# === workspace discovery API ===
def get_workspace_discovery_service(
    runtime: ExecutionEvidenceStorageRuntime = Depends(
        get_execution_evidence_storage_runtime
    ),
) -> SQLiteWorkspaceDiscoveryService:
    trusted_service = runtime.trusted_sqlite_service

    if trusted_service is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Workspace discovery storage is "
                "temporarily unavailable."
            ),
        )

    return SQLiteWorkspaceDiscoveryService(
        trusted_service.path
    )


@app.get(
    "/v1/workspaces",
    response_model=List[DiscoveredWorkspace],
)
def list_accessible_workspaces_endpoint(
    principal: AuthenticatedRequestPrincipal = Depends(
        get_authenticated_request_principal
    ),
    discovery_service: (
        SQLiteWorkspaceDiscoveryService
    ) = Depends(
        get_workspace_discovery_service
    ),
) -> List[DiscoveredWorkspace]:
    """List workspaces currently accessible to the caller.

    Workspace identities are derived from durable active
    memberships for the authenticated request principal.
    No caller-supplied workspace scope is trusted.
    """

    try:
        return discovery_service.list_accessible(
            principal=principal
        )
    except WorkspaceDiscoveryStoreError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Workspace discovery is temporarily "
                "unavailable."
            ),
        ) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


def get_workspace_access_service(
    runtime: ExecutionEvidenceStorageRuntime = Depends(
        get_execution_evidence_storage_runtime
    ),
) -> WorkspaceAccessService:
    if runtime.trusted_sqlite_service is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Workspace authorization storage is "
                "temporarily unavailable."
            ),
        )

    return SQLiteWorkspaceAccessService(
        runtime.trusted_sqlite_service.path
    )


def get_authorized_workspace_context(
    workspace_id: str,
    principal: AuthenticatedRequestPrincipal = Depends(
        get_authenticated_request_principal
    ),
    access_service: WorkspaceAccessService = Depends(
        get_workspace_access_service
    ),
) -> AuthorizedWorkspaceContext:
    try:
        return access_service.authorize(
            principal=principal,
            workspace_id=workspace_id,
        )
    except WorkspaceAccessNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Workspace does not exist.",
        ) from error
    except WorkspaceAccessStoreError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Workspace authorization storage is "
                "temporarily unavailable."
            ),
        ) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


def get_authorized_workspace_membership_store(
    context: AuthorizedWorkspaceContext = Depends(
        get_authorized_workspace_context
    ),
    runtime: ExecutionEvidenceStorageRuntime = Depends(
        get_execution_evidence_storage_runtime
    ),
) -> SQLiteWorkspaceMembershipStore:
    """Bind membership storage to authorized workspace scope."""

    if not isinstance(
        context,
        AuthorizedWorkspaceContext,
    ):
        raise TypeError(
            "Authorized workspace context is required."
        )

    if not isinstance(
        runtime,
        ExecutionEvidenceStorageRuntime,
    ):
        raise TypeError(
            "Execution evidence storage runtime is required."
        )

    trusted_service = runtime.trusted_sqlite_service

    if not isinstance(
        trusted_service,
        TrustedSQLiteStorageService,
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "Trusted workspace membership storage is "
                "temporarily unavailable."
            ),
        )

    return SQLiteWorkspaceMembershipStore(
        trusted_service.path,
        workspace_id=context.workspace_id,
    )


def get_project_access_service(
    runtime: ExecutionEvidenceStorageRuntime = Depends(
        get_execution_evidence_storage_runtime
    ),
) -> ProjectAccessService:
    if runtime.trusted_sqlite_service is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Project authorization storage is "
                "temporarily unavailable."
            ),
        )

    return SQLiteProjectAccessService(
        runtime.trusted_sqlite_service.path
    )


def get_authorized_project_context(
    workspace_id: str,
    project_id: str,
    principal: AuthenticatedRequestPrincipal = Depends(
        get_authenticated_request_principal
    ),
    access_service: ProjectAccessService = Depends(
        get_project_access_service
    ),
) -> AuthorizedProjectContext:
    try:
        return access_service.authorize(
            principal=principal,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    except ProjectAccessNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Project does not exist.",
        ) from error
    except ProjectAccessStoreError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Project authorization storage is "
                "temporarily unavailable."
            ),
        ) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


def get_authorized_execution_event_projection_service(
    context: AuthorizedProjectContext = Depends(
        get_authorized_project_context
    ),
    runtime: ExecutionEvidenceStorageRuntime = Depends(
        get_execution_evidence_storage_runtime
    ),
) -> ExecutionEventProjectionService:
    if runtime.trusted_sqlite_service is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Durable execution event storage is "
                "temporarily unavailable."
            ),
        )

    event_store = (
        runtime.trusted_sqlite_service
        .build_execution_event_store_for_authorized_project(
            context
        )
    )

    return ExecutionEventProjectionService(
        store=event_store
    )


def get_github_webhook_authentication_service(
    runtime: ExecutionEvidenceStorageRuntime = Depends(
        get_execution_evidence_storage_runtime
    ),
) -> GitHubWebhookAuthenticationService:
    if runtime.trusted_sqlite_service is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Durable execution event storage is "
                "unavailable. Migrate execution evidence "
                "storage to trusted SQLite."
            ),
        )

    trusted_service = runtime.trusted_sqlite_service

    return GitHubWebhookAuthenticationService(
        credential_store=(
            SQLiteGitHubWebhookCredentialStore(
                trusted_service.path
            )
        ),
        authority_store=(
            SQLiteGitHubWebhookCredentialAuthorityStore(
                trusted_service.path
            )
        ),
        secret_resolver=(
            EnvironmentGitHubWebhookSecretResolver()
        ),
    )


def get_github_webhook_ingestion_service(
    runtime: ExecutionEvidenceStorageRuntime = Depends(
        get_execution_evidence_storage_runtime
    ),
) -> GitHubWebhookIngestionService:
    if runtime.trusted_sqlite_service is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Durable execution event storage is "
                "unavailable. Migrate execution evidence "
                "storage to trusted SQLite."
            ),
        )

    trusted_service = runtime.trusted_sqlite_service

    routing_service = GitHubSourceRoutingService(
        binding_store=SQLiteGitHubSourceBindingStore(
            trusted_service.path
        )
    )

    return GitHubWebhookIngestionService(
        routing_service=routing_service,
        event_store_factory=(
            trusted_service
            .build_execution_event_store_for_workspace
        ),
    )


def get_authorized_roadmap_registry(
    context: AuthorizedProjectContext = Depends(
        get_authorized_project_context
    ),
    runtime: ExecutionEvidenceStorageRuntime = Depends(
        get_execution_evidence_storage_runtime
    ),
) -> SQLiteRoadmapSnapshotRegistry:
    """Bind lifecycle storage to the authorized workspace."""

    if not isinstance(
        context,
        AuthorizedProjectContext,
    ):
        raise TypeError(
            "Authorized project context is required."
        )

    if not isinstance(
        runtime,
        ExecutionEvidenceStorageRuntime,
    ):
        raise TypeError(
            "Execution evidence storage runtime is required."
        )

    base_registry = runtime.roadmap_registry

    if not isinstance(
        base_registry,
        SQLiteRoadmapSnapshotRegistry,
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "Trusted project lifecycle storage is "
                "unavailable. Migrate execution evidence "
                "storage to trusted SQLite first."
            ),
        )

    return SQLiteRoadmapSnapshotRegistry(
        base_registry.path,
        workspace_id=context.workspace_id,
        initialize_schema=False,
        ensure_workspace=False,
    )


def get_roadmap_snapshot_registry(
    runtime: ExecutionEvidenceStorageRuntime = Depends(
        get_execution_evidence_storage_runtime
    ),
) -> Optional[RoadmapSnapshotRegistry]:
    """Return the runtime's workspace-defaulted roadmap registry.

    This dependency is not authorization-context-bound and must
    not be used by routes that already hold an
    AuthorizedProjectContext. Such routes must construct their
    registry from the authorized workspace instead.
    """
    if not isinstance(
        runtime,
        ExecutionEvidenceStorageRuntime,
    ):
        runtime = (
            get_execution_evidence_storage_runtime()
        )

    return runtime.roadmap_registry


def get_execution_evidence_coordinator(
) -> StatefulGitHubSyncCoordinator:
    client = GitHubExecutionEvidenceClient(
        token=os.getenv("GITHUB_TOKEN"),
    )
    service = GitHubExecutionEvidenceService(
        client=client,
    )

    return StatefulGitHubSyncCoordinator(
        service=service,
        store=get_execution_evidence_store(),
    )


def get_execution_evidence_attribution_service(
) -> EvidenceAttributionService:
    return EvidenceAttributionService(
        store=get_execution_evidence_store(),
    )


def get_authorized_execution_evidence_attribution_service(
    context: AuthorizedProjectContext = Depends(
        get_authorized_project_context
    ),
    runtime: ExecutionEvidenceStorageRuntime = Depends(
        get_execution_evidence_storage_runtime
    ),
) -> EvidenceAttributionService:
    """Bind attribution storage to the authorized workspace."""
    if not isinstance(
        context,
        AuthorizedProjectContext,
    ):
        raise TypeError(
            "Authorized project context is required."
        )

    if not isinstance(
        runtime,
        ExecutionEvidenceStorageRuntime,
    ):
        raise TypeError(
            "Execution evidence storage runtime is required."
        )

    trusted_service = runtime.trusted_sqlite_service

    if not isinstance(
        trusted_service,
        TrustedSQLiteStorageService,
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "Trusted execution evidence attribution "
                "storage is unavailable. Migrate execution "
                "evidence storage to trusted SQLite first."
            ),
        )

    store = (
        trusted_service
        .build_repository_evidence_store_for_authorized_project(
            context
        )
    )

    return EvidenceAttributionService(
        store=store,
    )



class ProjectScopedAttributionIdentityRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    project_direction_id: Optional[str] = None
    roadmap_snapshot_id: Optional[str] = None

    @field_validator(
        "project_direction_id",
        "roadmap_snapshot_id",
        mode="before",
    )
    @classmethod
    def normalize_optional_identity(
        cls,
        value,
    ):
        if value is None:
            return None

        if not isinstance(value, str):
            return value

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Attribution identity values must not "
                "be blank."
            )

        return normalized

    @model_validator(mode="after")
    def require_roadmap_identity(
        self,
    ):
        if (
            self.project_direction_id is None
            and self.roadmap_snapshot_id is None
        ):
            raise ValueError(
                "Either project_direction_id or "
                "roadmap_snapshot_id is required."
            )

        return self


class ProjectScopedEvidenceAttributionAttachRequest(
    ProjectScopedAttributionIdentityRequest
):
    repository_key: str
    evidence_key: str
    roadmap_node_id: str
    rationale: str = ""
    expected_revision: Optional[int] = Field(
        default=None,
        ge=0,
    )

    @field_validator(
        "repository_key",
        "evidence_key",
        "roadmap_node_id",
        mode="before",
    )
    @classmethod
    def normalize_required_identity(
        cls,
        value,
    ):
        if not isinstance(value, str):
            return value

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Attribution identity values must not "
                "be blank."
            )

        return normalized

    @field_validator(
        "rationale",
        mode="before",
    )
    @classmethod
    def normalize_rationale(
        cls,
        value,
    ):
        if not isinstance(value, str):
            return value

        return value.strip()


class ProjectScopedEvidenceAttributionDetachRequest(
    ProjectScopedAttributionIdentityRequest
):
    repository_key: str
    evidence_key: str
    roadmap_node_id: str
    expected_revision: Optional[int] = Field(
        default=None,
        ge=0,
    )

    @field_validator(
        "repository_key",
        "evidence_key",
        "roadmap_node_id",
        mode="before",
    )
    @classmethod
    def normalize_required_identity(
        cls,
        value,
    ):
        if not isinstance(value, str):
            return value

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Attribution identity values must not "
                "be blank."
            )

        return normalized


class ProjectScopedEvidenceAttributionListQuery(
    ProjectScopedAttributionIdentityRequest
):
    repository_key: str
    roadmap_node_id: Optional[str] = None

    @field_validator(
        "repository_key",
        mode="before",
    )
    @classmethod
    def normalize_repository_key(
        cls,
        value,
    ):
        if not isinstance(value, str):
            return value

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Repository key must not be blank."
            )

        return normalized

    @field_validator(
        "roadmap_node_id",
        mode="before",
    )
    @classmethod
    def normalize_optional_node_id(
        cls,
        value,
    ):
        if value is None:
            return None

        if not isinstance(value, str):
            return value

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Roadmap node ID must not be blank."
            )

        return normalized



class ProjectStatusTransitionRequest(BaseModel):
    status: ProjectStatus
    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )
    expected_revision: int = Field(
        ge=0,
    )


BROAD_PLANNING_DOMAINS = {
    "ai_ml",
    "software_engineering",
    "general",
}


SUPPORTED_PLANNING_DOMAINS = {
    "ai_ml",
    "backend",
    "blockchain",
    "cloud",
    "computer_vision",
    "cybersecurity",
    "data_engineering",
    "databases",
    "developer_tools",
    "devops",
    "education_tech",
    "fintech",
    "frontend",
    "full_stack",
    "healthcare_ai",
    "mlops",
    "mobile",
    "nlp",
    "rag_llm",
    "recommendation_systems",
}




def build_research_evidence_assessment(
    evidence_payload: Dict,
    query: str,
):
    research_results = evidence_payload.get("research_results", [])

    if not research_results:
        return None

    required_anchor_terms = extract_required_anchor_terms(query)

    return build_evidence_assessment(
        research_results,
        query=query,
        required_anchor_terms=required_anchor_terms,
    )


def resolve_planning_domain(
    *,
    explicit_domain: Optional[str],
    inferred_focus: Optional[str],
) -> Optional[str]:
    explicit = (explicit_domain or "").strip()
    inferred = (inferred_focus or "").strip()

    if explicit and explicit != "general":
        return explicit

    if inferred and inferred != "general":
        return inferred

    return explicit or inferred or None



def resolve_response_planning_domain(
    *,
    planning_domain: Optional[str],
    generated_domain: Optional[str],
) -> Optional[str]:
    planned = (planning_domain or "").strip()
    generated = (generated_domain or "").strip()

    if (
        planned in BROAD_PLANNING_DOMAINS
        and generated
        and generated not in BROAD_PLANNING_DOMAINS
    ):
        return generated

    return planned or generated or None


def build_roadmap(idea: Dict) -> List[RoadmapStage]:
    mvp_steps = idea.get("mvp_scope", [])
    advanced_extensions = idea.get("advanced_extensions", [])
    detected_domain = idea.get("detected_domain", "")

    if detected_domain == "rag_llm":
        define_stage = RoadmapStage(
            id="define",
            title="Define the RAG evaluation question",
            purpose=(
                "Choose a narrow RAG workflow, a constrained document set, "
                "and measurable evaluation targets."
            ),
            tasks=[
                idea.get("evidence_buildable_gap")
                or (
                    "Choose one RAG failure mode to inspect, such as "
                    "retrieval quality, answer faithfulness, or citation coverage."
                ),
                (
                    "Select a small document collection, a fixed question set, "
                    "and evaluation metrics for retrieval and answer quality."
                ),
            ],
        )
    else:
        define_stage = RoadmapStage(
            id="define",
            title="Define the problem",
            purpose="Turn the recommendation into a narrow, measurable problem.",
            tasks=[
                idea.get("evidence_buildable_gap")
                or (
                    "Write a one-sentence problem statement and define "
                    "one success metric."
                ),
                "Choose a constrained input source and a realistic first user.",
            ],
        )

    return [
        define_stage,
        RoadmapStage(
            id="mvp",
            title="Build the MVP",
            purpose="Implement the smallest complete version of the idea.",
            tasks=mvp_steps[:10],
        ),
        RoadmapStage(
            id="validate",
            title="Validate the result",
            purpose="Demonstrate that the prototype works and document limitations.",
            tasks=[
                "Create representative test inputs and expected outputs.",
                "Measure one quality, accuracy, reliability, or user-value metric.",
                "Document known limitations and failure cases.",
            ],
        ),
        RoadmapStage(
            id="extend",
            title="Add one advanced extension",
            purpose="Increase technical depth only after the MVP is stable.",
            tasks=advanced_extensions[:3],
        ),
        RoadmapStage(
            id="package",
            title="Package for portfolio",
            purpose=(
                "Make the project easy for recruiters and interviewers "
                "to understand."
            ),
            tasks=[
                "Add an architecture diagram and setup instructions to the README.",
                "Record a short demo and include realistic screenshots or GIFs.",
                (
                    "Write one resume bullet explaining the technical impact "
                    "and system design."
                ),
            ],
        ),
    ]


def build_evidence(idea: Dict) -> List[EvidenceReference]:
    title = idea.get("evidence_title")

    if not title:
        return []

    return [
        EvidenceReference(
            title=title,
            source_type=idea.get("evidence_source_type", "unknown"),
            category=idea.get("research_category"),
            url=idea.get("evidence_url") or idea.get("url"),
        )
    ]


def build_risks(idea: Dict) -> List[str]:
    profile = idea.get("feasibility_analysis", {}).get(
        "build_profile",
        {},
    )
    difficulty = profile.get("difficulty", "")

    risks = [
        "Keep the first version constrained to a small, reproducible input set.",
        "Validate outputs before making claims about real-world usefulness.",
    ]

    if difficulty == "Hard":
        risks.insert(
            0,
            (
                "Reduce scope by implementing one narrow workflow before "
                "adding integrations, automation, or deployment polish."
            ),
        )

    return risks


def build_inference_options(candidate_families: List[Dict]) -> List[str]:
    labels = {
        "ai_ml": "AI / ML",
        "software_engineering": "Full-stack / Software Engineering",
        "cloud_platform": "Cloud / Platform",
        "cybersecurity": "Cybersecurity",
        "blockchain": "Blockchain",
        "fintech": "FinTech",
        "education_tech": "Education Technology",
    }

    options = []

    for candidate in candidate_families[:3]:
        family = candidate.get("family", "")
        label = labels.get(
            family,
            family.replace("_", " ").title(),
        )

        if label and label not in options:
            options.append(label)

    if "Help me choose" not in options:
        options.append("Help me choose")

    return options




@app.get(
    (
        "/v1/workspaces/{workspace_id}/"
        "projects/{project_id}/"
        "execution-evidence/events/lineage"
    ),
    response_model=ExecutionEventLineageResponse,
)
def get_project_execution_event_lineage(
    workspace_id: str,
    project_id: str,
    request: Request,
    context: AuthorizedProjectContext = Depends(
        get_authorized_project_context
    ),
    service: ExecutionEventProjectionService = Depends(
        get_authorized_execution_event_projection_service
    ),
) -> ExecutionEventLineageResponse:
    pagination_parameters = (
        "limit",
        "cursor",
        "offset",
        "page",
        "page_size",
        "per_page",
        "before",
        "after",
    )
    unsupported_sequence_parameters = (
        "from_sequence",
        "through_sequence",
    )

    pagination_parameter = next(
        (
            parameter
            for parameter in pagination_parameters
            if parameter in request.query_params
        ),
        None,
    )
    if pagination_parameter is not None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Execution event lineage is a complete "
                "project projection and does not support "
                "pagination parameter "
                f"'{pagination_parameter}'."
            ),
        )

    sequence_parameter = next(
        (
            parameter
            for parameter
            in unsupported_sequence_parameters
            if parameter in request.query_params
        ),
        None,
    )
    if sequence_parameter is not None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Execution event lineage sequence "
                f"parameter '{sequence_parameter}' is "
                "not yet supported."
            ),
        )

    try:
        projection = service.project_lineage(
            context.project_id
        )
    except (
        ExecutionEventProjectionUnsupportedStoreError
    ) as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    except ExecutionEventProjectHistoryTooLargeError as error:
        raise HTTPException(
            status_code=413,
            detail=str(error),
        ) from error
    except ExecutionEventProjectNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except ExecutionEventStoreError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Execution event lineage storage "
                "is temporarily unavailable."
            ),
        ) from error
    except ExecutionEventProjectionError as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Stored execution event lineage "
                "failed integrity validation."
            ),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    return ExecutionEventLineageResponse(
        project_id=projection.project_id,
        projection_through_sequence=(
            projection.projection_through_sequence
        ),
        ordered_records=[
            ExecutionEventRecordResponse(
                store_sequence=record.store_sequence,
                event=record.event,
            )
            for record
            in projection.ordered_records
        ],
        authoritative_event_ids=[
            record.event.execution_event_id
            for record
            in projection.ordered_records
            if (
                record.event.execution_event_id
                in projection.authoritative_event_ids
            )
        ],
        terminal_event_ids=list(
            projection.terminal_event_ids
        ),
        conflicts=[
            ExecutionEventLineageConflictResponse(
                predecessor_event_id=(
                    conflict.predecessor_event_id
                ),
                successor_event_ids=list(
                    conflict.successor_event_ids
                ),
                authoritative_successor_event_id=(
                    conflict
                    .authoritative_successor_event_id
                ),
            )
            for conflict
            in projection.conflicts
        ],
        has_conflicts=projection.has_conflicts,
    )


async def _read_bounded_github_webhook_body(
    request: Request,
) -> bytes:
    content_length = request.headers.get(
        "content-length"
    )

    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail="Invalid Content-Length.",
            ) from error

        if declared_length < 0:
            raise HTTPException(
                status_code=400,
                detail="Invalid Content-Length.",
            )

        if (
            declared_length
            > MAX_GITHUB_WEBHOOK_BODY_BYTES
        ):
            raise HTTPException(
                status_code=413,
                detail=(
                    "GitHub webhook payload exceeds "
                    "the maximum allowed size."
                ),
            )

    body = bytearray()

    async for chunk in request.stream():
        if (
            len(body) + len(chunk)
            > MAX_GITHUB_WEBHOOK_BODY_BYTES
        ):
            raise HTTPException(
                status_code=413,
                detail=(
                    "GitHub webhook payload exceeds "
                    "the maximum allowed size."
                ),
            )

        body.extend(chunk)

    return bytes(body)


@app.post(
    "/v1/integrations/github/webhook/{webhook_endpoint_id}",
    response_model=ExecutionEventAppendResult,
)
async def ingest_github_execution_evidence_webhook(
    webhook_endpoint_id: str,
    request: Request,
    github_event: str = Header(
        ...,
        alias="X-GitHub-Event",
    ),
    github_delivery: str = Header(
        ...,
        alias="X-GitHub-Delivery",
    ),
    github_signature: str = Header(
        ...,
        alias="X-Hub-Signature-256",
    ),
    authentication_service: (
        GitHubWebhookAuthenticationService
    ) = Depends(
        get_github_webhook_authentication_service
    ),
    ingestion_service: GitHubWebhookIngestionService = Depends(
        get_github_webhook_ingestion_service
    ),
) -> ExecutionEventAppendResult:
    raw_body = await _read_bounded_github_webhook_body(
        request
    )

    try:
        authenticated_source = (
            authentication_service.authenticate(
                webhook_endpoint_id=webhook_endpoint_id,
                signature_header=github_signature,
                raw_body=raw_body,
            )
        )

        return ingestion_service.ingest_authenticated(
            authenticated_source=authenticated_source,
            event_name=github_event,
            delivery_id=github_delivery,
            raw_body=raw_body,
            recorded_at=datetime.now(timezone.utc),
        )

    except (
        GitHubWebhookEndpointNotFoundError,
        GitHubWebhookCredentialAuthorityNotFoundError,
        GitHubWebhookRoutingNotFoundError,
        ExecutionEventProjectNotFoundError,
    ) as error:
        raise HTTPException(
            status_code=404,
            detail="GitHub webhook source was not found.",
        ) from error

    except GitHubWebhookSignatureError as error:
        raise HTTPException(
            status_code=401,
            detail=str(error),
        ) from error

    except (
        GitHubWebhookRepositoryIdentityError,
        GitHubWebhookMalformedJSONError,
        GitHubWebhookPayloadShapeError,
        GitHubWebhookPayloadError,
    ) as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    except (
        ExecutionEventIdempotencyConflictError
    ) as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    except (
        GitHubWebhookAuthenticationStoreError,
        GitHubWebhookSecretResolutionError,
        GitHubWebhookRoutingStoreError,
        ExecutionEventStoreError,
    ) as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


@app.get(
    "/v1/execution-evidence/repositories/{repository_key:path}",
    response_model=StoredRepositoryEvidence,
)
def get_execution_evidence_repository(
    repository_key: str,
    store: RepositoryEvidenceStore = Depends(
        get_execution_evidence_store
    ),
) -> StoredRepositoryEvidence:
    record = store.load(repository_key)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Repository evidence record was not found."
            ),
        )

    return record


@app.post(
    "/v1/execution-evidence/repositories/sync",
    response_model=StatefulGitHubSyncResult,
)
def sync_execution_evidence_repository(
    request: RepositoryEvidenceSyncRequest,
    coordinator: StatefulGitHubSyncCoordinator = Depends(
        get_execution_evidence_coordinator
    ),
) -> StatefulGitHubSyncResult:
    try:
        return coordinator.sync_repository(
            repository_url=request.repository_url,
            observed_at=datetime.now(timezone.utc),
            since=request.since,
        )
    except RepositoryEvidenceConflictError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


def _load_authorized_attribution_roadmap(
    *,
    roadmap_registry: SQLiteRoadmapSnapshotRegistry,
    context: AuthorizedProjectContext,
    project_direction_id: Optional[str] = None,
    roadmap_snapshot_id: Optional[str] = None,
):
    try:
        if project_direction_id is not None:
            legacy_roadmap = roadmap_registry.load(
                project_direction_id
            )

            if (
                legacy_roadmap is None
                or legacy_roadmap.project_id
                != context.project_id
            ):
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Trusted project direction "
                        "snapshot was not found."
                    ),
                )

            if roadmap_snapshot_id is None:
                stored_roadmap = legacy_roadmap
            else:
                if (
                    legacy_roadmap.roadmap_snapshot_id
                    != roadmap_snapshot_id
                ):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "roadmap_snapshot_id does not "
                            "match the trusted project "
                            "direction snapshot."
                        ),
                    )

                durable_roadmap = (
                    roadmap_registry
                    .load_by_durable_identity(
                        project_id=context.project_id,
                        roadmap_snapshot_id=(
                            roadmap_snapshot_id
                        ),
                    )
                )

                if durable_roadmap is None:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Durable roadmap identity does "
                            "not resolve to the trusted "
                            "project direction snapshot."
                        ),
                    )

                if (
                    durable_roadmap.project_direction_id
                    != project_direction_id
                ):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "project_direction_id does not "
                            "match the trusted durable "
                            "roadmap identity."
                        ),
                    )

                stored_roadmap = durable_roadmap

        elif roadmap_snapshot_id is not None:
            stored_roadmap = (
                roadmap_registry
                .load_by_durable_identity(
                    project_id=context.project_id,
                    roadmap_snapshot_id=(
                        roadmap_snapshot_id
                    ),
                )
            )

            if stored_roadmap is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Trusted roadmap snapshot was "
                        "not found."
                    ),
                )
        else:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Either project_direction_id or "
                    "roadmap_snapshot_id is required."
                ),
            )

    except HTTPException:
        raise
    except RoadmapRegistryError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Trusted roadmap storage could not "
                "validate the requested roadmap identity."
            ),
        ) from error

    if stored_roadmap.project_id != context.project_id:
        raise HTTPException(
            status_code=404,
            detail=(
                "Trusted project direction snapshot "
                "was not found."
            ),
        )

    return stored_roadmap


@app.post(
    "/v1/workspaces/{workspace_id}/projects/{project_id}/"
    "execution-evidence/attributions",
    response_model=AttributionMutationResult,
)
def attach_execution_evidence_attribution(
    workspace_id: str,
    project_id: str,
    request: ProjectScopedEvidenceAttributionAttachRequest,
    context: AuthorizedProjectContext = Depends(
        get_authorized_project_context
    ),
    service: EvidenceAttributionService = Depends(
        get_authorized_execution_evidence_attribution_service
    ),
    roadmap_registry: SQLiteRoadmapSnapshotRegistry = Depends(
        get_authorized_roadmap_registry
    ),
) -> AttributionMutationResult:
    try:
        require_capability(
            context,
            ProjectCapability.EXECUTION_EVIDENCE_MUTATE,
        )
    except ProjectCapabilityDeniedError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error

    stored_roadmap = (
        _load_authorized_attribution_roadmap(
            roadmap_registry=roadmap_registry,
            context=context,
            project_direction_id=(
                request.project_direction_id
            ),
            roadmap_snapshot_id=(
                request.roadmap_snapshot_id
            ),
        )
    )

    if stored_roadmap.project_status != "active":
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot attach new execution evidence "
                f"to a {stored_roadmap.project_status} "
                "project."
            ),
        )

    roadmap_stage = next(
        (
            stage
            for stage in stored_roadmap.snapshot.stages
            if (
                stage.stage_id
                == request.roadmap_node_id
            )
        ),
        None,
    )

    if roadmap_stage is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Roadmap node does not belong to the "
                "trusted project direction snapshot."
            ),
        )

    roadmap_context = RoadmapAttributionContext(
        roadmap_hash=(
            stored_roadmap.snapshot.roadmap_hash
        ),
        roadmap_stage_hash=(
            roadmap_stage.content_hash
        ),
        roadmap_node_id=roadmap_stage.stage_id,
        snapshot_version=(
            stored_roadmap.snapshot.snapshot_version
        ),
        canonicalization_version=(
            stored_roadmap.snapshot
            .canonicalization_version
        ),
    )

    try:
        return service.attach(
            repository_key=request.repository_key,
            evidence_key=request.evidence_key,
            roadmap_node_id=request.roadmap_node_id,
            project_id=stored_roadmap.project_id,
            roadmap_snapshot_id=(
                stored_roadmap.roadmap_snapshot_id
            ),
            project_direction_id=(
                stored_roadmap.project_direction_id
            ),
            roadmap_context=roadmap_context,
            rationale=request.rationale,
            decided_at=datetime.now(timezone.utc),
            expected_revision=request.expected_revision,
        )
    except (
        RepositoryEvidenceNotFoundError,
        ExecutionEvidenceNotFoundError,
    ) as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except RepositoryEvidenceConflictError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error


@app.delete(
    "/v1/workspaces/{workspace_id}/projects/{project_id}/"
    "execution-evidence/attributions",
    response_model=EvidenceAttributionDetachResponse,
)
def detach_execution_evidence_attribution(
    workspace_id: str,
    project_id: str,
    request: ProjectScopedEvidenceAttributionDetachRequest,
    context: AuthorizedProjectContext = Depends(
        get_authorized_project_context
    ),
    service: EvidenceAttributionService = Depends(
        get_authorized_execution_evidence_attribution_service
    ),
    roadmap_registry: SQLiteRoadmapSnapshotRegistry = Depends(
        get_authorized_roadmap_registry
    ),
) -> EvidenceAttributionDetachResponse:
    try:
        require_capability(
            context,
            ProjectCapability.EXECUTION_EVIDENCE_MUTATE,
        )
    except ProjectCapabilityDeniedError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error

    stored_roadmap = (
        _load_authorized_attribution_roadmap(
            roadmap_registry=roadmap_registry,
            context=context,
            project_direction_id=(
                request.project_direction_id
            ),
            roadmap_snapshot_id=(
                request.roadmap_snapshot_id
            ),
        )
    )

    try:
        removed = service.detach(
            repository_key=request.repository_key,
            evidence_key=request.evidence_key,
            roadmap_node_id=request.roadmap_node_id,
            project_id=stored_roadmap.project_id,
            roadmap_snapshot_id=(
                stored_roadmap.roadmap_snapshot_id
            ),
            project_direction_id=(
                stored_roadmap.project_direction_id
            ),
            removed_at=datetime.now(timezone.utc),
            expected_revision=request.expected_revision,
        )
    except RepositoryEvidenceNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except RepositoryEvidenceConflictError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    return EvidenceAttributionDetachResponse(
        removed=removed,
    )


@app.get(
    "/v1/workspaces/{workspace_id}/projects/{project_id}/"
    "execution-evidence/attributions",
    response_model=List[EvidenceAttribution],
)
def list_execution_evidence_attributions(
    workspace_id: str,
    project_id: str,
    repository_key: Optional[str] = None,
    project_direction_id: Optional[str] = None,
    roadmap_snapshot_id: Optional[str] = None,
    roadmap_node_id: Optional[str] = None,
    context: AuthorizedProjectContext = Depends(
        get_authorized_project_context
    ),
    service: EvidenceAttributionService = Depends(
        get_authorized_execution_evidence_attribution_service
    ),
    roadmap_registry: SQLiteRoadmapSnapshotRegistry = Depends(
        get_authorized_roadmap_registry
    ),
) -> List[EvidenceAttribution]:
    try:
        require_capability(
            context,
            ProjectCapability.EXECUTION_EVIDENCE_READ,
        )
    except ProjectCapabilityDeniedError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error

    try:
        query = ProjectScopedEvidenceAttributionListQuery(
            repository_key=repository_key,
            project_direction_id=project_direction_id,
            roadmap_snapshot_id=roadmap_snapshot_id,
            roadmap_node_id=roadmap_node_id,
        )
    except ValidationError as error:
        raise RequestValidationError(
            error.errors()
        ) from error

    stored_roadmap = (
        _load_authorized_attribution_roadmap(
            roadmap_registry=roadmap_registry,
            context=context,
            project_direction_id=(
                query.project_direction_id
            ),
            roadmap_snapshot_id=(
                query.roadmap_snapshot_id
            ),
        )
    )

    try:
        if query.roadmap_node_id is not None:
            return service.list_for_roadmap_node(
                repository_key=query.repository_key,
                project_id=stored_roadmap.project_id,
                roadmap_snapshot_id=(
                    stored_roadmap.roadmap_snapshot_id
                ),
                project_direction_id=(
                    stored_roadmap.project_direction_id
                ),
                roadmap_node_id=query.roadmap_node_id,
            )

        return service.list_for_repository(
            query.repository_key,
            project_id=stored_roadmap.project_id,
            roadmap_snapshot_id=(
                stored_roadmap.roadmap_snapshot_id
            ),
            project_direction_id=(
                stored_roadmap.project_direction_id
            ),
        )
    except RepositoryEvidenceNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@app.get(
    "/v1/workspaces/{workspace_id}/memberships",
    response_model=List[WorkspaceMembership],
)
def list_workspace_memberships(
    workspace_id: str,
    context: AuthorizedWorkspaceContext = Depends(
        get_authorized_workspace_context
    ),
    store: SQLiteWorkspaceMembershipStore = Depends(
        get_authorized_workspace_membership_store
    ),
) -> List[WorkspaceMembership]:
    try:
        require_workspace_capability(
            context,
            WorkspaceCapability.MEMBERSHIP_READ,
        )

        return store.list_current_memberships()

    except WorkspaceCapabilityDeniedError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except WorkspaceMembershipStoreError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Trusted workspace membership storage "
                "could not list memberships."
            ),
        ) from error


class WorkspaceMembershipStatusTransitionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    status: WorkspaceMembershipStatus
    expected_revision: int = Field(ge=0)
    reason: Optional[str] = None


class WorkspaceMembershipRoleTransitionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    role: WorkspaceMembershipRole
    expected_revision: int = Field(ge=0)
    reason: Optional[str] = None


class WorkspaceMembershipHistoryResponse(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    membership: WorkspaceMembership
    status_transitions: List[
        WorkspaceMembershipTransition
    ]
    role_transitions: List[
        WorkspaceMembershipRoleTransition
    ]


@app.get(
    (
        "/v1/workspaces/{workspace_id}/memberships/"
        "{membership_id}/history"
    ),
    response_model=WorkspaceMembershipHistoryResponse,
)
def get_workspace_membership_history(
    workspace_id: str,
    membership_id: str,
    context: AuthorizedWorkspaceContext = Depends(
        get_authorized_workspace_context
    ),
    store: SQLiteWorkspaceMembershipStore = Depends(
        get_authorized_workspace_membership_store
    ),
) -> WorkspaceMembershipHistoryResponse:
    try:
        require_workspace_capability(
            context,
            WorkspaceCapability.MEMBERSHIP_READ,
        )

        membership = store.load_by_id(
            membership_id
        )

        return WorkspaceMembershipHistoryResponse(
            membership=membership,
            status_transitions=(
                store.list_transitions(
                    membership_id
                )
            ),
            role_transitions=(
                store.list_role_transitions(
                    membership_id
                )
            ),
        )

    except WorkspaceCapabilityDeniedError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except WorkspaceMembershipNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Workspace membership does not exist.",
        ) from error
    except WorkspaceMembershipStoreError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Trusted workspace membership storage "
                "could not load membership history."
            ),
        ) from error


@app.patch(
    (
        "/v1/workspaces/{workspace_id}/memberships/"
        "{membership_id}/role"
    ),
    response_model=WorkspaceMembershipRoleMutationResult,
)
def transition_workspace_membership_role(
    workspace_id: str,
    membership_id: str,
    request: WorkspaceMembershipRoleTransitionRequest,
    context: AuthorizedWorkspaceContext = Depends(
        get_authorized_workspace_context
    ),
    store: SQLiteWorkspaceMembershipStore = Depends(
        get_authorized_workspace_membership_store
    ),
) -> WorkspaceMembershipRoleMutationResult:
    try:
        require_workspace_capability(
            context,
            WorkspaceCapability.MEMBERSHIP_ROLE_MANAGE,
        )

        return store.transition_role(
            membership_id,
            new_role=request.role,
            changed_at=datetime.now(
                timezone.utc
            ),
            expected_revision=(
                request.expected_revision
            ),
            changed_by_principal_id=(
                context.principal_id
            ),
            reason=request.reason,
        )

    except WorkspaceCapabilityDeniedError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except WorkspaceMembershipNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Workspace membership does not exist.",
        ) from error
    except WorkspaceMembershipRoleAuthorizationError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except WorkspaceMembershipLastManagerError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except (
        WorkspaceMembershipInactiveError,
        WorkspaceMembershipRevisionConflictError,
    ) as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except WorkspaceMembershipTransitionError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except WorkspaceMembershipStoreError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Trusted workspace membership storage "
                "could not transition membership role."
            ),
        ) from error


@app.patch(
    (
        "/v1/workspaces/{workspace_id}/memberships/"
        "{membership_id}/status"
    ),
    response_model=WorkspaceMembershipMutationResult,
)
def transition_workspace_membership_status(
    workspace_id: str,
    membership_id: str,
    request: WorkspaceMembershipStatusTransitionRequest,
    context: AuthorizedWorkspaceContext = Depends(
        get_authorized_workspace_context
    ),
    store: SQLiteWorkspaceMembershipStore = Depends(
        get_authorized_workspace_membership_store
    ),
) -> WorkspaceMembershipMutationResult:
    try:
        require_workspace_capability(
            context,
            WorkspaceCapability.MEMBERSHIP_STATUS_MANAGE,
        )

        return store.transition_status(
            membership_id,
            new_status=request.status,
            changed_at=datetime.now(
                timezone.utc
            ),
            expected_revision=(
                request.expected_revision
            ),
            reason=request.reason,
            changed_by_principal_id=(
                context.principal_id
            ),
        )

    except WorkspaceCapabilityDeniedError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except WorkspaceMembershipNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Workspace membership does not exist.",
        ) from error
    except WorkspaceMembershipLastManagerError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except WorkspaceMembershipRevisionConflictError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except WorkspaceMembershipTransitionError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except WorkspaceMembershipStoreError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Trusted workspace membership storage "
                "could not transition membership status."
            ),
        ) from error


@app.post(
    "/v1/workspaces/{workspace_id}/projects/{project_id}/status",
    response_model=ProjectStatusMutationResult,
)
def transition_project_status(
    workspace_id: str,
    project_id: str,
    request: ProjectStatusTransitionRequest,
    context: AuthorizedProjectContext = Depends(
        get_authorized_project_context
    ),
    roadmap_registry: SQLiteRoadmapSnapshotRegistry = Depends(
        get_authorized_roadmap_registry
    ),
) -> ProjectStatusMutationResult:
    try:
        require_capability(
            context,
            ProjectCapability.PROJECT_LIFECYCLE_MANAGE,
        )

        return (
            roadmap_registry
            .transition_project_status(
                context.project_id,
                new_status=request.status,
                changed_at=datetime.now(
                    timezone.utc
                ),
                reason=request.reason,
                expected_revision=(
                    request.expected_revision
                ),
            )
        )
    except ProjectCapabilityDeniedError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except ProjectNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except (
        ProjectRevisionConflictError,
        ProjectStatusTransitionError,
    ) as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except RoadmapRegistryError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Trusted project lifecycle storage "
                "could not complete the transition."
            ),
        ) from error


@app.get(
    "/v1/workspaces/{workspace_id}/projects/{project_id}/status-transitions",
    response_model=List[ProjectStatusTransition],
)
def list_project_status_transition_history(
    workspace_id: str,
    project_id: str,
    context: AuthorizedProjectContext = Depends(
        get_authorized_project_context
    ),
    roadmap_registry: SQLiteRoadmapSnapshotRegistry = Depends(
        get_authorized_roadmap_registry
    ),
) -> List[ProjectStatusTransition]:
    try:
        require_capability(
            context,
            ProjectCapability.PROJECT_READ,
        )

        return (
            roadmap_registry
            .list_project_status_transitions(
                context.project_id
            )
        )
    except ProjectCapabilityDeniedError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except ProjectNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except RoadmapRegistryError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Trusted project lifecycle history "
                "could not be loaded."
            ),
        ) from error


@app.get(
    "/v1/execution-evidence/storage/readiness",
    response_model=ExecutionEvidenceStorageReadiness,
)
def execution_evidence_storage_readiness(
    store: RepositoryEvidenceStore = Depends(
        get_execution_evidence_store
    ),
) -> ExecutionEvidenceStorageReadiness:
    return (
        assess_execution_evidence_storage_readiness(
            store
        )
    )


@app.get("/health")
def health() -> Dict:
    return {
        "status": "healthy",
        "service": "research-to-prototype-intelligence-api",
        "version": "2.1.0",
    }


@app.post("/v1/synthesis-demo")
def run_synthesis_demo_endpoint(request: SynthesisDemoRequest) -> Dict:
    artifact_path = Path(request.artifact_path)

    output_path = build_default_output_path(
        fixture_id=artifact_path.parent.name,
        artifact_id=artifact_path.stem,
        mode=request.mode,
        provider=request.provider,
        dry_run=request.dry_run,
        output_dir=Path("outputs/api_synthesis_runs"),
    )
    validation_report_output_path = build_default_validation_report_path(
        synthesis_output_path=output_path,
        report_dir=Path("outputs/reports"),
    )

    result = run_llm_synthesis_demo(
        artifact_path=artifact_path,
        mode=request.mode,
        provider_name=request.provider,
        dry_run=request.dry_run,
        calls_remaining=request.calls_remaining,
        tokens_remaining=request.tokens_remaining,
        output_path=output_path,
        validation_report_output_path=validation_report_output_path,
    )

    return {
        "status": "ready",
        "fixture_id": result.get("fixture_id"),
        "artifact_id": result.get("artifact_id"),
        "mode": result.get("mode"),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "dry_run": result.get("dry_run"),
        "api_call_attempted": result.get("api_call_attempted"),
        "routing_decision": result.get("routing_decision"),
        "saved_output_validation": result.get("saved_output_validation"),
        "final_synthesis": result.get("final_synthesis"),
        "final_synthesis_validation": result.get(
            "final_synthesis_validation"
        ),
        "validation_report_output_path": result.get(
            "validation_report_output_path"
        ),
    }


def _project_intelligence_persistence(
    *,
    status: str,
    remediation: Optional[str],
) -> ProjectIntelligencePersistence:
    return ProjectIntelligencePersistence(
        roadmap_registry=(
            RoadmapRegistryPersistenceStatus(
                status=status,
                remediation=remediation,
            )
        )
    )


def generate_project_intelligence(
    request: ProjectIntelligenceRequest,
    *,
    roadmap_registry: Optional[
        RoadmapSnapshotRegistry
    ] = None,
    roadmap_registry_status: str = (
        "unavailable_error"
    ),
    roadmap_registry_remediation: Optional[str] = (
        "Trusted roadmap persistence was not "
        "provided for this generation."
    ),
) -> ProjectIntelligenceResponse:
    persistence = _project_intelligence_persistence(
        status=roadmap_registry_status,
        remediation=roadmap_registry_remediation,
    )

    query = request.goal.strip()
    constraints = request.constraints.model_dump()
    selected_direction = (
        request.selected_direction.strip()
        if request.selected_direction
        else None
    )

    correction_metadata = get_query_metadata(query)
    corrected_query = correction_metadata.get(
        "corrected_query",
        query,
    )

    pipeline = [
        PipelineStep(
            name="query_correction",
            status="completed",
            detail=(
                "Checked the goal for high-confidence spelling and "
                "query normalization issues."
            ),
        ),
    ]

    if correction_metadata.get("query_requires_confirmation"):
        return ProjectIntelligenceResponse(
            persistence=persistence,
            status="needs_correction_confirmation",
            query=query,
            corrected_query=corrected_query,
            goal_summary=query,
            detected_domain=correction_metadata.get("detected_domain"),
            detected_intent=correction_metadata.get("detected_intent"),
            clarification_required=True,
            clarification_message=f"Did you mean: {corrected_query}?",
            pipeline=pipeline,
        )

    understanding = understand_query(
        goal=corrected_query,
        constraints=constraints,
    )

    pipeline.append(
        PipelineStep(
            name="query_understanding",
            status="completed",
            detail=(
                "Extracted explicit role, time, skill, stack, project intent, "
                "and possible technical-direction signals."
            ),
        )
    )

    if (
        understanding["requires_clarification_before_retrieval"]
        and not selected_direction
    ):
        pipeline.append(
            PipelineStep(
                name="clarification_gate",
                status="completed",
                detail=(
                    "Skipped retrieval because the goal did not include enough "
                    "technical direction for a trustworthy recommendation."
                ),
            )
        )

        return ProjectIntelligenceResponse(
            persistence=persistence,
            status="needs_clarification",
            query=query,
            corrected_query=corrected_query,
            goal_summary=corrected_query,
            detected_domain="general",
            detected_intent=correction_metadata.get("detected_intent"),
            clarification_required=True,
            clarification_message=understanding[
                "clarification_question"
            ],
            clarification_options=understanding[
                "clarification_options"
            ],
            suggested_topics=[
                "AI project for an ML engineer role in 3 weeks",
                "React portfolio project for frontend roles",
                "Cloud cost optimization project",
                "Cybersecurity automation project",
                "Help me choose based on my current skills",
            ],
            pipeline=pipeline,
        )

    retrieval_intent_hints = [
        hint
        for hint in (
            understanding["direction_hints"]
            + [correction_metadata.get("detected_domain")]
        )
        if hint
    ]

    evidence_payload = retrieve_evidence(
        corrected_query,
        top_k=6,
        intent_hints=retrieval_intent_hints,
        selected_direction=selected_direction,
    )

    inference = evidence_payload["inference"]
    evidence_items = evidence_payload["merged_results"]
    explicit_domain = correction_metadata.get("detected_domain")
    planning_domain = resolve_planning_domain(
        explicit_domain=explicit_domain,
        inferred_focus=inference.get("inferred_focus"),
    )
    has_specific_explicit_domain = bool(
        explicit_domain and explicit_domain != "general"
    )
    research_evidence_assessment = build_research_evidence_assessment(
        evidence_payload,
        query=corrected_query,
    )
    evidence_brief = build_evidence_brief(
        evidence_items=evidence_items,
        user_query=corrected_query,
    )
    evidence_cards = build_live_evidence_cards_from_brief(evidence_brief)
    evidence_coverage = asdict(
        classify_evidence_coverage(
            evidence_cards,
            query=corrected_query,
            detected_domain=planning_domain,
            supported_domains=SUPPORTED_PLANNING_DOMAINS,
            domain_inference=inference,
            query_metadata=correction_metadata,
        )
    )

    pipeline.extend(
        [
            PipelineStep(
                name="broad_evidence_retrieval",
                status="completed",
                detail=(
                    "Retrieved broad evidence from research papers, project "
                    "patterns, and GitHub implementation references."
                ),
            ),
            PipelineStep(
                name="evidence_domain_inference",
                status="completed",
                detail=(
                    "Inferred the technical family and focus from evidence, "
                    "then used that focus for a second retrieval pass."
                ),
            ),
            PipelineStep(
                name="focused_evidence_retrieval",
                status="completed",
                detail=(
                    f"Selected {len(evidence_items)} focused evidence items "
                    f"for {inference.get('inferred_focus', 'the inferred focus')}."
                ),
            ),
        ]
    )

    if (
        inference.get("requires_clarification")
        and not has_specific_explicit_domain
    ):
        candidate_families = inference.get(
            "candidate_families",
            [],
        )

        pipeline.append(
            PipelineStep(
                name="clarification_gate",
                status="completed",
                detail=(
                    "Evidence was too mixed to choose one technical direction "
                    "without asking the user a focused question."
                ),
            )
        )

        return ProjectIntelligenceResponse(
            persistence=persistence,
            status="needs_clarification",
            query=query,
            corrected_query=corrected_query,
            goal_summary=corrected_query,
            detected_domain=planning_domain,
            detected_intent=correction_metadata.get("detected_intent"),
            evidence_route=evidence_payload.get("selected_route"),
            evidence_coverage=evidence_coverage,
            source_counts={
                "research_papers": len(
                    evidence_payload.get("research_results", [])
                ),
                "project_patterns": len(
                    evidence_payload.get("project_results", [])
                ),
                "github_repositories": len(
                    evidence_payload.get("github_results", [])
                ),
            },
            clarification_required=True,
            clarification_message=(
                "Your goal could reasonably lead in more than one direction. "
                "Which type of work would you like the project to showcase?"
            ),
            clarification_options=build_inference_options(
                candidate_families
            ),
            inferred_domain_family=inference.get(
                "inferred_domain_family"
            ),
            family_confidence=inference.get("family_confidence"),
            inferred_focus=inference.get("inferred_focus"),
            focus_confidence=inference.get("focus_confidence"),
            candidate_families=candidate_families,
            candidate_focuses=inference.get(
                "candidate_focuses",
                [],
            ),
            pipeline=pipeline,
        )

    pipeline.append(
        PipelineStep(
            name="project_planning_baseline",
            status="completed",
            detail=(
                "Generated deterministic directions and applied target-role, "
                "timeline, skill-level, and preferred-stack constraints. "
                "This node will later be upgraded to LLM synthesis."
            ),
        )
    )

    ideas = generate_project_ideas(
        evidence_items,
        corrected_query,
        max_ideas=3,
        constraints=constraints,
        detected_domain=planning_domain,
    )

    enrichment = enrich_product_ideas(
        ideas=ideas,
        constraints=constraints,
    )
    ideas = apply_coverage_notes_to_ideas(
        ideas=enrichment.ideas,
        evidence_coverage=evidence_coverage,
    )
    ideas = adapt_ideas_to_query_anchors(
        ideas=ideas,
        query=corrected_query,
        resolved_domain=planning_domain,
    )
    final_verification_results = (
        enrichment.final_verification_results
    )
    repairs_by_index = enrichment.repairs_by_index

    product_plan_readiness = assess_product_plan_readiness(
        evidence_items=evidence_items,
        ideas=ideas,
        verification_results=final_verification_results,
        repairs_by_index=repairs_by_index,
        research_evidence_assessment=research_evidence_assessment,
    )

    pipeline.extend(
        [
            PipelineStep(
                name="plan_verification",
                status="completed",
                detail=(
                    "Checked role alignment, preferred stack, timeline, evidence, "
                    "specific MVP language, and direction diversity."
                ),
            ),
            PipelineStep(
                name="plan_repair",
                status="completed",
                detail=(
                    "Applied safe deterministic repairs before creating the "
                    "final Easy, Medium, and Hard portfolio ladder."
                ),
            ),
        ]
    )

    directions = []

    for index, idea in enumerate(ideas, start=1):
        verification = final_verification_results[index - 1]
        repairs = repairs_by_index[index - 1]

        feasibility = idea.get("feasibility_analysis", {})
        profile = feasibility.get("build_profile", {})

        mission_context = build_mission_context(
            idea=idea,
            user_goal=request.goal,
            query=corrected_query,
            resolved_planning_domain=planning_domain,
            constraints={
                "skill_level": getattr(request.constraints, "skill_level", "intermediate"),
                "time_available": getattr(request.constraints, "time_available", "2-3 weeks"),
                "preferred_stack": getattr(request.constraints, "preferred_stack", []),
                "target_roles": getattr(request.constraints, "target_roles", []),
            },
            evidence_coverage=evidence_coverage,
        )

        directions.append(
            ProjectDirection(
                id=f"direction-{index}",
                title=idea.get(
                    "project_title",
                    f"Project Direction {index}",
                ),
                summary=idea.get("idea_angle", ""),
                scope=profile.get("scope", "Unknown"),
                estimated_effort=profile.get(
                    "estimated_effort",
                    "Unknown",
                ),
                portfolio_tier=profile.get(
                    "tier",
                    "Portfolio Build",
                ),
                difficulty=profile.get(
                    "difficulty",
                    "Medium",
                ),
                career_signal=feasibility.get(
                    "skill_signal",
                    "Unknown",
                ),
                why_it_fits=" ".join(
                    part
                    for part in [
                        idea.get("constraint_summary", ""),
                        idea.get("evidence_focus_statement")
                        or idea.get("research_motivation")
                        or "Grounded in the selected technical evidence.",
                    ]
                    if part
                ),
                mvp_steps=idea.get("mvp_scope", []),
                advanced_extensions=idea.get(
                    "advanced_extensions",
                    [],
                ),
                tech_stack=idea.get(
                    "suggested_tech_stack",
                    [],
                ),
                target_roles=idea.get("target_roles", []),
                evidence=build_evidence(idea),
                decision_trace=(
                    build_project_decision_trace(
                        idea=idea,
                        idea_id=f"direction-{index}",
                        assessment=research_evidence_assessment,
                        query=corrected_query,
                    )
                    if research_evidence_assessment
                    else None
                ),
                roadmap=enrich_roadmap_for_execution(
                    stages=build_roadmap(idea),
                    idea=idea,
                    context=mission_context,
                ),
                risks=build_risks(idea),
                verification=VerificationResult(**verification),
                repairs_applied=repairs,
            )
        )

    if roadmap_registry is not None:
        created_at = datetime.now(timezone.utc)
        snapshot_records = [
            create_stored_roadmap_snapshot(
                response_direction_id=direction.id,
                title=direction.title,
                snapshot=build_roadmap_snapshot(
                    direction.roadmap
                ),
                created_at=created_at,
            )
            for direction in directions
        ]

        try:
            stored_snapshots = (
                roadmap_registry.create_many(
                    snapshot_records
                )
            )
        except RoadmapRegistryError:
            persistence = (
                _project_intelligence_persistence(
                    status="unavailable_error",
                    remediation=(
                        "Project directions were generated "
                        "successfully, but their trusted "
                        "roadmap identities could not be "
                        "persisted. Retry registration "
                        "before using attribution features."
                    ),
                )
            )
        else:
            directions = [
                direction.model_copy(
                    update={
                        "project_id": stored.project_id,
                        "roadmap_snapshot_id": (
                            stored.roadmap_snapshot_id
                        ),
                        "project_direction_id": (
                            stored.project_direction_id
                        ),
                    },
                    deep=True,
                )
                for direction, stored in zip(
                    directions,
                    stored_snapshots,
                )
            ]
            persistence = (
                _project_intelligence_persistence(
                    status="ready",
                    remediation=None,
                )
            )

    write_decision_trace_artifact(
        query=corrected_query,
        traces=[
            direction.decision_trace
            for direction in directions
            if direction.decision_trace is not None
        ],
    )

    pipeline.append(
        PipelineStep(
            name="response_validation",
            status="completed",
            detail=(
                f"Serialized {len(directions)} project directions with "
                "structured verification results."
            ),
        )
    )

    return ProjectIntelligenceResponse(
        persistence=persistence,
        status="ready",
        query=query,
        corrected_query=corrected_query,
        goal_summary=corrected_query,
        detected_domain=planning_domain,
        detected_intent=correction_metadata.get("detected_intent"),
        evidence_route=evidence_payload.get("selected_route"),
        evidence_coverage=evidence_coverage,
        source_counts={
            "research_papers": len(
                evidence_payload.get("research_results", [])
            ),
            "project_patterns": len(
                evidence_payload.get("project_results", [])
            ),
            "github_repositories": len(
                evidence_payload.get("github_results", [])
            ),
        },
        research_evidence_assessment=research_evidence_assessment,
        product_plan_readiness=product_plan_readiness.to_dict(),
        synthesis_status=build_project_intelligence_synthesis_status(
            query=corrected_query,
            constraints=constraints,
            evidence_items=evidence_items,
            project_directions=directions,
        ),
        clarification_required=False,
        inferred_domain_family=inference.get(
            "inferred_domain_family"
        ),
        family_confidence=inference.get("family_confidence"),
        inferred_focus=inference.get("inferred_focus"),
        focus_confidence=inference.get("focus_confidence"),
        resolved_planning_domain=resolve_response_planning_domain(
            planning_domain=planning_domain,
            generated_domain=(
                ideas[0].get("detected_domain")
                if ideas
                else None
            ),
        ),
        candidate_families=inference.get(
            "candidate_families",
            [],
        ),
        candidate_focuses=inference.get(
            "candidate_focuses",
            [],
        ),
        directions=directions,
        pipeline=pipeline,
    )


@app.post(
    "/v1/project-intelligence",
    response_model=ProjectIntelligenceResponse,
)
def generate_project_intelligence_endpoint(
    request: ProjectIntelligenceRequest,
    runtime: ExecutionEvidenceStorageRuntime = Depends(
        get_execution_evidence_storage_runtime
    ),
) -> ProjectIntelligenceResponse:
    return generate_project_intelligence(
        request,
        roadmap_registry=runtime.roadmap_registry,
        roadmap_registry_status=(
            runtime.roadmap_registry_status
        ),
        roadmap_registry_remediation=(
            runtime.remediation
        ),
    )
