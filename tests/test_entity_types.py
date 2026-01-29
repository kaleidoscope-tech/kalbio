"""
Unit tests for EntityType model and EntityTypesService.

Test Coverage:
    - EntityType.get_record_ids(): Validates proper API calls and return types
    - EntityTypesService._create_entity_type(): Tests client injection
    - EntityTypesService._create_entity_type_list(): Tests batch client injection
    - EntityTypesService.get_types(): Tests retrieval of all entity types
    - EntityTypesService.get_type_by_name(): Tests retrieval by name with None fallback
    - EntityTypesService.get_types_with_key_fields(): Tests filtering by key fields
    - EntityTypesService.get_type_exact_keys(): Tests exact key field matching with order independence

Fixtures:
    - `entity_type`: Provides a pre-configured EntityType instance with mocked client
"""

import pytest
from pydantic import ValidationError
from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient
from kalbio.entity_types import EntityType
from tests.conftest import _MockData


# ==================== Fixtures ====================


@pytest.fixture(name="entity_type")
def fixture_entity_type(kal_client_mock: KaleidoscopeClient) -> EntityType:
    """Fixture that provides an EntityType instance with the client set."""
    entity_type_data = _MockData.ENTITY_TYPES[0]
    entity_type = EntityType.model_validate(entity_type_data)
    entity_type._set_client(kal_client_mock)

    return entity_type


# ==================== EntityType Instance Methods ====================


def test_entity_type_get_record_ids(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    entity_type: EntityType,
):
    """
    Test that EntityType.get_record_ids():
    - Makes the GET request to the proper endpoint
    - Returns a list of record IDs as strings
    """
    record_ids = ["rec-1", "rec-2", "rec-3"]

    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=record_ids)

    result = entity_type.get_record_ids()

    mock_get.assert_called_once_with(
        f"/records/search?entity_slice_id={entity_type.id}"
    )

    assert len(result) == len(record_ids)
    assert all(record_ids[i] == result[i] for i in range(len(record_ids)))


# ==================== EntityTypesService Methods ====================


def test_create_entity_type(kal_client_mock: KaleidoscopeClient):
    """
    Test that EntityTypesService._create_entity_type():
    - Injects client (KaleidoscopeClient) into entity_type object
    """
    entity_type_data = _MockData.ENTITY_TYPES[0]

    result = kal_client_mock.entity_types._create_entity_type(entity_type_data)

    assert isinstance(result, EntityType)
    assert result._client is kal_client_mock
    assert result.id == entity_type_data["id"]


def test_create_entity_type_validation_error(kal_client_mock: KaleidoscopeClient):
    """
    Test that EntityTypesService._create_entity_type():
    - Throws ValidationError when invalid data for EntityType is passed in
    """
    invalid_data = {
        "id": "test-id",
        # Missing required fields: key_field_ids, slice_name
    }

    with pytest.raises(ValidationError):
        kal_client_mock.entity_types._create_entity_type(invalid_data)


def test_create_entity_type_list(kal_client_mock: KaleidoscopeClient):
    """
    Test that EntityTypesService._create_entity_type_list():
    - Injects client (KaleidoscopeClient) into each entity_type object
    """
    entity_types_data = [_MockData.ENTITY_TYPES[0], _MockData.ENTITY_TYPES[1]]

    result = kal_client_mock.entity_types._create_entity_type_list(entity_types_data)

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(et, EntityType) for et in result)
    assert all(et._client is kal_client_mock for et in result)


def test_create_entity_type_list_validation_error(
    kal_client_mock: KaleidoscopeClient,
):
    """
    Test that EntityTypesService._create_entity_type_list():
    - Throws ValidationError when invalid data for list[EntityType] is passed in
    """
    invalid_data = [
        _MockData.ENTITY_TYPES[0],
        {"id": "invalid", "missing": "required fields"},
    ]

    with pytest.raises(ValidationError):
        kal_client_mock.entity_types._create_entity_type_list(invalid_data)


