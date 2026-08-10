from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


CURRENT_SQLITE_SCHEMA_VERSION = 23


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


CREATE_PRINCIPAL_FOUNDATION_SQL = """
CREATE TABLE principal_kinds (
    principal_kind TEXT PRIMARY KEY
);

INSERT INTO principal_kinds (
    principal_kind
)
VALUES
    ('human'),
    ('service'),
    ('system'),
    ('agent');

CREATE TABLE principals (
    principal_row_id INTEGER
        PRIMARY KEY AUTOINCREMENT,
    principal_id TEXT NOT NULL UNIQUE,
    principal_kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (
            status IN (
                'active',
                'suspended',
                'deactivated'
            )
        ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (principal_kind)
        REFERENCES principal_kinds(principal_kind)
        ON DELETE RESTRICT
);

PRAGMA user_version = 15;
"""


CREATE_WORKSPACE_MEMBERSHIP_FOUNDATION_SQL = """
CREATE TABLE workspace_memberships (
    membership_row_id INTEGER
        PRIMARY KEY AUTOINCREMENT,
    membership_id TEXT NOT NULL UNIQUE,
    workspace_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (
            status IN (
                'active',
                'suspended',
                'removed'
            )
        ),
    revision INTEGER NOT NULL DEFAULT 0
        CHECK (revision >= 0),
    created_by_principal_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status_changed_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id)
        REFERENCES workspaces(workspace_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (principal_id)
        REFERENCES principals(principal_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (created_by_principal_id)
        REFERENCES principals(principal_id)
        ON DELETE RESTRICT
);

CREATE UNIQUE INDEX
    idx_workspace_memberships_current
ON workspace_memberships(
    workspace_id,
    principal_id
)
WHERE status != 'removed';

CREATE INDEX
    idx_workspace_memberships_principal
ON workspace_memberships(
    principal_id,
    workspace_id,
    status
);

CREATE TABLE workspace_membership_status_transitions (
    transition_id TEXT PRIMARY KEY,
    membership_row_id INTEGER NOT NULL,
    membership_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    previous_status TEXT
        CHECK (
            previous_status IS NULL
            OR previous_status IN (
                'active',
                'suspended',
                'removed'
            )
        ),
    new_status TEXT NOT NULL
        CHECK (
            new_status IN (
                'active',
                'suspended',
                'removed'
            )
        ),
    previous_revision INTEGER
        CHECK (
            previous_revision IS NULL
            OR previous_revision >= 0
        ),
    resulting_revision INTEGER NOT NULL
        CHECK (resulting_revision >= 0),
    changed_at TEXT NOT NULL,
    reason TEXT,
    FOREIGN KEY (membership_row_id)
        REFERENCES workspace_memberships(
            membership_row_id
        )
        ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id)
        REFERENCES workspaces(workspace_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (principal_id)
        REFERENCES principals(principal_id)
        ON DELETE RESTRICT,
    UNIQUE (
        membership_row_id,
        resulting_revision
    ),
    CHECK (
        (
            previous_status IS NULL
            AND previous_revision IS NULL
            AND new_status = 'active'
            AND resulting_revision = 0
        )
        OR
        (
            previous_status IS NOT NULL
            AND previous_revision IS NOT NULL
            AND previous_status <> new_status
            AND resulting_revision =
                previous_revision + 1
        )
    )
);

CREATE INDEX
    idx_workspace_membership_transitions_history
ON workspace_membership_status_transitions(
    membership_row_id,
    resulting_revision ASC
);

CREATE TRIGGER
    validate_workspace_membership_initial_state
BEFORE INSERT
ON workspace_memberships
BEGIN
    SELECT CASE
        WHEN
            NEW.status <> 'active'
            OR NEW.revision <> 0
            OR NEW.updated_at <> NEW.created_at
            OR NEW.status_changed_at <> NEW.created_at
        THEN RAISE(
            ABORT,
            'Workspace memberships must begin active at revision zero'
        )
    END;
END;

CREATE TRIGGER
    create_workspace_membership_genesis_transition
AFTER INSERT
ON workspace_memberships
BEGIN
    INSERT INTO workspace_membership_status_transitions (
        transition_id,
        membership_row_id,
        membership_id,
        workspace_id,
        principal_id,
        previous_status,
        new_status,
        previous_revision,
        resulting_revision,
        changed_at,
        reason
    )
    VALUES (
        'wmt_genesis_' || NEW.membership_id,
        NEW.membership_row_id,
        NEW.membership_id,
        NEW.workspace_id,
        NEW.principal_id,
        NULL,
        'active',
        NULL,
        0,
        NEW.created_at,
        NULL
    );
END;

CREATE TRIGGER
    validate_workspace_membership_transition_insert
BEFORE INSERT
ON workspace_membership_status_transitions
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM workspace_memberships AS membership
            WHERE
                membership.membership_row_id =
                    NEW.membership_row_id
                AND membership.membership_id =
                    NEW.membership_id
                AND membership.workspace_id =
                    NEW.workspace_id
                AND membership.principal_id =
                    NEW.principal_id
        )
        THEN RAISE(
            ABORT,
            'Workspace membership transition scope is invalid'
        )
    END;

    SELECT CASE
        WHEN
            NEW.previous_status IS NULL
            AND NOT EXISTS (
                SELECT 1
                FROM workspace_memberships AS membership
                WHERE
                    membership.membership_row_id =
                        NEW.membership_row_id
                    AND membership.status = 'active'
                    AND membership.revision = 0
                    AND NEW.new_status = 'active'
                    AND NEW.previous_revision IS NULL
                    AND NEW.resulting_revision = 0
                    AND NEW.changed_at =
                        membership.created_at
            )
        THEN RAISE(
            ABORT,
            'Workspace membership genesis transition is invalid'
        )
    END;

    SELECT CASE
        WHEN
            NEW.previous_status IS NOT NULL
            AND NOT EXISTS (
                SELECT 1
                FROM workspace_memberships AS membership
                WHERE
                    membership.membership_row_id =
                        NEW.membership_row_id
                    AND membership.status =
                        NEW.previous_status
                    AND membership.revision =
                        NEW.previous_revision
            )
        THEN RAISE(
            ABORT,
            'Workspace membership transition does not match current state'
        )
    END;

    SELECT CASE
        WHEN
            NEW.previous_status IS NOT NULL
            AND NOT (
                (
                    NEW.previous_status = 'active'
                    AND NEW.new_status IN (
                        'suspended',
                        'removed'
                    )
                )
                OR
                (
                    NEW.previous_status = 'suspended'
                    AND NEW.new_status IN (
                        'active',
                        'removed'
                    )
                )
            )
        THEN RAISE(
            ABORT,
            'Workspace membership status transition is invalid'
        )
    END;
END;

CREATE TRIGGER
    apply_workspace_membership_transition
AFTER INSERT
ON workspace_membership_status_transitions
WHEN NEW.previous_status IS NOT NULL
BEGIN
    UPDATE workspace_memberships
    SET
        status = NEW.new_status,
        revision = NEW.resulting_revision,
        updated_at = NEW.changed_at,
        status_changed_at = NEW.changed_at
    WHERE membership_row_id = NEW.membership_row_id;
END;

CREATE TRIGGER
    validate_workspace_membership_state_update
BEFORE UPDATE OF
    status,
    revision,
    updated_at,
    status_changed_at
ON workspace_memberships
WHEN
    OLD.status <> NEW.status
    OR OLD.revision <> NEW.revision
    OR OLD.updated_at <> NEW.updated_at
    OR OLD.status_changed_at <> NEW.status_changed_at
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM workspace_membership_status_transitions
                AS transition
            WHERE
                transition.membership_row_id =
                    OLD.membership_row_id
                AND transition.previous_status =
                    OLD.status
                AND transition.new_status =
                    NEW.status
                AND transition.previous_revision =
                    OLD.revision
                AND transition.resulting_revision =
                    NEW.revision
                AND transition.changed_at =
                    NEW.status_changed_at
                AND transition.changed_at =
                    NEW.updated_at
        )
        THEN RAISE(
            ABORT,
            'Workspace membership state changes require an authoritative transition'
        )
    END;
END;

CREATE TRIGGER
    prevent_workspace_membership_identity_update
BEFORE UPDATE OF
    membership_id,
    workspace_id,
    principal_id,
    created_by_principal_id,
    created_at
ON workspace_memberships
BEGIN
    SELECT RAISE(
        ABORT,
        'Workspace membership identity fields are immutable'
    );
END;

CREATE TRIGGER
    prevent_removed_workspace_membership_reactivation
BEFORE UPDATE OF
    status,
    revision,
    updated_at,
    status_changed_at
ON workspace_memberships
WHEN OLD.status = 'removed'
BEGIN
    SELECT RAISE(
        ABORT,
        'Removed workspace memberships are terminal'
    );
END;

CREATE TRIGGER
    prevent_workspace_membership_delete
BEFORE DELETE
ON workspace_memberships
BEGIN
    SELECT RAISE(
        ABORT,
        'Workspace memberships cannot be deleted'
    );
END;

CREATE TRIGGER
    prevent_workspace_membership_transition_update
BEFORE UPDATE
ON workspace_membership_status_transitions
BEGIN
    SELECT RAISE(
        ABORT,
        'Workspace membership transitions are immutable'
    );
END;

CREATE TRIGGER
    prevent_workspace_membership_transition_delete
BEFORE DELETE
ON workspace_membership_status_transitions
BEGIN
    SELECT RAISE(
        ABORT,
        'Workspace membership transitions cannot be deleted'
    );
END;

PRAGMA user_version = 16;
"""


