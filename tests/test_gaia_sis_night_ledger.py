"""Behavioral tests for the SIS night ledger (windowing, mapping, honesty).

Claim boundary: these prove window admission, meta.json→receipt mapping, band
presence, and honest degradation on junk/empty input. They do NOT validate the
energy numbers themselves — those are rebuttable seed estimates by design.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dharma_swarm.gaia_sis_night_ledger import (
    NightWindow,
    gather_night,
    night_ledger_markdown,
)

NOW = datetime(2026, 9, 2, 2, 0, tzinfo=timezone.utc)
WINDOW = NightWindow(since=NOW - timedelta(hours=8), until=NOW)


def _write_session(root: Path, name: str, **overrides) -> Path:
    meta = {
        "schema_version": 1,
        "session_id": name,
        "created_at": (NOW - timedelta(hours=1)).isoformat(),
        "updated_at": (NOW - timedelta(hours=1)).isoformat(),
        "provider_id": "claude",
        "model_id": "claude-sonnet-5",
        "total_cost_usd": 0.07,
        "total_input_tokens": 900,
        "total_output_tokens": 300,
        "status": "completed",
    }
    meta.update(overrides)
    session_dir = root / name
    session_dir.mkdir(parents=True)
    (session_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return session_dir


def test_window_admission_is_half_open_and_filters(tmp_path: Path) -> None:
    _write_session(tmp_path, "in-window")
    _write_session(
        tmp_path, "too-old",
        updated_at=(NOW - timedelta(hours=9)).isoformat(),
    )
    _write_session(tmp_path, "at-until-boundary", updated_at=NOW.isoformat())

    gather = gather_night([tmp_path], WINDOW)

    assert [r["trace_id"] for r in gather.receipts] == ["in-window"]
    assert gather.skipped_outside_window == 2
    assert gather.skipped_unreadable == 0


def test_meta_fields_map_onto_projection_duck_type(tmp_path: Path) -> None:
    _write_session(
        tmp_path, "mapped",
        provider_id="codex", model_id="gpt-5.6-sol",
        total_input_tokens=100, total_output_tokens=50, total_cost_usd=0.5,
    )

    receipt = gather_night([tmp_path], WINDOW).receipts[0]

    assert receipt["provider"] == "codex"
    assert receipt["model"] == "gpt-5.6-sol"
    assert receipt["input_tokens"] == 100
    assert receipt["output_tokens"] == 50
    assert receipt["cost_usd"] == 0.5


def test_ledger_always_carries_the_band_and_provider_rollup(tmp_path: Path) -> None:
    _write_session(tmp_path, "a")
    _write_session(tmp_path, "b", provider_id="codex", model_id="gpt-5.6-sol")

    report = night_ledger_markdown(gather_night([tmp_path], WINDOW), WINDOW, "test")

    assert "gCO2e" in report
    assert "lower" in report and "upper" in report  # never a single number
    assert "claude: 1 session(s)" in report
    assert "codex: 1 session(s)" in report
    assert "USD 0.1400" in report  # recorded cost is summed, labeled recorded
    assert "recorded, not billed-proof" in report


def test_junk_meta_is_skipped_and_counted_not_fatal(tmp_path: Path) -> None:
    _write_session(tmp_path, "good")
    bad = tmp_path / "corrupt"
    bad.mkdir()
    (bad / "meta.json").write_text("{not json", encoding="utf-8")
    no_ts = tmp_path / "no-timestamps"
    no_ts.mkdir()
    (no_ts / "meta.json").write_text(
        json.dumps({"provider_id": "claude"}), encoding="utf-8"
    )

    gather = gather_night([tmp_path], WINDOW)

    assert len(gather.receipts) == 1
    assert gather.skipped_unreadable == 2


def test_zero_token_sessions_reported_as_unmetered_not_zero_proof(tmp_path: Path) -> None:
    _write_session(
        tmp_path, "unmetered",
        total_input_tokens=0, total_output_tokens=0,
    )

    gather = gather_night([tmp_path], WINDOW)
    report = night_ledger_markdown(gather, WINDOW, "test")

    assert len(gather.unmetered) == 1
    assert "stored zeros are not promoted as proof of zero usage" in report


def test_empty_window_states_absence_is_not_zero_compute(tmp_path: Path) -> None:
    report = night_ledger_markdown(gather_night([tmp_path], WINDOW), WINDOW, "empty")

    assert "No metered session receipts" in report
    assert "not proof of zero compute" in report


def test_missing_root_is_tolerated(tmp_path: Path) -> None:
    gather = gather_night([tmp_path / "does-not-exist"], WINDOW)

    assert gather.receipts == ()
    assert gather.skipped_unreadable == 0
