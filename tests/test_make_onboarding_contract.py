"""Make-level session-status and edit-admission command boundaries.

Covers O4-B1 (`make organism-status` is deep/read-only under a write-attempt
guard and `make orient` remains its compatibility alias; only the explicit
owner command writes context), O4-B2 (preflight consumes the packet evaluator
exactly once, fail-closed), O4-B7 (`make agent-register` owns the persistent
identity route and `make agent-onboard` remains its compatibility alias), O4-B8
(Make forwards documented ARGS; unknown flags keep exit 2), and O4-B9
(admission receipts have one explicit external destination).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
RUNNER = "scripts/governance/run_agent_work_packet.py"

# The snapshot commit must not fork git's detached auto-maintenance into the
# measured window: on git >= 2.55 it writes .git/objects/info/commit-graphs/*
# into the pristine clone seconds later, and the tree-snapshot equality
# asserts would attribute that background write to the target under test.
_GIT_NO_AUTO_MAINTENANCE = ("-c", "maintenance.auto=false", "-c", "gc.auto=0")


@pytest.fixture(autouse=True)
def _no_bytecode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make targets spawn Python subprocesses; avoid writing __pycache__ into the repo."""
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")


def _recipe(target: str) -> str:
    matches = re.finditer(
        rf"^{re.escape(target)}:.*\n((?:\t.*\n|ifdef .*\n|endif\n)*)",
        MAKEFILE,
        re.MULTILINE,
    )
    for match in matches:
        header = match.group(0).splitlines()[0]
        if re.search(r":\s+(?:override\s+)?[A-Za-z_]\w*\s*(?::=|\+=|\?=|=)", header):
            continue
        return match.group(0)
    raise AssertionError(f"Makefile target {target!r} not found")


def _make(*args: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "-s", *args],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout,
    )


def _porcelain() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--ignored=matching"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    ).stdout


def _copy_tracked_checkout(destination: Path) -> None:
    """Clone, overlay, and commit the current tracked implementation.

    This is a genuine clean Git checkout at the implementation under test,
    without ignored bytecode or tool caches that could hide an import-time
    write.  A shared local clone avoids copying the repository object store.
    """
    subprocess.run(
        ["git", *_GIT_NO_AUTO_MAINTENANCE, "clone", "--quiet", "--shared", str(REPO_ROOT), str(destination)],
        check=True,
        timeout=120,
    )
    listed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout
    for raw_relative in listed.split(b"\0"):
        if not raw_relative:
            continue
        relative = os.fsdecode(raw_relative)
        source = REPO_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not source.exists() and not source.is_symlink():
            target.unlink(missing_ok=True)
        elif source.is_symlink():
            target.unlink(missing_ok=True)
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            shutil.copy2(source, target)
    subprocess.run(
        ["git", "-C", str(destination), *_GIT_NO_AUTO_MAINTENANCE, "add", "-A"],
        check=True,
        timeout=60,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(destination),
            *_GIT_NO_AUTO_MAINTENANCE,
            "-c",
            "user.name=Session Contract Test",
            "-c",
            "user.email=wp-o4-test@example.invalid",
            "commit",
            "--quiet",
            "--allow-empty",
            "-m",
            "snapshot implementation under test",
        ],
        check=True,
        timeout=60,
    )
    assert not subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=destination,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout


