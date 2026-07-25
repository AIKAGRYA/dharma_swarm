import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import pytest
import yaml
from scripts.runtime import pr_merge_control as prc


def _ci_required_success_rollup():
    return [
        {"name": "DocOps integrity gate", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "Coherence Delta PR body", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {
            "name": "Onboarding admission parity",
            "status": "COMPLETED",
            "conclusion": "SUCCESS",
        },
        {"name": "gitleaks", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "pytest (3.11)", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "pytest (3.12)", "status": "COMPLETED", "conclusion": "SUCCESS"},
    ]


def test_classify_pr_blocks_failing_checks():
    pr = {
        "number": 1,
        "title": "bad",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [
            {"name": "tests", "status": "COMPLETED", "conclusion": "FAILURE"},
        ],
    }

    result = prc.classify_pr(pr)

    assert result["status"] == "BLOCKED_CHECKS"
    assert result["checks"]["failing"] == ["tests"]


def test_classify_pr_uses_latest_duplicate_check_run():
    pr = {
        "number": 1,
        "title": "rerun",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [
            {
                "name": "Coherence Delta PR body",
                "status": "COMPLETED",
                "conclusion": "FAILURE",
                "completedAt": "2026-06-01T20:41:29Z",
            },
            {
                "name": "Coherence Delta PR body",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
                "completedAt": "2026-06-01T20:42:19Z",
            },
        ],
    }

    result = prc.classify_pr(pr)

    assert result["status"] == "GITHUB_GREEN_NEEDS_PACKET"
    assert result["checks"]["failing"] == []
    assert result["checks"]["passing"] == ["Coherence Delta PR body"]
    assert result["checks"]["raw_total"] == 2
    assert result["checks"]["total"] == 1


def test_classify_pr_newest_run_wins_even_when_older_run_finishes_later():
    """Duplicate runs are ordered by start time: an older run that completes
    after a newer failing run must not flip the context green."""
    pr = {
        "number": 1,
        "title": "overlapping rerun",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [
            {
                "name": "pytest (3.11)",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
                "startedAt": "2026-06-01T10:00:00Z",
                "completedAt": "2026-06-01T10:10:00Z",
            },
            {
                "name": "pytest (3.11)",
                "status": "COMPLETED",
                "conclusion": "FAILURE",
                "startedAt": "2026-06-01T10:05:00Z",
                "completedAt": "2026-06-01T10:06:00Z",
            },
        ],
    }

    result = prc.classify_pr(pr)

    assert result["checks"]["failing"] == ["pytest (3.11)"]
    assert result["checks"]["passing"] == []
    assert result["checks"]["total"] == 1


def test_classify_pr_requires_packet_when_github_green():
    pr = {
        "number": 2,
        "title": "good",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [
            {"name": "tests", "status": "COMPLETED", "conclusion": "SUCCESS"},
        ],
    }

    result = prc.classify_pr(pr)

    assert result["status"] == "GITHUB_GREEN_NEEDS_PACKET"
    assert result["checks"]["passing"] == ["tests"]


def test_coherence_results_rejects_placeholder_field():
    body = """
- Organ touched: docs/governance
- Declared-vs-actual gap closed: TODO
- Proof that re-reads the map: read COHERENCE_DELTA.md
- New drift introduced: none
"""

    result = prc.coherence_results(body)

    assert result["ok"] is False
    assert result["fields"]["Declared-vs-actual gap closed"]["ok"] is False


def test_coherence_results_accepts_substantive_fields():
    body = """
- Organ touched: `scripts/runtime/pr_merge_control.py` (operator review lane)
- Declared-vs-actual gap closed: makes PR review receipts explicit before merge.
- Proof that re-reads the map: checked COHERENCE_DELTA.md and AgentOps boundary.
- New drift introduced: no runtime authority change; merge command stays confirmation-gated.
"""

    result = prc.coherence_results(body)

    assert result["ok"] is True


def test_risk_from_files_flags_hot_paths():
    files = [
        {"filename": "dharma_swarm/telos_gates.py", "additions": 3, "deletions": 1},
        {"filename": "tests/test_telos.py", "additions": 5, "deletions": 0},
    ]

    result = prc.risk_from_files(files)

    assert result["level"] == "CRITICAL"
    assert "dharma_swarm/telos_gates.py" in result["hot_paths"]


def test_required_reviewers_can_be_explicitly_none():
    args = argparse.Namespace(required_reviewers="none")

    assert prc.required_reviewer_agents(args) == []


def test_claude_review_env_scrubs_anthropic_api_key_by_default():
    command, env = prc.review_command_and_env(
        "claude",
        {
            "ANTHROPIC_API_KEY": "depleted",
            "PATH": "/usr/bin",
        },
    )

    assert "-p" in command
    assert "--max-turns" in command
    assert "ANTHROPIC_API_KEY" not in env


def test_claude_review_env_can_opt_into_api_key():
    _, env = prc.review_command_and_env(
        "claude",
        {
            "ANTHROPIC_API_KEY": "funded",
            "DHARMA_CLAUDE_REVIEW_USE_API_KEY": "1",
            "PATH": "/usr/bin",
        },
    )

    assert env["ANTHROPIC_API_KEY"] == "funded"


def test_codex_review_defaults_to_bounded_reasoning():
    command, _ = prc.review_command_and_env("codex", {"PATH": "/usr/bin"})

    assert command[:2] == ["codex", "exec"]
    assert "--ephemeral" in command
    assert "model_reasoning_effort=\"medium\"" in command


def test_extract_review_verdict_from_verdict_section():
    text = """
## Verdict
REQUEST_CHANGES

## Findings
1. Needs work.
"""

    assert prc.extract_review_verdict(text) == "REQUEST_CHANGES"


def test_extract_review_verdict_rejects_placeholder_line():
    text = """
## Verdict
APPROVE | REQUEST_CHANGES | BLOCKED | NEEDS_HUMAN
"""

    assert prc.extract_review_verdict(text) == "UNKNOWN"


def test_run_agent_process_captures_success():
    result = prc.run_agent_process(
        [sys.executable, "-c", "import sys; print('## Verdict\\nAPPROVE\\n\\n## Findings\\n1. clean'); sys.stdin.read()"],
        "prompt body",
        {},
        timeout_s=2,
        kill_grace_s=0.1,
    )

    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    assert "APPROVE" in result["stdout"]


def test_run_agent_process_times_out_and_kills():
    result = prc.run_agent_process(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        "prompt body",
        {},
        timeout_s=0.1,
        kill_grace_s=0.1,
    )

    assert result["status"] == "timeout"
    assert result["timed_out"] is True
    assert result["exit_code"] == 124
    assert result["killed"] in {"term", "kill"}


def test_agent_review_status_blocks_timed_out_receipt(tmp_path):
    (tmp_path / "codex_review.md").write_text("## Verdict\nBLOCKED\n\n## Findings\n1. timed out\n", encoding="utf-8")
    prc.write_json(
        tmp_path / "codex_review_receipt.json",
        {
            "status": "timeout",
            "exit_code": 124,
            "timed_out": True,
            "timeout_s": 1,
        },
    )

    status = prc.load_agent_review_status(tmp_path, "codex")
    blockers = prc.agent_review_blockers(status, human_approved=False)

    assert "Codex review timed out after 1s" in blockers
    assert "Codex review verdict=BLOCKED" in blockers


def test_needs_human_verdict_requires_human_approved(tmp_path):
    (tmp_path / "claude_review.md").write_text("## Verdict\nNEEDS_HUMAN\n\n## Findings\n1. human gate\n", encoding="utf-8")
    prc.write_json(
        tmp_path / "claude_review_receipt.json",
        {
            "status": "completed",
            "exit_code": 0,
            "timed_out": False,
        },
    )

    status = prc.load_agent_review_status(tmp_path, "claude")

    assert "Claude review verdict=NEEDS_HUMAN requires --human-approved" in prc.agent_review_blockers(status, human_approved=False)
    assert prc.agent_review_blockers(status, human_approved=True) == []


def test_select_fanout_items_prefers_allowed_statuses_in_order():
    summary = {
        "items": [
            {"number": 10, "status": "BLOCKED_CHECKS", "title": "red", "updatedAt": "2026-06-01T00:00:00Z"},
            {"number": 11, "status": "NEEDS_AGENT_REVIEW", "title": "needs review", "updatedAt": "2026-06-01T00:00:00Z"},
            {"number": 12, "status": "GITHUB_GREEN_NEEDS_PACKET", "title": "green", "updatedAt": "2026-06-01T00:00:00Z"},
            {"number": 13, "status": "GITHUB_GREEN_NEEDS_PACKET", "title": "green 2", "updatedAt": "2026-06-02T00:00:00Z"},
        ]
    }

    selected = prc.select_fanout_items(
        summary,
        statuses=["GITHUB_GREEN_NEEDS_PACKET", "NEEDS_AGENT_REVIEW"],
        max_prs=3,
    )

    assert [item["number"] for item in selected] == [12, 13, 11]


def _write_current_fanout_packet(
    state_root,
    *,
    pr_number=12,
    head_sha="abc123",
    base_sha="base123",
    updated_at="2026-06-01T02:00:00Z",
    gate_decision="MERGE_CANDIDATE",
):
    packet_dir = state_root / f"pr-{pr_number}" / "20260601T020000Z"
    packet_dir.mkdir(parents=True)
    prc.write_json(
        packet_dir / "FACTS.json",
        {
            "pr": {
                "number": pr_number,
                "headRefOid": head_sha,
                "baseRefOid": base_sha,
                "updatedAt": updated_at,
            },
            "classification": {
                "status": "GITHUB_GREEN_NEEDS_PACKET",
                "reviewDecision": "NONE",
            },
        },
    )
    prc.write_json(packet_dir / "MERGE_GATE.json", {"decision": gate_decision, "blockers": []})
    return packet_dir


def test_select_fanout_plan_skips_current_packet_gate(tmp_path):
    packet_dir = _write_current_fanout_packet(tmp_path)
    summary = {
        "items": [
            {
                "number": 12,
                "title": "already packeted",
                "status": "GITHUB_GREEN_NEEDS_PACKET",
                "head_sha": "abc123",
                "base_sha": "base123",
                "updatedAt": "2026-06-01T02:00:00Z",
                "reviewDecision": "NONE",
            },
            {
                "number": 13,
                "title": "new work",
                "status": "GITHUB_GREEN_NEEDS_PACKET",
                "head_sha": "def456",
                "base_sha": "base123",
                "updatedAt": "2026-06-01T03:00:00Z",
                "reviewDecision": "NONE",
            },
        ]
    }

    plan = prc.select_fanout_plan(
        summary,
        statuses=["GITHUB_GREEN_NEEDS_PACKET"],
        max_prs=1,
        state_root=tmp_path,
        skip_current=True,
    )

    assert [item["number"] for item in plan["selected"]] == [13]
    assert plan["skipped_current"][0]["number"] == 12
    assert plan["skipped_current"][0]["packet_dir"] == str(packet_dir)


def test_select_fanout_plan_reprocesses_when_pr_updated_timestamp_changes(tmp_path):
    _write_current_fanout_packet(tmp_path, updated_at="2026-06-01T02:00:00Z")
    summary = {
        "items": [
            {
                "number": 12,
                "title": "metadata changed",
                "status": "GITHUB_GREEN_NEEDS_PACKET",
                "head_sha": "abc123",
                "base_sha": "base123",
                "updatedAt": "2026-06-01T02:05:00Z",
                "reviewDecision": "NONE",
            }
        ]
    }

    plan = prc.select_fanout_plan(
        summary,
        statuses=["GITHUB_GREEN_NEEDS_PACKET"],
        max_prs=1,
        state_root=tmp_path,
        skip_current=True,
    )

    assert [item["number"] for item in plan["selected"]] == [12]
    assert plan["skipped_current"] == []


def test_select_fanout_plan_reprocesses_when_head_changes(tmp_path):
    _write_current_fanout_packet(tmp_path, head_sha="abc123")
    summary = {
        "items": [
            {
                "number": 12,
                "title": "new head",
                "status": "GITHUB_GREEN_NEEDS_PACKET",
                "head_sha": "def456",
                "base_sha": "base123",
                "updatedAt": "2026-06-01T02:05:00Z",
                "reviewDecision": "NONE",
            }
        ]
    }

    plan = prc.select_fanout_plan(
        summary,
        statuses=["GITHUB_GREEN_NEEDS_PACKET"],
        max_prs=1,
        state_root=tmp_path,
        skip_current=True,
    )

    assert [item["number"] for item in plan["selected"]] == [12]
    assert plan["skipped_current"] == []


def test_select_fanout_plan_reprocesses_when_base_changes(tmp_path):
    _write_current_fanout_packet(tmp_path, base_sha="base123")
    summary = {
        "items": [
            {
                "number": 12,
                "title": "new base",
                "status": "GITHUB_GREEN_NEEDS_PACKET",
                "head_sha": "abc123",
                "base_sha": "base456",
                "updatedAt": "2026-06-01T02:00:00Z",
                "reviewDecision": "NONE",
            }
        ]
    }

    plan = prc.select_fanout_plan(
        summary,
        statuses=["GITHUB_GREEN_NEEDS_PACKET"],
        max_prs=1,
        state_root=tmp_path,
        skip_current=True,
    )

    assert [item["number"] for item in plan["selected"]] == [12]
    assert plan["skipped_current"] == []


def test_select_fanout_plan_reprocesses_blocked_gate(tmp_path):
    _write_current_fanout_packet(tmp_path, gate_decision="BLOCKED")
    summary = {
        "items": [
            {
                "number": 12,
                "title": "blocked gate",
                "status": "GITHUB_GREEN_NEEDS_PACKET",
                "head_sha": "abc123",
                "base_sha": "base123",
                "updatedAt": "2026-06-01T02:00:00Z",
                "reviewDecision": "NONE",
            }
        ]
    }

    plan = prc.select_fanout_plan(
        summary,
        statuses=["GITHUB_GREEN_NEEDS_PACKET"],
        max_prs=1,
        state_root=tmp_path,
        skip_current=True,
    )

    assert [item["number"] for item in plan["selected"]] == [12]
    assert plan["skipped_current"] == []


def test_select_fanout_plan_can_force_reprocess_current(tmp_path):
    _write_current_fanout_packet(tmp_path)
    summary = {
        "items": [
            {
                "number": 12,
                "title": "force",
                "status": "GITHUB_GREEN_NEEDS_PACKET",
                "head_sha": "abc123",
                "base_sha": "base123",
                "updatedAt": "2026-06-01T02:00:00Z",
                "reviewDecision": "NONE",
            }
        ]
    }

    plan = prc.select_fanout_plan(
        summary,
        statuses=["GITHUB_GREEN_NEEDS_PACKET"],
        max_prs=1,
        state_root=tmp_path,
        skip_current=False,
    )

    assert [item["number"] for item in plan["selected"]] == [12]
    assert plan["skipped_current"] == []


def test_select_fanout_plan_zero_max_selects_none(tmp_path):
    summary = {
        "items": [
            {
                "number": 12,
                "title": "would otherwise select",
                "status": "GITHUB_GREEN_NEEDS_PACKET",
                "head_sha": "abc123",
                "base_sha": "base123",
                "updatedAt": "2026-06-01T02:00:00Z",
                "reviewDecision": "NONE",
            }
        ]
    }

    plan = prc.select_fanout_plan(
        summary,
        statuses=["GITHUB_GREEN_NEEDS_PACKET"],
        max_prs=0,
        state_root=tmp_path,
        skip_current=False,
    )

    assert plan == {"selected": [], "skipped_current": []}


def test_select_fanout_plan_zero_max_does_not_scan_current_packets(tmp_path):
    _write_current_fanout_packet(tmp_path)
    summary = {
        "items": [
            {
                "number": 12,
                "title": "current but disabled",
                "status": "GITHUB_GREEN_NEEDS_PACKET",
                "head_sha": "abc123",
                "base_sha": "base123",
                "updatedAt": "2026-06-01T02:00:00Z",
                "reviewDecision": "NONE",
            }
        ]
    }

    plan = prc.select_fanout_plan(
        summary,
        statuses=["GITHUB_GREEN_NEEDS_PACKET"],
        max_prs=0,
        state_root=tmp_path,
        skip_current=True,
    )

    assert plan == {"selected": [], "skipped_current": []}


def test_should_skip_current_fanout_only_for_packet_only_off_mode():
    base = {
        "reprocess_current": False,
        "packet_only": True,
        "merge_mode": "off",
    }

    assert prc.should_skip_current_fanout(argparse.Namespace(**base)) is True
    assert prc.should_skip_current_fanout(argparse.Namespace(**{**base, "packet_only": False})) is False
    assert prc.should_skip_current_fanout(argparse.Namespace(**{**base, "merge_mode": "auto-when-clean"})) is False
    assert prc.should_skip_current_fanout(argparse.Namespace(**{**base, "reprocess_current": True})) is False


def test_build_queue_summary_counts_statuses():
    prs = [
        {
            "number": 1,
            "title": "good",
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": [{"name": "tests", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        },
        {
            "number": 2,
            "title": "bad",
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": [{"name": "tests", "status": "COMPLETED", "conclusion": "FAILURE"}],
        },
    ]

    summary = prc.build_queue_summary(prs, "owner/repo")

    assert summary["repo"] == "owner/repo"
    assert summary["counts"] == {"GITHUB_GREEN_NEEDS_PACKET": 1, "BLOCKED_CHECKS": 1}


def test_build_a2a_fanout_messages_targets_dynamic_fleet(tmp_path):
    messages = prc.build_a2a_fanout_messages(
        repo="owner/repo",
        run_id="20260604T000000Z",
        queue_summary={"total": 2, "counts": {"GITHUB_GREEN_NEEDS_PACKET": 1}},
        selected=[{"number": 12, "status": "GITHUB_GREEN_NEEDS_PACKET", "title": "green"}],
        processed=[],
        fanout_dir=tmp_path / "fanout",
        subjects=list(prc.DEFAULT_A2A_NATS_SUBJECTS),
        required_reviewers=["copilot", "claude", "devin"],
        merge_mode="auto-when-clean",
        dry_run=True,
        packet_only=False,
    )

    assert "dharma.a2a.github_copilot" in [message["subject"] for message in messages]
    assert "dharma.a2a.claude" in [message["subject"] for message in messages]
    assert "dharma.a2a.devin" in [message["subject"] for message in messages]
    assert "github_copilot" in messages[0]["payload"]["agent_roster"]
    assert messages[0]["payload"]["required_reviewers"] == ["copilot", "claude", "devin"]
    assert messages[0]["payload"]["authority"] == "conditional_merge"
    assert "conditional_merge_after_clean_gate" in messages[0]["payload"]["allowed_actions"]
    assert "unconditional_merge" in messages[0]["payload"]["forbidden_actions"]


def test_publish_a2a_fanout_session_blocks_when_required_secrets_missing(tmp_path):
    receipt = prc.publish_a2a_fanout_session(
        repo="owner/repo",
        run_id="run",
        queue_summary={"total": 0, "counts": {}},
        selected=[],
        processed=[],
        fanout_dir=tmp_path / "fanout",
        subjects=["dharma.a2a.fleet"],
        required_reviewers=["copilot", "claude", "devin"],
        merge_mode="off",
        dry_run=True,
        packet_only=False,
        required=True,
        timeout_s=0.1,
        env={},
        publisher=lambda _config, _messages, _timeout: [],
    )

    assert receipt["status"] == "BLOCKED"
    assert receipt["code"] == "NATS_SECRETS_MISSING"
    assert set(receipt["config"]["missing"]) == set(prc.NATS_REQUIRED_SECRET_NAMES)


def test_nats_config_records_ca_pem_without_leaking_secret_material():
    config = prc._nats_config(
        {
            "DEVIN_NATS_URL": "wss://nats.example.test:8443",
            "DEVIN_NATS_USER": "devin",
            "DEVIN_NATS_PW": "super-secret",
            "DEVIN_NATS_CA_PEM": "-----BEGIN CERTIFICATE-----\\nabc\\n-----END CERTIFICATE-----",
            "DEVIN_NATS_TLS_HOSTNAME": "nats.agni.example",
        },
        require_devin_secrets=True,
    )

    redacted = prc._redacted_nats_config(config)

    assert config.ca_pem == "-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n"
    assert config.ca_source == "env_pem"
    assert config.tls_hostname == "nats.agni.example"
    assert config.credential_family == "devin"
    assert redacted["has_ca_pem"] is True
    assert redacted["ca_source"] == "env_pem"
    assert redacted["tls_hostname"] == "nats.agni.example"
    assert redacted["tls_trust"] == "custom_ca_pem"
    assert redacted["credential_family"] == "devin"
    assert "BEGIN CERTIFICATE" not in str(redacted)
    assert "super-secret" not in str(redacted)


def test_nats_config_loads_ca_from_env_file(tmp_path):
    ca_path = tmp_path / "agni-ca.pem"
    ca_path.write_text("-----BEGIN CERTIFICATE-----\nfile\n-----END CERTIFICATE-----\n", encoding="utf-8")

    config = prc._nats_config(
        {
            "DEVIN_NATS_URL": "wss://nats.example.test:8443",
            "DEVIN_NATS_USER": "devin",
            "DEVIN_NATS_PW": "super-secret",
            "DEVIN_NATS_CA_FILE": str(ca_path),
        },
        require_devin_secrets=True,
    )

    assert config.ca_pem == "-----BEGIN CERTIFICATE-----\nfile\n-----END CERTIFICATE-----\n"
    assert config.ca_source == "env_file"
    assert prc._redacted_nats_config(config)["ca_source"] == "env_file"


def test_nats_config_falls_back_to_repo_agni_ca(tmp_path, monkeypatch):
    repo_ca_path = tmp_path / "agni-ws-ca.pem"
    repo_ca_path.write_text("-----BEGIN CERTIFICATE-----\nrepo\n-----END CERTIFICATE-----\n", encoding="utf-8")
    monkeypatch.setattr(prc, "AGNI_WS_CA_PATH", repo_ca_path)

    config = prc._nats_config(
        {
            "DEVIN_NATS_URL": "wss://nats.example.test:8443",
            "DEVIN_NATS_USER": "devin",
            "DEVIN_NATS_PW": "super-secret",
        },
        require_devin_secrets=True,
    )

    assert config.ca_pem == "-----BEGIN CERTIFICATE-----\nrepo\n-----END CERTIFICATE-----\n"
    assert config.ca_source == "repo_agni_ws_ca"
    assert prc._redacted_nats_config(config)["ca_source"] == "repo_agni_ws_ca"


def test_nats_config_prefers_merge_master_mike_credentials():
    config = prc._nats_config(
        {
            "MERGE_MASTER_MIKE_NATS_URL": "wss://mike-nats.example.test:8443",
            "MERGE_MASTER_MIKE_NATS_USER": "merge_master_mike",
            "MERGE_MASTER_MIKE_NATS_PW": "mike-secret",
            "MERGE_MASTER_MIKE_NATS_CA_PEM": "-----BEGIN CERTIFICATE-----\\nmike\\n-----END CERTIFICATE-----",
            "DEVIN_NATS_URL": "wss://devin-nats.example.test:8443",
            "DEVIN_NATS_USER": "devin",
            "DEVIN_NATS_PW": "devin-secret",
            "DEVIN_NATS_CA_PEM": "-----BEGIN CERTIFICATE-----\\ndevin\\n-----END CERTIFICATE-----",
        },
        require_devin_secrets=True,
    )

    assert config.endpoint == "wss://mike-nats.example.test:8443"
    assert config.user == "merge_master_mike"
    assert config.credential == "mike-secret"
    assert config.ca_pem == "-----BEGIN CERTIFICATE-----\nmike\n-----END CERTIFICATE-----\n"
    assert config.credential_family == "merge_master_mike"
    assert config.missing == ()


def test_nats_config_requires_complete_mike_family_when_any_mike_secret_present():
    config = prc._nats_config(
        {
            "MERGE_MASTER_MIKE_NATS_URL": "wss://mike-nats.example.test:8443",
            "DEVIN_NATS_URL": "wss://devin-nats.example.test:8443",
            "DEVIN_NATS_USER": "devin",
            "DEVIN_NATS_PW": "devin-secret",
        },
        require_devin_secrets=True,
    )

    assert config.credential_family == "merge_master_mike"
    assert set(config.missing) == {"MERGE_MASTER_MIKE_NATS_USER", "MERGE_MASTER_MIKE_NATS_PW"}


def test_nats_tls_kwargs_loads_custom_ca_and_hostname(monkeypatch):
    seen = {}

    class FakeTLSContext:
        def load_verify_locations(self, *, cadata):
            seen["cadata"] = cadata

    fake_context = FakeTLSContext()

    def fake_create_default_context(*, purpose):
        seen["purpose"] = purpose
        return fake_context

    monkeypatch.setattr(prc.ssl, "create_default_context", fake_create_default_context)
    kwargs = prc._nats_tls_kwargs(
        prc.NATSConfig(
            endpoint="wss://nats.example.test:8443",
            user="devin",
            credential="credential",
            missing=(),
            ca_pem="-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n",
            tls_hostname="nats.agni.example",
        )
    )

    assert kwargs["tls"] is fake_context
    assert kwargs["tls_hostname"] == "nats.agni.example"
    assert seen["purpose"] == prc.ssl.Purpose.SERVER_AUTH
    assert seen["cadata"] == "-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n"


def test_publish_a2a_fanout_session_records_verified_acks_without_secret(tmp_path):
    seen = {}

    def publisher(config, messages, timeout_s):
        seen["endpoint"] = config.endpoint
        seen["timeout_s"] = timeout_s
        return [
            {
                "subject": message["subject"],
                "kind": message["payload"]["kind"],
                "to": message["payload"]["to"],
                "ack_verified": True,
                "ack_tier": "JETSTREAM_PUB_ACK",
                "stream": "DHARMA_A2A",
                "seq": index + 1,
            }
            for index, message in enumerate(messages)
        ]

    receipt = prc.publish_a2a_fanout_session(
        repo="owner/repo",
        run_id="run",
        queue_summary={"total": 1, "counts": {"NEEDS_AGENT_REVIEW": 1}},
        selected=[{"number": 9, "status": "NEEDS_AGENT_REVIEW", "title": "needs review"}],
        processed=[],
        fanout_dir=tmp_path / "fanout",
        subjects=["dharma.a2a.fleet", "dharma.a2a.merge_master_mike"],
        required_reviewers=["copilot", "claude", "devin"],
        merge_mode="auto-when-clean",
        dry_run=False,
        packet_only=True,
        required=True,
        timeout_s=3.0,
        env={
            "DEVIN_NATS_URL": "wss://nats.example.test:8443",
            "DEVIN_NATS_USER": "devin",
            "DEVIN_NATS_PW": "super-secret",
        },
        publisher=publisher,
    )

    assert seen == {"endpoint": "wss://nats.example.test:8443", "timeout_s": 3.0}
    assert receipt["status"] == "OK"
    assert receipt["code"] == "NATS_ACK_VERIFIED"
    assert len(receipt["acks"]) == 2
    assert "super-secret" not in str(receipt)


def test_a2a_publisher_deadline_bounds_slow_publish(monkeypatch):
    async def slow_publish(_config, _messages, _timeout_s):
        await asyncio.sleep(0.2)
        return []

    monkeypatch.setattr(prc, "_publish_a2a_messages_async", slow_publish)
    started = time.monotonic()

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(
            prc._publish_a2a_messages_with_deadline(
                prc.NATSConfig(endpoint="nats://example.invalid", user="agent", credential="credential", missing=()),
                [{"subject": "dharma.a2a.fleet", "payload": {}}],
                timeout_s=0.01,
            )
        )

    assert time.monotonic() - started < 0.2


def test_render_fanout_markdown_states_no_external_authority():
    receipt = {
        "generated_at": "2026-06-01T00:00:00Z",
        "repo": "owner/repo",
        "dry_run": False,
        "selected": [{"number": 12, "status": "GITHUB_GREEN_NEEDS_PACKET", "title": "green"}],
        "processed": [
            {
                "number": 12,
                "gate_decision": "BLOCKED",
                "packet_dir": "/tmp/pr-12",
                "comment_path": "/tmp/comment.md",
                "reviewers": [{"agent": "codex", "exit_code": 0, "status": "completed", "verdict": "APPROVE"}],
                "blockers": ["Claude review verdict is MISSING"],
            }
        ],
    }

    text = prc.render_fanout_markdown(receipt)

    assert "does not merge, approve, push, or edit source" in text
    assert "GitHub comment text is rendered locally only" in text


def test_mike_merge_authority_skips_when_gate_blocked():
    called = False

    def runner(*_args, **_kwargs):
        nonlocal called
        called = True
        return prc.CommandResult(0, "", "")

    receipt = prc.run_mike_merge_authority(
        pr_number=12,
        gate={"decision": "BLOCKED", "blockers": ["missing devin receipt"]},
        method="squash",
        auto=True,
        runner=runner,
    )

    assert called is False
    assert receipt["status"] == "SKIPPED"
    assert receipt["blockers"] == ["missing devin receipt"]


def test_mike_merge_authority_runs_gh_when_gate_clean():
    seen = {}

    def runner(command, timeout, check):
        seen["command"] = command
        seen["timeout"] = timeout
        seen["check"] = check
        return prc.CommandResult(0, "merged\n", "")

    receipt = prc.run_mike_merge_authority(
        pr_number=12,
        gate={"decision": "MERGE_CANDIDATE", "packet_dir": "/tmp/packet", "required_reviewers": ["copilot", "claude", "devin"]},
        method="squash",
        auto=True,
        runner=runner,
    )

    assert seen == {
        "command": ["gh", "pr", "merge", "12", "--auto", "--squash", "--delete-branch"],
        "timeout": 300,
        "check": False,
    }
    assert receipt["status"] == "MERGE_COMMAND_ACCEPTED"
    assert receipt["required_reviewers"] == ["copilot", "claude", "devin"]


def test_mike_merge_authority_matches_head_commit_when_present():
    seen = {}

    def runner(command, timeout, check):
        seen["command"] = command
        return prc.CommandResult(0, "armed\n", "")

    prc.run_mike_merge_authority(
        pr_number=12,
        gate={
            "decision": "MERGE_CANDIDATE",
            "packet_dir": "/tmp/packet",
            "required_reviewers": [],
            "head_sha": "abc123",
        },
        method="squash",
        auto=True,
        runner=runner,
    )

    assert seen["command"] == [
        "gh",
        "pr",
        "merge",
        "12",
        "--auto",
        "--squash",
        "--delete-branch",
        "--match-head-commit",
        "abc123",
    ]


def test_render_github_comment_states_conditional_merge_boundary():
    packet = {
        "pr": {"number": 12},
        "classification": {"status": "NEEDS_AGENT_REVIEW", "mergeable": "MERGEABLE"},
        "risk": {"level": "LOW", "files_changed": 1, "additions": 2, "deletions": 0},
        "coherence": {"ok": True},
    }
    gate = {
        "decision": "BLOCKED",
        "blockers": ["missing devin_review.md receipt"],
        "warnings": [],
        "required_reviewers": ["copilot", "claude", "devin"],
    }

    text = prc.render_github_comment(packet, gate)

    assert "- Authority: `conditional_merge_after_clean_gate`" in text
    assert "only when explicitly asked to `merge when clean`" in text
    assert "`copilot_review.md` plus `copilot_review_receipt.json`" in text
    assert "`claude_review.md` plus `claude_review_receipt.json`" in text
    assert "`devin_review.md` plus `devin_review_receipt.json`" in text
    assert "may not approve, merge" not in text


def test_render_github_comment_includes_merge_receipt():
    packet = {
        "pr": {"number": 12},
        "classification": {"status": "GITHUB_GREEN_NEEDS_PACKET", "mergeable": "MERGEABLE"},
        "risk": {"level": "LOW", "files_changed": 1, "additions": 2, "deletions": 0},
        "coherence": {"ok": True},
    }
    gate = {
        "decision": "MERGE_CANDIDATE",
        "blockers": [],
        "warnings": [],
        "required_reviewers": ["copilot", "claude", "devin"],
    }
    merge_receipt = {
        "status": "MERGE_COMMAND_ACCEPTED",
        "reason": "gh pr merge accepted the conditional merge command",
        "method": "squash",
        "auto": True,
        "exit_code": 0,
    }

    text = prc.render_github_comment(packet, gate, merge_receipt)

    assert "### Merge Request" in text
    assert "- Status: `MERGE_COMMAND_ACCEPTED`" in text
    assert "- Auto-merge: `True`" in text


def _write_approve_review(out_dir, agent):
    (out_dir / f"{agent}_review.md").write_text(
        "## Verdict\nAPPROVE\n\n## Findings\n1. clean\n",
        encoding="utf-8",
    )
    prc.write_json(
        out_dir / f"{agent}_review_receipt.json",
        {
            "schema": "dharma.pr_review.agent_receipt.v1",
            "status": "completed",
            "exit_code": 0,
            "timed_out": False,
        },
    )


def test_gate_blocks_missing_required_ci_truth(tmp_path, monkeypatch):
    out_dir = tmp_path / "packet"
    out_dir.mkdir()
    prc.write_json(out_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    _write_approve_review(out_dir, "codex")
    _write_approve_review(out_dir, "claude")
    body = """
- Organ touched: `scripts/runtime/pr_merge_control.py`
- Declared-vs-actual gap closed: merge gate consumes the CI truth contract.
- Proof that re-reads the map: test covers missing protected DocOps check.
- New drift introduced: no merge authority change; gate gets stricter.
"""
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": [
                {"name": "Coherence Delta PR body", "status": "COMPLETED", "conclusion": "SUCCESS"}
            ],
            "body": body,
        },
    )
    monkeypatch.setattr(prc, "fetch_review_threads", lambda _pr, _repo: {"ok": True, "unresolved_count": 0})
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")

    gate = prc.build_gate(
        argparse.Namespace(
            pr=12,
            packet_dir=str(out_dir),
            state_root=str(tmp_path),
            allow_pending=False,
            human_approved=False,
            allow_backup_reviewer=False,
            backup_reviewers="backup_opus",
            backup_reviewer_reason="",
        )
    )

    assert gate["decision"] == "BLOCKED"
    assert gate["ci_truth"]["verdict"] == "FAIL"
    assert "required CI docops_integrity is MISSING; run `make docops-integrity`" in gate["blockers"]


