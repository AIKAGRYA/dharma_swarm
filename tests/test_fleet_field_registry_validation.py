"""Adversarial validation tests for fleet field registry v2."""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any
import pytest
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from scripts.runtime.fleet_field_registry_contract import (  # noqa: E402
    RUNTIME_CELL_COMPONENTS,
    SCHEMA_V2,
    validate_registry,
)
TRACKED = (
    "inter_agent/fable_claude_code/inbound/2026-07-09-hermes-agni-probe-reply.md"
)
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhdHRhY2tlciJ9.signatureATTACK"
BEARER = "Bearer supersecrettokenvalue99ATTACK"
PEM = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIEowIBAAKCAQEA0Z3VS5JJcds3xfnATTACK\n"
    "-----END RSA PRIVATE KEY-----"
)
API = "sk-attackercontrolledapitokenvalue99"
SECRETS = (JWT, BEARER, PEM, API)
def _v(data: dict) -> list[str]:
    return validate_registry(data, repo_root=REPO_ROOT)
def _any(errors: list[str], *phrases: str) -> bool:
    return any(any(p in e for p in phrases) for e in errors)
def _has(errors: list[str], *needles: str) -> bool:
    return any(all(n in e for n in needles) for e in errors)
def _no_leak(blob: Any, *secrets: str) -> None:
    text = "\n".join(blob) if isinstance(blob, (list, tuple)) else str(blob)
    assert all(s not in text for s in secrets)
def _agent(uid: str) -> dict:
    sub, dur = f"dharma.agent.{uid}.inbox", f"{uid}_inbox"
    comps = {n: {"status": "unknown", "note": "fixture"} for n in RUNTIME_CELL_COMPONENTS}
    for k, val in {
        "agent_uid": uid,
        "canonical_inbox_subject": sub,
        "durable_consumer": dur,
        "credential_principal": uid,
        "delivery_runtime": "inbox_bridge",
        "semantic_executor_mode": "none",
        "observability_projection": "projection_only",
    }.items():
        comps[k] = {"status": "declared", "value": val}
    for k in ("idempotent_effect_boundary", "receipt_lifecycle", "large_artifact_lane"):
        comps[k] = {"status": "unknown"}
    route = {
        "inbox_subject": sub,
        "durable_consumer": dur,
        "credential_principal": uid,
    }
    empty = {
        k: None
        for k in ("inbox_subject", "durable_consumer", "credential_principal", "authority_id")
    }
    return {
        "agent_uid": uid,
        "display_name": uid,
        "runtime": "fixture",
        "lanes_available": ["none"],
        "primary_lane": "none",
        "live_on_hub": False,
        "credential_env_names": [],
        "listen_subjects": [sub],
        "publish_subjects": [],
        "git_seat": f"inter_agent/{uid}/",
        "last_verified_send": "never",
        "last_verified_receive": "never",
        "probe_receipt": TRACKED,
        "evidence_status": "probe_backed",
        "identity_source": "runtime_observed_uncommitted",
        "canonical_inbox_subject": sub,
        "durable_consumer": dur,
        "credential_principal": uid,
        "semantic_executor_mode": "none",
        "transport_contact_tier": "unknown",
        "semantic_effect_ceiling": "HANDLER_ACKED",
        "readiness_ceiling": "unknown",
        "declared_route": route,
        "observed_effective_route": empty,
        "runtime_cell": {
            "components": comps,
            "transport_contact_tier": "unknown",
            "semantic_effect_ceiling": "HANDLER_ACKED",
            "readiness_ceiling": "unknown",
        },
    }
def _reg() -> dict:
    return {
        "schema": SCHEMA_V2,
        "updated": "2026-07-18",
        "secret_policy": "env_var_names_only",
        "authorities": [
            {
                "authority_id": "agni",
                "role": "source_compatibility",
                "evidence_status": "probe_backed",
            },
            {
                "authority_id": "meghadharma",
                "role": "candidate_reference",
                "evidence_status": "runtime_observed_uncommitted",
            },
        ],
        "runtime_cell_contract": {
            "components": list(RUNTIME_CELL_COMPONENTS),
            "delivery_drain_ceiling": "HANDLER_ACKED",
            "readiness_rule": "minimum_proven_tier_across_components_with_non_proof_unknown",
        },
        "agents": [_agent("alice"), _agent("bob")],
    }
