"""
Module for managing entity fields in Kaleidoscope.

This module provides classes and services for working with entity fields, which are the
schema definitions for data stored in the Kaleidoscope system. It includes:

- DataFieldTypeEnum: An enumeration of all supported field types
- EntityField: A model representing a field definition
- EntityFieldsService: A service class for retrieving and creating entity fields

Entity fields can be of two types:

- Key fields: Used to uniquely identify entities
- Data fields: Used to store additional information about entities

The service provides caching mechanisms to minimize API calls and includes error handling
for all network operations.

Classes:
    DataFieldTypeEnum: An enumeration of all supported field types
    EntityField: A model representing a field definition
    EntityFieldsService: A service class for retrieving and creating entity fields

Example:
    ```python
    # Get all key fields
    key_fields = client.entity_fields.get_key_fields()

    # Create or get a data field
    field = client.entity_fields.get_or_create_data_field(
        field_name="temperature",
        field_type=DataFieldTypeEnum.NUMBER
    )
    ```
"""

import logging
from datetime import datetime
from enum import Enum
from functools import lru_cache
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import KaleidoscopeClient
from pydantic import TypeAdapter
from typing import List, Optional, TypeAlias, Union

_logger = logging.getLogger(__name__)


class DataFieldTypeEnum(str, Enum):
    """Enumeration of data field types supported by the system.

    This enum defines all possible types of data fields that can be used in the application.
    Each field type represents a specific kind of data structure and validation rules.

    Attributes:
        TEXT: Plain text field.
        NUMBER: Numeric field for storing numbers.
        QUALIFIED_NUMBER: Numeric field with additional qualifiers or units.
        SMILES_STRING: Field for storing SMILES (Simplified Molecular Input Line Entry System) notation.
        SELECT: Single selection field from predefined options.
        MULTISELECT: Multiple selection field from predefined options.
        MOLFILE: Field for storing molecular structure files.
        RECORD_REFERENCE: Reference to another record by record_id.
        FILE: Generic file attachment field.
        IMAGE: Image file field.
        DATE: Date field.
        URL: Web URL field.
        BOOLEAN: Boolean (true/false) field.
        EMAIL: Email address field.
        PHONE: Phone number field.
        FORMULA: Field for storing formulas or calculated expressions.
        PEOPLE: Field for referencing people/users.
        VOTES: Field for storing vote counts or voting data.
        XY_ARRAY: Field for storing XY coordinate arrays.
        DNA_OLIGO: Field for storing DNA oligonucleotide sequences.
        RNA_OLIGO: Field for storing RNA oligonucleotide sequences.
        PEPTID: Field for storing peptide sequences.
        PLASMID: Field for storing plasmid information.
        GOOGLE_DRIVE: Field for Google Drive file references.
        S3_FILE: Field for AWS S3 file references.
        SNOWFLAKE_QUERY: Field for Snowflake database query references.
    """

    TEXT = "text"
    NUMBER = "number"
    QUALIFIED_NUMBER = "qualified-number"

    SMILES_STRING = "smiles-string"
    SELECT = "select"
    MULTISELECT = "multiselect"
    MOLFILE = "molfile"
    RECORD_REFERENCE = "record-reference"  # value is a record_id
    FILE = "file"
    IMAGE = "image"
    DATE = "date"
    URL = "URL"
    BOOLEAN = "boolean"
    EMAIL = "email"
    PHONE = "phone"
    FORMULA = "formula"
    PEOPLE = "people"
    VOTES = "votes"
    XY_ARRAY = "xy-array"
    DNA_OLIGO = "dna-oligo"
    RNA_OLIGO = "rna-oligo"
    PEPTID = "peptide"
    PLASMID = "plasmid"
    GOOGLE_DRIVE = "google-drive-file"
    S3_FILE = "s3-file"
    SNOWFLAKE_QUERY = "snowflake-query"


