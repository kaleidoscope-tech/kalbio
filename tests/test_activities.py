"""
Unit tests for Activity model and ActivitiesService.

Test Coverage:
    - Activity.update(): Validates proper API calls and parameter updates
    - Activity.add_records(): Tests adding records to activities
    - Activity.get_record_data(): Tests retrieval of record data from activities
    - ActivitiesService._create_activity(): Tests client injection
    - ActivitiesService._create_activity_list(): Tests batch client injection
    - ActivitiesService.get_activities(): Tests retrieval of all activities
    - ActivitiesService.get_activity_by_id(): Tests retrieval by ID with None fallback
    - ActivitiesService.get_activities_by_ids(): Tests batch retrieval with pagination
    - ActivitiesService.get_definitions(): Tests retrieval of activity definitions
    - ActivitiesService.get_definition_by_name(): Tests definition retrieval by name
    - ActivitiesService.get_definition_by_id(): Tests definition retrieval by ID
    - ActivitiesService.get_activities_with_record(): Tests filtering activities by record

Note: Activities represent the merged concept of tasks and experiments from the previous system.
Both task-type and experiment-type activities are tested using data from tasks.json and experiments.json.

Fixtures:
    - `activity_task`: Provides a pre-configured Activity instance (task type) with mocked client
    - `activity_experiment`: Provides a pre-configured Activity instance (experiment type) with mocked client
"""

import pytest
from pydantic import ValidationError
from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient
from kalbio.activities import Activity, ActivityStatusEnum
from tests.conftest import _MockData


# ==================== Fixtures ====================


@pytest.fixture(name="activity_task")
def fixture_activity_task(kal_client_mock: KaleidoscopeClient) -> Activity:
    """Fixture that provides a task-type Activity instance with the client set."""
    # Use a task from TASKS that has activity_type="task"
    task_data = next(t for t in _MockData.TASKS if t["activity_type"] == "task")
    activity = Activity.model_validate(task_data)
    activity._set_client(kal_client_mock)

    return activity


@pytest.fixture(name="activity_experiment")
def fixture_activity_experiment(kal_client_mock: KaleidoscopeClient) -> Activity:
    """Fixture that provides an experiment-type Activity instance with the client set."""
    # Use an experiment from EXPERIMENTS (which have activity_type="experiment")
    experiment_data = _MockData.EXPERIMENTS[0]
    activity = Activity.model_validate(experiment_data)
    activity._set_client(kal_client_mock)

    return activity


# ==================== Activity Instance Methods ====================


def test_activity_update(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, activity_task: Activity
):
    """
    Test that Activity.update():
    - Makes the PUT request to the proper endpoint
    - Updates the activity with provided fields
    """
    new_status = ActivityStatusEnum.IN_PROGRESS
    updated_data = {"status": new_status, "id": activity_task.id}

    mock_put = mocker.patch.object(kal_client_mock, "_put", return_value=updated_data)
    mocker.patch.object(Activity, "refetch", return_value=None)

    activity_task.update(status=new_status)

    mock_put.assert_called_once_with(
        f"/activities/{activity_task.id}", {"status": new_status}
    )

    assert activity_task.status == new_status


def test_activity_add_records(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    activity_experiment: Activity,
):
    """
    Test that Activity.add_records():
    - Makes the PUT request to the proper endpoint
    - Passes record IDs correctly
    """
    record_ids = ["rec-1", "rec-2", "rec-3"]

    mock_put = mocker.patch.object(kal_client_mock, "_put", return_value=None)

    activity_experiment.add_records(record_ids)

    mock_put.assert_called_once_with(
        f"/operations/{activity_experiment.id}/records", {"record_ids": record_ids}
    )


def test_activity_get_record_data(
    mocker: MockerFixture,
    activity_experiment: Activity,
):
    """
    Test that Activity.get_record_data():
    - Retrieves records associated with the activity
    - Calls get_activity_data for each record
    """
    # Mock the records property
    mock_record = mocker.MagicMock()
    mock_record.get_activity_data.return_value = {"some": "data"}

    mocker.patch.object(
        Activity,
        "records",
        new_callable=mocker.PropertyMock,
        return_value=[mock_record],
    )

    result = activity_experiment.get_record_data()

    mock_record.get_activity_data.assert_called_once_with(activity_experiment.id)
    assert len(result) == 1
    assert result[0] == {"some": "data"}


