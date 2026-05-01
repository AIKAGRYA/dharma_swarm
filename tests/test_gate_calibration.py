"""Tests for the gate_calibration script (Component 1.3).

The script lives at ~/.dharma/scripts/gate_calibration.py (outside the
dharma_swarm package) so tests load it via importlib.

Covers:
1. Empty witness dir -> empty digest, no crash
2. Per-gate aggregation correctness
3. Gate name extraction from reflection text
4. Outcome normalization (PASS/ALLOW/BLOCKED variants)
5. Drift detection: stable -> no alarm; sudden change -> alarm
6. Insufficient samples -> needs_review = False (defensive)
7. Markdown output truncation to preamble budget
8. JSON output round-trip

Run: pytest tests/test_gate_calibration.py -q
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Load gate_calibration.py as a module, since it's a script not in a package
_SCRIPT_PATH = Path.home() / ".dharma" / "scripts" / "gate_calibration.py"


@pytest.fixture(scope="module")
def gc_module():
    """Load the gate_calibration script as an importable module."""
    spec = importlib.util.spec_from_file_location("gate_calibration", _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        pytest.skip(f"gate_calibration.py not found at {_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["gate_calibration"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def witness_dir(tmp_path: Path) -> Path:
    d = tmp_path / "witness"
    d.mkdir()
    return d


@pytest.fixture
def md_path(tmp_path: Path) -> Path:
    return tmp_path / "gate_calibration.md"


@pytest.fixture
def json_path(tmp_path: Path) -> Path:
    return tmp_path / "gate_calibration.json"


def _seed_witness_jsonl(
    witness_dir: Path,
    *,
    date: str,
    rows: list[dict],
) -> Path:
    """Seed a single day's witness file. `rows` is list of partial dicts;
    ts is computed from `date` arg if not in row."""
    path = witness_dir / f"witness_{date.replace('-', '')}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for i, row in enumerate(rows):
            base_ts = datetime.fromisoformat(date + "T00:00:00+00:00")
            ts = (base_ts + timedelta(seconds=i)).isoformat()
            entry = {
                "ts": row.get("ts", ts),
                "phase": row.get("phase", "before_complete"),
                "outcome": row.get("outcome", "PASS"),
                "action": row.get("action", "test"),
                "reflection": row.get("reflection", ""),
            }
            if "prediction_id" in row:
                entry["prediction_id"] = row["prediction_id"]
            f.write(json.dumps(entry) + "\n")
    return path


# ---------------------------------------------------------------------------
# 1. Empty witness dir
# ---------------------------------------------------------------------------


def test_empty_witness_dir(gc_module, witness_dir, md_path, json_path) -> None:
    rc = gc_module.main(
        witness_dir=witness_dir,
        md_path=md_path,
        json_path=json_path,
        window_days=30,
        now=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    assert rc == 0
    assert md_path.exists()
    assert json_path.exists()

    payload = json.loads(json_path.read_text())
    assert payload["n_total_records"] == 0
    assert payload["per_gate"] == {}


# ---------------------------------------------------------------------------
# 2. Per-gate aggregation
# ---------------------------------------------------------------------------


def test_per_gate_aggregation(
    gc_module, witness_dir, md_path, json_path
) -> None:
    _seed_witness_jsonl(
        witness_dir,
        date="2026-04-25",
        rows=[
            {"outcome": "PASS", "reflection": "AHIMSA passed"},
            {"outcome": "PASS", "reflection": "AHIMSA passed"},
            {"outcome": "BLOCKED", "reflection": "AHIMSA violation"},
            {"outcome": "PASS", "reflection": "SATYA: claim coherent"},
            {"outcome": "BLOCKED", "reflection": "SATYA: claim incoherent"},
        ],
    )
    rc = gc_module.main(
        witness_dir=witness_dir,
        md_path=md_path,
        json_path=json_path,
        window_days=30,
        now=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    assert rc == 0
    payload = json.loads(json_path.read_text())
    per_gate = payload["per_gate"]
    assert "AHIMSA" in per_gate
    assert "SATYA" in per_gate
    assert per_gate["AHIMSA"]["n_total"] == 3
    assert per_gate["AHIMSA"]["n_pass"] == 2
    assert per_gate["AHIMSA"]["n_block"] == 1
    assert per_gate["AHIMSA"]["pass_rate"] == pytest.approx(2 / 3, abs=0.01)
    assert per_gate["SATYA"]["n_total"] == 2
    assert per_gate["SATYA"]["pass_rate"] == 0.5


# ---------------------------------------------------------------------------
# 3. Gate name extraction (case-insensitive, from reflection text)
# ---------------------------------------------------------------------------


def test_gate_extraction_case_insensitive(gc_module) -> None:
    assert gc_module._extract_gate("ahimsa violation: harmful") == "AHIMSA"
    assert gc_module._extract_gate("Mahakali strike triggered") == "MAHAKALI"
    assert gc_module._extract_gate("CONSENT: missing user consent") == "CONSENT"
    assert gc_module._extract_gate("nothing about gates") == "general"
    assert gc_module._extract_gate("") == "general"


# ---------------------------------------------------------------------------
# 4. Outcome normalization
# ---------------------------------------------------------------------------


def test_outcome_normalization(gc_module) -> None:
    assert gc_module._normalize_outcome("PASS") == "pass"
    assert gc_module._normalize_outcome("ALLOW") == "pass"
    assert gc_module._normalize_outcome("allowed") == "pass"
    assert gc_module._normalize_outcome("BLOCKED") == "block"
    assert gc_module._normalize_outcome("REFUSE") == "block"
    assert gc_module._normalize_outcome("HOLD") == "hold"
    assert gc_module._normalize_outcome("MAYBE") == "unknown"
    assert gc_module._normalize_outcome("") == "unknown"


# ---------------------------------------------------------------------------
# 5. Drift detection
# ---------------------------------------------------------------------------


def test_drift_detection_stable_no_alarm(
    gc_module, witness_dir, md_path, json_path
) -> None:
    # 12 days of stable AHIMSA pass_rate around 0.80
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    for day_offset in range(12, 0, -1):
        date = (base - timedelta(days=day_offset)).date().isoformat()
        # 80% pass: 8 PASS, 2 BLOCKED
        rows = (
            [{"outcome": "PASS", "reflection": "AHIMSA"}] * 8
            + [{"outcome": "BLOCKED", "reflection": "AHIMSA"}] * 2
        )
        _seed_witness_jsonl(witness_dir, date=date, rows=rows)

    rc = gc_module.main(
        witness_dir=witness_dir,
        md_path=md_path,
        json_path=json_path,
        window_days=30,
        now=base,
    )
    assert rc == 0
    payload = json.loads(json_path.read_text())
    drift = payload["drift"].get("AHIMSA", {})
    assert drift.get("needs_review") is False
    assert drift.get("baseline_mean") == pytest.approx(0.8, abs=0.01)


def test_drift_detection_sudden_change_fires(
    gc_module, witness_dir, md_path, json_path
) -> None:
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    # 11 days of 0.80, latest day at 0.20 -> big drift
    for day_offset in range(12, 1, -1):
        date = (base - timedelta(days=day_offset)).date().isoformat()
        rows = (
            [{"outcome": "PASS", "reflection": "AHIMSA"}] * 8
            + [{"outcome": "BLOCKED", "reflection": "AHIMSA"}] * 2
        )
        _seed_witness_jsonl(witness_dir, date=date, rows=rows)
    # latest day yesterday-style: 2 PASS, 8 BLOCKED -> 0.20
    latest_date = (base - timedelta(days=1)).date().isoformat()
    _seed_witness_jsonl(
        witness_dir,
        date=latest_date,
        rows=(
            [{"outcome": "PASS", "reflection": "AHIMSA"}] * 2
            + [{"outcome": "BLOCKED", "reflection": "AHIMSA"}] * 8
        ),
    )

    rc = gc_module.main(
        witness_dir=witness_dir,
        md_path=md_path,
        json_path=json_path,
        window_days=30,
        now=base,
    )
    assert rc == 0
    payload = json.loads(json_path.read_text())
    drift = payload["drift"].get("AHIMSA", {})
    assert drift.get("needs_review") is True
    assert drift.get("latest_pass_rate") == pytest.approx(0.2, abs=0.01)


# ---------------------------------------------------------------------------
# 6. Insufficient samples -> no alarm
# ---------------------------------------------------------------------------


def test_insufficient_samples_no_alarm(
    gc_module, witness_dir, md_path, json_path
) -> None:
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    # Only 3 days of data (below MIN_SAMPLES_FOR_BASELINE = 10)
    for day_offset in range(3, 0, -1):
        date = (base - timedelta(days=day_offset)).date().isoformat()
        rows = [{"outcome": "BLOCKED", "reflection": "AHIMSA"}]  # 100% block
        _seed_witness_jsonl(witness_dir, date=date, rows=rows)

    rc = gc_module.main(
        witness_dir=witness_dir,
        md_path=md_path,
        json_path=json_path,
        window_days=30,
        now=base,
    )
    assert rc == 0
    payload = json.loads(json_path.read_text())
    drift = payload["drift"].get("AHIMSA", {})
    # Even though pass_rate looks extreme, insufficient history -> no alarm
    assert drift.get("needs_review") is False
    assert "insufficient" in drift.get("reason", "").lower()


# ---------------------------------------------------------------------------
# 7. Markdown truncation to preamble budget
# ---------------------------------------------------------------------------


def test_markdown_truncated_to_preamble_budget(
    gc_module, witness_dir, md_path, json_path
) -> None:
    # Force long output by seeding many gates with many records
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    rows = []
    for gate in gc_module.KNOWN_GATES:
        for _ in range(20):
            rows.append({
                "outcome": "PASS",
                "reflection": f"{gate} reflection text" * 30,  # bulky reflections
            })
    date = (base - timedelta(days=1)).date().isoformat()
    _seed_witness_jsonl(witness_dir, date=date, rows=rows)

    rc = gc_module.main(
        witness_dir=witness_dir,
        md_path=md_path,
        json_path=json_path,
        window_days=30,
        now=base,
    )
    assert rc == 0
    md_text = md_path.read_text(encoding="utf-8")
    assert len(md_text) <= gc_module.PREAMBLE_BUDGET_CHARS + 100  # small slack


# ---------------------------------------------------------------------------
# 8. JSON output round-trip
# ---------------------------------------------------------------------------


def test_json_output_parseable(
    gc_module, witness_dir, md_path, json_path
) -> None:
    _seed_witness_jsonl(
        witness_dir,
        date="2026-04-30",
        rows=[
            {"outcome": "PASS", "reflection": "AHIMSA passed"},
            {"outcome": "BLOCKED", "reflection": "SATYA blocked"},
        ],
    )
    rc = gc_module.main(
        witness_dir=witness_dir,
        md_path=md_path,
        json_path=json_path,
        window_days=30,
        now=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    assert rc == 0
    payload = json.loads(json_path.read_text())
    assert "computed_at" in payload
    assert "per_gate" in payload
    assert "drift" in payload
    assert "config" in payload
    assert payload["config"]["drift_sigma_threshold"] == 2.0


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_corrupted_jsonl_lines_skipped(
    gc_module, witness_dir, md_path, json_path
) -> None:
    path = witness_dir / "witness_20260430.jsonl"
    path.write_text(
        json.dumps({
            "ts": "2026-04-30T12:00:00+00:00",
            "phase": "before_complete",
            "outcome": "PASS",
            "reflection": "AHIMSA",
        }) + "\n"
        + "not json\n"
        + "{partial\n"
        + "\n",
        encoding="utf-8",
    )
    rc = gc_module.main(
        witness_dir=witness_dir,
        md_path=md_path,
        json_path=json_path,
        window_days=30,
        now=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    assert rc == 0
    payload = json.loads(json_path.read_text())
    assert payload["n_total_records"] == 1