class EntityField(_KaleidoscopeBaseModel):
    """Represents a field within an entity in the Kaleidoscope system.

    This class defines the structure and metadata for individual fields that belong
    to an entity, including type information, key status, and optional references.

    Attributes:
        id (str): The UUID of the field.
        created_at (datetime): Timestamp when the field was created.
        is_key (bool): Indicates whether this field is a key field for the entity.
        field_name (str): The name of the field.
        field_type (DataFieldTypeEnum): The data type of the field.
        ref_slice_id (Optional[str]): Optional reference to a slice ID for relational fields.

    Example:
        ```python
        from kalbio.entity_fields import EntityField, DataFieldTypeEnum
        from datetime import datetime

        ef = EntityField(
            id="field_uuid",
            created_at=datetime.utcnow(),
            is_key=True,
            field_name="sample_id",
            field_type=DataFieldTypeEnum.TEXT,
            ref_slice_id=None,
        )
        print(str(ef))  # sample_id
        ```
    """

    created_at: datetime
    is_key: bool
    field_name: str
    field_type: DataFieldTypeEnum
    ref_slice_id: Optional[str]

    def __str__(self):
        return f"{self.field_name}"


EntityFieldIdentifier: TypeAlias = Union[EntityField, str]
"""An Identifier Type for Entity Fields.

An EntityField should be able to be identified by:

* EntityField (object instance)
* UUID (str)
* field_name (str)
"""


