"""Persistent autonomous agent with wake loop.

Composes AutonomousAgent — does NOT inherit or reinvent the ReAct loop.
Adds: autonomous wake scheduling, self-task generation, stigmergy/bus
reading, gate checks, witness logging, and per-agent mini-cron scheduling.

Used by conductor agents that run continuously alongside the orchestrator
or independently via launchd.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable

from dharma_swarm.autonomous_agent import AgentIdentity, AgentResult, AutonomousAgent
from dharma_swarm.models import AgentRole, ProviderType, TaskPriority, TaskStatus
from dharma_swarm.task_board_mirror import CanonicalTaskMirror, MirroredTaskSpec

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
    if provider_type == ProviderType.ANTHROPIC:
        return "anthropic"
    if provider_type == ProviderType.CLAUDE_CODE:
        return "openrouter"
    if provider_type == ProviderType.CODEX:
        return "codex"
    if provider_type in (ProviderType.OPENROUTER, ProviderType.OPENROUTER_FREE):
        return "openrouter"
    return "anthropic"


@dataclass(order=True)
class QueuedAttentionTask:
    """Priority-scored task injection for persistent agents."""

    priority_rank: int
    created_at: float = field(default_factory=time.monotonic)
    source: str = field(compare=False, default="injected")
    text: str = field(compare=False, default="")


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
    ) -> None:
        self.name = name
        self.role = role
        self.provider_type = provider_type
        self.model = model
        self.state_dir = state_dir or Path.home() / ".dharma"
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
        self._agent = AutonomousAgent(identity)

        # Lazy-init subsystems
        self._stigmergy: Any = None
        self._bus: Any = None

        # Orchestrator task injection
        self._task_queue: asyncio.PriorityQueue[QueuedAttentionTask] = asyncio.PriorityQueue()
        self._task_event = asyncio.Event()

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
        self._task_mirror = CanonicalTaskMirror(self.state_dir)

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

    async def _cron_consolidate_memory(self) -> str:
        """Demote old working memories to archival layer."""
        try:
            bank = self._agent.memory
            await bank.load()
            working = bank.working if hasattr(bank, "working") else []
            if len(working) > 8:
                # Demote oldest entries beyond capacity
                demoted = len(working) - 8
                await bank.save()
                return f"demoted={demoted}"
            return "nothing_to_demote"
        except Exception as exc:
            return f"error: {exc}"

    async def _cron_scan_stigmergy(self) -> str:
        """Scan for high-salience marks that might need attention."""
        try:
            stigmergy = await self._get_stigmergy()
            salient = await stigmergy.high_salience(threshold=0.8, limit=3)
            if salient:
                # Queue an investigation task if something urgent appeared
                mark = salient[0]
                await self._enqueue_attention_task(
                    f"Urgent stigmergy signal: {mark.observation[:150]}",
                    source="stigmergy",
                    priority_rank=3,
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
                await self._enqueue_attention_task(
                    f"Urgent message from {top.from_agent}: {top.subject}",
                    source="message",
                    priority_rank=1,
                )
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

    # -- Subsystem access (lazy init) ------------------------------------

    async def _get_stigmergy(self):
        if self._stigmergy is None:
            from dharma_swarm.stigmergy import StigmergyStore
            self._stigmergy = StigmergyStore()
        return self._stigmergy

    async def _get_bus(self):
        if self._bus is None:
            from dharma_swarm.message_bus import MessageBus
            db_path = Path.home() / ".dharma" / "db" / "messages.db"
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
        mirror_spec: MirroredTaskSpec | None = None

        try:
            # 0a. Load operator directives — the air traffic controller.
            # Read before everything else; directives override self-task gen.
            directives = None
            try:
                from dharma_swarm.operator_directives import load_directives
                directives = load_directives(self.state_dir)
            except Exception:
                pass

            # 0b. Run per-agent mini-crons (housekeeping tasks)
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
            active_campaign: dict[str, Any] | None = None
            if injected_task:
                task_text = injected_task
                task_source = "injected"
            elif messages:
                top_msg = messages[0]
                task_text = f"Respond to message from {top_msg.from_agent}: {top_msg.subject} — {top_msg.body[:300]}"
                task_source = "message"
            else:
                # Before falling through to self-generated work, check whether
                # this agent is pinned to an active campaign. Campaign pins
                # are first-class memory and keep the agent on a declared
                # track across wake cycles.
                active_campaign = self._check_pinned_campaign(directives=directives)
                if active_campaign is not None:
                    task_text = self._render_campaign_task(active_campaign)
                    task_source = "campaign"
                else:
                    task_text = self._generate_self_task(hot_paths, salient_marks)
                    task_source = "self"

            # 5b. Directive forbidden check + mission context injection.
            if directives is not None:
                from dharma_swarm.operator_directives import is_forbidden, mission_context_block
                if task_source in ("self", "campaign") and is_forbidden(task_text, directives):
                    logger.info(
                        "[%s] directive_redirect: forbidden task suppressed, "
                        "redirecting to DO item",
                        self.name,
                    )
                    if directives.do_items:
                        task_text = f"OPERATOR DIRECTIVE: {directives.do_items[0]}"
                    task_source = "directive"
                # Prepend mission context so the agent sees directives.
                ctx = mission_context_block(directives)
                if ctx:
                    task_text = f"{ctx}\n\n---\nTASK: {task_text}"

            mirror_spec = self._build_task_mirror_spec(
                task_source=task_source,
                task_text=task_text,
                active_campaign=active_campaign,
            )
            if mirror_spec is not None:
                await self._sync_task_mirror(mirror_spec)

            # 6. Gate check
            gate_outcome = self._check_gate(task_text)
            if gate_outcome and gate_outcome.get("blocked"):
                self._profile.record_gate(passed=False)
                result_info["blocked"] = True
                result_info["gate_reason"] = gate_outcome.get("reason", "")
                if mirror_spec is not None:
                    await self._sync_task_mirror(
                        self._replace_mirror_spec(
                            mirror_spec,
                            status=TaskStatus.FAILED,
                            result=gate_outcome.get("reason", ""),
                            metadata={"gate_blocked": True},
                        )
                    )
                await self._write_witness("BLOCKED", task_text, gate_outcome.get("reason", ""))
                return result_info
            if gate_outcome:
                self._profile.record_gate(passed=True)

            # 7. (gate passed or warned)

            # 8. Execute via AutonomousAgent ReAct loop
            agent_result: AgentResult = await self._agent.wake(task_text)

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
            if mirror_spec is not None:
                await self._sync_task_mirror(
                    self._replace_mirror_spec(
                        mirror_spec,
                        status=TaskStatus.COMPLETED,
                        result=self._mirror_result_summary(agent_result, duration),
                        metadata={
                            "turns": agent_result.turns,
                            "tokens": agent_result.total_tokens,
                            "duration_s": round(duration, 1),
                            "summary": agent_result.summary[:500],
                        },
                    )
                )

            # Campaign check-in — update durable campaign memory so the
            # executive's next cycle sees recent activity. Non-fatal on
            # failure; the task already completed.
            campaign_id_for_checkin = self._extract_campaign_for_checkin(
                task_source, task_text, active_campaign,
            )
            if campaign_id_for_checkin:
                try:
                    from dharma_swarm.campaigns import mark_check_in
                    mark_check_in(
                        campaign_id_for_checkin,
                        self.name,
                        note=self._summarize_for_checkin(agent_result, duration),
                    )
                except Exception as exc:
                    logger.warning(
                        "[%s] campaign check-in failed (%s): %s",
                        self.name, campaign_id_for_checkin, exc,
                    )

        except Exception as e:
            logger.error("[%s] wake error: %s", self.name, e)
            result_info["error"] = str(e)[:500]
            self._profile.record_task(success=False)
            if mirror_spec is not None:
                await self._sync_task_mirror(
                    self._replace_mirror_spec(
                        mirror_spec,
                        status=TaskStatus.FAILED,
                        result=str(e)[:500],
                        metadata={"error": str(e)[:500]},
                    )
                )
            await self._write_witness("ERROR", str(e)[:200], "")

        return result_info

    # -- Self-task generation (pure Python, no LLM) ----------------------

    def _generate_self_task(
        self,
        hot_paths: list[tuple[str, int]],
        salient_marks: list[Any],
    ) -> str:
        """Generate a task from environmental signals. No LLM call.

        Priority order (compression spec §185-206):
          1. Active primary campaign support — even if not personally pinned,
             non-lead agents bias toward the declared artifact.
          2. Unfulfilled heartbeat promises — from ``promise_pressure.json``.
          3. Stigmergy hot paths (demoted from #1).
          4. Salient marks (demoted).
          5. Generic system review.

        Silence-is-valid (V7 rule 4) still applies — but cannot justify chronic
        non-production when a primary campaign exists.
        """
        # 1. Primary campaign support (soft-primary today; Phase 4 tightens)
        try:
            from dharma_swarm.campaigns import active_primary
            primary = active_primary(meta_dir=self.state_dir / "meta")
        except Exception:
            primary = None
        if primary is not None:
            artifact = (
                primary.get("artifact_path")
                or primary.get("success_criteria")
                or primary.get("title", "?")
            )
            pinned = list(primary.get("pinned_agents") or [])
            role_hint = (
                "lead" if self.name in pinned and pinned[:1] == [self.name]
                else "support"
            )
            return (
                f"PRIMARY CAMPAIGN ({role_hint}): {primary.get('campaign_id', '?')} "
                f"— make measurable progress toward: {artifact}"
            )

        # 2. Unfulfilled heartbeat promises
        try:
            pp_path = self.state_dir / "meta" / "promise_pressure.json"
            if pp_path.exists():
                import json as _json
                pp = _json.loads(pp_path.read_text())
                promises = pp.get("promises") or []
                if promises:
                    top = promises[0]
                    text = str(top.get("text") or "").strip()
                    if text:
                        return f"UNFULFILLED PROMISE: {text[:280]}"
        except Exception as exc:
            logger.debug("[%s] promise_pressure read failed: %s", self.name, exc)

        # 3. Stigmergy hot paths (original behaviour, demoted)
        if hot_paths:
            top_path, count = hot_paths[0]
            return f"Investigate high-activity path: {top_path} ({count} marks in 6h)"

        # 4. Salient marks
        if salient_marks:
            mark = salient_marks[0]
            return f"Follow up on observation: {mark.observation}"

        # 5. Fallback
        return "Review system state, check agent notes in ~/.dharma/shared/, report observations"

    # -- Campaign pin integration ----------------------------------------

    def _check_pinned_campaign(self, directives: Any | None = None) -> dict[str, Any] | None:
        """Return the pinned campaign with the highest current attention debt.

        Read-only — write authority lives in ``dharma_swarm.campaigns``.
        Defensive: swallow any error and fall through to self-generation.
        """
        try:
            from dharma_swarm.campaigns import find_by_agent
            pins = find_by_agent(self.name, meta_dir=self.state_dir / "meta")
        except Exception as exc:
            logger.debug("[%s] campaign pin check failed: %s", self.name, exc)
            return None
        active = [c for c in pins if c.get("status", "active") == "active"]
        if not active:
            return None
        if len(active) == 1:
            return active[0]

        def _parse_timestamp(raw: Any) -> float:
            if not raw:
                return 0.0
            try:
                from datetime import datetime

                return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
            except Exception:
                return 0.0

        governance = None
        try:
            from dharma_swarm.governance_signal import load_governance

            governance = load_governance(meta_dir=self.state_dir / "meta")
        except Exception:
            governance = None

        now_ts = time.time()
        ages_hours: list[float] = []
        checkins: list[int] = []
        for campaign in active:
            anchor_ts = _parse_timestamp(
                campaign.get("last_check_in") or campaign.get("created"),
            )
            age_h = max(0.0, (now_ts - anchor_ts) / 3600.0) if anchor_ts else 0.0
            ages_hours.append(age_h)
            checkins.append(max(0, int(campaign.get("check_in_count", 0) or 0)))

        max_age = max(ages_hours) or 1.0
        max_checkins = max(checkins) if checkins else 0

        directive_text = ""
        if directives is not None:
            parts = [
                str(getattr(directives, "active_mission", "") or ""),
                *[str(x) for x in (getattr(directives, "do_items", []) or [])],
                *[str(x) for x in (getattr(directives, "context_lines", []) or [])],
            ]
            directive_text = " ".join(parts).lower()

        def _directive_match_bonus(campaign: dict[str, Any]) -> float:
            if not directive_text:
                return 0.0
            candidates = [
                str(campaign.get("campaign_id", "") or "").lower(),
                str(campaign.get("title", "") or "").lower(),
                str(campaign.get("domain", "") or "").lower(),
            ]
            for candidate in candidates:
                if candidate and len(candidate) >= 4 and candidate in directive_text:
                    return 0.5
            return 0.0

        best: dict[str, Any] | None = None
        best_score = float("-inf")
        for campaign, age_h, count in zip(active, ages_hours, checkins):
            campaign_id = str(campaign.get("campaign_id", "") or "")
            domain = str(campaign.get("domain", "") or "")

            stale_score = age_h / max_age if max_age > 0 else 0.0
            coverage_debt = 1.0 - (count / max_checkins) if max_checkins > 0 else 1.0
            score = (stale_score * 1.25) + (coverage_debt * 0.9)

            if campaign.get("primary") is True:
                score += 0.35

            if governance is not None:
                score += float(getattr(governance, "campaign_pressure", {}).get(campaign_id, 0.0) or 0.0) * 1.4
                if domain:
                    try:
                        domain_mult = governance.domain_weight(domain) / 0.125
                    except Exception:
                        domain_mult = 1.0
                    score += max(0.0, min(0.75, domain_mult - 1.0))
                    score += min(
                        0.6,
                        float(getattr(governance, "starvation_boosts", {}).get(domain, 0.0) or 0.0) * 2.0,
                    )

            score += _directive_match_bonus(campaign)

            if score > best_score:
                best = campaign
                best_score = score

        return best

    def _render_campaign_task(self, campaign: dict[str, Any]) -> str:
        campaign_id = campaign.get("campaign_id", "?")
        criteria = campaign.get("success_criteria") or campaign.get("title", "")
        markers = campaign.get("progress_markers") or []
        last_note = ""
        if markers:
            last = markers[-1]
            last_note = (last.get("note") or "")[:200]
        deadline = campaign.get("deadline")
        deadline_suffix = f" Deadline: {deadline}." if deadline else ""
        progress_suffix = f" Last progress: {last_note}" if last_note else ""
        return (
            f"CAMPAIGN: {campaign_id} — Make measurable progress on: "
            f"{criteria}.{deadline_suffix}{progress_suffix}"
        )

    @staticmethod
    def _extract_campaign_for_checkin(
        task_source: str,
        task_text: str,
        active_campaign: dict[str, Any] | None,
    ) -> str | None:
        if task_source == "campaign" and active_campaign:
            cid = active_campaign.get("campaign_id")
            return str(cid) if cid else None
        if task_source == "injected":
            # Inspect CAMPAIGN: <id> — prefix that the directive watcher
            # applies when a directive carries a campaign_id.
            import re as _re
            m = _re.match(r"CAMPAIGN:\s*([\w_\-]+)\s*—", task_text)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _summarize_for_checkin(agent_result: Any, duration_s: float) -> str:
        try:
            summary = (getattr(agent_result, "summary", "") or "")[:180]
            turns = getattr(agent_result, "turns", 0)
            return f"wake:{turns}t/{duration_s:.0f}s — {summary}"
        except Exception:
            return f"wake complete in {duration_s:.0f}s"

    def _build_task_mirror_spec(
        self,
        *,
        task_source: str,
        task_text: str,
        active_campaign: dict[str, Any] | None,
    ) -> MirroredTaskSpec | None:
        if task_source not in {"self", "campaign", "injected"}:
            return None

        digest = hashlib.sha1(f"{task_source}:{task_text}".encode("utf-8")).hexdigest()[:16]
        campaign_id = self._extract_campaign_for_checkin(task_source, task_text, active_campaign)
        metadata: dict[str, Any] = {
            "source": f"persistent_agent.{task_source}",
            "execution_substrate": "persistent_agent",
            "task_source": task_source,
            "agent_name": self.name,
            "agent_role": self.role.value,
            "provider": self.provider_type.value,
            "model": self.model,
            "task_text": task_text,
        }
        if campaign_id:
            metadata["campaign_id"] = campaign_id

        return MirroredTaskSpec(
            mirror_key=f"persistent_agent:{self.name}:{task_source}:{digest}",
            title=task_text[:240],
            description=(
                f"PersistentAgent {self.name} executing {task_source}-sourced work."
            ),
            priority=TaskPriority.HIGH if task_source in {"campaign", "injected"} else TaskPriority.NORMAL,
            created_by=self.name,
            assigned_to=self.name,
            status=TaskStatus.RUNNING,
            metadata=metadata,
        )

    @staticmethod
    def _replace_mirror_spec(
        spec: MirroredTaskSpec,
        *,
        status: TaskStatus,
        result: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MirroredTaskSpec:
        merged = dict(spec.metadata or {})
        if metadata:
            merged.update(metadata)
        return MirroredTaskSpec(
            mirror_key=spec.mirror_key,
            title=spec.title,
            description=spec.description,
            priority=spec.priority,
            created_by=spec.created_by,
            assigned_to=spec.assigned_to,
            status=status,
            result=result,
            metadata=merged,
        )

    @staticmethod
    def _mirror_result_summary(agent_result: Any, duration_s: float) -> str:
        summary = str(getattr(agent_result, "summary", "") or "").strip()
        compact = summary[:280] if summary else "wake complete"
        return f"{compact} (duration={duration_s:.1f}s)"

    async def _sync_task_mirror(self, spec: MirroredTaskSpec) -> None:
        try:
            await self._task_mirror.sync(spec)
        except Exception:
            logger.debug("[%s] task mirror failure", self.name, exc_info=True)

    async def _enqueue_attention_task(
        self,
        task_text: str,
        *,
        source: str,
        priority_rank: int,
    ) -> None:
        await self._task_queue.put(
            QueuedAttentionTask(
                priority_rank=priority_rank,
                source=source,
                text=task_text,
            )
        )
        self._task_event.set()

    # -- Gate check ------------------------------------------------------

    def _check_gate(self, task_text: str) -> dict[str, Any] | None:
        """Run telos gate check. Returns None if gates unavailable."""
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
            return {"blocked": False}
        except Exception as e:
            logger.debug("[%s] gate check skipped: %s", self.name, e)
            return None

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
        await self._write_witness("LOOP_START", f"interval={self.wake_interval}", "")

        while not shutdown_event.is_set():
            try:
                # Check for injected tasks
                injected = None
                if not self._task_queue.empty():
                    try:
                        queued = self._task_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    else:
                        injected = queued.text
                        if self._task_queue.empty():
                            self._task_event.clear()

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
                shutdown_task = asyncio.create_task(shutdown_event.wait())
                injected_task = asyncio.create_task(self._task_event.wait())
                done, pending = await asyncio.wait(
                    {shutdown_task, injected_task},
                    timeout=self.wake_interval,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                if shutdown_task in done and shutdown_event.is_set():
                    break  # shutdown signaled
                if injected_task in done and self._task_event.is_set():
                    continue  # wake immediately for injected work
            except asyncio.TimeoutError:
                pass  # time to wake again

        logger.info("[%s] Persistent loop stopped", self.name)
        await self._write_witness("LOOP_STOP", "", "")

    async def accept_task(self, task: str, *, priority_rank: int = 0) -> None:
        """Inject a task from the orchestrator."""
        await self._enqueue_attention_task(
            task,
            source="injected",
            priority_rank=priority_rank,
        )
        logger.info("[%s] Accepted injected task: %s", self.name, task[:160])
        await self._write_witness("TASK_ACCEPTED", task, "injected")

    @property
    def cron(self) -> AgentCronScheduler:
        """Access the per-agent cron scheduler for custom job registration."""
        return self._cron

    @property
    def profile(self):
        """Access the evolving agent profile."""
        return self._profile
