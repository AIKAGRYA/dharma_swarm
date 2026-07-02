"""Receipt writers for Forge production-contract reports."""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.forge_prod_contracts.scoreboard import ScoreboardReport
from dharma_swarm.forge_prod_contracts.taskbed import stable_payload_hash


RECEIPT_SCHEMA_VERSION = "forge_prod_contracts.receipt.v1"


def write_scoreboard_report(
    report: ScoreboardReport,
    output_dir: str | Path,
) -> tuple[Path, Path, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    report_payload = report.to_dict()
    json_path = destination / "scoreboard_report.json"
    markdown_path = destination / "scoreboard_report.md"
    receipt_path = destination / "scoreboard_receipt.json"
    json_path.write_text(
        json.dumps(report_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(format_markdown_report(report), encoding="utf-8")
    receipt_payload = build_receipt_payload(report, json_path)
    receipt_path.write_text(
        json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return json_path, markdown_path, receipt_path


def build_receipt_payload(
    report: ScoreboardReport, report_path: Path
) -> dict[str, object]:
    report_payload = report.to_dict()
    report_hash = stable_payload_hash(report_payload)
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "run_id": report.run_id,
        "artifact_path": str(report_path),
        "artifact_sha256": report_hash,
        "task_manifest_sha256": report_payload["task_manifest_sha256"],
        "execution_graded": True,
        "equal_budget": report.summary["equal_budget"],
        "contamination_state": report.summary["contamination_state"],
        "promotion_allowed": report.promotion_decision["promotion_allowed"],
        "blocked_gates": report.promotion_decision["blocked_gates"],
        "authority_attestation": {
            "offline": True,
            "network_calls": 0,
            "provider_keys_read": False,
            "router_mutated": False,
            "darwin_apply_called": False,
            "archive_fitness_mutated": False,
            "public_benchmark_submission": False,
        },
    }
    receipt["receipt_sha256"] = stable_payload_hash(receipt)
    return receipt


def format_markdown_report(report: ScoreboardReport) -> str:
    summary = report.summary
    lines = [
        "# Forge Production Contracts: Offline Scoreboard + Private Taskbed",
        "",
        f"- Run id: `{report.run_id}`",
        f"- Created: `{report.created_at}`",
        f"- Task count: `{summary['task_count']}`",
        f"- Equal budget: `{summary['equal_budget']}`",
        f"- Contamination state: `{summary['contamination_state']}`",
        f"- Promotion allowed: `{report.promotion_decision['promotion_allowed']}`",
        "",
        "## Arm Scores",
        "",
        "| Arm | Passes | Tasks | Average | Tokens | Failures |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    arms = summary["arms"]
    assert isinstance(arms, dict)
    for arm, row in arms.items():
        assert isinstance(row, dict)
        failures = ", ".join(str(item) for item in row["failure_classes"]) or "none"
        lines.append(
            "| {arm} | {passes} | {tasks} | {avg} | {tokens} | {failures} |".format(
                arm=arm,
                passes=row["pass_count"],
                tasks=row["task_count"],
                avg=row["average_score"],
                tokens=row["tokens_spent"],
                failures=failures,
            )
        )
    lines.extend(
        [
            "",
            "## Promotion Refusal",
            "",
            f"- Decision: `{report.promotion_decision['decision']}`",
            f"- Safe learning action: `{report.promotion_decision['safe_learning_action']}`",
            "- Blocked gates:",
        ]
    )
    for gate in report.promotion_decision["blocked_gates"]:
        lines.append(f"  - `{gate}`")
    return "\n".join(lines) + "\n"
