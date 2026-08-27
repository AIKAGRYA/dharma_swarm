"""Evaluator protocol and blind ring-1 fitness gate.

The mutation army sees only a gated scalar receipt, never evaluator internals.
Tripwire or correctness failure zeroes fitness before archival or promotion.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

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
_EVALUATION_BINDING_FIELDS = (
    "schema_version", "candidate_id", "target_id", "candidate_digest",
    "evaluator_id", "seed", "run_id", "command_digest", "output_digest",
    "isolation_digest",
)


class IsolationProofLike(Protocol):
    """Structural runner-proof boundary; no concrete sibling import required."""

    @property
    def promotion_allowed(self) -> bool: ...

    def to_dict(self) -> dict[str, Any]: ...


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_digest(payload: Any) -> str:
    """Deterministic sha256 over a JSON-canonicalized payload."""
    blob = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    )
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _is_sha256_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def validate_isolation_proof_payload(
    payload: object,
    *,
    expected_binding: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    """Validate non-authorizing isolation observations and their run binding.

    This does not attest the execution image or the truth of caller observations,
    so a positive ``promotion_allowed`` claim is rejected. A future promotion
    path must consume an externally attested capability, not this public shape.
    """
    base_fields = {*_ISOLATION_FACT_FIELDS, "digest", "promotion_allowed"}
    if type(payload) is not dict or set(payload) not in (
        base_fields,
        base_fields | {"evaluation_binding"},
    ):
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
    if payload["promotion_allowed"] is not False:
        return None, False
    if "evaluation_binding" not in payload:
        return (dict(payload), False) if expected_binding is None else (None, False)

    binding = payload["evaluation_binding"]
    if type(binding) is not dict or set(binding) != {*_EVALUATION_BINDING_FIELDS, "digest"}:
        return None, False
    string_fields = set(_EVALUATION_BINDING_FIELDS) - {"seed"}
    if (
        any(type(binding[field]) is not str for field in string_fields)
        or type(binding["seed"]) is not int
        or binding["schema_version"] != "foundry_evaluation_binding.v1"
    ):
        return None, False
    for field_name in ("candidate_digest", "command_digest", "output_digest",
                       "isolation_digest", "digest"):
        if not _is_sha256_digest(binding[field_name]):
            return None, False
    if binding["isolation_digest"] != payload["digest"]:
        return None, False
    binding_body = {field: binding[field] for field in _EVALUATION_BINDING_FIELDS}
    if binding["digest"] != canonical_digest(binding_body):
        return None, False
    if expected_binding is not None and any(
        binding.get(field) != value for field, value in expected_binding.items()
    ):
        return None, False
    return dict(payload), False


def _validated_isolation_proof(
    proof: object,
    *,
    expected_binding: dict[str, Any],
) -> tuple[dict[str, Any] | None, bool]:
    """Recompute the sibling IsolationProof digest and promotion predicate."""
    to_dict = getattr(proof, "to_dict", None)
    if not callable(to_dict):
        return None, False
    try:
        payload = to_dict()
    except (TypeError, ValueError):
        return None, False
    validated, derived_promotion = validate_isolation_proof_payload(
        payload,
        expected_binding=expected_binding,
    )
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


def candidate_digest(candidate: Candidate) -> str:
    """Bind every declared candidate field, including the exact proposed diff."""
    return canonical_digest(asdict(candidate))


@dataclass(frozen=True)
class EvaluationRunIdentity:
    """Caller-carried identity of the command invocation and its exact output."""

    run_id: str
    command_digest: str
    output_digest: str

    @classmethod
    def from_execution(
        cls, *, run_id: str, command: Any, output: Any
    ) -> EvaluationRunIdentity:
        if type(run_id) is not str or not run_id or len(run_id) > 256:
            raise ValueError("run_id must be a non-empty bounded string")
        return cls(run_id, canonical_digest(command), canonical_digest(output))

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _run_identity_payload(identity: object) -> dict[str, str] | None:
    if type(identity) is not EvaluationRunIdentity:
        return None
    payload = identity.to_dict()
    if not (type(payload["run_id"]) is str and 0 < len(payload["run_id"]) <= 256):
        return None
    if not all(_is_sha256_digest(payload[field]) for field in
               ("command_digest", "output_digest")):
        return None
    return payload


def _evaluation_binding_context(
    candidate: Candidate, evaluator_id: str, seed: int,
    run_identity: EvaluationRunIdentity,
) -> dict[str, Any]:
    identity = _run_identity_payload(run_identity)
    if (
        identity is None
        or not all(type(value) is str for value in
                   (candidate.candidate_id, candidate.target_id, evaluator_id))
        or type(seed) is not int
    ):
        raise ValueError("evaluation binding identity is malformed")
    return {
        "schema_version": "foundry_evaluation_binding.v1",
        "candidate_id": candidate.candidate_id,
        "target_id": candidate.target_id,
        "candidate_digest": candidate_digest(candidate),
        "evaluator_id": evaluator_id,
        "seed": seed,
        **identity,
    }


@dataclass(frozen=True)
class BoundIsolationProof:
    """Non-authorizing isolation facts bound to one evaluation invocation."""

    proof: object
    candidate: Candidate
    evaluator_id: str
    seed: int
    run_identity: EvaluationRunIdentity

    @property
    def promotion_allowed(self) -> bool:
        """Public observation envelopes never carry promotion authority."""
        return False

    def to_dict(self) -> dict[str, Any]:
        to_dict = getattr(self.proof, "to_dict", None)
        if not callable(to_dict):
            raise TypeError("bound isolation proof must expose to_dict()")
        payload = to_dict()
        if type(payload) is not dict:
            raise TypeError("bound isolation proof payload must be a plain dict")
        context = _evaluation_binding_context(
            self.candidate, self.evaluator_id, self.seed, self.run_identity
        )
        binding = {**context, "isolation_digest": payload.get("digest")}
        sealed_binding = {**binding, "digest": canonical_digest(binding)}
        return {**payload, "evaluation_binding": sealed_binding}


def bind_isolation_proof(
    proof: object, *, candidate: Candidate, evaluator_id: str, seed: int,
    run_identity: EvaluationRunIdentity,
) -> BoundIsolationProof:
    """Construct a bound observation envelope at the evaluator/runner boundary."""
    return BoundIsolationProof(proof, candidate, evaluator_id, seed, run_identity)


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
    isolation_proof: IsolationProofLike | None = None
    run_identity: EvaluationRunIdentity | None = None


@dataclass(frozen=True)
class EvalReceipt:
    """Blind result; fitness is zero on any tripwire or correctness failure."""

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
    run_identity: dict[str, str] | None
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
    """Wrap ``(candidate, seed) -> EvalMetrics`` as an evaluator."""

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
    run_identity_payload = _run_identity_payload(metrics.run_identity)
    expected_binding = None
    if run_identity_payload is not None:
        try:
            expected_binding = _evaluation_binding_context(
                candidate,
                evaluator.evaluator_id,
                seed,
                metrics.run_identity,
            )
        except (TypeError, ValueError):
            expected_binding = None
    if proof is not None and expected_binding is not None:
        proof_payload, proof_allows_promotion = _validated_isolation_proof(
            proof,
            expected_binding=expected_binding,
        )
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
        "run_identity": run_identity_payload,
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
        run_identity=run_identity_payload,
        sealed_at=_utc_now_iso(),
        digest=canonical_digest(body),
    )


def receipt_to_dict(receipt: EvalReceipt) -> dict[str, Any]:
    """Plain-dict view for JSON persistence."""
    return asdict(receipt)
