"""Tests for operator_directives — the air traffic controller."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.operator_directives import (
    OperatorDirectives,
    _parse,
    invalidate_cache,
    is_forbidden,
    load_directives,
    mission_context_block,
    seed_if_absent,
)


@pytest.fixture(autouse=True)
def _flush():
    invalidate_cache()
    yield
    invalidate_cache()


SAMPLE = """\
## Active Mission
NeurIPS 2026 Position Paper — abstract due May 4

## DO (in priority order)
1. Support NeurIPS abstract writing
2. Maintain daemon health
3. Produce swarm-relevant research

## DO NOT
- Do NOT work on mech-interp / R_V / contraction / geometric_lens (personal research)
- Do NOT reopen quarantined synthesis loops (eval_probe_loop)
- Do NOT prioritize background metabolism / consolidation churn over campaign work

## Key Context
- Primary campaign is authoritative
- 18 days to abstract
"""


def test_parse_sections() -> None:
    d = _parse(SAMPLE)
    assert d.active_mission == "NeurIPS 2026 Position Paper — abstract due May 4"
    assert len(d.do_items) == 3
    assert d.do_items[0] == "Support NeurIPS abstract writing"
    assert len(d.dont_items) == 3
    assert len(d.context_lines) == 2
    assert d.has_content is True


def test_parse_empty() -> None:
    d = _parse("")
    assert d.active_mission == ""
    assert d.do_items == []
    assert d.dont_items == []
    assert d.has_content is False


def test_is_forbidden_positive_matches() -> None:
    d = _parse(SAMPLE)
    assert is_forbidden("investigate R_V contraction in layer 5", d)
    assert is_forbidden("check mech-interp results", d)
    assert is_forbidden("geometric_lens analysis run", d)
    assert is_forbidden("contraction pattern detected", d)
    assert is_forbidden("reopen quarantined synthesis loops", d)
    assert is_forbidden("background metabolism is churning", d)
    assert is_forbidden("consolidation churn detected", d)


def test_is_forbidden_negative_matches() -> None:
    d = _parse(SAMPLE)
    assert not is_forbidden("write NeurIPS abstract section 2", d)
    assert not is_forbidden("maintain daemon pulse health", d)
    assert not is_forbidden("produce competitive landscape research", d)
    assert not is_forbidden("gauntlet score check", d)
    assert not is_forbidden("run guardian health audit", d)


def test_is_forbidden_empty_directives() -> None:
    assert not is_forbidden("anything", None)
    assert not is_forbidden("anything", OperatorDirectives())


def test_mission_context_block_format() -> None:
    d = _parse(SAMPLE)
    block = mission_context_block(d)
    assert "ACTIVE MISSION" in block
    assert "OPERATOR PRIORITIES" in block
    assert "OPERATOR CONSTRAINTS" in block
    assert "NeurIPS" in block


def test_mission_context_block_empty() -> None:
    assert mission_context_block(None) == ""
    assert mission_context_block(OperatorDirectives()) == ""


def test_seed_if_absent_creates_file(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    path = seed_if_absent(state_dir)
    assert path.exists()
    text = path.read_text()
    assert "NeurIPS" in text
    assert "## Active Mission" in text
    assert "## DO NOT" in text


def test_seed_if_absent_does_not_overwrite(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    seed_if_absent(state_dir)
    path = state_dir / "meta" / "OPERATOR_DIRECTIVES.md"
    path.write_text("custom content")
    seed_if_absent(state_dir)
    assert path.read_text() == "custom content"


def test_load_directives_from_disk(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    seed_if_absent(state_dir)
    d = load_directives(state_dir, force=True)
    assert d.has_content
    assert "NeurIPS" in d.active_mission
    assert len(d.do_items) >= 3
    assert len(d.dont_items) >= 3


def test_load_directives_missing_file(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir()
    (state_dir / "meta").mkdir()
    d = load_directives(state_dir, force=True)
    assert not d.has_content
    assert d.do_items == []


def test_load_directives_caches(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    seed_if_absent(state_dir)
    d1 = load_directives(state_dir, force=True)
    d2 = load_directives(state_dir)  # cached
    assert d1 is d2


def test_parse_alternative_header_styles() -> None:
    """Support both '## DO NOT' and '## Don't' and '## DONT'."""
    for header in ["## DO NOT", "## Don't", "## DONT"]:
        text = f"## Active Mission\nTest\n\n{header}\n- Do NOT work on mech-interp / R_V\n"
        d = _parse(text)
        assert len(d.dont_items) >= 1, f"failed for header: {header}"
        assert is_forbidden("mech-interp research", d)
