"""Operator Coherence Cockpit projection.

This module is intentionally read-only.  It does not create a new authority
file; it projects over git, governance docs, live-ops receipts/processes, and
dashboard files into a normalized dashboard/report payload.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # PyYAML is a project dependency, but keep the projection degradable.
    import yaml
except Exception:  # pragma: no cover - exercised only in broken envs
    yaml = None  # type: ignore[assignment]


SCHEMA_VERSION = "operator_coherence_cockpit.v0.1"
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSON_OUTPUT = DEFAULT_REPO_ROOT / "reports" / "governance" / "operator_coherence_cockpit.json"
DEFAULT_MARKDOWN_OUTPUT = DEFAULT_REPO_ROOT / "reports" / "governance" / "operator_coherence_cockpit.md"

KANBAN_LANES = [
    "Preserved Only",
    "Needs Decision",
    "Ready To Extract",
    "Active Branch",
    "Open PR",
    "Needs Repair",
    "Landing Queue",
    "Verified",
    "Archived",
]

READINESS_WEIGHTS = {
    "source_control_coherence": 0.20,
    "governance_legibility": 0.15,
    "test_ci_state": 0.15,
    "runtime_telemetry_liveness": 0.15,
    "operator_surface_usability": 0.10,
    "preservation_safety": 0.10,
    "external_product_proof": 0.10,
    "documentation_freshness": 0.05,
}

SURFACE_PROBES = [
    {
        "id": "dashboard",
        "label": "Dashboard app",
        "paths": ["dashboard/package.json", "dashboard/src/app/dashboard/page.tsx"],
    },
    {
        "id": "cockpit",
        "label": "Operator cockpit",
        "paths": [
            "dashboard/src/app/dashboard/cockpit/page.tsx",
            "dashboard/src/components/operator-coherence/OperatorCoherenceCockpit.tsx",
        ],
    },
    {
        "id": "control_surface_api",
        "label": "Control surface API",
        "paths": ["api/routers/control_surface.py", "dharma_swarm/operator_core/control_surface.py"],
    },
    {
        "id": "operator_coherence_api",
        "label": "Operator coherence API",
        "paths": ["api/routers/operator_coherence.py", "dharma_swarm/operator_core/operator_coherence_cockpit.py"],
    },
    {
        "id": "terminal",
        "label": "Terminal / TUI",
        "paths": ["terminal", "terminal-v2", "docs/ops/TMUX_AGENT_SUBSTRATE.md"],
    },
    {
        "id": "a2a",
        "label": "A2A substrate",
        "paths": ["dharma_swarm/a2a", "reports/a2a"],
    },
    {
        "id": "live_ops",
        "label": "Live ops census",
        "paths": ["scripts/runtime/live_ops_census.py", "docs/state/LIVE_OPS_DASHBOARD.md"],
    },
    {
        "id": "provider_model_routing",
        "label": "Provider/model routing",
        "paths": ["dharma_swarm/providers.py", "MODEL_ROUTING_MAP.md", "tests/test_model_router_telemetry.py"],
    },
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _utc_now()).isoformat()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def _file_age_hours(path: Path) -> float | None:
    try:
        return round((_utc_now().timestamp() - path.stat().st_mtime) / 3600, 2)
    except OSError:
        return None


def _safe_read_text(path: Path, max_chars: int = 80_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _age_hours_from_iso(value: Any) -> float | None:
    dt = _parse_date(value)
    if dt is None:
        return None
    return round((_utc_now() - dt).total_seconds() / 3600, 2)


def _run(cmd: list[str], *, cwd: Path, timeout: float = 6.0) -> dict[str, Any]:
    if not cmd or shutil.which(cmd[0]) is None:
        return {
            "ok": False,
            "exit_code": 127,
            "stdout": "",
            "stderr": f"{cmd[0] if cmd else 'command'} not found",
            "cmd": cmd,
        }
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "exit_code": 124,
            "stdout": exc.stdout or "",
            "stderr": f"timeout after {timeout}s",
            "cmd": cmd,
        }
    except OSError as exc:
        return {"ok": False, "exit_code": 126, "stdout": "", "stderr": str(exc), "cmd": cmd}
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "cmd": cmd,
    }


def _evidence(
    source: str,
    *,
    kind: str = "file",
    detail: str = "",
    path: str | None = None,
    status: str | None = None,
    age_hours: float | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "source": source,
        "path": path or source,
        "detail": detail,
        "status": status or "observed",
        "observed_at": _iso(),
        "age_hours": age_hours,
    }


def _card(
    *,
    kind: str,
    card_id: str,
    title: str,
    status: str,
    lane: str,
    risk: str,
    next_action: str,
    track: str = "unknown",
    branch: str = "",
    pr: str = "",
    decision_type: str = "engineering_task",
    evidence: list[dict[str, Any]] | None = None,
    facets: dict[str, Any] | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": card_id,
        "title": title,
        "status": status,
        "lane": lane if lane in KANBAN_LANES else "Needs Decision",
        "track": track or "unknown",
        "branch": branch,
        "pr": pr,
        "risk": risk,
        "next_action": next_action,
        "decision_type": decision_type,
        "evidence": evidence or [],
        "facets": {
            "tracked": False,
            "live": False,
            "stale": False,
            "preserved": False,
            "intentional": False,
            "rogue": False,
            "local_only": False,
            "origin_backed": False,
            "operator_decision": decision_type == "operator_decision",
            **(facets or {}),
        },
        "raw": raw or {},
    }


@dataclass
class ProbeContext:
    repo_root: Path
    include_github: bool = True
    include_live_probes: bool = True
    source_errors: list[dict[str, Any]] = field(default_factory=list)
    cards: list[dict[str, Any]] = field(default_factory=list)
    tracks_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    track_keywords: dict[str, list[str]] = field(default_factory=dict)

    def error(self, source: str, error: str) -> None:
        self.source_errors.append({"source": source, "error": error, "timestamp": _iso()})


def _parse_porcelain_worktrees(stdout: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in stdout.splitlines():
        if not line.strip():
            if current:
                records.append(current)
                current = {}
            continue
        if " " in line:
            key, value = line.split(" ", 1)
        else:
            key, value = line, True
        if key == "worktree" and current:
            records.append(current)
            current = {}
        if key in current:
            existing = current[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                current[key] = [existing, value]
        else:
            current[key] = value
    if current:
        records.append(current)
    return records


def _parse_status(stdout: str) -> dict[str, Any]:
    lines = stdout.splitlines()
    branch_line = lines[0] if lines and lines[0].startswith("##") else ""
    files = lines[1:] if branch_line else lines
    branch = "unknown"
    ahead = 0
    behind = 0
    if branch_line:
        branch_text = branch_line[3:]
        branch = branch_text.split("...", 1)[0].split(" [", 1)[0].strip()
        ahead_match = re.search(r"ahead (\d+)", branch_line)
        behind_match = re.search(r"behind (\d+)", branch_line)
        ahead = int(ahead_match.group(1)) if ahead_match else 0
        behind = int(behind_match.group(1)) if behind_match else 0
    tracked_dirty = [line for line in files if not line.startswith("??")]
    untracked = [line[3:] if line.startswith("?? ") else line for line in files if line.startswith("??")]
    deleted = [line for line in files if line[:2].strip() == "D" or line.startswith(" D")]
    return {
        "branch_line": branch_line,
        "branch": branch,
        "files": files,
        "dirty_count": len(files),
        "tracked_dirty_count": len(tracked_dirty),
        "untracked_count": len(untracked),
        "deleted_count": len(deleted),
        "dirty_sample": files[:30],
        "untracked_sample": untracked[:30],
        "ahead": ahead,
        "behind": behind,
    }


def _infer_track(ctx: ProbeContext, text: str) -> str:
    haystack = text.lower()
    best = ("unknown", 0)
    for track_id, keywords in ctx.track_keywords.items():
        score = sum(1 for kw in keywords if kw and kw.lower() in haystack)
        if score > best[1]:
            best = (track_id, score)
    return best[0]


def _probe_governance(ctx: ProbeContext) -> dict[str, Any]:
    root = ctx.repo_root
    active_path = root / "docs" / "governance" / "ACTIVE_TRACK.yaml"
    evidence_path = root / "reports" / "governance" / "active_track_evidence.json"
    broken_path = root / "docs" / "state" / "BROKEN_REGISTER.md"
    proposed_dir = root / "docs" / "governance" / "proposed_tracks"

    active_doc = _safe_yaml(active_path)
    if not active_doc:
        ctx.error("docs/governance/ACTIVE_TRACK.yaml", "could not parse ACTIVE_TRACK.yaml")
    evidence_doc = _safe_json(evidence_path)
    active_evidence = {
        str(t.get("id")): t
        for t in evidence_doc.get("active_tracks", [])
        if isinstance(t, dict) and t.get("id")
    }
    tracks: list[dict[str, Any]] = []

    for section, lifecycle in (
        ("active_tracks", "active"),
        ("closed_tracks", "closed"),
        ("archived_tracks", "archived"),
    ):
        for track in active_doc.get(section, []) or []:
            if not isinstance(track, dict):
                continue
            track_id = str(track.get("id") or track.get("name") or "unknown")
            evidence = active_evidence.get(track_id, {})
            verified_at = track.get("verified_at") or evidence.get("verified_at")
            ttl_days = int(track.get("ttl_days") or evidence.get("ttl_days") or 0)
            verified_dt = _parse_date(verified_at)
            stale = False
            if verified_dt and ttl_days:
                stale = (_utc_now() - verified_dt).total_seconds() > ttl_days * 86400
            progress = evidence.get("completion_progress") or {}
            total = int(progress.get("total") or 0)
            passed = int(progress.get("passed") or 0)
            readiness = round((passed / total) * 100, 1) if total else (100.0 if lifecycle != "active" else 0.0)
            status = str(track.get("status") or lifecycle).lower()
            shippable = bool(evidence.get("shippable")) or status == "shippable"
            lane = "Archived" if lifecycle != "active" else ("Verified" if shippable and not stale else "Needs Repair" if stale else "Active Branch")
            risk = "stale_claim" if stale else ("no_completion_evidence" if not evidence and lifecycle == "active" else "declared_intent")
            next_action = (
                "operator lifecycle review: stale verified_at exceeds ttl_days"
                if stale
                else "operator lifecycle review: shippable track can be landed/closed"
                if shippable and lifecycle == "active"
                else "continue engineering against declared completion criteria"
                if lifecycle == "active"
                else "archived/closed; keep as historical evidence"
            )
            item = {
                "id": track_id,
                "name": str(track.get("name") or track_id),
                "lifecycle": lifecycle,
                "status": status,
                "owner": track.get("owner") or "",
                "serves": track.get("serves") or "",
                "branch": track.get("branch") or "",
                "pr": track.get("pr") or "",
                "owned_surfaces": track.get("owned_surfaces") or [],
                "verified_at": verified_at,
                "ttl_days": ttl_days,
                "stale": stale,
                "readiness": readiness,
                "shippable": shippable,
                "completion_progress": {"passed": passed, "total": total},
                "evidence_present": bool(evidence),
                "next_items": track.get("next_items") or [],
                "evidence": [
                    _evidence("docs/governance/ACTIVE_TRACK.yaml", path="docs/governance/ACTIVE_TRACK.yaml", detail=section),
                    _evidence(
                        "reports/governance/active_track_evidence.json",
                        path="reports/governance/active_track_evidence.json",
                        detail="matched track evidence" if evidence else "no matching evidence row",
                        status="matched" if evidence else "missing",
                        age_hours=_file_age_hours(evidence_path),
                    ),
                ],
            }
            tracks.append(item)
            ctx.tracks_by_id[track_id] = item
            keywords = [track_id, str(track.get("name") or "")]
            keywords.extend(str(s) for s in (track.get("owned_surfaces") or []))
            keywords.extend(str(s) for s in (track.get("moves_vital_signs") or []))
            ctx.track_keywords[track_id] = keywords
            ctx.cards.append(
                _card(
                    kind="track",
                    card_id=f"track:{track_id}",
                    title=item["name"],
                    status="stale" if stale else "shippable" if shippable else status,
                    lane=lane,
                    risk=risk,
                    next_action=next_action,
                    track=track_id,
                    branch=item["branch"],
                    pr=item["pr"],
                    decision_type="operator_decision" if shippable or stale else "engineering_task",
                    evidence=item["evidence"],
                    facets={
                        "tracked": True,
                        "intentional": True,
                        "stale": stale,
                        "preserved": lifecycle != "active",
                        "operator_decision": shippable or stale,
                    },
                    raw=item,
                )
            )

    proposed_tracks: list[dict[str, Any]] = []
    if proposed_dir.exists():
        for path in sorted(proposed_dir.glob("*.yaml")):
            proposal = _safe_yaml(path)
            proposal_id = str(proposal.get("id") or path.stem) if proposal else path.stem
            proposed_tracks.append({"id": proposal_id, "path": _rel(path, root), "parsed": bool(proposal)})
            ctx.cards.append(
                _card(
                    kind="proposed_track",
                    card_id=f"proposed_track:{proposal_id}",
                    title=f"Proposed track: {proposal_id}",
                    status="proposed",
                    lane="Needs Decision",
                    risk="unopened_intent",
                    next_action="operator decision: open, reject, or archive proposed track",
                    track=proposal_id,
                    decision_type="operator_decision",
                    evidence=[_evidence(_rel(path, root), path=_rel(path, root), detail="proposed track file")],
                    facets={"tracked": True, "intentional": True, "operator_decision": True},
                )
            )

    broken_entries: list[dict[str, Any]] = []
    broken_text = _safe_read_text(broken_path)
    broken_lines = broken_text.splitlines()
    heading_indices = [
        (idx, line.strip())
        for idx, line in enumerate(broken_lines, start=1)
        if re.match(r"^###\s+BR-\d+", line.strip())
    ]
    for h_pos, (line_no, heading) in enumerate(heading_indices):
        next_line = heading_indices[h_pos + 1][0] if h_pos + 1 < len(heading_indices) else len(broken_lines) + 1
        block = "\n".join(broken_lines[line_no - 1 : next_line - 1])
        status_match = re.search(r"^\s*-\s+\*\*status:\*\*\s*(.+)$", block, re.I | re.M)
        status_text = status_match.group(1).strip() if status_match else ""
        if re.match(r"^\**\s*(FIXED|CLOSED)\b", status_text, re.I):
            continue
        is_closed = re.search(r"\b(FIXED|CLOSED)\b", status_text, re.I)
        is_open_like = (not status_text) or re.search(r"\b(OPEN|PARTIAL|INVESTIGATING|WORKAROUND|BLOCKER|DEGRADED|STALE)\b", status_text, re.I)
        if is_closed and not re.search(r"\b(OPEN|PARTIAL|WORKAROUND|INVESTIGATING)\b", status_text, re.I):
            continue
        if not is_open_like:
            continue
        entry = {"line": line_no, "text": heading[:240], "status": status_text[:240]}
        broken_entries.append(entry)
        if len(broken_entries) <= 25:
            ctx.cards.append(
                _card(
                    kind="broken_register",
                    card_id=f"broken:{line_no}",
                    title=heading.replace("### ", "", 1)[:140],
                    status="open",
                    lane="Needs Repair",
                    risk="known_breakage",
                    next_action="repair or explicitly retire this broken-register item",
                    track=_infer_track(ctx, block),
                    evidence=[
                        _evidence(
                            "docs/state/BROKEN_REGISTER.md",
                            path="docs/state/BROKEN_REGISTER.md",
                            detail=f"line {line_no}: {heading[:180]} | status: {status_text[:160]}",
                            status="open",
                            age_hours=_file_age_hours(broken_path),
                        )
                    ],
                    facets={"tracked": True, "intentional": True, "stale": (_file_age_hours(broken_path) or 0) > 24 * 14},
                )
            )

    return {
        "active_track_path": "docs/governance/ACTIVE_TRACK.yaml",
        "active_track_age_hours": _file_age_hours(active_path),
        "evidence_path": "reports/governance/active_track_evidence.json",
        "evidence_age_hours": _file_age_hours(evidence_path),
        "policy": active_doc.get("track_policy") or {},
        "tracks": tracks,
        "active_count": len([t for t in tracks if t["lifecycle"] == "active"]),
        "closed_count": len([t for t in tracks if t["lifecycle"] != "active"]),
        "proposed_tracks": proposed_tracks,
        "broken_register": {
            "path": "docs/state/BROKEN_REGISTER.md",
            "age_hours": _file_age_hours(broken_path),
            "open_like_count": len(broken_entries),
            "sample": broken_entries[:20],
        },
    }


def _probe_git(ctx: ProbeContext) -> dict[str, Any]:
    root = ctx.repo_root
    status_result = _run(["git", "status", "--short", "--branch"], cwd=root, timeout=5)
    if not status_result["ok"]:
        ctx.error("git.status", status_result["stderr"] or "git status failed")
    main_status = _parse_status(status_result["stdout"])
    head = _run(["git", "rev-parse", "--short", "HEAD"], cwd=root, timeout=3)
    main_status["head"] = head["stdout"].strip() if head["ok"] else ""

    stash_result = _run(["git", "stash", "list", "--date=iso"], cwd=root, timeout=5)
    stashes = []
    for line in stash_result["stdout"].splitlines() if stash_result["ok"] else []:
        stash_id = line.split(":", 1)[0]
        stashes.append({"id": stash_id, "summary": line[:300]})
        ctx.cards.append(
            _card(
                kind="stash",
                card_id=f"stash:{stash_id}",
                title=line[:120],
                status="stashed",
                lane="Preserved Only",
                risk="hidden_local_work",
                next_action="operator decision: inspect and either declare, apply to a branch, or archive",
                track=_infer_track(ctx, line),
                decision_type="operator_decision",
                evidence=[_evidence("git stash list", kind="git", detail=line, status="stashed")],
                facets={"tracked": False, "preserved": True, "intentional": False, "rogue": True, "operator_decision": True},
            )
        )

    wt_result = _run(["git", "worktree", "list", "--porcelain"], cwd=root, timeout=5)
    worktrees = _parse_porcelain_worktrees(wt_result["stdout"]) if wt_result["ok"] else []
    if not wt_result["ok"]:
        ctx.error("git.worktree", wt_result["stderr"] or "git worktree list failed")
    for wt in worktrees:
        wt_path = Path(str(wt.get("worktree", "")))
        exists = wt_path.exists()
        branch_ref = str(wt.get("branch") or "")
        branch = branch_ref.replace("refs/heads/", "") if branch_ref else "detached"
        status = _parse_status(_run(["git", "status", "--short", "--branch"], cwd=wt_path, timeout=5)["stdout"]) if exists else {}
        upstream = _run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=wt_path, timeout=3) if exists and branch != "detached" else {"ok": False, "stdout": "", "stderr": "detached or missing"}
        upstream_name = upstream["stdout"].strip() if upstream.get("ok") else ""
        ahead = int(status.get("ahead") or 0)
        behind = int(status.get("behind") or 0)
        local_only = bool(branch != "detached" and not upstream_name)
        dirty = int(status.get("dirty_count") or 0)
        prunable = "prunable" in wt
        track = _infer_track(ctx, f"{wt_path.name} {branch} {' '.join(status.get('dirty_sample') or [])}")
        lane = (
            "Needs Repair"
            if dirty or prunable
            else "Needs Decision"
            if branch == "detached" or local_only
            else "Active Branch"
            if ahead or behind
            else "Verified"
        )
        risk = (
            "dirty_worktree"
            if dirty
            else "prunable_worktree"
            if prunable
            else "detached_worktree"
            if branch == "detached"
            else "local_only_branch"
            if local_only
            else "branch_diverged"
            if ahead or behind
            else "clean_origin_backed"
        )
        next_action = (
            "inspect dirty files; declare/extract to track branch before landing"
            if dirty
            else "operator decision: recover or prune missing worktree reference"
            if prunable
            else "operator decision: attach detached worktree to a named branch or archive"
            if branch == "detached"
            else "publish branch or declare why it remains local-only"
            if local_only
            else "reconcile branch with upstream"
            if ahead or behind
            else "no immediate source-control action"
        )
        wt_record = {
            **status,
            "path": str(wt_path),
            "id": wt_path.name,
            "exists": exists,
            "branch": branch,
            "status_branch": status.get("branch"),
            "head": wt.get("HEAD", ""),
            "detached": branch == "detached",
            "prunable": prunable,
            "upstream": upstream_name,
            "ahead": ahead,
            "behind": behind,
            "local_only": local_only,
        }
        ctx.cards.append(
            _card(
                kind="worktree",
                card_id=f"worktree:{wt_path.name}",
                title=f"{wt_path.name} ({branch})",
                status="dirty" if dirty else "prunable" if prunable else "detached" if branch == "detached" else "clean",
                lane=lane,
                risk=risk,
                next_action=next_action,
                track=track,
                branch=branch,
                decision_type="operator_decision" if branch == "detached" or local_only or prunable else "engineering_task",
                evidence=[
                    _evidence("git worktree list --porcelain", kind="git", detail=str(wt)),
                    _evidence("git status --short --branch", kind="git", detail=(status.get("branch_line") or "")[:220]),
                ],
                facets={
                    "tracked": track != "unknown",
                    "intentional": track != "unknown",
                    "rogue": track == "unknown" and (dirty > 0 or local_only or branch == "detached"),
                    "local_only": local_only or ahead > 0,
                    "origin_backed": bool(upstream_name),
                    "preserved": bool(upstream_name) and dirty == 0,
                },
                raw=wt_record,
            )
        )
        if dirty:
            ctx.cards.append(
                _card(
                    kind="dirty_files",
                    card_id=f"dirty:{wt_path.name}",
                    title=f"{dirty} dirty file(s) in {wt_path.name}",
                    status="dirty",
                    lane="Needs Repair",
                    risk="local_only_work",
                    next_action="triage dirty files into tracked branch, PR, or explicit discard plan",
                    track=track,
                    branch=branch,
                    evidence=[_evidence("git status --short", kind="git", detail="\n".join(status.get("dirty_sample") or []))],
                    facets={
                        "tracked": False,
                        "intentional": track != "unknown",
                        "rogue": track == "unknown",
                        "local_only": True,
                        "origin_backed": bool(upstream_name),
                    },
                    raw={"dirty_sample": status.get("dirty_sample"), "untracked_sample": status.get("untracked_sample")},
                )
            )

    return {
        "main": main_status,
        "stashes": stashes,
        "worktrees": [
            card["raw"] for card in ctx.cards if card["kind"] == "worktree"
        ],
        "worktree_branches": sorted(
            {
                str(card["raw"].get("branch"))
                for card in ctx.cards
                if card["kind"] == "worktree" and card["raw"].get("branch")
            }
        ),
    }


def _parse_upstream_track(track: str) -> dict[str, Any]:
    """Parse a `git for-each-ref` upstream:track field like `[ahead 5, behind 804]`."""
    ahead = behind = 0
    gone = "gone" in track
    ahead_match = re.search(r"ahead (\d+)", track)
    behind_match = re.search(r"behind (\d+)", track)
    if ahead_match:
        ahead = int(ahead_match.group(1))
    if behind_match:
        behind = int(behind_match.group(1))
    return {"ahead": ahead, "behind": behind, "gone": gone}


# Cap how many per-branch cards we emit so a 200-branch repo does not flood the
# board. Counts in the summary are always complete; cards are the risky subset.
BRANCH_CARD_CAP = 40


def _probe_branches(ctx: ProbeContext, git_data: dict[str, Any]) -> dict[str, Any]:
    """Enumerate ALL local branches, not just the few checked out in worktrees.

    The worktree probe only sees branches that happen to be checked out. A repo
    can carry hundreds of local branches that are unpushed, orphaned (upstream
    `[gone]`), or ahead of origin — exactly the rogue/local-only work the cockpit
    must surface. This probe reads them read-only via `git for-each-ref`.
    """
    root = ctx.repo_root
    worktree_branches = set(git_data.get("worktree_branches") or [])
    fmt = "%(refname:short)%09%(upstream:short)%09%(upstream:track)%09%(committerdate:iso8601)"
    result = _run(["git", "for-each-ref", f"--format={fmt}", "refs/heads"], cwd=root, timeout=10)
    if not result["ok"]:
        ctx.error("git.for_each_ref", result["stderr"] or "git for-each-ref failed")
        return {"total": 0, "local_only": 0, "unpushed_ahead": 0, "orphaned_gone": 0, "stale": 0, "branches": []}

    branches: list[dict[str, Any]] = []
    counts = {"total": 0, "local_only": 0, "unpushed_ahead": 0, "orphaned_gone": 0, "stale": 0, "carded": 0}
    for line in result["stdout"].splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        name = parts[0].strip()
        if not name:
            continue
        upstream = parts[1].strip() if len(parts) > 1 else ""
        track = parts[2].strip() if len(parts) > 2 else ""
        committed = parts[3].strip() if len(parts) > 3 else ""
        parsed = _parse_upstream_track(track)
        age_hours = _age_hours_from_iso(committed)
        stale = age_hours is not None and age_hours > 24 * 30
        local_only = not upstream
        unpushed = bool(upstream) and not parsed["gone"] and parsed["ahead"] > 0
        orphaned = parsed["gone"]
        counts["total"] += 1
        if local_only:
            counts["local_only"] += 1
        if unpushed:
            counts["unpushed_ahead"] += 1
        if orphaned:
            counts["orphaned_gone"] += 1
        if stale:
            counts["stale"] += 1
        record = {
            "branch": name,
            "upstream": upstream,
            "ahead": parsed["ahead"],
            "behind": parsed["behind"],
            "gone": parsed["gone"],
            "local_only": local_only,
            "unpushed": unpushed,
            "in_worktree": name in worktree_branches,
            "age_hours": age_hours,
            "stale": stale,
            "last_commit": committed,
        }
        branches.append(record)

        # Cards: only risky branches, and never duplicate a worktree card.
        if name in worktree_branches:
            continue
        is_risky = orphaned or unpushed or local_only
        if not is_risky or counts["carded"] >= BRANCH_CARD_CAP:
            continue
        track_owner = _infer_track(ctx, name)
        if orphaned:
            risk = "orphaned_upstream_gone"
            lane = "Needs Decision"
            status = "orphaned"
            next_action = "operator decision: upstream is gone — re-push, rebase onto a live base, or archive/delete branch"
        elif unpushed:
            risk = "unpushed_commits"
            lane = "Needs Decision" if stale else "Active Branch"
            status = "ahead_of_origin"
            next_action = f"push {parsed['ahead']} local commit(s) or declare why this branch stays local"
        else:  # local_only (no upstream at all)
            risk = "local_only_branch"
            lane = "Needs Decision"
            status = "local_only"
            next_action = "publish branch to origin, fold into a track branch, or archive if abandoned"
        counts["carded"] += 1
        ctx.cards.append(
            _card(
                kind="branch",
                card_id=f"branch:{name}",
                title=f"branch {name}" + (f" (ahead {parsed['ahead']})" if parsed["ahead"] else ""),
                status=status,
                lane=lane,
                risk=risk,
                next_action=next_action,
                track=track_owner,
                branch=name,
                decision_type="operator_decision",
                evidence=[
                    _evidence(
                        "git for-each-ref refs/heads",
                        kind="git",
                        detail=f"{name} upstream={upstream or 'none'} track={track or 'none'} last_commit={committed}",
                        status=status,
                        age_hours=age_hours,
                    )
                ],
                facets={
                    "tracked": track_owner != "unknown",
                    "intentional": track_owner != "unknown",
                    "rogue": track_owner == "unknown",
                    "stale": stale,
                    "local_only": local_only or unpushed,
                    "origin_backed": bool(upstream) and not orphaned,
                    "preserved": bool(upstream) and not orphaned and not unpushed,
                    "operator_decision": True,
                },
                raw=record,
            )
        )

    counts.pop("carded", None)
    return {**counts, "branches": branches[:300]}


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
    except Exception as exc:  # pragma: no cover - import-path defensive
        ctx.error("live_ops_census.import", str(exc))
        return {"enabled": False, "reason": "import_failed", "summary": {}, "surfaces": []}
    try:
        census = build_live_ops_census(repo_root=ctx.repo_root, run_probes=ctx.include_live_probes)
    except Exception as exc:  # pragma: no cover - runtime defensive
        ctx.error("live_ops_census.build", str(exc))
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
    """Check the canonical onboarding door without mutating repo state.

    The project defines `make onboard` as the human/agent orientation entrypoint.
    Running it on every dashboard refresh would be too heavy and can depend on
    local terminal affordances, so this probe verifies the target and command
    wiring read-only and points to the evidence files it projects from.
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
        "reports/governance/active_track_evidence.json",
        "reports/governance/active_track_evidence.md",
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
            title="make onboard canonical orientation door",
            status=status,
            lane="Verified" if status == "wired" else "Needs Repair",
            risk="onboarding_projection" if status == "wired" else "onboarding_entrypoint_drift",
            next_action=(
                "keep make onboard wired to scripts/governance/agent_onboard.py"
                if status == "wired"
                else "repair Makefile onboard target so fresh agents have a canonical door"
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
                except Exception as exc:  # pragma: no cover - table-specific defensive
                    counts[table] = f"unreadable: {exc}"
            return {"readable": True, "tables": tables[:30], "table_counts": counts}
    except Exception as exc:
        return {"readable": False, "error": str(exc), "tables": [], "table_counts": {}}


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


def _probe_github(ctx: ProbeContext) -> dict[str, Any]:
    root = ctx.repo_root
    if not ctx.include_github:
        return {"enabled": False, "reason": "disabled", "prs": [], "ci": []}
    auth = _run(["gh", "auth", "status"], cwd=root, timeout=6)
    if not auth["ok"]:
        ctx.error("github.auth", "gh auth unavailable; PR/CI triage omitted")
        return {"enabled": False, "reason": "gh_auth_unavailable", "prs": [], "ci": []}
    pr_result = _run(
        [
            "gh",
            "pr",
            "list",
            "--limit",
            "50",
            "--json",
            "number,title,headRefName,baseRefName,state,isDraft,updatedAt,mergeStateStatus,statusCheckRollup,url",
        ],
        cwd=root,
        timeout=12,
    )
    if not pr_result["ok"]:
        ctx.error("github.pr_list", pr_result["stderr"] or "gh pr list failed")
        return {"enabled": True, "reason": "pr_list_failed", "prs": [], "ci": []}
    try:
        prs = json.loads(pr_result["stdout"])
        if not isinstance(prs, list):
            prs = []
    except json.JSONDecodeError as exc:
        ctx.error("github.pr_list", f"invalid JSON: {exc}")
        prs = []
    for pr in prs:
        updated_age = _age_hours_from_iso(pr.get("updatedAt"))
        checks = pr.get("statusCheckRollup") or []
        failed = [c for c in checks if isinstance(c, dict) and str(c.get("conclusion") or c.get("status")).upper() in {"FAILURE", "FAILED", "CANCELLED", "TIMED_OUT"}]
        pending = [c for c in checks if isinstance(c, dict) and str(c.get("status")).upper() not in {"COMPLETED", "SUCCESS"} and not c.get("conclusion")]
        status = "blocked" if failed else "pending" if pending else "open"
        stale = bool(updated_age and updated_age > 24 * 14)
        branch = str(pr.get("headRefName") or "")
        ctx.cards.append(
            _card(
                kind="pull_request",
                card_id=f"pr:{pr.get('number')}",
                title=f"PR #{pr.get('number')}: {pr.get('title')}",
                status="stale" if stale else status,
                lane="Needs Repair" if failed or stale else "Open PR",
                risk="ci_failed" if failed else "stale_pr" if stale else "open_review_surface",
                next_action="inspect failed CI logs" if failed else "operator review/merge ordering" if not stale else "close, refresh, or merge stale PR",
                track=_infer_track(ctx, f"{branch} {pr.get('title')}"),
                branch=branch,
                pr=str(pr.get("number") or ""),
                decision_type="operator_decision" if stale or not failed else "engineering_task",
                evidence=[_evidence("gh pr list", kind="github", detail=str(pr.get("url") or ""), age_hours=updated_age)],
                facets={
                    "tracked": True,
                    "origin_backed": True,
                    "stale": stale,
                    "operator_decision": stale or not failed,
                },
                raw=pr,
            )
        )
    return {"enabled": True, "prs": prs}


def _compute_readiness(
    *,
    repo_root: Path,
    governance: dict[str, Any],
    git_data: dict[str, Any],
    terminal: dict[str, Any],
    live_ops: dict[str, Any],
    surfaces: dict[str, Any],
    preservation: dict[str, Any],
    github: dict[str, Any],
    cards: list[dict[str, Any]],
) -> dict[str, Any]:
    worktrees = git_data.get("worktrees", [])
    dirty_wt = sum(1 for wt in worktrees if wt.get("dirty_count"))
    detached_wt = sum(1 for wt in worktrees if wt.get("detached"))
    local_only = sum(1 for wt in worktrees if wt.get("local_only") or wt.get("ahead"))
    branch_census = git_data.get("branch_census", {})
    local_only_branches = int(branch_census.get("local_only", 0))
    unpushed_branches = int(branch_census.get("unpushed_ahead", 0))
    orphaned_branches = int(branch_census.get("orphaned_gone", 0))
    # Branch sprawl is a real source-control-coherence signal but should not
    # zero the score on its own; cap its contribution.
    branch_penalty = min(40, local_only_branches * 1 + unpushed_branches * 2 + orphaned_branches * 2)
    source_score = max(
        0,
        100
        - dirty_wt * 14
        - detached_wt * 8
        - local_only * 7
        - len(git_data.get("stashes", [])) * 4
        - branch_penalty,
    )

    active = governance.get("active_count", 0)
    max_active = int((governance.get("policy") or {}).get("max_active") or 0)
    stale_tracks = sum(1 for t in governance.get("tracks", []) if t.get("lifecycle") == "active" and t.get("stale"))
    no_evidence = sum(1 for t in governance.get("tracks", []) if t.get("lifecycle") == "active" and not t.get("evidence_present"))
    governance_score = max(0, 100 - max(0, active - max_active) * 20 - stale_tracks * 12 - no_evidence * 10)
    if active == 0:
        governance_score = min(governance_score, 35)

    prs = github.get("prs", [])
    if github.get("enabled"):
        failed_prs = sum(1 for c in cards if c["kind"] == "pull_request" and c["risk"] == "ci_failed")
        stale_prs = sum(1 for c in cards if c["kind"] == "pull_request" and c["risk"] == "stale_pr")
        test_ci_score = max(0, 80 - failed_prs * 20 - stale_prs * 10)
    else:
        shippable = sum(1 for t in governance.get("tracks", []) if t.get("shippable"))
        test_ci_score = min(60, 25 + shippable * 4)

    orphan_sessions = sum(1 for c in cards if c["kind"] in {"tmux_session", "launchd_job"} and c["risk"].endswith("no_track_owner"))
    live_count = len(terminal.get("tmux_sessions", [])) + len(terminal.get("launchd_jobs", []))
    lo_summary = live_ops.get("summary", {}) if live_ops.get("enabled") else {}
    lo_by_status = lo_summary.get("by_status", {}) if isinstance(lo_summary, dict) else {}
    lo_live = int(lo_by_status.get("live", 0))
    lo_stale = int(lo_by_status.get("stale", 0))
    lo_blocked = int(lo_by_status.get("blocked", 0))
    lo_total = int(lo_summary.get("total", 0)) if isinstance(lo_summary, dict) else 0
    if lo_total:
        # Anchor runtime score on the canonical live-ops census: ratio of live
        # surfaces, penalized for stale/blocked, with a small bonus for any
        # observed terminal/process owners.
        runtime_score = max(
            0,
            round((lo_live / lo_total) * 100) - lo_stale * 6 - lo_blocked * 8 - orphan_sessions * 2,
        )
        runtime_score = min(100, runtime_score + (5 if live_count else 0))
    else:
        runtime_score = max(0, (65 if live_count else 35) - orphan_sessions * 8)

    wired_surfaces = sum(1 for s in surfaces.get("surfaces", []) if s.get("status") == "wired")
    surface_count = len(surfaces.get("surfaces", [])) or 1
    stale_surfaces = sum(1 for s in surfaces.get("surfaces", []) if s.get("stale"))
    surface_score = max(0, round((wired_surfaces / surface_count) * 100) - stale_surfaces * 6)

    preservation_score = max(0, 75 - preservation.get("at_risk_worktree_count", 0) * 9)
    if any(e.get("exists") and e.get("file_count", 0) for e in preservation.get("local_preservation", [])):
        preservation_score = min(100, preservation_score + 10)

    revenue_tracks = [t for t in governance.get("tracks", []) if t.get("serves") == "revenue-external-humans-served"]
    a2a_receipts = (repo_root / "reports" / "a2a").exists()
    external_score = 30 + (20 if revenue_tracks else 0) + (15 if a2a_receipts else 0)
    external_score = min(100, external_score)

    doc_ages = [
        governance.get("active_track_age_hours"),
        governance.get("evidence_age_hours"),
        (governance.get("broken_register") or {}).get("age_hours"),
    ]
    fresh_docs = [age for age in doc_ages if age is not None and age <= 24 * 14]
    doc_score = round((len(fresh_docs) / max(1, len([a for a in doc_ages if a is not None]))) * 100)

    categories = {
        "source_control_coherence": {
            "score": round(source_score, 1),
            "weight": READINESS_WEIGHTS["source_control_coherence"],
            "why": (
                f"{dirty_wt} dirty worktrees, {detached_wt} detached, {local_only} local-only/ahead worktrees, "
                f"{len(git_data.get('stashes', []))} stashes; "
                f"{branch_census.get('total', 0)} local branches "
                f"({local_only_branches} local-only, {unpushed_branches} unpushed-ahead, {orphaned_branches} orphaned)"
            ),
        },
        "governance_legibility": {
            "score": round(governance_score, 1),
            "weight": READINESS_WEIGHTS["governance_legibility"],
            "why": f"{active} active tracks, max {max_active or 'unknown'}, {stale_tracks} stale, {no_evidence} lacking evidence",
        },
        "test_ci_state": {
            "score": round(test_ci_score, 1),
            "weight": READINESS_WEIGHTS["test_ci_state"],
            "why": "GitHub PR/CI available" if github.get("enabled") else "GitHub unavailable; estimated from active-track evidence",
        },
        "runtime_telemetry_liveness": {
            "score": round(runtime_score, 1),
            "weight": READINESS_WEIGHTS["runtime_telemetry_liveness"],
            "why": (
                f"live-ops census: {lo_live}/{lo_total} surfaces live, {lo_stale} stale, {lo_blocked} blocked; "
                f"{live_count} terminal/process owners, {orphan_sessions} orphan candidates"
                if lo_total
                else f"{live_count} live terminal/process owners observed, {orphan_sessions} orphan candidates (live-ops census unavailable)"
            ),
        },
        "operator_surface_usability": {
            "score": round(surface_score, 1),
            "weight": READINESS_WEIGHTS["operator_surface_usability"],
            "why": f"{wired_surfaces}/{surface_count} expected operator surfaces wired, {stale_surfaces} stale proofs",
        },
        "preservation_safety": {
            "score": round(preservation_score, 1),
            "weight": READINESS_WEIGHTS["preservation_safety"],
            "why": f"{preservation.get('at_risk_worktree_count', 0)} worktrees at local preservation risk",
        },
        "external_product_proof": {
            "score": round(external_score, 1),
            "weight": READINESS_WEIGHTS["external_product_proof"],
            "why": f"{len(revenue_tracks)} revenue/external-human track(s); A2A receipt dir exists={a2a_receipts}",
        },
        "documentation_freshness": {
            "score": round(doc_score, 1),
            "weight": READINESS_WEIGHTS["documentation_freshness"],
            "why": "freshness of ACTIVE_TRACK, active_track_evidence, BROKEN_REGISTER",
        },
    }
    total = sum(v["score"] * v["weight"] for v in categories.values())
    return {
        "score": round(total, 1),
        "weights": READINESS_WEIGHTS,
        "categories": categories,
        "interpretation": "computed projection; not a final truth claim",
    }


def _build_kanban(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "lane": lane,
            "count": len([c for c in cards if c.get("lane") == lane]),
            "cards": [c for c in cards if c.get("lane") == lane][:80],
        }
        for lane in KANBAN_LANES
    ]


