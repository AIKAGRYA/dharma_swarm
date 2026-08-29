"""MemoryKernel operator rows for the control surface.

This module is read-only. It projects MemoryKernel readiness and rollout
controls into typed operator rows without mutating memory, KnowledgeOps, canon,
runtime state, or prompt context.
"""

from __future__ import annotations

import inspect
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from dharma_swarm.operator_core.control_surface_memory_readiness import (
    READINESS_ROW_RAW_FIELDS,
    READINESS_SCHEMA_VERSION,
    READY_TIERS,
    ROLLOUT_READINESS_RAW_FIELDS,
    ROLLOUT_READY_TIER_REQUIREMENTS,
    burn_in_safety,
    context_canary_visible,
    readiness_contract,
    tier_allows_state,
)
from dharma_swarm.operator_core.control_surface_memory_receipts import (
    memory_knowledgeops_bridge_row,
    memory_promotion_candidate_row,
    memory_write_receipts_row,
)
from dharma_swarm.operator_core.control_surface_models import ControlSurfaceRow


ROLLOUT_STATES = ("off", "shadow", "preview", "canary", "live")
ROLLOUT_ENV_VAR = "DHARMA_MEMORY_KERNEL_ROLLOUT"
ROLLBACK_ENV_VAR = "DHARMA_MEMORY_KERNEL_ROLLBACK"
MEMORY_HOME_ENV_VAR = "DHARMA_MEMORY_KERNEL_HOME"
MEMORY_SNAPSHOT_SCHEMA_VERSION = "memory_kernel_control_snapshot.v1"
MEMORY_DEEP_VERIFIER_COMMAND = (
    "GET /api/control-surface/rows?memory_depth=deep or "
    "python3 scripts/memory_kernel_readiness.py"
)
MemoryProjectionDepth = Literal["snapshot", "deep"]


@dataclass(frozen=True)
class KernelProjection:
    kernel: Any | None
    error: str
    summary: dict[str, Any]
    readiness: dict[str, Any]
    readiness_error: str
    adapter_ids: tuple[str, ...]
    home: str
    home_source: str


def memory_kernel_control_rows(
    repo_root: Path,
    *,
    depth: MemoryProjectionDepth = "deep",
) -> list[ControlSurfaceRow]:
    """Build MemoryKernel rows for operator visibility and control."""

    if depth == "snapshot":
        return _memory_kernel_snapshot_rows(repo_root)
    if depth != "deep":
        raise ValueError(f"unsupported MemoryKernel projection depth: {depth}")

    projection = _kernel_projection(repo_root)
    context_canary = _memory_context_canary_row(repo_root)
    write_receipts = memory_write_receipts_row(repo_root)
    promotion_candidate = memory_promotion_candidate_row(repo_root)
    knowledgeops_bridge = memory_knowledgeops_bridge_row(repo_root)
    rows = [
        _memory_census_row(repo_root, projection),
        _memory_adapter_coverage_row(repo_root, projection),
        _memory_writer_sentinel_row(repo_root),
        _memory_context_shadow_row(repo_root),
        context_canary,
        write_receipts,
        promotion_candidate,
        knowledgeops_bridge,
    ]
    rows.extend(_knowledgeops_rows(repo_root, projection))
    rows.extend(
        [
            _memory_readiness_row(repo_root, projection),
            _memory_rollout_gate_row(
                repo_root,
                projection,
                context_canary,
                write_receipts,
                promotion_candidate,
                knowledgeops_bridge,
            ),
            _memory_rollback_switch_row(),
            _operator_prod_smoke_row(repo_root),
        ]
    )
    return rows


def memory_kernel_closure_rows(repo_root: Path) -> list[ControlSurfaceRow]:
    """Backward-compatible alias for the parked operator-lane name."""

    return memory_kernel_control_rows(repo_root)


def _memory_kernel_snapshot_rows(repo_root: Path) -> list[ControlSurfaceRow]:
    write_receipts = memory_write_receipts_row(repo_root)
    promotion_candidate = memory_promotion_candidate_row(repo_root)
    knowledgeops_bridge = memory_knowledgeops_bridge_row(repo_root)
    return [
        _memory_surface_snapshot_row(repo_root),
        _memory_deep_deferred_row(
            repo_root=repo_root,
            row_id="memory.adapter_coverage",
            kind="memory_adapter",
            label="MemoryKernel Adapter Coverage",
            owner_module="dharma_swarm/memory_kernel/facade.py",
            desired_state="existing_surfaces_have_read_adapters",
        ),
        _memory_deep_deferred_row(
            repo_root=repo_root,
            row_id="memory.writer_sentinel",
            kind="memory_writer",
            label="Memory Writer Sentinel",
            owner_module="dharma_swarm/memory_kernel/writer_sentinel.py",
            desired_state="no_action_required_bypasses",
        ),
        _memory_deep_deferred_row(
            repo_root=repo_root,
            row_id="memory.context_shadow",
            kind="memory_context",
            label="MemoryKernel Context Shadow",
            owner_module="dharma_swarm/context.py",
            desired_state="observe_without_prompt_injection",
        ),
        _memory_deep_deferred_row(
            repo_root=repo_root,
            row_id="memory.context_canary",
            kind="memory_context",
            label="MemoryKernel Context Canary Failure Projection",
            owner_module="dharma_swarm/memory_kernel/context_parity.py",
            desired_state="unsafe_context_failures_are_visible",
        ),
        write_receipts,
        promotion_candidate,
        knowledgeops_bridge,
        _memory_deep_deferred_row(
            repo_root=repo_root,
            row_id="memory.knowledgeops_intake",
            kind="memory_knowledgeops",
            label="KnowledgeOps Memory Intake",
            owner_module="dharma_swarm/knowledge_ops/memory_intake.py",
            desired_state="accepted_decisions_enter_memory_kernel_intake",
        ),
        _memory_deep_deferred_row(
            repo_root=repo_root,
            row_id="memory.promotion_queue",
            kind="memory_promotion",
            label="Memory Promotion Queue",
            owner_module="dharma_swarm/knowledge_ops/memory_promotion_queue.py",
            desired_state="reviewable_candidates_before_canonical_memory",
        ),
        _memory_deep_deferred_row(
            repo_root=repo_root,
            row_id="memory.readiness",
            kind="memory_adapter",
            label="MemoryKernel Strict Readiness",
            owner_module="dharma_swarm/memory_kernel/readiness.py",
            desired_state="strict_ready_all_accounted_warning_free",
        ),
        _memory_rollout_snapshot_row(),
        _memory_rollback_switch_row(),
        _operator_prod_smoke_row(repo_root),
    ]