ADD_WORKSPACE_MEMBERSHIP_ROLE_FOUNDATION_SQL = """
ALTER TABLE workspace_memberships
ADD COLUMN role TEXT
    CHECK (
        role IS NULL
        OR role IN (
            'owner',
            'admin',
            'member',
            'viewer'
        )
    );

CREATE TABLE workspace_membership_role_transitions (
    role_transition_id TEXT PRIMARY KEY,
    membership_row_id INTEGER NOT NULL,
    membership_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    previous_role TEXT
        CHECK (
            previous_role IS NULL
            OR previous_role IN (
                'owner',
                'admin',
                'member',
                'viewer'
            )
        ),
    new_role TEXT NOT NULL
        CHECK (
            new_role IN (
                'owner',
                'admin',
                'member',
                'viewer'
            )
        ),
    previous_revision INTEGER NOT NULL
        CHECK (previous_revision >= 0),
    resulting_revision INTEGER NOT NULL
        CHECK (resulting_revision >= 1),
    changed_at TEXT NOT NULL,
    changed_by_principal_id TEXT,
    reason TEXT,
    FOREIGN KEY (membership_row_id)
        REFERENCES workspace_memberships(
            membership_row_id
        )
        ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id)
        REFERENCES workspaces(workspace_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (principal_id)
        REFERENCES principals(principal_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (changed_by_principal_id)
        REFERENCES principals(principal_id)
        ON DELETE RESTRICT,
    UNIQUE (
        membership_row_id,
        resulting_revision
    ),
    CHECK (
        previous_role IS NOT new_role
        AND resulting_revision =
            previous_revision + 1
    )
);

CREATE INDEX
    idx_workspace_membership_role_history
ON workspace_membership_role_transitions(
    membership_row_id,
    resulting_revision ASC
);

CREATE TRIGGER
    validate_workspace_membership_role_transition_insert
BEFORE INSERT
ON workspace_membership_role_transitions
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM workspace_memberships AS membership
            WHERE
                membership.membership_row_id =
                    NEW.membership_row_id
                AND membership.membership_id =
                    NEW.membership_id
                AND membership.workspace_id =
                    NEW.workspace_id
                AND membership.principal_id =
                    NEW.principal_id
                AND membership.role IS NEW.previous_role
                AND membership.revision =
                    NEW.previous_revision
        )
        THEN RAISE(
            ABORT,
            'Workspace membership role transition does not match current state'
        )
    END;

    SELECT CASE
        WHEN EXISTS (
            SELECT 1
            FROM workspace_membership_status_transitions
                AS status_transition
            WHERE
                status_transition.membership_row_id =
                    NEW.membership_row_id
                AND status_transition.resulting_revision =
                    NEW.resulting_revision
        )
        THEN RAISE(
            ABORT,
            'Workspace membership revision is already consumed by a status transition'
        )
    END;
END;

CREATE TRIGGER
    prevent_status_transition_role_revision_collision
BEFORE INSERT
ON workspace_membership_status_transitions
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1
            FROM workspace_membership_role_transitions
                AS role_transition
            WHERE
                role_transition.membership_row_id =
                    NEW.membership_row_id
                AND role_transition.resulting_revision =
                    NEW.resulting_revision
        )
        THEN RAISE(
            ABORT,
            'Workspace membership revision is already consumed by a role transition'
        )
    END;
END;

DROP TRIGGER
    validate_workspace_membership_initial_state;

CREATE TRIGGER
    validate_workspace_membership_initial_state
BEFORE INSERT
ON workspace_memberships
BEGIN
    SELECT CASE
        WHEN
            NEW.status <> 'active'
            OR NEW.role IS NOT NULL
            OR NEW.revision <> 0
            OR NEW.updated_at <> NEW.created_at
            OR NEW.status_changed_at <> NEW.created_at
        THEN RAISE(
            ABORT,
            'Workspace memberships must begin active, unassigned, and at revision zero'
        )
    END;
END;

DROP TRIGGER
    validate_workspace_membership_state_update;

CREATE TRIGGER
    validate_workspace_membership_state_update
BEFORE UPDATE OF
    status,
    role,
    revision,
    updated_at,
    status_changed_at
ON workspace_memberships
WHEN
    OLD.status IS NOT NEW.status
    OR OLD.role IS NOT NEW.role
    OR OLD.revision <> NEW.revision
    OR OLD.updated_at <> NEW.updated_at
    OR OLD.status_changed_at <> NEW.status_changed_at
BEGIN
    SELECT CASE
        WHEN OLD.status = 'removed'
        THEN RAISE(
            ABORT,
            'Removed workspace memberships are terminal'
        )
    END;

    SELECT CASE
        WHEN
            OLD.status IS NOT NEW.status
            AND OLD.role IS NOT NEW.role
        THEN RAISE(
            ABORT,
            'Workspace membership status and role cannot change in one mutation'
        )
    END;

    SELECT CASE
        WHEN
            OLD.status IS NEW.status
            AND OLD.role IS NEW.role
        THEN RAISE(
            ABORT,
            'Workspace membership revision changes require a status or role transition'
        )
    END;

    SELECT CASE
        WHEN
            OLD.status IS NOT NEW.status
            AND NOT EXISTS (
                SELECT 1
                FROM workspace_membership_status_transitions
                    AS transition
                WHERE
                    transition.membership_row_id =
                        OLD.membership_row_id
                    AND transition.previous_status =
                        OLD.status
                    AND transition.new_status =
                        NEW.status
                    AND transition.previous_revision =
                        OLD.revision
                    AND transition.resulting_revision =
                        NEW.revision
                    AND transition.changed_at =
                        NEW.status_changed_at
                    AND transition.changed_at =
                        NEW.updated_at
                    AND OLD.role IS NEW.role
            )
        THEN RAISE(
            ABORT,
            'Workspace membership status changes require an authoritative transition'
        )
    END;

    SELECT CASE
        WHEN
            OLD.role IS NOT NEW.role
            AND NOT EXISTS (
                SELECT 1
                FROM workspace_membership_role_transitions
                    AS transition
                WHERE
                    transition.membership_row_id =
                        OLD.membership_row_id
                    AND transition.previous_role
                        IS OLD.role
                    AND transition.new_role
                        IS NEW.role
                    AND transition.previous_revision =
                        OLD.revision
                    AND transition.resulting_revision =
                        NEW.revision
                    AND transition.changed_at =
                        NEW.updated_at
                    AND OLD.status IS NEW.status
                    AND OLD.status_changed_at =
                        NEW.status_changed_at
            )
        THEN RAISE(
            ABORT,
            'Workspace membership role changes require an authoritative transition'
        )
    END;
END;

CREATE TRIGGER
    apply_workspace_membership_role_transition
AFTER INSERT
ON workspace_membership_role_transitions
BEGIN
    UPDATE workspace_memberships
    SET
        role = NEW.new_role,
        revision = NEW.resulting_revision,
        updated_at = NEW.changed_at
    WHERE
        membership_row_id =
            NEW.membership_row_id;
END;

CREATE TRIGGER
    prevent_workspace_membership_role_transition_update
BEFORE UPDATE
ON workspace_membership_role_transitions
BEGIN
    SELECT RAISE(
        ABORT,
        'Workspace membership role transitions are immutable'
    );
END;

CREATE TRIGGER
    prevent_workspace_membership_role_transition_delete
BEFORE DELETE
ON workspace_membership_role_transitions
BEGIN
    SELECT RAISE(
        ABORT,
        'Workspace membership role transitions cannot be deleted'
    );
END;

PRAGMA user_version = 20;
"""


