"""PolicyCompiler integration for the Fourfold Action Warrant runtime gate."""

from __future__ import annotations

from dharma_swarm.fourfold_action_warrant import (
    ActionWarrantRequest,
    CapabilityInventory,
    EvidenceItem,
    build_fourfold_action_warrant,
)
from dharma_swarm.models import GateDecision
from dharma_swarm.policy_compiler import (
    FOURFOLD_ACTION_WARRANT_GATE_ENV,
    FOURFOLD_ACTION_WARRANT_METADATA_KEY,
    FOURFOLD_ACTION_WARRANT_RULE_SOURCE,
    Policy,
)


def _evidence(count: int = 50) -> list[EvidenceItem]:
    categories = ["root", "code", "tests", "history", "tools"]
    return [
        EvidenceItem(
            path=f"/repo/context_{idx}.py",
            category=categories[idx % len(categories)],
            theme="policy compiler runtime gate",
            why="prove the agent read enough surfaces before action",
        )
        for idx in range(count)
    ]


def _capabilities() -> CapabilityInventory:
    return CapabilityInventory(
        skills=["mcp-synergy", "gitnexus-exploring"],
        mcp_tools=["contextplus.semantic_code_search", "github.pull_request"],
        plugins=["GitHub"],
        hooks=["pre-commit"],
    )


def _paragraph(subject: str) -> str:
    return (
        f"{subject} is bounded as a policy-compiler runtime change: it links "
        "the action metadata contract to an explicit warrant without granting "
        "autonomous dispatch or changing default behavior for ordinary actions."
    )


def _allowing_warrant() -> dict[str, object]:
    request = ActionWarrantRequest(
        title="Merge governance policy into main",
        description="This changes a policy gate for significant repo actions.",
        metadata={"is_significant_action": True, "governance_impact": True},
        evidence=_evidence(),
        capabilities=_capabilities(),
        zeitgeist_signal_ids=["sig-policy-1"],
        integrated_vision=_paragraph("Vision"),
        connection_map=_paragraph("Connection"),
        meaningful_action=_paragraph("Action"),
    )
    warrant = build_fourfold_action_warrant(request)
    assert warrant.decision is GateDecision.ALLOW
    return warrant.model_dump(mode="json")


def test_fourfold_gate_disabled_by_default() -> None:
    policy = Policy()

    decision = policy.check_action(
        "Merge governance policy into main",
        action_metadata={"is_significant_action": True, "governance_impact": True},
    )

    assert decision.allowed is True
    assert decision.violated_rules == []


def test_fourfold_gate_blocks_missing_warrant_when_enabled() -> None:
    policy = Policy()

    decision = policy.check_action(
        "Merge governance policy into main",
        action_metadata={"is_significant_action": True, "governance_impact": True},
        enforce_fourfold_warrant=True,
    )

    assert decision.allowed is False
    assert decision.violated_rules[0].source == FOURFOLD_ACTION_WARRANT_RULE_SOURCE
    assert "missing_fourfold_action_warrant" in decision.reason
    assert "significant_action" in decision.reason


def test_fourfold_gate_blocks_non_allowing_warrant() -> None:
    policy = Policy()
    request = ActionWarrantRequest(
        title="Merge governance policy into main",
        description="This changes a policy gate for significant repo actions.",
        metadata={"is_significant_action": True, "governance_impact": True},
        evidence=_evidence(2),
        capabilities=_capabilities(),
        integrated_vision="short",
        connection_map="short",
        meaningful_action="short",
    )
    blocked = build_fourfold_action_warrant(request)
    assert blocked.decision is GateDecision.BLOCK

    decision = policy.check_action(
        "Merge governance policy into main",
        action_metadata={
            "is_significant_action": True,
            "governance_impact": True,
            FOURFOLD_ACTION_WARRANT_METADATA_KEY: blocked.model_dump(mode="json"),
        },
        enforce_fourfold_warrant=True,
    )

    assert decision.allowed is False
    assert "fourfold_action_warrant_block" in decision.reason
    assert "evidence_files<50" in decision.reason


def test_fourfold_gate_allows_complete_warrant() -> None:
    policy = Policy()

    decision = policy.check_action(
        "Merge governance policy into main",
        action_metadata={
            "is_significant_action": True,
            "governance_impact": True,
            FOURFOLD_ACTION_WARRANT_METADATA_KEY: _allowing_warrant(),
        },
        enforce_fourfold_warrant=True,
    )

    assert decision.allowed is True
    assert decision.violated_rules == []


def test_fourfold_gate_can_be_enabled_by_environment(monkeypatch) -> None:
    policy = Policy()
    monkeypatch.setenv(FOURFOLD_ACTION_WARRANT_GATE_ENV, "1")

    decision = policy.check_action(
        "Merge governance policy into main",
        action_metadata={"is_significant_action": True},
    )

    assert decision.allowed is False
    assert "fourfold action warrant gate" in decision.reason
