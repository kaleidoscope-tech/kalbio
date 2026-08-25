"""Service class for handling registration workflows in Kaleidoscope.

This module provides methods for driving the registration lifecycle of
operation files, including creating registrations, listing registration
files for an operation, pushing intermediate status updates (e.g. after
external validation), and submitting final results.

The typical webhook-driven workflow is:

1. Receive a ``registration_submitted`` webhook event containing a
   ``file_url`` and ``record_ids``.
2. Download the file using :meth:`FilesService.download_file`.
3. Process the file externally.
4. (Optional) Push intermediate status via
   :meth:`RegistrationService.push_status` (e.g. ``validated``,
   ``validation_failed``).
5. Submit final results via :meth:`RegistrationService.submit_results`.

Classes:
    RegistrationFileStatusEnum: Lifecycle states for a registration file.
    RegistrationResultStatusEnum: Terminal statuses for a results
        submission.
    RegistrationResultError: Per-record error from a failed registration.
    RegistrationFile: A registration attempt for a file within an
        operation.
    RegistrationFileWithErrors: A registration file with any per-record
        errors attached.
    RegistrationService: Service for the registration endpoints.
"""

from enum import Enum
from typing import Any, List, Optional

from pydantic import Field, model_validator

from kalbio._base import _ApiModel, _BaseService
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import _require_response_body


class RegistrationFileStatusEnum(str, Enum):
    """Lifecycle states for a registration file.

    Attributes:
        PENDING: Registration created, awaiting processing.
        VALIDATED: External validation succeeded.
        VALIDATION_FAILED: External validation failed.
        SUBMITTED: Results have been submitted for processing.
        COMPLETED: Registration completed successfully.
        FAILED: Registration failed.
    """

    PENDING = "pending"
    VALIDATED = "validated"
    VALIDATION_FAILED = "validation_failed"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    FAILED = "failed"


class RegistrationResultStatusEnum(str, Enum):
    """Terminal statuses reported when submitting registration results.

    Attributes:
        SUCCESS: Processing succeeded.
        ERROR: Processing failed.
    """

    SUCCESS = "success"
    ERROR = "error"


class RegistrationResultError(_ApiModel):
    """A per-record error surfaced from a failed registration.

    A value object rather than an entity: registration errors have no id of
    their own, so this extends `_ApiModel` (all fields optional) instead of
    `_KaleidoscopeBaseModel` (which requires `id`).

    Attributes:
        source_record_id (str): The ID of the source record that failed.
        status (str): The per-record status reported by the processor.
        error_message (str): Human-readable error description.
    """

    source_record_id: Optional[str] = None
    status: Optional[str] = None
    error_message: Optional[str] = None


class RegistrationFile(_KaleidoscopeBaseModel):
    """A registration attempt for a file within an operation.

    Attributes:
        workspace_id (str): ID of the workspace.
        operation_id (str): ID of the operation this registration belongs to.
        file_id (str): ID of the file being registered.
        status (RegistrationFileStatusEnum): Current lifecycle state.
        message (Optional[str]): Status message set by the processor.
        created_by (str): ID of the user who created the registration.
        last_updated_by (str): ID of the user who last updated the
            registration.
        created_at (str): ISO timestamp when the registration was created.
        updated_at (str): ISO timestamp when the registration was last
            updated.
    """

    workspace_id: Optional[str] = None
    operation_id: Optional[str] = None
    file_id: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    created_by: Optional[str] = None
    last_updated_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _coalesce_error_message(cls, data: Any) -> Any:
        # Server still returns a legacy ``error_message`` field that mirrors
        # ``message``. If a response ever comes back with only the legacy
        # field populated, fall back to it.
        if isinstance(data, dict) and data.get("message") is None:
            legacy = data.get("error_message")
            if legacy is not None:
                data = {**data, "message": legacy}
        return data


