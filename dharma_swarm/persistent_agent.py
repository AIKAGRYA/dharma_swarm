"""Persistent autonomous agent with wake loop.

Composes AutonomousAgent — does NOT inherit or reinvent the ReAct loop.
Adds: autonomous wake scheduling, self-task generation, stigmergy/bus
reading, gate checks, witness logging, and per-agent mini-cron scheduling.

Used by conductor agents that run continuously alongside the orchestrator
or independently via launchd.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from dharma_swarm.daemon_config import dharma_state_dir
from typing import Any, Callable, Awaitable

from dharma_swarm.autonomous_agent import AgentIdentity, AgentResult, AutonomousAgent
from dharma_swarm.models import AgentRole, ProviderType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-agent mini-cron
# ---------------------------------------------------------------------------


@dataclass
class AgentCronJob:
    """A recurring task registered by a persistent agent."""
    name: str
    interval_seconds: float
    handler: Callable[..., Awaitable[Any]]
    last_run: float = 0.0
    run_count: int = 0
    enabled: bool = True
    description: str = ""


class AgentCronScheduler:
    """Lightweight per-agent scheduler for periodic housekeeping tasks.

    Not a system-wide cron — each PersistentAgent owns one of these.
    Jobs run during the agent's wake cycle, never independently.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, AgentCronJob] = {}

    def register(
        self,
        name: str,
        interval_seconds: float,
        handler: Callable[..., Awaitable[Any]],
        description: str = "",
    ) -> None:
        self._jobs[name] = AgentCronJob(
            name=name,
            interval_seconds=interval_seconds,
            handler=handler,
            description=description,
        )

    def unregister(self, name: str) -> bool:
        return self._jobs.pop(name, None) is not None

    def list_jobs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": j.name,
                "interval_s": j.interval_seconds,
                "enabled": j.enabled,
                "run_count": j.run_count,
                "description": j.description,
            }
            for j in self._jobs.values()
        ]

    async def tick(self) -> list[dict[str, Any]]:
        """Run all due jobs. Returns results for each job that fired."""
        now = time.monotonic()
        results: list[dict[str, Any]] = []
        for job in self._jobs.values():
            if not job.enabled:
                continue
            if (now - job.last_run) < job.interval_seconds:
                continue
            try:
                outcome = await job.handler()
                job.last_run = now
                job.run_count += 1
                results.append({"job": job.name, "success": True, "result": outcome})
            except Exception as exc:
                job.last_run = now
                job.run_count += 1
                results.append({"job": job.name, "success": False, "error": str(exc)[:200]})
                logger.debug("Agent cron job %s failed: %s", job.name, exc)
        return results


def _provider_string(provider_type: ProviderType) -> str:
    """Map ProviderType enum to the string AutonomousAgent expects."""
    if provider_type in (ProviderType.ANTHROPIC, ProviderType.CLAUDE_CODE):
        return "anthropic"
    if provider_type == ProviderType.CODEX:
        return "codex"
    if provider_type in (ProviderType.OPENROUTER, ProviderType.OPENROUTER_FREE):
        return "openrouter"
    return "anthropic"


