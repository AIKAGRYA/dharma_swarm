from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _quality_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "revenue" / "cashclaw_lease_packet_quality_audit.py"
    spec = importlib.util.spec_from_file_location("cashclaw_lease_packet_quality_audit", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_packet(
    root: Path,
    *,
    title: str = "[BOUNTY $100] Good task",
    source_url: str = "https://github.com/buyer/repo/issues/1",
    price: float = 100.0,
    state: str = "open",
    acceptance_clues: list[str] | None = None,
) -> dict:
    artifact = root / "cycle_001" / "gauntlet" / "packet"
    artifact.mkdir(parents=True)
    delivery_plan = artifact / "delivery_plan.md"
    delivery_plan.write_text("# delivery\n", encoding="utf-8")
    source_scope_snapshot = artifact / "source_scope_snapshot.md"
    source_scope_snapshot.write_text("# source\n", encoding="utf-8")
    (artifact / "source_scope_snapshot.json").write_text(
        json.dumps(
            {
                "title": title,
                "source_url": source_url,
                "source_item_found": True,
                "state": state,
                "acceptance_clues": acceptance_clues
                if acceptance_clues is not None
                else ["Acceptance Criteria: includes tests"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    lease_preflight = artifact / "lease_preflight.json"
    lease_preflight.write_text(
        json.dumps(
            {
                "lease_preflight_passed": True,
                "no_external_side_effects": True,
                "reasons": [],
                "checks": {
                    "source_hard_risk_flags": [],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "lease_id": "lease-1",
        "title": title,
        "source_url": source_url,
        "proposed_price_usd": price,
        "risk_flags": [],
        "delivery_plan": str(delivery_plan),
        "source_scope_snapshot": str(source_scope_snapshot),
        "lease_preflight": str(lease_preflight),
    }


def test_quality_audit_passes_clean_source_backed_packet(tmp_path):
    quality = _quality_module()
    request = _write_packet(tmp_path)
    (tmp_path / "operator_revenue_lease_requests.json").write_text(
        json.dumps(
            {
                "status": "draft_only_not_granted",
                "external_side_effects_performed": False,
                "requests": [request],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "summaries.json").write_text(
        json.dumps([{"cycle": 1, "timestamp": "2026-05-31T00:00:00+00:00"}]) + "\n",
        encoding="utf-8",
    )

    audit = quality.build_quality_audit(tmp_path)
    quality.write_quality_audit(tmp_path, audit)

    assert audit["passed"] is True
    assert audit["packet_results"][0]["passed"] is True
    assert (tmp_path / "lease_packet_quality_audit.json").exists()
    assert "Packet Audit" in (tmp_path / "lease_packet_quality_audit.md").read_text(encoding="utf-8")


def test_quality_audit_holds_generic_or_closed_packet(tmp_path):
    quality = _quality_module()
    request = _write_packet(
        tmp_path,
        title="Fetched text source",
        source_url="https://github.com/buyer/repo/issues/1",
        state="closed",
        acceptance_clues=[],
    )
    (tmp_path / "operator_revenue_lease_requests.json").write_text(
        json.dumps(
            {
                "status": "draft_only_not_granted",
                "external_side_effects_performed": False,
                "requests": [request],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "summaries.json").write_text("[]\n", encoding="utf-8")

    audit = quality.build_quality_audit(tmp_path)
    result = audit["packet_results"][0]

    assert audit["passed"] is False
    assert result["passed"] is False
    assert "source_title_not_specific_paid_task" in result["reasons"]
    assert "github_source_not_open:closed" in result["reasons"]
    assert "source_lacks_acceptance_clues" in result["reasons"]
