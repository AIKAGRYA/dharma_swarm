from __future__ import annotations

import ast
from pathlib import Path


AGENT_FACING_DIRECT_PROVIDER_CALLS = {
    "api/routers/chat.py": 1,
    "dharma_swarm/autonomous_agent.py": 2,
}


def _call_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.append(func.id)
        elif isinstance(func, ast.Attribute):
            names.append(func.attr)

    return names


def test_shared_routing_load_bearing_surfaces_exist() -> None:
    """Swarm and AgentRunner already have the positive routed path."""

    swarm = Path("dharma_swarm/swarm.py").read_text(encoding="utf-8")
    agent_runner = Path("dharma_swarm/agent_runner.py").read_text(encoding="utf-8")

    assert "create_default_router()" in swarm
    assert "complete_for_task(" in agent_runner


def test_agent_facing_direct_provider_bypasses_are_explicitly_inventoried() -> None:
    """Keep known ModelRouter bypasses finite until the routing PR removes them."""

    actual = {
        path: _call_names(Path(path)).count("create_runtime_provider")
        for path in AGENT_FACING_DIRECT_PROVIDER_CALLS
    }

    assert actual == AGENT_FACING_DIRECT_PROVIDER_CALLS


def test_loop1_weave_doc_names_routing_bypass_targets() -> None:
    doc = Path("docs/governance/LOOP1_SUBSTRATE_WEAVE.md").read_text(encoding="utf-8")

    assert "dharma_swarm.autonomous_agent.AutonomousAgent" in doc
    assert "api.routers.chat" in doc
    assert "separate routing PR" in doc
