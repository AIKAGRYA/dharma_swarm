"""GO intake: economic primitive digestion for dharma_swarm.

The GO organ turns outside examples into structured case cards and optional
opportunity-board rows. It is deliberately non-custodial: no wallet actions,
no trades, no token launches, no outbound messages. The safe boundary is
ingest -> score -> propose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DHARMA_HOME = Path.home() / ".dharma"
DEFAULT_CASE_JSONL = DHARMA_HOME / "go/case_cards.jsonl"
DEFAULT_OPPORTUNITY_BOARD = DHARMA_HOME / "meta/opportunity_board.json"
BOUNDED_CONTEXT = "go_intake"
CAPABILITY_BOUNDARY = "ingestion_only"
DEFAULT_MOUTH = "manual_note"
ALLOWED_MOUTHS = frozenset({
    "manual_note",
    "repo_doc",
    "web_research",
    "agent_report",
    "market_snapshot",
    "provider_probe",
    "field_knowledge_base",
    "inquiry_seed",
    "telic_feedback",
    "customer_signal",
    "grant_call",
    "bounty_market",
    "competitor_release",
    "risk_incident",
    "social_attention",
    "compute_ledger",
})


@dataclass(frozen=True)
class PrimitiveProfile:
    primitive: str
    keywords: tuple[str, ...]
    dharma_mapping: tuple[str, ...]
    first_experiment: str
    economic_loop: str
    domain: str
    legal_safety: float
    telos_fit: float
    revenue_speed: float
    compute_leverage: float
    implementation_ease: float
    autonomy_gain: float


@dataclass
class GOCaseCard:
    case_id: str
    title: str
    primitive: str
    source_urls: list[str]
    economic_loop: str
    dharma_mapping: list[str]
    first_experiment: str
    risk: str
    score: float
    factor_scores: dict[str, float]
    source_sha256: str
    source_excerpt: str
    created_at: str
    hitl_required: bool = True
    no_fund_movement: bool = True
    bounded_context: str = BOUNDED_CONTEXT
    capability_boundary: str = CAPABILITY_BOUNDARY
    mouth: str = DEFAULT_MOUTH

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GOIntakeResult:
    cards: list[GOCaseCard]
    opportunity_rows: list[dict[str, Any]] = field(default_factory=list)
    case_jsonl: str = ""
    opportunity_board: str = ""
    dry_run: bool = True
    mouth: str = DEFAULT_MOUTH

    def to_json(self) -> dict[str, Any]:
        return {
            "cards": [card.to_json() for card in self.cards],
            "opportunity_rows": self.opportunity_rows,
            "case_jsonl": self.case_jsonl,
            "opportunity_board": self.opportunity_board,
            "dry_run": self.dry_run,
            "mouth": self.mouth,
        }


PROFILES: tuple[PrimitiveProfile, ...] = (
    PrimitiveProfile(
        primitive="incentive_market",
        keywords=("bittensor", "tao", "subnet", "validator", "miner", "emission", "yuma"),
        dharma_mapping=("economic_spine", "opportunity_board", "TelicSeam", "ValueEvent"),
        first_experiment="Simulate subnet-style rewards for GO scouts and validators; no token or staking.",
        economic_loop="Participants produce work, validators score it, emissions reward ranked contribution.",
        domain="economic_infrastructure",
        legal_safety=0.45,
        telos_fit=0.72,
        revenue_speed=0.38,
        compute_leverage=0.78,
        implementation_ease=0.46,
        autonomy_gain=0.86,
    ),
    PrimitiveProfile(
        primitive="agent_wallet_treasury",
        keywords=("virtuals", "erc-20", "base chain", "wallet", "treasury", "token", "agent token"),
        dharma_mapping=("Movement.sourcerer_ref", "economic_spine", "AgentIdentity", "Doctrine"),
        first_experiment="Paper-mode Movement treasury ledger with human-approved wallet boundary; no real funds.",
        economic_loop="Agent identity accumulates attention or usage value into a treasury that funds more work.",
        domain="movement_economy",
        legal_safety=0.28,
        telos_fit=0.56,
        revenue_speed=0.45,
        compute_leverage=0.56,
        implementation_ease=0.42,
        autonomy_gain=0.82,
    ),
    PrimitiveProfile(
        primitive="attention_to_capital",
        keywords=("truthterminal", "truth terminal", "$goat", "goat", "memecoin", "viral", "attention"),
        dharma_mapping=("BhedGnanMonitor", "telos_gates", "DOGMA_DRIFT", "WITNESS"),
        first_experiment="Study only: define anti-pattern gates for attention-to-capital loops; no launch.",
        economic_loop="AI-generated attention triggers speculative capital, which can fund more attention.",
        domain="risk_research",
        legal_safety=0.18,
        telos_fit=0.26,
        revenue_speed=0.62,
        compute_leverage=0.42,
        implementation_ease=0.55,
        autonomy_gain=0.64,
    ),
    PrimitiveProfile(
        primitive="agent_trading_framework",
        keywords=("ai16z", "eliza", "elizaos", "trading", "trades", "portfolio"),
        dharma_mapping=("ginko_paper_trade", "ginko_brier", "economic_spine", "WITNESS"),
        first_experiment="Paper-trading-only agent skill benchmark with Brier scoring and hard no-real-trade guard.",
        economic_loop="Agents allocate capital based on market signals and reinvest gains into the framework.",
        domain="paper_trading",
        legal_safety=0.30,
        telos_fit=0.45,
        revenue_speed=0.40,
        compute_leverage=0.45,
        implementation_ease=0.62,
        autonomy_gain=0.62,
    ),
    PrimitiveProfile(
        primitive="autonomous_treasury",
        keywords=("makerdao", "aave", "compound", "dao", "tvl", "treasury", "governance"),
        dharma_mapping=("economic_spine", "Doctrine", "GateDecisionRecord", "operator_approval"),
        first_experiment="Design a non-custodial treasury policy simulator with spending caps and gate records.",
        economic_loop="Protocol fees accrue to a governed treasury that funds ongoing development and risk work.",
        domain="treasury_governance",
        legal_safety=0.48,
        telos_fit=0.66,
        revenue_speed=0.30,
        compute_leverage=0.42,
        implementation_ease=0.50,
        autonomy_gain=0.70,
    ),
    PrimitiveProfile(
        primitive="self_evolution",
        keywords=("sakana", "darwin", "darwin-godel", "darwin-gödel", "dgm", "self-improving", "self-improving"),
        dharma_mapping=("DarwinEngine", "telos_gates", "evolution_archive", "packet_provenance"),
        first_experiment="Route GO-scored economic primitives into Darwin proposals under packet and gate constraints.",
        economic_loop="Code or harness changes improve performance, creating more useful work per unit compute.",
        domain="self_evolution",
        legal_safety=0.72,
        telos_fit=0.78,
        revenue_speed=0.34,
        compute_leverage=0.68,
        implementation_ease=0.58,
        autonomy_gain=0.74,
    ),
    PrimitiveProfile(
        primitive="compute_market",
        keywords=("akash", "runpod", "vast", "gensyn", "prime intellect", "gpu", "compute", "lambda", "coreweave"),
        dharma_mapping=("runtime_provider", "economic_spine", "compute_budget", "provider_quality_track"),
        first_experiment="ComputeTreasury v0: compare local/API/market GPU cost before any expensive run.",
        economic_loop="Marketplaces match workloads to available compute, reducing cost and expanding capacity.",
        domain="compute_acquisition",
        legal_safety=0.80,
        telos_fit=0.82,
        revenue_speed=0.46,
        compute_leverage=0.92,
        implementation_ease=0.66,
        autonomy_gain=0.78,
    ),
    PrimitiveProfile(
        primitive="agent_payment_rail",
        keywords=("x402", "http 402", "402 payment", "stablecoin", "usdc", "micropayment", "pay-per-use"),
        dharma_mapping=("economic_spine", "RevenueCell", "TelicSeam", "packet_provenance"),
        first_experiment="Expose a human-approved paid governance-scan API stub; payment integration remains testnet/mock.",
        economic_loop="Agents or users pay per API call without accounts, subscriptions, or manual invoicing.",
        domain="external_revenue",
        legal_safety=0.62,
        telos_fit=0.84,
        revenue_speed=0.82,
        compute_leverage=0.58,
        implementation_ease=0.72,
        autonomy_gain=0.66,
    ),
    PrimitiveProfile(
        primitive="vertical_agent_revenue",
        keywords=("servicenow", "agent 365", "agentforce", "harvey", "legora", "finance agent", "legal ai"),
        dharma_mapping=("opportunity_board", "economic_spine", "TelicSeam", "QUALITY_GATES"),
        first_experiment="Package the agentic code governance sprint as a scoped paid service.",
        economic_loop="Role-scoped agents do painful workflow work and prove ROI through audit trails.",
        domain="external_revenue",
        legal_safety=0.78,
        telos_fit=0.88,
        revenue_speed=0.86,
        compute_leverage=0.50,
        implementation_ease=0.78,
        autonomy_gain=0.55,
    ),
    PrimitiveProfile(
        primitive="research_paid_eval_outreach",
        keywords=(
            "anthropic model welfare",
            "kyle fish",
            "paid evaluation",
            "paid eval",
            "small grant",
            "small-grants",
            "research collaboration",
            "r_v",
            "model welfare",
        ),
        dharma_mapping=("RevenueCell", "external_outreach", "R_V", "opportunity_board", "TelicSeam"),
        first_experiment="Draft one human-approved paid R_V / governance evaluation outreach note.",
        economic_loop="A scoped evaluation or grant produces external funding, credibility, and compute budget.",
        domain="external_revenue",
        legal_safety=0.88,
        telos_fit=0.92,
        revenue_speed=0.74,
        compute_leverage=0.44,
        implementation_ease=0.86,
        autonomy_gain=0.42,
    ),
)

FALLBACK_PROFILE = PrimitiveProfile(
    primitive="economic_case_unknown",
    keywords=(),
    dharma_mapping=("field_knowledge_base", "opportunity_board"),
    first_experiment="Research and classify the economic primitive before implementation.",
    economic_loop="Unknown economic loop; requires source-grounded analysis.",
    domain="economic_research",
    legal_safety=0.55,
    telos_fit=0.50,
    revenue_speed=0.30,
    compute_leverage=0.30,
    implementation_ease=0.50,
    autonomy_gain=0.35,
)


def split_case_blocks(text: str) -> list[str]:
    """Split numbered or bulleted notes into case blocks."""

    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    marker = re.compile(r"^\s*(?:\d+\.|[-*])\s+")
    for line in lines:
        if marker.match(line):
            if current:
                blocks.append(current)
            current = [marker.sub("", line).strip()]
        elif current:
            current.append(line.rstrip())
    if current:
        blocks.append(current)
    if not blocks and text.strip():
        return [text.strip()]
    return ["\n".join(block).strip() for block in blocks if "\n".join(block).strip()]


def make_case_id(title: str, primitive: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not base:
        base = primitive
    return f"go-{base[:48]}"


def extract_title(block: str) -> str:
    first_line = next((line.strip() for line in block.splitlines() if line.strip()), "")
    title = first_line.split(".", 1)[0].strip()
    title = title.split("—", 1)[0].strip()
    title = title.split(":", 1)[0].strip()
    return title[:96] or "GO economic primitive"


def extract_urls(block: str) -> list[str]:
    return sorted(set(re.findall(r"https?://[^\s)>\]]+", block)))


def classify_primitive(block: str) -> PrimitiveProfile:
    lowered = block.lower()
    best = FALLBACK_PROFILE
    best_hits = 0
    for profile in PROFILES:
        hits = sum(1 for keyword in profile.keywords if keyword in lowered)
        if hits > best_hits:
            best = profile
            best_hits = hits
    return best


def risk_for_profile(profile: PrimitiveProfile, block: str) -> str:
    lowered = block.lower()
    if any(term in lowered for term in ("memecoin", "token launch", "trading", "real funds")):
        return "high"
    if profile.legal_safety < 0.35:
        return "high"
    if profile.legal_safety < 0.65:
        return "medium"
    return "low"


def score_profile(profile: PrimitiveProfile) -> tuple[float, dict[str, float]]:
    factors = {
        "telos_alignment": profile.telos_fit,
        "revenue_speed": profile.revenue_speed,
        "compute_leverage": profile.compute_leverage,
        "implementation_ease": profile.implementation_ease,
        "legal_safety": profile.legal_safety,
        "autonomy_gain": profile.autonomy_gain,
    }
    score = (
        0.25 * factors["telos_alignment"]
        + 0.20 * factors["revenue_speed"]
        + 0.15 * factors["compute_leverage"]
        + 0.15 * factors["implementation_ease"]
        + 0.15 * factors["legal_safety"]
        + 0.10 * factors["autonomy_gain"]
    )
    return round(score, 4), {key: round(value, 4) for key, value in factors.items()}


def validate_mouth(mouth: str) -> str:
    normalized = mouth.strip().lower().replace("-", "_")
    if normalized not in ALLOWED_MOUTHS:
        allowed = ", ".join(sorted(ALLOWED_MOUTHS))
        raise ValueError(f"unknown GO mouth {mouth!r}; allowed: {allowed}")
    return normalized


def case_card_from_block(
    block: str,
    *,
    now: datetime | None = None,
    mouth: str = DEFAULT_MOUTH,
) -> GOCaseCard:
    profile = classify_primitive(block)
    title = extract_title(block)
    score, factors = score_profile(profile)
    mouth = validate_mouth(mouth)
    return GOCaseCard(
        case_id=make_case_id(title, profile.primitive),
        title=title,
        primitive=profile.primitive,
        source_urls=extract_urls(block),
        economic_loop=profile.economic_loop,
        dharma_mapping=list(profile.dharma_mapping),
        first_experiment=profile.first_experiment,
        risk=risk_for_profile(profile, block),
        score=score,
        factor_scores=factors,
        source_sha256=hashlib.sha256(block.encode("utf-8")).hexdigest(),
        source_excerpt=block[:1000],
        created_at=(now or datetime.now(timezone.utc)).isoformat(),
        mouth=mouth,
    )


def cards_from_text(
    text: str,
    *,
    now: datetime | None = None,
    mouth: str = DEFAULT_MOUTH,
) -> list[GOCaseCard]:
    return [
        case_card_from_block(block, now=now, mouth=mouth)
        for block in split_case_blocks(text)
    ]


def opportunity_from_card(card: GOCaseCard) -> dict[str, Any]:
    evidence_signals = [
        f"go_case:{card.case_id}",
        f"primitive:{card.primitive}",
        f"risk:{card.risk}",
    ]
    evidence_signals.extend(card.source_urls)
    return {
        "opportunity_id": f"{card.case_id}-experiment",
        "title": f"GO: {card.title}",
        "domain": _domain_from_card(card),
        "thesis": card.first_experiment,
        "final_score": round(card.score * 100, 2),
        "why_now": (
            "External autonomous-economy primitives are maturing; dharma_swarm "
            "can safely ingest and simulate them before any fund-moving action."
        ),
        "factor_scores": card.factor_scores,
        "evidence_signals": evidence_signals,
        "source_inputs": [
            {
                "source": "go_intake",
                "evidence_ref": card.case_id,
                "primitive": card.primitive,
            }
        ],
        "metadata": {
            "bounded_context": BOUNDED_CONTEXT,
            "capability_boundary": CAPABILITY_BOUNDARY,
            "mouth": card.mouth,
            "allowed_next_step": "proposal_only",
            "requires_operator_approval": True,
            "forbidden_actions": [
                "fund_movement",
                "trade_execution",
                "token_launch",
                "outbound_outreach",
                "compute_rental",
                "task_dispatch",
            ],
            "seed_kind": "go_economic_primitive",
            "case_id": card.case_id,
            "primitive": card.primitive,
            "dharma_mapping": card.dharma_mapping,
            "hitl_required": card.hitl_required,
            "no_fund_movement": card.no_fund_movement,
            "risk": card.risk,
        },
    }


def _domain_from_card(card: GOCaseCard) -> str:
    if card.risk == "high":
        return "risk_research"
    profile = next((p for p in PROFILES if p.primitive == card.primitive), FALLBACK_PROFILE)
    return profile.domain


def load_opportunity_board(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8") or "[]")
    if not isinstance(raw, list):
        raise ValueError(f"opportunity board must contain a list: {path}")
    return [row for row in raw if isinstance(row, dict)]


def upsert_opportunity_rows(
    board: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {
        str(row.get("opportunity_id") or ""): row
        for row in board
        if row.get("opportunity_id")
    }
    order = [str(row.get("opportunity_id") or "") for row in board if row.get("opportunity_id")]
    for row in rows:
        opp_id = str(row.get("opportunity_id") or "")
        if not opp_id:
            continue
        if opp_id not in by_id:
            order.append(opp_id)
        by_id[opp_id] = row
    return [by_id[opp_id] for opp_id in order if opp_id in by_id]


def write_case_cards(path: Path, cards: list[GOCaseCard]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for card in cards:
            handle.write(json.dumps(card.to_json(), sort_keys=True) + "\n")


def write_opportunity_board(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ingest_go_text(
    text: str,
    *,
    case_jsonl: Path = DEFAULT_CASE_JSONL,
    opportunity_board: Path = DEFAULT_OPPORTUNITY_BOARD,
    emit_opportunities: bool = False,
    min_score: float = 0.58,
    dry_run: bool = True,
    now: datetime | None = None,
    mouth: str = DEFAULT_MOUTH,
) -> GOIntakeResult:
    mouth = validate_mouth(mouth)
    cards = cards_from_text(text, now=now, mouth=mouth)
    opportunity_rows = [
        opportunity_from_card(card)
        for card in cards
        if card.score >= min_score and card.risk != "high"
    ]
    if not dry_run:
        write_case_cards(case_jsonl, cards)
        if emit_opportunities:
            existing = load_opportunity_board(opportunity_board)
            write_opportunity_board(
                opportunity_board,
                upsert_opportunity_rows(existing, opportunity_rows),
            )
    return GOIntakeResult(
        cards=cards,
        opportunity_rows=opportunity_rows,
        case_jsonl=str(case_jsonl),
        opportunity_board=str(opportunity_board),
        dry_run=dry_run,
        mouth=mouth,
    )


def _read_input(path: Path | None, text: str | None) -> str:
    parts: list[str] = []
    if path is not None:
        parts.append(path.expanduser().read_text(encoding="utf-8"))
    if text:
        parts.append(text)
    payload = "\n\n".join(parts).strip()
    if not payload:
        raise ValueError("provide an input file or --text")
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest external economic primitives into GO case cards.",
    )
    parser.add_argument("input", nargs="?", type=Path)
    parser.add_argument("--text")
    parser.add_argument("--case-jsonl", type=Path, default=DEFAULT_CASE_JSONL)
    parser.add_argument("--opportunity-board", type=Path, default=DEFAULT_OPPORTUNITY_BOARD)
    parser.add_argument("--emit-opportunities", action="store_true")
    parser.add_argument(
        "--mouth",
        default=DEFAULT_MOUTH,
        choices=sorted(ALLOWED_MOUTHS),
        help="Ingestion adapter/source mouth. Does not change GO authority.",
    )
    parser.add_argument("--min-score", type=float, default=0.58)
    parser.add_argument("--write", action="store_true", help="Write case cards and optional opportunities.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = ingest_go_text(
        _read_input(args.input, args.text),
        case_jsonl=args.case_jsonl,
        opportunity_board=args.opportunity_board,
        emit_opportunities=args.emit_opportunities,
        min_score=args.min_score,
        dry_run=not args.write,
        mouth=args.mouth,
    )
    print(json.dumps(result.to_json(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
