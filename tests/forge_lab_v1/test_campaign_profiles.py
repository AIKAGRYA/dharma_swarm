from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from dharma_swarm.forge_lab import (
    campaign_control,
    campaign_gates,
    campaign_profile,
    provider_selftest,
)
from dharma_swarm.forge_lab.campaign_contract import (
    CampaignContractError,
    build_manifest,
)


COMMIT = "a" * 40
TREE = "b" * 40
CLEAN_IDENTITY = {
    "commit": COMMIT,
    "tree": TREE,
    "tree_state": "clean",
    "checkout": "/test/release",
}
EXACT_LIMITS = {
    "total_tokens": 1_000_000,
    "total_usd_micros": 25_000_000,
    "total_requests": 120,
    "deadline_utc": "2099-01-01T00:00:00Z",
    "host_caps": {"host": "meghadharma", "max_parallel_requests": 3},
}


def test_historical_n30_profile_retains_exact_moonshot_semantics() -> None:
    definition = campaign_profile.campaign_definition(campaign_profile.PROFILE)
    manifest = build_manifest(definition)

    assert definition["source"]["release_commit"] == campaign_profile.CANONICAL_COMMIT
    assert definition["source"]["release_tree"] == campaign_profile.CANONICAL_TREE
    assert definition["bootstrap"] == {
        "children": 1,
        "tasks_per_generation": 3,
        "novelty_pressure": 0.7,
        "solver_model": campaign_profile.MOONSHOT_MODEL,
        "verifier_model": campaign_profile.MOONSHOT_MODEL,
        "mutator_model": campaign_profile.MOONSHOT_MODEL,
        "per_candidate_token_ceiling": 300000,
        "rng_seed": 20260706,
    }
    assert definition["gates"]["exact_route"] == campaign_profile.MOONSHOT_MODEL
    assert "provider_attestation" not in definition["gates"]
    assert manifest["manifest_digest"] == (
        "sha256:28fb5ce1fc61caebf0fdf306b9bc3f6e8190afb1dcfb241dd8d3ab64db5392a9"
    )
    assert provider_selftest._role_bindings(manifest) == {
        "solver": campaign_profile.MOONSHOT_MODEL,
        "verifier": campaign_profile.MOONSHOT_MODEL,
        "mutator": campaign_profile.MOONSHOT_MODEL,
    }


def test_historical_exact_route_gate_remains_fail_closed(tmp_path: Path) -> None:
    manifest = build_manifest(
        campaign_profile.campaign_definition(campaign_profile.PROFILE)
    )
    receipt = {
        "live": True,
        "rows": [
            {
                "requested_model": campaign_profile.MOONSHOT_MODEL,
                "provider": "moonshot",
                "live": True,
                "callable": True,
                "stage": "complete",
                "fallback": False,
            }
        ],
    }
    path = tmp_path / "legacy-provider.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    gate = campaign_gates._provider_gate(manifest, str(path))

    assert gate["name"] == "exact_provider_route"
    assert gate["passed"] is False
    assert gate["code"] == "EXACT_PROVIDER_ROUTE_UNPROVEN"
    assert gate["detail"]["matching_rows"] == 1


def test_paired_profile_binds_injected_clean_release_and_stays_unpowered() -> None:
    definition = campaign_profile.campaign_definition(
        campaign_profile.PAIRED_PROFILE,
        release_identity=CLEAN_IDENTITY,
    )
    manifest = build_manifest(definition)

    assert manifest["source"]["release_commit"] == COMMIT
    assert manifest["source"]["release_tree"] == TREE
    assert set(manifest["limits"].values()) == {None}
    assert manifest["bootstrap"]["role_routes"] == campaign_profile.ROLE_ROUTE_BINDINGS
    assert manifest["bootstrap"]["evaluation_protocol"] == "paired_frozen_v1"
    assert manifest["bootstrap"]["paired_design"]["logical_splits"] == [
        "train",
        "explore",
        "confirm",
        "holdout",
    ]
    assert manifest["gates"]["provider_attestation"] == (
        campaign_profile.PROVIDER_ATTESTATION_POLICY
    )
    assert provider_selftest._role_bindings(manifest) == (
        campaign_profile.ROLE_ROUTE_BINDINGS
    )


def test_paired_profile_rejects_scientific_route_drift() -> None:
    definition = campaign_profile.campaign_definition(
        campaign_profile.PAIRED_PROFILE,
        release_identity=CLEAN_IDENTITY,
    )
    drifted = deepcopy(definition)
    drifted["bootstrap"]["role_routes"]["solver"] = "forge.untrusted.solver"

    with pytest.raises(CampaignContractError) as raised:
        build_manifest(drifted)

    assert raised.value.code == "INVALID_PAIRED_PROFILE"


def test_paired_plan_uses_fresh_clean_release_resolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        campaign_profile,
        "resolve_clean_release_identity",
        lambda: dict(CLEAN_IDENTITY),
    )

    plan = campaign_control.plan_campaign(
        campaign_profile.PAIRED_PROFILE,
        state_root=tmp_path,
    )

    assert plan["campaign_name"] == campaign_profile.PAIRED_PROFILE
    assert plan["powered"] is False
    assert plan["manifest"]["source"]["release_commit"] == COMMIT
    assert plan["manifest"]["source"]["release_tree"] == TREE


