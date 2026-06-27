"""Tests for the Semantic Commons registry and orientation contract."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
OBJECTS_PATH = REPO_ROOT / "docs/ontology/semantic_objects.yaml"
ALIASES_PATH = REPO_ROOT / "docs/ontology/semantic_aliases.yaml"
ORIENTATION_PATH = REPO_ROOT / "docs/ontology/session_orientation.yaml"
API_NAME_RE = re.compile(r"^dharma\.[a-z][a-z0-9_]*\.[A-Z][A-Za-z0-9]*$")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _norm(value: str) -> str:
    return " ".join(value.strip().lower().split())


def test_seed_objects_present() -> None:
    payload = _load(OBJECTS_PATH)
    ids = {item["id"] for item in payload["objects"]}

    assert {
        "semobj.agent_admission",
        "semobj.registration_desk",
        "semobj.agent_seed",
        "semobj.living_dock",
        "semobj.codex_composer",
        "semobj.sanctum",
        "semobj.holocron",
        "semobj.holocron_nest",
        "semobj.aerie",
        "semobj.landing_dock",
        "semobj.factory_droid",
        "semobj.a2a_card",
        "semobj.name_drift_preflight",
        "semobj.session_orientation",
        "semobj.orientation_layer",
        "semobj.orientation_route",
        "semobj.ontology_registry",
        "semobj.ontology_hub",
        "semobj.runtime_receipt",
        "semobj.codex_telos",
        "semobj.model_key_routing",
        "semobj.dkeys_key_store",
        "semobj.runtime_provider",
        "semobj.model_hierarchy",
        "semobj.provider_policy_router",
        "semobj.model_router",
        "semobj.routing_memory",
        "semobj.agent_uid",
        "semobj.nats_substrate",
        "semobj.a2a_inbox_route",
    } <= ids


def test_objects_have_required_fields_and_lifecycles() -> None:
    payload = _load(OBJECTS_PATH)
    allowed = set(payload["lifecycle_values"])
    required = {
        "id",
        "canonical_name",
        "api_name",
        "lifecycle",
        "owner_surface",
        "authority_level",
        "source_path",
        "aliases",
        "forbidden_aliases",
        "supersedes",
        "superseded_by",
    }
    ids = []
    for obj in payload["objects"]:
        ids.append(obj["id"])
        assert required <= set(obj), obj["id"]
        assert obj["lifecycle"] in allowed, obj["id"]
        assert obj["aliases"], obj["id"]
    assert len(ids) == len(set(ids))


def test_public_api_names_follow_adr_008() -> None:
    payload = _load(OBJECTS_PATH)

    for obj in payload["objects"]:
        api_name = obj["api_name"]
        assert API_NAME_RE.match(api_name), obj["id"]
        assert not re.search(r"(?:\.v[0-9]+|_v[0-9]+)$", api_name), obj["id"]


def test_aliases_resolve_to_one_active_object() -> None:
    objects = {item["id"]: item for item in _load(OBJECTS_PATH)["objects"]}
    aliases = _load(ALIASES_PATH)["aliases"]
    alias_targets: dict[str, set[str]] = {}

    for entry in aliases:
        if entry.get("status", "active") in {"deprecated", "forbidden"}:
            continue
        alias_targets.setdefault(_norm(entry["alias"]), set()).add(entry["canonical_id"])

    for alias, targets in alias_targets.items():
        active_targets = {
            target
            for target in targets
            if objects[target]["lifecycle"] in {"seed", "working", "preferred", "canonical"}
        }
        assert len(active_targets) == 1, (alias, active_targets)


def test_object_aliases_are_in_central_registry() -> None:
    objects = _load(OBJECTS_PATH)["objects"]
    aliases = _load(ALIASES_PATH)["aliases"]
    central = {
        (entry["canonical_id"], _norm(entry["alias"]))
        for entry in aliases
        if entry.get("status", "active") not in {"deprecated", "forbidden"}
    }

    for obj in objects:
        for alias in obj["aliases"]:
            assert (obj["id"], _norm(alias)) in central, (obj["id"], alias)


def test_separator_variants_are_registered() -> None:
    aliases = _load(ALIASES_PATH)["aliases"]
    by_target: dict[str, set[str]] = {}
    for entry in aliases:
        if entry.get("status", "active") in {"deprecated", "forbidden"}:
            continue
        by_target.setdefault(entry["canonical_id"], set()).add(_norm(entry["alias"]))

    for target, values in by_target.items():
        for alias in values:
            if "." in alias or " " in alias:
                continue
            if "-" in alias:
                assert alias.replace("-", "_") in values, (target, alias)
            if "_" in alias:
                assert alias.replace("_", "-") in values, (target, alias)


def test_forbidden_regression_aliases_registered_as_forbidden_only() -> None:
    aliases = _load(ALIASES_PATH)
    active = {_norm(item["alias"]) for item in aliases["aliases"]}
    forbidden = {_norm(item["alias"]) for item in aliases["forbidden_aliases"]}

    assert "icm" in forbidden
    assert "opencalw" in forbidden
    assert "message_v2" in forbidden
    assert "aaverie" in forbidden
    assert "icm" not in active
    assert "opencalw" not in active
    assert "message_v2" not in active
    assert "aaverie" not in active


def test_orientation_route_has_l0_l1_l2_before_corpus_search() -> None:
    payload = _load(ORIENTATION_PATH)

    for route in payload["routes"]:
        order = route["entry_order"]
        assert order[:3] == ["L0", "L1", "L2"], route["id"]
        layers = {layer["id"]: layer for layer in route["layers"]}
        for required in ("L0", "L1", "L2"):
            assert required in layers, route["id"]
            assert layers[required]["search_allowed"] is False, route["id"]
        assert layers["L0"]["budget_tokens"] <= 1000
        assert layers["L1"]["budget_tokens"] <= 2000
        assert layers["L2"]["budget_tokens"] <= 4000
        first_layer = layers[order[0]]
        assert first_layer["source_kind"] != "corpus_search", route["id"]
        assert layers["L4"]["search_allowed"] is True, route["id"]


def test_living_dock_subspaces_and_projection_names_are_registered() -> None:
    payload = _load(OBJECTS_PATH)
    aliases = _load(ALIASES_PATH)["aliases"]
    objects = {item["id"]: item for item in payload["objects"]}
    central = {
        (entry["canonical_id"], _norm(entry["alias"]))
        for entry in aliases
        if entry.get("status", "active") not in {"deprecated", "forbidden"}
    }

    expected = {
        "semobj.codex_composer": ("working", ["codex-composer", "codex_composer"]),
        "semobj.sanctum": ("working", ["living-dock-sanctum", "living_dock_sanctum"]),
        "semobj.holocron": ("working", ["living-dock-holocron", "living_dock_holocron"]),
        "semobj.holocron_nest": ("working", ["holocron-nest", "holocron_nest"]),
        "semobj.aerie": ("seed", ["Aerie", "fleet-aerie", "fleet_aerie"]),
        "semobj.landing_dock": ("seed", ["LandingDock", "landing-dock", "landing_dock"]),
        "semobj.factory_droid": ("seed", ["FactoryDroid", "factory-droid", "factory_droid", "DroidFactory"]),
    }

    for canonical_id, (lifecycle, object_aliases) in expected.items():
        assert objects[canonical_id]["lifecycle"] == lifecycle
        assert objects[canonical_id]["orientation_route"] == "route.semantic_commons_campaign"
        for alias in object_aliases:
            assert (canonical_id, _norm(alias)) in central, (canonical_id, alias)

    assert "DroidFactory" in objects["semobj.factory_droid"]["aliases"]
    assert "semobj.droid_factory" not in objects
    assert objects["semobj.sanctum"]["object_kind"] == "living_dock_subspace"
    assert objects["semobj.holocron"]["object_kind"] == "living_dock_subspace"
    assert objects["semobj.holocron_nest"]["object_kind"] == "living_dock_subspace"


def test_l5_seat_load_is_context_loading_not_d6_promotion() -> None:
    payload = _load(ORIENTATION_PATH)
    route = next(item for item in payload["routes"] if item["id"] == "route.semantic_commons_campaign")
    order = route["entry_order"]
    layers = {layer["id"]: layer for layer in route["layers"]}
    l5 = layers["L5"]

    assert order == ["L0", "L1", "L2", "L3", "L4", "L5"]
    assert "D6" not in order
    assert l5["name"] == "Seat Load"
    assert l5["source_kind"] == "named_agent_seat_load"
    assert l5["search_allowed"] is False
    assert "make onboard-agent AGENT_NAME=codex_composer" in l5["commands"]
    required_answers = set(l5["required_answers"])
    assert "what identity is being loaded" in required_answers
    assert "where is the LivingDock projection" in required_answers
    assert "which recent receipts are current" in required_answers
    assert "what policy ceiling applies" in required_answers
    assert "what shared swarm truth outranks private context" in required_answers
    assert "what Sanctum and Holocron context is in scope" in required_answers


def test_routing_identity_objects_are_registered() -> None:
    payload = _load(OBJECTS_PATH)
    aliases = _load(ALIASES_PATH)["aliases"]
    objects = {item["id"]: item for item in payload["objects"]}
    central = {
        (entry["canonical_id"], _norm(entry["alias"]))
        for entry in aliases
        if entry.get("status", "active") not in {"deprecated", "forbidden"}
    }

    expected_aliases = {
        "semobj.model_key_routing": ["MODEL_KEY_ROUTING", "the one way"],
        "semobj.dkeys_key_store": ["dkeys", "agent_keys.env"],
        "semobj.runtime_provider": [
            "resolve_runtime_provider_config",
            "create_runtime_provider",
        ],
        "semobj.model_hierarchy": ["canonical_seed_order", "provider seed order"],
        "semobj.provider_policy_router": ["ProviderRouteRequest", "ProviderRouteDecision"],
        "semobj.model_router": ["complete_for_task", "provider_chain"],
        "semobj.routing_memory": ["routing_memory.sqlite3"],
        "semobj.agent_uid": ["agent_uid", "stable agent UID"],
        "semobj.nats_substrate": ["NATS_SUBSTRATE_MASTER_SPEC", "NATS substrate"],
        "semobj.a2a_inbox_route": ["agent-inbox", "--route agent-inbox"],
    }

    for canonical_id, object_aliases in expected_aliases.items():
        assert canonical_id in objects
        assert objects[canonical_id]["orientation_route"] == "route.semantic_commons_campaign"
        for alias in object_aliases:
            assert (canonical_id, _norm(alias)) in central, (canonical_id, alias)


def test_routing_moc_includes_model_and_transport_authorities() -> None:
    payload = _load(ORIENTATION_PATH)
    route = next(item for item in payload["routes"] if item["id"] == "route.semantic_commons_campaign")
    layers = {layer["id"]: layer for layer in route["layers"]}
    l1_sources = set(layers["L1"]["source_paths"])

    assert "docs/ops/MODEL_KEY_ROUTING.md" in l1_sources
    assert "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md" in l1_sources
