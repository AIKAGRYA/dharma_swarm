"""Unit tests for the agent-fast compiler. No network, no hosted CI."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.ci import agent_fast as af


def test_select_pytest_targets_maps_module_stem_to_existing_test(
    tmp_path: Path,
) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_agent_fast.py").write_text("# smoke\n", encoding="utf-8")
    (tmp_path / "tests" / "test_foo.py").write_text("# foo\n", encoding="utf-8")

    targets = af.select_pytest_targets(
        ["dharma_swarm/foo.py", "README.md"],
        tmp_path,
    )

    assert "tests/test_foo.py" in targets
    assert "tests/test_agent_fast.py" in targets
    assert "README.md" not in targets


def test_select_pytest_targets_includes_changed_test_file(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_agent_fast.py").write_text("# smoke\n", encoding="utf-8")
    (tmp_path / "tests" / "test_ci_truth.py").write_text("# ci\n", encoding="utf-8")

    targets = af.select_pytest_targets(["tests/test_ci_truth.py"], tmp_path)

    assert "tests/test_ci_truth.py" in targets


def test_select_pytest_targets_skips_missing_guesses(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_agent_fast.py").write_text("# smoke\n", encoding="utf-8")

    targets = af.select_pytest_targets(["dharma_swarm/does_not_exist_mod.py"], tmp_path)

    assert targets == ["tests/test_agent_fast.py"]


def test_select_pytest_targets_caps_blast_radius(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_agent_fast.py").write_text("# smoke\n", encoding="utf-8")
    paths = []
    for i in range(af.MAX_PYTEST_TARGETS + 5):
        name = f"test_mod{i}.py"
        (tests / name).write_text("# x\n", encoding="utf-8")
        paths.append(f"dharma_swarm/mod{i}.py")

    targets = af.select_pytest_targets(paths, tmp_path)

    assert len(targets) == af.MAX_PYTEST_TARGETS


def test_select_ruff_paths_fail_open_to_package_when_no_python(
    tmp_path: Path,
) -> None:
    assert af.select_ruff_paths(["README.md"], tmp_path) == ["dharma_swarm"]


def test_write_report_is_typed_json(tmp_path: Path) -> None:
    path = tmp_path / "ci-agent-report.json"
    af.write_report(path, {"schema": af.REPORT_SCHEMA, "ok": True})

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == af.REPORT_SCHEMA
    assert payload["ok"] is True


def test_main_smoke_scope_writes_report(tmp_path: Path, monkeypatch) -> None:
    report = tmp_path / "ci-agent-report.json"
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    class FakeProc:
        def __init__(self, code: int) -> None:
            self.returncode = code
            self.stdout = "ok\n"
            self.stderr = ""

    monkeypatch.setattr(af, "_run", lambda argv, cwd: FakeProc(0))

    status = af.main(["--event", "local", "--report", str(report)])

    assert status == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["schema"] == af.REPORT_SCHEMA
    assert payload["scope"] == "smoke"
    assert payload["ok"] is True
    assert payload["pytest_targets"] == list(af.SMOKE_TESTS)
    assert payload["local_command"] == "make agent-fast"
    assert "full suite" in payload["claim_boundary"]


def test_main_fail_open_when_diff_unreadable(tmp_path: Path, monkeypatch) -> None:
    report = tmp_path / "ci-agent-report.json"
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(af, "changed_paths", lambda base, head: None)

    class FakeProc:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(af, "_run", lambda argv, cwd: FakeProc())

    status = af.main(
        [
            "--event",
            "pull_request",
            "--base",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "--head",
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "--report",
            str(report),
        ]
    )

    assert status == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["scope"] == "smoke"
    assert "could not read diff" in payload["reason"]
