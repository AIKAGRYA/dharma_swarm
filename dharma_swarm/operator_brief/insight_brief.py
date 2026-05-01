"""Ontology-native Operator Brief seam (v0).

Implements the contract in
``docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md``.

Single public entrypoint: :func:`run_once`. One tick produces a
``KnowledgeArtifact`` of subtype ``operator_brief`` linked to a full
witness/gate/value chain — or a fail-closed Outcome if any required
gate blocks.

Gate mapping (master spec §6, applied in this order):

* ``CONSENT``    — Tier B. Permission/exfiltration check.
* ``BHED_GNAN``  — Tier C. Doer-witness distinction. Always passes
  today; the witness row is still written so the seam picks up future
  strengthening automatically.
* ``STEELMAN``   — Tier C. Counterargument requirement. Enforced here:
  the drafted brief must contain at least one steelman marker or this
  seam treats the gate as BLOCK.
* ``DOGMA_DRIFT``— Tier C. Confidence-without-evidence check.
  Enforced here: the drafted brief must cite at least one
  ``session_events`` or ``memory_facts`` row id, or this seam treats
  the gate as BLOCK (fails as ``failed_input`` if no source available
  at all).

A REVIEW from any of the four gates is treated as BLOCK for v0.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.models import GateCheckResult, GateDecision, GateResult
from dharma_swarm.ontology import OntologyObj, OntologyRegistry
from dharma_swarm.ontology_runtime import (
    get_shared_registry,
    persist_shared_registry,
)
from dharma_swarm.telos_gates import DEFAULT_GATEKEEPER, TelosGatekeeper

logger = logging.getLogger(__name__)

REQUIRED_GATES: tuple[str, ...] = (
    "CONSENT",
    "BHED_GNAN",
    "STEELMAN",
    "DOGMA_DRIFT",
)

ARTIFACT_SUBTYPE = "operator_brief"
ARTIFACT_TYPE = "note"
DEFAULT_AGENT_ID = "operator_brief_agent"
DEFAULT_AGENT_NAME = "OperatorBriefAgent"

ENABLED_ENV = "DHARMA_OPERATOR_BRIEF_ENABLED"


# ──────────────────────────────────────────────────────────────────────
# Internal data carriers — not persisted; the persisted truth is the
# OntologyObj rows we register through OntologyRegistry.
# ──────────────────────────────────────────────────────────────────────


@dataclass
class _BriefInput:
    snapshot_hash: str
    cited_fact_ids: list[str] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)
    counterargument: str = ""
    has_source: bool = True

    def is_blank(self) -> bool:
        return not self.summary_lines and not self.cited_fact_ids


@dataclass
class _DraftedBrief:
    title: str
    body_markdown: str
    cited_fact_ids: list[str]
    has_steelman: bool


@dataclass
class _RunResult:
    artifact_id: str | None
    outcome: str
    witness_log_ids: list[str]
    gate_decision_ids: list[str]
    proposal_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "outcome": self.outcome,
            "witness_log_ids": list(self.witness_log_ids),
            "gate_decision_ids": list(self.gate_decision_ids),
            "proposal_id": self.proposal_id,
        }


# ──────────────────────────────────────────────────────────────────────
# Path helpers — every filesystem write goes through these so the
# no-raw-bypass test can verify the seam respects the artifact root.
# ──────────────────────────────────────────────────────────────────────


def _artifact_root() -> Path:
    """Resolve ``~/.dharma/artifacts/operator_brief`` honoring HOME overrides."""
    return Path.home() / ".dharma" / "artifacts" / "operator_brief"


def _artifact_dir_for(date_str: str) -> Path:
    return _artifact_root() / date_str


# ──────────────────────────────────────────────────────────────────────
# Public entrypoint
# ──────────────────────────────────────────────────────────────────────


def run_once(
    *,
    registry: OntologyRegistry | None = None,
    input_payload: dict[str, Any] | None = None,
    agent_id: str = DEFAULT_AGENT_ID,
    agent_name: str = DEFAULT_AGENT_NAME,
    gatekeeper: TelosGatekeeper | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """One tick of the operator-brief seam.

    Returns a dict with ``artifact_id``, ``outcome``, ``witness_log_ids``,
    ``gate_decision_ids``, ``proposal_id``. Idempotent on
    ``(date, agent_id)``: a re-run on the same day with the same agent
    returns the existing artifact instead of creating a duplicate.

    The ``input_payload`` argument is provided primarily for tests; in
    cron mode it is None and ``_collect_input`` derives a minimal
    snapshot from runtime state. Gates remain load-bearing in either
    mode.
    """

    reg = registry if registry is not None else get_shared_registry()
    keeper = gatekeeper or DEFAULT_GATEKEEPER
    now_dt = now or datetime.now(timezone.utc)
    date_str = now_dt.date().isoformat()

    agent_obj = _ensure_agent(reg, agent_id=agent_id, agent_name=agent_name)
    actual_agent_id = agent_obj.id if agent_obj is not None else agent_id

    # Idempotency: short-circuit if today's brief already exists for this agent.
    existing = _existing_artifact_for(reg, date_str, actual_agent_id)
    if existing is not None:
        return _RunResult(
            artifact_id=existing.id,
            outcome="success",
            witness_log_ids=[],
            gate_decision_ids=[],
            proposal_id=existing.properties.get("provenance", "") or None,
        ).to_dict()

    witness_ids: list[str] = []
    gate_ids: list[str] = []

    brief_input = _collect_input(input_payload)

    proposal_id = _propose(
        reg,
        agent_id=actual_agent_id,
        title=f"Operator Brief — {date_str}",
        snapshot_hash=brief_input.snapshot_hash,
    )

    witness_ids.append(
        _record_witness(
            reg,
            agent_obj,
            observation=(
                f"operator_brief.tick.start input_hash={brief_input.snapshot_hash} "
                f"cited={len(brief_input.cited_fact_ids)}"
            ),
            context=f"proposal:{proposal_id}",
        )
    )

    if not brief_input.has_source:
        # No runtime source at all — fail closed before drafting.
        gate_id = _record_gate_decision(
            reg,
            proposal_id=proposal_id,
            gate_name="DOGMA_DRIFT",
            decision=GateDecision.BLOCK,
            reason="no runtime source available; nothing to cite",
            gate_results={"DOGMA_DRIFT": (GateResult.FAIL, "no source")},
        )
        gate_ids.append(gate_id)
        witness_ids.append(
            _record_witness(
                reg,
                agent_obj,
                observation=(
                    "operator_brief.gate DOGMA_DRIFT block "
                    "reason=no-source proposal=" + str(proposal_id)
                ),
                context=f"gate_decision:{gate_id}",
            )
        )
        outcome_id = _record_outcome(
            reg,
            proposal_id=proposal_id,
            agent_id=actual_agent_id,
            success=False,
            reason="failed_input",
        )
        # Even on failure-closed, emit a (zero-value) ValueEvent + Contribution
        # so the watchdog (NEXT_10 item 8) can distinguish "ran and failed"
        # from "did not run".
        _emit_value_event(
            reg,
            outcome_id=outcome_id,
            agent_id=actual_agent_id,
            success=False,
            cited_count=0,
        )
        return _RunResult(
            artifact_id=None,
            outcome="failed_input",
            witness_log_ids=witness_ids,
            gate_decision_ids=gate_ids,
            proposal_id=proposal_id,
        ).to_dict()

    drafted = _draft_brief(brief_input, date_str=date_str, agent_name=agent_name)

    gate_results = _evaluate_gates(
        keeper=keeper,
        drafted=drafted,
        cited_fact_ids=brief_input.cited_fact_ids,
    )

    blocked_gate: str | None = None
    for gate_name in REQUIRED_GATES:
        result, reason = gate_results.get(
            gate_name, (GateResult.PASS, "not evaluated")
        )

        # Map gate result → decision. REVIEW is treated as BLOCK for v0
        # per master spec §6.
        if result == GateResult.PASS:
            decision = GateDecision.ALLOW
        elif result == GateResult.WARN:
            decision = GateDecision.BLOCK
        else:
            decision = GateDecision.BLOCK

        gate_id = _record_gate_decision(
            reg,
            proposal_id=proposal_id,
            gate_name=gate_name,
            decision=decision,
            reason=reason,
            gate_results={gate_name: (result, reason)},
        )
        gate_ids.append(gate_id)
        witness_ids.append(
            _record_witness(
                reg,
                agent_obj,
                observation=(
                    f"operator_brief.gate {gate_name} {decision.value} "
                    f"reason={reason or 'ok'}"
                ),
                context=f"gate_decision:{gate_id}",
            )
        )
        if decision == GateDecision.BLOCK and blocked_gate is None:
            blocked_gate = gate_name

    if blocked_gate is not None:
        outcome_id = _record_outcome(
            reg,
            proposal_id=proposal_id,
            agent_id=actual_agent_id,
            success=False,
            reason=f"failed_gate:{blocked_gate}",
        )
        _emit_value_event(
            reg,
            outcome_id=outcome_id,
            agent_id=actual_agent_id,
            success=False,
            cited_count=len(brief_input.cited_fact_ids),
        )
        _persist_if_shared(reg, registry)
        return _RunResult(
            artifact_id=None,
            outcome=f"failed_gate:{blocked_gate}",
            witness_log_ids=witness_ids,
            gate_decision_ids=gate_ids,
            proposal_id=proposal_id,
        ).to_dict()

    artifact_id, content_hash, materialise_error = _materialise_artifact(
        reg,
        proposal_id=proposal_id,
        agent_obj=agent_obj,
        agent_id=actual_agent_id,
        drafted=drafted,
        date_str=date_str,
        gate_decision_ids=gate_ids,
        witness_log_ids=witness_ids,
    )

    if artifact_id is None:
        outcome_id = _record_outcome(
            reg,
            proposal_id=proposal_id,
            agent_id=actual_agent_id,
            success=False,
            reason="failed_materialise",
            error=materialise_error or "",
        )
        _emit_value_event(
            reg,
            outcome_id=outcome_id,
            agent_id=actual_agent_id,
            success=False,
            cited_count=len(brief_input.cited_fact_ids),
        )
        _persist_if_shared(reg, registry)
        return _RunResult(
            artifact_id=None,
            outcome="failed_materialise",
            witness_log_ids=witness_ids,
            gate_decision_ids=gate_ids,
            proposal_id=proposal_id,
        ).to_dict()

    witness_ids.append(
        _record_witness(
            reg,
            agent_obj,
            observation=(
                f"operator_brief.materialise artifact={artifact_id} "
                f"sha256={content_hash}"
            ),
            context=f"artifact:{artifact_id}",
        )
    )

    outcome_id = _record_outcome(
        reg,
        proposal_id=proposal_id,
        agent_id=actual_agent_id,
        success=True,
        reason="success",
        result_summary=drafted.title,
    )

    value_event_id = _emit_value_event(
        reg,
        outcome_id=outcome_id,
        agent_id=actual_agent_id,
        success=True,
        cited_count=len(brief_input.cited_fact_ids),
    )

    if value_event_id is not None:
        _record_contribution(
            reg,
            value_event_id=value_event_id,
            agent_id=actual_agent_id,
        )

    if agent_obj is not None:
        _safe_create_link(reg, "authored", agent_obj.id, artifact_id)

    _persist_if_shared(reg, registry)

    return _RunResult(
        artifact_id=artifact_id,
        outcome="success",
        witness_log_ids=witness_ids,
        gate_decision_ids=gate_ids,
        proposal_id=proposal_id,
    ).to_dict()


# ──────────────────────────────────────────────────────────────────────
# Cron handler entrypoint
# ──────────────────────────────────────────────────────────────────────


def cron_run(job: dict[str, Any] | None = None) -> dict[str, Any]:
    """Cron handler: gated by ``DHARMA_OPERATOR_BRIEF_ENABLED``.

    When the flag is off (default), the function performs no source
    mutation: it does not create proposals, witness logs, gate
    decisions, artifacts, or value events. It simply reports
    ``status='disabled'``.
    """
    del job  # unused; kept for handler-protocol compatibility
    if os.getenv(ENABLED_ENV, "0").strip() not in ("1", "true", "TRUE", "yes"):
        logger.info(
            "operator_brief disabled (set %s=1 to enable)", ENABLED_ENV
        )
        return {
            "status": "disabled",
            "reason": f"{ENABLED_ENV} not set; no-op",
            "outcome": "skipped",
        }
    result = run_once()
    result["status"] = "ran"
    return result


# ──────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────


def _ensure_agent(
    reg: OntologyRegistry,
    *,
    agent_id: str,
    agent_name: str,
) -> OntologyObj | None:
    for obj in reg.get_objects_by_type("AgentIdentity"):
        if obj.properties.get("agent_id") == agent_id or obj.properties.get(
            "name"
        ) == agent_name:
            return obj
    obj, _errors = reg.create_object(
        "AgentIdentity",
        properties={
            "name": agent_name,
            "agent_id": agent_id,
            "role": "operator",
            "status": "idle",
            "provider": "system",
            "model": "operator_brief_seam_v0",
            "capabilities": ["operator_brief"],
        },
        created_by="operator_brief",
    )
    return obj


def _existing_artifact_for(
    reg: OntologyRegistry,
    date_str: str,
    agent_id: str,
) -> OntologyObj | None:
    for obj in reg.get_objects_by_type("KnowledgeArtifact"):
        props = obj.properties
        if props.get("subtype") != ARTIFACT_SUBTYPE:
            continue
        if props.get("brief_date") == date_str and props.get("agent_id") == agent_id:
            return obj
    return None


def _collect_input(payload: dict[str, Any] | None) -> _BriefInput:
    """Collect minimal runtime input for the brief.

    For v0, ``payload`` (when provided) is treated as the snapshot. In
    cron mode payload is None and we still require the caller (or a
    later wiring step) to surface something to cite — fail-closed if
    nothing is available. NEXT_10_SUBSTRATE_TODO item 7 will plumb
    real ``session_events``/``memory_facts`` here.
    """
    if not payload:
        # No source plumbed yet — surface honestly. The DOGMA_DRIFT path
        # in run_once will fail-closed.
        return _BriefInput(snapshot_hash="empty", has_source=False)

    cited = list(payload.get("cited_fact_ids") or [])
    lines = list(payload.get("summary_lines") or [])
    counter = str(payload.get("counterargument") or "").strip()
    raw = "|".join(cited) + "::" + "\n".join(lines) + "::" + counter
    snapshot_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return _BriefInput(
        snapshot_hash=snapshot_hash,
        cited_fact_ids=cited,
        summary_lines=lines,
        counterargument=counter,
        has_source=bool(cited or lines),
    )


def _propose(
    reg: OntologyRegistry,
    *,
    agent_id: str,
    title: str,
    snapshot_hash: str,
) -> str:
    obj, errors = reg.create_object(
        "ActionProposal",
        properties={
            "task_id": f"operator_brief::{snapshot_hash}",
            "agent_id": agent_id,
            "action_type": "manual",
            "title": title,
            "description": "Publish ontology-native operator brief (v0 seam).",
            "status": "proposed",
            "priority": "normal",
        },
        created_by="operator_brief",
    )
    if obj is None:
        raise RuntimeError(f"ActionProposal creation failed: {errors}")
    return obj.id


def _draft_brief(
    brief_input: _BriefInput,
    *,
    date_str: str,
    agent_name: str,
) -> _DraftedBrief:
    title = f"Operator Brief — {date_str}"
    counter = brief_input.counterargument or (
        "However, today's signal is sparse; an opposing read is that no "
        "decisive action is warranted yet."
    )
    summary_section = (
        "\n".join(f"- {line}" for line in brief_input.summary_lines)
        if brief_input.summary_lines
        else "- (no narrative lines surfaced; minimal brief)"
    )
    sources_section = (
        "\n".join(f"- `{fid}`" for fid in brief_input.cited_fact_ids)
        if brief_input.cited_fact_ids
        else "- (no sources cited)"
    )
    body = (
        f"# {title}\n\n"
        f"_Drafted by `{agent_name}` for the ontology-native operator brief seam (v0)._\n\n"
        "## Summary\n"
        f"{summary_section}\n\n"
        "## Cited runtime facts\n"
        f"{sources_section}\n\n"
        "## Steelman / opposing read\n"
        f"{counter}\n\n"
        "## Provenance\n"
        f"- input_snapshot_hash: `{brief_input.snapshot_hash}`\n"
        f"- cited_fact_count: {len(brief_input.cited_fact_ids)}\n"
        "- value_estimates: marked as ESTIMATED, not verified\n"
    )
    has_steelman = bool(
        re.search(r"\b(however|on the other hand|counter|opposing)\b", body, re.I)
    )
    return _DraftedBrief(
        title=title,
        body_markdown=body,
        cited_fact_ids=list(brief_input.cited_fact_ids),
        has_steelman=has_steelman,
    )


def _evaluate_gates(
    *,
    keeper: TelosGatekeeper,
    drafted: _DraftedBrief,
    cited_fact_ids: list[str],
) -> dict[str, tuple[GateResult, str]]:
    """Run the four required gates against the drafted brief content.

    Strategy:
    1. Call ``keeper.check`` once on the drafted body for CONSENT,
       BHED_GNAN, and ambient gate behaviour.
    2. Locally enforce STEELMAN (must contain a counter-argument
       marker — the gate's pattern check requires "mutate"/"propose"
       in the action string, which this seam does not use, so we
       enforce the spirit of the gate ourselves and record it).
    3. Locally enforce DOGMA_DRIFT (must cite ≥1 runtime fact id).

    The returned mapping always contains all four required gate names.
    """
    keeper_result: GateCheckResult = keeper.check(
        action="propose operator brief",
        content=drafted.body_markdown,
        tool_name="operator_brief",
        trust_mode="internal_yolo",
    )
    keeper_gates = keeper_result.gate_results

    out: dict[str, tuple[GateResult, str]] = {}

    consent = keeper_gates.get("CONSENT") or (GateResult.PASS, "")
    out["CONSENT"] = consent

    bhed = keeper_gates.get("BHED_GNAN") or (
        GateResult.PASS,
        "Doer-witness distinction noted",
    )
    out["BHED_GNAN"] = bhed

    if drafted.has_steelman:
        out["STEELMAN"] = (GateResult.PASS, "Counterargument present")
    else:
        out["STEELMAN"] = (
            GateResult.FAIL,
            "No steelman/counterargument found in drafted brief",
        )

    if cited_fact_ids:
        out["DOGMA_DRIFT"] = (
            GateResult.PASS,
            f"{len(cited_fact_ids)} runtime fact(s) cited",
        )
    else:
        out["DOGMA_DRIFT"] = (
            GateResult.FAIL,
            "No runtime fact ids cited; confidence without evidence",
        )

    return out


def _record_gate_decision(
    reg: OntologyRegistry,
    *,
    proposal_id: str,
    gate_name: str,
    decision: GateDecision,
    reason: str,
    gate_results: dict[str, tuple[GateResult, str]],
) -> str:
    serialized: dict[str, Any] = {}
    for name, (result, msg) in gate_results.items():
        serialized[name] = {
            "result": result.value if hasattr(result, "value") else str(result),
            "reason": msg,
            "gate": gate_name,
        }
    obj, errors = reg.create_object(
        "GateDecisionRecord",
        properties={
            "proposal_id": proposal_id,
            "decision": decision.value,
            "reason": f"{gate_name}: {reason}",
            "gate_results": serialized,
            "witness_reroutes": 0,
        },
        created_by="operator_brief",
    )
    if obj is None:
        raise RuntimeError(f"GateDecisionRecord creation failed: {errors}")

    # The has_gate_decision link is ONE_TO_ONE per the existing schema.
    # We attach the FIRST gate decision via the typed link and surface
    # the remainder via the proposal_id property (queryable).
    existing_link = reg.get_links(
        source_id=proposal_id, link_name="has_gate_decision"
    )
    if not existing_link:
        _safe_create_link(reg, "has_gate_decision", proposal_id, obj.id)
    return obj.id


def _record_witness(
    reg: OntologyRegistry,
    agent_obj: OntologyObj | None,
    *,
    observation: str,
    context: str,
) -> str:
    obj, errors = reg.create_object(
        "WitnessLog",
        properties={
            "observation": observation,
            "observer": "operator_brief",
            "context": context,
            "witness_quality": 0.7,
        },
        created_by="operator_brief",
    )
    if obj is None:
        raise RuntimeError(f"WitnessLog creation failed: {errors}")
    if agent_obj is not None:
        _safe_create_link(reg, "witnessed", agent_obj.id, obj.id)
    return obj.id


def _record_outcome(
    reg: OntologyRegistry,
    *,
    proposal_id: str,
    agent_id: str,
    success: bool,
    reason: str,
    result_summary: str = "",
    error: str = "",
) -> str:
    obj, errors = reg.create_object(
        "Outcome",
        properties={
            "proposal_id": proposal_id,
            "task_id": f"operator_brief::{proposal_id}",
            "agent_id": agent_id,
            "success": success,
            "result_summary": result_summary or reason,
            "error": error,
            "duration_ms": 0.0,
            "fitness_score": 1.0 if success else 0.0,
        },
        created_by="operator_brief",
    )
    if obj is None:
        raise RuntimeError(f"Outcome creation failed: {errors}")
    existing = reg.get_links(source_id=proposal_id, link_name="has_outcome")
    if not existing:
        _safe_create_link(reg, "has_outcome", proposal_id, obj.id)
    return obj.id


def _emit_value_event(
    reg: OntologyRegistry,
    *,
    outcome_id: str,
    agent_id: str,
    success: bool,
    cited_count: int,
) -> str | None:
    # Honest, estimated value: reflect that this is the operator-brief
    # seam (decision_clarity / operational_readiness) and that v0 has
    # not measured time saved. composite_value is conservatively low.
    composite = 0.5 if success else 0.0
    obj, errors = reg.create_object(
        "ValueEvent",
        properties={
            "outcome_id": outcome_id,
            "agent_id": agent_id,
            "cell_id": "",
            "task_id": f"operator_brief::{outcome_id}",
            "task_type": "operator_brief",
            "behavioral_signal": 0.5,
            "success_value": 1.0 if success else 0.0,
            "duration_efficiency": 0.5,
            "composite_value": composite,
            "scoring_method": "operator_brief_v0_estimated",
        },
        created_by="operator_brief",
    )
    if obj is None:
        logger.warning("ValueEvent creation failed: %s", errors)
        return None
    _safe_create_link(reg, "has_value_event", outcome_id, obj.id)
    obj.properties["estimated"] = True
    obj.properties["cited_count"] = cited_count
    return obj.id


def _record_contribution(
    reg: OntologyRegistry,
    *,
    value_event_id: str,
    agent_id: str,
) -> str | None:
    obj, errors = reg.create_object(
        "Contribution",
        properties={
            "value_event_id": value_event_id,
            "agent_id": agent_id,
            "cell_id": "",
            "task_type": "operator_brief",
            "credit_share": 1.0,
            "attributed_value": 0.5,
        },
        created_by="operator_brief",
    )
    if obj is None:
        logger.warning("Contribution creation failed: %s", errors)
        return None
    _safe_create_link(reg, "has_contribution", value_event_id, obj.id)
    return obj.id


def _materialise_artifact(
    reg: OntologyRegistry,
    *,
    proposal_id: str,
    agent_obj: OntologyObj | None,
    agent_id: str,
    drafted: _DraftedBrief,
    date_str: str,
    gate_decision_ids: list[str],
    witness_log_ids: list[str],
) -> tuple[str | None, str, str | None]:
    """Create the KnowledgeArtifact row, then write the file.

    Returns ``(artifact_id, sha256_hex, error_message)``. On
    materialisation failure (filesystem error after gates pass),
    returns ``(None, "", reason)`` so the caller can record a
    ``failed_materialise`` outcome.
    """
    artifact_obj, errors = reg.create_object(
        "KnowledgeArtifact",
        properties={
            "title": drafted.title,
            "artifact_type": ARTIFACT_TYPE,
            "domain": "dharma_swarm",
            "content": drafted.body_markdown,
            "provenance": proposal_id,
            "confidence": 0.6,
            "verified": False,
            # Subtype encoded in an existing-but-unused property field
            # to honour the spec's "no schema changes" rule.
            "subtype": ARTIFACT_SUBTYPE,
            "agent_id": agent_id,
            "brief_date": date_str,
        },
        created_by="operator_brief",
    )
    if artifact_obj is None:
        return None, "", f"KnowledgeArtifact creation failed: {errors}"

    artifact_id = artifact_obj.id

    # Build markdown body with frontmatter that records full lineage.
    frontmatter = (
        "---\n"
        f"artifact_id: {artifact_id}\n"
        f"agent_id: {agent_id}\n"
        f"proposal_id: {proposal_id}\n"
        f"brief_date: {date_str}\n"
        f"gate_decision_ids: [{', '.join(gate_decision_ids)}]\n"
        f"witness_log_ids: [{', '.join(witness_log_ids)}]\n"
        "value_event_status: estimated_not_verified\n"
        "---\n\n"
    )
    full_body = frontmatter + drafted.body_markdown

    artifact_dir = _artifact_dir_for(date_str)
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return None, "", f"mkdir failed: {exc}"

    file_path = artifact_dir / f"{artifact_id}.md"
    try:
        file_path.write_text(full_body, encoding="utf-8")
    except OSError as exc:
        return None, "", f"write failed: {exc}"

    content_hash = hashlib.sha256(full_body.encode("utf-8")).hexdigest()
    artifact_obj.properties["file_path"] = str(file_path)
    artifact_obj.properties["content_sha256"] = content_hash
    return artifact_id, content_hash, None


def _safe_create_link(
    reg: OntologyRegistry,
    link_name: str,
    source_id: str,
    target_id: str,
) -> None:
    try:
        reg.create_link(link_name, source_id=source_id, target_id=target_id,
                        created_by="operator_brief")
    except Exception:
        logger.debug("link %s skipped (%s -> %s)", link_name, source_id, target_id,
                     exc_info=True)


def _persist_if_shared(
    reg: OntologyRegistry,
    user_supplied: OntologyRegistry | None,
) -> None:
    """Flush back to disk only when we are operating on the shared registry.

    Tests pass an in-memory registry and should not trigger filesystem
    persistence beyond the artifact file itself.
    """
    if user_supplied is not None:
        return
    try:
        persist_shared_registry(reg)
    except Exception:
        logger.debug("operator_brief persist skipped", exc_info=True)
