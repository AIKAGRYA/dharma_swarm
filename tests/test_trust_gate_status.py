"""Fixture-driven tests for scripts/governance/trust_gate_status.py.

The scorer is a projection of existing owners; these tests run it against
synthetic owner files and assert the RED/AMBER/GREEN mapping and the JSON
schema. No network, no real git remote.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/governance/trust_gate_status.py"

spec = importlib.util.spec_from_file_location("trust_gate_status", SCRIPT)
assert spec is not None and spec.loader is not None
tgs = importlib.util.module_from_spec(spec)
sys.modules["trust_gate_status"] = tgs
spec.loader.exec_module(tgs)


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    (tmp_path / "reports/anatomy_audit_2099-01-01").mkdir(parents=True)
    (tmp_path / "reports/anatomy_audit_2099-01-01/lane_E.md").write_text(
        "Forge arena measured `cost_normalized_lift = -0.100` n=3\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/governance").mkdir(parents=True)
    (tmp_path / "docs/governance/VENTURE_CELL_PORTFOLIO.yaml").write_text(
        "schema_version: 1\n"
        "cells:\n"
        "  - id: cell-a\n"
        "    status: ACTIVE_SEASON_0\n"
        "  - id: cell-b\n"
        "    status: HELD\n"
        "    gauntlet: { revenue_usd: 0 }\n"
        "envisioned:\n"
        "  - id: cell-c\n"
        "    status: ENVISIONED\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/state").mkdir(parents=True)
    (tmp_path / "docs/state/BROKEN_REGISTER.md").write_text(
        "# BROKEN REGISTER\n\n## OPEN ITEMS\n\n"
        "### BR-001 — thing one\n**status:** OPEN\n\n"
        "## CLOSED ITEMS\n\n"
        "### BR-002 — thing two\n**status:** FIXED\n\n"
        "### BR-003 — thing three\n**status:** FIXED\n",
        encoding="utf-8",
    )
    (tmp_path / "dharma_swarm").mkdir()
    (tmp_path / "dharma_swarm/context_compiler.py").write_text(
        "def _build_sections(self):\n"
        "    sections = []\n"
        "    sections.append(governance_section)\n"
        "    sections.append(memory_kernel_section)\n",
        encoding="utf-8",
    )
    return tmp_path


def test_verdict_mapping_boundaries() -> None:
    assert tgs.verdict_for(0.8) == "GREEN"
    assert tgs.verdict_for(1.0) == "GREEN"
    assert tgs.verdict_for(0.79) == "AMBER"
    assert tgs.verdict_for(0.4) == "AMBER"
    assert tgs.verdict_for(0.39) == "RED"
    assert tgs.verdict_for(0.0) == "RED"


def test_c2_negative_lift_is_red(fake_repo: Path) -> None:
    result = tgs.score_c2(fake_repo)
    assert result.verdict == "RED"
    assert result.score <= 0.1
    assert any("-0.1" in ev for ev in result.evidence)


def test_c2_positive_lift_scores_up(fake_repo: Path) -> None:
    lane = fake_repo / "reports/anatomy_audit_2099-01-01/lane_E.md"
    lane.write_text("measured swarm_lift = 0.25 on the bench\n", encoding="utf-8")
    result = tgs.score_c2(fake_repo)
    assert result.score == pytest.approx(0.75)
    assert result.verdict == "AMBER"


def test_c2_unmeasured_is_red_zero(tmp_path: Path) -> None:
    result = tgs.score_c2(tmp_path)
    assert result.score == 0.0
    assert result.verdict == "RED"
    assert any("unmeasured" in ev for ev in result.evidence)


def test_c3_active_without_receipts_is_red(fake_repo: Path) -> None:
    result = tgs.score_c3(fake_repo)
    assert result.verdict == "RED"
    assert any("cell-a" in ev for ev in result.evidence)


def test_c3_receipts_plus_active_is_green(fake_repo: Path) -> None:
    portfolio = fake_repo / "docs/governance/VENTURE_CELL_PORTFOLIO.yaml"
    portfolio.write_text(
        portfolio.read_text(encoding="utf-8").replace("revenue_usd: 0", "revenue_usd: 500"),
        encoding="utf-8",
    )
    result = tgs.score_c3(fake_repo)
    assert result.score == pytest.approx(0.85)
    assert result.verdict == "GREEN"


def test_parse_cell_statuses(fake_repo: Path) -> None:
    statuses = tgs.parse_cell_statuses(
        fake_repo / "docs/governance/VENTURE_CELL_PORTFOLIO.yaml")
    assert statuses == {
        "cell-a": "ACTIVE_SEASON_0", "cell-b": "HELD", "cell-c": "ENVISIONED"}


def test_c4_uses_injected_branches(fake_repo: Path) -> None:
    branches = ["main", "feat/x-gold-rescue", "feat/organ-seed", "chore/y"]
    result = tgs.score_c4(fake_repo, branches)
    # br_component = 2/3 closed; seed_component = 1/(1+2)
    assert result.score == pytest.approx(0.5 * (2 / 3) + 0.5 * (1 / 3))
    assert result.verdict == "AMBER"


def test_c4_offline_branches_unmeasured(fake_repo: Path) -> None:
    result = tgs.score_c4(fake_repo, None)
    assert any("unmeasured" in ev for ev in result.evidence)
    assert result.score == pytest.approx(0.5 * (2 / 3), abs=1e-3)


def test_c5_not_first_token_is_red(fake_repo: Path) -> None:
    result = tgs.score_c5(fake_repo)
    assert result.verdict == "RED"
    assert result.score == pytest.approx(0.2)
    assert any("1 sections render before" in ev for ev in result.evidence)


def test_c5_first_token_is_green(fake_repo: Path) -> None:
    compiler = fake_repo / "dharma_swarm/context_compiler.py"
    compiler.write_text(
        "def _build_sections(self):\n"
        "    sections = []\n"
        "    sections.append(memory_kernel_section)\n"
        "    sections.append(governance_section)\n",
        encoding="utf-8",
    )
    result = tgs.score_c5(fake_repo)
    assert result.verdict == "GREEN"
    assert result.score == pytest.approx(0.9)


def test_c5_unwired_is_red_zero(fake_repo: Path) -> None:
    compiler = fake_repo / "dharma_swarm/context_compiler.py"
    compiler.write_text("def _build_sections(self):\n    sections = []\n",
                        encoding="utf-8")
    result = tgs.score_c5(fake_repo)
    assert result.score == 0.0
    assert result.verdict == "RED"


def test_parse_broken_counts(fake_repo: Path) -> None:
    counts = tgs.parse_broken_counts(fake_repo / "docs/state/BROKEN_REGISTER.md")
    assert counts == (3, 1, 2)


def test_c4_unknown_lifecycle_cannot_inflate_closed_ratio(fake_repo: Path) -> None:
    register = fake_repo / "docs/state/BROKEN_REGISTER.md"
    register.write_text(
        "# BROKEN REGISTER\n\n## OPEN ITEMS\n\n"
        "### BR-001 — open\n**status:** OPEN\n\n"
        "### BR-002 — malformed\n**status:** DEGRADED\n\n"
        "## CLOSED ITEMS\n\n"
        "### BR-003 — fixed\n**status:** FIXED\n",
        encoding="utf-8",
    )

    result = tgs.score_c4(fake_repo, [])

    assert any("total=3 open-like=1 closed-like=1" in item for item in result.evidence)
    assert result.score == 0.667


def test_scoreboard_json_schema(fake_repo: Path) -> None:
    payload = tgs.build_scoreboard(fake_repo, runtime_tree=None, branches=[])
    assert payload["schema"] == "dharma_swarm.trust_gate_status.v1"
    assert payload["fact_owner"] == "docs/vision_maps/NORTH_STAR.md §8"
    assert payload["authority"] == "projection_only"
    assert isinstance(payload["gate_open"], bool)
    conditions = payload["conditions"]
    assert [c["id"] for c in conditions] == ["C1", "C2", "C3", "C4", "C5"]
    for c in conditions:
        assert set(c) == {"id", "condition", "evidence", "score", "verdict",
                          "owner_of_truth"}
        assert c["verdict"] in {"RED", "AMBER", "GREEN"}
        assert 0.0 <= c["score"] <= 1.0
        assert isinstance(c["evidence"], list) and c["evidence"]
        assert isinstance(c["owner_of_truth"], str) and c["owner_of_truth"]


def test_gate_open_requires_all_green(fake_repo: Path) -> None:
    payload = tgs.build_scoreboard(fake_repo, runtime_tree=None, branches=[])
    assert payload["gate_open"] is False  # synthetic fixture is not all-GREEN


def test_render_table_contains_verdicts(fake_repo: Path) -> None:
    payload = tgs.build_scoreboard(fake_repo, runtime_tree=None, branches=[])
    table = tgs.render_table(payload)
    assert "TRUST GATE SCOREBOARD" in table
    assert "not authority" in table
    for c in payload["conditions"]:
        assert c["id"] in table
