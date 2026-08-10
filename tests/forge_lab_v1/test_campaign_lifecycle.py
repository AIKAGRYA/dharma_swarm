"""Acceptance slice for the minimum governed campaign lifecycle."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys

import pytest

from dharma_swarm.forge_lab import campaign_control
from dharma_swarm.forge_lab.campaign_profile import PROFILE


def _plan_and_run_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[dict, dict]:
    monkeypatch.setenv("RSI_LAB_STATE", str(tmp_path))
    monkeypatch.delenv("RSI_LAB_TRUSTED_OPERATOR_KEYS", raising=False)
    monkeypatch.delenv("RSI_LAB_LIFECYCLE_ACCEPTANCE_RECEIPT", raising=False)
    plan = campaign_control.plan_campaign(PROFILE)
    return plan, campaign_control.run_campaign(plan["manifest_digest"])


def _redigest_receipt(receipt: dict) -> None:
    unsigned = dict(receipt)
    unsigned.pop("receipt_digest", None)
    receipt["receipt_digest"] = (
        f"sha256:{sha256(campaign_control.canonical_json(unsigned)).hexdigest()}"
    )


def test_plan_is_content_addressed_exact_unpowered_and_non_live(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("RSI_LAB_STATE", str(tmp_path))
    monkeypatch.setitem(sys.modules, "dharma_swarm.forge_lab.cli", None)
    monkeypatch.setitem(sys.modules, "dharma_swarm.forge_lab.experiment", None)
    monkeypatch.setitem(sys.modules, "dharma_swarm.forge_v1.providers", None)

    first = campaign_control.plan_campaign(PROFILE)
    first_bytes = Path(first["manifest_path"]).read_bytes()
    second = campaign_control.plan_campaign(PROFILE)

    assert second["manifest_digest"] == first["manifest_digest"]
    assert Path(second["manifest_path"]).read_bytes() == first_bytes
    assert first["provider_calls"] == 0
    assert first["powered"] is False
    assert first["activation_code"] == "HISTORICAL_PROFILE_IMMUTABLE_BLOCKED"
    manifest = first["manifest"]
    assert manifest["source"]["release_commit"] == (
        "309650d5604768a8c90d987170fccf50af6a0536"
    )
    assert manifest["source"]["bootstrap_prior"] == {
        "run_id": "rsi-n30-20260718T131907Z",
        "type": "MostEvolvedBy",
        "metric": "maximum_generation",
        "generation": 30,
        "budget_valid_rows": 31,
        "budget_total_rows": 31,
        "complete_receipts": True,
        "evidence_scope": "bootstrap_prior_only",
    }
    assert manifest["stages"]["primary"]["primary_attempts"] == 1_000
    assert manifest["stages"]["primary"]["seed_counts_as_attempt"] is False
    assert set(manifest["limits"].values()) == {None}
    assert manifest["claims"]["bootstrap_prior_is_fitness_evidence"] is False


def test_manifest_cas_tamper_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("RSI_LAB_STATE", str(tmp_path))
    plan = campaign_control.plan_campaign(PROFILE)
    path = Path(plan["manifest_path"])
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["stages"]["primary"]["primary_attempts"] = 999
    path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(
        campaign_control.CampaignControlError,
        match="does not match|canonical|digest|1000 attempts",
    ):
        campaign_control.load_manifest(plan["manifest_digest"])


def test_only_the_named_governed_profile_is_implemented(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("RSI_LAB_STATE", str(tmp_path))
    with pytest.raises(
        campaign_control.CampaignControlError,
        match="implemented governed profile",
    ):
        campaign_control.plan_campaign("explore-open")


def test_missing_envelope_closes_campaign_with_one_replayable_blocked_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("RSI_LAB_STATE", str(tmp_path))
    monkeypatch.delenv("RSI_LAB_TRUSTED_OPERATOR_KEYS", raising=False)
    monkeypatch.delenv("RSI_LAB_LIFECYCLE_ACCEPTANCE_RECEIPT", raising=False)
    monkeypatch.setitem(sys.modules, "dharma_swarm.forge_lab.experiment", None)
    monkeypatch.setitem(sys.modules, "dharma_swarm.forge_v1.providers", None)
    plan = campaign_control.plan_campaign(PROFILE)

    first = campaign_control.run_campaign(plan["manifest_digest"])
    first_bytes = Path(first["receipt_path"]).read_bytes()
    replay = campaign_control.run_campaign(plan["manifest_digest"])

    assert first["disposition"] == "BLOCKED"
    assert first["technical_disposition"] == "blocked_with_evidence"
    assert first["provider_effects"]["requests_dispatched_by_campaign"] == 0
    assert first["provider_effects"]["paid_calls_authorized"] == 0
    assert first["progress"]["target_primary_attempts"] == 1_000
    assert first["progress"]["terminal_primary_attempts"] == 0
    assert first["cleanup"] == {
        "scratch_created": False,
        "state": "not_required",
        "residuals": [],
    }
    assert {item["code"] for item in first["blockers"]} >= {
        "MISSING_OPERATOR_ENVELOPE",
        "PROVIDER_RECEIPT_MISSING",
        "GOVERNED_EXECUTOR_NOT_IMPLEMENTED",
    }
    assert replay["replayed"] is True
    assert replay["receipt_digest"] == first["receipt_digest"]
    assert Path(replay["receipt_path"]).read_bytes() == first_bytes
    status = campaign_control.campaign_status(PROFILE)
    assert status["state"] == "FAILED"
    assert status["lease"] == {
        "fencing_token": None,
        "holder": None,
        "mode": None,
        "expires_at": None,
    }
    campaign_root = (
        tmp_path / ".dharma" / "forge_lab" / "campaigns" / PROFILE
    )
    assert all(
        (campaign_root / category).is_dir()
        for category in ("control", "receipts", "events", "checkpoints")
    )
    assert not (tmp_path / ".dharma" / "forge_lab" / "scratch").exists()
    from dharma_swarm.forge_lab.campaign_reconcile import reconcile_state

    reconciliation = reconcile_state(tmp_path, campaign_id=PROFILE)
    assert not [
        finding
        for finding in reconciliation["findings"]
        if finding["code"] == "MISSING_ROOT"
    ]
    assert reconciliation["repairs"] == []
    events = campaign_control.campaign_events(PROFILE)
    assert [event["sequence"] for event in events] == list(
        range(1, len(events) + 1)
    )
    assert len(
        list(
            (
                tmp_path
                / ".dharma"
                / "forge_lab"
                / "campaigns"
                / PROFILE
                / "receipts"
            ).glob("blocked-*.json")
        )
    ) == 1


def test_blocked_replay_rejects_tampered_self_digest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plan, blocked = _plan_and_run_blocked(monkeypatch, tmp_path)
    receipt_path = Path(blocked["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["blockers"][0]["detail"] = "tampered-after-terminalization"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(campaign_control.CampaignControlError) as raised:
        campaign_control.run_campaign(plan["manifest_digest"])

    assert raised.value.code == "BLOCKED_RECEIPT_INVALID"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("campaign_id", "different-campaign"),
        ("campaign_name", "different-campaign"),
        ("manifest_digest", f"sha256:{'0' * 64}"),
        ("request_id", "different-request"),
    ],
)
def test_blocked_replay_rejects_redigested_identity_substitution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
    replacement: str,
) -> None:
    plan, blocked = _plan_and_run_blocked(monkeypatch, tmp_path)
    receipt_path = Path(blocked["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt[field] = replacement
    _redigest_receipt(receipt)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(campaign_control.CampaignControlError) as raised:
        campaign_control.run_campaign(plan["manifest_digest"])

    assert raised.value.code == "BLOCKED_RECEIPT_INVALID"


@pytest.mark.parametrize("canonical_mutation", ["nonterminal_state", "active_lease"])
def test_blocked_replay_requires_failed_state_and_cleared_lease(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    canonical_mutation: str,
) -> None:
    plan, _blocked = _plan_and_run_blocked(monkeypatch, tmp_path)
    database = (
        tmp_path / ".dharma" / "forge_lab" / "campaigns" / "control.sqlite3"
    )
    with sqlite3.connect(database) as connection:
        if canonical_mutation == "nonterminal_state":
            connection.execute(
                "UPDATE campaigns SET state='CLOSING' WHERE campaign_id=?",
                (PROFILE,),
            )
        else:
            connection.execute(
                """UPDATE campaigns
                SET active_fence=41,lease_holder='injected-holder',
                    lease_mode='terminal_only',lease_expires='2999-01-01T00:00:00Z'
                WHERE campaign_id=?""",
                (PROFILE,),
            )

    with pytest.raises(campaign_control.CampaignControlError) as raised:
        campaign_control.run_campaign(plan["manifest_digest"])

    assert raised.value.code == "BLOCKED_RECEIPT_INVALID"


def test_transition_failure_leaves_no_receipt_and_retry_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from dharma_swarm.forge_lab.campaign_store import CampaignStore
    from dharma_swarm.forge_lab.campaign_store_schema import StoreError

    monkeypatch.setenv("RSI_LAB_STATE", str(tmp_path))
    plan = campaign_control.plan_campaign(PROFILE)
    original_apply_action = CampaignStore.apply_action

    def fail_closing(self, campaign_id, **kwargs):
        if kwargs["request_id"].endswith(".closing"):
            raise StoreError("INJECTED_STORE_FAILURE", "closing transition failed")
        return original_apply_action(self, campaign_id, **kwargs)

    monkeypatch.setattr(CampaignStore, "apply_action", fail_closing)
    with pytest.raises(campaign_control.CampaignControlError) as first_failure:
        campaign_control.run_campaign(plan["manifest_digest"])
    assert first_failure.value.code == "INJECTED_STORE_FAILURE"

    receipt_directory = (
        tmp_path / ".dharma" / "forge_lab" / "campaigns" / PROFILE / "receipts"
    )
    assert not list(receipt_directory.glob("blocked-*.json"))
    status = campaign_control.campaign_status(PROFILE)
    assert status["state"] == "DRAINING"
    assert status["lease"]["fencing_token"] is not None

    monkeypatch.setattr(CampaignStore, "apply_action", original_apply_action)
    with pytest.raises(campaign_control.CampaignControlError) as retry_failure:
        campaign_control.run_campaign(plan["manifest_digest"])
    assert retry_failure.value.code == "CAMPAIGN_RUN_INCOMPLETE"
    assert campaign_control.campaign_status(PROFILE)["state"] == "DRAINING"


def test_receipt_write_failure_occurs_after_terminal_state_and_release(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("RSI_LAB_STATE", str(tmp_path))
    plan = campaign_control.plan_campaign(PROFILE)
    original_atomic_json = campaign_control._atomic_json

    def fail_receipt_write(_path, _payload):
        raise OSError("injected receipt write failure")

    monkeypatch.setattr(campaign_control, "_atomic_json", fail_receipt_write)
    with pytest.raises(campaign_control.CampaignControlError) as first_failure:
        campaign_control.run_campaign(plan["manifest_digest"])
    assert first_failure.value.code == "BLOCKED_RECEIPT_WRITE_FAILED"

    status = campaign_control.campaign_status(PROFILE)
    assert status["state"] == "FAILED"
    assert status["lease"] == {
        "fencing_token": None,
        "holder": None,
        "mode": None,
        "expires_at": None,
    }
    receipt_directory = (
        tmp_path / ".dharma" / "forge_lab" / "campaigns" / PROFILE / "receipts"
    )
    assert not list(receipt_directory.glob("blocked-*.json"))

    monkeypatch.setattr(campaign_control, "_atomic_json", original_atomic_json)
    with pytest.raises(campaign_control.CampaignControlError) as retry_failure:
        campaign_control.run_campaign(plan["manifest_digest"])
    assert retry_failure.value.code == "CAMPAIGN_RUN_INCOMPLETE"


def test_cli_plan_run_query_stop_surface_is_operational_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    from dharma_swarm.forge_lab.rsi_cli import main

    monkeypatch.setenv("RSI_LAB_STATE", str(tmp_path))
    assert main(["campaign", "plan", "--profile", PROFILE, "--json"]) == 0
    plan = json.loads(capsys.readouterr().out)
    digest = plan["result"]["manifest_digest"]

    assert (
        main(
            [
                "campaign",
                "run",
                "--manifest",
                digest,
                "--request-id",
                "cli-blocked-run",
                "--json",
            ]
        )
        == 7
    )
    blocked_capture = capsys.readouterr()
    blocked = json.loads(blocked_capture.out)
    assert blocked["ok"] is False
    assert blocked["error"]["code"] == "CAMPAIGN_BLOCKED"
    assert blocked["result"]["disposition"] == "BLOCKED"
    assert blocked["result"]["provider_effects"]["requests_dispatched_by_campaign"] == 0

    for command in (
        ["campaign", "list", "--json"],
        ["campaign", "status", PROFILE, "--json"],
        ["campaign", "progress", PROFILE, "--json"],
        ["campaign", "events", PROFILE, "--json"],
        ["campaign", "stop", PROFILE, "--json"],
    ):
        assert main(command) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
