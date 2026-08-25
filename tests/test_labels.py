"""Unit tests for LabelsService."""

from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient
from kalbio.labels import Label


def test_get_labels(mocker: MockerFixture, kal_client_mock: KaleidoscopeClient):
    labels = [
        {"id": "lab-1", "label_name": "Priority"},
        {"id": "lab-2", "label_name": "Review"},
    ]
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=labels)

    result = kal_client_mock.labels.get_labels()

    mock_get.assert_called_once_with("/activity_labels")
    assert all(isinstance(label, Label) for label in result)
    assert all(label._client is kal_client_mock for label in result)
    assert [label.id for label in result] == ["lab-1", "lab-2"]


def test_get_labels_by_ids_filters(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    labels = [{"id": "lab-1"}, {"id": "lab-2"}, {"id": "lab-3"}]
    mocker.patch.object(kal_client_mock, "_get", return_value=labels)

    result = kal_client_mock.labels.get_labels_by_ids(["lab-2", "lab-3"])

    assert {label.id for label in result} == {"lab-2", "lab-3"}
