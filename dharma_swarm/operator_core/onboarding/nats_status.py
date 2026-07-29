"""Bounded, non-admission NATS substrate observation for session status.

This collector performs one local TCP-listener probe and filesystem existence
checks only. It never connects to an environment-selected endpoint, speaks the
NATS protocol, attempts JetStream operations, or promotes either observation
to live-contact evidence.
"""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir


SCHEMA = "dharma_swarm.onboard_nats_substrate.v1"
SPEC_PATH = "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"
LOCAL_TCP_HOST = "127.0.0.1"
LOCAL_TCP_PORT = 4222
TCP_PROBE_TIMEOUT_SECONDS = 0.2
PROBE_SCOPE = "local_tcp_listener_only"
_STATE_DISPLAY_ROOT = "~/" + ".dharma"
_MIRROR_RELATIVE_PATHS = (
    "a2a_bus/receipts/",
    "a2a_bus/" + "verifier" + ".jsonl",
    "a2a_bus/conjunction/",
    "a2a_bus/tasks/queue.jsonl",
    "a2a_bus/inboxes/",
)
FILESYSTEM_MIRROR_PATHS = tuple(
    f"{_STATE_DISPLAY_ROOT}/{relative_path}"
    for relative_path in _MIRROR_RELATIVE_PATHS
)
MIRRORS_ARE_LIVE_TRANSPORT_PROOF = False


def _tcp_listening() -> bool:
    """Observe only whether the fixed local TCP endpoint accepts a connection."""

    try:
        with socket.create_connection(
            (LOCAL_TCP_HOST, LOCAL_TCP_PORT),
            timeout=TCP_PROBE_TIMEOUT_SECONDS,
        ):
            return True
    except OSError:
        return False


def _mirror_rows(state_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for display_path, relative_path in zip(
        FILESYSTEM_MIRROR_PATHS,
        _MIRROR_RELATIVE_PATHS,
    ):
        target = state_root / relative_path.rstrip("/")
        rows.append({"path": display_path, "exists": target.exists()})
    return rows


def collect_nats_substrate_status(*, home: Path | None = None) -> dict[str, Any]:
    """Return a typed projection that carries no admission or liveness authority."""

    state_root = home / ".dharma" if home is not None else dharma_state_dir()
    mirrors = _mirror_rows(state_root)
    return {
        "schema": SCHEMA,
        "authority": "local_observation_only",
        "spec_path": SPEC_PATH,
        "tcp_host": LOCAL_TCP_HOST,
        "tcp_port": LOCAL_TCP_PORT,
        "tcp_probe_timeout_seconds": TCP_PROBE_TIMEOUT_SECONDS,
        "tcp_listening": _tcp_listening(),
        "probe_scope": PROBE_SCOPE,
        "filesystem_mirrors": mirrors,
        "filesystem_mirrors_exist": any(row["exists"] for row in mirrors),
        "mirrors_are_live_transport_proof": MIRRORS_ARE_LIVE_TRANSPORT_PROOF,
        "jetstream_ack_verified": False,
        "live_contact_claim": False,
    }


__all__ = [
    "FILESYSTEM_MIRROR_PATHS",
    "LOCAL_TCP_HOST",
    "LOCAL_TCP_PORT",
    "MIRRORS_ARE_LIVE_TRANSPORT_PROOF",
    "PROBE_SCOPE",
    "SCHEMA",
    "SPEC_PATH",
    "TCP_PROBE_TIMEOUT_SECONDS",
    "collect_nats_substrate_status",
]
