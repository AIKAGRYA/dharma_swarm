#!/usr/bin/env python3
"""Verify the Dharma Trust Forge overnight autoresearch bundle.

This is intentionally a content-shape verifier, not a judge of truth. It makes
the overnight loop prove that the required artifacts exist, are non-trivial,
carry source URLs where source-bearing claims are expected, and end in a typed
closeout receipt.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_REPORT_DIR = Path("reports/agentops/work_packets/dharma-trust-forge-overnight-autoresearch")

URL_RE = re.compile(r"https?://[^\s)>\]]+")

REQUIRED_MARKDOWN = [
    "mission_baseline.md",
    "agent_01_buyer_wound.md",
    "agent_02_competitive_edge.md",
    "agent_03_mcp_threat_surface.md",
    "agent_04_eval_fixture_factory.md",
    "agent_05_scorecard_typed_claims.md",
    "agent_06_remediation_playbook.md",
    "agent_07_mvp_architecture.md",
    "agent_08_karpathy_wiki_memory.md",
    "agent_09_revenue_packaging_ops.md",
    "agent_10_adversarial_go_no_go.md",
    "cross_critique_matrix.md",
    "DHARMA_TRUST_FORGE_OVERNIGHT_DECISION.md",
    "mvp_scorecard_spec.md",
    "eval_fixture_catalog.md",
    "remediation_playbook.md",
    "pricing_packaging_offer.md",
    "adoption_and_memory_plan.md",
    "validation_and_metrics_plan.md",
]

SOURCE_REQUIRED = {
    "mission_baseline.md",
    "agent_01_buyer_wound.md",
    "agent_02_competitive_edge.md",
    "agent_03_mcp_threat_surface.md",
    "agent_09_revenue_packaging_ops.md",
    "DHARMA_TRUST_FORGE_OVERNIGHT_DECISION.md",
}

REQUIRED_RECEIPT_FIELDS = {
    "schema_version",
    "mission_id",
    "started_at_utc",
    "completed_at_utc",
    "repo",
    "lanes_completed",
    "required_outputs_present",
    "recommended_next_action",
    "sellable_pilot_present",
    "external_actions_performed",
    "public_claims_authorized",
    "runtime_mutation_performed",
    "verification_commands",
    "sources",
    "blockers",
    "next_launch_command",
}


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _url_count(text: str) -> int:
    return len(set(URL_RE.findall(text)))


def verify_bundle(report_dir: Path, *, min_markdown_bytes: int = 800) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not report_dir.exists():
        return False, [f"report_dir_missing:{report_dir}"]
    if not report_dir.is_dir():
        return False, [f"report_dir_not_directory:{report_dir}"]

    for name in REQUIRED_MARKDOWN:
        path = report_dir / name
        if not path.exists():
            errors.append(f"missing_markdown:{name}")
            continue
        text = _load_text(path)
        if len(text.encode("utf-8")) < min_markdown_bytes:
            errors.append(f"markdown_too_small:{name}:{len(text.encode('utf-8'))}")
        if name in SOURCE_REQUIRED and _url_count(text) < 2:
            errors.append(f"source_urls_too_few:{name}:{_url_count(text)}")

    receipt_path = report_dir / "closeout_receipt.json"
    if not receipt_path.exists():
        errors.append("missing_receipt:closeout_receipt.json")
        return False, errors
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"receipt_json_invalid:{exc}")
        return False, errors

    missing_fields = sorted(REQUIRED_RECEIPT_FIELDS - set(receipt))
    if missing_fields:
        errors.append(f"receipt_missing_fields:{','.join(missing_fields)}")

    if receipt.get("schema_version") != "dharma.trust_forge_overnight_autoresearch.v1":
        errors.append("receipt_schema_version_invalid")
    if int(receipt.get("lanes_completed") or 0) != 10:
        errors.append(f"receipt_lanes_completed_invalid:{receipt.get('lanes_completed')}")
    if receipt.get("required_outputs_present") is not True:
        errors.append("receipt_required_outputs_present_not_true")
    if receipt.get("sellable_pilot_present") is not True:
        errors.append("receipt_sellable_pilot_present_not_true")
    if receipt.get("external_actions_performed") is not False:
        errors.append("receipt_external_actions_performed_must_be_false")
    if receipt.get("public_claims_authorized") is not False:
        errors.append("receipt_public_claims_authorized_must_be_false")
    if receipt.get("runtime_mutation_performed") is not False:
        errors.append("receipt_runtime_mutation_performed_must_be_false")
    if not isinstance(receipt.get("verification_commands"), list) or not receipt["verification_commands"]:
        errors.append("receipt_verification_commands_empty")
    if not isinstance(receipt.get("sources"), list) or len(receipt["sources"]) < 6:
        errors.append("receipt_sources_too_few")
    if not str(receipt.get("next_launch_command") or "").strip():
        errors.append("receipt_next_launch_command_empty")

    return not errors, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--min-markdown-bytes", type=int, default=800)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ok, errors = verify_bundle(args.report_dir, min_markdown_bytes=args.min_markdown_bytes)
    payload: dict[str, Any] = {
        "status": "pass" if ok else "fail",
        "report_dir": str(args.report_dir),
        "required_markdown_count": len(REQUIRED_MARKDOWN),
        "errors": errors,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"DHARMA_TRUST_FORGE_GOAL_{payload['status'].upper()}")
        for error in errors:
            print(f"- {error}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
