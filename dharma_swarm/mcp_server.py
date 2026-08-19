"""MCP Server — exposes DHARMA SWARM operations as MCP tools.

Requires the `mcp` optional dependency: pip install dharma-swarm[mcp]
"""

from __future__ import annotations

import json
import logging
from typing import Any

from dharma_swarm.models import AgentRole, TaskPriority
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity

logger = logging.getLogger(__name__)

# Consequential (mutating) tools; the read paths stay receipt-free.
MUTATING_MCP_TOOLS = ("spawn_agent", "create_task", "store_memory")


class McpToolSpine:
    """Spine wiring for the MCP tool boundary.

    Mints an ExecutionIdentity per consequential tool call and records
    side-effect intent/completion receipts in the runtime ledger. Fail-open:
    a broken store must never break the tool call — failures are counted
    (``audit_failures``), never silently swallowed.
    """

    def __init__(self, runtime_state: RuntimeStateStore | None) -> None:
        self._runtime_state = runtime_state
        self.audit_failures = 0

    def begin(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> tuple[ExecutionIdentity | None, str]:
        if self._runtime_state is None or tool_name not in MUTATING_MCP_TOOLS:
            return None, ""
        identity = ExecutionIdentity.new(
            task_id=f"mcp:{tool_name}",
            agent_id="mcp_client",
            metadata={"surface": "mcp_tool_access"},
        )
        effect_key = f"mcp:{tool_name}:{identity.run_id}"
        try:
            self._runtime_state.record_execution_identity_sync(
                identity,
                source="mcp_server.call_tool",
                metadata={"tool": tool_name},
            )
            self._runtime_state.record_side_effect_intent_sync(
                identity,
                effect_key,
                # Argument KEYS only: values may be large or sensitive.
                payload={"tool": tool_name, "argument_keys": sorted(arguments)},
            )
        except Exception:
            self.audit_failures += 1
            logger.warning(
                "mcp_server: spine intent receipt failed for %s; executing"
                " WITHOUT receipts",
                tool_name,
                exc_info=True,
            )
            return None, ""
        return identity, effect_key

    def complete(
        self,
        identity: ExecutionIdentity | None,
        effect_key: str,
        *,
        status: str = "completed",
    ) -> None:
        if identity is None or not effect_key or self._runtime_state is None:
            return
        try:
            self._runtime_state.record_side_effect_complete_sync(
                identity, effect_key, status=status
            )
        except Exception:
            self.audit_failures += 1
            logger.warning(
                "mcp_server: spine completion receipt failed for %s",
                effect_key,
                exc_info=True,
            )


def create_mcp_server(
    state_dir: str = ".dharma",
    *,
    runtime_state: RuntimeStateStore | None = None,
):
    """Create an MCP server with swarm tools.

    Returns the server instance. Call server.run() to start.
    Raises ImportError if mcp package is not installed.
    """
    try:
        from mcp.server import Server
        from mcp.types import Tool, TextContent
    except ImportError:
        raise ImportError(
            "MCP support requires the 'mcp' package. "
            "Install with: pip install dharma-swarm[mcp]"
        )

    server = Server("dharma-swarm")
    # Receipts land in the canonical runtime ledger unless a store is injected.
    spine = McpToolSpine(runtime_state if runtime_state is not None else RuntimeStateStore())
    _swarm = None

    async def _get_swarm():
        nonlocal _swarm
        if _swarm is None:
            from dharma_swarm.swarm import SwarmManager
            _swarm = SwarmManager(state_dir=state_dir)
            await _swarm.init()
        return _swarm

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="swarm_status",
                description="Get current DHARMA SWARM status",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="spawn_agent",
                description="Spawn a new agent in the swarm",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Agent name"},
                        "role": {
                            "type": "string",
                            "enum": [r.value for r in AgentRole],
                            "default": "general",
                        },
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="create_task",
                description="Create a new task",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string", "default": ""},
                        "priority": {
                            "type": "string",
                            "enum": [p.value for p in TaskPriority],
                            "default": "normal",
                        },
                    },
                    "required": ["title"],
                },
            ),
            Tool(
                name="list_tasks",
                description="List all tasks",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="store_memory",
                description="Store a memory in the swarm's strange loop",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="recall_memory",
                description="Recall recent memories",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 10},
                    },
                },
            ),
            Tool(
                name="graph_nexus_query",
                description="Query all dharma_swarm graphs for information about a concept or term",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "term": {"type": "string", "description": "Concept or term to search for"},
                    },
                    "required": ["term"],
                },
            ),
            Tool(
                name="concept_blast_radius",
                description="Compute cross-graph impact of changing or removing a concept",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "concept": {"type": "string", "description": "Concept name to analyze"},
                    },
                    "required": ["concept"],
                },
            ),
            Tool(
                name="telos_status",
                description="Show strategic objectives, key results, and progress",
                inputSchema={"type": "object", "properties": {}},
            ),
            # Sarathi — the apex chief-of-staff seat. READ-ONLY by design: these
            # make her legible to any MCP client (Claude, Codex, any model), but
            # none of them dispatch work. Delegation must go through
            # sarathi.delegate_all so the reversibility gate runs first; exposing
            # a dispatch tool here would let an MCP caller bypass that gate.
            Tool(
                name="sarathi_status",
                description=(
                    "Sarathi apex seat status: honest wake_loop_active / alive_claim "
                    "flags, pulse, brief and organ scoreboard. Read-only projection."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="sarathi_roster",
                description="List the sub-holons Sarathi can delegate to.",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        # Swarm-free tools dispatch BEFORE the bootstrap. `SwarmManager.init()`
        # mutates disk — it mkdirs the state dir, unlinks EMERGENCY_HOLD
        # (`swarm.py:563-569`) and seeds the Telos/Concept graphs — so booting it
        # to answer a read-only question would clear an operator's emergency hold
        # as a side effect of merely looking. These two read the organ package
        # directly and need no swarm.
        if name == "sarathi_status":
            from dharma_swarm.holon_system.sarathi import gateway_snapshot
            snapshot = gateway_snapshot()
            return [TextContent(type="text", text=json.dumps(snapshot, indent=2, default=str))]

        if name == "sarathi_roster":
            from dharma_swarm.holon_system.sarathi import load_roster
            return [TextContent(type="text", text=json.dumps(list(load_roster()), indent=2))]

        swarm = await _get_swarm()
        identity, effect_key = spine.begin(name, arguments)
        try:
            result = await _dispatch_tool(name, arguments, swarm)
        except Exception:
            spine.complete(identity, effect_key, status="failed")
            raise
        spine.complete(identity, effect_key)
        return result

    async def _dispatch_tool(
        name: str, arguments: dict[str, Any], swarm: Any
    ) -> list[TextContent]:
        if name == "swarm_status":
            state = await swarm.status()
            return [TextContent(type="text", text=state.model_dump_json(indent=2))]

        elif name == "spawn_agent":
            role = AgentRole(arguments.get("role", "general"))
            agent = await swarm.spawn_agent(
                name=arguments["name"], role=role
            )
            return [TextContent(
                type="text",
                text=json.dumps({"id": agent.id, "name": agent.name, "status": agent.status.value}),
            )]

        elif name == "create_task":
            priority = TaskPriority(arguments.get("priority", "normal"))
            task = await swarm.create_task(
                title=arguments["title"],
                description=arguments.get("description", ""),
                priority=priority,
            )
            return [TextContent(
                type="text",
                text=json.dumps({"id": task.id, "title": task.title, "status": task.status.value}),
            )]

        elif name == "list_tasks":
            tasks = await swarm.list_tasks()
            data = [{"id": t.id, "title": t.title, "status": t.status.value} for t in tasks]
            return [TextContent(type="text", text=json.dumps(data, indent=2))]

        elif name == "store_memory":
            await swarm.remember(arguments["content"])
            return [TextContent(type="text", text="Stored.")]

        elif name == "recall_memory":
            entries = await swarm.recall(limit=arguments.get("limit", 10))
            data = [{"layer": e.layer.value, "content": e.content[:200]} for e in entries]
            return [TextContent(type="text", text=json.dumps(data, indent=2))]

        elif name == "graph_nexus_query":
            from dharma_swarm.graph_nexus import GraphNexus
            async with GraphNexus() as nexus:
                result = await nexus.query_about(arguments["term"])
            return [TextContent(type="text", text=result.model_dump_json(indent=2))]

        elif name == "concept_blast_radius":
            from dharma_swarm.concept_blast_radius import ConceptBlastRadius
            cbr = ConceptBlastRadius()
            result = await cbr.compute_by_name(arguments["concept"])
            return [TextContent(type="text", text=result.model_dump_json(indent=2))]

        elif name == "telos_status":
            from dharma_swarm.telos_graph import TelosGraph
            telos = TelosGraph()
            await telos.load()
            summary = telos.strategy_map_summary()
            return [TextContent(type="text", text=json.dumps(summary, indent=2, default=str))]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server
