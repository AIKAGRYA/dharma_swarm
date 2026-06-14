"""promote_gate.py — recommend-only version promotion gate.

Reads two per-version metrics files (produced by version_metrics_rollup.py) and
emits a PROMOTE_CANDIDATE / HOLD / REJECT verdict from VERIFIED metrics only.

This gate PROPOSES; the operator COMMITS. It never:
  - calls EvolutionArchive.add_entry or mutates fitness,
  - switches the daemon or edits the launchd plist,
  - opens a new authority surface.

`request_promotion()` writes a PENDING_APPROVAL.json the operator must approve
via a separate gated script (H4) — two-key promotion.

Fail-closed rule (priority order):
  1. REJECT  if circuit_breaker_trips > 0, OR rollback_rate > 0.20,
             OR any applied entry had a gate BLOCK (gate_allow_rate < 1.0
             AND a gate-block was recorded), OR merkle chain fails.
  2. HOLD    (never auto-promote, never REJECT on thin data) if
             n_verified < N_MIN, OR soak_hours < SOAK_MIN, OR no incumbent.
  3. REJECT  if candidate is verifiably WORSE (CI-accounted) on correctness
             or receipt_ok_rate.
  4. PROMOTE_CANDIDATE if all verified metrics >= incumbent within margin AND
             cost ceiling AND gate_allow_rate >= 0.80 AND receipt_ok_rate >=
             0.85 AND soak met.
  5. Otherwise HOLD.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

N_MIN = 50          # minimum verified entries before a verdict can be conclusive
SOAK_MIN_HOURS = 12.0
ROLLBACK_CEIL = 0.20
COST_MULT_CEIL = 1.25
GATE_ALLOW_FLOOR = 0.80
RECEIPT_OK_FLOOR = 0.85
CI_MARGIN = 0.02    # tolerance band for "within margin" comparisons


@dataclass
class Verdict:
    decision: str               # PROMOTE_CANDIDATE | HOLD | REJECT
    reasons: list[str] = field(default_factory=list)
    candidate_build_id: str = ""
    incumbent_build_id: str = ""
    ready_for_promotion: bool = False
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _vm(metrics: dict[str, Any]) -> dict[str, Any]:
    return metrics.get("verified_metrics", {}) or {}


def _n(metrics: dict[str, Any]) -> int:
    return int((metrics.get("window", {}) or {}).get("n_entries", 0) or 0)


def _soak(metrics: dict[str, Any]) -> float:
    return float((metrics.get("window", {}) or {}).get("soak_hours", 0.0) or 0.0)


def _ci95_margin(rate: float, n: int) -> float:
    """Wald 95% half-width for a proportion; floored by CI_MARGIN to stay
    conservative on small or extreme samples."""
    if n <= 0:
        return 1.0
    p = min(max(rate, 0.0), 1.0)
    half = 1.96 * math.sqrt(max(p * (1.0 - p), 1e-9) / n)
    return max(half, CI_MARGIN)


def evaluate(candidate: dict[str, Any], incumbent: dict[str, Any] | None) -> Verdict:
    """Pure decision function over two rollup dicts. No I/O."""
    cb = candidate.get("build_id", "candidate")
    ib = incumbent.get("build_id", "incumbent") if incumbent else ""
    v = Verdict(decision="HOLD", candidate_build_id=cb, incumbent_build_id=ib)
    cm = _vm(candidate)

    # --- Clause 1: safety / tamper dominates (fail-closed) ---
    if int(candidate.get("circuit_breaker_trips", 0) or 0) > 0:
        v.decision = "REJECT"
        v.reasons.append("circuit_breaker_trips > 0")
        return v
    if float(cm.get("rollback_rate", 0.0) or 0.0) > ROLLBACK_CEIL:
        v.decision = "REJECT"
        v.reasons.append(f"rollback_rate {cm.get('rollback_rate')} > {ROLLBACK_CEIL}")
        return v
    if not bool(candidate.get("merkle_ok", True)):
        v.decision = "REJECT"
        v.reasons.append("merkle chain verification failed")
        return v
    # A gate BLOCK on any applied entry shows up as gate_allow_rate < 1.0 with a
    # recorded block flag. We treat an explicit block flag as a hard reject.
    if bool(candidate.get("had_gate_block", False)):
        v.decision = "REJECT"
        v.reasons.append("an applied entry had a telos gate BLOCK")
        return v

    # --- Clause 2: thin data / no baseline -> HOLD (inconclusive != failed) ---
    if _n(candidate) < N_MIN:
        v.reasons.append(f"n={_n(candidate)} < N_MIN({N_MIN}) -> inconclusive")
        return v
    if _soak(candidate) < SOAK_MIN_HOURS:
        v.reasons.append(f"soak_hours={_soak(candidate)} < {SOAK_MIN_HOURS} -> inconclusive")
        return v
    if incumbent is None:
        v.reasons.append("no incumbent baseline -> HOLD (first observation)")
        return v

    im = _vm(incumbent)
    n_c, n_i = _n(candidate), _n(incumbent)

    # --- Clause 3: verifiably worse (CI-accounted) -> REJECT ---
    corr_margin = _ci95_margin(float(cm.get("correctness_mean", 0.0) or 0.0), n_c)
    if float(cm.get("correctness_mean", 0.0)) + corr_margin < float(im.get("correctness_mean", 0.0)):
        v.decision = "REJECT"
        v.reasons.append("correctness verifiably worse than incumbent (CI-accounted)")
        return v
    ok_margin = _ci95_margin(float(cm.get("receipt_ok_rate", 0.0) or 0.0), n_c)
    if float(cm.get("receipt_ok_rate", 0.0)) + ok_margin < float(im.get("receipt_ok_rate", 0.0)):
        v.decision = "REJECT"
        v.reasons.append("receipt_ok_rate verifiably worse than incumbent (CI-accounted)")
        return v

    # --- Clause 4: all verified metrics >= incumbent within margin + ceilings ---
    corr_ok = float(cm.get("correctness_mean", 0.0)) + CI_MARGIN >= float(im.get("correctness_mean", 0.0))
    okrate_ok = float(cm.get("receipt_ok_rate", 0.0)) + CI_MARGIN >= float(im.get("receipt_ok_rate", 0.0))
    gate_ok = float(cm.get("gate_allow_rate", 0.0)) >= GATE_ALLOW_FLOOR
    receipt_floor_ok = float(cm.get("receipt_ok_rate", 0.0)) >= RECEIPT_OK_FLOOR

    inc_cost = float(im.get("cost_usd_per_applied", 0.0) or 0.0)
    cand_cost = float(cm.get("cost_usd_per_applied", 0.0) or 0.0)
    cost_observed = bool(cm.get("cost_observed", False))
    if not cost_observed or inc_cost <= 0.0:
        # Free models report cost_usd=0: cost ceiling degrades to non-gating;
        # latency/success carry the weight. Record the caveat, do not block.
        cost_ok = True
        v.reasons.append("cost not observed (free models?) -> cost ceiling non-gating")
    else:
        cost_ok = cand_cost <= inc_cost * COST_MULT_CEIL

    if corr_ok and okrate_ok and gate_ok and receipt_floor_ok and cost_ok:
        v.decision = "PROMOTE_CANDIDATE"
        v.ready_for_promotion = True
        v.reasons.append("all verified metrics >= incumbent within margin; ceilings met")
        return v

    # --- Clause 5: otherwise HOLD ---
    if not gate_ok:
        v.reasons.append(f"gate_allow_rate {cm.get('gate_allow_rate')} < {GATE_ALLOW_FLOOR}")
    if not receipt_floor_ok:
        v.reasons.append(f"receipt_ok_rate {cm.get('receipt_ok_rate')} < {RECEIPT_OK_FLOOR}")
    if not corr_ok:
        v.reasons.append("correctness not yet >= incumbent")
    return v


class VersionPromotionGate:
    """Filesystem-facing wrapper. Read-and-recommend only."""

    def __init__(self, version_metrics_dir: Path):
        self.dir = Path(version_metrics_dir)

    def _load(self, build_id: str) -> dict[str, Any]:
        path = self.dir / f"{build_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def compare(self, candidate_build_id: str, incumbent_build_id: str | None) -> Verdict:
        candidate = self._load(candidate_build_id)
        incumbent = self._load(incumbent_build_id) if incumbent_build_id else None
        return evaluate(candidate, incumbent)

    def write_soak_report(self, verdict: Verdict, out_dir: Path | None = None) -> Path:
        out_dir = Path(out_dir) if out_dir else (self.dir / "reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"SOAK_{verdict.candidate_build_id}.json"
        path.write_text(json.dumps(verdict.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path

    def request_promotion(self, verdict: Verdict, out_dir: Path | None = None) -> Path:
        """Write PENDING_APPROVAL.json — proposes only. Operator key (H4)
        performs the actual launchd swap. Never auto-flips a daemon."""
        if not verdict.ready_for_promotion:
            raise ValueError(
                f"refusing to request promotion: verdict={verdict.decision} "
                "(only PROMOTE_CANDIDATE may be requested)"
            )
        out_dir = Path(out_dir) if out_dir else self.dir
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "PENDING_APPROVAL.json"
        payload = verdict.to_dict()
        payload["requires_operator_approval"] = True
        payload["approval_command"] = (
            "python3 scripts/governance/promote_daemon_version.py "
            f"--approve {verdict.candidate_build_id}"
        )
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path
