"""Demand and first paid offer lane for Livelihood Loom."""

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


def build_demand_artifacts(
    *,
    top_50_path: str | Path,
    safety_review_path: str | Path,
    wedges_path: str | Path,
    packets_dir: str | Path,
    report_root: str | Path = DEFAULT_REPORT_ROOT,
    dharma_home: str | Path = DEFAULT_DHARMA_HOME,
    external_action_log: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    created = now or datetime.now(timezone.utc)
    top_50 = json.loads(Path(top_50_path).read_text(encoding="utf-8"))
    safety = json.loads(Path(safety_review_path).read_text(encoding="utf-8"))
    wedges = json.loads(Path(wedges_path).read_text(encoding="utf-8"))
    packet_index = _load_packet_index(Path(packets_dir))
    demand_dir = Path(report_root) / "demand"
    demand_dir.mkdir(parents=True, exist_ok=True)

    first_paid_offer = demand_dir / "first_paid_offer.md"
    _write_ascii(
        first_paid_offer,
        render_first_paid_offer(
            top_50=top_50,
            safety=safety,
            wedges=wedges,
            packet_index=packet_index,
            created_at=created,
        ),
    )

    sponsor_briefs = []
    for index, wedge in enumerate(wedges.get("wedges", [])[:3], start=1):
        path = demand_dir / f"sponsor_brief_{index:02d}.md"
        _write_ascii(path, render_sponsor_brief(wedge, index=index, created_at=created))
        sponsor_briefs.append(str(path))
    while len(sponsor_briefs) < 3:
        index = len(sponsor_briefs) + 1
        path = demand_dir / f"sponsor_brief_{index:02d}.md"
        _write_ascii(
            path,
            render_sponsor_brief(_fallback_wedge(index), index=index, created_at=created),
        )
        sponsor_briefs.append(str(path))

    action = draft_risk_reviewed_sponsor_signal(
        top_50=top_50,
        safety=safety,
        wedges=wedges,
        dharma_home=dharma_home,
        external_action_log=external_action_log,
        created_at=created,
    )
    external_action_path = demand_dir / "external_action_draft.json"
    _write_json(external_action_path, action)

    index_path = demand_dir / "index.json"
    payload = {
        "schema_version": "livelihood_loom.demand_artifacts.v1",
        "cell_id": CELL_ID,
        "generated_at": created.isoformat(),
        "draft_only": True,
        "sent": False,
        "first_paid_offer": str(first_paid_offer),
        "sponsor_briefs": sponsor_briefs,
        "external_action_draft": str(external_action_path),
        "external_action_status": action["status"],
    }
    _write_json(index_path, payload)
    return {**payload, "index": str(index_path)}


def draft_risk_reviewed_sponsor_signal(
    *,
    top_50: dict[str, Any],
    safety: dict[str, Any],
    wedges: dict[str, Any],
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
    safe_count = safety["summary"]["allowed"] + safety["summary"]["needs_review"]
    refs = _top_evidence_refs(top_50, limit=20)
    request = runtime.draft_external_action(
        ExternalActionRequest(
            cell_id=contract.cell_id,
            kind=ExternalActionKind.CAPITAL_SIGNAL,
            title="Draft sponsor signal for Livelihood Loom cultivation cycle",
            requested_by=AGENT_ID,
            payload={
                "claim_id": "claim_livelihood_loom_cultivation_cycle_ready",
                "cell_id": contract.cell_id,
                "claim_type": "cultivation_cycle_ready",
                "aggregate_count": max(int(safe_count), 2),
                "sector": "informal_economy_enablers",
                "region_level": "country_or_public_market",
                "evidence_refs": refs,
                "audit_status": "internal_red_team_reviewed",
                "outcome_metric": "safe_cultivation_assets_ready",
                "outcome_value": "top_50_safety_reviewed_5_packets_3_briefs",
                "time_period": created.strftime("%Y-%m"),
            },
            risk_notes=[
                "Draft only; no sponsor contacted.",
                "Uses aggregate public-source Top 50 and safety-review counts only.",
                "Requires human_governor approval before any external signal.",
                "Provider remains blocked; no provider-green claim is made.",
            ],
            evidence_refs=refs,
            idempotency_key=(
                f"{contract.mission_id}:cultivation_cycle:"
                f"{created.strftime('%Y%m%dT%H%M%SZ')}:capital_signal"
            ),
        )
    )
    reviewed = runtime.external_actions.risk_review(
        request.request_id,
        reviewer="worker_advocate_safety_red_team",
        notes=[
            "Risk-reviewed for draft-only aggregate public proof.",
            "No approval, execution, outreach, publication, payment, or capital action.",
            f"ROI wedges reviewed: {len(wedges.get('wedges', []))}.",
        ],
    )
    payload = reviewed.to_dict()
    payload["event_log"] = str(action_log)
    payload["approved"] = False
    payload["executed"] = False
    return payload


def render_first_paid_offer(
    *,
    top_50: dict[str, Any],
    safety: dict[str, Any],
    wedges: dict[str, Any],
    packet_index: dict[str, Any],
    created_at: datetime,
) -> str:
    return "\n".join(
        [
            "# First Paid Offer: Livelihood Enablement Packet Sprint",
            "",
            f"Created: {created_at.isoformat()}",
            "",
            "Offer:",
            "A fixed-fee internal cultivation sprint that turns a public "
            "informal-economy enabler map into a sponsor-ready packet set.",
            "",
            "Price:",
            "USD 7,500 draft offer for one two-week sponsor-readiness sprint.",
            "",
            "Included:",
            f"- Top 50 public-source cultivation list from {top_50['candidate_count']} candidates.",
            f"- Safety review: {safety['summary']['allowed']} allowed, "
            f"{safety['summary']['needs_review']} needs review, "
            f"{safety['summary']['blocked']} blocked.",
            f"- {wedges['wedge_count']} ROI wedges.",
            f"- {packet_index['packet_count']} enablement packets.",
            "- Three sponsor briefs.",
            "",
            "Boundaries:",
            "- Draft only. No outreach, publication, payment, investment, "
            "lending, on-chain action, or private data collection.",
            "- Human_governor approval is required before any external action.",
            "- Provider remains blocked until complete provider proof exists.",
            "",
        ]
    )


def render_sponsor_brief(wedge: dict[str, Any], *, index: int, created_at: datetime) -> str:
    top_candidates = wedge.get("top_candidates", [])
    lines = [
        f"# Draft Sponsor Brief {index:02d}: {wedge['label']}",
        "",
        f"Created: {created_at.isoformat()}",
        "",
        "Status: draft only; not sent.",
        "",
        "Demand thesis:",
        str(wedge["roi_thesis"]),
        "",
        "Sponsor value:",
        "Fund a bounded public-source cultivation packet that identifies "
        "non-extractive partner options and welfare metrics.",
        "",
        "Candidate partner examples:",
    ]
    for candidate in top_candidates[:5]:
        lines.append(
            "- {name} ({country}), score {score}".format(
                name=candidate["name"],
                country=candidate.get("country") or "unknown",
                score=candidate["score"],
            )
        )
    lines.extend(
        [
            "",
            "Risk controls:",
            "- Aggregate public proof only.",
            "- No private worker, seller, income, debt, caste, religion, health, "
            "or exact-location data.",
            "- No contact or publication without human_governor approval.",
            "",
        ]
    )
    return "\n".join(lines)


def _load_packet_index(packet_dir: Path) -> dict[str, Any]:
    index_path = packet_dir / "index.json"
    if index_path.exists():
        return json.loads(index_path.read_text(encoding="utf-8"))
    packet_files = sorted(packet_dir.glob("packet_*.json"))
    return {
        "packet_count": len(packet_files),
        "packets": [{"json": str(path)} for path in packet_files],
    }


def _fallback_wedge(index: int) -> dict[str, Any]:
    return {
        "label": f"Fallback livelihood enablement wedge {index}",
        "roi_thesis": "Use existing public-source candidates for sponsor discovery.",
        "top_candidates": [],
    }


def _top_evidence_refs(top_50: dict[str, Any], *, limit: int) -> list[str]:
    refs: list[str] = []
    for candidate in top_50["candidates"]:
        for ref in candidate.get("evidence_refs", []):
            if ref not in refs:
                refs.append(ref)
            if len(refs) >= limit:
                return refs
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

