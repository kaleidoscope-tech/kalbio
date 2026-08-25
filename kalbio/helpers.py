"""Module of helper methods for the Kaleidoscope Python Client.

This module provides utility functions for data transformation and other helper tasks.
Currently, it includes functionality to map field IDs to human-readable field names.

Functions:
    export_data: Transforms data records by mapping field IDs to field names.

Example:
    ```python
    from kalbio.helpers import export_data

    # Transform raw data with field IDs to data with field names
    processed_data = export_data(client, raw_data)
    ```
"""

import logging
from collections import Counter

from kalbio.client import KaleidoscopeClient
from typing import Any, Dict, List

_logger = logging.getLogger(__name__)


def export_data(
    client: KaleidoscopeClient, data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Rename each record's field-id keys to their human-readable field names.

    Each input record maps field IDs to values; each output record maps the
    corresponding field names to the same values. Field metadata is retrieved
    through the KaleidoscopeClient. A field ID with no matching field, or whose
    field has no name, keeps the original ID as its key.

    Args:
        client (KaleidoscopeClient): The client instance containing field metadata used
            to map field IDs to field names.
        data (List[Dict[str, Any]]): A list of records, each represented as a dictionary
            mapping field IDs to their values.

    Returns:
        (List[Dict[str, Any]]): A list of transformed records, each represented as a dictionary
            mapping field names (as keys) to their values.
    """
    key_fields = client.entity_fields.get_key_fields()
    data_fields = client.entity_fields.get_data_fields()

    id_to_field = {item.id: item for item in key_fields + data_fields}

    # Field names are not unique across the key-field and data-field namespaces.
    # When two field ids share a name, renaming both would collapse them into one
    # output key and drop a value, so ambiguous names keep the raw field id.
    name_counts = Counter(
        field.field_name for field in id_to_field.values() if field.field_name
    )
    colliding = sorted(name for name, count in name_counts.items() if count > 1)
    if colliding:
        _logger.warning(
            "export_data: field names %s map to multiple field ids; "
            "keeping the raw field id for those columns to avoid data loss",
            colliding,
        )

    def _output_key(field_id: str) -> str:
        field = id_to_field.get(field_id)
        name = field.field_name if field else None
        if name and name_counts[name] == 1:
            return name
        return field_id

    return [
        {_output_key(field_id): value for field_id, value in record.items()}
        for record in data
    ]
