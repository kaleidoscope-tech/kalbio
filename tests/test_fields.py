"""
Unit tests for the FieldsService class methods in the Kaleidoscope client.
This module contains tests for both key fields and data fields operations,
including retrieval, creation, and get-or-create functionality.
Test Coverage:
    Key Fields:
        - test_get_key_fields: Validates retrieval of all key fields
        - test_get_key_field: Validates retrieval of a specific key field by name
        - test_get_key_field_returns_none_when_not_found: Validates None return for non-existent fields
        - test_get_or_create_key_field: Validates creation of new key fields
        - test_get_or_create_key_field_existing: Validates retrieval of existing key fields
    Data Fields:
        - test_get_data_fields: Validates retrieval of all data fields
        - test_get_data_field: Validates retrieval of a specific data field by name
        - test_get_data_field_returns_none_when_not_found: Validates None return for non-existent fields
        - test_get_or_create_data_field: Validates creation of new data fields with type
        - test_get_or_create_data_field_existing: Validates retrieval of existing data fields
        - test_get_or_create_data_field_with_different_types: Validates handling of various field types
"""

from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient
from kalbio.entity_fields import DataFieldTypeEnum, EntityField
from tests.conftest import _MockData


# ==================== FieldsService Methods - Key Fields ====================


def test_get_key_fields(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that FieldsService.get_key_fields():
    - Makes the GET request to the proper endpoint
    - Returns a list of Field objects
    """
    key_fields_data = _MockData.KEY_FIELDS

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=key_fields_data
    )

    result = kal_client_mock.entity_fields.get_key_fields()

    mock_get.assert_called_once_with("/key_fields")
    assert isinstance(result, list)
    assert all(isinstance(f, EntityField) for f in result)
    assert len(result) == len(key_fields_data)
    assert all(f.is_key for f in result)


def test_get_key_field_by_name(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FieldsService.get_key_field_by_name():
    - Returns the field object for the field with the respective name
    """
    key_fields_data = _MockData.KEY_FIELDS
    target_field_name = key_fields_data[0]["field_name"]

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=key_fields_data
    )

    result = kal_client_mock.entity_fields.get_key_field_by_id(target_field_name)

    mock_get.assert_called_once_with("/key_fields")
    assert isinstance(result, EntityField)
    assert result.field_name == target_field_name
    assert result.is_key is True


def test_get_key_field_by_name_returns_none_when_not_found(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FieldsService.get_key_field_by_name():
    - Returns None when field with name is not found
    """
    key_fields_data = _MockData.KEY_FIELDS

    mocker.patch.object(kal_client_mock, "_get", return_value=key_fields_data)

    result = kal_client_mock.entity_fields.get_key_field_by_id("NonexistentField")

    assert result is None


def test_get_or_create_key_field(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FieldsService.get_or_create_key_field():
    - Makes the POST request to the proper endpoint
    - Returns the key field with the input name
    - If this field does not exist, it is created
    """
    field_name = "TestKeyField"
    response_field = _MockData.KEY_FIELDS[0].copy()
    response_field["field_name"] = field_name

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value=response_field
    )

    result = kal_client_mock.entity_fields.get_or_create_key_field(field_name)

    mock_post.assert_called_once_with("/key_fields/", {"field_name": field_name})
    assert isinstance(result, EntityField)
    assert result.field_name == field_name


