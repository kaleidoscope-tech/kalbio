"""
Module for managing entity fields in Kaleidoscope.

This module provides classes and services for working with entity fields, which are the
schema definitions for data stored in the Kaleidoscope system. It includes:

- DataFieldTypeEnum: An enumeration of all supported field types
- EntityField: Base class for a field definition
- KeyField: Subclass for key fields, with key-field-only update operations
- DataField: Subclass for data fields, with data-field-only update operations
- EntityFieldsService: Service class for retrieving and creating entity fields

Entity fields can be of two types:

- Key fields: Used to uniquely identify entities
- Data fields: Used to store additional information about entities

The service provides caching mechanisms to minimize API calls and includes error handling
for all network operations.

Classes:
    DataFieldTypeEnum: An enumeration of all supported field types
    FormatEnforcementEnum: How a key field's format/regex is enforced
    EntityFieldRoleEnum: Special roles a key field can play
    ValueAggregationTypeEnum: Aggregation types for data field display
    LookupDisplayOperationScopeEnum: Scope for lookup display operations
    EntityField: Base class for entity field definitions
    KeyField: Concrete key field with `update()` for identifier settings
    DataField: Concrete data field with `update()` for display/archival settings
    EntityFieldsService: Service for retrieving and creating entity fields

Example:
    ```python
    # Get all key fields
    key_fields = client.entity_fields.get_key_fields()

    # Create or get a data field
    field = client.entity_fields.get_or_create_data_field(
        field_name="temperature",
        field_type=DataFieldTypeEnum.NUMBER
    )

    # Update a key field's regex format
    key_field = client.entity_fields.get_or_create_key_field("sample_id")
    key_field.update(regex_format=r"^SMP-\\d{6}$")
    ```
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from kalbio._base import _BaseService
from kalbio._cache import cached
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import KalbioResponseError, _require_response_body
from typing import Final, List, Optional, TypeAlias, Union

_logger = logging.getLogger(__name__)


class _UnsetType:
    """Sentinel singleton used to distinguish "do not update" from "set to None".

    The update methods accept many optional arguments. For nullable fields like
    `regex_format`, callers need to be able to express both "leave the existing
    value alone" and "clear the existing value to None". Using `UNSET` as the
    default for unspecified arguments lets us tell the two apart.
    """

    _instance: Optional["_UnsetType"] = None

    def __new__(cls) -> "_UnsetType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET: Final[_UnsetType] = _UnsetType()
"""Sentinel value indicating an update argument was not provided.

Use this to leave a field unchanged when calling `KeyField.update()` or
`DataField.update()`. Pass `None` explicitly to clear a nullable field.
"""


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
        MIXTURE: Field for storing mixture compositions.
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
        STATUS: Field for tracking workflow/lifecycle status values.
        RXN: Field for storing chemical reaction notation.
        PROTEIN_STRUCTURE: Field for storing protein structure data.
    """

    TEXT = "text"
    NUMBER = "number"
    QUALIFIED_NUMBER = "qualified-number"

    SMILES_STRING = "smiles-string"
    SELECT = "select"
    MULTISELECT = "multiselect"
    MOLFILE = "molfile"
    RECORD_REFERENCE = "record-reference"  # value is a record_id
    MIXTURE = "mixture"
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
    STATUS = "status"
    RXN = "rxn"
    PROTEIN_STRUCTURE = "protein-structure"


class FormatEnforcementEnum(str, Enum):
    """How a key field's serial format / regex pattern is enforced on values.

    Attributes:
        SUGGEST: Suggest the format but do not block non-matching values.
        ENFORCE_ONLY: Reject values that do not match the format.
        GENERATE: Auto-generate the next value from the configured serial format.
    """

    SUGGEST = "suggest"
    ENFORCE_ONLY = "enforce_only"
    GENERATE = "generate"


class EntityFieldRoleEnum(str, Enum):
    """Special role assigned to a key field.

    Attributes:
        REGISTERED_ENTITY: Marks the key field as the workspace's registered-entity identifier.
    """

    REGISTERED_ENTITY = "registered_entity"


