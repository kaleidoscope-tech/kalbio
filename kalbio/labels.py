"""Module for managing task labels in Kaleidoscope.

This module provides classes and services for working with task labels,
including retrieval and filtering of labels from the Kaleidoscope workspace.

Classes:
    Label: Represents a task label with an ID and name.
    LabelsService: Service class for interacting with label-related API endpoints.
"""

import logging

from functools import lru_cache
from typing import List
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import KaleidoscopeClient
from pydantic import TypeAdapter

_logger = logging.getLogger(__name__)


class Label(_KaleidoscopeBaseModel):
    """A class representing a label in the Kaleidoscope system.

    This class extends _KaleidoscopeBaseModel and provides functionality for
    managing label data including serialization and string representations.

    Attributes:
        label_name (str): The name of the label.
    """

    label_name: str

    def __str__(self):
        return f"{self.label_name}"


class LabelsService:
    """Service class for managing and retrieving task labels from Kaleidoscope.

    This service provides methods to fetch labels from the Kaleidoscope workspace
    and filter them by specific criteria. It uses caching to optimize repeated
    label retrieval requests.

    Example:
        ```python
        # get all labels
        all_labels = client.labels.get_labels()

        # get labels by id
        specific_labels = client.labels.get_labels_by_ids(['id1', 'id2'])
        ```
    """

    def __init__(self, client: KaleidoscopeClient):
        self._client = client

    @lru_cache
    def get_labels(self) -> List[Label]:
        """Retrieve the task labels defined in the workspace.

        This method caches its values.

        Returns:
            List[Label]: The labels in the workspace.

        Note:
            If an exception occurs during the API request, it logs the error,
            clears the cache, and returns an empty list.
        """
        try:
            resp = self._client._get("/activity_labels")
            return TypeAdapter(List[Label]).validate_python(resp)
        except Exception as e:
            _logger.error(f"Error fetching labels: {e}")
            self.get_labels.cache_clear()
            return []

    def get_labels_by_ids(self, ids: List[str]) -> List[Label]:
        """Retrieve a list of Label objects whose IDs match the provided list.

        Args:
            ids (List[str]): A list of label IDs to filter by.

        Returns:
            List[Label]: A list of Label instances with IDs found in ids.
        """
        return [label for label in self.get_labels() if label.id in ids]
