"""Real JetStream live-contact verifier.

This is the implementation the governance probe deferred: it performs an actual
JetStream publish (and best-effort consumer ack) round-trip and only reports
``ack_verified=True`` when a live broker acknowledged a real message. A bare TCP
listener cannot satisfy this — it must speak the NATS protocol and JetStream
must return a publish ack on the message's own stream/sequence.

nats-py is an OPTIONAL dependency: it is imported lazily inside the verifier so
that merely importing this module (or running the stdlib-only governance probe)
never requires it. If it is absent, verification degrades honestly to
``ack_verified=False`` with a clear reason — it never fakes success.

Ack tiers follow docs/specs/GO_IDEA_SPARK_INGEST_SPINE_MASTER_BUILD.md:
``PUBLISH_ACCEPTED`` (JetStream stored the publish) upgrades to
``DELIVERED_TO_CONSUMER`` when a durable consumer reads the same payload back.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import socket
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def resolve_endpoint(endpoint: str | None = None) -> str:
    return (
        endpoint
        or os.environ.get("DHARMA_NATS_URL")
        or os.environ.get("NATS_URL")
        or "nats://127.0.0.1:4222"
    )


async def _round_trip(endpoint: str, timeout: float) -> dict[str, Any]:
    import nats  # lazy: optional dependency
    from nats.js.api import StorageType, StreamConfig

    token = uuid.uuid4().hex[:10]
    subject = f"_dharma_live_probe.{token}.ping"
    stream_name = f"DHARMA_LIVE_PROBE_{token}"
    payload = f"live-{token}".encode()

    nc = await nats.connect(
        servers=[endpoint],
        connect_timeout=timeout,
        allow_reconnect=False,
        max_reconnect_attempts=0,
    )
    try:
        js = nc.jetstream()
        await js.add_stream(
            StreamConfig(
                name=stream_name,
                subjects=[f"_dharma_live_probe.{token}.>"],
                storage=StorageType.MEMORY,
                max_msgs=16,
            )
        )
        pub_ack = await js.publish(subject, payload, timeout=timeout)
        result: dict[str, Any] = {
            "ack_verified": True,
            "code": "NATS_LIVE",
            "ack_tier": "PUBLISH_ACCEPTED",
            "stream": pub_ack.stream,
            "seq": pub_ack.seq,
            "verified_by": "nats_live_contact",
        }
        try:
            sub = await js.pull_subscribe(subject, durable=f"probe_{token}", stream=stream_name)
            msgs = await sub.fetch(1, timeout=timeout)
            if msgs and msgs[0].data == payload:
                await msgs[0].ack()
                result["ack_tier"] = "DELIVERED_TO_CONSUMER"
        except Exception as exc:  # publish ack already proves a live broker
            result["consumer_note"] = f"consumer read skipped: {exc}"
        try:
            await js.delete_stream(stream_name)
        except Exception:
            pass
        return result
    finally:
        try:
            await nc.close()
        except Exception:
            pass


def verify_jetstream_contact(endpoint: str | None = None, *, timeout: float = 2.0) -> dict[str, Any]:
    """Return a live-contact proof dict. Honest by construction: only a real
    JetStream publish ack yields ``ack_verified=True``.
    """

    configured = resolve_endpoint(endpoint)
    started = time.monotonic()

    if importlib.util.find_spec("nats") is None:
        return {
            "ack_verified": False,
            "code": "NATS_CLIENT_MISSING",
            "reason": "nats-py is not installed; `pip install nats-py` to verify live contact",
            "endpoint": configured,
        }

    # Fast stdlib reachability gate: never hand an unreachable endpoint to the
    # async client (a refused/black-holed port can otherwise stall the connect).
    parsed = urlparse(configured)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 4222
    try:
        socket.create_connection((host, port), timeout=min(timeout, 1.0)).close()
    except OSError as exc:
        return {
            "ack_verified": False,
            "code": "NATS_UNAVAILABLE",
            "reason": f"no TCP listener at {host}:{port}: {exc}",
            "endpoint": configured,
        }

    async def _bounded() -> dict[str, Any]:
        return await asyncio.wait_for(
            _round_trip(configured, timeout), timeout=max(timeout * 2.0, timeout + 2.0)
        )

    try:
        result = asyncio.run(_bounded())
    except RuntimeError as exc:
        # e.g. called from within a running event loop
        return {
            "ack_verified": False,
            "code": "NATS_ACK_FAILED",
            "reason": f"event loop unavailable for sync verify: {exc}",
            "endpoint": configured,
        }
    except Exception as exc:
        return {
            "ack_verified": False,
            "code": "NATS_ACK_FAILED",
            "reason": f"JetStream round-trip failed or timed out: {exc}",
            "endpoint": configured,
        }

    rtt_ms = round((time.monotonic() - started) * 1000)
    result["endpoint"] = configured
    result["rtt_ms"] = rtt_ms
    tier = result.get("ack_tier", "PUBLISH_ACCEPTED")
    result["reason"] = (
        f"JetStream {tier} ack verified: stream={result.get('stream')} "
        f"seq={result.get('seq')} rtt={rtt_ms}ms"
    )
    return result


DEFAULT_RECEIPT_PATH = Path.home() / ".dharma" / "a2a_bus" / "nats_live_receipt.json"


def resolve_receipt_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path).expanduser()
    env = os.environ.get("DHARMA_NATS_RECEIPT")
    return Path(env).expanduser() if env else DEFAULT_RECEIPT_PATH


def write_live_receipt(
    path: str | Path | None = None, *, endpoint: str | None = None, timeout: float = 2.0
) -> dict[str, Any]:
    """Run a real verification and persist the result as a fresh receipt.

    Intended to run on an interval (launchd/cron) so operator surfaces can report
    live NATS contact without a network round-trip on every render. Atomic write.
    """
    result = verify_jetstream_contact(endpoint, timeout=timeout)
    result["ts"] = datetime.now(timezone.utc).isoformat()
    target = resolve_receipt_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result), encoding="utf-8")
    tmp.replace(target)
    return result


def read_live_receipt(
    path: str | Path | None = None, *, max_age_s: float = 120.0
) -> dict[str, Any] | None:
    """Return the receipt dict iff it exists, is ack-verified, and is fresh."""
    target = resolve_receipt_path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("ack_verified"):
        return None
    try:
        when = datetime.fromisoformat(str(data.get("ts")))
    except (TypeError, ValueError):
        return None
    age = (datetime.now(timezone.utc) - when).total_seconds()
    if age > max_age_s:
        return None
    data["receipt_age_s"] = round(age, 1)
    return data


def _main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="NATS live-contact verifier / receipt writer")
    parser.add_argument("--write-receipt", action="store_true", help="verify and persist a fresh receipt")
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args(argv)
    if args.write_receipt:
        result = write_live_receipt(endpoint=args.endpoint, timeout=args.timeout)
    else:
        result = verify_jetstream_contact(args.endpoint, timeout=args.timeout)
    print(json.dumps(result))
    return 0 if result.get("ack_verified") else 1


if __name__ == "__main__":
    raise SystemExit(_main())
