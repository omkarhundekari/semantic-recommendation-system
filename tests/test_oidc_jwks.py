from __future__ import annotations

import json
import threading

import pytest

from execution_evidence.oidc_jwks import (
    CachedOIDCJWKSProvider,
    OIDCJWKSFetcher,
    OIDCJWKSRefreshThrottledError,
    OIDCJWKSUnavailableError,
    RequestsOIDCJWKSFetcher,
)
from execution_evidence.oidc_provider_config import (
    OIDCProviderConfig,
)


PROVIDER_ID = (
    "idp_123e4567-e89b-42d3-a456-426614174000"
)


def _config():
    return OIDCProviderConfig(
        identity_provider_id=PROVIDER_ID,
        issuer="https://issuer.example",
        audience="solvyn-api",
        jwks_uri="https://issuer.example/jwks",
    )


class Clock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value


class Fetcher(OIDCJWKSFetcher):
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.calls = 0

    def fetch(self, config):
        self.calls += 1

        if len(self.snapshots) > 1:
            return tuple(
                self.snapshots.pop(0)
            )

        return tuple(self.snapshots[0])


def test_cached_key_does_not_refetch():
    clock = Clock()
    fetcher = Fetcher(
        [
            [{"kid": "one"}],
        ]
    )
    provider = CachedOIDCJWKSProvider(
        fetcher=fetcher,
        monotonic=clock,
    )

    assert (
        provider.load_key(
            config=_config(),
            kid="one",
        )["kid"]
        == "one"
    )
    assert (
        provider.load_key(
            config=_config(),
            kid="one",
        )["kid"]
        == "one"
    )
    assert fetcher.calls == 1


def test_unknown_kid_refresh_is_throttled():
    clock = Clock()
    fetcher = Fetcher(
        [
            [{"kid": "old"}],
        ]
    )
    provider = CachedOIDCJWKSProvider(
        fetcher=fetcher,
        monotonic=clock,
    )

    provider.load_key(
        config=_config(),
        kid="old",
    )

    with pytest.raises(
        OIDCJWKSRefreshThrottledError
    ):
        provider.load_key(
            config=_config(),
            kid="new",
        )

    assert fetcher.calls == 1


def test_unknown_kid_refreshes_after_minimum_interval():
    clock = Clock()
    fetcher = Fetcher(
        [
            [{"kid": "old"}],
            [{"kid": "new"}],
        ]
    )
    provider = CachedOIDCJWKSProvider(
        fetcher=fetcher,
        monotonic=clock,
    )

    provider.load_key(
        config=_config(),
        kid="old",
    )

    clock.value += 61

    assert (
        provider.load_key(
            config=_config(),
            kid="new",
        )["kid"]
        == "new"
    )
    assert fetcher.calls == 2


def test_refresh_is_single_flight():
    clock = Clock()
    gate = threading.Event()
    entered = threading.Event()

    class BlockingFetcher(OIDCJWKSFetcher):
        def __init__(self):
            self.calls = 0

        def fetch(self, config):
            self.calls += 1
            entered.set()
            gate.wait(timeout=2)
            return ({"kid": "one"},)

    fetcher = BlockingFetcher()
    provider = CachedOIDCJWKSProvider(
        fetcher=fetcher,
        monotonic=clock,
    )

    results = []

    def load():
        results.append(
            provider.load_key(
                config=_config(),
                kid="one",
            )["kid"]
        )

    first = threading.Thread(target=load)
    second = threading.Thread(target=load)

    first.start()
    entered.wait(timeout=2)
    second.start()
    gate.set()

    first.join(timeout=2)
    second.join(timeout=2)

    assert results == ["one", "one"]
    assert fetcher.calls == 1


class FakeResponse:
    def __init__(
        self,
        *,
        body,
        status_code=200,
        headers=None,
        is_redirect=False,
    ):
        self._body = body
        self.status_code = status_code
        self.headers = headers or {}
        self.is_redirect = is_redirect
        self.is_permanent_redirect = False
        self.closed = False

    def iter_content(self, chunk_size):
        yield self._body

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_requests_fetcher_disables_redirects_and_compression():
    response = FakeResponse(
        body=json.dumps(
            {"keys": [{"kid": "one"}]}
        ).encode("utf-8")
    )
    session = FakeSession(response)

    result = RequestsOIDCJWKSFetcher(
        session=session
    ).fetch(
        _config()
    )

    assert result[0]["kid"] == "one"

    _, kwargs = session.calls[0]

    assert kwargs["allow_redirects"] is False
    assert (
        kwargs["headers"]["Accept-Encoding"]
        == "identity"
    )
    assert kwargs["stream"] is True


def test_requests_fetcher_rejects_redirect():
    response = FakeResponse(
        body=b"",
        status_code=302,
        is_redirect=True,
    )

    with pytest.raises(
        OIDCJWKSUnavailableError,
        match="redirect",
    ):
        RequestsOIDCJWKSFetcher(
            session=FakeSession(response)
        ).fetch(
            _config()
        )


def test_requests_fetcher_rejects_compression():
    response = FakeResponse(
        body=b"",
        headers={
            "Content-Encoding": "gzip"
        },
    )

    with pytest.raises(
        OIDCJWKSUnavailableError,
        match="Compressed",
    ):
        RequestsOIDCJWKSFetcher(
            session=FakeSession(response)
        ).fetch(
            _config()
        )


def test_requests_fetcher_rejects_too_many_keys():
    payload = {
        "keys": [
            {"kid": str(index)}
            for index in range(21)
        ]
    }

    response = FakeResponse(
        body=json.dumps(payload).encode("utf-8")
    )

    with pytest.raises(
        OIDCJWKSUnavailableError,
        match="invalid key set",
    ):
        RequestsOIDCJWKSFetcher(
            session=FakeSession(response)
        ).fetch(
            _config()
        )
