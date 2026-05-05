"""Tests for dharma_swarm.agent_runner_quality — semantic acceptance helpers.

Validates:
- _clamp01: clamping to [0, 1]
- _looks_like_provider_failure: error prefix detection
- CompletionAssessment dataclass
- _dedupe_keep_order: deduplication preserving order
- _normalize_bullet_text: strip bullet markers
- _extract_named_sections: section parsing from content
- _section_items: section item retrieval
- _extract_file_references: file path pattern extraction
- _extract_test_references: test file filtering
- _match_required_references: required vs observed matching
- _extract_meta_observations: system-level observation extraction
"""

from __future__ import annotations

import pytest

from dharma_swarm.agent_runner_quality import (
    CompletionAssessment,
    _clamp01,
    _dedupe_keep_order,
    _extract_file_references,
    _extract_meta_observations,
    _extract_named_sections,
    _extract_test_references,
    _looks_like_provider_failure,
    _match_required_references,
    _normalize_bullet_text,
    _section_items,
)


# ---------------------------------------------------------------------------
# _clamp01
# ---------------------------------------------------------------------------


class TestClamp01:
    def test_within_range(self):
        assert _clamp01(0.5) == 0.5

    def test_below_zero(self):
        assert _clamp01(-0.3) == 0.0

    def test_above_one(self):
        assert _clamp01(1.5) == 1.0

    def test_boundaries(self):
        assert _clamp01(0.0) == 0.0
        assert _clamp01(1.0) == 1.0


# ---------------------------------------------------------------------------
# _looks_like_provider_failure
# ---------------------------------------------------------------------------


class TestLooksLikeProviderFailure:
    def test_empty_is_failure(self):
        assert _looks_like_provider_failure("") is True
        assert _looks_like_provider_failure(None) is True

    def test_error_prefix(self):
        assert _looks_like_provider_failure("error: connection refused") is True

    def test_provider_error(self):
        assert _looks_like_provider_failure("provider error: rate limited") is True

    def test_timeout(self):
        assert _looks_like_provider_failure("timeout: 30s exceeded") is True

    def test_failed_prefix(self):
        assert _looks_like_provider_failure("failed: task execution") is True

    def test_unable_to(self):
        assert _looks_like_provider_failure("unable to reach model") is True

    def test_normal_content_not_failure(self):
        assert _looks_like_provider_failure("The code review found 3 issues") is False

    def test_case_insensitive(self):
        assert _looks_like_provider_failure("Error: something broke") is True


# ---------------------------------------------------------------------------
# CompletionAssessment
# ---------------------------------------------------------------------------


class TestCompletionAssessment:
    def test_construction(self):
        a = CompletionAssessment(accepted=True, quality_score=0.85, reason="Good work")
        assert a.accepted is True
        assert a.quality_score == 0.85
        assert a.reason == "Good work"

    def test_defaults(self):
        a = CompletionAssessment(accepted=False, quality_score=0.1)
        assert a.reason == ""


# ---------------------------------------------------------------------------
# _dedupe_keep_order
# ---------------------------------------------------------------------------


class TestDedupeKeepOrder:
    def test_basic(self):
        assert _dedupe_keep_order(["a", "b", "a", "c"]) == ["a", "b", "c"]

    def test_strips_whitespace(self):
        assert _dedupe_keep_order(["  x ", "x"]) == ["x"]

    def test_filters_empty(self):
        assert _dedupe_keep_order(["", "a", "", "b"]) == ["a", "b"]

    def test_handles_none(self):
        assert _dedupe_keep_order([None, "a"]) == ["a"]

    def test_preserves_order(self):
        assert _dedupe_keep_order(["c", "a", "b", "a"]) == ["c", "a", "b"]


# ---------------------------------------------------------------------------
# _normalize_bullet_text
# ---------------------------------------------------------------------------


class TestNormalizeBulletText:
    def test_dash_bullet(self):
        assert _normalize_bullet_text("- Fix the router") == "Fix the router"

    def test_star_bullet(self):
        assert _normalize_bullet_text("* Add tests") == "Add tests"

    def test_numbered(self):
        assert _normalize_bullet_text("1. First item") == "First item"

    def test_no_bullet(self):
        assert _normalize_bullet_text("Just text") == "Just text"

    def test_empty(self):
        assert _normalize_bullet_text("") == ""

    def test_none(self):
        assert _normalize_bullet_text(None) == ""


# ---------------------------------------------------------------------------
# _extract_named_sections
# ---------------------------------------------------------------------------


