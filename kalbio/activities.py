"""Activities Module for Kaleidoscope API Client.

This module provides functionality for managing activities (tasks, experiments,
projects, stages, milestones, and design cycles) within the Kaleidoscope platform. It includes
models for activities, activity definitions, and properties, as well as service classes for
performing CRUD operations and managing activity workflows.

The module manages:

- Activity creation, updates, and status transitions
- Activity definitions
- Properties
- Records of activities
- User and group assignments
- Labels of activities
- Related programs
- Parent-child activity relationships
- Activity dependencies and scheduling

Classes and types:
    ActivityStatusEnum: Enumeration of possible activity statuses used across activity workflows.
    ActivityType: Type alias for supported activity categories (task, experiment, project, stage, milestone, cycle).
    Property: Model representing a property (field) attached to entities, with update and file upload helpers.
    ActivityDefinition: Template/definition for activities (templates for programs, users, groups, labels, and properties).
    Activity: Core activity model (task/experiment/project) with cached relations, record accessors, and update helpers.
    ActivitiesService: Service class exposing CRUD and retrieval operations for activities and activity definitions.
    ActivityIdentifier: Identifier union for activities (instance, title, or UUID).
    DefinitionIdentifier: Identifier union for activity definitions (instance, title, or UUID).

Example:
    ```python
    # Create a new activity
    activity = client.activities.create_activity(
        title="Synthesis Experiment",
        activity_type="experiment",
        program_ids=["program-uuid", ...],
        assigned_user_ids=["user-uuid", ...]
    )

    # Update activity status
    activity.update(status=ActivityStatusEnum.IN_PROGRESS)

    # Add records to activity
    activity.add_records(["record-uuid"])

    # Get activity data
    record_data = activity.get_record_data()
    ```

Note:
    This module uses Pydantic for data validation and serialization. All datetime
    objects are timezone-aware and follow ISO 8601 format.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    Dict,
    List,
    Literal,
    Optional,
    TypeAlias,
    TypedDict,
    Union,
)

from pydantic import Field

from kalbio._base import _BaseService
from kalbio._cache import cached, cached_model_property

from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import _require_response_body, KalbioResponseError
from kalbio.entity_fields import UNSET, DataField, _UnsetType
from kalbio.labels import Label
from kalbio.programs import Program
from kalbio.record_views import RecordView
from kalbio.workspace import WorkspaceGroup, WorkspaceUser

if TYPE_CHECKING:
    from kalbio.records import Record, RecordIdentifier
    from kalbio.result_table_templates import (
        ResultTableTemplate,  # noqa: F401  used in ActivityDefinition.templates
    )


_logger = logging.getLogger(__name__)


class ActivityStatusEnum(str, Enum):
    """Enumeration of possible activity status values.

    This enum defines all possible states that an activity can be in during its lifecycle,
    including general workflow states, review states, and domain-specific states for
    design, synthesis, testing, and compound selection processes.

    Attributes:
        REQUESTED (str): Activity has been requested but not yet started.
        TODO (str): Activity is queued to be worked on.
        IN_PROGRESS (str): Activity is currently being worked on.
        NEEDS_REVIEW (str): Activity requires review.
        BLOCKED (str): Activity is blocked by dependencies or issues.
        PAUSED (str): Activity has been temporarily paused.
        CANCELLED (str): Activity has been cancelled.
        IN_REVIEW (str): Activity is currently under review.
        LOCKED (str): Activity is locked from modifications.
        TO_REVIEW (str): Activity is ready to be reviewed.
        UPLOAD_COMPLETE (str): Upload process for the activity is complete.
        NEW (str): Newly created activity.
        IN_DESIGN (str): Activity is in the design phase.
        READY_TO_MAKE (str): Activity is ready for manufacturing/creation.
        IN_SYNTHESIS (str): Activity is in the synthesis phase.
        IN_TEST (str): Activity is in the testing phase.
        IN_ANALYSIS (str): Activity is in the analysis phase.
        PARTIALLY_COMPLETE (str): Activity has been partially completed.
        PARKED (str): Activity has been parked for later consideration.
        COMPLETE (str): Activity has been completed.
        FAILED (str): Activity has failed.
        ABANDONED (str): Activity has been abandoned.
        IDEATION (str): Activity is in the ideation phase.
        TWO_D_SELECTION (str): Activity is in 2D selection phase.
        COMPUTATION (str): Activity is in the computation phase.
        COMPOUND_SELECTION (str): Activity is in the compound selection phase.
        SELECTED (str): Activity or compound has been selected.
        QUEUE_FOR_SYNTHESIS (str): Activity is queued for synthesis.
        DATA_REVIEW (str): Activity is in the data review phase.
        DONE (str): Activity is done.

    Example:
        ```python
        from kalbio.activities import ActivityStatusEnum

        status = ActivityStatusEnum.IN_PROGRESS
        print(status.value)
        ```
    """

    REQUESTED = "requested"
    TODO = "to do"
    IN_PROGRESS = "in progress"
    NEEDS_REVIEW = "needs review"
    BLOCKED = "blocked"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    IN_REVIEW = "in review"
    LOCKED = "locked"

    TO_REVIEW = "to review"
    UPLOAD_COMPLETE = "upload complete"

    NEW = "new"
    IN_DESIGN = "in design"
    READY_TO_MAKE = "ready to make"
    IN_SYNTHESIS = "in synthesis"
    IN_TEST = "in test"
    IN_ANALYSIS = "in analysis"
    PARTIALLY_COMPLETE = "partially complete"
    PARKED = "parked"
    COMPLETE = "complete"
    FAILED = "failed"
    ABANDONED = "abandoned"

    IDEATION = "ideation"
    TWO_D_SELECTION = "2D selection"
    COMPUTATION = "computation"
    COMPOUND_SELECTION = "compound selection"
    SELECTED = "selected"
    QUEUE_FOR_SYNTHESIS = "queue for synthesis"
    DATA_REVIEW = "data review"

    DONE = "done"


class CompletedBehaviorEnum(str, Enum):
    """How completed activities are surfaced in `ActivitiesService.search_activities`.

    Attributes:
        SHOW_ALL: Include every matching activity regardless of completion status.
        HIDE_COMPLETED_TREES: Hide activities whose entire ancestor chain is complete.
        HIDE_ALL: Hide every completed activity.
    """

    SHOW_ALL = "show-all"
    HIDE_COMPLETED_TREES = "hide-completed-trees"
    HIDE_ALL = "hide-all"


ActivityType: TypeAlias = Union[
    Literal["task"],
    Literal["experiment"],
    Literal["project"],
    Literal["stage"],
    Literal["milestone"],
    Literal["cycle"],
]
"""Type alias representing the valid types of activities in the system.

This type defines the allowed string values for the `activity_type` field
in Activity and ActivityDefinition models.
"""

ACTIVITY_TYPE_TO_LABEL: dict[ActivityType, str] = {
    "task": "Task",
    "experiment": "Experiment",
    "project": "Project",
    "stage": "Stage",
    "milestone": "Milestone",
    "cycle": "Design cycle",
}
"""Dictionary mapping activity type keys to their human-readable labels.

This mapping is used to convert the internal `activity_type` identifiers
into display-friendly strings for UI and reporting purposes.
"""


class QueueContentLayoutMapping(TypedDict):
    """A view-to-content-layouts mapping used by `set_queuing_behavior`.

    Attributes:
        view_id: UUID of the record view.
        content_layout_ids: UUIDs of the content layouts (placements of
            the view within an activity) that should receive queued
            records for this view.
    """

    view_id: str
    content_layout_ids: List[str]


class ContentLayoutComponentTypeEnum(str, Enum):
    """Component types for items in an activity definition's content layout."""

    NOTE_SECTION = "note_section"
    SHEET = "sheet"
    PLATEMAP = "platemap"
    RESULT_TABLE = "result_table"
    LOOKUP_TABLE = "lookup_table"
    DRC_CHART = "drc_chart"
    REQUESTS = "requests"


class ContentLayoutItem(_KaleidoscopeBaseModel):
    """One component placement within an activity definition's content layout.

    Each item represents a placement of a component (a note section, sheet,
    record view, etc.) within an activity. The `id` is what server-side
    "advanced settings" calls a `content_layout_id`. Exactly one of the
    typed identifier fields (`note_section_id`, `sheet_id`, `platemap_id`,
    `record_view_id`, `drc_config_id`) is populated based on
    `component_type`.

    Attributes:
        id: UUID of this content layout item (the `content_layout_id`).
        component_type: Which kind of component this placement holds.
        position_index: Display order within the activity layout.
        note_section_id: UUID of the note section, if `component_type`
            is `note_section`.
        sheet_id: UUID of the sheet, if `component_type` is `sheet`.
        platemap_id: UUID of the platemap, if `component_type` is `platemap`.
        record_view_id: UUID of the record view, if `component_type` is
            `result_table` or `lookup_table`.
        drc_config_id: UUID of the DRC config, if `component_type` is
            `drc_chart`.
    """

    component_type: Optional[str] = None
    position_index: Optional[int] = None
    note_section_id: Optional[str] = None
    sheet_id: Optional[str] = None
    platemap_id: Optional[str] = None
    record_view_id: Optional[str] = None
    drc_config_id: Optional[str] = None


