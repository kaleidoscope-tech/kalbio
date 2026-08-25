"""
Unit tests for the Record and RecordsService classes.

This module tests the functionality of:
- Record instance methods for managing experiments, values, and fields
- RecordsService methods for creating, retrieving, and searching records
- File upload functionality for record values
- Batch processing of multiple records

The tests use mocked KaleidoscopeClient instances to verify API calls
without making actual HTTP requests.
"""

import json
from datetime import datetime
from io import BytesIO
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient
from kalbio.activities import Activity
from kalbio.records import Record, RecordValue
from tests.conftest import _MockData


@pytest.fixture(name="record")
def fixture_record(kal_client_mock: KaleidoscopeClient) -> Record:
    """Fixture that provides a Record instance with client set."""
    record_data = _MockData.RECORDS[0]
    record = Record.model_validate(record_data)
    record._set_client(kal_client_mock)

    return record


@pytest.fixture(autouse=True)
def cleanup(kal_client_mock: KaleidoscopeClient):
    kal_client_mock.records.clear_record_caches()
    yield
    kal_client_mock.records.clear_record_caches()


# ==================== Record Instance Methods ====================


def test_get_activities(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, record: Record
):
    """
    Test that Record.get_activities():
    - Makes the GET request to the proper endpoint
    - Returns a list of Experiment objects
    """
    activities_data = []
    for exp in _MockData.EXPERIMENTS:
        if record.id in exp["all_record_ids"]:
            activities_data.append(exp)

    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=activities_data
    )

    result = record.get_activities()

    mock_get.assert_called_once_with(f"/records/{record.id}/operations")
    assert len(result) == len(activities_data)
    assert all(isinstance(exp, Activity) for exp in result)
    assert all(record.id in exp.all_record_ids for exp in result)


def test_record_add_value(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, record: Record
):
    """
    Test that Record.add_value():
    - Makes the POST request to the proper endpoint
    - All relevant input parameters are posted
    """
    field_id = "field-1"
    content = "test content"
    activity_id = "example id"

    mock_post = mocker.patch.object(kal_client_mock, "_post", return_value={})

    # TODO: Patching out all these resolvers is a temporary fix.
    mocker.patch.object(
        kal_client_mock.activities, "_resolve_activity_id", return_value=activity_id
    )
    mocker.patch.object(
        kal_client_mock.entity_fields, "_resolve_data_field_id", return_value=field_id
    )

    refetch = mocker.patch.object(
        kal_client_mock.records, "get_record_by_id", return_value=record
    )

    record.add_value(field_id, content, activity_id)

    refetch.assert_called_once_with(record.id)
    mock_post.assert_called_once_with(
        f"/records/{record.id}/values",
        {
            "content": content,
            "field_id": field_id,
            "operation_id": activity_id,
            "record_view_id": None,
        },
    )


def test_record_add_value_with_record_view_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, record: Record
):
    """
    Test that Record.add_value():
    - Forwards an explicit record_view_id to PUT /records/{id}/values
    """
    field_id = "field-1"
    content = "view-scoped content"
    activity_id = "activity-1"
    record_view_id = "view-1"

    mock_post = mocker.patch.object(kal_client_mock, "_post", return_value={})
    mocker.patch.object(
        kal_client_mock.activities, "_resolve_activity_id", return_value=activity_id
    )
    mocker.patch.object(
        kal_client_mock.entity_fields, "_resolve_data_field_id", return_value=field_id
    )
    mocker.patch.object(
        kal_client_mock.records, "get_record_by_id", return_value=record
    )

    record.add_value(field_id, content, activity_id, record_view_id=record_view_id)

    mock_post.assert_called_once_with(
        f"/records/{record.id}/values",
        {
            "content": content,
            "field_id": field_id,
            "operation_id": activity_id,
            "record_view_id": record_view_id,
        },
    )


def test_record_get_value_content_basic(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, record: Record
):
    """
    Test that Record.get_value_content():
    - Returns the most recent value content for a field
    """
    field_id = list(record.record_values.keys())[0]
    mocker.patch.object(
        kal_client_mock.entity_fields, "_resolve_data_field_id", return_value=field_id
    )

    result = record.get_value_content(field_id)

    assert result == record.record_values[field_id][0].content


