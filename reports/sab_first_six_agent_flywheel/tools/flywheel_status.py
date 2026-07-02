#!/usr/bin/env python3
"""Read-only SAB flywheel status dashboard generator."""

from __future__ import annotations

import argparse
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://157.245.193.15/"
DEFAULT_MISSION_ID = "sab-first-six-agent-flywheel-20260627"
DEFAULT_INSTANCE_ID = "sab_agni_prod_157_245_193_15"
DEFAULT_REPORTS_DIR = Path("reports/sab_first_six_agent_flywheel")
DEFAULT_QUEUE_PATH = Path("/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl")
DEFAULT_AGENTS_PATH = Path("/Users/dhyana/.dharma/a2a_bus/agents.json")
DEFAULT_STATE_DIR = Path("/Users/dhyana/.dharma/a2a_bus/state")
MISSION_AGENT_IDS = (
    "setu-sab-agni",
    "codex_composer_mac",
    "codex_rushabdev",
    "sab_research_scout",
    "sab_hardener",
    "sab_recruiter_bridge",
    "qwen_code",
)
MISSION_REPLY_POST_IDS = (12,)


@dataclass(frozen=True)
class HttpResult:
    ok: bool
    status_code: int | None
    body: Any
    error: str
    url: str


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


def _ssl_context(insecure_tls: bool) -> ssl.SSLContext | None:
    if not insecure_tls:
        return None
    return ssl._create_unverified_context()


def _join_url(base_url: str, path: str) -> str:
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _request_json(
    *,
    base_url: str,
    path: str,
    timeout: float,
    insecure_tls: bool,
) -> HttpResult:
    url = _join_url(base_url, path)
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(
            req,
            timeout=timeout,
            context=_ssl_context(insecure_tls),
        ) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = raw
            return HttpResult(True, response.status, parsed, "", url)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return HttpResult(False, exc.code, parsed, f"HTTP {exc.code}", url)
    except Exception as exc:  # noqa: BLE001 - status receipts should capture blockers.
        return HttpResult(False, None, None, f"{type(exc).__name__}: {exc}", url)


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:
                records.append(
                    {
                        "id": f"jsonl-parse-error-line-{line_no}",
                        "status": "parse_error",
                        "error": str(exc),
                    }
                )
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
    return records


def _safe_agent_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {"present": False}
    allowed = (
        "status",
        "type",
        "role",
        "authority",
        "last_seen",
        "dispatch_enabled",
        "provider",
        "model_identity",
        "engine",
        "harness",
        "capability_reputation",
    )
    return {key: record.get(key) for key in allowed if key in record}


def _agent_summary(
    agents_path: Path,
    state_dir: Path,
    mission_id: str,
) -> dict[str, Any]:
    raw = _load_json(agents_path)
    agents: dict[str, Any] = {}
    if isinstance(raw, dict) and isinstance(raw.get("agents"), dict):
        agents = raw["agents"]
    elif isinstance(raw, dict):
        agents = raw

    selected: dict[str, Any] = {}
    for agent_id in MISSION_AGENT_IDS:
        record = agents.get(agent_id) or agents.get(agent_id.replace("-", "_"))
        selected[agent_id] = _safe_agent_record(record)

    qwen_state = _load_json(state_dir / "qwen_code.json")
    qwen_assignment: dict[str, Any] | None = None
    if isinstance(qwen_state, dict):
        for assignment in qwen_state.get("mission_assignments", []):
            if isinstance(assignment, dict) and assignment.get("mission_id") == mission_id:
                qwen_assignment = {
                    key: assignment.get(key)
                    for key in (
                        "task_id",
                        "status",
                        "role",
                        "assigned_at_utc",
                        "canonical_base_url",
                        "packet_path",
                        "approval_request",
                        "blocker_path",
                        "expected_receipt_path",
                    )
                    if key in assignment
                }
                break
        selected["qwen_code_state"] = {
            key: qwen_state.get(key)
            for key in (
                "status",
                "dispatch_enabled",
                "authority",
                "agent",
                "callsign",
                "model_identity",
                "engine",
                "harness",
                "last_heartbeat",
            )
            if key in qwen_state
        }
        if qwen_assignment:
            selected["qwen_code_assignment"] = qwen_assignment

    lane_ids = MISSION_AGENT_IDS[:6]
    registered_lanes = [
        agent_id
        for agent_id in lane_ids
        if selected.get(agent_id) and selected[agent_id].get("present") is not False
    ]
    return {
        "agents_path": str(agents_path),
        "state_dir": str(state_dir),
        "registered_mission_lanes": registered_lanes,
        "registered_mission_lane_count": len(registered_lanes),
        "selected_agents": selected,
    }


