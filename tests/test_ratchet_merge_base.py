"""Acceptance: ratchet and module-budget grade from an immutable merge-base.

Invariant under test: a PR must not be able to raise its own ceiling. The
ratchet baseline and the Rule-10 grandfather map are graded from the
merge-base of the PR base and HEAD, so editing those files in the same diff
cannot loosen the gate.

The oracle is git itself: each test builds a real repository with a base
commit (the immutable fork point) and a head commit that tries to loosen the
gate, then asserts the loosening is ignored.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HYGIENE_DIR = REPO_ROOT / "scripts" / "governance" / "hygiene"
BUDGET_SCRIPT = REPO_ROOT / "scripts" / "governance" / "check_module_budget.py"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HYGIENE_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


counters_mod = _load("ratchet_counters")
ratchet = _load("ratchet")

Counter = counters_mod.Counter
Direction = counters_mod.Direction
Reading = counters_mod.Reading


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True
    ).strip()


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "commit.gpgsign", "false")


def _write_baselines(repo: Path, counters: dict[str, int]) -> Path:
    path = repo / ratchet.BASELINE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": ratchet.BASELINE_SCHEMA_VERSION,
                "tightened_on": "2026-06-12",
                "counters": counters,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _fake_counters(**values):
    direction = {"debt": Direction.DOWN, "asset": Direction.UP}
    return tuple(
        Counter(
            name=name,
            direction=direction[name.split("_")[0]],
            end_target=0,
            definition=f"fake {name}",
            measure=(lambda root, v=value: Reading(value=v, evidence=(f"{name}=",))),
        )
        for name, value in values.items()
    )


def _run(repo: Path, *flags: str) -> int:
    return ratchet.main(["--repo-root", str(repo), "--today", "2026-06-13", *flags])


@pytest.fixture()
def base_repo(tmp_path, monkeypatch):
    """A git repo whose base commit sets debt_things<=5, asset_things>=3."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_baselines(repo, {"debt_things": 5, "asset_things": 3})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base_sha = _git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(ratchet, "COUNTERS", _fake_counters(debt_things=5, asset_things=3))
    return repo, base_sha


# -- core acceptance: a PR cannot raise its own ratchet bar --------------------


def test_pr_raising_its_own_bar_is_rejected(base_repo, monkeypatch, capsys):
    repo, base_sha = base_repo
    # The PR loosens the down-counter baseline 5 -> 500 in the same diff and
    # ships debt of 100 (fine under 500, a regression under the real bar of 5).
    monkeypatch.setattr(ratchet, "COUNTERS", _fake_counters(debt_things=100, asset_things=3))
    _write_baselines(repo, {"debt_things": 500, "asset_things": 3})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "raise own bar")

    # Working-tree grading would wave this through (the hole we are closing).
    assert _run(repo) == ratchet.EXIT_GREEN
    # Merge-base grading reads the immutable bar (5) and rejects.
    assert _run(repo, "--baseline-merge-base-of", base_sha) == ratchet.EXIT_REGRESSION
    assert "debt_things" in capsys.readouterr().err


def test_legitimate_improvement_still_passes(base_repo, monkeypatch):
    repo, base_sha = base_repo
    # The PR genuinely lowers the debt to 3 and tightens its own baseline.
    monkeypatch.setattr(ratchet, "COUNTERS", _fake_counters(debt_things=3, asset_things=3))
    _write_baselines(repo, {"debt_things": 3, "asset_things": 3})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "improve")

    assert _run(repo, "--baseline-merge-base-of", base_sha) == ratchet.EXIT_GREEN


def test_new_counter_without_prior_bar_falls_back_to_working_tree(base_repo, monkeypatch):
    repo, base_sha = base_repo
    # The PR adds a brand-new counter absent from the merge-base baseline.
    monkeypatch.setattr(ratchet, "COUNTERS", _fake_counters(debt_things=5, debt_new=2))
    _write_baselines(repo, {"debt_things": 5, "debt_new": 2})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add counter")

    # No immutable bar exists for debt_new; its working-tree value is used and
    # the run is green (a new counter is a new fact, not a raised ceiling).
    assert _run(repo, "--baseline-merge-base-of", base_sha) == ratchet.EXIT_GREEN


def test_merge_base_unresolvable_fails_closed(tmp_path, monkeypatch):
    # A repo the flag cannot resolve a merge-base in must BLOCK, never silently
    # fall back to the editable working-tree baseline.
    repo = tmp_path / "nogit"
    repo.mkdir()
    _write_baselines(repo, {"debt_things": 5, "asset_things": 3})
    monkeypatch.setattr(ratchet, "COUNTERS", _fake_counters(debt_things=5, asset_things=3))
    assert _run(repo, "--baseline-merge-base-of", "origin/main") == ratchet.EXIT_BROKEN


# -- module-budget: a PR cannot grandfather its own oversized module ----------


def _init_budget_repo(tmp_path) -> tuple[Path, str]:
    repo = tmp_path / "budget"
    repo.mkdir()
    _init_repo(repo)
    (repo / "scripts" / "governance").mkdir(parents=True)
    shutil.copy(BUDGET_SCRIPT, repo / "scripts" / "governance" / "check_module_budget.py")
    (repo / "dharma_swarm").mkdir()
    (repo / "dharma_swarm" / "__init__.py").write_text("", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base budget")
    return repo, _git(repo, "rev-parse", "HEAD")


def _run_budget(repo: Path, base: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "scripts/governance/check_module_budget.py",
            "--base-ref",
            base,
            "--head-ref",
            "HEAD",
            *extra,
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


def test_pr_grandfathering_its_own_oversized_module_is_rejected(tmp_path):
    repo, base_sha = _init_budget_repo(tmp_path)
    # The PR adds a 1500-line module AND grandfathers it in the same diff.
    huge = repo / "dharma_swarm" / "huge.py"
    huge.write_text("x = 1\n" * 1500, encoding="utf-8")
    script = repo / "scripts" / "governance" / "check_module_budget.py"
    text = script.read_text(encoding="utf-8")
    text = text.replace(
        "GRANDFATHERED: dict[str, int] = {",
        'GRANDFATHERED: dict[str, int] = {\n    "dharma_swarm/huge.py": 1500,',
    )
    script.write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "sneak oversized module")

    # Working-tree grandfather map would wave it through.
    assert _run_budget(repo, base_sha).returncode == 0
    # Merge-base grandfather map (no huge.py) rejects it as a new oversized file.
    blocked = _run_budget(repo, base_sha, "--grandfather-base-ref", base_sha)
    assert blocked.returncode == 1
    assert "huge.py" in blocked.stdout


def test_module_budget_grandfather_base_ref_fails_closed(tmp_path):
    repo, _ = _init_budget_repo(tmp_path)
    (repo / "dharma_swarm" / "small.py").write_text("y = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "small")
    result = _run_budget(repo, "HEAD", "--grandfather-base-ref", "does-not-exist")
    assert result.returncode == 1
    assert "grandfather baseline unreadable" in result.stdout


# -- CODEOWNERS covers the named governance switch files ----------------------


def test_codeowners_covers_switch_files():
    text = (REPO_ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    for path in (
        "/docs/governance/hygiene/patterns/AI-M1.yaml",
        "/docs/governance/evidence_grades.yaml",
        "/docs/governance/hygiene/ratchet_baselines.json",
        "/scripts/governance/check_module_budget.py",
        "/.github/workflows/pudgala-rigor.yml",
    ):
        assert path in text, f"CODEOWNERS missing switch file: {path}"
