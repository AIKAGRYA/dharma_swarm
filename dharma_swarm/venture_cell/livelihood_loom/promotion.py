"""Promotion readiness lane for Livelihood Loom.

This module prepares sponsor-facing artifacts and approval gates. It never
executes outreach, publication, payment, on-chain action, or provider calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.venture_cell import (
    ExternalActionKind,
    ExternalActionRequest,
    VentureCellRuntime,
)
from dharma_swarm.venture_cell.livelihood_loom import load_livelihood_loom_contract
from dharma_swarm.venture_cell.livelihood_loom.ceo_agent import (
    AGENT_ID,
    DEFAULT_DHARMA_HOME,
)
from dharma_swarm.venture_cell.livelihood_loom.prioritization import (
    CELL_ID,
    DEFAULT_REPORT_ROOT,
)

ACCION_TARGET = {
    "name": "Accion",
    "target_type": "nonprofit_financial_inclusion_partner",
    "website": "https://www.accion.org/",
    "partner_page": "https://www.accion.org/partner-with-us/",
    "source_refs": [
        "https://www.accion.org/",
        "https://www.accion.org/partner-with-us/",
    ],
    "fit_thesis": (
        "Accion is a finance-inclusion organization with a partner path and "
        "a public focus on underserved people and small businesses. Livelihood "
        "Loom can approach it with an aggregate, public-source cultivation "
        "packet without collecting private worker data."
    ),
}


def build_promotion_readiness(
    *,
    report_root: str | Path = DEFAULT_REPORT_ROOT,
    dharma_home: str | Path = DEFAULT_DHARMA_HOME,
    external_action_log: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    created = now or datetime.now(timezone.utc)
    root = Path(report_root)
    promo_dir = root / "promotion"
    promo_dir.mkdir(parents=True, exist_ok=True)

    top_50 = _read_json(root / "cultivation" / "top_50.json")
    wedges = _read_json(root / "cultivation" / "wedges.json")
    safety = _read_json(root / "safety" / "top_50_safety_review.json")
    demand = _read_json(root / "demand" / "index.json")
    packets = _read_json(root / "enablement_packets" / "index.json")
    cycle = _read_json(root / "cycles" / "latest.json")
    provider_gap = _read_json(root / "status" / "provider_readiness_gap.json")

    one_pager = promo_dir / "sponsor_one_pager.md"
    review_packet = promo_dir / "human_review_packet.json"
    review_md = promo_dir / "human_review_packet.md"
    target_path = promo_dir / "first_sponsor_target.json"
    outreach_md = promo_dir / "first_outreach_draft.md"
    acted_gate_path = promo_dir / "external_acted_receipt_gate.json"
    provider_gate_path = promo_dir / "provider_readiness_gate.json"
    homepage_manifest_path = promo_dir / "homepage_manifest.json"
    latest_path = promo_dir / "latest.json"

    target = choose_first_sponsor_target(
        wedges=wedges,
        safety=safety,
        created_at=created,
    )
    flagged = _flagged_candidates(safety)
    _write_ascii(one_pager, render_sponsor_one_pager(top_50, wedges, safety, packets, target, created))
    _write_json(target_path, target)
    _write_ascii(outreach_md, render_first_outreach_draft(target, wedges, safety, created))
    review = build_human_review_packet(
        target=target,
        top_50=top_50,
        wedges=wedges,
        safety=safety,
        demand=demand,
        flagged_candidates=flagged,
        created_at=created,
    )
    _write_json(review_packet, review)
    _write_ascii(review_md, render_human_review_markdown(review))

    outreach_action = draft_first_outreach_action(
        target=target,
        top_50=top_50,
        safety=safety,
        wedges=wedges,
        outreach_draft_path=outreach_md,
        dharma_home=dharma_home,
        external_action_log=external_action_log,
        created_at=created,
    )
    outreach_action_path = promo_dir / "first_outreach_external_action.json"
    _write_json(outreach_action_path, outreach_action)

    acted_gate = {
        "schema_version": "livelihood_loom.external_acted_receipt_gate.v1",
        "cell_id": CELL_ID,
        "generated_at": created.isoformat(),
        "status": "blocked_pending_human_governor_approval_and_external_act",
        "complete": False,
        "required_for_completion": [
            "human_governor approves outreach action",
            "human or approved executor sends outreach",
            "external counterparty acts or responds",
            "acted receipt records timestamp, actor, counterparty, action, and evidence_ref",
        ],
        "not_fabricated": True,
        "current_external_action": str(outreach_action_path),
        "current_external_action_status": outreach_action["status"],
    }
    _write_json(acted_gate_path, acted_gate)

    provider_gate = {
        "schema_version": "livelihood_loom.provider_readiness_gate.v1",
        "cell_id": CELL_ID,
        "generated_at": created.isoformat(),
        "status": "red",
        "complete": False,
        "provider_green": False,
        "provider_gap": provider_gap,
        "next_safe_step": "Run provider proof only when keys/routes are available; do not block sponsor draft work.",
    }
    _write_json(provider_gate_path, provider_gate)

    homepage_manifest = {
        "schema_version": "livelihood_loom.homepage_manifest.v1",
        "cell_id": CELL_ID,
        "generated_at": created.isoformat(),
        "dashboard_route": "/dashboard/livelihood-loom",
        "api_route": "/api/livelihood-loom",
        "source_reports": {
            "cycle": str(root / "cycles" / "latest.json"),
            "top_50": str(root / "cultivation" / "top_50.json"),
            "wedges": str(root / "cultivation" / "wedges.json"),
            "safety": str(root / "safety" / "top_50_safety_review.json"),
            "demand": str(root / "demand" / "index.json"),
            "promotion": str(latest_path),
        },
        "public_status": "internal_only_not_published",
    }
    _write_json(homepage_manifest_path, homepage_manifest)

    latest = {
        "schema_version": "livelihood_loom.promotion_readiness.v1",
        "cell_id": CELL_ID,
        "generated_at": created.isoformat(),
        "steps": {
            "1_internal_homepage": "implemented_dashboard_route",
            "2_sponsor_one_pager": str(one_pager),
            "3_api_report_reader": "dashboard /api/livelihood-loom plus server report reader",
            "4_human_review": "packet_prepared_pending_human_governor",
            "5_first_sponsor_target": target,
            "6_external_acted_receipt": "blocked_pending_real_external_act",
            "7_provider_readiness": "red_gap_recorded",
        },
        "artifacts": {
            "homepage_manifest": str(homepage_manifest_path),
            "sponsor_one_pager": str(one_pager),
            "human_review_packet": str(review_packet),
            "human_review_markdown": str(review_md),
            "first_sponsor_target": str(target_path),
            "first_outreach_draft": str(outreach_md),
            "first_outreach_external_action": str(outreach_action_path),
            "external_acted_receipt_gate": str(acted_gate_path),
            "provider_readiness_gate": str(provider_gate_path),
        },
        "current_cycle": {
            "receipt_id": cycle.get("receipt_id", ""),
            "status": cycle.get("status", ""),
            "provider_green": bool(cycle.get("provider_green", False)),
        },
        "safety_boundary": {
            "external_contacts_made": False,
            "publication_made": False,
            "payments_made": False,
            "on_chain_transactions_made": False,
            "private_data_used": False,
            "provider_calls_made": False,
            "outreach_action_status": outreach_action["status"],
            "outreach_approved": bool(outreach_action.get("approved", False)),
            "outreach_executed": bool(outreach_action.get("executed", False)),
        },
    }
    _write_json(latest_path, latest)
    return {**latest, "latest_path": str(latest_path)}


def choose_first_sponsor_target(
    *,
    wedges: dict[str, Any],
    safety: dict[str, Any],
    created_at: datetime,
) -> dict[str, Any]:
    top_wedge = (wedges.get("wedges") or [{}])[0]
    return {
        "schema_version": "livelihood_loom.first_sponsor_target.v1",
        "generated_at": created_at.isoformat(),
        **ACCION_TARGET,
        "selected_wedge": {
            "wedge_id": top_wedge.get("wedge_id", ""),
            "label": top_wedge.get("label", ""),
            "roi_score": top_wedge.get("roi_score", 0),
        },
        "safety_basis": {
            "allowed": safety.get("summary", {}).get("allowed", 0),
            "needs_review": safety.get("summary", {}).get("needs_review", 0),
            "blocked": safety.get("summary", {}).get("blocked", 0),
        },
        "selection_status": "draft_target_pending_human_governor_review",
    }


def build_human_review_packet(
    *,
    target: dict[str, Any],
    top_50: dict[str, Any],
    wedges: dict[str, Any],
    safety: dict[str, Any],
    demand: dict[str, Any],
    flagged_candidates: list[dict[str, Any]],
    created_at: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": "livelihood_loom.human_review_packet.v1",
        "cell_id": CELL_ID,
        "generated_at": created_at.isoformat(),
        "status": "pending_human_governor_review",
        "reviewer": "dhyana",
        "must_review_before": [
            "approving outreach",
            "publishing sponsor-facing material",
            "claiming external acted receipt",
            "claiming provider-green",
        ],
        "target": target,
        "top_50_count": len(top_50.get("candidates", [])),
        "wedges": wedges.get("wedges", []),
        "safety_summary": safety.get("summary", {}),
        "flagged_candidates": flagged_candidates,
        "demand_index": demand,
        "decision_fields": {
            "approve_outreach": False,
            "approve_publication": False,
            "approve_provider_green_claim": False,
            "notes": "",
        },
    }


def draft_first_outreach_action(
    *,
    target: dict[str, Any],
    top_50: dict[str, Any],
    safety: dict[str, Any],
    wedges: dict[str, Any],
    outreach_draft_path: str | Path,
    dharma_home: str | Path = DEFAULT_DHARMA_HOME,
    external_action_log: str | Path | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    created = created_at or datetime.now(timezone.utc)
    contract = load_livelihood_loom_contract()
    home = Path(dharma_home).expanduser()
    action_log = (
        Path(external_action_log)
        if external_action_log is not None
        else home / "venture_cells" / CELL_ID / "external_actions.jsonl"
    )
    runtime = VentureCellRuntime(contract, action_log)
    request = runtime.draft_external_action(
        ExternalActionRequest(
            cell_id=contract.cell_id,
            kind=ExternalActionKind.OUTREACH,
            title=f"Draft first sponsor outreach to {target['name']}",
            requested_by=AGENT_ID,
            payload={
                "target_name": target["name"],
                "target_type": target["target_type"],
                "target_public_url": target["website"],
                "partner_page": target["partner_page"],
                "draft_path": str(outreach_draft_path),
                "wedge_count": len(wedges.get("wedges", [])),
                "top_50_count": len(top_50.get("candidates", [])),
                "safety_summary": safety.get("summary", {}),
            },
            risk_notes=[
                "Draft only; do not send without human_governor approval.",
                "Uses public organization-level target data only.",
                "No private worker data, income, debt, caste, religion, health, or exact-location data.",
                "No provider-green or external acted receipt claim.",
            ],
            evidence_refs=list(target.get("source_refs", [])),
            idempotency_key=(
                f"{contract.mission_id}:first_sponsor_outreach:"
                f"{created.strftime('%Y%m%dT%H%M%SZ')}:{target['name'].lower().replace(' ', '-')}"
            ),
        )
    )
    reviewed = runtime.external_actions.risk_review(
        request.request_id,
        reviewer="worker_advocate_safety_red_team",
        notes=[
            "Outreach draft uses public organization-level information.",
            "No approval or execution has been granted.",
            "External acted receipt remains pending until a real external act exists.",
        ],
    )
    payload = reviewed.to_dict()
    payload["event_log"] = str(action_log)
    payload["approved"] = False
    payload["executed"] = False
    return payload


def render_sponsor_one_pager(
    top_50: dict[str, Any],
    wedges: dict[str, Any],
    safety: dict[str, Any],
    packets: dict[str, Any],
    target: dict[str, Any],
    created_at: datetime,
) -> str:
    lines = [
        "# Livelihood Loom Sponsor One-Pager",
        "",
        f"Created: {created_at.isoformat()}",
        "Status: internal draft only; not published or sent.",
        "",
        "Offer:",
        "A two-week sponsor-readiness sprint that turns public informal-economy "
        "enabler data into safety-reviewed partner shortlists and welfare metrics.",
        "",
        "Proof packet:",
        f"- {len(top_50.get('candidates', []))} Top 50 candidates from {top_50.get('candidate_count', 0)} public-source rows.",
        f"- {wedges.get('wedge_count', 0)} ROI wedges.",
        f"- {packets.get('packet_count', 0)} enablement packets.",
        f"- Safety review: {safety.get('summary', {}).get('allowed', 0)} allowed, "
        f"{safety.get('summary', {}).get('needs_review', 0)} needs review, "
        f"{safety.get('summary', {}).get('blocked', 0)} blocked.",
        "",
        "First draft sponsor target:",
        f"- {target['name']}: {target['fit_thesis']}",
        "",
        "Guardrails:",
        "- Aggregate public proof only.",
        "- No private worker data collection.",
        "- No autonomous lending, investment, payment, publication, or outreach.",
        "- Human_governor approval required before any external action.",
        "- Provider remains red until complete ProviderProof exists.",
        "",
    ]
    return "\n".join(lines)


def render_first_outreach_draft(
    target: dict[str, Any],
    wedges: dict[str, Any],
    safety: dict[str, Any],
    created_at: datetime,
) -> str:
    wedge = (wedges.get("wedges") or [{}])[0]
    return "\n".join(
        [
            f"# Draft Outreach: {target['name']}",
            "",
            f"Created: {created_at.isoformat()}",
            "Status: draft only; not sent.",
            "",
            "Subject: Livelihood enablement packet for inclusive finance partners",
            "",
            "Hello,",
            "",
            "Livelihood Loom has prepared an internal public-source cultivation "
            "packet for informal-economy enablement. The current packet focuses "
            f"on {wedge.get('label', 'livelihood enablement')} and includes a "
            "Top 50 partner map, safety red-team review, and sponsor-ready "
            "enablement packets.",
            "",
            "The draft is aggregate-only and does not include private worker, "
            "seller, income, debt, caste, religion, health, or exact-location data.",
            "",
            "If useful, the next approved step would be a short sponsor-readiness "
            "conversation about where this packet could support responsible "
            "livelihood outcomes.",
            "",
            "Boundary note: this message is not authorized for sending until "
            "human_governor approval is recorded.",
            "",
            f"Safety summary: {safety.get('summary', {})}",
            "",
        ]
    )


def render_human_review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Livelihood Loom Human Review Packet",
        "",
        f"Status: {review['status']}",
        f"Reviewer: {review['reviewer']}",
        "",
        "Review before:",
    ]
    for item in review["must_review_before"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "Safety summary:",
            f"- Allowed: {review['safety_summary'].get('allowed', 0)}",
            f"- Needs review: {review['safety_summary'].get('needs_review', 0)}",
            f"- Blocked: {review['safety_summary'].get('blocked', 0)}",
            "",
            "Flagged candidates:",
        ]
    )
    for item in review["flagged_candidates"][:25]:
        lines.append(
            f"- rank {item['rank']}: {item['name']} "
            f"({item['safety_status']}; {', '.join(item['flags'])})"
        )
    lines.append("")
    return "\n".join(lines)


def _flagged_candidates(safety: dict[str, Any]) -> list[dict[str, Any]]:
    flagged = [
        {
            "rank": item["rank"],
            "name": item["name"],
            "company_id": item["company_id"],
            "safety_status": item["safety_status"],
            "flags": item.get("flags", []),
            "notes": item.get("notes", []),
        }
        for item in safety.get("reviews", [])
        if item.get("safety_status") != "allowed"
    ]
    flagged.sort(key=lambda item: (item["safety_status"] != "blocked", item["rank"]))
    return flagged


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_ascii(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("ascii", "backslashreplace") + b"\n")

