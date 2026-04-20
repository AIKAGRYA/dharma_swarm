"""Opportunity dispatcher (Layer B promoter, PR1 — scope stage only).

WHY THIS EXISTS

The opportunity board (``~/.dharma/meta/opportunity_board.json``) is a
strategic to-do list seeded from Codex top-40 welfare/revenue ideas plus
whatever populator runs in main. The curriculum engine knows how to convert
each opportunity into a 6-stage frontier-task chain (scope → validate →
deep_research → capability → mvp → first_artifact). The refill loop (PR6)
appends those rows to ``~/.dharma/meta/frontier_tasks_pending.jsonl``.

What was missing — the *promoter* — was the wire that takes an unaddressed
pending row and (a) creates a campaign manifest and (b) creates a row on the
canonical task_board so the orchestrator + agent_runner can execute it via
the existing Telic Seam (which already records ActionProposal + GateDecision
+ Outcome + ValueEvent + Contribution; we MUST NOT duplicate that here).

THIS MODULE IS A PROMOTER, NOT AN EXECUTOR

It has zero ``execute_*`` calls. It writes manifest state and task_board rows.
The orchestrator + agent_runner pick the row up via the canonical lane.

PR1 SCOPE (intentionally tiny — kaizen)

- Stage ``scope`` only. ``validate`` lands in PR2; ``deep_research`` in PR4.
- Kill-switch flag check (fail-paranoid: any error reading the flag = paused).
- fcntl.flock on dispatcher.lock to prevent concurrent runs.
- Plain-JSON campaign manifest (NOT ArtifactManifestStore — wrong primitive
  for state files; that's a sidecar manifest writer for actual artifacts).
- Telos gate via ``check_action`` with v3 REVIEW→ALLOW+WARN policy.
  REVIEW silently treated as ALLOW with a structured WARN log entry +
  ``manifest.review_logged=True`` so an operator can audit later. A FIXME
  ticket is open to wire REVIEW into a real operator approval queue.
- Budget gate via ``agent_registry.is_budget_exceeded()`` (the kill-switch
  predicate at agent_registry.py:887). This is a SEPARATE gate from throttle:
  budget = real spend; throttle = manifest scan (kicks in for deep_research
  in PR4). Both gates must clear.
- Full frontier_row stored in task.metadata so PR4 can rehydrate the
  FrontierTask for ``frontier_task_to_research_brief``.
- ``health.json`` write-through every run, even on failure path (try/except
  wraps everything). PR3's algedonic invariant reads this.
- ``--dry-run`` flag for safe verification.

OUT OF PR1

- ``validate``, ``deep_research``, ``capability``, ``mvp`` stages (PR2/PR4/PR5)
- Artifact completion observer (PR2)
- Algedonic stalled-frontier invariant (PR3)
- ``first_artifact`` stage (PR7 — separate result contract)
- Cron handler registration (PR6)
- Layer A refill (PR6)
- Dashboard surface (PR8)

NEW CONVENTION

This is the first module to use ``~/.dharma/campaigns/{opp_id}/`` as a
directory convention. Each opportunity gets a folder with manifest.json plus
per-stage artifacts. The PR2 observer will write ``scope.md`` etc. to this
folder.

ANCHOR POINTS (cite when reviewing)

- ``task_board.create`` (async): ``task_board.py:214``
- ``check_action(action, content)``: ``telos_gates.py:783``
- ``is_budget_exceeded()``: ``agent_registry.py:887``
- ``leave_stigmergic_mark`` (async): ``stigmergy.py:410``
- ``GateDecision`` enum: ``models.py:93``
- Telic Seam (DO NOT duplicate from this module):
  - ``orchestrator.py:1722, 1760`` (ActionProposal + GateDecision)
  - ``agent_runner.py:2680, 2810`` (Outcome + ValueEvent + Contribution)

OPEN MYSTERY (Layer C)

The populator of ``~/.dharma/meta/opportunity_board.json`` in main is unknown.
The board exists, but no module in main is the obvious writer. We know
``scripts/seed_codex_opportunities.py`` and
``scripts/upgrade_opportunity_board.py`` are operator-invoked seeders. The
autonomous populator is TBD; this is Layer C's job to identify, not Layer B's.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import errno
import fcntl
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm._campaign_manifest import (
    CAMPAIGN_ROOT,
    init_manifest,
    list_campaign_ids,
    manifest_path,
    read_manifest,
    update_stage,
    write_manifest,
)

logger = logging.getLogger(__name__)

DHARMA_HOME = Path.home() / ".dharma"
META_DIR = DHARMA_HOME / "meta"
PENDING_PATH = META_DIR / "frontier_tasks_pending.jsonl"
PAUSED_FLAG = META_DIR / "dispatcher_paused.flag"
LOCK_PATH = META_DIR / "dispatcher.lock"
HEALTH_PATH = META_DIR / "opportunity_dispatcher.health.json"
WITNESS_DIR = DHARMA_HOME / "witness"
# Canonical task_board location matches swarm.py:608 (state_dir/db/tasks.db).
TASK_BOARD_DB = DHARMA_HOME / "db" / "tasks.db"

# Stages this PR is allowed to promote. Extended in PR2/PR4/PR5.
PROMOTABLE_STAGES_PR1: tuple[str, ...] = ("scope",)

# Filenames per stage for the artifact_target metadata field. PR2's observer
# writes to these paths.
STAGE_FILENAME: dict[str, str] = {
    "scope": "scope.md",
    "validate": "validate.md",
    "deep_research": "deep_research.json",
    "capability": "capability.md",
    "mvp": "mvp.md",
    # ``first_artifact`` deliberately absent — PR7 needs a directory contract.
}


# --------------------------------------------------------------------------
# Kill-switch — fail-paranoid
# --------------------------------------------------------------------------


def is_paused() -> bool:
    """Return ``True`` if the dispatcher should refuse to run.

    Fail-paranoid: any error reading the flag (permissions, transient I/O)
    is treated as paused. The cost of refusing-to-run for a tick is one
    missed promotion. The cost of running when the operator wanted us
    paused can be multiple bad task_board rows. Pause wins.
    """
    try:
        if PAUSED_FLAG.exists():
            return True
        # If the path exists as something weird (a directory, a symlink to
        # nowhere, an unreadable file), .exists() returns True or False but
        # we want to treat any anomaly as paused.
        if PAUSED_FLAG.is_dir():
            return True
        return False
    except Exception:  # noqa: BLE001 — fail-paranoid intentionally broad
        return True


# --------------------------------------------------------------------------
# Lock — fcntl.flock, non-blocking
# --------------------------------------------------------------------------


@contextlib.contextmanager
def _flock_or_skip():
    """Hold an exclusive lock for the dispatcher run, or yield ``None`` if
    another process holds it. Non-blocking — concurrent invocations are
    benign and should just skip this tick."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK_PATH, "w", encoding="utf-8")
    try:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                yield None
                return
            raise
        yield fh
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        fh.close()