class Property(_KaleidoscopeBaseModel):
    """Represents a property in the Kaleidoscope system.

    A Property is a data field associated with an entity that contains a value of a specific type.
    It includes metadata about when and by whom it was created/updated, and provides methods
    to update its content.

    Attributes:
        id (str): UUID of the property.
        property_field_id (str): UUID to the property field that defines this
            property's schema.
        content (Any): The actual value/content stored in this property.
        created_at (datetime): Timestamp when the property was created.
        last_updated_by (str): UUID of the user who last updated this property.
        created_by (str): UUID of the user who created this property.
        property_name (str): Human-readable name of the property.
        field_type (DataFieldTypeEnum): The data type of this property's content.

    Example:
        ```python
        from kalbio.activities import Property

        prop = Property(
            id="prop_uuid",
            property_field_id="field_uuid",
            content="In progress",
            created_at=datetime.utcnow(),
            last_updated_by="user_uuid",
            created_by="user_uuid",
            property_name="Status",
            field_type=DataFieldTypeEnum.TEXT,
        )
        print(prop.property_name, prop.content)
        ```
    """

    property_field_id: Optional[str] = None
    content: Optional[Any] = None
    created_at: Optional[datetime] = None
    last_updated_by: Optional[str] = None
    created_by: Optional[str] = None
    property_name: Optional[str] = None
    field_type: Optional[str] = None

    def __str__(self):
        return f"Property({self.property_name}:{self.content})"

    def update_property(self, property_value: Any) -> None:
        """Update the property with a new value.

        Args:
            property_value: The new value to set for the property.

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            prop.update_property("Reviewed")
            ```
        """
        resp = self._client._put("/properties/" + self.id, {"content": property_value})
        if resp:
            for key, value in resp.items():
                if hasattr(self, key):
                    setattr(self, key, value)
        # A property lives on an activity or a definition; the owner's cached
        # copy now holds a stale property value.
        self._client.activities._clear_activity_caches()
        self._client.activities._clear_definition_caches()

    def update_property_file(
        self,
        file_name: str,
        file_data: BinaryIO,
        file_type: str,
    ) -> dict | None:
        """Update a property by uploading a file.

        Args:
            file_name: The name of the file to be updated.
            file_data: The binary data of the file to be updated.
            file_type: The MIME type of the file to be updated.

        Returns:
            A dict of response JSON data (contains reference to the
                uploaded file), or None if the server returned an empty body.

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            with open("report.pdf", "rb") as file_data:
                upload_info = prop.update_property_file(
                    file_name="report.pdf",
                    file_data=file_data,
                    file_type="application/pdf",
                )
            ```
        """
        resp = self._client._post_file(
            "/properties/" + self.id + "/file",
            (file_name, file_data, file_type),
        )
        # The upload mutates the property regardless of the response body, so the
        # owning activity/definition caches are now stale.
        self._client.activities._clear_activity_caches()
        self._client.activities._clear_definition_caches()
        if resp is None or len(resp) == 0:
            return None

        return resp