def test_get_types(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that EntityTypesService.get_types():
    - Makes the GET request to the proper endpoint
    - Returns a list of EntityType objects
    """
    entity_types_data = _MockData.ENTITY_TYPES

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=entity_types_data
    )

    result = kal_client_mock.entity_types.get_types()

    mock_get.assert_called_once_with("/entity_slices")
    assert isinstance(result, list)
    assert all(isinstance(et, EntityType) for et in result)
    assert len(result) == len(entity_types_data)


def test_get_type_by_name(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that EntityTypesService.get_type_by_name():
    - Makes the GET request to the proper endpoint
    - Finds the entity_type that has the corresponding name
    """
    entity_types_data = _MockData.ENTITY_TYPES
    target_name = entity_types_data[0]["slice_name"]

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=entity_types_data
    )

    result = kal_client_mock.entity_types.get_type_by_name(target_name)

    mock_get.assert_called_once_with("/entity_slices")
    assert isinstance(result, EntityType)
    assert result.slice_name == target_name


def test_get_type_by_name_returns_none_when_not_found(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that EntityTypesService.get_type_by_name():
    - Returns None when entity type with name is not found
    """
    entity_types_data = _MockData.ENTITY_TYPES

    mocker.patch.object(kal_client_mock, "_get", return_value=entity_types_data)

    result = kal_client_mock.entity_types.get_type_by_name("NonexistentName")

    assert result is None


def test_get_types_with_key_fields(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that EntityTypesService.get_types_with_key_fields():
    - Makes the GET request to the proper endpoint
    - Finds all entity_types that have the corresponding key_fields
    """
    entity_types_data = _MockData.ENTITY_TYPES
    # Get a key field that exists in at least one entity type
    target_key_field_id = entity_types_data[0]["key_field_ids"][0]

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=entity_types_data
    )

    result = kal_client_mock.entity_types.get_types_with_key_fields(
        [target_key_field_id]
    )

    mock_get.assert_called_once_with("/entity_slices")
    assert isinstance(result, list)
    assert all(isinstance(et, EntityType) for et in result)
    # Verify all returned types contain the target key field
    assert all(target_key_field_id in et.key_field_ids for et in result)


def test_get_types_with_multiple_key_fields(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that EntityTypesService.get_types_with_key_fields():
    - Finds entity types that have ALL the specified key fields
    """
    entity_types_data = _MockData.ENTITY_TYPES
    # Use entity type with multiple key fields
    target_entity = next(et for et in entity_types_data if len(et["key_field_ids"]) > 1)
    target_key_fields = target_entity["key_field_ids"]

    mocker.patch.object(kal_client_mock, "_get", return_value=entity_types_data)

    result = kal_client_mock.entity_types.get_types_with_key_fields(target_key_fields)

    assert isinstance(result, list)
    # Verify all returned types contain ALL target key fields
    assert all(all(kf in et.key_field_ids for kf in target_key_fields) for et in result)


def test_get_type_exact_keys(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that EntityTypesService.get_type_exact_keys():
    - Makes the GET request to the proper endpoint
    - Finds the entity_type that has the exact key_fields
    """
    entity_types_data = _MockData.ENTITY_TYPES
    target_entity = entity_types_data[0]
    target_key_fields = target_entity["key_field_ids"]

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=entity_types_data
    )

    result = kal_client_mock.entity_types.get_type_exact_keys(target_key_fields)

    mock_get.assert_called_once_with("/entity_slices")
    assert isinstance(result, EntityType)
    assert set(result.key_field_ids) == set(target_key_fields)
    assert result.id == target_entity["id"]


def test_get_type_exact_keys_returns_none_when_not_found(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that EntityTypesService.get_type_exact_keys():
    - Returns None when no entity type has the exact key fields
    """
    entity_types_data = _MockData.ENTITY_TYPES

    mocker.patch.object(kal_client_mock, "_get", return_value=entity_types_data)

    result = kal_client_mock.entity_types.get_type_exact_keys(["nonexistent-key-field"])

    assert result is None


def test_get_type_exact_keys_with_different_order(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that EntityTypesService.get_type_exact_keys():
    - Matches entity types regardless of key field order (using set comparison)
    """
    entity_types_data = _MockData.ENTITY_TYPES
    # Find entity with multiple key fields
    target_entity = next(et for et in entity_types_data if len(et["key_field_ids"]) > 1)
    target_key_fields = target_entity["key_field_ids"]
    # Reverse the order
    reversed_key_fields = list(reversed(target_key_fields))

    mocker.patch.object(kal_client_mock, "_get", return_value=entity_types_data)

    result = kal_client_mock.entity_types.get_type_exact_keys(reversed_key_fields)

    assert isinstance(result, EntityType)
    assert set(result.key_field_ids) == set(target_key_fields)
    assert result.id == target_entity["id"]
