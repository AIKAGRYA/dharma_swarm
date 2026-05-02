from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.render_repair_briefing import (
    MAX_LINE_CHARS,
    NO_DATA_LINE,
    render_repair_briefing,
)


def test_missing_file_renders_no_data(tmp_path: Path) -> None:
    assert render_repair_briefing(tmp_path / "missing.json") == NO_DATA_LINE


def test_full_score_renders_all_fields(tmp_path: Path) -> None:
    score = tmp_path / "r_repair_score.json"
    score.write_text(
        json.dumps(
            {
                "r_aggregate": 0.72,
                "r_gate": 0.85,
                "r_mutation": 0.61,
                "r_welfare": None,
                "n_predictions_total": 42,
                "confidence": 0.7,
                "provisional": True,
                "near_eigenform": False,
                "notes": ["first note"],
            }
        ),
        encoding="utf-8",
    )

    line = render_repair_briefing(score)
    assert "Repair: agg=0.72" in line
    assert "(gate=0.85 mut=0.61 wel=N/A)" in line
    assert "n=42 conf=0.7" in line
    assert "[provisional]" in line
    assert "[near_eigenform=False]" in line
    assert "notes: first note" in line


def test_nan_values_render_as_na(tmp_path: Path) -> None:
    score = tmp_path / "r_repair_score.json"
    score.write_text(
        json.dumps(
            {
                "r_aggregate": "nan",
                "r_gate": None,
                "r_mutation": float("nan"),
                "r_welfare": "NaN",
                "n_predictions_total": 0,
                "confidence": None,
                "near_eigenform": False,
            }
        ),
        encoding="utf-8",
    )

    line = render_repair_briefing(score)
    assert "agg=N/A" in line
    assert "gate=N/A" in line
    assert "mut=N/A" in line
    assert "wel=N/A" in line
    assert "conf=N/A" in line
    assert "nan" not in line.lower()


def test_near_eigenform_prefix_appears(tmp_path: Path) -> None:
    score = tmp_path / "r_repair_score.json"
    score.write_text(
        json.dumps(
            {
                "r_aggregate": 0.99,
                "r_gate": 1.0,
                "r_mutation": 1.0,
                "r_welfare": 0.98,
                "n_predictions_total": 90,
                "confidence": 1.0,
                "provisional": False,
                "near_eigenform": True,
                "notes": ["too perfect"],
            }
        ),
        encoding="utf-8",
    )

    assert render_repair_briefing(score).startswith("⚠️ NEAR_EIGENFORM ⚠️ ")


def test_output_line_is_bounded(tmp_path: Path) -> None:
    score = tmp_path / "r_repair_score.json"
    score.write_text(
        json.dumps(
            {
                "r_aggregate": 0.72,
                "r_gate": 0.85,
                "r_mutation": 0.61,
                "r_welfare": None,
                "n_predictions_total": 42,
                "confidence": 0.7,
                "provisional": True,
                "near_eigenform": True,
                "notes": ["x" * 500],
            }
        ),
        encoding="utf-8",
    )

    assert len(render_repair_briefing(score)) <= MAX_LINE_CHARS
