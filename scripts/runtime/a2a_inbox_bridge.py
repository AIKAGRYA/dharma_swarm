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
import os
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
    resolve_agent_uid,
)
from scripts.runtime.pr_merge_control import (  # noqa: E402
    NATSConfig,
    _nats_config,
    _nats_tls_kwargs,
    stamp,
    utc_now,
)

DEFAULT_A2A_BUS = Path.home() / ".dharma" / "a2a_bus"
DEFAULT_RECEIPT_DIR = REPO_ROOT / "reports" / "a2a" / "inbox_bridge_receipts"
DEFAULT_HEARTBEAT_DIR = DEFAULT_A2A_BUS / "bridge_heartbeats"

STATUS_NO_MESSAGES = "NO_MESSAGES"
STATUS_DELIVERED_AND_ACKED = "DELIVERED_AND_ACKED"
STATUS_DELIVERY_FAILED = "DELIVERY_FAILED"
STATUS_INVALID_ENVELOPE_ACKED = "INVALID_ENVELOPE_ACKED"
STATUS_NATS_CLIENT_MISSING = "NATS_CLIENT_MISSING"


class NatsMessageLike(Protocol):
    subject: str
    data: bytes

    async def ack(self) -> Any:
        ...

    async def nak(self) -> Any:
        ...


class PublisherLike(Protocol):
    async def publish(self, subject: str, payload: bytes) -> Any:
        ...

    async def flush(self, timeout: float | None = None) -> Any:
        ...


@dataclass(frozen=True)
class InboxBridgeConfig:
    agent_uid: str
    subject: str
    stream: str
    consumer: str
    inbox_dir: Path
    receipt_dir: Path
    endpoint: str = "nats://127.0.0.1:4222"
    flush_timeout_s: float = 2.0
    deliver_policy: str = "new"
    max_deliver: int = 5
    nats_config: NATSConfig | None = None


def subject_for_agent(agent_uid: str) -> str:
    return f"dharma.agent.{resolve_agent_uid(agent_uid)}.inbox"


def default_inbox_dir(agent_uid: str) -> Path:
    return DEFAULT_A2A_BUS / "inboxes" / resolve_agent_uid(agent_uid)


def default_heartbeat_file(agent_uid: str) -> Path:
    return DEFAULT_HEARTBEAT_DIR / f"{resolve_agent_uid(agent_uid)}.json"


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