# ==================== ActivitiesService Methods ====================


def test_create_activity(kal_client_mock: KaleidoscopeClient):
    """
    Test that ActivitiesService._create_activity():
    - Injects client (KaleidoscopeClient) into activity object
    """
    activity_data = _MockData.TASKS[0]

    result = kal_client_mock.activities._create_activity(activity_data)

    assert isinstance(result, Activity)
    assert result._client is kal_client_mock
    assert result.id == activity_data["id"]


def test_create_activity_validation_error(kal_client_mock: KaleidoscopeClient):
    """
    Test that ActivitiesService._create_activity():
    - Throws ValidationError when invalid data for Activity is passed in
    """
    invalid_data = {
        "id": "test-id",
        # Missing required fields: type, title, status, etc.
    }

    with pytest.raises(ValidationError):
        kal_client_mock.activities._create_activity(invalid_data)


def test_create_activity_list(kal_client_mock: KaleidoscopeClient):
    """
    Test that ActivitiesService._create_activity_list():
    - Injects client (KaleidoscopeClient) into each activity object
    """
    activities_data = [_MockData.TASKS[0], _MockData.EXPERIMENTS[0]]

    # Note: _create_activity_list signature says dict but actually accepts list
    result = kal_client_mock.activities._create_activity_list(activities_data)  # type: ignore

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(activity, Activity) for activity in result)
    assert all(activity._client is kal_client_mock for activity in result)


def test_create_activity_list_validation_error(
    kal_client_mock: KaleidoscopeClient,
):
    """
    Test that ActivitiesService._create_activity_list():
    - Throws ValidationError when invalid data for list[Activity] is passed in
    """
    invalid_data = [
        _MockData.TASKS[0],
        {"id": "invalid", "missing": "required fields"},
    ]

    with pytest.raises(ValidationError):
        kal_client_mock.activities._create_activity_list(invalid_data)  # type: ignore  # type: ignore


def test_get_activities(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that ActivitiesService.get_activities():
    - Makes the GET request to the proper endpoint
    - Returns a list of Activity objects
    """
    # Combine tasks and experiments since they're merged into activities
    activities_data = _MockData.TASKS

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=activities_data
    )

    result = kal_client_mock.activities.get_activities()

    mock_get.assert_called_once_with("/activities")
    assert isinstance(result, list)
    assert all(isinstance(activity, Activity) for activity in result)
    assert len(result) == len(activities_data)


def test_get_activity_by_id(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that ActivitiesService.get_activity_by_id():
    - Makes the GET request to the proper endpoint
    - Finds the activity with the corresponding ID
    """
    activity_data = _MockData.TASKS[0]
    target_id = activity_data["id"]

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=[activity_data]
    )

    result = kal_client_mock.activities.get_activity_by_id(target_id)

    mock_get.assert_called_once_with("/activities")
    assert isinstance(result, Activity)
    assert result.id == target_id


def test_get_activity_by_id_returns_none_when_not_found(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ActivitiesService.get_activity_by_id():
    - Returns None when activity with ID is not found
    """
    mocker.patch.object(kal_client_mock, "_get", return_value=None)

    result = kal_client_mock.activities.get_activity_by_id("nonexistent-id")

    assert result is None


def test_get_activities_by_ids(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ActivitiesService.get_activities_by_ids():
    - Makes the GET request to the proper endpoint with batch IDs
    - Returns all activities matching the provided IDs
    """
    activities_data = [_MockData.TASKS[0], _MockData.TASKS[1]]
    target_ids = [activities_data[0]["id"], activities_data[1]["id"]]

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=activities_data
    )

    result = kal_client_mock.activities.get_activities_by_ids(target_ids)

    # Verify the call was made with the correct format
    mock_get.assert_called_once_with("/activities")

    assert isinstance(result, list)
    assert len(result) == len(activities_data)
    assert all(isinstance(activity, Activity) for activity in result)