class ActivityDefinition(_KaleidoscopeBaseModel):
    """Represents the definition of an activity in the Kaleidoscope system.

    An ActivityDefinition contains a template for the metadata about a task or activity,
    including associated programs, users, groups, labels, and properties.

    Attributes:
        id (str): UUID of the Activity Definition.
        program_ids (List[str]): List of program UUIDs associated with this activity.
        title (str): The title of the activity.
        activity_type (ActivityType): The type/category of the activity.
        status (Optional[ActivityStatusEnum]): The current status of the activity.
            Defaults to None if not specified.
        assigned_user_ids (List[str]): List of user IDs assigned to this activity.
        assigned_group_ids (List[str]): List of group IDs assigned to this activity.
        label_ids (List[str]): List of label identifiers associated with this activity.
        properties (List[Property]): List of properties that define additional
            characteristics of the activity.
        external_id (Optional[str]): The id of the activity definition if it was imported from an external source
        registration_property_field_id (Optional[str]): UUID of the file property
            field whose uploads trigger external registration. Only set on
            operation-type definitions (experiment/cycle); None otherwise.
        registration_record_view_id (Optional[str]): UUID of the record view
            (table) whose records are sent for registration.
        registration_content_layout_id (Optional[str]): UUID of the content
            layout corresponding to ``registration_record_view_id``.
        registration_status_field_id (Optional[str]): UUID of the status field
            used to track registration progress.
        registration_result_record_view_id (Optional[str]): UUID of an optional
            results table for registration outputs.
        registration_result_content_layout_id (Optional[str]): UUID of the
            content layout corresponding to ``registration_result_record_view_id``.
        view_ids_to_add_to_when_record_attached (List[str]): UUIDs of record
            views that records are automatically added to when queued by an
            activity of this type.
        queue_content_layout_ids (List[str]): UUIDs of the content layouts
            within the activity that receive queued records.
        content_layout (List[ContentLayoutItem]): Component placements
            (note sections, sheets, record views, etc.) inside this
            definition. Each item's `id` is the `content_layout_id`
            used by `set_queuing_behavior` and `set_registration_settings`.

    Example:
        ```python
        definition = client.activities.get_definition_by_id("definition_uuid")
        if definition:
            print(definition.title, definition.activity_type)
        ```
    """

    program_ids: List[str] = Field(default_factory=list)
    title: Optional[str] = None
    activity_type: Optional[ActivityType] = None
    # The server is the source of truth for statuses, so accept whatever it
    # returns rather than validating against a client enum that drifts.
    # ActivityStatusEnum lists the common values for reference.
    status: Optional[str] = None
    assigned_user_ids: List[str] = Field(default_factory=list)
    assigned_group_ids: List[str] = Field(default_factory=list)
    label_ids: List[str] = Field(default_factory=list)
    properties: List[Property] = Field(default_factory=list)
    external_id: Optional[str] = None

    # Advanced settings — only populated on operation-type definitions
    # (experiment/cycle). Default to None / empty list on others.
    registration_property_field_id: Optional[str] = None
    registration_record_view_id: Optional[str] = None
    registration_content_layout_id: Optional[str] = None
    registration_status_field_id: Optional[str] = None
    registration_result_record_view_id: Optional[str] = None
    registration_result_content_layout_id: Optional[str] = None
    view_ids_to_add_to_when_record_attached: List[str] = []
    queue_content_layout_ids: List[str] = []
    content_layout: List[ContentLayoutItem] = []

    def __str__(self):
        return f"{self.id}:{self.title}"

    def _apply_update(self, body: dict) -> None:
        """PUT a pre-built body to this definition and refresh local state.

        Shared by `update` and the typed `set_*` helpers, which each build
        their own server-shaped body.
        """
        if not body:
            return None
        resp = self._client._put(f"/activity_definitions/{self.id}", body)
        if resp:
            # Validate the response through the model so nested fields
            # (e.g. content_layout) come back as typed objects, not dicts.
            updated = self.__class__._from_api(resp, self._client)
            for field_name in self.__class__.model_fields.keys():
                setattr(self, field_name, getattr(updated, field_name))
        self._client.activities._clear_definition_caches()
        if body.get("propagate_to_instances"):
            # Propagation applies this change to the activity instances created
            # from this definition, so their cached list/lookup snapshots are
            # now stale too.
            self._client.activities._clear_activity_caches()

    def update(
        self,
        *,
        title: Union[str, _UnsetType] = UNSET,
        description: Union[Optional[Any], _UnsetType] = UNSET,
        status: Union[str, ActivityStatusEnum, _UnsetType] = UNSET,
        priority: Union[str, _UnsetType] = UNSET,
        is_archived: Union[bool, _UnsetType] = UNSET,
        external_id: Union[str, _UnsetType] = UNSET,
        duration: Union[Optional[int], _UnsetType] = UNSET,
        aggregate_scheduling: Union[bool, _UnsetType] = UNSET,
        assigned_user_ids: Union[List[str], _UnsetType] = UNSET,
        add_assigned_user_ids: Union[List[str], _UnsetType] = UNSET,
        remove_assigned_user_ids: Union[List[str], _UnsetType] = UNSET,
        add_assigned_group_ids: Union[List[str], _UnsetType] = UNSET,
        remove_assigned_group_ids: Union[List[str], _UnsetType] = UNSET,
        add_label_ids: Union[List[str], _UnsetType] = UNSET,
        remove_label_ids: Union[List[str], _UnsetType] = UNSET,
        add_program_ids: Union[List[str], _UnsetType] = UNSET,
        remove_program_ids: Union[List[str], _UnsetType] = UNSET,
        propagate_to_instances: Union[bool, _UnsetType] = UNSET,
        **kwargs: Any,
    ) -> None:
        """Update this activity definition.

        Only the arguments you pass are sent to the server; omitted arguments
        default to ``UNSET`` and are left unchanged. Pass ``None`` to clear a
        nullable field.

        For registration and record-queuing settings, prefer the typed helpers
        ``set_registration_settings`` and ``set_queuing_behavior``.

        Args:
            title: New title.
            description: Description as rich-text JSON, or None to clear.
            status: Default status for new instances (an ``ActivityStatusEnum``
                value or its string).
            priority: Default priority (urgent/high/medium/low/none).
            is_archived: Archive (True) or unarchive (False) the definition.
            external_id: External identifier.
            duration: Default duration in days, or None to clear.
            aggregate_scheduling: Default aggregate-scheduling behavior.
            assigned_user_ids: Full replacement of the default assigned users.
            add_assigned_user_ids: Default assigned user UUIDs to add.
            remove_assigned_user_ids: Default assigned user UUIDs to remove.
            add_assigned_group_ids: Default assigned group UUIDs to add.
            remove_assigned_group_ids: Default assigned group UUIDs to remove.
            add_label_ids: Default label UUIDs to add.
            remove_label_ids: Default label UUIDs to remove.
            add_program_ids: Program UUIDs to add.
            remove_program_ids: Program UUIDs to remove.
            propagate_to_instances: Whether to apply the change to existing
                activity instances created from this definition.
            **kwargs: Additional request-body fields passed through as-is, for
                advanced settings not surfaced above (e.g. ``is_external``,
                ``inventory_*``, ``data_schema``, ``naming_convention``).

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            defn.update(title="Renamed assay", propagate_to_instances=True)
            defn.update(add_assigned_user_ids=["user_uuid"])
            ```
        """
        candidate = {
            "title": title,
            "description": description,
            "status": status,
            "priority": priority,
            "is_archived": is_archived,
            "external_id": external_id,
            "duration": duration,
            "aggregate_scheduling": aggregate_scheduling,
            "assigned_user_ids": assigned_user_ids,
            "add_assigned_user_ids": add_assigned_user_ids,
            "remove_assigned_user_ids": remove_assigned_user_ids,
            "add_assigned_group_ids": add_assigned_group_ids,
            "remove_assigned_group_ids": remove_assigned_group_ids,
            "add_label_ids": add_label_ids,
            "remove_label_ids": remove_label_ids,
            "add_program_ids": add_program_ids,
            "remove_program_ids": remove_program_ids,
            "propagate_to_instances": propagate_to_instances,
        }
        body = {
            key: value
            for key, value in candidate.items()
            if not isinstance(value, _UnsetType)
        }
        # Merge any extra request-body fields passed via kwargs (e.g. advanced
        # registration/inventory settings); the explicit params above win.
        body = {**kwargs, **body}
        self._apply_update(body)

    def set_registration_settings(
        self,
        *,
        property_field_id: Union[Optional[str], _UnsetType] = UNSET,
        record_view_id: Union[Optional[str], _UnsetType] = UNSET,
        content_layout_id: Union[Optional[str], _UnsetType] = UNSET,
        status_field_id: Union[Optional[str], _UnsetType] = UNSET,
        result_record_view_id: Union[Optional[str], _UnsetType] = UNSET,
        result_content_layout_id: Union[Optional[str], _UnsetType] = UNSET,
    ) -> None:
        """Configure external registration settings on this activity definition.

        Registration sends a ``registration_submitted`` webhook to a
        configured external service when team members register files
        from activities of this type.

        Only the arguments you pass are sent to the server. To clear a
        nullable field, pass ``None`` explicitly. Omitted arguments
        default to ``UNSET`` and are left unchanged.

        Changes take effect immediately for all activities of this type —
        registration settings live on the definition itself and are read
        by instances at runtime.

        Args:
            property_field_id: UUID of the file property field whose
                uploads should trigger registration. Pass None to clear.
            record_view_id: UUID of the record view (table) whose
                records will be sent for registration. Pass None to clear.
            content_layout_id: UUID of the content layout corresponding
                to ``record_view_id``. Pass None to clear.
            status_field_id: UUID of the status field used to track
                registration progress. Pass None to clear.
            result_record_view_id: UUID of an optional results table
                for registration outputs. Pass None to clear.
            result_content_layout_id: UUID of the content layout
                corresponding to ``result_record_view_id``. Pass None to clear.

        Example:
            ```python
            defn = client.activities.get_activity_definition_by_external_id(
                "my-assay-v2"
            )
            defn.set_registration_settings(
                property_field_id="file-field-uuid",
                record_view_id="view-uuid",
                content_layout_id="layout-uuid",
                status_field_id="status-uuid",
            )
            ```
        """
        body: dict = {}
        if not isinstance(property_field_id, _UnsetType):
            body["registration_property_field_id"] = property_field_id
        if not isinstance(record_view_id, _UnsetType):
            body["registration_record_view_id"] = record_view_id
        if not isinstance(content_layout_id, _UnsetType):
            body["registration_content_layout_id"] = content_layout_id
        if not isinstance(status_field_id, _UnsetType):
            body["registration_status_field_id"] = status_field_id
        if not isinstance(result_record_view_id, _UnsetType):
            body["registration_result_record_view_id"] = result_record_view_id
        if not isinstance(result_content_layout_id, _UnsetType):
            body["registration_result_content_layout_id"] = result_content_layout_id

        if not body:
            return None

        self._apply_update(body)

    def set_queuing_behavior(
        self,
        *,
        add_view_ids: Union[List[str], _UnsetType] = UNSET,
        remove_view_ids: Union[List[str], _UnsetType] = UNSET,
        queue_content_layout_ids: Union[
            List[QueueContentLayoutMapping], _UnsetType
        ] = UNSET,
    ) -> None:
        """Configure queuing behavior on this activity definition.

        Controls which tables records are automatically added to when
        they are queued by an activity of this type.

        Only the arguments you pass are sent to the server. Omitted
        arguments default to ``UNSET`` and are left unchanged.

        Changes take effect immediately for all activities of this type.

        Args:
            add_view_ids: Record view UUIDs to start adding records to
                when records are attached to activities of this type.
            remove_view_ids: Record view UUIDs to stop adding records to.
            queue_content_layout_ids: For each view, the content layouts
                within the activity that should receive queued records.
                Each entry is a dict of the form
                ``{"view_id": str, "content_layout_ids": List[str]}``.
                Passing this replaces the existing mapping wholesale.

        Example:
            ```python
            defn.set_queuing_behavior(
                add_view_ids=["view-uuid-1"],
                queue_content_layout_ids=[
                    {
                        "view_id": "view-uuid-1",
                        "content_layout_ids": ["layout-uuid"],
                    }
                ],
            )
            ```
        """
        body: dict = {}
        if not isinstance(add_view_ids, _UnsetType):
            body["add_view_ids_to_add_to_when_record_attached"] = add_view_ids
        if not isinstance(remove_view_ids, _UnsetType):
            body["remove_view_ids_to_add_to_when_record_attached"] = remove_view_ids
        if not isinstance(queue_content_layout_ids, _UnsetType):
            body["set_queue_content_layout_ids"] = queue_content_layout_ids

        if not body:
            return None

        self._apply_update(body)

    def content_layout_ids_for_view(self, view_id: str) -> List[str]:
        """Find content_layout item UUIDs that map to a given record view.

        Use this to discover the `content_layout_ids` needed by
        `set_queuing_behavior` and `set_registration_settings`.

        Args:
            view_id: UUID of the record view to look up.

        Returns:
            UUIDs of content layout items in this definition whose
            ``record_view_id`` matches ``view_id``. Empty if no items match.

        Example:
            ```python
            layout_ids = defn.content_layout_ids_for_view(view.id)
            defn.set_queuing_behavior(
                queue_content_layout_ids=[
                    {"view_id": view.id, "content_layout_ids": layout_ids}
                ],
            )
            ```
        """
        return [
            item.id for item in self.content_layout if item.record_view_id == view_id
        ]

    @property
    def record_views(self) -> List[RecordView]:
        """Regular record views attached to activities of this definition.

        Returns the live record views (tables) whose
        ``operation_definition_ids`` contain this definition's id. Use
        this to discover view UUIDs for advanced settings without needing
        an existing activity instance.

        Templates linked to this definition are NOT included — use
        `templates` instead.

        Returns:
            List of regular RecordView objects associated with this
            definition. Empty if no views are attached.

        Example:
            ```python
            for view in defn.record_views:
                print(view.id, view.view_name)
            ```
        """
        all_views = self._client.record_views.get_record_views()
        return [
            view
            for view in all_views
            if view.operation_definition_ids
            and self.id in view.operation_definition_ids
        ]

    @property
    def templates(self) -> List["ResultTableTemplate"]:
        """Result table templates linked to this activity definition.

        Returns templates whose ``operation_definition_ids`` contain this
        definition's id.

        Returns:
            List of ResultTableTemplate objects linked to this definition.
            Empty if none are linked.

        Example:
            ```python
            for template in defn.templates:
                print(template.id, template.template_name or template.view_name)
            ```
        """
        all_templates = self._client.result_table_templates.get_templates()
        return [
            t
            for t in all_templates
            if t.operation_definition_ids and self.id in t.operation_definition_ids
        ]

    def _resolve_placement(
        self, target: Union[RecordView, ContentLayoutItem]
    ) -> tuple[str, str]:
        """Resolve a RecordView or ContentLayoutItem to (view_id, content_layout_id).

        - RecordView: auto-derive the layout from `self.content_layout`. Raises
          ValueError if the view has zero or multiple placements.
        - ContentLayoutItem: use it directly. Raises ValueError if it has no
          `record_view_id` (e.g. it's a note section).
        """
        if isinstance(target, ContentLayoutItem):
            if target.record_view_id is None:
                raise ValueError(
                    f"ContentLayoutItem {target.id} has component_type="
                    f"{target.component_type} and no record_view_id — only "
                    f"result_table/lookup_table placements can be used here."
                )
            return target.record_view_id, target.id

        layout_ids = self.content_layout_ids_for_view(target.id)
        if len(layout_ids) == 0:
            raise ValueError(
                f"View {target.id} has no placement in this definition's "
                f"content_layout."
            )
        if len(layout_ids) > 1:
            raise ValueError(
                f"View {target.id} has {len(layout_ids)} placements in this "
                f"definition (content_layout_ids: {layout_ids}). Pass a "
                f"specific ContentLayoutItem from defn.content_layout, or use "
                f"set_queuing_behavior() / set_registration_settings() directly."
            )
        return target.id, layout_ids[0]

    def queue_to_views(
        self,
        views: List[Union[RecordView, ContentLayoutItem]],
    ) -> None:
        """Auto-add records to these views when queued by activities of this type.

        Sugar layer over `set_queuing_behavior`. For each entry, derives
        the underlying `content_layout_id` from this definition's
        `content_layout`.

        Changes take effect immediately for all activities of this type.

        Args:
            views: Views to queue records into. Each entry can be either:

                * A ``RecordView`` — auto-derives its placement in this
                  definition. Raises ``ValueError`` if the view has zero or
                  multiple placements.
                * A ``ContentLayoutItem`` — targets that specific placement.
                  Use this for views that are placed more than once.

        Example:
            ```python
            # Common case: just pass views
            defn.queue_to_views([results_view, qc_view])

            # Multi-placement case: pick the specific placement
            top_placement = next(
                item for item in defn.content_layout
                if item.record_view_id == results_view.id
                and item.position_index == 0
            )
            defn.queue_to_views([top_placement])
            ```
        """
        layouts_by_view: Dict[str, List[str]] = {}
        for target in views:
            view_id, layout_id = self._resolve_placement(target)
            layouts_by_view.setdefault(view_id, []).append(layout_id)

        self.set_queuing_behavior(
            add_view_ids=list(layouts_by_view.keys()),
            queue_content_layout_ids=[
                {"view_id": vid, "content_layout_ids": lids}
                for vid, lids in layouts_by_view.items()
            ],
        )

    def configure_registration(
        self,
        *,
        view: Union[RecordView, ContentLayoutItem],
        file_property_field: Union[Property, str],
        status_field: Union[DataField, str, None, _UnsetType] = UNSET,
        result_view: Union[RecordView, ContentLayoutItem, None, _UnsetType] = UNSET,
    ) -> None:
        """Configure external registration on this activity definition.

        Sugar layer over `set_registration_settings`. Derives
        `content_layout_id` (and `result_content_layout_id`) from the
        passed view(s).

        Changes take effect immediately for all activities of this type.

        Args:
            view: The record view whose records are sent for registration.
                Either a ``RecordView`` (auto-derives layout) or a
                ``ContentLayoutItem`` (specific placement). Required.
            file_property_field: The file property field whose uploads
                trigger registration. Either a ``Property`` (uses its
                ``property_field_id``) or a property-field UUID string.
                Required.
            status_field: Optional status field used to track registration
                progress. Pass a ``DataField``, a UUID string, ``None`` to
                clear, or leave unset to keep the current value.
            result_view: Optional results table for registration outputs.
                Same view/placement semantics as ``view``. Pass ``None`` to
                clear, or leave unset to keep the current value.

        Example:
            ```python
            defn.configure_registration(
                view=results_view,
                file_property_field=file_property,
                status_field=status_data_field,
            )
            ```
        """
        view_id, content_layout_id = self._resolve_placement(view)

        pf_id = (
            file_property_field.property_field_id
            if isinstance(file_property_field, Property)
            else file_property_field
        )

        body_kwargs: dict = {
            "property_field_id": pf_id,
            "record_view_id": view_id,
            "content_layout_id": content_layout_id,
        }

        if not isinstance(status_field, _UnsetType):
            if status_field is None or isinstance(status_field, str):
                body_kwargs["status_field_id"] = status_field
            else:
                body_kwargs["status_field_id"] = status_field.id

        if not isinstance(result_view, _UnsetType):
            if result_view is None:
                body_kwargs["result_record_view_id"] = None
                body_kwargs["result_content_layout_id"] = None
            else:
                r_view_id, r_layout_id = self._resolve_placement(result_view)
                body_kwargs["result_record_view_id"] = r_view_id
                body_kwargs["result_content_layout_id"] = r_layout_id

        self.set_registration_settings(**body_kwargs)

    @cached_model_property
    def activities(self) -> List[Activity]:
        """Get the activities for this activity definition.

        Returns:
            The activities associated with this
                activity definition.

        Note:
            This is a cached property.

        Example:
            ```python
            definition = client.activities.get_definition_by_id("definition_uuid")
            related = definition.activities if definition else []
            ```
        """
        return [
            a
            for a in self._client.activities.get_activities()
            if a.definition_id == self.id
        ]


