"""Records module for managing Kaleidoscope record operations.

This module provides classes and services for interacting with records in the Kaleidoscope system.
It includes functionality for filtering, sorting, managing record values, handling file attachments,
and searching records.

Classes:
    FilterRuleTypeEnum: Enumeration of available filter rule types for record filtering
    ViewFieldFilter: TypedDict for view-based field filter configuration
    ViewFieldSort: TypedDict for view-based field sort configuration
    FieldFilter: TypedDict for entity-based field filter configuration
    FieldSort: TypedDict for entity-based field sort configuration
    RecordValue: Model representing a single value within a record field
    Record: Model representing a complete record with all its fields and values
    RecordsService: Service class providing record-related API operations

The module uses Pydantic models for data validation and serialization, and integrates
with the KaleidoscopeClient for API communication.

Example:
    ```python
        # Get a record by ID
        record = client.records.get_record_by_id("record_uuid")

        # Add a value to a record field
        record.add_value(
            field_id="field_uuid",
            content="Experiment result",
            activity_id="activity_uuid"
        )

        # Get a field value
        value = record.get_value_content(field_id="field_uuid")

        # Update a field
        record.update_field(
            field_id="field_uuid",
            value="Updated value",
            activity_id="activity_uuid"
        )

        # Get activities associated with a record
        activities = record.get_activities()
    ```
"""

from __future__ import annotations
import itertools
import threading
from cachetools import TTLCache
import logging
from datetime import datetime
from enum import Enum
import json
from kalbio._base import _BaseService
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import KaleidoscopeClient
from kalbio.entity_fields import EntityFieldIdentifier
from pydantic import Field, ValidationError
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    Dict,
    List,
    Optional,
    Sequence,
    TypeAlias,
    TypedDict,
    Union,
    Unpack,
)

if TYPE_CHECKING:
    from kalbio.activities import Activity, ActivityIdentifier

_logger = logging.getLogger(__name__)

# Sentinel distinguishing "key absent" from a cached ``None`` (a negative lookup).
_MISSING = object()


class FilterRuleTypeEnum(str, Enum):
    """Enumeration of filter rule types for record filtering operations.

    This enum defines all available filter rule types that can be applied to record properties.
    Filter rules are categorized into several groups:

    - **Existence checks**: `IS_SET`, `IS_EMPTY`
    - **Equality checks**: `IS_EQUAL`, `IS_NOT_EQUAL`, `IS_ANY_OF_TEXT`
    - **String operations**: `INCLUDES`, `DOES_NOT_INCLUDE`, `STARTS_WITH`, `ENDS_WITH`
    - **Membership checks**: `IS_IN`, `IS_NOT_IN`
    - **Set operations**: `VALUE_IS_SUBSET_OF_PROPS`, `VALUE_IS_SUPERSET_OF_PROPS`,
        `VALUE_HAS_OVERLAP_WITH_PROPS`, `VALUE_HAS_NO_OVERLAP_WITH_PROPS`,
        `VALUE_HAS_SAME_ELEMENTS_AS_PROPS`
    - **Numeric comparisons**: `IS_LESS_THAN`, `IS_LESS_THAN_EQUAL`, `IS_GREATER_THAN`,
        `IS_GREATER_THAN_EQUAL`
    - **Absolute date comparisons**: `IS_BEFORE`, `IS_AFTER`, `IS_BETWEEN`
    - **Relative date comparisons**:
        - Day-based: `IS_BEFORE_RELATIVE_DAY`, `IS_AFTER_RELATIVE_DAY`, `IS_BETWEEN_RELATIVE_DAY`
        - Week-based: `IS_BEFORE_RELATIVE_WEEK`, `IS_AFTER_RELATIVE_WEEK`, `IS_BETWEEN_RELATIVE_WEEK`,
            `IS_LAST_WEEK`, `IS_THIS_WEEK`, `IS_NEXT_WEEK`
        - Month-based: `IS_BEFORE_RELATIVE_MONTH`, `IS_AFTER_RELATIVE_MONTH`, `IS_BETWEEN_RELATIVE_MONTH`,
            `IS_THIS_MONTH`, `IS_NEXT_MONTH`
    - **Update tracking**: `IS_LAST_UPDATED_AFTER`

    Each enum value corresponds to a string representation used in filter configurations.
    """

    IS_SET = "is_set"
    IS_EMPTY = "is_empty"
    IS_EQUAL = "is_equal"
    IS_ANY_OF_TEXT = "is_any_of_text"
    IS_NOT_EQUAL = "is_not_equal"
    INCLUDES = "includes"
    DOES_NOT_INCLUDE = "does_not_include"
    IS_IN = "is_in"
    IS_NOT_IN = "is_not_in"
    VALUE_IS_SUBSET_OF_PROPS = "value_is_subset_of_props"
    VALUE_IS_SUPERSET_OF_PROPS = "value_is_superset_of_props"
    VALUE_HAS_OVERLAP_WITH_PROPS = "value_has_overlap_with_props"
    VALUE_HAS_NO_OVERLAP_WITH_PROPS = "value_has_no_overlap_with_props"
    VALUE_HAS_SAME_ELEMENTS_AS_PROPS = "value_has_same_elements_as_props"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IS_LESS_THAN = "is_less_than"
    IS_LESS_THAN_EQUAL = "is_less_than_equal"
    IS_GREATER_THAN = "is_greater_than"
    IS_GREATER_THAN_EQUAL = "is_greater_than_equal"
    IS_BEFORE = "is_before"
    IS_AFTER = "is_after"
    IS_BETWEEN = "is_between"
    IS_BEFORE_RELATIVE_DAY = "is_before_relative_day"
    IS_AFTER_RELATIVE_DAY = "is_after_relative_day"
    IS_BETWEEN_RELATIVE_DAY = "is_between_relative_day"
    IS_BEFORE_RELATIVE_WEEK = "is_before_relative_week"
    IS_AFTER_RELATIVE_WEEK = "is_after_relative_week"
    IS_BETWEEN_RELATIVE_WEEK = "is_between_relative_week"
    IS_BEFORE_RELATIVE_MONTH = "is_before_relative_month"
    IS_AFTER_RELATIVE_MONTH = "is_after_relative_month"
    IS_BETWEEN_RELATIVE_MONTH = "is_between_relative_month"
    IS_LAST_WEEK = "is_last_week"
    IS_THIS_WEEK = "is_this_week"
    IS_NEXT_WEEK = "is_next_week"
    IS_THIS_MONTH = "is_this_month"
    IS_NEXT_MONTH = "is_next_month"
    IS_LAST_UPDATED_AFTER = "is_last_updated_after"


