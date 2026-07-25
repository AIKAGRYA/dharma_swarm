#!/usr/bin/env python3
"""Hygiene delta-ratchet.

Compare hygiene-violation counts between the PR base and the PR head, and
fail when the head **adds** new violations in **touched files**.

The repo already ships several non-blocking hygiene detectors:

  - ``scripts/governance/hygiene/sync_in_async.py``      (AS-08)
  - ``scripts/governance/hygiene/scan.py``                (AS-02 / AS-09)
  - ``scripts/governance/check_module_budget.py``         (AS-03)

Those produce baseline reports but do not gate CI. This ratchet wraps the
ones that are cheap and deterministic and enforces a *touched-file* rule:

  * Files that did not change between base and head are exempt (we do not
    care if a track-of-the-week happens to drop the global count).
  * Files that changed between base and head must not increase their
    individual violation count.

Files that drop below their baseline are encouraged (delta is reported).

New files (absent at the base ref) inherit a base count of 0, which would
punish pure code moves: relocating existing violations into a new module
reads as a per-file regression even when the repo-wide total is unchanged
or improved. To keep move-refactors legal, a NEW file's count for a metric
is evaluated against the NET delta of that metric across ALL touched files
in the diff: if the net is <= 0 the count is classified MOVED (reported,
not failing); if the net is > 0 the new file still fails. Files that
existed at base keep the strict per-file ratchet.

Usage:
    python scripts/governance/hygiene/delta_ratchet.py \\
        --base-ref origin/main --head-ref HEAD

    python scripts/governance/hygiene/delta_ratchet.py --json

Exit codes:
    0   no touched file regressed any tracked dimension (moves are exit 0)
    1   at least one touched file added net-new violations
    2   git / environment error
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# --- detectors --------------------------------------------------------------

BLOCKING_CALLS = {
    "time.sleep",
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "subprocess.run",
    "subprocess.call",
}

# Crude but deterministic: matches ``except Exception:`` / ``except BaseException:``
# / bare ``except:`` immediately followed by ``pass`` or a logging-only body.
# We rely on the AST for ``except``, then string-scan the body for ``pass`` or
# a single logger call \u2014 same heuristic as in scan.sh / AS-09.
SILENT_EXCEPT_TYPES = {"Exception", "BaseException", None}  # None = bare except

# Files we never scan (vendored, generated, fixture).
EXEMPT_PATH_FRAGMENTS = (
    "/__pycache__/",
    "/_vendor/",
    "/migrations/",
    "/.venv/",
    "/venv/",
)


def _dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted(node.value)
        if parent:
            return f"{parent}.{node.attr}"
    return None


def count_sync_in_async(source: str) -> int:
    """AS-08: sync I/O inside async functions."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return 0
    hits = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = _dotted(child.func)
                if name in BLOCKING_CALLS:
                    hits += 1
    return hits


def _stmt_is_silent(stmt: ast.stmt) -> bool:
    """A body that is silent: just ``pass``, or a single Expr that is a Constant/Call to log.*."""
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr):
        v = stmt.value
        if isinstance(v, ast.Constant):
            return True
        if isinstance(v, ast.Call):
            name = _dotted(v.func) or ""
            # logger.debug / logger.warning / log.warning / logging.warning etc.
            if re.match(r"^(logger?|log|logging)\.(debug|info|warning|warn|error|exception)$", name):
                return True
    return False


def count_silent_excepts(source: str) -> int:
    """AS-09: broad ``except`` handlers that swallow without re-raising or recording."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return 0
    hits = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        # Determine the caught type name.
        caught: str | None
        if node.type is None:
            caught = None
        elif isinstance(node.type, ast.Name):
            caught = node.type.id
        elif isinstance(node.type, ast.Attribute):
            caught = node.type.attr
        else:
            caught = None
        if caught not in SILENT_EXCEPT_TYPES:
            continue
        # Body must be small and silent.
        if not node.body:
            continue
        if len(node.body) > 2:
            continue
        if all(_stmt_is_silent(b) for b in node.body):
            hits += 1
    return hits


DETECTORS: dict[str, callable] = {
    "sync_in_async": count_sync_in_async,
    "silent_excepts": count_silent_excepts,
}


# --- git plumbing -----------------------------------------------------------


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (rc={result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def changed_python_files(base: str, head: str, cwd: Path) -> list[str]:
    out = _run_git(["diff", "--name-only", base, head, "--", "*.py"], cwd)
    files = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(frag in f"/{line}" for frag in EXEMPT_PATH_FRAGMENTS):
            continue
        files.append(line)
    return files


def show_at_ref(ref: str, path: str, cwd: Path) -> str | None:
    """Return file contents at a ref, or None if missing."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


# --- ratchet core -----------------------------------------------------------