class Comment(_KaleidoscopeBaseModel):
    """A user comment on a Kaleidoscope resource (e.g. an activity).

    Attributes:
        id: UUID of the comment.
        workspace_id: UUID of the workspace this comment belongs to.
        created_by: UUID of the user who authored the comment.
        content: Tiptap-compatible rich-text JSON document for the comment body.
        parent_comment_id: UUID of the parent comment if this is a reply, else None.
        mentioned_user_ids: UUIDs of users @-mentioned in the comment, if any.
        resource_type: Type of the resource the comment is attached to (e.g. "task").
        resource_id: UUID of the resource the comment is attached to.
        created_at: Timestamp the comment was created.
        updated_at: Timestamp the comment was last updated.
    """

    workspace_id: Optional[str] = None
    created_by: Optional[str] = None
    content: Optional[Any] = None
    parent_comment_id: Optional[str] = None
    mentioned_user_ids: Optional[List[str]] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ActivityEvent(_KaleidoscopeBaseModel):
    """An entry in the audit/event log for an activity.

    Returned by `Activity.get_events`. Each event captures one user
    action or system-generated change to the activity (status change,
    assignment, record attachment, etc.).

    Attributes:
        id: UUID of the event.
        event_type: String identifier of the event type.
        event_type_version: Version number of the event type schema.
        event_attrs: Event-specific attributes (shape varies by event_type).
        event_user_id: UUID of the user that triggered the event.
        created_at: Timestamp the event was recorded.
        resource_id: UUID of the resource the event applies to.
        resource_type: Type of the resource (e.g. "task").
        workspace_id: UUID of the workspace.
        parent_bulk_event_id: UUID of the parent bulk event if this event
            was part of a bulk operation.
        is_bulk: Whether this event was part of a bulk operation.
        request_id: Request identifier the event was emitted under, if any.
        session_id: Session identifier the event was emitted under, if any.
        log: Human-readable summary of the event, if available.
    """

    event_type: Optional[str] = None
    event_type_version: Optional[int] = None
    event_attrs: dict = Field(default_factory=dict)
    event_user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None
    workspace_id: Optional[str] = None
    parent_bulk_event_id: Optional[str] = None
    is_bulk: Optional[bool] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    log: Optional[str] = None


