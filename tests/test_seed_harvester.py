"""Tests for dharma_swarm.seed_harvester — YSD grading + seed extraction.

Validates:
- internal_to_ysd_display mapping across score ranges
- ysd_label threshold lookup
- _make_id deterministic hashing
- Seed dataclass construction and to_dict
- extract_from_lost_ideas markdown parsing
- extract_from_micro_saas markdown parsing
- extract_from_moonshots markdown parsing
- extract_from_scratch_dir keyword scanning
- compute_naff_score pattern detection and moat reduction
- compute_moat label generation
- grade_seed composite scoring, clamping, and YSD assignment
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.seed_harvester import (
    Seed,
    _make_id,
    compute_moat,
    compute_naff_score,
    extract_from_lost_ideas,
    extract_from_micro_saas,
    extract_from_moonshots,
    extract_from_scratch_dir,
    grade_seed,
    internal_to_ysd_display,
    ysd_label,
)


# ---------------------------------------------------------------------------
# YSD display conversion
# ---------------------------------------------------------------------------


class TestInternalToYsdDisplay:
    def test_low_score(self):
        display = internal_to_ysd_display(5)
        assert display.startswith("5.")

    def test_mid_score(self):
        display = internal_to_ysd_display(50)
        assert "10" in display

    def test_high_score(self):
        display = internal_to_ysd_display(85)
        assert "13" in display

    def test_transcendent_score(self):
        display = internal_to_ysd_display(95)
        assert "14" in display

    def test_zero_score(self):
        display = internal_to_ysd_display(0)
        assert display.startswith("5.")

    def test_max_score(self):
        display = internal_to_ysd_display(100)
        assert display.startswith("5.14")


# ---------------------------------------------------------------------------
# ysd_label
# ---------------------------------------------------------------------------


class TestYsdLabel:
    def test_kill_range(self):
        label = ysd_label(0)
        assert "KILL" in label

    def test_naff_range(self):
        label = ysd_label(25)
        assert "NAFF" in label

    def test_decent_range(self):
        label = ysd_label(45)
        assert "DECENT" in label

    def test_good_range(self):
        label = ysd_label(65)
        assert "GOOD" in label

    def test_exceptional_range(self):
        label = ysd_label(85)
        assert "EXCEPTIONAL" in label

    def test_transcendent_range(self):
        label = ysd_label(95)
        assert "TRANSCENDENT" in label


# ---------------------------------------------------------------------------
# _make_id
# ---------------------------------------------------------------------------


class TestMakeId:
    def test_deterministic(self):
        assert _make_id("Test Idea") == _make_id("Test Idea")

    def test_case_insensitive(self):
        assert _make_id("Test") == _make_id("test")

    def test_strips_whitespace(self):
        assert _make_id("  test  ") == _make_id("test")

    def test_returns_12_chars(self):
        assert len(_make_id("anything")) == 12

    def test_different_names_different_ids(self):
        assert _make_id("idea one") != _make_id("idea two")


# ---------------------------------------------------------------------------
# Seed dataclass
# ---------------------------------------------------------------------------


class TestSeed:
    def test_construction(self):
        s = Seed(
            id="abc123", name="Test Seed",
            description="A test", source_file="/tmp/test.md",
            source_type="scratch",
        )
        assert s.ysd_score == 0
        assert s.status == "raw"

    def test_to_dict(self):
        s = Seed(
            id="abc", name="S", description="D",
            source_file="f", source_type="core",
        )
        d = s.to_dict()
        assert d["id"] == "abc"
        assert d["name"] == "S"
        assert isinstance(d, dict)


# ---------------------------------------------------------------------------
# extract_from_lost_ideas
# ---------------------------------------------------------------------------


class TestExtractFromLostIdeas:
    def test_parses_ideas(self, tmp_path):
        md = tmp_path / "lost.md"
        md.write_text("""# Lost Ideas

