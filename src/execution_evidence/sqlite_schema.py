from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


CURRENT_SQLITE_SCHEMA_VERSION = 14


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



CREATE_PROJECT_FOUNDATION_SQL = """
CREATE TABLE projects (
    project_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (
            status IN (
                'active',
                'archived',
                'deleted'
            )
        ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id)
        REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    UNIQUE (workspace_id, project_id)
);

CREATE INDEX idx_projects_workspace_updated
    ON projects(
        workspace_id,
        updated_at DESC
    );

ALTER TABLE roadmap_registry
ADD COLUMN project_row_id INTEGER
    REFERENCES projects(project_row_id)
    ON DELETE RESTRICT;

ALTER TABLE roadmap_registry
ADD COLUMN roadmap_snapshot_id TEXT;

INSERT INTO projects (
    project_id,
    workspace_id,
    title,
    status,
    created_at,
    updated_at
)
SELECT
    'proj_migrated_' || project_direction_id,
    workspace_id,
    title,
    'active',
    created_at,
    created_at
FROM roadmap_registry;

UPDATE roadmap_registry
SET
    project_row_id = (
        SELECT project.project_row_id
        FROM projects AS project
        WHERE
            project.workspace_id =
                roadmap_registry.workspace_id
            AND project.project_id =
                'proj_migrated_' ||
                roadmap_registry.project_direction_id
    ),
    roadmap_snapshot_id = (
        'snap_migrated_' ||
        project_direction_id
    );

CREATE UNIQUE INDEX
    idx_roadmap_registry_public_snapshot
ON roadmap_registry(
    workspace_id,
    roadmap_snapshot_id
)
WHERE roadmap_snapshot_id IS NOT NULL;

CREATE INDEX
    idx_roadmap_registry_project_created
ON roadmap_registry(
    project_row_id,
    created_at DESC
)
WHERE project_row_id IS NOT NULL;

CREATE TRIGGER
    validate_roadmap_project_scope_insert
BEFORE INSERT ON roadmap_registry
WHEN NEW.project_row_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM projects AS project
            WHERE
                project.project_row_id =
                    NEW.project_row_id
                AND project.workspace_id =
                    NEW.workspace_id
        )
        THEN RAISE(
            ABORT,
            'Roadmap project scope does not match workspace'
        )
    END;
END;

CREATE TRIGGER
    validate_roadmap_project_scope_update
BEFORE UPDATE OF
    workspace_id,
    project_row_id
ON roadmap_registry
WHEN NEW.project_row_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM projects AS project
            WHERE
                project.project_row_id =
                    NEW.project_row_id
                AND project.workspace_id =
                    NEW.workspace_id
        )
        THEN RAISE(
            ABORT,
            'Roadmap project scope does not match workspace'
        )
    END;
END;
"""


