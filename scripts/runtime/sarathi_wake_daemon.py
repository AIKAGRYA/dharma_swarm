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
(Gate-10), a separate runtime act.

Safety envelope (unchanged from the organs it composes):
- The dial is READ from the environment (default ``propose`` -> nothing
  dispatches; invalid -> ``shadow``). Advancing to ``dispatch``/``full`` is
  the operator's explicit act after the proof passes.
- The kill-switch is checked at the CANONICAL ``~/.dharma/agents`` home
  (``--agents-root``, default) that the operator's ``request_kill(name)``
  writes to, so ``loop-emergency-stop`` from the phone always halts the loop.
- Budget: cumulative spend is carried across cycles AND across daemon restarts
  (a persisted ledger, seeded by ``--spent-usd``), never a hardcoded 0, so the
  cap actually enforces.
- ``delegate_all`` runs the reversibility gate before every delegation;
  ``git push`` / ``merge pr`` are NEVER_AUTO, so even at ``full`` Sarathi only
  enqueues mailbox tasks and requests automerge labels that Merge Master Mike
  re-gates under the now-live tier policy.
- Evidence is retained per run: each invocation gets a monotonic run id and a
  ``briefs/run_<NNNN>/`` directory, so a scheduler re-invoking the daemon never
  overwrites a prior autonomous cycle's brief.

