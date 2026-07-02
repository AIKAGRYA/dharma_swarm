#!/usr/bin/env python3
"""Run the Active Track Final Boss review lane.

This is the operational wrapper around the Final Boss doctrine:

1. Generate a track-specific dossier.
2. Fan out dimension-scoped council prompts.
3. Synthesize a YAML-attachable `final_boss_review` packet only from real
   council receipts.

Dry-run mode writes prompts and a manifest, but never writes a passing review
packet. It is for inspection only.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import check_track_status as track_status  # type: ignore  # noqa: E402
from generate_final_boss_dossier import (  # type: ignore  # noqa: E402
    REPORT_DIR,
    _find_track,
    _safe_token,
    build_dossier,
    render_prompt,
    write_artifacts as write_dossier_artifacts,
)


DEFAULT_COUNCIL_RUNNER = (
    Path.home()
    / ".codex"
    / "skills"
    / "codex-composer-decorrelated-review-council"
    / "scripts"
    / "run_council.py"
)
DEFAULT_REPO_PYTHON = Path("/Users/dhyana/dharma_swarm/.venv/bin/python")
REVIEW_SCHEMA = "dharma.active_track_final_boss.review.v1"
MANIFEST_SCHEMA = "dharma.active_track_final_boss.run_manifest.v1"

DIMENSION_GUIDANCE: dict[str, str] = {
    "production_engineering": (
        "Inspect implementation completeness, API boundaries, error handling, "
        "resource cleanup, typing, concurrency, and whether the code is durable "
        "production engineering rather than scaffolding."
    ),
    "sre_failure_modes": (
        "Attack outage paths: retries, duplicate side effects, partial failure, "
        "timeouts, restart/reconnect behavior, observability, rollback, and "
        "whether failure can silently look successful."
    ),
    "architecture_integration": (
        "Check that this strengthens the whole Dharma Swarm architecture, uses "
        "the right existing seams, and does not introduce isolated local modules "
        "or hidden coupling."
    ),
    "anti_slop_code_quality": (
        "Reject brittle tests, tautologies, mock-only confidence, dead code, "
        "overfit assertions, stale generated reports, and AI-looking filler."
    ),
    "governance_truthfulness": (
        "Verify the closure kind, evidence, limits, non-claims, receipts, active "
        "track graph edges, and whether the claim would mislead future agents."
    ),
    "security_supply_chain": (
        "Review secrets, authority boundaries, dependency and provider trust, "
        "prompt/receipt injection paths, data exposure, and unsafe escalation."
    ),
    "future_maintainability": (
        "Judge whether a future agent/operator can safely extend, debug, test, "
        "and retire this without reconstructing hidden context."
    ),
}


def _stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _repo_display_path(path: str | Path) -> str:
    resolved = Path(path).expanduser().resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def _read_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _int_value(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _score_value(value: object, default: int = 0) -> int:
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return default


def selected_dimensions(raw_dimensions: list[str]) -> list[str]:
    known = sorted(track_status.FINAL_BOSS_DIMENSIONS)
    if not raw_dimensions:
        return known
    normalized = []
    for raw in raw_dimensions:
        dim = track_status._as_lower_token(raw)
        if dim not in track_status.FINAL_BOSS_DIMENSIONS:
            raise SystemExit(f"unknown Final Boss dimension {raw!r}; known: {known}")
        if dim not in normalized:
            normalized.append(dim)
    return normalized


def render_dimension_prompt(
    dossier: dict[str, Any],
    *,
    dimension: str,
    round_index: int,
    round_count: int,
) -> str:
    guidance = DIMENSION_GUIDANCE[dimension]
    base_prompt = render_prompt(dossier)
    return f"""# Active Track Final Boss Dimension Pass

Round: {round_index}/{round_count}
Required dimension: `{dimension}`

Dimension guidance:
{guidance}

This is not a narrow style review. Review the whole track, but score the
requested dimension with special force.
If any evidence is missing for this dimension, do not pass.
If this dimension exposes a blocker in another dimension, report it anyway.

The answer is still JSON only, using the schema requested below.

