#!/usr/bin/env python3
"""Hardening lane, phase 2 of 2: DELIVER (trusted).

Runs as a separate job, on a separate runner, in a checkout the agent has
never touched. It receives one artifact — a `git bundle` written by
`scripts/runtime/lane_propose.py` — verifies it against facts it fetches
itself, then pushes the branch and opens a draft PR.

The trust rule, stated once and enforced throughout
---------------------------------------------------
**Nothing the propose phase says is evidence.** Its receipt is copied into
the PR body as narrative and is otherwise ignored. Every gate below is
re-derived here from (a) the bytes inside the bundle and (b) `origin`:

- branch name          -> from the bundle's own ref, matched against a strict pattern
- base commit          -> `git rev-parse origin/<base>`, fetched by this job
- one commit only      -> `git rev-list --count`
- parent legitimacy    -> `git merge-base --is-ancestor` against origin/<base>
- diff size            -> `git diff --numstat`, recomputed, capped
- touched paths        -> `git diff --name-only`, checked against the referee denylist
- open-draft ceiling   -> `gh pr list`, queried now

What the split buys, precisely
------------------------------
Every residual that made PR #1162 unmergeable was an instance of one fact:
the agent and the delivery step shared a machine. Each is answered here by
construction, not by a guard:

| residual (PR #1162)                          | why it cannot occur here            |
|----------------------------------------------|-------------------------------------|
| descendant races the `.git/config` restore    | descendants died with the other VM  |
| agent overwrites the resolved `git` binary    | this runner's git is a fresh image  |
| `url.<base>.insteadOf` redirects the push     | this `.git/config` never met an agent |
| `credential.helper` executes on push          | same — and `-c` could not fix it     |
| `filter.*.clean` runs during a privileged add | this job never runs `git add`       |
| test process inherits the write token         | tests ran in the other job, tokenless |

This job never runs agent code, never runs the test suite, never checks the
candidate tree out into a working tree, and never stages anything. It moves
objects and pushes a SHA.

Residual risk that remains, honestly
------------------------------------
The agent still authors the CONTENT. A hostile change set can be proposed —
it just cannot be delivered as anything other than a **draft PR**, under the
diff cap, outside the referee paths, with CI and human review ahead of it.
That is the same exposure as any external contributor, which is the correct
level for this lane and the level review exists to handle.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MAX_DIFF_LINES = int(os.environ.get("LANE_MAX_DIFF_LINES", "600"))
MAX_CHANGED_FILES = int(os.environ.get("LANE_MAX_CHANGED_FILES", "40"))
MAX_BUNDLE_BYTES = int(os.environ.get("LANE_MAX_BUNDLE_BYTES", str(8 * 1024 * 1024)))
# Uncompressed ceiling for the blobs the candidate touches. MAX_BUNDLE_BYTES
# measures COMPRESSED bytes and so does not bound this: compressible padding
# passes the bundle cap and unpacks large on the delivery runner.
MAX_CHANGED_BLOB_BYTES = int(
    os.environ.get("LANE_MAX_CHANGED_BLOB_BYTES", str(4 * 1024 * 1024)))
MAX_OPEN_LANE_DRAFTS = int(os.environ.get("LANE_MAX_OPEN_DRAFTS", "1"))

# Shell convention, and the same values lane_propose uses: a missing binary and
# a command that outran its budget must be distinguishable in the receipt.
EXIT_NOT_FOUND = 127
EXIT_TIMEOUT = 124
LANE_BRANCH_PREFIX = "lane/hardening-"
LANE_LABELS = ("mike-watch", "walk-ready", "lane-output")

# The bundle's ref must look exactly like a lane branch this repo minted.
# Anchored, so no path traversal, no ref-name trickery, no second segment.
BRANCH_RE = re.compile(r"^lane/hardening-\d{8}T\d{6}Z$")
BUNDLE_HEAD_RE = re.compile(r"^([0-9a-f]{40})\s+refs/heads/(\S+)$")

# Referee / Tier-2 surfaces. A lane change touching any of these is refused
# outright: the lane may not edit the machinery that judges the lane. This is
# the delivery-side copy — propose has its own author-side exclusions, and
# neither is trusted to be the other's enforcement.
DENY_PREFIXES = (
    ".github/workflows/",
    ".github/actions/",
    "scripts/runtime/pr_merge_control.py",
    "scripts/runtime/merge_master_mike_daemon.py",
    "scripts/runtime/lane_propose.py",
    "scripts/runtime/lane_deliver.py",
    "scripts/governance/check_automerge_tier_policy.py",
    "scripts/governance/loop_watcher.py",
    "docs/ops/loop_control/",
    "docs/governance/CI_TRUTH_CONTRACT.json",
    "scripts/governance/ci_parity_manifest.json",
    "reports/",
    "roaming_mailbox/",
    ".git/",
)
DENY_SUFFIXES = (".env", ".pem", ".key")
DENY_NAMES = {".env", "secrets.json", "CODEOWNERS"}

GIT_BIN = shutil.which("git") or "git"
GH_BIN = shutil.which("gh") or "gh"

CANDIDATE_REF = "refs/lane/candidate"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _run(cmd: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess:
    # `errors="surrogateescape"` is load-bearing, not style. Git filenames are
    # bytes, not UTF-8: a candidate containing a legal name like `bad-\xff.txt`
    # made plain text=True raise UnicodeDecodeError INSIDE this helper, which
    # escaped before refuse() could write a receipt — an untrusted candidate
    # crashing the trusted delivery job instead of being deterministically
    # rejected (Codex on #1200; reproduced against real git). surrogateescape
    # round-trips those bytes so the denylist sees the real path.
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              errors="surrogateescape",
                              timeout=timeout, check=False)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(cmd, EXIT_NOT_FOUND, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        # A hung command is a failed command with a receipt, not a crashed
        # delivery. This helper carried only the FileNotFoundError arm while
        # its sibling lane_propose._run grew a TimeoutExpired arm in this same
        # PR — the identical defect, left in the job that can do damage.
        # Every gate in main() runs through here: bundle fetch, origin fetch,
        # push, `gh pr list`, `gh pr create`. An escape past this point skips
        # refuse()/receipt() and the step reports NO_RECEIPT_WRITTEN.
        #
        # The `gh pr create` call is the one that matters. It runs AFTER the
        # push, so an escape there skips the orphan-branch rollback below and
        # strands exactly the `lane/hardening-*` branch that block exists to
        # remove — the failure mode this PR set out to close, reintroduced
        # through the timeout path. (Devin on #1200.)
        captured = exc.stdout or b"" if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        if isinstance(captured, bytes):
            captured = captured.decode("utf-8", "surrogateescape")
        return subprocess.CompletedProcess(cmd, EXIT_TIMEOUT, captured,
                                           f"timed out after {timeout}s")


def _git(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    # `-c` hardening here is belt-and-braces, not the boundary: this
    # checkout's config was written by actions/checkout on a clean runner and
    # no agent has ever run in this process tree. It is kept so that the
    # command set stays safe if this module is ever reused somewhere less
    # pristine — and it is honest about not being what makes the lane safe.
    flags = ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
             "-c", "diff.external=", "-c", "core.pager=cat"]
    return _run([GIT_BIN, *flags, *args], **kwargs)


def rollback_branch(branch: str, head_sha: str) -> str:
    """Delete our own pushed branch, and only ever our own.

    The open-draft ceiling counts PRs, not branches, so a pushed branch with
    no PR is an orphan every scheduled retry adds to and nothing cleans up.

    The lease is part of the delete, not a check before it. Reading the SHA
    with `ls-remote` and then deleting unconditionally is a TOCTOU: a writer
    that updates the branch between the two operations gets their commit
    deleted instead of our orphan. Greptile proved exactly that against the
    first version of this block (#1200).

    `--force-with-lease=<ref>:<sha>` with a delete refspec binds the two
    together atomically. Verified against git 2.43: a stale expectation is
    rejected with "(delete) ... stale info" and the branch survives; a
    matching expectation deletes.
    """
    deleted = _git(["push",
                    f"--force-with-lease=refs/heads/{branch}:{head_sha}",
                    "origin", f":refs/heads/{branch}"])
    if deleted.returncode == 0:
        return "deleted under lease"
    if "stale info" in (deleted.stderr + deleted.stdout):
        # Covers both "the branch moved" and "the branch was never there":
        # git reports a lease mismatch identically for a ref at another SHA
        # and a ref that does not exist. Either way we did not touch it.
        return ("kept: origin is not at our SHA (moved, or the push never "
                "landed); the lease refused the delete")
    return f"delete failed: {deleted.stderr[-200:]}"


def receipt(payload: dict, out: Path) -> None:
    payload.setdefault("schema", "dharma.lane_deliver_receipt.v1")
    payload.setdefault("generated_at", _utc_stamp())
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


def bundle_heads(bundle: Path) -> list[tuple[str, str]] | None:
    """(sha, branch) for every head the bundle carries, or None if unreadable."""
    listed = _git(["bundle", "list-heads", str(bundle)])
    if listed.returncode != 0:
        return None
    heads: list[tuple[str, str]] = []
    for line in listed.stdout.splitlines():
        match = BUNDLE_HEAD_RE.match(line.strip())
        if match:
            heads.append((match.group(1), match.group(2)))
        elif line.strip():
            # A ref that is not a plain branch (a tag, a note, a raw sha) is
            # not something this lane delivers. Surface it as unparseable
            # rather than silently ignoring the extra ref.
            return None
    return heads


def denied_paths(paths: list[str]) -> list[str]:
    bad = []
    for path in paths:
        name = Path(path).name
        if (path.startswith(DENY_PREFIXES) or path.endswith(DENY_SUFFIXES)
                or name in DENY_NAMES):
            bad.append(path)
    return sorted(bad)


def numstat_lines(base: str, head: str) -> int | None:
    """Changed lines, counting a rename as the delete plus the add it is.

    `--no-renames` is load-bearing and must match `changed_paths()`. With
    git's default rename detection a pure relocation is ONE record reading
    `0\t0\told => new`, which sums to zero and sails under MAX_DIFF_LINES.
    Measured on git 2.43 against an 800-line file:

        git diff --numstat              ->  0  0  big.py => moved.py     (0)
        git diff --no-renames --numstat ->  0  800 big.py
                                            800 0   moved.py            (1600)

    Without it the two gates disagreed about the same commit — `changed_paths`
    counted two files while this counted zero lines — so a candidate could
    relocate thousands of lines and be delivered as if it changed nothing.
    The blob ceiling only bounds that at 4 MiB, far above the ~600-line
    intent of the cap. (Devin on #1200.)
    """
    result = _git(["diff", "--no-renames", "--numstat", f"{base}..{head}"])
    if result.returncode != 0:
        # None, not 0. `_run` synthesizes empty stdout for a missing binary
        # (127) and a timeout (124), so an unreadable measurement summed to
        # zero and `lines > MAX_DIFF_LINES` could never fire — a change of any
        # size admitted because the ruler broke. The same fail-open closed for
        # `entries()` and for the propose-side status listing; this was the
        # remaining measurement gate that admitted on unreadable input.
        # (Devin on #1200.)
        return None
    total = 0
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            for cell in parts[:2]:
                if cell.isdigit():
                    total += int(cell)
    return total


def changed_paths(base: str, head: str) -> list[str]:
    """Every path the candidate touches, in machine-readable form.

    Two flags here are load-bearing, and both were proven necessary by
    executable review proofs against the first version of this file:

    ``-z``  — without it `git diff --name-only` emits git's HUMAN format,
              which C-quotes any path with non-ASCII or special bytes:
              `.github/workflows/é.yml` came back as
              `".github/workflows/\\303\\251.yml"`, whose leading quote meant
              it no longer matched the `.github/workflows/` deny prefix and
              `denied_paths()` returned []. NUL-delimited output is verbatim.

    ``--no-renames`` — with rename detection on, a rename reports ONLY the
              destination. Renaming `scripts/runtime/pr_merge_control.py` to
              `dharma_swarm/harmless.py` showed just the harmless destination
              while effectively deleting the referee gate. Disabling rename
              detection makes git report the delete and the add separately,
              so both sides face the denylist.
    """
    result = _git(["diff", "--no-renames", "--name-only", "-z",
                   f"{base}..{head}"])
    return [part for part in result.stdout.split("\0") if part]


def changed_blob_bytes(base: str, head: str) -> int | None:
    """Total uncompressed size of the blobs this candidate adds or modifies.

    `git diff --numstat` reports `-` for both cells on binary files, so a
    binary contributes ZERO toward the line cap. The bundle size ceiling does
    not close that either: it measures COMPRESSED bytes, so highly
    compressible data slips under it while unpacking to something far larger.
    This measures the real thing.

    What "larger" means here is OBJECT-STORE bytes, not worktree bytes. The
    delivery job never checks the candidate out (see
    test_delivery_never_stages_or_checks_out_the_candidate); `git fetch` of
    the bundle unpacks objects and stops there. An earlier draft of this
    docstring said "unpacking to something far larger on the delivery runner",
    which reads as materialized files and would argue for charging each path
    — a materialization that never happens. Stated correctly so the rationale
    matches what the code measures.

    Only blobs the base does not already have are charged. `changed_paths()`
    runs `--no-renames`, so a relocation arrives as delete(old) + add(new) —
    and the "new" blob is byte-identical to one already in the base tree, so
    charging it billed a candidate for content it did not ship. Measured on a
    4096-byte file: a pure rename charged 4096. (Greptile on #1200.)

    Comparing base and candidate blobs PER PATH — the fix as prescribed —
    does not close it: the destination is a new path with no base blob, so it
    still charges 4096. Membership in the base tree's blob-OID SET is the
    question, and it answers 0. Verified against git 2.43.

    Unique OIDs, because the object store gains a blob once no matter how
    many paths point at it; MAX_CHANGED_FILES bounds the path count
    separately.

    This one is a FALSE REFUSAL rather than a hole — it made the cap stricter
    than its own docstring claimed, never looser.
    """
    def entries(ref: str) -> dict[str, tuple[str, int]] | None:
        # None, not {}, when the listing could not be read. An unreadable
        # head listing used to be indistinguishable from "the candidate
        # contains nothing": the loop charged nothing, the function returned
        # 0, and `blob_bytes > MAX_CHANGED_BLOB_BYTES` could never fire —
        # fail-OPEN on the only ceiling that bounds binary content, which
        # already scores zero against the line cap. `_run` returns empty
        # stdout for both a missing binary (127) and a timeout (124), so this
        # was reachable without any attack. The asymmetry made it worse: a
        # failed `base` listing fails closed (empty OID set charges
        # everything) while a failed `head` listing failed open.
        # (Devin on #1200.)
        listing = _git(["ls-tree", "-r", "-z", "--long", ref])
        if listing.returncode != 0:
            return None
        out: dict[str, tuple[str, int]] = {}
        for entry in listing.stdout.split("\0"):
            if not entry:
                continue
            meta, _, path = entry.partition("\t")
            fields = meta.split()
            if len(fields) >= 4 and fields[3].isdigit():
                out[path] = (fields[2], int(fields[3]))
        return out

    head_entries = entries(head)
    base_entries = entries(base)
    if head_entries is None or base_entries is None:
        return None
    base_oids = {oid for oid, _ in base_entries.values()}

    charged: dict[str, int] = {}
    for path in changed_paths(base, head):
        found = head_entries.get(path)
        if found and found[0] not in base_oids:
            charged[found[0]] = found[1]
    return sum(charged.values())


def open_lane_drafts(repo: str) -> list[int] | None:
    result = _run([
        GH_BIN, "pr", "list", "--repo", repo, "--state", "open",
        "--label", "lane-output", "--json", "number,isDraft,headRefName",
        "--limit", "50",
    ])
    if result.returncode != 0:
        return None
    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(rows, list):
        return None
    return [
        int(row["number"]) for row in rows
        if row.get("isDraft") and str(row.get("headRefName", "")).startswith(
            LANE_BRANCH_PREFIX
        )
    ]


def commit_subject(sha: str) -> str:
    result = _git(["log", "-1", "--format=%s", sha])
    collapsed = re.sub(r"\s+", " ", result.stdout).strip()
    printable = "".join(ch for ch in collapsed if ch.isprintable())
    return printable[:72] or "hardening lane output"


def load_propose_receipt(path: Path | None) -> dict:
    """The other phase's receipt, for narration only. Never a gate input."""
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hardening lane — deliver")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--propose-receipt", default=None,
                        help="untrusted receipt from phase 1 (narrative only)")
    parser.add_argument("--base", default="main")
    parser.add_argument("--dry-run", action="store_true",
                        help="verify everything, push nothing")
    args = parser.parse_args(argv)
    out = Path(args.receipt)

    def refuse(reason: str, **extra) -> int:
        receipt({"status": "REFUSED", "reason": reason, **extra}, out)
        return 1

    bundle = Path(args.bundle)
    if not bundle.is_file():
        return refuse("no delivery bundle was produced")
    size = bundle.stat().st_size
    if size > MAX_BUNDLE_BYTES:
        return refuse("delivery bundle exceeds the size ceiling",
                      bytes=size, limit=MAX_BUNDLE_BYTES)

    # `bundle verify` also proves the prerequisite commits exist locally,
    # which is why this job checks out with full history.
    verified = _git(["bundle", "verify", str(bundle)])
    if verified.returncode != 0:
        return refuse("git bundle verify failed",
                      stderr=verified.stderr[-1000:])

    heads = bundle_heads(bundle)
    if heads is None:
        return refuse("bundle head list was unreadable or carried a "
                      "non-branch ref")
    if len(heads) != 1:
        return refuse("bundle must carry exactly one branch",
                      heads=[name for _, name in heads])
    claimed_sha, branch = heads[0]
    if not BRANCH_RE.match(branch):
        return refuse("bundle branch name is not a lane branch",
                      branch=branch)

    fetched = _git(["fetch", str(bundle),
                    f"refs/heads/{branch}:{CANDIDATE_REF}"])
    if fetched.returncode != 0:
        return refuse("could not fetch the candidate commit out of the bundle",
                      stderr=fetched.stderr[-1000:])
    head_sha = _git(["rev-parse", CANDIDATE_REF]).stdout.strip()
    if not head_sha or head_sha != claimed_sha:
        return refuse("candidate ref did not resolve to the bundled sha",
                      listed=claimed_sha, resolved=head_sha)

    # Base is fetched by THIS job. The propose phase's claim about its base
    # is not consulted.
    _git(["fetch", "origin", args.base])
    base_sha = _git(["rev-parse", "FETCH_HEAD"]).stdout.strip()
    if not base_sha:
        return refuse(f"could not resolve origin/{args.base}")

    count = _git(["rev-list", "--count", f"{base_sha}..{head_sha}"]).stdout.strip()
    if count != "1":
        return refuse("lane delivery must be exactly one commit",
                      commits=count, base=base_sha, head=head_sha)

    parent = _git(["rev-parse", f"{head_sha}^"]).stdout.strip()
    if not parent:
        return refuse("candidate commit has no parent")
    # Redundant backstop, stated as such: given the one-commit rule above,
    # nothing but `head` itself is absent from base, which already implies
    # `head^` is reachable from base. This check therefore cannot fire on its
    # own today. It is kept because it becomes load-bearing the moment the
    # one-commit rule is relaxed, and it costs one process.
    ancestry = _git(["merge-base", "--is-ancestor", parent, base_sha])
    if ancestry.returncode != 0:
        return refuse("candidate's parent is not an ancestor of "
                      f"origin/{args.base} — refusing to deliver a commit "
                      "built on unknown history",
                      parent=parent, base=base_sha)

    paths = changed_paths(parent, head_sha)
    if not paths:
        return refuse("candidate commit changes nothing")
    if len(paths) > MAX_CHANGED_FILES:
        return refuse("candidate touches too many files",
                      files=len(paths), limit=MAX_CHANGED_FILES)
    forbidden = denied_paths(paths)
    if forbidden:
        return refuse("candidate touches referee or excluded paths — the lane "
                      "may not edit the machinery that judges the lane",
                      paths=forbidden)

    lines = numstat_lines(parent, head_sha)
    if lines is None:
        return refuse("could not measure the candidate's changed lines")
    if lines > MAX_DIFF_LINES:
        return refuse("candidate exceeds the diff cap as measured here",
                      observed=lines, limit=MAX_DIFF_LINES)

    # Binary content is invisible to the line cap (numstat prints `-`), so it
    # gets its own ceiling measured in uncompressed bytes.
    blob_bytes = changed_blob_bytes(parent, head_sha)
    if blob_bytes is None:
        # Matches how an unreadable draft ceiling is handled below: a gate
        # that cannot read its input refuses rather than admitting.
        return refuse("could not measure the candidate's changed blob bytes")
    if blob_bytes > MAX_CHANGED_BLOB_BYTES:
        return refuse("candidate's changed blobs exceed the byte ceiling — "
                      "binary content does not register against the line cap",
                      bytes=blob_bytes, limit=MAX_CHANGED_BLOB_BYTES)

    # Authoritative ceiling: propose checked this early to avoid wasting an
    # agent run, but only the value read at delivery time governs.
    open_drafts = open_lane_drafts(args.repo)
    if open_drafts is None:
        return refuse("could not enumerate open lane drafts at delivery time")
    if len(open_drafts) >= MAX_OPEN_LANE_DRAFTS:
        receipt({"status": "CAP_HIT", "cap": "open_lane_drafts",
                 "observed": len(open_drafts), "limit": MAX_OPEN_LANE_DRAFTS,
                 "open": open_drafts, "branch": branch}, out)
        return 0

    verified_facts = {
        "branch": branch, "commit": head_sha, "parent": parent,
        "base": base_sha, "diff_lines": lines, "changed_files": len(paths),
        "paths": paths[:50], "bundle_bytes": size,
    }

    if args.dry_run:
        receipt({"status": "VERIFIED_DRY_RUN", **verified_facts}, out)
        return 0

    push = _git(["push", "origin", f"{head_sha}:refs/heads/{branch}"])
    if push.returncode != 0:
        # A failed push is AMBIGUOUS: the ref may have landed before the
        # client lost the response. Reporting PUSH_FAILED and walking away
        # strands exactly the orphan the rollback exists to remove — and an
        # orphan `lane/hardening-*` is invisible to the open-draft ceiling,
        # which counts PRs, so every retry accumulates another.
        #
        # This probe was gated on EXIT_TIMEOUT while the comment above it
        # said "ask origin rather than trusting the exit code" — the same
        # too-narrow gating already fixed for `gh pr create` in this file,
        # left in place two blocks away. A timeout is not the only failure
        # that can follow a server-side ref update; a connection reset after
        # the remote accepts does it too. So: probe on every non-zero.
        # (Greptile on #1200, matching Devin's finding on the create side.)
        #
        # The one exit needing no probe is a missing `git` binary: no process
        # ran, so nothing can have landed, and the probe would need the same
        # missing binary to answer.
        #
        # An UNANSWERABLE probe means attempt the rollback anyway, because the
        # lease — not the probe — is what makes the delete safe. Measured
        # against git 2.43, `--force-with-lease=<ref>:<sha>` on a delete
        # refspec in all three remote states:
        #
        #   ref absent          -> "! [rejected] (stale info)"  harmless no-op
        #   ref at OUR sha      -> "- [deleted]"                orphan cleaned
        #   ref at another sha  -> "! [rejected] (stale info)"  writer safe
        #
        # So a failed probe leaving `landed` empty and recording "nothing to
        # roll back" was strictly worse than trying: it stranded an orphan the
        # open-draft ceiling cannot see, and every retry adds another.
        # (Greptile on #1200, with an executed harness.)
        #
        # This does NOT contradict the `gh pr create` path above, which
        # refuses to delete when it cannot tell. The asymmetry is real: there,
        # a delete can CLOSE AN EXISTING PR, which is unrecoverable. Here no
        # PR exists yet, and the lease guarantees the delete can only ever
        # remove our own orphan.
        if push.returncode == EXIT_NOT_FOUND:
            rollback = "nothing to roll back: git never ran"
        else:
            probe = _git(["ls-remote", "origin", f"refs/heads/{branch}"])
            if probe.returncode != 0:
                rollback = ("probe unanswerable; attempted under lease: "
                            + rollback_branch(branch, head_sha))
            elif not probe.stdout.split():
                rollback = "nothing to roll back: origin has no such ref"
            elif probe.stdout.split()[0] == head_sha:
                rollback = rollback_branch(branch, head_sha)
            else:
                rollback = "kept: origin holds a different SHA on this branch"

        receipt({"status": "PUSH_FAILED", **verified_facts,
                 "stderr": push.stderr[-1000:],
                 "branch_rollback": rollback}, out)
        return 1

    proposed = load_propose_receipt(
        Path(args.propose_receipt) if args.propose_receipt else None)
    target = proposed.get("target", {})
    # The consumption claim gets its OWN untruncated line, and is emitted
    # before the human-readable summary that may be cut.
    #
    # It used to be recoverable only from the truncated `Target:` blob below,
    # which made the anti-starvation mechanism depend on JSON key ordering:
    # `receipt()` writes with sort_keys=True, so the target round-trips as
    # body, kind, summary, task_id — free-form body FIRST — and `[:400]` cut
    # `task_id` off the end. Measured: a task body over ~300 characters
    # dropped the id, `attempted_task_ids()` returned nothing for it, and
    # `select_target()` re-picked that same oldest task on every scheduled
    # run forever. The starvation this whole mechanism exists to prevent,
    # reachable by writing a slightly longer task description. (Devin on
    # #1200.)
    claim = ""
    # `isinstance` because `target` comes from the untrusted receipt and this
    # module's rule is that nothing the propose phase says is evidence. The
    # top-level receipt is validated as a dict; `target` is not, so `null`, a
    # string or a list all reach here. `.get()` on any of those raises
    # AttributeError — AFTER the push and BEFORE `gh pr create`, so it escapes
    # main(), skips receipt(), skips the rollback, and strands exactly the
    # orphan branch this PR exists to eliminate. Note `proposed.get("target",
    # {})` does NOT protect: the default applies only when the key is absent,
    # not when it is present and null. (Devin on #1200.)
    task_id = target.get("task_id") if isinstance(target, dict) else None
    if isinstance(task_id, str) and task_id:
        claim = ("- Consumption claim: "
                 f"`{json.dumps({'task_id': task_id}, sort_keys=True)}`\n")
    body = (
        "Hardening-lane output — **draft only**, produced by an agent that "
        "held no repository credential.\n\n"
        f"{claim}"
        f"- Target: `{json.dumps(target)[:400]}`\n"
        f"- Verified at delivery: {lines} changed lines across "
        f"{len(paths)} file(s), one commit on `{base_sha[:12]}`, no referee "
        "paths touched.\n"
        "- The proposing job ran with `contents: read` and "
        "`persist-credentials: false`; this PR was pushed by a separate job "
        "on a separate runner that never executed agent code.\n"
        "- Every figure above was re-derived from the delivered commit and "
        "from `origin` — the proposing phase's receipt is narrative, not "
        "evidence.\n\n"
        "Enters the review pipeline; the operator flips it ready."
    )
    pr = _run([
        GH_BIN, "pr", "create", "--repo", args.repo, "--draft",
        "--head", branch, "--base", args.base,
        "--title", commit_subject(head_sha),
        "--body", body,
        "--label", ",".join(LANE_LABELS),
    ])
    if pr.returncode == 0:
        receipt({"status": "DRAFT_PR_OPENED", **verified_facts,
                 "pr_output": (pr.stdout + pr.stderr)[-500:]}, out)
        return 0

    # A TIMED-OUT `gh pr create` is not a failed one. `gh` runs the GraphQL
    # mutation and then prints the URL; a timeout between those two leaves the
    # PR open on GitHub while the client reports non-zero. Rolling back there
    # deletes the head branch of a PR that exists — and GitHub closes a PR
    # whose head branch is deleted, so the lane would destroy the work it just
    # published and report "creation failed" for it.
    #
    # This is a defect this PR introduced: before the TimeoutExpired arm in
    # _run(), a hung `gh pr create` crashed main() and nothing was deleted.
    # Converting it to a non-zero exit made the rollback reachable. Ask GitHub
    # what exists rather than inferring it from an exit code, and treat "I
    # cannot tell" as "do not delete" — an orphan branch is recoverable, a
    # deleted PR is not. (Devin on #1200.)
    #
    # The probe runs for EVERY non-zero exit, not just the timeout. Gating it
    # on EXIT_TIMEOUT was my own too-narrow first fix: it closed the reported
    # instance and left the class open, while the comment above already argued
    # the general case. A timeout is not the only failure that can follow a
    # successful mutation — a connection reset while reading the response does
    # it, and so does the plainest case of all, which needs no race at all:
    # a retry where `gh` refuses because a PR for this branch ALREADY EXISTS.
    # That exits non-zero, and a PR provably exists. Rolling back there would
    # delete the branch and close it. (Devin on #1200, second pass.)
    #
    # The one exit that needs no probe is a missing `gh` binary: no process
    # ran, so no mutation can have happened, and the branch really is an
    # orphan. Probing with the same missing binary would only ever answer
    # "unknown" and strand it.
    if pr.returncode != EXIT_NOT_FOUND:
        existing = _run([GH_BIN, "pr", "list", "--repo", args.repo,
                         "--head", branch, "--state", "all",
                         "--json", "number", "--limit", "5"])
        unknown = existing.returncode != 0
        found = (not unknown
                 and existing.stdout.strip() not in ("", "[]"))
        if unknown or found:
            receipt({"status": "PR_CREATE_AMBIGUOUS", **verified_facts,
                     "pr_output": (pr.stdout + pr.stderr)[-500:],
                     "branch_rollback": "kept: " + (
                         "a PR already exists for this branch; deleting it "
                         "would close that PR" if found else
                         "could not enumerate PRs for this branch, so the "
                         "delete could not be proven safe")}, out)
            return 1

    receipt({"status": "PR_CREATE_FAILED", **verified_facts,
             "pr_output": (pr.stdout + pr.stderr)[-500:],
             "branch_rollback": rollback_branch(branch, head_sha)}, out)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
