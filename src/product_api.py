from dataclasses import asdict
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
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
from planning.llm_synthesis_demo import (
    build_default_output_path,
    build_default_validation_report_path,
    run_llm_synthesis_demo,
)
from schemas.product_models import (
    EvidenceReference,
    PipelineStep,
    ProjectDirection,
    ProjectIntelligenceRequest,
    ProjectIntelligenceResponse,
    RoadmapStage,
    VerificationResult,
    SynthesisDemoRequest,
)
from source_router import retrieve_evidence

from execution_evidence.api_models import (
    EvidenceAttributionAttachRequest,
    EvidenceAttributionDetachRequest,
    EvidenceAttributionDetachResponse,
    RepositoryEvidenceSyncRequest,
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
from execution_evidence.store import (
    RepositoryEvidenceConflictError,
    RepositoryEvidenceStore,
    StoredRepositoryEvidence,
)
from execution_evidence.trusted_store import (
    TrustedStoreInitializationError,
    initialize_fresh_trusted_store,
)


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


def build_execution_evidence_store(
    path: Optional[str] = None,
    *,
    backend: Optional[str] = None,
) -> RepositoryEvidenceStore:
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

        return JsonRepositoryEvidenceStore(
            resolved_path
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

    readiness = (
        assess_sqlite_database_readiness(
            resolved_path
        )
    )

    if readiness.status != "ready":
        details = "; ".join(
            readiness.errors
        )
        raise ValueError(
            "SQLite execution evidence storage "
            "failed readiness validation: "
            f"{details}"
        )

    return SQLiteRepositoryEvidenceStore(
        resolved_path,
        initialize_schema=False,
    )


_execution_evidence_store = (
    build_execution_evidence_store()
)


def get_execution_evidence_store(
) -> RepositoryEvidenceStore:
    return _execution_evidence_store


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


@app.post(
    "/v1/execution-evidence/attributions",
    response_model=AttributionMutationResult,
)
def attach_execution_evidence_attribution(
    request: EvidenceAttributionAttachRequest,
    service: EvidenceAttributionService = Depends(
        get_execution_evidence_attribution_service
    ),
) -> AttributionMutationResult:
    try:
        return service.attach(
            repository_key=request.repository_key,
            evidence_key=request.evidence_key,
            roadmap_node_id=request.roadmap_node_id,
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
    "/v1/execution-evidence/attributions",
    response_model=EvidenceAttributionDetachResponse,
)
def detach_execution_evidence_attribution(
    request: EvidenceAttributionDetachRequest,
    service: EvidenceAttributionService = Depends(
        get_execution_evidence_attribution_service
    ),
) -> EvidenceAttributionDetachResponse:
    try:
        removed = service.detach(
            repository_key=request.repository_key,
            evidence_key=request.evidence_key,
            roadmap_node_id=request.roadmap_node_id,
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
    "/v1/execution-evidence/attributions",
    response_model=List[EvidenceAttribution],
)
def list_execution_evidence_attributions(
    repository_key: str,
    roadmap_node_id: Optional[str] = None,
    service: EvidenceAttributionService = Depends(
        get_execution_evidence_attribution_service
    ),
) -> List[EvidenceAttribution]:
    try:
        if roadmap_node_id is not None:
            return service.list_for_roadmap_node(
                repository_key=repository_key,
                roadmap_node_id=roadmap_node_id,
            )

        return service.list_for_repository(
            repository_key
        )
    except RepositoryEvidenceNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
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


@app.post(
    "/v1/project-intelligence",
    response_model=ProjectIntelligenceResponse,
)
def generate_project_intelligence(
    request: ProjectIntelligenceRequest,
) -> ProjectIntelligenceResponse:
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
