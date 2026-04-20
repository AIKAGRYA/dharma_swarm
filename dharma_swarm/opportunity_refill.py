"""Layer A: refill the frontier_tasks_pending JSONL from the opportunity board.

Companion to ``opportunity_dispatcher.py`` (Layer B). Layer A reads the
strategic to-do list at ``~/.dharma/meta/opportunity_board.json``, asks the
``CurriculumEngine`` to bootstrap the top-K unaddressed opportunities into
6 frontier-task rows each, and APPENDS those rows to
``~/.dharma/meta/frontier_tasks_pending.jsonl`` for the dispatcher to pick up.

Single-source-of-truth for ``addressed_ids``: the filesystem scan of
``~/.dharma/campaigns/``. No separate index file. If a manifest folder
exists, the opportunity is addressed; refill skips it.

Append-only JSONL discipline: never compacts, never deletes. The dispatcher
treats the JSONL as a stream and is responsible for its own idempotency
(via the manifest scan). PR3 algedonic invariant catches starvation
(pending non-empty + no progress).

Cron handler registration lives in ``cron_runner.py``:
- ``frontier_dispatcher`` — runs the dispatcher tick (interval 30 min)
- ``frontier_refill``     — runs this refill (anchored daily 04:30)

Both honor the dispatcher's kill-switch flag at
``~/.dharma/meta/dispatcher_paused.flag`` (refusal is fail-paranoid:
unreadable flag = paused).

OPEN MYSTERY (Layer C): the populator of ``opportunity_board.json`` in main
is unknown. ``scripts/seed_codex_opportunities.py`` and
``scripts/upgrade_opportunity_board.py`` are operator-invoked. Layer C will
identify the autonomous populator (or build one).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Match the dispatcher's path constants — keep these in sync.
DHARMA_HOME = Path.home() / ".dharma"
META_DIR = DHARMA_HOME / "meta"
BOARD_PATH = META_DIR / "opportunity_board.json"
PENDING_PATH = META_DIR / "frontier_tasks_pending.jsonl"
PAUSED_FLAG = META_DIR / "dispatcher_paused.flag"

# Rebound the dispatcher's CAMPAIGN_ROOT via _campaign_manifest at call time
# so monkeypatching in tests propagates.
from dharma_swarm._campaign_manifest import list_campaign_ids  # noqa: E402


@dataclass
class RefillResult:
    paused: bool = False
    dry_run: bool = False
    board_count: int = 0
    addressed_count: int = 0
    candidates_after_filter: int = 0
    appended_rows: int = 0
    appended_opportunity_ids: list[str] = field(default_factory=list)
    skipped_already_addressed: list[str] = field(default_factory=list)
    error: str | None = None


def _is_paused() -> bool:
    """Mirror the dispatcher's fail-paranoid paused check."""
    try:
        if PAUSED_FLAG.exists():
            return True
        if PAUSED_FLAG.is_dir():
            return True
        return False
    except Exception:
        return True


def _read_board() -> list[dict[str, Any]]:
    """Read the opportunity board JSON. Tolerates absence (returns [])."""
    if not BOARD_PATH.exists():
        return []
    try:
        raw = json.loads(BOARD_PATH.read_text(encoding="utf-8") or "[]")
    except json.JSONDecodeError:
        logger.exception("opportunity_board.json is malformed; treating as empty")
        return []
    if not isinstance(raw, list):
        logger.warning("opportunity_board.json is not a list; treating as empty")
        return []
    out: list[dict[str, Any]] = []
    for entry in raw:
        if isinstance(entry, dict):
            out.append(entry)
    return out