PERSIST_DURABLE_ATTRIBUTION_IDENTITIES_SQL = """
ALTER TABLE evidence_attributions
ADD COLUMN project_id TEXT;

ALTER TABLE evidence_attributions
ADD COLUMN roadmap_snapshot_id TEXT;

UPDATE evidence_attributions
SET
    project_id = (
        SELECT project.project_id
        FROM roadmap_registry AS roadmap
        JOIN projects AS project
            ON project.project_row_id =
                roadmap.project_row_id
        WHERE
            roadmap.roadmap_registry_id =
                evidence_attributions.roadmap_registry_id
    ),
    roadmap_snapshot_id = (
        SELECT roadmap.roadmap_snapshot_id
        FROM roadmap_registry AS roadmap
        WHERE
            roadmap.roadmap_registry_id =
                evidence_attributions.roadmap_registry_id
    )
WHERE roadmap_registry_id IS NOT NULL;

CREATE TEMP TABLE
    durable_attribution_migration_guard (
        invalid_count INTEGER NOT NULL
            CHECK (invalid_count = 0)
    );

INSERT INTO durable_attribution_migration_guard (
    invalid_count
)
SELECT COUNT(*)
FROM evidence_attributions
WHERE
    (
        roadmap_registry_id IS NULL
        AND (
            attribution_id IS NOT NULL
            OR project_id IS NOT NULL
            OR roadmap_snapshot_id IS NOT NULL
            OR project_direction_id IS NOT NULL
        )
    )
    OR
    (
        roadmap_registry_id IS NOT NULL
        AND (
            attribution_id IS NULL
            OR project_id IS NULL
            OR roadmap_snapshot_id IS NULL
            OR project_direction_id IS NULL
            OR NOT EXISTS (
                SELECT 1
                FROM roadmap_registry AS roadmap
                JOIN projects AS project
                    ON project.project_row_id =
                        roadmap.project_row_id
                WHERE
                    roadmap.roadmap_registry_id =
                        evidence_attributions
                        .roadmap_registry_id
                    AND roadmap.project_direction_id =
                        evidence_attributions
                        .project_direction_id
                    AND roadmap.roadmap_snapshot_id =
                        evidence_attributions
                        .roadmap_snapshot_id
                    AND project.project_id =
                        evidence_attributions.project_id
            )
        )
    );

DROP TABLE durable_attribution_migration_guard;

CREATE INDEX
    idx_attributions_durable_snapshot
ON evidence_attributions(
    project_id,
    roadmap_snapshot_id,
    roadmap_node_id,
    status
)
WHERE roadmap_snapshot_id IS NOT NULL;

CREATE TRIGGER
    validate_attribution_identity_set_insert
BEFORE INSERT ON evidence_attributions
BEGIN
    SELECT CASE
        WHEN NOT (
            (
                NEW.attribution_id IS NULL
                AND NEW.roadmap_registry_id IS NULL
                AND NEW.project_id IS NULL
                AND NEW.roadmap_snapshot_id IS NULL
                AND NEW.project_direction_id IS NULL
            )
            OR
            (
                NEW.attribution_id IS NOT NULL
                AND NEW.roadmap_registry_id IS NOT NULL
                AND NEW.project_id IS NOT NULL
                AND NEW.roadmap_snapshot_id IS NOT NULL
                AND NEW.project_direction_id IS NOT NULL
            )
        )
        THEN RAISE(
            ABORT,
            'Attribution roadmap identity must be fully scoped or fully legacy'
        )
    END;
END;

CREATE TRIGGER
    validate_attribution_identity_set_update
BEFORE UPDATE OF
    attribution_id,
    roadmap_registry_id,
    project_id,
    roadmap_snapshot_id,
    project_direction_id
ON evidence_attributions
BEGIN
    SELECT CASE
        WHEN NOT (
            (
                NEW.attribution_id IS NULL
                AND NEW.roadmap_registry_id IS NULL
                AND NEW.project_id IS NULL
                AND NEW.roadmap_snapshot_id IS NULL
                AND NEW.project_direction_id IS NULL
            )
            OR
            (
                NEW.attribution_id IS NOT NULL
                AND NEW.roadmap_registry_id IS NOT NULL
                AND NEW.project_id IS NOT NULL
                AND NEW.roadmap_snapshot_id IS NOT NULL
                AND NEW.project_direction_id IS NOT NULL
            )
        )
        THEN RAISE(
            ABORT,
            'Attribution roadmap identity must be fully scoped or fully legacy'
        )
    END;
END;

CREATE TRIGGER
    validate_attribution_durable_identity_insert
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
            JOIN projects AS project
                ON project.project_row_id =
                    roadmap.project_row_id
            WHERE
                repository.repository_id =
                    NEW.repository_id
                AND repository.workspace_id =
                    roadmap.workspace_id
                AND roadmap.project_direction_id =
                    NEW.project_direction_id
                AND roadmap.roadmap_snapshot_id =
                    NEW.roadmap_snapshot_id
                AND project.project_id =
                    NEW.project_id
        )
        THEN RAISE(
            ABORT,
            'Attribution durable identity does not match trusted roadmap'
        )
    END;
END;

CREATE TRIGGER
    validate_attribution_durable_identity_update
BEFORE UPDATE OF
    repository_id,
    roadmap_registry_id,
    project_id,
    roadmap_snapshot_id,
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
            JOIN projects AS project
                ON project.project_row_id =
                    roadmap.project_row_id
            WHERE
                repository.repository_id =
                    NEW.repository_id
                AND repository.workspace_id =
                    roadmap.workspace_id
                AND roadmap.project_direction_id =
                    NEW.project_direction_id
                AND roadmap.roadmap_snapshot_id =
                    NEW.roadmap_snapshot_id
                AND project.project_id =
                    NEW.project_id
        )
        THEN RAISE(
            ABORT,
            'Attribution durable identity does not match trusted roadmap'
        )
    END;
END;
"""


ADD_PROJECT_LIFECYCLE_REVISION_SQL = """
ALTER TABLE projects
ADD COLUMN revision INTEGER NOT NULL DEFAULT 0
    CHECK (revision >= 0);
"""


