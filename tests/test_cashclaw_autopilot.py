from __future__ import annotations

import json

from dharma_swarm.revenue.cashclaw_autopilot import CashClawAutopilot
from dharma_swarm.revenue.cashclaw_employees import verify_employee_receipt_bundle
from dharma_swarm.revenue.idea_gauntlet import DECISION_HOLD, DECISION_KILL, DECISION_PASS
from dharma_swarm.revenue.spine import RevenueSpine, RevenueTarget, TargetStatus


def _autopilot(tmp_path, *, spine=None) -> CashClawAutopilot:
    return CashClawAutopilot(
        spine=spine,
        state_dir=tmp_path / "state",
        report_dir=tmp_path / "reports",
        gauntlet_root=tmp_path / "gauntlet",
    )


def test_synthetic_cycle_writes_top10_and_receipts(tmp_path):
    result = _autopilot(tmp_path).run_cycle(
        {
            "include_synthetic": True,
            "include_local": False,
            "include_spine": False,
            "include_hyrve": False,
            "top_n": 10,
            "require_env": False,
        }
    )

    assert result.clean_cycle is True
    assert result.side_effects_performed is False
    assert len(result.top10) == 10
    assert result.top10[0].status == "UNSENT_UNSUBMITTED"
    assert result.top10[0].no_external_side_effects is True
    assert result.latest_queue_path.endswith("latest_top10.md")
    assert (tmp_path / "state" / "latest_top10.md").exists()
    assert (tmp_path / "state" / "latest_top10.json").exists()
    assert (tmp_path / "state" / "cycle_log.jsonl").exists()
    assert (tmp_path / "reports" / "approval_queue.md").exists()
    assert result.employee_receipts_written == 60
    assert result.gateway_allow_count >= 50
    assert result.gateway_review_count + result.gateway_block_count == 10
    assert "External side effects: none" in (tmp_path / "reports" / "approval_queue.md").read_text(
        encoding="utf-8"
    )
    assert "Employee receipts: 60 across 10 packets" in (tmp_path / "reports" / "approval_queue.md").read_text(
        encoding="utf-8"
    )


