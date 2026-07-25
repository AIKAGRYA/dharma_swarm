"""Behavioral tests for scripts/governance/pr_ci_safe_rebase.py.
Strict scripted traces; guards assert exact SKIP diagnostics and call counts.
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
REPO, PR, HEAD_REF, BASE_REF = "owner/repo", 42, "feature/ci-heal", "main"
SHA_A, SHA_B = "a" * 40, "b" * 40
RESTORE = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
PACKET = "reports/agentops/work_packets/example.json"
SESSION = "changes a Session Entry packet under reports/agentops/work_packets/*.json"
WORKFLOW = (
    "changes a GitHub Actions workflow under .github/workflows/ "
    "(1 path(s)); workflow-write authority is not proven"
)
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
MetaItem = dict[str, Any] | CmdResult

@dataclass
class ScriptedRunner:
    calls: list[list[str]] = field(default_factory=list)
    handlers: list[Handler] = field(default_factory=list)
    def add(self, handler: Handler) -> None:
        self.handlers.append(handler)
    def __call__(self, argv: list[str]) -> CmdResult:
        self.calls.append(list(argv))
        for handler in self.handlers:
            out = handler(argv)
            if out is not None:
                return out
        raise AssertionError(f"unexpected command (no handler): {argv!r}")

def _pr_payload(
    *, sha: str = SHA_A, head_ref: str = HEAD_REF, base_ref: str = BASE_REF,
    full_name: str = REPO, changed_files: int = 1,
) -> dict[str, Any]:
    return {
        "number": PR, "base": {"ref": base_ref},
        "head": {"ref": head_ref, "sha": sha, "repo": {"full_name": full_name}},
        "changed_files": changed_files,
    }

def _fe(filename: str, previous: str | None = None) -> dict[str, Any]:
    e: dict[str, Any] = {"filename": filename}
    if previous is not None:
        e["previous_filename"] = previous
    return e

def _entries(n: int, prefix: str = "src/f") -> list[dict[str, Any]]:
    return [_fe(f"{prefix}{i}.py") for i in range(n)]

def _is_meta(a: list[str]) -> bool:
    return len(a) >= 3 and a[:2] == ["gh", "api"] and a[2] == f"repos/{REPO}/pulls/{PR}"

def _is_files(a: list[str], page: int) -> bool:
    if len(a) < 3 or a[:2] != ["gh", "api"]:
        return False
    t = a[2]
    return (t.startswith(f"repos/{REPO}/pulls/{PR}/files?")
            and re.search(rf"(?:[?&])page={page}(?:&|$)", t) is not None
            and "per_page=100" in t)

def _n_meta(calls: list[list[str]]) -> int:
    return sum(1 for c in calls if _is_meta(c))

def _n_files(calls: list[list[str]]) -> int:
    return sum(1 for c in calls if len(c) >= 3 and c[:2] == ["gh", "api"]
               and f"repos/{REPO}/pulls/{PR}/files?" in c[2])

def _n_git(calls: list[list[str]]) -> int:
    return sum(1 for c in calls if c and c[0] == "git")

def _no_mutation(calls: list[list[str]]) -> None:
    for a in calls:
        if a and a[0] == "git" and len(a) >= 2 and a[1] != "check-ref-format" and a[1] in MUTATION:
            pytest.fail(f"unexpected git mutation before skip: {a}")

def _meta_seq(payloads: list[MetaItem]) -> Handler:
    st = {"i": 0}
    def h(a: list[str]) -> CmdResult | None:
        if not _is_meta(a):
            return None
        i = st["i"]
        if i >= len(payloads):
            raise AssertionError(f"unexpected extra metadata read (index {i})")
        st["i"] = i + 1
        v = payloads[i]
        return v if isinstance(v, CmdResult) else CmdResult(stdout=json.dumps(v))
    return h

def _files_pages(pages: dict[int, list[dict[str, Any]] | str | CmdResult]) -> Handler:
    def h(a: list[str]) -> CmdResult | None:
        if len(a) < 3 or a[:2] != ["gh", "api"] or f"repos/{REPO}/pulls/{PR}/files?" not in a[2]:
            return None
        m = re.search(r"(?:[?&])page=(\d+)", a[2])
        if not m:
            raise AssertionError(f"files API missing page: {a[2]!r}")
        page = int(m.group(1))
        if page not in pages:
            raise AssertionError(f"unexpected files page {page}")
        v = pages[page]
        return v if isinstance(v, CmdResult) else CmdResult(stdout=v if isinstance(v, str) else json.dumps(v))
    return h

def _git_handlers(
    *, fetched_sha: str = SHA_A, push_rc: int = 0, rebase_rc: int = 0,
    abort_rc: int = 0, checkout_rc: int = 0, restore_rc: int = 0, check_ref_rc: int = 0,
) -> list[Handler]:
    def check_ref(a: list[str]) -> CmdResult | None:
        if a[:3] != ["git", "check-ref-format", "--branch"]:
            return None
        return CmdResult(returncode=check_ref_rc, stderr="bad ref" if check_ref_rc else "")
    def fetch_pr(a: list[str]) -> CmdResult | None:
        if len(a) >= 4 and a[:3] == ["git", "fetch", "origin"] and f"refs/pull/{PR}/head" in a[3]:
            return CmdResult()
        return None
    def rev_parse(a: list[str]) -> CmdResult | None:
        if a[:2] == ["git", "rev-parse"] and f"refs/pr-ci-health/{PR}" in a:
            return CmdResult(stdout=fetched_sha + "\n")
        return None
    def checkout(a: list[str]) -> CmdResult | None:
        if a[0] != "git" or a[1] not in {"checkout", "switch"}:
            return None
        if len(a) >= 4 and a[2] == "-f":
            return CmdResult(returncode=restore_rc, stderr="restore failed" if restore_rc else "")
        return CmdResult(returncode=checkout_rc, stderr="checkout failed" if checkout_rc else "")
    def rebase(a: list[str]) -> CmdResult | None:
        if a[:2] != ["git", "rebase"]:
            return None
        if a[:3] == ["git", "rebase", "--abort"]:
            return CmdResult(returncode=abort_rc, stderr="abort failed" if abort_rc else "")
        return CmdResult(returncode=rebase_rc, stderr="conflict" if rebase_rc else "")
    def push(a: list[str]) -> CmdResult | None:
        return (CmdResult(returncode=push_rc, stderr="lease rejected" if push_rc else "")
                if a[:2] == ["git", "push"] else None)
    return [check_ref, fetch_pr, rev_parse, checkout, rebase, push]

def _runner(
    metas: list[MetaItem], pages: dict[int, list[dict[str, Any]] | str | CmdResult],
    *, git: bool = True, fetched_sha: str = SHA_A, push_rc: int = 0,
    rebase_rc: int = 0, abort_rc: int = 0, checkout_rc: int = 0, restore_rc: int = 0,
    check_ref_rc: int = 0,
) -> ScriptedRunner:
    r = ScriptedRunner()
    r.add(_meta_seq(metas))
    r.add(_files_pages(pages))
    if git:
        for h in _git_handlers(
            fetched_sha=fetched_sha, push_rc=push_rc, rebase_rc=rebase_rc,
            abort_rc=abort_rc, checkout_rc=checkout_rc, restore_rc=restore_rc,
            check_ref_rc=check_ref_rc,
        ):
            r.add(h)
    return r

def _run(
    r: ScriptedRunner, *, restore_to: str | None = RESTORE, expected_head: str = HEAD_REF,
) -> tuple[int, str]:
    return _load_helper().safe_rebase(
        repo=REPO, pr=PR, expected_base=BASE_REF, expected_head=expected_head,
        runner=r, restore_to=restore_to,
    )

def _skip(
    code: int, out: str, calls: list[list[str]], *, reason: str,
    meta: int | None = None, files: int | None = None, git: int | None = 0,
) -> None:
    assert code == 0, out
    assert out == f"SKIP PR #{PR}: {reason}", out
    _no_mutation(calls)
    if meta is not None:
        assert _n_meta(calls) == meta, f"meta={_n_meta(calls)} want {meta}"
    if files is not None:
        assert _n_files(calls) == files, f"files={_n_files(calls)} want {files}"
    if git is not None:
        assert _n_git(calls) == git, f"git={_n_git(calls)} want {git}"

def _ready(meta: MetaItem, pages: dict[int, Any] | None = None, **kw: Any) -> ScriptedRunner:
    """Three meta reads + complete pages/Git so bypass cannot die on runner exhaustion."""
    return _runner([meta, meta, meta], pages if pages is not None else {1: [_fe("a.py")]}, **kw)

# --- exact-diagnostic guards (mutation targets; all bypass-ready) ---

def test_metadata_api_rc_nonzero_exact() -> None:
    fail = CmdResult(returncode=1, stdout=json.dumps(_pr_payload()), stderr="meta-boom")
    r = _ready(fail)
    code, out = _run(r)
    _skip(code, out, r.calls, reason="PR metadata API failed: meta-boom", meta=1, files=0, git=0)

def test_base_ref_not_main_exact() -> None:
    r = _ready(_pr_payload(base_ref="develop"))
    code, out = _run(r)
    _skip(code, out, r.calls, reason="base ref is not main", meta=1, files=0, git=0)

def test_head_ref_mismatch_exact() -> None:
    r = _ready(_pr_payload(head_ref="other-branch"))
    code, out = _run(r)
    _skip(code, out, r.calls, reason="head ref does not match expected-head", meta=1, files=0, git=0)

@pytest.mark.parametrize("sha", [123, "not-a-40-char-hex-sha-value-zzzzzzzz"])
def test_head_sha_type_or_regex_exact(sha: Any) -> None:
    p = _pr_payload()
    p["head"]["sha"] = sha
    r = _ready(p)
    code, out = _run(r)
    _skip(code, out, r.calls, reason="head.sha is not a 40-char hex SHA", meta=1, files=0, git=0)

def test_head_repo_non_object_exact() -> None:
    p = _pr_payload()
    p["head"]["repo"] = "not-an-object"
    r = _ready(p)
    code, out = _run(r)
    _skip(code, out, r.calls, reason="fork or missing head.repo; same-repo only", meta=1, files=0, git=0)

def test_head_repo_full_name_non_string_exact() -> None:
    p = _pr_payload()
    p["head"]["repo"]["full_name"] = 99
    r = _ready(p)
    code, out = _run(r)
    _skip(code, out, r.calls, reason="fork or missing head.repo.full_name; same-repo only",
          meta=1, files=0, git=0)

@pytest.mark.parametrize("changed", ["1", True, -1])
def test_changed_files_not_nonneg_int_exact(changed: Any) -> None:
    p = _pr_payload()
    p["changed_files"] = changed
    r = _ready(p)
    code, out = _run(r)
    _skip(code, out, r.calls, reason="changed_files is not a non-negative integer",
          meta=1, files=0, git=0)

def test_files_page_exceeds_per_page_exact() -> None:
    r = _ready(_pr_payload(), {1: _entries(101)})
    code, out = _run(r)
    _skip(code, out, r.calls, reason="files page 1 exceeds per_page=100", meta=1, files=1, git=0)

def test_premature_empty_files_page_exact() -> None:
    r = _ready(_pr_payload(), {1: []})
    code, out = _run(r)
    _skip(code, out, r.calls, reason="premature empty files page 1", meta=1, files=1, git=0)

def test_previous_filename_non_string_exact() -> None:
    r = _ready(_pr_payload(), {1: [{"filename": "a.py", "previous_filename": 123}]})
    code, out = _run(r)
    _skip(code, out, r.calls, reason="files page 1 previous_filename is not a string",
          meta=1, files=1, git=0)

def test_branch_validation_rc_nonzero_exact() -> None:
    r = _ready(_pr_payload(sha=SHA_A), check_ref_rc=1)
    code, out = _run(r)
    _skip(code, out, r.calls, reason=f"head ref failed check-ref-format: {HEAD_REF!r}",
          meta=2, files=1, git=1)
    assert r.calls[-1] == ["git", "check-ref-format", "--branch", HEAD_REF]
    assert not any(c[:2] == ["git", "fetch"] for c in r.calls)

def test_hostile_metachar_head_ref_inert_success() -> None:
    hostile = "feature/$(touch_pwn)"
    r = _ready(_pr_payload(sha=SHA_A, head_ref=hostile))
    code, out = _run(r, expected_head=hostile)
    assert code == 0 and out.startswith(f"REBASED PR #{PR}:")
    assert ["git", "check-ref-format", "--branch", hostile] in r.calls
    pushes = [c for c in r.calls if c[:2] == ["git", "push"]]
    assert len(pushes) == 1
    assert f"HEAD:refs/heads/{hostile}" in pushes[0]
    assert f"--force-with-lease=refs/heads/{hostile}:{SHA_A}" in pushes[0]

def test_rename_away_previous_filename_packet_skips() -> None:
    r = _ready(_pr_payload(), {1: [_fe("docs/moved.md", previous=PACKET)]})
    code, out = _run(r)
    _skip(code, out, r.calls, reason=f"{SESSION} (1 path(s))", meta=1, files=1, git=0)

def test_page_two_rename_away_previous_filename_packet_skips() -> None:
    r = _ready(_pr_payload(changed_files=101),
               {1: _entries(100), 2: [_fe("docs/moved.json", previous=PACKET)]})
    code, out = _run(r)
    _skip(code, out, r.calls, reason=f"{SESSION} (1 path(s))", meta=1, files=2, git=0)


def test_workflow_path_and_rename_skip_before_git() -> None:
    entries = [
        _fe(".github/workflows/new.yml"),
        _fe("docs/renamed.yml", previous=".github/workflows/old.yml"),
    ]
    for entry in entries:
        r = _ready(_pr_payload(), {1: [entry]})
        code, out = _run(r)
        _skip(code, out, r.calls, reason=WORKFLOW, meta=1, files=1, git=0)


def test_changed_files_count_mismatch_skips() -> None:
    r = _ready(_pr_payload(changed_files=2), {1: [_fe("a.py")]})
    code, out = _run(r)
    _skip(code, out, r.calls, reason="changed_files count mismatch: metadata=2 enumerated=1",
          meta=1, files=1, git=0)

def test_full_final_page_nonempty_sentinel_skips() -> None:
    r = _ready(_pr_payload(changed_files=100), {1: _entries(100), 2: [_fe("extra.py")]})
    code, out = _run(r)
    _skip(code, out, r.calls, reason="nonempty sentinel files page 2", meta=1, files=2, git=0)

def test_zero_changed_files_nonempty_page1_skips() -> None:
    r = _ready(_pr_payload(changed_files=0), {1: [_fe("surprise.py")]})
    code, out = _run(r)
    _skip(code, out, r.calls, reason="nonempty sentinel files page 1", meta=1, files=1, git=0)

def test_partial_non_final_files_page_skips() -> None:
    # Bypass-ready: page2 complete so mutant cannot die on missing page handler.
    r = _ready(_pr_payload(changed_files=101), {1: _entries(50), 2: _entries(51, "src/g")})
    code, out = _run(r)
    _skip(code, out, r.calls, reason="partial non-final files page 1", meta=1, files=1, git=0)

def test_duplicate_filename_skips() -> None:
    r = _ready(_pr_payload(changed_files=2), {1: [_fe("a.py"), _fe("a.py")]})
    code, out = _run(r)
    _skip(code, out, r.calls, reason="duplicate filename in files enumeration: 'a.py'",
          meta=1, files=1, git=0)

def test_files_api_nonzero_skips_exact() -> None:
    body = CmdResult(returncode=1, stdout=json.dumps([_fe("a.py")]), stderr="boom")
    r = _ready(_pr_payload(), {1: body})
    code, out = _run(r)
    _skip(code, out, r.calls, reason="files page 1 API failed: boom", meta=1, files=1, git=0)

def test_malformed_json_and_entry_shape_skips() -> None:
    # Array-shape case is the mutation target; other shapes share this test.
    r = _ready(_pr_payload(), {1: '{"not":"array"}'})
    code, out = _run(r)
    _skip(code, out, r.calls, reason="files page 1 is not a JSON array", meta=1, files=1, git=0)
    r2 = _runner([_pr_payload()], {1: "{not-json"}, git=False)
    c2, o2 = _run(r2)
    assert c2 == 0 and o2.startswith(f"SKIP PR #{PR}: malformed JSON for files page 1:")
    r3 = _runner([_pr_payload()], {1: ["not-an-object"]}, git=False)
    c3, o3 = _run(r3)
    _skip(c3, o3, r3.calls, reason="files page 1 entry is not an object", meta=1, files=1, git=0)
    r4 = _runner([_pr_payload()], {1: [{"filename": 123}]}, git=False)
    c4, o4 = _run(r4)
    _skip(c4, o4, r4.calls, reason="files page 1 entry missing string filename", meta=1, files=1, git=0)

# --- remaining behavioral coverage ---

def test_packet_on_page_two_skips_before_git() -> None:
    r = _runner([_pr_payload(changed_files=101)], {1: _entries(100), 2: [_fe(PACKET)]}, git=False)
    code, out = _run(r)
    _skip(code, out, r.calls, reason=f"{SESSION} (1 path(s))", meta=1, files=2, git=0)
    assert any(_is_files(c, 1) for c in r.calls) and any(_is_files(c, 2) for c in r.calls)
    assert not any("--paginate" in c for c in r.calls)

def test_metadata_object_and_type_failures() -> None:
    r = ScriptedRunner()
    r.add(lambda a: CmdResult(stdout="[]") if _is_meta(a) else None)
    code, out = _run(r)
    _skip(code, out, r.calls, reason="PR metadata is not a JSON object", meta=1, files=0, git=0)
    r2 = ScriptedRunner()
    r2.add(lambda a: CmdResult(stdout=json.dumps({"base": "x", "head": "y"})) if _is_meta(a) else None)
    c2, o2 = _run(r2)
    _skip(c2, o2, r2.calls, reason="PR metadata missing base/head objects", meta=1, files=0, git=0)

@pytest.mark.parametrize("changed", [3000, 3001])
def test_changed_files_at_or_over_cap_skips_before_files_api(changed: int) -> None:
    r = _runner([_pr_payload(changed_files=changed)], {}, git=False)
    code, out = _run(r)
    _skip(code, out, r.calls, reason=f"changed_files {changed} at or above enumerable cap 3000",
          meta=1, files=0, git=0)

def test_zero_changed_files_empty_sentinel_reaches_rebase() -> None:
    r = _runner([_pr_payload(sha=SHA_A, changed_files=0)] * 3, {1: []})
    code, out = _run(r)
    assert code == 0 and out.startswith(f"REBASED PR #{PR}:")
    assert _n_files(r.calls) == 1 and any(c == ["git", "rebase", "origin/main"] for c in r.calls)

def test_full_page_empty_sentinel_reaches_rebase() -> None:
    r = _runner([_pr_payload(sha=SHA_A, changed_files=100)] * 3, {1: _entries(100), 2: []})
    code, out = _run(r)
    assert code == 0 and out.startswith(f"REBASED PR #{PR}:")
    assert any(_is_files(c, 2) for c in r.calls)

def test_fork_pr_colliding_branch_name_skips_before_git() -> None:
    r = _runner([_pr_payload(full_name="other/fork")], {1: [_fe("a.py")]}, git=False)
    code, out = _run(r)
    _skip(code, out, r.calls, reason="fork PR head repo differs from target; same-repo only",
          meta=1, files=0, git=0)

def test_head_movement_after_pagination_skips_before_fetch() -> None:
    r = _runner([_pr_payload(sha=SHA_A), _pr_payload(sha=SHA_B)], {1: [_fe("a.py")]}, git=False)
    code, out = _run(r)
    _skip(code, out, r.calls, reason="PR head/base/files race after file enumeration",
          meta=2, files=1, git=0)

def test_head_movement_before_push_skips_no_push() -> None:
    r = _runner([_pr_payload(sha=SHA_A), _pr_payload(sha=SHA_A), _pr_payload(sha=SHA_B)],
                {1: [_fe("a.py")]})
    code, out = _run(r)
    assert code == 0 and out == f"SKIP PR #{PR}: PR head moved before push; not rewriting"
    assert not any(c[:2] == ["git", "push"] for c in r.calls)
    assert any(c[:2] == ["git", "rebase"] for c in r.calls)
    assert any(c[:3] == ["git", "checkout", "-f"] and RESTORE in c for c in r.calls)

def test_fetched_pr_ref_sha_mismatch_skips() -> None:
    r = _runner([_pr_payload(sha=SHA_A), _pr_payload(sha=SHA_A)], {1: [_fe("a.py")]},
                fetched_sha=SHA_B)
    code, out = _run(r)
    assert code == 0 and out == f"SKIP PR #{PR}: fetched PR ref SHA does not match inspected head.sha"
    assert not any(c[:2] == ["git", "rebase"] for c in r.calls)
    assert not any(c[:2] == ["git", "push"] for c in r.calls)

def test_malicious_newline_filenames_remain_data() -> None:
    nasty = "src/evil.py\n; git push --force"
    r = _runner([_pr_payload(sha=SHA_A)] * 3, {1: [_fe(nasty)]})
    code, out = _run(r)
    assert code == 0 and out.startswith(f"REBASED PR #{PR}:")
    assert all("\n" not in x or x == nasty or x.startswith("HEAD:") for a in r.calls for x in a)

def test_ordinary_same_repo_reaches_rebase_and_explicit_lease() -> None:
    r = _runner([_pr_payload(sha=SHA_A)] * 3, {1: [_fe("src/ok.py")]})
    code, out = _run(r)
    assert code == 0 and out.startswith(f"REBASED PR #{PR}:")
    fi = next(i for i, c in enumerate(r.calls)
              if c[:2] == ["git", "fetch"] and any(f"refs/pull/{PR}/head" in x for x in c))
    assert any(_is_meta(c) for c in r.calls[:fi])
    assert any("files?" in c[2] for c in r.calls[:fi] if len(c) >= 3)
    assert HEAD_REF not in r.calls[fi]
    assert any(c[0] == "git" and c[1] == "checkout" and f"ci-rebase/pr-{PR}" in c for c in r.calls)
    assert any(c == ["git", "rebase", "origin/main"] for c in r.calls)
    pushes = [c for c in r.calls if c[:2] == ["git", "push"]]
    assert len(pushes) == 1
    assert f"HEAD:refs/heads/{HEAD_REF}" in pushes[0]
    assert f"--force-with-lease=refs/heads/{HEAD_REF}:{SHA_A}" in pushes[0]
    assert any(c[:3] == ["git", "checkout", "-f"] and RESTORE in c for c in r.calls)

def test_lease_rejection_does_not_report_success() -> None:
    r = _runner([_pr_payload(sha=SHA_A)] * 3, {1: [_fe("src/ok.py")]}, push_rc=1)
    code, out = _run(r)
    assert code == 0 and out.startswith(f"SKIP PR #{PR}: push rejected (lease or remote):")
    assert not out.startswith(f"REBASED PR #{PR}:")

@pytest.mark.parametrize("restore_to", ["", "not-a-sha"])
def test_invalid_restore_target_skips_before_mutation(restore_to: str) -> None:
    r = _runner([_pr_payload(sha=SHA_A)] * 2, {1: [_fe("src/ok.py")]}, git=False)
    r.add(lambda a: CmdResult() if a[:3] == ["git", "check-ref-format", "--branch"] else None)
    code, out = _run(r, restore_to=restore_to)
    assert code == 0 and out == f"SKIP PR #{PR}: restore target missing or not a 40-char hex SHA"
    assert not any(c[:2] == ["git", "fetch"] for c in r.calls)

def test_restore_checkout_failure_after_push_is_error_not_rebased() -> None:
    r = _runner([_pr_payload(sha=SHA_A)] * 3, {1: [_fe("src/ok.py")]}, restore_rc=1)
    code, out = _run(r)
    assert code == 1 and out.startswith(f"ERROR PR #{PR}:")
    assert not out.startswith(f"REBASED PR #{PR}:")
    assert any(c[:2] == ["git", "push"] for c in r.calls)
    r2 = _runner([_pr_payload()] * 2, {1: [_fe("src/ok.py")]}, checkout_rc=1)
    c2, o2 = _run(r2)
    assert c2 == 0 and o2.startswith(f"SKIP PR #{PR}: checkout failed:")
    assert not any(c[:2] == ["git", "push"] for c in r2.calls)

def test_rebase_abort_failure_surfaces_local_error() -> None:
    r = _runner([_pr_payload(sha=SHA_A)] * 2, {1: [_fe("src/ok.py")]}, rebase_rc=1, abort_rc=1)
    code, out = _run(r)
    assert code == 1 and "rebase conflict and abort failed" in out
    assert any(c[:3] == ["git", "rebase", "--abort"] for c in r.calls)
    assert not any(c[:2] == ["git", "push"] for c in r.calls)

def test_guard_completes_before_every_pr_head_mutation() -> None:
    r = _runner([_pr_payload(sha=SHA_A)] * 3, {1: [_fe("src/ok.py")]})
    _run(r)
    def is_mut(a: list[str]) -> bool:
        return bool(a and a[0] == "git" and a[1] not in {"check-ref-format", "rev-parse"}
                    and a[1] in MUTATION)
    first = next(i for i, c in enumerate(r.calls) if is_mut(c))
    prefix = r.calls[:first]
    assert any(_is_meta(c) for c in prefix)
    assert any(len(c) >= 3 and "files?" in c[2] for c in prefix)
    assert sum(1 for c in prefix if _is_meta(c)) >= 2

def test_packet_prefix_constant_used_for_detection() -> None:
    mod = _load_helper()
    assert mod.PACKET_PREFIX == "reports/agentops/work_packets/"
    assert mod.is_protected_path(PACKET)
    assert not mod.is_protected_path("reports/agentops/unprotected/example.json")
    assert not mod.is_protected_path("reports/agentops/work_packets/example.txt")
    assert mod.packet_guard_selftest() == 0

def test_scripted_runner_rejects_unexpected_commands() -> None:
    with pytest.raises(AssertionError, match="unexpected command"):
        ScriptedRunner()(["git", "status"])