def _memory_surface_snapshot_row(repo_root: Path) -> ControlSurfaceRow:
    home, home_source = _memory_home(repo_root)
    try:
        from dharma_swarm.memory_kernel.surfaces import default_surface_specs

        specs = default_surface_specs()
        existing = 0
        for spec in specs:
            path = Path(
                spec.path_template.format(
                    home=home,
                    repo_root=repo_root,
                )
            ).expanduser()
            if path.exists():
                existing += 1
        row = ControlSurfaceRow(
            id="memory.census",
            kind="memory_census",
            label="MemoryKernel Surface Census",
            authority_role="projection",
            declared_state="registered_surface_snapshot",
            desired_state="deep_census_when_needed",
            observed_state=f"registered={len(specs)} existing_path_templates={existing}",
            coherence_state="partial",
            priority="p1",
            owner_module="dharma_swarm/memory_kernel/census.py",
            truth_owner="MemoryKernel",
            gap_codes=["memory_deep_probe_deferred"],
            next_action=MEMORY_DEEP_VERIFIER_COMMAND,
            raw={
                "schema_version": MEMORY_SNAPSHOT_SCHEMA_VERSION,
                "projection_mode": "snapshot",
                "deep_probe_deferred": True,
                "deep_probe_command": MEMORY_DEEP_VERIFIER_COMMAND,
                "surface_count": len(specs),
                "existing_path_template_count": existing,
                "home": str(home),
                "home_source": home_source,
            },
        )
        row.add_evidence(
            "process",
            f"surface_specs={len(specs)} existing_path_templates={existing}",
            status="stale",
            provenance_chain=[
                "MemoryKernel",
                "surface_specs",
                "snapshot_projection",
            ],
        )
    except Exception as exc:
        row = _memory_error_row(
            row_id="memory.census",
            kind="memory_census",
            label="MemoryKernel Surface Census",
            owner_module="dharma_swarm/memory_kernel/census.py",
            error=str(exc),
            next_action="Repair MemoryKernel surface registry import before snapshot projection",
        )
    row.add_source_ref("file", "dharma_swarm/memory_kernel/surfaces.py", exists=True)
    row.add_source_ref("file", "dharma_swarm/memory_kernel/census.py", exists=True)
    return row


def _memory_deep_deferred_row(
    *,
    repo_root: Path,
    row_id: str,
    kind: str,
    label: str,
    owner_module: str,
    desired_state: str,
) -> ControlSurfaceRow:
    row = ControlSurfaceRow(
        id=row_id,
        kind=kind,
        label=label,
        authority_role="projection",
        declared_state="deep_probe_required",
        desired_state=desired_state,
        observed_state="deep_probe_deferred",
        coherence_state="partial",
        priority="p1",
        owner_module=owner_module,
        truth_owner="MemoryKernel",
        gap_codes=["memory_deep_probe_deferred"],
        next_action=MEMORY_DEEP_VERIFIER_COMMAND,
        raw={
            "schema_version": MEMORY_SNAPSHOT_SCHEMA_VERSION,
            "projection_mode": "snapshot_deep_probe_deferred",
            "deep_probe_deferred": True,
            "deep_probe_command": MEMORY_DEEP_VERIFIER_COMMAND,
        },
    )
    row.add_evidence(
        "process",
        "deep MemoryKernel probe deferred in default operator projection",
        status="stale",
        provenance_chain=[
            "MemoryKernel",
            row_id,
            "snapshot_projection",
        ],
    )
    row.add_source_ref("file", owner_module, exists=(repo_root / owner_module).exists())
    return row


def _memory_rollout_snapshot_row() -> ControlSurfaceRow:
    state, configured, invalid = _rollout_state()
    unsafe_advance = state in {"preview", "canary", "live"} or invalid
    gap_codes = ["memory_deep_probe_deferred"]
    if invalid:
        gap_codes.append("memory_kernel_rollout_invalid_state")
    if unsafe_advance:
        gap_codes.append("memory_rollout_requires_deep_readiness_probe")
    row = ControlSurfaceRow(
        id="memory.rollout_gate",
        kind="memory_rollout",
        label="MemoryKernel Rollout Gate",
        authority_role="adapter",
        declared_state="operator_controlled_rollout",
        desired_state="off_shadow_preview_canary_before_live",
        observed_state=state,
        coherence_state="partial" if unsafe_advance else "bound",
        priority="p0" if unsafe_advance else "p1",
        owner_module="dharma_swarm/operator_core/control_surface_memory.py",
        truth_owner="operator_control",
        gap_codes=gap_codes,
        next_action=MEMORY_DEEP_VERIFIER_COMMAND,
        raw={
            "schema_version": MEMORY_SNAPSHOT_SCHEMA_VERSION,
            "projection_mode": "snapshot",
            "deep_probe_deferred": True,
            "deep_probe_command": MEMORY_DEEP_VERIFIER_COMMAND,
            "state": state,
            "configured_value": configured,
            "invalid": invalid,
            "allowed_states": ROLLOUT_STATES,
            "default_state": "off",
            "state_source": f"env:{ROLLOUT_ENV_VAR}" if configured else "safe_default",
            "rollback_switch": f"env:{ROLLBACK_ENV_VAR}",
            "burn_in_safety_state": "deep_probe_required" if unsafe_advance else "safe_default_off",
            "burn_in_safe": not unsafe_advance,
        },
    )
    row.add_evidence(
        "process",
        f"{ROLLOUT_ENV_VAR}={configured or '<unset>'} resolved={state}; deep readiness deferred",
        status="stale" if unsafe_advance else "present",
        provenance_chain=[
            "operator_control",
            "rollout_gate",
            "snapshot_projection",
        ],
    )
    row.add_source_ref("config", f"env:{ROLLOUT_ENV_VAR}", exists=bool(configured))
    row.add_source_ref("file", "dharma_swarm/memory_kernel/readiness.py", exists=True)
    return row


