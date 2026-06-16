"""Unit tests for ``scripts/governance/hygiene/delta_ratchet.py``.

Uses a tmp git repo so the tests do not depend on the real repository's
history. No conftest fixture dependencies.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "governance"
    / "hygiene"
    / "delta_ratchet.py"
)

spec = importlib.util.spec_from_file_location("delta_ratchet", SCRIPT_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules["delta_ratchet"] = mod
spec.loader.exec_module(mod)  # type: ignore[union-attr]


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    return repo


def _commit(repo: Path, files: dict[str, str], msg: str) -> str:
    for rel, content in files.items():
        full = repo / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD").strip()


CLEAN_FILE = "def f():\n    return 1\n"
SYNC_IN_ASYNC = dedent(
    """
    import time

    async def g():
        time.sleep(1)
    """
).lstrip()
SILENT_EXCEPT = dedent(
    """
    def h():
        try:
            risky()
        except Exception:
            pass
    """
).lstrip()


def test_count_sync_in_async_detects_blocking_call():
    assert mod.count_sync_in_async(SYNC_IN_ASYNC) == 1
    assert mod.count_sync_in_async(CLEAN_FILE) == 0


def test_count_silent_excepts_detects_pass():
    assert mod.count_silent_excepts(SILENT_EXCEPT) == 1
    assert mod.count_silent_excepts(CLEAN_FILE) == 0


def test_count_silent_excepts_ignores_handled():
    src = dedent(
        """
        def h():
            try:
                risky()
            except Exception as e:
                raise RuntimeError() from e
        """
    ).lstrip()
    assert mod.count_silent_excepts(src) == 0


def test_count_silent_excepts_treats_logger_only_as_silent():
    src = dedent(
        """
        import logging
        log = logging.getLogger(__name__)
        def h():
            try:
                risky()
            except Exception:
                log.warning("oops")
        """
    ).lstrip()
    assert mod.count_silent_excepts(src) == 1


def test_evaluate_no_regression_when_unchanged(tmp_path):
    repo = _init_repo(tmp_path)
    base = _commit(repo, {"a.py": CLEAN_FILE}, "base")
    head = _commit(repo, {"b.py": CLEAN_FILE}, "head")  # different file changed but clean
    deltas = mod.evaluate(base, head, repo)
    assert all(not d.regressions() for d in deltas)


def test_evaluate_flags_regression_in_touched_file(tmp_path):
    repo = _init_repo(tmp_path)
    base = _commit(repo, {"a.py": CLEAN_FILE}, "base")
    head = _commit(repo, {"a.py": SYNC_IN_ASYNC}, "head")
    deltas = mod.evaluate(base, head, repo)
    by_path = {d.path: d for d in deltas}
    assert "a.py" in by_path
    regs = by_path["a.py"].regressions()
    assert "sync_in_async" in regs
    assert regs["sync_in_async"] == (0, 1)


def test_evaluate_reports_improvement_only(tmp_path):
    repo = _init_repo(tmp_path)
    base = _commit(repo, {"a.py": SILENT_EXCEPT}, "base")
    head = _commit(repo, {"a.py": CLEAN_FILE}, "head")
    deltas = mod.evaluate(base, head, repo)
    d = deltas[0]
    assert not d.regressions()
    imp = d.improvements()
    assert "silent_excepts" in imp
    assert imp["silent_excepts"] == (1, 0)


def test_evaluate_skips_unchanged_files(tmp_path):
    repo = _init_repo(tmp_path)
    base = _commit(
        repo,
        {"clean.py": CLEAN_FILE, "dirty.py": SYNC_IN_ASYNC},
        "base",
    )
    head = _commit(
        repo,
        {"new.py": CLEAN_FILE},  # only new.py changes; dirty.py keeps its violation but is exempt
        "head",
    )
    deltas = mod.evaluate(base, head, repo)
    touched = {d.path for d in deltas}
    assert "dirty.py" not in touched  # unchanged, ignored
    assert "new.py" in touched
    assert not any(d.regressions() for d in deltas)


def test_evaluate_new_file_with_violation_is_regression(tmp_path):
    repo = _init_repo(tmp_path)
    base = _commit(repo, {"clean.py": CLEAN_FILE}, "base")
    head = _commit(repo, {"new.py": SYNC_IN_ASYNC}, "head")
    deltas = mod.evaluate(base, head, repo)
    by_path = {d.path: d for d in deltas}
    assert "new.py" in by_path
    assert by_path["new.py"].regressions().get("sync_in_async") == (0, 1)


def test_main_exit_code_on_regression(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _commit(repo, {"a.py": CLEAN_FILE}, "base")
    _commit(repo, {"a.py": SYNC_IN_ASYNC}, "head")
    rc = mod.main(
        ["--base-ref", "HEAD~1", "--head-ref", "HEAD", "--repo-root", str(repo)]
    )
    assert rc == 1


def test_main_exit_code_clean(tmp_path):
    repo = _init_repo(tmp_path)
    _commit(repo, {"a.py": CLEAN_FILE}, "base")
    _commit(repo, {"a.py": CLEAN_FILE + "# new comment\n"}, "head")
    rc = mod.main(
        ["--base-ref", "HEAD~1", "--head-ref", "HEAD", "--repo-root", str(repo)]
    )
    assert rc == 0
