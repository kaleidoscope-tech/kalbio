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
import logging
from datetime import datetime
from enum import Enum
from functools import cached_property, lru_cache

import cachetools.func
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import KaleidoscopeClient
from kalbio.entity_fields import DataFieldTypeEnum
from kalbio.programs import Program
from kalbio.labels import Label
from kalbio.workspace import WorkspaceUser, WorkspaceGroup
from typing import Any, BinaryIO, List, Literal, Optional, TypeAlias, Union
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kalbio.records import Record, RecordIdentifier


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
        READY_FOR_MAKE (str): Activity is ready for manufacturing/creation.
        IN_SYNTHESIS (str): Activity is in the synthesis phase.
        IN_TEST (str): Activity is in the testing phase.
        IN_ANALYSIS (str): Activity is in the analysis phase.
        PARKED (str): Activity has been parked for later consideration.
        COMPLETE (str): Activity has been completed.
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
    READY_FOR_MAKE = "ready for make"
    IN_SYNTHESIS = "in synthesis"
    IN_TEST = "in test"
    IN_ANALYSIS = "in analysis"
    PARKED = "parked"
    COMPLETE = "complete"

    IDEATION = "ideation"
    TWO_D_SELECTION = "2D selection"
    COMPUTATION = "computation"
    COMPOUND_SELECTION = "compound selection"
    SELECTED = "selected"
    QUEUE_FOR_SYNTHESIS = "queue for synthesis"
    DATA_REVIEW = "data review"

    DONE = "done"


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

    property_field_id: str
    content: Any
    created_at: datetime
    last_updated_by: str
    created_by: str
    property_name: str
    field_type: DataFieldTypeEnum

    def __str__(self):
        return f"Property({self.property_name}:{self.content})"

    def update_property(self, property_value: Any) -> None:
        """Update the property with a new value.

        Args:
            property_value: The new value to set for the property.

        Example:
            ```python
            prop.update_property("Reviewed")
            ```
        """
        try:
            resp = self._client._put(
                "/properties/" + self.id, {"content": property_value}
            )
            if resp:
                for key, value in resp.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
        except Exception as e:
            _logger.error(f"Error updating property {self.id}: {e}")
            return None

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
                uploaded file) if request successful, otherwise None.

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
        try:
            resp = self._client._post_file(
                "/properties/" + self.id + "/file",
                (file_name, file_data, file_type),
            )
            if resp is None or len(resp) == 0:
                return None

            return resp
        except Exception as e:
            _logger.error(f"Error adding file to property {self.id}: {e}")
            return None


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

    Example:
        ```python
        definition = client.activities.get_definition_by_id("definition_uuid")
        if definition:
            print(definition.title, definition.activity_type)
        ```
    """

    program_ids: List[str]
    title: str
    activity_type: ActivityType
    status: Optional[ActivityStatusEnum] = None
    assigned_user_ids: List[str]
    assigned_group_ids: List[str]
    label_ids: List[str]
    properties: List[Property]
    external_id: Optional[str] = None

    def __str__(self):
        return f"{self.id}:{self.title}"

    @cached_property
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

    Example:
        ```python
        activity = client.activities.get_activity_by_id("activity_uuid")
        if activity:
            print(activity.title, activity.status)
            first_record = activity.records[0] if activity.records else None
        ```
    """

    created_at: datetime
    parent_id: Optional[str] = None
    child_ids: List[str]
    definition_id: Optional[str] = None
    program_ids: List[str]
    activity_type: ActivityType
    title: str
    description: Any
    status: ActivityStatusEnum
    assigned_user_ids: List[str]
    assigned_group_ids: List[str]
    due_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    duration: Optional[int] = None
    completed_at_date: Optional[datetime] = None
    dependencies: List[str]
    label_ids: List[str]
    is_draft: bool
    properties: List[Property]
    external_id: Optional[str] = None

    # operation fields
    all_record_ids: List[str]

    def __str__(self):
        return f'Activity("{self.title}")'

    @cached_property
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

    @cached_property
    def assigned_users(self) -> List[WorkspaceUser]:
        """Get the assigned users for this activity.

        Returns:
            The users assigned to this activity.

        Note:
            This is a cached property.
        """
        return self._client.workspace.get_members_by_ids(self.assigned_user_ids)

    @cached_property
    def assigned_groups(self) -> List[WorkspaceGroup]:
        """Get the assigned groups for this activity.

        Returns:
            The groups assigned to this activity.

        Note:
            This is a cached property.
        """
        return self._client.workspace.get_groups_by_ids(self.assigned_group_ids)

    @cached_property
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

    @cached_property
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

    @cached_property
    def child_activities(self) -> List[Activity]:
        """Retrieve the child activities associated with this activity.

        Returns:
            A list of Activity objects representing the child activities.

        Note:
            This is a cached property.
        """
        try:
            resp = self._client._get("/activities/" + self.id + "/activities")
            return self._client.activities._create_activity_list(resp)
        except Exception as e:
            _logger.error(f"Error fetching child activities: {e}")
            return []

    @property
    def records(self) -> List["Record"]:
        """Retrieve the records associated with this activity.

        Returns:
            A list of Record objects corresponding to the activity.

        Note:
            This is a cached property.
        """
        try:
            resp = self._client._get("/operations/" + self.id + "/records")
            return [
                rec for rec in self._client.records._create_record_list(resp) if rec
            ]
        except Exception as e:
            _logger.error(f"Error fetching records: {e}")
            return []

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

    def update(self, **kwargs: Any) -> None:
        """Update the activity with the provided keyword arguments.

        Args:
            **kwargs: Arbitrary keyword arguments representing fields to update
                for the activity.

        Note:
            After calling update(), cached properties may be stale. Re-fetch the activity if needed.

        Example:
            ```python
            activity.update(status=ActivityStatusEnum.IN_PROGRESS)
            ```
        """
        try:
            resp = self._client._put("/activities/" + self.id, kwargs)
            if resp:
                for key, value in resp.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
        except Exception as e:
            _logger.error(f"Error updating activity: {e}")
            return None

    def add_records(self, record_ids: List[str]) -> None:
        """Add a list of record IDs to the activity.

        Args:
            record_ids: A list of record IDs to be added to the activity.

        Example:
            ```python
            activity.add_records(["record_uuid_1", "record_uuid_2"])
            ```
        """
        try:
            self._client._put(
                "/operations/" + self.id + "/records", {"record_ids": record_ids}
            )
        except Exception as e:
            _logger.error(f"Error adding record: {e}")
            return None

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


