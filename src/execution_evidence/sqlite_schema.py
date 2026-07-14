from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


CURRENT_SQLITE_SCHEMA_VERSION = 5


class SQLiteMigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SQLiteMigration:
    version: int
    name: str
    sql: str


INITIAL_SCHEMA_SQL = """
CREATE TABLE workspaces (
    workspace_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE repositories (
    repository_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    repository_key TEXT NOT NULL,
    provider TEXT NOT NULL,
    owner TEXT NOT NULL,
    repository_name TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0
        CHECK (revision >= 0),
    aggregate_schema_version INTEGER NOT NULL
        CHECK (aggregate_schema_version >= 1),
    saved_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id)
        REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    UNIQUE (workspace_id, repository_key)
);

CREATE TABLE evidence_items (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_id INTEGER NOT NULL,
    evidence_key TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    url TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    content_hash TEXT,
    payload_json TEXT NOT NULL,
    position INTEGER NOT NULL
        CHECK (position >= 0),
    FOREIGN KEY (repository_id)
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    UNIQUE (repository_id, evidence_key),
    UNIQUE (
        repository_id,
        evidence_type,
        external_id
    )
);

CREATE TABLE evidence_attributions (
    attribution_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_id INTEGER NOT NULL,
    evidence_key TEXT NOT NULL,
    roadmap_node_id TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL
        CHECK (
            confidence >= 0.0
            AND confidence <= 1.0
        ),
    rationale TEXT NOT NULL,
    status TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    position INTEGER NOT NULL
        CHECK (position >= 0),
    FOREIGN KEY (repository_id)
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    UNIQUE (
        repository_id,
        evidence_key,
        roadmap_node_id
    )
);

CREATE TABLE repository_sync_states (
    repository_id INTEGER PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (repository_id)
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE
);

CREATE TABLE repository_sync_snapshots (
    repository_id INTEGER PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (repository_id)
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE
);

CREATE TABLE execution_jobs (
    job_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    repository_id INTEGER,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    progress_current INTEGER NOT NULL DEFAULT 0
        CHECK (progress_current >= 0),
    progress_total INTEGER
        CHECK (
            progress_total IS NULL
            OR progress_total >= 0
        ),
    input_json TEXT NOT NULL,
    result_json TEXT,
    error_message TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0
        CHECK (cancel_requested IN (0, 1)),
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id)
        REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    FOREIGN KEY (repository_id)
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_repositories_workspace
    ON repositories(
        workspace_id,
        updated_at DESC
    );

CREATE INDEX idx_evidence_repository_timeline
    ON evidence_items(
        repository_id,
        occurred_at DESC
    );

CREATE INDEX idx_evidence_repository_type
    ON evidence_items(
        repository_id,
        evidence_type,
        occurred_at DESC
    );

CREATE INDEX idx_attributions_repository_stage
    ON evidence_attributions(
        repository_id,
        roadmap_node_id,
        status
    );

CREATE INDEX idx_attributions_evidence
    ON evidence_attributions(
        repository_id,
        evidence_key
    );

CREATE INDEX idx_jobs_workspace_status
    ON execution_jobs(
        workspace_id,
        status,
        created_at
    );

CREATE INDEX idx_jobs_repository_status
    ON execution_jobs(
        repository_id,
        status,
        created_at
    );
"""


ALLOW_PENDING_ATTRIBUTIONS_SQL = """
ALTER TABLE evidence_attributions
    RENAME TO evidence_attributions_v1;

CREATE TABLE evidence_attributions (
    attribution_id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_id INTEGER NOT NULL,
    evidence_key TEXT NOT NULL,
    roadmap_node_id TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL
        CHECK (
            confidence >= 0.0
            AND confidence <= 1.0
        ),
    rationale TEXT NOT NULL,
    status TEXT NOT NULL,
    decided_at TEXT,
    payload_json TEXT NOT NULL,
    position INTEGER NOT NULL
        CHECK (position >= 0),
    FOREIGN KEY (repository_id)
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    UNIQUE (
        repository_id,
        evidence_key,
        roadmap_node_id
    )
);

INSERT INTO evidence_attributions (
    attribution_id,
    repository_id,
    evidence_key,
    roadmap_node_id,
    source,
    confidence,
    rationale,
    status,
    decided_at,
    payload_json,
    position
)
SELECT
    attribution_id,
    repository_id,
    evidence_key,
    roadmap_node_id,
    source,
    confidence,
    rationale,
    status,
    decided_at,
    payload_json,
    position
FROM evidence_attributions_v1;

DROP TABLE evidence_attributions_v1;

CREATE INDEX idx_attributions_repository_stage
    ON evidence_attributions(
        repository_id,
        roadmap_node_id,
        status
    );

CREATE INDEX idx_attributions_evidence
    ON evidence_attributions(
        repository_id,
        evidence_key
    );
"""



