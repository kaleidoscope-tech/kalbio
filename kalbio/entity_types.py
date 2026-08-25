"""
Entity type management module for the Kaleidoscope system.

This module provides classes and services for working with entity types in Kaleidoscope.
Entity types define classifications of entities with associated key fields and slice names
for data organization and retrieval.

Classes:
    EntityType: Represents a single entity type with its configuration and key fields.
    EntityTypesService: Service class for managing and querying entity types.

Example:
    ```python
    # get all entity types
    all_types = client.entity_types.get_types()

    # get a specific type by name
    specific_type = client.entity_types.get_type_by_name("my_entity")
    ```
"""

from kalbio._base import _BaseService
from kalbio._cache import cached
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import _require_response_body
from pydantic import Field
from typing import List, Optional



class EntityType(_KaleidoscopeBaseModel):
    """Represents an entity type in the Kaleidoscope system.

    An EntityType defines a classification of entities with associated key fields
    and a slice name for data organization and retrieval.

    Attributes:
        id (str): UUID of the entity type.
        key_field_ids (List[str]): List of field IDs that serve as key fields for this entity type.
        slice_name (str): Name of the entity slice associated with this type.
    """

    key_field_ids: List[str] = Field(default_factory=list)
    slice_name: Optional[str] = None

    def __str__(self):
        return f"{self.slice_name}"

    def get_record_ids(self) -> List[str]:
        """Retrieve a list of record IDs associated with the current entity slice.

        Returns:
            List[str]: A list of record IDs as strings. Empty if the slice has
            no records.
        """
        return self._client.records.search_records(entity_slice_id=self.id)


class EntityTypesService(_BaseService):
    """Service class for managing and retrieving entity types from the Kaleidoscope API.

    This service provides methods to fetch, filter, and search entity types based on
    various criteria such as name and key field IDs. It handles the conversion of raw
    API responses into validated EntityType objects.

    Example:
        ```python
        # get all entity types
        all_types = client.entity_types.get_types()

        # get a specific type by name
        specific_type = client.entity_types.get_type_by_name("my_entity")
        ```
    """

    @cached
    def get_types(self) -> List[EntityType]:
        """Retrieve a list of entity types from the client.

        This method caches its values.

        Returns:
            List[EntityType]: A list of EntityType objects created from the response.

        Raises:
            KalbioAPIError: If the API request fails.
            KalbioResponseError: If the endpoint returns no usable body.
        """
        resp = _require_response_body(
            "GET", "/entity_slices", self._client._get("/entity_slices")
        )
        return EntityType._list_from_api(resp, self._client)

    def get_type_by_name(self, name: str) -> EntityType | None:
        """Retrieve an EntityType object from the list of entity types by its name.

        Args:
            name (str): The name of the entity type to search for.

        Returns:
            (EntityType | None): The EntityType object with the matching name if found, otherwise None.
        """
        entity_types = self.get_types()
        return next(
            (et for et in entity_types if et.slice_name == name),
            None,
        )

    def get_types_with_key_fields(self, key_field_ids: List[str]) -> List[EntityType]:
        """Return a list of EntityType objects that contain all the specified key field IDs.

        Args:
            key_field_ids (List[str]): A list of key field IDs to filter entity types.

        Returns:
            List[EntityType]: A list of EntityType instances where each entity type includes all the given key field IDs. Empty list when no key field IDs are given.
        """
        if not key_field_ids:
            return []
        required = set(key_field_ids)
        return [et for et in self.get_types() if required.issubset(et.key_field_ids)]

    def get_type_exact_keys(self, key_field_ids: List[str]) -> EntityType | None:
        """Retrieve an EntityType object whose key_field_ids exactly match the provided list.

        Args:
            key_field_ids (List[str]): A list of key field IDs to match against entity types.

        Returns:
            (EntityType | None): The matching EntityType object if found; otherwise, None.
        """
        entity_types = self.get_types()
        return next(
            (et for et in entity_types if set(et.key_field_ids) == set(key_field_ids)),
            None,
        )