class ViewFieldFilter(TypedDict):
    """TypedDict for view-based field filter configuration.

    Attributes:
        key_field_id (Optional[str]): The ID of the key field to filter by.
        view_field_id (Optional[str]): The ID of the view field to filter by.
        filter_type (FilterRuleTypeEnum): The type of filter rule to apply.
        filter_prop (Any): The property value to filter against.

    Example:
        ```python
        from kalbio.records import FilterRuleTypeEnum, ViewFieldFilter

        filter_config: ViewFieldFilter = {
            "key_field_id": "field_uuid",
            "view_field_id": None,
            "filter_type": FilterRuleTypeEnum.IS_EQUAL,
            "filter_prop": "S",
        }
        ```
    """

    key_field_id: Optional[str]
    view_field_id: Optional[str]
    filter_type: FilterRuleTypeEnum
    filter_prop: Any


class ViewFieldSort(TypedDict):
    """TypedDict for view-based field sort configuration.

    Attributes:
        key_field_id (Optional[str]): The ID of the key field to sort by.
        view_field_id (Optional[str]): The ID of the view field to sort by.
        descending (bool): Whether to sort in descending order.

    Example:
        ```python
        from kalbio.records import ViewFieldSort

        sort_config: ViewFieldSort = {
            "key_field_id": "field_uuid",
            "view_field_id": None,
            "descending": True,
        }
        ```
    """

    key_field_id: Optional[str]
    view_field_id: Optional[str]
    descending: bool


class FieldFilter(TypedDict):
    """TypedDict for entity-based field filter configuration.

    Attributes:
        field_id (Optional[str]): The ID of the field to filter by.
        filter_type (FilterRuleTypeEnum): The type of filter rule to apply.
        filter_prop (Any): The property value to filter against.

    Example:
        ```python
        from kalbio.records import FieldFilter, FilterRuleTypeEnum

        field_filter: FieldFilter = {
            "field_id": "field_uuid",
            "filter_type": FilterRuleTypeEnum.STARTS_WITH,
            "filter_prop": "EXP-",
        }
        ```
    """

    field_id: Optional[str]
    filter_type: FilterRuleTypeEnum
    filter_prop: Any


class FieldSort(TypedDict):
    """TypedDict for entity-based field sort configuration.

    Attributes:
        field_id (Optional[str]): The ID of the field to sort by.
        descending (bool): Whether to sort in descending order.

    Example:
        ```python
        from kalbio.records import FieldSort

        sort_config: FieldSort = {
            "field_id": "field_uuid",
            "descending": False,
        }
        ```
    """

    field_id: Optional[str]
    descending: bool


