from __future__ import annotations

from fastapi.testclient import TestClient

from product_api import app


CLIENT = TestClient(app)


def test_local_frontend_origin_is_allowed():
    response = CLIENT.options(
        "/v1/synthesis-demo",
        headers={
            "Origin":
                "http://localhost:3000",
            "Access-Control-Request-Method":
                "POST",
            "Access-Control-Request-Headers":
                "content-type",
        },
    )

    assert response.status_code == 200

    assert (
        response.headers.get(
            "access-control-allow-origin"
        )
        == "http://localhost:3000"
    )

    assert (
        response.headers.get(
            "access-control-allow-credentials"
        )
        == "true"
    )


def test_loopback_frontend_origin_is_allowed():
    response = CLIENT.options(
        "/v1/synthesis-demo",
        headers={
            "Origin":
                "http://127.0.0.1:3000",
            "Access-Control-Request-Method":
                "POST",
            "Access-Control-Request-Headers":
                "content-type",
        },
    )

    assert response.status_code == 200

    assert (
        response.headers.get(
            "access-control-allow-origin"
        )
        == "http://127.0.0.1:3000"
    )


def test_untrusted_origin_is_not_allowed():
    response = CLIENT.options(
        "/v1/synthesis-demo",
        headers={
            "Origin":
                "https://evil.example",
            "Access-Control-Request-Method":
                "POST",
            "Access-Control-Request-Headers":
                "content-type",
        },
    )

    assert response.status_code == 400

    assert (
        response.headers.get(
            "access-control-allow-origin"
        )
        is None
    )


def test_arbitrary_request_header_is_not_allowed():
    response = CLIENT.options(
        "/v1/synthesis-demo",
        headers={
            "Origin":
                "http://localhost:3000",
            "Access-Control-Request-Method":
                "POST",
            "Access-Control-Request-Headers":
                "x-solvyn-internal-login-secret",
        },
    )

    assert response.status_code == 400


def test_internal_secret_header_is_not_cors_allowlisted():
    response = CLIENT.options(
        "/v1/synthesis-demo",
        headers={
            "Origin":
                "http://localhost:3000",
            "Access-Control-Request-Method":
                "POST",
        },
    )

    allowed_headers = (
        response.headers.get(
            "access-control-allow-headers"
        )
        or ""
    ).lower()

    assert (
        "x-solvyn-internal-login-secret"
        not in allowed_headers
    )


def test_arbitrary_http_method_is_not_allowed():
    response = CLIENT.options(
        "/v1/synthesis-demo",
        headers={
            "Origin":
                "http://localhost:3000",
            "Access-Control-Request-Method":
                "TRACE",
        },
    )

    assert response.status_code == 400