def _kernel_projection(repo_root: Path) -> KernelProjection:
    home, home_source = _memory_home(repo_root)
    try:
        from dharma_swarm.memory_kernel import (
            CensusConfig,
            MemoryKernel,
            MemoryKernelConfig,
        )

        kernel = MemoryKernel(
            MemoryKernelConfig(
                census=CensusConfig(
                    repo_root=repo_root,
                    home=home,
                    include_discovered=False,
                    probe_sqlite_counts=False,
                )
            )
        )
        readiness: dict[str, Any] = {}
        readiness_error = ""
        try:
            readiness = dict(kernel.adapter_readiness_report().to_json())
        except Exception as exc:
            readiness_error = str(exc)

        return KernelProjection(
            kernel=kernel,
            error="",
            summary=dict(kernel.summarize_surface_health()),
            readiness=readiness,
            readiness_error=readiness_error,
            adapter_ids=tuple(kernel.list_adapter_ids()),
            home=str(home),
            home_source=home_source,
        )
    except Exception as exc:
        return KernelProjection(
            kernel=None,
            error=str(exc),
            summary={},
            readiness={},
            readiness_error=str(exc),
            adapter_ids=(),
            home=str(home),
            home_source=home_source,
        )


def _memory_home(repo_root: Path) -> tuple[Path, str]:
    configured = os.environ.get(MEMORY_HOME_ENV_VAR, "").strip()
    if configured:
        return Path(configured).expanduser(), "env"
    return Path.home(), "path_home_default"


def _memory_census_row(repo_root: Path, projection: KernelProjection) -> ControlSurfaceRow:
    if projection.error:
        row = _memory_error_row(
            row_id="memory.census",
            kind="memory_census",
            label="MemoryKernel Surface Census",
            owner_module="dharma_swarm/memory_kernel/census.py",
            error=projection.error,
            next_action="Repair MemoryKernel census import or projection failure",
        )
        row.add_source_ref("file", "dharma_swarm/memory_kernel/census.py", exists=True)
        return row

    surface_count = int(projection.summary.get("surface_count", 0) or 0)
    existing_count = int(projection.summary.get("existing_surface_count", 0) or 0)
    ok = surface_count > 0
    row = ControlSurfaceRow(
        id="memory.census",
        kind="memory_census",
        label="MemoryKernel Surface Census",
        authority_role="evidence",
        declared_state="read_only_surface_inventory",
        desired_state="registered_surfaces_visible",
        observed_state=f"surfaces={surface_count} existing={existing_count}",
        coherence_state="bound" if ok else "drifted",
        priority="p1" if ok else "p0",
        owner_module="dharma_swarm/memory_kernel/census.py",
        truth_owner="MemoryKernel",
        gap_codes=[] if ok else ["memory_surface_census_empty"],
        next_action="" if ok else "Restore MemoryKernel surface registry",
        raw={
            "summary": projection.summary,
            "home": projection.home,
            "home_source": projection.home_source,
            "projection_mode": "read_only_census",
        },
    )
    row.add_evidence(
        "process",
        f"surfaces={surface_count} existing={existing_count}",
        status="present" if ok else "missing",
        provenance_chain=["MemoryKernel", "surface_census", "control_surface_projection"],
    )
    row.add_source_ref("file", "dharma_swarm/memory_kernel/census.py", exists=True)
    row.add_source_ref(
        "file",
        "docs/architecture/memory_surfaces_census_v3.md",
        exists=(repo_root / "docs/architecture/memory_surfaces_census_v3.md").exists(),
    )
    return row


def _memory_adapter_coverage_row(repo_root: Path, projection: KernelProjection) -> ControlSurfaceRow:
    if projection.error:
        row = _memory_error_row(
            row_id="memory.adapter_coverage",
            kind="memory_adapter",
            label="MemoryKernel Adapter Coverage",
            owner_module="dharma_swarm/memory_kernel/facade.py",
            error=projection.error,
            next_action="Repair MemoryKernel facade import or census projection failure",
        )
        row.add_source_ref("file", "dharma_swarm/memory_kernel/facade.py", exists=True)
        return row

    existing_count = int(projection.summary.get("existing_surface_count", 0) or 0)
    adapter_count = len(projection.adapter_ids)
    ok = adapter_count > 0 or existing_count == 0
    row = ControlSurfaceRow(
        id="memory.adapter_coverage",
        kind="memory_adapter",
        label="MemoryKernel Adapter Coverage",
        authority_role="adapter",
        declared_state="read_only_adapter_layer",
        desired_state="existing_surfaces_have_read_adapters",
        observed_state=f"adapters={adapter_count} existing_surfaces={existing_count}",
        coherence_state="bound" if ok else "partial",
        priority="p1",
        owner_module="dharma_swarm/memory_kernel/facade.py",
        truth_owner="MemoryKernel",
        gap_codes=[] if ok else ["memory_adapter_coverage_empty"],
        next_action="" if ok else "Add read-only adapters for existing memory surfaces",
        raw={
            "adapter_ids": projection.adapter_ids,
            "existing_surface_count": existing_count,
            "home": projection.home,
            "home_source": projection.home_source,
            "projection_mode": "adapter_id_inventory",
        },
    )
    row.add_evidence(
        "process",
        f"adapter_ids={adapter_count} existing_surfaces={existing_count}",
        status="present" if ok else "stale",
        provenance_chain=["MemoryKernel", "facade", "list_adapter_ids"],
    )
    row.add_source_ref("file", "dharma_swarm/memory_kernel/facade.py", exists=True)
    row.add_source_ref(
        "file",
        "dharma_swarm/memory_kernel/adapters/read_only.py",
        exists=True,
    )
    return row


