"""Cap, refusal and hand-off behaviour for the hardening lane's untrusted phase."""

from __future__ import annotations

import inspect
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


def _intercept(monkeypatch, handler) -> None:
    """Route lane_propose's subprocess calls through `handler` first.

    Patched at the subprocess layer, not at `_run`/`_git`: those call each
    other, so patching them recurses.
    """
    real_run = subprocess.run

    def dispatch(cmd, *args, **kwargs):
        verdict = handler(cmd, kwargs)
        if verdict is not None:
            return verdict
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(lane_propose.subprocess, "run", dispatch)


def _lane_repo_with_stub_agent(tmp_path: Path, monkeypatch,
                               script: str) -> Path:
    """A seeded repo and a real on-disk agent binary running `script`.

    Returns the GITHUB_OUTPUT path, so a caller can assert on the job output
    as well as the receipt. The agent is a real executable rather than a
    patched subprocess so `main()` exercises its actual argv/stdin path.
    """
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
    monkeypatch.setattr(lane_propose, "select_target",
                        lambda repo_: dict(TARGET))

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    agent = fake_bin / "fake-agent"
    agent.write_text(
        "#!/bin/sh\n"
        "cat > /dev/null\n"                       # consume the prompt on stdin
        "mkdir -p dharma_swarm\n" + script,
        encoding="utf-8",
    )
    agent.chmod(0o755)
    monkeypatch.setattr(lane_propose, "AGENT_COMMANDS", {"claude": [str(agent)]})
    # `make test-fast` stands in as a green run; the suite itself is not
    # under test here.
    monkeypatch.setattr(lane_propose, "MAKE_BIN", "/bin/true")
    return outputs


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
    monkeypatch.setenv("LANE_DELIVERY_PUSH_TOKEN", "secret")
    monkeypatch.setenv("ACTIONS_RUNTIME_TOKEN", "secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "keep-me")
    env = lane_propose.agent_env("claude")
    for leaked in ("GITHUB_TOKEN", "GH_TOKEN", "MERGEMASTERMIKE_PAT",
                   "LANE_DELIVERY_PUSH_TOKEN", "ACTIONS_RUNTIME_TOKEN"):
        assert leaked not in env
    assert env["ANTHROPIC_API_KEY"] == "keep-me"


def test_agent_gets_only_its_own_providers_credential(monkeypatch) -> None:
    """Handing every agent both provider keys let a compromised `claude`
    exfiltrate or spend the OpenAI credential it has no use for, and vice
    versa (Codex on #1200). Each selector sees only its own."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic")
    monkeypatch.setenv("OPENAI_API_KEY", "openai")

    claude = lane_propose.agent_env("claude")
    assert claude["ANTHROPIC_API_KEY"] == "anthropic"
    assert "OPENAI_API_KEY" not in claude

    npx = lane_propose.agent_env("claude-npx")
    assert npx["ANTHROPIC_API_KEY"] == "anthropic"
    assert "OPENAI_API_KEY" not in npx

    codex = lane_propose.agent_env("codex")
    assert codex["OPENAI_API_KEY"] == "openai"
    assert "ANTHROPIC_API_KEY" not in codex

    # The test run needs no model credential and therefore gets neither.
    tests = lane_propose.agent_env()
    assert "ANTHROPIC_API_KEY" not in tests
    assert "OPENAI_API_KEY" not in tests


def test_eol_attribute_is_rejected_like_a_clean_filter(tmp_path: Path,
                                                       monkeypatch) -> None:
    """Regression for a verified gap (Codex on #1200). Checking only the
    `filter` attribute did not close the tested-vs-delivered gap: `text
    eol=lf` on a CRLF worktree file stores LF in the index while the tests
    read CRLF, and because the transform is deterministic the re-add
    reproduces the same tree hash — so the equality check passes over content
    that was never tested."""
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    (repo / ".gitattributes").write_text("*.py text eol=lf\n", encoding="utf-8")

    # An LF file under `eol=lf` transforms nothing, so nothing is flagged —
    # the guard measures divergence, not the mere presence of an attribute.
    (repo / "clean.py").write_bytes(b"x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert lane_propose.index_transformed_paths(["clean.py"]) == []

    # A CRLF file under the same attribute is Codex's case: LF lands in the
    # index while the tests read CRLF.
    (repo / "crlf.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert lane_propose.index_transformed_paths(["crlf.py"]) == ["crlf.py"]


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


def _repo_with_global_config(tmp_path: Path, monkeypatch, config: str) -> Path:
    """A repo whose GLOBAL git config the 'agent' controls.

    The agent runs as the same UID on the same runner as the lane, so
    $HOME/.gitconfig is squarely within its reach — the earlier claim in this
    module that it "cannot write the runner's global or system config" was
    simply false (Devin on #1200).
    """
    repo = tmp_path / "r"
    repo.mkdir()
    for cmd in (["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "t@e.com"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=repo, check=True)
    global_cfg = tmp_path / "gitconfig"
    global_cfg.write_text(config, encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_cfg))
    monkeypatch.chdir(repo)
    return repo


def test_an_oddly_named_file_does_not_discard_the_whole_change_set(
        tmp_path: Path, monkeypatch) -> None:
    """Regression for the propose-side twin of the C-quoting bypass this PR
    fixed on the delivery side (Devin on #1200).

    `git status --porcelain` C-quotes non-ASCII paths, and stripping the outer
    quotes leaves the ESCAPE TEXT. `git add` dies on the resulting bogus
    pathspec BEFORE touching the index — atomically — so one oddly-named file
    discarded every other file the agent produced, and the run reported
    NO_DIFF after burning its whole budget. Measured against real git:

        parsed -> ['a.py', 'caf\\\\303\\\\251.py']
        git add -> exit 128, STAGED: []      # a.py lost too
    """
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)

    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "café.py").write_text("y = 2\n", encoding="utf-8")

    found = lane_propose.agent_changed_paths()
    assert found == ["a.py", "café.py"], found

    staged = lane_propose.stage_agent_changes()
    assert staged == ["a.py", "café.py"], staged
    listed = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"],
                            cwd=repo, capture_output=True, check=True).stdout
    assert b"a.py" in listed and "café.py".encode() in listed


def test_a_rename_is_recorded_from_the_z_record_shape(
        tmp_path: Path, monkeypatch) -> None:
    """`-z` emits a rename as `XY <new>\\0<old>\\0` — the source is its own
    NUL field with no status prefix, not a ` -> ` infix. The parser must
    consume that extra field or it loses the side that makes renames
    deliverable."""
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    subprocess.run(["git", "mv", "a.py", "moved.py"], cwd=repo, check=True)

    assert lane_propose.agent_changed_paths() == ["a.py", "moved.py"]


def test_a_failed_stage_blocks_rather_than_reporting_no_diff(
        tmp_path: Path, monkeypatch) -> None:
    """A discarded `git add` return code made an aborted stage look exactly
    like an agent that produced nothing."""
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")

    real_git = lane_propose._git
    monkeypatch.setattr(lane_propose, "_git", lambda args, **kw:
                        subprocess.CompletedProcess(
                            args, 128, "", "fatal: pathspec did not match")
                        if args and args[0] == "add" else real_git(args, **kw))
    assert lane_propose.stage_agent_changes() is None


def test_an_unmeasurable_staged_diff_blocks_rather_than_claiming_no_diff(
        monkeypatch) -> None:
    """The propose-side twin, found by sweeping rather than reported.

    Here the fail-open is worse than admitting an oversized diff: 0 lines
    reads as NO_DIFF, so an unreadable measurement writes a whole agent run
    off as "the agent changed nothing".
    """
    monkeypatch.setattr(lane_propose, "_git", lambda args, **kw:
                        subprocess.CompletedProcess(
                            args, lane_propose.EXIT_TIMEOUT, "", "timed out")
                        if args and args[0] == "diff"
                        else subprocess.CompletedProcess(args, 0, "", ""))
    assert lane_propose.diff_line_count() is None


def test_non_utf8_command_output_is_a_receipt_not_a_crashed_lane(
        tmp_path: Path, monkeypatch) -> None:
    """Regression for the propose-side twin of a fix this PR made on delivery.

    `lane_deliver._run` got `errors="surrogateescape"` earlier in this PR
    because a non-UTF-8 filename crashed the trusted job (Codex). The sibling
    helper here was left on strict `text=True`, and the exception is raised
    INSIDE `subprocess.run` — so it escapes `_run`, escapes `main()`, and
    skips `done()`/`receipt()`/`emit_status()`. The workflow step then reports
    NO_RECEIPT_WRITTEN: the exact pathology the TimeoutExpired arm exists to
    close, reachable through a different door. Measured on this branch:

        text=True, strict          -> UnicodeDecodeError: byte 0xff ...
        text=True, surrogateescape -> 'ok \\udcff\\udcfe bad\\n'

    No attack needed. `make test-fast` runs a suite the agent has just edited,
    so one test writing raw bytes to stdout ends the run with no report and
    the whole agent budget spent. (Devin on #1200.)
    """
    # The agent writes a real change AND emits undecodable bytes, exercising
    # both the direct `subprocess.run(agent_argv, ...)` call and the receipt.
    outputs = _lane_repo_with_stub_agent(
        tmp_path, monkeypatch,
        "printf 'x = 1\\n' > dharma_swarm/fix.py\n"
        "printf 'raw \\377\\376 bytes\\n'\n")

    code = lane_propose.main(_args(tmp_path))
    stored = json.loads((tmp_path / "r.json").read_text())
    assert code == 0, stored
    assert stored["status"] == "READY_TO_DELIVER", stored
    assert "status=READY_TO_DELIVER" in outputs.read_text()

    # And `_run` itself, on a command whose output cannot be decoded.
    result = lane_propose._run(
        [sys.executable, "-c",
         r"import sys; sys.stdout.buffer.write(b'ok \xff\xfe bad\n')"])
    assert result.returncode == 0
    # Round-trips: surrogateescape is reversible, `replace` would not be.
    assert result.stdout.encode("utf-8", "surrogateescape") == b"ok \xff\xfe bad\n"


def test_a_timed_out_command_keeps_its_undecodable_tail(monkeypatch) -> None:
    """The same handler, on the arm that reports a blown budget.

    The timeout arm decoded its captured tail with `"replace"` while the
    delivery twin used `"surrogateescape"`. That tail is the ONLY evidence a
    timed-out run leaves, and `replace` cannot be re-encoded to the bytes the
    command actually emitted — so the divergence moved with the rest of it.
    """
    def boom(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 1),
                                        output=b"partial \xff\xfe output")
    monkeypatch.setattr(lane_propose.subprocess, "run", boom)
    result = lane_propose._run(["make", "test-fast"], timeout=5)
    assert result.returncode == lane_propose.EXIT_TIMEOUT
    assert result.stdout.encode("utf-8", "surrogateescape") == \
        b"partial \xff\xfe output"


def test_a_binary_file_and_a_submodule_are_measured_not_refused(
        tmp_path: Path, monkeypatch) -> None:
    """The negative control for the malformed-numstat refusal below.

    `-` is not a parse failure. git prints it for content it cannot count in
    lines, and refusing it would make the lane BLOCK on any change that
    touches a binary file. Measured on git 2.43:

        git diff --cached --no-renames --numstat
            -\t-\tb.bin
            1\t0\tt.txt

    The `ls-tree --long` twin nearly cost more: a `-r` listing still yields
    gitlink entries, and their size column is `-` as well —

        160000 commit 6a755cf8...       -\tmysub

    so a size rule of "digits or refuse" would have turned every repository
    with a submodule into a REFUSED delivery. Written before the parser was,
    not after.
    """
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)

    (repo / "b.bin").write_bytes(bytes(range(256)) * 8)
    (repo / "t.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    # The binary scores zero (MAX_CHANGED_BLOB_BYTES is what bounds it), the
    # text file scores its one line, and neither is unmeasurable.
    assert lane_propose.diff_line_count() == 1


def test_an_unparseable_numstat_record_is_unmeasurable_not_undercounted(
        tmp_path: Path, monkeypatch) -> None:
    """Regression for a cap that reported the marks it happened to like.

    Greptile's reproduction on #1200: a real 650-line staged file paired with
    `1\tNOT_A_NUMBER\tgenerated/change.py` measured as ONE line and emitted
    READY_TO_DELIVER past the 600-line cap, because the parse loop skipped
    every non-digit cell in silence. An unreadable exit code already refused;
    an unreadable OUTPUT did not.

    Two things this test deliberately does not claim. Real git cannot emit
    such a record — counts are decimal and tab-bearing paths are C-quoted, so
    the first two fields are always the count pair; it is reachable only by
    replacing the resolved `git` binary, the documented-unfixable residual of
    #1162. And READY_TO_DELIVER is a proposal, not a delivery: the trusted job
    re-measures with its own git on its own runner
    (`lane_deliver.numstat_lines`, refused at MAX_DIFF_LINES), and never reads
    this number. So this closes the FIRST gate, not the last one.
    """
    outputs = _lane_repo_with_stub_agent(
        tmp_path, monkeypatch,
        # 650 real lines, well past MAX_DIFF_LINES.
        "seq 650 | sed 's/^/x = /' > dharma_swarm/fix.py\n")

    def handler(cmd, kwargs):
        if "--numstat" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, "1\tNOT_A_NUMBER\tdharma_swarm/fix.py\n", "")
        return None

    _intercept(monkeypatch, handler)
    code = lane_propose.main(_args(tmp_path))
    stored = json.loads((tmp_path / "r.json").read_text())
    assert code == 1, stored
    assert stored["status"] == "BLOCKED", stored
    assert "could not measure the staged diff" in stored["reason"], stored
    assert "READY_TO_DELIVER" not in outputs.read_text()
    assert not (tmp_path / "d.bundle").exists(), (
        "an unmeasurable change must not be handed to the delivery phase")

    # And the parser itself, on each shape, so the rule is pinned rather than
    # inferred from one end-to-end run.
    assert lane_propose.numstat_record_lines(["1", "2", "p"]) == 3
    assert lane_propose.numstat_record_lines(["-", "-", "p"]) == 0
    assert lane_propose.numstat_record_lines(["1", "NOT_A_NUMBER", "p"]) is None
    assert lane_propose.numstat_record_lines(["1", "2"]) is None, (
        "a truncated record is malformed too")


def test_an_unreadable_restage_listing_is_not_blamed_on_the_test_run(
        tmp_path: Path, monkeypatch) -> None:
    """Regression for a checked-but-not-propagated exit code (Devin, #1200).

    `_stageable()` read `git ls-files`' return code and then degraded on
    failure instead of refusing: `tracked` stayed empty, so every INDEX-ONLY
    path — a rename source, a staged deletion — was filtered out. At the
    post-test re-stage that is most of the set, because `git reset -q HEAD --`
    has just moved it there. `git add` then succeeded over a partial set,
    `post_test_tree` diverged from `measured_tree`, and the run reported "the
    test run altered the measured content" about a staging-infrastructure
    failure it could have named exactly.

    This is why the AST gate below now demands more than the word
    `returncode`: the old code inspected it and still fell through.

    The listing is failed on its SECOND call only — the first staging pass
    must succeed, or the run never reaches the re-stage and the test would
    pass for the wrong reason.
    """
    outputs = _lane_repo_with_stub_agent(
        tmp_path, monkeypatch, "printf 'x = 1\\n' > dharma_swarm/fix.py\n")
    seen = {"ls_files": 0}

    def handler(cmd, kwargs):
        if "ls-files" in cmd:
            seen["ls_files"] += 1
            if seen["ls_files"] > 1:
                return subprocess.CompletedProcess(
                    cmd, lane_propose.EXIT_TIMEOUT, b"", b"timed out")
        return None

    _intercept(monkeypatch, handler)
    code = lane_propose.main(_args(tmp_path))
    stored = json.loads((tmp_path / "r.json").read_text())
    assert seen["ls_files"] > 1, "the run never reached the post-test re-stage"
    assert code == 1, stored
    assert stored["status"] == "BLOCKED", stored
    assert "staging-infrastructure failure" in stored["reason"], stored
    assert "altered the measured content" not in stored["reason"], (
        "an unreadable listing must not be reported as test-run drift")
    assert "READY_TO_DELIVER" not in outputs.read_text()


def test_an_unreadable_status_listing_blocks_rather_than_claiming_no_change(
        monkeypatch) -> None:
    """Regression for the fail-open twin of the `git add` one (Devin, #1200).

    `_run_bytes` synthesizes EXIT_TIMEOUT / EXIT_NOT_FOUND with empty stdout,
    so mapping any non-zero result to [] wrote a whole agent run off as
    NO_DIFF when the lane simply could not read what changed.
    """
    monkeypatch.setattr(lane_propose, "_run_bytes", lambda *a, **k:
                        subprocess.CompletedProcess(
                            [], lane_propose.EXIT_TIMEOUT, b"", b"timed out"))
    assert lane_propose.agent_changed_paths() is None
    assert lane_propose.stage_agent_changes() is None


def test_a_git_mv_does_not_discard_the_rest_of_the_run(
        tmp_path: Path, monkeypatch) -> None:
    """Regression for a defect the rename fix introduced (Devin on #1200).

    A porcelain R/C record only appears once the rename is ALREADY staged, so
    the SOURCE exists in neither the worktree nor the index and matches no
    pathspec. `git add` validates every pathspec before touching the index, so
    passing it killed the whole call. Measured on this branch before the fix:

        agent_changed_paths() -> ['a.py', 'b.py', 'c.py']
        stage_agent_changes() -> None        # BLOCKED, c.py never staged

    The earlier rename test missed it by running `git reset -q HEAD --` first,
    which restores the source into the index and makes the pathspec match —
    the real first staging call never sees that state.
    """
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    subprocess.run(["git", "mv", "a.py", "b.py"], cwd=repo, check=True)
    (repo / "c.py").write_text("z = 3\n", encoding="utf-8")

    # Both sides are still RECORDED — the post-test re-stage needs the source.
    assert lane_propose.agent_changed_paths() == ["a.py", "b.py", "c.py"]

    staged = lane_propose.stage_agent_changes()
    assert staged == ["a.py", "b.py", "c.py"], staged

    # `--no-renames`, for the same reason the caps use it: with rename
    # detection on, `--name-only` collapses a.py -> b.py and hides the
    # deletion half that proves the source was staged.
    listed = subprocess.run(
        ["git", "diff", "--cached", "--no-renames", "--name-only"],
        cwd=repo, capture_output=True, text=True, check=True).stdout.split()
    assert sorted(listed) == ["a.py", "b.py", "c.py"], listed


def test_a_dangling_symlink_is_staged_in_the_first_pass(
        tmp_path: Path, monkeypatch) -> None:
    """Regression for a false BLOCKED (Devin on #1200).

    `_stageable` must match what `git add` ACCEPTS. `Path.exists()` follows
    symlinks, so a freshly created dangling symlink read as absent and was
    filtered out of the first staging pass — but it stays in the returned
    `staged` list, so the post-test pass re-added it, the trees diverged, and
    the run died claiming "the test run altered the measured content" about a
    mutation that never occurred. Measured against real git:

        Path('dangling').exists()   -> False    git add -- dangling -> exit 0
        os.path.lexists('dangling') -> True     (staged)
    """
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)

    (repo / "dangling").symlink_to("/nonexistent/target")
    (repo / "ok.py").write_text("x = 1\n", encoding="utf-8")

    staged = lane_propose.stage_agent_changes()
    assert staged == ["dangling", "ok.py"], staged

    # Both trees must agree: what pass 1 staged is what pass 2 reproduces.
    measured = subprocess.run(["git", "write-tree"], cwd=repo,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    subprocess.run(["git", "reset", "-q", "HEAD", "--"], cwd=repo, check=True)
    subprocess.run(["git", "add", "--", *staged], cwd=repo, check=True)
    post = subprocess.run(["git", "write-tree"], cwd=repo,
                          capture_output=True, text=True,
                          check=True).stdout.strip()
    assert post == measured, "the two staging passes must agree"


def test_a_created_then_deleted_file_does_not_fail_the_restage(
        tmp_path: Path, monkeypatch) -> None:
    """Regression for a false BLOCKED that blamed the test suite (Devin, #1200).

    The post-test re-stage passed the RAW recorded list and discarded its exit
    code. A file the agent created, staged and then deleted arrives as
    `AD path`; after `git reset -q HEAD --` it is in neither HEAD, the index,
    nor the worktree, so `git add` aborts atomically and NOTHING is re-staged.
    The tree comparison then blamed the test run. Measured:

        re-add exit    : 128  pathspec '...' did not match any files
        post_test_tree : differs -> BLOCKED "the test run altered the
                         measured content" with make replaced by /bin/true

    `_stageable` must be RECOMPUTED after the reset, because the reset is what
    changes which paths resolve.
    """
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)

    (repo / "keep.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "tmp.py").write_text("y = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "tmp.py"], cwd=repo, check=True)
    (repo / "tmp.py").unlink()

    staged = lane_propose.stage_agent_changes()
    assert staged is not None
    measured = subprocess.run(["git", "write-tree"], cwd=repo,
                              capture_output=True, text=True,
                              check=True).stdout.strip()

    # Bind to the PRODUCTION path, not to a re-implementation of it. Calling
    # _stageable() directly here would pass even with main() restored to the
    # raw list — which is exactly how two earlier tests in this PR passed for
    # the wrong reason. Assert main() actually routes the re-stage through the
    # filter and reads the result.
    restage_block = inspect.getsource(lane_propose.main)
    restage_block = restage_block[restage_block.index('"reset", "-q", "HEAD"'):]
    assert "_stageable(staged)" in restage_block, (
        "main() must recompute the stageable subset after the reset")
    assert "restage.returncode" in restage_block, (
        "main() must read the re-stage exit code")

    subprocess.run(["git", "reset", "-q", "HEAD", "--"], cwd=repo, check=True)
    restage = subprocess.run(
        ["git", "add", "--", *lane_propose._stageable(staged)],
        cwd=repo, capture_output=True, text=True)
    assert restage.returncode == 0, restage.stderr
    post = subprocess.run(["git", "write-tree"], cwd=repo,
                          capture_output=True, text=True,
                          check=True).stdout.strip()
    assert post == measured, "the re-stage must reproduce the measured tree"


def test_a_staged_deletion_does_not_discard_the_run(
        tmp_path: Path, monkeypatch) -> None:
    """`git rm` has the identical shape: the path is in neither the worktree
    nor the index, so it must not reach `git add`."""
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    (repo / "gone.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    subprocess.run(["git", "rm", "-q", "gone.py"], cwd=repo, check=True)
    (repo / "kept.py").write_text("y = 2\n", encoding="utf-8")

    staged = lane_propose.stage_agent_changes()
    assert staged is not None, "a staged deletion must not block the run"
    listed = subprocess.run(["git", "diff", "--cached", "--name-only"],
                            cwd=repo, capture_output=True, text=True,
                            check=True).stdout.split()
    assert sorted(listed) == ["gone.py", "kept.py"], listed


def test_a_rename_survives_the_post_test_restage(tmp_path: Path,
                                                 monkeypatch) -> None:
    """Regression for a rename that could never be delivered (Devin on #1200).

    `git status --porcelain` reports a staged rename as one record,
    `R  old -> new`. Keeping only `new` meant `measured_tree` held the delete
    of `old` AND the add of `new`, while the post-test re-stage
    (`git reset -q HEAD --` then re-add the recorded paths) restored `old`
    from HEAD with nothing to remove it. So `post_test_tree` never matched and
    every rename ended BLOCKED claiming "the test run altered the measured
    content" — on a run where the tests changed nothing.

    That directly contradicted the rename accounting added in this same PR:
    the diff cap counts renames at full cost, which only makes sense if a
    rename can actually ship.
    """
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    (repo / "big.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    subprocess.run(["git", "mv", "big.py", "moved.py"], cwd=repo, check=True)

    # Both sides are recorded, not just the destination.
    assert lane_propose.agent_changed_paths() == ["big.py", "moved.py"]

    measured = subprocess.run(["git", "write-tree"], cwd=repo,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    # The exact re-stage main() performs after the test run.
    subprocess.run(["git", "reset", "-q", "HEAD", "--"], cwd=repo, check=True)
    subprocess.run(["git", "add", "--", "big.py", "moved.py"], cwd=repo,
                   check=True)
    post = subprocess.run(["git", "write-tree"], cwd=repo,
                          capture_output=True, text=True,
                          check=True).stdout.strip()
    assert post == measured, "a rename must round-trip through the re-stage"

    # And the check still catches a genuine test-run mutation.
    (repo / "moved.py").write_text("x = 999\n", encoding="utf-8")
    subprocess.run(["git", "reset", "-q", "HEAD", "--"], cwd=repo, check=True)
    subprocess.run(["git", "add", "--", "big.py", "moved.py"], cwd=repo,
                   check=True)
    mutated = subprocess.run(["git", "write-tree"], cwd=repo,
                             capture_output=True, text=True,
                             check=True).stdout.strip()
    assert mutated != measured


def test_a_staged_rename_is_counted_not_collapsed_to_zero(
        tmp_path: Path, monkeypatch) -> None:
    """The propose-side cap is the FIRST gate and had the same hole Devin
    found on the delivery side (#1200).

    `git diff --cached --numstat` collapses a staged rename into one
    `0\\t0\\told => new` record, so an agent could `git mv` an 800-line file
    and measure as a no-op against MAX_DIFF_LINES.
    """
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    body = "\n".join(f"line_{i} = {i}" for i in range(800)) + "\n"
    (repo / "big.py").write_text(body, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    subprocess.run(["git", "mv", "big.py", "moved.py"], cwd=repo, check=True)
    # Sanity: git's default view really does report this as nothing.
    default = subprocess.run(["git", "diff", "--cached", "--numstat"], cwd=repo,
                             capture_output=True, text=True, check=True).stdout
    assert "=>" in default and default.split("\t")[0] == "0", default

    assert lane_propose.diff_line_count() >= 1600


def test_only_the_dedicated_claim_line_records_consumption(monkeypatch) -> None:
    """Regression for a fragility Devin raised on #1200.

    The reader used to scan the WHOLE PR body, which also carries a
    `- Target:` blob holding the operator's free-form task description. Any
    text containing `"task_id": "X"` would have recorded X as attempted, and
    `select_target()` cannot un-attempt anything — permanent starvation of an
    unrelated task.

    Measured: that did NOT reproduce, because the blob goes through
    json.dumps and the embedded quotes arrive escaped (`\\"task_id\\"`). But
    the safety was incidental — it held only while every task-derived field
    reached the body via json.dumps. Anchoring makes it explicit, so an
    unescaped field appearing later cannot poison the ledger.
    """
    claim = json.dumps({"task_id": "T-SELF"}, sort_keys=True)
    target = {"kind": "mailbox", "task_id": "T-SELF", "summary": "s",
              "body": 'continue {"task_id": "T-ESCAPED"} please'}
    body = (
        "Hardening-lane output\n\n"
        f"- Consumption claim: `{claim}`\n"
        f"- Target: `{json.dumps(target)[:400]}`\n"
        # An UNESCAPED marker, which the old whole-body scan would have taken.
        '- Note: "task_id": "T-UNESCAPED"\n'
    )
    rows = [{"headRefName": "lane/hardening-20260802T120000Z", "body": body}]
    monkeypatch.setattr(lane_propose, "_run", lambda *a, **k:
                        subprocess.CompletedProcess(
                            [], 0, json.dumps(rows), ""))

    seen = lane_propose.attempted_task_ids("o/r")
    assert seen == {"T-SELF"}, seen
    assert "T-UNESCAPED" not in seen
    assert "T-ESCAPED" not in seen


def test_a_hung_blob_read_is_a_verdict_not_a_crashed_lane(
        tmp_path: Path, monkeypatch) -> None:
    """Regression for an escape reintroduced by the fix for a different one
    (Devin on #1200).

    `index_transformed_paths()` called `subprocess.run` directly, so a hung
    `git cat-file` raised straight past done()/receipt()/emit_status() and the
    run ended NO_RECEIPT_WRITTEN — the exact pathology finding #7 of this PR
    set out to close.

    It could not simply route through `_run()`: that is `text=True`, so the
    comparison would be `str != bytes`, always True, flagging every path and
    leaving the lane permanently BLOCKED. `_run_bytes()` keeps the bytes and
    the fail-closed arms.
    """
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py"], cwd=repo, check=True)

    def hang(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 120))

    monkeypatch.setattr(lane_propose.subprocess, "run", hang)
    # A verdict, not an exception — and fail-closed, because a blob that
    # cannot be read cannot be proven to match.
    assert lane_propose.index_transformed_paths(["a.py"]) == ["a.py"]


def test_run_bytes_returns_bytes_and_survives_a_missing_binary() -> None:
    """The whole reason this helper exists rather than reusing `_run`."""
    ok = lane_propose._run_bytes(["git", "--version"])
    assert ok.returncode == 0
    assert isinstance(ok.stdout, bytes)

    missing = lane_propose._run_bytes(["definitely-not-a-real-binary-xyz"])
    assert missing.returncode == lane_propose.EXIT_NOT_FOUND


def test_untransformed_content_is_not_flagged(tmp_path: Path, monkeypatch) -> None:
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py"], cwd=repo, check=True)
    assert lane_propose.index_transformed_paths(["a.py"]) == []


def test_a_global_clean_filter_transforming_a_staged_path_is_caught(
        tmp_path: Path, monkeypatch) -> None:
    """The bypass `--local` opened (Devin on #1200).

    Scoping the config scan to --local was meant to stop git-lfs from blocking
    every run. It also blinded the guard to $HOME/.gitconfig, which the agent
    can write. Measuring the delivered bytes closes it regardless of scope.
    """
    repo = _repo_with_global_config(
        tmp_path, monkeypatch,
        '[filter "evil"]\n\tclean = sed s/SECRET/REDACTED/\n\tsmudge = cat\n')
    (repo / ".gitattributes").write_text("*.py filter=evil\n", encoding="utf-8")
    (repo / "a.py").write_text('x = "SECRET"\n', encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    # Sanity: the transform really happened.
    staged = subprocess.run(["git", "cat-file", "-p", ":a.py"], cwd=repo,
                            capture_output=True, text=True, check=True).stdout
    assert "REDACTED" in staged
    assert lane_propose.index_transformed_paths(["a.py"]) == ["a.py"]


def test_core_autocrlf_is_caught_with_no_gitattributes_at_all(
        tmp_path: Path, monkeypatch) -> None:
    """No attribute list can close this one, which is why the guard stopped
    enumerating attributes.

    `core.autocrlf=true` in the global config rewrites CRLF to LF on `git add`
    with NO .gitattributes present, so every `check-attr` the old guard asked
    about read `unspecified` while the delivered bytes still differed from the
    tested bytes. Verified against real git before this test was written.
    """
    repo = _repo_with_global_config(tmp_path, monkeypatch,
                                    "[core]\n\tautocrlf = true\n")
    (repo / "a.py").write_bytes(b'x = 1\r\ny = 2\r\n')
    subprocess.run(["git", "add", "a.py"], cwd=repo, check=True)
    assert not (repo / ".gitattributes").exists()
    # The old guard's inputs both read clean...
    attrs = subprocess.run(
        ["git", "check-attr", "filter", "text", "eol", "--", "a.py"],
        cwd=repo, capture_output=True, text=True, check=True).stdout
    assert "unspecified" in attrs and "filter: evil" not in attrs
    # ...while the bytes differ.
    assert lane_propose.index_transformed_paths(["a.py"]) == ["a.py"]


def test_a_global_lfs_filter_does_not_block_the_lane(tmp_path: Path,
                                                     monkeypatch) -> None:
    """Git LFS registers `filter.lfs.clean` GLOBALLY on GitHub runners.

    Treating that as an attack made the lane report BLOCKED on every run on
    every machine with git-lfs installed — caught by CI on #1200 before it
    shipped. It transforms nothing unless a path is actually attributed to it,
    so measuring bytes gets this right without a scope carve-out.
    """
    repo = _repo_with_global_config(
        tmp_path, monkeypatch,
        '[filter "lfs"]\n\tclean = git-lfs clean -- %f\n')
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py"], cwd=repo, check=True)
    # Sanity: git really does see it in the global scope.
    seen = subprocess.run(["git", "config", "--get-regexp", r"^filter\..*\.clean"],
                          cwd=repo, capture_output=True, text=True)
    assert "filter.lfs.clean" in seen.stdout
    assert lane_propose.index_transformed_paths(["a.py"]) == []


def test_a_deleted_path_has_no_delivered_bytes_to_diverge(
        tmp_path: Path, monkeypatch) -> None:
    repo = _repo_with_global_config(tmp_path, monkeypatch, "")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "t"], cwd=repo, check=True)
    subprocess.run(["git", "rm", "-q", "a.py"], cwd=repo, check=True)
    assert lane_propose.index_transformed_paths(["a.py"]) == []


def test_already_attempted_mailbox_task_is_not_reselected(monkeypatch) -> None:
    """Nothing writes a claim back to loop-tasks (propose holds contents:read),
    so consumption is inferred from the lane's own delivered PR bodies.
    Without it the oldest ready task was re-selected forever and newer tasks
    starved behind it."""
    rows = [{"headRefName": "lane/hardening-20260101T000000Z",
             "body": '- Consumption claim: `{"task_id": "T-1"}`\n'
                     '- Target: `{"kind": "mailbox", "task_id": "T-1"}`'}]
    monkeypatch.setattr(
        lane_propose, "_run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, json.dumps(rows), ""))
    assert lane_propose.attempted_task_ids("o/r") == {"T-1"}


def test_attempt_history_at_the_cap_fails_closed(monkeypatch) -> None:
    """Regression for a verified defect (Greptile, #1200). A truncated
    history is indistinguishable from a complete one in this response, and a
    truncated history reads as "never attempted" — which re-selects an old
    task and starves the newer ones, the exact failure the function exists to
    prevent. Greptile demonstrated it at the 100-PR boundary: 100 results
    skipped T-OLD correctly, 101 results (truncated to 100) re-selected it.
    """
    monkeypatch.setattr(lane_propose, "ATTEMPT_HISTORY_LIMIT", 3)
    rows = [{"headRefName": f"lane/hardening-2026010{i}T000000Z",
             "body": f'- Consumption claim: `{{"task_id": "T-{i}"}}`\n'}
            for i in range(3)]
    monkeypatch.setattr(
        lane_propose, "_run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, json.dumps(rows), ""))
    assert lane_propose.attempted_task_ids("o/r") is None

    # One under the cap is a complete view and answers normally.
    monkeypatch.setattr(
        lane_propose, "_run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 0, json.dumps(rows[:2]), ""))
    assert lane_propose.attempted_task_ids("o/r") == {"T-0", "T-1"}


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
    outputs = _lane_repo_with_stub_agent(
        tmp_path, monkeypatch, "printf 'x = 1\\n' > dharma_swarm/fix.py\n")

    code = lane_propose.main(_args(tmp_path))
    stored = json.loads((tmp_path / "r.json").read_text())
    assert code == 0, stored
    assert stored["status"] == "READY_TO_DELIVER", stored
    assert (tmp_path / "d.bundle").is_file()
    assert "status=READY_TO_DELIVER" in outputs.read_text()
    # The receipt labels itself untrusted, so no downstream reader mistakes
    # it for evidence.
    assert "untrusted" in stored["trust"]