@pytest.mark.parametrize(
    ("github_status", "conclusion", "expected_status"),
    [
        (None, None, "MISSING"),
        ("IN_PROGRESS", "", "PENDING"),
        ("COMPLETED", "FAILURE", "FAIL"),
    ],
)
def test_gate_blocks_nonpassing_onboarding_admission_parity(
    tmp_path,
    monkeypatch,
    github_status,
    conclusion,
    expected_status,
):
    """WP-0F2 consumer proof: the manual Mike path fails closed on the
    onboarding required context straight from the live CI truth contract —
    no candidate-contract shim. Contract v5 requires the context as
    onboarding_session_status; the assertion reads the entry's id and
    local_command from the contract itself so a rename fails loudly here."""
    out_dir = tmp_path / "packet"
    out_dir.mkdir()
    prc.write_json(out_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    _write_approve_review(out_dir, "codex")
    _write_approve_review(out_dir, "claude")

    contract = prc.load_ci_truth_contract()
    onboarding_entries = [
        entry
        for entry in contract["required"]
        if "Onboarding admission parity" in entry.get("names", [])
    ]
    assert len(onboarding_entries) == 1, (
        "CI truth contract must require the onboarding admission context"
    )
    entry_id = onboarding_entries[0]["id"]
    local_command = onboarding_entries[0].get("local_command", "")

    rollup = [
        item
        for item in _ci_required_success_rollup()
        if item["name"] != "Onboarding admission parity"
    ]
    if github_status is not None:
        rollup.append(
            {
                "name": "Onboarding admission parity",
                "status": github_status,
                "conclusion": conclusion,
            }
        )
    body = """
- Organ touched: `tests/test_pr_merge_control.py` (Mike-owned consumer proof).
- Declared-vs-actual gap closed: manual merge authority blocks nonpassing onboarding admission.
- Proof that re-reads the map: the live CI truth contract is evaluated by build_gate.
- New drift introduced: none; the gate only gets stricter.
"""
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": rollup,
            "body": body,
        },
    )
    monkeypatch.setattr(
        prc,
        "fetch_review_threads",
        lambda _pr, _repo: {"ok": True, "unresolved_count": 0},
    )
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")

    gate = prc.build_gate(
        argparse.Namespace(
            pr=12,
            packet_dir=str(out_dir),
            state_root=str(tmp_path),
            allow_pending=False,
            human_approved=False,
            allow_backup_reviewer=False,
            backup_reviewers="backup_opus",
            backup_reviewer_reason="",
        )
    )

    blocker = (
        f"required CI {entry_id} is {expected_status}; run `{local_command}`"
    )
    assert gate["decision"] == "BLOCKED"
    assert gate["ci_truth"]["verdict"] == "FAIL"
    assert blocker in gate["blockers"]


