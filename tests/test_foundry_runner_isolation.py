"""Tests for the fail-closed Foundry runner isolation proof."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from dharma_swarm.foundry.evaluator import (
    Candidate,
    EvaluationRunIdentity,
    bind_isolation_proof,
    validate_isolation_proof_payload,
)
from dharma_swarm.foundry.runner_isolation import (
    IsolationLevel,
    IsolationPolicy,
    RunResult,
    promotion_allowed,
    run_isolated,
)

_PINNED_TEST_IMAGE = "registry.invalid/foundry@sha256:" + "a" * 64


def _docker_policy(**kwargs):
    return IsolationPolicy(
        docker_image=_PINNED_TEST_IMAGE,
        docker_executable=str(Path(sys.executable).resolve()),
        **kwargs,
    )


def _fake_runner(returncode=0, stdout="ok", stderr="", record=None):
    def runner(cmd, **kwargs):
        if record is not None:
            record.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    return runner


def _strong_result(tmp_path, *, returncode=0, stdout="ok", stderr=""):
    return run_isolated(
        ["python", "-m", "pytest", "-q"],
        str(tmp_path),
        _docker_policy(),
        docker_ok=True,
        runner=_fake_runner(returncode, stdout, stderr),
    )


def test_docker_path_is_argv_only_and_has_every_required_hardening_flag(tmp_path):
    calls: list = []
    candidate_argv = ["python", "-c", "print('literal')", "; touch /tmp/pwned"]
    policy = _docker_policy()
    result = run_isolated(
        candidate_argv,
        str(tmp_path),
        policy,
        docker_ok=True,
        runner=_fake_runner(record=calls),
    )

    assert result.isolation_level == IsolationLevel.DOCKER_NONET.value
    assert result.promotion_allowed is False
    docker_cmd, kwargs = calls[0]
    assert docker_cmd[:3] == [policy.docker_executable, "run", "--rm"]
    assert "--pull=never" in docker_cmd
    assert "--init" in docker_cmd
    assert "--network=none" in docker_cmd
    assert "--read-only" in docker_cmd
    assert "--cap-drop=ALL" in docker_cmd
    assert "--security-opt=no-new-privileges:true" in docker_cmd
    assert f"--pids-limit={policy.pids_limit}" in docker_cmd
    assert f"--memory={policy.memory_limit}" in docker_cmd
    assert f"--memory-swap={policy.memory_limit}" in docker_cmd
    assert f"--cpus={policy.cpu_limit}" in docker_cmd
    assert any(value.startswith("--tmpfs=/tmp:") for value in docker_cmd)
    assert f"--user={policy.run_as_user}" in docker_cmd
    assert any(value.endswith("dst=/work,readonly") for value in docker_cmd)
    assert "--workdir=/work" in docker_cmd
    assert f"--entrypoint={candidate_argv[0]}" in docker_cmd
    image_index = docker_cmd.index(policy.docker_image)
    assert docker_cmd[image_index + 1 :] == candidate_argv[1:]
    assert "@sha256:" in docker_cmd[image_index]
    assert kwargs["cwd"] is None
    assert "shell" not in kwargs


@pytest.mark.parametrize("docker_ok", [True, False])
def test_string_command_fails_closed_without_invocation(tmp_path, docker_ok):
    calls: list = []
    result = run_isolated(
        "pytest -q; touch /tmp/pwned",
        str(tmp_path),
        docker_ok=docker_ok,
        runner=_fake_runner(record=calls),
    )
    assert result.blocked
    assert result.isolation_level == IsolationLevel.BLOCKED.value
    assert "string commands are forbidden" in result.blocked_reason
    assert calls == []


def test_mutable_docker_image_fails_closed_without_invocation(tmp_path):
    calls: list = []
    result = run_isolated(
        ["pytest", "-q"],
        str(tmp_path),
        IsolationPolicy(docker_image="python:3.11-slim"),
        docker_ok=True,
        runner=_fake_runner(record=calls),
    )
    assert result.blocked
    assert "pinned by an exact sha256 digest" in result.blocked_reason
    assert calls == []


def test_default_policy_requires_composition_owned_image_pin(tmp_path):
    result = run_isolated(
        ["pytest", "-q"],
        str(tmp_path),
        IsolationPolicy(),
        docker_ok=True,
        runner=_fake_runner(),
    )
    assert result.blocked
    assert "pinned by an exact sha256 digest" in result.blocked_reason


def test_degraded_local_uses_exact_argv_and_can_never_promote(tmp_path):
    calls: list = []
    argv = ["python", "-c", "print('ok')", "$(touch /tmp/pwned)"]
    result = run_isolated(
        argv,
        str(tmp_path),
        IsolationPolicy(allow_degraded=True),
        docker_ok=False,
        runner=_fake_runner(record=calls),
    )
    assert result.isolation_level == IsolationLevel.LOCAL_RESTRICTED.value
    assert not result.blocked
    assert result.promotion_allowed is False
    assert promotion_allowed(result) is False
    local_cmd, kwargs = calls[0]
    assert local_cmd == argv
    assert kwargs["cwd"] == str(tmp_path.resolve())
    assert "shell" not in kwargs


def test_default_never_falls_back_to_local_when_docker_is_unavailable(tmp_path):
    calls: list = []
    result = run_isolated(
        ["pytest", "-q"],
        str(tmp_path),
        IsolationPolicy(),
        docker_ok=False,
        runner=_fake_runner(record=calls),
    )
    assert result.blocked
    assert result.isolation_level == IsolationLevel.BLOCKED.value
    assert result.promotion_allowed is False
    assert calls == []


def test_structural_runner_observation_is_evaluator_compatible_but_non_authoritative(
    tmp_path,
):
    result = _strong_result(tmp_path)
    candidate = Candidate(candidate_id="c1", target_id="t1", diff="+ pass")
    identity = EvaluationRunIdentity.from_execution(
        run_id="run-1",
        command=["python", "-m", "pytest", "-q"],
        output={"exit_code": result.exit_code, "stdout": result.stdout},
    )
    payload = bind_isolation_proof(
        result,
        candidate=candidate,
        evaluator_id="foundry-verifier",
        seed=7,
        run_identity=identity,
    ).to_dict()
    validated, allowed = validate_isolation_proof_payload(
        payload,
        expected_binding={
            "candidate_id": "c1",
            "target_id": "t1",
            "evaluator_id": "foundry-verifier",
            "seed": 7,
            "run_id": "run-1",
        },
    )
    assert validated == payload
    assert allowed is False
    assert payload["promotion_allowed"] is False
    assert payload["digest"].startswith("sha256:")


def test_nonzero_exit_is_valid_evidence_but_cannot_promote(tmp_path):
    result = _strong_result(tmp_path, returncode=7, stderr="failed")
    validated, allowed = validate_isolation_proof_payload(result.to_dict())
    assert validated == result.to_dict()
    assert result.exit_code == 7
    assert result.blocked is False
    assert result.promotion_allowed is False
    assert allowed is False


def test_bare_docker_label_without_hardening_facts_cannot_promote():
    result = RunResult(0, "", "", 1.0, IsolationLevel.DOCKER_NONET.value)
    assert result.promotion_allowed is False
    assert promotion_allowed(result) is False
    validated, allowed = validate_isolation_proof_payload(result.to_dict())
    assert validated == result.to_dict()
    assert allowed is False


def test_timeout_is_captured_and_cannot_promote(tmp_path):
    def timeout_runner(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 1.0, output="partial")

    result = run_isolated(
        ["sleep", "999"],
        str(tmp_path),
        _docker_policy(timeout_s=1.0),
        docker_ok=True,
        runner=timeout_runner,
    )
    assert result.timed_out
    assert result.stdout == "partial"
    assert result.promotion_allowed is False
    validated, allowed = validate_isolation_proof_payload(result.to_dict())
    assert validated == result.to_dict()
    assert allowed is False


def test_injected_runner_output_is_capped_and_incomplete_proof_is_blocked(tmp_path):
    result = run_isolated(
        ["oracle"],
        str(tmp_path),
        _docker_policy(output_limit_bytes=8),
        docker_ok=True,
        runner=_fake_runner(stdout="x" * 20, stderr="y" * 20),
    )
    assert result.stdout == "x" * 8
    assert result.stderr == "y" * 8
    assert result.details["stdout_truncated"] == "true"
    assert result.details["stderr_truncated"] == "true"
    assert result.blocked
    assert result.promotion_allowed is False


def test_default_subprocess_capture_is_stream_bounded(tmp_path):
    result = run_isolated(
        [
            sys.executable,
            "-c",
            "import os; os.write(1, b'x'*200000); os.write(2, b'y'*200000)",
        ],
        str(tmp_path),
        IsolationPolicy(allow_degraded=True, output_limit_bytes=1024),
        docker_ok=False,
    )
    assert len(result.stdout.encode()) <= 1024
    assert len(result.stderr.encode()) <= 1024
    assert result.details["stdout_truncated"] == "true"
    assert result.details["stderr_truncated"] == "true"
    assert result.blocked
    assert not result.timed_out
    assert result.promotion_allowed is False


def test_default_local_subprocess_does_not_interpret_shell_metacharacters(tmp_path):
    marker = tmp_path / "must-not-exist"
    literal = f"; touch {marker}"
    result = run_isolated(
        [sys.executable, "-c", "import sys; print(sys.argv[1])", literal],
        str(tmp_path),
        IsolationPolicy(allow_degraded=True),
        docker_ok=False,
    )
    assert result.exit_code == 0
    assert result.stdout.strip() == literal
    assert not marker.exists()


@pytest.mark.parametrize(
    "argv",
    [[], [""], ["echo", 1], ["echo", "bad\x00arg"]],
)
def test_malformed_argv_fails_closed_without_invocation(tmp_path, argv):
    calls: list = []
    result = run_isolated(
        argv,
        str(tmp_path),
        docker_ok=True,
        runner=_fake_runner(record=calls),
    )
    assert result.blocked
    assert result.isolation_level == IsolationLevel.BLOCKED.value
    assert calls == []


def test_missing_workdir_fails_closed_without_invocation(tmp_path):
    calls: list = []
    result = run_isolated(
        ["pytest", "-q"],
        str(tmp_path / "missing"),
        docker_ok=True,
        runner=_fake_runner(record=calls),
    )
    assert result.blocked
    assert "existing directory" in result.blocked_reason
    assert calls == []


@pytest.mark.parametrize(
    "policy",
    [
        _docker_policy(output_limit_bytes=0),
        _docker_policy(output_limit_bytes=1024 * 1024 + 1),
        _docker_policy(memory_limit="unlimited"),
        _docker_policy(pids_limit=0),
        _docker_policy(run_as_user="0:0"),
    ],
)
def test_unsafe_or_unbounded_policy_fails_closed(tmp_path, policy):
    result = run_isolated(
        ["pytest", "-q"],
        str(tmp_path),
        policy,
        docker_ok=True,
        runner=_fake_runner(),
    )
    assert result.blocked
    assert result.promotion_allowed is False


def test_proof_digest_changes_when_an_isolation_fact_changes(tmp_path):
    strong = _strong_result(tmp_path)
    weakened = RunResult(
        **{
            **strong.__dict__,
            "workdir_readonly": False,
        }
    )
    assert strong.to_dict()["digest"] != weakened.to_dict()["digest"]
    assert weakened.promotion_allowed is False
