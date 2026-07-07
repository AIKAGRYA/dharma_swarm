"""Node Registry — central directory of fleet nodes.

Tracks all remote nodes (VPSes, Mac Minis, etc.) with:
  - Endpoint URL, SSH alias, status, capabilities
  - Heartbeat monitoring (last_seen timestamps)
  - Capability-based discovery across the fleet

Persistence: JSON file at ~/.dharma/a2a/nodes.json
No new SQLite store — respects dharma.no-new-substrate rule.

Four-question discipline:
  1. Which loop?  Fleet health monitoring (sense node status → act on failures)
  2. Which membrane?  Network boundary between hub and remote nodes
  3. What artifact?  Node health records with capabilities + heartbeat
  4. Self-correcting?  Stale heartbeats trigger status degradation
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RemoteNode:
    """A remote node in the Dharma fleet.

    Attributes:
        node_id: Unique identifier (e.g. "agni", "rushabdev").
        endpoint: HTTP URL for the node gateway (e.g. "http://157.245.193.15:8420").
        ssh_alias: SSH config alias for fallback rsync (e.g. "agni").
        status: Current status: online, degraded, offline, unknown.
        last_heartbeat: ISO timestamp of last successful health check.
        capabilities: List of capability names fetched from the remote agent card.
        api_key: Runtime-only API key for authenticating to this node's gateway.
        api_key_env: Environment variable that should hold the gateway API key.
        metadata: Arbitrary extra data.
    """

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


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class NodeRegistry:
    """Central directory of fleet nodes.

    Stores nodes in memory and persists to JSON on disk.
    Provides capability-based discovery across the fleet.

    Usage::

        reg = NodeRegistry()
        reg.register(RemoteNode(
            node_id="agni",
            endpoint="http://157.245.193.15:8420",
            ssh_alias="agni",
            api_key="secret-key-here",
        ))
        nodes = reg.discover("code_review")
        await reg.health_check_all()
    """

    def __init__(self, nodes_path: Path | None = None) -> None:
        self._path = nodes_path or _NODES_PATH
        self._nodes: dict[str, RemoteNode] = {}
        self._load()

    # -- persistence ---------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("nodes", [])
            if not isinstance(data, list):
                raise ValueError("node registry JSON must be a list or object with a nodes list")
            for item in data:
                if not isinstance(item, dict):
                    continue
                known = {f.name for f in RemoteNode.__dataclass_fields__.values()}
                filtered = {k: v for k, v in item.items() if k in known}
                node_id = str(filtered.get("node_id", ""))
                if not node_id:
                    continue
                api_key_env = str(filtered.get("api_key_env") or _default_api_key_env(node_id))
                filtered["api_key_env"] = api_key_env

                legacy_api_key = str(filtered.get("api_key") or "")
                # Prefer the env reference. Only keep legacy plaintext in memory
                # when no referenced env var is available, and never write it back.
                filtered["api_key"] = "" if os.getenv(api_key_env) else legacy_api_key
                node = RemoteNode(**filtered)
                self._nodes[node.node_id] = node
        except Exception as exc:
            logger.warning("Failed to load node registry from %s: %s", self._path, exc)

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = [n.to_dict() for n in self._nodes.values()]
            self._path.write_text(
                json.dumps(data, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Failed to persist node registry: %s", exc)

    # -- registration --------------------------------------------------------

    def register(self, node: RemoteNode) -> None:
        """Register or update a node in the fleet."""
        self._nodes[node.node_id] = node
        self._persist()
        logger.info("Registered fleet node: %s at %s", _sanitize(node.node_id), _sanitize(node.endpoint))

    def unregister(self, node_id: str) -> bool:
        """Remove a node. Returns True if it existed."""
        if node_id not in self._nodes:
            return False
        del self._nodes[node_id]
        self._persist()
        logger.info("Unregistered fleet node: %s", _sanitize(node_id))
        return True

    # -- retrieval -----------------------------------------------------------

    def get(self, node_id: str) -> RemoteNode | None:
        return self._nodes.get(node_id)

    def list_all(self) -> list[RemoteNode]:
        return sorted(self._nodes.values(), key=lambda n: n.node_id)

    def list_online(self) -> list[RemoteNode]:
        return [n for n in self.list_all() if n.is_reachable()]

    def count(self) -> int:
        return len(self._nodes)

    # -- discovery -----------------------------------------------------------

    def discover(self, capability: str) -> list[RemoteNode]:
        """Find online nodes that advertise a matching capability."""
        cap_lower = capability.lower()
        return [
            n for n in self.list_online()
            if any(cap_lower in c.lower() for c in n.capabilities)
        ]

    # -- health monitoring ---------------------------------------------------

    async def health_check(self, node_id: str, timeout: float = 10.0) -> RemoteNode:
        """Ping a single node's health endpoint and update its status.

        Args:
            node_id: The node to check.
            timeout: HTTP timeout in seconds.

        Returns:
            The updated RemoteNode.
        """
        node = self._nodes.get(node_id)
        if node is None:
            raise ValueError(f"Unknown node: {node_id}")

        if not node.endpoint:
            node.status = "offline"
            node.metadata["last_error"] = "No endpoint configured"
            self._persist()
            return node

        url = f"{node.endpoint.rstrip('/')}/a2a/health"
        headers = {}
        api_key = node.resolved_api_key()
        if api_key:
            headers["X-A2A-Key"] = api_key

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            node.status = data.get("status", "online")
            node.last_heartbeat = _utc_now_iso()
            node.capabilities = data.get("capabilities", node.capabilities)
            node.metadata["task_counts"] = data.get("task_counts", {})
            node.metadata.pop("last_error", None)
            logger.info("Health check OK: %s (%s)", _sanitize(node_id), _sanitize(node.status))

        except Exception as exc:
            node.metadata["last_error"] = str(exc)
            _mark_stale(node)
            logger.warning("Health check failed for %s: %s", _sanitize(node_id), exc)

        self._persist()
        return node

    async def health_check_all(self, timeout: float = 10.0) -> list[RemoteNode]:
        """Ping all registered nodes and update statuses.

        Returns list of all nodes with updated statuses.
        """
        results = []
        for node_id in list(self._nodes):
            result = await self.health_check(node_id, timeout=timeout)
            results.append(result)
        return results

    def degrade_stale_nodes(self) -> list[str]:
        """Mark nodes with stale heartbeats as degraded or offline.

        Called periodically by Guardian or cron_runner.
        Returns list of node_ids that changed status.
        """
        changed = []
        now = _utc_now()
        for node in self._nodes.values():
            old_status = node.status
            _mark_stale(node, now=now)
            if node.status != old_status:
                changed.append(node.node_id)

        if changed:
            self._persist()
            logger.info("Degraded stale nodes: %s", changed)
        return changed


def _mark_stale(node: RemoteNode, now: datetime | None = None) -> None:
    """Update node status based on heartbeat age."""
    if not node.last_heartbeat:
        if node.status not in ("unknown", "offline"):
            node.status = "unknown"
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
        pass
    return ""


# ---------------------------------------------------------------------------
# Remote task dispatch (used by A2AClient for cross-node delegation)
# ---------------------------------------------------------------------------


async def dispatch_remote_task(
    node: RemoteNode,
    capability: str,
    message: str,
    from_agent: str = "dharma-hub",
    metadata: dict[str, Any] | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Submit a task to a remote node's gateway.

    Args:
        node: The target RemoteNode.
        capability: Capability being requested.
        message: Task instruction text.
        from_agent: Requester identity.
        metadata: Optional task metadata.
        timeout: HTTP timeout in seconds.

    Returns:
        Task response dict from the remote gateway.

    Raises:
        httpx.HTTPStatusError: On non-2xx response.
        httpx.ConnectError: If the node is unreachable.
    """
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
    """Poll a remote task's status.

    Args:
        node: The remote node running the task.
        task_id: The task ID to poll.
        timeout: HTTP timeout.

    Returns:
        Task status dict from the remote gateway.
    """
    url = f"{node.endpoint.rstrip('/')}/a2a/tasks/{task_id}"
    headers = {}
    api_key = node.resolved_api_key()
    if api_key:
        headers["X-A2A-Key"] = api_key

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