CREATE_PROJECT_STATUS_TRANSITIONS_SQL = """
CREATE TABLE project_status_transitions (
    transition_id TEXT PRIMARY KEY,
    project_row_id INTEGER NOT NULL,
    workspace_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    previous_status TEXT NOT NULL
        CHECK (
            previous_status IN (
                'active',
                'archived',
                'deleted'
            )
        ),
    new_status TEXT NOT NULL
        CHECK (
            new_status IN (
                'active',
                'archived',
                'deleted'
            )
        ),
    changed_at TEXT NOT NULL,
    reason TEXT,
    FOREIGN KEY (project_row_id)
        REFERENCES projects(project_row_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id)
        REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    CHECK (previous_status <> new_status)
);

CREATE INDEX idx_project_status_transitions_project
ON project_status_transitions(
    project_row_id,
    changed_at DESC
);

CREATE INDEX idx_project_status_transitions_public
ON project_status_transitions(
    workspace_id,
    project_id,
    changed_at DESC
);

CREATE TRIGGER validate_project_status_transition_scope_insert
BEFORE INSERT ON project_status_transitions
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM projects AS project
            WHERE
                project.project_row_id =
                    NEW.project_row_id
                AND project.workspace_id =
                    NEW.workspace_id
                AND project.project_id =
                    NEW.project_id
        )
        THEN RAISE(
            ABORT,
            'Project status transition scope is invalid'
        )
    END;
END;
"""


MAKE_DURABLE_ATTRIBUTION_IDENTITY_CANONICAL_SQL = """
CREATE TEMP TABLE durable_attribution_identity_guard (
    invalid_count INTEGER NOT NULL
        CHECK (invalid_count = 0)
);

INSERT INTO durable_attribution_identity_guard (
    invalid_count
)
SELECT COUNT(*)
FROM (
    SELECT
        repository_id,
        project_id,
        roadmap_snapshot_id,
        evidence_key,
        roadmap_node_id
    FROM evidence_attributions
    WHERE
        project_id IS NOT NULL
        AND roadmap_snapshot_id IS NOT NULL
    GROUP BY
        repository_id,
        project_id,
        roadmap_snapshot_id,
        evidence_key,
        roadmap_node_id
    HAVING COUNT(*) > 1
);

DROP TABLE durable_attribution_identity_guard;

DROP INDEX idx_attributions_scoped_identity;
DROP INDEX idx_attributions_repository_stage;
DROP INDEX idx_attributions_evidence;
DROP INDEX idx_attributions_durable_snapshot;

CREATE UNIQUE INDEX
    idx_attributions_scoped_identity
ON evidence_attributions(
    repository_id,
    project_id,
    roadmap_snapshot_id,
    evidence_key,
    roadmap_node_id
)
WHERE
    project_id IS NOT NULL
    AND roadmap_snapshot_id IS NOT NULL;

CREATE INDEX idx_attributions_repository_stage
ON evidence_attributions(
    repository_id,
    project_id,
    roadmap_snapshot_id,
    roadmap_node_id,
    status
)
WHERE
    project_id IS NOT NULL
    AND roadmap_snapshot_id IS NOT NULL;

CREATE INDEX idx_attributions_evidence
ON evidence_attributions(
    repository_id,
    project_id,
    roadmap_snapshot_id,
    evidence_key
)
WHERE
    project_id IS NOT NULL
    AND roadmap_snapshot_id IS NOT NULL;

CREATE INDEX idx_attributions_durable_snapshot
ON evidence_attributions(
    project_id,
    roadmap_snapshot_id,
    roadmap_node_id,
    status
)
WHERE
    project_id IS NOT NULL
    AND roadmap_snapshot_id IS NOT NULL;
"""


