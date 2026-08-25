"""Shared configuration for all API response models.

The client has no API versioning, so the server's response shape can drift out
from under a released client at any time. Two default Pydantic behaviors turn
that drift into breakage:

- ``extra="ignore"`` (the default) silently *drops* any field the model does
  not declare, so newly-added server data — including error detail — is lost.
- strict required fields raise ``ValidationError`` when the server stops sending
  a field, failing a call that would otherwise have worked.

`_ApiModel` neutralizes the first direction for the whole client by keeping
unknown fields (``extra="allow"``): they are preserved as attributes and appear
in ``model_dump()``. Individual models handle the second direction by keeping
non-identity fields optional.
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from kalbio._cache import cached_model_property

if TYPE_CHECKING:
    from kalbio.client import KaleidoscopeClient


class _BaseService:
    """Base for every resource service.

    Holds the owning :class:`KaleidoscopeClient` so cache controls
    (``cache_disabled``/``clear_caches``) and the HTTP helpers can find it.
    Subclasses inherit ``__init__`` and add resource-specific methods.
    """

    def __init__(self, client: "KaleidoscopeClient") -> None:
        self._client = client


class _ApiModel(BaseModel):
    """Base for every model parsed from an API response.

    Unknown server fields are retained rather than dropped, so forward-compatible
    additions (and unmodeled error detail) survive round-tripping through the
    client.
    """

    # extra="allow": never discard server fields the client doesn't model yet.
    # cached_model_property is a custom descriptor; Pydantic must be told it is
    # not a model field.
    model_config = ConfigDict(
        extra="allow",
        ignored_types=(cached_model_property,),
    )
