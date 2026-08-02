"""Cap, refusal and hand-off behaviour for the hardening lane's untrusted phase."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "runtime"))

import lane_propose  # noqa: E402

TARGET = {"kind": "mailbox", "task_id": "t", "summary": "s", "body": "b"}


def _args(tmp_path: Path) -> list[str]:
    return ["--repo", "o/r",
            "--receipt", str(tmp_path / "r.json"),
            "--bundle", str(tmp_path / "d.bundle")]


def test_receipt_writes_schema_and_payload(tmp_path: Path) -> None:
    out = tmp_path / "r.json"
    lane_propose.receipt({"status": "NO_WORK", "reason": "x"}, out)
    stored = json.loads(out.read_text())
    assert stored["schema"] == "dharma.lane_propose_receipt.v1"
    assert stored["status"] == "NO_WORK"
    assert stored["generated_at"]


def test_refuses_without_agent_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DHARMA_LANE_AGENT_CMD", raising=False)
    monkeypatch.setattr(lane_propose, "open_lane_drafts", lambda repo: [])
    monkeypatch.setattr(lane_propose, "select_target", lambda repo: dict(TARGET))
    code = lane_propose.main(_args(tmp_path))
    stored = json.loads((tmp_path / "r.json").read_text())
    assert code == 0
    assert stored["status"] == "BLOCKED"
    assert "DHARMA_LANE_AGENT_CMD" in stored["reason"]


def test_agent_selector_is_a_template_name_not_a_shell_string(
        tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DHARMA_LANE_AGENT_CMD", "/usr/bin/curl http://evil")
    monkeypatch.setattr(lane_propose, "open_lane_drafts", lambda repo: [])
    monkeypatch.setattr(lane_propose, "select_target", lambda repo: dict(TARGET))
    code = lane_propose.main(_args(tmp_path))
    stored = json.loads((tmp_path / "r.json").read_text())
    assert code == 0
    assert stored["status"] == "BLOCKED"
    assert "allowlist" in stored["reason"]


def test_no_work_when_nightly_positively_green(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(lane_propose, "open_lane_drafts", lambda repo: [])
    monkeypatch.setattr(lane_propose, "select_target", lambda repo: None)
    code = lane_propose.main(_args(tmp_path))
    stored = json.loads((tmp_path / "r.json").read_text())
    assert code == 0
    assert stored["status"] == "NO_WORK"


def test_unreadable_nightly_is_blocked_not_green(tmp_path: Path, monkeypatch) -> None:
    """Tri-state sensor: an API error must never be reported as health."""
    monkeypatch.setattr(lane_propose, "open_lane_drafts", lambda repo: [])
    monkeypatch.setattr(
        lane_propose, "select_target",
        lambda repo: {"kind": "nightly_unknown", "status": "api_error",
                      "conclusion": None})
    code = lane_propose.main(_args(tmp_path))
    stored = json.loads((tmp_path / "r.json").read_text())
    assert code == 0
    assert stored["status"] == "BLOCKED"
    assert "not a verdict" in stored["reason"]


def test_open_draft_ceiling_short_circuits_before_the_agent_runs(
        tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(lane_propose, "open_lane_drafts", lambda repo: [7])
    monkeypatch.setattr(lane_propose, "MAX_OPEN_LANE_DRAFTS", 1)
    called = []
    monkeypatch.setattr(lane_propose, "select_target",
                        lambda repo: called.append(1) or dict(TARGET))
    code = lane_propose.main(_args(tmp_path))
    stored = json.loads((tmp_path / "r.json").read_text())
    assert code == 0
    assert stored["status"] == "CAP_HIT"
    assert not called, "the ceiling must be checked before target selection"


def test_agent_environment_strips_every_credential_channel(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("GH_TOKEN", "secret")
    monkeypatch.setenv("MERGEMASTERMIKE_PAT", "secret")
    monkeypatch.setenv("ACTIONS_RUNTIME_TOKEN", "secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "keep-me")
    env = lane_propose.agent_env()
    for leaked in ("GITHUB_TOKEN", "GH_TOKEN", "MERGEMASTERMIKE_PAT",
                   "ACTIONS_RUNTIME_TOKEN"):
        assert leaked not in env
    assert env["ANTHROPIC_API_KEY"] == "keep-me"


def test_test_suite_timeout_becomes_a_cap_receipt_not_an_exception(
        tmp_path: Path, monkeypatch) -> None:
    """`subprocess.run(timeout=...)` raises TimeoutExpired. Uncaught, it flew
    past the receipt write and emit_status(), so a run that blew its test
    budget ended NO_RECEIPT_WRITTEN — losing the one outcome the budget
    exists to report."""
    def boom(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 1),
                                        output="partial output")
    monkeypatch.setattr(lane_propose.subprocess, "run", boom)
    result = lane_propose._run(["make", "test-fast"], timeout=5)
    assert result.returncode == lane_propose.EXIT_TIMEOUT
    assert "partial output" in result.stdout


def test_active_clean_filters_detects_configured_and_attributed(
        tmp_path: Path, monkeypatch) -> None:
    """A clean filter runs on `git add`, so it can put transformed bytes in
    the measured tree while the tests read the untransformed worktree — and
    because the filter is deterministic, re-adding reproduces the same hash
    and the equality check still passes. Detect and refuse."""
    repo = tmp_path / "r"
    repo.mkdir()
    for cmd in (["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "t@e.com"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=repo, check=True)
    monkeypatch.chdir(repo)
    assert lane_propose.active_clean_filters([]) == []

    subprocess.run(["git", "config", "--local", "filter.evil.clean",
                    "sed s/a/b/"], cwd=repo, check=True)
    found = lane_propose.active_clean_filters([])
    assert any("filter.evil.clean" in item for item in found), found


def test_a_global_filter_does_not_block_the_lane(tmp_path: Path,
                                                 monkeypatch) -> None:
    """Git LFS registers `filter.lfs.clean` in the GLOBAL config on GitHub
    runners. The agent cannot write global or system config, so a filter
    defined there is the runner's own setup, not an attack — and treating it
    as one made the lane report BLOCKED on every run everywhere git-lfs is
    installed. Caught by CI on #1200 before it could ship.
    """
    repo = tmp_path / "r"
    repo.mkdir()
    for cmd in (["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "t@e.com"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=repo, check=True)
    global_cfg = tmp_path / "gitconfig"
    global_cfg.write_text("[filter \"lfs\"]\n\tclean = git-lfs clean -- %f\n",
                          encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_cfg))
    monkeypatch.chdir(repo)
    # Sanity: git really does see it in the global scope.
    seen = subprocess.run(["git", "config", "--get-regexp", r"^filter\..*\.clean"],
                          cwd=repo, capture_output=True, text=True)
    assert "filter.lfs.clean" in seen.stdout
    # ...and the lane ignores it, because the agent cannot write there.
    assert lane_propose.active_clean_filters([]) == []


def test_already_attempted_mailbox_task_is_not_reselected(monkeypatch) -> None:
    """Nothing writes a claim back to loop-tasks (propose holds contents:read),
    so consumption is inferred from the lane's own delivered PR bodies.
    Without it the oldest ready task was re-selected forever and newer tasks
    starved behind it."""
    rows = [{"headRefName": "lane/hardening-20260101T000000Z",
             "body": 'Target: `{"kind": "mailbox", "task_id": "T-1"}`'}]
    monkeypatch.setattr(
        lane_propose, "_run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, json.dumps(rows), ""))
    assert lane_propose.attempted_task_ids("o/r") == {"T-1"}


def test_unreadable_attempt_history_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        lane_propose, "_run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "boom"))
    assert lane_propose.attempted_task_ids("o/r") is None


def test_unknown_attempt_history_blocks_rather_than_reworking(
        tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(lane_propose, "open_lane_drafts", lambda repo: [])
    monkeypatch.setattr(lane_propose, "select_target",
                        lambda repo: {"kind": "mailbox_unknown"})
    code = lane_propose.main(_args(tmp_path))
    stored = json.loads((tmp_path / "r.json").read_text())
    assert code == 0
    assert stored["status"] == "BLOCKED"
    assert "unattempted" in stored["reason"]


def test_summary_is_sanitized_to_one_printable_line() -> None:
    assert lane_propose.sanitize_summary("a\nb\tc") == "a b c"
    assert "\x00" not in lane_propose.sanitize_summary("a\x00b")
    assert len(lane_propose.sanitize_summary("x" * 500)) == 60
    assert lane_propose.sanitize_summary("   ") == "hardening lane output"


def test_excluded_paths_never_enter_the_change_set(tmp_path: Path,
                                                   monkeypatch) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    for path in ("dharma_swarm/keep.py", "reports/skip.json",
                 "roaming_mailbox/skip.json", "secrets.json", "creds.pem"):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    paths = lane_propose.agent_changed_paths()
    assert paths == ["dharma_swarm/keep.py"]


def test_no_blanket_staging_anywhere_in_the_module() -> None:
    """CLAUDE.md hard rule + semgrep dharma.scripts-no-git-add-all: an
    untrusted agent's output is staged by explicit path or not at all."""
    source = (REPO_ROOT / "scripts" / "runtime" / "lane_propose.py").read_text()
    # Code only — the prohibition is also NAMED in a comment, and matching
    # prose here would fail on the very sentence that documents the rule
    # (semgrep dharma.scripts-no-git-add-all matches patterns, not comments).
    code = "\n".join(
        line for line in source.splitlines()
        if not line.lstrip().startswith("#")
    )
    assert '"add", "-A"' not in code
    assert '"add", "."' not in code
    assert '"-A"' not in code


