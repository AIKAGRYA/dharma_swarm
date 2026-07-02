"""Orchestration receipt map for the Livelihood Loom cultivation cycle."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.venture_cell.livelihood_loom.prioritization import (
    CELL_ID,
    DEFAULT_REPORT_ROOT,
)

LANES = (
    {
        "lane_id": "lane_loom_conductor",
        "agent": "loom_conductor",
        "charter_roles": ("loom_conductor",),
        "module": "dharma_swarm/venture_cell/livelihood_loom/orchestration.py",
        "scope": "orchestration, task graph, receipt map",
    },
    {
        "lane_id": "lane_field_cartography",
        "agent": "field_cartography",
        "charter_roles": ("field_cartography",),
        "module": "dharma_swarm/venture_cell/livelihood_loom/prioritization.py",
        "scope": "CSV enrichment, scoring, Top 50, ROI wedges",
    },
    {
        "lane_id": "lane_worker_advocate_safety_red_team",
        "agent": "worker_advocate_safety_red_team",
        "charter_roles": ("worker_advocate", "safety_red_team"),
        "module": "dharma_swarm/venture_cell/livelihood_loom/safety.py",
        "scope": "harm analysis, exclusion rules, safety review",
    },
    {
        "lane_id": "lane_offer_builder",
        "agent": "offer_builder",
        "charter_roles": ("offer_builder",),
        "module": "dharma_swarm/venture_cell/livelihood_loom/enablement_packets.py",
        "scope": "five enablement packets",
    },
    {
        "lane_id": "lane_demand_builder",
        "agent": "demand_builder",
        "charter_roles": ("demand_builder",),
        "module": "dharma_swarm/venture_cell/livelihood_loom/demand.py",
        "scope": "sponsor demand briefs and first paid offer",
    },
    {
        "lane_id": "lane_evidence_auditor_memory_librarian",
        "agent": "evidence_auditor_memory_librarian",
        "charter_roles": ("evidence_auditor", "memory_librarian"),
        "module": "dharma_swarm/venture_cell/livelihood_loom/evidence.py",
        "scope": "proof, status gates, CLI integration, receipt index",
    },
)


def build_orchestration_receipts(
    *,
    outputs: dict[str, Any],
    report_root: str | Path = DEFAULT_REPORT_ROOT,
    now: datetime | None = None,
) -> dict[str, Any]:
    created = now or datetime.now(timezone.utc)
    root = Path(report_root)
    orchestration_dir = root / "orchestration"
    orchestration_dir.mkdir(parents=True, exist_ok=True)
    lane_status = [_lane_status(lane, outputs) for lane in LANES]
    mission_plan = {
        "schema_version": "livelihood_loom.orchestration_plan.v1",
        "cell_id": CELL_ID,
        "generated_at": created.isoformat(),
        "execution_mode": "emulated_six_lane_local_cycle",
        "external_actions": "draft_and_risk_review_only",
        "provider_claim": "provider_blocked_no_green_claim",
        "lanes": lane_status,
        "task_graph": _task_graph(),
    }
    mission_plan_json = orchestration_dir / "mission_plan.json"
    mission_plan_md = orchestration_dir / "mission_plan.md"
    receipt_index_json = orchestration_dir / "receipt_index.json"
    _write_json(mission_plan_json, mission_plan)
    _write_ascii(mission_plan_md, render_mission_plan_markdown(mission_plan))
    receipt_index = {
        "schema_version": "livelihood_loom.receipt_index.v1",
        "cell_id": CELL_ID,
        "generated_at": created.isoformat(),
        "lane_count": len(LANES),
        "receipts": _receipt_refs(outputs),
        "safety_boundary": {
            "provider_calls_made": False,
            "external_contacts_made": False,
            "payments_made": False,
            "on_chain_transactions_made": False,
            "private_data_used": False,
        },
    }
    _write_json(receipt_index_json, receipt_index)
    return {
        "mission_plan_json": str(mission_plan_json),
        "mission_plan_md": str(mission_plan_md),
        "receipt_index_json": str(receipt_index_json),
        "lane_count": len(LANES),
    }


def render_mission_plan_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Livelihood Loom Cultivation Mission Plan",
        "",
        f"- Execution mode: {payload['execution_mode']}",
        f"- Provider claim: {payload['provider_claim']}",
        "",
        "| Lane | Agent | Status | Module |",
        "| --- | --- | --- | --- |",
    ]
    for lane in payload["lanes"]:
        lines.append(
            "| {lane_id} | {agent} | {status} | `{module}` |".format(
                lane_id=lane["lane_id"],
                agent=lane["agent"],
                status=lane["status"],
                module=lane["module"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def _lane_status(lane: dict[str, Any], outputs: dict[str, Any]) -> dict[str, Any]:
    produced = _lane_outputs(lane["agent"], outputs)
    return {
        **lane,
        "charter_roles": list(lane["charter_roles"]),
        "status": "complete" if produced else "planned",
        "proof_refs": produced,
    }


def _lane_outputs(agent: str, outputs: dict[str, Any]) -> list[str]:
    keys = {
        "loom_conductor": ("orchestration",),
        "field_cartography": ("top_50_json", "top_50_md", "wedges_json"),
        "worker_advocate_safety_red_team": ("safety_review_json",),
        "offer_builder": ("packet_index",),
        "demand_builder": ("first_paid_offer", "sponsor_briefs", "external_action_draft"),
        "evidence_auditor_memory_librarian": ("cycle_latest", "provider_gap"),
    }[agent]
    refs: list[str] = []
    for key in keys:
        value = outputs.get(key)
        if isinstance(value, list):
            refs.extend(str(item) for item in value)
        elif value:
            refs.append(str(value))
    return refs


def _task_graph() -> list[dict[str, str]]:
    return [
        {"from": "field_cartography", "to": "worker_advocate_safety_red_team"},
        {"from": "field_cartography", "to": "offer_builder"},
        {"from": "worker_advocate_safety_red_team", "to": "offer_builder"},
        {"from": "offer_builder", "to": "demand_builder"},
        {"from": "demand_builder", "to": "evidence_auditor_memory_librarian"},
        {"from": "loom_conductor", "to": "evidence_auditor_memory_librarian"},
    ]


def _receipt_refs(outputs: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for key, value in sorted(outputs.items()):
        if isinstance(value, list):
            for item in value:
                refs.append({"name": key, "path": str(item)})
        elif isinstance(value, str):
            refs.append({"name": key, "path": value})
    return refs


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_ascii(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("ascii", "backslashreplace") + b"\n")

