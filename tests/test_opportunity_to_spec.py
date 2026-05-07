from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

from tools.build_protocol.opportunity_to_spec import (
    load_opportunity_board,
    opportunity_to_spec,
    render_spec,
    select_opportunity,
    spec_needs_operator_completion,
)
from tools.build_protocol.pilot00_dryrun_generator import parse_spec


def test_opportunity_to_spec_renders_pilot00_shape(tmp_path: Path) -> None:
    board = _write_board(tmp_path)
    rows = load_opportunity_board(board)
    selected = select_opportunity(rows, board_path=board, opportunity_id="opp_feedback")

    spec = render_spec(selected, today=date(2026, 5, 7))

    assert spec.startswith("# opportunity-2026-05-07-")
    assert "Telos: Close Shakti feedback edge - feedback_closure" in spec
    assert "Allowed paths:" in spec
    assert "- dharma_swarm/shakti_executive/inputs.py" in spec
    assert "## Source inputs" in spec
    assert "- telic:Outcome: dharma_swarm/shakti_executive/inputs.py:16" in spec
    assert "Proof command: TODO" in spec
    assert "Reviewer: TODO" in spec
    assert spec_needs_operator_completion(spec) is True


def test_opportunity_to_spec_output_reuses_pilot00_parser(tmp_path: Path) -> None:
    board = _write_board(tmp_path)
    out_dir = tmp_path / "specs"

    spec_path = opportunity_to_spec(
        board_path=board,
        output_dir=out_dir,
        opportunity_id="opp_feedback",
        today=date(2026, 5, 7),
    )

    with pytest.raises(ValueError, match="unknown"):
        parse_spec(spec_path)

    text = spec_path.read_text(encoding="utf-8")
    fixed = text.replace(
        "Proof command: TODO: single deterministic proof command",
        "Proof command: pytest tests/test_opportunity_to_spec.py -q",
    ).replace(
        "Reviewer: TODO: name the reviewer agent (must differ from builder)",
        "Reviewer: codex-reviewer",
    )
    spec_path.write_text(fixed, encoding="utf-8")

    pilot_spec = parse_spec(spec_path)
    assert pilot_spec.allowed_paths == ("dharma_swarm/shakti_executive/inputs.py",)
    assert pilot_spec.reviewer == "codex-reviewer"
    assert spec_needs_operator_completion(fixed) is False


def test_spec_completion_ignores_generator_comment_todo() -> None:
    spec = """# complete

<!-- Replace every TODO before running `dharma-build plan`. -->

Telos: Do the bounded thing

Allowed paths:
- dharma_swarm/shakti_executive/inputs.py

Forbidden paths:
- api/**

Proof command: pytest tests/test_opportunity_to_spec.py -q

Reviewer: codex-reviewer
"""

    assert spec_needs_operator_completion(spec) is False


def _write_board(tmp_path: Path) -> Path:
    board = tmp_path / "opportunity_board.json"
    board.write_text(
        json.dumps([
            {
                "opportunity_id": "opp_feedback",
                "title": "Close Shakti feedback edge",
                "domain": "internal_maintenance",
                "thesis": "feedback_closure",
                "final_score": 91.0,
                "why_now": "Outcome feedback does not reach the selector.",
                "evidence_signals": [
                    "telic:Outcome - dharma_swarm/shakti_executive/inputs.py:16",
                ],
                "source_inputs": [
                    {
                        "source": "telic:Outcome",
                        "evidence_ref": "dharma_swarm/shakti_executive/inputs.py:16",
                    }
                ],
            }
        ]),
        encoding="utf-8",
    )
    return board
