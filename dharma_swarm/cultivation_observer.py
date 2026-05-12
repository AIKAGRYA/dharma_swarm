"""Cultivation Observer — passive, falsifiable test of the cultivation premise.

This module exists to answer one question honestly:

    Does autonomous cultivation actually happen, or is "cultivation" a
    mythology we wrap around tasks we did ourselves?

The lodestones (GNANI, GPLOT) seed concept nodes, telos objectives, task
stubs, and stigmergy marks. The cultivation hypothesis is that, once
seeded, the swarm's autonomous agents will pick up these seeds and grow
them — proposing new objectives, adding new tasks tagged with the seed's
channel, refining concept nodes — without further human prompting.

If that's true, we should see measurable growth in counts and content
over a passive observation window. If we don't, the cultivation premise
is falsified for the current substrate state. Either result is valuable.

How it works
------------
A daily (or N-minute-interval) snapshot of three substrates is written
to disk:

    ~/.dharma/observatory/cultivation_snapshots/snapshot-<ISO>.json

Each snapshot records counts and content hashes. The observer then
diffs the latest snapshot against the previous one and emits a
single ``ExternalOutcomeRecord`` of kind ``cultivation_signal_v1``
with the net delta as ``value`` (new entities created since the last
snapshot, weighted by significance).

Crucial design constraints (binding):
    * Read-only. Snapshots are JSON files; the only substrate write is
      one ``ExternalOutcomeRecord`` per run via the existing telemetry
      plane. No new database, no new control plane.
    * Route state through ``daemon_config.dharma_state_dir()`` so the
      semgrep ``no-home-dharma`` rule is satisfied.
    * NaN-safe / "indeterminate"-safe: the first run has nothing to diff
      and reports value=0 with status="initial", not a fabricated signal.
    * Tagged falsifiability: each emitted record stores the seed channels
      it tracked, so downstream readers can verify the hypothesis with
      the original seed set in hand.

This is the v1 of GPLOT_CAIRN §7 prediction "autonomous cultivation
will produce ≥3 new gplot-tagged tasks within 7 days, OR the cultivation
hypothesis is falsified for the current substrate state."

See: GPLOT_LODESTONE.md, docs/GPLOT_CAIRN.md §7.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.telemetry_plane import (
    ExternalOutcomeRecord,
    TelemetryPlaneStore,
)

__all__ = [
    "OUTCOME_KIND_CULTIVATION_SIGNAL_V1",
    "CultivationSnapshot",
    "CultivationDelta",
    "take_snapshot",
    "diff_snapshots",
    "run_cultivation_observer",
    "DEFAULT_SEED_CHANNELS",
]

logger = logging.getLogger(__name__)

OUTCOME_KIND_CULTIVATION_SIGNAL_V1 = "cultivation_signal_v1"
"""Stable contract: the outcome kind written by this module."""

METHOD_VERSION = "passive_snapshot_diff_v1"

DEFAULT_SEED_CHANNELS: tuple[str, ...] = ("gnani", "gplot")
"""Stigmergy channels seeded by the lodestone boot path. The cultivation
hypothesis is evaluated PER channel — gnani autonomy and gplot autonomy
are independent claims.
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CultivationSnapshot:
    """One point-in-time snapshot of cultivable substrate state.

    Each substrate is summarized as (count, signature). The signature is
    a stable hash of the *content* — IDs, titles, statuses — so that
    edits to existing entities also surface in the diff (not just adds).
    """

    captured_at: datetime
    task_count: int
    task_signature: str
    task_count_by_tag: dict[str, int]
    telos_objective_count: int
    telos_signature: str
    telos_count_by_domain: dict[str, int]
    stigmergy_mark_count: int
    stigmergy_signature: str
    stigmergy_count_by_channel: dict[str, int]
    seed_channels: tuple[str, ...] = field(default_factory=tuple)
    method_version: str = METHOD_VERSION


@dataclass(frozen=True)
class CultivationDelta:
    """Per-channel growth signal from snapshot N → N+1.

    ``signal`` is a weighted scalar: it answers "did the substrate grow"
    on this channel? Positive ⇒ cultivation. Zero ⇒ stasis. Negative ⇒
    contraction. Magnitude is the count of new entities tagged with the
    channel, weighted by entity type (telos objectives count 3x, task
    seeds 2x, stigmergy marks 1x — strategic > tactical > signal).
    """

    channel: str
    new_tasks: int
    new_telos_objectives: int
    new_stigmergy_marks: int
    task_content_changed: bool
    telos_content_changed: bool
    stigmergy_content_changed: bool
    signal: float
    window_seconds: float


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


