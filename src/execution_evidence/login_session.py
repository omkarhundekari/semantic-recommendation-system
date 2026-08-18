from __future__ import annotations

from typing import Optional

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


LOGIN_SESSION_ID_PREFIX = "ses_"

MIN_LOGIN_SESSION_TOKEN_BYTES = 32

MAX_LOGIN_SESSION_TOKEN_BYTES = 1024


def create_login_session_id() -> str:
    return f"{LOGIN_SESSION_ID_PREFIX}{uuid4()}"


class LoginSession(BaseModel):
    """Durable opaque Solvyn login session.

    The raw browser credential is deliberately absent.

    Durable storage contains only a one-way SHA-256 digest
    of the opaque credential. The session is bound to both
    the durable principal and the exact identity link that
    authenticated the login.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    session_id: str = Field(min_length=1)
    principal_id: str = Field(min_length=1)
    identity_link_id: str = Field(min_length=1)

    created_at: datetime
    expires_at: datetime

    revoked_at: Optional[datetime] = None
    revoke_reason: Optional[str] = None

    @field_validator("session_id")
    @classmethod
    def validate_session_id(
        cls,
        value: str,
    ) -> str:
        _validate_prefixed_uuid4(
            value,
            prefix=LOGIN_SESSION_ID_PREFIX,
            label="Login session ID",
        )
        return value

    @field_validator("principal_id")
    @classmethod
    def validate_principal_id(
        cls,
        value: str,
    ) -> str:
        _validate_prefixed_uuid4(
            value,
            prefix="prn_",
            label="Principal ID",
        )
        return value

    @field_validator("identity_link_id")
    @classmethod
    def validate_identity_link_id(
        cls,
        value: str,
    ) -> str:
        _validate_prefixed_uuid4(
            value,
            prefix="pil_",
            label="Principal identity link ID",
        )
        return value

    @field_validator(
        "created_at",
        "expires_at",
        "revoked_at",
    )
    @classmethod
    def require_aware_datetime(
        cls,
        value: Optional[datetime],
    ) -> Optional[datetime]:
        if value is None:
            return None

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Login session timestamps must be "
                "timezone-aware."
            )

        return value

    @field_validator("revoke_reason")
    @classmethod
    def validate_revoke_reason(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        if (
            not value
            or value != value.strip()
        ):
            raise ValueError(
                "Login session revoke reason must be "
                "non-empty exact text."
            )

        return value

    @model_validator(mode="after")
    def validate_lifecycle(
        self,
    ) -> "LoginSession":
        if self.expires_at <= self.created_at:
            raise ValueError(
                "Login session expiration must follow "
                "creation."
            )

        if (
            self.revoked_at is None
            and self.revoke_reason is not None
        ):
            raise ValueError(
                "Active login sessions cannot have a "
                "revoke reason."
            )

        if (
            self.revoked_at is not None
            and self.revoke_reason is None
        ):
            raise ValueError(
                "Revoked login sessions require a "
                "revoke reason."
            )

        if (
            self.revoked_at is not None
            and self.revoked_at < self.created_at
        ):
            raise ValueError(
                "Login session revocation cannot "
                "precede creation."
            )

        return self


@dataclass(frozen=True)
class IssuedLoginSession:
    """One-time result of creating a login session.

    `token` is the opaque browser credential.

    Callers may transmit it to the trusted BFF/browser
    boundary exactly as required, but must never persist
    the raw value in durable storage or logs.
    """

    token: str
    session: LoginSession


def _validate_prefixed_uuid4(
    value: str,
    *,
    prefix: str,
    label: str,
) -> None:
    if not isinstance(value, str):
        raise ValueError(
            f"{label} must be text."
        )

    if value != value.strip():
        raise ValueError(
            f"{label} must not contain surrounding "
            "whitespace."
        )

    if not value.startswith(prefix):
        raise ValueError(
            f"{label} must start with {prefix!r}."
        )

    raw_uuid = value[len(prefix):]

    try:
        parsed = UUID(raw_uuid)
    except ValueError as error:
        raise ValueError(
            f"{label} must contain a valid UUID."
        ) from error

    if (
        parsed.version != 4
        or str(parsed) != raw_uuid
    ):
        raise ValueError(
            f"{label} must contain a canonical UUID4."
        )
