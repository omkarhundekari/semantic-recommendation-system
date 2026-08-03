from __future__ import annotations

import sqlite3
from pathlib import Path

from execution_evidence.github_webhook_credential import (
    GitHubWebhookCredential,
)
from execution_evidence.github_webhook_credential_store import (
    GitHubWebhookCredentialAlreadyExistsError,
    GitHubWebhookCredentialNotFoundError,
    GitHubWebhookCredentialStore,
    GitHubWebhookCredentialStoreError,
    GitHubWebhookCredentialTransitionError,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)


class SQLiteGitHubWebhookCredentialStore(
    GitHubWebhookCredentialStore
):
    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def create(
        self,
        credential: GitHubWebhookCredential,
    ) -> GitHubWebhookCredential:
        if (
            credential.retired_at is not None
            or credential.retired_reason is not None
        ):
            raise GitHubWebhookCredentialTransitionError(
                "New GitHub webhook credentials must "
                "begin current."
            )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute("BEGIN IMMEDIATE")

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
                VALUES (
                    ?, ?, ?, ?, ?, NULL, NULL
                )
                """,
                (
                    credential.github_webhook_credential_id,
                    credential.webhook_endpoint_id,
                    credential.installation_id,
                    credential.secret_ref,
                    credential.created_at.isoformat(),
                ),
            )

            stored = self._load_from_connection(
                connection,
                credential.github_webhook_credential_id,
            )

            if stored != credential:
                raise GitHubWebhookCredentialStoreError(
                    "Stored GitHub webhook credential "
                    "does not match authoritative state."
                )

            connection.execute("COMMIT")
            return stored

        except (
            GitHubWebhookCredentialStoreError,
            ValueError,
        ):
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)
            self._raise_create_integrity_error(error)
        except sqlite3.Error as error:
            self._rollback(connection)
            raise GitHubWebhookCredentialStoreError(
                "Could not create GitHub webhook "
                "credential."
            ) from error
        finally:
            connection.close()

    def load(
        self,
        github_webhook_credential_id: str,
    ) -> GitHubWebhookCredential:
        self._validate_identifier(
            github_webhook_credential_id,
            name="GitHub webhook credential ID",
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            return self._load_from_connection(
                connection,
                github_webhook_credential_id,
            )
        except GitHubWebhookCredentialNotFoundError:
            raise
        except sqlite3.Error as error:
            raise GitHubWebhookCredentialStoreError(
                "Could not load GitHub webhook "
                "credential."
            ) from error
        finally:
            connection.close()

    def load_current_by_webhook_endpoint_id(
        self,
        webhook_endpoint_id: str,
    ) -> GitHubWebhookCredential:
        self._validate_identifier(
            webhook_endpoint_id,
            name="GitHub webhook endpoint ID",
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            row = connection.execute(
                """
                SELECT
                    github_webhook_credential_id,
                    webhook_endpoint_id,
                    installation_id,
                    secret_ref,
                    created_at,
                    retired_at,
                    retired_reason
                FROM github_webhook_credentials
                WHERE
                    webhook_endpoint_id = ?
                    AND retired_at IS NULL
                """,
                (webhook_endpoint_id,),
            ).fetchone()

            if row is None:
                raise GitHubWebhookCredentialNotFoundError(
                    "Current GitHub webhook credential "
                    "does not exist."
                )

            return self._credential_from_row(row)

        except GitHubWebhookCredentialNotFoundError:
            raise
        except sqlite3.Error as error:
            raise GitHubWebhookCredentialStoreError(
                "Could not load current GitHub webhook "
                "credential."
            ) from error
        finally:
            connection.close()

    @staticmethod
    def _load_from_connection(
        connection: sqlite3.Connection,
        github_webhook_credential_id: str,
    ) -> GitHubWebhookCredential:
        row = connection.execute(
            """
            SELECT
                github_webhook_credential_id,
                webhook_endpoint_id,
                installation_id,
                secret_ref,
                created_at,
                retired_at,
                retired_reason
            FROM github_webhook_credentials
            WHERE github_webhook_credential_id = ?
            """,
            (github_webhook_credential_id,),
        ).fetchone()

        if row is None:
            raise GitHubWebhookCredentialNotFoundError(
                "GitHub webhook credential does not "
                "exist."
            )

        return (
            SQLiteGitHubWebhookCredentialStore
            ._credential_from_row(row)
        )

    @staticmethod
    def _credential_from_row(
        row: sqlite3.Row,
    ) -> GitHubWebhookCredential:
        return GitHubWebhookCredential(
            github_webhook_credential_id=row[
                "github_webhook_credential_id"
            ],
            webhook_endpoint_id=row[
                "webhook_endpoint_id"
            ],
            installation_id=row["installation_id"],
            secret_ref=row["secret_ref"],
            created_at=row["created_at"],
            retired_at=row["retired_at"],
            retired_reason=row["retired_reason"],
        )

    @staticmethod
    def _raise_create_integrity_error(
        error: sqlite3.IntegrityError,
    ) -> None:
        message = str(error)

        if (
            "UNIQUE constraint failed: "
            "github_webhook_credentials."
            "github_webhook_credential_id"
            in message
        ):
            raise GitHubWebhookCredentialAlreadyExistsError(
                "GitHub webhook credential ID already "
                "exists."
            ) from error

        if (
            "UNIQUE constraint failed: "
            "github_webhook_credentials."
            "webhook_endpoint_id"
            in message
        ):
            raise GitHubWebhookCredentialAlreadyExistsError(
                "GitHub webhook endpoint ID already "
                "exists."
            ) from error

        raise GitHubWebhookCredentialStoreError(
            "Could not create GitHub webhook credential."
        ) from error

    @staticmethod
    def _validate_identifier(
        value: str,
        *,
        name: str,
    ) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"{name} must be non-empty text."
            )

        if value != value.strip():
            raise ValueError(
                f"{name} must not contain "
                "surrounding whitespace."
            )

    @staticmethod
    def _rollback(
        connection: sqlite3.Connection,
    ) -> None:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
