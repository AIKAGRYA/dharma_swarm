from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.capital_lab.alpha_evidence import (
    DEFAULT_HARNESS_RUN_ID,
    DEFAULT_RUN_ID,
    MISSION_ID,
    ProviderConfig,
    REQUIRED_BASELINES,
    REQUIRED_COSTS,
    REQUIRED_LEAKAGE_TRAPS,
    StrategyGateInputs,
    build_alpha_evidence_scorecard,
    build_alpha_graveyard_packet,
    build_data_lineage_packet,
    build_leakage_gauntlet_receipt,
    build_strategy_evidence_packet,
    build_walk_forward_oos_receipt,
    evaluate_provider_readiness,
    generate_alpha_evidence_bundle,
    sha256_file,
    validate_artifact_bundle,
)


FIXED_TIME = "2026-06-05T14:01:00Z"


def _write_market_data(root: Path) -> None:
    data_dir = root / "data" / "clean"
    data_dir.mkdir(parents=True)
    (data_dir / "bars.csv").write_text(
        "ts,symbol,close,feature_available_at\n"
        "2025-01-01T00:00:00Z,AAA,10,2024-12-31T23:00:00Z\n",
        encoding="utf-8",
    )


def _clean_provider_config() -> ProviderConfig:
    return ProviderConfig(
        provider_id="clean_point_in_time_vendor",
        provider_tier="promotion_grade_readonly_fixture",
        asset_classes=("equities",),
        feed_type="historical_bars",
        expected_data_dirs=("data/clean",),
        license_ref="readonly-license-receipt-001",
        point_in_time_safe=True,
        survivorship_policy="active_and_delisted_symbols",
        corporate_actions_available=True,
        delisted_symbols_available=True,
        adjustment_policy="split_and_dividend_adjusted_with_raw_retention",
    )


def _clean_gate_inputs(leakage: bool = True) -> StrategyGateInputs:
    return StrategyGateInputs(
        feature_availability_timestamps=True,
        frozen_universe=True,
        final_holdout_touched_once=True,
        baselines={name: True for name in REQUIRED_BASELINES},
        costs={name: True for name in REQUIRED_COSTS},
        capacity_check=True,
        correlation_check=True,
        model_council_review=True,
        quant_gates_review=True,
        leakage_traps={name: leakage for name in REQUIRED_LEAKAGE_TRAPS},
        walk_forward_splits=4,
        walk_forward_min_train_rows=100,
        walk_forward_min_test_rows=25,
        final_holdout_policy="sealed_once",
    )


def _clean_packets(tmp_path: Path, *, leakage: bool = True):
    _write_market_data(tmp_path)
    provider_packet = evaluate_provider_readiness(
        run_id=DEFAULT_RUN_ID,
        mission_id=MISSION_ID,
        harness_run_id=DEFAULT_HARNESS_RUN_ID,
        data_root=tmp_path,
        env={"CLEAN_VENDOR_TOKEN": "redacted"},
        provider_configs=(_clean_provider_config(),),
        proof_overrides={
            "clean_point_in_time_vendor": {
                "feature_timestamp_receipts": ["feature_ts_receipt_001"],
                "quality_receipts": ["calendar_receipt_001"],
                "redistribution_allowed": False,
            }
        },
        generated_at=FIXED_TIME,
    )
    lineage_packet = build_data_lineage_packet(provider_packet, generated_at=FIXED_TIME)
    graveyard_packet = build_alpha_graveyard_packet(
        run_id=DEFAULT_RUN_ID,
        mission_id=MISSION_ID,
        harness_run_id=DEFAULT_HARNESS_RUN_ID,
        bootstrap_summary={
            "agni_prior_evidence_summary": {
                "lifecycle_state_counts": {"killed": 4, "burn_in": 3, "live": 1}
            }
        },
        generated_at=FIXED_TIME,
    )
    gate_inputs = _clean_gate_inputs(leakage=leakage)
    leakage_receipt = build_leakage_gauntlet_receipt(
        run_id=DEFAULT_RUN_ID,
        mission_id=MISSION_ID,
        harness_run_id=DEFAULT_HARNESS_RUN_ID,
        trap_results=gate_inputs.leakage_traps,
        generated_at=FIXED_TIME,
    )
    walk_forward_receipt = build_walk_forward_oos_receipt(
        run_id=DEFAULT_RUN_ID,
        mission_id=MISSION_ID,
        harness_run_id=DEFAULT_HARNESS_RUN_ID,
        gate_inputs=gate_inputs,
        generated_at=FIXED_TIME,
    )
    strategy_packet = build_strategy_evidence_packet(
        provider_packet,
        lineage_packet,
        graveyard_packet,
        leakage_receipt,
        walk_forward_receipt,
        gate_inputs=gate_inputs,
        generated_at=FIXED_TIME,
    )
    return (
        provider_packet,
        lineage_packet,
        graveyard_packet,
        leakage_receipt,
        walk_forward_receipt,
        strategy_packet,
    )