#### 1.1 AI Resume Screener
**What:** Screens resumes using NLP
**Status:** KILLED
**Why killed:** Too competitive

#### 1.2 Market Analyzer Tool
**What:** Analyzes market trends in real-time
**Revenue:** SaaS $49/month
""")
        seeds = extract_from_lost_ideas(md)
        assert len(seeds) == 2
        assert seeds[0].name == "AI Resume Screener"
        assert seeds[0].status == "killed"
        assert seeds[0].kill_history == 1
        assert seeds[1].name == "Market Analyzer Tool"
        assert "SaaS $49/month" in seeds[1].revenue_model

    def test_missing_file_returns_empty(self, tmp_path):
        assert extract_from_lost_ideas(tmp_path / "nope.md") == []

    def test_empty_file_returns_empty(self, tmp_path):
        md = tmp_path / "empty.md"
        md.write_text("# Nothing here")
        assert extract_from_lost_ideas(md) == []


# ---------------------------------------------------------------------------
# extract_from_micro_saas
# ---------------------------------------------------------------------------


class TestExtractFromMicroSaas:
    def test_parses_entries(self, tmp_path):
        md = tmp_path / "micro.md"
        md.write_text("""# Top 20

## #1. AI Agent Monitor
**Composite Score: 89.5**
**The Problem**: Agents fail silently
**Market Size**: $2B

## #2. Data Pipeline Auditor
**Composite Score: 75.0**
**The Problem**: Pipelines break overnight
""")
        seeds = extract_from_micro_saas(md)
        assert len(seeds) == 2
        assert seeds[0].name == "AI Agent Monitor"
        assert seeds[0].composite_score == 89.5
        assert seeds[0].source_type == "micro_saas"
        assert seeds[0].revenue_model == "SaaS subscription"

    def test_missing_file_returns_empty(self, tmp_path):
        assert extract_from_micro_saas(tmp_path / "nope.md") == []


# ---------------------------------------------------------------------------
# extract_from_moonshots
# ---------------------------------------------------------------------------


class TestExtractFromMoonshots:
    def test_parses_scored_entries(self, tmp_path):
        md = tmp_path / "moon.md"
        md.write_text("""# Moonshots

### #1 — Quantum AI Optimizer — Score: 8.5
**Evidence**: DARPA funding + Nature paper

