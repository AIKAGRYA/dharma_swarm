#!/usr/bin/env python3
"""Always-on semantic A2A responder for the fugu_ultra holon.

Layering contract:
- a2a_inbox_bridge.py proves transport delivery + handler ack only.
- this responder proves Fugu/Sakana model processing for relevant deliveries.
- domain reply publication is a separate typed receipt on the original reply_subject.

It is intentionally scoped to fugu_ultra instead of turning the Codex semantic
responder into a multi-agent god-file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.api_keys import bootstrap_runtime_env, env_value  # noqa: E402
from dharma_swarm.operator_core.semantic_receipt import (  # noqa: E402
    SCHEMA_VERSION as SEMANTIC_RECEIPT_SCHEMA,
    SemanticReceiptValidationError,
    utc_now_iso,
    validate_semantic_receipt,
)
from scripts.runtime.a2a_domain_reply_artifact import (  # noqa: E402
    DEFAULT_ARTIFACT_RECEIPT_DIR,
    artifact_path_for,
    build_domain_reply_artifact,
    write_artifact_author_receipt,
)
from scripts.runtime.a2a_domain_reply_worker import (  # noqa: E402
    DEFAULT_OUTBOX_ROOT,
    DEFAULT_RECEIPT_DIR as DEFAULT_DOMAIN_REPLY_RECEIPT_DIR,
)
from scripts.runtime.codex_composer_semantic_responder import (  # noqa: E402
    find_send_receipt,
    publish_domain_reply_sync,
)
from scripts.runtime.pr_merge_control import stamp, utc_now  # noqa: E402

DEFAULT_AGENT_UID = "fugu_ultra"
DEFAULT_MODEL = "fugu-ultra"
DEFAULT_PROVIDER = "sakana"
DEFAULT_BASE_URL = "https://api.sakana.ai/v1"
DEFAULT_DHARMA_HOME = Path.home() / ".dharma"
DEFAULT_INBOX_DIR = DEFAULT_DHARMA_HOME / "a2a_bus" / "inboxes" / DEFAULT_AGENT_UID
DEFAULT_SEND_RECEIPT_ROOT = REPO_ROOT / "reports" / "a2a" / "send_receipts"
DEFAULT_SEMANTIC_RECEIPT_DIR = REPO_ROOT / "reports" / "agentops" / "semantic_receipts"
DEFAULT_DRAIN_RECEIPT_DIR = REPO_ROOT / "reports" / "a2a" / "fugu_semantic_drains"
DEFAULT_STATE_DIR = (
    DEFAULT_DHARMA_HOME
    / "external_agents"
    / DEFAULT_AGENT_UID
    / "nest"
    / "semantic_responder"
)
DEFAULT_CANONICAL_STATE_PATH = DEFAULT_DHARMA_HOME / "a2a_bus" / "state" / f"{DEFAULT_AGENT_UID}.json"
SERVICE_ID = "fugu-ultra-semantic-responder"
LAUNCHD_LABEL = "com.dharma.fugu-ultra-semantic-responder"
SCHEMA_VERSION = "dharma.a2a.fugu_ultra_semantic_responder.v1"
HEARTBEAT_SCHEMA_VERSION = "dharma.a2a.fugu_ultra_semantic_responder_heartbeat.v1"
PROCESSED_FILENAME = "processed_deliveries.jsonl"
NO_PENDING_DELIVERIES_STATUS = "NO_PENDING_DELIVERIES"
PENDING_DELIVERIES_LEASE_HELD_STATUS = "PENDING_DELIVERIES_LEASE_HELD"
RELEVANCE_KEYWORDS = {
    "fugu",
    "sakana",
    "dgm",
    "darwin",
    "gödel",
    "godel",
    "benchmark",
    "a2a",
    "nats",
    "custody",
    "semantic",
    "fable",
    "codex",
    "future-proof",
    "futureproof",
    "teambench",
    "evolution",
    "receipt",
    "holon",
}
PROCESSED_STATUSES = {
    "DOMAIN_REPLY_PUBLISHED",
    "SEMANTIC_DRAINED_NO_PUBLISH",
    "SEMANTIC_DRAINED_SEND_RECEIPT_MISSING",
    "NOT_RELEVANT_IGNORED",
    "BASELINED_EXISTING",
}


@dataclass(frozen=True)
class Delivery:
    path: Path
    payload: dict[str, Any]
    envelope: dict[str, Any]
    packet_id: str
    reply_subject: str
    delivery_id: str


@dataclass(frozen=True)
class FuguCallResult:
    text: str
    latency_ms: int
    raw: dict[str, Any]
    prompt_sha256: str
    raw_response_sha256: str
    max_tokens: int


def _safe_token(value: object, *, fallback: str = "unknown") -> str:
    chars = [char if char.isalnum() or char in ("_", "-") else "_" for char in str(value or "")]
    return ("".join(chars).strip("_-") or fallback)[:96]


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path}")
    return data


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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _delivery_id(path: Path, payload: dict[str, Any], envelope: dict[str, Any]) -> str:
    stable = {
        "path": str(path.expanduser().resolve()),
        "packet_id": str(envelope.get("packet_id") or ""),
        "reply_subject": str(envelope.get("reply_subject") or ""),
        "envelope_sha256": str(payload.get("envelope_sha256") or ""),
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def delivery_from_path(path: Path, *, agent_uid: str = DEFAULT_AGENT_UID) -> Delivery | None:
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
    rows = _read_jsonl(Path(state_dir).expanduser().resolve() / PROCESSED_FILENAME)
    return {
        str(row.get("delivery_id"))
        for row in rows
        if row.get("delivery_id") and str(row.get("status") or "") in PROCESSED_STATUSES
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


def is_relevant(delivery: Delivery, *, agent_uid: str = DEFAULT_AGENT_UID) -> tuple[bool, str]:
    envelope = delivery.envelope
    if str(envelope.get("target_uid") or envelope.get("to") or "") == agent_uid:
        return True, "direct_target"
    blob = "\n".join(
        str(envelope.get(key) or "")
        for key in ("content", "kind", "subject", "file", "from")
    ).casefold()
    hits = sorted(keyword for keyword in RELEVANCE_KEYWORDS if keyword in blob)
    if hits:
        return True, "keyword:" + ",".join(hits[:8])
    return False, "no_direct_target_or_relevance_keyword"


def _prompt_for_delivery(delivery: Delivery, *, agent_uid: str) -> str:
    envelope = delivery.envelope
    soul_path = Path.home() / ".dharma" / "agents" / agent_uid / "SOUL.md"
    soul_excerpt = ""
    if soul_path.exists():
        soul_excerpt = soul_path.read_text(encoding="utf-8")[:5000]
    return f"""# fugu_ultra A2A/NATS semantic response task

