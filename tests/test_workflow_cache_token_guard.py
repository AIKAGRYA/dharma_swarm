from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "governance" / "check_workflow_cache_token.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_workflow_cache_token", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


COMPLIANT_CACHE = """\
name: sample
on: [push]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4
      - name: Cache pip
        uses: actions/cache@0000000000000000000000000000000000000000 # vX
        with:
          path: ~/.cache/pip
          key: pip-${{ hashFiles('uv.lock') }}
"""

BRANCH_KEYED_CACHE = """\
name: sample
on: [push]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Cache pip
        uses: actions/cache@0000000000000000000000000000000000000000 # vX
        with:
          path: ~/.cache/pip
          key: pip-${{ github.ref }}
"""

RESTORE_KEYS_CACHE = """\
name: sample
on: [push]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Cache pip
        uses: actions/cache@0000000000000000000000000000000000000000 # vX
        with:
          path: ~/.cache/pip
          key: pip-${{ hashFiles('uv.lock') }}
          restore-keys: |
            pip-
"""

SETUP_CACHE_NO_LOCKFILE = """\
name: sample
on: [push]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5
        with:
          python-version: "3.12"
          cache: pip
"""

SETUP_CACHE_WITH_LOCKFILE = """\
name: sample
on: [push]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-node@0000000000000000000000000000000000000000 # v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: dashboard/package-lock.json
"""

NO_PERMISSIONS = """\
name: sample
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4
"""


def _write(tmp_path: Path, name: str, body: str) -> Path:
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    (wf / name).write_text(body, encoding="utf-8")
    return wf


def _run_cli(workflows_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--workflows-dir", str(workflows_dir)],
        capture_output=True,
        text=True,
    )


def test_current_tree_is_green() -> None:
    # The real .github/workflows must pass today (dormant guard).
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_branch_keyed_cache_trips_red(tmp_path: Path) -> None:
    wf = _write(tmp_path, "poison.yml", BRANCH_KEYED_CACHE)
    result = _run_cli(wf)
    assert result.returncode == 1
    assert "not a pure function of a lockfile" in result.stdout


def test_restore_keys_cache_trips_red(tmp_path: Path) -> None:
    wf = _write(tmp_path, "poison.yml", RESTORE_KEYS_CACHE)
    result = _run_cli(wf)
    assert result.returncode == 1
    assert "restore-keys partial fallback" in result.stdout


def test_compliant_cache_passes(tmp_path: Path) -> None:
    wf = _write(tmp_path, "ok.yml", COMPLIANT_CACHE)
    result = _run_cli(wf)
    assert result.returncode == 0, result.stdout + result.stderr


def test_setup_cache_without_lockfile_trips_red(tmp_path: Path) -> None:
    wf = _write(tmp_path, "setup.yml", SETUP_CACHE_NO_LOCKFILE)
    result = _run_cli(wf)
    assert result.returncode == 1
    assert "cache-dependency-path" in result.stdout


def test_setup_cache_with_lockfile_passes(tmp_path: Path) -> None:
    wf = _write(tmp_path, "setup.yml", SETUP_CACHE_WITH_LOCKFILE)
    result = _run_cli(wf)
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_permissions_trips_red(tmp_path: Path) -> None:
    wf = _write(tmp_path, "noperms.yml", NO_PERMISSIONS)
    result = _run_cli(wf)
    assert result.returncode == 1
    assert "no top-level permissions block" in result.stdout


def test_module_unit_scan(tmp_path: Path) -> None:
    module = _load_module()
    wf = _write(tmp_path, "poison.yml", BRANCH_KEYED_CACHE)
    violations = module.scan_workflows(wf)
    assert any(v.guard == "cache" for v in violations)
