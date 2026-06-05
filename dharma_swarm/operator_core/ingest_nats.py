"""Optional NATS hot transport for ingest receipts.

Receipt files remain authoritative replay truth. This module only projects
already-written receipt files onto NATS when explicitly enabled and when the
existing NATS verifier has ack proof.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from dharma_swarm.operator_core.nats_substrate_status import probe_nats_substrate


SCHEMA_VERSION = "dharma_ingest_nats_projection.v1"
DEFAULT_SUBJECT = "dharma.ingest.receipts.world_signal"
DEFAULT_STREAM = "DHARMA_INGEST_RECEIPTS"


ProbeFn = Callable[..., Any]
PublisherFn = Callable[..., list[dict[str, Any]]]


def publish_ingest_receipts_if_enabled(
    receipt_dir: Path | str,
    correlation_id: str,
    *,
    env: dict[str, str] | None = None,
    endpoint: str | None = None,
    subject: str = DEFAULT_SUBJECT,
    probe: ProbeFn = probe_nats_substrate,
    publisher: PublisherFn | None = None,
    timeout: float = 2.0,
) -> dict[str, Any]:
    """Project one ingest run's receipts to NATS when explicitly enabled.

    ``DHARMA_INGEST_NATS=1`` is required. Without it this function does not
    probe NATS, import nats-py, or open a socket.
    """

    started = time.monotonic()
    effective_env = os.environ if env is None else env
    if str(effective_env.get("DHARMA_INGEST_NATS", "")).strip().lower() not in {"1", "true", "yes", "on"}:
        return _base_status(
            enabled=False,
            status="disabled",
            ack_status="unavailable",
            correlation_id=correlation_id,
            subject=subject,
            started=started,
            reason="DHARMA_INGEST_NATS is not enabled",
        )

    nats_status = _status_dict(
        probe(
            endpoint=endpoint,
            verify_ack=True,
            trust_fresh_receipt=True,
        )
    )
    ack_status = _ack_status(nats_status)
    status = _base_status(
        enabled=True,
        status=ack_status,
        ack_status=ack_status,
        correlation_id=correlation_id,
        subject=subject,
        started=started,
        reason=str(nats_status.get("reason") or ""),
    )
    status["nats_substrate"] = nats_status
    if ack_status != "ack_verified":
        status["publish_status"] = "not_attempted"
        return status

    payloads = _receipt_payloads(Path(receipt_dir), correlation_id)
    status["attempted_count"] = len(payloads)
    status["receipt_ids"] = [str(item.get("receipt_id") or "") for item in payloads if item.get("receipt_id")][:100]
    if not payloads:
        status["publish_status"] = "no_receipts"
        status["published_count"] = 0
        return status

    publish = publisher or _publish_payloads_sync
    try:
        acknowledgements = publish(
            payloads=payloads,
            endpoint=str(nats_status.get("endpoint") or endpoint or ""),
            subject=subject,
            timeout=timeout,
        )
    except Exception as exc:
        status["status"] = "publish_failed"
        status["publish_status"] = "failed"
        status["published_count"] = 0
        status["error"] = str(exc)[:1000]
        return status
    status["status"] = "ack_verified"
    status["publish_status"] = "published"
    status["published_count"] = len(acknowledgements)
    status["publish_acks"] = acknowledgements[:100]
    return status


def _base_status(
    *,
    enabled: bool,
    status: str,
    ack_status: str,
    correlation_id: str,
    subject: str,
    started: float,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "enabled": enabled,
        "status": status,
        "ack_status": ack_status,
        "transport": "nats_jetstream",
        "authority": "receipt_files_remain_authoritative",
        "correlation_id": correlation_id,
        "subject": subject,
        "attempted_count": 0,
        "published_count": 0,
        "publish_status": "not_attempted",
        "reason": reason,
        "duration_s": round(time.monotonic() - started, 3),
    }


def _status_dict(status: Any) -> dict[str, Any]:
    if hasattr(status, "to_dict"):
        value = status.to_dict()
    else:
        value = status
    return value if isinstance(value, dict) else {}


def _ack_status(status: dict[str, Any]) -> str:
    if status.get("ack_verified"):
        return "ack_verified"
    if status.get("port_4222_listening"):
        return "ack_unverified"
    return "unavailable"


def _receipt_payloads(receipt_dir: Path, correlation_id: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    if not receipt_dir.exists():
        return payloads
    for path in sorted(receipt_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("correlation_id") or "") != correlation_id:
            continue
        payload = dict(payload)
        payload["receipt_path"] = str(path)
        payloads.append(payload)
    return payloads


def _publish_payloads_sync(
    *,
    payloads: Iterable[dict[str, Any]],
    endpoint: str,
    subject: str,
    timeout: float,
) -> list[dict[str, Any]]:
    if importlib.util.find_spec("nats") is None:
        raise RuntimeError("NATS_CLIENT_MISSING: nats-py is not installed")
    return asyncio.run(_publish_payloads_async(payloads=payloads, endpoint=endpoint, subject=subject, timeout=timeout))


async def _publish_payloads_async(
    *,
    payloads: Iterable[dict[str, Any]],
    endpoint: str,
    subject: str,
    timeout: float,
) -> list[dict[str, Any]]:
    import nats
    from nats.js.api import StorageType, StreamConfig

    stream = os.environ.get("DHARMA_INGEST_NATS_STREAM") or DEFAULT_STREAM
    subject_root = ".".join(subject.split(".")[:-1]) or subject
    nc = await nats.connect(
        servers=[endpoint],
        connect_timeout=timeout,
        allow_reconnect=False,
        max_reconnect_attempts=0,
    )
    try:
        js = nc.jetstream()
        try:
            await js.add_stream(
                StreamConfig(
                    name=stream,
                    subjects=[f"{subject_root}.>"],
                    storage=StorageType.MEMORY,
                    max_msgs=10_000,
                )
            )
        except Exception:
            pass
        acks: list[dict[str, Any]] = []
        for payload in payloads:
            ack = await js.publish(subject, json.dumps(payload, sort_keys=True).encode("utf-8"), timeout=timeout)
            acks.append(
                {
                    "receipt_id": str(payload.get("receipt_id") or ""),
                    "ack_tier": "PUBLISH_ACCEPTED",
                    "stream": getattr(ack, "stream", ""),
                    "seq": getattr(ack, "seq", 0),
                }
            )
        return acks
    finally:
        try:
            await nc.close()
        except Exception:
            pass
