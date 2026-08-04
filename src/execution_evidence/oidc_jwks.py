from __future__ import annotations

import json
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple

import requests

from execution_evidence.oidc_provider_config import (
    OIDCProviderConfig,
)


MAX_JWKS_RESPONSE_BYTES = 1024 * 1024
MAX_JWKS_KEYS = 20
JWKS_CACHE_TTL_SECONDS = 10 * 60
JWKS_UNKNOWN_KID_REFRESH_MIN_SECONDS = 60
JWKS_CONNECT_TIMEOUT_SECONDS = 2.0
JWKS_READ_TIMEOUT_SECONDS = 5.0


class OIDCJWKSError(RuntimeError):
    pass


class OIDCJWKSUnavailableError(
    OIDCJWKSError
):
    pass


class OIDCJWKSKeyNotFoundError(
    OIDCJWKSError
):
    pass


class OIDCJWKSRefreshThrottledError(
    OIDCJWKSError
):
    pass


class OIDCJWKSFetcher(ABC):
    @abstractmethod
    def fetch(
        self,
        config: OIDCProviderConfig,
    ) -> Tuple[Mapping[str, object], ...]:
        raise NotImplementedError


class RequestsOIDCJWKSFetcher(
    OIDCJWKSFetcher
):
    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._session = session or requests.Session()

    def fetch(
        self,
        config: OIDCProviderConfig,
    ) -> Tuple[Mapping[str, object], ...]:
        try:
            response = self._session.get(
                config.jwks_uri,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                },
                allow_redirects=False,
                stream=True,
                timeout=(
                    JWKS_CONNECT_TIMEOUT_SECONDS,
                    JWKS_READ_TIMEOUT_SECONDS,
                ),
            )
        except requests.RequestException as error:
            raise OIDCJWKSUnavailableError(
                "OIDC JWKS endpoint is unavailable."
            ) from error

        try:
            if response.is_redirect or response.is_permanent_redirect:
                raise OIDCJWKSUnavailableError(
                    "OIDC JWKS redirects are not allowed."
                )

            if response.status_code != 200:
                raise OIDCJWKSUnavailableError(
                    "OIDC JWKS endpoint returned an "
                    "unexpected status."
                )

            content_encoding = response.headers.get(
                "Content-Encoding"
            )

            if (
                content_encoding is not None
                and content_encoding.lower() != "identity"
            ):
                raise OIDCJWKSUnavailableError(
                    "Compressed OIDC JWKS responses are "
                    "not accepted."
                )

            content_length = response.headers.get(
                "Content-Length"
            )

            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except ValueError as error:
                    raise OIDCJWKSUnavailableError(
                        "OIDC JWKS Content-Length is "
                        "invalid."
                    ) from error

                if (
                    declared_size < 0
                    or declared_size
                    > MAX_JWKS_RESPONSE_BYTES
                ):
                    raise OIDCJWKSUnavailableError(
                        "OIDC JWKS response exceeds the "
                        "maximum allowed size."
                    )

            body = bytearray()

            for chunk in response.iter_content(
                chunk_size=16 * 1024
            ):
                if not chunk:
                    continue

                if (
                    len(body) + len(chunk)
                    > MAX_JWKS_RESPONSE_BYTES
                ):
                    raise OIDCJWKSUnavailableError(
                        "OIDC JWKS response exceeds the "
                        "maximum allowed size."
                    )

                body.extend(chunk)

            try:
                payload = json.loads(
                    bytes(body).decode("utf-8")
                )
            except (
                UnicodeDecodeError,
                json.JSONDecodeError,
            ) as error:
                raise OIDCJWKSUnavailableError(
                    "OIDC JWKS response is not valid JSON."
                ) from error

            if not isinstance(payload, dict):
                raise OIDCJWKSUnavailableError(
                    "OIDC JWKS response must be an object."
                )

            keys = payload.get("keys")

            if (
                not isinstance(keys, list)
                or not keys
                or len(keys) > MAX_JWKS_KEYS
            ):
                raise OIDCJWKSUnavailableError(
                    "OIDC JWKS response contains an "
                    "invalid key set."
                )

            normalized = []

            for key in keys:
                if not isinstance(key, dict):
                    raise OIDCJWKSUnavailableError(
                        "OIDC JWKS keys must be objects."
                    )

                normalized.append(dict(key))

            return tuple(normalized)
        finally:
            response.close()


