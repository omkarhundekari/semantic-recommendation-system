from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from planning.candidate_provenance import CandidateProvenance
from schemas.decision_trace_models import ProjectDecisionTrace


class UserConstraints(BaseModel):
    skill_level: Optional[str] = Field(
        default=None,
        description="Examples: beginner, intermediate, advanced.",
    )
    time_available: Optional[str] = Field(
        default=None,
        description="Examples: weekend, 1 week, 3 weeks, 1 month.",
    )
    target_roles: List[str] = Field(default_factory=list)
    preferred_stack: List[str] = Field(default_factory=list)


class ProjectIntelligenceRequest(BaseModel):
    goal: str = Field(
        min_length=3,
        max_length=1200,
        description="Natural-language project goal or career objective.",
    )
    selected_direction: Optional[str] = Field(
        default=None,
        max_length=120,
        description=(
            "Optional user-confirmed direction chosen during clarification. "
            "This is separate from the user's raw goal."
        ),
    )
    constraints: UserConstraints = Field(default_factory=UserConstraints)


class SynthesisDemoRequest(BaseModel):
    artifact_path: str = Field(
        description=(
            "Path to a reviewed fixture artifact used for synthesis safety "
            "pipeline inspection."
        ),
    )
    mode: str = Field(default="deep")
    provider: str = Field(default="fake")
    dry_run: bool = Field(default=True)
    calls_remaining: int = Field(default=5)
    tokens_remaining: int = Field(default=10000)


class EvidenceReference(BaseModel):
    title: str
    source_type: str
    category: Optional[str] = None
    url: Optional[str] = None


class RoadmapStage(BaseModel):
    id: str
    title: str
    purpose: str
    tasks: List[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    status: str
    score: int
    max_score: int
    checks: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class ProjectDirection(BaseModel):
    id: str
    title: str
    summary: str
    scope: str
    estimated_effort: str
    portfolio_tier: str
    difficulty: str
    career_signal: str
    why_it_fits: str
    mvp_steps: List[str] = Field(default_factory=list)
    advanced_extensions: List[str] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list)
    target_roles: List[str] = Field(default_factory=list)
    evidence: List[EvidenceReference] = Field(default_factory=list)
    planner_provenance: Optional[CandidateProvenance] = None
    decision_trace: Optional[ProjectDecisionTrace] = None
    roadmap: List[RoadmapStage] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    verification: VerificationResult
    repairs_applied: List[str] = Field(default_factory=list)


class PipelineStep(BaseModel):
    name: str
    status: str
    detail: str


class SynthesisSummary(BaseModel):
    status: str
    source: str
    can_run_llm: bool
    routing_reason: str
    card_count: int
    validated: bool
    grounded_direction_count: int
    invented_source_count: int
    estimated_tokens: int


class ValidatedProjectDirection(BaseModel):
    scope_level: str
    build_type: str
    estimated_time: str
    title: str
    evidence_confidence: str
    source_ids: List[str] = Field(default_factory=list)
    grounding_warnings: List[str] = Field(default_factory=list)


class PresentationProjectDirection(BaseModel):
    title: str
    level: str
    estimated_time: str
    what_you_will_build: str
    why_it_matters: str
    skills_shown: List[str] = Field(default_factory=list)
    interview_talking_point: str
    evidence_badge: str
    confidence_explanation: str
    open_questions: List[str] = Field(default_factory=list)
    evidence_summary: str


class SynthesisStatus(BaseModel):
    available: bool
    reason: str
    safe_inspection_endpoint: str
    current_planning_source: str
    synthesis_summary: SynthesisSummary
    validated_project_directions: List[
        ValidatedProjectDirection
    ] = Field(default_factory=list)
    presentation_project_directions: List[
        PresentationProjectDirection
    ] = Field(default_factory=list)
    live_evidence_cards: Dict[str, Any] = Field(default_factory=dict)
    routing_preview: Dict[str, Any] = Field(default_factory=dict)
    token_estimate: Dict[str, Any] = Field(default_factory=dict)
    live_final_synthesis_preview: Dict[str, Any] = Field(default_factory=dict)
    live_final_synthesis_preview_validation: Dict[str, Any] = Field(
        default_factory=dict
    )
    safety_pipeline: Dict[str, bool] = Field(default_factory=dict)


class ProjectIntelligenceResponse(BaseModel):
    status: str
    query: str
    corrected_query: Optional[str] = None
    goal_summary: str

    detected_domain: Optional[str] = None
    detected_intent: Optional[str] = None
    evidence_route: Optional[str] = None
    source_counts: Dict[str, int] = Field(default_factory=dict)

    clarification_required: bool = False
    clarification_message: Optional[str] = None
    clarification_options: List[str] = Field(default_factory=list)
    suggested_topics: List[str] = Field(default_factory=list)

    inferred_domain_family: Optional[str] = None
    family_confidence: Optional[float] = None
    inferred_focus: Optional[str] = None
    focus_confidence: Optional[float] = None
    resolved_planning_domain: Optional[str] = None
    candidate_families: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_focuses: List[Dict[str, Any]] = Field(default_factory=list)

    research_evidence_assessment: Optional[Dict[str, Any]] = None
    product_plan_readiness: Optional[Dict[str, Any]] = None
    synthesis_status: Optional[SynthesisStatus] = None

    directions: List[ProjectDirection] = Field(default_factory=list)
    pipeline: List[PipelineStep] = Field(default_factory=list)