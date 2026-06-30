"""Tests for the telos objective lifecycle (Stream D).

Covers:
- ObjectiveStatus enum gains terminal states DONE / ABANDONED / SUPERSEDED.
- ``telos_sweep`` promotes progress>=1.0 → done, stale>60d & <1.0 → abandoned,
  leaves active/proposed and blocked untouched.
- ``_telos_summary`` surfaces done / abandoned / superseded / blocked counts.

Self-contained fixtures — does NOT touch tests/conftest.py.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import dharma_swarm.swarm_health_api as health_api
from dharma_swarm.telos_graph import (
    ObjectiveStatus,
    TERMINAL_STATUSES,
    TelosGraph,
)
from dharma_swarm.telos_substrate import telos_sweep, _sweep_classify


# ---------------------------------------------------------------------------
# Fixtures (local — do not touch tests/conftest.py)
# ---------------------------------------------------------------------------


def _compact(row: dict) -> str:
    """Compact JSON matching the on-disk objectives.jsonl format."""
    return json.dumps(row, separators=(",", ":"))


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    """Point swarm_health_api._STATE_DIR at a tmp_path."""
    monkeypatch.setattr(health_api, "_STATE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def telos_dir(state_dir):
    d = state_dir / "telos"
    d.mkdir()
    return d


def _make_row(
    *,
    id: str,
    name: str,
    status: str = "active",
    progress: float = 0.0,
    updated_at: str | None = None,
    priority: int = 5,
) -> dict:
    if updated_at is None:
        updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "id": id,
        "name": name,
        "description": "",
        "perspective": "process",
        "status": status,
        "progress": progress,
        "owner": "",
        "priority": priority,
        "target_date": None,
        "parent_id": None,
        "created_at": updated_at,
        "updated_at": updated_at,
        "metadata": {},
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(_compact(r) for r in rows) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


_NOW = datetime(2026, 6, 29, tzinfo=timezone.utc)
_RECENT = _NOW - timedelta(days=5)
_OLD = _NOW - timedelta(days=90)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# ObjectiveStatus enum
# ---------------------------------------------------------------------------


class TestObjectiveStatusEnum:
    def test_terminal_states_exist(self):
        assert ObjectiveStatus.DONE.value == "done"
        assert ObjectiveStatus.ABANDONED.value == "abandoned"
        assert ObjectiveStatus.SUPERSEDED.value == "superseded"

    def test_active_and_blocked_preserved(self):
        assert ObjectiveStatus.ACTIVE.value == "active"
        assert ObjectiveStatus.BLOCKED.value == "blocked"

    def test_terminal_set_contains_new_states(self):
        assert ObjectiveStatus.DONE in TERMINAL_STATUSES
        assert ObjectiveStatus.ABANDONED in TERMINAL_STATUSES
        assert ObjectiveStatus.SUPERSEDED in TERMINAL_STATUSES

    def test_active_not_terminal(self):
        assert ObjectiveStatus.ACTIVE not in TERMINAL_STATUSES
        assert ObjectiveStatus.BLOCKED not in TERMINAL_STATUSES


# ---------------------------------------------------------------------------
# telos_sweep
# ---------------------------------------------------------------------------


class TestTelosSweep:
    def test_progress_complete_becomes_done(self, telos_dir):
        path = telos_dir / "objectives.jsonl"
        rows = [
            _make_row(id="done-1", name="Finished A", progress=1.0,
                      updated_at=_iso(_RECENT)),
            _make_row(id="active-1", name="In flight B", progress=0.4,
                      updated_at=_iso(_RECENT)),
        ]
        _write_jsonl(path, rows)

        report = telos_sweep(path, dry_run=False, now=_NOW)

        assert report["written"] is True
        assert len(report["done"]) == 1
        assert report["done"][0][0] == "done-1"
        assert len(report["abandoned"]) == 0
        assert report["unchanged"] == 1

        written = _read_jsonl(path)
        assert written[0]["status"] == "done"
        assert written[1]["status"] == "active"

    def test_stale_below_complete_becomes_abandoned(self, telos_dir):
        path = telos_dir / "objectives.jsonl"
        rows = [
            _make_row(id="stale-1", name="Stale C", progress=0.3,
                      updated_at=_iso(_OLD)),
            _make_row(id="fresh-1", name="Fresh D", progress=0.2,
                      updated_at=_iso(_RECENT)),
        ]
        _write_jsonl(path, rows)

        report = telos_sweep(path, dry_run=False, now=_NOW)

        assert len(report["abandoned"]) == 1
        assert report["abandoned"][0][0] == "stale-1"
        assert report["unchanged"] == 1

        written = _read_jsonl(path)
        assert written[0]["status"] == "abandoned"
        assert written[1]["status"] == "active"

    def test_blocked_never_touched(self, telos_dir):
        path = telos_dir / "objectives.jsonl"
        # blocked with progress=1.0 AND blocked stale — must NOT transition.
        rows = [
            _make_row(id="blk-1", name="Blocked done", status="blocked",
                      progress=1.0, updated_at=_iso(_OLD)),
            _make_row(id="blk-2", name="Blocked stale", status="blocked",
                      progress=0.1, updated_at=_iso(_OLD)),
        ]
        _write_jsonl(path, rows)

        report = telos_sweep(path, dry_run=False, now=_NOW)

        assert report["blocked_untouched"] == 2
        assert len(report["done"]) == 0
        assert len(report["abandoned"]) == 0
        assert report["written"] is False  # no modifications → no write

        # File byte-identical
        written = _read_jsonl(path)
        assert written[0]["status"] == "blocked"
        assert written[1]["status"] == "blocked"

    def test_dry_run_writes_nothing(self, telos_dir):
        path = telos_dir / "objectives.jsonl"
        rows = [
            _make_row(id="done-1", name="Finished A", progress=1.0,
                      updated_at=_iso(_RECENT)),
            _make_row(id="stale-1", name="Stale C", progress=0.3,
                      updated_at=_iso(_OLD)),
        ]
        _write_jsonl(path, rows)
        before = path.read_bytes()

        report = telos_sweep(path, dry_run=True, now=_NOW)

        assert report["written"] is False
        assert len(report["done"]) == 1
        assert len(report["abandoned"]) == 1
        assert path.read_bytes() == before  # byte-identical

    def test_stash_backup_creates_copy(self, telos_dir):
        path = telos_dir / "objectives.jsonl"
        rows = [
            _make_row(id="done-1", name="Finished A", progress=1.0,
                      updated_at=_iso(_RECENT)),
        ]
        _write_jsonl(path, rows)

        report = telos_sweep(path, dry_run=False, stash_backup=True, now=_NOW)

        assert report["written"] is True
        assert report["backup_path"] is not None
        backup = Path(report["backup_path"])
        assert backup.exists()
        # Backup still has the old status
        backup_rows = _read_jsonl(backup)
        assert backup_rows[0]["status"] == "active"

    def test_no_transitions_leaves_file_untouched(self, telos_dir):
        path = telos_dir / "objectives.jsonl"
        rows = [
            _make_row(id="active-1", name="In flight B", progress=0.4,
                      updated_at=_iso(_RECENT)),
        ]
        _write_jsonl(path, rows)
        before = path.read_bytes()

        report = telos_sweep(path, dry_run=False, now=_NOW)

        assert report["written"] is False
        assert path.read_bytes() == before

    def test_classify_helper(self):
        now = _NOW
        assert _sweep_classify({"status": "active", "progress": 1.0}, now) == ("done", "progress>=1.0")
        assert _sweep_classify({"status": "active", "progress": 0.2,
                                "updated_at": _iso(_OLD)}, now)[0] == "abandoned"
        assert _sweep_classify({"status": "active", "progress": 0.2,
                                "updated_at": _iso(_RECENT)}, now)[0] == "active"
        assert _sweep_classify({"status": "blocked", "progress": 1.0}, now) == ("blocked", "untouched (blocked)")
        # already-terminal record is left alone
        assert _sweep_classify({"status": "done", "progress": 1.0}, now)[0] == "done"

    def test_compact_format_preserved(self, telos_dir):
        """Sweep output must keep the compact (no-space) JSON separators."""
        path = telos_dir / "objectives.jsonl"
        rows = [
            _make_row(id="done-1", name="Finished A", progress=1.0,
                      updated_at=_iso(_RECENT)),
        ]
        _write_jsonl(path, rows)

        telos_sweep(path, dry_run=False, now=_NOW)

        text = path.read_text(encoding="utf-8")
        # Compact separators: `":"` and `","` not `": "` and `", "`
        assert '":' in text
        assert '","' in text
        assert '"status":"done"' in text


# ---------------------------------------------------------------------------
# _telos_summary surfaces terminal counts
# ---------------------------------------------------------------------------


class TestTelosSummaryTerminalCounts:
    def _write(self, telos_dir, rows):
        _write_jsonl(telos_dir / "objectives.jsonl", rows)

    def test_includes_terminal_keys(self, telos_dir):
        rows = [
            _make_row(id="a", name="A", status="active", progress=0.5, priority=9,
                      updated_at=_iso(_RECENT)),
            _make_row(id="b", name="B", status="done", progress=1.0, priority=8,
                      updated_at=_iso(_RECENT)),
            _make_row(id="c", name="C", status="abandoned", progress=0.1,
                      updated_at=_iso(_OLD)),
            _make_row(id="d", name="D", status="superseded", progress=0.0,
                      updated_at=_iso(_RECENT)),
            _make_row(id="e", name="E", status="blocked", progress=0.0,
                      updated_at=_iso(_RECENT)),
        ]
        self._write(telos_dir, rows)

        result = health_api._telos_summary()

        assert result["total_objectives"] == 5
        assert result["active"] == 1
        assert result["done"] == 1
        assert result["abandoned"] == 1
        assert result["superseded"] == 1
        assert result["blocked"] == 1
        # avg_progress is over all 5 records
        assert result["avg_progress_scope"] == "all_objectives"
        assert result["avg_progress"] == round((0.5 + 1.0 + 0.1 + 0.0 + 0.0) / 5, 3)

    def test_top_objectives_only_active(self, telos_dir):
        # done objective with higher priority must NOT appear in top_objectives
        rows = [
            _make_row(id="done-1", name="Done hi-pri", status="done",
                      progress=1.0, priority=10, updated_at=_iso(_RECENT)),
            _make_row(id="active-1", name="Active hi-pri", status="active",
                      progress=0.3, priority=9, updated_at=_iso(_RECENT)),
        ]
        self._write(telos_dir, rows)

        result = health_api._telos_summary()

        names = [t["name"] for t in result["top_objectives"]]
        assert "Active hi-pri" in names
        assert "Done hi-pri" not in names

    def test_no_data(self, state_dir):
        # telos dir does not exist
        result = health_api._telos_summary()
        assert result == {"status": "no-data"}


# ---------------------------------------------------------------------------
# TelosGraph.terminal_objectives()
# ---------------------------------------------------------------------------


class TestTerminalObjectivesQuery:
    def test_terminal_objectives_filters_terminal(self, tmp_path):
        graph = TelosGraph(telos_dir=tmp_path)
        from dharma_swarm.telos_graph import TelosObjective
        graph._objectives["a"] = TelosObjective(id="a", name="A",
                                                status=ObjectiveStatus.ACTIVE)
        graph._objectives["b"] = TelosObjective(id="b", name="B",
                                                status=ObjectiveStatus.DONE)
        graph._objectives["c"] = TelosObjective(id="c", name="C",
                                                status=ObjectiveStatus.ABANDONED)
        graph._objectives["d"] = TelosObjective(id="d", name="D",
                                                status=ObjectiveStatus.BLOCKED)

        terminal = graph.terminal_objectives()
        terminal_ids = {o.id for o in terminal}
        assert terminal_ids == {"b", "c"}
        # active/blocked excluded
        assert "a" not in terminal_ids
        assert "d" not in terminal_ids