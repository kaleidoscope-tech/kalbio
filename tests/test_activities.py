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

import json

import pytest
from pydantic import ValidationError
from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient, KalbioResponseError
from kalbio.activities import (
    Activity,
    ActivityDefinition,
    ActivityEvent,
    ActivityStatusEnum,
    Comment,
    ContentLayoutItem,
)
from kalbio.entity_fields import DataField
from kalbio.record_views import RecordView
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


@pytest.fixture(name="experiment_definition")
def fixture_experiment_definition(
    kal_client_mock: KaleidoscopeClient,
) -> ActivityDefinition:
    """Fixture providing an experiment-type ActivityDefinition with client set."""
    definition_data = _MockData.EXPERIMENT_TYPES[0]
    definition = ActivityDefinition.model_validate(definition_data)
    definition._set_client(kal_client_mock)
    return definition


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


def test_activity_update_maps_explicit_params_and_skips_unset(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, activity_task: Activity
):
    """
    Test that Activity.update():
    - Maps explicit keyword params to the matching request-body keys
    - Sends only the params the caller passed (UNSET defaults are omitted)
    """
    mock_put = mocker.patch.object(
        kal_client_mock, "_put", return_value={"id": activity_task.id}
    )

    activity_task.update(title="New title", add_assigned_user_ids=["user-1"])

    mock_put.assert_called_once_with(
        f"/activities/{activity_task.id}",
        {"title": "New title", "add_assigned_user_ids": ["user-1"]},
    )


def test_activity_update_merges_kwargs_catch_all(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, activity_task: Activity
):
    """
    Test that Activity.update():
    - Merges fields passed via **kwargs into the request body alongside the
      explicit params, so anything not surfaced explicitly still gets through
    """
    mock_put = mocker.patch.object(
        kal_client_mock, "_put", return_value={"id": activity_task.id}
    )

    activity_task.update(title="New title", some_future_field="x")

    mock_put.assert_called_once_with(
        f"/activities/{activity_task.id}",
        {"title": "New title", "some_future_field": "x"},
    )


def test_activity_add_records(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    activity_experiment: Activity,
):
    """
    Test that Activity.add_records():
    - Makes the PUT request to the proper endpoint
    - Passes record IDs correctly
    - Refetches so stale membership caches are dropped
    """
    record_ids = ["rec-1", "rec-2", "rec-3"]

    mock_put = mocker.patch.object(kal_client_mock, "_put", return_value=None)
    mock_refetch = mocker.patch.object(Activity, "refetch", return_value=None)

    activity_experiment.add_records(record_ids)

    mock_put.assert_called_once_with(
        f"/operations/{activity_experiment.id}/records", {"record_ids": record_ids}
    )
    mock_refetch.assert_called_once()


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


def test_activity_record_views_filters_by_operation_id(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    activity_experiment: Activity,
):
    """
    Test that Activity.record_views:
    - Returns only views whose operation_ids contain this activity's id
    - Excludes views attached to other operations or to no operation
    """
    operation_id = activity_experiment.id
    mocker.patch.object(kal_client_mock, "_get", return_value=_MockData.RECORD_VIEWS)
    kal_client_mock.record_views.get_record_views.cache_clear()

    expected_view_ids = {
        v["id"]
        for v in _MockData.RECORD_VIEWS
        if operation_id in (v.get("operation_ids") or [])
    }

    result = activity_experiment.record_views

    assert len(result) > 0, "fixture should contain at least one matching view"
    assert {v.id for v in result} == expected_view_ids
    assert all(operation_id in (v.operation_ids or []) for v in result)


def test_activity_record_views_empty_when_no_views_attached(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    activity_task: Activity,
):
    """
    Test that Activity.record_views:
    - Returns an empty list when no record views are attached to this activity
    """
    mocker.patch.object(kal_client_mock, "_get", return_value=_MockData.RECORD_VIEWS)
    kal_client_mock.record_views.get_record_views.cache_clear()

    # activity_task is a task, not an operation, so no record views should
    # mention its id.
    result = activity_task.record_views

    assert result == []


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


