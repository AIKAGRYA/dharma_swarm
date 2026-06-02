"""CLI renderer for the VentureCell Operator OS projection."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from dharma_swarm.venture_cell.operator_os.daily_digest import write_operator_daily_digest
from dharma_swarm.venture_cell.operator_os.live_loader import load_live_operator_inputs
from dharma_swarm.venture_cell.operator_os.projection import build_operator_projection


def _memory_index_payload(projection: dict[str, Any]) -> dict[str, Any]:
    memory = projection.get("memory_kernel")
    return memory if isinstance(memory, dict) else {}


def _memory_query_eval_payload(projection: dict[str, Any]) -> dict[str, Any]:
    memory = _memory_index_payload(projection)
    return {
        "query_eval_status": memory.get("query_eval_status", "not_run"),
        "query_eval_passed": memory.get("query_eval_passed", 0),
        "query_eval_total": memory.get("query_eval_total", 0),
        "query_eval_results": memory.get("query_eval_results", []),
        "source_roots": memory.get("source_roots", []),
        "trusted_promotion_claimed": any(
            bool(result.get("trusted_promotion_claimed"))
            for result in memory.get("query_eval_results", [])
            if isinstance(result, dict)
        ),
    }


def _memory_coverage_payload(projection: dict[str, Any]) -> dict[str, Any]:
    memory = _memory_index_payload(projection)
    truncated = bool(memory.get("truncated"))
    root_coverage = [
        coverage
        for coverage in memory.get("root_coverage", [])
        if isinstance(coverage, dict)
    ]
    truncated_roots = [
        coverage for coverage in root_coverage if bool(coverage.get("truncated"))
    ]
    local_maintenance_targets = [
        {
            "role": str(coverage.get("role") or coverage.get("tier") or "unknown"),
            "tier": str(coverage.get("tier") or "unknown"),
            "root": str(coverage.get("root") or ""),
            "gap": "memory_kernel_index_truncated",
            "recommended_action": "add_query_specific_source_packet_or_increase_local_scan_budget",
        }
        for coverage in truncated_roots
    ]
    return {
        "schema": "dharma.venture_cell_operator_os.memory_coverage.v0",
        "status": memory.get("status", "unknown"),
        "index_status": memory.get("index_status", "not_built"),
        "indexed_count": memory.get("indexed_count", 0),
        "source_roots": memory.get("source_roots", []),
        "root_coverage": root_coverage,
        "root_count": len(root_coverage),
        "truncated_root_count": len(truncated_roots),
        "untruncated_root_count": len(root_coverage) - len(truncated_roots),
        "truncated_roles": [
            str(coverage.get("role") or coverage.get("tier") or "unknown")
            for coverage in truncated_roots
        ],
        "local_maintenance_targets": local_maintenance_targets,
        "local_maintenance_target_count": len(local_maintenance_targets),
        "truncated": truncated,
        "complete_coverage_claimed": False,
        "locally_actionable_gap": "memory_kernel_index_truncated" if truncated else "",
        "safe_next_action": (
            "Use root coverage to target local read-through maintenance without trusted promotion."
            if truncated
            else "Use current MemoryKernel coverage as bounded local recall evidence."
        ),
        "trusted_promotion_claimed": False,
        "not_authority": True,
    }


def _canvas_summary_payload(projection: dict[str, Any]) -> dict[str, Any]:
    raw_canvas = projection.get("canvas", [])
    canvas = [item for item in raw_canvas if isinstance(item, dict)]
    status_counts = Counter(str(item.get("status") or "unknown") for item in canvas)
    owner_counts = Counter(
        str(item.get("owner_department") or "unassigned") for item in canvas
    )
    lane_buckets: dict[str, list[dict[str, Any]]] = {}
    for item in canvas:
        lane = str(item.get("lane") or "unknown")
        lane_buckets.setdefault(lane, []).append(item)

    lanes = []
    for lane, items in sorted(lane_buckets.items()):
        lane_status_counts = Counter(
            str(item.get("status") or "unknown") for item in items
        )
        lanes.append(
            {
                "lane": lane,
                "item_count": len(items),
                "status_counts": dict(sorted(lane_status_counts.items())),
                "owner_departments": sorted(
                    {
                        str(item.get("owner_department") or "unassigned")
                        for item in items
                    }
                ),
                "item_ids": [
                    str(item.get("item_id") or "")
                    for item in items
                    if str(item.get("item_id") or "")
                ],
            }
        )

    blocked_items = [
        {
            "item_id": str(item.get("item_id") or ""),
            "lane": str(item.get("lane") or "unknown"),
            "status": str(item.get("status") or "unknown"),
            "owner_department": str(item.get("owner_department") or "unassigned"),
            "blocked_reason": str(item.get("blocked_reason") or ""),
        }
        for item in canvas
        if str(item.get("blocked_reason") or "")
    ]

    return {
        "schema": "dharma.venture_cell_operator_os.canvas_summary.v0",
        "status": projection.get("status", "unknown"),
        "autonomy_level": projection.get("autonomy_level", "unknown"),
        "total_item_count": len(canvas),
        "lane_count": len(lanes),
        "lanes": lanes,
        "status_counts": dict(sorted(status_counts.items())),
        "owner_department_counts": dict(sorted(owner_counts.items())),
        "owner_department_count": len(owner_counts),
        "blocked_items": blocked_items,
        "blocked_item_count": len(blocked_items),
        "safe_next_action": (
            "Inspect blocked local canvas items before widening internal execution."
            if blocked_items
            else "Use canvas lane counts as read-only operating context."
        ),
        "not_authority": True,
        "external_authority_granted": False,
        "trusted_promotion_claimed": False,
    }


def _department_summary_payload(projection: dict[str, Any]) -> dict[str, Any]:
    raw_departments = projection.get("departments", [])
    departments = [item for item in raw_departments if isinstance(item, dict)]
    status_counts = Counter(str(item.get("status") or "unknown") for item in departments)
    authority_mode_counts = Counter(
        str(item.get("authority_mode") or "unknown") for item in departments
    )
    blocked_departments = [
        {
            "department_id": str(item.get("department_id") or ""),
            "label": str(item.get("label") or ""),
            "status": str(item.get("status") or "unknown"),
            "authority_mode": str(item.get("authority_mode") or "unknown"),
            "next_action": str(item.get("next_action") or ""),
        }
        for item in departments
        if str(item.get("status") or "").startswith("blocked")
    ]
    department_items = [
        {
            "department_id": str(item.get("department_id") or ""),
            "label": str(item.get("label") or ""),
            "status": str(item.get("status") or "unknown"),
            "authority_mode": str(item.get("authority_mode") or "unknown"),
            "evidence_ref_count": len(
                item.get("evidence_refs", [])
                if isinstance(item.get("evidence_refs"), (list, tuple))
                else []
            ),
        }
        for item in departments
    ]
    return {
        "schema": "dharma.venture_cell_operator_os.department_summary.v0",
        "status": projection.get("status", "unknown"),
        "autonomy_level": projection.get("autonomy_level", "unknown"),
        "total_department_count": len(departments),
        "department_items": department_items,
        "status_counts": dict(sorted(status_counts.items())),
        "status_count": len(status_counts),
        "authority_mode_counts": dict(sorted(authority_mode_counts.items())),
        "authority_mode_count": len(authority_mode_counts),
        "blocked_departments": blocked_departments,
        "blocked_department_count": len(blocked_departments),
        "partial_department_count": int(status_counts.get("partial", 0)),
        "safe_next_action": (
            "Keep blocked departments internal until the required gate evidence exists."
            if blocked_departments
            else "Use department status counts as read-only operating context."
        ),
        "not_authority": True,
        "external_authority_granted": False,
        "trusted_promotion_claimed": False,
    }


def _gate_summary_payload(projection: dict[str, Any]) -> dict[str, Any]:
    raw_gates = projection.get("gates", [])
    gates = [item for item in raw_gates if isinstance(item, dict)]
    decision_counts = Counter(str(item.get("decision") or "unknown") for item in gates)
    coherence_counts = Counter(
        str(item.get("coherence_state") or "unknown") for item in gates
    )
    blocking_gates = [
        {
            "gate_id": str(item.get("gate_id") or ""),
            "label": str(item.get("label") or ""),
            "decision": str(item.get("decision") or "unknown"),
            "coherence_state": str(item.get("coherence_state") or "unknown"),
            "gap_codes": item.get("gap_codes", [])
            if isinstance(item.get("gap_codes"), (list, tuple))
            else [],
            "next_action": str(item.get("next_action") or ""),
        }
        for item in gates
        if str(item.get("decision") or "unknown") != "allow"
    ]
    gate_items = [
        {
            "gate_id": str(item.get("gate_id") or ""),
            "label": str(item.get("label") or ""),
            "decision": str(item.get("decision") or "unknown"),
            "coherence_state": str(item.get("coherence_state") or "unknown"),
            "gap_count": len(
                item.get("gap_codes", [])
                if isinstance(item.get("gap_codes"), (list, tuple))
                else []
            ),
            "evidence_ref_count": len(
                item.get("evidence_refs", [])
                if isinstance(item.get("evidence_refs"), (list, tuple))
                else []
            ),
        }
        for item in gates
    ]
    total_gap_count = sum(int(item["gap_count"]) for item in gate_items)
    return {
        "schema": "dharma.venture_cell_operator_os.gate_summary.v0",
        "status": projection.get("status", "unknown"),
        "autonomy_level": projection.get("autonomy_level", "unknown"),
        "total_gate_count": len(gates),
        "gate_items": gate_items,
        "decision_counts": dict(sorted(decision_counts.items())),
        "decision_count": len(decision_counts),
        "coherence_counts": dict(sorted(coherence_counts.items())),
        "coherence_count": len(coherence_counts),
        "allow_gate_count": int(decision_counts.get("allow", 0)),
        "blocking_gate_count": len(blocking_gates),
        "blocking_gates": blocking_gates,
        "total_gap_count": total_gap_count,
        "safe_next_action": (
            "Inspect blocking gates and required evidence before widening autonomy."
            if blocking_gates
            else "Use gate decision counts as read-only operating context."
        ),
        "not_authority": True,
        "external_authority_granted": False,
        "trusted_promotion_claimed": False,
    }


def _next_action_payload(projection: dict[str, Any]) -> dict[str, Any]:
    packet = projection.get("next_action_packet")
    return packet if isinstance(packet, dict) else {}


def _darshan_go_gate_payload(projection: dict[str, Any]) -> dict[str, Any]:
    packet = projection.get("darshan_go_gate_packet")
    return packet if isinstance(packet, dict) else {}


def _darshan_go_receipt_template_payload(projection: dict[str, Any]) -> dict[str, Any]:
    packet = _darshan_go_gate_payload(projection)
    template = packet.get("receipt_template")
    return template if isinstance(template, dict) else {}


def _memory_repair_payload(projection: dict[str, Any]) -> dict[str, Any]:
    packet = projection.get("memory_kernel_repair_packet")
    return packet if isinstance(packet, dict) else {}


def _authority_boundary_payload(projection: dict[str, Any]) -> dict[str, Any]:
    packet = projection.get("authority_boundary_packet")
    return packet if isinstance(packet, dict) else {}


def _gap_triage_payload(projection: dict[str, Any]) -> dict[str, Any]:
    packet = projection.get("gap_triage_packet")
    return packet if isinstance(packet, dict) else {}


def _completion_guard_payload(projection: dict[str, Any]) -> dict[str, Any]:
    status = str(projection.get("status", "unknown"))
    autonomy_level = str(projection.get("autonomy_level", "unknown"))
    go_gate = _darshan_go_gate_payload(projection)
    authority = _authority_boundary_payload(projection)
    final_closure_blockers = [
        "true_8h_elapsed_time_not_proven",
        "reporter_task_must_remain_open_until_terminal_receipt",
        "complete_verifier_expected_to_fail_until_reporter_closure",
        "final_adversary_score_metabolization_next_goal_review_required",
    ]
    external_authority_blockers = [
        "darshan_external_reader_gate_blocked",
        "accepted_privacy_redacted_go_receipt_missing",
    ] if go_gate.get("decision") == "block_external_authority" else []
    required_final_artifacts = [
        "06_adversary_audit.md",
        "07_score_history.md",
        "08_metabolization_packet.md",
        "09_next_goal_packet.md",
        "final_ds_goal_terminal_receipt",
        "complete_verifier_pass_after_reporter_closure",
    ]
    forbidden_actions = [
        "close_reporter_before_true_time_proof",
        "treat_live_score_as_completion",
        "claim_external_authority",
        "fake_go_receipts",
        "claim_nats_or_a2a_liveness_without_action_ack",
        "trusted_chetana_promotion_without_gates",
    ]
    return {
        "schema": "dharma.venture_cell_operator_os.completion_guard.v0",
        "decision": "keep_reporter_open",
        "status": status,
        "autonomy_level": autonomy_level,
        "not_final": True,
        "live_score_can_be_100_without_completion": True,
        "reporter_task_must_remain_open": True,
        "terminal_reporter_receipt_required": True,
        "complete_verifier_expected_blocker": "reporter_task_not_closed_until_terminal_receipt",
        "reporter_closure_policy": (
            "close only after true-time proof, final artifact review, "
            "terminal reporter receipt, and complete verifier pass"
        ),
        "final_closure_blockers": final_closure_blockers,
        "final_closure_blocker_count": len(final_closure_blockers),
        "external_authority_blockers": external_authority_blockers,
        "external_authority_blocker_count": len(external_authority_blockers),
        "authority_decision": authority.get("decision", "unknown"),
        "darshan_go_decision": go_gate.get("decision", "unknown"),
        "required_final_artifacts": required_final_artifacts,
        "required_final_artifact_count": len(required_final_artifacts),
        "forbidden_actions": forbidden_actions,
        "forbidden_action_count": len(forbidden_actions),
        "not_authority": True,
    }


def _latest_progress_receipt_id(latest_receipt_path: str) -> str:
    if not latest_receipt_path:
        return ""
    try:
        lines = Path(latest_receipt_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    prefix = "ds-goal progress receipt:"
    for line in lines:
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip().strip("`")
    return ""


def _artifact_manifest_payload(
    *,
    projection: dict[str, Any],
    artifact_paths: dict[str, Path],
    output_dir: Path,
) -> dict[str, Any]:
    memory = _memory_index_payload(projection)
    go_gate = _darshan_go_gate_payload(projection)
    authority = _authority_boundary_payload(projection)
    gap_triage = _gap_triage_payload(projection)
    memory_coverage = _memory_coverage_payload(projection)
    canvas_summary = _canvas_summary_payload(projection)
    department_summary = _department_summary_payload(projection)
    gate_summary = _gate_summary_payload(projection)
    completion_guard = _completion_guard_payload(projection)
    receipt_paths = [
        str(path)
        for path in sorted(output_dir.glob("*.md"))
        if path.name != "operator_os_digest.md"
    ]
    latest_receipt_path = receipt_paths[-1] if receipt_paths else ""
    latest_progress_receipt_id = _latest_progress_receipt_id(latest_receipt_path)
    return {
        "schema": "dharma.venture_cell_operator_os.render_manifest.v0",
        "status": projection.get("status", "unknown"),
        "autonomy_level": projection.get("autonomy_level", "unknown"),
        "memory_query_eval_status": memory.get("query_eval_status", "not_run"),
        "memory_query_eval_passed": memory.get("query_eval_passed", 0),
        "memory_query_eval_total": memory.get("query_eval_total", 0),
        "darshan_go_decision": go_gate.get("decision", "unknown"),
        "authority_decision": authority.get("decision", "unknown"),
        "gap_triage_decision": gap_triage.get("decision", "unknown"),
        "memory_coverage_truncated": memory_coverage.get("truncated", False),
        "memory_coverage_truncated_root_count": memory_coverage.get(
            "truncated_root_count", 0
        ),
        "canvas_item_count": canvas_summary.get("total_item_count", 0),
        "canvas_lane_count": canvas_summary.get("lane_count", 0),
        "canvas_blocked_item_count": canvas_summary.get("blocked_item_count", 0),
        "department_count": department_summary.get("total_department_count", 0),
        "department_blocked_count": department_summary.get("blocked_department_count", 0),
        "department_partial_count": department_summary.get("partial_department_count", 0),
        "gate_count": gate_summary.get("total_gate_count", 0),
        "gate_allow_count": gate_summary.get("allow_gate_count", 0),
        "gate_blocking_count": gate_summary.get("blocking_gate_count", 0),
        "completion_guard_decision": completion_guard.get("decision", "unknown"),
        "not_final": completion_guard.get("not_final", True),
        "artifact_paths": {
            name: str(path)
            for name, path in sorted(artifact_paths.items())
            if name != "artifact_manifest"
        },
        "receipt_paths": receipt_paths,
        "receipt_count": len(receipt_paths),
        "latest_receipt_path": latest_receipt_path,
        "latest_receipt_name": Path(latest_receipt_path).name if latest_receipt_path else "",
        "latest_progress_receipt_id": latest_progress_receipt_id,
        "latest_progress_receipt_id_source": latest_receipt_path
        if latest_progress_receipt_id
        else "",
        "receipt_inventory_has_progress_id": bool(latest_progress_receipt_id),
        "latest_progress_receipt_id_not_final": True,
        "receipt_inventory_scope": "run_markdown_receipts_excluding_digest",
        "receipt_inventory_not_final": True,
        "receipt_inventory_not_authority": True,
        "not_authority": True,
    }


def render_operator_surface(
    *,
    output_dir: Path,
    bundle_path: Path | None = None,
    state_root: Path | None = None,
    task_db_path: Path | None = None,
    task_limit: int = 50,
    a2a_limit: int = 50,
    max_memory_scan: int = 5000,
) -> dict[str, Path]:
    """Render the local Operator OS projection artifacts."""

    inputs = load_live_operator_inputs(
        bundle_path=bundle_path,
        state_root=state_root,
        task_db_path=task_db_path,
        task_limit=task_limit,
        a2a_limit=a2a_limit,
        supplemental_memory_roots=(output_dir,),
        max_memory_scan=max_memory_scan,
    )
    projection = build_operator_projection(inputs)
    output_dir.mkdir(parents=True, exist_ok=True)

    projection_path = output_dir / "operator_os_projection.json"
    projection_path.write_text(
        json.dumps(projection.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest_path = write_operator_daily_digest(
        projection,
        output_dir / "operator_os_digest.md",
    )
    memory_index_path = output_dir / "memory_kernel_index.json"
    memory_index_path.write_text(
        json.dumps(
            _memory_index_payload(projection.to_dict()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    memory_query_eval_path = output_dir / "memory_kernel_query_eval.json"
    memory_query_eval_path.write_text(
        json.dumps(
            _memory_query_eval_payload(projection.to_dict()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    memory_coverage_path = output_dir / "memory_kernel_coverage_packet.json"
    memory_coverage_path.write_text(
        json.dumps(
            _memory_coverage_payload(projection.to_dict()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    next_action_packet_path = output_dir / "operator_next_action_packet.json"
    next_action_packet_path.write_text(
        json.dumps(
            _next_action_payload(projection.to_dict()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    darshan_go_gate_packet_path = output_dir / "darshan_go_gate_packet.json"
    darshan_go_gate_packet_path.write_text(
        json.dumps(
            _darshan_go_gate_payload(projection.to_dict()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    darshan_go_receipt_template_path = output_dir / "darshan_go_receipt_template.json"
    darshan_go_receipt_template_path.write_text(
        json.dumps(
            _darshan_go_receipt_template_payload(projection.to_dict()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    memory_repair_packet_path = output_dir / "memory_kernel_repair_packet.json"
    memory_repair_packet_path.write_text(
        json.dumps(
            _memory_repair_payload(projection.to_dict()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    authority_boundary_packet_path = output_dir / "authority_boundary_packet.json"
    authority_boundary_packet_path.write_text(
        json.dumps(
            _authority_boundary_payload(projection.to_dict()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    gap_triage_packet_path = output_dir / "operator_gap_triage_packet.json"
    gap_triage_packet_path.write_text(
        json.dumps(
            _gap_triage_payload(projection.to_dict()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    canvas_summary_path = output_dir / "operator_canvas_summary_packet.json"
    canvas_summary_path.write_text(
        json.dumps(
            _canvas_summary_payload(projection.to_dict()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    department_summary_path = output_dir / "operator_department_summary_packet.json"
    department_summary_path.write_text(
        json.dumps(
            _department_summary_payload(projection.to_dict()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    gate_summary_path = output_dir / "operator_gate_summary_packet.json"
    gate_summary_path.write_text(
        json.dumps(
            _gate_summary_payload(projection.to_dict()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    completion_guard_path = output_dir / "operator_completion_guard_packet.json"
    completion_guard_path.write_text(
        json.dumps(
            _completion_guard_payload(projection.to_dict()),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths = {
        "projection": projection_path,
        "digest": digest_path,
        "memory_index": memory_index_path,
        "memory_query_eval": memory_query_eval_path,
        "memory_coverage_packet": memory_coverage_path,
        "next_action_packet": next_action_packet_path,
        "darshan_go_gate_packet": darshan_go_gate_packet_path,
        "darshan_go_receipt_template": darshan_go_receipt_template_path,
        "memory_kernel_repair_packet": memory_repair_packet_path,
        "authority_boundary_packet": authority_boundary_packet_path,
        "gap_triage_packet": gap_triage_packet_path,
        "canvas_summary_packet": canvas_summary_path,
        "department_summary_packet": department_summary_path,
        "gate_summary_packet": gate_summary_path,
        "completion_guard_packet": completion_guard_path,
    }
    artifact_manifest_path = output_dir / "operator_os_artifact_manifest.json"
    paths["artifact_manifest"] = artifact_manifest_path
    artifact_manifest_path.write_text(
        json.dumps(
            _artifact_manifest_payload(
                projection=projection.to_dict(),
                artifact_paths=paths,
                output_dir=output_dir,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return paths


def main(argv: list[str] | None = None) -> int:
    return _main(argv)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render a local VentureCell Operator OS projection."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    render_operator_surface(output_dir=args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