# --------------------------------------------------------------------------
# Pending JSONL reader
# --------------------------------------------------------------------------


def _read_pending_rows(path: Path | None = None) -> list[dict[str, Any]]:
    """Read all rows from the append-only pending JSONL.

    Schema mismatch tolerance: we skip blank lines and JSON-decode errors
    rather than crashing the whole tick. Errors are logged so they remain
    visible to the algedonic invariant (PR3) via dispatcher.health.json
    error count.

    Resolves ``path`` at call time (not as a default-arg) so test fixtures
    that monkeypatch ``PENDING_PATH`` are respected.
    """
    if path is None:
        path = PENDING_PATH
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping malformed pending row")
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _group_rows_by_opportunity(
    rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group rows by ``provenance.opportunity_id``. Rows without an opportunity_id
    are dropped (they cannot be associated with a campaign)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        prov = row.get("provenance") or {}
        opp_id = str(prov.get("opportunity_id") or "")
        if not opp_id:
            continue
        out.setdefault(opp_id, []).append(row)
    return out


def _row_for_stage(rows: list[dict[str, Any]], stage: str) -> dict[str, Any] | None:
    """Find the first row whose ``metadata.stage`` matches ``stage``."""
    for row in rows:
        meta = row.get("metadata") or {}
        if str(meta.get("stage") or "") == stage:
            return row
    return None


# --------------------------------------------------------------------------
# Telos gate — REVIEW→ALLOW+WARN per v3 policy
# --------------------------------------------------------------------------


@dataclass
class _GateOutcome:
    decision: str  # "allow" | "block" | "review"
    reason: str
    review_warning: bool = False


def _gate_check(action: str, content: str) -> _GateOutcome:
    """Run the telos gate. REVIEW is treated as ALLOW + WARN per v3 policy
    (a FIXME ticket is open to wire REVIEW into a real operator approval
    queue; for now we log structured WARN entries so it's auditable)."""
    try:
        from dharma_swarm.telos_gates import check_action
        from dharma_swarm.models import GateDecision
    except Exception as exc:  # noqa: BLE001
        # If gates can't be imported, treat as REVIEW so we never silently
        # bypass governance. Alarming but safer than the alternative.
        logger.exception("telos_gates import failed; treating as REVIEW")
        return _GateOutcome(decision="review", reason=f"import_error: {exc}", review_warning=True)
    try:
        result = check_action(action=action, content=content)
    except Exception as exc:  # noqa: BLE001
        logger.exception("check_action raised; treating as REVIEW")
        return _GateOutcome(decision="review", reason=f"check_error: {exc}", review_warning=True)
    decision = result.decision
    reason = getattr(result, "reason", "") or ""
    if decision == GateDecision.BLOCK:
        return _GateOutcome(decision="block", reason=reason)
    if decision == GateDecision.REVIEW:
        return _GateOutcome(decision="review", reason=reason, review_warning=True)
    return _GateOutcome(decision="allow", reason=reason)


def _write_review_warn(opp_id: str, stage: str, action: str, reason: str) -> None:
    """Append a structured WARN line to the witness log so REVIEW decisions
    that we treat as ALLOW remain auditable."""
    try:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        wpath = WITNESS_DIR / date / "dispatcher_review_warn.jsonl"
        wpath.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "opportunity_id": opp_id,
            "stage": stage,
            "action": action[:200],
            "gate_reason": reason[:500],
            "policy": "v3_review_to_allow",
            "fixme": "wire REVIEW into operator approval queue",
        }
        with wpath.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("witness review_warn write failed", exc_info=True)


