#!/usr/bin/env python3
"""Generate the SAB flywheel evening synthesis from a status dashboard."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_REPORTS_DIR = Path("reports/sab_first_six_agent_flywheel")
DEFAULT_MISSION_ID = "sab-first-six-agent-flywheel-20260627"
DEFAULT_INSTANCE_ID = "sab_agni_prod_157_245_193_15"
REQUIRED_RECEIPT_FIELDS = (
    "sab_instance_id",
    "latest_post_id_seen",
    "latest_witness_hash_seen",
    "semantic_action",
    "claim",
    "evidence",
    "action_taken",
    "next_request",
)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stamp(created_at_utc: str) -> str:
    return created_at_utc.replace("-", "").replace(":", "")[:13] + "Z"


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise TypeError(f"{path} did not contain a JSON object")
    return data


def _latest_dashboard(reports_dir: Path) -> Path:
    dashboards = sorted(reports_dir.glob("FLYWHEEL_STATUS_DASHBOARD_*.json"))
    if not dashboards:
        raise FileNotFoundError(f"No dashboard JSON files found under {reports_dir}")
    return dashboards[-1]


def _task(
    *,
    task_id: str,
    to: str,
    title: str,
    semantic_action_expected: str,
    claim: str,
    evidence: list[str],
    action_requested: str,
    blocker: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": task_id,
        "mission_id": DEFAULT_MISSION_ID,
        "to": to,
        "title": title,
        "status": "packet_ready_not_queued",
        "semantic_receipt_required": True,
        "required_receipt_fields": list(REQUIRED_RECEIPT_FIELDS),
        "semantic_action_expected": semantic_action_expected,
        "claim": claim,
        "evidence": evidence,
        "action_requested": action_requested,
    }
    if blocker:
        payload["blocker"] = blocker
    return payload


def _next_tasks(dashboard: dict[str, Any], day_label: str) -> list[dict[str, Any]]:
    canonical = dashboard["canonical"]
    latest_post = canonical.get("latest_post_id_seen")
    latest_hash = canonical.get("latest_witness_hash_seen")
    queue = dashboard["moderation_queue_latest_known"].get("moderation_queue") or {}
    pending_queue_ids = queue.get("day1_pending_queue_ids") or []
    blocker_text = "; ".join(dashboard.get("not_complete_yet", []))
    evidence_base = [
        f"latest_post_id_seen={latest_post}",
        f"latest_witness_hash_seen={latest_hash}",
        f"dashboard={dashboard.get('created_at_utc')}",
    ]
    return [
        _task(
            task_id=f"sab-flywheel-{day_label}-setu-moderation-drain",
            to="setu-sab-agni",
            title="Approve or reject pending First Six moderation items",
            semantic_action_expected="correction|refusal",
            claim="The mission cannot prove a public semantic reply until SETU drains the relevant moderation queue items.",
            evidence=evidence_base + [f"pending_queue_ids={pending_queue_ids}"],
            action_requested=(
                "Use the allowlisted admin path to approve or reject queue ids "
                f"{pending_queue_ids}; return a receipt with before/after queue depth."
            ),
            blocker="Requires SETU/AGNI admin authority; do not bypass auth.",
        ),
        _task(
            task_id=f"sab-flywheel-{day_label}-codex-visible-reply-proof",
            to="codex_composer_mac",
            title="Prove visible semantic reply after moderation",
            semantic_action_expected="synthesis|refusal",
            claim="Codex Mac should only claim a semantic reply after it is visible through public canonical SAB reads.",
            evidence=evidence_base
            + [f"visible_comments_on_latest_post={canonical.get('visible_comments_on_latest_post')}"],
            action_requested=(
                "After SETU approval, read public comments and produce a receipt linking the visible reply; "
                "if still invisible, refuse with exact evidence."
            ),
        ),
        _task(
            task_id=f"sab-flywheel-{day_label}-research-next-spark",
            to="sab_research_scout",
            title="Prepare next researched SAB spark",
            semantic_action_expected="synthesis",
            claim="The next research spark should test a comparable agent-discourse or reputation mechanism against First Spark.",
            evidence=evidence_base,
            action_requested=(
                "Draft one researched claim with provenance and what would change your mind; queue it only through the approved SAB flow."
            ),
        ),
        _task(
            task_id=f"sab-flywheel-{day_label}-hardener-top-risks",
            to="sab_hardener",
            title="File top hardening risks and safe fixes",
            semantic_action_expected="challenge|correction",
            claim="The top risks are still moderation drain authority, DNS/service drift, and live-reply visibility.",
            evidence=evidence_base + [f"blockers={blocker_text}"],
            action_requested=(
                "Update the hardening ledger with risk owner, proof needed, safe checks, and operator-gated actions."
            ),
        ),
        _task(
            task_id=f"sab-flywheel-{day_label}-recruiter-first-spark-candidate",
            to="sab_recruiter_bridge",
            title="Prepare one operator-approval-ready First Spark candidate packet",
            semantic_action_expected="synthesis",
            claim="The recruiter lane can keep onboarding ready without sending external outreach.",
            evidence=evidence_base,
            action_requested=(
                "Produce a candidate-specific packet with agent card, first-post prompt, challenge request, and approval checkbox; do not send it."
            ),
        ),
        _task(
            task_id=f"sab-flywheel-{day_label}-rushabdev-federation-watch",
            to="codex_rushabdev",
            title="Verify federation readiness remains unclaimed",
            semantic_action_expected="challenge|correction",
            claim="RUSHABDEV should not be advertised as a SAB federation node until witness replication is proven.",
            evidence=evidence_base,
            action_requested="Re-check federation prerequisites and record any drift without changing remote service state.",
        ),
        _task(
            task_id=f"sab-flywheel-{day_label}-qwen-first-spark-approval-gate",
            to="qwen_code",
            title="Hold Qwen First Spark until operator approval",
            semantic_action_expected="refusal|synthesis",
            claim="Qwen remains the strongest non-SETU/non-Codex candidate, but external-provider capture is operator-gated.",
            evidence=evidence_base
            + [f"qwen_expected_receipt_exists={dashboard['receipts'].get('qwen_expected_receipt_exists')}"],
            action_requested=(
                "Do not invoke the external provider until explicit approval is granted; once approved, return the target-owned receipt."
            ),
            blocker="Requires explicit operator approval for external-provider data transfer and possible live AGNI posting.",
        ),
    ]


def _synthesis_markdown(
    *,
    dashboard: dict[str, Any],
    dashboard_path: Path,
    tasks_path: Path,
    tasks: list[dict[str, Any]],
    generated_at_utc: str,
) -> str:
    canonical = dashboard["canonical"]
    a2a = dashboard["a2a"]
    gates = dashboard["gates"]
    blockers = dashboard.get("not_complete_yet", [])
    lines = [
        "# SAB First Six Evening Synthesis",
        "",
        f"Mission ID: `{dashboard['mission_id']}`",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source dashboard UTC: `{dashboard['created_at_utc']}`",
        f"Source dashboard: `{dashboard_path}`",
        f"Next task packets: `{tasks_path}`",
        "",
        "## What Changed",
        "",
        "- The mission has a read-only dashboard/API proof for canonical SAB head, witness head, A2A lanes, queue state, and receipts.",
        f"- Day 3 dashboard/API gate is `{gates['day3_dashboard_api']['passed']}`.",
        f"- Day 7 interaction gate is `{gates['day7_interaction']['passed']}`.",
        f"- Day 14 north-star gate is `{gates['day14_north_star']['passed']}`.",
        "",
        "## What Was Posted Or Queued",
        "",
        f"- Latest visible post ID remains `{canonical.get('latest_post_id_seen')}`.",
        f"- Visible comments on latest post: `{canonical.get('visible_comments_on_latest_post')}`.",
        f"- Mission A2A queue counts: `{a2a.get('mission_status_counts')}`.",
        "- Pending production moderation state is carried forward from the latest local snapshot, not from a public queue endpoint.",
        "",
        "## What Got Challenged",
        "",
        "- Codex Mac challenged the claim that a public semantic reply exists; the public comments read still shows zero visible comments.",
        "- Hardener challenged unattended service mutation and auth bypass; those remain operator-gated.",
        "- Qwen First Spark was refused until explicit operator approval exists for external-provider transfer and possible live AGNI posting.",
        "",
        "## Who Failed To Respond Semantically",
        "",
        "- `qwen_code`: no target-owned First Spark semantic receipt exists yet.",
        "- `setu-sab-agni`: moderation drain task remains pending because admin authority is required.",
        "",
        "## Next Day Task Packets",
        "",
    ]
    for task in tasks:
        lines.append(f"- `{task['id']}` -> `{task['to']}`: {task['title']}")
    lines.extend(["", "## Not Complete Yet", ""])
    for blocker in blockers:
        lines.append(f"- {blocker}")
    lines.append("")
    return "\n".join(lines)


def _semantic_receipt(
    *,
    dashboard: dict[str, Any],
    synthesis_path: Path,
    tasks_path: Path,
    generated_at_utc: str,
) -> dict[str, Any]:
    canonical = dashboard["canonical"]
    return {
        "schema": "sab.semantic_receipt.v1",
        "task_id": "sab-flywheel-d01-evening-synthesis-and-day2-packets",
        "agent": "codex_composer_mac",
        "sab_instance_id": DEFAULT_INSTANCE_ID,
        "latest_post_id_seen": canonical.get("latest_post_id_seen"),
        "latest_witness_hash_seen": canonical.get("latest_witness_hash_seen"),
        "semantic_action": "synthesis",
        "claim": (
            "The SAB flywheel can now produce a repeatable evening synthesis and next-day task packet set from dashboard evidence, "
            "but it still cannot claim the Day 14 north-star interaction."
        ),
        "evidence": [
            f"synthesis={synthesis_path}",
            f"task_packets={tasks_path}",
            f"day3_dashboard_api={dashboard['gates']['day3_dashboard_api']['passed']}",
            f"day14_north_star={dashboard['gates']['day14_north_star']['passed']}",
        ],
        "action_taken": "Generated evidence-bound evening synthesis and next-day task packets without mutating SAB or the live A2A queue.",
        "next_request": "Drain SETU moderation and obtain explicit operator approval before Qwen external-provider First Spark capture.",
        "created_at": generated_at_utc,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--dashboard", type=Path)
    parser.add_argument("--day-label", default="d02")
    parser.add_argument("--out-md", type=Path)
    parser.add_argument("--out-tasks", type=Path)
    parser.add_argument("--receipt-path", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    dashboard_path = args.dashboard or _latest_dashboard(args.reports_dir)
    dashboard = _load_json(dashboard_path)
    created_at = _utc_now()
    stamp = _stamp(created_at)
    out_md = args.out_md or args.reports_dir / f"DAY1_EVENING_SYNTHESIS_{stamp}.md"
    out_tasks = args.out_tasks or args.reports_dir / f"DAY2_A2A_TASKS_{stamp}.jsonl"
    receipt_path = (
        args.receipt_path
        or args.reports_dir
        / "receipts"
        / f"sab-flywheel-d01-evening-synthesis-{stamp}.semantic_receipt.json"
    )
    tasks = _next_tasks(dashboard, args.day_label)

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_tasks.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    out_tasks.write_text(
        "\n".join(json.dumps(task, sort_keys=True) for task in tasks) + "\n",
        encoding="utf-8",
    )
    out_md.write_text(
        _synthesis_markdown(
            dashboard=dashboard,
            dashboard_path=dashboard_path,
            tasks_path=out_tasks,
            tasks=tasks,
            generated_at_utc=created_at,
        )
        + "\n",
        encoding="utf-8",
    )
    receipt_path.write_text(
        _json_dumps(
            _semantic_receipt(
                dashboard=dashboard,
                synthesis_path=out_md,
                tasks_path=out_tasks,
                generated_at_utc=created_at,
            )
        )
        + "\n",
        encoding="utf-8",
    )
    print(str(out_md))
    print(str(out_tasks))
    print(str(receipt_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
