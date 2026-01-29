"""Provides models and services for managing workspaces in the Kaleidoscope system.

This module contains data models for workspaces, workspace users, workspace groups,
and workspace events, along with a service class for interacting with workspace-related
API endpoints.

Classes:
    WorkspaceAccessLevelEnum: Enumeration of possible access levels for workspace users.
    Workspace: Model representing a workspace with its basic metadata.
    WorkspaceUser: Model representing a user within a workspace, including access level.
    WorkspaceGroup: Model representing a group of users within a workspace.
    WorkspaceEvent: Model representing an event that occurred within a workspace.
    WorkspaceService: Service class providing methods to interact with workspace API endpoints.

Example:
    ```python
        # get an instance of the workspace
        workspace = client.workspace.get_workspace()

        # get all members in the workspace
        members = client.workspace.get_members()

        # get all events, with search criteria
        events = client.workspace.get_events(event_types=["create", "update"])
    ```
"""

from datetime import datetime
import json
import logging
from enum import Enum
from functools import lru_cache
from typing import List, Optional, TypedDict, Unpack
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import KaleidoscopeClient
from pydantic import TypeAdapter

_logger = logging.getLogger(__name__)


class WorkspaceAccessLevelEnum(str, Enum):
    """Enumeration of possible access levels for workspace users.

    Attributes:
        ADMIN: Administrator access with full privileges.
        TEAM_MEMBER: Regular team member access.
        GUEST: Guest access with limited privileges.
        VIEWER: Read-only viewer access.
        DEACTIVATED: Deactivated user status.
    """

    ADMIN = "admin"
    TEAM_MEMBER = "team-member"
    GUEST = "guest"
    VIEWER = "viewer"
    DEACTIVATED = "deactivated"


class Workspace(_KaleidoscopeBaseModel):
    """A model representing a workspace in the Kaleidoscope system.

    This class extends _KaleidoscopeBaseModel and provides a structured representation
    of a workspace with its associated metadata and utility methods for serialization
    and string representation.

    Attributes:
        id (str): UUID of the workspace
        workspace_name (str): The name identifier for the workspace.
    """

    workspace_name: str

    def __str__(self):
        return f"{self.workspace_name}"


class WorkspaceUser(_KaleidoscopeBaseModel):
    """Represents a user within a workspace with their access permissions and contact information.

    This class models a workspace user, storing their identification, name preferences,
    access level, and email address. It inherits from _KaleidoscopeBaseModel and provides
    utility methods for serialization and string representation.

    Attributes:
        full_name (Optional[str]): The user's full legal or registered name.
        preferred_name (Optional[str]): The name the user prefers to be called.
        access_level (WorkspaceAccessLevelEnum): The user's permission level within the workspace.
        email (str): The user's email address for communication and identification.
    """

    full_name: Optional[str]
    preferred_name: Optional[str]
    access_level: WorkspaceAccessLevelEnum
    email: str

    def __str__(self):
        return f"{self.full_name}"


class WorkspaceGroup(_KaleidoscopeBaseModel):
    """Represents a workspace group in the Kaleidoscope system.

    A WorkspaceGroup is a collection of users and programs that are organized together
    under a common group name and associated email address.

    Attributes:
        group_name (str): The name of the workspace group.
        user_ids (List[str]): A list of user IDs that belong to this workspace group.
        program_ids (List[str]): A list of program IDs associated with this workspace group.
        email (str): The email address associated with this workspace group.
    """

    group_name: str
    user_ids: List[str]
    program_ids: List[str]
    email: str

    def __str__(self):
        return f"{self.group_name}"


class WorkspaceEvent(_KaleidoscopeBaseModel):
    """Represents a workspace event in the Kaleidoscope system.

    This class models events that occur within a workspace, such as user actions,
    resource modifications, or system-generated events. It inherits from
    _KaleidoscopeBaseModel and provides methods for serialization and representation.

    Attributes:
        full_name (str): The full name of the user associated with the event.
        preferred_name (Optional[str]): The preferred name of the user, if available.
        is_bot (bool): Flag indicating whether the event was triggered by a bot.
        event_attrs (dict): Additional attributes specific to the event type.
        created_at (datetime): Timestamp when the event was created.
        resource_id (Optional[str]): ID of the resource associated with the event, if applicable.
        resource_type (Optional[str]): Type of the resource associated with the event, if applicable.
        event_type (str): The type/category of the event.
        event_type_version (int): Version number of the event type schema.
        event_user_id (str): The unique identifier of the user who triggered the event.
        parent_bulk_event_id (str): ID of the parent event if this is part of a bulk operation.
        is_bulk (bool): Flag indicating whether this is a bulk event.
    """

    full_name: str
    preferred_name: Optional[str]
    is_bot: bool
    event_attrs: dict
    created_at: datetime
    resource_id: Optional[str]
    resource_type: Optional[str]
    event_type: str
    event_type_version: int
    event_user_id: str
    parent_bulk_event_id: str
    is_bulk: bool

    def __str__(self):
        return f"{self.id}:{self.event_type}"


