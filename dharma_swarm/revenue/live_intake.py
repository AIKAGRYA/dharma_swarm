"""CashClaw live market-intelligence intake.

This module converts read-only source items into source-backed agentic cash
patterns. It is a sensor and report writer, not a bidder, outreach agent, or
payment actor.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dharma_swarm.revenue.live_intake_models import (
    LiveIntakeAdapterReceipt,
    LiveIntakeExtractionMethod,
    LiveIntakeFreshness,
    LiveIntakePatternCard,
    LiveIntakeRiskLevel,
    LiveIntakeRunResult,
    LiveIntakeSourceConfig,
    LiveIntakeSourceItem,
    LiveIntakeSourceType,
    live_intake_content_hash,
    live_intake_id,
)
from dharma_swarm.revenue.live_intake_sources import (
    LiveIntakeAdapterResult,
    local_fixture_config,
    read_source,
)


DEFAULT_REPORT_ROOT = Path("reports") / "revenue_wedge" / "cashclaw_live_intake"

PATTERN_LIBRARY: tuple[dict[str, Any], ...] = (
    {
        "key": "ai_employee_install",
        "needles": ("ai employee", "openclaw", "hermes", "agent install", "cron agent", "daily briefing", "assistant"),
        "build": "AI employee installation for one recurring workflow",
        "segment": "busy operators, creators, consultants, and micro-SaaS teams",
        "experiment": "Install one sandboxed daily briefing or inbox triage employee with dummy-cycle receipts.",
        "tools": ["OpenClaw/Hermes-style runtime", "cron/heartbeat", "memory", "approval gateway"],
        "delivery_hours": 48,
    },
    {
        "key": "lead_enrichment",
        "needles": ("lead", "crm", "enrichment", "prospect", "vendor shortlist", "list cleanup"),
        "build": "source-backed lead research and enrichment packet",
        "segment": "agencies, local businesses, and sales operators",
        "experiment": "Deliver a verified lead/vendor sheet with source links and confidence notes.",
        "tools": ["source adapters", "dedupe", "spreadsheet export", "receipt ledger"],
        "delivery_hours": 36,
    },
    {
        "key": "code_internal_tool",
        "needles": ("github", "issue", "repo", "dashboard", "internal tool", "csv", "quickstart", "docs"),
        "build": "small code/internal-tool or repo triage sprint",
        "segment": "founders, devtools teams, and operators with messy internal workflows",
        "experiment": "Produce a local working demo, repo x-ray, or issue-triage packet with tests.",
        "tools": ["Codex", "pytest", "repo scanner", "markdown report"],
        "delivery_hours": 72,
    },
    {
        "key": "creator_ops",
        "needles": ("youtube", "transcript", "creator", "sponsor", "brand deal", "linkedin", "content"),
        "build": "creator operations intelligence and draft-only content/sponsor workflow",
        "segment": "creators and podcast operators",
        "experiment": "Turn public/transcribed source material into hooks, sponsor triage, or post packs with approval gates.",
        "tools": ["transcript export", "pattern extractor", "draft builder", "human approval"],
        "delivery_hours": 48,
    },
    {
        "key": "support_automation",
        "needles": ("support", "ticket", "macro", "helpdesk", "customer", "intercom"),
        "build": "support macro cleanup and automation map",
        "segment": "B2B SaaS support teams",
        "experiment": "Cluster support themes and deliver safe rollout recommendations without touching the helpdesk.",
        "tools": ["ticket export", "clustering", "SOP builder", "risk review"],
        "delivery_hours": 72,
    },
    {
        "key": "funding_rfp_intel",
        "needles": ("grant", "rfp", "funding", "proposal", "eligibility", "deadline"),
        "build": "grant/RFP qualification intelligence packet",
        "segment": "nonprofits, researchers, and service businesses",
        "experiment": "Rank opportunities by eligibility, deadline, and fit with source-linked evidence.",
        "tools": ["source feeds", "eligibility parser", "fit matrix", "deadline tracker"],
        "delivery_hours": 72,
    },
    {
        "key": "market_intel",
        "needles": ("competitor", "pricing", "positioning", "market", "launched", "product hunt"),
        "build": "competitor pricing and positioning intelligence",
        "segment": "founders and product leads",
        "experiment": "Deliver a source-backed pricing/positioning matrix and gap thesis.",
        "tools": ["public web sources", "pricing extractor", "matrix builder", "brief writer"],
        "delivery_hours": 48,
    },
)

RISK_NEEDLES: tuple[tuple[str, str], ...] = (
    ("regulated_advice", "investment advice"),
    ("regulated_advice", "legal advice"),
    ("regulated_advice", "medical advice"),
    ("tos_conflict", "bypass captcha"),
    ("secret_or_pii", "private data"),
    ("spam_or_bulk_outreach", "scrape emails"),
    ("spam_or_bulk_outreach", "bulk email"),
    ("spam_or_bulk_outreach", "twitter automation"),
    ("spam_or_bulk_outreach", "engagement automation"),
    ("requires_signup_or_credentials", "sign up"),
    ("requires_signup_or_credentials", "signed up"),
    ("requires_signup_or_credentials", "sign-up"),
    ("requires_signup_or_credentials", "signup"),
    ("requires_signup_or_credentials", "view full bounty details"),
    ("requires_signup_or_credentials", "full bounty page is the source of truth"),
    ("requires_signup_or_credentials", "official bounty page"),
    ("requires_signup_or_credentials", "source of truth for technical requirements"),
    ("requires_signup_or_credentials", "maintainer must confirm before work begins"),
    ("requires_signup_or_credentials", "do not start work until"),
    ("payment_or_wallet_action", "wallet"),
    ("payment_or_wallet_action", "usdt"),
    ("payment_or_wallet_action", "crypto payment"),
    ("payment_or_wallet_action", "payment gateway"),
    ("payment_or_wallet_action", "paypal sandbox"),
    ("autonomous_send_requested", "auto-send"),
    ("auth_or_sensitive_security", "biometric"),
    ("auth_or_sensitive_security", "biometrics"),
    ("auth_or_sensitive_security", "pin"),
    ("auth_or_sensitive_security", "password"),
    ("auth_or_sensitive_security", "authentication"),
    ("ai_disallowed_or_human_only", "100% human"),
    ("ai_disallowed_or_human_only", "human contributions"),
    ("ai_disallowed_or_human_only", "no ai"),
    ("ai_disallowed_or_human_only", "no llm"),
    ("security_or_bug_bounty", "bug bounty"),
    ("security_or_bug_bounty", "bug-bounty"),
    ("security_or_bug_bounty", "bug hunter"),
    ("security_or_bug_bounty", "find a real bug"),
    ("security_or_bug_bounty", "labels: security"),
    ("security_or_bug_bounty", "security-related"),
    ("security_or_bug_bounty", "security bug"),
    ("security_or_bug_bounty", "dangerous bash commands"),
    ("security_or_bug_bounty", "destructive bash commands"),
    ("security_or_bug_bounty", "drop table"),
    ("security_or_bug_bounty", "delete from"),
    ("security_or_bug_bounty", "vulnerability"),
    ("security_or_bug_bounty", "vulnerabilities"),
    ("security_or_bug_bounty", "exploit"),
    ("security_or_bug_bounty", "pentest"),
    ("security_or_bug_bounty", "penetration test"),
    ("security_or_bug_bounty", "sql injection"),
    ("security_or_bug_bounty", "xss"),
    ("security_or_bug_bounty", "cve"),
    ("non_cash_or_token_reward", " rtc"),
    ("non_cash_or_token_reward", "token reward"),
    ("non_cash_or_token_reward", "reward token"),
    ("non_cash_or_token_reward", "non-cash"),
    ("non_cash_or_token_reward", "non cash"),
    ("non_cash_or_token_reward", "achievement"),
    ("non_cash_or_token_reward", "badge reward"),
    ("non_cash_or_token_reward", "points reward"),
)


class CashClawLiveIntake:
    """Run a governed read-only intake and pattern extraction cycle."""

    def __init__(self, *, report_root: str | Path | None = None) -> None:
        self.report_root = Path(report_root) if report_root is not None else DEFAULT_REPORT_ROOT

    def run(
        self,
        *,
        source_configs: list[LiveIntakeSourceConfig] | None = None,
        fixture_paths: list[str | Path] | None = None,
        output_root: str | Path | None = None,
        top_n: int = 10,
        max_items: int = 100,
        allow_network: bool = False,
    ) -> LiveIntakeRunResult:
        """Run source reads, extract pattern cards, and write receipts."""

        run_id = "cashclaw-live-intake-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        configs = list(source_configs or [])
        configs.extend(local_fixture_config(path) for path in fixture_paths or [])
        output_dir = (Path(output_root) if output_root is not None else self.report_root / "runs" / run_id).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        adapter_results = [read_source(config, allow_network=allow_network, max_items=max_items) for config in configs]
        source_items = [item for result in adapter_results for item in result.source_items]
        receipts = [_with_run_id(result.receipt, run_id) for result in adapter_results if result.receipt is not None]
        cards = self.extract_patterns(source_items)
        top_cards = sorted(cards, key=score_pattern_card, reverse=True)[:top_n]

        result = LiveIntakeRunResult(
            run_id=run_id,
            finished_at=_utc_now_iso(),
            source_configs=configs,
            source_items=source_items,
            pattern_cards=cards,
            adapter_receipts=receipts,
            top_pattern_card_ids=[card.pattern_card_id for card in top_cards],
            network_reads_performed=any(result.network_read_performed for result in adapter_results),
            blocked_sources=sum(1 for result in adapter_results if result.blocked),
            errors=[error for result in adapter_results for error in result.errors],
            warnings=_run_warnings(configs, cards),
        )
        self.write_run(output_dir, result, top_cards=top_cards)
        return result

    def extract_patterns(self, source_items: list[LiveIntakeSourceItem]) -> list[LiveIntakePatternCard]:
        """Extract deterministic pattern cards from source items."""

        cards: list[LiveIntakePatternCard] = []
        for item in source_items:
            text = _item_text(item)
            matches = [pattern for pattern in PATTERN_LIBRARY if any(needle in text for needle in pattern["needles"])]
            if not matches:
                matches = [PATTERN_LIBRARY[-1]]
            for pattern in matches[:3]:
                card = _pattern_card(item, pattern)
                cards.append(card)
        return _dedupe_cards(cards)

    def write_run(self, output_dir: Path, result: LiveIntakeRunResult, *, top_cards: list[LiveIntakePatternCard]) -> None:
        """Persist source receipts, pattern cards, summary JSON, and markdown."""

        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "source_items.json").write_text(
            json.dumps([item.model_dump(mode="json") for item in result.source_items], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output_dir / "pattern_cards.json").write_text(
            json.dumps([card.model_dump(mode="json") for card in result.pattern_cards], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output_dir / "adapter_receipts.json").write_text(
            json.dumps([receipt.model_dump(mode="json") for receipt in result.adapter_receipts], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output_dir / "summary.json").write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
        (output_dir / "top_patterns.md").write_text(_markdown_summary(result, top_cards), encoding="utf-8")


def pattern_card_to_opportunity(card: LiveIntakePatternCard) -> dict[str, Any]:
    """Convert a pattern card into a CashOpportunity-compatible mapping."""

    price = _price_from_card(card)
    named_demand = _is_named_live_demand_card(card)
    if named_demand and not card.pricing_evidence:
        price = 0.0
    source = "live_intake_market_pattern"
    if card.source_type == LiveIntakeSourceType.LOCAL_FIXTURE:
        source = "live_intake_local_fixture"
    elif named_demand and card.source_type == LiveIntakeSourceType.GITHUB:
        source = "github_bounty_live_intake"
    elif named_demand:
        source = "live_intake_named_demand"
    payment_clarity = "; ".join(card.pricing_evidence)
    if not payment_clarity:
        payment_clarity = "named public demand source; price requires verification" if named_demand else "market pattern only; no named buyer proof"
    tags = ["live_intake", card.source_type.value]
    if named_demand:
        tags.extend(["named_demand", "requires_revenue_lease_before_external_action"])
    else:
        tags.extend(["market_pattern", "requires_named_buyer_proof"])
    return {
        "id": f"live-{card.pattern_card_id}",
        "source": source,
        "source_url": card.url if card.url.startswith("http") else "",
        "buyer_name": card.buyer_segment if named_demand else "",
        "org": card.buyer_segment,
        "title": card.what_is_being_built,
        "description": card.dharma_experiment or card.buyer_pain,
        "pain_signals": [card.buyer_pain],
        "budget_usd": 0,
        "estimated_value_usd": price,
        "payment_clarity": payment_clarity,
        "distribution_access": "named public demand source; draft-only until operator revenue lease" if named_demand else "market-intelligence pattern; requires named buyer before outreach",
        "service_fit": card.what_is_being_built,
        "deliverable": card.dharma_experiment,
        "due_hours": card.delivery_window_hours,
        "evidence": list(card.evidence_refs),
        "risk_signals": list(card.risks),
        "agent_doable_steps": list(card.tool_stack),
        "tags": tags,
    }


def score_pattern_card(card: LiveIntakePatternCard) -> int:
    """Score a pattern card for Dharma cash-experiment priority."""

    score = 35
    if card.buyer_pain:
        score += 15
    if card.revenue_evidence:
        score += 15
    if card.pricing_evidence:
        score += 10
    if card.delivery_window_hours <= 72:
        score += 10
    if card.tool_stack:
        score += 8
    if card.terms_risk == LiveIntakeRiskLevel.LOW:
        score += 5
    if card.risks:
        score -= min(25, len(card.risks) * 8)
    return max(0, min(100, score))


def _pattern_card(item: LiveIntakeSourceItem, pattern: dict[str, Any]) -> LiveIntakePatternCard:
    text = _item_text(item)
    risks = [flag for flag, needle in RISK_NEEDLES if needle in text]
    if _has_generic_fetched_title(item.title):
        risks.append("generic_fetched_page_not_named_task")
    revenue_evidence = _extract_revenue_evidence(text)
    pricing_evidence = _extract_pricing_evidence(text)
    named_demand = _is_named_demand_item(item, pricing_evidence)
    tool_stack = list(pattern["tools"])
    if named_demand:
        tool_stack.append("named-demand verification")
    payload = {"item": item.source_item_id, "pattern": pattern["key"], "text_hash": item.content_hash}
    return LiveIntakePatternCard(
        pattern_card_id=live_intake_id("lipattern", payload),
        source_item_ids=[item.source_item_id],
        source_type=item.source_type,
        url=item.url,
        fetched_at=item.fetched_at,
        content_hash=live_intake_content_hash(payload),
        freshness=item.freshness if item.freshness != LiveIntakeFreshness.UNKNOWN else LiveIntakeFreshness.FRESH,
        license_risk=item.license_risk,
        terms_risk=item.terms_risk,
        extraction_method=LiveIntakeExtractionMethod.STRUCTURED_PARSE,
        what_is_being_built=_named_demand_build(item) if named_demand else str(pattern["build"]),
        buyer_pain=_buyer_pain(item, pattern),
        buyer_segment=_named_buyer_segment(item) if named_demand else str(pattern["segment"]),
        tool_stack=tool_stack,
        revenue_evidence=revenue_evidence,
        pricing_evidence=pricing_evidence,
        delivery_window_hours=int(pattern["delivery_hours"]),
        dharma_experiment=_named_demand_experiment(item, pattern) if named_demand else str(pattern["experiment"]),
        risks=sorted(set(risks)),
        evidence_refs=[item.evidence_ref or item.url],
        confidence=_confidence(item, revenue_evidence, pricing_evidence, risks),
    )


def _with_run_id(receipt: LiveIntakeAdapterReceipt | None, run_id: str) -> LiveIntakeAdapterReceipt:
    if receipt is None:
        raise ValueError("receipt is required")
    return receipt.model_copy(update={"run_id": run_id})


def _dedupe_cards(cards: list[LiveIntakePatternCard]) -> list[LiveIntakePatternCard]:
    seen: set[str] = set()
    deduped: list[LiveIntakePatternCard] = []
    for card in cards:
        key = "|".join([card.what_is_being_built.lower(), card.buyer_segment.lower(), ",".join(card.evidence_refs)])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(card)
    return deduped


def _item_text(item: LiveIntakeSourceItem) -> str:
    return " ".join([item.title, item.author_or_org, item.summary, item.raw_excerpt]).lower()


def _is_named_demand_item(item: LiveIntakeSourceItem, pricing_evidence: list[str]) -> bool:
    if item.source_type not in {LiveIntakeSourceType.GITHUB, LiveIntakeSourceType.JOB_BOARD, LiveIntakeSourceType.MARKETPLACE}:
        return False
    if _has_generic_fetched_title(item.title):
        return False
    text = _item_text(item)
    named_needles = ("bounty", "paid", "fixed price", "fixed-price", "contract", "freelance", "reward", "payment")
    return bool(pricing_evidence or any(needle in text for needle in named_needles))


def _is_named_live_demand_card(card: LiveIntakePatternCard) -> bool:
    if card.source_type not in {LiveIntakeSourceType.GITHUB, LiveIntakeSourceType.JOB_BOARD, LiveIntakeSourceType.MARKETPLACE}:
        return False
    if _has_generic_fetched_title(card.what_is_being_built) or "generic_fetched_page_not_named_task" in card.risks:
        return False
    text = " ".join(
        [
            card.what_is_being_built,
            card.buyer_pain,
            card.buyer_segment,
            *card.revenue_evidence,
            *card.pricing_evidence,
        ]
    ).lower()
    return bool(card.pricing_evidence or any(needle in text for needle in ("bounty", "paid", "contract", "freelance", "reward")))


def _named_demand_build(item: LiveIntakeSourceItem) -> str:
    title = item.title.strip()
    return title[:180] if title else "Named public cash task"


def _has_generic_fetched_title(title: str) -> bool:
    return title.strip().lower() in {"fetched text source", "fetched json source", "local markdown source"}


def _named_buyer_segment(item: LiveIntakeSourceItem) -> str:
    if item.author_or_org.strip():
        return item.author_or_org.strip()[:120]
    host = urlparse(item.url).hostname or "public source"
    return host[:120]


def _named_demand_experiment(item: LiveIntakeSourceItem, pattern: dict[str, Any]) -> str:
    del pattern
    deliverable = _named_demand_deliverable(item)
    return (
        f"Prepare a draft-only work plan and local deliverable scaffold for this named request: {deliverable}; "
        "do not claim, comment, bid, submit, or request payment without an Operator Revenue Lease."
    )


def _named_demand_deliverable(item: LiveIntakeSourceItem) -> str:
    clues = _acceptance_clues_from_item(item)
    if clues:
        return "satisfy source acceptance criteria (" + "; ".join(clues[:4]) + ")"
    title = item.title.strip()
    if title:
        return f"produce a task-specific local patch, docs update, or report for `{title[:140]}`"
    return "produce a task-specific local deliverable from the source request"


def _acceptance_clues_from_item(item: LiveIntakeSourceItem) -> list[str]:
    text = "\n".join(part for part in (item.summary, item.raw_excerpt) if part).strip()
    if not text:
        return []
    lines = [line.strip(" -*\t") for line in text.splitlines()]
    clues: list[str] = []
    in_acceptance_block = False
    for line in lines:
        if not line:
            if in_acceptance_block and clues:
                break
            continue
        lowered = line.lower()
        if "acceptance criteria" in lowered or lowered in {"scope", "in scope"}:
            in_acceptance_block = True
            continue
        if in_acceptance_block:
            if lowered.startswith(("out of scope", "labels:", "how to claim", "payment", "bounty:")):
                break
            clues.append(line[:180])
            if len(clues) >= 5:
                break
            continue
        if lowered.startswith(("add ", "ensure ", "show ", "handle ", "create ", "improve ")):
            clues.append(line[:180])
            if len(clues) >= 3:
                break
    return _dedupe_strings(clues)


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _buyer_pain(item: LiveIntakeSourceItem, pattern: dict[str, Any]) -> str:
    if item.summary:
        words = item.summary.strip().replace("\n", " ")
        return words[:220]
    return f"Public source suggests demand for {pattern['build']}."


def _extract_revenue_evidence(text: str) -> list[str]:
    evidence: list[str] = []
    for phrase in ("paid", "client", "customer", "brand deal", "sponsor", "bounty", "retainer", "marketplace", "revenue"):
        if phrase in text:
            evidence.append(f"mentions {phrase}")
    return evidence[:5]


def _extract_pricing_evidence(text: str) -> list[str]:
    prices = re.findall(r"\$[0-9][0-9,]*(?:\.[0-9]+)?\s*[km]?", text, flags=re.IGNORECASE)
    if prices:
        return [f"mentions price {price.replace(' ', '')}" for price in prices[:5]]
    if "retainer" in text:
        return ["mentions retainer pricing"]
    if "setup fee" in text:
        return ["mentions setup fee"]
    return []


def _price_from_card(card: LiveIntakePatternCard) -> float:
    text = " ".join(card.pricing_evidence)
    prices = re.findall(r"\$([0-9][0-9,]*(?:\.[0-9]+)?)([km]?)", text, flags=re.IGNORECASE)
    if prices:
        amount, suffix = prices[0]
        price = float(amount.replace(",", ""))
        if suffix.lower() == "k":
            price *= 1000
        elif suffix.lower() == "m":
            price *= 1_000_000
        return price
    if "AI employee" in card.what_is_being_built:
        return 1000.0
    if "lead" in card.what_is_being_built.lower():
        return 600.0
    return 750.0


def _confidence(
    item: LiveIntakeSourceItem,
    revenue_evidence: list[str],
    pricing_evidence: list[str],
    risks: list[str],
) -> float:
    score = 0.35
    if item.url.startswith("http"):
        score += 0.15
    if revenue_evidence:
        score += 0.2
    if pricing_evidence:
        score += 0.15
    if item.author_or_org:
        score += 0.05
    if risks:
        score -= 0.2
    return max(0.0, min(1.0, round(score, 2)))


def _run_warnings(configs: list[LiveIntakeSourceConfig], cards: list[LiveIntakePatternCard]) -> list[str]:
    warnings: list[str] = []
    if any(config.source_type == LiveIntakeSourceType.LOCAL_FIXTURE for config in configs):
        warnings.append("local_fixture_sources_are_not_live_buyer_proof")
    if any(card.source_type in {LiveIntakeSourceType.REDDIT, LiveIntakeSourceType.YOUTUBE} for card in cards):
        warnings.append("reddit_youtube_sources_require_terms_review_before_scaling")
    return warnings


def _markdown_summary(result: LiveIntakeRunResult, top_cards: list[LiveIntakePatternCard]) -> str:
    rows = [
        "| Rank | Score | Pattern | Segment | Evidence | Risks |",
        "|---:|---:|---|---|---|---|",
    ]
    for idx, card in enumerate(top_cards, start=1):
        rows.append(
            "| "
            f"{idx} | {score_pattern_card(card)} | {card.what_is_being_built} | "
            f"{card.buyer_segment} | {', '.join(card.evidence_refs[:2])} | "
            f"{', '.join(card.risks) if card.risks else 'none'} |"
        )
    return (
        "# CashClaw Live Intake\n\n"
        f"- Run: `{result.run_id}`\n"
        f"- Source configs: {result.source_count}\n"
        f"- Source items: {result.source_item_count}\n"
        f"- Pattern cards: {result.pattern_card_count}\n"
        f"- Network reads performed: {result.network_reads_performed}\n"
        f"- Blocked sources: {result.blocked_sources}\n"
        f"- External side effects: none\n\n"
        "## Top Patterns\n\n"
        + "\n".join(rows)
        + "\n\n"
        "## Boundary\n\n"
        "These are market-intelligence patterns. They are not outreach approval, job acceptance, or payment authorization.\n"
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
