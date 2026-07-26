"""Recommendation helpers for ``rsi newrun``."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.newrun import (
    DEFAULT_DIVERSE_MUTATOR,
    DEFAULT_DIVERSE_SOLVER,
    DEFAULT_DIVERSE_VERIFIER,
    DEFAULT_FAST_MUTATOR,
    DEFAULT_FAST_SOLVER,
    DEFAULT_FAST_VERIFIER,
    NEW_RUN_RECOMMEND_SCHEMA,
    NewRunPreset,
    build_presets,
)

PROVIDER_SELFTEST_SCHEMA = "rsi_lab.provider_selftest.v1"
DEFAULT_PROVIDER_EVIDENCE_MAX_AGE_S = 24 * 60 * 60


def _archive_root() -> Path:
    return Path(os.environ.get("RSILAB_EVOLUTION_ARCHIVE_ROOT", Path.home() / ".dharma" / "evolution_archive" / "agent_evolution"))


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _recent_runs(limit: int = 12) -> list[dict[str, Any]]:
    root = _archive_root()
    if not root.exists():
        return []
    runs: list[tuple[float, dict[str, Any]]] = []
    for directory in root.iterdir():
        if not directory.is_dir():
            continue
        manifest_path = directory / "run_manifest.json"
        closeout_path = directory / "closeout.json"
        if not manifest_path.exists() and not closeout_path.exists():
            continue
        mtime = max(manifest_path.stat().st_mtime if manifest_path.exists() else 0, closeout_path.stat().st_mtime if closeout_path.exists() else 0)
        manifest = _safe_json(manifest_path) if manifest_path.exists() else {}
        closeout = _safe_json(closeout_path) if closeout_path.exists() else {}
        runs.append((mtime, {"path": str(directory), "experiment_id": closeout.get("experiment_id") or manifest.get("experiment_id") or directory.name, "manifest": manifest, "closeout": closeout, "mtime": mtime}))
    return [row for _, row in sorted(runs, key=lambda item: item[0], reverse=True)[:limit]]


def _stats(run: dict[str, Any]) -> dict[str, Any]:
    return (run.get("closeout") or {}).get("stats") or {}


def _run_models(run: dict[str, Any]) -> dict[str, Any]:
    return ((run.get("manifest") or {}).get("config") or {})


def _has_descriptive_movement(run: dict[str, Any]) -> bool:
    """Return only an admitted descriptive configuration-score increase.

    Older closeouts lack these fields and therefore fail closed. In particular,
    a best pass rate above zero is not enough: it may be a saturated one-task
    panel or a metadata-only mutation whose executed phenotype never changed.
    This is L0 configuration-search evidence, never paired lift.
    """

    stats = _stats(run)
    try:
        executed_changes = int(stats.get("executed_phenotype_changes") or 0)
        observed_delta = float(stats.get("observed_best_delta") or 0)
        unique_task_ids = int(stats.get("unique_task_ids") or 0)
    except (TypeError, ValueError):
        return False
    return (
        stats.get("descriptive_movement_eligible") is True
        and stats.get("evidence_level") == "L0_LegacyConfigurationSignal"
        and stats.get("research_interpretation") == "configuration_search_signal"
        and stats.get("paired_lift_claim_eligible") is False
        and stats.get("authority_granted") is False
        and stats.get("same_panel_comparable") is True
        and executed_changes > 0
        and unique_task_ids >= 3
        and stats.get("seed_panel_saturated") is False
        and observed_delta > 0
    )


def _has_archive_movement(run: dict[str, Any]) -> bool:
    """Compatibility alias for the pre-L0-typing helper name."""

    return _has_descriptive_movement(run)


def _is_diverse_route(run: dict[str, Any]) -> bool:
    cfg = _run_models(run)
    return cfg.get("solver_model") == DEFAULT_DIVERSE_SOLVER and cfg.get("verifier_model") == DEFAULT_DIVERSE_VERIFIER and cfg.get("mutator_model") == DEFAULT_DIVERSE_MUTATOR


def _is_fast_route(run: dict[str, Any]) -> bool:
    cfg = _run_models(run)
    return cfg.get("solver_model") == DEFAULT_FAST_SOLVER and cfg.get("verifier_model") == DEFAULT_FAST_VERIFIER and cfg.get("mutator_model") == DEFAULT_FAST_MUTATOR


def _provider_receipts() -> list[dict[str, Any]]:
    root = Path(os.environ.get("RSI_LAB_PROVIDER_SELFTEST_ROOT", Path.home() / ".dharma" / "forge_lab" / "provider_selftests"))
    if not root.exists():
        return []
    now_raw = os.environ.get("RSI_LAB_PROVIDER_SELFTEST_NOW", "").strip()
    now = _parse_timestamp(now_raw) if now_raw else datetime.now(timezone.utc)
    if now is None:
        now = datetime.now(timezone.utc)
    try:
        max_age_s = max(
            0,
            int(
                os.environ.get(
                    "RSI_LAB_PROVIDER_SELFTEST_MAX_AGE_S",
                    DEFAULT_PROVIDER_EVIDENCE_MAX_AGE_S,
                )
            ),
        )
    except (TypeError, ValueError):
        max_age_s = DEFAULT_PROVIDER_EVIDENCE_MAX_AGE_S
    receipts: list[dict[str, Any]] = []
    for path in root.glob("*provider_selftest.json"):
        payload = _safe_json(path)
        checked_at = _parse_timestamp(str(payload.get("checked_at") or ""))
        if (
            not payload
            or payload.get("schema") != PROVIDER_SELFTEST_SCHEMA
            or payload.get("live") is not True
            or checked_at is None
        ):
            continue
        raw_age_s = (now - checked_at).total_seconds()
        age_s = max(0.0, raw_age_s)
        payload.setdefault("path", str(path))
        payload["_mtime"] = path.stat().st_mtime
        payload["_age_seconds"] = round(age_s, 3)
        payload["_fresh"] = -300 <= raw_age_s <= max_age_s
        payload["_max_age_seconds"] = max_age_s
        receipts.append(payload)
    return sorted(
        receipts,
        key=lambda payload: (
            str(payload.get("checked_at") or ""),
            float(payload.get("_mtime") or 0),
            str(payload.get("path") or ""),
        ),
        reverse=True,
    )


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _latest_route_evidence(
    receipts: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Project the newest live result for every exact model id.

    A newer failure intentionally shadows an older success. Aggregate receipt
    health and family counts cannot stand in for a callable exact route.
    """

    routes: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        if receipt.get("_fresh") is not True:
            continue
        for row in receipt.get("rows") or []:
            if not isinstance(row, dict):
                continue
            model_id = str(row.get("model_id") or "").strip()
            if not model_id or model_id in routes:
                continue
            callable_exact = (
                row.get("live") is True
                and row.get("callable") is True
                and str(row.get("outcome") or "") == "callable"
                and str(row.get("stage") or "") == "complete"
            )
            routes[model_id] = {
                "callable": callable_exact,
                "outcome": row.get("outcome"),
                "stage": row.get("stage"),
                "error_type": row.get("error_type"),
                "checked_at": receipt.get("checked_at"),
                "age_seconds": receipt.get("_age_seconds"),
                "fresh": True,
                "receipt": receipt.get("path") or receipt.get("receipt"),
                "host_bound": bool(receipt.get("execution_host")),
                "code_bound": bool(receipt.get("source_commit")),
            }
    return routes


