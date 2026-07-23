#!/usr/bin/env python3
"""Supervise Codex Composer semantic A2A replies.

This is the always-on semantic layer after the inbox bridge. The bridge proves
delivery only. This worker claims delivered A2A inbox records, runs the existing
semantic inbox drain, and optionally publishes the target-owned domain reply to
the original reply subject.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:  # These projection modules are not yet present on canonical main.
    from dharma_swarm.holon_canonical_state import (  # noqa: E402
        project_canonical_holon_state,
    )
    from dharma_swarm.holon_service_liveness import record_service_heartbeat  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - exercised through the availability flag
    project_canonical_holon_state = None
    record_service_heartbeat = None
from scripts.runtime.a2a_domain_reply_worker import (  # noqa: E402
    DEFAULT_OUTBOX_ROOT,
    DEFAULT_RECEIPT_DIR as DEFAULT_DOMAIN_REPLY_RECEIPT_DIR,
    load_domain_reply_target,
    publish_domain_reply_with_nats,
)
from scripts.runtime.codex_composer_semantic_inbox_drain import (  # noqa: E402
    DEFAULT_ARTIFACT_RECEIPT_DIR,
    DEFAULT_DRAIN_RECEIPT_DIR,
    DEFAULT_SEMANTIC_RECEIPT_DIR,
    drain_semantic_inbox,
)
from scripts.runtime.pr_merge_control import _nats_config, stamp, utc_now  # noqa: E402

DEFAULT_AGENT_UID = "codex_composer"
DEFAULT_DHARMA_HOME = Path.home() / ".dharma"
DEFAULT_INBOX_DIR = DEFAULT_DHARMA_HOME / "a2a_bus" / "inboxes" / DEFAULT_AGENT_UID
DEFAULT_SEND_RECEIPT_ROOT = REPO_ROOT / "reports" / "a2a" / "send_receipts"
DEFAULT_STATE_DIR = (
    DEFAULT_DHARMA_HOME
    / "external_agents"
    / DEFAULT_AGENT_UID
    / "nest"
    / "semantic_responder"
)
DEFAULT_CANONICAL_STATE_PATH = (
    DEFAULT_DHARMA_HOME / "a2a_bus" / "state" / f"{DEFAULT_AGENT_UID}.json"
)
PROCESSED_FILENAME = "processed_deliveries.jsonl"
SCHEMA_VERSION = "dharma.a2a.codex_composer_semantic_responder.v1"
HEARTBEAT_SCHEMA_VERSION = "dharma.a2a.codex_composer_semantic_responder_heartbeat.v1"
CANONICAL_PROJECTION_SCHEMA_VERSION = (
    "dharma.a2a.codex_composer_semantic_responder_canonical_projection.v1"
)
RESPONDER_SERVICE_ID = "codex-composer-semantic-responder"
RESPONDER_LAUNCHD_LABEL = "com.dharma.codex-composer-semantic-responder"
CANONICAL_PROJECTION_AVAILABLE = (
    project_canonical_holon_state is not None and record_service_heartbeat is not None
)
NO_PENDING_DELIVERIES_STATUS = "NO_PENDING_DELIVERIES"
DELIVERIES_LEASE_HELD_STATUS = "PENDING_DELIVERIES_LEASE_HELD"
# A semantic drain succeeded (model-authored artifact exists) but the domain
# reply publish did not complete. The delivery is intentionally NOT marked
# processed so a later tick can retry publish, but the model is never re-run,
# so an earlier semantic success cannot be overwritten by a later provider
# failure. This closes the fugu-verify idempotency flag named in the Phase A
# work items of A2A_MASTER_SPEC_v1.md.
PENDING_PUBLISH_STATUS = "SEMANTIC_SUCCESS_PENDING_PUBLISH"
PENDING_PUBLISH_DIRNAME = "pending_publish"
PUBLISH_RETRIES_EXHAUSTED_STATUS = "PUBLISH_RETRIES_EXHAUSTED_DLQ"
DEAD_LETTER_DIRNAME = "dead_letter"
DEFAULT_MAX_PUBLISH_ATTEMPTS = 5
A2A_INBOX_BRIDGE_SCHEMA_VERSION = "dharma.a2a.inbox_bridge_heartbeat.v1"
A2A_BRIDGE_FRESH_AFTER_SECONDS = 3600
A2A_BRIDGE_REACHABLE_STATUSES = {
    "IDLE",
    "NO_MESSAGES",
    "DELIVERED_AND_ACKED",
    "INVALID_ENVELOPE_ACKED",
}
PROCESSED_STATUSES = {
    "BASELINED_EXISTING",
    "DOMAIN_REPLY_PUBLISHED",
    "SEMANTIC_DRAINED_NO_PUBLISH",
    "ARTIFACT_INVALID",
    PUBLISH_RETRIES_EXHAUSTED_STATUS,
}


@dataclass(frozen=True)
class Delivery:
    path: Path
    payload: dict[str, Any]
    envelope: dict[str, Any]
    packet_id: str
    reply_subject: str
    delivery_id: str


def _safe_token(value: object, *, fallback: str = "unknown") -> str:
    chars = [char if char.isalnum() or char in ("_", "-") else "_" for char in str(value or "")]
    return ("".join(chars).strip("_-") or fallback)[:96]


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path}")
    return data


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    path.chmod(0o600)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    path.chmod(0o600)


def _safe_agent_state_filename(agent_uid: str) -> str:
    return f"{_safe_token(agent_uid, fallback='unknown')}.json"


def canonical_state_path_for_agent(
    agent_uid: str,
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
) -> Path:
    return Path(dharma_home).expanduser().resolve() / "a2a_bus" / "state" / _safe_agent_state_filename(agent_uid)


def _parse_utc(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _age_seconds(value: object, *, now: datetime) -> float | None:
    observed = _parse_utc(value)
    if observed is None:
        return None
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return max(0.0, round((current.astimezone(UTC) - observed).total_seconds(), 3))


def _bridge_heartbeat_path_for_canonical_state(canonical_state_path: Path, agent_uid: str) -> Path:
    state_dir = canonical_state_path.expanduser().resolve().parent
    a2a_bus = state_dir.parent
    return a2a_bus / "bridge_heartbeats" / _safe_agent_state_filename(agent_uid)


def _read_json_or_empty(path: Path) -> dict[str, Any]:
    try:
        return _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _bridge_liveness(
    *,
    agent_uid: str,
    canonical_state_path: Path,
    observed_at: str,
) -> dict[str, Any]:
    path = _bridge_heartbeat_path_for_canonical_state(canonical_state_path, agent_uid)
    payload = _read_json_or_empty(path)
    now = _parse_utc(observed_at) or datetime.now(UTC)
    timestamp = str(payload.get("timestamp") or payload.get("ts") or "")
    age = _age_seconds(timestamp, now=now)
    fresh = age is not None and age <= A2A_BRIDGE_FRESH_AFTER_SECONDS
    status = str(payload.get("status") or "unknown")
    schema_ok = payload.get("schema_version") == A2A_INBOX_BRIDGE_SCHEMA_VERSION
    heartbeat_seen = bool(payload)
    reachable = bool(
        heartbeat_seen
        and schema_ok
        and fresh
        and status in A2A_BRIDGE_REACHABLE_STATUSES
    )
    return {
        "component": "a2a_inbox_bridge",
        "heartbeat_path": str(path),
        "heartbeat_seen": heartbeat_seen,
        "fresh": fresh,
        "fresh_after_seconds": A2A_BRIDGE_FRESH_AFTER_SECONDS,
        "age_seconds": age,
        "status": status,
        "schema_ok": schema_ok,
        "transport_reachable": reachable,
        "timestamp": timestamp,
        "subject": str(payload.get("subject") or ""),
        "stream": str(payload.get("stream") or ""),
        "consumer": str(payload.get("consumer") or ""),
        "last_receipt_path": str(payload.get("last_receipt_path") or ""),
    }


def _latest_processed_delivery(state_dir: Path | str) -> dict[str, Any]:
    rows = _read_jsonl(Path(state_dir).expanduser().resolve() / PROCESSED_FILENAME)
    return dict(rows[-1]) if rows else {}


def _responder_runtime_status(loop_status: str) -> str:
    if loop_status == NO_PENDING_DELIVERIES_STATUS:
        return "idle"
    if loop_status == DELIVERIES_LEASE_HELD_STATUS:
        return "waiting_on_delivery_lease"
    if loop_status == "BASELINE_RECORDED":
        return "baselined_existing_backlog"
    if should_mark_processed(loop_status):
        return "processed_delivery"
    if loop_status == PENDING_PUBLISH_STATUS:
        return "semantic_success_pending_publish"
    if loop_status == PUBLISH_RETRIES_EXHAUSTED_STATUS:
        return "dead_lettered"
    if loop_status == "SEMANTIC_DRAINED_SEND_RECEIPT_MISSING":
        return "degraded"
    return "error"


def _canonical_status_for_loop(loop_status: str) -> str:
    runtime_status = _responder_runtime_status(loop_status)
    if runtime_status == "idle":
        return "partial_operating_semantic_responder_idle_no_pending_deliveries"
    if runtime_status == "processed_delivery":
        return "partial_operating_semantic_responder_processed_delivery"
    if runtime_status == "waiting_on_delivery_lease":
        return "partial_operating_semantic_responder_waiting_on_delivery_lease"
    if runtime_status == "baselined_existing_backlog":
        return "partial_operating_semantic_responder_baselined_existing_backlog"
    if runtime_status == "semantic_success_pending_publish":
        return "partial_operating_semantic_responder_semantic_success_pending_publish"
    if runtime_status == "dead_lettered":
        return "partial_operating_semantic_responder_dead_lettered"
    if runtime_status == "degraded":
        return "partial_operating_semantic_responder_degraded"
    return "partial_operating_semantic_responder_error"


def _latest_receipt_refs(receipt: dict[str, Any] | None) -> dict[str, Any]:
    latest = dict(receipt or {})
    drain = latest.get("semantic_drain_receipt")
    publish = latest.get("domain_reply_publish_receipt")
    drain = drain if isinstance(drain, dict) else {}
    publish = publish if isinstance(publish, dict) else {}
    return {
        "responder_receipt_path": str(latest.get("receipt_path") or ""),
        "responder_receipt_status": str(latest.get("status") or ""),
        "packet_id": str(latest.get("packet_id") or ""),
        "delivery_id": str(latest.get("delivery_id") or ""),
        "delivery_record_path": str(latest.get("delivery_record_path") or ""),
        "semantic_drain_status": str(drain.get("status") or ""),
        "semantic_drain_receipt_path": str(drain.get("receipt_path") or drain.get("drain_receipt_path") or ""),
        "domain_reply_artifact_path": str(drain.get("domain_reply_artifact_path") or ""),
        "domain_reply_publish_status": str(publish.get("status") or ""),
        "domain_reply_publish_receipt_path": str(publish.get("receipt_path") or ""),
        "semantic_reply_claim": bool(latest.get("semantic_reply_claim")),
        "domain_receipt_claim": bool(latest.get("domain_receipt_claim")),
    }


def _assert_safe_canonical_target(path: Path, agent_uid: str, existing: dict[str, Any]) -> None:
    expected_name = _safe_agent_state_filename(agent_uid)
    if path.name != expected_name:
        raise ValueError(
            f"canonical state path must target {expected_name}, got {path.name}"
        )
    existing_agent = str(existing.get("agent_uid") or existing.get("agent") or "")
    if existing_agent and existing_agent != agent_uid:
        raise ValueError(
            f"canonical state path contains agent {existing_agent!r}, expected {agent_uid!r}"
        )


def project_canonical_responder_state(
    *,
    canonical_state_path: Path,
    heartbeat: dict[str, Any],
    agent_uid: str,
    provider: str,
    model: str,
    state_dir: Path,
    latest_receipt: dict[str, Any] | None = None,
) -> Path:
    """Project responder liveness into canonical fleet truth."""
    if not CANONICAL_PROJECTION_AVAILABLE:
        raise RuntimeError(
            "canonical holon projection modules are unavailable on this checkout"
        )
    assert record_service_heartbeat is not None
    assert project_canonical_holon_state is not None
    path = canonical_state_path.expanduser().resolve()
    existing = _read_json_or_empty(path)
    _assert_safe_canonical_target(path, agent_uid, existing)
    loop_status = str(heartbeat.get("loop_status") or "unknown")
    runtime_status = _responder_runtime_status(loop_status)
    latest_processed = _latest_processed_delivery(state_dir)
    latest_refs = _latest_receipt_refs(latest_receipt)
    agents_root = path.parent.parent.parent / "agents"
    record_service_heartbeat(
        agent_uid,
        agents_root=agents_root,
        service_id=RESPONDER_SERVICE_ID,
        status="idle" if runtime_status in {
            "idle",
            "processed_delivery",
            "waiting_on_delivery_lease",
            "baselined_existing_backlog",
        } else "error",
        runtime_ref={
            "loop_status": loop_status,
            "runtime_status": runtime_status,
            "pending_delivery_count": int(heartbeat.get("pending_delivery_count") or 0),
            "provider": provider,
            "model": model,
        },
        proof_ref={
            "kind": "codex_composer_semantic_responder_loop",
            "local_heartbeat_path": str(heartbeat.get("heartbeat_path") or ""),
            "latest_receipt": latest_refs,
        },
        claim_scope={
            "semantic_responder_fresh": True,
            "last_processed_delivery_status": str(latest_processed.get("status") or loop_status),
            "no_pending_deliveries": loop_status == NO_PENDING_DELIVERIES_STATUS,
            "handler_ack_is_semantic_cognition": False,
            "live_model_call_claimed": False,
        },
    )

    project_canonical_holon_state(
        agent_uid,
        agents_root=agents_root,
        a2a_bus=path.parent.parent,
        semantic_responder_state_dir=state_dir,
        provider=provider,
        model=model,
        service_id=RESPONDER_SERVICE_ID,
        launchd_label=RESPONDER_LAUNCHD_LABEL,
        pid=int(heartbeat.get("pid") or os.getpid()),
        live_model_call_claimed=False,
    )
    return path


CanonicalProjector = Callable[..., Path]


def write_responder_heartbeat(
    state_dir: Path | str,
    *,
    agent_uid: str,
    provider: str,
    model: str,
    loop_status: str,
    pending_delivery_count: int,
    latest_receipt: dict[str, Any] | None = None,
    canonical_state_path: Path | None = None,
    project_canonical_state: bool = True,
    canonical_projector: CanonicalProjector = project_canonical_responder_state,
) -> dict[str, Any]:
    root = Path(state_dir).expanduser().resolve()
    observed_at = utc_now()
    latest_refs = _latest_receipt_refs(latest_receipt)
    latest_processed = _latest_processed_delivery(root)
    heartbeat = {
        "schema_version": HEARTBEAT_SCHEMA_VERSION,
        "timestamp": observed_at,
        "observed_at": observed_at,
        "agent_uid": agent_uid,
        "service_id": RESPONDER_SERVICE_ID,
        "launchd_label": RESPONDER_LAUNCHD_LABEL,
        "pid": os.getpid(),
        "status": _responder_runtime_status(loop_status),
        "loop_status": loop_status,
        "pending_delivery_count": max(0, int(pending_delivery_count)),
        "fresh": True,
        "fresh_after_seconds": 120,
        "provider": provider,
        "model": model,
        "live_model_call_claimed": False,
        "handler_ack_is_semantic_cognition": False,
        "latest_receipt": latest_refs,
        "last_processed_delivery_status": str(latest_processed.get("status") or ""),
        "latest_processed_delivery": latest_processed,
    }
    heartbeat_path = root / "heartbeat.json"
    heartbeat["heartbeat_path"] = str(heartbeat_path)
    _write_json(heartbeat_path, heartbeat)
    if project_canonical_state and (
        CANONICAL_PROJECTION_AVAILABLE
        or canonical_projector is not project_canonical_responder_state
    ):
        canonical_path = canonical_state_path or canonical_state_path_for_agent(agent_uid)
        project_path = canonical_projector(
            canonical_state_path=canonical_path,
            heartbeat=heartbeat,
            agent_uid=agent_uid,
            provider=provider,
            model=model,
            state_dir=root,
            latest_receipt=latest_receipt,
        )
        heartbeat["canonical_state_path"] = str(project_path)
        _write_json(heartbeat_path, heartbeat)
    elif project_canonical_state:
        heartbeat["canonical_projection_status"] = "UNAVAILABLE_ON_CHECKOUT"
        heartbeat["canonical_state_path"] = ""
        _write_json(heartbeat_path, heartbeat)
    return heartbeat


def _delivery_id(path: Path, payload: dict[str, Any], envelope: dict[str, Any]) -> str:
    stable = {
        "path": str(path.expanduser().resolve()),
        "packet_id": str(envelope.get("packet_id") or ""),
        "reply_subject": str(envelope.get("reply_subject") or ""),
        "envelope_sha256": str(payload.get("envelope_sha256") or ""),
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def delivery_from_path(path: Path, *, agent_uid: str) -> Delivery | None:
    try:
        payload = _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if str(payload.get("schema_version") or "") != "dharma.a2a.inbox_delivery.v1":
        return None
    envelope = payload.get("envelope")
    if not isinstance(envelope, dict):
        return None
    target_uid = str(payload.get("agent_uid") or envelope.get("target_uid") or "")
    if target_uid != agent_uid:
        return None
    packet_id = str(envelope.get("packet_id") or "")
    reply_subject = str(envelope.get("reply_subject") or "")
    if not packet_id or not reply_subject:
        return None
    return Delivery(
        path=path.expanduser().resolve(),
        payload=payload,
        envelope=envelope,
        packet_id=packet_id,
        reply_subject=reply_subject,
        delivery_id=_delivery_id(path, payload, envelope),
    )


def processed_delivery_ids(state_dir: Path | str) -> set[str]:
    path = Path(state_dir).expanduser().resolve() / PROCESSED_FILENAME
    return {
        str(row.get("delivery_id"))
        for row in _read_jsonl(path)
        if row.get("delivery_id") and should_mark_processed(str(row.get("status") or ""))
    }


def pending_deliveries(
    inbox_dir: Path | str,
    *,
    agent_uid: str,
    processed_ids: set[str],
    limit: int,
    packet_id: str = "",
) -> list[Delivery]:
    root = Path(inbox_dir).expanduser().resolve()
    if not root.exists():
        return []
    deliveries: list[Delivery] = []
    for path in sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime):
        delivery = delivery_from_path(path, agent_uid=agent_uid)
        if delivery is None or delivery.delivery_id in processed_ids:
            continue
        if packet_id and delivery.packet_id != packet_id:
            continue
        deliveries.append(delivery)
        if limit > 0 and len(deliveries) >= limit:
            break
    return deliveries


def find_send_receipt(
    send_receipt_root: Path | str,
    *,
    agent_uid: str,
    packet_id: str,
    reply_subject: str,
) -> Path | None:
    root = Path(send_receipt_root).expanduser().resolve()
    if not root.exists():
        return None
    candidates = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            receipt = _read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if str(receipt.get("packet_id") or "") != packet_id:
            continue
        if str(receipt.get("reply_subject") or "") != reply_subject:
            continue
        target = str(receipt.get("target_uid") or receipt.get("to") or "")
        if target and target != agent_uid:
            continue
        return path
    return None


def acquire_lease(state_dir: Path | str, delivery_id: str, *, ttl_s: float) -> Path | None:
    lease_dir = Path(state_dir).expanduser().resolve() / "leases"
    lease_dir.mkdir(parents=True, exist_ok=True)
    lease_path = lease_dir / f"{_safe_token(delivery_id)}.lock"
    if lease_path.exists():
        age_s = time.time() - lease_path.stat().st_mtime
        if age_s < ttl_s:
            return None
        try:
            lease_path.unlink()
        except FileNotFoundError:
            pass
    payload = {"schema_version": SCHEMA_VERSION, "delivery_id": delivery_id, "leased_at": utc_now()}
    try:
        fd = os.open(lease_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return None
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    lease_path.chmod(0o600)
    return lease_path


def release_lease(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def mark_processed(state_dir: Path | str, delivery: Delivery, *, status: str, receipt_path: str) -> None:
    if delivery.delivery_id in processed_delivery_ids(state_dir):
        return
    _append_jsonl(
        Path(state_dir).expanduser().resolve() / PROCESSED_FILENAME,
        {
            "schema_version": SCHEMA_VERSION,
            "timestamp": utc_now(),
            "delivery_id": delivery.delivery_id,
            "packet_id": delivery.packet_id,
            "reply_subject": delivery.reply_subject,
            "delivery_record_path": str(delivery.path),
            "status": status,
            "receipt_path": receipt_path,
        },
    )


def should_mark_processed(status: str) -> bool:
    return status in PROCESSED_STATUSES


def baseline_existing_deliveries(
    inbox_dir: Path | str,
    *,
    state_dir: Path | str,
    agent_uid: str,
    provider: str = "unknown",
    model: str = "unknown",
    canonical_state_path: Path | None = None,
    project_canonical_state: bool = False,
    canonical_projector: CanonicalProjector = project_canonical_responder_state,
) -> dict[str, Any]:
    seen = processed_delivery_ids(state_dir)
    deliveries = pending_deliveries(
        inbox_dir,
        agent_uid=agent_uid,
        processed_ids=seen,
        limit=0,
    )
    for delivery in deliveries:
        mark_processed(state_dir, delivery, status="BASELINED_EXISTING", receipt_path="")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": utc_now(),
        "status": "BASELINE_RECORDED",
        "agent_uid": agent_uid,
        "delivery_count": len(deliveries),
        "inbox_dir": str(Path(inbox_dir).expanduser().resolve()),
        "state_dir": str(Path(state_dir).expanduser().resolve()),
        "packet_ids": [delivery.packet_id for delivery in deliveries],
        "operator_contact_note": (
            "Existing inbox delivery records were marked processed so the always-on "
            "semantic responder starts from new traffic instead of replaying historical backlog."
        ),
    }
    write_responder_receipt(Path(state_dir).expanduser().resolve(), receipt)
    if project_canonical_state:
        write_responder_heartbeat(
            state_dir,
            agent_uid=agent_uid,
            provider=provider,
            model=model,
            loop_status="BASELINE_RECORDED",
            pending_delivery_count=0,
            latest_receipt=receipt,
            canonical_state_path=canonical_state_path,
            project_canonical_state=True,
            canonical_projector=canonical_projector,
        )
    return receipt


def write_responder_receipt(state_dir: Path | str, receipt: dict[str, Any]) -> Path:
    root = Path(state_dir).expanduser().resolve() / "receipts"
    packet = _safe_token(receipt.get("packet_id"))
    status = _safe_token(receipt.get("status"))
    path = root / f"{stamp()}-{status}-{packet}.json"
    receipt["receipt_path"] = str(path)
    _write_json(path, receipt)
    return path


def publish_domain_reply_sync(
    *,
    send_receipt_path: Path,
    reply_artifact_path: Path,
    agent_uid: str,
    outbox_root: Path,
    receipt_dir: Path,
    stream: str,
    timeout_s: float,
    flush_timeout_s: float,
) -> dict[str, Any]:
    target = load_domain_reply_target(
        send_receipt_path=send_receipt_path,
        reply_artifact_path=reply_artifact_path,
        agent_uid=agent_uid,
        outbox_root=outbox_root,
        enforce_owner_path=True,
    )
    config = _nats_config(dict(os.environ), require_devin_secrets=False)
    return asyncio.run(
        publish_domain_reply_with_nats(
            target,
            config=config,
            receipt_dir=receipt_dir,
            stream=stream,
            timeout_s=max(timeout_s, 0.1),
            flush_timeout_s=max(flush_timeout_s, 0.1),
        )
    )


DrainFunc = Callable[..., dict[str, Any]]
PublishFunc = Callable[..., dict[str, Any]]


def _pending_publish_path(state_dir: Path | str, delivery_id: str) -> Path:
    root = Path(state_dir).expanduser().resolve() / PENDING_PUBLISH_DIRNAME
    return root / f"{_safe_token(delivery_id)}.json"


def _dead_letter_path(state_dir: Path | str, delivery_id: str) -> Path:
    root = Path(state_dir).expanduser().resolve() / DEAD_LETTER_DIRNAME
    return root / f"{_safe_token(delivery_id)}.json"


def _write_json_once(path: Path, payload: dict[str, Any]) -> bool:
    """Atomically create one immutable JSON object.

    The deterministic target plus an exclusive hard-link promotion makes a
    terminal delivery effect idempotent across process crashes and restarts.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    _write_json(temporary, payload)
    try:
        os.link(temporary, path)
    except FileExistsError:
        return False
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    path.chmod(0o600)
    return True


