"""Unit tests for DashboardsService and the Dashboard model.

Covers dashboard retrieval, category hydration, and the membership mutators
(add/remove record/set), which update local state and invalidate the dashboards
cache.
"""

import pytest
from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient
from kalbio.dashboards import Dashboard, DashboardCategory


@pytest.fixture(name="dashboard")
def fixture_dashboard(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
) -> Dashboard:
    """A Dashboard obtained through the service, so its client is attached."""
    data = [{"id": "dash-1", "dashboard_name": "Overview", "record_ids": ["rec-0"]}]
    mocker.patch.object(kal_client_mock, "_get", return_value=data)
    dashboard = kal_client_mock.dashboards.get_dashboards()[0]
    kal_client_mock.dashboards.get_dashboards.cache_clear()
    return dashboard


def test_get_dashboards(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    data = [
        {"id": "dash-1", "dashboard_name": "Overview"},
        {"id": "dash-2", "dashboard_name": "Assays"},
    ]
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=data)

    result = kal_client_mock.dashboards.get_dashboards()

    mock_get.assert_called_once_with("/dashboards")
    assert all(isinstance(d, Dashboard) for d in result)
    assert all(d._client is kal_client_mock for d in result)
    assert [d.id for d in result] == ["dash-1", "dash-2"]


def test_get_categories_returns_models(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, dashboard: Dashboard
):
    categories = [
        {"id": "cat-1", "dashboard_id": "dash-1", "category_name": "Yield"},
        {"id": "cat-2", "dashboard_id": "dash-1", "category_name": "Purity"},
    ]
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=categories)

    result = dashboard.get_categories()

    mock_get.assert_called_once_with("/dashboards/dash-1/categories")
    assert all(isinstance(c, DashboardCategory) for c in result)
    assert all(c._client is kal_client_mock for c in result)


def test_add_category_returns_model(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, dashboard: Dashboard
):
    mocker.patch.object(
        kal_client_mock,
        "_post",
        return_value={"id": "cat-9", "category_name": "New"},
    )

    result = dashboard.add_category(
        category_name="New",
        operation_definition_ids=[],
        label_ids=[],
        field_ids=[],
    )

    assert isinstance(result, DashboardCategory)
    assert result._client is kal_client_mock
    assert result.id == "cat-9"


def test_add_record_updates_state_without_touching_response(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, dashboard: Dashboard
):
    # The server returns a dict body; the mutator must not dereference it as a
    # model (the prior bug did `resp.record_ids` and raised AttributeError).
    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value={"unrelated": "body"}
    )

    dashboard.add_record("rec-1")

    mock_post.assert_called_once_with(
        "/dashboards/dash-1/records", {"record_id": "rec-1"}
    )
    assert "rec-1" in dashboard.record_ids


def test_add_set_updates_state(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, dashboard: Dashboard
):
    mocker.patch.object(kal_client_mock, "_post", return_value={"unrelated": "body"})

    dashboard.add_set("set-1")

    assert "set-1" in dashboard.record_set_ids


def test_remove_record_updates_state(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, dashboard: Dashboard
):
    mocker.patch.object(kal_client_mock, "_delete", return_value=None)

    dashboard.remove_record("rec-0")

    assert "rec-0" not in dashboard.record_ids


def test_membership_mutation_invalidates_dashboards_cache(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    data = [{"id": "dash-1", "record_ids": []}]
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=data)
    mocker.patch.object(kal_client_mock, "_post", return_value={})

    dashboard = kal_client_mock.dashboards.get_dashboards()[0]  # populates cache
    dashboard.add_record("rec-1")  # must clear the cache
    kal_client_mock.dashboards.get_dashboards()  # refetches

    assert mock_get.call_count == 2