class EntityFieldsService:
    """Service class for managing key fields and data fields in Kaleidoscope.

    Entity fields can be of two types:

    - Key fields: Used to uniquely identify entities
    - Data fields: Used to store additional information about entities

    Example:
        ```python
        key_fields = client.entity_fields.get_key_fields()
        temperature = client.entity_fields.get_or_create_data_field(
            field_name="temperature",
            field_type=DataFieldTypeEnum.NUMBER,
        )
        ```
    """

    def __init__(self, client: KaleidoscopeClient):
        self._client = client

    #########################
    #    Public  Methods    #
    #########################

    ##### for Key Fields #####

    @lru_cache
    def get_key_fields(self) -> List[EntityField]:
        """Retrieve key fields and cache the result.

        Returns:
            Key field definitions for the workspace.

        Notes:
            On error, the caches are cleared and an empty list is returned.

        Example:
            ```python
            key_fields = client.entity_fields.get_key_fields()
            ```
        """
        try:
            resp = self._client._get("/key_fields")
            return TypeAdapter(List[EntityField]).validate_python(resp)
        except Exception as e:
            _logger.error(f"Error fetching key fields: {e}")
            self._clear_key_field_caches()
            return []

    def get_key_field_by_id(
        self, identifier: EntityFieldIdentifier
    ) -> EntityField | None:
        """Get a key field by an identifier.

        Args:
            identifier: Key field identifier. Data field identifiers will return None.

                This method will accept and resolve any type of EntityFieldIdentifier.

        Returns:
            Matching key field if found. If not, returns None.

        Example:
            ```python
            key_field = client.entity_fields.get_key_field_by_id("sample_id")
            ```
        """

        id_map = self._get_key_field_id_map()
        field_id = self._resolve_key_field_id(identifier)

        if field_id:
            return id_map.get(field_id, None)
        else:
            return None

    def get_or_create_key_field(self, field_name: str) -> EntityField | None:
        """Retrieve an existing key field by name or create it.

        Args:
            field_name: Name of the key field to fetch or create.

        Returns:
            Existing or newly created key field, or None on error.

        Example:
            ```python
            key_field = client.entity_fields.get_or_create_key_field("sample_id")
            ```
        """
        field = self.get_key_field_by_id(field_name)
        if field is not None:
            return field

        self._clear_key_field_caches()

        try:
            data = {"field_name": field_name}
            resp = self._client._post("/key_fields/", data)
            return EntityField.model_validate(resp)
        except Exception as e:
            _logger.error(f"Error getting or creating key field: {e}")
            return None

    ##### for Data Fields #####

    @lru_cache
    def get_data_fields(self) -> List[EntityField]:
        """Retrieve data fields and cache the result.

        Returns:
            Data field definitions for the workspace.

        Notes:
            On error, the caches are cleared and an empty list is returned.

        Example:
            ```python
            data_fields = client.entity_fields.get_data_fields()
            ```
        """
        try:
            resp = self._client._get("/data_fields")
            return TypeAdapter(List[EntityField]).validate_python(resp)
        except Exception as e:
            _logger.error(f"Error fetching data fields: {e}")
            self._clear_data_field_caches()
            return []

    def get_data_field_by_id(
        self, identifier: EntityFieldIdentifier
    ) -> EntityField | None:
        """Get a data field by identifier.

        Args:
            identifier: Identifier for a data field. Key field identifiers return None.

                This method will accept and resolve any type of EntityFieldIdentifier.


        Returns:
            Matching data field, if found.

        Example:
            ```python
            data_field = client.entity_fields.get_data_field_by_id("temperature")
            ```
        """

        id_map = self._get_data_field_id_map()
        field_id = self._resolve_data_field_id(identifier)

        if field_id:
            return id_map.get(field_id, None)
        else:
            return None

    def get_or_create_data_field(
        self, field_name: str, field_type: DataFieldTypeEnum
    ) -> EntityField | None:
        """Create a data field or return the existing one.

        Args:
            field_name: Name of the data field to create or retrieve.
            field_type: Data field type.

        Returns:
            Existing or newly created data field, or None on error.

        Example:
            ```python
            concentration = client.entity_fields.get_or_create_data_field(
                field_name="concentration",
                field_type=DataFieldTypeEnum.NUMBER,
            )
            ```
        """
        field = self.get_data_field_by_id(field_name)
        if field is not None:
            return field

        self._clear_data_field_caches()

        try:
            data: dict = {
                "field_name": field_name,
                "field_type": field_type.value,
                "attrs": {},
            }
            resp = self._client._post("/data_fields/", data)
            return EntityField.model_validate(resp)
        except Exception as e:
            _logger.error(f"Error getting or creating data field: {e}")
            return None

    #########################
    #    Private Methods    #
    #########################

    ##### for Key Fields #####

    @lru_cache
    def _get_key_field_id_map(self) -> dict[str, EntityField]:
        """Map key field UUIDs to their entities.

        Returns:
            UUID-to-EntityField mapping for key fields.
        """
        return {field.id: field for field in self.get_key_fields()}

    @lru_cache
    def _get_key_field_name_map(self) -> dict[str, EntityField]:
        """Map key field names to their entities.

        Returns:
            field_name-to-EntityField mapping for key fields.
        """
        return {field.field_name: field for field in self.get_key_fields()}

    def _resolve_key_field_id(self, identifier: EntityFieldIdentifier) -> str | None:
        """Resolve a key field identifier to its ID.

        Args:
            identifier: Key field object, UUID, or field name.

        Returns:
            Field ID if resolved; otherwise None.
        """
        if isinstance(identifier, EntityField):
            if identifier.is_key:
                return identifier.id
            else:
                _logger.error(f"Key field with identifier '{identifier}' not found.")
                return None

        id_map = self._get_key_field_id_map()
        if identifier in id_map:  # try to find by uuid
            return identifier

        key_field = self._get_key_field_name_map().get(identifier, None)
        if key_field:  # try to find by name
            return key_field.id

        _logger.error(f"Key field with identifier '{identifier}' not found.")
        return None

    def _clear_key_field_caches(self) -> None:
        """Clear caches for key fields.

        Call when a key field is added, removed, or changed.
        """
        self.get_key_fields.cache_clear()
        self._get_key_field_id_map.cache_clear()
        self._get_key_field_name_map.cache_clear()

    ##### for Data Fields #####

    @lru_cache
    def _get_data_field_id_map(self) -> dict[str, EntityField]:
        """Map data field UUIDs to their entities.

        Returns:
            UUID-to-EntityField mapping for data fields.
        """
        return {field.id: field for field in self.get_data_fields()}

    @lru_cache
    def _get_data_field_name_map(self) -> dict[str, EntityField]:
        """Map data field names to their entities.

        Returns:
            field_name-to-EntityField mapping for data fields.
        """
        return {field.field_name: field for field in self.get_data_fields()}

    def _resolve_data_field_id(self, identifier: EntityFieldIdentifier) -> str | None:
        """Resolve a data field identifier to its ID.

        Args:
            identifier: Data field object, UUID, or field name.

        Returns:
            Field ID if resolved; otherwise None.
        """
        if isinstance(identifier, EntityField):
            if not identifier.is_key:
                return identifier.id
            else:
                _logger.error(f"Data field with identifier '{identifier}' not found.")
                return None

        # Check if it's already an ID
        id_map = self._get_data_field_id_map()
        if identifier in id_map:
            return identifier

        # Try to find by name
        data_field = self._get_data_field_name_map().get(identifier, None)
        if data_field:
            return data_field.id

        _logger.error(f"Data field with identifier '{identifier}' not found.")
        return None

    def _clear_data_field_caches(self) -> None:
        """Clear caches for data fields."""
        self.get_data_fields.cache_clear()
        self._get_data_field_id_map.cache_clear()
        self._get_data_field_name_map.cache_clear()
