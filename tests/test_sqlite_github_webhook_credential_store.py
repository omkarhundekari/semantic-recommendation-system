from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from execution_evidence.github_webhook_credential import (
    GitHubWebhookCredential,
)
from execution_evidence.github_webhook_credential_store import (
    GitHubWebhookCredentialAlreadyExistsError,
    GitHubWebhookCredentialNotFoundError,
    GitHubWebhookCredentialStoreError,
    GitHubWebhookCredentialTransitionError,
)
from execution_evidence.sqlite_github_webhook_credential_store import (
    SQLiteGitHubWebhookCredentialStore,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)


UTC = timezone.utc
NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=UTC,
)

CREDENTIAL_ID = (
    "gwc_123e4567-e89b-42d3-a456-426614174000"
)
ENDPOINT_ID = (
    "gwe_123e4567-e89b-42d3-a456-426614174001"
)


@pytest.fixture
def database_path(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(path)
    return path


def _credential(**changes):
    values = {
        "github_webhook_credential_id": CREDENTIAL_ID,
        "webhook_endpoint_id": ENDPOINT_ID,
        "installation_id": None,
        "secret_ref": "SOLVYN_GITHUB_WEBHOOK_A",
        "created_at": NOW,
        "retired_at": None,
        "retired_reason": None,
    }
    values.update(changes)

    return GitHubWebhookCredential(**values)


def test_create_and_load_credential(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialStore(
        database_path
    )
    credential = _credential(
        installation_id="123456"
    )

    created = store.create(credential)
    loaded = store.load(
        credential.github_webhook_credential_id
    )

    assert created == credential
    assert loaded == credential


def test_create_preserves_opaque_secret_ref(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialStore(
        database_path
    )
    credential = _credential(
        secret_ref="vault://github/hook:A?version=7"
    )

    assert store.create(credential) == credential


def test_create_rejects_retired_credential(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialStore(
        database_path
    )
    credential = _credential(
        retired_at=NOW + timedelta(days=1),
        retired_reason="rotated",
    )

    with pytest.raises(
        GitHubWebhookCredentialTransitionError
    ):
        store.create(credential)


def test_duplicate_credential_id_maps_to_domain_error(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialStore(
        database_path
    )
    store.create(_credential())

    duplicate = _credential(
        webhook_endpoint_id=(
            "gwe_123e4567-e89b-42d3-a456-426614174002"
        )
    )

    with pytest.raises(
        GitHubWebhookCredentialAlreadyExistsError,
        match="credential ID",
    ):
        store.create(duplicate)


def test_duplicate_endpoint_id_maps_to_domain_error(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialStore(
        database_path
    )
    store.create(_credential())

    duplicate = _credential(
        github_webhook_credential_id=(
            "gwc_123e4567-e89b-42d3-a456-426614174002"
        )
    )

    with pytest.raises(
        GitHubWebhookCredentialAlreadyExistsError,
        match="endpoint ID",
    ):
        store.create(duplicate)


def test_load_missing_credential(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialStore(
        database_path
    )

    with pytest.raises(
        GitHubWebhookCredentialNotFoundError
    ):
        store.load(CREDENTIAL_ID)


def test_load_current_by_endpoint(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialStore(
        database_path
    )
    credential = _credential()
    store.create(credential)

    assert (
        store.load_current_by_webhook_endpoint_id(
            ENDPOINT_ID
        )
        == credential
    )


def test_load_current_unknown_endpoint_is_not_found(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialStore(
        database_path
    )

    with pytest.raises(
        GitHubWebhookCredentialNotFoundError
    ):
        store.load_current_by_webhook_endpoint_id(
            ENDPOINT_ID
        )



def test_retired_endpoint_is_not_current(
    database_path: Path,
):
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

        # Retirement is intentionally unreachable through
        # v19 writes. Drop only the genesis trigger in this
        # isolated test database so we can represent valid
        # historical state and exercise the current lookup.
        connection.execute(
            """
            DROP TRIGGER
            require_github_webhook_credential_genesis
            """
        )

        connection.execute(
            """
            INSERT INTO github_webhook_credentials (
                github_webhook_credential_id,
                webhook_endpoint_id,
                installation_id,
                secret_ref,
                created_at,
                retired_at,
                retired_reason
            )
            VALUES (?, ?, NULL, ?, ?, ?, ?)
            """,
            (
                CREDENTIAL_ID,
                ENDPOINT_ID,
                "SOLVYN_GITHUB_WEBHOOK_A",
                NOW.isoformat(),
                (
                    NOW + timedelta(days=1)
                ).isoformat(),
                "rotated",
            ),
        )

        connection.execute("COMMIT")
    finally:
        connection.close()

    store = SQLiteGitHubWebhookCredentialStore(
        database_path
    )

    with pytest.raises(
        GitHubWebhookCredentialNotFoundError
    ):
        store.load_current_by_webhook_endpoint_id(
            ENDPOINT_ID
        )


def test_endpoint_lookup_does_not_trim(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialStore(
        database_path
    )
    store.create(_credential())

    with pytest.raises(ValueError):
        store.load_current_by_webhook_endpoint_id(
            f" {ENDPOINT_ID}"
        )


def test_endpoint_lookup_does_not_case_fold(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialStore(
        database_path
    )
    store.create(_credential())

    with pytest.raises(
        GitHubWebhookCredentialNotFoundError
    ):
        store.load_current_by_webhook_endpoint_id(
            ENDPOINT_ID.upper()
        )


def test_store_does_not_initialize_schema(
    tmp_path: Path,
):
    database_path = tmp_path / "uninitialized.db"
    store = SQLiteGitHubWebhookCredentialStore(
        database_path
    )

    with pytest.raises(
        GitHubWebhookCredentialStoreError
    ):
        store.load_current_by_webhook_endpoint_id(
            ENDPOINT_ID
        )


def test_unknown_integrity_error_is_not_duplicate(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import execution_evidence.sqlite_github_webhook_credential_store as module

    original_connect = (
        module.connect_execution_evidence_database
    )

    class ConnectionProxy:
        def __init__(self, connection):
            self._connection = connection
            self._raised = False

        @property
        def in_transaction(self):
            return self._connection.in_transaction

        def execute(self, sql, parameters=()):
            if (
                not self._raised
                and "INSERT INTO github_webhook_credentials"
                in sql
            ):
                self._raised = True
                import sqlite3

                raise sqlite3.IntegrityError(
                    "CHECK constraint failed: unexpected"
                )

            return self._connection.execute(
                sql,
                parameters,
            )

        def close(self):
            self._connection.close()

    def connect_with_unknown_integrity_error(path):
        return ConnectionProxy(
            original_connect(path)
        )

    monkeypatch.setattr(
        module,
        "connect_execution_evidence_database",
        connect_with_unknown_integrity_error,
    )

    store = SQLiteGitHubWebhookCredentialStore(
        database_path
    )

    with pytest.raises(
        GitHubWebhookCredentialStoreError
    ) as raised:
        store.create(_credential())

    assert not isinstance(
        raised.value,
        GitHubWebhookCredentialAlreadyExistsError,
    )
