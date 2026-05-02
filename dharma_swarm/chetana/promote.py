"""chetana.promote — staged → trusted.

The single bottleneck through which all atoms must pass to become trusted.
Every promote call:

    1. Reads the staged atom (frontmatter + body).
    2. Validates the frontmatter against the chetana schema.
    3. Runs gate_check_atom() — telos gates on the body content.
    4. On BLOCK: writes a rejected-atom audit row, leaves the staged file alone.
    5. On WARN: writes the trusted atom with review_status='staged' (still needs human approval).
    6. On ALLOW with auto_promote=True: writes review_status='auto_promoted'.
    7. On ALLOW with auto_promote=False (default): writes review_status='staged'.
    8. Computes axiom_signature, sets provenance.promoted_at + promoted_by.
    9. Writes the trusted file to ~/.dharma/knowledge/wiki/concepts/<slug>.md
   10. Deletes the staging file iff write succeeded AND result != BLOCK.
   11. Returns PromoteResult with paths + decision.
"""

from __future__ import annotations

import asyncio
import atexit
import inspect
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Iterator

from . import staging as staging_mod
from .governance import gate_check_atom
from .provenance import (
    FrontmatterSchema,
    GateResult,
    ReviewStatus,
    parse_frontmatter,
)
from .staging import quarantine_atom, write_trusted
from .stigmergy_emit import emit_mark

logger = logging.getLogger(__name__)

PromotionHook = Callable[["PromoteResult", FrontmatterSchema, str], Awaitable[None] | None]
_HOOK_EXECUTOR_MAX_WORKERS = 4
_HOOK_DRAIN_DEFAULT_TIMEOUT_S = 2.0
_promotion_hooks: list[PromotionHook] = []
_hook_executor: ThreadPoolExecutor | None = None
_pending_hook_futures: set[Future] = set()
_pending_lock = threading.Lock()  # guards _pending_hook_futures mutations
_executor_shutdown = False


@dataclass
class PromoteResult:
    staged_path: Path
    trusted_path: Path | None
    decision: GateResult
    review_status: ReviewStatus | None
    rationale: str | None = None
    notes: list[str] = field(default_factory=list)


def register_promotion_hook(hook: PromotionHook) -> None:
    if hook not in _promotion_hooks:
        _promotion_hooks.append(hook)


def unregister_promotion_hook(hook: PromotionHook) -> None:
    try:
        _promotion_hooks.remove(hook)
    except ValueError:
        pass


@contextmanager
def promotion_hooks(*hooks: PromotionHook) -> Iterator[None]:
    for hook in hooks:
        register_promotion_hook(hook)
    try:
        yield
    finally:
        for hook in hooks:
            unregister_promotion_hook(hook)


def clear_promotion_hooks() -> None:
    drain_promotion_hooks()
    _promotion_hooks.clear()


def drain_promotion_hooks(timeout: float = _HOOK_DRAIN_DEFAULT_TIMEOUT_S) -> None:
    """Wait for pending hook futures with a bounded timeout.

    Futures still running after ``timeout`` seconds are logged as overdue and
    left in flight (the executor keeps the worker thread; subsequent submits
    queue behind them). Callers needing a hard guarantee must call
    ``shutdown_hook_executor`` instead.
    """
    with _pending_lock:
        snapshot = set(_pending_hook_futures)
    if not snapshot:
        return
    done, not_done = wait(snapshot, timeout=timeout)
    with _pending_lock:
        _pending_hook_futures.difference_update(done)
    if not_done:
        for future in not_done:
            logger.warning(
                "promotion hook still running after %.1fs drain timeout: %r",
                timeout,
                future,
            )


def _get_hook_executor() -> ThreadPoolExecutor:
    global _hook_executor, _executor_shutdown
    if _hook_executor is None or _executor_shutdown:
        _hook_executor = ThreadPoolExecutor(
            max_workers=_HOOK_EXECUTOR_MAX_WORKERS,
            thread_name_prefix="chetana-promote-hook",
        )
        _executor_shutdown = False
    return _hook_executor


def shutdown_hook_executor(wait_for_pending: bool = True, timeout: float = 5.0) -> None:
    """Shut down the hook executor; safe to call multiple times.

    Registered with ``atexit`` so process exit drains pending hooks. Tests can
    call this explicitly to force cleanup between modules.
    """
    global _hook_executor, _executor_shutdown
    if _hook_executor is None or _executor_shutdown:
        return
    if wait_for_pending:
        drain_promotion_hooks(timeout=timeout)
    try:
        _hook_executor.shutdown(wait=False)
    except Exception:  # pragma: no cover — defensive on shutdown
        logger.debug("hook executor shutdown raised", exc_info=True)
    _executor_shutdown = True


atexit.register(shutdown_hook_executor)


