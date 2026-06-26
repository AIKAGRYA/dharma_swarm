from __future__ import annotations

import ast
import copy
import importlib
import inspect
import json
import sys
from pathlib import Path

import pytest

from dharma_swarm.capital_lab.contracts import Direction, Insight


def write_snapshot(root: Path) -> Path:
    data = root / "data"
    data.mkdir(parents=True)
    (data / "agni_daily_reports.json").write_text(
        json.dumps(
            [
                {
                    "date": "2026-06-24",
                    "day_pnl": -3.0,
                    "losses": 2,
                    "nav": 13220.0,
                    "routes": 3,
                    "trades": 4,
                    "vraj_applied": 0,
                    "vraj_proposed": 2,
                    "wins": 2,
                },
                {
                    "date": "2026-06-25",
                    "day_pnl": 12.5,
                    "losses": 1,
                    "nav": 13225.0,
                    "routes": 3,
                    "trades": 5,
                    "vraj_applied": 0,
                    "vraj_proposed": 3,
                    "wins": 4,
                },
            ]
        ),
        encoding="utf-8",
    )
    (data / "agni_trading_timeline.json").write_text(
        json.dumps(
            {
                "alerts_daily": [
                    {
                        "date": "2026-06-25",
                        "feeds": {"sentiment": 2},
                        "lines": 2,
                        "stale": 2,
                    }
                ],
                "route_summary": {
                    "R01_vwap_btc": {
                        "first_trade": "2026-06-24T00:00:00+00:00",
                        "last_trade": "2026-06-25T00:00:00+00:00",
                        "pnl": 4.0,
                        "trades": 8,
                    },
                    "R02_funding_eth": {
                        "first_trade": "2026-06-24T00:00:00+00:00",
                        "last_trade": "2026-06-25T00:00:00+00:00",
                        "pnl": -1.0,
                        "trades": 4,
                    },
                },
                "routes": [
                    {
                        "first_ts": "2026-06-24T00:00:00+00:00",
                        "first_value": 50.0,
                        "last_ts": "2026-06-25T00:00:00+00:00",
                        "last_value": 54.0,
                        "route": "R01_vwap_btc",
                        "rows": 100,
                    },
                    {
                        "first_ts": "2026-06-24T00:00:00+00:00",
                        "first_value": 50.0,
                        "last_ts": "2026-06-25T00:00:00+00:00",
                        "last_value": 49.0,
                        "route": "R02_funding_eth",
                        "rows": 50,
                    },
                ],
                "system_equity": [
                    {
                        "date": "2026-06-25",
                        "timestamp": "2026-06-25T23:00:00+00:00",
                        "total_value": 13225.0,
                        "trading_pnl": 82.0,
                    }
                ],
                "trade_days": [],
            }
        ),
        encoding="utf-8",
    )
    (data / "agni_alpha_full_summary.json").write_text(
        json.dumps(
            {
                "by_day": [
                    {
                        "date": "2026-06-25",
                        "llm_failed": 1,
                        "no_regime_data": 0,
                        "no_sizeup_candidates": 2,
                        "observed": 4,
                        "total": 7,
                    }
                ],
                "first_last": [],
                "rows": 7,
            }
        ),
        encoding="utf-8",
    )
    (data / "routes.json").write_text('{"do_not_touch": true}\n', encoding="utf-8")
    return root


def import_bridge_without_broker():
    sys.modules.pop("dharma_swarm.capital_lab.agni_bridge", None)
    sys.modules.pop("dharma_swarm.capital_lab.broker_paper_membrane", None)
    return importlib.import_module("dharma_swarm.capital_lab.agni_bridge")


def test_bridge_import_does_not_import_broker_membrane() -> None:
    bridge = import_bridge_without_broker()

    assert "dharma_swarm.capital_lab.broker_paper_membrane" not in sys.modules

    tree = ast.parse(inspect.getsource(bridge))
    imported_modules: set[str] = set()
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")
            imported_names.update(alias.name for alias in node.names)

    assert "dharma_swarm.capital_lab.broker_paper_membrane" not in imported_modules
    assert {"Order", "OrderIntent", "PortfolioTarget", "RiskAdjustedTarget"}.isdisjoint(imported_names)


