from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SupportingPaperEvidence(BaseModel):
    document_id: str
    title: str
    category: Optional[str] = None
    retrieval_rank: Optional[int] = None
    alignment: Literal["direct", "adjacent", "weak"]
    evidence_tags: List[str] = Field(default_factory=list)
    evidence_snippets: List[str] = Field(default_factory=list)
    matched_query_terms: List[str] = Field(default_factory=list)
    matched_query_phrases: List[str] = Field(default_factory=list)
    matched_required_anchor_terms: List[str] = Field(default_factory=list)
    alignment_reason: str


class DetectedSignal(BaseModel):
    group: str
    name: str
    paper_count: int
    supporting_document_ids: List[str] = Field(default_factory=list)


class ImplementationReference(BaseModel):
    title: str
    source_type: str
    architecture_signals: List[str] = Field(default_factory=list)
    technology_signals: List[str] = Field(default_factory=list)
    trusted: bool = False


class IdeaInspiration(BaseModel):
    title: str
    source_type: str
    url: Optional[str] = None
    role: str = "idea_specific_inspiration"


class ProjectDecisionTrace(BaseModel):
    schema_version: str = "1.0"

    idea_id: str
    idea_title: str

    research_support_scope: Literal[
        "planning_domain",
        "idea_specific",
        "mixed",
    ]

    supporting_papers: List[SupportingPaperEvidence] = Field(
        default_factory=list
    )
    evidence_tags: List[str] = Field(default_factory=list)
    detected_signals: List[DetectedSignal] = Field(default_factory=list)

    buildable_gap: str
    confidence_level: Literal["strong", "limited", "exploratory"]
    confidence_reason: str

    planning_domain: str
    planning_domain_reason: str

    idea_specific_rationale: str
    primary_inspiration: Optional[IdeaInspiration] = None
    implementation_references: List[ImplementationReference] = Field(
        default_factory=list
    )

    assumptions: List[str] = Field(default_factory=list)
    evidence_gaps: List[str] = Field(default_factory=list)

    feasibility_result: Optional[str] = None
    feasibility_reason: Optional[str] = None
