"""Tests for OrchestrationGenome (spec §1) — validation, serialization, stable id,
TopologyGenome adapter seam, MAP-Elites descriptors, budget parity."""

from __future__ import annotations

import pytest

from dharma_swarm.coordination.genome import (
    BehavioralDescriptors,
    OrchestrationGenome,
    RoleBudget,
    RoleEdge,
    RosterMember,
    Subtask,
    VerificationStep,
)


def _genome(**overrides):
    base = dict(
        task_decomposition=[
            Subtask(subtask_id="t1", description="parse"),
            Subtask(subtask_id="t2", description="solve", depends_on=["t1"]),
        ],
        roster=[
            RosterMember(role_id="planner", member_id="qwen3-32b", kind="model"),
            RosterMember(role_id="solver", member_id="qwen2.5-coder-32b", kind="model"),
        ],
        role_graph=[RoleEdge(source_role_id="planner", target_role_id="solver")],
        prompt_fragments={"planner": "Decompose.", "solver": "Solve."},
        context_plan={"planner": [], "solver": "all"},
        budget_allocation={
            "planner": RoleBudget(tokens=500, latency_ms=1000),
            "solver": RoleBudget(tokens=1500, latency_ms=2000),
        },
        verification_plan=[VerificationStep(step="final")],
        adjudication_rule="synthesize",
        permissions={"solver": ["run_code"]},
    )
    base.update(overrides)
    return OrchestrationGenome(**base)


def test_genome_validates_clean_structure():
    g = _genome().validate_structure()
    assert g.genome_id.startswith("genome-")


def test_stable_id_is_content_addressed():
    g1 = _genome()
    g2 = _genome()
    assert g1.genome_id == g2.genome_id == g1.stable_id()


def test_stable_id_changes_with_structure_not_lineage():
    g1 = _genome()
    # lineage / descriptors / receipts must NOT change identity
    g2 = _genome()
    g2.lineage.parent_genome_id = "other"
    g2.lineage.mutation_op = "swap_model"
    g2.receipt_refs.append("receipt://abc")
    assert g1.stable_id() == g2.stable_id()
    # but a structural change must change identity
    g3 = _genome(adjudication_rule="vote")
    assert g3.stable_id() != g1.stable_id()


def test_serialization_roundtrip():
    g = _genome()
    clone = OrchestrationGenome.from_json(g.to_json())
    assert clone.genome_id == g.genome_id
    assert clone.roster[0].member_id == "qwen3-32b"
    assert clone.context_plan["solver"] == "all"
    assert clone.validate_structure().genome_id == g.genome_id


def test_validation_rejects_unknown_role_in_edge():
    g = _genome(role_graph=[RoleEdge(source_role_id="planner", target_role_id="ghost")])
    with pytest.raises(ValueError, match="unknown target role"):
        g.validate_structure()


def test_validation_rejects_unknown_subtask_dependency():
    g = _genome(task_decomposition=[Subtask(subtask_id="t1", depends_on=["nope"])])
    with pytest.raises(ValueError, match="depends on unknown"):
        g.validate_structure()


def test_validation_rejects_cyclic_decomposition():
    """The decomposition is a dependency DAG — a cycle must be rejected even when
    every dependency name exists (Codex P2 fix)."""
    g = _genome(
        task_decomposition=[
            Subtask(subtask_id="a", depends_on=["b"]),
            Subtask(subtask_id="b", depends_on=["a"]),
        ]
    )
    with pytest.raises(ValueError, match="dependency cycle"):
        g.validate_structure()


def test_validation_rejects_self_cycle():
    g = _genome(task_decomposition=[Subtask(subtask_id="a", depends_on=["a"])])
    with pytest.raises(ValueError, match="dependency cycle"):
        g.validate_structure()


def test_budget_parity_cap_enforced():
    g = _genome()  # total tokens = 2000
    g.validate_structure(budget_parity_cap=2000)  # exactly at cap is fine
    with pytest.raises(ValueError, match="budget parity violated"):
        g.validate_structure(budget_parity_cap=1999)


def test_behavioral_descriptors_derived():
    g = _genome().with_descriptors()
    d = g.behavioral_descriptors
    assert isinstance(d, BehavioralDescriptors)
    assert d.roster_size == 2
    assert d.roster_diversity == 2
    assert d.decomposition_depth == 2  # t2 -> t1
    assert d.topology_shape == "pipeline"
    assert d.adjudication == "synthesize"
    assert d.bin_key() == (2, 2, 2, "pipeline", "synthesize")


def test_topology_genome_adapter_roundtrip():
    """OrchestrationGenome EXTENDS TopologyGenome — adapter must round-trip the
    fields the base models (backward-compat-ready, spec §1 / §10a)."""
    g = _genome()
    topo = g.to_topology_genome()
    # base genome validates under its own contract
    topo.validate_structure()
    assert topo.genome_id == g.genome_id
    assert {n.node_id for n in topo.nodes} == {"planner", "solver"}
    assert topo.entrypoints == ["planner"]

    back = OrchestrationGenome.from_topology_genome(topo)
    assert {m.role_id for m in back.roster} == {"planner", "solver"}
    assert back.prompt_fragments["planner"] == "Decompose."
    assert back.context_plan["solver"] == "all"
    assert back.adjudication_rule == "synthesize"
    members = {m.role_id: m.member_id for m in back.roster}
    assert members["planner"] == "qwen3-32b"


def test_topology_shape_classifications():
    # single
    solo = OrchestrationGenome(roster=[RosterMember(role_id="a", member_id="m")])
    assert solo.derive_descriptors().topology_shape == "single"
    # star: one hub to all
    star = OrchestrationGenome(
        roster=[RosterMember(role_id=r, member_id="m") for r in ("hub", "x", "y")],
        role_graph=[
            RoleEdge(source_role_id="hub", target_role_id="x"),
            RoleEdge(source_role_id="hub", target_role_id="y"),
        ],
    )
    assert star.derive_descriptors().topology_shape == "star"
