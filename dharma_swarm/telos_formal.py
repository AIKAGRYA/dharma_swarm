"""Formal telos gates -- measured invariants, not keyword bingo.

This module is the rigorous successor to the string-matching gates in
``telos_gates.py``.  Where the legacy gatekeeper asks "does a forbidden
substring appear in the action text", these gates evaluate **structural and
measured predicates** over a typed :class:`ActionContext`.  Each gate returns a
*number* (entropy, effective rank, Shannon gap, orphan count) alongside its
verdict, so the result is auditable, hard to game by pasting keywords, and
differentiable enough for the evolution loop to optimize against.

The synthesis (see design discussion):

* **Buddhism specifies the targets.**  Each gate names the dharmic principle it
  enforces (anicca -> humility, anekantavada -> contextuality, anatta ->
  observer separation, pratityasamutpada -> provenance).
* **Computer science proves them.**  Information-flow non-interference,
  provenance DAGs, Ashby's law of requisite variety, least privilege.
* **The mathematics of quantum theory is the modelling language** for the
  belief/context gates -- density operators, von Neumann entropy, and
  non-commuting / contextual measurement -- with *no* quantum physics and *no*
  consciousness claims.  A "certain" belief is a pure state, and the humility
  gate forbids pure states by requiring ``S(rho) > epsilon``.

Nothing here mutates global state and nothing here imports the orchestrator.
The gates are pure functions of their inputs; :class:`FormalTelosGatekeeper`
composes them with the legacy keyword gatekeeper (kept as a cheap Tier-0 lint).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from dharma_swarm.models import GateDecision, GateResult, GateTier, _utc_now

__all__ = [
    "ActionContext",
    "BeliefState",
    "DataLabel",
    "EvaluatorJudgment",
    "FormalGateName",
    "FormalGateResult",
    "FormalGateReport",
    "FormalTelosGatekeeper",
    "InformationFlow",
    "ProvenanceClaim",
    "anekanta_contextuality_gate",
    "epistemic_humility_gate",
    "evaluate_formal_gates",
    "noninterference_gate",
    "observer_separation_gate",
    "provenance_integrity_gate",
    "requisite_variety_gate",
    "shannon_entropy",
    "von_neumann_entropy",
]

# Numerical tolerance for floating-point identity (PSD/trace/Hermitian checks).
_EPS = 1e-9


# === Information-theoretic primitives =======================================


def shannon_entropy(distribution: Sequence[float], base: float = 2.0) -> float:
    """Shannon entropy ``H = -sum p_i log_base p_i`` of a probability vector.

    The input is normalized to sum to 1 first.  Zero-probability events
    contribute zero (``0 log 0 := 0``).  Raises ``ValueError`` on negative
    mass or an all-zero vector.
    """
    arr = np.asarray(distribution, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError("distribution must be one-dimensional")
    if np.any(arr < -_EPS):
        raise ValueError("distribution has negative mass")
    arr = np.clip(arr, 0.0, None)
    total = float(arr.sum())
    if total <= _EPS:
        raise ValueError("distribution has zero total mass")
    p = arr / total
    nonzero = p[p > _EPS]
    return float(-np.sum(nonzero * (np.log(nonzero) / math.log(base))))


def von_neumann_entropy(rho: np.ndarray, base: float = 2.0) -> float:
    """Von Neumann entropy ``S(rho) = -tr(rho log rho)`` of a density operator.

    ``rho`` must be Hermitian, positive-semidefinite, and unit-trace.  The
    entropy is computed from the eigenvalues, so a *pure* state (one eigenvalue
    = 1, rest = 0) yields exactly ``0`` -- which is what the humility gate
    forbids.  A maximally mixed state on ``n`` levels yields ``log_base n``.
    """
    eigenvalues = _validate_density_matrix(rho)
    return shannon_entropy(eigenvalues, base=base)


def _validate_density_matrix(rho: np.ndarray) -> np.ndarray:
    """Validate ``rho`` is a density operator; return its real eigenvalues."""
    mat = np.asarray(rho, dtype=np.complex128)
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError("density matrix must be square")
    if not np.allclose(mat, mat.conj().T, atol=1e-7):
        raise ValueError("density matrix must be Hermitian")
    trace = complex(np.trace(mat))
    if abs(trace - 1.0) > 1e-6:
        raise ValueError(f"density matrix must have unit trace (got {trace:.6g})")
    eigenvalues = np.linalg.eigvalsh(mat)
    if np.any(eigenvalues < -1e-7):
        raise ValueError("density matrix must be positive-semidefinite")
    return np.clip(eigenvalues.real, 0.0, None)


def effective_rank(gram: np.ndarray) -> float:
    """Effective rank of a Gram/correlation matrix (Roy & Vetterli, 2007).

    ``erank = exp(H(normalized eigenvalues))`` in nats.  A set of perfectly
    collinear vectors has effective rank ~1 (one direction); a set of mutually
    orthogonal vectors of equal norm has effective rank = n.  This is the
    measure that makes "many-sidedness" ungameable: pasting the same opinion
    under three labels keeps the effective rank at 1.
    """
    mat = np.asarray(gram, dtype=np.float64)
    eigenvalues = np.linalg.eigvalsh(mat)
    eigenvalues = np.clip(eigenvalues.real, 0.0, None)
    total = float(eigenvalues.sum())
    if total <= _EPS:
        return 0.0
    p = eigenvalues / total
    nonzero = p[p > _EPS]
    entropy_nats = float(-np.sum(nonzero * np.log(nonzero)))
    return float(math.exp(entropy_nats))


# === Typed inputs ===========================================================


class FormalGateName(str, Enum):
    """The measured gates, named for the dharmic principle each enforces."""

    EPISTEMIC_HUMILITY = "epistemic_humility"  # anicca: no pure (certain) states
    ANEKANTA_CONTEXTUALITY = "anekanta_contextuality"  # genuine many-sidedness
    REQUISITE_VARIETY = "requisite_variety"  # Ashby: H(reg) >= H(disturbance)
    PROVENANCE_INTEGRITY = "provenance_integrity"  # pratityasamutpada / satya
    NON_INTERFERENCE = "non_interference"  # consent: no High->Low flow
    OBSERVER_SEPARATION = "observer_separation"  # anatta: measure != mutate


class DataLabel(str, Enum):
    """Confidentiality lattice for information-flow control (two-point)."""

    HIGH = "high"  # sensitive / secret
    LOW = "low"  # public-releasable


class BeliefState(BaseModel):
    """An agent's belief over mutually exclusive hypotheses.

    Two representations, both reduce to von Neumann entropy:

    * ``probabilities`` -- a classical categorical distribution (diagonal rho).
      Use this for ordinary calibrated confidence.
    * ``density_matrix`` -- a full density operator (list-of-rows, real or
      ``[re, im]`` pairs).  Use this only when off-diagonal coherence / order
      effects genuinely matter; most call sites want ``probabilities``.

    Exactly one must be provided.
    """

    model_config = ConfigDict(frozen=True)

    probabilities: Optional[list[float]] = None
    density_matrix: Optional[list[list[Any]]] = None
    labels: Optional[list[str]] = None

    @field_validator("probabilities")
    @classmethod
    def _check_probabilities(cls, v: Optional[list[float]]) -> Optional[list[float]]:
        if v is None:
            return v
        if len(v) < 1:
            raise ValueError("probabilities must be non-empty")
        if any(p < -_EPS for p in v):
            raise ValueError("probabilities must be non-negative")
        if sum(v) <= _EPS:
            raise ValueError("probabilities must have positive mass")
        return v

    def to_density_matrix(self) -> np.ndarray:
        """Return the density operator for this belief (diagonal if classical)."""
        if (self.probabilities is None) == (self.density_matrix is None):
            raise ValueError(
                "exactly one of probabilities or density_matrix must be set"
            )
        if self.probabilities is not None:
            p = np.asarray(self.probabilities, dtype=np.float64)
            p = p / p.sum()
            return np.diag(p).astype(np.complex128)
        rows = []
        for row in self.density_matrix or []:
            parsed = []
            for entry in row:
                if isinstance(entry, (list, tuple)) and len(entry) == 2:
                    parsed.append(complex(entry[0], entry[1]))
                else:
                    parsed.append(complex(entry))
            rows.append(parsed)
        return np.asarray(rows, dtype=np.complex128)

    def entropy(self, base: float = 2.0) -> float:
        """Von Neumann entropy of this belief (bits, by default)."""
        return von_neumann_entropy(self.to_density_matrix(), base=base)


class EvaluatorJudgment(BaseModel):
    """One evaluator's verdict, as a vector in a shared judgment space.

    ``vector`` is the evaluator's position (e.g. scores across criteria, or an
    embedding of its rationale).  Diversity is measured from the *geometry* of
    the judgment vectors, not from which keywords they contain.
    """

    model_config = ConfigDict(frozen=True)

    evaluator_id: str
    vector: list[float]
    frame: str = ""  # optional human label (mechanistic / phenomenological / ...)

    @field_validator("vector")
    @classmethod
    def _nonempty(cls, v: list[float]) -> list[float]:
        if not v:
            raise ValueError("judgment vector must be non-empty")
        return v


class ProvenanceClaim(BaseModel):
    """A single assertion with its confidence and supporting evidence ids."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class InformationFlow(BaseModel):
    """A declared flow of data from a labelled source to a sink."""

    model_config = ConfigDict(frozen=True)

    source_label: DataLabel
    sink_is_public: bool
    declassified: bool = False  # set only via an explicit, audited downgrade