ADD_WORKSPACE_MEMBERSHIP_STATUS_ACTOR_SQL = """
ALTER TABLE workspace_membership_status_transitions
ADD COLUMN changed_by_principal_id TEXT
    REFERENCES principals(principal_id)
    ON DELETE RESTRICT;

PRAGMA user_version = 21;
"""


CLASSIFY_WORKSPACE_KIND_SQL = """
ALTER TABLE workspaces
ADD COLUMN workspace_kind TEXT NOT NULL
    DEFAULT 'internal'
    CHECK (
        workspace_kind IN (
            'internal',
            'provisioned'
        )
    );

PRAGMA user_version = 22;
"""


CREATE_WORKSPACE_PROVISIONING_IDEMPOTENCY_SQL = """
CREATE TABLE workspace_provisioning_idempotency (
    provisioning_idempotency_row_id INTEGER
        PRIMARY KEY AUTOINCREMENT,
    principal_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    operation TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    workspace_id TEXT NOT NULL UNIQUE,
    membership_id TEXT NOT NULL UNIQUE,
    owner_role_transition_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    FOREIGN KEY (principal_id)
        REFERENCES principals(principal_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id)
        REFERENCES workspaces(workspace_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (membership_id)
        REFERENCES workspace_memberships(
            membership_id
        )
        ON DELETE RESTRICT,
    FOREIGN KEY (owner_role_transition_id)
        REFERENCES workspace_membership_role_transitions(
            role_transition_id
        )
        ON DELETE RESTRICT,
    UNIQUE (
        principal_id,
        idempotency_key
    ),
    CHECK (
        length(idempotency_key) >= 1
        AND length(idempotency_key) <= 255
    ),
    CHECK (
        length(operation) >= 1
    ),
    CHECK (
        length(request_fingerprint) = 64
        AND request_fingerprint
            NOT GLOB '*[^0-9a-f]*'
    )
);

CREATE INDEX
    idx_workspace_provisioning_idempotency_workspace
ON workspace_provisioning_idempotency(
    workspace_id
);

CREATE TRIGGER
    prevent_workspace_provisioning_idempotency_update
BEFORE UPDATE
ON workspace_provisioning_idempotency
BEGIN
    SELECT RAISE(
        ABORT,
        'Workspace provisioning idempotency records are immutable'
    );
END;

CREATE TRIGGER
    prevent_workspace_provisioning_idempotency_delete
BEFORE DELETE
ON workspace_provisioning_idempotency
BEGIN
    SELECT RAISE(
        ABORT,
        'Workspace provisioning idempotency records cannot be deleted'
    );
END;

PRAGMA user_version = 23;
"""


