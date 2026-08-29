#!/usr/bin/env python3
"""Compose all uplift guards for the pre-commit hook.

Returns exit code 0 on pass, 1 on any guard failure. Each guard reports
its own message; pass/warn messages go to stdout, fail messages to stderr.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.uplift_guards import (
    check_autonomous_destruction,
    check_fourfold_shakti_warrant,
    check_hotpath_acknowledged,
    check_kernel_integrity,
    check_mismatch_adjacency,
    check_no_secrets,
)
from scripts.uplift_guards.check_no_model_literals import check_no_model_literals
from scripts.uplift_guards.check_spine_ownership import check_spine_ownership


def check_assurance_diff(repo_root: Path) -> tuple[bool, str]:
    if os.environ.get("DHARMA_SKIP_ASSURANCE_GUARD", "").strip() == "1":
        return True, "assurance diff guard skipped by DHARMA_SKIP_ASSURANCE_GUARD=1"

    try:
        from dharma_swarm.assurance.runner import run_assurance
        from dharma_swarm.assurance.scanner_test_gaps import _git_changed_files
    except ImportError as exc:
        # Fail-open but never silently green (fail_closed.py AI-N1 spirit):
        # loud message plus a durable witness flag under ~/.dharma/witness/.
        _write_assurance_unavailable_witness(repo_root, str(exc))
        return True, (
            "ASSURANCE SCAN UNAVAILABLE (dependency missing) — not a pass: "
            f"{exc}"
        )

    changed_files = _git_changed_files(repo_root)
    if not changed_files:
        return True, "no changed files to scan"

    report = run_assurance(
        repo_root=repo_root,
        changed_files=changed_files,
    )
    changed_set = set(changed_files)
    blocking: list[dict] = []
    medium = 0
    for scanner_report in report.get("reports", []):
        for finding in scanner_report.get("findings", []):
            if str(finding.get("file", "")) not in changed_set:
                continue
            severity = finding.get("severity")
            if severity in {"critical", "high"}:
                blocking.append(finding)
            elif severity == "medium":
                medium += 1

    critical = sum(1 for finding in blocking if finding.get("severity") == "critical")
    high = sum(1 for finding in blocking if finding.get("severity") == "high")
    if blocking:
        first = blocking[0]
        top = (
            f"{first.get('category')} at "
            f"{first.get('file')}:{first.get('line')}"
        )
        return (
            False,
            "ASSURANCE DIFF GUARD: "
            f"critical={critical} high={high} medium={medium}. "
            f"First blocking finding: {top}",
        )
    return True, f"assurance diff clear of blocking findings (medium={medium})"

def _write_assurance_unavailable_witness(repo_root: Path, detail: str) -> None:
    """Leave a durable flag that the assurance scan did not run.

    The commit is still allowed; the flag exists so the gap is auditable
    rather than invisible. Witness failures must never block a commit.
    """
    try:
        log = (
            Path.home()
            / ".dharma"
            / "witness"
            / "assurance_guard_unavailable.jsonl"
        )
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "ts": datetime.now(UTC).isoformat(),
                        "repo": str(repo_root),
                        "detail": detail,
                    }
                )
                + "\n"
            )
    except Exception:
        pass


GUARDS = [
    ("kernel-integrity", check_kernel_integrity),
    ("secrets-scan", check_no_secrets),
    ("autonomous-destruction", check_autonomous_destruction),
    ("hotpath-ack", check_hotpath_acknowledged),
    ("fourfold-shakti-warrant", check_fourfold_shakti_warrant),
    ("mismatch-adjacency", check_mismatch_adjacency),
    ("assurance-diff", check_assurance_diff),
    ("spine-ownership", check_spine_ownership),
    ("no-model-literals", check_no_model_literals),
]


def main() -> int:
    msg_file = os.environ.get("DHARMA_COMMIT_MSG_FILE")
    failed = 0
    for name, guard in GUARDS:
        try:
            ok, message = guard(REPO_ROOT, commit_msg_file=msg_file) if "commit_msg_file" in guard.__code__.co_varnames else guard(REPO_ROOT)
        except Exception as exc:
            # RED-TEAM HARDENING: crash = fail-closed. A crashing guard is a
            # bypass vector (adversary can craft malformed input to take the
            # guard down and sail through). Never trust a crashed guard.
            print(f"  [{name}] guard crashed: {exc}", file=sys.stderr)
            ok, message = False, f"guard crashed (fail-closed): {exc}"
        prefix = "✓" if ok else "✗"
        stream = sys.stdout if ok else sys.stderr
        print(f"  {prefix} [{name}] {message}", file=stream)
        if not ok:
            failed += 1

    if failed:
        print(
            f"\n{failed} uplift guard(s) failed. To bypass a single guard, see\n"
            "  the env vars / tags listed in each message above. To bypass\n"
            "  ALL guards (emergency only), use git commit --no-verify.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
