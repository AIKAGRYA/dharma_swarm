"""Read-only operator control-surface projection.

This module reconciles existing runtime, telemetry, governance, memory, and
writer-inventory signals into typed rows for the operator cockpit. It does not
own state and must not initialize schemas, dispatch work, promote memory, or
write observations.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROW_KINDS = (
    "runtime_session",
    "task_claim",
    "delegation_run",
    "artifact",
    "memory_fact",
    "context_bundle",
    "operator_action",
    "session_event",
    "routing_decision",
    "provider_attempt",
    "policy_decision",
    "intervention_outcome",
    "external_outcome",
    "governance_check",
    "memory_surface",
    "memory_writer",
    "source_failure",
)

COHERENCE_STATES = ("bound", "partial", "drifted", "declared_only", "unknown")
PRIORITIES = ("p0", "p1", "p2", "backlog", "unknown")
AUTHORITY_ROLES = (
    "canonical_runtime",
    "telemetry_evidence",
    "governance_evidence",
    "memory_projection",
    "writer_inventory",
    "projection",
    "unknown",
)


@dataclass(frozen=True)
class EvidenceRef:
    """A stable pointer to evidence without copying heavy/private content."""

    evidence_id: str
    kind: str
    source: str
    ref: str
    observed_at: str = ""
    confidence: float | None = None
    redacted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ControlSurfaceRow:
    """One read-only operator cockpit row."""

    id: str
    kind: str
    label: str
    status: str = "unknown"
    priority: str = "unknown"
    authority_role: str = "unknown"
    truth_owner: str = ""
    coherence_state: str = "unknown"
    freshness: str = ""
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    gap_codes: list[str] = field(default_factory=list)
    next_action: str = ""
    human_decision_required: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_refs"] = [ref.to_dict() for ref in self.evidence_refs]
        return payload


@dataclass(frozen=True)
class ControlSurfaceQuery:
    kind: str | None = None
    priority: str | None = None
    coherence_state: str | None = None
    human_decision_required: bool | None = None
    stale: bool | None = None
    source: str | None = None
    limit: int = 250
    cursor: str | None = None


@dataclass(frozen=True)
class ControlSurfacePage:
    items: tuple[ControlSurfaceRow, ...]
    limit: int
    next_cursor: str | None = None
    total_before_page: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "page": {
                "limit": self.limit,
                "next_cursor": self.next_cursor,
                "total_before_page": self.total_before_page,
            },
        }


def build_control_surface_rows(
    *,
    repo_root: Path | str | None = None,
    runtime_db: Path | str | None = None,
    include_memory: bool = True,
    include_writers: bool = True,
    per_source_limit: int = 50,
) -> list[ControlSurfaceRow]:
    root = _repo_root(repo_root)
    db_path = Path(runtime_db).expanduser() if runtime_db is not None else _default_runtime_db()
    rows: list[ControlSurfaceRow] = []

    for builder in (
        lambda: _runtime_rows(db_path, per_source_limit),
        lambda: _telemetry_rows(db_path, per_source_limit),
        lambda: _governance_rows(root),
        lambda: _memory_surface_rows(root, include_memory),
        lambda: _writer_rows(root, include_writers),
    ):
        try:
            rows.extend(builder())
        except Exception as exc:
            rows.append(_source_failure_row(builder, exc))

    rows.sort(key=lambda row: (_priority_rank(row.priority), row.kind, row.id))
    return rows


def build_control_surface_page(
    *,
    query: ControlSurfaceQuery | None = None,
    rows: Iterable[ControlSurfaceRow] | None = None,
    repo_root: Path | str | None = None,
    runtime_db: Path | str | None = None,
) -> ControlSurfacePage:
    resolved = query or ControlSurfaceQuery()
    all_rows = list(rows) if rows is not None else build_control_surface_rows(
        repo_root=repo_root,
        runtime_db=runtime_db,
    )
    filtered = [row for row in all_rows if _matches_query(row, resolved)]
    start = 0
    if resolved.cursor:
        ids = [row.id for row in filtered]
        if resolved.cursor in ids:
            start = ids.index(resolved.cursor) + 1
    limit = max(1, min(resolved.limit, 1000))
    page_items = tuple(filtered[start : start + limit])
    next_cursor = page_items[-1].id if start + limit < len(filtered) and page_items else None
    return ControlSurfacePage(
        items=page_items,
        limit=limit,
        next_cursor=next_cursor,
        total_before_page=len(filtered),
    )


def build_control_surface_summary(
    rows: Iterable[ControlSurfaceRow] | None = None,
    *,
    repo_root: Path | str | None = None,
    runtime_db: Path | str | None = None,
) -> dict[str, Any]:
    all_rows = list(rows) if rows is not None else build_control_surface_rows(
        repo_root=repo_root,
        runtime_db=runtime_db,
    )
    by_coherence = {state: 0 for state in COHERENCE_STATES}
    by_priority = {priority: 0 for priority in PRIORITIES}
    by_kind: dict[str, int] = {}
    for row in all_rows:
        by_coherence[row.coherence_state if row.coherence_state in by_coherence else "unknown"] += 1
        by_priority[row.priority if row.priority in by_priority else "unknown"] += 1
        by_kind[row.kind] = by_kind.get(row.kind, 0) + 1
    return {
        "total": len(all_rows),
        "by_coherence": by_coherence,
        "by_priority": by_priority,
        "by_kind": by_kind,
        "human_decision_required_count": sum(1 for row in all_rows if row.human_decision_required),
        "source_failure_count": sum(1 for row in all_rows if row.kind == "source_failure"),
        "stale_count": sum(1 for row in all_rows if "stale" in row.gap_codes),
        "generated_at": _now_iso(),
        "sources_consulted": (
            "runtime_state",
            "telemetry_plane",
            "governance",
            "memory_kernel",
            "memory_writer_sentinel",
        ),
    }


def find_control_surface_row(
    row_id: str,
    *,
    rows: Iterable[ControlSurfaceRow] | None = None,
    repo_root: Path | str | None = None,
    runtime_db: Path | str | None = None,
) -> ControlSurfaceRow | None:
    for row in list(rows) if rows is not None else build_control_surface_rows(
        repo_root=repo_root,
        runtime_db=runtime_db,
    ):
        if row.id == row_id:
            return row
    return None


def find_evidence_ref(
    evidence_id: str,
    *,
    rows: Iterable[ControlSurfaceRow] | None = None,
    repo_root: Path | str | None = None,
    runtime_db: Path | str | None = None,
) -> EvidenceRef | None:
    for row in list(rows) if rows is not None else build_control_surface_rows(
        repo_root=repo_root,
        runtime_db=runtime_db,
    ):
        for ref in row.evidence_refs:
            if ref.evidence_id == evidence_id:
                return ref
    return None


def _runtime_rows(db_path: Path, limit: int) -> list[ControlSurfaceRow]:
    rows: list[ControlSurfaceRow] = []
    if not db_path.exists():
        return [_missing_store_row("runtime_state", db_path, "runtime_store_missing")]
    with _readonly_db(db_path) as db:
        rows.extend(_table_rows(db, "sessions", "updated_at", limit, _session_row))
        rows.extend(_table_rows(db, "task_claims", "claimed_at", limit, _claim_row))
        rows.extend(_table_rows(db, "delegation_runs", "started_at", limit, _run_row))
        rows.extend(_table_rows(db, "artifact_records", "created_at", limit, _artifact_row))
        rows.extend(_table_rows(db, "memory_facts", "updated_at", limit, _memory_fact_row))
        rows.extend(_table_rows(db, "context_bundles", "created_at", limit, _context_bundle_row))
        rows.extend(_table_rows(db, "operator_actions", "created_at", limit, _operator_action_row))
        rows.extend(_table_rows(db, "session_events", "created_at", limit, _session_event_row))
    return rows


def _telemetry_rows(db_path: Path, limit: int) -> list[ControlSurfaceRow]:
    if not db_path.exists():
        return []
    rows: list[ControlSurfaceRow] = []
    with _readonly_db(db_path) as db:
        rows.extend(_table_rows(db, "routing_decisions", "created_at", limit, _routing_decision_row))
        rows.extend(_table_rows(db, "provider_attempts", "created_at", limit, _provider_attempt_row))
        rows.extend(_table_rows(db, "policy_decisions", "created_at", limit, _policy_decision_row))
        rows.extend(_table_rows(db, "intervention_outcomes", "created_at", limit, _intervention_row))
        rows.extend(_table_rows(db, "external_outcomes", "created_at", limit, _external_outcome_row))
    return rows


def _governance_rows(repo_root: Path) -> list[ControlSurfaceRow]:
    rows = [
        _path_health_row(repo_root, "governance.active_surface_manifest", "ACTIVE_SURFACE_MANIFEST.yaml", "p0"),
        _path_health_row(repo_root, "governance.broken_register", "docs/state/BROKEN_REGISTER.md", "p0"),
        _path_health_row(repo_root, "governance.sovereign_manifest", "docs/governance/SOVEREIGN_MANIFEST.md", "p1"),
        _path_health_row(repo_root, "governance.agent_online", "docs/governance/AGENT_ONLINE.md", "p1"),
    ]
    interop_router = repo_root / "api" / "routers" / "interop.py"
    api_main = repo_root / "api" / "main.py"
    if interop_router.exists():
        registered = api_main.exists() and "interop" in api_main.read_text(encoding="utf-8", errors="ignore")
        rows.append(ControlSurfaceRow(
            id="governance.router.interop",
            kind="governance_check",
            label="Interop router registration",
            status="registered" if registered else "unregistered",
            priority="p1" if registered else "p0",
            authority_role="governance_evidence",
            truth_owner="api/main.py",
            coherence_state="bound" if registered else "drifted",
            evidence_refs=[_file_ref(repo_root, interop_router, "governance", "interop router exists")],
            source_refs=["api/routers/interop.py", "api/main.py"],
            gap_codes=[] if registered else ["router_not_registered"],
            next_action="" if registered else "Register api.routers.interop or remove the advertised surface.",
            human_decision_required=not registered,
        ))
    return rows


def _memory_surface_rows(repo_root: Path, enabled: bool) -> list[ControlSurfaceRow]:
    if not enabled:
        return []
    try:
        from dharma_swarm.memory_kernel import MemoryKernel
    except Exception as exc:
        return [_source_failure_row("memory_kernel", exc)]
    try:
        kernel = MemoryKernel()
        health = kernel.summarize_surface_health()
        surfaces = kernel.list_surfaces()
    except Exception as exc:
        return [_source_failure_row("memory_kernel", exc)]
    rows: list[ControlSurfaceRow] = []
    for surface in surfaces:
        exists = bool(getattr(surface.health, "exists", False))
        surface_id = str(getattr(surface, "surface_id", "unknown"))
        role = str(getattr(surface, "role", "unknown"))
        rows.append(ControlSurfaceRow(
            id=f"memory_surface.{surface_id}",
            kind="memory_surface",
            label=surface_id,
            status="present" if exists else "missing",
            priority="p1" if exists else "p2",
            authority_role="memory_projection",
            truth_owner="MemoryKernel",
            coherence_state="bound" if exists else "declared_only",
            evidence_refs=[EvidenceRef(
                evidence_id=_stable_id("evidence", "memory_surface", surface_id),
                kind="memory_surface",
                source="MemoryKernel",
                ref=surface_id,
                metadata={"role": role},
            )],
            source_refs=[str(getattr(surface, "path", ""))],
            raw={"surface": _json_safe(surface), "summary": health},
        ))
    return rows


def _writer_rows(repo_root: Path, enabled: bool) -> list[ControlSurfaceRow]:
    if not enabled:
        return []
    try:
        from dharma_swarm.memory_kernel.writers import MemoryWriterSentinel
    except Exception as exc:
        return [_source_failure_row("memory_writer_sentinel", exc)]
    try:
        sentinel = MemoryWriterSentinel(repo_root=repo_root)
        observations = sentinel.run()
    except Exception as exc:
        return [_source_failure_row("memory_writer_sentinel", exc)]
    rows: list[ControlSurfaceRow] = []
    for observation in observations:
        writer = observation.spec
        status = observation.status.value
        needs_human = writer.classification.value in {"review_required", "unsafe"} or status != "present"
        rows.append(ControlSurfaceRow(
            id=f"memory_writer.{writer.writer_id}",
            kind="memory_writer",
            label=writer.writer_id,
            status=status,
            priority=_risk_priority(writer.risk.value),
            authority_role="writer_inventory",
            truth_owner="MemoryWriterSentinel",
            coherence_state="bound" if status == "present" else "partial",
            evidence_refs=[EvidenceRef(
                evidence_id=_stable_id("evidence", "memory_writer", writer.writer_id),
                kind="writer_spec",
                source="MemoryWriterSentinel",
                ref=writer.symbol,
                metadata=observation.to_json(),
            )],
            source_refs=[observation.source_path],
            gap_codes=[status] if status != "present" else [],
            next_action="Review write path before claiming central control." if needs_human else "",
            human_decision_required=needs_human,
            raw=observation.to_json(),
        ))
    return rows


def _table_rows(
    db: sqlite3.Connection,
    table: str,
    order_column: str,
    limit: int,
    mapper,
) -> list[ControlSurfaceRow]:
    if not _table_exists(db, table):
        return []
    columns = _table_columns(db, table)
    order = order_column if order_column in columns else columns[0]
    query = f"SELECT * FROM {table} ORDER BY {order} DESC LIMIT ?"  # noqa: S608
    return [mapper(_row_dict(row)) for row in db.execute(query, (max(1, limit),)).fetchall()]


def _session_row(row: dict[str, Any]) -> ControlSurfaceRow:
    sid = _str(row.get("session_id"))
    return _runtime_row(
        row_id=f"runtime_session.{sid}",
        kind="runtime_session",
        label=f"Session {sid}",
        status=_str(row.get("status")),
        freshness=_str(row.get("updated_at")),
        evidence_ref=f"runtime_state:sessions:{sid}",
        raw=row,
    )


def _claim_row(row: dict[str, Any]) -> ControlSurfaceRow:
    claim_id = _str(row.get("claim_id"))
    status = _str(row.get("status"))
    return _runtime_row(
        row_id=f"task_claim.{claim_id}",
        kind="task_claim",
        label=f"{_str(row.get('agent_id'))} claim {_str(row.get('task_id'))}",
        status=status,
        priority="p1" if status in {"claimed", "in_progress"} else "p2",
        freshness=_str(row.get("heartbeat_at") or row.get("acked_at") or row.get("claimed_at")),
        evidence_ref=f"runtime_state:task_claims:{claim_id}",
        raw=row,
    )


def _run_row(row: dict[str, Any]) -> ControlSurfaceRow:
    run_id = _str(row.get("run_id"))
    status = _str(row.get("status"))
    failed = status in {"failed", "error", "stale_recovered"}
    return _runtime_row(
        row_id=f"delegation_run.{run_id}",
        kind="delegation_run",
        label=f"{_str(row.get('assigned_to'))} run {_str(row.get('task_id'))}",
        status=status,
        priority="p0" if failed else "p1",
        coherence_state="drifted" if failed else "bound",
        gap_codes=["run_failed"] if failed else [],
        freshness=_str(row.get("completed_at") or row.get("started_at")),
        evidence_ref=f"runtime_state:delegation_runs:{run_id}",
        raw=row,
    )


def _artifact_row(row: dict[str, Any]) -> ControlSurfaceRow:
    artifact_id = _str(row.get("artifact_id"))
    return _runtime_row(
        row_id=f"artifact.{artifact_id}",
        kind="artifact",
        label=f"{_str(row.get('artifact_kind'))} {artifact_id}",
        status=_str(row.get("promotion_state")),
        priority="p2",
        freshness=_str(row.get("created_at")),
        evidence_ref=f"runtime_state:artifact_records:{artifact_id}",
        raw=row,
    )


def _memory_fact_row(row: dict[str, Any]) -> ControlSurfaceRow:
    fact_id = _str(row.get("fact_id"))
    truth = _str(row.get("truth_state"))
    return _runtime_row(
        row_id=f"memory_fact.{fact_id}",
        kind="memory_fact",
        label=f"{_str(row.get('fact_kind'))} fact",
        status=truth,
        priority="p1" if truth == "promoted" else "p2",
        freshness=_str(row.get("updated_at")),
        evidence_ref=f"runtime_state:memory_facts:{fact_id}",
        raw={k: v for k, v in row.items() if k != "text"},
        source_refs=[_str(row.get("source_event_id")), _str(row.get("source_artifact_id"))],
    )


def _context_bundle_row(row: dict[str, Any]) -> ControlSurfaceRow:
    bundle_id = _str(row.get("bundle_id"))
    return _runtime_row(
        row_id=f"context_bundle.{bundle_id}",
        kind="context_bundle",
        label=f"Context bundle {bundle_id}",
        status="recorded",
        priority="p2",
        freshness=_str(row.get("created_at")),
        evidence_ref=f"runtime_state:context_bundles:{bundle_id}",
        raw={k: v for k, v in row.items() if k != "rendered_text"},
    )


def _operator_action_row(row: dict[str, Any]) -> ControlSurfaceRow:
    action_id = _str(row.get("action_id"))
    return _runtime_row(
        row_id=f"operator_action.{action_id}",
        kind="operator_action",
        label=_str(row.get("action_name")),
        status="recorded",
        priority="p1",
        freshness=_str(row.get("created_at")),
        evidence_ref=f"runtime_state:operator_actions:{action_id}",
        raw=row,
    )


def _session_event_row(row: dict[str, Any]) -> ControlSurfaceRow:
    event_id = _str(row.get("event_id"))
    return _runtime_row(
        row_id=f"session_event.{event_id}",
        kind="session_event",
        label=_str(row.get("event_name")),
        status=_str(row.get("ledger_kind")),
        priority="p2",
        freshness=_str(row.get("created_at")),
        evidence_ref=f"runtime_state:session_events:{event_id}",
        raw={k: v for k, v in row.items() if k != "event_text"},
    )


def _routing_decision_row(row: dict[str, Any]) -> ControlSurfaceRow:
    decision_id = _str(row.get("decision_id"))
    outcome = _str(row.get("outcome") or "unknown")
    failed = outcome in {"all_failed", "timeout", "gate_block", "no_route", "empty_content"}
    return _telemetry_row(
        row_id=f"routing_decision.{decision_id}",
        kind="routing_decision",
        label=f"{_str(row.get('selected_provider'))} {_str(row.get('action_name'))}",
        status=outcome,
        priority="p0" if failed or bool(row.get("requires_human")) else "p1",
        coherence_state="drifted" if failed else "bound",
        gap_codes=[f"routing_outcome:{outcome}"] if failed else [],
        human=bool(row.get("requires_human")),
        freshness=_str(row.get("created_at")),
        evidence_ref=f"telemetry:routing_decisions:{decision_id}",
        raw=row,
    )


def _provider_attempt_row(row: dict[str, Any]) -> ControlSurfaceRow:
    decision_id = _str(row.get("decision_id"))
    idx = _str(row.get("attempt_idx"))
    success = bool(row.get("success"))
    return _telemetry_row(
        row_id=f"provider_attempt.{decision_id}.{idx}",
        kind="provider_attempt",
        label=f"{_str(row.get('provider'))} attempt {idx}",
        status="success" if success else _str(row.get("outcome") or row.get("error_class") or "failed"),
        priority="p2" if success else "p1",
        coherence_state="bound" if success else "partial",
        gap_codes=[] if success else [f"provider_error:{_str(row.get('error_class') or 'unknown')}"],
        freshness=_str(row.get("created_at")),
        evidence_ref=f"telemetry:provider_attempts:{decision_id}:{idx}",
        raw={k: v for k, v in row.items() if k != "error_detail"},
    )


def _policy_decision_row(row: dict[str, Any]) -> ControlSurfaceRow:
    decision_id = _str(row.get("decision_id"))
    return _telemetry_row(
        row_id=f"policy_decision.{decision_id}",
        kind="policy_decision",
        label=_str(row.get("policy_name")),
        status=_str(row.get("decision")),
        priority="p1",
        freshness=_str(row.get("created_at")),
        evidence_ref=f"telemetry:policy_decisions:{decision_id}",
        raw=row,
    )


def _intervention_row(row: dict[str, Any]) -> ControlSurfaceRow:
    intervention_id = _str(row.get("intervention_id"))
    return _telemetry_row(
        row_id=f"intervention_outcome.{intervention_id}",
        kind="intervention_outcome",
        label=_str(row.get("intervention_type")),
        status=_str(row.get("outcome_status")),
        priority="p1",
        freshness=_str(row.get("created_at")),
        evidence_ref=f"telemetry:intervention_outcomes:{intervention_id}",
        raw=row,
    )


def _external_outcome_row(row: dict[str, Any]) -> ControlSurfaceRow:
    outcome_id = _str(row.get("outcome_id"))
    return _telemetry_row(
        row_id=f"external_outcome.{outcome_id}",
        kind="external_outcome",
        label=_str(row.get("outcome_kind")),
        status=_str(row.get("status")),
        priority="p2",
        freshness=_str(row.get("created_at")),
        evidence_ref=f"telemetry:external_outcomes:{outcome_id}",
        raw=row,
    )


def _runtime_row(
    *,
    row_id: str,
    kind: str,
    label: str,
    status: str,
    freshness: str,
    evidence_ref: str,
    raw: dict[str, Any],
    priority: str = "p1",
    coherence_state: str = "bound",
    gap_codes: list[str] | None = None,
    source_refs: list[str] | None = None,
) -> ControlSurfaceRow:
    return ControlSurfaceRow(
        id=row_id,
        kind=kind,
        label=label,
        status=status or "unknown",
        priority=priority,
        authority_role="canonical_runtime",
        truth_owner="RuntimeStateStore",
        coherence_state=coherence_state,
        freshness=freshness,
        evidence_refs=[_db_ref(evidence_ref, "runtime_state", freshness)],
        source_refs=[ref for ref in (source_refs or ["~/.dharma/state/runtime.db"]) if ref],
        gap_codes=gap_codes or [],
        human_decision_required=priority == "p0",
        raw=raw,
    )


def _telemetry_row(
    *,
    row_id: str,
    kind: str,
    label: str,
    status: str,
    freshness: str,
    evidence_ref: str,
    raw: dict[str, Any],
    priority: str = "p1",
    coherence_state: str = "bound",
    gap_codes: list[str] | None = None,
    human: bool = False,
) -> ControlSurfaceRow:
    return ControlSurfaceRow(
        id=row_id,
        kind=kind,
        label=label,
        status=status or "unknown",
        priority=priority,
        authority_role="telemetry_evidence",
        truth_owner="TelemetryPlaneStore",
        coherence_state=coherence_state,
        freshness=freshness,
        evidence_refs=[_db_ref(evidence_ref, "telemetry", freshness)],
        source_refs=["~/.dharma/state/runtime.db"],
        gap_codes=gap_codes or [],
        human_decision_required=human or priority == "p0",
        raw=raw,
    )


def _path_health_row(repo_root: Path, row_id: str, rel_path: str, priority: str) -> ControlSurfaceRow:
    path = repo_root / rel_path
    exists = path.exists()
    freshness = _mtime_iso(path) if exists else ""
    return ControlSurfaceRow(
        id=row_id,
        kind="governance_check",
        label=rel_path,
        status="present" if exists else "missing",
        priority=priority if not exists else "p2",
        authority_role="governance_evidence",
        truth_owner=rel_path,
        coherence_state="bound" if exists else "drifted",
        freshness=freshness,
        evidence_refs=[_file_ref(repo_root, path, "governance", rel_path)],
        source_refs=[rel_path],
        gap_codes=[] if exists else ["governance_file_missing"],
        human_decision_required=not exists and priority == "p0",
    )


def _missing_store_row(owner: str, db_path: Path, gap_code: str) -> ControlSurfaceRow:
    return ControlSurfaceRow(
        id=f"source_failure.{owner}.missing",
        kind="source_failure",
        label=f"{owner} store missing",
        status="missing",
        priority="p1",
        authority_role="projection",
        truth_owner=owner,
        coherence_state="partial",
        evidence_refs=[EvidenceRef(
            evidence_id=_stable_id("evidence", owner, str(db_path)),
            kind="missing_store",
            source=owner,
            ref=str(db_path),
        )],
        source_refs=[str(db_path)],
        gap_codes=[gap_code],
        next_action="Start the runtime or point the projector at the correct DB.",
    )


def _source_failure_row(source: object, exc: BaseException) -> ControlSurfaceRow:
    label = source if isinstance(source, str) else getattr(source, "__name__", repr(source))
    return ControlSurfaceRow(
        id=f"source_failure.{_slug(str(label))}",
        kind="source_failure",
        label=f"{label} failed",
        status="error",
        priority="p1",
        authority_role="projection",
        truth_owner=str(label),
        coherence_state="partial",
        evidence_refs=[EvidenceRef(
            evidence_id=_stable_id("evidence", "source_failure", str(label), str(exc)),
            kind="source_failure",
            source=str(label),
            ref=type(exc).__name__,
            metadata={"error": str(exc)},
        )],
        gap_codes=["source_adapter_failed"],
        next_action="Inspect source adapter failure before trusting this slice.",
        raw={"error": str(exc), "error_type": type(exc).__name__},
    )


def _readonly_db(path: Path) -> sqlite3.Connection:
    uri_path = path.resolve().as_posix()
    db = sqlite3.connect(f"file:{uri_path}?mode=ro&immutable=1", uri=True, timeout=1.0)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


def _table_exists(db: sqlite3.Connection, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(db: sqlite3.Connection, table: str) -> list[str]:
    return [str(row["name"]) for row in db.execute(f"PRAGMA table_info({table})").fetchall()]  # noqa: S608


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in row.keys():
        payload[key] = _json_maybe(row[key])
    return payload


def _json_maybe(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in "{[":
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _db_ref(ref: str, source: str, observed_at: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=_stable_id("evidence", ref),
        kind="db_row",
        source=source,
        ref=ref,
        observed_at=observed_at,
        redacted=True,
    )


def _file_ref(repo_root: Path, path: Path, kind: str, label: str) -> EvidenceRef:
    try:
        rendered = path.relative_to(repo_root).as_posix()
    except ValueError:
        rendered = path.as_posix()
    return EvidenceRef(
        evidence_id=_stable_id("evidence", "file", rendered),
        kind=kind,
        source="filesystem",
        ref=rendered,
        observed_at=_mtime_iso(path) if path.exists() else "",
        metadata={"label": label, "exists": path.exists()},
    )


def _matches_query(row: ControlSurfaceRow, query: ControlSurfaceQuery) -> bool:
    if query.kind and row.kind != query.kind:
        return False
    if query.priority and row.priority != query.priority:
        return False
    if query.coherence_state and row.coherence_state != query.coherence_state:
        return False
    if query.human_decision_required is not None and row.human_decision_required != query.human_decision_required:
        return False
    if query.stale is not None and ("stale" in row.gap_codes) != query.stale:
        return False
    if query.source and query.source not in row.truth_owner and not any(query.source in ref.source for ref in row.evidence_refs):
        return False
    return True


def _repo_root(repo_root: Path | str | None = None) -> Path:
    if repo_root is not None:
        return Path(repo_root).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "ACTIVE_SURFACE_MANIFEST.yaml").exists():
            return parent
    return Path.cwd().resolve()


def _default_runtime_db() -> Path:
    return Path.home() / ".dharma" / "state" / "runtime.db"


def _mtime_iso(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
    except OSError:
        return ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value.lower()).strip("_") or "unknown"


def _stable_id(*parts: object) -> str:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return "_".join([_slug(str(parts[0])), digest]) if parts else digest


def _priority_rank(priority: str) -> int:
    return {"p0": 0, "p1": 1, "p2": 2, "backlog": 3, "unknown": 4}.get(priority, 4)


def _risk_priority(risk: str) -> str:
    return {"critical": "p0", "high": "p1", "medium": "p2", "low": "backlog"}.get(risk, "unknown")


def _json_safe(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "to_json"):
        return value.to_json()
    if hasattr(value, "__dict__"):
        return {
            key: _json_safe(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
