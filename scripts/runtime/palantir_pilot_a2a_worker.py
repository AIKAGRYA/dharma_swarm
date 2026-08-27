#!/usr/bin/env python3
"""Run Palantir Pilot as a real A2A mailbox worker.

The worker subscribes to Palantir Pilot's declared A2A subject, publishes the
packet ack_subject when it has actually seen a packet, builds an answer through
the registered local public-source Palantir Pilot surface, writes a durable
answer artifact, and publishes a typed semantic reply to the packet reply_subject.

It is intentionally narrower than a general agent runtime: public-source only,
no private Palantir access, no source-tree mutation, and no claim that an
external model processed the packet.
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
from typing import Any, Callable, Protocol

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.palantir_pilot import (  # noqa: E402
    AGENT_ID,
    CALLSIGN,
    DEFAULT_DHARMA_HOME,
    DISPLAY_NAME,
    FORBIDDEN_ACTIONS,
    NATS_SUBJECT,
    build_answer_packet,
)
from dharma_swarm.daemon_config import runtime_report_dir  # noqa: E402
from scripts.runtime.a2a_send import ACK_TIER_HANDLER_ACKED, ACK_TIER_NO_CONTACT  # noqa: E402
from scripts.runtime.pr_merge_control import (  # noqa: E402
    NATSConfig,
    _nats_config,
    _nats_tls_kwargs,
    _redacted_nats_config,
    stamp,
    utc_now,
)

DEFAULT_A2A_BUS = Path.home() / ".dharma" / "a2a_bus"
DEFAULT_OUTBOX_DIR = DEFAULT_A2A_BUS / "outboxes" / CALLSIGN
DEFAULT_HEARTBEAT_FILE = DEFAULT_A2A_BUS / "worker_heartbeats" / f"{CALLSIGN}.json"
DEFAULT_RECEIPT_DIR = runtime_report_dir("a2a", "palantir_pilot_worker_receipts")

SEMANTIC_REPLY_SCHEMA = "dharma.a2a.semantic_reply.v1"
HANDLER_ACK_SCHEMA = "dharma.a2a.palantir_pilot.handler_ack.v1"
WORKER_RECEIPT_SCHEMA = "dharma.a2a.palantir_pilot.worker_receipt.v1"
ANSWER_ARTIFACT_SCHEMA = "dharma.a2a.palantir_pilot.answer_artifact.v1"

STATUS_NO_MESSAGES = "NO_MESSAGES"
STATUS_REPLIED = "PALANTIR_PILOT_REPLIED"
STATUS_FAILED = "PALANTIR_PILOT_FAILED"
STATUS_NATS_CLIENT_MISSING = "NATS_CLIENT_MISSING"
STATUS_NATS_SECRETS_MISSING = "NATS_SECRETS_MISSING"

REPLY_TIER_SEMANTIC = "SEMANTIC_REPLY_PUBLISHED"


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


AnswerBuilder = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class PalantirPilotWorkerConfig:
    subject: str = NATS_SUBJECT
    stream: str = "DHARMA_FLEET"
    consumer: str = "palantir_pilot_a2a"
    endpoint: str = "nats://127.0.0.1:4222"
    receipt_dir: Path = DEFAULT_RECEIPT_DIR
    outbox_dir: Path = DEFAULT_OUTBOX_DIR
    dharma_home: Path = DEFAULT_DHARMA_HOME
    query_limit: int = 8
    flush_timeout_s: float = 2.0


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True).encode("utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{stamp()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _safe_token(value: object, *, fallback: str = "unknown") -> str:
    chars = [
        char if char.isalnum() or char in ("_", "-") else "_"
        for char in str(value or "")
    ]
    return ("".join(chars).strip("_-") or fallback)[:96]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_envelope(message: NatsMessageLike) -> dict[str, Any]:
    payload = json.loads(message.data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("A2A packet must be a JSON object")
    for field in ("packet_id", "ack_subject", "reply_subject"):
        if not str(payload.get(field) or "").strip():
            raise ValueError(f"A2A packet is missing {field}")
    return payload


def query_from_envelope(envelope: dict[str, Any]) -> str:
    for key in ("query", "question", "content"):
        value = str(envelope.get(key) or "").strip()
        if value:
            return value
    raise ValueError("A2A packet does not contain query, question, or content")


def answer_artifact_path(config: PalantirPilotWorkerConfig, packet_id: str) -> Path:
    return config.outbox_dir / f"{_safe_token(packet_id)}-answer.json"


def evidence_refs(answer_packet: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for item in answer_packet.get("source_citations") or []:
        if isinstance(item, dict) and item.get("url"):
            refs.append(
                {
                    "kind": "public_url_metadata",
                    "ref": str(item["url"]),
                    "family": str(item.get("family") or ""),
                }
            )
    for item in answer_packet.get("note_citations") or []:
        if isinstance(item, dict) and item.get("path"):
            refs.append(
                {
                    "kind": "local_wiki_note",
                    "ref": str(item["path"]),
                    "family": "",
                }
            )
    return refs


def build_handler_ack_payload(
    envelope: dict[str, Any],
    *,
    config: PalantirPilotWorkerConfig,
    envelope_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": HANDLER_ACK_SCHEMA,
        "timestamp": utc_now(),
        "agent_id": AGENT_ID,
        "callsign": CALLSIGN,
        "packet_id": str(envelope["packet_id"]),
        "subject": config.subject,
        "ack_subject": str(envelope["ack_subject"]),
        "reply_subject": str(envelope["reply_subject"]),
        "ack_tier": ACK_TIER_HANDLER_ACKED,
        "envelope_sha256": envelope_sha256,
        "semantic_reply_claim": False,
        "peer_model_processed_claim": False,
        "operator_contact_note": "Palantir Pilot worker received the packet and will process it under its public-source boundary.",
    }


def build_semantic_reply_payload(
    envelope: dict[str, Any],
    *,
    query: str,
    answer_packet: dict[str, Any],
    artifact_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SEMANTIC_REPLY_SCHEMA,
        "timestamp": utc_now(),
        "from_agent": CALLSIGN,
        "from_agent_id": AGENT_ID,
        "display_name": DISPLAY_NAME,
        "to_agent": str(envelope.get("from") or envelope.get("sender") or "operator"),
        "packet_id": str(envelope["packet_id"]),
        "reply_subject": str(envelope["reply_subject"]),
        "query": query,
        "answer": str(answer_packet.get("answer") or ""),
        "confidence": str(answer_packet.get("confidence") or ""),
        "answer_packet": answer_packet,
        "semantic_reply_claim": True,
        "peer_model_processed_claim": False,
        "answer_engine": "palantir_pilot.local_public_source_query",
        "source_boundary": str(answer_packet.get("source_boundary") or ""),
        "registration_boundary": {
            "authority": "external_worker_evidence_only",
            "public_source_only": True,
            "official_affiliation": False,
            "private_palantir_access": False,
            "forbidden_actions": FORBIDDEN_ACTIONS,
        },
        "evidence_refs": evidence_refs(answer_packet),
        "source_artifact_path": str(artifact_path),
        "operator_contact_note": (
            "semantic reply generated by the local Palantir Pilot public-source "
            "workspace; no official Palantir affiliation, private tenant access, "
            "or Learn/course scraping is claimed"
        ),
    }


def write_worker_receipt(receipt_dir: Path, receipt: dict[str, Any]) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    packet_id = _safe_token(receipt.get("packet_id"))
    status = _safe_token(receipt.get("status"))
    path = receipt_dir / f"{stamp()}-{CALLSIGN}-{packet_id}-{status}.json"
    _write_json(path, receipt)
    return path


def write_heartbeat(path: Path, config: PalantirPilotWorkerConfig, payload: dict[str, Any]) -> None:
    body = {
        "schema_version": "dharma.a2a.palantir_pilot.worker_heartbeat.v1",
        "timestamp": utc_now(),
        "agent_id": AGENT_ID,
        "callsign": CALLSIGN,
        "subject": config.subject,
        "stream": config.stream,
        "consumer": config.consumer,
        **payload,
    }
    _write_json(path, body)


def no_messages_receipt(config: PalantirPilotWorkerConfig) -> dict[str, Any]:
    receipt = {
        "schema_version": WORKER_RECEIPT_SCHEMA,
        "timestamp": utc_now(),
        "status": STATUS_NO_MESSAGES,
        "agent_id": AGENT_ID,
        "callsign": CALLSIGN,
        "subject": config.subject,
        "stream": config.stream,
        "consumer": config.consumer,
        "endpoint": config.endpoint,
        "contact_evidence_tier": ACK_TIER_NO_CONTACT,
        "reply_evidence_tier": ACK_TIER_NO_CONTACT,
        "semantic_reply_claim": False,
        "live_contact_claim": False,
        "collaboration_claim": "none",
    }
    receipt_path = write_worker_receipt(config.receipt_dir, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return receipt


async def process_message(
    message: NatsMessageLike,
    *,
    publisher: PublisherLike,
    config: PalantirPilotWorkerConfig,
    answer_builder: AnswerBuilder = build_answer_packet,
) -> dict[str, Any]:
    ack_published = False
    reply_published = False
    receipt: dict[str, Any] = {
        "schema_version": WORKER_RECEIPT_SCHEMA,
        "timestamp": utc_now(),
        "status": STATUS_FAILED,
        "agent_id": AGENT_ID,
        "callsign": CALLSIGN,
        "subject": config.subject,
        "message_subject": str(message.subject),
        "stream": config.stream,
        "consumer": config.consumer,
        "endpoint": config.endpoint,
        "contact_evidence_tier": ACK_TIER_NO_CONTACT,
        "reply_evidence_tier": ACK_TIER_NO_CONTACT,
        "semantic_reply_claim": False,
        "peer_model_processed_claim": False,
        "live_contact_claim": False,
        "collaboration_claim": "none",
    }
    try:
        envelope = _parse_envelope(message)
        packet_id = str(envelope["packet_id"])
        query = query_from_envelope(envelope)
        envelope_sha = _sha256_bytes(message.data)
        receipt.update(
            {
                "packet_id": packet_id,
                "ack_subject": str(envelope["ack_subject"]),
                "reply_subject": str(envelope["reply_subject"]),
                "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
                "envelope_sha256": envelope_sha,
            }
        )

        ack_payload = build_handler_ack_payload(
            envelope,
            config=config,
            envelope_sha256=envelope_sha,
        )
        await publisher.publish(str(envelope["ack_subject"]), _json_bytes(ack_payload))
        await publisher.flush(timeout=config.flush_timeout_s)
        ack_published = True

        answer_packet = answer_builder(
            query,
            dharma_home=config.dharma_home,
            limit=config.query_limit,
        )
        artifact_path = answer_artifact_path(config, packet_id)
        reply_payload = build_semantic_reply_payload(
            envelope,
            query=query,
            answer_packet=answer_packet,
            artifact_path=artifact_path,
        )
        _write_json(artifact_path, reply_payload)

        await publisher.publish(str(envelope["reply_subject"]), _json_bytes(reply_payload))
        await publisher.flush(timeout=config.flush_timeout_s)
        reply_published = True
        await message.ack()

        receipt.update(
            {
                "status": STATUS_REPLIED,
                "contact_evidence_tier": ACK_TIER_HANDLER_ACKED,
                "reply_evidence_tier": REPLY_TIER_SEMANTIC,
                "semantic_reply_claim": True,
                "peer_model_processed_claim": False,
                "live_contact_claim": True,
                "collaboration_claim": "protocol_bound_semantic_reply",
                "ack_published": True,
                "reply_published": True,
                "broker_ack": True,
                "answer_artifact_path": str(artifact_path),
                "answer_artifact_sha256": _sha256_file(artifact_path),
                "answer_confidence": str(answer_packet.get("confidence") or ""),
                "source_citation_count": len(answer_packet.get("source_citations") or []),
                "note_citation_count": len(answer_packet.get("note_citations") or []),
                "answer_schema": str(answer_packet.get("schema_version") or ""),
                "reply_schema": SEMANTIC_REPLY_SCHEMA,
                "operator_contact_note": (
                    "Palantir Pilot worker received, acknowledged, answered, "
                    "persisted an artifact, and published a semantic reply under "
                    "its public-source registration boundary"
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
                "status": STATUS_FAILED,
                "error": f"{type(exc).__name__}: {exc}",
                "ack_published": ack_published,
                "reply_published": reply_published,
                "broker_ack": False,
                "broker_nak": broker_nak,
                "operator_contact_note": "Palantir Pilot worker failed before completing semantic reply.",
            }
        )
    receipt_path = write_worker_receipt(config.receipt_dir, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def _nats_failure_receipt(
    *,
    config: PalantirPilotWorkerConfig,
    status: str,
    nats_config: NATSConfig | None = None,
    error: str = "",
) -> dict[str, Any]:
    receipt = {
        "schema_version": WORKER_RECEIPT_SCHEMA,
        "timestamp": utc_now(),
        "status": status,
        "agent_id": AGENT_ID,
        "callsign": CALLSIGN,
        "subject": config.subject,
        "stream": config.stream,
        "consumer": config.consumer,
        "endpoint": config.endpoint,
        "nats": _redacted_nats_config(nats_config) if nats_config else {},
        "contact_evidence_tier": ACK_TIER_NO_CONTACT,
        "reply_evidence_tier": ACK_TIER_NO_CONTACT,
        "semantic_reply_claim": False,
        "live_contact_claim": False,
        "collaboration_claim": "none",
        "error": error,
    }
    receipt_path = write_worker_receipt(config.receipt_dir, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return receipt


async def run_worker_once(
    config: PalantirPilotWorkerConfig,
    *,
    nats_config: NATSConfig,
    max_messages: int = 1,
    fetch_timeout_s: float = 2.0,
    write_no_message_receipt: bool = True,
) -> list[dict[str, Any]]:
    if nats_config.missing or not nats_config.endpoint:
        return [
            _nats_failure_receipt(
                config=config,
                status=STATUS_NATS_SECRETS_MISSING,
                nats_config=nats_config,
                error="NATS credentials or endpoint missing",
            )
        ]

    try:
        import nats
        from nats.errors import TimeoutError as NatsTimeoutError
    except ModuleNotFoundError as exc:
        if getattr(exc, "name", "") == "nats":
            return [
                _nats_failure_receipt(
                    config=config,
                    status=STATUS_NATS_CLIENT_MISSING,
                    nats_config=nats_config,
                    error="nats-py is not installed in this Python environment",
                )
            ]
        raise

    nc = await nats.connect(
        servers=[str(nats_config.endpoint)],
        user=nats_config.user or None,
        password=nats_config.credential or None,
        connect_timeout=max(fetch_timeout_s, 0.1),
        allow_reconnect=False,
        max_reconnect_attempts=0,
        **_nats_tls_kwargs(nats_config),
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
            return [no_messages_receipt(config)] if write_no_message_receipt else []
        return [
            await process_message(message, publisher=nc, config=config)
            for message in messages
        ]
    finally:
        await nc.close()


async def run_worker_loop(
    config: PalantirPilotWorkerConfig,
    *,
    nats_config: NATSConfig,
    max_messages: int = 5,
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
        latest = await run_worker_once(
            config,
            nats_config=nats_config,
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
                f"{receipt['status']} callsign={CALLSIGN} subject={config.subject}",
                flush=True,
            )
            print(f"receipt: {receipt['receipt_path']}", flush=True)
        await asyncio.sleep(max(poll_interval_s, 0.1))
    return latest


def _build_config(args: argparse.Namespace, nats_config: NATSConfig) -> PalantirPilotWorkerConfig:
    return PalantirPilotWorkerConfig(
        subject=args.subject,
        stream=args.stream,
        consumer=args.consumer,
        endpoint=str(nats_config.endpoint or args.endpoint),
        receipt_dir=Path(args.receipt_dir).expanduser(),
        outbox_dir=Path(args.outbox_dir).expanduser(),
        dharma_home=Path(args.dharma_home).expanduser(),
        query_limit=max(args.query_limit, 1),
        flush_timeout_s=max(args.flush_timeout, 0.1),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subject", default=NATS_SUBJECT)
    parser.add_argument("--stream", default="DHARMA_FLEET")
    parser.add_argument("--consumer", default="palantir_pilot_a2a")
    parser.add_argument("--endpoint", default="nats://127.0.0.1:4222")
    parser.add_argument("--receipt-dir", default=str(DEFAULT_RECEIPT_DIR))
    parser.add_argument("--outbox-dir", default=str(DEFAULT_OUTBOX_DIR))
    parser.add_argument("--dharma-home", default=str(DEFAULT_DHARMA_HOME))
    parser.add_argument("--query-limit", type=int, default=8)
    parser.add_argument("--max-messages", type=int, default=1)
    parser.add_argument("--fetch-timeout", type=float, default=2.0)
    parser.add_argument("--flush-timeout", type=float, default=2.0)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--suppress-no-messages", action="store_true")
    parser.add_argument("--heartbeat-file", default=str(DEFAULT_HEARTBEAT_FILE))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    env = dict(os.environ)
    env.setdefault("NATS_URL", args.endpoint)
    nats_config = _nats_config(env, require_devin_secrets=False)
    config = _build_config(args, nats_config)
    heartbeat_file = Path(args.heartbeat_file).expanduser() if args.heartbeat_file else None

    try:
        if args.loop:
            receipts = asyncio.run(
                run_worker_loop(
                    config,
                    nats_config=nats_config,
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
                run_worker_once(
                    config,
                    nats_config=nats_config,
                    max_messages=max(args.max_messages, 1),
                    fetch_timeout_s=max(args.fetch_timeout, 0.1),
                    write_no_message_receipt=not args.suppress_no_messages,
                )
            )
    except KeyboardInterrupt:
        print("STOPPED", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(receipts, indent=2, sort_keys=True))
    else:
        for receipt in receipts:
            print(f"{receipt['status']} callsign={CALLSIGN} subject={config.subject}")
            print(f"receipt: {receipt['receipt_path']}")

    if any(receipt.get("status") == STATUS_REPLIED for receipt in receipts):
        return 0
    if any(receipt.get("status") == STATUS_FAILED for receipt in receipts):
        return 1
    if any(receipt.get("status") == STATUS_NATS_SECRETS_MISSING for receipt in receipts):
        return 3
    if any(receipt.get("status") == STATUS_NATS_CLIENT_MISSING for receipt in receipts):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
