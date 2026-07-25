"""SWE-bench grading arms for Forge real runs."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from dharma_swarm.forge_v1.harness import BudgetExhausted, TokenBroker
from dharma_swarm.forge_v1.run_real_proposer import Proposal, SweBenchProposer
from dharma_swarm.forge_v1.swebench_real import verify_prediction


# --------------------------------------------------------------------------- #
# Swebench-aware arms (grade with the Docker harness, share one TokenBroker)
# --------------------------------------------------------------------------- #
@dataclass
class GradedSample:
    model: str
    tokens: int
    patch_len: int
    resolved: bool
    grade_seconds: float
    error: str | None = None


@dataclass
class ArmRun:
    arm: str
    passed: bool = False
    samples: list[GradedSample] = field(default_factory=list)
    tokens_spent: int = 0
    wall_seconds: float = 0.0
    budget_exhausted: bool = False
    note: str = ""


def _grade(instance: dict, patch: str, *, timeout: int) -> tuple[bool, float, str | None]:
    """Grade ONE patch with the official swebench Docker harness. An empty patch
    is graded too (swebench reports it unresolved). Returns (resolved, seconds,
    error). An infra failure (image build/pull) is surfaced as an error, never a
    fake verdict."""
    t0 = time.time()
    try:
        resolved = verify_prediction(instance, patch, timeout=timeout)
        return bool(resolved), time.time() - t0, None
    except Exception as e:  # infra error: report honestly, do not fake
        return False, time.time() - t0, f"{type(e).__name__}: {e}"


def _consume_proposal(
    run: ArmRun, instance: dict, prop: Proposal, broker: TokenBroker, *, grade_timeout: int
) -> bool | None:
    """Charge tokens, grade the proposal, record the sample. Returns:
      True  -> resolved (arm passes, stop),
      False -> graded but not resolved (keep going),
      None  -> budget exhausted (stop the arm).
    A proposer error or empty patch is recorded as an unresolved sample (no
    Docker grade) so a transient provider failure doesn't kill the run or fake a
    verdict."""
    try:
        broker.charge(prop.tokens)
    except BudgetExhausted:
        run.budget_exhausted = True
        return None
    if prop.error or not prop.patch.strip():
        run.samples.append(
            GradedSample(prop.model, prop.tokens, len(prop.patch), False, 0.0,
                         prop.error or "empty-patch")
        )
        return False
    resolved, secs, err = _grade(instance, prop.patch, timeout=grade_timeout)
    run.samples.append(
        GradedSample(prop.model, prop.tokens, len(prop.patch), resolved, secs, err)
    )
    if resolved:
        run.passed = True
        return True
    return False


def champion_best_of_n(
    instance: dict,
    file_context: dict[str, str],
    proposer: SweBenchProposer,
    broker: TokenBroker,
    *,
    n: int,
    grade_timeout: int,
) -> ArmRun:
    """Best-of-N on a single model, graded by Docker. Keep the first patch that
    resolves; stop when budget can't afford the next sample."""
    run = ArmRun(arm="champion_best_of_n")
    t0 = time.time()
    for i in range(n):
        prop = proposer.propose(instance, file_context)
        outcome = _consume_proposal(run, instance, prop, broker, grade_timeout=grade_timeout)
        if outcome is None or outcome is True:
            break
    run.tokens_spent = broker.spent
    run.wall_seconds = time.time() - t0
    return run


def swarm_arm(
    instance: dict,
    file_context: dict[str, str],
    proposers: list[SweBenchProposer],
    broker: TokenBroker,
    *,
    grade_timeout: int,
) -> ArmRun:
    """Decorrelated swarm: each model proposes one patch; grade each with Docker;
    keep the first that resolves. Shares the SAME broker cap as the champion
    (equal budget). Selection across decorrelated proposers = the honest way a
    swarm can beat best-of-N (Transcendence Principle: diversity + verifier
    gate)."""
    run = ArmRun(arm="swarm")
    t0 = time.time()
    for proposer in proposers:
        prop = proposer.propose(instance, file_context)
        outcome = _consume_proposal(run, instance, prop, broker, grade_timeout=grade_timeout)
        if outcome is None or outcome is True:
            break
    run.tokens_spent = broker.spent
    run.wall_seconds = time.time() - t0
    return run
