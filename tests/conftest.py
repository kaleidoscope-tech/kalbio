"""
Pytest configuration and fixtures for kalbio testing.

This module provides shared fixtures and mock data utilities for testing the
Kaleidoscope client library. It includes a mocked client fixture that prevents
actual API calls during testing and a MockData class that provides access to
pre-loaded test data from JSON files.

The module uses pytest-mock for mocking HTTP methods and provides utilities
for caching and loading test data to improve test performance.

Fixtures:
    kal_client_mock: A mocked KaleidoscopeClient instance with HTTP methods
        patched to prevent actual network calls.

Classes:
    MockData: Container class providing static mock data loaded from JSON files
        for various application entities.

"""

import copy
import json
import os
from typing import Any, Final
import pytest

from pytest_mock import MockerFixture
from kalbio.client import _TokenResponse, KaleidoscopeClient

# Params for using the api to create an experiment in Kaleidoscope using the client
# These are only used for test fixture initialization and are mocked out during actual tests
_KALEIDOSCOPE_API_CLIENT_ID = os.getenv("KALEIDOSCOPE_API_CLIENT_ID", "test-client-id")
_KALEIDOSCOPE_API_CLIENT_SECRET = os.getenv(
    "KALEIDOSCOPE_API_CLIENT_SECRET", "test-client-secret"
)
_API_URL = os.getenv("KALEIDOSCOPE_API_URL", "https://api.kaleidoscope.bio")


@pytest.fixture
def kal_client_mock(mocker: MockerFixture):
    """
    Fixture that provides a mocked instance of KaleidoscopeClient for testing.
    This fixture patches the internal HTTP methods of the KaleidoscopeClient
    (_post, _post_file, _put, _get, _get_file) to raise NotImplementedError,
    preventing actual network calls during tests. The client is, however, initialized
    with the required API credentials and URL.
    Args:
        mocker (MockerFixture): The pytest-mock fixture used to patch methods.
    Yields:
        kal_client_mock (KaleidoscopeClient): The fixture for the mocked client instance.
    """
    mocker.patch.object(
        KaleidoscopeClient, "_get_auth_token", return_value="fake-token"
    )

    client = KaleidoscopeClient(
        _KALEIDOSCOPE_API_CLIENT_ID, _KALEIDOSCOPE_API_CLIENT_SECRET, _API_URL
    )

    client._update_auth_tokens(
        _TokenResponse(
            access_token="access_token",
            refresh_token="refresh_token",
            expires_in=int(1e9),
        )
    )

    mocker.patch.object(
        client, "_post", side_effect=NotImplementedError("KaleidoscopeClient._post")
    )
    mocker.patch.object(
        client,
        "_post_file",
        side_effect=NotImplementedError("KaleidoscopeClient._post_file"),
    )
    mocker.patch.object(
        client, "_put", side_effect=NotImplementedError("KaleidoscopeClient._put")
    )
    mocker.patch.object(
        client, "_get", side_effect=NotImplementedError("KaleidoscopeClient._get")
    )
    mocker.patch.object(
        client,
        "_get_file",
        side_effect=NotImplementedError("KaleidoscopeClient._get_file"),
    )
    mocker.patch.object(
        client,
        "_post_no_content",
        side_effect=NotImplementedError("KaleidoscopeClient._post_no_content"),
    )
    mocker.patch.object(
        client, "_delete", side_effect=NotImplementedError("KaleidoscopeClient._delete")
    )

    yield client


_data_cache: dict[str, Any] = {}


def _load_data(file_name: str) -> Any:
    # Deep-copy every access: fixtures are nested dicts, and tests mutate them
    # in place; a shallow copy would leak those mutations across tests.
    if file_name not in _data_cache:
        with open(f"tests/responses/{file_name}.json", encoding="utf-8") as f:
            _data_cache[file_name] = json.load(f)

    return copy.deepcopy(_data_cache[file_name])


# @dataclass(frozen=True)
class _MockData:
    """
    A container class for mock data used in testing.

    This class provides static mock data loaded from JSON files for various entities
    in the application. All attributes are class-level constants loaded at module import time.

    Attributes:
        EXPERIMENTS (list[dict]): Mock data for experiments.
        EXPERIMENT_TYPES (list[dict]): Mock data for experiment types.
        RECORDS (list[dict]): Mock data for records.
        RECORD_VALUES_DRUG_1 (list[dict]): Mock data for record values related to drug 1.
        TASKS (list[dict]): Mock data for tasks.
        RECORD_VIEWS (list[dict]): Mock data for record views.
        ENTITY_TYPES (list[dict]): Mock data for entity types.
        KEY_FIELDS (list[dict]): Mock data for key fields.
        DATA_FIELDS (list[dict]): Mock data for data fields.
        PROGRAMS (list[dict]): Mock data for programs.
    """

    EXPERIMENTS: Final[list[dict]] = _load_data("experiments")
    EXPERIMENT_TYPES: Final[list[dict]] = _load_data("experiment_types")
    RECORDS: Final[list[dict]] = _load_data("records")
    RECORD_VALUES_DRUG_1: Final[list[dict]] = _load_data("record_values_drug_1")
    TASKS: Final[list[dict]] = _load_data("tasks")
    RECORD_VIEWS: Final[list[dict]] = _load_data("record_views")
    ENTITY_TYPES: Final[list[dict]] = _load_data("entity_types")
    KEY_FIELDS: Final[list[dict]] = _load_data("key_fields")
    DATA_FIELDS: Final[list[dict]] = _load_data("data_fields")
    PROGRAMS: Final[list[dict]] = _load_data("programs")
