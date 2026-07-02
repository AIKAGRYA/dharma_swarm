"""Enablement packet builder for Livelihood Loom."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.venture_cell.livelihood_loom.prioritization import (
    CELL_ID,
    DEFAULT_REPORT_ROOT,
)


@dataclass(frozen=True)
class EnablementPacket:
    packet_id: str
    target_wedge: str
    beneficiary: str
    friction: str
    candidate_partners: tuple[dict[str, Any], ...]
    sponsor_value: str
    welfare_metric: str
    evidence_refs: tuple[str, ...]
    risks: tuple[str, ...]
    next_safe_action: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidate_partners"] = [dict(item) for item in self.candidate_partners]
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["risks"] = list(self.risks)
        return payload


PACKET_BLUEPRINTS = (
    {
        "target_wedge": "payment_acceptance_cashflow",
        "beneficiary": "cash-heavy micro-merchants and independent sellers",
        "friction": "lost sales and slow settlement from weak payment acceptance",
        "sponsor_value": "sponsor funds a public-source partner map for payment enablement",
        "welfare_metric": "aggregate count of merchants with safer payment options",
        "risks": (
            "No credit decisioning or income/debt fields.",
            "Payment partners need fee and grievance-path review.",
        ),
    },
    {
        "target_wedge": "market_access",
        "beneficiary": "micro-sellers, craftspeople, and small food vendors",
        "friction": "buyers cannot discover trustworthy small suppliers",
        "sponsor_value": "sponsor receives an evidence-backed market-access shortlist",
        "welfare_metric": "aggregate new buyer-access opportunities identified",
        "risks": (
            "No seller scraping, lead-list sale, or private contact enrichment.",
            "Use public partner-level proof only.",
        ),
    },
    {
        "target_wedge": "responsible_microfinance",
        "beneficiary": "entrepreneurs needing small-ticket stock or tool financing",
        "friction": "working capital is expensive, opaque, or unavailable",
        "sponsor_value": "sponsor gets a red-team-filtered responsible-finance map",
        "welfare_metric": "aggregate number of finance rails passing fee-safety review",
        "risks": (
            "High-fee lending and debt burden require human review.",
            "No autonomous lending or investment decision is allowed.",
        ),
    },
    {
        "target_wedge": "food_vendor_demand",
        "beneficiary": "small restaurants, home kitchens, couriers, and food vendors",
        "friction": "demand aggregation can raise volume while worsening worker terms",
        "sponsor_value": "sponsor sees demand rails with explicit courier-welfare risks",
        "welfare_metric": "aggregate food-vendor demand rails reviewed for worker safety",
        "risks": (
            "Exploitative gig terms and surveillance are risk-reviewed.",
            "No dispatch optimization or worker monitoring.",
        ),
    },
    {
        "target_wedge": "logistics_reliability",
        "beneficiary": "micro-sellers depending on local pickup and delivery",
        "friction": "failed deliveries and unreliable fulfillment erase margin",
        "sponsor_value": "sponsor gets a low-touch logistics enablement shortlist",
        "welfare_metric": "aggregate delivery-reliability partners mapped",
        "risks": (
            "No worker route tracking or location exposure.",
            "Use only public company-level logistics evidence.",
        ),
    },
)


def build_enablement_packets(
    *,
    safety_review_path: str | Path,
    wedges_path: str | Path,
    report_root: str | Path = DEFAULT_REPORT_ROOT,
    packet_count: int = 5,
    now: datetime | None = None,
) -> dict[str, Any]:
    created = now or datetime.now(timezone.utc)
    safety = json.loads(Path(safety_review_path).read_text(encoding="utf-8"))
    wedges = json.loads(Path(wedges_path).read_text(encoding="utf-8"))
    reviews = safety["reviews"]
    wedge_order = [item["wedge_id"] for item in wedges.get("wedges", [])]
    packets: list[EnablementPacket] = []
    for index, blueprint in enumerate(PACKET_BLUEPRINTS[:packet_count], start=1):
        target = blueprint["target_wedge"]
        partners = _partners_for_wedge(reviews, target)
        if not partners and wedge_order:
            partners = _partners_for_wedge(reviews, wedge_order[(index - 1) % len(wedge_order)])
        if not partners:
            partners = _fallback_partners(reviews)
        evidence_refs = _evidence_refs(partners)
        packets.append(
            EnablementPacket(
                packet_id=f"packet_{index:02d}",
                target_wedge=target,
                beneficiary=str(blueprint["beneficiary"]),
                friction=str(blueprint["friction"]),
                candidate_partners=tuple(partners[:5]),
                sponsor_value=str(blueprint["sponsor_value"]),
                welfare_metric=str(blueprint["welfare_metric"]),
                evidence_refs=tuple(evidence_refs[:12]),
                risks=tuple(str(item) for item in blueprint["risks"]),
                next_safe_action=(
                    "Draft-only internal sponsor review packet; do not contact "
                    "partners or publish claims without human_governor approval."
                ),
            )
        )

    packet_dir = Path(report_root) / "enablement_packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for packet in packets:
        payload = {
            "schema_version": "livelihood_loom.enablement_packet.v1",
            "cell_id": CELL_ID,
            "generated_at": created.isoformat(),
            **packet.to_dict(),
        }
        json_path = packet_dir / f"{packet.packet_id}.json"
        md_path = packet_dir / f"{packet.packet_id}.md"
        _write_json(json_path, payload)
        _write_ascii(md_path, render_packet_markdown(payload))
        outputs.append({"json": str(json_path), "md": str(md_path), "packet_id": packet.packet_id})

    index_path = packet_dir / "index.json"
    _write_json(
        index_path,
        {
            "schema_version": "livelihood_loom.enablement_packet_index.v1",
            "cell_id": CELL_ID,
            "generated_at": created.isoformat(),
            "source_safety_review": str(safety_review_path),
            "source_wedges": str(wedges_path),
            "packet_count": len(packets),
            "packets": outputs,
        },
    )
    return {
        "packet_dir": str(packet_dir),
        "packet_index": str(index_path),
        "packet_count": len(packets),
        "packets": outputs,
    }


def render_packet_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload['packet_id']}: {payload['target_wedge']}",
        "",
        f"- Beneficiary: {payload['beneficiary']}",
        f"- Friction: {payload['friction']}",
        f"- Sponsor value: {payload['sponsor_value']}",
        f"- Welfare metric: {payload['welfare_metric']}",
        f"- Next safe action: {payload['next_safe_action']}",
        "",
        "## Candidate Partners",
    ]
    for partner in payload["candidate_partners"]:
        lines.append(
            "- {name} ({country}); status={status}; score={score}".format(
                name=partner["name"],
                country=partner.get("country") or "unknown",
                status=partner["safety_status"],
                score=partner["prioritization_score"],
            )
        )
    lines.extend(["", "## Risks"])
    for risk in payload["risks"]:
        lines.append(f"- {risk}")
    lines.append("")
    return "\n".join(lines)


def _partners_for_wedge(reviews: list[dict[str, Any]], wedge_id: str) -> list[dict[str, Any]]:
    partners = [
        _partner_ref(review)
        for review in reviews
        if review["candidate"].get("wedge_id") == wedge_id
        and review["safety_status"] != "blocked"
    ]
    partners.sort(key=lambda item: (-float(item["prioritization_score"]), int(item["rank"])))
    return partners


def _fallback_partners(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    partners = [
        _partner_ref(review)
        for review in reviews
        if review["safety_status"] != "blocked"
    ]
    partners.sort(key=lambda item: (-float(item["prioritization_score"]), int(item["rank"])))
    return partners


def _partner_ref(review: dict[str, Any]) -> dict[str, Any]:
    candidate = review["candidate"]
    return {
        "rank": candidate["rank"],
        "company_id": candidate["company_id"],
        "name": candidate["name"],
        "country": candidate.get("country", ""),
        "wedge_id": candidate.get("wedge_id", ""),
        "prioritization_score": candidate["prioritization_score"],
        "safety_status": review["safety_status"],
        "flags": list(review["flags"]),
        "evidence_refs": list(review["evidence_refs"]),
    }


def _evidence_refs(partners: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for partner in partners:
        for ref in partner["evidence_refs"]:
            if ref not in refs:
                refs.append(ref)
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