class ValueAggregationTypeEnum(str, Enum):
    """How aggregated values are summarized for display on data fields.

    Attributes:
        LATEST: Most recently recorded value.
        LIST: All values, as a list.
        EARLIEST: Earliest recorded value.
        RANGE: Range (min - max).
        MEAN: Arithmetic mean.
        MEDIAN: Median.
        MINIMUM: Minimum value.
        MAXIMUM: Maximum value.
    """

    LATEST = "latest"
    LIST = "list"
    EARLIEST = "earliest"
    RANGE = "range"
    MEAN = "mean"
    MEDIAN = "median"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"


class LookupDisplayOperationScopeEnum(str, Enum):
    """Scope used when displaying a lookup data field's operation values.

    Attributes:
        ALL: Include values from all related operations.
        CHILD: Include only child operation values.
        PARENT: Include only parent operation values.
    """

    ALL = "all"
    CHILD = "child"
    PARENT = "parent"


class EntityField(_KaleidoscopeBaseModel):
    """Base class for fields within an entity in the Kaleidoscope system.

    Concrete instances are returned as either `KeyField` (when `is_key` is True)
    or `DataField` (when `is_key` is False). Each subclass exposes its own
    `update()` method scoped to the properties that are valid for that field
    role — for example, only `KeyField` allows updating `regex_format` and
    serial-format settings, while only `DataField` allows updating display
    aggregation and archival flags.

    Attributes:
        id (str): The UUID of the field.
        created_at (datetime): Timestamp when the field was created.
        is_key (bool): Whether this field is a key field for the entity.
        field_name (str): The name of the field.
        field_description (str): Human-readable description of the field. Empty
            string if unset.
        field_examples (str): Example values for the field. Empty string if unset.
        field_type (DataFieldTypeEnum): The data type of the field.
        ref_slice_id (Optional[str]): Reference to a slice ID for relational fields.
        regex_format (Optional[str]): Regex pattern used to validate key field values
            (only meaningful on key fields).

    Example:
        ```python
        from kalbio.entity_fields import KeyField, DataField

        # The service returns the appropriate subclass.
        key_field = client.entity_fields.get_or_create_key_field("sample_id")
        assert isinstance(key_field, KeyField)
        ```
    """

    created_at: Optional[datetime] = None
    is_key: Optional[bool] = None
    field_name: Optional[str] = None
    field_description: str = ""
    field_examples: str = ""
    field_type: Optional[str] = None
    ref_slice_id: Optional[str] = None
    regex_format: Optional[str] = None

    def __str__(self):
        return f"{self.field_name}"


