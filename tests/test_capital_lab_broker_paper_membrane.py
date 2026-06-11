from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.capital_lab.broker_paper_membrane import (
    BROKER_WRITE_AUTHORITY,
    CLEAN,
    LIVE_AUTHORITY,
    LIVE_READINESS,
    AuthorityFence,
    BrokerPaperMembrane,
    BrokerSnapshotOrder,
    OrderIntent,
    build_client_order_id,
    run_goal_b_proof_loop,
    run_kill_switch_drills,
)


def test_authority_fence_blocks_live_imports_and_calls(tmp_path: Path) -> None:
    source = tmp_path / "bad_adapter.py"
    source.write_text(
        "\n".join(
            [
                "import hyperliquid",
                "",
                "def route(exchange):",
                "    return exchange.place_buy_order('BTC', 1)",
            ]
        ),
        encoding="utf-8",
    )

    receipt = AuthorityFence().scan_python_sources([source])

    assert receipt.passed is False
    assert "hyperliquid" in receipt.denied_imports
    assert "place_buy_order" in receipt.denied_calls
    assert receipt.live_readiness == 0
    assert receipt.live_authority is False


def test_lifecycle_receipts_cover_submit_ack_partial_full_cancel_reject_expire(
    tmp_path: Path,
) -> None:
    adapter = BrokerPaperMembrane(ledger_path=tmp_path / "ledger.json")

    full_id = build_client_order_id("s", "AAPL", "buy", 10, "full")
    adapter.submit(OrderIntent(full_id, "aapl", "buy", "limit", 10, limit_price=100))
    adapter.ack(full_id)
    adapter.partial_fill(full_id, 4)
    adapter.full_fill(full_id)

    cancel_id = build_client_order_id("s", "MSFT", "sell", 2, "cancel")
    adapter.submit(OrderIntent(cancel_id, "MSFT", "sell", "limit", 2, limit_price=500))
    adapter.ack(cancel_id)
    adapter.cancel(cancel_id)

    reject_id = build_client_order_id("s", "TSLA", "buy", 1, "reject")
    adapter.submit(OrderIntent(reject_id, "TSLA", "buy", "limit", 1, limit_price=200))
    adapter.reject(reject_id, "fixture rejection")

    expire_id = build_client_order_id("s", "NVDA", "buy", 3, "expire")
    adapter.submit(OrderIntent(expire_id, "NVDA", "buy", "limit", 3, limit_price=140))
    adapter.ack(expire_id)
    adapter.expire(expire_id)

    event_types = {receipt.event_type for receipt in adapter.ledger.receipts}
    assert event_types == {
        "submit",
        "ack",
        "partial_fill",
        "full_fill",
        "cancel",
        "reject",
        "expire",
    }
    assert adapter.ledger.orders[full_id].terminal is True
    assert adapter.ledger.orders[full_id].status == "filled"
    with pytest.raises(ValueError, match="terminal order cannot be reopened"):
        adapter.cancel(full_id)