CREATE_ROADMAP_REGISTRY_SQL = """
CREATE TABLE roadmap_registry (
    roadmap_registry_id INTEGER
        PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    project_direction_id TEXT NOT NULL,
    response_direction_id TEXT NOT NULL,
    title TEXT NOT NULL,
    roadmap_hash TEXT NOT NULL
        CHECK (length(roadmap_hash) = 64),
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    supersedes_id TEXT,
    FOREIGN KEY (workspace_id)
        REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    FOREIGN KEY (
        workspace_id,
        supersedes_id
    )
        REFERENCES roadmap_registry(
            workspace_id,
            project_direction_id
        ),
    UNIQUE (
        workspace_id,
        project_direction_id
    )
);

CREATE INDEX idx_roadmap_registry_workspace_created
    ON roadmap_registry(
        workspace_id,
        created_at DESC
    );

CREATE INDEX idx_roadmap_registry_workspace_hash
    ON roadmap_registry(
        workspace_id,
        roadmap_hash
    );
"""


SCOPE_ATTRIBUTIONS_BY_PROJECT_SQL = """
ALTER TABLE evidence_attributions
    RENAME TO evidence_attributions_v2;

CREATE TABLE evidence_attributions (
    attribution_row_id INTEGER
        PRIMARY KEY AUTOINCREMENT,
    attribution_id TEXT,
    repository_id INTEGER NOT NULL,
    roadmap_registry_id INTEGER,
    project_direction_id TEXT,
    evidence_key TEXT NOT NULL,
    roadmap_node_id TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL
        CHECK (
            confidence >= 0.0
            AND confidence <= 1.0
        ),
    rationale TEXT NOT NULL,
    status TEXT NOT NULL,
    decided_at TEXT,
    payload_json TEXT NOT NULL,
    position INTEGER NOT NULL
        CHECK (position >= 0),
    CHECK (
        (
            attribution_id IS NULL
            AND roadmap_registry_id IS NULL
            AND project_direction_id IS NULL
        )
        OR
        (
            attribution_id IS NOT NULL
            AND length(trim(attribution_id)) > 0
            AND roadmap_registry_id IS NOT NULL
            AND project_direction_id IS NOT NULL
            AND length(trim(project_direction_id)) > 0
        )
    ),
    FOREIGN KEY (repository_id)
        REFERENCES repositories(repository_id)
        ON DELETE CASCADE,
    FOREIGN KEY (roadmap_registry_id)
        REFERENCES roadmap_registry(
            roadmap_registry_id
        )
        ON DELETE RESTRICT
);

INSERT INTO evidence_attributions (
    attribution_row_id,
    attribution_id,
    repository_id,
    roadmap_registry_id,
    project_direction_id,
    evidence_key,
    roadmap_node_id,
    source,
    confidence,
    rationale,
    status,
    decided_at,
    payload_json,
    position
)
SELECT
    attribution_id,
    NULL,
    repository_id,
    NULL,
    NULL,
    evidence_key,
    roadmap_node_id,
    source,
    confidence,
    rationale,
    status,
    decided_at,
    payload_json,
    position
FROM evidence_attributions_v2;

DROP TABLE evidence_attributions_v2;

CREATE UNIQUE INDEX
    idx_attributions_public_identity
ON evidence_attributions(
    attribution_id
)
WHERE attribution_id IS NOT NULL;

CREATE UNIQUE INDEX
    idx_attributions_scoped_identity
ON evidence_attributions(
    repository_id,
    project_direction_id,
    evidence_key,
    roadmap_node_id
)
WHERE project_direction_id IS NOT NULL;

CREATE UNIQUE INDEX
    idx_attributions_legacy_identity
ON evidence_attributions(
    repository_id,
    evidence_key,
    roadmap_node_id
)
WHERE project_direction_id IS NULL;

CREATE INDEX idx_attributions_repository_stage
    ON evidence_attributions(
        repository_id,
        project_direction_id,
        roadmap_node_id,
        status
    );

CREATE INDEX idx_attributions_evidence
    ON evidence_attributions(
        repository_id,
        project_direction_id,
        evidence_key
    );

CREATE TRIGGER
    validate_attribution_roadmap_scope_insert
BEFORE INSERT ON evidence_attributions
WHEN NEW.roadmap_registry_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM repositories AS repository
            JOIN roadmap_registry AS roadmap
                ON roadmap.roadmap_registry_id =
                    NEW.roadmap_registry_id
            WHERE
                repository.repository_id =
                    NEW.repository_id
                AND roadmap.workspace_id =
                    repository.workspace_id
                AND roadmap.project_direction_id =
                    NEW.project_direction_id
        )
        THEN RAISE(
            ABORT,
            'Attribution roadmap scope does not match repository workspace'
        )
    END;
END;

CREATE TRIGGER
    validate_attribution_roadmap_scope_update
BEFORE UPDATE OF
    repository_id,
    roadmap_registry_id,
    project_direction_id
ON evidence_attributions
WHEN NEW.roadmap_registry_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM repositories AS repository
            JOIN roadmap_registry AS roadmap
                ON roadmap.roadmap_registry_id =
                    NEW.roadmap_registry_id
            WHERE
                repository.repository_id =
                    NEW.repository_id
                AND roadmap.workspace_id =
                    repository.workspace_id
                AND roadmap.project_direction_id =
                    NEW.project_direction_id
        )
        THEN RAISE(
            ABORT,
            'Attribution roadmap scope does not match repository workspace'
        )
    END;
END;
"""


