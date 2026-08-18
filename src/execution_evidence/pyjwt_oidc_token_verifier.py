from __future__ import annotations

import base64
import json
from typing import Mapping

import jwt
from jwt.algorithms import RSAAlgorithm

from execution_evidence.oidc_jwks import (
    CachedOIDCJWKSProvider,
    OIDCJWKSKeyNotFoundError,
    OIDCJWKSRefreshThrottledError,
    OIDCJWKSUnavailableError,
)
from execution_evidence.oidc_provider_config import (
    OIDCProviderConfigurationNotFoundError,
    OIDCProviderConfig,
    OIDCProviderConfigRegistry,
)
from execution_evidence.oidc_token_verifier import (
    OIDCTokenInvalidError,
    OIDCTokenVerifier,
    OIDCTokenVerifierUnavailableError,
)
from execution_evidence.verified_oidc_identity import (
    VerifiedOIDCIdentity,
)


MAX_OIDC_BEARER_TOKEN_BYTES = 8 * 1024
OIDC_CLOCK_SKEW_SECONDS = 60
MIN_RSA_MODULUS_BITS = 2048
RS256 = "RS256"


class PyJWTOIDCTokenVerifier(
    OIDCTokenVerifier
):
    def __init__(
        self,
        *,
        provider_registry: OIDCProviderConfigRegistry,
        jwks_provider: CachedOIDCJWKSProvider,
    ) -> None:
        self._provider_registry = provider_registry
        self._jwks_provider = jwks_provider

    def verify(
        self,
        token: str,
    ) -> VerifiedOIDCIdentity:
        if not isinstance(token, str):
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        if (
            not token
            or len(token.encode("utf-8"))
            > MAX_OIDC_BEARER_TOKEN_BYTES
        ):
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        issuer = self._read_unverified_issuer(
            token
        )

        try:
            config = (
                self._provider_registry
                .load_by_issuer(issuer)
            )
        except (
            OIDCProviderConfigurationNotFoundError
        ) as error:
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            ) from error

        try:
            header = jwt.get_unverified_header(
                token
            )
        except jwt.InvalidTokenError as error:
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            ) from error

        algorithm = header.get("alg")
        kid = header.get("kid")

        if (
            algorithm not in config.allowed_algorithms
            or algorithm != RS256
        ):
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        if (
            not isinstance(kid, str)
            or not kid
            or kid != kid.strip()
        ):
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        try:
            jwk = self._jwks_provider.load_key(
                config=config,
                kid=kid,
            )
        except OIDCJWKSRefreshThrottledError as error:
            raise OIDCTokenVerifierUnavailableError(
                "OIDC signing keys are temporarily "
                "unavailable."
            ) from error
        except OIDCJWKSUnavailableError as error:
            raise OIDCTokenVerifierUnavailableError(
                "OIDC signing keys are temporarily "
                "unavailable."
            ) from error
        except OIDCJWKSKeyNotFoundError as error:
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            ) from error

        public_key = self._public_key_from_jwk(
            jwk
        )

        try:
            claims = jwt.decode(
                token,
                key=public_key,
                algorithms=list(
                    config.allowed_algorithms
                ),
                audience=config.audience,
                issuer=config.issuer,
                leeway=OIDC_CLOCK_SKEW_SECONDS,
                options={
                    "require": [
                        "exp",
                        "iss",
                        "aud",
                        "sub",
                    ],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
        except jwt.InvalidTokenError as error:
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            ) from error

        subject = claims.get("sub")
        verified_issuer = claims.get("iss")
        audience = claims.get("aud")

        if (
            not isinstance(subject, str)
            or not subject
            or subject != subject.strip()
        ):
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        if verified_issuer != config.issuer:
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        if not self._audience_matches(
            audience,
            config.audience,
        ):
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        return VerifiedOIDCIdentity(
            identity_provider_id=(
                config.identity_provider_id
            ),
            issuer=config.issuer,
            subject=subject,
        )

    def verify_login_id_token(
        self,
        token: str,
        *,
        expected_nonce: str,
    ) -> VerifiedOIDCIdentity:
        """Verify one login ID token and bind it to its nonce.

        This is intentionally separate from verify().

        RequestAuthenticator continues to use verify(), which
        preserves the resource-server authentication contract.
        Only the interactive login/callback path should use this
        method.

        The ordinary verifier performs all signature, algorithm,
        issuer, audience, expiry, not-before, subject, JWKS, and
        key-strength validation first. Only after that succeeds do
        we inspect the nonce from the exact same token.
        """

        if (
            not isinstance(expected_nonce, str)
            or not expected_nonce
            or expected_nonce
            != expected_nonce.strip()
        ):
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        identity = self.verify(token)

        try:
            claims = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_nbf": False,
                    "verify_iss": False,
                    "verify_aud": False,
                },
            )
        except jwt.InvalidTokenError as error:
            # Reaching this branch after verify() succeeded would
            # indicate an internally inconsistent token parse.
            # It still fails closed as an invalid login token.
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            ) from error

        if not isinstance(claims, dict):
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        nonce = claims.get("nonce")

        if (
            not isinstance(nonce, str)
            or not nonce
            or nonce != nonce.strip()
        ):
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        expected_bytes = expected_nonce.encode(
            "utf-8"
        )
        received_bytes = nonce.encode(
            "utf-8"
        )

        if (
            len(expected_bytes)
            != len(received_bytes)
        ):
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        import hmac

        if not hmac.compare_digest(
            expected_bytes,
            received_bytes,
        ):
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        return identity


    @staticmethod
    def _read_unverified_issuer(
        token: str,
    ) -> str:
        parts = token.split(".")

        if len(parts) != 3:
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        payload_segment = parts[1]

        try:
            padding = "=" * (
                -len(payload_segment) % 4
            )
            payload = base64.urlsafe_b64decode(
                payload_segment + padding
            )
            claims = json.loads(
                payload.decode("utf-8")
            )
        except (
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            ) from error

        if not isinstance(claims, dict):
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        issuer = claims.get("iss")

        if (
            not isinstance(issuer, str)
            or not issuer
            or issuer != issuer.strip()
        ):
            raise OIDCTokenInvalidError(
                "OIDC bearer token is invalid."
            )

        return issuer

    @staticmethod
    def _public_key_from_jwk(
        jwk: Mapping[str, object],
    ):
        if jwk.get("kty") != "RSA":
            raise OIDCTokenVerifierUnavailableError(
                "OIDC signing key is incompatible."
            )

        use = jwk.get("use")
        if use is not None and use != "sig":
            raise OIDCTokenVerifierUnavailableError(
                "OIDC signing key is incompatible."
            )

        key_ops = jwk.get("key_ops")
        if key_ops is not None:
            if (
                not isinstance(key_ops, list)
                or "verify" not in key_ops
            ):
                raise OIDCTokenVerifierUnavailableError(
                    "OIDC signing key is incompatible."
                )

        jwk_algorithm = jwk.get("alg")
        if (
            jwk_algorithm is not None
            and jwk_algorithm != RS256
        ):
            raise OIDCTokenVerifierUnavailableError(
                "OIDC signing key is incompatible."
            )

        modulus = jwk.get("n")
        exponent = jwk.get("e")

        if (
            not isinstance(modulus, str)
            or not modulus
            or not isinstance(exponent, str)
            or not exponent
        ):
            raise OIDCTokenVerifierUnavailableError(
                "OIDC signing key is malformed."
            )

        try:
            modulus_bytes = (
                PyJWTOIDCTokenVerifier
                ._decode_base64url_uint(
                    modulus
                )
            )
        except ValueError as error:
            raise OIDCTokenVerifierUnavailableError(
                "OIDC signing key is malformed."
            ) from error

        modulus_bits = int.from_bytes(
            modulus_bytes,
            "big",
        ).bit_length()

        if modulus_bits < MIN_RSA_MODULUS_BITS:
            raise OIDCTokenVerifierUnavailableError(
                "OIDC signing key is too weak."
            )

        try:
            return RSAAlgorithm.from_jwk(
                dict(jwk)
            )
        except (
            jwt.exceptions.InvalidKeyError,
            ValueError,
        ) as error:
            raise OIDCTokenVerifierUnavailableError(
                "OIDC signing key is malformed."
            ) from error

    @staticmethod
    def _decode_base64url_uint(
        value: str,
    ) -> bytes:
        try:
            padding = "=" * (
                -len(value) % 4
            )
            decoded = base64.urlsafe_b64decode(
                value + padding
            )
        except Exception as error:
            raise ValueError(
                "Invalid base64url integer."
            ) from error

        if not decoded:
            raise ValueError(
                "Invalid base64url integer."
            )

        return decoded

    @staticmethod
    def _audience_matches(
        claim,
        expected: str,
    ) -> bool:
        if isinstance(claim, str):
            return bool(claim) and claim == expected

        if isinstance(claim, list):
            if not claim:
                return False

            return any(
                isinstance(value, str)
                and bool(value)
                and value == expected
                for value in claim
            )

        return False
