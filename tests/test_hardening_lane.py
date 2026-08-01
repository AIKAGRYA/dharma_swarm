"""Hardening lane v1: cap/receipt behavior + workflow contract pins (PR-E)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "runtime"))

import hardening_lane  # noqa: E402

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "hardening-lane.yml"


def test_receipt_writes_schema_and_payload(tmp_path: Path) -> None:
    out = tmp_path / "r.json"
    hardening_lane.receipt({"status": "NO_WORK", "reason": "x"}, out)
    stored = json.loads(out.read_text())
    assert stored["schema"] == "dharma.hardening_lane_receipt.v1"
    assert stored["status"] == "NO_WORK"
    assert stored["generated_at"]


def test_lane_refuses_without_agent_cmd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DHARMA_LANE_AGENT_CMD", raising=False)
    monkeypatch.setattr(hardening_lane, "open_lane_drafts", lambda repo: [])
    monkeypatch.setattr(
        hardening_lane, "select_target",
        lambda repo: {"kind": "mailbox", "task_id": "t", "summary": "s", "body": "b"},
    )
    out = tmp_path / "r.json"
    code = hardening_lane.main(["--repo", "o/r", "--receipt", str(out)])
    stored = json.loads(out.read_text())
    assert code == 0
    assert stored["status"] == "BLOCKED"
    assert "DHARMA_LANE_AGENT_CMD" in stored["reason"]


def test_lane_refuses_non_allowlisted_agent_binary(tmp_path: Path, monkeypatch) -> None:
    # The secret is a template NAME; a shell string (or any unknown selector)
    # must be refused — no environment-derived text may reach subprocess argv.
    monkeypatch.setenv("DHARMA_LANE_AGENT_CMD", "/usr/bin/curl http://evil")
    monkeypatch.setattr(hardening_lane, "open_lane_drafts", lambda repo: [])
    monkeypatch.setattr(
        hardening_lane, "select_target",
        lambda repo: {"kind": "mailbox", "task_id": "t", "summary": "s", "body": "b"},
    )
    out = tmp_path / "r.json"
    code = hardening_lane.main(["--repo", "o/r", "--receipt", str(out)])
    stored = json.loads(out.read_text())
    assert code == 0
    assert stored["status"] == "BLOCKED"
    assert "allowlist" in stored["reason"]


def test_no_work_is_a_clean_exit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hardening_lane, "open_lane_drafts", lambda repo: [])
    monkeypatch.setattr(hardening_lane, "select_target", lambda repo: None)
    out = tmp_path / "r.json"
    code = hardening_lane.main(["--repo", "o/r", "--receipt", str(out)])
    assert code == 0
    assert json.loads(out.read_text())["status"] == "NO_WORK"


def test_lane_constants_enforce_ruling_caps() -> None:
    assert hardening_lane.MAX_DIFF_LINES <= 600, "tier-1 ceiling from the ruling"
    assert "mike-watch" in hardening_lane.LANE_LABELS
    assert "walk-ready" in hardening_lane.LANE_LABELS
    # Every agent template is a list of literals — the de-taint invariant.
    for name, argv in hardening_lane.AGENT_COMMANDS.items():
        assert isinstance(argv, list) and argv, name
        assert all(isinstance(part, str) for part in argv), name
    source = (REPO_ROOT / "scripts" / "runtime" / "hardening_lane.py").read_text()
    assert '"--draft"' in source, "lane output must be draft-only"
    # Scan CODE, not prose: the security comments name `git push` when
    # explaining which config keys run programs during it.
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    assert "git push" not in code.replace('_git(["push"', ""), (
        "only the explicit lane-branch push is allowed"
    )
    assert code.count('_git(["push"') == 1


def test_workflow_contract() -> None:
    doc = yaml.safe_load(WORKFLOW.read_text())
    triggers = doc.get("on", doc.get(True))
    assert set(triggers) == {"schedule", "workflow_dispatch"}
    job = doc["jobs"]["harden"]
    assert job["steps"][0]["name"] == "Halt on loop kill-switch"
    assert "contents/docs/ops/loop_control/KILLSWITCH?ref=loop-control" in job["steps"][0]["run"]
    assert "No commit found" in job["steps"][0]["run"], "missing-branch 404 must read as absent"
    env = job["env"]
    assert int(env["LANE_MAX_DIFF_LINES"]) <= 600
    assert int(env["LANE_MAX_AGENT_SECONDS"]) <= 1800
    # The job envelope is a cap, but it must be LONGER than the work it
    # authorizes or a cap-compliant run is killed before it writes its
    # receipt — the old 45-minute timeout was shorter than its own
    # 1200 + 1800 second budgets (Codex on PR #1162).
    assert job["timeout-minutes"] <= 90, "runtime cap lives in the workflow"
    inner = int(env["LANE_MAX_AGENT_SECONDS"]) + int(env["LANE_MAX_TEST_SECONDS"])
    assert inner < job["timeout-minutes"] * 60, (
        "inner budgets must fit the job envelope with receipt-writing margin"
    )
    text = WORKFLOW.read_text()
    assert "DHARMA_LANE_AGENT_CMD: ${{ secrets.DHARMA_LANE_AGENT_CMD }}" in text


# --- Greptile review round on #1162 --------------------------------------


def test_agent_env_strips_github_credentials(monkeypatch) -> None:
    """The lane holds contents:write and pull-requests:write to open its own
    draft; the agent must not inherit that authority."""
    monkeypatch.setenv("GH_TOKEN", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "model-key")
    env = hardening_lane.agent_env()
    assert "GH_TOKEN" not in env
    assert "GITHUB_TOKEN" not in env
    assert "GITHUB_REPOSITORY" not in env
    # The agent's own model credentials are what it legitimately needs.
    assert env["ANTHROPIC_API_KEY"] == "model-key"


def test_delivery_ceiling_blocks_a_second_draft(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hardening_lane, "open_lane_drafts", lambda repo: [4242])
    out = tmp_path / "r.json"
    assert hardening_lane.main(["--repo", "o/r", "--receipt", str(out)]) == 0
    stored = json.loads(out.read_text())
    assert stored["status"] == "CAP_HIT"
    assert stored["cap"] == "open_lane_drafts"


def test_unknown_draft_count_refuses_to_deliver(tmp_path: Path, monkeypatch) -> None:
    """A failed enumeration must not read as 'zero drafts open'."""
    monkeypatch.setattr(hardening_lane, "open_lane_drafts", lambda repo: None)
    out = tmp_path / "r.json"
    assert hardening_lane.main(["--repo", "o/r", "--receipt", str(out)]) == 0
    assert json.loads(out.read_text())["status"] == "BLOCKED"


def test_diff_cap_measures_the_staged_set_including_new_files() -> None:
    """git diff HEAD omits untracked files, so a new-file-only fix measured
    zero and a large new file escaped both the cap and the commit."""
    source = (REPO_ROOT / "scripts" / "runtime" / "hardening_lane.py").read_text()
    assert '_git(["diff", "--cached", "--numstat"])' in source
    # Staging is BY EXPLICIT PATH: this lane stages work produced by an
    # untrusted agent, so a blanket add could sweep in secrets or generated
    # reports (CLAUDE.md hard rule; semgrep dharma.scripts-no-git-add-all).
    assert '"git", "add", "-A"' not in source
    assert '"git", "add", "."' not in source
    assert '"git", "add", "-u"' not in source
    assert '_git(["add", "--", *' in source


def test_nightly_target_requires_a_completed_run() -> None:
    source = (REPO_ROOT / "scripts" / "runtime" / "hardening_lane.py").read_text()
    assert 'runs[0].get("status") == "completed"' in source


def test_workflow_keeps_the_mailbox_overlay_out_of_the_worktree() -> None:
    text = (REPO_ROOT / ".github" / "workflows" / "hardening-lane.yml").read_text()
    assert "LANE_MAILBOX_ROOT" in text
    assert "git checkout origin/loop-tasks --" not in text, (
        "overlay must not land in the worktree the lane commits from"
    )


def test_nonzero_agent_exit_never_delivers() -> None:
    source = (REPO_ROOT / "scripts" / "runtime" / "hardening_lane.py").read_text()
    assert '"status": "AGENT_FAILED"' in source
    assert "if agent.returncode != 0:" in source


def test_missing_agent_binary_yields_a_blocked_receipt() -> None:
    source = (REPO_ROOT / "scripts" / "runtime" / "hardening_lane.py").read_text()
    assert "except FileNotFoundError:" in source
    assert "is not installed" in source


def test_nightly_unknown_is_not_reported_as_green(tmp_path: Path, monkeypatch) -> None:
    """An unreadable or non-terminal nightly must not read as health."""
    monkeypatch.setattr(hardening_lane, "open_lane_drafts", lambda repo: [])
    monkeypatch.setattr(
        hardening_lane, "select_target",
        lambda repo: {"kind": "nightly_unknown", "status": "in_progress",
                      "conclusion": None},
    )
    out = tmp_path / "r.json"
    assert hardening_lane.main(["--repo", "o/r", "--receipt", str(out)]) == 0
    stored = json.loads(out.read_text())
    assert stored["status"] == "BLOCKED"
    assert "not a verdict" in stored["reason"]


def test_workflow_installs_dependencies_and_always_reports() -> None:
    text = (REPO_ROOT / ".github" / "workflows" / "hardening-lane.yml").read_text()
    assert 'pip install -e ".[dev]"' in text, (
        "without dev deps make test-fast fails collection and every run is TESTS_RED"
    )
    assert "lane_exit=" in text, "delivery-failure receipts must reach the summary"
    # Inner budgets must fit the job envelope with receipt-writing margin.
    assert hardening_lane.MAX_AGENT_SECONDS + hardening_lane.MAX_TEST_SECONDS <= 65 * 60


def test_no_git_call_can_execute_an_agent_written_hook() -> None:
    """.git/hooks/ is outside every path allowlist, so an agent could drop a
    pre-commit hook and have the lane's own privileged commit run it with
    GH_TOKEN in scope. Hook execution is disabled on the command line, where
    the agent-writable .git/config cannot override it."""
    source = (REPO_ROOT / "scripts" / "runtime" / "hardening_lane.py").read_text()
    settings = set(hardening_lane.GIT_NO_EXEC)
    # Each of these names a program git would otherwise run, chosen from a
    # file the agent can write. Greptile found them one at a time on #1162.
    for key in ("core.hooksPath=/dev/null", "core.fsmonitor=false",
                "commit.gpgSign=false", "tag.gpgSign=false",
                "gpg.program=/dev/null", "gpg.ssh.program=/dev/null",
                "core.sshCommand=/dev/null"):
        assert key in settings, key
    assert '["git", *GIT_NO_EXEC, *args]' in source
    # Exactly one raw git invocation: the wrapper itself.
    assert source.count('_run(["git"') == 1, (
        "every git call must go through _git so no invocation misses the guard"
    )


def test_git_wrapper_prefixes_every_invocation() -> None:
    calls: list[list[str]] = []
    original = hardening_lane._run
    try:
        hardening_lane._run = lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", "")
        hardening_lane._git(["commit", "-m", "x"])
    finally:
        hardening_lane._run = original
    assert calls == [
        ["git", *hardening_lane.GIT_NO_EXEC, "commit", "-m", "x"]
    ]


def test_git_config_is_restored_byte_for_byte(tmp_path, monkeypatch) -> None:
    """A denylist of config keys is a treadmill — filter.*.clean runs on
    `git add`, credential.helper on `git push`, url.*.insteadOf redirects
    the push itself. Restoring the captured config closes the class."""
    config = tmp_path / "config"
    config.write_bytes(b"[core]\n\trepositoryformatversion = 0\n")
    monkeypatch.setattr(hardening_lane, "GIT_CONFIG_PATH", config)
    before = hardening_lane.snapshot_git_config()
    config.write_bytes(b"[gpg]\n\tprogram = /tmp/evil\n[commit]\n\tgpgSign = true\n")
    assert hardening_lane.git_config_restored(before) is True
    assert config.read_bytes() == before


def test_unrestorable_git_config_blocks_delivery(tmp_path, monkeypatch) -> None:
    """An unrestorable config is an agent-controlled config: stop, don't
    commit and push under it."""
    monkeypatch.setattr(hardening_lane, "GIT_CONFIG_PATH", tmp_path / "gone")
    assert hardening_lane.snapshot_git_config() is None
    assert hardening_lane.git_config_restored(None) is False


def test_config_is_restored_after_the_agent_and_after_the_tests() -> None:
    """The test subprocess had every opportunity the agent process had."""
    source = (REPO_ROOT / "scripts" / "runtime" / "hardening_lane.py").read_text()
    assert source.count("if not git_config_restored(config_before):") == 2
    assert source.index("config_before = snapshot_git_config()") < source.index(
        "agent = subprocess.run("
    ), "the restore target must be captured BEFORE the agent runs"


def test_verification_runs_without_the_lanes_write_credentials() -> None:
    """`make test-fast` executes an agent-writable Makefile (and conftest,
    and pyproject) — it is agent-controlled code and must not inherit the
    token that opens the draft."""
    source = (REPO_ROOT / "scripts" / "runtime" / "hardening_lane.py").read_text()
    assert 'timeout=MAX_TEST_SECONDS, env=agent_env()' in source


def test_agent_env_is_the_only_environment_handed_to_agent_controlled_code(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GH_TOKEN", "write-enabled")
    monkeypatch.setenv("PR_CI_HEALTH_PUSH_TOKEN", "also-write-enabled")
    env = hardening_lane.agent_env()
    assert not any(key.startswith(("GH_", "GITHUB_")) for key in env)
    assert "PR_CI_HEALTH_PUSH_TOKEN" not in env
    # PATH/HOME survive — a stripped-bare environment cannot run make.
    assert "PATH" in env


def test_agent_paths_exclude_secrets_reports_and_the_mailbox(monkeypatch) -> None:
    """The staged set is explicit and filtered — the lane must never carry
    an agent-dropped secret, a generated report, or operator task state."""
    porcelain = (
        " M dharma_swarm/fix.py\n"
        "?? tests/test_new.py\n"
        "?? .env\n"
        "?? reports/governance/out.json\n"
        "?? roaming_mailbox/tasks/mbx_op_x.json\n"
        "?? creds.pem\n"
        "R  old.py -> renamed.py\n"
    )
    monkeypatch.setattr(
        hardening_lane, "_run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, porcelain, ""),
    )
    paths = hardening_lane.agent_changed_paths()
    assert paths == ["dharma_swarm/fix.py", "renamed.py", "tests/test_new.py"]
