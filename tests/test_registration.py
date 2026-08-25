"""
Unit tests for RegistrationService methods on the KaleidoscopeClient.

Covers:
- submit_results: legacy `error_message` field and new `message` field
- register_file: creates a registration and parses the response
- get_registration_files: lists registrations for an operation
- push_status: pushes an intermediate lifecycle status
"""

from typing import Any

import pytest
from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient
from kalbio.registration import (
    RegistrationFile,
    RegistrationFileStatusEnum,
    RegistrationFileWithErrors,
    RegistrationResultStatusEnum,
)


def _registration_file_response(**overrides) -> dict:
    """Build a valid RegistrationFile API response, with optional field overrides."""
    base = {
        "id": "reg-1",
        "workspace_id": "ws-1",
        "operation_id": "op-1",
        "file_id": "file-1",
        "status": "pending",
        "message": None,
        "error_message": None,
        "created_by": "user-1",
        "last_updated_by": "user-1",
        "created_at": "2026-06-01T00:00:00Z",
        "updated_at": "2026-06-01T00:00:00Z",
    }
    base.update(overrides)
    return base


# ==================== RegistrationService Methods ====================


def test_submit_results_success(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.submit_results():
    - Makes the POST request to the proper endpoint
    - Returns True on success
    - Sends only the status field when no optional params provided
    """
    operation_id = "op-123"
    file_id = "file-456"

    mock_post = mocker.patch.object(
        kal_client_mock, "_post_no_content", return_value=True
    )

    result = kal_client_mock.registration.submit_results(
        operation_id=operation_id,
        file_id=file_id,
        status=RegistrationResultStatusEnum.SUCCESS,
    )

    mock_post.assert_called_once_with(
        f"/operations/{operation_id}/register/{file_id}/results",
        {"status": "success"},
    )
    assert result is True


def test_submit_results_with_key_field_names(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.submit_results():
    - Includes key_field_names in payload when provided
    """
    operation_id = "op-123"
    file_id = "file-456"
    key_field_names = ["id", "name"]

    mock_post = mocker.patch.object(
        kal_client_mock, "_post_no_content", return_value=True
    )

    kal_client_mock.registration.submit_results(
        operation_id=operation_id,
        file_id=file_id,
        status=RegistrationResultStatusEnum.SUCCESS,
        key_field_names=key_field_names,
    )

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert payload["key_field_names"] == key_field_names


def test_submit_results_with_records(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.submit_results():
    - Includes records in payload when provided
    """
    operation_id = "op-123"
    file_id = "file-456"
    records: list[dict[str, Any]] = [
        {
            "record_id": "rec-1",
            "status": "matched",
            "data": {"id": "123", "name": "Example"},
        },
        {
            "record_id": "rec-2",
            "status": "not_found",
            "error_message": "No match found",
        },
    ]

    mock_post = mocker.patch.object(
        kal_client_mock, "_post_no_content", return_value=True
    )

    kal_client_mock.registration.submit_results(
        operation_id=operation_id,
        file_id=file_id,
        status=RegistrationResultStatusEnum.SUCCESS,
        records=records,
    )

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert payload["records"] == records


def test_submit_results_with_all_parameters(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.submit_results():
    - Correctly handles all parameters together
    """
    operation_id = "op-123"
    file_id = "file-456"
    key_field_names = ["id"]
    records = [
        {"record_id": "rec-1", "status": "matched", "data": {"id": "123"}},
    ]

    mock_post = mocker.patch.object(
        kal_client_mock, "_post_no_content", return_value=True
    )

    result = kal_client_mock.registration.submit_results(
        operation_id=operation_id,
        file_id=file_id,
        status=RegistrationResultStatusEnum.SUCCESS,
        key_field_names=key_field_names,
        records=records,
    )

    call_args = mock_post.call_args
    url = call_args[0][0]
    payload = call_args[0][1]

    assert url == f"/operations/{operation_id}/register/{file_id}/results"
    assert payload["status"] == "success"
    assert payload["key_field_names"] == key_field_names
    assert payload["records"] == records
    assert result is True


def test_submit_results_without_optional_parameters(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.submit_results():
    - Does not include optional parameters in payload when not provided
    """
    operation_id = "op-123"
    file_id = "file-456"

    mock_post = mocker.patch.object(
        kal_client_mock, "_post_no_content", return_value=True
    )

    kal_client_mock.registration.submit_results(
        operation_id=operation_id,
        file_id=file_id,
        status=RegistrationResultStatusEnum.SUCCESS,
    )

    call_args = mock_post.call_args
    payload = call_args[0][1]

    assert payload == {"status": "success"}
    assert "message" not in payload
    assert "key_field_names" not in payload
    assert "records" not in payload


def test_submit_results_returns_true_on_success(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.submit_results():
    - Returns True when the POST succeeds (it raises on failure rather than
      returning False, so False is not a reachable return value)
    """
    mocker.patch.object(kal_client_mock, "_post_no_content", return_value=True)

    result = kal_client_mock.registration.submit_results(
        operation_id="op-123",
        file_id="file-456",
        status=RegistrationResultStatusEnum.SUCCESS,
    )

    assert result is True


def test_submit_results_propagates_exceptions(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.submit_results():
    - Propagates exceptions raised by the underlying HTTP call
      (e.g. KalbioAPIError on 4xx/5xx, or other request errors)
    """
    mocker.patch.object(
        kal_client_mock,
        "_post_no_content",
        side_effect=Exception("connection error"),
    )

    with pytest.raises(Exception, match="connection error"):
        kal_client_mock.registration.submit_results(
            operation_id="op-123",
            file_id="file-456",
            status=RegistrationResultStatusEnum.SUCCESS,
        )


def test_submit_results_with_message(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.submit_results():
    - Sends the `message` field when provided
    - Accepts the RegistrationResultStatusEnum for status
    """
    mock_post = mocker.patch.object(
        kal_client_mock, "_post_no_content", return_value=True
    )

    kal_client_mock.registration.submit_results(
        operation_id="op-123",
        file_id="file-456",
        status=RegistrationResultStatusEnum.ERROR,
        message="processing failed",
    )

    payload = mock_post.call_args[0][1]
    assert payload["status"] is RegistrationResultStatusEnum.ERROR
    assert payload["message"] == "processing failed"


# ==================== RegistrationFile model ====================


def test_registration_file_backfills_message_from_legacy_error_message():
    """
    Test that RegistrationFile:
    - Populates `message` from a legacy `error_message` response field when
      `message` is missing/null
    """
    data = _registration_file_response(message=None, error_message="something broke")

    file = RegistrationFile.model_validate(data)

    assert file.message == "something broke"


def test_registration_file_prefers_message_over_error_message():
    """
    Test that RegistrationFile:
    - Uses `message` when both fields are populated (server sends both as mirrors)
    """
    data = _registration_file_response(message="preferred", error_message="legacy")

    file = RegistrationFile.model_validate(data)

    assert file.message == "preferred"


# ==================== register_file ====================


def test_register_file_success(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.register_file():
    - POSTs to the correct endpoint with an empty body
    - Parses the response into a RegistrationFile
    """
    operation_id = "op-123"
    file_id = "file-456"
    response = _registration_file_response(
        id="reg-1",
        operation_id=operation_id,
        file_id=file_id,
        status="pending",
    )

    mock_post = mocker.patch.object(kal_client_mock, "_post", return_value=response)

    result = kal_client_mock.registration.register_file(
        operation_id=operation_id, file_id=file_id
    )

    mock_post.assert_called_once_with(
        f"/operations/{operation_id}/register/{file_id}", {}
    )
    assert isinstance(result, RegistrationFile)
    assert result.id == "reg-1"
    assert result.status == RegistrationFileStatusEnum.PENDING
    assert result.file_id == file_id
    assert result.operation_id == operation_id


def test_register_file_propagates_exceptions(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.register_file():
    - Propagates exceptions raised by the underlying HTTP call
    """
    mocker.patch.object(
        kal_client_mock, "_post", side_effect=Exception("connection error")
    )

    with pytest.raises(Exception, match="connection error"):
        kal_client_mock.registration.register_file(
            operation_id="op-123", file_id="file-456"
        )


# ==================== get_registration_files ====================


def test_get_registration_files_success(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.get_registration_files():
    - GETs the correct endpoint
    - Parses the response into a list of RegistrationFileWithErrors
    - Handles both non-failed (empty record_errors) and failed entries
    """
    operation_id = "op-123"
    response = [
        {
            **_registration_file_response(id="reg-1", status="completed"),
            "record_errors": [],
        },
        {
            **_registration_file_response(
                id="reg-2", status="failed", message="bad file"
            ),
            "record_errors": [
                {
                    "source_record_id": "src-1",
                    "status": "error",
                    "error_message": "missing key",
                }
            ],
        },
    ]

    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=response)

    result = kal_client_mock.registration.get_registration_files(operation_id)

    mock_get.assert_called_once_with(f"/operations/{operation_id}/registrations")
    assert len(result) == 2
    assert all(isinstance(f, RegistrationFileWithErrors) for f in result)
    assert result[0].record_errors == []
    assert result[1].status == RegistrationFileStatusEnum.FAILED
    assert len(result[1].record_errors) == 1
    assert result[1].record_errors[0].source_record_id == "src-1"


def test_get_registration_files_empty(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.get_registration_files():
    - Returns an empty list when the response is empty
    """
    mocker.patch.object(kal_client_mock, "_get", return_value=[])

    result = kal_client_mock.registration.get_registration_files("op-123")

    assert result == []


# ==================== push_status ====================


def test_push_status_success(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.push_status():
    - POSTs to the correct endpoint
    - Sends only status when no message is provided
    - Returns True on success
    """
    operation_id = "op-123"
    file_id = "file-456"

    mock_post = mocker.patch.object(
        kal_client_mock, "_post_no_content", return_value=True
    )

    result = kal_client_mock.registration.push_status(
        operation_id=operation_id,
        file_id=file_id,
        status=RegistrationFileStatusEnum.VALIDATED,
    )

    mock_post.assert_called_once_with(
        f"/operations/{operation_id}/registration_files/{file_id}/status",
        {"status": RegistrationFileStatusEnum.VALIDATED},
    )
    assert result is True


def test_push_status_with_message(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.push_status():
    - Includes the message field when provided
    """
    mock_post = mocker.patch.object(
        kal_client_mock, "_post_no_content", return_value=True
    )

    kal_client_mock.registration.push_status(
        operation_id="op-123",
        file_id="file-456",
        status=RegistrationFileStatusEnum.VALIDATION_FAILED,
        message="row 42: invalid smiles",
    )

    payload = mock_post.call_args[0][1]
    assert payload["status"] is RegistrationFileStatusEnum.VALIDATION_FAILED
    assert payload["message"] == "row 42: invalid smiles"


def test_push_status_propagates_exceptions(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RegistrationService.push_status():
    - Propagates exceptions raised by the underlying HTTP call
    """
    mocker.patch.object(
        kal_client_mock,
        "_post_no_content",
        side_effect=Exception("connection error"),
    )

    with pytest.raises(Exception, match="connection error"):
        kal_client_mock.registration.push_status(
            operation_id="op-123",
            file_id="file-456",
            status=RegistrationFileStatusEnum.VALIDATED,
        )
