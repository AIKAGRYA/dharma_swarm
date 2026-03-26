"""Agent runner utility functions — extracted from agent_runner.py

This module contains helper functions that were previously inline in
agent_runner.py, reducing its size from 1965 lines to improve maintainability.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.config import DEFAULT_CONFIG as _SWARM_CFG
from dharma_swarm.models import AgentConfig, AgentState, LLMRequest, LLMResponse, Task, TaskPriority

# Constants moved from agent_runner.py
_HEARTBEAT_THRESHOLD = timedelta(seconds=_SWARM_CFG.agent.heartbeat_threshold_seconds)
_ERROR_PREFIXES = (
    "error",
    "api error:",
    "timeout: exceeded limit",
    "not logged in · please run /login",
    "openrouter error:",
    "no openrouter_api_key set",
)
_PRIORITY_SALIENCE = {
    TaskPriority.LOW: 0.30,
    TaskPriority.NORMAL: 0.50,
    TaskPriority.HIGH: 0.70,
    TaskPriority.URGENT: 0.90,
}
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_TOOLING_HINTS = (
    "apply patch", "bug", "code", "edit", "file", "fix", "implement",
    "module", "patch", "pytest", "refactor", "script", "test",
)
_FRONTIER_HINTS = (
    "analyze", "architecture", "compare", "debug", "design", "evaluate",
    "incident", "investigate", "prove", "research", "root cause", "security",
)
_PRIVILEGED_HINTS = (
    "credential", "delete", "deploy", "drop table", "kill ", "launchctl",
    "production", "rm -rf", "secret", "ssh", "sudo",
)


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


def clamp01(value: float) -> float:
    """Clamp value to [0, 1] range."""
    return max(0.0, min(1.0, value))


def coerce_bool(value: Any) -> bool | None:
    """Coerce various inputs to boolean or None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.lower().strip()
        if lower in _TRUE_VALUES:
            return True
        if lower in _FALSE_VALUES:
            return False
    try:
        return bool(int(value))
    except (ValueError, TypeError):
        return None


def task_metadata(task: Task) -> dict[str, Any]:
    """Extract metadata from task."""
    return getattr(task, "metadata", {}) or {}


def task_text(task: Task) -> str:
    """Extract text content from task."""
    return getattr(task, "text", "") or ""


def task_action_name(task: Task) -> str:
    """Extract action name from task."""
    metadata = task_metadata(task)
    action = metadata.get("action", "")
    if isinstance(action, str):
        return action.lower().strip()
    return ""


def metadata_number(metadata: dict[str, Any], *keys: str) -> float | None:
    """Extract numeric value from metadata by key."""
    for key in keys:
        if key in metadata:
            try:
                return float(metadata[key])
            except (ValueError, TypeError):
                continue
    return None


def metadata_bool(metadata: dict[str, Any], *keys: str) -> bool | None:
    """Extract boolean value from metadata by key."""
    for key in keys:
        if key in metadata:
            return coerce_bool(metadata[key])
    return None


def priority_score(priority: TaskPriority) -> float:
    """Return salience score for task priority."""
    return _PRIORITY_SALIENCE.get(priority, 0.50)


def supports_provider_method(provider: object | None, method_name: str) -> bool:
    """Check if provider supports a given method."""
    return provider is not None and hasattr(provider, method_name)


def is_routed_provider(provider: object | None) -> bool:
    """Check if provider has route_request method."""
    return supports_provider_method(provider, "route_request")


def requires_tooling(task: Task, config: AgentConfig) -> bool:
    """Determine if task requires tooling capability."""
    metadata = task_metadata(task)
    
    # Check explicit flags
    if metadata_bool(metadata, "tooling", "requires_tooling"):
        return True
    
    # Check action name
    action = task_action_name(task)
    if action and any(h in action for h in _TOOLING_HINTS):
        return True
    
    # Check task text
    text = task_text(task).lower()
    if any(h in text for h in _TOOLING_HINTS):
        return True
    
    return False


def requires_frontier_precision(task: Task, config: AgentConfig) -> bool:
    """Determine if task requires frontier-level precision."""
    metadata = task_metadata(task)
    
    # Check explicit flags
    if metadata_bool(metadata, "frontier", "requires_frontier"):
        return True
    if metadata.get("priority") == TaskPriority.URGENT:
        return True
    
    # Check action name
    action = task_action_name(task)
    if action and any(h in action for h in _FRONTIER_HINTS):
        return True
    
    # Check task text
    text = task_text(task).lower()
    if any(h in text for h in _FRONTIER_HINTS):
        return True
    
    # Check for complexity indicators
    text_len = len(text)
    if text_len > 2000:  # Long tasks likely need frontier
        return True
    
    return False


def is_privileged_action(task: Task) -> bool:
    """Check if task involves privileged/dangerous operations."""
    text = task_text(task).lower()
    metadata = task_metadata(task)
    action = task_action_name(task)
    
    # Check privileged hints in text
    if any(h in text for h in _PRIVILEGED_HINTS):
        return True
    
    # Check action name
    if action and any(h in action for h in _PRIVILEGED_HINTS):
        return True
    
    # Check metadata flags
    if metadata_bool(metadata, "privileged", "dangerous", "destructive"):
        return True
    
    return False


