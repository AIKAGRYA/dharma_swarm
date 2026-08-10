from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dharma_swarm.forge_v1.forge_v2 import pr_suite_execution as execution


def _runtime_script(path: Path, body: str) -> Path:
    path.write_text(f"#!{sys.executable}\n" + body, encoding="utf-8")
    path.chmod(0o700)
    return path


def _profile(runtime: Path, **changes: object) -> execution.ExecutionProfile:
    values: dict[str, object] = {
        "profile_id": "pytest-container-boundary",
        "backend": "docker",
        "runtime": str(runtime),
        "image": f"example.invalid/forge-evaluator@sha256:{'a' * 64}",
        "user": "65534:65534",
        "python": "/usr/local/bin/python",
        "output_limit_bytes": 4096,
    }
    values.update(changes)
    return execution.ExecutionProfile(**values)


def _write_profile(path: Path, profile: execution.ExecutionProfile) -> None:
    payload = profile.to_mapping()
    payload["profile_sha256"] = profile.sha256
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)


def test_missing_explicit_profile_and_backend_refuse(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(execution.PROFILE_ENV, raising=False)
    with pytest.raises(execution.IsolationUnavailable, match="explicit"):
        execution.resolve_execution_profile(None)

    unavailable = _profile(tmp_path / "missing-docker")
    with pytest.raises(execution.IsolationUnavailable, match="runtime unavailable"):
        execution.ContainerExecutor(
            unavailable,
            workspace_root=tmp_path / "work",
            total_timeout_seconds=5,
        )


def test_profile_digest_tamper_is_rejected(tmp_path: Path) -> None:
    runtime = _runtime_script(tmp_path / "runtime", "raise SystemExit(0)\n")
    profile = _profile(runtime)
    profile_path = tmp_path / "profile.json"
    _write_profile(profile_path, profile)
    assert execution.load_execution_profile(profile_path).sha256 == profile.sha256

    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    payload["memory_bytes"] = int(payload["memory_bytes"]) * 2
    profile_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(execution.ProfileTampered, match="digest mismatch"):
        execution.load_execution_profile(profile_path)


@pytest.mark.parametrize(
    "target",
    ["/tmp/test_escape.py", "../test_escape.py", "tests\\test_escape.py", "tests/test_\x00escape.py", "C:/test.py"],
)
def test_target_path_escape_shapes_are_rejected(tmp_path: Path, target: str) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    with pytest.raises(execution.UnsafeTargetPath):
        execution.validated_target_path(target, checkout)


def test_symlink_escape_is_rejected_before_materialization(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    outside = tmp_path / "outside"
    checkout.mkdir()
    outside.mkdir()
    (checkout / "tests").symlink_to(outside, target_is_directory=True)

    with pytest.raises(execution.UnsafeTargetPath):
        execution.safe_materialization_path(checkout, "tests/test_escape.py")
    assert not (outside / "test_escape.py").exists()


def test_internal_final_symlink_cannot_be_materialized(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "tests").mkdir()
    protected = checkout / "protected.txt"
    protected.write_text("unchanged", encoding="utf-8")
    (checkout / "tests" / "test_escape.py").symlink_to("../protected.txt")

    with pytest.raises(execution.UnsafeTargetPath):
        execution.safe_materialization_path(checkout, "tests/test_escape.py")
    with pytest.raises(execution.UnsafeTargetPath):
        execution.materialize_text(checkout, "tests/test_escape.py", "overwritten")

    assert protected.read_text(encoding="utf-8") == "unchanged"


def test_validator_receipt_requires_trusted_signature() -> None:
    trusted_key = Ed25519PrivateKey.generate()
    attacker_key = Ed25519PrivateKey.generate()
    trusted_public = trusted_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    body = {"schema": "example", "status": "fail_to_pass_validated"}
    signed = execution.sign_validator_receipt(
        body,
        signing_key=trusted_key,
        key_id="validator-a",
        nonce="validator-request-0001",
    )
    assert execution.verify_validator_receipt_signature(
        signed,
        trusted_public_keys={"validator-a": trusted_public},
    )["nonce"] == "validator-request-0001"

    forged = execution.sign_validator_receipt(
        body,
        signing_key=attacker_key,
        key_id="validator-a",
        nonce="validator-request-0001",
    )
    with pytest.raises(execution.ProfileTampered, match="not trusted"):
        execution.verify_validator_receipt_signature(
            forged,
            trusted_public_keys={"validator-a": trusted_public},
        )


def test_runtime_environment_drops_sentinel_secret(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime = _runtime_script(
        tmp_path / "fake-docker",
        """import os, sys
if len(sys.argv) > 1 and sys.argv[1] in ('info', 'image'):
    raise SystemExit(0)
print('secret-present' if os.environ.get('OPENAI_API_KEY') else 'secret-absent')
print('argv-secret-present' if any('sentinel-value' in arg for arg in sys.argv) else 'argv-secret-absent')
""",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sentinel-value")
    workspace = tmp_path / "workspace"
    executor = execution.ContainerExecutor(
        _profile(runtime),
        workspace_root=workspace,
        total_timeout_seconds=5,
    )

    result = executor.run(["/usr/bin/true"], cwd=workspace, timeout_seconds=2)

    assert result.passed
    assert "secret-absent" in result.stdout
    assert "argv-secret-absent" in result.stdout
    assert "sentinel-value" not in result.stdout + result.stderr


def test_container_command_has_non_negotiable_isolation_and_limits(tmp_path: Path) -> None:
    runtime = _runtime_script(tmp_path / "fake-docker", "raise SystemExit(0)\n")
    workspace = tmp_path / "workspace"
    executor = execution.ContainerExecutor(
        _profile(runtime),
        workspace_root=workspace,
        total_timeout_seconds=5,
        probe_backend=False,
    )
    command = executor.container_command(
        ["/usr/local/bin/python", "-m", "pytest", "tests/test_one.py"],
        cwd=workspace,
        cidfile=tmp_path / "container.cid",
        interactive=False,
    )

    for flag in (
        "--read-only",
        "--network=none",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        "--pids-limit",
        "--memory",
        "--memory-swap",
        "--cpus",
        "--ulimit",
        "--tmpfs",
        "--user",
    ):
        assert flag in command
    assert "65534:65534" in command
    assert "--pull=never" in command
    assert executor.profile.image in command
    mounts = [command[index + 1] for index, value in enumerate(command) if value == "--mount"]
    workspace_mount = next(value for value in mounts if "dst=/workspace" in value)
    assert workspace_mount.endswith("dst=/workspace")
    assert not workspace_mount.endswith(",rw")


def test_source_mirror_mount_is_readonly_and_only_added_when_referenced(tmp_path: Path) -> None:
    runtime = _runtime_script(tmp_path / "fake-docker", "raise SystemExit(0)\n")
    workspace = tmp_path / "workspace"
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    executor = execution.ContainerExecutor(
        _profile(runtime),
        workspace_root=workspace,
        source_roots=[mirror],
        total_timeout_seconds=5,
        probe_backend=False,
    )
    command = executor.container_command(
        ["git", "clone", str(mirror), str(workspace / "repo")],
        cwd=workspace,
        cidfile=tmp_path / "container.cid",
        interactive=False,
    )
    mounts = [command[index + 1] for index, value in enumerate(command) if value == "--mount"]

    assert any(value.endswith("dst=/input0,readonly") for value in mounts)


def test_output_flood_is_bounded_and_fails_closed(tmp_path: Path) -> None:
    runtime = _runtime_script(
        tmp_path / "flood-runtime",
        """import sys, time
if len(sys.argv) > 1 and sys.argv[1] in ('info', 'image'):
    raise SystemExit(0)
if len(sys.argv) > 1 and sys.argv[1] == 'rm':
    raise SystemExit(0)
sys.stdout.write('x' * 100000)
sys.stdout.flush()
time.sleep(30)
""",
    )
    workspace = tmp_path / "workspace"
    executor = execution.ContainerExecutor(
        _profile(runtime, output_limit_bytes=1024),
        workspace_root=workspace,
        total_timeout_seconds=5,
    )

    result = executor.run(["/usr/bin/true"], cwd=workspace, timeout_seconds=3)

    assert result.output_limit_exceeded
    assert not result.passed
    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= 1024


def test_runtime_that_never_reads_large_stdin_still_obeys_deadline(tmp_path: Path) -> None:
    runtime = _runtime_script(
        tmp_path / "stdin-stall-runtime",
        """import sys, time
if len(sys.argv) > 1 and sys.argv[1] in ('info', 'image'):
    raise SystemExit(0)
if len(sys.argv) > 1 and sys.argv[1] == 'rm':
    raise SystemExit(0)
time.sleep(30)
""",
    )
    workspace = tmp_path / "workspace"
    executor = execution.ContainerExecutor(
        _profile(runtime),
        workspace_root=workspace,
        total_timeout_seconds=3,
    )

    started = time.monotonic()
    result = executor.run(
        ["git", "apply", "-"],
        cwd=workspace,
        timeout_seconds=1,
        stdin="x" * (1024 * 1024),
    )

    assert result.timed_out
    assert time.monotonic() - started < 4.0


def test_timeout_kills_runtime_process_group_and_descendant(tmp_path: Path) -> None:
    sentinel = tmp_path / "descendant-survived"
    runtime = _runtime_script(
        tmp_path / "descendant-runtime",
        f"""import pathlib, subprocess, sys, time
if len(sys.argv) > 1 and sys.argv[1] in ('info', 'image'):
    raise SystemExit(0)
if len(sys.argv) > 1 and sys.argv[1] == 'rm':
    raise SystemExit(0)
child = "import pathlib,time; time.sleep(1.8); pathlib.Path({str(sentinel)!r}).write_text('escaped')"
subprocess.Popen([sys.executable, '-c', child])
time.sleep(30)
""",
    )
    workspace = tmp_path / "workspace"
    executor = execution.ContainerExecutor(
        _profile(runtime),
        workspace_root=workspace,
        total_timeout_seconds=3,
    )

    started = time.monotonic()
    result = executor.run(["/usr/bin/true"], cwd=workspace, timeout_seconds=1)
    time.sleep(2.0)

    assert result.timed_out
    assert time.monotonic() - started < 4.0
    assert not sentinel.exists()