CREATE_IMPORT_RECEIPTS_SQL = """
CREATE TABLE execution_evidence_import_receipts (
    receipt_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_identifier TEXT NOT NULL,
    source_root_hash TEXT NOT NULL,
    canonicalization_version INTEGER NOT NULL,
    report_version INTEGER NOT NULL,
    repository_count INTEGER NOT NULL,
    evidence_count INTEGER NOT NULL,
    attribution_count INTEGER NOT NULL,
    deterministic_report_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_import_receipts_source_hash
    ON execution_evidence_import_receipts(
        source_root_hash
    );
"""


MIGRATIONS: Sequence[SQLiteMigration] = (
    SQLiteMigration(
        version=1,
        name="create_execution_evidence_schema",
        sql=INITIAL_SCHEMA_SQL,
    ),
    SQLiteMigration(
        version=2,
        name="allow_pending_evidence_attributions",
        sql=ALLOW_PENDING_ATTRIBUTIONS_SQL,
    ),
    SQLiteMigration(
        version=3,
        name="create_execution_evidence_import_receipts",
        sql=CREATE_IMPORT_RECEIPTS_SQL,
    ),
    SQLiteMigration(
        version=4,
        name="create_roadmap_snapshot_registry",
        sql=CREATE_ROADMAP_REGISTRY_SQL,
    ),
    SQLiteMigration(
        version=5,
        name="scope_evidence_attributions_by_project",
        sql=SCOPE_ATTRIBUTIONS_BY_PROJECT_SQL,
    ),
)


def connect_execution_evidence_database(
    path: Path | str,
) -> sqlite3.Connection:
    database_path = Path(path)
    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        connection = sqlite3.connect(
            str(database_path),
            timeout=5.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )
        connection.execute(
            "PRAGMA busy_timeout = 5000"
        )
        connection.execute(
            "PRAGMA journal_mode = WAL"
        )
        connection.execute(
            "PRAGMA synchronous = NORMAL"
        )

        return connection
    except sqlite3.Error as error:
        raise SQLiteMigrationError(
            "Could not open the execution evidence database."
        ) from error


def initialize_execution_evidence_database(
    path: Path | str,
) -> int:
    connection = (
        connect_execution_evidence_database(path)
    )

    try:
        apply_execution_evidence_migrations(
            connection
        )
        return get_execution_evidence_schema_version(
            connection
        )
    finally:
        connection.close()


def apply_execution_evidence_migrations(
    connection: sqlite3.Connection,
) -> None:
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            execution_evidence_schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )

        applied_versions = {
            int(row["version"])
            for row in connection.execute(
                """
                SELECT version
                FROM execution_evidence_schema_migrations
                ORDER BY version
                """
            )
        }

        for migration in MIGRATIONS:
            if migration.version in applied_versions:
                continue

            _apply_migration(
                connection,
                migration,
            )
    except sqlite3.Error as error:
        raise SQLiteMigrationError(
            "Could not migrate the execution evidence database."
        ) from error


def get_execution_evidence_schema_version(
    connection: sqlite3.Connection,
) -> int:
    try:
        row = connection.execute(
            """
            SELECT COALESCE(MAX(version), 0)
                AS version
            FROM execution_evidence_schema_migrations
            """
        ).fetchone()
    except sqlite3.Error as error:
        raise SQLiteMigrationError(
            "Could not read the execution evidence schema version."
        ) from error

    if row is None:
        return 0

    return int(row["version"])


def _apply_migration(
    connection: sqlite3.Connection,
    migration: SQLiteMigration,
) -> None:
    escaped_name = migration.name.replace(
        "'",
        "''",
    )

    script = f"""
    BEGIN IMMEDIATE;

    {migration.sql}

    INSERT INTO execution_evidence_schema_migrations (
        version,
        name,
        applied_at
    )
    VALUES (
        {migration.version},
        '{escaped_name}',
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    );

    COMMIT;
    """

    try:
        connection.executescript(script)
    except sqlite3.Error:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass

        raise
