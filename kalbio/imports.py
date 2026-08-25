"""Service class for handling data imports into Kaleidoscope workspace.

This module provides the `ImportsService` class, which facilitates pushing data records
into the Kaleidoscope system. It supports flexible data import operations, allowing
organization by experiments, programs, and data sources.

Classes:
    ImportsService: Service for handling data imports into the Kaleidoscope workspace, providing methods to push records organized by source, experiment, program, record views, and set names.

Example:
    ```python
    key_fields = ["id", "timestamp"]
    records = [
        {"id": "001", "timestamp": "2024-01-01", "value": 42.5, "status": "active"},
        {"id": "002", "timestamp": "2024-01-02", "value": 38.7, "status": "pending"}
    ]
    # Push data to a specific source and experiment
    import_id = client.imports.push_data(
        key_field_names=key_fields,
        data=records,
        source_id="data_source_123",
        operation_id="exp_456",
        set_name="january_batch"
    )
    ```
"""

import warnings
from typing import Any, List, Optional

from pydantic import Field

from kalbio._base import _ApiModel, _BaseService
from kalbio.client import KalbioResponseError


class ImportValidationError(_ApiModel):
    """A per-row error from an import's validation pass.

    Populated for rows the server skipped or rejected; surfaced via
    ``ImportResult.validation_result``. A hard-failed import (``import_status``
    == ``"failed"``) carries no ``import_result`` — its error text lives in
    ``ImportRecord.error_message`` instead.
    """

    field_id: Optional[str] = None
    field_name: Optional[str] = None
    value: Any = None
    conflict_type: Optional[str] = None
    incoming_record_identifier: Optional[str] = None
    conflicting_record_id: Optional[str] = None
    conflicting_record_identifier: Optional[str] = None
    conflicting_value: Any = None
    constraint_fields: Optional[List[dict[str, Any]]] = None


class ImportValidationResult(_ApiModel):
    """Row-level outcome of an import's validation pass."""

    total_processed: Optional[int] = None
    successful: Optional[int] = None
    failed: Optional[int] = None
    errors: List[ImportValidationError] = Field(default_factory=list)


class ImportResult(_ApiModel):
    """Results summary from a completed import.

    For an import that completed but skipped or rejected rows, the per-row
    detail is in ``validation_result.errors``.
    """

    records_created: Optional[int] = None
    records_skipped: Optional[int] = None
    records_updated: Optional[int] = None
    fields_added: Optional[int] = None
    validation_result: Optional[ImportValidationResult] = None


class ImportRecord(_ApiModel):
    """Represents an import record returned by the imports API.

    To inspect a failed import, read both ``error_message`` (set on hard
    failure) and ``import_result.validation_result.errors`` (per-row detail
    when the import completed with skips).
    """

    id: str
    import_status: str
    is_complete: bool
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    started_at: Optional[str] = None
    error_message: Optional[str] = None
    operation_id: Optional[str] = None
    entity_slice_id: Optional[str] = None
    source_id: Optional[str] = None
    import_result: Optional[ImportResult] = None


