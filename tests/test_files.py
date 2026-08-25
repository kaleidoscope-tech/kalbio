"""
Unit tests for the FilesService.download_file() method of the KaleidoscopeClient.

This module tests the file download functionality, verifying that:
- GET requests are made to the correct endpoints
- The activity-scoped endpoint is used when activity_id is provided
- The default /files/{file_id} endpoint is used otherwise
- Filename defaults to file_id when not provided
- Destination defaults to current directory when not provided
- None is returned on failure
"""

import pytest
from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient


# ==================== FilesService Methods ====================


def test_download_file_basic(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FilesService.download_file():
    - Makes the GET request to /files/{file_id}
    - Uses file_id as filename when filename is not provided
    - Uses current directory as destination when not provided
    """
    file_id = "test-file-id"
    expected_path = file_id

    mock_get_file = mocker.patch.object(
        kal_client_mock, "_get_file", return_value=expected_path
    )

    result = kal_client_mock.files.download_file(file_id=file_id)

    mock_get_file.assert_called_once_with(f"/files/{file_id}", expected_path)
    assert result == expected_path


def test_download_file_with_filename(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FilesService.download_file():
    - Uses the provided filename instead of file_id
    """
    file_id = "test-file-id"
    filename = "data.csv"
    expected_path = filename

    mock_get_file = mocker.patch.object(
        kal_client_mock, "_get_file", return_value=expected_path
    )

    result = kal_client_mock.files.download_file(file_id=file_id, filename=filename)

    mock_get_file.assert_called_once_with(f"/files/{file_id}", expected_path)
    assert result == expected_path


def test_download_file_with_destination(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, tmp_path
):
    """
    Test that FilesService.download_file():
    - Uses the provided destination directory
    """
    file_id = "test-file-id"
    filename = "data.csv"
    destination = str(tmp_path)
    expected_path = f"{destination}/{filename}"

    mock_get_file = mocker.patch.object(
        kal_client_mock, "_get_file", return_value=expected_path
    )

    result = kal_client_mock.files.download_file(
        file_id=file_id, filename=filename, destination=destination
    )

    mock_get_file.assert_called_once_with(f"/files/{file_id}", expected_path)
    assert result == expected_path


def test_download_file_with_activity_id(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FilesService.download_file():
    - Uses the activity-scoped endpoint when activity_id is provided
    """
    file_id = "test-file-id"
    activity_id = "act-123"
    filename = "data.csv"
    expected_path = filename

    mock_get_file = mocker.patch.object(
        kal_client_mock, "_get_file", return_value=expected_path
    )

    result = kal_client_mock.files.download_file(
        file_id=file_id, filename=filename, activity_id=activity_id
    )

    mock_get_file.assert_called_once_with(
        f"/activities/{activity_id}/file/{file_id}", expected_path
    )
    assert result == expected_path


def test_download_file_with_all_parameters(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, tmp_path
):
    """
    Test that FilesService.download_file():
    - Correctly handles all parameters together
    """
    file_id = "test-file-id"
    filename = "results.csv"
    destination = str(tmp_path)
    activity_id = "act-456"
    expected_path = f"{destination}/{filename}"

    mock_get_file = mocker.patch.object(
        kal_client_mock, "_get_file", return_value=expected_path
    )

    result = kal_client_mock.files.download_file(
        file_id=file_id,
        filename=filename,
        destination=destination,
        activity_id=activity_id,
    )

    mock_get_file.assert_called_once_with(
        f"/activities/{activity_id}/file/{file_id}", expected_path
    )
    assert result == expected_path


def test_download_file_sanitizes_traversal_filename(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient, tmp_path
):
    """
    Test that FilesService.download_file():
    - Reduces a server-supplied filename to a bare name so a value containing
      ".." or an absolute path cannot write outside the destination directory.
    """
    mock_get_file = mocker.patch.object(
        kal_client_mock, "_get_file", return_value="ok"
    )

    kal_client_mock.files.download_file(
        file_id="fid", filename="../../etc/evil.csv", destination=str(tmp_path)
    )
    assert mock_get_file.call_args[0][1] == str(tmp_path / "evil.csv")

    kal_client_mock.files.download_file(
        file_id="fid", filename="/etc/abs.csv", destination=str(tmp_path)
    )
    assert mock_get_file.call_args[0][1] == str(tmp_path / "abs.csv")


def test_download_file_returns_none_on_failure(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FilesService.download_file():
    - Returns None when file download fails
    """
    file_id = "test-file-id"

    mocker.patch.object(kal_client_mock, "_get_file", return_value=None)

    result = kal_client_mock.files.download_file(file_id=file_id)

    assert result is None


def test_download_file_propagates_exceptions(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    """
    Test that FilesService.download_file():
    - Propagates exceptions raised by the underlying HTTP call
      (e.g. KalbioAPIError on 4xx/5xx, or other request errors)
    """
    file_id = "test-file-id"

    mocker.patch.object(
        kal_client_mock, "_get_file", side_effect=Exception("connection error")
    )

    with pytest.raises(Exception, match="connection error"):
        kal_client_mock.files.download_file(file_id=file_id)
