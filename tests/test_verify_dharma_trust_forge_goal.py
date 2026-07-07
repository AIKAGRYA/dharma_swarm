from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.verify_dharma_trust_forge_goal import REQUIRED_MARKDOWN, verify_bundle


def _write_valid_bundle(root: Path) -> None:
    source_block = "\n\nSources:\n- https://example.com/a\n- https://example.com/b\n"
    body = "# Artifact\n\n" + ("substantive line with concrete claim and evidence shape.\n" * 40)
    for name in REQUIRED_MARKDOWN:
        text = body + (source_block if name in {
            "mission_baseline.md",
            "agent_01_buyer_wound.md",
            "agent_02_competitive_edge.md",
            "agent_03_mcp_threat_surface.md",
            "agent_09_revenue_packaging_ops.md",
            "DHARMA_TRUST_FORGE_OVERNIGHT_DECISION.md",
        } else "")
        (root / name).write_text(text, encoding="utf-8")
    receipt = {
        "schema_version": "dharma.trust_forge_overnight_autoresearch.v1",
        "mission_id": "dharma-trust-forge-overnight-test",
        "started_at_utc": "2026-07-06T00:00:00Z",
        "completed_at_utc": "2026-07-06T08:00:00Z",
        "repo": "/Users/dhyana/dharma_swarm",
        "lanes_completed": 10,
        "required_outputs_present": True,
        "recommended_next_action": "build_mvp_scorecard",
        "sellable_pilot_present": True,
        "external_actions_performed": False,
        "public_claims_authorized": False,
        "runtime_mutation_performed": False,
        "verification_commands": ["make onboard"],
        "sources": [
            "https://docs.langchain.com/langsmith/observability",
            "https://langfuse.com/docs",
            "https://www.braintrust.dev/docs",
            "https://docs.agentops.ai/",
            "https://modelcontextprotocol.io/specification/2025-06-18",
            "https://0din.ai/scope",
        ],
        "blockers": [],
        "next_launch_command": "/goal follow docs/agent_tasks/...",
    }
    (root / "closeout_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")


def test_verify_bundle_accepts_complete_bundle(tmp_path: Path) -> None:
    _write_valid_bundle(tmp_path)
    ok, errors = verify_bundle(tmp_path, min_markdown_bytes=200)
    assert ok
    assert errors == []


def test_verify_bundle_rejects_missing_report_dir(tmp_path: Path) -> None:
    ok, errors = verify_bundle(tmp_path / "missing")
    assert not ok
    assert errors == [f"report_dir_missing:{tmp_path / 'missing'}"]


def test_verify_bundle_rejects_missing_receipt(tmp_path: Path) -> None:
    for name in REQUIRED_MARKDOWN:
        (tmp_path / name).write_text("# short\n", encoding="utf-8")
    ok, errors = verify_bundle(tmp_path)
    assert not ok
    assert "missing_receipt:closeout_receipt.json" in errors
