from __future__ import annotations

from pathlib import Path

from dharma_swarm.routing_fusion_inventory import (
    CORE_ROUTING_MODULES,
    DIRECT_PROVIDER_CALL_ALLOWLIST,
    FIRST_BYPASS_SURFACES,
    build_inventory,
    unallowlisted_provider_bypasses,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_routing_fusion_inventory_scans_the_whole_source_tree() -> None:
    inventory = build_inventory(REPO_ROOT)

    assert inventory["counts"]["dharma_swarm_python_modules"] >= 500
    assert inventory["counts"]["core_routing_modules"] == len(CORE_ROUTING_MODULES)
    assert inventory["counts"]["direct_provider_call_suspects"] >= len(
        FIRST_BYPASS_SURFACES
    )
    assert set(FIRST_BYPASS_SURFACES).issubset(set(DIRECT_PROVIDER_CALL_ALLOWLIST))


def test_no_new_direct_provider_bypass_without_allowlist_update() -> None:
    assert unallowlisted_provider_bypasses(REPO_ROOT) == []


def test_first_fusion_surfaces_are_in_the_current_allowlist() -> None:
    assert set(FIRST_BYPASS_SURFACES).issubset(set(DIRECT_PROVIDER_CALL_ALLOWLIST))