### #2 — Neural Architecture Search — Score: 7.2
First-of-its-kind search tool
""")
        seeds = extract_from_moonshots(md)
        assert len(seeds) == 2
        assert seeds[0].name == "Quantum AI Optimizer"
        assert seeds[0].composite_score == 8.5
        assert seeds[0].source_type == "moonshot"

    def test_missing_file_returns_empty(self, tmp_path):
        assert extract_from_moonshots(tmp_path / "nope.md") == []


# ---------------------------------------------------------------------------
# extract_from_scratch_dir
# ---------------------------------------------------------------------------


class TestExtractFromScratchDir:
    def test_finds_idea_files(self, tmp_path):
        (tmp_path / "idea.md").write_text(
            "# Revenue Pipeline\nBuild a product that monetizes AI agents"
        )
        (tmp_path / "notes.md").write_text(
            "# Meeting Notes\nDiscussed weather and lunch plans"
        )
        seeds = extract_from_scratch_dir(tmp_path)
        assert len(seeds) == 1
        assert seeds[0].name == "Revenue Pipeline"

    def test_missing_dir_returns_empty(self, tmp_path):
        assert extract_from_scratch_dir(tmp_path / "nope") == []

    def test_empty_dir_returns_empty(self, tmp_path):
        (tmp_path / "empty").mkdir()
        assert extract_from_scratch_dir(tmp_path / "empty") == []


# ---------------------------------------------------------------------------
# compute_naff_score
# ---------------------------------------------------------------------------


class TestComputeNaffScore:
    def test_naff_todo_app(self):
        seed = Seed(
            id="x", name="AI Todo App",
            description="Manage your tasks with AI",
            source_file="f", source_type="scratch",
        )
        score = compute_naff_score(seed)
        assert score > 0.5

    def test_unique_project_low_naff(self):
        seed = Seed(
            id="x", name="R_V Metric Dashboard",
            description="dharma_swarm telos gate contraction analysis",
            source_file="f", source_type="core",
        )
        score = compute_naff_score(seed)
        assert score < 0.3

    def test_clamped_to_01(self):
        seed = Seed(
            id="x", name="prompt library chatbot todo app blog generator",
            description="generic template assistant for all",
            source_file="f", source_type="scratch",
            kill_history=5,
        )
        score = compute_naff_score(seed)
        assert 0.0 <= score <= 1.0

    def test_kill_history_increases_naff(self):
        base = Seed(id="x", name="Test", description="A thing", source_file="f", source_type="scratch")
        killed = Seed(id="x", name="Test", description="A thing", source_file="f", source_type="scratch", kill_history=3)
        assert compute_naff_score(killed) > compute_naff_score(base)


# ---------------------------------------------------------------------------
# compute_moat
# ---------------------------------------------------------------------------


class TestComputeMoat:
    def test_no_moat(self):
        seed = Seed(id="x", name="Generic App", description="does stuff", source_file="f", source_type="scratch")
        assert compute_moat(seed) == "No clear moat"

    def test_has_moat(self):
        seed = Seed(id="x", name="R_V Metric Tool", description="dharma_swarm analysis", source_file="f", source_type="core")
        moat = compute_moat(seed)
        assert moat != "No clear moat"
        assert "unique" in moat.lower()


# ---------------------------------------------------------------------------
# grade_seed
# ---------------------------------------------------------------------------


class TestGradeSeed:
    def test_micro_saas_base_score(self):
        seed = Seed(
            id="x", name="Test SaaS", description="A SaaS product",
            source_file="f", source_type="micro_saas",
        )
        graded = grade_seed(seed)
        assert graded.ysd_score >= 20  # At least NAFF+

    def test_scratch_base_score(self):
        seed = Seed(
            id="x", name="Random Idea", description="Something vague",
            source_file="f", source_type="scratch",
        )
        graded = grade_seed(seed)
        assert graded.ysd_score <= 60

    def test_moat_boosts_score(self):
        no_moat = Seed(id="x", name="Generic", description="does stuff", source_file="f", source_type="micro_saas")
        with_moat = Seed(id="y", name="R_V Contraction Analyzer", description="dharma_swarm telos", source_file="f", source_type="micro_saas")
        grade_seed(no_moat)
        grade_seed(with_moat)
        assert with_moat.ysd_score > no_moat.ysd_score

    def test_score_clamped_0_100(self):
        seed = Seed(
            id="x", name="Super Naff Todo App Prompt Library",
            description="generic template chatbot blog generator",
            source_file="f", source_type="scratch",
            kill_history=10,
        )
        graded = grade_seed(seed)
        assert 0 <= graded.ysd_score <= 100

    def test_ysd_display_set(self):
        seed = Seed(id="x", name="Test", description="d", source_file="f", source_type="core")
        graded = grade_seed(seed)
        assert graded.ysd_display.startswith("5.")

    def test_ysd_label_set(self):
        seed = Seed(id="x", name="Test", description="d", source_file="f", source_type="core")
        graded = grade_seed(seed)
        assert len(graded.ysd_label) > 0

    def test_composite_score_positive(self):
        seed = Seed(id="x", name="Test", description="d", source_file="f", source_type="core")
        graded = grade_seed(seed)
        assert graded.composite_score > 0

    def test_built_status_bonus(self):
        raw = Seed(id="x", name="Test", description="d", source_file="f", source_type="micro_saas", status="raw")
        built = Seed(id="y", name="Test", description="d", source_file="f", source_type="micro_saas", status="built")
        grade_seed(raw)
        grade_seed(built)
        assert built.ysd_score > raw.ysd_score
