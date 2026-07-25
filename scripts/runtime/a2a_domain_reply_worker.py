#!/usr/bin/env python3
"""Publish target-owned A2A domain reply artifacts to recorded reply subjects.

This is the semantic layer after the inbox bridge. It does not generate peer
replies. It only validates a reply artifact that already lives in the target
agent's outbox and publishes a typed domain receipt to the reply subject from
the original send receipt.
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

from scripts.runtime.a2a_send import ACK_TIER_NO_CONTACT, resolve_agent_uid  # noqa: E402
from dharma_swarm.operator_core.semantic_receipt import (  # noqa: E402
    SemanticReceiptValidationError,
    validate_semantic_receipt,
)
from scripts.runtime.a2a_topology import DEFAULT_COMPATIBILITY_STREAM  # noqa: E402
from scripts.runtime.pr_merge_control import (  # noqa: E402
    NATSConfig,
    _nats_config,
    _nats_tls_kwargs,
    _redacted_nats_config,
    stamp,
    utc_now,
)

DEFAULT_OUTBOX_ROOT = Path.home() / ".dharma" / "a2a_bus" / "outboxes"
DEFAULT_RECEIPT_DIR = REPO_ROOT / "reports" / "a2a" / "domain_reply_receipts"

DOMAIN_REPLY_ARTIFACT_SCHEMA = "dharma.a2a.domain_reply_artifact.v1"
DOMAIN_RECEIPT_SCHEMA = "dharma.a2a.domain_receipt.v1"

STATUS_DOMAIN_REPLY_PUBLISHED = "DOMAIN_REPLY_PUBLISHED"
STATUS_ARTIFACT_INVALID = "ARTIFACT_INVALID"
STATUS_NATS_SECRETS_MISSING = "NATS_SECRETS_MISSING"
STATUS_NATS_CLIENT_MISSING = "NATS_CLIENT_MISSING"
STATUS_PUBLISH_FAILED = "PUBLISH_FAILED"

ACK_TIER_DOMAIN_RECEIPTED = "DOMAIN_RECEIPTED"


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

    async def flush(self, timeout: float | None = None) -> Any:
        ...


@dataclass(frozen=True)
class DomainReplyTarget:
    send_receipt_path: Path
    send_receipt: dict[str, Any]
    reply_artifact_path: Path
    reply_artifact: dict[str, Any]
    agent_uid: str
    packet_id: str
    reply_subject: str


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


def _safe_token(value: object, *, fallback: str = "unknown") -> str:
    chars = [char if char.isalnum() or char in ("_", "-") else "_" for char in str(value or "")]
    return ("".join(chars).strip("_-") or fallback)[:96]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True).encode("utf-8")


def _pub_ack_payload(pub_ack: Any) -> dict[str, Any]:
    stream = str(getattr(pub_ack, "stream", "") or "")
    seq = getattr(pub_ack, "seq", None)
    if not stream or not isinstance(seq, int):
        raise RuntimeError("JetStream publish did not return a durable puback")
    return {"transport_ack": "JETSTREAM_PUB_ACK", "stream": stream, "seq": seq}


def default_outbox_dir(agent_uid: str, *, outbox_root: Path | str = DEFAULT_OUTBOX_ROOT) -> Path:
    return Path(outbox_root).expanduser().resolve() / resolve_agent_uid(agent_uid)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _artifact_actor(artifact: dict[str, Any]) -> str:
    return str(
        artifact.get("authored_by")
        or artifact.get("from_agent")
        or artifact.get("agent_uid")
        or ""
    ).strip()


def _semantic_claim_requested(artifact: dict[str, Any]) -> bool:
    return bool(artifact.get("semantic_reply_claim") or artifact.get("peer_model_processed_claim"))


def _receipt_matches_reply(
    receipt: dict[str, Any],
    *,
    agent_uid: str,
    packet_id: str,
    reply_subject: str,
) -> bool:
    if not bool(receipt.get("semantic_reply_claim")):
        return False
    if str(receipt.get("agent_uid") or "") != agent_uid:
        return False
    if str(receipt.get("correlation_id") or "") != packet_id:
        return False
    if str(receipt.get("reply_to") or "") != reply_subject:
        return False
    return packet_id in str(receipt.get("review_target") or "")


def _validated_semantic_receipt_refs(
    *,
    artifact: dict[str, Any],
    agent_uid: str,
    packet_id: str,
    reply_subject: str,
) -> list[str]:
    refs = artifact.get("evidence_refs")
    if not isinstance(refs, list):
        refs = []
    semantic_path = artifact.get("semantic_receipt_path")
    if semantic_path:
        refs = [*refs, str(semantic_path)]

    valid_refs: list[str] = []
    for ref in refs:
        path = Path(str(ref)).expanduser()
        if not path.exists() or not path.is_file():
            continue
        try:
            payload = _read_json(path)
            receipt = validate_semantic_receipt(payload)
        except (OSError, ValueError, SemanticReceiptValidationError, json.JSONDecodeError):
            continue
        if not _receipt_matches_reply(
            receipt,
            agent_uid=agent_uid,
            packet_id=packet_id,
            reply_subject=reply_subject,
        ):
            continue
        valid_refs.append(str(path.resolve()))
    return list(dict.fromkeys(valid_refs))


def _validate_artifact(
    *,
    artifact: dict[str, Any],
    artifact_path: Path,
    send_receipt: dict[str, Any],
    send_receipt_path: Path,
    agent_uid: str,
    outbox_root: Path,
    enforce_owner_path: bool,
) -> None:
    owner_dir = default_outbox_dir(agent_uid, outbox_root=outbox_root)
    if enforce_owner_path and not _is_relative_to(artifact_path, owner_dir):
        raise ValueError(f"reply artifact must live under the target-owned outbox {owner_dir}")

    schema = str(artifact.get("schema_version") or artifact.get("schema") or "")
    if schema not in {DOMAIN_REPLY_ARTIFACT_SCHEMA, DOMAIN_RECEIPT_SCHEMA}:
        raise ValueError(
            f"reply artifact schema must be {DOMAIN_REPLY_ARTIFACT_SCHEMA} "
            f"or {DOMAIN_RECEIPT_SCHEMA}"
        )

    actor = _artifact_actor(artifact)
    if actor != agent_uid:
        raise ValueError(f"reply artifact actor {actor!r} does not match target agent {agent_uid!r}")

    packet_id = str(send_receipt.get("packet_id") or "")
    if not packet_id:
        raise ValueError("send receipt is missing packet_id")
    if str(artifact.get("packet_id") or "") != packet_id:
        raise ValueError("reply artifact packet_id does not match send receipt")

    reply_subject = str(send_receipt.get("reply_subject") or "")
    if not reply_subject:
        raise ValueError("send receipt is missing reply_subject")
    if artifact.get("reply_subject") and str(artifact["reply_subject"]) != reply_subject:
        raise ValueError("reply artifact reply_subject does not match send receipt")

    artifact_send_receipt = str(artifact.get("send_receipt_path") or "")
    if artifact_send_receipt and Path(artifact_send_receipt).expanduser().resolve() != send_receipt_path:
        raise ValueError("reply artifact send_receipt_path does not match")

    if not any(str(artifact.get(key) or "").strip() for key in ("summary", "verdict", "decision")):
        raise ValueError("reply artifact needs summary, verdict, or decision")

    if _semantic_claim_requested(artifact):
        valid_semantic_refs = _validated_semantic_receipt_refs(
            artifact=artifact,
            agent_uid=agent_uid,
            packet_id=packet_id,
            reply_subject=reply_subject,
        )
        if not valid_semantic_refs:
            raise ValueError(
                "semantic reply claims require a linked, validated SemanticReceipt "
                "with authored_by_model=true and matching agent_uid, packet_id, and reply_subject"
            )
        artifact["validated_semantic_receipt_refs"] = valid_semantic_refs


def load_domain_reply_target(
    *,
    send_receipt_path: Path | str,
    reply_artifact_path: Path | str,
    agent_uid: str = "",
    outbox_root: Path | str = DEFAULT_OUTBOX_ROOT,
    enforce_owner_path: bool = True,
) -> DomainReplyTarget:
    send_path = Path(send_receipt_path).expanduser().resolve()
    artifact_path = Path(reply_artifact_path).expanduser().resolve()
    send_receipt = _read_json(send_path)
    artifact = _read_json(artifact_path)
    target_uid = resolve_agent_uid(
        agent_uid
        or str(send_receipt.get("target_uid") or send_receipt.get("to") or "")
    )
    root = Path(outbox_root).expanduser().resolve()
    _validate_artifact(
        artifact=artifact,
        artifact_path=artifact_path,
        send_receipt=send_receipt,
        send_receipt_path=send_path,
        agent_uid=target_uid,
        outbox_root=root,
        enforce_owner_path=enforce_owner_path,
    )
    return DomainReplyTarget(
        send_receipt_path=send_path,
        send_receipt=send_receipt,
        reply_artifact_path=artifact_path,
        reply_artifact=artifact,
        agent_uid=target_uid,
        packet_id=str(send_receipt["packet_id"]),
        reply_subject=str(send_receipt["reply_subject"]),
    )


def build_domain_receipt_payload(target: DomainReplyTarget) -> dict[str, Any]:
    artifact = target.reply_artifact
    evidence_refs = artifact.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        evidence_refs = []
    peer_model_processed = bool(artifact.get("peer_model_processed_claim", False))
    semantic_reply_claim = bool(artifact.get("semantic_reply_claim", peer_model_processed))
    source_audit_claim = bool(artifact.get("source_audit_claim", False))
    authenticated_target_runtime_claim = bool(artifact.get("authenticated_target_runtime_claim", False))
    if source_audit_claim:
        semantic_audit_depth = "source_audit"
    elif semantic_reply_claim:
        semantic_audit_depth = "packet_only"
    else:
        semantic_audit_depth = "typed_failure"
    return {
        "schema_version": DOMAIN_RECEIPT_SCHEMA,
        "timestamp": utc_now(),
        "from_agent": target.agent_uid,
        "to_agent": str(target.send_receipt.get("from") or target.send_receipt.get("sender") or "operator"),
        "packet_id": target.packet_id,
        "reply_subject": target.reply_subject,
        "domain_receipt": True,
        "semantic_reply_claim": semantic_reply_claim,
        "target_owned_artifact_claim": True,
        "authenticated_target_runtime_claim": authenticated_target_runtime_claim,
        "peer_model_processed_claim": peer_model_processed,
        "source_audit_claim": source_audit_claim,
        "semantic_audit_depth": semantic_audit_depth,
        "author_kind": str(artifact.get("author_kind") or "target_outbox_artifact"),
        "verdict": str(artifact.get("verdict") or artifact.get("decision") or "received"),
        "summary": str(artifact.get("summary") or ""),
        "evidence_refs": evidence_refs,
        "source_artifact_schema": str(artifact.get("schema_version") or artifact.get("schema") or ""),
        "source_artifact_path": str(target.reply_artifact_path),
        "source_artifact_sha256": sha256_file(target.reply_artifact_path),
        "validated_semantic_receipt_refs": list(artifact.get("validated_semantic_receipt_refs") or []),
        "causation_send_receipt_path": str(target.send_receipt_path),
        "causation_send_receipt_sha256": sha256_file(target.send_receipt_path),
        "operator_contact_note": (
            "target-owned reply artifact was validated and published to the recorded "
            "reply_subject as a typed domain receipt; semantic_reply_claim follows "
            "the artifact's explicit peer/model-processing claim; target_owned_artifact_claim "
            "is a path and metadata ownership claim, not an authenticated target-runtime signature"
        ),
    }


def write_domain_reply_receipt(receipt_dir: Path, receipt: dict[str, Any]) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    agent = _safe_token(receipt.get("agent_uid"))
    packet_id = _safe_token(receipt.get("packet_id"))
    path = receipt_dir / f"{stamp()}-{agent}-{packet_id}.json"
    _write_json(path, receipt)
    return path


async def publish_domain_reply(
    target: DomainReplyTarget,
    *,
    publisher: PublisherLike,
    receipt_dir: Path,
    endpoint: str,
    stream: str,
    flush_timeout_s: float = 2.0,
    nats: dict[str, Any] | None = None,
    transport_ack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = build_domain_receipt_payload(target)
    payload_bytes = _json_bytes(payload)
    receipt = {
        "schema_version": "dharma.a2a.domain_reply_publish_receipt.v1",
        "timestamp": utc_now(),
        "status": STATUS_PUBLISH_FAILED,
        "agent_uid": target.agent_uid,
        "packet_id": target.packet_id,
        "reply_subject": target.reply_subject,
        "send_receipt_path": str(target.send_receipt_path),
        "reply_artifact_path": str(target.reply_artifact_path),
        "reply_artifact_sha256": payload["source_artifact_sha256"],
        "stream": stream,
        "endpoint": endpoint,
        "nats": nats or {},
        "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "payload_schema": DOMAIN_RECEIPT_SCHEMA,
        "semantic_reply_claim": False,
        "domain_receipt_claim": False,
        "target_owned_artifact_claim": True,
        "contact_evidence_tier": ACK_TIER_NO_CONTACT,
        "reply_evidence_tier": ACK_TIER_NO_CONTACT,
    }
    try:
        message_id = "domain_reply_" + hashlib.sha256(
            f"{target.reply_subject}|{receipt['payload_sha256']}".encode("utf-8")
        ).hexdigest()[:32]
        pub_ack = await publisher.publish(
            target.reply_subject,
            payload_bytes,
            headers={"Nats-Msg-Id": message_id},
            timeout=flush_timeout_s,
        )
        durable_pub_ack = _pub_ack_payload(pub_ack)
        await publisher.flush(timeout=flush_timeout_s)
        receipt.update(
            {
                "status": STATUS_DOMAIN_REPLY_PUBLISHED,
                "contact_evidence_tier": ACK_TIER_DOMAIN_RECEIPTED,
                "reply_evidence_tier": ACK_TIER_DOMAIN_RECEIPTED,
                "semantic_reply_claim": bool(payload.get("semantic_reply_claim", False)),
                "domain_receipt_claim": True,
                "message_id": message_id,
                "transport_ack": durable_pub_ack,
                "domain_receipt_payload": payload,
                "operator_contact_note": (
                    "typed domain receipt was published to the recorded reply_subject; "
                    "run a2a_reply_capture.py to record DOMAIN_RECEIPTED from the stream"
                ),
            }
        )

    except Exception as exc:
        receipt.update(
            {
                "status": STATUS_PUBLISH_FAILED,
                "error": f"{type(exc).__name__}: {exc}",
                "operator_contact_note": "domain receipt payload could not be published",
            }
        )
    receipt_path = write_domain_reply_receipt(receipt_dir, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return receipt


class _JetStreamPublisher:
    def __init__(self, nc: Any) -> None:
        self.nc = nc
        self.js = nc.jetstream()
        self.last_ack: Any = None

    async def publish(
        self,
        subject: str,
        payload: bytes,
        *,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        self.last_ack = await self.js.publish(
            subject,
            payload,
            timeout=timeout,
            headers=headers,
        )
        return self.last_ack

    async def flush(self, timeout: float | None = None) -> None:
        await self.nc.flush(timeout=timeout)

    def transport_ack(self) -> dict[str, Any]:
        if self.last_ack is None:
            return {}
        return {
            "transport_ack": "JETSTREAM_PUB_ACK",
            "stream": getattr(self.last_ack, "stream", ""),
            "seq": getattr(self.last_ack, "seq", None),
        }


async def publish_domain_reply_with_nats(
    target: DomainReplyTarget,
    *,
    config: NATSConfig,
    receipt_dir: Path,
    stream: str,
    timeout_s: float,
    flush_timeout_s: float,
) -> dict[str, Any]:
    if config.missing or not config.endpoint:
        receipt = {
            "schema_version": "dharma.a2a.domain_reply_publish_receipt.v1",
            "timestamp": utc_now(),
            "status": STATUS_NATS_SECRETS_MISSING,
            "agent_uid": target.agent_uid,
            "packet_id": target.packet_id,
            "reply_subject": target.reply_subject,
            "send_receipt_path": str(target.send_receipt_path),
            "reply_artifact_path": str(target.reply_artifact_path),
            "stream": stream,
            "endpoint": config.endpoint,
            "nats": _redacted_nats_config(config),
            "missing": list(config.missing),
            "semantic_reply_claim": False,
            "domain_receipt_claim": False,
            "contact_evidence_tier": ACK_TIER_NO_CONTACT,
            "reply_evidence_tier": ACK_TIER_NO_CONTACT,
            "operator_contact_note": "NATS credentials or endpoint missing; domain receipt not published",
        }
        receipt_path = write_domain_reply_receipt(receipt_dir, receipt)
        receipt["receipt_path"] = str(receipt_path)
        return receipt

    try:
        import nats
    except ModuleNotFoundError as exc:
        if getattr(exc, "name", "") != "nats":
            raise
        receipt = {
            "schema_version": "dharma.a2a.domain_reply_publish_receipt.v1",
            "timestamp": utc_now(),
            "status": STATUS_NATS_CLIENT_MISSING,
            "agent_uid": target.agent_uid,
            "packet_id": target.packet_id,
            "reply_subject": target.reply_subject,
            "send_receipt_path": str(target.send_receipt_path),
            "reply_artifact_path": str(target.reply_artifact_path),
            "stream": stream,
            "endpoint": config.endpoint,
            "nats": _redacted_nats_config(config),
            "semantic_reply_claim": False,
            "domain_receipt_claim": False,
            "contact_evidence_tier": ACK_TIER_NO_CONTACT,
            "reply_evidence_tier": ACK_TIER_NO_CONTACT,
            "error": "nats-py is not installed in this Python environment",
        }
        receipt_path = write_domain_reply_receipt(receipt_dir, receipt)
        receipt["receipt_path"] = str(receipt_path)
        return receipt

    nc = await nats.connect(
        servers=[config.endpoint],
        user=config.user or None,
        password=config.credential or None,
        connect_timeout=timeout_s,
        allow_reconnect=False,
        max_reconnect_attempts=0,
        **_nats_tls_kwargs(config),
    )
    try:
        publisher = _JetStreamPublisher(nc)
        receipt = await publish_domain_reply(
            target,
            publisher=publisher,
            receipt_dir=receipt_dir,
            endpoint=config.endpoint,
            stream=stream,
            flush_timeout_s=flush_timeout_s,
            nats=_redacted_nats_config(config),
        )
        return receipt
    finally:
        await nc.close()


def artifact_invalid_receipt(
    *,
    agent_uid: str,
    packet_id: str,
    reply_subject: str,
    send_receipt_path: Path | str,
    reply_artifact_path: Path | str,
    receipt_dir: Path,
    error: str,
) -> dict[str, Any]:
    receipt = {
        "schema_version": "dharma.a2a.domain_reply_publish_receipt.v1",
        "timestamp": utc_now(),
        "status": STATUS_ARTIFACT_INVALID,
        "agent_uid": agent_uid,
        "packet_id": packet_id,
        "reply_subject": reply_subject,
        "send_receipt_path": str(send_receipt_path),
        "reply_artifact_path": str(reply_artifact_path),
        "semantic_reply_claim": False,
        "domain_receipt_claim": False,
        "contact_evidence_tier": ACK_TIER_NO_CONTACT,
        "reply_evidence_tier": ACK_TIER_NO_CONTACT,
        "error": error,
        "operator_contact_note": "reply artifact failed target-owned validation; no domain receipt published",
    }
    receipt_path = write_domain_reply_receipt(receipt_dir, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--send-receipt", required=True, help="A2A send receipt with packet_id and reply_subject")
    parser.add_argument("--reply-artifact", required=True, help="target-owned domain reply artifact JSON")
    parser.add_argument("--agent-uid", default="", help="target agent uid; defaults to send receipt target_uid/to")
    parser.add_argument("--outbox-root", default=str(DEFAULT_OUTBOX_ROOT))
    parser.add_argument("--receipt-dir", default=str(DEFAULT_RECEIPT_DIR))
    parser.add_argument("--stream", default=DEFAULT_COMPATIBILITY_STREAM)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--flush-timeout", type=float, default=2.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    receipt_dir = Path(args.receipt_dir)
    try:
        target = load_domain_reply_target(
            send_receipt_path=args.send_receipt,
            reply_artifact_path=args.reply_artifact,
            agent_uid=args.agent_uid,
            outbox_root=args.outbox_root,
            enforce_owner_path=True,
        )
    except Exception as exc:
        try:
            send_receipt = _read_json(Path(args.send_receipt).expanduser().resolve())
        except Exception:
            send_receipt = {}
        receipt = artifact_invalid_receipt(
            agent_uid=str(args.agent_uid or send_receipt.get("target_uid") or send_receipt.get("to") or "unknown"),
            packet_id=str(send_receipt.get("packet_id") or "unknown"),
            reply_subject=str(send_receipt.get("reply_subject") or "unknown"),
            send_receipt_path=args.send_receipt,
            reply_artifact_path=args.reply_artifact,
            receipt_dir=receipt_dir,
            error=f"{type(exc).__name__}: {exc}",
        )
        if args.json:
            print(json.dumps(receipt, indent=2, sort_keys=True))
        else:
            print(f"{receipt['status']} packet_id={receipt['packet_id']} reply_subject={receipt['reply_subject']}")
            print(f"receipt: {receipt['receipt_path']}")
        return 2

    config = _nats_config(dict(os.environ), require_devin_secrets=False)
    receipt = asyncio.run(
        publish_domain_reply_with_nats(
            target,
            config=config,
            receipt_dir=receipt_dir,
            stream=args.stream,
            timeout_s=max(args.timeout, 0.1),
            flush_timeout_s=max(args.flush_timeout, 0.1),
        )
    )
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(f"{receipt['status']} packet_id={receipt['packet_id']} reply_subject={receipt['reply_subject']}")
        print(f"receipt: {receipt['receipt_path']}")

    if receipt["status"] == STATUS_DOMAIN_REPLY_PUBLISHED:
        return 0
    if receipt["status"] == STATUS_NATS_SECRETS_MISSING:
        return 3
    if receipt["status"] == STATUS_NATS_CLIENT_MISSING:
        return 4
    if receipt["status"] == STATUS_ARTIFACT_INVALID:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
