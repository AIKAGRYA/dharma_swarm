"""welfare_attribution - external welfare sensor feedback channel.

Component 1.6 of the OMEGA Layer + Causal Closure plan
(~/.claude/plans/a-structural-dazzling-garden.md).

WHY THIS EXISTS
---------------
The plan: "External welfare grounding via welfare_ton_mrv certificates
feeding back into evolution fitness — the only fitness signal that
survives Goodhart because it grounds outside the system."

Without an external sensor the system is grading its own homework.
Welfare-Ton certificates are issued from satellite imagery + on-the-ground
verification + livelihood survey - genuinely outside the agent's
generative substrate. Wiring them into Proposal.fitness_after_deployment
closes the outer cybernetic loop with reality.

DESIGN: STANDALONE, DUCK-TYPED, MOCKABLE
----------------------------------------
welfare_ton_mrv currently exists as a stub package in canonical
(governance/tier-1-install). Its internal modules (models.py,
verifier.py, satellite.py) are not yet implemented. To build this
component WITHOUT depending on welfare_ton_mrv being merged or filled
in:

  1. We accept ANY object that exposes the Certificate Protocol below
     (duck typing). Tests provide MockCertificate.
  2. We never import from welfare_ton_mrv. Wiring at the certificate-
     issued callback site happens at merge phase by the caller, who
     converts WelfareTonCertificate -> our protocol-compatible shape.

This keeps Component 1.6 shippable and tested even though its
production datasource isn't ready.

CERTIFICATE PROTOCOL (duck-typed)
---------------------------------
An object that has:
  certificate_id: str
  issued_at: str (ISO8601 UTC)
  domain: str  ("carbon" | "biodiversity" | "livelihood" | "soil_health"
                | "composite")
  project_id: str  (the WelfareTonProject id)
  project_code_paths: list[str]  (file/module paths the project touches)
  evidence: list[str]  (decision_ids cited as evidence in verification)
  outcome: dict[str, float]  (e.g., {"carbon_kgco2e": -1500.0,
                                     "biodiversity_index": 0.12})

PROPOSAL PROTOCOL (duck-typed)
------------------------------
An object that has:
  id: str
  component: str  (the touched module)
  description: str
  affected_files: list[str]
  decision_at: str (ISO8601 UTC)
  fitness_after_deployment: list[dict]  (the field we MUTATE)
  predicted_outcome: dict[str, float] | None  (optional)
  jagat_kalyan_register_links: list[str]  (decision_ids registered as
                                            welfare-related)

ATTRIBUTION HEURISTIC (honest about limits)
-------------------------------------------
Causal attribution from agent decisions to multi-month welfare outcomes
is the hardest problem in the entire plan. We do NOT claim to solve it.
We provide a defensible heuristic whose biases are documented:

    directness(decision, cert) =
        0.40 * topical_overlap(decision.affected_files,
                               cert.project_code_paths)
      + 0.30 * temporal_proximity(decision.decision_at,
                                   cert.issued_at)
      + 0.20 * register_link(decision.id,
                             cert.project_id,
                             decision.jagat_kalyan_register_links)
      + 0.10 * citation_in_cert(decision.id, cert.evidence)

Decisions with directness < ATTRIBUTION_FLOOR are dropped. Remaining are
normalized to sum 1.0. Total welfare score is composed from outcome
dimensions.

KNOWN LIMITS:
1. Confounding. The agent shares credit with humans, weather, policy.
   We report `unattributed_delta` so the system never claims sole credit.
2. Time horizon mismatch. Carbon outcomes lag 6-24 months; this version
   catches short-loop signals only.
3. Goodhart. Proposers might learn to register-link spuriously to up
   their score. Mitigation: register_link weight is bounded; large
   attribution shifts (>20%) require Mahakali-eligible review.

FITNESS BUDGET (Goodhart firewall)
----------------------------------
DarwinEngine's effective fitness reads welfare-attribution at
`welfare_evidence_weight` (intentionally small, default 0.05). We
also clamp `delta_applied` per certificate per entry to ±0.1 so a
single big number cannot swing rankings.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ATTRIBUTION_FLOOR: float = 0.15
DELTA_CLAMP: float = 0.10  # max |delta_applied| per certificate per entry
TEMPORAL_PROXIMITY_TAU_DAYS: float = 14.0  # exp decay half-life
ATTRIBUTION_LOG_PATH = (
    Path.home() / ".dharma" / "welfare" / "attribution_log.jsonl"
)
DAILY_REPORT_DIR = Path.home() / ".dharma" / "welfare" / "attribution"

# Outcome dimension sign convention. Positive sign = better welfare.
# E.g. carbon_kgco2e is REDUCTION (positive value = reduced emissions).
# If the certificate reports raw emissions (positive value = emitted),
# the integrator must flip sign before passing to us.
DIMENSION_SIGNS: dict[str, int] = {
    "carbon_kgco2e": +1,            # reduction
    "biodiversity_index": +1,        # increase
    "livelihood_usd": +1,            # household income gain
    "soil_health_index": +1,         # improvement
}


# ---------------------------------------------------------------------------
# Protocols (duck-typing)
# ---------------------------------------------------------------------------


@runtime_checkable
class CertificateLike(Protocol):
    certificate_id: str
    issued_at: str
    domain: str
    project_id: str
    project_code_paths: list[str]
    evidence: list[str]
    outcome: dict[str, float]


@runtime_checkable
class ProposalLike(Protocol):
    id: str
    component: str
    description: str
    affected_files: list[str]
    decision_at: str
    fitness_after_deployment: list[dict]
    jagat_kalyan_register_links: list[str]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class Attribution:
    proposal_id: str
    weight: float           # normalized share, sum==1.0 across attributions
    directness: float       # raw directness pre-normalization
    rationale: str
    delta_applied: float    # signed contribution to fitness_after_deployment
    components: dict[str, float] = field(default_factory=dict)  # heuristic breakdown


@dataclass
class AttributionRecord:
    certificate_id: str
    issued_at: str
    domain: str
    total_welfare_score: float          # composite, signed, in [-1, 1]
    raw_outcome: dict[str, float]
    attributions: list[Attribution] = field(default_factory=list)
    unattributed_delta: float = 0.0     # the residual we DON'T claim
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("total_welfare_score", "unattributed_delta"):
            v = d.get(k)
            if isinstance(v, float) and math.isnan(v):
                d[k] = None
        return d


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def attribute_certificate(
    certificate: CertificateLike,
    candidate_proposals: Iterable[ProposalLike],
    *,
    window_days: int = 90,
    attribution_floor: float = ATTRIBUTION_FLOOR,
    now: datetime | None = None,
) -> AttributionRecord:
    """Compute attribution of a welfare certificate across recent proposals.

    Parameters
    ----------
    certificate:
        Anything matching CertificateLike (duck-typed).
    candidate_proposals:
        Iterable of recent proposals to consider. Caller filters by date
        before passing in (we apply a soft re-filter via temporal_proximity).
    window_days:
        Soft cutoff for "recent." Decisions older than this contribute
        ~0 to temporal_proximity.
    attribution_floor:
        Minimum directness to include a proposal.
    now:
        Override for testing.

    Returns
    -------
    AttributionRecord
        Always returned; empty attributions on no-match. Never raises.
    """
    now = now or datetime.now(timezone.utc)

    cert_issued_at = _parse_ts(certificate.issued_at) or now
    cert_paths = list(getattr(certificate, "project_code_paths", []) or [])
    cert_evidence = list(getattr(certificate, "evidence", []) or [])
    cert_project_id = str(getattr(certificate, "project_id", ""))
    raw_outcome = dict(getattr(certificate, "outcome", {}) or {})

    # Pass 1: compute raw directness for each candidate
    raw: list[tuple[ProposalLike, float, dict[str, float], str]] = []
    for prop in candidate_proposals:
        decision_at = _parse_ts(prop.decision_at)
        if decision_at is None:
            continue
        # Soft window: drop if older than window_days * 2 (very stale)
        if (cert_issued_at - decision_at).days > window_days * 2:
            continue

        components = {
            "topical_overlap": _topical_overlap(
                getattr(prop, "affected_files", []) or [],
                cert_paths,
            ),
            "temporal_proximity": _temporal_proximity(
                decision_at, cert_issued_at,
            ),
            "register_link": _register_link(
                getattr(prop, "jagat_kalyan_register_links", []) or [],
                cert_project_id,
            ),
            "citation_in_cert": _citation_in_cert(prop.id, cert_evidence),
        }
        directness = (
            0.40 * components["topical_overlap"]
            + 0.30 * components["temporal_proximity"]
            + 0.20 * components["register_link"]
            + 0.10 * components["citation_in_cert"]
        )
        rationale = _format_rationale(components)
        raw.append((prop, directness, components, rationale))

    # Filter by floor
    above_floor = [r for r in raw if r[1] >= attribution_floor]

    # Compute total welfare score (composite, signed, normalized)
    total_welfare_score = _composite_welfare_score(raw_outcome)

    if not above_floor:
        notes: list[str] = []
        if not raw:
            notes.append("no proposals provided in window")
        else:
            notes.append(
                f"all {len(raw)} candidates below attribution_floor "
                f"({attribution_floor:.2f}); welfare unattributed"
            )
        return AttributionRecord(
            certificate_id=certificate.certificate_id,
            issued_at=certificate.issued_at,
            domain=getattr(certificate, "domain", "composite"),
            total_welfare_score=total_welfare_score,
            raw_outcome=raw_outcome,
            attributions=[],
            unattributed_delta=total_welfare_score,
            notes=notes,
        )

    # Normalize directness to weights summing to 1.0
    sum_d = sum(r[1] for r in above_floor)
    attributions: list[Attribution] = []
    if sum_d <= 0:
        # Defensive: shouldn't happen since each item is >= floor > 0
        attributions = []
        unattributed = total_welfare_score
    else:
        for prop, directness, components, rationale in above_floor:
            weight = directness / sum_d
            # Apply with delta clamp (Goodhart firewall)
            raw_delta = total_welfare_score * weight
            delta_clamped = max(-DELTA_CLAMP, min(DELTA_CLAMP, raw_delta))
            attributions.append(Attribution(
                proposal_id=prop.id,
                weight=round(weight, 4),
                directness=round(directness, 4),
                rationale=rationale,
                delta_applied=round(delta_clamped, 4),
                components={k: round(v, 4) for k, v in components.items()},
            ))
        # Residual after clamping AND any rounding
        attributed = sum(a.delta_applied for a in attributions)
        unattributed = total_welfare_score - attributed

    notes = []
    if abs(unattributed) > 0.01 and attributions:
        notes.append(
            "non-zero unattributed_delta — system NOT claiming sole credit"
        )

    return AttributionRecord(
        certificate_id=certificate.certificate_id,
        issued_at=certificate.issued_at,
        domain=getattr(certificate, "domain", "composite"),
        total_welfare_score=total_welfare_score,
        raw_outcome=raw_outcome,
        attributions=attributions,
        unattributed_delta=round(unattributed, 4),
        notes=notes,
    )


def apply_attribution_to_proposals(
    record: AttributionRecord,
    proposals_by_id: dict[str, ProposalLike],
) -> list[str]:
    """Mutate proposals' fitness_after_deployment list with this record.

    Returns a list of proposal_ids actually mutated (those present in the
    map). Proposals missing from the map are skipped silently — caller
    can detect by comparing record.attributions vs return value.

    Idempotency: pass the same record twice and you get duplicate entries.
    Callers should track which (certificate_id -> proposal_id) pairs they've
    already applied.
    """
    mutated: list[str] = []
    for attribution in record.attributions:
        prop = proposals_by_id.get(attribution.proposal_id)
        if prop is None:
            continue
        entry = {
            "certificate_id": record.certificate_id,
            "issued_at": record.issued_at,
            "domain": record.domain,
            "weight": attribution.weight,
            "directness": attribution.directness,
            "delta_applied": attribution.delta_applied,
            "rationale": attribution.rationale,
        }
        # The list is a Python attribute; in production the Proposal type
        # should be a Pydantic model and `fitness_after_deployment` is its
        # field. Calling code is responsible for serialization/persistence.
        existing = list(getattr(prop, "fitness_after_deployment", []) or [])
        existing.append(entry)
        setattr(prop, "fitness_after_deployment", existing)
        mutated.append(prop.id)
    return mutated


def persist_attribution(
    record: AttributionRecord,
    *,
    log_path: Path | None = None,
) -> bool:
    """Append record to ~/.dharma/welfare/attribution_log.jsonl.

    Best-effort. Returns True on success, False on IO error. Never raises.
    """
    log_path = log_path or ATTRIBUTION_LOG_PATH
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict()) + "\n")
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def _topical_overlap(
    decision_files: list[str],
    cert_paths: list[str],
) -> float:
    """Set-overlap of file paths. Uses path-prefix containment for
    project_code_paths that are directories."""
    if not decision_files or not cert_paths:
        return 0.0

    df = {f.lower().rstrip("/") for f in decision_files if f}
    cp = [p.lower().rstrip("/") for p in cert_paths if p]
    if not df or not cp:
        return 0.0

    matches = 0
    for f in df:
        for p in cp:
            # Either exact match or f is under p (p is a directory)
            if f == p or f.startswith(p + "/"):
                matches += 1
                break
    return min(1.0, matches / len(df))


def _temporal_proximity(decision_at: datetime, cert_at: datetime) -> float:
    """Exponential decay. score = exp(-days / tau).
    Score is 1.0 when same day, 0.5 at tau days, ~0.05 at 3*tau."""
    delta_days = abs((cert_at - decision_at).total_seconds()) / 86400.0
    return math.exp(-delta_days / TEMPORAL_PROXIMITY_TAU_DAYS)


def _register_link(
    register_links: list[str],
    cert_project_id: str,
) -> float:
    """1.0 iff the proposal explicitly registered this project_id as
    welfare-related, 0.0 otherwise. Bounded to prevent gaming: even
    full register_link with no other signals scores only 0.20 in the
    composite."""
    if not register_links or not cert_project_id:
        return 0.0
    # Match on project_id substring or exact equality
    cert_id_lower = cert_project_id.lower()
    for link in register_links:
        if not isinstance(link, str):
            continue
        if cert_id_lower == link.lower() or cert_id_lower in link.lower():
            return 1.0
    return 0.0


def _citation_in_cert(decision_id: str, cert_evidence: list[str]) -> float:
    """1.0 iff the certificate's evidence list cites this decision_id.
    Strongest possible signal: the verifier ON THE GROUND points at the
    decision."""
    if not decision_id or not cert_evidence:
        return 0.0
    decision_lower = decision_id.lower()
    for e in cert_evidence:
        if not isinstance(e, str):
            continue
        if decision_lower == e.lower() or decision_lower in e.lower():
            return 1.0
    return 0.0


def _composite_welfare_score(outcome: dict[str, float]) -> float:
    """Compose dimension outcomes into a single signed score in [-1, 1].

    For each known dimension: normalize via tanh on a typical scale,
    apply sign convention, average. Unknown dimensions are skipped.
    """
    if not outcome:
        return 0.0

    # Per-dimension normalization scales (heuristic; tunable)
    scales = {
        "carbon_kgco2e": 1000.0,        # 1000 kgco2e ≈ tanh(1) ≈ 0.76
        "biodiversity_index": 0.20,      # 0.20 unit ≈ moderate signal
        "livelihood_usd": 5000.0,        # 5000 USD per cert ≈ moderate
        "soil_health_index": 0.20,
    }

    contributions: list[float] = []
    for key, val in outcome.items():
        if key not in DIMENSION_SIGNS:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        scale = scales.get(key, 1.0)
        signed = DIMENSION_SIGNS[key] * v
        contributions.append(math.tanh(signed / max(scale, 1e-9)))

    if not contributions:
        return 0.0
    return sum(contributions) / len(contributions)


def _format_rationale(components: dict[str, float]) -> str:
    """Short human-readable explanation of attribution score components."""
    parts = []
    for k in ("topical_overlap", "temporal_proximity",
              "register_link", "citation_in_cert"):
        v = components.get(k, 0.0)
        if v > 0.01:
            parts.append(f"{k}={v:.2f}")
    return ", ".join(parts) if parts else "no components above zero"


__all__ = [
    "ATTRIBUTION_FLOOR",
    "DELTA_CLAMP",
    "Attribution",
    "AttributionRecord",
    "CertificateLike",
    "ProposalLike",
    "attribute_certificate",
    "apply_attribution_to_proposals",
    "persist_attribution",
]