CREATE_PRINCIPAL_IDENTITY_FOUNDATION_SQL = """
CREATE TABLE identity_providers (
    identity_provider_row_id INTEGER
        PRIMARY KEY AUTOINCREMENT,
    identity_provider_id TEXT NOT NULL UNIQUE,
    provider_kind TEXT NOT NULL
        CHECK (
            provider_kind IN (
                'google',
                'github',
                'microsoft',
                'oidc',
                'saml'
            )
        ),
    issuer TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (
            status IN (
                'active',
                'disabled'
            )
        ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (
        identity_provider_id,
        issuer
    )
);

CREATE TABLE principal_identity_links (
    identity_link_row_id INTEGER
        PRIMARY KEY AUTOINCREMENT,
    link_id TEXT NOT NULL UNIQUE,
    identity_provider_id TEXT NOT NULL,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (
            status IN (
                'active',
                'ended'
            )
        ),
    linked_at TEXT NOT NULL,
    ended_at TEXT,
    end_reason TEXT,
    ended_by_principal_id TEXT,
    severed_at TEXT,
    severed_reason TEXT,
    severed_by_principal_id TEXT,
    FOREIGN KEY (
        identity_provider_id,
        issuer
    )
        REFERENCES identity_providers(
            identity_provider_id,
            issuer
        )
        ON DELETE RESTRICT,
    FOREIGN KEY (principal_id)
        REFERENCES principals(principal_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (ended_by_principal_id)
        REFERENCES principals(principal_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (severed_by_principal_id)
        REFERENCES principals(principal_id)
        ON DELETE RESTRICT,
    CHECK (
        (
            status = 'active'
            AND ended_at IS NULL
            AND end_reason IS NULL
            AND ended_by_principal_id IS NULL
            AND severed_at IS NULL
            AND severed_reason IS NULL
            AND severed_by_principal_id IS NULL
        )
        OR
        (
            status = 'ended'
            AND ended_at IS NOT NULL
            AND end_reason IS NOT NULL
        )
    ),
    CHECK (
        severed_at IS NULL
        OR (
            status = 'ended'
            AND severed_reason IS NOT NULL
        )
    ),
    CHECK (
        severed_at IS NOT NULL
        OR (
            severed_reason IS NULL
            AND severed_by_principal_id IS NULL
        )
    )
);

CREATE UNIQUE INDEX
    idx_principal_identity_links_active
ON principal_identity_links(
    issuer,
    subject
)
WHERE status = 'active';

CREATE INDEX
    idx_principal_identity_links_identity_history
ON principal_identity_links(
    issuer,
    subject
);

CREATE INDEX
    idx_principal_identity_links_principal_status
ON principal_identity_links(
    principal_id,
    status
);

CREATE TRIGGER
    prevent_identity_provider_identity_update
BEFORE UPDATE OF
    identity_provider_id,
    issuer
ON identity_providers
BEGIN
    SELECT RAISE(
        ABORT,
        'Identity provider identity is immutable'
    );
END;

CREATE TRIGGER
    prevent_identity_provider_delete
BEFORE DELETE
ON identity_providers
BEGIN
    SELECT RAISE(
        ABORT,
        'Identity providers cannot be deleted'
    );
END;

CREATE TRIGGER
    enforce_principal_identity_lifetime_ownership
BEFORE INSERT
ON principal_identity_links
WHEN EXISTS (
    SELECT 1
    FROM principal_identity_links
    WHERE
        issuer = NEW.issuer
        AND subject = NEW.subject
        AND principal_id != NEW.principal_id
        AND severed_at IS NULL
)
BEGIN
    SELECT RAISE(
        ABORT,
        'External identity is historically owned by another principal'
    );
END;

CREATE TRIGGER
    require_principal_identity_link_genesis
BEFORE INSERT
ON principal_identity_links
WHEN
    NEW.status != 'active'
    OR NEW.ended_at IS NOT NULL
    OR NEW.end_reason IS NOT NULL
    OR NEW.ended_by_principal_id IS NOT NULL
    OR NEW.severed_at IS NOT NULL
    OR NEW.severed_reason IS NOT NULL
    OR NEW.severed_by_principal_id IS NOT NULL
BEGIN
    SELECT RAISE(
        ABORT,
        'Principal identity links must begin active'
    );
END;

CREATE TRIGGER
    prevent_principal_identity_fields_update
BEFORE UPDATE OF
    link_id,
    identity_provider_id,
    issuer,
    subject,
    principal_id,
    linked_at
ON principal_identity_links
BEGIN
    SELECT RAISE(
        ABORT,
        'Principal identity fields are immutable'
    );
END;

CREATE TRIGGER
    enforce_principal_identity_link_lifecycle
BEFORE UPDATE OF
    status,
    ended_at,
    end_reason,
    ended_by_principal_id,
    severed_at,
    severed_reason,
    severed_by_principal_id
ON principal_identity_links
WHEN
    OLD.status = 'active'
    AND (
        NEW.status != 'ended'
        OR NEW.ended_at IS NULL
        OR NEW.end_reason IS NULL
        OR NEW.severed_at IS NOT NULL
        OR NEW.severed_reason IS NOT NULL
        OR NEW.severed_by_principal_id IS NOT NULL
    )
BEGIN
    SELECT RAISE(
        ABORT,
        'Principal identity links may only end'
    );
END;

CREATE TRIGGER
    prevent_ended_principal_identity_link_update
BEFORE UPDATE
ON principal_identity_links
WHEN OLD.status = 'ended'
BEGIN
    SELECT RAISE(
        ABORT,
        'Ended principal identity links are terminal'
    );
END;

CREATE TRIGGER
    prevent_principal_identity_link_delete
BEFORE DELETE
ON principal_identity_links
BEGIN
    SELECT RAISE(
        ABORT,
        'Principal identity links cannot be deleted'
    );
END;

PRAGMA user_version = 17;
"""


