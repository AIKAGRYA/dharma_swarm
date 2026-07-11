"""Git and governance probes for the Operator Coherence Cockpit."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.onboarding.broken_register import (
    parse_broken_register,
)

from .base import (
    ProbeContext,
    _age_hours_from_iso,
    _card,
    _evidence,
    _file_age_hours,
    _parse_date,
    _rel,
    _run,
    _safe_json,
    _safe_yaml,
    _utc_now,
)

# Trust rule (operator directive 2026-06-25): an ACTIVE track must not display as
# verified-complete on existence checks alone. Without >=1 rigorous criterion
# (test_passes / commit_on_main / receipt_valid / pr_merged) the surfaced
# readiness is capped so the number can never exceed what a real check supports.
# This kills the "9/9 criteria pass -> 100%" theater where every criterion is a
# file_exists/file_contains grep. The rigorous bar itself lives in
# scripts/governance/check_track_status.py (has_rigorous_evidence).
UNVERIFIED_READINESS_CEILING = 50.0


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
            has_rigorous_evidence = bool(evidence.get("has_rigorous_evidence"))
            criteria_pass_rate = round((passed / total) * 100, 1) if total else (100.0 if lifecycle != "active" else 0.0)
            # An ACTIVE track with no rigorous evidence cannot read above the
            # ceiling no matter how many existence checks pass. The displayed
            # number is then provably bounded by what a real check supports.
            readiness_capped = (
                lifecycle == "active" and total > 0 and not has_rigorous_evidence
                and criteria_pass_rate > UNVERIFIED_READINESS_CEILING
            )
            readiness = UNVERIFIED_READINESS_CEILING if readiness_capped else criteria_pass_rate
            readiness_basis = (
                "rigorous" if has_rigorous_evidence
                else ("existence-only" if total > 0 else "no-evidence")
            )
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
                "criteria_pass_rate": criteria_pass_rate,
                "has_rigorous_evidence": has_rigorous_evidence,
                "readiness_basis": readiness_basis,
                "readiness_capped": readiness_capped,
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
    broken_result = parse_broken_register(broken_path)
    for broken in broken_result.open_entries:
        status_text = broken.raw_status or broken.status
        block = f"{broken.heading}\n{broken.body}"
        broken_entries.append(
            {
                "line": broken.line,
                "text": f"### {broken.heading}"[:240],
                "status": status_text[:240],
            }
        )
        if len(broken_entries) <= 25:
            ctx.cards.append(
                _card(
                    kind="broken_register",
                    card_id=f"broken:{broken.line}",
                    title=broken.heading[:140],
                    status="open",
                    lane="Needs Repair",
                    risk="known_breakage",
                    next_action="repair or explicitly retire this broken-register item",
                    track=_infer_track(ctx, block),
                    evidence=[
                        _evidence(
                            "docs/state/BROKEN_REGISTER.md",
                            path="docs/state/BROKEN_REGISTER.md",
                            detail=f"line {broken.line}: {broken.heading[:180]} | status: {status_text[:160]}",
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