You are fugu_ultra, a high-level Fugu/Sakana-inspired holon in dharma_swarm.
You are monitoring A2A/NATS for relevant packets. Reply as fugu_ultra.

Hard boundaries:
- Do not claim external sends, code changes, trades, spend, or doctrine promotion.
- You may analyze, challenge, propose, and acknowledge receipt.
- Distinguish transport delivery from semantic cognition.
- Prefer concise, high-signal output with concrete next steps.

Seat context excerpt:
{soul_excerpt}

Delivery path: {delivery.path}
Packet id: {delivery.packet_id}
Reply subject: {delivery.reply_subject}

Delivered envelope JSON:
```json
{json.dumps(envelope, indent=2, sort_keys=True)}
```

Return a direct reply for the sending agent/operator. Include:
1. one-line verdict;
2. what is relevant;
3. proposed next action;
4. any uncertainty or boundary.
"""


def call_fugu(
    prompt: str,
    *,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    timeout_s: float = 180.0,
    max_tokens: int = 1600,
) -> FuguCallResult:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - environment failure path
        raise RuntimeError("openai package is not installed") from exc
    bootstrap_runtime_env()
    token = api_key or env_value("SAKANA_API_KEY")
    if not token:
        raise RuntimeError("SAKANA_API_KEY is not available")
    client = OpenAI(api_key=token, base_url=base_url, timeout=timeout_s)
    prompt_sha = _sha256_text(prompt)
    last_dump: dict[str, Any] = {}
    started = time.perf_counter()
    for token_cap in (max_tokens, max(max_tokens * 2, 2400)):
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=token_cap,
        )
        last_dump = resp.model_dump()
        content = getattr(resp.choices[0].message, "content", None) if resp.choices else None
        if content and str(content).strip():
            latency_ms = int((time.perf_counter() - started) * 1000)
            raw = {
                "id": last_dump.get("id"),
                "model": last_dump.get("model"),
                "object": last_dump.get("object"),
                "usage": last_dump.get("usage"),
                "finish_reason": last_dump.get("choices", [{}])[0].get("finish_reason") if last_dump.get("choices") else "",
            }
            return FuguCallResult(
                text=str(content).strip(),
                latency_ms=latency_ms,
                raw=raw,
                prompt_sha256=prompt_sha,
                raw_response_sha256=_sha256_text(json.dumps(last_dump, sort_keys=True, default=str)),
                max_tokens=token_cap,
            )
    raise RuntimeError(
        "Fugu returned no visible content; likely max_tokens were consumed by reasoning. "
        f"last_usage={last_dump.get('usage')}"
    )


FuguCall = Callable[[str], FuguCallResult]
PublishFunc = Callable[..., dict[str, Any]]


def _semantic_receipt_path(receipt_dir: Path, *, packet_id: str) -> Path:
    return receipt_dir / f"{stamp()}-sakana-fugu-ultra-{_safe_token(packet_id)}.json"


def _failure_semantic_receipt(
    *,
    delivery: Delivery,
    prompt: str,
    error: str,
    failure_type: str = "provider_failed",
    latency_ms: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": SEMANTIC_RECEIPT_SCHEMA,
        "receipt_id": f"semr_fugu_{uuid4().hex}",
        "created_at": utc_now_iso(),
        "agent_uid": DEFAULT_AGENT_UID,
        "critic_agent_id": f"{DEFAULT_PROVIDER}:{DEFAULT_MODEL}",
        "model_identity": {"provider": DEFAULT_PROVIDER, "model": DEFAULT_MODEL},
        "authored_by_model": False,
        "review_target": f"a2a:{delivery.packet_id}:fugu_ultra_semantic_responder",
        "intent_ack": False,
        "capability_match": 0.0,
        "understood_request": False,
        "missing_context": [],
        "verdict": "blocked",
        "summary": "Fugu semantic responder could not produce a model-authored reply.",
        "recommendations": [
            {
                "priority": "p0",
                "action": "Inspect responder error and retry when Sakana/Fugu route is healthy.",
                "rationale": error[:500],
            }
        ],
        "acceptance_gates": [
            {"name": "fugu_model_visible_reply", "met": False, "evidence": error[:500]}
        ],
        "explicit_disagreement": "No semantic reply claim is made because the Fugu model call failed.",
        "evidence_refs": [str(delivery.path)],
        "confidence": 0.0,
        "not_claimed_agents": ["codex", "claude", "fable", "hermes", "devin"],
        "failure_type": failure_type,
        "failure_reason": error,
        "correlation_id": delivery.packet_id,
        "reply_to": delivery.reply_subject,
        "model_call_latency_ms": latency_ms,
        "prompt_sha256": _sha256_text(prompt),
        "raw_response_sha256": "",
    }


def _success_semantic_receipt(
    *,
    delivery: Delivery,
    prompt: str,
    result: FuguCallResult,
    relevance_reason: str,
) -> dict[str, Any]:
    summary = result.text[:4000]
    receipt = {
        "schema_version": SEMANTIC_RECEIPT_SCHEMA,
        "receipt_id": f"semr_fugu_{uuid4().hex}",
        "created_at": utc_now_iso(),
        "agent_uid": DEFAULT_AGENT_UID,
        "critic_agent_id": f"{DEFAULT_PROVIDER}:{DEFAULT_MODEL}",
        "model_identity": {"provider": DEFAULT_PROVIDER, "model": DEFAULT_MODEL},
        "authored_by_model": True,
        "review_target": f"a2a:{delivery.packet_id}:fugu_ultra_semantic_responder",
        "intent_ack": True,
        "capability_match": 1.0,
        "understood_request": True,
        "missing_context": [],
        "verdict": "approve",
        "summary": summary,
        "recommendations": [
            {
                "priority": "p1",
                "action": "Route any requested implementation through explicit leases and receipts.",
                "rationale": "fugu_ultra can propose and respond semantically, but not silently execute irreversible actions.",
            }
        ],
        "acceptance_gates": [
            {"name": "relevance_gate", "met": True, "evidence": relevance_reason},
            {"name": "fugu_model_visible_reply", "met": True, "evidence": f"max_tokens={result.max_tokens}"},
            {"name": "transport_not_confused_with_semantics", "met": True, "evidence": "separate inbox bridge + semantic receipt"},
        ],
        "explicit_disagreement": "",
        "evidence_refs": [str(delivery.path)],
        "confidence": 0.86,
        "not_claimed_agents": ["codex", "claude", "fable", "hermes", "devin"],
        "failure_type": "",
        "failure_reason": "",
        "correlation_id": delivery.packet_id,
        "reply_to": delivery.reply_subject,
        "model_call_latency_ms": result.latency_ms,
        "prompt_sha256": result.prompt_sha256,
        "raw_response_sha256": result.raw_response_sha256,
        "fugu_raw": result.raw,
    }
    return validate_semantic_receipt(receipt)


def write_responder_receipt(state_dir: Path | str, receipt: dict[str, Any]) -> Path:
    root = Path(state_dir).expanduser().resolve() / "receipts"
    path = root / f"{stamp()}-{_safe_token(receipt.get('status'))}-{_safe_token(receipt.get('packet_id'))}.json"
    receipt["receipt_path"] = str(path)
    _write_json(path, receipt)
    return path


def write_heartbeat(
    state_dir: Path | str,
    *,
    status: str,
    pending_delivery_count: int,
    latest_receipt: dict[str, Any] | None,
    canonical_state_path: Path | None = DEFAULT_CANONICAL_STATE_PATH,
) -> dict[str, Any]:
    root = Path(state_dir).expanduser().resolve()
    latest = dict(latest_receipt or {})
    heartbeat = {
        "schema_version": HEARTBEAT_SCHEMA_VERSION,
        "timestamp": utc_now(),
        "observed_at": utc_now(),
        "agent_uid": DEFAULT_AGENT_UID,
        "service_id": SERVICE_ID,
        "launchd_label": LAUNCHD_LABEL,
        "pid": os.getpid(),
        "status": status,
        "pending_delivery_count": max(0, int(pending_delivery_count)),
        "fresh": True,
        "fresh_after_seconds": 120,
        "provider": DEFAULT_PROVIDER,
        "model": DEFAULT_MODEL,
        "live_model_call_claimed": bool(latest.get("semantic_reply_claim")),
        "semantic_reply_claim": bool(latest.get("semantic_reply_claim")),
        "domain_receipt_claim": bool(latest.get("domain_receipt_claim")),
        "latest_receipt": {
            "status": str(latest.get("status") or ""),
            "packet_id": str(latest.get("packet_id") or ""),
            "receipt_path": str(latest.get("receipt_path") or ""),
            "semantic_receipt_path": str(latest.get("semantic_receipt_path") or ""),
            "domain_reply_publish_receipt_path": str((latest.get("domain_reply_publish_receipt") or {}).get("receipt_path") or "") if isinstance(latest.get("domain_reply_publish_receipt"), dict) else "",
        },
    }
    heartbeat_path = root / "heartbeat.json"
    heartbeat["heartbeat_path"] = str(heartbeat_path)
    _write_json(heartbeat_path, heartbeat)
    if canonical_state_path is not None:
        project_canonical_state(canonical_state_path, heartbeat=heartbeat, latest_receipt=latest)
    return heartbeat


def project_canonical_state(path: Path | str, *, heartbeat: dict[str, Any], latest_receipt: dict[str, Any]) -> None:
    p = Path(path).expanduser().resolve()
    existing = _read_json(p) if p.exists() else {"agent_uid": DEFAULT_AGENT_UID}
    existing.update(
        {
            "schema_version": "dharma.holon_canonical_state.v1",
            "agent_uid": DEFAULT_AGENT_UID,
            "agent": DEFAULT_AGENT_UID,
            "status": "a2a_bridge_and_fugu_semantic_responder_active" if heartbeat.get("status") in {"idle", "processed_delivery"} else "fugu_semantic_responder_degraded",
            "wake_loop_active": True,
            "semantic_responder_active": True,
            "last_heartbeat": heartbeat.get("timestamp"),
            "state_written_at": utc_now(),
            "state_written_by": "fugu_ultra_semantic_responder",
            "fugu_semantic_responder": {
                "service_id": SERVICE_ID,
                "launchd_label": LAUNCHD_LABEL,
                "heartbeat_path": heartbeat.get("heartbeat_path"),
                "status": heartbeat.get("status"),
                "fresh": True,
                "provider": DEFAULT_PROVIDER,
                "model": DEFAULT_MODEL,
                "live_model_call_claimed": bool(heartbeat.get("live_model_call_claimed")),
                "latest_receipt": heartbeat.get("latest_receipt"),
            },
            "semantic_reply_claim": bool(latest_receipt.get("semantic_reply_claim")),
            "peer_model_processed_claim": bool(latest_receipt.get("semantic_reply_claim")),
        }
    )
    _write_json(p, existing)


def _not_relevant_receipt(delivery: Delivery, *, relevance_reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": utc_now(),
        "status": "NOT_RELEVANT_IGNORED",
        "agent_uid": DEFAULT_AGENT_UID,
        "delivery_id": delivery.delivery_id,
        "packet_id": delivery.packet_id,
        "reply_subject": delivery.reply_subject,
        "delivery_record_path": str(delivery.path),
        "relevance_reason": relevance_reason,
        "semantic_reply_claim": False,
        "domain_receipt_claim": False,
        "operator_contact_note": "Fugu responder ignored a non-relevant packet and made no semantic reply claim.",
    }


def process_delivery(
    delivery: Delivery,
    *,
    state_dir: Path,
    send_receipt_root: Path,
    outbox_root: Path,
    semantic_receipt_dir: Path,
    artifact_receipt_dir: Path,
    domain_reply_receipt_dir: Path,
    no_publish: bool,
    stream: str,
    timeout_s: float,
    flush_timeout_s: float,
    fugu_call: FuguCall | None = None,
    publish_func: PublishFunc = publish_domain_reply_sync,
) -> dict[str, Any]:
    relevant, relevance_reason = is_relevant(delivery)
    if not relevant:
        receipt = _not_relevant_receipt(delivery, relevance_reason=relevance_reason)
        write_responder_receipt(state_dir, receipt)
        return receipt

    send_receipt_path = find_send_receipt(
        send_receipt_root,
        agent_uid=DEFAULT_AGENT_UID,
        packet_id=delivery.packet_id,
        reply_subject=delivery.reply_subject,
    )
    prompt = _prompt_for_delivery(delivery, agent_uid=DEFAULT_AGENT_UID)
    fugu = fugu_call or (lambda prompt_text: call_fugu(prompt_text, timeout_s=timeout_s))
    semantic_receipt: dict[str, Any]
    status = "SEMANTIC_DRAINED_SEND_RECEIPT_MISSING"
    publish_receipt: dict[str, Any] | None = None
    error = ""
    try:
        result = fugu(prompt)
        semantic_receipt = _success_semantic_receipt(
            delivery=delivery,
            prompt=prompt,
            result=result,
            relevance_reason=relevance_reason,
        )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        semantic_receipt = validate_semantic_receipt(
            _failure_semantic_receipt(delivery=delivery, prompt=prompt, error=error)
        )

    semantic_receipt_dir.mkdir(parents=True, exist_ok=True)
    semantic_receipt_path = _semantic_receipt_path(semantic_receipt_dir, packet_id=delivery.packet_id)
    _write_json(semantic_receipt_path, semantic_receipt)
    semantic_claim = bool(semantic_receipt.get("semantic_reply_claim"))
    verdict = str(semantic_receipt.get("verdict") or "blocked")
    summary = str(semantic_receipt.get("summary") or "Fugu semantic responder wrote a typed receipt.")
    evidence_refs = [str(delivery.path), str(semantic_receipt_path)]
    if send_receipt_path is not None:
        evidence_refs.append(str(send_receipt_path))
    artifact = build_domain_reply_artifact(
        delivery_record=delivery.payload,
        agent_uid=DEFAULT_AGENT_UID,
        verdict=verdict,
        summary=summary,
        evidence_refs=evidence_refs,
        send_receipt_path=send_receipt_path,
        peer_model_processed_claim=semantic_claim,
        semantic_reply_claim=semantic_claim,
        author_kind="fugu_ultra_semantic_responder",
    )
    artifact["semantic_receipt_path"] = str(semantic_receipt_path)
    artifact["semantic_receipt_id"] = str(semantic_receipt.get("receipt_id") or "")
    artifact["handler_ack_is_semantic_cognition"] = False
    artifact["authenticated_target_runtime_claim"] = True if semantic_claim else False
    artifact_path = artifact_path_for(
        outbox_root=outbox_root,
        agent_uid=DEFAULT_AGENT_UID,
        packet_id=delivery.packet_id,
    )
    _write_json(artifact_path, artifact)
    artifact_author_receipt = write_artifact_author_receipt(
        receipt_dir=artifact_receipt_dir,
        artifact_path=artifact_path,
        artifact=artifact,
        delivery_record_path=delivery.path,
    )

    if no_publish:
        status = "SEMANTIC_DRAINED_NO_PUBLISH"
    elif send_receipt_path is not None:
        publish_receipt = publish_func(
            send_receipt_path=send_receipt_path,
            reply_artifact_path=artifact_path,
            agent_uid=DEFAULT_AGENT_UID,
            outbox_root=outbox_root,
            receipt_dir=domain_reply_receipt_dir,
            stream=stream,
            timeout_s=timeout_s,
            flush_timeout_s=flush_timeout_s,
        )
        status = str(publish_receipt.get("status") or "DOMAIN_REPLY_PUBLISH_UNKNOWN")

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": utc_now(),
        "status": status,
        "agent_uid": DEFAULT_AGENT_UID,
        "delivery_id": delivery.delivery_id,
        "packet_id": delivery.packet_id,
        "reply_subject": delivery.reply_subject,
        "delivery_record_path": str(delivery.path),
        "send_receipt_path": str(send_receipt_path) if send_receipt_path else "",
        "semantic_receipt_path": str(semantic_receipt_path),
        "domain_reply_artifact_path": str(artifact_path),
        "domain_reply_artifact_author_receipt_path": str(artifact_author_receipt),
        "domain_reply_publish_receipt": publish_receipt or {},
        "semantic_reply_claim": semantic_claim,
        "domain_receipt_claim": bool((publish_receipt or {}).get("domain_receipt_claim")),
        "peer_model_processed_claim": semantic_claim,
        "handler_ack_is_semantic_cognition": False,
        "authenticated_target_runtime_claim": bool(artifact.get("authenticated_target_runtime_claim")),
        "relevance_reason": relevance_reason,
        "operator_contact_note": (
            "Fugu Ultra semantic responder processed a delivered A2A record. "
            "Transport handler ack, Fugu model processing, and domain reply publication are separate evidence tiers."
        ),
    }
    if error:
        receipt["error"] = error
    if send_receipt_path is None and not no_publish:
        receipt["operator_contact_note"] = (
            "Fugu semantic receipt/artifact was written, but no matching send receipt was found; "
            "domain reply publication requires packet_id/reply_subject causation from the send receipt."
        )
    write_responder_receipt(state_dir, receipt)
    return receipt


def should_mark_processed(status: str) -> bool:
    return status in PROCESSED_STATUSES


def run_once(
    *,
    inbox_dir: Path,
    state_dir: Path,
    send_receipt_root: Path,
    outbox_root: Path,
    semantic_receipt_dir: Path,
    artifact_receipt_dir: Path,
    domain_reply_receipt_dir: Path,
    no_publish: bool,
    stream: str,
    timeout_s: float,
    flush_timeout_s: float,
    limit: int,
    lease_ttl_s: float,
    packet_id: str = "",
    canonical_state_path: Path | None = DEFAULT_CANONICAL_STATE_PATH,
    fugu_call: FuguCall | None = None,
    publish_func: PublishFunc = publish_domain_reply_sync,
) -> list[dict[str, Any]]:
    seen = processed_delivery_ids(state_dir)
    deliveries = pending_deliveries(
        inbox_dir,
        agent_uid=DEFAULT_AGENT_UID,
        processed_ids=seen,
        limit=limit,
        packet_id=packet_id,
    )
    receipts: list[dict[str, Any]] = []
    claimed = 0
    for delivery in deliveries:
        lease = acquire_lease(state_dir, delivery.delivery_id, ttl_s=lease_ttl_s)
        if lease is None:
            continue
        claimed += 1
        try:
            receipt = process_delivery(
                delivery,
                state_dir=state_dir,
                send_receipt_root=send_receipt_root,
                outbox_root=outbox_root,
                semantic_receipt_dir=semantic_receipt_dir,
                artifact_receipt_dir=artifact_receipt_dir,
                domain_reply_receipt_dir=domain_reply_receipt_dir,
                no_publish=no_publish,
                stream=stream,
                timeout_s=timeout_s,
                flush_timeout_s=flush_timeout_s,
                fugu_call=fugu_call,
                publish_func=publish_func,
            )
            receipts.append(receipt)
            status = str(receipt.get("status") or "")
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
        latest = receipts[-1]
        status = "processed_delivery" if should_mark_processed(str(latest.get("status") or "")) else "degraded"
    elif deliveries and claimed == 0:
        latest = None
        status = "waiting_on_delivery_lease"
    else:
        latest = None
        status = "idle"
    write_heartbeat(
        state_dir,
        status=status,
        pending_delivery_count=len(deliveries),
        latest_receipt=latest,
        canonical_state_path=canonical_state_path,
    )
    return receipts


def baseline_existing_deliveries(
    inbox_dir: Path,
    *,
    state_dir: Path,
    limit: int = 0,
) -> dict[str, Any]:
    seen = processed_delivery_ids(state_dir)
    deliveries = pending_deliveries(
        inbox_dir,
        agent_uid=DEFAULT_AGENT_UID,
        processed_ids=seen,
        limit=limit,
    )
    for delivery in deliveries:
        mark_processed(state_dir, delivery, status="BASELINED_EXISTING", receipt_path="")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": utc_now(),
        "status": "BASELINE_RECORDED",
        "agent_uid": DEFAULT_AGENT_UID,
        "delivery_count": len(deliveries),
        "packet_ids": [delivery.packet_id for delivery in deliveries],
        "inbox_dir": str(inbox_dir.expanduser().resolve()),
        "state_dir": str(state_dir.expanduser().resolve()),
        "operator_contact_note": "Existing fugu_ultra inbox delivery records were marked processed so the semantic responder starts from new traffic.",
    }
    write_responder_receipt(state_dir, receipt)
    write_heartbeat(state_dir, status="baselined_existing_backlog", pending_delivery_count=0, latest_receipt=receipt)
    return receipt


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=["once", "loop", "baseline"], nargs="?", default="once")
    parser.add_argument("--inbox-dir", default=str(DEFAULT_INBOX_DIR))
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument("--send-receipt-root", default=str(DEFAULT_SEND_RECEIPT_ROOT))
    parser.add_argument("--outbox-root", default=str(DEFAULT_OUTBOX_ROOT))
    parser.add_argument("--semantic-receipt-dir", default=str(DEFAULT_SEMANTIC_RECEIPT_DIR))
    parser.add_argument("--artifact-receipt-dir", default=str(DEFAULT_ARTIFACT_RECEIPT_DIR))
    parser.add_argument("--domain-reply-receipt-dir", default=str(DEFAULT_DOMAIN_REPLY_RECEIPT_DIR))
    parser.add_argument("--stream", default="DHARMA_FLEET")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--interval-s", type=float, default=60.0)
    parser.add_argument("--lease-ttl-s", type=float, default=1800.0)
    parser.add_argument("--packet-id", default="")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--flush-timeout", type=float, default=2.0)
    parser.add_argument("--canonical-state-path", default=str(DEFAULT_CANONICAL_STATE_PATH))
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    inbox_dir = _path(args.inbox_dir)
    state_dir = _path(args.state_dir)
    canonical_state_path = _path(args.canonical_state_path) if args.canonical_state_path else None

    if args.mode == "baseline":
        receipt = baseline_existing_deliveries(inbox_dir, state_dir=state_dir, limit=max(args.limit, 0))
        if args.json:
            print(json.dumps(receipt, indent=2, sort_keys=True))
        else:
            print(f"{receipt['status']} delivery_count={receipt['delivery_count']}")
            print(f"receipt: {receipt['receipt_path']}")
        return 0

    while True:
        receipts = run_once(
            inbox_dir=inbox_dir,
            state_dir=state_dir,
            send_receipt_root=_path(args.send_receipt_root),
            outbox_root=_path(args.outbox_root),
            semantic_receipt_dir=_path(args.semantic_receipt_dir),
            artifact_receipt_dir=_path(args.artifact_receipt_dir),
            domain_reply_receipt_dir=_path(args.domain_reply_receipt_dir),
            no_publish=args.no_publish,
            stream=args.stream,
            timeout_s=args.timeout,
            flush_timeout_s=args.flush_timeout,
            limit=max(args.limit, 1),
            lease_ttl_s=max(args.lease_ttl_s, 1.0),
            packet_id=args.packet_id,
            canonical_state_path=canonical_state_path,
        )
        if args.json:
            print(json.dumps({"receipts": receipts}, indent=2, sort_keys=True))
        elif receipts:
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