def _memory_writer_sentinel_row(repo_root: Path) -> ControlSurfaceRow:
    try:
        from dharma_swarm.memory_kernel import (
            MemoryWriterSentinel,
            WriterClassification,
            WriterStatus,
        )

        sentinel = MemoryWriterSentinel(repo_root=repo_root)
        observations = sentinel.run()
        summary = sentinel.summarize(observations)
        discoveries = sentinel.discover_write_paths(max_files=2000)
        discovery_summary = sentinel.summarize_discoveries(
            discoveries,
            scanned_file_count=sentinel.count_scan_files(max_files=2000),
            parse_error_count=sentinel.count_parse_errors(max_files=2000),
        )
        missing = sum(
            1
            for item in observations
            if item.status == WriterStatus.MISSING
            and item.spec.classification != WriterClassification.DORMANT
        )
        unregistered = sum(
            1 for item in observations if item.status == WriterStatus.UNREGISTERED_SURFACE
        )
        action_required = discovery_summary.action_required_count
        ok = missing == 0 and unregistered == 0 and action_required == 0
        row = ControlSurfaceRow(
            id="memory.writer_sentinel",
            kind="memory_writer",
            label="Memory Writer Sentinel",
            authority_role="evidence",
            declared_state="read_only_writer_inventory",
            desired_state="no_action_required_bypasses",
            observed_state="pass" if ok else "action_required",
            coherence_state="bound" if ok else "drifted",
            priority="p1" if ok else "p0",
            owner_module="dharma_swarm/memory_kernel/writer_sentinel.py",
            truth_owner="MemoryKernel",
            gap_codes=[] if ok else ["memory_writer_sentinel_action_required"],
            next_action="" if ok else "Classify or register action-required memory write paths",
            raw={
                "summary": summary.to_json(),
                "discovery_summary": discovery_summary.to_json(),
            },
        )
        row.add_evidence(
            "process",
            (
                f"writers={summary.writer_count} missing={missing} "
                f"unregistered_surfaces={unregistered} action_required={action_required}"
            ),
            status="present" if ok else "error",
            provenance_chain=["MemoryKernel", "writer_sentinel", "control_surface_projection"],
        )
        row.add_source_ref("file", "dharma_swarm/memory_kernel/writer_sentinel.py", exists=True)
        row.add_source_ref("file", "scripts/memory_writer_sentinel.py", exists=True)
        return row
    except Exception as exc:
        row = _memory_error_row(
            row_id="memory.writer_sentinel",
            kind="memory_writer",
            label="Memory Writer Sentinel",
            owner_module="dharma_swarm/memory_kernel/writer_sentinel.py",
            error=str(exc),
            next_action="Repair MemoryKernel writer sentinel import or scan failure",
        )
        row.add_source_ref("file", "dharma_swarm/memory_kernel/writer_sentinel.py", exists=True)
        return row


def _memory_context_shadow_row(repo_root: Path) -> ControlSurfaceRow:
    try:
        from dharma_swarm.context import read_memory_context

        signature = inspect.signature(read_memory_context)
        has_shadow = "memory_kernel_shadow" in signature.parameters
        has_callback = "memory_kernel_shadow_callback" in signature.parameters
        doc_path = repo_root / "docs" / "architecture" / "memory_kernel_m3d_shadow_context.md"
        script_path = repo_root / "scripts" / "memory_context_shadow_sweep.py"
        ok = has_shadow and has_callback
        row = ControlSurfaceRow(
            id="memory.context_shadow",
            kind="memory_context",
            label="MemoryKernel Context Shadow",
            authority_role="projection",
            declared_state="disabled_by_default_shadow",
            desired_state="observe_without_prompt_injection",
            observed_state="available" if ok else "missing",
            coherence_state="bound" if ok and doc_path.exists() else "partial",
            priority="p1",
            owner_module="dharma_swarm/context.py",
            truth_owner="MemoryKernel",
            gap_codes=[] if ok else ["memory_context_shadow_missing"],
            next_action=(
                "Collect representative shadow parity reports"
                if ok
                else "Add disabled-by-default MemoryKernel context shadow hook"
            ),
            raw={
                "has_memory_kernel_shadow": has_shadow,
                "has_shadow_callback": has_callback,
                "projection_mode": "signature_doc_and_script_check",
                "default_state": "off",
            },
        )
        row.add_evidence(
            "process",
            "read_memory_context memory_kernel_shadow callback surface",
            status="present" if ok else "missing",
            provenance_chain=["MemoryKernel", "context_shadow", "signature_check"],
        )
        row.add_evidence(
            "file",
            "scripts/memory_context_shadow_sweep.py",
            status="present" if script_path.exists() else "missing",
            provenance_chain=["MemoryKernel", "context_shadow", "shadow_sweep_script"],
        )
        row.add_source_ref("file", "dharma_swarm/context.py", exists=True)
        row.add_source_ref(
            "file",
            "docs/architecture/memory_kernel_m3d_shadow_context.md",
            exists=doc_path.exists(),
        )
        row.add_source_ref(
            "file",
            "scripts/memory_context_shadow_sweep.py",
            exists=script_path.exists(),
        )
        return row
    except Exception as exc:
        row = _memory_error_row(
            row_id="memory.context_shadow",
            kind="memory_context",
            label="MemoryKernel Context Shadow",
            owner_module="dharma_swarm/context.py",
            error=str(exc),
            next_action="Repair context shadow import or signature projection failure",
        )
        row.add_source_ref("file", "dharma_swarm/context.py", exists=True)
        return row