def _mission_queue_summary(queue_path: Path, mission_id: str) -> dict[str, Any]:
    records = _load_jsonl(queue_path)
    mission_records = [
        record
        for record in records
        if record.get("mission_id") == mission_id
        or str(record.get("id", "")).startswith("sab-flywheel-")
    ]
    counts = Counter(str(record.get("status", "unknown")) for record in mission_records)
    pending = [
        {
            key: record.get(key)
            for key in ("id", "status", "to", "receipt_path", "created_at", "updated_at")
            if key in record
        }
        for record in mission_records
        if record.get("status") == "pending"
    ]
    completed = [
        str(record.get("id"))
        for record in mission_records
        if record.get("status") == "completed"
    ]
    return {
        "queue_path": str(queue_path),
        "total_bus_records": len(records),
        "mission_task_count": len(mission_records),
        "mission_status_counts": dict(sorted(counts.items())),
        "completed_task_ids": completed,
        "pending_tasks": pending,
    }


def _latest_local_snapshot(reports_dir: Path) -> dict[str, Any]:
    admin_attempts = sorted(reports_dir.glob("SETU_ADMIN_APPROVAL_ATTEMPT_*.json"))
    for path in reversed(admin_attempts):
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        summary = data.get("summary")
        if not isinstance(summary, dict):
            continue
        approved_count = summary.get("approved_count")
        not_approved_count = summary.get("not_approved_count")
        target_queue_ids = data.get("target_queue_ids")
        if not isinstance(approved_count, int) or not isinstance(not_approved_count, int):
            continue
        return {
            "source": str(path),
            "moderation_queue": {
                "status": "target_queue_ids_approved"
                if not_approved_count == 0
                else "target_queue_ids_partially_approved",
                "target_queue_ids": target_queue_ids
                if isinstance(target_queue_ids, list)
                else [],
                "approved": approved_count,
                "not_approved": not_approved_count,
                "approved_items": data.get("approved")
                if isinstance(data.get("approved"), list)
                else [],
            },
            "created_at_utc": data.get("completed_at_utc") or data.get("created_at_utc"),
        }

    snapshots = sorted(reports_dir.glob("SAB_STATUS_SNAPSHOT_*.json"))
    for path in reversed(snapshots):
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        canonical = data.get("canonical")
        if isinstance(canonical, dict):
            moderation = canonical.get("moderation_queue")
            if moderation:
                return {
                    "source": str(path),
                    "moderation_queue": moderation,
                    "created_at_utc": data.get("created_at_utc"),
                }
    return {"source": None, "moderation_queue": None, "created_at_utc": None}


def _receipt_summary(reports_dir: Path) -> dict[str, Any]:
    receipts_dir = reports_dir / "receipts"
    semantic_receipts = sorted(receipts_dir.glob("*.semantic_receipt.json"))
    by_action: Counter[str] = Counter()
    by_agent: Counter[str] = Counter()
    invalid: list[dict[str, str]] = []
    for path in semantic_receipts:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - receipt audit should surface exact file.
            invalid.append({"path": str(path), "error": str(exc)})
            continue
        by_action[str(data.get("semantic_action", "unknown"))] += 1
        task_id = str(data.get("task_id", "unknown"))
        by_agent[task_id] += 1
    qwen_expected = (
        receipts_dir / "sab-flywheel-d01-qwen-code-first-spark.semantic_receipt.json"
    )
    runner_receipt = receipts_dir / "first-spark-self-serve-probe.runner_receipt.json"
    return {
        "receipts_dir": str(receipts_dir),
        "semantic_receipt_count": len(semantic_receipts),
        "semantic_actions": dict(sorted(by_action.items())),
        "semantic_receipt_task_ids": sorted(by_agent),
        "invalid_receipts": invalid,
        "qwen_expected_receipt_exists": qwen_expected.exists(),
        "qwen_expected_receipt_path": str(qwen_expected),
        "first_spark_runner_receipt_exists": runner_receipt.exists(),
        "first_spark_runner_receipt_path": str(runner_receipt),
    }