# --------------------------------------------------------------------------
# Budget gate
# --------------------------------------------------------------------------


def _budget_exceeded() -> bool:
    """Wrap ``AgentRegistry.is_budget_exceeded`` so import failures are
    treated as exceeded (fail-paranoid: refuse to dispatch if we can't
    verify spend)."""
    try:
        from dharma_swarm.agent_registry import AgentRegistry
    except Exception:
        logger.exception("agent_registry import failed; treating budget as exceeded")
        return True
    try:
        return AgentRegistry().is_budget_exceeded()
    except Exception:
        logger.exception("is_budget_exceeded raised; treating as exceeded")
        return True


# --------------------------------------------------------------------------
# Stigmergic mark — best-effort
# --------------------------------------------------------------------------


async def _mark_stigmergy(opp_id: str, stage: str, task_id: str) -> None:
    """Leave a stigmergic mark on the new task_board row. Best-effort:
    if it fails we log but do not fail the whole promotion."""
    try:
        from dharma_swarm.stigmergy import leave_stigmergic_mark
    except Exception:
        logger.debug("stigmergy import failed; skipping mark")
        return
    try:
        await leave_stigmergic_mark(
            agent="opportunity_dispatcher",
            file_path=str(manifest_path(opp_id)),
            observation=f"promoted {stage} for {opp_id} → task {task_id}",
            salience=0.7,
            connections=[opp_id, task_id],
            channel="strategy",
            action="write",
        )
    except Exception:
        logger.exception("leave_stigmergic_mark failed")


