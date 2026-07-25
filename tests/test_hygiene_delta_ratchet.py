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


def _silent_excepts(n: int) -> str:
    """A module with exactly ``n`` silent except handlers."""
    blocks = [
        dedent(
            f"""
            def h{i}():
                try:
                    risky()
                except Exception:
                    pass
            """
        ).lstrip()
        for i in range(n)
    ]
    return "\n".join(blocks)


def test_pure_move_to_new_file_is_moved_not_regression(tmp_path):
    # PR #774 shape: 4 silent-excepts leave vector_store.py (15 -> 11) and
    # land verbatim in new embedders.py (0 -> 4). Net 0 => MOVED, exit 0.
    repo = _init_repo(tmp_path)
    _commit(repo, {"vector_store.py": _silent_excepts(15)}, "base")
    _commit(
        repo,
        {
            "vector_store.py": _silent_excepts(11),
            "embedders.py": _silent_excepts(4),
        },
        "head",
    )
    deltas = mod.evaluate("HEAD~1", "HEAD", repo)
    by_path = {d.path: d for d in deltas}
    assert not by_path["embedders.py"].base_exists
    assert by_path["embedders.py"].regressions() == {}
    assert by_path["embedders.py"].moved.get("silent_excepts") == (0, 4)
    assert by_path["vector_store.py"].improvements().get("silent_excepts") == (15, 11)
    rc = mod.main(["--base-ref", "HEAD~1", "--head-ref", "HEAD", "--repo-root", str(repo)])
    assert rc == 0


def test_new_file_with_net_new_violations_still_fails(tmp_path):
    # A new file whose counts are NOT covered by improvements elsewhere.
    repo = _init_repo(tmp_path)
    _commit(repo, {"clean.py": CLEAN_FILE}, "base")
    _commit(repo, {"new.py": _silent_excepts(2)}, "head")
    deltas = mod.evaluate("HEAD~1", "HEAD", repo)
    by_path = {d.path: d for d in deltas}
    assert by_path["new.py"].moved == {}
    assert by_path["new.py"].regressions().get("silent_excepts") == (0, 2)
    rc = mod.main(["--base-ref", "HEAD~1", "--head-ref", "HEAD", "--repo-root", str(repo)])
    assert rc == 1


def test_move_plus_genuinely_new_violation_fails(tmp_path):
    # Move 4 out of the source (-4) but land 5 in the new file (+5): net +1.
    repo = _init_repo(tmp_path)
    _commit(repo, {"vector_store.py": _silent_excepts(15)}, "base")
    _commit(
        repo,
        {
            "vector_store.py": _silent_excepts(11),
            "embedders.py": _silent_excepts(5),
        },
        "head",
    )
    deltas = mod.evaluate("HEAD~1", "HEAD", repo)
    by_path = {d.path: d for d in deltas}
    assert by_path["embedders.py"].moved == {}
    assert by_path["embedders.py"].regressions().get("silent_excepts") == (0, 5)
    rc = mod.main(["--base-ref", "HEAD~1", "--head-ref", "HEAD", "--repo-root", str(repo)])
    assert rc == 1


def test_net_credit_never_excuses_preexisting_file(tmp_path):
    # A file that existed at base keeps the strict per-file ratchet even
    # when improvements elsewhere make the touched-set net <= 0.
    repo = _init_repo(tmp_path)
    _commit(
        repo,
        {"a.py": CLEAN_FILE, "b.py": _silent_excepts(2)},
        "base",
    )
    _commit(
        repo,
        {"a.py": _silent_excepts(1), "b.py": CLEAN_FILE},
        "head",
    )
    deltas = mod.evaluate("HEAD~1", "HEAD", repo)
    by_path = {d.path: d for d in deltas}
    assert by_path["a.py"].moved == {}
    assert by_path["a.py"].regressions().get("silent_excepts") == (0, 1)
    rc = mod.main(["--base-ref", "HEAD~1", "--head-ref", "HEAD", "--repo-root", str(repo)])
    assert rc == 1


def test_render_text_reports_moved_section(tmp_path):
    repo = _init_repo(tmp_path)
    _commit(repo, {"src.py": _silent_excepts(3)}, "base")
    _commit(
        repo,
        {"src.py": CLEAN_FILE, "dst.py": _silent_excepts(3)},
        "head",
    )
    deltas = mod.evaluate("HEAD~1", "HEAD", repo)
    text = mod.render_text(deltas)
    assert "## REGRESSIONS  (0)" in text
    assert "## MOVED  (1)" in text
    assert "dst.py  silent_excepts: 0 -> 3" in text
    assert "## IMPROVEMENTS  (1)" in text


def test_to_dict_includes_moved(tmp_path):
    repo = _init_repo(tmp_path)
    _commit(repo, {"src.py": _silent_excepts(2)}, "base")
    _commit(
        repo,
        {"src.py": CLEAN_FILE, "dst.py": _silent_excepts(2)},
        "head",
    )
    deltas = mod.evaluate("HEAD~1", "HEAD", repo)
    by_path = {d.path: d.to_dict() for d in deltas}
    assert by_path["dst.py"]["moved"] == {"silent_excepts": [0, 2]}
    assert by_path["dst.py"]["base_exists"] is False
    assert by_path["dst.py"]["regressions"] == {}
    assert by_path["src.py"]["base_exists"] is True


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
