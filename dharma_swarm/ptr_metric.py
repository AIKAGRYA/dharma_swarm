"""Predictive Telic Repair (PTR) shadow metric.

PTR is a recomputable, negative-authority readiness score. It sits above
TCS: TCS contributes the S5 identity pillar, but PTR also requires verified
repair, live actuation, repo integrity, and governance integrity.

This module is deliberately pure. It does not run subprocesses, inspect git,
invoke pytest, call models, mutate runtime behavior, or grant authority.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PTR_VERSION = "ptr.v0"

DEFAULT_STATE_DIR = Path.home() / ".dharma"
DEFAULT_SCORE_PATH = DEFAULT_STATE_DIR / "meta" / "ptr_score.json"
DEFAULT_HISTORY_PATH = DEFAULT_STATE_DIR / "meta" / "ptr_history.jsonl"

MISSING_PRIOR = 0.35
EPSILON = 1e-6
OMEGA_FREE_BAND = 0.15
OMEGA_DIVERGENCE_THRESHOLD = 0.40
TCS_DRIFT_THRESHOLD = 0.40
TCS_CRITICAL_THRESHOLD = 0.25
NON_AUTHORITATIVE_FLAGS = frozenset({"provisional", "low_coverage"})
HOLD_FLAGS = frozenset({"sustained_tcs_critical", "sustained_omega_divergence"})
CAUTION_FLAGS = frozenset({"near_eigenform"})

PILLAR_WEIGHTS: dict[str, float] = {
    "predictive_repair": 0.30,
    "actuation_liveness": 0.20,
    "repo_integrity": 0.20,
    "governance_integrity": 0.20,
    "tcs_identity": 0.10,
}

CORE_REQUIRED_PILLARS = ("predictive_repair", "governance_integrity")

VERDICT_ORDER = {
    "INSUFFICIENT_EVIDENCE": 0,
    "HOLD": 1,
    "REPAIR_MODE": 2,
    "CAUTION": 3,
    "PROCEED": 4,
}

PTR_AUTONOMY_CAP = {
    "PROCEED": 2,  # HUMAN_ON_LOOP; PTR never raises autonomy.
    "CAUTION": 2,
    "REPAIR_MODE": 1,  # HUMAN_SUPERVISED
    "HOLD": 1,
    "INSUFFICIENT_EVIDENCE": 1,
}


@dataclass(frozen=True)
class PTRPillar:
    """One pillar input to the PTR score.

    ``point`` is the observed score. ``lcb90`` is a conservative lower bound
    supplied by the caller when available. If no lower bound is supplied, the
    scorer uses the point estimate directly.
    """

    point: float | None
    lcb90: float | None = None
    confidence: float = 1.0
    missing: bool = False
    stale: bool = False
    evidence_refs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    def is_missing(self) -> bool:
        return self.missing or _finite_or_none(self.point) is None

    def point_value(self) -> float | None:
        value = _finite_or_none(self.point)
        return _clamp01(value) if value is not None else None

    def lower_bound_value(self) -> float | None:
        value = _finite_or_none(self.lcb90)
        if value is None:
            value = _finite_or_none(self.point)
        return _clamp01(value) if value is not None else None


@dataclass(frozen=True)
class PTRInputs:
    """Complete input vector for a PTR computation."""

    predictive_repair: PTRPillar
    tcs_identity: PTRPillar
    actuation_liveness: PTRPillar
    repo_integrity: PTRPillar
    governance_integrity: PTRPillar
    tcs: float | None = None
    live_score: float | None = None
    calibration_confidence: float = 1.0
    coverage_confidence: float | None = None
    independence_confidence: float = 1.0
    sustained_omega_cycles: int = 0
    sustained_low_tcs_cycles: int = 0
    source: str = "manual"

    def pillars(self) -> dict[str, PTRPillar]:
        return {
            "predictive_repair": self.predictive_repair,
            "tcs_identity": self.tcs_identity,
            "actuation_liveness": self.actuation_liveness,
            "repo_integrity": self.repo_integrity,
            "governance_integrity": self.governance_integrity,
        }


@dataclass(frozen=True)
class PTRScore:
    """Output of ``compute_ptr_score``."""

    ptr_version: str
    computed_at: str
    source: str
    ptr: float
    ptr_raw: float
    verdict: str
    authoritative: bool
    confidence: float
    omega_delta: float | None
    omega_attenuator: float
    ptr_autonomy_cap: int
    authority_model: str
    components: dict[str, float | None]
    component_lcb90: dict[str, float]
    weights: dict[str, float]
    caps: list[str] = field(default_factory=list)
    inputs_stale: list[str] = field(default_factory=list)
    missingness: list[dict[str, str]] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return _json_safe(payload)


def compute_ptr_score(inputs: PTRInputs, *, now: datetime | None = None) -> PTRScore:
    """Compute a PTR shadow score from a complete pillar vector.

    The returned score is recomputable from explicit inputs and never grants
    permission. Consumers may use the verdict only as warning, repair pressure,
    or downward autonomy cap.
    """

    now = now or datetime.now(timezone.utc)
    pillars = inputs.pillars()

    components: dict[str, float | None] = {}
    component_lcb90: dict[str, float] = {}
    missingness: list[dict[str, str]] = []
    inputs_stale: list[str] = []
    evidence_refs: list[str] = []
    notes: list[str] = []
    caps: list[str] = []

    coverage_units = 0.0
    pillar_conf_terms: list[tuple[float, float]] = []

    for name, pillar in pillars.items():
        point = pillar.point_value()
        missing = pillar.is_missing()
        effective = pillar.lower_bound_value()

        components[name] = point
        if missing:
            effective = MISSING_PRIOR
            missingness.append({"pillar": name, "kind": "missing"})
        elif effective is None:
            effective = MISSING_PRIOR
            missingness.append({"pillar": name, "kind": "invalid"})
        if name == "tcs_identity":
            effective = min(0.85, effective)

        if pillar.stale:
            inputs_stale.append(name)
            coverage_units += 0.5
        elif not missing:
            coverage_units += 1.0

        confidence = 0.0 if missing else _clamp01(pillar.confidence)
        if pillar.stale:
            confidence = min(confidence, 0.5)
        pillar_conf_terms.append((PILLAR_WEIGHTS[name], confidence))

        component_lcb90[name] = _clamp01(effective)
        evidence_refs.extend(pillar.evidence_refs)
        notes.extend(pillar.notes)
        for flag in pillar.flags:
            if flag not in caps:
                caps.append(flag)

    ptr_raw = _weighted_geomean(component_lcb90, PILLAR_WEIGHTS)

    computed_coverage = (coverage_units / max(1, len(PILLAR_WEIGHTS))) ** 2
    coverage_confidence = (
        _clamp01(inputs.coverage_confidence)
        if inputs.coverage_confidence is not None
        else _clamp01(computed_coverage)
    )
    pillar_confidence = _weighted_confidence(pillar_conf_terms)
    confidence = (
        pillar_confidence
        * _clamp01(inputs.calibration_confidence)
        * coverage_confidence
        * _clamp01(inputs.independence_confidence)
    )

    tcs_value = _resolve_tcs_value(inputs, pillars["tcs_identity"])
    live_value = _finite_or_none(inputs.live_score)
    omega_delta = None
    omega_attenuator = 1.0
    if tcs_value is not None and live_value is not None:
        omega_delta = abs(_clamp01(live_value) - _clamp01(tcs_value))
        omega_attenuator = omega_attenuation(omega_delta)
        if omega_delta >= OMEGA_DIVERGENCE_THRESHOLD:
            caps.append("omega_divergence")
        elif omega_delta > OMEGA_FREE_BAND:
            caps.append("omega_pressure")
    else:
        missingness.append({"pillar": "omega", "kind": "missing_tcs_or_live_score"})

    ptr = ptr_raw * confidence * omega_attenuator

    core_missing = any(pillars[name].is_missing() for name in CORE_REQUIRED_PILLARS)
    non_authoritative_flags = sorted(set(caps) & NON_AUTHORITATIVE_FLAGS)
    authoritative = not core_missing and not non_authoritative_flags
    if core_missing:
        caps.append("core_evidence_missing")
    if non_authoritative_flags:
        caps.append("authority_withheld")
    for flag in non_authoritative_flags:
        missingness.append({"pillar": "authority", "kind": flag})

    repo_lcb = component_lcb90["repo_integrity"]
    governance_lcb = component_lcb90["governance_integrity"]
    tcs_lcb = component_lcb90["tcs_identity"]

    if repo_lcb < 0.50:
        caps.append("repo_integrity_low")
    if governance_lcb < 0.50:
        caps.append("governance_integrity_low")
    if tcs_lcb < TCS_DRIFT_THRESHOLD:
        caps.append("tcs_drift")
    if tcs_lcb < TCS_CRITICAL_THRESHOLD and inputs.sustained_low_tcs_cycles >= 3:
        caps.append("sustained_tcs_critical")
    if (
        omega_delta is not None
        and omega_delta >= OMEGA_DIVERGENCE_THRESHOLD
        and inputs.sustained_omega_cycles >= 3
    ):
        caps.append("sustained_omega_divergence")

    verdict = _base_verdict(ptr, authoritative)
    if authoritative and (repo_lcb < 0.50 or governance_lcb < 0.50):
        verdict = "HOLD"
    if omega_delta is not None and omega_delta >= OMEGA_DIVERGENCE_THRESHOLD:
        verdict = _cap_verdict(verdict, "CAUTION")
    if tcs_lcb < TCS_DRIFT_THRESHOLD:
        verdict = _cap_verdict(verdict, "CAUTION")
    if set(caps) & CAUTION_FLAGS:
        verdict = _cap_verdict(verdict, "CAUTION")
    if set(caps) & HOLD_FLAGS:
        verdict = "HOLD"

    return PTRScore(
        ptr_version=PTR_VERSION,
        computed_at=now.isoformat(),
        source=inputs.source,
        ptr=round(_clamp01(ptr), 4),
        ptr_raw=round(_clamp01(ptr_raw), 4),
        verdict=verdict,
        authoritative=authoritative,
        confidence=round(_clamp01(confidence), 4),
        omega_delta=round(omega_delta, 4) if omega_delta is not None else None,
        omega_attenuator=round(_clamp01(omega_attenuator), 4),
        ptr_autonomy_cap=PTR_AUTONOMY_CAP[verdict],
        authority_model="negative_only",
        components=components,
        component_lcb90={k: round(v, 4) for k, v in component_lcb90.items()},
        weights=dict(PILLAR_WEIGHTS),
        caps=sorted(set(caps)),
        inputs_stale=sorted(set(inputs_stale)),
        missingness=missingness,
        evidence_refs=sorted(set(evidence_refs)),
        notes=notes,
    )


def omega_attenuation(omega_delta: float | None) -> float:
    """Return PTR attenuation for TCS/live divergence."""

    value = _finite_or_none(omega_delta)
    if value is None:
        return 1.0
    value = max(0.0, value)
    if value <= OMEGA_FREE_BAND:
        return 1.0
    scaled = (value - OMEGA_FREE_BAND) / 0.25
    return _clamp01(max(0.25, math.exp(-2.0 * scaled * scaled)))


def conservative_lcb(
    point: float | None,
    confidence: float,
    *,
    prior: float = MISSING_PRIOR,
) -> float | None:
    """Shrink a point estimate toward a conservative prior."""

    value = _finite_or_none(point)
    if value is None:
        return None
    conf = _clamp01(confidence)
    return _clamp01(prior + ((_clamp01(value) - prior) * conf))


def pillar_from_repair_score(repair_score: Any) -> PTRPillar:
    """Build the predictive-repair pillar from ``r_repair_metric.RepairScore``."""

    point = _finite_or_none(getattr(repair_score, "r_aggregate", None))
    confidence = _clamp01(getattr(repair_score, "confidence", 0.0))
    notes = list(getattr(repair_score, "notes", []) or [])
    flags: list[str] = []
    if getattr(repair_score, "provisional", False):
        flags.append("provisional")
    if getattr(repair_score, "near_eigenform", False):
        flags.append("near_eigenform")

    return PTRPillar(
        point=point,
        lcb90=conservative_lcb(point, confidence),
        confidence=confidence,
        missing=point is None,
        evidence_refs=["r_repair_metric"],
        notes=notes,
        flags=flags,
    )


def pillar_from_tcs(
    tcs: float | None,
    *,
    confidence: float = 1.0,
    evidence_ref: str = "identity",
) -> PTRPillar:
    """Build the TCS identity pillar."""

    value = _finite_or_none(tcs)
    effective = min(0.85, _clamp01(value)) if value is not None else None
    return PTRPillar(
        point=value,
        lcb90=effective,
        confidence=confidence,
        missing=value is None,
        evidence_refs=[evidence_ref],
    )


def persist_ptr_score(
    score: PTRScore,
    *,
    score_path: Path | None = None,
    history_path: Path | None = None,
) -> bool:
    """Persist latest PTR score and append history JSONL."""

    score_path = score_path or DEFAULT_SCORE_PATH
    history_path = history_path or DEFAULT_HISTORY_PATH
    payload = score.to_dict()
    ok = True

    try:
        score_path.parent.mkdir(parents=True, exist_ok=True)
        score_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError:
        ok = False

    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")
    except OSError:
        ok = False

    return ok


def read_latest_ptr_score(path: Path | None = None) -> dict[str, Any] | None:
    """Read a persisted PTR score. Returns None on missing or malformed JSON."""

    path = path or DEFAULT_SCORE_PATH
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _base_verdict(ptr: float, authoritative: bool) -> str:
    if not authoritative:
        return "INSUFFICIENT_EVIDENCE"
    if ptr >= 0.70:
        return "PROCEED"
    if ptr >= 0.55:
        return "CAUTION"
    if ptr >= 0.40:
        return "REPAIR_MODE"
    return "HOLD"


def _cap_verdict(current: str, max_verdict: str) -> str:
    if VERDICT_ORDER[current] > VERDICT_ORDER[max_verdict]:
        return max_verdict
    return current


def _resolve_tcs_value(inputs: PTRInputs, pillar: PTRPillar) -> float | None:
    explicit = _finite_or_none(inputs.tcs)
    if explicit is not None:
        return explicit
    return pillar.point_value()


def _weighted_geomean(values: dict[str, float], weights: dict[str, float]) -> float:
    total_weight = sum(weights.values()) or 1.0
    total = 0.0
    for key, weight in weights.items():
        value = max(EPSILON, _clamp01(values[key]))
        total += (weight / total_weight) * math.log(value)
    return _clamp01(math.exp(total))


def _weighted_confidence(weighted_confidences: list[tuple[float, float]]) -> float:
    total_weight = sum(weight for weight, _ in weighted_confidences) or 1.0
    total = 0.0
    for weight, confidence in weighted_confidences:
        total += (weight / total_weight) * math.log(max(EPSILON, _clamp01(confidence)))
    return _clamp01(math.exp(total))


def _finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _clamp01(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


__all__ = [
    "PTRInputs",
    "PTRPillar",
    "PTRScore",
    "compute_ptr_score",
    "conservative_lcb",
    "omega_attenuation",
    "persist_ptr_score",
    "pillar_from_repair_score",
    "pillar_from_tcs",
    "read_latest_ptr_score",
]