class Activity(_KaleidoscopeBaseModel):
    """Represents an activity (e.g. task or experiment) within the Kaleidoscope system.

    An Activity is a unit of work that can be assigned to users or groups, have dependencies,
    and contain associated records and properties. Activities can be organized hierarchically
    with parent-child relationships and linked to programs.

    Attributes:
        id (str): Unique identifier for the model instance.
        created_at (datetime): The timestamp when the activity was created.
        parent_id (Optional[str]): The ID of the parent activity, if this is a child activity.
        child_ids (List[str]): List of child activity IDs.
        definition_id (Optional[str]): The ID of the activity definition template.
        program_ids (List[str]): List of program IDs this activity belongs to.
        activity_type (ActivityType): The type/category of the activity.
        title (str): The title of the activity.
        description (Any): Detailed description of the activity.
        status (ActivityStatusEnum): Current status of the activity.
        assigned_user_ids (List[str]): List of user IDs assigned to this activity.
        assigned_group_ids (List[str]): List of group IDs assigned to this activity.
        due_date (Optional[datetime]): The deadline for completing the activity.
        start_date (Optional[datetime]): The scheduled start date for the activity.
        duration (Optional[int]): Expected duration of the activity.
        completed_at_date (Optional[datetime]): The timestamp when the activity was completed.
        dependencies (List[str]): List of activity IDs that this activity depends on.
        label_ids (List[str]): List of label IDs associated with this activity.
        is_draft (bool): Whether the activity is in draft status.
        properties (List[Property]): List of custom properties associated with the activity.
        external_id (Optional[str]): The id of the activity if it was imported from an external source
        all_record_ids (List[str]): All record IDs associated with the activity across operations.
        data_table_record_mapping (Dict[str, List[str]]): Per-view record ordering for this operation,
            keyed by record view id. The authoritative source for "which records are on this view".

    Example:
        ```python
        activity = client.activities.get_activity_by_id("activity_uuid")
        if activity:
            print(activity.title, activity.status)
            first_record = activity.records[0] if activity.records else None
        ```
    """

    created_at: Optional[datetime] = None
    parent_id: Optional[str] = None
    child_ids: List[str] = Field(default_factory=list)
    definition_id: Optional[str] = None
    program_ids: List[str] = Field(default_factory=list)
    activity_type: Optional[ActivityType] = None
    title: Optional[str] = None
    description: Optional[Any] = None
    # The server is the source of truth for statuses, so accept whatever it
    # returns rather than validating against a client enum that drifts.
    # ActivityStatusEnum lists the common values for reference.
    status: Optional[str] = None
    assigned_user_ids: List[str] = Field(default_factory=list)
    assigned_group_ids: List[str] = Field(default_factory=list)
    subscriber_ids: List[str] = Field(default_factory=list)
    due_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    duration: Optional[int] = None
    completed_at_date: Optional[datetime] = None
    dependencies: List[str] = Field(default_factory=list)
    label_ids: List[str] = Field(default_factory=list)
    is_draft: Optional[bool] = None
    properties: List[Property] = Field(default_factory=list)
    external_id: Optional[str] = None

    # operation fields
    all_record_ids: List[str] = Field(default_factory=list)
    data_table_record_mapping: Dict[str, List[str]] = {}

    def __str__(self):
        return f'Activity("{self.title}")'

    @cached_model_property
    def activity_definition(self) -> ActivityDefinition | None:
        """Get the activity definition for this activity.

        Returns:
            The activity definition associated with this
                activity. If the activity has no definition, returns None.

        Note:
            This is a cached property.

        Example:
            ```python
            definition = activity.activity_definition
            print(definition.title if definition else "No template")
            ```
        """
        if self.definition_id:
            return self._client.activities.get_definition_by_id(self.definition_id)
        else:
            return None

    @cached_model_property
    def assigned_users(self) -> List[WorkspaceUser]:
        """Get the assigned users for this activity.

        Returns:
            The users assigned to this activity.

        Note:
            This is a cached property.
        """
        return self._client.workspace.get_members_by_ids(self.assigned_user_ids)

    @cached_model_property
    def assigned_groups(self) -> List[WorkspaceGroup]:
        """Get the assigned groups for this activity.

        Returns:
            The groups assigned to this activity.

        Note:
            This is a cached property.
        """
        return self._client.workspace.get_groups_by_ids(self.assigned_group_ids)

    @cached_model_property
    def labels(self) -> List[Label]:
        """Get the labels for this activity.

        Returns:
            The labels associated with this activity.

        Note:
            This is a cached property.

        Example:
            ```python
            label_names = [label.name for label in activity.labels]
            ```
        """
        return self._client.labels.get_labels_by_ids(self.label_ids)

    @cached_model_property
    def programs(self) -> List[Program]:
        """Retrieve the programs associated with this activity.

        Returns:
            A list of Program instances fetched by their IDs.

        Note:
            This is a cached property.

        Example:
            ```python
            program_titles = [program.title for program in activity.programs]
            ```
        """
        return self._client.programs.get_programs_by_ids(self.program_ids)

    @cached_model_property
    def child_activities(self) -> List[Activity]:
        """Retrieve the child activities associated with this activity.

        Returns:
            A list of Activity objects representing the child activities.

        Note:
            This is a cached property.
        """
        resp = self._client._get("/activities/" + self.id + "/activities")
        if resp is None:
            return []
        return self._client.activities._create_activity_list(resp)

    @property
    def records(self) -> List["Record"]:
        """Retrieve the records associated with this activity.

        Returns:
            A list of Record objects corresponding to the activity.

        Note:
            Each access performs a live GET against the server; the result is
            not cached.
        """
        resp = self._client._get("/operations/" + self.id + "/records")
        if resp is None:
            return []
        return [rec for rec in self._client.records._create_record_list(resp) if rec]

    @property
    def record_views(self) -> List[RecordView]:
        """Regular record views attached to this operation.

        Returns the live record views (tables) associated with this operation —
        i.e. the views you can target when writing values via
        `Record.add_value(record_view_id=...)` or importing via
        `client.imports.push_data(operation_id=..., record_view_id=...)`.

        Templates linked to this activity's definition are NOT included —
        access them via ``activity.activity_definition.templates``.

        Returns:
            List of regular RecordView objects whose `operation_ids` contains
            this activity's id. Returns an empty list if this activity is not
            an operation or has no attached views.

        Example:
            ```python
            for view in activity.record_views:
                print(view.id, view.view_name)
            ```
        """
        all_views = self._client.record_views.get_record_views()
        return [
            view
            for view in all_views
            if view.operation_ids and self.id in view.operation_ids
        ]

    def records_on_view(self, view_id: str) -> List["Record"]:
        """Records currently on a specific view of this operation.

        Reads `data_table_record_mapping[view_id]`.
        Records that fail to resolve are dropped.

        Args:
            view_id: The UUID of the record view.

        Returns:
            Records on the view, in the order the server stores them.

        Example:
            ```python
            for record in activity.records_on_view(view.id):
                print(record.record_identifier)
            ```
        """
        record_ids = self.data_table_record_mapping.get(view_id, [])
        if not record_ids:
            return []
        return [r for r in self._client.records.get_records_by_ids(record_ids) if r]

    def get_record(self, identifier: RecordIdentifier) -> Record | None:
        """Retrieves the record with the given identifier if it is in the operation.

        Args:
            identifier: An identifier for a Record.

                This method will accept and resolve any type of RecordIdentifier.

        Returns:
            The record if it is in the operation, otherwise None

        Example:
            ```python
            record = activity.get_record("record_uuid")
            ```
        """
        idx = self._client.records._resolve_to_record_id(identifier)

        if idx is None:
            return None

        return next(
            (r for r in self.records if r.id == idx),
            None,
        )

    def has_record(self, identifier: RecordIdentifier) -> bool:
        """Retrieve whether a record with the given identifier is in the operation

        Args:
            identifier: An identifier for a Record.

                This method will accept and resolve any type of RecordIdentifier.

        Returns:
            Whether the record is in the operation

        Example:
            ```python
            has_link = activity.has_record("record_uuid")
            ```
        """
        return self.get_record(identifier) is not None

    def update(
        self,
        *,
        parent_id: Union[Optional[str], _UnsetType] = UNSET,
        title: Union[str, _UnsetType] = UNSET,
        description: Union[Optional[Any], _UnsetType] = UNSET,
        status: Union[str, ActivityStatusEnum, _UnsetType] = UNSET,
        priority: Union[str, _UnsetType] = UNSET,
        definition_id: Union[str, _UnsetType] = UNSET,
        add_dependencies: Union[List[str], _UnsetType] = UNSET,
        remove_dependencies: Union[List[str], _UnsetType] = UNSET,
        due_date: Union[Optional[datetime], _UnsetType] = UNSET,
        start_date: Union[Optional[datetime], _UnsetType] = UNSET,
        duration: Union[Optional[int], _UnsetType] = UNSET,
        aggregate_scheduling: Union[bool, _UnsetType] = UNSET,
        add_label_ids: Union[List[str], _UnsetType] = UNSET,
        remove_label_ids: Union[List[str], _UnsetType] = UNSET,
        add_program_ids: Union[List[str], _UnsetType] = UNSET,
        remove_program_ids: Union[List[str], _UnsetType] = UNSET,
        add_assigned_user_ids: Union[List[str], _UnsetType] = UNSET,
        remove_assigned_user_ids: Union[List[str], _UnsetType] = UNSET,
        add_assigned_group_ids: Union[List[str], _UnsetType] = UNSET,
        remove_assigned_group_ids: Union[List[str], _UnsetType] = UNSET,
        add_reviewer_ids: Union[List[str], _UnsetType] = UNSET,
        remove_reviewer_ids: Union[List[str], _UnsetType] = UNSET,
        add_subscriber_ids: Union[List[str], _UnsetType] = UNSET,
        remove_subscriber_ids: Union[List[str], _UnsetType] = UNSET,
        external_id: Union[str, _UnsetType] = UNSET,
        comment: Union[Any, _UnsetType] = UNSET,
        shift_dependency_mode: Union[str, _UnsetType] = UNSET,
        avoid_weekends: Union[bool, _UnsetType] = UNSET,
        extend_in_progress_items: Union[bool, _UnsetType] = UNSET,
        **kwargs: Any,
    ) -> None:
        """Update this activity.

        Only the arguments you pass are sent to the server; omitted arguments
        default to ``UNSET`` and are left unchanged. Pass ``None`` to clear a
        nullable field (e.g. ``due_date=None``).

        Args:
            parent_id: UUID of the parent activity, or None to detach.
            title: New title.
            description: Description as rich-text JSON, or None to clear.
            status: New status (an ``ActivityStatusEnum`` value or its string).
            priority: New priority (urgent/high/medium/low/none).
            definition_id: UUID of the activity definition to associate.
            add_dependencies: Activity UUIDs to add as blocking dependencies.
            remove_dependencies: Activity UUIDs to remove as dependencies.
            due_date: Due date (``datetime``), or None to clear.
            start_date: Start date (``datetime``), or None to clear.
            duration: Duration in days, or None to clear.
            aggregate_scheduling: Whether to roll up child scheduling.
            add_label_ids: Label UUIDs to add.
            remove_label_ids: Label UUIDs to remove.
            add_program_ids: Program UUIDs to add.
            remove_program_ids: Program UUIDs to remove.
            add_assigned_user_ids: User UUIDs to assign.
            remove_assigned_user_ids: User UUIDs to unassign.
            add_assigned_group_ids: Group UUIDs to assign.
            remove_assigned_group_ids: Group UUIDs to unassign.
            add_reviewer_ids: User UUIDs to add as reviewers.
            remove_reviewer_ids: User UUIDs to remove as reviewers.
            add_subscriber_ids: User UUIDs to subscribe to notifications. Must be
                workspace members; subscribing anyone other than yourself
                requires the workspace ``update.tasks.other_subscribers``
                permission.
            remove_subscriber_ids: User UUIDs to unsubscribe.
            external_id: External identifier.
            comment: A comment to post with the update, as rich-text JSON.
            shift_dependency_mode: How dependent activities shift when dates change.
            avoid_weekends: Whether date shifts skip weekends.
            extend_in_progress_items: Whether in-progress items extend on shift.
            **kwargs: Additional request-body fields passed through as-is, for
                any server field not surfaced as an explicit parameter above.

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            activity.update(status=ActivityStatusEnum.IN_PROGRESS)
            activity.update(add_assigned_user_ids=["user_uuid"])
            activity.update(add_subscriber_ids=["user_uuid"])
            ```
        """
        candidate = {
            "parent_id": parent_id,
            "title": title,
            "description": description,
            "status": status,
            "priority": priority,
            "definition_id": definition_id,
            "add_dependencies": add_dependencies,
            "remove_dependencies": remove_dependencies,
            "due_date": due_date,
            "start_date": start_date,
            "duration": duration,
            "aggregate_scheduling": aggregate_scheduling,
            "add_label_ids": add_label_ids,
            "remove_label_ids": remove_label_ids,
            "add_program_ids": add_program_ids,
            "remove_program_ids": remove_program_ids,
            "add_assigned_user_ids": add_assigned_user_ids,
            "remove_assigned_user_ids": remove_assigned_user_ids,
            "add_assigned_group_ids": add_assigned_group_ids,
            "remove_assigned_group_ids": remove_assigned_group_ids,
            "add_reviewer_ids": add_reviewer_ids,
            "remove_reviewer_ids": remove_reviewer_ids,
            "add_subscriber_ids": add_subscriber_ids,
            "remove_subscriber_ids": remove_subscriber_ids,
            "external_id": external_id,
            "comment": comment,
            "shift_dependency_mode": shift_dependency_mode,
            "avoid_weekends": avoid_weekends,
            "extend_in_progress_items": extend_in_progress_items,
        }
        body = {
            key: value
            for key, value in candidate.items()
            if not isinstance(value, _UnsetType)
        }
        # Merge any extra request-body fields passed via kwargs; the explicit
        # params above win on conflict.
        body = {**kwargs, **body}
        # Serialize date values (e.g. due_date/start_date) to ISO strings.
        body = {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in body.items()
        }
        if not body:
            return None
        resp = self._client._put("/activities/" + self.id, body)
        if resp:
            # Validate the response through the model so nested fields
            # (e.g. properties) come back as typed, client-hydrated objects.
            updated = self.__class__._from_api(resp, self._client)
            for field_name in self.__class__.model_fields.keys():
                setattr(self, field_name, getattr(updated, field_name))
        # Cached relations (programs, assigned users, etc.) can reflect fields
        # that just changed.
        self.clear_caches()
        # The cached activity list/maps still hold this activity's prior state.
        self._client.activities._clear_activity_caches()

    def add_records(self, record_ids: List[str]) -> None:
        """Add a list of record IDs to the activity.

        Args:
            record_ids: A list of record IDs to be added to the activity.

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            activity.add_records(["record_uuid_1", "record_uuid_2"])
            ```
        """
        self._client._put(
            "/operations/" + self.id + "/records", {"record_ids": record_ids}
        )
        # Refresh this operation's record membership (data_table_record_mapping)
        # and drop the now-stale activity and record→activities caches.
        self.refetch()

    def get_record_data(self) -> List[dict]:
        """Retrieve data from all this activity's associated records.

        Returns:
            A list containing the activity data for each record,
                obtained by calling get_activity_data with the current activity's UUID.

        Example:
            ```python
            data = activity.get_record_data()
            ```
        """
        data = []
        for record in self.records:
            data.append(record.get_activity_data(self.id))
        return data

    def get_events(self) -> List[ActivityEvent]:
        """Retrieve the audit/event log entries for this activity.

        Returns:
            A list of ActivityEvent records for this activity, in the order
            the server provides them (typically newest first).

        Example:
            ```python
            for event in activity.get_events():
                print(event.event_type, event.created_at, event.log)
            ```
        """
        resp = self._client._get(f"/activities/{self.id}/events")
        if resp is None:
            return []
        return [ActivityEvent.model_validate(e) for e in resp]

    def get_comments(self) -> List[Comment]:
        """Retrieve comments posted on this activity.

        Returns:
            A list of Comment objects attached to this activity.

        Example:
            ```python
            for comment in activity.get_comments():
                print(comment.created_by, comment.content)
            ```
        """
        resp = self._client._get(f"/activities/{self.id}/comments")
        if resp is None:
            return []
        comments = [Comment.model_validate(c) for c in resp]
        for c in comments:
            c._set_client(self._client)
        return comments

    def refetch(self):
        """Refreshes all the data of the current activity instance.

        The activity is also removed from all local caches of its associated client.

        Automatically called by mutating methods of this activity, but can also be called manually.

        Example:
            ```python
            activity.refetch()
            up_to_date_records = activity.records
            ```
        """
        self._client.activities._clear_activity_caches()

        new = self._client.activities.get_activity_by_id(self.id)

        if new is None:
            _logger.error(f"Unable to refresh Activity({self.id})")
            return None

        for k, v in new.__dict__.items():
            setattr(self, k, v)
        # Drop cached relations (programs, assigned users, child activities) so
        # they refetch against the refreshed field values.
        self.clear_caches()