def test_get_or_create_key_field_existing(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FieldsService.get_or_create_key_field():
    - Returns existing field if it already exists
    """
    existing_field = _MockData.KEY_FIELDS[0]
    field_name = existing_field["field_name"]

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value=existing_field
    )

    result = kal_client_mock.entity_fields.get_or_create_key_field(field_name)

    mock_post.assert_called_once_with("/key_fields/", {"field_name": field_name})
    assert isinstance(result, EntityField)
    assert result.id == existing_field["id"]
    assert result.field_name == field_name


# ==================== FieldsService Methods - Data Fields ====================


def test_get_data_fields(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that FieldsService.get_data_fields():
    - Makes the GET request to the proper endpoint
    - Returns a list of Field objects
    """
    data_fields_data = _MockData.DATA_FIELDS

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=data_fields_data
    )

    result = kal_client_mock.entity_fields.get_data_fields()

    mock_get.assert_called_once_with("/data_fields")
    assert isinstance(result, list)
    assert all(isinstance(f, EntityField) for f in result)
    assert len(result) == len(data_fields_data)
    assert all(not f.is_key for f in result)


def test_get_data_field_by_name(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FieldsService.get_data_field_by_name():
    - Returns the data field with the corresponding name
    """
    data_fields_data = _MockData.DATA_FIELDS
    target_field_name = data_fields_data[0]["field_name"]

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=data_fields_data
    )

    result = kal_client_mock.entity_fields.get_data_field_by_id(target_field_name)

    mock_get.assert_called_once_with("/data_fields")
    assert isinstance(result, EntityField)
    assert result.field_name == target_field_name
    assert result.is_key is False


def test_get_data_field_by_name_returns_none_when_not_found(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FieldsService.get_data_field_by_name():
    - Returns None when field with name is not found
    """
    data_fields_data = _MockData.DATA_FIELDS

    mocker.patch.object(kal_client_mock, "_get", return_value=data_fields_data)

    result = kal_client_mock.entity_fields.get_data_field_by_id("NonexistentField")

    assert result is None


def test_get_or_create_data_field(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FieldsService.get_or_create_data_field():
    - Makes the POST request to the proper endpoint
    - Returns the data field with the input name
    - If this data field does not exist, it is created
    """
    field_name = "TestDataField"
    field_type = DataFieldTypeEnum.TEXT
    response_field = _MockData.DATA_FIELDS[0].copy()
    response_field["field_name"] = field_name
    response_field["field_type"] = field_type.value

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value=response_field
    )

    result = kal_client_mock.entity_fields.get_or_create_data_field(
        field_name, field_type
    )

    mock_post.assert_called_once_with(
        "/data_fields/",
        {"field_name": field_name, "field_type": field_type.value, "attrs": {}},
    )
    assert isinstance(result, EntityField)
    assert result.field_name == field_name
    assert result.field_type == field_type


def test_get_or_create_data_field_existing(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FieldsService.get_or_create_data_field():
    - Returns existing field if it already exists
    """
    existing_field = _MockData.DATA_FIELDS[1]
    field_name = existing_field["field_name"]
    field_type = DataFieldTypeEnum.NUMBER

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value=existing_field
    )

    result = kal_client_mock.entity_fields.get_or_create_data_field(
        field_name, field_type
    )

    mock_post.assert_called_once_with(
        "/data_fields/",
        {"field_name": field_name, "field_type": field_type.value, "attrs": {}},
    )
    assert isinstance(result, EntityField)
    assert result.id == existing_field["id"]
    assert result.field_name == field_name


def test_get_or_create_data_field_with_different_types(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FieldsService.get_or_create_data_field():
    - Works correctly with different field types
    """
    field_types = [
        DataFieldTypeEnum.TEXT,
        DataFieldTypeEnum.NUMBER,
        DataFieldTypeEnum.BOOLEAN,
        DataFieldTypeEnum.DATE,
    ]

    for field_type in field_types:
        field_name = f"TestField_{field_type.value}"
        response_field = _MockData.DATA_FIELDS[0].copy()
        response_field["field_name"] = field_name
        response_field["field_type"] = field_type.value

        mocker.patch.object(kal_client_mock, "_post", return_value=response_field)

        result = kal_client_mock.entity_fields.get_or_create_data_field(
            field_name, field_type
        )

        assert isinstance(result, EntityField)
        assert result.field_name == field_name
        assert result.field_type == field_type