def test_provider_readiness_records_alias_presence_without_secret_values(tmp_path: Path) -> None:
    _write_market_data(tmp_path)
    provider_packet = evaluate_provider_readiness(
        data_root=tmp_path,
        env={"ALPACA_API_KEY": "SHOULD_NOT_APPEAR", "ALPACA_SECRET_KEY": "ALSO_HIDDEN"},
        generated_at=FIXED_TIME,
    )

    encoded = json.dumps(provider_packet, sort_keys=True)
    assert "SHOULD_NOT_APPEAR" not in encoded
    assert "ALSO_HIDDEN" not in encoded
    assert provider_packet["live_readiness"] == 0
    assert provider_packet["live_authority"] is False

    alpaca = next(provider for provider in provider_packet["providers"] if provider["provider_id"] == "alpaca_market_data")
    assert alpaca["config_aliases_present"]["ALPACA_API_KEY"] is True
    assert alpaca["secret_value_recorded"] is False


def test_default_leakage_gauntlet_enumerates_all_required_traps() -> None:
    receipt = build_leakage_gauntlet_receipt(generated_at=FIXED_TIME)

    assert [trap["trap_id"] for trap in receipt["traps"]] == list(REQUIRED_LEAKAGE_TRAPS)
    assert all(trap["implemented"] for trap in receipt["traps"])
    assert receipt["clean"] is False
    assert receipt["status"] == "blocked_leakage_or_lineage"


def test_clean_synthetic_proof_can_score_above_80_while_authority_stays_zero(tmp_path: Path) -> None:
    packets = _clean_packets(tmp_path, leakage=True)
    scorecard = build_alpha_evidence_scorecard(*packets, generated_at=FIXED_TIME)

    assert packets[0]["clean"] is True
    assert packets[1]["clean"] is True
    assert packets[-1]["clean"] is True
    assert scorecard["clean"] is True
    assert scorecard["status"] == "alpha_evidence_clean_80_candidate"
    assert scorecard["score"] >= 80.0
    assert scorecard["live_readiness"] == 0
    assert scorecard["live_authority"] is False


def test_scorecard_is_capped_below_80_when_leakage_gate_fails(tmp_path: Path) -> None:
    packets = _clean_packets(tmp_path, leakage=False)
    scorecard = build_alpha_evidence_scorecard(*packets, generated_at=FIXED_TIME)

    assert packets[3]["clean"] is False
    assert scorecard["clean"] is False
    assert scorecard["score"] <= 79.0
    assert any(cap["reason"] == "leakage_gauntlet_not_clean" for cap in scorecard["hard_caps_applied"])


def test_generate_bundle_writes_hashable_partial_artifacts_without_forbidden_token(tmp_path: Path) -> None:
    bootstrap_dir = tmp_path / "bootstrap"
    bootstrap_dir.mkdir()
    (bootstrap_dir / "strategy_evidence_packet.json").write_text(
        json.dumps(
            {
                "agni_prior_evidence_summary": {
                    "lifecycle_state_counts": {"killed": 2, "burn_in": 1, "live": 0}
                }
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    result = generate_alpha_evidence_bundle(
        output_dir=output_dir,
        bootstrap_dir=bootstrap_dir,
        generated_at=FIXED_TIME,
    )

    assert result["clean"] is False
    assert result["status"] == "alpha_evidence_partial_clean_false"
    validation = validate_artifact_bundle(output_dir)
    assert validation["valid"], validation["errors"]

    manifest = validation["manifest"]
    assert manifest["live_readiness"] == 0
    assert manifest["live_authority"] is False
    for artifact_name, digest in manifest["artifact_hashes"].items():
        assert sha256_file(output_dir / artifact_name) == digest

    combined_text = "\n".join(path.read_text(encoding="utf-8") for path in output_dir.iterdir())
    assert "live" + "_ready" not in combined_text
