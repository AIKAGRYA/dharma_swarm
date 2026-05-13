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
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm import opportunity_dispatcher_observer as _observer
from dharma_swarm._campaign_manifest import (
    CAMPAIGN_ROOT,
    init_manifest,
    list_campaign_ids,
    manifest_path,
    read_manifest,
    update_stage,
    write_manifest,
)
from dharma_swarm.operator_action_gateway import OperatorActionGateway
from dharma_swarm.runtime_state import RuntimeStateStore

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

# Stages this PR is allowed to promote. Extended through PR5.
# PR1 had only ``scope``; PR2 adds ``validate``; PR4 adds ``deep_research``;
# PR5 adds ``capability`` and ``mvp``; ``first_artifact`` is deferred to PR7
# because it expects a built artifact (per template at curriculum_engine.py:153),
# not a memo, and so needs a different result contract.
PROMOTABLE_STAGES: tuple[str, ...] = (
    "scope", "validate", "deep_research", "capability", "mvp",
)

# Throttle: deep_research stages are expensive (LLM-driven AutoResearch).
# Cap at N promotions in a rolling 24h window. PR4 enforces this gate.
DEEP_RESEARCH_THROTTLE_PER_DAY = 6
DEEP_RESEARCH_WINDOW_SECONDS = 24 * 3600

# Filenames per stage for the artifact_target metadata field. The completion
# observer writes to these paths.
STAGE_FILENAME: dict[str, str] = {
    "scope": "scope.md",
    "validate": "validate.md",
    "deep_research": "deep_research.json",
    "capability": "capability.md",
    "mvp": "mvp.md",
    # ``first_artifact`` deliberately absent — PR7 needs a directory contract.
}

# Retry backoff for failed stages. Index = retry_count *before* the increment;
# value = seconds to wait before the next retry. ``None`` = abandon (no more
# retries). PR2 policy: try once, retry after 1h, retry after 6h, then abandon.
RETRY_BACKOFF_SECONDS: tuple[int | None, ...] = (3600, 21600, None)

# Stages whose completion the observer treats as a stage_doc (writes a plain
# .md file from task.result). ``deep_research`` is excluded because PR4 routes
# it through ArtifactManifestStore for proper sidecar-manifest semantics.
STAGE_DOC_STAGES: frozenset[str] = frozenset({"scope", "validate", "capability", "mvp"})

HealthState = _observer.HealthState
ObserveResult = _observer.ObserveResult
DEFAULT_INTERVAL_SECONDS = _observer.DEFAULT_INTERVAL_SECONDS
CRITICAL_FAILURE_THRESHOLD = _observer.CRITICAL_FAILURE_THRESHOLD


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


