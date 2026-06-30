"""Typed inputs and result models for the formal telos gates."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from dharma_swarm.models import GateDecision, GateResult, GateTier, _utc_now
from dharma_swarm.telos_formal_math import (
    EPS,
    validate_density_matrix,
    von_neumann_entropy,
)

__all__ = [
    "ActionContext",
    "BeliefState",
    "DataLabel",
    "EvaluatorJudgment",
    "FormalGateName",
    "FormalGateResult",
    "FormalGateReport",
    "InformationFlow",
    "ProvenanceClaim",
]


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
    """An agent's belief over mutually exclusive hypotheses."""

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
        if any(p < -EPS for p in v):
            raise ValueError("probabilities must be non-negative")
        if sum(v) <= EPS:
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
        matrix = self.to_density_matrix()
        validate_density_matrix(matrix)
        return von_neumann_entropy(matrix, base=base)


class EvaluatorJudgment(BaseModel):
    """One evaluator's verdict, as a vector in a shared judgment space."""

    model_config = ConfigDict(frozen=True)

    evaluator_id: str
    vector: list[float]
    frame: str = ""

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
    declassified: bool = False


class ActionContext(BaseModel):
    """The structured object every formal gate reads."""

    model_config = ConfigDict(frozen=True)

    action: str = ""
    actor_id: str = ""

    belief: Optional[BeliefState] = None
    min_entropy_bits: float = 0.05

    evaluator_judgments: list[EvaluatorJudgment] = Field(default_factory=list)
    min_effective_evaluators: float = 2.0

    regulator_distribution: Optional[list[float]] = None
    disturbance_distribution: Optional[list[float]] = None

    provenance_claims: list[ProvenanceClaim] = Field(default_factory=list)
    high_confidence_threshold: float = 0.85

    information_flows: list[InformationFlow] = Field(default_factory=list)

    observer_id: Optional[str] = None
    observed_id: Optional[str] = None
    measures_state: bool = False
    mutates_state: bool = False


class FormalGateResult(BaseModel):
    """The verdict of a single formal gate, with the measured quantity."""

    gate: FormalGateName
    tier: GateTier
    result: GateResult
    measure: float
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