def _top_actions(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risk_rank = {
        "local_unpreserved_work": 0,
        "dirty_worktree": 1,
        "local_only_work": 1,
        "tmux_no_track_owner": 2,
        "launchd_no_track_owner": 2,
        "ci_failed": 3,
        "stale_claim": 4,
        "stale_pr": 5,
    }
    candidates = [c for c in cards if c.get("next_action")]
    candidates.sort(key=lambda c: (risk_rank.get(c.get("risk"), 99), 0 if c["facets"].get("operator_decision") else 1, c.get("title", "")))
    return [
        {
            "title": c["title"],
            "kind": c["kind"],
            "risk": c["risk"],
            "next_action": c["next_action"],
            "evidence": c.get("evidence", [])[:2],
        }
        for c in candidates[:3]
    ]


def _definition_answers(payload: dict[str, Any]) -> dict[str, Any]:
    cards = payload["cards"]
    return {
        "what_is_safe": [
            c for c in cards
            if c["facets"].get("preserved") or c["lane"] in {"Verified", "Archived", "Preserved Only"}
        ][:12],
        "what_is_dirty": [c for c in cards if c["status"] == "dirty" or c["risk"] in {"dirty_worktree", "local_only_work"}][:12],
        "what_is_abandoned": [
            *[
                _card(
                    kind="dashboard_abandoned_candidate",
                    card_id=f"dashboard_abandoned:{i}",
                    title=item["path"],
                    status="stale_candidate",
                    lane="Needs Decision",
                    risk="abandoned_dashboard_candidate",
                    next_action="verify route usage or archive surface",
                    evidence=[_evidence(item["path"], path=item["path"], age_hours=item.get("age_hours"))],
                    facets={"stale": True, "operator_decision": True},
                )
                for i, item in enumerate(payload["operator_surfaces"].get("abandoned_dashboard_candidates", [])[:8])
            ],
            *[c for c in cards if c["risk"] in {"stale_pr", "stale_surface_proof", "stale_claim"}][:8],
        ][:12],
        "what_is_live": [c for c in cards if c["facets"].get("live")][:12],
        "what_is_blocked": [c for c in cards if c["lane"] == "Needs Repair" or c["status"] in {"blocked", "open"}][:12],
        "what_might_be_rogue": [c for c in cards if c["facets"].get("rogue")][:12],
        "what_should_i_do_next": payload["executive"]["next_3_actions"],
        "prod_readiness": payload["readiness"],
    }


def _probe_operating_loops(ctx: ProbeContext) -> dict[str, Any]:
    """Project loop health stubs for the cockpit.

    This is projection-only. Loop owners remain the scripts, receipts, cron
    configs, and governance docs named in each row.
    """
    root = ctx.repo_root
    logs_root = Path.home() / ".dharma" / "logs"
    de_bug_digest_path = logs_root / "name_drift_preflight_digest_latest.json"
    de_bug_digest = _safe_json(de_bug_digest_path)
    de_bug_age = _file_age_hours(de_bug_digest_path)
    de_bug_status = str(de_bug_digest.get("status") or "missing_receipt")
    de_bug_hits = int(de_bug_digest.get("hit_count") or 0)
    de_bug_unique = int(de_bug_digest.get("unique_hit_count") or 0)
    de_bug_blockers = de_bug_digest.get("blockers") if isinstance(de_bug_digest.get("blockers"), list) else []
    de_bug_healthy = de_bug_status == "swept" and not de_bug_blockers and de_bug_age is not None and de_bug_age <= 6

    home = Path.home()

    # runtime_truth_freshness: read-only projection of the live ops census receipt.
    census_path = home / ".dharma" / "ops" / "live_process_census.json"
    census = _safe_json(census_path)
    census_age = _file_age_hours(census_path)
    census_summary = census.get("summary") if isinstance(census.get("summary"), dict) else {}
    census_fresh = bool(census) and census_age is not None and census_age <= 6
    census_status = "healthy" if census_fresh else "needs_attention"

    # pr_control_plane: read-only projection of the Hermes PR clearer last-run receipt.
    pr_clearer_path = home / ".hermes" / "pr_clearer_last_run.json"
    pr_clearer = _safe_json(pr_clearer_path)
    pr_clearer_age = _file_age_hours(pr_clearer_path)
    pr_clearer_auth = bool(pr_clearer.get("auth"))
    pr_actions = pr_clearer.get("actions")
    pr_action_count = len(pr_actions) if isinstance(pr_actions, list) else (pr_actions if isinstance(pr_actions, int) else 0)
    pr_fresh = bool(pr_clearer) and pr_clearer_age is not None and pr_clearer_age <= 12
    pr_status = "healthy" if (pr_fresh and pr_clearer_auth) else "needs_attention"

    # kaizenops_daily_action: canonical receipt dir (~/.dharma per runtime-receipts-not-in-git rule).
    kaizen_dir = home / ".dharma" / "kaizenops"
    kaizen_receipts = sorted(kaizen_dir.glob("*.json")) if kaizen_dir.exists() else []
    kaizen_latest = kaizen_receipts[-1] if kaizen_receipts else None
    kaizen_age = _file_age_hours(kaizen_latest) if kaizen_latest else None
    kaizen_record = _safe_json(kaizen_latest) if kaizen_latest else {}
    kaizen_acted = bool(kaizen_latest) and str(kaizen_record.get("action") or kaizen_record.get("status") or "").upper() != "NO_ACTION"
    kaizen_status = "healthy" if (kaizen_age is not None and kaizen_age <= 30 and kaizen_acted) else "needs_attention"
    kaizen_hermes_path = home / ".hermes" / "kaizenops" / "snapshots.jsonl"
    kaizen_hermes_age = _file_age_hours(kaizen_hermes_path)

    loops = [
        {
            "id": "de_bug_corral_sweep",
            "title": "DE_BUG_CORRAL sweep",
            "status": "healthy" if de_bug_healthy else "needs_attention",
            "cadence": "every 6h",
            "owner": "scripts/governance/name_drift_preflight.py",
            "receipt_path": str(de_bug_digest_path),
            "last_age_hours": de_bug_age,
            "metrics": {
                "hit_count": de_bug_hits,
                "unique_hit_count": de_bug_unique,
                "route_count": len(de_bug_digest.get("by_route", {}) if isinstance(de_bug_digest.get("by_route"), dict) else {}),
            },
            "next_action": de_bug_digest.get("next_action") or "run make bug-corral-scan with JSON/Markdown/digest outputs",
            "evidence": [
                _evidence("scripts/governance/name_drift_preflight.py", path="scripts/governance/name_drift_preflight.py", status="owner"),
                _evidence(str(de_bug_digest_path), path=str(de_bug_digest_path), status=de_bug_status, age_hours=de_bug_age),
                _evidence("DE_BUG_CORRAL/00.md", path="DE_BUG_CORRAL/00.md", status="canonical" if (root / "DE_BUG_CORRAL/00.md").exists() else "missing"),
            ],
            "raw": de_bug_digest,
        },
        {
            "id": "kaizenops_daily_action",
            "title": "KaizenOps one-action metabolism",
            "status": kaizen_status,
            "cadence": "daily",
            "owner": "docs/governance/KAIZENOPS.md",
            "receipt_path": str(kaizen_dir),
            "last_age_hours": kaizen_age,
            "metrics": {
                "receipts_present": len(kaizen_receipts),
                "latest_acted": kaizen_acted,
                "hermes_snapshot_age_hours": kaizen_hermes_age,
            },
            "next_action": (
                "wire KaizenOps daily one-action to write ~/.dharma/kaizenops/YYYY-MM-DD.json"
                if not kaizen_latest
                else "route one verified waste item and record today's receipt"
            ),
            "evidence": [
                _evidence("docs/governance/KAIZENOPS.md", path="docs/governance/KAIZENOPS.md", status="owner"),
                _evidence(str(kaizen_dir), path=str(kaizen_dir), status=("observed" if kaizen_latest else "missing"), age_hours=kaizen_age),
                _evidence(str(kaizen_hermes_path), path=str(kaizen_hermes_path), status="stale_secondary", age_hours=kaizen_hermes_age),
            ],
            "raw": kaizen_record,
        },
        {
            "id": "pr_control_plane",
            "title": "PR control-plane sweep",
            "status": pr_status,
            "cadence": "3x/day + GitHub Actions",
            "owner": "scripts/runtime/pr_merge_control.py + Hermes pr_clearer.py",
            "receipt_path": str(pr_clearer_path),
            "last_age_hours": pr_clearer_age,
            "metrics": {
                "open_pr_count": pr_clearer.get("count"),
                "action_count": pr_action_count,
                "auth_ok": pr_clearer_auth,
            },
            "next_action": (
                "constrain PR clearer to AmitabhainArunachala/dharma_swarm and report queue deltas"
                if pr_status != "healthy"
                else "hold report-only; enable action mode only behind PR_CLEAR_ACTION=1"
            ),
            "evidence": [
                _evidence("scripts/runtime/pr_merge_control.py", path="scripts/runtime/pr_merge_control.py", status="owner"),
                _evidence(str(pr_clearer_path), path=str(pr_clearer_path), status=("observed" if pr_clearer else "missing"), age_hours=pr_clearer_age),
            ],
            "raw": pr_clearer,
        },
        {
            "id": "runtime_truth_freshness",
            "title": "Runtime truth freshness",
            "status": census_status,
            "cadence": "2h/daily depending daemon mode",
            "owner": "scripts/runtime/live_ops_census.py",
            "receipt_path": str(census_path),
            "last_age_hours": census_age,
            "metrics": {k: v for k, v in census_summary.items() if isinstance(v, (int, float, str, bool))},
            "next_action": (
                "run scripts/runtime/live_ops_census.py --write then runtime_truth_closeout.py"
                if not census_fresh
                else "hold; census within 6h SLA"
            ),
            "evidence": [
                _evidence("scripts/runtime/live_ops_census.py", path="scripts/runtime/live_ops_census.py", status="owner"),
                _evidence(str(census_path), path=str(census_path), status=(str(census.get("schema_version") or "observed") if census else "missing"), age_hours=census_age),
            ],
            "raw": census_summary,
        },
    ]

    for loop in loops:
        status = str(loop.get("status") or "unknown")
        lane = "Verified" if status == "healthy" else "Needs Repair" if status == "needs_attention" else "Needs Decision"
        ctx.cards.append(
            _card(
                kind="operating_loop",
                card_id=f"operating_loop:{loop['id']}",
                title=str(loop["title"]),
                status=status,
                lane=lane,
                risk="known_breakage" if lane == "Needs Repair" else "stale_surface_proof" if status == "stub" else "live_ops_blocked",
                next_action=str(loop.get("next_action") or "verify loop receipt"),
                track="kaizenops",
                evidence=loop.get("evidence") if isinstance(loop.get("evidence"), list) else [],
                facets={"live": status == "healthy", "stale": status != "healthy", "operator_decision": status == "stub"},
                raw=loop,
            )
        )

    return {
        "schema_version": "operator_loops_stub.v1",
        "loops": loops,
        "summary": {
            "total": len(loops),
            "healthy": sum(1 for loop in loops if loop.get("status") == "healthy"),
            "needs_attention": sum(1 for loop in loops if loop.get("status") == "needs_attention"),
            "stub": sum(1 for loop in loops if loop.get("status") == "stub"),
        },
    }


def build_operator_coherence_cockpit(
    repo_root: Path | None = None,
    *,
    include_github: bool = True,
    include_live_probes: bool = True,
) -> dict[str, Any]:
    """Build the normalized cockpit JSON projection."""
    root = (repo_root or DEFAULT_REPO_ROOT).resolve()
    ctx = ProbeContext(repo_root=root, include_github=include_github, include_live_probes=include_live_probes)

    governance = _probe_governance(ctx)
    git_data = _probe_git(ctx)
    branches = _probe_branches(ctx, git_data)
    git_data["branch_census"] = branches
    terminal = _probe_terminal_processes(ctx) if include_live_probes else {"tmux_sessions": [], "launchd_jobs": [], "processes": [], "disabled": True}
    live_ops = _probe_live_ops(ctx)
    onboarding = _probe_onboarding(ctx)
    runtime_receipts = _probe_runtime_db_and_receipts(ctx)
    operator_surfaces = _probe_dashboard_and_surfaces(ctx)
    preservation = _probe_preservation(ctx, git_data)
    github = _probe_github(ctx)
    operating_loops = _probe_operating_loops(ctx)

    readiness = _compute_readiness(
        repo_root=root,
        governance=governance,
        git_data=git_data,
        terminal=terminal,
        live_ops=live_ops,
        surfaces=operator_surfaces,
        preservation=preservation,
        github=github,
        cards=ctx.cards,
    )
    kanban = _build_kanban(ctx.cards)
    top_blockers = [
        {
            "title": c["title"],
            "kind": c["kind"],
            "risk": c["risk"],
            "next_action": c["next_action"],
            "evidence": c.get("evidence", [])[:2],
        }
        for c in ctx.cards
        if c["lane"] in {"Needs Repair", "Needs Decision"} or c["facets"].get("rogue")
    ][:10]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso(),
        "repo_root": str(root),
        "source_errors": ctx.source_errors,
        "source_refs": {
            "git": ["git status --short --branch", "git worktree list --porcelain", "git stash list"],
            "branches": ["git for-each-ref --format=... refs/heads"],
            "governance": [
                "docs/governance/ACTIVE_TRACK.yaml",
                "reports/governance/active_track_evidence.json",
                "docs/state/BROKEN_REGISTER.md",
            ],
            "live_ops": ["tmux ls", "launchctl list", "ps -axo pid,etime,command", "scripts/runtime/live_ops_census.py"],
            "onboarding": ["make onboard", "scripts/governance/agent_onboard.py"],
            "runtime_receipts": [".dharma/state/runtime.db", ".dharma/db/runtime.db", "reports/**/*receipt*"],
            "dashboard": [probe for surface in SURFACE_PROBES for probe in surface["paths"]],
            "preservation": [".dharma/preservation", "~/.dharma/preservation", "reports/governance"],
            "github": ["gh pr list --json ..."] if include_github else [],
            "operating_loops": ["DE_BUG_CORRAL/00.md", "~/.dharma/logs/name_drift_preflight_digest_latest.json"],
        },
        "executive": {
            "health": "critical" if readiness["score"] < 40 else "mixed" if readiness["score"] < 70 else "stable",
            "prod_readiness_estimate": readiness["score"],
            "top_blockers": top_blockers,
            "next_3_actions": _top_actions(ctx.cards),
        },
        "readiness": readiness,
        "kanban": kanban,
        "cards": ctx.cards,
        "track_portfolio": governance,
        "rogue_work_radar": {
            "cards": [
                c
                for c in ctx.cards
                if c["facets"].get("rogue")
                or c["risk"]
                in {
                    "dirty_worktree",
                    "local_only_work",
                    "hidden_local_work",
                    "local_only_branch",
                    "unpushed_commits",
                    "orphaned_upstream_gone",
                }
            ],
            "dirty_worktree_count": sum(1 for wt in git_data.get("worktrees", []) if wt.get("dirty_count")),
            "local_only_count": sum(1 for wt in git_data.get("worktrees", []) if wt.get("local_only") or wt.get("ahead")),
            "stash_count": len(git_data.get("stashes", [])),
            "local_branch_total": branches.get("total", 0),
            "local_only_branch_count": branches.get("local_only", 0),
            "unpushed_branch_count": branches.get("unpushed_ahead", 0),
            "orphaned_branch_count": branches.get("orphaned_gone", 0),
        },
        "agent_terminal_census": terminal,
        "branch_census": branches,
        "live_ops": live_ops,
        "onboarding": onboarding,
        "runtime_receipts": runtime_receipts,
        "operator_surfaces": operator_surfaces,
        "preservation_ledger": preservation,
        "pr_ci_triage": github,
        "operating_loops": operating_loops,
        "git": git_data,
    }
    payload["definition_answers"] = _definition_answers(payload)
    return payload