def load_dead_letter(state_dir: Path | str, delivery_id: str) -> dict[str, Any] | None:
    path = _dead_letter_path(state_dir, delivery_id)
    try:
        payload = _read_json(path)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        return None
    if str(payload.get("delivery_id") or "") != delivery_id:
        raise ValueError(f"dead letter delivery id mismatch: {path}")
    return payload


def write_dead_letter(
    state_dir: Path | str,
    delivery: Delivery,
    *,
    pending_job: dict[str, Any],
    attempt_count: int,
    reason: str,
    error: str = "",
    operator_quarantined: bool = False,
) -> tuple[Path, dict[str, Any], bool]:
    """Create the exactly-once terminal record for an unpublishable reply."""

    path = _dead_letter_path(state_dir, delivery.delivery_id)
    now = utc_now()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": now,
        "status": PUBLISH_RETRIES_EXHAUSTED_STATUS,
        "delivery_id": delivery.delivery_id,
        "packet_id": delivery.packet_id,
        "reply_subject": delivery.reply_subject,
        "delivery_record_path": str(delivery.path),
        "publish_attempt_count": max(0, int(attempt_count)),
        "first_pending_at": str(
            pending_job.get("first_pending_at")
            or pending_job.get("timestamp")
            or now
        ),
        "last_attempt_at": now,
        "terminal_reason": reason,
        "last_error": error,
        "operator_quarantined": operator_quarantined,
        "semantic_reply_claim": bool(pending_job.get("semantic_reply_claim")),
        "domain_reply_artifact_path": str(
            pending_job.get("domain_reply_artifact_path") or ""
        ),
        "semantic_receipt_path": str(pending_job.get("semantic_receipt_path") or ""),
        "semantic_receipt_id": str(pending_job.get("semantic_receipt_id") or ""),
        "preserved_pending_publish": pending_job,
        "authority_boundary": (
            "Terminal delivery state prevents another semantic model run. "
            "It does not claim domain publication or remote effect."
        ),
    }
    created = _write_json_once(path, payload)
    if not created:
        existing = load_dead_letter(state_dir, delivery.delivery_id)
        if existing is None:
            raise RuntimeError(f"dead letter exists but is unreadable: {path}")
        payload = existing
    return path, payload, created


