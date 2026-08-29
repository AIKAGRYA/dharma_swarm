"""Evaluator Protocol and the blind ring-1 fitness gate.

An :class:`Evaluator` turns a :class:`Candidate` (a proposed code change to an
external target) into :class:`EvalMetrics`. The Foundry never lets the mutation
army read the evaluator: the army only ever receives the scalar fitness on the
returned :class:`EvalReceipt`. That is the "blind" property — the scoring logic
is a separate object (and, for command evaluators, a separate process via
:mod:`dharma_swarm.foundry.runner_isolation`), so the search cannot learn to
address the grader instead of the code.

:func:`blind_evaluate` is the ring-1 gate: it runs the tripwires first and
zeroes fitness on any trip or correctness failure, so a reward-hacked or
scope-violating candidate can never enter the elite grid with a positive score.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from dharma_swarm.foundry.runner_isolation import IsolationProof


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_digest(payload: Any) -> str:
    """Deterministic sha256 over a JSON-canonicalized payload.

    Used to seal receipts so a third party can recompute the hash from the
    published artifact alone.
    """
    blob = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Candidate:
    """A proposed change to an external target, produced by the mutation army."""

    candidate_id: str
    target_id: str
    diff: str
    origin_model: str = ""
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalMetrics:
    """The raw output of one evaluation — before tripwire/correctness gating.

    ``primary_score`` is higher-is-better and is the number the elite grid ranks
    by once gated. ``correctness_passed`` must be True for any positive fitness
    to survive (a fast-but-wrong kernel is a zero, not a win).
    """

    primary_score: float
    correctness_passed: bool
    metrics: dict[str, float] = field(default_factory=dict)
    wall_clock_s: float = 0.0
    notes: str = ""
    isolation_proof: "IsolationProof | None" = None
    failure_category: str = ""


@dataclass(frozen=True)
class EvalReceipt:
    """The blind, gated result the army is allowed to see: a scalar and flags.

    ``fitness`` is zero whenever a tripwire fired or correctness failed, so the
    only thing the search can optimize is real, tripwire-clean improvement.
    """

    candidate_id: str
    target_id: str
    evaluator_id: str
    seed: int
    fitness: float
    correctness_passed: bool
    tripwires_fired: tuple[str, ...]
    metrics: dict[str, float]
    wall_clock_s: float
    promotion_allowed: bool
    isolation_proof: dict[str, Any] | None
    sealed_at: str
    digest: str
    failure_category: str = ""

    def is_win(self) -> bool:
        return self.fitness > 0.0 and self.correctness_passed and not self.tripwires_fired


@runtime_checkable
class Evaluator(Protocol):
    """The one thing every target must supply: a way to score a candidate.

    Implementations MUST be pure with respect to a fixed seed (run-twice
    identity), MUST run correctness before benchmarking, and MUST NOT expose
    their scoring internals to the candidate. See
    :class:`dharma_swarm.foundry.targets.TargetSpec` for how targets bind one.
    """

    evaluator_id: str

    def prepare(self) -> None:
        """Pin the target and warm any fixtures. Called once per campaign."""

    def evaluate(self, candidate: Candidate, *, seed: int) -> EvalMetrics:
        """Score a single candidate deterministically under ``seed``."""


@dataclass
class CallableEvaluator:
    """Adapter that wraps a plain scoring function as an :class:`Evaluator`.

    The scoring function receives ``(candidate, seed)`` and returns
    :class:`EvalMetrics`. Used for hermetic tests and for in-process evaluators;
    command-line/Docker evaluators live in
    :mod:`dharma_swarm.foundry.runner_isolation`.
    """

    evaluator_id: str
    score_fn: Any
    _prepared: bool = False

    def prepare(self) -> None:
        self._prepared = True

    def evaluate(self, candidate: Candidate, *, seed: int) -> EvalMetrics:
        return self.score_fn(candidate, seed)


def blind_evaluate(
    evaluator: Evaluator,
    candidate: Candidate,
    *,
    seed: int = 0,
    tripwires_fired: tuple[str, ...] = (),
) -> EvalReceipt:
    """Ring 1: score a candidate, then gate fitness to zero on any red flag.

    ``tripwires_fired`` is the output of :func:`scan_tripwires` (run by the loop
    before this call). Any fired tripwire, or a correctness failure, forces
    fitness to zero regardless of the raw ``primary_score`` — a hacked or
    out-of-scope candidate cannot buy its way into the archive.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("evaluator_metrics_invalid: seed must be an integer")
    for field_name, value in (
        ("candidate_id", candidate.candidate_id),
        ("target_id", candidate.target_id),
        ("evaluator_id", getattr(evaluator, "evaluator_id", "")),
    ):
        if not isinstance(value, str) or not value or len(value) > 512:
            raise ValueError(f"evaluator_metrics_invalid: {field_name} is invalid")
    start = time.monotonic()
    metrics = evaluator.evaluate(candidate, seed=seed)
    measured = time.monotonic() - start

    if not isinstance(metrics, EvalMetrics):
        raise ValueError("evaluator_metrics_invalid: evaluator returned wrong schema")
    if not isinstance(metrics.correctness_passed, bool):
        raise ValueError("evaluator_metrics_invalid: correctness flag is not boolean")
    if (
        isinstance(metrics.primary_score, bool)
        or not isinstance(metrics.primary_score, (int, float))
        or not math.isfinite(float(metrics.primary_score))
    ):
        raise ValueError("evaluator_metrics_invalid: primary score is non-finite/non-numeric")
    if not isinstance(metrics.metrics, dict):
        raise ValueError("evaluator_metrics_invalid: metrics must be an object")
    if len(metrics.metrics) > 1000:
        raise ValueError("evaluator_metrics_invalid: too many metric fields")
    normalized_metrics: dict[str, float] = {}
    for key, value in metrics.metrics.items():
        if (
            not isinstance(key, str)
            or not key
            or len(key) > 256
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError("evaluator_metrics_invalid: metric values must be finite numbers")
        normalized_metrics[key] = float(value)
    if not isinstance(metrics.notes, str) or len(metrics.notes) > 16_384:
        raise ValueError("evaluator_metrics_invalid: notes field is invalid")
    if (
        not isinstance(metrics.failure_category, str)
        or len(metrics.failure_category) > 80
        or (
            metrics.failure_category
            and not re.fullmatch(r"[a-z0-9_.:-]+", metrics.failure_category)
        )
    ):
        raise ValueError("evaluator_metrics_invalid: failure category is invalid")
    wall_clock = metrics.wall_clock_s or measured
    if (
        isinstance(wall_clock, bool)
        or not isinstance(wall_clock, (int, float))
        or not math.isfinite(float(wall_clock))
        or float(wall_clock) < 0
    ):
        raise ValueError("evaluator_metrics_invalid: wall clock is invalid")

    gated = bool(metrics.correctness_passed) and not tripwires_fired
    fitness = float(metrics.primary_score) if gated and metrics.primary_score > 0 else 0.0

    proof = metrics.isolation_proof
    try:
        proof_payload = proof.to_dict() if proof is not None else None
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("evaluator_metrics_invalid: isolation proof is invalid") from exc
    if proof_payload is not None and not isinstance(proof_payload, dict):
        raise ValueError("evaluator_metrics_invalid: isolation proof is invalid")
    if proof_payload is not None:
        # Reject non-finite or otherwise non-JSON proof fields before sealing.
        canonical_digest(proof_payload)
    promotion = bool(proof and proof.promotion_allowed)
    body = {
        "candidate_id": candidate.candidate_id,
        "target_id": candidate.target_id,
        "evaluator_id": evaluator.evaluator_id,
        "seed": seed,
        "fitness": fitness,
        "correctness_passed": bool(metrics.correctness_passed),
        "tripwires_fired": list(tripwires_fired),
        "metrics": normalized_metrics,
        "wall_clock_s": round(float(wall_clock), 6),
        "promotion_allowed": promotion,
        "isolation_proof": proof_payload,
        "failure_category": metrics.failure_category,
    }
    return EvalReceipt(
        candidate_id=candidate.candidate_id,
        target_id=candidate.target_id,
        evaluator_id=evaluator.evaluator_id,
        seed=seed,
        fitness=fitness,
        correctness_passed=bool(metrics.correctness_passed),
        tripwires_fired=tuple(tripwires_fired),
        metrics=normalized_metrics,
        wall_clock_s=round(float(wall_clock), 6),
        promotion_allowed=promotion,
        isolation_proof=proof_payload,
        sealed_at=_utc_now_iso(),
        digest=canonical_digest(body),
        failure_category=metrics.failure_category,
    )


def receipt_to_dict(receipt: EvalReceipt) -> dict[str, Any]:
    """Plain-dict view for JSON persistence."""
    return asdict(receipt)
