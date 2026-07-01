#!/usr/bin/env python3
"""Render an agent offboarding receipt for a finished work session.

Version: 0.0.0.1

This is the complement to `make onboard`: onboarding tells an agent where it is
starting; offboarding tells the next human or audit agent what was done, what
was verified, what remains dirty, and where to continue.

The command is a projection, not an authority surface. It does not decide that
work is complete. It records the evidence the finishing agent provides plus
current git state. By default it writes fleet-readable receipts under
~/.dharma/ops (override with DHARMA_OPS_DIR). Use --repo-receipt only when a
durable repo handoff is intentionally wanted.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.0.0.1"
OFFBOARD_RECEIPT_NAME = "offboard_receipt"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ops_dir() -> Path:
    override = os.environ.get("DHARMA_OPS_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".dharma" / "ops"


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        ).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def _branch_slug(branch: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", branch.strip() or "detached")
    return slug.strip("-") or "detached"


def _porcelain_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    out = _git("status", "--porcelain=v1")
    for line in out.splitlines():
        if not line:
            continue
        status = line[:2]
        path = line[3:] if len(line) > 3 else ""
        rows.append({"status": status, "path": path})
    return rows


def _dirty_summary(max_files: int) -> dict[str, Any]:
    rows = _porcelain_rows()
    counts = {
        "total": len(rows),
        "staged": 0,
        "unstaged": 0,
        "untracked": 0,
        "deleted": 0,
    }
    for row in rows:
        status = row["status"]
        if status == "??":
            counts["untracked"] += 1
            continue
        if status[0] != " ":
            counts["staged"] += 1
        if status[1] != " ":
            counts["unstaged"] += 1
        if "D" in status:
            counts["deleted"] += 1
    return {
        "dirty": bool(rows),
        "counts": counts,
        "sample": rows[:max_files],
        "sample_truncated": len(rows) > max_files,
    }


def _upstream() -> str:
    return _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")


def _ahead_behind(upstream: str) -> dict[str, int | None]:
    if not upstream:
        return {"ahead": None, "behind": None}
    raw = _git("rev-list", "--left-right", "--count", f"{upstream}...HEAD")
    parts = raw.split()
    if len(parts) != 2:
        return {"ahead": None, "behind": None}
    behind, ahead = parts
    return {"ahead": int(ahead), "behind": int(behind)}


def build_receipt(args: argparse.Namespace) -> dict[str, Any]:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    upstream = _upstream()
    dirty = _dirty_summary(args.max_files)
    return {
        "schema_version": "agent-offboard-v0.0.0.1",
        "generated_at": _now_iso(),
        "repo_root": str(REPO_ROOT),
        "version": VERSION,
        "branch": branch,
        "upstream": upstream,
        "ahead_behind": _ahead_behind(upstream),
        "head_sha": _git("rev-parse", "--short=12", "HEAD"),
        "recent_commits": _git("log", "--oneline", "-5").splitlines(),
        "task": args.task,
        "packet_id": args.packet_id,
        "owners_consulted": args.owner,
        "verification": args.verification,
        "artifacts": args.artifact,
        "claims_not_made": args.claim_not_made,
        "risks_or_blockers": args.risk,
        "next_steps": args.next_step,
        "dirty_summary": dirty,
        "recommended_finish_commands": [
            "git diff --stat",
            "git status --short --branch",
            "run the narrowest meaningful verification for touched files",
            "make agent-build-closeout before PR or merge handoff",
        ],
        "audit_search_tags": [
            "AGENT_OFFBOARD_RECEIPT",
            "OFFBOARD_V0_0_0_1",
            "CONTEXT_PACKET_CLOSEOUT",
        ],
    }


def render_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        "# Agent Offboard Receipt",
        "",
        "Search tags: AGENT_OFFBOARD_RECEIPT OFFBOARD_V0_0_0_1 CONTEXT_PACKET_CLOSEOUT",
        "",
        f"- generated_at: {receipt['generated_at']}",
        f"- version: {receipt['version']}",
        f"- repo_root: {receipt['repo_root']}",
        f"- branch: {receipt['branch']}",
        f"- upstream: {receipt['upstream'] or 'none'}",
        f"- head_sha: {receipt['head_sha']}",
        f"- ahead: {receipt['ahead_behind']['ahead']}",
        f"- behind: {receipt['ahead_behind']['behind']}",
        f"- task: {receipt['task'] or ''}",
        f"- packet_id: {receipt['packet_id'] or ''}",
        f"- dirty: {'yes' if receipt['dirty_summary']['dirty'] else 'no'}",
        f"- dirty_counts: {json.dumps(receipt['dirty_summary']['counts'], sort_keys=True)}",
        "",
        "## Owners Consulted",
    ]
    lines.extend(f"- {item}" for item in receipt["owners_consulted"] or [""])
    lines.extend(["", "## Verification"])
    lines.extend(f"- {item}" for item in receipt["verification"] or [""])
    lines.extend(["", "## Artifacts"])
    lines.extend(f"- {item}" for item in receipt["artifacts"] or [""])
    lines.extend(["", "## Claims Not Made"])
    lines.extend(f"- {item}" for item in receipt["claims_not_made"] or [""])
    lines.extend(["", "## Risks Or Blockers"])
    lines.extend(f"- {item}" for item in receipt["risks_or_blockers"] or [""])
    lines.extend(["", "## Next Steps"])
    lines.extend(f"- {item}" for item in receipt["next_steps"] or [""])
    lines.extend(["", "## Dirty Sample"])
    for row in receipt["dirty_summary"]["sample"]:
        lines.append(f"- {row['status']} {row['path']}")
    if receipt["dirty_summary"]["sample_truncated"]:
        lines.append("- ... sample truncated")
    lines.extend(["", "## Recent Commits"])
    lines.extend(f"- {item}" for item in receipt["recent_commits"])
    lines.append("")
    return "\n".join(lines)


def write_receipts(receipt: dict[str, Any], *, repo_receipt: bool, receipt_dir: Path | None) -> dict[str, str]:
    written: dict[str, str] = {}
    ops_dir = _ops_dir()
    ops_dir.mkdir(parents=True, exist_ok=True)
    ops_json = ops_dir / f"{OFFBOARD_RECEIPT_NAME}.json"
    ops_md = ops_dir / f"{OFFBOARD_RECEIPT_NAME}.md"
    written["ops_json"] = str(ops_json)
    written["ops_markdown"] = str(ops_md)

    if repo_receipt:
        base = receipt_dir or (REPO_ROOT / "reports" / "handoffs" / "offboard")
        base.mkdir(parents=True, exist_ok=True)
        stamp = receipt["generated_at"].replace(":", "").replace("-", "")
        stem = f"{stamp}__{_branch_slug(str(receipt['branch']))}"
        repo_json = base / f"{stem}.json"
        repo_md = base / f"{stem}.md"
        written["repo_json"] = str(repo_json)
        written["repo_markdown"] = str(repo_md)
    payload = dict(receipt)
    payload["written_receipts"] = written
    ops_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ops_md.write_text(render_markdown(payload), encoding="utf-8")
    if repo_receipt:
        repo_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        repo_md.write_text(render_markdown(payload), encoding="utf-8")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="", help="Plain-language task or project closed out")
    parser.add_argument("--packet-id", default="", help="Context packet used, when applicable")
    parser.add_argument("--owner", action="append", default=[], help="Owner file, command, or source consulted")
    parser.add_argument("--verification", action="append", default=[], help="Verification command/result summary")
    parser.add_argument("--artifact", action="append", default=[], help="Artifact, receipt, or file path produced")
    parser.add_argument("--claim-not-made", action="append", default=[], help="Claim intentionally not made")
    parser.add_argument("--risk", action="append", default=[], help="Residual risk or blocker")
    parser.add_argument("--next-step", action="append", default=[], help="Recommended next action")
    parser.add_argument("--repo-receipt", action="store_true", help="Also write durable repo receipt under reports/handoffs/offboard")
    parser.add_argument("--receipt-dir", type=Path, help="Override repo receipt directory, mainly for tests")
    parser.add_argument("--max-files", type=int, default=80, help="Maximum dirty files to include in receipt sample")
    parser.add_argument("--json", action="store_true", help="Emit machine receipt JSON to stdout")
    args = parser.parse_args(argv)

    receipt = build_receipt(args)
    written = write_receipts(receipt, repo_receipt=args.repo_receipt, receipt_dir=args.receipt_dir)
    receipt["written_receipts"] = written

    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(render_markdown(receipt))
        print("Written receipts:")
        for key, value in written.items():
            print(f"- {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