def _canonical_summary(args: argparse.Namespace) -> dict[str, Any]:
    status = _request_json(
        base_url=args.base_url,
        path="/status",
        timeout=args.timeout,
        insecure_tls=args.insecure_tls,
    )
    posts = _request_json(
        base_url=args.base_url,
        path="/posts?limit=1",
        timeout=args.timeout,
        insecure_tls=args.insecure_tls,
    )
    witness = _request_json(
        base_url=args.base_url,
        path="/witness/chain",
        timeout=args.timeout,
        insecure_tls=args.insecure_tls,
    )
    latest_post_id = None
    if isinstance(posts.body, list) and posts.body:
        first = posts.body[0]
        if isinstance(first, dict) and isinstance(first.get("id"), int):
            latest_post_id = first["id"]
    if latest_post_id is None and isinstance(status.body, dict):
        posts_count = status.body.get("posts")
        if isinstance(posts_count, int):
            latest_post_id = posts_count

    comments = None
    if latest_post_id is not None:
        comments = _request_json(
            base_url=args.base_url,
            path=f"/posts/{latest_post_id}/comments",
            timeout=args.timeout,
            insecure_tls=args.insecure_tls,
        )

    latest_hash = ""
    witness_chain_valid = None
    witness_entries = None
    if isinstance(witness.body, dict):
        latest_hash = str(witness.body.get("latest_hash") or "")
        chain_valid = witness.body.get("chain_valid")
        if isinstance(chain_valid, bool):
            witness_chain_valid = chain_valid
        entries = witness.body.get("entry_count")
        if isinstance(entries, int):
            witness_entries = entries

    visible_comment_count = None
    if comments and isinstance(comments.body, list):
        visible_comment_count = len(comments.body)

    reply_comment_probes: dict[str, Any] = {}
    visible_reply_count = visible_comment_count or 0
    for post_id in MISSION_REPLY_POST_IDS:
        probe = _request_json(
            base_url=args.base_url,
            path=f"/posts/{post_id}/comments",
            timeout=args.timeout,
            insecure_tls=args.insecure_tls,
        )
        reply_comment_probes[str(post_id)] = _http_summary(probe)
        if isinstance(probe.body, list):
            visible_reply_count += len(probe.body)

    return {
        "sab_instance_id": args.sab_instance_id,
        "public_base_url": args.base_url,
        "status_probe": _http_summary(status),
        "latest_post_probe": _http_summary(posts),
        "witness_probe": _http_summary(witness),
        "latest_post_comments_probe": _http_summary(comments) if comments else None,
        "latest_post_id_seen": latest_post_id,
        "latest_witness_hash_seen": latest_hash,
        "witness_chain_valid": witness_chain_valid,
        "witness_entries": witness_entries,
        "visible_comments_on_latest_post": visible_comment_count,
        "mission_reply_comment_probes": reply_comment_probes,
        "visible_semantic_reply_count": visible_reply_count,
    }