def test_exporter_appends_signed_packet_and_does_not_touch_routes_json(tmp_path: Path) -> None:
    bridge = import_bridge_without_broker()
    snapshot = write_snapshot(tmp_path / "snapshot")
    routes_json = snapshot / "data" / "routes.json"
    before = routes_json.read_text(encoding="utf-8")
    jsonl = tmp_path / "packets" / "agni.jsonl"
    jsonl.parent.mkdir(parents=True)
    jsonl.write_text('{"already":"there"}\n', encoding="utf-8")

    packet = bridge.export_agni_packet(
        snapshot,
        jsonl,
        generated_at="2026-06-26T00:00:00Z",
    )

    assert routes_json.read_text(encoding="utf-8") == before
    lines = jsonl.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"already": "there"}
    assert json.loads(lines[1])["packet_id"] == packet["packet_id"]
    assert bridge.validate_packet_signature(packet)
    assert packet["authority"] == bridge.AUTHORITY_BOUNDARY
    assert set(packet["source_snapshot"]["files"]) == set(bridge.STABLE_AGNI_FILES)
    assert "routes.json" not in packet["source_snapshot"]["files"]


def test_importer_maps_packets_to_evidence_and_insights_only(tmp_path: Path) -> None:
    bridge = import_bridge_without_broker()
    packet = bridge.build_agni_packet(
        write_snapshot(tmp_path / "snapshot"),
        generated_at="2026-06-26T00:00:00Z",
    )

    result = bridge.import_packets_to_dharma_capital([packet])

    assert result.authority == bridge.AUTHORITY_BOUNDARY
    assert result.comparison.status == bridge.SISTER_LAB_MISSING
    assert result.universe.source == "dharma_capital_agni_bridge_v0"
    assert {"BTC", "ETH"}.issubset(set(result.universe.security_ids))
    assert result.evidence[0].custody_label == "RECEIPT_BACKED_PROJECTION"
    assert all(isinstance(insight, Insight) for insight in result.evidence[0].insights)
    assert {insight.direction for insight in result.evidence[0].insights} == {
        Direction.UP,
        Direction.DOWN,
    }
    assert {type(obj).__name__ for obj in result.evidence[0].insights} == {"Insight"}
    assert all(proposal.auto_approved is False for proposal in result.proposals)
    assert all(proposal.capital_authority_change is False for proposal in result.proposals)
    assert all(proposal.route_mutation is False for proposal in result.proposals)
    assert all(proposal.order_generation is False for proposal in result.proposals)
    assert all(proposal.approval_state == "requires_human_review" for proposal in result.proposals)


def test_importer_compares_orthogonal_sister_labs(tmp_path: Path) -> None:
    bridge = import_bridge_without_broker()
    snapshot = write_snapshot(tmp_path / "snapshot")
    agni = bridge.build_agni_packet(
        snapshot,
        generated_at="2026-06-26T00:00:00Z",
        lab_id="agni",
        strategy_scope="crypto_multi_route_vps_trading",
    )
    sister = bridge.build_agni_packet(
        snapshot,
        generated_at="2026-06-26T00:01:00Z",
        lab_id="rushabdev",
        parent_lab_id="trading-lab/rushabdev",
        strategy_scope="forex_macro_event_vps_trading",
    )

    result = bridge.import_packets_to_dharma_capital([agni, sister])

    assert result.comparison.status == "compared"
    assert result.comparison.orthogonality_status == "orthogonal_scope_claimed"
    assert set(result.comparison.ranked_labs) == {"agni", "rushabdev"}


def test_importer_flags_clone_risk_for_non_orthogonal_sister_lab(tmp_path: Path) -> None:
    bridge = import_bridge_without_broker()
    snapshot = write_snapshot(tmp_path / "snapshot")
    agni = bridge.build_agni_packet(
        snapshot,
        generated_at="2026-06-26T00:00:00Z",
        lab_id="agni",
        strategy_scope="crypto_multi_route_vps_trading",
    )
    clone = bridge.build_agni_packet(
        snapshot,
        generated_at="2026-06-26T00:01:00Z",
        lab_id="agni_clone",
        parent_lab_id="trading-lab/agni-clone",
        strategy_scope="crypto_multi_route_vps_trading",
    )

    result = bridge.import_packets_to_dharma_capital([agni, clone])

    assert result.comparison.status == "compared_with_clone_risk"
    assert result.comparison.orthogonality_status == "clone_risk"
    assert any(proposal.reason == "sister_lab_clone_risk" for proposal in result.proposals)


def test_importer_rejects_signature_tamper_and_authority_escalation(tmp_path: Path) -> None:
    bridge = import_bridge_without_broker()
    packet = bridge.build_agni_packet(
        write_snapshot(tmp_path / "snapshot"),
        generated_at="2026-06-26T00:00:00Z",
    )
    tampered = copy.deepcopy(packet)
    tampered["performance"]["total_pnl"] = 999999
    with pytest.raises(ValueError, match="invalid packet signature"):
        bridge.import_packets_to_dharma_capital([tampered])

    escalated = copy.deepcopy(packet)
    escalated["authority"]["live_authority"] = True
    escalated = bridge.sign_packet(escalated)
    with pytest.raises(ValueError, match="authority boundary violation"):
        bridge.import_packets_to_dharma_capital([escalated])
