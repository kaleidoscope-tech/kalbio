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
    VALID_CONTENT_TYPES (list): List of acceptable content types for file downloads.
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

import os
from datetime import datetime, timedelta
import json
from json import JSONDecodeError
from pydantic import BaseModel
import requests
import urllib
from typing import Any, BinaryIO, Dict, Optional

PROD_API_URL = "https://api.kaleidoscope.bio"
"""The production URL for the Kaleidoscope API.

This is the default url used for the `KaleidoscopeClient`, in the event
no url is provided in the `KaleidoscopeClient`'s initialization"""

VALID_CONTENT_TYPES = [
    "text/csv",
    "chemical/x-mdl-sdfile",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]
"""List of acceptable content types for file downloads.

Any file retrieved by the `KaleidoscopeClient` must be of one the above types"""

TIMEOUT_MAXIMUM = 10
"""Maximum timeout for API requests in seconds."""

_env_client_id = os.getenv("KALEIDOSCOPE_API_CLIENT_ID")
_env_client_secret = os.getenv("KALEIDOSCOPE_API_CLIENT_SECRET")


class _TokenResponse(BaseModel):
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
    _additional_headers: dict
    _iap_client_id: Optional[str]

    _refresh_token: str = None
    _access_token: str = None
    _auth_refresh_before: Optional[datetime] = None

    _iap_token: Optional[str] = None
    _iap_refresh_before: Optional[datetime] = None

    def __init__(
        self,
        client_id: Optional[str] = _env_client_id,
        client_secret: Optional[str] = _env_client_secret,
        url: str = PROD_API_URL,
        additional_headers: dict = {},
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
        from kalbio.imports import ImportsService
        from kalbio.labels import LabelsService
        from kalbio.programs import ProgramsService
        from kalbio.property_fields import PropertyFieldsService
        from kalbio.record_views import RecordViewsService
        from kalbio.records import RecordsService
        from kalbio.workspace import WorkspaceService

        self._api_url = url

        self.activities = ActivitiesService(self)
        self.dashboards = DashboardsService(self)
        self.entity_fields = EntityFieldsService(self)
        self.entity_types = EntityTypesService(self)
        self.exports = ExportsService(self)
        self.imports = ImportsService(self)
        self.labels = LabelsService(self)
        self.property_fields = PropertyFieldsService(self)
        self.programs = ProgramsService(self)
        self.record_views = RecordViewsService(self)
        self.records = RecordsService(self)
        self.workspace = WorkspaceService(self)

        self._client_id = client_id
        self._client_secret = client_secret
        self.additional_headers = additional_headers
        self._iap_client_id = iap_client_id
        self._verify_ssl = verify_ssl

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

        Raises:
            RuntimeError: If the auth endpoint responds with an error status code.
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
        if auth_resp.status_code >= 400:
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

    def _get_headers(self) -> dict:
        """Build authorization headers, refreshing tokens if needed.

        Returns:
            dict: HTTP headers including `Authorization`, `Content-Type`,
                and optionally `Proxy-Authorization` for IAP.
        """
        if (
            self._auth_refresh_before is None
            or datetime.now() > self._auth_refresh_before
        ):
            self._refresh_auth_token()

        headers = {
            "Content-Type": "application/json",
            "X-Kal-Authorization": f"Bearer {self._access_token}",
            **self._get_iap_headers(),
            **self.additional_headers,
        }

        return headers

    def _post(self, url: str, payload: dict) -> Any:
        """Send a POST request to the specified URL with the given payload.

        Args:
            url (str): The endpoint URL (relative to the API base URL) to send the
                POST request to.
            payload (dict): The data to be sent in the body of the POST request.
                Should be serializable to JSON.

        Returns:
            Any: The JSON response from the server if the request is successful
            and the response is valid JSON. Returns None if the response cannot be decoded.

        Raises:
            Exception: Any exception that may be raised `requests.post`
        """

        resp = requests.post(
            self._api_url + url,
            data=json.dumps(payload),
            headers=self._get_headers(),
            timeout=TIMEOUT_MAXIMUM,
            verify=self._verify_ssl,
        )
        if resp.status_code >= 400:
            print(f"POST {url} received {resp.status_code}: ", resp.content)
            return None
        try:
            return resp.json()
        except JSONDecodeError:
            return None

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
            Any: The JSON response from the server if the request is successful.
            Returns None if the response cannot be decoded.

        Raises:
            Exception: Any exception that may be raised `requests.post`
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
            print(f"POST {url} received {resp.status_code}: ", resp.content)
            return None
        try:
            return resp.json()
        except JSONDecodeError:
            return None

    def _put(self, url: str, payload: dict) -> Any:
        """Send a PUT request to the specified URL with the provided payload.

        Args:
            url (str): The endpoint URL (relative to the base API URL).
            payload (dict): The data to be sent in the PUT request body.

        Returns:
            Any: The JSON response from the server if the request is successful.
            Returns None if the response cannot be decoded.

        Raises:
            Exception: Any exception that may be raised `requests.put`
        """

        resp = requests.put(
            self._api_url + url,
            data=json.dumps(payload),
            headers=self._get_headers(),
            timeout=TIMEOUT_MAXIMUM,
            verify=self._verify_ssl,
        )
        if resp.status_code >= 400:
            print(f"PUT {url} received {resp.status_code}: ", resp.content)
            return None
        try:
            return resp.json()
        except JSONDecodeError:
            return None

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a GET request to the specified API endpoint with optional query parameters.

        Args:
            url (str): The API endpoint path to append to the base URL.
            params (Optional[Dict[str, Any]]): Dictionary of query parameters to
                include in the request. Defaults to None.

        Returns:
            Any: The JSON response from the server if the request is successful.
            Returns None if the response cannot be decoded.

        Raises:
            Exception: Any exception that may be raised `requests.get`
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
        if resp.status_code >= 400:
            print(f"GET {url} received {resp.status_code}", resp.content)
            return None
        try:
            return resp.json()
        except JSONDecodeError:
            return None

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
            if the request fails or the response does not contain valid file data.

        Raises:
            Exception: Any exception that may be raised `requests.get`

        Note:
            Only responses with valid content types (as defined in VALID_CONTENT_TYPES)
            are saved.
        """
        url = self._api_url + url
        if params:
            url += "?" + urllib.parse.urlencode(params)

        resp = requests.get(
            url,
            headers=self._get_headers(),
            stream=True,
            timeout=TIMEOUT_MAXIMUM,
            verify=self._verify_ssl,
        )
        if resp.status_code >= 400:
            print(f"GET {url} received {resp.status_code}", resp.content)
            return None

        content_type = resp.headers.get("Content-Type", "")
        if content_type not in VALID_CONTENT_TYPES:
            print(
                f"Invalid Content-Type: {content_type}. Response does not contain valid file data."
            )
            return None

        with open(download_path, "wb") as f_download:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f_download.write(chunk)

        return download_path

    def _delete(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a DELETE request to the specified API endpoint with optional query parameters.

        Args:
            url (str): The API endpoint path to append to the base URL.
            params (Optional[Dict[str, Any]]): Dictionary of query parameters to
                include in the request. Defaults to None.

        Returns:
            Any: The JSON response from the server if the request is successful.
            Returns None if the response cannot be decoded.

        Raises:
            Exception: Any exception that may be raised `requests.delete`
        """
        url = self._api_url + url
        if params:
            url += "?" + urllib.parse.urlencode(params)

        resp = requests.delete(
            url,
            headers=self._get_headers(),
            timeout=TIMEOUT_MAXIMUM,
            verify=self._verify_ssl,
        )
        if resp.status_code >= 400:
            print(f"DELETE {url} received {resp.status_code}", resp.content)
            return None
        try:
            return resp.json()
        except JSONDecodeError:
            return None