def test_paired_plan_accepts_only_a_complete_explicit_limit_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        campaign_profile,
        "resolve_clean_release_identity",
        lambda: dict(CLEAN_IDENTITY),
    )

    plan = campaign_control.plan_campaign(
        campaign_profile.PAIRED_PROFILE,
        state_root=tmp_path,
        limits=EXACT_LIMITS,
    )

    assert plan["powered"] is True
    assert plan["operator_authority_bound"] is False
    assert plan["activation_code"] == "SIGNED_OPERATOR_ENVELOPE_REQUIRED"
    assert plan["manifest"]["limits"] == EXACT_LIMITS

    incomplete = dict(EXACT_LIMITS)
    incomplete.pop("total_requests")
    with pytest.raises(campaign_control.CampaignControlError) as raised:
        campaign_control.plan_campaign(
            campaign_profile.PAIRED_PROFILE,
            state_root=tmp_path,
            limits=incomplete,
        )
    assert raised.value.code == "INVALID_PLAN_LIMITS"


def test_historical_profile_refuses_mutable_limit_injection(tmp_path: Path) -> None:
    with pytest.raises(campaign_control.CampaignControlError) as raised:
        campaign_control.plan_campaign(
            campaign_profile.PROFILE,
            state_root=tmp_path,
            limits=EXACT_LIMITS,
        )

    assert raised.value.code == "INVALID_PLAN_LIMITS"


def test_paired_run_requires_a_live_prepared_challenge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        campaign_profile,
        "resolve_clean_release_identity",
        lambda: dict(CLEAN_IDENTITY),
    )
    plan = campaign_control.plan_campaign(
        campaign_profile.PAIRED_PROFILE,
        state_root=tmp_path,
    )

    with pytest.raises(campaign_control.CampaignControlError) as raised:
        campaign_control.run_campaign(
            plan["manifest_digest"],
            request_id="paired-without-prepare",
            state_root=tmp_path,
        )

    assert raised.value.code == "PROVIDER_CHALLENGE_REQUIRED"
    assert campaign_control.list_campaigns(state_root=tmp_path) == []


def test_paired_prepare_exposes_fence_then_same_request_can_close_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        campaign_profile,
        "resolve_clean_release_identity",
        lambda: dict(CLEAN_IDENTITY),
    )
    plan = campaign_control.plan_campaign(
        campaign_profile.PAIRED_PROFILE,
        state_root=tmp_path,
    )
    digest = plan["manifest_digest"]
    challenge = campaign_control.prepare_campaign(
        digest,
        request_id="paired-probe-1",
        state_root=tmp_path,
    )
    replay = campaign_control.prepare_campaign(
        digest,
        request_id="paired-probe-1",
        state_root=tmp_path,
    )

    assert challenge["dispatch_enabled"] is False
    assert challenge["fencing_token"] > 0
    assert challenge["probe_request_nonce"].startswith("forge-provider-probe-")
    assert replay["replayed"] is True
    assert replay["challenge_digest"] == challenge["challenge_digest"]

    with pytest.raises(campaign_control.CampaignControlError) as wrong_request:
        campaign_control.run_campaign(
            digest,
            request_id="different-probe",
            state_root=tmp_path,
        )
    assert wrong_request.value.code == "PROVIDER_CHALLENGE_REQUIRED"

    blocked = campaign_control.run_campaign(
        digest,
        request_id="paired-probe-1",
        state_root=tmp_path,
    )
    assert blocked["disposition"] == "BLOCKED"
    assert {item["code"] for item in blocked["blockers"]} >= {
        "PROVIDER_RECEIPT_MISSING",
        "GOVERNED_EXECUTOR_NOT_IMPLEMENTED",
    }
    status = campaign_control.campaign_status(
        campaign_profile.PAIRED_PROFILE,
        state_root=tmp_path,
    )
    assert status["state"] == "FAILED"
    assert status["lease"]["fencing_token"] is None


