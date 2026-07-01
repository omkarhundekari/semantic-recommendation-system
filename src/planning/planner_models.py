from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvidenceSource:
    source_id: str
    source_type: str
    title: str
    excerpt: str
    category: Optional[str] = None
    url: Optional[str] = None
    retrieval_rank: Optional[int] = None
    retrieval_signals: Dict[str, float] = field(default_factory=dict)
    support_scope: str = "direct"
    retention_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceBrief:
    query: str
    sources: List[EvidenceSource] = field(default_factory=list)
    source_counts: Dict[str, int] = field(default_factory=dict)
    recurring_concepts: List[str] = field(default_factory=list)
    coverage_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "sources": [
                source.to_dict()
                for source in self.sources
            ],
            "source_counts": dict(self.source_counts),
            "recurring_concepts": list(self.recurring_concepts),
            "coverage_warnings": list(self.coverage_warnings),
        }
