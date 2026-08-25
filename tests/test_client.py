"""
Unit tests for KalbioAPIError and the HTTP-layer error semantics of KaleidoscopeClient.

Test coverage:
    - KalbioAPIError: attribute population, message format, bytes decoding
    - KaleidoscopeClient._get: returns None on 404, raises KalbioAPIError on other 4xx/5xx
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from json import JSONDecodeError

import pytest
from pytest_mock import MockerFixture

from kalbio.client import (
    _require_response_body,
    _TokenResponse,
    KalbioAPIError,
    KalbioResponseError,
    KaleidoscopeClient,
)


# ==================== KalbioAPIError ====================


def test_kalbio_api_error_populates_attributes():
    """KalbioAPIError stores method, url, status_code, response_body on the instance."""
    err = KalbioAPIError("PUT", "/foo/123", 400, b'{"code":"BAD"}')

    assert err.method == "PUT"
    assert err.url == "/foo/123"
    assert err.status_code == 400
    assert err.response_body == b'{"code":"BAD"}'


def test_kalbio_api_error_message_decodes_bytes():
    """Default str(err) decodes bytes response_body as utf-8 (no leading b'...')."""
    err = KalbioAPIError("PUT", "/foo", 400, b'{"message":"bad input"}')

    msg = str(err)
    assert msg == 'PUT /foo failed with status 400: {"message":"bad input"}'
    assert "b'" not in msg


def test_kalbio_api_error_message_handles_str_body():
    """Non-bytes response_body is included as-is."""
    err = KalbioAPIError("GET", "/x", 500, "Internal Server Error")

    assert str(err) == "GET /x failed with status 500: Internal Server Error"


# ==================== _get error semantics ====================


@pytest.fixture(name="unmocked_client")
def fixture_unmocked_client(mocker: MockerFixture) -> KaleidoscopeClient:
    """Real KaleidoscopeClient with auth bypassed but no HTTP-method mocks."""
    mocker.patch.object(
        KaleidoscopeClient, "_get_auth_token", return_value="fake-token"
    )
    client = KaleidoscopeClient("test-id", "test-secret", "https://example.test")
    client._update_auth_tokens(
        _TokenResponse(
            access_token="access_token",
            refresh_token="refresh_token",
            expires_in=int(1e9),
        )
    )
    return client


def test_get_returns_none_on_404(
    mocker: MockerFixture, unmocked_client: KaleidoscopeClient
):
    """A 404 from the server returns None (preserves "not found" semantics)."""
    mock_resp = mocker.Mock(status_code=404, content=b"not found")
    mocker.patch("kalbio.client.requests.get", return_value=mock_resp)

    result = unmocked_client._get("/something/missing")

    assert result is None


def test_get_raises_on_non_404_4xx(
    mocker: MockerFixture, unmocked_client: KaleidoscopeClient
):
    """A non-404 4xx response raises KalbioAPIError with method/url/status/body populated."""
    mock_resp = mocker.Mock(status_code=400, content=b'{"code":"BAD"}')
    mocker.patch("kalbio.client.requests.get", return_value=mock_resp)

    with pytest.raises(KalbioAPIError) as exc_info:
        unmocked_client._get("/bad/request")

    err = exc_info.value
    assert err.method == "GET"
    assert err.url.endswith("/bad/request")
    assert err.status_code == 400
    assert err.response_body == b'{"code":"BAD"}'


# ==================== empty body vs. broken body ====================


def _decode_failing_response(mocker: MockerFixture, status_code: int, content: bytes):
    """A mock response whose ``.json()`` raises like a non-JSON body would."""
    resp = mocker.Mock(status_code=status_code, content=content)
    resp.json.side_effect = JSONDecodeError("Expecting value", "", 0)
    return resp


def test_get_returns_none_on_empty_body(
    mocker: MockerFixture, unmocked_client: KaleidoscopeClient
):
    """A 2xx with an empty body decodes to None (legitimate no-content)."""
    resp = _decode_failing_response(mocker, 200, b"")
    mocker.patch("kalbio.client.requests.get", return_value=resp)

    assert unmocked_client._get("/empty") is None


def test_get_raises_on_undecodable_body(
    mocker: MockerFixture, unmocked_client: KaleidoscopeClient
):
    """A 2xx with a non-empty, non-JSON body raises instead of returning None."""
    resp = _decode_failing_response(mocker, 200, b"<html>oops</html>")
    mocker.patch("kalbio.client.requests.get", return_value=resp)

    with pytest.raises(KalbioResponseError) as exc_info:
        unmocked_client._get("/broken")

    assert exc_info.value.response_body == b"<html>oops</html>"


def test_undecodable_body_logs_warning(
    mocker: MockerFixture,
    unmocked_client: KaleidoscopeClient,
    caplog: pytest.LogCaptureFixture,
):
    """The undecodable-body path is visible in logs, not silent."""
    resp = _decode_failing_response(mocker, 200, b"boom")
    mocker.patch("kalbio.client.requests.get", return_value=resp)

    with caplog.at_level(logging.WARNING, logger="kalbio.client"):
        with pytest.raises(KalbioResponseError):
            unmocked_client._get("/broken")

    assert "undecodable body" in caplog.text


@pytest.mark.parametrize("http_method", ["post", "put", "delete"])
def test_write_methods_return_none_on_empty_body(
    mocker: MockerFixture, unmocked_client: KaleidoscopeClient, http_method: str
):
    """POST/PUT/DELETE with an empty 2xx body return None (no content)."""
    resp = _decode_failing_response(mocker, 200, b"")
    mocker.patch(f"kalbio.client.requests.{http_method}", return_value=resp)

    caller = getattr(unmocked_client, f"_{http_method}")
    if http_method == "delete":
        assert caller("/thing/1") is None
    else:
        assert caller("/thing", {}) is None


@pytest.mark.parametrize("http_method", ["post", "put", "delete"])
def test_write_methods_raise_on_undecodable_body(
    mocker: MockerFixture, unmocked_client: KaleidoscopeClient, http_method: str
):
    """POST/PUT/DELETE with a non-empty, non-JSON 2xx body raise KalbioResponseError."""
    resp = _decode_failing_response(mocker, 200, b"not json")
    mocker.patch(f"kalbio.client.requests.{http_method}", return_value=resp)

    caller = getattr(unmocked_client, f"_{http_method}")
    with pytest.raises(KalbioResponseError):
        if http_method == "delete":
            caller("/thing/1")
        else:
            caller("/thing", {})


# ==================== _require_response_body ====================


def test_require_response_body_passes_through_non_none():
    """A present body (including a falsy empty list) is returned unchanged."""
    assert _require_response_body("GET", "/x", [{"a": 1}]) == [{"a": 1}]
    assert _require_response_body("GET", "/x", []) == []


def test_require_response_body_raises_on_none():
    """A None body raises KalbioResponseError naming the method and endpoint."""
    with pytest.raises(KalbioResponseError) as exc_info:
        _require_response_body("GET", "/programs", None)

    err = exc_info.value
    assert err.method == "GET"
    assert err.url == "/programs"
    assert err.response_body is None


# ==================== token refresh / re-auth fallback ====================


@pytest.fixture(name="auth_client")
def fixture_auth_client() -> KaleidoscopeClient:
    """Client holding a refresh token but no valid access token yet."""
    client = KaleidoscopeClient("test-id", "test-secret", "https://example.test")
    client._refresh_token = "stored-refresh-token"
    return client


def test_refresh_falls_back_to_client_credentials_on_4xx(
    mocker: MockerFixture, auth_client: KaleidoscopeClient
):
    """A 4xx from the refresh grant re-auths via client_credentials instead of raising.

    A revoked/expired refresh token can never succeed again, so raising here is
    what previously left the client permanently unable to authenticate.
    """
    mocker.patch(
        "kalbio.client.requests.post",
        return_value=mocker.Mock(status_code=401, content=b"invalid_grant"),
    )
    get_auth = mocker.patch.object(auth_client, "_get_auth_token")

    auth_client._refresh_auth_token()

    get_auth.assert_called_once()


def test_refresh_raises_on_5xx(
    mocker: MockerFixture, auth_client: KaleidoscopeClient
):
    """A 5xx is a transient server error: surface it, don't re-auth."""
    mocker.patch(
        "kalbio.client.requests.post",
        return_value=mocker.Mock(status_code=503, content=b"unavailable"),
    )
    get_auth = mocker.patch.object(auth_client, "_get_auth_token")

    with pytest.raises(RuntimeError):
        auth_client._refresh_auth_token()

    get_auth.assert_not_called()


