from __future__ import annotations

import json
from pathlib import Path

from scripts.runtime.refresh_agni_watcher import (
    CommandResult,
    build_watcher_payload,
    write_watcher_outputs,
)


def test_agni_watcher_payload_is_read_only_and_preserves_blockers() -> None:
    snapshot = {
        "files": {
            "data/dashboard_snapshot.json": {
                "path": "data/dashboard_snapshot.json",
                "exists": True,
                "fresh": False,
                "age_s": 4000,
                "max_age_s": 1800,
            },
            "data/market_snapshot.json": {
                "path": "data/market_snapshot.json",
                "exists": True,
                "fresh": True,
                "age_s": 120,
                "max_age_s": 600,
            },
        },
        "feed_freshness": {
            "crypto_history": {
                "path": "data/cache/crypto_history.json",
                "exists": True,
                "fresh": False,
                "age_s": 5000,
                "threshold_s": 3600,
            },
            "yield_curve": {
                "path": "data/cache/yield_curve.json",
                "exists": True,
                "fresh": True,
                "age_s": 1000,
                "threshold_s": 86400,
            },
        },
    }
    cron = {
        "timestamp": "2026-06-29T17:47:58Z",
        "window_days": 2,
        "total_crons": 97,
        "counts": {"GREEN": 47, "RED_STALE_LOG": 1, "UNKNOWN_NO_LOG": 0},
    }
    killed = {
        "timestamp": "2026-06-29T17:47:58Z",
        "killed_route_count": 94,
        "routes_with_capital": 94,
        "routes_with_positions": 0,
        "total_open_positions": 0,
        "total_positions_value_usd": 0.0,
        "total_cash_trapped_usd": 7703.09,
    }
    results = [
        CommandResult("snapshot_probe", "ssh agni snapshot", 0, "{}"),
        CommandResult("cron_audit", "ssh agni cron", 0, "{}"),
        CommandResult("killed_routes_audit", "ssh agni killed", 0, "{}"),
    ]

    payload = build_watcher_payload(
        checked_at="2026-06-29T18:00:00Z",
        ssh_alias="agni",
        trading_root="/root/trading_lab",
        snapshot=snapshot,
        cron_audit=cron,
        killed_routes=killed,
        command_results=results,
    )

    assert payload["schema_version"] == "dharma_remote_kaizen_agni_result.v1"
    assert payload["updated_at"] == "2026-06-29T18:00:00Z"
    assert payload["mode"] == "paper"
    assert payload["live_order_authority"] is False
    assert payload["exchange_key_mutation"] is False
    assert payload["real_money_permission"] == "blocked"
    assert payload["remote_writes"] == []
    assert payload["ok"] is True
    blockers = payload["packet"]["blockers"]
    assert "Dashboard snapshot must be <=30 minutes old." in blockers
    assert any("crypto_history" in blocker for blocker in blockers)
    assert any("RED_STALE_LOG=1" in blocker for blocker in blockers)
    assert "Real-money permission remains blocked without explicit operator approval." in blockers
    assert payload["packet"]["route_screen"]["capital_eligible"] is False


def test_agni_watcher_outputs_materialize_latest_and_receipt(tmp_path: Path) -> None:
    payload = build_watcher_payload(
        checked_at="2026-06-29T18:00:00Z",
        ssh_alias="agni",
        trading_root="/root/trading_lab",
        snapshot={"files": {}, "feed_freshness": {}},
        cron_audit={"counts": {}},
        killed_routes={},
        command_results=[CommandResult("snapshot_probe", "ssh agni snapshot", 0, "{}")],
    )

    result_path, markdown_path, receipt_path = write_watcher_outputs(
        payload,
        state_root=tmp_path,
    )

    assert result_path == tmp_path / "remote_nodes" / "agni" / "kaizen_agni_latest.json"
    assert markdown_path == tmp_path / "remote_nodes" / "agni" / "kaizen_agni_latest.md"
    assert receipt_path.name == "agni-trading_kaizen_agni-20260629T180000Z.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert result["receipt_path"] == str(receipt_path)
    assert result == receipt
    assert "real_money_permission: blocked" in markdown_path.read_text(encoding="utf-8")
