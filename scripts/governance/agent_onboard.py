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
from collections import Counter
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


def _run_probe(args: list[str], *, cwd: Path = REPO_ROOT, timeout: int = 8) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, str(exc)
    return completed.returncode == 0, completed.stdout.strip()


def _port_listening(port: int) -> bool:
    ok, _out = _run_probe(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
        timeout=4,
    )
    return ok


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


def _strip_ref_prefix(branch: str | None) -> str | None:
    if not branch:
        return None
    prefix = "refs/heads/"
    return branch[len(prefix):] if branch.startswith(prefix) else branch


def _parse_worktree_porcelain(text: str) -> list[dict[str, Any]]:
    """Parse `git worktree list --porcelain` into small dictionaries."""
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
    if "pr" in text or "review" in text or "merge-master" in text:
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

def render_repo_state(*, fast: bool = False) -> None:
    section("DHARMA SWARM — AGENT ONBOARDING")
    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "(detached)"
    sha = git("rev-parse", "--short=10", "HEAD")
    head_msg = git("log", "-1", "--format=%ci %s")
    # Divergence from origin/main, if known
    ahead = git("rev-list", "--count", "origin/main..HEAD")
    behind = git("rev-list", "--count", "HEAD..origin/main")
    dirty_count: int | str
    if fast:
        dirty_count = "(skipped in fast mode)"
    else:
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
    tracks = _active_tracks(track)
    section(f"ACTIVE TRACKS ({len(tracks)}; 1-10; owner: docs/governance/ACTIVE_TRACK.yaml)")
    if not evidence:
        print("  WARNING: no active_track_evidence.json found.")
        print("  Run: python3 scripts/governance/check_track_status.py")
        return

    # Map evidence per-track rows by id for fast lookup.
    ev_by_id = {tr.get("id"): tr for tr in (evidence.get("active_tracks") or [])}
    primary_id = evidence.get("active_track_id")

    if not tracks:
        # Fall back to evidence rows if YAML parse yielded nothing.
        tracks = [{"id": tr.get("id")} for tr in (evidence.get("active_tracks") or [])]

    for block in tracks:
        tid = block.get("id", "(unknown)")
        primary_tag = " [PRIMARY]" if (block.get("primary") or tid == primary_id) else ""
        print(f"  ID         : {tid}{primary_tag}")
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
        ev = ev_by_id.get(tid, {})
        progress = ev.get("completion_progress", {"passed": 0, "total": 0})
        print(f"  Prereqs    : {'OK' if ev.get('prerequisites_ok') else 'FAILED'}")
        print(f"  Completion : {progress['passed']}/{progress['total']}")
        shippable = ev.get("shippable", False)
        print(f"  Shippable  : {'YES — declare next track' if shippable else 'no'}")

        criteria = ev.get("criteria", [])
        if criteria:
            print("  Acceptance criteria:")
            for c in criteria:
                mark = "✓" if c.get("passed") else "✗"
                print(f"    {mark} [{c.get('kind')}] {c.get('id')}")
                if not c.get("passed"):
                    print(f"        {c.get('detail', '')}")
        print()


def render_parallel_work_lanes(track: dict[str, Any], *, fast: bool = False) -> None:
    section("PARALLEL WORK LANES (live git/worktree inventory)")
    policy = (track or {}).get("parallel_lane_policy") or {}
    model = policy.get("model") or "one strategic active track; many coordinated work lanes"
    allowed = policy.get("allowed", True)
    print(f"  Model      : {model}")
    print(f"  Allowed    : {'yes' if allowed else 'no'}")
    print("  Meaning    : ACTIVE_TRACK.yaml is the strategic north-star, not a global mutex.")
    if policy.get("strategic_track_role"):
        print(f"  Track role : {policy['strategic_track_role']}")

    snapshot = _work_lane_snapshot()
    worktrees = snapshot["worktrees"]
    prunable = [w for w in worktrees if w.get("prunable")]
    detached = [w for w in worktrees if w.get("detached")]
    existing = [w for w in worktrees if w.get("exists")]

    print()
    print("  Local pressure:")
    print(
        f"    worktrees={len(worktrees)} existing={len(existing)} "
        f"prunable={len(prunable)} detached={len(detached)} "
        f"local_branches={snapshot['local_branch_count']}"
    )
    if snapshot["family_counts"]:
        top = snapshot["family_counts"].most_common(8)
        print("    lane families: " + ", ".join(f"{name}={count}" for name, count in top))

    current = [
        w for w in worktrees
        if w.get("exists") and not w.get("prunable")
    ][:8]
    if current:
        print()
        print("  Active worktree sample:")
        for w in current:
            branch = w.get("branch") or ("(detached)" if w.get("detached") else "(unknown)")
            head = str(w.get("head") or "")[:10]
            print(f"    - {w.get('basename')}: {branch} @ {head}")

    if prunable:
        print()
        print("  Cleanup candidates:")
        for w in prunable[:6]:
            branch = w.get("branch") or ("(detached)" if w.get("detached") else "(unknown)")
            print(f"    - {w.get('path')} [{branch}]")
        if len(prunable) > 6:
            print(f"    ... {len(prunable) - 6} more prunable worktrees")
        print("    Rule: review receipts before pruning; never delete unreviewed user work.")

    if not fast and snapshot["recent_branches"]:
        print()
        print("  Recent local branches:")
        for branch in snapshot["recent_branches"][:6]:
            print(f"    - {branch['date']} {branch['name']}: {branch['subject'][:80]}")

    print()
    print("  Lane requirements:")
    requirements = policy.get("lane_requirements") or [
        "Bind work to the active strategic track or an explicit exception lane.",
        "Use an isolated worktree/branch or ds-goal/AgentOps packet for implementation.",
        "Declare owner, scope, verification, and receipt path before broad edits.",
        "Do not write into unrelated dirty files.",
    ]
    for req in requirements[:8]:
        print(f"    - {req}")
    if policy.get("root_worktree_policy"):
        print(f"  Root policy: {policy['root_worktree_policy']}")
    if policy.get("cleanup_policy"):
        print(f"  Cleanup    : {policy['cleanup_policy']}")


def render_product_center() -> None:
    section("PRODUCT CENTER")
    print("  Dharma Swarm is a telos-gated DGM Goodworks Intelligence Core.")
    print("  Job: verifiable welfare, ecological MRV, regenerative coordination.")
    print("  API: /api/goodworks-dgm/status, /api/goodworks-dgm/goal, /api/goodworks-dgm/receipts")
    print("  Dashboard: /dashboard/goodworks")
    print("  Runtime: scripts/runtime/goodworks_dgm_tick.py --seed-pilot")
    print("  Agent tool: goodworks_dgm; optional MCP: python3 -m dharma_swarm.goodworks_dgm.mcp")
    print("  Key truth: GitHub never contains API key values; reconcile dkeys via local probes only.")


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


def render_manifest_health(*, fast: bool = False) -> None:
    section("SURFACE MANIFEST HEALTH (owner: ACTIVE_SURFACE_MANIFEST.yaml)")
    if not SURFACE_MANIFEST.exists():
        print("  MISSING — ACTIVE_SURFACE_MANIFEST.yaml not found")
        return
    days, _ = _doc_staleness("ACTIVE_SURFACE_MANIFEST.yaml")
    if days >= 0:
        tag = "stale" if days > SURFACE_MANIFEST_STALE_DAYS else "fresh"
        print(f"  Last git touch: {days}d ago ({tag})")
    if fast:
        print("  Health        : skipped in fast mode")
        return

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
    # Union surfaces across all active tracks, preserving order and deduping.
    surfaces: list[str] = []
    seen: set[str] = set()
    for trk in _active_tracks(track):
        for surface in (trk.get("surfaces") or []):
            if surface not in seen:
                seen.add(surface)
                surfaces.append(surface)
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