class ActionContext(BaseModel):
    """The structured object every formal gate reads.

    Every field is optional: a gate is *skipped* (not failed) when the context
    lacks the data it needs, so callers populate only what is relevant to the
    action under review.  This is the typed replacement for the single action
    string the legacy gatekeeper inspects.
    """

    model_config = ConfigDict(frozen=True)

    action: str = ""
    actor_id: str = ""

    # epistemic humility
    belief: Optional[BeliefState] = None
    min_entropy_bits: float = 0.05  # S(rho) must exceed this; 0 == pure state

    # anekanta contextuality
    evaluator_judgments: list[EvaluatorJudgment] = Field(default_factory=list)
    min_effective_evaluators: float = 2.0

    # requisite variety (Ashby)
    regulator_distribution: Optional[list[float]] = None
    disturbance_distribution: Optional[list[float]] = None

    # provenance / satya
    provenance_claims: list[ProvenanceClaim] = Field(default_factory=list)
    high_confidence_threshold: float = 0.85

    # non-interference / consent
    information_flows: list[InformationFlow] = Field(default_factory=list)

    # observer separation / anatta
    observer_id: Optional[str] = None
    observed_id: Optional[str] = None
    measures_state: bool = False
    mutates_state: bool = False


# === Result models ==========================================================


