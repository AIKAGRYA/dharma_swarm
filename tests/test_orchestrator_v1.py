"""Zero-weight orchestrator v1 tests (spec §10 step 4): emits a valid genome,
runs through the arena, archives winners WITHOUT mutating production routing,
produces a decision_packet — all hermetic, no GPU/keys."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from dharma_swarm.coordination.genome import OrchestrationGenome
from dharma_swarm.coordination.orchestrator_v1 import (
    MapElitesArchive,
    ZeroWeightOrchestratorV1,
)


def test_seed_population_are_valid_genomes():
    orch = ZeroWeightOrchestratorV1(seed=1)
    seeds = orch.seed_population()
    assert seeds
    for g in seeds:
        assert isinstance(g, OrchestrationGenome)
        g.validate_structure()
        assert g.genome_id.startswith("genome-")
        assert g.behavioral_descriptors.roster_size >= 1


def test_mutation_produces_valid_child_with_lineage():
    orch = ZeroWeightOrchestratorV1(seed=2)
    parent = orch.seed_population()[0]
    child = orch.mutate(parent, generation=1)
    child.validate_structure()
    assert child.lineage.parent_genome_id == parent.genome_id
    assert child.lineage.mutation_op
    assert child.lineage.generation == 1


def test_evolve_finds_positive_lift_winner():
    orch = ZeroWeightOrchestratorV1(seed=3)
    result = orch.evolve(generations=10)
    assert result.evaluated >= 5
    assert result.best is not None
    # the seed router (all specialists + synthesize) is a positive-lift winner
    assert result.best.closeout_state == "positive_lift_candidate"
    assert result.best.score == 1.0
    assert len(result.archive.winners()) >= 1


def test_archive_is_quality_diversity_not_top_k():
    orch = ZeroWeightOrchestratorV1(seed=4)
    result = orch.evolve(generations=12)
    cells = result.archive.cells
    # multiple distinct behavioral cells illuminated (diversity, not a leaderboard)
    assert len(cells) >= 2
    # each cell key is a behavioral descriptor tuple, occupant matches it
    for key, entry in cells.items():
        assert entry.genome.behavioral_descriptors.bin_key() == key


def test_contaminated_genome_never_wins_a_cell():
    orch = ZeroWeightOrchestratorV1(seed=5)
    cheater = OrchestrationGenome(
        roster=[{"role_id": "r0", "member_id": "alpha-math", "kind": "model"}],
        adjudication_rule="single",
        permissions={"r0": ["read_sealed_labels"]},
    ).with_descriptors()
    entry = orch.evaluate(cheater)
    assert entry.closeout_state == "contaminated_quarantine"
    assert entry.fitness < 0  # floored: cannot win any MAP-Elites cell
    archive = MapElitesArchive()
    # A contaminated genome is NEVER archived — not even into an empty cell — so it
    # can never become an elite or a mutation parent (Codex P2 fix).
    assert archive.consider(entry) is False
    assert archive.cells == {}
    assert entry not in archive.elites()
    # a clean genome with a real score IS archived into the (still-empty) cell
    clean = orch.evaluate(orch.seed_population()[0])
    assert archive.consider(clean) is True


def test_evolve_writes_route_receipts_and_decision_packet(tmp_path):
    orch = ZeroWeightOrchestratorV1(seed=6)
    result = orch.evolve(generations=6, output_dir=tmp_path)
    assert (tmp_path / "route_receipts.jsonl").exists()
    assert (tmp_path / "map_elites_archive.json").exists()
    assert (tmp_path / "decision_packet.md").exists()
    # route receipts carry lineage + closeout per evaluated genome
    rows = [
        json.loads(line)
        for line in (tmp_path / "route_receipts.jsonl").read_text().splitlines()
    ]
    assert len(rows) == result.evaluated
    assert all("mutation_op" in r and "closeout_state" in r for r in rows)
    packet = (tmp_path / "decision_packet.md").read_text()
    assert "Decision Packet" in packet


def test_orchestrator_does_not_touch_production_routing():
    """Spec invariant: NO production-router mutation. The module must not import
    provider_policy / orchestrator.py routing / model_hierarchy."""
    src = Path("dharma_swarm/coordination/orchestrator_v1.py").read_text()
    tree = ast.parse(src)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
    forbidden = ("provider_policy", "model_hierarchy", "model_pool", "smart_router",
                 "router_v1", "decision_router")
    for mod in imported:
        for bad in forbidden:
            assert bad not in mod, f"orchestrator_v1 must not import production routing ({mod})"
    # the production orchestrator may not be imported either
    assert not any(m.endswith("dharma_swarm.orchestrator") for m in imported)
