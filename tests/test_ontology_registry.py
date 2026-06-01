"""Tests for the Palantir-grade typed ontology layer."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dharma_swarm.ontology import (
    Link,
    LinkDef,
    ObjectType,
    OntologyObj,
    OntologyRegistry,
    PropertyDef,
    PropertyType,
    ShaktiEnergy,
    TypeStatus,
    check_security,
    validate_link,
    validate_object,
    # Legacy API
    ONTOLOGY,
    blocked_entities,
    deadline_pressure,
    deadline_summary,
    entities_by_type,
    entity_context,
    entity_graph,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def registry() -> OntologyRegistry:
    return OntologyRegistry.create_dharma_registry()


@pytest.fixture
def populated_registry(registry: OntologyRegistry) -> OntologyRegistry:
    """Registry with sample objects and links."""
    thread, _ = registry.create_object("ResearchThread", {
        "name": "mechanistic", "domain": "mechanistic",
        "status": "active", "priority": 0.9,
    })
    exp, _ = registry.create_object("Experiment", {
        "name": "L27 causal", "status": "running",
        "model": "mistral-7b", "r_v_value": 0.72,
    })
    agent, _ = registry.create_object("AgentIdentity", {
        "name": "researcher-01", "role": "researcher",
    })
    artifact, _ = registry.create_object("KnowledgeArtifact", {
        "title": "Patching results", "artifact_type": "result",
        "domain": "mech_interp", "verified": True,
    })
    task, _ = registry.create_object("TypedTask", {
        "title": "Run pipeline", "status": "pending",
        "priority": "high", "task_type": "experiment",
    })
    registry.create_link("has_experiment", thread.id, exp.id)
    registry.create_link("produces", exp.id, artifact.id)
    registry.create_link("assigned_to", task.id, agent.id)
    return registry


# ── Registry Factory ────────────────────────────────────────────────


class TestRegistryFactory:
    def test_create_dharma_registry(self, registry: OntologyRegistry) -> None:
        stats = registry.stats()
        assert stats["registered_types"] == 21  # 16 core + 5 revenue
        assert stats["registered_links"] >= 40  # 12+8 defs, each with inverse
        assert stats["registered_actions"] >= 16

    def test_all_type_names(self, registry: OntologyRegistry) -> None:
        names = registry.type_names()
        expected = [
            "ActionProposal", "AgentIdentity", "ComputeReinvestment",
            "Contribution", "CustodianRole", "EvolutionEntry",
            "ExecutionLease", "Experiment", "GateDecisionRecord",
            "KnowledgeArtifact", "Outcome", "Paper", "ResearchThread",
            "RevenueEngagement", "RevenueOffer", "RevenueOutreachDraft",
            "RevenueTarget", "TypedTask", "ValueEvent", "VentureCell",
            "WitnessLog",
        ]
        assert names == expected

    def test_each_type_has_properties(self, registry: OntologyRegistry) -> None:
        for obj_type in registry.get_types():
            assert len(obj_type.properties) > 0, f"{obj_type.name} has no properties"

    def test_each_type_has_telos(self, registry: OntologyRegistry) -> None:
        for obj_type in registry.get_types():
            assert 0.0 <= obj_type.telos_alignment <= 1.0


# ── Object CRUD ─────────────────────────────────────────────────────


class TestObjectCRUD:
    def test_create_valid_object(self, registry: OntologyRegistry) -> None:
        obj, errs = registry.create_object("Experiment", {
            "name": "test", "status": "designed",
        })
        assert obj is not None
        assert errs == []
        assert obj.type_name == "Experiment"
        assert obj.properties["name"] == "test"

    def test_create_missing_required(self, registry: OntologyRegistry) -> None:
        obj, errs = registry.create_object("Experiment", {"status": "designed"})
        assert obj is None
        assert any("required" in e for e in errs)

    def test_create_invalid_enum(self, registry: OntologyRegistry) -> None:
        obj, errs = registry.create_object("Experiment", {
            "name": "test", "status": "nonexistent",
        })
        assert obj is None
        assert any("enum" in e for e in errs)

    def test_create_unknown_type(self, registry: OntologyRegistry) -> None:
        obj, errs = registry.create_object("FakeType", {})
        assert obj is None
        assert any("unknown" in e for e in errs)

    def test_get_object(self, registry: OntologyRegistry) -> None:
        obj, _ = registry.create_object("WitnessLog", {
            "observation": "test", "observer": "test-agent",
        })
        found = registry.get_object(obj.id)
        assert found is not None
        assert found.id == obj.id

    def test_get_objects_by_type(self, registry: OntologyRegistry) -> None:
        registry.create_object("WitnessLog", {
            "observation": "a", "observer": "agent-1",
        })
        registry.create_object("WitnessLog", {
            "observation": "b", "observer": "agent-2",
        })
        logs = registry.get_objects_by_type("WitnessLog")
        assert len(logs) == 2

    def test_update_valid(self, registry: OntologyRegistry) -> None:
        obj, _ = registry.create_object("Experiment", {
            "name": "test", "status": "designed",
        })
        updated, errs = registry.update_object(obj.id, {"status": "running"})
        assert updated is not None
        assert errs == []
        assert updated.properties["status"] == "running"
        assert updated.version == 2

    def test_update_immutable_blocked(self, registry: OntologyRegistry) -> None:
        obj, _ = registry.create_object("AgentIdentity", {
            "name": "agent-x", "role": "researcher",
        })
        _, errs = registry.update_object(obj.id, {"name": "renamed"})
        assert any("immutable" in e for e in errs)

    def test_update_nonexistent(self, registry: OntologyRegistry) -> None:
        _, errs = registry.update_object("fake-id", {"status": "running"})
        assert any("not found" in e for e in errs)

    def test_put_object_creates_with_exact_id(self, registry: OntologyRegistry) -> None:
        obj, errs = registry.put_object(
            OntologyObj(
                id="custodian-linter",
                type_name="CustodianRole",
                properties={
                    "name": "linter",
                    "tier": 3,
                    "model": "gpt-5.4-mini",
                    "status": "growing",
                    "total_runs": 1,
                    "success_rate": 1.0,
                    "files_healed": 2,
                },
                created_by="tester",
            )
        )
        assert obj is not None
        assert errs == []
        assert obj.id == "custodian-linter"
        assert registry.get_object("custodian-linter") is not None

    def test_put_object_updates_existing_with_validation(self, registry: OntologyRegistry) -> None:
        created, errs = registry.put_object(
            OntologyObj(
                id="custodian-linter",
                type_name="CustodianRole",
                properties={
                    "name": "linter",
                    "tier": 3,
                    "model": "gpt-5.4-mini",
                    "status": "growing",
                    "total_runs": 1,
                    "success_rate": 1.0,
                    "files_healed": 2,
                },
                created_by="tester",
            )
        )
        assert created is not None
        assert errs == []

        updated, errs = registry.put_object(
            OntologyObj(
                id="custodian-linter",
                type_name="CustodianRole",
                properties={
                    "name": "linter",
                    "status": "solid",
                    "total_runs": 5,
                    "success_rate": 0.8,
                    "files_healed": 8,
                },
                created_by="tester",
            )
        )
        assert updated is not None
        assert errs == []
        assert updated.properties["status"] == "solid"
        assert updated.properties["total_runs"] == 5
        assert updated.version == 2

    def test_put_object_blocks_immutable_change(self, registry: OntologyRegistry) -> None:
        created, errs = registry.put_object(
            OntologyObj(
                id="custodian-linter",
                type_name="CustodianRole",
                properties={
                    "name": "linter",
                    "tier": 3,
                    "model": "gpt-5.4-mini",
                    "status": "growing",
                    "total_runs": 1,
                    "success_rate": 1.0,
                    "files_healed": 2,
                },
                created_by="tester",
            )
        )
        assert created is not None
        assert errs == []

        _, errs = registry.put_object(
            OntologyObj(
                id="custodian-linter",
                type_name="CustodianRole",
                properties={
                    "name": "renamed",
                    "status": "solid",
                    "total_runs": 5,
                    "success_rate": 0.8,
                    "files_healed": 8,
                },
                created_by="tester",
            )
        )
        assert any("immutable" in e for e in errs)


# ── Links ───────────────────────────────────────────────────────────


class TestLinks:
    def test_create_valid_link(self, populated_registry: OntologyRegistry) -> None:
        links = populated_registry.get_links(link_name="has_experiment")
        assert len(links) == 1

    def test_link_type_enforcement(self, registry: OntologyRegistry) -> None:
        thread, _ = registry.create_object("ResearchThread", {
            "name": "test", "status": "active",
        })
        agent, _ = registry.create_object("AgentIdentity", {
            "name": "agent", "role": "researcher",
        })
        _, errs = registry.create_link("has_experiment", thread.id, agent.id)
        assert any("target" in e for e in errs)

    def test_cardinality_enforcement(self, registry: OntologyRegistry) -> None:
        task, _ = registry.create_object("TypedTask", {
            "title": "test", "status": "pending",
        })
        a1, _ = registry.create_object("AgentIdentity", {
            "name": "a1", "role": "coder",
        })
        a2, _ = registry.create_object("AgentIdentity", {
            "name": "a2", "role": "coder",
        })
        link1, errs1 = registry.create_link("assigned_to", task.id, a1.id)
        assert link1 is not None
        _, errs2 = registry.create_link("assigned_to", task.id, a2.id)
        assert any("cardinality" in e for e in errs2)

    def test_many_to_many_allows_multiple(self, registry: OntologyRegistry) -> None:
        task, _ = registry.create_object("TypedTask", {
            "title": "test", "status": "pending",
        })
        k1, _ = registry.create_object("KnowledgeArtifact", {
            "title": "a1", "artifact_type": "file",
        })
        k2, _ = registry.create_object("KnowledgeArtifact", {
            "title": "a2", "artifact_type": "note",
        })
        l1, _ = registry.create_link("consumes", task.id, k1.id)
        l2, _ = registry.create_link("consumes", task.id, k2.id)
        assert l1 is not None
        assert l2 is not None

    def test_get_linked_objects(self, populated_registry: OntologyRegistry) -> None:
        threads = populated_registry.get_objects_by_type("ResearchThread")
        exps = populated_registry.get_linked_objects(threads[0].id, "has_experiment")
        assert len(exps) == 1
        assert exps[0].properties["name"] == "L27 causal"

    def test_inverse_link_registered(self, registry: OntologyRegistry) -> None:
        inv = registry.get_link_def("Experiment", "belongs_to_thread")
        assert inv is not None
        assert inv.target_type == "ResearchThread"

    def test_source_not_found(self, registry: OntologyRegistry) -> None:
        target, _ = registry.create_object("Experiment", {
            "name": "test", "status": "designed",
        })
        _, errs = registry.create_link("has_experiment", "fake-id", target.id)
        assert any("source" in e for e in errs)


# ── Actions ─────────────────────────────────────────────────────────


class TestActions:
    def test_execute_success(self, registry: OntologyRegistry) -> None:
        obj, _ = registry.create_object("Experiment", {
            "name": "test", "status": "designed",
        })
        result = registry.execute_action("Experiment", "Run", obj.id, {"gpu": "A100"})
        assert result.result == "success"

    def test_execute_unknown_action(self, registry: OntologyRegistry) -> None:
        result = registry.execute_action("Experiment", "FakeAction", "id", {})
        assert result.result == "failed"
        assert "no action" in result.error

    def test_telos_gate_blocks(self, registry: OntologyRegistry) -> None:
        obj, _ = registry.create_object("Experiment", {
            "name": "test", "status": "designed",
        })

        def block_gates(name, params):
            return {"SATYA": "BLOCK"}

        result = registry.execute_action(
            "Experiment", "Run", obj.id, {}, gate_check=block_gates,
        )
        assert result.result == "blocked"

    def test_telos_gate_passes(self, registry: OntologyRegistry) -> None:
        obj, _ = registry.create_object("Experiment", {
            "name": "test", "status": "designed",
        })

        def pass_gates(name, params):
            return {"AHIMSA": "PASS", "SATYA": "PASS"}

        result = registry.execute_action(
            "Experiment", "Run", obj.id, {}, gate_check=pass_gates,
        )
        assert result.result == "success"

    def test_telos_gate_hardwired_without_explicit_gate(
        self, registry: OntologyRegistry,
    ) -> None:
        # W1: the default gatekeeper is hard-wired into execute_action, so a declared
        # telos_gate enforces even when the caller passes NO gate_check — it cannot be
        # bypassed by omission. EvolutionEntry is telos_required; Propose declares gates.
        obj, _ = registry.create_object("EvolutionEntry", {
            "component": "test.py", "change_type": "mutation",
        })
        # harmful params -> blocked by the default gate (no gate_check passed)
        blocked = registry.execute_action(
            "EvolutionEntry", "Propose", obj.id, {"command": "weaponize an attack to harm people"},
        )
        assert blocked.result == "blocked"
        assert "telos gate blocked" in blocked.error
        assert blocked.gate_results  # the default gate actually ran
        # benign params -> the gate runs and passes, but telos_required types stay
        # fail-closed without an explicit post-default gate.
        ok = registry.execute_action(
            "EvolutionEntry", "Propose", obj.id, {"note": "benign refactor"},
        )
        assert ok.result == "blocked"
        assert "telos-required type requires explicit gate_check" in ok.error
        assert ok.gate_results

    def test_action_history(self, registry: OntologyRegistry) -> None:
        obj, _ = registry.create_object("Experiment", {
            "name": "test", "status": "designed",
        })
        registry.execute_action("Experiment", "Design", obj.id, {})
        registry.execute_action("Experiment", "Run", obj.id, {})
        history = registry.action_history(object_id=obj.id)
        assert len(history) == 2
        assert history[0].action_name == "Run"  # most recent first


# ── Security ────────────────────────────────────────────────────────


class TestSecurity:
    def test_wildcard_allows_all(self, registry: OntologyRegistry) -> None:
        obj_type = registry.get_type("Experiment")
        ok, msg = check_security(obj_type, "anyone", "read")
        assert ok is True

    def test_restricted_roles(self, registry: OntologyRegistry) -> None:
        obj_type = registry.get_type("Paper")
        ok, msg = check_security(obj_type, "coder", "write")
        assert ok is False
        assert "denied" in msg

    def test_allowed_role(self, registry: OntologyRegistry) -> None:
        obj_type = registry.get_type("Paper")
        ok, msg = check_security(obj_type, "researcher", "write")
        assert ok is True

    def test_delete_restricted(self, registry: OntologyRegistry) -> None:
        obj_type = registry.get_type("AgentIdentity")
        ok, msg = check_security(obj_type, "researcher", "delete")
        assert ok is False

    def test_witness_log_no_delete(self, registry: OntologyRegistry) -> None:
        obj_type = registry.get_type("WitnessLog")
        ok, msg = check_security(obj_type, "system", "delete")
        assert ok is False  # empty delete_roles = nobody can delete


# ── OAG (Ontology-Augmented Generation) ─────────────────────────────


class TestOAG:
    def test_describe_type(self, registry: OntologyRegistry) -> None:
        desc = registry.describe_type("Experiment")
        assert "Experiment" in desc
        assert "r_v_value" in desc
        assert "mahasaraswati" in desc

    def test_describe_unknown(self, registry: OntologyRegistry) -> None:
        assert "Unknown" in registry.describe_type("Fake")

    def test_schema_for_llm_all(self, registry: OntologyRegistry) -> None:
        schema = registry.schema_for_llm()
        assert "Ontology Context" in schema
        for name in registry.type_names():
            assert name in schema

    def test_schema_for_llm_subset(self, registry: OntologyRegistry) -> None:
        schema = registry.schema_for_llm(["WitnessLog", "Paper"])
        assert "WitnessLog" in schema
        assert "Paper" in schema
        assert "Experiment" not in schema

    def test_object_context(self, populated_registry: OntologyRegistry) -> None:
        exps = populated_registry.get_objects_by_type("Experiment")
        ctx = populated_registry.object_context_for_llm(exps[0].id)
        assert "L27 causal" in ctx
        assert "produces" in ctx

    def test_object_context_not_found(self, registry: OntologyRegistry) -> None:
        ctx = registry.object_context_for_llm("fake-id")
        assert "not found" in ctx.lower()


# ── Persistence ─────────────────────────────────────────────────────


class TestPersistence:
    def test_save_and_load(self, populated_registry: OntologyRegistry) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            populated_registry.save(path)
            assert path.exists()

            reg2 = OntologyRegistry()
            loaded = reg2.load(path)
            assert loaded > 0

            s1 = populated_registry.stats()
            s2 = reg2.stats()
            assert s2["registered_types"] == s1["registered_types"]
            assert s2["total_objects"] == s1["total_objects"]
            assert s2["total_links"] == s1["total_links"]

    def test_load_nonexistent(self, registry: OntologyRegistry) -> None:
        loaded = registry.load(Path("/tmp/nonexistent_ontology.json"))
        assert loaded == 0

    def test_graph_summary(self, registry: OntologyRegistry) -> None:
        summary = registry.graph_summary()
        assert "Ontology Graph" in summary
        assert "Experiment" in summary


# ── Validation ──────────────────────────────────────────────────────


class TestValidation:
    def test_validate_object_type_mismatch(self) -> None:
        obj = OntologyObj(type_name="Wrong", properties={})
        obj_type = ObjectType(name="Right")
        errs = validate_object(obj, obj_type)
        assert any("mismatch" in e for e in errs)

    def test_validate_link_name_mismatch(self) -> None:
        link = Link(
            link_name="wrong",
            source_id="a", source_type="X",
            target_id="b", target_type="Y",
        )
        link_def = LinkDef(name="right", source_type="X", target_type="Y")
        errs = validate_link(link, link_def)
        assert any("mismatch" in e for e in errs)

    def test_validate_float_type(self) -> None:
        obj_type = ObjectType(
            name="Test",
            properties={"val": PropertyDef(
                name="val", property_type=PropertyType.FLOAT,
            )},
        )
        obj = OntologyObj(type_name="Test", properties={"val": "not_a_number"})
        errs = validate_object(obj, obj_type)
        assert any("numeric" in e for e in errs)

    def test_validate_boolean_type(self) -> None:
        obj_type = ObjectType(
            name="Test",
            properties={"flag": PropertyDef(
                name="flag", property_type=PropertyType.BOOLEAN,
            )},
        )
        obj = OntologyObj(type_name="Test", properties={"flag": "true"})
        errs = validate_object(obj, obj_type)
        assert any("boolean" in e for e in errs)


# ── Legacy API ──────────────────────────────────────────────────────


class TestLegacyAPI:
    def test_ontology_dict_populated(self) -> None:
        assert len(ONTOLOGY) >= 14

    def test_rv_paper_entity(self) -> None:
        rv = ONTOLOGY["rv_paper"]
        assert rv.type == "research_paper"
        assert rv.deadline is not None

    def test_entities_by_type(self) -> None:
        papers = entities_by_type("research_paper")
        assert len(papers) >= 2

    def test_entity_graph(self) -> None:
        graph = entity_graph()
        assert "rv_paper" in graph
        assert "mech_interp_lab" in graph["rv_paper"]

    def test_deadline_pressure(self) -> None:
        dl = deadline_pressure()
        assert len(dl) >= 1

    def test_deadline_summary(self) -> None:
        s = deadline_summary()
        assert "rv_paper" in s

    def test_entity_context(self) -> None:
        ctx = entity_context("rv_paper")
        assert "COLM" in ctx

    def test_entity_context_unknown(self) -> None:
        ctx = entity_context("nonexistent")
        assert "Unknown" in ctx

    def test_blocked_entities(self) -> None:
        # No blocked entities currently
        blocked = blocked_entities()
        assert isinstance(blocked, list)


# ── Dharmic Extensions ──────────────────────────────────────────────


class TestDharmicExtensions:
    def test_witness_log_max_telos(self, registry: OntologyRegistry) -> None:
        wl = registry.get_type("WitnessLog")
        assert wl.telos_alignment == 1.0

    def test_evolution_telos_required(self, registry: OntologyRegistry) -> None:
        ev = registry.get_type("EvolutionEntry")
        assert ev.security.telos_required is True

    def test_shakti_energies_diverse(self, registry: OntologyRegistry) -> None:
        energies = {t.shakti_energy for t in registry.get_types()}
        assert len(energies) >= 3  # at least 3 of 4 shaktis represented

    def test_actions_have_telos_gates(self, registry: OntologyRegistry) -> None:
        gated_actions = [
            a for a in registry._actions.values()
            if a.telos_gates
        ]
        assert len(gated_actions) >= 5


class TestRevenueOntologyTypes:
    """Validate revenue pipeline types are registered and well-formed."""

    REVENUE_TYPE_NAMES = [
        "RevenueTarget", "RevenueOffer", "RevenueOutreachDraft",
        "RevenueEngagement", "ComputeReinvestment",
    ]

    def test_all_revenue_types_registered(self, registry: OntologyRegistry) -> None:
        for name in self.REVENUE_TYPE_NAMES:
            assert registry.get_type(name) is not None, f"{name} not registered"

    def test_revenue_target_properties(self, registry: OntologyRegistry) -> None:
        rt = registry.get_type("RevenueTarget")
        assert "name" in rt.properties
        assert "status" in rt.properties
        assert "qualification_score" in rt.properties
        assert "spine_ref" in rt.properties

    def test_revenue_engagement_has_contracted_value(self, registry: OntologyRegistry) -> None:
        eng = registry.get_type("RevenueEngagement")
        assert "contracted_value_usd" in eng.properties
        assert eng.properties["contracted_value_usd"].required is True

    def test_outreach_has_approval_gate(self, registry: OntologyRegistry) -> None:
        od = registry.get_type("RevenueOutreachDraft")
        approve = next((a for a in od.actions if a.name == "Approve"), None)
        assert approve is not None
        assert "AHIMSA" in approve.telos_gates

    def test_action_proposal_accepts_revenue_type(self, registry: OntologyRegistry) -> None:
        ap = registry.get_type("ActionProposal")
        at_prop = ap.properties["action_type"]
        assert "revenue" in at_prop.enum_values

    def test_outcome_has_revenue_fields(self, registry: OntologyRegistry) -> None:
        outcome = registry.get_type("Outcome")
        assert "outcome_kind" in outcome.properties
        assert "economic_amount_usd" in outcome.properties
        assert "revenue" in outcome.properties["outcome_kind"].enum_values

    def test_value_event_has_revenue_fields(self, registry: OntologyRegistry) -> None:
        ve = registry.get_type("ValueEvent")
        assert "value_kind" in ve.properties
        assert "economic_value_usd" in ve.properties
        assert "paid_revenue" in ve.properties["value_kind"].enum_values

    def test_contribution_has_revenue_fields(self, registry: OntologyRegistry) -> None:
        c = registry.get_type("Contribution")
        assert "beneficiary_type" in c.properties
        assert "revenue_ref" in c.properties

    def test_revenue_links_registered(self, registry: OntologyRegistry) -> None:
        link = registry.get_link_def("RevenueTarget", "has_offer")
        assert link is not None
        assert link.target_type == "RevenueOffer"

    def test_engagement_to_outcome_link(self, registry: OntologyRegistry) -> None:
        link = registry.get_link_def("RevenueEngagement", "engagement_outcome")
        assert link is not None
        assert link.target_type == "Outcome"

    def test_engagement_to_reinvestment_link(self, registry: OntologyRegistry) -> None:
        link = registry.get_link_def("RevenueEngagement", "engagement_reinvestment")
        assert link is not None
        assert link.target_type == "ComputeReinvestment"

    def test_revenue_types_are_mahalakshmi(self, registry: OntologyRegistry) -> None:
        for name in ["RevenueTarget", "RevenueOffer", "RevenueEngagement",
                      "ComputeReinvestment"]:
            t = registry.get_type(name)
            assert t.shakti_energy == ShaktiEnergy.MAHALAKSHMI

    def test_outreach_is_maheshwari(self, registry: OntologyRegistry) -> None:
        od = registry.get_type("RevenueOutreachDraft")
        assert od.shakti_energy == ShaktiEnergy.MAHESHWARI

    def test_create_revenue_target_object(self, registry: OntologyRegistry) -> None:
        obj, errors = registry.create_object("RevenueTarget", {
            "name": "acme/widgets",
            "source": "github_scout",
            "status": "scouted",
            "qualification_score": 0.75,
        })
        assert obj is not None, f"Creation failed: {errors}"
        assert obj.type_name == "RevenueTarget"

    def test_create_engagement_object(self, registry: OntologyRegistry) -> None:
        obj, errors = registry.create_object("RevenueEngagement", {
            "target_id": "tgt-001",
            "offer_id": "off-001",
            "status": "scoping",
            "contracted_value_usd": 15000.0,
        })
        assert obj is not None, f"Creation failed: {errors}"
        assert obj.properties["contracted_value_usd"] == 15000.0


# ── OMS Hardening (TypeStatus + api_name + uniqueness) ───────────


class TestTypeStatus:
    def test_new_type_defaults_to_experimental(self) -> None:
        t = ObjectType(name="Scratch", description="test")
        assert t.status == TypeStatus.EXPERIMENTAL

    def test_domain_types_are_active(self, registry: OntologyRegistry) -> None:
        for name in registry.type_names():
            obj_type = registry.get_type(name)
            assert obj_type is not None
            assert obj_type.status == TypeStatus.ACTIVE, (
                f"{name} should be ACTIVE, got {obj_type.status}"
            )

    def test_status_enum_values(self) -> None:
        assert set(TypeStatus) == {
            TypeStatus.EXPERIMENTAL,
            TypeStatus.ACTIVE,
            TypeStatus.PROMOTED,
        }


class TestApiName:
    def test_all_domain_types_have_api_name(self, registry: OntologyRegistry) -> None:
        for name in registry.type_names():
            obj_type = registry.get_type(name)
            assert obj_type is not None
            assert obj_type.api_name, f"{name} is missing api_name"
            assert obj_type.api_name.startswith("dharma."), (
                f"{name} api_name should start with 'dharma.', got {obj_type.api_name!r}"
            )

    def test_api_names_are_unique(self, registry: OntologyRegistry) -> None:
        seen: dict[str, str] = {}
        for name in registry.type_names():
            obj_type = registry.get_type(name)
            assert obj_type is not None
            if obj_type.api_name in seen:
                pytest.fail(
                    f"Duplicate api_name {obj_type.api_name!r}: "
                    f"{seen[obj_type.api_name]} and {name}"
                )
            seen[obj_type.api_name] = name

    def test_register_type_rejects_duplicate_api_name(self, registry: OntologyRegistry) -> None:
        with pytest.raises(ValueError, match="api_name .* already registered"):
            registry.register_type(
                ObjectType(
                    name="ResearchThreadShadow",
                    description="duplicate API identity",
                    api_name="dharma.research.ResearchThread",
                )
            )

    def test_allow_overwrite_does_not_bypass_api_name_uniqueness(
        self,
        registry: OntologyRegistry,
    ) -> None:
        with pytest.raises(ValueError, match="api_name .* already registered"):
            registry.register_type(
                ObjectType(
                    name="AgentIdentity",
                    description="same name, wrong frozen API identity",
                    api_name="dharma.research.ResearchThread",
                ),
                allow_overwrite=True,
            )

    def test_api_name_format(self, registry: OntologyRegistry) -> None:
        """ADR-008: dharma.<domain>.<TypeName>, PascalCase, no .vN suffix."""
        for name in registry.type_names():
            obj_type = registry.get_type(name)
            assert obj_type is not None
            parts = obj_type.api_name.split(".")
            assert len(parts) == 3, (
                f"{name} api_name should have exactly 3 parts, got {obj_type.api_name!r}"
            )
            assert parts[0] == "dharma", (
                f"{name} api_name should start with 'dharma', got {parts[0]!r}"
            )
            assert parts[2] == obj_type.name, (
                f"{name} api_name TypeName should match ObjectType.name, "
                f"got {parts[2]!r}"
            )
            assert parts[2][0].isupper(), (
                f"{name} api_name TypeName should be PascalCase, got {parts[2]!r}"
            )

    def test_new_type_has_empty_api_name(self) -> None:
        t = ObjectType(name="Scratch", description="test")
        assert t.api_name == ""


class TestRegisterTypeUniqueness:
    def test_duplicate_raises(self, registry: OntologyRegistry) -> None:
        with pytest.raises(ValueError, match="already registered"):
            registry.register_type(
                ObjectType(name="ResearchThread", description="dup")
            )

    def test_allow_overwrite(self, registry: OntologyRegistry) -> None:
        registry.register_type(
            ObjectType(name="ResearchThread", description="replaced"),
            allow_overwrite=True,
        )
        t = registry.get_type("ResearchThread")
        assert t is not None
        assert t.description == "replaced"

    def test_new_name_succeeds(self, registry: OntologyRegistry) -> None:
        registry.register_type(
            ObjectType(name="BrandNew", description="fresh")
        )
        t = registry.get_type("BrandNew")
        assert t is not None
        assert t.status == TypeStatus.EXPERIMENTAL

    def test_promoted_api_name_is_immutable_on_overwrite(
        self,
        registry: OntologyRegistry,
    ) -> None:
        registry.register_type(
            ObjectType(
                name="StableContract",
                description="promoted contract",
                status=TypeStatus.PROMOTED,
                api_name="dharma.contract.StableContract",
            )
        )

        with pytest.raises(ValueError, match="PROMOTED with immutable api_name"):
            registry.register_type(
                ObjectType(
                    name="StableContract",
                    description="attempted identity drift",
                    status=TypeStatus.PROMOTED,
                    api_name="dharma.contract.RenamedContract",
                ),
                allow_overwrite=True,
            )