class RecordValue(_KaleidoscopeBaseModel):
    """Represents a single value entry in a record within the Kaleidoscope system.

    A RecordValue stores the actual content of a record along with metadata about when it was
    created and its relationships to parent records and operations.

    Attributes:
        id (str): UUID of the record value
        content (Any): The actual data value stored in this record. Can be of any type.
        created_at (Optional[datetime]): Timestamp indicating when this value was created.
            Defaults to None.
        record_id (Optional[str]): Identifier of the parent record this value belongs to.
            Defaults to None.
        operation_id (Optional[str]): Identifier of the operation that created or modified
            this value. Defaults to None.
        record_view_id (Optional[str]): Identifier of the record view on the operation
            this value was written to. Only set when the value was created against a
            specific view of an operation; None for key field values and for
            non-view-scoped writes. Defaults to None.

    Example:
        ```python
        from datetime import datetime
        from kalbio.records import RecordValue

        value = RecordValue(
            id="value_uuid",
            content="Completed",
            created_at=datetime.utcnow(),
            record_id="record_uuid",
            operation_id="activity_uuid",
            record_view_id="view_uuid",
        )
        ```
    """

    content: Optional[Any] = None
    created_at: Optional[datetime] = None  # data value
    record_id: Optional[str] = None  # data value
    operation_id: Optional[str] = None  # data value
    record_view_id: Optional[str] = None  # data value

    def __str__(self):
        return f"{self.content}"