def test_propose_holds_no_push_or_pr_capability() -> None:
    """The structural claim of the split, pinned in source: this phase can
    neither push nor open a PR, so a compromised agent has nothing to steal
    that would let it deliver anything."""
    source = (REPO_ROOT / "scripts" / "runtime" / "lane_propose.py").read_text()
    assert '"push"' not in source
    assert '"pr", "create"' not in source
    # It hands off a bundle instead.
    assert '"bundle", "create"' in source


def test_bundle_handoff_is_written_and_status_is_emitted(
        tmp_path: Path, monkeypatch) -> None:
    """End-to-end on the propose side with a stub agent: a real bundle lands
    at the requested path and the job output says READY_TO_DELIVER."""
    repo = tmp_path / "r"
    repo.mkdir()
    for cmd in (["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "t@example.com"],
                ["git", "config", "user.name", "t"],
                ["git", "config", "commit.gpgSign", "false"]):
        subprocess.run(cmd, cwd=repo, check=True)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    monkeypatch.chdir(repo)

    outputs = tmp_path / "gh_output"
    outputs.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))
    monkeypatch.setenv("DHARMA_LANE_AGENT_CMD", "claude")
    monkeypatch.setattr(lane_propose, "open_lane_drafts", lambda repo_: [])
    monkeypatch.setattr(lane_propose, "select_target", lambda repo_: dict(TARGET))

    # A real agent binary on disk, exercising the real argv/stdin path rather
    # than a patched subprocess: it writes one file, like a hardening agent.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    agent = fake_bin / "fake-agent"
    agent.write_text(
        "#!/bin/sh\n"
        "cat > /dev/null\n"                       # consume the prompt on stdin
        "mkdir -p dharma_swarm\n"
        "printf 'x = 1\\n' > dharma_swarm/fix.py\n",
        encoding="utf-8",
    )
    agent.chmod(0o755)
    monkeypatch.setattr(lane_propose, "AGENT_COMMANDS", {"claude": [str(agent)]})
    # `make test-fast` stands in as a green run; the suite itself is not
    # under test here.
    monkeypatch.setattr(lane_propose, "MAKE_BIN", "/bin/true")

    code = lane_propose.main(_args(tmp_path))
    stored = json.loads((tmp_path / "r.json").read_text())
    assert code == 0, stored
    assert stored["status"] == "READY_TO_DELIVER", stored
    assert (tmp_path / "d.bundle").is_file()
    assert "status=READY_TO_DELIVER" in outputs.read_text()
    # The receipt labels itself untrusted, so no downstream reader mistakes
    # it for evidence.
    assert "untrusted" in stored["trust"]
