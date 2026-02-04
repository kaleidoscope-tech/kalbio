"""
Unit tests for the ProgramsService class and Program model.
Test Coverage:
- Normal operation with multiple programs
- Empty result sets
- Single and multiple ID filtering
- Non-existent IDs and partial matches
- Edge cases (empty input lists)
- Model field validation
- Internal method calls and API endpoint verification

This module contains tests for:
- ProgramsService.get_programs(): Fetching all programs from the API
- ProgramsService.get_program_by_ids(): Filtering programs by ID
- Program model: Data structure and field validation
"""

from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient
from kalbio.programs import Program
from tests.conftest import _MockData


# ==================== ProgramsService Methods ====================


def test_get_programs(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that ProgramsService.get_programs():
    - Makes the GET request to the proper endpoint
    - Returns a list of Program objects
    """
    programs_data = _MockData.PROGRAMS

    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=programs_data)

    result = kal_client_mock.programs.get_programs()

    mock_get.assert_called_once_with("/programs")
    assert isinstance(result, list)
    assert all(isinstance(p, Program) for p in result)
    assert len(result) == len(programs_data)


def test_get_programs_returns_empty_list(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ProgramsService.get_programs():
    - Returns empty list when no programs exist
    """
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=[])

    result = kal_client_mock.programs.get_programs()

    mock_get.assert_called_once_with("/programs")
    assert isinstance(result, list)
    assert len(result) == 0


def test_get_programs_by_ids(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ProgramsService.get_programs_by_ids():
    - Returns all programs that have any of the input program ids
    """
    programs_data = _MockData.PROGRAMS
    target_ids = [programs_data[0]["id"], programs_data[1]["id"]]

    mocker.patch.object(kal_client_mock, "_get", return_value=programs_data)

    result = kal_client_mock.programs.get_programs_by_ids(target_ids)

    assert isinstance(result, list)
    assert all(isinstance(p, Program) for p in result)
    assert len(result) == 2
    assert all(p.id in target_ids for p in result)


def test_get_programs_by_ids_single_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ProgramsService.get_programs_by_ids():
    - Correctly filters for a single program ID
    """
    programs_data = _MockData.PROGRAMS
    target_id = programs_data[0]["id"]

    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=programs_data)

    result = kal_client_mock.programs.get_programs_by_ids([target_id])

    mock_get.assert_called_once_with("/programs")
    assert len(result) == 1
    assert result[0].id == target_id


def test_get_programs_by_ids_no_matches(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ProgramsService.get_programs_by_ids():
    - Returns empty list when no programs match the input IDs
    """
    programs_data = _MockData.PROGRAMS
    nonexistent_ids = ["nonexistent-1", "nonexistent-2"]

    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=programs_data)

    result = kal_client_mock.programs.get_programs_by_ids(nonexistent_ids)

    mock_get.assert_called_once_with("/programs")
    assert isinstance(result, list)
    assert len(result) == 0


def test_get_programs_by_ids_all_programs(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ProgramsService.get_programs_by_ids():
    - Returns all programs when all IDs are provided
    """
    programs_data = _MockData.PROGRAMS
    all_ids = [p["id"] for p in programs_data]

    mocker.patch.object(kal_client_mock, "_get", return_value=programs_data)

    result = kal_client_mock.programs.get_programs_by_ids(all_ids)

    assert len(result) == len(programs_data)
    assert all(p.id in all_ids for p in result)


def test_get_programs_by_ids_partial_matches(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ProgramsService.get_programs_by_ids():
    - Returns only matching programs when some IDs don't exist
    """
    programs_data = _MockData.PROGRAMS
    mixed_ids = [programs_data[0]["id"], "nonexistent-id", programs_data[2]["id"]]

    mocker.patch.object(kal_client_mock, "_get", return_value=programs_data)

    result = kal_client_mock.programs.get_programs_by_ids(mixed_ids)

    assert len(result) == 2
    assert result[0].id == programs_data[0]["id"]
    assert result[1].id == programs_data[2]["id"]


def test_get_programs_by_ids_empty_list(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ProgramsService.get_programs_by_ids():
    - Returns empty list when empty ID list is provided
    """
    programs_data = _MockData.PROGRAMS

    mocker.patch.object(kal_client_mock, "_get", return_value=programs_data)

    result = kal_client_mock.programs.get_programs_by_ids([])

    assert isinstance(result, list)
    assert len(result) == 0


def test_program_model_fields(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that Program model:
    - Has correct fields (id, title)
    - Fields are properly populated
    """
    programs_data = _MockData.PROGRAMS

    mocker.patch.object(kal_client_mock, "_get", return_value=programs_data)

    result = kal_client_mock.programs.get_programs()

    for i, program in enumerate(result):
        assert hasattr(program, "id")
        assert hasattr(program, "title")
        assert program.id == programs_data[i]["id"]
        assert program.title == programs_data[i]["title"]


def test_get_programs_by_ids_calls_get_programs(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ProgramsService.get_programs_by_ids():
    - Internally calls get_programs() to retrieve all programs
    """
    programs_data = _MockData.PROGRAMS
    target_ids = [programs_data[0]["id"]]

    # Mock _get to return programs
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=programs_data)

    result = kal_client_mock.programs.get_programs_by_ids(target_ids)

    # Verify get_programs was called (which calls _get)
    mock_get.assert_called_once_with("/programs")
    assert len(result) == 1
