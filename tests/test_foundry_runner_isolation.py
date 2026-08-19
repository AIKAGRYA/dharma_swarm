"""Tests for runner isolation and the promotion-gating rule."""

from __future__ import annotations

import subprocess

from dharma_swarm.foundry.runner_isolation import (
    IsolationLevel,
    IsolationPolicy,
    RunResult,
    promotion_allowed,
    run_isolated,
)


def _fake_runner(returncode=0, stdout="ok", stderr="", record=None):
    def runner(cmd, **kwargs):
        if record is not None:
            record.append(cmd)
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    return runner


def test_docker_path_uses_network_none():
    calls: list = []
    result = run_isolated(
        "pytest -q", "/tmp/wd", IsolationPolicy(),
        docker_ok=True, runner=_fake_runner(record=calls),
    )
    assert result.isolation_level == IsolationLevel.DOCKER_NONET.value
    docker_cmd = calls[0]
    assert docker_cmd[:3] == ["docker", "run", "--rm"]
    assert "none" in docker_cmd  # --network none present


def test_degraded_local_when_no_docker():
    result = run_isolated(
        "pytest -q", "/tmp/wd", IsolationPolicy(allow_degraded=True),
        docker_ok=False, runner=_fake_runner(),
    )
    assert result.isolation_level == IsolationLevel.LOCAL_RESTRICTED.value
    assert not result.blocked


def test_blocked_when_no_docker_and_degraded_disallowed():
    result = run_isolated(
        "pytest -q", "/tmp/wd", IsolationPolicy(allow_degraded=False),
        docker_ok=False, runner=_fake_runner(),
    )
    assert result.blocked
    assert result.isolation_level == IsolationLevel.BLOCKED.value


def test_promotion_requires_strong_isolation():
    strong = RunResult(0, "", "", 1.0, IsolationLevel.DOCKER_NONET.value)
    degraded = RunResult(0, "", "", 1.0, IsolationLevel.LOCAL_RESTRICTED.value)
    blocked = RunResult(-1, "", "", 0.0, IsolationLevel.BLOCKED.value, blocked=True)
    assert promotion_allowed(strong) is True
    assert promotion_allowed(degraded) is False  # degraded may explore, not confirm
    assert promotion_allowed(blocked) is False


def test_promotion_denied_on_timeout():
    timed_out = RunResult(
        -1, "", "timeout", 120.0, IsolationLevel.DOCKER_NONET.value, timed_out=True
    )
    assert promotion_allowed(timed_out) is False


def test_timeout_is_captured():
    def timeout_runner(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 1.0)

    result = run_isolated(
        "sleep 999", "/tmp/wd", IsolationPolicy(timeout_s=1.0),
        docker_ok=False, runner=timeout_runner,
    )
    assert result.timed_out