def load_pending_publish(state_dir: Path | str, delivery_id: str) -> dict[str, Any] | None:
    """Return a saved semantic-success job whose publish has not completed.

    The job pins the already-authored, model-backed domain reply artifact so a
    retry publishes the same artifact instead of re-running the model critic.
    A missing or unreadable job returns ``None`` (fall back to a fresh drain).
    """

    path = _pending_publish_path(state_dir, delivery_id)
    if not path.exists():
        return None
    try:
        job = _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    artifact_path = str(job.get("domain_reply_artifact_path") or "")
    # Only honor the job if its pinned artifact still exists on disk; otherwise a
    # fresh drain is safer than publishing a dangling reference.
    if not artifact_path or not Path(artifact_path).expanduser().exists():
        return None
    if not bool(job.get("semantic_reply_claim")):
        # A non-semantic (typed-failure) drain has nothing to protect from being
        # re-run, so do not pin it.
        return None
    return job


def save_pending_publish(
    state_dir: Path | str,
    delivery: "Delivery",
    *,
    drain_receipt: dict[str, Any],
    attempt_count: int,
    last_error: str = "",
) -> Path:
    """Persist a semantic-success drain so a later tick can retry publish only."""

    path = _pending_publish_path(state_dir, delivery.delivery_id)
    previous = _read_json_or_empty(path)
    now = utc_now()
    _write_json(
        path,
        {
            "schema_version": SCHEMA_VERSION,
            "timestamp": now,
            "delivery_id": delivery.delivery_id,
            "packet_id": delivery.packet_id,
            "reply_subject": delivery.reply_subject,
            "delivery_record_path": str(delivery.path),
            "domain_reply_artifact_path": str(drain_receipt.get("domain_reply_artifact_path") or ""),
            "semantic_receipt_path": str(drain_receipt.get("semantic_receipt_path") or ""),
            "semantic_receipt_id": str(drain_receipt.get("semantic_receipt_id") or ""),
            "semantic_reply_claim": bool(drain_receipt.get("semantic_reply_claim")),
            "drain_receipt": drain_receipt,
            "publish_attempt_count": max(1, int(attempt_count)),
            "first_pending_at": str(
                previous.get("first_pending_at")
                or previous.get("timestamp")
                or now
            ),
            "last_attempt_at": now,
            "last_error": last_error,
        },
    )
    return path


