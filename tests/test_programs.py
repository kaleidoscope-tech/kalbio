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

import pytest
from pytest_mock import MockerFixture

from kalbio.client import KalbioResponseError, KaleidoscopeClient
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


def test_get_programs_raises_when_endpoint_returns_no_body(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ProgramsService.get_programs():
    - Raises KalbioResponseError (not an opaque ValidationError) when the
      collection endpoint 404s or returns an empty body (_get -> None)
    """
    mocker.patch.object(kal_client_mock, "_get", return_value=None)

    with pytest.raises(KalbioResponseError):
        kal_client_mock.programs.get_programs()


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


# ==================== ProgramsService.create_program ====================


def test_create_program(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that ProgramsService.create_program():
    - Makes POST request to /programs
    - Returns a Program object
    """
    new_program = {
        "id": "new-program-uuid",
        "title": "New Program",
        "created_at": "2024-06-01T00:00:00Z",
        "created_by": "user-uuid",
        "workspace_id": "ws-uuid",
    }

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value=new_program
    )

    result = kal_client_mock.programs.create_program("New Program")

    mock_post.assert_called_once_with("/programs", {"title": "New Program"})
    assert isinstance(result, Program)
    assert result.id == "new-program-uuid"
    assert result.title == "New Program"


def test_create_program_clears_cache(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ProgramsService.create_program():
    - Clears the get_programs cache after creation
    """
    programs_data = _MockData.PROGRAMS
    mocker.patch.object(kal_client_mock, "_get", return_value=programs_data)

    # Populate cache
    kal_client_mock.programs.get_programs()

    new_program = {"id": "new-uuid", "title": "Created"}
    mocker.patch.object(kal_client_mock, "_post", return_value=new_program)

    kal_client_mock.programs.create_program("Created")

    # Cache should be cleared, so get_programs should call _get again
    updated_data = programs_data + [new_program]
    mocker.patch.object(kal_client_mock, "_get", return_value=updated_data)
    result = kal_client_mock.programs.get_programs()

    assert len(result) == len(programs_data) + 1


# ==================== ProgramsService.update_program ====================


def test_update_program(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that ProgramsService.update_program():
    - Makes PUT request to /programs/{program_id}
    - Returns the updated Program object
    """
    program_id = "8bc96c35-22f2-4fbc-9941-3d15ff619f89"
    updated_program = {
        "id": program_id,
        "title": "Updated Title",
        "created_at": "2024-01-17T16:53:20.192Z",
        "created_by": "e2bc1097-0c12-476c-b6cb-db614bb8e1d2",
        "workspace_id": "8f8066a3-3046-4008-87b0-718ab8a9c1b7",
    }

    mock_put = mocker.patch.object(
        kal_client_mock, "_put", return_value=updated_program
    )

    result = kal_client_mock.programs.update_program(program_id, "Updated Title")

    mock_put.assert_called_once_with(
        f"/programs/{program_id}", {"title": "Updated Title"}
    )
    assert isinstance(result, Program)
    assert result.id == program_id
    assert result.title == "Updated Title"


def test_update_program_clears_cache(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ProgramsService.update_program():
    - Clears the get_programs cache after update
    """
    programs_data = _MockData.PROGRAMS
    mocker.patch.object(kal_client_mock, "_get", return_value=programs_data)

    # Populate cache
    kal_client_mock.programs.get_programs()

    updated = {"id": programs_data[0]["id"], "title": "Renamed"}
    mocker.patch.object(kal_client_mock, "_put", return_value=updated)

    kal_client_mock.programs.update_program(programs_data[0]["id"], "Renamed")

    # Cache should be cleared
    updated_data = [updated] + programs_data[1:]
    mocker.patch.object(kal_client_mock, "_get", return_value=updated_data)
    result = kal_client_mock.programs.get_programs()

    assert result[0].title == "Renamed"


def test_create_program_propagates_api_error(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ProgramsService.create_program():
    - Propagates KalbioAPIError when the API request fails
    """
    from kalbio.client import KalbioAPIError

    mocker.patch.object(
        kal_client_mock,
        "_post",
        side_effect=KalbioAPIError("POST", "/programs", 400, b"bad request"),
    )

    with pytest.raises(KalbioAPIError):
        kal_client_mock.programs.create_program("Will Fail")


def test_update_program_propagates_api_error(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ProgramsService.update_program():
    - Propagates KalbioAPIError when the API request fails
    """
    from kalbio.client import KalbioAPIError

    mocker.patch.object(
        kal_client_mock,
        "_put",
        side_effect=KalbioAPIError("PUT", "/programs/some-id", 400, b"bad request"),
    )

    with pytest.raises(KalbioAPIError):
        kal_client_mock.programs.update_program("some-id", "Will Fail")