class RegistrationFileWithErrors(RegistrationFile):
    """A registration file with any per-record errors attached.

    Attributes:
        record_errors (List[RegistrationResultError]): Errors for records
            that failed to register. Empty unless ``status`` is
            ``failed``.
    """

    record_errors: List[RegistrationResultError] = Field(default_factory=list)


class RegistrationService(_BaseService):
    """Service class for registration workflows.

    Provides methods to create registrations, list registration files
    for an operation, push intermediate status updates, and submit final
    results.
    """

    def register_file(self, operation_id: str, file_id: str) -> RegistrationFile:
        """Register a file with an operation.

        Creates a registration for a previously uploaded file, submitting
        it for external registration processing.

        Args:
            operation_id (str): The operation to register the file with.
            file_id (str): The uploaded file to register.

        Returns:
            RegistrationFile: The newly created registration.

        Raises:
            KalbioAPIError: If the API request fails.
        """
        url = f"/operations/{operation_id}/register/{file_id}"
        resp = _require_response_body("POST", url, self._client._post(url, {}))
        return RegistrationFile._from_api(resp, self._client)

    def get_registration_files(
        self, operation_id: str
    ) -> List[RegistrationFileWithErrors]:
        """List all registration files for an operation.

        Args:
            operation_id (str): The operation to list registrations for.

        Returns:
            List[RegistrationFileWithErrors]: Registration files for the
            operation. ``record_errors`` will be populated for entries
            whose ``status`` is ``failed``.

        Raises:
            KalbioAPIError: If the API request fails.
        """
        url = f"/operations/{operation_id}/registrations"
        resp = _require_response_body("GET", url, self._client._get(url))
        return RegistrationFileWithErrors._list_from_api(resp, self._client)

    def push_status(
        self,
        operation_id: str,
        file_id: str,
        status: RegistrationFileStatusEnum,
        message: Optional[str] = None,
    ) -> bool:
        """Push the current status of a registration file.

        Used to report intermediate lifecycle updates from an external
        processor (e.g. ``validated``, ``validation_failed``) without
        submitting full results.

        Args:
            operation_id (str): The operation the registration belongs to.
            file_id (str): The registration file to update.
            status (RegistrationFileStatusEnum): The status to push.
            message (str, optional): Optional message to attach to the
                status update.

        Returns:
            bool: True if the request succeeded (204).

        Raises:
            KalbioAPIError: If the API request fails.
        """
        payload: dict[str, Any] = {"status": status}
        if message is not None:
            payload["message"] = message

        url = f"/operations/{operation_id}/registration_files/{file_id}/status"
        return self._client._post_no_content(url, payload)

    def submit_results(
        self,
        operation_id: str,
        file_id: str,
        status: RegistrationResultStatusEnum,
        message: Optional[str] = None,
        key_field_names: Optional[list[str]] = None,
        records: Optional[list[dict[str, Any]]] = None,
    ) -> bool:
        """Submit registration results for a processed file.

        Called after downloading and processing a file from a
        ``registration_submitted`` webhook event.

        Args:
            operation_id (str): The operation ID from the webhook event.
            file_id (str): The file ID from the webhook event.
            status (RegistrationResultStatusEnum): Overall result status.
            message (str, optional): Message to attach to the results.
            key_field_names (list[str], optional): Names of key fields in the
                result data (e.g. ``["id", "name"]``).
            records (list[dict[str, Any]], optional): Per-record results. Each
                dict should contain ``record_id`` (str, required),
                ``status`` (str, required), and optionally ``data``
                (dict[str, Any]) and ``error_message`` (str).

        Returns:
            bool: True if the results were submitted successfully (204).

        Raises:
            KalbioAPIError: If the API request fails.
        """
        payload: dict[str, Any] = {"status": status}
        if message is not None:
            payload["message"] = message
        if key_field_names is not None:
            payload["key_field_names"] = key_field_names
        if records is not None:
            payload["records"] = records

        url = f"/operations/{operation_id}/register/{file_id}/results"
        return self._client._post_no_content(url, payload)
