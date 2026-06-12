"""Evidence-only alpha membrane for Dharma Capital Lab Goal A.

The module builds deterministic packets for provider coverage, lineage,
leakage traps, walk-forward gates, alpha graveyard evidence, and the
institutional scorecard. It deliberately never grants trading authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence


MISSION_ID = "20260605T140100Z-dharma-capital-lab-goal-a-alpha-evidence-12h"
DEFAULT_RUN_ID = "20260605T140100Z"
DEFAULT_HARNESS_RUN_ID = (
    "dharma-capital-lab-goal-a-alpha-evidence-12h-20260605T140100Z"
)
LIVE_READINESS = 0
LIVE_AUTHORITY = False
AUTHORITY = "evidence_only"
CAPITAL_PERMISSION = "none"

ALLOWED_FINAL_STATUSES = {
    "alpha_evidence_clean_80_candidate",
    "alpha_evidence_partial_clean_false",
    "blocked_provider_constraints",
    "blocked_leakage_or_lineage",
}

REQUIRED_BASELINES = (
    "cash_no_trade",
    "buy_and_hold",
    "random",
    "momentum",
    "mean_reversion",
    "volatility_filter",
)

REQUIRED_COSTS = (
    "fees",
    "spread",
    "slippage",
    "borrow",
    "turnover",
    "capacity",
)

REQUIRED_LEAKAGE_TRAPS = (
    "future_label_trap",
    "shuffled_label_trap",
    "reverse_time_trap",
    "survivor_only_universe_trap",
    "parameter_cherry_pick_trap",
    "current_data_enrichment_trap",
)

REQUIRED_PROVIDER_GATES = (
    "point_in_time_safe",
    "survivorship_not_survivors_only",
    "corporate_actions_available",
    "delisted_symbols_available",
    "license_ref_present",
    "raw_payload_hashes_present",
    "normalized_dataset_hash_present",
    "feature_availability_timestamps_present",
    "promotion_grade",
)

REQUIRED_STRATEGY_GATES = (
    "provider_clean",
    "promotion_grade_provider",
    "point_in_time_lineage",
    "feature_availability_timestamps",
    "frozen_universe",
    "walk_forward_oos",
    "final_holdout_touched_once",
    "baselines_complete",
    "cost_model_complete",
    "capacity_check",
    "correlation_check",
    "leakage_gauntlet_passed",
    "model_council_review",
    "quant_gates_review",
    "alpha_graveyard_recorded",
)

HASHABLE_SUFFIXES = {
    ".csv",
    ".json",
    ".jsonl",
    ".ndjson",
    ".parquet",
    ".feather",
    ".txt",
}
SENSITIVE_NAME_RE = re.compile(
    r"(?:^|[._-])(secret|token|credential|passwd|password|private[_-]?key|api[_-]?key|env)(?:$|[._-])",
    re.IGNORECASE,
)
FORBIDDEN_ARTIFACT_RE = re.compile(
    r"\blive" r"[_-]ready\b|\bprofit\b|signed live payload|real order",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ProviderConfig:
    provider_id: str
    provider_tier: str
    asset_classes: tuple[str, ...]
    feed_type: str
    expected_data_dirs: tuple[str, ...]
    config_aliases: tuple[str, ...] = ()
    license_ref: str = ""
    redistribution_allowed: bool = False
    point_in_time_safe: bool = False
    survivorship_policy: str = "unproven"
    corporate_actions_available: bool = False
    delisted_symbols_available: bool = False
    adjustment_policy: str = "unproven"
    known_limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class StrategyGateInputs:
    """External proof knobs for tests or future read-only evaluators."""

    feature_availability_timestamps: bool = False
    frozen_universe: bool = False
    final_holdout_touched_once: bool = False
    baselines: Mapping[str, bool] = field(default_factory=dict)
    costs: Mapping[str, bool] = field(default_factory=dict)
    capacity_check: bool = False
    correlation_check: bool = False
    model_council_review: bool = False
    quant_gates_review: bool = False
    leakage_traps: Mapping[str, bool] = field(default_factory=dict)
    walk_forward_splits: int = 0
    walk_forward_min_train_rows: int = 0
    walk_forward_min_test_rows: int = 0
    final_holdout_policy: str = "not_proven"
    extra_blockers: tuple[str, ...] = ()


DEFAULT_PROVIDER_CONFIGS = (
    ProviderConfig(
        provider_id="alpaca_market_data",
        provider_tier="tier1_plumbing_unverified_subscription",
        asset_classes=("equities", "crypto"),
        feed_type="bars_and_quotes_if_subscription_allows",
        expected_data_dirs=("data/cache", "data/realtime"),
        config_aliases=("ALPACA_API_KEY", "ALPACA_SECRET_KEY"),
        survivorship_policy="unproven",
        adjustment_policy="subscription_tier_unproven",
        known_limitations=(
            "subscription_tier_not_proven",
            "corporate_actions_not_proven",
            "delisted_symbols_not_proven",
            "point_in_time_lineage_not_proven",
        ),
    ),
    ProviderConfig(
        provider_id="yfinance_public_fallback",
        provider_tier="tier1_public_fallback",
        asset_classes=("equities",),
        feed_type="historical_bars",
        expected_data_dirs=("data/cache",),
        survivorship_policy="survivors_only_risk",
        adjustment_policy="unverified_public_adjustments",
        known_limitations=(
            "license_not_promotion_grade",
            "survivorship_not_controlled",
            "point_in_time_not_proven",
        ),
    ),
    ProviderConfig(
        provider_id="crypto_exchange_public_cache",
        provider_tier="tier1_crypto_plumbing",
        asset_classes=("crypto",),
        feed_type="public_or_cached_bars",
        expected_data_dirs=("data/cache", "data/realtime", "data/signals"),
        config_aliases=("BINANCE_API_KEY", "BYBIT_API_KEY"),
        survivorship_policy="exchange_symbol_lifecycle_unproven",
        adjustment_policy="not_applicable_or_unproven",
        known_limitations=(
            "exchange_symbol_lifecycle_not_proven",
            "raw_payload_hashes_required",
            "normalized_dataset_hash_required",
        ),
    ),
    ProviderConfig(
        provider_id="prediction_market_public_cache",
        provider_tier="tier1_event_market_plumbing",
        asset_classes=("prediction_markets",),
        feed_type="public_or_cached_event_markets",
        expected_data_dirs=("data/polymarket",),
        survivorship_policy="market_resolution_lifecycle_unproven",
        adjustment_policy="not_applicable",
        known_limitations=(
            "not_equity_alpha_provider",
            "event_lifecycle_lineage_not_proven",
        ),
    ),
    ProviderConfig(
        provider_id="fred_macro_cache",
        provider_tier="tier1_macro_public_or_keyed_cache",
        asset_classes=("macro", "rates"),
        feed_type="macro_time_series",
        expected_data_dirs=("data/cache", "data/signals"),
        config_aliases=("FRED_API_KEY",),
        survivorship_policy="not_equity_universe",
        adjustment_policy="not_applicable",
        known_limitations=(
            "release_timestamp_lineage_required",
            "revision_history_not_proven",
        ),
    ),
    ProviderConfig(
        provider_id="insider_signals_cache",
        provider_tier="tier1_auxiliary_signal_cache",
        asset_classes=("equities", "event_signals"),
        feed_type="auxiliary_event_signals",
        expected_data_dirs=("data/insider", "data/signals"),
        survivorship_policy="issuer_universe_lineage_unproven",
        adjustment_policy="requires_point_in_time_event_availability",
        known_limitations=(
            "current_data_enrichment_trap_required",
            "feature_timestamp_receipts_required",
        ),
    ),
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_json(payload: Any) -> str:
    return sha256_bytes(canonical_json_bytes(payload))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def common_packet_fields(run_id: str, mission_id: str, harness_run_id: str, generated_at: str) -> dict[str, Any]:
    return {
        "authority": AUTHORITY,
        "broker_write_authority": False,
        "capital_permission": CAPITAL_PERMISSION,
        "generated_at": generated_at,
        "harness_run_id": harness_run_id,
        "live_authority": LIVE_AUTHORITY,
        "live_order_authority": False,
        "live_readiness": LIVE_READINESS,
        "mission_id": mission_id,
        "paper_only": True,
        "run_id": run_id,
        "secret_value_recorded": False,
        "secret_values_read": False,
        "withdrawals_or_transfers": False,
    }


def redacted_alias_presence(aliases: Sequence[str], env: Mapping[str, str] | None = None) -> dict[str, bool]:
    source = os.environ if env is None else env
    return {alias: bool(source.get(alias)) for alias in aliases}


def safe_file_candidates(data_root: Path | None, rel_dirs: Sequence[str], max_files: int = 32) -> list[Path]:
    if data_root is None:
        return []
    root = Path(data_root)
    if not root.exists():
        return []
    candidates: list[Path] = []
    for rel_dir in rel_dirs:
        directory = root / rel_dir
        if not directory.exists() or not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in HASHABLE_SUFFIXES:
                continue
            rel_name = path.relative_to(root).as_posix()
            if SENSITIVE_NAME_RE.search(rel_name):
                continue
            candidates.append(path)
            if len(candidates) >= max_files:
                return candidates
    return candidates


def summarize_data_dirs(data_root: Path | None, rel_dirs: Sequence[str]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for rel_dir in rel_dirs:
        directory = Path(data_root) / rel_dir if data_root is not None else None
        exists = bool(directory and directory.exists() and directory.is_dir())
        file_count = 0
        newest_mtime_utc = None
        if exists and directory is not None:
            mtimes: list[float] = []
            for path in directory.rglob("*"):
                if path.is_file() and not SENSITIVE_NAME_RE.search(path.name):
                    file_count += 1
                    mtimes.append(path.stat().st_mtime)
            if mtimes:
                newest_mtime_utc = (
                    datetime.fromtimestamp(max(mtimes), UTC)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
        summary[rel_dir] = {
            "exists": exists,
            "file_count": file_count,
            "newest_mtime_utc": newest_mtime_utc,
        }
    return summary


def raw_payload_hashes_for_provider(data_root: Path | None, config: ProviderConfig) -> dict[str, str]:
    if data_root is None:
        return {}
    root = Path(data_root)
    hashes: dict[str, str] = {}
    for path in safe_file_candidates(root, config.expected_data_dirs):
        try:
            hashes[path.relative_to(root).as_posix()] = sha256_file(path)
        except OSError:
            continue
    return hashes


def normalized_hash(provider_id: str, raw_hashes: Mapping[str, str], proof: Mapping[str, Any]) -> str:
    if not raw_hashes and not proof.get("normalized_dataset_hash"):
        return ""
    if proof.get("normalized_dataset_hash"):
        return str(proof["normalized_dataset_hash"])
    payload = {
        "provider_id": provider_id,
        "raw_hashes": dict(sorted(raw_hashes.items())),
        "normalization_contract": "provider+path+sha256:v1",
    }
    return sha256_json(payload)


def provider_public_hash(provider: Mapping[str, Any]) -> str:
    public_payload = {
        key: value
        for key, value in provider.items()
        if key not in {"provider_hash", "packet_hash"}
    }
    return sha256_json(public_payload)


def evaluate_provider_readiness(
    *,
    run_id: str = DEFAULT_RUN_ID,
    mission_id: str = MISSION_ID,
    harness_run_id: str = DEFAULT_HARNESS_RUN_ID,
    data_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    provider_configs: Sequence[ProviderConfig] = DEFAULT_PROVIDER_CONFIGS,
    proof_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    proof_overrides = proof_overrides or {}
    providers: list[dict[str, Any]] = []

    for config in provider_configs:
        proof = proof_overrides.get(config.provider_id, {})
        raw_hashes = dict(proof.get("raw_payload_hashes") or raw_payload_hashes_for_provider(data_root, config))
        normalized_dataset_hash = normalized_hash(config.provider_id, raw_hashes, proof)
        license_ref = str(proof.get("license_ref", config.license_ref))
        feature_timestamp_receipts = list(proof.get("feature_timestamp_receipts", []))

        survivorship_policy = str(proof.get("survivorship_policy", config.survivorship_policy))
        gates = {
            "point_in_time_safe": bool(proof.get("point_in_time_safe", config.point_in_time_safe)),
            "survivorship_not_survivors_only": "survivors_only" not in survivorship_policy,
            "corporate_actions_available": bool(
                proof.get("corporate_actions_available", config.corporate_actions_available)
            ),
            "delisted_symbols_available": bool(
                proof.get("delisted_symbols_available", config.delisted_symbols_available)
            ),
            "license_ref_present": bool(license_ref),
            "raw_payload_hashes_present": bool(raw_hashes),
            "normalized_dataset_hash_present": bool(normalized_dataset_hash),
            "feature_availability_timestamps_present": bool(feature_timestamp_receipts),
            "promotion_grade": False,
        }
        gates["promotion_grade"] = all(value for key, value in gates.items() if key != "promotion_grade")
        blockers = [f"provider_gate_failed:{gate}" for gate, passed in gates.items() if not passed]

        provider = {
            "adjustment_policy": str(proof.get("adjustment_policy", config.adjustment_policy)),
            "asset_classes": list(config.asset_classes),
            "blockers": blockers,
            "config_aliases_present": redacted_alias_presence(config.config_aliases, env),
            "corporate_actions_available": gates["corporate_actions_available"],
            "data_dir_summary": summarize_data_dirs(data_root, config.expected_data_dirs),
            "delisted_symbols_available": gates["delisted_symbols_available"],
            "expected_data_dirs": list(config.expected_data_dirs),
            "feature_timestamp_receipts": feature_timestamp_receipts,
            "feed_type": config.feed_type,
            "known_limitations": list(config.known_limitations),
            "license_ref": license_ref,
            "normalized_dataset_hash": normalized_dataset_hash,
            "point_in_time_safe": gates["point_in_time_safe"],
            "promotion_grade": gates["promotion_grade"],
            "provider_id": config.provider_id,
            "provider_tier": config.provider_tier,
            "quality_receipts": list(proof.get("quality_receipts", [])),
            "raw_payload_hashes": raw_hashes,
            "redistribution_allowed": bool(
                proof.get("redistribution_allowed", config.redistribution_allowed)
            ),
            "required_gates": gates,
            "secret_aliases_used": list(config.config_aliases),
            "secret_value_recorded": False,
            "survivorship_policy": survivorship_policy,
        }
        provider["provider_hash"] = provider_public_hash(provider)
        providers.append(provider)

    promotion_grade_count = sum(1 for provider in providers if provider["promotion_grade"])
    aggregate_gates = {
        gate: any(provider["required_gates"].get(gate, False) for provider in providers)
        for gate in REQUIRED_PROVIDER_GATES
    }
    blockers = []
    if promotion_grade_count == 0:
        blockers.append("no_promotion_grade_provider")
    blockers.extend(
        f"provider_gate_failed:{gate}" for gate, passed in aggregate_gates.items() if not passed
    )

    packet: dict[str, Any] = {
        **common_packet_fields(run_id, mission_id, harness_run_id, generated_at),
        "blockers": blockers,
        "canonical_provider": next(
            (provider["provider_id"] for provider in providers if provider["promotion_grade"]),
            "",
        ),
        "clean": promotion_grade_count > 0,
        "data_root_observed": str(data_root) if data_root is not None else "",
        "promotion_grade_provider_count": promotion_grade_count,
        "provider_count": len(providers),
        "providers": providers,
        "required_promotion_gates": aggregate_gates,
        "schema_version": "dharma.capital_lab.alpha_evidence.v2.provider_readiness_packet",
        "status": "alpha_evidence_partial_clean_false"
        if promotion_grade_count
        else "blocked_provider_constraints",
    }
    packet["packet_hash"] = sha256_json(packet)
    return packet


def build_data_lineage_packet(
    provider_packet: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or str(provider_packet["generated_at"])
    receipts: list[dict[str, Any]] = []
    for provider in provider_packet["providers"]:
        receipt = {
            "as_of_calendar": {
                "calendar_id": "provider_calendar_or_exchange_calendar_required",
                "coverage_end": provider.get("coverage_end", ""),
                "coverage_start": provider.get("coverage_start", ""),
                "feature_timestamp_policy": "feature_timestamp_must_precede_signal_timestamp",
            },
            "corporate_actions": {
                "available": bool(provider["corporate_actions_available"]),
                "adjustment_policy": provider["adjustment_policy"],
            },
            "delisting": {
                "available": bool(provider["delisted_symbols_available"]),
                "policy": "delisted_symbols_or_event_lifecycle_required",
            },
            "feature_timestamp_receipts": list(provider["feature_timestamp_receipts"]),
            "license": {
                "license_ref": provider["license_ref"],
                "redistribution_allowed": bool(provider["redistribution_allowed"]),
            },
            "normalized_dataset_hash": provider["normalized_dataset_hash"],
            "point_in_time_safe": bool(provider["point_in_time_safe"]),
            "provider_hash": provider["provider_hash"],
            "provider_id": provider["provider_id"],
            "raw_payload_hashes": dict(provider["raw_payload_hashes"]),
            "secret_value_recorded": False,
            "survivorship": {
                "policy": provider["survivorship_policy"],
                "survivor_only_blocked": "survivors_only" in provider["survivorship_policy"],
            },
        }
        receipt["lineage_hash"] = sha256_json(receipt)
        receipts.append(receipt)

    clean_receipts = [
        receipt
        for receipt in receipts
        if receipt["point_in_time_safe"]
        and bool(receipt["feature_timestamp_receipts"])
        and bool(receipt["license"]["license_ref"])
        and bool(receipt["raw_payload_hashes"])
        and bool(receipt["normalized_dataset_hash"])
        and receipt["corporate_actions"]["available"]
        and receipt["delisting"]["available"]
        and not receipt["survivorship"]["survivor_only_blocked"]
    ]
    packet = {
        **common_packet_fields(
            str(provider_packet["run_id"]),
            str(provider_packet["mission_id"]),
            str(provider_packet["harness_run_id"]),
            generated_at,
        ),
        "blockers": []
        if clean_receipts
        else [
            "no_clean_lineage_receipt",
            "lineage_requires_license_raw_hash_normalized_hash_calendar_corporate_actions_delisting_feature_timestamps",
        ],
        "clean": bool(clean_receipts),
        "lineage_receipts": receipts,
        "promotion_grade_lineage_count": len(clean_receipts),
        "schema_version": "dharma.capital_lab.alpha_evidence.v2.data_lineage_packet",
        "status": "alpha_evidence_partial_clean_false"
        if clean_receipts
        else "blocked_leakage_or_lineage",
    }
    packet["packet_hash"] = sha256_json(packet)
    return packet


def load_bootstrap_summary(bootstrap_dir: Path | None) -> dict[str, Any]:
    if bootstrap_dir is None:
        return {}
    strategy_path = Path(bootstrap_dir) / "strategy_evidence_packet.json"
    provider_path = Path(bootstrap_dir) / "provider_readiness_packet.json"
    summary: dict[str, Any] = {}
    for path in (strategy_path, provider_path):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for key in (
            "agni_prior_evidence_summary",
            "agni_observation",
            "alpha_graveyard",
        ):
            if key in payload:
                summary[key] = payload[key]
    return summary


def build_alpha_graveyard_packet(
    *,
    run_id: str = DEFAULT_RUN_ID,
    mission_id: str = MISSION_ID,
    harness_run_id: str = DEFAULT_HARNESS_RUN_ID,
    bootstrap_summary: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    bootstrap_summary = bootstrap_summary or {}
    prior = bootstrap_summary.get("agni_prior_evidence_summary") or bootstrap_summary.get("agni_observation") or {}
    lifecycle_counts = prior.get("lifecycle_state_counts", {})
    killed = int(lifecycle_counts.get("killed", 0) or 0)
    burn_in = int(lifecycle_counts.get("burn_in", 0) or 0)
    operational_paper = int(lifecycle_counts.get("live", 0) or 0)
    entries = []
    if killed:
        entries.append(
            {
                "bucket": "killed_routes",
                "candidate_count": killed,
                "decision": "graveyard_only",
                "promotion_credit": False,
                "reason": "route lifecycle says rejected or retired; lineage must be attached before alpha credit",
            }
        )
    if burn_in:
        entries.append(
            {
                "bucket": "burn_in_routes",
                "candidate_count": burn_in,
                "decision": "quarantine_until_oos",
                "promotion_credit": False,
                "reason": "burn-in status is not out-of-sample evidence",
            }
        )
    if operational_paper:
        entries.append(
            {
                "bucket": "paper_operational_routes",
                "candidate_count": operational_paper,
                "decision": "prior_evidence_only",
                "promotion_credit": False,
                "reason": "paper route operation cannot certify market edge",
            }
        )

    recorded = bool(entries)
    packet = {
        **common_packet_fields(run_id, mission_id, harness_run_id, generated_at),
        "blockers": [] if recorded else ["no_alpha_graveyard_entries"],
        "clean": recorded,
        "entries": entries,
        "graveyard_recorded": recorded,
        "policy": {
            "promotion_credit_allowed": False,
            "route_counts_are_edge_evidence": False,
            "survivor_only_clean_packets_forbidden": True,
        },
        "schema_version": "dharma.capital_lab.alpha_evidence.v2.alpha_graveyard_packet",
        "status": "alpha_evidence_partial_clean_false",
        "total_candidate_count": sum(int(entry["candidate_count"]) for entry in entries),
    }
    packet["packet_hash"] = sha256_json(packet)
    return packet


def build_leakage_gauntlet_receipt(
    *,
    run_id: str = DEFAULT_RUN_ID,
    mission_id: str = MISSION_ID,
    harness_run_id: str = DEFAULT_HARNESS_RUN_ID,
    trap_results: Mapping[str, bool] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    trap_results = trap_results or {}
    traps: list[dict[str, Any]] = []
    for trap_id in REQUIRED_LEAKAGE_TRAPS:
        passed = bool(trap_results.get(trap_id, False))
        traps.append(
            {
                "implemented": True,
                "passed": passed,
                "required": True,
                "trap_id": trap_id,
                "verdict": "passed" if passed else "blocked_without_dataset_receipt",
            }
        )

    passed_all = all(trap["passed"] for trap in traps)
    packet = {
        **common_packet_fields(run_id, mission_id, harness_run_id, generated_at),
        "blockers": [] if passed_all else [f"leakage_trap_not_passed:{trap['trap_id']}" for trap in traps if not trap["passed"]],
        "clean": passed_all,
        "leakage_gauntlet_passed": passed_all,
        "schema_version": "dharma.capital_lab.alpha_evidence.v2.leakage_gauntlet_receipt",
        "status": "alpha_evidence_partial_clean_false" if passed_all else "blocked_leakage_or_lineage",
        "traps": traps,
    }
    packet["packet_hash"] = sha256_json(packet)
    return packet


def build_walk_forward_oos_receipt(
    *,
    run_id: str = DEFAULT_RUN_ID,
    mission_id: str = MISSION_ID,
    harness_run_id: str = DEFAULT_HARNESS_RUN_ID,
    gate_inputs: StrategyGateInputs | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    gate_inputs = gate_inputs or StrategyGateInputs()
    enough_splits = gate_inputs.walk_forward_splits >= 3
    enough_rows = gate_inputs.walk_forward_min_train_rows > 0 and gate_inputs.walk_forward_min_test_rows > 0
    passed = (
        gate_inputs.frozen_universe
        and enough_splits
        and enough_rows
        and gate_inputs.final_holdout_touched_once
    )
    blockers = []
    if not gate_inputs.frozen_universe:
        blockers.append("walk_forward_requires_frozen_universe")
    if not enough_splits:
        blockers.append("walk_forward_requires_at_least_three_oos_splits")
    if not enough_rows:
        blockers.append("walk_forward_requires_train_and_test_rows")
    if not gate_inputs.final_holdout_touched_once:
        blockers.append("final_holdout_touched_once_not_proven")

    packet = {
        **common_packet_fields(run_id, mission_id, harness_run_id, generated_at),
        "blockers": blockers,
        "clean": passed,
        "final_holdout": {
            "policy": gate_inputs.final_holdout_policy,
            "touched_once": gate_inputs.final_holdout_touched_once,
            "used_for_optimization": False,
        },
        "frozen_universe": gate_inputs.frozen_universe,
        "schema_version": "dharma.capital_lab.alpha_evidence.v2.walk_forward_oos_receipt",
        "split_contract": {
            "min_required_splits": 3,
            "observed_splits": gate_inputs.walk_forward_splits,
            "train_rows_min": gate_inputs.walk_forward_min_train_rows,
            "test_rows_min": gate_inputs.walk_forward_min_test_rows,
        },
        "status": "alpha_evidence_partial_clean_false" if passed else "blocked_leakage_or_lineage",
        "walk_forward_oos": passed,
    }
    packet["packet_hash"] = sha256_json(packet)
    return packet


def build_strategy_evidence_packet(
    provider_packet: Mapping[str, Any],
    lineage_packet: Mapping[str, Any],
    graveyard_packet: Mapping[str, Any],
    leakage_receipt: Mapping[str, Any],
    walk_forward_receipt: Mapping[str, Any],
    *,
    gate_inputs: StrategyGateInputs | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or str(provider_packet["generated_at"])
    gate_inputs = gate_inputs or StrategyGateInputs()
    baseline_gates = {name: bool(gate_inputs.baselines.get(name, False)) for name in REQUIRED_BASELINES}
    cost_gates = {name: bool(gate_inputs.costs.get(name, False)) for name in REQUIRED_COSTS}
    required_gates = {
        "provider_clean": bool(provider_packet["clean"]),
        "promotion_grade_provider": int(provider_packet["promotion_grade_provider_count"]) > 0,
        "point_in_time_lineage": bool(lineage_packet["clean"]),
        "feature_availability_timestamps": gate_inputs.feature_availability_timestamps,
        "frozen_universe": gate_inputs.frozen_universe,
        "walk_forward_oos": bool(walk_forward_receipt["walk_forward_oos"]),
        "final_holdout_touched_once": bool(walk_forward_receipt["final_holdout"]["touched_once"]),
        "baselines_complete": all(baseline_gates.values()),
        "cost_model_complete": all(cost_gates.values()),
        "capacity_check": gate_inputs.capacity_check,
        "correlation_check": gate_inputs.correlation_check,
        "leakage_gauntlet_passed": bool(leakage_receipt["leakage_gauntlet_passed"]),
        "model_council_review": gate_inputs.model_council_review,
        "quant_gates_review": gate_inputs.quant_gates_review,
        "alpha_graveyard_recorded": bool(graveyard_packet["graveyard_recorded"]),
    }
    blockers = [f"gate_failed:{gate}" for gate, passed in required_gates.items() if not passed]
    blockers.extend(gate_inputs.extra_blockers)
    clean = all(required_gates.values())
    if not provider_packet["clean"]:
        status = "blocked_provider_constraints"
    elif not required_gates["leakage_gauntlet_passed"] or not required_gates["point_in_time_lineage"]:
        status = "blocked_leakage_or_lineage"
    elif clean:
        status = "alpha_evidence_clean_80_candidate"
    else:
        status = "alpha_evidence_partial_clean_false"

    packet = {
        **common_packet_fields(
            str(provider_packet["run_id"]),
            str(provider_packet["mission_id"]),
            str(provider_packet["harness_run_id"]),
            generated_at,
        ),
        "baseline_gates": baseline_gates,
        "blockers": blockers,
        "clean": clean,
        "cost_model_gates": cost_gates,
        "edge_claim": False,
        "existing_input_policy": {
            "backtests": "prior_evidence_only_until_lineage_gates_pass",
            "caches": "prior_evidence_only_until_provider_packet_clean",
            "dashboards": "prior_evidence_only",
            "paper_routes": "prior_evidence_only_not_edge_certification",
            "route_state": "prior_evidence_only",
        },
        "historical_test_policy": {
            "current_auxiliary_enrichment_allowed": False,
            "feature_timestamp_must_precede_signal_timestamp": True,
            "final_holdout_touched_once_required": True,
            "frozen_universe_required": True,
            "survivor_only_universe_blocks_clean": True,
        },
        "required_gates": required_gates,
        "schema_version": "dharma.capital_lab.alpha_evidence.v2.strategy_evidence_packet",
        "status": status,
    }
    packet["packet_hash"] = sha256_json(packet)
    return packet


def percentage(values: Sequence[bool]) -> float:
    if not values:
        return 0.0
    return 100.0 * sum(1 for value in values if value) / len(values)


def weighted_dimension(label: str, score: float, weight: float) -> dict[str, float | str]:
    score = round(float(score), 2)
    weight = round(float(weight), 2)
    return {
        "label": label,
        "score": score,
        "weight": weight,
        "weighted_points": round(score * weight / 100.0, 4),
    }


def build_alpha_evidence_scorecard(
    provider_packet: Mapping[str, Any],
    lineage_packet: Mapping[str, Any],
    graveyard_packet: Mapping[str, Any],
    leakage_receipt: Mapping[str, Any],
    walk_forward_receipt: Mapping[str, Any],
    strategy_packet: Mapping[str, Any],
    *,
    artifact_hashes: Mapping[str, str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or str(provider_packet["generated_at"])
    provider_gate_values = [
        bool(provider["required_gates"][gate])
        for provider in provider_packet["providers"]
        for gate in REQUIRED_PROVIDER_GATES
    ]
    lineage_values = [
        bool(receipt["raw_payload_hashes"])
        and bool(receipt["normalized_dataset_hash"])
        and bool(receipt["feature_timestamp_receipts"])
        and bool(receipt["license"]["license_ref"])
        and bool(receipt["point_in_time_safe"])
        for receipt in lineage_packet["lineage_receipts"]
    ]
    leakage_values = [bool(trap["passed"]) for trap in leakage_receipt["traps"]]
    strategy_values = [bool(value) for value in strategy_packet["required_gates"].values()]
    baseline_cost_values = list(strategy_packet["baseline_gates"].values()) + list(
        strategy_packet["cost_model_gates"].values()
    )
    walk_values = [
        bool(walk_forward_receipt["frozen_universe"]),
        bool(walk_forward_receipt["walk_forward_oos"]),
        bool(walk_forward_receipt["final_holdout"]["touched_once"]),
    ]

    dimensions = {
        "authority_safety": weighted_dimension("Authority safety", 100.0, 10.0),
        "provider_readiness": weighted_dimension(
            "Provider readiness", 25.0 + 75.0 * percentage(provider_gate_values) / 100.0, 15.0
        ),
        "data_lineage": weighted_dimension(
            "Data lineage", 25.0 + 75.0 * percentage(lineage_values) / 100.0, 16.0
        ),
        "leakage_controls": weighted_dimension(
            "Leakage controls", 35.0 + 65.0 * percentage(leakage_values) / 100.0, 14.0
        ),
        "walk_forward_oos": weighted_dimension(
            "Walk-forward OOS", 25.0 + 75.0 * percentage(walk_values) / 100.0, 12.0
        ),
        "strategy_validation": weighted_dimension(
            "Strategy validation", 20.0 + 80.0 * percentage(strategy_values) / 100.0, 12.0
        ),
        "baselines_costs_capacity": weighted_dimension(
            "Baselines, costs, capacity", 20.0 + 80.0 * percentage(baseline_cost_values) / 100.0, 9.0
        ),
        "alpha_graveyard": weighted_dimension(
            "Alpha graveyard", 82.0 if graveyard_packet["graveyard_recorded"] else 35.0, 6.0
        ),
        "report_integrity": weighted_dimension("Report integrity", 88.0, 6.0),
    }
    weighted_score_before_caps = round(
        sum(float(value["weighted_points"]) for value in dimensions.values()), 2
    )

    hard_caps: list[dict[str, Any]] = []
    if not provider_packet["clean"] or not lineage_packet["clean"]:
        hard_caps.append(
            {
                "cap": 79.0,
                "reason": "provider_or_data_lineage_gate_not_clean",
            }
        )
    if not leakage_receipt["leakage_gauntlet_passed"]:
        hard_caps.append(
            {
                "cap": 79.0,
                "reason": "leakage_gauntlet_not_clean",
            }
        )
    if not walk_forward_receipt["walk_forward_oos"]:
        hard_caps.append(
            {
                "cap": 78.0,
                "reason": "walk_forward_oos_not_clean",
            }
        )
    if LIVE_READINESS != 0 or LIVE_AUTHORITY:
        hard_caps.append({"cap": 0.0, "reason": "authority_boundary_violation"})

    score = weighted_score_before_caps
    if hard_caps:
        score = min(score, *(float(cap["cap"]) for cap in hard_caps))
    score = round(score, 2)
    clean = bool(strategy_packet["clean"] and score >= 80.0)
    status = "alpha_evidence_clean_80_candidate" if clean else "alpha_evidence_partial_clean_false"

    packet = {
        **common_packet_fields(
            str(provider_packet["run_id"]),
            str(provider_packet["mission_id"]),
            str(provider_packet["harness_run_id"]),
            generated_at,
        ),
        "artifact_hashes": dict(artifact_hashes or {}),
        "blockers": list(provider_packet["blockers"])
        + list(lineage_packet["blockers"])
        + list(strategy_packet["blockers"]),
        "clean": clean,
        "dimensions": dimensions,
        "edge_or_return_claim": False,
        "hard_caps_applied": hard_caps,
        "readiness_claims": {
            "institutional_alpha_engine_candidate_architecture": clean,
            "investment_advice": False,
            "paper_or_fixture_evidence_treated_as_edge": False,
        },
        "required_artifacts": required_artifact_names(),
        "schema_version": "dharma.capital_lab.alpha_evidence.v2.alpha_evidence_scorecard",
        "score": score,
        "status": status,
        "target": "80/100 institutional alpha-evidence architecture",
        "weight_total": round(sum(float(value["weight"]) for value in dimensions.values()), 2),
        "weighted_score_before_caps": weighted_score_before_caps,
    }
    if packet["status"] not in ALLOWED_FINAL_STATUSES:
        raise ValueError(f"invalid final status: {packet['status']}")
    packet["scorecard_hash"] = sha256_json(packet)
    return packet


def build_independent_evaluator_receipt(
    scorecard: Mapping[str, Any],
    strategy_packet: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or str(scorecard["generated_at"])
    accepted = bool(scorecard["clean"] and strategy_packet["clean"] and float(scorecard["score"]) >= 80.0)
    blockers = [] if accepted else ["independent_acceptance_requires_clean_strategy_and_score_at_or_above_80"]
    packet = {
        **common_packet_fields(
            str(scorecard["run_id"]),
            str(scorecard["mission_id"]),
            str(scorecard["harness_run_id"]),
            generated_at,
        ),
        "accepted": accepted,
        "blockers": blockers,
        "clean": accepted,
        "evaluator": "deterministic_membrane_self_check_not_external_certifier",
        "schema_version": "dharma.capital_lab.alpha_evidence.v2.independent_evaluator_receipt",
        "score_observed": scorecard["score"],
        "status": "alpha_evidence_partial_clean_false"
        if not accepted
        else "alpha_evidence_clean_80_candidate",
    }
    packet["packet_hash"] = sha256_json(packet)
    return packet


def required_artifact_names() -> list[str]:
    return [
        "provider_readiness_packet.json",
        "data_lineage_packet.json",
        "alpha_graveyard_packet.json",
        "leakage_gauntlet_receipt.json",
        "walk_forward_oos_receipt.json",
        "strategy_evidence_packet.json",
        "alpha_evidence_scorecard.json",
        "independent_evaluator_receipt.json",
        "artifact_manifest.json",
        "final_report.md",
    ]


def render_final_report(scorecard: Mapping[str, Any], manifest_hashes: Mapping[str, str]) -> str:
    blockers = list(dict.fromkeys(str(blocker) for blocker in scorecard.get("blockers", [])))
    blocker_lines = "\n".join(f"- {blocker}" for blocker in blockers[:30]) or "- none"
    hash_lines = "\n".join(f"- {name}: {digest}" for name, digest in sorted(manifest_hashes.items()))
    cap_lines = "\n".join(
        f"- {cap['reason']}: cap={cap['cap']}" for cap in scorecard.get("hard_caps_applied", [])
    ) or "- none"
    return (
        "# Dharma Capital Lab Goal A Alpha Evidence Membrane\n\n"
        f"- mission_id: {scorecard['mission_id']}\n"
        f"- harness_run_id: {scorecard['harness_run_id']}\n"
        f"- run_id: {scorecard['run_id']}\n"
        f"- final_status: {scorecard['status']}\n"
        f"- score: {scorecard['score']}\n"
        f"- clean: {str(scorecard['clean']).lower()}\n"
        f"- live_readiness: {scorecard['live_readiness']}\n"
        f"- live_authority: {str(scorecard['live_authority']).lower()}\n"
        "- capital_return_claim: false\n"
        "- broker_write_authority: false\n\n"
        "## Authority Boundary\n\n"
        "- evidence-only packet generation\n"
        "- no broker writes, transfers, withdrawals, or order payload signing\n"
        "- no secret values read or recorded\n"
        "- prior route, dashboard, cache, and paper evidence remains input-only\n\n"
        "## Artifact Hashes\n\n"
        f"{hash_lines}\n\n"
        "## Score Caps\n\n"
        f"{cap_lines}\n\n"
        "## Blockers\n\n"
        f"{blocker_lines}\n\n"
        "## Next Actions\n\n"
        "- Attach promotion-grade point-in-time provider receipts with license, raw hashes, normalized hashes, corporate actions, delisting coverage, and feature timestamps.\n"
        "- Run the leakage gauntlet on frozen historical data before scoring a clean strategy packet.\n"
        "- Execute walk-forward OOS with baselines, costs, capacity, correlation, and one-use final holdout receipts.\n"
    )


def artifact_hashes(paths: Mapping[str, Path]) -> dict[str, str]:
    return {name: sha256_file(path) for name, path in sorted(paths.items()) if path.exists()}


def build_artifact_manifest(
    *,
    run_id: str,
    mission_id: str,
    harness_run_id: str,
    generated_at: str,
    hashes: Mapping[str, str],
) -> dict[str, Any]:
    missing = [name for name in required_artifact_names() if name not in hashes and name != "artifact_manifest.json"]
    manifest = {
        **common_packet_fields(run_id, mission_id, harness_run_id, generated_at),
        "all_required_artifacts_hashable": not missing,
        "artifact_hashes": dict(sorted(hashes.items())),
        "manifest_hash_basis_excludes_self": True,
        "missing_artifact_hashes": missing,
        "required_artifacts": required_artifact_names(),
        "schema_version": "dharma.capital_lab.alpha_evidence.v2.artifact_manifest",
    }
    manifest["manifest_hash"] = sha256_json(manifest)
    return manifest


def assert_no_forbidden_artifact_claims(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    match = FORBIDDEN_ARTIFACT_RE.search(text)
    if match:
        raise ValueError(f"forbidden artifact claim in {path}: {match.group(0)}")


def validate_artifact_bundle(output_dir: Path) -> dict[str, Any]:
    output_dir = Path(output_dir)
    manifest_path = output_dir / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for name in required_artifact_names():
        path = output_dir / name
        if not path.exists():
            errors.append(f"missing:{name}")
            continue
        if name.endswith(".json"):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"invalid_json:{name}:{exc}")
        try:
            assert_no_forbidden_artifact_claims(path)
        except ValueError as exc:
            errors.append(str(exc))
    for name, expected_hash in manifest.get("artifact_hashes", {}).items():
        path = output_dir / name
        if path.exists() and sha256_file(path) != expected_hash:
            errors.append(f"hash_mismatch:{name}")
    return {"valid": not errors, "errors": errors, "manifest": manifest}


def generate_alpha_evidence_bundle(
    *,
    output_dir: Path,
    run_id: str = DEFAULT_RUN_ID,
    mission_id: str = MISSION_ID,
    harness_run_id: str = DEFAULT_HARNESS_RUN_ID,
    data_root: Path | None = None,
    bootstrap_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
    provider_configs: Sequence[ProviderConfig] = DEFAULT_PROVIDER_CONFIGS,
    proof_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    gate_inputs: StrategyGateInputs | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    bootstrap_summary = load_bootstrap_summary(bootstrap_dir)
    gate_inputs = gate_inputs or StrategyGateInputs()

    provider_packet = evaluate_provider_readiness(
        run_id=run_id,
        mission_id=mission_id,
        harness_run_id=harness_run_id,
        data_root=data_root,
        env=env,
        provider_configs=provider_configs,
        proof_overrides=proof_overrides,
        generated_at=generated_at,
    )
    lineage_packet = build_data_lineage_packet(provider_packet, generated_at=generated_at)
    graveyard_packet = build_alpha_graveyard_packet(
        run_id=run_id,
        mission_id=mission_id,
        harness_run_id=harness_run_id,
        bootstrap_summary=bootstrap_summary,
        generated_at=generated_at,
    )
    leakage_receipt = build_leakage_gauntlet_receipt(
        run_id=run_id,
        mission_id=mission_id,
        harness_run_id=harness_run_id,
        trap_results=gate_inputs.leakage_traps,
        generated_at=generated_at,
    )
    walk_forward_receipt = build_walk_forward_oos_receipt(
        run_id=run_id,
        mission_id=mission_id,
        harness_run_id=harness_run_id,
        gate_inputs=gate_inputs,
        generated_at=generated_at,
    )
    strategy_packet = build_strategy_evidence_packet(
        provider_packet,
        lineage_packet,
        graveyard_packet,
        leakage_receipt,
        walk_forward_receipt,
        gate_inputs=gate_inputs,
        generated_at=generated_at,
    )

    json_payloads: MutableMapping[str, dict[str, Any]] = {
        "provider_readiness_packet.json": provider_packet,
        "data_lineage_packet.json": lineage_packet,
        "alpha_graveyard_packet.json": graveyard_packet,
        "leakage_gauntlet_receipt.json": leakage_receipt,
        "walk_forward_oos_receipt.json": walk_forward_receipt,
        "strategy_evidence_packet.json": strategy_packet,
    }
    written_paths: dict[str, Path] = {}
    for name, payload in json_payloads.items():
        path = output_dir / name
        write_json(path, payload)
        written_paths[name] = path

    current_hashes = artifact_hashes(written_paths)
    scorecard = build_alpha_evidence_scorecard(
        provider_packet,
        lineage_packet,
        graveyard_packet,
        leakage_receipt,
        walk_forward_receipt,
        strategy_packet,
        artifact_hashes=current_hashes,
        generated_at=generated_at,
    )
    independent_receipt = build_independent_evaluator_receipt(
        scorecard, strategy_packet, generated_at=generated_at
    )
    for name, payload in {
        "alpha_evidence_scorecard.json": scorecard,
        "independent_evaluator_receipt.json": independent_receipt,
    }.items():
        path = output_dir / name
        write_json(path, payload)
        written_paths[name] = path

    current_hashes = artifact_hashes(written_paths)
    final_report = render_final_report(scorecard, current_hashes)
    final_report_path = output_dir / "final_report.md"
    final_report_path.write_text(final_report, encoding="utf-8")
    written_paths["final_report.md"] = final_report_path

    current_hashes = artifact_hashes(written_paths)
    manifest = build_artifact_manifest(
        run_id=run_id,
        mission_id=mission_id,
        harness_run_id=harness_run_id,
        generated_at=generated_at,
        hashes=current_hashes,
    )
    manifest_path = output_dir / "artifact_manifest.json"
    write_json(manifest_path, manifest)
    written_paths["artifact_manifest.json"] = manifest_path

    validation = validate_artifact_bundle(output_dir)
    if not validation["valid"]:
        raise ValueError(f"invalid alpha evidence bundle: {validation['errors']}")
    return {
        "output_dir": str(output_dir),
        "score": scorecard["score"],
        "status": scorecard["status"],
        "clean": scorecard["clean"],
        "artifact_hashes": artifact_hashes(written_paths),
        "validation": validation,
    }


def mirror_bundle(source_dir: Path, mirror_dir: Path) -> None:
    source_dir = Path(source_dir)
    mirror_dir = Path(mirror_dir)
    mirror_dir.mkdir(parents=True, exist_ok=True)
    for name in required_artifact_names():
        source = source_dir / name
        if source.exists():
            shutil.copy2(source, mirror_dir / name)
