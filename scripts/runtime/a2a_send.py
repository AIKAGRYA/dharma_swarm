#!/usr/bin/env python3
"""Operator surface for sending one A2A packet to an agent over NATS.

Usage:
    python3 scripts/runtime/a2a_send.py --to devin --file inter_agent/devin/inbound/packet.md
    python3 scripts/runtime/a2a_send.py --to devin --file packet.md --wait 30 --json
    python3 scripts/runtime/a2a_send.py --to hermes-m5 --route agent-inbox --file packet.md

Publishes the file as a ``dharma.a2a.send.v1`` envelope to ``dharma.a2a.<agent>``,
writes an ack receipt under ``reports/a2a/send_receipts/``, and reports a single
terminal status:

    NATS_SECRETS_MISSING  no usable NATS credentials in the environment
    NATS_CLIENT_MISSING   nats-py is not installed in the active Python env
    PUBLISH_FAILED        connected/attempted but the publish did not complete
    PUBLISH_ACKED         broker accepted the packet (JetStream pub-ack)
    <AGENT>_CONSUMED      a consumer acked on the envelope ack_subject
    <AGENT>_REPLIED       a reply arrived on the envelope reply_subject

Consumers signal consumption/reply by publishing any payload to the ack/reply
subjects named in the envelope.

This is a compatibility/operator contact surface. It is not the canonical
Runtime Truth NATS task path, cannot publish to ``DS_TASKS`` on behalf of
``A2ANatsTransport.publish_task``, and its receipts cannot satisfy production
readiness gates for ``runtime-truth-nats-2026-06``.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.runtime.pr_merge_control import (  # noqa: E402
    NATSConfig,
    _a2a_target_for_subject,
    _nats_config,
    _nats_tls_kwargs,
    _is_publish_permission_violation,
    _redacted_nats_config,
    stamp,
    utc_now,
)
from dharma_swarm.a2a.agent_card import (  # noqa: E402
    A2A_INBOX_ROUTE_ALIAS,
    a2a_inbox_subject,
    resolve_agent_uid,
)
from dharma_swarm.operator_core.runtime_truth import runtime_db_path_from_env, stable_payload_hash  # noqa: E402
from dharma_swarm.runtime_state import RuntimeReceipt, RuntimeStateStore  # noqa: E402
from dharma_swarm.spine.identity import ExecutionIdentity  # noqa: E402
from dharma_swarm.spine.receipt import EvidenceReceipt  # noqa: E402
from dharma_swarm.spine.warrant import RuntimeWarrantDenied, issue_runtime_warrant  # noqa: E402

DEFAULT_RECEIPT_DIR = REPO_ROOT / "reports" / "a2a" / "send_receipts"

STATUS_SECRETS_MISSING = "NATS_SECRETS_MISSING"
STATUS_NATS_CLIENT_MISSING = "NATS_CLIENT_MISSING"
STATUS_PUBLISH_FAILED = "PUBLISH_FAILED"
STATUS_PERMISSIONS_DENIED = "NATS_PERMISSIONS_DENIED"
STATUS_PUBLISH_ACKED = "PUBLISH_ACKED"
STATUS_PUBLISH_DEDUPED = "PUBLISH_DEDUPED"
ACK_TIER_NO_CONTACT = "NO_CONTACT"
ACK_TIER_PUBLISH_ACCEPTED = "PUBLISH_ACCEPTED"
ACK_TIER_CORE_FLUSH_ONLY = "CORE_FLUSH_ONLY"
ACK_TIER_HANDLER_ACKED = "HANDLER_ACKED"
ROUTE_A2A = "a2a"
ROUTE_AGENT_INBOX = A2A_INBOX_ROUTE_ALIAS
CANONICAL_RUNTIME_TRUTH_NATS_TASK_PATH = False
COMPATIBILITY_NATS_BYPASS_CLASS = (
    "operator_contact_compatibility_only;"
    " cannot_satisfy_runtime_truth_nats_production_gate"
)


def _validate_subject_token(token: str, *, label: str) -> str:
    return resolve_agent_uid(token) if label == "agent uid" else _validate_a2a_token(token, label=label)


def _validate_a2a_token(token: str, *, label: str) -> str:
    cleaned = (token or "").strip()
    forbidden = {".", "*", ">", "/", "\\"}
    if not cleaned or any(char.isspace() or char in forbidden for char in cleaned):
        raise ValueError(f"invalid {label} for NATS subject: {cleaned!r}")
    return cleaned


def subject_for_route(to: str, *, route: str, agent_uid: str = "") -> tuple[str, str]:
    if route == ROUTE_A2A:
        recipient = _validate_subject_token(to, label="a2a recipient")
        subject = f"dharma.a2a.{recipient}"
        return subject, _a2a_target_for_subject(subject)
    if route == ROUTE_AGENT_INBOX:
        resolved_uid = resolve_agent_uid(to, agent_uid=agent_uid)
        return a2a_inbox_subject(resolved_uid), resolved_uid
    raise ValueError(f"unsupported A2A send route: {route}")


def _status_agent_label(envelope: dict[str, Any]) -> str:
    if envelope.get("route") == ROUTE_AGENT_INBOX:
        raw = str(envelope.get("target_uid") or envelope.get("to") or "agent")
    else:
        raw = str(envelope.get("subject") or "agent").rsplit(".", 1)[-1]
    chars = [char.upper() if char.isalnum() else "_" for char in raw]
    return "".join(chars).strip("_") or "AGENT"


def _permissions_denied_message(config: NATSConfig, subject: str) -> str:
    user = config.user or "current"
    return (
        f"broker rejected publish to {subject}: the {user} NATS credential is "
        "not authorized to publish to this lane (server-side ACL)"
    )


def _recorded_publish_permission_violation(message: str, subject: str) -> bool:
    return _is_publish_permission_violation(message, subject)


def build_envelope(
    *,
    to: str,
    file_path: Path,
    sender: str,
    kind: str,
    packet_id: str,
    route: str = ROUTE_A2A,
    agent_uid: str = "",
) -> dict[str, Any]:
    content = file_path.read_text(encoding="utf-8")
    subject, target_uid = subject_for_route(to, route=route, agent_uid=agent_uid)
    try:
        rel_path = str(file_path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        rel_path = str(file_path)
    return {
        "schema_version": "dharma.a2a.send.v1",
        "packet_id": packet_id,
        "timestamp": utc_now(),
        "from": sender,
        "to": target_uid,
        "kind": kind,
        "route": route,
        "target_uid": target_uid,
        "subject": subject,
        "ack_subject": f"{subject}.ack.{packet_id}",
        "reply_subject": f"{subject}.reply.{packet_id}",
        "file": rel_path,
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content": content,
    }


async def _publish_and_wait(
    config: NATSConfig,
    envelope: dict[str, Any],
    *,
    wait_s: float,
    timeout_s: float,
    insecure_tls: bool = False,
) -> dict[str, Any]:
    import nats

    result: dict[str, Any] = {
        "status": STATUS_PUBLISH_FAILED,
        "ack_tier": None,
        "consumed": False,
        "replied": False,
        "reply_payload": None,
        "permissions_denied_detail": None,
    }
    tls_kwargs = _nats_tls_kwargs(config)
    if insecure_tls and not config.ca_pem:
        insecure_ctx = ssl.create_default_context()
        insecure_ctx.check_hostname = False
        insecure_ctx.verify_mode = ssl.CERT_NONE
        tls_kwargs["tls"] = insecure_ctx
    permission_violation = asyncio.Event()

    async def _quiet_error_cb(exc: Exception) -> None:
        message = str(exc)
        if _recorded_publish_permission_violation(message, envelope["subject"]):
            result["permissions_denied_detail"] = _permissions_denied_message(
                config, envelope["subject"]
            )
            permission_violation.set()
        result["last_connection_error"] = type(exc).__name__

    nc = await nats.connect(
        servers=[str(config.endpoint)],
        user=config.user or None,
        password=config.credential or None,
        connect_timeout=timeout_s,
        allow_reconnect=False,
        max_reconnect_attempts=0,
        error_cb=_quiet_error_cb,
        **tls_kwargs,
    )
    try:
        consumed_event: asyncio.Event = asyncio.Event()
        replied_event: asyncio.Event = asyncio.Event()

        async def _safe_unsubscribe(subscription: Any) -> None:
            try:
                await subscription.unsubscribe()
            except Exception as exc:
                result.setdefault("cleanup_errors", []).append(
                    f"unsubscribe:{type(exc).__name__}"
                )

        async def on_ack(msg: Any) -> None:
            consumed_event.set()

        async def on_reply(msg: Any) -> None:
            try:
                result["reply_payload"] = json.loads(msg.data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                result["reply_payload"] = {"raw": msg.data.decode("utf-8", "replace")}
            replied_event.set()

        ack_sub = await nc.subscribe(envelope["ack_subject"], cb=on_ack)
        reply_sub = await nc.subscribe(envelope["reply_subject"], cb=on_reply)

        data = json.dumps(envelope, sort_keys=True).encode("utf-8")
        try:
            js_ack = await nc.jetstream().publish(
                envelope["subject"], data, timeout=timeout_s
            )
            result["ack_tier"] = ACK_TIER_PUBLISH_ACCEPTED
            result["transport_ack"] = "JETSTREAM_PUB_ACK"
            result["stream"] = js_ack.stream
            result["seq"] = js_ack.seq
        except Exception as exc:
            result["status"] = STATUS_PUBLISH_FAILED
            result["ack_tier"] = None
            result["transport_ack"] = "JETSTREAM_PUB_ACK_AMBIGUOUS"
            result["error"] = type(exc).__name__
            if result["permissions_denied_detail"] is None:
                try:
                    await asyncio.wait_for(permission_violation.wait(), timeout=0.5)
                except Exception as wait_exc:
                    result["permission_wait_guard_error"] = type(wait_exc).__name__
            if result["permissions_denied_detail"] is None and _recorded_publish_permission_violation(str(exc), envelope["subject"]):
                result["permissions_denied_detail"] = _permissions_denied_message(
                    config, envelope["subject"]
                )
            if result["permissions_denied_detail"] is not None:
                result["status"] = STATUS_PERMISSIONS_DENIED
                result["error"] = result["permissions_denied_detail"]
            await _safe_unsubscribe(ack_sub)
            await _safe_unsubscribe(reply_sub)
            return result
        result["status"] = STATUS_PUBLISH_ACKED

        agent = _status_agent_label(envelope)
        deadline = asyncio.get_running_loop().time() + max(wait_s, 0.0)
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            waiters = [asyncio.create_task(replied_event.wait())]
            if not consumed_event.is_set():
                waiters.append(asyncio.create_task(consumed_event.wait()))
            done, pending = await asyncio.wait(
                waiters, timeout=remaining, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            if not done:
                break
            if replied_event.is_set():
                break
        if consumed_event.is_set():
            result["consumed"] = True
            result["ack_tier"] = ACK_TIER_HANDLER_ACKED
            result["status"] = f"{agent}_CONSUMED"
        if replied_event.is_set():
            result["replied"] = True
            result["consumed"] = True
            result["ack_tier"] = ACK_TIER_HANDLER_ACKED
            result["status"] = f"{agent}_REPLIED"
        await _safe_unsubscribe(ack_sub)
        await _safe_unsubscribe(reply_sub)
    finally:
        try:
            await asyncio.wait_for(nc.close(), timeout=2.0)
        except Exception as exc:
            result["close_guard_error"] = type(exc).__name__
    return result


def _nats_cli_env(config: NATSConfig) -> dict[str, str]:
    env = dict(os.environ)
    env["NATS_URL"] = str(config.endpoint)
    if config.user:
        env["NATS_USER"] = config.user
    if config.credential:
        env["NATS_PASSWORD"] = config.credential
    return env


def _nats_cli_command(config: NATSConfig, *, timeout_s: float, ca_path: Path | None) -> list[str]:
    cmd = [
        "nats",
        "--no-context",
        f"--timeout={max(timeout_s, 0.1):g}s",
    ]
    if ca_path is not None:
        cmd.append(f"--tlsca={ca_path}")
    cmd.extend(["publish", "--jetstream", "--force-stdin"])
    return cmd


def _publish_with_nats_cli(
    config: NATSConfig,
    envelope: dict[str, Any],
    *,
    timeout_s: float,
) -> dict[str, Any]:
    """Fallback publish path when nats-py is unavailable.

    This uses the existing NATS CLI, not a second bus. A successful JetStream
    publish can prove only broker acceptance. It cannot prove handler contact.
    """
    if shutil.which("nats") is None:
        raise ModuleNotFoundError("No module named 'nats'", name="nats")
    if config.tls_hostname:
        raise RuntimeError("nats CLI fallback does not support NATS TLS hostname override")

    data = json.dumps(envelope, sort_keys=True)
    ca_tmp: tempfile.NamedTemporaryFile[str] | None = None
    ca_path: Path | None = None
    try:
        if config.ca_pem:
            ca_tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
            ca_tmp.write(config.ca_pem)
            ca_tmp.flush()
            ca_tmp.close()
            ca_path = Path(ca_tmp.name)

        cmd = _nats_cli_command(config, timeout_s=timeout_s, ca_path=ca_path)
        proc = subprocess.run(
            [*cmd, envelope["subject"]],
            input=data,
            text=True,
            capture_output=True,
            timeout=max(timeout_s + 5.0, 5.0),
            check=False,
            env=_nats_cli_env(config),
        )
    finally:
        if ca_path is not None:
            try:
                ca_path.unlink()
            except OSError:
                pass

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(f"nats CLI publish failed with code {proc.returncode}: {detail}")

    return {
        "status": STATUS_PUBLISH_ACKED,
        "ack_tier": ACK_TIER_PUBLISH_ACCEPTED,
        "transport_ack": "NATS_CLI_JETSTREAM_PUB_ACK",
        "cli_fallback_used": True,
        "cli_stdout": proc.stdout.strip(),
        "consumed": False,
        "replied": False,
        "reply_payload": None,
    }


def write_receipt(receipt_dir: Path, receipt: dict[str, Any]) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{stamp()}-{receipt['to']}-{receipt['packet_id']}"
    path = receipt_dir / f"{stem}.json"
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    suffix = 1
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            path = receipt_dir / f"{stem}-{suffix}.json"
            suffix += 1
            continue
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        return path


def _runtime_db_path(value: str | None) -> Path:
    return Path(value).expanduser() if value else runtime_db_path_from_env()


def _runtime_identity_for_envelope(envelope: dict[str, Any], *, sender: str) -> ExecutionIdentity:
    packet_id = str(envelope.get("packet_id") or "")
    subject = str(envelope.get("subject") or "")
    target = str(envelope.get("target_uid") or envelope.get("to") or "")
    digest = stable_payload_hash(
        {
            "surface": "a2a_send",
            "packet_id": packet_id,
            "subject": subject,
            "target": target,
        }
    ).replace("sha256:", "", 1)
    task_id = f"a2a-send-{packet_id}"
    return ExecutionIdentity.new(
        task_id=task_id,
        trace_id=f"trace_a2a_send_{digest[:16]}",
        correlation_id=f"a2a_send:{target}:{packet_id}",
        run_id=f"run_a2a_send_{digest[:16]}",
        claim_id=f"claim_a2a_send_{digest[:16]}",
        idempotency_key=f"idem_a2a_send:{subject}:{packet_id}",
        agent_id=sender,
        session_id="a2a_send",
        message_id=packet_id,
        metadata={
            "surface": "scripts/runtime/a2a_send.py",
            "route": str(envelope.get("route") or ""),
            "subject": subject,
            "target_uid": target,
        },
    )


def _begin_runtime_publish(
    *,
    envelope: dict[str, Any],
    sender: str,
    runtime_db: Path,
    stale_after_seconds: float,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    identity = _runtime_identity_for_envelope(envelope, sender=sender)
    side_effect_key = f"a2a_send.publish:{envelope['subject']}:{envelope['packet_id']}"
    metadata = {
        **identity.to_metadata(),
        "surface": "scripts/runtime/a2a_send.py",
        "packet_id": str(envelope.get("packet_id") or ""),
        "route": str(envelope.get("route") or ""),
        "subject": str(envelope.get("subject") or ""),
        "target_uid": str(envelope.get("target_uid") or ""),
        "sha256": str(envelope.get("sha256") or ""),
        "operation_hash": stable_payload_hash(
            {
                "subject": envelope.get("subject"),
                "packet_id": envelope.get("packet_id"),
                "sha256": envelope.get("sha256"),
                "route": envelope.get("route"),
                "target_uid": envelope.get("target_uid"),
            }
        ),
    }
    store = RuntimeStateStore(runtime_db)
    store.record_execution_identity_sync(identity, source="a2a_send", metadata=metadata)
    inserted = store.try_begin_idempotent_side_effect_sync(
        identity,
        side_effect_key,
        metadata=metadata,
        stale_after_seconds=stale_after_seconds,
    )
    return {
        "store": store,
        "identity": identity,
        "side_effect_key": side_effect_key,
        "metadata": metadata,
        "idempotency_inserted": inserted,
        "runtime_db": str(runtime_db),
        "started_at": started_at,
    }


def _runtime_ref(dispatch: dict[str, Any]) -> dict[str, Any]:
    identity = dispatch["identity"]
    return {
        "runtime_db": dispatch["runtime_db"],
        "run_id": identity.run_id,
        "task_id": identity.task_id,
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "claim_id": identity.claim_id,
        "idempotency_key": identity.idempotency_key,
        "side_effect_key": dispatch["side_effect_key"],
        "idempotency_inserted": bool(dispatch["idempotency_inserted"]),
    }


def _evidence_receipt_ref(receipt: EvidenceReceipt) -> dict[str, Any]:
    return {
        "receipt_id": str(receipt.receipt_id),
        "trace_id": receipt.trace_id,
        "span_id": receipt.span_id,
        "task_id": receipt.task_id,
        "operation": receipt.operation,
        "status": receipt.status,
    }


def _evidence_status_for_publish(receipt: dict[str, Any]) -> tuple[str, str, str | None, bool]:
    status = str(receipt.get("status") or STATUS_PUBLISH_FAILED)
    error_detail = str(receipt.get("error") or "") or None
    if status == STATUS_PUBLISH_FAILED and error_detail and "RuntimeWarrantDenied" in error_detail:
        return "dropped", "guardrail_blocked", error_detail, False
    if status == STATUS_NATS_CLIENT_MISSING:
        return "failed", "provider_unreachable", error_detail, False
    if status in {STATUS_PUBLISH_FAILED, STATUS_PERMISSIONS_DENIED}:
        return "failed", "provider_failed", error_detail, True
    if status == STATUS_PUBLISH_DEDUPED:
        return "dropped", "guardrail_blocked", "duplicate publish skipped by idempotency", False
    return "ok", "none", None, True


def _build_publish_evidence_receipt(dispatch: dict[str, Any], receipt: dict[str, Any]) -> EvidenceReceipt:
    identity = dispatch["identity"]
    metadata = dict(dispatch["metadata"])
    finished_at = datetime.now(timezone.utc)
    started_at = dispatch.get("started_at")
    if not isinstance(started_at, datetime):
        started_at = finished_at
    evidence_status, error_source, error_detail, provider_attempted = _evidence_status_for_publish(receipt)
    warrant_ref = receipt.get("runtime_warrant_ref")
    warrant_ref = warrant_ref if isinstance(warrant_ref, dict) else {}
    attributes = {
        "correlation_id": identity.correlation_id,
        "idempotency_key": identity.idempotency_key,
        "side_effect_key": str(dispatch["side_effect_key"]),
        "runtime_warrant_receipt_id": str(warrant_ref.get("receipt_id") or ""),
        "a2a_send_receipt_status": str(receipt.get("status") or ""),
        "ack_tier": str(receipt.get("ack_tier") or ""),
        "contact_evidence_tier": str(receipt.get("contact_evidence_tier") or ""),
        "collaboration_claim": str(receipt.get("collaboration_claim") or ""),
        "packet_id": str(metadata.get("packet_id") or ""),
        "route": str(metadata.get("route") or ""),
        "subject": str(metadata.get("subject") or ""),
    }
    return EvidenceReceipt(
        trace_id=identity.trace_id,
        span_id=identity.run_id,
        parent_span_id=identity.parent_run_id or None,
        context_id=identity.session_id,
        task_id=identity.task_id,
        claim_id=identity.claim_id or None,
        agent_id=str(metadata.get("target_uid") or identity.agent_id),
        provider="nats",
        operation="a2a_send.publish",
        provider_attempted=provider_attempted,
        status=evidence_status,
        error_source=error_source,
        error_detail=error_detail,
        started_at=started_at,
        finished_at=finished_at,
        latency_ms=int((finished_at - started_at).total_seconds() * 1000),
        attributes=attributes,
    )


def _issue_runtime_warrant_for_publish(dispatch: dict[str, Any]) -> dict[str, Any]:
    warrant = issue_runtime_warrant(
        store=dispatch["store"],
        identity=dispatch["identity"],
        surface="scripts/runtime/a2a_send.py",
        action="publish",
        side_effect_key=str(dispatch["side_effect_key"]),
        idempotency_inserted=bool(dispatch["idempotency_inserted"]),
        requested_claims=("a2a_publish_attempt", "runtime_receipt_pending"),
        metadata={
            **dict(dispatch["metadata"]),
            "warrant_scope": "pre_publish_permission",
            "claim_boundary": "publish attempt only; handler/domain/semantic/completion require later receipts",
        },
    )
    return warrant.to_ref()


def _complete_runtime_publish(dispatch: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    store = dispatch["store"]
    identity = dispatch["identity"]
    side_effect_key = str(dispatch["side_effect_key"])
    status = str(receipt.get("status") or STATUS_PUBLISH_FAILED)
    final_state = (
        "completed"
        if status
        not in {
            STATUS_PUBLISH_FAILED,
            STATUS_NATS_CLIENT_MISSING,
            STATUS_PERMISSIONS_DENIED,
        }
        else "failed"
    )
    receipt_id = f"rr_{identity.run_id}_a2a_send_{status.lower()}"
    evidence_receipt = _build_publish_evidence_receipt(dispatch, receipt)
    evidence_ref = _evidence_receipt_ref(evidence_receipt)
    receipt["spine_evidence_receipt_ref"] = evidence_ref
    payload = {
        **dict(dispatch["metadata"]),
        "a2a_send_receipt_status": status,
        "ack_tier": receipt.get("ack_tier"),
        "contact_evidence_tier": receipt.get("contact_evidence_tier"),
        "live_contact_claim": bool(receipt.get("live_contact_claim")),
        "collaboration_claim": receipt.get("collaboration_claim"),
        "subject": receipt.get("subject"),
        "receipt_path": receipt.get("receipt_path"),
        "runtime_warrant_ref": receipt.get("runtime_warrant_ref"),
        "spine_evidence_receipt_ref": evidence_ref,
        "spine_evidence_receipt": evidence_receipt.to_dict(),
    }
    store.complete_idempotent_side_effect_sync(
        identity,
        side_effect_key,
        status=final_state,
        result_receipt_id=receipt_id,
        metadata=payload,
    )
    runtime_receipt = store.record_runtime_receipt_sync(
        RuntimeReceipt(
            receipt_id=receipt_id,
            receipt_type="a2a_send",
            status=status,
            run_id=identity.run_id,
            task_id=identity.task_id,
            trace_id=identity.trace_id,
            correlation_id=identity.correlation_id,
            causation_id=identity.causation_id,
            parent_run_id=identity.parent_run_id,
            agent_id=identity.agent_id,
            idempotency_key=identity.idempotency_key,
            side_effect_key=side_effect_key,
            payload=payload,
        )
    )
    return {
        **_runtime_ref(dispatch),
        "receipt_id": runtime_receipt.receipt_id,
        "spine_evidence_receipt_ref": evidence_ref,
    }


def _is_missing_nats_client(exc: Exception) -> bool:
    return isinstance(exc, ModuleNotFoundError) and getattr(exc, "name", "") == "nats"


def classify_contact_evidence(receipt: dict[str, Any]) -> dict[str, Any]:
    """Classify whether a send receipt proves live collaboration.

    The NATS substrate spec treats publish acceptance as weaker than hot contact.
    Hot contact requires a handler ack or domain receipt. This classifier keeps
    that distinction explicit in every receipt, including failure and fallback
    paths.
    """
    status = str(receipt.get("status") or "")
    ack_tier = receipt.get("ack_tier")
    if ack_tier == ACK_TIER_HANDLER_ACKED:
        return {
            "contact_evidence_tier": ACK_TIER_HANDLER_ACKED,
            "live_contact_claim": True,
            "collaboration_claim": "handler_ack",
            "operator_contact_note": (
                "target handler acked the packet subject; this is not by itself "
                "a semantic peer reply"
            ),
        }
    if ack_tier == ACK_TIER_PUBLISH_ACCEPTED:
        return {
            "contact_evidence_tier": ACK_TIER_PUBLISH_ACCEPTED,
            "live_contact_claim": False,
            "collaboration_claim": "publish_only",
            "operator_contact_note": "broker accepted the packet; this is not live collaboration by itself",
        }
    if ack_tier == ACK_TIER_CORE_FLUSH_ONLY:
        return {
            "contact_evidence_tier": ACK_TIER_CORE_FLUSH_ONLY,
            "live_contact_claim": False,
            "collaboration_claim": "transport_flush_only",
            "operator_contact_note": "core NATS flush completed without durable JetStream ack or handler ack",
        }
    if status == STATUS_PUBLISH_DEDUPED:
        return {
            "contact_evidence_tier": ACK_TIER_NO_CONTACT,
            "live_contact_claim": False,
            "collaboration_claim": "duplicate_publish_skipped",
            "operator_contact_note": "duplicate packet publish skipped by RuntimeStateStore idempotency",
        }
    if status in {
        STATUS_SECRETS_MISSING,
        STATUS_NATS_CLIENT_MISSING,
        STATUS_PUBLISH_FAILED,
        STATUS_PERMISSIONS_DENIED,
    }:
        return {
            "contact_evidence_tier": ACK_TIER_NO_CONTACT,
            "live_contact_claim": False,
            "collaboration_claim": "none",
            "operator_contact_note": "no live A2A collaboration proven",
        }
    return {
        "contact_evidence_tier": str(ack_tier or ACK_TIER_NO_CONTACT),
        "live_contact_claim": False,
        "collaboration_claim": "unknown",
        "operator_contact_note": "receipt status is not enough to claim collaboration",
    }


def console_receipt() -> dict[str, Any]:
    """Return an operator-facing receipt shape without persisted receipt fields."""
    return {
        "schema_version": "dharma.a2a.send_console.v1",
        "packet_id": "<redacted>",
        "status": "<recorded>",
        "subject": "<redacted>",
        "ack_subject": "<redacted>",
        "reply_subject": "<redacted>",
        "file": "<redacted>",
        "receipt_path": "<written>",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--to", required=True, help="agent lane, e.g. devin, codex, claude")
    parser.add_argument("--file", required=True, help="packet file to send")
    parser.add_argument("--from", dest="sender", default="operator", help="sender identity")
    parser.add_argument("--kind", default="fleet.packet", help="envelope kind")
    parser.add_argument(
        "--route",
        choices=[ROUTE_A2A, ROUTE_AGENT_INBOX],
        default=ROUTE_A2A,
        help="NATS subject route: dharma.a2a.<agent> compatibility or dharma.agent.<agent_uid>.inbox hot-contact path",
    )
    parser.add_argument(
        "--agent-uid",
        default="",
        help="stable agent uid for --route agent-inbox; defaults to --to with known aliases",
    )
    parser.add_argument("--wait", type=float, default=10.0, help="seconds to wait for consume/reply")
    parser.add_argument("--timeout", type=float, default=10.0, help="connect/publish timeout seconds")
    parser.add_argument("--receipt-dir", default=str(DEFAULT_RECEIPT_DIR))
    parser.add_argument(
        "--runtime-db",
        default="",
        help="RuntimeStateStore database for direct-publish idempotency; defaults to DHARMA_STATE_DIR/runtime.db or ~/.dharma/state/runtime.db",
    )
    parser.add_argument(
        "--packet-id",
        default="",
        help="explicit packet id for idempotent retries; defaults to a fresh random id",
    )
    parser.add_argument("--json", action="store_true", help="print the receipt JSON to stdout")
    parser.add_argument(
        "--insecure-tls",
        action="store_true",
        help="skip TLS verification (only until a NATS CA pem is distributed; "
        "ignored when a CA pem secret is present)",
    )
    args = parser.parse_args(argv)

    file_path = Path(args.file)
    if not file_path.is_file():
        print(f"ERROR: packet file not found: {file_path}", file=sys.stderr)
        return 2

    config = _nats_config(dict(os.environ), require_devin_secrets=False)
    packet_id = args.packet_id.strip() or uuid.uuid4().hex[:12]
    try:
        envelope = build_envelope(
            to=args.to,
            file_path=file_path,
            sender=args.sender,
            kind=args.kind,
            packet_id=packet_id,
            route=args.route,
            agent_uid=args.agent_uid,
        )
    except ValueError as exc:
        print(f"ERROR: {type(exc).__name__}", file=sys.stderr)
        return 2
    receipt: dict[str, Any] = {
        "schema_version": "dharma.a2a.send_receipt.v1",
        "packet_id": packet_id,
        "timestamp": utc_now(),
        "to": args.to,
        "route": envelope["route"],
        "target_uid": envelope["target_uid"],
        "subject": envelope["subject"],
        "ack_subject": envelope["ack_subject"],
        "reply_subject": envelope["reply_subject"],
        "file": envelope["file"],
        "sha256": envelope["sha256"],
        "nats": _redacted_nats_config(config),
        "production_contract": {
            "canonical_runtime_truth_nats_task_path": CANONICAL_RUNTIME_TRUTH_NATS_TASK_PATH,
            "compatibility_bypass_class": COMPATIBILITY_NATS_BYPASS_CLASS,
            "production_readiness_claim_allowed": False,
            "canonical_transport": "A2ANatsTransport.publish_task",
            "canonical_stream": "DS_TASKS",
        },
    }
    runtime_dispatch: dict[str, Any] | None = None
    if config.missing or not config.endpoint:
        receipt["status"] = STATUS_SECRETS_MISSING
        receipt["ack_tier"] = None
        receipt["missing"] = list(config.missing)
    else:
        runtime_dispatch = _begin_runtime_publish(
            envelope=envelope,
            sender=args.sender,
            runtime_db=_runtime_db_path(args.runtime_db),
            stale_after_seconds=max(args.timeout * 2 + args.wait + 5, 1.0),
        )
        receipt["runtime_truth_ref"] = _runtime_ref(runtime_dispatch)
        if not runtime_dispatch["idempotency_inserted"]:
            receipt["status"] = STATUS_PUBLISH_DEDUPED
            receipt["ack_tier"] = None
        else:
            try:
                receipt["runtime_warrant_ref"] = _issue_runtime_warrant_for_publish(runtime_dispatch)
            except RuntimeWarrantDenied as exc:
                receipt["status"] = STATUS_PUBLISH_FAILED
                receipt["ack_tier"] = None
                receipt["error"] = f"RuntimeWarrantDenied: {exc}"
                if exc.warrant is not None:
                    receipt["runtime_warrant_ref"] = exc.warrant.to_ref()
            else:
                try:
                    deadline_s = args.timeout * 2 + args.wait + 5
                    outcome = asyncio.run(
                        asyncio.wait_for(
                            _publish_and_wait(
                                config,
                                envelope,
                                wait_s=args.wait,
                                timeout_s=args.timeout,
                                insecure_tls=args.insecure_tls,
                            ),
                            timeout=deadline_s,
                        )
                    )
                    receipt.update(outcome)
                except Exception as exc:  # surface broker/TLS failures as a receipt, not a stack trace
                    if _is_missing_nats_client(exc):
                        try:
                            receipt.update(
                                _publish_with_nats_cli(
                                    config,
                                    envelope,
                                    timeout_s=args.timeout,
                                )
                            )
                        except Exception as fallback_exc:
                            if _is_missing_nats_client(fallback_exc):
                                receipt["status"] = STATUS_NATS_CLIENT_MISSING
                                receipt["ack_tier"] = None
                            else:
                                receipt["status"] = STATUS_PUBLISH_FAILED
                                receipt["ack_tier"] = None
                            receipt["error"] = type(fallback_exc).__name__
                            receipt["python_client_error"] = type(exc).__name__
                    else:
                        receipt["status"] = STATUS_PUBLISH_FAILED
                        receipt["ack_tier"] = None
                        receipt["error"] = type(exc).__name__

    receipt.update(classify_contact_evidence(receipt))
    receipt_path = write_receipt(Path(args.receipt_dir), receipt)
    receipt["receipt_path"] = str(receipt_path)
    if runtime_dispatch is not None and runtime_dispatch["idempotency_inserted"]:
        try:
            receipt["runtime_truth_ref"] = _complete_runtime_publish(runtime_dispatch, receipt)
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except Exception as exc:
            receipt["runtime_truth_error"] = type(exc).__name__
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(console_receipt(), indent=2, sort_keys=True))
    else:
        print("a2a_send: <recorded>")
        print("receipt: <written>")
    if receipt["status"] == STATUS_SECRETS_MISSING:
        return 3
    if receipt["status"] == STATUS_NATS_CLIENT_MISSING:
        return 4
    if receipt["status"] in {STATUS_PUBLISH_FAILED, STATUS_PERMISSIONS_DENIED}:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
