"""Deep Agent harness flags and manifest models.

Phase 0 keeps these models additive and default-off so legacy AgentRunner
behavior remains the runtime default until later phases opt in explicitly.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from dharma_swarm.models import AgentConfig, AgentRole, ProviderType

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}


def _env_flag(
    name: str,
    *,
    default: bool = False,
    env: Mapping[str, str] | None = None,
) -> bool:
    raw = (env or os.environ).get(name, "")
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


class DeepAgentFeatureFlags(BaseModel):
    """Feature gates for the staged Deep Agent harness rollout."""

    deep_agent_harness_enabled: bool = False
    todo_tool_enabled: bool = False
    backend_protocol_v2_enabled: bool = False
    task_tool_enabled: bool = False
    async_subagents_enabled: bool = False
    tool_hitl_enabled: bool = False
    agent_checkpoints_enabled: bool = False
    cost_ingest_enabled: bool = False
    acp_enabled: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "DeepAgentFeatureFlags":
        return cls(
            deep_agent_harness_enabled=_env_flag("DGC_DEEP_AGENT_HARNESS_ENABLED", env=env),
            todo_tool_enabled=_env_flag("DGC_TODO_TOOL_ENABLED", env=env),
            backend_protocol_v2_enabled=_env_flag("DGC_BACKEND_PROTOCOL_V2_ENABLED", env=env),
            task_tool_enabled=_env_flag("DGC_TASK_TOOL_ENABLED", env=env),
            async_subagents_enabled=_env_flag("DGC_ASYNC_SUBAGENTS_ENABLED", env=env),
            tool_hitl_enabled=_env_flag("DGC_TOOL_HITL_ENABLED", env=env),
            agent_checkpoints_enabled=_env_flag("DGC_AGENT_CHECKPOINTS_ENABLED", env=env),
            cost_ingest_enabled=_env_flag("DGC_COST_INGEST_ENABLED", env=env),
            acp_enabled=_env_flag("DGC_ACP_ENABLED", env=env),
        )

    @property
    def any_enabled(self) -> bool:
        return any(self.model_dump().values())


class DeepAgentIdentity(BaseModel):
    """Harness identity profile for one agent runtime."""

    agent_id: str
    agent_name: str
    agent_role: AgentRole
    session_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None


class DeepAgentProviderPolicy(BaseModel):
    """Provider/model selection policy for the harness."""

    provider: ProviderType
    model: str
    max_turns: int = Field(default=50, ge=1)
    max_tokens: int = Field(default=4096, ge=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    context_budget: int = Field(default=30_000, ge=1024)


class DeepAgentBackendPolicy(BaseModel):
    """Structured backend contract settings."""

    backend_kind: Literal["legacy_local_tools", "deep_agent_backend_v2"] = "legacy_local_tools"
    render_legacy_strings: bool = True


class DeepAgentMemoryPolicy(BaseModel):
    """Memory scoping for harness context assembly."""

    scope: Literal["agent", "session", "project", "user"] = "agent"
    include_layers: list[str] = Field(default_factory=list)


class DeepAgentSubagentPolicy(BaseModel):
    """Subagent limits and rollout guardrails."""

    enabled: bool = False
    max_depth: int = Field(default=0, ge=0, le=8)
    max_fanout: int = Field(default=0, ge=0, le=32)
    allowed_tools: list[str] = Field(default_factory=list)


class DeepAgentInterruptPolicy(BaseModel):
    """Interrupt and approval behavior."""

    approval_required_tools: list[str] = Field(default_factory=list)
    interrupt_on: list[str] = Field(default_factory=list)


class DeepAgentSandboxPolicy(BaseModel):
    """Sandbox/runtime isolation policy."""

    mode: Literal["inherit", "workspace_write", "sandboxed"] = "inherit"
    network_enabled: bool = False


class DeepAgentCostPolicy(BaseModel):
    """Cost rollup and budget policy."""

    budget_cents: int | None = Field(default=None, ge=0)
    ingest_enabled: bool = False


class DeepAgentCheckpointPolicy(BaseModel):
    """Checkpoint and restart safety policy."""

    enabled: bool = False
    durable_store: Literal["runtime_state", "checkpoint_store"] = "runtime_state"


class DeepAgentHarnessConfig(BaseModel):
    """Typed manifest for the staged Deep Agent runtime profile."""

    identity: DeepAgentIdentity
    provider_policy: DeepAgentProviderPolicy
    backend_policy: DeepAgentBackendPolicy = Field(default_factory=DeepAgentBackendPolicy)
    enabled_tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    memory_policy: DeepAgentMemoryPolicy = Field(default_factory=DeepAgentMemoryPolicy)
    subagent_policy: DeepAgentSubagentPolicy = Field(default_factory=DeepAgentSubagentPolicy)
    async_subagent_policy: DeepAgentSubagentPolicy = Field(default_factory=DeepAgentSubagentPolicy)
    interrupt_policy: DeepAgentInterruptPolicy = Field(default_factory=DeepAgentInterruptPolicy)
    sandbox_policy: DeepAgentSandboxPolicy = Field(default_factory=DeepAgentSandboxPolicy)
    cost_policy: DeepAgentCostPolicy = Field(default_factory=DeepAgentCostPolicy)
    checkpoint_policy: DeepAgentCheckpointPolicy = Field(default_factory=DeepAgentCheckpointPolicy)
    feature_flags: DeepAgentFeatureFlags = Field(default_factory=DeepAgentFeatureFlags)

    @field_validator("enabled_tools", "skills", mode="before")
    @classmethod
    def _coerce_string_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]


def deep_agent_harness_config_from_agent_config(
    config: AgentConfig,
    *,
    env: Mapping[str, str] | None = None,
) -> DeepAgentHarnessConfig:
    """Build a default-off harness manifest from the canonical AgentConfig."""

    raw_manifest = config.metadata.get("deep_agent_harness")
    if isinstance(raw_manifest, dict):
        return DeepAgentHarnessConfig.model_validate(raw_manifest)

    raw_skills = config.metadata.get("skills", [])
    return DeepAgentHarnessConfig(
        identity=DeepAgentIdentity(
            agent_id=config.id,
            agent_name=config.name,
            agent_role=config.role,
            session_id=config.metadata.get("session_id"),
            task_id=config.metadata.get("task_id"),
            run_id=config.metadata.get("run_id"),
        ),
        provider_policy=DeepAgentProviderPolicy(
            provider=config.provider,
            model=config.model,
            max_turns=config.max_turns,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            context_budget=config.context_budget,
        ),
        enabled_tools=list(config.tools),
        skills=[str(item) for item in raw_skills] if isinstance(raw_skills, list) else [],
        feature_flags=DeepAgentFeatureFlags.from_env(env),
    )
