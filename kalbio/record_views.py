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

from datetime import datetime
from enum import Enum
from kalbio._base import _BaseService
from kalbio._cache import cached
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import _require_response_body
from typing import Any, Dict, List, Optional, TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from kalbio.entity_fields import DataField, DataFieldTypeEnum



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


class FilterRuleType(str, Enum):
    """Comparison rule applied by a `RecordViewFilter`."""

    IS_SET = "is_set"
    IS_EMPTY = "is_empty"
    IS_EQUAL = "is_equal"
    IS_ANY_OF_TEXT = "is_any_of_text"
    IS_NOT_ANY_OF_TEXT = "is_not_any_of_text"
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
    SUBFIELD_RULE = "subfield_rule"


class RecordViewSort(TypedDict):
    """Sort configuration on a record view.

    Exactly one of `key_field_id` or `view_field_id` should be non-null.

    Attributes:
        key_field_id (Optional[str]): UUID of the key field to sort by, if any.
        view_field_id (Optional[str]): UUID of the view field to sort by, if any.
        descending (bool): Sort direction.
        plot_field_config (Optional[dict]): Optional plot-field config when
            sorting by a plot field. Keep as raw dict; shape depends on the
            field's chart variant.
    """

    key_field_id: Optional[str]
    view_field_id: Optional[str]
    descending: bool
    plot_field_config: Optional[dict]


class RecordViewFilter(TypedDict):
    """Filter configuration on a record view.

    Exactly one of `key_field_id` or `view_field_id` should be non-null.

    Attributes:
        key_field_id (Optional[str]): UUID of the key field to filter on.
        view_field_id (Optional[str]): UUID of the view field to filter on.
        filter_type (str): The comparison rule. Use `FilterRuleType` values.
        filter_prop (Any): The filter's argument (e.g. the value to compare
            against, a range, an array of options). Shape depends on
            `filter_type`; server accepts arbitrary JSON here.
        plot_field_config (Optional[dict]): Optional plot-field config when
            filtering by a plot field.
    """

    key_field_id: Optional[str]
    view_field_id: Optional[str]
    filter_type: str
    filter_prop: Any
    plot_field_config: Optional[dict]


class RecordViewColorFilter(TypedDict):
    """Color rule on a record view: a filter plus the color to apply when rows match.

    Same shape as `RecordViewFilter` with one extra field.

    Attributes:
        key_field_id (Optional[str]): UUID of the key field to filter on.
        view_field_id (Optional[str]): UUID of the view field to filter on.
        filter_type (str): The comparison rule. Use `FilterRuleType` values.
        filter_prop (Any): Filter argument.
        plot_field_config (Optional[dict]): Optional plot-field config.
        color (str): Color string to apply to matching rows.
    """

    key_field_id: Optional[str]
    view_field_id: Optional[str]
    filter_type: str
    filter_prop: Any
    plot_field_config: Optional[dict]
    color: str


