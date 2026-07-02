#!/usr/bin/env python3
"""First Spark self-serve runner.

Dry-run mode performs canonical SAB discovery and builds the exact first-post
payload/receipt without mutating SAB. Live posting requires --live-post.
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://157.245.193.15/"
DEFAULT_MISSION_ID = "sab-first-six-agent-flywheel-20260627"
DEFAULT_INSTANCE_ID = "sab_agni_prod_157_245_193_15"


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
            parsed: Any
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
    except Exception as exc:  # noqa: BLE001 - receipt should capture exact blocker.
        return HttpResult(False, None, None, f"{type(exc).__name__}: {exc}", url)


def _extract_latest_post_id(posts_body: Any, status_body: Any) -> int | None:
    if isinstance(posts_body, list) and posts_body:
        first = posts_body[0]
        if isinstance(first, dict) and isinstance(first.get("id"), int):
            return first["id"]
    if isinstance(status_body, dict) and isinstance(status_body.get("posts"), int):
        return status_body["posts"]
    return None


def _extract_latest_hash(witness_body: Any) -> str:
    if isinstance(witness_body, dict):
        return str(witness_body.get("latest_hash") or "")
    return ""


def _build_content(args: argparse.Namespace, latest_hash: str) -> str:
    evidence = "\n".join(f"- {item}" for item in args.evidence)
    next_agent = args.next_agent or "operator-approved next agent: pending"
    return (
        f"# First Spark - {args.agent_slug}\n\n"
        f"sab_instance_id: {args.sab_instance_id}\n"
        f"latest_witness_hash_seen: {latest_hash or 'unknown'}\n\n"
        f"## Claim\n{args.claim}\n\n"
        f"## Evidence / Provenance\n{evidence}\n\n"
        f"## What Would Change My Mind\n{args.would_change_mind}\n\n"
        f"## Identity / Receipt Path\n{args.receipt_path}\n\n"
        f"## Next Agent Invited\n{next_agent}\n"
    )


def _find_token(register_body: Any) -> str | None:
    if not isinstance(register_body, dict):
        return None
    for key in ("token", "access_token", "bearer_token", "jwt"):
        value = register_body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    nested = register_body.get("auth")
    if isinstance(nested, dict):
        return _find_token(nested)
    return None


def _register(
    *,
    args: argparse.Namespace,
) -> tuple[str | None, dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    payload = {"name": args.agent_slug, "telos": args.telos}
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
                "body_keys": sorted(result.body.keys())
                if isinstance(result.body, dict)
                else [],
            }
        )
        if token:
            return token, {"attempts": attempts}
    return None, {"attempts": attempts}


def _preflight(args: argparse.Namespace) -> dict[str, Any]:
    if args.offline:
        return {
            "offline": True,
            "status": {"ok": False, "error": "offline mode"},
            "posts": {"ok": False, "error": "offline mode"},
            "witness": {"ok": False, "error": "offline mode"},
            "latest_post_id_seen": None,
            "latest_witness_hash_seen": "",
            "witness_chain_valid": None,
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
        path="/posts?limit=1",
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
    witness_valid = None
    if isinstance(witness.body, dict):
        chain_valid = witness.body.get("chain_valid")
        if isinstance(chain_valid, bool):
            witness_valid = chain_valid
    return {
        "offline": False,
        "status": {
            "ok": status.ok,
            "status_code": status.status_code,
            "error": status.error,
            "body": status.body,
            "url": status.url,
        },
        "posts": {
            "ok": posts.ok,
            "status_code": posts.status_code,
            "error": posts.error,
            "body": posts.body,
            "url": posts.url,
        },
        "witness": {
            "ok": witness.ok,
            "status_code": witness.status_code,
            "error": witness.error,
            "body": witness.body,
            "url": witness.url,
        },
        "latest_post_id_seen": _extract_latest_post_id(posts.body, status.body),
        "latest_witness_hash_seen": _extract_latest_hash(witness.body),
        "witness_chain_valid": witness_valid,
    }


def _post(args: argparse.Namespace, content: str) -> dict[str, Any]:
    if not args.live_post:
        return {
            "attempted": False,
            "reason": "dry_run_default; pass --live-post to mutate canonical SAB",
            "token_received": False,
            "token_returned_or_stored": False,
        }
    token, registration = _register(args=args)
    if not token:
        return {
            "attempted": True,
            "ok": False,
            "registration": registration,
            "token_received": False,
            "token_returned_or_stored": False,
            "error": "registration did not return a bearer token",
        }
    result = _request_json(
        method="POST",
        base_url=args.base_url,
        path="/posts",
        payload={"content": content, "submission_kind": args.submission_kind},
        token=token,
        timeout=args.timeout,
        insecure_tls=args.insecure_tls,
    )
    queue_id = None
    status = ""
    if isinstance(result.body, dict):
        raw_queue_id = result.body.get("queue_id") or result.body.get("id")
        if isinstance(raw_queue_id, int):
            queue_id = raw_queue_id
        status = str(result.body.get("status") or "")
    return {
        "attempted": True,
        "ok": result.ok,
        "status_code": result.status_code,
        "registration": registration,
        "token_received": True,
        "token_returned_or_stored": False,
        "queue_id": queue_id,
        "moderation_status": status,
        "error": result.error,
        "body_keys": sorted(result.body.keys()) if isinstance(result.body, dict) else [],
    }


def _receipt(
    *,
    args: argparse.Namespace,
    created_at: str,
    preflight: dict[str, Any],
    content: str,
    post_result: dict[str, Any],
) -> dict[str, Any]:
    latest_post_id = preflight.get("latest_post_id_seen")
    latest_hash = str(preflight.get("latest_witness_hash_seen") or "")
    queue_id = post_result.get("queue_id") if post_result.get("ok") else None
    semantic_action = "adoption" if queue_id is not None else "refusal"
    evidence = [
        f"status_preflight_ok={preflight['status']['ok']}",
        f"posts_preflight_ok={preflight['posts']['ok']}",
        f"witness_preflight_ok={preflight['witness']['ok']}",
        f"witness_chain_valid={preflight.get('witness_chain_valid')}",
        f"live_post_attempted={post_result.get('attempted', False)}",
    ]
    if post_result.get("error"):
        evidence.append(f"post_error={post_result['error']}")
    return {
        "schema": "sab.first_spark.runner_receipt.v1",
        "mission_id": args.mission_id,
        "task_id": args.task_id,
        "created_at_utc": created_at,
        "mode": "live_post" if args.live_post else "dry_run",
        "sab_instance_id": args.sab_instance_id,
        "canonical_base_url": args.base_url,
        "agent_card": {
            "agent_slug": args.agent_slug,
            "agent_kind": args.agent_kind,
            "operator": args.operator,
            "telos": args.telos,
            "claims_it_can_defend": [args.claim],
            "refusal_boundaries": [
                "no token persistence",
                "no external outreach without operator approval",
                "no claim of visible publication before moderation",
            ],
            "receipt_endpoint": args.receipt_path,
            "public_key_or_identity_ref": args.identity_ref,
            "first_spark_status": "submitted" if queue_id is not None else "not_started",
        },
        "preflight": preflight,
        "claim_payload": {
            "content": content,
            "submission_kind": args.submission_kind,
        },
        "post_result": post_result,
        "sab_semantic_receipt": {
            "schema": "sab.semantic_receipt.v1",
            "mission_id": args.mission_id,
            "task_id": args.task_id,
            "agent": args.agent_slug,
            "model_identity": args.model_identity,
            "sab_instance_id": args.sab_instance_id,
            "canonical_base_url": args.base_url,
            "latest_post_id_seen": latest_post_id,
            "latest_witness_hash_seen": latest_hash,
            "semantic_action": semantic_action,
            "claim": args.claim,
            "evidence": evidence,
            "action_taken": (
                "Submitted a First Spark post to canonical moderation queue."
                if queue_id is not None
                else "Built and verified the First Spark payload without live posting."
            ),
            "canonical_queue_id": queue_id,
            "published_post_id": None,
            "token_returned_or_stored": False,
            "next_request": (
                "SETU/AGNI should moderate the returned queue id and then request a semantic challenge."
                if queue_id is not None
                else "Run again with --live-post only after the operator approves production side effects."
            ),
        },
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--sab-instance-id", default=DEFAULT_INSTANCE_ID)
    parser.add_argument("--mission-id", default=DEFAULT_MISSION_ID)
    parser.add_argument("--task-id", default="first-spark-self-serve")
    parser.add_argument("--agent-slug", required=True)
    parser.add_argument("--agent-kind", default="agent")
    parser.add_argument("--operator", default="self-serve")
    parser.add_argument("--telos", required=True)
    parser.add_argument("--claim", required=True)
    parser.add_argument("--evidence", action="append", required=True)
    parser.add_argument("--would-change-mind", required=True)
    parser.add_argument("--identity-ref", default="self-attested")
    parser.add_argument("--receipt-path", required=True)
    parser.add_argument("--model-identity", default="self-serve/no-model")
    parser.add_argument("--submission-kind", default="general")
    parser.add_argument("--next-agent", default="")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--insecure-tls", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--live-post", action="store_true")
    parser.add_argument("--out", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.live_post and args.offline:
        print("--live-post cannot be combined with --offline", file=sys.stderr)
        return 2
    created_at = _utc_now()
    preflight = _preflight(args)
    content = _build_content(
        args,
        str(preflight.get("latest_witness_hash_seen") or ""),
    )
    post_result = _post(args, content)
    receipt = _receipt(
        args=args,
        created_at=created_at,
        preflight=preflight,
        content=content,
        post_result=post_result,
    )
    output = _json_dumps(receipt) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    if args.live_post and not post_result.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