def test_record_get_value_content_filtered_by_activity(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that Record.get_value_content():
    - Returns the value written by the requested activity, not the newest value
      across all activities.
    """
    record = Record.model_validate(
        {
            "id": "rec-filter",
            "record_values": {
                "field-1": [
                    {
                        "id": "v-a",
                        "content": "A-value",
                        "operation_id": "op-A",
                        "record_id": "rec-filter",
                        "created_at": "2025-01-01T00:00:00+00:00",
                    },
                    {
                        "id": "v-b",
                        "content": "B-value",
                        "operation_id": "op-B",
                        "record_id": "rec-filter",
                        "created_at": "2025-01-02T00:00:00+00:00",
                    },
                ]
            },
        }
    )
    record._set_client(kal_client_mock)
    mocker.patch.object(
        kal_client_mock.entity_fields, "_resolve_data_field_id", return_value="field-1"
    )
    mocker.patch.object(
        kal_client_mock.activities,
        "_resolve_activity_id",
        side_effect=lambda activity_id: activity_id,
    )

    # Unfiltered, the newest value (op-B) wins.
    assert record.get_value_content("field-1") == "B-value"
    # Filtered to op-A, only op-A's value is eligible.
    assert record.get_value_content("field-1", activity_id="op-A") == "A-value"


def test_record_get_activity_data(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that Record.get_activity_data():
    - Maps each field to the value written by the given activity
    - Omits fields with no value for that activity
    """
    record = Record.model_validate(
        {
            "id": "rec",
            "record_values": {
                "f1": [
                    {"id": "a1", "content": "x", "operation_id": "op-A", "record_id": "rec"},
                    {"id": "a2", "content": "y", "operation_id": "op-B", "record_id": "rec"},
                ],
                "f2": [
                    {"id": "b1", "content": "z", "operation_id": "op-B", "record_id": "rec"},
                ],
            },
        }
    )
    record._set_client(kal_client_mock)
    mocker.patch.object(
        kal_client_mock.entity_fields,
        "_resolve_data_field_id",
        side_effect=lambda field_id: field_id,
    )
    mocker.patch.object(
        kal_client_mock.activities,
        "_resolve_activity_id",
        side_effect=lambda activity_id: activity_id,
    )

    result = record.get_activity_data("op-A")

    # f1 has an op-A value; f2 only has an op-B value and is omitted.
    assert result == {"f1": "x"}


def test_record_update_field(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, record: Record
):
    """
    Test that Record.update_field():
    - Makes the POST request to the proper endpoint
    - The specified field is changed to the input value
    """
    drug_1_data = _MockData.RECORD_VALUES_DRUG_1[0]

    field_id = drug_1_data["id"]
    activity_id = drug_1_data["operation_id"]
    value = "new value"

    # updated field data
    response = drug_1_data
    response["content"] = value

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"resource": response}
    )
    # TODO: Patching out all these resolvers is a temporary fix.
    # Goal is to implement a caching system in activities and entity_fields more similar to records
    # Then, write a line like
    #   kal_client_mock.activities._build_activity(activity_data)
    # To add the activity to your cache

    mocker.patch.object(
        kal_client_mock.activities, "_resolve_activity_id", return_value=activity_id
    )
    mocker.patch.object(
        kal_client_mock.entity_fields, "_resolve_data_field_id", return_value=field_id
    )

    refetch = mocker.patch.object(
        kal_client_mock.records, "get_record_by_id", return_value=record
    )

    result = record.update_field(field_id, value, activity_id)

    mock_post.assert_called_once_with(
        f"/records/{record.id}/values",
        {
            "field_id": field_id,
            "content": value,
            "operation_id": activity_id,
            "record_view_id": None,
        },
    )
    refetch.assert_called_once_with(record.id)
    assert isinstance(result, RecordValue)
    assert result.content == value


def test_record_update_field_with_record_view_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, record: Record
):
    """
    Test that Record.update_field():
    - Forwards an explicit record_view_id to PUT /records/{id}/values
    """
    drug_1_data = _MockData.RECORD_VALUES_DRUG_1[0]
    field_id = drug_1_data["id"]
    activity_id = drug_1_data["operation_id"]
    record_view_id = "view-uuid"
    value = "new value"

    response = drug_1_data
    response["content"] = value

    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"resource": response}
    )
    mocker.patch.object(
        kal_client_mock.activities, "_resolve_activity_id", return_value=activity_id
    )
    mocker.patch.object(
        kal_client_mock.entity_fields, "_resolve_data_field_id", return_value=field_id
    )
    mocker.patch.object(
        kal_client_mock.records, "get_record_by_id", return_value=record
    )

    record.update_field(field_id, value, activity_id, record_view_id=record_view_id)

    mock_post.assert_called_once_with(
        f"/records/{record.id}/values",
        {
            "field_id": field_id,
            "content": value,
            "operation_id": activity_id,
            "record_view_id": record_view_id,
        },
    )


