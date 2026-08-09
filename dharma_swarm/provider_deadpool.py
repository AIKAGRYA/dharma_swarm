"""In-session deadpool for connection-dead LLM providers.

Classifies connection-level transport failures and caches the dead lanes for
a TTL so chain walks stop re-probing corpses on every request. Shared by the
ModelRouter walk (providers.py) and the direct cheap-first walk
(runtime_provider.py); pure stdlib so neither import direction cycles.
"""

from __future__ import annotations

import errno
import logging
import os
import time
from collections.abc import Hashable
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

# How long a connection-dead provider stays skipped by the chain walk.
# In-session only (per-instance cache) — a provider that comes back up is
# retried after expiry. Override with DGC_ROUTER_DEADPOOL_TTL_SECONDS.
PROVIDER_DEADPOOL_TTL_SECONDS = 300.0

_CONNECTION_DEAD_EXCEPTION_NAMES = frozenset(
    {
        # httpx / requests / aiohttp transport-level connect failures
        "ConnectError",
        "ConnectTimeout",
        "ClientConnectorError",
        "ClientConnectionError",
        "NewConnectionError",
    }
)

_CONNECTION_DEAD_ERRNOS = frozenset(
    {
        errno.ECONNREFUSED,
        errno.ECONNRESET,
        errno.ECONNABORTED,
        errno.EHOSTUNREACH,
        errno.EHOSTDOWN,
        errno.ENETUNREACH,
        errno.ENETDOWN,
    }
)

_CONNECTION_DEAD_MESSAGE_TOKENS = (
    "connection refused",
    "connection reset",
    "cannot connect to host",
    "all connection attempts failed",
    "failed to establish a new connection",
    "name or service not known",
    "nodename nor servname provided",
    "temporary failure in name resolution",
    "network is unreachable",
    "no route to host",
)


def deadpool_ttl_seconds() -> float:
    """Effective TTL: DGC_ROUTER_DEADPOOL_TTL_SECONDS override or the default."""
    raw = os.environ.get("DGC_ROUTER_DEADPOOL_TTL_SECONDS")
    if raw in (None, ""):
        return PROVIDER_DEADPOOL_TTL_SECONDS
    return float(raw)


def is_connection_dead_error(exc: BaseException) -> bool:
    """Classify a connection-level transport failure (refused/unreachable/DNS).

    Deliberately narrow: auth failures, 4xx responses, and rate limits must
    return False — those can be fixed mid-session and never justify skipping
    a provider. Walks the exception chain because HTTP clients wrap the raw
    OSError in their own transport exception types.
    """
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ConnectionError):
            return True
        if type(current).__name__ in _CONNECTION_DEAD_EXCEPTION_NAMES:
            return True
        if isinstance(current, OSError) and current.errno in _CONNECTION_DEAD_ERRNOS:
            return True
        message = str(current).lower()
        if any(token in message for token in _CONNECTION_DEAD_MESSAGE_TOKENS):
            return True
        current = current.__cause__ or current.__context__
    return False


K = TypeVar("K", bound=Hashable)


class ProviderDeadpool(Generic[K]):
    """Record/active/clear cache of connection-dead providers, fail-open.

    `filter` returns the original chain untouched when every candidate is
    dead, so a walk always re-probes (a success clears the entry, a failure
    refreshes the TTL with a receipted error) instead of refusing outright.
    """

    def __init__(self, ttl_seconds: float | None = None) -> None:
        effective = deadpool_ttl_seconds() if ttl_seconds is None else ttl_seconds
        self._ttl_seconds = max(0.0, effective)
        self._entries: dict[K, float] = {}

    @property
    def ttl_seconds(self) -> float:
        return self._ttl_seconds

    def __contains__(self, key: object) -> bool:
        return key in self._entries

    def record(self, key: K, *, error: str = "") -> None:
        """Mark a provider connection-dead for the TTL so walks skip the corpse."""
        if self._ttl_seconds <= 0.0:
            return
        self._entries[key] = time.monotonic() + self._ttl_seconds
        logger.warning(
            "Provider %s deadpooled for %.0fs after connection failure: %s",
            getattr(key, "value", key),
            self._ttl_seconds,
            error,
        )

    def active(self, key: K) -> bool:
        """True while the entry's TTL is unexpired; expired entries are pruned."""
        expiry = self._entries.get(key)
        if expiry is None:
            return False
        if time.monotonic() >= expiry:
            self._entries.pop(key, None)
            return False
        return True

    def clear(self, key: K) -> None:
        """Drop the entry after a successful call — the lane is alive again."""
        self._entries.pop(key, None)

    def filter(self, chain: list[K]) -> tuple[list[K], bool]:
        """Filter connection-dead providers; fail open if the whole chain is dead."""
        if not self._entries:
            return (chain, False)
        active = [item for item in chain if not self.active(item)]
        if not active or len(active) == len(chain):
            return (chain, False)
        return (active, True)