# --------------------------------------------------------------------------
# task_board promotion
# --------------------------------------------------------------------------


async def _create_task_for_stage(
    *,
    opp_id: str,
    stage: str,
    row: dict[str, Any],
    depends_on: list[str],
) -> str:
    """Create a task_board row. Returns the new task_id.

    The full ``row`` dict is stored under ``metadata.frontier_row`` so that
    PR4 can rehydrate the FrontierTask via Pydantic for
    ``frontier_task_to_research_brief``.
    """
    from dharma_swarm.models import TaskPriority
    from dharma_swarm.task_board import TaskBoard

    task_type = "deep_research" if stage == "deep_research" else "stage_doc"
    artifact_filename = STAGE_FILENAME.get(stage, f"{stage}.md")
    metadata = {
        "source": "frontier_task",
        "task_type": task_type,
        "stage": stage,
        "opportunity_id": opp_id,
        "frontier_id": row.get("frontier_id") or "",
        "campaign_dir": str(CAMPAIGN_ROOT / opp_id),
        "artifact_target": str(CAMPAIGN_ROOT / opp_id / artifact_filename),
        "frontier_row": row,
    }
    TASK_BOARD_DB.parent.mkdir(parents=True, exist_ok=True)
    board = TaskBoard(TASK_BOARD_DB)
    # init_db is idempotent (CREATE TABLE IF NOT EXISTS) — cheap to call each
    # promotion and ensures we never crash on a fresh state_dir.
    await board.init_db()
    title = str(row.get("title") or f"{stage} for {opp_id}")
    description = str(row.get("description") or "")
    task = await board.create(
        title=title,
        description=description,
        priority=TaskPriority.HIGH,
        created_by="opportunity_dispatcher",
        depends_on=depends_on or None,
        metadata=metadata,
    )
    return task.id


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------


@dataclass
class HealthState:
    last_run_at: str = ""
    last_success_at: str | None = None
    consecutive_failures: int = 0
    run_count: int = 0
    success_count: int = 0
    last_run_dispatched: int = 0
    last_run_dry_run: bool = False
    last_run_paused: bool = False
    last_run_pending_count: int = 0
    last_run_errors: list[str] = field(default_factory=list)


def _read_health() -> HealthState:
    if not HEALTH_PATH.exists():
        return HealthState()
    try:
        raw = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    except Exception:
        return HealthState()
    return HealthState(
        last_run_at=str(raw.get("last_run_at") or ""),
        last_success_at=raw.get("last_success_at"),
        consecutive_failures=int(raw.get("consecutive_failures") or 0),
        run_count=int(raw.get("run_count") or 0),
        success_count=int(raw.get("success_count") or 0),
        last_run_dispatched=int(raw.get("last_run_dispatched") or 0),
        last_run_dry_run=bool(raw.get("last_run_dry_run") or False),
        last_run_paused=bool(raw.get("last_run_paused") or False),
        last_run_pending_count=int(raw.get("last_run_pending_count") or 0),
        last_run_errors=list(raw.get("last_run_errors") or []),
    )


def _write_health(state: HealthState) -> None:
    HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_run_at": state.last_run_at,
        "last_success_at": state.last_success_at,
        "consecutive_failures": state.consecutive_failures,
        "run_count": state.run_count,
        "success_count": state.success_count,
        "last_run_dispatched": state.last_run_dispatched,
        "last_run_dry_run": state.last_run_dry_run,
        "last_run_paused": state.last_run_paused,
        "last_run_pending_count": state.last_run_pending_count,
        "last_run_errors": state.last_run_errors[-5:],  # cap retained errors
        "schema_version": 1,
    }
    tmp = HEALTH_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, HEALTH_PATH)


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------


