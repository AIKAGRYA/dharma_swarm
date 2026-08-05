"""Namespaced key/value store for runtime injection (LG30 parity).

langgraph ``BaseStore`` / ``InMemoryStore`` parity for the surface the graph
runtime actually injects: ``get`` / ``put`` / ``delete`` / ``search`` over
``(namespace_tuple, key)`` addresses. Values are Mappings; every read
returns a :class:`KVItem` snapshot, never a live alias, so a node cannot
mutate stored state by holding onto a returned value (langgraph
``InMemoryStore`` returns immutable-by-convention items; DharmaGraph makes
the isolation explicit by deep-copying).

The store is deliberately NOT part of graph state: it is injected per
invoke, never checkpointed, and never digested. Cross-superstep durability
of store contents is the caller's concern — the same object passed to
``invoke(store=...)`` is the same object every node sees.

claim_mode: candidate / test_only. Not wired into production dispatch.
"""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Protocol, runtime_checkable

__all__ = [
    "InMemoryKVStore",
    "KVItem",
    "KVStore",
    "StoreNamespaceError",
]


class StoreNamespaceError(ValueError):
    """A namespace or key argument was malformed (fail closed)."""


def _normalized_namespace(namespace: Iterable[str] | str) -> tuple[str, ...]:
    """Coerce a namespace to a non-empty tuple of non-empty strings.

    A bare string is a single-segment namespace (convenience only); every
    other iterable must yield strings. Empty namespaces and empty segments
    fail closed — silently accepting them would collapse distinct addresses.
    """
    if isinstance(namespace, str):
        parts: tuple[str, ...] = (namespace,)
    else:
        try:
            parts = tuple(namespace)
        except TypeError as exc:
            raise StoreNamespaceError(
                f"namespace must be a string or an iterable of strings, got "
                f"{type(namespace).__name__!r} (fail closed)"
            ) from exc
    if not parts:
        raise StoreNamespaceError("namespace must have at least one segment")
    for part in parts:
        if not isinstance(part, str) or not part:
            raise StoreNamespaceError(
                f"namespace segments must be non-empty strings, got {part!r}"
            )
    return parts


def _validated_key(key: str) -> str:
    if not isinstance(key, str) or not key:
        raise StoreNamespaceError(f"store key must be a non-empty string, got {key!r}")
    return key


@dataclass(frozen=True)
class KVItem:
    """One stored record: its full address plus a snapshot of its value."""

    namespace: tuple[str, ...]
    key: str
    value: Mapping[str, Any]


@runtime_checkable
class KVStore(Protocol):
    """Structural store contract the graph runtime injects into nodes."""

    def get(
        self, namespace: Iterable[str] | str, key: str
    ) -> KVItem | None: ...

    def put(
        self,
        namespace: Iterable[str] | str,
        key: str,
        value: Mapping[str, Any],
    ) -> None: ...

    def delete(self, namespace: Iterable[str] | str, key: str) -> None: ...

    def search(
        self,
        namespace_prefix: Iterable[str] | str,
        *,
        filter: Mapping[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[KVItem]: ...


class InMemoryKVStore:
    """Process-local :class:`KVStore` (langgraph ``InMemoryStore`` parity).

    Thread-safe because one superstep runs every ready task concurrently and
    two tasks may legally address the same namespace. Ordering of
    :meth:`search` is deterministic — sorted by ``(namespace, key)`` — so a
    seeded two-arm differential is reproducible.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: dict[tuple[str, ...], dict[str, Mapping[str, Any]]] = {}

    def get(self, namespace: Iterable[str] | str, key: str) -> KVItem | None:
        ns = _normalized_namespace(namespace)
        name = _validated_key(key)
        with self._lock:
            stored = self._data.get(ns, {}).get(name)
            if stored is None:
                return None
            return KVItem(namespace=ns, key=name, value=copy.deepcopy(stored))

    def put(
        self,
        namespace: Iterable[str] | str,
        key: str,
        value: Mapping[str, Any],
    ) -> None:
        ns = _normalized_namespace(namespace)
        name = _validated_key(key)
        if not isinstance(value, Mapping):
            raise StoreNamespaceError(
                f"store values must be Mappings, got {type(value).__name__!r} "
                "(fail closed)"
            )
        with self._lock:
            self._data.setdefault(ns, {})[name] = copy.deepcopy(dict(value))

    def delete(self, namespace: Iterable[str] | str, key: str) -> None:
        """Remove one record; deleting a missing address is a no-op (parity)."""
        ns = _normalized_namespace(namespace)
        name = _validated_key(key)
        with self._lock:
            bucket = self._data.get(ns)
            if bucket is not None:
                bucket.pop(name, None)
                if not bucket:
                    self._data.pop(ns, None)

    def search(
        self,
        namespace_prefix: Iterable[str] | str,
        *,
        filter: Mapping[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[KVItem]:
        """Records whose namespace starts with ``namespace_prefix``.

        ``filter`` is an all-of equality match against the stored value;
        ``limit`` truncates the deterministic ``(namespace, key)`` order.
        """
        prefix = _normalized_namespace(namespace_prefix)
        if limit is not None and limit < 0:
            raise StoreNamespaceError(f"search limit must be >= 0, got {limit!r}")
        with self._lock:
            matches: list[KVItem] = []
            for ns in sorted(self._data):
                if ns[: len(prefix)] != prefix:
                    continue
                for name in sorted(self._data[ns]):
                    stored = self._data[ns][name]
                    if filter is not None and any(
                        stored.get(field) != expected
                        for field, expected in filter.items()
                    ):
                        continue
                    matches.append(
                        KVItem(
                            namespace=ns,
                            key=name,
                            value=copy.deepcopy(stored),
                        )
                    )
        return matches if limit is None else matches[:limit]
