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

from kalbio.client import KaleidoscopeClient
from typing import Any, Dict, List


def export_data(
    client: KaleidoscopeClient, data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Transform a list of data records by mapping field IDs to their corresponding field names.

    This function takes raw data records where keys are field IDs and converts them into
    records where keys are human-readable field names. It uses the KaleidoscopeClient to
    retrieve field metadata and perform the mapping. If a field ID is not found in the
    metadata, the original ID is preserved as the key.

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
    return [
        {
            (id_to_field[id].field_name if id in id_to_field else id): value
            for id, value in record.items()
        }
        for record in data
    ]
