from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "governance_scan.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("governance_scan", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_governance_scan_help_is_available() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
timeout=30,
)

    assert "--base-ref" in result.stdout
    assert "--skip-module-budget" in result.stdout


def test_governance_scan_builds_wave_a_commands() -> None:
    module = _load_module()

    commands = module.build_commands(
        base_ref="origin/main",
        head_ref="HEAD",
        warn_only=True,
        skip_module_budget=False,
    )

    joined = [" ".join(command) for command in commands]
    assert any("check_test_hygiene.py" in command for command in joined)
    assert any("check_module_budget.py" in command for command in joined)
    assert any("--warn-only" in command for command in joined)
