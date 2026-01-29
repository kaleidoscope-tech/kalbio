"""
Unit tests for the ImportsService.push_data() method of the KaleidoscopeClient.

This module tests the data import functionality, verifying that:
- POST requests are made to the correct endpoints
- Input data and key fields are properly uploaded
- Optional parameters (source_id, operation_id, program_id, set_name, record_view_ids) are handled correctly
- URL paths are constructed appropriately based on provided parameters
- Payloads contain the expected fields and values
- Edge cases like empty data and large datasets are handled properly

The tests use pytest-mock to mock HTTP requests and verify the correct behavior
of the push_data method under various scenarios.
"""

from typing import Any, Dict, List
from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient


# ==================== ImportsService Methods ====================


def test_push_data_basic(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that ImportsService.push_data():
    - Makes the POST request to the proper endpoint
    - All relevant input data is uploaded
    """
    key_field_names = ["DrugId", "CompoundId"]
    data = [
        {"DrugId": "drug1", "CompoundId": "comp1", "effectiveness": 85.5},
        {"DrugId": "drug2", "CompoundId": "comp2", "effectiveness": 92.3},
    ]

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"status": "success"}
    )

    result = kal_client_mock.imports.push_data(
        key_field_names=key_field_names, data=data
    )

    mock_post.assert_called_once_with(
        "/push/imports",
        {"key_field_names": key_field_names, "data": data, "record_view_ids": []},
    )
    assert result == {"status": "success"}


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
        kal_client_mock, "_post", return_value={"status": "success"}
    )

    result = kal_client_mock.imports.push_data(
        key_field_names=key_field_names, data=data, source_id=source_id
    )

    mock_post.assert_called_once_with(
        f"/push/imports/{source_id}",
        {"key_field_names": key_field_names, "data": data, "record_view_ids": []},
    )
    assert result == {"status": "success"}


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
        kal_client_mock, "_post", return_value={"status": "success"}
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
        kal_client_mock, "_post", return_value={"status": "success"}
    )

    kal_client_mock.imports.push_data(
        key_field_names=key_field_names, data=data, set_name=set_name
    )

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert "set_name" in payload
    assert payload["set_name"] == set_name


def test_push_data_with_record_view_ids(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data():
    - Includes record_view_ids in payload
    """
    key_field_names = ["DrugId"]
    data = [{"DrugId": "drug1"}]
    record_view_ids = ["view-1", "view-2", "view-3"]

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"status": "success"}
    )

    kal_client_mock.imports.push_data(
        key_field_names=key_field_names, data=data, record_view_ids=record_view_ids
    )

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert payload["record_view_ids"] == record_view_ids


def test_push_data_with_all_optional_parameters(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ImportsService.push_data():
    - Correctly handles all optional parameters together
    - All relevant input data is uploaded
    """
    key_field_names = ["DrugId", "CompoundId"]
    data = [
        {"DrugId": "drug1", "CompoundId": "comp1", "effectiveness": 85.5},
        {"DrugId": "drug2", "CompoundId": "comp2", "effectiveness": 92.3},
    ]
    source_id = "source-123"
    operation_id = "exp-456"
    program_id = "prog-789"
    record_view_ids = ["view-1", "view-2"]
    set_name = "Full Import Set"

    mock_post = mocker.patch.object(
        kal_client_mock,
        "_post",
        return_value={"status": "success", "records_created": 2},
    )

    result = kal_client_mock.imports.push_data(
        key_field_names=key_field_names,
        data=data,
        source_id=source_id,
        operation_id=operation_id,
        program_id=program_id,
        record_view_ids=record_view_ids,
        set_name=set_name,
    )

    call_args = mock_post.call_args

    # Verify URL includes source_id
    assert call_args[0][0] == f"/push/imports/{source_id}"

    # Verify payload includes all parameters
    payload = call_args[0][1]
    assert payload["key_field_names"] == key_field_names
    assert payload["data"] == data
    assert payload["operation_id"] == operation_id
    assert payload["program_id"] == program_id
    assert payload["record_view_ids"] == record_view_ids
    assert payload["set_name"] == set_name

    assert result == {"status": "success", "records_created": 2}


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
        kal_client_mock, "_post", return_value={"status": "success"}
    )

    kal_client_mock.imports.push_data(key_field_names=key_field_names, data=data)

    call_args = mock_post.call_args
    payload = call_args[0][1]

    # Verify only required fields and empty record_view_ids are in payload
    assert "key_field_names" in payload
    assert "data" in payload
    assert "record_view_ids" in payload
    assert payload["record_view_ids"] == []

    # Verify optional fields are NOT in payload when None
    assert "program_id" not in payload
    assert "operation_id" not in payload
    assert "set_name" not in payload


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
        return_value={"status": "success", "records_created": 100},
    )

    result = kal_client_mock.imports.push_data(
        key_field_names=key_field_names, data=data
    )

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert len(payload["data"]) == 100
    assert result["records_created"] == 100


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
        return_value={"status": "success", "records_created": 0},
    )

    result = kal_client_mock.imports.push_data(
        key_field_names=key_field_names, data=data
    )

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert payload["data"] == []
    assert result["records_created"] == 0
