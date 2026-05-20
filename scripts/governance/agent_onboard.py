#!/usr/bin/env python3
"""agent_onboard.py — the single door any human or agent uses to land in
the current operating reality of dharma_swarm.

This command does NOT own any fact. It reads from the existing owners
(ACTIVE_TRACK.yaml, ACTIVE_SURFACE_MANIFEST.yaml, LIVE_OPS_DASHBOARD.md,
BROKEN_REGISTER.md, SOVEREIGN_MANIFEST.md, git) and renders the current
truth in one screen.

Usage:
    python3 scripts/governance/agent_onboard.py
    make onboard

Exit code: always 0 on stale state. Warnings are surfaced inline. No CI
gate depends on this command — it is informational. Hard gates live in
scripts/governance/check_track_status.py, scripts/docops/, and the
existing CI workflows.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_JSON = REPO_ROOT / "reports/governance/active_track_evidence.json"
ACTIVE_TRACK = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"
LIVE_OPS = REPO_ROOT / "docs/state/LIVE_OPS_DASHBOARD.md"
BROKEN_REGISTER = REPO_ROOT / "docs/state/BROKEN_REGISTER.md"
SURFACE_MANIFEST = REPO_ROOT / "ACTIVE_SURFACE_MANIFEST.yaml"

# Soft-warning thresholds. Beyond these, surface a note. Never a gate.
LIVE_OPS_STALE_DAYS = 7
SURFACE_MANIFEST_STALE_DAYS = 30
KNOWN_DECAY_THRESHOLD_DAYS = 30

# Docs that have repeatedly misled agents in the past. Intentionally short;
# this is not a place to dump every doc.
KNOWN_DECAY_DOCS = [
    "docs/governance/BUILD_SESSION_ENTRYPOINT.md",
    "docs/plans/NEXT_10_SUBSTRATE_TODO.md",
    "docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md",
    "docs/plans/HANDOFF_ONTOLOGY_NATIVE_OPERATOR_BRIEF.md",
    "CYBERNETIC_LOOP_MAP.md",
    "reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md",
]


# ---------------------------------------------------------------------------
# Small helpers (stdlib-only)
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def git(*args: str, cwd: Path = REPO_ROOT) -> str:
    try:
        out = subprocess.check_output(
            ["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return out.rstrip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return ""


def _today() -> date:
    return datetime.now(tz=timezone.utc).date()


def _doc_staleness(doc_rel: str) -> tuple[int, str]:
    """Return (days_since_last_touch, last_commit_subject) for a doc."""
    last = git("log", "-1", "--format=%cI|%s", "--", doc_rel)
    if not last or "|" not in last:
        return (-1, "")
    iso, subject = last.split("|", 1)
    try:
        when = datetime.fromisoformat(iso).date()
    except ValueError:
        return (-1, subject)
    return ((_today() - when).days, subject)


# ---------------------------------------------------------------------------
# Section renderers (pure-ish; each returns nothing but prints)
# ---------------------------------------------------------------------------

def render_repo_state() -> None:
    section("DHARMA SWARM — AGENT ONBOARDING")
    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "(detached)"
    sha = git("rev-parse", "--short=10", "HEAD")
    head_msg = git("log", "-1", "--format=%ci %s")
    # Divergence from origin/main, if known
    ahead = git("rev-list", "--count", "origin/main..HEAD")
    behind = git("rev-list", "--count", "HEAD..origin/main")
    dirty = git("status", "--porcelain")
    dirty_count = len([ln for ln in dirty.splitlines() if ln.strip()])

    print(f"Branch       : {branch}")
    print(f"HEAD         : {sha}")
    print(f"Commit       : {head_msg}")
    if ahead or behind:
        ahead_n = ahead or "?"
        behind_n = behind or "?"
        print(f"vs origin/main: ahead {ahead_n}, behind {behind_n}")
    print(f"Dirty files  : {dirty_count}")
    print(f"Today (UTC)  : {_today().isoformat()}")


def render_active_track(evidence: dict[str, Any] | None,
                        track: dict[str, Any]) -> None:
    section("ACTIVE TRACK (owner: docs/governance/ACTIVE_TRACK.yaml)")
    if not evidence:
        print("  WARNING: no active_track_evidence.json found.")
        print("  Run: python3 scripts/governance/check_track_status.py")
        return

    block = (track or {}).get("active_track") or {}
    print(f"  ID         : {evidence.get('active_track_id', '(unknown)')}")
    if block.get("name"):
        print(f"  Name       : {block['name']}")
    if block.get("status"):
        print(f"  Status     : {block['status']}")
    if block.get("verified_at") and block.get("ttl_days"):
        try:
            verified = date.fromisoformat(str(block["verified_at"]))
            age = (_today() - verified).days
            ttl = int(block["ttl_days"])
            remaining = ttl - age
            tag = "OK" if remaining >= 0 else f"OVERDUE by {-remaining}d"
            print(f"  TTL        : {age}/{ttl} days used ({tag})")
        except (ValueError, TypeError):
            pass
    progress = evidence.get("completion_progress", {"passed": 0, "total": 0})
    print(f"  Prereqs    : {'OK' if evidence.get('prerequisites_ok') else 'FAILED'}")
    print(f"  Completion : {progress['passed']}/{progress['total']}")
    shippable = evidence.get("shippable", False)
    print(f"  Shippable  : {'YES — declare next track' if shippable else 'no'}")

    print()
    print("  Acceptance criteria:")
    for c in evidence.get("criteria", []):
        mark = "✓" if c.get("passed") else "✗"
        print(f"    {mark} [{c.get('kind')}] {c.get('id')}")
        if not c.get("passed"):
            print(f"        {c.get('detail', '')}")


def render_live_ops() -> None:
    section("LIVE OPS SNAPSHOT (owner: docs/state/LIVE_OPS_DASHBOARD.md)")
    if not LIVE_OPS.exists():
        print("  MISSING — LIVE_OPS_DASHBOARD.md not found")
        return
    days, _subj = _doc_staleness("docs/state/LIVE_OPS_DASHBOARD.md")
    text = LIVE_OPS.read_text(encoding="utf-8", errors="replace")
    snap_match = re.search(r"\*\*Snapshot date:\*\*\s*([\d\-]+)", text)
    snapshot = snap_match.group(1) if snap_match else "(unknown)"
    status_match = re.search(r"\*\*Status:\*\*\s*([^\n]+)", text)
    status = status_match.group(1).strip() if status_match else "(unknown)"
    print(f"  Snapshot date : {snapshot}")
    print(f"  Status        : {status}")
    if days >= 0:
        tag = "stale" if days > LIVE_OPS_STALE_DAYS else "fresh"
        print(f"  Last git touch: {days}d ago ({tag} threshold {LIVE_OPS_STALE_DAYS}d)")
        if days > LIVE_OPS_STALE_DAYS:
            print("  NOTE: dashboard prose may lag reality. Trust git log + this command.")


def render_manifest_health() -> None:
    section("SURFACE MANIFEST HEALTH (owner: ACTIVE_SURFACE_MANIFEST.yaml)")
    if not SURFACE_MANIFEST.exists():
        print("  MISSING — ACTIVE_SURFACE_MANIFEST.yaml not found")
        return
    days, _ = _doc_staleness("ACTIVE_SURFACE_MANIFEST.yaml")
    if days >= 0:
        tag = "stale" if days > SURFACE_MANIFEST_STALE_DAYS else "fresh"
        print(f"  Last git touch: {days}d ago ({tag})")

    # Try to call manifest_health.build_health_report() if importable
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from dharma_swarm.manifest_health import build_health_report  # type: ignore
        report = build_health_report()
        entities = report.get("entities", []) if isinstance(report, dict) else []
        green = sum(1 for e in entities if e.get("status") == "green")
        yellow = sum(1 for e in entities if e.get("status") == "yellow")
        red = sum(1 for e in entities if e.get("status") == "red")
        print(f"  Health        : green={green} yellow={yellow} red={red}")
        if red:
            print("  Top RED entities:")
            for e in [e for e in entities if e.get("status") == "red"][:5]:
                print(f"    - {e.get('id', '?')}: {e.get('gap', '')}")
    except Exception as exc:  # pragma: no cover — informational only
        print(f"  (manifest_health unavailable: {type(exc).__name__})")


def _parse_broken_register() -> dict[str, Any]:
    """Return summary counts and top open BR items."""
    if not BROKEN_REGISTER.exists():
        return {"present": False}
    text = BROKEN_REGISTER.read_text(encoding="utf-8", errors="replace")

    # Split by H3 BR headings, then look at each block's status line.
    blocks = re.split(r"(?m)^### (BR-\d+[^\n]*)\n", text)
    # blocks = [pre, heading1, body1, heading2, body2, ...]
    items = []
    for i in range(1, len(blocks), 2):
        heading = blocks[i].strip()
        body = blocks[i + 1] if i + 1 < len(blocks) else ""
        status_match = re.search(r"\*\*status:\*\*\s*([^\n]+)", body, re.IGNORECASE)
        status = status_match.group(1).strip() if status_match else ""
        # First UPPERCASE word of status (OPEN, PARTIAL, FIXED, CLOSED, ...).
        # Strip leading bold markers / punctuation.
        cleaned = re.sub(r"^[\W_]+", "", status)
        word_match = re.match(r"[A-Z_]+", cleaned)
        status_word = word_match.group(0) if word_match else "UNKNOWN"
        items.append({"heading": heading, "status_word": status_word, "status": status})

    open_like = [it for it in items if it["status_word"] in {"OPEN", "PARTIAL", "INVESTIGATING", "WORKAROUND"}]
    closed_like = [it for it in items if it["status_word"] in {"FIXED", "CLOSED"}]
    return {
        "present": True,
        "total": len(items),
        "open_count": len(open_like),
        "closed_count": len(closed_like),
        "top_open": open_like[:3],
    }


def render_broken_register() -> None:
    section("BROKEN REGISTER (owner: docs/state/BROKEN_REGISTER.md)")
    info = _parse_broken_register()
    if not info.get("present"):
        print("  MISSING — BROKEN_REGISTER.md not found")
        return
    print(f"  Items: total={info['total']} open-like={info['open_count']} closed-like={info['closed_count']}")
    top = info.get("top_open") or []
    if top:
        print("  Top open items:")
        for it in top:
            print(f"    - [{it['status_word']}] {it['heading']}")


def render_axioms() -> None:
    section("LIVING AXIOMS (owner: docs/governance/SOVEREIGN_MANIFEST.md)")
    print("  A1 — No new files at top level of dharma_swarm/")
    print("  A2 — No new duplicate bridge/router/adapter/orchestrator")
    print("  A3 — Update NAVIGATION.md for any new seam")
    print("  A4 — No vibe-coding (find the file before guessing the API)")
    print("  A5 — No god objects (files >3000 LOC)")
    print("  A6 — Docs decay; verify numbers before citing")
    print("  A7 — No new circular imports")
    print("  A8 — Frontmatter discipline (no YAML in governance prose)")


def render_recent_activity(track: dict[str, Any]) -> None:
    surfaces = (track.get("active_track") or {}).get("surfaces", []) if track else []
    if not surfaces:
        return
    section(f"RECENT TRACK ACTIVITY (last 14 days, {len(surfaces)} surfaces)")
    since = (_today() - timedelta(days=14)).isoformat()
    args = ["log", "--since", since, "--oneline", "--no-merges", "--"]
    for surface in surfaces:
        args.append(surface.replace("/**", ""))
    out = git(*args)
    commits = out.splitlines() if out else []
    if commits:
        for line in commits[:15]:
            print(f"  {line}")
        if len(commits) > 15:
            print(f"  ... ({len(commits) - 15} more)")
    else:
        print("  (no commits in the window — the track may be paused)")


def render_decay_watch() -> None:
    section("KNOWN-DECAY DOCS — verify before citing")
    for doc in KNOWN_DECAY_DOCS:
        days, _subj = _doc_staleness(doc)
        if days < 0:
            tag = "MISSING"
        elif days > KNOWN_DECAY_THRESHOLD_DAYS:
            tag = f"STALE ({days}d since last touch)"
        else:
            tag = f"recent ({days}d)"
        print(f"  [{tag}] {doc}")


def render_tooling_first() -> None:
    section("TOOLING-FIRST CONTEXT PASS")
    print("  Before grep/read-heavy investigation in dharma_swarm, prefer:")
    print("  - make onboard")
    print("  - xray.py / make xray                   — repo overview")
    print("  - GitNexus impact/context                — blast radius, callers/callees")
    print("  - Context+ MCP semantic search           — blast radius where available")
    print("  - ast-grep                               — structural search")
    print("  - radon                                  — complexity hotspots")
    print("  - grimp                                  — import graph / dependency truth")
    print("  - vulture + ruff F401/F811               — dead-code / import rot")
    print("  - lint-imports                           — advisory unless contracts green")


def render_enforcement_and_depth() -> None:
    section("ENFORCEMENT (run before opening a PR)")
    print("  make docops-integrity      # documentation invariants")
    print("  make governance-all        # full governance gate bundle")
    print("  python3 scripts/governance/check_track_status.py")
    print("  python3 scripts/governance/render_active_track_includes.py --check")
    section("DEPTH POINTERS (read on demand, not in order)")
    print("  Repo rules & behaviour : CLAUDE.md, AGENTS.md, docs/AGENTS.md")
    print("  Anti-slop rules        : docs/governance/ANTI_SLOP_RULES.md")
    print("  Doc ownership map      : docs/governance/CANONICAL_DOC_STACK.md")
    print("  Architecture/doctrine  : docs/governance/SOVEREIGN_MANIFEST.md, docs/doctrine/")
    print("  Coherence Delta        : docs/governance/COHERENCE_DELTA.md")
    print("  Daily/work loops       : docs/governance/AGENTOPS.md, KAIZENOPS.md, DAILY_OPERATING_BRIEF.md")


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_evidence() -> dict[str, Any] | None:
    if not EVIDENCE_JSON.exists():
        return None
    try:
        return json.loads(EVIDENCE_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _refresh_evidence() -> None:
    """Re-run check_track_status to make sure the evidence is current."""
    script = REPO_ROOT / "scripts/governance/check_track_status.py"
    if not script.exists():
        return
    try:
        subprocess.run([sys.executable, str(script), "--warn-only"],
                       cwd=REPO_ROOT, capture_output=True, timeout=30)
    except (subprocess.TimeoutExpired, OSError):
        pass


def _load_track_yaml() -> dict[str, Any]:
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from check_track_status import load_active_track  # type: ignore
        return load_active_track(ACTIVE_TRACK) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    os.chdir(REPO_ROOT)
    _refresh_evidence()
    evidence = _load_evidence()
    track = _load_track_yaml()

    render_repo_state()
    render_active_track(evidence, track)
    render_live_ops()
    render_manifest_health()
    render_broken_register()
    render_axioms()
    render_recent_activity(track)
    render_decay_watch()
    render_tooling_first()
    render_enforcement_and_depth()

    section("WHAT TO DO NEXT")
    block = (track or {}).get("active_track") or {}
    next_items = block.get("next_items", []) if block else []
    prereqs_ok = bool(evidence and evidence.get("prerequisites_ok"))
    shippable = bool(evidence and evidence.get("shippable"))
    if not prereqs_ok:
        print("  Prerequisites are failing. The active track is mis-declared.")
        print("  Fix the YAML or re-open the previous track.")
    elif shippable:
        print("  All completion criteria pass. Close this track and declare the next.")
        print("  Edit docs/governance/ACTIVE_TRACK.yaml:")
        print("    - move active_track block to closed_tracks")
        print("    - declare the new active_track block")
        print("  Run: python3 scripts/governance/render_active_track_includes.py")
    elif next_items:
        print("  Pick from next_items in ACTIVE_TRACK.yaml. Suggested order:")
        for item in next_items[:5]:
            tag = " (blocker)" if item.get("blocker") else ""
            print(f"    - [{item.get('kind', '?')}]{tag} {item.get('what', '')[:80]}")
    else:
        print("  No next_items declared. Add to ACTIVE_TRACK.yaml or pick from BR-* open items.")
    print()
    print("  Reminder: this command renders the owners; it does not own any fact.")
    print("  When in doubt: trust the filesystem, git log, and ACTIVE_TRACK.yaml.")

    # Informational tool. Always exit 0.
    return 0


if __name__ == "__main__":
    sys.exit(main())
