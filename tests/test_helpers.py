"""
Tests for the export_data helper function.
This module contains tests that verify the export_data function correctly:
- Converts field IDs to field names using the KaleidoscopeClient
- Handles key fields and data fields appropriately
- Preserves unknown field IDs
- Maintains value types during conversion
- Handles edge cases like empty lists

The tests use pytest fixtures and mocking to isolate the export_data function
from external dependencies.
"""

from typing import Any, Dict, List
from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient
from kalbio.entity_fields import EntityField
from kalbio.helpers import export_data
from tests.conftest import _MockData


# ==================== Helper Functions ====================


def test_export_data(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that export_data():
    - Returns a list of records, each represented as a dictionary mapping field names to their values
    - Converts field IDs to field names using client.Fields methods
    """
    # Create mock key fields and data fields
    key_fields_data = _MockData.KEY_FIELDS
    data_fields_data = _MockData.DATA_FIELDS

    # Mock the Fields service methods
    mock_get_key_fields = mocker.patch.object(
        kal_client_mock.entity_fields,
        "get_key_fields",
        return_value=[EntityField.model_validate(f) for f in key_fields_data],
    )

    mock_get_data_fields = mocker.patch.object(
        kal_client_mock.entity_fields,
        "get_data_fields",
        return_value=[EntityField.model_validate(f) for f in data_fields_data],
    )

    # Create test data with field IDs as keys
    field_id_1 = key_fields_data[0]["id"]
    field_name_1 = key_fields_data[0]["field_name"]

    field_id_2 = data_fields_data[0]["id"]
    field_name_2 = data_fields_data[0]["field_name"]

    input_data = [
        {field_id_1: "value1", field_id_2: "value2"},
        {field_id_1: "value3", field_id_2: "value4"},
    ]

    result = export_data(kal_client_mock, input_data)

    # Verify the Fields methods were called
    mock_get_key_fields.assert_called_once()
    mock_get_data_fields.assert_called_once()

    # Verify the output structure
    assert isinstance(result, list)
    assert len(result) == 2

    # Verify field IDs were replaced with field names
    assert field_name_1 in result[0]
    assert field_name_2 in result[0]
    assert result[0][field_name_1] == "value1"
    assert result[0][field_name_2] == "value2"

    assert field_name_1 in result[1]
    assert field_name_2 in result[1]
    assert result[1][field_name_1] == "value3"
    assert result[1][field_name_2] == "value4"


def test_export_data_with_unknown_field_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that export_data():
    - Preserves unknown field IDs (not in key_fields or data_fields) as-is
    """
    key_fields_data = _MockData.KEY_FIELDS[:1]
    data_fields_data = _MockData.DATA_FIELDS[:1]

    mocker.patch.object(
        kal_client_mock.entity_fields,
        "get_key_fields",
        return_value=[EntityField.model_validate(f) for f in key_fields_data],
    )

    mocker.patch.object(
        kal_client_mock.entity_fields,
        "get_data_fields",
        return_value=[EntityField.model_validate(f) for f in data_fields_data],
    )

    known_field_id = key_fields_data[0]["id"]
    known_field_name = key_fields_data[0]["field_name"]
    unknown_field_id = "unknown-field-id-123"

    input_data = [{known_field_id: "known_value", unknown_field_id: "unknown_value"}]

    result = export_data(kal_client_mock, input_data)

    assert len(result) == 1
    # Known field ID should be converted to field name
    assert known_field_name in result[0]
    assert result[0][known_field_name] == "known_value"
    # Unknown field ID should be preserved as-is
    assert unknown_field_id in result[0]
    assert result[0][unknown_field_id] == "unknown_value"


def test_export_data_empty_list(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that export_data():
    - Returns an empty list when given an empty list
    """
    key_fields_data = _MockData.KEY_FIELDS
    data_fields_data = _MockData.DATA_FIELDS

    mocker.patch.object(
        kal_client_mock.entity_fields,
        "get_key_fields",
        return_value=[EntityField.model_validate(f) for f in key_fields_data],
    )

    mocker.patch.object(
        kal_client_mock.entity_fields,
        "get_data_fields",
        return_value=[EntityField.model_validate(f) for f in data_fields_data],
    )

    input_data: List[Dict[str, Any]] = []

    result = export_data(kal_client_mock, input_data)

    assert isinstance(result, list)
    assert len(result) == 0


def test_export_data_with_all_field_types(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that export_data():
    - Correctly handles records with both key fields and data fields
    """
    key_fields_data = _MockData.KEY_FIELDS
    data_fields_data = _MockData.DATA_FIELDS

    mocker.patch.object(
        kal_client_mock.entity_fields,
        "get_key_fields",
        return_value=[EntityField.model_validate(f) for f in key_fields_data],
    )

    mocker.patch.object(
        kal_client_mock.entity_fields,
        "get_data_fields",
        return_value=[EntityField.model_validate(f) for f in data_fields_data],
    )

    # Create input with multiple key and data fields
    input_data = [
        {
            key_fields_data[0]["id"]: "key_value_1",
            key_fields_data[1]["id"]: "key_value_2",
            data_fields_data[0]["id"]: "data_value_1",
            data_fields_data[1]["id"]: "data_value_2",
        }
    ]

    result = export_data(kal_client_mock, input_data)

    assert len(result) == 1
    # All field IDs should be replaced with field names
    assert key_fields_data[0]["field_name"] in result[0]
    assert key_fields_data[1]["field_name"] in result[0]
    assert data_fields_data[0]["field_name"] in result[0]
    assert data_fields_data[1]["field_name"] in result[0]
    # Values should be preserved
    assert result[0][key_fields_data[0]["field_name"]] == "key_value_1"
    assert result[0][key_fields_data[1]["field_name"]] == "key_value_2"
    assert result[0][data_fields_data[0]["field_name"]] == "data_value_1"
    assert result[0][data_fields_data[1]["field_name"]] == "data_value_2"


def test_export_data_preserves_value_types(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that export_data():
    - Preserves the types of values (not just strings)
    """
    key_fields_data = _MockData.KEY_FIELDS[:1]
    data_fields_data = _MockData.DATA_FIELDS[:2]

    mocker.patch.object(
        kal_client_mock.entity_fields,
        "get_key_fields",
        return_value=[EntityField.model_validate(f) for f in key_fields_data],
    )

    mocker.patch.object(
        kal_client_mock.entity_fields,
        "get_data_fields",
        return_value=[EntityField.model_validate(f) for f in data_fields_data],
    )

    field_id_1 = key_fields_data[0]["id"]
    field_id_2 = data_fields_data[0]["id"]
    field_id_3 = data_fields_data[1]["id"]

    # Test with different value types
    input_data = [
        {field_id_1: "string_value", field_id_2: 42, field_id_3: True},
        {field_id_1: "another_string", field_id_2: 3.14, field_id_3: None},
    ]

    result = export_data(kal_client_mock, input_data)

    field_name_1 = key_fields_data[0]["field_name"]
    field_name_2 = data_fields_data[0]["field_name"]
    field_name_3 = data_fields_data[1]["field_name"]

    # Verify types are preserved
    assert result[0][field_name_1] == "string_value"
    assert result[0][field_name_2] == 42
    assert isinstance(result[0][field_name_2], int)
    assert result[0][field_name_3] is True

    assert result[1][field_name_1] == "another_string"
    assert result[1][field_name_2] == 3.14
    assert isinstance(result[1][field_name_2], float)
    assert result[1][field_name_3] is None