_WORKFLOWS_ROOT = Path(__file__).resolve().parents[1]
_AUTOMERGE_WORKFLOW = _WORKFLOWS_ROOT / ".github" / "workflows" / "automerge.yml"
_PARITY_MANIFEST = _WORKFLOWS_ROOT / "scripts" / "governance" / "ci_parity_manifest.json"

# The plan's exhaustive fail-closed states for a required check
# (docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:1100-1103):
# absent, pending, failed, cancelled, timed out, action required.
_NONSUCCESS_REQUIRED_STATES = [
    (None, None, "MISSING"),
    ("IN_PROGRESS", "", "PENDING"),
    ("COMPLETED", "FAILURE", "FAIL"),
    ("COMPLETED", "CANCELLED", "FAIL"),
    ("COMPLETED", "TIMED_OUT", "FAIL"),
    ("COMPLETED", "ACTION_REQUIRED", "FAIL"),
]


def _contract_success_rollup(contract):
    return [
        {"name": entry["names"][0], "status": "COMPLETED", "conclusion": "SUCCESS"}
        for entry in contract["required"]
    ]


def _build_gate_for_rollup(base_dir, monkeypatch, rollup):
    out_dir = base_dir / "packet"
    out_dir.mkdir(parents=True)
    prc.write_json(out_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    _write_approve_review(out_dir, "codex")
    _write_approve_review(out_dir, "claude")
    body = """
- Organ touched: `tests/test_pr_merge_control.py` (Mike-owned consumer proof).
- Declared-vs-actual gap closed: every entry path consumes one required-check truth.
- Proof that re-reads the map: the live CI truth contract is evaluated by build_gate.
- New drift introduced: none; the gate only gets stricter.
"""
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": rollup,
            "body": body,
        },
    )
    monkeypatch.setattr(
        prc,
        "fetch_review_threads",
        lambda _pr, _repo: {"ok": True, "unresolved_count": 0},
    )
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")
    return prc.build_gate(
        argparse.Namespace(
            pr=12,
            packet_dir=str(out_dir),
            state_root=str(base_dir),
            allow_pending=False,
            human_approved=False,
            allow_backup_reviewer=False,
            backup_reviewers="backup_opus",
            backup_reviewer_reason="",
        )
    )