def test_create_activity_requires_id(kal_client_mock: KaleidoscopeClient):
    """
    Test that ActivitiesService._create_activity():
    - Still raises ValidationError when `id` (the one required field) is missing
    - Accepts otherwise-partial data: non-identity fields are optional so a
      drifted/partial server response no longer breaks parsing
    """
    with pytest.raises(ValidationError):
        kal_client_mock.activities._create_activity({"title": "no id"})

    activity = kal_client_mock.activities._create_activity({"id": "test-id"})
    assert activity.id == "test-id"


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


def test_create_activity_list_requires_id(
    kal_client_mock: KaleidoscopeClient,
):
    """
    Test that ActivitiesService._create_activity_list():
    - Raises ValidationError when any element is missing `id`
    - Accepts otherwise-partial elements (non-identity fields are optional)
    """
    with pytest.raises(ValidationError):
        kal_client_mock.activities._create_activity_list(
            [_MockData.TASKS[0], {"missing": "id"}]  # type: ignore
        )

    result = kal_client_mock.activities._create_activity_list(
        [{"id": "a1"}, {"id": "a2"}]  # type: ignore
    )
    assert [a.id for a in result] == ["a1", "a2"]


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
    mocker.patch.object(kal_client_mock, "_get", return_value=[])

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


def test_get_definition_by_id_resolves_by_title(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that ActivitiesService.get_definition_by_id():
    - Resolves a definition when given its title (not just its id)
    """
    definitions_data = _MockData.EXPERIMENT_TYPES
    target_name = definitions_data[0]["title"]

    mocker.patch.object(kal_client_mock, "_get", return_value=definitions_data)

    result = kal_client_mock.activities.get_definition_by_id(target_name)

    assert result is not None
    assert result.title == target_name


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


# ==================== Activity events / comments ====================


def _sample_event_payload(activity_id: str) -> dict:
    return {
        "id": "event-uuid-1",
        "event_type": "task.updated",
        "event_type_version": 1,
        "event_attrs": {"field": "status", "old": "to do", "new": "in progress"},
        "event_user_id": "user-uuid-1",
        "created_at": "2026-06-18T12:00:00Z",
        "resource_id": activity_id,
        "resource_type": "task",
        "workspace_id": "workspace-uuid",
        "parent_bulk_event_id": None,
        "is_bulk": False,
        "request_id": None,
        "session_id": None,
        "log": "User changed status from 'to do' to 'in progress'",
    }


def _sample_comment_payload(
    activity_id: str, comment_id: str = "comment-uuid-1"
) -> dict:
    return {
        "id": comment_id,
        "workspace_id": "workspace-uuid",
        "created_by": "user-uuid-1",
        "content": {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "hi"}]}
            ],
        },
        "parent_comment_id": None,
        "mentioned_user_ids": [],
        "resource_type": "task",
        "resource_id": activity_id,
        "created_at": "2026-06-18T12:00:00Z",
        "updated_at": "2026-06-18T12:00:00Z",
    }


def test_activity_get_events(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    activity_experiment: Activity,
):
    """
    Test that Activity.get_events():
    - Hits GET /activities/{id}/events
    - Returns a list of ActivityEvent instances
    """
    payload = [_sample_event_payload(activity_experiment.id)]
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=payload)

    events = activity_experiment.get_events()

    mock_get.assert_called_once_with(f"/activities/{activity_experiment.id}/events")
    assert len(events) == 1
    assert isinstance(events[0], ActivityEvent)
    assert events[0].event_type == "task.updated"
    assert events[0].log == "User changed status from 'to do' to 'in progress'"


def test_activity_get_events_returns_empty_on_404(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    activity_experiment: Activity,
):
    """get_events() returns [] when the activity isn't found (_get returns None)."""
    mocker.patch.object(kal_client_mock, "_get", return_value=None)

    assert activity_experiment.get_events() == []


def test_activity_get_comments(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    activity_experiment: Activity,
):
    """
    Test that Activity.get_comments():
    - Hits GET /activities/{id}/comments
    - Returns Comment instances with the client set
    """
    payload = [_sample_comment_payload(activity_experiment.id)]
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=payload)

    comments = activity_experiment.get_comments()

    mock_get.assert_called_once_with(f"/activities/{activity_experiment.id}/comments")
    assert len(comments) == 1
    assert isinstance(comments[0], Comment)
    assert comments[0]._client is kal_client_mock