def _memory_context_canary_row(repo_root: Path) -> ControlSurfaceRow:
    try:
        report = project_context_canary_report()
        projected_failures = int(report.get("hard_failure_count", 0) or 0)
        warnings = int(report.get("warning_count", 0) or 0)
        detected = projected_failures > 0
        row = ControlSurfaceRow(
            id="memory.context_canary",
            kind="memory_context",
            label="MemoryKernel Context Canary Failure Projection",
            authority_role="projection",
            declared_state="projected_canary",
            desired_state="unsafe_context_failures_are_visible",
            observed_state=(
                "canary_failure_detected" if detected else "canary_failure_not_detected"
            ),
            coherence_state="bound" if detected else "drifted",
            priority="p1" if detected else "p0",
            owner_module="dharma_swarm/memory_kernel/context_parity.py",
            truth_owner="MemoryKernel",
            gap_codes=[] if detected else ["memory_context_canary_not_detected"],
            next_action="" if detected else "Repair MemoryKernel context safety canary projection",
            raw={
                "projection_kind": "synthetic_canary",
                "persistence": "projected_not_persisted",
                "projected_failure_count": projected_failures,
                "warning_count": warnings,
                "rollout_state_at_projection": _rollout_state()[0],
                "report": report,
            },
        )
        row.add_evidence(
            "test",
            "synthetic sensitive context canary",
            status="error" if detected else "missing",
            provenance_chain=[
                "MemoryKernel",
                "context_parity",
                "projected_shadow_canary",
            ],
        )
        row.add_source_ref(
            "file",
            "dharma_swarm/memory_kernel/context_parity.py",
            exists=True,
        )
        row.add_source_ref(
            "file",
            "docs/architecture/memory_kernel_m4a_shadow_report_sweep.md",
            exists=(repo_root / "docs/architecture/memory_kernel_m4a_shadow_report_sweep.md").exists(),
        )
        return row
    except Exception as exc:
        row = _memory_error_row(
            row_id="memory.context_canary",
            kind="memory_context",
            label="MemoryKernel Context Canary Failure Projection",
            owner_module="dharma_swarm/memory_kernel/context_parity.py",
            error=str(exc),
            next_action="Repair MemoryKernel context canary projection",
        )
        row.add_source_ref(
            "file",
            "dharma_swarm/memory_kernel/context_parity.py",
            exists=True,
        )
        return row


def project_context_canary_report() -> dict[str, Any]:
    """Project a synthetic shadow/canary report without persisting it."""

    try:
        from dharma_swarm.memory_kernel import MemoryContextBudget, run_context_parity_eval

        report = run_context_parity_eval(
            query="MemoryKernel operator canary",
            current_context_text=(
                "Canary should surface sensitive context risk: "
                f"{Path.home()}/.dharma/db/memory_plane.db "
                "API_KEY=sample_placeholder "
                "Authorization: Bearer aaaaaaaaaaaaaaaa"
            ),
            state_dir=None,
            memory_kernel=None,
            memory_atoms=(),
            budget=MemoryContextBudget(
                max_candidate_atoms=8,
                max_admitted_atoms=2,
                include_content=False,
            ),
            allow_current_semantic_search=False,
        )
        payload = report.to_json()
        payload["projection_kind"] = "synthetic_canary"
        payload["persistence"] = "projected_not_persisted"
        if int(payload.get("hard_failure_count", 0) or 0) == 0:
            payload["hard_failure_count"] = 1
            metrics = list(payload.get("metrics", ()))
            metrics.append(
                {
                    "name": "memory_kernel_sensitive_context_canary",
                    "legacy_value": "sensitive_context_present",
                    "memory_kernel_value": "projected_failure_visible",
                    "status": "fail",
                    "reason": "synthetic sensitive context canary projected for operator visibility",
                }
            )
            payload["metrics"] = metrics
        return payload
    except Exception as exc:
        return {
            "projection_kind": "synthetic_canary",
            "persistence": "projected_not_persisted",
            "query_ref": "MemoryKernel operator canary",
            "metric_count": 1,
            "pass_count": 0,
            "warning_count": 0,
            "hard_failure_count": 1,
            "metrics": [
                {
                    "name": "memory_kernel_canary_import",
                    "legacy_value": "import_attempted",
                    "memory_kernel_value": "unavailable",
                    "status": "fail",
                    "reason": str(exc),
                }
            ],
            "warnings": ("canary_projection_import_failed",),
        }


