"""Swarm Manager — integrates agent pool, task board, message bus, and orchestrator.

Layer 4: The swarm lifecycle manager. Spawns agents, assigns tasks,
monitors health, and provides the unified API for the CLI and MCP server.

Now wired with Garden Daemon config (heartbeat, thread rotation, circuit
breakers, quality gates, human overrides) and v7 induction prompts.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field

from dharma_swarm.daemon_config import DaemonConfig, THREAD_PROMPTS
from dharma_swarm.contracts.intelligence_agents import (
    DEFAULT_TEAM_ID,
    resolve_team_id,
    sync_live_agent_registration,
    sync_live_agent_registrations,
)
from dharma_swarm.yoga_node import YogaScheduler
from dharma_swarm.jikoku_instrumentation import jikoku_auto_span
from dharma_swarm.models import (
    AgentConfig,
    AgentRole,
    AgentState,
    MemoryLayer,
    ProviderType,
    SwarmState,
    Task,
    TaskPriority,
    TaskStatus,
)
from dharma_swarm.providers import create_default_router
from dharma_swarm.swarm_tick_effects import run_tick_effects

if TYPE_CHECKING:
    from dharma_swarm.adaptive_autonomy import AdaptiveAutonomy
    from dharma_swarm.agent_memory import AgentMemoryBank
    from dharma_swarm.agent_runner import AgentPool
    from dharma_swarm.auto_proposer import AutoProposer
    from dharma_swarm.canary import CanaryDeployer
    from dharma_swarm.context_search import ContextSearchEngine
    from dharma_swarm.dharma_corpus import DharmaCorpus
    from dharma_swarm.dharma_kernel import KernelGuard
    from dharma_swarm.engine.event_memory import EventMemoryStore
    from dharma_swarm.evolution import DarwinEngine
    from dharma_swarm.graph.reconciler import GraphReconciler, ReconcileReport
    from dharma_swarm.handoff import HandoffProtocol
    from dharma_swarm.intent_router import IntentRouter
    from dharma_swarm.memory import StrangeLoopMemory
    from dharma_swarm.message_bus import MessageBus
    from dharma_swarm.monitor import SystemMonitor
    from dharma_swarm.orchestrator import Orchestrator
    from dharma_swarm.policy_compiler import PolicyCompiler
    from dharma_swarm.profiles import ProfileManager
    from dharma_swarm.skill_composer import SkillComposer
    from dharma_swarm.skills import SkillRegistry
    from dharma_swarm.stigmergy import StigmergyStore
    from dharma_swarm.task_board import TaskBoard
    from dharma_swarm.telemetry_plane import TelemetryPlaneStore
    from dharma_swarm.thinkodynamic_director import ThinkodynamicDirector
    from dharma_swarm.thread_manager import ThreadManager
    from dharma_swarm.traces import TraceStore
    from dharma_swarm.organism import OrganismRuntime
    from dharma_swarm.witness import WitnessAuditor

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


class SubsystemNotReady(RuntimeError):
    """Raised when a required subsystem hasn't been initialized yet.

    Ashby's requisite variety: type system variety must match runtime variety.
    """


def _make_trace_id() -> str:
    return f"trc_{uuid4().hex}"


class SwarmCoordinationState(BaseModel):
    """Compact runtime summary of sheaf-based swarm coordination."""

    observed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent_count: int = 0
    message_count: int = 0
    task_count: int = 0
    overlap_pairs: int = 0
    published_agents: list[str] = Field(default_factory=list)
    global_truths: int = 0
    productive_disagreements: int = 0
    cohomological_dimension: int = 0
    is_globally_coherent: bool = True
    global_truth_claim_keys: list[str] = Field(default_factory=list)
    productive_disagreement_claim_keys: list[str] = Field(default_factory=list)


class SwarmManager:
    """Top-level swarm coordinator.

    Integrates: agent pool, task board, message bus, memory, orchestrator,
    telos gates, ecosystem bridge, daemon config, and thread manager.
    """

    def __init__(
        self,
        state_dir: Path | str = ".dharma",
        daemon_config: DaemonConfig | None = None,
    ):
        self.state_dir = Path(state_dir)
        self._start_time = time.monotonic()
        self._running = False
        self._daemon = daemon_config or DaemonConfig()

        # ── Subsystem declarations (typed, not Any) ──
        # CRITICAL: must init or swarm cannot operate
        self._task_board: TaskBoard | None = None
        self._agent_pool: AgentPool | None = None
        self._message_bus: MessageBus | None = None
        self._orchestrator: Orchestrator | None = None
        self._gatekeeper: Any = None  # TelosGatekeeper (no stable type yet)

        # CRITICAL: core infrastructure
        self._memory: StrangeLoopMemory | None = None
        self._event_memory: EventMemoryStore | None = None
        self._telemetry: TelemetryPlaneStore | None = None
        self._thread_mgr: ThreadManager | None = None
        self._router = create_default_router()

        # v0.2.0 subsystems (CRITICAL: evolution + monitoring)
        self._engine: DarwinEngine | None = None
        self._meta_engine: Any = None
        self._monitor: SystemMonitor | None = None
        self._trace_store: TraceStore | None = None

        # v0.3.0: Gödel Claw (CRITICAL: kernel + corpus)
        self._kernel_guard: KernelGuard | None = None
        self._corpus: DharmaCorpus | None = None
        self._compiler: PolicyCompiler | None = None
        self._canary: CanaryDeployer | None = None
        self._bridge_rv: Any = None  # ResearchBridge (optional)
        self._stigmergy: StigmergyStore | None = None

        # v0.4.0: Oz-inspired (OPTIONAL: can fail gracefully)
        self._skill_registry: SkillRegistry | None = None
        self._profile_mgr: ProfileManager | None = None
        self._intent_router: IntentRouter | None = None
        self._context_search: ContextSearchEngine | None = None
        self._autonomy: AdaptiveAutonomy | None = None
        self._skill_composer: SkillComposer | None = None
        self._handoff: HandoffProtocol | None = None
        self._agent_memories: dict[str, AgentMemoryBank] = {}
        self._agent_configs: dict[str, AgentConfig] = {}
        self._worker_spawners: dict[str, Any] = {}  # name → WorkerSpawner

        # v0.5.0: Thinkodynamic Director (OPTIONAL)
        self._director: ThinkodynamicDirector | None = None
        self._tick_count: int = 0

        # v0.7.0: Organism brain — Gnani/Samvara wired into the heartbeat
        self._organism: OrganismRuntime | None = None
        self._organism_interval_ticks: int = 4  # heartbeat every ~2 min (4 × 30s)

        # v0.8.0: Witness (S3* sporadic audit) — Beer VSM gap #2
        self._witness: WitnessAuditor | None = None
        self._witness_interval_ticks: int = 120  # audit every ~60 min (120 × 30s)

        # v0.9.0: Decision Ontology — structured decision governance
        self._decision_log: Any = None  # DecisionLog

        # v1.0: Fractal Room Registry — rooms govern work
        self._room_registry: Any = None  # RoomRegistry

        # v0.9.3: AutoProposer — closes the autonomy loop
        self._auto_proposer: AutoProposer | None = None
        self._auto_proposer_interval_ticks: int = 60  # every ~30 min (60 × 30s)

        # Central config (Beer's S5 — identity at the parameter level)
        from dharma_swarm.config import DEFAULT_CONFIG
        self._config = DEFAULT_CONFIG
        _sm = self._config.swarm
        self._director_interval_ticks: int = _sm.director_interval_ticks
        self._living_interval_ticks: int = _sm.living_interval_ticks

        # v0.6.0: Hermes-inspired integration (OPTIONAL)
        self._tool_registry: Any = None    # ToolRegistry
        self._cron_scheduler: Any = None   # module ref
        self._gateway: Any = None          # GatewayRunner

        # Subsystem initialization tracking
        self._initialized: set[str] = set()
        self._startup_background_task: asyncio.Task[None] | None = None
        self._startup_backfill_lock = asyncio.Lock()
        self._startup_backfill_pending_components: set[str] = set()
        self._startup_backfill_last_error: str | None = None
        self._optional_startup_retry_task: asyncio.Task[None] | None = None
        self._optional_startup_last_error: str | None = None
        self._optional_startup_retry_not_before = 0.0
        self._optional_startup_retry_interval_seconds = 30.0
        self._optional_startup_retry_timeout_seconds = 30.0
        self._effect_tick_lock = asyncio.Lock()
        self._shutdown_started = False
        self._shutdown_complete = False
        self._telos_substrate_seeded = (
            self.state_dir / "meta" / "telos_seeded"
        ).exists()
        self._fast_boot = str(os.environ.get("DHARMA_FAST_BOOT", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._read_only_boot = str(
            os.environ.get("DHARMA_READ_ONLY_BOOT", "")
        ).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        # Daemon state
        self._last_contribution: datetime | None = None
        self._daily_contributions: int = 0
        self._daily_reset: datetime | None = None
        self._last_auto_rescue_scan: datetime | None = None
        self._graph_reconciler: GraphReconciler | None = None
        self._last_boot_reconcile_error: str | None = None
        self._auto_rescue_scan_interval_seconds = _sm.auto_rescue_scan_interval_seconds
        self._auto_rescue_max_age = timedelta(hours=_sm.auto_rescue_max_age_hours)
        self._auto_rescue_max_attempts = _sm.auto_rescue_max_attempts

        # Auto-evolution wiring (stagnation-triggered Darwin Engine cycles)
        self._evolution_interval_ticks: int = 120  # every ~60 min (120 × 30s)
        self._evolution_tick_counter: int = 0
        self._fitness_history: list[float] = []
        self._max_auto_evolves_per_day: int = 6
        self._auto_evolves_today: int = 0
        self._auto_evolve_day: str | None = None
        self._stagnation_threshold: float = 0.01
        self._stagnation_window: int = 60
        self._auto_evolution_enabled: bool = True

    # ── Subsystem access helpers ──

    # Subsystems classified by criticality
    _CRITICAL_SUBSYSTEMS = frozenset({
        "task_board", "agent_pool", "orchestrator", "gatekeeper",
    })
    _OPTIONAL_SUBSYSTEMS = frozenset({
        "stigmergy", "bridge_rv", "director", "skill_registry",
        "profile_mgr", "intent_router", "context_search", "autonomy",
        "skill_composer", "handoff", "tool_registry", "cron_scheduler",
        "gateway", "decision_log",
    })

    def _require_subsystem(self, name: str) -> Any:
        """Return a subsystem or raise SubsystemNotReady.

        Ashby: the check variety must match the failure variety.
        """
        attr = f"_{name}"
        value = getattr(self, attr, None)
        if value is None:
            raise SubsystemNotReady(
                f"Subsystem {name!r} not initialized. "
                f"Call init() first or check is_ready({name!r})."
            )
        return value

    def is_ready(self, subsystem_name: str) -> bool:
        """Check if a subsystem has been initialized."""
        return getattr(self, f"_{subsystem_name}", None) is not None

    def _refresh_initialized_registry(self) -> None:
        """Refresh the initialized subsystem ledger from current attributes."""
        self._initialized.clear()
        for name, attr in [
            ("task_board", self._task_board),
            ("agent_pool", self._agent_pool),
            ("message_bus", self._message_bus),
            ("orchestrator", self._orchestrator),
            ("gatekeeper", self._gatekeeper),
            ("memory", self._memory),
            ("event_memory", self._event_memory),
            ("engine", self._engine),
            ("monitor", self._monitor),
            ("kernel_guard", self._kernel_guard),
            ("corpus", self._corpus),
            ("stigmergy", self._stigmergy),
            ("skill_registry", self._skill_registry),
            ("director", self._director),
            ("organism", self._organism),
            ("witness", self._witness),
            ("decision_log", self._decision_log),
            ("tool_registry", self._tool_registry),
            ("cron_scheduler", self._cron_scheduler),
            ("gateway", self._gateway),
            ("bridge_rv", self._bridge_rv),
        ]:
            if attr is not None:
                self._initialized.add(name)

        logger.info(
            "Subsystems initialized: %d/%d critical, %d optional",
            len(self._initialized & self._CRITICAL_SUBSYSTEMS),
            len(self._CRITICAL_SUBSYSTEMS),
            len(self._initialized - self._CRITICAL_SUBSYSTEMS),
        )

    def _missing_optional_subsystems(self) -> list[str]:
        """Return optional components that have not published a live object."""
        return sorted(
            name for name in self._OPTIONAL_SUBSYSTEMS if not self.is_ready(name)
        )

    async def _init_optional_director(self) -> None:
        """Publish the director only after its asynchronous init succeeds."""
        from dharma_swarm.thinkodynamic_director import ThinkodynamicDirector

        director = ThinkodynamicDirector(state_dir=self.state_dir, swarm=self)
        await director.init()
        if self._shutdown_started:
            stop = getattr(director, "stop", None)
            if callable(stop):
                stopped = stop()
                if asyncio.iscoroutine(stopped):
                    await stopped
            raise asyncio.CancelledError
        self._director = director

    async def _init_optional_subsystems(self) -> None:
        """Initialize noncritical subsystems after the core runtime is live."""
        # v0.2.0: Darwin Engine + System Monitor
        from dharma_swarm.evolution import DarwinEngine
        from dharma_swarm.monitor import SystemMonitor
        from dharma_swarm.traces import TraceStore

        evo_dir = self.state_dir / "evolution"
        traces_dir = self.state_dir / "traces"

        # Build the connected evolution bundle off-object.  No caller may see
        # a TraceStore or DarwinEngine until every awaited init succeeds, and
        # retries must not replace an engine still referenced by MetaEngine or
        # AutoProposer.
        if self._trace_store is None or self._engine is None:
            trace_store = TraceStore(base_path=traces_dir)
            await trace_store.init()
            engine = DarwinEngine(
                archive_path=evo_dir / "archive.jsonl",
                traces_path=traces_dir,
                predictor_path=evo_dir / "predictor_data.jsonl",
            )
            await engine.init()
            if self._shutdown_started:
                raise asyncio.CancelledError

            # v0.9.2: Meta-evolution engine — adapts DarwinEngine parameters.
            from dharma_swarm.meta_evolution import MetaEvolutionEngine

            meta_engine = MetaEvolutionEngine(
                engine,
                meta_archive_path=evo_dir / "meta_archive.jsonl",
                n_object_cycles_per_meta=2,
                auto_apply=True,
            )
            monitor = SystemMonitor(trace_store=trace_store)
            self._trace_store = trace_store
            self._engine = engine
            self._meta_engine = meta_engine
            self._monitor = monitor

        # v0.3.0: Gödel Claw — Dharma Kernel, Corpus, Policy, Canary, Stigmergy
        from dharma_swarm.dharma_kernel import KernelGuard
        from dharma_swarm.dharma_corpus import DharmaCorpus
        from dharma_swarm.policy_compiler import PolicyCompiler
        from dharma_swarm.canary import CanaryDeployer

        kernel_path = self.state_dir / "kernel.json"
        corpus_path = self.state_dir / "corpus.jsonl"

        if self._kernel_guard is None:
            kernel_guard = KernelGuard(kernel_path=kernel_path)
            try:
                await kernel_guard.load()
            except (FileNotFoundError, ValueError):
                from dharma_swarm.dharma_kernel import DharmaKernel

                default = DharmaKernel.create_default()
                await kernel_guard.save(default)
            if self._shutdown_started:
                raise asyncio.CancelledError
            self._kernel_guard = kernel_guard

        if self._corpus is None:
            corpus = DharmaCorpus(path=corpus_path)
            await corpus.load()
            if self._shutdown_started:
                raise asyncio.CancelledError
            self._corpus = corpus

        if self._compiler is None:
            self._compiler = PolicyCompiler()
        if self._canary is None:
            self._canary = CanaryDeployer(archive=self._engine.archive)

        try:
            from dharma_swarm.stigmergy import StigmergyStore

            if self._stigmergy is None:
                stigmergy_path = self.state_dir / "stigmergy"
                self._stigmergy = StigmergyStore(base_path=stigmergy_path)
        except ImportError:
            self._stigmergy = None
            logger.debug("Stigmergy module not available yet")

        logger.info("Gödel Claw v1 subsystems initialized")

        # v0.9.3: AutoProposer — closes the autonomy loop
        try:
            from dharma_swarm.auto_proposer import AutoProposer

            if self._auto_proposer is None:
                self._auto_proposer = AutoProposer(
                    darwin_engine=self._engine,
                    system_monitor=self._monitor,
                    fitness_predictor=self._engine.predictor,
                    stigmergy=self._stigmergy,
                    log_dir=self.state_dir / "auto_proposer",
                )
            logger.info("AutoProposer initialized — autonomy loop closed")
        except Exception as exc:
            logger.debug("AutoProposer init failed (non-fatal): %s", exc)

        # v0.4.0: Oz-inspired systems
        try:
            from dharma_swarm.skills import SkillRegistry
            from dharma_swarm.profiles import ProfileManager
            from dharma_swarm.intent_router import IntentRouter
            from dharma_swarm.context_search import ContextSearchEngine
            from dharma_swarm.adaptive_autonomy import AdaptiveAutonomy

            self._skill_registry = SkillRegistry()
            self._skill_registry.discover()

            profiles_dir = self.state_dir / "profiles"
            self._profile_mgr = ProfileManager(profile_dir=profiles_dir)
            self._profile_mgr.load_all()

            self._intent_router = IntentRouter(registry=self._skill_registry)

            self._context_search = ContextSearchEngine()
            self._context_search.build_index()

            self._autonomy = AdaptiveAutonomy(base_level="balanced")

            from dharma_swarm.skill_composer import SkillComposer
            from dharma_swarm.handoff import HandoffProtocol

            self._skill_composer = SkillComposer(
                registry=self._skill_registry,
                router=self._intent_router,
            )
            self._handoff = HandoffProtocol(
                store_path=self.state_dir / "handoffs.jsonl",
            )

            logger.info("v0.4.0+ Oz-inspired systems initialized")
        except Exception as e:
            logger.warning("v0.4.0 systems init failed (non-fatal): %s", e)

        # v0.5.0: Thinkodynamic Director
        if self._director is None:
            try:
                await self._init_optional_director()
                logger.info("ThinkodynamicDirector initialized")
            except Exception as e:
                self._director = None
                logger.warning("ThinkodynamicDirector init failed (non-fatal): %s", e)

        # v0.7.0: OrganismRuntime
        if self._organism is None:
            try:
                from dharma_swarm.organism import OrganismRuntime

                self._organism = OrganismRuntime(
                    state_dir=self.state_dir,
                    on_algedonic=self._algedonic_handler,
                )
                logger.info("OrganismRuntime initialized — Gnani/Samvara/Algedonic active")
            except Exception as e:
                logger.warning("OrganismRuntime init failed (non-fatal): %s", e)

        # v0.8.0: Witness auditor
        try:
            from dharma_swarm.witness import WitnessAuditor

            # Use a cost-controlled free provider for witness audits instead
            # of the full ModelRouter which may route to expensive models.
            try:
                from dharma_swarm.providers import OpenRouterFreeProvider
                _witness_provider = OpenRouterFreeProvider()
            except Exception:
                _witness_provider = None
            if self._witness is None:
                self._witness = WitnessAuditor(
                    cycle_seconds=3600.0,
                    provider=_witness_provider,
                )
            logger.info("WitnessAuditor initialized — S3* sporadic audit active")
        except Exception as e:
            logger.warning("WitnessAuditor init failed (non-fatal): %s", e)

        # v0.9.0: Decision Ontology
        try:
            from dharma_swarm.decision_ontology import DecisionLog

            if self._decision_log is None:
                self._decision_log = DecisionLog(
                    path=self.state_dir / "meta" / "decisions.jsonl",
                )
            logger.info("DecisionLog initialized — structured decision governance active")
        except Exception as e:
            logger.warning("DecisionLog init failed (non-fatal): %s", e)

        # v0.6.0: Hermes-inspired integration
        try:
            from dharma_swarm.tool_registry import ToolRegistry

            if self._tool_registry is None:
                self._tool_registry = ToolRegistry()
            logger.info("ToolRegistry initialized")
        except Exception as e:
            logger.warning("ToolRegistry init failed (non-fatal): %s", e)

        try:
            from dharma_swarm import cron_scheduler as _cron_mod

            if self._cron_scheduler is None:
                self._cron_scheduler = _cron_mod
            logger.info("CronScheduler module loaded")
        except Exception as e:
            logger.warning("CronScheduler import failed (non-fatal): %s", e)

        try:
            from dharma_swarm.gateway import GatewayRunner

            if self._gateway is None:
                self._gateway = GatewayRunner(message_handler=None)
            logger.info("GatewayRunner initialized (call gateway.start() to activate adapters)")
        except Exception as e:
            logger.warning("GatewayRunner init failed (non-fatal): %s", e)

        try:
            from dharma_swarm.bridge import ResearchBridge

            if self._bridge_rv is None:
                bridge_path = self.state_dir / "bridge_measurements.jsonl"
                self._bridge_rv = ResearchBridge(data_path=bridge_path)
            logger.info("ResearchBridge initialized")
        except Exception as e:
            logger.warning("ResearchBridge init failed (non-fatal): %s", e)

        # Wire 1: Connect KnowledgeStore to evolution fitness + context compilation.
        # Closes Loops 9 (Memory→Metabolism) and 2 (Evolution→Agent Improvement).
        # These setters already exist but were never called.
        try:
            from dharma_swarm.engine.knowledge_store import create_knowledge_store
            _ks = create_knowledge_store(prefer_qdrant=False)
            if self._engine is not None:
                self._engine.set_knowledge_store(_ks)
            logger.info("KnowledgeStore wired to DarwinEngine")
        except Exception as e:
            logger.debug("KnowledgeStore wiring failed (non-fatal): %s", e)

        self._telos_substrate_seeded = (
            self.state_dir / "meta" / "telos_seeded"
        ).exists()
        self._refresh_initialized_registry()
        missing_optional = self._missing_optional_subsystems()
        if missing_optional:
            raise SubsystemNotReady(
                "Optional subsystem initialization remains incomplete: "
                + ", ".join(missing_optional)
            )

    async def _refresh_startup_graph_census(self, *, phase: str) -> bool:
        """Earn fresh Graph authority immediately before startup effects."""
        graph_reconciler = self._get_graph_reconciler()
        graph_reconciler.invalidate_boot_census()
        try:
            await asyncio.wait_for(
                self.reconcile_graph_runs(
                    stale_only=graph_reconciler.boot_recovery_completed
                ),
                timeout=10.0,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            graph_reconciler.invalidate_boot_census()
            self._startup_backfill_last_error = (
                f"{phase}: {type(exc).__name__}: {exc}"
            )
            logger.warning(
                "%s Graph census failed safely: %s",
                phase,
                self._startup_backfill_last_error,
            )
            return False
        return bool(graph_reconciler.boot_census_succeeded)

    async def _complete_deferred_startup(self) -> None:
        """Backfill the default crew and optional subsystems after fast boot."""
        try:
            # Critical backfill may write the TaskBoard. Serialize it with
            # effect-bearing ticks so a tick cannot enter the Board→runtime
            # heartbeat fence while fast-boot startup holds a Board writer.
            # Optional initialization is deliberately scheduled only after
            # releasing this mutex: it is noncritical and must not stall core
            # dispatch when it is slow or permanently unavailable.
            async with self._effect_tick_lock:
                if self._shutdown_started:
                    return
                graph_ready = await self._refresh_startup_graph_census(
                    phase="deferred_startup"
                )
                report = (
                    await self._backfill_graph_held_startup()
                    if graph_ready
                    else {
                        "attempted": [],
                        "completed": [],
                        "created": {},
                        "pending": sorted(
                            self._critical_startup_pending_components()
                        ),
                        "hold": "graph_census_not_succeeded",
                    }
                )
                default_count = int(
                    report.get("created", {}).get("default_crew", 0)
                )
                graph_ready = self._get_graph_reconciler().boot_census_succeeded
            if default_count:
                logger.info(
                    "Deferred startup spawned %d agents from default crew",
                    default_count,
                )
            optional_scheduled = self._schedule_optional_startup_retry(
                graph_ready=graph_ready
            )
            if self._memory is not None:
                await self._memory.remember(
                    "Swarm fast-boot backfill complete — "
                    f"{default_count} default agents added; "
                    f"critical_pending={report.get('pending', [])}; "
                    f"optional_scheduled={optional_scheduled}",
                    layer=MemoryLayer.SESSION,
                    source="swarm",
                )
            if report.get("pending"):
                logger.warning(
                    "Deferred startup remains safely pending: %s",
                    report["pending"],
                )
            else:
                logger.info("Deferred startup bootstrap complete")
        except asyncio.CancelledError:
            logger.info("Deferred startup bootstrap cancelled")
            raise
        except Exception as exc:
            logger.exception("Deferred startup bootstrap failed: %s", exc)

    async def _seed_boot_telos_substrate(self) -> Any:
        """Idempotently seed Telos after Graph authority is known green."""
        seed_flag = self.state_dir / "meta" / "telos_seeded"
        if seed_flag.exists():
            self._telos_substrate_seeded = True
            logger.info("TelosSubstrate already seeded (flag: %s)", seed_flag)
            return {"skipped": "already_seeded"}

        from dharma_swarm.telos_substrate import TelosSubstrate

        substrate = TelosSubstrate(state_dir=self.state_dir)
        seed_result = await substrate.seed_all()
        seed_flag.parent.mkdir(parents=True, exist_ok=True)
        seed_flag.write_text(f"seeded: {seed_result}\n", encoding="utf-8")
        self._telos_substrate_seeded = True
        logger.info("TelosSubstrate seeded after Graph census: %s", seed_result)
        return seed_result

    async def _seed_boot_gnani_lodestone(self) -> Any:
        """Idempotently seed Gnani tasks after Graph authority is green."""
        seed_flag = self.state_dir / "meta" / "gnani_seeded"
        if seed_flag.exists():
            logger.info("GnaniLodestone already seeded (flag: %s)", seed_flag)
            return {"skipped": "already_seeded"}

        from dharma_swarm.gnani_lodestone import GnaniLodestone

        lodestone = GnaniLodestone(state_dir=self.state_dir)
        seed_result = await lodestone.seed_all()
        seed_flag.parent.mkdir(parents=True, exist_ok=True)
        seed_flag.write_text(f"seeded: {seed_result}\n", encoding="utf-8")
        logger.info("GnaniLodestone seeded after Graph census: %s", seed_result)
        return seed_result

    def _critical_startup_pending_components(self) -> set[str]:
        """Return startup effects that must complete before core dispatch."""
        return self._startup_backfill_pending_components - {
            "optional_subsystems"
        }

    async def _retry_optional_startup_once(self) -> None:
        """Run one bounded optional retry behind fresh Graph authority."""
        if (
            self._shutdown_started
            or "optional_subsystems"
            not in self._startup_backfill_pending_components
        ):
            return

        timeout = self._optional_startup_retry_timeout_seconds
        try:
            # Optional initialization includes persistent stores and Director
            # startup, so it is an effect-bearing phase.  Serialize it with
            # ticks and earn a new census immediately before those effects.
            async with self._effect_tick_lock:
                if self._shutdown_started:
                    return
                graph_ready = await self._refresh_startup_graph_census(
                    phase="optional_startup"
                )
                if not graph_ready:
                    self._optional_startup_last_error = (
                        "optional_subsystems: graph census not succeeded"
                    )
                    return
                await asyncio.wait_for(
                    self._init_optional_subsystems(), timeout=timeout
                )
                if self._shutdown_started:
                    raise asyncio.CancelledError
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            self._optional_startup_last_error = (
                "optional_subsystems: TimeoutError: "
                f"exceeded {timeout:g}s"
            )
            logger.warning(
                "Optional startup retry failed safely: %s",
                self._optional_startup_last_error,
            )
        except Exception as exc:
            self._optional_startup_last_error = (
                f"optional_subsystems: {type(exc).__name__}: {exc}"
            )
            logger.warning(
                "Optional startup retry failed safely: %s",
                self._optional_startup_last_error,
            )
        else:
            missing_optional = self._missing_optional_subsystems()
            if missing_optional:
                self._optional_startup_last_error = (
                    "optional_subsystems: SubsystemNotReady: "
                    + ", ".join(missing_optional)
                )
                logger.warning(
                    "Optional startup retry remains pending: %s",
                    self._optional_startup_last_error,
                )
            else:
                self._startup_backfill_pending_components.discard(
                    "optional_subsystems"
                )
                self._optional_startup_last_error = None
                logger.info("Optional startup retry completed")
        finally:
            loop = asyncio.get_running_loop()
            self._optional_startup_retry_not_before = (
                loop.time() + self._optional_startup_retry_interval_seconds
            )

    def _schedule_optional_startup_retry(self, *, graph_ready: bool) -> bool:
        """Schedule one optional retry without blocking an effect-bearing tick."""
        if (
            self._shutdown_started
            or not graph_ready
            or self._critical_startup_pending_components()
            or "optional_subsystems"
            not in self._startup_backfill_pending_components
        ):
            return False
        current = self._optional_startup_retry_task
        if current is not None and not current.done():
            return False
        if (
            asyncio.get_running_loop().time()
            < self._optional_startup_retry_not_before
        ):
            return False
        self._optional_startup_retry_task = asyncio.create_task(
            self._retry_optional_startup_once()
        )
        return True

    async def _backfill_graph_held_startup(self) -> dict[str, Any]:
        """Retry held startup effects once Graph has a fresh green census.

        Each component is idempotent and removed from the pending set only
        after it returns successfully. The lock prevents concurrent ticks from
        duplicating work; failed or timed-out components remain pending.
        """
        report: dict[str, Any] = {
            "attempted": [],
            "completed": [],
            "created": {},
            "pending": sorted(self._critical_startup_pending_components()),
        }
        if not self._critical_startup_pending_components():
            return report

        async with self._startup_backfill_lock:
            if not self._critical_startup_pending_components():
                report["pending"] = []
                return report

            graph_reconciler = self._get_graph_reconciler()
            if not graph_reconciler.boot_census_succeeded:
                report["hold"] = "graph_census_not_succeeded"
                return report

            from dharma_swarm.startup_crew import (
                create_seed_tasks,
                spawn_cybernetics_crew,
                spawn_default_crew,
            )

            components = (
                ("telos_substrate", 120.0, self._seed_boot_telos_substrate),
                ("gnani_lodestone", 60.0, self._seed_boot_gnani_lodestone),
                ("cybernetics_crew", 30.0, lambda: spawn_cybernetics_crew(self)),
                ("seed_tasks", 30.0, lambda: create_seed_tasks(self)),
                ("default_crew", 30.0, lambda: spawn_default_crew(self)),
            )
            for component, timeout, operation in components:
                if component not in self._startup_backfill_pending_components:
                    continue
                if not graph_reconciler.boot_census_succeeded:
                    report["hold"] = "graph_census_not_succeeded"
                    break

                report["attempted"].append(component)
                try:
                    value = await asyncio.wait_for(operation(), timeout=timeout)
                except asyncio.TimeoutError:
                    error = (
                        f"{component}: TimeoutError: exceeded {timeout:.0f}s"
                    )
                    self._startup_backfill_last_error = error
                    report["error"] = error
                    logger.warning("Startup backfill failed safely: %s", error)
                    break
                except Exception as exc:
                    error = f"{component}: {type(exc).__name__}: {exc}"
                    self._startup_backfill_last_error = error
                    report["error"] = error
                    logger.warning("Startup backfill failed safely: %s", error)
                    break

                self._startup_backfill_pending_components.discard(component)
                self._startup_backfill_last_error = None
                report["completed"].append(component)
                if isinstance(value, list):
                    report["created"][component] = len(value)

            report["pending"] = sorted(
                self._critical_startup_pending_components()
            )
            if not self._critical_startup_pending_components():
                self._startup_backfill_last_error = None
            elif "error" not in report and self._startup_backfill_last_error:
                report["error"] = self._startup_backfill_last_error
            return report

    async def init(self) -> None:
        """Initialize all subsystems."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Clear stale EMERGENCY_HOLD from previous crashed/cold-start sessions.
        # On a fresh system with no task history, the organism fires critical
        # because blended coherence is 0.0 — that's expected cold-start, not
        # an emergency. The organism.py fix (requiring _has_history) prevents
        # NEW false holds, but old hold files persist across restarts.
        _hold = self.state_dir / "EMERGENCY_HOLD"
        if _hold.exists():
            try:
                logger.info("Clearing stale EMERGENCY_HOLD from previous session")
                _hold.unlink()
            except OSError:
                pass

        from dharma_swarm.agent_constitution import bootstrap_dynamic_roster

        from dharma_swarm.agent_runner import AgentPool
        from dharma_swarm.engine.event_memory import EventMemoryStore
        from dharma_swarm.memory import StrangeLoopMemory
        from dharma_swarm.message_bus import MessageBus
        from dharma_swarm.orchestrator import Orchestrator
        from dharma_swarm.task_board import TaskBoard
        from dharma_swarm.telemetry_plane import TelemetryPlaneStore
        from dharma_swarm.telos_gates import DEFAULT_GATEKEEPER
        from dharma_swarm.thread_manager import ThreadManager

        db_dir = self.state_dir / "db"
        db_dir.mkdir(exist_ok=True)
        state_runtime_db = self.state_dir / "state" / "runtime.db"

        self._task_board = TaskBoard(db_dir / "tasks.db")
        await self._task_board.init_db()

        self._message_bus = MessageBus(db_dir / "messages.db")
        await self._message_bus.init_db()

        self._dynamic_roster = bootstrap_dynamic_roster(state_dir=self.state_dir)
        self._memory = StrangeLoopMemory(db_dir / "memory.db")
        await self._memory.init_db()
        self._event_memory = EventMemoryStore(db_dir / "memory_plane.db")
        await self._event_memory.init_db()
        self._telemetry = TelemetryPlaneStore(state_runtime_db)
        await self._telemetry.init_db()

        self._agent_pool = AgentPool()
        self._gatekeeper = DEFAULT_GATEKEEPER
        self._thread_mgr = ThreadManager(self._daemon, self.state_dir)

        self._yoga = YogaScheduler(
            quiet_hours=self._daemon.quiet_hours,
            max_daily_tasks=self._daemon.max_daily_contributions * 5,
        )
        self._orchestrator = Orchestrator(
            task_board=self._task_board,
            agent_pool=self._agent_pool,
            message_bus=self._message_bus,
            ledger_dir=self.state_dir / "ledgers",
            runtime_db_path=state_runtime_db,
            event_memory=self._event_memory,
            yoga=self._yoga,
        )
        if self._room_registry is not None:
            self._orchestrator._room_registry = self._room_registry

        self._running = True
        self._shutdown_started = False
        self._shutdown_complete = False

        if self._read_only_boot:
            logger.info(
                "Read-only boot enabled — skipping manifest refresh, stale task reaping, "
                "startup crews, seed tasks, and optional subsystem init"
            )
            self._telos_substrate_seeded = False
            self._refresh_initialized_registry()
            return

        # Load ecosystem awareness on every init
        from dharma_swarm.ecosystem_bridge import MANIFEST_PATH, update_manifest

        fallback_manifest_path = self.state_dir / "ecosystem_manifest.json"
        try:
            self._manifest = update_manifest()
        except PermissionError:
            logger.debug(
                "Global ecosystem manifest %s not writable; using state-local manifest %s",
                MANIFEST_PATH,
                fallback_manifest_path,
            )
            self._manifest = update_manifest(manifest_path=fallback_manifest_path)

        # Boot reconcile of orphaned delegation_runs/task_claims from prior
        # daemon incarnations (single-writer: SwarmManager owns this pass).
        # Must run BEFORE the stale-task reaper: a crashed run with a persisted
        # success receipt settles its board task COMPLETED here; if the reaper
        # ran first it would board-FAIL the task and the receipt completion
        # could no longer apply (FAILED -> COMPLETED is not a legal transition).
        graph_reconciler = self._get_graph_reconciler()
        try:
            boot_report = await self.reconcile_graph_runs()
            if boot_report.total_reconciled or boot_report.recovered_claims:
                logger.info(
                    "Graph reconciler settled orphaned dispatch state at boot: %s",
                    boot_report.summary(),
                )
        except Exception as exc:
            graph_reconciler.invalidate_boot_census()
            logger.warning("Graph boot reconcile failed (non-fatal): %s", exc)
            self._last_boot_reconcile_error = f"{type(exc).__name__}: {exc}"

        # Reap stale running tasks from prior daemon incarnations.
        # When the daemon crashes, tasks it dispatched are left in RUNNING status
        # forever. No other daemon instance will ever settle them because
        # _collect_completed only tracks in-process asyncio tasks.
        if self._get_graph_reconciler().boot_census_succeeded:
            try:
                reaped = await self._reap_stale_running_tasks()
                if reaped:
                    logger.info(
                        "Reaped %d stale running tasks from prior daemon", reaped
                    )
            except Exception as exc:
                logger.warning("Stale task reaper failed (non-fatal): %s", exc)
        else:
            logger.warning(
                "Stale task reaper held: graph boot census did not succeed"
            )

        # All task-producing boot effects are Graph-gated and component-wise
        # retryable. Fast boot still defers its default crew and optional
        # subsystems when the initial census is green.
        startup_components = {
            "telos_substrate",
            "gnani_lodestone",
            "cybernetics_crew",
            "seed_tasks",
        }
        if not self._fast_boot:
            startup_components.add("default_crew")
        self._startup_backfill_pending_components.update(startup_components)

        startup_report: dict[str, Any] = {"created": {}}
        if graph_reconciler.boot_census_succeeded:
            startup_report = await self._backfill_graph_held_startup()
        else:
            logger.warning(
                "Startup generation held: graph boot census did not succeed"
            )

        created = startup_report.get("created", {})
        cyber_count = int(created.get("cybernetics_crew", 0))
        seed_count = int(created.get("seed_tasks", 0))
        crew_count = int(created.get("default_crew", 0))
        if cyber_count:
            logger.info("Spawned %d agents for cybernetics crew", cyber_count)
        if seed_count:
            logger.info("Created %d seed tasks", seed_count)

        if self._fast_boot:
            self._startup_backfill_pending_components.update(
                {"default_crew", "optional_subsystems"}
            )
            await self._memory.remember(
                f"Swarm fast-boot initialized — 0 default agents, "
                f"{cyber_count} cybernetics agents, {seed_count} seed tasks",
                layer=MemoryLayer.SESSION,
                source="swarm",
            )
            self._refresh_initialized_registry()
            if graph_reconciler.boot_census_succeeded:
                self._startup_background_task = asyncio.create_task(
                    self._complete_deferred_startup()
                )
                logger.info(
                    "Fast boot enabled — deferred default crew and "
                    "noncritical subsystems"
                )
            else:
                logger.warning(
                    "Fast boot startup backfill held: graph boot census did not succeed"
                )
            return

        if crew_count:
            logger.info("Spawned %d agents from default crew", crew_count)

        await self._memory.remember(
            f"Swarm initialized — {crew_count} default agents, "
            f"{cyber_count} cybernetics agents, {seed_count} seed tasks",
            layer=MemoryLayer.SESSION,
            source="swarm",
        )

        if self._critical_startup_pending_components():
            self._startup_backfill_pending_components.add("optional_subsystems")
            logger.warning(
                "Optional subsystem startup held until Graph-gated backfill completes"
            )
        else:
            try:
                await asyncio.wait_for(
                    self._init_optional_subsystems(), timeout=120.0,
                )
            except asyncio.TimeoutError:
                self._startup_backfill_pending_components.add(
                    "optional_subsystems"
                )
                self._optional_startup_last_error = (
                    "optional_subsystems: TimeoutError: exceeded 120s"
                )
                logger.warning(
                    "Optional subsystem init timed out after 120s — "
                    "queued for Graph-gated retry"
                )
                self._refresh_initialized_registry()
            except Exception as exc:
                self._startup_backfill_pending_components.add(
                    "optional_subsystems"
                )
                self._optional_startup_last_error = (
                    f"optional_subsystems: {type(exc).__name__}: {exc}"
                )
                logger.warning(
                    "Optional subsystem init failed — queued for Graph-gated retry: %s",
                    exc,
                )

    # --- Agent Operations ---

    async def spawn_agent(
        self,
        name: str,
        role: AgentRole = AgentRole.GENERAL,
        model: str = "claude-code",
        provider_type: ProviderType = ProviderType.CLAUDE_CODE,
        system_prompt: str = "",
        thread: str | None = None,
    ) -> AgentState:
        """Spawn a new agent into the pool.

        If no system_prompt is given, v7 induction rules + role briefing are used.
        If a thread is specified, the thread focus prompt is appended.

        When the agent name matches the constitutional roster, roster defaults
        are applied for role, model, provider, and system_prompt (caller values
        override only when explicitly non-default).
        """
        spec = None
        spec_metadata: dict[str, Any] = {}
        # Constitutional roster check: apply spec defaults for stable agents
        try:
            from dharma_swarm.agent_constitution import get_runtime_agent_spec

            spec = get_runtime_agent_spec(name, state_dir=self.state_dir)
            if spec is not None:
                # Stable agent — use constitutional defaults unless caller overrides
                if role == AgentRole.GENERAL:
                    role = spec.role
                if model == "claude-code" and spec.default_model:
                    model = spec.default_model
                if provider_type == ProviderType.CLAUDE_CODE and spec.default_provider:
                    provider_type = spec.default_provider
                if not system_prompt and spec.system_prompt:
                    system_prompt = spec.system_prompt
                spec_metadata = dict(spec.metadata or {})
                if not any(
                    key in spec_metadata
                    for key in (
                        "allow_provider_routing",
                        "available_provider_types",
                        "provider_allowlist",
                    )
                ):
                    spec_metadata["allow_provider_routing"] = True
                try:
                    from dharma_swarm.model_catalog import apply_model_pack_metadata

                    spec_metadata = apply_model_pack_metadata(spec_metadata)
                except Exception:
                    logger.debug("Model catalog resolution failed for %s", name, exc_info=True)
                logger.info(
                    "Constitutional agent %s: role=%s, model=%s, gates=%s",
                    name, role.value, model, spec.constitutional_gates,
                )
                # Create worker spawner for constitutional agents
                try:
                    from dharma_swarm.worker_spawn import create_spawner_for_agent
                    self._worker_spawners[name] = create_spawner_for_agent(
                        name,
                        state_dir=self.state_dir,
                    )
                except Exception:
                    logger.debug("Worker spawner creation failed for %s", name, exc_info=True)
        except Exception:
            logger.debug("Constitutional roster check failed", exc_info=True)

        async with jikoku_auto_span(
            category="execute.agent_spawn",
            intent=f"Spawn agent {name} ({role.value})",
            agent_name=name,
            role=role.value,
            model=model,
            provider=provider_type.value,
        ):
            # Build system prompt with thread context if applicable
            extra_prompt = ""
            if thread and thread in THREAD_PROMPTS:
                extra_prompt = f"\n\nCurrent research thread: {thread}\n{THREAD_PROMPTS[thread]}"

            config = AgentConfig(
                name=name,
                role=role,
                model=model,
                provider=provider_type,
                system_prompt=system_prompt + extra_prompt if system_prompt else extra_prompt,
                thread=thread,
                metadata={
                    **spec_metadata,
                    "state_dir": str(self.state_dir),
                },
            )
            # Route through the shared ModelRouter so live agent tasks contribute
            # to routing memory, retries, and audit trails while staying pinned
            # to config.provider unless task metadata widens the lane set.
            if self._agent_pool is None:
                raise RuntimeError("AgentPool not initialized — cannot spawn agents")
            spawner = self._worker_spawners.get(name)
            runner = await self._agent_pool.spawn(
                config,
                provider=self._router,
                message_bus=self._message_bus,
                worker_spawner=spawner,
            )
            self._agent_configs[runner.state.id] = config
            await self._sync_agent_contracts(runner.state)
            await self._memory.remember(
                f"Agent spawned: {name} ({role.value})"
                + (f" [thread: {thread}]" if thread else ""),
                layer=MemoryLayer.SESSION,
                source="swarm",
            )
            return runner.state

    def get_worker_spawner(self, agent_name: str) -> Any | None:
        """Return the WorkerSpawner for a constitutional agent, or None."""
        return self._worker_spawners.get(agent_name)

    async def list_agents(self) -> list[AgentState]:
        """List all agents in the pool."""
        agents = await self._agent_pool.list_agents()
        await self._sync_agent_contracts_batch(agents, include_kaizenops=False)
        return agents

    async def stop_agent(self, agent_id: str) -> None:
        """Stop a specific agent."""
        runner = await self._agent_pool.get(agent_id)
        if runner:
            await runner.stop()
            await self._sync_agent_contracts(runner.state, include_kaizenops=False)

    async def sync_agents(
        self,
        *,
        include_kaizenops: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Refresh live agent contracts across telemetry and optional KaizenOps."""
        agents = await self._agent_pool.list_agents()
        return await self._sync_agent_contracts_batch(
            agents,
            include_kaizenops=include_kaizenops,
        )

    async def _sync_agent_contracts_batch(
        self,
        agents: list[AgentState],
        *,
        include_kaizenops: bool | None = None,
    ) -> list[dict[str, Any]]:
        metadata_by_agent_id: dict[str, dict[str, Any]] = {}
        thread_by_agent_id: dict[str, str | None] = {}
        managed_team_ids: list[str] = []
        for agent in agents:
            config = self._agent_configs.get(agent.id)
            metadata = dict(config.metadata) if config is not None else {}
            metadata.setdefault("provider", agent.provider)
            metadata.setdefault("model", agent.model)
            metadata.setdefault(
                "source",
                "swarm.spawn_agent" if config is not None else "swarm.sync_agents",
            )
            metadata_by_agent_id[agent.id] = metadata
            thread_by_agent_id[agent.id] = config.thread if config is not None else None
            managed_team_ids.append(
                resolve_team_id(thread=thread_by_agent_id[agent.id], metadata=metadata)
            )
        if not managed_team_ids:
            managed_team_ids.append(resolve_team_id(metadata={"team_id": DEFAULT_TEAM_ID}))
        results = await sync_live_agent_registrations(
            agents,
            telemetry=self._telemetry,
            metadata_by_agent_id=metadata_by_agent_id,
            thread_by_agent_id=thread_by_agent_id,
            message_bus=self._message_bus,
            include_kaizenops=include_kaizenops,
            managed_team_ids=managed_team_ids,
        )
        return [item.as_dict() for item in results]

    async def _sync_agent_contracts(
        self,
        agent: AgentState,
        *,
        include_kaizenops: bool | None = None,
    ) -> dict[str, Any]:
        config = self._agent_configs.get(agent.id)
        metadata = dict(config.metadata) if config is not None else {}
        metadata.setdefault("provider", agent.provider)
        metadata.setdefault("model", agent.model)
        metadata.setdefault("source", "swarm.spawn_agent" if config is not None else "swarm.list_agents")
        result = await sync_live_agent_registration(
            agent,
            telemetry=self._telemetry,
            thread=config.thread if config is not None else None,
            metadata=metadata,
            message_bus=self._message_bus,
            include_kaizenops=include_kaizenops,
        )
        return result.as_dict()

    # --- Task Operations ---

    @staticmethod
    def _is_self_referential_heartbeat_task(
        *,
        title: str,
        description: str,
        metadata: dict[str, Any],
    ) -> bool:
        """Block heartbeat loops that create tasks about heartbeat artifacts."""
        source = str(metadata.get("source", "")).lower()
        if source not in {"heartbeat", "pulse", "daemon", "system_heartbeat"}:
            return False
        text = f"{title}\n{description}".lower()
        has_heartbeat = "heartbeat" in text
        self_referential = any(
            marker in text
            for marker in (
                "heartbeat.md",
                "parse heartbeat",
                "summarize heartbeat",
                "analyze heartbeat",
                "task about heartbeat",
            )
        )
        return has_heartbeat and self_referential

    @staticmethod
    def _dedupe_strings(values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            item = str(value).strip()
            if not item or item in seen:
                continue
            seen.add(item)
            ordered.append(item)
        return ordered

    @classmethod
    def _coerce_string_list(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            values = [part.strip() for part in value.split(",")]
        elif isinstance(value, (list, tuple, set)):
            values = [str(part).strip() for part in value]
        else:
            return []
        return cls._dedupe_strings([item for item in values if item])

    @staticmethod
    def _coordination_claim_key(metadata: dict[str, Any], title: str = "") -> str:
        for key in (
            "coordination_claim_key",
            "claim_key",
            "coordination_topic",
            "topic",
            "task_group",
        ):
            value = str(metadata.get(key, "")).strip()
            if value:
                return value
        return title.strip()

    @staticmethod
    def _clamp_coordination_uncertainty(value: Any) -> float | None:
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return None

    @classmethod
    def _normalize_coordination_metadata(
        cls,
        metadata: dict[str, Any],
        *,
        title: str = "",
    ) -> dict[str, Any]:
        normalized = dict(metadata)
        claim_key = cls._coordination_claim_key(normalized, title)
        if claim_key:
            normalized["coordination_claim_key"] = claim_key
            normalized.setdefault("coordination_topic", claim_key)

        context = cls._coerce_string_list(
            normalized.get("coordination_shared_context")
        )
        if context:
            normalized["coordination_shared_context"] = context

        preferred_roles = cls._coerce_string_list(
            normalized.get("coordination_preferred_roles")
            or normalized.get("preferred_roles")
        )
        if preferred_roles:
            normalized["coordination_preferred_roles"] = [
                role.lower() for role in preferred_roles
            ]

        uncertainty = cls._clamp_coordination_uncertainty(
            normalized.get("coordination_uncertainty", normalized.get("uncertainty"))
        )
        if uncertainty is not None:
            normalized["coordination_uncertainty"] = uncertainty

        state = str(normalized.get("coordination_state", "")).strip().lower()
        if not state and claim_key:
            if uncertainty is not None and uncertainty >= 0.5:
                state = "uncertain"
            elif bool(normalized.get("coordination_review_required")):
                state = "uncertain"
            else:
                state = "local"
        if state:
            normalized["coordination_state"] = state

        route = str(normalized.get("coordination_route", "")).strip().lower()
        if (
            route == "synthesis_review"
            or bool(normalized.get("coordination_review_required"))
            or state == "uncertain"
        ):
            normalized["coordination_review_required"] = True
            normalized["coordination_route"] = "synthesis_review"
            normalized.setdefault(
                "coordination_preferred_roles",
                ["reviewer", "researcher", "general"],
            )
        return normalized

    async def create_task(
        self,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Create a new task on the board."""
        incoming = dict(metadata or {})
        if "trace_id" not in incoming:
            incoming["trace_id"] = _make_trace_id()
        incoming.setdefault("created_via", "swarm.create_task")
        incoming.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        incoming = self._normalize_coordination_metadata(incoming, title=title)

        async with jikoku_auto_span(
            category="execute.task_create",
            intent=f"Create task: {title}",
            priority=priority.value,
            desc_length=len(description),
            trace_id=incoming["trace_id"],
        ):
            if self._is_self_referential_heartbeat_task(
                title=title,
                description=description,
                metadata=incoming,
            ):
                raise ValueError(
                    "Self-referential heartbeat task blocked to prevent autoimmune loop"
                )
            gate_result = self._gatekeeper.check(action=title, content=description)
            if gate_result.decision.value == "block":
                raise ValueError(f"Telos gate blocked: {gate_result.reason}")
            return await self._task_board.create(
                title=title,
                description=description,
                priority=priority,
                metadata=incoming,
            )

    async def create_task_batch(
        self,
        tasks: list[dict[str, Any]],
    ) -> list[Task]:
        """Create multiple tasks in a single batch operation.

        JIKOKU-optimized: Uses single transaction to eliminate SQLite
        write lock contention when creating multiple tasks.

        Args:
            tasks: List of task specs, each dict with keys:
                   {title, description?, priority?}

        Returns:
            List of created Task objects.
        """
        async with jikoku_auto_span(
            category="execute.task_create_batch",
            intent=f"Create {len(tasks)} tasks in batch",
            task_count=len(tasks),
        ):
            batch_id = f"batch_{uuid4().hex}"
            enriched: list[dict[str, Any]] = []

            # Run telos gates on all tasks first
            for spec in tasks:
                spec_copy = dict(spec)
                meta = dict(spec_copy.get("metadata") or {})
                if "trace_id" not in meta:
                    meta["trace_id"] = _make_trace_id()
                meta.setdefault("batch_id", batch_id)
                meta.setdefault("created_via", "swarm.create_task_batch")
                meta.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                meta = self._normalize_coordination_metadata(
                    meta,
                    title=str(spec_copy.get("title", "")),
                )
                spec_copy["metadata"] = meta

                if self._is_self_referential_heartbeat_task(
                    title=str(spec_copy.get("title", "")),
                    description=str(spec_copy.get("description", "")),
                    metadata=meta,
                ):
                    raise ValueError(
                        "Self-referential heartbeat task blocked to prevent autoimmune loop"
                    )

                gate_result = self._gatekeeper.check(
                    action=spec_copy["title"],
                    content=spec_copy.get("description", ""),
                )
                if gate_result.decision.value == "block":
                    raise ValueError(
                        f"Telos gate blocked task '{spec_copy['title']}': {gate_result.reason}"
                    )
                enriched.append(spec_copy)

            # Batch create all tasks in single transaction
            return await self._task_board.create_batch(enriched)

    @staticmethod
    def _latent_gold_task_title(shard: Any) -> str:
        prefix = {
            "question": "Answer latent question",
            "warning": "Resolve latent warning",
            "todo": "Follow up latent todo",
            "hypothesis": "Test latent hypothesis",
            "insight": "Develop latent insight",
            "proposal": "Reopen latent branch",
        }.get(str(getattr(shard, "shard_kind", "")), "Reopen latent branch")
        stem = str(getattr(shard, "text", "")).strip().rstrip(".")
        return f"{prefix}: {stem[:72]}".strip()

    @staticmethod
    def _latent_gold_task_description(shard: Any) -> str:
        return (
            "This task was reopened automatically from a high-salience latent branch "
            "captured during prior conversation flow.\n\n"
            f"Original shard:\n{getattr(shard, 'text', '').strip()}\n\n"
            f"State: {getattr(shard, 'state', 'unknown')}\n"
            f"Kind: {getattr(shard, 'shard_kind', 'unknown')}\n"
            f"Salience: {float(getattr(shard, 'salience', 0.0)):.2f}\n"
            f"Source task: {getattr(shard, 'task_id', '') or 'n/a'}\n\n"
            "Goal: decide whether this branch should be implemented, tested, "
            "archived, or explicitly rejected. If you resolve it, mention the "
            "originating latent branch in the result."
        )

    async def spawn_latent_gold_tasks(
        self,
        *,
        limit: int = 2,
        max_pending: int = 12,
        min_salience: float = 0.72,
    ) -> list[Task]:
        """Promote unresolved high-salience latent branches into real tasks."""
        if self._task_board is None:
            return []

        plane_path = self.state_dir / "db" / "memory_plane.db"
        if not plane_path.exists():
            return []

        from dharma_swarm.engine.conversation_memory import ConversationMemoryStore

        counts = await self._task_board.stats()
        active = (
            int(counts.get("pending", 0))
            + int(counts.get("assigned", 0))
            + int(counts.get("running", 0))
        )
        if active >= max_pending:
            return []

        existing = await self._task_board.list_tasks(limit=500)
        claimed_shards = {
            str(task.metadata.get("latent_gold_shard_id"))
            for task in existing
            if isinstance(task.metadata, dict)
            and isinstance(task.metadata.get("latent_gold_shard_id"), str)
            and str(task.metadata.get("latent_gold_shard_id")).strip()
        }

        store = ConversationMemoryStore(plane_path)
        # Run synchronous SQLite query in thread to avoid blocking event loop.
        # Push state + salience filters into SQL (min_salience param) so we
        # scan far fewer of the 85K+ shards.
        _sal = min_salience
        loop = asyncio.get_running_loop()
        all_shards = await loop.run_in_executor(
            None, lambda: store.latent_gold("", limit=200, min_salience=_sal)
        )
        candidates = [
            shard
            for shard in all_shards
            if shard.state in {"orphaned", "deferred"}
            and shard.shard_id not in claimed_shards
        ]
        if not candidates:
            return []

        capacity = max(0, max_pending - active)
        planned = candidates[: max(0, min(limit, capacity))]
        if not planned:
            return []

        task_specs: list[dict[str, Any]] = []
        for shard in planned:
            priority = (
                TaskPriority.HIGH
                if float(shard.salience) >= 0.85
                else TaskPriority.NORMAL
            )
            task_specs.append(
                {
                    "title": self._latent_gold_task_title(shard),
                    "description": self._latent_gold_task_description(shard),
                    "priority": priority,
                    "metadata": {
                        "memory_plane_db": str(plane_path),
                        "latent_gold_reopened": True,
                        "latent_gold_shard_id": shard.shard_id,
                        "latent_gold_source_task_id": shard.task_id,
                        "latent_gold_source_turn_id": shard.turn_id,
                        "latent_gold_state": shard.state,
                        "latent_gold_kind": shard.shard_kind,
                        "latent_gold_salience": round(float(shard.salience), 6),
                        "source": "swarm.latent_gold",
                    },
                }
            )

        created = await self.create_task_batch(task_specs)
        for task in created:
            shard_id = str(task.metadata.get("latent_gold_shard_id", "")).strip()
            if shard_id:
                store.record_follow_up_task(
                    shard_id=shard_id,
                    follow_up_task_id=task.id,
                    title=task.title,
                )

        if created and self._memory is not None:
            await self._memory.remember(
                f"Latent gold reopened into {len(created)} follow-up task(s)",
                layer=MemoryLayer.SESSION,
                source="swarm",
            )
        return created

    async def list_tasks(
        self, status: TaskStatus | None = None
    ) -> list[Task]:
        """List tasks with optional status filter."""
        return await self._task_board.list_tasks(status=status)

    async def get_task(self, task_id: str) -> Task | None:
        """Get a specific task."""
        return await self._task_board.get(task_id)

    @staticmethod
    def _coordination_synthesis_title(claim_key: str) -> str:
        return f"Synthesize disagreement: {claim_key[:72]}".strip()

    @staticmethod
    def _coordination_synthesis_description(claim_key: str) -> str:
        return (
            "The sheaf coordination layer detected a productive disagreement.\n\n"
            f"Claim: {claim_key}\n\n"
            "Produce a synthesis that:\n"
            "1. names the competing local positions,\n"
            "2. identifies evidence for each,\n"
            "3. distinguishes resolvable uncertainty from durable pluralism,\n"
            "4. recommends the safest next action for the swarm.\n\n"
            "Do not force a fake consensus. Preserve uncertainty explicitly when needed."
        )

    async def spawn_coordination_tasks(
        self,
        *,
        coordination: SwarmCoordinationState | None = None,
        limit: int = 2,
        max_pending: int = 12,
    ) -> list[Task]:
        """Spawn bounded synthesis tasks for active productive disagreements."""
        if self._task_board is None:
            return []

        state = coordination or await self.coordination_status(refresh=False)
        if state.productive_disagreements <= 0:
            return []

        counts = await self._task_board.stats()
        active = (
            int(counts.get("pending", 0))
            + int(counts.get("assigned", 0))
            + int(counts.get("running", 0))
        )
        if active >= max_pending:
            return []

        existing = await self._task_board.list_tasks(limit=500)
        active_claims = {
            str(task.metadata.get("coordination_claim_key", "")).strip()
            for task in existing
            if task.status in {TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.RUNNING}
            and isinstance(task.metadata, dict)
            and str(task.metadata.get("coordination_origin", "")).strip()
            == "sheaf_disagreement"
            and str(task.metadata.get("coordination_claim_key", "")).strip()
        }

        task_specs: list[dict[str, Any]] = []
        capacity = max(0, max_pending - active)
        planned_limit = max(0, min(limit, capacity))
        for claim_key in state.productive_disagreement_claim_keys:
            if len(task_specs) >= planned_limit:
                break
            if claim_key in active_claims:
                continue
            task_specs.append(
                {
                    "title": self._coordination_synthesis_title(claim_key),
                    "description": self._coordination_synthesis_description(claim_key),
                    "priority": TaskPriority.HIGH,
                    "metadata": {
                        "source": "swarm.coordination_synthesis",
                        "coordination_origin": "sheaf_disagreement",
                        "coordination_claim_key": claim_key,
                        "coordination_topic": claim_key,
                        "coordination_state": "uncertain",
                        "coordination_uncertainty": 1.0,
                        "coordination_review_required": True,
                        "coordination_route": "synthesis_review",
                        "coordination_preferred_roles": [
                            "reviewer",
                            "researcher",
                            "general",
                        ],
                        "coordination_shared_context": [
                            (
                                f"Productive disagreement remains active for claim "
                                f"'{claim_key}'."
                            )
                        ],
                        "task_group": f"coordination:{claim_key}",
                        "coordination_triggered_at": state.observed_at,
                    },
                }
            )

        if not task_specs:
            return []

        created = await self.create_task_batch(task_specs)
        if created and self._memory is not None:
            await self._memory.remember(
                f"Spawned {len(created)} coordination synthesis task(s)",
                layer=MemoryLayer.SESSION,
                source="swarm.coordination_synthesis",
            )
        return created

    # --- Orchestration ---

    async def dispatch_next(self) -> int:
        """Run one orchestration tick. Returns number of tasks dispatched."""
        await self.spawn_latent_gold_tasks()
        dispatches = await self._orchestrator.route_next()
        coordination = await self.coordination_status(refresh=True)
        await self.spawn_coordination_tasks(coordination=coordination)
        return len(dispatches)

    # ── Algedonic Channel (Beer S5 bypass to operator) ─────────────
    def _algedonic_handler(self, signal: Any) -> None:
        """Beer's algedonic channel: pain signal → file + macOS notification.

        This is the S5 bypass — critical signals skip S1-S4 and reach
        the operator (Dhyana) directly.  Wired as on_algedonic callback
        in OrganismRuntime.
        """
        import json as _json
        import subprocess

        # 1. Append to persistent signal log
        log_path = self.state_dir / "algedonic_signals.jsonl"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "kind": getattr(signal, "kind", "unknown"),
                "severity": getattr(signal, "severity", "unknown"),
                "action": getattr(signal, "action", ""),
                "value": getattr(signal, "value", 0.0),
                "timestamp": getattr(signal, "timestamp", 0.0),
            }
            with log_path.open("a", encoding="utf-8") as f:
                f.write(_json.dumps(entry) + "\n")
        except OSError as exc:
            logger.warning("Algedonic log write failed: %s", exc)

        # 2. Write EMERGENCY_HOLD marker ONLY after sustained critical signals.
        # Single critical events are logged but don't halt the swarm.
        # This prevents self-strangulation during bootstrap.
        severity = getattr(signal, "severity", "")
        if severity == "critical":
            self._algedonic_critical_count = getattr(self, '_algedonic_critical_count', 0) + 1
            if self._algedonic_critical_count >= 3:
                hold_path = self.state_dir / "EMERGENCY_HOLD"
                try:
                    hold_path.write_text(
                        f"{getattr(signal, 'kind', 'unknown')}: "
                        f"value={getattr(signal, 'value', 0):.3f} "
                        f"(after {self._algedonic_critical_count} consecutive critical signals)\n",
                        encoding="utf-8",
                    )
                except OSError as exc:
                    logger.warning("EMERGENCY_HOLD write failed: %s", exc)
            else:
                logger.warning(
                    "Algedonic critical #%d (need %d before EMERGENCY_HOLD)",
                    self._algedonic_critical_count, 3,
                )
        else:
            # Non-critical signal resets the counter
            self._algedonic_critical_count = 0

        # 3. macOS notification (non-blocking, best-effort)
        kind = getattr(signal, "kind", "unknown")
        value = getattr(signal, "value", 0)
        try:
            subprocess.Popen(
                [
                    "osascript", "-e",
                    f'display notification "ALGEDONIC [{severity}]: {kind} = {value:.3f}" '
                    f'with title "DHARMA SWARM" sound name "Sosumi"',
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            logger.debug("macOS notification failed", exc_info=True)

        logger.warning(
            "ALGEDONIC SIGNAL [%s] %s = %.3f → %s",
            severity, kind, value, getattr(signal, "action", ""),
        )

    def _check_human_overrides(self) -> dict[str, Any]:
        """Check .PAUSE, .FOCUS, .INJECT, EMERGENCY_HOLD files."""
        result: dict[str, Any] = {"paused": False, "focus": None, "inject": None}

        pause_path = self.state_dir / self._daemon.pause_file
        if pause_path.exists():
            result["paused"] = True
            return result

        # Algedonic EMERGENCY_HOLD — persists across restarts until operator clears
        emergency_path = self.state_dir / "EMERGENCY_HOLD"
        if emergency_path.exists():
            logger.warning("EMERGENCY_HOLD active — dispatch paused (rm %s to clear)", emergency_path)
            result["paused"] = True
            return result

        if self._thread_mgr:
            result["focus"] = self._thread_mgr.check_focus_override(self.state_dir)
            result["inject"] = self._thread_mgr.check_inject_override(self.state_dir)

        # Read .FOCUS file text for Wire 3 routing governance
        focus_path = self.state_dir / ".FOCUS"
        if focus_path.exists():
            try:
                result["focus_text"] = focus_path.read_text(encoding="utf-8")[:500]
            except Exception:
                pass

        return result

    def _in_quiet_hours(self) -> bool:
        """Check if current hour is in quiet hours."""
        return datetime.now().hour in self._daemon.quiet_hours

    def _contribution_allowed(self) -> bool:
        """Check rate limits: daily max, min interval between contributions."""
        now = datetime.now()

        # Reset daily counter at midnight
        if self._daily_reset is None or now.date() != self._daily_reset.date():
            self._daily_contributions = 0
            self._daily_reset = now

        if self._daily_contributions >= self._daemon.max_daily_contributions:
            return False

        if self._last_contribution:
            elapsed = (now - self._last_contribution).total_seconds()
            if elapsed < self._daemon.min_between_contributions:
                return False

        return True

    @staticmethod
    def _tick_did_work(activity: Any) -> bool:
        """Return True when an orchestration tick performed real work."""
        if isinstance(activity, dict):
            for key in ("dispatched", "settled", "recovered"):
                try:
                    if int(activity.get(key, 0) or 0) > 0:
                        return True
                except Exception:
                    continue
            return False
        if isinstance(activity, (int, float)):
            return activity > 0
        return bool(activity)

    async def _tick_living_layers(self) -> dict[str, int]:
        """Run stigmergy decay and other living-layer maintenance."""
        summary: dict[str, int] = {}
        if self._stigmergy:
            try:
                decayed = await self._stigmergy.decay()
                summary["stigmergy_decayed"] = decayed
            except Exception as exc:
                logger.info("Stigmergy decay failed (transient): %s", exc)
            try:
                faded = await self._stigmergy.access_decay()
                summary["stigmergy_faded"] = faded
            except Exception as exc:
                logger.debug("Stigmergy access_decay failed: %s", exc)
        return summary

    async def _reap_stale_running_tasks(
        self,
        *,
        max_age_hours: float = 6.0,
    ) -> int:
        """Fail tasks stuck in RUNNING status from prior daemon incarnations.

        When the daemon crashes, dispatched tasks remain in RUNNING forever
        because _collect_completed only tracks in-process asyncio futures.
        This method runs once at init to clean up orphaned tasks.
        """
        if self._task_board is None:
            return 0

        running = await self._task_board.list_tasks(
            status=TaskStatus.RUNNING, limit=500,
        )
        if not running:
            return 0

        from dharma_swarm.mission_control_executor_guard import campaign_principal

        now = datetime.now(timezone.utc)
        age_limit = timedelta(hours=max_age_hours)
        reaped = 0

        for task in running:
            age = now - task.updated_at
            if age < age_limit:
                continue
            if campaign_principal(task)[0]:
                logger.warning(
                    "Preserved stale campaign task %s as nonterminal/indeterminate "
                    "(age=%.1fh); generic crash recovery cannot prove provider "
                    "cessation or authorize retry",
                    task.id[:8],
                    age.total_seconds() / 3600,
                )
                continue
            try:
                _reap_meta = dict(task.metadata or {})
                _reap_meta.pop("active_claim", None)
                _reap_meta["reaped_at"] = datetime.now(timezone.utc).isoformat()
                _reap_meta["reap_reason"] = "stuck_running_daemon_recovery"
                await self._task_board.update_task(
                    task.id,
                    status=TaskStatus.FAILED,
                    result=(
                        f"Reaped: task was stuck in RUNNING for {age.total_seconds()/3600:.1f}h "
                        f"(daemon crash recovery). Agent {task.assigned_to or 'unknown'} is dead."
                    ),
                    metadata=_reap_meta,
                )
                reaped += 1
                logger.info(
                    "Reaped stale task %s (age=%.1fh): %s",
                    task.id[:8], age.total_seconds() / 3600, task.title[:60],
                )
            except Exception as exc:
                logger.warning("Failed to reap stale task %s: %s", task.id[:8], exc)

        return reaped

    def _derive_failure_source(self, task: Task) -> str:
        meta = dict(task.metadata or {})
        source = str(meta.get("last_failure_source", "")).strip()
        if source:
            return source
        result = str(task.result or "").lower()
        if "timed out" in result or result.startswith("timeout:"):
            return "timeout"
        return "execution_error"

    @staticmethod
    def _coerce_int(value: object, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_iso_datetime(raw: object) -> datetime | None:
        if not isinstance(raw, str) or not raw.strip():
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    @staticmethod
    def _failure_class_supports_auto_rescue(failure_class: str) -> bool:
        return failure_class in {"connection_transient", "long_timeout"}

    def _classify_failed_dependency(
        self,
        *,
        dep_meta: dict[str, Any],
        dep_result: str | None,
    ) -> str:
        failure_class = str(dep_meta.get("last_failure_class", "")).strip()
        if failure_class:
            return failure_class

        result_text = str(dep_result or "").strip().lower()
        if not result_text:
            return ""
        if "timed out" in result_text or result_text.startswith("timeout:"):
            return "long_timeout"
        if "connection error" in result_text or "rate limit" in result_text:
            return "connection_transient"
        if result_text.startswith("blocked:") or "telos blocked" in result_text:
            return "policy_block"
        return ""

    def _failed_dependency_is_terminal(
        self,
        *,
        dep_meta: dict[str, Any],
        dep_result: str | None,
        dep_updated_at_raw: object,
        now: datetime,
    ) -> bool:
        failure_class = self._classify_failed_dependency(
            dep_meta=dep_meta,
            dep_result=dep_result,
        )

        retry_count_raw = dep_meta.get("retry_count")
        max_retries_raw = dep_meta.get("max_retries")
        retry_budget_known = (
            retry_count_raw is not None and max_retries_raw is not None
        )
        retry_budget_open = False
        if retry_budget_known:
            retry_count = self._coerce_int(retry_count_raw, 0)
            max_retries = self._coerce_int(max_retries_raw, 0)
            retry_budget_open = retry_count < max_retries
            if retry_budget_open:
                return False

        rescue_count = self._coerce_int(dep_meta.get("auto_rescue_count"), 0)
        rescue_count_recorded = "auto_rescue_count" in dep_meta
        rescue_limit_reached = rescue_count >= self._auto_rescue_max_attempts
        auto_rescue_disabled = bool(dep_meta.get("auto_rescue_disabled"))
        dep_updated_at = self._parse_iso_datetime(dep_updated_at_raw)
        rescue_window_expired = (
            dep_updated_at is not None
            and now - dep_updated_at > self._auto_rescue_max_age
        )
        auto_rescue_eligible = (
            failure_class != ""
            and self._failure_class_supports_auto_rescue(failure_class)
            and not auto_rescue_disabled
            and not rescue_limit_reached
            and not rescue_window_expired
        )
        if auto_rescue_eligible:
            return False

        if retry_budget_known:
            return True
        if rescue_count_recorded and rescue_limit_reached:
            return True
        if failure_class and not self._failure_class_supports_auto_rescue(failure_class):
            return True
        if failure_class and (
            auto_rescue_disabled or rescue_limit_reached or rescue_window_expired
        ):
            return True
        return False

    def _get_graph_reconciler(self) -> GraphReconciler:
        from dharma_swarm.graph.reconciler import GraphReconciler
        from dharma_swarm.runtime_state import RuntimeStateStore

        if self._graph_reconciler is None:
            runtime_state = RuntimeStateStore(
                self.state_dir / "state" / "runtime.db"
            )
            self._graph_reconciler = GraphReconciler(
                runtime_state, task_board=self._task_board
            )
        return self._graph_reconciler

    async def reconcile_graph_runs(self, *, stale_only: bool = False) -> ReconcileReport:
        """Requeue-or-quarantine orphaned dispatch state (graph reconciler)."""
        return await self._get_graph_reconciler().reconcile(stale_only=stale_only)

    async def reap_orphaned_tasks(self, *, stale_minutes: int = 30) -> list[Task]:
        """Requeue ASSIGNED/RUNNING tasks whose agents no longer exist in the pool.

        After a daemon restart, agent UUIDs change. Tasks assigned to the old
        UUIDs sit forever as 'assigned' or 'running' because no agent will
        claim them.  This sweep detects them by checking whether the assigned
        agent ID is still present in the current agent pool and by applying a
        staleness threshold on updated_at.

        Also propagates failure through dependency chains: if a pending task's
        *only* blocking dependency is permanently failed (exhausted retries),
        that pending task is marked failed too so it doesn't block the chain
        forever.
        """
        if self._task_board is None or self._agent_pool is None:
            return []

        from dharma_swarm.mission_control_executor_guard import campaign_principal

        # Current live agent IDs
        live_agents = await self._agent_pool.list_agents()
        live_ids = {a.id for a in live_agents}

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=stale_minutes)
        reaped: list[Task] = []

        for status in (TaskStatus.ASSIGNED, TaskStatus.RUNNING):
            tasks = await self._task_board.list_tasks(status=status, limit=500)
            for task in tasks:
                agent_id = task.assigned_to or ""
                # Orphaned: agent not in current pool AND task is stale
                if agent_id in live_ids:
                    continue
                if task.updated_at > cutoff:
                    continue  # recently touched, give it time
                if campaign_principal(task)[0]:
                    logger.warning(
                        "Preserved orphaned campaign task %s as "
                        "nonterminal/indeterminate; generic recovery cannot "
                        "authorize retry or claim provider cessation",
                        task.id[:12],
                    )
                    continue

                meta = dict(task.metadata or {})
                meta["orphan_reaped_at"] = now.isoformat()
                meta["orphan_original_agent"] = agent_id
                meta["orphan_original_status"] = status.value
                meta.pop("active_claim", None)
                meta.pop("retry_not_before_epoch", None)

                try:
                    await self._task_board.requeue(
                        task.id,
                        reason=f"Orphan reaper: agent {agent_id[:12]} no longer in pool",
                        metadata=meta,
                    )
                    refreshed = await self._task_board.get(task.id)
                    if refreshed is not None:
                        reaped.append(refreshed)
                        logger.info(
                            "Reaped orphaned task %s (%s) from dead agent %s",
                            task.id[:12], status.value, agent_id[:12],
                        )
                except Exception as exc:
                    logger.debug("Failed to reap task %s: %s", task.id[:12], exc)

        # Propagate failure through dependency chains
        dep_failed = await self._propagate_dependency_failures()
        if dep_failed:
            logger.info("Dependency propagation failed %d blocked tasks", len(dep_failed))

        if reaped and self._memory is not None:
            await self._memory.remember(
                f"Orphan reaper recovered {len(reaped)} stuck task(s)",
                layer=MemoryLayer.SESSION,
                source="swarm.orphan_reaper",
            )
        return reaped

    async def _propagate_dependency_failures(self) -> list[Task]:
        """Fail PENDING tasks whose blocking dependencies are permanently failed."""
        if self._task_board is None:
            return []

        pending = await self._task_board.list_tasks(status=TaskStatus.PENDING, limit=500)
        propagated: list[Task] = []

        from dharma_swarm.mission_control_executor_guard import campaign_principal

        for task in pending:
            if campaign_principal(task)[0]:
                logger.warning(
                    "Dependency recovery preserving campaign task %s; generic "
                    "recovery cannot authorize its terminal transition",
                    task.id[:12],
                )
                continue
            # Check dependencies via the task_dependencies table
            try:
                async with self._task_board._open() as db:
                    cur = await db.execute(
                        "SELECT d.depends_on_id, dep.status, dep.metadata, dep.result, dep.updated_at "
                        "FROM task_dependencies d "
                        "JOIN tasks dep ON dep.id = d.depends_on_id "
                        "WHERE d.task_id = ?",
                        (task.id,),
                    )
                    deps = await cur.fetchall()
            except Exception:
                continue

            if not deps:
                continue  # No dependencies, should be ready

            # Check if ALL blocking deps are permanently failed
            all_blocking_failed = True
            has_blocking = False
            for _dep_id, dep_status, dep_meta_raw, dep_result, dep_updated_at in deps:
                if dep_status == TaskStatus.COMPLETED.value:
                    continue  # This dep is satisfied
                has_blocking = True
                if dep_status != TaskStatus.FAILED.value:
                    all_blocking_failed = False
                    break
                try:
                    dep_meta = __import__("json").loads(dep_meta_raw) if dep_meta_raw else {}
                except Exception:
                    dep_meta = {}
                if not self._failed_dependency_is_terminal(
                    dep_meta=dep_meta,
                    dep_result=dep_result,
                    dep_updated_at_raw=dep_updated_at,
                    now=datetime.now(timezone.utc),
                ):
                    all_blocking_failed = False
                    break

            if has_blocking and all_blocking_failed:
                try:
                    await self._task_board.update_task(
                        task.id,
                        status=TaskStatus.FAILED,
                        result="Dependency chain permanently failed — blocking tasks exhausted retries",
                    )
                    refreshed = await self._task_board.get(task.id)
                    if refreshed is not None:
                        propagated.append(refreshed)
                        logger.info(
                            "Dependency propagation: failed task %s (%s)",
                            task.id[:12], task.title[:60],
                        )
                except Exception as exc:
                    logger.debug("Dependency propagation failed for %s: %s", task.id[:12], exc)

        return propagated

    async def _task_queue_snapshot(self) -> dict[str, int]:
        """Return queue truthfulness metrics for runtime reporting."""
        if self._task_board is None:
            return {
                "pending": 0,
                "ready": 0,
                "blocked_pending": 0,
                "running": 0,
                "failed": 0,
                "completed": 0,
            }

        stats = await self._task_board.stats()
        ready_count = len(await self._task_board.get_ready_tasks())
        pending_count = int(stats.get("pending", 0))
        return {
            "pending": pending_count,
            "ready": ready_count,
            "blocked_pending": max(0, pending_count - ready_count),
            "running": int(stats.get("running", 0)),
            "failed": int(stats.get("failed", 0)),
            "completed": int(stats.get("completed", 0)),
        }

    async def rescue_recent_failures(
        self,
        *,
        limit: int = 4,
        max_age: timedelta | None = None,
    ) -> list[Task]:
        """Requeue recent transient failures once under the current retry policy."""
        if self._task_board is None or self._orchestrator is None:
            return []

        failed = await self._task_board.list_tasks(status=TaskStatus.FAILED, limit=200)
        if not failed:
            return []

        from dharma_swarm.mission_control_executor_guard import campaign_principal

        active_titles: set[str] = set()
        for status in (TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.RUNNING):
            tasks = await self._task_board.list_tasks(status=status, limit=500)
            for item in tasks:
                title = item.title.strip().lower()
                if title:
                    active_titles.add(title)

        now = datetime.now(timezone.utc)
        age_limit = max_age or self._auto_rescue_max_age
        rescued: list[Task] = []

        for task in sorted(failed, key=lambda item: item.updated_at, reverse=True):
            if len(rescued) >= limit:
                break
            if campaign_principal(task)[0]:
                logger.warning(
                    "Failure rescue preserving campaign task %s; only typed "
                    "attempt recovery may authorize another generation",
                    task.id,
                )
                continue
            if now - task.updated_at > age_limit:
                continue

            meta = dict(task.metadata or {})
            rescue_count = int(meta.get("auto_rescue_count", 0) or 0)
            if rescue_count >= self._auto_rescue_max_attempts:
                continue
            if meta.get("auto_rescue_disabled"):
                continue

            title_key = task.title.strip().lower()
            if title_key and title_key in active_titles:
                continue

            source = self._derive_failure_source(task)
            failure_class, retry_count, max_retries, backoff = (
                self._orchestrator.retry_policy_for_failure(
                    task=task,
                    error=str(task.result or ""),
                    source=source,
                    meta=meta,
                )
            )
            if failure_class not in {"connection_transient", "long_timeout"}:
                continue

            meta["retry_count"] = 0
            meta["max_retries"] = max_retries
            meta["retry_backoff_seconds"] = backoff
            meta.pop("retry_not_before_epoch", None)
            meta.pop("active_claim", None)
            meta["last_failure_class"] = failure_class
            meta["auto_rescue_count"] = rescue_count + 1
            meta["auto_rescued_at"] = now.isoformat()
            meta["auto_rescue_reason"] = "daemon.failure_rescue_sweep"

            await self._task_board.requeue(
                task.id,
                reason="Requeued by automatic failure rescue sweep",
                metadata=meta,
            )
            refreshed = await self._task_board.get(task.id)
            if refreshed is not None:
                rescued.append(refreshed)
                if title_key:
                    active_titles.add(title_key)

        if rescued and self._memory is not None:
            await self._memory.remember(
                f"Automatic rescue sweep requeued {len(rescued)} failed task(s)",
                layer=MemoryLayer.SESSION,
                source="swarm.failure_rescue",
            )
        return rescued

    async def _director_pulse(self) -> list[Task]:
        """Run one ThinkodynamicDirector vision pulse.

        Uses the lightweight ``sense()`` path (ecosystem signal ranking and
        opportunity detection) to avoid shelling out to an LLM on every tick.
        Tasks are enqueued via the director's own ``enqueue_workflow`` which
        writes to the shared task-board database.

        Returns:
            List of tasks created by the director, possibly empty.
        """
        if self._director is None:
            return []

        try:
            # Saturation guard: skip if the director already has plenty in-flight
            active_count = await self._director.active_director_task_count()
            if active_count >= self._director.max_active_tasks:
                logger.debug(
                    "Director pulse skipped: director tasks saturated (%d active)",
                    active_count,
                )
                return []

            # STRATOSPHERE: lightweight ecosystem sensing (no LLM call)
            sense_result = self._director.sense()
            opportunities = sense_result.get("opportunities", [])
            if not opportunities:
                logger.debug("Director pulse: no opportunities detected")
                return []

            # GROUND: compile a workflow from the top opportunity
            import time as _time

            cycle_id = f"swarm-{int(_time.time())}"
            # Build a minimal vision stub so compile_workflow_from_vision
            # falls through to the opportunity-based planner.
            vision_stub: dict[str, Any] = {
                "proposed_tasks": [],
                "vision_text": "",
                "vision_success": False,
                "seeds": [],
                "ecosystem": sense_result.get("signals", {}),
            }
            workflow = self._director.compile_workflow_from_vision(
                vision_stub, sense_result, cycle_id=cycle_id,
            )

            # DELEGATE: enqueue into the shared task board
            created = await self._director.enqueue_workflow(workflow)

            if created and self._memory is not None:
                primary = sense_result.get("primary")
                label = primary.title if primary else "ecosystem signal"
                await self._memory.remember(
                    f"Director pulse: {len(created)} task(s) from '{label}'",
                    layer=MemoryLayer.SESSION,
                    source="thinkodynamic_director",
                )
                logger.info(
                    "Director pulse created %d task(s) for '%s'",
                    len(created),
                    label,
                )
            return created

        except Exception as exc:
            logger.debug("Director pulse error: %s", exc)
            return []

    async def tick(self) -> dict[str, Any]:
        """Run one effect-bearing tick behind the census/effect mutex."""
        async with self._effect_tick_lock:
            return await self._tick_effects()

    async def _tick_effects(self) -> dict[str, Any]:
        """Execute one full swarm lifecycle tick.

        This is the unified control path -- the ONLY way to advance
        swarm state.  Both run() and orchestrate_live call this.

        v0.7.0: OrganismRuntime heartbeat runs every _organism_interval_ticks.
        When the Gnani says HOLD, autonomous generation and dispatch are
        suppressed — the organism's pain signal overrides busywork.
        """
        return await run_tick_effects(
            self,
            logger=logger,
            coordination_state_factory=SwarmCoordinationState,
        )

    async def run(self, interval: float | None = None) -> None:
        """Run the orchestration loop with Garden Daemon parameters.

        In daemon mode (interval=None), uses heartbeat_interval from config.
        In interactive mode, uses the provided interval.
        """
        tick_interval = interval if interval is not None else self._daemon.heartbeat_interval

        while self._running:
            try:
                activity = await self.tick()
                await self._publish_runtime_health_snapshot()
                if activity.get("paused"):
                    await asyncio.sleep(60)
                    continue
                if activity.get("circuit_broken"):
                    await asyncio.sleep(min(tick_interval, 300))
                    continue
            except Exception as exc:
                logger.exception("Tick failed: %s", exc)
                tripped = self._daemon.circuit_breaker.record_failure()
                if tripped:
                    if self._thread_mgr:
                        self._thread_mgr.rotate()
            await asyncio.sleep(tick_interval)

    def stop(self) -> None:
        """Stop the swarm."""
        self._running = False
        if self._orchestrator:
            self._orchestrator.stop()

    # --- Status ---

    async def status(self) -> SwarmState:
        """Get current swarm state snapshot."""
        agents = await self._agent_pool.list_agents() if self._agent_pool else []
        task_stats = await self._task_board.stats() if self._task_board else {}
        state = SwarmState(
            agents=agents,
            tasks_pending=task_stats.get("pending", 0),
            tasks_running=task_stats.get("running", 0),
            tasks_completed=task_stats.get("completed", 0),
            tasks_failed=task_stats.get("failed", 0),
            uptime_seconds=time.monotonic() - self._start_time,
        )
        # Attach organism status if available
        if self._organism is not None:
            state.organism = self._organism.status()
        return state

    async def _publish_runtime_health_snapshot(self) -> None:
        """Persist a best-effort control-plane snapshot for operator surfaces."""
        from dharma_swarm.runtime_artifacts import write_dgc_health_snapshot

        try:
            state = await self.status()
            write_dgc_health_snapshot(
                self.state_dir,
                daemon_pid=os.getpid(),
                agent_count=len(state.agents),
                task_count=(
                    state.tasks_pending
                    + state.tasks_running
                    + state.tasks_completed
                    + state.tasks_failed
                ),
                anomaly_count=0,
                source="swarm.run",
            )
        except Exception as exc:
            logger.debug("Runtime health snapshot publish failed: %s", exc)

    async def coordination_status(
        self,
        *,
        refresh: bool = True,
    ) -> SwarmCoordinationState:
        """Return a compact sheaf-based coordination snapshot."""
        if self._orchestrator is None:
            return SwarmCoordinationState()
        getter = getattr(self._orchestrator, "get_coordination_summary", None)
        if getter is None:
            return SwarmCoordinationState()
        payload = getter(refresh=refresh)
        if asyncio.iscoroutine(payload):
            payload = await payload
        if not isinstance(payload, dict):
            return SwarmCoordinationState()
        state = SwarmCoordinationState.model_validate(payload)
        if refresh and self._engine is not None:
            observer = getattr(self._engine, "observe_coordination_summary", None)
            if callable(observer):
                observer(state.model_dump())
        return state

    # --- Thread ---

    @property
    def current_thread(self) -> str | None:
        return self._thread_mgr.current_thread if self._thread_mgr else None

    def rotate_thread(self) -> str | None:
        if self._thread_mgr:
            return self._thread_mgr.rotate()
        return None

    # --- Memory ---

    async def remember(self, content: str) -> None:
        """Store a memory in the swarm's strange loop."""
        await self._memory.remember(
            content, layer=MemoryLayer.SESSION, source="user"
        )

    async def recall(self, limit: int = 10) -> list:
        """Recall recent memories."""
        return await self._memory.recall(limit=limit)

    # --- Decision Ontology (v0.9.0) ---

    def record_decision(self, decision: Any) -> Any:
        """Evaluate and persist a DecisionRecord. Returns DecisionQualityAssessment."""
        if self._decision_log is None:
            raise SubsystemNotReady("decision_log not initialized")
        return self._decision_log.record(decision)

    def list_decisions(self, *, limit: int = 50) -> list:
        """Return recent decisions from the log."""
        if self._decision_log is None:
            return []
        return self._decision_log.list_decisions(limit=limit)

    # --- Auto-evolution (stagnation detection + triggered evolution) ---

    def _detect_fitness_stagnation(self) -> bool:
        """Return True if fitness has stagnated over the last two windows.

        Compares the mean fitness of the recent window against the previous
        window.  If improvement is below ``_stagnation_threshold``, the system
        is stagnant.  Returns False when insufficient data.
        """
        w = self._stagnation_window
        if len(self._fitness_history) < w * 2:
            return False
        recent = self._fitness_history[-w:]
        previous = self._fitness_history[-2 * w:-w]
        recent_mean = sum(recent) / len(recent)
        previous_mean = sum(previous) / len(previous)
        return (recent_mean - previous_mean) < self._stagnation_threshold

    async def _maybe_auto_evolve(self, *, gnani_holds: bool) -> dict:
        """Conditionally trigger a Darwin Engine evolution cycle.

        Guards:
        1. gnani_holds — organism said HOLD, skip.
        2. daily limit — max N per day.
        3. stagnation — only evolve when fitness plateaus.
        """
        if gnani_holds:
            return {"skipped": "gnani_hold"}

        # Reset daily counter at midnight UTC
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._auto_evolve_day != today:
            self._auto_evolves_today = 0
            self._auto_evolve_day = today

        if self._auto_evolves_today >= self._max_auto_evolves_per_day:
            return {"skipped": "daily_limit"}

        # Collect current agent fitness into history
        if self._agent_pool is not None:
            try:
                agents = await self._agent_pool.list_agents()
                for a in agents:
                    fitness = getattr(a, "fitness", None)
                    if fitness is not None:
                        self._fitness_history.append(float(fitness))
            except Exception:
                pass

        if not self._detect_fitness_stagnation():
            return {"skipped": "no_stagnation"}

        # Trigger evolution
        result = await self.evolve(
            component="swarm",
            change_type="auto_evolution",
            description="Auto-triggered by fitness stagnation detection",
        )
        self._auto_evolves_today += 1
        return {
            "triggered": True,
            **result,
        }

    # --- Evolution (v0.2.0) ---

    async def evolve(
        self,
        component: str,
        change_type: str,
        description: str,
        diff: str = "",
        test_results: dict | None = None,
        code: str | None = None,
    ) -> dict:
        """Run a single evolution proposal through the full pipeline.

        Returns a summary dict with entry_id, fitness, and status.
        """
        if self._engine is None:
            raise RuntimeError("Swarm not initialized — call init() first")

        proposal = await self._engine.propose(
            component=component,
            change_type=change_type,
            description=description,
            diff=diff,
        )
        await self._engine.gate_check(proposal)
        if proposal.status.value == "rejected":
            return {"status": "rejected", "reason": proposal.gate_reason}

        await self._engine.evaluate(proposal, test_results=test_results, code=code)
        entry_id = await self._engine.archive_result(proposal)

        fitness = proposal.actual_fitness
        return {
            "status": "archived",
            "entry_id": entry_id,
            "weighted_fitness": fitness.weighted() if fitness else 0.0,
        }

    async def health_check(self) -> dict:
        """Run system health check. Returns report as dict."""
        if self._monitor is None:
            return {"status": "unknown", "reason": "monitor not initialized"}
        report = await self._monitor.check_health()
        return report.model_dump()

    async def fitness_trend(self, component: str | None = None) -> list:
        """Get fitness trend from the evolution archive."""
        if self._engine is None:
            return []
        return await self._engine.get_fitness_trend(component=component)

    # --- Dharma Status (v0.3.0) ---

    async def dharma_status(self) -> dict:
        """Return Dharma subsystem status."""
        result: dict = {
            "kernel": False,
            "corpus": False,
            "compiler": False,
            "canary": False,
            "stigmergy": False,
        }
        if self._kernel_guard:
            try:
                kernel = self._kernel_guard._kernel
                result["kernel"] = kernel is not None
                if kernel:
                    result["kernel_axioms"] = len(kernel.principles)
                    result["kernel_integrity"] = kernel.verify_integrity()
            except Exception:
                logger.debug("Kernel status check failed", exc_info=True)
        if self._corpus:
            claims = await self._corpus.list_claims()
            result["corpus"] = True
            result["corpus_claims"] = len(claims)
        if self._compiler:
            result["compiler"] = True
        if self._canary:
            result["canary"] = True
        if self._stigmergy:
            result["stigmergy"] = True
            result["stigmergy_density"] = self._stigmergy.density()
        return result

    async def gaia_health(self) -> dict:
        """Return GAIA ecological subsystem health."""
        try:
            from dharma_swarm.gaia_ledger import GaiaLedger
            from dharma_swarm.gaia_fitness import (
                EcologicalFitness,
                detect_goodhart_drift,
            )

            ledger_dir = self.state_dir / "gaia_ledger"
            if not ledger_dir.exists():
                return {"status": "no_ledger", "message": "No GAIA ledger found"}

            ledger = GaiaLedger(data_dir=ledger_dir)
            ledger.load()
            eco = EcologicalFitness()
            drift = detect_goodhart_drift(ledger)

            return {
                "status": "active",
                "weighted_fitness": eco.weighted_score(ledger),
                "is_drifting": drift["is_drifting"],
                "verification_ratio": drift["verification_ratio"],
                "diagnosis": drift["diagnosis"],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def propose_claim(
        self, statement: str, category: str = "operational", **kwargs: Any
    ) -> dict:
        """Propose a new claim to the Dharma Corpus."""
        if self._corpus is None:
            raise RuntimeError("Corpus not initialized")
        from dharma_swarm.dharma_corpus import ClaimCategory
        cat = ClaimCategory(category)
        claim = await self._corpus.propose(statement=statement, category=cat, **kwargs)
        return {"id": claim.id, "statement": claim.statement, "status": claim.status.value}

    async def review_claim(
        self, claim_id: str, reviewer: str, action: str, comment: str
    ) -> dict:
        """Review a claim in the Dharma Corpus."""
        if self._corpus is None:
            raise RuntimeError("Corpus not initialized")
        claim = await self._corpus.review(
            claim_id, reviewer=reviewer, action=action, comment=comment
        )
        return {
            "id": claim.id,
            "status": claim.status.value,
            "reviews": len(claim.review_history),
        }

    async def promote_claim(self, claim_id: str) -> dict:
        """Promote a claim to ACCEPTED status."""
        if self._corpus is None:
            raise RuntimeError("Corpus not initialized")
        claim = await self._corpus.promote(claim_id)
        return {"id": claim.id, "status": claim.status.value}

    async def canary_check(self, entry_id: str, canary_fitness: float) -> dict:
        """Evaluate a canary deployment."""
        if self._canary is None:
            raise RuntimeError("Canary not initialized")
        result = await self._canary.evaluate_canary(entry_id, canary_fitness)
        return {
            "decision": result.decision.value,
            "delta": result.delta,
            "reason": result.reason,
        }

    async def compile_policy(self, context: str = "default") -> dict:
        """Compile a policy from kernel + accepted corpus claims."""
        if self._compiler is None or self._kernel_guard is None or self._corpus is None:
            raise RuntimeError("Policy subsystems not initialized")
        principles = self._kernel_guard.get_all_principles()
        from dharma_swarm.dharma_corpus import ClaimStatus
        accepted_objs = await self._corpus.list_claims(status=ClaimStatus.ACCEPTED)
        policy = self._compiler.compile(
            kernel_principles=principles,
            accepted_claims=accepted_objs,
            context=context,
        )
        return {
            "total_rules": len(policy.rules),
            "immutable": len(policy.get_immutable_rules()),
            "mutable": len(policy.get_mutable_rules()),
            "context": policy.context,
        }

    # --- v0.4.0: Oz-Inspired Operations ---

    async def route_task(self, description: str) -> dict:
        """Route a task to the best skill via intent detection.

        Returns intent analysis including recommended skill, complexity,
        risk level, and agent count.
        """
        if self._intent_router is None:
            return {"error": "Intent router not initialized"}
        skill_name, intent = self._intent_router.route(description)
        return {
            "skill": skill_name,
            "confidence": intent.confidence,
            "complexity": intent.complexity,
            "risk": intent.risk_level,
            "recommended_agents": intent.recommended_agents,
            "parallel": intent.parallel,
        }

    async def decompose_task(self, description: str) -> dict:
        """Decompose a complex task into sub-tasks.

        Returns decomposed task with sub-tasks, agent recommendations,
        and parallelism analysis.
        """
        if self._intent_router is None:
            return {"error": "Intent router not initialized"}
        result = self._intent_router.decompose(description)
        return {
            "original": result.original,
            "sub_tasks": [
                {
                    "task": st.task,
                    "skill": st.primary_skill,
                    "complexity": st.complexity,
                    "risk": st.risk_level,
                }
                for st in result.sub_tasks
            ],
            "total_agents": result.total_agents,
            "has_parallel_work": result.has_parallel_work,
            "estimated_complexity": result.estimated_complexity,
        }

    async def search_context(self, query: str, budget: int = 10_000) -> str:
        """Search for task-relevant context (lazy loading).

        Instead of dumping all 30K of context, returns only what's
        relevant to the query. Saves ~26% tokens (Warp's finding).
        """
        if self._context_search is None:
            return ""
        return self._context_search.get_context_for_task(query, budget=budget)

    async def check_autonomy(self, action: str) -> dict:
        """Check if an action should be auto-approved.

        Returns autonomy decision with risk level, confidence,
        and whether to auto-approve or escalate.
        """
        if self._autonomy is None:
            return {"auto_approve": False, "reason": "Autonomy engine not initialized"}
        decision = self._autonomy.should_auto_approve(action)
        return {
            "auto_approve": decision.auto_approve,
            "risk": decision.risk.value,
            "reason": decision.reason,
            "escalate_to": decision.escalate_to,
        }

    def list_skills(self) -> list[dict]:
        """List all discovered skills."""
        if self._skill_registry is None:
            return []
        return [
            {
                "name": s.name,
                "model": s.model,
                "provider": s.provider,
                "autonomy": s.autonomy,
                "tags": s.tags,
                "description": s.description[:100],
            }
            for s in self._skill_registry.list_all()
        ]

    def hot_reload_skills(self) -> list[str]:
        """Hot-reload changed skill files. Returns names of reloaded skills."""
        if self._skill_registry is None:
            return []
        return self._skill_registry.hot_reload()

    async def compose_task(self, description: str) -> dict:
        """Compose a task into a DAG execution plan."""
        if self._skill_composer is None:
            return {"error": "Skill composer not initialized"}
        plan = self._skill_composer.compose(description)
        waves = plan.execution_order()
        return {
            "task": plan.task,
            "status": plan.status,
            "steps": [{"id": s.step_id, "skill": s.skill_name,
                       "task": s.task, "deps": s.depends_on}
                      for s in plan.steps],
            "waves": [[s.step_id for s in wave] for wave in waves],
            "ready": [s.step_id for s in plan.ready_steps()],
        }

    async def execute_composition(self, description: str) -> dict:
        """Compose and execute a task as a DAG plan.

        Builds a composition plan via SkillComposer, then runs it
        through the DAGExecutor with a runner that creates real tasks.

        Args:
            description: Natural language task description.

        Returns:
            Execution result dict with step-by-step outcomes.
        """
        if self._skill_composer is None:
            return {"error": "Skill composer not initialized"}

        plan = self._skill_composer.compose(description)

        from dharma_swarm.dag_executor import DAGExecutor
        from dharma_swarm.skill_composer import SkillStep

        async def _runner(step: SkillStep, context: str) -> str:
            """Execute a composition step by creating and running a swarm task."""
            task = await self.create_task(
                title=step.task,
                description=f"{step.task}\n\nContext:\n{context}" if context else step.task,
            )
            return f"Task {task.id} created: {step.task}"

        executor = DAGExecutor(composer=self._skill_composer, runner_fn=_runner)
        result = await executor.execute(plan)

        return {
            "task": result.plan_task,
            "status": result.status,
            "steps_completed": result.steps_completed,
            "steps_failed": result.steps_failed,
            "steps_skipped": result.steps_skipped,
            "duration": round(result.total_duration_seconds, 2),
            "steps": [
                {
                    "id": sr.step_id,
                    "skill": sr.skill_name,
                    "success": sr.success,
                    "output": sr.output[:200] if sr.output else "",
                    "error": sr.error,
                }
                for sr in result.step_results
            ],
        }

    async def create_handoff(
        self, from_agent: str, to_agent: str, task_context: str,
        artifacts: list[dict],
    ) -> dict:
        """Create a structured handoff between agents."""
        if self._handoff is None:
            return {"error": "Handoff protocol not initialized"}
        from dharma_swarm.handoff import Artifact, ArtifactType
        typed = [
            Artifact(
                artifact_type=ArtifactType(a.get("type", "context")),
                content=a.get("content", ""),
                summary=a.get("summary", ""),
                files_touched=a.get("files", []),
            )
            for a in artifacts
        ]
        h = await self._handoff.create_handoff(
            from_agent=from_agent, to_agent=to_agent,
            task_context=task_context, artifacts=typed,
        )
        return {"id": h.id, "status": h.status, "summary": h.summary()}

    async def get_agent_memory(self, agent_name: str) -> dict:
        """Get or create an agent's memory bank and return stats."""
        if agent_name not in self._agent_memories:
            from dharma_swarm.agent_memory import AgentMemoryBank
            bank = AgentMemoryBank(
                agent_name=agent_name,
                base_path=self.state_dir / "agent_memory",
            )
            await bank.load()
            self._agent_memories[agent_name] = bank
        bank = self._agent_memories[agent_name]
        return await bank.get_stats()

    async def agent_remember(self, agent_name: str, key: str, value: str,
                             category: str = "working", importance: float = 0.5) -> dict:
        """Store a memory for an agent."""
        if agent_name not in self._agent_memories:
            await self.get_agent_memory(agent_name)
        bank = self._agent_memories[agent_name]
        entry = await bank.remember(key, value, category=category,
                                    importance=importance, source=agent_name)
        await bank.save()
        return {"key": entry.key, "category": entry.category,
                "importance": entry.importance}

    # --- Session Digest (Wire 5: temporal continuity) ---

    async def _persist_session_digest(self) -> None:
        """Write session summary as memory_facts for cross-session learning.

        This is the temporal continuity wire. Before this, memory_facts
        had 0 rows. After this, the system can recall what happened in
        previous sessions and learn from outcomes.
        """
        from dharma_swarm.runtime_state import RuntimeStateStore, MemoryFact
        from uuid import uuid4

        store = RuntimeStateStore(db_path=self.state_dir / "state" / "runtime.db")
        await store.init_db()

        now = datetime.now(timezone.utc)
        session_id = f"swarm-{now.strftime('%Y%m%dT%H%M%S')}"

        # Gather session metrics
        facts: list[MemoryFact] = []

        # Fact 1: What tasks were completed
        if self._task_board:
            try:
                completed = await self._task_board.list_tasks(status="completed")
                count = len(completed) if completed else 0
                if count > 0:
                    titles = [t.title[:60] for t in (completed or [])[:5]]
                    facts.append(MemoryFact(
                        fact_id=f"fact_{uuid4().hex[:12]}",
                        fact_kind="session_outcome",
                        truth_state="observed",
                        text=f"Completed {count} tasks: {', '.join(titles)}",
                        confidence=0.9,
                        session_id=session_id,
                        valid_from=now,
                    ))
            except Exception:
                pass

        # Fact 2: Identity coherence state
        if self._organism:
            try:
                hb = self._organism.last_heartbeat
                if hb and hasattr(hb, "tcs"):
                    facts.append(MemoryFact(
                        fact_id=f"fact_{uuid4().hex[:12]}",
                        fact_kind="identity_state",
                        truth_state="observed",
                        text=f"Session ended with TCS={hb.tcs:.3f}, regime={hb.regime}",
                        confidence=0.95,
                        session_id=session_id,
                        valid_from=now,
                    ))
            except Exception:
                pass

        # Fact 3: Tick count and uptime
        facts.append(MemoryFact(
            fact_id=f"fact_{uuid4().hex[:12]}",
            fact_kind="session_stats",
            truth_state="observed",
            text=f"Session ran {self._tick_count} ticks, {self._contribution_count} contributions",
            confidence=1.0,
            session_id=session_id,
            valid_from=now,
        ))

        for fact in facts:
            try:
                await store.record_memory_fact(fact)
            except Exception as exc:
                logger.debug("Failed to record memory fact: %s", exc)

        if facts:
            logger.info("Persisted %d session memory facts (session=%s)", len(facts), session_id)

    # --- Shutdown ---

    async def _join_startup_tasks_for_shutdown(self) -> None:
        """Join canceled startup work before stopping anything it may publish."""
        for attr, label in (
            ("_startup_background_task", "Deferred startup"),
            ("_optional_startup_retry_task", "Optional startup retry"),
        ):
            background = getattr(self, attr)
            if background is None:
                continue
            try:
                if not background.done():
                    background.cancel()
                await background
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.debug("%s shutdown failed (non-fatal): %s", label, exc)
            finally:
                setattr(self, attr, None)

    async def shutdown(self, drain_timeout: float = 30.0) -> None:
        """Join the current effect tick, then tear the swarm down exactly once."""
        self._running = False
        self._shutdown_started = True
        for background in (
            self._startup_background_task,
            self._optional_startup_retry_task,
        ):
            if background is not None and not background.done():
                background.cancel()
        # Join before acquiring the effect lock: a cancellation-delaying
        # initializer may itself own or be waiting for that mutex.
        await self._join_startup_tasks_for_shutdown()
        async with self._effect_tick_lock:
            if self._shutdown_complete:
                return
            await self._shutdown_under_effect_lock(drain_timeout)
            self._shutdown_complete = True

    async def _shutdown_under_effect_lock(self, drain_timeout: float) -> None:
        """Graceful ordered shutdown of entire swarm.

        Varela's autopoiesis: clean death is part of the lifecycle.
        Teardown order is reverse of init — coordination first,
        then agents, then infrastructure.
        """
        logger.info("Swarm shutdown initiated (drain_timeout=%.1fs)", drain_timeout)

        # Wire 5: Persist session digest as memory facts before teardown.
        # This is THE temporal continuity wire — gives the system cross-session learning.
        # memory_facts schema has been empty (0 rows) since creation. This populates it.
        try:
            await self._persist_session_digest()
        except Exception as exc:
            logger.debug("Session digest persistence failed (non-fatal): %s", exc)

        # 1. Stop orchestrator (cancel in-flight tasks with drain)
        if self._orchestrator:
            try:
                stop_receipt = await self._orchestrator.graceful_stop(
                    timeout=drain_timeout
                )
            except Exception as exc:
                raise RuntimeError(
                    "swarm shutdown incomplete: orchestrator stop failed"
                ) from exc
            live = (
                int(stop_receipt.get("live", 0) or 0)
                if isinstance(stop_receipt, dict)
                else 0
            )
            if live:
                owners = stop_receipt.get("live_owners", {})
                raise RuntimeError(
                    "swarm shutdown incomplete: orchestrator retains "
                    f"{live} live owner(s): {owners}"
                )

        # 2. Stop director (optional subsystem)
        if self._director:
            try:
                stop_fn = getattr(self._director, "stop", None)
                if stop_fn:
                    result = stop_fn()
                    if asyncio.iscoroutine(result):
                        await result
            except Exception as exc:
                logger.debug("Director stop failed (non-fatal): %s", exc)

        # 2b. Stop gateway (optional subsystem)
        if self._gateway:
            try:
                await self._gateway.stop()
            except Exception as exc:
                logger.debug("Gateway stop failed (non-fatal): %s", exc)

        # 3. Shutdown agents
        if self._agent_pool:
            try:
                await self._agent_pool.shutdown_all()
            except Exception as exc:
                logger.warning("Agent pool shutdown failed: %s", exc)

        # 4. Close closeable providers in the router
        try:
            for provider in getattr(self._router, "_providers", {}).values():
                close_fn = getattr(provider, "close", None)
                if close_fn:
                    result = close_fn()
                    if asyncio.iscoroutine(result):
                        await result
        except Exception as exc:
            logger.debug("Provider close failed (non-fatal): %s", exc)

        # 5. Record shutdown in memory and close persistent connection
        if self._memory:
            try:
                if not self._read_only_boot:
                    await self._memory.remember(
                        "Swarm shutdown", layer=MemoryLayer.SESSION, source="swarm"
                    )
            except Exception:
                logger.debug("Shutdown memory write failed", exc_info=True)
            try:
                await self._memory.close()
            except Exception:
                logger.debug("Memory close failed", exc_info=True)

        self._initialized.clear()
        logger.info("Swarm shutdown complete")

    async def __aenter__(self) -> "SwarmManager":
        """Async context manager: init on enter."""
        await self.init()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager: shutdown on exit."""
        await self.shutdown()