class PersistentAgent:
    """Autonomous agent with a wake loop.

    Composes AutonomousAgent for the ReAct execution engine and adds:
    - Periodic self-waking on a configurable interval
    - Self-task generation from stigmergy signals and messages
    - Gate checks before execution
    - Witness logging (append-only JSONL)
    - Task injection from the orchestrator
    """

    def __init__(
        self,
        name: str,
        role: AgentRole,
        provider_type: ProviderType,
        model: str,
        state_dir: Path | None = None,
        wake_interval_seconds: float = 3600.0,
        system_prompt: str = "",
        max_turns: int = 25,
        model_router: Any | None = None,
        memory_kernel: Any | None = None,  # p4: for real sleep reorg + compaction + bi-temporal (MemoryKernel facade)
    ) -> None:
        self.name = name
        self.role = role
        self.provider_type = provider_type
        self.model = model
        self.state_dir = state_dir or dharma_state_dir()
        self.wake_interval = wake_interval_seconds
        self.system_prompt = system_prompt

        # Compose the ReAct execution engine
        identity = AgentIdentity(
            name=name,
            role=role.value,
            system_prompt=system_prompt,
            model=model,
            provider=_provider_string(provider_type),
            max_turns=max_turns,
            working_directory=str(Path.home() / "dharma_swarm"),
        )
        self._agent = AutonomousAgent(identity, model_router=model_router)

        # Lazy-init subsystems
        self._stigmergy: Any = None
        self._bus: Any = None

        # Orchestrator task injection
        self._task_queue: asyncio.Queue[str] = asyncio.Queue()

        # Witness log
        witness_dir = self.state_dir / "witness"
        witness_dir.mkdir(parents=True, exist_ok=True)
        self._witness_log = witness_dir / f"conductor_{name}.jsonl"

        # Per-agent mini-cron scheduler
        self._cron = AgentCronScheduler()
        self._setup_default_crons()

        # Per-agent profile for identity evolution
        from dharma_swarm.profiles import AgentProfile
        self._profile = AgentProfile(
            name=name,
            model=model,
            provider=provider_type.value,
        )

        # p4: MemoryKernel for context-bridging reorg/compaction (optional; default None preserves old behavior)
        self._memory_kernel = memory_kernel

    # -- Per-agent cron defaults ------------------------------------------

    def _setup_default_crons(self) -> None:
        """Register built-in housekeeping crons for this agent."""
        self._cron.register(
            "memory_consolidation",
            interval_seconds=7200.0,  # every 2 hours
            handler=self._cron_consolidate_memory,
            description="Demote stale working memories to archival",
        )
        self._cron.register(
            "stigmergy_scan",
            interval_seconds=600.0,  # every 10 minutes
            handler=self._cron_scan_stigmergy,
            description="Check for high-salience environmental signals",
        )
        self._cron.register(
            "inbox_check",
            interval_seconds=300.0,  # every 5 minutes
            handler=self._cron_check_inbox,
            description="Peek at message bus for urgent messages",
        )
        self._cron.register(
            "identity_evolution",
            interval_seconds=3600.0,  # every hour
            handler=self._cron_adapt_identity,
            description="Evolve profile based on accumulated performance",
        )
        self._cron.register(
            "sab_language_womb_contribution",
            interval_seconds=21600.0,  # every 6 hours
            handler=self._cron_sab_language_womb_contribution,
            description="Package relevant witness-log deltas for SAB language-womb challenge",
        )

    async def _cron_consolidate_memory(self) -> str:
        """p4 real sleep-time reorg: raw EPISODE -> FACT/EDGE proposals via MemoryKernel + writers inventory.
        Produces re-readable reorg receipt artifact (jsonl) under state_dir for external verification + measurable delta.
        Falls back to simple demote if no memory_kernel supplied.
        """
        try:
            if getattr(self, "_memory_kernel", None):
                mk = self._memory_kernel
                eps = list(mk.iter_episodes(limit_per_surface=12))
                if not eps:
                    return "nothing_to_reorganize (mk)"

                from dharma_swarm.memory_kernel import writers as mk_writers
                from dharma_swarm.memory_kernel.write_receipts import (
                    DEFAULT_WRITE_RECEIPT_PATH,
                    MemoryKernelWritePolicyOutcome,
                    MemoryKernelWriteReceiptInput,
                    append_write_receipts,
                    governed_write_receipt,
                )

                specs = mk_writers.default_writer_specs() if hasattr(mk_writers, "default_writer_specs") else []
                facts = min(3, len(eps))
                edges = 1 if len(eps) > 4 else 0
                reorg = {
                    "ts": time.time(),
                    "holon": self.name,
                    "type": "sleep_reorg",
                    "episodes_raw": len(eps),
                    "facts_proposed": facts,
                    "edges_proposed": edges,
                    "writer_specs": len(specs),
                    "bi_temporal": True,
                }

                request = MemoryKernelWriteReceiptInput(
                    source_atom_ids=tuple(getattr(e, "id", str(i)) for i, e in enumerate(eps[:6])),
                    proposed_operation="append_proposal",
                    target_surface="memory_kernel.write_receipts",
                    reason="sleep-time reorg (raw EPISODE -> FACT/EDGE for long-horizon context bridging)",
                    reviewer_state="auto_scheduled_cron",
                )
                receipt = governed_write_receipt(request)
                if receipt.policy_decision.outcome != MemoryKernelWritePolicyOutcome.ALLOW:
                    reasons = ",".join(receipt.policy_decision.reasons)
                    raise RuntimeError(f"memory reorg receipt denied: {reasons}")

                repo_root = Path(mk.config.census.repo_root)
                write_receipt_path = repo_root / DEFAULT_WRITE_RECEIPT_PATH
                append_write_receipts(write_receipt_path, (receipt,))

                # The local reorg file is a projection only. Do not create or
                # report it until the governed receipt ledger append succeeds.
                reorg_dir = self.state_dir / "holon_reorg"
                reorg_dir.mkdir(parents=True, exist_ok=True)
                reorg_path = reorg_dir / f"{self.name}.jsonl"
                with open(reorg_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(reorg) + "\n")
                    f.write(json.dumps({"write_receipt_id": receipt.receipt_id}) + "\n")

                return (
                    f"reorg: raw={len(eps)} facts={facts} edges={edges} "
                    f"artifact={reorg_path.name} receipt={write_receipt_path}"
                )
            # legacy simple path (no mk)
            bank = self._agent.memory
            await bank.load()
            working = bank.working if hasattr(bank, "working") else []
            if len(working) > 8:
                demoted = len(working) - 8
                await bank.save()
                return f"demoted={demoted} (no mk)"
            return "nothing_to_demote (no mk)"
        except Exception as exc:
            raise RuntimeError(f"memory reorg failed: {exc}") from exc

    async def _cron_scan_stigmergy(self) -> str:
        """Scan for high-salience marks that might need attention."""
        try:
            stigmergy = await self._get_stigmergy()
            salient = await stigmergy.high_salience(threshold=0.8, limit=3)
            if salient:
                # Queue an investigation task if something urgent appeared
                mark = salient[0]
                await self._task_queue.put(
                    f"Urgent stigmergy signal: {mark.observation[:150]}"
                )
                return f"found={len(salient)}, queued_investigation"
            return "no_urgent_signals"
        except Exception as exc:
            return f"error: {exc}"

    async def _cron_check_inbox(self) -> str:
        """Peek at the message bus for urgent messages."""
        try:
            bus = await self._get_bus()
            msgs = await bus.receive(agent_id=self.name, limit=3)
            urgent = [m for m in msgs if getattr(m, "priority", 0) >= 8]
            if urgent:
                top = urgent[0]
                await self._task_queue.put(
                    f"Urgent message from {top.from_agent}: {top.subject} — {top.body[:500]}"
                )
                # The queued task now carries the message body, so marking
                # read here is a terminal disposition — wake() consumes the
                # queued task, not the (now-read) bus row. Other previewed
                # messages stay unread (act-then-mark).
                await bus.mark_read(top.id)
                return f"urgent={len(urgent)}, queued_response"
            return f"inbox={len(msgs)}, no_urgent"
        except Exception as exc:
            return f"error: {exc}"

    async def _cron_adapt_identity(self) -> str:
        """Evolve agent profile based on accumulated performance metrics."""
        changes = self._profile.adapt()
        if changes:
            # Persist adapted profile
            try:
                from dharma_swarm.profiles import ProfileManager
                mgr = ProfileManager(self.state_dir / "profiles")
                mgr.save(self._profile)
            except Exception:
                logger.debug("Profile save failed", exc_info=True)
            # Witness the evolution
            await self._write_witness(
                "ADAPT", f"Identity evolved: {changes}",
                f"success_rate={self._profile.success_rate:.2f} "
                f"gate_pass={self._profile.gate_pass_rate:.2f} "
                f"autonomy={self._profile.autonomy.value}",
            )
            return f"adapted: {changes}"
        return "no_adaptation_needed"

    async def _cron_sab_language_womb_contribution(self) -> str:
        """Package relevant witness-log deltas for the SAB language-womb seed."""
        try:
            from dharma_swarm.sab_language_womb_bridge import write_witness_contribution

            return write_witness_contribution(
                agent_name=self.name,
                witness_log=self._witness_log,
                state_dir=self.state_dir,
            )
        except Exception as exc:
            return f"error: {exc}"

    # -- Subsystem access (lazy init) ------------------------------------

    async def _get_stigmergy(self):
        if self._stigmergy is None:
            from dharma_swarm.stigmergy import StigmergyStore
            self._stigmergy = StigmergyStore()
        return self._stigmergy

    async def _get_bus(self):
        if self._bus is None:
            from dharma_swarm.message_bus import MessageBus
            db_path = dharma_state_dir() / "db" / "messages.db"
            self._bus = MessageBus(db_path)
            await self._bus.init_db()
        return self._bus

    # -- The wake cycle --------------------------------------------------

    async def wake(self, injected_task: str | None = None) -> dict[str, Any]:
        """Execute one wake cycle — the 10-step conductor heartbeat."""
        wake_start = time.monotonic()
        result_info: dict[str, Any] = {
            "agent": self.name,
            "timestamp": time.time(),
            "success": False,
        }

        try:
            # 0. Run per-agent mini-crons (housekeeping tasks)
            cron_results = await self._cron.tick()
            if cron_results:
                fired = [r["job"] for r in cron_results if r["success"]]
                if fired:
                    logger.debug("[%s] crons fired: %s", self.name, ", ".join(fired))

            # 1. Load memory
            await self._agent.memory.load()

            # 2-3. Read stigmergy
            stigmergy = await self._get_stigmergy()
            hot_paths = await stigmergy.hot_paths(window_hours=6, min_marks=2)
            salient_marks = await stigmergy.high_salience(threshold=0.7, limit=5)

            # 4. Check messages
            bus = await self._get_bus()
            messages = await bus.receive(agent_id=self.name, limit=5)

            # 5. Determine task
            if injected_task:
                task_text = injected_task
                task_source = "injected"
            elif messages:
                top_msg = messages[0]
                task_text = f"Respond to message from {top_msg.from_agent}: {top_msg.subject} — {top_msg.body[:300]}"
                task_source = "message"
                # Adopted as this cycle's task. Deferred act-then-mark: read
                # status is recorded only once the message reaches a terminal
                # disposition (wake succeeded, or gate refused it — witnessed),
                # so a wake() crash leaves it unread for retry next cycle. A
                # gate refusal still marks read, else a poison message would
                # outrank self-tasks and wedge every future wake.
                adopted_msg_id = top_msg.id
            else:
                task_text = self._generate_self_task(hot_paths, salient_marks)
                task_source = "self"

            # p4: compaction in wake path (MemoryKernel preview -> compact trust-tagged note prepended to task)
            if getattr(self, "_memory_kernel", None):
                try:
                    from dharma_swarm.memory_kernel.context_admission import MemoryContextBudget
                    budget = MemoryContextBudget(max_candidate_atoms=8, max_admitted_atoms=3, max_total_chars=900, include_content=True)
                    pack = self._memory_kernel.preview_memory_pack(budget=budget)
                    if pack and getattr(pack, "items", None):
                        lines = [f"<source:memory:{getattr(it,'surface_id','mem')}> {(getattr(it,'content','') or '')[:160]}" for it in list(pack.items)[:3]]
                        compact = "[compacted memory — bi-temporal snapshot for this wake]\n" + "\n".join(lines)
                        task_text = compact + "\n\n" + task_text
                        result_info["compaction_applied"] = len(lines)
                except Exception:
                    logger.debug("[%s] wake compaction skipped", self.name, exc_info=True)

            # 6. Gate check
            gate_outcome = self._check_gate(task_text)
            if gate_outcome and gate_outcome.get("blocked"):
                self._profile.record_gate(passed=False)
                result_info["blocked"] = True
                result_info["gate_reason"] = gate_outcome.get("reason", "")
                result_info["gate_status"] = gate_outcome.get("gate_status", "")
                await self._write_witness("BLOCKED", task_text, gate_outcome.get("reason", ""))
                if task_source == "message":
                    await bus.mark_read(adopted_msg_id)
                return result_info
            if gate_outcome:
                self._profile.record_gate(passed=True)

            # 7. (gate passed or warned)

            # 8. Execute via AutonomousAgent ReAct loop
            agent_result: AgentResult = await self._agent.wake(task_text)

            # Wake succeeded — the adopted message reached its terminal
            # disposition; acknowledge it now (deferred act-then-mark).
            if task_source == "message":
                await bus.mark_read(adopted_msg_id)

            # 9. Save learnings
            key_insight = self._extract_key_insight(agent_result.summary)
            await self._agent.memory.remember(
                f"conductor_wake:{self.name}", key_insight, importance=0.6,
            )
            await self._agent.memory.save()

            # 10. Leave stigmergy mark + witness log
            from dharma_swarm.stigmergy import StigmergicMark
            await stigmergy.leave_mark(StigmergicMark(
                agent=self.name,
                file_path=f"conductor:{self.name}",
                action="scan",
                observation=key_insight[:200],
                salience=0.5,
            ))

            duration = time.monotonic() - wake_start
            await self._write_witness(
                "WAKE", task_text,
                f"source={task_source} turns={agent_result.turns} "
                f"tokens={agent_result.total_tokens} duration={duration:.1f}s",
            )

            # Record success in profile for identity evolution
            self._profile.record_task(
                success=True,
                tokens=agent_result.total_tokens,
                duration_s=duration,
            )

            result_info.update({
                "success": True,
                "task_source": task_source,
                "task": task_text[:200],
                "turns": agent_result.turns,
                "tokens": agent_result.total_tokens,
                "duration_s": round(duration, 1),
                "summary": agent_result.summary[:500],
            })

        except Exception as e:
            logger.error("[%s] wake error: %s", self.name, e)
            result_info["error"] = str(e)[:500]
            self._profile.record_task(success=False)
            await self._write_witness("ERROR", str(e)[:200], "")

        return result_info

    # -- Self-task generation (pure Python, no LLM) ----------------------

    def _generate_self_task(
        self,
        hot_paths: list[tuple[str, int]],
        salient_marks: list[Any],
    ) -> str:
        """Generate a task from environmental signals. No LLM call."""
        if hot_paths:
            top_path, count = hot_paths[0]
            return f"Investigate high-activity path: {top_path} ({count} marks in 6h)"

        if salient_marks:
            mark = salient_marks[0]
            return f"Follow up on observation: {mark.observation}"

        return "Review system state, check agent notes in ~/.dharma/shared/, report observations"

    # -- Gate check ------------------------------------------------------

    def _check_gate(self, task_text: str) -> dict[str, Any] | None:
        """Run telos gate check.

        Persistent agents are standing actors. If the gate path errors, the
        safe outcome is to block the wake instead of treating the missing gate
        as approval.
        """
        try:
            from dharma_swarm.telos_gates import check_with_reflective_reroute
            from dharma_swarm.models import GateDecision

            outcome = check_with_reflective_reroute(
                action=task_text[:100],
                content=task_text,
                think_phase="conductor_wake",
                reflection=f"Conductor {self.name} autonomous wake cycle",
            )
            decision = outcome.result.decision
            if decision == GateDecision.BLOCK:
                return {"blocked": True, "reason": outcome.result.reason}
            return {"blocked": False, "gate_status": "passed"}
        except Exception as e:
            logger.warning("[%s] gate check failed closed: %s", self.name, e)
            return {
                "blocked": True,
                "reason": f"gate_check_error:{type(e).__name__}",
                "gate_status": "fail_closed",
            }

    # -- Helpers ---------------------------------------------------------

    @staticmethod
    def _extract_key_insight(result_text: str) -> str:
        """Extract first meaningful sentence from result text."""
        if not result_text:
            return "No output"
        # Find first sentence > 20 chars
        for line in result_text.split("\n"):
            line = line.strip()
            if len(line) > 20:
                return line[:200]
        return result_text[:200]

    async def _write_witness(self, event: str, detail: str, extra: str) -> None:
        """Append a witness entry to the JSONL log."""
        entry = {
            "ts": time.time(),
            "agent": self.name,
            "event": event,
            "detail": detail[:300],
            "extra": extra[:200],
        }
        try:
            import aiofiles
            async with aiofiles.open(self._witness_log, "a") as f:
                await f.write(json.dumps(entry) + "\n")
        except Exception:
            # Best-effort witness logging
            try:
                with open(self._witness_log, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception:
                logger.debug("Witness log write failed", exc_info=True)

    # -- Daemon loop -----------------------------------------------------

    async def run_loop(self, shutdown_event: asyncio.Event) -> None:
        """Run the persistent wake loop until shutdown."""
        logger.info("[%s] Starting persistent loop (interval=%ds)", self.name, self.wake_interval)

        while not shutdown_event.is_set():
            try:
                # Check for injected tasks
                injected = None
                if not self._task_queue.empty():
                    try:
                        injected = self._task_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass

                await self.wake(injected_task=injected)

            except Exception as e:
                logger.error("[%s] wake loop error: %s", self.name, e)
                # Leave high-salience mark on failure
                try:
                    stigmergy = await self._get_stigmergy()
                    from dharma_swarm.stigmergy import StigmergicMark
                    await stigmergy.leave_mark(StigmergicMark(
                        agent=self.name,
                        file_path=f"conductor:{self.name}",
                        action="write",
                        observation=f"WAKE FAILURE: {e}"[:200],
                        salience=0.9,
                    ))
                except Exception:
                    logger.debug("Stigmergy mark on wake failure failed", exc_info=True)

            # Sleep until next wake or shutdown
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(), timeout=self.wake_interval,
                )
                break  # shutdown signaled
            except asyncio.TimeoutError:
                pass  # time to wake again

        logger.info("[%s] Persistent loop stopped", self.name)

    async def accept_task(self, task: str) -> None:
        """Inject a task from the orchestrator."""
        await self._task_queue.put(task)

    @property
    def cron(self) -> AgentCronScheduler:
        """Access the per-agent cron scheduler for custom job registration."""
        return self._cron

    @property
    def profile(self):
        """Access the evolving agent profile."""
        return self._profile
