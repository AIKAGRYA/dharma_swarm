"""MCP Server — exposes DHARMA SWARM operations as MCP tools.

Requires the `mcp` optional dependency: pip install dharma-swarm[mcp]
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dharma_swarm.models import AgentRole, TaskPriority
from dharma_swarm.operator_action_gateway import OperatorActionGateway
from dharma_swarm.operator_views import OperatorViews
from dharma_swarm.runtime_state import RuntimeStateStore


def _runtime_db_for_state_dir(state_dir: str, runtime_db_path: str | Path | None = None) -> Path:
    if runtime_db_path is not None:
        return Path(runtime_db_path).expanduser()
    return Path(state_dir).expanduser() / "state" / "runtime.db"


def create_mcp_server(state_dir: str = ".dharma", runtime_db_path: str | Path | None = None):
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
    _swarm = None
    runtime_state = RuntimeStateStore(_runtime_db_for_state_dir(state_dir, runtime_db_path))
    action_gateway = OperatorActionGateway(runtime_state)

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
            Tool(
                name="operator_runtime_overview",
                description="Read the canonical runtime/operator state overview",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="operator_recent_actions",
                description="Read recent governed operator actions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20},
                    },
                },
            ),
            Tool(
                name="operator_pending_actions",
                description="Read pending operator actions waiting for approval",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20},
                    },
                },
            ),
            Tool(
                name="propose_operator_action",
                description="Create a governed action proposal without executing it",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action_name": {"type": "string"},
                        "reason": {"type": "string", "default": ""},
                        "target": {"type": "string", "default": ""},
                        "risk": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "default": "medium",
                        },
                        "payload": {"type": "object", "default": {}},
                    },
                    "required": ["action_name"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        swarm = await _get_swarm()

        if name == "swarm_status":
            state = await swarm.status()
            return [TextContent(type="text", text=state.model_dump_json(indent=2))]

        elif name == "spawn_agent":
            role = AgentRole(arguments.get("role", "general"))
            proposal = await action_gateway.submit_proposal(
                action_name="mcp.spawn_agent",
                actor="mcp",
                reason=f"spawn agent {arguments['name']}",
                payload={"tool": name, "arguments": dict(arguments)},
                source="mcp_server",
                target="swarm.spawn_agent",
                risk="medium",
                approval_required=False,
            )
            agent = await swarm.spawn_agent(
                name=arguments["name"], role=role
            )
            await action_gateway.record_outcome(
                proposal.action.action_id,
                status="executed",
                outcome={"agent_id": agent.id, "agent_name": agent.name, "status": agent.status.value},
            )
            return [TextContent(
                type="text",
                text=json.dumps({"id": agent.id, "name": agent.name, "status": agent.status.value}),
            )]

        elif name == "create_task":
            priority = TaskPriority(arguments.get("priority", "normal"))
            proposal = await action_gateway.submit_proposal(
                action_name="mcp.create_task",
                actor="mcp",
                reason=str(arguments.get("title", "") or "create task"),
                payload={"tool": name, "arguments": dict(arguments)},
                source="mcp_server",
                target="swarm.create_task",
                risk="medium",
                approval_required=False,
            )
            task = await swarm.create_task(
                title=arguments["title"],
                description=arguments.get("description", ""),
                priority=priority,
            )
            await action_gateway.record_outcome(
                proposal.action.action_id,
                status="executed",
                outcome={"task_id": task.id, "title": task.title, "status": task.status.value},
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

        elif name == "operator_runtime_overview":
            views = OperatorViews(runtime_state)
            overview = await views.runtime_overview()
            pending = await views.pending_operator_actions(limit=50)
            data = {
                "sessions": overview.sessions,
                "claims": overview.claims,
                "active_claims": overview.active_claims,
                "acknowledged_claims": overview.acknowledged_claims,
                "runs": overview.runs,
                "active_runs": overview.active_runs,
                "artifacts": overview.artifacts,
                "promoted_facts": overview.promoted_facts,
                "context_bundles": overview.context_bundles,
                "operator_actions": overview.operator_actions,
                "pending_operator_actions": len(pending),
            }
            return [TextContent(type="text", text=json.dumps(data, indent=2))]

        elif name == "operator_recent_actions":
            views = OperatorViews(runtime_state)
            actions = await views.recent_operator_actions(limit=int(arguments.get("limit", 20) or 20))
            return [TextContent(type="text", text=json.dumps(actions, indent=2, default=str))]

        elif name == "operator_pending_actions":
            views = OperatorViews(runtime_state)
            actions = await views.pending_operator_actions(limit=int(arguments.get("limit", 20) or 20))
            return [TextContent(type="text", text=json.dumps(actions, indent=2, default=str))]

        elif name == "propose_operator_action":
            proposal = await action_gateway.submit_proposal(
                action_name=str(arguments["action_name"]),
                actor="mcp",
                reason=str(arguments.get("reason", "") or ""),
                payload=dict(arguments.get("payload") or {}),
                source="mcp_server",
                target=str(arguments.get("target", "") or ""),
                risk=str(arguments.get("risk", "medium") or "medium"),
                approval_required=True,
                telos_check=True,
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "action_id": proposal.action.action_id,
                            "status": proposal.action.payload["lifecycle"]["status"],
                            "warrant": proposal.action.payload["warrant"],
                            "gate": proposal.action.payload["gate"],
                        },
                        indent=2,
                        default=str,
                    ),
                )
            ]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server
