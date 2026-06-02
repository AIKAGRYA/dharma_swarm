"""CLI renderer for the VentureCell Operator OS projection."""

from __future__ import annotations

import argparse
import json
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
    return {
        "schema": "dharma.venture_cell_operator_os.memory_coverage.v0",
        "status": memory.get("status", "unknown"),
        "index_status": memory.get("index_status", "not_built"),
        "indexed_count": memory.get("indexed_count", 0),
        "source_roots": memory.get("source_roots", []),
        "root_coverage": memory.get("root_coverage", []),
        "truncated": truncated,
        "locally_actionable_gap": "memory_kernel_index_truncated" if truncated else "",
        "safe_next_action": (
            "Use root coverage to target local read-through maintenance without trusted promotion."
            if truncated
            else "Use current MemoryKernel coverage as bounded local recall evidence."
        ),
        "trusted_promotion_claimed": False,
        "not_authority": True,
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
    return {
        "schema": "dharma.venture_cell_operator_os.completion_guard.v0",
        "decision": "keep_reporter_open",
        "status": status,
        "autonomy_level": autonomy_level,
        "not_final": True,
        "live_score_can_be_100_without_completion": True,
        "final_closure_blockers": [
            "true_8h_elapsed_time_not_proven",
            "reporter_task_must_remain_open_until_terminal_receipt",
            "complete_verifier_expected_to_fail_until_reporter_closure",
            "final_adversary_score_metabolization_next_goal_review_required",
        ],
        "external_authority_blockers": [
            "darshan_external_reader_gate_blocked",
            "accepted_privacy_redacted_go_receipt_missing",
        ]
        if go_gate.get("decision") == "block_external_authority"
        else [],
        "authority_decision": authority.get("decision", "unknown"),
        "darshan_go_decision": go_gate.get("decision", "unknown"),
        "required_final_artifacts": [
            "06_adversary_audit.md",
            "07_score_history.md",
            "08_metabolization_packet.md",
            "09_next_goal_packet.md",
            "final_ds_goal_terminal_receipt",
            "complete_verifier_pass_after_reporter_closure",
        ],
        "forbidden_actions": [
            "close_reporter_before_true_time_proof",
            "treat_live_score_as_completion",
            "claim_external_authority",
            "fake_go_receipts",
            "claim_nats_or_a2a_liveness_without_action_ack",
            "trusted_chetana_promotion_without_gates",
        ],
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
    authority = _authority_boundary_payload(projection)
    gap_triage = _gap_triage_payload(projection)
    memory_coverage = _memory_coverage_payload(projection)
    completion_guard = _completion_guard_payload(projection)
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
        "completion_guard_decision": completion_guard.get("decision", "unknown"),
        "not_final": completion_guard.get("not_final", True),
        "artifact_paths": {
            name: str(path)
            for name, path in sorted(artifact_paths.items())
            if name != "artifact_manifest"
        },
        "receipt_paths": [
            str(path)
            for path in sorted(output_dir.glob("*.md"))
            if path.name != "operator_os_digest.md"
        ],
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
