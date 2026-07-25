"""Tests for the stable immutable-release launch boundary."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "runtime" / "dharma_swarm_release_runner.sh"
PIN = "a" * 40


def _fake_release(tmp_path: Path) -> tuple[Path, Path]:
    release = tmp_path / "release"
    python = release / ".venv" / "bin" / "python"
    loader = release / "scripts" / "load_runtime_env.sh"
    python.parent.mkdir(parents=True)
    loader.parent.mkdir(parents=True)
    python.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"${RUNNER_CALL_LOG}\"\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    loader.write_text("export TEST_RUNTIME_ENV_LOADED=1\n", encoding="utf-8")
    return release, python


def test_release_runner_uses_pinned_release_interpreter_and_guard() -> None:
    text = RUNNER.read_text(encoding="utf-8")

    assert "${release_root}/.venv/bin/python" in text
    assert "DHARMA_RUNTIME_EXPECTED_COMMIT" in text
    assert "DHARMA_PYTHON must live inside DHARMA_RELEASE_ROOT" in text
    assert text.index("dharma_swarm.runtime_admission") < text.index(
        'source "${runtime_env_helper}"'
    )
    assert text.index("dharma_swarm.runtime_admission") < text.index(
        "dharma_swarm.dgc_cli orchestrate-live"
    )
    assert "/Users/dhyana/dharma_swarm/.venv" not in text
    assert "/Users/dhyana/dharma_swarm/.env" not in text


def test_release_runner_executes_guard_before_live_command(tmp_path: Path) -> None:
    release, _python = _fake_release(tmp_path)
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

    assert result.returncode == 0, result.stderr
    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert calls == [
        (
            "-m dharma_swarm.runtime_admission "
            f"--repo {release} --expected-commit {PIN}"
        ),
        "-m dharma_swarm.dgc_cli orchestrate-live",
    ]


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
    assert "must live inside DHARMA_RELEASE_ROOT" in result.stderr