def _parse_envelope(message: NatsMessageLike, config: InboxBridgeConfig) -> dict[str, Any]:
    payload = json.loads(message.data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("A2A inbox payload must be a JSON object")
    if str(payload.get("schema_version") or "") != "dharma.a2a.send.v1":
        raise ValueError("A2A inbox payload must use schema dharma.a2a.send.v1")
    packet_id = str(payload.get("packet_id") or "")
    if not packet_id:
        raise ValueError("A2A inbox payload is missing packet_id")
    if str(message.subject) != config.subject:
        raise ValueError("A2A inbox message subject does not match the configured inbox")
    if str(payload.get("subject") or "") != config.subject:
        raise ValueError("A2A inbox envelope subject does not match the configured inbox")
    target_uid = str(payload.get("target_uid") or payload.get("to") or "")
    if target_uid != config.agent_uid:
        raise ValueError("A2A inbox envelope target does not match the configured agent")
    expected_ack = f"{config.subject}.ack.{packet_id}"
    if str(payload.get("ack_subject") or "") != expected_ack:
        raise ValueError("A2A inbox payload ack_subject is not packet-bound to this inbox")
    expected_reply = f"{config.subject}.reply.{packet_id}"
    if str(payload.get("reply_subject") or "") != expected_reply:
        raise ValueError("A2A inbox payload reply_subject is not packet-bound to this inbox")
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


async def process_message(
    message: NatsMessageLike,
    *,
    publisher: PublisherLike,
    config: InboxBridgeConfig,
) -> dict[str, Any]:
    """Persist one inbox envelope, publish its ack, then broker-ack it."""

    receipt = _base_receipt(config, message)
    try:
        payload = _parse_envelope(message, config)
    except Exception as exc:
        envelope_sha = hashlib.sha256(message.data).hexdigest()
        try:
            await message.ack()
            broker_ack = True
        except Exception as ack_exc:  # pragma: no cover - defensive receipt detail
            broker_ack = False
            receipt["broker_ack_error"] = f"{type(ack_exc).__name__}: {ack_exc}"
        receipt.update(
            {
                "status": STATUS_INVALID_ENVELOPE_ACKED,
                "packet_id": "unknown",
                "error": f"{type(exc).__name__}: {exc}",
                "envelope_sha256": envelope_sha,
                "broker_ack": broker_ack,
                "broker_nak": False,
                "envelope_ack_published": False,
                "contact_evidence_tier": "NO_CONTACT",
                "collaboration_claim": "none",
                "poison_message_quarantined": True,
                "operator_contact_note": (
                    "invalid non-canonical inbox payload was broker-acked so the "
                    "durable consumer cannot redeliver it forever"
                ),
            }
        )
        receipt_path = write_receipt(config.receipt_dir, receipt)
        receipt["receipt_path"] = str(receipt_path)
        return receipt

    try:
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
        await publisher.publish(ack_subject, _json_bytes(ack_payload))
        await publisher.flush(timeout=config.flush_timeout_s)
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
                "operator_contact_note": (
                    "delivery handler persisted the envelope and published its "
                    "ack_subject; no semantic peer reply is claimed"
                ),
            }
        )
    except Exception as exc:
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

    runtime_nats = config.nats_config
    nc = await nats.connect(
        servers=[config.endpoint],
        user=(runtime_nats.user or None) if runtime_nats else None,
        password=(runtime_nats.credential or None) if runtime_nats else None,
        allow_reconnect=False,
        max_reconnect_attempts=0,
        **(_nats_tls_kwargs(runtime_nats) if runtime_nats else {}),
    )
    try:
        from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy

        js = nc.jetstream()
        deliver_policy = (
            DeliverPolicy.NEW if config.deliver_policy == "new" else DeliverPolicy.ALL
        )
        consumer_config = ConsumerConfig(
            durable_name=config.consumer,
            filter_subject=config.subject,
            ack_policy=AckPolicy.EXPLICIT,
            ack_wait=60,
            max_deliver=max(config.max_deliver, 1),
            deliver_policy=deliver_policy,
        )
        sub = await js.pull_subscribe(
            config.subject,
            durable=config.consumer,
            stream=config.stream,
            config=consumer_config,
        )
        try:
            messages = await sub.fetch(max_messages, timeout=fetch_timeout_s)
        except NatsTimeoutError:
            messages = []
        if not messages:
            return [write_no_messages_receipt(config)] if write_no_message_receipt else []
        receipts = []
        for message in messages:
            receipts.append(await process_message(message, publisher=nc, config=config))
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
    discovered_nats = _nats_config(dict(os.environ), require_devin_secrets=False)
    endpoint = args.endpoint or discovered_nats.endpoint or "nats://127.0.0.1:4222"
    runtime_nats = NATSConfig(
        endpoint=endpoint,
        user=discovered_nats.user,
        credential=discovered_nats.credential,
        missing=(),
        ca_pem=discovered_nats.ca_pem,
        ca_source=discovered_nats.ca_source,
        tls_hostname=discovered_nats.tls_hostname,
        credential_family=discovered_nats.credential_family,
    )
    return InboxBridgeConfig(
        agent_uid=agent_uid,
        subject=subject,
        stream=args.stream,
        consumer=args.consumer,
        inbox_dir=inbox_dir,
        receipt_dir=Path(args.receipt_dir),
        endpoint=endpoint,
        flush_timeout_s=args.flush_timeout,
        deliver_policy=args.deliver_policy,
        max_deliver=max(args.max_deliver, 1),
        nats_config=runtime_nats,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent-uid", required=True, help="stable target agent UID")
    parser.add_argument("--consumer", required=True, help="durable pull consumer name")
    parser.add_argument("--subject", default="", help="override inbox subject")
    parser.add_argument("--stream", default="DHARMA_FLEET")
    parser.add_argument(
        "--endpoint",
        default="",
        help="broker URL; defaults to canonical NATS environment, then localhost",
    )
    parser.add_argument("--inbox-dir", default="")
    parser.add_argument("--receipt-dir", default=str(DEFAULT_RECEIPT_DIR))
    parser.add_argument("--max-messages", type=int, default=1)
    parser.add_argument("--fetch-timeout", type=float, default=2.0)
    parser.add_argument("--flush-timeout", type=float, default=2.0)
    parser.add_argument("--deliver-policy", choices=["new", "all"], default="new")
    parser.add_argument("--max-deliver", type=int, default=5)
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
