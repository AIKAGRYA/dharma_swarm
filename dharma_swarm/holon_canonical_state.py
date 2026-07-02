"""Canonical fleet-state projection for HOLON runtime evidence.

This module converges existing component evidence into
``~/.dharma/a2a_bus/state/{agent_uid}.json``. It does not supervise processes,
publish messages, or create a new receipt store.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dharma_swarm.holon_bridge import AGENTS_ROOT
from dharma_swarm.holon_service_liveness import (
    assess_service_liveness,
    latest_service_heartbeat,
)
from dharma_swarm.holon_transport_liveness import (
    DEFAULT_A2A_HEARTBEAT_FRESH_SECONDS,
    assess_a2a_inbox_bridge_liveness,
    default_a2a_bridge_heartbeat_file,
)
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash

CANONICAL_STATE_SCHEMA_VERSION = "dharma.holon_canonical_state.v1"
DEFAULT_DHARMA_HOME = Path.home() / ".dharma"
DEFAULT_A2A_BUS = DEFAULT_DHARMA_HOME / "a2a_bus"
DEFAULT_STATE_DIR = DEFAULT_A2A_BUS / "state"
DEFAULT_SERVICE_FRESH_SECONDS = 300
L4_SERVICE_ID = "holon-l4-service"
SEMANTIC_RESPONDER_SERVICE_ID = "codex-composer-semantic-responder"
SEMANTIC_RESPONDER_LAUNCHD_LABEL = "com.dharma.codex-composer-semantic-responder"


def canonical_state_path(agent_uid: str, *, a2a_bus: Path | None = None) -> Path:
    return _a2a_bus_root(a2a_bus=a2a_bus) / "state" / f"{_safe_agent_uid(agent_uid)}.json"


def project_canonical_holon_state(
    agent_uid: str,
    *,
    agents_root: Path | None = None,
    a2a_bus: Path | None = None,
    semantic_responder_state_dir: Path | None = None,
    provider: str = "",
    model: str = "",
    service_id: str = "canonical-state-projector",
    launchd_label: str = "",
    pid: int | None = None,
    semantic_responder_service_id: str = SEMANTIC_RESPONDER_SERVICE_ID,
    semantic_responder_launchd_label: str = SEMANTIC_RESPONDER_LAUNCHD_LABEL,
    l4_service_id: str = L4_SERVICE_ID,
    now: datetime | None = None,
    bridge_fresh_after_seconds: int = DEFAULT_A2A_HEARTBEAT_FRESH_SECONDS,
    responder_fresh_after_seconds: int = DEFAULT_SERVICE_FRESH_SECONDS,
    l4_fresh_after_seconds: int = DEFAULT_SERVICE_FRESH_SECONDS,
    live_model_call_claimed: bool = False,
) -> dict[str, Any]:
    """Build and atomically write canonical state for one holon."""

    state = build_canonical_holon_state(
        agent_uid,
        agents_root=agents_root,
        a2a_bus=a2a_bus,
        semantic_responder_state_dir=semantic_responder_state_dir,
        provider=provider,
        model=model,
        service_id=service_id,
        launchd_label=launchd_label,
        pid=pid,
        semantic_responder_service_id=semantic_responder_service_id,
        semantic_responder_launchd_label=semantic_responder_launchd_label,
        l4_service_id=l4_service_id,
        now=now,
        bridge_fresh_after_seconds=bridge_fresh_after_seconds,
        responder_fresh_after_seconds=responder_fresh_after_seconds,
        l4_fresh_after_seconds=l4_fresh_after_seconds,
        live_model_call_claimed=live_model_call_claimed,
    )
    path = canonical_state_path(agent_uid, a2a_bus=_a2a_bus_for_agents(agents_root, a2a_bus))
    existing = _read_json(path)
    _assert_safe_state_target(path, agent_uid, existing)
    payload = {**existing, **state}
    payload["record_hash"] = ""
    payload["record_hash"] = stable_payload_hash(payload)
    _atomic_write_json(path, payload)
    return payload


def build_canonical_holon_state(
    agent_uid: str,
    *,
    agents_root: Path | None = None,
    a2a_bus: Path | None = None,
    semantic_responder_state_dir: Path | None = None,
    provider: str = "",
    model: str = "",
    service_id: str = "canonical-state-projector",
    launchd_label: str = "",
    pid: int | None = None,
    semantic_responder_service_id: str = SEMANTIC_RESPONDER_SERVICE_ID,
    semantic_responder_launchd_label: str = SEMANTIC_RESPONDER_LAUNCHD_LABEL,
    l4_service_id: str = L4_SERVICE_ID,
    now: datetime | None = None,
    bridge_fresh_after_seconds: int = DEFAULT_A2A_HEARTBEAT_FRESH_SECONDS,
    responder_fresh_after_seconds: int = DEFAULT_SERVICE_FRESH_SECONDS,
    l4_fresh_after_seconds: int = DEFAULT_SERVICE_FRESH_SECONDS,
    live_model_call_claimed: bool = False,
) -> dict[str, Any]:
    observed = _utc(now)
    root = Path(agents_root or AGENTS_ROOT).expanduser()
    bus = _a2a_bus_for_agents(root, a2a_bus)
    identity = _read_json(root / agent_uid / "identity.json")

    route_provider = provider or str(identity.get("provider") or identity.get("provider_type") or "")
    route_model = model or str(identity.get("model") or "")
    bridge = assess_a2a_inbox_bridge_liveness(
        agent_uid,
        heartbeat_path=bus / "bridge_heartbeats" / f"{_safe_agent_uid(agent_uid)}.json",
        now=observed,
        fresh_after_seconds=bridge_fresh_after_seconds,
    )
    responder = assess_service_liveness(
        agent_uid,
        agents_root=root,
        now=observed,
        fresh_after_seconds=responder_fresh_after_seconds,
        service_id=semantic_responder_service_id,
    )
    l4 = assess_service_liveness(
        agent_uid,
        agents_root=root,
        now=observed,
        fresh_after_seconds=l4_fresh_after_seconds,
        service_id=l4_service_id,
    )
    semantic_receipt = latest_semantic_responder_receipt(semantic_responder_state_dir)
    l4_proof = latest_l4_proof(agent_uid, agents_root=root, service_id=l4_service_id)
    l4_claim_scope = dict(l4_proof.get("claim_scope") or {})
    explicit_live_claim = bool(
        live_model_call_claimed or l4_claim_scope.get("live_model_call_claimed")
    )

    component_fresh = {
        "bridge": bool(bridge.get("fresh")),
        "semantic_responder": bool(responder.get("fresh")),
        "l4_service": bool(l4.get("fresh")),
    }
    status = _overall_status(
        bridge_reachable=bool(bridge.get("transport_reachable")),
        responder_alive=bool(responder.get("service_alive")),
        l4_alive=bool(l4.get("service_alive")),
        any_fresh=any(component_fresh.values()),
    )
    freshness = {
        "bridge": _freshness_label(bridge.get("heartbeat_seen"), bridge.get("fresh")),
        "semantic_responder": _freshness_label(
            responder.get("heartbeat_seen"), responder.get("fresh")
        ),
        "l4_service": _freshness_label(l4.get("heartbeat_seen"), l4.get("fresh")),
    }
    payload: dict[str, Any] = {
        "schema_version": CANONICAL_STATE_SCHEMA_VERSION,
        "agent": agent_uid,
        "agent_uid": agent_uid,
        "status": status,
        "last_heartbeat": _format_utc(observed),
        "service_id": service_id,
        "state_written_by": "dharma_swarm.holon_canonical_state",
        "launchd_label": launchd_label,
        "pid": pid,
        "bridge_heartbeat_path": str(bridge.get("heartbeat_path") or default_a2a_bridge_heartbeat_file(agent_uid)),
        "bridge_fresh": bool(bridge.get("fresh")),
        "bridge_transport_reachable": bool(bridge.get("transport_reachable")),
        "responder_heartbeat_path": str(responder.get("heartbeat_path") or ""),
        "responder_fresh": bool(responder.get("fresh")),
        "responder_alive": bool(responder.get("service_alive")),
        "l4_heartbeat_path": str(l4.get("heartbeat_path") or ""),
        "l4_fresh": bool(l4.get("fresh")),
        "l4_service_alive": bool(l4.get("service_alive")),
        "latest_semantic_responder_receipt": semantic_receipt,
        "latest_semantic_responder_receipt_path": str(semantic_receipt.get("path") or ""),
        "last_processed_delivery_status": _latest_delivery_status(semantic_receipt),
        "latest_l4_proof_artifact": str(l4_proof.get("artifact_path") or ""),
        "latest_l4_proof_digest": str(l4_proof.get("artifact_digest") or ""),
        "provider_model_route": {
            "provider": route_provider,
            "model": route_model,
            "truth_source": "explicit_args_or_identity_json",
        },
        "live_model_call_claimed": explicit_live_claim,
        "freshness": freshness,
        "component_freshness": dict(freshness),
        "components": {
            "bridge": bridge,
            "semantic_responder": {
                **responder,
                "service_id": semantic_responder_service_id,
                "launchd_label": semantic_responder_launchd_label,
                "latest_processed_delivery_status": _latest_delivery_status(semantic_receipt),
            },
            "l4_service": {
                **l4,
                "service_id": l4_service_id,
                "latest_proof": l4_proof,
            },
        },
        "record_hash": "",
    }
    if launchd_label or pid is not None:
        payload["launchd"] = {
            "label": launchd_label,
            "pid": pid,
            "pid_known": pid is not None,
        }
    payload["record_hash"] = stable_payload_hash(payload)
    return payload


def latest_semantic_responder_receipt(state_dir: Path | None) -> dict[str, Any]:
    if state_dir is None:
        return {}
    root = Path(state_dir).expanduser() / "receipts"
    if not root.exists():
        return {}
    candidates = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime)
    for path in reversed(candidates):
        payload = _read_json(path)
        if not payload:
            continue
        return {
            "path": str(path),
            "status": str(payload.get("status") or ""),
            "timestamp": str(payload.get("timestamp") or ""),
            "packet_id": str(payload.get("packet_id") or ""),
            "reply_subject": str(payload.get("reply_subject") or ""),
            "semantic_reply_claim": bool(payload.get("semantic_reply_claim")),
            "domain_receipt_claim": bool(payload.get("domain_receipt_claim")),
            "handler_ack_is_semantic_cognition": bool(
                payload.get("handler_ack_is_semantic_cognition")
            ),
            "live_model_call_claimed": False,
        }
    return {}


def latest_l4_proof(
    agent_uid: str,
    *,
    agents_root: Path | None = None,
    service_id: str = L4_SERVICE_ID,
) -> dict[str, Any]:
    heartbeat = latest_service_heartbeat(agent_uid, agents_root, service_id=service_id) or {}
    proof_ref = dict(heartbeat.get("proof_ref") or {})
    artifact = dict(proof_ref.get("artifact") or {})
    claim_scope = dict(heartbeat.get("claim_scope") or {})
    artifact_path = str(artifact.get("path") or "")
    artifact_payload = _read_json(Path(artifact_path)) if artifact_path else {}
    artifact_claim_scope = dict(artifact_payload.get("claim_scope") or {})
    if artifact_claim_scope:
        claim_scope = {**claim_scope, **artifact_claim_scope}
    return {
        "heartbeat_record_hash": str(heartbeat.get("record_hash") or ""),
        "heartbeat_observed_at": str(heartbeat.get("observed_at") or ""),
        "artifact_path": artifact_path,
        "artifact_digest": str(artifact.get("digest") or proof_ref.get("artifact_digest") or ""),
        "proof_digest": str(proof_ref.get("proof_digest") or ""),
        "transport_reachable": bool(claim_scope.get("transport_reachable")),
        "orchestration_proven": bool(claim_scope.get("orchestration_proven")),
        "live_model_call_claimed": bool(claim_scope.get("live_model_call_claimed")),
        "claim_scope": claim_scope,
    }


def _a2a_bus_for_agents(agents_root: Path | None, a2a_bus: Path | None) -> Path:
    if a2a_bus is not None:
        return _a2a_bus_root(a2a_bus=a2a_bus)
    if agents_root is not None:
        return Path(agents_root).expanduser().parent / "a2a_bus"
    return DEFAULT_A2A_BUS


def _a2a_bus_root(*, a2a_bus: Path | None = None) -> Path:
    return Path(a2a_bus or DEFAULT_A2A_BUS).expanduser()


def _safe_agent_uid(value: object) -> str:
    safe = "".join(
        char if char.isalnum() or char in ("_", "-") else "_"
        for char in str(value or "").strip()
    ).strip("_-")
    return safe or "unknown"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _assert_safe_state_target(path: Path, agent_uid: str, existing: dict[str, Any]) -> None:
    if path.name != f"{_safe_agent_uid(agent_uid)}.json":
        raise ValueError(f"canonical state path must target {agent_uid}: {path}")
    existing_agent = str(existing.get("agent_uid") or existing.get("agent") or "")
    if existing_agent and existing_agent != agent_uid:
        raise ValueError(
            f"canonical state path contains agent {existing_agent!r}, expected {agent_uid!r}"
        )


def _utc(value: datetime | None = None) -> datetime:
    observed = value or datetime.now(UTC)
    if observed.tzinfo is None:
        return observed.replace(tzinfo=UTC)
    return observed.astimezone(UTC)


def _format_utc(value: datetime | None = None) -> str:
    return _utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _freshness_label(seen: object, fresh: object) -> str:
    if not seen:
        return "missing"
    return "fresh" if fresh else "stale"


def _overall_status(
    *,
    bridge_reachable: bool,
    responder_alive: bool,
    l4_alive: bool,
    any_fresh: bool,
) -> str:
    if bridge_reachable and responder_alive and l4_alive:
        return "operational"
    if any_fresh:
        return "partial"
    return "stale"


def _latest_delivery_status(receipt: dict[str, Any]) -> str:
    return str(receipt.get("status") or "NO_PENDING_DELIVERIES")


__all__ = [
    "CANONICAL_STATE_SCHEMA_VERSION",
    "L4_SERVICE_ID",
    "SEMANTIC_RESPONDER_LAUNCHD_LABEL",
    "SEMANTIC_RESPONDER_SERVICE_ID",
    "build_canonical_holon_state",
    "canonical_state_path",
    "latest_l4_proof",
    "latest_semantic_responder_receipt",
    "project_canonical_holon_state",
]