class KeyField(EntityField):
    """A key field — uniquely identifies entities in the workspace.

    Key fields support updating identifier-related settings such as
    `regex_format`, serial-format configuration, and the field's role.

    Example:
        ```python
        key_field = client.entity_fields.get_or_create_key_field("sample_id")
        key_field.update(
            regex_format=r"^SMP-\\d{6}$",
            format_enforcement=FormatEnforcementEnum.ENFORCE_ONLY,
        )
        ```
    """

    is_key: bool = True

    def update(
        self,
        *,
        field_name: Union[str, _UnsetType] = UNSET,
        field_description: Union[str, _UnsetType] = UNSET,
        field_examples: Union[str, _UnsetType] = UNSET,
        regex_format: Union[Optional[str], _UnsetType] = UNSET,
        serial_format_prefix: Union[Optional[str], _UnsetType] = UNSET,
        serial_format_padding: Union[Optional[int], _UnsetType] = UNSET,
        format_enforcement: Union[Optional[FormatEnforcementEnum], _UnsetType] = UNSET,
        show_format_warning: Union[bool, _UnsetType] = UNSET,
        initial_counter_value: Union[int, _UnsetType] = UNSET,
        role: Union[Optional[EntityFieldRoleEnum], _UnsetType] = UNSET,
    ) -> "KeyField":
        """Update one or more configurable properties of this key field.

        Only the arguments you pass are sent to the server. To clear a
        nullable field (e.g. remove an existing regex), pass `None`
        explicitly. Omitted arguments default to `UNSET` and are left
        unchanged.

        Args:
            field_name: New name for the field.
            field_description: Human-readable description of the field
                (max 500 characters). Pass an empty string to clear.
            field_examples: Example values for the field (max 500 characters).
                Pass an empty string to clear.
            regex_format: Regex pattern to enforce on key values; pass None to clear.
            serial_format_prefix: Prefix for auto-generated identifiers; pass None to clear.
            serial_format_padding: Zero-padding width for the serial counter; pass None to clear.
            format_enforcement: How the format is enforced; pass None to clear.
            show_format_warning: Whether to surface a UI warning on format mismatches.
            initial_counter_value: Starting value for the serial counter.
            role: Special role for this key field; pass None to clear.

        Returns:
            The updated `KeyField` (also reflected on `self`).

        Raises:
            KalbioAPIError: If the API request fails.
            KalbioResponseError: If the server returns no usable body.

        Example:
            ```python
            # Add a regex pattern and enforce it
            key_field.update(
                regex_format=r"^SMP-\\d{6}$",
                format_enforcement=FormatEnforcementEnum.ENFORCE_ONLY,
            )

            # Clear an existing regex
            key_field.update(regex_format=None)
            ```
        """
        body: dict = {}
        if not isinstance(field_name, _UnsetType):
            body["field_name"] = field_name
        if not isinstance(field_description, _UnsetType):
            body["field_description"] = field_description
        if not isinstance(field_examples, _UnsetType):
            body["field_examples"] = field_examples
        if not isinstance(regex_format, _UnsetType):
            body["regex_format"] = regex_format
        if not isinstance(serial_format_prefix, _UnsetType):
            body["serial_format_prefix"] = serial_format_prefix
        if not isinstance(serial_format_padding, _UnsetType):
            body["serial_format_padding"] = serial_format_padding
        if not isinstance(format_enforcement, _UnsetType):
            body["format_enforcement"] = (
                format_enforcement.value
                if isinstance(format_enforcement, FormatEnforcementEnum)
                else format_enforcement
            )
        if not isinstance(show_format_warning, _UnsetType):
            body["show_format_warning"] = show_format_warning
        if not isinstance(initial_counter_value, _UnsetType):
            body["initial_counter_value"] = initial_counter_value
        if not isinstance(role, _UnsetType):
            body["role"] = (
                role.value if isinstance(role, EntityFieldRoleEnum) else role
            )

        if not body:
            return self

        resp = self._client._put(f"/key_fields/{self.id}", body)
        if resp is None or "resource" not in resp:
            raise KalbioResponseError("PUT", f"/key_fields/{self.id}", resp)

        # PUT /key_fields returns the updated field under "resource"; the POST
        # create path instead returns the bare field object.
        updated = KeyField.model_validate(resp["resource"])
        _copy_fields(updated, self)
        self._client.entity_fields._clear_key_field_caches()
        return self