Usage (the operator's scheduler/launchd re-invokes for a standing loop):

    DGC_SARATHI_AUTONOMY=dispatch python3 scripts/runtime/sarathi_wake_daemon.py --cycles 1
    python3 scripts/runtime/sarathi_wake_daemon.py --json --cycles 3

Exit code: 0 for governed outcomes (ran / kill / budget); 1 if any cycle
halted with ``error`` or ``unverified`` (so a service manager alerts).
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
# Canonical kill/persistence home — the same root request_kill(name) writes to.
DEFAULT_AGENTS_ROOT = Path.home() / ".dharma" / "agents"
SENDER = "sarathi"
_ERROR_STATUSES = frozenset({"halted:error", "halted:unverified"})

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


def reserve_run(sarathi_root: Path) -> tuple[int, Path]:
    """Atomically reserve a fresh run id + its brief directory.

    Concurrency-safe (Greptile P1 on PR #1170): a bare read/increment/write
    counter let two daemons sharing ``--state-root`` pick the same id and
    overwrite each other's evidence. ``mkdir`` is atomic on POSIX, so we
    reserve the per-run directory itself — the loser of any race gets
    ``FileExistsError`` and retries with the next id. No lock, no counter.
    """
    briefs_root = sarathi_root / "briefs"
    briefs_root.mkdir(parents=True, exist_ok=True)
    existing = [
        int(path.name[4:])
        for path in briefs_root.glob("run_*")
        if path.name[4:].isdigit()
    ]
    candidate = (max(existing) + 1) if existing else 1
    while True:
        run_dir = briefs_root / f"run_{candidate:04d}"
        try:
            run_dir.mkdir()  # atomic reservation
        except FileExistsError:
            candidate += 1
            continue
        return candidate, run_dir


def _spent_ledger(sarathi_root: Path) -> Path:
    return sarathi_root / "spent_usd"


def read_cumulative_spend(sarathi_root: Path, seed: float) -> float:
    """Cumulative autonomous spend carried across restarts; seed if no ledger."""
    ledger = _spent_ledger(sarathi_root)
    if ledger.exists():
        try:
            return float(ledger.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            pass
    return max(0.0, seed)


def _write_spend(sarathi_root: Path, value: float) -> None:
    _spent_ledger(sarathi_root).write_text(f"{value:.6f}", encoding="utf-8")


async def run_daemon(
    *,
    cycles: int,
    state_root: Path,
    agents_root: Path,
    backlog: tuple[dict, ...],
    cap_usd: float,
    operator_reachable: bool,
    spent_seed: float,
) -> dict:
    sarathi_root = state_root / "sarathi"
    sarathi_root.mkdir(parents=True, exist_ok=True)
    run_id, briefs_dir = reserve_run(sarathi_root)
    mailbox = RoamingMailbox(queue_root=sarathi_root / "mailbox")
    audit = (
        json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        if AUDIT_PATH.exists()
        else None
    )
    roster = load_roster() or DEFAULT_ROSTER
    level = current_autonomy_level()

    # Cumulative spend carried across cycles AND restarts (never hardcoded 0).
    spent = read_cumulative_spend(sarathi_root, spent_seed)

    def load_boot_pack() -> BootPack:
        # Dedup against EVERY task this sender has open OR completed, not just
        # currently-claimable ones: a claimed/responded task's summary must
        # still suppress re-planning the same backlog item.
        seen = frozenset(
            task.summary for task in mailbox.list_tasks() if task.sender == SENDER
        )
        return BootPack(
            roster=roster, open_items=backlog, ready_summaries=seen, audit=audit
        )

    brief_counter = {"n": 0}

    def brief_sink(text: str) -> str:
        path = briefs_dir / f"brief_cycle_{brief_counter['n']:03d}.md"
        path.write_text(text, encoding="utf-8")
        brief_counter["n"] += 1
        return str(path)

    closeback_ledger = sarathi_root / "closeback_ledger.jsonl"

    def closeback(outcomes, brief_ref) -> None:
        # Durable lifecycle linkage: every cycle's outcomes + brief ref are
        # appended to a persistent ledger (not left in closeback=none mode).
        with closeback_ledger.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "run_id": run_id,
                        "brief_ref": brief_ref,
                        "outcomes": [outcome.to_dict() for outcome in outcomes],
                    },
                    default=str,
                )
                + "\n"
            )

    statuses: list[str] = []
    replies: list[str] = []
    for _ in range(cycles):
        work = make_wake_work_fn(
            load_boot_pack=load_boot_pack,
            mailbox=mailbox,
            level=level,
            operator_reachable=operator_reachable,
            brief_sink=brief_sink,
            closeback=closeback,
            context_id=f"sarathi-wake-daemon:run{run_id}",
        )
        result = await holon_wake_cycle(
            "sarathi",
            work,
            spent_usd=spent,
            cap_usd=cap_usd,
            agents_root=agents_root,  # canonical kill + persistence home
            persist=True,
        )
        statuses.append(str(result.get("status")))
        if result.get("reply"):
            replies.append(str(result.get("reply")))
        # Carry per-cycle cost forward (0 until the runtime wires a real cost
        # source; the mechanism — persisted, non-zero-carrying — is the point).
        spent += float(result.get("cost_usd") or 0.0)
        _write_spend(sarathi_root, spent)
        if result.get("status") != "ran":
            break

    had_error = any(status in _ERROR_STATUSES for status in statuses)
    report = {
        "schema_version": "dharma.sarathi.wake_daemon_report.v1",
        "run_id": run_id,
        "autonomy_level": level.value,
        "wake_loop_active": False,  # never claimed here; Gate-10 earns it
        "cycles_run": len(statuses),
        "statuses": statuses,
        "spent_usd": round(spent, 6),
        "cap_usd": cap_usd,
        "had_error": had_error,
        "last_reply": replies[-1] if replies else "",
        "briefs_dir": str(briefs_dir),
        "agents_root": str(agents_root),
    }
    blob = json.dumps(report, indent=2, sort_keys=True) + "\n"
    (sarathi_root / f"wake_daemon_report_run_{run_id:04d}.json").write_text(
        blob, encoding="utf-8"
    )  # retained per run
    (sarathi_root / "wake_daemon_report.json").write_text(
        blob, encoding="utf-8"
    )  # latest-pointer convenience
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--state-root", default="~/.dharma")
    parser.add_argument(
        "--agents-root",
        default="",
        help="kill/persistence home (default ~/.dharma/agents, the canonical "
        "root request_kill(name) writes to — keep it default so the phone kill "
        "always reaches this loop)",
    )
    parser.add_argument("--backlog", default="", help="JSON file of open items")
    parser.add_argument("--cap-usd", type=float, default=1.0)
    parser.add_argument(
        "--spent-usd",
        type=float,
        default=0.0,
        help="seed cumulative spend when no persisted ledger exists yet",
    )
    parser.add_argument(
        "--operator-reachable",
        action="store_true",
        help="assert the operator is reachable (softens the gate's OPERATOR_ONLY "
        "escalation to IRREVERSIBLE); default False keeps the strictest floor",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    agents_root = (
        Path(args.agents_root).expanduser() if args.agents_root else DEFAULT_AGENTS_ROOT
    )
    report = asyncio.run(
        run_daemon(
            cycles=max(1, args.cycles),
            state_root=Path(args.state_root).expanduser(),
            agents_root=agents_root,
            backlog=load_backlog(args.backlog or None),
            cap_usd=args.cap_usd,
            operator_reachable=args.operator_reachable,
            spent_seed=args.spent_usd,
        )
    )
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"sarathi wake daemon: run={report['run_id']}, "
            f"dial={report['autonomy_level']}, cycles_run={report['cycles_run']}, "
            f"spent=${report['spent_usd']:.4f}/{report['cap_usd']:.4f}, "
            f"statuses={report['statuses']}"
        )
    # Governed outcomes (ran / kill / budget) are healthy; only error/unverified
    # cycles produce a nonzero exit so a service manager applies its policy.
    return 1 if report["had_error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