@pytest.mark.parametrize(
    ("github_status", "conclusion", "expected_status"), _NONSUCCESS_REQUIRED_STATES
)
def test_gate_blocks_every_required_entry_on_every_nonsuccess_state(
    tmp_path,
    monkeypatch,
    github_status,
    conclusion,
    expected_status,
):
    """WP-0F2 consumer proof, set-agnostic: the manual Mike path fails closed
    for EVERY required entry the live CI truth contract declares, on every
    fail-closed state the Titanium plan enumerates (plan :1100-1103). The
    entries are read from the contract at runtime, so ratifying a different
    final set (WP-0F1) is exercised by this exact test without edits."""
    contract = prc.load_ci_truth_contract()
    assert contract["required"], "CI truth contract must declare required entries"
    for index, entry in enumerate(contract["required"]):
        rollup = [
            item
            for item in _contract_success_rollup(contract)
            if item["name"] != entry["names"][0]
        ]
        if github_status is not None:
            rollup.append(
                {
                    "name": entry["names"][0],
                    "status": github_status,
                    "conclusion": conclusion,
                }
            )
        gate = _build_gate_for_rollup(tmp_path / f"case{index}", monkeypatch, rollup)
        blocker = (
            f"required CI {entry['id']} is {expected_status}; "
            f"run `{entry.get('local_command', '')}`"
        )
        assert gate["decision"] == "BLOCKED", entry["id"]
        assert gate["ci_truth"]["verdict"] == "FAIL", entry["id"]
        assert blocker in gate["blockers"], entry["id"]


