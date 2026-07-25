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
    load_registry,
    render_table,
    validate,
)


def test_registry_file_exists_and_parses():
    data = load_registry()
    assert data["schema"] == "dharma_fleet_field_registry.v1"
    assert data["secret_policy"] == "env_var_names_only"


def test_committed_registry_is_valid():
    errors = validate(load_registry())
    assert errors == []


def test_every_probed_agent_has_receipt_in_repo():
    data = load_registry()
    for agent in data["agents"]:
        receipt = REPO_ROOT / agent["probe_receipt"]
        assert receipt.exists(), f"{agent['agent_uid']}: missing {receipt}"


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
    del data["agents"][1]["probe_receipt"]
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
