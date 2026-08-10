"""Model-family detection and immutable preset definitions for ``rsi newrun``."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, replace
from typing import Any, Iterable

from dharma_swarm.forge_lab.campaign_profile import (
    PROVIDER_ATTESTATION_POLICY,
    ROLE_ROUTE_BINDINGS,
)


GOVERNED_CAMPAIGN_REQUIRED = "GOVERNED_CAMPAIGN_REQUIRED"
GOVERNED_CAMPAIGN_REQUIRED_EXIT = 7
GOVERNED_CAMPAIGN_COMMAND = "rsi campaign plan --profile forge-lab-paired-frozen-v1"

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

    def forge_args(
        self,
        *,
        source_repo: str | None = None,
        keep_worktree: bool = False,
    ) -> list[str]:
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

    def command(
        self,
        *,
        source_repo: str | None = None,
        keep_worktree: bool = False,
    ) -> str:
        """Return the governed planning entrypoint, never a legacy live command."""

        del source_repo, keep_worktree
        return GOVERNED_CAMPAIGN_COMMAND

    def as_dict(
        self,
        *,
        source_repo: str | None = None,
        keep_worktree: bool = False,
    ) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "solver_model": self.solver_model,
            "verifier_model": self.verifier_model,
            "mutator_model": self.mutator_model,
            "role_routes": dict(ROLE_ROUTE_BINDINGS),
            "provider_attestation": dict(PROVIDER_ATTESTATION_POLICY),
            "evaluation_protocol": "paired_frozen_v1",
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
            "command": self.command(
                source_repo=source_repo,
                keep_worktree=keep_worktree,
            ),
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


def detect_current_model(
    env: dict[str, str] | None = None,
    explicit: str | None = None,
) -> tuple[str | None, str | None]:
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
            notes=(
                current_label,
                "Pass --model <id> or set RSILAB_MODEL/RSI_MODEL/FORGE_MODEL/CODEX_MODEL.",
            ),
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
            notes=(
                "Good middle path between fast smoke and diverse n=3.",
                current_label,
            ),
        ),
    ]


def select_preset(
    presets: Iterable[NewRunPreset],
    name: str,
) -> NewRunPreset:
    for preset in presets:
        if preset.name == name:
            return preset
    choices = ", ".join(p.name for p in presets)
    raise ValueError(f"unknown newrun preset {name!r}; choose one of: {choices}")


def apply_overrides(
    preset: NewRunPreset,
    args: argparse.Namespace,
) -> NewRunPreset:
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


__all__ = [
    "CURRENT_MODEL_ENV_KEYS",
    "DEFAULT_DIVERSE_MUTATOR",
    "DEFAULT_DIVERSE_SOLVER",
    "DEFAULT_DIVERSE_VERIFIER",
    "DEFAULT_FAST_MUTATOR",
    "DEFAULT_FAST_SOLVER",
    "DEFAULT_FAST_VERIFIER",
    "GOVERNED_CAMPAIGN_COMMAND",
    "GOVERNED_CAMPAIGN_REQUIRED",
    "GOVERNED_CAMPAIGN_REQUIRED_EXIT",
    "NewRunPreset",
    "apply_overrides",
    "build_presets",
    "detect_current_model",
    "select_preset",
]
