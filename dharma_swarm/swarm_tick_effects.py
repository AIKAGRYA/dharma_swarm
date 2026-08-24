"""Effect-bearing lifecycle tick implementation for :mod:`dharma_swarm.swarm`.

This import-leaf module owns implementation only. ``SwarmManager`` retains
the public method, effect mutex, state, and all scheduling authority.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from dharma_swarm.models import Task, TaskPriority, TaskStatus


async def run_tick_effects(
    self: Any,
    *,
    logger: logging.Logger,
    coordination_state_factory: Callable[[], Any],
) -> dict[str, Any]:
    """Execute one full swarm lifecycle tick.

    This is the unified control path -- the ONLY way to advance
    swarm state.  Both run() and orchestrate_live call this.

    v0.7.0: OrganismRuntime heartbeat runs every _organism_interval_ticks.
    When the Gnani says HOLD, autonomous generation and dispatch are
    suppressed — the organism's pain signal overrides busywork.
    """
    result: dict[str, Any] = {
        "paused": False, "circuit_broken": False,
        "dispatched": 0, "settled": 0, "rescued": 0,
        "synthesized": 0, "director_proposals": 0,
        "reopened": 0, "living_summary": {},
        "organism_verdict": None, "organism_power": None,
    }
    if self._shutdown_started:
        result["paused"] = True
        result["shutdown"] = True
        return result
    import time as _time
    _tick_t0 = _time.monotonic()
    logger.info("tick-%d start", self._tick_count + 1)
    overrides = self._check_human_overrides()
    if overrides["paused"]:
        result["paused"] = True
        return result
    if overrides["focus"] and self._thread_mgr:
        self._thread_mgr._current_thread = overrides["focus"]
        # Wire 3: .FOCUS governs routing, not just thread selection.
        # When identity TCS is drifting, boost routing toward corrective behavior.
        focus_text = str(overrides.get("focus_text", ""))
        if "GPR" in focus_text and self._router:
            # Low gate passage rate → route through reflective reroute path
            self._router._routing_bias = min(
                getattr(self._router, "_routing_bias", 0.0) + 0.1, 0.5
            )
            logger.info(".FOCUS(GPR): routing bias increased to favor frontier models")
        elif "RM" in focus_text and self._engine:
            # Low research momentum → prioritize research tasks
            logger.info(".FOCUS(RM): flagging research task priority boost")
    if self._daemon.circuit_breaker.is_broken:
        result["circuit_broken"] = True
        return result

    allow_autonomous_generation = True
    if self._in_quiet_hours():
        allow_autonomous_generation = False
    if not self._contribution_allowed():
        allow_autonomous_generation = False

    # Every effect-bearing tick starts from red and earns a fresh Graph
    # census while holding _effect_tick_lock. No concurrent tick can reuse
    # the prior green result while this pass is in flight.
    graph_reconciler = self._get_graph_reconciler()
    graph_reconciler.invalidate_boot_census()
    if not self._read_only_boot:
        recovering_boot = not graph_reconciler.boot_recovery_completed
        try:
            tick_report = await asyncio.wait_for(
                self.reconcile_graph_runs(
                    stale_only=graph_reconciler.boot_recovery_completed
                ),
                timeout=10.0,
            )
            result["graph_reconciled"] = tick_report.total_reconciled
        except asyncio.TimeoutError:
            graph_reconciler.invalidate_boot_census()
            logger.warning("Fresh Graph census timed out after 10s")
        except Exception as exc:
            graph_reconciler.invalidate_boot_census()
            error_key = (
                "graph_boot_census_error"
                if recovering_boot
                else "graph_reconcile_error"
            )
            logger.warning("Fresh Graph census failed: %s", exc)
            result[error_key] = f"{type(exc).__name__}: {exc}"

    graph_ready = graph_reconciler.boot_census_succeeded
    result["graph_boot_census_succeeded"] = graph_ready
    if graph_ready:
        try:
            result["claims_heartbeaten"] = (
                graph_reconciler.heartbeat_live_claims()
            )
        except Exception as exc:
            graph_reconciler.invalidate_boot_census()
            graph_ready = False
            result["graph_boot_census_succeeded"] = False
            allow_autonomous_generation = False
            logger.warning("Claim heartbeat failed (non-fatal): %s", exc)
            result["claims_heartbeat_error"] = f"{type(exc).__name__}: {exc}"
            result["graph_dispatch_hold"] = "claim_heartbeat_failed"
    else:
        allow_autonomous_generation = False
        result["claims_heartbeaten"] = 0
        result["graph_dispatch_hold"] = "boot_census_not_succeeded"

    critical_pending = self._critical_startup_pending_components()
    startup_ready = not critical_pending
    if critical_pending:
        if graph_ready:
            backfill_report = await self._backfill_graph_held_startup()
            result["startup_backfill"] = backfill_report
        else:
            result["startup_backfill_hold"] = "graph_census_not_succeeded"
        graph_ready = graph_reconciler.boot_census_succeeded
        result["graph_boot_census_succeeded"] = graph_ready
        critical_pending = self._critical_startup_pending_components()
        startup_ready = not critical_pending

    result["startup_backfill_ready"] = startup_ready
    if not startup_ready:
        allow_autonomous_generation = False
        result["startup_backfill_pending"] = sorted(critical_pending)
        result["startup_dispatch_hold"] = "startup_backfill_pending"
        if self._startup_backfill_last_error:
            result["startup_backfill_error"] = (
                self._startup_backfill_last_error
            )

    optional_pending = (
        "optional_subsystems"
        in self._startup_backfill_pending_components
    )
    optional_scheduled = self._schedule_optional_startup_retry(
        graph_ready=graph_ready and startup_ready
    )
    optional_task = self._optional_startup_retry_task
    result["optional_startup_pending"] = optional_pending
    result["optional_startup_retry_scheduled"] = optional_scheduled
    result["optional_startup_retry_running"] = bool(
        optional_task is not None and not optional_task.done()
    )
    if self._optional_startup_last_error:
        result["optional_startup_error"] = (
            self._optional_startup_last_error
        )
    if not graph_ready:
        allow_autonomous_generation = False
        result["graph_dispatch_hold"] = "boot_census_not_succeeded"

    # v0.9.1: Deferred Telos Substrate seeding (once, first tick). Keep
    # this write-producing bootstrap behind the same fresh Graph census.
    # The concept graph is ~21 MB JSON (4686 nodes, 54804 edges).
    if graph_ready and startup_ready and not self._telos_substrate_seeded:
        seed_marker = self.state_dir / "meta" / "substrate_seeded.flag"
        if seed_marker.exists():
            self._telos_substrate_seeded = True
            logger.info("TelosSubstrate already seeded (flag exists)")
        else:
            self._telos_substrate_seeded = True
            try:
                from dharma_swarm.telos_substrate import TelosSubstrate

                substrate = TelosSubstrate(state_dir=self.state_dir)
                seed_result = await asyncio.wait_for(
                    substrate.seed_all(), timeout=120.0
                )
                logger.info("TelosSubstrate seeded: %s", seed_result)
                seed_marker.parent.mkdir(parents=True, exist_ok=True)
                seed_marker.write_text("seeded")
            except asyncio.TimeoutError:
                logger.warning("TelosSubstrate seeding timed out (120s)")
            except Exception as e:
                logger.warning("TelosSubstrate seeding failed (non-fatal): %s", e)

    # ── Organism heartbeat: Gnani / Samvara ──
    # Runs every _organism_interval_ticks. When the Gnani says HOLD,
    # we suppress autonomous generation — no new busywork until
    # coherence recovers or Samvara completes its diagnostic cycle.
    self._tick_count += 1
    gnani_holds = False
    if (self._organism is not None
            and self._tick_count % self._organism_interval_ticks == 0):
        try:
            hb = await asyncio.wait_for(self._organism.heartbeat(), timeout=10.0)
            result["organism_verdict"] = hb.gnani_verdict.decision if hb.gnani_verdict else None
            result["organism_power"] = (
                self._organism.samvara.current_power.value
                if (self._organism.samvara.active
                    and self._organism.samvara.current_power is not None)
                else None
            )
            if hb.gnani_verdict and hb.gnani_verdict.decision == "HOLD":
                gnani_holds = True
                allow_autonomous_generation = False
                logger.warning(
                    "Gnani HOLD (cycle %d, power=%s): %s — suppressing dispatch",
                    hb.cycle,
                    result["organism_power"] or "—",
                    hb.gnani_verdict.reason,
                )
            # ── Samvara corrections → task pipeline ──
            # When Samvara diagnoses issues, turn corrections into
            # high-priority tasks so the TD can act on them.
            if (allow_autonomous_generation
                    and hb.samvara_diagnostic
                    and hb.samvara_diagnostic.corrections):
                try:
                    corrections_created = 0
                    for corr in hb.samvara_diagnostic.corrections[:3]:
                        await self._task_board.create(
                            title=f"[samvara] {corr[:80]}",
                            description=(
                                f"Samvara correction (power={result['organism_power'] or 'unknown'}, "
                                f"cycle={hb.cycle}): {corr}"
                            ),
                            priority=TaskPriority.HIGH,
                            created_by="samvara",
                        )
                        corrections_created += 1
                    if corrections_created:
                        logger.info(
                            "Samvara → %d correction tasks enqueued", corrections_created,
                        )
                except Exception as corr_exc:
                    logger.debug("Samvara correction task creation failed: %s", corr_exc)
        except asyncio.TimeoutError:
            logger.warning("Organism heartbeat timed out after 10s")
        except Exception as exc:
            logger.debug("Organism heartbeat error: %s", exc)

    # ── Meta-evolution: observe organism fitness, adapt hyperparameters ──
    if (hasattr(self, "_meta_engine") and self._meta_engine is not None
            and result.get("organism_verdict") is not None):
        try:
            from dharma_swarm.evolution import CycleResult

            blended = 0.0
            if self._organism is not None:
                status = self._organism.status()
                blended = status.get("last_blended") or 0.0

            # Consume live agent fitness from durable bus (if available)
            live_best = 0.0
            if self._message_bus is not None:
                try:
                    fitness_events = await asyncio.wait_for(
                        self._message_bus.consume_events("AGENT_FITNESS", limit=50),
                        timeout=3.0,
                    )
                    for ev in fitness_events:
                        payload = ev.get("payload") if isinstance(ev, dict) else {}
                        if isinstance(payload, dict):
                            score = payload.get("fitness_score")
                            if isinstance(score, (int, float)) and score > live_best:
                                live_best = float(score)
                    if live_best > 0:
                        logger.info("Meta-evo: live agent fitness=%.3f (from %d events)",
                                    live_best, len(fitness_events))
                except (asyncio.TimeoutError, Exception):
                    pass  # Non-critical

            # Use max of organism blended and live agent fitness
            best_fitness = max(blended, live_best) if live_best > 0 else blended

            meta_obs = self._meta_engine.observe_cycle_result(
                CycleResult(
                    cycle_id=f"tick-{self._tick_count}",
                    best_fitness=best_fitness,
                ),
            )
            if meta_obs is not None:
                result["meta_evolved"] = meta_obs.evolved_parameters
                result["meta_fitness"] = meta_obs.meta_fitness
                logger.info(
                    "Meta-evolution tick-%d: mf=%.3f evolved=%s",
                    self._tick_count, meta_obs.meta_fitness, meta_obs.evolved_parameters,
                )
        except Exception as me_exc:
            logger.debug("Meta-evolution observation error: %s", me_exc)

    rescued: list[Task] = []
    now = datetime.now(timezone.utc)
    if graph_ready and (self._last_auto_rescue_scan is None
        or (now - self._last_auto_rescue_scan).total_seconds()
        >= self._auto_rescue_scan_interval_seconds):
        try:
            rescued = await asyncio.wait_for(
                self.rescue_recent_failures(), timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning("rescue_recent_failures timed out after 10s")
        self._last_auto_rescue_scan = now
    elif not graph_ready:
        result["auto_rescue_hold"] = "graph_census_not_succeeded"
    result["rescued"] = len(rescued)

    # Orphan reaper: recover tasks stuck on dead agents (runs with rescue scan)
    if (graph_ready
            and self._last_auto_rescue_scan is not None
            and self._last_auto_rescue_scan == now):
        try:
            orphans = await asyncio.wait_for(
                self.reap_orphaned_tasks(), timeout=10.0
            )
            result["orphans_reaped"] = len(orphans)
            if orphans:
                logger.info("Orphan reaper recovered %d task(s)", len(orphans))
        except asyncio.TimeoutError:
            logger.warning("reap_orphaned_tasks timed out after 10s")
        except Exception:
            logger.debug("Orphan reaper error", exc_info=True)

    queue_snapshot: dict[str, int] = {}
    try:
        queue_snapshot = await asyncio.wait_for(
            self._task_queue_snapshot(), timeout=5.0
        )
        result["tasks_ready"] = queue_snapshot.get("ready", 0)
        result["tasks_blocked_pending"] = queue_snapshot.get("blocked_pending", 0)
    except asyncio.TimeoutError:
        logger.warning("_task_queue_snapshot timed out after 5s")

    reopened: list[Any] = []
    # Suppress synthetic task generation when operator-created tasks are pending
    _has_real_tasks = False
    if self._task_board is not None:
        try:
            _pending = await self._task_board.list_tasks(
                status=TaskStatus.PENDING, limit=20
            )
            _has_real_tasks = any(
                isinstance(t.metadata, dict)
                and t.metadata.get("created_via") in ("manual_seed", "swarm.create_task")
                or t.created_by == "operator"
                for t in _pending
            )
        except Exception:
            pass
    if allow_autonomous_generation and not _has_real_tasks:
        import time as _t

        _t0 = _t.monotonic()
        try:
            reopened = await asyncio.wait_for(
                self.spawn_latent_gold_tasks(), timeout=20.0
            )
        except asyncio.TimeoutError:
            logger.warning("spawn_latent_gold_tasks timed out after 20s")
        _dur = _t.monotonic() - _t0
        if _dur > 2.0:
            logger.warning("spawn_latent_gold_tasks took %.1fs", _dur)
    result["reopened"] = len(reopened)

    # When Gnani or Graph readiness holds, settle completions without
    # dispatching new work.
    activity: dict = {}
    _orch_t0 = _time.monotonic()
    try:
        if not gnani_holds and graph_ready and startup_ready:
            activity = await asyncio.wait_for(
                self._orchestrator.tick(), timeout=45.0
            )
            result["dispatched"] = activity.get("dispatched", 0)
            result["settled"] = activity.get("settled", 0)
        elif graph_ready:
            # Still settle completed tasks, just don't dispatch new ones.
            activity = await asyncio.wait_for(
                self._orchestrator.tick_settle_only(), timeout=45.0
            )
    except asyncio.TimeoutError:
        logger.warning("orchestrator.tick timed out after 45s")
    _orch_dur = _time.monotonic() - _orch_t0
    if _orch_dur > 5.0:
        logger.warning("orchestrator.tick took %.1fs", _orch_dur)

    _coord_t0 = _time.monotonic()
    try:
        coordination = await asyncio.wait_for(
            self.coordination_status(refresh=False), timeout=10.0
        )
        # Status remains observable while held, but synthesis is autonomous
        # task generation and therefore requires Graph readiness.
        if not allow_autonomous_generation or _has_real_tasks:
            synthesized = []
        else:
            synthesized = await asyncio.wait_for(
                self.spawn_coordination_tasks(coordination=coordination),
                timeout=15.0,
            )
    except asyncio.TimeoutError:
        coordination = coordination_state_factory()
        synthesized = []
        logger.warning("coordination timed out")
    result["synthesized"] = len(synthesized)
    _coord_dur = _time.monotonic() - _coord_t0
    if _coord_dur > 5.0:
        logger.warning("coordination took %.1fs", _coord_dur)

    director_proposals: list[Task] = []
    if (allow_autonomous_generation and self._director is not None
        and self._tick_count % self._director_interval_ticks == 0):
        _dir_t0 = _time.monotonic()
        try:
            director_proposals = await asyncio.wait_for(
                self._director_pulse(), timeout=20.0
            )
        except asyncio.TimeoutError:
            logger.warning("director_pulse timed out after 20s")
        except Exception:
            logger.debug("Director pulse failed", exc_info=True)
        _dir_dur = _time.monotonic() - _dir_t0
        if _dir_dur > 5.0:
            logger.warning("director_pulse took %.1fs", _dir_dur)
    result["director_proposals"] = len(director_proposals)

    living_summary: dict[str, int] = {}
    if self._tick_count % self._living_interval_ticks == 0:
        try:
            living_summary = await asyncio.wait_for(
                self._tick_living_layers(), timeout=15.0
            )
        except asyncio.TimeoutError:
            logger.warning("_tick_living_layers timed out after 15s")
    result["living_summary"] = living_summary

    # ── Witness audit (Beer S3*): sporadic random audit ──
    if (self._witness is not None
            and self._tick_count % self._witness_interval_ticks == 0):
        try:
            findings = await self._witness.run_cycle()
            result["witness_findings"] = len(findings)
            actionable = sum(1 for f in findings if f.is_actionable)
            if actionable:
                logger.info(
                    "Witness S3* audit: %d findings, %d actionable",
                    len(findings), actionable,
                )
        except Exception as exc:
            logger.debug("Witness audit error: %s", exc)

    # ── AutoProposer: closed-loop self-improvement ──
    if (allow_autonomous_generation and self._auto_proposer is not None
            and self._tick_count % self._auto_proposer_interval_ticks == 0):
        try:
            ap_result = await asyncio.wait_for(
                self._auto_proposer.cycle(), timeout=30.0
            )
            result["auto_proposer_observations"] = ap_result.observations_collected
            result["auto_proposer_proposals"] = ap_result.proposals_generated
            result["auto_proposer_submitted"] = ap_result.proposals_submitted
            if ap_result.proposals_generated:
                logger.info(
                    "AutoProposer: %d observations -> %d proposals -> %d submitted",
                    ap_result.observations_collected,
                    ap_result.proposals_generated,
                    ap_result.proposals_submitted,
                )
        except asyncio.TimeoutError:
            logger.warning("AutoProposer.cycle timed out after 30s")
        except Exception as exc:
            logger.debug("AutoProposer cycle error: %s", exc)

    _tick_dur = _time.monotonic() - _tick_t0
    logger.info(
        "tick-%d done (%.1fs): dispatched=%d settled=%d rescued=%d reopened=%d "
        "ready=%d blocked=%d organism=%s meta=%s",
        self._tick_count, _tick_dur,
        result.get("dispatched", 0), result.get("settled", 0),
        len(rescued), len(reopened),
        queue_snapshot.get("ready", -1),
        queue_snapshot.get("blocked_pending", -1),
        result.get("organism_verdict", "-"),
        result.get("meta_fitness", "-"),
    )
    did_work = (bool(reopened) or bool(rescued) or bool(synthesized)
                or bool(director_proposals) or self._tick_did_work(activity))
    if did_work:
        self._last_contribution = datetime.now()
        self._daily_contributions += 1
        self._daemon.circuit_breaker.record_success()
        if self._thread_mgr:
            self._thread_mgr.record_contribution()
    return result
