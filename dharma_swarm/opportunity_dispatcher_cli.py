"""CLI orchestration for ``opportunity_dispatcher``."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from types import ModuleType


def _dispatcher(dispatcher_module: ModuleType | None = None) -> ModuleType:
    if dispatcher_module is not None:
        return dispatcher_module
    from dharma_swarm import opportunity_dispatcher
    return opportunity_dispatcher


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


async def _run_full_tick(
    *,
    dry_run: bool,
    max_promotions: int | None,
    observe: bool,
    dispatcher_module: ModuleType | None = None,
):
    dispatcher = _dispatcher(dispatcher_module)
    promote = await dispatcher.run_once(dry_run=dry_run, max_promotions=max_promotions)
    obs = dispatcher.ObserveResult()
    if observe and not dry_run and not promote.paused:
        try:
            obs = await dispatcher.observe_completions()
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(dispatcher.__name__).exception("observe_completions raised")
            obs.errors.append(str(exc))
    return promote, obs


def main(argv: list[str] | None = None, *, dispatcher_module: ModuleType | None = None) -> int:
    dispatcher = _dispatcher(dispatcher_module)
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.retry_quarantined:
        ok, msg = dispatcher.retry_quarantined(args.retry_quarantined)
        print(json.dumps({"action": "retry_quarantined", "ok": ok, "message": msg}))
        return 0 if ok else 1

    state = dispatcher._read_health()
    result = dispatcher.RunResult(dry_run=args.dry_run)
    obs = dispatcher.ObserveResult()
    ok = True
    logger = logging.getLogger(dispatcher.__name__)

    try:
        with dispatcher._flock_or_skip() as held:
            if held is None:
                logger.warning("dispatcher already running; skipping this tick")
                state.last_run_at = datetime.now(timezone.utc).isoformat()
                dispatcher._write_health(state)
                return 0
            try:
                result, obs = asyncio.run(
                    _run_full_tick(
                        dry_run=args.dry_run,
                        max_promotions=args.max_promotions,
                        observe=not args.no_observe,
                        dispatcher_module=dispatcher,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("run_full_tick raised")
                result.errors.append(str(exc))
                ok = False
    except Exception as exc:  # noqa: BLE001
        logger.exception("dispatcher outer wrapper crashed")
        result.errors.append(str(exc))
        ok = False

    state = dispatcher._update_health_from_result(
        state, result, ok=ok and not result.errors and not obs.errors,
    )
    state.last_run_observed_completed = len(obs.completed)
    state.last_run_observed_failed_retried = len(obs.failed_retried)
    state.last_run_observed_failed_abandoned = len(obs.failed_abandoned)
    state.last_run_observed_quarantined = len(obs.quarantined)
    state.last_run_observed_in_flight = len(obs.in_flight)
    if obs.errors:
        state.last_run_errors = (state.last_run_errors + obs.errors)[-5:]
    try:
        dispatcher._write_health(state)
    except Exception:
        logger.exception("failed to write health.json")

    if not args.dry_run and not result.paused:
        dispatcher._maybe_fire_invariant(state, result.pending_count, len(obs.in_flight))

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
