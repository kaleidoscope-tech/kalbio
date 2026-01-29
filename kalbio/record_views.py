"""Module for managing Kaleidoscope record views and their operations.

This module provides classes and services for interacting with record views in the Kaleidoscope system.

Classes:
    RecordTransfer: TypedDict defining the structure for transferring records with key field values.
    ViewField: TypedDict defining the structure for view fields with data and lookup field references.
    RecordView: Model representing a record view with methods for extending views.
    RecordViewsService: Service class for managing record view operations and API interactions.

Example:
    ```python
        views = client.record_views.get_record_views()
        for view in views:
            print(f"View: {view.view_name}, Entity Slice: {view.entity_slice_id}")

        # View: Customer Records, Entity Slice: abc-123-def
        # View: Product Catalog, Entity Slice: xyz-456-ghi
    ```
"""

import logging
from functools import lru_cache
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import KaleidoscopeClient
from pydantic import TypeAdapter
from typing import Any, Dict, List, Optional, TypedDict

_logger = logging.getLogger(__name__)


class RecordTransfer(TypedDict):
    """TypedDict defining the structure for transferring records with key field values.

    Attributes:
        record_id (str): The unique identifier of the record to transfer.
        key_field_name_to_value (Dict[str, Any]): A dictionary mapping key field names to their values.
    """

    record_id: str
    key_field_name_to_value: Dict[str, Any]


class ViewField(TypedDict):
    """TypedDict defining the structure for view fields with data and lookup field references.

    Attributes:
        data_field_id (Optional[str]): The ID of the data field, if applicable.
        lookup_field_id (Optional[str]): The ID of the lookup field, if applicable.
    """

    data_field_id: Optional[str]
    lookup_field_id: Optional[str]


class RecordView(_KaleidoscopeBaseModel):
    """Represents a view of records in the Kaleidoscope system.

    A RecordView defines how records are displayed and accessed, including the entity slice
    they belong to, associated programs and operations, and the fields visible in the view.

    Attributes:
        id (str): UUID of the record view
        entity_slice_id (str): ID of the entity slice this view belongs to.
        program_ids (List[str]): List of program IDs associated with this view. Defaults to empty list.
        operation_ids (Optional[List[str]]): Optional list of operation IDs associated with this view.
        operation_definition_ids (Optional[List[str]]): Optional list of operation definition IDs.
        view_fields (List[ViewField]): List of fields visible in this view. Defaults to empty list.
    """

    view_name: str
    entity_slice_id: str
    program_ids: List[str] = []
    operation_ids: Optional[List[str]] = None
    operation_definition_ids: Optional[List[str]] = None
    view_fields: List[ViewField] = []

    def __str__(self):
        return f"{self.view_name}"

    class ExtendViewBody(TypedDict):
        """TypedDict defining the body for extending a record view.

        Attributes:
            new_key_field_name (str): The name of the new key field to add.
            records_to_transfer (Optional[List[RecordTransfer]]): A list of records to transfer with their new key values.
        """

        new_key_field_name: str
        records_to_transfer: Optional[List[RecordTransfer]]

    def extend_view(self, body: ExtendViewBody) -> None:
        """Extends the current record view by adding a key field.

        Args:
            body (ExtendViewBody): The request body containing information about the key field to add.
        """
        try:
            resp = self._client._put(
                "/record_views/" + self.id + "/add_key_field", dict(body)
            )
            if resp:
                for key, value in resp.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
        except Exception as e:
            _logger.error(f"Error updating record view: {e}")
            return None


class RecordViewsService:
    """Service class for managing record views in Kaleidoscope.

    This service provides methods to interact with record views, including retrieving,
    creating, and managing RecordView objects. It handles the conversion of raw data
    into RecordView instances and ensures proper client association.

    Example:
        ```python
        views = client.record_views.get_record_views()
        for view in views:
            print(f"View: {view.view_name}, Entity Slice: {view.entity_slice_id}")

        # View: Customer Records, Entity Slice: abc-123-def
        # View: Product Catalog, Entity Slice: xyz-456-ghi
        ```
    """

    def __init__(self, client: KaleidoscopeClient):
        self._client = client

    def _create_record_view(self, data: dict) -> RecordView:
        """Create a RecordView instance from a dictionary of data.

        This internal method validates the provided data against the RecordView model,
        sets the client reference, and returns the configured RecordView instance.

        Args:
            data (dict): A dictionary containing the data to populate the RecordView.
                         Must conform to the RecordView model schema.

        Returns:
            RecordView: A validated RecordView instance with the client reference set.

        Raises:
            ValidationError: If the data could not be validated as an RecordView.
        """

        record_view = RecordView.model_validate(data)
        record_view._set_client(self._client)

        return record_view

    def _create_record_views_list(self, data: list[dict]) -> List[RecordView]:
        """Converts a list of data dictionaries into a list of RecordView objects and sets the client for each RecordView.

        Args:
            data (list): A list of dictionaries representing record view data.

        Returns:
            List[RecordView]: A list of RecordView objects with the client set.

        Raises:
            ValidationError: If the data could not be validated as a list of RecordView objects.
        """
        record_views = TypeAdapter(List[RecordView]).validate_python(data)
        for record_view in record_views:
            record_view._set_client(self._client)

        return record_views

    @lru_cache
    def get_record_views(self) -> List[RecordView]:
        """Retrieves a list of record views available in the workspace.

        This method caches its values.

        Returns:
            List[RecordView]: A list of RecordView objects representing the record views in the workspace.

        Note:
            If an exception occurs during the API request, it logs the error,
            clears the cache, and returns an empty list.
        """
        try:
            resp = self._client._get("/record_views")
            return self._create_record_views_list(resp)
        except Exception as e:
            _logger.error(f"Error fetching record views: {e}")
            self.get_record_views.cache_clear()
            return []
