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

        scope = self._normalize_scope(
            project_id=project_id,
            roadmap_snapshot_id=roadmap_snapshot_id,
            project_direction_id=project_direction_id,
        )
        attribution_identity = self._identity_for_values(
            scope=scope,
            evidence_key=evidence_key,
            roadmap_node_id=roadmap_node_id,
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
            if existing.roadmap_context != roadmap_context:
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
                if scope["project_direction_id"]
                is not None
                else None
            ),
            project_id=scope["project_id"],
            roadmap_snapshot_id=(
                scope["roadmap_snapshot_id"]
            ),
            project_direction_id=(
                scope["project_direction_id"]
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
        project_id: Optional[str] = None,
        roadmap_snapshot_id: Optional[str] = None,
        project_direction_id: Optional[str] = None,
        expected_revision: Optional[int] = None,
    ) -> bool:
        record = self._load_record(repository_key)
        scope = self._normalize_scope(
            project_id=project_id,
            roadmap_snapshot_id=roadmap_snapshot_id,
            project_direction_id=project_direction_id,
        )
        attribution_identity = self._identity_for_values(
            scope=scope,
            evidence_key=evidence_key,
            roadmap_node_id=roadmap_node_id,
        )

        remaining = [
            attribution
            for attribution in record.attributions
            if (
                attribution.attribution_identity
                != attribution_identity
            )
        ]

        if len(remaining) == len(record.attributions):
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
        project_id: Optional[str] = None,
        roadmap_snapshot_id: Optional[str] = None,
        project_direction_id: Optional[str] = None,
    ) -> List[EvidenceAttribution]:
        record = self._load_record(repository_key)
        scope = self._normalize_scope(
            project_id=project_id,
            roadmap_snapshot_id=roadmap_snapshot_id,
            project_direction_id=project_direction_id,
        )

        return [
            attribution.model_copy(deep=True)
            for attribution in record.attributions
            if self._matches_scope(
                attribution=attribution,
                scope=scope,
            )
        ]

    def list_for_roadmap_node(
        self,
        *,
        repository_key: str,
        roadmap_node_id: str,
        project_id: Optional[str] = None,
        roadmap_snapshot_id: Optional[str] = None,
        project_direction_id: Optional[str] = None,
    ) -> List[EvidenceAttribution]:
        return [
            attribution
            for attribution in self.list_for_repository(
                repository_key,
                project_id=project_id,
                roadmap_snapshot_id=roadmap_snapshot_id,
                project_direction_id=(
                    project_direction_id
                ),
            )
            if (
                attribution.roadmap_node_id
                == roadmap_node_id
            )
        ]

    @staticmethod
    def _normalize_scope(
        *,
        project_id: Optional[str],
        roadmap_snapshot_id: Optional[str],
        project_direction_id: Optional[str],
    ) -> dict[str, Optional[str]]:
        normalized_project_id = (
            project_id.strip()
            if project_id
            else None
        )
        normalized_snapshot_id = (
            roadmap_snapshot_id.strip()
            if roadmap_snapshot_id
            else None
        )
        normalized_direction_id = (
            project_direction_id.strip()
            if project_direction_id
            else None
        )

        if (
            (normalized_project_id is None)
            != (normalized_snapshot_id is None)
        ):
            raise ValueError(
                "project_id and roadmap_snapshot_id "
                "must be supplied together."
            )

        return {
            "project_id": normalized_project_id,
            "roadmap_snapshot_id": (
                normalized_snapshot_id
            ),
            "project_direction_id": (
                normalized_direction_id
            ),
        }

    @staticmethod
    def _identity_for_values(
        *,
        scope: dict[str, Optional[str]],
        evidence_key: str,
        roadmap_node_id: str,
    ) -> tuple[str, ...]:
        project_id = scope["project_id"]
        roadmap_snapshot_id = (
            scope["roadmap_snapshot_id"]
        )
        project_direction_id = (
            scope["project_direction_id"]
        )

        if (
            project_id is not None
            and roadmap_snapshot_id is not None
        ):
            return (
                "durable",
                project_id,
                roadmap_snapshot_id,
                evidence_key,
                roadmap_node_id,
            )

        if project_direction_id is not None:
            return (
                "direction",
                project_direction_id,
                evidence_key,
                roadmap_node_id,
            )

        return (
            "legacy",
            evidence_key,
            roadmap_node_id,
        )

    @staticmethod
    def _matches_scope(
        *,
        attribution: EvidenceAttribution,
        scope: dict[str, Optional[str]],
    ) -> bool:
        project_id = scope["project_id"]
        roadmap_snapshot_id = (
            scope["roadmap_snapshot_id"]
        )
        project_direction_id = (
            scope["project_direction_id"]
        )

        if (
            project_id is not None
            and roadmap_snapshot_id is not None
        ):
            return attribution.durable_scope == (
                project_id,
                roadmap_snapshot_id,
            )

        if project_direction_id is not None:
            return (
                attribution.project_direction_id
                == project_direction_id
            )

        return True

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
