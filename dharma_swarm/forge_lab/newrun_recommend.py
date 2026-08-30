"""Evidence-backed preset recommendation for ``rsi newrun --recommend``.

Split out of ``newrun`` to keep both modules under the repo's 500-line budget
(CLAUDE.md law; SOVEREIGN_MANIFEST axiom A5). The parent module re-exports
``recommend_preset``; parent-owned preset constants are imported lazily at
call time so the dependency stays one-directional.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.state_io import dharma_home, provider_selftest_root

NEW_RUN_RECOMMEND_SCHEMA = "rsi_lab.newrun_recommendation.v1"


def _archive_root() -> Path:
    return Path(
        os.environ.get(
            "RSILAB_EVOLUTION_ARCHIVE_ROOT",
            dharma_home() / "evolution_archive" / "agent_evolution",
        )
    )


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
        mtime = max(
            manifest_path.stat().st_mtime if manifest_path.exists() else 0,
            closeout_path.stat().st_mtime if closeout_path.exists() else 0,
        )
        manifest = _safe_json(manifest_path) if manifest_path.exists() else {}
        closeout = _safe_json(closeout_path) if closeout_path.exists() else {}
        runs.append(
            (
                mtime,
                {
                    "path": str(directory),
                    "experiment_id": closeout.get("experiment_id") or manifest.get("experiment_id") or directory.name,
                    "manifest": manifest,
                    "closeout": closeout,
                    "mtime": mtime,
                },
            )
        )
    return [row for _, row in sorted(runs, key=lambda item: item[0], reverse=True)[:limit]]


def _stats(run: dict[str, Any]) -> dict[str, Any]:
    closeout = run.get("closeout") or {}
    return closeout.get("stats") or {}


def _run_models(run: dict[str, Any]) -> dict[str, Any]:
    return ((run.get("manifest") or {}).get("config") or {})


def _best_minus_seed(run: dict[str, Any]) -> float:
    stats = _stats(run)
    try:
        return float(stats.get("best_pass_rate", 0) or 0) - float(stats.get("seed_pass_rate", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _has_archive_movement(run: dict[str, Any]) -> bool:
    stats = _stats(run)
    closeout_state = str((run.get("closeout") or {}).get("closeout_state") or "")
    try:
        best = float(stats.get("best_pass_rate", 0) or 0)
    except (TypeError, ValueError):
        best = 0.0
    return closeout_state in {"inconclusive_low_power", "measured_negative"} and (
        _best_minus_seed(run) > 0 or best > 0
    )


def _is_diverse_route(run: dict[str, Any]) -> bool:
    from dharma_swarm.forge_lab.newrun import (
        DEFAULT_DIVERSE_MUTATOR,
        DEFAULT_DIVERSE_SOLVER,
        DEFAULT_DIVERSE_VERIFIER,
    )

    cfg = _run_models(run)
    return (
        cfg.get("solver_model") == DEFAULT_DIVERSE_SOLVER
        and cfg.get("verifier_model") == DEFAULT_DIVERSE_VERIFIER
        and cfg.get("mutator_model") == DEFAULT_DIVERSE_MUTATOR
    )


def _is_fast_route(run: dict[str, Any]) -> bool:
    from dharma_swarm.forge_lab.newrun import (
        DEFAULT_FAST_MUTATOR,
        DEFAULT_FAST_SOLVER,
        DEFAULT_FAST_VERIFIER,
    )

    cfg = _run_models(run)
    return (
        cfg.get("solver_model") == DEFAULT_FAST_SOLVER
        and cfg.get("verifier_model") == DEFAULT_FAST_VERIFIER
        and cfg.get("mutator_model") == DEFAULT_FAST_MUTATOR
    )


def _latest_provider_selftest() -> dict[str, Any] | None:
    root = provider_selftest_root()
    if not root.exists():
        return None
    receipts = sorted(root.glob("*provider_selftest.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in receipts:
        payload = _safe_json(path)
        if payload:
            payload.setdefault("path", str(path))
            return payload
    return None


def recommend_preset(current_model: str | None = None) -> dict[str, Any]:
    """Recommend a conservative next EXPLORE run from recent archive evidence.

    This is deliberately not a statistical promotion rule. It is an operator
    convenience for deciding which *shadow EXPLORE* preset should run next.
    """

    recent = _recent_runs()
    provider = _latest_provider_selftest()
    provider_ok = bool(provider and provider.get("ok") and int(provider.get("independent_route_count") or 0) >= 2)
    latest_fast = next((run for run in recent if _is_fast_route(run)), None)
    latest_diverse = next((run for run in recent if _is_diverse_route(run)), None)
    fast_moved = bool(latest_fast and _has_archive_movement(latest_fast))
    diverse_recent_negative = bool(
        latest_diverse
        and str((latest_diverse.get("closeout") or {}).get("closeout_state") or "") == "measured_negative"
    )

    reasons: list[str] = []
    preset = "fast"
    if not provider_ok:
        reasons.append("provider health is missing or below 2 independent callable families; start with cheap smoke")
        preset = "fast"
    elif not fast_moved:
        reasons.append("latest fast lane has no positive archive movement; rerun cheap smoke before soaking")
        preset = "fast"
    elif diverse_recent_negative:
        reasons.append("latest diverse lane was measured_negative; prefer current-model soak over diverse")
        preset = "soak"
    else:
        recent_movers = [run for run in recent[:4] if _has_archive_movement(run)]
        if len(recent_movers) >= 2:
            reasons.append("provider health is clean and at least two recent runs show archive movement; diverse is allowed")
            preset = "diverse"
        else:
            reasons.append("fast lane moved; collect more depth with soak before diverse")
            preset = "soak"

    if not reasons:
        reasons.append("default conservative smoke")
    from dharma_swarm.forge_lab.newrun import build_presets, select_preset

    presets = build_presets(current_model)
    selected = select_preset(presets, preset)
    return {
        "schema": NEW_RUN_RECOMMEND_SCHEMA,
        "selected_preset": preset,
        "selected": selected.as_dict(),
        "reasons": reasons,
        "provider_selftest": {
            "present": provider is not None,
            "ok": bool(provider.get("ok")) if provider else False,
            "independent_route_count": int(provider.get("independent_route_count") or 0) if provider else 0,
            "receipt": provider.get("path") or provider.get("receipt") if provider else None,
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
                    for key in ("seed_pass_rate", "best_pass_rate", "tokens_spent_total")
                },
            }
            for run in recent[:6]
        ],
    }