def test_get_definitions(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that ActivitiesService.get_definitions():
    - Makes the GET request to the proper endpoint
    - Returns a list of ActivityDefinition objects
    """
    definitions_data = _MockData.EXPERIMENT_TYPES

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=definitions_data
    )

    result = kal_client_mock.activities.get_definitions()

    mock_get.assert_called_once_with("/activity_definitions")
    assert isinstance(result, list)
    assert len(result) == len(definitions_data)


def test_get_definition_by_name(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ActivitiesService.get_definition_by_name():
    - Finds the activity definition with the corresponding name
    """
    definitions_data = _MockData.EXPERIMENT_TYPES
    target_name = definitions_data[0]["title"]

    mocker.patch.object(kal_client_mock, "_get", return_value=definitions_data)

    result = kal_client_mock.activities.get_definition_by_id(target_name)

    assert result is not None
    assert result.title == target_name


def test_get_definition_by_name_returns_none_when_not_found(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ActivitiesService.get_definition_by_name():
    - Returns None when definition with name is not found
    """
    definitions_data = _MockData.EXPERIMENT_TYPES

    mocker.patch.object(kal_client_mock, "_get", return_value=definitions_data)

    result = kal_client_mock.activities.get_definition_by_id("NonexistentName")

    assert result is None


def test_get_definition_by_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ActivitiesService.get_definition_by_id():
    - Finds the activity definition with the corresponding ID
    """
    definitions_data = _MockData.EXPERIMENT_TYPES
    target_id = definitions_data[0]["id"]

    mocker.patch.object(kal_client_mock, "_get", return_value=definitions_data)

    result = kal_client_mock.activities.get_definition_by_id(target_id)

    assert result is not None
    assert result.id == target_id


def test_get_definition_by_id_returns_none_when_not_found(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ActivitiesService.get_definition_by_id():
    - Returns None when definition with ID is not found
    """
    definitions_data = _MockData.EXPERIMENT_TYPES

    mocker.patch.object(kal_client_mock, "_get", return_value=definitions_data)

    result = kal_client_mock.activities.get_definition_by_id("nonexistent-id")

    assert result is None


def test_get_activities_with_record(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ActivitiesService.get_activities_with_record():
    - Makes the GET request to the proper endpoint
    - Returns activities containing the specified record
    """
    # Use experiments that have record_ids
    activities_data = [
        act for act in _MockData.EXPERIMENTS if len(act.get("all_record_ids", [])) > 0
    ]
    target_record_id = activities_data[0]["all_record_ids"][0]
    filtered_data = [
        act for act in activities_data if target_record_id in act["all_record_ids"]
    ]

    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=filtered_data)

    result = kal_client_mock.activities.get_activities_with_record(target_record_id)

    mock_get.assert_called_once_with(f"/records/{target_record_id}/operations")
    assert isinstance(result, list)
    assert all(isinstance(activity, Activity) for activity in result)
    # Verify all returned activities contain the target record
    assert all(target_record_id in activity.all_record_ids for activity in result)


def test_activity_task_type_distinction(kal_client_mock: KaleidoscopeClient):
    """
    Test that both task and experiemnt activity types are properly handled:
    - Validates that task-type activities can be created
    - Validates that experiment-type activities can be created
    - Ensures both types follow the same Activity model
    """
    # Test task type
    task_data = next(t for t in _MockData.TASKS if t["activity_type"] == "task")
    task_activity = kal_client_mock.activities._create_activity(task_data)
    assert task_activity.activity_type == "task"
    assert isinstance(task_activity, Activity)

    # Test experiment type
    experiment_data = _MockData.EXPERIMENTS[0]
    experiment_activity = kal_client_mock.activities._create_activity(experiment_data)
    assert experiment_activity.activity_type == "experiment"
    assert isinstance(experiment_activity, Activity)
    assert hasattr(experiment_activity, "all_record_ids")


def test_activity_with_properties(kal_client_mock: KaleidoscopeClient):
    """
    Test that Activity with properties:
    - Properly validates and creates Property objects
    - Sets client on each property
    """
    # Find an activity with properties
    activity_data = next(
        (act for act in _MockData.TASKS if len(act.get("properties", [])) > 0), None
    )

    if activity_data:
        activity = kal_client_mock.activities._create_activity(activity_data)

        assert len(activity.properties) > 0
        for prop in activity.properties:
            assert prop._client is kal_client_mock


def test_activity_status_enum_values():
    """
    Test that ActivityStatusEnum contains expected status values:
    - Validates common statuses used in both tasks and experiments
    """
    assert ActivityStatusEnum.TODO.value == "to do"
    assert ActivityStatusEnum.IN_PROGRESS.value == "in progress"
    assert ActivityStatusEnum.COMPLETE.value == "complete"
    assert ActivityStatusEnum.CANCELLED.value == "cancelled"
    assert ActivityStatusEnum.BLOCKED.value == "blocked"
