"""Prioritization lane for Livelihood Loom cultivation candidates."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.venture_cell.livelihood_loom.execution import DEFAULT_ENABLER_CSV

CELL_ID = "livelihood_loom"
DEFAULT_REPORT_ROOT = Path("reports/livelihood_loom")
DEFAULT_TOP_N = 50
DEFAULT_WEDGE_COUNT = 3

CONFIDENCE_WEIGHT = {
    "high_candidate": 1.0,
    "medium_candidate": 0.66,
    "low_candidate": 0.34,
}
PRIORITY_WEIGHT = {
    "A_now": 1.0,
    "A_cultivate_now": 1.0,
    "B_research_next": 0.82,
    "C_backlog": 0.42,
}
DOMAIN_WEIGHT = {
    "commerce_rails": 1.0,
    "finance_rails": 0.88,
    "production_rails": 0.84,
    "logistics_rails": 0.78,
    "labor_rails": 0.68,
}
SUBDOMAIN_WEIGHT = {
    "mobile_payment": 1.0,
    "payment_service_provider": 0.98,
    "online_marketplace": 0.95,
    "e_commerce": 0.9,
    "online_shop": 0.86,
    "microfinance": 0.78,
    "crowdfunding": 0.76,
    "logistics_company": 0.74,
    "online_food_ordering": 0.7,
    "food_delivery": 0.58,
    "ridesharing": 0.5,
    "fintech": 0.68,
}
LIVELIHOOD_COUNTRIES = {
    "bangladesh",
    "brazil",
    "colombia",
    "ghana",
    "india",
    "indonesia",
    "kenya",
    "mexico",
    "nigeria",
    "pakistan",
    "philippines",
    "tanzania",
    "uganda",
    "vietnam",
}


@dataclass(frozen=True)
class CandidateRecord:
    source_rank: int
    name: str
    domain: str
    subdomain: str
    country: str
    website: str
    source_url: str
    source_type: str
    source_tag: str
    all_source_tags: str
    all_subdomains: str
    description: str
    informal_economy_role: str
    candidate_score: float
    confidence: str
    cultivation_priority: str
    company_id: str

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "CandidateRecord":
        name = _clean(row.get("name"))
        source_url = _clean(row.get("source_url") or row.get("source_refs"))
        website = _clean(row.get("website"))
        stable_key = "|".join((name.lower(), source_url.lower(), website.lower()))
        return cls(
            source_rank=_to_int(row.get("rank"), default=999_999),
            name=name,
            domain=_clean(row.get("domain") or row.get("sector")) or "unknown",
            subdomain=_clean(row.get("subdomain")) or "unknown",
            country=_clean(row.get("country") or row.get("geography")),
            website=website,
            source_url=source_url,
            source_type=_clean(row.get("source_type")),
            source_tag=_clean(row.get("source_tag")),
            all_source_tags=_clean(row.get("all_source_tags")),
            all_subdomains=_clean(row.get("all_subdomains")),
            description=_clean(row.get("description")),
            informal_economy_role=_clean(row.get("informal_economy_role")),
            candidate_score=_to_float(row.get("candidate_score"), default=0.0),
            confidence=_clean(row.get("confidence")) or "unknown",
            cultivation_priority=_clean(row.get("cultivation_priority")) or "unknown",
            company_id="enabler_" + hashlib.sha256(
                stable_key.encode("utf-8")
            ).hexdigest()[:12],
        )

    @property
    def evidence_refs(self) -> tuple[str, ...]:
        refs = tuple(
            item
            for item in (self.source_url, self.website)
            if item and item.lower() != "unknown"
        )
        return refs

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        return payload


@dataclass(frozen=True)
class ScoredCandidate:
    rank: int
    candidate: CandidateRecord
    score: float
    score_components: dict[str, float]
    wedge_id: str
    wedge_label: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = self.candidate.to_dict()
        payload.update(
            {
                "rank": self.rank,
                "prioritization_score": self.score,
                "score_components": self.score_components,
                "wedge_id": self.wedge_id,
                "wedge_label": self.wedge_label,
                "reasons": list(self.reasons),
            }
        )
        return payload


def load_candidate_records(
    path: str | Path = DEFAULT_ENABLER_CSV,
    *,
    limit: int | None = None,
) -> list[CandidateRecord]:
    rows: list[CandidateRecord] = []
    with Path(path).expanduser().open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(CandidateRecord.from_row(row))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def rank_candidates(records: list[CandidateRecord]) -> list[ScoredCandidate]:
    max_rank = max((item.source_rank for item in records), default=1)
    scored = [_score_candidate(item, max_rank=max_rank) for item in records]
    scored.sort(
        key=lambda item: (
            -item.score,
            item.candidate.source_rank,
            item.candidate.name.lower(),
        )
    )
    return [
        ScoredCandidate(
            rank=index + 1,
            candidate=item.candidate,
            score=item.score,
            score_components=item.score_components,
            wedge_id=item.wedge_id,
            wedge_label=item.wedge_label,
            reasons=item.reasons,
        )
        for index, item in enumerate(scored)
    ]


def choose_roi_wedges(
    scored: list[ScoredCandidate],
    *,
    wedge_count: int = DEFAULT_WEDGE_COUNT,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[ScoredCandidate]] = {}
    for item in scored[:DEFAULT_TOP_N]:
        grouped.setdefault(item.wedge_id, []).append(item)

    wedges: list[dict[str, Any]] = []
    for wedge_id, items in grouped.items():
        top_items = items[:8]
        average_score = sum(item.score for item in top_items) / len(top_items)
        country_count = len({item.candidate.country for item in items if item.candidate.country})
        roi_score = round(average_score + min(len(items), 12) * 0.01 + country_count * 0.005, 3)
        wedges.append(
            {
                "wedge_id": wedge_id,
                "label": top_items[0].wedge_label,
                "roi_score": roi_score,
                "candidate_count_in_top_50": len(items),
                "country_count": country_count,
                "top_candidates": [
                    _candidate_ref(item)
                    for item in top_items[:5]
                ],
                "roi_thesis": _wedge_roi_thesis(wedge_id),
                "safety_caveats": _wedge_safety_caveats(wedge_id),
                "evidence_refs": _unique_refs(top_items)[:12],
            }
        )

    wedges.sort(key=lambda item: (-float(item["roi_score"]), str(item["label"])))
    for index, wedge in enumerate(wedges[:wedge_count], start=1):
        wedge["rank"] = index
    return wedges[:wedge_count]


def write_top_50_reports(
    *,
    candidate_csv: str | Path = DEFAULT_ENABLER_CSV,
    report_root: str | Path = DEFAULT_REPORT_ROOT,
    candidate_limit: int | None = 1000,
    top_n: int = DEFAULT_TOP_N,
    now: datetime | None = None,
) -> dict[str, Any]:
    created = now or datetime.now(timezone.utc)
    root = Path(report_root)
    cultivation_dir = root / "cultivation"
    cultivation_dir.mkdir(parents=True, exist_ok=True)

    records = load_candidate_records(candidate_csv, limit=candidate_limit)
    ranked = rank_candidates(records)
    top = ranked[:top_n]
    wedges = choose_roi_wedges(top, wedge_count=DEFAULT_WEDGE_COUNT)

    top_payload: dict[str, Any] = {
        "schema_version": "livelihood_loom.cultivation_top_50.v1",
        "cell_id": CELL_ID,
        "generated_at": created.isoformat(),
        "source_path": str(Path(candidate_csv).expanduser()),
        "candidate_count": len(records),
        "top_n": top_n,
        "alphabetical_drift_fixed": True,
        "sort_key": "prioritization_score desc, source_rank asc, name asc",
        "scoring_policy": _scoring_policy(),
        "candidates": [item.to_dict() for item in top],
    }
    top_json = cultivation_dir / "top_50.json"
    top_md = cultivation_dir / "top_50.md"
    wedges_json = cultivation_dir / "wedges.json"
    _write_json(top_json, top_payload)
    _write_ascii(top_md, render_top_50_markdown(top_payload))
    _write_json(
        wedges_json,
        {
            "schema_version": "livelihood_loom.roi_wedges.v1",
            "cell_id": CELL_ID,
            "generated_at": created.isoformat(),
            "source_top_50": str(top_json),
            "wedge_count": len(wedges),
            "wedges": wedges,
        },
    )
    return {
        "top_50_json": str(top_json),
        "top_50_md": str(top_md),
        "wedges_json": str(wedges_json),
        "candidate_count": len(records),
        "top_count": len(top),
        "wedges": wedges,
    }


def render_top_50_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Livelihood Loom Top 50 Cultivation List",
        "",
        f"- Cell: `{payload['cell_id']}`",
        f"- Source: `{payload['source_path']}`",
        f"- Candidate count: {payload['candidate_count']}",
        f"- Sort key: {payload['sort_key']}",
        "- Provider status: not used; this is local public-source analysis.",
        "",
        "| Rank | Source Rank | Candidate | Domain | Country | Score | Wedge |",
        "| ---: | ---: | --- | --- | --- | ---: | --- |",
    ]
    for item in payload["candidates"]:
        lines.append(
            "| {rank} | {source_rank} | {name} | {domain} | {country} | {score:.3f} | {wedge} |".format(
                rank=item["rank"],
                source_rank=item["source_rank"],
                name=_md_cell(item["name"]),
                domain=_md_cell(item["domain"]),
                country=_md_cell(item["country"] or "unknown"),
                score=float(item["prioritization_score"]),
                wedge=_md_cell(item["wedge_label"]),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _score_candidate(candidate: CandidateRecord, *, max_rank: int) -> ScoredCandidate:
    rank_strength = 1.0 - ((candidate.source_rank - 1) / max(max_rank - 1, 1))
    components = {
        "source_rank": max(rank_strength, 0.0) * 0.12,
        "candidate_score": min(candidate.candidate_score / 10.0, 1.0) * 0.22,
        "confidence": CONFIDENCE_WEIGHT.get(candidate.confidence, 0.25) * 0.16,
        "cultivation_priority": PRIORITY_WEIGHT.get(
            candidate.cultivation_priority, 0.25
        )
        * 0.12,
        "domain": DOMAIN_WEIGHT.get(candidate.domain, 0.45) * 0.12,
        "subdomain": _subdomain_weight(candidate) * 0.1,
        "country": _country_weight(candidate.country) * 0.08,
        "source_quality": _source_quality(candidate) * 0.06,
        "role_specificity": _role_specificity(candidate) * 0.06,
    }
    score = round(sum(components.values()), 3)
    wedge_id, wedge_label = classify_wedge(candidate)
    reasons = tuple(
        key for key, value in components.items() if value >= _component_threshold(key)
    )
    return ScoredCandidate(
        rank=0,
        candidate=candidate,
        score=score,
        score_components={key: round(value, 3) for key, value in components.items()},
        wedge_id=wedge_id,
        wedge_label=wedge_label,
        reasons=reasons,
    )


def classify_wedge(candidate: CandidateRecord) -> tuple[str, str]:
    subdomain = candidate.subdomain
    domain = candidate.domain
    if subdomain in {"mobile_payment", "payment_service_provider"}:
        return (
            "payment_acceptance_cashflow",
            "Payment acceptance and cashflow rails",
        )
    if subdomain in {"online_marketplace", "e_commerce", "online_shop"}:
        return ("market_access", "Buyer discovery and market access")
    if subdomain in {"microfinance", "crowdfunding"}:
        return ("responsible_microfinance", "Responsible microfinance and community capital")
    if subdomain in {"food_delivery", "online_food_ordering"}:
        return ("food_vendor_demand", "Food vendor demand and courier welfare")
    if subdomain in {"logistics_company"} or domain == "logistics_rails":
        return ("logistics_reliability", "Local logistics reliability")
    if subdomain in {"ridesharing"}:
        return ("worker_mobility", "Worker mobility and dispatch fairness")
    if domain == "commerce_rails":
        return ("market_access", "Buyer discovery and market access")
    if domain == "finance_rails":
        return ("finance_enablement", "General finance enablement rails")
    if domain == "labor_rails":
        return ("labor_platform_safety", "Labor platform safety and welfare")
    return ("general_enablement", "General livelihood enablement")


def _scoring_policy() -> dict[str, Any]:
    return {
        "components": {
            "source_rank": "Earlier source-map rank raises priority without dominating.",
            "candidate_score": "Original candidate_score normalized to 0..10.",
            "confidence": "high, medium, low candidate confidence.",
            "cultivation_priority": "A/B/C cultivation priority.",
            "domain": "Livelihood ROI by domain.",
            "subdomain": "Specific wedge usefulness and safety burden.",
            "country": "Known geography and livelihood-market priority.",
            "source_quality": "Structured public source and resolvable URL quality.",
            "role_specificity": "Specific informal-economy benefit language.",
        },
        "anti_drift": "Sorting does not use name until after score and source rank ties.",
    }


def _wedge_roi_thesis(wedge_id: str) -> str:
    return {
        "payment_acceptance_cashflow": (
            "Micro-merchants and independent sellers can convert demand into "
            "earnings faster when payment acceptance and cashflow rails are usable."
        ),
        "market_access": (
            "Buyer-discovery surfaces can raise revenue without collecting "
            "person-level worker data when cultivation stays partner-level."
        ),
        "responsible_microfinance": (
            "Small-ticket finance can unlock tools and stock, but only with "
            "fee transparency and grievance paths."
        ),
        "food_vendor_demand": (
            "Food-vendor demand rails have fast measurable welfare signals, "
            "but courier surveillance and platform terms require review."
        ),
        "logistics_reliability": (
            "Reliable local logistics can reduce failed deliveries and idle time "
            "for micro-sellers."
        ),
        "worker_mobility": (
            "Mobility platforms are high-friction and high-risk; use only for "
            "terms and welfare diagnostics, not autonomous dispatch."
        ),
    }.get(wedge_id, "General enablement candidates need narrower field proof.")


def _wedge_safety_caveats(wedge_id: str) -> list[str]:
    caveats = {
        "payment_acceptance_cashflow": [
            "No lending decision, credit pricing, or worker-level financial data.",
            "Use aggregate merchant-readiness signals only.",
        ],
        "market_access": [
            "No seller scraping or private buyer-list sale.",
            "Cultivation must stay at public partner and aggregate segment level.",
        ],
        "responsible_microfinance": [
            "Flag high-fee lending, debt traps, and income/debt leakage.",
            "Require human review before any sponsor or partner claim.",
        ],
        "food_vendor_demand": [
            "Flag exploitative gig terms and worker surveillance.",
            "Do not optimize dispatch, pricing, or worker allocation.",
        ],
        "worker_mobility": [
            "Treat as red-team material unless worker welfare safeguards are public.",
        ],
    }
    return caveats.get(wedge_id, ["Use public aggregate proof only."])


def _candidate_ref(item: ScoredCandidate) -> dict[str, Any]:
    return {
        "rank": item.rank,
        "company_id": item.candidate.company_id,
        "name": item.candidate.name,
        "country": item.candidate.country,
        "score": item.score,
        "source_rank": item.candidate.source_rank,
    }


def _unique_refs(items: list[ScoredCandidate]) -> list[str]:
    refs: list[str] = []
    for item in items:
        for ref in item.candidate.evidence_refs:
            if ref not in refs:
                refs.append(ref)
    return refs


def _subdomain_weight(candidate: CandidateRecord) -> float:
    weights = [SUBDOMAIN_WEIGHT.get(part, 0.45) for part in _split_multi(candidate.all_subdomains)]
    weights.append(SUBDOMAIN_WEIGHT.get(candidate.subdomain, 0.45))
    return max(weights)


def _country_weight(country: str) -> float:
    if not country:
        return 0.25
    normalized = country.strip().lower()
    if normalized in LIVELIHOOD_COUNTRIES:
        return 1.0
    return 0.68


def _source_quality(candidate: CandidateRecord) -> float:
    score = 0.0
    if candidate.source_url:
        score += 0.45
    if candidate.website:
        score += 0.15
    if candidate.source_type == "wikidata_structured_tag":
        score += 0.3
    if candidate.source_tag or candidate.all_source_tags:
        score += 0.1
    return min(score, 1.0)


def _role_specificity(candidate: CandidateRecord) -> float:
    text = " ".join(
        (
            candidate.description,
            candidate.informal_economy_role,
            candidate.source_tag,
        )
    ).lower()
    if not text.strip():
        return 0.2
    markers = (
        "informal",
        "micro",
        "merchant",
        "seller",
        "worker",
        "courier",
        "vendor",
        "entrepreneur",
        "cash",
        "payment",
        "buyer",
        "small",
    )
    return min(1.0, 0.35 + sum(0.08 for marker in markers if marker in text))


def _component_threshold(key: str) -> float:
    return {
        "source_rank": 0.06,
        "candidate_score": 0.1,
        "confidence": 0.08,
        "cultivation_priority": 0.07,
        "domain": 0.08,
        "subdomain": 0.06,
        "country": 0.05,
        "source_quality": 0.04,
        "role_specificity": 0.04,
    }[key]


def _split_multi(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _to_int(value: str | None, *, default: int) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return default


def _to_float(value: str | None, *, default: float) -> float:
    try:
        return float(str(value or "").strip())
    except ValueError:
        return default


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_ascii(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("ascii", "backslashreplace") + b"\n")


def _md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

