"""Tests for the rolling-window theme persistence layer."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dharma_swarm.world_radar.theme_window import (
    ThemeWindowEntry,
    load_theme_window,
    run_theme_window_update,
    save_theme_window,
    update_theme_window,
)


def _movement(movement_id: str, title: str, score: float) -> dict[str, object]:
    return {"movement_id": movement_id, "title": title, "weighted_score": score}


def test_new_movement_is_recorded_as_newly_seen() -> None:
    window, newly_seen = update_theme_window({}, [_movement("m1", "Theme One", 0.7)])
    assert "m1" in window
    assert window["m1"].occurrence_count == 1
    assert newly_seen == ("m1",)


def test_recurring_movement_increments_occurrence_and_is_not_newly_seen() -> None:
    window, _ = update_theme_window({}, [_movement("m1", "Theme One", 0.7)])
    window, newly_seen = update_theme_window(window, [_movement("m1", "Theme One", 0.9)])
    assert window["m1"].occurrence_count == 2
    assert window["m1"].best_weighted_score == 0.9  # max across cycles
    assert newly_seen == ()


def test_best_weighted_score_never_decreases() -> None:
    window, _ = update_theme_window({}, [_movement("m1", "Theme One", 0.9)])
    window, _ = update_theme_window(window, [_movement("m1", "Theme One", 0.3)])
    assert window["m1"].best_weighted_score == 0.9


def test_movement_without_id_is_skipped_not_crashed() -> None:
    window, newly_seen = update_theme_window({}, [{"title": "no id here"}])
    assert window == {}
    assert newly_seen == ()


def test_malformed_weighted_score_defaults_to_zero_not_crash() -> None:
    window, newly_seen = update_theme_window(
        {},
        [{"movement_id": "m1", "title": "bad score", "weighted_score": "not-a-number"}],
    )

    assert newly_seen == ("m1",)
    assert window["m1"].best_weighted_score == 0.0


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    window, _ = update_theme_window({}, [_movement("m1", "Theme One", 0.7)])
    path = tmp_path / "theme_window.json"
    save_theme_window(path, window)
    reloaded = load_theme_window(path)
    assert reloaded["m1"].movement_id == "m1"
    assert reloaded["m1"].occurrence_count == 1


def test_load_missing_file_is_empty(tmp_path: Path) -> None:
    assert load_theme_window(tmp_path / "nope.json") == {}


def test_load_garbled_file_is_empty_not_a_crash(tmp_path: Path) -> None:
    path = tmp_path / "theme_window.json"
    path.write_text("not json at all {{{", encoding="utf-8")
    assert load_theme_window(path) == {}


def test_run_theme_window_update_end_to_end(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    meta.mkdir(parents=True)
    board = {
        "movements": [
            {"movement_id": "m1", "title": "Theme One", "weighted_score": 0.8},
            {"movement_id": "m2", "title": "Theme Two", "weighted_score": 0.6},
        ]
    }
    (meta / "world_signal_board.json").write_text(json.dumps(board), encoding="utf-8")

    summary = run_theme_window_update(tmp_path)
    assert summary["total_tracked_themes"] == 2
    assert summary["newly_seen_count"] == 2

    # Second cycle: m1 recurs, m3 is new.
    board2 = {
        "movements": [
            {"movement_id": "m1", "title": "Theme One", "weighted_score": 0.85},
            {"movement_id": "m3", "title": "Theme Three", "weighted_score": 0.5},
        ]
    }
    (meta / "world_signal_board.json").write_text(json.dumps(board2), encoding="utf-8")
    summary2 = run_theme_window_update(tmp_path)
    assert summary2["total_tracked_themes"] == 3  # m1, m2 (persisted), m3
    assert summary2["newly_seen_count"] == 1
    assert summary2["newly_seen_movement_ids"] == ["m3"]


def test_run_theme_window_update_resolves_state_dir(tmp_path: Path) -> None:
    # Copilot review finding: state_dir must be canonicalized ('..' segments
    # resolved), matching deep_sweep/zeitgeist_promotion's write-site handling
    # of the same kind of write-driving state dir.
    aliased_state = tmp_path / "nested" / ".."
    summary = run_theme_window_update(aliased_state)
    window_path = Path(summary["window_path"])
    assert window_path.is_relative_to(tmp_path.resolve() / "meta")
    assert ".." not in window_path.parts


def test_run_theme_window_update_missing_board_is_defensive(tmp_path: Path) -> None:
    summary = run_theme_window_update(tmp_path)
    assert summary["movements_this_cycle"] == 0
    assert summary["total_tracked_themes"] == 0


def test_stale_entry_is_pruned_not_accumulated_forever() -> None:
    # Copilot review finding: the module is named a "rolling window" but
    # never evicted anything, so it would grow unbounded forever. An entry
    # not seen again within max_age_days must be pruned on the next update.
    stale_entry = ThemeWindowEntry(
        movement_id="stale-1",
        title="Old Theme",
        first_seen_at=(datetime.now(timezone.utc) - timedelta(days=200)).isoformat(),
        last_seen_at=(datetime.now(timezone.utc) - timedelta(days=200)).isoformat(),
        occurrence_count=1,
        best_weighted_score=0.5,
    )
    window = {"stale-1": stale_entry}
    updated, newly_seen = update_theme_window(window, [_movement("m1", "Fresh Theme", 0.7)])
    assert "stale-1" not in updated
    assert "m1" in updated
    assert newly_seen == ("m1",)


def test_recent_entry_survives_pruning() -> None:
    recent_entry = ThemeWindowEntry(
        movement_id="recent-1",
        title="Recent Theme",
        first_seen_at=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        last_seen_at=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        occurrence_count=3,
        best_weighted_score=0.5,
    )
    window = {"recent-1": recent_entry}
    updated, _ = update_theme_window(window, [])
    assert "recent-1" in updated


def test_garbled_last_seen_at_is_pruned_not_crashed() -> None:
    garbled = ThemeWindowEntry(
        movement_id="garbled-1",
        title="Garbled",
        first_seen_at="not-a-timestamp",
        last_seen_at="not-a-timestamp",
        occurrence_count=1,
        best_weighted_score=0.5,
    )
    updated, _ = update_theme_window({"garbled-1": garbled}, [])
    assert "garbled-1" not in updated


def test_custom_max_age_days_is_honored() -> None:
    entry = ThemeWindowEntry(
        movement_id="m1",
        title="Theme",
        first_seen_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        last_seen_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        occurrence_count=1,
        best_weighted_score=0.5,
    )
    updated, _ = update_theme_window({"m1": entry}, [], max_age_days=1)
    assert "m1" not in updated
