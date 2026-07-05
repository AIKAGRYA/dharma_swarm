#!/usr/bin/env python3
"""Workflow cache-poisoning and token least-privilege guard.

Two dormant meta-grep guards over ``.github/workflows/*.yml``. They add no
runtime cost on the current tree (which has no ``actions/cache@`` step and no
custom pip cache) and arm themselves the moment a cache step or a
permission-less workflow lands.

Guard A -- cache-poisoning.
GitHub Actions cache is a cross-branch write surface: a job on an untrusted
branch can seed a cache entry that a later privileged job restores. The two
mitigations that neutralise the class are (1) an exact cache key that is a
pure function of a lockfile, so a poisoned key never matches, and (2) no
``restore-keys`` partial fallback, so a near-miss key does not silently pull a
foreign entry. This guard trips when a workflow adds:

  * an ``actions/cache@`` (or ``actions/cache/restore@``) step whose ``key`` is
    not a ``hashFiles(...)`` of a lockfile, or that carries any branch/ref
    token in the key, or that declares ``restore-keys``; or
  * a ``setup-python`` / ``setup-node`` built-in ``cache:`` (pip/npm/yarn/pnpm)
    with no ``cache-dependency-path`` lockfile pin.

Guard B -- token least-privilege.
Every workflow must declare a top-level ``permissions:`` block so the run does
not inherit the repository default token scope. A workflow with no
``permissions:`` block trips this guard.

Oracles: GitHub Actions cache-poisoning advisories and the OpenSSF Scorecard
token-permissions / cache checks.

Usage:
    python3 scripts/governance/check_workflow_cache_token.py
    python3 scripts/governance/check_workflow_cache_token.py --workflows-dir DIR

Exit codes:
    0   every workflow is compliant
    1   at least one cache or permissions violation
    2   environment error (no workflow directory found)
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

CACHE_USES_RE = re.compile(r"uses:\s*actions/cache(?:/restore|/save)?@")
SETUP_CACHE_RE = re.compile(r"^\s*cache:\s*(?:['\"]?)(pip|npm|yarn|pnpm)(?:['\"]?)\s*(?:#.*)?$")
KEY_RE = re.compile(r"^\s*key:\s*(.+?)\s*$")
RESTORE_KEYS_RE = re.compile(r"^\s*restore-keys:")
DEP_PATH_RE = re.compile(r"^\s*cache-dependency-path:")
TOP_PERMISSIONS_RE = re.compile(r"^permissions:\s*(?:#.*)?$")

# Tokens that make a cache key branch/ref/sha dependent rather than a pure
# function of pinned dependencies.
BRANCH_TOKENS = (
    "github.ref",
    "github.ref_name",
    "github.head_ref",
    "github.base_ref",
    "github.sha",
    "github.event",
)

# Lockfile name fragments a compliant hashFiles() key may hash.
LOCKFILE_FRAGMENTS = (
    ".lock",
    "lock.json",
    "requirements",
    "pipfile.lock",
    "poetry.lock",
    "uv.lock",
    "gemfile.lock",
    "go.sum",
    "cargo.lock",
)


@dataclass
class Violation:
    workflow: str
    line: int
    guard: str
    message: str


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _collect_step_block(lines: list[str], start: int) -> list[tuple[int, str]]:
    """Return (line_no, text) for the step that owns the cache ``uses`` at
    index ``start``: the ``uses`` line and every following line that is part of
    the same list item (deeper-or-equal indent, stopping at the next ``- ``
    list item or a dedent)."""
    base = _indent(lines[start])
    block = [(start + 1, lines[start])]
    for idx in range(start + 1, len(lines)):
        line = lines[idx]
        if not line.strip():
            block.append((idx + 1, line))
            continue
        if _indent(line) < base:
            break
        if line.lstrip().startswith("- "):
            break
        block.append((idx + 1, line))
    return block


def _key_is_lockfile_pure(key_value: str) -> bool:
    lowered = key_value.lower()
    if any(tok in lowered for tok in BRANCH_TOKENS):
        return False
    if "hashfiles(" not in lowered:
        return False
    return any(frag in lowered for frag in LOCKFILE_FRAGMENTS)


def _check_cache_steps(rel: str, lines: list[str]) -> list[Violation]:
    out: list[Violation] = []
    for idx, line in enumerate(lines):
        if not CACHE_USES_RE.search(line):
            continue
        block = _collect_step_block(lines, idx)
        key_value: str | None = None
        has_restore_keys = False
        for _line_no, text in block:
            m = KEY_RE.match(text)
            if m and key_value is None:
                key_value = m.group(1)
            if RESTORE_KEYS_RE.match(text):
                has_restore_keys = True
        if has_restore_keys:
            out.append(Violation(
                rel, idx + 1, "cache",
                "actions/cache step declares restore-keys partial fallback; "
                "use exact-key-only restore (remove restore-keys).",
            ))
        if key_value is None:
            out.append(Violation(
                rel, idx + 1, "cache",
                "actions/cache step has no explicit key; require a "
                "hashFiles() key that is a pure function of a lockfile.",
            ))
        elif not _key_is_lockfile_pure(key_value):
            out.append(Violation(
                rel, idx + 1, "cache",
                "actions/cache key is not a pure function of a lockfile "
                f"(branch/ref token or non-lockfile hashFiles): {key_value!r}",
            ))
    return out


def _check_setup_cache(rel: str, lines: list[str]) -> list[Violation]:
    out: list[Violation] = []
    for idx, line in enumerate(lines):
        m = SETUP_CACHE_RE.match(line)
        if not m:
            continue
        base = _indent(line)
        # The sibling with-block keys share this indentation. Scan the
        # contiguous same-or-deeper run around this line for a dependency path.
        has_dep_path = False
        for jdx in range(idx + 1, len(lines)):
            nxt = lines[jdx]
            if nxt.strip() and _indent(nxt) < base:
                break
            if nxt.lstrip().startswith("- "):
                break
            if DEP_PATH_RE.match(nxt):
                has_dep_path = True
                break
        for jdx in range(idx - 1, -1, -1):
            prev = lines[jdx]
            if prev.strip() and _indent(prev) < base:
                break
            if prev.lstrip().startswith("- "):
                break
            if DEP_PATH_RE.match(prev):
                has_dep_path = True
                break
        if not has_dep_path:
            out.append(Violation(
                rel, idx + 1, "cache",
                f"setup action 'cache: {m.group(1)}' has no "
                "cache-dependency-path lockfile pin.",
            ))
    return out


def _check_permissions(rel: str, lines: list[str]) -> list[Violation]:
    for line in lines:
        if TOP_PERMISSIONS_RE.match(line):
            return []
    return [Violation(
        rel, 1, "permissions",
        "workflow declares no top-level permissions block; add an explicit "
        "least-privilege permissions block.",
    )]


def scan_workflows(workflows_dir: Path) -> list[Violation]:
    out: list[Violation] = []
    for path in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
        rel = f".github/workflows/{path.name}"
        lines = path.read_text(encoding="utf-8").splitlines()
        out.extend(_check_permissions(rel, lines))
        out.extend(_check_cache_steps(rel, lines))
        out.extend(_check_setup_cache(rel, lines))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workflows-dir",
        default=None,
        help="path to the workflows directory (default: <repo>/.github/workflows)",
    )
    args = parser.parse_args(argv)

    if args.workflows_dir:
        workflows_dir = Path(args.workflows_dir)
    else:
        repo_root = Path(__file__).resolve().parents[2]
        workflows_dir = repo_root / ".github" / "workflows"

    if not workflows_dir.is_dir():
        print(f"::error::cache-token guard — no workflows directory at {workflows_dir}")
        return 2

    violations = scan_workflows(workflows_dir)
    if not violations:
        count = len(list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml")))
        print(f"cache-token guard: OK — {count} workflow(s), no cache or "
              "permissions violation.")
        return 0

    cache_v = [v for v in violations if v.guard == "cache"]
    perm_v = [v for v in violations if v.guard == "permissions"]
    print(f"::error::cache-token guard — {len(violations)} violation(s) "
          f"({len(cache_v)} cache, {len(perm_v)} permissions):")
    for v in violations:
        print(f"  [{v.guard}] {v.workflow}:{v.line}: {v.message}")
    print("Cache steps must use an exact hashFiles() lockfile key with no "
          "restore-keys fallback; every workflow must declare a top-level "
          "permissions block.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