class FormalGateResult(BaseModel):
    """The verdict of a single formal gate, with the measured quantity."""

    gate: FormalGateName
    tier: GateTier
    result: GateResult
    measure: float  # the number the gate computed (entropy, erank, gap, ...)
    threshold: float
    reason: str
    detail: dict[str, Any] = Field(default_factory=dict)

    @property
    def skipped(self) -> bool:
        return self.result == GateResult.PASS and self.reason.startswith("skipped:")


class FormalGateReport(BaseModel):
    """Aggregate verdict across all applicable formal gates."""

    decision: GateDecision
    results: list[FormalGateResult]
    evaluated_at: str = Field(default_factory=lambda: _utc_now().isoformat())
    receipt_sha256: str = ""

    def by_gate(self, gate: FormalGateName) -> Optional[FormalGateResult]:
        for r in self.results:
            if r.gate == gate:
                return r
        return None

    def compute_receipt(self) -> str:
        """Deterministic content hash over the (gate, result, measure) tuples."""
        payload = [
            {
                "gate": r.gate.value,
                "tier": r.tier.value,
                "result": r.result.value,
                "measure": round(r.measure, 9),
                "threshold": round(r.threshold, 9),
            }
            for r in self.results
        ]
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# === The gates ==============================================================


def _skip(gate: FormalGateName, tier: GateTier, why: str) -> FormalGateResult:
    return FormalGateResult(
        gate=gate,
        tier=tier,
        result=GateResult.PASS,
        measure=float("nan"),
        threshold=float("nan"),
        reason=f"skipped: {why}",
    )


