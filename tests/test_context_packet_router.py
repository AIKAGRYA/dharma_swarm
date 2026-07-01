from __future__ import annotations

from scripts.governance.context_packet_router import (
    INDEX_PATH,
    packet_by_id,
    route_packets,
)


def test_context_packet_index_exists() -> None:
    assert INDEX_PATH.exists()


def test_routes_sab_topic_to_sab_packet() -> None:
    matches = route_packets("SAB First Spark flywheel witness receipt", top=1)
    assert matches
    assert matches[0].packet_id == "ctx.sab-flywheel"


def test_routes_runtime_provider_path_to_model_packet() -> None:
    matches = route_packets(
        "fix provider fallback",
        paths=("dharma_swarm/runtime_provider.py",),
        top=1,
    )
    assert matches
    assert matches[0].packet_id == "ctx.model-provider-routing"


def test_exact_packet_lookup_returns_file() -> None:
    packet = packet_by_id("ctx.memory-semantic-commons")
    assert packet is not None
    assert packet["file"] == "packets/03_memory_semantic_commons.md"
