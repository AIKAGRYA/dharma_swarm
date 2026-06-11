#!/usr/bin/env python3
"""agent_onboard.py — the single door any human or agent uses to land in
the current operating reality of dharma_swarm.

This command does NOT own any fact. It reads from the existing owners
(ACTIVE_TRACK.yaml, ACTIVE_SURFACE_MANIFEST.yaml, LIVE_OPS_DASHBOARD.md,
BROKEN_REGISTER.md, SOVEREIGN_MANIFEST.md, git) and renders the current
truth in one screen.

Usage:
    python3 scripts/governance/agent_onboard.py            # full picture
    python3 scripts/governance/agent_onboard.py --fast     # <5s, skips slow probes
    python3 scripts/governance/agent_onboard.py --json     # machine receipt to stdout
    python3 scripts/governance/agent_onboard.py --no-net   # skip network (gh) calls
    make onboard

Every run also tees a machine-readable receipt to
~/.dharma/ops/onboard_receipt.json (override dir: DHARMA_OPS_DIR) so fleet
agents (hermes-m5, loops, VPS workers) can consume operating reality
without executing this script. The receipt is a projection, not authority.

Write behavior: this command never writes owner files. When the generated
evidence (reports/governance/active_track_evidence.json) is missing or
older than 60 minutes, it invokes check_track_status.py — the evidence
OWNER — which regenerates the tracked evidence reports (this can dirty
the working tree, same as the governance loop does). Suppress with
AGENT_ONBOARD_NO_REFRESH=1 or --fast; force with AGENT_ONBOARD_REFRESH=1.

Exit code: always 0 on stale state. Warnings are surfaced inline. No CI
gate depends on this command — it is informational. Hard gates live in
scripts/governance/check_track_status.py, scripts/docops/, and the
existing CI workflows.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
# One explicit path insert so dharma_swarm imports resolve to THIS worktree's
# package, not whichever checkout an editable install happens to point at.
# (Previously a hidden insert inside render_manifest_health was load-bearing.)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
EVIDENCE_JSON = REPO_ROOT / "reports/governance/active_track_evidence.json"
ACTIVE_TRACK = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"
LIVE_OPS = REPO_ROOT / "docs/state/LIVE_OPS_DASHBOARD.md"
BROKEN_REGISTER = REPO_ROOT / "docs/state/BROKEN_REGISTER.md"
SURFACE_MANIFEST = REPO_ROOT / "ACTIVE_SURFACE_MANIFEST.yaml"

# Soft-warning thresholds. Beyond these, surface a note. Never a gate.
LIVE_OPS_STALE_DAYS = 7
SURFACE_MANIFEST_STALE_DAYS = 30
KNOWN_DECAY_THRESHOLD_DAYS = 30
EVIDENCE_STALE_MINUTES = 60


def _ops_dir() -> Path:
    """Fleet-readable state dir for machine receipts (same home as the
    live process census receipt this script already reads)."""
    override = os.environ.get("DHARMA_OPS_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".dharma" / "ops"


ONBOARD_RECEIPT_NAME = "onboard_receipt.json"

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


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _strip_ref_prefix(branch: str | None) -> str | None:
    if not branch:
        return None
    prefix = "refs/heads/"
    return branch[len(prefix):] if branch.startswith(prefix) else branch


def _parse_worktree_porcelain(text: str) -> list[dict[str, Any]]:
    worktrees: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            if current is not None:
                worktrees.append(current)
                current = None
            continue
        if line.startswith("worktree "):
            if current is not None:
                worktrees.append(current)
            current = {
                "path": line[len("worktree "):].strip(),
                "head": None,
                "branch": None,
                "detached": False,
                "bare": False,
                "locked": False,
                "prunable": False,
            }
            continue
        if current is None:
            continue
        if line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):].strip()
        elif line.startswith("branch "):
            current["branch"] = _strip_ref_prefix(line[len("branch "):].strip())
        elif line == "detached":
            current["detached"] = True
        elif line == "bare":
            current["bare"] = True
        elif line.startswith("locked"):
            current["locked"] = True
        elif line.startswith("prunable"):
            current["prunable"] = True
    if current is not None:
        worktrees.append(current)
    return worktrees


def _lane_family(label: str) -> str:
    text = label.lower()
    if "forge" in text or "arena" in text or "measurement" in text:
        return "forge/measurement"
    if "living_agent_kernel" in text or "living-agent-kernel" in text:
        return "living-agent-kernel"
    if "runtime-truth" in text or "runtime_truth" in text or "spine" in text:
        return "runtime-truth/spine"
    if "docops" in text or "governance" in text:
        return "docops/governance"
    if "capital" in text or "revenue" in text or "cash" in text:
        return "capital/revenue"
    if re.search(r"(?:^|[-_/])pr(?:[-_/\d]|$)", text) or "review" in text or "merge-master" in text:
        return "pr/review/merge"
    if "cleanup" in text or "repair" in text:
        return "cleanup/repair"
    if "goodworks" in text or "dgm" in text:
        return "goodworks"
    return "other"


def _recent_local_branches(limit: int = 8) -> list[dict[str, str]]:
    out = git(
        "for-each-ref",
        "--sort=-committerdate",
        "--format=%(refname:short)|%(committerdate:short)|%(subject)",
        "refs/heads",
    )
    branches: list[dict[str, str]] = []
    for line in out.splitlines():
        name, sep, rest = line.partition("|")
        if not sep:
            continue
        date_s, _, subject = rest.partition("|")
        branches.append({"name": name, "date": date_s, "subject": subject})
        if len(branches) >= limit:
            break
    return branches


def _work_lane_snapshot() -> dict[str, Any]:
    worktree_text = git("worktree", "list", "--porcelain")
    worktrees = _parse_worktree_porcelain(worktree_text) if worktree_text else []
    for w in worktrees:
        path = Path(str(w.get("path", "")))
        w["exists"] = path.exists()
        w["basename"] = path.name

    branch_text = git("for-each-ref", "--format=%(refname:short)", "refs/heads")
    local_branches = [line.strip() for line in branch_text.splitlines() if line.strip()]
    worktree_labels = [
        " ".join(
            str(part) for part in (w.get("basename"), w.get("branch")) if part
        )
        for w in worktrees
    ]
    family_counts = Counter(_lane_family(label) for label in [*local_branches, *worktree_labels])
    return {
        "worktrees": worktrees,
        "local_branch_count": len(local_branches),
        "recent_branches": _recent_local_branches(),
        "family_counts": family_counts,
    }


# ---------------------------------------------------------------------------
# Section renderers (pure-ish; each returns nothing but prints)
# ---------------------------------------------------------------------------

def render_repo_state(*, fast: bool = False) -> dict[str, Any]:
    section("DHARMA SWARM — AGENT ONBOARDING")
    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "(detached)"
    sha = git("rev-parse", "--short=10", "HEAD")
    head_msg = git("log", "-1", "--format=%ci %s")
    # Divergence from origin/main, if known
    ahead = git("rev-list", "--count", "origin/main..HEAD")
    behind = git("rev-list", "--count", "HEAD..origin/main")
    dirty_count: int | None
    dirty_dirs: list[tuple[str, int]] = []
    if fast:
        dirty_count = None  # git status over a big dirty tree is the slow part
    else:
        dirty = git("status", "--porcelain")
        dirty_lines = [ln for ln in dirty.splitlines() if ln.strip()]
        dirty_count = len(dirty_lines)
        dir_counts: Counter[str] = Counter()
        for ln in dirty_lines:
            rel = ln[3:].strip().strip('"')
            parent = str(Path(rel).parent)
            dir_counts[parent] += 1
        dirty_dirs = dir_counts.most_common(3)

    print(f"Worktree     : {REPO_ROOT}  (this checkout — symbols may be mirrored in sibling worktrees)")
    print(f"Branch       : {branch}")
    print(f"HEAD         : {sha}")
    print(f"Commit       : {head_msg}")
    if ahead or behind:
        ahead_n = ahead or "?"
        behind_n = behind or "?"
        print(f"vs origin/main: ahead {ahead_n}, behind {behind_n}")
    if dirty_count is None:
        print("Dirty files  : (skipped — --fast)")
    else:
        breakdown = ""
        if dirty_dirs:
            breakdown = "  (top: " + ", ".join(f"{d}={n}" for d, n in dirty_dirs) + ")"
        print(f"Dirty files  : {dirty_count}{breakdown}")
    print(f"Today (UTC)  : {_today().isoformat()}  (commit timestamps may show local +0900)")
    print()
    print("Remember only: make onboard")
    if dirty_count:
        print("Next command : make agent-build-closeout  # before PR/merge handoff")
    elif dirty_count == 0:
        print("Next command : make agent-build-preflight # before editing")
    print("If unsure    : rerun make onboard (or --fast); it repeats the next command")
    return {
        "worktree": str(REPO_ROOT),
        "branch": branch,
        "head": sha,
        "ahead": ahead or None,
        "behind": behind or None,
        "dirty_files": dirty_count,
        "dirty_top_dirs": dict(dirty_dirs),
    }


def render_parallel_work_lanes() -> dict[str, Any]:
    """Live git/worktree inventory so 0..N parallel builds can coordinate.

    Completes the intent of commit cf11a80f8 (parallel_lane_policy): the
    helpers landed there but this render function never did. Reads only
    git state; owns no fact.
    """
    section("PARALLEL WORK LANES — who else is building (owner: git worktree/branches)")
    snap = _work_lane_snapshot()
    worktrees = snap.get("worktrees") or []
    print(f"  Worktrees: {len(worktrees)}  ·  Local branches: {snap.get('local_branch_count', 0)}")
    here = str(REPO_ROOT)
    for w in worktrees[:12]:
        marker = "▶" if str(w.get("path")) == here else " "
        flags = "".join(
            tag for tag, on in (
                (" [detached]", w.get("detached")),
                (" [locked]", w.get("locked")),
                (" [prunable]", w.get("prunable")),
                (" [MISSING]", not w.get("exists")),
            ) if on
        )
        print(f"  {marker} {w.get('basename', '?')}  branch={w.get('branch') or '(none)'}{flags}")
    if len(worktrees) > 12:
        print(f"    ... ({len(worktrees) - 12} more — `git worktree list`)")
    families = snap.get("family_counts") or {}
    if families:
        fam = ", ".join(f"{k}={v}" for k, v in sorted(families.items(), key=lambda kv: -kv[1]))
        print(f"  Lane families: {fam}")
    recent = snap.get("recent_branches") or []
    if recent:
        print("  Most recent branches:")
        for b in recent[:5]:
            print(f"    - {b['name']}  ({b['date']})  {b['subject'][:60]}")
    print("  Before editing a hot-path symbol: it may exist in several worktrees.")
    print("  Policy: parallel lanes are allowed; non-overlapping surfaces are the boundary.")
    return {
        "worktree_count": len(worktrees),
        "local_branch_count": snap.get("local_branch_count", 0),
        "worktrees": [
            {"basename": w.get("basename"), "branch": w.get("branch"),
             "exists": w.get("exists"), "prunable": w.get("prunable")}
            for w in worktrees
        ],
        "lane_families": dict(families),
    }


def _evidence_age_minutes(evidence: dict[str, Any] | None) -> float | None:
    """Age of the evidence snapshot in minutes, or None if undatable."""
    raw = (evidence or {}).get("generated_at")
    when: datetime | None = None
    if isinstance(raw, str):
        try:
            when = datetime.fromisoformat(raw)
        except ValueError:
            when = None
    if when is None and EVIDENCE_JSON.exists():
        try:
            when = datetime.fromtimestamp(EVIDENCE_JSON.stat().st_mtime, tz=timezone.utc)
        except OSError:
            return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    # Clamp: a future generated_at (clock skew) must not render a giant
    # negative age — treat as 0 (fresh).
    return max(0.0, (datetime.now(tz=timezone.utc) - when).total_seconds() / 60.0)


def render_active_track(evidence: dict[str, Any] | None,
                        track: dict[str, Any]) -> None:
    section("ACTIVE PORTFOLIO (owner: docs/governance/ACTIVE_TRACK.yaml)")
    if not evidence:
        print("  WARNING: no active_track_evidence.json found.")
        print("  Run: python3 scripts/governance/check_track_status.py")
        return

    age_min = _evidence_age_minutes(evidence)
    if age_min is not None:
        if age_min > EVIDENCE_STALE_MINUTES:
            print(f"  ⚠ Evidence snapshot is {age_min/60:.1f}h old — criteria below may lag reality.")
            print("    Refresh: python3 scripts/governance/check_track_status.py")
        else:
            print(f"  Evidence age: {age_min:.0f}m (fresh)")

    # v2: a portfolio of 1..N co-equal active tracks. Render them all, not just
    # the primary — so an agent never reads "there is one active track".
    active_tracks = evidence.get("active_tracks")
    summary = evidence.get("portfolio_summary") or {}
    if active_tracks:
        n = summary.get("active", len(active_tracks))
        print(f"  {n} co-equal active track(s) "
              f"(WIP warn {summary.get('warn_active')}, max {summary.get('max_active')}). "
              "A new project is a NEW TRACK here, not a violation.")
        coverage = evidence.get("spine_coverage") or {}
        if coverage:
            covered = [k for k, v in coverage.items() if v]
            gaps = [k for k, v in coverage.items() if not v]
            print(f"  Spine coverage: {', '.join(covered) or '(none)'}"
                  + (f"  ·  GAPS (no active track): {', '.join(gaps)}" if gaps else ""))
        for t in active_tracks:
            cp = t.get("completion_progress", {"passed": 0, "total": 0})
            flag = "SHIPPABLE" if t.get("shippable") else f"{cp['passed']}/{cp['total']}"
            print()
            print(f"  • {t.get('id')}  [{t.get('status')}]  serves={t.get('serves')}  ({flag})")
            edges = [f"{k}={t.get(k)}" for k in ("complements", "depends_on", "conflicts_with") if t.get(k)]
            if edges:
                print(f"      {'  '.join(edges)}")
            for c in t.get("criteria", []):
                mark = "✓" if c.get("passed") else "✗"
                line = f"      {mark} [{c.get('kind')}] {c.get('id')}"
                print(line if c.get("passed") else line + f"  — {c.get('detail', '')}")
        print()
        print("  To OPEN A NEW TRACK (when the operator proposes a project): add an entry")
        print("  under `active_tracks:` in docs/governance/ACTIVE_TRACK.yaml with serves:")
        print("  <spine objective>, owned_surfaces:, and acceptance criteria; then run")
        print("  `python3 scripts/governance/render_active_track_includes.py`. Up to "
              f"{summary.get('max_active', 10)} may run concurrently with non-overlapping surfaces.")
        return

    # v1 back-compat: single active_track block.
    block = (track or {}).get("active_track") or {}
    print(f"  ID         : {evidence.get('active_track_id', '(unknown)')}")
    if block.get("name"):
        print(f"  Name       : {block['name']}")
    if block.get("status"):
        print(f"  Status     : {block['status']}")
    progress = evidence.get("completion_progress", {"passed": 0, "total": 0})
    print(f"  Prereqs    : {'OK' if evidence.get('prerequisites_ok') else 'FAILED'}")
    print(f"  Completion : {progress['passed']}/{progress['total']}")
    shippable = evidence.get("shippable", False)
    print(f"  Shippable  : {'YES' if shippable else 'no'}")
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


def render_live_ops_cockpit() -> None:
    section("LIVE OPS COCKPIT — READ-ONLY OPERATIONS CONTROL")
    runbook = REPO_ROOT / "docs/ops/LIVE_OPS_COCKPIT.md"
    census_script = REPO_ROOT / "scripts/runtime/live_ops_census.py"
    cockpit_page = REPO_ROOT / "dashboard/src/app/dashboard/cockpit/page.tsx"
    receipt = Path.home() / ".dharma/ops/live_process_census.json"
    nats_spec = REPO_ROOT / "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"
    tmux_spec = REPO_ROOT / "docs/ops/TMUX_AGENT_SUBSTRATE.md"

    print(f"  Runbook       : {'present' if runbook.exists() else 'missing'} docs/ops/LIVE_OPS_COCKPIT.md")
    print(f"  Census script : {'present' if census_script.exists() else 'missing'} scripts/runtime/live_ops_census.py")
    print(f"  Dashboard     : {'present' if cockpit_page.exists() else 'missing'} /dashboard/cockpit")
    print(f"  NATS spec     : {'present' if nats_spec.exists() else 'missing'} docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md")
    print(f"  tmux spec     : {'present' if tmux_spec.exists() else 'missing'} docs/ops/TMUX_AGENT_SUBSTRATE.md")
    if receipt.exists():
        try:
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            summary = payload.get("summary", {})
            print(f"  Receipt       : present {receipt}")
            print(f"  Surfaces      : {summary.get('total', '?')} total; status={summary.get('by_status', {})}")
            print(f"  Operator gates: {summary.get('human_authority_required', '?')} require John")
            print(f"  VPS candidates: {summary.get('vps_candidates', '?')}")
        except (OSError, json.JSONDecodeError):
            print(f"  Receipt       : unreadable {receipt}")
    else:
        print("  Receipt       : missing — run python3 scripts/runtime/live_ops_census.py --write")
    print("  Authority     : read-only; shows commands/policies but executes nothing")


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
        print(f"  (manifest_health unavailable: {type(exc).__name__}: {exc})")


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


# Fallback only — the live list is parsed from SOVEREIGN_MANIFEST.md at
# render time so a new/reworded axiom can never drift invisibly here.
_AXIOM_FALLBACK = [
    "A1 — No new files at top level of dharma_swarm/",
    "A2 — No new duplicate bridge/router/adapter/orchestrator",
    "A3 — Update NAVIGATION.md for any new seam",
    "A4 — No vibe-coding (find the file before guessing the API)",
    "A5 — No god objects (files >3000 LOC)",
    "A6 — Docs decay; verify numbers before citing",
    "A7 — No new circular imports",
    "A8 — Frontmatter discipline (no YAML in governance prose)",
]


def _parse_axioms_from_manifest() -> list[str]:
    manifest = REPO_ROOT / "docs/governance/SOVEREIGN_MANIFEST.md"
    if not manifest.exists():
        return []
    try:
        text = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    found = re.findall(r"(?m)^#{2,4}\s*(A\d+)\s*[:—-]\s*([^\n]+)", text)
    return [f"{aid} — {title.strip().rstrip('*').strip()}" for aid, title in found]


def render_axioms() -> None:
    section("LIVING AXIOMS (owner: docs/governance/SOVEREIGN_MANIFEST.md)")
    axioms = _parse_axioms_from_manifest()
    if axioms:
        for line in axioms:
            print(f"  {line}")
    else:
        print("  (could not parse axioms from SOVEREIGN_MANIFEST.md — static fallback,")
        print("   verify against the manifest before relying on these)")
        for line in _AXIOM_FALLBACK:
            print(f"  {line}")


def _all_track_surfaces(track: dict[str, Any]) -> list[str]:
    """Surfaces across ALL active tracks. v2 uses `owned_surfaces`; v1 used
    `surfaces`. (The v1-only read silently killed this section when the v2
    portfolio shipped — read both, across the whole portfolio.)"""
    if not track:
        return []
    tracks = track.get("active_tracks") or []
    if not tracks and track.get("active_track"):
        tracks = [track["active_track"]]
    surfaces: list[str] = []
    for t in tracks:
        if not isinstance(t, dict):
            continue
        for s in (t.get("owned_surfaces") or t.get("surfaces") or []):
            if s not in surfaces:
                surfaces.append(s)
    return surfaces


def render_recent_activity(track: dict[str, Any]) -> None:
    surfaces = _all_track_surfaces(track)
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


def render_spine_status() -> None:
    """Surface the correlation_spine declaration to operators.

    Reads from the existing owners only (ACTIVE_SURFACE_MANIFEST.yaml plus
    on-disk file presence and the live runtime.db). Does not own any fact;
    does not gate anything. Always exits 0 — informational, matching the
    rest of agent_onboard.

    Per PR A.5 doctrine: receipts may differ by closure layer, correlation
    identity must not. This section makes the layer map visible at every
    build-session boot so operators don't accidentally introduce a fourth
    receipt without declaring it here.

    Three rendering passes:
      1. Declared layers (read from manifest correlation_spine.layers)
      2. Schema introspection (does receipt_json column exist in DDL?)
      3. Live DB stats (receipt fill-rate on delegation_runs, if DB present)

    Pass (1) is the doctrinal map. Passes (2) and (3) close the
    declared-vs-actual gap by checking what the live system reports back.
    Together they form a cybernetic loop: declare → observe → reconcile.
    """
    section("CORRELATION SPINE — closure layers and canonical receipts")
    layers: list[dict[str, Any]] = []
    invariant: str | None = None
    try:
        import yaml  # type: ignore

        if SURFACE_MANIFEST.exists():
            data = yaml.safe_load(SURFACE_MANIFEST.read_text(encoding="utf-8")) or {}
            spine = data.get("correlation_spine") or {}
            layers = spine.get("layers", []) or []
            invariant = spine.get("invariant")
    except Exception as exc:  # pragma: no cover — informational only
        print(f"  (could not parse ACTIVE_SURFACE_MANIFEST.yaml correlation_spine: {exc})")
        return

    if not layers:
        print("  No correlation_spine block declared in ACTIVE_SURFACE_MANIFEST.yaml.")
        print("  Expected for PR A.5 — add the block before adding new receipt types.")
        return

    if invariant:
        print(f"  Invariant: {invariant}")
        print()

    # Pass 1: declared layers
    for layer in layers:
        lid = layer.get("id", "?")
        receipt_class = layer.get("receipt_class", "?")
        receipt_module = layer.get("receipt_module", "?")
        identity = layer.get("identity_field", "?")
        role = layer.get("role", "?")
        rel = receipt_module.replace(".", "/") + ".py" if receipt_module != "?" else ""
        present = (REPO_ROOT / rel).exists() if rel else False
        tag = "ok" if present else "MISSING"
        print(f"  [{tag}] {lid}: {receipt_class} ({role})")
        print(f"          module: {receipt_module}")
        print(f"          identity: {identity}")

    # Pass 2: schema introspection — does the dispatch-layer canonical store
    # actually carry the receipt column? (Preserved from PR #367's framing
    # as a useful declared-vs-actual reconciliation; runtime_state.py is the
    # legacy dispatch-layer persistence surface, distinct from but adjacent
    # to the spine receipt itself.)
    runtime_state = REPO_ROOT / "dharma_swarm" / "runtime_state.py"
    if runtime_state.exists():
        rs_text = runtime_state.read_text(encoding="utf-8", errors="replace")
        has_receipt = "receipt_json" in rs_text
        print()
        print(f"  runtime_state.py receipt_json DDL: {'present' if has_receipt else 'MISSING'}")

    # Pass 3: live DB fill-rate — informational, never fails.
    db_path = Path.home() / ".dharma" / "state" / "runtime.db"
    if db_path.exists():
        try:
            from dharma_swarm.operator_core.runtime_truth import (
                connect_runtime_db_read_only,
            )

            conn = connect_runtime_db_read_only(db_path)
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM delegation_runs")
                total = cur.fetchone()[0]
                cur.execute(
                    "SELECT COUNT(*) FROM delegation_runs WHERE receipt_json IS NOT NULL"
                )
                filled = cur.fetchone()[0]
                if total > 0:
                    fill_rate = f"{filled}/{total} ({100 * filled // total}%)"
                else:
                    fill_rate = "0/0"
                print(f"  Live receipt fill rate (delegation_runs): {fill_rate}")
            finally:
                conn.close()
        except Exception as exc:  # pragma: no cover — informational only
            print(f"  (live DB unavailable: {type(exc).__name__})")
    else:
        print("  (runtime.db not present — no live stats)")


def _runtime_db_path() -> Path:
    state_dir = os.environ.get("DHARMA_STATE_DIR")
    if state_dir:
        return Path(state_dir).expanduser() / "runtime.db"
    return Path.home() / ".dharma" / "state" / "runtime.db"


def _runtime_truth_packets(
    evidence: dict[str, Any] | None,
    track: dict[str, Any],
) -> list[Any]:
    from dharma_swarm.operator_core.contracts import RuntimeTruthPacket, RuntimeTruthState
    from dharma_swarm.operator_core.runtime_truth import (
        runtime_truth_packets_from_runtime_db,
    )

    observed_at = _now_iso()
    block = (track or {}).get("active_track") or {}
    progress = (evidence or {}).get("completion_progress") or {}
    passed = int(progress.get("passed") or 0)
    total = int(progress.get("total") or 0)
    criteria = (evidence or {}).get("criteria") or []
    failed_ids = [
        str(item.get("id"))
        for item in criteria
        if isinstance(item, dict) and not item.get("passed") and item.get("id")
    ]
    shippable = bool(evidence and evidence.get("shippable"))
    prereqs_ok = bool(evidence and evidence.get("prerequisites_ok"))
    active_track_id = str((evidence or {}).get("active_track_id") or block.get("id") or "unknown")

    packets: list[Any] = [
        RuntimeTruthPacket(
            surface_id="governance.active_track",
            kind="governance_projection",
            observed_at=observed_at,
            owner_surface="docs/governance/ACTIVE_TRACK.yaml",
            source_kind="generated_evidence",
            artifact_refs=[
                str(EVIDENCE_JSON.relative_to(REPO_ROOT)),
                "reports/governance/active_track_evidence.md",
            ],
            source_refs=[str(ACTIVE_TRACK.relative_to(REPO_ROOT))],
            readiness_state=(
                RuntimeTruthState.READY_BY_PROBE
                if prereqs_ok
                else RuntimeTruthState.NOT_READY_BY_PROBE
            ),
            progress_state=(
                RuntimeTruthState.PROGRESSING_BY_ARTIFACT
                if total and passed < total
                else RuntimeTruthState.COMPLETED_BY_RECEIPT
                if total and passed >= total
                else RuntimeTruthState.UNKNOWN
            ),
            completion_state=(
                RuntimeTruthState.COMPLETED_BY_RECEIPT
                if shippable
                else RuntimeTruthState.UNKNOWN
            ),
            authority_state=RuntimeTruthState.PROJECTION_ONLY,
            source_state=RuntimeTruthState.OBSERVED if evidence else RuntimeTruthState.MISSING,
            missing_machine_fields=[
                "run_id",
                "mission_id",
                "correlation_id",
                *[f"failed_criterion:{item}" for item in failed_ids],
            ],
            metadata={
                "active_track_id": active_track_id,
                "criteria_passed": passed,
                "criteria_total": total,
            },
        )
    ]

    manifest_text = ""
    if SURFACE_MANIFEST.exists():
        manifest_text = SURFACE_MANIFEST.read_text(encoding="utf-8", errors="replace")
    correlation_declared = "correlation_spine:" in manifest_text
    packets.append(
        RuntimeTruthPacket(
            surface_id="correlation_spine.manifest",
            kind="owner_manifest",
            observed_at=observed_at,
            owner_surface="ACTIVE_SURFACE_MANIFEST.yaml",
            source_kind="repo_file_probe",
            source_refs=[str(SURFACE_MANIFEST.relative_to(REPO_ROOT))],
            readiness_state=(
                RuntimeTruthState.READY_BY_PROBE
                if correlation_declared
                else RuntimeTruthState.NOT_READY_BY_PROBE
            ),
            authority_state=RuntimeTruthState.PROJECTION_ONLY,
            source_state=(
                RuntimeTruthState.OBSERVED
                if correlation_declared
                else RuntimeTruthState.MISSING
            ),
            probe_ok=correlation_declared,
            missing_machine_fields=[] if correlation_declared else ["correlation_spine"],
        )
    )

    runtime_db = _runtime_db_path()
    packets.extend(
        runtime_truth_packets_from_runtime_db(runtime_db, observed_at=observed_at)
    )

    invariant_test = REPO_ROOT / "tests/test_spine_persistence_invariant.py"
    invariant_present = invariant_test.exists()
    packets.append(
        RuntimeTruthPacket(
            surface_id="a2a.persistence_invariant",
            kind="test_contract",
            observed_at=observed_at,
            owner_surface="tests/test_spine_persistence_invariant.py",
            source_kind="repo_test_contract",
            source_refs=[
                "tests/test_spine_persistence_invariant.py",
                "dharma_swarm/a2a/a2a_server.py",
                "dharma_swarm/a2a/a2a_bridge.py",
            ],
            readiness_state=(
                RuntimeTruthState.READY_BY_PROBE
                if invariant_present
                else RuntimeTruthState.NOT_READY_BY_PROBE
            ),
            completion_state=RuntimeTruthState.UNKNOWN,
            evaluator_state=RuntimeTruthState.UNKNOWN,
            authority_state=RuntimeTruthState.PROJECTION_ONLY,
            probe_ok=invariant_present,
            missing_machine_fields=[
                "latest_test_run",
                "latest_ci_run",
            ] if invariant_present else ["test_contract"],
        )
    )

    # External gates are rendered ONLY if declared in the manifest owner.
    # (A previous version hardcoded an external PR ref here — a fact owned
    # by nobody, which violated this script's own doctrine.)
    for gate in _declared_external_gates():
        packets.append(
            RuntimeTruthPacket(
                surface_id=str(gate.get("surface_id") or "external.undeclared"),
                kind="external_truth",
                observed_at=observed_at,
                owner_surface="ACTIVE_SURFACE_MANIFEST.yaml",
                source_kind="external_gated",
                source_refs=[str(gate.get("ref") or "")],
                authority_state=RuntimeTruthState.PROJECTION_ONLY,
                external_state=RuntimeTruthState.EXTERNAL_GATED,
                mutation_state=RuntimeTruthState.NO_MUTATION_OBSERVED,
                probe_ok=None,
                missing_machine_fields=[
                    "external_api_probe_result",
                    "proof_json_path",
                    "operator_authority_to_probe_external_state",
                ],
                metadata={"no_external_probe_performed": True},
            )
        )
    return packets


def _declared_external_gates() -> list[dict[str, Any]]:
    """External truth gates declared in ACTIVE_SURFACE_MANIFEST.yaml
    (key: external_gates: [{surface_id, ref}, ...]). Undeclared → none."""
    try:
        import yaml  # type: ignore

        if not SURFACE_MANIFEST.exists():
            return []
        data = yaml.safe_load(SURFACE_MANIFEST.read_text(encoding="utf-8")) or {}
        gates = data.get("external_gates") or []
        return [g for g in gates if isinstance(g, dict)]
    except Exception:
        return []


def render_runtime_truth(
    evidence: dict[str, Any] | None,
    track: dict[str, Any],
) -> list[dict[str, Any]]:
    section("RUNTIME TRUTH PACKETS — read-only projection")
    # Guarded like every sibling section: a missing/broken dharma_swarm
    # install must degrade this section, never break the exit-0 contract.
    try:
        from dharma_swarm.operator_core.runtime_truth import (
            summarize_runtime_truth_packets,
        )

        packets = _runtime_truth_packets(evidence, track)
    except Exception as exc:
        print(f"  (runtime truth unavailable: {type(exc).__name__}: {exc})")
        return []
    rows = [packet.to_dict() for packet in packets]
    summary = summarize_runtime_truth_packets(packets)
    print("  Doctrine: packets project existing owners; this section is not authority.")
    print(
        "  Compact: "
        f"runtime_db={summary.get('runtime_db') or 'unknown'}; "
        f"latest_receipt={summary.get('latest_receipt') or 'none'}; "
        f"run_id={summary.get('run_id') or 'missing'}; "
        f"task_id={summary.get('task_id') or 'missing'}; "
        f"heartbeat={summary.get('heartbeat') or 'unknown'}; "
        f"progress={summary.get('progress') or 'unknown'}; "
        f"completion={summary.get('completion') or 'unknown'}; "
        f"retry={summary.get('retry') or 'unknown'}"
    )
    missing = summary.get("missing") or []
    if missing:
        print(f"  Missing machine fields: {', '.join(str(item) for item in missing)}")
    # One digest line per packet; the full rows go to the machine receipt
    # (~/.dharma/ops/onboard_receipt.json) — they were ~44% of the output's
    # tokens as inline JSONL and no consumer parsed stdout.
    print("  Packets (full rows in the onboard receipt):")
    for row in rows:
        anomalies = []
        for axis in ("heartbeat_state", "progress_state", "completion_state"):
            val = str(row.get(axis) or "")
            if val and val not in {"unknown", ""} and ("stalled" in val or "blocked" in val or "not_ready" in val):
                anomalies.append(f"{axis.removesuffix('_state')}={val}")
        anomaly_s = ("  ⚠ " + ", ".join(anomalies)) if anomalies else ""
        print(f"    - {row.get('surface_id')}  [{row.get('kind')}]{anomaly_s}")
    return rows


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


def _tool_available(*, which: str | None = None,
                    python_import: str | None = None) -> bool:
    """Return True if a CLI tool or Python import is reachable.
    In-process probes (shutil.which / find_spec) — no subprocess spawns."""
    if python_import:
        try:
            return importlib.util.find_spec(python_import) is not None
        except (ImportError, ValueError):
            return False
    if which:
        return shutil.which(which) is not None
    return False


# (label, probe_kwargs, install_hint)
_TOOLING_PROBES: list[tuple[str, dict[str, str], str]] = [
    ("xray.py", {"python_import": "dharma_swarm.xray"}, "built-in — check dharma_swarm install"),
    ("gitnexus", {"which": "gitnexus"}, "npm install -g gitnexus"),
    ("ast-grep", {"which": "ast-grep"}, "cargo install ast-grep / brew install ast-grep"),
    ("radon", {"which": "radon"}, "pip install radon"),
    ("grimp", {"python_import": "grimp"}, "pip install grimp"),
    ("vulture", {"which": "vulture"}, "pip install vulture"),
    ("lint-imports", {"which": "lint-imports"}, "pip install import-linter"),
]


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
    print("  - wiki show <topic> / wiki search <term> — dharma wiki at ~/.dharma/knowledge/wiki/")
    print("  - memory MCP open_nodes / search_nodes   — cross-session graph (most-skipped tool)")
    print()
    print("  Tool availability on this machine:")
    for label, kwargs, hint in _TOOLING_PROBES:
        ok = _tool_available(**kwargs)
        mark = "✅" if ok else "❌"
        suffix = "" if ok else f"  (install: {hint})"
        print(f"    {mark} {label}{suffix}")
    # Worktree truth: which checkout does `import dharma_swarm` actually win?
    try:
        spec = importlib.util.find_spec("dharma_swarm")
        origin = Path(spec.origin).resolve().parent if spec and spec.origin else None
        if origin is not None:
            local = (REPO_ROOT / "dharma_swarm").resolve()
            tag = "this worktree" if origin == local else f"ANOTHER CHECKOUT: {origin}"
            print(f"  import dharma_swarm resolves to: {tag}")
    except Exception:
        pass


def render_pr_hygiene(*, net: bool = True) -> list[dict[str, Any]]:
    section("PR HYGIENE — open pull request health")
    # Rule TEXT is owned by the workflows; point, don't paraphrase.
    # (A previous hardcoded copy taught the pre-#533 author-based model long
    # after the workflow had moved to per-intent-lane throttling.)
    print("  Rule owners (read these, not prose copies):")
    print("    - Throttling: .github/workflows/bot-pr-limit.yml  (per-INTENT-lane limits, not per-author)")
    print("    - Stale lifecycle: .github/workflows/stale-pr.yml  (warn → auto-close; drafts exempt)")
    print("    - Quality gates: docs/governance/PR_QUALITY_GATES.md")
    print()
    print("  Before opening a PR:")
    print("    1. Run: make agent-build-closeout")
    print("    2. Check for existing PRs on same topic:")
    print("       gh pr list --state open --search '<your topic>'")
    print("    3. Fill all PR template sections (Why, Surface, Coherence Delta, ...)")
    print("    4. Mark WIP/scaffold PRs as drafts; prefix shelved PRs with [SHELVED]")
    print()

    if not net:
        print("  (network skipped — rerun without --fast/--no-net for the live PR list)")
        return []

    # Live open-PR list — same call the old count used, with enough fields
    # to prevent duplicate-intent PRs. Repo inferred from cwd, not hardcoded.
    prs: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "open",
             "--json", "number,title,author,updatedAt,isDraft", "--limit", "30"],
            capture_output=True, text=True, timeout=15, cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            err = (result.stderr or "").strip().splitlines()
            print(f"  (gh pr list failed: {err[0] if err else 'unknown error'})")
            return []
        prs = json.loads(result.stdout or "[]")
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"  (gh CLI unavailable — cannot check open PRs: {type(exc).__name__})")
        return []

    count = len(prs)
    print(f"  Current open PRs: {count}")
    if count > 20:
        print("  ⚠️  HIGH — consider closing stale/duplicate PRs before adding more")
    elif count > 10:
        print("  ⚠  MODERATE — review open PRs for duplicates")
    else:
        print("  ✓  Healthy")
    for pr in prs[:12]:
        draft = " [draft]" if pr.get("isDraft") else ""
        author = (pr.get("author") or {}).get("login", "?")
        updated = str(pr.get("updatedAt", ""))[:10]
        print(f"    #{pr.get('number')}{draft}  {str(pr.get('title', ''))[:64]}  ({author}, {updated})")
    if count > 12:
        print(f"    ... ({count - 12} more — gh pr list)")
    return prs


def render_hygiene_system() -> None:
    section("HYGIENE SYSTEM (owner: docs/governance/hygiene/)")
    root = REPO_ROOT / "docs/governance/hygiene"
    pattern_dir = root / "patterns"
    patterns = []
    unreadable = 0
    for path in sorted(pattern_dir.glob("*.yaml")):
        if not (path.name.startswith("VC-") or path.name.startswith("AI-")):
            continue
        # Files carry .yaml extensions but historically hold JSON bodies.
        # Accept either; never silently drop a hygiene pattern.
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            unreadable += 1
            continue
        payload = None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            try:
                import yaml  # type: ignore

                payload = yaml.safe_load(text)
            except Exception:
                payload = None
        if not isinstance(payload, dict):
            unreadable += 1
            continue
        patterns.append(payload)
    if unreadable:
        print(f"  ⚠ {unreadable} pattern file(s) unreadable — counts below are incomplete")

    stage_counts: dict[str, int] = {}
    namespace_counts: dict[str, int] = {}
    for pattern in patterns:
        stage = str(pattern.get("stage", "unknown"))
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        pattern_id = str(pattern.get("id", "UNKNOWN"))
        namespace = pattern_id.split("-", 1)[0]
        namespace_counts[namespace] = namespace_counts.get(namespace, 0) + 1

    if patterns:
        summary = ", ".join(f"{stage}={count}" for stage, count in sorted(stage_counts.items()))
        namespaces = ", ".join(
            f"{namespace}={count}" for namespace, count in sorted(namespace_counts.items())
        )
        print(f"  Patterns: {len(patterns)} ({namespaces}; {summary})")
    else:
        print("  Patterns: missing or unreadable")

    baselines = sorted((root / "baselines").glob("*.txt"))
    latest = baselines[-1].relative_to(REPO_ROOT).as_posix() if baselines else "none yet"
    print(f"  Latest baseline: {latest}")
    print("  AI-agent governance: docs/governance/hygiene/AI_AGENT_GOVERNANCE.md")
    # Latest dated artifacts by glob, so this section never pins yesterday's
    # snapshot forever.
    for label, pattern in (
        ("Deep-dive packet", "reports/governance/anti_ai_slop_futureproof_deep_dive_*.md"),
        ("Control backlog", "reports/governance/anti_ai_slop_control_backlog_*.md"),
        ("Scan snapshot", "reports/governance/anti_ai_slop_scan_snapshot_*.json"),
    ):
        matches = sorted(REPO_ROOT.glob(pattern))
        if matches:
            print(f"  {label}: {matches[-1].relative_to(REPO_ROOT).as_posix()}")
    print("  Doctrine: AI-* signals are advisory until promoted through LIFECYCLE.md")
    print("  Run: make hygiene-audit   # non-blocking scan")
    print("  Run: make hygiene-check   # generated docs + pattern integrity")
    print("  Run: make agent-build-preflight   # start an agent build session")
    print("  Run: make agent-build-closeout    # close an agent build before PR handoff")

    for label, prefix in (
        ("AI-agent review signals", "AI-"),
        ("Code hygiene review signals", "VC-"),
    ):
        surfaced = [
            pattern for pattern in patterns
            if str(pattern.get("id", "")).startswith(prefix)
            and pattern.get("stage") in {"advisory", "enforced"}
        ][:5]
        if surfaced:
            print(f"  {label}:")
            for pattern in surfaced:
                print(f"    - {pattern.get('id')}: {pattern.get('title')} ({pattern.get('stage')})")


def render_enforcement_and_depth() -> None:
    section("ENFORCEMENT (run before opening a PR)")
    print("  make agent-build-preflight # onboarding + hygiene integrity at session start")
    print("  make agent-build-closeout  # no-write hygiene scan + full governance bundle")
    print("  make docops-integrity      # documentation invariants")
    print("  make governance-all        # full governance gate bundle")
    print("  python3 scripts/governance/check_track_status.py")
    print("  python3 scripts/governance/render_active_track_includes.py --check")
    section("DEPTH POINTERS (read on demand, not in order)")
    print("  Repo rules & behaviour : CLAUDE.md, AGENTS.md, docs/AGENTS.md")
    print("  Anti-slop rules (10)   : docs/governance/ANTI_SLOP_RULES.md   [enforced]")
    print("  AI-agent hygiene       : docs/governance/hygiene/AI_AGENT_GOVERNANCE.md")
    print("  Vibe-code hygiene (54) : docs/governance/VIBE_CODE_HYGIENE.md [advisory catalogue]")
    print("     scan & baseline     : scripts/governance/vibe_code_scan.sh")
    print("                           reports/governance/vibe_code_baseline_2026-06-07.txt")
    print("  Doc ownership map      : docs/governance/CANONICAL_DOC_STACK.md")
    print("  Architecture/doctrine  : docs/governance/SOVEREIGN_MANIFEST.md, docs/doctrine/")
    print("  Coherence Delta        : docs/governance/COHERENCE_DELTA.md")
    print("  Daily/work loops       : docs/governance/AGENTOPS.md, KAIZENOPS.md, DAILY_OPERATING_BRIEF.md")


def render_drift_triage() -> None:
    """Dhyana drift triage — top priority drifted zones."""
    section("DRIFT TRIAGE (owner: dharma_swarm/dhyana/drift_triage.py)")
    try:
        from dharma_swarm.dhyana.drift_triage import triage_drifted_zones
        entries = triage_drifted_zones()
    except Exception as exc:
        print(f"  (could not run drift triage: {exc})")
        return

    if not entries:
        print("  No drifted zones found. Control surface is clean.")
        return

    top = entries[:5]
    print(f"  {len(entries)} zones triaged. Top {len(top)} by priority_score:")
    print()
    for i, e in enumerate(top, 1):
        br_tag = f" [{', '.join(e.related_br_ids)}]" if e.related_br_ids else ""
        print(f"  {i}. [{e.coherence_state}] {e.label[:60]}")
        print(f"     score={e.priority_score:.1f}  blast={e.blast_radius:.1f}  age={e.age_days:.0f}d  centrality={e.semantic_centrality:.2f}{br_tag}")
        if e.recommended_action:
            print(f"     → {e.recommended_action[:80]}")
    print()


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_evidence() -> dict[str, Any] | None:
    if not EVIDENCE_JSON.exists():
        return None
    try:
        data = json.loads(EVIDENCE_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    # Shape-normalize: a partial write by a parallel check_track_status run
    # can yield valid JSON with garbage entries — degrade, never crash.
    tracks = data.get("active_tracks")
    if isinstance(tracks, list):
        data["active_tracks"] = [t for t in tracks if isinstance(t, dict)]
    elif tracks is not None:
        data["active_tracks"] = []
    return data


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
    here = str(Path(__file__).parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        from check_track_status import load_active_track  # type: ignore
        track = load_active_track(ACTIVE_TRACK) or {}
        # v2 portfolio back-compat: legacy onboard sections read the singular
        # `active_track`. Synthesize it as the primary (first) active track so
        # those sections keep rendering. The full portfolio is in `active_tracks`.
        if "active_track" not in track and track.get("active_tracks"):
            tracks = [t for t in track["active_tracks"] if t]
            if tracks:
                track["active_track"] = tracks[0]
        return track
    except Exception:
        return {}


def _collect_next_items(
    evidence: dict[str, Any] | None,
    track: dict[str, Any],
) -> list[dict[str, Any]]:
    """next_items from the v2 portfolio's UNSHIPPED active tracks.

    The old read used the v1 singular `active_track` (= first track after
    the v2 shim), which served already-completed work as next steps whenever
    the first track happened to be shippable. Pull from every active track
    that still has failing criteria; fall back to v1.
    """
    ev_tracks = {
        t.get("id"): t
        for t in ((evidence or {}).get("active_tracks") or [])
        if isinstance(t, dict)
    }
    yaml_tracks = (track or {}).get("active_tracks") or []
    if not yaml_tracks and (track or {}).get("active_track"):
        yaml_tracks = [track["active_track"]]

    items: list[dict[str, Any]] = []
    for t in yaml_tracks:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        ev = ev_tracks.get(tid) or {}
        if ev_tracks and ev.get("shippable"):
            continue  # done — its next_items are stale by definition
        for item in t.get("next_items") or []:
            if isinstance(item, dict):
                items.append({**item, "track_id": tid})
    return items


def _write_receipt(payload: dict[str, Any]) -> Path | None:
    """Tee the machine receipt for fleet consumers. Never raises; failure
    degrades to a printed note. Writes OUTSIDE the repo — onboard stays
    read-only on owners."""
    try:
        ops = _ops_dir()
        ops.mkdir(parents=True, exist_ok=True)
        target = ops / ONBOARD_RECEIPT_NAME
        tmp = target.with_suffix(f".{os.getpid()}.tmp")  # unique per writer: concurrent runs never race on one tmp
        tmp.write_text(json.dumps(payload, sort_keys=True, indent=1), encoding="utf-8")
        tmp.replace(target)
        return target
    except Exception as exc:  # OSError, or TypeError from an unserializable value
        # stderr, never stdout: --json consumers must always get clean JSON.
        print(f"(could not write onboard receipt: {type(exc).__name__}: {exc})", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render dharma_swarm operating reality from its owners.")
    parser.add_argument("--fast", action="store_true",
                        help="skip slow probes (git status, drift triage, manifest health, network)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="print the machine receipt JSON to stdout instead of prose")
    parser.add_argument("--no-net", action="store_true",
                        help="skip network calls (gh pr list)")
    # Deliberate exception to always-exit-0: an UNRECOGNIZED FLAG exits 2
    # (argparse default, usage on stderr, stdout empty). The exit-0 contract
    # covers stale STATE; silently proceeding on a typo'd flag would mask
    # broken automation — e.g. '--fasy' running a 30s full pass as exit 0.
    args = parser.parse_args(argv)
    net = not (args.fast or args.no_net)

    os.chdir(REPO_ROOT)

    # Evidence freshness: refresh by default when missing or stale, unless
    # told not to. AGENT_ONBOARD_REFRESH=1 forces; AGENT_ONBOARD_NO_REFRESH=1
    # or --fast skips. Freshness must not depend on an external loop being alive.
    force = os.getenv("AGENT_ONBOARD_REFRESH", "").strip() == "1"
    skip = args.fast or os.getenv("AGENT_ONBOARD_NO_REFRESH", "").strip() == "1"
    evidence = _load_evidence()
    age_min = _evidence_age_minutes(evidence)
    stale = evidence is None or age_min is None or age_min > EVIDENCE_STALE_MINUTES
    if force or (stale and not skip):
        _refresh_evidence()
        evidence = _load_evidence()
    track = _load_track_yaml()

    if args.as_json:
        # Machine mode: build the receipt quietly and print it.
        import contextlib
        import io

        sink = io.StringIO()
        with contextlib.redirect_stdout(sink):
            repo_state = render_repo_state(fast=args.fast)
            lanes = render_parallel_work_lanes()
            rows = render_runtime_truth(evidence, track)
            prs = render_pr_hygiene(net=net)
        payload = _receipt_payload(repo_state, lanes, rows, prs, evidence, track)
        _write_receipt(payload)
        print(json.dumps(payload, sort_keys=True, indent=1))
        return 0

    repo_state = render_repo_state(fast=args.fast)
    render_active_track(evidence, track)
    lanes = render_parallel_work_lanes()
    render_live_ops()
    render_live_ops_cockpit()
    if args.fast:
        section("SURFACE MANIFEST HEALTH (skipped — --fast)")
        print("  Rerun without --fast for the manifest health report.")
    else:
        render_manifest_health()
    render_broken_register()
    render_axioms()
    render_recent_activity(track)
    render_spine_status()
    rows = render_runtime_truth(evidence, track)
    prs = render_pr_hygiene(net=net)
    render_hygiene_system()
    render_decay_watch()
    render_tooling_first()
    render_enforcement_and_depth()
    if args.fast:
        section("DRIFT TRIAGE (skipped — --fast)")
        print("  Rerun without --fast for the drift triage (the slowest section).")
    else:
        render_drift_triage()

    section("WHAT TO DO NEXT")
    # Portfolio-aware: an operator proposing a new project should OPEN A TRACK,
    # never be told it "violates the active track".
    active_tracks = (evidence or {}).get("active_tracks") or []
    next_items = _collect_next_items(evidence, track)
    prereqs_ok = bool(evidence and evidence.get("prerequisites_ok"))
    shippable_ids = [t.get("id") for t in active_tracks if t.get("shippable")]

    print("  If the operator proposes a NEW project: open a new track (see the")
    print("  ACTIVE PORTFOLIO section above for how) — do NOT treat it as a")
    print("  violation of an existing track. Concurrency is allowed up to the WIP limit.")
    print()
    if not prereqs_ok:
        print("  A track's prerequisites are failing — it is mis-declared. Fix the YAML.")
    if shippable_ids:
        print(f"  Shippable now: {', '.join(shippable_ids)} — move each to closed_tracks")
        print("  (the other active tracks keep running), then run")
        print("  python3 scripts/governance/render_active_track_includes.py")
    if next_items:
        print("  Or continue an unshipped active track — next_items:")
        for item in next_items[:6]:
            tag = " (blocker)" if item.get("blocker") else ""
            print(f"    - [{item.get('track_id', '?')}] [{item.get('kind', '?')}]{tag} {item.get('what', '')}")
    print()
    print("  Reminder: this command renders the owners; it does not own any fact.")
    print("  When in doubt: trust the filesystem, git log, and ACTIVE_TRACK.yaml.")

    receipt_path = _write_receipt(
        _receipt_payload(repo_state, lanes, rows, prs, evidence, track))
    if receipt_path:
        print(f"  Machine receipt: {receipt_path}  (fleet-readable; also: --json)")

    # Informational tool. Always exit 0.
    return 0


def _receipt_payload(
    repo_state: dict[str, Any],
    lanes: dict[str, Any],
    rows: list[dict[str, Any]],
    prs: list[dict[str, Any]],
    evidence: dict[str, Any] | None,
    track: dict[str, Any],
) -> dict[str, Any]:
    active_tracks = (evidence or {}).get("active_tracks") or []
    broken = _parse_broken_register()
    return {
        "schema": "dharma_swarm.onboard_receipt.v1",
        "observed_at": _now_iso(),
        "authority": "projection_only",
        "repo": repo_state,
        "work_lanes": lanes,
        "portfolio": {
            "summary": (evidence or {}).get("portfolio_summary"),
            "spine_coverage": (evidence or {}).get("spine_coverage"),
            "evidence_age_minutes": _evidence_age_minutes(evidence),
            "tracks": [
                {
                    "id": t.get("id"),
                    "status": t.get("status"),
                    "serves": t.get("serves"),
                    "shippable": t.get("shippable"),
                    "failing_criteria": [
                        c.get("id")
                        for c in (t.get("criteria") if isinstance(t.get("criteria"), list) else []) or []
                        if isinstance(c, dict) and not c.get("passed")
                    ],
                }
                for t in active_tracks
                if isinstance(t, dict)
            ],
        },
        "next_items": _collect_next_items(evidence, track)[:10],
        "broken_register": {
            k: broken.get(k) for k in ("total", "open_count", "closed_count")
        },
        "open_prs": [
            {"number": p.get("number"), "title": p.get("title"),
             "isDraft": p.get("isDraft")} for p in prs if isinstance(p, dict)
        ],
        "runtime_truth_packets": rows,
    }


if __name__ == "__main__":
    sys.exit(main())