def _probe_all(agent: dict, *, mode: str = "always_on") -> None:
    comps = agent["runtime_cell"]["components"]
    for name in RUNTIME_CELL_COMPONENTS:
        comps[name] = {"status": "probed", "value": "x"}
    comps["agent_uid"] = {"status": "probed", "value": agent["agent_uid"]}
    comps["semantic_executor_mode"] = {"status": "probed", "value": mode}
    agent["semantic_executor_mode"] = mode
def _tiers(agent: dict, tier: str, *, effect: str | None = None) -> None:
    effect = tier if effect is None else effect
    for side in (agent, agent["runtime_cell"]):
        side["transport_contact_tier"] = tier
        side["semantic_effect_ceiling"] = effect
        side["readiness_ceiling"] = tier
def _proof(**kw) -> dict:
    base = {
        "agent_uid": "alice",
        "observed_at": "2026-07-09T00:00:00Z",
        "claimed_tier": "HANDLER_ACKED",
        "artifact_path": TRACKED,
        "artifact_sha256": "0" * 64,
    }
    base.update(kw)
    return base
def _ready(data: dict, **proof_kw) -> dict:
    agent = data["agents"][0]
    _probe_all(agent)
    _tiers(agent, "HANDLER_ACKED")
    agent["proof_evidence"] = _proof(**proof_kw)
    return agent
def _obs(sub, dur, prin, auth, **extra) -> dict:
    return {
        "inbox_subject": sub,
        "durable_consumer": dur,
        "credential_principal": prin,
        "authority_id": auth,
        **extra,
    }