CREATE_GITHUB_SOURCE_BINDING_FOUNDATION_SQL = """
CREATE TABLE github_source_bindings (
    github_source_binding_row_id INTEGER
        PRIMARY KEY AUTOINCREMENT,
    github_source_binding_id TEXT NOT NULL UNIQUE,
    repository_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    installation_id TEXT,
    created_at TEXT NOT NULL,
    retired_at TEXT,
    retired_reason TEXT,
    FOREIGN KEY (workspace_id)
        REFERENCES workspaces(workspace_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (
        workspace_id,
        project_id
    )
        REFERENCES projects(
            workspace_id,
            project_id
        )
        ON DELETE RESTRICT,
    CHECK (
        (
            retired_at IS NULL
            AND retired_reason IS NULL
        )
        OR
        (
            retired_at IS NOT NULL
            AND retired_reason IS NOT NULL
        )
    )
);

CREATE UNIQUE INDEX
    idx_github_source_bindings_current_repository
ON github_source_bindings(
    repository_id
)
WHERE retired_at IS NULL;

CREATE TABLE github_webhook_credentials (
    github_webhook_credential_row_id INTEGER
        PRIMARY KEY AUTOINCREMENT,
    github_webhook_credential_id TEXT
        NOT NULL UNIQUE,
    webhook_endpoint_id TEXT
        NOT NULL UNIQUE,
    installation_id TEXT,
    secret_ref TEXT NOT NULL,
    created_at TEXT NOT NULL,
    retired_at TEXT,
    retired_reason TEXT,
    CHECK (
        length(secret_ref) > 0
    ),
    CHECK (
        (
            retired_at IS NULL
            AND retired_reason IS NULL
        )
        OR
        (
            retired_at IS NOT NULL
            AND retired_reason IS NOT NULL
        )
    )
);

/*
 * secret_ref is deliberately opaque to this schema.
 * It must not encode assumptions about environment
 * variables, Vault, KMS, encrypted rows, or any other
 * future secret-storage implementation.
 */

CREATE TABLE github_webhook_credential_authorities (
    github_webhook_credential_authority_row_id INTEGER
        PRIMARY KEY AUTOINCREMENT,
    github_webhook_credential_authority_id TEXT
        NOT NULL UNIQUE,
    github_webhook_credential_id TEXT NOT NULL,
    repository_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    retired_at TEXT,
    retired_reason TEXT,
    FOREIGN KEY (github_webhook_credential_id)
        REFERENCES github_webhook_credentials(
            github_webhook_credential_id
        )
        ON DELETE RESTRICT,
    CHECK (
        (
            retired_at IS NULL
            AND retired_reason IS NULL
        )
        OR
        (
            retired_at IS NOT NULL
            AND retired_reason IS NOT NULL
        )
    )
);

CREATE UNIQUE INDEX
    idx_github_webhook_authorities_current_pair
ON github_webhook_credential_authorities(
    github_webhook_credential_id,
    repository_id
)
WHERE retired_at IS NULL;

CREATE TRIGGER
    require_github_source_binding_genesis
BEFORE INSERT
ON github_source_bindings
WHEN
    NEW.retired_at IS NOT NULL
    OR NEW.retired_reason IS NOT NULL
BEGIN
    SELECT RAISE(
        ABORT,
        'GitHub source bindings must begin current'
    );
END;

CREATE TRIGGER
    prevent_github_source_binding_update
BEFORE UPDATE
ON github_source_bindings
BEGIN
    /*
     * Retirement is reserved but unreachable in v19.
     * A future privileged retirement operation must
     * preserve repository/workspace/project identity
     * and permit only the first lifecycle transition.
     */
    SELECT RAISE(
        ABORT,
        'GitHub source bindings are immutable'
    );
END;

CREATE TRIGGER
    prevent_github_source_binding_delete
BEFORE DELETE
ON github_source_bindings
BEGIN
    SELECT RAISE(
        ABORT,
        'GitHub source bindings cannot be deleted'
    );
END;

CREATE TRIGGER
    require_github_webhook_credential_genesis
BEFORE INSERT
ON github_webhook_credentials
WHEN
    NEW.retired_at IS NOT NULL
    OR NEW.retired_reason IS NOT NULL
BEGIN
    SELECT RAISE(
        ABORT,
        'GitHub webhook credentials must begin current'
    );
END;

CREATE TRIGGER
    prevent_github_webhook_credential_update
BEFORE UPDATE
ON github_webhook_credentials
BEGIN
    SELECT RAISE(
        ABORT,
        'GitHub webhook credentials are immutable'
    );
END;

CREATE TRIGGER
    prevent_github_webhook_credential_delete
BEFORE DELETE
ON github_webhook_credentials
BEGIN
    SELECT RAISE(
        ABORT,
        'GitHub webhook credentials cannot be deleted'
    );
END;

CREATE TRIGGER
    require_github_webhook_authority_genesis
BEFORE INSERT
ON github_webhook_credential_authorities
WHEN
    NEW.retired_at IS NOT NULL
    OR NEW.retired_reason IS NOT NULL
BEGIN
    SELECT RAISE(
        ABORT,
        'GitHub webhook credential authorities must begin current'
    );
END;

CREATE TRIGGER
    prevent_github_webhook_authority_update
BEFORE UPDATE
ON github_webhook_credential_authorities
BEGIN
    SELECT RAISE(
        ABORT,
        'GitHub webhook credential authorities are immutable'
    );
END;

CREATE TRIGGER
    prevent_github_webhook_authority_delete
BEFORE DELETE
ON github_webhook_credential_authorities
BEGIN
    SELECT RAISE(
        ABORT,
        'GitHub webhook credential authorities cannot be deleted'
    );
END;

PRAGMA user_version = 19;
"""



