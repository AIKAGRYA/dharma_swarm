"""Operator-facing preview for governed Forge/RSI Lab exploration.

``rsi newrun`` projects candidate run shapes, but it is not a spend-authority
surface. Execution belongs to ``rsi campaign`` and requires a validated signed
operator envelope. The retained ``--execute`` flag fails closed so old
automation cannot silently fall through to the legacy live launcher.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, replace
from typing import Any, Iterable

NEW_RUN_SCHEMA = "rsi_lab.newrun_options.v1"
NEW_RUN_RECOMMEND_SCHEMA = "rsi_lab.newrun_recommendation.v1"
CLI_RESULT_SCHEMA = "forge_lab.cli_result.v1"
GOVERNED_CAMPAIGN_REQUIRED = "GOVERNED_CAMPAIGN_REQUIRED"
GOVERNED_CAMPAIGN_REQUIRED_EXIT = 7
GOVERNED_CAMPAIGN_COMMAND = (
    "rsi campaign plan --profile forge-lab-n30-to-1000-v1"
)

CURRENT_MODEL_ENV_KEYS = (
    "RSILAB_MODEL",
    "RSI_MODEL",
    "FORGE_MODEL",
    "CODEX_MODEL",
    "MODEL",
)

DEFAULT_FAST_SOLVER = "kimi-code"
DEFAULT_FAST_VERIFIER = "glm-5.2"
DEFAULT_FAST_MUTATOR = "gemini-2.5-flash"
# The broad diversity preset must use exact slot-resolvable route IDs. Bare
# deepseek-v4-pro/minimax-m3 route through the OpenAI-compatible fallback and 404
# on this Mac; the :cloud IDs are the verified Ollama Cloud frontier routes.
DEFAULT_DIVERSE_SOLVER = "deepseek-v4-pro:cloud"
DEFAULT_DIVERSE_VERIFIER = "minimax-m3:cloud"
DEFAULT_DIVERSE_MUTATOR = "kimi-k2.7-code:cloud"


@dataclass(frozen=True)
class NewRunPreset:
    """A compact operator choice plus the exact Forge Lab run shape."""

    name: str
    label: str
    description: str
    solver_model: str
    verifier_model: str
    mutator_model: str
    generations: int
    children: int
    tasks: int
    budget_tokens: int
    budget_usd: float
    max_experiment_tokens: int
    novelty_pressure: float = 0.7
    propose_timeout: int = 240
    grade_timeout: int = 600
    rng_seed: int = 20260723
    notes: tuple[str, ...] = ()

    def forge_args(self, *, source_repo: str | None = None, keep_worktree: bool = False) -> list[str]:
        args = [
            "run",
            "--mode",
            "shadow",
            "--category",
            "agent",
            "--generations",
            str(self.generations),
            "--children",
            str(self.children),
            "--tasks",
            str(self.tasks),
            "--novelty-pressure",
            str(self.novelty_pressure),
            "--solver-model",
            self.solver_model,
            "--verifier-model",
            self.verifier_model,
            "--mutator-model",
            self.mutator_model,
            "--budget-tokens",
            str(self.budget_tokens),
            "--budget-usd",
            str(self.budget_usd),
            "--max-experiment-tokens",
            str(self.max_experiment_tokens),
            "--propose-timeout",
            str(self.propose_timeout),
            "--grade-timeout",
            str(self.grade_timeout),
            "--rng-seed",
            str(self.rng_seed),
        ]
        if source_repo:
            args.extend(["--source-repo", source_repo])
        if keep_worktree:
            args.append("--keep-worktree")
        return args

    def command(self, *, source_repo: str | None = None, keep_worktree: bool = False) -> str:
        """Return the governed planning entrypoint, never a legacy live command."""

        del source_repo, keep_worktree
        return GOVERNED_CAMPAIGN_COMMAND

    def as_dict(self, *, source_repo: str | None = None, keep_worktree: bool = False) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "solver_model": self.solver_model,
            "verifier_model": self.verifier_model,
            "mutator_model": self.mutator_model,
            "generations": self.generations,
            "children": self.children,
            "tasks": self.tasks,
            "budget_tokens": self.budget_tokens,
            "budget_usd": self.budget_usd,
            "max_experiment_tokens": self.max_experiment_tokens,
            "novelty_pressure": self.novelty_pressure,
            "propose_timeout": self.propose_timeout,
            "grade_timeout": self.grade_timeout,
            "rng_seed": self.rng_seed,
            "notes": list(self.notes),
            "command": self.command(source_repo=source_repo, keep_worktree=keep_worktree),
        }


def _family(model_id: str) -> str:
    mid = (model_id or "").strip().lower()
    if mid.startswith(("glm", "zai/", "z-ai/")):
        return "glm"
    if mid.startswith(("kimi", "moonshot")) or "kimi" in mid:
        return "kimi"
    if mid.startswith("gemini"):
        return "gemini"
    if mid.startswith("deepseek"):
        return "deepseek"
    if mid.startswith("minimax"):
        return "minimax"
    if mid.startswith("qwen") or "qwen" in mid:
        return "qwen"
    if mid.startswith(("gpt", "o1", "o3")):
        return "openai"
    if mid.startswith(("claude", "opus", "sonnet")):
        return "anthropic"
    if mid.startswith(("meta/", "nvidia/")) or "llama" in mid:
        return "llama"
    return mid.split("/", 1)[0].split(":", 1)[0] or "unknown"


def _cross_family_verifier(model_id: str | None) -> str:
    if not model_id:
        return DEFAULT_FAST_VERIFIER
    return "kimi-code" if _family(model_id) == "glm" else DEFAULT_FAST_VERIFIER


def detect_current_model(env: dict[str, str] | None = None, explicit: str | None = None) -> tuple[str | None, str | None]:
    """Return ``(model_id, source)`` from an explicit flag or common env names."""

    if explicit and explicit.strip():
        return explicit.strip(), "--model"
    env = env or os.environ
    for key in CURRENT_MODEL_ENV_KEYS:
        value = env.get(key, "").strip()
        if value:
            return value, key
    return None, None


def build_presets(current_model: str | None = None) -> list[NewRunPreset]:
    """Build the bleeding-edge run menu, adapting one row to the active model."""

    current = current_model.strip() if current_model else ""
    current_or_fast = current or DEFAULT_FAST_SOLVER
    current_label = f"current model: {current}" if current else "default fast model lane"
    return [
        NewRunPreset(
            name="fast",
            label="Fast frontier smoke",
            description=(
                "Lowest-friction live EXPLORE run: one generation, one child, one task. "
                "Use this to keep the lab moving and verify the current route still works."
            ),
            solver_model=DEFAULT_FAST_SOLVER,
            verifier_model=DEFAULT_FAST_VERIFIER,
            mutator_model=DEFAULT_FAST_MUTATOR,
            generations=1,
            children=1,
            tasks=1,
            budget_tokens=120_000,
            budget_usd=2.0,
            max_experiment_tokens=220_000,
            rng_seed=20260723,
            notes=(
                "Matches the latest successful local low-power shape: Kimi solve, GLM verify, Gemini mutate.",
                "Good default when you want one fresh receipt without a long soak.",
            ),
        ),
        NewRunPreset(
            name="current",
            label="Use my current model",
            description=(
                "Route solver and mutator through the model you are already using, "
                "with a cross-family verifier when possible."
            ),
            solver_model=current_or_fast,
            verifier_model=_cross_family_verifier(current_or_fast),
            mutator_model=current_or_fast,
            generations=1,
            children=1,
            tasks=1,
            budget_tokens=120_000,
            budget_usd=2.0,
            max_experiment_tokens=260_000,
            rng_seed=20260724,
            notes=(current_label, "Pass --model <id> or set RSILAB_MODEL/RSI_MODEL/FORGE_MODEL/CODEX_MODEL."),
        ),
        NewRunPreset(
            name="diverse",
            label="Diverse frontier n=3",
            description=(
                "A wider open-compute run with distinct solver/verifier/mutator families. "
                "Use when fast smoke is green and you want archive diversity."
            ),
            solver_model=DEFAULT_DIVERSE_SOLVER,
            verifier_model=DEFAULT_DIVERSE_VERIFIER,
            mutator_model=DEFAULT_DIVERSE_MUTATOR,
            generations=3,
            children=3,
            tasks=3,
            budget_tokens=120_000,
            budget_usd=2.0,
            max_experiment_tokens=1_200_000,
            rng_seed=20260725,
            notes=(
                "Higher spend and wall time; still EXPLORE-only and not a promotion claim.",
                "Local July 21 run of this shape was measured_negative; rerun only after route health improves.",
            ),
        ),
        NewRunPreset(
            name="soak",
            label="Current-model soak",
            description=(
                "Two generations and two children using your current model as mutator/solver. "
                "This is the one to leave running after a smoke pass."
            ),
            solver_model=current_or_fast,
            verifier_model=_cross_family_verifier(current_or_fast),
            mutator_model=current_or_fast,
            generations=2,
            children=2,
            tasks=2,
            budget_tokens=120_000,
            budget_usd=2.0,
            max_experiment_tokens=700_000,
            rng_seed=20260726,
            notes=("Good middle path between fast smoke and diverse n=3.", current_label),
        ),
    ]


def select_preset(presets: Iterable[NewRunPreset], name: str) -> NewRunPreset:
    for preset in presets:
        if preset.name == name:
            return preset
    choices = ", ".join(p.name for p in presets)
    raise ValueError(f"unknown newrun preset {name!r}; choose one of: {choices}")


def apply_overrides(preset: NewRunPreset, args: argparse.Namespace) -> NewRunPreset:
    updates: dict[str, Any] = {}
    for attr, arg_name in (
        ("solver_model", "solver_model"),
        ("verifier_model", "verifier_model"),
        ("mutator_model", "mutator_model"),
        ("generations", "generations"),
        ("children", "children"),
        ("tasks", "tasks"),
        ("budget_tokens", "budget_tokens"),
        ("budget_usd", "budget_usd"),
        ("max_experiment_tokens", "max_experiment_tokens"),
        ("rng_seed", "rng_seed"),
    ):
        value = getattr(args, arg_name, None)
        if value is not None:
            updates[attr] = value
    return replace(preset, **updates) if updates else preset



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
    cfg = _run_models(run)
    return (
        cfg.get("solver_model") == DEFAULT_DIVERSE_SOLVER
        and cfg.get("verifier_model") == DEFAULT_DIVERSE_VERIFIER
        and cfg.get("mutator_model") == DEFAULT_DIVERSE_MUTATOR
    )


def _is_fast_route(run: dict[str, Any]) -> bool:
    cfg = _run_models(run)
    return (
        cfg.get("solver_model") == DEFAULT_FAST_SOLVER
        and cfg.get("verifier_model") == DEFAULT_FAST_VERIFIER
        and cfg.get("mutator_model") == DEFAULT_FAST_MUTATOR
    )


def _latest_provider_selftest() -> dict[str, Any] | None:
    from dharma_swarm.forge_lab.provider_selftest import _receipt_root

    try:
        root = _receipt_root()
    except ValueError:
        return None
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

def add_newrun_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preset", choices=("fast", "current", "diverse", "soak"), help="select a run preset")
    parser.add_argument("--recommend", action="store_true", help="inspect recent archive/provider evidence and choose a preset")
    parser.add_argument("--model", help="current model id to use for the current/soak presets")
    parser.add_argument("--solver-model", help="override solver model id")
    parser.add_argument("--verifier-model", help="override verifier model id")
    parser.add_argument("--mutator-model", help="override mutator model id")
    parser.add_argument("--generations", type=int, help="override generation count")
    parser.add_argument("--children", type=int, help="override children per generation")
    parser.add_argument("--tasks", type=int, help="override tasks per generation")
    parser.add_argument("--budget-tokens", type=int, help="override per-candidate token accounting cap")
    parser.add_argument("--budget-usd", type=float, help="override per-candidate USD accounting cap")
    parser.add_argument("--max-experiment-tokens", type=int, help="override experiment token fuse")
    parser.add_argument("--rng-seed", type=int, help="override RNG seed")
    parser.add_argument("--source-repo", help="source repo for scratch worktrees; defaults to the Forge CLI default")
    parser.add_argument("--keep-worktree", action="store_true", help="keep scratch worktree after execution")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="deprecated compatibility flag; always fails closed (use governed rsi campaign)",
    )


def _payload(args: argparse.Namespace) -> tuple[dict[str, Any], NewRunPreset | None]:
    current_model, current_source = detect_current_model(explicit=getattr(args, "model", None))
    presets = build_presets(current_model)
    recommended = recommend_preset(current_model) if getattr(args, "recommend", False) else None
    preset_name = args.preset or (recommended or {}).get("selected_preset")
    selected = apply_overrides(select_preset(presets, preset_name), args) if preset_name else None
    payload = {
        "schema": NEW_RUN_SCHEMA,
        "current_model": current_model,
        "current_model_source": current_source,
        "safety_boundary": {
            "mode": "shadow EXPLORE",
            "execution_surface": "rsi campaign",
            "newrun_execute_supported": False,
            "signed_operator_envelope_required": True,
            "production_mutation": False,
            "positive_lift_claim": False,
        },
        "presets": [
            p.as_dict(source_repo=args.source_repo, keep_worktree=args.keep_worktree)
            for p in presets
        ],
        "selected": selected.as_dict(source_repo=args.source_repo, keep_worktree=args.keep_worktree) if selected else None,
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
            f"solver={preset['solver_model']} verifier={preset['verifier_model']} mutator={preset['mutator_model']}"
        )
        print(
            "     shape: "
            f"g={preset['generations']} children={preset['children']} tasks={preset['tasks']} "
            f"max_tokens={preset['max_experiment_tokens']}"
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
            "error": {
                "code": GOVERNED_CAMPAIGN_REQUIRED,
                "message": message,
            },
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
