from typing import List, Optional

from pydantic import BaseModel, Field


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
    constraints: UserConstraints = Field(default_factory=UserConstraints)


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
    checks: dict = Field(default_factory=dict)
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
    roadmap: List[RoadmapStage] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    verification: VerificationResult
    repairs_applied: List[str] = Field(default_factory=list)


class PipelineStep(BaseModel):
    name: str
    status: str
    detail: str


class ProjectIntelligenceResponse(BaseModel):
    status: str
    query: str
    corrected_query: Optional[str] = None
    goal_summary: str
    detected_domain: Optional[str] = None
    detected_intent: Optional[str] = None
    evidence_route: Optional[str] = None
    source_counts: dict = Field(default_factory=dict)
    clarification_message: Optional[str] = None
    suggested_topics: List[str] = Field(default_factory=list)
    directions: List[ProjectDirection] = Field(default_factory=list)
    pipeline: List[PipelineStep] = Field(default_factory=list)