def _tree_snapshot(root: Path) -> dict[str, tuple[object, ...]]:
    """Content-address every file/symlink so ignored writes cannot disappear."""
    snapshot: dict[str, tuple[object, ...]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            snapshot[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            snapshot[relative] = (
                "file",
                path.stat().st_mode,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
    return snapshot


# --- O4-B1: organism status is mutation-free ---------------------------------

def test_organism_status_owns_projection_and_orient_is_alias() -> None:
    recipe = _recipe("organism-status")
    alias = _recipe("orient")
    assert "orientation_graph.py" in recipe
    assert "--write-context" not in recipe, (
        "make organism-status must be a mutation-free projection; context refresh "
        "belongs only to the explicit owner command (spec §2.1)"
    )
    assert alias.splitlines() == ["orient: organism-status"]


@pytest.mark.timeout(180)
def test_make_orient_attempts_no_repository_write(tmp_path: Path) -> None:
    """Run from a cache-free tracked copy so first imports are observable."""
    checkout = tmp_path / "clean-checkout"
    _copy_tracked_checkout(checkout)
    before = _tree_snapshot(checkout)
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["XDG_CACHE_HOME"] = str(tmp_path / "xdg-cache")
    result = subprocess.run(
        [
            "make",
            "-s",
            "orient",
            f"PYTHON={sys.executable} -S",
            # Hostile caller values must not re-enable in-checkout bytecode.
            "PYTHONDONTWRITEBYTECODE=",
            "PYTHONPYCACHEPREFIX=.",
        ],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert _tree_snapshot(checkout) == before, (
        "make orient wrote or changed the pristine tracked copy, including an "
        "ignored bytecode/cache path"
    )
    assert "organism-status: override PYTHONDONTWRITEBYTECODE := 1" in MAKEFILE
    assert "\tPYTHONDONTWRITEBYTECODE=1 $(PYTHON)" in MAKEFILE


@pytest.mark.parametrize(
    ("target", "extra_args"),
    [
        ("onboard", ["ARGS=--json"]),
        ("agent-register", ["ARGS=--json"]),
    ],
)
def test_session_and_registration_commands_are_dependency_light_and_read_only(
    tmp_path: Path,
    target: str,
    extra_args: list[str],
) -> None:
    checkout = tmp_path / target
    _copy_tracked_checkout(checkout)
    before = _tree_snapshot(checkout)
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env.pop("PYTHONDONTWRITEBYTECODE", None)

    result = subprocess.run(
        [
            "make",
            "-s",
            target,
            *extra_args,
            f"PYTHON={sys.executable} -S",
            "PYTHONDONTWRITEBYTECODE=",
            "PYTHONPYCACHEPREFIX=.",
        ],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )

    assert result.returncode == 0, result.stderr[-2000:]
    json.loads(result.stdout)
    assert _tree_snapshot(checkout) == before


def test_explicit_context_refresh_command_is_documented() -> None:
    """The owner command stays discoverable next to the read-only target."""
    assert "orientation_graph.py --write-context" in MAKEFILE


# --- O4-B2: preflight consumes the packet evaluator --------------------------

@pytest.mark.parametrize("target", ["agent-build-preflight", "agent-build-closeout"])
def test_edit_admission_targets_require_an_exact_packet_before_prerequisites(
    tmp_path: Path,
    target: str,
) -> None:
    report_root = tmp_path / "must-not-be-created"
    result = subprocess.run(
        ["make", "-s", target, f"AGENTOPS_REPORT_ROOT={report_root}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        env=os.environ.copy(),
    )

    assert result.returncode == 2
    assert "PACKET=<path> is required" in result.stderr
    assert not report_root.exists()

def test_preflight_single_evaluation_and_exact_base() -> None:
    """The Make door delegates the exact-base decision once to preflight."""
    recipe = _recipe("agent-build-preflight")
    prerequisites = recipe.splitlines()[0].partition(":")[2].split()
    assert prerequisites == ["agentops-report-root-check"]
    assert recipe.count("run_agent_work_packet.py") == 1
    assert recipe.count("--packet") == 1
    assert '--packet "$${PACKET}"' in recipe
    assert "--preflight" in recipe
    assert "--dry-run" not in recipe
    assert '--report-root "$${AGENTOPS_REPORT_ROOT}"' in recipe
    assert recipe.index("$(MAKE) -s verifier-selfcheck") < recipe.index(
        "$(MAKE) -s hygiene-check"
    ) < recipe.index("--preflight")

    root_check = _recipe("agentops-report-root-check")
    assert root_check.count("run_agent_work_packet.py") == 1
    assert "$(_AGENTOPS_RESOLVE_PYTHON)" in root_check
    assert '"$$agentops_python"' in root_check
    assert '--validate-report-root "$${AGENTOPS_REPORT_ROOT}"' in root_check
    assert root_check.count("--validate-report-child") == 3
    assert "--validate-report-child cache" in root_check
    assert "--validate-report-child cache/hypothesis" in root_check
    assert "--validate-report-child onboard" in root_check
    assert "--packet" not in root_check


def test_closeout_uses_descendant_aware_packet_evaluation() -> None:
    recipe = _recipe("agent-build-closeout")
    assert recipe.count("run_agent_work_packet.py") == 1
    assert '--packet "$${PACKET}"' in recipe
    assert "--closeout" in recipe
    assert "--dry-run" not in recipe
    assert '--report-root "$${AGENTOPS_REPORT_ROOT}"' in recipe
    assert "governance-all" in recipe


def test_preflight_packet_evaluation_fails_closed(tmp_path: Path) -> None:
    """The exact command the Makefile preflight runs for PACKET must fail on an
    invalid packet. Exercised directly, not through `make agent-build-preflight`
    — that target chains verifier-selfcheck/hygiene-check, minutes of
    unrelated work that flapped the 30s per-test budget on CI (#897)."""
    bogus = tmp_path / "bogus-packet.json"
    bogus.write_text('{"id": "nope"}', encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            RUNNER,
            "--packet",
            str(bogus),
            "--preflight",
            "--report-root",
            str(tmp_path / "agentops-reports"),
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode != 0, (
        "an invalid packet must fail the preflight evaluator, not pass"
    )


# --- O4-B9: admission receipts stay outside the checkout ---------------------

def test_make_admission_recipes_use_external_report_root(tmp_path: Path) -> None:
    """Both Make admission modes declare one external receipt destination."""
    before = _porcelain()
    assert (
        "override AGENTOPS_CACHE_ROOT := $(AGENTOPS_REPORT_ROOT)/cache"
        in MAKEFILE
    )
    assert "export AGENTOPS_REPORT_ROOT" in MAKEFILE
    assert "export AGENTOPS_CACHE_ROOT" in MAKEFILE
    assert "override AGENTOPS_PYTEST_ADDOPTS := -p no:cacheprovider" in MAKEFILE
    for cache_export in (
        "PYTHONDONTWRITEBYTECODE := 1",
        "PYTHONPYCACHEPREFIX := $(AGENTOPS_CACHE_ROOT)/python-pycache",
        "PYTEST_ADDOPTS := $(AGENTOPS_PYTEST_ADDOPTS)",
        "RUFF_CACHE_DIR := $(AGENTOPS_CACHE_ROOT)/ruff",
        "XDG_CACHE_HOME := $(AGENTOPS_CACHE_ROOT)/xdg",
        "HYPOTHESIS_STORAGE_DIRECTORY := $(AGENTOPS_CACHE_ROOT)/hypothesis",
    ):
        assert (
            "agentops-report-root-check agent-build-preflight "
            "agent-build-closeout: override "
            f"{cache_export}"
        ) in MAKEFILE
    assert (
        "agentops-report-root-check agent-build-preflight "
        "agent-build-closeout: override DHARMA_OPS_DIR := "
        "$(AGENTOPS_REPORT_ROOT)/onboard"
    ) in MAKEFILE
    for interpreter_export in (
        "AGENTOPS_PYTHON := $(_AGENTOPS_PYTHON_INPUT)",
        "PYTHON := $(_AGENTOPS_PYTHON_INPUT)",
        "VENV_PYTHON := $(_AGENTOPS_PYTHON_INPUT)",
        "PYTEST := $(_AGENTOPS_PYTHON_INPUT) -m pytest",
        "REPO_PYTHON := PYTHONPATH=. $(_AGENTOPS_PYTHON_INPUT)",
    ):
        assert (
            "agentops-report-root-check agent-build-preflight "
            "agent-build-closeout: override "
            f"{interpreter_export}"
        ) in MAKEFILE
    assert "define _AGENTOPS_EXPORT_ENV" in MAKEFILE
    for shell_export in (
        "export PYTHONDONTWRITEBYTECODE=1",
        'export HYPOTHESIS_STORAGE_DIRECTORY="$${AGENTOPS_REPORT_ROOT}/cache/hypothesis"',
        'export DHARMA_OPS_DIR="$${AGENTOPS_REPORT_ROOT}/onboard"',
        'export AGENTOPS_PYTHON="$$agentops_python"',
        'export REPO_PYTHON="PYTHONPATH=. $$agentops_python"',
    ):
        assert shell_export in MAKEFILE
    assert "override _AGENTOPS_PYTHON_INPUT := python3" in MAKEFILE
    assert "AGENTOPS_RECURSIVE_OVERRIDES" not in MAKEFILE
    assert MAKEFILE.count("MAKEOVERRIDES=") == 3
    assert '"$$agentops_python" scripts/governance/run_agent_work_packet.py' in MAKEFILE
    assert '--packet "$${PACKET}"' in MAKEFILE
    assert '--report-root "$${AGENTOPS_REPORT_ROOT}"' in MAKEFILE

    env = os.environ.copy()
    env.pop("AGENTOPS_REPORT_ROOT", None)
    env.pop("DHARMA_OPS_DIR", None)
    make_probe = tmp_path / "agentops-make-probe.mk"
    make_probe.write_text(
        f"include {(REPO_ROOT / 'Makefile').as_posix()}\n"
        ".PHONY: __print_agentops_report_root __print_agentops_cache_policy\n"
        "__print_agentops_report_root:\n"
        "\t@printf '%s\\n' \"$(AGENTOPS_REPORT_ROOT)\"\n"
        "__print_agentops_cache_policy:\n"
        "\t@printf '%s|%s\\n' \"$(AGENTOPS_CACHE_ROOT)\" "
        "\"$(AGENTOPS_PYTEST_ADDOPTS)\"\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "make",
            "-s",
            "-f",
            str(make_probe),
            "__print_agentops_report_root",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    report_root = Path(result.stdout.strip()).resolve()
    assert report_root.is_absolute()
    assert report_root != REPO_ROOT and REPO_ROOT not in report_root.parents
    uid = subprocess.run(
        ["/usr/bin/id", "-u"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()
    assert report_root == Path(f"/tmp/dharma-agentops-{uid}").resolve()

    packet = tmp_path / "packet with spaces.json"
    external_reports = tmp_path / "external reports"
    hardened = subprocess.run(
        [
            "make",
            "-s",
            "-f",
            str(make_probe),
            "__print_agentops_cache_policy",
            f"AGENTOPS_REPORT_ROOT={external_reports}",
            "AGENTOPS_CACHE_ROOT=.",
            "AGENTOPS_PYTEST_ADDOPTS=--lf",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert hardened.returncode == 0, hardened.stderr
    assert hardened.stdout.strip() == (
        f"{external_reports}/cache|-p no:cacheprovider"
    )

    for target, mode in (
        ("agent-build-preflight", "--preflight"),
        ("agent-build-closeout", "--closeout"),
    ):
        recipe = _recipe(target)
        assert recipe.count("run_agent_work_packet.py") == 1
        assert mode in recipe
        assert recipe.count('--report-root "$${AGENTOPS_REPORT_ROOT}"') == 1

        expanded = subprocess.run(
            [
                "make",
                "-n",
                target,
                f"PACKET={packet}",
                f"AGENTOPS_REPORT_ROOT={external_reports}",
                "DHARMA_OPS_DIR=.",
                "AGENTOPS_CACHE_ROOT=.",
                "AGENTOPS_PYTEST_ADDOPTS=--lf",
                "PYTHONDONTWRITEBYTECODE=0",
                "PYTHONPYCACHEPREFIX=.",
                "PYTEST_ADDOPTS=--lf",
                "RUFF_CACHE_DIR=.",
                "XDG_CACHE_HOME=.",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        assert expanded.returncode == 0, expanded.stderr
        assert '--packet "${PACKET}"' in expanded.stdout
        assert '--report-root "${AGENTOPS_REPORT_ROOT}"' in expanded.stdout
        assert '"$agentops_python" scripts/governance/run_agent_work_packet.py' in expanded.stdout
        assert "MAKEOVERRIDES=" in expanded.stdout
        # Caller-controlled paths are carried in the environment, not expanded
        # into shell source where quotes or command substitutions can execute.
        assert f'--packet "{packet}"' not in expanded.stdout
        assert f'--report-root "{external_reports}"' not in expanded.stdout

    assert _porcelain() == before, (
        "resolving the Make admission report root changed ordinary or ignored "
        "source-tree status"
    )


# WP-0D repo-scale override (2026-08-01 amendment): this test spawns real
# `make` admission subprocesses and passes alone in ~6s, but crosses the
# blanket fast budget under full-suite load (pytest-timeout in selectors.py
# after 8,061 passes on 2026-08-01 current main). The override widens THIS
# test only; the root cause is CPU contention on a fixed-cost test, not a
# leak or hang. Registered in REPO_SCALE_OVERRIDES
# (tests/test_fast_suite_isolation.py).
@pytest.mark.timeout(45)
def test_make_report_root_rejects_hypothesis_cache_symlink(
    tmp_path: Path,
) -> None:
    """The Hypothesis leaf is validated before verifier collection can write."""
    checkout = tmp_path / "clean-checkout"
    _copy_tracked_checkout(checkout)
    # Use the canonical POSIX report anchor. On macOS, pytest's tmp_path lives
    # under the Darwin account-temp root, whose getconf probe can be denied by
    # a constrained local runner before the leaf under test is inspected.
    report_root = Path("/tmp") / f"dharma-wp-o8-{os.getpid()}-{tmp_path.name}"
    shutil.rmtree(report_root, ignore_errors=True)
    cache_root = report_root / "cache"
    cache_root.mkdir(parents=True)
    (cache_root / "hypothesis").symlink_to(checkout, target_is_directory=True)
    before = _tree_snapshot(checkout)

    try:
        result = subprocess.run(
            [
                "make",
                "-s",
                "agentops-report-root-check",
                f"AGENTOPS_REPORT_ROOT={report_root}",
                f"AGENTOPS_PYTHON={sys.executable}",
            ],
            cwd=checkout,
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode != 0, result.stdout
        assert any(
            token in result.stderr
            for token in ("symlink", "escapes", "inside repository", "external")
        ), result.stderr
        assert _tree_snapshot(checkout) == before
    finally:
        shutil.rmtree(report_root, ignore_errors=True)


@pytest.mark.parametrize("source_variable", ["AGENTOPS_REPORT_ROOT", "DHARMA_OPS_DIR"])
def test_make_report_root_metacharacters_never_become_shell(
    tmp_path: Path,
    source_variable: str,
) -> None:
    """Make syntax and shell metacharacters stay inert before validation."""
    checkout = tmp_path / "clean-checkout"
    _copy_tracked_checkout(checkout)
    before = _tree_snapshot(checkout)
    shell_sentinel = checkout / "shell-source-write"
    make_sentinel = checkout / "make-source-write"
    malicious = (
        f'{tmp_path}/external"; touch shell-source-write; printf " '
        "$(shell touch make-source-write)"
    )
    env = os.environ.copy()
    env.pop("AGENTOPS_REPORT_ROOT", None)
    env.pop("DHARMA_OPS_DIR", None)
    result = subprocess.run(
        [
            "make",
            "-s",
            "agentops-report-root-check",
            f"{source_variable}={malicious}",
            f"AGENTOPS_PYTHON={sys.executable}",
        ],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )

    assert result.returncode in {0, 2}, result.stderr[-2000:]
    assert not shell_sentinel.exists()
    assert not make_sentinel.exists()
    assert _tree_snapshot(checkout) == before


@pytest.mark.parametrize("source_variable", ["AGENTOPS_REPORT_ROOT", "DHARMA_OPS_DIR"])
def test_make_report_root_shell_metacharacters_stay_data(
    tmp_path: Path,
    source_variable: str,
) -> None:
    """Shell-only syntax stays inert even without the earlier Make `$` guard."""
    checkout = tmp_path / "clean-checkout"
    _copy_tracked_checkout(checkout)
    before = _tree_snapshot(checkout)
    sentinel = checkout / "shell-source-write"
    malicious = f'{tmp_path}/external"; touch shell-source-write; printf "'
    env = os.environ.copy()
    env.pop("AGENTOPS_REPORT_ROOT", None)
    env.pop("DHARMA_OPS_DIR", None)
    result = subprocess.run(
        [
            "make",
            "-s",
            "agentops-report-root-check",
            f"{source_variable}={malicious}",
            f"AGENTOPS_PYTHON={sys.executable}",
        ],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )

    assert result.returncode in {0, 2}, result.stderr[-2000:]
    assert not sentinel.exists()
    assert _tree_snapshot(checkout) == before


@pytest.mark.parametrize("variable", ["PYTHON", "PACKET"])
def test_make_rejects_expansion_syntax_before_evaluation(
    tmp_path: Path,
    variable: str,
) -> None:
    """Global Make inputs reject function syntax without executing it."""
    checkout = tmp_path / "clean-checkout"
    _copy_tracked_checkout(checkout)
    marker = tmp_path / f"{variable.lower()}-make-expansion-executed"
    result = subprocess.run(
        [
            "make",
            "-s",
            "help",
            f"{variable}=$(shell touch {marker})",
        ],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )

    assert result.returncode == 2
    assert f"{variable} must not contain Make expansion syntax" in result.stderr
    assert not marker.exists()


@pytest.mark.parametrize("source_variable", ["AGENTOPS_REPORT_ROOT", "DHARMA_OPS_DIR"])
@pytest.mark.parametrize("parallel", [False, True], ids=["serial", "parallel"])
def test_make_rejects_in_tree_report_root_before_prerequisites(
    source_variable: str,
    parallel: bool,
) -> None:
    """The external-root check orders every potentially writeful prerequisite."""
    suffix = f"{source_variable.lower()}-{'parallel' if parallel else 'serial'}"
    inside_root = REPO_ROOT / f".wp-o4-invalid-agentops-{suffix}"
    assert not inside_root.exists(), f"test sentinel unexpectedly exists: {inside_root}"
    before = _porcelain()
    env = os.environ.copy()
    env.pop("AGENTOPS_REPORT_ROOT", None)
    env.pop("DHARMA_OPS_DIR", None)
    command = ["make", "-s"]
    if parallel:
        command.append("-j4")
    command.extend(
        [
            "agent-build-preflight",
            "PACKET=/tmp/unused-session-entry.json",
            f"{source_variable}={inside_root}",
        ]
    )

    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )

    assert result.returncode != 0
    assert "[1/4]" not in (result.stdout + result.stderr), (
        "verifier-selfcheck ran before the report-root validator failed"
    )
    assert not inside_root.exists(), "unsafe root was written before validation"
    assert _porcelain() == before, (
        "unsafe report-root admission changed ordinary or ignored source status"
    )


@pytest.mark.parametrize("parallel", [False, True], ids=["serial", "parallel"])
def test_make_rejects_cache_symlink_escape_before_prerequisites(
    tmp_path: Path,
    parallel: bool,
) -> None:
    """Validate external descendants before Python/cache-using prerequisites.

    The cache path deliberately resolves into a pristine checkout.  A content
    snapshot (not Git porcelain) proves the validator itself and the rejected
    build created no ignored bytecode, modified file, or other source artifact.
    """
    checkout = tmp_path / "clean-checkout"
    _copy_tracked_checkout(checkout)
    external_root = tmp_path / "private-agentops"
    external_root.mkdir(mode=0o700)
    (external_root / "cache").symlink_to(checkout, target_is_directory=True)
    before = _tree_snapshot(checkout)

    command = ["make", "-s"]
    if parallel:
        command.append("-j4")
    command.extend(
        [
            "agent-build-preflight",
            "PACKET=/tmp/unused-session-entry.json",
            f"AGENTOPS_REPORT_ROOT={external_root}",
            f"AGENTOPS_PYTHON={sys.executable}",
        ]
    )
    result = subprocess.run(
        command,
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "cache" in combined and "escapes external report_root" in combined, (
        "failure must come from validating the cache descendant, not an "
        f"earlier incidental error:\n{combined[-2000:]}"
    )
    assert "[1/4]" not in combined, (
        "verifier-selfcheck ran before the cache descendant was rejected"
    )
    assert _tree_snapshot(checkout) == before, (
        "the rejected cache symlink caused a source or ignored-cache write"
    )
    assert (external_root / "cache").is_symlink()


def test_make_agentops_bootstrap_never_executes_repo_venv_sitecustomize(
    tmp_path: Path,
) -> None:
    """The ordinary AgentOps door defaults to host python3, not repo .venv.

    The repository venv is armed with an import-time write witness and the
    legacy PYTHON variable explicitly points at it.  Admission must still
    bootstrap with the separate, external AGENTOPS_PYTHON identity.
    """
    checkout = tmp_path / "clean-checkout"
    _copy_tracked_checkout(checkout)
    repo_venv = checkout / ".venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(repo_venv)],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    site_packages = (
        repo_venv
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    site_packages.mkdir(parents=True, exist_ok=True)
    witness = site_packages / "wp_o4_repo_venv_witness.py"
    witness.write_text(
        "import os\n"
        "from pathlib import Path\n"
        "marker = os.environ.get('WP_O4_BOOTSTRAP_MARKER')\n"
        "if marker:\n"
        "    Path(marker).write_text('repo venv executed', encoding='utf-8')\n",
        encoding="utf-8",
    )
    # A .pth import is deterministic even when the host Python distribution
    # already supplies its own ``sitecustomize`` module.
    (site_packages / "wp_o4_repo_venv_witness.pth").write_text(
        "import wp_o4_repo_venv_witness\n",
        encoding="utf-8",
    )
    marker = tmp_path / "repo-venv-executed"
    env = os.environ.copy()
    env["WP_O4_BOOTSTRAP_MARKER"] = str(marker)

    # Prove the witness is live, then remove its evidence before exercising
    # the AgentOps Make boundary.
    armed = subprocess.run(
        [str(repo_venv / "bin" / "python"), "-c", "pass"],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert armed.returncode == 0, armed.stderr
    assert marker.read_text(encoding="utf-8") == "repo venv executed"
    marker.unlink()

    # A hostile source PATH entry wins ordinary `command -v python3`; the
    # bootstrap must remove it and select the later external host identity.
    env["PATH"] = os.pathsep.join(
        [str(repo_venv / "bin"), str(Path(sys.executable).parent), env["PATH"]]
    )
    result = subprocess.run(
        [
            "make",
            "-s",
            "agentops-report-root-check",
            "PYTHON=.venv/bin/python",
            f"AGENTOPS_REPORT_ROOT={tmp_path / 'agentops-reports'}",
        ],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )

    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
    assert not marker.exists(), (
        "repo .venv/sitecustomize executed before AgentOps runner validation"
    )


def test_make_agentops_bootstrap_preserves_external_venv_dependencies(
    tmp_path: Path,
) -> None:
    """Validation resolves symlinks, but execution retains venv identity."""
    checkout = tmp_path / "clean-checkout"
    _copy_tracked_checkout(checkout)
    external_venv = tmp_path / "external-agentops-venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(external_venv)],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    site_packages = (
        external_venv
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    site_packages.mkdir(parents=True, exist_ok=True)
    # Make the implementation-under-test dependencies available without
    # installing anything.  The witness module itself exists only in this
    # external venv, so resolving bin/python to its base executable loses it.
    dependency_roots: list[Path] = []
    source_boundaries = (REPO_ROOT.resolve(), checkout.resolve())
    for raw_path in sys.path:
        if not raw_path or "\n" in raw_path:
            continue
        try:
            dependency_root = Path(raw_path).resolve(strict=True)
        except OSError:
            continue
        if not dependency_root.is_dir() or dependency_root.name not in {
            "site-packages",
            "dist-packages",
        }:
            continue
        if any(
            dependency_root == boundary or boundary in dependency_root.parents
            for boundary in source_boundaries
        ):
            continue
        if dependency_root not in dependency_roots:
            dependency_roots.append(dependency_root)
    assert dependency_roots, "test interpreter exposes no external dependency root"
    (site_packages / "wp_o4_test_dependencies.pth").write_text(
        "".join(f"{path}\n" for path in dependency_roots),
        encoding="utf-8",
    )
    (site_packages / "wp_o4_venv_only_dependency.py").write_text(
        "VALUE = 'external venv dependency imported'\n",
        encoding="utf-8",
    )
    marker = tmp_path / "external-venv-dependency-imported"
    (site_packages / "wp_o4_external_venv_witness.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "from wp_o4_venv_only_dependency import VALUE\n"
        "marker = os.environ.get('WP_O4_VENV_DEPENDENCY_MARKER')\n"
        "if marker:\n"
        "    Path(marker).write_text(VALUE, encoding='utf-8')\n",
        encoding="utf-8",
    )
    (site_packages / "wp_o4_external_venv_witness.pth").write_text(
        "import wp_o4_external_venv_witness\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["WP_O4_VENV_DEPENDENCY_MARKER"] = str(marker)

    result = subprocess.run(
        [
            "make",
            "-s",
            "agentops-report-root-check",
            f"AGENTOPS_PYTHON={external_venv / 'bin' / 'python'}",
            f"AGENTOPS_REPORT_ROOT={tmp_path / 'agentops-reports'}",
        ],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )

    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
    assert marker.read_text(encoding="utf-8") == (
        "external venv dependency imported"
    )


@pytest.mark.parametrize(
    ("malicious_template", "expected_error"),
    [
        ("$(shell touch {marker})", "must not contain Make expansion syntax"),
        ("python3; touch {marker}", "must be a simple executable path"),
    ],
    ids=["make-expansion", "shell-expansion"],
)
def test_make_agentops_python_injection_is_inert(
    tmp_path: Path,
    malicious_template: str,
    expected_error: str,
) -> None:
    """Caller-controlled interpreter text is frozen, validated, and inert."""
    checkout = tmp_path / "clean-checkout"
    _copy_tracked_checkout(checkout)
    marker = tmp_path / "bootstrap-injection-executed"
    malicious = malicious_template.format(marker=marker)
    result = subprocess.run(
        [
            "make",
            "-s",
            "agentops-report-root-check",
            f"AGENTOPS_PYTHON={malicious}",
            f"AGENTOPS_REPORT_ROOT={tmp_path / 'agentops-reports'}",
        ],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )

    assert result.returncode == 2
    assert expected_error in result.stderr
    assert not marker.exists()


def test_make_rejects_repo_local_agentops_python_before_execution(
    tmp_path: Path,
) -> None:
    """Both lexical and resolved bootstrap identities stay out of source."""
    checkout = tmp_path / "clean-checkout"
    _copy_tracked_checkout(checkout)
    fake_python = checkout / ".venv" / "bin" / "python"
    fake_python.parent.mkdir(parents=True)
    marker = tmp_path / "repo-python-executed"
    fake_python.write_text(
        f"#!/bin/sh\ntouch {marker}\nexit 0\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    result = subprocess.run(
        [
            "make",
            "-s",
            "agentops-report-root-check",
            "AGENTOPS_PYTHON=.venv/bin/python",
            f"AGENTOPS_REPORT_ROOT={tmp_path / 'agentops-reports'}",
        ],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )

    assert result.returncode == 2
    assert "must be external to source and Git state" in result.stderr
    assert not marker.exists()


# --- O4-B7: the A2A identity target has a precise canonical name --------------

def test_agent_register_owns_identity_route_and_agent_onboard_is_alias() -> None:
    recipe = _recipe("agent-register")
    alias = _recipe("agent-onboard")
    assert "a2a_agent_onboard.py $(ARGS)" in recipe
    assert alias.splitlines() == ["agent-onboard: agent-register"]


# --- O4-B8: ARGS forwarding and usage exits -----------------------------------

@pytest.mark.timeout(120)
def test_make_forwards_onboard_args_and_usage_exit() -> None:
    recipe = _recipe("onboard")
    assert "agent_onboard.py $(ARGS)" in recipe
    result = _make("onboard", "ARGS=--definitely-not-a-real-flag")
    assert result.returncode == 2, (
        f"unknown onboard flags must keep exit 2, got {result.returncode}"
    )


@pytest.mark.timeout(120)
def test_door_delegates_to_compact_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Make door renders and propagates the compact engine's readiness."""
    monkeypatch.setenv("DHARMA_OPS_DIR", str(tmp_path / "ops"))
    result = _make("onboard")
    header = re.search(
        r"^DHARMA ONBOARD — [A-Z_]+ \(exit (\d+)\)$",
        result.stdout,
        re.MULTILINE,
    )
    assert header, "make onboard must render the compact CLI header and typed exit"
    reported_exit = int(header.group(1))
    assert (result.returncode == 0) == (reported_exit == 0), (
        "make onboard must succeed exactly when the rendered verdict is ready"
    )


def test_make_reports_failure_while_direct_cli_preserves_typed_exit() -> None:
    """GNU Make maps failed recipes to 2; JSON retains the command's type."""
    inside = REPO_ROOT / ".invalid-onboard-receipt-root"
    env = {**os.environ, "DHARMA_OPS_DIR": str(inside), "PYTHONDONTWRITEBYTECODE": "1"}
    direct = subprocess.run(
        [sys.executable, "scripts/governance/agent_onboard.py", "--json"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    through_make = subprocess.run(
        ["make", "-s", "onboard", "ARGS=--json", f"PYTHON={sys.executable}"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    direct_truth = json.loads(direct.stdout)
    make_truth = json.loads(through_make.stdout)
    assert direct.returncode == direct_truth["exit_code"] == 3
    assert through_make.returncode == 2
    assert make_truth["exit_code"] == 3
    assert not inside.exists()
