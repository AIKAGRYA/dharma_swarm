"""Dharma Reward Forge v0 — the one-task loop-closure runner.

Wires the EXISTING organs into a single sealed-task loop (NO new engine):

    DharmaEval (score baseline + candidate on a SEALED holdout, deterministic oracle)
      -> build_scoreboard   (manifest + suite contamination-guarded)
      -> EvolutionReceipt    (patch hash, manifest hash, score, cost, command, exit code; hash-stable)
      -> verify_evolution_receipt
      -> FitnessScore.from_external_receipt  (unconfirmed receipt -> ZERO fitness; anti-inward-machine)
      -> EvolutionPromotionRequest -> evaluate_promotion_request
            (returns `candidate_for_human_review` ONLY if the holdout improves AND
             telos/safety/governance/receipt/cost/rollback all pass)

This v0 proves the WIRING deterministically: the candidate output is supplied by the
caller, so no LLM / network / GPU is needed to demonstrate that the loop closes and
emits a valid, verifiable receipt. The telos/safety decision is INJECTED
(`safety_passed`, `governance_passed`) so the loop core is decoupled from the gate's
internal API; `telos_gate_decision()` is the live adapter to wire in v0.1.

Sealing discipline (Forge robustness requirement #1): the candidate's holdout output
must be produced WITHOUT access to `holdout_task.expected`. v0 enforces this by
construction — the caller supplies the output; the oracle (expected answer) lives only
here, outside the candidate workspace. v0.1 swaps in live DGM generation + check_action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dharma_swarm.archive import FitnessScore
from dharma_swarm.dharma_eval import (
    DharmaEvalScore,
    DharmaEvalTask,
    build_scoreboard,
    score_output,
)
from dharma_swarm.evolution_promotion import (
    EvolutionPromotionRequest,
    EvolutionPromotionReview,
    evaluate_promotion_request,
)
from dharma_swarm.evolution_receipt import (
    EvolutionReceipt,
    build_evolution_receipt,
    hash_text,
    verify_evolution_receipt,
)


@dataclass
class SealedForgeResult:
    """Outcome of one sealed Forge task: the promotion review + the replayable receipt."""

    review: EvolutionPromotionReview
    receipt: EvolutionReceipt
    fitness: FitnessScore
    holdout_delta: float
    baseline_score: float
    candidate_score: float


def telos_gate_decision(action: str, content: str = "") -> tuple[bool, bool]:
    """Live adapter to the real telos gate (TelosGatekeeper via check_action).

    Returns (safety_passed, governance_passed). Defensive: any gate error or a
    blocking result yields a conservative (False, False). Wire this as the default
    gate in v0.1; v0 callers may inject explicit booleans for hermetic tests.
    """
    try:
        from dharma_swarm.telos_gates import check_action

        result = check_action(action, content)
    except Exception:
        return False, False
    blocked = bool(getattr(result, "blocked", False))
    passed_attr = getattr(result, "passed", None)
    passed = (not blocked) if passed_attr is None else bool(passed_attr)
    return passed, passed


def run_sealed_forge_task(
    *,
    suite_id: str,
    manifest_hash: str,
    holdout_task: DharmaEvalTask,
    candidate_id: str,
    incumbent_id: str,
    candidate_holdout_output: Any,
    baseline_holdout_output: Any,
    patch_text: str,
    safety_passed: bool,
    governance_passed: bool,
    cost: float = 0.0,
    cost_within_budget: bool = True,
    runtime_within_budget: bool = True,
    rollback_ref: str = "",
    test_commands: list[str] | None = None,
    exit_codes: list[int] | None = None,
    min_holdout_improvement: float = 0.0,
) -> SealedForgeResult:
    """Run one sealed task end-to-end and return the promotion review + receipt.

    Raises ValueError on a non-holdout task, an empty diff, or scoreboard
    contamination (manifest/suite) — the loop refuses contaminated evidence.
    """
    if holdout_task.split != "holdout":
        raise ValueError("sealed Forge task must be scored on the 'holdout' split")
    if not patch_text.strip():
        raise ValueError("non-empty diff required (Forge receipt #3)")

    # 1. Deterministic oracle scores baseline + candidate on the SEALED holdout.
    baseline: DharmaEvalScore = score_output(
        holdout_task,
        baseline_holdout_output,
        candidate_id=incumbent_id,
        suite_id=suite_id,
        manifest_hash=manifest_hash,
    )
    candidate: DharmaEvalScore = score_output(
        holdout_task,
        candidate_holdout_output,
        candidate_id=candidate_id,
        suite_id=suite_id,
        manifest_hash=manifest_hash,
    )

    # 2. Scoreboard — raises on manifest/suite contamination (Forge robustness #1/#2).
    board = build_scoreboard(
        suite_id=suite_id,
        manifest_hash=manifest_hash,
        baseline_id=incumbent_id,
        candidate_id=candidate_id,
        baseline_scores=[baseline],
        candidate_scores=[candidate],
        split="holdout",
        min_delta=min_holdout_improvement,
    )

    # 3. Replayable receipt — binds patch, manifest, score, cost, command, exit code.
    receipt = build_evolution_receipt(
        child_archive_entry_id=candidate_id,
        parent_archive_entry_id=incumbent_id or None,
        patch_hash=hash_text(patch_text),
        eval_manifest_hash=manifest_hash,
        eval_split="holdout",
        score=candidate.score,
        cost=float(cost),
        test_commands=list(test_commands or []),
        exit_codes=list(exit_codes or []),
        telos_result={"safety_passed": safety_passed, "governance_passed": governance_passed},
        evidence_refs=[board.scoreboard_id],
    )
    receipt_verified, _reason = verify_evolution_receipt(receipt)

    # 4. Fitness from the EXTERNALLY-CONFIRMED receipt (anti-inward-machine bridge).
    fitness = FitnessScore.from_external_receipt(
        holdout_score=candidate.score,
        external_confirmed=receipt_verified,
        safety_passed=safety_passed,
        cost_normalized=min(max(float(cost), 0.0), 1.0),
    )

    # 5. Promotion gate — candidate_for_human_review ONLY if holdout improves + gates pass.
    request = EvolutionPromotionRequest(
        candidate_id=candidate_id,
        incumbent_id=incumbent_id,
        baseline_scores={"correctness": baseline.score},
        holdout_scores={"correctness": candidate.score},
        min_improvement={"correctness": float(min_holdout_improvement)},
        safety_passed=safety_passed,
        governance_passed=governance_passed,
        receipt_verified=receipt_verified,
        cost_within_budget=cost_within_budget,
        runtime_within_budget=runtime_within_budget,
        scorer_contaminated=False,  # build_scoreboard would have raised on contamination
        rollback_ref=rollback_ref,
        evidence_refs=[receipt.receipt_id, board.scoreboard_id],
    )
    review = evaluate_promotion_request(request)

    return SealedForgeResult(
        review=review,
        receipt=receipt,
        fitness=fitness,
        holdout_delta=board.delta,
        baseline_score=baseline.score,
        candidate_score=candidate.score,
    )


def _demo() -> SealedForgeResult:
    """A built-in sealed task: the Forge's first heartbeat, runnable with no deps.

    Mirrors the v0 bootstrap target — a candidate that fixes a sealed holdout where
    the incumbent failed. Run: `python3 scripts/runtime/reward_forge_v0.py`.
    """
    holdout = DharmaEvalTask(
        task_id="forge-bootstrap-1",
        split="holdout",
        domain="repo_repair",
        prompt="Harden the reward substrate against manifest/suite contamination.",
        expected={"contamination_rejected": True},
    )
    return run_sealed_forge_task(
        suite_id="forge_v0_bootstrap",
        manifest_hash="sha256:demo-manifest",
        holdout_task=holdout,
        candidate_id="child_001",
        incumbent_id="incumbent_000",
        candidate_holdout_output={"contamination_rejected": True},
        baseline_holdout_output={"contamination_rejected": False},
        patch_text="--- a/dharma_eval.py\n+++ b/dharma_eval.py\n+    raise ValueError('contamination')\n",
        safety_passed=True,
        governance_passed=True,
        rollback_ref="git:HEAD~1",
        test_commands=["python3 -m pytest tests/test_dharma_eval.py -q"],
        exit_codes=[0],
        min_holdout_improvement=0.5,
    )


if __name__ == "__main__":
    import json

    result = _demo()
    print("=== Dharma Reward Forge v0 — first heartbeat ===")
    print(f"promotion status : {result.review.status}")
    print(f"holdout delta    : {result.holdout_delta:+.3f}  ({result.baseline_score} -> {result.candidate_score})")
    print(f"fitness.correctness (external-confirmed): {result.fitness.correctness}")
    print(f"receipt verified : {verify_evolution_receipt(result.receipt)[0]}")
    print("receipt:")
    print(
        json.dumps(
            {
                "patch_hash": result.receipt.patch_hash,
                "eval_manifest_hash": result.receipt.eval_manifest_hash,
                "score": result.receipt.score,
                "cost": result.receipt.cost,
                "test_commands": result.receipt.test_commands,
                "exit_codes": result.receipt.exit_codes,
                "receipt_payload_hash": result.receipt.receipt_payload_hash,
            },
            indent=2,
        )
    )