class ActivitiesService:
    """Service class for managing activities in the Kaleidoscope platform.

    This service provides methods to create, retrieve, and manage activities
    (tasks/experiments) and their definitions within a Kaleidoscope workspace.
    It handles activity lifecycle operations including creation, retrieval by
    ID or associated records, and batch operations.

    Note:
        Some methods use LRU caching to improve performance. Cache is cleared on errors.
    """

    def __init__(self, client: KaleidoscopeClient):
        self._client = client

    #########################
    #    Public  Methods    #
    #########################

    ##### for Activities #####

    @lru_cache
    def get_activities(self) -> List[Activity]:
        """Retrieve all activities in the workspace, including experiments.

        Returns:
            A list of Activity objects representing the activities
                in the workspace.

        Note:
            This method caches its results. If an exception occurs, logs the error,
            clears the cache, and returns an empty list.

        Example:
            ```python
            activities = client.activities.get_activities()
            ```
        """
        try:
            resp = self._client._get("/activities")
            return self._create_activity_list(resp)
        except Exception as e:
            _logger.error(f"Error fetching activities: {e}")
            self._clear_activity_caches()
            return []

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
        start_date: Optional[datetime] = None,
        duration: Optional[int] = None,
    ) -> Activity | None:
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
            start_date: Start date for the activity. Defaults to None.
            duration: Duration in days for the activity. Defaults to None.

        Returns:
            The newly created activity instance or None if activity
                creation was not successful.

        Example:
            ```python
            new_activity = client.activities.create_activity(
                title="Synthesis",
                activity_type="experiment",
                program_ids=["program_uuid"],
            )
            ```
        """
        self._clear_activity_caches()

        try:
            payload = {
                "title": title,
                "activity_type": activity_type,
                "definition_id": self._resolve_definition_id(activity_definition_id),
                "program_ids": program_ids if program_ids else [],
                "assigned_user_ids": assigned_user_ids if assigned_user_ids else [],
                "start_date": start_date.isoformat() if start_date else None,
                "duration": duration,
            }
            resp = self._client._post("/activities", payload)
            return self._create_activity(resp[0])
        except Exception as e:
            _logger.error(f"Error creating activity {title}: {e}")
            return None

    @cachetools.func.ttl_cache(maxsize=128, ttl=10)
    def get_activities_with_record(self, record_id: RecordIdentifier) -> List[Activity]:
        """Retrieve all activities that contain a specific record.

        Args:
            record_id: Identifier for the record.

                Any type of RecordIdentifier will be accepted.

        Returns:
            Activities that include the specified record.

        Note:
            If an exception occurs, logs the error and returns an empty list.

        Example:
            ```python
            activities = client.activities.get_activities_with_record("record_uuid")
            ```
        """
        record_uuid = self._client.records._resolve_to_record_id(record_id)
        if record_uuid is None:
            return []

        try:
            resp = self._client._get("/records/" + record_uuid + "/operations")
            return self._create_activity_list(resp)
        except Exception as e:
            _logger.error(f"Error fetching activities with record {record_id}: {e}")
            self.get_activities_with_record.cache_clear()
            return []

    ##### for ActivityDefinitions #####
    @lru_cache
    def get_definitions(self) -> List[ActivityDefinition]:
        """Retrieve all available activity definitions.

        Returns:
            All activity definitions in the workspace.

        Raises:
            ValidationError: If the data could not be validated as an ActivityDefinition.

        Note:
            This method caches its results. If an exception occurs, logs the error,
            clears the cache, and returns an empty list.

        Example:
            ```python
            definitions = client.activities.get_definitions()
            ```
        """
        try:
            resp = self._client._get("/activity_definitions")
            return [self._create_activity_definition(data) for data in resp]

        except Exception as e:
            _logger.error(f"Error fetching activity definitions: {e}")
            self._clear_definition_caches()
            return []

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

    @lru_cache
    def _get_activity_id_map(self) -> dict[str, Activity]:
        """gets a dict that maps uuids to their corresponding Activity

        Returns:
             a map of uuid to Activity
        """
        return {activity.id: activity for activity in self.get_activities()}

    @lru_cache
    def _get_activity_title_map(self) -> dict[str, Activity]:
        """gets a dict that maps an activity's title to its object instance

        Returns:
            str-to-Activity dict that maps titles to Activity
        """
        return {activity.title: activity for activity in self.get_activities()}

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

        _logger.error(f"Activity not found: {identifier}")
        return None

    def _clear_activity_caches(self):
        """Clears all caches of Activity objects

        Call when any activity is created, removed, or updated
        """
        self.get_activities.cache_clear()
        self._get_activity_id_map.cache_clear()
        self._get_activity_title_map.cache_clear()

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

    @lru_cache
    def _get_definition_id_map(self) -> dict[str, ActivityDefinition]:
        """get a map of uuids to their respective activity definition.

        Returns:
            A mapping of uuid-to-ActivityDefinition
        """
        return {definition.id: definition for definition in self.get_definitions()}

    @lru_cache
    def _get_definition_title_map(self) -> dict[str, ActivityDefinition]:
        """get a map of an ActivityDefinition's title to their respective ActivityDefinition

        Returns:
            A mapping of title-to-Activity-Definition
        """
        return {definition.title: definition for definition in self.get_definitions()}

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

        _logger.error(f"Definition not found: {identifier}")
        return None

    def _clear_definition_caches(self):
        """Clears all caches of ActivityDefinition objects

        Call when any activity definition is created, removed, or updated
        """
        self.get_definitions.cache_clear()
        self._get_definition_id_map.cache_clear()
        self._get_definition_title_map.cache_clear()
