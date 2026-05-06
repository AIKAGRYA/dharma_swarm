from __future__ import annotations

import ast
from pathlib import Path

from dharma_swarm.models import AgentConfig, AgentRole, ProviderType


IDENTITY_SHAPED_CLASSES = {
    "AgentConfig",
    "AgentConfig_",
    "AgentIdentity",
    "AgentIdentityRecord",
    "AgentProfile",
}


EXPECTED_IDENTITY_SURFACES = {
    "api/graphql/schema.py:AgentIdentity",
    "api/routers/graphql_router.py:AgentIdentity",
    "dharma_swarm/agent_registry.py:AgentIdentity",
    "dharma_swarm/autonomous_agent.py:AgentIdentity",
    "dharma_swarm/config.py:AgentConfig_",
    "dharma_swarm/models.py:AgentConfig",
    "dharma_swarm/profiles.py:AgentProfile",
    "dharma_swarm/telemetry_plane.py:AgentIdentityRecord",
    "dharma_swarm/transcendence.py:AgentConfig",
}


def _class_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }


def test_agent_identity_surfaces_are_explicitly_inventoried() -> None:
    """Prevent new agent identity dialects from appearing without review."""

    found: set[str] = set()
    for root in (Path("dharma_swarm"), Path("api")):
        for path in root.rglob("*.py"):
            for class_name in _class_names(path):
                if class_name in IDENTITY_SHAPED_CLASSES:
                    found.add(f"{path.as_posix()}:{class_name}")

    assert found == EXPECTED_IDENTITY_SURFACES


def test_agent_config_accepts_legacy_string_identity_fields() -> None:
    """AgentConfig is the current runtime constructor and string bridge."""

    config = AgentConfig(
        name="loop1-worker",
        role="coder",
        provider="openrouter_free",
        model="test-model",
    )

    assert config.role is AgentRole.CODER
    assert config.provider is ProviderType.OPENROUTER_FREE
