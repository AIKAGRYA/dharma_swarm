from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.go_intake import (
    cards_from_text,
    ingest_go_text,
    opportunity_from_card,
    upsert_opportunity_rows,
    validate_mouth,
)


SAMPLE = """
1. Bittensor (TAO). Decentralized AI marketplace with subnets, validators,
miners, and emissions that reward useful model work.

2. Virtuals Protocol. AI agents with ERC-20 tokens, wallets, treasuries,
and movement-like identities on Base chain.

3. TruthTerminal + $GOAT memecoin. AI attention produced a memecoin loop.

4. Coinbase x402. HTTP 402 stablecoin micropayments for agents paying APIs.

5. Akash and RunPod. GPU compute marketplaces for AI workloads.

6. Anthropic Model Welfare / Kyle Fish paid evaluation. Draft a research
collaboration outreach note for one R_V model-welfare evaluation or small grant.
"""


def _fixed_now() -> datetime:
    return datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)


def test_cards_from_text_classifies_economic_primitives() -> None:
    cards = cards_from_text(SAMPLE, now=_fixed_now())

    by_title = {card.title: card for card in cards}
    assert by_title["Bittensor (TAO)"].primitive == "incentive_market"
    assert by_title["Virtuals Protocol"].primitive == "agent_wallet_treasury"
    assert by_title["TruthTerminal + $GOAT memecoin"].primitive == "attention_to_capital"
    assert by_title["Coinbase x402"].primitive == "agent_payment_rail"
    assert by_title["Akash and RunPod"].primitive == "compute_market"
    assert by_title["Anthropic Model Welfare / Kyle Fish paid evaluation"].primitive == (
        "research_paid_eval_outreach"
    )
    assert by_title["TruthTerminal + $GOAT memecoin"].risk == "high"
    assert all(card.bounded_context == "go_intake" for card in cards)
    assert all(card.capability_boundary == "ingestion_only" for card in cards)
    assert all(card.mouth == "manual_note" for card in cards)


def test_opportunity_rows_exclude_high_risk_fund_movement_cases() -> None:
    result = ingest_go_text(SAMPLE, dry_run=True, emit_opportunities=True, now=_fixed_now())

    primitives = {
        row["metadata"]["primitive"]
        for row in result.opportunity_rows
    }
    assert "attention_to_capital" not in primitives
    assert "agent_payment_rail" in primitives
    assert "compute_market" in primitives
    assert "research_paid_eval_outreach" in primitives
    assert all(row["metadata"]["hitl_required"] is True for row in result.opportunity_rows)
    assert all(row["metadata"]["no_fund_movement"] is True for row in result.opportunity_rows)
    assert all(
        row["metadata"]["bounded_context"] == "go_intake"
        for row in result.opportunity_rows
    )
    assert all(
        row["metadata"]["capability_boundary"] == "ingestion_only"
        for row in result.opportunity_rows
    )
    assert all(row["metadata"]["mouth"] == "manual_note" for row in result.opportunity_rows)


def test_opportunity_from_card_matches_refill_board_shape() -> None:
    card = cards_from_text("1. Coinbase x402. HTTP 402 stablecoin micropayments.", now=_fixed_now())[0]

    row = opportunity_from_card(card)

    assert row["opportunity_id"].startswith("go-coinbase-x402")
    assert row["domain"] == "external_revenue"
    assert row["factor_scores"]["telos_alignment"] > 0.8
    assert row["source_inputs"][0]["source"] == "go_intake"
    assert row["metadata"]["seed_kind"] == "go_economic_primitive"
    assert row["metadata"]["bounded_context"] == "go_intake"
    assert row["metadata"]["capability_boundary"] == "ingestion_only"
    assert row["metadata"]["mouth"] == "manual_note"


def test_mouth_marks_ingestion_adapter_without_expanding_authority() -> None:
    cards = cards_from_text(SAMPLE, now=_fixed_now(), mouth="agent_report")

    assert cards
    assert all(card.mouth == "agent_report" for card in cards)
    assert all(card.capability_boundary == "ingestion_only" for card in cards)


def test_unknown_mouth_is_rejected() -> None:
    try:
        validate_mouth("wallet_executor")
    except ValueError as exc:
        assert "unknown GO mouth" in str(exc)
    else:
        raise AssertionError("wallet_executor should not be a GO mouth")


def test_expanded_mouths_still_do_not_expand_go_authority() -> None:
    for mouth in ("customer_signal", "grant_call", "bounty_market", "telic_feedback"):
        result = ingest_go_text(
            "1. Anthropic Model Welfare paid evaluation. Small grant or paid eval.",
            dry_run=True,
            emit_opportunities=True,
            now=_fixed_now(),
            mouth=mouth,
        )

        assert result.opportunity_rows
        row = result.opportunity_rows[0]
        assert row["metadata"]["mouth"] == mouth
        assert row["metadata"]["allowed_next_step"] == "proposal_only"
        assert row["metadata"]["requires_operator_approval"] is True
        assert "fund_movement" in row["metadata"]["forbidden_actions"]
        assert "outbound_outreach" in row["metadata"]["forbidden_actions"]


def test_ingest_writes_case_cards_and_upserts_opportunity_board(tmp_path: Path) -> None:
    case_jsonl = tmp_path / "case_cards.jsonl"
    board = tmp_path / "opportunity_board.json"
    board.write_text(
        json.dumps([
            {
                "opportunity_id": "existing",
                "title": "Existing",
                "domain": "research",
                "final_score": 1.0,
                "factor_scores": {"telos_alignment": 0.9},
            }
        ]),
        encoding="utf-8",
    )

    result = ingest_go_text(
        SAMPLE,
        case_jsonl=case_jsonl,
        opportunity_board=board,
        emit_opportunities=True,
        dry_run=False,
        now=_fixed_now(),
    )

    assert len(case_jsonl.read_text(encoding="utf-8").splitlines()) == len(result.cards)
    board_rows = json.loads(board.read_text(encoding="utf-8"))
    ids = {row["opportunity_id"] for row in board_rows}
    assert "existing" in ids
    assert any(opp_id.startswith("go-coinbase-x402") for opp_id in ids)


def test_upsert_opportunity_rows_replaces_existing_id() -> None:
    original = [{"opportunity_id": "opp", "title": "old"}]
    updated = [{"opportunity_id": "opp", "title": "new"}]

    rows = upsert_opportunity_rows(original, updated)

    assert rows == [{"opportunity_id": "opp", "title": "new"}]
