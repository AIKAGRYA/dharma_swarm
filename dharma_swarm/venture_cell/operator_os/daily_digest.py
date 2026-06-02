"""Markdown digest for the VentureCell Operator OS projection."""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.venture_cell.operator_os.schema import VentureCellOperatorProjection


def render_operator_daily_digest(projection: VentureCellOperatorProjection) -> str:
    """Render the projection into a compact operator digest."""

    lines = [
        f"# VentureCell Operator OS Digest: {projection.venture_cell_id}",
        "",
        f"- Status: `{projection.status}`",
        f"- Autonomy: `{projection.autonomy_level}`",
        f"- Artifact: `{projection.artifact_id or 'none'}`",
        "",
        "## Departments",
        "",
    ]
    for department in projection.departments:
        lines.append(
            f"- `{department.department_id}` {department.label}: "
            f"{department.status}; surface `{department.ds_surface}`; authority `{department.authority_mode}`."
        )

    lines.extend(["", "## Canvas", ""])
    for item in projection.canvas:
        blocked = f"; blocked `{item.blocked_reason}`" if item.blocked_reason else ""
        lines.append(f"- `{item.lane}` {item.title}: `{item.status}`{blocked}.")

    lines.extend(["", "## Gates", ""])
    for gate in projection.gates:
        gaps = ", ".join(gate.gap_codes) if gate.gap_codes else "none"
        lines.append(
            f"- `{gate.gate_id}` decision `{gate.decision}`; "
            f"coherence `{gate.coherence_state}`; gaps `{gaps}`."
        )

    authority = projection.authority_boundary_packet
    blocked_authority_actions = (
        ", ".join(authority.blocked_actions[:8]) if authority.blocked_actions else "none"
    )
    lines.extend(
        [
            "",
            "## Authority Boundary",
            "",
            f"- Decision: `{authority.decision}`",
            f"- Allowed local actions: `{', '.join(authority.allowed_local_actions)}`",
            f"- Blocked actions: `{blocked_authority_actions}`",
            "- Operator OS NATS action ack proof: "
            f"`{authority.liveness_claims.get('operator_os_nats_action_ack_proof_present', False)}`",
            "- Operator OS A2A live action ack proof: "
            f"`{authority.liveness_claims.get('operator_os_a2a_live_action_ack_proof_present', False)}`",
            f"- Trusted Chetana promotion claimed: `{authority.promotion_claims.get('trusted_chetana_promotion_claimed', False)}`",
        ]
    )

    go_gate = projection.darshan_go_gate_packet
    blocked_actions = ", ".join(go_gate.blocked_actions) if go_gate.blocked_actions else "none"
    expected_artifacts = (
        ", ".join(go_gate.expected_local_artifacts) if go_gate.expected_local_artifacts else "none"
    )
    receipt_template_status = str(
        go_gate.receipt_template.get("template_status") or "not_rendered"
    )
    lines.extend(
        [
            "",
            "## Darshan GO Gate",
            "",
            f"- Decision: `{go_gate.decision}`",
            f"- Authority boundary: `{go_gate.authority_boundary}`",
            f"- Required source: `{go_gate.required_receipt_source}`",
            f"- Required schema: `{go_gate.required_receipt_schema}`",
            f"- Countable events: `{', '.join(go_gate.countable_event_types)}`",
            f"- Blocked actions: `{blocked_actions}`",
            f"- Expected local artifacts: `{expected_artifacts}`",
            f"- Receipt template: `{receipt_template_status}`",
            f"- Next governed action: {go_gate.next_governed_action}",
        ]
    )

    packet = projection.next_action_packet
    blockers = ", ".join(packet.blockers) if packet.blockers else "none"
    blocked_departments = (
        ", ".join(packet.blocked_departments) if packet.blocked_departments else "none"
    )
    lines.extend(
        [
            "",
            "## Next Action Packet",
            "",
            f"- Decision: `{packet.decision}`",
            f"- Owner: `{packet.owner_department}`",
            f"- Next governed action: {packet.next_governed_action}",
            f"- Blocked departments: `{blocked_departments}`",
            f"- Required unblock artifact: {packet.required_unblock_artifact or 'none'}",
            f"- Memory query evals: `{packet.memory_query_eval_status}` "
            f"({packet.memory_query_eval_passed}/{packet.memory_query_eval_total})",
            f"- Blockers: `{blockers}`",
        ]
    )

    triage = projection.gap_triage_packet
    local_gaps = (
        ", ".join(triage.locally_actionable_gaps)
        if triage.locally_actionable_gaps
        else "none"
    )
    external_gaps = (
        ", ".join(triage.external_authority_required_gaps)
        if triage.external_authority_required_gaps
        else "none"
    )
    lines.extend(
        [
            "",
            "## Gap Triage",
            "",
            f"- Decision: `{triage.decision}`",
            f"- Top blocker: `{triage.top_blocker or 'none'}`",
            f"- External-authority gaps: `{external_gaps}`",
            f"- Locally actionable gaps: `{local_gaps}`",
            f"- Not authority: `{triage.not_authority}`",
        ]
    )
    for item in triage.gap_items[:6]:
        lines.append(
            f"- `{item.get('gap_code')}` owner `{item.get('owner_department')}`; "
            f"severity `{item.get('severity')}`; "
            f"local `{item.get('can_progress_locally')}`; "
            f"external `{item.get('requires_external_authority')}`."
        )

    memory = projection.memory_kernel
    lines.extend(
        [
            "",
            "## Memory Kernel",
            "",
            f"- Status: `{memory.status}`",
            f"- Staged: `{memory.staged_count}`",
            f"- Trusted: `{memory.trusted_count}`",
            f"- Quarantine: `{memory.quarantine_count}`",
            f"- Truncated scan: `{memory.truncated}`",
            f"- Index: `{memory.index_status or 'not_built'}` with `{memory.indexed_count}` entries",
            f"- Query evals: `{memory.query_eval_status}` "
            f"({memory.query_eval_passed}/{memory.query_eval_total})",
        ]
    )
    repair = projection.memory_kernel_repair_packet
    lines.extend(
        [
            "",
            "## Memory Repair Packet",
            "",
            f"- Decision: `{repair.decision}`",
            f"- Status: `{repair.status}`",
            f"- Safe next action: {repair.safe_next_action}",
            f"- Repair items: `{len(repair.repair_items)}`",
        ]
    )
    if memory.query_eval_results:
        lines.extend(["", "## Memory Query Evals", ""])
        for result in memory.query_eval_results:
            passed = "pass" if result.get("passed") else "fail"
            missing = ", ".join(result.get("missing_terms") or ()) or "none"
            lines.append(
                f"- `{passed}` {result.get('query')}: "
                f"`{result.get('status')}`; matches `{result.get('matched_count')}`; "
                f"missing `{missing}`."
            )
    if memory.index_entries:
        lines.extend(["", "## Memory Index", ""])
        for tier in ("trusted", "staged", "quarantine"):
            tier_entries = [
                entry
                for entry in memory.index_entries
                if str(entry.get("tier") or "unknown") == tier
            ]
            if not tier_entries:
                continue
            lines.append(f"- `{tier}` entries shown: `{len(tier_entries[:3])}`")
            for entry in tier_entries[:3]:
                title = str(entry.get("title") or entry.get("path") or "untitled")
                path = str(entry.get("path") or "")
                lines.append(f"  - {title}: `{path}`")

    lines.extend(["", "## Daily Cycle", ""])
    for step in projection.daily_cycle:
        lines.append(f"- {step}")

    lines.extend(["", "## Next Actions", ""])
    for action in projection.next_actions:
        lines.append(f"- {action}")
    lines.extend(["", "## Evidence", ""])
    for ref in projection.evidence_refs:
        lines.append(f"- `{ref}`")
    return "\n".join(lines).rstrip() + "\n"


def write_operator_daily_digest(
    projection: VentureCellOperatorProjection,
    output_path: Path,
) -> Path:
    """Write the digest to an explicit local path."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_operator_daily_digest(projection), encoding="utf-8")
    return output_path
