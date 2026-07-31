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
- Budget SCOPE (read this before trusting ``--cap-usd``): this cap bounds only
  THIS daemon process's OWN direct spend. The wake cycle is deterministic and
  runs ``invoker=None`` (it enqueues mailbox tasks; it makes no provider calls),
  so its direct cost is ~$0 and the cap is effectively slack today. It is NOT a
  limit on autonomous work: the provider-backed cost of dispatched tasks is
  incurred later by the executing sub-holons and is bounded by THEIR budgets
  (``economic_spine`` per-agent tokens), never charged to this ledger. Do not
  rely on ``--cap-usd`` to bound aggregate autonomous spend — that needs an
  authoritative downstream-cost source wired via ``run_holon_loop``'s
  ``spend_fn`` (deferred; Greptile P1 on #1170). The persisted-ledger mechanics
  below are correct for the daemon's own spend and ready for such a source.
- Budget mechanics: cumulative direct spend is carried across cycles AND across
  daemon restarts (a persisted ledger, seeded by ``--spent-usd``), never a
  hardcoded 0. Concurrent daemons sharing ``--state-root`` are serialized by an
  advisory ``flock`` around the whole read/check/work/write sequence: two
  overlapping invocations can never both authorize spend from one stale
  snapshot — the second halts ``budget-contended`` (Greptile P1 on #1170).
- Closeback linkage is folded into the per-run report (a JSON artifact already
  emitted, rewritten after every cycle), NOT a separate ``.jsonl`` store, so it
  neither raises the store-inventory census ratchet nor trips the memory-writer
  sentinel for a non-memory operational write.
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
import math
import os
import sys
from contextlib import contextmanager
from pathlib import Path

try:  # POSIX advisory locking; the daemon runs server-side (Linux/macOS).
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback (no cross-proc lock)
    fcntl = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.holon_runtime import holon_wake_cycle  # noqa: E402
from dharma_swarm.holon_system.sarathi.plan import (  # noqa: E402
    BootPack,
    stored_dedup_key,
)
from dharma_swarm.holon_system.sarathi.roster import DEFAULT_ROSTER, load_roster  # noqa: E402
from dharma_swarm.holon_system.sarathi.wake import make_wake_work_fn  # noqa: E402
from dharma_swarm.operator_core.autonomy_dial import current_autonomy_level  # noqa: E402
from dharma_swarm.roaming_mailbox import RoamingMailbox  # noqa: E402

AUDIT_PATH = REPO_ROOT / "reports/loop_closure/cybernetics_codex/latest_audit.json"
# Canonical kill/persistence home — the same root request_kill(name) writes to.
DEFAULT_AGENTS_ROOT = Path.home() / ".dharma" / "agents"
SENDER = "sarathi"
# A pre-dispatch governed halt (budget lock held by another daemon) OR a
# fail-closed halt on a corrupt persisted spend ledger: no wake cycle was
# invoked, so these must not count toward ``cycles_run``.
_CONTENDED_STATUS = "halted:budget-contended"
_INVALID_LEDGER_STATUS = "halted:budget-invalid"
_PRE_DISPATCH_HALTS = frozenset({_CONTENDED_STATUS, _INVALID_LEDGER_STATUS})
# A corrupt spend ledger is an operational fault the operator must clear, so it
# exits nonzero like error/unverified — never a silent, budget-bypassing "ran".
_ERROR_STATUSES = frozenset({"halted:error", "halted:unverified", _INVALID_LEDGER_STATUS})


class InvalidSpendLedgerError(ValueError):
    """The persisted spend ledger is non-finite, negative, or unparseable."""

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
    """Cumulative autonomous spend carried across restarts; seed if no ledger.

    Fails closed on a corrupt persisted ledger (Greptile P1 security on PR
    #1170): a non-finite (``nan``/``inf``), negative, or unparseable persisted
    ``spent_usd`` would flow straight into the budget guard, where every
    ``spent >= cap`` comparison against NaN is False — silently bypassing a
    finite cap. Unlike the CLI seed (validated in ``main``), persisted state is
    attacker/corruption-reachable, so a present-but-invalid ledger raises
    :class:`InvalidSpendLedgerError` rather than falling back to a value that permits
    dispatch. Only a MISSING or empty ledger falls back to the (validated) seed.
    """
    ledger = _spent_ledger(sarathi_root)
    if ledger.exists():
        raw = ledger.read_text(encoding="utf-8").strip()
        if raw:
            try:
                value = float(raw)
            except ValueError as exc:
                raise InvalidSpendLedgerError(
                    f"persisted spend ledger is not a number: {raw!r}"
                ) from exc
            if not math.isfinite(value) or value < 0:
                raise InvalidSpendLedgerError(
                    f"persisted spend ledger is non-finite or negative: {raw!r}"
                )
            return value
    return max(0.0, seed)


def _write_spend(sarathi_root: Path, value: float) -> None:
    _spent_ledger(sarathi_root).write_text(f"{value:.6f}", encoding="utf-8")


@contextmanager
def _spend_lock(sarathi_root: Path):
    """Cross-process budget lock (Greptile P1 security on PR #1170).

    Two daemons sharing ``--state-root`` must not both read one ``spent_usd``
    snapshot, both pass the cap guard, and both overwrite the ledger — that
    lost-update race lets concurrent runs spend past ``--cap-usd`` while the
    ledger retains only one update. An advisory ``flock`` serializes the WHOLE
    read/check/work/write sequence: the first daemon holds it for its entire
    run; a second daemon fails the non-blocking acquire and yields ``False`` so
    its caller halts (``budget-contended``) instead of authorizing spend from a
    stale snapshot. ``flock`` is released by the kernel if the holder dies, so a
    crash never strands the lock (unlike an ``O_EXCL`` lockfile).
    """
    if fcntl is None:  # pragma: no cover - non-POSIX: no cross-process lock
        yield True
        return
    sarathi_root.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(sarathi_root / "spend.lock"), os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError:
            acquired = False
        yield acquired
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


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

    def load_boot_pack() -> BootPack:
        # Dedup against EVERY task this sender has open OR completed, not just
        # currently-claimable ones: a claimed/responded task must still suppress
        # re-planning the SAME backlog item. Uses the FULL-identity dedup key
        # persisted on each task (recipient/channel/body/deps/metadata, not just
        # summary), so a revised backlog item — including a re-route to a
        # different recipient — re-plans instead of being dropped (Greptile P1
        # plan.py L127 + L209).
        seen = frozenset(
            key
            for task in mailbox.list_tasks()
            if task.sender == SENDER
            for key in (stored_dedup_key(task.metadata),)
            if key  # a keyless (pre-key) task does not dedup — see build_plan
        )
        return BootPack(
            roster=roster, open_items=backlog, ready_keys=seen, audit=audit
        )

    brief_counter = {"n": 0}

    def brief_sink(text: str) -> str:
        path = briefs_dir / f"brief_cycle_{brief_counter['n']:03d}.md"
        path.write_text(text, encoding="utf-8")
        brief_counter["n"] += 1
        return str(path)

    # Durable closeback linkage lives in the per-run report (rewritten after
    # every cycle), NOT a dedicated ``closeback_ledger.jsonl``: a separate store
    # raised the store-inventory census ratchet and tripped the memory-writer
    # sentinel (action-required, decision=deny) for a non-memory operational
    # append. Folding it into the report we already emit keeps the same
    # per-cycle durability with zero new store footprint.
    closeback_records: list[dict] = []

    def closeback(outcomes, brief_ref) -> None:
        closeback_records.append(
            {
                "run_id": run_id,
                "brief_ref": brief_ref,
                "outcomes": [outcome.to_dict() for outcome in outcomes],
            }
        )

    statuses: list[str] = []
    replies: list[str] = []
    # Provisional display value only; the AUTHORIZING read happens under the lock
    # below and is never taken from a corrupt ledger (fail-closed there).
    spent = 0.0

    def build_report() -> dict:
        had_error = any(status in _ERROR_STATUSES for status in statuses)
        cycles_run = sum(1 for status in statuses if status not in _PRE_DISPATCH_HALTS)
        return {
            "schema_version": "dharma.sarathi.wake_daemon_report.v1",
            "run_id": run_id,
            "autonomy_level": level.value,
            "wake_loop_active": False,  # never claimed here; Gate-10 earns it
            "cycles_run": cycles_run,
            "statuses": statuses,
            "spent_usd": round(spent, 6),
            "cap_usd": cap_usd,
            "had_error": had_error,
            "last_reply": replies[-1] if replies else "",
            "briefs_dir": str(briefs_dir),
            "agents_root": str(agents_root),
            "closeback": closeback_records,
            # Honest scope of the USD cap (Greptile P1 on PR #1170): this daemon
            # runs invoker=None and build_plan is deterministic, so its OWN wake
            # cycle makes no provider calls — its direct spend is ~$0 and the
            # persisted ledger advances only if a direct-cost lever is later
            # added. The cap therefore bounds the DAEMON's direct spend, NOT the
            # aggregate downstream cost of dispatched work, which is bounded by
            # the executing sub-holons' own budgets. An aggregate-spend cap would
            # need an authoritative spend source wired via run_holon_loop's
            # spend_fn (deferred; the economic spine tracks per-agent tokens,
            # not global USD).
            "budget_scope": "daemon-direct-spend",
            "budget_note": (
                "cap_usd bounds this daemon's OWN direct spend only (~$0; "
                "deterministic, invoker=None); it does NOT limit autonomous "
                "work — dispatched tasks' provider cost is bounded by the "
                "executing sub-holons' budgets, not this ledger"
            ),
        }

    def persist_report() -> dict:
        report = build_report()
        blob = json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
        (sarathi_root / f"wake_daemon_report_run_{run_id:04d}.json").write_text(
            blob, encoding="utf-8"
        )  # retained per run
        (sarathi_root / "wake_daemon_report.json").write_text(
            blob, encoding="utf-8"
        )  # latest-pointer convenience
        return report

    with _spend_lock(sarathi_root) as have_budget_lock:
        if not have_budget_lock:
            # Another Sarathi wake loop holds the budget lock. Do NOT read the
            # spend snapshot or dispatch — the safe answer to "cannot authorize
            # from a stale snapshot" is to not run this overlapping invocation.
            # A governed halt (exit 0), never an error.
            statuses.append(_CONTENDED_STATUS)
            return persist_report()

        # Cumulative spend read FRESH under the lock (never a stale snapshot),
        # carried across cycles AND restarts, never a hardcoded 0. A corrupt
        # persisted ledger (non-finite/negative/garbage) FAILS CLOSED here — it
        # must never authorize dispatch by defeating `spent >= cap` (Greptile P1
        # security). The operator clears the ledger; exit is nonzero.
        try:
            spent = read_cumulative_spend(sarathi_root, spent_seed)
        except InvalidSpendLedgerError as exc:
            statuses.append(_INVALID_LEDGER_STATUS)
            replies.append(f"halted: {exc}")
            return persist_report()
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
            # Carry per-cycle cost forward (0 until the runtime wires a real
            # cost source; the mechanism — persisted, non-zero-carrying,
            # serialized under the lock — is the point).
            spent += float(result.get("cost_usd") or 0.0)
            _write_spend(sarathi_root, spent)
            persist_report()  # per-cycle durability (report rewritten each cycle)
            if result.get("status") != "ran":
                break

    return persist_report()


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
    parser.add_argument(
        "--cap-usd",
        type=float,
        default=1.0,
        help="cap on this daemon's OWN direct spend only (deterministic, "
        "invoker=None wake cycle -> ~$0 today). This is NOT a limit on "
        "autonomous work: dispatched tasks' provider cost is bounded by the "
        "executing sub-holons' budgets, not this ledger. Do not rely on it to "
        "bound aggregate autonomous spend (Greptile P1 on #1170).",
    )
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

    # Reject a non-finite or negative budget before it reaches the guard. A NaN
    # cap slips through argparse's ``float`` and defeats the budget floor
    # entirely — every ``spent >= cap`` comparison against NaN is False, so the
    # cap never halts and the loop dispatches paid work unbounded (Greptile P1,
    # T-Rex verified). Fail closed on the operator's most safety-critical dial.
    for flag, value in (("--cap-usd", args.cap_usd), ("--spent-usd", args.spent_usd)):
        if not math.isfinite(value) or value < 0:
            parser.error(f"{flag} must be a finite, non-negative number (got {value!r})")

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