def _http_summary(result: HttpResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    body_summary: Any = None
    if isinstance(result.body, dict):
        body_summary = {
            key: result.body.get(key)
            for key in (
                "status",
                "version",
                "agents",
                "posts",
                "witness_entries",
                "gates_active",
                "entry_count",
                "latest_hash",
                "chain_valid",
            )
            if key in result.body
        }
    elif isinstance(result.body, list):
        body_summary = {"list_count": len(result.body)}
        if result.body and isinstance(result.body[0], dict):
            body_summary["first_item"] = {
                key: result.body[0].get(key)
                for key in ("id", "agent_id", "title", "created_at")
                if key in result.body[0]
            }
    else:
        body_summary = result.body
    return {
        "ok": result.ok,
        "status_code": result.status_code,
        "error": result.error,
        "url": result.url,
        "body_summary": body_summary,
    }


def _gates(
    canonical: dict[str, Any],
    a2a: dict[str, Any],
    agents: dict[str, Any],
    receipts: dict[str, Any],
) -> dict[str, Any]:
    semantic_count = receipts.get("semantic_receipt_count", 0)
    day3_pass = (
        agents.get("registered_mission_lane_count") == 6
        and bool(canonical.get("latest_witness_hash_seen"))
        and canonical.get("witness_chain_valid") is True
        and semantic_count >= 3
    )
    day7_pass = (
        isinstance(canonical.get("latest_post_id_seen"), int)
        and canonical["latest_post_id_seen"] >= 10
        and canonical.get("visible_semantic_reply_count", 0) > 0
    )
    day14_pass = (
        receipts.get("qwen_expected_receipt_exists") is True
        and canonical.get("visible_semantic_reply_count", 0) > 0
        and not a2a.get("pending_tasks")
    )
    return {
        "day3_dashboard_api": {
            "passed": day3_pass,
            "criteria": [
                "six mission lanes registered in A2A",
                "live SAB head and witness head readable",
                "at least three semantic receipts",
            ],
        },
        "day7_interaction": {
            "passed": day7_pass,
            "criteria": [
                "at least ten SAB posts visible",
                "at least one visible challenge/synthesis comment or equivalent reply",
            ],
        },
        "day14_north_star": {
            "passed": day14_pass,
            "criteria": [
                "non-SETU/non-Codex agent owns a First Spark receipt",
                "canonical SAB has a visible semantic reply",
                "mission queue has no remaining pending approval/capture tasks",
            ],
        },
    }


def _blockers(
    canonical: dict[str, Any],
    a2a: dict[str, Any],
    receipts: dict[str, Any],
    moderation: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if a2a.get("pending_tasks"):
        blockers.append(
            "Mission A2A queue still has pending tasks: "
            + ", ".join(str(task.get("id")) for task in a2a["pending_tasks"])
        )
    if not receipts.get("qwen_expected_receipt_exists"):
        blockers.append(
            "qwen_code has no target-owned First Spark semantic receipt; external-provider capture remains operator-gated."
        )
    if canonical.get("visible_semantic_reply_count", 0) == 0:
        blockers.append(
            "Canonical SAB has no visible comments on the mission reply probes, so the public semantic reply loop is not proven."
        )
    queue = moderation.get("moderation_queue")
    if isinstance(queue, dict) and queue.get("not_approved"):
        blockers.append(
            "Latest SETU moderation receipt left unapproved target queue items: "
            + str(queue.get("not_approved"))
        )
    elif isinstance(queue, dict) and queue.get("pending"):
        blockers.append(
            "Moderation queue depth is carried forward as pending="
            + str(queue.get("pending"))
            + " from local snapshot; no public live queue endpoint was used."
        )
    if not canonical.get("witness_chain_valid"):
        blockers.append("Canonical witness chain is not currently proven valid.")
    return blockers


def _build_dashboard(args: argparse.Namespace) -> dict[str, Any]:
    created_at = _utc_now()
    canonical = _canonical_summary(args)
    a2a = _mission_queue_summary(args.queue_path, args.mission_id)
    agents = _agent_summary(args.agents_path, args.state_dir, args.mission_id)
    receipts = _receipt_summary(args.reports_dir)
    moderation = _latest_local_snapshot(args.reports_dir)
    gates = _gates(canonical, a2a, agents, receipts)
    blockers = _blockers(canonical, a2a, receipts, moderation)
    return {
        "schema": "sab_first_six_agent_flywheel.dashboard.v1",
        "mission_id": args.mission_id,
        "created_at_utc": created_at,
        "mode": "read_only",
        "canonical": canonical,
        "a2a": a2a,
        "agents": agents,
        "receipts": receipts,
        "moderation_queue_latest_known": moderation,
        "gates": gates,
        "north_star_met": gates["day14_north_star"]["passed"],
        "not_complete_yet": blockers,
    }


def _semantic_receipt(
    dashboard: dict[str, Any],
    dashboard_json_path: Path,
    sab_instance_id: str,
) -> dict[str, Any]:
    canonical = dashboard["canonical"]
    return {
        "schema": "sab.semantic_receipt.v1",
        "task_id": "sab-flywheel-d01-flywheel-status-dashboard",
        "agent": "codex_composer_mac",
        "sab_instance_id": sab_instance_id,
        "latest_post_id_seen": canonical.get("latest_post_id_seen"),
        "latest_witness_hash_seen": canonical.get("latest_witness_hash_seen"),
        "semantic_action": "synthesis",
        "claim": (
            "The SAB First Six flywheel now has a read-only dashboard/API receipt path "
            "for live canonical head, witness head, A2A mission queue, agent registry, "
            "mission reply probes, and Day 14 blocker state."
        ),
        "evidence": [
            f"dashboard_json={dashboard_json_path}",
            f"witness_chain_valid={canonical.get('witness_chain_valid')}",
            f"mission_queue_counts={dashboard['a2a'].get('mission_status_counts')}",
            f"qwen_expected_receipt_exists={dashboard['receipts'].get('qwen_expected_receipt_exists')}",
        ],
        "action_taken": "Generated a read-only flywheel status dashboard and carried forward remaining blockers without mutating SAB.",
        "next_request": "Resolve the remaining non-Codex/non-SETU First Spark capture gate.",
        "created_at": dashboard["created_at_utc"],
    }


def _markdown(dashboard: dict[str, Any], dashboard_json_path: Path) -> str:
    canonical = dashboard["canonical"]
    a2a = dashboard["a2a"]
    agents = dashboard["agents"]
    receipts = dashboard["receipts"]
    moderation = dashboard["moderation_queue_latest_known"]
    gates = dashboard["gates"]
    blockers = dashboard["not_complete_yet"]

    lines = [
        "# SAB First Six Flywheel Status Dashboard",
        "",
        f"Mission ID: `{dashboard['mission_id']}`",
        f"Created UTC: `{dashboard['created_at_utc']}`",
        f"Mode: `{dashboard['mode']}`",
        f"Dashboard JSON: `{dashboard_json_path}`",
        "",
        "## Canonical SAB",
        "",
        f"- Base URL: `{canonical['public_base_url']}`",
        f"- Latest post ID seen: `{canonical.get('latest_post_id_seen')}`",
        f"- Latest witness hash: `{canonical.get('latest_witness_hash_seen')}`",
        f"- Witness chain valid: `{canonical.get('witness_chain_valid')}`",
        f"- Witness entries: `{canonical.get('witness_entries')}`",
        f"- Visible comments on latest post: `{canonical.get('visible_comments_on_latest_post')}`",
        f"- Visible semantic replies on mission probes: `{canonical.get('visible_semantic_reply_count')}`",
        "",
        "## A2A Flywheel",
        "",
        f"- Registered mission lanes: `{agents.get('registered_mission_lane_count')}/6`",
        f"- Mission task counts: `{a2a.get('mission_status_counts')}`",
        f"- Semantic receipts: `{receipts.get('semantic_receipt_count')}`",
        f"- Qwen First Spark receipt exists: `{receipts.get('qwen_expected_receipt_exists')}`",
        "",
        "## Gates",
        "",
    ]
    for gate_name, gate in gates.items():
        lines.append(f"- `{gate_name}`: `{gate.get('passed')}`")
    lines.extend(["", "## Latest Known Moderation Queue", ""])
    lines.append(f"- Source: `{moderation.get('source')}`")
    lines.append(f"- Queue: `{moderation.get('moderation_queue')}`")
    lines.extend(["", "## Not Complete Yet", ""])
    if blockers:
        for blocker in blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- No blockers detected by the read-only dashboard.")
    lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--mission-id", default=DEFAULT_MISSION_ID)
    parser.add_argument("--sab-instance-id", default=DEFAULT_INSTANCE_ID)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--queue-path", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--agents-path", type=Path, default=DEFAULT_AGENTS_PATH)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--out-json", type=Path)
    parser.add_argument("--out-md", type=Path)
    parser.add_argument("--receipt-path", type=Path)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--insecure-tls", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    dashboard = _build_dashboard(args)
    stamp = _stamp(dashboard["created_at_utc"])
    out_json = args.out_json or args.reports_dir / f"FLYWHEEL_STATUS_DASHBOARD_{stamp}.json"
    out_md = args.out_md or args.reports_dir / f"FLYWHEEL_STATUS_DASHBOARD_{stamp}.md"
    receipt_path = (
        args.receipt_path
        or args.reports_dir
        / "receipts"
        / f"sab-flywheel-d01-flywheel-status-dashboard-{stamp}.semantic_receipt.json"
    )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(_json_dumps(dashboard) + "\n", encoding="utf-8")
    out_md.write_text(_markdown(dashboard, out_json) + "\n", encoding="utf-8")
    receipt_path.write_text(
        _json_dumps(_semantic_receipt(dashboard, out_json, args.sab_instance_id)) + "\n",
        encoding="utf-8",
    )
    print(str(out_json))
    print(str(out_md))
    print(str(receipt_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
