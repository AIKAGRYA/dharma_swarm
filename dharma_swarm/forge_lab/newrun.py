"""One-command run planner for sustained Forge/RSI Lab exploration.

``rsi newrun`` is intentionally an operator-facing *menu* first and a live
launcher only when ``--execute`` is supplied.  The generated commands are all
shadow-mode EXPLORE runs: they can spend model tokens, write isolated lab
receipts, and create scratch worktrees, but they do not promote candidates or
mutate production state.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.model_pool import (
    FORGE_KIMI_K3_OPENROUTER_MODEL_ID,
    forge_high_slot_model_ids,
)
from dharma_swarm.forge_lab.newrun_recommend import (
    NEW_RUN_RECOMMEND_SCHEMA as NEW_RUN_RECOMMEND_SCHEMA,
    recommend_preset,
)

NEW_RUN_SCHEMA = "rsi_lab.newrun_options.v1"
SOURCE_REFUSAL_EXIT = 7

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


def _model_pool_cloud_route(family: str) -> str:
    """Resolve a high-slot cloud route without duplicating model IDs here."""

    for model_id in forge_high_slot_model_ids():
        if model_id.casefold().startswith(family) and model_id.endswith(":cloud"):
            return model_id
    raise RuntimeError(f"model pool has no cloud route for family={family!r}")


# Broad diversity is projected from the canonical model pool.  Bare family
# routes can select incompatible OpenAI-style fallbacks; the pool owns the
# exact provider-resolvable cloud IDs.
DEFAULT_DIVERSE_SOLVER = _model_pool_cloud_route("deepseek")
DEFAULT_DIVERSE_VERIFIER = _model_pool_cloud_route("minimax")
DEFAULT_DIVERSE_MUTATOR = FORGE_KIMI_K3_OPENROUTER_MODEL_ID


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
        return "python -m dharma_swarm.forge_lab.cli " + " ".join(
            shlex.quote(part) for part in self.forge_args(source_repo=source_repo, keep_worktree=keep_worktree)
        )

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
    parser.add_argument("--execute", action="store_true", help="run the selected preset now; this can spend live model tokens")


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
            "live_model_spend_requires_execute": True,
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
    print("RSI Lab NEWRUN — bleeding-edge run menu")
    current = payload.get("current_model") or "not detected"
    source = payload.get("current_model_source") or "pass --model or set RSILAB_MODEL"
    print(f"Current model: {current} ({source})")
    print()
    print("Safety: shadow EXPLORE only; --execute can spend model tokens; no production mutation; no positive-lift claim.")
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
        print(f"     run: rsi newrun --preset {preset['name']} --execute")
        print(f"     underlying: {preset['command']}")
        for note in preset.get("notes", []):
            print(f"       note: {note}")
        print()
    print("Examples:")
    print("  RSILAB - NEWRUN --recommend")
    print("  RSILAB - NEWRUN --preset fast --execute")
    print("  rsi newrun --model glm-5.2 --preset soak --execute")
    print("  rsi newrun --preset current --model claude-opus-4-6 --execute")


def run_newrun(args: argparse.Namespace) -> int:
    payload, selected = _payload(args)
    if args.json and not args.execute:
        print(json.dumps({"ok": True, **payload}, indent=2, sort_keys=True))
        return 0
    if not selected:
        print_human_menu(payload)
        return 0
    if not args.execute:
        if args.json:
            print(json.dumps({"ok": True, **payload}, indent=2, sort_keys=True))
        else:
            print_human_menu(payload)
            recommendation = payload.get("recommendation") or {}
            if recommendation:
                print("Recommendation:")
                print(f"  selected: {recommendation.get('selected_preset')}")
                for reason in recommendation.get("reasons", []):
                    print(f"  reason: {reason}")
            print(f"Selected preset: {selected.name}")
            print(f"Execute with: rsi newrun --preset {selected.name} --execute")
        return 0

    from dharma_swarm.forge_lab.source_guard import require_execution_source

    try:
        source = require_execution_source(
            Path(args.source_repo) if args.source_repo else None
        )
    except RuntimeError as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "schema": NEW_RUN_SCHEMA,
                        "error": {
                            "code": "NONCANONICAL_EXECUTION_SOURCE",
                            "message": str(exc),
                        },
                    },
                    sort_keys=True,
                )
            )
        else:
            print(f"rsi newrun refused: {exc}", file=sys.stderr)
        return SOURCE_REFUSAL_EXIT

    print(
        f"[rsi newrun] executing preset={selected.name} source={source['commit']}; "
        "live model tokens may be spent",
        flush=True,
    )
    from dharma_swarm.forge_lab.cli import main as forge_lab_main

    return forge_lab_main(
        selected.forge_args(
            source_repo=str(source["repo"]),
            keep_worktree=args.keep_worktree,
        )
    )