def clear_pending_publish(state_dir: Path | str, delivery_id: str) -> None:
    path = _pending_publish_path(state_dir, delivery_id)
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def process_delivery(
    delivery: Delivery,
    *,
    state_dir: Path,
    send_receipt_root: Path,
    outbox_root: Path,
    semantic_receipt_dir: Path,
    artifact_receipt_dir: Path,
    drain_receipt_dir: Path,
    domain_reply_receipt_dir: Path,
    agent_uid: str,
    provider: str,
    model: str,
    no_publish: bool,
    stream: str,
    timeout_s: float,
    flush_timeout_s: float,
    max_publish_attempts: int = DEFAULT_MAX_PUBLISH_ATTEMPTS,
    drain_func: DrainFunc = drain_semantic_inbox,
    publish_func: PublishFunc = publish_domain_reply_sync,
) -> dict[str, Any]:
    max_publish_attempts = max(1, int(max_publish_attempts))
    existing_dead_letter = load_dead_letter(state_dir, delivery.delivery_id)
    if existing_dead_letter is not None:
        receipt = {
            "schema_version": SCHEMA_VERSION,
            "timestamp": utc_now(),
            "status": PUBLISH_RETRIES_EXHAUSTED_STATUS,
            "agent_uid": agent_uid,
            "delivery_id": delivery.delivery_id,
            "packet_id": delivery.packet_id,
            "reply_subject": delivery.reply_subject,
            "delivery_record_path": str(delivery.path),
            "send_receipt_path": "",
            "semantic_drain_receipt": dict(
                existing_dead_letter.get("preserved_pending_publish", {}).get(
                    "drain_receipt", {}
                )
            ),
            "domain_reply_publish_receipt": {},
            "semantic_reply_claim": bool(
                existing_dead_letter.get("semantic_reply_claim")
            ),
            "domain_receipt_claim": False,
            "reused_pending_publish": True,
            "semantic_success_pinned": True,
            "publish_attempt_count": int(
                existing_dead_letter.get("publish_attempt_count") or 0
            ),
            "max_publish_attempts": max_publish_attempts,
            "dead_letter_path": str(
                _dead_letter_path(state_dir, delivery.delivery_id)
            ),
            "terminal_effect_reused": True,
            "handler_ack_is_semantic_cognition": False,
            "authenticated_target_runtime_claim": False,
            "no_publish": no_publish,
            "operator_contact_note": (
                "Reused the immutable terminal delivery record. No semantic "
                "model or domain publisher was invoked."
            ),
        }
        write_responder_receipt(state_dir, receipt)
        return receipt

    send_receipt_path = find_send_receipt(
        send_receipt_root,
        agent_uid=agent_uid,
        packet_id=delivery.packet_id,
        reply_subject=delivery.reply_subject,
    )
    # Idempotency guard (fugu-verify flag, Phase A work item in
    # A2A_MASTER_SPEC_v1.md): if a prior tick already produced a model-authored
    # semantic success whose publish did not complete, reuse the pinned artifact
    # and retry publish only. The model critic is never re-run for that delivery,
    # so a good semantic reply cannot be overwritten by a later provider failure.
    pending_job = None if no_publish else load_pending_publish(state_dir, delivery.delivery_id)
    drain_receipt: dict[str, Any] | None = None
    publish_receipt: dict[str, Any] | None = None
    status = "FAILED"
    error = ""
    reused_pending_publish = False
    prior_publish_attempts = int(
        (pending_job or {}).get("publish_attempt_count") or 0
    )
    try:
        if pending_job is not None:
            drain_receipt = dict(pending_job.get("drain_receipt") or {})
            reused_pending_publish = True
        else:
            drain_receipt = drain_func(
                delivery_record_path=delivery.path,
                send_receipt_path=send_receipt_path,
                outbox_root=outbox_root,
                semantic_receipt_dir=semantic_receipt_dir,
                artifact_receipt_dir=artifact_receipt_dir,
                drain_receipt_dir=drain_receipt_dir,
                agent_uid=agent_uid,
                provider=provider,
                model=model,
            )
        status = "SEMANTIC_DRAINED_NO_PUBLISH" if no_publish else "SEMANTIC_DRAINED_SEND_RECEIPT_MISSING"
        artifact_path_str = str((drain_receipt or {}).get("domain_reply_artifact_path") or "")
        if not no_publish and send_receipt_path is not None and artifact_path_str:
            publish_receipt = publish_func(
                send_receipt_path=send_receipt_path,
                reply_artifact_path=Path(artifact_path_str),
                agent_uid=agent_uid,
                outbox_root=outbox_root,
                receipt_dir=domain_reply_receipt_dir,
                stream=stream,
                timeout_s=timeout_s,
                flush_timeout_s=flush_timeout_s,
            )
            status = str(publish_receipt.get("status") or "DOMAIN_REPLY_PUBLISH_UNKNOWN")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        status = "SEMANTIC_RESPONDER_FAILED"

    # Persist / clear the pending-publish pin. A semantic success whose publish
    # did not complete is saved so the next tick retries publish with the same
    # artifact; a completed publish clears the pin.
    semantic_success = bool((drain_receipt or {}).get("semantic_reply_claim"))
    publish_completed = status == "DOMAIN_REPLY_PUBLISHED"
    semantic_success_pinned = False
    dead_letter_path = ""
    terminal_effect_created = False
    publish_attempt_count = prior_publish_attempts
    if not no_publish and semantic_success and not publish_completed:
        publish_attempt_count = prior_publish_attempts + 1
        pending_snapshot = {
            **dict(pending_job or {}),
            "delivery_id": delivery.delivery_id,
            "packet_id": delivery.packet_id,
            "reply_subject": delivery.reply_subject,
            "delivery_record_path": str(delivery.path),
            "domain_reply_artifact_path": str(
                (drain_receipt or {}).get("domain_reply_artifact_path") or ""
            ),
            "semantic_receipt_path": str(
                (drain_receipt or {}).get("semantic_receipt_path") or ""
            ),
            "semantic_receipt_id": str(
                (drain_receipt or {}).get("semantic_receipt_id") or ""
            ),
            "semantic_reply_claim": True,
            "drain_receipt": drain_receipt or {},
            "publish_attempt_count": publish_attempt_count,
        }
        if publish_attempt_count >= max_publish_attempts:
            dead_letter, _, terminal_effect_created = write_dead_letter(
                state_dir,
                delivery,
                pending_job=pending_snapshot,
                attempt_count=publish_attempt_count,
                reason=(
                    "matching causal send receipt did not arrive"
                    if send_receipt_path is None
                    else "domain reply publication did not complete"
                ),
                error=error or status,
            )
            dead_letter_path = str(dead_letter)
            clear_pending_publish(state_dir, delivery.delivery_id)
            status = PUBLISH_RETRIES_EXHAUSTED_STATUS
            semantic_success_pinned = True
        else:
            try:
                save_pending_publish(
                    state_dir,
                    delivery,
                    drain_receipt=drain_receipt or {},
                    attempt_count=publish_attempt_count,
                    last_error=error or status,
                )
                semantic_success_pinned = True
            except OSError as exc:
                error = f"{type(exc).__name__}: {exc}"
                dead_letter, _, terminal_effect_created = write_dead_letter(
                    state_dir,
                    delivery,
                    pending_job=pending_snapshot,
                    attempt_count=publish_attempt_count,
                    reason="pending publish state could not be persisted safely",
                    error=error,
                )
                dead_letter_path = str(dead_letter)
                status = PUBLISH_RETRIES_EXHAUSTED_STATUS
                semantic_success_pinned = True
            # Only relabel when no publish was even attempted (send receipt or
            # artifact missing); a real publish failure keeps its own status so
            # it remains visible until the bounded terminal attempt.
            if publish_receipt is None and status != PUBLISH_RETRIES_EXHAUSTED_STATUS:
                status = PENDING_PUBLISH_STATUS
    elif publish_completed:
        clear_pending_publish(state_dir, delivery.delivery_id)

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": utc_now(),
        "status": status,
        "agent_uid": agent_uid,
        "delivery_id": delivery.delivery_id,
        "packet_id": delivery.packet_id,
        "reply_subject": delivery.reply_subject,
        "delivery_record_path": str(delivery.path),
        "send_receipt_path": str(send_receipt_path) if send_receipt_path else "",
        "semantic_drain_receipt": drain_receipt or {},
        "domain_reply_publish_receipt": publish_receipt or {},
        "semantic_reply_claim": bool((drain_receipt or {}).get("semantic_reply_claim")),
        "domain_receipt_claim": bool((publish_receipt or {}).get("domain_receipt_claim")),
        "reused_pending_publish": reused_pending_publish,
        "semantic_success_pinned": semantic_success_pinned,
        "publish_attempt_count": publish_attempt_count,
        "max_publish_attempts": max_publish_attempts,
        "dead_letter_path": dead_letter_path,
        "terminal_effect_created": terminal_effect_created,
        "handler_ack_is_semantic_cognition": False,
        "authenticated_target_runtime_claim": False,
        "no_publish": no_publish,
        "operator_contact_note": (
            "Codex Composer semantic responder processed a delivered A2A record. "
            "Delivery ACK, semantic drain, and domain reply publication are separate evidence tiers."
        ),
    }
    if error:
        receipt["error"] = error
    if not no_publish and send_receipt_path is None:
        receipt["operator_contact_note"] = (
            "Semantic artifact was written, but no matching send receipt was found; "
            "domain reply publication requires packet_id and reply_subject causation from the send receipt."
        )
    if reused_pending_publish:
        receipt["operator_contact_note"] = (
            "Reused a pinned model-authored semantic success and retried publish only; "
            "the model critic was not re-run, so a prior semantic reply cannot be "
            "overwritten by a later provider failure."
        )
    if status == PUBLISH_RETRIES_EXHAUSTED_STATUS:
        receipt["operator_contact_note"] = (
            "The pinned semantic success reached its bounded publication limit "
            "and was preserved in one immutable dead-letter record. No domain "
            "publication or remote effect is claimed."
        )
    write_responder_receipt(state_dir, receipt)
    return receipt