CREATE_PROJECT_EXECUTION_EVENTS_SQL = """
CREATE TABLE project_execution_events (
    execution_event_row_id INTEGER
        PRIMARY KEY AUTOINCREMENT,
    execution_event_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    project_row_id INTEGER NOT NULL,
    project_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    actor_id TEXT,
    ingested_by_id TEXT,
    source_provider TEXT NOT NULL,
    source_account_id TEXT,
    external_resource_id TEXT,
    external_entity_type TEXT,
    external_entity_id TEXT,
    provider_idempotency_key TEXT,
    client_idempotency_key TEXT,
    ingestion_method TEXT NOT NULL
        CHECK (
            ingestion_method IN (
                'manual',
                'api',
                'webhook',
                'import',
                'system'
            )
        ),
    source_payload_hash TEXT,
    verified_at TEXT,
    visibility TEXT NOT NULL DEFAULT 'private'
        CHECK (
            visibility IN (
                'private',
                'project',
                'shareable',
                'public'
            )
        ),
    payload_json TEXT NOT NULL,
    event_fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id)
        REFERENCES workspaces(workspace_id)
        ON DELETE CASCADE,
    FOREIGN KEY (project_row_id)
        REFERENCES projects(project_row_id)
        ON DELETE RESTRICT,
    UNIQUE (
        workspace_id,
        execution_event_id
    ),
    CHECK (
        provider_idempotency_key IS NOT NULL
        OR client_idempotency_key IS NOT NULL
    )
);

CREATE UNIQUE INDEX
    idx_project_execution_events_provider_replay
ON project_execution_events(
    workspace_id,
    provider_idempotency_key
)
WHERE provider_idempotency_key IS NOT NULL;

CREATE UNIQUE INDEX
    idx_project_execution_events_client_replay
ON project_execution_events(
    workspace_id,
    client_idempotency_key
)
WHERE client_idempotency_key IS NOT NULL;

CREATE INDEX idx_project_execution_events_timeline
ON project_execution_events(
    workspace_id,
    project_id,
    occurred_at DESC,
    recorded_at DESC,
    execution_event_id DESC
);

CREATE INDEX idx_project_execution_events_actor
ON project_execution_events(
    workspace_id,
    actor_id,
    occurred_at DESC
)
WHERE actor_id IS NOT NULL;

CREATE TRIGGER validate_project_execution_event_scope_insert
BEFORE INSERT ON project_execution_events
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM projects AS project
            WHERE
                project.project_row_id =
                    NEW.project_row_id
                AND project.workspace_id =
                    NEW.workspace_id
                AND project.project_id =
                    NEW.project_id
        )
        THEN RAISE(
            ABORT,
            'Execution event project scope is invalid'
        )
    END;
END;

CREATE TRIGGER prevent_project_execution_event_update
BEFORE UPDATE ON project_execution_events
BEGIN
    SELECT RAISE(
        ABORT,
        'Execution events are immutable'
    );
END;

CREATE TRIGGER prevent_project_execution_event_delete
BEFORE DELETE ON project_execution_events
BEGIN
    SELECT RAISE(
        ABORT,
        'Execution events are immutable'
    );
END;
"""


ADD_EXECUTION_EVENT_SUPERSESSION_SQL = """
ALTER TABLE project_execution_events
ADD COLUMN supersedes_execution_event_id TEXT;

CREATE INDEX idx_project_execution_events_supersedes
ON project_execution_events (
    workspace_id,
    supersedes_execution_event_id
)
WHERE supersedes_execution_event_id IS NOT NULL;
"""


ADD_EXECUTION_EVENT_LINEAGE_ORDER_INDEX_SQL = """
CREATE INDEX
    idx_project_execution_events_lineage_order
ON project_execution_events(
    workspace_id,
    project_row_id,
    execution_event_row_id
);
"""


