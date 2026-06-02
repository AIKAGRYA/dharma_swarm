"""Build a read-only VentureCell Operator OS projection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from dharma_swarm.chetana import staging as chetana_staging
from dharma_swarm.operator_core.a2a_task_lifecycle import read_queue, task_lifecycle_state
from dharma_swarm.operator_core.governed_work_admission import (
    GovernedWorkRequest,
    WorkKind,
    evaluate_governed_work_admission,
)
from dharma_swarm.venture_cell.darshan.bundle import validate_bundle
from dharma_swarm.venture_cell.darshan.external_reader_gate import (
    latest_darshan_bundle_path,
    validate_external_reader_gate_summary,
)
from dharma_swarm.venture_cell.darshan.schema import DecisionDelta, PolsiaHandoff
from dharma_swarm.venture_cell.operator_os.schema import (
    CanvasItem,
    GateSummary,
    MemoryKernelSnapshot,
    OperatorDepartment,
    VentureCellOperatorProjection,
)


@dataclass(frozen=True)
class OperatorOSInputs:
    """Explicit inputs for the read-only Operator OS projection."""

    venture_cell_id: str = "DARSHAN"
    bundle_path: Path | None = None
    task_board_tasks: Sequence[Any] = ()
    a2a_tasks: Sequence[Mapping[str, Any]] | None = None
    state_root: Path | str | None = None
    staging_root: Path | None = None
    trusted_root: Path | None = None
    quarantine_root: Path | None = None
    mission_contract_present: bool = True
    workspace_lease_present: bool = True
    context_quorum_ok: bool = True
    max_memory_scan: int = 5000


def build_operator_projection(inputs: OperatorOSInputs | None = None) -> VentureCellOperatorProjection:
    """Project existing DS evidence into a company-OS shape."""

    active = inputs or OperatorOSInputs()
    selected_bundle = active.bundle_path or latest_darshan_bundle_path()
    bundle = _bundle_context(selected_bundle)
    gate = _external_reader_gate(selected_bundle)
    memory = build_memory_kernel_snapshot(
        staging_root=active.staging_root,
        trusted_root=active.trusted_root,
        quarantine_root=active.quarantine_root,
        max_scan=active.max_memory_scan,
    )
    admission = _work_admission_gate(active)
    a2a_rows = _a2a_rows(active)
    canvas = tuple(
        [
            *_bundle_canvas_items(bundle),
            *_task_board_canvas_items(active.task_board_tasks),
            *_a2a_canvas_items(a2a_rows),
        ]
    )
    gates = (gate, admission)
    departments = _department_roster(gate, memory)
    status = _projection_status(bundle, gate, canvas)
    autonomy_level = _autonomy_level(gate, admission, canvas)
    gaps = _gap_codes(bundle, gate, admission, memory, canvas)
    next_actions = _next_actions(gaps)

    return VentureCellOperatorProjection(
        venture_cell_id=active.venture_cell_id,
        title=bundle["title"] or active.venture_cell_id,
        artifact_id=bundle["artifact_id"],
        status=status,
        autonomy_level=autonomy_level,
        company_profile={
            "venture_cell_id": active.venture_cell_id,
            "title": bundle["title"] or active.venture_cell_id,
            "artifact_id": bundle["artifact_id"],
            "blueprint": "Cofounder shell + Polsia operating cycles + Dharma governance",
            "authority_boundary": "read_only_projection_until_gates_pass",
            "bundle_path": bundle["bundle_path"],
        },
        departments=departments,
        canvas=canvas,
        gates=gates,
        memory_kernel=memory,
        daily_cycle=_daily_cycle(),
        evidence_refs=tuple(ref for ref in _evidence_refs(bundle, gate, memory) if ref),
        gap_codes=gaps,
        next_actions=next_actions,
    )


def build_memory_kernel_snapshot(
    *,
    staging_root: Path | None = None,
    trusted_root: Path | None = None,
    quarantine_root: Path | None = None,
    max_scan: int = 5000,
) -> MemoryKernelSnapshot:
    """Summarize Chetana/wiki roots without promoting or mutating atoms."""

    staging_root = staging_root or chetana_staging.STAGING_ROOT
    trusted_root = trusted_root or chetana_staging.TRUSTED_DEFAULT
    quarantine_root = quarantine_root or chetana_staging.QUARANTINE_ROOT
    staged_count, staged_truncated = _bounded_md_count(staging_root, max_scan)
    trusted_count, trusted_truncated = _bounded_md_count(trusted_root, max_scan)
    quarantine_count, quarantine_truncated = _bounded_md_count(quarantine_root, max_scan)
    truncated = staged_truncated or trusted_truncated or quarantine_truncated
    roots = tuple(str(root) for root in (staging_root, trusted_root, quarantine_root))

    gap_codes: list[str] = []
    if staged_count == 0 and trusted_count == 0:
        status = "declared_only"
        gap_codes.append("memory_kernel_has_no_visible_atoms")
    elif trusted_count == 0:
        status = "staged_only"
        gap_codes.append("memory_kernel_trusted_projection_missing")
    elif truncated:
        status = "large_projection_needs_index"
        gap_codes.append("memory_kernel_query_index_missing")
    else:
        status = "projection_available"

    return MemoryKernelSnapshot(
        status=status,
        staged_count=staged_count,
        trusted_count=trusted_count,
        quarantine_count=quarantine_count,
        truncated=truncated,
        source_roots=roots,
        evidence_refs=tuple(root for root in roots if Path(root).exists()),
        gap_codes=tuple(gap_codes),
        next_action=(
            "Build a read-through MemoryKernel index over Chetana/wiki with provenance gates"
            if gap_codes
            else "Use this snapshot as the read-only memory substrate for Operator OS agents"
        ),
    )


def _bundle_context(bundle_path: Path | None) -> dict[str, Any]:
    if bundle_path is None:
        return {
            "valid": False,
            "bundle_path": "",
            "title": "",
            "artifact_id": "",
            "errors": ["bundle_path_missing"],
            "warnings": [],
            "decision_delta": None,
            "polsia_handoff": None,
        }
    result = validate_bundle(bundle_path)
    manifest = result.manifest
    decision_delta: DecisionDelta | None = None
    handoff: PolsiaHandoff | None = None
    if result.valid:
        decision_delta = DecisionDelta.model_validate(
            json.loads((result.bundle_path / "decision_delta.json").read_text(encoding="utf-8"))
        )
        handoff = PolsiaHandoff.model_validate(
            json.loads((result.bundle_path / "polsia_handoff.json").read_text(encoding="utf-8"))
        )
    return {
        "valid": result.valid,
        "bundle_path": str(result.bundle_path),
        "title": manifest.title if manifest else "",
        "artifact_id": manifest.artifact_id if manifest else "",
        "errors": list(result.errors),
        "warnings": list(result.warnings),
        "decision_delta": decision_delta,
        "polsia_handoff": handoff,
    }


def _external_reader_gate(bundle_path: Path | None) -> GateSummary:
    summary = validate_external_reader_gate_summary(bundle_path)
    decision = "allow" if summary["pass_gate"] else "block"
    return GateSummary(
        gate_id="darshan.external_reader_go_receipts",
        label="Darshan External Reader Go Receipt Gate",
        observed_state=str(summary["observed_state"]),
        coherence_state=str(summary["coherence_state"]),
        decision=decision,
        evidence_refs=tuple(str(ref) for ref in summary.get("receipt_paths", []) if ref),
        gap_codes=tuple(str(code) for code in summary.get("gap_codes", [])),
        next_action=(
            "Advance only after one accepted countable external-reader Go receipt"
            if not summary["pass_gate"]
            else "Keep the accepted receipt linked to decision_delta.json"
        ),
        raw=summary,
    )


def _work_admission_gate(inputs: OperatorOSInputs) -> GateSummary:
    admission = evaluate_governed_work_admission(
        GovernedWorkRequest(
            agent_uid="venturecell_operator_os",
            work_kind=WorkKind.LONG_RUNNING,
            intent="Run bounded VentureCell Operator OS build or planning work",
            risk_tier="Q2",
            autonomy_level="reviewed_internal",
            context_quorum_ok=inputs.context_quorum_ok,
            mission_contract_present=inputs.mission_contract_present,
            workspace_lease_present=inputs.workspace_lease_present,
            allowed_files=[
                "dharma_swarm/venture_cell/",
                "tests/",
                "reports/venture_operator_os/",
            ],
            forbidden_files=[
                "external_outreach",
                "payments",
                "deployment",
                "protected_merge",
            ],
        )
    )
    return GateSummary(
        gate_id="operator_os.governed_work_admission",
        label="Governed Work Admission",
        observed_state="mission contract present" if inputs.mission_contract_present else "mission contract missing",
        coherence_state="bound" if admission.decision == "allow" else "partial",
        decision=admission.decision,
        evidence_refs=("dharma_swarm/operator_core/governed_work_admission.py",),
        gap_codes=tuple(admission.reasons if admission.decision != "allow" else ()),
        next_action=(
            "Continue bounded internal build work with receipts"
            if admission.decision == "allow"
            else "Satisfy governed admission before widening autonomy"
        ),
        raw=admission.model_dump(mode="json"),
    )


def _department_roster(
    external_reader_gate: GateSummary,
    memory: MemoryKernelSnapshot,
) -> tuple[OperatorDepartment, ...]:
    reader_bound = external_reader_gate.decision == "allow"
    growth_status = "review_required" if reader_bound else "blocked_on_external_reader_gate"
    memory_status = "read_only_projection" if memory.trusted_count else "declared_only"
    return (
        OperatorDepartment(
            "strategy",
            "Strategy",
            "Polsia CEO/strategy cycle",
            "decision_delta.json + governed_work_admission",
            "review_required",
            status="bound",
            evidence_refs=("dharma_swarm/venture_cell/darshan/schema.py",),
            borrowed_from=("polsia", "cofounder"),
            next_action="Convert decision deltas into explicit next operating bets.",
        ),
        OperatorDepartment(
            "product",
            "Product Canvas",
            "Cofounder Canvas/product workspace",
            "article.md + attention_ledger.json",
            "draft_only",
            status="bound",
            evidence_refs=("dharma_swarm/venture_cell/darshan/bundle.py",),
            borrowed_from=("cofounder",),
            next_action="Render artifact, attention, claim, and gate lanes in one canvas.",
        ),
        OperatorDepartment(
            "engineering",
            "Engineering",
            "Polsia engineer role + Cofounder task execution",
            "TaskBoard + A2A filesystem receipts",
            "reviewed_internal",
            status="partial",
            evidence_refs=(
                "dharma_swarm/task_board.py",
                "dharma_swarm/operator_core/a2a_task_lifecycle.py",
            ),
            borrowed_from=("polsia", "cofounder"),
            next_action="Attach TaskBoard and A2A queue rows to the Operator OS canvas.",
        ),
        OperatorDepartment(
            "growth",
            "Growth",
            "Polsia growth role with DS contact gate",
            "Darshan external-reader Go receipt gate",
            "human_approved_only",
            status=growth_status,
            evidence_refs=("dharma_swarm/venture_cell/darshan/external_reader_gate.py",),
            borrowed_from=("polsia",),
            next_action=external_reader_gate.next_action,
        ),
        OperatorDepartment(
            "communications",
            "Communications",
            "Polsia comms role with privacy receipts",
            "attention_ledger.json + external_reader_events",
            "human_approved_only",
            status=growth_status,
            evidence_refs=("dharma_swarm/venture_cell/darshan/schema.py",),
            borrowed_from=("polsia", "cofounder"),
            next_action="Keep outreach as drafted/internal until a redacted Go receipt is accepted.",
        ),
        OperatorDepartment(
            "operations",
            "Operations",
            "Polsia daily operating cycle",
            "daily_operating_brief + ds-goal receipts",
            "reviewed_internal",
            status="partial",
            evidence_refs=(
                "dharma_swarm/daily_operating_brief.py",
                "scripts/runtime/autonomy_spine.py",
            ),
            borrowed_from=("polsia",),
            next_action="Emit a daily digest from the projection and mission receipts.",
        ),
        OperatorDepartment(
            "library",
            "Library",
            "Cofounder shared Library",
            "source_pack.json + claim_ledger.json + reports",
            "read_only",
            status="bound",
            evidence_refs=("dharma_swarm/venture_cell/darshan/bundle.py",),
            borrowed_from=("cofounder",),
            next_action="Expose source, claim, and receipt artifacts before synthesis.",
        ),
        OperatorDepartment(
            "memory",
            "Memory Kernel",
            "Karpathy-style LLM wiki substrate",
            "Chetana staging/wiki/provenance",
            "read_only_until_promoted",
            status=memory_status,
            evidence_refs=memory.evidence_refs,
            borrowed_from=("karpathy_llm_wiki", "dharma_swarm"),
            next_action=memory.next_action,
        ),
        OperatorDepartment(
            "governance",
            "Governance",
            "Dharma receipt/witness substrate",
            "governed_work_admission + gate ledgers",
            "default_deny",
            status="bound",
            evidence_refs=(
                "dharma_swarm/operator_core/governed_work_admission.py",
                "dharma_swarm/venture_cell/darshan/external_reader_gate.py",
            ),
            borrowed_from=("dharma_swarm",),
            next_action="Progress autonomy only after receipts and verifier traces pass.",
        ),
    )


def _bundle_canvas_items(bundle: dict[str, Any]) -> list[CanvasItem]:
    bundle_path = Path(bundle["bundle_path"]) if bundle.get("bundle_path") else None
    items: list[CanvasItem] = []
    files = (
        ("artifact", "article.md", "Public artifact draft", "product"),
        ("library", "source_pack.json", "Source pack", "library"),
        ("claims", "claim_ledger.json", "Claim ledger", "library"),
        ("attention", "attention_ledger.json", "Attention ledger", "communications"),
        ("gates", "gate_decisions.json", "Gate decisions", "governance"),
        ("decisions", "decision_delta.json", "Decision delta", "strategy"),
        ("operator_handoff", "polsia_handoff.json", "External operator handoff", "operations"),
    )
    for lane, filename, title, owner in files:
        path = bundle_path / filename if bundle_path else None
        exists = bool(path and path.exists())
        items.append(
            CanvasItem(
                item_id=f"darshan.{filename}",
                lane=lane,
                title=title,
                status="available" if exists else "missing",
                source_surface="darshan_bundle",
                owner_department=owner,
                evidence_refs=(str(path),) if path else (),
                blocked_reason="" if exists else "bundle_file_missing",
            )
        )
    delta = bundle.get("decision_delta")
    if isinstance(delta, DecisionDelta):
        for task_id in delta.new_task_ids:
            items.append(
                CanvasItem(
                    item_id=f"darshan.decision_delta.task.{task_id}",
                    lane="attention_queue",
                    title=f"Decision-delta task {task_id}",
                    status="declared",
                    source_surface="decision_delta.json",
                    owner_department="operations",
                    evidence_refs=(str(bundle_path / "decision_delta.json"),) if bundle_path else (),
                )
            )
    handoff = bundle.get("polsia_handoff")
    if isinstance(handoff, PolsiaHandoff):
        for output in handoff.requested_outputs:
            items.append(
                CanvasItem(
                    item_id=f"darshan.polsia_handoff.{_safe_id(output)}",
                    lane="operator_handoff",
                    title=output,
                    status="requested",
                    source_surface="polsia_handoff.json",
                    owner_department="operations",
                    evidence_refs=(str(bundle_path / "polsia_handoff.json"),) if bundle_path else (),
                )
            )
    return items


def _task_board_canvas_items(tasks: Sequence[Any]) -> list[CanvasItem]:
    items: list[CanvasItem] = []
    for task in tasks:
        value = _task_to_mapping(task)
        task_id = str(value.get("id") or "")
        if not task_id:
            continue
        status = str(value.get("status") or "unknown")
        items.append(
            CanvasItem(
                item_id=f"task_board.{task_id}",
                lane="task_board",
                title=str(value.get("title") or task_id),
                status=status,
                source_surface="TaskBoard",
                owner_department=str(value.get("assigned_to") or "engineering"),
                evidence_refs=("dharma_swarm/task_board.py",),
                raw=value,
            )
        )
    return items


def _a2a_canvas_items(rows: Sequence[Mapping[str, Any]]) -> list[CanvasItem]:
    items: list[CanvasItem] = []
    for row in rows:
        task_id = str(row.get("id") or "").strip()
        if not task_id:
            continue
        lifecycle = task_lifecycle_state(dict(row), require_artifact_or_evidence=False)
        items.append(
            CanvasItem(
                item_id=f"a2a.{task_id}",
                lane="a2a_queue",
                title=str(row.get("title") or row.get("body") or task_id).splitlines()[0][:120],
                status=str(lifecycle["state"]),
                source_surface="A2A filesystem queue",
                owner_department=str(row.get("to") or "engineering"),
                evidence_refs=("dharma_swarm/operator_core/a2a_task_lifecycle.py",),
                blocked_reason="" if lifecycle["closed"] else "a2a_task_not_terminal",
                raw={**dict(row), "lifecycle": lifecycle},
            )
        )
    return items


def _a2a_rows(inputs: OperatorOSInputs) -> tuple[Mapping[str, Any], ...]:
    if inputs.a2a_tasks is not None:
        return tuple(inputs.a2a_tasks)
    if inputs.state_root is None:
        return ()
    return tuple(read_queue(inputs.state_root))


def _task_to_mapping(task: Any) -> dict[str, Any]:
    if isinstance(task, Mapping):
        return dict(task)
    metadata = getattr(task, "metadata", None)
    return {
        "id": getattr(task, "id", ""),
        "title": getattr(task, "title", ""),
        "status": getattr(getattr(task, "status", ""), "value", getattr(task, "status", "")),
        "priority": getattr(getattr(task, "priority", ""), "value", getattr(task, "priority", "")),
        "assigned_to": getattr(task, "assigned_to", ""),
        "created_by": getattr(task, "created_by", ""),
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


def _projection_status(
    bundle: dict[str, Any],
    external_reader_gate: GateSummary,
    canvas: Sequence[CanvasItem],
) -> str:
    if not bundle["valid"]:
        return "blocked_on_bundle"
    if external_reader_gate.decision != "allow":
        return "blocked_on_external_reader_gate"
    if any(item.status == "missing" for item in canvas):
        return "partial"
    return "ready_for_reviewed_internal_execution"


def _autonomy_level(
    external_reader_gate: GateSummary,
    admission: GateSummary,
    canvas: Sequence[CanvasItem],
) -> str:
    if external_reader_gate.decision != "allow":
        return "L0_read_only_plan"
    if admission.decision != "allow":
        return "L1_reviewed_internal_only"
    terminal_a2a = any(item.lane == "a2a_queue" and item.status.endswith("_verified") for item in canvas)
    if terminal_a2a:
        return "L2_receipted_internal_execution"
    return "L1_reviewed_internal_only"


def _gap_codes(
    bundle: dict[str, Any],
    external_reader_gate: GateSummary,
    admission: GateSummary,
    memory: MemoryKernelSnapshot,
    canvas: Sequence[CanvasItem],
) -> tuple[str, ...]:
    gaps: list[str] = []
    if not bundle["valid"]:
        gaps.extend(str(error) for error in bundle["errors"])
    gaps.extend(external_reader_gate.gap_codes)
    gaps.extend(admission.gap_codes)
    gaps.extend(memory.gap_codes)
    if not any(item.lane == "task_board" for item in canvas):
        gaps.append("operator_os_task_board_projection_empty")
    if not any(item.lane == "a2a_queue" for item in canvas):
        gaps.append("operator_os_a2a_projection_empty")
    return tuple(dict.fromkeys(gaps))


def _next_actions(gaps: Sequence[str]) -> tuple[str, ...]:
    actions: list[str] = []
    if any("external_reader" in gap for gap in gaps):
        actions.append("Record one accepted, privacy-redacted external-reader Go receipt before external growth/comms autonomy.")
    if "operator_os_task_board_projection_empty" in gaps:
        actions.append("Attach current TaskBoard rows to the Operator OS canvas.")
    if "operator_os_a2a_projection_empty" in gaps:
        actions.append("Attach A2A queue rows and closure receipts to the Operator OS canvas.")
    if any("memory_kernel" in gap for gap in gaps):
        actions.append("Build a read-through MemoryKernel index over Chetana/wiki with source and promotion receipts.")
    if not actions:
        actions.append("Run the next bounded internal builder under governed admission and record receipts.")
    return tuple(actions)


def _evidence_refs(
    bundle: dict[str, Any],
    external_reader_gate: GateSummary,
    memory: MemoryKernelSnapshot,
) -> Iterable[str]:
    yield bundle.get("bundle_path", "")
    yield from external_reader_gate.evidence_refs
    yield from memory.evidence_refs
    yield "dharma_swarm/venture_cell/operator_os/projection.py"


def _daily_cycle() -> tuple[str, ...]:
    return (
        "observe local evidence and receipts",
        "update canvas and attention queue",
        "plan with governed_work_admission",
        "execute only reviewed internal work",
        "verify with tests or receipt checks",
        "write daily digest and next packet",
    )


def _bounded_md_count(root: Path, max_scan: int) -> tuple[int, bool]:
    resolved = root.expanduser()
    if not resolved.exists():
        return 0, False
    count = 0
    for path in resolved.rglob("*.md"):
        if path.is_file():
            count += 1
            if count >= max_scan:
                return count, True
    return count, False


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")[:80] or "item"