def test_local_inbox_opportunity_becomes_action_packet(tmp_path):
    inbox = tmp_path / "state" / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "paid_task.json").write_text(
        json.dumps(
            {
                "id": "local-paid-agent-install",
                "source": "local_inbox",
                "buyer_name": "Busy consultant",
                "org": "Operator Desk",
                "title": "Install daily client-briefing AI employee",
                "description": "Need a daily briefing agent from local docs with source receipts.",
                "pain_signals": ["daily reporting bottleneck", "client context scattered"],
                "budget_usd": 1200,
                "payment_clarity": "fixed-fee setup",
                "distribution_access": "inbound request saved locally",
                "service_fit": "AI employee installation",
                "deliverable": "Cron-based briefing agent, dummy test run, SOP, and approval gates.",
                "due_hours": 48,
                "evidence": ["local inbox request"],
                "agent_doable_steps": ["write skill", "configure cron", "run dummy cycle", "write SOP"],
                "tags": ["agent_install", "fast_cash"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = _autopilot(tmp_path).run_cycle(
        {
            "include_synthetic": False,
            "include_local": True,
            "include_spine": False,
            "include_hyrve": False,
            "top_n": 10,
        }
    )

    assert result.opportunities_scanned == 1
    assert len(result.top10) == 1
    packet = result.top10[0]
    assert packet.buyer_name == "Busy consultant"
    assert packet.source == "local_inbox"
    assert packet.score >= 80
    assert packet.approval_packet_ready is True
    assert packet.gauntlet_decision == DECISION_PASS
    assert packet.status == "UNSENT_UNSUBMITTED"
    assert packet.no_external_side_effects is True
    assert packet.gateway_decision == "review"
    assert "operator_approval" in packet.gateway_required_receipts
    assert packet.employee_receipt_count == 6
    assert packet.employee_receipt_id.startswith("caemp_")
    assert packet.execution_receipt_id.startswith("caexec_")
    assert packet.employee_receipt_bundle_id.startswith("caempbundle_")
    assert packet.employee_roles_completed == [
        "opportunity_scanner",
        "buyer_scout",
        "budget_skeptic",
        "deliverable_builder",
        "risk_welfare_gate",
        "approval_clerk",
    ]
    assert "Human reviews packet" in packet.first_action
    assert "requires human approval before sending" in packet.draft_message
    assert (tmp_path / "gauntlet" / packet.action_id / "gateway_decision.json").exists()
    employee_receipt = tmp_path / "gauntlet" / packet.action_id / "employee_receipt.json"
    assert employee_receipt.exists()
    receipt_payload = json.loads(employee_receipt.read_text(encoding="utf-8"))
    assert receipt_payload["side_effects_performed"] is False
    assert len(receipt_payload["employee_receipts"]) == 6
    assert receipt_payload["final_gateway_decision"] == "review"
    assert receipt_payload["final_employee_receipt_id"] == packet.employee_receipt_id
    assert receipt_payload["final_execution_receipt_id"] == packet.execution_receipt_id
    assert verify_employee_receipt_bundle(employee_receipt, allowed_root=tmp_path / "gauntlet") == []


def test_high_risk_opportunity_is_blocked(tmp_path):
    inbox = tmp_path / "state" / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "risky.json").write_text(
        json.dumps(
            {
                "id": "risky-trading",
                "source": "local_inbox",
                "buyer_name": "Anon trader",
                "title": "Guaranteed trading bot with auto-send cold email",
                "description": "Guarantee returns, use API key credentials, and send without approval.",
                "pain_signals": ["wants guaranteed returns"],
                "budget_usd": 5000,
                "payment_clarity": "wallet transfer after launch",
                "distribution_access": "requires credentials",
                "service_fit": "Trading research support",
                "deliverable": "Live trading bot",
                "risk_signals": ["trading", "guaranteed returns", "API key", "send without approval"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = _autopilot(tmp_path).run_cycle(
        {
            "include_synthetic": False,
            "include_local": True,
            "include_spine": False,
            "include_hyrve": False,
        }
    )

    packet = result.top10[0]
    assert packet.approval_packet_ready is False
    assert packet.verdict in {DECISION_KILL, DECISION_HOLD}
    assert "regulated_advice" in packet.risk_flags
    assert "guaranteed_revenue" in packet.risk_flags
    assert "secret_or_pii" in packet.risk_flags
    assert "autonomous_send_requested" in packet.risk_flags
    assert packet.gateway_decision == "block"
    assert "gauntlet_not_pass_to_human" in packet.gateway_decision_reasons
    assert "passing_gauntlet_evaluation" in packet.gateway_required_receipts


def test_clean_opportunities_are_preselected_before_noisy_risk(tmp_path):
    inbox = tmp_path / "state" / "inbox"
    inbox.mkdir(parents=True)
    records = [
        {
            "id": f"risky-{idx}",
            "source": "github_bounty_live_intake",
            "source_url": f"https://github.com/noisy/repo/issues/{idx}",
            "buyer_name": "Noisy repo",
            "title": f"High value token/security task {idx}",
            "description": "Requires wallet transfer and security bug bounty work.",
            "pain_signals": ["bounty"],
            "estimated_value_usd": 5000,
            "payment_clarity": "wallet transfer after work",
            "distribution_access": "public issue",
            "service_fit": "security task",
            "deliverable": "security bounty",
            "risk_signals": ["payment_or_wallet_action", "security_or_bug_bounty"],
            "agent_doable_steps": ["blocked"],
        }
        for idx in range(5)
    ]
    records.append(
        {
            "id": "clean-docs-bounty",
            "source": "github_bounty_live_intake",
            "source_url": "https://github.com/clean/repo/issues/1",
            "buyer_name": "clean/repo",
            "title": "Documentation quickstart bounty",
            "description": "Paid bounty for verified quickstart docs.",
            "pain_signals": ["docs gaps", "onboarding friction"],
            "estimated_value_usd": 150,
            "payment_clarity": "bounty paid after merged documentation PR",
            "distribution_access": "public issue/PR path; no submit without approval",
            "service_fit": "Code/internal-tool delivery",
            "deliverable": "Tested quickstart doc and reproduction notes.",
            "agent_doable_steps": ["install project", "verify quickstart", "write docs patch"],
            "tags": ["named_demand"],
        }
    )
    (inbox / "mixed.json").write_text(json.dumps(records) + "\n", encoding="utf-8")

    result = _autopilot(tmp_path).run_cycle(
        {
            "include_synthetic": False,
            "include_local": True,
            "include_spine": False,
            "include_hyrve": False,
            "top_n": 1,
            "max_opportunities": 3,
        }
    )

    assert result.top10[0].title == "Documentation quickstart bounty"
    assert result.top10[0].risk_flags == []
    assert result.top10[0].approval_packet_ready is True


def test_gauntlet_artifacts_are_written(tmp_path):
    result = _autopilot(tmp_path).run_cycle(
        {
            "include_synthetic": True,
            "include_local": False,
            "include_spine": False,
            "include_hyrve": False,
            "top_n": 3,
        }
    )

    artifact_dir = tmp_path / "gauntlet" / result.top10[0].action_id
    assert (artifact_dir / "human_packet.md").exists()
    assert (artifact_dir / "delivery_plan.md").exists()
    assert (artifact_dir / "operator_revenue_lease_request.md").exists()
    assert (artifact_dir / "gate_evidence.json").exists()
    assert (artifact_dir / "evaluation.json").exists()
    lease_request = (artifact_dir / "operator_revenue_lease_request.md").read_text(encoding="utf-8")
    gate_evidence = json.loads((artifact_dir / "gate_evidence.json").read_text(encoding="utf-8"))
    evaluation = json.loads((artifact_dir / "evaluation.json").read_text(encoding="utf-8"))
    assert "draft_only_not_granted" in lease_request
    assert "APPROVE REVENUE LEASE" in lease_request
    assert "operator_revenue_lease_request.md" in gate_evidence["gates"]["channel"]["evidence_refs"]
    assert evaluation["candidate_id"] == result.top10[0].action_id


def test_revenue_spine_targets_are_read_without_approving_outreach(tmp_path):
    spine = RevenueSpine(storage_dir=tmp_path / "spine")
    spine.add_target(
        RevenueTarget(
            name="agent-framework/repo",
            org="agent-framework",
            domain="github",
            pain_signals=["needs_governance_audit", "no_provenance"],
            repo_urls=["https://github.com/agent-framework/repo"],
            estimated_value_usd=2000,
            status=TargetStatus.QUALIFIED,
            qualification_score=0.9,
        )
    )

    result = _autopilot(tmp_path, spine=spine).run_cycle(
        {
            "include_synthetic": False,
            "include_local": False,
            "include_spine": True,
            "include_hyrve": False,
        }
    )

    assert len(result.top10) == 1
    assert result.top10[0].source == "revenue_spine"
    assert spine.pending_outreach() == []


def test_run_cycle_does_not_fetch_hyrve_when_disabled(tmp_path, monkeypatch):
    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("HYRVE fetch should not run when include_hyrve is false")

    monkeypatch.setattr("dharma_swarm.revenue.cashclaw_autopilot.urlopen", fail_urlopen)

    result = _autopilot(tmp_path).run_cycle(
        {
            "include_synthetic": True,
            "include_local": False,
            "include_spine": False,
            "include_hyrve": False,
            "hyrve_url": "https://example.invalid/tasks",
            "top_n": 1,
        }
    )

    assert result.clean_cycle is True
    assert result.side_effects_performed is False
    assert result.errors == []


def test_hyrve_rejects_unapproved_fetch_without_urlopen(tmp_path, monkeypatch):
    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("HYRVE fetch should be gated before urlopen")

    monkeypatch.delenv("DHARMA_CASHCLAW_ALLOW_HYRVE", raising=False)
    monkeypatch.setattr("dharma_swarm.revenue.cashclaw_autopilot.urlopen", fail_urlopen)

    result = _autopilot(tmp_path).run_cycle(
        {
            "include_synthetic": False,
            "include_local": False,
            "include_spine": False,
            "include_hyrve": True,
            "hyrve_url": "https://cashclawai.com/api/tasks",
        }
    )

    assert result.clean_cycle is False
    assert result.external_network_reads_performed is False
    assert any("HYRVE fetch requires DHARMA_CASHCLAW_ALLOW_HYRVE=1" in error for error in result.errors)


def test_hyrve_rejects_file_localhost_and_private_urls_without_urlopen(tmp_path, monkeypatch):
    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("HYRVE fetch should reject unsafe URL before urlopen")

    monkeypatch.setenv("DHARMA_CASHCLAW_ALLOW_HYRVE", "1")
    monkeypatch.setattr("dharma_swarm.revenue.cashclaw_autopilot.urlopen", fail_urlopen)

    for url in ("file:///tmp/tasks.json", "https://localhost/tasks", "https://127.0.0.1/tasks"):
        result = _autopilot(tmp_path).run_cycle(
            {
                "include_synthetic": False,
                "include_local": False,
                "include_spine": False,
                "include_hyrve": True,
                "hyrve_url": url,
            }
        )
        assert result.clean_cycle is False
        assert result.external_network_reads_performed is False
        assert result.errors


def test_cost_cap_blocks_before_gauntlet_artifacts_are_written(tmp_path):
    result = _autopilot(tmp_path).run_cycle(
        {
            "include_synthetic": True,
            "include_local": False,
            "include_spine": False,
            "include_hyrve": False,
            "top_n": 10,
            "cost_cap_usd": 0.01,
        }
    )

    assert result.clean_cycle is False
    assert result.top10 == []
    assert result.employee_receipts_written == 0
    assert "no artifacts written" in result.errors[0]
    assert list((tmp_path / "gauntlet").glob("*")) == []


def test_cycle_log_contains_final_paths(tmp_path):
    result = _autopilot(tmp_path).run_cycle(
        {
            "include_synthetic": True,
            "include_local": False,
            "include_spine": False,
            "include_hyrve": False,
            "top_n": 1,
        }
    )

    row = json.loads((tmp_path / "state" / "cycle_log.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert row["latest_queue_path"] == result.latest_queue_path
    assert row["report_path"] == result.report_path
    assert row["cycle_log_path"] == result.cycle_log_path
