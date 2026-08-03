from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from execution_evidence.github_webhook_credential import (
    GitHubWebhookCredential,
)
from execution_evidence.github_webhook_credential_authority import (
    GitHubWebhookCredentialAuthority,
)
from execution_evidence.github_webhook_credential_authority_store import (
    GitHubWebhookCredentialAuthorityAlreadyExistsError,
    GitHubWebhookCredentialAuthorityCredentialNotFoundError,
    GitHubWebhookCredentialAuthorityNotFoundError,
    GitHubWebhookCredentialAuthorityStoreError,
    GitHubWebhookCredentialAuthorityTransitionError,
)
from execution_evidence.sqlite_github_webhook_credential_authority_store import (
    SQLiteGitHubWebhookCredentialAuthorityStore,
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
    20,
    0,
    tzinfo=UTC,
)

CREDENTIAL_ID = (
    "gwc_123e4567-e89b-42d3-a456-426614174000"
)
SECOND_CREDENTIAL_ID = (
    "gwc_223e4567-e89b-42d3-a456-426614174000"
)
ENDPOINT_ID = (
    "gwe_123e4567-e89b-42d3-a456-426614174000"
)
SECOND_ENDPOINT_ID = (
    "gwe_223e4567-e89b-42d3-a456-426614174000"
)
AUTHORITY_ID = (
    "gwa_123e4567-e89b-42d3-a456-426614174000"
)
SECOND_AUTHORITY_ID = (
    "gwa_223e4567-e89b-42d3-a456-426614174000"
)


@pytest.fixture
def database_path(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "solvyn.db"

    initialize_execution_evidence_database(path)

    return path


def _credential(
    *,
    credential_id: str = CREDENTIAL_ID,
    endpoint_id: str = ENDPOINT_ID,
) -> GitHubWebhookCredential:
    return GitHubWebhookCredential(
        github_webhook_credential_id=credential_id,
        webhook_endpoint_id=endpoint_id,
        installation_id=None,
        secret_ref="SOLVYN_GITHUB_WEBHOOK_TEST",
        created_at=NOW,
    )


def _authority(
    *,
    authority_id: str = AUTHORITY_ID,
    credential_id: str = CREDENTIAL_ID,
    repository_id: str = "123",
    retired_at=None,
    retired_reason=None,
) -> GitHubWebhookCredentialAuthority:
    return GitHubWebhookCredentialAuthority(
        github_webhook_credential_authority_id=(
            authority_id
        ),
        github_webhook_credential_id=credential_id,
        repository_id=repository_id,
        created_at=NOW,
        retired_at=retired_at,
        retired_reason=retired_reason,
    )


def _create_credential(
    database_path: Path,
    *,
    credential_id: str = CREDENTIAL_ID,
    endpoint_id: str = ENDPOINT_ID,
) -> GitHubWebhookCredential:
    return SQLiteGitHubWebhookCredentialStore(
        database_path
    ).create(
        _credential(
            credential_id=credential_id,
            endpoint_id=endpoint_id,
        )
    )


def test_create_and_load_authority(
    database_path: Path,
):
    _create_credential(database_path)

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )
    authority = _authority()

    created = store.create(authority)
    loaded = store.load(AUTHORITY_ID)

    assert created == authority
    assert loaded == authority


def test_create_requires_existing_credential(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )

    with pytest.raises(
        GitHubWebhookCredentialAuthorityCredentialNotFoundError
    ):
        store.create(_authority())


def test_create_rejects_retired_authority(
    database_path: Path,
):
    _create_credential(database_path)

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )

    with pytest.raises(
        GitHubWebhookCredentialAuthorityTransitionError
    ):
        store.create(
            _authority(
                retired_at=NOW + timedelta(days=1),
                retired_reason="rotated",
            )
        )


def test_duplicate_authority_id_maps_to_domain_error(
    database_path: Path,
):
    _create_credential(database_path)

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )

    store.create(_authority())

    with pytest.raises(
        GitHubWebhookCredentialAuthorityAlreadyExistsError
    ):
        store.create(
            _authority(
                repository_id="456"
            )
        )


def test_duplicate_current_credential_repository_pair_maps_to_domain_error(
    database_path: Path,
):
    _create_credential(database_path)

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )

    store.create(_authority())

    with pytest.raises(
        GitHubWebhookCredentialAuthorityAlreadyExistsError
    ):
        store.create(
            _authority(
                authority_id=SECOND_AUTHORITY_ID
            )
        )


def test_two_credentials_can_authorize_same_repository(
    database_path: Path,
):
    _create_credential(database_path)

    _create_credential(
        database_path,
        credential_id=SECOND_CREDENTIAL_ID,
        endpoint_id=SECOND_ENDPOINT_ID,
    )

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )

    first = store.create(_authority())

    second = store.create(
        _authority(
            authority_id=SECOND_AUTHORITY_ID,
            credential_id=SECOND_CREDENTIAL_ID,
        )
    )

    assert first.repository_id == "123"
    assert second.repository_id == "123"
    assert (
        first.github_webhook_credential_id
        != second.github_webhook_credential_id
    )