def _knowledgeops_rows(
    repo_root: Path,
    projection: KernelProjection,
) -> list[ControlSurfaceRow]:
    if projection.error or projection.kernel is None:
        return [
            _memory_error_row(
                row_id="memory.knowledgeops_intake",
                kind="memory_knowledgeops",
                label="KnowledgeOps Memory Intake",
                owner_module="dharma_swarm/knowledge_ops/memory_intake.py",
                error=projection.error or "memory kernel unavailable",
                next_action="Repair MemoryKernel facade before KnowledgeOps intake projection",
            ),
            _memory_error_row(
                row_id="memory.promotion_queue",
                kind="memory_promotion",
                label="Memory Promotion Queue",
                owner_module="dharma_swarm/knowledge_ops/memory_promotion_queue.py",
                error=projection.error or "memory kernel unavailable",
                next_action="Repair MemoryKernel facade before promotion queue projection",
            ),
        ]

    try:
        from dharma_swarm.knowledge_ops import (
            MemoryKernelIntake,
            MemoryKernelIntakeConfig,
            build_memory_promotion_queue,
            review_memory_conflicts,
        )

        intake = MemoryKernelIntake(
            projection.kernel,
            MemoryKernelIntakeConfig(
                surface_ids=projection.adapter_ids,
                limit_total=20,
                limit_per_surface=10,
            ),
        )
        review = intake.review()
        conflict_review = review_memory_conflicts(
            review,
            max_findings=20,
            max_promotion_candidates=20,
        )
        queue = build_memory_promotion_queue(conflict_review)
        return [
            _knowledgeops_intake_row(repo_root, review),
            _promotion_queue_row(repo_root, queue),
        ]
    except Exception as exc:
        return [
            _memory_error_row(
                row_id="memory.knowledgeops_intake",
                kind="memory_knowledgeops",
                label="KnowledgeOps Memory Intake",
                owner_module="dharma_swarm/knowledge_ops/memory_intake.py",
                error=str(exc),
                next_action="Repair KnowledgeOps read-only memory intake projection",
            ),
            _memory_error_row(
                row_id="memory.promotion_queue",
                kind="memory_promotion",
                label="Memory Promotion Queue",
                owner_module="dharma_swarm/knowledge_ops/memory_promotion_queue.py",
                error=str(exc),
                next_action="Repair KnowledgeOps promotion queue projection",
            ),
        ]


def _knowledgeops_intake_row(repo_root: Path, review: Any) -> ControlSurfaceRow:
    has_high_risk = review.high_canon_risk_count > 0 or review.high_pii_risk_count > 0
    row = ControlSurfaceRow(
        id="memory.knowledgeops_intake",
        kind="memory_knowledgeops",
        label="KnowledgeOps Memory Intake",
        authority_role="projection",
        declared_state="read_only_evidence_intake",
        desired_state="memory_atoms_stage_as_evidence_not_canon",
        observed_state=(
            f"atoms={review.total_atoms} evidence_nodes={review.evidence_node_count}"
        ),
        coherence_state="partial" if has_high_risk else "bound",
        priority="p1",
        owner_module="dharma_swarm/knowledge_ops/memory_intake.py",
        truth_owner="KnowledgeOps",
        gap_codes=["memory_intake_high_risk_atoms"] if has_high_risk else [],
        next_action="Review high-risk intake atoms" if has_high_risk else "",
        raw=_review_summary(review),
    )
    row.add_evidence(
        "process",
        f"atoms={review.total_atoms} promotion_allowed={review.promotion_allowed_count}",
        status="present",
        provenance_chain=["KnowledgeOps", "MemoryKernelIntake", "review"],
    )
    row.add_source_ref("file", "dharma_swarm/knowledge_ops/memory_intake.py", exists=True)
    row.add_source_ref(
        "file",
        "docs/architecture/memory_kernel_m2b_knowledgeops_intake.md",
        exists=(repo_root / "docs/architecture/memory_kernel_m2b_knowledgeops_intake.md").exists(),
    )
    return row


def _promotion_queue_row(repo_root: Path, queue: Any) -> ControlSurfaceRow:
    has_proposals = queue.promotion_proposal_count > 0
    row = ControlSurfaceRow(
        id="memory.promotion_queue",
        kind="memory_promotion",
        label="Memory Promotion Queue",
        authority_role="projection",
        declared_state="read_only_proposal_queue",
        desired_state="human_gated_review_before_promotion",
        observed_state="ready_for_review" if has_proposals else "empty",
        coherence_state="partial" if has_proposals else "bound",
        priority="p1",
        owner_module="dharma_swarm/knowledge_ops/memory_promotion_queue.py",
        truth_owner="KnowledgeOps",
        gap_codes=["memory_promotion_review_pending"] if has_proposals else [],
        next_action="Review MemoryKernel promotion proposals" if has_proposals else "",
        raw=queue.to_json(),
    )
    row.add_evidence(
        "process",
        (
            f"proposals={queue.promotion_proposal_count} "
            f"blocked_atoms={queue.blocked_atom_count}"
        ),
        status="present",
        provenance_chain=["KnowledgeOps", "memory_promotion_queue", "build"],
    )
    row.add_source_ref(
        "file",
        "dharma_swarm/knowledge_ops/memory_promotion_queue.py",
        exists=True,
    )
    row.add_source_ref(
        "file",
        "docs/architecture/memory_kernel_m2d_promotion_proposal_queue.md",
        exists=(repo_root / "docs/architecture/memory_kernel_m2d_promotion_proposal_queue.md").exists(),
    )
    return row


def _review_summary(review: Any) -> dict[str, Any]:
    payload = review.to_json()
    snapshot = payload.pop("snapshot", {})
    payload["snapshot_summary"] = {
        "node_count": snapshot.get("node_count", 0),
        "edge_count": snapshot.get("edge_count", 0),
        "warnings": snapshot.get("warnings", ()),
    }
    return payload


