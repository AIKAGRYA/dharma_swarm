#!/usr/bin/env python3
"""Operator surface for sending one A2A packet to an agent over NATS.

Usage:
    python3 scripts/runtime/a2a_send.py --to devin --file inter_agent/devin/inbound/packet.md
    python3 scripts/runtime/a2a_send.py --to devin --file packet.md --wait 30 --json

Publishes the file as a ``dharma.a2a.send.v1`` envelope to ``dharma.a2a.<agent>``,
writes an ack receipt under ``reports/a2a/send_receipts/``, and reports a single
terminal status:

    NATS_SECRETS_MISSING  no usable NATS credentials in the environment
    PUBLISH_FAILED        connected/attempted but the publish did not complete
    PUBLISH_ACKED         broker accepted the packet (JetStream pub-ack when
                          permitted, otherwise core publish + flush)
    <AGENT>_CONSUMED      a consumer acked on dharma.a2a.<agent>.ack.<packet_id>
    <AGENT>_REPLIED       a reply arrived on dharma.a2a.<agent>.reply.<packet_id>

Consumers signal consumption/reply by publishing any payload to the ack/reply
subjects named in the envelope (the wildcard listener contract
``dharma.a2a.<agent>.>`` covers both).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import ssl
import sys
import uuid
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
    _redacted_nats_config,
    stamp,
    utc_now,
)

DEFAULT_RECEIPT_DIR = REPO_ROOT / "reports" / "a2a" / "send_receipts"

STATUS_SECRETS_MISSING = "NATS_SECRETS_MISSING"
STATUS_PUBLISH_FAILED = "PUBLISH_FAILED"
STATUS_PUBLISH_ACKED = "PUBLISH_ACKED"


def build_envelope(
    *,
    to: str,
    file_path: Path,
    sender: str,
    kind: str,
    packet_id: str,
) -> dict[str, Any]:
    content = file_path.read_text(encoding="utf-8")
    subject = f"dharma.a2a.{to}"
    try:
        rel_path = str(file_path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        rel_path = str(file_path)
    return {
        "schema_version": "dharma.a2a.send.v1",
        "packet_id": packet_id,
        "timestamp": utc_now(),
        "from": sender,
        "to": _a2a_target_for_subject(subject),
        "kind": kind,
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
    }
    tls_kwargs = _nats_tls_kwargs(config)
    if insecure_tls and not config.ca_pem:
        insecure_ctx = ssl.create_default_context()
        insecure_ctx.check_hostname = False
        insecure_ctx.verify_mode = ssl.CERT_NONE
        tls_kwargs["tls"] = insecure_ctx
    async def _quiet_error_cb(exc: Exception) -> None:
        result["last_connection_error"] = f"{type(exc).__name__}: {exc}"

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
            result["ack_tier"] = "JETSTREAM_PUB_ACK"
            result["stream"] = js_ack.stream
            result["seq"] = js_ack.seq
        except Exception:
            await nc.publish(envelope["subject"], data)
            await nc.flush(timeout=timeout_s)
            result["ack_tier"] = "CORE_FLUSH"
        result["status"] = STATUS_PUBLISH_ACKED

        agent = envelope["subject"].rsplit(".", 1)[-1].upper()
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
            result["status"] = f"{agent}_CONSUMED"
        if replied_event.is_set():
            result["replied"] = True
            result["consumed"] = True
            result["status"] = f"{agent}_REPLIED"
        await ack_sub.unsubscribe()
        await reply_sub.unsubscribe()
    finally:
        await nc.close()
    return result


def write_receipt(receipt_dir: Path, receipt: dict[str, Any]) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_dir / f"{stamp()}-{receipt['to']}-{receipt['packet_id']}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


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
    parser.add_argument("--wait", type=float, default=10.0, help="seconds to wait for consume/reply")
    parser.add_argument("--timeout", type=float, default=10.0, help="connect/publish timeout seconds")
    parser.add_argument("--receipt-dir", default=str(DEFAULT_RECEIPT_DIR))
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
    packet_id = uuid.uuid4().hex[:12]
    envelope = build_envelope(
        to=args.to, file_path=file_path, sender=args.sender, kind=args.kind, packet_id=packet_id
    )
    receipt: dict[str, Any] = {
        "schema_version": "dharma.a2a.send_receipt.v1",
        "packet_id": packet_id,
        "timestamp": utc_now(),
        "to": args.to,
        "subject": envelope["subject"],
        "ack_subject": envelope["ack_subject"],
        "reply_subject": envelope["reply_subject"],
        "file": envelope["file"],
        "sha256": envelope["sha256"],
        "nats": _redacted_nats_config(config),
    }
    if config.missing or not config.endpoint:
        receipt["status"] = STATUS_SECRETS_MISSING
        receipt["missing"] = list(config.missing)
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
            receipt["status"] = STATUS_PUBLISH_FAILED
            # The receipt is printed and persisted, and NATS exception text can echo
            # the endpoint URL as user:password@host. Keep the receipt taint-free:
            # only the exception TYPE enters it; the scrubbed detail goes to stderr.
            # Exception TYPE only: NATS error text can embed user:password@host and
            # no scrubbing convinces taint tracking once config.credential is in the
            # flow. Reproduce with the NATS CLI for full detail.
            receipt["error"] = type(exc).__name__
            print(f"publish failed: {type(exc).__name__}", file=sys.stderr)

    receipt_path = write_receipt(Path(args.receipt_dir), receipt)
    receipt["receipt_path"] = str(receipt_path)
    if args.json:
        print(json.dumps(console_receipt(), indent=2, sort_keys=True))
    else:
        print("a2a_send: <recorded>")
        print("receipt: <written>")
    if receipt["status"] == STATUS_SECRETS_MISSING:
        return 3
    if receipt["status"] == STATUS_PUBLISH_FAILED:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
