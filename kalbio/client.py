"""Kaleidoscope API Client Module.

This module provides the main client class for interacting with the Kaleidoscope API.

The KaleidoscopeClient provides access to various service endpoints including:

- activities: Manage activities
- imports: Import data into Kaleidoscope
- programs: Manage programs
- entity_types: Manage entity types
- records: Manage records
- fields: Manage fields
- experiments: Manage experiments
- record_views: Manage record views
- exports: Export data from Kaleidoscope

Attributes:
    PROD_API_URL (str): The production URL for the Kaleidoscope API.
    TIMEOUT_MAXIMUM (int): Maximum timeout for API requests in seconds.

Example:
    ```python
        # instantiate client object
        client = KaleidoscopeClient(
            client_id="your_client_id",
            client_secret="your_client_secret"
        )

        # retrieve activities
        programs = client.activities.get_activities()
    ```
"""

import logging
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
import json
from json import JSONDecodeError
import requests
import urllib
from typing import Any, BinaryIO, Dict, Iterator, List, Optional

from kalbio._base import _ApiModel
from kalbio._cache import clear_service_caches

_logger = logging.getLogger(__name__)

PROD_API_URL = "https://api.kaleidoscope.bio"
"""The production URL for the Kaleidoscope API.

This is the default url used for the `KaleidoscopeClient`, in the event
no url is provided in the `KaleidoscopeClient`'s initialization"""

TIMEOUT_MAXIMUM = 300
"""Maximum timeout for API requests in seconds."""


class KalbioAPIError(Exception):
    """Raised when a Kaleidoscope API request returns a 4xx or 5xx response.

    Attributes:
        method: HTTP method of the failed request (e.g. ``"PUT"``).
        url: Relative endpoint path (e.g. ``"/activity_definitions/abc"``).
        status_code: HTTP status code returned by the server.
        response_body: Raw response body. Usually a Kaleidoscope structured
            error (JSON with ``code``/``message`` or Zod validation details);
            occasionally bytes/HTML for unexpected failures.
    """

    def __init__(
        self,
        method: str,
        url: str,
        status_code: int,
        response_body: Any,
    ):
        self.method = method
        self.url = url
        self.status_code = status_code
        self.response_body = response_body
        if isinstance(response_body, bytes):
            body_str = response_body.decode("utf-8", errors="replace")
        else:
            body_str = str(response_body)
        super().__init__(
            f"{method} {url} failed with status {status_code}: {body_str}"
        )


class KalbioResponseError(Exception):
    """Raised when a request succeeds (2xx) but the body is unusable.

    Distinct from ``KalbioAPIError`` (a 4xx/5xx status): here the server
    accepted the request but returned something the client cannot act on — for
    example a push that returned no ``import_id``. The raw body is kept on
    ``response_body`` so callers can see what actually came back.

    Attributes:
        method: HTTP method of the request (e.g. ``"POST"``).
        url: Relative endpoint path.
        response_body: Raw response body returned by the server.
    """

    def __init__(self, method: str, url: str, response_body: Any):
        self.method = method
        self.url = url
        self.response_body = response_body
        super().__init__(
            f"{method} {url} returned an unexpected response body: {response_body!r}"
        )


def _require_response_body(method: str, url: str, resp: Any) -> Any:
    """Return ``resp`` unless a client helper collapsed it to ``None``.

    The HTTP helpers return ``None`` when an endpoint 404s or sends an empty
    body. Callers that require content — a collection to validate, an object to
    construct — pass their result through this so a missing body fails with a
    clear ``KalbioResponseError`` naming the endpoint instead of an opaque
    ``ValidationError`` or ``TypeError`` further downstream.

    Args:
        method: HTTP method used for the request (for error context).
        url: Endpoint the request was sent to.
        resp: The value returned by the HTTP helper.

    Returns:
        Any: ``resp`` unchanged, guaranteed non-``None``.

    Raises:
        KalbioResponseError: If ``resp`` is ``None``.
    """
    if resp is None:
        raise KalbioResponseError(method, url, resp)
    return resp


