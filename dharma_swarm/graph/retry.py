"""Per-node retry policy for the neutral graph core (LG24 parity slice).

Mirrors ``langgraph.types.RetryPolicy`` (1.2.4, ``site-packages/langgraph/
types.py:416``) field-for-field and default-for-default, plus the runtime
selection/backoff/give-up arithmetic of ``langgraph/pregel/_retry.py``:

* ``max_attempts`` counts the FIRST attempt (3 = one run + two retries).
* Give up when ``failed_attempts >= max_attempts``.
* ``interval = min(max_interval, initial_interval * backoff_factor ** (k-1))``
  where ``k`` is the 1-indexed FAILED-attempt count.
* Jitter is ADDITIVE ``uniform(0, 1)``, not proportional.
* A tuple of policies selects the FIRST policy whose ``retry_on`` matches.

Deviations from the reference, recorded deliberately:

* ``default_retry_on`` omits langgraph's ``httpx``/``requests`` 5xx branches:
  the neutral engine has no HTTP dependencies. Every other classification is
  identical.
* :class:`~dharma_swarm.graph.errors.NodeTimeoutError` is classified retryable
  FIRST. langgraph gets this for free because its ``NodeTimeoutError`` derives
  from bare ``Exception``; ours derives from ``GraphRuntimeError`` (a
  ``RuntimeError``, which the shared deterministic-error tuple rejects), so the
  early check restores identical observable behavior.

The jitter draw is taken from ``effects.random()`` and the wait from
``effects.retry_sleep()`` (DST law: no bare ``random``/``asyncio.sleep`` in the
engine, so a seeded run replays byte-identically and never really sleeps).

claim_mode: candidate / test_only. Not wired into production dispatch.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Sequence, TypeVar

from dharma_swarm.graph.effects import provider_retry_sleep
from dharma_swarm.graph.errors import NodeExecutionError, NodeTimeoutError
from dharma_swarm.graph.interrupts import GraphInterrupt

__all__ = [
    "RetryPolicy",
    "RetryPolicySpec",
    "backoff_interval",
    "default_retry_on",
    "normalize_retry_policies",
    "retry_candidate",
    "retry_sleep_seconds",
    "run_with_retry",
    "select_retry_policy",
    "should_retry_on",
]

_T = TypeVar("_T")


# langgraph 1.2.4 ``default_retry_on``: deterministic programmer errors are
# never worth retrying; anything else is assumed transient.
_NON_RETRYABLE: tuple[type[BaseException], ...] = (
    ValueError,
    TypeError,
    ArithmeticError,
    ImportError,
    LookupError,
    NameError,
    SyntaxError,
    RuntimeError,
    ReferenceError,
    StopIteration,
    StopAsyncIteration,
    OSError,
)


def default_retry_on(exc: Exception) -> bool:
    """Default retry predicate (langgraph 1.2.4 ``default_retry_on`` parity)."""
    if isinstance(exc, NodeTimeoutError):
        # langgraph's NodeTimeoutError inherits bare Exception precisely so the
        # default policy retries it; ours inherits GraphRuntimeError, so the
        # RuntimeError rejection below must not claim it.
        return True
    if isinstance(exc, ConnectionError):
        return True
    if isinstance(exc, _NON_RETRYABLE):
        return False
    return True


RetryOn = (
    type[Exception] | Sequence[type[Exception]] | Callable[[Exception], bool]
)


@dataclass(frozen=True)
class RetryPolicy:
    """Configuration for retrying nodes (``langgraph.types.RetryPolicy`` parity).

    ``max_attempts`` INCLUDES the first attempt, matching the reference: a
    policy with ``max_attempts=3`` executes the node at most three times.
    """

    initial_interval: float = 0.5
    """Amount of time that must elapse before the first retry, in seconds."""
    backoff_factor: float = 2.0
    """Multiplier by which the interval increases after each retry."""
    max_interval: float = 128.0
    """Maximum amount of time that may elapse between retries, in seconds."""
    max_attempts: int = 3
    """Maximum number of attempts before giving up, INCLUDING the first."""
    jitter: bool = True
    """Whether to add random jitter to the interval between retries."""
    retry_on: RetryOn = field(default=default_retry_on)
    """Exception class, sequence of classes, or ``(exc) -> bool`` predicate."""


RetryPolicySpec = RetryPolicy | Sequence[RetryPolicy] | None


def normalize_retry_policies(policies: RetryPolicySpec) -> tuple[RetryPolicy, ...]:
    """Normalize the ``retry_policy=`` argument to a canonical tuple.

    ``None`` means "no retry" (langgraph parity: a task without a policy runs
    exactly once). A single policy is wrapped; a sequence is preserved IN ORDER
    because selection is first-match.
    """
    if policies is None:
        return ()
    if isinstance(policies, RetryPolicy):
        return (policies,)
    normalized = tuple(policies)
    for entry in normalized:
        if not isinstance(entry, RetryPolicy):
            raise TypeError(
                "retry_policy must be a RetryPolicy, a sequence of "
                f"RetryPolicy, or None; received {type(entry).__name__} "
                "(fail closed)"
            )
    return normalized


def should_retry_on(policy: RetryPolicy, exc: Exception) -> bool:
    """Whether ``policy`` claims ``exc`` (``_should_retry_on`` parity).

    Class / sequence-of-classes / callable-predicate forms are all accepted;
    anything else raises ``TypeError`` exactly as the reference does.
    """
    retry_on: Any = policy.retry_on
    if isinstance(retry_on, type) and issubclass(retry_on, BaseException):
        return isinstance(exc, retry_on)
    if isinstance(retry_on, Sequence) and not isinstance(retry_on, (str, bytes)):
        return isinstance(exc, tuple(retry_on))
    if callable(retry_on):
        return bool(retry_on(exc))
    raise TypeError(
        "retry_on must be an Exception class, a list or tuple of Exception "
        "classes, or a callable"
    )


def select_retry_policy(
    policies: RetryPolicySpec, exc: Exception
) -> RetryPolicy | None:
    """The FIRST policy whose ``retry_on`` matches ``exc``, else ``None``.

    First-match (not best-match, not last-match) is the reference semantics:
    ``for policy in retry_policy: if _should_retry_on(policy, exc): break``.
    """
    for policy in normalize_retry_policies(policies):
        if should_retry_on(policy, exc):
            return policy
    return None


def backoff_interval(policy: RetryPolicy, failed_attempts: int) -> float:
    """Base (pre-jitter) wait after ``failed_attempts`` failures, 1-indexed.

    ``failed_attempts=1`` is the wait after the FIRST failure, so the first
    wait is ``initial_interval`` and each later wait multiplies by
    ``backoff_factor`` until ``max_interval`` caps it.
    """
    if failed_attempts < 1:
        raise ValueError(
            f"failed_attempts is 1-indexed (received {failed_attempts!r})"
        )
    return min(
        policy.max_interval,
        policy.initial_interval * (policy.backoff_factor ** (failed_attempts - 1)),
    )


def retry_sleep_seconds(
    policy: RetryPolicy, failed_attempts: int, effects: Any
) -> float:
    """Backoff plus optional ADDITIVE ``uniform(0, 1)`` jitter.

    The draw goes through ``effects.random()`` so a seeded run reproduces the
    exact sleep sequence (DST law); a provider without the seam is a
    programming error, not a silent fallback to global entropy.
    """
    interval = backoff_interval(policy, failed_attempts)
    if not policy.jitter:
        return interval
    return interval + effects.random().uniform(0.0, 1.0)


def retry_candidate(exc: BaseException) -> Exception:
    """The exception ``retry_on`` should be evaluated against.

    The executor wraps node failures in
    :class:`~dharma_swarm.graph.errors.NodeExecutionError`; the reference
    evaluates the policy against what the NODE raised, so unwrap one level of
    engine bookkeeping before matching.
    """
    if isinstance(exc, NodeExecutionError) and isinstance(exc.__cause__, Exception):
        return exc.__cause__
    if isinstance(exc, Exception):
        return exc
    raise TypeError(
        f"retry policies never see BaseException {type(exc).__name__} "
        "(control-flow signals are re-raised before policy selection)"
    )


async def run_with_retry(
    policies: RetryPolicySpec,
    effects: Any,
    run_attempt: Callable[[], Coroutine[Any, Any, _T]],
) -> _T:
    """Run ``run_attempt()`` under a declared first-match retry ladder.

    ``run_attempt`` is a zero-arg factory for one ATTEMPT's coroutine (the
    executor's own per-attempt frame push + node run + timeout envelope,
    closed over its arguments) so this function owns only the ladder's
    select/count/backoff arithmetic, not attempt execution itself.

    :class:`~dharma_swarm.graph.interrupts.GraphInterrupt` and
    ``asyncio.CancelledError`` are control-flow signals, never failures, and
    propagate unretried (``GraphBubbleUp`` parity / step-teardown ownership).
    """
    failed = 0
    while True:
        try:
            return await run_attempt()
        except (GraphInterrupt, asyncio.CancelledError):
            raise
        except Exception as exc:
            policy = select_retry_policy(policies, retry_candidate(exc))
            if policy is None:
                raise
            failed += 1
            if failed >= policy.max_attempts:
                # max_attempts INCLUDES the first attempt (reference parity).
                raise
            await provider_retry_sleep(
                effects, retry_sleep_seconds(policy, failed, effects)
            )