def quarantine_packet(
    *,
    inbox_dir: Path,
    state_dir: Path,
    agent_uid: str,
    packet_id: str,
    reason: str,
    lease_ttl_s: float,
) -> dict[str, Any]:
    """Terminalize one known pending semantic success without invoking a model."""

    matches = pending_deliveries(
        inbox_dir,
        agent_uid=agent_uid,
        processed_ids=set(),
        limit=0,
        packet_id=packet_id,
    )
    if len(matches) != 1:
        raise ValueError(
            f"quarantine requires exactly one delivery for packet {packet_id!r}; "
            f"found {len(matches)}"
        )
    delivery = matches[0]
    lease = acquire_lease(state_dir, delivery.delivery_id, ttl_s=lease_ttl_s)
    if lease is None:
        raise RuntimeError(f"delivery lease is held: {delivery.delivery_id}")
    try:
        existing = load_dead_letter(state_dir, delivery.delivery_id)
        pending_job = load_pending_publish(state_dir, delivery.delivery_id)
        if existing is None and pending_job is None:
            raise ValueError(
                "quarantine requires a pinned semantic success or an existing dead letter"
            )
        attempt_count = int(
            (existing or pending_job or {}).get("publish_attempt_count") or 1
        )
        if existing is None:
            dead_letter_path, dead_letter, created = write_dead_letter(
                state_dir,
                delivery,
                pending_job=dict(pending_job or {}),
                attempt_count=attempt_count,
                reason=reason,
                error=str((pending_job or {}).get("last_error") or ""),
                operator_quarantined=True,
            )
        else:
            dead_letter_path = _dead_letter_path(state_dir, delivery.delivery_id)
            dead_letter = existing
            created = False
        receipt = {
            "schema_version": SCHEMA_VERSION,
            "timestamp": utc_now(),
            "status": PUBLISH_RETRIES_EXHAUSTED_STATUS,
            "agent_uid": agent_uid,
            "delivery_id": delivery.delivery_id,
            "packet_id": delivery.packet_id,
            "reply_subject": delivery.reply_subject,
            "delivery_record_path": str(delivery.path),
            "send_receipt_path": "",
            "semantic_drain_receipt": dict(
                (pending_job or {}).get("drain_receipt") or {}
            ),
            "domain_reply_publish_receipt": {},
            "semantic_reply_claim": bool(
                (pending_job or dead_letter).get("semantic_reply_claim")
            ),
            "domain_receipt_claim": False,
            "reused_pending_publish": True,
            "semantic_success_pinned": True,
            "publish_attempt_count": attempt_count,
            "dead_letter_path": str(dead_letter_path),
            "terminal_effect_created": created,
            "operator_quarantined": True,
            "handler_ack_is_semantic_cognition": False,
            "authenticated_target_runtime_claim": False,
            "no_publish": False,
            "operator_contact_note": (
                "Operator-authorized quarantine preserved the pinned semantic "
                "artifact and terminalized the delivery without invoking a "
                "model or publisher."
            ),
        }
        receipt_path = write_responder_receipt(state_dir, receipt)
        mark_processed(
            state_dir,
            delivery,
            status=PUBLISH_RETRIES_EXHAUSTED_STATUS,
            receipt_path=str(receipt_path),
        )
        clear_pending_publish(state_dir, delivery.delivery_id)
        return receipt
    finally:
        release_lease(lease)


