#!/usr/bin/env python3
"""Capture asynchronous A2A reply-subject payloads as receipts.

The sender can wait for a reply only during its process lifetime. This verifier
checks the reply subject recorded in a send receipt and persists a receipt for
what is actually present: no reply, an untyped reply payload, or a typed domain
receipt. It does not generate peer replies.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.runtime.a2a_send import (  # noqa: E402
    ACK_TIER_HANDLER_ACKED,
    ACK_TIER_NO_CONTACT,
)
from scripts.runtime.a2a_topology import (  # noqa: E402
    DEFAULT_COMPATIBILITY_STREAM,
    REPLY_CONSUMER_PREFIX,
)
from scripts.runtime.pr_merge_control import stamp, utc_now  # noqa: E402

DEFAULT_SEND_RECEIPT_ROOT = REPO_ROOT / "reports" / "a2a" / "send_receipts"
DEFAULT_REPLY_RECEIPT_ROOT = REPO_ROOT / "reports" / "a2a" / "reply_receipts"

STATUS_NO_REPLY = "NO_REPLY"
STATUS_REPLY_CAPTURED = "REPLY_CAPTURED"
STATUS_DOMAIN_RECEIPTED = "DOMAIN_RECEIPTED"
STATUS_REPLY_CAPTURE_FAILED = "REPLY_CAPTURE_FAILED"
STATUS_REPLY_SUBJECT_MISMATCH = "REPLY_SUBJECT_MISMATCH"
STATUS_NATS_CLIENT_MISSING = "NATS_CLIENT_MISSING"
ACK_TIER_DOMAIN_RECEIPTED = "DOMAIN_RECEIPTED"
ACK_TIER_RED_MISMATCH = "RED_MISMATCH"

DOMAIN_REPLY_SCHEMAS = {
    "dharma.a2a.semantic_reply.v1",
    "dharma.a2a.domain_receipt.v1",
    "dharma.a2a.reply_receipt.v1",
}


class NatsMessageLike(Protocol):
    subject: str
    data: bytes

    async def ack(self) -> Any:
        ...

    async def nak(self) -> Any:
        ...


@dataclass(frozen=True)
class ReplyCaptureTarget:
    send_receipt_path: Path
    send_receipt: dict[str, Any]
    reply_subject: str
    packet_id: str
    target: str


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _safe_token(value: object, *, fallback: str = "unknown") -> str:
    chars = [char if char.isalnum() or char in ("_", "-") else "_" for char in str(value or "")]
    return ("".join(chars).strip("_-") or fallback)[:96]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_reply_receipt(receipt_root: Path, receipt: dict[str, Any]) -> Path:
    receipt_root.mkdir(parents=True, exist_ok=True)
    packet_id = _safe_token(receipt.get("packet_id"))
    target = _safe_token(receipt.get("to") or receipt.get("target_uid"))
    path = receipt_root / f"{stamp()}-{target}-{packet_id}.json"
    _write_json(path, receipt)
    return path


def commit_reply_receipt(receipt_root: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    """Atomically commit one idempotent capture receipt before source ACK."""

    receipt_root.mkdir(parents=True, exist_ok=True)
    payload_sha = str(receipt.get("reply_payload_sha256") or "")
    reply_subject = str(receipt.get("reply_subject") or "")
    if not payload_sha or not reply_subject:
        raise ValueError("capture receipt requires reply subject and payload hash")
    capture_id = "reply_capture_" + hashlib.sha256(
        f"{reply_subject}|{payload_sha}".encode("utf-8")
    ).hexdigest()[:32]
    target = _safe_token(receipt.get("to") or receipt.get("target_uid"))
    packet_id = _safe_token(receipt.get("packet_id"))
    path = receipt_root / f"{target}-{packet_id}-{capture_id}.json"
    receipt = {**receipt, "capture_id": capture_id, "receipt_path": str(path)}

    if path.exists():
        committed = _read_json(path)
        if (
            committed.get("capture_id") != capture_id
            or committed.get("reply_payload_sha256") != payload_sha
        ):
            raise RuntimeError(f"reply capture collision at {path}")
        return committed

    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=receipt_root)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, path)
        except FileExistsError:
            committed = _read_json(path)
            if (
                committed.get("capture_id") != capture_id
                or committed.get("reply_payload_sha256") != payload_sha
            ):
                raise RuntimeError(f"reply capture collision at {path}")
            return committed
        directory_fd = os.open(receipt_root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temp_path.unlink(missing_ok=True)
    return receipt


def _payload_from_message(message: NatsMessageLike) -> tuple[dict[str, Any], str]:
    sha = hashlib.sha256(message.data).hexdigest()
    try:
        payload = json.loads(message.data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {"raw": message.data.decode("utf-8", "replace")}
    if not isinstance(payload, dict):
        payload = {"value": payload}
    return payload, sha


def _schema(payload: dict[str, Any]) -> str:
    return str(payload.get("schema_version") or payload.get("schema") or "")


def _is_domain_receipt(payload: dict[str, Any]) -> bool:
    schema = _schema(payload)
    return schema in DOMAIN_REPLY_SCHEMAS


def reply_consumer_name(reply_subject: str) -> str:
    """Return the stable durable consumer name for one exact reply subject."""

    digest = hashlib.sha256(reply_subject.encode("utf-8")).hexdigest()[:32]
    return f"{REPLY_CONSUMER_PREFIX}{digest}"


def pending_reply_targets(
    send_receipt_root: Path | str,
    *,
    target: str = "",
    limit: int = 0,
) -> list[ReplyCaptureTarget]:
    root = Path(send_receipt_root).expanduser().resolve()
    if not root.exists():
        return []
    paths = sorted(
        (path for path in root.glob("*.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    targets: list[ReplyCaptureTarget] = []
    for path in paths:
        receipt = _read_json(path)
        if receipt.get("replied") is True:
            continue
        reply_subject = str(receipt.get("reply_subject") or "")
        if not reply_subject:
            continue
        receipt_target = str(receipt.get("to") or receipt.get("target_uid") or "")
        target_uid = str(receipt.get("target_uid") or "")
        if target and target not in path.stem and target not in {receipt_target, target_uid}:
            continue
        targets.append(
            ReplyCaptureTarget(
                send_receipt_path=path,
                send_receipt=receipt,
                reply_subject=reply_subject,
                packet_id=str(receipt.get("packet_id") or path.stem),
                target=receipt_target or target_uid or "unknown",
            )
        )
        if limit > 0 and len(targets) >= limit:
            break
    return targets


def no_reply_receipt(target: ReplyCaptureTarget, *, stream: str, endpoint: str) -> dict[str, Any]:
    return {
        "schema_version": "dharma.a2a.reply_capture_receipt.v1",
        "timestamp": utc_now(),
        "status": STATUS_NO_REPLY,
        "reply_evidence_tier": STATUS_NO_REPLY,
        "contact_evidence_tier": str(
            target.send_receipt.get("contact_evidence_tier") or ACK_TIER_NO_CONTACT
        ),
        "to": target.target,
        "target_uid": str(target.send_receipt.get("target_uid") or ""),
        "packet_id": target.packet_id,
        "reply_subject": target.reply_subject,
        "send_receipt_path": str(target.send_receipt_path),
        "send_status": str(target.send_receipt.get("status") or ""),
        "stream": stream,
        "endpoint": endpoint,
        "semantic_reply_claim": False,
        "domain_receipt_claim": False,
        "operator_contact_note": "no reply payload was available on the recorded reply_subject",
    }


async def capture_reply_message(
    target: ReplyCaptureTarget,
    message: NatsMessageLike,
    *,
    receipt_root: Path,
    stream: str,
    endpoint: str,
) -> dict[str, Any]:
    recoverable_receipt_path = ""
    try:
        if str(message.subject) != target.reply_subject:
            receipt = {
                "schema_version": "dharma.a2a.reply_capture_receipt.v1",
                "timestamp": utc_now(),
                "status": STATUS_REPLY_SUBJECT_MISMATCH,
                "reply_evidence_tier": ACK_TIER_RED_MISMATCH,
                "contact_evidence_tier": ACK_TIER_NO_CONTACT,
                "to": target.target,
                "target_uid": str(target.send_receipt.get("target_uid") or ""),
                "packet_id": target.packet_id,
                "reply_subject": target.reply_subject,
                "message_subject": str(message.subject),
                "send_receipt_path": str(target.send_receipt_path),
                "send_status": str(target.send_receipt.get("status") or ""),
                "stream": stream,
                "endpoint": endpoint,
                "semantic_reply_claim": False,
                "domain_receipt_claim": False,
                "operator_contact_note": "reply payload subject did not match the recorded reply_subject",
            }
            await message.nak()
            receipt_path = write_reply_receipt(receipt_root, receipt)
            receipt["receipt_path"] = str(receipt_path)
            return receipt
        payload, payload_sha = _payload_from_message(message)
        domain_receipted = _is_domain_receipt(payload)
        semantic_reply_claim = (
            bool(payload.get("semantic_reply_claim") or payload.get("peer_model_processed_claim"))
            if domain_receipted
            else False
        )
        status = STATUS_DOMAIN_RECEIPTED if domain_receipted else STATUS_REPLY_CAPTURED
        receipt = {
            "schema_version": "dharma.a2a.reply_capture_receipt.v1",
            "timestamp": utc_now(),
            "status": status,
            "reply_evidence_tier": status,
            "contact_evidence_tier": (
                ACK_TIER_DOMAIN_RECEIPTED if domain_receipted else ACK_TIER_HANDLER_ACKED
            ),
            "to": target.target,
            "target_uid": str(target.send_receipt.get("target_uid") or ""),
            "packet_id": target.packet_id,
            "reply_subject": target.reply_subject,
            "send_receipt_path": str(target.send_receipt_path),
            "send_status": str(target.send_receipt.get("status") or ""),
            "stream": stream,
            "endpoint": endpoint,
            "message_subject": str(message.subject),
            "reply_payload_sha256": payload_sha,
            "reply_payload": payload,
            "reply_schema": _schema(payload),
            "semantic_reply_claim": semantic_reply_claim,
            "domain_receipt_claim": domain_receipted,
            "operator_contact_note": (
                "typed domain receipt captured; semantic_reply_claim follows payload"
                if domain_receipted
                else "untyped reply_subject payload captured; this is not semantic collaboration"
            ),
        }
        receipt = commit_reply_receipt(receipt_root, receipt)
        recoverable_receipt_path = str(receipt["receipt_path"])
        await message.ack()
    except Exception as exc:
        try:
            await message.nak()
        except Exception:
            pass
        receipt = {
            "schema_version": "dharma.a2a.reply_capture_receipt.v1",
            "timestamp": utc_now(),
            "status": STATUS_REPLY_CAPTURE_FAILED,
            "reply_evidence_tier": ACK_TIER_NO_CONTACT,
            "contact_evidence_tier": ACK_TIER_NO_CONTACT,
            "to": target.target,
            "packet_id": target.packet_id,
            "reply_subject": target.reply_subject,
            "send_receipt_path": str(target.send_receipt_path),
            "stream": stream,
            "endpoint": endpoint,
            "semantic_reply_claim": False,
            "domain_receipt_claim": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        if recoverable_receipt_path:
            receipt["recoverable_receipt_path"] = recoverable_receipt_path
            receipt["operator_contact_note"] = (
                "reply receipt was durably committed, but source broker ACK failed; "
                "redelivery will reuse the committed receipt"
            )
            return receipt
    if receipt.get("receipt_path"):
        return receipt
    receipt_path = write_reply_receipt(receipt_root, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return receipt


async def capture_target_once(
    target: ReplyCaptureTarget,
    *,
    receipt_root: Path,
    endpoint: str,
    stream: str,
    timeout_s: float,
) -> dict[str, Any]:
    try:
        import nats
        from nats.errors import TimeoutError as NatsTimeoutError
    except ModuleNotFoundError as exc:
        if getattr(exc, "name", "") != "nats":
            raise
        receipt = {
            "schema_version": "dharma.a2a.reply_capture_receipt.v1",
            "timestamp": utc_now(),
            "status": STATUS_NATS_CLIENT_MISSING,
            "reply_evidence_tier": ACK_TIER_NO_CONTACT,
            "contact_evidence_tier": ACK_TIER_NO_CONTACT,
            "to": target.target,
            "packet_id": target.packet_id,
            "reply_subject": target.reply_subject,
            "send_receipt_path": str(target.send_receipt_path),
            "stream": stream,
            "endpoint": endpoint,
            "semantic_reply_claim": False,
            "domain_receipt_claim": False,
            "error": "nats-py is not installed in this Python environment",
        }
        receipt_path = write_reply_receipt(receipt_root, receipt)
        receipt["receipt_path"] = str(receipt_path)
        return receipt

    nc = await nats.connect(servers=[endpoint], allow_reconnect=False, max_reconnect_attempts=0)
    try:
        js = nc.jetstream()
        sub = await js.pull_subscribe(
            target.reply_subject,
            durable=reply_consumer_name(target.reply_subject),
            stream=stream,
        )
        try:
            messages = await sub.fetch(1, timeout=timeout_s)
        except NatsTimeoutError:
            messages = []
        if not messages:
            receipt = no_reply_receipt(target, stream=stream, endpoint=endpoint)
            receipt_path = write_reply_receipt(receipt_root, receipt)
            receipt["receipt_path"] = str(receipt_path)
            return receipt
        return await capture_reply_message(
            target,
            messages[0],
            receipt_root=receipt_root,
            stream=stream,
            endpoint=endpoint,
        )
    finally:
        await nc.close()


def _target_from_args(args: argparse.Namespace) -> ReplyCaptureTarget:
    if args.send_receipt:
        path = Path(args.send_receipt).expanduser().resolve()
        receipt = _read_json(path)
        reply_subject = str(receipt.get("reply_subject") or args.reply_subject or "")
        if not reply_subject:
            raise ValueError("send receipt does not contain reply_subject")
        return ReplyCaptureTarget(
            send_receipt_path=path,
            send_receipt=receipt,
            reply_subject=reply_subject,
            packet_id=str(receipt.get("packet_id") or args.packet_id or path.stem),
            target=str(receipt.get("to") or receipt.get("target_uid") or args.target or "unknown"),
        )
    if not args.reply_subject or not args.packet_id:
        raise ValueError("--reply-subject and --packet-id are required without --send-receipt")
    return ReplyCaptureTarget(
        send_receipt_path=Path(""),
        send_receipt={
            "packet_id": args.packet_id,
            "reply_subject": args.reply_subject,
            "to": args.target or "unknown",
        },
        reply_subject=args.reply_subject,
        packet_id=args.packet_id,
        target=args.target or "unknown",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--send-receipt", default="", help="specific A2A send receipt JSON")
    parser.add_argument("--reply-subject", default="", help="reply subject when no send receipt is used")
    parser.add_argument("--packet-id", default="")
    parser.add_argument("--target", default="")
    parser.add_argument("--send-receipt-root", default=str(DEFAULT_SEND_RECEIPT_ROOT))
    parser.add_argument("--receipt-root", default=str(DEFAULT_REPLY_RECEIPT_ROOT))
    parser.add_argument("--endpoint", default="nats://127.0.0.1:4222")
    parser.add_argument("--stream", default=DEFAULT_COMPATIBILITY_STREAM)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.send_receipt or args.reply_subject:
            targets = [_target_from_args(args)]
        else:
            targets = pending_reply_targets(
                args.send_receipt_root,
                target=args.target,
                limit=max(args.limit, 1),
            )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    receipts: list[dict[str, Any]] = []
    for target in targets:
        receipts.append(
            asyncio.run(
                capture_target_once(
                    target,
                    receipt_root=Path(args.receipt_root),
                    endpoint=args.endpoint,
                    stream=args.stream,
                    timeout_s=max(args.timeout, 0.1),
                )
            )
        )
    if not targets:
        print("NO_PENDING_REPLY_TARGETS")
        return 0
    if args.json:
        print(json.dumps(receipts, indent=2, sort_keys=True))
    else:
        for receipt in receipts:
            print(
                f"{receipt['status']} packet_id={receipt['packet_id']} "
                f"reply_subject={receipt['reply_subject']}"
            )
            print(f"receipt: {receipt['receipt_path']}")
    if any(receipt["status"] == STATUS_REPLY_CAPTURE_FAILED for receipt in receipts):
        return 1
    if any(receipt["status"] == STATUS_NATS_CLIENT_MISSING for receipt in receipts):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
