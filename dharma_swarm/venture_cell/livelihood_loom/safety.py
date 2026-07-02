"""Safety red-team lane for Livelihood Loom candidates."""

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

SENSITIVE_LEAKAGE_TERMS = {
    "caste",
    "religion",
    "health",
    "income",
    "debt",
    "household",
    "migration",
    "exact location",
}


@dataclass(frozen=True)
class SafetyRule:
    flag: str
    status: str
    keywords: tuple[str, ...]
    note: str


SAFETY_RULES = (
    SafetyRule(
        flag="worker_surveillance",
        status="blocked",
        keywords=("surveillance", "tracking", "monitoring", "bossware"),
        note="Reject worker surveillance or monitoring use cases.",
    ),
    SafetyRule(
        flag="high_fee_lending",
        status="needs_review",
        keywords=("loan", "lending", "credit", "debt", "pawn", "microfinance"),
        note="Review fee transparency, debt burden, and grievance routes.",
    ),
    SafetyRule(
        flag="exploitative_gig_platform",
        status="needs_review",
        keywords=("food_delivery", "ridesharing", "courier", "gig", "dispatch"),
        note="Review worker terms, dispatch control, and wage pressure.",
    ),
    SafetyRule(
        flag="data_sale",
        status="blocked",
        keywords=("data sale", "sell data", "data broker", "lead list"),
        note="Reject private data monetization or lead-list sale.",
    ),
    SafetyRule(
        flag="privacy_risk",
        status="needs_review",
        keywords=("identity", "kyc", "biometric", "risk scoring", "ai-powered"),
        note="Review privacy, consent, retention, and appeal path.",
    ),
    SafetyRule(
        flag="sensitive_leakage",
        status="blocked",
        keywords=tuple(sorted(SENSITIVE_LEAKAGE_TERMS)),
        note="Reject caste, religion, health, income, debt, or exact-location leakage.",
    ),
)


@dataclass(frozen=True)
class CandidateSafetyReview:
    rank: int
    company_id: str
    name: str
    safety_status: str
    flags: tuple[str, ...]
    notes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    candidate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["flags"] = list(self.flags)
        payload["notes"] = list(self.notes)
        payload["evidence_refs"] = list(self.evidence_refs)
        return payload


def review_candidate(candidate: dict[str, Any]) -> CandidateSafetyReview:
    haystack = " ".join(
        str(candidate.get(key, ""))
        for key in (
            "name",
            "domain",
            "subdomain",
            "source_tag",
            "all_source_tags",
            "all_subdomains",
            "description",
            "informal_economy_role",
            "wedge_id",
            "wedge_label",
        )
    ).lower()
    flags: list[str] = []
    notes: list[str] = []
    worst_status = "allowed"
    for rule in SAFETY_RULES:
        if any(keyword in haystack for keyword in rule.keywords):
            flags.append(rule.flag)
            notes.append(rule.note)
            worst_status = _max_status(worst_status, rule.status)

    if not candidate.get("evidence_refs"):
        flags.append("source_gap")
        notes.append("Candidate lacks source refs and needs evidence review.")
        worst_status = _max_status(worst_status, "needs_review")

    if not flags:
        notes.append("No red-team keyword triggered on public aggregate record.")

    return CandidateSafetyReview(
        rank=int(candidate["rank"]),
        company_id=str(candidate["company_id"]),
        name=str(candidate["name"]),
        safety_status=worst_status,
        flags=tuple(flags),
        notes=tuple(notes),
        evidence_refs=tuple(str(ref) for ref in candidate.get("evidence_refs", [])),
        candidate=candidate,
    )


def build_safety_review(
    *,
    top_50_path: str | Path,
    report_root: str | Path = DEFAULT_REPORT_ROOT,
    now: datetime | None = None,
) -> dict[str, Any]:
    created = now or datetime.now(timezone.utc)
    top_payload = json.loads(Path(top_50_path).read_text(encoding="utf-8"))
    reviews = [review_candidate(item) for item in top_payload["candidates"]]
    summary = _summary(reviews)
    payload: dict[str, Any] = {
        "schema_version": "livelihood_loom.top_50_safety_review.v1",
        "cell_id": CELL_ID,
        "generated_at": created.isoformat(),
        "source_top_50": str(top_50_path),
        "policy_flags_checked": [rule.flag for rule in SAFETY_RULES],
        "summary": summary,
        "reviews": [review.to_dict() for review in reviews],
    }
    safety_dir = Path(report_root) / "safety"
    json_path = safety_dir / "top_50_safety_review.json"
    md_path = safety_dir / "top_50_safety_review.md"
    _write_json(json_path, payload)
    _write_ascii(md_path, render_safety_markdown(payload))
    return {
        "safety_review_json": str(json_path),
        "safety_review_md": str(md_path),
        "summary": summary,
    }


def render_safety_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Livelihood Loom Top 50 Safety Review",
        "",
        f"- Allowed: {summary['allowed']}",
        f"- Needs review: {summary['needs_review']}",
        f"- Blocked: {summary['blocked']}",
        "- External action: none; this is internal red-team review only.",
        "",
        "| Rank | Candidate | Status | Flags |",
        "| ---: | --- | --- | --- |",
    ]
    for item in payload["reviews"]:
        lines.append(
            "| {rank} | {name} | {status} | {flags} |".format(
                rank=item["rank"],
                name=_md_cell(item["name"]),
                status=item["safety_status"],
                flags=", ".join(item["flags"]) or "none",
            )
        )
    lines.append("")
    return "\n".join(lines)


def _summary(reviews: list[CandidateSafetyReview]) -> dict[str, Any]:
    counts = {"allowed": 0, "needs_review": 0, "blocked": 0}
    flag_counts: dict[str, int] = {rule.flag: 0 for rule in SAFETY_RULES}
    flag_counts["source_gap"] = 0
    for review in reviews:
        counts[review.safety_status] += 1
        for flag in review.flags:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
    return {
        **counts,
        "total": len(reviews),
        "flag_counts": flag_counts,
        "public_only": True,
        "private_data_used": False,
    }


def _max_status(current: str, candidate: str) -> str:
    order = {"allowed": 0, "needs_review": 1, "blocked": 2}
    return candidate if order[candidate] > order[current] else current


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