def test_automerge_and_mike_share_one_required_check_authority():
    """WP-0F2 single-truth proof (plan :1092-1094): automerge derives its
    required set solely from ci_parity_manifest.json, Mike's gate from the CI
    truth contract, and the two are the same canonical set. Parity is already
    fail-closed at contract load (ci_truth.py:114-127); asserting the equality
    here makes divergence fail loudly inside Mike's own suite, and asserting
    no manifest context appears literally in automerge.yml keeps a private
    context list from ever coming back."""
    contract = prc.load_ci_truth_contract()
    manifest = json.loads(_PARITY_MANIFEST.read_text(encoding="utf-8"))
    manifest_contexts = sorted(
        str(entry["context"]) for entry in manifest["required_contexts"]
    )
    canonical = sorted(str(entry["names"][0]) for entry in contract["required"])
    assert manifest_contexts == canonical
    text = _AUTOMERGE_WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/governance/ci_parity_manifest.json" in text
    assert "steps.required_contexts.outputs.required_checks" in text
    for context in manifest_contexts:
        assert context not in text, (
            f"automerge.yml must not hardcode required context {context!r}"
        )


def _automerge_required_check_skips(rollup, required_contexts):
    """Python mirror of automerge.yml's step-3 jq evaluation: normalize each
    rollup item (PENDING when incomplete, else uppercase conclusion or
    NO_CONCLUSION), keep the latest entry per name, then skip when any
    required context is missing or outside the green set
    {SUCCESS, NEUTRAL, SKIPPED}."""
    normalized = {}
    for ordinal, item in enumerate(rollup):
        name = str(
            item.get("name") or item.get("context") or item.get("workflowName") or "unnamed"
        )
        observed = str(item.get("startedAt") or item.get("completedAt") or "")
        if str(item.get("status") or "COMPLETED") != "COMPLETED":
            state = "PENDING"
        else:
            state = str(item.get("conclusion") or item.get("state") or "").upper()
            state = state or "NO_CONCLUSION"
        key = (observed, ordinal)
        current = normalized.get(name)
        if current is None or key > current[0]:
            normalized[name] = (key, state)
    states = {name: state for name, (_, state) in normalized.items()}
    missing = [context for context in required_contexts if context not in states]
    not_green = [
        context
        for context in required_contexts
        if context in states and states[context] not in {"SUCCESS", "NEUTRAL", "SKIPPED"}
    ]
    return bool(missing or not_green)


