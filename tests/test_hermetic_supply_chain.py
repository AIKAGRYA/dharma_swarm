"""Acceptance tests for the hermetic supply chain + blast-radius CODEOWNERS.

Two oracles, matching .github/workflows/hermetic.yml:

1. CODEOWNERS routing is derived from *measured* transitive blast radius, and
   every module at/above the threshold — the six named in dive_arch_invariants.md
   in particular — carries an explicit CODEOWNERS entry. Removing one from the
   owner list makes the check fail (synthetic drift).

2. A lockfile that drifts from pyproject.toml fails `uv lock --check` while a
   clean tree passes. Skipped when uv is not installed (e.g. the pip-based
   required pytest lane); the hermetic.yml workflow is the CI enforcer.

3. (WP-0H) The hermetic.yml workflow text itself is contract-checked: it must
   gate pull requests, pin its installer and actions exactly, run the drift
   oracle before the frozen sync, and contain no false-green pattern. The
   uv-version lockstep with the Makefile is owned by
   tests/test_bootstrap_contract.py and is not re-asserted here.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "governance" / "codeowners_blast_radius.py"
CODEOWNERS = REPO_ROOT / ".github" / "CODEOWNERS"
PYPROJECT = REPO_ROOT / "pyproject.toml"
LOCKFILE = REPO_ROOT / "uv.lock"
HERMETIC_TEXT = (
    REPO_ROOT / ".github" / "workflows" / "hermetic.yml"
).read_text(encoding="utf-8")
HERMETIC = yaml.safe_load(HERMETIC_TEXT)

SIX_MEASURED = (
    "dharma_swarm/models.py",
    "dharma_swarm/correlation_context.py",
    "dharma_swarm/daemon_config.py",
    "dharma_swarm/runtime_contract.py",
    "dharma_swarm/spine/identity.py",
    "dharma_swarm/merkle_log.py",
)


def _load_module():
    spec = importlib.util.spec_from_file_location("codeowners_blast_radius", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_check_passes_on_current_tree():
    mod = _load_module()
    assert mod.main(["--check"]) == 0


def test_six_measured_modules_are_routed():
    mod = _load_module()
    patterns = mod._codeowners_patterns(CODEOWNERS)
    for rel in SIX_MEASURED:
        assert mod._is_covered(rel, patterns), f"{rel} not routed in CODEOWNERS"


def test_heavy_set_covers_the_six():
    mod = _load_module()
    modmap, blast = mod._measure()
    heavy = set(mod._heavy_modules(modmap, blast))
    for rel in SIX_MEASURED:
        dotted = rel.removesuffix(".py").replace("/", ".")
        assert dotted in heavy, f"{dotted} not in measured heavy set"


def test_dropping_a_required_owner_fails_check():
    # Synthetic: an owner list that omits a measured heavy module is uncovered.
    mod = _load_module()
    patterns = [p for p in mod._codeowners_patterns(CODEOWNERS) if p != "dharma_swarm/models.py"]
    assert not mod._is_covered("dharma_swarm/models.py", patterns)


def test_package_style_importfrom_resolves_imported_submodule(tmp_path):
    mod = _load_module()
    pkg = tmp_path / "dharma_swarm"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "hot_module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (pkg / "importer.py").write_text("from dharma_swarm import hot_module\n", encoding="utf-8")

    modmap = mod._module_map(pkg, tmp_path)
    importers = mod._direct_importers(modmap, tmp_path)

    assert importers["dharma_swarm.hot_module"] == {"dharma_swarm.importer"}


def test_relative_importfrom_resolves_imported_submodule(tmp_path):
    mod = _load_module()
    pkg = tmp_path / "dharma_swarm"
    child = pkg / "chetana"
    child.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (child / "__init__.py").write_text("", encoding="utf-8")
    (child / "staging.py").write_text("VALUE = 1\n", encoding="utf-8")
    (child / "actor.py").write_text("from . import staging\n", encoding="utf-8")

    modmap = mod._module_map(pkg, tmp_path)
    importers = mod._direct_importers(modmap, tmp_path)

    assert importers["dharma_swarm.chetana.staging"] == {"dharma_swarm.chetana.actor"}


def test_blast_radius_is_monotone_under_measurement():
    # The six named modules must each measure above the threshold, i.e. the
    # routing really is earned by coupling mass, not a hardcoded name list.
    mod = _load_module()
    _, blast = mod._measure()
    for rel in SIX_MEASURED:
        dotted = rel.removesuffix(".py").replace("/", ".")
        assert blast[dotted] >= mod.BLAST_THRESHOLD, f"{dotted}={blast[dotted]}"


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed in this lane")
def test_lockfile_drift_fails_clean_passes(tmp_path):
    for name in ("pyproject.toml", "uv.lock", "README.md"):
        src = REPO_ROOT / name
        if src.exists():
            shutil.copy(src, tmp_path / name)

    def lock_check() -> int:
        return subprocess.run(
            ["uv", "lock", "--check"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        ).returncode

    # Clean tree: lock matches pyproject -> green.
    assert lock_check() == 0, "clean tree should pass uv lock --check"

    # Synthetic drift: add a dependency without relocking -> red.
    pp = tmp_path / "pyproject.toml"
    text = pp.read_text()
    assert '"croniter>=2.0",' in text
    pp.write_text(text.replace('"croniter>=2.0",', '"croniter>=2.0",\n    "requests>=2.0",'))
    assert lock_check() != 0, "lockfile drift should fail uv lock --check"


# ── WP-0H: hermetic.yml workflow contract (text is the enforceable surface) ─


def _hermetic_command_lines() -> list[str]:
    return [
        line.strip()
        for line in HERMETIC_TEXT.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_hermetic_workflow_gates_pull_requests():
    triggers = HERMETIC.get("on") or HERMETIC[True]
    assert "pull_request" in triggers
    assert "merge_group" in triggers
    assert "hermetic-install" in HERMETIC["jobs"]


def test_hermetic_installer_is_version_pinned():
    uv_pin = HERMETIC["env"]["UV_VERSION"]
    assert re.match(r"^\d+\.\d+\.\d+$", str(uv_pin)), (
        f"UV_VERSION {uv_pin!r} is not an exact x.y.z pin"
    )
    # The install step must consume that exact pin — no floating `pip install uv`.
    assert '"uv==${UV_VERSION}"' in HERMETIC_TEXT


def test_hermetic_drift_oracle_runs_before_frozen_sync():
    check = HERMETIC_TEXT.index("uv lock --check")
    sync = HERMETIC_TEXT.index("uv sync --frozen")
    assert check < sync, "the drift oracle must run before the frozen sync"
    assert PYPROJECT.is_file() and LOCKFILE.is_file()


def test_hermetic_actions_are_sha_pinned():
    for job_id, job in HERMETIC["jobs"].items():
        for step in job["steps"]:
            uses = step.get("uses")
            if uses is None:
                continue
            assert re.search(r"@[0-9a-f]{40}\b", uses), (
                f"{job_id} uses unpinned action {uses!r}; pin to a full commit SHA"
            )


def test_hermetic_workflow_has_no_false_green_pattern():
    lines = _hermetic_command_lines()
    assert not any("|| true" in line for line in lines)
    assert not any("continue-on-error" in line for line in lines)
    pipe_to_shell = re.compile(r"(curl|wget)[^\n|]*\|\s*(ba|z)?sh")
    assert not any(pipe_to_shell.search(line) for line in lines)


def test_hermetic_install_is_bounded_and_serialized():
    assert HERMETIC["jobs"]["hermetic-install"]["timeout-minutes"] <= 30
    assert HERMETIC["concurrency"]["group"].startswith("hermetic-")


def test_every_polyglot_lane_has_a_committed_lockfile():
    # One lockfile authority per language lane (WP-0A / WP-0H supply chain).
    for lockfile in ("uv.lock", "dashboard/package-lock.json", "terminal/bun.lock"):
        assert (REPO_ROOT / lockfile).is_file(), f"missing lockfile {lockfile}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