_env_client_id = os.getenv("KALEIDOSCOPE_API_CLIENT_ID")
_env_client_secret = os.getenv("KALEIDOSCOPE_API_CLIENT_SECRET")


class _TokenResponse(_ApiModel):
    """OAuth token response payload returned by Kaleidoscope auth endpoints.

    Attributes:
        access_token (str): Bearer token used for authenticated API calls.
        refresh_token (str): Token used to obtain a new access token when the current one expires.
        expires_in (int): Lifetime of the access token in seconds.
    """

    access_token: str
    refresh_token: str
    expires_in: int


class KaleidoscopeClient:
    """A client for interacting with the Kaleidoscope API.

    This client provides a high-level interface to various Kaleidoscope services including
    imports, programs, entity types, records, fields, tasks, experiments, record views, and exports.
    It handles authentication using API key credentials and provides methods for making HTTP requests
    (GET, POST, PUT) to the API endpoints.

    Attributes:
        activities (ActivitiesService): Service for managing activities.
        dashboards (DashboardsService): Service for managing dashboards.
        workspace (WorkspaceService): Service for workspace-related operations.
        programs (ProgramsService): Service for managing programs.
        labels (LabelsService): Service for managing labels.
        entity_types (EntityTypesService): Service for managing entity types.
        entity_fields (EntityFieldsService): Service for managing entity fields.
        records (RecordsService): Service for managing records.
        record_views (RecordViewsService): Service for managing record views.
        imports (ImportsService): Service for managing data imports.
        exports (ExportsService): Service for managing data exports.
        property_fields (PropertyFieldsService): Service for managing property fields.

    Example:
        ```python
        client = KaleidoscopeClient(
            client_id="your_api_client_id",
            client_secret="your_api_client_secret"
        )
        # Use the client to interact with various services
        programs = client.activities.get_activities()

        # For applications behind Google Cloud IAP:
        client = KaleidoscopeClient(
            client_id="your_api_client_id",
            client_secret="your_api_client_secret",
            iap_client_id="your_iap_client_id.apps.googleusercontent.com"
        )
        ```
    """

    _client_id: str
    _client_secret: str
    additional_headers: dict
    _iap_client_id: Optional[str]

    _refresh_token: Optional[str] = None
    _access_token: Optional[str] = None
    _auth_refresh_before: Optional[datetime] = None

    _iap_token: Optional[str] = None
    _iap_refresh_before: Optional[datetime] = None

    _auth_lock: threading.Lock

    def __init__(
        self,
        client_id: Optional[str] = _env_client_id,
        client_secret: Optional[str] = _env_client_secret,
        url: str = PROD_API_URL,
        additional_headers: Optional[dict] = None,
        iap_client_id: Optional[str] = None,
        verify_ssl: bool = True,
    ):
        """Initialize the Kaleidoscope API client.

        Sets up the client with API credentials and optional API URL, and initializes
        service interfaces for interacting with different API endpoints.

        Args:
            client_id (str): The API client ID for authentication.
            client_secret (str): The API client secret for authentication.
            url (Optional[str]): The base URL for the API. Defaults to the production
                API URL if not provided.
            iap_client_id (Optional[str]): The OAuth client ID for Google Cloud
                Identity-Aware Proxy. If provided, the client will automatically
                fetch and refresh IAP tokens. Requires the `google-auth` package.

        Example:
            ```python
            # Using explicit credentials
            client = KaleidoscopeClient(client_id="id", client_secret="secret")

            # Or rely on environment variables KALEIDOSCOPE_API_CLIENT_ID/SECRET
            client = KaleidoscopeClient()

            # For applications behind Google Cloud IAP
            client = KaleidoscopeClient(
                client_id="id",
                client_secret="secret",
                iap_client_id="your_iap_client_id.apps.googleusercontent.com"
            )
            ```
        """
        if client_id is None:
            raise ValueError(
                'No client_id provided and "KALEIDOSCOPE_API_CLIENT_ID" was not found in the environment.'
            )

        if client_secret is None:
            raise ValueError(
                'No client_secret provided and "KALEIDOSCOPE_API_CLIENT_SECRET" was not found in the environment.'
            )

        from kalbio.activities import ActivitiesService
        from kalbio.dashboards import DashboardsService
        from kalbio.entity_fields import EntityFieldsService
        from kalbio.entity_types import EntityTypesService
        from kalbio.exports import ExportsService
        from kalbio.files import FilesService
        from kalbio.imports import ImportsService
        from kalbio.labels import LabelsService
        from kalbio.programs import ProgramsService
        from kalbio.property_fields import PropertyFieldsService
        from kalbio.record_views import RecordViewsService
        from kalbio.records import RecordsService
        from kalbio.registration import RegistrationService
        from kalbio.result_table_templates import ResultTableTemplatesService
        from kalbio.workspace import WorkspaceService

        self._api_url = url
        self._cache_state = threading.local()

        self.activities = ActivitiesService(self)
        self.dashboards = DashboardsService(self)
        self.entity_fields = EntityFieldsService(self)
        self.entity_types = EntityTypesService(self)
        self.exports = ExportsService(self)
        self.files = FilesService(self)
        self.imports = ImportsService(self)
        self.labels = LabelsService(self)
        self.property_fields = PropertyFieldsService(self)
        self.programs = ProgramsService(self)
        self.record_views = RecordViewsService(self)
        self.records = RecordsService(self)
        self.registration = RegistrationService(self)
        self.result_table_templates = ResultTableTemplatesService(self)
        self.workspace = WorkspaceService(self)

        self._client_id = client_id
        self._client_secret = client_secret
        self.additional_headers = additional_headers or {}
        self._iap_client_id = iap_client_id
        self._verify_ssl = verify_ssl
        self._auth_lock = threading.Lock()

    def _services(self) -> List[Any]:
        """Every service instance attached to this client."""
        return [
            value for value in vars(self).values() if getattr(value, "_client", None) is self
        ]

    def clear_caches(self) -> None:
        """Drop every cached read across all services.

        Call this when data has changed outside the client (or through another
        client) and cached results may be stale.

        Example:
            ```python
            client.clear_caches()
            programs = client.programs.get_programs()  # refetched from the server
            ```
        """
        for service in self._services():
            clear_service_caches(service)

    def _is_cache_disabled(self) -> bool:
        """Whether the calling thread is inside a `cache_disabled` block."""
        return getattr(self._cache_state, "disabled", False)

    @contextmanager
    def cache_disabled(self) -> Iterator[None]:
        """Bypass all read caches for the duration of the block.

        Reads inside the block always hit the server and refresh the cache. The
        flag is per-thread, so a client shared across threads only bypasses
        caching on the thread that entered the block. Nested blocks restore the
        previous state on exit.

        Example:
            ```python
            with client.cache_disabled():
                fields = client.entity_fields.get_key_fields()  # always fresh
            ```
        """
        previous = getattr(self._cache_state, "disabled", False)
        self._cache_state.disabled = True
        try:
            yield
        finally:
            self._cache_state.disabled = previous

    def _refresh_iap_token(self):
        """Fetch or refresh the IAP ID token.

        Uses google-auth to obtain an ID token for the configured IAP client ID.
        Supports both service account credentials and user credentials from
        `gcloud auth application-default login`.

        Raises:
            ImportError: If google-auth is not installed.
            google.auth.exceptions.DefaultCredentialsError: If no valid credentials found.
        """
        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import id_token
        except ImportError:
            raise ImportError(
                "The 'google-auth' package is required for IAP authentication. "
                "Install it with: pip install google-auth or re-install kalbio with the iap option: "
                "pip install kalbio[iap]"
            )
        self._iap_token = id_token.fetch_id_token(Request(), self._iap_client_id)
        # IAP tokens typically expire in 1 hour; refresh 10 minutes early
        self._iap_refresh_before = datetime.now() + timedelta(minutes=50)

    def _update_auth_tokens(self, resp: _TokenResponse):
        """Persist access and refresh tokens and compute the next refresh time.

        Args:
            resp: Token payload returned from the auth endpoint.
        """
        self._access_token = resp.access_token
        self._refresh_token = resp.refresh_token
        self._auth_refresh_before = datetime.now() + timedelta(
            seconds=resp.expires_in - (60 * 10)  # add a 10 minute buffer
        )

    def _get_auth_token(self):
        """Fetch an access token using client credentials.

        Raises:
            RuntimeError: If the auth endpoint responds with an error status code.
        """
        auth_resp = requests.post(
            self._api_url + "/auth/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            headers={**self._get_iap_headers(), **self.additional_headers},
            timeout=TIMEOUT_MAXIMUM,
            verify=self._verify_ssl,
        )
        if auth_resp.status_code >= 400:
            raise RuntimeError(
                f"Could not connect to server with client_id {self._client_id}: {auth_resp.content}"
            )

        self._update_auth_tokens(_TokenResponse.model_validate(auth_resp.json()))

    def _refresh_auth_token(self):
        """Refresh the access token using the stored refresh token.

        A 4xx from the refresh grant means the refresh token is expired, revoked,
        or family-revoked and can never succeed again, so fall back to a fresh
        client-credentials grant rather than failing every subsequent call.

        Raises:
            RuntimeError: If the auth endpoint responds with a server error (5xx).
        """
        if self._refresh_token is None:
            return self._get_auth_token()

        auth_resp = requests.post(
            self._api_url + "/auth/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            },
            headers={**self._get_iap_headers(), **self.additional_headers},
            timeout=TIMEOUT_MAXIMUM,
            verify=self._verify_ssl,
        )
        if 400 <= auth_resp.status_code < 500:
            return self._get_auth_token()
        if auth_resp.status_code >= 500:
            raise RuntimeError(f"Could not refresh access token: {auth_resp.content}")

        self._update_auth_tokens(_TokenResponse.model_validate(auth_resp.json()))

    def _get_iap_headers(self) -> dict:
        """Build IAP headers, refreshing tokens if needed.

        Returns:
            dict: HTTP header for IAP (Proxy-Authorization)
        """
        headers = {}
        if self._iap_client_id:
            if (
                self._iap_refresh_before is None
                or datetime.now() > self._iap_refresh_before
            ):
                self._refresh_iap_token()
            headers["Authorization"] = f"Bearer {self._iap_token}"

        return headers

    def _auth_token_expired(self) -> bool:
        """Whether the access token is missing or past its refresh deadline."""
        return (
            self._auth_refresh_before is None
            or datetime.now() > self._auth_refresh_before
        )

    def _get_headers(self) -> dict:
        """Build authorization headers, refreshing tokens if needed.

        Returns:
            dict: HTTP headers including `Authorization`, `Content-Type`,
                and optionally `Proxy-Authorization` for IAP.
        """
        if self._auth_token_expired():
            with self._auth_lock:
                # Re-check under the lock: another thread may have already
                # refreshed while this one waited. The server rotates refresh
                # tokens and revokes the whole family if a rotated one is
                # presented again, so refresh must happen exactly once per expiry.
                if self._auth_token_expired():
                    self._refresh_auth_token()

        headers = {
            "Content-Type": "application/json",
            "X-Kal-Authorization": f"Bearer {self._access_token}",
            **self._get_iap_headers(),
            **self.additional_headers,
        }

        return headers

    def _json_body_or_none(
        self, method: str, url: str, resp: requests.Response
    ) -> Any:
        """Decode a successful response body as JSON, telling empty from broken.

        An empty body is a legitimate no-content success and returns ``None``. A
        non-empty body that cannot be decoded means the server returned a 2xx
        with a payload the client cannot use, which is surfaced as
        ``KalbioResponseError`` rather than silently collapsed to ``None``.

        Args:
            method: HTTP method of the request, used for logging and error context.
            url: Endpoint the request was sent to.
            resp: Response whose body should be decoded.

        Returns:
            Any: The decoded JSON value, or ``None`` when the body is empty.

        Raises:
            KalbioResponseError: If the body is non-empty but not valid JSON.
        """
        try:
            return resp.json()
        except JSONDecodeError:
            if not resp.content.strip():
                _logger.debug(
                    "%s %s returned an empty body; treating as no content",
                    method,
                    url,
                )
                return None
            _logger.warning(
                "%s %s returned a 2xx response with an undecodable body: %r",
                method,
                url,
                resp.content,
            )
            raise KalbioResponseError(method, url, resp.content)

    def _post(self, url: str, payload: dict) -> Any:
        """Send a POST request to the specified URL with the given payload.

        Args:
            url (str): The endpoint URL (relative to the API base URL) to send the
                POST request to.
            payload (dict): The data to be sent in the body of the POST request.
                Should be serializable to JSON.

        Returns:
            Any: The decoded JSON response, or None if the response body is empty.

        Raises:
            KalbioAPIError: If the API request returns a 4xx or 5xx response.
            KalbioResponseError: If the request succeeds but the body is non-empty
                and cannot be decoded as JSON.
            Exception: Any exception that may be raised by ``requests.post``.
        """

        resp = requests.post(
            self._api_url + url,
            data=json.dumps(payload),
            headers=self._get_headers(),
            timeout=TIMEOUT_MAXIMUM,
            verify=self._verify_ssl,
        )
        if resp.status_code >= 400:
            raise KalbioAPIError("POST", url, resp.status_code, resp.content)
        return self._json_body_or_none("POST", url, resp)

    def _post_no_content(self, url: str, payload: dict) -> bool:
        """Send a POST request expecting a 204 No Content response.

        Args:
            url (str): The endpoint URL (relative to the API base URL).
            payload (dict): The data to be sent in the body of the POST request.
                Should be serializable to JSON.

        Returns:
            bool: True if the request succeeded (status < 400), False otherwise.

        Raises:
            Exception: Any exception that may be raised by ``requests.post``
        """

        resp = requests.post(
            self._api_url + url,
            data=json.dumps(payload),
            headers=self._get_headers(),
            timeout=TIMEOUT_MAXIMUM,
            verify=self._verify_ssl,
        )
        if resp.status_code >= 400:
            raise KalbioAPIError("POST", url, resp.status_code, resp.content)
        return True

    def _post_file(
        self, url: str, file_data: tuple[str, BinaryIO, str], body: Any = None
    ) -> Any:
        """Send a POST request with a file and optional JSON body.

        Args:
            url (str): The endpoint URL (relative to the API base URL).
            file_data (tuple[str, BinaryIO, str]): A tuple containing the file name,
                file object, and MIME type.
            body (Any): Optional data to be sent as JSON in the
                form data. Defaults to None.

        Returns:
            Any: The decoded JSON response, or None if the response body is empty.

        Raises:
            KalbioAPIError: If the API request returns a 4xx or 5xx response.
            KalbioResponseError: If the request succeeds but the body is non-empty
                and cannot be decoded as JSON.
            Exception: Any exception that may be raised by ``requests.post``.
        """
        files = {"file": file_data}

        form_data = {}
        if body:
            form_data["body"] = json.dumps(body)

        resp = requests.post(
            self._api_url + url,
            files=files,
            data=form_data,
            headers=self._get_headers(),
            timeout=TIMEOUT_MAXIMUM,
            verify=self._verify_ssl,
        )
        if resp.status_code >= 400:
            raise KalbioAPIError("POST", url, resp.status_code, resp.content)
        return self._json_body_or_none("POST", url, resp)

    def _put(self, url: str, payload: dict) -> Any:
        """Send a PUT request to the specified URL with the provided payload.

        Args:
            url (str): The endpoint URL (relative to the base API URL).
            payload (dict): The data to be sent in the PUT request body.

        Returns:
            Any: The decoded JSON response, or None if the response body is empty.

        Raises:
            KalbioAPIError: If the API request returns a 4xx or 5xx response.
            KalbioResponseError: If the request succeeds but the body is non-empty
                and cannot be decoded as JSON.
            Exception: Any exception that may be raised by ``requests.put``.
        """

        resp = requests.put(
            self._api_url + url,
            data=json.dumps(payload),
            headers=self._get_headers(),
            timeout=TIMEOUT_MAXIMUM,
            verify=self._verify_ssl,
        )
        if resp.status_code >= 400:
            raise KalbioAPIError("PUT", url, resp.status_code, resp.content)
        return self._json_body_or_none("PUT", url, resp)

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a GET request to the specified API endpoint with optional query parameters.

        Args:
            url (str): The API endpoint path to append to the base URL.
            params (Optional[Dict[str, Any]]): Dictionary of query parameters to
                include in the request. Defaults to None.

        Returns:
            Any: The decoded JSON response, or None if the endpoint returns 404
            or the response body is empty.

        Raises:
            KalbioAPIError: If the API request returns a non-404 4xx or a 5xx response.
            KalbioResponseError: If the request succeeds but the body is non-empty
                and cannot be decoded as JSON.
            Exception: Any exception that may be raised by ``requests.get``.
        """
        url = self._api_url + url
        if params:
            url += "?" + urllib.parse.urlencode(params)

        resp = requests.get(
            url,
            headers=self._get_headers(),
            timeout=TIMEOUT_MAXIMUM,
            verify=self._verify_ssl,
        )
        if resp.status_code == 404:
            _logger.debug("GET %s returned 404; returning None", url)
            return None
        if resp.status_code >= 400:
            raise KalbioAPIError("GET", url, resp.status_code, resp.content)
        return self._json_body_or_none("GET", url, resp)

    def _get_file(
        self, url: str, download_path: str, params: Optional[Dict[str, Any]] = None
    ) -> str | None:
        """Download a file from the specified URL and save it to the given path.

        Args:
            url (str): The endpoint URL (relative to the API base URL) to download
                the file from.
            download_path (str): The local file path where the downloaded file
                will be saved.
            params (Optional[Dict[str, Any]]): Dictionary of query parameters to
                include in the request. Defaults to None.

        Returns:
            (str | None): The path to the downloaded file if successful. Returns None
            if the file is not found (404).

        Raises:
            Exception: Any exception that may be raised `requests.get`
        """
        url = self._api_url + url
        if params:
            url += "?" + urllib.parse.urlencode(params)

        with requests.get(
            url,
            headers=self._get_headers(),
            stream=True,
            timeout=TIMEOUT_MAXIMUM,
            verify=self._verify_ssl,
        ) as resp:
            if resp.status_code == 404:
                _logger.debug("GET %s returned 404; returning None", url)
                return None
            if resp.status_code >= 400:
                raise KalbioAPIError("GET", url, resp.status_code, resp.content)

            try:
                with open(download_path, "wb") as f_download:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f_download.write(chunk)
            except BaseException:
                # A mid-stream failure leaves a truncated file; remove it so the
                # caller never mistakes a partial download for a complete one.
                if os.path.exists(download_path):
                    os.remove(download_path)
                raise

        return download_path

    def _delete(
        self,
        url: str,
        payload: Optional[dict] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Send a DELETE request to the specified API endpoint.

        Args:
            url (str): The API endpoint path to append to the base URL.
            payload (Optional[dict]): JSON body to send. Defaults to ``{}``
                because Fastify rejects an empty body when Content-Type is
                ``application/json``. Pass a real dict for endpoints that
                accept a DELETE body.
            params (Optional[Dict[str, Any]]): Dictionary of query parameters to
                include in the request. Defaults to None.

        Returns:
            Any: The decoded JSON response, or None if the response body is empty.

        Raises:
            KalbioAPIError: If the API request returns a 4xx or 5xx response.
            KalbioResponseError: If the request succeeds but the body is non-empty
                and cannot be decoded as JSON.
            Exception: Any exception that may be raised by ``requests.delete``.
        """
        url = self._api_url + url
        if params:
            url += "?" + urllib.parse.urlencode(params)

        resp = requests.delete(
            url,
            data=json.dumps(payload if payload is not None else {}),
            headers=self._get_headers(),
            timeout=TIMEOUT_MAXIMUM,
            verify=self._verify_ssl,
        )
        if resp.status_code >= 400:
            raise KalbioAPIError("DELETE", url, resp.status_code, resp.content)
        return self._json_body_or_none("DELETE", url, resp)
