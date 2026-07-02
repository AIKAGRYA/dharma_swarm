"""Forge v1 — the offline scoreboard machinery.

The Forge measures, honestly, whether a coordinated swarm beats best-of-N on a
single model AT EQUAL TOKEN BUDGET. This module is the load-bearing machinery,
built to run fully offline (stub models, fake fixtures) so the measurement can
be trusted BEFORE any live provider call. Real models/benchmarks swap in later
behind the same interfaces.

Pieces:
- TokenBroker    : equal-budget enforcement (cumulative cap, aborting interrupt)
- RepairTask     : a code-repair fixture (buggy files + a HIDDEN gold test)
- verify         : sandboxed binary verifier (isolated temp dir, gold test wins,
                   pass = test exit code 0 — never an agent self-report)
- best_of_n      : verifier-selected best-of-N (keep the first passer, not average)
- run_scoreboard : two arms at EQUAL budget on the SAME tasks -> swarm_lift
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol


# --------------------------------------------------------------------------- #
# Equal-budget enforcement
# --------------------------------------------------------------------------- #
class BudgetExhausted(Exception):
    """A call would push cumulative tokens past the arm's cap."""


@dataclass
class TokenBroker:
    """Sums prompt+completion tokens across every call in ONE arm and refuses
    the call that would cross the cap. This is what makes 'swarm vs single
    model' a fair fight instead of a spending contest."""

    cap: int
    spent: int = 0
    calls: int = 0

    def remaining(self) -> int:
        return max(0, self.cap - self.spent)

    def can_afford(self, tokens: int) -> bool:
        return self.spent + tokens <= self.cap

    def charge(self, tokens: int) -> int:
        if tokens < 0:
            raise ValueError("tokens must be >= 0")
        if not self.can_afford(tokens):
            raise BudgetExhausted(
                f"{tokens} tokens would exceed cap {self.cap} (spent {self.spent})"
            )
        self.spent += tokens
        self.calls += 1
        return self.spent


# --------------------------------------------------------------------------- #
# Task + verifier
# --------------------------------------------------------------------------- #
@dataclass
class RepairTask:
    """A code-repair fixture. The agent sees `files` and must produce a patch
    (filename -> new content). It NEVER sees `test_files` (the gold test) and
    cannot edit them — the verifier restores them after applying the patch."""

    name: str
    files: dict[str, str]          # buggy, agent-editable source
    test_files: dict[str, str]     # HIDDEN gold test (agent may not edit)
    gold_patch: dict[str, str]     # the correct fix (for stub models/reference)
    test_args: list[str]           # argv after the python exe, e.g. ["test_x.py"]


_VERIFY_CACHE: dict = {}


def verify(task: RepairTask, candidate: dict[str, str] | None) -> bool:
    """Deterministic memo around _verify_uncached: an identical (task, patch) maps
    to the same result, so the evolution loop can re-score configs cheaply. The
    key includes the full patch content, so genuinely different (real) patches
    never falsely hit."""
    key = (task.name, tuple(sorted((candidate or {}).items())))
    if key not in _VERIFY_CACHE:
        _VERIFY_CACHE[key] = _verify_uncached(task, candidate)
    return _VERIFY_CACHE[key]


def _verify_uncached(task: RepairTask, candidate: dict[str, str] | None) -> bool:
    """Apply `candidate` to an ISOLATED copy of the task, restore the gold test,
    run it, and return pass/fail from the test EXIT CODE. Docker-like isolation
    via a fresh temp dir; the gold test is restored last so a patch cannot edit
    its own grader (the DGM 'delete the detector' failure)."""
    with tempfile.TemporaryDirectory(prefix="forge_v1_") as tmp:
        root = Path(tmp)
        try:
            for name, src in task.files.items():
                _write(root, name, src)
            for name, src in (candidate or {}).items():
                if name in task.test_files:
                    continue  # agent may not edit the gold test
                _write(root, name, src)
            for name, src in task.test_files.items():  # gold test wins, restored last
                _write(root, name, src)
        except ValueError:
            return False
        try:
            proc = subprocess.run(
                [sys.executable, *task.test_args],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return False
        return proc.returncode == 0


def _write(root: Path, name: str, src: str) -> None:
    root_resolved = root.resolve()
    path = (root / name).resolve()
    try:
        path.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"refusing to write outside verifier root: {name}") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(src)


# --------------------------------------------------------------------------- #
# Candidate / model interface
# --------------------------------------------------------------------------- #
@dataclass
class Candidate:
    patch: dict[str, str]   # filename -> new content
    tokens: int             # prompt+completion tokens this call cost