def test_automerge_skip_matches_mike_fail_on_every_nonsuccess_state():
    """WP-0F2 same-verdict proof (plan :1106): for every required context and
    every fail-closed state, the manifest-driven automerge path skips AND the
    contract-driven CI truth verdict is FAIL — the two entry paths cannot
    disagree in the fail direction."""
    contract = prc.load_ci_truth_contract()
    required_contexts = [str(entry["names"][0]) for entry in contract["required"]]
    for entry in contract["required"]:
        for github_status, conclusion, _expected in _NONSUCCESS_REQUIRED_STATES:
            rollup = [
                item
                for item in _contract_success_rollup(contract)
                if item["name"] != entry["names"][0]
            ]
            if github_status is not None:
                rollup.append(
                    {
                        "name": entry["names"][0],
                        "status": github_status,
                        "conclusion": conclusion,
                    }
                )
            assert _automerge_required_check_skips(rollup, required_contexts), (
                entry["id"],
                conclusion,
            )
            verdict = prc.evaluate_ci_rollup(rollup, contract)["verdict"]
            assert verdict == "FAIL", (entry["id"], conclusion)


def test_workflow_dispatch_event_and_schedule_paths_share_one_gate_job():
    """WP-0F2 entry-path proof (plan :1106): manual workflow_dispatch, PR
    events, check_suite, review events, and the scheduled sweep all enter the
    single `evaluate` job, whose manifest-load and candidate-evaluation steps
    carry no event-conditional `if`, so every path traverses the identical
    required-check evaluation."""
    workflow = yaml.safe_load(_AUTOMERGE_WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on") or workflow.get(True)
    assert {
        "pull_request",
        "check_suite",
        "pull_request_review",
        "schedule",
        "workflow_dispatch",
    } <= set(triggers)
    jobs = workflow["jobs"]
    assert list(jobs) == ["evaluate"]
    steps = {step.get("name"): step for step in jobs["evaluate"]["steps"]}
    required_step = steps["Load manifest-driven required contexts"]
    evaluate_step = steps["Evaluate candidates and dispatch Mike"]
    assert "if" not in required_step
    assert "if" not in evaluate_step
    event_pr = jobs["evaluate"]["env"]["EVENT_PR"]
    assert "github.event.pull_request.number" in event_pr
    assert "github.event.inputs.pr" in event_pr


def test_bot_pr_waiver_cannot_bypass_required_check_evaluation():
    """WP-0F2 waiver-scope proof (plan :1097): `bot-pr` waives reviewer
    receipts only. Lexical confinement over automerge.yml's evaluate script:
    the required-check block (step-3 comment through the step-4 comment)
    gates on missing_required / required_not_green with an unconditional
    skip, and contains no bot-pr, mike-watch, or merge_when_clean branch
    that could exempt a labeled PR from it."""
    workflow = yaml.safe_load(_AUTOMERGE_WORKFLOW.read_text(encoding="utf-8"))
    steps = {step.get("name"): step for step in workflow["jobs"]["evaluate"]["steps"]}
    script = steps["Evaluate candidates and dispatch Mike"]["run"]
    block = script[script.index("# 3.") : script.index("# 4.")]
    assert "missing_required" in block
    assert "required_not_green" in block
    assert "continue" in block
    assert "bot-pr" not in block
    assert "mike-watch" not in block
    assert "merge_when_clean" not in block


def test_gate_reports_advisory_red_and_pending_without_granting_authority(
    tmp_path, monkeypatch
):
    out_dir = tmp_path / "packet"
    out_dir.mkdir()
    prc.write_json(out_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    body = """
- Organ touched: `scripts/runtime/pr_merge_control.py`
- Declared-vs-actual gap closed: Mike consumes the exact protected CI set.
- Proof that re-reads the map: this test keeps advisory failures visible.
- New drift introduced: advisory checks do not silently gain merge authority.
"""
    rollup = _ci_required_success_rollup() + [
        {
            "name": "Quality ratchet - repo-wide fitness function",
            "status": "COMPLETED",
            "conclusion": "FAILURE",
        },
        {
            "name": "Onboarding macOS 3.81 compatibility",
            "status": "IN_PROGRESS",
            "conclusion": "",
        },
    ]
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": rollup,
            "body": body,
        },
    )
    monkeypatch.setattr(
        prc,
        "fetch_review_threads",
        lambda _pr, _repo: {"ok": True, "unresolved_count": 0},
    )
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")

    gate = prc.build_gate(
        argparse.Namespace(
            pr=12,
            packet_dir=str(out_dir),
            state_root=str(tmp_path),
            allow_pending=False,
            human_approved=False,
            allow_backup_reviewer=False,
            backup_reviewers="backup_opus",
            backup_reviewer_reason="",
            required_reviewers="none",
        )
    )

    assert gate["decision"] == "MERGE_CANDIDATE"
    assert gate["blockers"] == []
    assert any("reported failing checks" in warning for warning in gate["warnings"])
    assert any("reported pending checks" in warning for warning in gate["warnings"])