def _mut(case_id: str, d: dict) -> None:
    a = d["agents"][0]
    rc = a["runtime_cell"]["components"]
    if case_id == "uid_ws":
        a["agent_uid"] = rc["agent_uid"]["value"] = "bad uid"
    elif case_id == "uid_wild":
        a["agent_uid"] = rc["agent_uid"]["value"] = "wild*"
    elif case_id == "subj_wild":
        a["declared_route"]["inbox_subject"] = a["canonical_inbox_subject"] = (
            "dharma.agent.*.inbox"
        )
    elif case_id == "subj_ws":
        a["declared_route"]["inbox_subject"] = a["canonical_inbox_subject"] = (
            "dharma.agent. alice.inbox"
        )
    elif case_id == "durable":
        a["declared_route"]["durable_consumer"] = a["durable_consumer"] = "alice.inbox"
    elif case_id == "route_mm":
        a["canonical_inbox_subject"] = "dharma.agent.other.inbox"
    elif case_id == "stray":
        d["agents"].append("stray string entry")
    elif case_id == "role":
        d["authorities"][0]["role"] = "overlord"
    elif case_id == "auth":
        a["authority_id"] = "no-such-authority"
    elif case_id == "lane":
        a["primary_lane"] = "carrier_pigeon"
    elif case_id == "abs":
        a["probe_receipt"] = "/etc/passwd"
    elif case_id == "trav":
        a["probe_receipt"] = "../secrets/token"
    elif case_id == "password":
        a["password"] = "not-a-real-secret-value-XYZ"
    elif case_id == "tier_mm":
        a["readiness_ceiling"] = "unknown"
        a["runtime_cell"]["readiness_ceiling"] = "HANDLER_ACKED"
    elif case_id == "overclaim":
        _tiers(a, "HANDLER_ACKED")
    elif case_id == "json_pw":
        d["password"] = "should-not-leak-in-json-mode"
    elif case_id == "semantic":
        a["semantic_executor_mode"] = "none"
        rc["semantic_executor_mode"] = {"status": "declared", "value": "none"}
        _tiers(a, "DOMAIN_RECEIPTED")
    elif case_id == "uid_bind":
        rc["agent_uid"] = {"status": "probed", "value": "not-alice"}
    elif case_id == "mode_bind":
        a["semantic_executor_mode"] = "none"
        rc["semantic_executor_mode"] = {"status": "declared", "value": "always_on"}
    elif case_id == "obs_bind":
        a["authority_id"] = "agni"
        a["observed_effective_route"] = _obs(
            "dharma.agent.alice.inbox", "alice_inbox", "alice", "agni"
        )
        rc["canonical_inbox_subject"] = {
            "status": "probed",
            "value": "dharma.agent.wrong.inbox",
        }
    elif case_id == "target":
        a["authority_id"] = "agni"
        a["observed_effective_route"] = _obs(None, None, None, None)
        a["target_route"] = {
            "inbox_subject": "dharma.agent.alice.inbox",
            "durable_consumer": "alice_inbox",
            "credential_principal": "alice",
        }
        rc["canonical_inbox_subject"] = {
            "status": "probed",
            "value": "dharma.agent.alice.inbox",
        }
    elif case_id == "quar_probe":
        d["routing_collisions"] = [
            {
                "collision_id": "alice-bob-shared",
                "subject": "dharma.a2a.shared",
                "agents": ["alice", "bob"],
            }
        ]
        a["observed_effective_route"] = _obs(
            None, None, None, "agni", collision_ref="alice-bob-shared"
        )
        rc["canonical_inbox_subject"] = {
            "status": "probed",
            "value": "dharma.a2a.shared",
        }
    elif case_id == "prin_dup":
        for agent in d["agents"]:
            agent["authority_id"] = "agni"
            agent["observed_effective_route"] = _obs(
                f"dharma.agent.{agent['agent_uid']}.inbox",
                f"{agent['agent_uid']}_inbox",
                "shared-principal",
                "agni",
            )
    elif case_id == "auth_one":
        d["authorities"] = [d["authorities"][0]]
    elif case_id == "auth_dup":
        d["authorities"][1]["authority_id"] = d["authorities"][0]["authority_id"]
    else:
        raise AssertionError(case_id)
_EXPECT = {
    "uid_ws": ("or", ("whitespace", "UID grammar"), ()),
    "uid_wild": ("or", ("wildcard", "UID grammar"), ()),
    "subj_wild": ("or", ("wildcard",), ()),
    "subj_ws": ("or", ("whitespace",), ()),
    "durable": ("or", ("durable",), ()),
    "route_mm": ("and", ("canonical_inbox_subject", "declared_route"), ()),
    "stray": ("or", ("not a mapping",), ()),
    "role": ("or", ("unknown role",), ()),
    "auth": ("or", ("not in authorities",), ()),
    "lane": ("and", ("primary_lane", "unknown"), ("carrier_pigeon",)),
    "abs": ("or", ("repo-relative", "absolute"), ()),
    "trav": ("or", ("traversal",), ()),
    "password": ("or", ("secret-bearing key",), ("not-a-real-secret-value-XYZ",)),
    "tier_mm": ("and", ("readiness_ceiling", "!="), ()),
    "overclaim": ("or", ("overclaims", "does not match"), ()),
    "json_pw": ("or", ("secret-bearing key", "secret"), ("should-not-leak-in-json-mode",)),
    "semantic": ("sem", ("semantic", "executor"), ()),
    "uid_bind": ("and", ("agent_uid", "value"), ()),
    "mode_bind": ("and", ("semantic_executor_mode", "value"), ()),
    "obs_bind": ("and", ("canonical_inbox_subject", "observed"), ()),
    "target": ("target", ("canonical_inbox_subject",), ()),
    "quar_probe": ("or", ("quarantine", "collision"), ()),
    "prin_dup": ("and", ("credential_principal", "duplicate"), ("shared-principal",)),
    "auth_one": ("and", ("authorities", "at least two"), ()),
    "auth_dup": ("or", ("duplicate authority_id",), ()),
}
@pytest.mark.parametrize("planted", [BEARER, JWT, PEM], ids=["bearer", "jwt", "private_key"])
def test_bearer_jwt_private_key_shapes_rejected_and_redacted(planted):
    data = _reg()
    data["agents"][0]["runtime"] = planted
    errors = _v(data)
    assert any("high-confidence secret" in e for e in errors)
    _no_leak(errors, planted, "MIIEowIBAAKCAQEA")
