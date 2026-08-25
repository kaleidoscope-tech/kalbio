"""Shared caching for service read methods.

Every cache created through :func:`cached` is:

- cleared in bulk by :meth:`KaleidoscopeClient.clear_caches`,
- bypassed for a single call by passing ``use_cache=False``,
- bypassed for a block of calls inside :meth:`KaleidoscopeClient.cache_disabled`.

A bypassed read recomputes the value and refreshes the stored entry, so the
cache holds the fresh result afterward.
"""

from __future__ import annotations

import functools
import threading
from typing import Any, Callable, Generic, Optional, Protocol, TypeVar, overload

from cachetools import Cache, LRUCache, TTLCache
from cachetools.keys import hashkey

R = TypeVar("R")
R_co = TypeVar("R_co", covariant=True)
T = TypeVar("T")

_DEFAULT_MAXSIZE = 128


class CachedMethod(Protocol[R_co]):
    """A method wrapped by :func:`cached`: callable, skippable, and clearable."""

    def __call__(self, *args: Any, use_cache: bool = ..., **kwargs: Any) -> R_co: ...

    def cache_clear(self) -> None: ...


def _client_cache_disabled(service: Any) -> bool:
    """Whether the service's owning client is inside a ``cache_disabled`` block."""
    client = getattr(service, "_client", None)
    checker = getattr(client, "_is_cache_disabled", None)
    return bool(checker()) if callable(checker) else False


@overload
def cached(func: Callable[..., R]) -> CachedMethod[R]: ...


@overload
def cached(
    *,
    ttl: Optional[float] = ...,
    maxsize: Optional[int] = ...,
    cache_none: bool = ...,
) -> Callable[[Callable[..., R]], CachedMethod[R]]: ...


def cached(
    func: Optional[Callable[..., R]] = None,
    *,
    ttl: Optional[float] = None,
    maxsize: Optional[int] = None,
    cache_none: bool = True,
) -> Any:
    """Cache a service method's result, keyed on the instance and arguments.

    Args:
        ttl: If set, cached entries expire this many seconds after they are stored.
        maxsize: Maximum number of cached entries before least-recently-used
            eviction. Defaults to 128, matching ``functools.lru_cache``.
        cache_none: When False, a ``None`` result is not stored, so the next call
            retries instead of serving a cached miss. Useful for reads whose
            ``None`` means "transiently unavailable" rather than "no such thing".

    The wrapped method gains a keyword-only ``use_cache`` argument (default
    ``True``) and a ``cache_clear()`` attribute.

    The cache store is created once per decorated method and shared across every
    instance of the owning class, keyed by the instance. Distinct clients never
    read each other's entries, but ``clear_caches()`` on one client clears the
    stored reads for all clients of that class. This is a benign efficiency
    quirk (an extra refetch), not a correctness issue, and single-client-per-
    process is the expected usage.
    """
    if func is None:
        return functools.partial(
            cached, ttl=ttl, maxsize=maxsize, cache_none=cache_none
        )

    store: Cache
    if ttl is not None:
        store = TTLCache(maxsize=maxsize or _DEFAULT_MAXSIZE, ttl=ttl)
    else:
        store = LRUCache(maxsize=maxsize or _DEFAULT_MAXSIZE)
    lock = threading.Lock()

    @functools.wraps(func)
    def wrapper(self: Any, *args: Any, use_cache: bool = True, **kwargs: Any) -> R:
        # Key on the service instance itself (like functools.lru_cache) so caches
        # from distinct clients never collide.
        key = hashkey(self, *args, **kwargs)
        if use_cache and not _client_cache_disabled(self):
            with lock:
                try:
                    return store[key]
                except KeyError:
                    pass
        result = func(self, *args, **kwargs)
        if cache_none or result is not None:
            with lock:
                store[key] = result
        return result

    def cache_clear() -> None:
        with lock:
            store.clear()

    wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
    return wrapper


def clear_service_caches(service: Any) -> None:
    """Clear every cache attached to a service instance or its class.

    Handles methods wrapped by :func:`cached` (and ``functools.lru_cache`` /
    ``cachetools.func`` wrappers, which also expose ``cache_clear``) as well as
    bare ``cachetools.Cache`` attributes such as the record-lookup maps.
    """
    for holder in (type(service).__dict__, vars(service)):
        for value in list(holder.values()):
            cache_clear = getattr(value, "cache_clear", None)
            if callable(cache_clear):
                cache_clear()
            elif isinstance(value, Cache):
                value.clear()


class cached_model_property(Generic[T]):
    """A cached property for model objects that respects the client's cache controls.

    Like :func:`functools.cached_property`, the wrapped method runs once and the
    result is stored on the instance. It differs in two ways:

    - Access inside :meth:`KaleidoscopeClient.cache_disabled` recomputes the value
      and refreshes the stored copy.
    - The stored value is dropped by the model's ``clear_caches()``.
    """

    def __init__(self, func: Callable[[Any], T]) -> None:
        self.func = func
        # Store the value under a private key rather than the attribute's own
        # name: this stays a non-data descriptor, so leaving `attrname` out of
        # the instance dict means __get__ runs on every access and can honor
        # cache_disabled().
        self.store_key: Optional[str] = None
        self.__doc__ = func.__doc__

    def __set_name__(self, owner: type, name: str) -> None:
        self.store_key = f"__kalbio_cached_{name}"

    @overload
    def __get__(
        self, instance: None, owner: Optional[type] = ...
    ) -> "cached_model_property[T]": ...

    @overload
    def __get__(self, instance: object, owner: Optional[type] = ...) -> T: ...

    def __get__(self, instance: Any, owner: Optional[type] = None) -> Any:
        if instance is None:
            return self
        if self.store_key is None:
            raise TypeError("cached_model_property must be assigned to a class attribute")
        cache = instance.__dict__
        if self.store_key in cache and not _client_cache_disabled(instance):
            return cache[self.store_key]
        value = self.func(instance)
        cache[self.store_key] = value
        return value


def clear_model_caches(model: Any) -> None:
    """Drop every :class:`cached_model_property` value stored on a model instance."""
    for klass in type(model).__mro__:
        for attr in vars(klass).values():
            if isinstance(attr, cached_model_property) and attr.store_key is not None:
                model.__dict__.pop(attr.store_key, None)
