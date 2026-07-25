#!/usr/bin/env python3
"""Spine bypass report — warning-only scan of dispatch paths.

Scans production ``dharma_swarm/`` code for A2A ``server.submit()`` calls
that bypass ``invoke_agent()``.  Outputs a classified table distinguishing:

    spine-adopted    — call inside an invoke_agent() invoker closure
    intentional      — known migration-bypass on the allowlist
    unknown          — dispatch path not yet classified
    test-only        — lives under tests/ (not scanned by default)
    non-production   — docstring, comment, or docs reference

This script **reports only** — it never fails CI.  Hard guards live in
``scripts/uplift_guards/check_spine_ownership.py``.

Usage::

    python3 scripts/governance/spine_bypass_report.py
    python3 scripts/governance/spine_bypass_report.py --json
"""
import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRODUCTION_DIR = _REPO_ROOT / "dharma_swarm"

# Regex matching A2AServer .submit( calls specifically.
# Matches:  _server.submit(  server.submit(  self._server.submit(
# Excludes: pool.submit(  SkillBridge.submit(  etc.
_SUBMIT_RE = re.compile(r"(?:_server|(?<!\w)server)\.submit\(")

# Known spine-adopted call sites: file:line pairs where .submit() is
# intentionally inside an invoke_agent() invoker closure.
_SPINE_ADOPTED: set[tuple[str, int]] = {
    # submit_task_via_spine() invoker closure — the ONE blessed A2A submit
    # path. All production surfaces (bridge ingest, node_gateway endpoints,
    # a2a_client._dispatch_local, nats_transport.consume_message) route
    # through this single call site.
    ("dharma_swarm/a2a/spine_adapter.py", 88),
}

# Known intentional migration-bypass sites (allowlist).
# Each entry: (relative_path, line_number, reason).
#
# DRAINED TO ZERO 2026-07-03 (spine-adoption item 4). Doctrine
# (docs/plans/ORGANISM_REWIRE_DOCTRINE_2026-07-02.md §1): this stays empty.
# The ONLY sanctioned way to add an entry is a PR that also raises the
# `spine_bypass_entries` ratchet baseline
# (docs/governance/hygiene/ratchet_baselines.json) with review — a visible
# governance act, never a runtime escape hatch.
_INTENTIONAL_BYPASS: dict[tuple[str, int], str] = {}

# Stable snippet-keyed fallback for intentional sites whose line numbers
# drift during transport hardening. Keys are (relative_path, exact code
# line). Kept EMPTY for the same doctrine reason as _INTENTIONAL_BYPASS:
# every previously allowlisted dispatch path has been drained through
# submit_task_via_spine(). Adding an entry is a reviewed governance act.
_INTENTIONAL_BYPASS_SNIPPETS: dict[tuple[str, str], str] = {}

# Known non-production lines (docstring examples, etc.)
_NON_PRODUCTION: set[tuple[str, int]] = {
    ("dharma_swarm/a2a/a2a_server.py", 327),  # docstring example
}


@dataclass
class BypassEntry:
    file: str
    line: int
    classification: str  # spine-adopted | intentional | unknown | non-production
    reason: str = ""
    code: str = ""


def _scan_production_submits() -> list[BypassEntry]:
    """Scan dharma_swarm/ for .submit( calls and classify each."""
    entries: list[BypassEntry] = []

    for root, _dirs, files in os.walk(_PRODUCTION_DIR):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = Path(root) / fname
            rel = str(fpath.relative_to(_REPO_ROOT))
            try:
                lines = fpath.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue

            for i, line_text in enumerate(lines, 1):
                if not _SUBMIT_RE.search(line_text):
                    continue
                # Skip comments and docstrings
                stripped = line_text.lstrip()
                if stripped.startswith("#"):
                    continue
                if stripped.startswith(('"""', "'''", '``')):
                    continue

                key = (rel, i)
                code = stripped.rstrip()

                if key in _SPINE_ADOPTED:
                    entries.append(BypassEntry(
                        file=rel, line=i,
                        classification="spine-adopted",
                        reason="Inside invoke_agent() invoker closure",
                        code=code,
                    ))
                elif key in _NON_PRODUCTION:
                    entries.append(BypassEntry(
                        file=rel, line=i,
                        classification="non-production",
                        reason="Docstring / example code",
                        code=code,
                    ))
                elif key in _INTENTIONAL_BYPASS:
                    entries.append(BypassEntry(
                        file=rel, line=i,
                        classification="intentional",
                        reason=_INTENTIONAL_BYPASS[key],
                        code=code,
                    ))
                elif (rel, code) in _INTENTIONAL_BYPASS_SNIPPETS:
                    entries.append(BypassEntry(
                        file=rel, line=i,
                        classification="intentional",
                        reason=_INTENTIONAL_BYPASS_SNIPPETS[(rel, code)],
                        code=code,
                    ))
                else:
                    entries.append(BypassEntry(
                        file=rel, line=i,
                        classification="unknown",
                        reason="Not yet classified — review needed",
                        code=code,
                    ))

    return sorted(entries, key=lambda e: (e.classification, e.file, e.line))


def _print_table(entries: list[BypassEntry]) -> None:
    """Print a human-readable report."""
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.classification] = counts.get(e.classification, 0) + 1

    print("=" * 72)
    print("SPINE BYPASS REPORT (warning only — does not fail CI)")
    print("=" * 72)
    print()

    # Summary
    total = len(entries)
    adopted = counts.get("spine-adopted", 0)
    intentional = counts.get("intentional", 0)
    unknown = counts.get("unknown", 0)
    non_prod = counts.get("non-production", 0)

    print(f"  Total .submit() sites in dharma_swarm/:  {total}")
    print(f"  Spine-adopted (via invoke_agent):         {adopted}")
    print(f"  Intentional migration bypass:             {intentional}")
    print(f"  Unknown / unclassified:                   {unknown}")
    print(f"  Non-production (docstring/example):       {non_prod}")
    print()

    if total == 0:
        print("  No .submit() call sites found.")
        return

    # Detail table
    print(f"{'Classification':<18} {'File':<45} {'Line':>5}  {'Reason'}")
    print("-" * 120)
    for e in entries:
        print(f"{e.classification:<18} {e.file:<45} {e.line:>5}  {e.reason}")

    print()
    if unknown > 0:
        print(
            f"⚠  {unknown} unknown bypass(es) found. "
            "Add to _INTENTIONAL_BYPASS or _SPINE_ADOPTED in this script, "
            "or migrate to invoke_agent()."
        )
    else:
        print(
            "✓  All .submit() sites classified. "
            f"{intentional} intentional bypass(es) remain on the migration allowlist."
        )
    print()


def _print_json(entries: list[BypassEntry]) -> None:
    """Print JSON report for programmatic consumption."""
    data = {
        "report": "spine_bypass",
        "entries": [
            {
                "file": e.file,
                "line": e.line,
                "classification": e.classification,
                "reason": e.reason,
                "code": e.code,
            }
            for e in entries
        ],
        "summary": {},
    }
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.classification] = counts.get(e.classification, 0) + 1
    data["summary"] = counts
    print(json.dumps(data, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Spine bypass report")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    entries = _scan_production_submits()

    if args.json:
        _print_json(entries)
    else:
        _print_table(entries)

    # Always exit 0 — this is warning-only
    return 0


if __name__ == "__main__":
    sys.exit(main())
