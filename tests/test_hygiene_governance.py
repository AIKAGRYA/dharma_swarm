from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_hygiene_integrity_gate_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/governance/hygiene/check_hygiene_integrity.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Hygiene integrity OK" in result.stdout


def test_hygiene_scan_single_pattern_writes_output(tmp_path: Path) -> None:
    output = tmp_path / "baseline.txt"
    subprocess.run(
        [
            sys.executable,
            "scripts/governance/hygiene/scan.py",
            "--pattern",
            "VC-A2",
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    text = output.read_text(encoding="utf-8")
    assert "VC-A2 - Trivially true tests" in text
    assert "exit_code:" in text


def test_hygiene_scan_ai_agent_pattern_writes_output(tmp_path: Path) -> None:
    output = tmp_path / "ai-baseline.txt"
    subprocess.run(
        [
            sys.executable,
            "scripts/governance/hygiene/scan.py",
            "--pattern",
            "AI-A1",
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    text = output.read_text(encoding="utf-8")
    assert "AI-A1 - Untrusted text treated as agent instruction" in text
    assert "exit_code:" in text


def test_run_python_with_repo_env_normalizes_relative_script_from_non_repo_cwd(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["DHARMA_PYTHON"] = sys.executable

    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts/governance/run_python_with_repo_env.sh"),
            "scripts/governance/hygiene/scan.py",
            "--help",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--pattern" in result.stdout


def test_run_python_with_repo_env_falls_back_to_path_python3_not_sibling_worktree(tmp_path: Path) -> None:
    if (REPO_ROOT / ".venv" / "bin" / "python").exists():
        pytest.skip("repo-local .venv intentionally takes precedence over PATH python3")

    marker = tmp_path / "python3-used.txt"
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "python3"
    shim.write_text(
        "#!/usr/bin/env sh\n"
        f"printf 'used\\n' > {shlex.quote(str(marker))}\n"
        f"exec {shlex.quote(sys.executable)} \"$@\"\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)

    env = os.environ.copy()
    env.pop("DHARMA_PYTHON", None)
    env["PATH"] = f"{shim_dir}{os.pathsep}{env['PATH']}"

    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts/governance/run_python_with_repo_env.sh"),
            "scripts/governance/hygiene/scan.py",
            "--help",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--pattern" in result.stdout
    assert marker.read_text(encoding="utf-8") == "used\n"


def test_run_python_with_repo_env_resolves_dharma_python_command_from_path(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "dharma-python-used.txt"
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "python3"
    shim.write_text(
        "#!/usr/bin/env sh\n"
        f"printf 'used\\n' > {shlex.quote(str(marker))}\n"
        f"exec {shlex.quote(sys.executable)} \"$@\"\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)

    env = os.environ.copy()
    env["DHARMA_PYTHON"] = "python3"
    env["PATH"] = f"{shim_dir}{os.pathsep}{env['PATH']}"

    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts/governance/run_python_with_repo_env.sh"),
            "scripts/governance/hygiene/scan.py",
            "--help",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--pattern" in result.stdout
    assert marker.read_text(encoding="utf-8") == "used\n"