def _hash_obj(items: list[dict[str, Any]]) -> str:
    """Stable content hash: deterministic for the same logical state.

    Sorted by key 'id' if present so insertion order doesn't matter.
    """
    sortable = sorted(
        items, key=lambda d: d.get("id") or d.get("title") or str(d)
    )
    payload = json.dumps(sortable, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _count_by_key(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        # Accept str (single tag/domain), list (multiple tags), or missing.
        val = it.get(key)
        if val is None:
            continue
        if isinstance(val, str):
            out[val] = out.get(val, 0) + 1
        elif isinstance(val, (list, tuple)):
            for v in val:
                if isinstance(v, str):
                    out[v] = out.get(v, 0) + 1
    return out


async def take_snapshot(
    *,
    state_dir: Path | None = None,
    seed_channels: Sequence[str] = DEFAULT_SEED_CHANNELS,
) -> CultivationSnapshot:
    """Capture one snapshot. Read-only.

    Failures on any substrate degrade gracefully — that substrate
    contributes zeros, others still register. This matches the existing
    guardian/cultivation philosophy that one broken graph doesn't break
    observation.
    """
    sd = Path(state_dir) if state_dir is not None else dharma_state_dir()

    # --- TaskBoard ----------------------------------------------------
    tasks_dump: list[dict[str, Any]] = []
    try:
        from dharma_swarm.task_board import TaskBoard

        tb = TaskBoard(db_path=sd / "task_board.db")
        await tb.init_db()
        tasks = await tb.list_tasks(limit=500)
        for t in tasks:
            tasks_dump.append(
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status.value,
                    "tags": (t.metadata or {}).get("tags", []),
                }
            )
    except Exception as exc:
        logger.warning("cultivation_observer: TaskBoard snapshot failed: %s", exc)

    # --- TelosGraph ---------------------------------------------------
    telos_dump: list[dict[str, Any]] = []
    try:
        from dharma_swarm.telos_graph import TelosGraph

        tg = TelosGraph(telos_dir=sd / "telos")
        try:
            await tg.load()
        except Exception:
            pass
        for obj in tg.list_objectives():
            telos_dump.append(
                {
                    "id": obj.id,
                    "name": obj.name,
                    "status": obj.status.value,
                    "domain": (obj.metadata or {}).get("domain", ""),
                }
            )
    except Exception as exc:
        logger.warning("cultivation_observer: TelosGraph snapshot failed: %s", exc)

    # --- StigmergyStore ----------------------------------------------
    stig_dump: list[dict[str, Any]] = []
    try:
        from dharma_swarm.stigmergy import StigmergyStore

        ss = StigmergyStore(db_path=sd / "stigmergy.db")
        await ss.init_db()
        # Most stigmergy stores expose list_marks or all_marks; fall back to a
        # per-channel query if needed.
        channel_counts: dict[str, list[Any]] = {}
        for ch in seed_channels:
            try:
                marks = await ss.list_marks(channel=ch, limit=500)
            except Exception:
                marks = []
            channel_counts[ch] = list(marks)
            for m in marks:
                stig_dump.append(
                    {
                        "id": getattr(m, "id", "") or getattr(m, "mark_id", ""),
                        "channel": ch,
                        "kind": getattr(m, "kind", ""),
                        "summary": getattr(m, "summary", "")[:60],
                    }
                )
    except Exception as exc:
        logger.warning(
            "cultivation_observer: StigmergyStore snapshot failed: %s", exc
        )

    return CultivationSnapshot(
        captured_at=datetime.now(timezone.utc),
        task_count=len(tasks_dump),
        task_signature=_hash_obj(tasks_dump),
        task_count_by_tag=_count_by_key(tasks_dump, "tags"),
        telos_objective_count=len(telos_dump),
        telos_signature=_hash_obj(telos_dump),
        telos_count_by_domain=_count_by_key(telos_dump, "domain"),
        stigmergy_mark_count=len(stig_dump),
        stigmergy_signature=_hash_obj(stig_dump),
        stigmergy_count_by_channel=_count_by_key(stig_dump, "channel"),
        seed_channels=tuple(seed_channels),
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def snapshots_dir(state_dir: Path | None = None) -> Path:
    sd = Path(state_dir) if state_dir is not None else dharma_state_dir()
    out = sd / "observatory" / "cultivation_snapshots"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _snapshot_to_json(snap: CultivationSnapshot) -> dict[str, Any]:
    d = asdict(snap)
    d["captured_at"] = snap.captured_at.isoformat()
    d["seed_channels"] = list(snap.seed_channels)
    return d


def _snapshot_from_json(d: dict[str, Any]) -> CultivationSnapshot:
    return CultivationSnapshot(
        captured_at=datetime.fromisoformat(d["captured_at"]),
        task_count=int(d["task_count"]),
        task_signature=d["task_signature"],
        task_count_by_tag=dict(d.get("task_count_by_tag", {})),
        telos_objective_count=int(d["telos_objective_count"]),
        telos_signature=d["telos_signature"],
        telos_count_by_domain=dict(d.get("telos_count_by_domain", {})),
        stigmergy_mark_count=int(d["stigmergy_mark_count"]),
        stigmergy_signature=d["stigmergy_signature"],
        stigmergy_count_by_channel=dict(d.get("stigmergy_count_by_channel", {})),
        seed_channels=tuple(d.get("seed_channels", ())),
        method_version=d.get("method_version", METHOD_VERSION),
    )


def write_snapshot(
    snap: CultivationSnapshot, *, state_dir: Path | None = None
) -> Path:
    out = snapshots_dir(state_dir)
    ts = snap.captured_at.strftime("%Y%m%dT%H%M%SZ")
    path = out / f"snapshot-{ts}.json"
    path.write_text(json.dumps(_snapshot_to_json(snap), indent=2))
    return path


def latest_two_snapshots(
    state_dir: Path | None = None,
) -> tuple[CultivationSnapshot | None, CultivationSnapshot | None]:
    out = snapshots_dir(state_dir)
    files = sorted(out.glob("snapshot-*.json"))
    if not files:
        return None, None
    if len(files) == 1:
        return None, _snapshot_from_json(json.loads(files[-1].read_text()))
    prev = _snapshot_from_json(json.loads(files[-2].read_text()))
    curr = _snapshot_from_json(json.loads(files[-1].read_text()))
    return prev, curr


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def diff_snapshots(
    prev: CultivationSnapshot,
    curr: CultivationSnapshot,
    *,
    channel: str,
) -> CultivationDelta:
    """Compute per-channel delta between two snapshots.

    "Channel" maps to:
        - stigmergy marks: directly via ``stigmergy_count_by_channel``
        - tasks: via the tag matching the channel
        - telos objectives: via the metadata domain matching the channel
    """
    new_tasks = max(
        0,
        curr.task_count_by_tag.get(channel, 0)
        - prev.task_count_by_tag.get(channel, 0),
    )
    new_telos = max(
        0,
        curr.telos_count_by_domain.get(channel, 0)
        - prev.telos_count_by_domain.get(channel, 0),
    )
    new_stig = max(
        0,
        curr.stigmergy_count_by_channel.get(channel, 0)
        - prev.stigmergy_count_by_channel.get(channel, 0),
    )

    # Content-change flags (signature-level): an edit to an existing
    # entity is still cultivation evidence even if counts don't move.
    task_changed = prev.task_signature != curr.task_signature
    telos_changed = prev.telos_signature != curr.telos_signature
    stig_changed = prev.stigmergy_signature != curr.stigmergy_signature

    # Weighted signal: strategic > tactical > signal.
    signal = 3.0 * new_telos + 2.0 * new_tasks + 1.0 * new_stig

    window = max(
        0.0, (curr.captured_at - prev.captured_at).total_seconds()
    )

    return CultivationDelta(
        channel=channel,
        new_tasks=new_tasks,
        new_telos_objectives=new_telos,
        new_stigmergy_marks=new_stig,
        task_content_changed=task_changed,
        telos_content_changed=telos_changed,
        stigmergy_content_changed=stig_changed,
        signal=float(signal),
        window_seconds=float(window),
    )


# ---------------------------------------------------------------------------
# Substrate-writing layer
# ---------------------------------------------------------------------------


def _delta_to_record(
    delta: CultivationDelta,
    *,
    run_id: str,
    method_version: str = METHOD_VERSION,
) -> ExternalOutcomeRecord:
    return ExternalOutcomeRecord(
        outcome_id=str(uuid.uuid4()),
        outcome_kind=OUTCOME_KIND_CULTIVATION_SIGNAL_V1,
        value=float(delta.signal),
        unit="weighted_new_entities",
        confidence=0.9 if delta.window_seconds > 0 else 0.0,
        status="observed",
        subject_id=delta.channel,
        summary=(
            f"channel={delta.channel} "
            f"new_telos={delta.new_telos_objectives} "
            f"new_tasks={delta.new_tasks} "
            f"new_stig={delta.new_stigmergy_marks} "
            f"signal={delta.signal:.1f} "
            f"window_h={delta.window_seconds / 3600:.1f}"
        ),
        session_id="cultivation_observer",
        task_id="",
        run_id=run_id,
        metadata={
            "method_version": method_version,
            "channel": delta.channel,
            "new_tasks": delta.new_tasks,
            "new_telos_objectives": delta.new_telos_objectives,
            "new_stigmergy_marks": delta.new_stigmergy_marks,
            "task_content_changed": delta.task_content_changed,
            "telos_content_changed": delta.telos_content_changed,
            "stigmergy_content_changed": delta.stigmergy_content_changed,
            "window_seconds": delta.window_seconds,
            "falsifiability_target": "gplot_cairn_section_7",
        },
    )


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------


async def run_cultivation_observer(
    *,
    state_dir: Path | None = None,
    store: TelemetryPlaneStore | None = None,
    seed_channels: Sequence[str] = DEFAULT_SEED_CHANNELS,
    dry_run: bool = False,
) -> tuple[CultivationSnapshot, list[CultivationDelta], list[ExternalOutcomeRecord]]:
    """One cycle of the observer: take snapshot, diff against the prior,
    emit one ``ExternalOutcomeRecord`` per seed channel.

    First-run behavior: stores the snapshot, emits no records (nothing
    to diff yet). This is the honest "initial state" handling — we don't
    fabricate a baseline signal.
    """
    sd = Path(state_dir) if state_dir is not None else dharma_state_dir()
    store = store or TelemetryPlaneStore()

    snap = await take_snapshot(state_dir=sd, seed_channels=seed_channels)
    write_snapshot(snap, state_dir=sd)

    prev, _curr = latest_two_snapshots(state_dir=sd)
    if prev is None:
        logger.info(
            "cultivation_observer: first snapshot written; nothing to diff yet"
        )
        return snap, [], []

    deltas: list[CultivationDelta] = []
    for ch in seed_channels:
        deltas.append(diff_snapshots(prev, snap, channel=ch))

    run_id = str(uuid.uuid4())
    records = [_delta_to_record(d, run_id=run_id) for d in deltas]

    if dry_run:
        logger.info(
            "cultivation_observer: dry-run; %d deltas computed, no records written",
            len(deltas),
        )
        return snap, deltas, records

    for rec in records:
        await store.record_external_outcome(rec)
    logger.info(
        "cultivation_observer: wrote %d records across %s channels",
        len(records),
        list(seed_channels),
    )
    return snap, deltas, records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m dharma_swarm.cultivation_observer",
        description=(
            "Cultivation Observer — passive, falsifiable test of whether "
            "lodestone-seeded substrates actually accrete autonomously."
        ),
    )
    p.add_argument(
        "--channels", nargs="+", default=list(DEFAULT_SEED_CHANNELS),
        help="Seed channels to track (default: gnani gplot).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Compute delta but do not write back.",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose logging."
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    snap, deltas, records = asyncio.run(
        run_cultivation_observer(
            seed_channels=tuple(args.channels),
            dry_run=args.dry_run,
        )
    )
    print(
        f"cultivation_observer: snapshot captured "
        f"tasks={snap.task_count} telos={snap.telos_objective_count} "
        f"stigmergy={snap.stigmergy_mark_count}"
    )
    for d in deltas:
        print(
            f"  delta[{d.channel}]: signal={d.signal:.1f} "
            f"new_telos={d.new_telos_objectives} new_tasks={d.new_tasks} "
            f"new_stig={d.new_stigmergy_marks} "
            f"window_h={d.window_seconds / 3600:.1f}"
        )
    print(f"records_written={0 if args.dry_run else len(records)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
