"""Per-node retry policy (LG24) — dharmagraph-engine-2026-07.

Covers: langgraph-1.2.4-identical policy defaults, per-node retry selection
(a policy-less sibling never retries), first-match selection across a policy
sequence, the capped exponential backoff ladder, seeded jitter routed through
``effects.random()`` with no wall-clock sleeping, ``max_attempts`` counting the
first attempt, the three ``retry_on`` spellings, and the write-clearing
guarantee (a retried node commits exactly one set of writes).

No LangGraph imports here — the two-arm differential lives in the gauntlet's
``seeded_retry_policy`` workload.
"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping

import pytest

from dharma_swarm.graph.channels import AppendChannel, LastValueChannel
from dharma_swarm.graph.compiler import GraphBuilder
from dharma_swarm.graph.effects import SimulatedEffects
from dharma_swarm.graph.errors import NodeExecutionError, NodeTimeoutError
from dharma_swarm.graph.interrupts import GraphInterrupted, interrupt
from dharma_swarm.graph.retry import (
    RetryPolicy,
    backoff_interval,
    default_retry_on,
    normalize_retry_policies,
    retry_candidate,
    retry_sleep_seconds,
    select_retry_policy,
    should_retry_on,
)
from dharma_swarm.graph.types import END, START

FAST = {"initial_interval": 0.01, "jitter": False}


def _run(compiled, effects: SimulatedEffects, **kwargs: Any):
    return asyncio.run(
        compiled.invoke(input={"log": []}, effects=effects, **kwargs)
    )


def _graph(node_id: str, fn, **node_kwargs: Any):
    return (
        GraphBuilder(f"retry-{node_id}")
        .add_channel("log", AppendChannel)
        .add_node(node_id, fn, **node_kwargs)
        .add_edge(START, node_id)
        .add_edge(node_id, END)
        .compile()
    )


def _failing(counter: dict[str, int], exc: BaseException, succeed_after: int = 0):
    """A node that raises ``exc`` until its call count passes ``succeed_after``."""

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        counter["n"] += 1
        if succeed_after == 0 or counter["n"] <= succeed_after:
            raise exc
        return {"log": ["ok"]}

    return node


# -- policy shape -------------------------------------------------------


def test_retry_policy_defaults_match_langgraph_1_2_4():
    policy = RetryPolicy()
    assert policy.initial_interval == 0.5
    assert policy.backoff_factor == 2.0
    assert policy.max_interval == 128.0
    assert policy.max_attempts == 3  # includes the first attempt
    assert policy.jitter is True
    assert policy.retry_on is default_retry_on


@pytest.mark.parametrize(
    "exc,retryable",
    [
        (ConnectionError("net"), True),
        (NodeTimeoutError("n", 1.0, kind="run", run_timeout=0.5), True),
        (ValueError("bad"), False),
        (TypeError("bad"), False),
        (KeyError("bad"), False),  # LookupError
        (ZeroDivisionError("bad"), False),  # ArithmeticError
        (RuntimeError("bad"), False),
        (OSError("bad"), False),
        (Exception("unknown"), True),
    ],
)
def test_default_retry_on_classification(exc: Exception, retryable: bool):
    assert default_retry_on(exc) is retryable


def test_normalize_retry_policies_rejects_non_policies():
    assert normalize_retry_policies(None) == ()
    single = RetryPolicy()
    assert normalize_retry_policies(single) == (single,)
    with pytest.raises(TypeError, match="fail closed"):
        normalize_retry_policies(["not-a-policy"])  # type: ignore[list-item]


def test_should_retry_on_accepts_class_sequence_and_callable():
    assert should_retry_on(RetryPolicy(retry_on=KeyError), KeyError("k"))
    assert should_retry_on(RetryPolicy(retry_on=(KeyError, ValueError)), ValueError())
    assert should_retry_on(RetryPolicy(retry_on=lambda exc: True), ValueError())
    with pytest.raises(TypeError, match="retry_on must be"):
        should_retry_on(RetryPolicy(retry_on=17), ValueError())  # type: ignore[arg-type]


def test_backoff_intervals_capped_exponential():
    policy = RetryPolicy(
        initial_interval=0.01, backoff_factor=3.0, max_interval=0.05
    )
    assert [backoff_interval(policy, k) for k in range(1, 6)] == [
        0.01,
        0.01 * 3.0,
        0.05,
        0.05,
        0.05,
    ]
    with pytest.raises(ValueError, match="1-indexed"):
        backoff_interval(policy, 0)


def test_jitter_is_additive_uniform_from_the_effects_seam():
    policy = RetryPolicy(initial_interval=0.01, jitter=True)
    first = retry_sleep_seconds(policy, 1, SimulatedEffects(4))
    same = retry_sleep_seconds(policy, 1, SimulatedEffects(4))
    other = retry_sleep_seconds(policy, 1, SimulatedEffects(5))
    assert first == same  # same seed, same draw
    assert first != other
    assert 0.01 <= first < 1.01  # additive uniform(0, 1), not proportional


def test_retry_candidate_unwraps_node_execution_error():
    cause = ConnectionError("net")
    wrapped = NodeExecutionError("node failed")
    wrapped.__cause__ = cause
    assert retry_candidate(wrapped) is cause
    assert retry_candidate(cause) is cause


# -- selection ----------------------------------------------------------


def test_add_node_retry_selection_only_configured_node_retries():
    counts = {"guarded": 0, "plain": 0}

    def guarded(state):
        counts["guarded"] += 1
        if counts["guarded"] < 3:
            raise ConnectionError("transient")
        return {"log": ["guarded"]}

    def plain(state):
        counts["plain"] += 1
        return {"log": ["plain"]}

    compiled = (
        GraphBuilder("selection")
        .add_channel("log", AppendChannel)
        .add_node(
            "guarded",
            guarded,
            retry_policy=RetryPolicy(max_attempts=5, **FAST),
        )
        .add_node("plain", plain)
        .add_edge(START, "guarded")
        .add_edge(START, "plain")
        .add_edge("guarded", END)
        .add_edge("plain", END)
        .compile()
    )
    result = _run(compiled, SimulatedEffects(1))
    assert counts == {"guarded": 3, "plain": 1}
    assert sorted(result.state["log"]) == ["guarded", "plain"]


def test_first_matching_policy_selected_from_sequence():
    policies = (
        RetryPolicy(retry_on=(KeyError,), max_attempts=3, **FAST),
        RetryPolicy(retry_on=(Exception,), max_attempts=5, **FAST),
    )
    assert select_retry_policy(policies, KeyError("k")) is policies[0]
    assert select_retry_policy(policies, ConnectionError("c")) is policies[1]
    assert select_retry_policy((), KeyError("k")) is None

    counts = {"n": 0}
    effects = SimulatedEffects(1)
    with pytest.raises(NodeExecutionError):
        _run(
            _graph("f", _failing(counts, KeyError("k")), retry_policy=list(policies)),
            effects,
        )
    # The EARLIER policy's ladder wins even though the later one also matches.
    assert counts["n"] == 3
    assert len(effects.retry_sleeps) == 2


# -- ladder arithmetic in situ ------------------------------------------


def test_max_attempts_includes_first_attempt_then_reraises():
    counts = {"n": 0}
    effects = SimulatedEffects(2)
    with pytest.raises(NodeExecutionError):
        _run(
            _graph(
                "f",
                _failing(counts, ConnectionError("always")),
                retry_policy=RetryPolicy(max_attempts=3, **FAST),
            ),
            effects,
        )
    assert counts["n"] == 3
    assert len(effects.retry_sleeps) == 2

    once = {"n": 0}
    single_effects = SimulatedEffects(2)
    with pytest.raises(NodeExecutionError):
        _run(
            _graph(
                "f",
                _failing(once, ConnectionError("always")),
                retry_policy=RetryPolicy(max_attempts=1, **FAST),
            ),
            single_effects,
        )
    assert once["n"] == 1
    assert single_effects.retry_sleeps == []


def test_backoff_ladder_recorded_through_the_effects_seam_without_waiting():
    counts = {"n": 0}
    effects = SimulatedEffects(3)
    with pytest.raises(NodeExecutionError):
        _run(
            _graph(
                "f",
                _failing(counts, ConnectionError("always")),
                retry_policy=RetryPolicy(
                    initial_interval=0.01,
                    backoff_factor=3.0,
                    max_interval=0.05,
                    max_attempts=5,
                    jitter=False,
                ),
            ),
            effects,
        )
    assert effects.retry_sleeps == [0.01, 0.01 * 3.0, 0.05, 0.05]


def test_jitter_routes_through_effects_random_deterministically():
    def ladder(seed: int) -> list[float]:
        effects = SimulatedEffects(seed)
        with pytest.raises(NodeExecutionError):
            _run(
                _graph(
                    "f",
                    _failing({"n": 0}, ConnectionError("always")),
                    retry_policy=RetryPolicy(max_attempts=4, initial_interval=0.01),
                ),
                effects,
            )
        return list(effects.retry_sleeps)

    first, repeat, different = ladder(9), ladder(9), ladder(10)
    assert len(first) == 3
    assert first == repeat  # same seed replays the exact ladder
    assert first != different
    assert all(0.01 <= sleep < 1.01 for sleep in first)


# -- retry_on in situ ---------------------------------------------------


def test_non_matching_exception_never_retries():
    counts = {"n": 0}
    effects = SimulatedEffects(4)
    with pytest.raises(NodeExecutionError):
        _run(
            _graph(
                "f",
                _failing(counts, ValueError("deterministic")),
                retry_policy=RetryPolicy(
                    retry_on=(KeyError,), max_attempts=4, **FAST
                ),
            ),
            effects,
        )
    assert counts["n"] == 1
    assert effects.retry_sleeps == []


def test_retry_on_callable_predicate_retries_the_wrapped_cause():
    counts = {"n": 0}
    result = _run(
        _graph(
            "f",
            _failing(counts, ValueError("retry me"), succeed_after=1),
            retry_policy=RetryPolicy(
                retry_on=lambda exc: isinstance(exc, ValueError),
                max_attempts=3,
                **FAST,
            ),
        ),
        SimulatedEffects(5),
    )
    # The predicate saw the NODE's ValueError, not the engine's wrapper.
    assert counts["n"] == 2
    assert result.state["log"] == ["ok"]


def test_default_policy_splits_transient_from_deterministic_failures():
    transient = {"n": 0}
    with pytest.raises(NodeExecutionError):
        _run(
            _graph(
                "f",
                _failing(transient, ConnectionError("net")),
                retry_policy=RetryPolicy(max_attempts=3, **FAST),
            ),
            SimulatedEffects(6),
        )
    assert transient["n"] == 3

    deterministic = {"n": 0}
    with pytest.raises(NodeExecutionError):
        _run(
            _graph(
                "f",
                _failing(deterministic, ValueError("bad")),
                retry_policy=RetryPolicy(max_attempts=3, **FAST),
            ),
            SimulatedEffects(6),
        )
    assert deterministic["n"] == 1


# -- write clearing + control-flow signals ------------------------------


def test_failed_attempt_writes_cleared_single_barrier_commit():
    counts = {"n": 0}

    def flaky(state):
        counts["n"] += 1
        if counts["n"] < 3:
            raise ConnectionError("transient")
        return {"log": ["appended"], "total": counts["n"]}

    compiled = (
        GraphBuilder("writes-cleared")
        .add_channel("log", AppendChannel)
        .add_channel("total", LastValueChannel)
        .add_node("flaky", flaky, retry_policy=RetryPolicy(max_attempts=5, **FAST))
        .add_edge(START, "flaky")
        .add_edge("flaky", END)
        .compile()
    )
    result = _run(compiled, SimulatedEffects(7))
    assert counts["n"] == 3
    # Three executions, ONE committed append: failed attempts propose nothing.
    assert result.state["log"] == ["appended"]
    assert result.state["total"] == 3


def test_interrupt_is_never_retried():
    counts = {"n": 0}

    def asking(state):
        counts["n"] += 1
        interrupt({"question": "continue?"})
        return {"log": ["never"]}

    compiled = _graph(
        "asking", asking, retry_policy=RetryPolicy(max_attempts=5, **FAST)
    )
    effects = SimulatedEffects(8)
    with pytest.raises(GraphInterrupted):
        _run(compiled, effects)
    assert counts["n"] == 1  # a suspension is not a failure
    assert effects.retry_sleeps == []


def test_cancellation_is_never_retried():
    counts = {"n": 0}

    async def cancelling(state):
        counts["n"] += 1
        raise asyncio.CancelledError()

    effects = SimulatedEffects(9)
    with pytest.raises(asyncio.CancelledError):
        _run(
            _graph(
                "c", cancelling, retry_policy=RetryPolicy(max_attempts=5, **FAST)
            ),
            effects,
        )
    assert counts["n"] == 1
    assert effects.retry_sleeps == []


def test_nodes_without_a_policy_run_exactly_once():
    counts = {"n": 0}
    with pytest.raises(NodeExecutionError):
        _run(
            _graph("f", _failing(counts, ConnectionError("always"))),
            SimulatedEffects(10),
        )
    assert counts["n"] == 1
