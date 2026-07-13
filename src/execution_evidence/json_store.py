from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

from execution_evidence.store import (
    CURRENT_EVIDENCE_STORE_SCHEMA_VERSION,
    RepositoryEvidenceConflictError,
    RepositoryEvidenceStore,
    StoredRepositoryEvidence,
)


class RepositoryEvidenceStoreError(RuntimeError):
    pass


class RepositoryEvidenceStoreDocument(BaseModel):
    schema_version: int = Field(
        default=CURRENT_EVIDENCE_STORE_SCHEMA_VERSION,
        ge=1,
    )
    records: Dict[str, StoredRepositoryEvidence] = Field(
        default_factory=dict
    )

    def model_post_init(self, __context) -> None:
        mismatched_keys = [
            repository_key
            for repository_key, record in self.records.items()
            if repository_key
            != record.repository.repository_key
        ]

        if mismatched_keys:
            raise ValueError(
                "Repository evidence store contains a record "
                "under the wrong repository key."
            )


class JsonRepositoryEvidenceStore(
    RepositoryEvidenceStore
):
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def load(
        self,
        repository_key: str,
    ) -> Optional[StoredRepositoryEvidence]:
        document = self._read_document()
        record = document.records.get(repository_key)

        if record is None:
            return None

        return record.model_copy(deep=True)

    def save(
        self,
        record: StoredRepositoryEvidence,
        *,
        expected_revision: Optional[int] = None,
    ) -> StoredRepositoryEvidence:
        document = self._read_document()
        repository_key = record.repository.repository_key
        existing = document.records.get(repository_key)
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

        document.records[repository_key] = saved
        self._write_document(document)

        return saved.model_copy(deep=True)

    def delete(
        self,
        repository_key: str,
    ) -> bool:
        document = self._read_document()

        if repository_key not in document.records:
            return False

        del document.records[repository_key]
        self._write_document(document)

        return True

    def list_repository_keys(self) -> List[str]:
        document = self._read_document()
        return sorted(document.records)

    def _read_document(
        self,
    ) -> RepositoryEvidenceStoreDocument:
        if not self._path.exists():
            return RepositoryEvidenceStoreDocument()

        try:
            raw_document = self._path.read_text(
                encoding="utf-8"
            )
        except OSError as error:
            raise RepositoryEvidenceStoreError(
                "Could not read the repository evidence store."
            ) from error

        try:
            payload = json.loads(raw_document)
        except json.JSONDecodeError as error:
            raise RepositoryEvidenceStoreError(
                "Repository evidence store contains invalid JSON."
            ) from error

        try:
            return (
                RepositoryEvidenceStoreDocument.model_validate(
                    payload
                )
            )
        except ValidationError as error:
            raise RepositoryEvidenceStoreError(
                "Repository evidence store failed schema validation."
            ) from error

    def _write_document(
        self,
        document: RepositoryEvidenceStoreDocument,
    ) -> None:
        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = self._path.with_name(
            f".{self._path.name}.{uuid4().hex}.tmp"
        )

        serialized = document.model_dump_json(
            indent=2,
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as temporary_file:
                temporary_file.write(serialized)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            os.replace(
                temporary_path,
                self._path,
            )
        except OSError as error:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

            raise RepositoryEvidenceStoreError(
                "Could not write the repository evidence store."
            ) from error
