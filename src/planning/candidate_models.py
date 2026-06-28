from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class CandidateDirection:
    title: str
    problem_statement: str
    target_user: str
    core_workflow: List[str]
    mvp_scope: List[str]
    success_metrics: List[str]
    evidence_relationship: str
    source_ids: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    suggested_stack: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateGenerationRequest:
    user_goal: str
    skill_level: str = ""
    time_available: str = ""
    target_roles: List[str] = field(default_factory=list)
    preferred_stack: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