def _preset_route_status(
    preset: NewRunPreset,
    routes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    models = list(
        dict.fromkeys(
            (
                preset.solver_model,
                preset.verifier_model,
                preset.mutator_model,
            )
        )
    )
    missing = [model for model in models if model not in routes]
    unavailable = [
        model
        for model in models
        if model in routes and routes[model].get("callable") is not True
    ]
    observed_callable = not missing and not unavailable
    return {
        "callable": observed_callable,
        "observed_callable": observed_callable,
        "host_bound": observed_callable
        and all(routes[model].get("host_bound") is True for model in models),
        "code_bound": observed_callable
        and all(routes[model].get("code_bound") is True for model in models),
        "models": models,
        "missing": missing,
        "unavailable": unavailable,
    }


def recommend_preset(current_model: str | None = None) -> dict[str, Any]:
    """Recommend a conservative next shadow EXPLORE run."""

    recent = _recent_runs()
    receipts = _provider_receipts()
    routes = _latest_route_evidence(receipts)
    latest_fast = next((run for run in recent if _is_fast_route(run)), None)
    latest_diverse = next((run for run in recent if _is_diverse_route(run)), None)
    fast_descriptive_movement = bool(
        latest_fast and _has_descriptive_movement(latest_fast)
    )
    diverse_recent_negative = bool(latest_diverse and str((latest_diverse.get("closeout") or {}).get("closeout_state") or "") == "measured_negative")
    recent_descriptive_movers = [
        run for run in recent[:4] if _has_descriptive_movement(run)
    ]
    presets = build_presets(current_model)
    route_status = {
        preset.name: _preset_route_status(preset, routes)
        for preset in presets
    }
    reasons: list[str] = []

    # The signal lane is first when fresh exact-route observations cover its
    # cloud trio: it spends its L0 budget on five same-panel adaptive-search
    # tasks rather than the legacy diverse lane's candidate churn.
    if not fast_descriptive_movement:
        preferred = ["signal", "fast", "current", "soak", "diverse"]
        reasons.append(
            "no recent run records an eligible same-panel positive descriptive "
            "configuration delta; prefer the five-task signal panel"
        )
    elif diverse_recent_negative:
        preferred = ["signal", "soak", "fast", "current", "diverse"]
        reasons.append(
            "latest diverse lane was measured_negative; prefer the bounded signal panel"
        )
    elif len(recent_descriptive_movers) >= 2:
        preferred = ["signal", "diverse", "soak", "fast", "current"]
        reasons.append(
            "recent descriptive configuration movement is recorded, but the "
            "five-task signal panel remains the conservative next measurement"
        )
    else:
        preferred = ["signal", "soak", "fast", "current", "diverse"]
        reasons.append(
            "one recent run records descriptive movement; collect a broader "
            "same-panel comparison before candidate churn"
        )

    selected = next(
        (
            preset
            for name in preferred
            for preset in presets
            if preset.name == name and route_status[name]["callable"]
        ),
        None,
    )
    if selected is None:
        missing_models = sorted(
            {
                model
                for status in route_status.values()
                for model in (*status["missing"], *status["unavailable"])
            }
        )
        reasons.append(
            "no preset has explicit callable evidence for every exact solver, verifier, "
            "and mutator route; run `rsi provider selftest --profile newrun --live`"
        )
        if missing_models:
            reasons.append(
                "unproven or unavailable exact routes: " + ", ".join(missing_models)
            )
    else:
        selected_status = route_status[selected.name]
        binding = (
            "host/code-bound observations"
            if selected_status["host_bound"] and selected_status["code_bound"]
            else "advisory observations without complete host/code binding"
        )
        reasons.append(
            f"selected {selected.name} from fresh exact-route {binding}"
        )

    latest_provider = receipts[0] if receipts else None
    selected_status = route_status.get(selected.name) if selected else None
    return {
        "schema": NEW_RUN_RECOMMEND_SCHEMA,
        "selected_preset": selected.name if selected else None,
        "selected": selected.as_dict() if selected else None,
        "reasons": reasons or ["default conservative smoke"],
        "provider_selftest": {
            "present": bool(receipts),
            "scanned_receipts": len(receipts),
            "max_age_seconds": (
                int(latest_provider.get("_max_age_seconds"))
                if latest_provider
                else DEFAULT_PROVIDER_EVIDENCE_MAX_AGE_S
            ),
            "ok": (
                bool(latest_provider.get("ok"))
                if latest_provider
                else False
            ),
            "independent_route_count": (
                int(latest_provider.get("independent_route_count") or 0)
                if latest_provider
                else 0
            ),
            "receipt": (
                latest_provider.get("path") or latest_provider.get("receipt")
                if latest_provider
                else None
            ),
            "routes": routes,
            "preset_route_status": route_status,
            "advisory_only": True,
            "host_bound": bool(
                selected_status and selected_status.get("host_bound")
            ),
            "code_bound": bool(
                selected_status and selected_status.get("code_bound")
            ),
        },
        "recent_runs": [
            {
                "experiment_id": run.get("experiment_id"),
                "path": run.get("path"),
                "closeout_state": (run.get("closeout") or {}).get("closeout_state"),
                "models": {
                    key: _run_models(run).get(key)
                    for key in ("solver_model", "verifier_model", "mutator_model")
                },
                "stats": {
                    key: _stats(run).get(key)
                    for key in (
                        "seed_pass_rate",
                        "best_pass_rate",
                        "reported_tokens_lower_bound",
                        "usage_completeness",
                        "same_panel_comparable",
                        "executed_phenotype_changes",
                        "unique_task_ids",
                        "seed_panel_saturated",
                        "observed_best_delta",
                        "descriptive_movement_eligible",
                        "evidence_level",
                    )
                },
            }
            for run in recent[:6]
        ],
    }
