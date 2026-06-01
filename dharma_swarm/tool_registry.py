"""Tool Registry — central singleton for self-registering executable tools.

Inspired by Hermes Agent's tools/registry.py. Coexists with SkillRegistry:
  - SkillRegistry: human-readable SKILL.md role definitions (agent personas)
  - ToolRegistry: programmatic tool registration (executable actions)

Tools self-register at import time via ``registry.register()``.
The registry handles schema collection, dispatch, availability checking,
and error wrapping.

Import chain (circular-import safe):
    tool_registry.py  (no deps on tool files)
           ^
    tools/*.py  (import registry at module level, call register())
           ^
    swarm.py / dgc_cli.py  (import registry + trigger tool discovery)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Optional

from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.adapters import identity_from_carrier
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity

logger = logging.getLogger(__name__)


class ToolEntry:
    """Metadata for a single registered tool."""

    __slots__ = (
        "name", "toolset", "schema", "handler", "check_fn",
        "requires_env", "is_async", "description",
    )

    def __init__(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None,
        requires_env: list[str],
        is_async: bool,
        description: str,
    ):
        self.name = name
        self.toolset = toolset
        self.schema = schema
        self.handler = handler
        self.check_fn = check_fn
        self.requires_env = requires_env
        self.is_async = is_async
        self.description = description


class ToolRegistry:
    """Singleton registry that collects tool schemas + handlers.

    Tools register at module-import time; the swarm queries the registry
    for schemas and dispatches calls through it.
    """

    def __init__(
        self,
        *,
        runtime_state: RuntimeStateStore | None = None,
        require_identity: bool = False,
    ) -> None:
        self._tools: dict[str, ToolEntry] = {}
        self._toolset_checks: dict[str, Callable] = {}
        self._runtime_state = runtime_state
        self._require_identity = require_identity

    # ── Registration ─────────────────────────────────────────────────

    def register(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None = None,
        requires_env: list[str] | None = None,
        is_async: bool = False,
        description: str = "",
    ) -> None:
        """Register a tool. Called at module-import time by each tool file."""
        self._tools[name] = ToolEntry(
            name=name,
            toolset=toolset,
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            requires_env=requires_env or [],
            is_async=is_async,
            description=description or schema.get("description", ""),
        )
        if check_fn and toolset not in self._toolset_checks:
            self._toolset_checks[toolset] = check_fn

    # ── Schema retrieval ─────────────────────────────────────────────

    def get_definitions(
        self,
        tool_names: set[str] | None = None,
        quiet: bool = False,
    ) -> list[dict]:
        """Return OpenAI-format tool schemas for requested tools.

        Only tools whose ``check_fn()`` passes are included.
        If *tool_names* is None, returns all available tools.
        """
        targets = sorted(tool_names) if tool_names else sorted(self._tools)
        result: list[dict] = []
        for name in targets:
            entry = self._tools.get(name)
            if not entry:
                continue
            if entry.check_fn:
                try:
                    if not entry.check_fn():
                        if not quiet:
                            logger.debug("Tool %s unavailable (check failed)", name)
                        continue
                except Exception:
                    if not quiet:
                        logger.debug("Tool %s check raised; skipping", name)
                    continue
            result.append({"type": "function", "function": entry.schema})
        return result

    # ── Dispatch ──────────────────────────────────────────────────────

    def _resolve_identity(
        self,
        name: str,
        args: dict,
        *,
        runtime_state: RuntimeStateStore | None,
        require_identity: bool,
        execution_identity: ExecutionIdentity | None,
        metadata: dict[str, Any] | None,
    ) -> ExecutionIdentity | None:
        if require_identity and runtime_state is None:
            raise MissingExecutionIdentity("RuntimeStateStore is required when ToolRegistry requires ExecutionIdentity")
        if execution_identity is not None:
            return execution_identity.require_for_dispatch()
        carrier = {
            "tool_call_id": args.get("tool_call_id") or f"tool:{name}",
            "tool_name": name,
            "task_id": args.get("task_id"),
            "agent_id": args.get("agent_id"),
            "metadata": metadata or args.get("metadata") or {},
        }
        if require_identity:
            return identity_from_carrier(carrier, surface="tool", require_existing=True)
        if runtime_state is not None:
            return identity_from_carrier(carrier, surface="tool")
        return ExecutionIdentity.from_metadata(carrier["metadata"], require=False)

    def dispatch(self, name: str, args: dict, **kwargs: Any) -> str:
        """Execute a tool handler by name.

        Async handlers are bridged automatically. All exceptions are
        caught and returned as ``{"error": "..."}`` JSON strings.
        """
        entry = self._tools.get(name)
        if not entry:
            return json.dumps({"error": f"Unknown tool: {name}"})
        runtime_state = kwargs.pop("runtime_state", self._runtime_state)
        require_identity = kwargs.pop("require_identity", self._require_identity)
        execution_identity = kwargs.pop("execution_identity", None)
        metadata = kwargs.pop("metadata", None)
        identity: ExecutionIdentity | None = None
        side_effect_key = f"tool_registry.dispatch:{name}"
        try:
            identity = self._resolve_identity(
                name,
                args,
                runtime_state=runtime_state,
                require_identity=require_identity,
                execution_identity=execution_identity,
                metadata=metadata,
            )
            if identity is not None:
                side_effect_key = f"tool_registry.dispatch:{name}:{identity.task_id}"
            if identity is not None and runtime_state is not None:
                runtime_state.record_execution_identity_sync(
                    identity,
                    source="tool_registry.dispatch",
                    metadata={"tool_name": name},
                )
                runtime_state.record_side_effect_intent_sync(
                    identity,
                    side_effect_key,
                    payload={"tool_name": name},
                )
            if entry.is_async:
                loop: asyncio.AbstractEventLoop | None = None
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    pass
                if loop and loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(asyncio.run, entry.handler(args, **kwargs))
                        result = future.result(timeout=120)
                else:
                    result = asyncio.run(entry.handler(args, **kwargs))
            else:
                result = entry.handler(args, **kwargs)
            if identity is not None and runtime_state is not None:
                runtime_state.record_side_effect_complete_sync(
                    identity,
                    side_effect_key,
                    result_receipt_id=f"tool:{name}",
                    payload={"tool_name": name},
                )
            return result
        except Exception as e:
            if identity is not None and runtime_state is not None:
                try:
                    runtime_state.record_side_effect_complete_sync(
                        identity,
                        side_effect_key,
                        status="failed",
                        payload={"tool_name": name, "error": type(e).__name__},
                    )
                except Exception:
                    logger.exception("Tool %s failed to record runtime failure receipt", name)
            logger.exception("Tool %s dispatch error: %s", name, e)
            return json.dumps({"error": f"Tool execution failed: {type(e).__name__}: {e}"})

    # ── Query helpers ─────────────────────────────────────────────────

    def get_all_tool_names(self) -> list[str]:
        """Return sorted list of all registered tool names."""
        return sorted(self._tools.keys())

    def get_toolset_for_tool(self, name: str) -> Optional[str]:
        """Return the toolset a tool belongs to, or None."""
        entry = self._tools.get(name)
        return entry.toolset if entry else None

    def get_tool_to_toolset_map(self) -> dict[str, str]:
        """Return ``{tool_name: toolset_name}`` for every registered tool."""
        return {name: e.toolset for name, e in self._tools.items()}

    def is_toolset_available(self, toolset: str) -> bool:
        """Check if a toolset's requirements are met."""
        check = self._toolset_checks.get(toolset)
        if not check:
            return True
        try:
            return bool(check())
        except Exception:
            logger.debug("Toolset %s check raised; marking unavailable", toolset)
            return False

    def check_toolset_requirements(self) -> dict[str, bool]:
        """Return ``{toolset: available_bool}`` for every toolset."""
        toolsets = set(e.toolset for e in self._tools.values())
        return {ts: self.is_toolset_available(ts) for ts in sorted(toolsets)}

    def get_available_toolsets(self) -> dict[str, dict]:
        """Return toolset metadata for UI display."""
        toolsets: dict[str, dict] = {}
        for entry in self._tools.values():
            ts = entry.toolset
            if ts not in toolsets:
                toolsets[ts] = {
                    "available": self.is_toolset_available(ts),
                    "tools": [],
                    "requirements": [],
                }
            toolsets[ts]["tools"].append(entry.name)
            if entry.requires_env:
                for env in entry.requires_env:
                    if env not in toolsets[ts]["requirements"]:
                        toolsets[ts]["requirements"].append(env)
        return toolsets

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# Module-level singleton
registry = ToolRegistry()
