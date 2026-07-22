"""WP-0C1 (TIT-004): the required Semgrep scan fails closed.

Contract under test: ``scripts/governance/run_semgrep_with_ca.sh`` plus the
Makefile scanner targets. A missing or version-mismatched scanner is a named
nonzero failure, never a green skip; the warn-only behavior lives in an
explicitly named advisory target that never enters ``governance-all``; the
scan carries a portable wall-clock bound converted into a named nonzero failure.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = REPO_ROOT / "scripts/governance/run_semgrep_with_ca.sh"
MAKEFILE = REPO_ROOT / "Makefile"
RATIFIED_PIN = "1.168.0"


def _run_wrapper(args: list[str], env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_overrides)
    return subprocess.run(
        [str(WRAPPER), *args],
        cwd=REPO_ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _fake_semgrep(tmp_path: Path, *, version: str, body: str = "exit 0") -> Path:
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "semgrep"
    fake.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            if [[ "${{1:-}}" == "--version" ]]; then
              echo "{version}"
              exit 0
            fi
            {body}
            """
        )
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return fake


def _fake_hanging_version_semgrep(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "hanging-version-bin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "semgrep"
    fake.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            if [[ "${1:-}" == "--version" ]]; then
              sleep 30
              exit 0
            fi
            exit 0
            """
        )
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return fake


def test_absent_semgrep_is_named_nonzero_failure():
    proc = _run_wrapper(
        ["--config", ".semgrep", "--error", "--metrics=off"],
        {
            "DHARMA_SEMGREP_BIN": "definitely-missing-semgrep-xyz",
            "DHARMA_SEMGREP_ALLOW_MISSING": "",
        },
    )
    assert proc.returncode == 2, proc.stderr
    assert "SEMGREP_MISSING" in proc.stderr


def test_absent_semgrep_advisory_optin_is_explicit_skip():
    proc = _run_wrapper(
        ["--config", ".semgrep", "--metrics=off"],
        {
            "DHARMA_SEMGREP_BIN": "definitely-missing-semgrep-xyz",
            "DHARMA_SEMGREP_ALLOW_MISSING": "1",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert "SEMGREP_SKIPPED" in proc.stderr


def test_version_mismatch_is_named_nonzero_failure(tmp_path):
    fake = _fake_semgrep(tmp_path, version="1.99.9")
    proc = _run_wrapper(
        ["--config", ".semgrep", "--error", "--metrics=off"],
        {
            "DHARMA_SEMGREP_BIN": str(fake),
            "DHARMA_SEMGREP_EXPECTED_VERSION": RATIFIED_PIN,
        },
    )
    assert proc.returncode == 2, proc.stderr
    assert "SEMGREP_VERSION_MISMATCH" in proc.stderr
    assert "1.99.9" in proc.stderr
    assert RATIFIED_PIN in proc.stderr


def test_version_probe_timeout_is_named_nonzero_failure(tmp_path):
    fake = _fake_hanging_version_semgrep(tmp_path)
    started = time.monotonic()
    proc = _run_wrapper(
        ["--config", ".semgrep", "--error", "--metrics=off"],
        {
            "DHARMA_SEMGREP_BIN": str(fake),
            "DHARMA_SEMGREP_EXPECTED_VERSION": RATIFIED_PIN,
            "DHARMA_SEMGREP_WALLCLOCK": "1",
        },
    )
    elapsed = time.monotonic() - started
    assert proc.returncode == 2, proc.stderr
    assert "SEMGREP_VERSION_TIMEOUT" in proc.stderr
    assert elapsed < 10, f"version timeout leaked descendants for {elapsed:.1f}s"


def test_matching_version_execs_scanner_with_expanded_args(tmp_path):
    args_file = tmp_path / "recorded-args"
    fake = _fake_semgrep(
        tmp_path,
        version=RATIFIED_PIN,
        body=f'printf "%s\\n" "$@" > "{args_file}"\nexit 0',
    )
    proc = _run_wrapper(
        ["--config", ".semgrep", "--error", "--metrics=off"],
        {
            "DHARMA_SEMGREP_BIN": str(fake),
            "DHARMA_SEMGREP_EXPECTED_VERSION": RATIFIED_PIN,
        },
    )
    assert proc.returncode == 0, proc.stderr
    recorded = args_file.read_text().splitlines()
    assert ".semgrep/dharma-anti-slop.yml" in recorded
    assert ".semgrep/security.yml" in recorded
    assert "--error" in recorded


def test_wallclock_overrun_is_named_nonzero_failure(tmp_path):
    fake = _fake_semgrep(tmp_path, version=RATIFIED_PIN, body="sleep 30\nexit 0")
    started = time.monotonic()
    proc = _run_wrapper(
        ["--config", ".semgrep", "--metrics=off"],
        {"DHARMA_SEMGREP_BIN": str(fake), "DHARMA_SEMGREP_WALLCLOCK": "1"},
    )
    elapsed = time.monotonic() - started
    assert proc.returncode == 2, proc.stderr
    assert "SEMGREP_TIMEOUT" in proc.stderr
    assert elapsed < 10, f"scan timeout leaked descendants for {elapsed:.1f}s"


def test_invalid_wallclock_is_named_nonzero_failure(tmp_path):
    fake = _fake_semgrep(tmp_path, version=RATIFIED_PIN)
    proc = _run_wrapper(
        ["--config", ".semgrep", "--metrics=off"],
        {
            "DHARMA_SEMGREP_BIN": str(fake),
            "DHARMA_SEMGREP_WALLCLOCK": "not-a-number",
        },
    )
    assert proc.returncode == 2, proc.stderr
    assert "SEMGREP_TIMEOUT_CONFIG_INVALID" in proc.stderr


@pytest.mark.skipif(
    shutil.which("semgrep") is None,
    reason="semgrep binary not installed on this host; the strict-scan positive "
    "path runs in the semgrep CI lane and was proven by the WP-0C1R receipt",
)
def test_strict_scan_fails_on_violating_fixture(tmp_path):
    rule = tmp_path / "rule.yml"
    rule.write_text(
        textwrap.dedent(
            """\
            rules:
              - id: wp0c1-negative-control-eval
                pattern: eval(...)
                message: WP-0C1 negative-control fixture violation
                severity: ERROR
                languages: [python]
            """
        )
    )
    target = tmp_path / "violating.py"
    target.write_text('eval("1 + 1")\n')
    proc = _run_wrapper(
        ["--config", str(rule), "--error", "--metrics=off", str(target)],
        {},
    )
    assert proc.returncode != 0, proc.stdout


def _makefile_recipe(target: str) -> str:
    text = MAKEFILE.read_text()
    lines = text.splitlines()
    body: list[str] = []
    capture = False
    for line in lines:
        if line.startswith(f"{target}:"):
            capture = True
            continue
        if capture:
            if line.startswith("\t") or not line.strip():
                body.append(line)
                if not line.strip() and body and not any(
                    later.startswith("\t") for later in body[-1:]
                ):
                    continue
            else:
                break
    return "\n".join(body)


def test_make_semgrep_is_the_strict_required_scan():
    recipe = _makefile_recipe("semgrep")
    assert "--error" in recipe, "make semgrep must be strict (--error)"
    assert ".semgrep/security.yml" in recipe, (
        "the required scan runs the security ruleset WP-0C1R proved clean"
    )
    assert "DHARMA_SEMGREP_EXPECTED_VERSION" in recipe, (
        "the required scan enforces the ratified version pin"
    )


def test_advisory_target_exists_and_never_enters_governance_all():
    text = MAKEFILE.read_text()
    assert "semgrep-advisory:" in text
    recipe = _makefile_recipe("semgrep-advisory")
    assert "DHARMA_SEMGREP_ALLOW_MISSING=1" in recipe
    assert "--error" not in recipe
    governance_line = next(
        line for line in text.splitlines() if line.startswith("governance-all:")
    )
    assert "semgrep-advisory" not in governance_line
    assert " semgrep " in governance_line + " "
    assert "gitleaks" in governance_line


def test_make_gitleaks_absent_is_named_nonzero_failure():
    proc = subprocess.run(
        ["make", "gitleaks", "GITLEAKS=definitely-missing-gitleaks-xyz"],
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "GITLEAKS_MISSING" in proc.stdout + proc.stderr
