"""Organism Closure v0 — file-native proof loop.

Proves: EvidenceReceipt(success=True) yields a different NextDecision than
EvidenceReceipt(success=False). Scope locked by Track 3 plan, 2026-05-08:
file-native dataclasses, JSON I/O only, imports stdlib + operating_facts,
correlation_id mandatory, DarwinProposalCandidate is data only (never
submitted to evolution.py), module-private (no public re-export).
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from dharma_swarm.operator_core.operating_facts import (
    AgentOpsRunFact,
    HumanQualityRatingFact,
    OperatingFactBundle,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "organism_closure_v0"
_REVIEW_TIERS = {"auto", "review", "human"}

class EvidenceInconsistentError(ValueError): ...
class ClosureContractError(ValueError): ...

@dataclass(frozen=True)
class TelosObjective:
    objective_id: str = "jagat_kalyan"
    name: str = "Jagat Kalyan"
    perspective: str = "purpose"

@dataclass(frozen=True)
class VentureCellRef:
    cell_id: str = ""
    name: str = ""

@dataclass(frozen=True)
class WorkPacket:
    packet_id: str
    correlation_id: str
    title: str
    allowed_paths: tuple[str, ...]
    acceptance_test: str
    rollback_plan: str
    objective_id: str = "jagat_kalyan"
    cell_id: str = ""
    forbidden_paths: tuple[str, ...] = ()
    review_tier: str = "review"

    def __post_init__(self) -> None:
        if not (self.correlation_id and self.allowed_paths and self.acceptance_test and self.rollback_plan):
            raise ClosureContractError("WorkPacket missing required field")
        if set(self.allowed_paths) & set(self.forbidden_paths):
            raise ClosureContractError("WorkPacket allowed/forbidden path overlap")
        if self.review_tier not in _REVIEW_TIERS:
            raise ClosureContractError(f"WorkPacket.review_tier ∉ {_REVIEW_TIERS}")

@dataclass(frozen=True)
class EvidenceReceipt:
    receipt_id: str
    correlation_id: str
    work_packet_id: str
    agentops_source: str
    test_exit_code: int
    files_changed: tuple[tuple[str, str], ...]
    duration_ms: float
    replay_command: str
    success: bool
    created_at: str

    def __post_init__(self) -> None:
        if not (self.correlation_id and self.replay_command):
            raise ClosureContractError("EvidenceReceipt missing correlation_id/replay_command")
        if self.success != (self.test_exit_code == 0):
            raise EvidenceInconsistentError(f"success={self.success} but exit={self.test_exit_code}")

@dataclass(frozen=True)
class VSMProjection:
    projection_id: str
    correlation_id: str
    captured_at: str
    s1_open_packets: int
    s1_failed_24h: int
    s1_success_24h: int
    s2_collisions_24h: int
    s3_packets_blocked_24h: int
    s4_recognition_seed_age_hours: float
    s4_algedonic_unique_values_last_200: int
    s5_kernel_signature_match: bool
    truth_stale: bool

    def __post_init__(self) -> None:
        if not self.correlation_id:
            raise ClosureContractError("VSMProjection.correlation_id required")

@dataclass(frozen=True)
class KaizenReviewLink:
    review_id: str
    correlation_id: str
    evidence_receipt_id: str
    next_recommendation: str
    waste_patterns: tuple[str, ...] = ()
    has_human_yds: bool = False

    def __post_init__(self) -> None:
        if not self.correlation_id or not self.next_recommendation:
            raise ClosureContractError("KaizenReviewLink correlation_id/next_recommendation required")

@dataclass(frozen=True)
class DarwinProposalCandidate:
    candidate_id: str
    correlation_id: str
    component: str
    description: str
    evidence_refs: tuple[str, ...] = ()
    kaizen_review_refs: tuple[str, ...] = ()

@dataclass(frozen=True)
class NextDecision:
    decision_id: str
    correlation_id: str
    decided_at: str
    decided_by: str
    input_refs: tuple[str, ...]
    candidate_packet_ids: tuple[str, ...]
    chosen_packet_id: str | None
    reason: str
    confidence: float
    expires_at: str

def _hid(prefix: str, *parts: str) -> str:
    digest = hashlib.blake2s("|".join(parts).encode("utf-8"), digest_size=6).hexdigest()
    return f"{prefix}_{digest}"

def _success_from_agentops(fact: AgentOpsRunFact) -> bool:
    return fact.gate_state == "all_green" and fact.scope_state == "scope_clean"

def record_evidence_receipt(
    packet: WorkPacket,
    agentops_fact: AgentOpsRunFact,
    *,
    correlation_id: str,
    created_at: str,
    duration_ms: float = 0.0,
) -> EvidenceReceipt:
    success = _success_from_agentops(agentops_fact)
    return EvidenceReceipt(
        receipt_id=_hid("ev", correlation_id, packet.packet_id, str(success)),
        correlation_id=correlation_id,
        work_packet_id=packet.packet_id,
        agentops_source=agentops_fact.source_path,
        test_exit_code=0 if success else 1,
        files_changed=tuple(
            (p, _hid("blob", p, packet.packet_id)[5:]) for p in agentops_fact.changed_files
        ),
        duration_ms=duration_ms,
        replay_command=f"pytest {packet.acceptance_test} -q",
        success=success,
        created_at=created_at,
    )

def project_vsm(
    bundle: OperatingFactBundle,
    receipt: EvidenceReceipt | None,
    *,
    correlation_id: str,
    captured_at: str,
    recognition_seed_age_hours: float,
    algedonic_unique_values_last_200: int,
    kernel_signature_match: bool,
    open_packets: int = 0,
    collisions_24h: int = 0,
    packets_blocked_24h: int = 0,
    truth_stale_threshold_hours: float = 24.0,
) -> VSMProjection:
    success_24h = sum(1 for r in bundle.agentops if r.gate_state == "all_green") + (
        1 if receipt and receipt.success else 0
    )
    failed_24h = sum(1 for r in bundle.agentops if r.gate_state == "some_red") + (
        1 if receipt and not receipt.success else 0
    )
    truth_stale = (
        recognition_seed_age_hours > truth_stale_threshold_hours
        or algedonic_unique_values_last_200 < 2
        or not kernel_signature_match
    )
    return VSMProjection(
        projection_id=_hid("vsm", correlation_id, captured_at),
        correlation_id=correlation_id,
        captured_at=captured_at,
        s1_open_packets=open_packets,
        s1_failed_24h=failed_24h,
        s1_success_24h=success_24h,
        s2_collisions_24h=collisions_24h,
        s3_packets_blocked_24h=packets_blocked_24h,
        s4_recognition_seed_age_hours=recognition_seed_age_hours,
        s4_algedonic_unique_values_last_200=algedonic_unique_values_last_200,
        s5_kernel_signature_match=kernel_signature_match,
        truth_stale=truth_stale,
    )

def kaizen_link(
    receipt: EvidenceReceipt,
    *,
    human_yds: HumanQualityRatingFact | None = None,
    waste_patterns: tuple[str, ...] = (),
) -> KaizenReviewLink:
    rec = (
        "Promote pattern; queue follow-up packet to extend coverage."
        if receipt.success
        else "Hold packet; narrow allowed_paths and rerun acceptance_test before proposing a successor."
    )
    return KaizenReviewLink(
        review_id=_hid("kz", receipt.correlation_id, receipt.receipt_id),
        correlation_id=receipt.correlation_id,
        evidence_receipt_id=receipt.receipt_id,
        next_recommendation=rec,
        waste_patterns=waste_patterns,
        has_human_yds=human_yds is not None,
    )

def decide_next(
    projection: VSMProjection,
    candidates: list[WorkPacket],
    review: KaizenReviewLink,
    *,
    decided_at: str,
    expires_at: str,
    decided_by: str = "policy",
) -> NextDecision:
    cids = tuple(p.packet_id for p in candidates)
    accepted = "Promote" in review.next_recommendation
    if projection.truth_stale:
        chosen, reason, conf = None, "truth_stale: S4/algedonic/S5 integrity flagged", 0.0
    elif accepted and cids:
        chosen, reason, conf = cids[0], "evidence_accepted: KaizenReview promotes pattern", 0.7
    elif not accepted:
        chosen, reason, conf = None, "evidence_failed: KaizenReview recommends hold-and-narrow", 0.2
    else:
        chosen, reason, conf = None, "no_candidates", 0.0
    return NextDecision(
        decision_id=_hid("nd", projection.correlation_id, decided_at),
        correlation_id=projection.correlation_id,
        decided_at=decided_at,
        decided_by=decided_by,
        input_refs=(projection.projection_id, review.review_id, review.evidence_receipt_id),
        candidate_packet_ids=cids,
        chosen_packet_id=chosen,
        reason=reason,
        confidence=conf,
        expires_at=expires_at,
    )

def validate_darwin_candidate(c: DarwinProposalCandidate) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if not c.evidence_refs:
        failures.append("evidence_missing")
    if not c.kaizen_review_refs:
        failures.append("kaizen_review_missing")
    if not c.correlation_id:
        failures.append("correlation_id_missing")
    return (not failures, failures)

def to_jsonable(obj: object) -> object:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, (tuple, list)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    return obj

def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(to_jsonable(payload), indent=2, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as h:
            h.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def load_fixture(name: str, *, root: Path | None = None) -> dict:
    return read_json((root or FIXTURE_ROOT) / name)
