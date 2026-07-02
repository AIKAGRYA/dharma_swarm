"""Evidence and full-cycle receipt lane for Livelihood Loom."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.venture_cell.livelihood_loom.ceo_agent import (
    AGENT_ID,
    CALLSIGN,
    DEFAULT_DHARMA_HOME,
)
from dharma_swarm.venture_cell.livelihood_loom.demand import build_demand_artifacts
from dharma_swarm.venture_cell.livelihood_loom.enablement_packets import (
    build_enablement_packets,
)
from dharma_swarm.venture_cell.livelihood_loom.execution import DEFAULT_ENABLER_CSV
from dharma_swarm.venture_cell.livelihood_loom.orchestration import (
    build_orchestration_receipts,
)
from dharma_swarm.venture_cell.livelihood_loom.prioritization import (
    CELL_ID,
    DEFAULT_REPORT_ROOT,
    DEFAULT_TOP_N,
    write_top_50_reports,
)
from dharma_swarm.venture_cell.livelihood_loom.safety import build_safety_review


def run_cultivation_cycle(
    *,
    candidate_csv: str | Path = DEFAULT_ENABLER_CSV,
    candidate_limit: int | None = 1000,
    top_n: int = DEFAULT_TOP_N,
    report_root: str | Path = DEFAULT_REPORT_ROOT,
    dharma_home: str | Path = DEFAULT_DHARMA_HOME,
    external_action_log: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    created = now or datetime.now(timezone.utc)
    receipt_id = "lloom_cultivation_" + created.strftime("%Y%m%dT%H%M%SZ")
    root = Path(report_root)

    top_outputs = write_top_50_reports(
        candidate_csv=candidate_csv,
        report_root=root,
        candidate_limit=candidate_limit,
        top_n=top_n,
        now=created,
    )
    safety_outputs = build_safety_review(
        top_50_path=top_outputs["top_50_json"],
        report_root=root,
        now=created,
    )
    packet_outputs = build_enablement_packets(
        safety_review_path=safety_outputs["safety_review_json"],
        wedges_path=top_outputs["wedges_json"],
        report_root=root,
        now=created,
    )
    demand_outputs = build_demand_artifacts(
        top_50_path=top_outputs["top_50_json"],
        safety_review_path=safety_outputs["safety_review_json"],
        wedges_path=top_outputs["wedges_json"],
        packets_dir=packet_outputs["packet_dir"],
        report_root=root,
        dharma_home=dharma_home,
        external_action_log=external_action_log,
        now=created,
    )
    provider_gap = write_provider_readiness_gap(report_root=root, now=created)
    cycle_dir = root / "cycles"
    latest_path = cycle_dir / "latest.json"
    receipt_path = cycle_dir / f"{receipt_id}.json"
    outputs: dict[str, Any] = {
        **top_outputs,
        **safety_outputs,
        **packet_outputs,
        **demand_outputs,
        "provider_gap": provider_gap["path"],
        "cycle_latest": str(latest_path),
        "orchestration": str(root / "orchestration" / "mission_plan.json"),
    }
    orchestration_outputs = build_orchestration_receipts(
        outputs=outputs,
        report_root=root,
        now=created,
    )
    outputs.update(orchestration_outputs)

    cycle = {
        "schema_version": "livelihood_loom.cultivation_cycle.v1",
        "receipt_id": receipt_id,
        "cell_id": CELL_ID,
        "agent_uid": AGENT_ID,
        "created_at": created.isoformat(),
        "status": "cultivation_ready_provider_blocked",
        "provider_green": False,
        "provider_readiness_gap": provider_gap,
        "status_gates": build_status_gates(
            report_root=root,
            dharma_home=dharma_home,
            provider_gap=provider_gap,
        ),
        "outputs": outputs,
        "safety_boundary": {
            "external_action_mode": "human_approved_only",
            "external_action_status": demand_outputs["external_action_status"],
            "external_contacts_made": False,
            "publication_made": False,
            "payments_made": False,
            "on_chain_transactions_made": False,
            "private_data_used": False,
            "provider_calls_made": False,
            "capital_boundary": "dharma_capital_read_only_aggregated_signals",
        },
        "definition_of_done": {
            "top_50_not_alphabetical": True,
            "roi_wedges_explicit": True,
            "enablement_packets": packet_outputs["packet_count"],
            "safety_reviewed": True,
            "first_paid_offer_written": True,
            "sponsor_briefs_draft_only": True,
            "external_action_risk_reviewed_only": (
                demand_outputs["external_action_status"] == "risk_reviewed"
            ),
            "provider_remains_blocked": True,
        },
    }
    _write_json(receipt_path, cycle)
    _write_json(latest_path, cycle)
    sandbox_receipt = (
        Path(dharma_home).expanduser()
        / "external_agents"
        / AGENT_ID
        / "receipts"
        / f"{receipt_id}.json"
    )
    _write_json(sandbox_receipt, cycle)
    cycle["receipt_path"] = str(receipt_path)
    cycle["latest_path"] = str(latest_path)
    cycle["sandbox_receipt_path"] = str(sandbox_receipt)
    _write_json(receipt_path, cycle)
    _write_json(latest_path, cycle)
    _write_json(sandbox_receipt, cycle)
    return cycle


def write_provider_readiness_gap(
    *,
    report_root: str | Path = DEFAULT_REPORT_ROOT,
    now: datetime | None = None,
) -> dict[str, Any]:
    created = now or datetime.now(timezone.utc)
    path = Path(report_root) / "status" / "provider_readiness_gap.json"
    payload = {
        "schema_version": "livelihood_loom.provider_readiness_gap.v1",
        "cell_id": CELL_ID,
        "agent_uid": AGENT_ID,
        "generated_at": created.isoformat(),
        "status": "red",
        "provider_green": False,
        "truth": "registered_bootstrapped_cultivation_ready_provider_blocked",
        "missing_provider_proof_fields": [
            "provider",
            "model",
            "attempted_at",
            "success=true",
            "receipt_id",
            "trace_id",
            "result_ref",
        ],
        "provider_calls_made": False,
        "claim_guard": "Do not claim provider-green until ProviderProof.is_green().",
        "path": str(path),
    }
    _write_json(path, payload)
    return payload


def build_status_gates(
    *,
    report_root: str | Path = DEFAULT_REPORT_ROOT,
    dharma_home: str | Path = DEFAULT_DHARMA_HOME,
    provider_gap: dict[str, Any] | None = None,
) -> dict[str, dict[str, str]]:
    home = Path(dharma_home).expanduser()
    root = Path(report_root)
    registration_path = home / "external_agents" / AGENT_ID / "registration.json"
    living_agent_path = home / "agents" / AGENT_ID / "living_agent.json"
    card_path = home / "a2a" / "cards" / f"{CALLSIGN}.json"
    bootstrap_path = root / "bootstrap" / "latest.json"
    top_50_path = root / "cultivation" / "top_50.json"
    safety_path = root / "safety" / "top_50_safety_review.json"
    packets_path = root / "enablement_packets" / "index.json"
    demand_path = root / "demand" / "index.json"
    provider = provider_gap or {"status": "red"}
    return {
        "ceo_registration": _gate(
            registration_path.exists() and living_agent_path.exists() and card_path.exists(),
            str(living_agent_path),
            "CEO registration surfaces missing",
        ),
        "safe_bootstrap": _gate(
            bootstrap_path.exists(),
            str(bootstrap_path),
            "safe bootstrap receipt missing",
        ),
        "top_50": _gate(top_50_path.exists(), str(top_50_path), "Top 50 missing"),
        "safety_review": _gate(
            safety_path.exists(),
            str(safety_path),
            "Top 50 safety review missing",
        ),
        "enablement_packets": _gate(
            packets_path.exists(),
            str(packets_path),
            "packet index missing",
        ),
        "demand_drafts": _gate(
            demand_path.exists(),
            str(demand_path),
            "demand artifacts missing",
        ),
        "provider_proof": {
            "status": str(provider["status"]),
            "detail": "provider remains blocked; complete ProviderProof absent",
        },
    }


def _gate(condition: bool, detail: str, missing: str) -> dict[str, str]:
    return {"status": "green" if condition else "yellow", "detail": detail if condition else missing}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )

