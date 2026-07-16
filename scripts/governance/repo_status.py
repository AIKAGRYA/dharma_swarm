#!/usr/bin/env python3
"""repo_status.py — quick cross-agent state snapshot.

Renders a one-screen summary any agent (Devin, Codex, Claude Code, Copilot)
can read to know: what is the active track, what PRs are open, what is stale,
what tasks are claimed, and what needs attention.

Usage:
    python3 scripts/governance/repo_status.py
    make status
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_broken_register_parser():
    path = REPO_ROOT / "dharma_swarm/operator_core/onboarding/broken_register.py"
    spec = importlib.util.spec_from_file_location("_dharma_broken_register_status", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load canonical broken-register parser: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.parse_broken_register


parse_broken_register = _load_broken_register_parser()

ACTIVE_TRACK = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"
BROKEN_REGISTER = REPO_ROOT / "docs/state/BROKEN_REGISTER.md"
HOTLIST = REPO_ROOT / "docs/state/HOTLIST.md"
NEXT_PHASE_MAP = REPO_ROOT / "docs/state/NEXT_PHASE_MAP.md"

STALE_DAYS = 14
NOW = datetime.now(timezone.utc)

# ── helpers ──────────────────────────────────────────────────────────────

def _run(cmd: list[str], cwd: Path = REPO_ROOT) -> str:
    """Run a subprocess, return stdout or empty string on failure."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(cwd), timeout=30,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _git_branch() -> str:
    return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def _git_last_commit() -> str:
    return _run(["git", "log", "-1", "--oneline"])


def _open_prs() -> list[dict]:
    """Get open PRs via gh CLI. Returns empty list if gh unavailable."""
    raw = _run([
        "gh", "pr", "list", "--state", "open", "--limit", "100",
        "--json", "number,title,createdAt,author,headRefName",
    ])
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def _parse_active_track() -> dict[str, str]:
    """Extract key fields for the primary active track from ACTIVE_TRACK.yaml.

    Handles both schemas: v2 (`active_tracks:` list) and v1 (singular
    `active_track:`) via the shared normalizer. For v2 portfolios it returns the
    primary (first ACTIVE) track plus an `active_count` of how many tracks are
    live, so `make status` reflects the portfolio rather than a single slot.
    """
    info: dict[str, str] = {}
    if not ACTIVE_TRACK.exists():
        return info
    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))
        from check_track_status import load_active_track, normalize_portfolio  # type: ignore
        p = normalize_portfolio(load_active_track(ACTIVE_TRACK))
        primary = p.get("primary") or {}
        for key in ("id", "status", "name", "verified_at", "owner"):
            if primary.get(key) is not None:
                info[key] = str(primary[key])
        info["active_count"] = str(len([t for t in p["active_tracks"]
                                        if str(t.get("status", "")).upper() in {"ACTIVE", "SHIPPABLE"}]))
        if info.get("id"):
            return info
    except Exception:
        pass
    # Fallback: legacy regex (v1 indented-under-active_track fields).
    text = ACTIVE_TRACK.read_text()
    for key in ("id", "status", "name", "verified_at", "owner"):
        m = re.search(rf"^\s+{key}:\s*(.+)$", text, re.MULTILINE)
        if m:
            info[key] = m.group(1).strip().strip('"').strip("'").strip("|")
    return info


def _count_broken_register() -> tuple[int, int]:
    """Return canonical (distinct total, open-like) register counts."""
    result = parse_broken_register(BROKEN_REGISTER)
    return (result.total, result.open_count) if result.present else (0, 0)


def _hotlist_summary() -> tuple[int, int, int]:
    """Return (total, done, in-progress) from HOTLIST.md."""
    if not HOTLIST.exists():
        return 0, 0, 0
    text = HOTLIST.read_text()
    rows = re.findall(r"^\|.*\|$", text, re.MULTILINE)
    total = 0
    done = 0
    in_progress = 0
    for row in rows:
        if "---" in row or "Priority" in row:
            continue
        total += 1
        lower = row.lower()
        if "done" in lower or "merged" in lower or "✓" in lower:
            done += 1
        elif "in.progress" in lower or "active" in lower or "wip" in lower:
            in_progress += 1
    return total, done, in_progress