def _run_hook_sync(
    hook: PromotionHook,
    result: PromoteResult,
    schema: FrontmatterSchema,
    body: str,
) -> None:
    out = hook(result, schema, body)
    if inspect.isawaitable(out):
        asyncio.run(out)


def _run_promotion_hooks_safely(
    result: PromoteResult,
    schema: FrontmatterSchema,
    body: str,
) -> None:
    if result.decision == "BLOCK" or not _promotion_hooks:
        return

    for hook in list(_promotion_hooks):
        future = _get_hook_executor().submit(_run_hook_sync, hook, result, schema, body)
        with _pending_lock:
            _pending_hook_futures.add(future)

        def _log_done(done: Future, hook_name: str = getattr(hook, "__name__", repr(hook))) -> None:
            with _pending_lock:
                _pending_hook_futures.discard(done)
            try:
                done.result()
            except Exception:
                logger.warning("promotion hook failed: %s", hook_name, exc_info=True)

        future.add_done_callback(_log_done)


def _register_default_promotion_hooks_if_enabled() -> None:
    from dharma_swarm.chetana import register_default_promotion_hooks

    register_default_promotion_hooks()


def promote(
    *,
    staged_path: Path,
    promoted_by: str = "chetana.promote",
    reviewer: str | None = None,
    auto_promote: bool = False,
    confidence_override: float | None = None,
) -> PromoteResult:
    """Promote a staged atom to the trusted wiki layer.

    See module docstring for the full state machine. Returns a PromoteResult
    even on BLOCK (with trusted_path=None and the rationale).
    """
    staged_path = Path(staged_path).resolve()
    if not staged_path.exists():
        raise FileNotFoundError(staged_path)
    _require_staged_path(staged_path)

    raw = staged_path.read_text(encoding="utf-8")
    schema, body = parse_frontmatter(raw)
    if schema is None:
        raise ValueError(
            f"staged atom has no chetana frontmatter: {staged_path} "
            f"(use chetana.ingest first)"
        )
    if schema.provenance is not None:
        raise ValueError(
            f"staged atom already has provenance set; refusing double-promote: {staged_path}"
        )
    if confidence_override is not None:
        schema = schema.model_copy(update={"confidence": confidence_override})

    gov = gate_check_atom(
        atom_content=body,
        atom_title=schema.title,
        requested_action="chetana.promote",
        metadata={"atom_id": schema.atom_id, "atom_type": schema.type},
    )

    notes: list[str] = []
    if gov.result == "BLOCK":
        # Move to a rejected/ folder for audit, do NOT write to trusted.
        rejected_path = quarantine_atom(staged_path)
        notes.append(
            f"BLOCKED by gates {gov.record.gates_blocked}; staged atom moved to {rejected_path}"
        )
        return PromoteResult(
            staged_path=staged_path,
            trusted_path=None,
            decision="BLOCK",
            review_status="rejected",
            rationale=gov.record.rationale,
            notes=notes,
        )

    review_status: ReviewStatus
    if gov.result == "WARN":
        review_status = "staged"
    elif gov.result == "ALLOW":
        review_status = "auto_promoted" if auto_promote else "staged"
    else:  # pragma: no cover — defensive
        review_status = "staged"

    promoted_schema = schema.model_copy(
        update={
            "provenance": gov.to_provenance(
                promoted_by=promoted_by,
                review_status=review_status,
                reviewer=reviewer,
            )
        }
    )

    trusted_path = write_trusted(promoted_schema, body)
    notes.append(f"promoted ({gov.result}, review={review_status}) → {trusted_path}")

    result = PromoteResult(
        staged_path=staged_path,
        trusted_path=trusted_path,
        decision=gov.result,
        review_status=review_status,
        rationale=gov.record.rationale,
        notes=notes,
    )

    _register_default_promotion_hooks_if_enabled()
    _run_promotion_hooks_safely(result, promoted_schema, body)

    # Best-effort stigmergy emit — never blocks promotion on failure.
    emit_mark(
        action="chetana.promote",
        content=f"{schema.title} | {result.decision}",
        connections=["chetana", "promote", schema.type, result.review_status or "staged"],
        salience=schema.confidence,
    )

    # Successful promote → remove the staged file.
    try:
        staged_path.unlink()
    except OSError as e:
        logger.warning("failed to unlink staged atom %s: %s", staged_path, e)

    return result


def _require_staged_path(path: Path) -> None:
    """Require promote inputs to originate from the configured staging root."""
    staging_root = staging_mod.STAGING_ROOT.resolve()
    try:
        path.relative_to(staging_root)
    except ValueError as exc:
        raise ValueError(
            f"refusing to promote path outside chetana staging root: {path} "
            f"(staging root: {staging_root})"
        ) from exc
