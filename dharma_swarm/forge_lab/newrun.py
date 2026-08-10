"""Operator-facing preview for governed Forge/RSI Lab exploration.

``rsi newrun`` projects candidate run shapes, but it is not a spend-authority
surface. Execution belongs to ``rsi campaign`` and requires a validated signed
operator envelope. The retained ``--execute`` flag fails closed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.campaign_profile import (
    PROVIDER_ATTESTATION_POLICY as PROVIDER_ATTESTATION_POLICY,
    ROLE_ROUTE_BINDINGS as ROLE_ROUTE_BINDINGS,
)
from dharma_swarm.forge_lab.newrun_presets import (
    CURRENT_MODEL_ENV_KEYS as CURRENT_MODEL_ENV_KEYS,
    DEFAULT_DIVERSE_MUTATOR,
    DEFAULT_DIVERSE_SOLVER,
    DEFAULT_DIVERSE_VERIFIER,
    DEFAULT_FAST_MUTATOR as DEFAULT_FAST_MUTATOR,
    DEFAULT_FAST_SOLVER as DEFAULT_FAST_SOLVER,
    DEFAULT_FAST_VERIFIER as DEFAULT_FAST_VERIFIER,
    GOVERNED_CAMPAIGN_COMMAND,
    GOVERNED_CAMPAIGN_REQUIRED,
    GOVERNED_CAMPAIGN_REQUIRED_EXIT,
    NewRunPreset,
    _cross_family_verifier as _cross_family_verifier,
    _family as _family,
    apply_overrides,
    build_presets,
    detect_current_model,
    select_preset,
)


NEW_RUN_SCHEMA = "rsi_lab.newrun_options.v1"
NEW_RUN_RECOMMEND_SCHEMA = "rsi_lab.newrun_recommendation.v1"
CLI_RESULT_SCHEMA = "forge_lab.cli_result.v1"


def _archive_root() -> Path:
    explicit = os.environ.get("RSILAB_EVOLUTION_ARCHIVE_ROOT", "").strip()
    if explicit:
        root = Path(explicit)
        if not root.is_absolute():
            raise ValueError("RSILAB_EVOLUTION_ARCHIVE_ROOT must be absolute")
        return root
    state = os.environ.get("RSI_LAB_STATE", "").strip()
    if state:
        state_root = Path(state)
    else:
        base = os.environ.get("RSI_LAB_BASE", "").strip()
        if not base:
            raise ValueError(
                "canonical state is unbound; set RSI_LAB_STATE or RSI_LAB_BASE"
            )
        state_root = Path(base) / "state"
    if not state_root.is_absolute():
        raise ValueError("canonical RSI Lab state root must be absolute")
    return state_root / ".dharma" / "evolution_archive" / "agent_evolution"


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _recent_runs(limit: int = 12) -> list[dict[str, Any]]:
    try:
        root = _archive_root()
    except ValueError:
        return []
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
                    "experiment_id": closeout.get("experiment_id")
                    or manifest.get("experiment_id")
                    or directory.name,
                    "manifest": manifest,
                    "closeout": closeout,
                    "mtime": mtime,
                },
            )
        )
    ordered = sorted(runs, key=lambda item: item[0], reverse=True)[:limit]
    return [row for _, row in ordered]


def _stats(run: dict[str, Any]) -> dict[str, Any]:
    closeout = run.get("closeout") or {}
    return closeout.get("stats") or {}


def _run_models(run: dict[str, Any]) -> dict[str, Any]:
    return (run.get("manifest") or {}).get("config") or {}


def _shadow_champion_evidence() -> dict[str, Any] | None:
    """Load only a fully validated paired shadow champion, if one exists."""

    from dharma_swarm.forge_lab.champion_store import ChampionStore, ChampionStoreError

    try:
        category_root = _archive_root()
        state = ChampionStore(category_root.parent, category=category_root.name).load()
    except (OSError, ValueError, ChampionStoreError):
        return None
    champion = state.get("champion")
    if not isinstance(champion, dict):
        return None
    return {
        "revision": state.get("revision"),
        "candidate_id": champion.get("candidate_id"),
        "experiment_id": champion.get("experiment_id"),
        "plan_sha256": champion.get("evaluation_plan_sha256"),
        "metadata_sha256": champion.get("metadata_sha256"),
        "evidence_tier": champion.get("evidence_tier"),
    }


def _is_diverse_route(run: dict[str, Any]) -> bool:
    cfg = _run_models(run)
    return (
        cfg.get("solver_model") == DEFAULT_DIVERSE_SOLVER
        and cfg.get("verifier_model") == DEFAULT_DIVERSE_VERIFIER
        and cfg.get("mutator_model") == DEFAULT_DIVERSE_MUTATOR
    )


def _latest_provider_selftest() -> dict[str, Any] | None:
    from dharma_swarm.forge_lab.provider_selftest import _receipt_root

    try:
        root = _receipt_root()
    except ValueError:
        return None
    if not root.exists():
        return None
    receipts = sorted(
        root.glob("*provider_selftest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in receipts:
        payload = _safe_json(path)
        if payload:
            payload.setdefault("path", str(path))
            return payload
    return None


def recommend_preset(current_model: str | None = None) -> dict[str, Any]:
    """Recommend a conservative next EXPLORE run from recent archive evidence."""

    recent = _recent_runs()
    provider = _latest_provider_selftest()
    provider_ok = bool(
        provider
        and provider.get("schema") == "rsi_lab.provider_attestation.v1"
        and int(provider.get("independent_transport_count") or 0) >= 2
    )
    champion = _shadow_champion_evidence()
    latest_diverse = next((run for run in recent if _is_diverse_route(run)), None)
    diverse_recent_negative = bool(
        latest_diverse
        and str((latest_diverse.get("closeout") or {}).get("closeout_state") or "")
        == "measured_negative"
    )

    reasons: list[str] = []
    preset = "fast"
    if not provider_ok:
        reasons.append(
            "fresh manifest-bound provider attestation with 2 independent transports is missing; "
            "only a cheap smoke may be considered"
        )
    elif champion is None:
        reasons.append(
            "no complete budget-valid paired shadow champion exists; legacy raw best scores "
            "cannot justify escalation"
        )
    elif diverse_recent_negative:
        reasons.append(
            "latest diverse lane was measured_negative; prefer current-model soak over diverse"
        )
        preset = "soak"
    else:
        champion_revision = int(champion.get("revision") or 0)
        if champion_revision >= 2:
            reasons.append(
                "provider attestation is fresh and at least two paired champion transitions "
                "are durable; diverse is allowed"
            )
            preset = "diverse"
        else:
            reasons.append(
                "one paired shadow champion is durable; collect another paired transition "
                "with a soak before diverse"
            )
            preset = "soak"

    if not reasons:
        reasons.append("default conservative smoke")
    selected = select_preset(build_presets(current_model), preset)
    return {
        "schema": NEW_RUN_RECOMMEND_SCHEMA,
        "selected_preset": preset,
        "selected": selected.as_dict(),
        "reasons": reasons,
        "provider_selftest": {
            "present": provider is not None,
            "ok": bool(provider.get("ok")) if provider else False,
            "independent_route_count": int(provider.get("independent_route_count") or 0)
            if provider
            else 0,
            "receipt": provider.get("path") or provider.get("receipt")
            if provider
            else None,
        },
        "paired_shadow_champion": champion,
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
                        "tokens_spent_total",
                    )
                },
            }
            for run in recent[:6]
        ],
    }


def add_newrun_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--preset",
        choices=("fast", "current", "diverse", "soak"),
        help="select a run preset",
    )
    parser.add_argument(
        "--recommend",
        action="store_true",
        help="inspect recent archive/provider evidence and choose a preset",
    )
    parser.add_argument("--model", help="current model id for current/soak presets")
    parser.add_argument("--solver-model", help="override solver model id")
    parser.add_argument("--verifier-model", help="override verifier model id")
    parser.add_argument("--mutator-model", help="override mutator model id")
    parser.add_argument("--generations", type=int, help="override generation count")
    parser.add_argument("--children", type=int, help="override children per generation")
    parser.add_argument("--tasks", type=int, help="override tasks per generation")
    parser.add_argument(
        "--budget-tokens",
        type=int,
        help="override per-candidate token accounting cap",
    )
    parser.add_argument(
        "--budget-usd",
        type=float,
        help="override per-candidate USD accounting cap",
    )
    parser.add_argument(
        "--max-experiment-tokens",
        type=int,
        help="override experiment token fuse",
    )
    parser.add_argument("--rng-seed", type=int, help="override RNG seed")
    parser.add_argument("--source-repo", help="source repo for scratch worktrees")
    parser.add_argument(
        "--keep-worktree",
        action="store_true",
        help="keep scratch worktree after execution",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="deprecated compatibility flag; always fails closed (use governed rsi campaign)",
    )


def _payload(args: argparse.Namespace) -> tuple[dict[str, Any], NewRunPreset | None]:
    current_model, current_source = detect_current_model(
        explicit=getattr(args, "model", None)
    )
    presets = build_presets(current_model)
    recommended = (
        recommend_preset(current_model) if getattr(args, "recommend", False) else None
    )
    preset_name = args.preset or (recommended or {}).get("selected_preset")
    selected = (
        apply_overrides(select_preset(presets, preset_name), args)
        if preset_name
        else None
    )
    payload = {
        "schema": NEW_RUN_SCHEMA,
        "current_model": current_model,
        "current_model_source": current_source,
        "safety_boundary": {
            "mode": "shadow EXPLORE",
            "execution_surface": "rsi campaign",
            "newrun_execute_supported": False,
            "signed_operator_envelope_required": True,
            "fresh_provider_attestation_required": True,
            "evaluation_protocol": "paired_frozen_v1",
            "production_mutation": False,
            "positive_lift_claim": False,
        },
        "presets": [
            preset.as_dict(
                source_repo=args.source_repo,
                keep_worktree=args.keep_worktree,
            )
            for preset in presets
        ],
        "selected": selected.as_dict(
            source_repo=args.source_repo,
            keep_worktree=args.keep_worktree,
        )
        if selected
        else None,
        "recommendation": recommended,
    }
    return payload, selected


def print_human_menu(payload: dict[str, Any]) -> None:
    print("RSI Lab NEWRUN — governed campaign preview")
    current = payload.get("current_model") or "not detected"
    source = payload.get("current_model_source") or "pass --model or set RSILAB_MODEL"
    print(f"Current model: {current} ({source})")
    print()
    print(
        "Safety: preview only; paid execution requires rsi campaign plus a "
        "validated signed operator envelope."
    )
    print()
    print("Options:")
    for index, preset in enumerate(payload["presets"], start=1):
        print(f"  {index}. {preset['name']} — {preset['label']}")
        print(f"     {preset['description']}")
        print(
            "     models: "
            f"solver={preset['solver_model']} verifier={preset['verifier_model']} "
            f"mutator={preset['mutator_model']}"
        )
        print(
            "     shape: "
            f"g={preset['generations']} children={preset['children']} "
            f"tasks={preset['tasks']} max_tokens={preset['max_experiment_tokens']}"
        )
        print(f"     governed plan: {preset['command']}")
        for note in preset.get("notes", []):
            print(f"       note: {note}")
        print()
    print("Examples:")
    print("  RSILAB - NEWRUN --recommend")
    print("  rsi newrun --model glm-5.2 --preset soak")
    print(f"  {GOVERNED_CAMPAIGN_COMMAND}")


def run_newrun(args: argparse.Namespace) -> int:
    payload, selected = _payload(args)
    if args.execute:
        message = (
            "rsi newrun is preview-only; execution requires a "
            "content-addressed governed campaign and validated signed "
            "operator envelope"
        )
        error = {
            "schema": CLI_RESULT_SCHEMA,
            "ok": False,
            "command": "newrun",
            "error": {"code": GOVERNED_CAMPAIGN_REQUIRED, "message": message},
            "result": {
                "selected_preset": selected.name if selected else None,
                "governed_entrypoint": GOVERNED_CAMPAIGN_COMMAND,
            },
        }
        if args.json:
            print(json.dumps(error, sort_keys=True))
        print(
            f"rsi newrun failed [{GOVERNED_CAMPAIGN_REQUIRED}]: {message}; "
            f"next: {GOVERNED_CAMPAIGN_COMMAND}",
            file=sys.stderr,
        )
        return GOVERNED_CAMPAIGN_REQUIRED_EXIT

    if args.json:
        print(json.dumps({"ok": True, **payload}, indent=2, sort_keys=True))
        return 0
    if not selected:
        print_human_menu(payload)
        return 0
    print_human_menu(payload)
    recommendation = payload.get("recommendation") or {}
    if recommendation:
        print("Recommendation:")
        print(f"  selected: {recommendation.get('selected_preset')}")
        for reason in recommendation.get("reasons", []):
            print(f"  reason: {reason}")
    print(f"Selected preset: {selected.name}")
    print(f"Governed planning entrypoint: {selected.command()}")
    return 0
