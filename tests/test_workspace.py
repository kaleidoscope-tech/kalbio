"""Unit tests for WorkspaceService.

Covers workspace/member/group retrieval (with client hydration) and event
search, including datetime query-param serialization and model construction.
"""

from datetime import datetime, timezone

from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient
from kalbio.workspace import (
    Workspace,
    WorkspaceEvent,
    WorkspaceGroup,
    WorkspaceUser,
)


def test_get_workspace(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    mock_get = mocker.patch.object(
        kal_client_mock,
        "_get",
        return_value={"id": "ws-1", "workspace_name": "Acme"},
    )

    result = kal_client_mock.workspace.get_workspace()

    mock_get.assert_called_once_with("/workspaces/active")
    assert isinstance(result, Workspace)
    assert result._client is kal_client_mock
    assert result.id == "ws-1"


def test_get_workspace_returns_none_when_absent(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    mocker.patch.object(kal_client_mock, "_get", return_value=None)

    assert kal_client_mock.workspace.get_workspace() is None


def test_get_members(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    members = [
        {"id": "u-1", "full_name": "Ada", "email": "ada@example.com"},
        {"id": "u-2", "full_name": "Grace", "email": "grace@example.com"},
    ]
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=members)

    result = kal_client_mock.workspace.get_members()

    mock_get.assert_called_once_with("/workspaces/members")
    assert all(isinstance(m, WorkspaceUser) for m in result)
    assert all(m._client is kal_client_mock for m in result)
    assert [m.id for m in result] == ["u-1", "u-2"]


def test_get_members_by_ids_filters(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    members = [{"id": "u-1"}, {"id": "u-2"}, {"id": "u-3"}]
    mocker.patch.object(kal_client_mock, "_get", return_value=members)

    result = kal_client_mock.workspace.get_members_by_ids(["u-1", "u-3"])

    assert {m.id for m in result} == {"u-1", "u-3"}


def test_get_groups(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    groups = [{"id": "g-1", "group_name": "Chem"}, {"id": "g-2", "group_name": "Bio"}]
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=groups)

    result = kal_client_mock.workspace.get_groups()

    mock_get.assert_called_once_with("/workspaces/groups")
    assert all(isinstance(g, WorkspaceGroup) for g in result)
    assert all(g._client is kal_client_mock for g in result)


def test_get_events_returns_models(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    events = [
        {"id": "ev-1", "event_type": "create"},
        {"id": "ev-2", "event_type": "update"},
    ]
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=events)

    result = kal_client_mock.workspace.get_events(event_types=["create", "update"])

    assert all(isinstance(e, WorkspaceEvent) for e in result)
    assert all(e._client is kal_client_mock for e in result)
    assert [e.id for e in result] == ["ev-1", "ev-2"]


def test_get_events_serializes_datetime_params(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=[])
    after = datetime(2026, 1, 1, tzinfo=timezone.utc)

    kal_client_mock.workspace.get_events(
        after_date=after, resource_type="record", event_types=["create", "update"]
    )

    sent_params = mock_get.call_args[0][1]
    # datetime -> bare ISO string (no surrounding JSON quotes, no space separator)
    assert sent_params["after_date"] == "2026-01-01T00:00:00+00:00"
    # plain strings pass through unquoted
    assert sent_params["resource_type"] == "record"
    # lists are JSON-encoded, matching the search endpoints
    assert sent_params["event_types"] == '["create", "update"]'


def test_get_workspace_does_not_cache_none(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """A transiently-absent workspace is not cached, so the next call retries."""
    mock_get = mocker.patch.object(kal_client_mock, "_get", side_effect=[None, {"id": "ws-1"}])

    assert kal_client_mock.workspace.get_workspace() is None
    result = kal_client_mock.workspace.get_workspace()

    assert result is not None
    assert result.id == "ws-1"
    assert mock_get.call_count == 2


def test_get_events_empty(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    mocker.patch.object(kal_client_mock, "_get", return_value=None)

    assert kal_client_mock.workspace.get_events() == []
