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

import logging
from functools import lru_cache
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import KaleidoscopeClient
from pydantic import TypeAdapter
from typing import List

_logger = logging.getLogger(__name__)


class EntityType(_KaleidoscopeBaseModel):
    """Represents an entity type in the Kaleidoscope system.

    An EntityType defines a classification of entities with associated key fields
    and a slice name for data organization and retrieval.

    Attributes:
        id (str): UUID of the entity type.
        key_field_ids (List[str]): List of field IDs that serve as key fields for this entity type.
        slice_name (str): Name of the entity slice associated with this type.
    """

    key_field_ids: List[str]
    slice_name: str

    def __str__(self):
        return f"{self.slice_name}"

    def get_record_ids(self) -> List[str]:
        """Retrieve a list of record IDs associated with the current entity slice.

        Returns:
            List[str]: A list of record IDs as strings.

        Note:
            If an exception occurs during the API request, it logs the error
            and returns an empty list.
        """
        try:
            resp = self._client._get("/records/search?entity_slice_id=" + self.id)
            return resp
        except Exception as e:
            _logger.error(f"Error fetching record_ids of this entity type: {e}")
            return []


class EntityTypesService:
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

    def __init__(self, client: KaleidoscopeClient):
        self._client = client

    def _create_entity_type(self, data: dict) -> EntityType:
        """Create an EntityType instance from the provided data dictionary.

        Args:
            data (dict): A dictionary containing the data required to instantiate an EntityType.

        Returns:
            EntityType: The validated and initialized EntityType instance.

        Raises:
            ValidationError: If the data could not be validated as an EntityType.
        """
        entity_type = TypeAdapter(EntityType).validate_python(data)
        entity_type._set_client(self._client)
        return entity_type

    def _create_entity_type_list(self, data: list[dict]) -> List[EntityType]:
        """Convert a list of entity type data dictionaries into a list of EntityType objects.

        Args:
            data (list[dict]): The input data representing entity types.

        Returns:
            List[EntityType]: A list of EntityType instances with the client set.

        Raises:
            ValidationError: If the data could not be validated as a list of EntityType objects.
        """
        entity_types = TypeAdapter(List[EntityType]).validate_python(data)

        for entity_type in entity_types:
            entity_type._set_client(self._client)

        return entity_types

    @lru_cache
    def get_types(self) -> List[EntityType]:
        """Retrieve a list of entity types from the client.

        This method caches its values.

        Returns:
            List[EntityType]: A list of EntityType objects created from the response.

        Note:
            If an exception occurs during the API request, it logs the error,
            clears the cache, and returns an empty list.
        """
        try:
            resp = self._client._get("/entity_slices")
            return self._create_entity_type_list(resp)
        except Exception as e:
            _logger.error(f"Error fetching entity types: {e}")
            self.get_types.cache_clear()
            return []

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
            List[EntityType]: A list of EntityType instances where each entity type includes all the given key field IDs.
        """
        entity_types = self.get_types()
        return [
            et
            for et in entity_types
            if all([id in et.key_field_ids for id in key_field_ids])
        ]

    def get_type_exact_keys(self, key_field_ids: List[str]) -> EntityType | None:
        """Retrieve an EntityType object whose key_field_ids exactly match the provided list.

        Args:
            key_field_ids (List[str]): A list of key field IDs to match against entity types.

        Returns:
            (EntityType | None): The matching EntityType object if found; otherwise, None.
        """
        entity_types = self._client.entity_types.get_types()
        return next(
            (et for et in entity_types if set(et.key_field_ids) == set(key_field_ids)),
            None,
        )
