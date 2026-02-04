"""
Kaleidoscope Base Model Module.

Internal class.

This module defines the base model class for all Kaleidoscope objects, providing
common functionality for serialization, comparison, and client management.

The `_KaleidoscopeBaseModel` class extends Pydantic's BaseModel to provide:
- Unique identification via id attribute
- Client instance management for API interactions
- Standard serialization methods (JSON, dictionary)
- Comparison and hashing based on id
- String representation methods

Classes:
    _KaleidoscopeBaseModel: Base class for all Kaleidoscope model objects.
"""

from pydantic import BaseModel
from kalbio.client import KaleidoscopeClient
import json


class _KaleidoscopeBaseModel(BaseModel):
    """
    Base model class for Kaleidoscope objects.
    This class provides common functionality for all Kaleidoscope model objects,
    including serialization, comparison, and client management.
    Attributes:
        id (str): Unique identifier for the model instance.
        _client (KaleidoscopeClient): Internal reference to the Kaleidoscope client instance.
    Methods:
        __eq__(other): Compare two model instances based on their type and id.
        __hash__(): Return hash value based on the id attribute.
        __str__(): Return string representation of the model instance.
        __repr__(): Return string representation of the model instance.
        to_json(): Serialize the model instance to a JSON string.
        to_dict(): Convert the model instance to a dictionary containing the id.
        _set_client(client): Set the KaleidoscopeClient instance for this object.
    """

    id: str
    _client: KaleidoscopeClient

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def __str__(self):
        return f"{type(self).__name__}:'{self.id[:8]}...'"

    def __repr__(self):
        return f"{self.__class__}({self.model_dump()})"

    def to_json(self) -> str:
        """
        Serializes the model to a JSON-formatted string.
        Returns:
            str: A JSON string representation of the model, with indentation for readability.
        Notes:
            - This method is a thin convenience wrapper. To customize serialization options,
              call json.dumps(...) directly on a `dict` of the model.
            - One way a `dict` may be optained throught the `to_dict()` method
        """

        return json.dumps(self.model_dump(), indent=4, sort_keys=False, default=str)

    def to_dict(self) -> dict:
        """
        Return a dictionary representation of the model by delegating to self.model_dump().
        Returns:
            dict: A mapping of field names to their serialized values. The exact structure and
            serialization behavior (e.g., handling of nested models, inclusion of defaults,
            or custom encoders) follow the semantics of the underlying model_dump implementation.
        Notes:
            - This method is a thin convenience wrapper. To customize serialization options,
              call model_dump(...) directly with the desired parameters.
        """

        return self.model_dump()

    def _set_client(self, client: KaleidoscopeClient) -> None:
        """
        Set the `KaleidoscopeClient` instance for this object.
        Also recursively sets client on all _KaleidoscopeBaseModel attributes
        """
        self._client = client

        # Iterate through field names and get actual values from the instance
        for field_name in self.__class__.model_fields.keys():
            value = getattr(self, field_name, None)
            if value is None:
                continue

            if isinstance(value, _KaleidoscopeBaseModel):
                value._set_client(client)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, _KaleidoscopeBaseModel):
                        item._set_client(client)
            elif isinstance(value, dict):
                for item in value.values():
                    if isinstance(item, _KaleidoscopeBaseModel):
                        item._set_client(client)
                    elif isinstance(item, list):
                        for nested_item in item:
                            if isinstance(nested_item, _KaleidoscopeBaseModel):
                                nested_item._set_client(client)
