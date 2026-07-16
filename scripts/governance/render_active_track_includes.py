#!/usr/bin/env python3
"""render_active_track_includes.py — keep doc pointers in sync with ACTIVE_TRACK.yaml.

Scans governance Markdown for the markers:

    <!-- ACTIVE_TRACK:START -->
    ...managed content...
    <!-- ACTIVE_TRACK:END -->

and rewrites the body between them from docs/governance/ACTIVE_TRACK.yaml.

This is the structural fix for "prose pointer rotted while work moved on":
the prose pointer is now generated from one source. Hand-edits between the
markers are over-written on next run, so they cannot drift.

Usage:
    python3 scripts/governance/render_active_track_includes.py          # rewrite
    python3 scripts/governance/render_active_track_includes.py --check  # CI mode

In --check mode, the script exits non-zero if any managed block is out of date.
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

# Re-use the YAML loader from check_track_status so we stay stdlib-only.
sys.path.insert(0, str(Path(__file__).parent))
from check_track_status import (  # noqa: E402
    load_active_track, ACTIVE_TRACK_PATH, normalize_portfolio, _is_active,
)

START = "<!-- ACTIVE_TRACK:START -->"
END = "<!-- ACTIVE_TRACK:END -->"
BLOCK_RE = re.compile(re.escape(START) + r"(.*?)" + re.escape(END), re.DOTALL)

# Files that render the active-track block. Add new consumers here as the
# governance surface grows; never hand-write between the markers.
MANAGED_FILES = [
    Path("CLAUDE.md"),
    Path("docs/governance/SOVEREIGN_MANIFEST.md"),
]


def _render_one_track(t: dict, lines: list) -> None:
    """Render a single track's compact digest into `lines`.

    Deliberately not the full track body: descriptions, next-items, and
    non-goals live in ACTIVE_TRACK.yaml and its checker. The digest keeps only
    identity, freshness, and surface-ownership boundaries.
    """
    blockers = sum(1 for it in (t.get("next_items") or []) if it.get("blocker"))
    lines.append(
        f"- **`{t.get('id', '(none)')}`** — {t.get('name', '(unnamed)')} "
        f"({t.get('status', 'UNKNOWN')}, serves `{t.get('serves', '(none)')}`, "
        f"verified {t.get('verified_at', '(unset)')}, "
        f"open blocker items: {blockers})"
    )
    owned = t.get("owned_surfaces") or []
    if owned:
        lines.append(f"  - owns: {', '.join(str(s) for s in owned)}")


def render_block(track: dict) -> str:
    """Render the managed governance block from the track portfolio.

    Works for both schemas: normalize_portfolio adapts v1 (singular
    active_track) into a one-track portfolio, so this renders either.

    The stamp's "newest verified_at" is derived from the YAML (never from
    the wall clock) so --check replays byte-for-byte in CI.
    """
    p = normalize_portfolio(track)
    tracks = p["active_tracks"]
    active = [t for t in tracks if _is_active(t)]
    policy = p["track_policy"]
    spine = p["spine_objectives"]
    closed = p["closed_tracks"]

    verified = sorted(str(t["verified_at"]) for t in tracks if t.get("verified_at"))
    as_of = verified[-1] if verified else "(unset)"

    lines = [
        START,
        "",
        "<!-- GENERATED — do not hand-edit.",
        "     source-of-truth: docs/governance/ACTIVE_TRACK.yaml",
        "     render: python3 scripts/governance/render_active_track_includes.py",
        "     check:  python3 scripts/governance/render_active_track_includes.py --check",
        "     checked by: .github/workflows/active-track.yml, make docops-integrity,",
        "                 tests/test_active_track_governance.py",
        f"     newest track verified_at in source: {as_of} -->",
        "",
        f"**Active portfolio — declared intent only:** {len(active)} co-equal "
        f"track(s) (WIP warn {policy.get('warn_active')}, max "
        f"{policy.get('max_active')}; model: {policy.get('model')}). "
        "This stamped digest carries track identity and surface ownership, "
        "NOT runtime truth and NOT full track detail (descriptions, next-items, "
        "non-goals stay in the YAML). Declared intent comes from "
        "`docs/governance/ACTIVE_TRACK.yaml`; evaluate it with "
        "`python3 scripts/governance/check_track_status.py`. Never answer "
        "runtime or liveness questions from this block or another prose copy.",
        "",
    ]

    if spine:
        served = {t.get("serves") for t in active}
        gaps = [str(o.get("id")) for o in spine if o.get("id") not in served]
        objectives = ", ".join(f"`{o.get('id')}`" for o in spine)
        coverage = (
            f" — NO ACTIVE TRACK serves: {', '.join(gaps)}" if gaps
            else " (each covered by at least one active track)"
        )
        lines.append(f"**Spine objectives:** {objectives}{coverage}")
        lines.append("")

    if not tracks:
        lines.append("**Active track:** (none declared)")
        lines.append("")
    for t in tracks:
        _render_one_track(t, lines)
    if tracks:
        lines.append("")
        lines.append(
            "Before editing any file, check it against the `owns:` globs "
            "above — a surface owned by a track you are not serving is "
            "off-limits except through that track's own next-items. Full "
            "track detail: `docs/governance/ACTIVE_TRACK.yaml`."
        )
        lines.append("")

    if closed:
        lines.append("**Recently closed tracks:** " + " · ".join(
            f"`{ct.get('id')}` ({ct.get('status')}, closed {ct.get('closed_at')})"
            for ct in closed[:3]  # newest three; closed_tracks is newest-first
        ))
        lines.append("")

    lines.append("For machine-readable status, run "
                 "`python3 scripts/governance/check_track_status.py` — it writes "
                 "`reports/governance/active_track_evidence.md` (untracked; "
                 "derived status is not committed). CI publishes the latest "
                 "copy on the `generated/status` branch: "
                 "`git show origin/generated/status:"
                 "reports/governance/active_track_evidence.md`.")
    lines.append("")
    lines.append(END)
    return "\n".join(lines)


def render_block_relative(track: dict, doc_path: Path) -> str:
    """Render the managed block for a doc.

    The evidence pointer is now a regen command plus a generated/status branch
    reference (no repo-relative file link — the evidence files are untracked,
    so a path link would rot in any fresh checkout), so no per-doc relative
    path fixup is needed. Kept as the per-doc render hook.
    """
    del doc_path
    return render_block(track)


def update_file(path: Path, expected_block: str, *, check_only: bool) -> bool:
    """Return True if the file already matches; False if it needs an update."""
    if not path.exists():
        print(f"warning: {path} does not exist, skipping", file=sys.stderr)
        return True
    text = path.read_text(encoding="utf-8")
    match = BLOCK_RE.search(text)
    if not match:
        # No markers yet — append at end of file.
        new_text = text.rstrip() + "\n\n" + expected_block + "\n"
        ok = False
    else:
        existing = match.group(0)
        if existing == expected_block:
            return True
        new_text = text[:match.start()] + expected_block + text[match.end():]
        ok = False
    if check_only:
        if not ok:
            print(f"OUT OF DATE: {path}", file=sys.stderr)
            diff = difflib.unified_diff(
                text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"{path} (current)",
                tofile=f"{path} (expected)",
                n=2,
            )
            sys.stderr.writelines(diff)
        return ok
    path.write_text(new_text, encoding="utf-8")
    print(f"updated: {path}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="Exit non-zero if any managed block is out of date.")
    args = parser.parse_args()

    if not ACTIVE_TRACK_PATH.exists():
        print(f"error: {ACTIVE_TRACK_PATH} not found", file=sys.stderr)
        return 2

    track = load_active_track(ACTIVE_TRACK_PATH)
    if not track:
        print("error: ACTIVE_TRACK.yaml is empty or malformed", file=sys.stderr)
        return 2

    all_ok = True
    for path in MANAGED_FILES:
        block = render_block_relative(track, path)
        ok = update_file(path, block, check_only=args.check)
        all_ok = all_ok and ok

    if args.check and not all_ok:
        print("\nRun `python3 scripts/governance/render_active_track_includes.py` "
              "to rewrite the managed blocks.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
