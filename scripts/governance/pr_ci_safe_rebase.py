#!/usr/bin/env python3
"""Fail-closed same-repo PR rebase for pr-ci-health.

Guards Session Entry packet paths and binds same-repo head identity with an
explicit force-with-lease before any PR-head rewrite. Stdlib only.

Workflow contract: main fetch/config may precede this helper; PR-head
fetch/checkout/rebase/push must not. This helper never merges a PR.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable, Sequence

PACKET_PREFIX = "reports/agentops/work_packets/"
WORKFLOW_PREFIX = ".github/workflows/"
MAX_ENUMERABLE_CHANGED_FILES = 3000
FILES_PER_PAGE = 100
EXPECTED_BASE = "main"
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")

Runner = Callable[[list[str]], "CmdResult"]


@dataclass(frozen=True)
class CmdResult:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class PRIdentity:
    base_ref: str
    head_ref: str
    head_sha: str
    head_repo: str
    changed_files: int


class Skip(Exception):
    """Safe skip: exit 0 with SKIP message."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class LocalError(Exception):
    """Unexpected local error: may exit nonzero; never push after incomplete proof."""


def is_protected_path(path: str) -> bool:
    return path.startswith(PACKET_PREFIX) and path.endswith(".json")


def is_workflow_path(path: str) -> bool:
    return path.startswith(WORKFLOW_PREFIX)


