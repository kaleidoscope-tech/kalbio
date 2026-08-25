"""Tests for the shared read-cache controls on KaleidoscopeClient.

Covers the three escape hatches:
- `client.clear_caches()` drops every cached read across services.
- `use_cache=False` bypasses the cache for a single read and refreshes it.
- `client.cache_disabled()` bypasses reads for the duration of the block.
"""

from typing import Any

import pytest
from pytest_mock import MockerFixture

from kalbio._cache import cached_model_property
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import KaleidoscopeClient


@pytest.fixture(name="client")
def fixture_client() -> KaleidoscopeClient:
    """A client whose HTTP layer is mocked per test (no auth/network)."""
    return KaleidoscopeClient("test-id", "test-secret", "https://example.test")


# ==================== @cached service methods ====================


def test_service_read_is_cached(mocker: MockerFixture, client: KaleidoscopeClient):
    """A repeated read hits the server once."""
    mock_get = mocker.patch.object(client, "_get", return_value=[])

    client.programs.get_programs()
    client.programs.get_programs()

    assert mock_get.call_count == 1


def test_clear_caches_forces_refetch(
    mocker: MockerFixture, client: KaleidoscopeClient
):
    """clear_caches() drops cached reads so the next call refetches."""
    mock_get = mocker.patch.object(client, "_get", return_value=[])

    client.programs.get_programs()
    assert mock_get.call_count == 1

    client.clear_caches()
    client.programs.get_programs()
    assert mock_get.call_count == 2


def test_clear_caches_spans_multiple_services(
    mocker: MockerFixture, client: KaleidoscopeClient
):
    """clear_caches() reaches every service, not just one."""
    mock_get = mocker.patch.object(client, "_get", return_value=[])

    client.programs.get_programs()
    client.entity_types.get_types()
    assert mock_get.call_count == 2

    client.clear_caches()
    client.programs.get_programs()
    client.entity_types.get_types()
    assert mock_get.call_count == 4


def test_use_cache_false_bypasses_and_refreshes(
    mocker: MockerFixture, client: KaleidoscopeClient
):
    """use_cache=False refetches, and stores the fresh value for later reads."""
    mock_get = mocker.patch.object(client, "_get", return_value=[])

    client.programs.get_programs()
    client.programs.get_programs()
    assert mock_get.call_count == 1  # second read served from cache

    client.programs.get_programs(use_cache=False)
    assert mock_get.call_count == 2  # bypassed the cache

    client.programs.get_programs()
    assert mock_get.call_count == 2  # bypass refreshed the cache


# ==================== cache_disabled() context manager ====================


def test_cache_disabled_bypasses_within_block(
    mocker: MockerFixture, client: KaleidoscopeClient
):
    """Every read inside the block hits the server; afterwards caching resumes."""
    mock_get = mocker.patch.object(client, "_get", return_value=[])

    client.programs.get_programs()
    assert mock_get.call_count == 1

    with client.cache_disabled():
        client.programs.get_programs()
        client.programs.get_programs()
    assert mock_get.call_count == 3  # both reads bypassed

    client.programs.get_programs()
    assert mock_get.call_count == 3  # cache repopulated in the block


def test_cache_disabled_restores_nested_state(client: KaleidoscopeClient):
    """Nested blocks leave the flag exactly as they found it."""
    assert client._is_cache_disabled() is False

    with client.cache_disabled():
        assert client._is_cache_disabled() is True
        with client.cache_disabled():
            assert client._is_cache_disabled() is True
        assert client._is_cache_disabled() is True

    assert client._is_cache_disabled() is False


# ==================== record-lookup maps ====================


def test_clear_caches_clears_record_maps(client: KaleidoscopeClient):
    """clear_caches() empties the record-lookup TTLCache maps."""
    client.clear_caches()
    client.records._records_uuid_map["rec-1"] = None
    client.records._records_key_field_map[frozenset()] = None

    client.clear_caches()

    assert "rec-1" not in client.records._records_uuid_map
    assert frozenset() not in client.records._records_key_field_map