class Model(Protocol):
    name: str

    def propose(self, task: RepairTask, sample_idx: int) -> Candidate: ...


# --------------------------------------------------------------------------- #
# Best-of-N champion
# --------------------------------------------------------------------------- #
@dataclass
class ArmResult:
    passed: bool
    samples: int
    tokens: int


def best_of_n(
    model: Model, task: RepairTask, broker: TokenBroker, max_samples: int = 256
) -> ArmResult:
    """Sample candidates, run each through the verifier, KEEP the first that
    passes. Stop when the budget can't afford the next call. Keep-best, never
    average (averaging without a verifier lowers quality — Self-MoA)."""
    samples = 0
    for i in range(max_samples):
        cand = model.propose(task, i)
        try:
            broker.charge(cand.tokens)
        except BudgetExhausted:
            break
        samples += 1
        if verify(task, cand.patch):
            return ArmResult(passed=True, samples=samples, tokens=broker.spent)
    return ArmResult(passed=False, samples=samples, tokens=broker.spent)


# --------------------------------------------------------------------------- #
# Scoreboard
# --------------------------------------------------------------------------- #
# An arm is: (task, broker) -> ArmResult. Fresh broker (budget) per task.
Arm = Callable[[RepairTask, TokenBroker], ArmResult]


def run_arm(arm: Arm, tasks: list[RepairTask], budget: int) -> dict:
    per_task = []
    for task in tasks:
        broker = TokenBroker(cap=budget)
        res = arm(task, broker)
        per_task.append(
            {
                "task": task.name,
                "passed": res.passed,
                "samples": res.samples,
                "tokens": res.tokens,
            }
        )
    n = len(tasks)
    passed = sum(1 for r in per_task if r["passed"])
    return {
        "pass_at_1": passed / n if n else 0.0,
        "passed": passed,
        "n": n,
        "per_task": per_task,
    }


def run_scoreboard(
    tasks: list[RepairTask],
    champion: Arm,
    swarm: Arm,
    budget: int,
    *,
    ci_samples: int = 1000,
    ci_seed: int = 0,
) -> dict:
    """Both arms at EQUAL budget on the SAME tasks. swarm_lift =
    pass@1(swarm) - pass@1(champion). An honest negative is a valid result:
    freeze the swarm, ship best-of-N. Ship requires a paired bootstrap CI lower
    bound above zero, not merely positive raw lift."""
    champ = run_arm(champion, tasks, budget)
    swrm = run_arm(swarm, tasks, budget)
    lift = swrm["pass_at_1"] - champ["pass_at_1"]
    diffs = [
        (1.0 if s["passed"] else 0.0) - (1.0 if c["passed"] else 0.0)
        for c, s in zip(champ["per_task"], swrm["per_task"])
    ]
    ci = paired_bootstrap_ci(diffs, samples=ci_samples, seed=ci_seed)
    ship = ci["lower"] > 0
    if ship:
        status = "positive_lift_ci_cleared"
    elif lift > 0:
        status = "positive_lift_ci_not_cleared"
    else:
        status = "measured_negative_or_zero"
    return {
        "budget_per_task": budget,
        "n_tasks": len(tasks),
        "champion_pass_at_1": champ["pass_at_1"],
        "swarm_pass_at_1": swrm["pass_at_1"],
        "swarm_lift": lift,
        "paired_bootstrap_ci": ci,
        "ship_swarm": ship,
        "status": status,
        "champion": champ,
        "swarm": swrm,
    }


def paired_bootstrap_ci(
    paired_diffs: list[float],
    *,
    samples: int = 1000,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict:
    """Bootstrap the paired per-task lift distribution.

    Each element is one task's swarm outcome minus champion outcome, so pairing
    preserves task difficulty. The real Forge ship rule is CI lower > 0.
    """
    n = len(paired_diffs)
    if n == 0:
        return {"n": 0, "mean": 0.0, "lower": 0.0, "upper": 0.0}
    mean = sum(paired_diffs) / n
    if samples <= 0:
        return {"n": n, "mean": mean, "lower": mean, "upper": mean}

    rng = random.Random(seed)
    means = []
    for _ in range(samples):
        draw = [paired_diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(draw) / n)
    means.sort()
    lo_i = max(0, min(samples - 1, int((alpha / 2) * samples)))
    hi_i = max(0, min(samples - 1, int((1 - alpha / 2) * samples)))
    return {
        "n": n,
        "mean": mean,
        "lower": means[lo_i],
        "upper": means[hi_i],
    }
