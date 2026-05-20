"""Artifact and runtime-record persistence for the Operator Brief seam."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

from dharma_swarm.correlation_context import get_correlation
from dharma_swarm.ontology import OntologyObj, OntologyRegistry
from dharma_swarm.runtime_state import ArtifactRecord, RuntimeStateStore

from dharma_swarm.operator_brief.types import (
    ARTIFACT_SUBTYPE,
    ARTIFACT_TYPE,
    OPERATOR_BRIEF_CAUSE_ID,
    OPERATOR_BRIEF_CELL_KIND,
    OPERATOR_BRIEF_CELL_NAME,
    _BriefInput,
    _DraftedBrief,
)

logger = logging.getLogger(__name__)

OPERATOR_BRIEF_TRACE_ID_SOURCE = "synthetic_legacy_alias"


def _operator_brief_trace(proposal_id: str, date_str: str) -> tuple[str, str]:
    """Return a deterministic legacy trace alias until upstream trace propagation lands."""
    correlation = get_correlation()
    if correlation.trace_id:
        return correlation.trace_id, "correlation_context"
    anchor = proposal_id or date_str
    return f"operator_brief::{anchor}", OPERATOR_BRIEF_TRACE_ID_SOURCE


def _artifact_root() -> Path:
    """Resolve ``~/.dharma/artifacts/operator_brief`` honoring HOME overrides."""
    return Path.home() / ".dharma" / "artifacts" / "operator_brief"


def _artifact_dir_for(date_str: str) -> Path:
    return _artifact_root() / date_str


def _materialise_artifact(
    reg: OntologyRegistry,
    *,
    runtime_state: RuntimeStateStore | None,
    proposal_id: str,
    agent_obj: OntologyObj | None,
    agent_id: str,
    cell_id: str,
    brief_input: _BriefInput,
    drafted: _DraftedBrief,
    date_str: str,
    gate_decision_ids: list[str],
    witness_log_ids: list[str],
) -> tuple[str | None, str, str | None]:
    """Write the file, then publish the KnowledgeArtifact row.

    Returns ``(artifact_id, sha256_hex, error_message)``. On
    materialisation failure (filesystem error after gates pass),
    returns ``(None, "", reason)`` so the caller can record a
    ``failed_materialise`` outcome.
    """
    del agent_obj  # retained in the call signature for seam readability
    trace_id, trace_id_source = _operator_brief_trace(proposal_id, date_str)
    artifact_obj = OntologyObj(
        type_name="KnowledgeArtifact",
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
            "cause_id": OPERATOR_BRIEF_CAUSE_ID,
            "cell_id": cell_id,
            "movement_kind": OPERATOR_BRIEF_CELL_KIND,
            "trace_id": trace_id,
            "trace_id_source": trace_id_source,
            "cited_fact_ids": list(drafted.cited_fact_ids),
        },
        created_by="operator_brief",
    )

    artifact_id = artifact_obj.id

    # Build markdown body with frontmatter that records full lineage.
    frontmatter = (
        "---\n"
        f"artifact_id: {artifact_id}\n"
        f"agent_id: {agent_id}\n"
        f"proposal_id: {proposal_id}\n"
        f"cause_id: {OPERATOR_BRIEF_CAUSE_ID}\n"
        f"cell_id: {cell_id}\n"
        f"trace_id: {trace_id}\n"
        f"trace_id_source: {trace_id_source}\n"
        f"brief_date: {date_str}\n"
        f"cited_fact_ids: [{', '.join(drafted.cited_fact_ids)}]\n"
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

    runtime_error = _record_runtime_artifact(
        runtime_state,
        artifact_id=artifact_id,
        file_path=file_path,
        content_hash=content_hash,
        date_str=date_str,
        proposal_id=proposal_id,
        cell_id=cell_id,
        trace_id=trace_id,
        trace_id_source=trace_id_source,
        brief_input=brief_input,
        gate_decision_ids=gate_decision_ids,
        witness_log_ids=witness_log_ids,
    )
    if runtime_error is not None:
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("failed to clean orphan operator brief file", exc_info=True)
        return None, "", f"Runtime artifact record failed: {runtime_error}"

    inserted, errors = reg.put_object(artifact_obj, updated_by="operator_brief")
    if inserted is None:
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("failed to clean orphan operator brief file", exc_info=True)
        return None, "", f"KnowledgeArtifact creation failed: {errors}"
    return artifact_id, content_hash, None


def _ensure_operator_brief_cell(reg: OntologyRegistry) -> OntologyObj | None:
    for obj in reg.get_objects_by_type("VentureCell"):
        if (
            obj.properties.get("cause_id") == OPERATOR_BRIEF_CAUSE_ID
            or obj.properties.get("name") == OPERATOR_BRIEF_CELL_NAME
        ):
            return obj

    obj, errors = reg.create_object(
        "VentureCell",
        properties={
            "name": OPERATOR_BRIEF_CELL_NAME,
            "description": (
                "Existing VentureCell container for the first "
                "ontology-native Operator Brief cause; not a Movement engine."
            ),
            "domain": "governance",
            "autonomy_stage": 1,
            "status": "active",
            "budget_tokens": 0,
            "kpis": {
                "artifact_subtype": ARTIFACT_SUBTYPE,
                "phase": "operator_brief_v0",
            },
            "cause_id": OPERATOR_BRIEF_CAUSE_ID,
            "movement_kind": OPERATOR_BRIEF_CELL_KIND,
        },
        created_by="operator_brief",
    )
    if obj is None:
        logger.warning("operator brief VentureCell creation failed: %s", errors)
    return obj


def _backfill_existing_runtime_artifact(
    runtime_state: RuntimeStateStore | None,
    *,
    existing: OntologyObj | None,
    date_str: str,
    cell_id: str,
    brief_input: _BriefInput | None = None,
    gate_decision_ids: list[str] | None = None,
    witness_log_ids: list[str] | None = None,
    outcome_id: str = "",
    value_event_id: str | None = None,
) -> str | None:
    if runtime_state is None or existing is None:
        return None
    file_path_str = str(existing.properties.get("file_path") or "")
    content_hash = str(existing.properties.get("content_sha256") or "")
    if not file_path_str or not content_hash:
        return None
    trace_id = str(existing.properties.get("trace_id") or "")
    trace_id_source = str(existing.properties.get("trace_id_source") or "")
    if not trace_id:
        trace_id, trace_id_source = _operator_brief_trace(
            str(existing.properties.get("provenance") or ""),
            date_str,
        )
    error = _record_runtime_artifact(
        runtime_state,
        artifact_id=existing.id,
        file_path=Path(file_path_str),
        content_hash=content_hash,
        date_str=date_str,
        proposal_id=str(existing.properties.get("provenance") or ""),
        cell_id=cell_id or str(existing.properties.get("cell_id") or ""),
        trace_id=trace_id,
        trace_id_source=trace_id_source,
        brief_input=brief_input,
        gate_decision_ids=gate_decision_ids or [],
        witness_log_ids=witness_log_ids or [],
        outcome_id=outcome_id,
        value_event_id=value_event_id or "",
    )
    if error is not None:
        logger.warning("operator_brief runtime artifact backfill failed: %s", error)
        return None
    return existing.id


def _record_runtime_artifact(
    runtime_state: RuntimeStateStore | None,
    *,
    artifact_id: str,
    file_path: Path,
    content_hash: str,
    date_str: str,
    proposal_id: str,
    cell_id: str,
    trace_id: str,
    trace_id_source: str,
    brief_input: _BriefInput | None,
    gate_decision_ids: list[str],
    witness_log_ids: list[str],
    outcome_id: str = "",
    value_event_id: str = "",
) -> str | None:
    if runtime_state is None:
        return None
    if not file_path.exists():
        return f"missing artifact payload: {file_path}"

    cited_fact_ids = list(brief_input.cited_fact_ids) if brief_input else []
    source_event_ids = list(brief_input.source_event_ids) if brief_input else []
    memory_fact_ids = list(brief_input.memory_fact_ids) if brief_input else []
    source_session_ids = list(brief_input.source_session_ids) if brief_input else []
    session_id = source_session_ids[0] if source_session_ids else "operator_brief"
    record = ArtifactRecord(
        artifact_id=artifact_id,
        artifact_kind=ARTIFACT_SUBTYPE,
        session_id=session_id,
        task_id=f"operator_brief::{proposal_id or date_str}",
        payload_path=str(file_path),
        checksum=content_hash,
        promotion_state="published",
        metadata={
            "subtype": ARTIFACT_SUBTYPE,
            "cause_id": OPERATOR_BRIEF_CAUSE_ID,
            "cell_id": cell_id,
            "movement_kind": OPERATOR_BRIEF_CELL_KIND,
            "trace_id": trace_id,
            "trace_id_source": trace_id_source,
            "proposal_id": proposal_id,
            "outcome_id": outcome_id,
            "value_event_id": value_event_id,
            "brief_date": date_str,
            "cited_fact_ids": cited_fact_ids,
            "source_event_ids": source_event_ids,
            "memory_fact_ids": memory_fact_ids,
            "gate_decision_ids": list(gate_decision_ids),
            "witness_log_ids": list(witness_log_ids),
            "content_sha256": content_hash,
        },
    )
    try:
        _run_async_sync(lambda: runtime_state.record_artifact(record))
    except Exception as exc:
        return str(exc)
    return None


def _run_async_sync(factory):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    raise RuntimeError("operator_brief sync entrypoint cannot await inside a running loop")