def epistemic_humility_gate(
    belief: Optional[BeliefState],
    min_entropy_bits: float = 0.05,
) -> FormalGateResult:
    """Anicca / epistemic humility: forbid pure (certain) belief states.

    A belief is admissible iff ``S(rho) > min_entropy_bits``.  A pure state --
    "I am 100% certain" -- has entropy exactly 0 and is blocked.  This is the
    continuous, ungameable replacement for the prose constraint
    ``confidence < 1.0``.
    """
    gate = FormalGateName.EPISTEMIC_HUMILITY
    tier = GateTier.B
    if belief is None:
        return _skip(gate, tier, "no belief state provided")
    entropy = belief.entropy(base=2.0)
    if entropy > min_entropy_bits:
        return FormalGateResult(
            gate=gate, tier=tier, result=GateResult.PASS,
            measure=entropy, threshold=min_entropy_bits,
            reason=f"S(rho)={entropy:.4f} bits > {min_entropy_bits}",
        )
    return FormalGateResult(
        gate=gate, tier=tier, result=GateResult.FAIL,
        measure=entropy, threshold=min_entropy_bits,
        reason=(
            f"belief is effectively certain (S(rho)={entropy:.4f} bits "
            f"<= {min_entropy_bits}); certainty is forbidden"
        ),
    )


def anekanta_contextuality_gate(
    judgments: Sequence[EvaluatorJudgment],
    min_effective_evaluators: float = 2.0,
) -> FormalGateResult:
    """Anekantavada: require genuine, non-collinear many-sidedness.

    Builds the normalized Gram matrix of the evaluator judgment vectors and
    requires its **effective rank** to exceed ``min_effective_evaluators``.
    Three evaluators that all say the same thing collapse to effective rank ~1
    and FAIL, even if their text contains all the right keywords -- which is
    precisely the gaming that the legacy keyword-frame check could not stop.
    """
    gate = FormalGateName.ANEKANTA_CONTEXTUALITY
    tier = GateTier.C
    if len(judgments) < 2:
        return _skip(gate, tier, "fewer than 2 evaluators")
    dim = len(judgments[0].vector)
    if any(len(j.vector) != dim for j in judgments):
        raise ValueError("all judgment vectors must share one dimensionality")
    matrix = np.asarray([j.vector for j in judgments], dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms < _EPS] = 1.0
    unit = matrix / norms
    gram = unit @ unit.T
    erank = effective_rank(gram)
    detail = {"n_evaluators": len(judgments), "effective_rank": erank}
    if erank >= min_effective_evaluators - _EPS:
        return FormalGateResult(
            gate=gate, tier=tier, result=GateResult.PASS,
            measure=erank, threshold=min_effective_evaluators,
            reason=f"effective rank {erank:.3f} >= {min_effective_evaluators}",
            detail=detail,
        )
    return FormalGateResult(
        gate=gate, tier=tier, result=GateResult.WARN,
        measure=erank, threshold=min_effective_evaluators,
        reason=(
            f"evaluators are near-collinear (effective rank {erank:.3f} < "
            f"{min_effective_evaluators}); not genuine many-sidedness"
        ),
        detail=detail,
    )


def requisite_variety_gate(
    regulator_distribution: Optional[Sequence[float]],
    disturbance_distribution: Optional[Sequence[float]],
) -> FormalGateResult:
    """Ashby's law of requisite variety: ``H(regulator) >= H(disturbance)``.

    Only variety can absorb variety.  If the governing repertoire has less
    entropy than the disturbances it must regulate, the system is structurally
    under-resourced and the gate warns.
    """
    gate = FormalGateName.REQUISITE_VARIETY
    tier = GateTier.C
    if regulator_distribution is None or disturbance_distribution is None:
        return _skip(gate, tier, "regulator/disturbance distributions absent")
    h_reg = shannon_entropy(regulator_distribution)
    h_dist = shannon_entropy(disturbance_distribution)
    gap = h_reg - h_dist
    detail = {"H_regulator": h_reg, "H_disturbance": h_dist}
    if gap >= -_EPS:
        return FormalGateResult(
            gate=gate, tier=tier, result=GateResult.PASS,
            measure=gap, threshold=0.0,
            reason=f"H(reg)={h_reg:.3f} >= H(dist)={h_dist:.3f}",
            detail=detail,
        )
    return FormalGateResult(
        gate=gate, tier=tier, result=GateResult.WARN,
        measure=gap, threshold=0.0,
        reason=(
            f"insufficient requisite variety: H(reg)={h_reg:.3f} < "
            f"H(dist)={h_dist:.3f}"
        ),
        detail=detail,
    )


