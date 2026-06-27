"""Regression tests for scripts/governance/loop/scoper.py glob matching.

These tests close the gap that let the broken hand-rolled ``_match_glob`` ship:
none of the original 14 scoper tests asserted that a *subdirectory* file maps
to its expected diff-mapped prompts. The hand-rolled regex converter had two
compounding bugs that made every ``**`` and ``*`` wildcard entry silently fail
to match any real file path, so a changed file in a subdirectory mapped to ZERO
prompts — defeating the scoper's core purpose (VAL-SCOPE-002).

The fix replaces the hand-rolled regex with ``fnmatch.fnmatchcase`` (stdlib).
These tests pin that fix: every wildcard entry in ``FILE_TO_PROMPTS`` must match
a real subdirectory path, and ``map_file_to_prompts`` must return the expected
prompts for subdirectory files (not an empty list).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def scoper():
    sys.path.insert(0, str(REPO_ROOT))
    import importlib

    mod = importlib.import_module("scripts.governance.loop.scoper")
    importlib.reload(mod)
    return mod


# ---------------------------------------------------------------------------
# Every wildcard entry in FILE_TO_PROMPTS must match a real subdirectory path
# ---------------------------------------------------------------------------

# (pattern, representative_real_path). Covers all 11 wildcard entries.
WILDCARD_MATCH_CASES: list[tuple[str, str]] = [
    ("tests/**", "tests/test_x.py"),
    ("tests/**", "tests/governance/loop/test_scoper.py"),
    ("dharma_swarm/spine/**", "dharma_swarm/spine/routing.py"),
    ("dharma_swarm/spine/**", "dharma_swarm/spine/sub/deep.py"),
    ("dharma_swarm/provider_*.py", "dharma_swarm/provider_policy.py"),
    ("dharma_swarm/a2a/**", "dharma_swarm/a2a/a2a_bridge.py"),
    ("dharma_swarm/memory_kernel/**", "dharma_swarm/memory_kernel/kernel.py"),
    ("dharma_swarm/council/**", "dharma_swarm/council/profiles.py"),
    ("scripts/governance/hygiene/**", "scripts/governance/hygiene/ratchet.py"),
    ("scripts/governance/**", "scripts/governance/check_import_provenance.py"),
    (".github/workflows/**", ".github/workflows/ci.yml"),
    ("docs/governance/**", "docs/governance/ACTIVE_TRACK.yaml"),
    ("dharma_swarm/**/*.py", "dharma_swarm/spine/foo.py"),
]


@pytest.mark.parametrize("pattern, path", WILDCARD_MATCH_CASES)
def test_wildcard_pattern_matches_subdirectory_path(scoper, pattern, path):
    """Each wildcard entry in FILE_TO_PROMPTS matches a real subdirectory path.

    This is the core regression: the old hand-rolled regex returned False for
    every one of these (``**`` collapsed to a bare ``*`` quantifier on the
    preceding char; ``*`` produced ``[!/]*`` where ``!`` is not regex negation).
    """
    assert scoper._match_glob(pattern, path), (
        f"wildcard pattern {pattern!r} failed to match real path {path!r}"
    )


def test_all_wildcard_file_to_prompts_entries_have_a_matching_path(scoper):
    """Every entry in FILE_TO_PROMPTS that contains a wildcard character must
    match at least one constructed subdirectory path — no silent dead entries."""
    wildcard_entries = [
        (pat, pids)
        for pat, pids in scoper.FILE_TO_PROMPTS
        if "*" in pat or "?" in pat
    ]
    assert wildcard_entries, "expected at least one wildcard entry in FILE_TO_PROMPTS"

    for pattern, prompt_ids in wildcard_entries:
        # Construct a representative path from the pattern by replacing the
        # first '**' with 'sub/file.py' and '*' with 'x'.
        sample = pattern.replace("**", "sub/file.py", 1).replace("*", "x", 1)
        # If no '**' was present, the '*' replacement already produced a path;
        # ensure it still has a file-like suffix.
        if "." not in sample.split("/")[-1]:
            sample = sample + ".py"
        assert scoper._match_glob(pattern, sample), (
            f"wildcard entry {pattern!r} (prompts {prompt_ids}) matched no path; "
            f"sample tried: {sample!r}"
        )


# ---------------------------------------------------------------------------
# Subdirectory files map to their expected diff-mapped prompts (not empty)
# ---------------------------------------------------------------------------


def test_tests_subdirectory_file_maps_to_tests_prompts(scoper):
    """tests/test_x.py maps to the tests/** prompts (TV-01, TV-02, TV-06, TV-07).

    This is the canonical example from the bug report: the old code returned []
    for any file under tests/.
    """
    pids = scoper.map_file_to_prompts("tests/test_x.py")
    expected = {"TV-01", "TV-02", "TV-06", "TV-07"}
    assert expected.issubset(set(pids)), (
        f"tests/test_x.py should map to at least {expected}, got {pids}"
    )
    assert len(pids) > 0, "subdirectory file mapped to ZERO prompts (the bug)"


def test_spine_subdirectory_file_maps_to_spine_prompts(scoper):
    """dharma_swarm/spine/foo.py maps to the spine prompts (TV-08, RDR-01, RDR-04)."""
    pids = scoper.map_file_to_prompts("dharma_swarm/spine/foo.py")
    expected = {"TV-08", "RDR-01", "RDR-04"}
    assert expected.issubset(set(pids)), (
        f"dharma_swarm/spine/foo.py should map to at least {expected}, got {pids}"
    )
    assert len(pids) > 0, "subdirectory file mapped to ZERO prompts (the bug)"


def test_a2a_subdirectory_file_maps_to_a2a_prompts(scoper):
    """dharma_swarm/a2a/a2a_bridge.py maps to the a2a prompts (RDR-03, APS-03)."""
    pids = scoper.map_file_to_prompts("dharma_swarm/a2a/a2a_bridge.py")
    expected = {"RDR-03", "APS-03"}
    assert expected.issubset(set(pids)), (
        f"dharma_swarm/a2a/a2a_bridge.py should map to at least {expected}, got {pids}"
    )
    assert len(pids) > 0, "subdirectory file mapped to ZERO prompts (the bug)"


def test_deeply_nested_subdirectory_file_maps_to_prompts(scoper):
    """A deeply nested file still maps (tests/governance/loop/test_x.py -> tests/**)."""
    pids = scoper.map_file_to_prompts("tests/governance/loop/test_x.py")
    expected = {"TV-01", "TV-02", "TV-06", "TV-07"}
    assert expected.issubset(set(pids)), (
        f"deeply nested tests file should map to {expected}, got {pids}"
    )


def test_governance_hygiene_subdirectory_maps_to_prompts(scoper):
    """scripts/governance/hygiene/ratchet.py maps to the hygiene prompts (GEF-02, GEF-08).

    Also matches scripts/governance/** (GEF-02), so GEF-02 is a subset check.
    """
    pids = scoper.map_file_to_prompts("scripts/governance/hygiene/ratchet.py")
    expected = {"GEF-02", "GEF-08"}
    assert expected.issubset(set(pids)), (
        f"scripts/governance/hygiene/ratchet.py should map to at least {expected}, got {pids}"
    )


def test_workflows_subdirectory_maps_to_prompts(scoper):
    """.github/workflows/ci.yml maps to the workflow prompts (GEF-07, GEF-02)."""
    pids = scoper.map_file_to_prompts(".github/workflows/ci.yml")
    expected = {"GEF-07", "GEF-02"}
    assert expected.issubset(set(pids)), (
        f".github/workflows/ci.yml should map to at least {expected}, got {pids}"
    )


def test_literal_path_still_matches(scoper):
    """Literal-path entries (no wildcards) still match exactly (no regression)."""
    pids = scoper.map_file_to_prompts("dharma_swarm/providers.py")
    # Literal entry: dharma_swarm/providers.py -> RDR-06, APS-09
    # Also matches dharma_swarm/provider_*.py -> RDR-06
    assert "RDR-06" in pids, f"literal providers.py should map to RDR-06, got {pids}"
    assert "APS-09" in pids, f"literal providers.py should map to APS-09, got {pids}"


def test_non_matching_path_returns_empty(scoper):
    """A path that matches no entry returns an empty list (negative control)."""
    pids = scoper.map_file_to_prompts("completely/unrelated/path.md")
    assert pids == [], f"unrelated path should map to no prompts, got {pids}"


# ---------------------------------------------------------------------------
# select_prompts integrates the fix: subdirectory diff produces diff-mapped prompts
# ---------------------------------------------------------------------------


ALL_COUNCILS = [
    "testing_verification",
    "architecture_complexity",
    "runtime_distributed_reliability",
    "ai_slop_prompt_security",
    "governance_evidence_fitness",
]


def test_select_prompts_subdirectory_diff_nonempty(scoper):
    """VAL-SCOPE-002: a diff of only subdirectory files produces non-empty
    diff-mapped prompts (the bug made this empty)."""
    scope = scoper.select_prompts(
        changed_files=["tests/test_x.py", "dharma_swarm/spine/foo.py"],
        warrant_councils=list(ALL_COUNCILS),
    )
    assert len(scope["diff_mapped_prompt_ids"]) > 0, (
        "subdirectory-only diff produced zero diff-mapped prompts (the bug)"
    )
    # rationale references the subdirectory files with non-empty prompt_ids
    for entry in scope["rationale"]:
        if entry["file"] in ("tests/test_x.py", "dharma_swarm/spine/foo.py"):
            assert len(entry["prompt_ids"]) > 0, (
                f"rationale for {entry['file']} is empty (the bug)"
            )
