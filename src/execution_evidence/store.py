from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from execution_evidence.github_repository import (
    GitHubRepositoryReference,
)
from execution_evidence.models import (
    ExecutionEvidenceItem,
    RepositorySyncState,
)
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
)


CURRENT_EVIDENCE_STORE_SCHEMA_VERSION = 1


class StoredRepositoryEvidence(BaseModel):
    schema_version: int = Field(
        default=CURRENT_EVIDENCE_STORE_SCHEMA_VERSION,
        ge=1,
    )
    repository: GitHubRepositoryReference
    evidence: List[ExecutionEvidenceItem] = Field(
        default_factory=list
    )
    sync_state: RepositorySyncState
    sync_snapshot: GitHubRepositorySyncSnapshot
    revision: int = Field(default=0, ge=0)
    saved_at: datetime

    def model_post_init(self, __context) -> None:
        repository_key = self.repository.repository_key

        if self.sync_state.repository_key != repository_key:
            raise ValueError(
                "Repository sync state does not match "
                "the stored repository."
            )

        if self.sync_snapshot.repository_key != repository_key:
            raise ValueError(
                "Repository sync snapshot does not match "
                "the stored repository."
            )

        mismatched_items = [
            item.evidence_key
            for item in self.evidence
            if (
                item.provider != self.repository.provider
                or item.repository_full_name.lower()
                != self.repository.full_name.lower()
            )
        ]

        if mismatched_items:
            raise ValueError(
                "Stored execution evidence contains items "
                "from a different repository."
            )


class RepositoryEvidenceConflictError(RuntimeError):
    pass


class RepositoryEvidenceStore(ABC):
    @abstractmethod
    def load(
        self,
        repository_key: str,
    ) -> Optional[StoredRepositoryEvidence]:
        raise NotImplementedError

    @abstractmethod
    def save(
        self,
        record: StoredRepositoryEvidence,
        *,
        expected_revision: Optional[int] = None,
    ) -> StoredRepositoryEvidence:
        raise NotImplementedError

    @abstractmethod
    def delete(
        self,
        repository_key: str,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_repository_keys(self) -> List[str]:
        raise NotImplementedError


class InMemoryRepositoryEvidenceStore(
    RepositoryEvidenceStore
):
    def __init__(self) -> None:
        self._records: Dict[
            str,
            StoredRepositoryEvidence,
        ] = {}

    def load(
        self,
        repository_key: str,
    ) -> Optional[StoredRepositoryEvidence]:
        record = self._records.get(repository_key)

        if record is None:
            return None

        return record.model_copy(deep=True)

    def save(
        self,
        record: StoredRepositoryEvidence,
        *,
        expected_revision: Optional[int] = None,
    ) -> StoredRepositoryEvidence:
        repository_key = record.repository.repository_key
        existing = self._records.get(repository_key)
        current_revision = (
            existing.revision
            if existing is not None
            else -1
        )

        if (
            expected_revision is not None
            and expected_revision != current_revision
        ):
            raise RepositoryEvidenceConflictError(
                "Repository evidence revision conflict: "
                f"expected {expected_revision}, "
                f"found {current_revision}."
            )

        saved = record.model_copy(
            update={
                "revision": current_revision + 1,
            },
            deep=True,
        )

        self._records[repository_key] = saved

        return saved.model_copy(deep=True)

    def delete(
        self,
        repository_key: str,
    ) -> bool:
        return self._records.pop(
            repository_key,
            None,
        ) is not None

    def list_repository_keys(self) -> List[str]:
        return sorted(self._records)