def provenance_integrity_gate(
    claims: Sequence[ProvenanceClaim],
    high_confidence_threshold: float = 0.85,
) -> FormalGateResult:
    """Satya / pratityasamutpada: no high-confidence claim without evidence.

    Every assertion whose confidence exceeds the threshold must carry at least
    one evidence id.  Orphan high-confidence claims (dependent origination
    violated) FAIL the gate.  The measure is the orphan count.
    """
    gate = FormalGateName.PROVENANCE_INTEGRITY
    tier = GateTier.B
    if not claims:
        return _skip(gate, tier, "no provenance claims provided")
    orphans = [
        c.claim_id
        for c in claims
        if c.confidence >= high_confidence_threshold and not c.evidence_ids
    ]
    detail = {"orphan_claims": orphans, "n_claims": len(claims)}
    if not orphans:
        return FormalGateResult(
            gate=gate, tier=tier, result=GateResult.PASS,
            measure=0.0, threshold=0.0,
            reason="all high-confidence claims carry evidence",
            detail=detail,
        )
    return FormalGateResult(
        gate=gate, tier=tier, result=GateResult.FAIL,
        measure=float(len(orphans)), threshold=0.0,
        reason=(
            f"{len(orphans)} high-confidence claim(s) without evidence: "
            f"{', '.join(orphans)}"
        ),
        detail=detail,
    )


def noninterference_gate(flows: Sequence[InformationFlow]) -> FormalGateResult:
    """Consent / non-interference: no HIGH data reaches a public sink.

    A two-point Goguen-Meseguer non-interference check: a flow from a HIGH
    source to a public sink violates confidentiality unless it has been
    explicitly, auditably declassified.  This replaces the legacy
    ``sensitive_path AND exfil_word`` substring conjunction with a real
    information-flow predicate.
    """
    gate = FormalGateName.NON_INTERFERENCE
    tier = GateTier.A
    if not flows:
        return _skip(gate, tier, "no information flows declared")
    leaks = [
        f
        for f in flows
        if f.source_label == DataLabel.HIGH
        and f.sink_is_public
        and not f.declassified
    ]
    detail = {"n_flows": len(flows), "leaks": len(leaks)}
    if not leaks:
        return FormalGateResult(
            gate=gate, tier=tier, result=GateResult.PASS,
            measure=0.0, threshold=0.0,
            reason="no high->public information flow",
            detail=detail,
        )
    return FormalGateResult(
        gate=gate, tier=tier, result=GateResult.FAIL,
        measure=float(len(leaks)), threshold=0.0,
        reason=(
            f"{len(leaks)} undeclassified HIGH->public flow(s): "
            f"non-interference violated"
        ),
        detail=detail,
    )


def observer_separation_gate(
    observer_id: Optional[str],
    observed_id: Optional[str],
    measures_state: bool,
    mutates_state: bool,
) -> FormalGateResult:
    """Anatta / observer separation: the observer is not the observed, and a
    single transaction may not both measure and mutate the same state.

    The first clause is the legacy ``observer_id != observed_id`` predicate
    (kept).  The second is the quantum-inspired rule that measurement and
    unitary evolution are distinct operations -- you cannot read your own state
    and rewrite it in one atomic step, which is exactly the in-process
    self-signing failure mode the kernel must avoid.
    """
    gate = FormalGateName.OBSERVER_SEPARATION
    tier = GateTier.A
    if observer_id is None and observed_id is None and not measures_state:
        return _skip(gate, tier, "no observation declared")
    if observer_id is not None and observer_id == observed_id:
        return FormalGateResult(
            gate=gate, tier=tier, result=GateResult.FAIL,
            measure=1.0, threshold=0.0,
            reason=f"observer == observed ({observer_id})",
        )
    if measures_state and mutates_state:
        return FormalGateResult(
            gate=gate, tier=tier, result=GateResult.FAIL,
            measure=1.0, threshold=0.0,
            reason="single transaction both measures and mutates the same state",
        )
    return FormalGateResult(
        gate=gate, tier=tier, result=GateResult.PASS,
        measure=0.0, threshold=0.0,
        reason="observer separated from observed; measure/mutate disjoint",
    )