def test_duplicate_client_order_id_is_idempotent_across_replay(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    client_order_id = build_client_order_id("strategy", "AAPL", "buy", 1, "same")
    intent = OrderIntent(client_order_id, "AAPL", "buy", "market", 1)
    adapter = BrokerPaperMembrane(ledger_path=ledger_path)

    _, first_receipt, duplicate = adapter.submit(intent)
    _, second_receipt, duplicate_again = adapter.submit(intent)
    replayed = BrokerPaperMembrane(ledger_path=ledger_path)
    _, replay_receipt, duplicate_after_replay = replayed.submit(intent)

    assert first_receipt is not None
    assert duplicate is False
    assert second_receipt is None
    assert duplicate_again is True
    assert replay_receipt is None
    assert duplicate_after_replay is True
    assert len(replayed.ledger.orders) == 1
    assert len(replayed.ledger.receipts) == 1


def test_reconciliation_blocks_on_field_level_mismatch(tmp_path: Path) -> None:
    adapter = BrokerPaperMembrane(ledger_path=tmp_path / "ledger.json")
    client_order_id = build_client_order_id("s", "AAPL", "buy", 5, "recon")
    adapter.submit(OrderIntent(client_order_id, "AAPL", "buy", "limit", 5, limit_price=100))
    adapter.ack(client_order_id)

    matched = adapter.reconcile(adapter.ledger.snapshot())
    mismatch_snapshot = adapter.ledger.snapshot()
    mismatch_snapshot[0] = BrokerSnapshotOrder(
        **{
            **mismatch_snapshot[0].to_dict(),
            "status": "filled",
            "terminal": True,
        }
    )
    mismatched = adapter.reconcile(mismatch_snapshot)

    assert matched.readiness_blocked is False
    assert matched.kill_switch_engaged is False
    assert mismatched.readiness_blocked is True
    assert mismatched.kill_switch_engaged is True
    assert {item["field"] for item in mismatched.mismatches} == {"status", "terminal"}
    assert adapter.kill_switch_engaged is True


def test_reconciliation_mismatch_actually_blocks_next_order(tmp_path: Path) -> None:
    """A tripped reconciliation kill-switch must ENFORCE: the next submit is
    refused. (Previously the 'block' was a flag no code path read.)"""
    from dharma_swarm.capital_lab.risk_governor import RiskHalt

    adapter = BrokerPaperMembrane(ledger_path=tmp_path / "ledger.json")
    cid = build_client_order_id("s", "AAPL", "buy", 5, "recon")
    adapter.submit(OrderIntent(cid, "AAPL", "buy", "limit", 5, limit_price=100))
    adapter.ack(cid)

    mismatch = adapter.ledger.snapshot()
    mismatch[0] = BrokerSnapshotOrder(
        **{**mismatch[0].to_dict(), "status": "filled", "terminal": True}
    )
    adapter.reconcile(mismatch)
    assert adapter.risk_governor.engaged is True

    new_id = build_client_order_id("s", "MSFT", "buy", 1, "after-halt")
    with pytest.raises(RiskHalt):
        adapter.submit(OrderIntent(new_id, "MSFT", "buy", "market", 1))


def test_pre_trade_gate_blocks_order_rate_breach(tmp_path: Path) -> None:
    from dharma_swarm.capital_lab.risk_governor import RiskGovernor, RiskHalt, RiskLimits

    gov = RiskGovernor(RiskLimits(max_orders_per_window=2, rate_window_seconds=1000.0))
    adapter = BrokerPaperMembrane(ledger_path=tmp_path / "ledger.json", risk_governor=gov)
    adapter.submit(OrderIntent(build_client_order_id("s", "AAPL", "buy", 1, "a"),
                               "AAPL", "buy", "market", 1))
    adapter.submit(OrderIntent(build_client_order_id("s", "MSFT", "buy", 1, "b"),
                               "MSFT", "buy", "market", 1))
    with pytest.raises(RiskHalt):
        adapter.submit(OrderIntent(build_client_order_id("s", "TSLA", "buy", 1, "c"),
                                   "TSLA", "buy", "market", 1))


def test_kill_switch_drills_preserve_false_zero_authority_fields() -> None:
    drills = run_kill_switch_drills()

    assert set(drills) == {
        "heartbeat_kill_switch",
        "stale_data_kill_switch",
        "max_loss_or_drawdown_kill_switch",
        "order_rate_or_exposure_kill_switch",
    }
    assert all(receipt["passed"] for receipt in drills.values())
    assert all(receipt["kill_switch_engaged"] for receipt in drills.values())
    assert all(receipt["live_readiness"] == LIVE_READINESS for receipt in drills.values())
    assert all(receipt["live_authority"] is LIVE_AUTHORITY for receipt in drills.values())
    assert all(
        receipt["broker_write_authority"] is BROKER_WRITE_AUTHORITY
        for receipt in drills.values()
    )
    assert all(receipt["clean"] is CLEAN for receipt in drills.values())


def test_goal_b_proof_loop_emits_blocked_fixture_packets(tmp_path: Path) -> None:
    result = run_goal_b_proof_loop(tmp_path)

    readiness = result["adapter_readiness_packet"]
    feasibility = result["execution_feasibility_packet"]
    manifest = result["manifest"]

    assert readiness["live_readiness"] == 0
    assert readiness["live_authority"] is False
    assert readiness["broker_write_authority"] is False
    assert readiness["clean"] is False
    assert readiness["fixture_or_internal_only"] is True
    assert readiness["external_broker_paper_evidence"] is False
    assert all(readiness["lifecycle_events_supported"].values())
    assert readiness["idempotent_client_order_ids"] is True
    assert readiness["duplicate_prevention_available"] is True

    assert feasibility["score"] == 80.0
    assert feasibility["live_readiness"] == 0
    assert feasibility["external_broker_paper_evidence"] is False
    assert feasibility["fixture_or_internal_only"] is True
    assert feasibility["drills"]["reconciliation_mismatch_blocks"] is True
    assert feasibility["drills"]["order_rate_or_exposure_kill_switch"] is True
    assert manifest["local_loop_passed"] is True

    expected_files = {
        "adapter_readiness_packet.json",
        "authority_fence_receipts.json",
        "builder_manifest.json",
        "builder_report.md",
        "duplicate_order_drill.json",
        "execution_feasibility_packet.json",
        "kill_switch_drills.json",
        "lifecycle_receipts.json",
        "matched_reconciliation_packet.json",
        "mismatch_reconciliation_packet.json",
    }
    assert expected_files <= {path.name for path in tmp_path.iterdir()}