@dataclass
class RunResult:
    paused: bool = False
    dry_run: bool = False
    pending_count: int = 0
    promoted: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def _promote_one_opportunity(
    *,
    opp_id: str,
    rows: list[dict[str, Any]],
    dry_run: bool,
    result: RunResult,
) -> None:
    """Apply the PR1 promotion rules to a single opportunity. Mutates
    ``result`` with what happened."""
    # 1. Ensure manifest exists. If not, create it from the first scope row
    #    (the bootstrap template guarantees one row per stage per opportunity).
    manifest = read_manifest(opp_id)
    if manifest is None:
        # Pull metadata from any row — they all share provenance for the same opp.
        sample = rows[0]
        prov = sample.get("provenance") or {}
        manifest = init_manifest(
            opportunity_id=opp_id,
            title=str(sample.get("title") or opp_id),
            domain=str(prov.get("domain") or "unknown"),
            telos_alignment=float(prov.get("telos_alignment") or 0.0),
        )
        if not dry_run:
            write_manifest(opp_id, manifest)

    # 2. Find the first PR1-eligible stage. PR1 = scope only.
    stage = "scope"
    if stage not in PROMOTABLE_STAGES_PR1:
        return
    stage_state = manifest["stages"][stage]
    if stage_state["status"] in {"promoted", "dispatched", "completed", "quarantined", "abandoned"}:
        result.skipped.append(
            {"opportunity_id": opp_id, "stage": stage, "reason": f"already_{stage_state['status']}"}
        )
        return

    row = _row_for_stage(rows, stage)
    if row is None:
        result.skipped.append(
            {"opportunity_id": opp_id, "stage": stage, "reason": "no_pending_row_for_stage"}
        )
        return

    # 3. Telos gate (v3 policy)
    action = f"promote_frontier_task:{stage}:{row.get('title') or ''}"
    content = json.dumps(row, ensure_ascii=False)
    gate = _gate_check(action=action, content=content)
    if gate.decision == "block":
        manifest["gate_blocked"] = True
        update_stage(
            manifest, stage,
            status="blocked", task_id=None,
            blocked_reason=gate.reason,
            blocked_at=datetime.now(timezone.utc).isoformat(),
        )
        if not dry_run:
            write_manifest(opp_id, manifest)
        result.skipped.append(
            {"opportunity_id": opp_id, "stage": stage, "reason": "gate_block", "detail": gate.reason}
        )
        return
    if gate.decision == "review":
        # v3: ALLOW + WARN + review_logged
        manifest["review_logged"] = True
        if not dry_run:
            _write_review_warn(opp_id, stage, action, gate.reason)

    # 4. Budget gate
    if _budget_exceeded():
        manifest["budget_blocked"] = True
        if not dry_run:
            write_manifest(opp_id, manifest)
        result.skipped.append({"opportunity_id": opp_id, "stage": stage, "reason": "budget_exceeded"})
        return

    # 5. Promote — create task_board row
    if dry_run:
        result.promoted.append(
            {"opportunity_id": opp_id, "stage": stage, "task_id": "<dry-run>", "title": row.get("title")}
        )
        return

    try:
        task_id = await _create_task_for_stage(
            opp_id=opp_id, stage=stage, row=row, depends_on=[],
        )
    except Exception as exc:
        logger.exception("task_board.create failed for %s/%s", opp_id, stage)
        result.errors.append(f"{opp_id}/{stage}: {exc}")
        return

    # 6. Update manifest
    manifest["budget_blocked"] = False  # cleared if we got past it
    update_stage(
        manifest, stage,
        status="promoted",
        task_id=task_id,
        promoted_at=datetime.now(timezone.utc).isoformat(),
        retry_count=0,
        last_retry_at=None,
        next_retry_at=None,
    )
    write_manifest(opp_id, manifest)

    # 7. Stigmergic mark (best effort)
    await _mark_stigmergy(opp_id, stage, task_id)

    result.promoted.append(
        {"opportunity_id": opp_id, "stage": stage, "task_id": task_id, "title": row.get("title")}
    )