class RecordView(_KaleidoscopeBaseModel):
    """Represents a view of records in the Kaleidoscope system.

    A RecordView defines how records are displayed and accessed: the entity
    slice it belongs to, associated programs/operations, visible fields,
    filters, sorts, color rules, and grouping config.

    Attributes:
        id (str): UUID of the record view.
        view_name (str): Display name of the view.
        entity_slice_id (str): ID of the entity slice this view belongs to.
        program_ids (List[str]): Programs associated with this view.
        operation_ids (Optional[List[str]]): Operations this view is attached to.
        operation_definition_ids (Optional[List[str]]): Operation definitions
            (experiment types) this view is attached to.
        view_fields (List[ViewField]): Fields visible in this view.
        filters (List[RecordViewFilter]): View filter configurations.
        sorts (List[RecordViewSort]): View sort configurations.
        color_filters (List[RecordViewColorFilter]): Color-filter configurations.
        record_set_ids_filter (List[str]): Record set IDs restricting the view.
        record_ids_filter (List[str]): Specific record IDs restricting the view.
        incrementing_field_ids (List[str]): Incrementing field UUIDs.
        sort_order (Optional[str]): `'alphabetical'`, `'created_date'`,
            `'manual'`, or None.
        sort_descending (Optional[bool]): Sort direction.
        view_mode (Optional[str]): Display mode (e.g. `'table'`).
        parent_record_view_id (Optional[str]): Parent view UUID, if this view
            was created from another.
        is_archived (bool): Whether the view is archived.
        is_template (bool): Whether this view is a reusable template.
            See `kalbio.result_table_templates.ResultTableTemplate`.
        template_name (Optional[str]): Human-readable template label, set
            only when `is_template` is True.
        group_by_mode (Optional[str]): Grouping mode.
        group_by_field_id (Optional[str]): Group-by field UUID.
        workspace_id (Optional[str]): UUID of the workspace.
        created_by (Optional[str]): UUID of the user who created the view.
        last_updated_by (Optional[str]): UUID of the user who last updated the view.
        created_at (Optional[datetime]): Creation timestamp.
        updated_at (Optional[datetime]): Last-updated timestamp.
    """

    view_name: Optional[str] = None
    entity_slice_id: Optional[str] = None
    program_ids: List[str] = []
    operation_ids: Optional[List[str]] = None
    operation_definition_ids: Optional[List[str]] = None
    view_fields: List[ViewField] = []
    filters: List[RecordViewFilter] = []
    sorts: List[RecordViewSort] = []
    color_filters: List[RecordViewColorFilter] = []
    record_set_ids_filter: List[str] = []
    record_ids_filter: List[str] = []
    incrementing_field_ids: List[str] = []
    sort_order: Optional[str] = None
    sort_descending: Optional[bool] = None
    view_mode: Optional[str] = None
    parent_record_view_id: Optional[str] = None
    is_archived: bool = False
    is_template: bool = False
    template_name: Optional[str] = None
    group_by_mode: Optional[str] = None
    group_by_field_id: Optional[str] = None
    workspace_id: Optional[str] = None
    created_by: Optional[str] = None
    last_updated_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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

        Raises:
            KalbioAPIError: If the API request fails.
        """
        resp = self._client._put(
            "/record_views/" + self.id + "/add_key_field", dict(body)
        )
        if resp is not None:
            fresh = RecordView.model_validate(resp)
            for key, value in fresh:
                setattr(self, key, value)
            self._set_client(self._client)
        self._client.record_views._clear_record_view_caches()
        # Transferred records may move to a different slice, so drop record caches.
        self._client.records.clear_record_caches()

    class ReplaceKeyFieldsBody(TypedDict, total=False):
        """TypedDict defining the body for replacing key fields on a record view.

        Attributes:
            add_key_field_names (List[str]): Names of key fields to add to the view.
            remove_key_field_ids (List[str]): UUIDs of key fields to remove from the view.
            records_to_transfer (Optional[List[RecordTransfer]]): One entry per
                record currently on the view. Each entry's
                ``key_field_name_to_value`` must cover the FULL new key set
                (existing − removed + added) — the server rejects partial maps.
        """

        add_key_field_names: List[str]
        remove_key_field_ids: List[str]
        records_to_transfer: Optional[List[RecordTransfer]]

    def replace_key_fields(self, body: ReplaceKeyFieldsBody) -> Optional["RecordView"]:
        """Atomically swap key fields on this record view.

        The server creates (or reuses) the slice whose key set is
        ``(existing − removed + added)``, copies this view onto it, transfers
        any records via the transfer flow, and returns the NEW view. The new
        view has a different ``id`` and ``entity_slice_id``, so this method
        returns a fresh ``RecordView`` rather than mutating ``self``.

        Args:
            body: Request body with adds (by name), removes (by id), and
                per-record key values for the new slice.

        Returns:
            The new RecordView, or None if the request failed.
        """
        resp = self._client._put(
            "/record_views/" + self.id + "/replace_key_fields", dict(body)
        )
        # The server creates a new slice/view and transfers records onto it, so
        # both the view list and the record caches are now stale.
        self._client.record_views._clear_record_view_caches()
        self._client.records.clear_record_caches()
        if resp is None:
            return None
        new_view = RecordView.model_validate(resp)
        new_view._set_client(self._client)
        return new_view


class RecordViewsService(_BaseService):
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

    def _clear_record_view_caches(self) -> None:
        """Clears the cached record-view list.

        Call when views are created, removed, or updated — including when an
        operation is created, since the server attaches new views to it.
        """
        self.get_record_views.cache_clear()

    def _create_record_views_list(self, data: list[dict]) -> List[RecordView]:
        """Converts a list of data dictionaries into a list of RecordView objects and sets the client for each RecordView.

        Args:
            data (list): A list of dictionaries representing record view data.

        Returns:
            List[RecordView]: A list of RecordView objects with the client set.

        Raises:
            ValidationError: If the data could not be validated as a list of RecordView objects.
        """
        return RecordView._list_from_api(data, self._client)

    @cached
    def get_record_views(self) -> List[RecordView]:
        """Retrieves the regular record views in the workspace.

        Templates (where `is_template` is True) are excluded from this list.
        To retrieve templates, use `client.result_table_templates.get_templates()`.

        This method caches its values.

        Returns:
            List[RecordView]: Regular (non-template) record views in the workspace.
        """
        resp = _require_response_body(
            "GET", "/record_views", self._client._get("/record_views")
        )
        all_views = self._create_record_views_list(resp)
        return [v for v in all_views if not v.is_template]

    def get_data_fields_on_view(
        self,
        view_id: str,
        field_type: Optional["DataFieldTypeEnum"] = None,
    ) -> List["DataField"]:
        """Get the data fields visible on a given record view.

        Walks the view's `view_fields`, resolves each `data_field_id`
        via `client.entity_fields.get_data_field_by_id`, and optionally
        filters by `field_type`.

        Useful for discovering field UUIDs needed by activity-definition
        advanced settings (e.g. `registration_status_field_id`).

        Args:
            view_id: UUID of the record view.
            field_type: Optional data field type to filter by.

        Returns:
            DataField objects on the view, in the view's field order.
            Empty if the view is not found, has no data fields, or no
            fields match `field_type`.

        Example:
            ```python
            status_field = client.record_views.get_data_fields_on_view(
                view_id, DataFieldTypeEnum.STATUS
            )[0]
            ```
        """
        view = next(
            (v for v in self.get_record_views() if v.id == view_id),
            None,
        )
        if view is None:
            return []

        fields: List["DataField"] = []
        for vf in view.view_fields:
            data_field_id = vf.get("data_field_id")
            if not data_field_id:
                continue
            df = self._client.entity_fields.get_data_field_by_id(data_field_id)
            if df is None:
                continue
            if field_type is not None and df.field_type != field_type:
                continue
            fields.append(df)
        return fields