def test_gate_accepts_named_backup_reviewer_when_claude_unavailable(tmp_path, monkeypatch):
    out_dir = tmp_path / "packet"
    out_dir.mkdir()
    prc.write_json(out_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    _write_approve_review(out_dir, "codex")
    _write_approve_review(out_dir, "backup_opus")
    body = """
- Organ touched: `docs/ops/PR_REVIEW_CONTROL.md`
- Declared-vs-actual gap closed: backup reviewer receipts are explicit.
- Proof that re-reads the map: merge gate test covers Claude fallback.
- New drift introduced: no merge authority change; fallback is explicit.
"""
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": _ci_required_success_rollup(),
            "body": body,
        },
    )
    monkeypatch.setattr(prc, "fetch_review_threads", lambda _pr, _repo: {"ok": True, "unresolved_count": 0})
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")

    gate = prc.build_gate(
        argparse.Namespace(
            pr=12,
            packet_dir=str(out_dir),
            state_root=str(tmp_path),
            allow_pending=False,
            human_approved=False,
            allow_backup_reviewer=True,
            backup_reviewers="backup_opus",
            backup_reviewer_reason="Claude Code subscription credits unavailable",
        )
    )

    assert gate["decision"] == "MERGE_CANDIDATE"
    assert "missing claude_review.md receipt" not in gate["blockers"]
    assert gate["backup_review_policy"]["status"] == "accepted"
    assert gate["backup_review_policy"]["accepted_reviewer"] == "backup_opus"


def test_gate_blocks_missing_dynamic_required_reviewer(tmp_path, monkeypatch):
    out_dir = tmp_path / "packet"
    out_dir.mkdir()
    prc.write_json(out_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    _write_approve_review(out_dir, "copilot")
    _write_approve_review(out_dir, "claude")
    body = """
- Organ touched: `docs/ops/PR_REVIEW_CONTROL.md`
- Declared-vs-actual gap closed: dynamic reviewer receipts are explicit.
- Proof that re-reads the map: merge gate test covers missing Devin receipt.
- New drift introduced: no merge authority without the required quorum.
"""
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": _ci_required_success_rollup(),
            "body": body,
        },
    )
    monkeypatch.setattr(prc, "fetch_review_threads", lambda _pr, _repo: {"ok": True, "unresolved_count": 0})
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")

    gate = prc.build_gate(
        argparse.Namespace(
            pr=12,
            packet_dir=str(out_dir),
            state_root=str(tmp_path),
            allow_pending=False,
            human_approved=False,
            allow_backup_reviewer=False,
            backup_reviewers="backup_opus",
            backup_reviewer_reason="",
            required_reviewers="copilot,claude,devin",
        )
    )

    assert gate["decision"] == "BLOCKED"
    assert gate["required_reviewers"] == ["copilot", "claude", "devin"]
    assert "missing devin_review.md receipt" in gate["blockers"]


def test_gate_accepts_dynamic_required_reviewer_quorum(tmp_path, monkeypatch):
    out_dir = tmp_path / "packet"
    out_dir.mkdir()
    prc.write_json(out_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    _write_approve_review(out_dir, "copilot")
    _write_approve_review(out_dir, "claude")
    _write_approve_review(out_dir, "devin")
    body = """
- Organ touched: `docs/ops/PR_REVIEW_CONTROL.md`
- Declared-vs-actual gap closed: Copilot, Claude, and Devin receipts are all present.
- Proof that re-reads the map: merge gate test covers dynamic quorum pass.
- New drift introduced: no gate bypass; reviewer names are data.
"""
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": _ci_required_success_rollup(),
            "body": body,
        },
    )
    monkeypatch.setattr(prc, "fetch_review_threads", lambda _pr, _repo: {"ok": True, "unresolved_count": 0})
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")

    gate = prc.build_gate(
        argparse.Namespace(
            pr=12,
            packet_dir=str(out_dir),
            state_root=str(tmp_path),
            allow_pending=False,
            human_approved=False,
            allow_backup_reviewer=False,
            backup_reviewers="backup_opus",
            backup_reviewer_reason="",
            required_reviewers="copilot,claude,devin",
        )
    )

    assert gate["decision"] == "MERGE_CANDIDATE"
    assert gate["required_reviewers"] == ["copilot", "claude", "devin"]


def test_gate_accepts_explicit_no_reviewer_quorum_for_docs_low_policy(tmp_path, monkeypatch):
    out_dir = tmp_path / "packet"
    out_dir.mkdir()
    prc.write_json(out_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    body = """
- Organ touched: `docs/governance/PR_QUALITY_GATES.md`
- Declared-vs-actual gap closed: docs-low automation can prove no reviewer quorum.
- Proof that re-reads the map: merge gate test covers required_reviewers=none.
- New drift introduced: no broad bypass; this must be explicitly passed.
"""
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": _ci_required_success_rollup(),
            "body": body,
            "headRefOid": "abc123",
        },
    )
    monkeypatch.setattr(prc, "fetch_review_threads", lambda _pr, _repo: {"ok": True, "unresolved_count": 0})
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")

    gate = prc.build_gate(
        argparse.Namespace(
            pr=12,
            packet_dir=str(out_dir),
            state_root=str(tmp_path),
            allow_pending=False,
            human_approved=False,
            allow_backup_reviewer=False,
            backup_reviewers="backup_opus",
            backup_reviewer_reason="",
            required_reviewers="none",
        )
    )

    assert gate["decision"] == "MERGE_CANDIDATE"
    assert gate["required_reviewers"] == []
    assert gate["head_sha"] == "abc123"