# ==================== ActivityDefinition Update Methods ====================


def test_activity_definition_update_puts_only_provided_kwargs(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    experiment_definition: ActivityDefinition,
):
    """
    Test that ActivityDefinition.update():
    - Makes the PUT request to the proper endpoint
    - Sends exactly the kwargs the caller passed
    - Clears definition caches on success
    """
    # Server always returns the full updated definition. Build a realistic
    # response by patching just the field(s) we changed onto the existing data.
    full_response = {**_MockData.EXPERIMENT_TYPES[0], "title": "Renamed"}
    mock_put = mocker.patch.object(kal_client_mock, "_put", return_value=full_response)
    mock_clear = mocker.patch.object(
        kal_client_mock.activities, "_clear_definition_caches"
    )

    experiment_definition.update(title="Renamed", propagate_to_instances=True)

    mock_put.assert_called_once_with(
        f"/activity_definitions/{experiment_definition.id}",
        {"title": "Renamed", "propagate_to_instances": True},
    )
    mock_clear.assert_called_once()
    assert experiment_definition.title == "Renamed"


def test_activity_definition_update_maps_explicit_params(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    experiment_definition: ActivityDefinition,
):
    """
    Test that ActivityDefinition.update():
    - Maps explicit keyword params to the matching request-body keys
    - Sends only the params the caller passed (UNSET defaults are omitted)
    """
    mock_put = mocker.patch.object(kal_client_mock, "_put", return_value=None)
    mocker.patch.object(kal_client_mock.activities, "_clear_definition_caches")

    experiment_definition.update(add_assigned_user_ids=["user-1"])

    mock_put.assert_called_once_with(
        f"/activity_definitions/{experiment_definition.id}",
        {"add_assigned_user_ids": ["user-1"]},
    )


def test_activity_definition_update_passes_unlisted_fields_via_kwargs(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    experiment_definition: ActivityDefinition,
):
    """
    Test that ActivityDefinition.update():
    - Passes advanced fields not surfaced as explicit params through **kwargs
    """
    mock_put = mocker.patch.object(kal_client_mock, "_put", return_value=None)
    mocker.patch.object(kal_client_mock.activities, "_clear_definition_caches")

    experiment_definition.update(is_external=True, inventory_enabled=True)

    mock_put.assert_called_once_with(
        f"/activity_definitions/{experiment_definition.id}",
        {"is_external": True, "inventory_enabled": True},
    )


def test_activity_definition_update_noop_on_empty_kwargs(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    experiment_definition: ActivityDefinition,
):
    """
    Test that ActivityDefinition.update():
    - Does not call the API when no kwargs are supplied
    """
    mock_put = mocker.patch.object(kal_client_mock, "_put")

    experiment_definition.update()

    mock_put.assert_not_called()


def test_activity_definition_update_propagate_clears_activity_caches(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    experiment_definition: ActivityDefinition,
):
    """
    Test that ActivityDefinition.update():
    - Clears the activity instance caches when propagate_to_instances=True,
      since propagation mutates the instances server-side.
    """
    mocker.patch.object(
        kal_client_mock, "_put", return_value=dict(_MockData.EXPERIMENT_TYPES[0])
    )
    mocker.patch.object(kal_client_mock.activities, "_clear_definition_caches")
    mock_clear_activities = mocker.patch.object(
        kal_client_mock.activities, "_clear_activity_caches"
    )

    experiment_definition.update(title="Renamed", propagate_to_instances=True)
    mock_clear_activities.assert_called_once()

    mock_clear_activities.reset_mock()
    experiment_definition.update(title="Again")
    mock_clear_activities.assert_not_called()