class TestExtractNamedSections:
    def test_basic(self):
        content = "Findings:\n- Issue A\n- Issue B\nEvidence:\n- File X"
        sections = _extract_named_sections(content)
        assert "findings" in sections
        assert len(sections["findings"]) == 2
        assert "evidence" in sections

    def test_empty(self):
        assert _extract_named_sections("") == {}

    def test_none(self):
        assert _extract_named_sections(None) == {}

    def test_preserves_content(self):
        content = "Summary:\nThe system is healthy"
        sections = _extract_named_sections(content)
        assert "The system is healthy" in sections["summary"]


# ---------------------------------------------------------------------------
# _section_items
# ---------------------------------------------------------------------------


class TestSectionItems:
    def test_basic(self):
        sections = {"findings": ["- Bug in router", "- Memory leak"]}
        items = _section_items(sections, "Findings")
        assert items == ["Bug in router", "Memory leak"]

    def test_missing_section(self):
        assert _section_items({}, "missing") == []

    def test_filters_empty(self):
        sections = {"data": ["- Valid", "", "  "]}
        items = _section_items(sections, "data")
        assert items == ["Valid"]


# ---------------------------------------------------------------------------
# _extract_file_references
# ---------------------------------------------------------------------------


class TestExtractFileReferences:
    def test_python_files(self):
        content = "See dharma_swarm/router.py and dharma_swarm/cascade.py for details"
        refs = _extract_file_references(content)
        assert "dharma_swarm/router.py" in refs
        assert "dharma_swarm/cascade.py" in refs

    def test_nested_paths(self):
        content = "Modified src/dharma_swarm/models/agent.py"
        refs = _extract_file_references(content)
        assert len(refs) >= 1

    def test_no_refs(self):
        assert _extract_file_references("Just plain text") == []

    def test_deduplicates(self):
        content = "dharma_swarm/foo.py dharma_swarm/foo.py"
        refs = _extract_file_references(content)
        assert refs.count("dharma_swarm/foo.py") == 1

    def test_multiple_extensions(self):
        content = "config.yaml data.json script.sh template.md"
        refs = _extract_file_references(content)
        # These need path separators to match
        assert refs == []


# ---------------------------------------------------------------------------
# _extract_test_references
# ---------------------------------------------------------------------------


class TestExtractTestReferences:
    def test_tests_dir(self):
        content = "See tests/test_router.py for verification"
        refs = _extract_test_references(content)
        assert "tests/test_router.py" in refs

    def test_non_test_excluded(self):
        content = "dharma_swarm/router.py and tests/test_router.py"
        refs = _extract_test_references(content)
        assert "dharma_swarm/router.py" not in refs
        assert "tests/test_router.py" in refs


# ---------------------------------------------------------------------------
# _match_required_references
# ---------------------------------------------------------------------------


class TestMatchRequiredReferences:
    def test_all_matched(self):
        matched, missing = _match_required_references(
            ["dharma_swarm/router.py", "tests/test_router.py"],
            ["dharma_swarm/router.py", "tests/test_router.py"],
            lowered_content="",
        )
        assert len(matched) == 2
        assert len(missing) == 0

    def test_some_missing(self):
        matched, missing = _match_required_references(
            ["file_a.py", "file_b.py", "file_c.py"],
            ["file_a.py"],
            lowered_content="",
        )
        assert "file_a.py" in matched
        assert "file_b.py" in missing

    def test_found_in_content(self):
        matched, missing = _match_required_references(
            ["dharma_swarm/cascade.py"],
            [],
            lowered_content="the dharma_swarm/cascade.py file handles loops",
        )
        assert "dharma_swarm/cascade.py" in matched

    def test_empty_required(self):
        matched, missing = _match_required_references([], ["a", "b"], lowered_content="")
        assert matched == []
        assert missing == []


# ---------------------------------------------------------------------------
# _extract_meta_observations
# ---------------------------------------------------------------------------


class TestExtractMetaObservations:
    def test_detects_system_markers(self):
        content = "The orchestrator is routing tasks efficiently. The feedback loop is stable."
        observations = _extract_meta_observations(content, system_effects=[])
        assert any("orchestrator" in o.lower() for o in observations)

    def test_includes_system_effects(self):
        observations = _extract_meta_observations(
            "Some content",
            system_effects=["Improved throughput by 20%"],
        )
        assert "Improved throughput by 20%" in observations

    def test_no_markers(self):
        observations = _extract_meta_observations("Just a simple report.", system_effects=[])
        assert observations == []
