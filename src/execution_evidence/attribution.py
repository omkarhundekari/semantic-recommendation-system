from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel

from execution_evidence.models import (
    EvidenceAttribution,
    RoadmapAttributionContext,
)
from execution_evidence.store import (
    RepositoryEvidenceConflictError,
    RepositoryEvidenceStore,
    StoredRepositoryEvidence,
)


class RepositoryEvidenceNotFoundError(LookupError):
    pass


class ExecutionEvidenceNotFoundError(LookupError):
    pass


class AttributionContextConflictError(
    RepositoryEvidenceConflictError
):
    pass


class AttributionMutationResult(BaseModel):
    stored: StoredRepositoryEvidence
    attribution: EvidenceAttribution
    created: bool


class EvidenceAttributionService:
    def __init__(
        self,
        *,
        store: RepositoryEvidenceStore,
    ) -> None:
        self._store = store

    def attach(
        self,
        *,
        repository_key: str,
        evidence_key: str,
        roadmap_node_id: str,
        decided_at: datetime,
        rationale: str = "",
        project_id: Optional[str] = None,
        roadmap_snapshot_id: Optional[str] = None,
        project_direction_id: Optional[str] = None,
        roadmap_context: Optional[
            RoadmapAttributionContext
        ] = None,
        expected_revision: Optional[int] = None,
    ) -> AttributionMutationResult:
        record = self._load_record(repository_key)
        self._require_evidence(
            record=record,
            evidence_key=evidence_key,
        )

        normalized_project_direction_id = (
            project_direction_id.strip()
            if project_direction_id
            else None
        )

        attribution_identity = (
            normalized_project_direction_id,
            evidence_key,
            roadmap_node_id,
        )

        existing = next(
            (
                item
                for item in record.attributions
                if (
                    item.attribution_identity
                    == attribution_identity
                )
            ),
            None,
        )

        if existing is not None:
            if (
                existing.roadmap_context
                != roadmap_context
            ):
                raise AttributionContextConflictError(
                    "Evidence attribution already exists "
                    "with different roadmap identity context."
                )

            return AttributionMutationResult(
                stored=record,
                attribution=existing,
                created=False,
            )

        attribution = EvidenceAttribution(
            attribution_id=(
                str(uuid4())
                if normalized_project_direction_id
                is not None
                else None
            ),
            project_id=(
                project_id.strip()
                if project_id
                else None
            ),
            roadmap_snapshot_id=(
                roadmap_snapshot_id.strip()
                if roadmap_snapshot_id
                else None
            ),
            project_direction_id=(
                normalized_project_direction_id
            ),
            evidence_key=evidence_key,
            roadmap_node_id=roadmap_node_id,
            source="manual",
            confidence=1.0,
            rationale=rationale,
            status="accepted",
            decided_at=decided_at,
            roadmap_context=roadmap_context,
        )

        updated = StoredRepositoryEvidence.model_validate(
            {
                **record.model_dump(),
                "attributions": [
                    *record.attributions,
                    attribution,
                ],
                "saved_at": decided_at,
            }
        )

        saved = self._store.save(
            updated,
            expected_revision=(
                record.revision
                if expected_revision is None
                else expected_revision
            ),
        )

        return AttributionMutationResult(
            stored=saved,
            attribution=attribution,
            created=True,
        )

    def detach(
        self,
        *,
        repository_key: str,
        evidence_key: str,
        roadmap_node_id: str,
        removed_at: datetime,
        project_direction_id: Optional[str] = None,
        expected_revision: Optional[int] = None,
    ) -> bool:
        record = self._load_record(repository_key)
        normalized_project_direction_id = (
            project_direction_id.strip()
            if project_direction_id
            else None
        )
        attribution_identity = (
            normalized_project_direction_id,
            evidence_key,
            roadmap_node_id,
        )

        remaining = [
            attribution
            for attribution in record.attributions
            if (
                attribution.attribution_identity
                != attribution_identity
            )
        ]

        if len(remaining) == len(
            record.attributions
        ):
            return False

        updated = StoredRepositoryEvidence.model_validate(
            {
                **record.model_dump(),
                "attributions": remaining,
                "saved_at": removed_at,
            }
        )

        self._store.save(
            updated,
            expected_revision=(
                record.revision
                if expected_revision is None
                else expected_revision
            ),
        )

        return True

    def list_for_repository(
        self,
        repository_key: str,
        *,
        project_direction_id: Optional[str] = None,
    ) -> List[EvidenceAttribution]:
        record = self._load_record(repository_key)
        normalized_project_direction_id = (
            project_direction_id.strip()
            if project_direction_id
            else None
        )

        return [
            attribution.model_copy(deep=True)
            for attribution in record.attributions
            if (
                project_direction_id is None
                or attribution.project_direction_id
                == normalized_project_direction_id
            )
        ]

    def list_for_roadmap_node(
        self,
        *,
        repository_key: str,
        roadmap_node_id: str,
        project_direction_id: Optional[str] = None,
    ) -> List[EvidenceAttribution]:
        return [
            attribution
            for attribution in self.list_for_repository(
                repository_key,
                project_direction_id=(
                    project_direction_id
                ),
            )
            if (
                attribution.roadmap_node_id
                == roadmap_node_id
            )
        ]

    def _load_record(
        self,
        repository_key: str,
    ) -> StoredRepositoryEvidence:
        record = self._store.load(repository_key)

        if record is None:
            raise RepositoryEvidenceNotFoundError(
                "Repository evidence record was not found."
            )

        return record

    @staticmethod
    def _require_evidence(
        *,
        record: StoredRepositoryEvidence,
        evidence_key: str,
    ) -> None:
        if not any(
            item.evidence_key == evidence_key
            for item in record.evidence
        ):
            raise ExecutionEvidenceNotFoundError(
                "Execution evidence item was not found "
                "in the repository record."
            )
