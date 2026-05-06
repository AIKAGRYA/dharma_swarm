"""Tests for the Fourfold Action Warrant gate."""

from __future__ import annotations

from dharma_swarm.fourfold_action_warrant import (
    ActionWarrantRequest,
    CapabilityInventory,
    EvidenceItem,
    build_fourfold_action_warrant,
    requires_fourfold_warrant,
    trigger_reasons_for_action,
)
from dharma_swarm.models import GateDecision


def _evidence(count: int) -> list[EvidenceItem]:
    categories = ["root", "code", "tests", "history", "tools"]
    return [
        EvidenceItem(
            path=f"/repo/file_{i}.py",
            category=categories[i % len(categories)],
            theme="stage2",
            why="read before action",
        )
        for i in range(count)
    ]


def _capabilities() -> CapabilityInventory:
    return CapabilityInventory(
        skills=["mcp-synergy", "gitnexus-exploring"],
        mcp_tools=["filesystem.read_multiple_files", "github.fetch_pr"],
        plugins=["GitHub"],
        hooks=["pre-commit"],
    )


def test_trigger_reasons_for_governance_action() -> None:
    reasons = trigger_reasons_for_action(
        "Merge governance hook into main",
        "This writes code and changes a policy gate.",
        {"is_significant_action": True, "governance_impact": True},
    )

    assert "significant_action" in reasons
    assert "governance_impact" in reasons
    assert "main_branch_or_release" in reasons
    assert requires_fourfold_warrant(
        "Merge governance hook into main",
        metadata={"governance_impact": True},
    )


def test_required_warrant_blocks_incomplete_manifest() -> None:
    request = ActionWarrantRequest(
        title="Enable autonomous dispatch from S4",
        metadata={"dispatch_authority": True},
        evidence=_evidence(2),
        capabilities=_capabilities(),
        integrated_vision="short",
        connection_map="short",
        meaningful_action="short",
    )

    warrant = build_fourfold_action_warrant(request, min_evidence_files=5)

    assert warrant.required
    assert warrant.decision is GateDecision.BLOCK
    assert any(blocker.startswith("evidence_files<5") for blocker in warrant.blockers)
    assert any(blocker.startswith("missing_warrant_paragraphs") for blocker in warrant.blockers)


def test_complete_manifest_allows_high_authority_action() -> None:
    paragraph = (
        "The action is understood as a bounded S4 consumer change: it improves "
        "strategic sensing without granting dispatch authority or changing the "
        "operator's control path."
    )
    request = ActionWarrantRequest(
        title="Wire read-only governance pressure into S4",
        metadata={"governance_impact": True, "writes_code": True},
        evidence=_evidence(5),
        capabilities=_capabilities(),
        zeitgeist_signal_ids=["sig-a"],
        integrated_vision=paragraph,
        connection_map=paragraph.replace("S4", "S3/S4"),
        meaningful_action=paragraph.replace("strategic sensing", "test-covered artifacts"),
    )

    warrant = build_fourfold_action_warrant(request, min_evidence_files=5)

    assert warrant.required
    assert warrant.decision is GateDecision.ALLOW
    assert warrant.allowed
    assert warrant.evidence_count == 5
    assert set(warrant.evidence_categories) == {"root", "code", "tests", "history", "tools"}


def test_non_authority_action_does_not_require_warrant() -> None:
    request = ActionWarrantRequest(
        title="Read the operator note",
        description="No code mutation, no dispatch, no external tools.",
    )

    warrant = build_fourfold_action_warrant(request)

    assert not warrant.required
    assert warrant.decision is GateDecision.ALLOW
