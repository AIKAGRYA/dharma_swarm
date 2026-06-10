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
    Path("docs/governance/BUILD_SESSION_ENTRYPOINT.md"),
]


def _render_one_track(t: dict, lines: list) -> None:
    """Render a single track's block into `lines` (used per active track)."""
    lines.append(f"### {t.get('name', '(unnamed)')}")
    lines.append("")
    lines.append(f"**Track id:** `{t.get('id', '(none)')}` · "
                 f"**Status:** {t.get('status', 'UNKNOWN')} · "
                 f"**Owner:** {t.get('owner', '(unset)')}")
    lines.append(f"**Serves spine objective:** `{t.get('serves', '(none)')}` · "
                 f"**Verified at:** {t.get('verified_at', '(unset)')} "
                 f"(TTL {t.get('ttl_days', 14)} days)")
    edges = []
    for kind in ("complements", "depends_on", "conflicts_with"):
        vals = t.get(kind) or []
        if vals:
            edges.append(f"{kind}: {', '.join(str(v) for v in vals)}")
    if edges:
        lines.append(f"**Relations:** {' · '.join(edges)}")
    owned = t.get("owned_surfaces") or []
    if owned:
        lines.append(f"**Owns surfaces:** {', '.join(str(s) for s in owned)}")
    moves = t.get("moves_vital_signs") or []
    if moves:
        lines.append(f"**Moves vital signs:** {', '.join(str(s) for s in moves)}")
    lines.append("")
    desc = (t.get("description") or "").strip()
    if desc:
        lines.extend(desc.splitlines())
        lines.append("")
    next_items = t.get("next_items") or []
    if next_items:
        lines.append("**Next items:**")
        lines.append("")
        for item in next_items:
            tag = " (blocker)" if item.get("blocker") else ""
            lines.append(f"- [{item.get('kind', '?')}]{tag} {str(item.get('what', '')).strip()}")
        lines.append("")
    non_goals = t.get("non_goals") or []
    if non_goals:
        lines.append("**Non-goals:**")
        lines.append("")
        for ng in non_goals:
            lines.append(f"- {str(ng).strip()}")
        lines.append("")


def render_block(track: dict) -> str:
    """Render the managed governance block from the track portfolio.

    Works for both schemas: normalize_portfolio adapts v1 (singular
    active_track) into a one-track portfolio, so this renders either.
    """
    p = normalize_portfolio(track)
    tracks = p["active_tracks"]
    active = [t for t in tracks if _is_active(t)]
    policy = p["track_policy"]
    spine = p["spine_objectives"]
    closed = p["closed_tracks"]

    lines = [
        START,
        "",
        "<!-- This block is generated from docs/governance/ACTIVE_TRACK.yaml.",
        "     Do not hand-edit. Run scripts/governance/render_active_track_includes.py",
        "     after updating the YAML. -->",
        "",
        f"**Active portfolio:** {len(active)} co-equal track(s) "
        f"(WIP warn {policy.get('warn_active')}, max {policy.get('max_active')}). "
        "A new project is a new track here, not a violation — "
        f"model: {policy.get('model')}.",
        "",
    ]

    if spine:
        served = {t.get("serves") for t in active}
        lines.append("**Spine objectives (each track serves one):**")
        lines.append("")
        for o in spine:
            oid = o.get("id")
            mark = "covered" if oid in served else "**no active track**"
            lines.append(f"- `{oid}` — {o.get('name', '')} ({mark})")
        lines.append("")

    if not tracks:
        lines.append("**Active track:** (none declared)")
        lines.append("")
    for t in tracks:
        _render_one_track(t, lines)

    if closed:
        lines.append("**Recently closed tracks:**")
        lines.append("")
        for ct in closed[:3]:  # newest three; closed_tracks is newest-first
            lines.append(
                f"- `{ct.get('id')}` — {ct.get('name')} "
                f"({ct.get('status')}, closed {ct.get('closed_at')})"
            )
        lines.append("")

    lines.append("For machine-readable status, see "
                 "[`reports/governance/active_track_evidence.md`]"
                 "(../../reports/governance/active_track_evidence.md) "
                 "(generated by `scripts/governance/check_track_status.py`).")
    lines.append("")
    lines.append(END)
    return "\n".join(lines)


def render_block_relative(track: dict, doc_path: Path) -> str:
    """Render with a relative path link to the evidence file based on doc location."""
    depth = len(doc_path.parts) - 1  # number of directories above repo root
    rel_prefix = "../" * depth
    block = render_block(track)
    return block.replace("../../reports/governance/active_track_evidence.md",
                         f"{rel_prefix}reports/governance/active_track_evidence.md")


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
