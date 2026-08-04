from __future__ import annotations

from typing import Optional

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.oidc_token_verifier import (
    OIDCTokenInvalidError,
    OIDCTokenVerifier,
    OIDCTokenVerifierUnavailableError,
)
from execution_evidence.request_principal_resolver import (
    RequestPrincipalNotFoundError,
    RequestPrincipalResolutionStoreError,
    RequestPrincipalResolver,
)


class RequestAuthenticationError(RuntimeError):
    pass


class RequestAuthenticationRequiredError(
    RequestAuthenticationError
):
    pass


class RequestAuthenticationFailedError(
    RequestAuthenticationError
):
    pass


class RequestAuthenticationUnavailableError(
    RequestAuthenticationError
):
    pass


class RequestAuthenticator:
    def __init__(
        self,
        *,
        token_verifier: OIDCTokenVerifier,
        principal_resolver: RequestPrincipalResolver,
    ) -> None:
        self._token_verifier = token_verifier
        self._principal_resolver = (
            principal_resolver
        )

    def authenticate(
        self,
        authorization_header: Optional[str],
    ) -> AuthenticatedRequestPrincipal:
        token = self._extract_bearer_token(
            authorization_header
        )

        try:
            identity = self._token_verifier.verify(
                token
            )
        except OIDCTokenInvalidError as error:
            raise RequestAuthenticationFailedError(
                "Request authentication failed."
            ) from error
        except OIDCTokenVerifierUnavailableError as error:
            raise RequestAuthenticationUnavailableError(
                "Request authentication is temporarily "
                "unavailable."
            ) from error

        try:
            return self._principal_resolver.resolve(
                identity
            )
        except RequestPrincipalNotFoundError as error:
            raise RequestAuthenticationFailedError(
                "Request authentication failed."
            ) from error
        except (
            RequestPrincipalResolutionStoreError
        ) as error:
            raise RequestAuthenticationUnavailableError(
                "Request authentication is temporarily "
                "unavailable."
            ) from error

    @staticmethod
    def _extract_bearer_token(
        authorization_header: Optional[str],
    ) -> str:
        if authorization_header is None:
            raise RequestAuthenticationRequiredError(
                "Bearer authentication is required."
            )

        if not isinstance(
            authorization_header,
            str,
        ):
            raise RequestAuthenticationRequiredError(
                "Bearer authentication is required."
            )

        parts = authorization_header.split()

        if (
            len(parts) != 2
            or parts[0].lower() != "bearer"
            or not parts[1]
        ):
            raise RequestAuthenticationRequiredError(
                "Bearer authentication is required."
            )

        return parts[1]
