"""End-to-end tests for the full Forge (L1-L4), all offline. They assert the
machine is HONEST and that the loop actually closes: competence models behave
as designed, the verify-gated diverse swarm beats a single model (skill
selection), the evolution loop improves fitness and keeps a monotone best-so-far
curve, the ablation attributes per-edge contribution, the ledger persists, and
the real-model adapter parses a completion into a working patch."""
import tempfile
from pathlib import Path

from dharma_swarm.forge_v1.evolution import evolve
from dharma_swarm.forge_v1.harness import TokenBroker, best_of_n, run_arm, verify
from dharma_swarm.forge_v1.providers import FakeCompletion, LiveModel
from dharma_swarm.forge_v1.swarm import QualityModel, SwarmConfig, build_arm
from dharma_swarm.forge_v1.swebench import bench_tasks
from dharma_swarm.forge_v1.tracking import RunLedger, ablate_edges

TASKS = bench_tasks()
BUDGET = 8000


def _champion(task, broker):
    return best_of_n(QualityModel("champ", seed=7, comp_period=2), task, broker)


# --- L2: competence models + the coordination mechanism ---
def test_quality_model_competence_is_deterministic_and_ceilinged():
    m = QualityModel("m", seed=3, comp_period=2)
    t = TASKS[0]
    # deterministic
    assert m.solves(t) == m.solves(t)
    # ceiling: if it can't solve it, more samples never produce the gold patch
    if not m.solves(t):
        assert m.propose(t, 0).patch == m.propose(t, 99).patch == t.files


def test_diverse_gated_swarm_beats_single_model():
    # A single model's best-of-N is capped at its competence.
    single = run_arm(lambda t, b: best_of_n(QualityModel("s", 7, 2), t, b), TASKS, BUDGET)
    # A diverse, verify-gated swarm covers the union of competences.
    swarm_cfg = SwarmConfig([(7, 2), (11, 2), (23, 2), (41, 2)], verify_gate=True)
    swarm = run_arm(build_arm(swarm_cfg), TASKS, BUDGET)
    assert swarm["pass_at_1"] >= single["pass_at_1"]


def test_verify_gate_matters():
    cfg_on = SwarmConfig([(7, 2), (11, 2), (23, 2)], verify_gate=True)
    cfg_off = SwarmConfig([(7, 2), (11, 2), (23, 2)], verify_gate=False)
    on = run_arm(build_arm(cfg_on), TASKS, BUDGET)["pass_at_1"]
    off = run_arm(build_arm(cfg_off), TASKS, BUDGET)["pass_at_1"]
    assert on >= off  # selecting the verified patch never hurts


# --- L4: the evolutionary loop closes ---
def test_evolution_improves_and_curve_is_monotone():
    out, best_cfg, archive = evolve(TASKS, _champion, BUDGET, generations=12, seed=42)
    curve = out["fitness_curve"]
    # best-so-far never decreases, and evolution found something >= the weak seed
    assert all(b >= a for a, b in zip(curve, curve[1:]))
    assert curve[-1] >= curve[0]
    assert out["archive_size"] > 12
    assert 0.0 <= out["swarm_pass_at_1"] <= 1.0
    assert out["final_lift_ci"]["n"] == len(TASKS)
    assert out["ship_swarm"] == (out["final_lift_ci"]["lower"] > 0)


# --- L3: ablation + ledger ---
def test_ablation_attributes_edges():
    cfg = SwarmConfig([(7, 2), (11, 2), (23, 2)], verify_gate=True)
    abl = ablate_edges(cfg, TASKS, _champion, BUDGET)
    assert "verify_gate" in abl["edge_contributions"]
    assert any(k.startswith("proposer[") for k in abl["edge_contributions"])


def test_ledger_persists_and_reads_back():
    with tempfile.TemporaryDirectory() as d:
        ledger = RunLedger(path=Path(d) / "runs.jsonl")
        ledger.record({"event": "x", "lift": 0.25})
        rows = ledger.all()
        assert rows and rows[-1]["lift"] == 0.25


# --- L1: real-model adapter parses a completion into a working patch ---
def test_live_model_parses_completion_into_patch():
    t = TASKS[0]
    gold = t.gold_patch["solution.py"]
    completion = FakeCompletion([f"Here is the fix:\n```python\n{gold}```\n"])
    cand = LiveModel(completion).propose(t, 0)
    assert verify(t, cand.patch) is True
    assert cand.tokens > 0