class DataField(EntityField):
    """A data field — stores additional information about entities.

    Data fields support updating display, aggregation, archival, and
    type-related settings.

    Example:
        ```python
        data_field = client.entity_fields.get_or_create_data_field(
            "temperature", DataFieldTypeEnum.NUMBER,
        )
        data_field.update(
            display_aggregation_type=ValueAggregationTypeEnum.MEAN,
            is_archived=False,
        )
        ```
    """

    is_key: bool = False

    def update(
        self,
        *,
        field_name: Union[str, _UnsetType] = UNSET,
        field_description: Union[str, _UnsetType] = UNSET,
        field_examples: Union[str, _UnsetType] = UNSET,
        is_archived: Union[bool, _UnsetType] = UNSET,
        is_readonly: Union[bool, _UnsetType] = UNSET,
        display_aggregation_type: Union[
            Optional[ValueAggregationTypeEnum], _UnsetType
        ] = UNSET,
        display_includes_sub_records: Union[bool, _UnsetType] = UNSET,
        display_includes_operations: Union[bool, _UnsetType] = UNSET,
        lookup_display_aggregation_type: Union[
            Optional[ValueAggregationTypeEnum], _UnsetType
        ] = UNSET,
        lookup_display_includes_sub_records: Union[bool, _UnsetType] = UNSET,
        lookup_display_operation_scope: Union[
            LookupDisplayOperationScopeEnum, _UnsetType
        ] = UNSET,
        attrs: Union[dict, _UnsetType] = UNSET,
    ) -> "DataField":
        """Update one or more configurable properties of this data field.

        Only the arguments you pass are sent to the server. Omitted arguments
        default to `UNSET` and are left unchanged. For nullable display
        aggregation fields, pass `None` explicitly to clear them.

        Args:
            field_name: New name for the field.
            field_description: Human-readable description of the field
                (max 500 characters). Pass an empty string to clear.
            field_examples: Example values for the field (max 500 characters).
                Pass an empty string to clear.
            is_archived: Whether the field is archived.
            is_readonly: Whether the field is read-only.
            display_aggregation_type: How aggregated values are displayed; pass None to clear.
            display_includes_sub_records: Whether to include sub-records in the display value.
            display_includes_operations: Whether to include operations in the display value.
            lookup_display_aggregation_type: Aggregation type for lookup display; pass None to clear.
            lookup_display_includes_sub_records: Whether lookups include sub-records.
            lookup_display_operation_scope: Scope of operations included in lookup displays.
            attrs: Type-specific attributes JSON for this field.

        Returns:
            The updated `DataField` (also reflected on `self`).

        Raises:
            KalbioAPIError: If the API request fails.
            KalbioResponseError: If the server returns no usable body.

        Example:
            ```python
            # Archive a field
            data_field.update(is_archived=True)

            # Set how aggregated values are displayed
            data_field.update(
                display_aggregation_type=ValueAggregationTypeEnum.MEAN,
                display_includes_sub_records=True,
            )
            ```
        """
        body: dict = {}
        if not isinstance(field_name, _UnsetType):
            body["field_name"] = field_name
        if not isinstance(field_description, _UnsetType):
            body["field_description"] = field_description
        if not isinstance(field_examples, _UnsetType):
            body["field_examples"] = field_examples
        if not isinstance(is_archived, _UnsetType):
            body["is_archived"] = is_archived
        if not isinstance(is_readonly, _UnsetType):
            body["is_readonly"] = is_readonly
        if not isinstance(display_aggregation_type, _UnsetType):
            body["display_aggregation_type"] = (
                display_aggregation_type.value
                if isinstance(display_aggregation_type, ValueAggregationTypeEnum)
                else display_aggregation_type
            )
        if not isinstance(display_includes_sub_records, _UnsetType):
            body["display_includes_sub_records"] = display_includes_sub_records
        if not isinstance(display_includes_operations, _UnsetType):
            body["display_includes_operations"] = display_includes_operations
        if not isinstance(lookup_display_aggregation_type, _UnsetType):
            body["lookup_display_aggregation_type"] = (
                lookup_display_aggregation_type.value
                if isinstance(lookup_display_aggregation_type, ValueAggregationTypeEnum)
                else lookup_display_aggregation_type
            )
        if not isinstance(lookup_display_includes_sub_records, _UnsetType):
            body["lookup_display_includes_sub_records"] = (
                lookup_display_includes_sub_records
            )
        if not isinstance(lookup_display_operation_scope, _UnsetType):
            body["lookup_display_operation_scope"] = (
                lookup_display_operation_scope.value
                if isinstance(
                    lookup_display_operation_scope, LookupDisplayOperationScopeEnum
                )
                else lookup_display_operation_scope
            )
        if not isinstance(attrs, _UnsetType):
            body["attrs"] = attrs

        if not body:
            return self

        resp = self._client._put(f"/data_fields/{self.id}", body)
        if resp is None or "resource" not in resp:
            raise KalbioResponseError("PUT", f"/data_fields/{self.id}", resp)

        # PUT /data_fields response shape is { resource: { field, validation }, event },
        # unlike PUT /key_fields (bare field under "resource") and the POST create
        # path (bare field object).
        field_payload = resp["resource"].get("field", resp["resource"])
        updated = DataField.model_validate(field_payload)
        _copy_fields(updated, self)
        self._client.entity_fields._clear_data_field_caches()
        return self


