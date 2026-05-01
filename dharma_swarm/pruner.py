"""Pruner — sweep the zen garden.

Cuts noise across every subsystem:
- Stigmergy marks below salience threshold → archive
- Telos objectives that are duplicates or subsumed → merge into parent
- Bridge edges below confidence threshold → prune
- Trace entries older than N days → archive
- Concept nodes with zero connections → flag for removal
- Small granular items that matter → plug into larger parent node

Not deletion. Compression. The signal stays, the noise goes.
Like raking a zen garden — what remains is cleaner, more powerful.

Usage::

    pruner = Pruner()
    report = await pruner.sweep()
    pruner.print_report(report)

Integration:
    dgc prune              -- CLI command
    sleep_cycle.py         -- optional PRUNE phase after GC
    cron                   -- daily 03:00 sweep
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PruneReport:
    """What the pruner did."""
    timestamp: str = ""
    duration_seconds: float = 0.0

    stigmergy_archived: int = 0
    stigmergy_kept: int = 0

    bridges_pruned: int = 0
    bridges_kept: int = 0

    telos_merged: int = 0
    telos_kept: int = 0

    concepts_flagged: int = 0
    concepts_kept: int = 0

    traces_archived: int = 0

    noise_removed: int = 0  # total items pruned/archived/merged
    signal_remaining: int = 0  # total items kept

    actions_taken: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Pruner:
    """Sweep the zen garden. Signal stays, noise goes."""

    def __init__(
        self,
        state_dir: Path | None = None,
        stigmergy_threshold: float = 0.3,
        bridge_threshold: float = 0.2,
        trace_max_days: int = 14,
        dry_run: bool = False,
    ) -> None:
        self._state_dir = state_dir or Path.home() / ".dharma"
        self._stig_threshold = stigmergy_threshold
        self._bridge_threshold = bridge_threshold
        self._trace_max_days = trace_max_days
        self._dry_run = dry_run

    async def sweep(self) -> PruneReport:
        """Run all pruning passes. Returns what was cut."""
        report = PruneReport(timestamp=datetime.now(timezone.utc).isoformat())
        started = time.monotonic()

        await self._prune_stigmergy(report)
        await self._prune_bridges(report)
        await self._prune_telos(report)
        await self._prune_concepts(report)
        await self._prune_traces(report)

        report.noise_removed = (
            report.stigmergy_archived + report.bridges_pruned +
            report.telos_merged + report.traces_archived
        )
        report.signal_remaining = (
            report.stigmergy_kept + report.bridges_kept +
            report.telos_kept + report.concepts_kept
        )
        report.duration_seconds = round(time.monotonic() - started, 3)
        return report

    # ── Stigmergy: archive low-salience marks ───────────────────

    async def _prune_stigmergy(self, report: PruneReport) -> None:
        """Move marks below salience threshold to archive."""
        marks_file = self._state_dir / "stigmergy" / "marks.jsonl"
        archive_file = self._state_dir / "stigmergy" / "archive.jsonl"

        if not marks_file.exists():
            return

        try:
            lines = marks_file.read_text(encoding="utf-8").splitlines()
            keep = []
            archive = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    mark = json.loads(line)
                    salience = mark.get("salience", 0.5)
                    if salience < self._stig_threshold:
                        archive.append(line)
                        report.stigmergy_archived += 1
                    else:
                        keep.append(line)
                        report.stigmergy_kept += 1
                except json.JSONDecodeError:
                    archive.append(line)  # corrupt → archive
                    report.stigmergy_archived += 1

            if not self._dry_run and archive:
                # Append archived marks
                with open(archive_file, "a", encoding="utf-8") as f:
                    for line in archive:
                        f.write(line + "\n")
                # Rewrite marks file with only kept marks
                marks_file.write_text("\n".join(keep) + "\n" if keep else "", encoding="utf-8")
                report.actions_taken.append(
                    f"Stigmergy: archived {len(archive)} low-salience marks, kept {len(keep)}"
                )
            elif archive:
                report.actions_taken.append(
                    f"Stigmergy: WOULD archive {len(archive)} marks (dry run)"
                )

        except Exception as exc:
            report.errors.append(f"stigmergy: {exc}")

    # ── Bridges: prune low-confidence edges ─────────────────────

    async def _prune_bridges(self, report: PruneReport) -> None:
        """Remove bridge edges below confidence threshold."""
        import sqlite3

        db_path = self._state_dir / "db" / "bridges.db"
        if not db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            # Count before
            total = conn.execute("SELECT COUNT(*) FROM bridge_edges").fetchone()[0]
            low = conn.execute(
                "SELECT COUNT(*) FROM bridge_edges WHERE confidence < ?",
                (self._bridge_threshold,),
            ).fetchone()[0]

            if not self._dry_run and low > 0:
                conn.execute(
                    "DELETE FROM bridge_edges WHERE confidence < ?",
                    (self._bridge_threshold,),
                )
                conn.commit()
                report.actions_taken.append(
                    f"Bridges: pruned {low} edges below {self._bridge_threshold} confidence"
                )
            elif low > 0:
                report.actions_taken.append(
                    f"Bridges: WOULD prune {low} edges (dry run)"
                )

            report.bridges_pruned = low
            report.bridges_kept = total - low
            conn.close()

        except Exception as exc:
            report.errors.append(f"bridges: {exc}")

    # ── Telos: merge duplicate/subsumed objectives ──────────────

    async def _prune_telos(self, report: PruneReport) -> None:
        """Find duplicate or near-duplicate telos objectives and flag for merge."""
        try:
            from dharma_swarm.telos_graph import TelosGraph

            tg = TelosGraph(telos_dir=self._state_dir / "telos")
            await tg.load()
            objectives = tg.list_objectives()
            report.telos_kept = len(objectives)

            if len(objectives) < 2:
                return

            # Find duplicates by name similarity (normalized)
            seen: dict[str, list[str]] = {}
            for obj in objectives:
                # Normalize: lowercase, strip whitespace, remove common prefixes
                key = obj.name.lower().strip()
                for prefix in ("objective: ", "obj-", "goal: "):
                    if key.startswith(prefix):
                        key = key[len(prefix):]
                # Further normalize
                key = " ".join(key.split())  # collapse whitespace

                if key in seen:
                    seen[key].append(obj.id)
                    report.telos_merged += 1
                    report.actions_taken.append(
                        f"Telos: duplicate '{obj.name}' (same as {seen[key][0][:12]})"
                    )
                else:
                    seen[key] = [obj.id]

            # Find objectives that are clearly subsets of others
            names = [(obj.id, obj.name.lower()) for obj in objectives]
            for i, (id_a, name_a) in enumerate(names):
                for id_b, name_b in names[i+1:]:
                    if len(name_a) > 10 and len(name_b) > 10:
                        if name_a in name_b or name_b in name_a:
                            shorter = name_a if len(name_a) < len(name_b) else name_b
                            report.telos_merged += 1
                            report.actions_taken.append(
                                f"Telos: '{shorter[:40]}' subsumed by larger objective"
                            )

            report.telos_kept -= report.telos_merged

        except Exception as exc:
            report.errors.append(f"telos: {exc}")

    # ── Concepts: flag zero-connection nodes ────────────────────

    async def _prune_concepts(self, report: PruneReport) -> None:
        """Flag concept nodes with no edges and no bridges."""
        try:
            cg_path = self._state_dir / "semantic" / "concept_graph.json"
            if not cg_path.exists():
                return

            data = json.loads(cg_path.read_text(encoding="utf-8"))
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])
            if not isinstance(nodes, list) or not isinstance(edges, list):
                return

            report.concepts_kept = len(nodes)
            if len(nodes) > 5_000 or len(edges) > 20_000:
                report.actions_taken.append(
                    "Concepts: skipped isolated-node scan for large graph "
                    f"({len(nodes)} nodes, {len(edges)} edges)"
                )
                return

            degree_by_id: dict[str, int] = {}
            for raw_edge in edges:
                if not isinstance(raw_edge, dict):
                    continue
                source_id = str(raw_edge.get("source_id", "") or "")
                target_id = str(raw_edge.get("target_id", "") or "")
                if source_id:
                    degree_by_id[source_id] = degree_by_id.get(source_id, 0) + 1
                if target_id:
                    degree_by_id[target_id] = degree_by_id.get(target_id, 0) + 1

            for raw_node in nodes:
                if not isinstance(raw_node, dict):
                    continue
                node_id = str(raw_node.get("id", "") or "")
                try:
                    salience = float(raw_node.get("salience", 0.5) or 0.0)
                except (TypeError, ValueError):
                    salience = 0.5
                if degree_by_id.get(node_id, 0) == 0 and salience < 0.5:
                    report.concepts_flagged += 1

            if report.concepts_flagged > 0:
                report.actions_taken.append(
                    f"Concepts: {report.concepts_flagged} isolated low-salience nodes "
                    f"(zero edges, salience < 0.5) — candidates for removal"
                )
            report.concepts_kept -= report.concepts_flagged

        except Exception as exc:
            report.errors.append(f"concepts: {exc}")

    # ── Traces: archive old entries ─────────────────────────────

    async def _prune_traces(self, report: PruneReport) -> None:
        """Move trace entries older than N days to archive."""
        trace_dir = self._state_dir / "traces" / "history"
        archive_dir = self._state_dir / "traces" / "archive"

        if not trace_dir.exists():
            return

        archive_dir.mkdir(parents=True, exist_ok=True)
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._trace_max_days)

        try:
            for trace_file in trace_dir.iterdir():
                if not trace_file.is_file():
                    continue
                # Check modification time
                mtime = datetime.fromtimestamp(trace_file.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    if not self._dry_run:
                        dest = archive_dir / trace_file.name
                        trace_file.rename(dest)
                    report.traces_archived += 1

            if report.traces_archived > 0:
                report.actions_taken.append(
                    f"Traces: {'archived' if not self._dry_run else 'WOULD archive'} "
                    f"{report.traces_archived} entries older than {self._trace_max_days} days"
                )

        except Exception as exc:
            report.errors.append(f"traces: {exc}")

    # ── Display ─────────────────────────────────────────────────

    def print_report(self, report: PruneReport) -> None:
        """Print the zen garden report."""
        mode = " (DRY RUN)" if self._dry_run else ""
        print("\n╔══════════════════════════════════════════════════════════════╗")
        print(f"║  PRUNER — Sweep the Zen Garden{mode:<29}║")
        print("╚══════════════════════════════════════════════════════════════╝")

        print(f"\n  {'Subsystem':<20} {'Kept':>8} {'Pruned':>8} {'Action'}")
        print(f"  {'─'*20} {'─'*8} {'─'*8} {'─'*30}")
        print(f"  {'Stigmergy':<20} {report.stigmergy_kept:>8} {report.stigmergy_archived:>8} archive low-salience")
        print(f"  {'Bridges':<20} {report.bridges_kept:>8} {report.bridges_pruned:>8} drop low-confidence")
        print(f"  {'Telos':<20} {report.telos_kept:>8} {report.telos_merged:>8} merge duplicates")
        print(f"  {'Concepts':<20} {report.concepts_kept:>8} {report.concepts_flagged:>8} flag isolated")
        print(f"  {'Traces':<20} {'─':>8} {report.traces_archived:>8} archive old")

        print(f"\n  SIGNAL: {report.signal_remaining} | NOISE REMOVED: {report.noise_removed}")

        if report.actions_taken:
            print(f"\n  ACTIONS ({len(report.actions_taken)})")
            for action in report.actions_taken[:15]:
                print(f"    {action}")
            if len(report.actions_taken) > 15:
                print(f"    ... and {len(report.actions_taken) - 15} more")

        if report.errors:
            print(f"\n  ERRORS ({len(report.errors)})")
            for err in report.errors:
                print(f"    ! {err}")

        print(f"\n  Duration: {report.duration_seconds:.2f}s")
