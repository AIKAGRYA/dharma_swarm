from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


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