def test_get_record_by_id_use_cache_false_bypasses_map(
    mocker: MockerFixture, client: KaleidoscopeClient
):
    """use_cache=False skips a cached record and refetches from the server."""
    client.clear_caches()
    client.records._records_uuid_map["rec-1"] = None  # cached "not found"
    mock_get = mocker.patch.object(client, "_get", return_value=None)

    assert client.records.get_record_by_id("rec-1") is None
    assert mock_get.call_count == 0  # served from the cache

    assert client.records.get_record_by_id("rec-1", use_cache=False) is None
    assert mock_get.call_count == 1  # bypassed the cache


def test_cache_disabled_bypasses_record_map(
    mocker: MockerFixture, client: KaleidoscopeClient
):
    """Record reads inside cache_disabled() ignore the lookup map."""
    client.clear_caches()
    client.records._records_uuid_map["rec-1"] = None
    mock_get = mocker.patch.object(client, "_get", return_value=None)

    with client.cache_disabled():
        client.records.get_record_by_id("rec-1")

    assert mock_get.call_count == 1


def test_record_maps_are_isolated_between_clients():
    """Record-lookup caches must not be shared across client instances."""
    client_a = KaleidoscopeClient("id-a", "secret-a", "https://example.test")
    client_b = KaleidoscopeClient("id-b", "secret-b", "https://example.test")

    client_a.records._records_uuid_map["rec-1"] = None

    assert "rec-1" in client_a.records._records_uuid_map
    assert "rec-1" not in client_b.records._records_uuid_map
    assert (
        client_a.records._records_uuid_map is not client_b.records._records_uuid_map
    )


# ==================== write-through invalidation ====================


def test_create_activity_invalidates_record_views(
    mocker: MockerFixture, client: KaleidoscopeClient
):
    """Creating an operation drops the cached record-views snapshot.

    Server-side, a new operation gets its own record views; a stale cache is
    why `activity.record_views` came back empty for a freshly created activity.
    """
    mock_get = mocker.patch.object(client, "_get", return_value=[])
    mocker.patch.object(client, "_post", return_value=[{"id": "act-1"}])

    client.record_views.get_record_views()
    client.record_views.get_record_views()
    assert mock_get.call_count == 1  # second read served from cache

    client.activities.create_activity(title="Exp", activity_type="experiment")

    client.record_views.get_record_views()
    assert mock_get.call_count == 2  # create_activity dropped the cached views


# ==================== model-level cached properties ====================


class _CachingModel(_KaleidoscopeBaseModel):
    """Minimal model exercising cached_model_property against the HTTP layer."""

    @cached_model_property
    def thing(self) -> Any:
        return self._client._get("/thing")


def _model_with_client(client: KaleidoscopeClient) -> _CachingModel:
    model = _CachingModel(id="m1")
    model._set_client(client)
    return model


def test_model_cached_property_caches(
    mocker: MockerFixture, client: KaleidoscopeClient
):
    """A model cached property computes once and reuses the stored value."""
    model = _model_with_client(client)
    mock_get = mocker.patch.object(client, "_get", side_effect=[1, 2, 3])

    assert model.thing == 1
    assert model.thing == 1
    assert mock_get.call_count == 1


def test_model_clear_caches_recomputes(
    mocker: MockerFixture, client: KaleidoscopeClient
):
    """clear_caches() on the model drops cached properties so they recompute."""
    model = _model_with_client(client)
    mock_get = mocker.patch.object(client, "_get", side_effect=[1, 2, 3])

    assert model.thing == 1
    model.clear_caches()
    assert model.thing == 2
    assert mock_get.call_count == 2


def test_model_cached_property_respects_cache_disabled(
    mocker: MockerFixture, client: KaleidoscopeClient
):
    """Inside cache_disabled() a model cached property recomputes on each access."""
    model = _model_with_client(client)
    mock_get = mocker.patch.object(client, "_get", side_effect=[1, 2, 3])

    assert model.thing == 1
    with client.cache_disabled():
        assert model.thing == 2
        assert model.thing == 3
    assert mock_get.call_count == 3

    assert model.thing == 3  # value stored during the block is reused afterward
    assert mock_get.call_count == 3
