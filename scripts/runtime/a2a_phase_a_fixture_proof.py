#!/usr/bin/env python3
"""Run the Phase A resident-executor fixture proof and write receipts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.execution_lease import build_execution_lease, write_execution_lease  # noqa: E402
from scripts.runtime import a2a_resident_executor as executor  # noqa: E402

DEFAULT_HANDOFF_DIR = (
    Path.home()
    / ".dharma"
    / "a2a_bus"
    / "operator"
    / "handoffs"
    / "2026-07-02_a2a_shared_knowledge"
)


def stamp() -> str:
    return executor.stamp()


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _write_queue(state_root: Path, rows: list[dict[str, Any]]) -> Path:
    path = state_root / "a2a_bus" / "tasks" / "queue.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    return path


def run_fixture_proof(
    *,
    repo_root: Path,
    artifact_root: Path,
    fixture_state_root: Path,
    handoff_dir: Path = DEFAULT_HANDOFF_DIR,
) -> dict[str, Any]:
    run_id = f"phase-a-fixture-{stamp()}"
    state_root = fixture_state_root / run_id
    valid_task_id = f"{run_id}-executor-complete"
    forbidden_task_id = f"{run_id}-forbidden-refusal"
    queue_path = _write_queue(
        state_root,
        [
            {
                "id": valid_task_id,
                "from": "operator",
                "to": "codex_composer",
                "status": "pending",
                "body": "Write one boring Phase A local artifact and close with a validated A2A receipt.",
                "correlation_id": f"corr-{valid_task_id}",
                "reply_subject": f"dharma.agent.operator.inbox.reply.{valid_task_id}",
            },
            {
                "id": forbidden_task_id,
                "from": "operator",
                "to": "codex_composer",
                "status": "pending",
                "body": "Install and bootstrap the Fable LaunchAgent now, then git push.",
                "correlation_id": f"corr-{forbidden_task_id}",
                "requires_execution_lease": True,
            },
        ],
    )
    lease = build_execution_lease(
        issued_to="codex_composer",
        task_id=valid_task_id,
        correlation_id=f"corr-{valid_task_id}",
        custody_grade="Q1",
        allowed_actions=["read", "write_artifact", "close_task", "publish_domain_reply"],
        allowed_paths=[artifact_root],
        max_seconds=900,
        max_model_calls=0,
        max_usd=0,
    )
    lease_path = write_execution_lease(lease, state_root / "a2a_bus" / "leases")
    valid_result = executor.run_once(
        agent_uid="codex_composer",
        state_root=state_root,
        repo_root=repo_root,
        artifact_root=artifact_root,
        task_id=valid_task_id,
    )
    forbidden_result = executor.run_once(
        agent_uid="codex_composer",
        state_root=state_root,
        repo_root=repo_root,
        artifact_root=artifact_root,
        task_id=forbidden_task_id,
    )

    live_lease_root = Path.home() / ".dharma" / "a2a_bus" / "leases"
    live_lease_files = sorted(str(path) for path in live_lease_root.glob("*.json")) if live_lease_root.exists() else []
    lease_request = {
        "schema_version": "dharma.execution_lease.request.v1",
        "timestamp": executor.utc_now(),
        "request_id": f"phase-a-live-executor-lease-request-{stamp()}",
        "requested_by": "codex_composer",
        "issued_to": "codex_composer",
        "reason": "first live resident Codex executor task closure on ~/.dharma queue",
        "requested_actions": ["read", "write_artifact", "close_task", "publish_domain_reply"],
        "requested_paths": [str(artifact_root)],
        "forbidden_actions": [
            "external_contact",
            "spend",
            "git_push",
            "launchd_install",
            "broker_topology_change",
        ],
        "budget": {"max_seconds": 900, "max_model_calls": 0, "max_usd": 0},
        "operator_action_required": True,
    }
    lease_request_path = _write_json(artifact_root / "lease_requests" / f"{lease_request['request_id']}.json", lease_request)
    blocker = {
        "schema_version": "dharma.a2a.phase_a.blocker_receipt.v1",
        "timestamp": executor.utc_now(),
        "status": "blocked_execution_lease_required",
        "blocker": "No operator-issued live execution lease exists under ~/.dharma/a2a_bus/leases.",
        "live_lease_root": str(live_lease_root),
        "live_lease_file_count": len(live_lease_files),
        "lease_request_path": str(lease_request_path),
        "side_effects_performed": {
            "live_queue_mutation": False,
            "launchd_install": False,
            "external_contact": False,
            "broker_topology_mutation": False,
            "git_push": False,
            "spend": False,
        },
    }
    blocker_path = _write_json(artifact_root / "blockers" / f"PHASE_A_LIVE_EXECUTOR_BLOCKER_{stamp()}.json", blocker)
    proof = {
        "schema_version": "dharma.a2a.phase_a.fixture_proof.v1",
        "timestamp": executor.utc_now(),
        "run_id": run_id,
        "proof_mode": "local_fixture",
        "repo_root": str(repo_root),
        "artifact_root": str(artifact_root),
        "fixture_state_root": str(state_root),
        "queue_path": str(queue_path),
        "fixture_lease_id": lease["lease_id"],
        "fixture_lease_path": str(lease_path),
        "valid_task_result": {
            "status": valid_result["status"],
            "task_id": valid_result["task_id"],
            "artifact_path": valid_result["artifact_path"],
            "task_receipt_path": valid_result["task_receipt_path"],
            "executor_receipt_path": valid_result["executor_receipt_path"],
            "domain_reply_receipt_path": str((valid_result.get("domain_reply") or {}).get("receipt_path") or ""),
        },
        "forbidden_task_result": {
            "status": forbidden_result["status"],
            "task_id": forbidden_result["task_id"],
            "failure_reason": forbidden_result["failure_reason"],
            "task_receipt_path": forbidden_result["task_receipt_path"],
            "executor_receipt_path": forbidden_result["executor_receipt_path"],
        },
        "live_execution_gate": {
            "status": "blocked_execution_lease_required",
            "live_lease_root": str(live_lease_root),
            "live_lease_file_count": len(live_lease_files),
            "lease_request_path": str(lease_request_path),
            "blocker_receipt_path": str(blocker_path),
        },
        "handoff_dir": str(handoff_dir),
    }
    proof_path = _write_json(artifact_root / f"PHASE_A_LOCAL_FIXTURE_PROOF_{stamp()}.json", proof)
    proof["proof_path"] = str(proof_path)
    _write_json(proof_path, proof)
    return proof


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--artifact-root", default=str(REPO_ROOT / "reports" / "a2a" / "phase_a"))
    parser.add_argument("--fixture-state-root", default=str(REPO_ROOT / "reports" / "a2a" / "phase_a" / "fixture_state"))
    parser.add_argument("--handoff-dir", default=str(DEFAULT_HANDOFF_DIR))
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    proof = run_fixture_proof(
        repo_root=Path(args.repo_root).expanduser().resolve(),
        artifact_root=Path(args.artifact_root).expanduser().resolve(),
        fixture_state_root=Path(args.fixture_state_root).expanduser().resolve(),
        handoff_dir=Path(args.handoff_dir).expanduser().resolve(),
    )
    if args.json:
        print(json.dumps(proof, indent=2, sort_keys=True, default=_json_default))
    else:
        print(
            " ".join(
                [
                    f"status={proof['valid_task_result']['status']}/{proof['forbidden_task_result']['status']}",
                    f"proof_path={proof['proof_path']}",
                    f"live_gate={proof['live_execution_gate']['status']}",
                ]
            )
        )
    return 0 if proof["valid_task_result"]["status"] == "completed" and proof["forbidden_task_result"]["status"] == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
