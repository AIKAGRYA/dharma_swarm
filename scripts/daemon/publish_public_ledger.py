#!/usr/bin/env python3
"""Lane 3 public miss/hit ledger: append a timestamped GitHub issue comment.

The GitHub issue is the log. This process never PATCHes a prior comment.
Local chain state is rewritten as a single JSON object (not JSONL).
Fail-closed after 30 days without human input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

SCHEMA_HEARTBEAT = "dharma.public_ledger.heartbeat.v1"
SCHEMA_DIGEST = "dharma.public_ledger.miss_hit.v1"
SCHEMA_CHAIN = "dharma.public_ledger.chain.v1"
MARKER = "<!-- dharma-public-ledger:v1 -->"
HUMAN_SILENCE = timedelta(days=30)
ISSUE_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/issues/(\d+)/?$"
)


class LedgerPublishError(ValueError):
    """Refuse to publish: schema, token, or transport is not admissible."""


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def sha256_hex(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_issue_url(url: str) -> tuple[str, int]:
    match = ISSUE_RE.fullmatch(url.strip())
    if match is None:
        raise LedgerPublishError(f"invalid issue url: {url!r}")
    return f"{match.group(1)}/{match.group(2)}", int(match.group(3))


def parse_timestamp(raw: str | None) -> datetime | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError as exc:
        raise LedgerPublishError(f"invalid timestamp: {raw!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_digest(digest: dict[str, Any]) -> None:
    if digest.get("schema") != SCHEMA_DIGEST:
        raise LedgerPublishError("digest schema mismatch")
    entries = digest.get("entries")
    if not isinstance(entries, list):
        raise LedgerPublishError("digest entries must be a list")
    misses = [row for row in entries if isinstance(row, dict) and row.get("kind") == "miss"]
    hits = [row for row in entries if isinstance(row, dict) and row.get("kind") == "hit"]
    try:
        claimed_misses = int(digest["misses"])
        claimed_hits = int(digest["hits"])
    except (KeyError, TypeError, ValueError) as exc:
        raise LedgerPublishError("digest hits/misses must be integers") from exc
    if claimed_misses != len(misses) or claimed_hits != len(hits):
        raise LedgerPublishError("miss_count_mismatch")
    if digest.get("schema") and digest.get("observed_at") in (None, ""):
        raise LedgerPublishError("digest observed_at required")


def validate_heartbeat(heartbeat: dict[str, Any]) -> None:
    if heartbeat.get("schema") != SCHEMA_HEARTBEAT:
        raise LedgerPublishError("heartbeat schema mismatch")
    if not heartbeat.get("observed_at"):
        raise LedgerPublishError("heartbeat observed_at required")


def compose_entry(
    *,
    heartbeat: dict[str, Any],
    digest: dict[str, Any],
    prev_digest: str | None,
    now: datetime,
) -> tuple[str, str]:
    validate_heartbeat(heartbeat)
    validate_digest(digest)
    observed = _iso(now)
    prev = prev_digest or "none"
    hb_sha = sha256_hex(heartbeat)
    dg_sha = sha256_hex(digest)
    miss_lines = []
    for row in digest["entries"]:
        if not isinstance(row, dict):
            continue
        ident = row.get("invariant_id", "")
        kind = row.get("kind", "")
        extra = row.get("transition_id")
        suffix = f" transition={extra}" if extra else ""
        miss_lines.append(f"- {kind}: `{ident}` `{row.get('digest', '')}`{suffix}")
    body_core = "\n".join(
        [
            MARKER,
            f"<!-- prev:{prev} -->",
            f"# Public Miss Ledger — {observed}",
            "",
            f"- heartbeat_sha256: `{hb_sha}`",
            f"- digest_sha256: `{dg_sha}`",
            f"- daemon: `{heartbeat.get('daemon_id', '')}`",
            f"- heartbeat_status: `{heartbeat.get('status', '')}`",
            f"- hits: {digest['hits']}",
            f"- misses: {digest['misses']}",
            "",
            "## Entries",
            "",
            *miss_lines,
            "",
            "This comment is append-only. Prior comments are not edited.",
            "",
        ]
    )
    entry_digest = "sha256:" + hashlib.sha256(body_core.encode("utf-8")).hexdigest()
    body = body_core.replace(
        MARKER,
        f"{MARKER}\n<!-- digest:{entry_digest} -->",
        1,
    )
    return body, entry_digest


def human_silence_halted(last_human_input: str | None, now: datetime) -> bool:
    parsed = parse_timestamp(last_human_input) if last_human_input else None
    if parsed is None:
        return True
    return (now - parsed) >= HUMAN_SILENCE


def default_poster(
    *,
    method: str,
    repo: str,
    issue_number: int,
    body: str,
    token: str,
) -> dict[str, Any]:
    if method != "POST":
        raise LedgerPublishError("only POST is admitted (append-only)")
    payload = json.dumps({"body": body}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "dharma-public-ledger",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LedgerPublishError(f"github post failed: {exc}") from exc


def _read_chain(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    head = payload.get("head")
    return head if isinstance(head, str) else None


def _write_chain(path: Path, head: str, now: datetime) -> None:
    payload = {
        "schema": SCHEMA_CHAIN,
        "head": head,
        "updated_at": _iso(now),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def publish(
    *,
    heartbeat: dict[str, Any],
    digest: dict[str, Any],
    issue_url: str,
    token: str,
    now: datetime,
    last_human_input: str | None,
    dry_run: bool,
    poster: Callable[..., dict[str, Any]],
    chain_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    if human_silence_halted(last_human_input, now):
        return {
            "posted": False,
            "dry_run": dry_run,
            "halted": True,
            "reason": "human_silence",
            "entry_digest": None,
        }
    if not dry_run and not token:
        raise LedgerPublishError("GITHUB_TOKEN required to post")
    repo, issue_number = parse_issue_url(issue_url)
    prev = _read_chain(chain_path)
    body, entry_digest = compose_entry(
        heartbeat=heartbeat, digest=digest, prev_digest=prev, now=now
    )
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(body, encoding="utf-8")
    if chain_path is not None:
        _write_chain(chain_path, entry_digest, now)
    posted = False
    html_url = None
    if not dry_run:
        response = poster(
            method="POST",
            repo=repo,
            issue_number=issue_number,
            body=body,
            token=token,
        )
        posted = True
        html_url = response.get("html_url") if isinstance(response, dict) else None
    return {
        "posted": posted,
        "dry_run": dry_run,
        "halted": False,
        "reason": None,
        "entry_digest": entry_digest,
        "issue": f"{repo}#{issue_number}",
        "comment_url": html_url,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--heartbeat", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--issue-url", required=True)
    parser.add_argument("--last-human-input", default="")
    parser.add_argument("--last-human-input-file", default="")
    parser.add_argument("--chain-path", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--now",
        default="",
        help="ISO-8601 UTC override (tests / replay only)",
    )
    args = parser.parse_args(argv)
    try:
        heartbeat = json.loads(Path(args.heartbeat).read_text(encoding="utf-8"))
        digest = json.loads(Path(args.digest).read_text(encoding="utf-8"))
        last_human = args.last_human_input.strip() or None
        if args.last_human_input_file:
            last_human = Path(args.last_human_input_file).read_text(
                encoding="utf-8"
            ).strip()
        now = (
            parse_timestamp(args.now)
            if args.now
            else datetime.now(timezone.utc)
        )
        if now is None:
            raise LedgerPublishError("invalid --now")
        result = publish(
            heartbeat=heartbeat,
            digest=digest,
            issue_url=args.issue_url,
            token=os.environ.get("GITHUB_TOKEN", ""),
            now=now,
            last_human_input=last_human,
            dry_run=args.dry_run,
            poster=default_poster,
            chain_path=Path(args.chain_path) if args.chain_path else None,
            output_path=Path(args.output) if args.output else None,
        )
    except (OSError, json.JSONDecodeError, LedgerPublishError) as exc:
        print(f"ledger: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    if result.get("halted"):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
