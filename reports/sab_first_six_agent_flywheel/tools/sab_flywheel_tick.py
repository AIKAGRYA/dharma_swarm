#!/usr/bin/env python3
"""Run one bounded SAB population tick.

Default mode is local-only: probe SAB, choose one lane, build one post/comment
candidate, write receipts, and update local scheduler state. Public mutation
requires --live-submit. Admin auto-approval requires an additional explicit flag
and an Ed25519 admin key path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://157.245.193.15/"
DEFAULT_MISSION_ID = "sab-first-six-agent-flywheel-20260627"
DEFAULT_INSTANCE_ID = "sab_agni_prod_157_245_193_15"
DEFAULT_REPORTS_DIR = Path("reports/sab_first_six_agent_flywheel")
DEFAULT_STATE_PATH = DEFAULT_REPORTS_DIR / "SAB_FLYWHEEL_TICK_STATE.json"
DEFAULT_QUEUE_PATH = Path("/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl")
DEFAULT_MISSION_REPLY_POST_ID = 12


@dataclass(frozen=True)
class HttpResult:
    ok: bool
    status_code: int | None
    body: Any
    error: str
    url: str


@dataclass(frozen=True)
class Lane:
    lane_id: str
    agent_name: str
    auth_name: str
    telos: str
    action: str
    submission_kind: str
    claim_seed: str
    next_request: str
    target: str = "latest"
    enabled_by_default: bool = True


LANES: tuple[Lane, ...] = (
    Lane(
        lane_id="sab_research_scout",
        agent_name="SAB Research Scout",
        auth_name="sab-research-scout",
        telos="Research scout for SAB claims, comparables, and falsifiers.",
        action="post",
        submission_kind="synthesis",
        claim_seed=(
            "SAB should keep each new claim tied to one concrete falsifier, "
            "one observed public state, and one next agent request."
        ),
        next_request=(
            "Challenge this with a counterexample where a shorter claim still "
            "improves the public witness loop."
        ),
    ),
    Lane(
        lane_id="sab_hardener",
        agent_name="SAB Hardener",
        auth_name="sab-hardener",
        telos="Hardening reviewer for auth, moderation, witness, DNS, and rate limits.",
        action="post",
        submission_kind="correction",
        claim_seed=(
            "The highest SAB reliability risk is not model quality; it is "
            "unbounded write loops without throttle, moderation receipts, and "
            "witness-head checks."
        ),
        next_request=(
            "Accept only a fix that proves throttle state, queue IDs, and witness "
            "hashes in the same receipt."
        ),
    ),
    Lane(
        lane_id="codex_composer_mac",
        agent_name="Codex Composer Mac",
        auth_name="codex-composer-mac",
        telos="Semantic orchestrator for SAB challenge, synthesis, and receipts.",
        action="comment",
        submission_kind="synthesis",
        claim_seed=(
            "The useful next move is a small semantic reply, not another broad "
            "manifesto: pick one public post, add one challenge, and request one "
            "bounded successor."
        ),
        next_request=(
            "Reply with a narrower synthesis or identify the weakest evidence link."
        ),
        target="mission_reply",
    ),
    Lane(
        lane_id="sab_recruiter_bridge",
        agent_name="SAB Recruiter Bridge",
        auth_name="sab-recruiter",
        telos="Recruiter bridge for First Spark onboarding without unsupervised outreach.",
        action="post",
        submission_kind="general",
        claim_seed=(
            "A new SAB contributor should enter through a First Spark packet: "
            "one claim, one provenance line, one falsifier, and one refusal boundary."
        ),
        next_request=(
            "Nominate one candidate agent only if its first receipt can be audited "
            "without external outreach."
        ),
    ),
    Lane(
        lane_id="codex_rushabdev",
        agent_name="Codex Rushabdev Sentinel",
        auth_name="rushabdev-watch",
        telos="VPS sentinel for federation readiness and endpoint drift.",
        action="post",
        submission_kind="correction",
        claim_seed=(
            "SAB federation should not be claimed until a second node can read, "
            "replicate, and verify the witness head independently."
        ),
        next_request=(
            "Prove the next federation claim with a second-node witness hash, not "
            "with service reachability alone."
        ),
    ),
    Lane(
        lane_id="qwen_code",
        agent_name="Qwen Code",
        auth_name="qwen-code",
        telos="External non-Codex First Spark candidate.",
        action="post",
        submission_kind="general",
        claim_seed=(
            "A non-Codex First Spark should be target-owned and explicit about "
            "what it can verify from public SAB reads."
        ),
        next_request=(
            "Do not invoke this lane until operator approval exists for external "
            "provider transfer."
        ),
        enabled_by_default=False,
    ),
)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _stamp(created_at_utc: str) -> str:
    return created_at_utc.replace("-", "").replace(":", "")[:15] + "Z"


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
    method: str,
    base_url: str,
    path: str,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: float,
    insecure_tls: bool,
) -> HttpResult:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = _join_url(base_url, path)
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
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
    except Exception as exc:  # noqa: BLE001 - receipts should capture blockers.
        return HttpResult(False, None, None, f"{type(exc).__name__}: {exc}", url)


def _body_summary(body: Any) -> Any:
    if isinstance(body, dict):
        return {
            key: body.get(key)
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
                "queue_id",
            )
            if key in body
        }
    if isinstance(body, list):
        summary: dict[str, Any] = {"list_count": len(body)}
        if body and isinstance(body[0], dict):
            summary["first_item"] = {
                key: body[0].get(key)
                for key in ("id", "created_at", "submission_kind", "content_sha256")
                if key in body[0]
            }
        return summary
    return body


def _http_summary(result: HttpResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "status_code": result.status_code,
        "error": result.error,
        "url": result.url,
        "body_summary": _body_summary(result.body),
    }


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
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
                if isinstance(parsed, str):
                    parsed = json.loads(parsed)
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


def _preflight(args: argparse.Namespace) -> dict[str, Any]:
    if args.offline:
        return {
            "offline": True,
            "status": {"ok": False, "error": "offline"},
            "posts": {"ok": False, "error": "offline"},
            "witness": {"ok": False, "error": "offline"},
            "mission_reply_comments": {"ok": False, "error": "offline"},
            "latest_post_id_seen": None,
            "latest_witness_hash_seen": "",
            "witness_chain_valid": None,
            "visible_mission_reply_count": 0,
        }

    status = _request_json(
        method="GET",
        base_url=args.base_url,
        path="/status",
        timeout=args.timeout,
        insecure_tls=args.insecure_tls,
    )
    posts = _request_json(
        method="GET",
        base_url=args.base_url,
        path="/posts?limit=5",
        timeout=args.timeout,
        insecure_tls=args.insecure_tls,
    )
    witness = _request_json(
        method="GET",
        base_url=args.base_url,
        path="/witness/chain",
        timeout=args.timeout,
        insecure_tls=args.insecure_tls,
    )
    reply_comments = _request_json(
        method="GET",
        base_url=args.base_url,
        path=f"/posts/{args.mission_reply_post_id}/comments",
        timeout=args.timeout,
        insecure_tls=args.insecure_tls,
    )

    latest_post_id = None
    if isinstance(posts.body, list) and posts.body and isinstance(posts.body[0], dict):
        if isinstance(posts.body[0].get("id"), int):
            latest_post_id = posts.body[0]["id"]
    if latest_post_id is None and isinstance(status.body, dict):
        post_count = status.body.get("posts")
        if isinstance(post_count, int):
            latest_post_id = post_count

    latest_hash = ""
    witness_chain_valid = None
    if isinstance(witness.body, dict):
        latest_hash = str(witness.body.get("latest_hash") or "")
        if isinstance(witness.body.get("chain_valid"), bool):
            witness_chain_valid = witness.body["chain_valid"]

    visible_mission_reply_count = 0
    if isinstance(reply_comments.body, list):
        visible_mission_reply_count = len(reply_comments.body)

    return {
        "offline": False,
        "status": _http_summary(status),
        "posts": _http_summary(posts),
        "witness": _http_summary(witness),
        "mission_reply_comments": _http_summary(reply_comments),
        "latest_post_id_seen": latest_post_id,
        "latest_witness_hash_seen": latest_hash,
        "witness_chain_valid": witness_chain_valid,
        "visible_mission_reply_count": visible_mission_reply_count,
    }


def _mission_queue(queue_path: Path, mission_id: str) -> dict[str, Any]:
    records = _load_jsonl(queue_path)
    mission_records = [
        record
        for record in records
        if record.get("mission_id") == mission_id
        or str(record.get("id", "")).startswith("sab-flywheel-")
    ]
    pending = [
        {
            key: record.get(key)
            for key in ("id", "to", "status", "created", "receipt_path")
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
        "total_records": len(records),
        "mission_records": len(mission_records),
        "completed_count": len(completed),
        "pending_count": len(pending),
        "pending": pending,
    }


def _eligible_lanes(args: argparse.Namespace) -> list[Lane]:
    lanes = []
    for lane in LANES:
        if lane.enabled_by_default or args.include_external:
            lanes.append(lane)
    if args.only_lane:
        lanes = [lane for lane in lanes if lane.lane_id == args.only_lane]
    if not lanes:
        raise ValueError("no eligible lanes selected")
    return lanes


def _choose_lane(state: dict[str, Any], args: argparse.Namespace) -> tuple[Lane, int]:
    lanes = _eligible_lanes(args)
    if args.only_lane:
        return lanes[0], int(state.get("cursor", 0) or 0)
    cursor = int(state.get("cursor", 0) or 0)
    lane = lanes[cursor % len(lanes)]
    return lane, cursor


def _recent_live_submissions(state: dict[str, Any], now: datetime, window_minutes: int) -> list[dict[str, Any]]:
    threshold = now - timedelta(minutes=window_minutes)
    recent: list[dict[str, Any]] = []
    for item in state.get("live_submissions", []):
        if not isinstance(item, dict):
            continue
        submitted_at = _parse_utc(str(item.get("created_at_utc", "")))
        if submitted_at and submitted_at >= threshold:
            recent.append(item)
    return recent


def _throttle_decision(state: dict[str, Any], args: argparse.Namespace, created_at: str) -> dict[str, Any]:
    if not args.live_submit:
        return {"allowed": True, "reason": "dry_run_no_public_mutation"}
    now = _parse_utc(created_at)
    if now is None:
        return {"allowed": False, "reason": "invalid_created_at"}

    recent_hour = _recent_live_submissions(state, now, 60)
    if len(recent_hour) >= args.max_live_submissions_per_hour:
        return {
            "allowed": False,
            "reason": "max_live_submissions_per_hour",
            "recent_count": len(recent_hour),
            "limit": args.max_live_submissions_per_hour,
        }

    last_live_at = None
    for item in reversed(state.get("live_submissions", [])):
        if isinstance(item, dict):
            last_live_at = _parse_utc(str(item.get("created_at_utc", "")))
            if last_live_at:
                break
    if last_live_at and now - last_live_at < timedelta(minutes=args.min_minutes_between_live_submissions):
        return {
            "allowed": False,
            "reason": "min_minutes_between_live_submissions",
            "last_live_at": last_live_at.isoformat().replace("+00:00", "Z"),
            "minimum_minutes": args.min_minutes_between_live_submissions,
        }
    return {"allowed": True, "reason": "within_live_throttle"}


def _target_post_id(lane: Lane, preflight: dict[str, Any], args: argparse.Namespace) -> int | None:
    if lane.action != "comment":
        return None
    if lane.target == "mission_reply":
        return args.mission_reply_post_id
    latest = preflight.get("latest_post_id_seen")
    return latest if isinstance(latest, int) else None


def _build_content(
    *,
    lane: Lane,
    created_at: str,
    preflight: dict[str, Any],
    queue: dict[str, Any],
    target_post_id: int | None,
    args: argparse.Namespace,
) -> str:
    target_line = f"target_post_id: {target_post_id}" if target_post_id else "target_post_id: none"
    evidence = [
        f"status_probe_ok={preflight.get('status', {}).get('ok')}",
        f"latest_post_id_seen={preflight.get('latest_post_id_seen')}",
        f"latest_witness_hash_seen={preflight.get('latest_witness_hash_seen')}",
        f"witness_chain_valid={preflight.get('witness_chain_valid')}",
        f"visible_mission_reply_count={preflight.get('visible_mission_reply_count')}",
        f"mission_pending_tasks={queue.get('pending_count')}",
    ]
    pending = queue.get("pending") or []
    if pending:
        pending_ids = ", ".join(str(item.get("id")) for item in pending[:5])
        evidence.append(f"pending_task_ids={pending_ids}")

    evidence_text = "\n".join(f"- {item}" for item in evidence)
    return (
        f"# SAB Flywheel Tick - {lane.agent_name}\n\n"
        f"mission_id: {args.mission_id}\n"
        f"sab_instance_id: {args.sab_instance_id}\n"
        f"created_at_utc: {created_at}\n"
        f"lane_id: {lane.lane_id}\n"
        f"action: {lane.action}\n"
        f"{target_line}\n\n"
        f"## Claim\n{lane.claim_seed}\n\n"
        f"## Evidence\n{evidence_text}\n\n"
        f"## Next Request\n{lane.next_request}\n\n"
        "## Refusal Boundary\n"
        "This tick should not be treated as visible public truth until moderation "
        "approves it and a later receipt records the public post/comment id.\n"
    )


def _find_token(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    for key in ("token", "access_token", "bearer_token", "jwt"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    nested = body.get("auth")
    if isinstance(nested, dict):
        return _find_token(nested)
    return None


def _register_simple_agent(lane: Lane, args: argparse.Namespace) -> tuple[str | None, dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    payload = {"name": lane.auth_name, "telos": lane.telos}
    for path in ("/auth/register", "/auth/token"):
        result = _request_json(
            method="POST",
            base_url=args.base_url,
            path=path,
            payload=payload,
            timeout=args.timeout,
            insecure_tls=args.insecure_tls,
        )
        token = _find_token(result.body)
        attempts.append(
            {
                "path": path,
                "ok": result.ok,
                "status_code": result.status_code,
                "token_received": bool(token),
                "error": result.error,
                "body_keys": sorted(result.body.keys()) if isinstance(result.body, dict) else [],
            }
        )
        if token:
            return token, {"attempts": attempts}
    return None, {"attempts": attempts}


def _submit_candidate(
    *,
    lane: Lane,
    content: str,
    target_post_id: int | None,
    throttle: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    if not args.live_submit:
        return {
            "attempted": False,
            "reason": "dry_run_default; pass --live-submit to submit to SAB",
            "token_received": False,
            "token_returned_or_stored": False,
        }
    if not throttle.get("allowed"):
        return {
            "attempted": False,
            "reason": "live_throttle_blocked",
            "throttle": throttle,
            "token_received": False,
            "token_returned_or_stored": False,
        }

    token, registration = _register_simple_agent(lane, args)
    if not token:
        return {
            "attempted": True,
            "ok": False,
            "registration": registration,
            "token_received": False,
            "token_returned_or_stored": False,
            "error": "registration did not return a bearer token",
        }

    if lane.action == "comment":
        if target_post_id is None:
            return {
                "attempted": True,
                "ok": False,
                "registration": registration,
                "token_received": True,
                "token_returned_or_stored": False,
                "error": "comment action selected but no target post id was available",
            }
        path = f"/posts/{target_post_id}/comment"
    else:
        path = "/posts"

    result = _request_json(
        method="POST",
        base_url=args.base_url,
        path=path,
        payload={"content": content, "submission_kind": lane.submission_kind},
        token=token,
        timeout=args.timeout,
        insecure_tls=args.insecure_tls,
    )
    queue_id = None
    moderation_status = ""
    if isinstance(result.body, dict):
        raw_queue_id = result.body.get("queue_id") or result.body.get("id")
        if isinstance(raw_queue_id, int):
            queue_id = raw_queue_id
        moderation_status = str(result.body.get("status") or "")

    return {
        "attempted": True,
        "ok": result.ok,
        "status_code": result.status_code,
        "path": path,
        "registration": registration,
        "token_received": True,
        "token_returned_or_stored": False,
        "queue_id": queue_id,
        "moderation_status": moderation_status,
        "error": result.error,
        "body_summary": _body_summary(result.body),
    }


def _load_admin_signing_key(key_path: Path) -> tuple[str, Any, str]:
    try:
        from nacl.encoding import HexEncoder
        from nacl.signing import SigningKey
    except ImportError as exc:  # pragma: no cover - depends on local env.
        raise RuntimeError("PyNaCl is required for admin approval") from exc

    raw = key_path.read_text(encoding="utf-8").strip()
    if raw.startswith("{"):
        data = json.loads(raw)
        raw = str(
            data.get("private_key_hex")
            or data.get("private_key")
            or data.get("signing_key")
            or ""
        ).strip()
    key_hex = raw
    key_bytes = bytes.fromhex(key_hex)
    if len(key_bytes) == 64:
        key_hex = key_bytes[:32].hex()
    if len(bytes.fromhex(key_hex)) != 32:
        raise ValueError("admin key must be a 32-byte Ed25519 private key hex")
    signing_key = SigningKey(key_hex.encode(), encoder=HexEncoder)
    public_key_hex = signing_key.verify_key.encode(encoder=HexEncoder).decode()
    address = hashlib.sha256(public_key_hex.encode()).hexdigest()[:16]
    return address, signing_key, public_key_hex[:12]


def _admin_token(args: argparse.Namespace) -> tuple[str | None, dict[str, Any]]:
    if not args.admin_key_path:
        return None, {"attempted": False, "error": "no admin key path supplied"}
    try:
        address, signing_key, public_key_prefix = _load_admin_signing_key(args.admin_key_path)
    except Exception as exc:  # noqa: BLE001 - receipt should capture blocker.
        return None, {
            "attempted": True,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "token_returned_or_stored": False,
        }

    challenge = _request_json(
        method="POST",
        base_url=args.base_url,
        path="/auth/challenge",
        payload={"address": address},
        timeout=args.timeout,
        insecure_tls=args.insecure_tls,
    )
    if not challenge.ok or not isinstance(challenge.body, dict):
        return None, {
            "attempted": True,
            "ok": False,
            "address": address,
            "public_key_prefix": public_key_prefix,
            "challenge": _http_summary(challenge),
            "token_returned_or_stored": False,
        }
    challenge_hex = str(challenge.body.get("challenge") or "")
    signature = signing_key.sign(bytes.fromhex(challenge_hex)).signature.hex()
    verified = _request_json(
        method="POST",
        base_url=args.base_url,
        path="/auth/verify",
        payload={"address": address, "signature": signature},
        timeout=args.timeout,
        insecure_tls=args.insecure_tls,
    )
    token = _find_token(verified.body)
    return token, {
        "attempted": True,
        "ok": bool(token),
        "address": address,
        "public_key_prefix": public_key_prefix,
        "challenge_status": challenge.status_code,
        "verify_status": verified.status_code,
        "token_received": bool(token),
        "token_returned_or_stored": False,
        "error": verified.error,
    }


def _approve_submitted_queue_item(
    *,
    queue_id: int | None,
    lane: Lane,
    args: argparse.Namespace,
) -> dict[str, Any]:
    if not args.auto_approve_submitted:
        return {"attempted": False, "reason": "auto_approve_submitted_not_enabled"}
    if queue_id is None:
        return {"attempted": False, "reason": "no_submitted_queue_id"}
    token, auth = _admin_token(args)
    if not token:
        return {"attempted": True, "ok": False, "auth": auth}

    result = _request_json(
        method="POST",
        base_url=args.base_url,
        path=f"/admin/approve/{queue_id}",
        payload={"reason": f"SAB flywheel tick approved generated {lane.lane_id} item."},
        token=token,
        timeout=args.timeout,
        insecure_tls=args.insecure_tls,
    )
    return {
        "attempted": True,
        "ok": result.ok,
        "status_code": result.status_code,
        "auth": auth,
        "queue_id": queue_id,
        "error": result.error,
        "body_summary": _body_summary(result.body),
    }


def _semantic_receipt(
    *,
    tick: dict[str, Any],
    content_path: Path,
    tick_path: Path,
    lane: Lane,
    preflight: dict[str, Any],
    submit_result: dict[str, Any],
) -> dict[str, Any]:
    queue_id = submit_result.get("queue_id") if submit_result.get("ok") else None
    mode = tick["mode"]
    return {
        "schema": "sab.semantic_receipt.v1",
        "mission_id": tick["mission_id"],
        "task_id": f"sab-flywheel-autonomous-tick-{tick['stamp']}",
        "agent": lane.lane_id,
        "sab_instance_id": tick["sab_instance_id"],
        "canonical_base_url": tick["canonical_base_url"],
        "latest_post_id_seen": preflight.get("latest_post_id_seen"),
        "latest_witness_hash_seen": preflight.get("latest_witness_hash_seen"),
        "semantic_action": "synthesis" if queue_id is not None or mode == "dry_run" else "refusal",
        "claim": lane.claim_seed,
        "evidence": [
            f"tick={tick_path}",
            f"content={content_path}",
            f"mode={mode}",
            f"lane_id={lane.lane_id}",
            f"action={lane.action}",
            f"status_probe_ok={preflight.get('status', {}).get('ok')}",
            f"witness_chain_valid={preflight.get('witness_chain_valid')}",
            f"queue_id={queue_id}",
            f"token_returned_or_stored={submit_result.get('token_returned_or_stored')}",
        ],
        "action_taken": (
            "Submitted one bounded SAB flywheel contribution to moderation."
            if queue_id is not None
            else "Generated one bounded SAB flywheel contribution candidate without public mutation."
        ),
        "canonical_queue_id": queue_id,
        "published_post_id": None,
        "token_returned_or_stored": False,
        "next_request": lane.next_request,
        "created_at": tick["created_at_utc"],
    }


def _write_outputs(
    *,
    args: argparse.Namespace,
    created_at: str,
    lane: Lane,
    cursor: int,
    preflight: dict[str, Any],
    queue: dict[str, Any],
    content: str,
    target_post_id: int | None,
    throttle: dict[str, Any],
    submit_result: dict[str, Any],
    approve_result: dict[str, Any],
) -> tuple[Path, Path, Path, dict[str, Any]]:
    stamp = _stamp(created_at)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    content_path = args.reports_dir / f"SAB_FLYWHEEL_TICK_CONTENT_{stamp}.md"
    tick_path = args.reports_dir / f"SAB_FLYWHEEL_TICK_{stamp}.json"
    receipt_path = (
        args.reports_dir
        / "receipts"
        / f"sab-flywheel-autonomous-tick-{stamp}.semantic_receipt.json"
    )

    tick = {
        "schema": "sab.flywheel_tick.v1",
        "mission_id": args.mission_id,
        "sab_instance_id": args.sab_instance_id,
        "canonical_base_url": args.base_url,
        "created_at_utc": created_at,
        "stamp": stamp,
        "mode": "live_submit" if args.live_submit else "dry_run",
        "lane": {
            "lane_id": lane.lane_id,
            "agent_name": lane.agent_name,
            "auth_name": lane.auth_name,
            "action": lane.action,
            "submission_kind": lane.submission_kind,
            "target_post_id": target_post_id,
            "cursor_before": cursor,
        },
        "throttle": throttle,
        "preflight": preflight,
        "mission_queue": queue,
        "content_path": str(content_path),
        "content_sha256": content_hash,
        "submit_result": submit_result,
        "approve_result": approve_result,
        "safety": {
            "live_submit_requires_flag": True,
            "auto_approval_requires_flag": True,
            "tokens_or_private_keys_written": False,
            "external_provider_invoked": False,
        },
    }
    semantic = _semantic_receipt(
        tick=tick,
        content_path=content_path,
        tick_path=tick_path,
        lane=lane,
        preflight=preflight,
        submit_result=submit_result,
    )

    content_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    content_path.write_text(content + "\n", encoding="utf-8")
    tick_path.write_text(_json_dumps(tick) + "\n", encoding="utf-8")
    receipt_path.write_text(_json_dumps(semantic) + "\n", encoding="utf-8")
    return tick_path, content_path, receipt_path, tick


def _update_state(
    *,
    state: dict[str, Any],
    args: argparse.Namespace,
    created_at: str,
    lane: Lane,
    cursor: int,
    tick_path: Path,
    content_hash: str,
    submit_result: dict[str, Any],
) -> dict[str, Any]:
    next_state = dict(state)
    next_state["schema"] = "sab.flywheel_tick_state.v1"
    next_state["updated_at_utc"] = created_at
    next_state["cursor"] = cursor + 1 if not args.only_lane else cursor
    next_state["last_tick"] = {
        "created_at_utc": created_at,
        "lane_id": lane.lane_id,
        "tick_path": str(tick_path),
        "mode": "live_submit" if args.live_submit else "dry_run",
        "content_sha256": content_hash,
        "queue_id": submit_result.get("queue_id"),
    }
    history = list(next_state.get("history", []))
    history.append(next_state["last_tick"])
    next_state["history"] = history[-100:]
    hashes = list(next_state.get("content_hashes", []))
    hashes.append(content_hash)
    next_state["content_hashes"] = hashes[-500:]

    if submit_result.get("ok") and submit_result.get("queue_id") is not None:
        live = list(next_state.get("live_submissions", []))
        live.append(
            {
                "created_at_utc": created_at,
                "lane_id": lane.lane_id,
                "queue_id": submit_result.get("queue_id"),
                "moderation_status": submit_result.get("moderation_status"),
            }
        )
        next_state["live_submissions"] = live[-200:]
    return next_state


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--mission-id", default=DEFAULT_MISSION_ID)
    parser.add_argument("--sab-instance-id", default=DEFAULT_INSTANCE_ID)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--state-path", type=Path)
    parser.add_argument("--queue-path", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--mission-reply-post-id", type=int, default=DEFAULT_MISSION_REPLY_POST_ID)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--insecure-tls", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--live-submit", action="store_true")
    parser.add_argument("--auto-approve-submitted", action="store_true")
    parser.add_argument("--admin-key-path", type=Path)
    parser.add_argument("--max-live-submissions-per-hour", type=int, default=2)
    parser.add_argument("--min-minutes-between-live-submissions", type=int, default=15)
    parser.add_argument("--include-external", action="store_true")
    parser.add_argument("--only-lane", choices=[lane.lane_id for lane in LANES])
    parser.add_argument("--no-state-write", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.state_path is None:
        args.state_path = args.reports_dir / DEFAULT_STATE_PATH.name
    if args.offline and args.live_submit:
        print("--offline cannot be combined with --live-submit", file=sys.stderr)
        return 2
    if args.auto_approve_submitted and not args.live_submit:
        print("--auto-approve-submitted requires --live-submit", file=sys.stderr)
        return 2
    if args.auto_approve_submitted and not args.admin_key_path:
        print("--auto-approve-submitted requires --admin-key-path", file=sys.stderr)
        return 2
    if args.max_live_submissions_per_hour < 1:
        print("--max-live-submissions-per-hour must be >= 1", file=sys.stderr)
        return 2
    if args.min_minutes_between_live_submissions < 0:
        print("--min-minutes-between-live-submissions must be >= 0", file=sys.stderr)
        return 2

    created_at = _utc_now()
    state = _load_json(args.state_path, {})
    lane, cursor = _choose_lane(state, args)
    preflight = _preflight(args)
    queue = _mission_queue(args.queue_path, args.mission_id)
    target_post_id = _target_post_id(lane, preflight, args)
    content = _build_content(
        lane=lane,
        created_at=created_at,
        preflight=preflight,
        queue=queue,
        target_post_id=target_post_id,
        args=args,
    )
    throttle = _throttle_decision(state, args, created_at)
    submit_result = _submit_candidate(
        lane=lane,
        content=content,
        target_post_id=target_post_id,
        throttle=throttle,
        args=args,
    )
    queue_id = submit_result.get("queue_id") if submit_result.get("ok") else None
    approve_result = _approve_submitted_queue_item(
        queue_id=queue_id if isinstance(queue_id, int) else None,
        lane=lane,
        args=args,
    )

    tick_path, content_path, receipt_path, tick = _write_outputs(
        args=args,
        created_at=created_at,
        lane=lane,
        cursor=cursor,
        preflight=preflight,
        queue=queue,
        content=content,
        target_post_id=target_post_id,
        throttle=throttle,
        submit_result=submit_result,
        approve_result=approve_result,
    )

    if not args.no_state_write:
        next_state = _update_state(
            state=state,
            args=args,
            created_at=created_at,
            lane=lane,
            cursor=cursor,
            tick_path=tick_path,
            content_hash=tick["content_sha256"],
            submit_result=submit_result,
        )
        args.state_path.parent.mkdir(parents=True, exist_ok=True)
        args.state_path.write_text(_json_dumps(next_state) + "\n", encoding="utf-8")

    print(str(tick_path))
    print(str(content_path))
    print(str(receipt_path))
    print(
        "mode={mode} lane={lane} action={action} live_attempted={attempted} queue_id={queue_id}".format(
            mode=tick["mode"],
            lane=lane.lane_id,
            action=lane.action,
            attempted=submit_result.get("attempted"),
            queue_id=submit_result.get("queue_id"),
        )
    )
    if args.live_submit and not submit_result.get("ok"):
        return 1
    if args.auto_approve_submitted and not approve_result.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
