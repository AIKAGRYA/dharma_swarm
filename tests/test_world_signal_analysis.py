from __future__ import annotations

from pathlib import Path

from dharma_swarm.world_radar.analysis import (
    build_world_signal_board,
    load_source_feedback_ledger,
    load_source_weights,
    promotion_ready_signals,
    save_source_feedback_ledger,
    save_source_weights,
    update_source_weights_from_opportunities,
)


def test_two_independent_public_sources_promote() -> None:
    board = build_world_signal_board(
        [
            _row("hn-1", "hacker_news", score=0.82),
            _row("gh-1", "github", score=0.78),
        ],
        now="2026-05-13T00:00:00Z",
    )

    movement = board["movements"][0]
    assert movement["status"] == "promotion_ready"
    assert movement["independent_sources"] == 2
    assert movement["triage"]["decision"] == "promote"
    assert set(movement["triage_tuple"]) == {"novelty", "telos_fit", "tractability", "source_confidence"}
    promoted = promotion_ready_signals(board)[0]
    assert promoted["source"] == "world_zeitgeist"
    assert promoted["metadata"]["triage_tuple"]["telos_fit"] >= 0.45


def test_operator_drop_with_url_promotes() -> None:
    board = build_world_signal_board([_row("op-1", "operator_drop", score=0.72)])

    assert board["movements"][0]["status"] == "promotion_ready"
    assert board["movements"][0]["promotion_reason"] == (
        "triage passed with operator drop and concrete evidence URL/source"
    )


def test_single_public_source_incubates_not_promotes() -> None:
    board = build_world_signal_board([_row("hn-1", "hacker_news", score=0.72)])

    movement = board["movements"][0]
    assert movement["status"] == "incubating"
    assert movement["cascade_queries"]
    assert movement["triage_tuple"]["source_confidence"] >= 0.55
    assert not promotion_ready_signals(board)


def test_low_telos_signal_is_rejected_even_with_source_count() -> None:
    rows = [
        _row("hn-coupon", "hacker_news", score=0.88),
        _row("gh-coupon", "github", score=0.86),
    ]
    for row in rows:
        row["title"] = "Casino coupon promo"
        row["description"] = "Gambling coupon spam with no governed agent or research value."
        row["keywords"] = ["casino", "coupon", "promo"]
        row["metadata"] = {"movement_key": "casino coupon promo"}

    board = build_world_signal_board(rows)

    movement = board["movements"][0]
    assert movement["status"] == "rejected"
    assert movement["triage"]["decision"] == "reject"
    assert "reject_keyword_match" in movement["triage"]["reasons"]
    assert board["health"]["rejected"] == 1
    assert not promotion_ready_signals(board)


def test_operator_drop_without_evidence_incubates_as_insufficient_evidence() -> None:
    row = _row("op-no-url", "operator_drop", score=0.92)
    row["url"] = ""

    board = build_world_signal_board([row])

    movement = board["movements"][0]
    assert movement["status"] == "incubating"
    assert movement["triage"]["decision"] == "insufficient_evidence"
    assert movement["promotion_reason"] == "triage needs more concrete source evidence"
    assert not promotion_ready_signals(board)


def test_source_weights_roundtrip_and_feedback(tmp_path: Path) -> None:
    path = tmp_path / "source_weights.json"
    save_source_weights(path, {"github": 0.9})

    weights = load_source_weights(path)
    updated = update_source_weights_from_opportunities(
        weights,
        [
            {
                "source_inputs": [{"raw_source": "github"}],
                "realized_outcomes": [{"success": True}],
            },
            {
                "source_inputs": [{"raw_source": "reddit"}],
                "realized_outcomes": [{"success": False}],
            },
        ],
    )

    assert updated["github"] > weights["github"]
    assert updated["reddit"] < weights["reddit"]


def test_source_weights_do_not_decay_for_pending_rows() -> None:
    updated = update_source_weights_from_opportunities(
        {"github": 0.86},
        [{"source_inputs": [{"raw_source": "github"}]}],
    )

    assert updated["github"] == 0.86


def test_source_weight_feedback_is_event_idempotent(tmp_path: Path) -> None:
    ledger_path = tmp_path / "source_feedback_ledger.json"
    applied = load_source_feedback_ledger(ledger_path)
    rows = [
        {
            "opportunity_id": "opp-world",
            "source_inputs": [{"raw_source": "github"}],
            "realized_outcomes": [{"outcome_id": "outcome-1", "success": True}],
        }
    ]

    first = update_source_weights_from_opportunities(
        {"github": 0.86},
        rows,
        applied_event_ids=applied,
    )
    save_source_feedback_ledger(ledger_path, applied)
    second = update_source_weights_from_opportunities(
        first,
        rows,
        applied_event_ids=load_source_feedback_ledger(ledger_path),
    )

    assert first["github"] == 0.89
    assert second["github"] == first["github"]


def _row(row_id: str, source: str, *, score: float) -> dict[str, object]:
    return {
        "id": row_id,
        "source": source,
        "source_type": source,
        "category": "company",
        "title": "SubQ managed agent runtime",
        "description": "A public signal about managed agent execution infrastructure.",
        "relevance_score": score,
        "keywords": ["agentic", "runtime"],
        "url": f"https://example.com/{row_id}",
        "metadata": {"movement_key": "subq managed agent runtime"},
    }
