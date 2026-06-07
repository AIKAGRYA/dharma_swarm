from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest

from dharma_swarm.revenue.cashclaw_autopilot import CashClawAutopilot, CashOpportunity
from dharma_swarm.revenue.live_intake import CashClawLiveIntake, pattern_card_to_opportunity
from dharma_swarm.revenue.live_intake_models import LiveIntakeSourceConfig, LiveIntakeSourceItem, LiveIntakeSourceType, live_intake_content_hash
from dharma_swarm.revenue.live_intake_sources import go_archive_config, read_source


class _FakeUrlopenResponse:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int) -> bytes:
        return BytesIO(self._raw).read()


def test_local_fixture_intake_writes_receipts_and_patterns(tmp_path):
    fixture = tmp_path / "agentic_builders.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "AI employee setup for daily client briefing",
                    "author": "builder",
                    "url": "https://example.com/ai-employee",
                    "summary": "Founder paid $1000 setup fee for an AI employee cron agent that drafts daily client briefings.",
                },
                {
                    "title": "Creator sponsor triage agent",
                    "url": "https://example.com/sponsor-agent",
                    "summary": "Creator uses an OpenClaw-style assistant to triage brand deals and draft sponsor replies.",
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output = tmp_path / "run"
    result = CashClawLiveIntake().run(fixture_paths=[fixture], output_root=output, top_n=5)

    assert result.network_reads_performed is False
    assert result.source_item_count == 2
    assert result.pattern_card_count >= 2
    assert result.adapter_receipts[0].source_items_emitted == 2
    assert result.adapter_receipts[0].external_side_effects_performed is False
    assert "local_fixture_sources_are_not_live_buyer_proof" in result.warnings
    assert (output / "summary.json").exists()
    assert (output / "top_patterns.md").exists()
    assert "AI employee installation" in (output / "top_patterns.md").read_text(encoding="utf-8")


def test_live_intake_parses_k_suffix_prices(tmp_path):
    fixture = tmp_path / "bounty.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "title": "[Bounty $3k] Research automation task",
                "author": "repo-owner",
                "url": "https://example.com/issues/1",
                "summary": "Paid bounty $3k for a source-backed research workflow using agents.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = CashClawLiveIntake().run(fixture_paths=[fixture], output_root=tmp_path / "run", top_n=1)
    opportunity = pattern_card_to_opportunity(result.pattern_cards[0])

    assert "mentions price $3k" in result.pattern_cards[0].pricing_evidence
    assert opportunity["estimated_value_usd"] == 3000.0


def test_named_github_demand_uses_source_acceptance_not_generic_pattern(tmp_path):
    summary = (
        "When the API returns an empty response body, the app crashes. "
        "This is not a pricing or positioning research task.\n\n"
        "Acceptance Criteria:\n"
        "- API calls handle null/undefined responses gracefully\n"
        "- User sees a friendly error toast instead of a crash\n"
        "- Add at least one unit test for the error handling path\n"
        "Labels: bounty:$50"
    )
    item = LiveIntakeSourceItem(
        source_item_id="liitem_api_error",
        source_config_id="github-bounty-agent-friendly",
        source_type=LiveIntakeSourceType.GITHUB,
        url="https://github.com/labmain/ai-agent-pay-demo/issues/35",
        content_hash=live_intake_content_hash({"summary": summary}),
        title="Add error handling for empty API responses",
        author_or_org="labmain/ai-agent-pay-demo",
        summary=summary,
        raw_excerpt=summary,
    )

    cards = CashClawLiveIntake().extract_patterns([item])
    opportunity = pattern_card_to_opportunity(cards[0])

    assert "API calls handle null/undefined responses gracefully" in opportunity["deliverable"]
    assert "friendly error toast" in opportunity["deliverable"]
    assert "unit test" in opportunity["deliverable"]
    assert "competitor pricing and positioning intelligence" not in opportunity["deliverable"]


def test_security_labeled_hook_bounty_is_risk_flagged(tmp_path):
    fixture = tmp_path / "security_hook_bounty.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "title": "[BOUNTY $100] HOOK: Pre-tool-use hook that blocks destructive bash commands",
                "author": "claude-builders-bounty/claude-builders-bounty",
                "url": "https://github.com/example/agent-bounties/issues/3",
                "summary": (
                    "Create a Claude Code pre-tool-use hook that intercepts dangerous bash commands. "
                    "Blocks rm -rf, DROP TABLE, TRUNCATE, and DELETE FROM without a WHERE clause. "
                    "Labels: bounty, hook, security"
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = CashClawLiveIntake().run(fixture_paths=[fixture], output_root=tmp_path / "run", top_n=3)

    assert result.pattern_cards
    assert all("security_or_bug_bounty" in card.risks for card in result.pattern_cards)
    assert all("security_or_bug_bounty" in pattern_card_to_opportunity(card)["risk_signals"] for card in result.pattern_cards)


def test_signup_gated_bounty_is_risk_flagged(tmp_path):
    fixture = tmp_path / "signup_gated_bounty.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "title": "[PAID BOUNTY - $960] Attachment Summarizer Service",
                "author": "warpspeedopen-source/warpspeed-bounties",
                "url": "https://github.com/example/bounties/issues/1",
                "summary": (
                    "Full technical requirements, submission rules, and acceptance criteria are available on the official bounty page. "
                    "View Full Bounty Details & Sign Up. Sign up as a developer, then return to this issue and comment that you have signed up. "
                    "A maintainer must confirm before work begins. Do not start work until a maintainer confirms your claim."
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = CashClawLiveIntake().run(fixture_paths=[fixture], output_root=tmp_path / "run", top_n=3)

    assert result.pattern_cards
    assert all("requires_signup_or_credentials" in card.risks for card in result.pattern_cards)
    assert all("requires_signup_or_credentials" in pattern_card_to_opportunity(card)["risk_signals"] for card in result.pattern_cards)


def test_generic_marketplace_homepage_is_not_named_demand(tmp_path):
    item = LiveIntakeSourceItem(
        source_item_id="liitem-market-homepage",
        source_config_id="marketplace-homepage",
        source_type=LiveIntakeSourceType.MARKETPLACE,
        url="https://www.example-market.invalid/",
        content_hash=live_intake_content_hash("marketplace homepage"),
        title="Fetched text source",
        summary="AI agent job marketplace. Post bounties. Pay only $5 for approved work.",
        evidence_ref="https://www.example-market.invalid/",
    )

    cards = CashClawLiveIntake().extract_patterns([item])
    opportunity = pattern_card_to_opportunity(cards[0])

    assert opportunity["source"] == "live_intake_market_pattern"
    assert "requires_named_buyer_proof" in opportunity["tags"]
    assert opportunity["buyer_name"] == ""


def test_default_network_source_is_blocked_without_urlopen(monkeypatch):
    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("network should be gated before urlopen")

    monkeypatch.delenv("DHARMA_CASHCLAW_ALLOW_LIVE_INTAKE", raising=False)
    monkeypatch.setattr("dharma_swarm.revenue.live_intake_sources.urlopen", fail_urlopen)
    config = LiveIntakeSourceConfig(
        source_config_id="src-hn",
        source_type=LiveIntakeSourceType.HACKER_NEWS,
        url="https://hn.algolia.com/api/v1/search?query=ai%20agent",
        adapter_name="hn_json",
        host_allowlist=["hn.algolia.com"],
        network_enabled=True,
    )

    result = read_source(config, allow_network=False)

    assert result.blocked is True
    assert result.network_read_performed is False
    assert "network_read_requires_allow_network" in result.errors[0]


def test_private_or_local_network_urls_rejected_by_model():
    with pytest.raises(ValueError, match="local or private"):
        LiveIntakeSourceConfig(
            source_config_id="src-local",
            source_type=LiveIntakeSourceType.OTHER,
            url="https://127.0.0.1:8000/feed.json",
            adapter_name="bad",
            host_allowlist=["127.0.0.1"],
            network_enabled=True,
        )


def test_network_read_requires_host_allowlist():
    with pytest.raises(ValueError, match="host allowlist"):
        LiveIntakeSourceConfig(
            source_config_id="src-no-allow",
            source_type=LiveIntakeSourceType.BLOG,
            url="https://example.com/feed.json",
            adapter_name="blog_json",
            network_enabled=True,
        )


def test_reddit_and_youtube_network_sources_are_terms_sensitive():
    with pytest.raises(ValueError, match="explicit low terms_risk"):
        LiveIntakeSourceConfig(
            source_config_id="src-youtube",
            source_type=LiveIntakeSourceType.YOUTUBE,
            url="https://www.googleapis.com/youtube/v3/search",
            adapter_name="youtube_api",
            host_allowlist=["www.googleapis.com"],
            network_enabled=True,
        )


def test_local_fixture_byte_cap_returns_blocked_receipt(tmp_path):
    fixture = tmp_path / "too_large.md"
    fixture.write_text("x" * 32, encoding="utf-8")
    config = LiveIntakeSourceConfig(
        source_config_id="src-small-cap",
        source_type=LiveIntakeSourceType.LOCAL_FIXTURE,
        url="artifact://cashclaw-live-intake/too_large",
        adapter_name="local_fixture",
        local_path=str(fixture),
        max_bytes=8,
    )

    result = read_source(config)

    assert result.blocked is True
    assert result.receipt is not None
    assert result.receipt.source_items_emitted == 0
    assert "exceeded max byte cap" in result.errors[0]


def test_github_bounty_api_records_become_named_source_items(monkeypatch):
    payload = {
        "items": [
            {
                "html_url": "https://github.com/example/agent-bounties/issues/7",
                "url": "https://api.github.com/repos/example/agent-bounties/issues/7",
                "repository_url": "https://api.github.com/repos/example/agent-bounties",
                "title": "[BOUNTY $200] n8n + Claude workflow",
                "body": "Create an exportable n8n workflow that summarizes weekly repo activity. Payment on merged PR.",
                "labels": [{"name": "bounty"}, {"name": "$200"}, {"name": "workflow"}],
                "user": {"login": "bounty-owner"},
                "created_at": "2026-05-30T00:00:00Z",
            }
        ]
    }

    monkeypatch.setenv("DHARMA_CASHCLAW_ALLOW_LIVE_INTAKE", "1")
    monkeypatch.setattr("dharma_swarm.revenue.live_intake_sources.urlopen", lambda *_args, **_kwargs: _FakeUrlopenResponse(payload))
    config = LiveIntakeSourceConfig(
        source_config_id="github-bounty-search",
        source_type=LiveIntakeSourceType.GITHUB,
        url="https://api.github.com/search/issues?q=label:bounty+state:open&per_page=1",
        adapter_name="github_search_api",
        extraction_method="api_json",
        license_risk="low",
        terms_risk="low",
        host_allowlist=["api.github.com"],
        network_enabled=True,
    )

    result = read_source(config, allow_network=True)

    assert result.blocked is False
    assert result.network_read_performed is True
    assert result.source_items[0].url == "https://github.com/example/agent-bounties/issues/7"
    assert result.source_items[0].author_or_org == "example/agent-bounties"
    assert "Labels: bounty, $200, workflow" in result.source_items[0].summary


def test_go_archive_index_becomes_cashclaw_evidence_without_network(tmp_path):
    clean = tmp_path / "clean.txt"
    clean.write_text(
        "[BOUNTY $50] Fix empty API response\n"
        "Acceptance Criteria:\n"
        "- add null handling\n"
        "- add one regression test\n",
        encoding="utf-8",
    )
    body = tmp_path / "body.html"
    body.write_text("<html><body>raw body</body></html>", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": "go_site_archive_receipt.v1",
                "receipt_id": "goarch_test",
                "run_id": "archive-run-1",
                "source_spec_id": "github-bounty-source",
                "capture_status": "captured",
            }
        ),
        encoding="utf-8",
    )
    entry = {
        "run_id": "archive-run-1",
        "source_spec_id": "github-bounty-source",
        "url": "https://github.com/labmain/ai-agent-pay-demo/issues/35?utm_source=x",
        "canonical_url": "https://github.com/labmain/ai-agent-pay-demo/issues/35",
        "final_canonical_url": "https://github.com/labmain/ai-agent-pay-demo/issues/35",
        "title": "[BOUNTY $50] Fix empty API response",
        "source_kind": "html",
        "content_type": "text/html",
        "content_hash": live_intake_content_hash(body.read_text(encoding="utf-8")),
        "capture_status": "captured",
        "body_path": str(body),
        "receipt_path": str(receipt),
        "clean_text_path": str(clean),
        "clean_text_hash": live_intake_content_hash(clean.read_text(encoding="utf-8")),
        "robots_decision": "allowed",
    }
    index = tmp_path / "archive_index.jsonl"
    index.write_text(
        json.dumps(entry) + "\n" + json.dumps({"capture_status": "deduped", "dedupe_of": entry["canonical_url"]}) + "\n",
        encoding="utf-8",
    )

    result = read_source(go_archive_config(index), max_items=10)

    assert result.network_read_performed is False
    assert result.blocked is False
    assert result.receipt is not None
    assert result.receipt.source_items_emitted == 1
    assert result.receipt.warnings == ["go_archive_rows_skipped:1"]
    item = result.source_items[0]
    assert item.source_type == LiveIntakeSourceType.GITHUB
    assert item.evidence_ref == str(receipt)
    assert item.metadata["go_archive"]["source_trust"] is None
    assert item.metadata["go_archive"]["receipt_path"] == str(receipt)
    assert item.metadata["go_archive"]["body_path"] == str(body)

    cards = CashClawLiveIntake().extract_patterns(result.source_items)
    opportunity = pattern_card_to_opportunity(cards[0])

    assert cards[0].evidence_refs == [str(receipt)]
    assert opportunity["source"] == "github_bounty_live_intake"
    assert opportunity["buyer_name"] == "labmain/ai-agent-pay-demo"
    assert "null handling" in opportunity["deliverable"]


def test_autopilot_live_fixture_patterns_do_not_become_approval_ready(tmp_path):
    fixture = tmp_path / "pattern.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "title": "OpenClaw AI employee installation offer",
                "url": "https://example.com/openclaw-offer",
                "summary": "Several builders sell AI employee installs, setup fee $1000, but this is market pattern evidence only.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    autopilot = CashClawAutopilot(
        state_dir=tmp_path / "state",
        report_dir=tmp_path / "reports",
        gauntlet_root=tmp_path / "gauntlet",
    )

    result = autopilot.run_cycle(
        {
            "include_synthetic": False,
            "include_local": False,
            "include_spine": False,
            "include_hyrve": False,
            "include_live_intake": True,
            "live_fixture": str(fixture),
            "live_output_root": str(tmp_path / "live"),
            "top_n": 5,
        }
    )

    assert result.external_network_reads_performed is False
    assert result.opportunities_scanned >= 1
    assert result.top10
    assert all(packet.approval_packet_ready is False for packet in result.top10)
    assert all(packet.source == "live_intake_local_fixture" for packet in result.top10)
    assert all(packet.status == "UNSENT_UNSUBMITTED" for packet in result.top10)


