from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.fractal import (
    FractalRoom,
    RoomEconomy,
    RoomIdentity,
    RoomLaw,
    RoomMemory,
    RoomPulse,
    build_agentops_room,
    build_core_ops_room,
    build_revenue_wedge_room,
    room_from_dict,
    room_module_bindings,
    validate_human_yds_rating,
    validate_room,
    work_packet_scope_to_dict,
)


def test_core_room_validates_as_root_causal_membrane() -> None:
    room = build_core_ops_room()
    validation = room.validate()

    assert validation.ok
    assert room.room_id == "dharma-swarm-core"
    assert room.cell_id == "dharma-swarm-core"
    assert room.identity.kind == "root"
    assert room.identity.parent_id == ""
    assert "api/**" in room.law.forbidden_files
    assert "AI-assigned authoritative YDS" in room.law.forbidden_work


def test_room_round_trips_through_json_shape() -> None:
    room = build_agentops_room()
    payload = room.to_dict()
    encoded = json.dumps(payload)
    decoded = room_from_dict(json.loads(encoded))

    assert decoded == room
    assert decoded.law.allowed_files == ("scripts/governance/**", "docs/governance/**", "tests/**")
    assert decoded.memory.stigmergy_channels == ("agentops", "governance")


def test_module_bindings_ground_rooms_in_existing_repo_organs() -> None:
    bindings = {binding.layer: binding for binding in room_module_bindings()}

    assert "dharma_swarm/dharma_kernel.py" in bindings["telos"].modules
    assert "dharma_swarm/ontology.py" in bindings["ontology"].modules
    assert "dharma_swarm/task_board.py" in bindings["operation"].modules
    assert "dharma_swarm/signal_bus.py" in bindings["coordination"].modules
    assert "dharma_swarm/economic_engine.py" in bindings["economy"].modules
    assert "scripts/governance/kaizen_review_from_agentops.py" in bindings["learning"].modules
    assert bindings["human-quality"].room_contract.endswith("authoritative ratings.")


def test_active_room_without_law_is_warned_or_rejected() -> None:
    room = FractalRoom(
        identity=RoomIdentity(
            id="thin-room",
            kind="research",
            purpose="Explore a bounded question.",
            status="active",
            parent_id="dharma-swarm-core",
        ),
        law=RoomLaw(gates=(), allowed_work=(), forbidden_work=(), allowed_files=()),
    )

    validation = validate_room(room)

    assert "active room must declare at least one gate" in validation.errors
    assert "law.allowed_work is empty; operators cannot tell what the room is for" in validation.warnings
    assert "law.allowed_files is empty; AgentOps projection will not constrain repo scope" in validation.warnings


def test_venture_room_requires_economic_accountability() -> None:
    room = FractalRoom(
        identity=RoomIdentity(
            id="product-cell",
            kind="venture_cell",
            purpose="Try a customer-facing proof.",
            parent_id="dharma-swarm-core",
        ),
        law=RoomLaw(
            allowed_work=("customer discovery",),
            forbidden_work=("dashboard build before proof",),
            allowed_files=("docs/**",),
        ),
        economy=RoomEconomy(),
        memory=RoomMemory(memory_namespace="rooms/product-cell", report_paths=("reports/agentops",)),
        pulse=RoomPulse(next_packet_recommendation="interview one user"),
    )

    validation = room.validate()

    assert "venture/product/revenue rooms require economy.value_hypothesis" in validation.errors
    assert "venture/product/revenue rooms require kill_conditions" in validation.errors


def test_revenue_wedge_room_satisfies_five_law_minimum() -> None:
    room = build_revenue_wedge_room(room_id="paid-xray")
    validation = room.validate()

    assert validation.ok
    assert room.identity.kind == "venture_cell"
    assert room.economy.revenue_target_usd == 100.0
    assert room.economy.kill_conditions
    assert room.economy.spinout_conditions
    assert "spend_budget" in room.law.approval_required_for


def test_agentops_scope_projection_keeps_room_as_context_not_executor() -> None:
    room = build_agentops_room()
    scope = room.to_agentops_scope("Harden the work packet runner")
    payload = work_packet_scope_to_dict(scope)

    assert payload["room_id"] == "agentops"
    assert payload["metadata"]["cell_id"] == "agentops"
    assert payload["metadata"]["room_kind"] == "agentops"
    assert payload["allowed_files"] == ["scripts/governance/**", "docs/governance/**", "tests/**"]
    assert payload["forbidden_files"] == [
        "api/**",
        "dashboard/**",
        "dharma_swarm/dharma_kernel.py",
        "dharma_swarm/telos_gates.py",
    ]
    assert payload["approval"]["before_commit"] is True
    assert payload["approval"]["before_merge"] is True


def test_yds_boundary_uses_human_yosemite_scale_not_one_to_ten() -> None:
    assert validate_human_yds_rating("5.12a") == "5.12a"
    assert validate_human_yds_rating("5.15") == "5.15"

    with pytest.raises(ValueError):
        validate_human_yds_rating("8")

    with pytest.raises(ValueError):
        validate_human_yds_rating("5.16")


def test_room_schema_does_not_import_runtime_execution_organs() -> None:
    source = Path("dharma_swarm/fractal/fractal_room.py").read_text(encoding="utf-8")

    assert "from dharma_swarm.agent_runner" not in source
    assert "from dharma_swarm.task_board" not in source
    assert "from dharma_swarm.telic_seam" not in source
    assert "from dharma_swarm.ontology" not in source
    assert "subprocess" not in source
    assert "git " not in source
