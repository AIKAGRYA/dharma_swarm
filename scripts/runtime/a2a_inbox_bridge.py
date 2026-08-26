#!/usr/bin/env python3
"""Drain a spec-canonical A2A agent inbox durable into a filesystem dock.

This bridge is a delivery handler, not a semantic agent. It may prove that an
envelope reached a target dock and that the bridge published the envelope
``ack_subject``. It must not claim that the target model read or answered the
message without a separate reply/domain receipt.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.runtime.a2a_send import (  # noqa: E402
    ACK_TIER_HANDLER_ACKED,
    ROUTE_AGENT_INBOX,
)
from scripts.runtime.a2a_topology import (  # noqa: E402
    DEFAULT_COMPATIBILITY_STREAM,
    DLQ_SUBJECT_TEMPLATE,
)
from scripts.runtime.pr_merge_control import stamp, utc_now  # noqa: E402
from dharma_swarm.a2a.agent_card import a2a_inbox_subject, resolve_agent_uid  # noqa: E402
from dharma_swarm.daemon_config import runtime_report_dir  # noqa: E402

DEFAULT_A2A_BUS = Path.home() / ".dharma" / "a2a_bus"
DEFAULT_RECEIPT_DIR = runtime_report_dir("a2a", "inbox_bridge_receipts")
DEFAULT_HEARTBEAT_DIR = DEFAULT_A2A_BUS / "bridge_heartbeats"

STATUS_NO_MESSAGES = "NO_MESSAGES"
STATUS_DELIVERED_AND_ACKED = "DELIVERED_AND_ACKED"
STATUS_DELIVERY_FAILED = "DELIVERY_FAILED"
STATUS_DEAD_LETTERED = "DEAD_LETTERED"
STATUS_DLQ_PUBLISH_FAILED = "DLQ_PUBLISH_FAILED"
STATUS_NATS_CLIENT_MISSING = "NATS_CLIENT_MISSING"

NATS_ENVELOPE_SCHEMA = "dharma.nats.envelope.v1"
DLQ_PAYLOAD_SCHEMA = "dharma.nats.dlq_failure.v1"


class MalformedEnvelope(ValueError):
    """The source bytes cannot become a valid durable semantic job."""


class IdempotencyCollision(ValueError):
    """An event id was reused with different source bytes."""


class NatsMessageLike(Protocol):
    subject: str
    data: bytes

    async def ack(self) -> Any:
        ...

    async def nak(self) -> Any:
        ...


class PublisherLike(Protocol):
    async def publish(
        self,
        subject: str,
        payload: bytes,
        *,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        ...


@dataclass(frozen=True)
class InboxBridgeConfig:
    agent_uid: str
    subject: str
    stream: str
    consumer: str
    inbox_dir: Path
    receipt_dir: Path
    job_db: Path
    endpoint: str = "nats://127.0.0.1:4222"
    flush_timeout_s: float = 2.0
    max_deliveries: int = 3


def subject_for_agent(agent_uid: str) -> str:
    return a2a_inbox_subject(resolve_agent_uid(agent_uid))


def default_inbox_dir(agent_uid: str) -> Path:
    return DEFAULT_A2A_BUS / "inboxes" / resolve_agent_uid(agent_uid)


def default_heartbeat_file(agent_uid: str) -> Path:
    return DEFAULT_HEARTBEAT_DIR / f"{resolve_agent_uid(agent_uid)}.json"


def default_job_db(agent_uid: str) -> Path:
    return DEFAULT_A2A_BUS / "semantic_jobs" / f"{resolve_agent_uid(agent_uid)}.sqlite3"


def _safe_token(value: object, *, fallback: str) -> str:
    raw = str(value or fallback)
    chars = [char if char.isalnum() or char in ("_", "-") else "_" for char in raw]
    cleaned = "".join(chars).strip("_-")
    return cleaned[:96] or fallback


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True).encode("utf-8")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{stamp()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _job_connection(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30.0)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_jobs (
            event_id TEXT PRIMARY KEY,
            envelope_sha256 TEXT NOT NULL,
            envelope_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    return connection


def commit_semantic_job(
    job_db: Path,
    *,
    event_id: str,
    envelope_sha256: str,
    envelope: dict[str, Any],
) -> bool:
    """Commit a recoverable semantic job before the source message is acked."""

    now = utc_now()
    with _job_connection(job_db) as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO semantic_jobs (
                event_id, envelope_sha256, envelope_json, status, created_at, updated_at
            ) VALUES (?, ?, ?, 'PENDING', ?, ?)
            """,
            (event_id, envelope_sha256, json.dumps(envelope, sort_keys=True), now, now),
        )
        if cursor.rowcount != 1:
            row = connection.execute(
                "SELECT envelope_sha256 FROM semantic_jobs WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if row is None or str(row[0]) != envelope_sha256:
                raise IdempotencyCollision(
                    f"event_id {event_id!r} already identifies a different envelope"
                )
    return cursor.rowcount == 1


def load_committed_job(job_db: Path, event_id: str) -> dict[str, Any] | None:
    if not job_db.exists():
        return None
    with _job_connection(job_db) as connection:
        row = connection.execute(
            """
            SELECT event_id, envelope_sha256, envelope_json, status, created_at, updated_at
            FROM semantic_jobs WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "event_id": row[0],
        "envelope_sha256": row[1],
        "envelope": json.loads(row[2]),
        "status": row[3],
        "created_at": row[4],
        "updated_at": row[5],
    }


def count_committed_jobs(job_db: Path) -> int:
    if not job_db.exists():
        return 0
    with _job_connection(job_db) as connection:
        row = connection.execute("SELECT COUNT(*) FROM semantic_jobs").fetchone()
    return int(row[0]) if row is not None else 0


def write_receipt(receipt_dir: Path, receipt: dict[str, Any]) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    packet_id = _safe_token(receipt.get("packet_id"), fallback="unknown")
    path = receipt_dir / f"{stamp()}-{receipt['agent_uid']}-{packet_id}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_heartbeat(path: Path, config: InboxBridgeConfig, payload: dict[str, Any]) -> None:
    body = {
        "schema_version": "dharma.a2a.inbox_bridge_heartbeat.v1",
        "timestamp": utc_now(),
        "agent_uid": config.agent_uid,
        "subject": config.subject,
        "stream": config.stream,
        "consumer": config.consumer,
        **payload,
    }
    _write_json_atomic(path, body)


def _parse_envelope(message: NatsMessageLike) -> dict[str, Any]:
    try:
        payload = json.loads(message.data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MalformedEnvelope(f"A2A inbox payload is not valid UTF-8 JSON: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise MalformedEnvelope("A2A inbox payload must be a JSON object")
    if not isinstance(payload.get("packet_id"), str) or not payload["packet_id"].strip():
        raise MalformedEnvelope("A2A inbox payload is missing packet_id")
    if not isinstance(payload.get("ack_subject"), str) or not payload["ack_subject"]:
        raise MalformedEnvelope("A2A inbox payload is missing ack_subject")
    return payload


def _delivery_path(config: InboxBridgeConfig, payload: dict[str, Any]) -> Path:
    packet_id = _safe_token(payload.get("packet_id"), fallback="unknown")
    return config.inbox_dir / f"{packet_id}.json"


def _base_receipt(config: InboxBridgeConfig, message: NatsMessageLike) -> dict[str, Any]:
    return {
        "schema_version": "dharma.a2a.inbox_bridge_receipt.v1",
        "timestamp": utc_now(),
        "agent_uid": config.agent_uid,
        "route": ROUTE_AGENT_INBOX,
        "subject": config.subject,
        "message_subject": str(message.subject),
        "stream": config.stream,
        "consumer": config.consumer,
        "endpoint": config.endpoint,
        "bridge_kind": "filesystem_delivery_handler",
        "semantic_reply_claim": False,
        "peer_model_processed_claim": False,
    }


def _subject_token(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in ("_", "-") else "_" for char in value.lower())
    return cleaned.strip("_-") or "unknown"


def _delivery_count(message: NatsMessageLike) -> int:
    metadata = getattr(message, "metadata", None)
    if callable(metadata):
        metadata = metadata()
    for value in (getattr(metadata, "num_delivered", None), getattr(message, "delivery_count", None)):
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count > 0:
            return count
    return 1


def _pub_ack_payload(pub_ack: Any) -> dict[str, Any]:
    stream = str(getattr(pub_ack, "stream", "") or "")
    seq = getattr(pub_ack, "seq", None)
    if not stream or not isinstance(seq, int):
        raise RuntimeError("JetStream publish did not return a durable puback")
    return {"transport_ack": "JETSTREAM_PUB_ACK", "stream": stream, "seq": seq}


def _dlq_subject(config: InboxBridgeConfig) -> str:
    return DLQ_SUBJECT_TEMPLATE.format(
        stream=_subject_token(config.stream),
        consumer=_subject_token(config.consumer),
    )


async def _dead_letter(
    message: NatsMessageLike,
    *,
    publisher: PublisherLike,
    config: InboxBridgeConfig,
    failure_kind: str,
    error: Exception,
    durable_job_committed: bool = False,
) -> dict[str, Any]:
    original_sha = hashlib.sha256(message.data).hexdigest()
    subject = _dlq_subject(config)
    message_id = "dlq_" + hashlib.sha256(
        f"{subject}|{original_sha}|{failure_kind}".encode("utf-8")
    ).hexdigest()[:32]
    now = utc_now()
    payload = {
        "schema": NATS_ENVELOPE_SCHEMA,
        "message_id": message_id,
        "correlation_id": original_sha,
        "causation_id": original_sha,
        "subject": subject,
        "from_agent": config.agent_uid,
        "to_agent": "operator",
        "kind": "event",
        "created_at": now,
        "requires_ack": False,
        "payload": {
            "schema": DLQ_PAYLOAD_SCHEMA,
            "created_at": now,
            "failure_kind": failure_kind,
            "original_subject": str(message.subject),
            "original_payload_sha256": original_sha,
            "delivery_count": _delivery_count(message),
            "max_deliveries": config.max_deliveries,
            "error_type": type(error).__name__,
            "error": str(error),
            "operator_blocker": "A2A_DELIVERY_DEAD_LETTERED",
        },
    }
    pub_ack = await publisher.publish(
        subject,
        _json_bytes(payload),
        headers={"Nats-Msg-Id": message_id},
        timeout=config.flush_timeout_s,
    )
    transport_ack = _pub_ack_payload(pub_ack)
    await message.ack()
    receipt = _base_receipt(config, message)
    receipt.update(
        {
            "status": STATUS_DEAD_LETTERED,
            "failure_kind": failure_kind,
            "error": f"{type(error).__name__}: {error}",
            "broker_ack": True,
            "broker_nak": False,
            "envelope_ack_published": False,
            "dlq_subject": subject,
            "dlq_message_id": message_id,
            "dlq_transport_ack": transport_ack,
            "durable_job_committed": durable_job_committed,
            "contact_evidence_tier": "NO_CONTACT",
            "collaboration_claim": "none",
        }
    )
    return receipt


async def process_message(
    message: NatsMessageLike,
    *,
    publisher: PublisherLike,
    config: InboxBridgeConfig,
) -> dict[str, Any]:
    """Persist one inbox envelope, publish its ack, then broker-ack it."""

    receipt = _base_receipt(config, message)
    durable_job_committed = False
    try:
        payload = _parse_envelope(message)
        packet_id = str(payload.get("packet_id") or "")
        ack_subject = str(payload["ack_subject"])
        envelope_sha = hashlib.sha256(message.data).hexdigest()
        delivery_path = _delivery_path(config, payload)
        delivery_record = {
            "schema_version": "dharma.a2a.inbox_delivery.v1",
            "delivered_at": utc_now(),
            "agent_uid": config.agent_uid,
            "bridge_kind": "filesystem_delivery_handler",
            "source_subject": message.subject,
            "stream": config.stream,
            "consumer": config.consumer,
            "envelope_sha256": envelope_sha,
            "envelope": payload,
            "semantic_reply_claim": False,
            "peer_model_processed_claim": False,
        }
        job_inserted = commit_semantic_job(
            config.job_db,
            event_id=packet_id,
            envelope_sha256=envelope_sha,
            envelope=payload,
        )
        durable_job_committed = True
        _write_json_atomic(delivery_path, delivery_record)

        ack_payload = {
            "schema_version": "dharma.a2a.inbox_bridge_ack.v1",
            "timestamp": utc_now(),
            "agent_uid": config.agent_uid,
            "packet_id": packet_id,
            "subject": config.subject,
            "delivered_to": str(delivery_path),
            "envelope_sha256": envelope_sha,
            "ack_tier": ACK_TIER_HANDLER_ACKED,
            "bridge_kind": "filesystem_delivery_handler",
            "semantic_reply_claim": False,
            "peer_model_processed_claim": False,
        }
        ack_message_id = "handler_ack_" + hashlib.sha256(
            f"{ack_subject}|{envelope_sha}".encode("utf-8")
        ).hexdigest()[:32]
        pub_ack = await publisher.publish(
            ack_subject,
            _json_bytes(ack_payload),
            headers={"Nats-Msg-Id": ack_message_id},
            timeout=config.flush_timeout_s,
        )
        ack_transport_ack = _pub_ack_payload(pub_ack)
        await message.ack()
        receipt.update(
            {
                "status": STATUS_DELIVERED_AND_ACKED,
                "packet_id": packet_id,
                "ack_subject": ack_subject,
                "delivery_path": str(delivery_path),
                "envelope_sha256": envelope_sha,
                "contact_evidence_tier": ACK_TIER_HANDLER_ACKED,
                "collaboration_claim": "filesystem_delivery_handler_ack",
                "broker_ack": True,
                "envelope_ack_published": True,
                "envelope_ack_message_id": ack_message_id,
                "envelope_ack_transport_ack": ack_transport_ack,
                "durable_job_committed": True,
                "semantic_job_status": "PENDING",
                "semantic_job_db": str(config.job_db),
                "duplicate": not job_inserted,
                "operator_contact_note": (
                    "delivery handler persisted the envelope and published its "
                    "ack_subject; no semantic peer reply is claimed"
                ),
            }
        )
    except (MalformedEnvelope, IdempotencyCollision) as exc:
        failure_kind = (
            "MALFORMED_ENVELOPE"
            if isinstance(exc, MalformedEnvelope)
            else "IDEMPOTENCY_COLLISION"
        )
        try:
            receipt = await _dead_letter(
                message,
                publisher=publisher,
                config=config,
                failure_kind=failure_kind,
                error=exc,
                durable_job_committed=durable_job_committed,
            )
        except Exception as dlq_exc:
            try:
                await message.nak()
                broker_nak = True
            except Exception:
                broker_nak = False
            receipt.update(
                {
                    "status": STATUS_DLQ_PUBLISH_FAILED,
                    "error": f"{type(exc).__name__}: {exc}",
                    "dlq_error": f"{type(dlq_exc).__name__}: {dlq_exc}",
                    "broker_ack": False,
                    "broker_nak": broker_nak,
                    "envelope_ack_published": False,
                    "contact_evidence_tier": "NO_CONTACT",
                    "collaboration_claim": "none",
                }
            )
    except Exception as exc:
        if _delivery_count(message) >= config.max_deliveries:
            try:
                receipt = await _dead_letter(
                    message,
                    publisher=publisher,
                    config=config,
                    failure_kind="MAX_DELIVER_EXHAUSTED",
                    error=exc,
                    durable_job_committed=durable_job_committed,
                )
            except Exception as dlq_exc:
                try:
                    await message.nak()
                    broker_nak = True
                except Exception:
                    broker_nak = False
                receipt.update(
                    {
                        "status": STATUS_DLQ_PUBLISH_FAILED,
                        "error": f"{type(exc).__name__}: {exc}",
                        "dlq_error": f"{type(dlq_exc).__name__}: {dlq_exc}",
                        "broker_ack": False,
                        "broker_nak": broker_nak,
                        "envelope_ack_published": False,
                        "durable_job_committed": durable_job_committed,
                        "contact_evidence_tier": "NO_CONTACT",
                        "collaboration_claim": "none",
                    }
                )
        else:
            try:
                await message.nak()
                broker_nak = True
            except Exception as nak_exc:  # pragma: no cover - defensive receipt detail
                broker_nak = False
                receipt["broker_nak_error"] = f"{type(nak_exc).__name__}: {nak_exc}"
            receipt.update(
                {
                    "status": STATUS_DELIVERY_FAILED,
                    "error": f"{type(exc).__name__}: {exc}",
                    "broker_ack": False,
                    "broker_nak": broker_nak,
                    "envelope_ack_published": False,
                    "durable_job_committed": durable_job_committed,
                    "contact_evidence_tier": "NO_CONTACT",
                    "collaboration_claim": "none",
                }
            )
    receipt_path = write_receipt(config.receipt_dir, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def write_no_messages_receipt(config: InboxBridgeConfig) -> dict[str, Any]:
    receipt = {
        "schema_version": "dharma.a2a.inbox_bridge_receipt.v1",
        "timestamp": utc_now(),
        "status": STATUS_NO_MESSAGES,
        "agent_uid": config.agent_uid,
        "route": ROUTE_AGENT_INBOX,
        "subject": config.subject,
        "stream": config.stream,
        "consumer": config.consumer,
        "endpoint": config.endpoint,
        "contact_evidence_tier": "NO_CONTACT",
        "collaboration_claim": "none",
    }
    receipt_path = write_receipt(config.receipt_dir, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return receipt


async def run_bridge_once(
    config: InboxBridgeConfig,
    *,
    max_messages: int = 1,
    fetch_timeout_s: float = 2.0,
    write_no_message_receipt: bool = True,
) -> list[dict[str, Any]]:
    try:
        import nats
        from nats.errors import TimeoutError as NatsTimeoutError
    except ModuleNotFoundError as exc:
        if getattr(exc, "name", "") == "nats":
            receipt = {
                "schema_version": "dharma.a2a.inbox_bridge_receipt.v1",
                "timestamp": utc_now(),
                "status": STATUS_NATS_CLIENT_MISSING,
                "agent_uid": config.agent_uid,
                "route": ROUTE_AGENT_INBOX,
                "subject": config.subject,
                "stream": config.stream,
                "consumer": config.consumer,
                "endpoint": config.endpoint,
                "contact_evidence_tier": "NO_CONTACT",
                "collaboration_claim": "none",
                "error": "nats-py is not installed in this Python environment",
            }
            receipt_path = write_receipt(config.receipt_dir, receipt)
            receipt["receipt_path"] = str(receipt_path)
            return [receipt]
        raise

    nc = await nats.connect(
        servers=[config.endpoint],
        allow_reconnect=False,
        max_reconnect_attempts=0,
    )
    try:
        js = nc.jetstream()
        sub = await js.pull_subscribe(
            config.subject,
            durable=config.consumer,
            stream=config.stream,
        )
        try:
            messages = await sub.fetch(max_messages, timeout=fetch_timeout_s)
        except NatsTimeoutError:
            messages = []
        if not messages:
            return [write_no_messages_receipt(config)] if write_no_message_receipt else []
        receipts = []
        for message in messages:
            receipts.append(await process_message(message, publisher=js, config=config))
        return receipts
    finally:
        await nc.close()


async def run_bridge_loop(
    config: InboxBridgeConfig,
    *,
    max_messages: int = 10,
    fetch_timeout_s: float = 30.0,
    poll_interval_s: float = 1.0,
    max_cycles: int = 0,
    heartbeat_file: Path | None = None,
    suppress_no_messages: bool = True,
) -> list[dict[str, Any]]:
    latest: list[dict[str, Any]] = []
    cycle = 0
    while max_cycles <= 0 or cycle < max_cycles:
        cycle += 1
        latest = await run_bridge_once(
            config,
            max_messages=max_messages,
            fetch_timeout_s=fetch_timeout_s,
            write_no_message_receipt=not suppress_no_messages,
        )
        if heartbeat_file is not None:
            write_heartbeat(
                heartbeat_file,
                config,
                {
                    "status": latest[-1]["status"] if latest else "IDLE",
                    "cycle": cycle,
                    "last_receipt_path": latest[-1].get("receipt_path", "") if latest else "",
                    "receipt_count": len(latest),
                    "suppress_no_messages": suppress_no_messages,
                },
            )
        for receipt in latest:
            print(
                f"{receipt['status']} agent_uid={receipt['agent_uid']} "
                f"subject={receipt['subject']}",
                flush=True,
            )
            print(f"receipt: {receipt['receipt_path']}", flush=True)
        await asyncio.sleep(max(poll_interval_s, 0.1))
    return latest


def _build_config(args: argparse.Namespace) -> InboxBridgeConfig:
    agent_uid = resolve_agent_uid(args.agent_uid)
    subject = args.subject or subject_for_agent(agent_uid)
    inbox_dir = Path(args.inbox_dir) if args.inbox_dir else default_inbox_dir(agent_uid)
    return InboxBridgeConfig(
        agent_uid=agent_uid,
        subject=subject,
        stream=args.stream,
        consumer=args.consumer,
        inbox_dir=inbox_dir,
        receipt_dir=Path(args.receipt_dir),
        job_db=(Path(args.job_db) if args.job_db else default_job_db(agent_uid)),
        endpoint=args.endpoint,
        flush_timeout_s=args.flush_timeout,
        max_deliveries=max(args.max_deliveries, 1),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent-uid", required=True, help="stable target agent UID")
    parser.add_argument("--consumer", required=True, help="durable pull consumer name")
    parser.add_argument("--subject", default="", help="override inbox subject")
    parser.add_argument("--stream", default=DEFAULT_COMPATIBILITY_STREAM)
    parser.add_argument("--endpoint", default="nats://127.0.0.1:4222")
    parser.add_argument("--inbox-dir", default="")
    parser.add_argument("--receipt-dir", default=str(DEFAULT_RECEIPT_DIR))
    parser.add_argument("--job-db", default="", help="durable semantic job SQLite database")
    parser.add_argument("--max-messages", type=int, default=1)
    parser.add_argument("--fetch-timeout", type=float, default=2.0)
    parser.add_argument("--flush-timeout", type=float, default=2.0)
    parser.add_argument("--max-deliveries", type=int, default=3)
    parser.add_argument("--loop", action="store_true", help="keep polling until interrupted")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--suppress-no-messages", action="store_true")
    parser.add_argument("--heartbeat-file", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        config = _build_config(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    heartbeat_file = (
        Path(args.heartbeat_file)
        if args.heartbeat_file
        else default_heartbeat_file(config.agent_uid)
    )

    try:
        if args.loop:
            receipts = asyncio.run(
                run_bridge_loop(
                    config,
                    max_messages=max(args.max_messages, 1),
                    fetch_timeout_s=max(args.fetch_timeout, 0.1),
                    poll_interval_s=max(args.poll_interval, 0.1),
                    max_cycles=max(args.max_cycles, 0),
                    heartbeat_file=heartbeat_file,
                    suppress_no_messages=args.suppress_no_messages,
                )
            )
        else:
            receipts = asyncio.run(
                run_bridge_once(
                    config,
                    max_messages=max(args.max_messages, 1),
                    fetch_timeout_s=max(args.fetch_timeout, 0.1),
                    write_no_message_receipt=not args.suppress_no_messages,
                )
            )
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("STOPPED", file=sys.stderr)
        return 130

    if args.json:
        print(json.dumps(receipts, indent=2, sort_keys=True))
    else:
        for receipt in receipts:
            print(
                f"{receipt['status']} agent_uid={receipt['agent_uid']} "
                f"subject={receipt['subject']}"
            )
            print(f"receipt: {receipt['receipt_path']}")

    if any(receipt.get("status") == STATUS_DELIVERY_FAILED for receipt in receipts):
        return 1
    if any(receipt.get("status") == STATUS_NATS_CLIENT_MISSING for receipt in receipts):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
