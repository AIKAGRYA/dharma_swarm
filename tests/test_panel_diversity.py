"""Tests for the panel-diversity provenance gate.

Includes a regression test that reproduces this module's own origin story:
a 4-lens review panel where every lens actually dispatched to the same
provider (Claude) must be flagged as single_model_multi_persona, never
genuine_diversity — regardless of how much the lenses' verdicts disagreed.
"""

from __future__ import annotations

from dharma_swarm.coordination.panel_diversity import (
    LensAssignment,
    assign_diverse_lenses,
    check_panel_diversity,
)
from dharma_swarm.models import ProviderType


def test_same_provider_every_lens_fails_closed() -> None:
    # Reproduces the exact origin case: 4 role-prompted lenses, one provider.
    assignments = tuple(
        LensAssignment(role=role, provider=ProviderType.CLAUDE_CODE)
        for role in ("skeptic", "builder", "strategist", "diversity_auditor")
    )
    report = check_panel_diversity(assignments)
    assert report.verdict == "single_model_multi_persona"
    assert report.safe_to_trust_consensus is False
    assert report.distinct_provider_count == 1
    assert report.meets_family_floor is False


def test_two_or_more_distinct_providers_meets_floor() -> None:
    assignments = (
        LensAssignment(role="skeptic", provider=ProviderType.OLLAMA),
        LensAssignment(role="builder", provider=ProviderType.CEREBRAS),
        LensAssignment(role="strategist", provider=ProviderType.CLAUDE_CODE),
    )
    report = check_panel_diversity(assignments)
    assert report.meets_family_floor is True
    assert report.distinct_provider_count == 3
    assert report.verdict == "genuine_diversity"
    assert report.safe_to_trust_consensus is True
    assert report.distinct_model_family_count == 3


def test_two_provider_lanes_with_one_model_family_fail_floor() -> None:
    assignments = (
        LensAssignment(role="api", provider=ProviderType.ANTHROPIC),
        LensAssignment(role="cli", provider=ProviderType.CLAUDE_CODE),
    )
    report = check_panel_diversity(assignments)
    assert report.distinct_provider_count == 2
    assert report.model_families_used == ("claude",)
    assert report.meets_family_floor is False
    assert report.verdict == "single_model_multi_persona"


def test_hosted_lanes_with_same_default_family_fail_floor() -> None:
    assignments = (
        LensAssignment(role="a", provider=ProviderType.SILICONFLOW),
        LensAssignment(role="b", provider=ProviderType.TOGETHER),
        LensAssignment(role="c", provider=ProviderType.FIREWORKS),
    )
    report = check_panel_diversity(assignments)
    assert report.distinct_provider_count == 3
    assert report.model_families_used == ("qwen3-coder",)
    assert report.verdict == "single_model_multi_persona"


def test_empty_assignments_is_insufficient_data_not_a_crash() -> None:
    report = check_panel_diversity(())
    assert report.verdict == "insufficient_data"
    assert report.safe_to_trust_consensus is False
    assert report.distinct_provider_count == 0


def test_diverse_providers_but_convergent_phrasing_is_flagged() -> None:
    # Real provider diversity, but near-identical reasoning text -- the
    # "one lens's template became another's" memetic-drift signature.
    assignments = (
        LensAssignment(role="skeptic", provider=ProviderType.OLLAMA),
        LensAssignment(role="builder", provider=ProviderType.CEREBRAS),
    )
    shared_text = (
        "this proposal introduces significant risk to the existing "
        "governance floor and should not proceed without further review "
        "of the downstream consequences for the active track portfolio"
    )
    reasoning = {"skeptic": shared_text, "builder": shared_text}
    report = check_panel_diversity(assignments, reasoning_by_role=reasoning)
    assert report.suspected_memetic_drift is True
    assert report.verdict == "insufficient_data"
    assert report.safe_to_trust_consensus is False
    assert ("builder", "skeptic") in report.overlapping_role_pairs


def test_diverse_providers_and_distinct_reasoning_is_genuine() -> None:
    assignments = (
        LensAssignment(role="skeptic", provider=ProviderType.OLLAMA),
        LensAssignment(role="builder", provider=ProviderType.CEREBRAS),
    )
    reasoning = {
        "skeptic": "the correctness gate cannot apply here because no ground truth exists yet for this class of claim",
        "builder": "the smallest MVP reuses the existing movement clustering and only needs a rolling window state file",
    }
    report = check_panel_diversity(assignments, reasoning_by_role=reasoning)
    assert report.suspected_memetic_drift is False
    assert report.verdict == "genuine_diversity"
    assert report.safe_to_trust_consensus is True


def test_assign_diverse_lenses_gives_each_role_a_distinct_provider_when_possible() -> None:
    roles = ("skeptic", "builder", "strategist", "diversity_auditor")
    candidates = (ProviderType.OLLAMA, ProviderType.CEREBRAS, ProviderType.CLAUDE_CODE, ProviderType.GOOGLE_AI)
    assignments = assign_diverse_lenses(roles, candidate_providers=candidates)
    assert len(assignments) == 4
    assert {a.provider for a in assignments} == set(candidates)
    report = check_panel_diversity(assignments)
    assert report.verdict == "genuine_diversity"


def test_assign_diverse_lenses_rejects_empty_candidate_pool() -> None:
    try:
        assign_diverse_lenses(("skeptic",), candidate_providers=())
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_more_roles_than_providers_wraps_and_gate_catches_underdiversity() -> None:
    roles = ("a", "b", "c")
    candidates = (ProviderType.CLAUDE_CODE,)  # only one lane available
    assignments = assign_diverse_lenses(roles, candidate_providers=candidates)
    report = check_panel_diversity(assignments)
    assert report.verdict == "single_model_multi_persona"
