"""
Unit tests for RecordView model and RecordViewsService.

This module tests the functionality of:
- RecordView instance methods (e.g., extend_view)
- RecordViewsService methods for creating and retrieving record views
- Client injection into RecordView instances
- Proper API endpoint calls and response handling

Test Coverage:
    - RecordView.extend_view(): Verifies PUT request to add key fields and instance updates
    - RecordViewsService._create_record_view(): Verifies client injection into single record view
    - RecordViewsService._create_record_views_list(): Verifies client injection into multiple record views
    - RecordViewsService.get_record_views(): Verifies GET request and list of RecordView objects returned

Fixtures:
    record_view: Provides a RecordView instance with mocked client for testing.
"""

import pytest
from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient
from kalbio.record_views import RecordView
from tests.conftest import _MockData


# ==================== Fixtures ====================


@pytest.fixture(name="record_view")
def fixture_record_view(kal_client_mock: KaleidoscopeClient) -> RecordView:
    """Fixture that provides a RecordView instance for testing."""
    record_view_data = _MockData.RECORD_VIEWS[0]
    record_view = RecordView.model_validate(record_view_data)
    record_view._set_client(kal_client_mock)
    return record_view


# ==================== RecordView Methods ====================


def test_record_view_extend_view(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, record_view: RecordView
):
    """
    Test that RecordView.extend_view():
    - Makes the PUT request to the proper endpoint
    - All parameters extend the existing record view object
    - Updates the record view instance with response data
    """
    body: RecordView.ExtendViewBody = {
        "new_key_field_name": "New Key Field",
        "records_to_transfer": [
            {"record_id": "rec-123", "key_field_name_to_value": {"field1": "value1"}}
        ],
    }

    # Mock response that updates the record view
    mock_response = {
        "id": record_view.id,
        "entity_slice_id": record_view.entity_slice_id,
        "program_ids": ["new-program-id"],
        "view_fields": [{"data_field_id": "new-field-id", "lookup_field_id": None}],
    }

    mock_put = mocker.patch.object(kal_client_mock, "_put", return_value=mock_response)

    record_view.extend_view(body)

    mock_put.assert_called_once_with(
        f"/record_views/{record_view.id}/add_key_field", body
    )
    # Verify that the record view was updated with response data
    assert record_view.program_ids == ["new-program-id"]


# ==================== RecordViewsService Methods ====================


def test_create_record_view(kal_client_mock: KaleidoscopeClient):
    """
    Test that RecordViewsService._create_record_view():
    - Injects client into new record view
    """
    record_view_data = _MockData.RECORD_VIEWS[0]

    result = kal_client_mock.record_views._create_record_view(record_view_data)

    assert isinstance(result, RecordView)
    assert result._client is kal_client_mock
    assert result.id == record_view_data["id"]


def test_create_record_views_list(kal_client_mock: KaleidoscopeClient):
    """
    Test that RecordViewsService._create_record_views_list():
    - Injects client into all new record views
    """
    record_views_data = [_MockData.RECORD_VIEWS[0], _MockData.RECORD_VIEWS[1]]

    result = kal_client_mock.record_views._create_record_views_list(record_views_data)

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(rv, RecordView) for rv in result)
    assert all(rv._client is kal_client_mock for rv in result)


def test_get_record_views(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that RecordViewsService.get_record_views():
    - Makes the GET request to the proper endpoint
    - Returns a list of RecordView objects
    """
    record_views_data = [
        _MockData.RECORD_VIEWS[0],
        _MockData.RECORD_VIEWS[1],
        _MockData.RECORD_VIEWS[2],
    ]

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=record_views_data
    )

    result = kal_client_mock.record_views.get_record_views()

    mock_get.assert_called_once_with("/record_views")
    assert isinstance(result, list)
    assert len(result) == 3
    assert all(isinstance(rv, RecordView) for rv in result)
    assert all(rv._client is kal_client_mock for rv in result)
