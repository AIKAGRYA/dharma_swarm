"""Pydantic data models for DHARMA SWARM.

All shared types, enums, and data structures used across the swarm system.
Every module imports from here — this is the schema contract.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# === Enums ===

class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class AgentStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    STARTING = "starting"
    STOPPING = "stopping"
    DEAD = "dead"


class AgentRole(str, Enum):
    CODER = "coder"
    REVIEWER = "reviewer"
    RESEARCHER = "researcher"
    TESTER = "tester"
    ORCHESTRATOR = "orchestrator"
    GENERAL = "general"
    # PSMV cognitive roles (from 5-role agent briefings)
    CARTOGRAPHER = "cartographer"
    ARCHEOLOGIST = "archeologist"
    SURGEON = "surgeon"
    ARCHITECT = "architect"
    VALIDATOR = "validator"
    CONDUCTOR = "conductor"
    # Constitutional topology (6-agent stable roster)
    OPERATOR = "operator"
    ARCHIVIST = "archivist"
    RESEARCH_DIRECTOR = "research_director"
    SYSTEMS_ARCHITECT = "systems_architect"
    STRATEGIST = "strategist"
    WITNESS = "witness"
    # Ephemeral worker role
    WORKER = "worker"


class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


class GateTier(str, Enum):
    A = "A"  # Absolute block
    B = "B"  # Strong block
    C = "C"  # Advisory


class GateResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


class GateDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REVIEW = "review"


class TopologyType(str, Enum):
    FAN_OUT = "fan_out"
    FAN_IN = "fan_in"
    PIPELINE = "pipeline"
    BROADCAST = "broadcast"


class MemoryLayer(str, Enum):
    IMMEDIATE = "immediate"
    SESSION = "session"
    DEVELOPMENT = "development"
    WITNESS = "witness"
    META = "meta"


class ProviderType(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    NVIDIA_NIM = "nvidia_nim"
    LOCAL = "local"
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"
    OPENROUTER_FREE = "openrouter_free"
    OLLAMA = "ollama"
    GROQ = "groq"
    CEREBRAS = "cerebras"
    SILICONFLOW = "siliconflow"
    TOGETHER = "together"
    FIREWORKS = "fireworks"
    GOOGLE_AI = "google_ai"
    SAMBANOVA = "sambanova"
    MISTRAL = "mistral"
    CHUTES = "chutes"


class AutonomyLevel(str, Enum):
    """How much freedom an agent has to act without confirmation."""
    LOCKED = "locked"
    CAUTIOUS = "cautious"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    FULL = "full"


# === Utility ===

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


# === Core Models ===

class Task(BaseModel):
    """A unit of work in the swarm."""
    id: str = Field(default_factory=_new_id)
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    assigned_to: Optional[str] = None
    created_by: str = "system"
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    depends_on: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    result: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """Configuration for spawning an agent.

    This is the CANONICAL agent identity model. All code that creates,
    stores, or references agent identity should use this class.
    See AGENT_IDENTITY_UNIFICATION.md for the migration plan.

    Legacy compatibility: bare strings for `provider` and `role` are
    coerced to enums via the model_validator below.
    """
    id: str = Field(default_factory=_new_id)
    name: str
    role: AgentRole = AgentRole.GENERAL
    provider: ProviderType = ProviderType.ANTHROPIC
    model: str = "claude-sonnet-4-20250514"
    system_prompt: str = ""
    max_turns: int = 50
    thread: Optional[str] = None
    tools: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Extended identity fields (Sprint 2)
    autonomy: AutonomyLevel = AutonomyLevel.BALANCED
    temperature: float = 0.7
    max_tokens: int = 4096
    context_budget: int = 30_000
    timeout: int = 300
    working_directory: str = ""
    wake_interval: int = 3600
    display_name: str = ""
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_enums(cls, data: Any) -> Any:
        """Coerce legacy bare strings to proper enums."""
        if isinstance(data, dict):
            # provider / provider_type normalization
            for key in ("provider", "provider_type"):
                val = data.get(key)
                if isinstance(val, str) and not isinstance(val, ProviderType):
                    try:
                        data["provider"] = ProviderType(val.lower())
                    except ValueError:
                        pass
            # role normalization
            val = data.get("role")
            if isinstance(val, str) and not isinstance(val, AgentRole):
                try:
                    data["role"] = AgentRole(val.lower())
                except ValueError:
                    pass
        return data


_SLUG_RE = re.compile(r"[^a-z0-9]+")


class AgentIdentity(BaseModel):
    """Canonical unified agent identity.

    Single source of truth for who an agent IS.  Supersedes the four
    legacy schemas (``AgentConfig``, ``AgentProfile``,
    ``autonomous_agent.AgentIdentity``, and ``startup_crew`` dicts).

    See ``AGENT_IDENTITY_UNIFICATION.md`` for the full migration spec.
    ``AgentConfig`` remains for backward compatibility; new code should
    construct ``AgentIdentity`` instead.
    """

    # ── Identity (required) ──
    name: str
    role: AgentRole = AgentRole.GENERAL
    provider: ProviderType = ProviderType.ANTHROPIC
    model: str = ""
    system_prompt: str = ""

    # ── Identity (optional) ──
    thread: Optional[str] = None
    working_directory: str = Field(default_factory=lambda: str(Path.home()))

    # ── Execution config ──
    max_turns: int = 25
    allowed_tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)
    wake_interval: float = 3600.0
    autonomy: AutonomyLevel = AutonomyLevel.BALANCED
    max_tokens: int = 4096
    temperature: float = 0.7
    context_budget: int = 30_000
    timeout: int = 300

    # ── Classification ──
    skill_name: str = ""
    tags: list[str] = Field(default_factory=list)
    display_name: str = ""
    agent_slug: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_enums(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ("provider", "provider_type"):
                val = data.get(key)
                if isinstance(val, str) and not isinstance(val, ProviderType):
                    try:
                        data["provider"] = ProviderType(val.lower())
                    except ValueError:
                        pass
            val = data.get("role")
            if isinstance(val, str) and not isinstance(val, AgentRole):
                try:
                    data["role"] = AgentRole(val.lower())
                except ValueError:
                    pass
        return data

    def resolved_display_name(self) -> str:
        return self.display_name or self.name

    def resolved_agent_slug(self) -> str:
        if self.agent_slug:
            return self.agent_slug
        return _SLUG_RE.sub("-", self.name.strip().lower()).strip("-") or "agent"

    def resolved_model(self) -> str:
        return self.model or "claude-sonnet-4-20250514"

    def provider_string(self) -> str:
        return self.provider.value

    def to_agent_config(self) -> AgentConfig:
        """Downcast to legacy AgentConfig for backward compatibility."""
        return AgentConfig(
            name=self.name,
            role=self.role,
            provider=self.provider,
            model=self.resolved_model(),
            system_prompt=self.system_prompt,
            max_turns=self.max_turns,
            thread=self.thread,
            tools=self.allowed_tools,
            autonomy=self.autonomy,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            context_budget=self.context_budget,
            timeout=self.timeout,
            working_directory=self.working_directory,
            wake_interval=int(self.wake_interval),
            display_name=self.display_name,
            tags=self.tags,
        )

    @classmethod
    def from_agent_config(cls, cfg: AgentConfig) -> AgentIdentity:
        """Upcast from legacy AgentConfig."""
        return cls(
            name=cfg.name,
            role=cfg.role,
            provider=cfg.provider,
            model=cfg.model,
            system_prompt=cfg.system_prompt,
            thread=cfg.thread,
            working_directory=cfg.working_directory or str(Path.home()),
            max_turns=cfg.max_turns,
            allowed_tools=cfg.tools,
            wake_interval=float(cfg.wake_interval),
            autonomy=cfg.autonomy,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            context_budget=cfg.context_budget,
            timeout=cfg.timeout,
            display_name=cfg.display_name,
            tags=cfg.tags,
        )


class AgentState(BaseModel):
    """Runtime state of an agent."""
    id: str
    name: str
    role: AgentRole
    status: AgentStatus = AgentStatus.IDLE
    current_task: Optional[str] = None
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    turns_used: int = 0
    tasks_completed: int = 0
    provider: str = ""
    model: str = ""
    error: Optional[str] = None


class Message(BaseModel):
    """A message between agents."""
    id: str = Field(default_factory=_new_id)
    from_agent: str
    to_agent: str
    subject: Optional[str] = None
    body: str
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.UNREAD
    created_at: datetime = Field(default_factory=_utc_now)
    read_at: Optional[datetime] = None
    reply_to: Optional[str] = None
    trace_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class GateCheckResult(BaseModel):
    """Result of running telos gates on an action."""
    decision: GateDecision
    reason: str
    gate: str = ""
    gate_results: dict[str, tuple[GateResult, str]] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)


class MemoryEntry(BaseModel):
    """An entry in the strange loop memory system."""
    id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_utc_now)
    layer: MemoryLayer
    content: str
    source: str = "agent"
    tags: list[str] = Field(default_factory=list)
    development_marker: bool = False
    witness_quality: float = 0.5


class SwarmState(BaseModel):
    """Overall swarm status snapshot."""
    agents: list[AgentState] = Field(default_factory=list)
    tasks_pending: int = 0
    tasks_running: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    uptime_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=_utc_now)
    organism: dict[str, Any] | None = None  # OrganismRuntime status when available


class TaskDispatch(BaseModel):
    """A task assignment from orchestrator to agent."""
    task_id: str
    agent_id: str
    topology: TopologyType = TopologyType.FAN_OUT
    timeout_seconds: float = 300.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SandboxResult(BaseModel):
    """Result from running code in a sandbox."""
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    timed_out: bool = False


class LLMRequest(BaseModel):
    """A request to an LLM provider."""
    model: str
    messages: list[dict[str, Any]]
    system: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    tools: list[dict[str, Any]] = Field(default_factory=list)


class LLMResponse(BaseModel):
    """Response from an LLM provider."""
    content: str
    model: str
    provider: str = ""
    usage: dict[str, int] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    stop_reason: Optional[str] = None


# === Cascade / Strange Loop Models ===

class LoopDomain(BaseModel):
    """Configuration for a cascade domain.

    Defines the phase functions (generate/test/score/gate/mutate/select/eigenform)
    and convergence parameters for one domain of the strange loop engine.
    """
    name: str
    generate_fn: str = "dharma_swarm.cascade_domains.common.default_generate"
    test_fn: str = "dharma_swarm.cascade_domains.common.default_test"
    score_fn: str = "dharma_swarm.cascade_domains.common.default_score"
    gate_fn: str = "dharma_swarm.cascade_domains.common.telos_gate"
    mutate_fn: str = "dharma_swarm.cascade_domains.common.default_mutate"
    select_fn: str = "dharma_swarm.cascade_domains.common.default_select"
    eigenform_fn: str = "dharma_swarm.cascade_domains.common.default_eigenform"
    max_iterations: int = 10
    fitness_threshold: float = 0.7
    eigenform_epsilon: float = 0.01
    convergence_window: int = 3
    max_duration_seconds: float = 300.0
    mutation_rate: float = 0.1


class LoopResult(BaseModel):
    """Result of running one cascade domain through the loop engine."""
    domain: str
    cycle_id: str = Field(default_factory=_new_id)
    iterations_completed: int = 0
    best_fitness: float = 0.0
    eigenform_reached: bool = False
    converged: bool = False
    convergence_reason: str = ""
    fitness_trajectory: list[float] = Field(default_factory=list)
    eigenform_trajectory: list[float] = Field(default_factory=list)
    duration_seconds: float = 0.0
    interrupted: bool = False
    interrupt_reason: str = ""


class CatalyticEdge(BaseModel):
    """Directed edge in the catalytic knowledge graph."""
    source: str
    target: str
    edge_type: str
    strength: float = 1.0
    evidence: str = ""


class ForgeScore(BaseModel):
    """Composite quality score produced by QualityForge."""
    stars: float = 0.0
    yosemite: float = 5.0
    dharmic: float = 0.0
    efficiency: float = 0.0
    elegance_sub: float = 0.0
    behavioral_sub: float = 0.0
    timestamp: datetime = Field(default_factory=_utc_now)


class SystemVitals(BaseModel):
    """Snapshot of system-level R_V measurement and regime."""
    system_rv: float = 1.0
    pr_current: float = 0.0
    pr_previous: float = 0.0
    regime: str = "unknown"
    exploration_factor: float = 1.0
    dimension_count: int = 0
