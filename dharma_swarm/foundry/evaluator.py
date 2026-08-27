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
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from dharma_swarm.foundry.runner_isolation import IsolationProof

_ISOLATION_BOOL_FIELDS = (
    "network_disabled",
    "blocked",
    "timed_out",
    "readonly_rootfs",
    "cap_drop_all",
    "no_new_privileges",
    "pids_limited",
    "memory_limited",
    "memory_swap_limited",
    "tmpfs_limited",
    "non_root_user",
    "workdir_readonly",
)
_ISOLATION_FACT_FIELDS = (
    "isolation_level",
    "network_disabled",
    "blocked",
    "timed_out",
    "exit_code",
    "readonly_rootfs",
    "cap_drop_all",
    "no_new_privileges",
    "pids_limited",
    "memory_limited",
    "memory_swap_limited",
    "tmpfs_limited",
    "non_root_user",
    "workdir_readonly",
)


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
        default=str,
        allow_nan=False,
    )
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def validate_isolation_proof_payload(
    payload: object,
) -> tuple[dict[str, Any] | None, bool]:
    """Validate serialized sibling IsolationProof facts, digest, and predicate."""
    expected = {*_ISOLATION_FACT_FIELDS, "digest", "promotion_allowed"}
    if type(payload) is not dict or set(payload) != expected:
        return None, False
    if type(payload["isolation_level"]) is not str or type(payload["digest"]) is not str:
        return None, False
    if any(type(payload[field]) is not bool for field in _ISOLATION_BOOL_FIELDS):
        return None, False
    if type(payload["exit_code"]) is not int:
        return None, False

    body = {field: payload[field] for field in _ISOLATION_FACT_FIELDS}
    digest = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if payload["digest"] != digest:
        return None, False
    derived_promotion = (
        not payload["blocked"]
        and not payload["timed_out"]
        and payload["network_disabled"]
        and payload["readonly_rootfs"]
        and payload["cap_drop_all"]
        and payload["no_new_privileges"]
        and payload["pids_limited"]
        and payload["memory_limited"]
        and payload["memory_swap_limited"]
        and payload["tmpfs_limited"]
        and payload["non_root_user"]
        and payload["workdir_readonly"]
        and payload["exit_code"] == 0
        and payload["isolation_level"] == "docker_nonet"
    )
    if payload["promotion_allowed"] is not derived_promotion:
        return None, False
    return dict(payload), derived_promotion


def _validated_isolation_proof(proof: object) -> tuple[dict[str, Any] | None, bool]:
    """Recompute the sibling IsolationProof digest and promotion predicate."""
    to_dict = getattr(proof, "to_dict", None)
    if not callable(to_dict):
        return None, False
    try:
        payload = to_dict()
    except (TypeError, ValueError):
        return None, False
    validated, derived_promotion = validate_isolation_proof_payload(payload)
    if validated is None:
        return None, False
    if getattr(proof, "promotion_allowed", None) is not derived_promotion:
        return None, False
    return validated, derived_promotion


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
    start = time.monotonic()
    metrics = evaluator.evaluate(candidate, seed=seed)
    measured = time.monotonic() - start

    fired = list(tripwires_fired)
    invalid_metrics = False
    if type(metrics.primary_score) is bool:
        primary_score = 0.0
        invalid_metrics = True
    else:
        try:
            primary_score = float(metrics.primary_score)
        except (TypeError, ValueError):
            primary_score = 0.0
            invalid_metrics = True
    if not math.isfinite(primary_score):
        primary_score = 0.0
        invalid_metrics = True

    normalized_metrics: dict[str, float] = {}
    for key, value in metrics.metrics.items():
        if type(value) is bool:
            invalid_metrics = True
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            invalid_metrics = True
            continue
        if not math.isfinite(number):
            invalid_metrics = True
            continue
        normalized_metrics[str(key)] = number

    correctness_passed = metrics.correctness_passed
    if type(correctness_passed) is not bool:
        correctness_passed = False
        invalid_metrics = True

    if type(metrics.wall_clock_s) is bool:
        wall_clock_s = measured
        invalid_metrics = True
    else:
        try:
            wall_clock_s = float(metrics.wall_clock_s or measured)
        except (TypeError, ValueError):
            wall_clock_s = measured
            invalid_metrics = True
    if not math.isfinite(wall_clock_s) or wall_clock_s < 0:
        wall_clock_s = measured
        invalid_metrics = True
    wall_clock_s = round(wall_clock_s, 6)
    if invalid_metrics and "invalid_evaluator_metrics" not in fired:
        fired.append("invalid_evaluator_metrics")

    gated = correctness_passed and not fired
    fitness = primary_score if gated and primary_score > 0 else 0.0

    proof = metrics.isolation_proof
    proof_payload = None
    proof_allows_promotion = False
    if proof is not None:
        proof_payload, proof_allows_promotion = _validated_isolation_proof(proof)
    promotion = bool(fitness > 0 and proof_allows_promotion)
    body = {
        "candidate_id": candidate.candidate_id,
        "target_id": candidate.target_id,
        "evaluator_id": evaluator.evaluator_id,
        "seed": seed,
        "fitness": fitness,
        "correctness_passed": correctness_passed,
        "tripwires_fired": fired,
        "metrics": normalized_metrics,
        "wall_clock_s": wall_clock_s,
        "promotion_allowed": promotion,
        "isolation_proof": proof_payload,
    }
    return EvalReceipt(
        candidate_id=candidate.candidate_id,
        target_id=candidate.target_id,
        evaluator_id=evaluator.evaluator_id,
        seed=seed,
        fitness=fitness,
        correctness_passed=correctness_passed,
        tripwires_fired=tuple(fired),
        metrics=normalized_metrics,
        wall_clock_s=wall_clock_s,
        promotion_allowed=promotion,
        isolation_proof=proof_payload,
        sealed_at=_utc_now_iso(),
        digest=canonical_digest(body),
    )


def receipt_to_dict(receipt: EvalReceipt) -> dict[str, Any]:
    """Plain-dict view for JSON persistence."""
    return asdict(receipt)