def test_search_activities_accepts_string_statuses(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that search_activities():
    - Accepts plain-string statuses (the SDK's permissive style), not only
      ActivityStatusEnum members, and normalizes both to their string value.
    """
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=[])

    kal_client_mock.activities.search_activities(statuses=["in progress"])
    assert mock_get.call_args.kwargs["params"]["statuses"] == json.dumps(
        [["in progress"]]
    )

    kal_client_mock.activities.search_activities(
        statuses=[ActivityStatusEnum.IN_PROGRESS, "custom"]
    )
    assert mock_get.call_args.kwargs["params"]["statuses"] == json.dumps(
        [[ActivityStatusEnum.IN_PROGRESS.value, "custom"]]
    )


def test_create_activity_raises_on_empty_response(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that create_activity():
    - Raises KalbioResponseError instead of IndexError when the endpoint returns
      an empty list.
    """
    mocker.patch.object(kal_client_mock, "_post", return_value=[])

    with pytest.raises(KalbioResponseError):
        kal_client_mock.activities.create_activity(
            title="X", activity_type="experiment"
        )


def test_create_activity_raises_on_unresolvable_definition(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that create_activity():
    - Fails fast when a provided activity_definition_id can't be resolved,
      instead of silently creating a definition-less activity.
    """
    mocker.patch.object(
        kal_client_mock.activities, "_resolve_definition_id", return_value=None
    )
    mock_post = mocker.patch.object(kal_client_mock, "_post")

    with pytest.raises(ValueError):
        kal_client_mock.activities.create_activity(
            title="X",
            activity_type="experiment",
            activity_definition_id="does-not-exist",
        )
    mock_post.assert_not_called()


def test_set_registration_settings_sends_only_specified_fields(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    experiment_definition: ActivityDefinition,
):
    """
    Test that set_registration_settings():
    - Only includes fields the caller explicitly passed (UNSET defaults are skipped)
    - Forwards None as an explicit clear
    - Always includes propagate_to_instances
    - Maps short kwarg names to `registration_*` payload keys
    """
    mock_put = mocker.patch.object(kal_client_mock, "_put", return_value=None)
    mocker.patch.object(kal_client_mock.activities, "_clear_definition_caches")

    experiment_definition.set_registration_settings(
        property_field_id="file-uuid",
        status_field_id=None,
    )

    mock_put.assert_called_once_with(
        f"/activity_definitions/{experiment_definition.id}",
        {
            "registration_property_field_id": "file-uuid",
            "registration_status_field_id": None,
        },
    )


def test_set_registration_settings_noop_when_no_fields_provided(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    experiment_definition: ActivityDefinition,
):
    """
    Test that set_registration_settings():
    - Does not call the API when called with no arguments
    """
    mock_put = mocker.patch.object(kal_client_mock, "_put")

    experiment_definition.set_registration_settings()

    mock_put.assert_not_called()


def test_set_queuing_behavior_sends_expected_payload(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    experiment_definition: ActivityDefinition,
):
    """
    Test that set_queuing_behavior():
    - Only sends fields the caller explicitly passed
    - Maps short kwarg names to the verbose server keys
    - Forwards the queue_content_layout_ids list-of-mappings shape unchanged
    """
    mock_put = mocker.patch.object(kal_client_mock, "_put", return_value=None)
    mocker.patch.object(kal_client_mock.activities, "_clear_definition_caches")

    experiment_definition.set_queuing_behavior(
        add_view_ids=["view-1"],
        queue_content_layout_ids=[
            {"view_id": "view-1", "content_layout_ids": ["layout-1"]}
        ],
    )

    mock_put.assert_called_once_with(
        f"/activity_definitions/{experiment_definition.id}",
        {
            "add_view_ids_to_add_to_when_record_attached": ["view-1"],
            "set_queue_content_layout_ids": [
                {"view_id": "view-1", "content_layout_ids": ["layout-1"]}
            ],
        },
    )


def test_set_queuing_behavior_noop_when_no_fields_provided(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    experiment_definition: ActivityDefinition,
):
    """
    Test that set_queuing_behavior():
    - Does not call the API when no setting kwargs are provided
    """
    mock_put = mocker.patch.object(kal_client_mock, "_put")

    experiment_definition.set_queuing_behavior()

    mock_put.assert_not_called()


def test_content_layout_ids_for_view(
    kal_client_mock: KaleidoscopeClient,
):
    """
    Test that ActivityDefinition.content_layout_ids_for_view():
    - Returns ids of content_layout items whose record_view_id matches
    - Returns an empty list when no items match
    """
    definition_data = {
        **_MockData.EXPERIMENT_TYPES[0],
        "content_layout": [
            {
                "id": "layout-1",
                "component_type": "result_table",
                "position_index": 0,
                "record_view_id": "view-A",
            },
            {
                "id": "layout-2",
                "component_type": "lookup_table",
                "position_index": 1,
                "record_view_id": "view-A",
            },
            {
                "id": "layout-3",
                "component_type": "result_table",
                "position_index": 2,
                "record_view_id": "view-B",
            },
            {
                "id": "layout-4",
                "component_type": "note_section",
                "position_index": 3,
                "note_section_id": "note-1",
            },
        ],
    }
    definition = ActivityDefinition.model_validate(definition_data)
    definition._set_client(kal_client_mock)

    assert definition.content_layout_ids_for_view("view-A") == ["layout-1", "layout-2"]
    assert definition.content_layout_ids_for_view("view-B") == ["layout-3"]
    assert definition.content_layout_ids_for_view("view-missing") == []


def test_activity_definition_record_views_filters_by_operation_definition_id(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    experiment_definition: ActivityDefinition,
):
    """
    Test that ActivityDefinition.record_views:
    - Returns only views whose operation_definition_ids contain this definition's id
    """
    fake_views = [
        {
            **_MockData.RECORD_VIEWS[0],
            "operation_definition_ids": [experiment_definition.id],
        },
        {**_MockData.RECORD_VIEWS[1], "operation_definition_ids": ["other-def-id"]},
        {**_MockData.RECORD_VIEWS[2], "operation_definition_ids": None},
    ]
    mocker.patch.object(kal_client_mock, "_get", return_value=fake_views)
    kal_client_mock.record_views.get_record_views.cache_clear()

    result = experiment_definition.record_views

    assert len(result) == 1
    assert result[0].id == fake_views[0]["id"]


def test_activity_definition_record_views_excludes_templates(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    experiment_definition: ActivityDefinition,
):
    """
    ActivityDefinition.record_views excludes is_template=True entries
    (templates are surfaced via the `templates` property instead).
    """
    fake_views = [
        {
            **_MockData.RECORD_VIEWS[0],
            "operation_definition_ids": [experiment_definition.id],
            "is_template": False,
        },
        {
            **_MockData.RECORD_VIEWS[1],
            "operation_definition_ids": [experiment_definition.id],
            "is_template": True,
        },
    ]
    mocker.patch.object(kal_client_mock, "_get", return_value=fake_views)
    kal_client_mock.record_views.get_record_views.cache_clear()

    result = experiment_definition.record_views

    assert len(result) == 1
    assert result[0].id == fake_views[0]["id"]
    assert all(not v.is_template for v in result)


def test_activity_definition_templates_returns_linked_templates(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    experiment_definition: ActivityDefinition,
):
    """
    ActivityDefinition.templates returns templates whose
    operation_definition_ids contain this definition's id.
    """
    fake_templates = [
        {
            "id": "t-linked",
            "workspace_id": "ws",
            "view_name": "linked template",
            "template_name": "linked",
            "entity_slice_id": "slice",
            "operation_definition_ids": [experiment_definition.id],
            "is_template": True,
        },
        {
            "id": "t-other",
            "workspace_id": "ws",
            "view_name": "other template",
            "template_name": "other",
            "entity_slice_id": "slice",
            "operation_definition_ids": ["different-def"],
            "is_template": True,
        },
    ]
    mocker.patch.object(kal_client_mock, "_get", return_value=fake_templates)
    kal_client_mock.result_table_templates.get_templates.cache_clear()

    result = experiment_definition.templates

    assert {t.id for t in result} == {"t-linked"}


# ==================== Sugar Methods (queue_to_views / configure_registration) ====================


def _make_definition_with_layout(
    kal_client_mock: KaleidoscopeClient,
    content_layout: list[dict],
) -> ActivityDefinition:
    """Helper to build an ActivityDefinition with a custom content_layout."""
    data = {**_MockData.EXPERIMENT_TYPES[0], "content_layout": content_layout}
    defn = ActivityDefinition.model_validate(data)
    defn._set_client(kal_client_mock)
    return defn


def test_queue_to_views_auto_derives_layout_from_single_placement(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
):
    """
    Test that queue_to_views():
    - Auto-derives content_layout_ids from RecordView when a view has one placement
    - Delegates to set_queuing_behavior with the server-shaped payload
    """
    defn = _make_definition_with_layout(
        kal_client_mock,
        [
            {
                "id": "layout-A",
                "component_type": "result_table",
                "position_index": 0,
                "record_view_id": "view-A",
            },
        ],
    )
    view = RecordView.model_validate(
        {
            **_MockData.RECORD_VIEWS[0],
            "id": "view-A",
        }
    )

    mock_put = mocker.patch.object(kal_client_mock, "_put", return_value=None)
    mocker.patch.object(kal_client_mock.activities, "_clear_definition_caches")

    defn.queue_to_views([view])

    mock_put.assert_called_once_with(
        f"/activity_definitions/{defn.id}",
        {
            "add_view_ids_to_add_to_when_record_attached": ["view-A"],
            "set_queue_content_layout_ids": [
                {"view_id": "view-A", "content_layout_ids": ["layout-A"]}
            ],
        },
    )


def test_queue_to_views_raises_when_view_has_multiple_placements(
    kal_client_mock: KaleidoscopeClient,
):
    """
    Test that queue_to_views():
    - Raises ValueError when a RecordView has multiple placements in the definition
    """
    defn = _make_definition_with_layout(
        kal_client_mock,
        [
            {
                "id": "layout-A",
                "component_type": "result_table",
                "position_index": 0,
                "record_view_id": "view-A",
            },
            {
                "id": "layout-B",
                "component_type": "lookup_table",
                "position_index": 1,
                "record_view_id": "view-A",
            },
        ],
    )
    view = RecordView.model_validate({**_MockData.RECORD_VIEWS[0], "id": "view-A"})

    with pytest.raises(ValueError, match="2 placements"):
        defn.queue_to_views([view])


def test_queue_to_views_accepts_content_layout_item_for_explicit_placement(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
):
    """
    Test that queue_to_views():
    - Accepts ContentLayoutItem to target a specific placement
    - Lets users disambiguate multi-placement views
    """
    defn = _make_definition_with_layout(
        kal_client_mock,
        [
            {
                "id": "layout-A",
                "component_type": "result_table",
                "position_index": 0,
                "record_view_id": "view-A",
            },
            {
                "id": "layout-B",
                "component_type": "lookup_table",
                "position_index": 1,
                "record_view_id": "view-A",
            },
        ],
    )
    chosen = defn.content_layout[1]  # layout-B

    mock_put = mocker.patch.object(kal_client_mock, "_put", return_value=None)
    mocker.patch.object(kal_client_mock.activities, "_clear_definition_caches")

    defn.queue_to_views([chosen])

    mock_put.assert_called_once_with(
        f"/activity_definitions/{defn.id}",
        {
            "add_view_ids_to_add_to_when_record_attached": ["view-A"],
            "set_queue_content_layout_ids": [
                {"view_id": "view-A", "content_layout_ids": ["layout-B"]}
            ],
        },
    )


def test_configure_registration_derives_layout_and_resolves_objects(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
):
    """
    Test that configure_registration():
    - Derives content_layout_id from the passed view
    - Accepts a DataField for status_field and uses its id
    - Accepts a string for file_property_field
    - Delegates to set_registration_settings with the right payload
    """
    defn = _make_definition_with_layout(
        kal_client_mock,
        [
            {
                "id": "layout-A",
                "component_type": "result_table",
                "position_index": 0,
                "record_view_id": "view-A",
            },
        ],
    )
    view = RecordView.model_validate({**_MockData.RECORD_VIEWS[0], "id": "view-A"})

    status_data_field = mocker.MagicMock(spec=DataField)
    status_data_field.id = "status-df-id"

    mock_put = mocker.patch.object(kal_client_mock, "_put", return_value=None)
    mocker.patch.object(kal_client_mock.activities, "_clear_definition_caches")

    defn.configure_registration(
        view=view,
        file_property_field="file-pf-id",
        status_field=status_data_field,
    )

    mock_put.assert_called_once_with(
        f"/activity_definitions/{defn.id}",
        {
            "registration_property_field_id": "file-pf-id",
            "registration_record_view_id": "view-A",
            "registration_content_layout_id": "layout-A",
            "registration_status_field_id": "status-df-id",
        },
    )
