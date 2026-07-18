"""Behavioral tests for scripts/governance/pr_ci_safe_rebase.py.

Prove fail-closed behavior with scripted command traces, not string presence.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "scripts" / "governance" / "pr_ci_safe_rebase.py"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "pr-ci-health.yml"
REPO, PR, HEAD_REF, BASE_REF = "owner/repo", 42, "feature/ci-heal", "main"
SHA_A, SHA_B = "a" * 40, "b" * 40
RESTORE = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
PACKET = "reports/agentops/work_packets/example.json"
MUTATION = {"fetch", "checkout", "rebase", "push", "branch", "switch", "reset", "merge"}


def _load_helper():
    if not HELPER_PATH.is_file():
        pytest.fail(f"missing helper: {HELPER_PATH}")
    spec = importlib.util.spec_from_file_location("pr_ci_safe_rebase", HELPER_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@dataclass
class CmdResult:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


Handler = Callable[[list[str]], CmdResult | None]


@dataclass
class ScriptedRunner:
    calls: list[list[str]] = field(default_factory=list)
    handlers: list[Handler] = field(default_factory=list)
    default: CmdResult = field(default_factory=CmdResult)

    def add(self, handler: Handler) -> None:
        self.handlers.append(handler)

    def __call__(self, argv: list[str]) -> CmdResult:
        self.calls.append(list(argv))
        for handler in self.handlers:
            out = handler(argv)
            if out is not None:
                return out
        return self.default


def _pr_payload(
    *, sha: str = SHA_A, head_ref: str = HEAD_REF, base_ref: str = BASE_REF,
    full_name: str = REPO, changed_files: int = 1,
) -> dict[str, Any]:
    return {
        "number": PR, "base": {"ref": base_ref},
        "head": {"ref": head_ref, "sha": sha, "repo": {"full_name": full_name}},
        "changed_files": changed_files,
    }


def _file_entry(filename: str, previous: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"filename": filename}
    if previous is not None:
        entry["previous_filename"] = previous
    return entry


def _entries(n: int, prefix: str = "src/f") -> list[dict[str, Any]]:
    return [_file_entry(f"{prefix}{i}.py") for i in range(n)]


def _is_pr_meta(argv: list[str]) -> bool:
    return len(argv) >= 3 and argv[:2] == ["gh", "api"] and argv[2] == f"repos/{REPO}/pulls/{PR}"


def _is_files_page(argv: list[str], page: int) -> bool:
    if len(argv) < 3 or argv[:2] != ["gh", "api"]:
        return False
    t = argv[2]
    return (
        t.startswith(f"repos/{REPO}/pulls/{PR}/files?")
        and re.search(rf"(?:[?&])page={page}(?:&|$)", t) is not None
        and "per_page=100" in t
    )


def _assert_no_pr_head_mutation(calls: list[list[str]]) -> None:
    for argv in calls:
        if argv and argv[0] == "git" and len(argv) >= 2:
            if argv[1] != "check-ref-format" and argv[1] in MUTATION:
                pytest.fail(f"unexpected git mutation before skip: {argv}")


def _meta_sequence(payloads: list[dict[str, Any]]) -> Handler:
    state = {"i": 0}

    def handler(argv: list[str]) -> CmdResult | None:
        if not _is_pr_meta(argv):
            return None
        i = state["i"]
        if i >= len(payloads):
            return CmdResult(returncode=1, stderr="unexpected extra meta call")
        state["i"] = i + 1
        return CmdResult(stdout=json.dumps(payloads[i]))

    return handler


def _files_pages(pages: dict[int, list[dict[str, Any]] | str]) -> Handler:
    def handler(argv: list[str]) -> CmdResult | None:
        if len(argv) < 3 or argv[:2] != ["gh", "api"] or f"repos/{REPO}/pulls/{PR}/files?" not in argv[2]:
            return None
        m = re.search(r"(?:[?&])page=(\d+)", argv[2])
        if not m:
            return CmdResult(returncode=1, stderr="missing page")
        page = int(m.group(1))
        if page not in pages:
            return CmdResult(stdout="[]")
        value = pages[page]
        return CmdResult(stdout=value if isinstance(value, str) else json.dumps(value))

    return handler


def _ordinary_git_handlers(
    *, fetched_sha: str = SHA_A, push_rc: int = 0, rebase_rc: int = 0,
    abort_rc: int = 0, checkout_rc: int = 0, restore_checkout_rc: int = 0,
    check_ref_rc: int = 0,
) -> list[Handler]:
    def check_ref(argv: list[str]) -> CmdResult | None:
        if argv[:3] == ["git", "check-ref-format", "--branch"]:
            return CmdResult(returncode=check_ref_rc)
        return None

    def fetch_pr(argv: list[str]) -> CmdResult | None:
        if len(argv) >= 4 and argv[:3] == ["git", "fetch", "origin"] and f"refs/pull/{PR}/head" in argv[3]:
            return CmdResult()
        return None

    def rev_parse(argv: list[str]) -> CmdResult | None:
        if argv[:2] == ["git", "rev-parse"] and f"refs/pr-ci-health/{PR}" in argv:
            return CmdResult(stdout=fetched_sha + "\n")
        return None

    def checkout(argv: list[str]) -> CmdResult | None:
        if argv[0] != "git" or argv[1] not in {"checkout", "switch"}:
            return None
        if len(argv) >= 4 and argv[2] == "-f":  # restore: checkout -f <sha>
            return CmdResult(
                returncode=restore_checkout_rc,
                stderr="restore failed" if restore_checkout_rc else "",
            )
        return CmdResult(returncode=checkout_rc, stderr="checkout failed" if checkout_rc else "")

    def rebase(argv: list[str]) -> CmdResult | None:
        if argv[:2] != ["git", "rebase"]:
            return None
        if argv[:3] == ["git", "rebase", "--abort"]:
            return CmdResult(returncode=abort_rc, stderr="abort failed" if abort_rc else "")
        return CmdResult(returncode=rebase_rc, stderr="conflict" if rebase_rc else "")

    def push(argv: list[str]) -> CmdResult | None:
        if argv[:2] == ["git", "push"]:
            return CmdResult(returncode=push_rc, stderr="lease rejected" if push_rc else "")
        return None

    return [check_ref, fetch_pr, rev_parse, checkout, rebase, push]


def _runner_with(
    metas: list[dict[str, Any]], pages: dict[int, list[dict[str, Any]] | str],
    *, git: bool = True, fetched_sha: str = SHA_A, push_rc: int = 0,
    rebase_rc: int = 0, abort_rc: int = 0, checkout_rc: int = 0,
    restore_checkout_rc: int = 0,
) -> ScriptedRunner:
    runner = ScriptedRunner()
    runner.add(_meta_sequence(metas))
    runner.add(_files_pages(pages))
    if git:
        for h in _ordinary_git_handlers(
            fetched_sha=fetched_sha, push_rc=push_rc, rebase_rc=rebase_rc,
            abort_rc=abort_rc, checkout_rc=checkout_rc,
            restore_checkout_rc=restore_checkout_rc,
        ):
            runner.add(h)
    return runner


def _run(
    runner: ScriptedRunner, *, expected_base: str = BASE_REF,
    expected_head: str = HEAD_REF, restore_to: str | None = RESTORE,
) -> tuple[int, str]:
    return _load_helper().safe_rebase(
        repo=REPO, pr=PR, expected_base=expected_base, expected_head=expected_head,
        runner=runner, restore_to=restore_to,
    )


def _assert_skip_no_git(code: int, out: str, calls: list[list[str]]) -> None:
    assert code == 0
    assert out.startswith(f"SKIP PR #{PR}:")
    _assert_no_pr_head_mutation(calls)


def test_packet_on_page_two_skips_before_git() -> None:
    runner = _runner_with(
        [_pr_payload(changed_files=101)], {1: _entries(100), 2: [_file_entry(PACKET)]},
    )
    code, out = _run(runner)
    _assert_skip_no_git(code, out, runner.calls)
    assert "packet" in out.lower() or "Session Entry" in out or "work_packets" in out
    assert any(_is_files_page(c, 2) for c in runner.calls)
    assert not any("--paginate" in c for c in runner.calls)


def test_rename_away_previous_filename_packet_skips() -> None:
    runner = _runner_with(
        [_pr_payload(changed_files=1)],
        {1: [_file_entry("docs/moved.md", previous=PACKET)]},
    )
    code, out = _run(runner)
    _assert_skip_no_git(code, out, runner.calls)


def test_api_failure_and_malformed_page_skip() -> None:
    runner = ScriptedRunner()
    runner.add(_meta_sequence([_pr_payload(changed_files=1)]))

    def fail_files(argv: list[str]) -> CmdResult | None:
        if len(argv) >= 3 and "files?" in argv[2]:
            return CmdResult(returncode=1, stderr="boom")
        return None

    runner.add(fail_files)
    code, out = _run(runner)
    _assert_skip_no_git(code, out, runner.calls)

    runner2 = _runner_with([_pr_payload(changed_files=1)], {1: '{"not":"array"}'}, git=False)
    code2, out2 = _run(runner2)
    _assert_skip_no_git(code2, out2, runner2.calls)

    runner3 = _runner_with([_pr_payload(changed_files=1)], {1: [{"filename": 123}]}, git=False)
    code3, out3 = _run(runner3)
    _assert_skip_no_git(code3, out3, runner3.calls)


@pytest.mark.parametrize("changed", [3000, 3001])
def test_changed_files_at_or_over_cap_skips_before_files_api(changed: int) -> None:
    """GitHub hard-cap makes changed_files == 3000 ambiguous; fail closed at >= 3000."""
    runner = _runner_with([_pr_payload(changed_files=changed)], {}, git=False)
    code, out = _run(runner)
    _assert_skip_no_git(code, out, runner.calls)
    assert not any("files?" in " ".join(c) for c in runner.calls)
    assert not any(c and c[0] == "git" and c[1] in MUTATION for c in runner.calls)


def test_changed_files_count_mismatch_skips() -> None:
    runner = _runner_with([_pr_payload(changed_files=2)], {1: [_file_entry("a.py")]}, git=False)
    code, out = _run(runner)
    _assert_skip_no_git(code, out, runner.calls)


def test_full_final_page_nonempty_sentinel_skips() -> None:
    """Metadata 100 + full page1 + nonempty page2 sentinel must skip (no mutation)."""
    runner = _runner_with(
        [_pr_payload(changed_files=100)],
        {1: _entries(100), 2: [_file_entry("extra.py")]}, git=False,
    )
    code, out = _run(runner)
    _assert_skip_no_git(code, out, runner.calls)
    assert any(_is_files_page(c, 1) for c in runner.calls)
    assert any(_is_files_page(c, 2) for c in runner.calls)


def test_zero_changed_files_nonempty_page1_skips() -> None:
    """Metadata zero with nonempty page1 sentinel must skip (no mutation)."""
    runner = _runner_with(
        [_pr_payload(changed_files=0)], {1: [_file_entry("surprise.py")]}, git=False,
    )
    code, out = _run(runner)
    _assert_skip_no_git(code, out, runner.calls)
    assert any(_is_files_page(c, 1) for c in runner.calls)


def test_zero_changed_files_empty_sentinel_reaches_rebase() -> None:
    runner = _runner_with([_pr_payload(sha=SHA_A, changed_files=0)] * 3, {1: []})
    code, out = _run(runner)
    assert code == 0 and out.startswith(f"REBASED PR #{PR}:")
    assert any(_is_files_page(c, 1) for c in runner.calls)
    assert any(c == ["git", "rebase", "origin/main"] for c in runner.calls)


def test_full_page_empty_sentinel_reaches_rebase() -> None:
    runner = _runner_with(
        [_pr_payload(sha=SHA_A, changed_files=100)] * 3, {1: _entries(100), 2: []},
    )
    code, out = _run(runner)
    assert code == 0 and out.startswith(f"REBASED PR #{PR}:")
    assert any(_is_files_page(c, 2) for c in runner.calls)


def test_fork_pr_colliding_branch_name_skips_before_git() -> None:
    runner = _runner_with(
        [_pr_payload(full_name="other/fork", changed_files=1)], {1: [_file_entry("a.py")]},
    )
    code, out = _run(runner)
    _assert_skip_no_git(code, out, runner.calls)
    assert "fork" in out.lower() or "same-repo" in out.lower() or "repo" in out.lower()


def test_head_movement_after_pagination_skips_before_fetch() -> None:
    runner = _runner_with(
        [_pr_payload(sha=SHA_A, changed_files=1), _pr_payload(sha=SHA_B, changed_files=1)],
        {1: [_file_entry("a.py")]},
    )
    code, out = _run(runner)
    assert code == 0 and out.startswith(f"SKIP PR #{PR}:")
    assert not any(
        c[:2] == ["git", "fetch"] and any(f"refs/pull/{PR}/head" in x for x in c)
        for c in runner.calls
    )
    assert not any(c[:2] == ["git", "rebase"] for c in runner.calls)
    assert not any(c[:2] == ["git", "push"] for c in runner.calls)


def test_head_movement_before_push_skips_no_push() -> None:
    runner = _runner_with(
        [
            _pr_payload(sha=SHA_A, changed_files=1),
            _pr_payload(sha=SHA_A, changed_files=1),
            _pr_payload(sha=SHA_B, changed_files=1),
        ],
        {1: [_file_entry("a.py")]},
    )
    code, out = _run(runner)
    assert code == 0 and out.startswith(f"SKIP PR #{PR}:")
    assert not any(c[:2] == ["git", "push"] for c in runner.calls)
    assert any(c[:2] == ["git", "rebase"] for c in runner.calls)


def test_fetched_pr_ref_sha_mismatch_skips() -> None:
    runner = _runner_with(
        [_pr_payload(sha=SHA_A, changed_files=1), _pr_payload(sha=SHA_A, changed_files=1)],
        {1: [_file_entry("a.py")]}, fetched_sha=SHA_B,
    )
    code, out = _run(runner)
    assert code == 0 and out.startswith(f"SKIP PR #{PR}:")
    assert not any(c[:2] == ["git", "rebase"] for c in runner.calls)
    assert not any(c[:2] == ["git", "push"] for c in runner.calls)


def test_malicious_newline_filenames_remain_data() -> None:
    nasty = "src/evil.py\n; git push --force"
    runner = _runner_with([_pr_payload(sha=SHA_A, changed_files=1)] * 3, {1: [_file_entry(nasty)]})
    code, out = _run(runner)
    assert code == 0 and out.startswith(f"REBASED PR #{PR}:")
    for argv in runner.calls:
        assert all(isinstance(a, str) for a in argv)
        assert "rm -rf" not in " ".join(argv)
        for a in argv:
            if "\n" in a:
                assert a == nasty or a.startswith("HEAD:")


def test_ordinary_same_repo_reaches_rebase_and_explicit_lease() -> None:
    runner = _runner_with(
        [_pr_payload(sha=SHA_A, changed_files=1)] * 3, {1: [_file_entry("src/ok.py")]},
    )
    code, out = _run(runner)
    assert code == 0 and out.startswith(f"REBASED PR #{PR}:")
    first_fetch_idx = next(
        i for i, c in enumerate(runner.calls)
        if c[:2] == ["git", "fetch"] and any(f"refs/pull/{PR}/head" in x for x in c)
    )
    assert any(_is_pr_meta(c) for c in runner.calls[:first_fetch_idx])
    assert any("files?" in c[2] for c in runner.calls[:first_fetch_idx] if len(c) >= 3)
    fetch = runner.calls[first_fetch_idx]
    assert any(f"refs/pull/{PR}/head" in x for x in fetch) and HEAD_REF not in fetch
    assert any(c[0] == "git" and c[1] == "checkout" and f"ci-rebase/pr-{PR}" in c for c in runner.calls)
    assert any(c == ["git", "rebase", "origin/main"] for c in runner.calls)
    assert not any(c[:3] == ["git", "rebase", "--abort"] for c in runner.calls)
    push_calls = [c for c in runner.calls if c[:2] == ["git", "push"]]
    assert len(push_calls) == 1
    assert f"HEAD:refs/heads/{HEAD_REF}" in push_calls[0]
    assert f"--force-with-lease=refs/heads/{HEAD_REF}:{SHA_A}" in push_calls[0]


def test_lease_rejection_does_not_report_success() -> None:
    runner = _runner_with(
        [_pr_payload(sha=SHA_A, changed_files=1)] * 3, {1: [_file_entry("src/ok.py")]}, push_rc=1,
    )
    code, out = _run(runner)
    assert not out.startswith(f"REBASED PR #{PR}:")
    assert "SKIP" in out or code != 0 or "lease" in out.lower() or "push" in out.lower()
    assert any(c[:2] == ["git", "push"] for c in runner.calls)


@pytest.mark.parametrize("restore_to", ["", "not-a-sha"])
def test_invalid_restore_target_skips_before_mutation(restore_to: str) -> None:
    runner = _runner_with(
        [_pr_payload(sha=SHA_A, changed_files=1)] * 2, {1: [_file_entry("src/ok.py")]},
    )
    code, out = _run(runner, restore_to=restore_to)
    _assert_skip_no_git(code, out, runner.calls)
    assert "restore" in out.lower()
    assert not any(c[:2] == ["git", "fetch"] for c in runner.calls)


def test_restore_checkout_failure_after_push_is_error_not_rebased() -> None:
    runner = _runner_with(
        [_pr_payload(sha=SHA_A, changed_files=1)] * 3, {1: [_file_entry("src/ok.py")]},
        restore_checkout_rc=1,
    )
    code, out = _run(runner)
    assert code == 1 and out.startswith(f"ERROR PR #{PR}:")
    assert not out.startswith(f"REBASED PR #{PR}:")
    assert "restore" in out.lower() or "push completed" in out.lower()
    assert any(c[:2] == ["git", "push"] for c in runner.calls)
    assert any(c[:3] == ["git", "checkout", "-f"] and RESTORE in c for c in runner.calls)
    runner2 = _runner_with([_pr_payload()] * 2, {1: [_file_entry("src/ok.py")]}, checkout_rc=1)
    code2, out2 = _run(runner2)
    assert code2 == 0 and out2.startswith(f"SKIP PR #{PR}:")
    assert any(c[:3] == ["git", "checkout", "-f"] for c in runner2.calls)
    assert not any(c[:2] == ["git", "push"] for c in runner2.calls)


def test_rebase_abort_failure_surfaces_local_error() -> None:
    runner = _runner_with(
        [_pr_payload(sha=SHA_A, changed_files=1)] * 2, {1: [_file_entry("src/ok.py")]},
        rebase_rc=1, abort_rc=1,
    )
    code, out = _run(runner)
    assert code == 1 and out.startswith(f"ERROR PR #{PR}:")
    assert any(c[:3] == ["git", "rebase", "--abort"] for c in runner.calls)
    assert not any(c[:2] == ["git", "push"] for c in runner.calls)


def test_guard_completes_before_every_pr_head_mutation() -> None:
    runner = _runner_with(
        [_pr_payload(sha=SHA_A, changed_files=1)] * 3, {1: [_file_entry("src/ok.py")]},
    )
    _run(runner)

    def is_mutation(argv: list[str]) -> bool:
        if not argv or argv[0] != "git" or argv[1] in {"check-ref-format", "rev-parse"}:
            return False
        return argv[1] in MUTATION

    first = next(i for i, c in enumerate(runner.calls) if is_mutation(c))
    prefix = runner.calls[:first]
    assert any(_is_pr_meta(c) for c in prefix)
    assert any(len(c) >= 3 and "files?" in c[2] for c in prefix)
    assert sum(1 for c in prefix if _is_pr_meta(c)) >= 2


def test_workflow_docops_exclusion_before_helper() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    step = text.split("- name: Rebase conflict-free behind-main branches", 1)[1]
    exclusion = '[ "$head" = "chore/docops-autorefresh" ]'
    helper = "python3 scripts/governance/pr_ci_safe_rebase.py"
    assert exclusion in step and helper in step
    assert step.index(exclusion) < step.index(helper)


def test_workflow_delegates_to_helper_no_direct_pr_head_mutation() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "scripts/governance/pr_ci_safe_rebase.py" in text
    assert 'git fetch origin "$head"' not in text
    assert 'git checkout -B "ci-rebase/$head"' not in text
    assert "git rebase origin/main" not in text
    assert 'git push origin "ci-rebase/$head:$head"' not in text
    assert "gh api --paginate" not in text
    assert "SESSION_ENTRY_PACKET_PREFIX" not in text


def test_packet_prefix_constant_used_for_detection() -> None:
    mod = _load_helper()
    assert mod.PACKET_PREFIX == "reports/agentops/work_packets/"
    assert mod.is_protected_path(PACKET)
    assert not mod.is_protected_path("reports/agentops/unprotected/example.json")
    assert not mod.is_protected_path("reports/agentops/work_packets/example.txt")
    assert mod.packet_guard_selftest() == 0