# === Composed gatekeeper ====================================================


def evaluate_formal_gates(context: ActionContext) -> FormalGateReport:
    """Run every applicable formal gate over ``context`` and aggregate.

    Decision rule mirrors the legacy tiering:
      * any Tier-A FAIL -> BLOCK
      * any Tier-B FAIL -> BLOCK
      * any Tier-C FAIL/WARN (and no A/B block) -> REVIEW
      * otherwise -> ALLOW
    """
    results = [
        observer_separation_gate(
            context.observer_id,
            context.observed_id,
            context.measures_state,
            context.mutates_state,
        ),
        noninterference_gate(context.information_flows),
        epistemic_humility_gate(context.belief, context.min_entropy_bits),
        provenance_integrity_gate(
            context.provenance_claims, context.high_confidence_threshold
        ),
        anekanta_contextuality_gate(
            context.evaluator_judgments, context.min_effective_evaluators
        ),
        requisite_variety_gate(
            context.regulator_distribution, context.disturbance_distribution
        ),
    ]

    def _failed(tier: GateTier) -> bool:
        return any(
            r.tier == tier and r.result == GateResult.FAIL for r in results
        )

    if _failed(GateTier.A) or _failed(GateTier.B):
        decision = GateDecision.BLOCK
    elif any(
        r.tier == GateTier.C and r.result in (GateResult.FAIL, GateResult.WARN)
        for r in results
    ):
        decision = GateDecision.REVIEW
    else:
        decision = GateDecision.ALLOW

    report = FormalGateReport(decision=decision, results=results)
    report.receipt_sha256 = report.compute_receipt()
    return report


class FormalTelosGatekeeper:
    """Composes the legacy keyword gatekeeper (Tier-0 lint) with the formal
    measured gates (Tier 1+).

    The legacy gatekeeper is a cheap, fast first line of defence against
    obviously-harmful action strings.  It is *not* discarded -- it runs first,
    and any BLOCK it raises short-circuits.  When it allows, the formal gates
    evaluate the structured context and produce the auditable, measured
    verdict.  This is additive: existing callers of the keyword gatekeeper are
    unaffected, and new callers opt in by constructing an :class:`ActionContext`.
    """

    def __init__(self, keyword_gatekeeper: Any | None = None) -> None:
        if keyword_gatekeeper is None:
            # Imported lazily to avoid a hard import cycle at module load.
            from dharma_swarm.telos_gates import TelosGatekeeper

            keyword_gatekeeper = TelosGatekeeper()
        self._keyword = keyword_gatekeeper

    def check(
        self,
        context: ActionContext,
        *,
        content: str = "",
        tool_name: str = "",
        run_keyword_prefilter: bool = True,
    ) -> tuple[GateDecision, FormalGateReport, Optional[Mapping[str, Any]]]:
        """Run the Tier-0 keyword lint then the formal gates.

        Returns ``(decision, formal_report, keyword_result_or_None)``.  If the
        keyword pre-filter blocks, the formal gates are skipped and its block
        decision wins.
        """
        keyword_payload: Optional[Mapping[str, Any]] = None
        if run_keyword_prefilter:
            keyword_check = self._keyword.check(
                action=context.action, content=content, tool_name=tool_name
            )
            keyword_payload = {
                "decision": keyword_check.decision,
                "gate": keyword_check.gate,
                "reason": keyword_check.reason,
            }
            if keyword_check.decision == GateDecision.BLOCK:
                blocked = evaluate_formal_gates(context)
                return GateDecision.BLOCK, blocked, keyword_payload

        report = evaluate_formal_gates(context)
        return report.decision, report, keyword_payload
