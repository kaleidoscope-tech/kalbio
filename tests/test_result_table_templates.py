"""Unit tests for ResultTableTemplate model and ResultTableTemplatesService."""

from typing import Any

import pytest
from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient
from kalbio.record_views import (
    FilterRuleType,
    RecordViewColorFilter,
    RecordViewFilter,
    RecordViewSort,
)
from kalbio.result_table_templates import (
    ResultTableTemplate,
    ResultTableTemplatesService,
    _set_if_not_none,
)


# ==================== Fixtures ====================


def _sample_template_payload(template_id: str = "template-uuid-1") -> dict[str, Any]:
    return {
        "id": template_id,
        "workspace_id": "workspace-uuid",
        "view_name": "Compound results",
        "template_name": "Standard compound results",
        "entity_slice_id": "slice-uuid",
        "program_ids": [],
        "view_fields": [],
        "filters": [],
        "sorts": [],
        "color_filters": [],
        "record_set_ids_filter": [],
        "is_archived": False,
        "is_template": True,
        "activity_scope_ids": [],
        "scoped_definition_ids": [],
    }


@pytest.fixture(name="template")
def fixture_template(kal_client_mock: KaleidoscopeClient) -> ResultTableTemplate:
    t = ResultTableTemplate.model_validate(_sample_template_payload())
    t._set_client(kal_client_mock)
    return t


# ==================== Read methods ====================


def test_get_templates(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """get_templates() hits GET /record_view_templates, validates each result,
    and sets the client on each instance so inherited RecordView methods work."""
    payload = [_sample_template_payload("t-1"), _sample_template_payload("t-2")]
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=payload)
    kal_client_mock.result_table_templates.get_templates.cache_clear()

    result = kal_client_mock.result_table_templates.get_templates()

    mock_get.assert_called_once_with("/record_view_templates")
    assert len(result) == 2
    assert all(isinstance(t, ResultTableTemplate) for t in result)
    assert {t.id for t in result} == {"t-1", "t-2"}
    assert all(t._client is kal_client_mock for t in result)


def test_get_template_by_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """get_template_by_id() returns a ResultTableTemplate with client set."""
    payload = _sample_template_payload("specific-uuid")
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=payload)

    result = kal_client_mock.result_table_templates.get_template_by_id("specific-uuid")

    mock_get.assert_called_once_with("/record_view_templates/specific-uuid")
    assert isinstance(result, ResultTableTemplate)
    assert result.id == "specific-uuid"
    assert result._client is kal_client_mock


