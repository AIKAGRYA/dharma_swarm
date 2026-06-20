"""Minimal verifier and archive closure for intelligence supply-chain signals."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.world_radar.bronze import BOUNDARY_CONTRACT
from dharma_swarm.world_radar.io_utils import (
    append_jsonl_once,
    read_json,
    utc_now_iso,
    write_json_atomic,
)

RESEARCH_BRIEF_SCHEMA = "intelligence_supply_chain.research_brief.v1"
VERIFIER_RECEIPT_SCHEMA = "intelligence_supply_chain.frontier_council_receipt.v1"
SANDBOX_RESULT_SCHEMA = "intelligence_supply_chain.sandbox_result.v1"
ARCHIVE_RECEIPT_SCHEMA = "intelligence_supply_chain.archive_receipt.v1"
COUNCIL_AGENT_ID = "dharma_swarm.frontier_council"


@dataclass(frozen=True)
class FullChainRunResult:
    """Receipt paths emitted by one full supply-chain closure attempt."""

    research_brief_path: str
    verifier_receipt_path: str
    sandbox_result_path: str
    archive_receipt_path: str
    archive_ledger_path: str
    decision_kind: str
    sandbox_passed: bool

    @property
    def ok(self) -> bool:
        return self.sandbox_passed


def run_full_supply_chain(
    boundary_path: Path | str,
    *,
    state_dir: Path | str | None = None,
    sandbox_command: Sequence[str] | None = None,
    sandbox_cwd: Path | str | None = None,
    timeout_s: int = 30,
) -> FullChainRunResult:
    """Consume one Bronze boundary and close it with verifier + archive receipts."""

    state = _state_dir(state_dir)
    boundary_file = Path(boundary_path).expanduser()
    boundary = _load_required_json(boundary_file, label="boundary")
    _validate_boundary(boundary)
    raw_receipt_path = Path(str(boundary["evidence"]["raw_receipt_path"])).expanduser()
    raw_receipt = _load_required_json(raw_receipt_path, label="raw_receipt")

    brief = _research_brief(boundary, raw_receipt, raw_receipt_path=raw_receipt_path)
    brief_path = research_brief_dir(state) / f"{brief['brief_id']}.json"
    write_json_atomic(brief_path, brief)

    verifier = _verifier_receipt(boundary, raw_receipt, brief, brief_path=brief_path)
    verifier_path = verifier_receipt_dir(state) / f"{verifier['verifier_receipt_id']}.json"
    write_json_atomic(verifier_path, verifier)

    command = list(sandbox_command or _default_sandbox_command())
    sandbox = _run_sandbox(
        command,
        boundary=boundary,
        verifier=verifier,
        cwd=Path(sandbox_cwd).expanduser() if sandbox_cwd else Path.cwd(),
        timeout_s=timeout_s,
    )
    sandbox_path = sandbox_result_dir(state) / f"{sandbox['sandbox_result_id']}.json"
    write_json_atomic(sandbox_path, sandbox)

    archive = _archive_receipt(
        boundary,
        raw_receipt,
        brief,
        verifier,
        sandbox,
        paths={
            "raw_receipt_path": str(raw_receipt_path),
            "boundary_path": str(boundary_file),
            "research_brief_path": str(brief_path),
            "verifier_receipt_path": str(verifier_path),
            "sandbox_result_path": str(sandbox_path),
        },
    )
    archive_path = archive_receipt_dir(state) / f"{archive['archive_receipt_id']}.json"
    write_json_atomic(archive_path, archive)
    append_jsonl_once(archive_ledger_path(state), archive, key_field="archive_receipt_id")

    return FullChainRunResult(
        research_brief_path=str(brief_path),
        verifier_receipt_path=str(verifier_path),
        sandbox_result_path=str(sandbox_path),
        archive_receipt_path=str(archive_path),
        archive_ledger_path=str(archive_ledger_path(state)),
        decision_kind=str(verifier["decision"]["kind"]),
        sandbox_passed=bool(sandbox["passed"]),
    )


def supply_chain_root(state_dir: Path | str | None = None) -> Path:
    return _state_dir(state_dir) / "meta" / "intelligence_supply_chain"


def silver_root(state_dir: Path | str | None = None) -> Path:
    return supply_chain_root(state_dir) / "silver"


def research_brief_dir(state_dir: Path | str | None = None) -> Path:
    return silver_root(state_dir) / "research_briefs"


def verifier_receipt_dir(state_dir: Path | str | None = None) -> Path:
    return silver_root(state_dir) / "verifier_receipts"


def sandbox_result_dir(state_dir: Path | str | None = None) -> Path:
    return silver_root(state_dir) / "sandbox_results"


def archive_receipt_dir(state_dir: Path | str | None = None) -> Path:
    return supply_chain_root(state_dir) / "archive"


def archive_ledger_path(state_dir: Path | str | None = None) -> Path:
    return supply_chain_root(state_dir) / "archive.jsonl"


def _research_brief(
    boundary: dict[str, Any],
    raw_receipt: dict[str, Any],
    *,
    raw_receipt_path: Path,
) -> dict[str, Any]:
    brief_id = _artifact_id("isc_brief", boundary["boundary_id"], boundary["content_hash"])
    return {
        "schema_version": RESEARCH_BRIEF_SCHEMA,
        "brief_id": brief_id,
        "created_at": utc_now_iso(),
        "source_boundary_id": boundary["boundary_id"],
        "source_receipt_id": boundary["source_receipt_id"],
        "content_hash": boundary["content_hash"],
        "source_url": boundary["source_url"],
        "source_title": boundary["title"],
        "raw_receipt_path": str(raw_receipt_path),
        "claims": [
            {
                "kind": boundary["claim"]["kind"],
                "text": boundary["claim"]["text"],
                "verified": False,
            }
        ],
        "source_policy": {
            "raw_text_is_untrusted": bool(boundary["guardrails"]["source_text_is_untrusted"]),
            "must_not_execute_payload": bool(
                raw_receipt["instruction_policy"]["payload_must_not_be_executed"]
            ),
        },
        "corroboration": dict(raw_receipt.get("corroboration") or {}),
        "synthesis": (
            "Single-source external signal admitted for verifier review. "
            "No source text is treated as instruction or apply authority."
        ),
    }


def _verifier_receipt(
    boundary: dict[str, Any],
    raw_receipt: dict[str, Any],
    brief: dict[str, Any],
    *,
    brief_path: Path,
) -> dict[str, Any]:
    corroboration = dict(raw_receipt.get("corroboration") or {})
    observed_k = int(corroboration.get("observed_k") or 0)
    required_k = int(corroboration.get("required_k") or 2)
    if observed_k < required_k:
        decision = {
            "kind": "halt",
            "reason": "insufficient_independent_corroboration",
            "observed_k": observed_k,
            "required_k": required_k,
        }
    else:
        decision = {
            "kind": "scorable_task",
            "task": {
                "task_id": _artifact_id("isc_task", boundary["boundary_id"], brief["brief_id"]),
                "hypothesis": f"Evaluate applicability of external signal: {boundary['title']}",
                "quality_metric": "sandbox_command_exit_code_zero",
                "sandbox_command_required": True,
                "pass_interpretation": "Command exits 0 and emits an archive receipt before any apply.",
                "fail_interpretation": "Do not apply; archive failed task evidence.",
            },
        }
    receipt_id = _artifact_id("isc_verifier", boundary["boundary_id"], json.dumps(decision, sort_keys=True))
    return {
        "schema_version": VERIFIER_RECEIPT_SCHEMA,
        "verifier_receipt_id": receipt_id,
        "created_at": utc_now_iso(),
        "verifier": COUNCIL_AGENT_ID,
        "verifier_interface": BOUNDARY_CONTRACT,
        "source_boundary_id": boundary["boundary_id"],
        "source_receipt_id": boundary["source_receipt_id"],
        "content_hash": boundary["content_hash"],
        "research_brief_id": brief["brief_id"],
        "research_brief_path": str(brief_path),
        "input_claim": boundary["claim"],
        "decision": decision,
        "guardrails": {
            "source_text_was_untrusted": bool(boundary["guardrails"]["source_text_is_untrusted"]),
            "self_signed_runtime_verdict_allowed": False,
            "may_apply_code": False,
        },
    }


def _run_sandbox(
    command: list[str],
    *,
    boundary: dict[str, Any],
    verifier: dict[str, Any],
    cwd: Path,
    timeout_s: int,
) -> dict[str, Any]:
    started_at = utc_now_iso()
    result_id = _artifact_id("isc_sandbox", boundary["boundary_id"], verifier["verifier_receipt_id"])
    try:
        completed = subprocess.run(  # noqa: S603 - command is caller-provided argv, never shell.
            command,
            cwd=str(cwd),
            timeout=timeout_s,
            capture_output=True,
            text=True,
            check=False,
        )
        exit_code = int(completed.returncode)
        error = ""
        stdout = completed.stdout
        stderr = completed.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        exit_code = 124 if isinstance(exc, subprocess.TimeoutExpired) else 127
        error = str(exc)
        stdout = getattr(exc, "stdout", "") or ""
        stderr = getattr(exc, "stderr", "") or ""
    return {
        "schema_version": SANDBOX_RESULT_SCHEMA,
        "sandbox_result_id": result_id,
        "started_at": started_at,
        "completed_at": utc_now_iso(),
        "source_boundary_id": boundary["boundary_id"],
        "verifier_receipt_id": verifier["verifier_receipt_id"],
        "command": command,
        "cwd": str(cwd),
        "timeout_s": timeout_s,
        "exit_code": exit_code,
        "passed": exit_code == 0,
        "error": _preview(error, limit=500),
        "stdout_preview": _preview(stdout),
        "stderr_preview": _preview(stderr),
    }


def _archive_receipt(
    boundary: dict[str, Any],
    raw_receipt: dict[str, Any],
    brief: dict[str, Any],
    verifier: dict[str, Any],
    sandbox: dict[str, Any],
    *,
    paths: dict[str, str],
) -> dict[str, Any]:
    archive_id = _artifact_id("isc_archive", boundary["boundary_id"], verifier["verifier_receipt_id"])
    decision_kind = str(verifier["decision"]["kind"])
    return {
        "schema_version": ARCHIVE_RECEIPT_SCHEMA,
        "archive_receipt_id": archive_id,
        "created_at": utc_now_iso(),
        "status": f"closed_{decision_kind}",
        "source_url": boundary["source_url"],
        "source_title": boundary["title"],
        "content_hash": boundary["content_hash"],
        "lineage": {
            "signal": boundary["content_hash"],
            "raw_receipt": raw_receipt["receipt_id"],
            "boundary": boundary["boundary_id"],
            "research_brief": brief["brief_id"],
            "verifier_receipt": verifier["verifier_receipt_id"],
            "implementation": "no_change",
            "sandbox_result": sandbox["sandbox_result_id"],
            "ablation": sandbox["sandbox_result_id"],
            "kept_claim": decision_kind,
        },
        "decision": verifier["decision"],
        "sandbox_passed": bool(sandbox["passed"]),
        "not_applied": True,
        "paths": paths,
    }


def _validate_boundary(boundary: dict[str, Any]) -> None:
    if boundary.get("verifier_interface") != BOUNDARY_CONTRACT:
        raise ValueError("unsupported_boundary_contract")
    if not boundary.get("not_applied"):
        raise ValueError("boundary_must_not_be_preapplied")
    if not isinstance(boundary.get("evidence"), dict):
        raise ValueError("boundary_missing_evidence")


def _load_required_json(path: Path, *, label: str) -> dict[str, Any]:
    payload = read_json(path, default=None)
    if not isinstance(payload, dict):
        raise FileNotFoundError(f"{label}_json_not_found:{path}")
    return payload


def _default_sandbox_command() -> list[str]:
    return [sys.executable, "-m", "compileall", "-q", "dharma_swarm/frontier_council.py"]


def _artifact_id(prefix: str, *parts: str) -> str:
    seed = "|".join(parts)
    return f"{prefix}_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24]}"


def _preview(value: str | bytes, *, limit: int = 2000) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return " ".join(str(value).split())[:limit]


def _state_dir(state_dir: Path | str | None) -> Path:
    return Path(state_dir).expanduser() if state_dir is not None else dharma_state_dir()


__all__ = [
    "ARCHIVE_RECEIPT_SCHEMA",
    "FullChainRunResult",
    "RESEARCH_BRIEF_SCHEMA",
    "SANDBOX_RESULT_SCHEMA",
    "VERIFIER_RECEIPT_SCHEMA",
    "archive_ledger_path",
    "archive_receipt_dir",
    "research_brief_dir",
    "run_full_supply_chain",
    "sandbox_result_dir",
    "verifier_receipt_dir",
]