async def run_once(
    *,
    dry_run: bool = False,
    max_promotions: int | None = None,
) -> RunResult:
    """Single tick of the dispatcher. Returns a RunResult.

    Wrapped in lock + try/except by ``main()``. This function focuses on
    business logic; ``main`` handles ops/health.
    """
    result = RunResult(dry_run=dry_run)
    if is_paused():
        result.paused = True
        return result

    rows = _read_pending_rows()
    result.pending_count = len(rows)
    grouped = _group_rows_by_opportunity(rows)

    attempts = 0
    for opp_id, opp_rows in grouped.items():
        if max_promotions is not None and attempts >= max_promotions:
            break
        before_promoted = len(result.promoted)
        before_errors = len(result.errors)
        await _promote_one_opportunity(
            opp_id=opp_id, rows=opp_rows, dry_run=dry_run, result=result,
        )
        # Count any genuine promotion attempt (success OR error) against the
        # cap. Skips (gate_block, budget, already-promoted) don't consume the
        # cap so an operator can still see all opportunities exercised.
        if (
            len(result.promoted) > before_promoted
            or len(result.errors) > before_errors
        ):
            attempts += 1

    return result


def _update_health_from_result(state: HealthState, result: RunResult, ok: bool) -> HealthState:
    state.run_count += 1
    state.last_run_at = datetime.now(timezone.utc).isoformat()
    state.last_run_dry_run = result.dry_run
    state.last_run_paused = result.paused
    state.last_run_pending_count = result.pending_count
    state.last_run_dispatched = len(result.promoted)
    state.last_run_errors = list(result.errors)
    if ok:
        state.success_count += 1
        state.last_success_at = state.last_run_at
        state.consecutive_failures = 0
    else:
        state.consecutive_failures += 1
    return state


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="opportunity_dispatcher",
        description="Promote frontier tasks from the pending queue onto the canonical task_board.",
    )
    p.add_argument("--dry-run", action="store_true", help="Plan only; write no manifests or tasks.")
    p.add_argument(
        "--max", dest="max_promotions", type=int, default=None,
        help="Cap on promotions per tick (default: unlimited).",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true", help="Log INFO instead of WARNING.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    state = _read_health()
    result: RunResult = RunResult(dry_run=args.dry_run)
    ok = True

    try:
        with _flock_or_skip() as held:
            if held is None:
                logger.warning("dispatcher already running; skipping this tick")
                # Don't bump run_count if we never ran the body. But DO write
                # health so the algedonic invariant sees activity.
                state.last_run_at = datetime.now(timezone.utc).isoformat()
                _write_health(state)
                return 0
            try:
                result = asyncio.run(
                    run_once(dry_run=args.dry_run, max_promotions=args.max_promotions)
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("run_once raised")
                result.errors.append(str(exc))
                ok = False
    except Exception as exc:  # noqa: BLE001 — catch-all for ops health
        logger.exception("dispatcher outer wrapper crashed")
        result.errors.append(str(exc))
        ok = False

    state = _update_health_from_result(state, result, ok=ok and not result.errors)
    try:
        _write_health(state)
    except Exception:
        logger.exception("failed to write health.json")

    # Print a short human summary on stdout for operator visibility.
    summary = {
        "paused": result.paused,
        "dry_run": result.dry_run,
        "pending_count": result.pending_count,
        "promoted": len(result.promoted),
        "skipped": len(result.skipped),
        "errors": len(result.errors),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