def _tool_available(*, which: str | None = None,
                    python_import: str | None = None) -> bool:
    """Return True if a CLI tool or Python import is reachable."""
    if python_import:
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"import {python_import}"],
                capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False
    if which:
        try:
            result = subprocess.run(
                ["which", which], capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False
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


def render_tooling_first(*, fast: bool = False) -> None:
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
    print("  - wiki show <topic> / wiki search <term> — 115-article wiki at ~/.dharma/knowledge/wiki/")
    print("  - memory MCP open_nodes / search_nodes   — cross-session graph (most-skipped tool)")
    print()
    print("  Tool availability on this machine:")
    if fast:
        print("    skipped in fast mode")
        return
    for label, kwargs, hint in _TOOLING_PROBES:
        ok = _tool_available(**kwargs)
        mark = "✅" if ok else "❌"
        suffix = "" if ok else f"  (install: {hint})"
        print(f"    {mark} {label}{suffix}")


def render_frontend_readiness() -> None:
    section("FRONTEND READINESS (canonical dashboard + terminal)")
    dashboard_dir = REPO_ROOT / "dashboard"
    build_id = dashboard_dir / ".next/BUILD_ID"
    node_modules = dashboard_dir / "node_modules"

    deps_ok, deps_out = _run_probe(
        ["npm", "--prefix", "dashboard", "ls", "--depth=0"],
        timeout=12,
    )
    bridge_ok, bridge_out = _run_probe(
        [sys.executable, "-c", "import dharma_swarm.terminal_bridge"],
        timeout=8,
    )
    api_http_ok, _ = _run_probe(
        ["curl", "--max-time", "2", "-fsS", "http://127.0.0.1:8420/api/health"],
        timeout=4,
    )
    web_http_ok, _ = _run_probe(
        ["curl", "--max-time", "2", "-fsS", "http://127.0.0.1:3420/dashboard"],
        timeout=4,
    )
    api_listening = api_http_ok or _port_listening(8420)
    web_listening = web_http_ok or _port_listening(3420)

    print(f"  Dashboard deps : {'OK' if deps_ok else 'BROKEN'}")
    if not deps_ok:
        first_line = deps_out.splitlines()[0] if deps_out else "npm ls failed"
        print(f"    fix: make dashboard-install  ({first_line})")
    print(f"  Dashboard build: {'present' if build_id.exists() else 'missing'}")
    if not build_id.exists():
        print("    fix: make dashboard-build")
    api_status = "healthy" if api_http_ok else "listening" if api_listening else "not ready"
    web_status = "serving /dashboard" if web_http_ok else "listening" if web_listening else "not ready"
    print(f"  API :8420      : {api_status}")
    print(f"  Web :3420      : {web_status}")
    print(f"  Terminal bridge: {'imports cleanly' if bridge_ok else 'BROKEN'}")
    if not bridge_ok:
        first_line = bridge_out.splitlines()[-1] if bridge_out else "bridge import failed"
        print(f"    fix: make terminal-check  ({first_line})")
    print(f"  node_modules   : {'present' if node_modules.exists() else 'missing'}")


def render_context_quorum() -> None:
    section("CONTEXT QUORUM — MULTI-AGENT COORDINATION SPINE")
    script = REPO_ROOT / "scripts/runtime/context_quorum.py"
    policy = REPO_ROOT / "docs/ops/context_quorum_policy.json"
    ok, out = _run_probe([sys.executable, str(script), "status", "--json"], timeout=8)
    data: dict[str, Any] = {}
    if ok and out:
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            data = {}

    print(f"  CLI            : {'present' if script.exists() else 'missing'}")
    print(f"  Policy         : {'present' if policy.exists() else 'missing'}")
    if data:
        print(f"  Agent homes    : {data.get('agent_home_count', 0)} at {data.get('agent_home_root', '~/.dharma/agents')}")
        sample = data.get("sample_agents") or []
        if sample:
            print(f"  Sample agents  : {', '.join(sample[:6])}")
    else:
        print("  Agent homes    : unknown")
    print("  Start agent    : make context-quorum-init AGENT=name ROLE=role")
    print("  Pre-edit gate  : make context-quorum-check AGENT=name RISK=Q2 QUESTION='...'")
    print("  Handoff        : make context-quorum-handoff AGENT=name SUMMARY='...'")


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
    print("  PGE/long-run harness   : docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md, docs/ops/LONG_RUNNING_HARNESS.md")
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


def _active_tracks(track: dict[str, Any] | None) -> list[dict[str, Any]]:
    tracks = (track or {}).get("active_tracks") or []
    return tracks if isinstance(tracks, list) else []


def _primary_track(track: dict[str, Any] | None) -> dict[str, Any]:
    """Return the primary active track (primary:true marker, else first)."""
    tracks = _active_tracks(track)
    for trk in tracks:
        if isinstance(trk, dict) and trk.get("primary"):
            return trk
    return tracks[0] if tracks else {}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    fast = "--fast" in args or os.environ.get("DHARMA_ONBOARD_FAST") == "1"
    os.chdir(REPO_ROOT)
    if not fast:
        _refresh_evidence()
    evidence = _load_evidence()
    track = _load_track_yaml()

    render_repo_state(fast=fast)
    render_active_track(evidence, track)
    render_parallel_work_lanes(track, fast=fast)
    render_product_center()
    render_live_ops()
    render_manifest_health(fast=fast)
    render_broken_register()
    render_axioms()
    if not fast:
        render_recent_activity(track)
        render_decay_watch()
        render_frontend_readiness()
        render_context_quorum()
    render_tooling_first(fast=fast)
    render_enforcement_and_depth()

    section("WHAT TO DO NEXT")
    tracks = _active_tracks(track)
    ev_by_id = {tr.get("id"): tr for tr in (evidence.get("active_tracks") or [])} if evidence else {}
    # Across all active tracks: are prereqs failing anywhere? are all shippable?
    any_prereq_failing = any(
        not ev_by_id.get(trk.get("id"), {}).get("prerequisites_ok", True)
        for trk in tracks
    )
    all_shippable = bool(tracks) and all(
        ev_by_id.get(trk.get("id"), {}).get("shippable", False)
        for trk in tracks
    )
    if any_prereq_failing:
        print("  Prerequisites are failing on one or more active tracks (mis-declared).")
        print("  Fix the YAML or re-open the relevant track.")
    elif all_shippable:
        print("  All completion criteria pass on every active track. Close the shippable ones.")
        print("  Edit docs/governance/ACTIVE_TRACK.yaml:")
        print("    - move the shippable active_tracks item(s) to closed_tracks")
        print("    - declare any successor track block(s)")
        print("  Run: python3 scripts/governance/render_active_track_includes.py")
    else:
        printed_any = False
        for trk in tracks:
            next_items = trk.get("next_items", []) or []
            ev = ev_by_id.get(trk.get("id"), {})
            if ev.get("shippable"):
                print(f"  [{trk.get('id')}] SHIPPABLE — close it and declare its successor.")
                printed_any = True
                continue
            if not next_items:
                continue
            primary_tag = " [PRIMARY]" if trk.get("primary") else ""
            print(f"  next_items for [{trk.get('id')}]{primary_tag}:")
            for item in next_items[:5]:
                tag = " (blocker)" if item.get("blocker") else ""
                print(f"    - [{item.get('kind', '?')}]{tag} {item.get('what', '')[:80]}")
            printed_any = True
        if not printed_any:
            print("  No next_items declared. Add to ACTIVE_TRACK.yaml or pick from BR-* open items.")
    print()
    print("=" * 72)
    print("SEE-ALSO LINKS")
    print("=" * 72)
    print("  Substrate map      ~/.dharma/knowledge/wiki/concepts/dharma-swarm-substrate-map.md")
    print("                       (existing surfaces — look here BEFORE writing new files)")
    print("  Anti-slop rules    docs/governance/ANTI_SLOP_RULES.md  (10 rules; Rule 2 load-bearing)")
    print("  Sovereign manifest docs/governance/SOVEREIGN_MANIFEST.md  (architectural truth)")
    print("  Surface manifest   ACTIVE_SURFACE_MANIFEST.yaml  (control-plane inventory)")
    print("  Wiki index         ~/.dharma/knowledge/wiki/index.md  (355 atoms, 8 MOCs)")
    print("  Broken register    docs/state/BROKEN_REGISTER.md  (interface mismatches + decay)")
    print()
    print("  Reminder: this command renders the owners; it does not own any fact.")
    print("  When in doubt: trust the filesystem, git log, and ACTIVE_TRACK.yaml.")

    # Informational tool. Always exit 0.
    return 0


if __name__ == "__main__":
    sys.exit(main())