def default_runner(argv: list[str]) -> CmdResult:
    proc = subprocess.run(  # noqa: S603 — argv list only, never shell=True
        argv,
        check=False,
        capture_output=True,
        text=True,
    )
    return CmdResult(
        returncode=int(proc.returncode),
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def _run(runner: Runner, argv: list[str]) -> CmdResult:
    if not argv or not all(isinstance(a, str) for a in argv):
        raise LocalError("invalid argv")
    return runner(list(argv))


def _parse_json(text: str, *, what: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise Skip(f"malformed JSON for {what}: {exc}") from exc


def _fetch_pr_metadata(runner: Runner, repo: str, pr: int) -> dict[str, Any]:
    result = _run(runner, ["gh", "api", f"repos/{repo}/pulls/{pr}"])
    if result.returncode != 0:
        raise Skip(f"PR metadata API failed: {result.stderr.strip() or result.returncode}")
    payload = _parse_json(result.stdout, what="PR metadata")
    if not isinstance(payload, dict):
        raise Skip("PR metadata is not a JSON object")
    return payload


def _require_identity(
    payload: dict[str, Any],
    *,
    repo: str,
    expected_base: str,
    expected_head: str,
) -> PRIdentity:
    if expected_base != EXPECTED_BASE:
        raise Skip(f"expected-base must be {EXPECTED_BASE!r}")

    base = payload.get("base")
    head = payload.get("head")
    if not isinstance(base, dict) or not isinstance(head, dict):
        raise Skip("PR metadata missing base/head objects")

    base_ref = base.get("ref")
    if not isinstance(base_ref, str) or base_ref != expected_base or base_ref != EXPECTED_BASE:
        raise Skip(f"base ref is not {EXPECTED_BASE}")

    head_ref = head.get("ref")
    if not isinstance(head_ref, str) or head_ref != expected_head:
        raise Skip("head ref does not match expected-head")

    head_sha = head.get("sha")
    if not isinstance(head_sha, str) or not _SHA_RE.fullmatch(head_sha):
        raise Skip("head.sha is not a 40-char hex SHA")

    head_repo_obj = head.get("repo")
    if not isinstance(head_repo_obj, dict):
        raise Skip("fork or missing head.repo; same-repo only")
    full_name = head_repo_obj.get("full_name")
    if not isinstance(full_name, str):
        raise Skip("fork or missing head.repo.full_name; same-repo only")
    if full_name.casefold() != repo.casefold():
        raise Skip("fork PR head repo differs from target; same-repo only")

    changed = payload.get("changed_files")
    if not isinstance(changed, int) or isinstance(changed, bool) or changed < 0:
        raise Skip("changed_files is not a non-negative integer")
    # GitHub files endpoint hard-caps at 3000; equality is not provably complete.
    if changed >= MAX_ENUMERABLE_CHANGED_FILES:
        raise Skip(
            f"changed_files {changed} at or above enumerable cap "
            f"{MAX_ENUMERABLE_CHANGED_FILES}"
        )

    return PRIdentity(
        base_ref=base_ref,
        head_ref=head_ref,
        head_sha=head_sha,
        head_repo=full_name,
        changed_files=changed,
    )


def _same_identity(a: PRIdentity, b: PRIdentity) -> bool:
    return (
        a.base_ref == b.base_ref
        and a.head_ref == b.head_ref
        and a.head_sha == b.head_sha
        and a.head_repo.casefold() == b.head_repo.casefold()
        and a.changed_files == b.changed_files
    )


def _fetch_files_page(
    runner: Runner, repo: str, pr: int, page: int
) -> list[Any]:
    path = f"repos/{repo}/pulls/{pr}/files?per_page={FILES_PER_PAGE}&page={page}"
    result = _run(runner, ["gh", "api", path])
    if result.returncode != 0:
        raise Skip(
            f"files page {page} API failed: "
            f"{result.stderr.strip() or result.returncode}"
        )
    payload = _parse_json(result.stdout, what=f"files page {page}")
    if not isinstance(payload, list):
        raise Skip(f"files page {page} is not a JSON array")
    if len(payload) > FILES_PER_PAGE:
        raise Skip(f"files page {page} exceeds per_page={FILES_PER_PAGE}")
    return payload


def _require_empty_sentinel(
    runner: Runner, repo: str, pr: int, page: int
) -> None:
    """Fetch one sentinel page and require a valid empty JSON array."""
    payload = _fetch_files_page(runner, repo, pr, page)
    if payload:
        raise Skip(f"nonempty sentinel files page {page}")


def _enumerate_changed_files(
    runner: Runner, repo: str, pr: int, changed_files: int
) -> list[dict[str, Any]]:
    # Metadata zero: page 1 is the termination sentinel.
    if changed_files == 0:
        _require_empty_sentinel(runner, repo, pr, 1)
        return []

    collected: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    pages_needed = (changed_files + FILES_PER_PAGE - 1) // FILES_PER_PAGE

    for page in range(1, pages_needed + 1):
        payload = _fetch_files_page(runner, repo, pr, page)
        if not payload:
            raise Skip(f"premature empty files page {page}")

        if page < pages_needed and len(payload) != FILES_PER_PAGE:
            raise Skip(f"partial non-final files page {page}")

        for entry in payload:
            if not isinstance(entry, dict):
                raise Skip(f"files page {page} entry is not an object")
            filename = entry.get("filename")
            if not isinstance(filename, str):
                raise Skip(f"files page {page} entry missing string filename")
            if "previous_filename" in entry:
                prev = entry.get("previous_filename")
                if not isinstance(prev, str):
                    raise Skip(
                        f"files page {page} previous_filename is not a string"
                    )
            if filename in seen_names:
                raise Skip(f"duplicate filename in files enumeration: {filename!r}")
            seen_names.add(filename)
            collected.append(entry)

    if len(collected) != changed_files:
        raise Skip(
            f"changed_files count mismatch: metadata={changed_files} "
            f"enumerated={len(collected)}"
        )

    # Full final page is ambiguous without a next empty sentinel page.
    if changed_files % FILES_PER_PAGE == 0:
        _require_empty_sentinel(runner, repo, pr, pages_needed + 1)

    return collected


def _protected_paths(entries: Sequence[dict[str, Any]]) -> list[str]:
    hits: list[str] = []
    for entry in entries:
        filename = entry.get("filename")
        if isinstance(filename, str) and is_protected_path(filename):
            hits.append(filename)
        prev = entry.get("previous_filename")
        if isinstance(prev, str) and is_protected_path(prev):
            hits.append(prev)
    return hits


def _workflow_paths(entries: Sequence[dict[str, Any]]) -> list[str]:
    hits: list[str] = []
    for entry in entries:
        filename = entry.get("filename")
        if isinstance(filename, str) and is_workflow_path(filename):
            hits.append(filename)
        prev = entry.get("previous_filename")
        if isinstance(prev, str) and is_workflow_path(prev):
            hits.append(prev)
    return hits


def _validate_branch_name(runner: Runner, head_ref: str) -> None:
    result = _run(runner, ["git", "check-ref-format", "--branch", head_ref])
    if result.returncode != 0:
        raise Skip(f"head ref failed check-ref-format: {head_ref!r}")


def _resolve_restore_target(restore_to: str | None) -> str:
    """Require a valid 40-hex restore SHA before any PR-head mutation."""
    candidate = restore_to
    if candidate is None:
        candidate = os.environ.get("GITHUB_SHA") or ""
    if not isinstance(candidate, str) or not _SHA_RE.fullmatch(candidate):
        raise Skip("restore target missing or not a 40-char hex SHA")
    return candidate


def _restore_checkout(runner: Runner, restore_to: str) -> None:
    """Checkout restore target; inspect return code (never silently ignore)."""
    result = _run(runner, ["git", "checkout", "-f", restore_to])
    if result.returncode != 0:
        raise LocalError(
            f"restore checkout failed: {result.stderr.strip() or result.returncode}"
        )


def safe_rebase(
    *,
    repo: str,
    pr: int,
    expected_base: str,
    expected_head: str,
    runner: Runner | None = None,
    restore_to: str | None = None,
) -> tuple[int, str]:
    """Run fail-closed guard + rebase. Returns (exit_code, message)."""
    run = runner or default_runner

    message = ""
    exit_code = 0
    did_checkout = False
    restore_sha: str | None = None

    try:
        if not isinstance(pr, int) or isinstance(pr, bool) or pr <= 0:
            raise Skip("PR number must be a positive integer")
        if not isinstance(repo, str) or "/" not in repo:
            raise Skip("repo must look like owner/name")

        # --- metadata + identity (before file inspection) ---
        meta = _fetch_pr_metadata(run, repo, pr)
        identity = _require_identity(
            meta,
            repo=repo,
            expected_base=expected_base,
            expected_head=expected_head,
        )

        # --- complete changed-file enumeration ---
        entries = _enumerate_changed_files(run, repo, pr, identity.changed_files)
        protected = _protected_paths(entries)
        if protected:
            raise Skip(
                "changes a Session Entry packet under "
                f"{PACKET_PREFIX}*.json ({len(protected)} path(s))"
            )
        workflows = _workflow_paths(entries)
        if workflows:
            raise Skip(
                "changes a GitHub Actions workflow under "
                f"{WORKFLOW_PREFIX} ({len(workflows)} path(s)); "
                "workflow-write authority is not proven"
            )

        # --- race re-read before any PR-head git mutation ---
        meta2 = _fetch_pr_metadata(run, repo, pr)
        identity2 = _require_identity(
            meta2,
            repo=repo,
            expected_base=expected_base,
            expected_head=expected_head,
        )
        if not _same_identity(identity, identity2):
            raise Skip("PR head/base/files race after file enumeration")

        _validate_branch_name(run, identity.head_ref)

        # Require restore target before fetch/checkout/rebase/push.
        restore_sha = _resolve_restore_target(restore_to)

        # --- bind PR head by trusted PR number ref ---
        local_pr_ref = f"refs/pr-ci-health/{pr}"
        fetch_map = f"refs/pull/{pr}/head:{local_pr_ref}"
        fetch = _run(run, ["git", "fetch", "origin", fetch_map])
        if fetch.returncode != 0:
            raise Skip(f"fetch PR head ref failed: {fetch.stderr.strip() or fetch.returncode}")

        rev = _run(run, ["git", "rev-parse", local_pr_ref])
        if rev.returncode != 0:
            raise Skip("rev-parse of fetched PR ref failed")
        fetched_sha = (rev.stdout or "").strip()
        if fetched_sha.casefold() != identity.head_sha.casefold():
            raise Skip("fetched PR ref SHA does not match inspected head.sha")

        local_branch = f"ci-rebase/pr-{pr}"
        did_checkout = True  # checkout may partially mutate even when it returns nonzero
        checkout = _run(
            run,
            ["git", "checkout", "-B", local_branch, local_pr_ref],
        )
        if checkout.returncode != 0:
            raise Skip(f"checkout failed: {checkout.stderr.strip() or checkout.returncode}")

        rebase = _run(run, ["git", "rebase", "origin/main"])
        if rebase.returncode != 0:
            # Abort only on actual rebase failure; inspect abort RC.
            abort = _run(run, ["git", "rebase", "--abort"])
            if abort.returncode != 0:
                raise LocalError(
                    "rebase conflict and abort failed: "
                    f"{abort.stderr.strip() or abort.returncode}"
                )
            raise Skip("rebase conflict; aborted")

        # --- re-read identity immediately before push ---
        meta3 = _fetch_pr_metadata(run, repo, pr)
        identity3 = _require_identity(
            meta3,
            repo=repo,
            expected_base=expected_base,
            expected_head=expected_head,
        )
        if not _same_identity(identity, identity3):
            raise Skip("PR head moved before push; not rewriting")

        head_ref = identity.head_ref
        lease = f"--force-with-lease=refs/heads/{head_ref}:{identity.head_sha}"
        push_refspec = f"HEAD:refs/heads/{head_ref}"
        push = _run(
            run,
            ["git", "push", "origin", push_refspec, lease],
        )
        if push.returncode != 0:
            raise Skip(
                f"push rejected (lease or remote): "
                f"{push.stderr.strip() or push.returncode}"
            )

        message = (
            f"REBASED PR #{pr}: {head_ref}@{identity.head_sha[:12]} "
            f"onto origin/main"
        )
        exit_code = 0
    except Skip as exc:
        message = f"SKIP PR #{pr}: {exc.reason}"
        exit_code = 0
    except LocalError as exc:
        message = f"ERROR PR #{pr}: {exc}"
        exit_code = 1
    except Exception as exc:  # noqa: BLE001 — surface unexpected local errors
        message = f"ERROR PR #{pr}: unexpected: {exc}"
        exit_code = 1
    finally:
        # Only restore when this process moved HEAD; never inject git mutation
        # on pure metadata/file-guard skips.
        if did_checkout and restore_sha:
            try:
                _restore_checkout(run, restore_sha)
            except LocalError as restore_exc:
                # Do not retain REBASED success when local restore failed.
                if message.startswith(f"REBASED PR #{pr}:"):
                    message = (
                        f"ERROR PR #{pr}: push completed but local restore "
                        f"failed: {restore_exc}"
                    )
                else:
                    message = f"ERROR PR #{pr}: {restore_exc}"
                exit_code = 1
            except Exception as restore_exc:  # noqa: BLE001
                if message.startswith(f"REBASED PR #{pr}:"):
                    message = (
                        f"ERROR PR #{pr}: push completed but local restore "
                        f"failed: {restore_exc}"
                    )
                else:
                    message = f"ERROR PR #{pr}: unexpected restore: {restore_exc}"
                exit_code = 1

    return exit_code, message


def packet_guard_selftest() -> int:
    """Dependency-free page-two guard proof for AgentOps negative controls."""
    calls: list[list[str]] = []
    meta = {"base": {"ref": "main"}, "head": {"ref": "selftest", "sha": "a" * 40,
            "repo": {"full_name": "self/test"}}, "changed_files": 101}
    page1 = [{"filename": f"src/f{i}.py"} for i in range(100)]
    page2 = [{"filename": "docs/moved.json",
             "previous_filename": "reports/agentops/work_packets/selftest.json"}]

    def runner(argv: list[str]) -> CmdResult:
        calls.append(list(argv))
        target = argv[2] if len(argv) > 2 else ""
        if argv[:2] == ["gh", "api"] and target.endswith("/pulls/1"):
            return CmdResult(stdout=json.dumps(meta))
        if argv[:2] == ["gh", "api"] and "&page=1" in target:
            return CmdResult(stdout=json.dumps(page1))
        if argv[:2] == ["gh", "api"] and "&page=2" in target:
            return CmdResult(stdout=json.dumps(page2))
        return CmdResult(returncode=1, stderr="unexpected selftest command")

    code, message = safe_rebase(
        repo="self/test", pr=1, expected_base="main", expected_head="selftest",
        runner=runner, restore_to="f" * 40,
    )
    passed = code == 0 and "Session Entry packet" in message and not any(
        argv and argv[0] == "git" for argv in calls
    )
    print("packet-guard-selftest: " + ("PASS" if passed else f"FAIL: {message}"))
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    effective_argv = sys.argv[1:] if argv is None else argv
    if effective_argv == ["--selftest-packet-guard"]:
        return packet_guard_selftest()
    parser = argparse.ArgumentParser(
        description="Fail-closed same-repo PR rebase with Session Entry guard",
    )
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--pr", required=True, type=int, help="PR number")
    parser.add_argument("--expected-base", required=True, help="must be main")
    parser.add_argument("--expected-head", required=True, help="head branch name")
    parser.add_argument(
        "--restore-to",
        default=None,
        help="git checkout target after work (default: $GITHUB_SHA)",
    )
    args = parser.parse_args(effective_argv)

    code, message = safe_rebase(
        repo=args.repo,
        pr=args.pr,
        expected_base=args.expected_base,
        expected_head=args.expected_head,
        restore_to=args.restore_to,
    )
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