def run_once(
    *,
    inbox_dir: Path,
    state_dir: Path,
    send_receipt_root: Path,
    outbox_root: Path,
    semantic_receipt_dir: Path,
    artifact_receipt_dir: Path,
    drain_receipt_dir: Path,
    domain_reply_receipt_dir: Path,
    agent_uid: str,
    provider: str,
    model: str,
    no_publish: bool,
    stream: str,
    timeout_s: float,
    flush_timeout_s: float,
    limit: int,
    lease_ttl_s: float,
    max_publish_attempts: int = DEFAULT_MAX_PUBLISH_ATTEMPTS,
    packet_id: str = "",
    canonical_state_path: Path | None = None,
    project_canonical_state: bool = True,
    canonical_projector: CanonicalProjector = project_canonical_responder_state,
    drain_func: DrainFunc = drain_semantic_inbox,
    publish_func: PublishFunc = publish_domain_reply_sync,
) -> list[dict[str, Any]]:
    seen = processed_delivery_ids(state_dir)
    deliveries = pending_deliveries(
        inbox_dir,
        agent_uid=agent_uid,
        processed_ids=seen,
        limit=limit,
        packet_id=packet_id,
    )
    receipts: list[dict[str, Any]] = []
    claimed_deliveries = 0
    for delivery in deliveries:
        lease = acquire_lease(state_dir, delivery.delivery_id, ttl_s=lease_ttl_s)
        if lease is None:
            continue
        claimed_deliveries += 1
        try:
            receipt = process_delivery(
                delivery,
                state_dir=state_dir,
                send_receipt_root=send_receipt_root,
                outbox_root=outbox_root,
                semantic_receipt_dir=semantic_receipt_dir,
                artifact_receipt_dir=artifact_receipt_dir,
                drain_receipt_dir=drain_receipt_dir,
                domain_reply_receipt_dir=domain_reply_receipt_dir,
                agent_uid=agent_uid,
                provider=provider,
                model=model,
                no_publish=no_publish,
                stream=stream,
                timeout_s=timeout_s,
                flush_timeout_s=flush_timeout_s,
                max_publish_attempts=max_publish_attempts,
                drain_func=drain_func,
                publish_func=publish_func,
            )
            receipts.append(receipt)
            status = str(receipt.get("status") or "unknown")
            if should_mark_processed(status):
                mark_processed(
                    state_dir,
                    delivery,
                    status=status,
                    receipt_path=str(receipt.get("receipt_path") or ""),
                )
        finally:
            release_lease(lease)
    if receipts:
        loop_status = str(receipts[-1].get("status") or "unknown")
        latest_receipt = receipts[-1]
    elif deliveries and claimed_deliveries == 0:
        loop_status = DELIVERIES_LEASE_HELD_STATUS
        latest_receipt = None
    else:
        loop_status = NO_PENDING_DELIVERIES_STATUS
        latest_receipt = None
    write_responder_heartbeat(
        state_dir,
        agent_uid=agent_uid,
        provider=provider,
        model=model,
        loop_status=loop_status,
        pending_delivery_count=len(deliveries),
        latest_receipt=latest_receipt,
        canonical_state_path=canonical_state_path,
        project_canonical_state=project_canonical_state,
        canonical_projector=canonical_projector,
    )
    return receipts


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "mode",
        choices=["once", "loop", "baseline", "quarantine"],
        nargs="?",
        default="once",
    )
    parser.add_argument("--agent-uid", default=DEFAULT_AGENT_UID)
    parser.add_argument("--inbox-dir", default=str(DEFAULT_INBOX_DIR))
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument("--send-receipt-root", default=str(DEFAULT_SEND_RECEIPT_ROOT))
    parser.add_argument("--outbox-root", default=str(DEFAULT_OUTBOX_ROOT))
    parser.add_argument("--semantic-receipt-dir", default=str(DEFAULT_SEMANTIC_RECEIPT_DIR))
    parser.add_argument("--artifact-receipt-dir", default=str(DEFAULT_ARTIFACT_RECEIPT_DIR))
    parser.add_argument("--drain-receipt-dir", default=str(DEFAULT_DRAIN_RECEIPT_DIR))
    parser.add_argument("--domain-reply-receipt-dir", default=str(DEFAULT_DOMAIN_REPLY_RECEIPT_DIR))
    parser.add_argument("--provider", default=None, help="runtime provider; default resolves via runtime_provider")
    parser.add_argument("--model", default=None, help="model id; default resolves via runtime_provider")
    parser.add_argument("--stream", default="DHARMA_FLEET")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--interval-s", type=float, default=30.0)
    parser.add_argument("--lease-ttl-s", type=float, default=1800.0)
    parser.add_argument("--packet-id", default="", help="only process this packet id")
    parser.add_argument(
        "--max-publish-attempts",
        type=int,
        default=DEFAULT_MAX_PUBLISH_ATTEMPTS,
        help="terminalize a pinned semantic success after this many publish cycles",
    )
    parser.add_argument(
        "--quarantine-reason",
        default="operator-authorized poison-packet containment",
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--flush-timeout", type=float, default=2.0)
    parser.add_argument(
        "--canonical-state-path",
        default="",
        help="canonical fleet state path; defaults to ~/.dharma/a2a_bus/state/{agent_uid}.json",
    )
    parser.add_argument(
        "--no-canonical-state",
        action="store_true",
        help="write responder-local heartbeat only, without canonical fleet-state projection",
    )
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    canonical_state_path = (
        _path(args.canonical_state_path)
        if args.canonical_state_path
        else canonical_state_path_for_agent(args.agent_uid)
    )

    common = {
        "inbox_dir": _path(args.inbox_dir),
        "state_dir": _path(args.state_dir),
        "send_receipt_root": _path(args.send_receipt_root),
        "outbox_root": _path(args.outbox_root),
        "semantic_receipt_dir": _path(args.semantic_receipt_dir),
        "artifact_receipt_dir": _path(args.artifact_receipt_dir),
        "drain_receipt_dir": _path(args.drain_receipt_dir),
        "domain_reply_receipt_dir": _path(args.domain_reply_receipt_dir),
        "agent_uid": args.agent_uid,
        "provider": args.provider,
        "model": args.model,
        "no_publish": args.no_publish,
        "stream": args.stream,
        "timeout_s": args.timeout,
        "flush_timeout_s": args.flush_timeout,
        "limit": args.limit,
        "lease_ttl_s": args.lease_ttl_s,
        "max_publish_attempts": args.max_publish_attempts,
        "packet_id": args.packet_id,
        "canonical_state_path": canonical_state_path,
        "project_canonical_state": not args.no_canonical_state,
    }

    if args.mode == "quarantine":
        if not args.packet_id:
            parser.error("quarantine mode requires --packet-id")
        receipt = quarantine_packet(
            inbox_dir=common["inbox_dir"],
            state_dir=common["state_dir"],
            agent_uid=args.agent_uid,
            packet_id=args.packet_id,
            reason=args.quarantine_reason,
            lease_ttl_s=args.lease_ttl_s,
        )
        if args.json:
            print(json.dumps(receipt, indent=2, sort_keys=True))
        else:
            print(
                f"{receipt['status']} packet_id={receipt['packet_id']} "
                f"dead_letter={receipt['dead_letter_path']}"
            )
        return 0

    if args.mode == "baseline":
        receipt = baseline_existing_deliveries(
            common["inbox_dir"],
            state_dir=common["state_dir"],
            agent_uid=args.agent_uid,
            provider=args.provider,
            model=args.model,
            canonical_state_path=canonical_state_path,
            project_canonical_state=not args.no_canonical_state,
        )
        if args.json:
            print(json.dumps(receipt, indent=2, sort_keys=True))
        else:
            print(f"{receipt['status']} delivery_count={receipt['delivery_count']}")
            print(f"receipt: {receipt['receipt_path']}")
        return 0

    while True:
        receipts = run_once(**common)
        if args.json:
            print(json.dumps({"receipts": receipts}, indent=2, sort_keys=True))
        else:
            if receipts:
                for receipt in receipts:
                    print(
                        f"{receipt['status']} packet_id={receipt['packet_id']} "
                        f"semantic={receipt['semantic_reply_claim']} domain={receipt['domain_receipt_claim']}"
                    )
                    print(f"receipt: {receipt['receipt_path']}")
            else:
                print("NO_PENDING_DELIVERIES")
        if args.mode == "once":
            return 0
        time.sleep(max(args.interval_s, 1.0))


if __name__ == "__main__":
    raise SystemExit(main())