def allow_provider_routing(task: Task, config: AgentConfig) -> bool:
    """Determine if provider routing is allowed for this task."""
    metadata = task_metadata(task)
    
    # Check explicit disable
    if metadata_bool(metadata, "no_route", "disable_routing") is True:
        return False
    
    # Check forced provider
    if metadata.get("provider") or metadata.get("force_provider"):
        return False
    
    # Privileged actions don't route
    if is_privileged_action(task):
        return False
    
    return True


def parse_provider_types(value: Any) -> list:
    """Parse provider types from various input formats."""
    from dharma_swarm.models import ProviderType
    
    if value is None:
        return []
    
    if isinstance(value, ProviderType):
        return [value]
    
    if isinstance(value, str):
        try:
            return [ProviderType(value.lower())]
        except ValueError:
            return []
    
    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            if isinstance(item, ProviderType):
                result.append(item)
            elif isinstance(item, str):
                try:
                    result.append(ProviderType(item.lower()))
                except ValueError:
                    continue
        return result
    
    return []


def available_provider_types(
    available: list | None = None,
    requires_tooling: bool = False,
    requires_frontier: bool = False,
) -> list:
    """Filter available providers by capability requirements."""
    from dharma_swarm.models import ProviderType
    
    if available is None:
        # Default to all providers
        available = list(ProviderType)
    
    result = []
    for provider in available:
        # Skip Ollama for frontier tasks (unless explicitly allowed)
        if requires_frontier and provider == ProviderType.OLLAMA:
            continue
        result.append(provider)
    
    return result


def estimate_requested_tokens(request: LLMRequest, *, requires_tooling: bool = False) -> int:
    """Estimate token count for a request."""
    total_chars = 0
    
    for msg in request.messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text", "")
                    if isinstance(text, str):
                        total_chars += len(text)
    
    # Rough estimate: 4 chars per token
    base_tokens = total_chars // 4
    
    # Add overhead for tooling
    if requires_tooling:
        base_tokens += 1000
    
    return max(base_tokens, 100)


def response_total_tokens(response: LLMResponse | None) -> int:
    """Extract total token count from response."""
    if response is None:
        return 0
    usage = getattr(response, "usage", None) or {}
    prompt = usage.get("prompt_tokens", 0) or 0
    completion = usage.get("completion_tokens", 0) or 0
    return prompt + completion


def feedback_quality_score(
    success: bool | None,
    error_prefix: str | None,
    response_time_sec: float,
    response: LLMResponse | None,
) -> float:
    """Calculate quality score for provider feedback."""
    if success is False:
        return 0.0
    
    if error_prefix:
        return 0.1
    
    score = 1.0
    
    # Penalize slow responses
    if response_time_sec > 30:
        score *= 0.9
    if response_time_sec > 60:
        score *= 0.8
    
    # Bonus for complete responses
    if response and response.finish_reason == "stop":
        score *= 1.1
    
    return min(score, 1.0)


def state_from_config(config: AgentConfig) -> AgentState:
    """Build initial agent state from config."""
    return AgentState(
        agent_id=config.agent_id,
        name=config.name,
        role=config.role,
        status="idle",
        current_task=None,
        last_heartbeat=utc_now(),
        metadata={},
    )


def build_self_state_block(agent_name: str) -> str:
    """Build self-state description for agent prompts."""
    return f"""You are {agent_name}, an autonomous agent in the DHARMA SWARM system.

Your role is to execute tasks with awareness of the broader system context.
You have access to:
- Stigmergic marks left by other agents
- Your own memory bank across three tiers
- The message bus for coordination
- Provider routing for LLM access

Operate with computational humility: acknowledge uncertainty, prefer recognition
over construction, and leave marks that help future agents."""


def resolve_config_state_dir(config: AgentConfig) -> Path | None:
    """Resolve state directory from config."""
    if hasattr(config, "state_dir") and config.state_dir:
        return Path(config.state_dir)
    return None


def resolve_prompt_state_dir(task: Task, config: AgentConfig) -> Path | None:
    """Resolve state directory from task prompt."""
    metadata = task_metadata(task)
    state_dir = metadata.get("state_dir") or metadata.get("STATE_DIR")
    if state_dir:
        return Path(state_dir)
    return resolve_config_state_dir(config)


def resolve_agent_registry_dir(task: Task, config: AgentConfig) -> Path | None:
    """Resolve agent registry directory."""
    # Check task metadata
    metadata = task_metadata(task)
    registry = metadata.get("agent_registry") or metadata.get("AGENT_REGISTRY")
    if registry:
        return Path(registry)
    
    # Check config
    if hasattr(config, "agent_registry") and config.agent_registry:
        return Path(config.agent_registry)
    
    # Default
    return None
