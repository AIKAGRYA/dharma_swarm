"""NATS substrate status projection for operator-facing readiness claims.

This module is stdlib-only at import time and for the default probe: it proves
only that a TCP listener exists and never claims liveness from an open port.
When called with ``verify_ack=True`` it delegates to the optional
``nats_live_contact`` verifier for a real JetStream publish/consumer ack — that
path lazily imports nats-py and is the only way ``ack_verified`` becomes True.
"""

from __future__ import annotations

import socket
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SPEC_PATH = Path("docs/specs/GO_IDEA_SPARK_INGEST_SPINE_MASTER_BUILD.md")


@dataclass(frozen=True)
class NatsSubstrateStatus:
    available: bool
    code: str
    reason: str
    spec_path: str
    endpoint: str
    port_4222_listening: bool
    ack_verified: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tcp_listening(host: str, port: int, *, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_nats_substrate(
    *,
    host: str | None = None,
    port: int | None = None,
    endpoint: str | None = None,
    spec_path: Path = SPEC_PATH,
    verify_ack: bool = False,
    receipt_path: Path | str | None = None,
    trust_fresh_receipt: bool = False,
) -> NatsSubstrateStatus:
    """Return claim-safe NATS status.

    A port listener is not a live-contact proof. With ``verify_ack=True`` a real
    JetStream publish/consumer round-trip is attempted via the optional
    ``nats_live_contact`` verifier, and ``ack_verified`` is set True only on a
    genuine broker ack. Default False keeps this probe stdlib-only and
    offline-safe (it never claims liveness from a bare open port).
    """

    configured = endpoint or os.environ.get("DHARMA_NATS_URL") or os.environ.get("NATS_URL") or "nats://127.0.0.1:4222"
    parsed = urlparse(configured)
    probe_host = host or parsed.hostname or "127.0.0.1"
    probe_port = port or parsed.port or 4222

    if trust_fresh_receipt:
        try:
            from dharma_swarm.operator_core.nats_live_contact import read_live_receipt

            receipt = read_live_receipt(receipt_path)
        except Exception:  # pragma: no cover - defensive status surface
            receipt = None
        if receipt and receipt.get("ack_verified"):
            return NatsSubstrateStatus(
                available=True,
                code="NATS_LIVE",
                reason=str(receipt.get("reason") or "JetStream ack verified")
                + f" [live receipt age {receipt.get('receipt_age_s', '?')}s]",
                spec_path=str(spec_path),
                endpoint=configured,
                port_4222_listening=True,
                ack_verified=True,
            )

    port_open = _tcp_listening(probe_host, probe_port)
    if not port_open:
        return NatsSubstrateStatus(
            available=False,
            code="NATS_UNAVAILABLE",
            reason=f"no TCP listener on {probe_host}:{probe_port}; filesystem mirrors are not live-contact proof",
            spec_path=str(spec_path),
            endpoint=configured,
            port_4222_listening=False,
            ack_verified=False,
        )

    if not verify_ack and os.environ.get("DHARMA_NATS_VERIFY", "").strip().lower() in ("1", "true", "yes", "on"):
        try:
            from dharma_swarm.operator_core.nats_live_contact import read_live_receipt

            receipt = read_live_receipt()
        except Exception:  # pragma: no cover - defensive
            receipt = None
        if receipt and receipt.get("ack_verified"):
            return NatsSubstrateStatus(
                available=True,
                code="NATS_LIVE",
                reason=str(receipt.get("reason") or "JetStream ack verified")
                + f" [live receipt age {receipt.get('receipt_age_s', '?')}s]",
                spec_path=str(spec_path),
                endpoint=configured,
                port_4222_listening=True,
                ack_verified=True,
            )

    if verify_ack:
        try:
            from dharma_swarm.operator_core.nats_live_contact import verify_jetstream_contact

            result = verify_jetstream_contact(configured)
        except Exception as exc:  # pragma: no cover - defensive
            result = {"ack_verified": False, "code": "NATS_ACK_FAILED", "reason": f"verifier error: {exc}"}
        if result.get("ack_verified"):
            return NatsSubstrateStatus(
                available=True,
                code="NATS_LIVE",
                reason=str(result.get("reason") or "JetStream publish/consumer ack verified"),
                spec_path=str(spec_path),
                endpoint=configured,
                port_4222_listening=True,
                ack_verified=True,
            )
        return NatsSubstrateStatus(
            available=False,
            code=str(result.get("code") or "NATS_ACK_UNVERIFIED"),
            reason=str(result.get("reason") or "TCP listener exists, but JetStream ack is not verified"),
            spec_path=str(spec_path),
            endpoint=configured,
            port_4222_listening=True,
            ack_verified=False,
        )

    return NatsSubstrateStatus(
        available=False,
        code="NATS_ACK_UNVERIFIED",
        reason="TCP listener exists, but JetStream publish/consumer ack is not verified",
        spec_path=str(spec_path),
        endpoint=configured,
        port_4222_listening=True,
        ack_verified=False,
    )
