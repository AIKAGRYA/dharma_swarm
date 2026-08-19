"""Per-node hard/idle timeout + heartbeat (LG25) — dharmagraph-engine-2026-07.

Covers: ``TimeoutPolicy`` coercion/validation, the hard (``run_timeout``) bound
that no amount of progress can extend, the idle bound that expires without
progress, heartbeat refresh extending only the idle bound, timeout composed
with a retry ladder (fresh deadlines per attempt), step atomicity under a
timed-out superstep, and ``heartbeat()`` as a no-op outside a timed attempt.

No LangGraph imports here — the two-arm differential lives in the gauntlet's
``seeded_node_timeout`` workload.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import pytest

from dharma_swarm.graph.channels import AppendChannel, LastValueChannel
from dharma_swarm.graph.compiler import GraphBuilder
from dharma_swarm.graph.effects import SimulatedEffects
from dharma_swarm.graph.errors import GraphRuntimeError, NodeTimeoutError
from dharma_swarm.graph.retry import RetryPolicy, default_retry_on
from dharma_swarm.graph.timeouts import TimeoutPolicy, current_watchdog, heartbeat
from dharma_swarm.graph.types import END, START

TIGHT = 0.05  # a bound a stuck node trips
GENEROUS = 5.0  # a bound a working node never trips
STUCK = 30.0  # a node that never finishes on its own


def _graph(fn, **node_kwargs: Any):
    return (
        GraphBuilder("timeout")
        .add_channel("log", AppendChannel)
        .add_node("worker", fn, **node_kwargs)
        .add_edge(START, "worker")
        .add_edge("worker", END)
        .compile()
    )


def _run(compiled, seed: int = 1):
    return asyncio.run(
        compiled.invoke(input={"log": []}, effects=SimulatedEffects(seed))
    )


async def _hung(state):
    await asyncio.sleep(STUCK)
    return {"log": ["hung"]}


# -- policy shape -------------------------------------------------------


def test_timeout_policy_mirrors_langgraph_field_names():
    policy = TimeoutPolicy(
        run_timeout=1.5, idle_timeout=0.5, refresh_on="heartbeat"
    )
    assert (policy.run_timeout, policy.idle_timeout) == (1.5, 0.5)
    assert policy.refresh_on == "heartbeat"
    assert TimeoutPolicy().refresh_on == "auto"


def test_timeout_policy_coerce_normalizes_and_fails_closed():
    assert TimeoutPolicy.coerce(None) is None
    bare = TimeoutPolicy.coerce(2)
    assert bare == TimeoutPolicy(run_timeout=2.0, refresh_on="auto")
    delta = TimeoutPolicy.coerce(TimeoutPolicy(idle_timeout=timedelta(seconds=3)))
    assert delta == TimeoutPolicy(idle_timeout=3.0)
    with pytest.raises(ValueError, match="must be greater than 0"):
        TimeoutPolicy.coerce(0)
    with pytest.raises(ValueError, match="run_timeout, idle_timeout, or both"):
        TimeoutPolicy.coerce(TimeoutPolicy())
    with pytest.raises(ValueError, match="refresh_on"):
        TimeoutPolicy.coerce(
            TimeoutPolicy(run_timeout=1.0, refresh_on="whenever")  # type: ignore[arg-type]
        )


def test_node_timeout_error_is_retryable_but_not_an_os_error():
    error = NodeTimeoutError("worker", 0.2, kind="run", run_timeout=0.1)
    assert isinstance(error, GraphRuntimeError)
    # langgraph parity: NOT a builtin TimeoutError (an OSError), so the default
    # retry predicate can still claim it.
    assert not isinstance(error, TimeoutError)
    assert default_retry_on(error) is True
    assert (error.kind, error.timeout, error.idle_timeout) == ("run", 0.1, None)
    with pytest.raises(ValueError, match="idle_timeout is required"):
        NodeTimeoutError("worker", 0.2, kind="idle")
    with pytest.raises(ValueError, match="kind must be"):
        NodeTimeoutError("worker", 0.2, kind="wall")  # type: ignore[arg-type]


# -- hard bound ---------------------------------------------------------


def test_hard_timeout_fails_superstep_with_typed_error():
    with pytest.raises(NodeTimeoutError) as exc_info:
        _run(_graph(_hung, timeout=TimeoutPolicy(run_timeout=TIGHT)))
    error = exc_info.value
    assert error.kind == "run"
    assert error.node == "worker"
    assert error.run_timeout == TIGHT
    assert error.elapsed >= TIGHT


def test_fast_node_completes_under_the_same_hard_bound():
    async def fast(state):
        await asyncio.sleep(0.001)
        return {"log": ["fast"]}

    result = _run(_graph(fast, timeout=TimeoutPolicy(run_timeout=GENEROUS)))
    assert result.state["log"] == ["fast"]


def test_heartbeats_never_extend_the_hard_bound():
    async def busy_but_alive(state):
        while True:
            await asyncio.sleep(0.005)
            heartbeat()

    with pytest.raises(NodeTimeoutError) as exc_info:
        _run(
            _graph(
                busy_but_alive,
                timeout=TimeoutPolicy(
                    run_timeout=TIGHT, idle_timeout=GENEROUS, refresh_on="heartbeat"
                ),
            )
        )
    assert exc_info.value.kind == "run"


# -- idle bound ---------------------------------------------------------


def test_idle_timeout_expires_without_heartbeat():
    with pytest.raises(NodeTimeoutError) as exc_info:
        _run(
            _graph(
                _hung,
                timeout=TimeoutPolicy(idle_timeout=TIGHT, refresh_on="heartbeat"),
            )
        )
    error = exc_info.value
    assert error.kind == "idle"
    assert error.idle_timeout == TIGHT
    assert error.run_timeout is None


def test_heartbeat_refresh_extends_idle_deadline_not_hard():
    async def beating(state):
        # Total runtime (~0.15s) far exceeds the idle bound but stays inside
        # the hard bound: only a working refresh can let this finish.
        for _ in range(30):
            await asyncio.sleep(0.005)
            heartbeat()
        return {"log": ["beating"]}

    result = _run(
        _graph(
            beating,
            timeout=TimeoutPolicy(
                idle_timeout=TIGHT, run_timeout=GENEROUS, refresh_on="heartbeat"
            ),
        )
    )
    assert result.state["log"] == ["beating"]


def test_heartbeat_outside_a_timed_attempt_is_a_no_op():
    assert current_watchdog() is None
    heartbeat()  # must not raise

    seen: list[Any] = []

    def untimed(state):
        seen.append(current_watchdog())
        heartbeat()
        return {"log": ["untimed"]}

    result = _run(_graph(untimed))
    assert result.state["log"] == ["untimed"]
    assert seen == [None]  # no watchdog installed for an untimed node


# -- composition with retry + atomicity ---------------------------------


def test_timeout_then_retry_succeeds_and_clears_first_attempt_writes():
    attempts = {"n": 0}

    async def flapping(state):
        attempts["n"] += 1
        if attempts["n"] == 1:
            await asyncio.sleep(STUCK)
        return {"log": ["flapping"], "attempt": attempts["n"]}

    compiled = (
        GraphBuilder("timeout-retry")
        .add_channel("log", AppendChannel)
        .add_channel("attempt", LastValueChannel)
        .add_node(
            "worker",
            flapping,
            timeout=TimeoutPolicy(run_timeout=TIGHT),
            retry_policy=RetryPolicy(
                retry_on=(NodeTimeoutError,),
                initial_interval=0.001,
                max_attempts=2,
                jitter=False,
            ),
        )
        .add_edge(START, "worker")
        .add_edge("worker", END)
        .compile()
    )
    result = _run(compiled)
    assert attempts["n"] == 2
    # The timed-out attempt contributed nothing; exactly one append committed.
    assert result.state["log"] == ["flapping"]
    assert result.state["attempt"] == 2


def test_default_policy_retries_a_timed_out_node():
    attempts = {"n": 0}

    async def flapping(state):
        attempts["n"] += 1
        if attempts["n"] == 1:
            await asyncio.sleep(STUCK)
        return {"log": ["flapping"]}

    result = _run(
        _graph(
            flapping,
            timeout=TimeoutPolicy(run_timeout=TIGHT),
            retry_policy=RetryPolicy(
                initial_interval=0.001, max_attempts=2, jitter=False
            ),
        )
    )
    assert attempts["n"] == 2
    assert result.state["log"] == ["flapping"]


def test_exhausted_timeout_retries_reraise_the_timeout():
    attempts = {"n": 0}

    async def always_hung(state):
        attempts["n"] += 1
        await asyncio.sleep(STUCK)

    effects = SimulatedEffects(2)
    compiled = _graph(
        always_hung,
        timeout=TimeoutPolicy(run_timeout=TIGHT),
        retry_policy=RetryPolicy(
            initial_interval=0.001, max_attempts=2, jitter=False
        ),
    )
    with pytest.raises(NodeTimeoutError):
        asyncio.run(compiled.invoke(input={"log": []}, effects=effects))
    assert attempts["n"] == 2
    assert effects.retry_sleeps == [0.001]


def test_timed_out_superstep_yields_no_result_and_no_timed_node_writes():
    checkpoints: dict[int, Any] = {}

    async def sibling(state):
        return {"log": ["sibling"]}

    compiled = (
        GraphBuilder("timeout-atomicity")
        .add_channel("log", AppendChannel)
        .add_node("worker", _hung, timeout=TimeoutPolicy(run_timeout=TIGHT))
        .add_node("sibling", sibling)
        .add_edge(START, "worker")
        .add_edge(START, "sibling")
        .add_edge("worker", END)
        .add_edge("sibling", END)
        .compile()
    )
    error = None
    try:
        asyncio.run(
            compiled.invoke(
                input={"log": []},
                effects=SimulatedEffects(3),
                on_checkpoint=lambda cp: checkpoints.__setitem__(cp.superstep, cp),
            )
        )
    except NodeTimeoutError as exc:
        error = exc
    assert error is not None
    # The run raises and returns no result; the timed-out node's own writes
    # never appear anywhere. The succeeded sibling's proposal rides the error
    # as a pending write instead (pre-existing LG06 failure-resume parity).
    assert set(checkpoints) == {0}
    assert "hung" not in checkpoints[0].channels["log"]["items"]
    assert error.succeeded_pull_nodes == ("sibling",)
