#!/usr/bin/env python3
"""Read-only wall-clock evolution loop for Dharma Capital.

The loop is intentionally evidence-first. It refreshes the local AGNI evidence
packet, imports it as Dharma Capital projections, scores current hedge-fund
capability against a fixed rubric, runs the focused bridge verifier, and writes
iteration receipts. It never grants live authority or writes to AGNI.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.capital_lab.agni_bridge import (  # noqa: E402
    AUTHORITY_BOUNDARY,
    canonical_json,
    export_agni_packet,
    import_packet_jsonl_to_dharma_capital,
    sha256_json,
    validate_packet_signature,
)


DEFAULT_CAPITAL_ROOT = Path("/Users/dhyana/dharma_capital")
DEFAULT_SNAPSHOT_ROOT = Path("/Users/dhyana/agni_ginko_trading_history_20260625")
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "reports" / "capital_lab" / "dharma_capital_evolution"
VERIFY_COMMAND = [
    sys.executable,
    "-m",
    "pytest",
    "-q",
    "tests/test_capital_lab_agni_bridge.py",
]


@dataclass(frozen=True)
class ScoreDimension:
    dimension_id: str
    label: str
    weight: int
    points: int
    evidence: tuple[str, ...]
    blockers: tuple[str, ...]
    next_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension_id": self.dimension_id,
            "label": self.label,
            "weight": self.weight,
            "points": self.points,
            "evidence": list(self.evidence),
            "blockers": list(self.blockers),
            "next_actions": list(self.next_actions),
        }


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{time.monotonic_ns()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{time.monotonic_ns()}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(payload) + "\n")


def canonical_paths(capital_root: Path) -> dict[str, Path]:
    return {
        "current_truth": capital_root / "CURRENT_TRUTH.md",
        "relationship_map": capital_root / "RELATIONSHIP_MAP.md",
        "foundry_schema": capital_root / "alpha" / "foundry_schema.py",
        "agni_audit": capital_root / "alpha_foundry" / "agni_state_audit_2026-06-17.md",
        "seed_candidates": capital_root / "alpha_foundry" / "seed_candidates.json",
        "conversion": capital_root / "alpha_foundry" / "dharma_alpha_foundry_conversion.json",
        "holon": capital_root / "holon" / "dharma_capital_holon.py",
        "source_manifest": capital_root / "SOURCE_MANIFEST.json",
    }


def path_evidence(paths: dict[str, Path]) -> dict[str, bool]:
    return {name: path.exists() for name, path in paths.items()}


def _score_if(condition: bool, points: int) -> int:
    return points if condition else 0


def score_dharma_capital(
    *,
    capital_root: Path,
    packet: dict[str, Any],
    import_result: dict[str, Any],
    verifier_passed: bool,
) -> dict[str, Any]:
    paths = canonical_paths(capital_root)
    files = path_evidence(paths)
    signature_valid = validate_packet_signature(packet)
    authority_clean = packet.get("authority") == AUTHORITY_BOUNDARY
    route_count = int(packet.get("evidence_summary", {}).get("routes_observed") or 0)
    comparison = import_result.get("comparison") or {}
    stale = packet.get("stale_or_broken") or {}
    broken_counts = stale.get("broken_counts_7d") if isinstance(stale, dict) else {}
    has_broken_counts = any(int(value or 0) > 0 for value in (broken_counts or {}).values())

    dimensions = [
        ScoreDimension(
            "topology_truth",
            "Topology, canon, and authority map",
            10,
            _score_if(files["current_truth"] and files["relationship_map"], 7),
            (
                str(paths["current_truth"]),
                str(paths["relationship_map"]),
                "SHAKTI_GINKO -> Dharma Capital -> Foundry/Trading Lab/AGNI/capital_lab map is explicit.",
            ),
            (
                "Dharma Capital is a distinct advisor/research/fund entity, but it is not yet a verified live operating fund or admitted L4 agent.",
            ),
            (
                "Keep one canonical machine-readable topology packet.",
                "Attach rating movement to receipts instead of narrative claims.",
            ),
        ),
        ScoreDimension(
            "capital_lab_membrane",
            "Evidence, typed contracts, and risk membrane",
            15,
            _score_if(verifier_passed and authority_clean, 8),
            (
                "dharma_swarm/capital_lab/contracts.py",
                "dharma_swarm/capital_lab/agni_bridge.py",
                f"focused_verifier_passed={verifier_passed}",
            ),
            (
                "Membrane emits Universe/Insight projections, not portfolio/risk/execution readiness.",
            ),
            (
                "Add candidate-level statistical validation receipts.",
                "Keep broker-paper and live-order authority separated by tests.",
            ),
        ),
        ScoreDimension(
            "agni_bridge_data_plane",
            "AGNI bridge and data plane",
            10,
            _score_if(signature_valid and authority_clean and route_count > 0, 5),
            (
                f"packet_id={packet.get('packet_id', '')}",
                f"routes_observed={route_count}",
                f"signature_valid={signature_valid}",
            ),
            (
                "Only one lab packet is present; sister-lab orthogonality is not proven.",
                "Snapshot is local and dated; it is not a live data plane.",
            ),
            (
                "Add at least one non-clone sister-lab packet.",
                "Refresh snapshots through an approved read-only export path.",
            ),
        ),
        ScoreDimension(
            "alpha_foundry_candidate_discipline",
            "Alpha Foundry candidate discipline",
            15,
            _score_if(files["foundry_schema"] and files["seed_candidates"] and files["conversion"], 4),
            (
                str(paths["foundry_schema"]),
                str(paths["seed_candidates"]),
                str(paths["conversion"]),
            ),
            (
                "Foundry is scaffold/local spec only; routes are not yet bound to first-class candidate journals.",
            ),
            (
                "Convert route families into alpha candidates with source packets.",
                "Write append-only decision journals before any promotion language.",
            ),
        ),
        ScoreDimension(
            "research_validation_grade",
            "Research validation and statistical grade",
            15,
            _score_if(route_count > 0, 3),
            (
                f"comparison_status={comparison.get('status', '')}",
                f"stale_or_broken_clean={stale.get('is_clean') if isinstance(stale, dict) else ''}",
            ),
            (
                "No fresh DSR/PBO/PSR-style candidate gate is proven.",
                "Broken or stale AGNI alpha-cycle counts remain." if has_broken_counts else "Validation remains below research-grade institutional proof.",
            ),
            (
                "Run cost-adjusted replay, perturbation, and true-trial-count checks per candidate.",
                "Demote generic TA route farming into a negative-control lane.",
            ),
        ),
        ScoreDimension(
            "portfolio_construction",
            "Portfolio construction and risk budget",
            10,
            1,
            (
                "Typed PortfolioTarget/RiskAdjustedTarget contracts exist.",
                "No allocation optimizer or candidate risk budget is proven in this run.",
            ),
            (
                "No portfolio optimizer, exposure budget, stress budget, or capacity model is wired to evidence.",
            ),
            (
                "Build paper-only portfolio target simulator from candidate Insights.",
                "Require risk governor clamps before any target can become execution intent.",
            ),
        ),
        ScoreDimension(
            "execution_reconciliation_ops",
            "Execution, reconciliation, and operations",
            10,
            0,
            (
                "live_order_authority=false",
                "broker_write_authority=false",
                "capital_approval=false",
            ),
            (
                "No live execution authority, no broker write path, no reconciliation-grade operating loop.",
            ),
            (
                "Keep live execution at zero until legal, tax, custody, Sarathi, and human gates pass.",
                "Improve paper reconciliation only.",
            ),
        ),
        ScoreDimension(
            "l4_agent_autonomy",
            "Agentic L4 autonomy",
            10,
            _score_if(files["holon"], 1),
            (
                str(paths["holon"]),
                "holon is reconstructed/paper-safe and not verified as original live L4.",
            ),
            (
                "No admitted persistent Dharma Capital CEO-CIO agent with durable wake loop.",
            ),
            (
                "Admit a read-only scout holon first.",
                "Require harness, registration, liveness, and receipts before autonomy claims.",
            ),
        ),
        ScoreDimension(
            "legal_compliance_revenue",
            "Legal, compliance, and revenue reality",
            5,
            _score_if(files["source_manifest"], 2),
            (
                str(paths["source_manifest"]),
                "Sarathi gates irreversible moves.",
                "Known revenue is $0; known paper P&L claim is +$65.74 over 88 days from one route.",
            ),
            (
                "No legal/compliance program, external capital path, or actual fund revenue is proven.",
            ),
            (
                "Keep Kalshi/legal venue work behind a written memo and Sarathi approval.",
                "Do not market or externalize fund claims from this score.",
            ),
        ),
    ]
    total = sum(item.points for item in dimensions)
    return {
        "schema_version": "dharma.capital.rating.v1",
        "generated_at": utc_now(),
        "rating_out_of_100": total,
        "rating_label": "research_grade_agentic_hedge_fund_target",
        "live_fund_rating_out_of_100": 8,
        "capital_authorized_rating_out_of_100": 0,
        "plain_english": (
            "Dharma Capital is a serious institutional advisor/research/fund-brain "
            "prototype, not yet a fully capable operating research-grade agentic "
            "hedge fund and not a live fund."
        ),
        "dimension_scores": [item.to_dict() for item in dimensions],
        "files_seen": {name: str(path) for name, path in paths.items()},
        "file_presence": files,
        "authority": dict(AUTHORITY_BOUNDARY),
    }


def run_verifier(timeout_seconds: int) -> dict[str, Any]:
    started = utc_now()
    try:
        completed = subprocess.run(
            VERIFY_COMMAND,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "command": VERIFY_COMMAND,
            "started_at": started,
            "completed_at": utc_now(),
            "returncode": completed.returncode,
            "passed": completed.returncode == 0,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": VERIFY_COMMAND,
            "started_at": started,
            "completed_at": utc_now(),
            "returncode": None,
            "passed": False,
            "timeout_seconds": timeout_seconds,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
        }


def build_iteration(
    *,
    run_dir: Path,
    iteration: int,
    snapshot_root: Path,
    capital_root: Path,
    verifier_timeout_seconds: int,
    skip_verifier: bool,
) -> dict[str, Any]:
    iteration_dir = run_dir / "iterations" / f"{iteration:04d}"
    packet_jsonl = iteration_dir / "agni_packets.jsonl"
    packet = export_agni_packet(snapshot_root, packet_jsonl, generated_at=utc_now())
    import_result_obj = import_packet_jsonl_to_dharma_capital(packet_jsonl)
    import_result = import_result_obj.to_dict()
    atomic_write_json(iteration_dir / "capital_import_receipt.json", import_result)

    verifier = (
        {
            "command": VERIFY_COMMAND,
            "passed": None,
            "skipped": True,
            "reason": "skip_verifier requested",
        }
        if skip_verifier
        else run_verifier(verifier_timeout_seconds)
    )
    verifier_passed = verifier.get("passed") is True or skip_verifier
    rating = score_dharma_capital(
        capital_root=capital_root,
        packet=packet,
        import_result=import_result,
        verifier_passed=verifier_passed,
    )
    receipt = {
        "schema_version": "dharma.capital.evolution.iteration.v1",
        "iteration": iteration,
        "generated_at": utc_now(),
        "run_dir": str(run_dir),
        "snapshot_root": str(snapshot_root),
        "capital_root": str(capital_root),
        "packet": {
            "packet_id": packet["packet_id"],
            "jsonl": str(packet_jsonl),
            "signature": packet["signature"],
            "signature_valid": validate_packet_signature(packet),
            "routes_observed": packet["evidence_summary"]["routes_observed"],
            "latest_activity_ts": packet["evidence_summary"].get("latest_activity_ts", ""),
            "authority": packet["authority"],
        },
        "comparison": import_result.get("comparison", {}),
        "proposal_count": len(import_result.get("proposals", [])),
        "verifier": verifier,
        "rating": rating,
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = sha256_json({key: value for key, value in receipt.items() if key != "receipt_hash"})
    atomic_write_json(iteration_dir / "iteration_receipt.json", receipt)
    atomic_write_json(run_dir / "latest.json", receipt)
    append_jsonl(run_dir / "receipts.jsonl", receipt)
    atomic_write_text(run_dir / "STATUS.md", status_markdown(receipt))
    return receipt


def status_markdown(receipt: dict[str, Any]) -> str:
    rating = receipt.get("rating", {})
    packet = receipt.get("packet", {})
    comparison = receipt.get("comparison", {})
    verifier = receipt.get("verifier", {})
    lines = [
        "# Dharma Capital Evolution Run",
        "",
        f"Updated: {receipt.get('generated_at', '')}",
        f"Iteration: {receipt.get('iteration', '')}",
        f"Rating: {rating.get('rating_out_of_100', '')}/100",
        f"Live fund rating: {rating.get('live_fund_rating_out_of_100', '')}/100",
        f"Capital-authorized rating: {rating.get('capital_authorized_rating_out_of_100', '')}/100",
        f"Packet: {packet.get('packet_id', '')}",
        f"Routes observed: {packet.get('routes_observed', '')}",
        f"Comparison: {comparison.get('status', '')}",
        f"Verifier passed: {verifier.get('passed')}",
        "",
        "## Boundary",
        "",
        "- read_only=true",
        "- live_order_authority=false",
        "- broker_write_authority=false",
        "- capital_approval=false",
        "- route_mutation_authority=false",
        "- order_generation_authority=false",
        "",
        "## Highest-Leverage Next Moves",
        "",
        "1. Make route families report up to first-class Dharma Capital Alpha Foundry candidates.",
        "2. Add one orthogonal sister-lab packet so AGNI is not judged alone.",
        "3. Add true-trial-count, DSR/PBO/PSR, cost, perturbation, and concentration gates.",
        "4. Build a paper-only portfolio target simulator that cannot emit orders.",
        "5. Admit a read-only Dharma Capital scout holon with liveness receipts.",
        "",
    ]
    return "\n".join(lines)


def summarize_run(run_dir: Path, receipts: Sequence[dict[str, Any]], status: str) -> dict[str, Any]:
    latest = receipts[-1] if receipts else {}
    rating = latest.get("rating", {}) if latest else {}
    summary = {
        "schema_version": "dharma.capital.evolution.summary.v1",
        "status": status,
        "completed_at": utc_now(),
        "run_dir": str(run_dir),
        "iteration_count": len(receipts),
        "latest_rating_out_of_100": rating.get("rating_out_of_100"),
        "latest_live_fund_rating_out_of_100": rating.get("live_fund_rating_out_of_100"),
        "latest_capital_authorized_rating_out_of_100": rating.get("capital_authorized_rating_out_of_100"),
        "latest_receipt_hash": latest.get("receipt_hash", ""),
        "authority": dict(AUTHORITY_BOUNDARY),
    }
    atomic_write_json(run_dir / "summary.json", summary)
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mission-id", default="")
    parser.add_argument("--duration-seconds", type=float, default=7200.0)
    parser.add_argument("--interval-seconds", type=float, default=600.0)
    parser.add_argument("--max-iterations", type=int, default=0)
    parser.add_argument("--snapshot-root", type=Path, default=DEFAULT_SNAPSHOT_ROOT)
    parser.add_argument("--capital-root", type=Path, default=DEFAULT_CAPITAL_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--verifier-timeout-seconds", type=int, default=180)
    parser.add_argument("--skip-verifier", action="store_true")
    parser.add_argument("--stop-on-verifier-failure", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    mission_id = args.mission_id or f"dharma-capital-evolution-{utc_now().replace(':', '').replace('-', '')}"
    run_dir = args.output_root.expanduser() / mission_id
    run_dir.mkdir(parents=True, exist_ok=True)

    started = {
        "schema_version": "dharma.capital.evolution.run.v1",
        "mission_id": mission_id,
        "started_at": utc_now(),
        "duration_seconds": max(0.0, args.duration_seconds),
        "interval_seconds": max(0.0, args.interval_seconds),
        "snapshot_root": str(args.snapshot_root.expanduser()),
        "capital_root": str(args.capital_root.expanduser()),
        "run_dir": str(run_dir),
        "authority": dict(AUTHORITY_BOUNDARY),
    }
    atomic_write_json(run_dir / "run.json", started)

    receipts: list[dict[str, Any]] = []
    deadline = time.monotonic() + max(0.0, args.duration_seconds)
    interval = max(0.0, args.interval_seconds)
    iteration = 0
    status = "completed"
    try:
        while True:
            iteration += 1
            receipt = build_iteration(
                run_dir=run_dir,
                iteration=iteration,
                snapshot_root=args.snapshot_root.expanduser(),
                capital_root=args.capital_root.expanduser(),
                verifier_timeout_seconds=max(1, args.verifier_timeout_seconds),
                skip_verifier=args.skip_verifier,
            )
            receipts.append(receipt)
            if args.stop_on_verifier_failure and receipt["verifier"].get("passed") is False:
                status = "stopped_on_verifier_failure"
                break
            if args.max_iterations and iteration >= args.max_iterations:
                break
            if time.monotonic() >= deadline:
                break
            if interval:
                time.sleep(min(interval, max(0.0, deadline - time.monotonic())))
    except KeyboardInterrupt:
        status = "interrupted"
    summary = summarize_run(run_dir, receipts, status)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"status: {summary['status']}")
        print(f"run_dir: {summary['run_dir']}")
        print(f"iterations: {summary['iteration_count']}")
        print(f"latest_rating: {summary['latest_rating_out_of_100']}/100")
    return 0 if status in {"completed", "interrupted"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
