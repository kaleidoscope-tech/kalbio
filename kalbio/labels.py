"""Module for managing task labels in Kaleidoscope.

This module provides classes and services for working with task labels,
including retrieval and filtering of labels from the Kaleidoscope workspace.

Classes:
    Label: Represents a task label with an ID and name.
    LabelsService: Service class for interacting with label-related API endpoints.
"""


from kalbio._base import _BaseService
from kalbio._cache import cached
from typing import List, Optional
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import _require_response_body



class Label(_KaleidoscopeBaseModel):
    """A class representing a label in the Kaleidoscope system.

    This class extends _KaleidoscopeBaseModel and provides functionality for
    managing label data including serialization and string representations.

    Attributes:
        label_name (str): The name of the label.
    """

    label_name: Optional[str] = None

    def __str__(self):
        return f"{self.label_name}"


class LabelsService(_BaseService):
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

    @cached
    def get_labels(self) -> List[Label]:
        """Retrieve the task labels defined in the workspace.

        This method caches its values.

        Returns:
            List[Label]: The labels in the workspace.

        Raises:
            KalbioAPIError: If the API request fails.
            KalbioResponseError: If the endpoint returns no usable body.
        """
        resp = _require_response_body(
            "GET", "/activity_labels", self._client._get("/activity_labels")
        )
        return Label._list_from_api(resp, self._client)

    def get_labels_by_ids(self, ids: List[str]) -> List[Label]:
        """Retrieve a list of Label objects whose IDs match the provided list.

        Args:
            ids (List[str]): A list of label IDs to filter by.

        Returns:
            List[Label]: A list of Label instances with IDs found in ids.
        """
        id_set = set(ids)
        return [label for label in self.get_labels() if label.id in id_set]