@pytest.mark.parametrize(
    "names,leaks",
    [(["not_an_env_name"], ()), (["NATS_PASSWORD=hunter2"], ("hunter2",))],
    ids=["bare_value", "assignment_form"],
)
def test_credential_env_names_reject_values_not_names(names, leaks):
    data = _reg()
    data["agents"][0]["credential_env_names"] = names
    errors = _v(data)
    assert any("credential_env_names" in e or "secret" in e.lower() for e in errors)
    _no_leak(errors, *leaks)
@pytest.mark.parametrize("case_id", list(_EXPECT), ids=list(_EXPECT))
def test_validation_rejects_malformed_and_mismatched_fields(case_id):
    mode, phrases, leaks = _EXPECT[case_id]
    data = _reg()
    _mut(case_id, data)
    errors = _v(data)
    if mode == "and":
        assert _has(errors, *phrases), errors
    elif mode == "sem":
        assert any("semantic" in e.lower() and "executor" in e.lower() for e in errors), errors
    elif mode == "target":
        assert any(
            "canonical_inbox_subject" in e and ("probed" in e or "observed" in e)
            for e in errors
        ), errors
    else:
        assert _any(errors, *phrases), errors
    _no_leak(errors, *leaks)
def test_observed_effective_route_collision_rejected_without_quarantine():
    data = _reg()
    shared = "dharma.a2a.shared"
    for agent in data["agents"]:
        agent["authority_id"] = "agni"
        agent["observed_effective_route"] = _obs(shared, None, None, "agni")
    errors = _v(data)
    assert any("duplicate" in e and "inbox_subject" in e for e in errors)
    _no_leak(errors, shared)
def test_untracked_receipt_rejected():
    data = _reg()
    untracked = REPO_ROOT / "reports/agentops/_ffr_test_untracked_receipt.md"
    untracked.parent.mkdir(parents=True, exist_ok=True)
    untracked.write_text("temp", encoding="utf-8")
    try:
        data["agents"][0]["probe_receipt"] = str(untracked.relative_to(REPO_ROOT))
        assert any("not git-tracked" in e for e in _v(data))
    finally:
        untracked.unlink(missing_ok=True)
def test_hash_uid_mismatch_and_legacy_unbound_receipt_proof():
    data = _reg()
    _ready(data, agent_uid="not-alice")
    errors = _v(data)
    assert any("agent_uid mismatch" in e for e in errors)
    assert any("artifact_sha256 mismatch" in e or "sha256" in e for e in errors)
    data = _reg()
    agent = data["agents"][0]
    assert agent.get("probe_receipt") and agent.get("proof_evidence") is None
    assert agent["readiness_ceiling"] == "unknown"
    assert not any("overclaims" in e for e in _v(data))
@pytest.mark.parametrize(
    "observed_at,phrase",
    [("2010-01-01T00:00:00Z", "stale"), ("2099-06-01T00:00:00Z", "future")],
    ids=["stale", "future"],
)
def test_proof_evidence_observed_at_window_rejected(observed_at, phrase):
    data = _reg()
    _ready(data, observed_at=observed_at)
    assert any(phrase in e for e in _v(data))
def test_symlink_receipt_escaping_repository_rejected(tmp_path):
    data = _reg()
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("escape-target", encoding="utf-8")
    link = REPO_ROOT / "reports/agentops/_ffr_escape_symlink_receipt.md"
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    try:
        link.symlink_to(outside)
        data["agents"][0]["probe_receipt"] = str(link.relative_to(REPO_ROOT))
        errors = _v(data)
        assert any("escape" in e or "symlink" in e for e in errors)
        _no_leak(errors, str(outside), "escape-target")
    finally:
        link.unlink(missing_ok=True)