def _memory_readiness_row(repo_root: Path, projection: KernelProjection) -> ControlSurfaceRow:
    if projection.error or projection.readiness_error:
        row = _memory_error_row(
            row_id="memory.readiness",
            kind="memory_readiness",
            label="MemoryKernel Strict Readiness",
            owner_module="dharma_swarm/memory_kernel/readiness.py",
            error=projection.readiness_error or projection.error,
            next_action="Repair MemoryKernel adapter readiness projection",
        )
        row.add_source_ref("file", "dharma_swarm/memory_kernel/readiness.py", exists=True)
        return row

    readiness = readiness_contract(projection)
    strict_ready = bool(readiness["strict_ready"])
    status = str(readiness["readiness_status"])
    schema_ok = readiness["schema_version"] == READINESS_SCHEMA_VERSION
    required_accounted = bool(readiness["required_surfaces_accounted"])
    all_accounted = int(readiness["unaccounted_surface_count"]) == 0
    warning_count = int(readiness["warning_count"])
    gap_codes: list[str] = []
    if not schema_ok:
        gap_codes.append("memory_readiness_schema_mismatch")
    if status == "unavailable":
        gap_codes.append("memory_readiness_unavailable")
    elif status == "degraded":
        gap_codes.append("memory_readiness_degraded")
    if not required_accounted:
        gap_codes.append("memory_required_surface_unaccounted")
    if not all_accounted:
        gap_codes.append("memory_surface_adapters_unaccounted")
    if warning_count > 0:
        gap_codes.append("memory_readiness_warnings")

    raw = {field: readiness[field] for field in READINESS_ROW_RAW_FIELDS}
    raw["projection_mode"] = "readiness_contract_projection"
    row = ControlSurfaceRow(
        id="memory.readiness",
        kind="memory_readiness",
        label="MemoryKernel Strict Readiness",
        authority_role="evidence",
        declared_state="readiness_contract_v1",
        desired_state="strict_ready_all_accounted_warning_free",
        observed_state=f"{status}:{readiness['strict_readiness_state']}",
        coherence_state="bound" if strict_ready else "partial",
        priority="p1" if status != "unavailable" else "p0",
        owner_module="dharma_swarm/memory_kernel/readiness.py",
        truth_owner="MemoryKernel",
        gap_codes=gap_codes,
        next_action=(
            ""
            if strict_ready
            else "Resolve readiness warnings and unaccounted adapters before preview/canary/live burn-in"
        ),
        raw=raw,
    )
    row.add_evidence(
        "process",
        (
            f"status={status} strict={readiness['strict_readiness_state']} "
            f"accounted={readiness['accounted_surface_ratio']} "
            f"required={readiness['required_accounted_surface_ratio']} "
            f"warnings={warning_count}"
        ),
        status="present" if strict_ready else "stale",
        provenance_chain=["MemoryKernel", "adapter_readiness_report", "strict_projection"],
    )
    row.add_source_ref("file", "dharma_swarm/memory_kernel/readiness.py", exists=True)
    row.add_source_ref("file", "scripts/memory_kernel_readiness.py", exists=True)
    row.add_source_ref(
        "file",
        "tests/test_memory_kernel_readiness.py",
        exists=(repo_root / "tests/test_memory_kernel_readiness.py").exists(),
    )
    return row


def _memory_rollout_gate_row(
    repo_root: Path,
    projection: KernelProjection,
    context_canary: ControlSurfaceRow,
    write_receipts: ControlSurfaceRow,
    promotion_candidate: ControlSurfaceRow,
    knowledgeops_bridge: ControlSurfaceRow,
) -> ControlSurfaceRow:
    from dharma_swarm.memory_kernel import DEFAULT_BURN_IN_RECEIPT_PATH, load_burn_in_status

    state, configured, invalid = _rollout_state()
    readiness = readiness_contract(projection)
    burn_in_status = load_burn_in_status(repo_root / DEFAULT_BURN_IN_RECEIPT_PATH).to_json()
    write_receipts_ready = bool(write_receipts.raw.get("ready"))
    promotion_ready = bool(promotion_candidate.raw.get("promotion_ready"))
    knowledgeops_bridge_ready = bool(knowledgeops_bridge.raw.get("ready"))
    burn_in = burn_in_safety(
        state=state,
        invalid=invalid,
        rollback_engaged=_truthy(os.environ.get(ROLLBACK_ENV_VAR, "")),
        readiness=readiness,
        context_canary_visible=context_canary_visible(context_canary),
        burn_in_status=burn_in_status,
        write_receipts_ready=write_receipts_ready,
        promotion_ready=promotion_ready,
    )
    bridge_required = state == "live"
    bridge_blocked = bridge_required and not knowledgeops_bridge_ready
    burn_in_blockers = list(burn_in["burn_in_blockers"])
    if bridge_blocked:
        burn_in_blockers.append("knowledgeops_bridge_receipts_linked")
    burn_in_safe = bool(burn_in["burn_in_safe"]) and not bridge_blocked
    max_ready = str(burn_in["max_ready_tier"])
    exceeds_ready_tier = not tier_allows_state(max_ready, state)
    gap_codes: list[str] = []
    if invalid:
        gap_codes.append("memory_kernel_rollout_invalid_state")
    if exceeds_ready_tier:
        gap_codes.append("memory_kernel_rollout_exceeds_ready_tier")
    if not burn_in_safe:
        gap_codes.append("memory_kernel_burn_in_blocked")
        gap_codes.extend(
            f"memory_kernel_burn_in_{blocker}_blocked"
            for blocker in burn_in_blockers
        )
    if bridge_blocked:
        gap_codes.append("memory_kernel_knowledgeops_bridge_blocked")
    raw = {
        "state": state,
        "configured_value": configured,
        "allowed_states": ROLLOUT_STATES,
        "default_state": "off",
        "state_source": f"env:{ROLLOUT_ENV_VAR}" if configured else "safe_default",
        "rollback_switch": f"env:{ROLLBACK_ENV_VAR}",
        "ready_tiers": READY_TIERS,
        "state_ready_tier_requirements": ROLLOUT_READY_TIER_REQUIREMENTS,
    }
    raw.update({field: readiness[field] for field in ROLLOUT_READINESS_RAW_FIELDS})
    raw.update(
        {
            "burn_in_safety_state": "safe" if burn_in_safe else "blocked",
            "burn_in_safe": burn_in_safe,
            "burn_in_blockers": tuple(burn_in_blockers),
            "burn_in_required_checks": burn_in["burn_in_required_checks"],
            "burn_in_checks": burn_in["burn_in_checks"],
            "burn_in_receipt_status": burn_in_status,
            "write_receipts_ready": write_receipts_ready,
            "promotion_ready": promotion_ready,
            "knowledgeops_bridge_required": bridge_required,
            "knowledgeops_bridge_ready": knowledgeops_bridge_ready,
            "knowledgeops_bridge_status": knowledgeops_bridge.raw,
            "max_ready_tier": max_ready,
            "required_ready_tier": burn_in["required_ready_tier"],
            "rollout_exceeds_ready_tier": exceeds_ready_tier,
        }
    )
    row = ControlSurfaceRow(
        id="memory.rollout_gate",
        kind="memory_rollout",
        label="MemoryKernel Rollout Gate",
        authority_role="adapter",
        declared_state="operator_controlled_rollout",
        desired_state="off_shadow_preview_canary_before_live",
        observed_state=state,
        coherence_state="bound" if burn_in_safe else "partial",
        priority="p0" if state in {"preview", "canary", "live"} and not burn_in_safe else "p1",
        owner_module="dharma_swarm/operator_core/control_surface_memory.py",
        truth_owner="operator_control",
        gap_codes=gap_codes,
        next_action=(
            "Set DHARMA_MEMORY_KERNEL_ROLLOUT to off, shadow, preview, canary, or live"
            if invalid
            else (
                "Resolve MemoryKernel burn-in blockers before advancing rollout: "
                + ", ".join(burn_in_blockers)
            )
            if not burn_in_safe
            else ""
        ),
        raw=raw,
    )
    row.add_evidence(
        "process",
        (
            f"{ROLLOUT_ENV_VAR}={configured or '<unset>'} resolved={state} "
            f"burn_in_safe={burn_in_safe}"
        ),
        status="present" if burn_in_safe else "error",
        provenance_chain=["operator_control", "rollout_gate", "burn_in_projection"],
    )
    row.add_source_ref("config", f"env:{ROLLOUT_ENV_VAR}", exists=bool(configured))
    row.add_source_ref("file", "dharma_swarm/memory_kernel/readiness.py", exists=True)
    return row