def test_record_get_value_content_filtered_by_record_view_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, record: Record
):
    """
    Test that Record.get_value_content():
    - Filters values down to those matching a given record_view_id
    - Excludes values from other views and key field values (record_view_id None)
    """
    field_id = list(record.record_values.keys())[0]
    values = record.record_values[field_id]

    target_view_id = "view-target"

    # Tag the first value with the target view, leave the others untagged.
    values[0].record_view_id = target_view_id
    values[0].content = "in-view value"
    for v in values[1:]:
        v.record_view_id = None

    mocker.patch.object(
        kal_client_mock.entity_fields, "_resolve_data_field_id", return_value=field_id
    )

    result = record.get_value_content(field_id, record_view_id=target_view_id)
    assert result == "in-view value"

    # A view that no value belongs to returns None
    none_result = record.get_value_content(field_id, record_view_id="other-view")
    assert none_result is None


def test_record_update_field_file(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, record: Record
):
    """
    Test that Record.update_field_file():
    - Makes the POST request to the proper endpoint
    - The specified field is changed to the input file
    """
    field_id = _MockData.RECORD_VALUES_DRUG_1[0]["field_id"]
    file_name = "test.txt"
    file_data = BytesIO(b"test file content")
    file_type = "text/plain"

    response_record_value = _MockData.RECORD_VALUES_DRUG_1[0]

    mock_post_file = mocker.patch.object(
        kal_client_mock, "_post_file", return_value={"resource": response_record_value}
    )
    # TODO: Patching out all this resolver is a temporary fix.
    mocker.patch.object(
        kal_client_mock.entity_fields, "_resolve_data_field_id", return_value=field_id
    )

    refetch = mocker.patch.object(
        kal_client_mock.records, "get_record_by_id", return_value=record
    )

    result = record.update_field_file(field_id, file_name, file_data, file_type)

    refetch.assert_called_once_with(record.id)
    mock_post_file.assert_called_once()
    call_args: tuple = mock_post_file.call_args
    assert call_args[0][0] == f"/records/{record.id}/values/file"
    assert call_args[0][1][0] == file_name
    assert call_args[0][1][2] == file_type
    assert isinstance(result, RecordValue)


# ==================== RecordsService Methods ====================


def test_create_record(kal_client_mock: KaleidoscopeClient):
    """
    Test that RecordsService._create_record():
    - Client is injected into new record
    """
    record_data = _MockData.RECORDS[0]

    result = kal_client_mock.records._create_record(record_data)

    assert isinstance(result, Record)
    assert result._client is kal_client_mock


def test_create_record_list(kal_client_mock: KaleidoscopeClient):
    """
    Test that RecordsService._create_record_list():
    - Client is injected into all new records
    """
    records_data = _MockData.RECORDS

    result = kal_client_mock.records._create_record_list(records_data)

    assert isinstance(result, list)
    assert all(isinstance(r, Record) for r in result)
    assert all(r and r._client is kal_client_mock for r in result)


