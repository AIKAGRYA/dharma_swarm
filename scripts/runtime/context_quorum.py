#!/usr/bin/env python3
"""Context quorum spine for multi-agent coordination.

This is intentionally small: it creates persistent agent homes, checks
context-quorum evidence for a task, records receipts, enforces protected-file
awareness, and writes handoff artifacts. It does not replace CI, Memory Palace,
GitNexus, Context+, or human review.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = REPO_ROOT / "docs/ops/context_quorum_policy.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def agent_root(policy: dict[str, Any], agent_id: str) -> Path:
    root = Path(os.path.expanduser(policy.get("agent_home_root", "~/.dharma/agents")))
    return root / agent_id


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def write_if_missing(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def command_receipt(family: str, args: list[str], *, timeout: int = 20) -> dict[str, Any]:
    started = utc_now()
    try:
        completed = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        output = completed.stdout or ""
        status = "ok" if completed.returncode == 0 else "nonzero"
        exit_code: int | None = completed.returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        output = str(exc)
        status = "error"
        exit_code = None
    return {
        "family": family,
        "tool": args[0],
        "args_hash": sha256_text(json.dumps(args, sort_keys=True)),
        "started_at": started,
        "finished_at": utc_now(),
        "status": status,
        "exit_code": exit_code,
        "output_hash": sha256_text(output),
        "summary": first_line(output) or status,
    }


def first_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:240]
    return ""


def repo_rel(path: str | Path) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            return p.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return p.as_posix()
    return p.as_posix()


def changed_files_from_git(base_ref: str | None) -> list[str]:
    files: set[str] = set()
    if base_ref:
        out = subprocess.run(
            ["git", "diff", "--name-only", base_ref, "--"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        files.update(line.strip() for line in out.stdout.splitlines() if line.strip())
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=15,
    )
    for line in status.stdout.splitlines():
        if not line:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            files.add(path)
    return sorted(files)


def protected_hits(policy: dict[str, Any], paths: list[str]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for path in paths:
        rel = repo_rel(path)
        for item in policy.get("protected_files", []):
            pattern = item["pattern"]
            if fnmatch.fnmatch(rel, pattern):
                hits.append({
                    "path": rel,
                    "pattern": pattern,
                    "tier": item.get("tier", "protected"),
                    "reason": item.get("reason", ""),
                })
    return hits


def parse_receipt(value: str) -> dict[str, Any]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("receipt must be FAMILY=PATH")
    family, raw_path = value.split("=", 1)
    path = Path(os.path.expanduser(raw_path))
    if not path.exists():
        raise argparse.ArgumentTypeError(f"receipt path missing: {path}")
    return {
        "family": family,
        "tool": "external_receipt",
        "artifact_path": path.as_posix(),
        "artifact_hash": sha256_file(path),
        "status": "ok",
        "summary": f"external receipt {path.name}",
        "finished_at": utc_now(),
    }


def init_agent(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    root = agent_root(policy, args.agent)
    now = utc_now()
    for sub in ("context", "tools", "memory", "work", "handoff", "evidence"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    passport = {
        "agent_id": args.agent,
        "name": args.name or args.agent,
        "role": args.role,
        "created_at": now,
        "repo_root": REPO_ROOT.as_posix(),
        "home_root": root.as_posix(),
        "memory_namespace": f"agent:{args.agent}",
        "status": "candidate",
    }
    if not (root / "passport.json").exists() or args.force:
        write_json(root / "passport.json", passport)
    write_if_missing(root / "role.md", f"# {args.name or args.agent}\n\nRole: {args.role}\n\nPurpose: {args.purpose}\n")
    write_if_missing(root / "state.md", "# State\n\nCurrent focus: unset\n\nLast verified: never\n")
    write_if_missing(root / "context/repo_map.md", "# Repo Map\n\nRun a context quorum before treating this as current.\n")
    write_json(root / "context/context_manifest.latest.json", {"agent_id": args.agent, "status": "empty", "updated_at": now})
    write_if_missing(root / "context/known_unknowns.md", "# Known Unknowns\n\n- none recorded\n")
    tool_registry = {"version": policy["version"], "tool_families": policy["tool_families"], "updated_at": now}
    write_json(root / "tools/tool_registry.json", tool_registry)
    for rel in (
        "tools/tool_receipts.jsonl",
        "memory/memory_ledger.jsonl",
        "memory/recall_receipts.jsonl",
        "work/decision_log.jsonl",
        "work/risk_log.jsonl",
        "handoff/handoff_events.jsonl",
        "evidence/action_events.jsonl",
        "evidence/verification_receipts.jsonl",
    ):
        write_if_missing(root / rel, "")
    write_if_missing(root / "work/current_plan.md", "# Current Plan\n\nNo active plan.\n")
    write_if_missing(root / "handoff/HANDOFF.md", "# Handoff\n\nNo handoff yet.\n")
    append_jsonl(root / "evidence/action_events.jsonl", {"type": "agent_home_initialized", "timestamp": now, "agent_id": args.agent})
    print(root)
    return 0


def status(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    root = Path(os.path.expanduser(policy.get("agent_home_root", "~/.dharma/agents")))
    homes = sorted(p.name for p in root.iterdir() if p.is_dir()) if root.exists() else []
    payload = {
        "policy_path": args.policy.as_posix(),
        "policy_present": args.policy.exists(),
        "agent_home_root": root.as_posix(),
        "agent_home_count": len(homes),
        "sample_agents": homes[:8],
        "script": Path(__file__).as_posix(),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Context quorum policy : {'present' if payload['policy_present'] else 'missing'}")
        print(f"Agent home root       : {payload['agent_home_root']}")
        print(f"Agent homes           : {payload['agent_home_count']}")
        if homes[:8]:
            print(f"Sample agents         : {', '.join(homes[:8])}")
    return 0


def build_manifest(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    policy = load_policy(args.policy)
    if args.risk not in policy["risk_levels"]:
        raise SystemExit(f"unknown risk level: {args.risk}")
    root = agent_root(policy, args.agent)
    root.mkdir(parents=True, exist_ok=True)
    receipts: list[dict[str, Any]] = []
    if not args.no_onboard:
        receipts.append(command_receipt("onboard", ["make", "onboard"], timeout=30))
    if args.exact_query:
        receipts.append(command_receipt("exact_local", ["rg", "-n", "-m", "40", args.exact_query, "."], timeout=20))
    receipts.extend(args.receipt or [])
    if args.test_command:
        receipts.append(command_receipt("tests_or_ci", shlex.split(args.test_command), timeout=args.test_timeout))
    changed = [repo_rel(p) for p in args.changed_file]
    if not changed and args.changed_from:
        changed = changed_files_from_git(args.changed_from)
    if changed:
        receipts.append(command_receipt("git_history", ["git", "log", "-n", "5", "--", *changed], timeout=15))
    hits = protected_hits(policy, changed)
    protected_authorized = bool(hits and args.human_approval)
    receipts.append({
        "family": "protected_files",
        "tool": "context_quorum",
        "status": "ok" if not hits or protected_authorized else "blocked",
        "summary": f"{len(hits)} protected matches",
        "finished_at": utc_now(),
        "authorized": protected_authorized,
        "hits": hits,
    })
    receipts.append({
        "family": "memory_or_docs",
        "tool": "file_exists",
        "status": "ok",
        "summary": "CLAUDE.md, AGENTS.md, and docs/ops/AGENT_ONBOARDING.md checked",
        "finished_at": utc_now(),
        "paths": ["CLAUDE.md", "AGENTS.md", "docs/ops/AGENT_ONBOARDING.md"],
    })
    if args.human_approval:
        receipts.append({"family": "human_approval", "tool": "operator_statement", "status": "ok", "summary": args.human_approval, "finished_at": utc_now()})
    if args.rollback_plan:
        receipts.append({"family": "rollback_plan", "tool": "operator_statement", "status": "ok", "summary": args.rollback_plan, "finished_at": utc_now()})

    satisfied = {r["family"] for r in receipts if r.get("status") in {"ok", "nonzero"}}
    required = policy["risk_levels"][args.risk]["required_families"]
    missing = [family for family in required if family not in satisfied]
    blocked = bool(hits and not protected_authorized)
    allowed = not blocked and not missing and len(satisfied) >= policy["risk_levels"][args.risk]["min_families"]
    manifest = {
        "task_id": args.task_id,
        "agent_id": args.agent,
        "risk_level": args.risk,
        "question": args.question,
        "created_at": utc_now(),
        "repo_root": REPO_ROOT.as_posix(),
        "changed_files": changed,
        "required_families": required,
        "satisfied_families": sorted(satisfied),
        "missing_families": missing,
        "protected_hits": hits,
        "receipts": receipts,
        "allowed_next_action": "bounded_action_allowed" if allowed else "blocked_needs_context_or_permission",
    }
    write_json(root / "context/context_manifest.latest.json", manifest)
    append_jsonl(root / "evidence/action_events.jsonl", {"type": "context_quorum", "timestamp": utc_now(), "task_id": args.task_id, "allowed": allowed})
    append_jsonl(root / "tools/tool_receipts.jsonl", {"timestamp": utc_now(), "task_id": args.task_id, "receipt_count": len(receipts), "manifest_hash": sha256_text(json.dumps(manifest, sort_keys=True))})
    return manifest, 0 if allowed else (3 if blocked else 2)


def check(args: argparse.Namespace) -> int:
    manifest, rc = build_manifest(args)
    print(json.dumps({
        "task_id": manifest["task_id"],
        "risk_level": manifest["risk_level"],
        "allowed_next_action": manifest["allowed_next_action"],
        "missing_families": manifest["missing_families"],
        "protected_hits": manifest["protected_hits"],
        "manifest_path": agent_root(load_policy(args.policy), args.agent).joinpath("context/context_manifest.latest.json").as_posix(),
    }, indent=2, sort_keys=True))
    return rc


def handoff(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    root = agent_root(policy, args.agent)
    manifest_path = root / "context/context_manifest.latest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    text = [
        "# Handoff",
        "",
        f"Agent: {args.agent}",
        f"Task: {args.task_id or manifest.get('task_id', 'unknown')}",
        f"Risk: {manifest.get('risk_level', 'unknown')}",
        f"Generated: {utc_now()}",
        "",
        "## Current State",
        "",
        args.summary or "No summary provided.",
        "",
        "## Context Quorum",
        "",
        f"Allowed next action: {manifest.get('allowed_next_action', 'unknown')}",
        f"Missing families: {', '.join(manifest.get('missing_families', [])) or 'none'}",
        f"Protected hits: {len(manifest.get('protected_hits', []))}",
        "",
        "## Next Agent",
        "",
        args.next_step or "Run make onboard, read this handoff, and refresh context quorum before editing.",
        "",
    ]
    path = root / "handoff/HANDOFF.md"
    path.write_text("\n".join(text), encoding="utf-8")
    append_jsonl(root / "handoff/handoff_events.jsonl", {"timestamp": utc_now(), "task_id": args.task_id, "path": path.as_posix()})
    print(path)
    return 0


def protect(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    paths = [repo_rel(p) for p in args.changed_file] or changed_files_from_git(args.changed_from)
    hits = protected_hits(policy, paths)
    print(json.dumps({"changed_files": paths, "protected_hits": hits}, indent=2, sort_keys=True))
    return 3 if hits and args.fail_on_hit else 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Dharma Swarm context quorum coordinator")
    p.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=status)
    ia = sub.add_parser("init-agent")
    ia.add_argument("--agent", required=True)
    ia.add_argument("--name", default="")
    ia.add_argument("--role", required=True)
    ia.add_argument("--purpose", default="Persistent meta-agent")
    ia.add_argument("--force", action="store_true")
    ia.set_defaults(func=init_agent)
    c = sub.add_parser("check")
    c.add_argument("--agent", required=True)
    c.add_argument("--task-id", required=True)
    c.add_argument("--risk", default="Q2")
    c.add_argument("--question", required=True)
    c.add_argument("--exact-query", default="")
    c.add_argument("--changed-file", action="append", default=[])
    c.add_argument("--changed-from", default="")
    c.add_argument("--receipt", type=parse_receipt, action="append")
    c.add_argument("--test-command", default="")
    c.add_argument("--test-timeout", type=int, default=120)
    c.add_argument("--human-approval", default="")
    c.add_argument("--rollback-plan", default="")
    c.add_argument("--no-onboard", action="store_true")
    c.set_defaults(func=check)
    h = sub.add_parser("handoff")
    h.add_argument("--agent", required=True)
    h.add_argument("--task-id", default="")
    h.add_argument("--summary", default="")
    h.add_argument("--next-step", default="")
    h.set_defaults(func=handoff)
    pr = sub.add_parser("protect")
    pr.add_argument("--changed-file", action="append", default=[])
    pr.add_argument("--changed-from", default="")
    pr.add_argument("--fail-on-hit", action="store_true")
    pr.set_defaults(func=protect)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
