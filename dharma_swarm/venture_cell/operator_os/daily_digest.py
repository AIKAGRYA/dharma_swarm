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
        ]
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
