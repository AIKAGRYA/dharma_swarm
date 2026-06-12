from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.runtime import a2a_prod_readiness_solicit


def test_default_reviewers_cover_two_agents_and_three_model_hints() -> None:
    reviewers = a2a_prod_readiness_solicit.DEFAULT_REVIEWERS

    assert len({reviewer.agent_id for reviewer in reviewers}) >= 2
    assert len({reviewer.model_family_hint for reviewer in reviewers}) >= 3
    assert any(reviewer.agent_id == "qwen_code" for reviewer in reviewers)
    assert any(
        reviewer.agent_id == "gemini_reviewer" and reviewer.model_family_hint == "google"
        for reviewer in reviewers
    )
    assert any("ops" in reviewer.role for reviewer in reviewers)
    assert any("security" in reviewer.role or "adversarial" in reviewer.role for reviewer in reviewers)


def test_default_evidence_refs_include_latest_daemon_and_quarantine_receipts() -> None:
    evidence_refs = set(a2a_prod_readiness_solicit.DEFAULT_EVIDENCE_REFS)

    assert "reports/a2a/nats_reset/2026-06-13/A2A_DAEMON_WIRING_AUDIT.json" in evidence_refs
    assert "reports/a2a/nats_reset/2026-06-13/A2A_LIVE_HANDLER_REPAIR_PLAN.json" in evidence_refs
    assert "reports/a2a/nats_reset/2026-06-13/FILE_BUS_GUARD_AFTER_HERMES_DISABLE.json" in evidence_refs
    assert (
        "reports/a2a/hermes_broadcast_guard/2026-06-13/HERMES_ALERT_ROUTER_BROADCAST_GUARD_APPLIED.json"
        in evidence_refs
    )
    assert (
        "reports/a2a/launchagent_quarantine_receipts/20260612T184702Z-a2a-launchagent-quarantine.json"
        in evidence_refs
    )


def test_write_solicitations_creates_request_files_and_receipt(tmp_path: Path) -> None:
    root = tmp_path / "quorum"

    receipt = a2a_prod_readiness_solicit.write_solicitations(
        root=root,
        date="2026-06-13",
        reviewers=[
            a2a_prod_readiness_solicit.ReviewerTarget(
                agent_id="codex_composer",
                model_family_hint="openai",
                role="ops_verifier",
            ),
            a2a_prod_readiness_solicit.ReviewerTarget(
                agent_id="fable_composer",
                model_family_hint="anthropic",
                role="adversarial_security_reviewer",
            ),
            a2a_prod_readiness_solicit.ReviewerTarget(
                agent_id="hermes_m5",
                model_family_hint="hermes",
                role="agent_harness_reviewer",
            ),
        ],
        requested_by="codex_composer",
        evidence_refs=["reports/a2a/nats_reset/2026-06-13/AFTER.json"],
        write=True,
        created_at="2026-06-13T00:00:00+00:00",
    )

    assert receipt["status"] == "SOLICITATION_WRITTEN"
    assert receipt["transport_status"] == "NOT_SENT"
    assert receipt["request_count"] == 3
    assert sorted(receipt["model_family_hints"]) == ["anthropic", "hermes", "openai"]
    assert (root / "2026-06-13" / "SOLICITATION_RECEIPT.json").exists()

    request_path = root / "2026-06-13" / "requests" / "fable_composer.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["schema_version"] == "dharma.a2a.prod_readiness_solicitation.v1"
    assert request["target_agent_id"] == "fable_composer"
    assert request["reviewer_record_schema"] == "dharma.a2a.prod_readiness_reviewer.v1"
    assert request["reviewer_record_path"].endswith("2026-06-13/fable_composer.json")
    assert request["quorum_requirements"]["min_model_families"] == 3


def test_dry_run_does_not_write_files(tmp_path: Path) -> None:
    root = tmp_path / "quorum"

    receipt = a2a_prod_readiness_solicit.write_solicitations(
        root=root,
        date="2026-06-13",
        reviewers=[
            a2a_prod_readiness_solicit.ReviewerTarget(
                agent_id="codex_composer",
                model_family_hint="openai",
                role="ops_verifier",
            )
        ],
        requested_by="codex_composer",
        evidence_refs=["reports/a2a/nats_reset/2026-06-13/AFTER.json"],
        write=False,
        created_at="2026-06-13T00:00:00+00:00",
    )

    assert receipt["status"] == "DRY_RUN"
    assert not root.exists()
    assert receipt["request_paths"] == [
        str(root / "2026-06-13" / "requests" / "codex_composer.json")
    ]


def test_parse_reviewer_spec_rejects_invalid_tokens() -> None:
    with pytest.raises(ValueError, match="--reviewer"):
        a2a_prod_readiness_solicit.parse_reviewer_spec("codex:openai")

    with pytest.raises(ValueError, match="agent_id"):
        a2a_prod_readiness_solicit.parse_reviewer_spec("bad agent:openai:ops")