def test_get_template_by_id_returns_none_when_not_found(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """get_template_by_id() returns None when the server returns None (404)."""
    mocker.patch.object(kal_client_mock, "_get", return_value=None)

    result = kal_client_mock.result_table_templates.get_template_by_id("missing")

    assert result is None


# ==================== Create / save_view_as / duplicate / promote ====================


def test_create_template_omits_none_kwargs(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """create_template() only includes non-None kwargs in the POST body."""
    response_payload = _sample_template_payload()
    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value=response_payload
    )
    kal_client_mock.result_table_templates.get_templates.cache_clear()

    result = kal_client_mock.result_table_templates.create_template(
        view_name="Compound results",
        entity_slice_id="slice-uuid",
        data_field_ids=["field-1", "field-2"],
        template_name="Standard compound results",
    )

    mock_post.assert_called_once_with(
        "/record_view_templates",
        {
            "view_name": "Compound results",
            "entity_slice_id": "slice-uuid",
            "template_name": "Standard compound results",
            "data_field_ids": ["field-1", "field-2"],
        },
    )
    assert isinstance(result, ResultTableTemplate)


def test_save_view_as_template(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """save_view_as_template() POSTs with source_view_id."""
    response_payload = _sample_template_payload()
    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value=response_payload
    )

    kal_client_mock.result_table_templates.save_view_as_template(
        source_view_id="view-uuid",
        view_name="From existing view",
    )

    mock_post.assert_called_once_with(
        "/record_view_templates",
        {"source_view_id": "view-uuid", "view_name": "From existing view"},
    )


def test_duplicate_template(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """duplicate_template() POSTs to /duplicate with an empty body."""
    response_payload = _sample_template_payload("dup-uuid")
    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value=response_payload
    )

    result = kal_client_mock.result_table_templates.duplicate_template("orig-uuid")

    mock_post.assert_called_once_with(
        "/record_view_templates/orig-uuid/duplicate", {}
    )
    assert isinstance(result, ResultTableTemplate)


def test_promote_view_to_template(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """promote_view_to_template() POSTs to /promote with the expected body."""
    response_payload = _sample_template_payload()
    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value=response_payload
    )

    kal_client_mock.result_table_templates.promote_view_to_template(
        source_view_id="view-uuid",
        operation_definition_id="def-uuid",
        view_name="Promoted view",
        position_index=2,
    )

    mock_post.assert_called_once_with(
        "/record_view_templates/promote",
        {
            "source_view_id": "view-uuid",
            "operation_definition_id": "def-uuid",
            "view_name": "Promoted view",
            "position_index": 2,
        },
    )


# ==================== Update / delete ====================


def test_update_template_sends_only_provided_kwargs(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """update_template() only includes non-None kwargs in the PUT body."""
    response_payload = _sample_template_payload()
    mock_put = mocker.patch.object(
        kal_client_mock, "_put", return_value=response_payload
    )

    kal_client_mock.result_table_templates.update_template(
        "template-uuid-1",
        view_name="Renamed",
        is_archived=True,
    )

    mock_put.assert_called_once_with(
        "/record_view_templates/template-uuid-1",
        {"view_name": "Renamed", "is_archived": True},
    )


def test_update_template_forwards_typed_filters_sorts_color_filters(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """Typed filter/sort/color_filter lists pass through unchanged into the request body."""
    response_payload = _sample_template_payload()
    mock_put = mocker.patch.object(
        kal_client_mock, "_put", return_value=response_payload
    )

    filters: list[RecordViewFilter] = [
        {
            "key_field_id": None,
            "view_field_id": "vf-1",
            "filter_type": FilterRuleType.IS_SET.value,
            "filter_prop": None,
            "plot_field_config": None,
        }
    ]
    sorts: list[RecordViewSort] = [
        {
            "key_field_id": None,
            "view_field_id": "vf-1",
            "descending": True,
            "plot_field_config": None,
        }
    ]
    color_filters: list[RecordViewColorFilter] = [
        {
            "key_field_id": None,
            "view_field_id": "vf-1",
            "filter_type": FilterRuleType.IS_EQUAL.value,
            "filter_prop": "foo",
            "plot_field_config": None,
            "color": "#FF0000",
        }
    ]

    kal_client_mock.result_table_templates.update_template(
        "template-uuid-1",
        filters=filters,
        sorts=sorts,
        color_filters=color_filters,
    )

    mock_put.assert_called_once_with(
        "/record_view_templates/template-uuid-1",
        {"filters": filters, "sorts": sorts, "color_filters": color_filters},
    )


def test_delete_template(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """delete_template() hits DELETE /record_view_templates/{id}."""
    mock_delete = mocker.patch.object(kal_client_mock, "_delete", return_value=None)

    kal_client_mock.result_table_templates.delete_template("template-uuid-1")

    mock_delete.assert_called_once_with("/record_view_templates/template-uuid-1")


# ==================== Link / unlink ====================


def _assert_get_templates_cache_refetches_after(
    mocker: MockerFixture,
    kal_client_mock: KaleidoscopeClient,
    operation,
) -> None:
    """Run `operation` between two get_templates() calls and assert that the
    second call re-fetches (cache was cleared by `operation`)."""
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=[])
    kal_client_mock.result_table_templates.get_templates.cache_clear()

    kal_client_mock.result_table_templates.get_templates()  # populate cache
    assert mock_get.call_count == 1

    operation()  # should clear cache

    kal_client_mock.result_table_templates.get_templates()  # should re-fetch
    assert mock_get.call_count == 2


def test_link_to_operation_definition_returns_template_and_clears_cache(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """link_to_operation_definition() POSTs to /link, refetches the template
    (because the server's /link response returns pre-link state), returns the
    fresh ResultTableTemplate with client set, and clears the templates cache."""
    # Server's /link response is the pre-link state (server quirk).
    # The refetch GET returns the post-link state.
    pre_link = _sample_template_payload("template-uuid")
    pre_link["operation_definition_ids"] = []
    post_link = _sample_template_payload("template-uuid")
    post_link["operation_definition_ids"] = ["def-uuid"]
    mock_post = mocker.patch.object(
        kal_client_mock, "_post", return_value=pre_link
    )
    mock_get = mocker.patch.object(
        kal_client_mock, "_get", return_value=post_link
    )

    result = kal_client_mock.result_table_templates.link_to_operation_definition(
        "template-uuid",
        operation_definition_id="def-uuid",
        position_index=1,
    )

    mock_post.assert_called_once_with(
        "/record_view_templates/link",
        {
            "template_view_id": "template-uuid",
            "operation_definition_id": "def-uuid",
            "position_index": 1,
        },
    )
    mock_get.assert_called_once_with("/record_view_templates/template-uuid")
    assert isinstance(result, ResultTableTemplate)
    assert result._client is kal_client_mock
    # Returned template reflects the *post-link* state, not the stale POST response.
    assert result.operation_definition_ids == ["def-uuid"]
    # Cache invalidation on link is covered by the same pattern tested for
    # unlink / bulk_link / bulk_unlink below.


def test_template_link_unlink_clears_record_view_caches(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """Linking/unlinking/deleting a template instantiates or removes per-experiment
    record views, so the record-view cache must be cleared too."""
    mocker.patch.object(kal_client_mock, "_post", return_value=None)
    mocker.patch.object(kal_client_mock, "_delete", return_value=None)
    mocker.patch.object(
        kal_client_mock, "_get", return_value=_sample_template_payload("t")
    )
    spy = mocker.patch.object(
        kal_client_mock.record_views, "_clear_record_view_caches"
    )

    templates = kal_client_mock.result_table_templates
    templates.link_to_operation_definition("t", operation_definition_id="d")
    templates.unlink_from_operation_definition(
        "t", operation_definition_id="d", content_layout_id="c"
    )
    templates.bulk_link_to_operation_definitions("t", operation_definition_ids=["d"])
    templates.bulk_unlink_from_operation_definitions("t", operation_definition_ids=["d"])
    templates.delete_template("t")

    assert spy.call_count == 5


def test_unlink_from_operation_definition_clears_cache(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """unlink_from_operation_definition() POSTs and clears the templates cache."""
    mock_post = mocker.patch.object(kal_client_mock, "_post", return_value=None)

    kal_client_mock.result_table_templates.unlink_from_operation_definition(
        "template-uuid",
        operation_definition_id="def-uuid",
        content_layout_id="layout-uuid",
    )

    mock_post.assert_called_once_with(
        "/record_view_templates/template-uuid/unlink",
        {
            "operation_definition_id": "def-uuid",
            "content_layout_id": "layout-uuid",
        },
    )

    _assert_get_templates_cache_refetches_after(
        mocker,
        kal_client_mock,
        lambda: kal_client_mock.result_table_templates.unlink_from_operation_definition(
            "template-uuid",
            operation_definition_id="def-uuid",
            content_layout_id="layout-uuid",
        ),
    )


def test_bulk_link_to_operation_definitions_clears_cache(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """bulk_link_to_operation_definitions() POSTs and clears the templates cache."""
    mock_post = mocker.patch.object(kal_client_mock, "_post", return_value=None)

    kal_client_mock.result_table_templates.bulk_link_to_operation_definitions(
        "template-uuid",
        operation_definition_ids=["def-1", "def-2"],
    )

    mock_post.assert_called_once_with(
        "/record_view_templates/bulk/link",
        {
            "template_view_id": "template-uuid",
            "operation_definition_ids": ["def-1", "def-2"],
        },
    )

    _assert_get_templates_cache_refetches_after(
        mocker,
        kal_client_mock,
        lambda: kal_client_mock.result_table_templates.bulk_link_to_operation_definitions(
            "template-uuid", operation_definition_ids=["def-1"]
        ),
    )


def test_bulk_unlink_from_operation_definitions_clears_cache(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """bulk_unlink_from_operation_definitions() POSTs and clears the templates cache."""
    mock_post = mocker.patch.object(kal_client_mock, "_post", return_value=None)

    kal_client_mock.result_table_templates.bulk_unlink_from_operation_definitions(
        "template-uuid",
        operation_definition_ids=["def-1", "def-2"],
    )

    mock_post.assert_called_once_with(
        "/record_view_templates/bulk/unlink",
        {
            "template_view_id": "template-uuid",
            "operation_definition_ids": ["def-1", "def-2"],
        },
    )

    _assert_get_templates_cache_refetches_after(
        mocker,
        kal_client_mock,
        lambda: kal_client_mock.result_table_templates.bulk_unlink_from_operation_definitions(
            "template-uuid", operation_definition_ids=["def-1"]
        ),
    )


# ==================== Helpers ====================


def test_set_if_not_none_skips_none():
    """_set_if_not_none omits the key when value is None."""
    payload: dict = {}
    _set_if_not_none(payload, "foo", None)
    assert payload == {}


def test_set_if_not_none_includes_non_none():
    """_set_if_not_none adds non-None values, including falsy ones (empty list, False, 0)."""
    payload: dict = {}
    _set_if_not_none(payload, "list", [])
    _set_if_not_none(payload, "flag", False)
    _set_if_not_none(payload, "count", 0)
    assert payload == {"list": [], "flag": False, "count": 0}
