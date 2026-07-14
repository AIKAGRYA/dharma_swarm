"""Persistent fleet-node directory, health monitor, and remote dispatcher."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any, Callable

import httpx

from dharma_swarm.daemon_config import dharma_state_dir

logger = logging.getLogger(__name__)

_LOG_SANITIZE_RE = re.compile(r"[\r\n\x00-\x1f\x7f]")
_ENV_SANITIZE_RE = re.compile(r"[^A-Za-z0-9]+")
_CREDENTIAL_KEY_RE = re.compile(
    r"(api[_-]?key|token|secret|password|credential|private[_-]?key|authorization)",
    re.IGNORECASE,
)
_REDACTED_SECRET = "<redacted>"


def _sanitize(value: object) -> str:
    """Strip control characters from a value before logging."""
    return _LOG_SANITIZE_RE.sub("_", str(value))


def _default_api_key_env(node_id: str) -> str:
    """Return the canonical env-var reference for a node's gateway key."""
    sanitized = _ENV_SANITIZE_RE.sub("_", str(node_id)).strip("_").upper()
    return f"DHARMA_NODE_KEY_{sanitized or 'NODE'}"


def _is_credential_field(key: object) -> bool:
    return bool(_CREDENTIAL_KEY_RE.search(str(key)))


def _redact_credential_fields(value: Any) -> Any:
    """Recursively redact values stored under credential-looking field names."""
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if _is_credential_field(key):
                redacted[key] = _REDACTED_SECRET
            else:
                redacted[key] = _redact_credential_fields(item)
        return redacted
    if isinstance(value, list):
        return [_redact_credential_fields(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_credential_fields(item) for item in value)
    return value


_STATE_DIR = dharma_state_dir("DHARMA_HOME")
_NODES_PATH = _STATE_DIR / "a2a" / "nodes.json"

# Nodes with no heartbeat for this many seconds are marked degraded.
_HEARTBEAT_STALE_SECONDS = 300  # 5 minutes
# Nodes with no heartbeat for this long are marked offline.
_HEARTBEAT_OFFLINE_SECONDS = 900  # 15 minutes
_NODE_STATUSES = frozenset({"online", "degraded", "offline", "unknown"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _heartbeat_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


@dataclass
class RemoteNode:
    """Credential-safe runtime and persisted state for one fleet node."""

    node_id: str
    endpoint: str = ""
    ssh_alias: str = ""
    status: str = "unknown"
    last_heartbeat: str = ""
    capabilities: list[str] = field(default_factory=list)
    api_key: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    api_key_env: str = ""

    def __post_init__(self) -> None:
        if not self.api_key_env:
            self.api_key_env = _default_api_key_env(self.node_id)

    def is_reachable(self) -> bool:
        """Whether the node is considered reachable for task dispatch."""
        return self.status in ("online", "degraded")

    def resolved_api_key(self) -> str:
        """Return the active API key from runtime memory or its env reference."""
        if self.api_key:
            return self.api_key
        if self.api_key_env:
            return os.getenv(self.api_key_env, "")
        return ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("api_key", None)
        d["api_key_env"] = self.api_key_env or _default_api_key_env(self.node_id)
        d["metadata"] = _redact_credential_fields(d.get("metadata", {}))
        return d


# fmt: off
class NodeRegistry:
    """Thread-safe central directory persisted as one atomic JSON snapshot."""

    def __init__(self, nodes_path: Path | None = None, *, clock: Callable[[], datetime] | None = None) -> None:
        self._path = nodes_path or _NODES_PATH
        self._nodes: dict[str, RemoteNode] = {}
        self._lock = RLock()
        self._clock = clock or _utc_now
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("nodes", [])
            if not isinstance(data, list):
                raise ValueError(
                    "node registry JSON must be a list or object with a nodes list"
                )
            for item in data:
                if not isinstance(item, dict):
                    continue
                known = {f.name for f in RemoteNode.__dataclass_fields__.values()}
                filtered = {k: v for k, v in item.items() if k in known}
                node_id = str(filtered.get("node_id", ""))
                if not node_id:
                    continue
                api_key_env = str(
                    filtered.get("api_key_env") or _default_api_key_env(node_id)
                )
                filtered["api_key_env"] = api_key_env

                legacy_api_key = str(filtered.get("api_key") or "")
                # Prefer the env reference. Only keep legacy plaintext in memory
                # when no referenced env var is available, and never write it back.
                filtered["api_key"] = "" if os.getenv(api_key_env) else legacy_api_key
                node = RemoteNode(**filtered)
                self._nodes[node.node_id] = node
        except Exception as exc:
            logger.warning("Failed to load node registry from %s: %s", self._path, exc)

    def _persist(self) -> bool:
        temporary: Path | None = None
        try:
            with self._lock:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                data = json.dumps([node.to_dict() for node in self._nodes.values()], indent=2, default=str) + "\n"
                with NamedTemporaryFile(
                    "w", encoding="utf-8", dir=self._path.parent,
                    prefix=f".{self._path.name}.", delete=False,
                ) as handle:
                    handle.write(data)
                    temporary = Path(handle.name)
                temporary.replace(self._path)
            return True
        except Exception as exc:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            logger.error("Failed to persist node registry: %s", exc)
            return False

    def _replace_node(self, node_id: str, replacement: RemoteNode | None) -> RemoteNode | None:
        previous = self._nodes.get(node_id)
        if replacement is None:
            self._nodes.pop(node_id, None)
        else:
            self._nodes[node_id] = replacement
        if self._persist():
            return previous
        if previous is None:
            self._nodes.pop(node_id, None)
        else:
            self._nodes[node_id] = previous
        raise RuntimeError(f"Failed to persist node registry update: {node_id}")

    def register(self, node: RemoteNode) -> None:
        """Register or update a node in the fleet."""
        with self._lock:
            self._replace_node(node.node_id, deepcopy(node))
        logger.info(
            "Registered fleet node: %s at %s",
            _sanitize(node.node_id),
            _sanitize(node.endpoint),
        )

    def unregister(self, node_id: str) -> bool:
        """Remove a node. Returns True if it existed."""
        with self._lock:
            if node_id not in self._nodes:
                return False
            self._replace_node(node_id, None)
        logger.info("Unregistered fleet node: %s", _sanitize(node_id))
        return True

    def get(self, node_id: str) -> RemoteNode | None:
        with self._lock:
            self._refresh_stale_locked()
            node = self._nodes.get(node_id)
            return deepcopy(node) if node is not None else None

    def list_all(self) -> list[RemoteNode]:
        with self._lock:
            self._refresh_stale_locked()
            return sorted((deepcopy(node) for node in self._nodes.values()), key=lambda node: node.node_id)

    def list_online(self) -> list[RemoteNode]:
        return [n for n in self.list_all() if n.is_reachable()]

    def count(self) -> int:
        with self._lock:
            return len(self._nodes)

    def update_status(
        self, node_id: str, *, status: str, observed_at: str = "", witness: str = "",
    ) -> RemoteNode:
        """Atomically persist an explicit, provenance-labelled status mutation."""
        node_status = str(status or "").strip().lower()
        observed, provenance = str(observed_at or "").strip(), str(witness or "").strip()
        if node_status not in _NODE_STATUSES:
            raise ValueError(f"invalid node status: {status!r}")
        if node_status in {"online", "degraded"} and not observed:
            raise ValueError("reachable status requires observed_at")
        if node_status in {"online", "degraded"} and not provenance:
            raise ValueError("reachable status requires a witness")
        parsed = _heartbeat_time(observed) if observed else None
        if observed and parsed is None:
            raise ValueError("observed_at must be a timezone-aware ISO timestamp")
        with self._lock:
            current = self._nodes.get(node_id)
            if current is None:
                raise ValueError(f"Unknown node: {node_id}")
            metadata = deepcopy(current.metadata)
            if provenance:
                metadata["status_witness"] = provenance
            if parsed is not None:
                metadata["status_observed_at"] = parsed.astimezone(timezone.utc).isoformat()
            heartbeat = metadata.get("status_observed_at", current.last_heartbeat) if node_status in {"online", "degraded"} else current.last_heartbeat
            updated = replace(current, status=node_status, last_heartbeat=heartbeat, metadata=metadata)
            self._replace_node(node_id, updated)
            return deepcopy(updated)

    def record_heartbeat(
        self, node_id: str, *, last_heartbeat: str, status: str,
        metadata: Mapping[str, Any] | None = None, canonical_agent_uid: str = "",
    ) -> RemoteNode:
        """Persist a heartbeat; unknown nodes require a projector-resolved UID."""
        node_id = str(node_id or "").strip()
        uid = str(canonical_agent_uid or "").strip()
        heartbeat_at = str(last_heartbeat or "").strip()
        node_status = str(status or "").strip().lower()
        if not node_id or not heartbeat_at:
            raise ValueError("heartbeat node_id and last_heartbeat are required")
        if node_status not in _NODE_STATUSES:
            raise ValueError(f"invalid node heartbeat status: {status!r}")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise TypeError("heartbeat metadata must be a mapping")

        incoming_metadata = deepcopy(dict(metadata or {}))
        incoming_uid = str(incoming_metadata.get("agent_uid") or "").strip()
        incoming_time = _heartbeat_time(heartbeat_at)
        if incoming_time is None:
            raise ValueError("last_heartbeat must be a timezone-aware ISO timestamp")
        with self._lock:
            current = self._nodes.get(node_id)
            if current is None and not uid:
                raise ValueError(f"Unknown node identity: {node_id}")
            existing_uid = str((current.metadata.get("agent_uid") if current is not None else "") or "").strip()
            identities = {value for value in (uid, incoming_uid, existing_uid) if value}
            if len(identities) > 1:
                raise ValueError("heartbeat identity does not match registered node")
            incoming_message_id = str(incoming_metadata.get("presence_message_id") or "")
            current_message_id = str(current.metadata.get("presence_message_id") or "") if current is not None else ""
            current_time = _heartbeat_time(current.last_heartbeat) if current is not None else None
            if current is not None and (
                (bool(incoming_message_id) and current_message_id == incoming_message_id)
                or (current_time is not None and current_time >= incoming_time)
            ):
                return deepcopy(current)
            base = current or RemoteNode(node_id=node_id)
            merged_metadata = {**base.metadata, **incoming_metadata}
            if identities:
                merged_metadata["agent_uid"] = next(iter(identities))
            updated = replace(base, status=node_status, last_heartbeat=heartbeat_at, metadata=merged_metadata)
            self._replace_node(node_id, updated)
            return deepcopy(updated)

    def rollback_heartbeat(
        self, node_id: str, *, expected_presence_message_id: str, previous: RemoteNode | None,
    ) -> bool:
        """Restore previous state only while the failed heartbeat is current."""
        with self._lock:
            current = self._nodes.get(node_id)
            current_message_id = str(current.metadata.get("presence_message_id") or "") if current is not None else ""
            if current_message_id != expected_presence_message_id:
                return False
            self._replace_node(node_id, deepcopy(previous))
            return True

    def discover(self, capability: str) -> list[RemoteNode]:
        """Find online nodes that advertise a matching capability."""
        cap_lower = capability.lower()
        return [
            n
            for n in self.list_online()
            if any(cap_lower in c.lower() for c in n.capabilities)
        ]

    async def health_check(self, node_id: str, timeout: float = 10.0) -> RemoteNode:
        """Ping one node and persist its resulting health state."""
        with self._lock:
            snapshot = deepcopy(self._nodes.get(node_id))
        if snapshot is None:
            raise ValueError(f"Unknown node: {node_id}")
        if not snapshot.endpoint:
            with self._lock:
                current = deepcopy(self._nodes[node_id])
                current.status = "offline"
                current.metadata["last_error"] = "No endpoint configured"
                self._replace_node(node_id, current)
                return deepcopy(current)

        url = f"{snapshot.endpoint.rstrip('/')}/a2a/health"
        headers = {}
        api_key = snapshot.resolved_api_key()
        if api_key:
            headers["X-A2A-Key"] = api_key
        data: dict[str, Any] | None = None
        failure: Exception | None = None
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            failure = exc
        with self._lock:
            current = deepcopy(self._nodes.get(node_id))
            if current is None:
                raise ValueError(f"Unknown node: {node_id}")
            if failure is None and isinstance(data, dict):
                current.status = str(data.get("status", "online"))
                current.last_heartbeat = self._clock().astimezone(timezone.utc).isoformat()
                current.capabilities = list(data.get("capabilities", current.capabilities))
                current.metadata["task_counts"] = data.get("task_counts", {})
                current.metadata.pop("last_error", None)
                logger.info("Health check OK: %s", _sanitize(node_id))
            else:
                current.metadata["last_error"] = str(failure)
                if not current.last_heartbeat and current.is_reachable():
                    current.status = "unknown"
                    current.metadata["status_witness"] = "health_check_failure"
                    current.metadata["status_observed_at"] = self._clock().astimezone(timezone.utc).isoformat()
                else:
                    _mark_stale(current, now=self._clock())
                logger.warning("Health check failed for %s: %s", _sanitize(node_id), failure)
            self._replace_node(node_id, current)
            return deepcopy(current)

    async def health_check_all(self, timeout: float = 10.0) -> list[RemoteNode]:
        """Ping every registered node and return updated states."""
        with self._lock:
            node_ids = list(self._nodes)
        results = []
        for node_id in node_ids:
            result = await self.health_check(node_id, timeout=timeout)
            results.append(result)
        return results

    def degrade_stale_nodes(self) -> list[str]:
        """Persist staleness transitions and return changed node IDs."""
        with self._lock:
            changed = self._refresh_stale_locked()
        if changed:
            logger.info("Degraded stale nodes: %s", changed)
        return changed

    def _refresh_stale_locked(self) -> list[str]:
        previous: dict[str, RemoteNode] = {}
        for node_id, current in tuple(self._nodes.items()):
            updated = deepcopy(current)
            _mark_stale(updated, now=self._clock())
            if updated.status != current.status:
                previous[node_id] = current
                self._nodes[node_id] = updated
        if previous and not self._persist():
            self._nodes.update(previous)
            raise RuntimeError("Failed to persist stale node transitions")
        return sorted(previous)
# fmt: on


def _mark_stale(node: RemoteNode, now: datetime | None = None) -> None:
    """Update node status based on heartbeat age."""
    if not node.last_heartbeat:
        return

    now = now or _utc_now()
    try:
        last = datetime.fromisoformat(node.last_heartbeat)
        age = (now - last).total_seconds()
    except (ValueError, TypeError):
        node.status = "unknown"
        return

    if age > _HEARTBEAT_OFFLINE_SECONDS:
        node.status = "offline"
    elif age > _HEARTBEAT_STALE_SECONDS:
        node.status = "degraded"


def _current_trace_id() -> str:
    """Read trace_id from CorrelationContext if available."""
    try:
        from dharma_swarm.correlation_context import get_correlation

        corr = get_correlation()
        if corr.trace_id:
            return corr.trace_id
    except Exception:
        logger.debug("Correlation context unavailable", exc_info=True)
    return ""


async def dispatch_remote_task(
    node: RemoteNode,
    capability: str,
    message: str,
    from_agent: str = "dharma-hub",
    metadata: dict[str, Any] | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Submit a task to a remote node and return its gateway response."""
    url = f"{node.endpoint.rstrip('/')}/a2a/tasks"
    headers = {"Content-Type": "application/json"}
    api_key = node.resolved_api_key()
    if api_key:
        headers["X-A2A-Key"] = api_key

    body: dict[str, Any] = {
        "from_agent": from_agent,
        "capability": capability,
        "messages": [{"role": "user", "content": message}],
        "metadata": metadata or {},
    }

    trace_id = _current_trace_id()
    if trace_id:
        body["trace_id"] = trace_id

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def poll_remote_task(
    node: RemoteNode,
    task_id: str,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Poll and return one remote task's current gateway state."""
    url = f"{node.endpoint.rstrip('/')}/a2a/tasks/{task_id}"
    headers = {}
    api_key = node.resolved_api_key()
    if api_key:
        headers["X-A2A-Key"] = api_key

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
