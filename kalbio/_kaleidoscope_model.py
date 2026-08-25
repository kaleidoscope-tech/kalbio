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

from typing import Any, List, Type, TypeVar

from kalbio._base import _ApiModel
from kalbio.client import KaleidoscopeClient
from kalbio._cache import clear_model_caches
import json

_ModelT = TypeVar("_ModelT", bound="_KaleidoscopeBaseModel")


class _KaleidoscopeBaseModel(_ApiModel):
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
        # Exact-type comparison, not isinstance: two subclasses sharing an id
        # (e.g. a KeyField and a DataField) must not compare equal, and equality
        # must stay symmetric across a base/subclass pair.
        return type(self) is type(other) and self.id == other.id

    def __hash__(self):
        return hash(self.id)

    @classmethod
    def _from_api(
        cls: Type[_ModelT], data: Any, client: KaleidoscopeClient
    ) -> _ModelT:
        """Validate an API payload into this model and attach the client.

        Every service that constructs a model from a response should route
        through this so validation and client hydration can never drift or be
        forgotten.
        """
        model = cls.model_validate(data)
        model._set_client(client)
        return model

    @classmethod
    def _list_from_api(
        cls: Type[_ModelT], data: Any, client: KaleidoscopeClient
    ) -> List[_ModelT]:
        """Validate a list of API payloads into models, hydrating each one."""
        return [cls._from_api(item, client) for item in data]

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
            - One way a `dict` may be obtained through the `to_dict()` method
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

    def clear_caches(self) -> None:
        """Drop this object's cached properties so they refetch on next access.

        Model objects cache related lookups (e.g. an activity's programs,
        assigned users, or child activities). Call this when that related data
        may have changed on the server and the cached copy is stale.

        This clears only this instance. Service-level caches are cleared
        separately via `client.clear_caches()`.

        Example:
            ```python
            activity.clear_caches()
            fresh_programs = activity.programs  # refetched
            ```
        """
        clear_model_caches(self)

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
