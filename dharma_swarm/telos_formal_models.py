"""Typed inputs and result models for the formal telos gates."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from enum import Enum
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from dharma_swarm.models import GateDecision, GateResult, GateTier, _utc_now
from dharma_swarm.telos_formal_math import EPS, von_neumann_entropy

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

    EPISTEMIC_HUMILITY = "epistemic_humility"
    ANEKANTA_CONTEXTUALITY = "anekanta_contextuality"
    REQUISITE_VARIETY = "requisite_variety"
    PROVENANCE_INTEGRITY = "provenance_integrity"
    NON_INTERFERENCE = "non_interference"
    OBSERVER_SEPARATION = "observer_separation"


class DataLabel(str, Enum):
    """Confidentiality lattice for information-flow control."""

    LOW = "low"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    HIGH = "high"


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
        if (self.probabilities is None) == (self.density_matrix is None):
            raise ValueError("exactly one of probabilities or density_matrix must be set")
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
        return von_neumann_entropy(self.to_density_matrix(), base=base)


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
    max_belief_mass: float = 0.97
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
    """Aggregate verdict across all applicable formal gates.

    The unkeyed SHA-256 receipt is tamper-evident; the optional HMAC is the
    tamper-resistant form when a key is available.
    """

    model_config = ConfigDict(validate_assignment=True)

    decision: GateDecision
    results: list[FormalGateResult]
    evaluated_at: str = Field(default_factory=lambda: _utc_now().isoformat())
    receipt_sha256: str = ""
    receipt_hmac: str = ""

    @staticmethod
    def _float_to_json(value: float) -> float | None:
        return None if not math.isfinite(value) else round(value, 9)

    def _canonical_payload(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "results": [
                {
                    "gate": r.gate.value,
                    "tier": r.tier.value,
                    "result": r.result.value,
                    "measure": self._float_to_json(r.measure),
                    "threshold": self._float_to_json(r.threshold),
                }
                for r in self.results
            ],
        }

    def _canonical_json(self) -> str:
        return json.dumps(
            self._canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def by_gate(self, gate: FormalGateName) -> Optional[FormalGateResult]:
        for r in self.results:
            if r.gate == gate:
                return r
        return None

    def compute_receipt(self) -> str:
        return hashlib.sha256(self._canonical_json().encode("utf-8")).hexdigest()

    def receipt_matches(self) -> bool:
        return hmac.compare_digest(self.receipt_sha256, self.compute_receipt())

    def sign(self, key: bytes) -> str:
        self.receipt_hmac = hmac.new(
            key,
            self._canonical_json().encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return self.receipt_hmac
