#!/usr/bin/env python3
"""Standing wake-loop runtime wrapper for the Sarathi apex (PR-S5).

This is the Gate-9 runtime wrapper the proof report points at: it binds the
merged wake organs (``make_wake_work_fn``) into a governed standing loop so
``DGC_SARATHI_AUTONOMY`` actually drives real work. Without a wrapper like
this the dial changes nothing — ``codex_composer_wake_loop.run_once`` still
publishes read-only status (Codex P1 on PR #1167).

The daemon is deliberately thin: it composes existing pieces and holds NO new
liveness constants beyond the loop cadence/cap it is told. It does NOT set
``wake_loop_active`` — that flag is earned only by the 14-cycle proof
(Gate-10), which is a separate runtime act.

Safety envelope (unchanged from the organs it composes):
- The dial is READ from the environment (default ``propose`` -> nothing
  dispatches; invalid -> ``shadow``). Advancing to ``dispatch``/``full`` is
  the operator's explicit act after the proof passes.
- ``holon_wake_cycle`` runs the kill-switch and budget checks BEFORE any work
  every cycle, so ``loop-emergency-stop`` halts the loop from the operator's
  phone at all times.
- ``delegate_all`` runs the reversibility gate before every delegation;
  ``git push`` / ``merge pr`` are NEVER_AUTO, so even at ``full`` Sarathi only
  enqueues mailbox tasks and requests automerge labels that Merge Master Mike
  re-gates under the now-live tier policy.

Usage (the operator's scheduler/launchd re-invokes for a standing loop):

    DGC_SARATHI_AUTONOMY=dispatch python3 scripts/runtime/sarathi_wake_daemon.py --cycles 1
    python3 scripts/runtime/sarathi_wake_daemon.py --json --cycles 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.holon_runtime import holon_wake_cycle  # noqa: E402
from dharma_swarm.holon_system.sarathi.plan import BootPack  # noqa: E402
from dharma_swarm.holon_system.sarathi.roster import DEFAULT_ROSTER, load_roster  # noqa: E402
from dharma_swarm.holon_system.sarathi.wake import make_wake_work_fn  # noqa: E402
from dharma_swarm.operator_core.autonomy_dial import current_autonomy_level  # noqa: E402
from dharma_swarm.roaming_mailbox import RoamingMailbox  # noqa: E402

AUDIT_PATH = REPO_ROOT / "reports/loop_closure/cybernetics_codex/latest_audit.json"

# Default standing-loop backlog: review-only items grounded in runtime truth.
# The operator replaces this with a real backlog file for production.
DEFAULT_BACKLOG: tuple[dict, ...] = (
    {
        "kind": "review",
        "summary": "review blocked loops in latest_audit.json",
        "body": "walk the blocked loops in the cybernetics codex audit and report the unblock evidence needed",
    },
)


def load_backlog(path: str | None) -> tuple[dict, ...]:
    if not path:
        return DEFAULT_BACKLOG
    items = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise SystemExit("backlog file must contain a JSON list of open items")
    return tuple(items)


async def run_daemon(
    *,
    cycles: int,
    state_root: Path,
    backlog: tuple[dict, ...],
    cap_usd: float,
    operator_reachable: bool,
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
    level = current_autonomy_level()  # READ the dial (unlike the proof runner)

    current: dict = {"cycle": 0}

    def load_boot_pack() -> BootPack:
        ready = frozenset(task.summary for task in mailbox.ready_tasks())
        return BootPack(
            roster=roster, open_items=backlog, ready_summaries=ready, audit=audit
        )

    def brief_sink(text: str) -> str:
        path = briefs_dir / f"brief_cycle_{current['cycle']:03d}.md"
        path.write_text(text, encoding="utf-8")
        return str(path)

    statuses: list[str] = []
    replies: list[str] = []
    for cycle in range(cycles):
        current["cycle"] = cycle
        work = make_wake_work_fn(
            load_boot_pack=load_boot_pack,
            mailbox=mailbox,
            level=level,  # the live dial drives dispatch
            operator_reachable=operator_reachable,
            brief_sink=brief_sink,
            context_id=f"sarathi-wake-daemon:{cycle}",
        )
        result = await holon_wake_cycle(
            "sarathi",
            work,
            spent_usd=0.0,
            cap_usd=cap_usd,
            agents_root=state_root / "agents",
            persist=True,
        )
        statuses.append(str(result.get("status")))
        if result.get("reply"):
            replies.append(str(result.get("reply")))
        # A kill/budget halt is terminal for this invocation — respect it.
        if result.get("status") != "ran":
            break

    report = {
        "schema_version": "dharma.sarathi.wake_daemon_report.v1",
        "autonomy_level": level.value,
        "wake_loop_active": False,  # never claimed here; Gate-10 earns it
        "cycles_run": len(statuses),
        "statuses": statuses,
        "last_reply": replies[-1] if replies else "",
        "briefs_dir": str(briefs_dir),
    }
    (sarathi_root / "wake_daemon_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--state-root", default="~/.dharma")
    parser.add_argument("--backlog", default="", help="JSON file of open items")
    parser.add_argument("--cap-usd", type=float, default=1.0)
    parser.add_argument(
        "--operator-reachable",
        action="store_true",
        help="assert the operator is reachable (softens the gate's OPERATOR_ONLY "
        "escalation to IRREVERSIBLE); default False keeps the strictest floor",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    report = asyncio.run(
        run_daemon(
            cycles=max(1, args.cycles),
            state_root=Path(args.state_root).expanduser(),
            backlog=load_backlog(args.backlog or None),
            cap_usd=args.cap_usd,
            operator_reachable=args.operator_reachable,
        )
    )
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"sarathi wake daemon: dial={report['autonomy_level']}, "
            f"cycles_run={report['cycles_run']}, "
            f"statuses={report['statuses']}"
        )
    # A kill/budget halt is not a daemon failure — it is the governed stop.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
