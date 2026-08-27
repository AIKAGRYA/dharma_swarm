"""Tests for the stable immutable-release launch boundary."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "runtime" / "dharma_swarm_release_runner.sh"
PIN = "a" * 40


def _git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _fake_release(tmp_path: Path) -> tuple[Path, Path]:
    release = tmp_path / "release"
    python = release / ".venv" / "bin" / "python"
    loader = release / "scripts" / "load_runtime_env.sh"
    admission = release / "dharma_swarm" / "runtime_admission.py"
    python.parent.mkdir(parents=True)
    loader.parent.mkdir(parents=True)
    admission.parent.mkdir(parents=True)
    python.write_text(
        "#!/usr/bin/env bash\n"
        'printf \'%s\\n\' "$*" >> "$(dirname "$0")/../runner_calls.log"\n'
        "printf 'github=%s runtime=%s\\n' \"${GITHUB_TOKEN-<unset>}\" "
        '"${TEST_RUNTIME_ENV_LOADED-<unset>}" >> '
        '"$(dirname "$0")/../runner_env.log"\n',
        encoding="utf-8",
    )
    python.chmod(0o755)
    loader.write_text(
        'if [[ -n "${TEST_RUNTIME_LOADER_LOG-}" ]]; then\n'
        "    printf 'loaded\\n' >> \"${TEST_RUNTIME_LOADER_LOG}\"\n"
        "fi\n"
        "export TEST_RUNTIME_ENV_LOADED=1\n",
        encoding="utf-8",
    )
    admission.write_text("# fake admission target\n", encoding="utf-8")
    (release / ".gitignore").write_text(".venv/\n*.pyc\n", encoding="utf-8")
    _git(release, "init", "-b", "main")
    _git(release, "add", ".gitignore", "dharma_swarm", "scripts")
    _git(
        release,
        "-c",
        "user.name=Runtime Runner Test",
        "-c",
        "user.email=runtime-runner@example.invalid",
        "commit",
        "-m",
        "sealed release",
    )
    return release, python


def test_release_runner_uses_pinned_release_interpreter_and_guard() -> None:
    text = RUNNER.read_text(encoding="utf-8")

    assert "${release_root}/.venv/bin/python" in text
    assert "DHARMA_RUNTIME_EXPECTED_COMMIT" in text
    assert "DHARMA_PYTHON must be the release-local .venv/bin/python" in text
    assert "ignored import bytecode" in text
    assert '"${runtime_python}" -B -I -S' in text
    assert text.index("dharma_swarm/runtime_admission.py") < text.index(
        'source "${runtime_env_helper}"'
    )
    assert text.index("dharma_swarm/runtime_admission.py") < text.index(
        "dharma_swarm.runtime_release_entrypoint orchestrate-live"
    )
    assert "a2a-inbox-bridge" in text
    assert "codex-composer-semantic-responder" in text
    assert "bridge_env=(" in text
    assert "env -i" in text
    assert '"PYTHONUNBUFFERED=1"' in text
    assert "uv run" not in text
    assert "/Users/dhyana/dharma_swarm/.venv" not in text
    assert "/Users/dhyana/dharma_swarm/.env" not in text


def test_release_runner_executes_guard_before_live_command(tmp_path: Path) -> None:
    release, _python = _fake_release(tmp_path)
    call_log = release / ".venv" / "runner_calls.log"
    environment = os.environ.copy()
    environment.update(
        {
            "DHARMA_RELEASE_ROOT": str(release),
            "DHARMA_RUNTIME_EXPECTED_COMMIT": PIN,
        }
    )

    result = subprocess.run(
        ["/bin/bash", str(RUNNER)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert calls == [
        (
            f"-B -I -S {release}/dharma_swarm/runtime_admission.py "
            f"--repo {release} --expected-commit {PIN}"
        ),
        "-B -I -m dharma_swarm.runtime_release_entrypoint orchestrate-live",
    ]

    call_log.unlink()
    verify = subprocess.run(
        ["/bin/bash", str(RUNNER), "--verify-only"],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert verify.returncode == 0, verify.stderr
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        (
            f"-B -I -S {release}/dharma_swarm/runtime_admission.py "
            f"--repo {release} --expected-commit {PIN}"
        )
    ]


def test_release_runner_dispatches_bridge_through_the_same_interpreter(
    tmp_path: Path,
) -> None:
    release, _python = _fake_release(tmp_path)
    call_log = release / ".venv" / "runner_calls.log"
    env_log = release / ".venv" / "runner_env.log"
    environment = os.environ.copy()
    environment.update(
        {
            "DHARMA_RELEASE_ROOT": str(release),
            "DHARMA_RUNTIME_EXPECTED_COMMIT": PIN,
            "GITHUB_TOKEN": "must-not-reach-bridge",
        }
    )

    result = subprocess.run(
        [
            "/bin/bash",
            str(RUNNER),
            "a2a-inbox-bridge",
            "--agent-uid",
            "codex_composer",
            "--consumer",
            "codex_composer_inbox",
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        (
            f"-B -I -S {release}/dharma_swarm/runtime_admission.py "
            f"--repo {release} --expected-commit {PIN}"
        ),
        (
            "-B -I -m dharma_swarm.runtime_release_entrypoint "
            "a2a-inbox-bridge --agent-uid codex_composer "
            "--consumer codex_composer_inbox"
        ),
    ]
    assert env_log.read_text(encoding="utf-8").splitlines() == [
        "github=must-not-reach-bridge runtime=<unset>",
        "github=<unset> runtime=<unset>",
    ]


def test_release_runner_dispatches_semantic_responder_after_admission(
    tmp_path: Path,
) -> None:
    release, _python = _fake_release(tmp_path)
    call_log = release / ".venv" / "runner_calls.log"
    env_log = release / ".venv" / "runner_env.log"
    loader_log = tmp_path / "runtime_loader.log"
    environment = os.environ.copy()
    environment.update(
        {
            "DHARMA_RELEASE_ROOT": str(release),
            "DHARMA_RUNTIME_EXPECTED_COMMIT": PIN,
            "GITHUB_TOKEN": "provider-visible-to-responder",
            "TEST_RUNTIME_LOADER_LOG": str(loader_log),
        }
    )

    result = subprocess.run(
        [
            "/bin/bash",
            str(RUNNER),
            "codex-composer-semantic-responder",
            "loop",
            "--interval-s",
            "60",
            "--limit",
            "1",
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        (
            f"-B -I -S {release}/dharma_swarm/runtime_admission.py "
            f"--repo {release} --expected-commit {PIN}"
        ),
        (
            "-B -I -m dharma_swarm.runtime_release_entrypoint "
            "codex-composer-semantic-responder loop --interval-s 60 --limit 1"
        ),
    ]
    assert env_log.read_text(encoding="utf-8").splitlines() == [
        "github=provider-visible-to-responder runtime=<unset>",
        "github=provider-visible-to-responder runtime=1",
    ]
    assert loader_log.read_text(encoding="utf-8").splitlines() == ["loaded"]


def test_release_runner_rejects_dirty_release_before_responder_env_or_dispatch(
    tmp_path: Path,
) -> None:
    release, _python = _fake_release(tmp_path)
    call_log = release / ".venv" / "runner_calls.log"
    loader_log = tmp_path / "runtime_loader.log"
    (release / "uncommitted.py").write_text("# dirty release\n", encoding="utf-8")
    environment = os.environ.copy()
    environment.update(
        {
            "DHARMA_RELEASE_ROOT": str(release),
            "DHARMA_RUNTIME_EXPECTED_COMMIT": PIN,
            "TEST_RUNTIME_LOADER_LOG": str(loader_log),
        }
    )

    result = subprocess.run(
        [
            "/bin/bash",
            str(RUNNER),
            "codex-composer-semantic-responder",
            "once",
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 78
    assert "release checkout has uncommitted paths" in result.stderr
    assert not loader_log.exists()
    assert not call_log.exists()


def test_release_runner_rejects_unknown_command_before_python(tmp_path: Path) -> None:
    release, _python = _fake_release(tmp_path)
    call_log = release / ".venv" / "runner_calls.log"
    environment = os.environ.copy()
    environment.update(
        {
            "DHARMA_RELEASE_ROOT": str(release),
            "DHARMA_RUNTIME_EXPECTED_COMMIT": PIN,
        }
    )

    result = subprocess.run(
        ["/bin/bash", str(RUNNER), "python", "-m", "arbitrary.module"],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 78
    assert "unsupported command" in result.stderr
    assert not call_log.exists()


def test_release_runner_rejects_interpreter_from_another_checkout(
    tmp_path: Path,
) -> None:
    release, _python = _fake_release(tmp_path)
    environment = os.environ.copy()
    environment.update(
        {
            "DHARMA_RELEASE_ROOT": str(release),
            "DHARMA_RUNTIME_EXPECTED_COMMIT": PIN,
            "DHARMA_PYTHON": "/usr/bin/python3",
        }
    )

    result = subprocess.run(
        ["/bin/bash", str(RUNNER)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 78
    assert "must be the release-local .venv/bin/python" in result.stderr


def test_release_runner_rejects_lexical_parent_traversal_before_execution(
    tmp_path: Path,
) -> None:
    release, _python = _fake_release(tmp_path)
    outside = tmp_path / "outside" / "python"
    outside.parent.mkdir()
    outside.write_text(
        "#!/usr/bin/env bash\nprintf 'executed\\n' >> \"${RUNNER_CALL_LOG}\"\n",
        encoding="utf-8",
    )
    outside.chmod(0o755)
    call_log = tmp_path / "calls.log"
    environment = os.environ.copy()
    environment.update(
        {
            "DHARMA_RELEASE_ROOT": str(release),
            "DHARMA_RUNTIME_EXPECTED_COMMIT": PIN,
            "DHARMA_PYTHON": f"{release}/../outside/python",
            "RUNNER_CALL_LOG": str(call_log),
        }
    )

    result = subprocess.run(
        ["/bin/bash", str(RUNNER)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 78
    assert "must be the release-local .venv/bin/python" in result.stderr
    assert not call_log.exists()


def test_release_runner_rejects_symlinked_venv_directory(tmp_path: Path) -> None:
    release = tmp_path / "release"
    outside = tmp_path / "outside-venv"
    python = outside / "bin" / "python"
    loader = release / "scripts" / "load_runtime_env.sh"
    admission = release / "dharma_swarm" / "runtime_admission.py"
    python.parent.mkdir(parents=True)
    loader.parent.mkdir(parents=True)
    admission.parent.mkdir(parents=True)
    python.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    python.chmod(0o755)
    loader.write_text(":\n", encoding="utf-8")
    admission.write_text("# fake admission target\n", encoding="utf-8")
    (release / ".gitignore").write_text(".venv\n", encoding="utf-8")
    (release / ".venv").symlink_to(outside, target_is_directory=True)
    _git(release, "init", "-b", "main")
    _git(release, "add", ".gitignore", "dharma_swarm", "scripts")
    _git(
        release,
        "-c",
        "user.name=Runtime Runner Test",
        "-c",
        "user.email=runtime-runner@example.invalid",
        "commit",
        "-m",
        "sealed release",
    )
    environment = os.environ.copy()
    environment.update(
        {
            "DHARMA_RELEASE_ROOT": str(release),
            "DHARMA_RUNTIME_EXPECTED_COMMIT": PIN,
        }
    )

    result = subprocess.run(
        ["/bin/bash", str(RUNNER)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 78
    assert "must be the release-local .venv/bin/python" in result.stderr


def test_release_runner_rejects_ignored_bytecode_before_python(
    tmp_path: Path,
) -> None:
    release, _python = _fake_release(tmp_path)
    (release / "sitecustomize.pyc").write_bytes(b"ignored startup bytecode")
    call_log = tmp_path / "calls.log"
    environment = os.environ.copy()
    environment.update(
        {
            "DHARMA_RELEASE_ROOT": str(release),
            "DHARMA_RUNTIME_EXPECTED_COMMIT": PIN,
            "RUNNER_CALL_LOG": str(call_log),
        }
    )

    result = subprocess.run(
        ["/bin/bash", str(RUNNER)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 78
    assert "ignored import bytecode" in result.stderr
    assert not call_log.exists()


def test_release_runner_rejects_blank_commit_pin_before_python(
    tmp_path: Path,
) -> None:
    release, _python = _fake_release(tmp_path)
    call_log = tmp_path / "calls.log"
    environment = os.environ.copy()
    environment.update(
        {
            "DHARMA_RELEASE_ROOT": str(release),
            "DHARMA_RUNTIME_EXPECTED_COMMIT": "   ",
            "RUNNER_CALL_LOG": str(call_log),
        }
    )

    result = subprocess.run(
        ["/bin/bash", str(RUNNER)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 78
    assert "full 40-character commit SHA" in result.stderr
    assert not call_log.exists()


def test_release_runner_rejects_interpreter_symlinked_outside_release(
    tmp_path: Path,
) -> None:
    """A `.venv/bin/python` symlink to an outside executable must fail before
    that executable ever runs (review round 2: the dir-only `pwd -P`
    canonicalization admitted the outside target)."""
    release, python = _fake_release(tmp_path)
    outside = tmp_path / "outside-python"
    outside.write_text(
        '#!/usr/bin/env bash\nprintf \'OUTSIDE %s\\n\' "$*" >> "${RUNNER_CALL_LOG}"\n',
        encoding="utf-8",
    )
    outside.chmod(0o755)
    python.unlink()
    python.symlink_to(outside)
    call_log = tmp_path / "calls.log"
    environment = os.environ.copy()
    environment.update(
        {
            "DHARMA_RELEASE_ROOT": str(release),
            "DHARMA_RUNTIME_EXPECTED_COMMIT": PIN,
            "RUNNER_CALL_LOG": str(call_log),
        }
    )

    result = subprocess.run(
        ["/bin/bash", str(RUNNER), "--verify-only"],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 78, result.stderr
    assert "resolves outside the release root" in result.stderr
    assert not call_log.exists(), "outside interpreter must never execute"


def test_release_runner_accepts_interpreter_symlinked_within_release(
    tmp_path: Path,
) -> None:
    release, python = _fake_release(tmp_path)
    real = python.parent / "python3"
    python.rename(real)
    python.symlink_to(real.name)
    call_log = release / ".venv" / "runner_calls.log"
    environment = os.environ.copy()
    environment.update(
        {
            "DHARMA_RELEASE_ROOT": str(release),
            "DHARMA_RUNTIME_EXPECTED_COMMIT": PIN,
        }
    )

    result = subprocess.run(
        ["/bin/bash", str(RUNNER), "--verify-only"],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 1 and "runtime_admission.py" in calls[0]
