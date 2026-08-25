"""
Unit tests for the ImportsService of the KaleidoscopeClient.

This module tests the data import functionality, verifying that:
- POST requests are made to the correct endpoints
- Input data and key fields are properly uploaded
- Optional parameters (source_id, operation_id, program_id, set_name,
  record_view_id, add_fields_to_record_view_ids) are handled correctly
- URL paths are constructed appropriately based on provided parameters
- Payloads contain the expected fields and values
- Edge cases like empty data and large datasets are handled properly
- push_data and push_data_by_field_id return import IDs
- get_imports and get_import retrieve import status
- The deprecated `record_view_ids` parameter emits a warning and is not sent

The tests use pytest-mock to mock HTTP requests and verify the correct behavior
of the ImportsService methods under various scenarios.
"""

import warnings
from typing import Any, Dict, List

import pytest
from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient, KalbioResponseError
from kalbio.imports import (
    ImportRecord,
    ImportValidationError,
    ImportValidationResult,
)


MOCK_IMPORT_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


# ==================== ImportsService.push_data ====================


def test_push_data_basic(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that ImportsService.push_data():
    - Makes the POST request to the proper endpoint
    - Returns the import_id from the response
    - Sends only key_field_names and data when no optional params are set
    """
    key_field_names = ["DrugId", "CompoundId"]
    data = [
        {"DrugId": "drug1", "CompoundId": "comp1", "effectiveness": 85.5},
        {"DrugId": "drug2", "CompoundId": "comp2", "effectiveness": 92.3},
    ]

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"import_id": MOCK_IMPORT_ID}
    )

    result = kal_client_mock.imports.push_data(
        key_field_names=key_field_names, data=data
    )

    mock_post.assert_called_once_with(
        "/push/imports",
        {"key_field_names": key_field_names, "data": data},
    )
    assert result == MOCK_IMPORT_ID


def test_push_data_with_source_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data():
    - Uses correct endpoint when source_id is provided
    - Appends source_id to URL path
    """
    key_field_names = ["DrugId"]
    data = [{"DrugId": "drug1", "name": "Test Drug"}]
    source_id = "source-123"

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"import_id": MOCK_IMPORT_ID}
    )

    result = kal_client_mock.imports.push_data(
        key_field_names=key_field_names, data=data, source_id=source_id
    )

    mock_post.assert_called_once_with(
        f"/push/imports/{source_id}",
        {"key_field_names": key_field_names, "data": data},
    )
    assert result == MOCK_IMPORT_ID


def test_push_data_with_program_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data():
    - Includes program_id in payload when provided
    """
    key_field_names = ["DrugId"]
    data = [{"DrugId": "drug1"}]
    program_id = "prog-789"

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"import_id": MOCK_IMPORT_ID}
    )

    kal_client_mock.imports.push_data(
        key_field_names=key_field_names, data=data, program_id=program_id
    )

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert "program_id" in payload
    assert payload["program_id"] == program_id


def test_push_data_with_set_name(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data():
    - Includes set_name in payload when provided
    """
    key_field_names = ["DrugId"]
    data = [{"DrugId": "drug1"}]
    set_name = "Test Set"

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"import_id": MOCK_IMPORT_ID}
    )

    kal_client_mock.imports.push_data(
        key_field_names=key_field_names, data=data, set_name=set_name
    )

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert "set_name" in payload
    assert payload["set_name"] == set_name


def test_push_data_with_record_view_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data():
    - Sends a singular record_view_id when targeting a specific view on an operation
    """
    key_field_names = ["DrugId"]
    data = [{"DrugId": "drug1"}]
    operation_id = "op-1"
    record_view_id = "view-1"

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"import_id": MOCK_IMPORT_ID}
    )

    kal_client_mock.imports.push_data(
        key_field_names=key_field_names,
        data=data,
        operation_id=operation_id,
        record_view_id=record_view_id,
    )

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert payload["operation_id"] == operation_id
    assert payload["record_view_id"] == record_view_id


def test_push_data_with_add_fields_to_record_view_ids(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data():
    - Sends add_fields_to_record_view_ids when provided
    """
    key_field_names = ["DrugId"]
    data = [{"DrugId": "drug1"}]
    add_fields_to_record_view_ids = ["view-2", "view-3"]

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"import_id": MOCK_IMPORT_ID}
    )

    kal_client_mock.imports.push_data(
        key_field_names=key_field_names,
        data=data,
        add_fields_to_record_view_ids=add_fields_to_record_view_ids,
    )

    payload = mock_post.call_args[0][1]
    assert payload["add_fields_to_record_view_ids"] == add_fields_to_record_view_ids