def test_autopilot_live_github_bounty_can_create_human_packet(monkeypatch, tmp_path):
    payload = {
        "items": [
            {
                "html_url": "https://github.com/claude-builders-bounty/claude-builders-bounty/issues/5",
                "url": "https://api.github.com/repos/claude-builders-bounty/claude-builders-bounty/issues/5",
                "repository_url": "https://api.github.com/repos/claude-builders-bounty/claude-builders-bounty",
                "title": "[BOUNTY $200] WORKFLOW: n8n + Claude Code weekly dev summary",
                "body": "Create a complete n8n workflow that automatically generates a weekly narrative summary of a GitHub repo's activity. Payment is released automatically on merge.",
                "labels": [{"name": "bounty"}, {"name": "workflow"}, {"name": "$200"}],
                "user": {"login": "claudebounty"},
                "created_at": "2026-03-27T00:55:44Z",
            }
        ]
    }
    source_config = tmp_path / "github_sources.json"
    source_config.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_config_id": "github-agent-bounty-search",
                        "source_type": "github",
                        "url": "https://api.github.com/search/issues?q=label:bounty+state:open&per_page=1",
                        "label": "GitHub bounty search",
                        "adapter_name": "github_search_api",
                        "extraction_method": "api_json",
                        "license_risk": "low",
                        "terms_risk": "low",
                        "host_allowlist": ["api.github.com"],
                        "max_bytes": 1000000,
                        "enabled": True,
                        "network_enabled": True,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DHARMA_CASHCLAW_ALLOW_LIVE_INTAKE", "1")
    monkeypatch.setattr("dharma_swarm.revenue.live_intake_sources.urlopen", lambda *_args, **_kwargs: _FakeUrlopenResponse(payload))
    autopilot = CashClawAutopilot(
        state_dir=tmp_path / "state",
        report_dir=tmp_path / "reports",
        gauntlet_root=tmp_path / "gauntlet",
    )

    result = autopilot.run_cycle(
        {
            "include_synthetic": False,
            "include_local": False,
            "include_spine": False,
            "include_hyrve": False,
            "include_live_intake": True,
            "live_source_config": str(source_config),
            "live_output_root": str(tmp_path / "live"),
            "allow_live_network": True,
            "top_n": 1,
        }
    )

    assert result.external_network_reads_performed is True
    assert result.top10[0].source == "github_bounty_live_intake"
    assert result.top10[0].buyer_name == "claude-builders-bounty/claude-builders-bounty"
    assert result.top10[0].approval_packet_ready is True
    assert result.top10[0].status == "UNSENT_UNSUBMITTED"
    artifact_dir = Path(result.top10[0].artifact_dir)
    delivery_plan = artifact_dir / "delivery_plan.md"
    gate_evidence = json.loads((artifact_dir / "gate_evidence.json").read_text(encoding="utf-8"))

    assert delivery_plan.exists()
    delivery_text = delivery_plan.read_text(encoding="utf-8")
    assert "No external side effects performed" in delivery_text
    assert "Do not comment, claim, bid, submit a PR" in delivery_text
    assert "https://github.com/claude-builders-bounty/claude-builders-bounty/issues/5" in delivery_text
    assert "delivery_plan.md" in gate_evidence["gates"]["delivery_proof"]["evidence_refs"]