def _stale_prs(prs: list[dict]) -> list[dict]:
    """Filter PRs older than STALE_DAYS."""
    cutoff = NOW - timedelta(days=STALE_DAYS)
    stale = []
    for pr in prs:
        created = pr.get("createdAt", "")
        if not created:
            continue
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if dt < cutoff:
                stale.append(pr)
        except ValueError:
            pass
    return stale


def _count_test_functions() -> int:
    """Fast count of def test_ functions."""
    count = 0
    for f in (REPO_ROOT / "tests").rglob("*.py"):
        try:
            count += f.read_text().count("def test_")
        except Exception:
            pass
    return count


# ── main ─────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  DHARMA SWARM — REPO STATUS")
    print(f"  {NOW.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # Git state
    branch = _git_branch()
    last = _git_last_commit()
    print(f"\n📌 Branch: {branch}")
    print(f"   Last commit: {last}")

    # Active track
    track = _parse_active_track()
    if track:
        print(f"\n🎯 Active Track: {track.get('name', '?')}")
        print(f"   ID: {track.get('id', '?')}")
        print(f"   Status: {track.get('status', '?')}")
        verified = track.get("verified_at", "")
        if verified:
            print(f"   Verified: {verified}")
    else:
        print("\n🎯 Active Track: (could not parse ACTIVE_TRACK.yaml)")

    # Open PRs
    prs = _open_prs()
    stale = _stale_prs(prs)
    print(f"\n📋 Open PRs: {len(prs)} total, {len(stale)} stale (>{STALE_DAYS}d)")
    if prs:
        # Show recent 5
        recent = sorted(prs, key=lambda p: p.get("number", 0), reverse=True)[:5]
        for pr in recent:
            author = pr.get("author", {}).get("login", "?")
            print(f"   #{pr['number']:>3} ({author}) {pr['title'][:60]}")
        if len(prs) > 5:
            print(f"   ... and {len(prs) - 5} more")

    # Stale PRs
    if stale:
        print(f"\n⚠️  Stale PRs ({len(stale)} older than {STALE_DAYS} days):")
        for pr in sorted(stale, key=lambda p: p.get("number", 0)):
            age = (NOW - datetime.fromisoformat(
                pr["createdAt"].replace("Z", "+00:00")
            )).days
            print(f"   #{pr['number']:>3} ({age}d old) {pr['title'][:55]}")

    # Broken register
    total_br, open_br = _count_broken_register()
    print(f"\n🔧 Broken Register: {total_br} total, {open_br} open-like")

    # Hotlist
    total_hl, done_hl, wip_hl = _hotlist_summary()
    if total_hl:
        pending = total_hl - done_hl - wip_hl
        print(f"\n📊 Hotlist: {total_hl} items — {done_hl} done, {wip_hl} WIP, {pending} pending")

    # Test count
    test_count = _count_test_functions()
    print(f"\n🧪 Test functions: {test_count}")

    # Quick health warnings
    warnings = []
    if len(stale) > 10:
        warnings.append(f"{len(stale)} stale PRs — consider closing or rebasing")
    if open_br >= 5:
        warnings.append(f"{open_br} open broken register items")

    # Check stale docs
    stale_docs = []
    for doc_path in [
        "CYBERNETIC_LOOP_MAP.md",
        "INTERFACE_MISMATCH_MAP.md",
        "docs/state/LIVE_OPS_DASHBOARD.md",
    ]:
        full = REPO_ROOT / doc_path
        if full.exists():
            try:
                stat = full.stat()
                age = (NOW - datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                )).days
                if age > 7:
                    stale_docs.append(f"{doc_path} ({age}d since modified)")
            except Exception:
                pass
    if stale_docs:
        warnings.append("Stale docs: " + ", ".join(stale_docs))

    if warnings:
        print("\n⚠️  Warnings:")
        for w in warnings:
            print(f"   - {w}")

    print("\n" + "=" * 60)
    print("  Run `make onboard` for session status")
    print("  Run `make organism-status` for whole-organism orientation")
    print("  Run `make status` for this quick snapshot")
    print("=" * 60)


if __name__ == "__main__":
    main()
