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

import logging
from functools import lru_cache
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import KaleidoscopeClient
from pydantic import TypeAdapter
from typing import List, Literal, TypeAlias, Union

_logger = logging.getLogger(__name__)

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

    dashboard_id: str
    category_name: str
    operation_definition_ids: List[str]
    label_ids: List[List[str]]
    field_ids: List[str]

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

    dashboard_name: str
    dashboard_description: str
    dashboard_type: DashboardType
    record_ids: List[str]
    record_set_ids: List[str]

    def __str__(self):
        return f"{self.dashboard_name}"

    def add_category(
        self,
        category_name: str,
        operation_definition_ids: List[str],
        label_ids: List[List[str]],
        field_ids: List[str],
    ) -> DashboardCategory | None:
        """Create a new dashboard category on this dashboard.

        Args:
            category_name (str): The name of the new category.
            operation_definition_ids (List[str]): A list of operation definition IDs to include in the category.
            label_ids (List[List[str]]): A list of label IDs to include in the category.
            field_ids (List[str]): A list of field IDs to include in the category.

        Returns:
            (DashboardCategory | None): The newly created category object, or None if creation failed.
        """
        try:
            data = data = {
                "category_name": category_name,
                "operation_definition_ids": operation_definition_ids,
                "label_ids": label_ids,
                "field_ids": field_ids,
            }
            resp = self._client._post(
                f"/dashboards/{self.id}/categories",
                data,
            )
            return resp
        except Exception as e:
            _logger.error(f"Error creating a category for this dashboard: {e}")
            return None

    def remove_category(self, category_id: str):
        """Remove a category from the dashboard.

        Args:
            category_id (str): The unique identifier of the category to be removed.
        """
        try:
            self._client._delete(
                f"/dashboards/{self.id}/categories/{category_id}",
            )
        except Exception as e:
            _logger.error(f"Error removing this category: {e}")
            return

    def get_categories(self) -> List[DashboardCategory]:
        """Retrieve all categories associated with this dashboard.

        Returns:
            List[DashboardCategory]: A list of DashboardCategory objects associated with this dashboard.
        """
        try:
            resp = self._client._get(
                f"/dashboards/{self.id}/categories",
            )
            return resp
        except Exception as e:
            _logger.error(f"Error fetching categories of this dashboard: {e}")
            return []

    def add_record(self, record_id: str):
        """Add a record to the dashboard.

        Args:
            record_id (str): The unique identifier of the record to be added.
        """
        try:
            data = {"record_id": record_id}
            resp = self._client._post(f"/dashboards/{self.id}/records", data)
            if resp:
                self.record_ids = resp.record_ids
        except Exception as e:
            _logger.error(f"Error adding record to this dashboard: {e}")
            return

    def remove_record(self, record_id: str):
        """Remove a record from the dashboard.

        Args:
            record_id (str): The unique identifier of the record to be removed.
        """
        try:
            self._client._delete(
                f"/dashboards/{self.id}/records/{record_id}",
            )
        except Exception as e:
            _logger.error(f"Error removing this record: {e}")
            return

    def add_set(self, set_id):
        """Add a set to the dashboard.

        Args:
            set_id (str): The unique identifier of the set to be added.
        """
        try:
            data = {"set_id": set_id}
            resp = self._client._post(f"/dashboards/{self.id}/sets", data)
            if resp:
                self.record_set_ids = resp.record_set_id
        except Exception as e:
            _logger.error(f"Error adding set to this dashboard: {e}")
            return

    def remove_set(self, set_id: str):
        """Remove a set from the dashboard.

        Args:
            set_id (str): The unique identifier of the set to be removed.
        """
        try:
            resp = self._client._delete(
                f"/dashboards/{self.id}/sets/{set_id}",
            )
            if resp:
                self.record_set_ids = resp.record_set_id
        except Exception as e:
            _logger.error(f"Error removing this set: {e}")
            return


class DashboardsService:
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

    def __init__(self, client: KaleidoscopeClient):
        self._client = client

    def _create_dashboard(self, data: dict) -> Dashboard:
        """Create a Dashboard instance from the provided data dictionary.

        Args:
            data (dict): A dictionary containing the data required to instantiate a Dashboard.

        Returns:
            Dashboard: The validated and initialized Dashboard instance.
        """
        dashboard = TypeAdapter(Dashboard).validate_python(data)
        dashboard._set_client(self._client)
        return dashboard

    def _create_dashboard_list(self, data: list[dict]) -> List[Dashboard]:
        """Convert a list of dashboard data dictionaries into a list of Dashboard objects.

        Args:
            data (list[dict]): The input data representing dashboards.

        Returns:
            List[Dashboard]: A list of Dashboard instances with the client set.
        """
        dashboards = TypeAdapter(List[Dashboard]).validate_python(data)

        for dashboard in dashboards:
            dashboard._set_client(self._client)

        return dashboards

    @lru_cache
    def get_dashboards(self) -> List[Dashboard]:
        """Retrieve a list of dashboards from the client.

        Returns:
            List[Dashboard]: A list of Dashboard objects created from the response.
        """
        try:
            resp = self._client._get("/dashboards")
            return self._create_dashboard_list(resp)
        except Exception as e:
            _logger.error(f"Error fetching dashboards: {e}")
            self.get_dashboards.cache_clear()
            return []
