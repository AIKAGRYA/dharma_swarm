"""GitHub probe, readiness score, kanban, and definition answers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import KANBAN_LANES, READINESS_WEIGHTS, ProbeContext, _age_hours_from_iso, _card, _evidence, _run
from .git_governance import _infer_track

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