@dataclass
class FileDelta:
    path: str
    base_counts: dict[str, int] = field(default_factory=dict)
    head_counts: dict[str, int] = field(default_factory=dict)
    base_exists: bool = True
    # Metrics reclassified from regression to MOVED by apply_move_credit
    # (new-file counts covered by net improvement across the touched set).
    moved: dict[str, tuple[int, int]] = field(default_factory=dict)

    def regressions(self) -> dict[str, tuple[int, int]]:
        out: dict[str, tuple[int, int]] = {}
        for name in DETECTORS:
            if name in self.moved:
                continue
            b = self.base_counts.get(name, 0)
            h = self.head_counts.get(name, 0)
            if h > b:
                out[name] = (b, h)
        return out

    def improvements(self) -> dict[str, tuple[int, int]]:
        out: dict[str, tuple[int, int]] = {}
        for name in DETECTORS:
            b = self.base_counts.get(name, 0)
            h = self.head_counts.get(name, 0)
            if h < b:
                out[name] = (b, h)
        return out

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "base": self.base_counts,
            "head": self.head_counts,
            "base_exists": self.base_exists,
            "regressions": {k: list(v) for k, v in self.regressions().items()},
            "improvements": {k: list(v) for k, v in self.improvements().items()},
            "moved": {k: list(v) for k, v in self.moved.items()},
        }


def net_deltas(deltas: list[FileDelta]) -> dict[str, int]:
    """Net violation delta per metric across every touched file."""
    net: dict[str, int] = {name: 0 for name in DETECTORS}
    for d in deltas:
        for name in DETECTORS:
            net[name] += d.head_counts.get(name, 0) - d.base_counts.get(name, 0)
    return net


def apply_move_credit(deltas: list[FileDelta]) -> None:
    """Reclassify new-file counts as MOVED when the touched set nets out.

    A file absent at base has a 0 baseline for every metric, so relocating
    existing violations into it reads as a regression even when the diff-wide
    total is flat or improved (PR #774: 4 silent-excepts moved verbatim out
    of vector_store.py into new embedders.py). For each metric where a NEW
    file's head count exceeds its base, if the net delta across ALL touched
    files is <= 0, the count is MOVED, not a regression. Net > 0 still fails.
    Files that existed at base are never excused by the net.
    """
    net = net_deltas(deltas)
    for d in deltas:
        if d.base_exists:
            continue
        for name in DETECTORS:
            b = d.base_counts.get(name, 0)
            h = d.head_counts.get(name, 0)
            if h > b and net.get(name, 0) <= 0:
                d.moved[name] = (b, h)


def evaluate(base: str, head: str, cwd: Path) -> list[FileDelta]:
    files = changed_python_files(base, head, cwd)
    deltas: list[FileDelta] = []
    for f in files:
        base_src = show_at_ref(base, f, cwd)
        head_src = show_at_ref(head, f, cwd)
        d = FileDelta(path=f, base_exists=base_src is not None)
        for name, fn in DETECTORS.items():
            d.base_counts[name] = fn(base_src) if base_src else 0
            d.head_counts[name] = fn(head_src) if head_src else 0
        deltas.append(d)
    apply_move_credit(deltas)
    return deltas


# --- reporting --------------------------------------------------------------


def render_text(deltas: list[FileDelta]) -> str:
    out: list[str] = []
    out.append(f"hygiene delta-ratchet — {len(deltas)} touched .py files")
    out.append("")

    regressed = [d for d in deltas if d.regressions()]
    moved = [d for d in deltas if d.moved and not d.regressions()]
    improved = [
        d for d in deltas if d.improvements() and not d.regressions() and not d.moved
    ]
    stable = [
        d
        for d in deltas
        if not d.regressions() and not d.improvements() and not d.moved
    ]

    if regressed:
        out.append(f"## REGRESSIONS  ({len(regressed)})")
        for d in regressed:
            for name, (b, h) in d.regressions().items():
                out.append(f"  - {d.path}  {name}: {b} -> {h}  (+{h - b})")
        out.append("")
    else:
        out.append("## REGRESSIONS  (0)  — no touched file added net-new violations")
        out.append("")

    if moved:
        net = net_deltas(deltas)
        out.append(
            f"## MOVED  ({len(moved)})  — new-file counts offset by improvements"
            " elsewhere in this diff (net <= 0)"
        )
        for d in moved:
            for name, (b, h) in d.moved.items():
                out.append(
                    f"  - {d.path}  {name}: {b} -> {h}"
                    f"  (+{h - b} relocated; touched-set net {net[name]:+d})"
                )
        out.append("")

    if improved:
        out.append(f"## IMPROVEMENTS  ({len(improved)})")
        for d in improved:
            for name, (b, h) in d.improvements().items():
                out.append(f"  - {d.path}  {name}: {b} -> {h}  ({h - b})")
        out.append("")

    out.append(f"## STABLE  ({len(stable)})")
    for d in stable[:20]:
        out.append(f"  - {d.path}")
    if len(stable) > 20:
        out.append(f"  ... and {len(stable) - 20} more")
    return "\n".join(out)


# --- main -------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--base-ref",
        default=os.environ.get("GITHUB_BASE_REF", "origin/main"),
        help="Git ref for the PR base (default: origin/main).",
    )
    p.add_argument(
        "--head-ref",
        default="HEAD",
        help="Git ref for the PR head (default: HEAD).",
    )
    p.add_argument("--repo-root", default=str(REPO_ROOT))
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    cwd = Path(args.repo_root).resolve()
    try:
        deltas = evaluate(args.base_ref, args.head_ref, cwd)
    except RuntimeError as exc:
        print(f"hygiene-delta-ratchet: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps([d.to_dict() for d in deltas], indent=2, sort_keys=True))
    else:
        print(render_text(deltas))

    return 1 if any(d.regressions() for d in deltas) else 0


if __name__ == "__main__":
    raise SystemExit(main())
