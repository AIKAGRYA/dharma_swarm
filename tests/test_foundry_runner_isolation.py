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
        "pytest -q", "/tmp/wd", IsolationPolicy(run_as_user="65534:65534"),
        docker_ok=True, runner=_fake_runner(record=calls),
    )
    assert result.isolation_level == IsolationLevel.DOCKER_NONET.value
    docker_cmd = calls[0]
    assert docker_cmd[:3] == ["docker", "run", "--rm"]
    assert "none" in docker_cmd  # --network none present
    for expected in (
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--pids-limit",
        "--memory-swap",
        "--tmpfs",
        "--user",
        "65534:65534",
    ):
        assert expected in docker_cmd


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
    controls = {
        "network_disabled": "true",
        "readonly_rootfs": "true",
        "cap_drop_all": "true",
        "no_new_privileges": "true",
        "pids_limited": "true",
        "memory_limited": "true",
        "memory_swap_limited": "true",
        "tmpfs_limited": "true",
        "non_root_user": "true",
        "workdir_readonly": "true",
    }
    strong = RunResult(
        0, "", "", 1.0, IsolationLevel.DOCKER_NONET.value, details=controls
    )
    degraded = RunResult(0, "", "", 1.0, IsolationLevel.LOCAL_RESTRICTED.value)
    blocked = RunResult(-1, "", "", 0.0, IsolationLevel.BLOCKED.value, blocked=True)
    assert promotion_allowed(strong) is True
    assert promotion_allowed(degraded) is False  # degraded may explore, not confirm
    assert promotion_allowed(blocked) is False


def test_promotion_denied_when_any_declared_docker_control_is_missing():
    controls = {
        "network_disabled": "true",
        "readonly_rootfs": "true",
        "cap_drop_all": "true",
        "no_new_privileges": "true",
        "pids_limited": "true",
        "memory_limited": "true",
        "memory_swap_limited": "false",
        "tmpfs_limited": "true",
        "non_root_user": "true",
        "workdir_readonly": "true",
    }
    result = RunResult(
        0, "", "", 1.0, IsolationLevel.DOCKER_NONET.value, details=controls
    )
    assert promotion_allowed(result) is False


def test_promotion_denied_without_non_root_user_or_with_root_uid():
    controls = {
        "network_disabled": "true",
        "readonly_rootfs": "true",
        "cap_drop_all": "true",
        "no_new_privileges": "true",
        "pids_limited": "true",
        "memory_limited": "true",
        "memory_swap_limited": "true",
        "tmpfs_limited": "true",
        "non_root_user": "false",
        "workdir_readonly": "true",
    }
    missing = RunResult(
        0, "", "", 1.0, IsolationLevel.DOCKER_NONET.value, details=controls
    )
    assert promotion_allowed(missing) is False

    calls: list = []
    root_result = run_isolated(
        "true",
        "/tmp/wd",
        IsolationPolicy(run_as_user="0:0", readonly_workdir=True),
        docker_ok=True,
        runner=_fake_runner(record=calls),
    )
    assert ["--user", "0:0"] == calls[0][calls[0].index("--user"):][:2]
    assert promotion_allowed(
        root_result,
        IsolationPolicy(run_as_user="0:0", readonly_workdir=True),
    ) is False


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


def test_as_bash_preserves_nested_quoting():
    # Regression: a naive space-join ran `cd` bare and the payload from the
    # wrong directory (first megha smoke, 2026-08-19).
    from dharma_swarm.foundry.runner_isolation import _as_bash

    cmd = ["bash", "-c", 'cd examples/x && python -c "import evaluator; print(1)"']
    rendered = _as_bash(cmd)
    assert "'cd examples/x && python -c \"import evaluator; print(1)\"'" in rendered
    assert _as_bash("already a string") == "already a string"