def _find_eligible_stage(manifest: dict[str, Any]) -> str | None:
    """Pick the first PROMOTABLE stage that the dispatcher should attempt
    on this tick, walking the canonical order.

    Stop conditions (return ``None``):
    - A stage is in flight (``promoted`` or ``dispatched``) — wait for it
      before promoting any successor.
    - A stage is ``quarantined`` or ``abandoned`` — operator must clear via
      ``--retry-quarantined`` or accept the chain death.
    - A stage is ``failed`` with ``next_retry_at`` in the future — not yet.

    Skip conditions (continue to next stage):
    - A stage is ``completed`` — move on to its successor.

    Promote conditions (return that stage):
    - Status is ``pending`` (fresh) or ``blocked`` (gate may have changed
      its mind) or ``failed`` with retry due now.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    for stage in PROMOTABLE_STAGES:
        s = manifest["stages"].get(stage)
        if s is None:  # schema mismatch — treat as not promotable
            return None
        status = str(s.get("status") or "")
        if status in {"promoted", "dispatched"}:
            return None
        if status == "completed":
            continue
        if status in {"quarantined", "abandoned"}:
            return None
        if status == "failed":
            next_retry = s.get("next_retry_at")
            if next_retry is not None and now_iso < str(next_retry):
                return None
        # status is pending, blocked, or failed-with-retry-due
        return stage
    return None


def _summarize_chain_status(statuses: dict[str, Any]) -> str:
    """One-word summary for the skip reason. Picks the strongest signal."""
    vals = list(statuses.values())
    if any(v == "promoted" or v == "dispatched" for v in vals):
        return "in_flight"
    if any(v == "quarantined" for v in vals):
        return "quarantined"
    if any(v == "abandoned" for v in vals):
        return "abandoned"
    if all(v == "completed" or v is None for v in vals):
        return "all_completed"
    if any(v == "failed" for v in vals):
        return "failed_retry_pending"
    return "no_eligible_stage"


def _count_recent_deep_research_promotions(
    window_seconds: int = DEEP_RESEARCH_WINDOW_SECONDS,
) -> int:
    """Scan all campaign manifests and count deep_research stages that were
    promoted (or completed) within the last ``window_seconds``.

    This is the throttle counter: cap is ``DEEP_RESEARCH_THROTTLE_PER_DAY``.
    Counts promotions even if the stage later completed or was quarantined,
    because the cost was already incurred at promotion time.
    """
    threshold = datetime.now(timezone.utc).timestamp() - window_seconds
    count = 0
    for opp_id in list_campaign_ids():
        m = read_manifest(opp_id)
        if m is None:
            continue
        s = (m.get("stages") or {}).get("deep_research") or {}
        promoted_at = s.get("promoted_at") or s.get("completed_at")
        if not promoted_at:
            continue
        try:
            ts = datetime.fromisoformat(str(promoted_at)).timestamp()
        except ValueError:
            continue
        if ts >= threshold:
            count += 1
    return count


def _depends_on_for_stage(manifest: dict[str, Any], stage: str) -> list[str]:
    """Return the task_id of the immediately-prior PROMOTABLE stage if it
    exists and was promoted (so its task_id is on task_board). Empty list
    for the first stage."""
    try:
        idx = PROMOTABLE_STAGES.index(stage)
    except ValueError:
        return []
    if idx == 0:
        return []
    prev = PROMOTABLE_STAGES[idx - 1]
    prev_state = manifest["stages"].get(prev) or {}
    prev_task_id = prev_state.get("task_id")
    return [prev_task_id] if prev_task_id else []


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


def _record_review_operator_action(opp_id: str, stage: str, action: str, reason: str) -> None:
    """Record REVIEW decisions in the canonical operator action queue.

    The dispatcher still preserves the existing v3 REVIEW->ALLOW+WARN
    semantics. This adds the missing operator-visible queue entry without
    changing promotion behavior in this PR.
    """
    try:
        runtime_state = RuntimeStateStore(DHARMA_HOME / "state" / "runtime.db")
        gateway = OperatorActionGateway(runtime_state)
        gateway.submit_proposal_sync(
            action_name="opportunity_dispatcher.review_required",
            actor="opportunity_dispatcher",
            reason=reason,
            payload={
                "opportunity_id": opp_id,
                "stage": stage,
                "action": action,
                "legacy_policy": "v3_review_to_allow",
            },
            source="opportunity_dispatcher",
            target="operator_approval_queue",
            risk="medium",
            approval_required=True,
            telos_check=False,
            correlation_id=f"opportunity_review:{opp_id}:{stage}",
            idempotency_key=f"opportunity_review:{opp_id}:{stage}",
        )
    except Exception:
        logger.debug("operator action review queue write failed", exc_info=True)


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
# Health facade
# --------------------------------------------------------------------------


def _read_health() -> HealthState:
    return _observer._read_health(HEALTH_PATH)


def _write_health(state: HealthState) -> None:
    _observer._write_health(state, HEALTH_PATH)


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

    # 2. Find the first eligible stage in canonical order.
    #    A stage is eligible when:
    #      - it is in PROMOTABLE_STAGES (PR-gated)
    #      - its current status is "pending" (or "failed" with retry due, or
    #        "blocked" — gate may now allow)
    #      - the immediately prior stage is completed (or there is no prior)
    #    The first such stage wins; we promote one stage per opportunity per
    #    tick. Subsequent ticks pick up the next stage as predecessors complete.
    stage = _find_eligible_stage(manifest)
    if stage is None:
        # Silent skip is fine for the dispatcher's own logic, but emit a
        # reason for operator visibility (which stages already in flight,
        # which were completed, which are quarantined).
        statuses = {st: m.get("status") for st, m in (manifest.get("stages") or {}).items()}
        result.skipped.append(
            {"opportunity_id": opp_id, "stage": "<chain>",
             "reason": f"already_{_summarize_chain_status(statuses)}",
             "stages": statuses}
        )
        return
    stage_state = manifest["stages"][stage]

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
            _record_review_operator_action(opp_id, stage, action, gate.reason)

    # 4a. Throttle gate (PR4): cap deep_research promotions per 24h window.
    if stage == "deep_research":
        recent = _count_recent_deep_research_promotions()
        if recent >= DEEP_RESEARCH_THROTTLE_PER_DAY:
            manifest["throttled"] = True
            if not dry_run:
                write_manifest(opp_id, manifest)
            result.skipped.append(
                {"opportunity_id": opp_id, "stage": stage,
                 "reason": "deep_research_throttled",
                 "recent_count": recent,
                 "limit": DEEP_RESEARCH_THROTTLE_PER_DAY}
            )
            return

    # 4b. Budget gate
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

    depends_on = _depends_on_for_stage(manifest, stage)
    try:
        task_id = await _create_task_for_stage(
            opp_id=opp_id, stage=stage, row=row, depends_on=depends_on,
        )
    except Exception as exc:
        logger.exception("task_board.create failed for %s/%s", opp_id, stage)
        result.errors.append(f"{opp_id}/{stage}: {exc}")
        return

    # 6. Update manifest. Preserve retry_count across re-promotions so the
    #    failure handler can keep counting toward the abandon threshold.
    manifest["budget_blocked"] = False  # cleared if we got past it
    prior_retry_count = int(stage_state.get("retry_count") or 0)
    update_stage(
        manifest, stage,
        status="promoted",
        task_id=task_id,
        promoted_at=datetime.now(timezone.utc).isoformat(),
        retry_count=prior_retry_count,
        # last_retry_at and next_retry_at intentionally preserved — they
        # describe the most recent failure, not this re-promotion.
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
    return _observer._update_health_from_result(state, result, ok)


# --------------------------------------------------------------------------
# Completion observer facade
#
# The implementation lives in opportunity_dispatcher_observer.py. Keep these
# wrappers so existing tests and callers can patch this module's paths.
# --------------------------------------------------------------------------


def _scan_in_flight() -> list[tuple[str, str, dict[str, Any]]]:
    return _observer._scan_in_flight()


def _is_quarantine_result(task: Any) -> bool:
    return _observer._is_quarantine_result(task)


async def _process_completed_task(
    opp_id: str, stage: str, manifest: dict[str, Any], task: Any,
    result: ObserveResult,
) -> None:
    await _observer._process_completed_task(
        opp_id, stage, manifest, task, result,
        campaign_root=CAMPAIGN_ROOT,
        stage_filename=STAGE_FILENAME,
        stage_doc_stages=STAGE_DOC_STAGES,
    )


def _process_failed_task(
    opp_id: str, stage: str, manifest: dict[str, Any], task: Any,
    result: ObserveResult,
) -> None:
    _observer._process_failed_task(
        opp_id, stage, manifest, task, result,
        retry_backoff_seconds=RETRY_BACKOFF_SECONDS,
    )


async def observe_completions() -> ObserveResult:
    return await _observer.observe_completions(
        task_board_db=TASK_BOARD_DB,
        campaign_root=CAMPAIGN_ROOT,
        stage_filename=STAGE_FILENAME,
        stage_doc_stages=STAGE_DOC_STAGES,
        retry_backoff_seconds=RETRY_BACKOFF_SECONDS,
    )


def retry_quarantined(spec: str) -> tuple[bool, str]:
    return _observer.retry_quarantined(
        spec,
        promotable_stages=PROMOTABLE_STAGES,
        stage_filename=STAGE_FILENAME,
    )


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
    p.add_argument(
        "--no-observe", action="store_true",
        help="Skip the completion observer (promotion-only mode).",
    )
    p.add_argument(
        "--retry-quarantined", metavar="OPP_ID:STAGE", default=None,
        help="Clear a quarantined stage so the dispatcher will re-attempt it.",
    )
    return p


# --------------------------------------------------------------------------
# Stalled-frontier invariant facade
# --------------------------------------------------------------------------


def _is_frontier_active(pending_count: int, observed_in_flight: int) -> bool:
    return _observer._is_frontier_active(pending_count, observed_in_flight)


def _stall_window_seconds(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> int:
    return _observer._stall_window_seconds(interval_seconds)


def detect_stalled_frontier(
    *,
    state: HealthState,
    pending_count: int,
    observed_in_flight: int,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
) -> dict[str, Any] | None:
    return _observer.detect_stalled_frontier(
        state=state,
        pending_count=pending_count,
        observed_in_flight=observed_in_flight,
        interval_seconds=interval_seconds,
    )


def _maybe_fire_invariant(
    state: HealthState, pending_count: int, observed_in_flight: int,
) -> None:
    _observer._maybe_fire_invariant(
        state, pending_count, observed_in_flight,
    )


async def _run_full_tick(
    *, dry_run: bool, max_promotions: int | None, observe: bool,
) -> tuple[RunResult, ObserveResult]:
    """Promotion phase + observer phase, in that order. Each phase isolates
    its own try/except so a failing observer cannot prevent promotion (and
    vice versa)."""
    promote = await run_once(dry_run=dry_run, max_promotions=max_promotions)
    obs = ObserveResult()
    if observe and not dry_run and not promote.paused:
        try:
            obs = await observe_completions()
        except Exception as exc:  # noqa: BLE001
            logger.exception("observe_completions raised")
            obs.errors.append(str(exc))
    return promote, obs


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # --retry-quarantined is a one-shot CLI op; doesn't take the lock or
    # touch health.json (it's a manual operator action).
    if args.retry_quarantined:
        ok, msg = retry_quarantined(args.retry_quarantined)
        print(json.dumps({"action": "retry_quarantined", "ok": ok, "message": msg}))
        return 0 if ok else 1

    state = _read_health()
    result: RunResult = RunResult(dry_run=args.dry_run)
    obs: ObserveResult = ObserveResult()
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
                result, obs = asyncio.run(
                    _run_full_tick(
                        dry_run=args.dry_run,
                        max_promotions=args.max_promotions,
                        observe=not args.no_observe,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("run_full_tick raised")
                result.errors.append(str(exc))
                ok = False
    except Exception as exc:  # noqa: BLE001 — catch-all for ops health
        logger.exception("dispatcher outer wrapper crashed")
        result.errors.append(str(exc))
        ok = False

    state = _update_health_from_result(state, result, ok=ok and not result.errors and not obs.errors)
    state.last_run_observed_completed = len(obs.completed)
    state.last_run_observed_failed_retried = len(obs.failed_retried)
    state.last_run_observed_failed_abandoned = len(obs.failed_abandoned)
    state.last_run_observed_quarantined = len(obs.quarantined)
    state.last_run_observed_in_flight = len(obs.in_flight)
    if obs.errors:
        state.last_run_errors = (state.last_run_errors + obs.errors)[-5:]
    try:
        _write_health(state)
    except Exception:
        logger.exception("failed to write health.json")

    # Stalled-frontier invariant — fire AFTER health is written so the
    # bridge sees the most recent state. Best-effort; bridge errors do not
    # affect exit code.
    if not args.dry_run and not result.paused:
        _maybe_fire_invariant(state, result.pending_count, len(obs.in_flight))

    # Print a short human summary on stdout for operator visibility.
    summary = {
        "paused": result.paused,
        "dry_run": result.dry_run,
        "pending_count": result.pending_count,
        "promoted": len(result.promoted),
        "skipped": len(result.skipped),
        "errors": len(result.errors) + len(obs.errors),
        "observed_completed": len(obs.completed),
        "observed_failed_retried": len(obs.failed_retried),
        "observed_failed_abandoned": len(obs.failed_abandoned),
        "observed_quarantined": len(obs.quarantined),
        "observed_in_flight": len(obs.in_flight),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
