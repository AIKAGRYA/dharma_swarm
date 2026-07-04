"""Canonical operating facts and organ boundary contracts.

This module is the membrane between Dharma Swarm's operational organs.  Each
organ keeps its private implementation, but exposes small immutable facts that
operator-facing synthesis can consume without depending on internal mechanics.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.operator_core.runtime_truth_refs import runtime_ref_values
from dharma_swarm.operator_core.telic_value_reader import read_telic_value_summary


HUMAN_YDS_SOURCES = {"human", "operator", "dhyana"}
YDS_RE = re.compile(r"^5\.(?:6|7|8|9|10|11|12|13|14|15)(?:[abcd])?$")
REVENUE_KEYWORDS = (
    "revenue",
    "wedge",
    "grant",
    "customer",
    "stripe",
    "gumroad",
    "mrr",
    "arr",
    "runway",
    "sell",
    "pricing",
)
COHERENCE_STATES = ("bound", "partial", "declared_only", "drifted", "unknown")


@dataclass(frozen=True)
class OrganBoundary:
    """A membrane contract for one subsystem/organ."""

    name: str
    owns: str
    emits: tuple[str, ...]
    may_read: tuple[str, ...] = ()
    must_not_mutate: tuple[str, ...] = ()
    python_api: str = ""
    rust_readiness: str = "keep_python"
    notes: str = ""


@dataclass(frozen=True)
class OrganStateFact:
    """Read-only declared-vs-observed projection for one operational organ."""

    name: str
    owns: str
    declared_state: str
    observed_state: str
    coherence_state: str
    evidence_refs: tuple[str, ...] = ()
    open_gap: str = ""
    next_packet_hint: str = ""
    declared_primitive: str = ""
    actual_runtime_primitive: str = ""
    source_stores: tuple[str, ...] = ()
    sink_stores: tuple[str, ...] = ()
    gates_declared: tuple[str, ...] = ()
    gates_enforced: tuple[str, ...] = ()
    witness_writes: tuple[str, ...] = ()
    scheduled: str = "UNKNOWN"
    merged_to_main: str = "UNKNOWN"
    last_observed: str = ""
    drift: str = ""
    next_bindable_gap: str = ""
    risk: str = "UNKNOWN"


ORGAN_BOUNDARIES: tuple[OrganBoundary, ...] = (
    OrganBoundary(
        name="agentops",
        owns="bounded repo execution facts",
        emits=("AgentOpsRunFact",),
        must_not_mutate=("human_yds", "daily_operating_brief", "kaizen_review"),
        python_api="scripts/governance/run_agent_work_packet.py report.json",
        rust_readiness="candidate_later",
        notes="Scope/diff validation may become Rust after the packet schema is stable.",
    ),
    OrganBoundary(
        name="kaizen_review",
        owns="continuous-improvement evidence from completed AgentOps runs",
        emits=("KaizenReviewFact",),
        may_read=("agentops", "human_yds"),
        must_not_mutate=("agentops", "human_yds", "daily_operating_brief"),
        python_api="scripts/governance/kaizen_review_from_agentops.py",
        rust_readiness="keep_python",
    ),
    OrganBoundary(
        name="human_yds",
        owns="human-authoritative quality judgment",
        emits=("HumanQualityRatingFact",),
        must_not_mutate=("agentops", "kaizen_review", "daily_operating_brief"),
        python_api="append_human_yds_rating() / load_human_yds_rating_facts()",
        rust_readiness="candidate_later",
        notes="Ledger integrity may become Rust; rating semantics stay human/Python.",
    ),
    OrganBoundary(
        name="burn_cost",
        owns="resource-spend and waste signals",
        emits=("BurnReportFact",),
        must_not_mutate=("agentops", "human_yds", "telic_value"),
        python_api="load_burn_report_facts()",
        rust_readiness="candidate_later",
        notes="High-volume trace compaction is a good future Rust substrate.",
    ),
    OrganBoundary(
        name="revenue",
        owns="self-funding and product wedge signals",
        emits=("RevenueSignalFact",),
        must_not_mutate=("human_yds", "agentops", "telic_value"),
        python_api="load_revenue_signal_facts()",
        rust_readiness="keep_python",
    ),
    OrganBoundary(
        name="daily_operating_brief",
        owns="human-facing synthesis of operating facts",
        emits=("DailyOperatingBrief",),
        may_read=("agentops", "kaizen_review", "human_yds", "burn_cost", "revenue"),
        must_not_mutate=("agentops", "kaizen_review", "human_yds", "telic_value"),
        python_api="dharma_swarm.daily_operating_brief",
        rust_readiness="keep_python",
    ),
    OrganBoundary(
        name="command_spine",
        owns="dry-run operator planning and next-packet recommendation",
        emits=("WorkPacketDraft", "AgentOpsReview", "RustReadinessDecision"),
        may_read=("agentops", "human_yds", "mission_contract", "intent_router"),
        must_not_mutate=("agentops", "daily_operating_brief", "telic_value"),
        python_api="dharma_swarm.operator_core.command_spine",
        rust_readiness="keep_python",
    ),
    OrganBoundary(
        name="telic_value",
        owns="Outcome, ValueEvent, and Contribution truth",
        emits=("Outcome", "ValueEvent", "Contribution"),
        must_not_mutate=("agentops", "human_yds", "daily_operating_brief"),
        python_api="dharma_swarm.telic_seam",
        rust_readiness="keep_python",
    ),
)


@dataclass(frozen=True)
class GateFact:
    name: str
    passed: bool | None
    exit_code: int | None = None


@dataclass(frozen=True)
class AgentOpsRunFact:
    source_path: str
    job_id: str
    status: str
    branch: str
    worktree: str
    gate_state: str
    scope_state: str
    commit_state: str
    approval_state: str
    changed_files: tuple[str, ...] = ()
    scope_violations: tuple[str, ...] = ()
    failed_gates: tuple[str, ...] = ()
    commit_hash: str | None = None
    runtime_truth_ref_keys: tuple[str, ...] = ()
    runtime_truth_jobs_with_refs: int = 0
    runtime_truth_jobs_without_refs: int = 0
    receipt_refs: tuple[str, ...] = ()
    correlation_ids: tuple[str, ...] = ()
    identity_invariant_digests: tuple[str, ...] = ()


@dataclass(frozen=True)
class KaizenReviewFact:
    source_path: str
    jobs_reviewed: int
    next_recommendation: str
    waste_patterns: tuple[str, ...] = ()
    stop_doing_items: tuple[str, ...] = ()
    playbook_update_candidates: tuple[str, ...] = ()
    runtime_truth_ref_keys: tuple[str, ...] = ()
    runtime_truth_jobs_with_refs: int = 0
    runtime_truth_jobs_without_refs: int = 0
    receipt_refs: tuple[str, ...] = ()
    correlation_ids: tuple[str, ...] = ()
    identity_invariant_digests: tuple[str, ...] = ()
    has_human_yds_rating: bool = False


@dataclass(frozen=True)
class HumanQualityRatingFact:
    source_path: str
    artifact_uri: str
    rating: str
    source: str
    human_note: str = ""
    created_at: str = ""
    authoritative: bool = False
    title: str = ""


@dataclass(frozen=True)
class BurnReportFact:
    source_path: str
    label: str
    total_cost_usd: float | None = None
    total_tokens: int | None = None
    unpriced_span_count: int = 0
    raw_count: int = 0


@dataclass(frozen=True)
class RevenueSignalFact:
    source_path: str
    line: str
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class OperatingFactInputs:
    agentops_reports_dir: Path | None = None
    kaizen_reports_dir: Path | None = None
    yds_ratings_path: Path | None = None
    burn_report_path: Path | None = None
    revenue_notes_path: Path | None = None


@dataclass(frozen=True)
class OperatingFactBundle:
    agentops: tuple[AgentOpsRunFact, ...] = ()
    kaizen: tuple[KaizenReviewFact, ...] = ()
    human_yds: tuple[HumanQualityRatingFact, ...] = ()
    burn: tuple[BurnReportFact, ...] = ()
    revenue: tuple[RevenueSignalFact, ...] = ()
    missing_sources: tuple[str, ...] = ()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def organ_boundary_map() -> dict[str, OrganBoundary]:
    return {boundary.name: boundary for boundary in ORGAN_BOUNDARIES}


def rust_membrane_candidates() -> tuple[OrganBoundary, ...]:
    return tuple(
        boundary
        for boundary in ORGAN_BOUNDARIES
        if boundary.rust_readiness == "candidate_later"
    )


def build_operating_fact_bundle(inputs: OperatingFactInputs) -> OperatingFactBundle:
    missing: list[str] = []
    agentops = load_agentops_run_facts(inputs.agentops_reports_dir)
    if inputs.agentops_reports_dir is None or not agentops:
        missing.append("AgentOps reports")
    kaizen = load_kaizen_review_facts(inputs.kaizen_reports_dir)
    if inputs.kaizen_reports_dir is None or not kaizen:
        missing.append("KaizenReview reports")
    human_yds = load_human_yds_rating_facts(inputs.yds_ratings_path)
    if inputs.yds_ratings_path is None or not human_yds:
        missing.append("Human YDS ledger")
    burn = load_burn_report_facts(inputs.burn_report_path)
    if inputs.burn_report_path is None or not burn:
        missing.append("Burn/cost report")
    revenue = load_revenue_signal_facts(inputs.revenue_notes_path)
    if inputs.revenue_notes_path is None or not revenue:
        missing.append("Revenue notes")
    return OperatingFactBundle(
        agentops=tuple(agentops),
        kaizen=tuple(kaizen),
        human_yds=tuple(human_yds),
        burn=tuple(burn),
        revenue=tuple(revenue),
        missing_sources=tuple(missing),
    )


def load_agentops_run_facts(path: Path | None) -> list[AgentOpsRunFact]:
    facts: list[AgentOpsRunFact] = []
    for report_path, report in _json_reports(path, "report.json"):
        facts.append(_agentops_fact(report_path, report))
    return facts


def load_kaizen_review_facts(path: Path | None) -> list[KaizenReviewFact]:
    facts: list[KaizenReviewFact] = []
    for report_path, report in _json_reports(path, "kaizen_review.json"):
        runtime_summary = report.get("runtime_truth_summary")
        if not isinstance(runtime_summary, dict):
            runtime_summary = {}
        facts.append(
            KaizenReviewFact(
                source_path=report_path.as_posix(),
                jobs_reviewed=_int(report.get("jobs_reviewed")),
                next_recommendation=_string(report.get("next_work_packet_recommendation")),
                waste_patterns=_strings(report.get("waste_patterns")),
                stop_doing_items=_strings(report.get("stop_doing_items")),
                playbook_update_candidates=_strings(report.get("playbook_update_candidates")),
                runtime_truth_ref_keys=_strings(runtime_summary.get("ref_keys")),
                runtime_truth_jobs_with_refs=_int(runtime_summary.get("jobs_with_refs")),
                runtime_truth_jobs_without_refs=_int(runtime_summary.get("jobs_without_refs")),
                receipt_refs=runtime_ref_values(
                    report, ("receipt_id", "receipt_hash", "receipt_refs", "runtime_receipt_refs")
                ),
                correlation_ids=runtime_ref_values(report, ("run_id", "trace_id", "correlation_id")),
                identity_invariant_digests=runtime_ref_values(report, ("identity_invariant_digest",)),
                has_human_yds_rating=bool(report.get("human_yds_rating")),
            )
        )
    return facts


def load_human_yds_rating_facts(path: Path | None) -> list[HumanQualityRatingFact]:
    records = _load_records(path)
    if not records:
        return []
    facts: list[HumanQualityRatingFact] = []
    source_path = Path(path).expanduser().as_posix() if path is not None else ""
    for record in records:
        fact = _yds_fact(source_path, record)
        if fact is not None:
            facts.append(fact)
    return facts


def load_burn_report_facts(path: Path | None) -> list[BurnReportFact]:
    records = _load_records(path)
    if records is None:
        return []
    source_path = Path(path).expanduser().as_posix() if path is not None else ""
    if not records:
        return []
    return [_burn_fact(source_path, records)]


def load_revenue_signal_facts(path: Path | None) -> list[RevenueSignalFact]:
    if path is None:
        return []
    resolved = path.expanduser()
    if not resolved.exists():
        return []
    lines = resolved.read_text(encoding="utf-8").splitlines()
    facts: list[RevenueSignalFact] = []
    for line in lines:
        text = line.strip()
        lowered = text.lower()
        hits = tuple(keyword for keyword in REVENUE_KEYWORDS if keyword in lowered)
        if text and hits:
            facts.append(
                RevenueSignalFact(
                    source_path=resolved.as_posix(),
                    line=text,
                    keywords=hits,
                )
            )
    return facts


def append_human_yds_rating(
    ledger_path: Path,
    *,
    artifact_uri: str,
    rating: str,
    human_note: str,
    operator_id: str = "dhyana",
    artifact_kind: str = "operator_artifact",
    title: str = "",
    evidence_refs: Iterable[str] = (),
    created_at: str | None = None,
) -> HumanQualityRatingFact:
    """Append one human-authoritative YDS rating to a JSONL ledger."""

    clean_rating = rating.strip()
    if not YDS_RE.fullmatch(clean_rating):
        raise ValueError("rating must be a YDS value from 5.6 through 5.15")
    clean_uri = artifact_uri.strip()
    if not clean_uri:
        raise ValueError("artifact_uri must not be empty")
    clean_note = human_note.strip()
    if not clean_note:
        raise ValueError("human_note must not be empty")
    source = operator_id.strip().lower() or "dhyana"
    if source not in HUMAN_YDS_SOURCES:
        raise ValueError("operator_id must identify human/operator/dhyana")

    created = created_at or utc_now_iso()
    record_seed = {
        "created_at": created,
        "artifact_uri": clean_uri,
        "rating": clean_rating,
        "operator_id": source,
        "human_note": clean_note,
    }
    rating_id = "yds_" + hashlib.blake2s(
        json.dumps(record_seed, sort_keys=True).encode("utf-8"),
        digest_size=6,
    ).hexdigest()
    record = {
        "schema_version": "human_yds_rating.v1",
        "rating_id": rating_id,
        "created_at": created,
        "operator_id": source,
        "rating_scale": "YDS",
        "rating_value": clean_rating,
        "artifact": {
            "kind": artifact_kind,
            "uri": clean_uri,
            "title": title.strip(),
        },
        "human_note": clean_note,
        "evidence_refs": sorted({str(ref).strip() for ref in evidence_refs if str(ref).strip()}),
        "context": {"source": "operator_cli"},
    }
    resolved = ledger_path.expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
    return _yds_fact(resolved.as_posix(), record)  # type: ignore[return-value]


def fact_to_dict(fact: Any) -> dict[str, Any]:
    return asdict(fact)


def bundle_to_dict(bundle: OperatingFactBundle) -> dict[str, Any]:
    return {
        "agentops": [fact_to_dict(fact) for fact in bundle.agentops],
        "kaizen": [fact_to_dict(fact) for fact in bundle.kaizen],
        "human_yds": [fact_to_dict(fact) for fact in bundle.human_yds],
        "burn": [fact_to_dict(fact) for fact in bundle.burn],
        "revenue": [fact_to_dict(fact) for fact in bundle.revenue],
        "organ_states": [fact_to_dict(fact) for fact in organ_state_facts(bundle)],
        "missing_sources": list(bundle.missing_sources),
    }


def organ_state_facts(bundle: OperatingFactBundle | None = None) -> tuple[OrganStateFact, ...]:
    """Project organ coherence from the current operating fact bundle.

    The projection is advisory. It reads already-exposed facts and does not
    create runtime authority, mutate ontology, schedule work, or classify PRs.
    """

    active_bundle = bundle or OperatingFactBundle()
    return tuple(_organ_state_fact(boundary, active_bundle) for boundary in ORGAN_BOUNDARIES)


def coherence_map_to_dict(bundle: OperatingFactBundle | None = None) -> dict[str, Any]:
    active_bundle = bundle or OperatingFactBundle()
    return {
        "organ_states": [fact_to_dict(fact) for fact in organ_state_facts(active_bundle)],
        "missing_sources": list(active_bundle.missing_sources),
    }


def _agentops_fact(path: Path, report: dict[str, Any]) -> AgentOpsRunFact:
    runtime_summary = report.get("runtime_truth_summary")
    if not isinstance(runtime_summary, dict):
        runtime_summary = {}
    gates = report.get("gates") if isinstance(report.get("gates"), list) else []
    gate_facts = [_gate_fact(gate, index) for index, gate in enumerate(gates)]
    failed_gates = tuple(gate.name for gate in gate_facts if gate.passed is False)
    unknown_gates = [gate for gate in gate_facts if gate.passed is None]
    if failed_gates:
        gate_state = "some_red"
    elif gate_facts and not unknown_gates:
        gate_state = "all_green"
    else:
        gate_state = "unknown"

    scope = report.get("scope") if isinstance(report.get("scope"), dict) else {}
    violations = tuple(
        _string(item.get("path"))
        for item in scope.get("violations", [])
        if isinstance(item, dict) and _string(item.get("path"))
    )
    if violations or scope.get("passed") is False:
        scope_state = "scope_violation"
    elif scope.get("passed") is True:
        scope_state = "scope_clean"
    else:
        scope_state = "unknown"

    commit_hash = _string(report.get("commit_hash")) or None
    decision = _string(report.get("commit_decision")).lower()
    if commit_hash:
        commit_state = "commit_created"
    elif "approval" in decision:
        commit_state = "blocked_by_approval"
    elif decision:
        commit_state = "no_commit"
    else:
        commit_state = "unknown"

    approval = report.get("approval") if isinstance(report.get("approval"), dict) else {}
    if approval.get("before_commit") or approval.get("before_merge"):
        approval_state = "human_approval_needed"
    elif approval:
        approval_state = "not_needed"
    else:
        approval_state = "unknown"

    return AgentOpsRunFact(
        source_path=path.as_posix(),
        job_id=_string(report.get("job_id")) or "unknown",
        status=_string(report.get("status")) or "unknown",
        branch=_string(report.get("branch")) or "unknown",
        worktree=_string(report.get("worktree")) or "unknown",
        gate_state=gate_state,
        scope_state=scope_state,
        commit_state=commit_state,
        approval_state=approval_state,
        changed_files=_strings(scope.get("changed_files")),
        scope_violations=violations,
        failed_gates=failed_gates,
        commit_hash=commit_hash,
        runtime_truth_ref_keys=_strings(runtime_summary.get("ref_keys")),
        runtime_truth_jobs_with_refs=_int(runtime_summary.get("jobs_with_refs")),
        runtime_truth_jobs_without_refs=_int(runtime_summary.get("jobs_without_refs")),
        receipt_refs=runtime_ref_values(
            report, ("receipt_id", "receipt_hash", "receipt_refs", "runtime_receipt_refs")
        ),
        correlation_ids=runtime_ref_values(report, ("run_id", "trace_id", "correlation_id")),
        identity_invariant_digests=runtime_ref_values(report, ("identity_invariant_digest",)),
    )


def _organ_state_fact(boundary: OrganBoundary, bundle: OperatingFactBundle) -> OrganStateFact:
    if boundary.name == "agentops":
        return _agentops_organ_state(boundary, bundle)
    if boundary.name == "kaizen_review":
        return _kaizen_organ_state(boundary, bundle)
    if boundary.name == "human_yds":
        return _human_yds_organ_state(boundary, bundle)
    if boundary.name == "burn_cost":
        return _burn_cost_organ_state(boundary, bundle)
    if boundary.name == "revenue":
        return _revenue_organ_state(boundary, bundle)
    if boundary.name == "daily_operating_brief":
        return _daily_brief_organ_state(boundary, bundle)
    if boundary.name == "command_spine":
        return _command_spine_organ_state(boundary, bundle)
    if boundary.name == "telic_value":
        return _telic_value_organ_state(boundary, bundle)
    return _state(
        boundary,
        observed_state="no organ-specific projection available",
        coherence_state="unknown",
        evidence_refs=(boundary.python_api,),
        open_gap="add an operating fact reader before trusting this organ's state",
        next_packet_hint=f"map {boundary.name} into operating_facts with tests",
    )


def _agentops_organ_state(boundary: OrganBoundary, bundle: OperatingFactBundle) -> OrganStateFact:
    if not bundle.agentops:
        return _state(
            boundary,
            observed_state="no AgentOps reports loaded",
            coherence_state="unknown",
            open_gap="AgentOps is declared but no report fact is present in this bundle",
            next_packet_hint="run one bounded AgentOps packet and load its report.json",
        )
    evidence = tuple(
        ref
        for run in bundle.agentops
        for ref in (
            run.source_path,
            *run.receipt_refs,
            *run.correlation_ids,
            *run.identity_invariant_digests,
        )
        if ref
    )
    if any(run.gate_state == "some_red" or run.scope_state == "scope_violation" for run in bundle.agentops):
        return _state(
            boundary,
            observed_state="AgentOps report loaded with red gate or scope violation",
            coherence_state="drifted",
            evidence_refs=evidence,
            open_gap="execution facts exist but the packet is not clean",
            next_packet_hint="fix the red gate or narrow allowed_files before expanding scope",
        )
    green_clean_runs = tuple(
        run for run in bundle.agentops if run.gate_state == "all_green" and run.scope_state == "scope_clean"
    )
    has_runtime_refs = any(
        bool(run.receipt_refs)
        or bool(run.correlation_ids)
        or bool(run.identity_invariant_digests)
        for run in green_clean_runs
    )
    if green_clean_runs and has_runtime_refs:
        return _state(
            boundary,
            observed_state="AgentOps report loaded with green gates, clean scope, and runtime truth refs",
            coherence_state="bound",
            evidence_refs=evidence,
        )
    if green_clean_runs:
        return _state(
            boundary,
            observed_state="AgentOps report loaded with green gates and clean scope but no runtime truth refs",
            coherence_state="partial",
            evidence_refs=evidence,
            open_gap="green gate/scope report lacks runtime truth refs",
            next_packet_hint="rerun AgentOps with trace, receipt, or identity refs before projecting bound",
        )
    return _state(
        boundary,
        observed_state="AgentOps report loaded with incomplete gate or scope evidence",
        coherence_state="partial",
        evidence_refs=evidence,
        open_gap="report exists but gate/scope truth is incomplete",
        next_packet_hint="rerun AgentOps with complete gate and scope fields",
    )


def _kaizen_organ_state(boundary: OrganBoundary, bundle: OperatingFactBundle) -> OrganStateFact:
    if not bundle.kaizen:
        return _declared_only(
            boundary,
            "KaizenReview has no report fact in this bundle",
            "run KaizenReview from a completed AgentOps report",
        )
    evidence = tuple(
        ref
        for review in bundle.kaizen
        for ref in (
            review.source_path,
            *review.receipt_refs,
            *review.correlation_ids,
            *review.identity_invariant_digests,
        )
        if ref
    )
    has_next = any(review.next_recommendation for review in bundle.kaizen)
    has_runtime_refs = any(review.runtime_truth_jobs_with_refs for review in bundle.kaizen)
    if has_next and has_runtime_refs:
        return _state(
            boundary,
            observed_state="KaizenReview report includes next-packet recommendation and runtime truth refs",
            coherence_state="bound",
            evidence_refs=evidence,
        )
    if has_next:
        return _state(
            boundary,
            observed_state="KaizenReview report includes next-packet recommendation without runtime truth refs",
            coherence_state="partial",
            evidence_refs=evidence,
            open_gap="review feeds the next packet but is not tied to runtime truth refs",
            next_packet_hint="rerun KaizenReview from AgentOps reports carrying trace, receipt, or identity refs",
        )
    return _state(
        boundary,
        observed_state="KaizenReview report loaded without next-packet recommendation",
        coherence_state="partial",
        evidence_refs=evidence,
        open_gap="review exists but does not feed the next AgentOps packet",
        next_packet_hint="rerun KaizenReview with a next_work_packet_recommendation",
    )


def _human_yds_organ_state(boundary: OrganBoundary, bundle: OperatingFactBundle) -> OrganStateFact:
    if not bundle.human_yds:
        return _declared_only(
            boundary,
            "human YDS ledger has no loaded rating fact",
            "record one human-authoritative YDS rating for the latest useful artifact",
        )
    evidence = tuple(rating.source_path for rating in bundle.human_yds if rating.source_path)
    if any(rating.authoritative for rating in bundle.human_yds):
        return _state(
            boundary,
            observed_state="human-authoritative YDS rating loaded",
            coherence_state="bound",
            evidence_refs=evidence,
        )
    return _state(
        boundary,
        observed_state="only advisory YDS ratings loaded",
        coherence_state="partial",
        evidence_refs=evidence,
        open_gap="YDS facts exist but none are human-authoritative",
        next_packet_hint="ask the operator to rate the artifact before using YDS as authority",
    )


def _burn_cost_organ_state(boundary: OrganBoundary, bundle: OperatingFactBundle) -> OrganStateFact:
    if not bundle.burn:
        return _declared_only(
            boundary,
            "burn/cost report has no loaded fact",
            "load a cost report before scaling more agent execution",
        )
    evidence = tuple(burn.source_path for burn in bundle.burn if burn.source_path)
    unpriced = sum(burn.unpriced_span_count for burn in bundle.burn)
    if unpriced:
        return _state(
            boundary,
            observed_state=f"burn report loaded with {unpriced} unpriced span(s)",
            coherence_state="partial",
            evidence_refs=evidence,
            open_gap="cost facts exist but some spans are unpriced",
            next_packet_hint="close the pricing span before scaling autonomous runs",
        )
    return _state(
        boundary,
        observed_state="burn report loaded with priced facts",
        coherence_state="bound",
        evidence_refs=evidence,
    )


def _revenue_organ_state(boundary: OrganBoundary, bundle: OperatingFactBundle) -> OrganStateFact:
    if not bundle.revenue:
        return _declared_only(
            boundary,
            "revenue signal source has no loaded fact",
            "bind one revenue or product-wedge note to the operating brief inputs",
        )
    evidence = tuple(signal.source_path for signal in bundle.revenue if signal.source_path)
    return _state(
        boundary,
        observed_state="revenue/product-wedge signal loaded",
        coherence_state="partial",
        evidence_refs=evidence,
        open_gap="revenue signals are present but not yet bound to outcome/value facts",
        next_packet_hint="link revenue signal to a Telic value or AgentOps artifact",
    )


def _daily_brief_organ_state(boundary: OrganBoundary, bundle: OperatingFactBundle) -> OrganStateFact:
    loaded_count = (
        len(bundle.agentops)
        + len(bundle.kaizen)
        + len(bundle.human_yds)
        + len(bundle.burn)
        + len(bundle.revenue)
    )
    if not loaded_count:
        return _declared_only(
            boundary,
            "Daily Brief has no loaded upstream facts in this bundle",
            "feed at least one operating fact source into the brief builder",
        )
    if bundle.missing_sources:
        return _state(
            boundary,
            observed_state="Daily Brief can read some upstream facts but sources are missing",
            coherence_state="partial",
            evidence_refs=tuple(bundle.missing_sources),
            open_gap="not all declared brief inputs are present",
            next_packet_hint="fill the missing operating fact source with the highest review value",
        )
    return _state(
        boundary,
        observed_state="Daily Brief has all declared fact inputs loaded",
        coherence_state="bound",
    )


def _command_spine_organ_state(boundary: OrganBoundary, bundle: OperatingFactBundle) -> OrganStateFact:
    if bundle.agentops:
        return _state(
            boundary,
            observed_state="command spine can be checked against loaded AgentOps facts",
            coherence_state="partial",
            evidence_refs=tuple(run.source_path for run in bundle.agentops),
            open_gap="command plans are advisory until AgentOps and human review close the loop",
            next_packet_hint="compare the next command plan to the latest AgentOps report",
        )
    return _state(
        boundary,
        observed_state="dry-run command planning API exists without loaded execution feedback",
        coherence_state="partial",
        evidence_refs=(boundary.python_api,),
        open_gap="no AgentOps feedback fact is loaded for this command spine view",
        next_packet_hint="run the drafted packet through AgentOps and reload facts",
    )


def _telic_value_organ_state(boundary: OrganBoundary, bundle: OperatingFactBundle) -> OrganStateFact:
    summary = read_telic_value_summary()
    if not summary:
        return _state(
            boundary,
            observed_state="ontology DB not present or empty; no telic value projected",
            coherence_state="declared_only",
            evidence_refs=(boundary.python_api,),
            open_gap="Outcome/ValueEvent/Contribution objects not yet created",
            next_packet_hint="run a revenue or task cycle that writes to TelicSeam",
        )
    counts = summary.get("counts", {})
    total = sum(counts.values())
    revenue_usd = summary.get("revenue_usd", 0.0)
    parts = [f"{k}={v}" for k, v in counts.items() if v]
    observed = f"{total} telic objects ({', '.join(parts)})"
    if revenue_usd > 0:
        observed += f"; revenue value ${revenue_usd:.2f}"
    return _state(
        boundary,
        observed_state=observed,
        coherence_state="bound" if total > 0 else "declared_only",
        evidence_refs=(str(Path.home() / ".dharma" / "ontology.db"),),
        open_gap="" if total > 0 else "no telic objects found",
        next_packet_hint="use telic value facts in operator synthesis" if total > 0
        else "run a cycle that writes Outcome/ValueEvent/Contribution",
    )


def _declared_only(boundary: OrganBoundary, open_gap: str, next_packet_hint: str) -> OrganStateFact:
    return _state(
        boundary,
        observed_state="declared boundary with no loaded runtime fact",
        coherence_state="declared_only",
        evidence_refs=(boundary.python_api,),
        open_gap=open_gap,
        next_packet_hint=next_packet_hint,
    )


def _state(
    boundary: OrganBoundary,
    *,
    observed_state: str,
    coherence_state: str,
    evidence_refs: tuple[str, ...] = (),
    open_gap: str = "",
    next_packet_hint: str = "",
) -> OrganStateFact:
    if coherence_state not in COHERENCE_STATES:
        raise ValueError(f"unknown coherence_state: {coherence_state}")
    return OrganStateFact(
        name=boundary.name,
        owns=boundary.owns,
        declared_state=f"owns {boundary.owns}; emits {', '.join(boundary.emits) or 'nothing'}",
        observed_state=observed_state,
        coherence_state=coherence_state,
        evidence_refs=tuple(ref for ref in evidence_refs if ref),
        open_gap=open_gap,
        next_packet_hint=next_packet_hint,
        declared_primitive=boundary.owns,
        actual_runtime_primitive=observed_state,
        source_stores=boundary.may_read,
        sink_stores=boundary.emits,
        gates_declared=boundary.must_not_mutate,
        gates_enforced=(),
        witness_writes=tuple(ref for ref in evidence_refs if ref),
        last_observed=utc_now_iso(),
        drift=open_gap,
        next_bindable_gap=next_packet_hint,
        risk="unknown" if coherence_state == "unknown" else coherence_state,
    )


def _gate_fact(gate: Any, index: int) -> GateFact:
    if not isinstance(gate, dict):
        return GateFact(name=f"gate-{index + 1}", passed=None)
    passed = gate.get("passed")
    if not isinstance(passed, bool):
        exit_code = gate.get("exit_code")
        passed = exit_code == 0 if isinstance(exit_code, int) else None
    exit_code = gate.get("exit_code")
    return GateFact(
        name=_string(gate.get("name")) or f"gate-{index + 1}",
        passed=passed,
        exit_code=exit_code if isinstance(exit_code, int) else None,
    )


def _yds_fact(source_path: str, record: dict[str, Any]) -> HumanQualityRatingFact | None:
    rating = _string(record.get("rating_value") or record.get("rating") or record.get("yds"))
    if not rating:
        return None
    artifact = record.get("artifact")
    title = ""
    if isinstance(artifact, dict):
        artifact_uri = _string(artifact.get("uri"))
        title = _string(artifact.get("title"))
    else:
        artifact_uri = _string(artifact)
    source = _string(record.get("source") or record.get("operator_id")).lower()
    context = record.get("context") if isinstance(record.get("context"), dict) else {}
    context_source = _string(context.get("source")).lower()
    authoritative = source in HUMAN_YDS_SOURCES or context_source == "operator_cli"
    return HumanQualityRatingFact(
        source_path=source_path,
        artifact_uri=artifact_uri or "unknown",
        rating=rating,
        source=source or context_source or "unknown",
        human_note=_string(record.get("human_note") or record.get("human_comment") or record.get("comment")),
        created_at=_string(record.get("created_at") or record.get("timestamp")),
        authoritative=authoritative,
        title=title,
    )


def _burn_fact(source_path: str, records: list[dict[str, Any]]) -> BurnReportFact:
    total_cost = 0.0
    saw_cost = False
    total_tokens = 0
    saw_tokens = False
    unpriced = 0
    labels: list[str] = []
    for record in records:
        cost = _first_number(record, ("total_cost_usd", "estimated_cost_usd", "cost_usd", "amount_usd"))
        tokens = _first_int(record, ("total_tokens", "tokens", "input_tokens", "output_tokens"))
        if cost is not None:
            total_cost += cost
            saw_cost = True
        elif any(key in record for key in ("provider", "model", "span_id", "trace_id")):
            unpriced += 1
        if tokens is not None:
            total_tokens += tokens
            saw_tokens = True
        label = _string(record.get("label") or record.get("task") or record.get("provider") or record.get("model"))
        if label:
            labels.append(label)
    label = ", ".join(sorted(set(labels))[:3]) or Path(source_path).name
    return BurnReportFact(
        source_path=source_path,
        label=label,
        total_cost_usd=round(total_cost, 6) if saw_cost else None,
        total_tokens=total_tokens if saw_tokens else None,
        unpriced_span_count=unpriced,
        raw_count=len(records),
    )


def _json_reports(path: Path | None, filename: str) -> list[tuple[Path, dict[str, Any]]]:
    if path is None:
        return []
    resolved = path.expanduser()
    paths: list[Path]
    if resolved.is_file():
        paths = [resolved] if resolved.name == filename else []
    elif resolved.is_dir():
        paths = sorted(resolved.rglob(filename))
    else:
        return []
    reports: list[tuple[Path, dict[str, Any]]] = []
    for item in paths:
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            reports.append((item, data))
    return reports


def _load_records(path: Path | None) -> list[dict[str, Any]] | None:
    if path is None:
        return None
    resolved = path.expanduser()
    if not resolved.exists():
        return None
    text = resolved.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if resolved.suffix.lower() == ".jsonl":
        records: list[dict[str, Any]] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                records.append(data)
        return records
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _first_number(record: dict[str, Any], keys: Iterable[str]) -> float | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _first_int(record: dict[str, Any], keys: Iterable[str]) -> int | None:
    for direct_key in ("total_tokens", "tokens"):
        value = record.get(direct_key)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    total = 0
    saw = False
    for key in keys:
        if key in {"total_tokens", "tokens"}:
            continue
        value = record.get(key)
        if isinstance(value, int):
            total += value
            saw = True
        elif isinstance(value, float):
            total += int(value)
            saw = True
    return total if saw else None


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _string(value: Any) -> str:
    return str(value or "").strip()


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(_string(item) for item in value if _string(item))
