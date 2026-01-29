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
    response = client.imports.push_data(
        key_field_names=key_fields,
        data=records,
        source_id="data_source_123",
        operation_id="exp_456",
        set_name="january_batch"
    )
    ```
"""

from typing import Any, Optional
from kalbio.client import KaleidoscopeClient


class ImportsService:
    """Service class for handling data imports into Kaleidoscope workspace.

    This service provides functionality to push data records into the workspace,
    with support for organizing data by sources, experiments, programs, and record views.

    Methods:
        push_data: Imports data records into the workspace with various organizational options.
    """

    def __init__(self, client: KaleidoscopeClient):
        self._client = client

    def push_data(
        self,
        key_field_names: list[str],
        data: list[dict[str, Any]],
        source_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        program_id: Optional[str] = None,
        record_view_ids: Optional[list[str]] = [],
        set_name: Optional[str] = None,
    ) -> Any:
        """Import data into the workspace.

        Sends a list of records, each represented as a dictionary of field names and values,
        to the Kaleidoscope workspace.

        Args:
            key_field_names (list[str]): List of field names that serve as keys for the records.
            data (list[dict[str, Any]]): List of records to import, each as a dictionary mapping field names to values.
            source_id (str, optional): Identifier for the data source. If provided, data is imported under this source.
            operation_id (str, optional): Identifier for the experiment. If provided, data is imported into this specific experiment.
            program_id (str, optional): Identifier for the program. If provided, data is imported under this program.
            record_view_ids (list[str], optional): List of record view IDs to associate with the imported data.
            set_name (str, optional): Name of the set to which the imported data belongs.

        Returns:
            Any: Response object from the client's POST request to the import endpoint.
        """
        payload = {
            "key_field_names": key_field_names,
            "data": data,
            "record_view_ids": record_view_ids,
        }

        if program_id:
            payload["program_id"] = program_id
        if operation_id:
            payload["operation_id"] = operation_id
        if set_name:
            payload["set_name"] = set_name

        url = "/push/imports"
        if source_id:
            url = url + f"/{source_id}"

        return self._client._post(url, payload)
