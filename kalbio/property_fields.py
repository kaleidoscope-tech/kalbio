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

from kalbio._base import _BaseService
from kalbio._cache import cached
from typing import List, Optional
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import _require_response_body



class PropertyField(_KaleidoscopeBaseModel):
    """Represents a property field in the Kaleidoscope system.

    A PropertyField defines a named property with a description and data type,
    used to structure and validate data within the Kaleidoscope framework.

    Attributes:
        property_name (str): The name of the property field.
        property_description (str): A human-readable description of the property.
        field_type (DataFieldTypeEnum): The data type of the field.
    """

    property_name: Optional[str] = None
    property_description: Optional[str] = None
    field_type: Optional[str] = None

    def __str__(self):
        return f"{self.property_name}"


class PropertyFieldsService(_BaseService):
    """Service class for managing property fields in Kaleidoscope.

    This service provides methods to retrieve and manage property field definitions
    from the Kaleidoscope API. It uses caching to optimize repeated requests for
    property field data.

    """

    @cached
    def get_property_fields(self) -> List[PropertyField]:
        """Retrieve the property fields from the client.

        This method caches its values.

        Returns:
            List[PropertyField]: A list of PropertyField objects representing the property fields in the workspace.

        Raises:
            KalbioAPIError: If the API request fails.
            KalbioResponseError: If the endpoint returns no usable body.
        """
        resp = _require_response_body(
            "GET", "/property_fields", self._client._get("/property_fields")
        )
        return PropertyField._list_from_api(resp, self._client)