def _copy_fields(source: EntityField, target: EntityField) -> None:
    """Copy mutable model fields from `source` to `target` in place.

    Declared fields and `extra="allow"` fields (which live in
    `__pydantic_extra__`) are both copied, so server-added attributes stay in
    sync on `target` after an update.
    """
    for field_name in source.__class__.model_fields.keys():
        setattr(target, field_name, getattr(source, field_name))
    for extra_name, extra_value in (source.__pydantic_extra__ or {}).items():
        setattr(target, extra_name, extra_value)


EntityFieldIdentifier: TypeAlias = Union[EntityField, str]
"""An Identifier Type for Entity Fields.

An EntityField should be able to be identified by:

* EntityField (object instance) — also accepts `KeyField` and `DataField`
* UUID (str)
* field_name (str)
"""


class EntityFieldsService(_BaseService):
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

    #########################
    #    Public  Methods    #
    #########################

    ##### for Key Fields #####

    @cached
    def get_key_fields(self) -> List[KeyField]:
        """Retrieve key fields and cache the result.

        Returns:
            Key field definitions for the workspace.

        Raises:
            KalbioAPIError: If the API request fails.
            KalbioResponseError: If the endpoint returns no usable body.

        Example:
            ```python
            key_fields = client.entity_fields.get_key_fields()
            ```
        """
        resp = _require_response_body(
            "GET", "/key_fields", self._client._get("/key_fields")
        )
        return KeyField._list_from_api(resp, self._client)

    def get_key_field_by_id(
        self, identifier: EntityFieldIdentifier
    ) -> KeyField | None:
        """Get a key field by any identifier.

        Despite the ``_by_id`` name, this accepts and resolves any
        `EntityFieldIdentifier`: a UUID, a `field_name`, or a `KeyField`/`EntityField`
        object.

        Args:
            identifier: Key field UUID, field name, or object. Identifiers that
                resolve to a data field return None.

        Returns:
            Matching key field if found. If not, returns None.

        Example:
            ```python
            key_field = client.entity_fields.get_key_field_by_id("sample_id")
            ```
        """

        field_id = self._resolve_key_field_id(identifier)
        if field_id is None:
            return None
        return self._get_key_field_id_map().get(field_id, None)

    def get_or_create_key_field(self, field_name: str) -> KeyField:
        """Retrieve an existing key field by name or create it.

        Args:
            field_name: Name of the key field to fetch or create.

        Returns:
            Existing or newly created key field.

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            key_field = client.entity_fields.get_or_create_key_field("sample_id")
            ```
        """
        field = self.get_key_field_by_id(field_name)
        if field is not None:
            return field

        data = {"field_name": field_name}
        # POST /key_fields returns the bare field object.
        resp = _require_response_body(
            "POST", "/key_fields/", self._client._post("/key_fields/", data)
        )
        field = KeyField._from_api(resp, self._client)
        self._clear_key_field_caches()
        return field

    ##### for Data Fields #####

    @cached
    def get_data_fields(self) -> List[DataField]:
        """Retrieve data fields and cache the result.

        Returns:
            Data field definitions for the workspace.

        Raises:
            KalbioAPIError: If the API request fails.
            KalbioResponseError: If the endpoint returns no usable body.

        Example:
            ```python
            data_fields = client.entity_fields.get_data_fields()
            ```
        """
        resp = _require_response_body(
            "GET", "/data_fields", self._client._get("/data_fields")
        )
        return DataField._list_from_api(resp, self._client)

    def get_data_field_by_id(
        self, identifier: EntityFieldIdentifier
    ) -> DataField | None:
        """Get a data field by any identifier.

        Despite the ``_by_id`` name, this accepts and resolves any
        `EntityFieldIdentifier`: a UUID, a `field_name`, or a `DataField`/`EntityField`
        object.

        Args:
            identifier: Data field UUID, field name, or object. Identifiers that
                resolve to a key field return None.

        Returns:
            Matching data field, if found.

        Example:
            ```python
            data_field = client.entity_fields.get_data_field_by_id("temperature")
            ```
        """

        field_id = self._resolve_data_field_id(identifier)
        if field_id is None:
            return None
        return self._get_data_field_id_map().get(field_id, None)

    def get_or_create_data_field(
        self, field_name: str, field_type: DataFieldTypeEnum
    ) -> DataField:
        """Create a data field or return the existing one.

        Args:
            field_name: Name of the data field to create or retrieve.
            field_type: Data field type.

        Returns:
            Existing or newly created data field.

        Raises:
            KalbioAPIError: If the API request fails.

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

        data: dict = {
            "field_name": field_name,
            "field_type": field_type.value,
            "attrs": {},
        }
        # POST /data_fields returns the bare field object.
        resp = _require_response_body(
            "POST", "/data_fields/", self._client._post("/data_fields/", data)
        )
        field = DataField._from_api(resp, self._client)
        self._clear_data_field_caches()
        return field

    #########################
    #    Private Methods    #
    #########################

    ##### for Key Fields #####

    @cached
    def _get_key_field_id_map(self) -> dict[str, KeyField]:
        """Map key field UUIDs to their entities.

        Returns:
            UUID-to-KeyField mapping for key fields.
        """
        return {field.id: field for field in self.get_key_fields()}

    @cached
    def _get_key_field_name_map(self) -> dict[str, KeyField]:
        """Map key field names to their entities.

        Returns:
            field_name-to-KeyField mapping for key fields.
        """
        return {
            field.field_name: field
            for field in self.get_key_fields()
            if field.field_name is not None
        }

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
                _logger.debug(f"Key field with identifier '{identifier}' not found.")
                return None

        id_map = self._get_key_field_id_map()
        if identifier in id_map:  # try to find by uuid
            return identifier

        key_field = self._get_key_field_name_map().get(identifier, None)
        if key_field:  # try to find by name
            return key_field.id

        _logger.debug(f"Key field with identifier '{identifier}' not found.")
        return None

    def _clear_key_field_caches(self) -> None:
        """Clear caches for key fields.

        Call when a key field is added, removed, or changed.
        """
        self.get_key_fields.cache_clear()
        self._get_key_field_id_map.cache_clear()
        self._get_key_field_name_map.cache_clear()

    ##### for Data Fields #####

    @cached
    def _get_data_field_id_map(self) -> dict[str, DataField]:
        """Map data field UUIDs to their entities.

        Returns:
            UUID-to-DataField mapping for data fields.
        """
        return {field.id: field for field in self.get_data_fields()}

    @cached
    def _get_data_field_name_map(self) -> dict[str, DataField]:
        """Map data field names to their entities.

        Returns:
            field_name-to-DataField mapping for data fields.
        """
        return {
            field.field_name: field
            for field in self.get_data_fields()
            if field.field_name is not None
        }

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
                _logger.debug(f"Data field with identifier '{identifier}' not found.")
                return None

        # Check if it's already an ID
        id_map = self._get_data_field_id_map()
        if identifier in id_map:
            return identifier

        # Try to find by name
        data_field = self._get_data_field_name_map().get(identifier, None)
        if data_field:
            return data_field.id

        _logger.debug(f"Data field with identifier '{identifier}' not found.")
        return None

    def _clear_data_field_caches(self) -> None:
        """Clear caches for data fields."""
        self.get_data_fields.cache_clear()
        self._get_data_field_id_map.cache_clear()
        self._get_data_field_name_map.cache_clear()