ADD_TRUSTED_RECEIPT_LINEAGE_FOUNDATION_SQL = """
ALTER TABLE execution_evidence_import_receipts
ADD COLUMN receipt_version INTEGER NOT NULL DEFAULT 1
    CHECK (receipt_version IN (1, 2));

ALTER TABLE execution_evidence_import_receipts
ADD COLUMN receipt_kind TEXT
    CHECK (
        receipt_kind IS NULL
        OR receipt_kind IN (
            'root',
            'sqlite_upgrade',
            'epoch_boundary'
        )
    );

ALTER TABLE execution_evidence_import_receipts
ADD COLUMN predecessor_receipt_id TEXT;

ALTER TABLE execution_evidence_import_receipts
ADD COLUMN schema_version_from INTEGER
    CHECK (
        schema_version_from IS NULL
        OR schema_version_from >= 0
    );

ALTER TABLE execution_evidence_import_receipts
ADD COLUMN schema_version_to INTEGER
    CHECK (
        schema_version_to IS NULL
        OR schema_version_to >= 0
    );

ALTER TABLE execution_evidence_import_receipts
ADD COLUMN lineage_epoch INTEGER
    CHECK (
        lineage_epoch IS NULL
        OR lineage_epoch >= 0
    );

CREATE UNIQUE INDEX
    idx_import_receipts_unique_successor
ON execution_evidence_import_receipts(
    predecessor_receipt_id
)
WHERE predecessor_receipt_id IS NOT NULL;

CREATE UNIQUE INDEX
    idx_import_receipts_unique_epoch_origin
ON execution_evidence_import_receipts(
    lineage_epoch
)
WHERE
    receipt_version = 2
    AND receipt_kind IN (
        'root',
        'epoch_boundary'
    )
    AND lineage_epoch IS NOT NULL;

CREATE INDEX
    idx_import_receipts_lineage_tip
ON execution_evidence_import_receipts(
    lineage_epoch,
    schema_version_to,
    receipt_id
)
WHERE receipt_version = 2;

CREATE TRIGGER
    trg_import_receipts_v2_structure_insert
BEFORE INSERT ON execution_evidence_import_receipts
WHEN
    NEW.receipt_version = 2
    AND (
        NEW.receipt_kind IS NULL
        OR NEW.schema_version_to IS NULL
        OR NEW.lineage_epoch IS NULL
        OR NEW.lineage_epoch < 1
        OR (
            NEW.receipt_kind = 'root'
            AND (
                NEW.predecessor_receipt_id IS NOT NULL
                OR NEW.schema_version_from IS NOT NULL
            )
        )
        OR (
            NEW.receipt_kind IN (
                'sqlite_upgrade',
                'epoch_boundary'
            )
            AND (
                NEW.predecessor_receipt_id IS NULL
                OR NEW.schema_version_from IS NULL
                OR NEW.schema_version_to
                    <= NEW.schema_version_from
            )
        )
    )
BEGIN
    SELECT RAISE(
        ABORT,
        'Receipt version 2 lineage fields are invalid'
    );
END;

CREATE TRIGGER
    trg_import_receipts_v2_predecessor_insert
BEFORE INSERT ON execution_evidence_import_receipts
WHEN
    NEW.receipt_version = 2
    AND NEW.predecessor_receipt_id IS NOT NULL
    AND NOT EXISTS (
        SELECT 1
        FROM execution_evidence_import_receipts
        WHERE receipt_id =
            NEW.predecessor_receipt_id
    )
BEGIN
    SELECT RAISE(
        ABORT,
        'Receipt predecessor does not exist'
    );
END;

CREATE TRIGGER
    trg_import_receipts_lineage_immutable
BEFORE UPDATE
ON execution_evidence_import_receipts
WHEN
    OLD.receipt_version = 2
    OR NEW.receipt_version = 2
    OR EXISTS (
        SELECT 1
        FROM execution_evidence_import_receipts
        WHERE predecessor_receipt_id =
            OLD.receipt_id
    )
BEGIN
    SELECT RAISE(
        ABORT,
        'Receipt lineage rows are immutable'
    );
END;

CREATE TRIGGER
    trg_import_receipts_delete_protection
BEFORE DELETE
ON execution_evidence_import_receipts
WHEN
    OLD.receipt_version = 2
    OR EXISTS (
        SELECT 1
        FROM execution_evidence_import_receipts
        WHERE predecessor_receipt_id =
            OLD.receipt_id
    )
BEGIN
    SELECT RAISE(
        ABORT,
        'Receipt lineage rows cannot be deleted'
    );
END;

PRAGMA user_version = 14;
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
    SQLiteMigration(
        version=6,
        name="create_durable_project_foundation",
        sql=CREATE_PROJECT_FOUNDATION_SQL,
    ),
    SQLiteMigration(
        version=7,
        name="persist_durable_attribution_identities",
        sql=(
            PERSIST_DURABLE_ATTRIBUTION_IDENTITIES_SQL
        ),
    ),
    SQLiteMigration(
        version=8,
        name="make_durable_attribution_identity_canonical",
        sql=(
            MAKE_DURABLE_ATTRIBUTION_IDENTITY_CANONICAL_SQL
        ),
    ),
    SQLiteMigration(
        version=9,
        name="create_project_status_transition_audit",
        sql=CREATE_PROJECT_STATUS_TRANSITIONS_SQL,
    ),
    SQLiteMigration(
        version=10,
        name="add_project_lifecycle_revision",
        sql=ADD_PROJECT_LIFECYCLE_REVISION_SQL,
    ),
    SQLiteMigration(
        version=11,
        name="create_project_execution_event_stream",
        sql=CREATE_PROJECT_EXECUTION_EVENTS_SQL,
    ),
    SQLiteMigration(
        version=12,
        name="add_execution_event_supersession",
        sql=ADD_EXECUTION_EVENT_SUPERSESSION_SQL,
    ),
    SQLiteMigration(
        version=13,
        name="add_execution_event_lineage_order_index",
        sql=(
            ADD_EXECUTION_EVENT_LINEAGE_ORDER_INDEX_SQL
        ),
    ),
    SQLiteMigration(
        version=14,
        name="add_trusted_receipt_lineage_foundation",
        sql=(
            ADD_TRUSTED_RECEIPT_LINEAGE_FOUNDATION_SQL
        ),
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