@dataclass(frozen=True)
class _CachedJWKS:
    keys: Tuple[Mapping[str, object], ...]
    fetched_at: float


class CachedOIDCJWKSProvider:
    def __init__(
        self,
        *,
        fetcher: OIDCJWKSFetcher,
        monotonic=time.monotonic,
    ) -> None:
        self._fetcher = fetcher
        self._monotonic = monotonic
        self._state_lock = threading.RLock()
        self._cache: Dict[str, _CachedJWKS] = {}
        self._refresh_locks: Dict[
            str,
            threading.Lock,
        ] = {}

    def load_key(
        self,
        *,
        config: OIDCProviderConfig,
        kid: str,
    ) -> Mapping[str, object]:
        cached = self._load_fresh_cache(config)

        if cached is None:
            cached = self._refresh(
                config=config,
                force=False,
            )

        key = self._select_key(
            cached.keys,
            kid,
        )

        if key is not None:
            return key

        refreshed = self._refresh_for_unknown_kid(
            config=config,
            kid=kid,
        )

        key = self._select_key(
            refreshed.keys,
            kid,
        )

        if key is None:
            raise OIDCJWKSKeyNotFoundError(
                "OIDC signing key was not found."
            )

        return key

    def _load_fresh_cache(
        self,
        config: OIDCProviderConfig,
    ) -> Optional[_CachedJWKS]:
        now = self._monotonic()

        with self._state_lock:
            cached = self._cache.get(
                config.identity_provider_id
            )

            if cached is None:
                return None

            if (
                now - cached.fetched_at
                >= JWKS_CACHE_TTL_SECONDS
            ):
                return None

            return cached

    def _refresh_for_unknown_kid(
        self,
        *,
        config: OIDCProviderConfig,
        kid: str,
    ) -> _CachedJWKS:
        lock = self._refresh_lock_for(
            config.identity_provider_id
        )

        with lock:
            now = self._monotonic()

            with self._state_lock:
                cached = self._cache.get(
                    config.identity_provider_id
                )

            if cached is not None:
                existing = self._select_key(
                    cached.keys,
                    kid,
                )

                if existing is not None:
                    return cached

                if (
                    now - cached.fetched_at
                    < JWKS_UNKNOWN_KID_REFRESH_MIN_SECONDS
                ):
                    raise OIDCJWKSRefreshThrottledError(
                        "OIDC signing-key refresh is "
                        "temporarily throttled."
                    )

            return self._fetch_and_store(
                config=config,
                fetched_at=now,
            )

    def _refresh(
        self,
        *,
        config: OIDCProviderConfig,
        force: bool,
    ) -> _CachedJWKS:
        lock = self._refresh_lock_for(
            config.identity_provider_id
        )

        with lock:
            if not force:
                cached = self._load_fresh_cache(
                    config
                )

                if cached is not None:
                    return cached

            return self._fetch_and_store(
                config=config,
                fetched_at=self._monotonic(),
            )

    def _fetch_and_store(
        self,
        *,
        config: OIDCProviderConfig,
        fetched_at: float,
    ) -> _CachedJWKS:
        keys = self._fetcher.fetch(config)

        cached = _CachedJWKS(
            keys=keys,
            fetched_at=fetched_at,
        )

        with self._state_lock:
            self._cache[
                config.identity_provider_id
            ] = cached

        return cached

    def _refresh_lock_for(
        self,
        provider_id: str,
    ) -> threading.Lock:
        with self._state_lock:
            lock = self._refresh_locks.get(
                provider_id
            )

            if lock is None:
                lock = threading.Lock()
                self._refresh_locks[
                    provider_id
                ] = lock

            return lock

    @staticmethod
    def _select_key(
        keys: Tuple[Mapping[str, object], ...],
        kid: str,
    ) -> Optional[Mapping[str, object]]:
        matches = [
            key
            for key in keys
            if key.get("kid") == kid
        ]

        if len(matches) > 1:
            raise OIDCJWKSUnavailableError(
                "OIDC JWKS contains duplicate signing "
                "key identifiers."
            )

        if not matches:
            return None

        return matches[0]