def test_get_record_by_id(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that RecordsService.get_record_by_id():
    - Makes the GET request to the proper endpoint
    - Returned record has input id
    """
    record_data = _MockData.RECORDS[0]
    record_id = record_data["id"]

    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=record_data)

    result = kal_client_mock.records.get_record_by_id(record_id)

    mock_get.assert_called_once_with(f"/records/{record_id}")
    assert isinstance(result, Record)
    assert result.id == record_id


def test_get_record_by_id_returns_none_when_not_found(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RecordsService.get_record_by_id():
    - Returns None when record is not found
    """
    mocker.patch.object(kal_client_mock, "_get", return_value=None)

    result = kal_client_mock.records.get_record_by_id("nonexistent")

    assert result is None


def test_get_records_by_ids(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that RecordsService.get_records_by_ids():
    - Makes the GET request to the proper endpoint
    - Returns all records for the given IDs
    """
    records_data = _MockData.RECORDS[:2]
    record_ids = [rec["id"] for rec in records_data]

    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=records_data)

    result = kal_client_mock.records.get_records_by_ids(record_ids)

    mock_get.assert_called_once()
    assert isinstance(result, list)
    assert all(isinstance(r, Record) for r in result)
    assert len(result) == len(records_data)


def test_get_records_by_ids_batching(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RecordsService.get_records_by_ids():
    - Makes multiple GET requests when batch size is exceeded
    """
    records_data = _MockData.RECORDS
    record_ids = [f"rec-{i}" for i in range(300)]  # More than default batch size

    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=records_data)

    kal_client_mock.records.get_records_by_ids(record_ids, batch_size=100)  # type: ignore

    # Should make 3 calls for 300 IDs with batch_size=100
    assert mock_get.call_count == 3


def test_get_records_by_ids_use_cache_false_drops_stale(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RecordsService.get_records_by_ids(use_cache=False):
    - Refetches and drops a cached record the server no longer returns, instead
      of returning the stale cached copy.
    """
    svc = kal_client_mock.records

    mocker.patch.object(kal_client_mock, "_get", return_value=[{"id": "rid"}])
    assert [r.id for r in svc.get_records_by_ids(["rid"])] == ["rid"]
    assert "rid" in svc._records_uuid_map

    # The record has since been deleted server-side; a fresh fetch returns nothing.
    mocker.patch.object(kal_client_mock, "_get", return_value=[])
    result = svc.get_records_by_ids(["rid"], use_cache=False)

    assert result == []
    assert "rid" not in svc._records_uuid_map


def test_get_record_by_key_values(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RecordsService.get_record_by_key_values():
    - Makes the GET request to the proper endpoint
    - Returns the matching record
    """
    record_data = _MockData.RECORDS[0]
    key_values = {"DrugId": "drug 1"}

    # TODO: Patching out all these resolvers is a temporary fix.
    mocker.patch.object(
        kal_client_mock.entity_fields, "_resolve_key_field_id", return_value="DrugId"
    )
    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=[{"record": record_data}]
    )

    result = kal_client_mock.records.get_record_by_id(key_values)  # type: ignore

    mock_get.assert_called_once_with(
        "/records/identifiers",
        {"records_key_field_to_value": json.dumps([{"DrugId": "drug 1"}])},
    )
    assert isinstance(result, Record)


def test_get_or_create_record(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RecordsService.get_or_create_record():
    - Makes the POST request to the proper endpoint
    - Returns the record with the input key values
    """
    record_data = _MockData.RECORDS[0]
    key_values = {"DrugId": "drug 1"}

    mock_post = mocker.patch.object(kal_client_mock, "_post", return_value=record_data)

    mocker.patch.object(
        kal_client_mock.entity_fields, "_resolve_key_field_id", return_value="DrugId"
    )

    result = kal_client_mock.records.get_or_create_record(key_values)  # type: ignore

    mock_post.assert_called_once_with("/records", {"key_field_to_value": key_values})
    assert isinstance(result, Record)
    assert record_data["id"] == result.id


def test_search_records(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    """
    Test that RecordsService.search_records():
    - Makes the GET request to the proper endpoint
    - Returns list of record IDs
    """
    record_ids = ["rec-1", "rec-2", "rec-3"]

    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=record_ids)

    result = kal_client_mock.records.search_records(
        entity_slice_id="slice-id", limit=10
    )  # type: ignore

    mock_get.assert_called_once()
    assert result == record_ids


def test_create_record_value_file(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that RecordsService.create_record_value_file():
    - Makes the POST request to the proper endpoint
    - Creates a record value for a file and uploads it
    """
    record_id = _MockData.RECORDS[0]["id"]
    field_id = "field-1"
    file_name = "test.txt"
    file_data = BytesIO(b"test content")
    file_type = "text/plain"

    response = {
        "resource": {
            "content": file_data,
            "created_at": datetime.now().isoformat(),
            "created_by": "9d95f7a6-79ec-4cf3-9b99-eec59149a0f5",
            "id": str(uuid4()),
            "import_id": None,
            "field_id": "4feab06e-0a8d-407e-afd8-a54e0ca93e5c",
            "field_type": "number",
            "operation_id": None,
            "record_id": record_id,
            "workspace_id": "60171855-b8ee-4079-a809-2aaf1947829b",
        }
    }

    mock_post_file = mocker.patch.object(
        kal_client_mock, "_post_file", return_value=response
    )

    result = kal_client_mock.records.create_record_value_file(
        record_id, field_id, file_name, file_data, file_type
    )

    mock_post_file.assert_called_once()
    assert isinstance(result, RecordValue)
    assert result.content == file_data