class Record(_KaleidoscopeBaseModel):
    """Represents a record in the Kaleidoscope system.

    A Record is a core data structure that contains values organized by fields, can be associated
    with experiments, and may have sub-records. Records are identified by a unique ID and belong
    to an entity slice.

    Attributes:
        id (str): UUID of the record.
        created_at (datetime): The timestamp when the record was created.
        entity_slice_id (str): The ID of the entity slice this record belongs to.
        identifier_ids (List[str]): A list of identifier IDs associated with this record.
        record_identifier (str): Human-readable identifier string for the record.
        record_values (Dict[str, List[RecordValue]]): A dictionary mapping field IDs to lists of record values.
        initial_operation_id (Optional[str]): The ID of the initial operation that created this record, if applicable.
        sub_record_ids (List[str]): A list of IDs for sub-records associated with this record.

    Example:
        ```python
        from kalbio.client import KaleidoscopeClient

        client = KaleidoscopeClient()
        record = client.records.get_record_by_id("record_uuid")
        latest_value = record.get_value_content(field_id="field_uuid")
        print(record.record_identifier, latest_value)
        ```
    """

    created_at: Optional[datetime] = None
    entity_slice_id: Optional[str] = None
    identifier_ids: List[str] = Field(default_factory=list)
    record_identifier: Optional[str] = None
    record_values: Dict[str, List[RecordValue]] = Field(default_factory=dict)  # [field_id, values[]]
    initial_operation_id: Optional[str] = None
    sub_record_ids: List[str] = Field(default_factory=list)

    def __str__(self):
        return f"{self.record_identifier}"

    def get_activities(self) -> List["Activity"]:
        """Retrieves a list of activities associated with this record.

        Returns:
            A list of activities related to this record.

        Example:
            ```python
            activities = record.get_activities()
            for activity in activities:
                print(activity.id)
            ```
        """
        return self._client.activities.get_activities_with_record(self.id)

    def _write_field_value(
        self,
        field_id: EntityFieldIdentifier,
        content: Any,
        activity_id: Optional[ActivityIdentifier],
        record_view_id: Optional[str],
    ) -> RecordValue | None:
        """Writes a value to a field and refreshes this record from the server.

        Shared implementation for `add_value` and `update_field`.

        Returns:
            The written record value, or None if the server returned an empty body.
        """
        body = {
            "field_id": self._client.entity_fields._resolve_data_field_id(field_id),
            "content": content,
            "operation_id": self._client.activities._resolve_activity_id(activity_id),
            "record_view_id": record_view_id,
        }

        resp = self._client._post("/records/" + self.id + "/values", body)
        self.refetch()

        if resp is None or len(resp) == 0:
            return None

        resource = resp.get("resource")
        if not resource:
            return None

        return RecordValue._from_api(resource, self._client)

    def add_value(
        self,
        field_id: EntityFieldIdentifier,
        content: Any,
        activity_id: Optional[ActivityIdentifier] = None,
        record_view_id: Optional[str] = None,
    ) -> RecordValue | None:
        """Adds a value to a specified field for a given activity.

        Args:
            field_id: Identifier of the field to which the value will be added.

                Any type of EntityFieldIdentifier will be accepted and resolved.
            content: The value/content to be saved for the field.
            activity_id: The identifier of the activity. Defaults to None.

                Any type of EntityFieldIdentifier will be accepted and resolved.
            record_view_id: The UUID of the specific record view on the operation
                to write the value to. Use `Activity.record_views` to discover the
                available views on an operation. Only meaningful when `activity_id`
                is also provided. Defaults to None.

        Returns:
            The written record value, or None if the server returned an empty body.

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            # Write to the operation as a whole
            record.add_value(
                field_id="field_uuid",
                content="Experiment result",
                activity_id="activity_uuid",
            )

            # Write to a specific record view on the operation
            view = activity.record_views[0]
            record.add_value(
                field_id="field_uuid",
                content="Experiment result",
                activity_id=activity.id,
                record_view_id=view.id,
            )
            ```
        """
        return self._write_field_value(
            field_id, content, activity_id, record_view_id
        )

    def get_value_content(
        self,
        field_id: EntityFieldIdentifier,
        activity_id: Optional[ActivityIdentifier] = None,
        include_sub_record_values: Optional[bool] = False,
        sub_record_id: Optional["RecordIdentifier"] = None,
        record_view_id: Optional[str] = None,
    ) -> Any | None:
        """Retrieves the content of a record value for a specified field.

        Optionally filtered by activity, sub-record, record view, and inclusion of
        sub-record values.

        Args:
            field_id: The ID of the field to retrieve the value for.
            activity_id: The ID of the activity to filter values by. Defaults to None.
            include_sub_record_values: Whether to include values from sub-records. Defaults to False.
            sub_record_id: The ID of a specific sub-record to filter values by. Defaults to None.
            record_view_id: The UUID of the specific record view on the operation
                to filter values by. When set, key field values (which are not
                associated with any view) are excluded. Defaults to None.

        Returns:
            The content of the most recent matching record value, or None if no value is found.

        Example:
            ```python
            latest_content = record.get_value_content(
                field_id="field_uuid",
                activity_id="activity_uuid",
                include_sub_record_values=True,
            )
            print(latest_content)

            # Filter by a specific record view on an operation
            latest_in_view = record.get_value_content(
                field_id="field_uuid",
                activity_id="activity_uuid",
                record_view_id="view_uuid",
            )
            ```
        """
        field_uuid = self._client.entity_fields._resolve_data_field_id(field_id)
        activity_uuid = self._client.activities._resolve_activity_id(activity_id)
        sub_record_uuid = self._client.records._resolve_to_record_id(sub_record_id)

        if not field_uuid:
            return None

        values = self.record_values.get(field_uuid)
        if not values:
            return None

        # include key values in the activity data (record_id = None)
        if activity_uuid is not None:
            values = [
                value
                for value in values
                if (value.operation_id == activity_uuid) or value.record_id is None
            ]

        if not include_sub_record_values and sub_record_uuid is None:
            # key values have None for the record_id
            values = [
                value
                for value in values
                if value.record_id == self.id or value.record_id is None
            ]

        if sub_record_uuid:
            values = [value for value in values if value.record_id == sub_record_uuid]

        if record_view_id is not None:
            values = [
                value for value in values if value.record_view_id == record_view_id
            ]

        sorted_values: List[RecordValue] = sorted(
            values,
            key=lambda x: (x.created_at is not None, x.created_at),
            reverse=True,
        )
        value = next(iter(sorted_values), None)
        return value.content if value else None

    def get_activity_data(self, activity_id: ActivityIdentifier) -> dict:
        """Retrieves activity data for a specific activity ID.

        Args:
            activity_id: The identifier of the activity.

                Any type of ActivityIdentifier will be accepted and resolved.

        Returns:
            A dictionary mapping field IDs to their corresponding values for the given activity.
            Only fields with non-None values are included.

        Example:
            ```python
            activity_data = record.get_activity_data(activity_id="activity_uuid")
            print(activity_data.get("field_uuid"))
            ```
        """
        activity_uuid = self._client.activities._resolve_activity_id(activity_id)

        data = {}
        for field_id in self.record_values.keys():
            result = self.get_value_content(field_id, activity_uuid)
            if result is not None:
                data[field_id] = result

        return data

    def update_field(
        self,
        field_id: EntityFieldIdentifier,
        value: Any,
        activity_id: ActivityIdentifier | None,
        record_view_id: Optional[str] = None,
    ) -> RecordValue | None:
        """Updates a specific field of the record with the given value.

        Args:
            field_id: The ID of the field to update.
            value: The new value to set for the field.
            activity_id: The ID of the activity associated with the update, or None if not an activity value
            record_view_id: The UUID of the specific record view on the operation
                to write the value to. Use `Activity.record_views` to discover the
                available views on an operation. Only meaningful when `activity_id`
                is also provided. Defaults to None.

        Returns:
            The updated record value, or None if the server returned an empty body.

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            updated_value = record.update_field(
                field_id="field_uuid",
                value="Updated value",
                activity_id="activity_uuid",
            )
            print(updated_value.content if updated_value else None)
            ```
        """
        return self._write_field_value(field_id, value, activity_id, record_view_id)

    def update_field_file(
        self,
        field_id: EntityFieldIdentifier,
        file_name: str,
        file_data: BinaryIO,
        file_type: str,
        activity_id: Optional[ActivityIdentifier] = None,
        record_view_id: Optional[str] = None,
    ) -> RecordValue | None:
        """Update a record value with a file.

        Args:
            field_id: The ID of the field to update.
            file_name: The name of the file to upload.
            file_data: The binary data of the file.
            file_type: The MIME type of the file.
            activity_id: The ID of the activity, if applicable. Defaults to None.
            record_view_id: The UUID of the specific record view on the operation
                to write the value to. Only meaningful when `activity_id` is also
                provided. Defaults to None.

        Returns:
            The updated record value, or None if the server returned an empty body.

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            with open("report.pdf", "rb") as file_data:
                uploaded_value = record.update_field_file(
                    field_id="file_field_uuid",
                    file_name="report.pdf",
                    file_data=file_data,
                    file_type="application/pdf",
                )
            ```
        """
        field_uuid = self._client.entity_fields._resolve_data_field_id(field_id)
        activity_uuid = self._client.activities._resolve_activity_id(activity_id)

        body = {
            "field_id": field_uuid,
        }

        if activity_uuid:
            body["operation_id"] = activity_uuid
        if record_view_id:
            body["record_view_id"] = record_view_id

        resp = self._client._post_file(
            "/records/" + self.id + "/values/file",
            (file_name, file_data, file_type),
            body,
        )
        self.refetch()

        if resp is None or len(resp) == 0:
            return None

        resource = resp.get("resource")
        if not resource:
            return None

        return RecordValue._from_api(resource, self._client)

    def get_values(self) -> List[RecordValue]:
        """Retrieve all values associated with this record.

        Makes a GET request to fetch the values for the current record using its ID.
        If the request is successful, returns the list of record values. If the
        response is None, returns an empty list.

        Returns:
            A list of RecordValue objects associated with this record. Returns an empty list if no values exist.

        Example:
            ```python
            values = record.get_values()
            print([value.content for value in values])
            ```
        """
        resp = self._client._get("/records/" + self.id + "/values")
        if resp is None:
            return []
        return RecordValue._list_from_api(resp, self._client)

    def refetch(self):
        """Refreshes all the data of the current record instance.

        The record is also removed from all local caches of its associated client.

        Automatically called by mutating methods of this record, but can also be called manually.

        Example:
            ```python
            record.refetch()
            refreshed_value = record.get_value_content(field_id="field_uuid")
            ```
        """

        self._client.records._clear_record_from_caches(self)

        new = self._client.records.get_record_by_id(self.id)
        if new is None:
            _logger.error(f"Unable to refresh Record({self.id})")
            return None
        for k, v in new.__dict__.items():
            setattr(self, k, v)