def test_push_data_record_view_ids_is_deprecated(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data():
    - Emits a DeprecationWarning when the legacy record_view_ids param is used
    - Does NOT send record_view_ids in the payload (the server ignores it)
    """
    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"import_id": MOCK_IMPORT_ID}
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        kal_client_mock.imports.push_data(
            key_field_names=["DrugId"],
            data=[{"DrugId": "drug1"}],
            record_view_ids=["view-1", "view-2"],
        )

    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) == 1
    assert "record_view_ids" in str(deprecations[0].message)

    payload = mock_post.call_args[0][1]
    assert "record_view_ids" not in payload


def test_push_data_with_all_optional_parameters(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data():
    - Correctly handles all optional parameters together
    - Returns import_id
    """
    key_field_names = ["DrugId", "CompoundId"]
    data = [
        {"DrugId": "drug1", "CompoundId": "comp1", "effectiveness": 85.5},
        {"DrugId": "drug2", "CompoundId": "comp2", "effectiveness": 92.3},
    ]
    source_id = "source-123"
    operation_id = "exp-456"
    program_id = "prog-789"
    record_view_id = "view-target"
    add_fields_to_record_view_ids = ["view-extra-1", "view-extra-2"]
    set_name = "Full Import Set"

    mock_post = mocker.patch.object(
        kal_client_mock,
        "_post",
        return_value={"import_id": MOCK_IMPORT_ID},
    )

    result = kal_client_mock.imports.push_data(
        key_field_names=key_field_names,
        data=data,
        source_id=source_id,
        operation_id=operation_id,
        program_id=program_id,
        record_view_id=record_view_id,
        add_fields_to_record_view_ids=add_fields_to_record_view_ids,
        set_name=set_name,
    )

    call_args = mock_post.call_args

    assert call_args[0][0] == f"/push/imports/{source_id}"

    payload = call_args[0][1]
    assert payload["key_field_names"] == key_field_names
    assert payload["data"] == data
    assert payload["operation_id"] == operation_id
    assert payload["program_id"] == program_id
    assert payload["record_view_id"] == record_view_id
    assert payload["add_fields_to_record_view_ids"] == add_fields_to_record_view_ids
    assert payload["set_name"] == set_name

    assert result == MOCK_IMPORT_ID


def test_push_data_without_optional_parameters(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data():
    - Does not include optional parameters in payload when not provided
    """
    key_field_names = ["DrugId"]
    data = [{"DrugId": "drug1"}]

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"import_id": MOCK_IMPORT_ID}
    )

    kal_client_mock.imports.push_data(key_field_names=key_field_names, data=data)

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert set(payload.keys()) == {"key_field_names", "data"}


def test_push_data_with_large_dataset(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data():
    - Handles large datasets correctly
    """
    key_field_names = ["DrugId"]
    data = [{"DrugId": f"drug{i}", "value": i * 10} for i in range(100)]

    mock_post = mocker.patch.object(
        kal_client_mock,
        "_post",
        return_value={"import_id": MOCK_IMPORT_ID},
    )

    result = kal_client_mock.imports.push_data(
        key_field_names=key_field_names, data=data
    )

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert len(payload["data"]) == 100
    assert result == MOCK_IMPORT_ID


def test_push_data_with_empty_data(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data():
    - Handles empty data list
    """
    key_field_names = ["DrugId"]
    data: List[Dict[str, Any]] = []

    mock_post = mocker.patch.object(
        kal_client_mock,
        "_post",
        return_value={"import_id": MOCK_IMPORT_ID},
    )

    result = kal_client_mock.imports.push_data(
        key_field_names=key_field_names, data=data
    )

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert payload["data"] == []
    assert result == MOCK_IMPORT_ID


def test_push_data_raises_when_no_import_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data():
    - Raises KalbioResponseError (surfacing the body) when the API response
      has no import_id, instead of silently returning None
    """
    body = {"code": "invalid_data", "message": "no key fields matched"}
    mocker.patch.object(kal_client_mock, "_post", return_value=body)

    with pytest.raises(KalbioResponseError) as exc_info:
        kal_client_mock.imports.push_data(
            key_field_names=["DrugId"], data=[{"DrugId": "drug1"}]
        )

    assert exc_info.value.response_body == body


# ==================== ImportsService.push_data_by_field_id ====================


def test_push_data_by_field_id_basic(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data_by_field_id():
    - Makes the POST request to /push/imports/by-field-id
    - Uses key_field_ids instead of key_field_names
    - Returns the import_id
    """
    key_field_ids = ["uuid-field-1", "uuid-field-2"]
    data = [
        {"uuid-field-1": "val1", "uuid-field-2": "val2", "uuid-field-3": 85.5},
    ]

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"import_id": MOCK_IMPORT_ID}
    )

    result = kal_client_mock.imports.push_data_by_field_id(
        key_field_ids=key_field_ids, data=data
    )

    mock_post.assert_called_once_with(
        "/push/imports/by-field-id",
        {"key_field_ids": key_field_ids, "data": data, "record_view_ids": []},
    )
    assert result == MOCK_IMPORT_ID


def test_push_data_by_field_id_with_all_options(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data_by_field_id():
    - Includes all optional parameters in payload
    """
    key_field_ids = ["uuid-field-1"]
    data = [{"uuid-field-1": "val1"}]
    operation_id = "op-123"
    program_id = "prog-456"
    record_view_ids = ["view-1"]
    set_name = "Batch 1"

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"import_id": MOCK_IMPORT_ID}
    )

    result = kal_client_mock.imports.push_data_by_field_id(
        key_field_ids=key_field_ids,
        data=data,
        operation_id=operation_id,
        program_id=program_id,
        record_view_ids=record_view_ids,
        set_name=set_name,
    )

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert payload["key_field_ids"] == key_field_ids
    assert payload["data"] == data
    assert payload["operation_id"] == operation_id
    assert payload["program_id"] == program_id
    assert payload["record_view_ids"] == record_view_ids
    assert payload["set_name"] == set_name
    assert result == MOCK_IMPORT_ID


def test_push_data_by_field_id_raises_when_no_import_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data_by_field_id():
    - Raises KalbioResponseError (surfacing the body) when the API response
      has no import_id, instead of silently returning None
    """
    mocker.patch.object(kal_client_mock, "_post", return_value=None)

    with pytest.raises(KalbioResponseError):
        kal_client_mock.imports.push_data_by_field_id(
            key_field_ids=["uuid-1"], data=[{"uuid-1": "val1"}]
        )


# ==================== ImportsService.get_imports ====================


def test_get_imports_basic(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.get_imports():
    - Makes GET request to /imports
    - Returns list of ImportRecord objects
    """
    imports_data = [
        {
            "id": "import-1",
            "import_status": "completed",
            "is_complete": True,
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "id": "import-2",
            "import_status": "created",
            "is_complete": False,
            "created_at": "2024-01-02T00:00:00Z",
        },
    ]

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=imports_data
    )

    result = kal_client_mock.imports.get_imports()

    mock_get.assert_called_once_with("/imports", None)
    assert len(result) == 2
    assert all(isinstance(r, ImportRecord) for r in result)
    assert result[0].id == "import-1"
    assert result[0].import_status == "completed"
    assert result[0].is_complete is True
    assert result[1].id == "import-2"
    assert result[1].is_complete is False


def test_get_imports_with_filters(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.get_imports():
    - Passes is_complete, page, page_size as query params
    """
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=[])

    kal_client_mock.imports.get_imports(is_complete=True, page=2, page_size=10)

    mock_get.assert_called_once_with(
        "/imports", {"is_complete": 1, "page": 2, "page_size": 10}
    )


def test_get_imports_is_complete_false(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.get_imports():
    - Converts is_complete=False to 0
    """
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=[])

    kal_client_mock.imports.get_imports(is_complete=False)

    mock_get.assert_called_once_with("/imports", {"is_complete": 0})


def test_get_imports_returns_empty_on_none(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.get_imports():
    - Returns empty list when API returns None
    """
    mocker.patch.object(kal_client_mock, "_get", return_value=None)

    result = kal_client_mock.imports.get_imports()

    assert result == []


# ==================== ImportsService.get_import ====================


def test_get_import_by_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.get_import():
    - Makes GET request to /imports/{import_id}
    - Returns an ImportRecord
    """
    import_data = {
        "id": MOCK_IMPORT_ID,
        "import_status": "completed",
        "is_complete": True,
        "created_at": "2024-01-01T00:00:00Z",
        "completed_at": "2024-01-01T00:05:00Z",
        "error_message": None,
        "import_result": {
            "records_created": 50,
            "records_skipped": 2,
        },
    }

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=import_data
    )

    result = kal_client_mock.imports.get_import(MOCK_IMPORT_ID)

    mock_get.assert_called_once_with(f"/imports/{MOCK_IMPORT_ID}")
    assert isinstance(result, ImportRecord)
    assert result.id == MOCK_IMPORT_ID
    assert result.import_status == "completed"
    assert result.is_complete is True
    assert result.import_result is not None
    assert result.import_result.records_created == 50
    assert result.import_result.records_skipped == 2


def test_get_import_returns_none_on_failure(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.get_import():
    - Returns None when API returns None
    """
    mocker.patch.object(kal_client_mock, "_get", return_value=None)

    result = kal_client_mock.imports.get_import(MOCK_IMPORT_ID)

    assert result is None


# ==================== Import error surfacing ====================


def test_get_import_parses_validation_errors(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.get_import():
    - Parses per-row error detail from import_result.validation_result.errors
      into typed ImportValidationResult / ImportValidationError objects
    """
    import_data = {
        "id": MOCK_IMPORT_ID,
        "import_status": "completed",
        "is_complete": True,
        "import_result": {
            "records_created": 3,
            "records_skipped": 2,
            "validation_result": {
                "total_processed": 5,
                "successful": 3,
                "failed": 2,
                "errors": [
                    {
                        "field_id": "f1",
                        "field_name": "Compound",
                        "value": "abc",
                        "conflict_type": "conflicts_with_existing",
                        "incoming_record_identifier": "R-1",
                        "conflicting_record_identifier": "R-existing",
                    },
                    {
                        "field_id": "f2",
                        "field_name": "Weight",
                        "value": "not-a-number",
                        "conflict_type": "invalid_format",
                    },
                ],
            },
        },
    }

    mocker.patch.object(kal_client_mock, "_get", return_value=import_data)

    result = kal_client_mock.imports.get_import(MOCK_IMPORT_ID)

    assert result is not None
    assert result.import_result is not None
    validation = result.import_result.validation_result
    assert isinstance(validation, ImportValidationResult)
    assert validation.failed == 2
    assert len(validation.errors) == 2
    assert all(isinstance(e, ImportValidationError) for e in validation.errors)
    assert validation.errors[0].conflict_type == "conflicts_with_existing"
    assert validation.errors[0].incoming_record_identifier == "R-1"
    assert validation.errors[1].conflict_type == "invalid_format"


def test_get_import_preserves_unmodeled_error_fields(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportRecord (extra="allow"):
    - Keeps error detail the client does not model instead of dropping it, so
      callers can still act on whatever the server returned
    """
    import_data = {
        "id": MOCK_IMPORT_ID,
        "import_status": "failed",
        "is_complete": True,
        "error_message": "Import failed while resolving key fields",
        "error_details": {"failed_row": 4, "reason": "unknown_key_field"},
    }

    mocker.patch.object(kal_client_mock, "_get", return_value=import_data)

    result = kal_client_mock.imports.get_import(MOCK_IMPORT_ID)

    assert result is not None
    assert result.error_message == "Import failed while resolving key fields"
    # Unmodeled field is retained via extra="allow", both as an attribute and in the dump.
    assert result.error_details == {"failed_row": 4, "reason": "unknown_key_field"}
    assert result.model_dump()["error_details"] == {
        "failed_row": 4,
        "reason": "unknown_key_field",
    }
