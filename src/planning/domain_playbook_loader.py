from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field


PLAYBOOK_DIR = Path(__file__).resolve().parents[2] / "data" / "playbooks"


class DomainPlaybook(BaseModel):
    domain: str
    playbook_version: str

    typical_inputs: List[str] = Field(default_factory=list)
    typical_outputs: List[str] = Field(default_factory=list)
    core_concepts: List[str] = Field(default_factory=list)
    typical_file_structure: List[str] = Field(default_factory=list)
    setup_commands: List[str] = Field(default_factory=list)

    first_milestone_check: str
    validation_checks: List[str] = Field(default_factory=list)
    common_errors: List[str] = Field(default_factory=list)
    typical_portfolio_artifacts: List[str] = Field(default_factory=list)
    interview_talking_points: List[str] = Field(default_factory=list)

    demo_strategy: str
    metrics_to_track: List[str] = Field(default_factory=list)
    deployment_path: str
    test_strategy: str


def load_domain_playbook(domain: str) -> DomainPlaybook:
    normalized_domain = (domain or "generic").strip().lower() or "generic"
    path = PLAYBOOK_DIR / f"{normalized_domain}.json"

    if not path.exists():
        raise ValueError(
            f"No mission playbook found for domain '{normalized_domain}'. "
            f"Expected file: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    return DomainPlaybook(**payload)


def load_playbook_or_generic(domain: str | None) -> DomainPlaybook:
    try:
        return load_domain_playbook(domain or "generic")
    except ValueError:
        return load_domain_playbook("generic")