def test_refresh_stores_rotated_tokens_on_success(
    mocker: MockerFixture, auth_client: KaleidoscopeClient
):
    """A successful refresh persists the rotated access/refresh token pair."""
    mocker.patch(
        "kalbio.client.requests.post",
        return_value=mocker.Mock(
            status_code=200,
            json=lambda: {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            },
        ),
    )

    auth_client._refresh_auth_token()

    assert auth_client._access_token == "new-access"
    assert auth_client._refresh_token == "new-refresh"


def test_refresh_without_stored_token_uses_client_credentials(
    mocker: MockerFixture, auth_client: KaleidoscopeClient
):
    """With no refresh token stored, refresh goes straight to client_credentials."""
    auth_client._refresh_token = None
    post = mocker.patch("kalbio.client.requests.post")
    get_auth = mocker.patch.object(auth_client, "_get_auth_token")

    auth_client._refresh_auth_token()

    get_auth.assert_called_once()
    post.assert_not_called()


def test_concurrent_get_headers_refreshes_once(
    mocker: MockerFixture, auth_client: KaleidoscopeClient
):
    """Concurrent callers with an expired token trigger exactly one refresh.

    Presenting a rotated refresh token twice makes the server revoke the whole
    token family, so the lock must collapse a burst of callers into one refresh.
    """
    refresh_calls = []

    def fake_refresh():
        refresh_calls.append(1)
        time.sleep(0.05)  # widen the window for a second caller to race in
        auth_client._access_token = "refreshed"
        auth_client._auth_refresh_before = datetime.now() + timedelta(hours=1)

    mocker.patch.object(auth_client, "_refresh_auth_token", side_effect=fake_refresh)

    thread_count = 8
    start = threading.Barrier(thread_count)

    def worker():
        start.wait()
        auth_client._get_headers()

    threads = [threading.Thread(target=worker) for _ in range(thread_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(refresh_calls) == 1
