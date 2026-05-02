"""Schema-only tests for the Phase-1 inquiry chain.

Verifies that Signal, Question, Evidence ObjectTypes register,
that AgentIdentity gained the is_principal field non-destructively,
and that the inquiry-chain LinkDefs auto-register their inverses.

These tests do NOT instantiate runtime rows — Phase-1 schema only.
Runtime tests for ObserveSignal/AssertClaim/AttachEvidence land
when the seam wiring lands in a follow-up commit.
"""

from __future__ import annotations

import pytest

from dharma_swarm.ontology import OntologyRegistry, PropertyType


@pytest.fixture
def registry() -> OntologyRegistry:
    return OntologyRegistry.create_dharma_registry()


# ── Signal / Question / Evidence presence ─────────────────────────────────────


@pytest.mark.parametrize("type_name,required_props,actions", [
    ("Signal",
     {"signal_id", "source", "captured_at", "payload", "observer_ref"},
     {"ObserveSignal"}),
    ("Question",
     {"question_id", "text", "opener_ref", "opened_at", "lifecycle_state"},
     {"AskQuestion", "AnswerQuestion", "AbandonQuestion"}),
    ("Evidence",
     {"evidence_id", "claim_ref", "kind", "direction", "attached_at", "attached_by_ref"},
     {"AttachEvidence"}),
])
def test_inquiry_type_registered(registry, type_name, required_props, actions):
    obj_type = registry.get_type(type_name)
    assert obj_type is not None, f"{type_name} not registered"

    actual_required = {n for n, p in obj_type.properties.items() if p.required}
    assert required_props.issubset(actual_required), (
        f"{type_name} missing required fields: "
        f"{required_props - actual_required}"
    )

    actual_actions = {a.name for a in obj_type.actions}
    assert actions.issubset(actual_actions), (
        f"{type_name} missing actions: {actions - actual_actions}"
    )


def test_signal_observe_action_gates_ahimsa(registry):
    sig = registry.get_type("Signal")
    observe = next(a for a in sig.actions if a.name == "ObserveSignal")
    assert "AHIMSA" in observe.telos_gates, (
        "ObserveSignal must gate AHIMSA on payload"
    )


def test_evidence_attach_action_gates_satya(registry):
    ev = registry.get_type("Evidence")
    attach = next(a for a in ev.actions if a.name == "AttachEvidence")
    assert "SATYA" in attach.telos_gates, (
        "AttachEvidence must gate SATYA"
    )


# ── AgentIdentity.is_principal field (additive, default=False) ────────────────


def test_agent_identity_is_principal_present(registry):
    ai = registry.get_type("AgentIdentity")
    assert "is_principal" in ai.properties
    p = ai.properties["is_principal"]
    assert p.property_type == PropertyType.BOOLEAN
    assert p.default is False, (
        "is_principal must default to False so existing rows are non-destructively "
        "treated as non-principal"
    )
    assert p.required is False, (
        "is_principal must be optional; required=True would invalidate the 23 "
        "existing AgentIdentity rows in the live DB"
    )


# ── Inquiry-chain LinkDefs auto-register inverses ─────────────────────────────


@pytest.mark.parametrize("link_name,source,target", [
    ("observed_by", "Signal", "AgentIdentity"),
    ("opens_question", "Signal", "Question"),
    ("opened_by", "Question", "AgentIdentity"),
    ("answered_by_claim", "Question", "Claim"),
    ("claim_proposed_by", "Claim", "AgentIdentity"),
    ("claim_has_evidence", "Claim", "Evidence"),
    ("evidence_from_artifact", "Evidence", "KnowledgeArtifact"),
])
def test_inquiry_linkdef_registered(registry, link_name, source, target):
    links = registry.get_links_for(source)
    matching = [l for l in links if l.name == link_name]
    assert len(matching) == 1, (
        f"LinkDef {link_name} ({source} -> {target}) not registered"
    )
    assert matching[0].target_type == target


def test_inquiry_linkdefs_have_inverses(registry):
    """Each new LinkDef must auto-register an inverse so traversal works both ways."""
    expected_inverses = {
        "observed_signals", "opened_by_signal", "opened_questions",
        "answers_question", "proposed_claims", "evidences_claim",
        "evidence_uses",
    }
    all_link_names = set()
    for tn in registry.type_names():
        for l in registry.get_links_for(tn):
            all_link_names.add(l.name)
    missing = expected_inverses - all_link_names
    assert not missing, f"Inverse links not auto-registered: {missing}"


# ── Net registry shape ────────────────────────────────────────────────────────


def test_total_type_count_after_inquiry_additions(registry):
    """Sanity check: 16 original + 6 spec-style adds + 3 inquiry adds = 25."""
    assert len(registry.type_names()) >= 25
    for required in ("Signal", "Question", "Evidence", "Claim", "Doctrine",
                     "AgentIdentity", "Outcome", "ValueEvent", "WitnessLog",
                     "KnowledgeArtifact"):
        assert registry.get_type(required) is not None
