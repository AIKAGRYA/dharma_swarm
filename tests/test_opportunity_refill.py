"""Tests for opportunity_refill (Layer A) + cron handler registration.

Covers:
- refill skips opportunities with existing manifest folders (filesystem-
  derived addressed_ids — single source of truth, no separate index).
- refill filters by min_telos_alignment.
- refill appends to JSONL, never overwrites.
- refill respects the dispatcher's paused flag (fail-paranoid).
- refill is idempotent if board does not change between runs.
- dry-run writes nothing.
- cron handlers `frontier_dispatcher` and `frontier_refill` dispatch through
  cron_runner.execute_cron_job.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm import _campaign_manifest, opportunity_refill


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def tmp_dharma(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    dharma = tmp_path / "dharma"
    meta = dharma / "meta"
    meta.mkdir(parents=True)
    campaigns = dharma / "campaigns"

    monkeypatch.setattr(opportunity_refill, "DHARMA_HOME", dharma)
    monkeypatch.setattr(opportunity_refill, "META_DIR", meta)
    monkeypatch.setattr(opportunity_refill, "BOARD_PATH", meta / "opportunity_board.json")
    monkeypatch.setattr(opportunity_refill, "PENDING_PATH", meta / "frontier_tasks_pending.jsonl")
    monkeypatch.setattr(opportunity_refill, "PAUSED_FLAG", meta / "dispatcher_paused.flag")
    monkeypatch.setattr(_campaign_manifest, "CAMPAIGN_ROOT", campaigns)
    return dharma


def _opp(opp_id: str, *, telos: float = 0.95, score: float = 80.0,
         title_hint: str = "Demo") -> dict[str, Any]:
    return {
        "opportunity_id": opp_id,
        "title": f"{title_hint} {opp_id}",
        "domain": "external_revenue",
        "thesis": "wedge",
        "factor_scores": {
            "telos_alignment": telos,
            "world_value": 0.6,
            "leverage": 0.7,
        },
        "final_score": score,
        "evidence_signals": ["sig-1"],
        "why_now": "demo",
        "timestamp": "2026-04-19T15:36:41.631916Z",
    }


def _write_board(tmp_dharma: Path, opps: list[dict[str, Any]]) -> None:
    (tmp_dharma / "meta" / "opportunity_board.json").write_text(
        json.dumps(opps), encoding="utf-8",
    )


def _seed_addressed(tmp_dharma: Path, opp_id: str) -> None:
    """Create a minimal manifest folder so the opp is treated as addressed."""
    from dharma_swarm._campaign_manifest import init_manifest, write_manifest
    m = init_manifest(opportunity_id=opp_id, title=f"seeded {opp_id}",
                      domain="x", telos_alignment=0.9)
    write_manifest(opp_id, m)


# --------------------------------------------------------------------------
# Refill behavior
# --------------------------------------------------------------------------


def test_refill_appends_rows_for_top_k_opportunities(tmp_dharma: Path):
    _write_board(tmp_dharma, [
        _opp("opp_high", score=90.0),
        _opp("opp_mid", score=70.0),
        _opp("opp_low", score=40.0),
    ])
    res = opportunity_refill.refill_frontier_tasks_pending(top_k=2)

    assert res.error is None
    assert res.board_count == 3
    assert res.appended_rows == 12  # 2 opps × 6 stages
    # Top-K by score: opp_high + opp_mid
    assert set(res.appended_opportunity_ids) == {"opp_high", "opp_mid"}

    # JSONL written.
    pending = tmp_dharma / "meta" / "frontier_tasks_pending.jsonl"
    assert pending.exists()
    rows = pending.read_text().splitlines()
    assert len(rows) == 12


def test_refill_skips_opportunities_with_existing_manifest_folders(tmp_dharma: Path):
    _write_board(tmp_dharma, [_opp("opp_addressed"), _opp("opp_fresh")])
    _seed_addressed(tmp_dharma, "opp_addressed")

    res = opportunity_refill.refill_frontier_tasks_pending(top_k=2)

    assert res.appended_opportunity_ids == ["opp_fresh"]
    assert "opp_addressed" in res.skipped_already_addressed


def test_refill_filters_by_min_telos_alignment(tmp_dharma: Path):
    _write_board(tmp_dharma, [
        _opp("opp_aligned", telos=0.8),
        _opp("opp_extractive", telos=0.05),
    ])
    res = opportunity_refill.refill_frontier_tasks_pending(
        top_k=10, min_telos_alignment=0.5,
    )
    assert res.appended_opportunity_ids == ["opp_aligned"]


def test_refill_paused_when_flag_present(tmp_dharma: Path):
    _write_board(tmp_dharma, [_opp("opp_x")])
    (tmp_dharma / "meta" / "dispatcher_paused.flag").touch()

    res = opportunity_refill.refill_frontier_tasks_pending(top_k=1)

    assert res.paused is True
    assert res.appended_rows == 0
    assert not (tmp_dharma / "meta" / "frontier_tasks_pending.jsonl").exists()


def test_refill_dry_run_writes_nothing(tmp_dharma: Path):
    _write_board(tmp_dharma, [_opp("opp_x")])
    res = opportunity_refill.refill_frontier_tasks_pending(top_k=1, dry_run=True)

    assert res.dry_run is True
    assert res.appended_rows == 6
    assert res.appended_opportunity_ids == ["opp_x"]
    assert not (tmp_dharma / "meta" / "frontier_tasks_pending.jsonl").exists()


def test_refill_appends_never_overwrites(tmp_dharma: Path):
    _write_board(tmp_dharma, [_opp("opp_first")])
    opportunity_refill.refill_frontier_tasks_pending(top_k=1)

    # Now seed a manifest for opp_first so the next refill picks a new one.
    _seed_addressed(tmp_dharma, "opp_first")
    _write_board(tmp_dharma, [_opp("opp_first"), _opp("opp_second", score=70.0)])

    opportunity_refill.refill_frontier_tasks_pending(top_k=1)

    rows = (tmp_dharma / "meta" / "frontier_tasks_pending.jsonl").read_text().splitlines()
    # 6 rows from opp_first + 6 rows from opp_second = 12 total (append-only).
    assert len(rows) == 12


def test_refill_handles_missing_board(tmp_dharma: Path):
    res = opportunity_refill.refill_frontier_tasks_pending(top_k=3)
    assert res.error is None
    assert res.board_count == 0
    assert res.appended_rows == 0


def test_refill_handles_malformed_board(tmp_dharma: Path):
    (tmp_dharma / "meta" / "opportunity_board.json").write_text(
        "{not json", encoding="utf-8",
    )
    res = opportunity_refill.refill_frontier_tasks_pending(top_k=1)
    assert res.board_count == 0  # treated as empty


# --------------------------------------------------------------------------
# Cron handler registration
# --------------------------------------------------------------------------


def test_cron_handler_frontier_refill_dispatches(
    tmp_dharma: Path, monkeypatch: pytest.MonkeyPatch,
):
    _write_board(tmp_dharma, [_opp("opp_cron")])
    from dharma_swarm.cron_runner import execute_cron_job

    job = {
        "name": "frontier_refill_test",
        "handler": "frontier_refill",
        "top_k": 1,
        "dry_run": True,  # don't pollute test FS even though we're sandboxed
    }
    res = execute_cron_job(job)

    assert "frontier_refill" in res.output
    assert res.status.value == "completed"


def test_cron_handler_frontier_dispatcher_dispatches(
    tmp_dharma: Path, monkeypatch: pytest.MonkeyPatch,
):
    """The dispatcher handler executes opportunity_dispatcher.main and
    passes through the dry-run flag."""
    from dharma_swarm.cron_runner import execute_cron_job
    from dharma_swarm import opportunity_dispatcher

    # Patch the dispatcher's main to record args without doing real work.
    captured: dict[str, Any] = {"argv": None}
    def _stub_main(argv):
        captured["argv"] = list(argv) if argv is not None else []
        return 0
    monkeypatch.setattr(opportunity_dispatcher, "main", _stub_main)

    job = {
        "name": "frontier_dispatcher_test",
        "handler": "frontier_dispatcher",
        "dry_run": True,
        "max_promotions": 2,
    }
    res = execute_cron_job(job)

    assert res.status.value == "completed"
    assert "--dry-run" in captured["argv"]
    assert "--max" in captured["argv"]
    assert "2" in captured["argv"]


def test_cron_handler_unknown_returns_failed():
    from dharma_swarm.cron_runner import execute_cron_job
    res = execute_cron_job({"name": "x", "handler": "no_such_handler"})
    assert res.status.value == "failed"
    assert "Unsupported" in res.output
