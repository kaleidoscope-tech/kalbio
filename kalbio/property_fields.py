"""Service for managing property field definitions in Kaleidoscope.

This module provides classes and services for working with property fields, which define
named properties with descriptions and data types used to structure and validate data
within the Kaleidoscope framework.

Classes:
    PropertyField: Represents a single property field with name, description, and type.
    PropertyFieldsService: Service for retrieving and managing property field definitions.

Example:
    ```python
    fields = client.property_fields.get_property_fields()
    for field in fields:
        print(f"{field.property_name}: {field.field_type}")
    ```
"""

import logging
from functools import lru_cache
from typing import List
from pydantic import TypeAdapter
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import KaleidoscopeClient
from kalbio.entity_fields import DataFieldTypeEnum

_logger = logging.getLogger(__name__)


class PropertyField(_KaleidoscopeBaseModel):
    """Represents a property field in the Kaleidoscope system.

    A PropertyField defines a named property with a description and data type,
    used to structure and validate data within the Kaleidoscope framework.

    Attributes:
        property_name (str): The name of the property field.
        property_description (str): A human-readable description of the property.
        field_type (DataFieldTypeEnum): The data type of the field.
    """

    property_name: str
    property_description: str
    field_type: DataFieldTypeEnum

    def __str__(self):
        return f"{self.property_name}"


class PropertyFieldsService:
    """Service class for managing property fields in Kaleidoscope.

    This service provides methods to retrieve and manage property field definitions
    from the Kaleidoscope API. It uses caching to optimize repeated requests for
    property field data.

    """

    def __init__(self, client: KaleidoscopeClient):
        self._client = client

    @lru_cache
    def get_property_fields(self) -> List[PropertyField]:
        """Retrieve the property fields from the client.

        This method caches its values.

        Returns:
            List[PropertyField]: A list of PropertyField objects representing the property fields in the workspace.

        Note:
            If an exception occurs during the API request, it logs the error,
            clears the cache, and returns an empty list.
        """
        try:
            resp = self._client._get("/property_fields")
            return TypeAdapter(List[PropertyField]).validate_python(resp)
        except Exception as e:
            _logger.error(f"Error fetching property fields: {e}")
            self.get_property_fields.cache_clear()
            return []