class ImportsService(_BaseService):
    """Service class for handling data imports into Kaleidoscope workspace.

    This service provides functionality to push data records into the workspace,
    with support for organizing data by sources, experiments, programs, and record views.
    """

    @staticmethod
    def _import_id_or_raise(resp: Any, method: str, url: str) -> str:
        """Return the ``import_id`` from a push response or raise.

        The push endpoints respond ``200 {"import_id": ...}`` on success. Any
        other 2xx body means the client cannot tell what happened, so surface it
        rather than collapsing it to ``None``.
        """
        if isinstance(resp, dict) and resp.get("import_id"):
            return resp["import_id"]
        raise KalbioResponseError(method, url, resp)

    def push_data(
        self,
        key_field_names: list[str],
        data: list[dict[str, Any]],
        source_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        program_id: Optional[str] = None,
        record_view_id: Optional[str] = None,
        add_fields_to_record_view_ids: Optional[list[str]] = None,
        set_name: Optional[str] = None,
        record_view_ids: Optional[list[str]] = None,
    ) -> str:
        """Import data into the workspace using field names.

        Sends a list of records, each represented as a dictionary of field names and values,
        to the Kaleidoscope workspace.

        Args:
            key_field_names (list[str]): List of field names that serve as keys for the records.
            data (list[dict[str, Any]]): List of records to import, each as a dictionary mapping field names to values.
            source_id (str, optional): Identifier for the data source. If provided, data is imported under this source.
            operation_id (str, optional): Identifier for the operation/experiment. If provided, data is imported into this specific operation.
            program_id (str, optional): Identifier for the program. If provided, data is imported under this program.
            record_view_id (str, optional): UUID of the record view on the operation
                to import the data into. Use `Activity.record_views` to discover the
                available views on an operation. Only meaningful when `operation_id`
                is also provided.
            add_fields_to_record_view_ids (list[str], optional): UUIDs of additional
                record views that any newly-created fields from this import should be
                added to. Distinct from `record_view_id`: these views are not the
                target of the import, they just get the new fields added to them.
            set_name (str, optional): Name of the set to which the imported data belongs.
            record_view_ids (list[str], optional): Deprecated on this method. The
                server only accepts a singular `record_view_id` for
                operation-targeted imports plus `add_fields_to_record_view_ids`
                for adding fields to extra views. Values passed here are ignored.
                Switch to `record_view_id` and/or `add_fields_to_record_view_ids`.
                (The same-named parameter on `push_data_by_field_id` is a
                different, functional parameter that the server does honor.)

        Returns:
            str: The import ID for the created import.

        Raises:
            KalbioAPIError: If the request returns a 4xx or 5xx response.
            KalbioResponseError: If the request succeeds but the body contains
                no ``import_id`` (the raw body is on ``response_body``).

        Example:
            ```python
            # Import into a specific record view on an operation
            activity = client.activities.get_activity_by_id("op_uuid")
            view = activity.record_views[0]
            client.imports.push_data(
                key_field_names=["id"],
                data=[{"id": "S-001", "yield": 42.5}],
                operation_id=activity.id,
                record_view_id=view.id,
            )
            ```
        """
        if record_view_ids is not None:
            warnings.warn(
                "`record_view_ids` (plural) is deprecated and was silently ignored "
                "by the server. Use `record_view_id` (singular) to target a specific "
                "record view on the operation, and/or `add_fields_to_record_view_ids` "
                "to add new fields to additional views.",
                DeprecationWarning,
                stacklevel=2,
            )

        payload: dict[str, Any] = {
            "key_field_names": key_field_names,
            "data": data,
        }

        if program_id is not None:
            payload["program_id"] = program_id
        if operation_id is not None:
            payload["operation_id"] = operation_id
        if record_view_id is not None:
            payload["record_view_id"] = record_view_id
        if add_fields_to_record_view_ids is not None:
            payload["add_fields_to_record_view_ids"] = add_fields_to_record_view_ids
        if set_name is not None:
            payload["set_name"] = set_name

        url = "/push/imports"
        if source_id:
            url = url + f"/{source_id}"

        resp = self._client._post(url, payload)
        return self._import_id_or_raise(resp, "POST", url)

    def push_data_by_field_id(
        self,
        key_field_ids: list[str],
        data: list[dict[str, Any]],
        operation_id: Optional[str] = None,
        program_id: Optional[str] = None,
        record_view_ids: Optional[list[str]] = None,
        set_name: Optional[str] = None,
    ) -> str:
        """Import data into the workspace using field UUIDs instead of field names.

        Sends a list of records where keys are field UUIDs rather than field names.

        Args:
            key_field_ids (list[str]): List of field UUIDs that serve as keys for the records.
            data (list[dict[str, Any]]): List of records to import, each as a dictionary mapping field UUIDs to values.
            operation_id (str, optional): Identifier for the experiment.
            program_id (str, optional): Identifier for the program.
            record_view_ids (list[str], optional): Record view IDs to associate
                with the imported data. This endpoint sends them to the server
                and they take effect, unlike the same-named (deprecated)
                parameter on `push_data`, which is ignored.
            set_name (str, optional): Name of the set to which the imported data belongs.

        Returns:
            str: The import ID for the created import.

        Raises:
            KalbioAPIError: If the request returns a 4xx or 5xx response.
            KalbioResponseError: If the request succeeds but the body contains
                no ``import_id`` (the raw body is on ``response_body``).
        """
        if record_view_ids is None:
            record_view_ids = []

        payload = {
            "key_field_ids": key_field_ids,
            "data": data,
            "record_view_ids": record_view_ids,
        }

        if program_id:
            payload["program_id"] = program_id
        if operation_id:
            payload["operation_id"] = operation_id
        if set_name:
            payload["set_name"] = set_name

        url = "/push/imports/by-field-id"
        resp = self._client._post(url, payload)
        return self._import_id_or_raise(resp, "POST", url)

    def get_imports(
        self,
        is_complete: Optional[bool] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> List[ImportRecord]:
        """Retrieve imports in the workspace.

        Args:
            is_complete (bool, optional): Filter by completion status.
            page (int, optional): Page number for pagination.
            page_size (int, optional): Number of items per page.

        Returns:
            List[ImportRecord]: A list of import records.
        """
        params = {}
        if is_complete is not None:
            params["is_complete"] = 1 if is_complete else 0
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size

        resp = self._client._get("/imports", params if params else None)
        if resp is None:
            return []
        # Assumes the endpoint returns a top-level list; if it ever paginates
        # into an envelope (e.g. {"items": [...]}), this iterates the wrong shape.
        return [ImportRecord(**record) for record in resp]

    def get_import(self, import_id: str) -> Optional[ImportRecord]:
        """Retrieve a specific import by ID.

        Args:
            import_id (str): The UUID of the import to retrieve.

        Returns:
            ImportRecord: The import record, or None if not found.
        """
        resp = self._client._get(f"/imports/{import_id}")
        if resp is None:
            return None
        return ImportRecord(**resp)