RecordIdentifier: TypeAlias = Union[Record, str, dict[EntityFieldIdentifier, str]]
"""Identifier type for Record

Record can be identified by:

* object instance of a Record
* uuid
* key field dictionary
    * a dict that maps `EntityFieldIdentifier`s to `str`s
"""


class SearchRecordsQuery(TypedDict, total=False):
    """TypedDict for search records query parameters.

    Attributes:
        record_set_ids (Optional[str]): The IDs of the record sets to search within.
        program_id (Optional[str]): The ID of the program associated with the records.
        entity_slice_id (Optional[str]): The ID of the entity slice to filter records.
        operation_id (Optional[str]): The ID of the operation to filter records.
        identifier_ids (Optional[List[str]]): List of identifier IDs to filter records.
        view_field_filters (Optional[List[ViewFieldFilter]]): List of filters to apply on view fields.
        view_field_sorts (Optional[List[ViewFieldSort]]): List of sorting criteria for view fields.
        entity_field_filters (Optional[List[FieldFilter]]): List of filters to apply on entity fields.
        entity_field_sorts (Optional[List[FieldSort]]): List of sorting criteria for entity fields.
        search_text (Optional[str]): Text string to search for within records.
        limit (Optional[int]): Maximum number of records to return in the search results.

    Example:
        ```python
        from kalbio.records import SearchRecordsQuery, FilterRuleTypeEnum

        query: SearchRecordsQuery = {
            "entity_slice_id": "entity_uuid",
            "search_text": "treatment",
            "entity_field_filters": [
                {
                    "field_id": "status_field_uuid",
                    "filter_type": FilterRuleTypeEnum.IS_EQUAL,
                    "filter_prop": "Completed",
                }
            ],
            "limit": 25,
        }
        ```
    """

    record_set_ids: Optional[str]
    program_id: Optional[str]
    entity_slice_id: Optional[str]
    operation_id: Optional[str]
    identifier_ids: Optional[List[str]]
    view_field_filters: Optional[List[ViewFieldFilter]]
    view_field_sorts: Optional[List[ViewFieldSort]]
    entity_field_filters: Optional[List[FieldFilter]]
    entity_field_sorts: Optional[List[FieldSort]]
    search_text: Optional[str]
    limit: Optional[int]


