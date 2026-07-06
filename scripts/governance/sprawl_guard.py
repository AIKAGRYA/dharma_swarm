#!/usr/bin/env python3
"""Sprawl guard — the missing ENFORCEMENT for axioms A1/A2 (read-only, deterministic).

Why this exists (evidence, 2026-07-06)
--------------------------------------
The operator runs ``make onboard`` / ``make orient`` before most builds, the
SOVEREIGN_MANIFEST already declares axioms **A1 NO FLAT-PACKAGE GROWTH** and
**A2 NO DUPLICATE IMPLEMENTATIONS**, and ``ACTIVE_SURFACE_MANIFEST.yaml`` already
exists as a surface registry — and yet ``holon_bridge.py`` / ``holon_runtime.py``
each exist in ~138 copies across ~69 trees, with 3-4 drifted implementations.

Conclusion: the failure is not missing rules or missing orientation. It is that
*nothing fails when a duplicate is created*. Orientation tells you where things
are; it does not stop you adding the 139th copy. This script is the boring gate
that returns a non-zero exit code the moment a declared singleton is duplicated
or a retired module is imported.

Design invariants (mirrors the reversibility gate's spirit):
  * READ-ONLY: it inspects tracked files; it never edits, deletes, or moves.
  * DETERMINISTIC: no model, no network; output is a pure function of the tree.
  * SCOPED: it uses ``git ls-files`` so nested worktrees / .venv / vendor copies
    are naturally excluded — the disease being measured is *in-repo* drift, not
    the harmless mirror copies in sibling worktrees.
  * PY3.9-SAFE: this guard must run under /usr/bin/python3 too, so it must never
    contain the 3.10-only syntax that would make it fail to even collect.

Usage:
    python3 scripts/governance/sprawl_guard.py            # human report
    python3 scripts/governance/sprawl_guard.py --json     # machine receipt
    python3 scripts/governance/sprawl_guard.py --strict   # exit 1 on any finding

Exit codes: 0 = clean; 1 = at least one sprawl finding (with --strict, or always
for hard violations). This is intended for pre-commit / CI / make targets.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict


# --------------------------------------------------------------------------- #
# The singleton registry. This is the whole point: a small, declarative list of
# "there must be exactly ONE of these" primitives. Generalizes beyond holons —
# add any symbol/module that should have one canonical home. Keep it boring.
# --------------------------------------------------------------------------- #
SINGLETON_SYMBOLS = [
    {
        "symbol": "def load_holon",
        "canonical": "dharma_swarm/holon_bridge.py",
        "why": "identity->RunningHolon loader; one runtime definition only",
    },
    {
        "symbol": "def holon_wake_cycle",
        "canonical": "dharma_swarm/holon_runtime.py",
        "why": "governed wake metabolism; one runtime definition only",
    },
]

# Modules that have been retired to a single canonical home. A tracked runtime
# file importing the left pattern is a hard violation (points at a dead fork).
FORBIDDEN_IMPORTS = [
    {
        "pattern": "holon.holon_bridge",
        "use_instead": "dharma_swarm.holon_bridge",
        "why": "standalone holon/ fork; not the canonical runtime bridge",
    },
    {
        "pattern": "holon.holon_runtime",
        "use_instead": "dharma_swarm.holon_runtime",
        "why": "standalone holon/ fork; not the canonical runtime wake loop",
    },
]

# Filenames to watch for copy-drift. We report distinct-content count per name so
# "138 copies" is correctly read as "N distinct implementations mirrored M times".
COPY_WATCHLIST = ["holon_bridge.py", "holon_runtime.py"]

# Paths whose matches are allowed / expected (tests, fixtures, and — until the
# collapse lands — the known holon/ fork itself, so the guard reports it as the
# ONE thing to delete rather than drowning in noise).
ALLOW_PATH_SUBSTRINGS = ("/tests/", "tests/", "/fixtures/", "fixtures/", "/conftest")
KNOWN_FORK_PREFIX = "holon/"  # the standalone fork slated for deletion (Phase 2)


def _git_tracked_files(repo_root):
    out = subprocess.check_output(
        ["git", "ls-files"], cwd=repo_root, text=True
    )
    return [line for line in out.splitlines() if line]


def _is_test_or_fixture(path):
    return any(s in path for s in ALLOW_PATH_SUBSTRINGS)


def _sha1(repo_root, path):
    full = os.path.join(repo_root, path)
    try:
        with open(full, "rb") as fh:
            return hashlib.sha1(fh.read()).hexdigest()
    except OSError:
        return "<unreadable>"


def scan(repo_root):
    files = _git_tracked_files(repo_root)
    py_files = [f for f in files if f.endswith(".py")]

    findings = []

    # 1) Singleton symbol definitions.
    singleton_report = []
    for entry in SINGLETON_SYMBOLS:
        symbol = entry["symbol"]
        # Match both ``def NAME`` and ``async def NAME`` so async coroutines
        # (e.g. ``async def holon_wake_cycle``) are not false-negatives.
        if symbol.startswith("def "):
            fn_name = symbol[len("def ") :]
            needle = re.compile(r"^\s*(?:async\s+)?def\s+" + re.escape(fn_name) + r"\b")
        else:
            needle = re.compile(r"^\s*" + re.escape(symbol) + r"\b")
        definers = []
        for f in py_files:
            if _is_test_or_fixture(f):
                continue
            full = os.path.join(repo_root, f)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        if needle.search(line):
                            definers.append(f)
                            break
            except OSError:
                continue
        extra = [d for d in definers if d != entry["canonical"]]
        canonical_found = entry["canonical"] in definers
        status = "ok" if (canonical_found and not extra) else "fail"
        singleton_report.append(
            {
                "symbol": symbol,
                "canonical": entry["canonical"],
                "canonical_found": canonical_found,
                "definers": definers,
                "extra_definitions": extra,
                "status": status,
            }
        )
        if status == "fail":
            findings.append(
                "SINGLETON %r: canonical_found=%s extra=%s"
                % (symbol, canonical_found, extra)
            )

    # 2) Forbidden imports of retired forks.
    import_report = []
    for entry in FORBIDDEN_IMPORTS:
        pat = entry["pattern"]
        rx = re.compile(r"(?:^|\W)(?:import|from)\s+" + re.escape(pat) + r"\b")
        offenders = []
        for f in py_files:
            if _is_test_or_fixture(f) or f.startswith(KNOWN_FORK_PREFIX):
                continue
            full = os.path.join(repo_root, f)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            if rx.search(text):
                offenders.append(f)
        import_report.append(
            {"pattern": pat, "use_instead": entry["use_instead"], "offenders": offenders}
        )
        if offenders:
            findings.append("FORBIDDEN_IMPORT %r used by %s" % (pat, offenders))

    # 3) Copy-drift census (in-repo tracked files only).
    copy_report = []
    by_name = defaultdict(list)
    for f in files:
        base = os.path.basename(f)
        if base in COPY_WATCHLIST:
            by_name[base].append(f)
    for name in COPY_WATCHLIST:
        paths = by_name.get(name, [])
        digest_to_paths = defaultdict(list)
        for p in paths:
            digest_to_paths[_sha1(repo_root, p)].append(p)
        copy_report.append(
            {
                "name": name,
                "tracked_copies": len(paths),
                "distinct_contents": len(digest_to_paths),
                "versions": [
                    {"sha1": d[:12], "count": len(ps), "paths": ps}
                    for d, ps in sorted(
                        digest_to_paths.items(), key=lambda kv: -len(kv[1])
                    )
                ],
            }
        )

    return {
        "singletons": singleton_report,
        "forbidden_imports": import_report,
        "copy_drift": copy_report,
        "findings": findings,
        "clean": not findings,
    }


def _print_human(report):
    print("=" * 72)
    print("SPRAWL GUARD — read-only enforcement of A1/A2 (no model, deterministic)")
    print("=" * 72)
    print("\n[1] SINGLETON SYMBOLS (must have exactly one canonical definition)")
    for s in report["singletons"]:
        mark = "OK  " if s["status"] == "ok" else "FAIL"
        print("  %s %s -> %s" % (mark, s["symbol"], s["canonical"]))
        if s["extra_definitions"]:
            for e in s["extra_definitions"]:
                print("        extra definition: %s" % e)
        if not s["canonical_found"]:
            print("        canonical definition NOT FOUND")

    print("\n[2] FORBIDDEN IMPORTS (retired forks must not be imported by runtime)")
    for i in report["forbidden_imports"]:
        if i["offenders"]:
            print("  FAIL import %s (use %s):" % (i["pattern"], i["use_instead"]))
            for o in i["offenders"]:
                print("        %s" % o)
        else:
            print("  OK   no runtime import of %s" % i["pattern"])

    print("\n[3] COPY DRIFT (in-repo tracked; distinct contents = real drift)")
    for c in report["copy_drift"]:
        print(
            "  %s: %d tracked copies, %d DISTINCT contents"
            % (c["name"], c["tracked_copies"], c["distinct_contents"])
        )
        for v in c["versions"]:
            print("        %s x%d  %s" % (v["sha1"], v["count"], v["paths"]))

    print("\n" + "-" * 72)
    if report["clean"]:
        print("RESULT: CLEAN — no sprawl findings.")
    else:
        print("RESULT: %d FINDING(S):" % len(report["findings"]))
        for f in report["findings"]:
            print("  - " + f)
    print("-" * 72)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only sprawl guard for A1/A2.")
    ap.add_argument("--json", action="store_true", help="emit JSON receipt")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 on any finding (default: exit 1 only when findings exist)",
    )
    ap.add_argument("--repo-root", default=None)
    args = ap.parse_args(argv)

    repo_root = args.repo_root or os.getcwd()
    # Resolve to the git top-level so it works from any subdir.
    try:
        repo_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=repo_root, text=True
        ).strip()
    except subprocess.CalledProcessError:
        pass

    report = scan(repo_root)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)

    # A finding is a non-zero exit. --strict is reserved for future "warn-only"
    # categories; today any finding fails so the gate is honest by default.
    return 0 if report["clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
