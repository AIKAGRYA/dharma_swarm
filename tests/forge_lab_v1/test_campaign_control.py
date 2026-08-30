from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.forge_lab import campaign_control, campaign_event_chain


@pytest.fixture
def isolated_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    state = tmp_path / "state"
    monkeypatch.setenv("RSI_LAB_STATE", str(state))
    monkeypatch.setenv("DHARMA_HOME", str(state / ".dharma"))
    return state


def test_fixed_pilot_runs_five_paired_attempts_with_zero_spend(
    isolated_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_secret = "provider-secret-must-not-be-recorded"
    monkeypatch.setenv("OPENAI_API_KEY", fake_secret)
    plan = campaign_control.plan_campaign(campaign_control.PILOT_PROFILE)

    result = campaign_control.run_campaign(
        plan["manifest_digest"],
        "test-five-paired-attempts",
    )

    closeout = result["closeout"]
    assert closeout["attempt_count"] == 5
    assert closeout["paired_attempt_count"] == 5
    assert closeout["caps_observed"] == {
        "provider_calls": 0,
        "tokens": 0,
        "usd": 0.0,
    }
    assert closeout["evidence_class"] == "ControlPlaneTestOnly"
    assert closeout["scientific_verdict"] == "inconclusive"
    assert closeout["positive_rsi_claim"] is False

    campaign_id = result["campaign_id"]
    status = campaign_control.campaign_status(campaign_id)
    progress = campaign_control.campaign_progress(campaign_id)
    events = campaign_control.campaign_events(campaign_id)
    assert status["campaign"]["state"] == "COMPLETED"
    assert status["campaign"]["attempt_count"] == 5
    assert progress == {
        "campaign": campaign_id,
        "state": "COMPLETED",
        "completed": 5,
        "planned": 5,
        "fraction": 1.0,
    }
    assert [row["sequence"] for row in events["events"]] == list(range(1, 13))
    assert events["events"][-1]["state"] == "COMPLETED"
    previous_event_digest = None
    for event in events["events"]:
        assert event["previous_event_digest"] == previous_event_digest
        unsigned = {key: value for key, value in event.items() if key != "event_digest"}
        assert event["event_digest"] == campaign_control.content_digest(unsigned)
        previous_event_digest = event["event_digest"]

    root = isolated_state / ".dharma" / "forge_lab"
    attempts = sorted((root / "campaigns" / "runs" / campaign_id / "attempts").glob("*.json"))
    assert len(attempts) == 5
    previous_attempt_digest = None
    attempt_digests = []
    for path in attempts:
        row = json.loads(path.read_text(encoding="utf-8"))
        assert row["seed"]["passed"] is True
        assert row["child"]["passed"] is True
        assert row["delta"] == 0
        assert row["positive_rsi_claim"] is False
        assert row["previous_attempt_digest"] == previous_attempt_digest
        unsigned = {key: value for key, value in row.items() if key != "attempt_digest"}
        assert row["attempt_digest"] == campaign_control.content_digest(unsigned)
        previous_attempt_digest = row["attempt_digest"]
        attempt_digests.append(row["attempt_digest"])
    assert closeout["attempt_receipt_digests"] == attempt_digests
    assert closeout["attempts_digest"] == campaign_control.content_digest(
        attempt_digests
    )
    assert closeout["terminal_event_digest"] == previous_event_digest
    assert closeout["closeout_digest"] == campaign_control.content_digest(
        {key: value for key, value in closeout.items() if key != "closeout_digest"}
    )
    assert fake_secret not in "".join(
        path.read_text(encoding="utf-8")
        for path in root.rglob("*")
        if path.is_file()
    )


def test_five_independent_campaign_invocations_are_bounded_and_receipted(
    isolated_state: Path,
) -> None:
    plan = campaign_control.plan_campaign(campaign_control.PILOT_PROFILE)
    results = [
        campaign_control.run_campaign(plan["manifest_digest"], f"bounded-test-{index}")
        for index in range(1, 6)
    ]

    assert len({row["campaign_id"] for row in results}) == 5
    assert all(row["closeout"]["attempt_count"] == 5 for row in results)
    listing = campaign_control.list_campaigns("completed")
    assert listing["count"] == 5
    assert sum(row["attempt_count"] for row in listing["campaigns"]) == 25


def test_campaign_run_is_idempotent_and_manifest_tampering_fails_closed(
    isolated_state: Path,
) -> None:
    plan = campaign_control.plan_campaign(campaign_control.PILOT_PROFILE)
    first = campaign_control.run_campaign(plan["manifest_digest"], "idempotent-pilot")
    second = campaign_control.run_campaign(plan["manifest_digest"], "idempotent-pilot")
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert second["closeout"] == first["closeout"]

    manifest_path = Path(plan["path"])
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["caps"]["provider_calls"] = 1
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(campaign_control.CampaignError, match="digest mismatch"):
        campaign_control.run_campaign(plan["manifest_digest"], "tampered-pilot")


def test_live_profile_and_unsafe_identifiers_remain_fail_closed(
    isolated_state: Path,
) -> None:
    with pytest.raises(campaign_control.CampaignError, match="fail-closed"):
        campaign_control.plan_campaign("explore-open")

    plan = campaign_control.plan_campaign(campaign_control.PILOT_PROFILE)
    with pytest.raises(ValueError, match="safe characters"):
        campaign_control.run_campaign(plan["manifest_digest"], "../escape")


def test_interrupted_campaign_resumes_validated_prefix_without_duplicates(
    isolated_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = campaign_control.plan_campaign(campaign_control.PILOT_PROFILE)
    original_append = campaign_event_chain._append_event
    crashed = False

    def crash_before_third_attempt_event(*args, **kwargs):
        nonlocal crashed
        sequence = int(args[3])
        if sequence == 7 and not crashed:
            crashed = True
            raise RuntimeError("simulated_process_loss")
        return original_append(*args, **kwargs)

    monkeypatch.setattr(
        campaign_event_chain,
        "_append_event",
        crash_before_third_attempt_event,
    )
    with pytest.raises(RuntimeError, match="simulated_process_loss"):
        campaign_control.run_campaign(plan["manifest_digest"], "resume-pilot")

    monkeypatch.setattr(campaign_event_chain, "_append_event", original_append)
    resumed = campaign_control.run_campaign(
        plan["manifest_digest"],
        "resume-pilot",
    )
    assert resumed["resumed"] is True
    assert resumed["closeout"]["resumed_after_interruption"] is True
    events = campaign_control.campaign_events(resumed["campaign_id"])["events"]
    assert [row["sequence"] for row in events] == list(range(1, 13))
    assert len({row["event_digest"] for row in events}) == 12
    run_dir = (
        isolated_state
        / ".dharma"
        / "forge_lab"
        / "campaigns"
        / "runs"
        / resumed["campaign_id"]
    )
    assert len(list((run_dir / "attempts").glob("attempt_*.json"))) == 5


def test_attempt_or_event_tampering_blocks_resume_and_read_views(
    isolated_state: Path,
) -> None:
    plan = campaign_control.plan_campaign(campaign_control.PILOT_PROFILE)
    result = campaign_control.run_campaign(plan["manifest_digest"], "tamper-chain")
    run_dir = (
        isolated_state
        / ".dharma"
        / "forge_lab"
        / "campaigns"
        / "runs"
        / result["campaign_id"]
    )
    attempt_path = run_dir / "attempts" / "attempt_003.json"
    original_attempt = attempt_path.read_text(encoding="utf-8")
    attempt = json.loads(original_attempt)
    attempt["child"]["output"] = -1
    attempt_path.write_text(json.dumps(attempt) + "\n", encoding="utf-8")
    with pytest.raises(campaign_control.CampaignError, match="attempt receipt mismatch"):
        campaign_control.run_campaign(plan["manifest_digest"], "tamper-chain")

    attempt_path.write_text(original_attempt, encoding="utf-8")
    event_path = run_dir / "events.jsonl"
    events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
    events[5]["detail"]["attempt_completed"] = 99
    event_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in events),
        encoding="utf-8",
    )
    with pytest.raises(campaign_control.CampaignError, match="event chain mismatch"):
        campaign_control.campaign_events(result["campaign_id"])
    status = campaign_control.campaign_status(result["campaign_id"])
    assert status["campaign"]["state"] == "CORRUPT"
    assert status["campaign"]["integrity"] == "failed"
