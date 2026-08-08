"""Tests for the real JetStream live-contact verifier.

These are offline-safe: they assert the verifier degrades HONESTLY (never fakes
``ack_verified``) when no broker is reachable. The real publish/consumer ack
round-trip against a live server is exercised in the operator demo, not here.
"""

from __future__ import annotations

from dharma_swarm.operator_core import nats_live_contact
from dharma_swarm.operator_core import nats_substrate_status
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


def test_verify_jetstream_contact_unreachable_is_honest(monkeypatch) -> None:
    monkeypatch.setattr(nats_live_contact.importlib.util, "find_spec", lambda _name: object())

    def _unreachable(*_args, **_kwargs):
        raise OSError("fixture endpoint unavailable")

    monkeypatch.setattr(nats_live_contact.socket, "create_connection", _unreachable)
    result = verify_jetstream_contact(endpoint="nats://127.0.0.1:1", timeout=0.5)
    assert result["ack_verified"] is False
    assert result["code"] == "NATS_UNAVAILABLE"


def test_probe_verify_ack_blocks_when_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(nats_substrate_status, "_tcp_listening", lambda *_args, **_kwargs: False)
    status = probe_nats_substrate(endpoint="nats://127.0.0.1:1", verify_ack=True).to_dict()
    assert status["available"] is False
    assert status["ack_verified"] is False
    assert status["spec_path"] == "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"


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
    receipt = tmp_path / "r.json"
    _fresh_receipt(receipt, ack=True, age_s=0)
    monkeypatch.setenv("DHARMA_NATS_VERIFY", "1")
    monkeypatch.setenv("DHARMA_NATS_RECEIPT", str(receipt))
    monkeypatch.setattr(nats_substrate_status, "_tcp_listening", lambda *_args, **_kwargs: True)

    status = probe_nats_substrate(endpoint="nats://fixture.invalid:4222").to_dict()

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
