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

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _sequence_items(value: Any) -> tuple[Any, ...]:
    return tuple(value) if isinstance(value, (list, tuple)) else ()


def _dict_items(value: Any) -> list[dict[str, Any]]:
    return [item for item in _sequence_items(value) if isinstance(item, dict)]


def _sequence_count(value: Any) -> int:
    return len(_sequence_items(value))


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
    root_coverage = _dict_items(memory.get("root_coverage", []))
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
    canvas = _dict_items(projection.get("canvas", []))
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
    departments = _dict_items(projection.get("departments", []))
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
            "evidence_ref_count": _sequence_count(item.get("evidence_refs")),
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
    gates = _dict_items(projection.get("gates", []))
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
            "gap_codes": _sequence_items(item.get("gap_codes")),
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
            "gap_count": _sequence_count(item.get("gap_codes")),
            "evidence_ref_count": _sequence_count(item.get("evidence_refs")),
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


def _evidence_summary_payload(projection: dict[str, Any]) -> dict[str, Any]:
    refs = [
        str(ref)
        for ref in _sequence_items(projection.get("evidence_refs", []))
        if str(ref or "").strip()
    ]
    evidence_items: list[dict[str, Any]] = []
    for ref in refs:
        path = Path(ref)
        is_external_url = ref.startswith(("http://", "https://"))
        is_absolute = path.is_absolute()
        exists = False if is_external_url else path.exists()
        evidence_items.append(
            {
                "ref": ref,
                "classification": (
                    "external_url"
                    if is_external_url
                    else "absolute_local_path"
                    if is_absolute
                    else "relative_local_path"
                ),
                "is_absolute": is_absolute,
                "exists": exists,
            }
        )
    absolute_count = sum(1 for item in evidence_items if bool(item["is_absolute"]))
    external_url_count = sum(
        1 for item in evidence_items if item["classification"] == "external_url"
    )
    existing_local_count = sum(
        1
        for item in evidence_items
        if item["classification"] != "external_url" and bool(item["exists"])
    )
    return {
        "schema": "dharma.venture_cell_operator_os.evidence_summary.v0",
        "status": projection.get("status", "unknown"),
        "autonomy_level": projection.get("autonomy_level", "unknown"),
        "total_evidence_ref_count": len(evidence_items),
        "evidence_items": evidence_items,
        "absolute_ref_count": absolute_count,
        "relative_ref_count": len(evidence_items) - absolute_count - external_url_count,
        "external_url_count": external_url_count,
        "existing_local_ref_count": existing_local_count,
        "safe_next_action": (
            "Inspect evidence refs directly before using them in gate, authority, or finality claims."
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


def _required_receipt_field_groups(fields: tuple[Any, ...]) -> list[dict[str, Any]]:
    groups: dict[str, list[str]] = {
        "top_level": [],
        "payload": [],
        "other_nested": [],
    }
    for field_value in fields:
        field = str(field_value or "").strip()
        if not field:
            continue
        if field.startswith("payload."):
            groups["payload"].append(field)
        elif "." in field:
            groups["other_nested"].append(field)
        else:
            groups["top_level"].append(field)
    return [
        {
            "group": group,
            "field_count": len(values),
            "fields": values,
        }
        for group, values in groups.items()
        if values
    ]


def _expected_local_artifact_items(
    refs: tuple[Any, ...],
    *,
    output_dir: Path | None = None,
) -> list[dict[str, Any]]:
    artifact_items: list[dict[str, Any]] = []
    for ref_value in refs:
        ref = str(ref_value or "").strip()
        if not ref:
            continue
        path = Path(ref)
        contains_placeholder = "<" in ref and ">" in ref
        is_external_url = ref.startswith(("http://", "https://"))
        classification = "external_url"
        resolution_base = ""
        resolved_path = ""
        exists = False
        parent_exists = False
        if is_external_url:
            resolution_status = "external_url_not_local_artifact"
        else:
            if path.is_absolute():
                resolved = path
                classification = "absolute_local_path"
                resolution_base = "absolute"
            elif output_dir is not None and path.name == ref:
                resolved = output_dir / path
                classification = "report_local_path"
                resolution_base = "output_dir"
            else:
                resolved = _REPO_ROOT / path
                classification = "repo_relative_path"
                resolution_base = "repo_root"
            resolved_path = str(resolved)
            parent_exists = resolved.parent.exists()
            exists = False if contains_placeholder else resolved.exists()
            resolution_status = (
                "placeholder_waits_for_accepted_go_receipt"
                if contains_placeholder
                else "exists"
                if exists
                else "missing"
            )
        artifact_items.append(
            {
                "ref": ref,
                "classification": classification,
                "resolution_base": resolution_base,
                "resolved_path": resolved_path,
                "contains_placeholder": contains_placeholder,
                "parent_exists": parent_exists,
                "exists": exists,
                "resolution_status": resolution_status,
            }
        )
    return artifact_items


def _darshan_go_unblock_payload(
    projection: dict[str, Any],
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    go_gate = _darshan_go_gate_payload(projection)
    authority = _authority_boundary_payload(projection)
    accepted_receipts = _sequence_items(go_gate.get("accepted_receipts"))
    rejected_receipts = _sequence_items(go_gate.get("rejected_receipts"))
    missing_receipts = _sequence_items(go_gate.get("missing_receipts"))
    expected_local_artifacts = _sequence_items(go_gate.get("expected_local_artifacts"))
    required_receipt_fields = _sequence_items(go_gate.get("required_receipt_fields"))
    required_receipt_field_groups = _required_receipt_field_groups(
        required_receipt_fields
    )
    required_receipt_field_counts = {
        str(item["group"]): int(item["field_count"])
        for item in required_receipt_field_groups
    }
    blocked_actions = _sequence_items(go_gate.get("blocked_actions"))
    blocked_departments = _sequence_items(go_gate.get("blocked_departments"))
    expected_local_artifact_items = _expected_local_artifact_items(
        expected_local_artifacts,
        output_dir=output_dir,
    )
    existing_artifact_count = sum(
        1 for item in expected_local_artifact_items if bool(item.get("exists"))
    )
    pending_placeholder_count = sum(
        1
        for item in expected_local_artifact_items
        if bool(item.get("contains_placeholder"))
    )
    missing_artifact_count = sum(
        1
        for item in expected_local_artifact_items
        if item.get("resolution_status") == "missing"
    )
    parent_exists_count = sum(
        1 for item in expected_local_artifact_items if bool(item.get("parent_exists"))
    )
    external_artifact_count = sum(
        1
        for item in expected_local_artifact_items
        if item.get("classification") == "external_url"
    )
    readiness = (
        "missing_expected_local_artifacts"
        if missing_artifact_count
        else "local_artifacts_present_except_go_receipt_placeholder"
        if pending_placeholder_count
        else "all_expected_local_artifacts_present"
    )
    return {
        "schema": "dharma.venture_cell_operator_os.darshan_go_unblock.v0",
        "status": projection.get("status", "unknown"),
        "autonomy_level": projection.get("autonomy_level", "unknown"),
        "decision": "wait_for_accepted_external_reader_go_receipt",
        "darshan_go_decision": go_gate.get("decision", "unknown"),
        "authority_decision": authority.get("decision", "unknown"),
        "why_external_reader_required": go_gate.get(
            "why_external_reader_required", ""
        ),
        "required_receipt_schema": go_gate.get("required_receipt_schema", ""),
        "required_receipt_source": go_gate.get("required_receipt_source", ""),
        "required_receipt_fields": required_receipt_fields,
        "required_receipt_field_count": len(required_receipt_fields),
        "required_receipt_field_groups": required_receipt_field_groups,
        "required_receipt_field_group_count": len(required_receipt_field_groups),
        "required_receipt_top_level_field_count": required_receipt_field_counts.get(
            "top_level", 0
        ),
        "required_receipt_payload_field_count": required_receipt_field_counts.get(
            "payload", 0
        ),
        "required_receipt_other_nested_field_count": required_receipt_field_counts.get(
            "other_nested", 0
        ),
        "expected_local_artifacts": expected_local_artifacts,
        "expected_local_artifact_count": len(expected_local_artifacts),
        "expected_local_artifact_items": expected_local_artifact_items,
        "expected_local_artifact_item_count": len(expected_local_artifact_items),
        "expected_local_artifact_existing_count": existing_artifact_count,
        "expected_local_artifact_missing_count": missing_artifact_count,
        "expected_local_artifact_pending_placeholder_count": pending_placeholder_count,
        "expected_local_artifact_parent_exists_count": parent_exists_count,
        "expected_local_artifact_external_ref_count": external_artifact_count,
        "expected_local_artifact_all_local": external_artifact_count == 0,
        "expected_local_artifact_readiness": readiness,
        "accepted_receipts": accepted_receipts,
        "accepted_receipt_count": len(accepted_receipts),
        "rejected_receipts": rejected_receipts,
        "rejected_receipt_count": len(rejected_receipts),
        "missing_receipts": missing_receipts,
        "missing_receipt_count": len(missing_receipts),
        "blocked_actions": blocked_actions,
        "blocked_action_count": len(blocked_actions),
        "blocked_departments": blocked_departments,
        "blocked_department_count": len(blocked_departments),
        "safe_local_prework": [
            "inspect_expected_local_artifacts",
            "prepare_privacy_redacted_receipt_shape_only_after_real_event",
            "keep_growth_and_communications_internal",
        ],
        "safe_local_prework_count": 3,
        "forbidden_actions": [
            "create_fake_go_receipt",
            "mark_template_as_accepted",
            "perform_external_outreach",
            "publish_or_handoff_externally",
            "claim_live_external_authority",
        ],
        "forbidden_action_count": 5,
        "not_receipt": True,
        "not_evidence": True,
        "not_authority": True,
        "external_authority_granted": False,
        "trusted_promotion_claimed": False,
    }


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
    go_unblock = _darshan_go_unblock_payload(projection)
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
    return _progress_receipt_id_from_path(Path(latest_receipt_path))


def _receipt_markdown_paths(output_dir: Path) -> list[Path]:
    return sorted(
        path for path in output_dir.glob("*.md") if path.name != "operator_os_digest.md"
    )


def _progress_receipt_id_from_path(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    prefix = "ds-goal progress receipt:"
    for line in lines:
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip().strip("`")
    return ""


def _goal_truth_payload(
    *,
    projection: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    receipt_items = []
    for path in _receipt_markdown_paths(output_dir):
        progress_receipt_id = _progress_receipt_id_from_path(path)
        receipt_items.append(
            {
                "name": path.name,
                "path": str(path),
                "progress_receipt_id": progress_receipt_id,
                "has_progress_receipt_id": bool(progress_receipt_id),
            }
        )

    progress_receipt_ids = [
        str(item["progress_receipt_id"])
        for item in receipt_items
        if item["has_progress_receipt_id"]
    ]
    receipt_names_by_progress_id: dict[str, list[str]] = {}
    for item in receipt_items:
        progress_receipt_id = str(item["progress_receipt_id"])
        if progress_receipt_id:
            receipt_names_by_progress_id.setdefault(progress_receipt_id, []).append(
                str(item["name"])
            )
    progress_id_counts = Counter(progress_receipt_ids)
    duplicate_progress_receipt_ids = [
        receipt_id
        for receipt_id, count in sorted(progress_id_counts.items())
        if count > 1
    ]
    duplicate_progress_receipt_groups = [
        {
            "progress_receipt_id": receipt_id,
            "count": int(progress_id_counts[receipt_id]),
            "receipt_names": receipt_names_by_progress_id.get(receipt_id, []),
        }
        for receipt_id in duplicate_progress_receipt_ids
    ]
    missing_progress_receipt_names = [
        str(item["name"]) for item in receipt_items if not item["has_progress_receipt_id"]
    ]
    latest_receipt = receipt_items[-1] if receipt_items else {}
    completion_guard = _completion_guard_payload(projection)

    return {
        "schema": "dharma.venture_cell_operator_os.goal_truth.v0",
        "status": projection.get("status", "unknown"),
        "autonomy_level": projection.get("autonomy_level", "unknown"),
        "truth_source": "report_directory_markdown_receipt_headers",
        "receipt_inventory_scope": "run_markdown_receipts_excluding_digest",
        "receipts": receipt_items,
        "receipt_count": len(receipt_items),
        "progress_receipt_ids": progress_receipt_ids,
        "progress_receipt_id_counts": dict(sorted(progress_id_counts.items())),
        "progress_receipt_count": len(progress_receipt_ids),
        "unique_progress_receipt_id_count": len(progress_id_counts),
        "duplicate_progress_receipt_ids": duplicate_progress_receipt_ids,
        "duplicate_progress_receipt_id_count": len(duplicate_progress_receipt_ids),
        "duplicate_progress_receipt_groups": duplicate_progress_receipt_groups,
        "duplicate_progress_receipt_group_count": len(
            duplicate_progress_receipt_groups
        ),
        "missing_progress_receipt_names": missing_progress_receipt_names,
        "missing_progress_receipt_count": len(missing_progress_receipt_names),
        "all_receipts_have_progress_receipts": not missing_progress_receipt_names,
        "latest_receipt_name": str(latest_receipt.get("name", "")),
        "latest_receipt_path": str(latest_receipt.get("path", "")),
        "latest_progress_receipt_id": str(
            latest_receipt.get("progress_receipt_id", "")
        ),
        "receipt_chain_complete_claimed": False,
        "reporter_task_policy": completion_guard.get("reporter_closure_policy", ""),
        "reporter_task_must_remain_open": completion_guard.get(
            "reporter_task_must_remain_open", True
        ),
        "terminal_reporter_receipt_required": completion_guard.get(
            "terminal_reporter_receipt_required", True
        ),
        "complete_verifier_expected_blocker": completion_guard.get(
            "complete_verifier_expected_blocker", ""
        ),
        "complete_verifier_pass_claimed": False,
        "not_final": True,
        "not_authority": True,
    }


def _artifact_manifest_payload(
    *,
    projection: dict[str, Any],
    artifact_paths: dict[str, Path],
    output_dir: Path,
) -> dict[str, Any]:
    memory = _memory_index_payload(projection)
    go_gate = _darshan_go_gate_payload(projection)
    go_unblock = _darshan_go_unblock_payload(projection, output_dir=output_dir)
    authority = _authority_boundary_payload(projection)
    gap_triage = _gap_triage_payload(projection)
    memory_coverage = _memory_coverage_payload(projection)
    canvas_summary = _canvas_summary_payload(projection)
    department_summary = _department_summary_payload(projection)
    gate_summary = _gate_summary_payload(projection)
    evidence_summary = _evidence_summary_payload(projection)
    completion_guard = _completion_guard_payload(projection)
    goal_truth = _goal_truth_payload(projection=projection, output_dir=output_dir)
    receipt_paths = [str(path) for path in _receipt_markdown_paths(output_dir)]
    latest_receipt_path = receipt_paths[-1] if receipt_paths else ""
    latest_progress_receipt_id = _latest_progress_receipt_id(latest_receipt_path)
    artifact_path_map = {
        name: str(path)
        for name, path in sorted(artifact_paths.items())
        if name != "artifact_manifest"
    }
    summary_packet_names = [
        name for name in sorted(artifact_path_map) if name.endswith("_summary_packet")
    ]
    return {
        "schema": "dharma.venture_cell_operator_os.render_manifest.v0",
        "status": projection.get("status", "unknown"),
        "autonomy_level": projection.get("autonomy_level", "unknown"),
        "memory_query_eval_status": memory.get("query_eval_status", "not_run"),
        "memory_query_eval_passed": memory.get("query_eval_passed", 0),
        "memory_query_eval_total": memory.get("query_eval_total", 0),
        "darshan_go_decision": go_gate.get("decision", "unknown"),
        "darshan_go_unblock_decision": go_unblock.get("decision", "unknown"),
        "darshan_go_unblock_required_receipt_field_count": go_unblock.get(
            "required_receipt_field_count", 0
        ),
        "darshan_go_unblock_required_receipt_field_group_count": go_unblock.get(
            "required_receipt_field_group_count", 0
        ),
        "darshan_go_unblock_required_receipt_top_level_field_count": go_unblock.get(
            "required_receipt_top_level_field_count", 0
        ),
        "darshan_go_unblock_required_receipt_payload_field_count": go_unblock.get(
            "required_receipt_payload_field_count", 0
        ),
        "darshan_go_unblock_expected_local_artifact_count": go_unblock.get(
            "expected_local_artifact_count", 0
        ),
        "darshan_go_unblock_expected_local_artifact_existing_count": go_unblock.get(
            "expected_local_artifact_existing_count", 0
        ),
        "darshan_go_unblock_expected_local_artifact_missing_count": go_unblock.get(
            "expected_local_artifact_missing_count", 0
        ),
        "darshan_go_unblock_expected_local_artifact_pending_placeholder_count": go_unblock.get(
            "expected_local_artifact_pending_placeholder_count", 0
        ),
        "darshan_go_unblock_blocked_action_count": go_unblock.get(
            "blocked_action_count", 0
        ),
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
        "evidence_ref_count": evidence_summary.get("total_evidence_ref_count", 0),
        "existing_local_evidence_ref_count": evidence_summary.get(
            "existing_local_ref_count", 0
        ),
        "absolute_evidence_ref_count": evidence_summary.get("absolute_ref_count", 0),
        "relative_evidence_ref_count": evidence_summary.get("relative_ref_count", 0),
        "completion_guard_decision": completion_guard.get("decision", "unknown"),
        "goal_truth_progress_receipt_count": goal_truth.get(
            "progress_receipt_count", 0
        ),
        "goal_truth_unique_progress_receipt_id_count": goal_truth.get(
            "unique_progress_receipt_id_count", 0
        ),
        "goal_truth_missing_progress_receipt_count": goal_truth.get(
            "missing_progress_receipt_count", 0
        ),
        "goal_truth_duplicate_progress_receipt_id_count": goal_truth.get(
            "duplicate_progress_receipt_id_count", 0
        ),
        "goal_truth_duplicate_progress_receipt_group_count": goal_truth.get(
            "duplicate_progress_receipt_group_count", 0
        ),
        "not_final": completion_guard.get("not_final", True),
        "artifact_paths": artifact_path_map,
        "artifact_count": len(artifact_path_map),
        "json_artifact_count": sum(
            1 for path in artifact_path_map.values() if Path(path).suffix == ".json"
        ),
        "markdown_artifact_count": sum(
            1 for path in artifact_path_map.values() if Path(path).suffix == ".md"
        ),
        "summary_packet_names": summary_packet_names,
        "summary_packet_count": len(summary_packet_names),
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
    darshan_go_unblock_packet_path = output_dir / "darshan_go_unblock_packet.json"
    darshan_go_unblock_packet_path.write_text(
        json.dumps(
            _darshan_go_unblock_payload(projection.to_dict(), output_dir=output_dir),
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
    evidence_summary_path = output_dir / "operator_evidence_summary_packet.json"
    evidence_summary_path.write_text(
        json.dumps(
            _evidence_summary_payload(projection.to_dict()),
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
    goal_truth_path = output_dir / "operator_goal_truth_packet.json"
    goal_truth_path.write_text(
        json.dumps(
            _goal_truth_payload(
                projection=projection.to_dict(),
                output_dir=output_dir,
            ),
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
        "darshan_go_unblock_packet": darshan_go_unblock_packet_path,
        "memory_kernel_repair_packet": memory_repair_packet_path,
        "authority_boundary_packet": authority_boundary_packet_path,
        "gap_triage_packet": gap_triage_packet_path,
        "canvas_summary_packet": canvas_summary_path,
        "department_summary_packet": department_summary_path,
        "gate_summary_packet": gate_summary_path,
        "evidence_summary_packet": evidence_summary_path,
        "completion_guard_packet": completion_guard_path,
        "goal_truth_packet": goal_truth_path,
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
