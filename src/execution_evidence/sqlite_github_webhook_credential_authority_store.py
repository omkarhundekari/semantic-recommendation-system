from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

from execution_evidence.github_webhook_credential_authority import (
    GitHubWebhookCredentialAuthority,
)
from execution_evidence.github_webhook_credential_authority_store import (
    GitHubWebhookCredentialAuthorityAlreadyExistsError,
    GitHubWebhookCredentialAuthorityCredentialNotFoundError,
    GitHubWebhookCredentialAuthorityNotFoundError,
    GitHubWebhookCredentialAuthorityStore,
    GitHubWebhookCredentialAuthorityStoreError,
    GitHubWebhookCredentialAuthorityTransitionError,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)


class SQLiteGitHubWebhookCredentialAuthorityStore(
    GitHubWebhookCredentialAuthorityStore
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
        authority: GitHubWebhookCredentialAuthority,
    ) -> GitHubWebhookCredentialAuthority:
        if (
            authority.retired_at is not None
            or authority.retired_reason is not None
        ):
            raise (
                GitHubWebhookCredentialAuthorityTransitionError(
                    "New GitHub webhook credential "
                    "authorities must begin current."
                )
            )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute("BEGIN IMMEDIATE")

            credential = connection.execute(
                """
                SELECT github_webhook_credential_id
                FROM github_webhook_credentials
                WHERE github_webhook_credential_id = ?
                """,
                (
                    authority.github_webhook_credential_id,
                ),
            ).fetchone()

            if credential is None:
                raise (
                    GitHubWebhookCredentialAuthorityCredentialNotFoundError(
                        "GitHub webhook credential does "
                        "not exist."
                    )
                )

            connection.execute(
                """
                INSERT INTO github_webhook_credential_authorities (
                    github_webhook_credential_authority_id,
                    github_webhook_credential_id,
                    repository_id,
                    created_at,
                    retired_at,
                    retired_reason
                )
                VALUES (?, ?, ?, ?, NULL, NULL)
                """,
                (
                    (
                        authority
                        .github_webhook_credential_authority_id
                    ),
                    authority.github_webhook_credential_id,
                    authority.repository_id,
                    authority.created_at.isoformat(),
                ),
            )

            stored = self._load_from_connection(
                connection,
                (
                    authority
                    .github_webhook_credential_authority_id
                ),
            )

            if stored != authority:
                raise (
                    GitHubWebhookCredentialAuthorityStoreError(
                        "Stored GitHub webhook credential "
                        "authority does not match "
                        "authoritative state."
                    )
                )

            connection.execute("COMMIT")
            return stored

        except (
            GitHubWebhookCredentialAuthorityStoreError,
            ValueError,
        ):
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)
            self._raise_create_integrity_error(error)
        except sqlite3.Error as error:
            self._rollback(connection)
            raise GitHubWebhookCredentialAuthorityStoreError(
                "Could not create GitHub webhook "
                "credential authority."
            ) from error
        finally:
            connection.close()

    def load(
        self,
        github_webhook_credential_authority_id: str,
    ) -> GitHubWebhookCredentialAuthority:
        self._validate_identifier(
            github_webhook_credential_authority_id,
            name="GitHub webhook credential authority ID",
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            return self._load_from_connection(
                connection,
                github_webhook_credential_authority_id,
            )
        except GitHubWebhookCredentialAuthorityNotFoundError:
            raise
        except sqlite3.Error as error:
            raise GitHubWebhookCredentialAuthorityStoreError(
                "Could not load GitHub webhook "
                "credential authority."
            ) from error
        finally:
            connection.close()

    def load_current(
        self,
        *,
        github_webhook_credential_id: str,
        repository_id: str,
    ) -> GitHubWebhookCredentialAuthority:
        self._validate_identifier(
            github_webhook_credential_id,
            name="GitHub webhook credential ID",
        )
        self._validate_exact_lookup_value(
            repository_id,
            name="GitHub repository ID",
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
                    github_webhook_credential_authority_id,
                    github_webhook_credential_id,
                    repository_id,
                    created_at,
                    retired_at,
                    retired_reason
                FROM github_webhook_credential_authorities
                WHERE
                    github_webhook_credential_id = ?
                    AND repository_id = ?
                    AND retired_at IS NULL
                """,
                (
                    github_webhook_credential_id,
                    repository_id,
                ),
            ).fetchone()

            if row is None:
                raise (
                    GitHubWebhookCredentialAuthorityNotFoundError(
                        "Current GitHub webhook credential "
                        "authority does not exist."
                    )
                )

            return self._authority_from_row(row)

        except GitHubWebhookCredentialAuthorityNotFoundError:
            raise
        except sqlite3.Error as error:
            raise GitHubWebhookCredentialAuthorityStoreError(
                "Could not load current GitHub webhook "
                "credential authority."
            ) from error
        finally:
            connection.close()

    def list_for_credential(
        self,
        github_webhook_credential_id: str,
    ) -> List[GitHubWebhookCredentialAuthority]:
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
            rows = connection.execute(
                """
                SELECT
                    github_webhook_credential_authority_id,
                    github_webhook_credential_id,
                    repository_id,
                    created_at,
                    retired_at,
                    retired_reason
                FROM github_webhook_credential_authorities
                WHERE github_webhook_credential_id = ?
                ORDER BY
                    created_at ASC,
                    github_webhook_credential_authority_row_id ASC
                """,
                (github_webhook_credential_id,),
            ).fetchall()

            return [
                self._authority_from_row(row)
                for row in rows
            ]

        except sqlite3.Error as error:
            raise GitHubWebhookCredentialAuthorityStoreError(
                "Could not list GitHub webhook "
                "credential authorities."
            ) from error
        finally:
            connection.close()

    @staticmethod
    def _load_from_connection(
        connection: sqlite3.Connection,
        github_webhook_credential_authority_id: str,
    ) -> GitHubWebhookCredentialAuthority:
        row = connection.execute(
            """
            SELECT
                github_webhook_credential_authority_id,
                github_webhook_credential_id,
                repository_id,
                created_at,
                retired_at,
                retired_reason
            FROM github_webhook_credential_authorities
            WHERE github_webhook_credential_authority_id = ?
            """,
            (
                github_webhook_credential_authority_id,
            ),
        ).fetchone()

        if row is None:
            raise (
                GitHubWebhookCredentialAuthorityNotFoundError(
                    "GitHub webhook credential authority "
                    "does not exist."
                )
            )

        return (
            SQLiteGitHubWebhookCredentialAuthorityStore
            ._authority_from_row(row)
        )

    @staticmethod
    def _authority_from_row(
        row: sqlite3.Row,
    ) -> GitHubWebhookCredentialAuthority:
        return GitHubWebhookCredentialAuthority(
            github_webhook_credential_authority_id=row[
                "github_webhook_credential_authority_id"
            ],
            github_webhook_credential_id=row[
                "github_webhook_credential_id"
            ],
            repository_id=row["repository_id"],
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
            "github_webhook_credential_authorities."
            "github_webhook_credential_authority_id"
            in message
        ):
            raise (
                GitHubWebhookCredentialAuthorityAlreadyExistsError(
                    "GitHub webhook credential authority "
                    "ID already exists."
                )
            ) from error

        if (
            "UNIQUE constraint failed: "
            "github_webhook_credential_authorities."
            "github_webhook_credential_id, "
            "github_webhook_credential_authorities."
            "repository_id"
            in message
        ):
            raise (
                GitHubWebhookCredentialAuthorityAlreadyExistsError(
                    "GitHub webhook credential already "
                    "has current authority for this "
                    "repository."
                )
            ) from error

        raise GitHubWebhookCredentialAuthorityStoreError(
            "Could not create GitHub webhook credential "
            "authority."
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
    def _validate_exact_lookup_value(
        value: str,
        *,
        name: str,
    ) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"{name} must be non-empty text."
            )

    @staticmethod
    def _rollback(
        connection: sqlite3.Connection,
    ) -> None:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
