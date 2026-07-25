"""L2 — the coordinated swarm arm + its evolvable 'genome'.

The thing the Forge measures against best-of-N: a real coordination topology
(repair by N proposers -> verify-gate -> rank), parameterised by a SwarmConfig
the evolution loop mutates. Runs offline on deterministic QualityModels so the
whole loop is free + green; swap QualityModel for providers.LiveModel to go live.

HONEST DESIGN NOTE: each offline model has a fixed COMPETENCE (it solves a
deterministic subset of tasks and NEVER the rest, regardless of samples — a real
capability ceiling). Decorrelated by seed, so different models cover different
tasks. This is the ONLY honest way a swarm beats single-model best-of-N at equal
budget: diversity of competence + verifier-gated selection (skill selection /
the Transcendence Principle) — NOT "more agents = better".
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .harness import ArmResult, BudgetExhausted, Candidate, RepairTask, TokenBroker, verify


@dataclass
class QualityModel:
    """Offline stand-in for a real model with a fixed competence. Solves ~1/
    comp_period of tasks (deterministic by seed) and never the rest."""

    name: str
    seed: int
    comp_period: int = 2
    tokens: int = 1000

    def solves(self, task: RepairTask) -> bool:
        h = int(hashlib.sha256(f"comp:{task.name}:{self.seed}".encode()).hexdigest(), 16)
        return (h % max(1, self.comp_period)) == 0

    def propose(self, task: RepairTask, sample_idx: int) -> Candidate:
        patch = dict(task.gold_patch) if self.solves(task) else dict(task.files)
        return Candidate(patch=patch, tokens=self.tokens)


@dataclass
class SwarmConfig:
    """The swarm 'genome' the evolution loop mutates."""

    proposers: list[tuple[int, int]]   # list of (seed, comp_period)
    verify_gate: bool = True
    tokens_per_call: int = 1000

    def models(self) -> list[QualityModel]:
        return [
            QualityModel(name=f"p{i}", seed=s, comp_period=c, tokens=self.tokens_per_call)
            for i, (s, c) in enumerate(self.proposers)
        ]

    def fingerprint(self) -> str:
        return f"n={len(self.proposers)};gate={int(self.verify_gate)};{sorted(self.proposers)}"


def build_arm_from_models(models: list, verify_gate: bool = True):
    """L2.5 — a coordinated swarm Arm over a list of PRE-BUILT models (real
    `providers.LiveModel`s OR offline stubs — anything with
    `.propose(task, idx) -> Candidate`). Each proposer offers a patch; with the
    verify-gate the arm keeps the first verifier-passing one (selection across
    decorrelated proposers); without it, it submits the first proposer's patch
    unchecked. All calls share ONE TokenBroker (equal-budget honesty).

    This is how the swarm goes LIVE: pass e.g.
    `[LiveModel(PoolCompletion("gemini-2.5-flash")), LiveModel(PoolCompletion("glm-5.1"))]`
    as `models`, against a best-of-N champion on the single best model."""

    def arm(task: RepairTask, broker: TokenBroker) -> ArmResult:
        samples = 0
        last: Candidate | None = None
        for m in models:
            cand = m.propose(task, 0)
            try:
                broker.charge(cand.tokens)
            except BudgetExhausted:
                break
            samples += 1
            last = cand
            if verify_gate:
                if verify(task, cand.patch):
                    return ArmResult(True, samples, broker.spent)
            else:
                # no gate -> no selection: submit the first candidate as-is
                return ArmResult(verify(task, cand.patch), samples, broker.spent)
        passed = bool(last and verify(task, last.patch))
        return ArmResult(passed, samples, broker.spent)

    return arm


def build_arm(config: SwarmConfig):
    """Build a coordinated swarm Arm from a config (offline genome -> QualityModels).
    Delegates to build_arm_from_models; the real-model path is the SAME arm with
    LiveModels instead of QualityModels."""
    return build_arm_from_models(config.models(), config.verify_gate)
