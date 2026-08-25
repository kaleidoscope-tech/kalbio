"""Unit tests for PropertyFieldsService."""

from pytest_mock import MockerFixture

from kalbio.client import KaleidoscopeClient
from kalbio.property_fields import PropertyField


def test_get_property_fields(
    mocker: MockerFixture, kal_client_mock: KaleidoscopeClient
):
    fields = [
        {"id": "pf-1", "property_name": "Molecular Weight", "field_type": "number"},
        {"id": "pf-2", "property_name": "Notes", "field_type": "text"},
    ]
    mock_get = mocker.patch.object(kal_client_mock, "_get", return_value=fields)

    result = kal_client_mock.property_fields.get_property_fields()

    mock_get.assert_called_once_with("/property_fields")
    assert all(isinstance(pf, PropertyField) for pf in result)
    # Regression: returned models previously lacked the client reference.
    assert all(pf._client is kal_client_mock for pf in result)
    assert [pf.id for pf in result] == ["pf-1", "pf-2"]
