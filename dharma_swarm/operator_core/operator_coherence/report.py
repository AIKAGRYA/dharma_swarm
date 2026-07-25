"""Build and render the Operator Coherence Cockpit projection."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir

from .base import DEFAULT_JSON_OUTPUT, DEFAULT_MARKDOWN_OUTPUT, DEFAULT_REPO_ROOT, SCHEMA_VERSION, SURFACE_PROBES, ProbeContext, _iso
from .git_governance import _probe_branches, _probe_git, _probe_governance
from .github_readiness import _build_kanban, _compute_readiness, _definition_answers, _probe_github, _top_actions
from .ops_probes import (
    _probe_dashboard_and_surfaces,
    _probe_live_ops,
    _probe_onboarding,
    _probe_preservation,
    _probe_runtime_db_and_receipts,
    _probe_terminal_processes,
)

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
            "preservation": [".dharma/preservation", str(dharma_state_dir() / "preservation"), "reports/governance"],
            "github": ["gh pr list --json ..."] if include_github else [],
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