{base_prompt}
"""


def write_dimension_prompts(
    dossier: dict[str, Any],
    *,
    out_dir: Path,
    dimensions: list[str],
    rounds: int,
) -> list[dict[str, Any]]:
    prompt_dir = out_dir / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    stem = (
        f"{_safe_token(dossier['track_id'])}-"
        f"{_safe_token(dossier['target_closure_kind']).lower()}"
    )
    for round_index in range(1, rounds + 1):
        for dimension in dimensions:
            path = prompt_dir / f"{stem}-round-{round_index}-{dimension}.md"
            path.write_text(
                render_dimension_prompt(
                    dossier,
                    dimension=dimension,
                    round_index=round_index,
                    round_count=rounds,
                ).rstrip() + "\n",
                encoding="utf-8",
            )
            rows.append({
                "round": round_index,
                "dimension": dimension,
                "prompt": str(path),
            })
    return rows


def run_council_for_prompt(
    *,
    python: Path,
    council_runner: Path,
    prompt_file: Path,
    out_dir: Path,
    repo_root: Path,
    evidence_files: list[str],
    review_target: str,
    timeout_seconds: int,
    max_output_tokens: int,
    include_paid_deep_lanes: bool,
    allow_ollama_substitutes: bool,
) -> dict[str, Any]:
    cmd = [
        str(python),
        str(council_runner),
        "--repo-root",
        str(repo_root),
        "--prompt-file",
        str(prompt_file),
        "--review-target",
        review_target,
        "--out-dir",
        str(out_dir),
        "--target-score",
        "100",
        "--timeout-seconds",
        str(timeout_seconds),
        "--max-output-tokens",
        str(max_output_tokens),
        "--json",
    ]
    for evidence_file in evidence_files:
        cmd.extend(["--evidence-file", evidence_file])
    if include_paid_deep_lanes:
        cmd.append("--include-paid-deep-lanes")
    if allow_ollama_substitutes:
        cmd.append("--allow-ollama-substitutes")

    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        text=True,
        capture_output=True,
        timeout=timeout_seconds + 60,
    )
    payload: dict[str, Any]
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {}
    payload.update({
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
        "command": cmd,
    })
    return payload


def _receipt_disagreement_count(receipt: dict[str, Any]) -> int:
    count = 0
    for row in receipt.get("critics") or []:
        if not isinstance(row, dict):
            continue
        parsed = row.get("parsed") or {}
        if isinstance(parsed, dict) and str(parsed.get("explicit_disagreement") or "").strip():
            count += 1
    return count


def run_local_verifiers(dossier: dict[str, Any], *, timeout_seconds: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for verifier in dossier.get("local_verifiers") or []:
        if not isinstance(verifier, dict):
            continue
        command = str(verifier.get("command") or "").strip()
        row: dict[str, Any] = {
            "id": str(verifier.get("id") or "local-verifier"),
            "command": command,
            "purpose": str(verifier.get("purpose") or ""),
            "passed": False,
            "returncode": None,
        }
        if not command:
            row["stderr_tail"] = "missing command"
            rows.append(row)
            continue
        try:
            proc = subprocess.run(
                shlex.split(command),
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
            )
            row.update({
                "passed": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout_tail": (proc.stdout or "")[-4000:],
                "stderr_tail": (proc.stderr or "")[-4000:],
            })
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            row.update({
                "failure_type": type(exc).__name__,
                "stderr_tail": str(exc)[-4000:],
            })
        rows.append(row)
    return rows


def _build_council_coverage(
    *,
    receipt_paths: list[str | Path],
    dimensions: list[str],
    rounds: int,
) -> list[dict[str, Any]]:
    ordered_dimensions = sorted(track_status._as_str_set(dimensions))
    rows: list[dict[str, Any]] = []
    index = 0
    for round_index in range(1, max(1, rounds) + 1):
        for dimension in ordered_dimensions:
            if index >= len(receipt_paths):
                return rows
            rows.append({
                "round": round_index,
                "dimension": dimension,
                "council_receipt": _repo_display_path(receipt_paths[index]),
            })
            index += 1
    return rows


def build_review_packet(
    *,
    dossier_path: str | Path,
    receipt_paths: list[str | Path],
    dimensions: list[str],
    rounds: int,
    runtime_evidence: list[str],
    failure_modes_tested: list[str],
    mock_only: bool,
    local_verifier_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    dossier = _read_json(dossier_path)
    receipts = [_read_json(path) for path in receipt_paths]
    required_counts = [
        _int_value(r.get("required_critic_count") or r.get("critic_count"))
        for r in receipts
    ]
    score_values = [_score_value(r.get("score_min")) for r in receipts]
    explicit_disagreements = sum(_receipt_disagreement_count(r) for r in receipts)
    verifier_results = list(local_verifier_results or [])
    local_verifiers_passed = bool(verifier_results) and all(
        isinstance(row, dict) and row.get("passed") is True for row in verifier_results
    )
    profile = track_status._as_lower_token(dossier.get("graduation_profile"))
    failure_modes = sorted(track_status._as_str_set(failure_modes_tested))

    packet: dict[str, Any] = {
        "schema_version": REVIEW_SCHEMA,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "track_id": dossier.get("track_id"),
        "target_closure_kind": track_status._as_upper_token(dossier.get("target_closure_kind")),
        "graduation_profile": profile,
        "dossier": _repo_display_path(dossier_path),
        "council_receipts": [_repo_display_path(path) for path in receipt_paths],
        "reviewer_count": min(required_counts) if required_counts else 0,
        "score_min": min(score_values) if score_values else 0,
        "explicit_disagreements": explicit_disagreements,
        "local_verifiers_passed": local_verifiers_passed,
        "local_verifier_results": verifier_results,
        "rounds": max(1, rounds),
        "dimensions": sorted(track_status._as_str_set(dimensions)),
        "council_coverage": _build_council_coverage(
            receipt_paths=receipt_paths,
            dimensions=dimensions,
            rounds=rounds,
        ),
    }
    if receipt_paths:
        packet["council_receipt"] = packet["council_receipts"][0]
    if profile == "runtime_transport" or runtime_evidence:
        packet["runtime_evidence"] = list(runtime_evidence)
        packet["failure_modes_tested"] = failure_modes
        packet["mock_only"] = bool(mock_only)
    return packet


def validation_blocks_for_packet(
    *,
    track_id: str,
    target_closure_kind: str,
    packet: dict[str, Any],
) -> list[str]:
    track, _section = _find_track(track_id)
    candidate = dict(track)
    candidate["target_closure_kind"] = track_status._as_upper_token(target_closure_kind)
    candidate["graduation_profile"] = packet.get("graduation_profile") or track_status._graduation_profile(track)
    candidate["final_boss_review"] = packet
    return track_status._final_boss_blocks(candidate, target_closure_kind)


def write_review_packet(
    *,
    packet: dict[str, Any],
    out_dir: Path,
    track_id: str,
    target_closure_kind: str,
) -> dict[str, Any]:
    review_dir = out_dir / "reviews"
    review_dir.mkdir(parents=True, exist_ok=True)
    path = review_dir / (
        f"{_stamp()}-{_safe_token(track_id)}-"
        f"{_safe_token(target_closure_kind).lower()}-final-boss-review.json"
    )
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"final_boss_review_json": str(path)}


def yaml_snippet(packet: dict[str, Any]) -> str:
    lines = [
        "final_boss_review:",
        f"  dossier: {json.dumps(packet['dossier'])}",
    ]
    if packet.get("council_receipt"):
        lines.append(f"  council_receipt: {json.dumps(packet['council_receipt'])}")
    if packet.get("council_receipts"):
        lines.append("  council_receipts:")
        lines.extend(f"    - {json.dumps(path)}" for path in packet["council_receipts"])
    if packet.get("council_coverage"):
        lines.append("  council_coverage:")
        for row in packet["council_coverage"]:
            lines.extend([
                f"    - round: {row['round']}",
                f"      dimension: {json.dumps(row['dimension'])}",
                f"      council_receipt: {json.dumps(row['council_receipt'])}",
            ])
    lines.extend([
        f"  reviewer_count: {packet['reviewer_count']}",
        f"  score_min: {packet['score_min']}",
        f"  explicit_disagreements: {packet['explicit_disagreements']}",
        f"  local_verifiers_passed: {str(bool(packet.get('local_verifiers_passed'))).lower()}",
        "  local_verifier_results:",
    ])
    verifier_rows = packet.get("local_verifier_results") or []
    if verifier_rows:
        for row in verifier_rows:
            lines.extend([
                f"    - id: {json.dumps(row.get('id'))}",
                f"      command: {json.dumps(row.get('command'))}",
                f"      passed: {str(bool(row.get('passed'))).lower()}",
                f"      returncode: {row.get('returncode') if row.get('returncode') is not None else 'null'}",
            ])
    else:
        lines[-1] = "  local_verifier_results: []"
    lines.extend([
        f"  rounds: {packet['rounds']}",
        "  dimensions:",
    ])
    lines.extend(f"    - {json.dumps(dim)}" for dim in packet["dimensions"])
    if "runtime_evidence" in packet:
        if packet["runtime_evidence"]:
            lines.append("  runtime_evidence:")
            lines.extend(f"    - {json.dumps(path)}" for path in packet["runtime_evidence"])
        else:
            lines.append("  runtime_evidence: []")
        if packet.get("failure_modes_tested"):
            lines.append("  failure_modes_tested:")
            lines.extend(f"    - {json.dumps(mode)}" for mode in packet["failure_modes_tested"])
        else:
            lines.append("  failure_modes_tested: []")
        lines.append(f"  mock_only: {str(bool(packet.get('mock_only'))).lower()}")
    return "\n".join(lines) + "\n"


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track-id", required=True)
    parser.add_argument("--target-closure-kind", default="SUBSTRATE_TRUSTED")
    parser.add_argument("--rounds", type=int, default=track_status.FINAL_BOSS_MIN_ROUNDS)
    parser.add_argument("--dimension", action="append", default=[])
    parser.add_argument("--out-dir", default=str(REPORT_DIR()))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--receipt", action="append", default=[],
                        help="Existing council receipt JSON to synthesize from; repeatable.")
    parser.add_argument("--synthesize-only", action="store_true")
    parser.add_argument("--runtime-evidence", action="append", default=[],
                        help="Runtime proof path/receipt required for runtime_transport production claims.")
    parser.add_argument("--failure-mode-tested", action="append", default=[])
    parser.add_argument("--mock-only", action="store_true")
    parser.add_argument("--council-runner", default=str(DEFAULT_COUNCIL_RUNNER))
    parser.add_argument("--python", default=str(DEFAULT_REPO_PYTHON if DEFAULT_REPO_PYTHON.exists() else Path(sys.executable)))
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--max-output-tokens", type=int, default=12000)
    parser.add_argument("--local-verifier-timeout-seconds", type=int, default=300)
    parser.add_argument("--include-paid-deep-lanes", action="store_true")
    parser.add_argument("--allow-ollama-substitutes", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    target = track_status._as_upper_token(args.target_closure_kind)
    if target not in track_status.CLOSURE_KINDS:
        raise SystemExit(f"unknown target closure kind {target!r}")
    rounds = max(1, args.rounds)
    dimensions = selected_dimensions(args.dimension)
    out_dir = Path(args.out_dir).expanduser().resolve()

    dossier = build_dossier(args.track_id, target)
    dossier_paths = write_dossier_artifacts(dossier, out_dir)
    prompt_rows = write_dimension_prompts(
        dossier,
        out_dir=out_dir,
        dimensions=dimensions,
        rounds=rounds,
    )

    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "track_id": args.track_id,
        "target_closure_kind": target,
        "graduation_profile": dossier["graduation_profile"],
        "dossier": dossier_paths,
        "dimensions": dimensions,
        "rounds": rounds,
        "prompt_count": len(prompt_rows),
        "prompts": prompt_rows,
        "dry_run": bool(args.dry_run),
        "ship_safe": False,
    }

    receipt_paths = [str(Path(p).expanduser()) for p in args.receipt]
    local_verifier_results: list[dict[str, Any]] = []
    council_runs: list[dict[str, Any]] = []
    if args.dry_run:
        manifest["status"] = "dry_run_only"
        manifest["note"] = "Prompts generated only; no council receipts and no final_boss_review packet."
    elif not args.synthesize_only:
        local_verifier_results = run_local_verifiers(
            dossier,
            timeout_seconds=args.local_verifier_timeout_seconds,
        )
        manifest["local_verifier_results"] = local_verifier_results
        council_out = out_dir / "council"
        council_runner = Path(args.council_runner).expanduser().resolve()
        python = Path(args.python).expanduser().resolve()
        if not council_runner.exists():
            raise SystemExit(f"council runner not found: {council_runner}")
        for row in prompt_rows:
            review_target = (
                f"final-boss:{args.track_id}:{target}:"
                f"round-{row['round']}:{row['dimension']}"
            )
            run = run_council_for_prompt(
                python=python,
                council_runner=council_runner,
                prompt_file=Path(row["prompt"]),
                out_dir=council_out,
                repo_root=REPO_ROOT,
                evidence_files=dossier["evidence_files"],
                review_target=review_target,
                timeout_seconds=args.timeout_seconds,
                max_output_tokens=args.max_output_tokens,
                include_paid_deep_lanes=args.include_paid_deep_lanes,
                allow_ollama_substitutes=args.allow_ollama_substitutes,
            )
            run.update({"round": row["round"], "dimension": row["dimension"]})
            council_runs.append(run)
            if run.get("summary_json"):
                receipt_paths.append(str(run["summary_json"]))
        manifest["council_runs"] = council_runs
    elif not args.dry_run:
        local_verifier_results = run_local_verifiers(
            dossier,
            timeout_seconds=args.local_verifier_timeout_seconds,
        )
        manifest["local_verifier_results"] = local_verifier_results

    if not args.dry_run and receipt_paths:
        packet = build_review_packet(
            dossier_path=dossier_paths["dossier_json"],
            receipt_paths=receipt_paths,
            dimensions=dimensions,
            rounds=rounds,
            runtime_evidence=args.runtime_evidence,
            failure_modes_tested=args.failure_mode_tested,
            mock_only=args.mock_only,
            local_verifier_results=local_verifier_results,
        )
        blocks = validation_blocks_for_packet(
            track_id=args.track_id,
            target_closure_kind=target,
            packet=packet,
        )
        packet["ready_for_yaml_attach"] = not blocks
        packet["validation_blocks"] = blocks
        packet_paths = write_review_packet(
            packet=packet,
            out_dir=out_dir,
            track_id=args.track_id,
            target_closure_kind=target,
        )
        manifest["final_boss_review"] = packet_paths
        manifest["final_boss_review_packet"] = packet
        manifest["yaml_snippet"] = yaml_snippet(packet)
        manifest["ship_safe"] = not blocks
        manifest["status"] = "pass_fullness" if not blocks else "hold_blockers"
    elif not args.dry_run:
        manifest["status"] = "hold_no_receipts"
        manifest["note"] = "No council receipts were produced or supplied."

    manifest_path = out_dir / "runs" / (
        f"{_stamp()}-{_safe_token(args.track_id)}-{_safe_token(target).lower()}-manifest.json"
    )
    latest_manifest_path = out_dir / "runs" / (
        f"latest-{_safe_token(args.track_id)}-{_safe_token(target).lower()}-manifest.json"
    )
    manifest["manifest_json"] = str(manifest_path)
    manifest["latest_manifest_json"] = str(latest_manifest_path)
    write_manifest(manifest_path, manifest)
    write_manifest(latest_manifest_path, manifest)

    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(f"FINAL_BOSS status={manifest['status']} ship_safe={manifest['ship_safe']}")
        print(f"manifest: {manifest_path}")
        if manifest.get("final_boss_review"):
            print(f"review: {manifest['final_boss_review']['final_boss_review_json']}")
    return 0 if manifest["ship_safe"] or args.dry_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
