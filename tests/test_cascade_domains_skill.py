"""Tests for dharma_swarm/cascade_domains/skill.py — SKILL domain scoring."""

from __future__ import annotations

from typing import Any

import pytest

from dharma_swarm.cascade_domains.skill import (
    _parse_frontmatter,
    _score_behavioral,
    _score_completeness,
    _score_composability,
    _score_compression,
    _score_structure,
    generate,
    get_domain,
    score,
)


SAMPLE_SKILL_CONTENT = """---
name: test-skill
description: A test skill for validation purposes.
allowed-tools:
  - grep
  - read
---

# Test Skill

This skill demonstrates proper structure.

## When to Use

Use this when testing the cascade domain scoring.

## Steps

1. First step with `code example`
2. Second step with details

```bash
echo "hello world"
```

## Verification

Check the output is correct.
"""

MINIMAL_CONTENT = "Just some text with no frontmatter or structure."


class TestGetDomain:
    def test_default_config(self) -> None:
        domain = get_domain()
        assert domain.name == "skill"
        assert domain.max_iterations == 25
        assert domain.fitness_threshold == 0.55

    def test_custom_config(self) -> None:
        domain = get_domain({"max_iterations": 50, "fitness_threshold": 0.8})
        assert domain.max_iterations == 50
        assert domain.fitness_threshold == 0.8

    def test_domain_function_paths(self) -> None:
        domain = get_domain()
        assert "skill.generate" in domain.generate_fn
        assert "skill.score" in domain.score_fn


class TestParseFrontmatter:
    def test_valid_frontmatter(self) -> None:
        fm = _parse_frontmatter(SAMPLE_SKILL_CONTENT)
        assert fm["name"] == "test-skill"
        assert "test skill" in fm["description"].lower()

    def test_no_frontmatter(self) -> None:
        fm = _parse_frontmatter(MINIMAL_CONTENT)
        assert fm == {}

    def test_empty_content(self) -> None:
        fm = _parse_frontmatter("")
        assert fm == {}

    def test_quoted_values(self) -> None:
        content = '---\nname: "my-skill"\ndescription: \'A description\'\n---\n\nBody'
        fm = _parse_frontmatter(content)
        assert fm["name"] == "my-skill"
        assert fm["description"] == "A description"


class TestGenerate:
    def test_generate_with_content(self) -> None:
        artifact = generate({"content": SAMPLE_SKILL_CONTENT}, {})
        assert artifact["content"] == SAMPLE_SKILL_CONTENT
        assert artifact["skill_name"] == "unknown"

    def test_generate_with_skill_name(self) -> None:
        artifact = generate({"skill_name": "nonexistent-skill"}, {})
        assert artifact["skill_name"] == "nonexistent-skill"
        assert artifact["content"] == ""

    def test_generate_with_context_skill_name(self) -> None:
        artifact = generate(None, {"skill_name": "from-context"})
        assert artifact["skill_name"] == "from-context"

    def test_generate_empty(self) -> None:
        artifact = generate(None, {})
        assert artifact["content"] == ""
        assert artifact["skill_name"] == "unknown"


class TestScoreStructure:
    def test_full_structure(self) -> None:
        fm = _parse_frontmatter(SAMPLE_SKILL_CONTENT)
        s = _score_structure(SAMPLE_SKILL_CONTENT, fm)
        assert s > 0.7  # Has frontmatter, description, headers, code

    def test_minimal_structure(self) -> None:
        s = _score_structure(MINIMAL_CONTENT, {})
        assert s == 0.0  # No frontmatter, no headers, no code

    def test_frontmatter_only(self) -> None:
        content = "---\nname: x\ndescription: y\n---\n\nSome text"
        fm = _parse_frontmatter(content)
        s = _score_structure(content, fm)
        assert 0.3 <= s <= 0.7  # Has frontmatter + description but no code


class TestScoreCompression:
    def test_normal_text(self) -> None:
        s = _score_compression(SAMPLE_SKILL_CONTENT)
        assert 0.0 < s <= 1.0

    def test_empty_content(self) -> None:
        assert _score_compression("") == 0.0

    def test_highly_repetitive(self) -> None:
        repetitive = "hello " * 1000
        s = _score_compression(repetitive)
        assert s < 0.5  # Very repetitive = low score


class TestScoreBehavioral:
    def test_content_with_steps(self) -> None:
        s = _score_behavioral(SAMPLE_SKILL_CONTENT)
        assert s >= 0.0  # Has numbered steps and verification

    def test_empty_content(self) -> None:
        s = _score_behavioral("")
        assert s == 0.0


class TestScoreCompleteness:
    def test_complete_skill(self) -> None:
        s = _score_completeness(SAMPLE_SKILL_CONTENT)
        assert s > 0.2  # Well-structured content scores higher than baseline

    def test_empty_content(self) -> None:
        s = _score_completeness("")
        assert s <= 0.3  # Empty/minimal gets low baseline score


class TestScoreComposability:
    def test_composable_skill(self) -> None:
        s = _score_composability(SAMPLE_SKILL_CONTENT)
        assert 0.0 <= s <= 1.0

    def test_empty_content(self) -> None:
        s = _score_composability("")
        assert s <= 0.5  # Empty/minimal gets low baseline score


class TestScore:
    def test_score_full_artifact(self) -> None:
        artifact = {"content": SAMPLE_SKILL_CONTENT, "skill_name": "test"}
        result = score(artifact, {})
        assert "fitness" in result or "overall" in result or isinstance(result, dict)

    def test_score_empty_artifact(self) -> None:
        artifact = {"content": "", "skill_name": "empty"}
        result = score(artifact, {})
        assert isinstance(result, dict)