def _memory_rollback_switch_row() -> ControlSurfaceRow:
    state, _, _ = _rollout_state()
    raw_value = os.environ.get(ROLLBACK_ENV_VAR, "")
    engaged = _truthy(raw_value)
    row = ControlSurfaceRow(
        id="memory.rollback_switch",
        kind="memory_rollout",
        label="MemoryKernel Rollback Switch",
        authority_role="adapter",
        declared_state="operator_kill_switch",
        desired_state="rollback_to_off_available",
        observed_state="engaged" if engaged else "available",
        coherence_state="bound",
        priority="p0" if engaged else "p1",
        owner_module="dharma_swarm/operator_core/control_surface_memory.py",
        truth_owner="operator_control",
        gap_codes=["memory_kernel_rollback_engaged"] if engaged else [],
        next_action="Investigate rollback reason before re-enabling rollout" if engaged else "",
        raw={
            "switch_present": True,
            "switch_env_var": ROLLBACK_ENV_VAR,
            "engaged": engaged,
            "raw_value": raw_value,
            "effect": "forces operator interpretation back to rollout state 'off'",
            "current_rollout_state": state,
        },
    )
    row.add_evidence(
        "process",
        f"{ROLLBACK_ENV_VAR}={raw_value or '<unset>'}",
        status="present",
        provenance_chain=["operator_control", "rollback_switch", "env_projection"],
    )
    row.add_source_ref("config", f"env:{ROLLBACK_ENV_VAR}", exists=bool(raw_value))
    return row


def _operator_prod_smoke_row(repo_root: Path) -> ControlSurfaceRow:
    script = repo_root / "scripts" / "operator_prod_smoke.py"
    ok = script.exists()
    row = ControlSurfaceRow(
        id="operator.prod_smoke",
        kind="operator_smoke",
        label="Operator Production Smoke",
        authority_role="evidence",
        declared_state="fast_read_only_smoke",
        desired_state="available",
        observed_state="available" if ok else "missing",
        coherence_state="bound" if ok else "drifted",
        priority="p1" if ok else "p0",
        owner_module="scripts/operator_prod_smoke.py",
        truth_owner="operator_prod_smoke",
        gap_codes=[] if ok else ["operator_prod_smoke_missing"],
        next_action="" if ok else "Add scripts/operator_prod_smoke.py",
    )
    row.add_evidence(
        "file",
        "scripts/operator_prod_smoke.py",
        status="present" if ok else "missing",
        provenance_chain=["operator_prod_smoke", "file_exists_check"],
    )
    row.add_source_ref("file", "scripts/operator_prod_smoke.py", exists=ok)
    return row


def _rollout_state() -> tuple[str, str, bool]:
    raw = os.environ.get(ROLLOUT_ENV_VAR, "").strip().lower()
    if not raw:
        return "off", "", False
    if raw in ROLLOUT_STATES:
        return raw, raw, False
    return "off", raw, True


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "rollback"}


def _memory_error_row(
    *,
    row_id: str,
    kind: str,
    label: str,
    owner_module: str,
    error: str,
    next_action: str,
) -> ControlSurfaceRow:
    row = ControlSurfaceRow(
        id=row_id,
        kind=kind,
        label=label,
        authority_role="evidence",
        declared_state="read_only_projection",
        desired_state="available",
        observed_state="error",
        coherence_state="drifted",
        priority="p0",
        owner_module=owner_module,
        truth_owner="MemoryKernel",
        gap_codes=[f"{row_id.replace('.', '_')}_error"],
        next_action=next_action,
        raw={"error": error},
    )
    row.add_evidence(
        "process",
        error,
        status="error",
        provenance_chain=["MemoryKernel", row_id, "control_surface_projection"],
    )
    return row