def render_markdown_report(payload: dict[str, Any]) -> str:
    """Render a human-readable receipt from the normalized JSON."""
    lines = [
        "# Operator Coherence Cockpit",
        "",
        f"- Generated: `{payload.get('generated_at')}`",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Repo: `{payload.get('repo_root')}`",
        f"- Prod readiness estimate: **{payload['readiness']['score']}%** ({payload['readiness']['interpretation']})",
        "",
        "## Executive Board",
        "",
        f"- Health: **{payload['executive']['health']}**",
        f"- Top blocker count shown: {len(payload['executive']['top_blockers'])}",
        "",
        "### Next 3 actions",
    ]
    for idx, action in enumerate(payload["executive"]["next_3_actions"], start=1):
        evidence = action.get("evidence", [{}])[0].get("source", "no evidence")
        lines.append(f"{idx}. **{action['risk']}** — {action['next_action']}  ")
        lines.append(f"   - Card: `{action['kind']}` {action['title']}  ")
        lines.append(f"   - Evidence: `{evidence}`")
    lines.extend(["", "## Readiness scoring", ""])
    for key, item in payload["readiness"]["categories"].items():
        lines.append(f"- **{key}**: {item['score']}% × {item['weight']:.0%} — {item['why']}")
    lines.extend(["", "## Kanban counts", ""])
    for lane in payload["kanban"]:
        lines.append(f"- {lane['lane']}: {lane['count']}")
    radar = payload.get("rogue_work_radar", {})
    bc = payload.get("branch_census", {})
    lines.extend(["", "## Reality layer (git + runtime)", ""])
    lines.append(
        f"- Branches: {bc.get('total', 0)} local "
        f"({radar.get('local_only_branch_count', 0)} local-only, "
        f"{radar.get('unpushed_branch_count', 0)} unpushed-ahead, "
        f"{radar.get('orphaned_branch_count', 0)} orphaned/upstream-gone)"
    )
    lines.append(
        f"- Worktrees: {radar.get('dirty_worktree_count', 0)} dirty, "
        f"{radar.get('local_only_count', 0)} local-only/ahead; {radar.get('stash_count', 0)} stashes"
    )
    live_ops = payload.get("live_ops", {})
    if live_ops.get("enabled"):
        by_status = (live_ops.get("summary", {}) or {}).get("by_status", {})
        lines.append(
            f"- Live ops: {by_status.get('live', 0)} live, {by_status.get('stale', 0)} stale, "
            f"{by_status.get('blocked', 0)} blocked, {by_status.get('stopped', 0)} stopped "
            f"(source: scripts/runtime/live_ops_census.py)"
        )
    else:
        lines.append(f"- Live ops: unavailable ({live_ops.get('reason', 'unknown')})")
    onboarding = payload.get("onboarding", {})
    lines.append(f"- Onboarding: make onboard `{onboarding.get('status', 'unknown')}` — {onboarding.get('target', '').strip()}")
    runtime_receipts = payload.get("runtime_receipts", {})
    runtime_dbs = runtime_receipts.get("runtime_dbs", [])
    readable_dbs = len([db for db in runtime_dbs if db.get("readable")])
    lines.append(
        f"- Runtime DB / receipts: {readable_dbs}/{len(runtime_dbs)} runtime DBs readable; "
        f"{runtime_receipts.get('receipt_count', 0)} receipt files discovered"
    )
    lines.extend(["", "## Definition-of-done quick answers", ""])
    answer_labels = {
        "what_is_safe": "What is safe?",
        "what_is_dirty": "What is dirty?",
        "what_is_abandoned": "What is abandoned?",
        "what_is_live": "What is live?",
        "what_is_blocked": "What is blocked?",
        "what_might_be_rogue": "What might be rogue?",
    }
    for key, label in answer_labels.items():
        items = payload["definition_answers"].get(key, [])
        lines.append(f"### {label}")
        if not items:
            lines.append("- No cards in this bucket.")
        for card in items[:10]:
            evidence = card.get("evidence", [{}])[0].get("source", "no evidence")
            lines.append(f"- `{card['kind']}` **{card['title']}** — {card['risk']} → {card['next_action']} _(evidence: {evidence})_")
        lines.append("")
    lines.extend(["## Source errors / uncertainty", ""])
    if payload.get("source_errors"):
        for err in payload["source_errors"]:
            lines.append(f"- `{err.get('source')}`: {err.get('error')}")
    else:
        lines.append("- None captured.")
    lines.extend(["", "## Evidence discipline", ""])
    lines.append("This receipt is generated from probe JSON. Do not hand-edit it as truth; regenerate from `scripts/runtime/operator_coherence_cockpit.py`.")
    return "\n".join(lines) + "\n"


def write_operator_coherence_outputs(
    payload: dict[str, Any],
    *,
    json_output: Path = DEFAULT_JSON_OUTPUT,
    markdown_output: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> tuple[Path, Path]:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_tmp = json_output.with_suffix(json_output.suffix + ".tmp")
    md_tmp = markdown_output.with_suffix(markdown_output.suffix + ".tmp")
    json_tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_tmp.write_text(render_markdown_report(payload), encoding="utf-8")
    os.replace(json_tmp, json_output)
    os.replace(md_tmp, markdown_output)
    return json_output, markdown_output