def test_one_credential_can_authorize_multiple_repositories(
    database_path: Path,
):
    _create_credential(database_path)

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )

    first = store.create(_authority())

    second = store.create(
        _authority(
            authority_id=SECOND_AUTHORITY_ID,
            repository_id="456",
        )
    )

    assert first.repository_id == "123"
    assert second.repository_id == "456"


def test_load_missing_authority(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )

    with pytest.raises(
        GitHubWebhookCredentialAuthorityNotFoundError
    ):
        store.load(AUTHORITY_ID)


def test_load_current_exact_pair(
    database_path: Path,
):
    _create_credential(database_path)

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )
    authority = store.create(_authority())

    loaded = store.load_current(
        github_webhook_credential_id=CREDENTIAL_ID,
        repository_id="123",
    )

    assert loaded == authority


def test_current_repository_lookup_does_not_trim(
    database_path: Path,
):
    _create_credential(database_path)

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )
    store.create(_authority())

    with pytest.raises(
        GitHubWebhookCredentialAuthorityNotFoundError
    ):
        store.load_current(
            github_webhook_credential_id=CREDENTIAL_ID,
            repository_id=" 123 ",
        )


def test_current_repository_lookup_does_not_coerce(
    database_path: Path,
):
    _create_credential(database_path)

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )
    store.create(_authority())

    with pytest.raises(ValueError):
        store.load_current(
            github_webhook_credential_id=CREDENTIAL_ID,
            repository_id=123,
        )


def test_current_credential_lookup_rejects_surrounding_whitespace(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )

    with pytest.raises(ValueError):
        store.load_current(
            github_webhook_credential_id=(
                f" {CREDENTIAL_ID} "
            ),
            repository_id="123",
        )


def test_unknown_current_pair_is_not_found(
    database_path: Path,
):
    _create_credential(database_path)

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )

    with pytest.raises(
        GitHubWebhookCredentialAuthorityNotFoundError
    ):
        store.load_current(
            github_webhook_credential_id=CREDENTIAL_ID,
            repository_id="999",
        )


def test_retired_authority_is_not_current(
    database_path: Path,
):
    _create_credential(database_path)

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )
    store.create(_authority())

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

        # Retirement is intentionally unreachable in v19.
        # This isolated test removes only that protection
        # so current-lookup behavior can be pinned against
        # structurally valid historical state.
        connection.execute(
            """
            DROP TRIGGER
                prevent_github_webhook_authority_update
            """
        )

        connection.execute(
            """
            UPDATE github_webhook_credential_authorities
            SET
                retired_at = ?,
                retired_reason = ?
            WHERE
                github_webhook_credential_authority_id = ?
            """,
            (
                (
                    NOW + timedelta(days=1)
                ).isoformat(),
                "rotated",
                AUTHORITY_ID,
            ),
        )

        connection.execute("COMMIT")
    finally:
        connection.close()

    with pytest.raises(
        GitHubWebhookCredentialAuthorityNotFoundError
    ):
        store.load_current(
            github_webhook_credential_id=CREDENTIAL_ID,
            repository_id="123",
        )

    historical = store.load(AUTHORITY_ID)

    assert historical.retired_at is not None
    assert historical.retired_reason == "rotated"


def test_list_for_credential_returns_history_in_storage_order(
    database_path: Path,
):
    _create_credential(database_path)

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )

    first = store.create(
        _authority(
            repository_id="123"
        )
    )

    second = store.create(
        _authority(
            authority_id=SECOND_AUTHORITY_ID,
            repository_id="456",
        )
    )

    assert store.list_for_credential(
        CREDENTIAL_ID
    ) == [
        first,
        second,
    ]


def test_list_unknown_credential_is_empty(
    database_path: Path,
):
    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )

    assert store.list_for_credential(
        CREDENTIAL_ID
    ) == []


def test_store_does_not_initialize_schema(
    tmp_path: Path,
):
    database_path = tmp_path / "missing.db"

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )

    with pytest.raises(
        GitHubWebhookCredentialAuthorityStoreError
    ):
        store.load(AUTHORITY_ID)


def test_unknown_integrity_error_is_not_duplicate(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _create_credential(database_path)

    import execution_evidence.sqlite_github_webhook_credential_authority_store as module

    original_connect = (
        module.connect_execution_evidence_database
    )

    class ConnectionProxy:
        def __init__(
            self,
            connection,
        ):
            self._connection = connection

        @property
        def in_transaction(self):
            return self._connection.in_transaction

        def execute(
            self,
            sql,
            parameters=(),
        ):
            if (
                "INSERT INTO "
                "github_webhook_credential_authorities"
                in sql
            ):
                raise module.sqlite3.IntegrityError(
                    "unknown authority integrity failure"
                )

            return self._connection.execute(
                sql,
                parameters,
            )

        def close(self):
            self._connection.close()

    def connect_with_unknown_integrity_error(
        path,
    ):
        return ConnectionProxy(
            original_connect(path)
        )

    monkeypatch.setattr(
        module,
        "connect_execution_evidence_database",
        connect_with_unknown_integrity_error,
    )

    store = SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    )

    with pytest.raises(
        GitHubWebhookCredentialAuthorityStoreError
    ) as raised:
        store.create(_authority())

    assert not isinstance(
        raised.value,
        GitHubWebhookCredentialAuthorityAlreadyExistsError,
    )
