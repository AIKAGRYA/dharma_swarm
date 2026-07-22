#!/usr/bin/env python3
"""Render a read-only Fourfold Shakti warrant for a proposed action."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from dharma_swarm.shakti_warrant import (
    FourfoldActionWarrantRequest,
    WarrantEvidence,
    WarrantVerdict,
    evaluate_fourfold_warrant,
    render_warrant_report,
)


def _parse_metadata(items: list[str]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"metadata must be key=value, got {item!r}")
        key, raw_value = item.split("=", 1)
        lowered = raw_value.lower()
        if lowered == "true":
            value: Any = True
        elif lowered == "false":
            value = False
        else:
            try:
                value = int(raw_value)
            except ValueError:
                try:
                    value = float(raw_value)
                except ValueError:
                    value = raw_value
        metadata[key] = value
    return metadata


def _env_impact_checked() -> bool:
    return os.environ.get("DHARMA_UPLIFT_ACK", "").strip().lower() == "impact-checked"


def _run_git(repo_root: Path, args: list[str]) -> str:
    # WP-0C1 (TIT-005): closed stdin (git must never wait on an inherited
    # pipe) and a finite wall clock converted into a named failure.
    timeout_seconds = 120.0
    raw_timeout = os.environ.get("DHARMA_GIT_TIMEOUT", "").strip()
    if raw_timeout:
        try:
            parsed = float(raw_timeout)
            if parsed > 0:
                timeout_seconds = parsed
        except ValueError:
            pass
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(
            f"GIT_TIMEOUT: git {' '.join(args)} exceeded {timeout_seconds:g}s "
            "wall clock (named nonzero failure)"
        ) from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "git command failed"
        raise SystemExit(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout


def _parse_name_status(output: str) -> list[str]:
    paths: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        paths.append(parts[-1])
    return sorted(set(paths))


def _parse_path_lines(output: str) -> list[str]:
    return sorted(set(line.strip() for line in output.splitlines() if line.strip()))


def _git_diff_args(scope: str, base_ref: str) -> list[str]:
    if scope == "staged":
        return ["diff", "--cached"]
    if scope == "unstaged":
        return ["diff"]
    if scope == "head":
        return ["diff", "HEAD"]
    if scope == "base":
        return ["diff", f"{base_ref}...HEAD"]
    raise SystemExit(f"unknown diff scope: {scope}")


def _path_counts(paths: list[str]) -> dict[str, int]:
    return {
        "source": sum(
            path.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".sh"))
            for path in paths
        ),
        "tests": sum(
            path.startswith("tests/") or "/test_" in path or path.endswith("_test.py")
            for path in paths
        ),
        "docs": sum(
            path.startswith("docs/") or path.endswith((".md", ".rst", ".txt"))
            for path in paths
        ),
    }


def _git_evidence(
    *,
    repo_root: Path,
    scope: str,
    base_ref: str,
    include_untracked: bool,
    max_diff_chars: int,
) -> tuple[WarrantEvidence | None, dict[str, Any], list[str], str]:
    if scope == "none":
        return None, {}, [], ""

    diff_args = _git_diff_args(scope, base_ref)
    name_status = _run_git(repo_root, [*diff_args, "--name-status"])
    stat = _run_git(repo_root, [*diff_args, "--stat"])
    diff_text = _run_git(repo_root, [*diff_args, "--", "."])
    paths = _parse_name_status(name_status)
    untracked: list[str] = []
    if include_untracked:
        untracked = _parse_path_lines(
            _run_git(repo_root, ["ls-files", "--others", "--exclude-standard"])
        )
        paths = sorted(set([*paths, *untracked]))

    counts = _path_counts(paths)
    metadata = {
        "diff_bound": True,
        "diff_scope": scope,
        "changed_files_count": len(paths),
        "source_files_count": counts["source"],
        "test_files_count": counts["tests"],
        "doc_files_count": counts["docs"],
        "untracked_files_count": len(untracked),
    }
    summary = (
        f"git diff scope={scope}: {len(paths)} changed path(s), "
        f"source={counts['source']}, tests={counts['tests']}, docs={counts['docs']}, "
        f"untracked={len(untracked)}"
    )
    if stat.strip():
        summary += "; " + " ".join(stat.strip().splitlines()[:3])
    if len(diff_text) > max_diff_chars:
        diff_text = diff_text[:max_diff_chars] + "\n[diff truncated]"

    evidence = WarrantEvidence(
        source="git",
        kind="git_diff",
        summary=summary,
        paths=paths,
        confidence=1.0,
        metadata=metadata,
    )
    return evidence, metadata, paths, diff_text


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate a proposed action against the four Shakti questions.",
    )
    parser.add_argument("--intent", required=True, help="Short statement of intended action.")
    parser.add_argument(
        "--content",
        default="",
        help="Additional action detail. Reads stdin if omitted and stdin is piped.",
    )
    parser.add_argument("--actor-id", default="operator", help="Actor requesting the action.")
    parser.add_argument("--actor-type", default="agent", help="Actor type.")
    parser.add_argument("--runtime-type", default="local", help="Runtime type.")
    parser.add_argument("--action-type", default="proposed_action", help="Action type label.")
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Target file/path. Repeatable.",
    )
    parser.add_argument(
        "--tool",
        action="append",
        default=[],
        help="Requested tool/command. Repeatable.",
    )
    parser.add_argument(
        "--metadata",
        action="append",
        default=[],
        help="Metadata key=value. Repeatable.",
    )
    parser.add_argument(
        "--provenance",
        action="append",
        default=[],
        help="Provenance reference. Repeatable.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root for git diff binding.")
    parser.add_argument(
        "--diff-scope",
        choices=["none", "unstaged", "staged", "head", "base"],
        default="none",
        help="Bind the warrant to git changes.",
    )
    parser.add_argument("--base-ref", default="origin/main", help="Base ref for --diff-scope base.")
    parser.add_argument(
        "--include-untracked",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include untracked files in git evidence.",
    )
    parser.add_argument(
        "--max-diff-chars",
        type=int,
        default=8000,
        help="Maximum diff text chars to include in warrant content.",
    )
    parser.add_argument(
        "--pass-on-empty-diff",
        action="store_true",
        help="Exit 0 without a warrant when the selected diff scope has no changed paths.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text report.")
    parser.add_argument(
        "--json-output",
        help="Write JSON warrant payload to this path in addition to stdout output.",
    )
    parser.add_argument(
        "--report-output",
        help="Write text warrant report to this path in addition to stdout output.",
    )
    parser.add_argument(
        "--fail-on",
        choices=[item.value for item in WarrantVerdict],
        action="append",
        default=[],
        help="Exit non-zero when verdict matches. Repeatable.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    content = args.content
    if not content and not sys.stdin.isatty():
        content = sys.stdin.read()
    metadata = _parse_metadata(args.metadata)
    if _env_impact_checked():
        metadata.setdefault("impact_checked", True)
    evidence_items = []
    target_paths = list(args.target)
    if args.diff_scope != "none":
        evidence, diff_metadata, diff_paths, diff_text = _git_evidence(
            repo_root=Path(args.repo_root),
            scope=args.diff_scope,
            base_ref=args.base_ref,
            include_untracked=args.include_untracked,
            max_diff_chars=args.max_diff_chars,
        )
        metadata = {**diff_metadata, **metadata}
        if evidence is not None:
            evidence_items.append(evidence)
        target_paths = sorted(set([*target_paths, *diff_paths]))
        if args.pass_on_empty_diff and not target_paths:
            print(f"No changed paths for diff scope {args.diff_scope}; warrant not required.")
            return 0
        content = "\n\n".join(part for part in [content, diff_text] if part)

    request = FourfoldActionWarrantRequest(
        actor_id=args.actor_id,
        actor_type=args.actor_type,
        runtime_type=args.runtime_type,
        action_type=args.action_type,
        intent=args.intent,
        content=content,
        target_paths=target_paths,
        requested_tools=args.tool,
        metadata=metadata,
        evidence=evidence_items,
        provenance=args.provenance,
    )
    warrant = evaluate_fourfold_warrant(request)
    json_output = json.dumps(warrant.model_dump(mode="json"), indent=2, sort_keys=True)
    report_output = render_warrant_report(warrant)

    if args.json_output:
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json_output + "\n", encoding="utf-8")
    if args.report_output:
        report_path = Path(args.report_output)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_output + "\n", encoding="utf-8")

    if args.json:
        print(json_output)
    else:
        print(report_output)

    return 1 if warrant.verdict.value in set(args.fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(main())