def test_gate_blocks_backup_reviewer_without_written_reason(tmp_path, monkeypatch):
    out_dir = tmp_path / "packet"
    out_dir.mkdir()
    prc.write_json(out_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    _write_approve_review(out_dir, "codex")
    _write_approve_review(out_dir, "backup_opus")
    body = """
- Organ touched: `docs/ops/PR_REVIEW_CONTROL.md`
- Declared-vs-actual gap closed: backup reviewer receipts are explicit.
- Proof that re-reads the map: merge gate test covers missing reason.
- New drift introduced: no merge authority change; fallback is explicit.
"""
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": _ci_required_success_rollup(),
            "body": body,
        },
    )
    monkeypatch.setattr(prc, "fetch_review_threads", lambda _pr, _repo: {"ok": True, "unresolved_count": 0})
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")

    gate = prc.build_gate(
        argparse.Namespace(
            pr=12,
            packet_dir=str(out_dir),
            state_root=str(tmp_path),
            allow_pending=False,
            human_approved=False,
            allow_backup_reviewer=True,
            backup_reviewers="backup_opus",
            backup_reviewer_reason="",
        )
    )

    assert gate["decision"] == "BLOCKED"
    assert "backup reviewer requires --backup-reviewer-reason" in gate["blockers"]
    assert gate["backup_review_policy"]["status"] == "missing_reason"


def _advisory_thread(login):
    return {
        "isResolved": False,
        "isOutdated": False,
        "comments": {"nodes": [{"author": {"login": login}, "body": "summary"}]},
    }


_BOT_PR_BODY = """
- Organ touched: `docs/governance/spine_adoption_metric.json`
- Declared-vs-actual gap closed: the automated metric snapshot is refreshed.
- Proof that re-reads the map: the generator re-reads the spine adoption owner.
- New drift introduced: none; this is a trusted automation refresh.
"""


def test_thread_is_advisory_only_classifies_greptile_solo_thread():
    assert prc.thread_is_advisory_only(_advisory_thread("greptile-apps")) is True
    assert prc.thread_is_advisory_only(_advisory_thread("johnvincentshrader")) is False
    # A thread with any non-advisory participant is never advisory-only.
    mixed = {
        "comments": {
            "nodes": [
                {"author": {"login": "greptile-apps"}},
                {"author": {"login": "johnvincentshrader"}},
            ]
        }
    }
    assert prc.thread_is_advisory_only(mixed) is False
    # An empty/authorless thread is conservatively treated as blocking.
    assert prc.thread_is_advisory_only({"comments": {"nodes": []}}) is False


def test_gate_waives_required_reviewers_for_bot_pr(tmp_path, monkeypatch):
    out_dir = tmp_path / "packet"
    out_dir.mkdir()
    prc.write_json(out_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    # No reviewer receipts written on purpose: a bot-pr must merge without them.
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "REVIEW_REQUIRED",
            "statusCheckRollup": _ci_required_success_rollup(),
            "labels": [{"name": "bot-pr"}],
            "body": _BOT_PR_BODY,
        },
    )
    monkeypatch.setattr(prc, "fetch_review_threads", lambda _pr, _repo: {"ok": True, "unresolved": [], "unresolved_count": 0})
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")

    gate = prc.build_gate(
        argparse.Namespace(
            pr=12,
            packet_dir=str(out_dir),
            state_root=str(tmp_path),
            allow_pending=False,
            human_approved=False,
            allow_backup_reviewer=False,
            backup_reviewers="backup_opus",
            backup_reviewer_reason="",
            required_reviewers="codex,claude",
        )
    )

    assert gate["decision"] == "MERGE_CANDIDATE"
    assert gate["required_reviewers"] == []
    assert gate["bot_pr"]["is_bot_pr"] is True
    assert any("waived required reviewer receipts" in w for w in gate["warnings"])
    assert not any("receipt" in b for b in gate["blockers"])


def test_gate_ignores_advisory_bot_threads_for_bot_pr(tmp_path, monkeypatch):
    out_dir = tmp_path / "packet"
    out_dir.mkdir()
    prc.write_json(out_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    threads = {
        "ok": True,
        "unresolved": [_advisory_thread("greptile-apps")],
        "unresolved_count": 1,
    }
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "REVIEW_REQUIRED",
            "statusCheckRollup": _ci_required_success_rollup(),
            "labels": [{"name": "bot-pr"}],
            "body": _BOT_PR_BODY,
        },
    )
    monkeypatch.setattr(prc, "fetch_review_threads", lambda _pr, _repo: threads)
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")

    gate = prc.build_gate(
        argparse.Namespace(
            pr=12,
            packet_dir=str(out_dir),
            state_root=str(tmp_path),
            allow_pending=False,
            human_approved=False,
            allow_backup_reviewer=False,
            backup_reviewers="backup_opus",
            backup_reviewer_reason="",
            required_reviewers="codex,claude",
        )
    )

    assert gate["decision"] == "MERGE_CANDIDATE"
    assert gate["review_threads"]["blocking_unresolved_count"] == 0
    assert not any("unresolved review threads" in b for b in gate["blockers"])
    assert any("advisory review thread" in w for w in gate["warnings"])


def test_gate_still_blocks_non_advisory_threads_for_bot_pr(tmp_path, monkeypatch):
    out_dir = tmp_path / "packet"
    out_dir.mkdir()
    prc.write_json(out_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    threads = {
        "ok": True,
        # Greptile's solo thread is advisory; a human thread is a real request.
        "unresolved": [_advisory_thread("greptile-apps"), _advisory_thread("johnvincentshrader")],
        "unresolved_count": 2,
    }
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "REVIEW_REQUIRED",
            "statusCheckRollup": _ci_required_success_rollup(),
            "labels": [{"name": "bot-pr"}],
            "body": _BOT_PR_BODY,
        },
    )
    monkeypatch.setattr(prc, "fetch_review_threads", lambda _pr, _repo: threads)
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")

    gate = prc.build_gate(
        argparse.Namespace(
            pr=12,
            packet_dir=str(out_dir),
            state_root=str(tmp_path),
            allow_pending=False,
            human_approved=False,
            allow_backup_reviewer=False,
            backup_reviewers="backup_opus",
            backup_reviewer_reason="",
            required_reviewers="codex,claude",
        )
    )

    assert gate["decision"] == "BLOCKED"
    assert gate["review_threads"]["blocking_unresolved_count"] == 1
    assert "1 unresolved review threads" in gate["blockers"]


def test_gate_does_not_waive_threads_for_non_bot_pr(tmp_path, monkeypatch):
    out_dir = tmp_path / "packet"
    out_dir.mkdir()
    prc.write_json(out_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    # Fully reviewed PR; the only blocker is an advisory greptile thread, which
    # must STILL block because the PR is not labelled bot-pr.
    _write_approve_review(out_dir, "codex")
    _write_approve_review(out_dir, "claude")
    threads = {
        "ok": True,
        "unresolved": [_advisory_thread("greptile-apps")],
        "unresolved_count": 1,
    }
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": _ci_required_success_rollup(),
            "labels": [],
            "body": _BOT_PR_BODY,
        },
    )
    monkeypatch.setattr(prc, "fetch_review_threads", lambda _pr, _repo: threads)
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")

    gate = prc.build_gate(
        argparse.Namespace(
            pr=12,
            packet_dir=str(out_dir),
            state_root=str(tmp_path),
            allow_pending=False,
            human_approved=False,
            allow_backup_reviewer=False,
            backup_reviewers="backup_opus",
            backup_reviewer_reason="",
            required_reviewers="codex,claude",
        )
    )

    assert gate["decision"] == "BLOCKED"
    assert gate["bot_pr"]["is_bot_pr"] is False
    assert "1 unresolved review threads" in gate["blockers"]