def test_receipt_path_errors_use_field_label_not_always_probe_receipt():
    data = _reg()
    agent = _ready(data, artifact_path="/etc/passwd")
    agent["readiness_ceiling"] = agent["runtime_cell"]["readiness_ceiling"] = "unknown"
    assert any(
        "proof_evidence.artifact_path" in e and ("absolute" in e or "repo-relative" in e)
        for e in _v(data)
    )
@pytest.mark.parametrize("kind", ["missing_field", "unknown_auth", "mismatch", "quarantine_ok"])
def test_observed_authority_required_known_and_matching(kind):
    data = _reg()
    a = data["agents"][0]
    a["authority_id"] = "agni"
    if kind == "missing_field":
        a["observed_effective_route"] = {
            "inbox_subject": None,
            "durable_consumer": None,
            "credential_principal": None,
        }
        assert _has(_v(data), "authority_id", "observed_effective_route")
    elif kind == "unknown_auth":
        a["observed_effective_route"] = _obs(
            "dharma.agent.alice.inbox", "alice_inbox", "alice", "no-such-authority"
        )
        errors = _v(data)
        assert any("authority" in e for e in errors)
        _no_leak(errors, "no-such-authority")
    elif kind == "mismatch":
        a["observed_effective_route"] = _obs(
            "dharma.agent.alice.inbox", "alice_inbox", "alice", "meghadharma"
        )
        assert any("mismatch" in e or "authority" in e for e in _v(data))
    else:
        data["routing_collisions"] = [
            {
                "collision_id": "alice-bob-shared",
                "subject": "dharma.a2a.shared",
                "agents": ["alice", "bob"],
            }
        ]
        a["observed_effective_route"] = _obs(
            None, None, None, "agni", collision_ref="alice-bob-shared"
        )
        for key in ("canonical_inbox_subject", "durable_consumer", "credential_principal"):
            a["runtime_cell"]["components"][key] = {"status": "unprobed"}
        assert not any(
            "observed_effective_route.authority_id" in e and "mismatch" in e
            for e in _v(data)
        )
@pytest.mark.parametrize("kind", ["secret_uid", "authority_enums", "tier_scalar", "secret_key"])
def test_attacker_controlled_scalars_never_appear_in_errors(kind):
    data = _reg()
    if kind == "secret_uid":
        data["agents"][0]["agent_uid"] = JWT
        data["agents"][0]["runtime_cell"]["components"]["agent_uid"]["value"] = JWT
        errors = _v(data)
        assert errors
        _no_leak(errors, JWT, "eyJ")
    elif kind == "authority_enums":
        data["authorities"][0]["role"] = "overlord-secret-role-XYZ"
        data["authorities"][0]["evidence_status"] = "evidence-secret-status-XYZ"
        errors = _v(data)
        assert any("role" in e or "evidence_status" in e for e in errors)
        _no_leak(errors, "overlord-secret-role-XYZ", "evidence-secret-status-XYZ")
    elif kind == "tier_scalar":
        data["agents"][0]["transport_contact_tier"] = "TIER_SECRET_LEAK_XYZ"
        errors = _v(data)
        assert any("transport_contact_tier" in e for e in errors)
        _no_leak(errors, "TIER_SECRET_LEAK_XYZ")
    else:
        data["agents"][0]["api_key_ATTACKER"] = "value-should-also-be-redacted"
        errors = _v(data)
        assert any("secret-bearing key under" in e and "redacted" in e for e in errors)
        _no_leak(errors, "api_key_ATTACKER", "value-should-also-be-redacted")
@pytest.mark.parametrize("planted", SECRETS, ids=["jwt", "bearer", "pem", "api"])
def test_secret_shapes_never_reach_error_text(planted):
    data = _reg()
    data["agents"][0]["runtime"] = planted
    errors = _v(data)
    assert errors
    _no_leak(errors, planted, "MIIEowIBAAKCAQEA")