def _append_rows(rows: list[dict[str, Any]]) -> None:
    """Append the given rows to the pending JSONL. NEVER compacts."""
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PENDING_PATH.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _frontier_task_to_row(task: Any) -> dict[str, Any]:
    """Convert a CurriculumEngine FrontierTask (Pydantic) to a JSONL row.

    The shape matches what the dispatcher's ``_read_pending_rows`` expects
    (provenance.opportunity_id, metadata.stage, etc.).
    """
    if hasattr(task, "model_dump"):
        return task.model_dump(mode="json")
    if isinstance(task, dict):
        return task
    raise TypeError(f"Cannot serialize frontier task of type {type(task)!r}")


def refill_frontier_tasks_pending(
    *,
    top_k: int = 3,
    min_telos_alignment: float = 0.5,
    dry_run: bool = False,
) -> RefillResult:
    """Bootstrap the top unaddressed opportunities into pending frontier tasks.

    Args:
        top_k: how many unaddressed opportunities to bootstrap this run.
        min_telos_alignment: filter out opportunities whose telos_alignment
            falls below this threshold. Default 0.5 — keep meaningful
            telos-alignment but allow exploratory wedges.
        dry_run: if True, compute everything and return the result without
            appending to the JSONL.

    Returns:
        RefillResult describing what was found and what was written.
    """
    result = RefillResult(dry_run=dry_run)
    if _is_paused():
        result.paused = True
        return result

    board = _read_board()
    result.board_count = len(board)

    addressed = list_campaign_ids()
    result.addressed_count = len(addressed)

    # Filter board by addressed_ids first so the operator can see what was
    # skipped purely because it's already in flight.
    addressable: list[dict[str, Any]] = []
    for opp in board:
        opp_id = str(opp.get("opportunity_id") or "")
        if not opp_id:
            continue
        if opp_id in addressed:
            result.skipped_already_addressed.append(opp_id)
            continue
        addressable.append(opp)
    result.candidates_after_filter = len(addressable)

    if not addressable:
        return result

    try:
        from dharma_swarm.curriculum_engine import CurriculumEngine
    except Exception as exc:  # noqa: BLE001
        logger.exception("CurriculumEngine import failed")
        result.error = f"import_error: {exc}"
        return result

    try:
        tasks = CurriculumEngine().derive_from_opportunity_board(
            addressable,
            top_k=top_k,
            min_telos_alignment=min_telos_alignment,
            addressed_ids=set(),  # already filtered above
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("derive_from_opportunity_board raised")
        result.error = f"derive_error: {exc}"
        return result

    rows = [_frontier_task_to_row(t) for t in tasks]
    if dry_run:
        result.appended_rows = len(rows)
        result.appended_opportunity_ids = sorted({
            (r.get("provenance") or {}).get("opportunity_id") or ""
            for r in rows
        } - {""})
        return result

    try:
        _append_rows(rows)
    except Exception as exc:  # noqa: BLE001
        logger.exception("append to frontier_tasks_pending.jsonl failed")
        result.error = f"append_error: {exc}"
        return result

    result.appended_rows = len(rows)
    result.appended_opportunity_ids = sorted({
        (r.get("provenance") or {}).get("opportunity_id") or ""
        for r in rows
    } - {""})
    return result


def _build_arg_parser():
    import argparse
    p = argparse.ArgumentParser(
        prog="opportunity_refill",
        description="Bootstrap top unaddressed opportunities into pending frontier tasks.",
    )
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--min-telos", type=float, default=0.5)
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    import sys
    args = _build_arg_parser().parse_args(argv)
    res = refill_frontier_tasks_pending(
        top_k=args.top_k,
        min_telos_alignment=args.min_telos,
        dry_run=args.dry_run,
    )
    summary = {
        "paused": res.paused,
        "dry_run": res.dry_run,
        "board_count": res.board_count,
        "addressed_count": res.addressed_count,
        "candidates_after_filter": res.candidates_after_filter,
        "appended_rows": res.appended_rows,
        "appended_opportunity_ids": res.appended_opportunity_ids,
        "skipped_already_addressed": res.skipped_already_addressed,
        "error": res.error,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if res.error is None else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
