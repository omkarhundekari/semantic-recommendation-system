from pathlib import Path

from execution_evidence.sqlite_execution_event_store import (
    SQLiteExecutionEventStore,
)
from execution_evidence.storage_service import (
    TrustedSQLiteStorageService,
)
from execution_evidence.trusted_store import (
    initialize_fresh_trusted_store,
)


def test_trusted_storage_service_builds_execution_event_store(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-22T12:00:00+00:00",
    )

    service = TrustedSQLiteStorageService(
        database_path,
        workspace_id="workspace_test",
    )

    store = service.build_execution_event_store()

    assert isinstance(
        store,
        SQLiteExecutionEventStore,
    )
    assert store._path == database_path
    assert store._workspace_id == "workspace_test"
