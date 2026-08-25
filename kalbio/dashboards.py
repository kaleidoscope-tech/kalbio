"""
Dashboards module for the Kaleidoscope system.

This module provides classes and services for working with dashboards in Kaleidoscope.
Dashboards summarize data across a workspace in some way, allowing for data comparison,
status review, and more.

Classes:
    Dashboard: Represents a single dashboard with its categories and configurations.
    DashboardsService: Service class for managing and querying dashboards.

Example:
    ```python
    # get all dashboards
    dashboards = client.dashboards.get_dashboards()
    ```
"""

from kalbio._base import _BaseService
from kalbio._cache import cached
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import _require_response_body
from pydantic import Field
from typing import List, Literal, Optional, TypeAlias, Union


DashboardType: TypeAlias = Union[
    Literal["decision"],
    Literal["data"],
    Literal["chart"],
    Literal["field"],
    Literal["summary"],
]
"""Type alias representing the valid types of dashboards in the system.

This type defines the allowed string values for the `dashboard_type` field
in Dashboard models.
"""


class DashboardCategory(_KaleidoscopeBaseModel):
    """Represents the definition of a DashboardCategory in the Kaleidoscope system.

    A DashboardCategory defines a summary and aggregation for entities and sets in that
    dashboard.

    Attributes:
        id (str): UUID of the Dashboard Category.
        dashboard_id (str): The dashboard this category is a part of.
        category_name (str): The name of the category.
        operation_definition_ids (List[str]): The operation activity definitions reflected in this category.
        label_ids (List[List[str]]): The labels reflected in this category.
        field_ids (List[str]): The fields reflected in this category.
    """

    dashboard_id: Optional[str] = None
    category_name: Optional[str] = None
    operation_definition_ids: List[str] = Field(default_factory=list)
    label_ids: List[List[str]] = Field(default_factory=list)
    field_ids: List[str] = Field(default_factory=list)

    def __str__(self):
        return f"{self.id}:{self.category_name}"


class Dashboard(_KaleidoscopeBaseModel):
    """Represents a dashboard in the Kaleidoscope system.

    A Dashboard represents an aggregation and summarization of the state of a workspace with respect
    to both entity data and activity.

    Attributes:
        id (str): UUID of the dashboard.
        dashboard_name (str): The name of the dashboard.
        dashboard_description (str): The description of the dashboard.
        dashboard_type (DashboardType): The type of the dashboard, representing how it aggregates data.
        record_ids (List[str]): List of record IDs associated with the dashboard.
        record_set_ids (List[str]): List of record set IDs associated with the dashboard.
    """

    dashboard_name: Optional[str] = None
    dashboard_description: Optional[str] = None
    dashboard_type: Optional[DashboardType] = None
    record_ids: List[str] = Field(default_factory=list)
    record_set_ids: List[str] = Field(default_factory=list)

    def __str__(self):
        return f"{self.dashboard_name}"

    def add_category(
        self,
        category_name: str,
        operation_definition_ids: List[str],
        label_ids: List[List[str]],
        field_ids: List[str],
    ) -> DashboardCategory:
        """Create a new dashboard category on this dashboard.

        Args:
            category_name (str): The name of the new category.
            operation_definition_ids (List[str]): A list of operation definition IDs to include in the category.
            label_ids (List[List[str]]): A list of label IDs to include in the category.
            field_ids (List[str]): A list of field IDs to include in the category.

        Returns:
            DashboardCategory: The newly created category object.

        Raises:
            KalbioAPIError: If the API request fails.
        """
        data = {
            "category_name": category_name,
            "operation_definition_ids": operation_definition_ids,
            "label_ids": label_ids,
            "field_ids": field_ids,
        }
        url = f"/dashboards/{self.id}/categories"
        resp = _require_response_body("POST", url, self._client._post(url, data))
        return DashboardCategory._from_api(resp, self._client)

    def remove_category(self, category_id: str):
        """Remove a category from the dashboard.

        Args:
            category_id (str): The unique identifier of the category to be removed.
        """
        self._client._delete(
            f"/dashboards/{self.id}/categories/{category_id}",
        )

    def get_categories(self) -> List[DashboardCategory]:
        """Retrieve all categories associated with this dashboard.

        Returns:
            List[DashboardCategory]: A list of DashboardCategory objects associated with this dashboard.
        """
        resp = self._client._get(
            f"/dashboards/{self.id}/categories",
        )
        if resp is None:
            return []
        return DashboardCategory._list_from_api(resp, self._client)

    def add_record(self, record_id: str):
        """Add a record to the dashboard.

        Args:
            record_id (str): The unique identifier of the record to be added.
        """
        data = {"record_id": record_id}
        self._client._post(f"/dashboards/{self.id}/records", data)
        if record_id not in self.record_ids:
            self.record_ids.append(record_id)
        self._client.dashboards.get_dashboards.cache_clear()

    def remove_record(self, record_id: str):
        """Remove a record from the dashboard.

        Args:
            record_id (str): The unique identifier of the record to be removed.
        """
        self._client._delete(
            f"/dashboards/{self.id}/records/{record_id}",
        )
        if record_id in self.record_ids:
            self.record_ids.remove(record_id)
        self._client.dashboards.get_dashboards.cache_clear()

    def add_set(self, set_id: str):
        """Add a set to the dashboard.

        Args:
            set_id (str): The unique identifier of the set to be added.
        """
        data = {"set_id": set_id}
        self._client._post(f"/dashboards/{self.id}/sets", data)
        if set_id not in self.record_set_ids:
            self.record_set_ids.append(set_id)
        self._client.dashboards.get_dashboards.cache_clear()

    def remove_set(self, set_id: str):
        """Remove a set from the dashboard.

        Args:
            set_id (str): The unique identifier of the set to be removed.
        """
        self._client._delete(
            f"/dashboards/{self.id}/sets/{set_id}",
        )
        if set_id in self.record_set_ids:
            self.record_set_ids.remove(set_id)
        self._client.dashboards.get_dashboards.cache_clear()


class DashboardsService(_BaseService):
    """Service class for managing and retrieving dashboards from the Kaleidoscope API.

    This service provides methods to fetch dashboards. It handles the conversion of raw API responses
    into validated Dashboard objects.

    Attributes:
        client (KaleidoscopeClient): The Kaleidoscope client instance used for API communication.

    Example:
        ```python
        client = KaleidoscopeClient(...)
        dashboards = client.dashboards.get_dashboards()
        ```
    """

    def _create_dashboard(self, data: dict) -> Dashboard:
        """Create a Dashboard instance from the provided data dictionary.

        Args:
            data (dict): A dictionary containing the data required to instantiate a Dashboard.

        Returns:
            Dashboard: The validated and initialized Dashboard instance.
        """
        return Dashboard._from_api(data, self._client)

    def _create_dashboard_list(self, data: list[dict]) -> List[Dashboard]:
        """Convert a list of dashboard data dictionaries into a list of Dashboard objects.

        Args:
            data (list[dict]): The input data representing dashboards.

        Returns:
            List[Dashboard]: A list of Dashboard instances with the client set.
        """
        return Dashboard._list_from_api(data, self._client)

    @cached
    def get_dashboards(self) -> List[Dashboard]:
        """Retrieve a list of dashboards from the client.

        Returns:
            List[Dashboard]: A list of Dashboard objects created from the response.
        """
        resp = _require_response_body(
            "GET", "/dashboards", self._client._get("/dashboards")
        )
        return self._create_dashboard_list(resp)