CREATE_EXECUTION_ACTOR_IDENTITY_NAMESPACE_SQL = """
CREATE TABLE execution_actor_identity_namespaces (
    execution_actor_namespace_row_id INTEGER
        PRIMARY KEY AUTOINCREMENT,
    execution_actor_namespace_id TEXT NOT NULL UNIQUE,
    source_provider TEXT NOT NULL UNIQUE,
    identity_provider_id TEXT NOT NULL,
    issuer TEXT NOT NULL,
    created_at TEXT NOT NULL,
    retired_at TEXT,
    retired_reason TEXT,
    FOREIGN KEY (
        identity_provider_id,
        issuer
    )
        REFERENCES identity_providers(
            identity_provider_id,
            issuer
        )
        ON DELETE RESTRICT,
    CHECK (
        (
            retired_at IS NULL
            AND retired_reason IS NULL
        )
        OR
        (
            retired_at IS NOT NULL
            AND retired_reason IS NOT NULL
        )
    )
);

CREATE TRIGGER
    require_execution_actor_namespace_genesis
BEFORE INSERT
ON execution_actor_identity_namespaces
WHEN
    NEW.retired_at IS NOT NULL
    OR NEW.retired_reason IS NOT NULL
BEGIN
    SELECT RAISE(
        ABORT,
        'Execution actor identity namespaces must begin current'
    );
END;

CREATE TRIGGER
    prevent_execution_actor_namespace_update
BEFORE UPDATE
ON execution_actor_identity_namespaces
BEGIN
    /*
     * Retirement is deliberately unreachable in v18.
     *
     * A future privileged retirement operation must only
     * permit the first NULL -> non-NULL retirement edge.
     * It must continue blocking changes to namespace ID,
     * source provider, provider ID, issuer, created_at,
     * un-retirement, and re-retirement.
     */
    SELECT RAISE(
        ABORT,
        'Execution actor identity namespaces are immutable'
    );
END;

CREATE TRIGGER
    prevent_execution_actor_namespace_delete
BEFORE DELETE
ON execution_actor_identity_namespaces
BEGIN
    SELECT RAISE(
        ABORT,
        'Execution actor identity namespaces cannot be deleted'
    );
END;

PRAGMA user_version = 18;
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
    SQLiteMigration(
        version=15,
        name="create_principal_foundation",
        sql=CREATE_PRINCIPAL_FOUNDATION_SQL,
    ),
    SQLiteMigration(
        version=16,
        name="create_workspace_membership_foundation",
        sql=(
            CREATE_WORKSPACE_MEMBERSHIP_FOUNDATION_SQL
        ),
    ),
    SQLiteMigration(
        version=17,
        name="create_principal_identity_foundation",
        sql=(
            CREATE_PRINCIPAL_IDENTITY_FOUNDATION_SQL
        ),
    ),
    SQLiteMigration(
        version=18,
        name=(
            "create_execution_actor_identity_namespace"
        ),
        sql=(
            CREATE_EXECUTION_ACTOR_IDENTITY_NAMESPACE_SQL
        ),
    ),
    SQLiteMigration(
        version=19,
        name="create_github_source_binding_foundation",
        sql=CREATE_GITHUB_SOURCE_BINDING_FOUNDATION_SQL,
    ),
    SQLiteMigration(
        version=20,
        name=(
            "add_workspace_membership_role_foundation"
        ),
        sql=(
            ADD_WORKSPACE_MEMBERSHIP_ROLE_FOUNDATION_SQL
        ),
    ),
    SQLiteMigration(
        version=21,
        name=(
            "add_workspace_membership_status_actor"
        ),
        sql=(
            ADD_WORKSPACE_MEMBERSHIP_STATUS_ACTOR_SQL
        ),
    ),
    SQLiteMigration(
        version=22,
        name="classify_workspace_kind",
        sql=CLASSIFY_WORKSPACE_KIND_SQL,
    ),
    SQLiteMigration(
        version=23,
        name="create_workspace_provisioning_idempotency",
        sql=CREATE_WORKSPACE_PROVISIONING_IDEMPOTENCY_SQL,
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