class RecordsService(_BaseService):
    """Service class for managing records in Kaleidoscope.

    This service provides methods for creating, retrieving, and searching records,
    as well as managing record values and file uploads. It acts as an interface
    between the KaleidoscopeClient and Record objects.

    Example:
        ```python
        # Get a record by ID
        record = client.records.get_record_by_id("record_uuid")
        # Get multiple records (preserves order)
        records = client.records.get_records_by_ids(["id1", "id2"])
        # Search by text
        matches = client.records.search_records(search_text="experiment-a")
        ```
    """

    def __init__(self, client: KaleidoscopeClient):
        super().__init__(client)
        # Per-instance so caches from distinct clients never collide: a client
        # is scoped to one workspace's credentials, and a shared class-level
        # cache would let one client serve another's records.
        # fmt: off
        self._records_uuid_map: TTLCache[str, Record | None] = TTLCache(
            maxsize=1000, ttl=60
        )
        self._records_key_field_map: TTLCache[frozenset, Record | None] = TTLCache(
            maxsize=1000, ttl=60
        )
        # fmt: on
        # cachetools caches are not thread-safe; this client is meant to be
        # shared across threads, so every access to the maps above is guarded.
        self._records_lock = threading.Lock()

    def _use_record_cache(self, use_cache: bool = True) -> bool:
        """Whether record-lookup caches should be consulted for this read."""
        return use_cache and not self._client._is_cache_disabled()

    #########################
    #    Public  Methods    #
    #########################

    def get_record_by_id(
        self, record_id: RecordIdentifier, use_cache: bool = True
    ) -> Record | None:
        """Retrieves a record by its identifier.

        Args:
            record_id: The identifier of the record to retrieve.
                Any type of RecordIdentifier will be accepted and resolved
            use_cache: When False, skip the record cache and fetch from the
                server, refreshing the cached value. Ignored when ``record_id``
                is already a ``Record`` instance, which is returned as-is.

        Returns:
            The record object if found, otherwise None.

        Example:
            ```python
            record = client.records.get_record_by_id("record_uuid")
            print(record.record_identifier if record else "missing")
            ```
        """
        if isinstance(record_id, Record):
            return record_id

        if isinstance(record_id, str):
            return self._get_record_by_uuid(record_id, use_cache=use_cache)
        else:
            return self._get_record_by_key_values(record_id, use_cache=use_cache)

    def get_records_by_ids(
        self,
        record_ids: Sequence[RecordIdentifier],
        batch_size: int = 250,
        use_cache: bool = True,
    ) -> List[Record]:
        """Retrieves records corresponding to the provided list of record IDs.

        Args:
            record_ids: A list of record IDs to retrieve.
            batch_size: How many records retrieved with every API call. Defaults to 250.
            use_cache: When False, skip the record cache and fetch every record
                from the server, refreshing the cached values.

        Returns:
            A list of Record objects corresponding to the provided IDs.

        Example:
            ```python
            records = client.records.get_records_by_ids([
                "record_uuid_1",
                "record_uuid_2",
            ])
            print(len(records))
            ```
        """
        all_records = []

        for batch in itertools.batched(record_ids, batch_size):
            all_records.extend(
                self._get_records_in_order(list(batch), use_cache=use_cache)
            )

        return [record for record in all_records if record]

    def get_or_create_record(
        self, key_values: dict[EntityFieldIdentifier, str]
    ) -> Record | None:
        """Retrieves an existing record matching the provided key-value pairs, or creates a new one if none exists.

        Args:
            key_values: A dictionary containing key-value pairs to identify or create the record.

        Returns:
            The retrieved or newly created Record object, or None if the
            server returned an empty body for a newly created record.

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            record = client.records.get_or_create_record({"FIELD_ID": "KEY-123"})
            print(record.record_identifier if record else "not created")
            ```
        """
        try:
            resolved_values = self._resolve_key_values(key_values)
        except ValueError as e:
            _logger.error(f"Invalid key fields: {e}")
            return None

        record_key = frozenset(resolved_values.items())

        # A prior lookup miss caches None under this key; only reuse a real hit,
        # otherwise fall through to create the record.
        if self._use_record_cache():
            with self._records_lock:
                cached = self._records_key_field_map.get(record_key)
            if cached is not None:
                return cached

        resp = self._client._post(
            "/records",
            {"key_field_to_value": resolved_values},
        )
        if resp is None or len(resp) == 0:
            return None

        return self._create_record(resp)

    def search_records(self, **params: Unpack[SearchRecordsQuery]) -> list[str]:
        """Searches for records using the provided query parameters.

        Args:
            **params: Keyword arguments representing search criteria. Non-string values will be JSON-encoded before being sent.

        Returns:
            A list of record identifiers matching the search criteria. Returns an empty list if the response is empty.

        Example:
            ```python
            record_ids = client.records.search_records(search_text="cell line")
            ```
        """
        client_params = {
            key: (value if isinstance(value, str) else json.dumps(value))
            for key, value in params.items()
        }
        resp = self._client._get("/records/search", client_params)
        if resp is None:
            return []

        return resp

    def create_record_value_file(
        self,
        record_id: RecordIdentifier,
        field_id: str,
        file_name: str,
        file_data: BinaryIO,
        file_type: str,
        activity_id: Optional[str] = None,
    ) -> RecordValue | None:
        """Creates a record value for a file and uploads it to the specified record.

        Args:
            record_id: The identifier of the record to which the file value will be added.

                Any type of RecordIdentifier will be accepted and resolved.
            field_id: The identifier of the field associated with the file value.
            file_name: The name of the file to be uploaded.
            file_data: A binary stream representing the file data.
            file_type: The MIME type of the file.
            activity_id: An optional activity identifier.

        Returns:
            The created RecordValue object, or None if the record was not
            found or the server returned an empty body.

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            with open("results.csv", "rb") as file_data:
                value = client.records.create_record_value_file(
                    record_id="record_uuid",
                    field_id="file_field_uuid",
                    file_name="results.csv",
                    file_data=file_data,
                    file_type="text/csv",
                )
            ```
        """
        record_uuid = self._resolve_to_record_id(record_id)
        if record_uuid is None:
            return None

        body = {
            "field_id": field_id,
        }

        if activity_id:
            body["operation_id"] = activity_id

        resp = self._client._post_file(
            "/records/" + record_uuid + "/values/file",
            (file_name, file_data, file_type),
            body,
        )

        with self._records_lock:
            cached_record = self._records_uuid_map.get(record_uuid)
        if cached_record is not None:
            cached_record.refetch()

        if resp is None or len(resp) == 0:
            return None

        resource = resp.get("resource")
        if not resource:
            return None

        return RecordValue._from_api(resource, self._client)

    def clear_record_caches(self):
        """Clears all caches for Record objects.

        Call whenever caches may be stale.

        Note that all methods of Record automatically update the caches.
        This is to be called if you would like your program to refetch the latest data from the API.

        Example:
            ```python
            client.records.clear_record_caches()
            ```
        """
        with self._records_lock:
            self._records_uuid_map.clear()
            self._records_key_field_map.clear()
        self._client.activities.get_activities_with_record.cache_clear()

    #########################
    #    Private Methods    #
    #########################

    def _create_record(self, data: dict) -> Record | None:
        """Creates a new Record instance from the provided data.

        Validates the input data using the Record model, sets the client for the record,
        and adds it local record caches.

        Args:
            data: The data to be validated and used for creating the Record.

        Returns:
            The validated and initialized Record instance or None, if the data is invalid.
        """
        try:
            record = Record._from_api(data, self._client)
        except ValidationError as e:
            _logger.error(f"Failed to validate data as record: {e}")
            return None

        key = self.__record_to_hashable_key_fields(record)
        with self._records_lock:
            self._records_uuid_map[record.id] = record
            self._records_key_field_map[key] = record

        return record

    def _create_record_list(self, data: list[dict]) -> List[Record | None]:
        """Converts a list of record data into a list of record objects.

        Each piece of data is validated as a Record, has the client set for the record,
        and is added to local record caches.

        Args:
            data: The input data to be converted into Record objects.

        Returns:
            A list of Record objects with the client set.
        """

        return [self._create_record(r) for r in data]

    def _resolve_key_values(
        self, key_values: dict[EntityFieldIdentifier, str]
    ) -> dict[str, str]:
        """Resolves EntityFieldIdentifier of a dict of field-to-value pairings

        Args:
            key_values: the unresolved field-to-value pairings that identify a given record

        Raises:
            ValueError: If an EntityFieldIdentifier cannot be resolved

        Returns:
            The resolved field-to-value pairings
        """
        result = {}

        for k, v in key_values.items():
            key = self._client.entity_fields._resolve_key_field_id(k)

            if key is None:
                raise ValueError(f"Invalid EntityFieldIdentifier {k}")

            result[key] = v

        return result

    def __record_to_hashable_key_fields(
        self, record: Record
    ) -> frozenset[tuple[str, Any]]:
        """Gets a unique frozenset from a given record.

        Args:
            record: the record to get the frozenset from

        Returns:
            Frozenset of fields & values of a given record.
        """
        identifier_ids = set(record.identifier_ids)

        # Mirror the lookup key built in `_get_record_by_key_values`: the
        # identifier value can sit at any position in a field's value list, and
        # lookup keys carry the value as a string.
        pairs: list[tuple[str, Any]] = []
        for key_field_id, values in record.record_values.items():
            identifier_value = next(
                (value for value in values if value.id in identifier_ids), None
            )
            if identifier_value is not None:
                pairs.append((key_field_id, str(identifier_value.content)))

        return frozenset(pairs)

    def _get_record_by_uuid(
        self, record_id: str, use_cache: bool = True
    ) -> Record | None:
        """Retrieves a record by its uuid.

        If corresponding record is cached, it is retrieved from the cache. Otherwise, it is fetched from the API.

        Args:
            record_id: the uuid of a record
            use_cache: when False, skip the cache and fetch from the API.

        Returns:
            The corresponding record.
        """
        if self._use_record_cache(use_cache):
            with self._records_lock:
                cached = self._records_uuid_map.get(record_id, _MISSING)
            if cached is not _MISSING:
                return cached

        resp = self._client._get("/records/" + record_id)

        if resp is None:
            with self._records_lock:
                self._records_uuid_map[record_id] = None
            return None

        return self._create_record(resp)

    def _get_record_by_key_values(
        self, key_values: dict[EntityFieldIdentifier, str], use_cache: bool = True
    ) -> Record | None:
        """Retrieves a record by a corresponding field-to-value dict

        Args:
            key_values: the field-to-value dict
            use_cache: when False, skip the cache and fetch from the API.

        Returns:
            the corresponding record
        """
        try:
            resolved_values = self._resolve_key_values(key_values)
        except ValueError as e:
            _logger.error(f"Invalid key fields: {e}")
            return None

        key = frozenset(resolved_values.items())

        if self._use_record_cache(use_cache):
            with self._records_lock:
                cached = self._records_key_field_map.get(key, _MISSING)
            if cached is not _MISSING:
                return cached

        resp = self._client._get(
            "/records/identifiers",
            {"records_key_field_to_value": json.dumps([resolved_values])},
        )

        if resp is None or len(resp) == 0:
            with self._records_lock:
                self._records_key_field_map[key] = None
            return None

        result = resp[0].get("record")
        if not result:
            raise ValueError("Response is not valid record")

        return self._create_record(result)

    def _resolve_to_record_id(
        self, identifier: RecordIdentifier | None, lazy: bool = False
    ) -> str | None:
        """Resolves a record identifier to its UUID.

        Set `lazy` to true if uuids should not be validated.

        Given a record type:

        * A Record will have its uuid returned
        * A UUID will return itself
        * A field-to-value dict will be retrieved from cache or an API request

        Args:
            identifier: resolves a RecordIdentifier, is nullable
            lazy: if lazy, then it will not ensure that the uuid is a valid uuid.

        Returns:
            The record UUID if found, otherwise None.
        """
        if identifier is None:
            return None

        if isinstance(identifier, Record):
            if lazy:
                return identifier.id

            record = self._get_record_by_uuid(identifier.id)
            return record.id if record else None

        if isinstance(identifier, str):
            return identifier
        else:
            record = self._get_record_by_key_values(identifier)

            if record:
                return record.id
            else:
                return None

    def _get_records_in_order(
        self, identifiers: list[RecordIdentifier], use_cache: bool = True
    ) -> list[Record | None]:
        """Gets records in order. Invalid record identifiers are replaced with None, rather than being removed from the result.

        Args:
            identifiers: a list of record identifiers to retrieve
            use_cache: when False, refetch every record instead of reusing cached ones.

        Returns:
            The set of corresponding records, in the original order of the record identifiers.
        """
        resolved = [
            self._resolve_to_record_id(ident, lazy=True) for ident in identifiers
        ]

        cache_active = self._use_record_cache(use_cache)

        if cache_active:
            with self._records_lock:
                to_fetch = [
                    uuid
                    for uuid in resolved
                    if uuid and uuid not in self._records_uuid_map
                ]
        else:
            # Bypassing the cache means refetch everything; drop the stale
            # entries first so an id the server no longer returns resolves to
            # None instead of a lingering cached record.
            to_fetch = [uuid for uuid in resolved if uuid]
            with self._records_lock:
                for uuid in to_fetch:
                    self._records_uuid_map.pop(uuid, None)

        if to_fetch:
            resp = (
                self._client._get("/records", {"record_ids": ",".join(to_fetch)})
                or []
            )
            self._create_record_list(resp)

        with self._records_lock:
            ordered = [
                self._records_uuid_map.get(uuid) if uuid else None for uuid in resolved
            ]

        return ordered

    def _clear_record_from_caches(self, record: Record):
        """Removes a given record from the record service caches

        Call when a record is updated."""
        key = self.__record_to_hashable_key_fields(record)
        with self._records_lock:
            self._records_uuid_map.pop(record.id, None)
            self._records_key_field_map.pop(key, None)
