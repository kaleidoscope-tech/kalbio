"""
Service class for handling data exports from Kaleidoscope.

This class provides methods to export and download data from the Kaleidoscope API,
specifically for pulling record search data and saving it as CSV files.

Classes:
    ExportsService: Service class for exporting and downloading record search data as CSV.

Example:
    ```python
        # Pull data and download as CSV
        file_path = client.exports_service.pull_data(
            filename="my_export.csv",
            entity_slice_id="some-uuid",
            download_path="/path/to/downloads",
            search_text="example"
        )
    ```
"""

from typing import Optional
from kalbio.client import KaleidoscopeClient


class ExportsService:
    """Service class for handling data exports from Kaleidoscope.

    This class provides methods to export and download data from the Kaleidoscope API,
    specifically for pulling record search data and saving it as CSV files.

    Example:
        ```python
        # Pull data and download as CSV
        file_path = client.exports_service.pull_data(
            filename="my_export.csv",
            entity_slice_id="some-uuid",
            download_path="/path/to/downloads",
            search_text="example"
        )
        ```
    """

    def __init__(self, client: "KaleidoscopeClient"):
        self._client = client

    def pull_data(
        self,
        filename: str,
        entity_slice_id: str,
        download_path: Optional[str] = None,
        record_view_id: Optional[str] = None,
        view_field_ids: Optional[str] = None,
        identifier_ids: Optional[str] = None,
        record_set_id: Optional[str] = None,
        program_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        record_set_filters: Optional[str] = None,
        view_field_filters: Optional[str] = None,
        view_field_sorts: Optional[str] = None,
        entity_field_filters: Optional[str] = None,
        entity_field_sorts: Optional[str] = None,
        search_text: Optional[str] = None,
    ) -> str | None:
        """Pull record search data and download it as a CSV file.

        This method interacts with the Kaleidoscope API to export records as a CSV file based on the provided parameters.
        It supports filtering, sorting, and searching records, and allows specifying various identifiers and filters
        to customize the export.

        Args:
            filename (str): The name of the CSV file to be downloaded.
            entity_slice_id (str): The ID of the entity slice to export records from.
            download_path (str, optional): The directory path where the CSV file will be saved. Defaults to None (uses '/tmp').
            record_view_id (str, optional): The ID of the record view to filter records. Defaults to None.
            view_field_ids (str, optional): Comma-separated IDs of view fields to include in the export. Defaults to None.
            identifier_ids (str, optional): Comma-separated IDs of identifiers to filter records. Defaults to None.
            record_set_id (str, optional): The ID of the record set to filter records. Defaults to None.
            program_id (str, optional): The ID of the program to filter records. Defaults to None.
            operation_id (str, optional): The ID of the operation to filter records. Defaults to None.
            record_set_filters (str, optional): Filters to apply to the record set. Defaults to None.
            view_field_filters (str, optional): Filters to apply to view fields. Defaults to None.
            view_field_sorts (str, optional): Sorting options for view fields. Defaults to None.
            entity_field_filters (str, optional): Filters to apply to entity fields. Defaults to None.
            entity_field_sorts (str, optional): Sorting options for entity fields. Defaults to None.
            search_text (str, optional): Text to search within records. Defaults to None.

        Returns:
            (str | None): The file path of the downloaded CSV file, or None if not successful.

        API Reference:
            https://kaleidoscope.readme.io/reference/get_records-export-csv
        """

        params = {
            "filename": filename,
            "entity_slice_id": entity_slice_id,
        }

        optional_params = {
            "record_view_id": record_view_id,
            "view_field_ids": view_field_ids,
            "identifier_ids": identifier_ids,
            "record_set_id": record_set_id,
            "program_id": program_id,
            "operation_id": operation_id,
            "record_set_filters": record_set_filters,
            "view_field_filters": view_field_filters,
            "view_field_sorts": view_field_sorts,
            "entity_field_filters": entity_field_filters,
            "entity_field_sorts": entity_field_sorts,
            "search_text": search_text,
        }

        params.update(
            {key: value for key, value in optional_params.items() if value is not None}
        )

        url = "/records/export/csv"
        file = self._client._get_file(
            url,
            f"{download_path if download_path else '/tmp'}/{filename}",
            params,
        )

        return file
