"""Tests for tools.build_protocol.brief_to_spec."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from tools.build_protocol.brief_to_spec import (
    DEFAULT_FORBIDDEN_PATHS,
    brief_to_spec,
    extract_move,
    find_latest_briefing,
    render_spec,
    write_spec,
)


SAMPLE_BRIEFING = """---
captured: 2026-05-07T04:30:00+08:00
type: morning_briefing
---

# Morning Briefing — 2026-05-07

## In one paragraph

The substrate is frozen. TCS has been 0.70.

## Overnight findings (3 bullets max)

- A
- B
- C

## The single most important move for today

**Edit `~/.claude/scheduled-tasks/heartbeat-3h/SKILL.md` — add a Solicit step that writes `channel="review"` stigmergy marks for the top-3 unaddressed gaps after Phase 2 identification.**

Mechanical, ~10 LOC, no research required. Verify with `pytest tests/test_heartbeat.py -q`.

## What's stale and needs attention

Other stuff.
"""


SAMPLE_NO_MOVE = """---
captured: 2026-05-07T04:30:00+08:00
---

# Morning Briefing — 2026-05-07

## In one paragraph

Nothing today.
"""


def test_extract_move_pulls_headline_body_paths_loc_proof():
    move = extract_move(SAMPLE_BRIEFING)
    assert "Edit" in move.headline
    assert "stigmergy" in move.headline.lower()
    assert any("heartbeat-3h/SKILL.md" in p for p in move.target_paths)
    assert move.loc_estimate == 10
    assert any("pytest" in c for c in move.proof_commands)
    # the heartbeat skill is not on the hot list, so no warning
    assert move.hot_file_warnings == ()


def test_extract_move_flags_hot_files():
    text = SAMPLE_BRIEFING.replace(
        "~/.claude/scheduled-tasks/heartbeat-3h/SKILL.md",
        "dharma_swarm/orchestrate_live.py",
    )
    move = extract_move(text)
    assert any("orchestrate_live.py" in p for p in move.hot_file_warnings)


def test_extract_move_raises_when_no_move_section():
    with pytest.raises(ValueError, match="most important move"):
        extract_move(SAMPLE_NO_MOVE)


def test_render_spec_contains_required_pilot00_fields():
    move = extract_move(SAMPLE_BRIEFING)
    spec = render_spec(move, briefing_path=Path("/dev/null/briefing.md"), today=date(2026, 5, 7))
    # Pilot-00 spec format requires these literal field names
    assert spec.startswith("# brief-2026-05-07-")
    assert "Telos:" in spec
    assert "Allowed paths:" in spec
    assert "Forbidden paths:" in spec
    assert "Proof command:" in spec
    assert "Reviewer:" in spec
    # All defaults present
    for fp in DEFAULT_FORBIDDEN_PATHS:
        assert f"- {fp}" in spec
    # Reviewer always TODO until human edits
    assert "Reviewer: TODO" in spec


def test_render_spec_extracts_proof_command_when_present():
    move = extract_move(SAMPLE_BRIEFING)
    spec = render_spec(move, briefing_path=Path("/dev/null/briefing.md"))
    assert "pytest tests/test_heartbeat.py" in spec


def test_render_spec_uses_TODO_when_proof_missing():
    text = SAMPLE_BRIEFING.replace("`pytest tests/test_heartbeat.py -q`", "no command here")
    move = extract_move(text)
    spec = render_spec(move, briefing_path=Path("/dev/null/briefing.md"))
    assert "Proof command: TODO" in spec


def test_rendered_spec_parses_via_pilot00_when_todos_replaced(tmp_path):
    """The seam's whole purpose: brief_to_spec output → pilot00 parse_spec.

    With TODOs in place, pilot00 must REJECT (good — it's the human gate).
    With TODOs replaced, pilot00 must ACCEPT.
    """
    from tools.build_protocol.pilot00_dryrun_generator import parse_spec

    move = extract_move(SAMPLE_BRIEFING)
    spec = render_spec(move, briefing_path=Path("/dev/null/briefing.md"))
    # Reviewer was TODO; pilot00 should reject as containing unknown
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(spec, encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        parse_spec(spec_path)
    # Replace the only TODO and pilot00 should accept
    fixed = spec.replace(
        "Reviewer: TODO: name the reviewer agent (must differ from builder)",
        "Reviewer: codex-reviewer",
    )
    spec_path.write_text(fixed, encoding="utf-8")
    pilot_spec = parse_spec(spec_path)
    assert pilot_spec.reviewer == "codex-reviewer"
    assert pilot_spec.proof_command.startswith("pytest")


def test_write_spec_produces_dated_path(tmp_path):
    out = write_spec(
        "# test-spec\nTelos: x\n",
        output_dir=tmp_path,
        title_slug="test-slug",
        today=date(2026, 5, 7),
    )
    assert out == tmp_path / "2026-05-07-test-slug.md"
    assert out.read_text() == "# test-spec\nTelos: x\n"


def test_find_latest_briefing_skips_empty(tmp_path):
    older = tmp_path / "2026-05-06"
    older.mkdir()
    (older / "morning_briefing.md").write_text("hello", encoding="utf-8")
    newer_empty = tmp_path / "2026-05-07"
    newer_empty.mkdir()
    (newer_empty / "morning_briefing.md").write_text("", encoding="utf-8")
    found = find_latest_briefing(daily_root=tmp_path)
    assert found.parent.name == "2026-05-06"


def test_brief_to_spec_end_to_end(tmp_path):
    daily = tmp_path / "daily"
    day = daily / "2026-05-07"
    day.mkdir(parents=True)
    (day / "morning_briefing.md").write_text(SAMPLE_BRIEFING, encoding="utf-8")
    out_dir = tmp_path / "specs"
    spec_path = brief_to_spec(
        briefing_path=day / "morning_briefing.md",
        output_dir=out_dir,
        today=date(2026, 5, 7),
    )
    assert spec_path.parent == out_dir
    text = spec_path.read_text(encoding="utf-8")
    assert "Telos: Edit" in text
    assert "TODO" in text  # Reviewer TODO remains until human edits
