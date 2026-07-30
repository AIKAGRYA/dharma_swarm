#!/usr/bin/env python3
"""Operator runner for the Sarathi 14-cycle unattended-proof window (PR-S4).

This is the RUNTIME WRAPPER the Gate-9 thin-source invariant points at:
cycle counts, state paths, and receipts live here — never in
``dharma_swarm/holon_system/sarathi/*``. One command on the runtime host:

    python3 scripts/runtime/sarathi_proof_window.py            # 14 cycles
    python3 scripts/runtime/sarathi_proof_window.py --json     # machine report

Kill-path receipt contract: the proof can only PASS when
``<state-root>/sarathi/kill_path_receipt.json`` exists and carries
``{"verified": true, "verified_at": "...", "method": "..."}``. The operator
creates that file only after ACTUALLY confirming loop-emergency-stop from
the phone; this runner never creates it. Absent or invalid, the verdict
fails closed (``kill_path_verified=False``) — by the operator's own spec.

The window is propose-only by spec: the dial is hard-pinned to ``propose``
here regardless of ``DGC_SARATHI_AUTONOMY``; nothing is dispatched during
the proof. Cycle records persist via ``holon_persistence``; briefs and the
verdict report land under ``<state-root>/sarathi/``. Exit 0 only on PASS.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

# A kill-path receipt's verified_at must look like a real timestamp, not any
# nonempty string (Codex P2). Require at least YYYY-MM-DDThh:mm.
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.holon_runtime import holon_wake_cycle  # noqa: E402
from dharma_swarm.holon_system.sarathi.delegate import invoke_receipt_path  # noqa: E402
from dharma_swarm.holon_system.sarathi.plan import BootPack  # noqa: E402
from dharma_swarm.holon_system.sarathi.proof import (  # noqa: E402
    REQUIRED_UNATTENDED_CYCLES,
    ProofCycleRecord,
    evaluate_unattended_proof,
    sakshi_audit_brief,
)
from dharma_swarm.holon_system.sarathi.roster import DEFAULT_ROSTER, load_roster  # noqa: E402
from dharma_swarm.holon_system.sarathi.wake import make_wake_work_fn  # noqa: E402
from dharma_swarm.operator_core.autonomy_dial import AutonomyLevel  # noqa: E402
from dharma_swarm.roaming_mailbox import RoamingMailbox  # noqa: E402

AUDIT_PATH = REPO_ROOT / "reports/loop_closure/cybernetics_codex/latest_audit.json"

# Default proof-window backlog: review-only items grounded in the runtime
# audit — safe at any dial, meaningful at propose.
DEFAULT_BACKLOG: tuple[dict, ...] = (
    {
        "kind": "review",
        "summary": "review blocked loops in latest_audit.json",
        "body": "walk the blocked loops in the cybernetics codex audit and report the unblock evidence needed",
    },
    {
        "kind": "review",
        "summary": "review arena truth report freshness",
        "body": "check reports/governance/arena for staleness against the orchestration track",
    },
)


def read_kill_path_receipt(state_root: Path) -> dict | None:
    """The operator-created receipt, or None. Never created here.

    Fully validated (Codex P2): a truncated/partial file must not authorize a
    pass. Requires ``verified is True``, a ``verified_at`` that matches a real
    timestamp shape, and a nonempty ``method`` describing HOW the mobile
    emergency stop was confirmed.
    """
    path = state_root / "sarathi" / "kill_path_receipt.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("verified") is not True:
        return None
    if not _TIMESTAMP_RE.match(str(payload.get("verified_at") or "")):
        return None
    if not str(payload.get("method") or "").strip():
        return None
    return payload


def load_backlog(path: str | None) -> tuple[dict, ...]:
    if not path:
        return DEFAULT_BACKLOG
    items = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise SystemExit("backlog file must contain a JSON list of open items")
    return tuple(items)


async def run_window(
    *,
    cycles: int,
    state_root: Path,
    backlog: tuple[dict, ...],
    cap_usd: float,
) -> dict:
    sarathi_root = state_root / "sarathi"
    briefs_dir = sarathi_root / "briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)
    mailbox = RoamingMailbox(queue_root=sarathi_root / "mailbox")
    audit = (
        json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        if AUDIT_PATH.exists()
        else None
    )
    roster = load_roster() or DEFAULT_ROSTER

    current: dict = {"cycle": 0, "outcomes": []}

    def load_boot_pack() -> BootPack:
        ready = frozenset(task.summary for task in mailbox.ready_tasks())
        return BootPack(
            roster=roster, open_items=backlog, ready_summaries=ready, audit=audit
        )

    def brief_sink(text: str) -> str:
        path = briefs_dir / f"brief_cycle_{current['cycle']:02d}.md"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def closeback(outcomes, ref) -> None:
        current["outcomes"] = [outcome.to_dict() for outcome in outcomes]

    def receipt_exists(ref: str) -> bool:
        # A dispatched row is backed by either a mailbox task file or a
        # durable invoke-receipt file (both resolvable after the process exits).
        try:
            if mailbox.task_path(ref).exists():
                return True
        except ValueError:
            pass
        return invoke_receipt_path(mailbox, ref).exists()

    records: list[ProofCycleRecord] = []
    for cycle in range(cycles):
        current["cycle"], current["outcomes"] = cycle, []
        work = make_wake_work_fn(
            load_boot_pack=load_boot_pack,
            mailbox=mailbox,
            level=AutonomyLevel.PROPOSE,  # the window is propose-only by spec
            brief_sink=brief_sink,
            closeback=closeback,
            context_id=f"sarathi-proof-window:{cycle}",
        )
        result = await holon_wake_cycle(
            "sarathi",
            work,
            spent_usd=0.0,
            cap_usd=cap_usd,
            agents_root=state_root / "agents",
            persist=True,
        )
        findings = sakshi_audit_brief(current["outcomes"], receipt_exists=receipt_exists)
        records.append(
            ProofCycleRecord(
                cycle_index=cycle,
                status=str(result.get("status")),
                dial_level="propose",
                audit_findings=tuple(findings),
            )
        )

    receipt = read_kill_path_receipt(state_root)
    # The verdict is ALWAYS judged against the full 14-cycle requirement —
    # the invocation must not be able to lower its own threshold. --cycles
    # only controls how many cycles THIS run executes: fewer than 14 is a
    # smoke run that can never pass (Greptile P1 on PR #1167, verified by
    # execution: --cycles 1 + receipt previously produced a passing verdict).
    verdict = evaluate_unattended_proof(
        records,
        kill_path_verified=receipt is not None,
        required_cycles=REQUIRED_UNATTENDED_CYCLES,
    )
    report = {
        "schema_version": "dharma.sarathi.proof_window_report.v1",
        "cycles_run": len(records),
        "statuses": [record.status for record in records],
        "audit_findings_total": sum(len(r.audit_findings) for r in records),
        "consecutive_clean": verdict.consecutive_clean,
        "required": verdict.required,
        "kill_path_receipt": receipt,
        "kill_path_verified": verdict.kill_path_verified,
        "passed": verdict.passed,
        "failures": list(verdict.failures),
        "briefs_dir": str(briefs_dir),
        "next_on_pass": (
            "Bind the wake organs into a standing loop (this runner, or an "
            "equivalent runtime wrapper calling make_wake_work_fn on a "
            "schedule), THEN set DGC_SARATHI_AUTONOMY=dispatch; full only after "
            "one clean week at dispatch (operator ruling 2026-07-30). The env "
            "var alone changes nothing until a loop invokes the organs — "
            "codex_composer_wake_loop.run_once still publishes read-only status."
        ),
    }
    (sarathi_root / "proof_window_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--cycles",
        type=int,
        default=REQUIRED_UNATTENDED_CYCLES,
        help="cycles to RUN this invocation; the verdict always requires the "
        "full 14-cycle window, so fewer than 14 is a smoke run that cannot pass",
    )
    parser.add_argument("--state-root", default="~/.dharma")
    parser.add_argument("--backlog", default="", help="JSON file of open items")
    parser.add_argument("--cap-usd", type=float, default=1.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    report = asyncio.run(
        run_window(
            cycles=max(1, args.cycles),
            state_root=Path(args.state_root).expanduser(),
            backlog=load_backlog(args.backlog or None),
            cap_usd=args.cap_usd,
        )
    )
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"proof window: {report['consecutive_clean']}/{report['required']} clean, "
            f"kill_path_verified={report['kill_path_verified']}, "
            f"passed={report['passed']}"
        )
        for failure in report["failures"]:
            print(f"  FAIL: {failure}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
