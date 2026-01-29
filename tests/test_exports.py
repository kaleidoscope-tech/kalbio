"""
Test suite for the ExportsService class in kalbio.exports module.
This module contains tests for the ExportsService.pull_data() method,
which handles exporting data from Kaleidoscope to CSV files.

Test Functions:
    test_pull_data_basic: Validates basic export functionality with required parameters
    test_pull_data_default_download_path: Verifies default /tmp download path usage
    test_pull_data_with_optional_parameters: Tests selective optional parameter inclusion
    test_pull_data_with_all_parameters: Validates all possible parameters are handled
    test_pull_data_returns_none_on_failure: Ensures proper None return on failure
    test_pull_data_with_filtering_and_sorting: Tests filter and sort parameter handling
"""

from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient


# ==================== ExportsService Methods ====================


def test_pull_data_basic(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that ExportsService.pull_data():
    - Makes the GET request to the proper endpoint
    - CSV file is stored at input file location
    """
    filename = "test_export.csv"
    entity_slice_id = "test-entity-slice-id"
    download_path = "/tmp"
    expected_file_path = f"{download_path}/{filename}"

    mock_get_file = mocker.patch.object(
        kal_client_mock, "_get_file", return_value=expected_file_path
    )

    result = kal_client_mock.exports.pull_data(
        filename=filename, entity_slice_id=entity_slice_id, download_path=download_path
    )

    mock_get_file.assert_called_once_with(
        "/records/export/csv",
        expected_file_path,
        {"filename": filename, "entity_slice_id": entity_slice_id},
    )
    assert result == expected_file_path


def test_pull_data_default_download_path(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ExportsService.pull_data():
    - Uses /tmp as default download path when not specified
    """
    filename = "test_export.csv"
    entity_slice_id = "test-entity-slice-id"
    expected_file_path = f"/tmp/{filename}"

    mock_get_file = mocker.patch.object(
        kal_client_mock, "_get_file", return_value=expected_file_path
    )

    result = kal_client_mock.exports.pull_data(
        filename=filename, entity_slice_id=entity_slice_id
    )

    mock_get_file.assert_called_once_with(
        "/records/export/csv",
        expected_file_path,
        {"filename": filename, "entity_slice_id": entity_slice_id},
    )
    assert result == expected_file_path


def test_pull_data_with_optional_parameters(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ExportsService.pull_data():
    - Includes optional parameters when provided
    - Excludes None optional parameters
    """
    filename = "test_export.csv"
    entity_slice_id = "test-entity-slice-id"
    download_path = "/custom/path"
    record_view_id = "view-123"
    operation_id = "op-456"
    search_text = "test search"
    expected_file_path = f"{download_path}/{filename}"

    mock_get_file = mocker.patch.object(
        kal_client_mock, "_get_file", return_value=expected_file_path
    )

    result = kal_client_mock.exports.pull_data(
        filename=filename,
        entity_slice_id=entity_slice_id,
        download_path=download_path,
        record_view_id=record_view_id,
        operation_id=operation_id,
        search_text=search_text,
    )

    # Verify the call includes optional parameters
    call_args = mock_get_file.call_args
    assert call_args[0][0] == "/records/export/csv"
    assert call_args[0][1] == expected_file_path

    params = call_args[0][2]
    assert params["filename"] == filename
    assert params["entity_slice_id"] == entity_slice_id
    assert params["record_view_id"] == record_view_id
    assert params["operation_id"] == operation_id
    assert params["search_text"] == search_text

    # Verify None parameters are not included
    assert "view_field_ids" not in params
    assert "identifier_ids" not in params

    assert result == expected_file_path


def test_pull_data_with_all_parameters(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ExportsService.pull_data():
    - Correctly handles all optional parameters when provided
    """
    filename = "full_export.csv"
    entity_slice_id = "entity-123"
    download_path = "/exports"
    record_view_id = "view-123"
    view_field_ids = "field1,field2,field3"
    identifier_ids = "id1,id2"
    record_set_id = "set-123"
    program_id = "prog-123"
    operation_id = "op-123"
    record_set_filters = "filter1"
    view_field_filters = "vf_filter1"
    view_field_sorts = "vf_sort1"
    entity_field_filters = "ef_filter1"
    entity_field_sorts = "ef_sort1"
    search_text = "search"

    expected_file_path = f"{download_path}/{filename}"

    mock_get_file = mocker.patch.object(
        kal_client_mock, "_get_file", return_value=expected_file_path
    )

    result = kal_client_mock.exports.pull_data(
        filename=filename,
        entity_slice_id=entity_slice_id,
        download_path=download_path,
        record_view_id=record_view_id,
        view_field_ids=view_field_ids,
        identifier_ids=identifier_ids,
        record_set_id=record_set_id,
        program_id=program_id,
        operation_id=operation_id,
        record_set_filters=record_set_filters,
        view_field_filters=view_field_filters,
        view_field_sorts=view_field_sorts,
        entity_field_filters=entity_field_filters,
        entity_field_sorts=entity_field_sorts,
        search_text=search_text,
    )

    call_args = mock_get_file.call_args
    params = call_args[0][2]

    # Verify all parameters are included
    assert params["filename"] == filename
    assert params["entity_slice_id"] == entity_slice_id
    assert params["record_view_id"] == record_view_id
    assert params["view_field_ids"] == view_field_ids
    assert params["identifier_ids"] == identifier_ids
    assert params["record_set_id"] == record_set_id
    assert params["program_id"] == program_id
    assert params["operation_id"] == operation_id
    assert params["record_set_filters"] == record_set_filters
    assert params["view_field_filters"] == view_field_filters
    assert params["view_field_sorts"] == view_field_sorts
    assert params["entity_field_filters"] == entity_field_filters
    assert params["entity_field_sorts"] == entity_field_sorts
    assert params["search_text"] == search_text

    assert result == expected_file_path


def test_pull_data_returns_none_on_failure(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ExportsService.pull_data():
    - Returns None when file download fails
    """
    filename = "test_export.csv"
    entity_slice_id = "test-entity-slice-id"

    mocker.patch.object(kal_client_mock, "_get_file", return_value=None)

    result = kal_client_mock.exports.pull_data(
        filename=filename, entity_slice_id=entity_slice_id
    )

    assert result is None


def test_pull_data_with_filtering_and_sorting(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ExportsService.pull_data():
    - Correctly handles filter and sort parameters
    """
    filename = "filtered_export.csv"
    entity_slice_id = "entity-123"
    view_field_filters = '{"field_id": "test", "filter_type": "is_equal"}'
    view_field_sorts = '{"field_id": "test", "descending": true}'
    entity_field_filters = (
        '{"field_id": "entity_test", "filter_type": "is_greater_than"}'
    )
    entity_field_sorts = '{"field_id": "entity_test", "descending": false}'

    expected_file_path = f"/tmp/{filename}"

    mock_get_file = mocker.patch.object(
        kal_client_mock, "_get_file", return_value=expected_file_path
    )

    result = kal_client_mock.exports.pull_data(
        filename=filename,
        entity_slice_id=entity_slice_id,
        view_field_filters=view_field_filters,
        view_field_sorts=view_field_sorts,
        entity_field_filters=entity_field_filters,
        entity_field_sorts=entity_field_sorts,
    )

    call_args = mock_get_file.call_args
    params = call_args[0][2]

    assert params["view_field_filters"] == view_field_filters
    assert params["view_field_sorts"] == view_field_sorts
    assert params["entity_field_filters"] == entity_field_filters
    assert params["entity_field_sorts"] == entity_field_sorts
    assert result == expected_file_path