class WorkspaceService:
    """Service class for managing workspace-related operations in Kaleidoscope.

    This service provides methods to retrieve workspace information, members, groups,
    and events. It uses caching (via lru_cache) for frequently accessed data like
    workspace details, members, and groups to improve performance.

    Example:
        ```python
        # get an instance of the workspace
        workspace = client.workspace.get_workspace()

        # get all members in the workspace
        members = client.workspace.get_members()

        # get all events, with search criteria
        events = client.workspace.get_events(event_types=["create", "update"])
        ```

    Note:
        Cached methods (get_workspace, get_members, get_groups) will automatically
        clear their cache on error to ensure stale data is not returned on subsequent calls.
    """

    def __init__(self, client: KaleidoscopeClient):
        self._client = client

    @lru_cache
    def get_workspace(self) -> Workspace | None:
        """Retrieves the authenticated workspace.

        This method caches its values.

        Returns:
            (Workspace | None): The active workspace, or None if an error occurs.
        """
        try:
            resp = self._client._get("/workspaces/active")
            return Workspace.model_validate(resp)
        except Exception as e:
            _logger.error(f"Error fetching workspace: {e}")
            self.get_workspace.cache_clear()
            return None

    @lru_cache
    def get_members(self) -> List[WorkspaceUser]:
        """Retrieves the members of the authenticated workspace.

        This method caches its values.

        Returns:
            List[WorkspaceUser]: The users in the workspace.

        Note:
            If an exception occurs during the API request, it logs the error,
            clears the cache, and returns an empty list.
        """
        try:
            resp = self._client._get("/workspaces/members")
            return TypeAdapter(List[WorkspaceUser]).validate_python(resp)
        except Exception as e:
            _logger.error(f"Error fetching members: {e}")
            self.get_members.cache_clear()
            return []

    def get_members_by_ids(self, ids: List[str]) -> List[WorkspaceUser]:
        """Retrieves a list of WorkspaceUser objects whose IDs match the provided list.

        Args:
            ids (List[str]): A list of member IDs to filter by.

        Returns:
            List[WorkspaceUser]: A list of WorkspaceUser instances with IDs found in ids.
        """
        return [member for member in self.get_members() if member.id in ids]

    @lru_cache
    def get_groups(self) -> List[WorkspaceGroup]:
        """Retrieves the groups of the authenticated workspace.

        This method caches its values.

        Returns:
            List[WorkspaceGroup]: The groups in the workspace.

        Note:
            If an exception occurs during the API request, it logs the error,
            clears the cache, and returns an empty list.
        """
        try:
            resp = self._client._get("/workspaces/groups")
            return TypeAdapter(List[WorkspaceGroup]).validate_python(resp)
        except Exception as e:
            _logger.error(f"Error fetching groups: {e}")
            self.get_groups.cache_clear()
            return []

    def get_groups_by_ids(self, ids: List[str]) -> List[WorkspaceGroup]:
        """Retrieves a list of WorkspaceGroup objects whose IDs match the provided list.

        Args:
            ids (List[str]): A list of group IDs to filter by.

        Returns:
            List[WorkspaceGroup]: A list of WorkspaceGroup instances with IDs found in ids.
        """
        return [group for group in self.get_groups() if group.id in ids]

    class EventsQuery(TypedDict):
        """TypedDict for workspace events query parameters.

        Attributes:
            page (Optional[int]): The page number for pagination.
            page_size (Optional[int]): The number of items per page.
            event_types (List[str]): List of event types to filter by.
            resource_type (str): The type of resource to filter by.
            event_user_ids (list[str]): List of user IDs to filter events by.
            after_date (datetime): Filter events occurring after this date.
            before_date (datetime): Filter events occurring before this date.
        """

        page: Optional[int]
        page_size: Optional[int]
        event_types: List[str]
        resource_type: str
        event_user_ids: list[str]
        after_date: datetime
        before_date: datetime

    def get_events(self, **params: Unpack[EventsQuery]) -> List[WorkspaceEvent]:
        """Searches for events using the provided query parameters.

        Args:
            **params (Unpack[EventsQuery]): Keyword arguments representing search criteria. Non-string values will be JSON-encoded before being sent.

        Returns:
            list[WorkspaceEvent]: A list of events matching the search criteria.
            Returns an empty list if the response is empty.

        Note:
            If an exception occurs during the API request, it logs the error and returns an empty list.
        """
        try:
            client_params = {
                key: (value if isinstance(value, str) else json.dumps(value))
                for key, value in params.items()
            }
            resp = self._client._get("/workspaces/events", client_params)
            if resp is None:
                return []

            return resp
        except Exception as e:
            _logger.error(f"Error fetching events: {e}")
            return []
