"""Runtime, live-ops, dashboard, preservation, and receipt probes."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

from .base import DEFAULT_REPO_ROOT, ProbeContext, SURFACE_PROBES, _card, _evidence, _file_age_hours, _rel, _run, _safe_read_text
from .git_governance import _infer_track

def _probe_live_ops(ctx: ProbeContext) -> dict[str, Any]:
    """Project the canonical live-ops census (scripts/runtime/live_ops_census.py).

    This is the existing owner of runtime liveness truth. We read it rather than
    re-deriving liveness, and we flag surfaces whose receipts claim liveness but
    are stale, or that are blocked / desired-live-but-stopped.
    """
    if not ctx.include_live_probes:
        return {"enabled": False, "reason": "live_probes_disabled", "summary": {}, "surfaces": []}
    # The live-ops census lives under scripts/runtime; depending on how this
    # module is invoked (pytest, API import, CLI script) the repo root may not
    # be on sys.path. Add it defensively so the import resolves either way.
    repo_root_str = str(DEFAULT_REPO_ROOT)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    try:
        from scripts.runtime.live_ops_census import build_live_ops_census
    except Exception:  # pragma: no cover - import-path defensive
        ctx.error("live_ops_census.import", "live-ops census import failed")
        return {"enabled": False, "reason": "import_failed", "summary": {}, "surfaces": []}
    try:
        census = build_live_ops_census(repo_root=ctx.repo_root, run_probes=ctx.include_live_probes)
    except Exception:  # pragma: no cover - runtime defensive
        ctx.error("live_ops_census.build", "live-ops census build failed")
        return {"enabled": False, "reason": "build_failed", "summary": {}, "surfaces": []}

    surfaces = census.get("surfaces", []) if isinstance(census, dict) else []
    compact: list[dict[str, Any]] = []
    for surface in surfaces:
        if not isinstance(surface, dict):
            continue
        status = str(surface.get("status") or "unknown")
        desired = str(surface.get("desired_state") or "")
        age_hours = surface.get("age_hours")
        sid = str(surface.get("id") or surface.get("label") or "surface")
        compact.append(
            {
                "id": sid,
                "label": surface.get("label"),
                "status": status,
                "desired_state": desired,
                "age_hours": age_hours,
                "freshness": surface.get("freshness"),
                "human_authority_required": surface.get("human_authority_required"),
            }
        )
        stale = status == "stale"
        blocked = status == "blocked"
        desired_live_but_stopped = desired == "live" and status in {"stopped", "stale", "blocked"}
        if not (stale or blocked or desired_live_but_stopped):
            continue
        if stale:
            risk = "stale_liveness_claim"
            lane = "Needs Repair"
            next_action = "re-exercise the surface to refresh its receipt, or mark it stopped; do not trust the stale liveness claim"
        elif blocked:
            risk = "live_ops_blocked"
            lane = "Needs Repair"
            next_action = str(surface.get("next_action") or "unblock surface per live-ops census")
        else:
            risk = "desired_live_but_stopped"
            lane = "Needs Decision"
            next_action = str(surface.get("next_action") or "start the surface or revise its desired state")
        ctx.cards.append(
            _card(
                kind="live_ops_surface",
                card_id=f"live_ops:{sid}",
                title=f"{surface.get('label') or sid} — {status}",
                status=status,
                lane=lane,
                risk=risk,
                next_action=next_action,
                track=_infer_track(ctx, f"{sid} {surface.get('label') or ''}"),
                decision_type="operator_decision" if surface.get("human_authority_required") else "engineering_task",
                evidence=[
                    _evidence(
                        "scripts/runtime/live_ops_census.py",
                        kind="live_ops",
                        path="scripts/runtime/live_ops_census.py",
                        detail=f"{sid}: status={status} desired={desired} age_hours={age_hours}",
                        status=status,
                        age_hours=age_hours if isinstance(age_hours, (int, float)) else None,
                    )
                ],
                facets={
                    "tracked": True,
                    "intentional": True,
                    "live": status == "live",
                    "stale": stale,
                    "operator_decision": bool(surface.get("human_authority_required")),
                },
                raw=surface,
            )
        )

    return {
        "enabled": True,
        "schema_version": census.get("schema_version") if isinstance(census, dict) else None,
        "generated_at": census.get("generated_at") if isinstance(census, dict) else None,
        "summary": census.get("summary", {}) if isinstance(census, dict) else {},
        "surfaces": compact,
    }


def _probe_terminal_processes(ctx: ProbeContext) -> dict[str, Any]:
    root = ctx.repo_root
    tmux_result = _run(["tmux", "ls"], cwd=root, timeout=4)
    tmux_sessions: list[dict[str, Any]] = []
    if tmux_result["ok"]:
        for line in tmux_result["stdout"].splitlines():
            name = line.split(":", 1)[0].strip()
            track = _infer_track(ctx, line)
            tmux_sessions.append({"name": name, "raw": line[:300], "track": track})
            if track == "unknown":
                ctx.cards.append(
                    _card(
                        kind="tmux_session",
                        card_id=f"tmux:{name}",
                        title=f"tmux session with no owner: {name}",
                        status="orphan_candidate",
                        lane="Needs Decision",
                        risk="tmux_no_track_owner",
                        next_action="operator decision: assign session to a track or stop it manually",
                        decision_type="operator_decision",
                        evidence=[_evidence("tmux ls", kind="process", detail=line)],
                        facets={"live": True, "rogue": True, "operator_decision": True},
                    )
                )
    else:
        ctx.error("tmux.ls", tmux_result["stderr"] or "tmux ls failed")

    launchd_result = _run(["launchctl", "list"], cwd=root, timeout=5)
    launchd_jobs: list[dict[str, Any]] = []
    if launchd_result["ok"]:
        for line in launchd_result["stdout"].splitlines()[1:]:
            if not re.search(r"(dharma|swarm|a2a|codex|claude|nats|uvicorn|dashboard)", line, re.I):
                continue
            parts = line.split()
            label = parts[-1] if parts else line
            track = _infer_track(ctx, line)
            launchd_jobs.append({"label": label, "raw": line[:300], "track": track})
            if track == "unknown":
                ctx.cards.append(
                    _card(
                        kind="launchd_job",
                        card_id=f"launchd:{label}",
                        title=f"launchd job with unknown owner: {label}",
                        status="orphan_candidate",
                        lane="Needs Decision",
                        risk="launchd_no_track_owner",
                        next_action="operator decision: assign launchd job to a track or document why global",
                        decision_type="operator_decision",
                        evidence=[_evidence("launchctl list", kind="process", detail=line)],
                        facets={"live": True, "rogue": True, "operator_decision": True},
                    )
                )
    else:
        ctx.error("launchctl.list", launchd_result["stderr"] or "launchctl list failed")

    ps_result = _run(["ps", "-axo", "pid,etime,command"], cwd=root, timeout=5)
    processes: list[dict[str, Any]] = []
    if ps_result["ok"]:
        for line in ps_result["stdout"].splitlines()[1:]:
            if not re.search(r"(dharma_swarm|dharma|codex|claude|devin|auggie|nats|uvicorn|next dev|tmux|agent)", line, re.I):
                continue
            compact = re.sub(r"\s+", " ", line).strip()
            if "operator_coherence_cockpit" in compact:
                continue
            pid = compact.split(" ", 1)[0]
            track = _infer_track(ctx, compact)
            processes.append({"pid": pid, "command": compact[:260], "track": track})
    else:
        ctx.error("ps", ps_result["stderr"] or "ps failed")

    return {
        "tmux_sessions": tmux_sessions,
        "launchd_jobs": launchd_jobs,
        "processes": processes[:80],
    }


def _probe_dashboard_and_surfaces(ctx: ProbeContext) -> dict[str, Any]:
    root = ctx.repo_root
    surfaces: list[dict[str, Any]] = []
    for surface in SURFACE_PROBES:
        proofs = []
        existing = 0
        max_age: float | None = None
        for raw_path in surface["paths"]:
            path = root / raw_path
            exists = path.exists()
            if exists:
                existing += 1
            age = _file_age_hours(path)
            if age is not None:
                max_age = age if max_age is None else max(max_age, age)
            proofs.append({"path": raw_path, "exists": exists, "age_hours": age})
        status = "wired" if existing == len(surface["paths"]) else "partial" if existing else "missing"
        stale = max_age is None or max_age > 24 * 21
        surfaces.append(
            {
                "id": surface["id"],
                "label": surface["label"],
                "status": status,
                "proof_age_hours": max_age,
                "stale": stale,
                "proofs": proofs,
            }
        )
        lane = "Verified" if status == "wired" and not stale else "Needs Repair" if status != "missing" else "Needs Decision"
        ctx.cards.append(
            _card(
                kind="operator_surface",
                card_id=f"surface:{surface['id']}",
                title=surface["label"],
                status=status if not stale else f"{status}_stale",
                lane=lane,
                risk="stale_surface_proof" if stale else "surface_projection",
                next_action="refresh proof or rewire surface to current projection" if stale or status != "wired" else "keep proof current",
                track=_infer_track(ctx, f"{surface['id']} {surface['label']} {' '.join(surface['paths'])}"),
                evidence=[
                    _evidence(p["path"], path=p["path"], detail=f"exists={p['exists']}", age_hours=p["age_hours"])
                    for p in proofs
                ],
                facets={"tracked": True, "intentional": True, "stale": stale},
                raw=surfaces[-1],
            )
        )

    dashboard_files = sorted((root / "dashboard").glob("src/app/dashboard/**/page.tsx")) if (root / "dashboard").exists() else []
    abandoned_candidates = []
    for path in dashboard_files:
        age = _file_age_hours(path)
        text = _safe_read_text(path, max_chars=2000)
        if age is not None and age > 24 * 45 and not re.search(r"fetch|use[A-Z]|api|control", text):
            abandoned_candidates.append({"path": _rel(path, root), "age_hours": age})
    return {"surfaces": surfaces, "abandoned_dashboard_candidates": abandoned_candidates[:30]}


def _probe_preservation(ctx: ProbeContext, git_data: dict[str, Any]) -> dict[str, Any]:
    root = ctx.repo_root
    preservation_paths = [
        root / ".dharma" / "preservation",
        Path.home() / ".dharma" / "preservation",
        root / "reports" / "governance",
    ]
    entries: list[dict[str, Any]] = []
    for base in preservation_paths:
        if not base.exists():
            entries.append({"path": str(base), "exists": False, "file_count": 0, "latest_age_hours": None})
            continue
        files = [p for p in base.rglob("*") if p.is_file()]
        latest_age = min((_file_age_hours(p) for p in files if _file_age_hours(p) is not None), default=None)
        entries.append({"path": str(base), "exists": True, "file_count": len(files), "latest_age_hours": latest_age})
    at_risk_worktrees = [
        wt for wt in git_data.get("worktrees", [])
        if wt.get("dirty_count") or wt.get("local_only") or wt.get("detached")
    ]
    ledger = {
        "local_preservation": entries,
        "at_risk_worktree_count": len(at_risk_worktrees),
        "at_risk_worktrees": at_risk_worktrees[:20],
        "off_machine_evidence": [
            {
                "worktree": wt.get("id"),
                "branch": wt.get("branch"),
                "origin_backed": bool(wt.get("upstream")),
                "dirty_count": wt.get("dirty_count", 0),
            }
            for wt in git_data.get("worktrees", [])
        ],
    }
    if at_risk_worktrees:
        ctx.cards.append(
            _card(
                kind="preservation_risk",
                card_id="preservation:at-risk-worktrees",
                title=f"{len(at_risk_worktrees)} worktree(s) still at preservation risk",
                status="at_risk",
                lane="Needs Decision",
                risk="local_unpreserved_work",
                next_action="push, PR, receipt, or explicit operator preservation decision",
                decision_type="operator_decision",
                evidence=[_evidence("git worktree/status", kind="git", detail=json.dumps(ledger["off_machine_evidence"][:8], indent=2))],
                facets={"local_only": True, "operator_decision": True, "rogue": True},
            )
        )
    return ledger


def _probe_onboarding(ctx: ProbeContext) -> dict[str, Any]:
    """Check the canonical session-status command without mutating repo state.

    Running it on every dashboard refresh would be too heavy, so this probe
    verifies the target and command wiring and points to its contract sources.
    """
    root = ctx.repo_root
    makefile = root / "Makefile"
    text = _safe_read_text(makefile, max_chars=120_000)
    has_target = bool(re.search(r"^onboard:\s*$", text, re.M))
    target_line = ""
    if has_target:
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            if line.strip() == "onboard:":
                target_line = "\n".join(lines[idx : idx + 3])
                break
    command_mentions_agent_onboard = "scripts/governance/agent_onboard.py" in target_line
    evidence_paths = [
        "scripts/governance/agent_onboard.py",
        "docs/governance/BUILD_SESSION_ENTRYPOINT.md",
    ]
    records = []
    for raw in evidence_paths:
        path = root / raw
        records.append({"path": raw, "exists": path.exists(), "age_hours": _file_age_hours(path)})
    status = "wired" if has_target and command_mentions_agent_onboard else "missing_or_drifted"
    ctx.cards.append(
        _card(
            kind="onboarding",
            card_id="onboarding:make-onboard",
            title="make onboard session status",
            status=status,
            lane="Verified" if status == "wired" else "Needs Repair",
            risk="session_status_projection" if status == "wired" else "onboarding_entrypoint_drift",
            next_action=(
                "keep make onboard wired to scripts/governance/agent_onboard.py"
                if status == "wired"
                else "repair Makefile onboard target so sessions have canonical status"
            ),
            track="unknown",
            evidence=[
                _evidence(
                    "Makefile",
                    path="Makefile",
                    detail=target_line or "onboard target not found",
                    status=status,
                    age_hours=_file_age_hours(makefile),
                ),
                *[
                    _evidence(
                        r["path"],
                        path=r["path"],
                        detail=f"exists={r['exists']}",
                        status="present" if r["exists"] else "missing",
                        age_hours=r["age_hours"],
                    )
                    for r in records
                ],
            ],
            facets={"tracked": True, "intentional": True, "stale": status != "wired"},
            raw={"target": target_line, "evidence_paths": records},
        )
    )
    return {"status": status, "target": target_line, "evidence_paths": records}


def _sqlite_table_summary(path: Path) -> dict[str, Any]:
    try:
        uri = f"file:{path}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=1.0) as conn:
            rows = conn.execute(
                "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name"
            ).fetchall()
            tables = [str(row[0]) for row in rows]
            counts: dict[str, int | str] = {}
            for table in tables[:10]:
                try:
                    counts[table] = int(conn.execute(f'select count(*) from "{table}"').fetchone()[0])
                except Exception:  # pragma: no cover - table-specific defensive
                    counts[table] = "unreadable"
            return {"readable": True, "tables": tables[:30], "table_counts": counts}
    except Exception:
        return {"readable": False, "error": "database probe failed", "tables": [], "table_counts": {}}


def _probe_runtime_db_and_receipts(ctx: ProbeContext) -> dict[str, Any]:
    """Read-only runtime DB + receipt ledger.

    This does not claim database authority. It simply surfaces whether the
    expected local runtime DBs and receipt artifacts exist, how fresh they are,
    and whether the SQLite files can be opened in read-only mode.
    """
    root = ctx.repo_root
    db_paths = [
        root / ".dharma" / "state" / "runtime.db",
        root / ".dharma" / "db" / "runtime.db",
        Path.home() / ".dharma" / "state" / "runtime.db",
        Path.home() / ".dharma" / "db" / "runtime.db",
    ]
    seen: set[str] = set()
    db_records: list[dict[str, Any]] = []
    for path in db_paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        exists = path.exists()
        age = _file_age_hours(path)
        record = {
            "path": key,
            "exists": exists,
            "age_hours": age,
            "stale": age is not None and age > 24 * 7,
            **(_sqlite_table_summary(path) if exists else {"readable": False, "tables": [], "table_counts": {}}),
        }
        db_records.append(record)
        if exists and record["stale"]:
            ctx.cards.append(
                _card(
                    kind="runtime_db",
                    card_id=f"runtime_db:{len(db_records)}",
                    title=f"stale runtime DB: {path.name}",
                    status="stale",
                    lane="Needs Repair",
                    risk="stale_runtime_db",
                    next_action="verify whether runtime receipts still write here or retire this DB as stale",
                    evidence=[
                        _evidence(
                            key,
                            kind="runtime_db",
                            path=key,
                            detail=f"readable={record.get('readable')} tables={record.get('tables')}",
                            status="stale",
                            age_hours=age,
                        )
                    ],
                    facets={"tracked": True, "intentional": True, "stale": True},
                    raw=record,
                )
            )

    receipt_globs = [
        "reports/**/*receipt*.json",
        "reports/**/*receipt*.jsonl",
        ".swarm_collab/**/receipts/*",
        ".dharma/**/*receipt*.json",
        ".dharma/**/*receipt*.jsonl",
    ]
    receipt_files: list[Path] = []
    for pattern in receipt_globs:
        receipt_files.extend([p for p in root.glob(pattern) if p.is_file()])
    unique_receipts = sorted(set(receipt_files), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    receipt_records = [
        {"path": _rel(path, root), "age_hours": _file_age_hours(path), "size": path.stat().st_size}
        for path in unique_receipts[:50]
    ]
    if not receipt_records:
        ctx.cards.append(
            _card(
                kind="runtime_receipts",
                card_id="runtime_receipts:none-found",
                title="no local runtime/semantic receipt files found in expected paths",
                status="missing",
                lane="Needs Decision",
                risk="receipt_ledger_missing",
                next_action="confirm receipt location or wire the cockpit to the canonical receipt directory",
                decision_type="operator_decision",
                evidence=[_evidence("receipt globs", kind="receipt", detail=", ".join(receipt_globs), status="missing")],
                facets={"operator_decision": True, "stale": True},
            )
        )
    return {
        "runtime_dbs": db_records,
        "receipt_count": len(unique_receipts),
        "recent_receipts": receipt_records,
    }