ActivityIdentifier: TypeAlias = Union[Activity, str]
"""Identifier class for Activity

Activities are able to be identified by:

* an object instance of an Activity
* title
* UUID
"""

DefinitionIdentifier: TypeAlias = Union[ActivityDefinition, str]
"""Identifier class for ActivityDefinition

ActivityDefinitions are able to be identified by:

* an object instance of an ActivityDefinition
* title
* UUID
"""


class ActivitiesService(_BaseService):
    """Service class for managing activities in the Kaleidoscope platform.

    This service provides methods to create, retrieve, and manage activities
    (tasks/experiments) and their definitions within a Kaleidoscope workspace.
    It handles activity lifecycle operations including creation, retrieval by
    ID or associated records, and batch operations.

    Note:
        Some methods use LRU caching to improve performance. Cache is cleared on errors.
    """

    #########################
    #    Public  Methods    #
    #########################

    ##### for Activities #####

    @cached
    def get_activities(self) -> List[Activity]:
        """Retrieve all activities in the workspace, including experiments.

        Returns:
            A list of Activity objects representing the activities
                in the workspace.

        Note:
            This method caches its results.

        Raises:
            KalbioAPIError: If the API request fails.
            KalbioResponseError: If the endpoint returns no usable body.

        Example:
            ```python
            activities = client.activities.get_activities()
            ```
        """
        resp = _require_response_body(
            "GET", "/activities", self._client._get("/activities")
        )
        return self._create_activity_list(resp)

    def get_activity_by_type(self, activity_type: ActivityType) -> List[Activity]:
        """Retrieve all activities of a certain type in the workspace.

        Args:
            activity_type: The type of `Activity` to retrieve.

        Returns:
            A list of Activity objects with the type of `activity_type`

        Example:
            ```python
            experiments = client.activities.get_activity_by_type("experiment")
            tasks = client.activities.get_activity_by_type("task")
            ```
        """

        return [
            act for act in self.get_activities() if act.activity_type == activity_type
        ]

    def get_activity_by_id(self, activity_id: ActivityIdentifier) -> Activity | None:
        """Retrieve an activity by its identifier.

        Args:
            activity_id: An identifier of the activity to retrieve.

                This method will accept and resolve any type of ActivityIdentifier.

        Returns:
            The Activity object if found, otherwise None.

        Example:
            ```python
            activity = client.activities.get_activity_by_id("activity_uuid")
            ```
        """
        id_to_activity = self._get_activity_id_map()
        identifier = self._resolve_activity_id(activity_id)

        if identifier is None:
            return None

        return id_to_activity.get(identifier, None)

    def get_activities_by_ids(self, ids: List[ActivityIdentifier]) -> List[Activity]:
        """Fetch multiple activities by their identifiers.

        Args:
            ids: A list of activity identifier strings to fetch.

                This method will accept and resolve any type of ActivityIdentifier inside the `ids`.

        Returns:
            A list of Activity objects corresponding to the provided IDs.

        Note:
            ids that are invalid and return None are not included in the returned list of Activities

        Example:
            ```python
            selected = client.activities.get_activities_by_ids([
                "activity_uuid_1",
                "activity_uuid_2",
            ])
            ```
        """
        activities = []

        for activity_id in ids:
            res = self.get_activity_by_id(activity_id)
            if res:
                activities.append(res)

        return activities

    def get_activity_by_external_id(self, external_id: str) -> Activity | None:
        """Retrieve an activity by its external identifier.

        Args:
            external_id: The external identifier of the activity to retrieve.

        Returns:
            The Activity object if found, otherwise None.

        Example:
            ```python
            ext_activity = client.activities.get_activity_by_external_id("jira-123")
            ```
        """
        activities = self.get_activities()
        return next(
            (a for a in activities if a.external_id == external_id),
            None,
        )

    def create_activity(
        self,
        title: str,
        activity_type: ActivityType,
        program_ids: Optional[list[str]] = None,
        activity_definition_id: Optional[DefinitionIdentifier] = None,
        assigned_user_ids: Optional[List[str]] = None,
        subscriber_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        duration: Optional[int] = None,
    ) -> Activity:
        """Create a new activity.

        Args:
            title: The title/name of the activity.
            activity_type: The type of activity (e.g. task, experiment, etc.).
            program_ids: List of program IDs to associate with
                the activity. Defaults to None.
            activity_definition_id: Identifier for an activity definition to create the activity with.
                Defaults to None.

                The identifier will resolve any type of DefinitionIdentifier.
            assigned_user_ids: List of user IDs to assign to
                the activity. Defaults to None.
            subscriber_ids: List of user IDs to subscribe to the activity's
                notifications, in addition to the assignees and creator who are
                subscribed automatically. Must be workspace members. Defaults to None.
            start_date: Start date for the activity. Defaults to None.
            duration: Duration in days for the activity. Defaults to None.

        Returns:
            The newly created activity instance.

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            new_activity = client.activities.create_activity(
                title="Synthesis",
                activity_type="experiment",
                program_ids=["program_uuid"],
            )
            ```
        """
        definition_id = self._resolve_definition_id(activity_definition_id)
        if activity_definition_id is not None and definition_id is None:
            # A provided-but-unresolvable identifier would otherwise silently
            # create a definition-less activity.
            raise ValueError(
                f"Could not resolve activity_definition_id: {activity_definition_id!r}"
            )
        payload = {
            "title": title,
            "activity_type": activity_type,
            "definition_id": definition_id,
            "program_ids": program_ids if program_ids else [],
            "assigned_user_ids": assigned_user_ids if assigned_user_ids else [],
            "subscriber_ids": subscriber_ids if subscriber_ids else [],
            "start_date": start_date.isoformat() if start_date else None,
            "duration": duration,
        }
        resp = _require_response_body(
            "POST", "/activities", self._client._post("/activities", payload)
        )
        if not resp:
            # The endpoint returns the created activity as a single-element list;
            # anything else can't be turned into an Activity.
            raise KalbioResponseError("POST", "/activities", resp)
        # Clear after the write: clearing first lets a concurrent read
        # repopulate the cache with the pre-create snapshot.
        self._clear_activity_caches()
        # Creating an operation server-side also creates its record views, so the
        # cached record-view list no longer reflects the workspace.
        self._client.record_views._clear_record_view_caches()
        return self._create_activity(resp[0])

    def get_activities_with_record(
        self, record_id: RecordIdentifier, use_cache: bool = True
    ) -> List[Activity]:
        """Retrieve all activities that contain a specific record.

        Args:
            record_id: Identifier for the record.

                Any type of RecordIdentifier will be accepted.
            use_cache: When False, skip the cache and fetch from the server,
                refreshing the cached value.

        Returns:
            Activities that include the specified record.

        Example:
            ```python
            activities = client.activities.get_activities_with_record("record_uuid")
            ```
        """
        record_uuid = self._client.records._resolve_to_record_id(record_id)
        if record_uuid is None:
            return []
        return self._get_activities_with_record(record_uuid, use_cache=use_cache)

    @cached(ttl=10, maxsize=128)
    def _get_activities_with_record(self, record_uuid: str) -> List[Activity]:
        # Keyed on the resolved UUID: a RecordIdentifier may be an unhashable
        # dict, which the cache key builder cannot hash.
        resp = self._client._get("/records/" + record_uuid + "/operations")
        if resp is None:
            return []
        return self._create_activity_list(resp)

    # records.py clears this cache through the public name; keep cache_clear
    # reachable via the bound method's underlying function.
    get_activities_with_record.cache_clear = _get_activities_with_record.cache_clear  # type: ignore[attr-defined]

    def search_activities(
        self,
        *,
        search_text: Optional[str] = None,
        activity_types: Optional[List[ActivityType]] = None,
        definition_ids: Optional[List[str]] = None,
        record_ids: Optional[List[str]] = None,
        statuses: Optional[List[ActivityStatusEnum]] = None,
        label_ids: Optional[List[str]] = None,
        assigned_user_ids: Optional[List[str]] = None,
        created_by: Optional[str] = None,
        parent_id: Union[Optional[str], _UnsetType] = UNSET,
        limit: Optional[int] = None,
        completed_behavior: Optional[CompletedBehaviorEnum] = None,
    ) -> List[Activity]:
        """Search activities with server-side filtering.

        Returns the matching activities, in the server's default order, capped
        at `limit` (server max: 500).

        For list filters (`statuses`, `label_ids`, `assigned_user_ids`) the values
        are OR-combined: a hit on any value qualifies an activity.

        Args:
            search_text: Free-text query matched against activity title
            activity_types: Restrict to these activity types (e.g. `["task", "experiment"]`).
            definition_ids: Restrict to activities created from these definition UUIDs.
            record_ids: Restrict to activities containing any of these record UUIDs.
            statuses: Restrict to activities currently in any of these statuses.
            label_ids: Restrict to activities tagged with any of these label UUIDs.
            assigned_user_ids: Restrict to activities assigned to any of these user UUIDs.
            created_by: Restrict to activities created by this user UUID.
            parent_id: Parent-filter behavior — `UNSET` (default) for no filter,
                `None` to return root activities only, or a UUID for direct children
                of that activity.
            limit: Maximum number of results to return (server caps at 500).
            completed_behavior: How completed activities are surfaced; defaults
                server-side to `SHOW_ALL`.

        Returns:
            Matching activities, possibly empty.

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            # Find in-progress experiments assigned to a specific user
            results = client.activities.search_activities(
                activity_types=["experiment"],
                statuses=[ActivityStatusEnum.IN_PROGRESS],
                assigned_user_ids=["user-uuid"],
                limit=50,
            )

            # Find only root activities
            roots = client.activities.search_activities(parent_id=None)
            ```
        """
        params: Dict[str, Any] = {}

        if search_text is not None:
            params["search_text"] = search_text
        if activity_types is not None:
            params["activity_types"] = json.dumps(activity_types)
        if definition_ids is not None:
            params["definition_ids"] = json.dumps(definition_ids)
        if record_ids is not None:
            params["record_ids"] = json.dumps(record_ids)
        if statuses is not None:
            params["statuses"] = json.dumps(
                [[s.value if isinstance(s, ActivityStatusEnum) else s for s in statuses]]
            )
        if label_ids is not None:
            params["label_ids"] = json.dumps([label_ids])
        if assigned_user_ids is not None:
            params["assigned_user_ids"] = json.dumps([assigned_user_ids])
        if created_by is not None:
            params["created_by"] = created_by
        if not isinstance(parent_id, _UnsetType):
            params["parent_id"] = "null" if parent_id is None else parent_id
        if limit is not None:
            params["limit"] = limit
        if completed_behavior is not None:
            params["completed_behavior"] = (
                completed_behavior.value
                if isinstance(completed_behavior, CompletedBehaviorEnum)
                else completed_behavior
            )

        resp = self._client._get("/activities/search", params=params)
        if resp is None:
            return []
        return self._create_activity_list(resp)

    ##### for ActivityDefinitions #####
    @cached
    def get_definitions(self) -> List[ActivityDefinition]:
        """Retrieve all available activity definitions.

        Returns:
            All activity definitions in the workspace.

        Raises:
            KalbioAPIError: If the API request fails.
            KalbioResponseError: If the endpoint returns no usable body.
            ValidationError: If the data could not be validated as an ActivityDefinition.

        Note:
            This method caches its results.

        Example:
            ```python
            definitions = client.activities.get_definitions()
            ```
        """
        resp = _require_response_body(
            "GET",
            "/activity_definitions",
            self._client._get("/activity_definitions"),
        )
        return [self._create_activity_definition(data) for data in resp]

    def get_definition_by_id(
        self, definition_id: DefinitionIdentifier
    ) -> ActivityDefinition | None:
        """Retrieve an activity definition by ID (UUID or name)

        Args:
            definition_id: Identifier for the activity definition.

                This method will accept and resolve any type of DefinitionIdentifier.

        Returns:
            The activity definition if found, None otherwise.

        Example:
            ```python
            definition = client.activities.get_definition_by_id("definition_uuid")
            ```
        """
        id_map = self._get_definition_id_map()
        identifier = self._resolve_definition_id(definition_id)

        if identifier is None:
            return None
        else:
            return id_map.get(identifier, None)

    def get_definitions_by_ids(
        self, ids: List[DefinitionIdentifier]
    ) -> List[ActivityDefinition]:
        """Retrieve activity definitions by their identifiers

        Args:
            ids: List of definition identifiers to retrieve.

                This method will accept and resolve all types of DefinitionIdentifier.

        Returns:
            List of found activity definitions.

        Example:
            ```python
            defs = client.activities.get_definitions_by_ids(["def1", "def2"])
            ```
        """
        definitions = []

        for definition_id in ids:
            res = self.get_definition_by_id(definition_id)
            if res:
                definitions.append(res)

        return definitions

    def get_activity_definition_by_external_id(
        self, external_id: str
    ) -> ActivityDefinition | None:
        """Retrieve an activity definition by its external identifier.

        Args:
            external_id: The external identifier of the activity definition to retrieve.

        Returns:
            The ActivityDefinition object if found, otherwise None.

        Example:
            ```python
            definition = client.activities.get_activity_definition_by_external_id("jira-def-7")
            ```
        """
        definitions = self.get_definitions()
        return next(
            (d for d in definitions if d.external_id == external_id),
            None,
        )

    #########################
    #    Private Methods    #
    #########################

    ##### for Activities #####

    def _create_activity(self, data: dict) -> Activity:
        """Convert a dictionary of activity data into a validated Activity object.

        Args:
            data: A dictionary containing the activity information.

        Returns:
            An activity object created from the provided data, with the
                client set.

        Raises:
            ValidationError: If the data could not be validated as an Activity.
        """
        activity = Activity.model_validate(data)
        activity._set_client(self._client)

        return activity

    def _create_activity_list(self, data: list[dict]) -> List[Activity]:
        """Convert input data into a list of Activity objects.

        Args:
            data: The input data to be converted into Activity objects.

        Returns:
            A list of Activity objects with clients set.

        Raises:
            ValidationError: If the data could not be validated as a list of
                Activity objects.
        """
        return [self._create_activity(d) for d in data]

    @cached
    def _get_activity_id_map(self) -> dict[str, Activity]:
        """gets a dict that maps uuids to their corresponding Activity

        Returns:
             a map of uuid to Activity
        """
        return {activity.id: activity for activity in self.get_activities()}

    @cached
    def _get_activity_title_map(self) -> dict[str, Activity]:
        """gets a dict that maps an activity's title to its object instance

        Returns:
            str-to-Activity dict that maps titles to Activity
        """
        # Titles are neither unique nor required; untitled activities are
        # excluded and, on a title collision, resolution returns an arbitrary
        # matching activity.
        return {
            activity.title: activity
            for activity in self.get_activities()
            if activity.title is not None
        }

    def _resolve_activity_id(self, identifier: ActivityIdentifier | None) -> str | None:
        """Resolves an ActivityIdentifier.

        Will get the corresponding uuid of Activity based on the identifier.

        Identifiers will be resolved, while `None` will always return `None`.

        Args:
            identifier: Identifier for an Activity or None.

        Returns:
            Returns an Activity's UUID for a valid ActivityIdentifier, else returns None
        """
        if identifier is None:
            return None

        if isinstance(identifier, Activity):
            return identifier.id

        id_map = self._get_activity_id_map()
        if identifier in id_map:
            return identifier

        name_map = self._get_activity_title_map()
        activity = name_map.get(identifier)
        if activity:
            return activity.id

        _logger.debug(f"Activity not found: {identifier}")
        return None

    def _clear_activity_caches(self):
        """Clears all caches of Activity objects

        Call when any activity is created, removed, or updated
        """
        self.get_activities.cache_clear()
        self._get_activity_id_map.cache_clear()
        self._get_activity_title_map.cache_clear()
        # The record→activities mapping is derived from the activity set and
        # their record membership, so it goes stale whenever either changes.
        self._get_activities_with_record.cache_clear()

    ##### for ActivityDefinitions #####

    def _create_activity_definition(self, data: dict) -> ActivityDefinition:
        """Creates an ActivityDefinition based on API data

        Args:
            data: dict of json data

        Returns:
            validated ActivityDefinition

        Raises:
            ValidationError: if data can not be validated
        """
        activity_definition = ActivityDefinition.model_validate(data)
        activity_definition._set_client(self._client)

        return activity_definition

    @cached
    def _get_definition_id_map(self) -> dict[str, ActivityDefinition]:
        """get a map of uuids to their respective activity definition.

        Returns:
            A mapping of uuid-to-ActivityDefinition
        """
        return {definition.id: definition for definition in self.get_definitions()}

    @cached
    def _get_definition_title_map(self) -> dict[str, ActivityDefinition]:
        """get a map of an ActivityDefinition's title to their respective ActivityDefinition

        Returns:
            A mapping of title-to-Activity-Definition
        """
        # Titles are neither unique nor required; untitled definitions are
        # excluded and, on a title collision, resolution returns an arbitrary
        # matching definition.
        return {
            definition.title: definition
            for definition in self.get_definitions()
            if definition.title is not None
        }

    def _resolve_definition_id(
        self, identifier: DefinitionIdentifier | None
    ) -> str | None:
        """Resolve an ActivityDefinitionIdentifier to its corresponding uuid.

        Will return the corresponding UUID of given identifiers, and will always return `None` if the identifier is `None`.

        Args:
            identifier: An identifier for ActivityDefinition.

        Returns:
            Return the corresponding UUID if the identifier is valid, else returns None
        """
        if identifier is None:
            return None

        if isinstance(identifier, ActivityDefinition):
            return identifier.id

        id_map = self._get_definition_id_map()
        if identifier in id_map:  # check by uuid
            return identifier

        name_map = self._get_definition_title_map()
        definition = name_map.get(identifier)
        if definition:  # check by title
            return definition.id

        _logger.debug(f"Definition not found: {identifier}")
        return None

    def _clear_definition_caches(self):
        """Clears all caches of ActivityDefinition objects

        Call when any activity definition is created, removed, or updated
        """
        self.get_definitions.cache_clear()
        self._get_definition_id_map.cache_clear()
        self._get_definition_title_map.cache_clear()
