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
from cachetools import TTLCache
import logging
from datetime import datetime
from enum import Enum
import json
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import KaleidoscopeClient
from kalbio.entity_fields import EntityFieldIdentifier
from pydantic import TypeAdapter, ValidationError
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    Dict,
    List,
    Optional,
    TypeAlias,
    TypedDict,
    Union,
    Unpack,
)

if TYPE_CHECKING:
    from kalbio.activities import Activity, ActivityIdentifier

_logger = logging.getLogger(__name__)


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
        )
        ```
    """

    content: Any
    created_at: Optional[datetime] = None  # data value
    record_id: Optional[str] = None  # data value
    operation_id: Optional[str] = None  # data value

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

    created_at: datetime
    entity_slice_id: str
    identifier_ids: List[str]
    record_identifier: str
    record_values: Dict[str, List[RecordValue]]  # [field_id, values[]]
    initial_operation_id: Optional[str] = None
    sub_record_ids: List[str]

    def __str__(self):
        return f"{self.record_identifier}"

    def get_activities(self) -> List["Activity"]:
        """Retrieves a list of activities associated with this record.

        Returns:
            A list of activities related to this record.

        Note:
            If an exception occurs during the API request, it logs the error and returns an empty list.

        Example:
            ```python
            activities = record.get_activities()
            for activity in activities:
                print(activity.id)
            ```
        """
        return self._client.activities.get_activities_with_record(self.id)

    def add_value(
        self,
        field_id: EntityFieldIdentifier,
        content: Any,
        activity_id: Optional[ActivityIdentifier] = None,
    ) -> None:
        """Adds a value to a specified field for a given activity.

        Args:
            field_id: Identifier of the field to which the value will be added.

                Any type of EntityFieldIdentifier will be accepted and resolved.
            content: The value/content to be saved for the field.
            activity_id: The identifier of the activity. Defaults to None.

                Any type of EntityFieldIdentifier will be accepted and resolved.

        Example:
            ```python
            record.add_value(
                field_id="field_uuid",
                content="Experiment result",
                activity_id="activity_uuid",
            )
            ```
        """
        try:
            self._client._post(
                "/records/" + self.id + "/values",
                {
                    "content": content,
                    "field_id": self._client.entity_fields._resolve_data_field_id(
                        field_id
                    ),
                    "operation_id": (
                        self._client.activities._resolve_activity_id(activity_id)
                    ),
                },
            )
            self.refetch()
            return
        except Exception as e:
            _logger.error(f"Error adding this value: {e}")
            return

    def get_value_content(
        self,
        field_id: EntityFieldIdentifier,
        activity_id: Optional[ActivityIdentifier] = None,
        include_sub_record_values: Optional[bool] = False,
        sub_record_id: Optional["RecordIdentifier"] = None,
    ) -> Any | None:
        """Retrieves the content of a record value for a specified field.

        Optionally filtered by activity, sub-record, and inclusion of sub-record values.

        Args:
            field_id: The ID of the field to retrieve the value for.
            activity_id: The ID of the activity to filter values by. Defaults to None.
            include_sub_record_values: Whether to include values from sub-records. Defaults to False.
            sub_record_id: The ID of a specific sub-record to filter values by. Defaults to None.

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

        if not include_sub_record_values:
            # key values have None for the record_id
            values = [
                value
                for value in values
                if value.record_id == self.id or value.record_id is None
            ]

        if sub_record_uuid:
            values = [value for value in values if value.record_id == sub_record_uuid]

        sorted_values: List[RecordValue] = sorted(
            values,
            key=lambda x: x.created_at if x.created_at else datetime.min,
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
    ) -> RecordValue | None:
        """Updates a specific field of the record with the given value.

        Args:
            field_id: The ID of the field to update.
            value: The new value to set for the field.
            activity_id: The ID of the activity associated with the update, or None if not an activity value

        Returns:
            The updated record value if the operation is successful, otherwise None.

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
        try:
            field_uuid = self._client.entity_fields._resolve_data_field_id(field_id)
            activity_uuid = self._client.activities._resolve_activity_id(activity_id)

            body = {
                "field_id": field_uuid,
                "content": value,
                "operation_id": activity_uuid,
            }

            resp = self._client._post("/records/" + self.id + "/values", body)
            self.refetch()

            if resp is None or len(resp) == 0:
                return None

            return RecordValue.model_validate(resp.get("resource"))
        except Exception as e:
            _logger.error(f"Error updating the field: {e}")
            return None

    def update_field_file(
        self,
        field_id: EntityFieldIdentifier,
        file_name: str,
        file_data: BinaryIO,
        file_type: str,
        activity_id: Optional[ActivityIdentifier] = None,
    ) -> RecordValue | None:
        """Update a record value with a file.

        Args:
            field_id: The ID of the field to update.
            file_name: The name of the file to upload.
            file_data: The binary data of the file.
            file_type: The MIME type of the file.
            activity_id: The ID of the activity, if applicable. Defaults to None.

        Returns:
            The updated record value if the operation is successful, otherwise None.

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
        try:
            field_uuid = self._client.entity_fields._resolve_data_field_id(field_id)
            activity_uuid = self._client.activities._resolve_activity_id(activity_id)

            body = {
                "field_id": field_uuid,
            }

            if activity_uuid:
                body["operation_id"] = activity_uuid

            resp = self._client._post_file(
                "/records/" + self.id + "/values/file",
                (file_name, file_data, file_type),
                body,
            )
            self.refetch()

            if resp is None or len(resp) == 0:
                return None

            return RecordValue.model_validate(resp.get("resource"))
        except Exception as e:
            _logger.error(f"Error uploading file to field: {e}")
            return None

    def get_values(self) -> List[RecordValue]:
        """Retrieve all values associated with this record.

        Makes a GET request to fetch the values for the current record using its ID.
        If the request is successful, returns the list of record values. If the response
        is None or an error occurs during the request, returns an empty list.

        Returns:
            A list of RecordValue objects associated with this record. Returns an empty list if no values exist.

        Note:
            If an exception occurs during the API request, it logs the error and returns an empty list.

        Example:
            ```python
            values = record.get_values()
            print([value.content for value in values])
            ```
        """
        try:
            resp = self._client._get("/records/" + self.id + "/values")
            if resp is None:
                return []
            return TypeAdapter(List[RecordValue]).validate_python(resp)
        except Exception as e:
            _logger.error(f"Error fetching values for this record: {e}")
            return []

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


class SearchRecordsQuery(TypedDict):
    """TypedDict for search records query parameters.

    Attributes:
        record_set_id (Optional[str]): The ID of the record set to search within.
        program_id (Optional[str]): The ID of the program associated with the records.
        entity_slice_id (Optional[str]): The ID of the entity slice to filter records.
        operation_id (Optional[str]): The ID of the operation to filter records.
        identifier_ids (Optional[List[str]]): List of identifier IDs to filter records.
        record_set_filters (Optional[List[str]]): List of filters to apply on record sets.
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

    record_set_id: Optional[str]
    program_id: Optional[str]
    entity_slice_id: Optional[str]
    operation_id: Optional[str]
    identifier_ids: Optional[List[str]]
    record_set_filters: Optional[List[str]]
    view_field_filters: Optional[List[ViewFieldFilter]]
    view_field_sorts: Optional[List[ViewFieldSort]]
    entity_field_filters: Optional[List[FieldFilter]]
    entity_field_sorts: Optional[List[FieldSort]]
    search_text: Optional[str]
    limit: Optional[int]


class RecordsService:
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

    # fmt: off
    _records_uuid_map: TTLCache[str, Record | None] = TTLCache(
        maxsize=1000, ttl=60
    )
    _records_key_field_map: TTLCache[frozenset, Record | None] = TTLCache(
        maxsize=1000, ttl=60
    )
    # fmt: on

    def __init__(self, client: KaleidoscopeClient):
        self._client = client

    #########################
    #    Public  Methods    #
    #########################

    def get_record_by_id(self, record_id: RecordIdentifier) -> Record | None:
        """Retrieves a record by its identifier.

        Args:
            record_id: The identifier of the record to retrieve.
                Any type of RecordIdentifier will be accepted and resolved

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
            return self._get_record_by_uuid(record_id)
        else:
            return self._get_record_by_key_values(record_id)

    def get_records_by_ids(
        self, record_ids: List[RecordIdentifier], batch_size: int = 250
    ) -> List[Record]:
        """Retrieves records corresponding to the provided list of record IDs.

        Args:
            record_ids: A list of record IDs to retrieve.
            batch_size: How many records retrieved with every API call. Defaults to 250.

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
        try:
            all_records = []

            for batch in itertools.batched(record_ids, batch_size):
                all_records.extend(self._get_records_in_order(list(batch)))

            return [uuid for uuid in all_records if uuid]
        except Exception as e:
            _logger.error(f"Error fetching records {record_ids}: {e}")
            return []

    def get_or_create_record(
        self, key_values: dict[EntityFieldIdentifier, str]
    ) -> Record | None:
        """Retrieves an existing record matching the provided key-value pairs, or creates a new one if none exists.

        Args:
            key_values: A dictionary containing key-value pairs to identify or create the record.

        Returns:
            The retrieved or newly created Record object if successful or None, if no record is found or created

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

        if record_key in self._records_key_field_map:
            return self._records_key_field_map[record_key]

        try:
            resp = self._client._post(
                "/records",
                {"key_field_to_value": resolved_values},
            )
            if resp is None or len(resp) == 0:
                return None

            return self._create_record(resp)
        except Exception as e:
            _logger.error(f"Error creating record {key_values}: {e}")
            return None

    def search_records(self, **params: Unpack[SearchRecordsQuery]) -> list[str]:
        """Searches for records using the provided query parameters.

        Args:
            **params: Keyword arguments representing search criteria. Non-string values will be JSON-encoded before being sent.

        Returns:
            A list of record identifiers matching the search criteria. Returns an empty list if the response is empty.

        Note:
            If an exception occurs during the API request, it logs the error and returns an empty list.

        Example:
            ```python
            record_ids = client.records.search_records(search_text="cell line")
            ```
        """
        try:
            client_params = {
                key: (value if isinstance(value, str) else json.dumps(value))
                for key, value in params.items()
            }
            resp = self._client._get("/records/search", client_params)
            if resp is None:
                return []

            return resp
        except Exception as e:
            _logger.error(f"Error searching records {params}: {e}")
            return []

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
            The created RecordValue object if successful, otherwise None.

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

        try:
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

            if resp is None or len(resp) == 0:
                return None

            return RecordValue.model_validate(resp.get("resource"))
        except Exception as e:
            _logger.error(f"Error uploading file to record field: {e}")
            return None

    def clear_record_caches(self):
        """Clears all caches for Record objects.

        Call whenever caches may be stale.

        Note that all methods of Record automaticaly update the caches.
        This is to be called if you would like your program to refetch the latest data from the API.

        Example:
            ```python
            client.records.clear_record_caches()
            ```
        """
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
            record = Record.model_validate(data)
        except ValidationError as e:
            _logger.error(f"Failed to validate data as record: {e}")
            return None

        record._set_client(self._client)

        self._records_uuid_map[record.id] = record
        key = self.__record_to_hashable_key_fields(record)
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
        key_fields = set(record.identifier_ids)

        # hash a record according to its key values
        return frozenset(
            (key_field_id, value[0].content)
            for key_field_id, value in record.record_values.items()
            if value and (value[0].id in key_fields)
        )

    def _get_record_by_uuid(self, record_id: str) -> Record | None:
        """Retrieves a record by its uuid.

        If corresponding record is cached, it is retrieved from the cache. Otherwise, it is fetched from the API.

        Args:
            record_id: the uuid of a record

        Returns:
            The corresponding record.
        """
        if record_id in self._records_uuid_map:
            return self._records_uuid_map[record_id]

        try:
            resp = self._client._get("/records/" + record_id)

            if resp is None:
                self._records_uuid_map[record_id] = None
                return None

            return self._create_record(resp)
        except Exception as e:
            _logger.error(f"Error fetching record {id}: {e}")
            return None

    def _get_record_by_key_values(
        self, key_values: dict[EntityFieldIdentifier, str]
    ) -> Record | None:
        """Retrieves a record by a corresponding field-to-value dict

        Args:
            key_values: the field-to-value dict

        Returns:
            the corresponding record
        """
        try:
            resolved_values = self._resolve_key_values(key_values)
        except ValueError as e:
            _logger.error(f"Invalid key fields: {e}")
            return None

        key = frozenset(resolved_values.items())

        if key in self._records_key_field_map:
            return self._records_key_field_map[key]

        try:
            resp = self._client._get(
                "/records/identifiers",
                {"records_key_field_to_value": json.dumps([resolved_values])},
            )

            if resp is None or len(resp) == 0:
                self._records_key_field_map[key] = None
                return None

            result = resp[0].get("record")
            if not result:
                raise ValueError("Response is not valid record")

            return self._create_record(result)
        except Exception as e:
            _logger.error(f"Error fetching records {key_values}: {e}")
            return None

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
        self, identifiers: list[RecordIdentifier]
    ) -> list[Record | None]:
        """Gets records in order. Invalid record identifiers are replaced with None, rather than being removed from the result.

        Args:
            identifiers: a list of record identifiers to retrieve

        Returns:
            The set of corresponding records, in the original order of the record identifiers.
        """
        resolved = [
            self._resolve_to_record_id(ident, lazy=True) for ident in identifiers
        ]

        # fmt: off
        to_fetch = [
            uuid for uuid in resolved
            if uuid and uuid not in self._records_uuid_map
        ]
        # fmt: on

        resp = self._client._get(f"/records?record_ids={','.join(to_fetch)}") or []
        self._create_record_list(resp)

        ordered = [
            self._records_uuid_map.get(uuid) if uuid else None for uuid in resolved
        ]

        return ordered

    def _clear_record_from_caches(self, record: Record):
        """Removes a given record from the record service caches

        Call when a record is updated."""
        self._records_uuid_map.pop(record.id, None)
        self._records_key_field_map.pop(
            self.__record_to_hashable_key_fields(record), None
        )
