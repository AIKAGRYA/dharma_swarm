"""Regression: the NATS transport must reconnect with a *bounded* backoff.

Before this change ``A2ANatsTransport.connect()`` called
``nats.connect(..., allow_reconnect=False, max_reconnect_attempts=0)``, so a
transient broker drop was immediately fatal. These tests mock ``nats.connect``
and assert the connect options now request reconnection with a finite,
positive attempt budget and a positive backoff — i.e. a simulated broker drop
would be retried rather than fatal — while the negative control proves the
retry budget stays bounded (never nats-py's ``-1`` infinite sentinel).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from dharma_swarm.a2a.nats_transport import A2ANatsTransport, NatsTransportConfig
from dharma_swarm.runtime_state import RuntimeStateStore


def _requests_bounded_reconnect(kwargs: dict[str, Any]) -> bool:
    """Verifier: do these ``nats.connect`` kwargs request bounded reconnection?

    True iff reconnection is enabled, the attempt budget is a finite positive
    int (so retries are bounded, never nats-py's ``-1`` = infinite or ``0`` =
    fatal), and the backoff wait is a positive finite number.
    """

    if kwargs.get("allow_reconnect") is not True:
        return False
    attempts = kwargs.get("max_reconnect_attempts")
    if not isinstance(attempts, int) or isinstance(attempts, bool):
        return False
    if attempts <= 0 or not math.isfinite(attempts):
        return False
    wait = kwargs.get("reconnect_time_wait")
    if not isinstance(wait, (int, float)) or isinstance(wait, bool):
        return False
    if not (wait > 0 and math.isfinite(wait)):
        return False
    return True


async def _capture_connect_kwargs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    config: NatsTransportConfig | None = None,
) -> dict[str, Any]:
    """Drive ``connect()`` with a mocked broker and return the connect kwargs."""

    captured: dict[str, Any] = {}

    async def fake_connect(*_args: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        return SimpleNamespace(jetstream=lambda: object())

    # The transport imports nats lazily inside ``connect()``; inject a stub
    # module so the mocked path works in CI environments without nats-py
    # (monkeypatch restores sys.modules afterwards).
    monkeypatch.setitem(sys.modules, "nats", SimpleNamespace(connect=fake_connect))

    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    transport = A2ANatsTransport(runtime_state=runtime, config=config)
    await transport.connect()
    return captured


@pytest.mark.asyncio
async def test_connect_requests_bounded_reconnect_with_backoff(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    kwargs = await _capture_connect_kwargs(monkeypatch, tmp_path)

    # Reconnection is now requested (was allow_reconnect=False, attempts=0 -> fatal).
    assert kwargs["allow_reconnect"] is True
    # Bounded attempts > 0: a broker drop is retried, not fatal.
    assert kwargs["max_reconnect_attempts"] > 0
    # Backoff between attempts > 0.
    assert kwargs["reconnect_time_wait"] > 0
    # Disconnect/reconnect callbacks that log are wired.
    assert callable(kwargs.get("disconnected_cb"))
    assert callable(kwargs.get("reconnected_cb"))
    # The whole policy reads as bounded reconnect + positive backoff.
    assert _requests_bounded_reconnect(kwargs) is True


@pytest.mark.asyncio
async def test_reconnect_attempts_are_bounded_not_infinite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    kwargs = await _capture_connect_kwargs(monkeypatch, tmp_path)
    attempts = kwargs["max_reconnect_attempts"]

    # Finite positive int -> bounded retries; never nats-py's -1 infinite sentinel.
    assert isinstance(attempts, int) and not isinstance(attempts, bool)
    assert attempts > 0
    assert attempts != -1
    assert math.isfinite(attempts)


@pytest.mark.asyncio
async def test_reconnect_policy_is_configurable_via_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = NatsTransportConfig(max_reconnect_attempts=12, reconnect_time_wait_s=0.5)
    kwargs = await _capture_connect_kwargs(monkeypatch, tmp_path, config=config)

    assert kwargs["max_reconnect_attempts"] == 12
    assert kwargs["reconnect_time_wait"] == 0.5
    assert _requests_bounded_reconnect(kwargs) is True


def test_bounded_predicate_rejects_unbounded_configs_negative_control() -> None:
    """Negative control: the adversarial 'unbounded / fatal' cases must still fail.

    The verifier used by the green test must REJECT infinite (-1), no-reconnect
    (0), reconnect-disabled, and zero-backoff configurations. If any of these
    were shipped, the green assertions above would correctly fail.
    """

    # -1 == nats-py infinite reconnect (unbounded) -> must fail the bound check.
    assert _requests_bounded_reconnect(
        {"allow_reconnect": True, "max_reconnect_attempts": -1, "reconnect_time_wait": 2.0}
    ) is False
    # 0 == no reconnect / fatal -> must fail.
    assert _requests_bounded_reconnect(
        {"allow_reconnect": True, "max_reconnect_attempts": 0, "reconnect_time_wait": 2.0}
    ) is False
    # Reconnection disabled -> must fail.
    assert _requests_bounded_reconnect(
        {"allow_reconnect": False, "max_reconnect_attempts": 60, "reconnect_time_wait": 2.0}
    ) is False
    # No backoff -> must fail.
    assert _requests_bounded_reconnect(
        {"allow_reconnect": True, "max_reconnect_attempts": 60, "reconnect_time_wait": 0}
    ) is False
    # Sanity: a bounded, backed-off config passes.
    assert _requests_bounded_reconnect(
        {"allow_reconnect": True, "max_reconnect_attempts": 60, "reconnect_time_wait": 2.0}
    ) is True
