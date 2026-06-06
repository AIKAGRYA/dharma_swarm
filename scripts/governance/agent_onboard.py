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

    packets.append(
        RuntimeTruthPacket(
            surface_id="external.keystone_merge",
            kind="external_truth",
            observed_at=observed_at,
            owner_surface="external_operator_state",
            source_kind="external_gated",
            source_refs=["external:abduznik/instrumation#98"],
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


def render_runtime_truth(
    evidence: dict[str, Any] | None,
    track: dict[str, Any],
) -> list[dict[str, Any]]:
    from dharma_swarm.operator_core.runtime_truth import summarize_runtime_truth_packets

    section("RUNTIME TRUTH PACKETS — read-only projection")
    packets = _runtime_truth_packets(evidence, track)
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
    print("  Machine rows (JSONL):")
    for row in rows:
        print(f"    {json.dumps(row, sort_keys=True)}")
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
    print("  - wiki show <topic> / wiki search <term> — 115-article wiki at ~/.dharma/knowledge/wiki/")
    print("  - memory MCP open_nodes / search_nodes   — cross-session graph (most-skipped tool)")
    print()
    print("  Tool availability on this machine:")
    for label, kwargs, hint in _TOOLING_PROBES:
        ok = _tool_available(**kwargs)
        mark = "✅" if ok else "❌"
        suffix = "" if ok else f"  (install: {hint})"
        print(f"    {mark} {label}{suffix}")


def render_pr_hygiene() -> None:
    section("PR HYGIENE — open pull request health")
    print("  Rules (see docs/governance/PR_QUALITY_GATES.md):")
    print("    - Bot authors: max 3 open PRs (enforced by bot-pr-limit.yml)")
    print("    - Bot PRs: auto-close after 14 days inactivity")
    print("    - Human PRs: auto-close after 30 days inactivity")
    print("    - Draft PRs: exempt from auto-close")
    print("    - Duplicate-intent bot PRs: detected by title-prefix matching")
    print()
    print("  Before opening a PR:")
    print("    1. Run: make governance-all")
    print("    2. Check for existing PRs on same topic:")
    print("       gh pr list --state open --search '<your topic>'")
    print("    3. Fill all PR template sections (Why, Surface, Coherence Delta, ...)")
    print("    4. Mark WIP/scaffold PRs as drafts; prefix shelved PRs with [SHELVED]")
    print()

    # Attempt to show open PR count if gh is available.
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--repo", "AmitabhainArunachala/dharma_swarm",
             "--state", "open", "--json", "number", "--jq", "length"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip().isdigit():
            count = int(result.stdout.strip())
            print(f"  Current open PRs: {count}")
            if count > 20:
                print("  ⚠️  HIGH — consider closing stale/duplicate PRs before adding more")
            elif count > 10:
                print("  ⚠  MODERATE — review open PRs for duplicates")
            else:
                print("  ✓  Healthy")
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        print("  (gh CLI unavailable — cannot check open PR count)")


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
    if os.getenv("AGENT_ONBOARD_REFRESH", "").strip() == "1":
        _refresh_evidence()
    evidence = _load_evidence()
    track = _load_track_yaml()

    render_repo_state()
    render_active_track(evidence, track)
    render_live_ops()
    render_live_ops_cockpit()
    render_manifest_health()
    render_broken_register()
    render_axioms()
    render_recent_activity(track)
    render_spine_status()
    render_runtime_truth(evidence, track)
    render_pr_hygiene()
    render_decay_watch()
    render_tooling_first()
    render_enforcement_and_depth()
    render_drift_triage()

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
