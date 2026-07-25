"""L2.5 — the real-model swarm arm (build_arm_from_models) over the provider-backed
LiveModel path, validated OFFLINE via FakeCompletion (no live calls). Proves the
swarm topology works with real Model objects, and that the verify-gate selects the
passing proposer across decorrelated models."""
from dharma_swarm.forge_v1.fixtures import ADD_TASK
from dharma_swarm.forge_v1.harness import TokenBroker
from dharma_swarm.forge_v1.providers import FakeCompletion, LiveModel
from dharma_swarm.forge_v1.swarm import build_arm_from_models


def _live(code: str) -> LiveModel:
    """A LiveModel whose backend always returns `code` in a python code block —
    exactly the shape a real provider returns, parsed by LiveModel."""
    return LiveModel(FakeCompletion([f"```python\n{code}```\n"]))


def test_real_model_swarm_gate_selects_correct_proposer():
    gold = ADD_TASK.gold_patch["solution.py"]
    buggy = ADD_TASK.files["solution.py"]
    weak = _live(buggy)    # proposes the still-buggy file
    strong = _live(gold)   # proposes the fix
    arm = build_arm_from_models([weak, strong], verify_gate=True)
    res = arm(ADD_TASK, TokenBroker(cap=10_000))
    assert res.passed          # the gate keeps the strong proposer's passing patch
    assert res.samples == 2    # tried weak (fail) then strong (pass)


def test_real_model_swarm_no_gate_submits_first_unchecked():
    buggy = ADD_TASK.files["solution.py"]
    gold = ADD_TASK.gold_patch["solution.py"]
    arm = build_arm_from_models([_live(buggy), _live(gold)], verify_gate=False)
    res = arm(ADD_TASK, TokenBroker(cap=10_000))
    assert not res.passed       # no gate -> submits the first (buggy) -> fail
    assert res.samples == 1


def test_real_model_swarm_respects_token_budget():
    # tokens come from FakeCompletion (prompt+text/4); a tiny cap aborts early.
    gold = ADD_TASK.gold_patch["solution.py"]
    arm = build_arm_from_models([_live(gold), _live(gold)], verify_gate=True)
    res = arm(ADD_TASK, TokenBroker(cap=1))   # cannot afford even one call
    assert not res.passed
    assert res.samples == 0
