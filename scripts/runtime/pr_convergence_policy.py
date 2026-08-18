#!/usr/bin/env python3
"""pr_convergence_policy.py — deterministic PR convergence ordering (ADVISORY).

The "convergence steward" core, the LIGHT way: a pure, reproducible policy that
ranks open PRs so the swarm self-orders instead of the operator triaging by hand.
It is ADVISORY — it never feeds Merge Master Mike's build_gate blockers and never
changes merge authority. Mike (or the operator) may consume the order as ONE
ordering input; the gate decision is unchanged.

Policy (deterministic — identical inputs always yield identical output):
  R1 drafts-don't-lead   — draft PRs rank last.
  R2 decision > impl     — PRs touching governance/decision surfaces outrank pure
                           implementation PRs.
  R3 surface-overlap->1  — when 2+ non-draft PRs touch the same HAND-EDITED owned
                           surface, elect ONE canonical lane (highest rigor grade,
                           then lowest PR#); the others are marked dependent.
  R4 escalate-when-undef — an overlap with no deterministic canonical signal
                           (equal grade AND no rigor signal at all) is added to
                           escalate[] instead of guessing; the ratchet must
                           exclude escalate-flagged PRs from auto-merge.

Regenerable outputs (active_track_evidence.json/.md, track_portfolio.json) are
NOT real collisions and are excluded from R3 — they regenerate from the gate.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Two PRs both touching these is NOT a real collision (regenerated, not hand-edited).
REGENERABLE = frozenset({
    "reports/governance/active_track_evidence.json",
    "reports/governance/active_track_evidence.md",
    "reports/governance/track_portfolio.json",
})

# A PR touching any of these (hand-edited) is a "decision/governance" lane (R2).
DECISION_GLOBS = (
    "docs/governance/**",
    "docs/architecture/ADRs/**",
    "ACTIVE_TRACK.yaml",
    "docs/governance/ACTIVE_TRACK.yaml",
    "docs/governance/SOVEREIGN_MANIFEST.md",
    "docs/governance/CANONICAL_DOC_STACK.md",
)


def _matches_any(path: str, globs) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def _real_files(files):
    """Files that count for collision — regenerable outputs excluded."""
    return [f for f in files if f not in REGENERABLE]


def is_decision_pr(files) -> bool:
    return any(_matches_any(f, DECISION_GLOBS) for f in _real_files(files))


def overlapping_surface(files_a, files_b, owned_surfaces=()) -> bool:
    """True iff A and B both touch the same hand-edited file or owned-surface glob."""
    ra, rb = set(_real_files(files_a)), set(_real_files(files_b))
    if ra & rb:
        return True
    for surf in owned_surfaces:
        if any(_matches_any(f, [surf]) for f in ra) and any(_matches_any(f, [surf]) for f in rb):
            return True
    return False


def compute_convergence_order(open_prs, pr_files, owned_surfaces=(), grades=None) -> dict:
    """Pure. open_prs: [{number:int, isDraft:bool, ...}]; pr_files: {num:[paths]};
    owned_surfaces: iterable of globs; grades: {num:int}. Returns
    {order, rationale, escalate, canonical}. Same inputs -> same output."""
    grades = grades or {}
    rationale: dict = {}
    escalate: list = []
    canonical: dict = {}
    dependent: set = set()

    drafts = {p["number"]: bool(p.get("isDraft")) for p in open_prs}
    nondraft = [p["number"] for p in open_prs if not drafts.get(p["number"])]

    for i, a in enumerate(sorted(nondraft)):
        for b in sorted(nondraft)[i + 1:]:
            if not overlapping_surface(pr_files.get(a, []), pr_files.get(b, []), owned_surfaces):
                continue
            ga, gb = int(grades.get(a, 0)), int(grades.get(b, 0))
            if ga != gb:
                win, lose = (a, b) if ga > gb else (b, a)            # R3: higher grade wins
            else:
                win, lose = (a, b) if a < b else (b, a)              # tiebreak: lowest #
                if ga == 0 and gb == 0:
                    escalate.extend([a, b])                          # R4: no signal -> escalate
            canonical[f"overlap:{min(a, b)}-{max(a, b)}"] = win
            dependent.add(lose)
            rationale[lose] = f"dependent: converge behind #{win} (shared hand-edited surface)"

    escalate = sorted(set(escalate))

    def sort_key(p):
        n = p["number"]
        return (
            1 if drafts.get(n) else 0,                               # R1: drafts last
            1 if n in dependent else 0,                              # R3: dependents after canonical
            0 if is_decision_pr(pr_files.get(n, [])) else 1,         # R2: decision first
            -int(grades.get(n, 0)),                                  # higher grade first
            n,                                                       # stable final tiebreak
        )

    order = [p["number"] for p in sorted(open_prs, key=sort_key)]
    for n in order:
        if n in rationale:
            continue
        if drafts.get(n):
            rationale[n] = "draft: ranked last (drafts don't lead)"
        elif is_decision_pr(pr_files.get(n, [])):
            rationale[n] = "decision/governance lane: outranks implementation"
        else:
            rationale[n] = "implementation lane"
    return {"order": order, "rationale": rationale, "escalate": escalate, "canonical": canonical}


def _fetch_live(limit: int) -> dict:
    """ADVISORY live run: reuse the existing owners for reads; never mutate."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))  # repo-root only — never shadow bare names
    from scripts.runtime.pr_merge_control import fetch_open_prs, fetch_pr_files  # noqa: E402
    from scripts.governance.check_track_status import (  # noqa: E402
        ACTIVE_TRACK_PATH, load_active_track, normalize_portfolio,
    )
    repo = "AIKAGRYA/dharma_swarm"
    prs = fetch_open_prs(limit)
    pr_files = {p["number"]: [f["path"] for f in fetch_pr_files(p["number"], repo)] for p in prs}
    portfolio = normalize_portfolio(load_active_track(ACTIVE_TRACK_PATH))
    owned = [s for t in portfolio.get("active_tracks", []) for s in (t.get("owned_surfaces") or [])]
    return compute_convergence_order(prs, pr_files, owned_surfaces=owned)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args(argv)
    result = _fetch_live(args.limit)
    print(json.dumps(result, indent=2))
    if result["escalate"]:
        print(f"\nescalate to operator (undefined canonical): {result['escalate']}", file=sys.stderr)
    return 0  # advisory — always exits 0


if __name__ == "__main__":
    raise SystemExit(main())
