from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OFFBOARD_SCRIPT = REPO_ROOT / "scripts/governance/agent_offboard.py"


def test_offboard_writes_ops_receipts_and_emits_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DHARMA_OPS_DIR", str(tmp_path / "ops"))

    result = subprocess.run(
        [
            sys.executable,
            str(OFFBOARD_SCRIPT),
            "--json",
            "--task",
            "context packet closeout",
            "--packet-id",
            "ctx.command-plane-governance",
            "--owner",
            "docs/context_engineering/PACKET_SCHEMA.md",
            "--verification",
            "pytest tests/test_context_packet_router.py: passed",
            "--artifact",
            "docs/context_engineering/CONTEXT_PACKET_INDEX.json",
            "--claim-not-made",
            "repo-wide worktree is clean",
            "--risk",
            "unrelated dirty worktree remains",
            "--next-step",
            "commit scoped files",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "agent-offboard-v0.0.0.1"
    assert payload["version"] == "0.0.0.1"
    assert payload["packet_id"] == "ctx.command-plane-governance"
    assert "AGENT_OFFBOARD_RECEIPT" in payload["audit_search_tags"]
    assert payload["dirty_summary"]["counts"]["total"] >= 0

    ops_json = tmp_path / "ops" / "offboard_receipt.json"
    ops_md = tmp_path / "ops" / "offboard_receipt.md"
    assert ops_json.exists()
    assert ops_md.exists()
    assert "AGENT_OFFBOARD_RECEIPT" in ops_md.read_text(encoding="utf-8")


def test_offboard_repo_receipt_can_write_to_explicit_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DHARMA_OPS_DIR", str(tmp_path / "ops"))
    repo_receipts = tmp_path / "repo_receipts"

    result = subprocess.run(
        [
            sys.executable,
            str(OFFBOARD_SCRIPT),
            "--task",
            "repo receipt smoke",
            "--repo-receipt",
            "--receipt-dir",
            str(repo_receipts),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "Written receipts:" in result.stdout
    assert list(repo_receipts.glob("*.json"))
    markdown_receipts = list(repo_receipts.glob("*.md"))
    assert markdown_receipts
    assert "OFFBOARD_V0_0_0_1" in markdown_receipts[0].read_text(encoding="utf-8")
