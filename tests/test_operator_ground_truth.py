"""Focused tests for ``scripts/operator_ground_truth.py``.

Covers:
    1. warning classifier catches the session_events-without-structured-rows case
    2. worktree porcelain parser handles realistic input
    3. JSON output / build_report contains the expected top-level keys
    4. process and runtime-DB scans degrade gracefully when artifacts are missing
    5. graceful handling of an unreadable / malformed SQLite file
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "operator_ground_truth.py"


def _load_module():
    name = "operator_ground_truth"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve string annotations via
    # sys.modules[cls.__module__].__dict__ (Python 3.13 dataclass behaviour).
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ogt():
    return _load_module()


# ---------------------------------------------------------------------------
# 1. warning classifier
# ---------------------------------------------------------------------------


def test_warning_classifier_flags_session_events_without_structured_rows(ogt):
    report = ogt.Report()
    report.runtime_dbs = [
        {
            "path": "/tmp/runtime.db",
            "tables": ["session_events", "task_claims", "delegation_runs"],
            "row_counts": {
                "session_events": 343,
                "task_claims": 0,
                "delegation_runs": 0,
                "artifact_records": 0,
                "memory_facts": 0,
                "context_bundles": 0,
                "operator_actions": 0,
            },
            "error": None,
        }
    ]
    warnings = ogt.classify_warnings(report)
    msgs = [w.message for w in warnings]
    assert any("session_events=343" in m and "structured runtime tables are empty" in m for m in msgs)


def test_warning_classifier_does_not_flag_when_structured_rows_exist(ogt):
    report = ogt.Report()
    report.runtime_dbs = [
        {
            "path": "/tmp/runtime.db",
            "tables": ["session_events", "task_claims"],
            "row_counts": {
                "session_events": 10,
                "task_claims": 1,
                "delegation_runs": None,
                "artifact_records": None,
                "memory_facts": None,
                "context_bundles": None,
                "operator_actions": None,
            },
            "error": None,
        }
    ]
    warnings = ogt.classify_warnings(report)
    assert not any("structured runtime tables are empty" in w.message for w in warnings)


def test_warning_classifier_marks_divergent_current_branch_as_critical(ogt):
    report = ogt.Report()
    report.repo = {"ahead": 2, "behind": 3}
    warnings = ogt.classify_warnings(report)
    assert any(
        w.severity == "critical" and "2 ahead and 3 behind" in w.message
        for w in warnings
    )


def test_warning_classifier_marks_dirty_worktree_as_warning(ogt):
    report = ogt.Report()
    report.worktrees = [
        {
            "path": "/Users/x/promotion_worktrees/operator-ground-truth-v0",
            "branch": "feature/operator-ground-truth-v0",
            "head": "deadbeef",
            "exists": True,
            "dirty": True,
            "modified": 11,
            "untracked": 0,
        }
    ]
    warnings = ogt.classify_warnings(report)
    assert any(
        w.severity == "warning" and "dirty changes" in w.message
        for w in warnings
    )


def test_warning_classifier_flags_multiple_worktrees_on_same_branch(ogt):
    report = ogt.Report()
    report.worktrees = [
        {"path": "/a", "branch": "feature/x", "exists": True, "dirty": False},
        {"path": "/b", "branch": "feature/x", "exists": True, "dirty": False},
    ]
    warnings = ogt.classify_warnings(report)
    assert any("multiple worktrees on same branch feature/x" in w.message for w in warnings)


# ---------------------------------------------------------------------------
# 2. worktree porcelain parser
# ---------------------------------------------------------------------------


def test_parse_worktree_porcelain_basic(ogt):
    text = (
        "worktree /Users/x/repo\n"
        "HEAD aaaa1111\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /tmp/detached\n"
        "HEAD bbbb2222\n"
        "detached\n"
        "\n"
        "worktree /tmp/locked\n"
        "HEAD cccc3333\n"
        "branch refs/heads/feat/foo\n"
        "locked\n"
        "prunable gitdir invalid\n"
        "\n"
    )
    out = ogt.parse_worktree_porcelain(text)
    assert len(out) == 3
    assert out[0]["path"] == "/Users/x/repo"
    assert out[0]["head"] == "aaaa1111"
    assert out[0]["branch"] == "refs/heads/main"
    assert out[0]["detached"] is False

    assert out[1]["detached"] is True
    assert out[1]["branch"] is None

    assert out[2]["locked"] is True
    assert out[2]["prunable"] is True
    assert out[2]["branch"] == "refs/heads/feat/foo"


def test_parse_worktree_porcelain_handles_trailing_no_blank(ogt):
    # git sometimes does not emit a trailing blank line
    text = "worktree /a\nHEAD 1234\nbranch refs/heads/main"
    out = ogt.parse_worktree_porcelain(text)
    assert len(out) == 1
    assert out[0]["path"] == "/a"


# ---------------------------------------------------------------------------
# 3. JSON output / top-level keys
# ---------------------------------------------------------------------------


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, timeout=30)


def _make_minimal_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-q", "-b", "main"], cwd=repo)
    _git(["config", "user.email", "t@t"], cwd=repo)
    _git(["config", "user.name", "t"], cwd=repo)
    (repo / "README").write_text("hi")
    _git(["add", "."], cwd=repo)
    _git(["commit", "-q", "-m", "init"], cwd=repo)
    return repo


def test_build_report_top_level_keys_and_json_roundtrip(ogt, tmp_path):
    repo = _make_minimal_repo(tmp_path)
    report = ogt.build_report(repo, include_processes=False, include_runtime_dbs=True)
    payload = report.to_dict()
    for key in ("repo", "worktrees", "runtime_dbs", "processes", "test_surface", "warnings", "summary", "generated_at"):
        assert key in payload, f"missing top-level key {key}"
    # JSON must be serialisable
    s = json.dumps(payload)
    assert isinstance(s, str)
    # Summary should be a non-empty single line
    assert "Current truth:" in payload["summary"]


def test_main_writes_output_and_returns_zero_on_clean_repo(ogt, tmp_path, capsys):
    repo = _make_minimal_repo(tmp_path)
    out_file = tmp_path / "out" / "ogt.json"
    rc = ogt.main(
        [
            "--repo-root",
            str(repo),
            "--json",
            "--no-processes",
            "--output",
            str(out_file),
        ]
    )
    assert rc == 0
    assert out_file.exists()
    payload = json.loads(out_file.read_text())
    assert payload["repo"]["root"] == str(repo)
    assert payload["worktrees"], "minimal repo should have at least its own worktree"


# ---------------------------------------------------------------------------
# 4. graceful degradation
# ---------------------------------------------------------------------------


def test_collect_processes_returns_empty_when_no_relevant_procs(ogt, tmp_path, monkeypatch):
    # Patch _run to simulate ps emitting only irrelevant processes.
    monkeypatch.setattr(ogt, "_run", lambda *a, **k: "1 launchd\n2 kernel_task\n")
    procs = ogt.collect_processes(tmp_path, set())
    assert procs == []


def test_collect_worktrees_handles_missing_git(ogt, tmp_path, monkeypatch):
    # Force _run to simulate "command unavailable" by always returning None.
    monkeypatch.setattr(ogt, "_run", lambda *a, **k: None)
    assert ogt.collect_worktrees(tmp_path) == []


def test_inspect_runtime_db_handles_malformed_file(ogt, tmp_path):
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"this is not a sqlite database")
    info = ogt.inspect_runtime_db(bad)
    # Either error is set, or row_counts are all None — but we must not raise.
    assert info["path"] == str(bad)
    assert set(info["row_counts"]) == set(ogt.CANONICAL_RUNTIME_TABLES)
    assert info["error"] is not None or all(v is None for v in info["row_counts"].values())


def test_inspect_runtime_db_empty_real_sqlite(ogt, tmp_path):
    db = tmp_path / "real.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE session_events (id INTEGER)")
    conn.execute("CREATE TABLE task_claims (id INTEGER)")
    conn.executemany("INSERT INTO session_events (id) VALUES (?)", [(i,) for i in range(5)])
    conn.commit()
    conn.close()
    info = ogt.inspect_runtime_db(db)
    assert info["error"] is None
    assert info["row_counts"]["session_events"] == 5
    assert info["row_counts"]["task_claims"] == 0
    # Tables not present should be reported as None
    assert info["row_counts"]["delegation_runs"] is None


def test_classify_warnings_emits_no_daemons_info_when_empty(ogt):
    report = ogt.Report()
    warnings = ogt.classify_warnings(report)
    assert any(w.severity == "info" and "no relevant daemons" in w.message for w in warnings)


# ---------------------------------------------------------------------------
# 5. argparse smoke
# ---------------------------------------------------------------------------


def test_parse_args_defaults(ogt):
    ns = ogt.parse_args([])
    assert ns.json is False
    assert ns.include_processes is True
    assert ns.include_runtime_dbs is True
    assert ns.include_tests is True
    assert ns.output is None


def test_parse_args_no_processes_flag(ogt):
    ns = ogt.parse_args(["--no-processes", "--no-runtime-dbs", "--no-tests"])
    assert ns.include_processes is False
    assert ns.include_runtime_dbs is False
    assert ns.include_tests is False


def test_main_returns_zero_by_default_even_with_critical_warning(ogt, tmp_path, monkeypatch):
    repo = _make_minimal_repo(tmp_path)
    critical_report = ogt.Report()
    critical_report.repo = {"root": str(repo), "ahead": 1, "behind": 1}
    critical_report.warnings = [{"severity": "critical", "message": "critical test"}]
    critical_report.summary = "Current truth: critical test"
    monkeypatch.setattr(ogt, "build_report", lambda *a, **k: critical_report)
    assert ogt.main(["--repo-root", str(repo), "--no-processes"]) == 0
    assert ogt.main(["--repo-root", str(repo), "--no-processes", "--fail-on-critical"]) == 1
