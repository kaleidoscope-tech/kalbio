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
from kalbio.entity_fields import (
    DataField,
    DataFieldTypeEnum,
    EntityField,
    FormatEnforcementEnum,
    KeyField,
    LookupDisplayOperationScopeEnum,
    ValueAggregationTypeEnum,
)
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

    mocker.patch.object(kal_client_mock, "_get", return_value=[])
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

    # The field already exists, so get_or_create must return it without POSTing.
    mocker.patch.object(
        kal_client_mock, "_get", return_value=_MockData.KEY_FIELDS
    )
    mock_post = mocker.patch.object(kal_client_mock, "_post")

    result = kal_client_mock.entity_fields.get_or_create_key_field(field_name)

    mock_post.assert_not_called()
    assert isinstance(result, EntityField)
    assert result.id == existing_field["id"]
    assert result.field_name == field_name


def test_get_key_fields_returns_key_field_subclass(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FieldsService.get_key_fields():
    - Returns concrete KeyField instances (not just the EntityField base)
    """
    mocker.patch.object(kal_client_mock, "_get", return_value=_MockData.KEY_FIELDS)

    result = kal_client_mock.entity_fields.get_key_fields()

    assert all(isinstance(f, KeyField) for f in result)


def test_key_field_update_regex_format(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that KeyField.update():
    - Issues PUT /key_fields/{id} with only the explicitly-provided fields
    - Mutates self in place from the response's `resource` envelope
    - Clears the service's key field caches
    """
    existing_field = _MockData.KEY_FIELDS[0]
    regex_format = r"^SMP-\d{6}$"

    updated_payload = existing_field.copy()
    updated_payload["regex_format"] = regex_format

    mocker.patch.object(kal_client_mock, "_get", return_value=_MockData.KEY_FIELDS)
    mock_put = mocker.patch.object(
        kal_client_mock,
        "_put",
        return_value={"resource": updated_payload, "event": None},
    )
    cache_clear_spy = mocker.spy(
        kal_client_mock.entity_fields, "_clear_key_field_caches"
    )

    key_field = kal_client_mock.entity_fields.get_key_field_by_id(
        existing_field["field_name"]
    )
    assert isinstance(key_field, KeyField)

    result = key_field.update(regex_format=regex_format)

    mock_put.assert_called_once_with(
        f"/key_fields/{existing_field['id']}",
        {"regex_format": regex_format},
    )
    assert result is key_field  # in-place update returns self
    assert key_field.regex_format == regex_format
    cache_clear_spy.assert_called_once()


def test_key_field_update_clears_nullable_field(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that KeyField.update():
    - Forwards explicit None for nullable fields (clears them on the server)
    """
    existing_field = _MockData.KEY_FIELDS[0]

    cleared_payload = existing_field.copy()
    cleared_payload["regex_format"] = None

    mocker.patch.object(kal_client_mock, "_get", return_value=_MockData.KEY_FIELDS)
    mock_put = mocker.patch.object(
        kal_client_mock,
        "_put",
        return_value={"resource": cleared_payload, "event": None},
    )

    key_field = kal_client_mock.entity_fields.get_key_field_by_id(
        existing_field["field_name"]
    )
    assert isinstance(key_field, KeyField)

    key_field.update(regex_format=None)

    mock_put.assert_called_once_with(
        f"/key_fields/{existing_field['id']}",
        {"regex_format": None},
    )
    assert key_field.regex_format is None


def test_key_field_update_serializes_enums(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that KeyField.update():
    - Serializes enum-typed parameters to their string values for the JSON body
    """
    existing_field = _MockData.KEY_FIELDS[0]

    mocker.patch.object(kal_client_mock, "_get", return_value=_MockData.KEY_FIELDS)
    mock_put = mocker.patch.object(
        kal_client_mock,
        "_put",
        return_value={"resource": existing_field, "event": None},
    )

    key_field = kal_client_mock.entity_fields.get_key_field_by_id(
        existing_field["field_name"]
    )
    assert isinstance(key_field, KeyField)

    key_field.update(
        format_enforcement=FormatEnforcementEnum.ENFORCE_ONLY,
        serial_format_prefix="SMP-",
        serial_format_padding=6,
    )

    mock_put.assert_called_once_with(
        f"/key_fields/{existing_field['id']}",
        {
            "serial_format_prefix": "SMP-",
            "serial_format_padding": 6,
            "format_enforcement": "enforce_only",
        },
    )


def test_key_field_update_no_args_is_noop(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that KeyField.update():
    - Skips the network call when no updatable arguments are provided
    """
    existing_field = _MockData.KEY_FIELDS[0]

    mocker.patch.object(kal_client_mock, "_get", return_value=_MockData.KEY_FIELDS)
    mock_put = mocker.patch.object(kal_client_mock, "_put")

    key_field = kal_client_mock.entity_fields.get_key_field_by_id(
        existing_field["field_name"]
    )
    assert isinstance(key_field, KeyField)

    result = key_field.update()

    assert result is key_field
    mock_put.assert_not_called()


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

    mocker.patch.object(kal_client_mock, "_get", return_value=[])
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

    # The field already exists, so get_or_create must return it without POSTing.
    mocker.patch.object(
        kal_client_mock, "_get", return_value=_MockData.DATA_FIELDS
    )
    mock_post = mocker.patch.object(kal_client_mock, "_post")

    result = kal_client_mock.entity_fields.get_or_create_data_field(
        field_name, field_type
    )

    mock_post.assert_not_called()
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

    mocker.patch.object(kal_client_mock, "_get", return_value=[])

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


def test_get_data_fields_returns_data_field_subclass(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FieldsService.get_data_fields():
    - Returns concrete DataField instances (not just the EntityField base)
    """
    mocker.patch.object(kal_client_mock, "_get", return_value=_MockData.DATA_FIELDS)

    result = kal_client_mock.entity_fields.get_data_fields()

    assert all(isinstance(f, DataField) for f in result)


def test_data_field_update_serializes_fields(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that DataField.update():
    - Forwards explicit booleans, enum string values, and dict attrs to PUT /data_fields/{id}
    - Unwraps the {resource: {field, validation}, event} response shape
    - Mutates self in place and clears the data field caches
    """
    existing_field = _MockData.DATA_FIELDS[0]

    updated_payload = existing_field.copy()
    updated_payload["is_archived"] = True

    mocker.patch.object(kal_client_mock, "_get", return_value=_MockData.DATA_FIELDS)
    mock_put = mocker.patch.object(
        kal_client_mock,
        "_put",
        return_value={
            "resource": {"field": updated_payload, "validation": {}},
            "event": None,
        },
    )
    cache_clear_spy = mocker.spy(
        kal_client_mock.entity_fields, "_clear_data_field_caches"
    )

    data_field = kal_client_mock.entity_fields.get_data_field_by_id(
        existing_field["field_name"]
    )
    assert isinstance(data_field, DataField)

    result = data_field.update(
        is_archived=True,
        display_aggregation_type=ValueAggregationTypeEnum.MEAN,
        display_includes_sub_records=True,
        lookup_display_operation_scope=LookupDisplayOperationScopeEnum.CHILD,
        attrs={"custom": 1},
    )

    mock_put.assert_called_once_with(
        f"/data_fields/{existing_field['id']}",
        {
            "is_archived": True,
            "display_aggregation_type": "mean",
            "display_includes_sub_records": True,
            "lookup_display_operation_scope": "child",
            "attrs": {"custom": 1},
        },
    )
    assert result is data_field
    assert data_field.is_key is False
    cache_clear_spy.assert_called_once()


def test_data_field_update_no_args_is_noop(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that DataField.update():
    - Skips the network call when no updatable arguments are provided
    """
    existing_field = _MockData.DATA_FIELDS[0]

    mocker.patch.object(kal_client_mock, "_get", return_value=_MockData.DATA_FIELDS)
    mock_put = mocker.patch.object(kal_client_mock, "_put")

    data_field = kal_client_mock.entity_fields.get_data_field_by_id(
        existing_field["field_name"]
    )
    assert isinstance(data_field, DataField)

    result = data_field.update()

    assert result is data_field
    mock_put.assert_not_called()


def test_key_field_and_data_field_have_different_update_signatures():
    """
    Test that key-only and data-only update parameters live on the right subclasses:
    - regex_format / format_enforcement only on KeyField.update
    - is_archived / display_aggregation_type only on DataField.update
    """
    import inspect

    key_params = set(inspect.signature(KeyField.update).parameters.keys())
    data_params = set(inspect.signature(DataField.update).parameters.keys())

    key_only = {
        "regex_format",
        "serial_format_prefix",
        "serial_format_padding",
        "format_enforcement",
        "show_format_warning",
        "initial_counter_value",
        "role",
    }
    data_only = {
        "is_archived",
        "is_readonly",
        "display_aggregation_type",
        "display_includes_sub_records",
        "display_includes_operations",
        "lookup_display_aggregation_type",
        "lookup_display_includes_sub_records",
        "lookup_display_operation_scope",
        "attrs",
    }

    assert key_only.issubset(key_params)
    assert key_only.isdisjoint(data_params)

    assert data_only.issubset(data_params)
    assert data_only.isdisjoint(key_params)


# ==================== field_description / field_examples ====================


def test_entity_field_defaults_description_and_examples_to_empty_string(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that EntityField:
    - Defaults field_description and field_examples to "" when the server
      response omits them (older responses / new client)
    """
    mocker.patch.object(kal_client_mock, "_get", return_value=_MockData.KEY_FIELDS)

    fields = kal_client_mock.entity_fields.get_key_fields()

    assert all(f.field_description == "" for f in fields)
    assert all(f.field_examples == "" for f in fields)


def test_entity_field_parses_description_and_examples(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that EntityField:
    - Parses field_description and field_examples from the server response
    """
    field = _MockData.KEY_FIELDS[0].copy()
    field["field_description"] = "the compound identifier"
    field["field_examples"] = "CMP-001, CMP-002"

    mocker.patch.object(kal_client_mock, "_get", return_value=[field])

    result = kal_client_mock.entity_fields.get_key_fields()

    assert result[0].field_description == "the compound identifier"
    assert result[0].field_examples == "CMP-001, CMP-002"


def test_key_field_update_sends_description_and_examples(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that KeyField.update():
    - Forwards field_description and field_examples when provided
    """
    existing_field = _MockData.KEY_FIELDS[0]

    mocker.patch.object(kal_client_mock, "_get", return_value=_MockData.KEY_FIELDS)
    mock_put = mocker.patch.object(
        kal_client_mock,
        "_put",
        return_value={"resource": existing_field, "event": None},
    )

    key_field = kal_client_mock.entity_fields.get_key_field_by_id(
        existing_field["field_name"]
    )
    assert isinstance(key_field, KeyField)

    key_field.update(field_description="new desc", field_examples="ex1")

    mock_put.assert_called_once_with(
        f"/key_fields/{existing_field['id']}",
        {"field_description": "new desc", "field_examples": "ex1"},
    )


def test_data_field_update_sends_description_and_examples(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that DataField.update():
    - Forwards field_description and field_examples when provided
    """
    existing_field = _MockData.DATA_FIELDS[0]

    mocker.patch.object(kal_client_mock, "_get", return_value=_MockData.DATA_FIELDS)
    mock_put = mocker.patch.object(
        kal_client_mock,
        "_put",
        return_value={
            "resource": {"field": existing_field, "validation": {}},
            "event": None,
        },
    )

    data_field = kal_client_mock.entity_fields.get_data_field_by_id(
        existing_field["field_name"]
    )
    assert isinstance(data_field, DataField)

    data_field.update(field_description="new desc", field_examples="ex1")

    mock_put.assert_called_once_with(
        f"/data_fields/{existing_field['id']}",
        {"field_description": "new desc", "field_examples": "ex1"},
    )
