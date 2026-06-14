#!/usr/bin/env python3
"""Probe the installed ds-goal wrapper against temp runtime DBs.

This verifier compares the wrapper's default target with an explicit
DHARMA_SWARM_REPO pin to the audited checkout. It writes only under the
requested temp proof root and never edits the wrapper or target repos.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.ds_goal_wrapper_contract import (
    default_wrapper_target as _shared_default_wrapper_target,
    wrapper_convergence_decision_packet,
)


DEFAULT_WRAPPER = Path.home() / ".dharma" / "bin" / "ds-goal"
MAJOR_RECEIPT_TYPES = ("task_claim", "delegation_run", "a2a_task")


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _print(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, default=_json_default, sort_keys=True))
        return
    print("DS-GOAL WRAPPER RECEIPT PROBE")
    print(f"status: {payload['status']}")
    print(f"proof_root: {payload['proof_root']}")
    for case in payload["cases"]:
        summary = case.get("receipt_summary") or {}
        print(
            f"- {case['case']}: clean={summary.get('clean')} "
            f"major={summary.get('major_total')} "
            f"missing_side_effect={summary.get('major_missing_side_effect_key')} "
            f"missing_idempotency={summary.get('major_missing_idempotency_joins')} "
            f"run_id={case.get('run_id', '')}"
        )
    if payload.get("next_action"):
        print(f"next_action: {payload['next_action']}")


def _safe_env(*, home: Path, path_value: str, repo_pin: Path | None) -> dict[str, str]:
    env = {
        "HOME": str(home),
        "PATH": path_value,
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "TMPDIR": os.environ.get("TMPDIR", tempfile.gettempdir()),
    }
    if repo_pin is not None:
        env["DHARMA_SWARM_REPO"] = str(repo_pin)
    return env


def _run_json_command(
    command: list[str],
    *,
    env: dict[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or f"command timed out after {timeout_seconds}s",
            "json": {},
            "command": command,
        }
    parsed: dict[str, Any] = {}
    stdout = completed.stdout.strip()
    if stdout:
        try:
            candidate = json.loads(stdout)
            if isinstance(candidate, dict):
                parsed = candidate
        except json.JSONDecodeError:
            parsed = {}
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "json": parsed,
        "command": command,
    }


def _run_wrapper_case(
    *,
    case: str,
    wrapper: Path,
    proof_root: Path,
    audited_repo: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    state_root = proof_root / case / "state"
    kernel_store = proof_root / case / "kernel"
    mission_id = f"{case}-wrapper-proof-{uuid4().hex[:8]}"
    repo_pin = audited_repo if case == "pinned" else None
    env = _safe_env(
        home=Path.home(),
        path_value=os.environ.get("PATH", "/usr/bin:/bin"),
        repo_pin=repo_pin,
    )
    init_result = _run_json_command(
        [
            str(wrapper),
            "init",
            "--state-root",
            str(state_root),
            "--kernel-store",
            str(kernel_store),
            "--mission-id",
            mission_id,
            "--goal",
            f"{case} wrapper receipt proof",
            "--json",
        ],
        env=env,
        timeout_seconds=timeout_seconds,
    )
    run_result: dict[str, Any] = {
        "returncode": 99,
        "stdout": "",
        "stderr": "init did not complete",
        "json": {},
        "command": [],
    }
    if init_result["returncode"] == 0:
        run_result = _run_json_command(
            [
                str(wrapper),
                "run",
                "--state-root",
                str(state_root),
                "--kernel-store",
                str(kernel_store),
                "--mission-id",
                mission_id,
                "--max-wakes",
                "1",
                "--json",
            ],
            env=env,
            timeout_seconds=timeout_seconds,
        )
    runtime_truth_ref = run_result.get("json", {}).get("runtime_truth_ref")
    if not isinstance(runtime_truth_ref, dict):
        runtime_truth_ref = {}
    runtime_db = Path(
        str(runtime_truth_ref.get("runtime_db") or state_root / ".runtime" / "runtime.db")
    )
    run_id = str(runtime_truth_ref.get("run_id") or "")
    return {
        "case": case,
        "repo_pin": str(repo_pin or ""),
        "state_root": str(state_root),
        "kernel_store": str(kernel_store),
        "mission_id": mission_id,
        "runtime_db": str(runtime_db),
        "run_id": run_id,
        "init": _command_result_summary(init_result),
        "run": _command_result_summary(run_result),
        "receipt_summary": summarize_runtime_receipts(runtime_db, run_id=run_id),
    }


def _command_result_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "returncode": result.get("returncode"),
        "stderr": str(result.get("stderr") or "").strip(),
        "command": result.get("command") or [],
    }


def _count_one(db: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> int:
    row = db.execute(query, params).fetchone()
    if row is None:
        return 0
    value = row[0]
    return int(value or 0)


def summarize_runtime_receipts(db_path: Path, *, run_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "run_id": run_id,
        "runtime_total": 0,
        "runtime_side_effect_key_filled": 0,
        "major_total": 0,
        "major_missing_side_effect_key": 0,
        "major_missing_idempotency_joins": 0,
        "major_rows": [],
        "clean": False,
        "error": "",
    }
    if not db_path.exists():
        result["error"] = "runtime DB missing"
        return result
    if not run_id:
        result["error"] = "run_id missing"
        return result
    try:
        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            params = (run_id,)
            result["runtime_total"] = _count_one(
                db,
                "SELECT COUNT(*) FROM runtime_receipts WHERE run_id = ?",
                params,
            )
            result["runtime_side_effect_key_filled"] = _count_one(
                db,
                "SELECT COUNT(*) FROM runtime_receipts "
                "WHERE run_id = ? AND COALESCE(side_effect_key, '') != ''",
                params,
            )
            placeholders = ",".join("?" for _ in MAJOR_RECEIPT_TYPES)
            major_params = (run_id, *MAJOR_RECEIPT_TYPES)
            result["major_total"] = _count_one(
                db,
                "SELECT COUNT(*) FROM runtime_receipts "
                f"WHERE run_id = ? AND receipt_type IN ({placeholders})",
                major_params,
            )
            result["major_missing_side_effect_key"] = _count_one(
                db,
                "SELECT COUNT(*) FROM runtime_receipts "
                f"WHERE run_id = ? AND receipt_type IN ({placeholders}) "
                "AND COALESCE(side_effect_key, '') = ''",
                major_params,
            )
            result["major_missing_idempotency_joins"] = _count_one(
                db,
                "SELECT COUNT(*) "
                "FROM runtime_receipts rr "
                "LEFT JOIN idempotency_records ir "
                "ON rr.idempotency_key = ir.idempotency_key "
                "AND rr.side_effect_key = ir.side_effect_key "
                "WHERE rr.run_id = ? "
                f"AND rr.receipt_type IN ({placeholders}) "
                "AND ir.idempotency_key IS NULL",
                major_params,
            )
            rows = db.execute(
                "SELECT receipt_type, receipt_id, status, idempotency_key, side_effect_key "
                "FROM runtime_receipts "
                f"WHERE run_id = ? AND receipt_type IN ({placeholders}) "
                "ORDER BY created_at, receipt_id",
                major_params,
            ).fetchall()
            result["major_rows"] = [dict(row) for row in rows]
    except sqlite3.Error as exc:
        result["error"] = str(exc)
        return result
    result["clean"] = (
        int(result["major_total"]) > 0
        and int(result["major_missing_side_effect_key"]) == 0
        and int(result["major_missing_idempotency_joins"]) == 0
    )
    return result


def classify_cases(cases: list[dict[str, Any]]) -> tuple[str, str]:
    by_case = {case.get("case"): case for case in cases}
    pinned = by_case.get("pinned", {})
    default = by_case.get("default", {})
    pinned_clean = bool((pinned.get("receipt_summary") or {}).get("clean"))
    default_clean = bool((default.get("receipt_summary") or {}).get("clean"))
    if pinned_clean and default_clean:
        return (
            "clean",
            "default wrapper and audited checkout both produce keyed major receipts",
        )
    if pinned_clean and not default_clean:
        return (
            "split_brain_confirmed",
            "default wrapper target emits weak receipts while DHARMA_SWARM_REPO pin is clean",
        )
    if not pinned_clean and default_clean:
        return (
            "audited_checkout_dirty",
            "audited checkout pin emits weak receipts while default wrapper is clean",
        )
    return (
        "both_dirty",
        "both default wrapper and audited checkout pin emit weak receipts or failed to run",
    )


def _default_wrapper_target(
    *,
    home: Path,
    audited_repo: Path,
    wrapper: Path = DEFAULT_WRAPPER,
) -> dict[str, Any]:
    return _shared_default_wrapper_target(
        home=home,
        audited_repo=audited_repo,
        wrapper=wrapper,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run temp-state ds-goal wrapper receipt probes.",
    )
    parser.add_argument("--wrapper", type=Path, default=DEFAULT_WRAPPER)
    parser.add_argument("--audited-repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--proof-root", type=Path, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--expect-split-brain",
        action="store_true",
        help="Exit 0 only when pinned is clean and default wrapper is dirty.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    proof_root = args.proof_root
    if proof_root is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        proof_root = Path(tempfile.gettempdir()) / f"ds-goal-wrapper-receipt-probe-{stamp}"
    proof_root.mkdir(parents=True, exist_ok=True)
    cases = [
        _run_wrapper_case(
            case="pinned",
            wrapper=args.wrapper,
            proof_root=proof_root,
            audited_repo=args.audited_repo,
            timeout_seconds=max(1, int(args.timeout_seconds)),
        ),
        _run_wrapper_case(
            case="default",
            wrapper=args.wrapper,
            proof_root=proof_root,
            audited_repo=args.audited_repo,
            timeout_seconds=max(1, int(args.timeout_seconds)),
        ),
    ]
    status, next_action = classify_cases(cases)
    payload = {
        "schema_version": "dharma.ds_goal_wrapper_receipt_probe.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "proof_root": str(proof_root),
        "wrapper": str(args.wrapper),
        "audited_repo": str(args.audited_repo),
        "default_wrapper_target": _default_wrapper_target(
            home=Path.home(),
            audited_repo=args.audited_repo,
            wrapper=args.wrapper,
        ),
        "convergence_decision_packet": {
            **wrapper_convergence_decision_packet(
                home=Path.home(),
                audited_repo=args.audited_repo,
                wrapper=args.wrapper,
            ),
            "latest_probe_status": status,
            "latest_probe_next_action": next_action,
            "latest_probe_proof_root": str(proof_root),
        },
        "cases": cases,
        "next_action": next_action,
    }
    _print(payload, as_json=args.json)
    if args.expect_split_brain:
        return 0 if status == "split_brain_confirmed" else 1
    return 0 if status == "clean" else 1


if __name__ == "__main__":
    raise SystemExit(main())
