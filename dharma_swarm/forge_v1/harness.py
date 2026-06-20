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


def verify(task: RepairTask, candidate: dict[str, str] | None) -> bool:
    """Apply `candidate` to an ISOLATED copy of the task, restore the gold test,
    run it, and return pass/fail from the test EXIT CODE. Docker-like isolation
    via a fresh temp dir; the gold test is restored last so a patch cannot edit
    its own grader (the DGM 'delete the detector' failure)."""
    with tempfile.TemporaryDirectory(prefix="forge_v1_") as tmp:
        root = Path(tmp)
        for name, src in task.files.items():
            _write(root, name, src)
        for name, src in (candidate or {}).items():
            if name in task.test_files:
                continue  # agent may not edit the gold test
            _write(root, name, src)
        for name, src in task.test_files.items():  # gold test wins, restored last
            _write(root, name, src)
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
    path = root / name
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
    tasks: list[RepairTask], champion: Arm, swarm: Arm, budget: int
) -> dict:
    """Both arms at EQUAL budget on the SAME tasks. swarm_lift =
    pass@1(swarm) - pass@1(champion). An honest negative is a valid result:
    freeze the swarm, ship best-of-N."""
    champ = run_arm(champion, tasks, budget)
    swrm = run_arm(swarm, tasks, budget)
    lift = swrm["pass_at_1"] - champ["pass_at_1"]
    return {
        "budget_per_task": budget,
        "n_tasks": len(tasks),
        "champion_pass_at_1": champ["pass_at_1"],
        "swarm_pass_at_1": swrm["pass_at_1"],
        "swarm_lift": lift,
        # real version gates on a paired bootstrap-CI lower bound > 0, not raw lift
        "ship_swarm": lift > 0,
        "status": "positive_lift" if lift > 0 else "measured_negative_or_zero",
        "champion": champ,
        "swarm": swrm,
    }