def test_autopilot_blocks_human_only_and_payment_rail_bounties(tmp_path):
    autopilot = CashClawAutopilot(
        state_dir=tmp_path / "state",
        report_dir=tmp_path / "reports",
        gauntlet_root=tmp_path / "gauntlet",
    )
    human_only = CashOpportunity(
        source="github_bounty_live_intake",
        source_url="https://github.com/example/repo/issues/1",
        buyer_name="example/repo",
        title="Inherited Tag Values are not Overwritten [100% human contributions]",
        description="This bounty requires 100% human contributions and no AI.",
        pain_signals=["human-only bounty"],
        estimated_value_usd=20,
        payment_clarity="mentions price $20",
        distribution_access="named public demand source",
        service_fit="code fix",
        deliverable="draft only",
        agent_doable_steps=["repo triage"],
    )
    payment_rail = CashOpportunity(
        source="github_bounty_live_intake",
        source_url="https://github.com/example/repo/issues/2",
        buyer_name="example/repo",
        title="USDT crypto payment gateway with webhook",
        description="Implement strict crypto payment gateway and PayPal sandbox payment flow.",
        pain_signals=["payment rail implementation"],
        estimated_value_usd=750,
        payment_clarity="mentions price $750",
        distribution_access="named public demand source",
        service_fit="payment gateway code",
        deliverable="draft only",
        agent_doable_steps=["repo triage"],
    )
    auth_sensitive = CashOpportunity(
        source="github_bounty_live_intake",
        source_url="https://github.com/example/repo/issues/3",
        buyer_name="example/repo",
        title="Note Locking - Biometrics/PIN",
        description="Implement biometrics and PIN authentication.",
        pain_signals=["sensitive authentication feature"],
        estimated_value_usd=660,
        payment_clarity="mentions price $660",
        distribution_access="named public demand source",
        service_fit="auth feature",
        deliverable="draft only",
        agent_doable_steps=["repo triage"],
    )
    bug_bounty = CashOpportunity(
        source="github_bounty_live_intake",
        source_url="https://github.com/example/bug-bounty/issues/4",
        buyer_name="example/bug-bounty",
        title="Low hanging fruit bug bounty automation",
        description="Automate bug bounty vulnerability finding.",
        pain_signals=["bug bounty automation"],
        estimated_value_usd=700,
        payment_clarity="mentions price $700",
        distribution_access="named public demand source",
        service_fit="bug bounty automation",
        deliverable="draft only",
        agent_doable_steps=["repo triage"],
    )
    upstream_flagged = CashOpportunity(
        source="github_bounty_live_intake",
        source_url="https://github.com/example/repo/issues/5",
        buyer_name="example/repo",
        title="Normal looking code task",
        description="No obvious risky phrase here.",
        pain_signals=["normal task"],
        estimated_value_usd=100,
        payment_clarity="mentions price $100",
        distribution_access="named public demand source",
        service_fit="code fix",
        deliverable="draft only",
        risk_signals=["security_or_bug_bounty"],
        agent_doable_steps=["repo triage"],
    )
    bug_hunter = CashOpportunity(
        source="github_bounty_live_intake",
        source_url="https://github.com/example/rustchain-bounties/issues/520",
        buyer_name="example/rustchain-bounties",
        title="[Achievement] Bug Hunter - Find a Real Bug - 3 RTC",
        description="Find a real bug and receive RTC reward points.",
        pain_signals=["bug hunter achievement"],
        estimated_value_usd=0.3,
        payment_clarity="mentions reward 3 RTC",
        distribution_access="named public demand source",
        service_fit="bug hunter bounty",
        deliverable="draft only",
        agent_doable_steps=["repo triage"],
    )
    token_reward = CashOpportunity(
        source="github_bounty_live_intake",
        source_url="https://github.com/example/rustchain-bounties/issues/515",
        buyer_name="example/rustchain-bounties",
        title="[Bounty] Add RustChain to Your GitHub Profile README - 2 RTC",
        description="Reward is 2 RTC achievement points, not cash.",
        pain_signals=["token reward"],
        estimated_value_usd=0.2,
        payment_clarity="mentions reward 2 RTC",
        distribution_access="named public demand source",
        service_fit="profile readme update",
        deliverable="draft only",
        agent_doable_steps=["repo triage"],
    )

    assert "ai_disallowed_or_human_only" in autopilot._risk_flags(human_only)
    assert "payment_or_wallet_action" in autopilot._risk_flags(payment_rail)
    assert "auth_or_sensitive_security" in autopilot._risk_flags(auth_sensitive)
    assert "security_or_bug_bounty" in autopilot._risk_flags(bug_bounty)
    assert "security_or_bug_bounty" in autopilot._risk_flags(upstream_flagged)
    assert "security_or_bug_bounty" in autopilot._risk_flags(bug_hunter)
    assert "non_cash_or_token_reward" in autopilot._risk_flags(bug_hunter)
    assert "non_cash_or_token_reward" in autopilot._risk_flags(token_reward)
