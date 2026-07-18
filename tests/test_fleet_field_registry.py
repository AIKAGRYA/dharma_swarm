"""Tests for scripts/runtime/fleet_field_registry.py and the registry itself."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.runtime.fleet_field_registry import (  # noqa: E402
    REGISTRY_PATH,
    RUNTIME_CELL_COMPONENTS,
    SCHEMA_V2,
    compute_readiness_ceiling,
    load_registry,
    render_table,
    validate,
)


# ---------------------------------------------------------------------------
# Existing / migrated registry contract
# ---------------------------------------------------------------------------


def test_registry_file_exists_and_parses():
    data = load_registry()
    assert data["schema"] == SCHEMA_V2
    assert data["secret_policy"] == "env_var_names_only"


def test_committed_registry_is_valid():
    errors = validate(load_registry())
    assert errors == []


def test_every_probed_agent_has_receipt_in_repo():
    data = load_registry()
    for agent in data["agents"]:
        receipt = agent.get("probe_receipt")
        if not receipt:
            # uncommitted / reference-gap rows may omit a committed probe receipt
            assert agent.get("evidence_status") in {
                "runtime_observed_uncommitted",
                "reference_gap",
                "unprobed",
            }, f"{agent['agent_uid']}: missing probe_receipt without honest evidence_status"
            continue
        path = REPO_ROOT / receipt
        assert path.exists(), f"{agent['agent_uid']}: missing {path}"


def test_probed_field_covers_expected_identities():
    uids = {agent["agent_uid"] for agent in load_registry()["agents"]}
    assert {
        "hermes",
        "rushabdev",
        "devin-roaming-2987d222",
        "fable_claude_code",
        "codex",
        "perplexity-computer",
    } <= uids


def test_validation_rejects_credential_value_shapes():
    data = copy.deepcopy(load_registry())
    data["agents"][0]["credential_env_names"] = ["not_an_env_name"]
    errors = validate(data)
    assert any("credential_env_names" in error for error in errors)


def test_validation_rejects_literal_secret_values():
    data = copy.deepcopy(load_registry())
    data["agents"][0]["runtime"] = "vps with password=hunter2 baked in"
    errors = validate(data)
    assert any("possible secret value" in error for error in errors)


def test_validation_handles_non_mapping_agent_entry_cleanly():
    data = copy.deepcopy(load_registry())
    data["agents"].append("stray string entry")
    errors = validate(data)  # must not raise
    assert any("not a mapping" in error for error in errors)


def test_validation_rejects_unknown_lane_and_missing_fields():
    data = copy.deepcopy(load_registry())
    data["agents"][0]["primary_lane"] = "carrier_pigeon"
    # ensure the second agent would trip probe_receipt if required by its status
    if "probe_receipt" in data["agents"][1]:
        del data["agents"][1]["probe_receipt"]
        data["agents"][1]["evidence_status"] = "probe_backed"
    errors = validate(data)
    assert any("carrier_pigeon" in error for error in errors)
    assert any("probe_receipt" in error for error in errors)


def test_render_table_lists_all_agents():
    data = load_registry()
    table = render_table(data)
    for agent in data["agents"]:
        assert agent["agent_uid"] in table


def test_registration_card_matches_registry_uid():
    import json

    card = json.loads(
        (REPO_ROOT / "examples/agents/perplexity-computer.registration.json").read_text()
    )
    assert card["agent_uid"] == "perplexity-computer"
    registry_uids = {agent["agent_uid"] for agent in load_registry()["agents"]}
    assert card["agent_uid"] in registry_uids


# ---------------------------------------------------------------------------
# FFR v2 — Universal Agent Runtime Cell contract
# ---------------------------------------------------------------------------


def _minimal_v2_registry() -> dict:
    """Honest minimal multi-authority registry used by unit tests."""
    components = {
        name: {"status": "unknown", "note": "fixture"} for name in RUNTIME_CELL_COMPONENTS
    }
    components["agent_uid"] = {"status": "declared", "value": "alice"}
    components["canonical_inbox_subject"] = {
        "status": "declared",
        "value": "dharma.agent.alice.inbox",
    }
    components["durable_consumer"] = {"status": "declared", "value": "alice_inbox"}
    components["credential_principal"] = {"status": "declared", "value": "alice"}
    components["delivery_runtime"] = {"status": "declared", "value": "inbox_bridge"}
    components["semantic_executor_mode"] = {"status": "declared", "value": "none"}
    components["idempotent_effect_boundary"] = {"status": "unknown"}
    components["receipt_lifecycle"] = {"status": "unknown"}
    components["large_artifact_lane"] = {"status": "unknown"}
    components["observability_projection"] = {"status": "declared", "value": "projection_only"}

    bob_components = copy.deepcopy(components)
    bob_components["agent_uid"] = {"status": "declared", "value": "bob"}
    bob_components["canonical_inbox_subject"] = {
        "status": "declared",
        "value": "dharma.agent.bob.inbox",
    }
    bob_components["durable_consumer"] = {"status": "declared", "value": "bob_inbox"}
    bob_components["credential_principal"] = {"status": "declared", "value": "bob"}

    return {
        "schema": SCHEMA_V2,
        "updated": "2026-07-18",
        "secret_policy": "env_var_names_only",
        "authorities": [
            {
                "authority_id": "agni",
                "role": "source_compatibility",
                "evidence_status": "probe_backed",
                "live_stream": "DHARMA_A2A",
            },
            {
                "authority_id": "meghadharma",
                "role": "candidate_reference",
                "evidence_status": "runtime_observed_uncommitted",
                "live_stream": "DHARMA_A2A",
            },
        ],
        "runtime_cell_contract": {
            "components": list(RUNTIME_CELL_COMPONENTS),
            "delivery_drain_ceiling": "HANDLER_ACKED",
            "readiness_rule": "minimum_proven_tier_across_components",
        },
        "agents": [
            {
                "agent_uid": "alice",
                "display_name": "Alice",
                "runtime": "fixture",
                "lanes_available": ["none"],
                "primary_lane": "none",
                "live_on_hub": False,
                "credential_env_names": [],
                "listen_subjects": ["dharma.agent.alice.inbox"],
                "publish_subjects": [],
                "git_seat": "inter_agent/alice/",
                "last_verified_send": "never",
                "last_verified_receive": "never",
                "probe_receipt": "inter_agent/fable_claude_code/inbound/2026-07-09-hermes-agni-probe-reply.md",
                "evidence_status": "probe_backed",
                "canonical_inbox_subject": "dharma.agent.alice.inbox",
                "durable_consumer": "alice_inbox",
                "semantic_executor_mode": "none",
                "transport_contact_tier": "unknown",
                "semantic_effect_ceiling": "HANDLER_ACKED",
                "readiness_ceiling": "unknown",
                "runtime_cell": {
                    "components": components,
                    "transport_contact_tier": "unknown",
                    "semantic_effect_ceiling": "HANDLER_ACKED",
                    "readiness_ceiling": "unknown",
                },
            },
            {
                "agent_uid": "bob",
                "display_name": "Bob",
                "runtime": "fixture",
                "lanes_available": ["none"],
                "primary_lane": "none",
                "live_on_hub": False,
                "credential_env_names": [],
                "listen_subjects": ["dharma.agent.bob.inbox"],
                "publish_subjects": [],
                "git_seat": "inter_agent/bob/",
                "last_verified_send": "never",
                "last_verified_receive": "never",
                "probe_receipt": "inter_agent/fable_claude_code/inbound/2026-07-09-hermes-agni-probe-reply.md",
                "evidence_status": "probe_backed",
                "canonical_inbox_subject": "dharma.agent.bob.inbox",
                "durable_consumer": "bob_inbox",
                "semantic_executor_mode": "none",
                "transport_contact_tier": "unknown",
                "semantic_effect_ceiling": "HANDLER_ACKED",
                "readiness_ceiling": "unknown",
                "runtime_cell": {
                    "components": bob_components,
                    "transport_contact_tier": "unknown",
                    "semantic_effect_ceiling": "HANDLER_ACKED",
                    "readiness_ceiling": "unknown",
                },
            },
        ],
    }


def test_v2_schema_constant_and_committed_registry_use_v2():
    assert SCHEMA_V2 == "dharma_fleet_field_registry.v2"
    data = load_registry()
    assert data["schema"] == "dharma_fleet_field_registry.v2"


def test_v2_requires_nonempty_multi_authority_with_unique_ids_and_roles():
    data = _minimal_v2_registry()
    assert validate(data) == []

    data_one = copy.deepcopy(data)
    data_one["authorities"] = [data_one["authorities"][0]]
    errors = validate(data_one)
    assert any("authorities" in e and "at least two" in e for e in errors)

    data_dup = copy.deepcopy(data)
    data_dup["authorities"][1]["authority_id"] = data_dup["authorities"][0]["authority_id"]
    errors = validate(data_dup)
    assert any("duplicate authority_id" in e for e in errors)

    data_role = copy.deepcopy(data)
    del data_role["authorities"][0]["role"]
    errors = validate(data_role)
    assert any("role" in e for e in errors)


def test_v2_runtime_cell_contract_lists_ten_components():
    data = load_registry()
    contract = data["runtime_cell_contract"]
    components = contract["components"]
    assert set(components) == set(RUNTIME_CELL_COMPONENTS)
    assert len(components) == 10
    for name in (
        "agent_uid",
        "canonical_inbox_subject",
        "durable_consumer",
        "credential_principal",
        "delivery_runtime",
        "semantic_executor_mode",
        "idempotent_effect_boundary",
        "receipt_lifecycle",
        "large_artifact_lane",
        "observability_projection",
    ):
        assert name in components


def test_every_agent_carries_runtime_cell_projection_and_readiness_ceiling():
    data = load_registry()
    for agent in data["agents"]:
        uid = agent["agent_uid"]
        cell = agent.get("runtime_cell")
        assert isinstance(cell, dict), f"{uid}: missing runtime_cell projection"
        comps = cell.get("components")
        assert isinstance(comps, dict), f"{uid}: runtime_cell.components must be a mapping"
        for name in RUNTIME_CELL_COMPONENTS:
            assert name in comps, f"{uid}: missing runtime_cell component {name}"
            status = comps[name].get("status") if isinstance(comps[name], dict) else None
            assert status, f"{uid}: component {name} needs explicit status"
        for field in (
            "transport_contact_tier",
            "semantic_effect_ceiling",
            "readiness_ceiling",
        ):
            assert cell.get(field), f"{uid}: missing runtime_cell.{field}"
            assert agent.get(field), f"{uid}: missing top-level {field}"


def test_duplicate_non_null_canonical_inbox_subjects_rejected():
    data = _minimal_v2_registry()
    data["agents"][1]["canonical_inbox_subject"] = data["agents"][0]["canonical_inbox_subject"]
    data["agents"][1]["runtime_cell"]["components"]["canonical_inbox_subject"]["value"] = data[
        "agents"
    ][0]["canonical_inbox_subject"]
    errors = validate(data)
    assert any("canonical_inbox_subject" in e and "duplicate" in e for e in errors)


def test_duplicate_non_null_durable_consumers_rejected():
    data = _minimal_v2_registry()
    data["agents"][1]["durable_consumer"] = data["agents"][0]["durable_consumer"]
    data["agents"][1]["runtime_cell"]["components"]["durable_consumer"]["value"] = data["agents"][
        0
    ]["durable_consumer"]
    errors = validate(data)
    assert any("durable_consumer" in e and "duplicate" in e for e in errors)


def test_semantic_effect_ceiling_rejected_without_semantic_executor():
    data = _minimal_v2_registry()
    agent = data["agents"][0]
    agent["semantic_executor_mode"] = "none"
    agent["runtime_cell"]["components"]["semantic_executor_mode"] = {
        "status": "declared",
        "value": "none",
    }
    agent["semantic_effect_ceiling"] = "DOMAIN_RECEIPTED"
    agent["runtime_cell"]["semantic_effect_ceiling"] = "DOMAIN_RECEIPTED"
    agent["readiness_ceiling"] = "DOMAIN_RECEIPTED"
    agent["runtime_cell"]["readiness_ceiling"] = "DOMAIN_RECEIPTED"
    errors = validate(data)
    assert any("semantic" in e.lower() and "executor" in e.lower() for e in errors)

    agent["semantic_executor_mode"] = "unknown"
    agent["runtime_cell"]["components"]["semantic_executor_mode"] = {
        "status": "unknown",
        "value": "unknown",
    }
    agent["semantic_effect_ceiling"] = "PROCESSED"
    agent["runtime_cell"]["semantic_effect_ceiling"] = "PROCESSED"
    errors = validate(data)
    assert any("semantic" in e.lower() for e in errors)


def test_unknown_values_accepted_only_when_explicit_and_not_rendered_green():
    data = _minimal_v2_registry()
    agent = data["agents"][0]
    agent["transport_contact_tier"] = "unknown"
    agent["semantic_effect_ceiling"] = "unknown"
    agent["readiness_ceiling"] = "unknown"
    agent["runtime_cell"]["transport_contact_tier"] = "unknown"
    agent["runtime_cell"]["semantic_effect_ceiling"] = "unknown"
    agent["runtime_cell"]["readiness_ceiling"] = "unknown"
    assert validate(data) == []

    table = render_table(data)
    assert "alice" in table
    # Must not paint unknown as a green/live success.
    assert "READY" not in table
    assert "LIVE-SEMANTIC" not in table
    # Honest unknown marker present for the agent row.
    assert "unknown" in table.lower()


def test_secret_value_rejection_preserved_on_v2_shapes():
    data = _minimal_v2_registry()
    data["agents"][0]["credential_env_names"] = ["NATS_PASSWORD=hunter2"]
    errors = validate(data)
    assert any("credential_env_names" in e or "possible secret value" in e for e in errors)

    data = _minimal_v2_registry()
    data["agents"][0]["runtime"] = "token=supersecretvalue"
    errors = validate(data)
    assert any("possible secret value" in e for e in errors)


def test_renderer_exposes_authority_transport_and_semantic_ceiling_honestly():
    data = load_registry()
    table = render_table(data)
    # Multi-authority names must appear (not singular-hub-only prose).
    assert "agni" in table.lower()
    assert "meghadharma" in table.lower() or "mac" in table.lower()
    for agent in data["agents"]:
        assert agent["agent_uid"] in table
        tier = str(agent.get("transport_contact_tier", "unknown"))
        ceiling = str(agent.get("semantic_effect_ceiling", "unknown"))
        # Renderer must surface the declared tiers, not invent green.
        assert tier in table or tier.upper() in table
        assert ceiling in table or ceiling.upper() in table


def test_compute_readiness_ceiling_fail_closed():
    # Delivery alone never exceeds HANDLER_ACKED.
    assert (
        compute_readiness_ceiling(
            component_statuses={
                "delivery_runtime": "probed",
                "semantic_executor_mode": "none",
            },
            semantic_executor_mode="none",
            transport_contact_tier="HANDLER_ACKED",
            semantic_effect_ceiling="DOMAIN_RECEIPTED",
        )
        == "HANDLER_ACKED"
    )
    # Unknown stays unknown when anything critical is unknown.
    assert (
        compute_readiness_ceiling(
            component_statuses={name: "unknown" for name in RUNTIME_CELL_COMPONENTS},
            semantic_executor_mode="unknown",
            transport_contact_tier="unknown",
            semantic_effect_ceiling="unknown",
        )
        == "unknown"
    )
    # Overclaim with absent semantic executor is capped.
    capped = compute_readiness_ceiling(
        component_statuses={
            "delivery_runtime": "probed",
            "semantic_executor_mode": "absent",
            "agent_uid": "probed",
        },
        semantic_executor_mode="absent",
        transport_contact_tier="HANDLER_ACKED",
        semantic_effect_ceiling="EFFECT_COMMITTED",
    )
    assert capped == "HANDLER_ACKED"
