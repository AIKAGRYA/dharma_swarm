"""Tests for the real JetStream live-contact verifier.

These are offline-safe: they assert the verifier degrades HONESTLY (never fakes
``ack_verified``) when no broker is reachable. The real publish/consumer ack
round-trip against a live server is exercised in the operator demo, not here.
"""

from __future__ import annotations

import pytest

from dharma_swarm.operator_core.nats_live_contact import (
    resolve_endpoint,
    verify_jetstream_contact,
)
from dharma_swarm.operator_core.nats_substrate_status import probe_nats_substrate


def test_resolve_endpoint_prefers_explicit() -> None:
    assert resolve_endpoint("nats://example:9999") == "nats://example:9999"


def test_resolve_endpoint_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.delenv("DHARMA_NATS_URL", raising=False)
    monkeypatch.delenv("NATS_URL", raising=False)
    assert resolve_endpoint() == "nats://127.0.0.1:4222"


def test_verify_jetstream_contact_unreachable_is_honest() -> None:
    result = verify_jetstream_contact(endpoint="nats://127.0.0.1:1", timeout=0.5)
    assert result["ack_verified"] is False
    assert result["code"] in {"NATS_UNAVAILABLE", "NATS_ACK_FAILED", "NATS_CLIENT_MISSING"}


def test_probe_verify_ack_blocks_when_unreachable() -> None:
    status = probe_nats_substrate(endpoint="nats://127.0.0.1:1", verify_ack=True).to_dict()
    assert status["available"] is False
    assert status["ack_verified"] is False


def _fresh_receipt(path, *, ack=True, age_s=0):
    import json
    from datetime import datetime, timedelta, timezone

    ts = (datetime.now(timezone.utc) - timedelta(seconds=age_s)).isoformat()
    path.write_text(
        json.dumps({"ack_verified": ack, "code": "NATS_LIVE", "reason": "verified", "ts": ts}),
        encoding="utf-8",
    )


def test_read_live_receipt_accepts_fresh_verified(tmp_path) -> None:
    from dharma_swarm.operator_core.nats_live_contact import read_live_receipt

    receipt = tmp_path / "r.json"
    _fresh_receipt(receipt, ack=True, age_s=0)
    got = read_live_receipt(receipt, max_age_s=120)
    assert got is not None and got["ack_verified"] is True


def test_read_live_receipt_rejects_stale(tmp_path) -> None:
    from dharma_swarm.operator_core.nats_live_contact import read_live_receipt

    receipt = tmp_path / "r.json"
    _fresh_receipt(receipt, ack=True, age_s=600)
    assert read_live_receipt(receipt, max_age_s=120) is None


def test_probe_reports_live_from_fresh_receipt_when_port_open(tmp_path, monkeypatch) -> None:
    import socket

    srv = socket.socket()
    try:
        srv.bind(("127.0.0.1", 0))
    except PermissionError:
        srv.close()
        pytest.skip("local socket bind blocked in this sandbox")
    srv.listen(1)
    port = srv.getsockname()[1]
    receipt = tmp_path / "r.json"
    _fresh_receipt(receipt, ack=True, age_s=0)
    monkeypatch.setenv("DHARMA_NATS_VERIFY", "1")
    monkeypatch.setenv("DHARMA_NATS_RECEIPT", str(receipt))
    try:
        status = probe_nats_substrate(endpoint=f"nats://127.0.0.1:{port}").to_dict()
    finally:
        srv.close()
    assert status["ack_verified"] is True
    assert status["code"] == "NATS_LIVE"


def test_probe_can_trust_explicit_fresh_receipt_without_env(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DHARMA_NATS_VERIFY", raising=False)
    receipt = tmp_path / "r.json"
    _fresh_receipt(receipt, ack=True, age_s=0)

    status = probe_nats_substrate(
        endpoint="nats://127.0.0.1:1",
        receipt_path=receipt,
        trust_fresh_receipt=True,
    ).to_dict()

    assert status["available"] is True
    assert status["ack_verified"] is True
    assert status["code"] == "NATS_LIVE"