def test_paired_run_verifies_receipt_against_its_live_challenge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        campaign_profile,
        "resolve_clean_release_identity",
        lambda: dict(CLEAN_IDENTITY),
    )
    plan = campaign_control.plan_campaign(
        campaign_profile.PAIRED_PROFILE,
        state_root=tmp_path,
    )
    digest = plan["manifest_digest"]
    challenge = campaign_control.prepare_campaign(
        digest,
        request_id="paired-signed-probe",
        state_root=tmp_path,
    )
    role_rows = {
        "solver": {
            "requested_model": "solver-v1",
            "served_model": "solver-v1",
            "model_family": "solver-family",
            "provider": "provider-a-route",
            "provider_family": "provider-a",
            "physical_transport_identity": "provider:https://a.example/v1",
            "callable": True,
            "live": True,
            "stage": "complete",
            "fallback": False,
        },
        "verifier": {
            "requested_model": "verifier-v1",
            "served_model": "verifier-v1",
            "model_family": "verifier-family",
            "provider": "provider-b-route",
            "provider_family": "provider-b",
            "physical_transport_identity": "provider:https://b.example/v1",
            "callable": True,
            "live": True,
            "stage": "complete",
            "fallback": False,
        },
        "mutator": {
            "requested_model": "mutator-v1",
            "served_model": "mutator-v1",
            "model_family": "solver-family",
            "provider": "provider-a-alias",
            "provider_family": "provider-a",
            "physical_transport_identity": "provider:https://a.example/v1",
            "callable": True,
            "live": True,
            "stage": "complete",
            "fallback": False,
        },
    }
    key_id = "paired-test-probe-key"
    key = Ed25519PrivateKey.generate()
    receipt = provider_selftest.build_provider_attestation(
        plan["manifest"],
        role_rows=role_rows,
        probe_request_nonce=challenge["probe_request_nonce"],
        probe_fencing_token=challenge["fencing_token"],
        signing_key_id=key_id,
        signing_key=key,
    )
    receipt_path = tmp_path / "paired-provider-receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    trust_path = tmp_path / "provider-probe-trust.json"
    trust_path.write_text(
        json.dumps(
            {
                "schema": provider_selftest.PROVIDER_PROBE_TRUST_SCHEMA,
                "keys": {key_id: public_key.hex()},
            }
        ),
        encoding="utf-8",
    )
    trust_path.chmod(0o600)
    monkeypatch.setenv("RSI_LAB_TRUSTED_PROVIDER_PROBE_KEYS", str(trust_path))

    blocked = campaign_control.run_campaign(
        digest,
        request_id="paired-signed-probe",
        provider_receipt_path=str(receipt_path),
        state_root=tmp_path,
    )

    provider_gate = next(
        gate for gate in blocked["gates"] if gate["name"] == "provider_attestation"
    )
    assert provider_gate["passed"] is True
    assert provider_gate["detail"]["probe_authority"]["fencing_token"] == (
        challenge["fencing_token"]
    )
    assert {item["code"] for item in blocked["blockers"]} >= {
        "GOVERNED_EXECUTOR_NOT_IMPLEMENTED"
    }
    assert "PROVIDER_ATTESTATION_INVALID" not in {
        item["code"] for item in blocked["blockers"]
    }


def test_expired_paired_challenge_can_be_refenced_with_a_new_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        campaign_profile,
        "resolve_clean_release_identity",
        lambda: dict(CLEAN_IDENTITY),
    )
    plan = campaign_control.plan_campaign(
        campaign_profile.PAIRED_PROFILE,
        state_root=tmp_path,
    )
    digest = plan["manifest_digest"]
    first = campaign_control.prepare_campaign(
        digest,
        request_id="paired-expiring-probe",
        state_root=tmp_path,
    )
    database = (
        tmp_path / ".dharma" / "forge_lab" / "campaigns" / "control.sqlite3"
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE campaigns SET lease_expires='2000-01-01T00:00:00Z' "
            "WHERE campaign_id=?",
            (campaign_profile.PAIRED_PROFILE,),
        )

    with pytest.raises(campaign_control.CampaignControlError) as expired:
        campaign_control.prepare_campaign(
            digest,
            request_id="paired-expiring-probe",
            state_root=tmp_path,
        )
    assert expired.value.code == "PROVIDER_CHALLENGE_EXPIRED"

    second = campaign_control.prepare_campaign(
        digest,
        request_id="paired-refenced-probe",
        state_root=tmp_path,
    )
    assert second["fencing_token"] > first["fencing_token"]
    assert second["probe_request_nonce"] != first["probe_request_nonce"]


def test_paired_plan_refuses_unproven_release_before_manifest_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse() -> dict[str, str]:
        raise campaign_profile.ReleaseIdentityError("working tree is dirty")

    monkeypatch.setattr(campaign_profile, "resolve_clean_release_identity", refuse)

    with pytest.raises(campaign_control.CampaignControlError) as raised:
        campaign_control.plan_campaign(
            campaign_profile.PAIRED_PROFILE,
            state_root=tmp_path,
        )

    assert raised.value.code == "CLEAN_RELEASE_IDENTITY_UNPROVEN"
    assert not (tmp_path / ".dharma" / "forge_lab" / "manifests").exists()


def test_release_resolver_refuses_dirty_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        campaign_profile,
        "_git_output",
        lambda checkout, *arguments: " M campaign_profile.py",
    )

    with pytest.raises(campaign_profile.ReleaseIdentityError, match="clean committed"):
        campaign_profile.resolve_clean_release_identity(Path("/test/release"))


def test_release_resolver_refuses_head_change_during_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outputs = iter(("", COMMIT, TREE, "", "c" * 40))
    monkeypatch.setattr(
        campaign_profile,
        "_git_output",
        lambda checkout, *arguments: next(outputs),
    )

    with pytest.raises(campaign_profile.ReleaseIdentityError, match="changed"):
        campaign_profile.resolve_clean_release_identity(Path("/test/release"))
