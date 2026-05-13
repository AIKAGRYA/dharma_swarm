"""Tests for the pure Action Authority Gate model/classifier."""

from __future__ import annotations

from dharma_swarm.action_authority import (
    ActionAuthorityMode,
    AuthoritySurface,
    AuthorityTier,
    build_action_authority_request,
    classify_authority_tier,
    evaluate_action_authority,
    min_evidence_files_for_tier,
)
from dharma_swarm.fourfold_action_warrant import (
    ActionWarrantRequest,
    CapabilityInventory,
    EvidenceItem,
    build_fourfold_action_warrant,
)
from dharma_swarm.models import GateDecision


def _complete_warrant(*, title: str = "Write governance-safe feature"):
    categories = ("root", "code", "tests", "history", "tools")
    evidence = [
        EvidenceItem(
            path=f"{categories[i % len(categories)]}/file_{i}.py",
            category=categories[i % len(categories)],
            theme="authority context",
            why="proves the action was inspected",
        )
        for i in range(50)
    ]
    paragraph = (
        "This warrant connects the proposed action to the current governance "
        "track with enough detail to demonstrate context, risk, and scope. "
        "It is intentionally long enough to satisfy the narrative contract."
    )
    return build_fourfold_action_warrant(
        ActionWarrantRequest(
            title=title,
            description="Write files in the repository with meaningful code mutation.",
            metadata={"is_significant_action": True, "mutates_repo": True},
            evidence=evidence,
            capabilities=CapabilityInventory(skills=["repo-review"]),
            zeitgeist_signal_ids=["sig-1"],
            integrated_vision=paragraph,
            connection_map=paragraph,
            meaningful_action=paragraph,
        )
    )


def test_action_authority_gate_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("DHARMA_ACTION_AUTHORITY_GATE", raising=False)
    request = build_action_authority_request(
        title="Write feature files",
        target_paths=("dharma_swarm/new_feature.py",),
        requested_tools=("write_file",),
    )

    decision = evaluate_action_authority(request)

    assert decision.mode is ActionAuthorityMode.OFF
    assert decision.raw_decision is GateDecision.ALLOW
    assert decision.effective_decision is GateDecision.ALLOW
    assert decision.blocked is False


def test_classifier_identifies_read_only_repo_and_governance_tiers() -> None:
    assert (
        classify_authority_tier(title="Read files", content="Inspect status")
        is AuthorityTier.READ_ONLY
    )
    assert (
        classify_authority_tier(
            title="Edit module",
            target_paths=("dharma_swarm/agent_runner.py",),
            requested_tools=("edit_file",),
        )
        is AuthorityTier.REPO_MUTATION
    )
    assert (
        classify_authority_tier(
            title="Change governance policy",
            target_paths=("docs/governance/POLICY.md",),
        )
        is AuthorityTier.GOVERNANCE_MUTATION
    )


def test_fourfold_evidence_threshold_is_tier_scoped() -> None:
    assert min_evidence_files_for_tier(AuthorityTier.REPO_MUTATION) == 8
    assert min_evidence_files_for_tier(AuthorityTier.EXECUTION) == 8
    assert min_evidence_files_for_tier(AuthorityTier.EXTERNAL_SIDE_EFFECT) == 12
    assert min_evidence_files_for_tier(AuthorityTier.CROSS_AGENT_DISPATCH) == 12
    assert min_evidence_files_for_tier(AuthorityTier.GOVERNANCE_MUTATION) == 50
    assert min_evidence_files_for_tier(AuthorityTier.RELEASE_OR_MAIN) == 50


def test_shadow_missing_warrant_would_block_but_effectively_allows() -> None:
    request = build_action_authority_request(
        title="Write feature files",
        target_paths=("dharma_swarm/new_feature.py",),
        requested_tools=("write_file",),
    )

    decision = evaluate_action_authority(request, mode=ActionAuthorityMode.SHADOW)

    assert decision.raw_decision is GateDecision.BLOCK
    assert decision.effective_decision is GateDecision.ALLOW
    assert decision.would_block is True
    assert decision.blocked is False
    assert "code_mutation" in decision.trigger_reasons


def test_enforce_missing_warrant_blocks_high_authority_action() -> None:
    request = build_action_authority_request(
        title="Write feature files",
        target_paths=("dharma_swarm/new_feature.py",),
        requested_tools=("write_file",),
    )

    decision = evaluate_action_authority(request, mode=ActionAuthorityMode.ENFORCE)

    assert decision.raw_decision is GateDecision.BLOCK
    assert decision.effective_decision is GateDecision.BLOCK
    assert decision.blocked is True
    assert "fourfold action warrant gate" in decision.reason


def test_complete_warrant_allows_high_authority_action() -> None:
    warrant = _complete_warrant()
    request = build_action_authority_request(
        title="Write governance-safe feature",
        content="Write files in the repository with meaningful code mutation.",
        target_paths=("dharma_swarm/new_feature.py",),
        requested_tools=("write_file",),
        fourfold_warrant=warrant,
    )

    decision = evaluate_action_authority(request, mode=ActionAuthorityMode.ENFORCE)

    assert decision.raw_decision is GateDecision.ALLOW
    assert decision.effective_decision is GateDecision.ALLOW
    assert decision.blocked is False
    assert decision.warrant_id == warrant.warrant_id


def test_negative_ptr_can_only_push_allow_to_review() -> None:
    request = build_action_authority_request(
        title="Read current status",
        metadata={
            "ptr_score": {
                "authority_model": "negative_only",
                "verdict": "INSUFFICIENT_EVIDENCE",
                "authoritative": False,
                "caps": ["low_coverage"],
            }
        },
    )

    decision = evaluate_action_authority(request, mode=ActionAuthorityMode.ENFORCE)

    assert decision.raw_decision is GateDecision.REVIEW
    assert decision.effective_decision is GateDecision.REVIEW
    assert decision.blocked is False
    assert decision.warnings == ("ptr_negative_evidence:INSUFFICIENT_EVIDENCE",)


def test_ptr_cannot_override_missing_warrant_block() -> None:
    request = build_action_authority_request(
        title="Write feature files",
        target_paths=("dharma_swarm/new_feature.py",),
        requested_tools=("write_file",),
        metadata={
            "ptr_score": {
                "authority_model": "negative_only",
                "verdict": "PROCEED",
                "authoritative": True,
                "caps": [],
            }
        },
    )

    decision = evaluate_action_authority(request, mode=ActionAuthorityMode.ENFORCE)

    assert decision.raw_decision is GateDecision.BLOCK
    assert decision.effective_decision is GateDecision.BLOCK
    assert decision.blocked is True
