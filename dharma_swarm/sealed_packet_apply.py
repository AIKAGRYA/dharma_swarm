"""Sealed Build Protocol packet ingestion for DarwinEngine.

This leaf module keeps the bulky packet validation and conservative diff guard
out of ``evolution.py`` while preserving DarwinEngine as the public authority.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
import fnmatch
import json
from pathlib import Path
from typing import Any

from dharma_swarm.diff_applier import parse_unified_diff
from dharma_swarm.promotion_gate import SEALED_PACKET_BLOCKED_PATHS as _SEALED_PACKET_BLOCKED_PATHS
from dharma_swarm.evolution import (
    EvidenceTier,
    EvolutionStatus,
    Proposal,
    SandboxResult,
    SealedPacketApplyResult,
)
from dharma_swarm.traces import TraceEntry


async def apply_sealed_packet(
    engine: Any,
    dryrun_root: Path,
    *,
    shadow: bool = True,
    workspace: Path | None = None,
    proof_timeout: float = 120.0,
    max_diff_lines: int = 50,
    halt_path: Path | None = None,
    promotion_verification: dict[str, Any] | None = None,
    trusted_judge_public_keys: Iterable[str | bytes] = (),
) -> SealedPacketApplyResult:
    """Validate, gate, prove, and archive a sealed Build Protocol packet."""
    root = Path(dryrun_root).expanduser().resolve()
    result = SealedPacketApplyResult(packet_root=str(root), shadow=shadow)
    if not shadow:
        from dharma_swarm.promotion_gate import _promotion_verification_allows_live

        if not _promotion_verification_allows_live(
            promotion_verification,
            trusted_judge_public_keys=trusted_judge_public_keys,
        ):
            return await _refuse_sealed_packet(
                engine,
                result,
                "live apply requires forge_v2.verify_promotion packet",
                "promotion_verification",
            )
    stop_file = halt_path or (Path.home() / ".dharma" / "HALT_DARWIN_PROPOSALS")
    if Path(stop_file).exists():
        return await _refuse_sealed_packet(engine, result, "halt switch present", "kill_switch")

    required = {
        "build_packet": root / "build_packet.json",
        "review_packet": root / "review_packet.json",
        "proof_packet": root / "proof_packet.json",
    }
    missing = [name for name, candidate in required.items() if not candidate.is_file()]
    if missing:
        return await _refuse_sealed_packet(
            engine,
            result,
            f"missing packet files: {', '.join(missing)}",
            "packet_shape",
        )

    try:
        build_packet = _read_packet_json(required["build_packet"])
        review_packet = _read_packet_json(required["review_packet"])
        proof_packet = _read_packet_json(required["proof_packet"])
    except (OSError, json.JSONDecodeError) as exc:
        return await _refuse_sealed_packet(
            engine,
            result,
            f"invalid packet json: {exc}",
            "packet_json",
        )

    proof_payload = dict(proof_packet.get("payload") or {})
    if proof_payload.get("merge_decision") != "seal":
        return await _refuse_sealed_packet(
            engine,
            result,
            "proof packet merge_decision is not seal",
            "proof_seal",
        )

    gate_failures = _sealed_packet_gate_failures(review_packet, proof_payload)
    if gate_failures:
        return await _refuse_sealed_packet(
            engine,
            result,
            "sealed packet gate results are not all pass",
            gate_failures,
        )

    build_meta = dict(build_packet.get("metadata") or {})
    work_packet = _load_sealed_work_packet(root, proof_payload)
    allowed_paths = _sealed_packet_allowed_paths(build_meta, work_packet)
    proof_command = _sealed_packet_proof_command(root, build_meta, work_packet)
    if not proof_command:
        return await _refuse_sealed_packet(engine, result, "missing proof command", "proof_command")

    diff_ref = str(dict(review_packet.get("metadata") or {}).get("diff_ref") or "")
    diff_text, diff_missing = _read_sealed_packet_diff(root, diff_ref, workspace)
    if diff_text:
        guard_failures, files_changed, diff_lines = _guard_sealed_packet_diff(
            diff_text,
            allowed_paths=allowed_paths,
            max_diff_lines=max_diff_lines,
        )
        result.files_changed = files_changed
        if guard_failures:
            return await _refuse_sealed_packet(
                engine,
                result,
                "sealed packet diff failed conservative guards",
                guard_failures,
            )
        if not shadow:
            authorized = {
                str(entry).strip()
                for entry in (dict(promotion_verification or {}).get("authorized_source_files") or [])
                if str(entry).strip()
            }
            unauthorized = [path for path in files_changed if path not in authorized]
            if unauthorized:
                return await _refuse_sealed_packet(
                    engine,
                    result,
                    "sealed packet diff touches files the promotion packet does not authorize",
                    [f"path_not_authorized_by_promotion:{path}" for path in unauthorized],
                )
    else:
        files_changed = []
        diff_lines = 0
        if not shadow:
            return await _refuse_sealed_packet(
                engine,
                result,
                "diff artifact missing for live apply",
                "diff_artifact",
            )

    description = str(
        build_packet.get("description")
        or build_meta.get("telos_statement")
        or "Apply sealed Build Protocol packet"
    )
    component = files_changed[0] if files_changed else _first_allowed_path(allowed_paths)
    proposal = Proposal(
        component=component or "sealed_packet",
        change_type="sealed_packet_shadow" if shadow else "sealed_packet",
        description=description,
        diff=diff_text,
        spec_ref=str(build_meta.get("spec_path") or root),
        requirement_refs=[str(build_packet.get("title") or root.name)],
        think_notes=(
            "Risk: bounded sealed-packet ingestion. "
            "Rollback: refuse or rollback via apply_diff_and_test. "
            "Alternatives considered: leave packet unconsumed, manual apply. "
            "Expected: auditable Darwin archive entry."
        ),
        evidence_tier=EvidenceTier.LOCAL.value,
        metadata={
            "sealed_packet_root": str(root),
            "build_protocol_version": build_meta.get("protocol_version", "v0"),
            "diff_ref": diff_ref,
            "diff_missing": diff_missing,
            "shadow": shadow,
        },
    )
    result.proposal_id = proposal.id

    await engine.gate_check(proposal)
    if proposal.status == EvolutionStatus.REJECTED:
        return await _refuse_sealed_packet(
            engine,
            result,
            proposal.gate_reason or "darwin gate rejected sealed packet",
            "darwin_gate",
            proposal_id=proposal.id,
        )

    proof_result = await _run_sealed_packet_proof(
        proof_command,
        cwd=(Path(workspace).resolve() if workspace is not None else Path.cwd().resolve()),
        timeout=proof_timeout,
    )
    result.proof_exit_code = int(proof_result["exit_code"])
    if result.proof_exit_code != 0:
        result.test_results = proof_result
        return await _refuse_sealed_packet(
            engine,
            result,
            "fresh proof command failed",
            "fresh_proof",
            proposal_id=proposal.id,
        )

    test_results: dict[str, Any] = {
        "pass_rate": engine._parse_sandbox_result(
            SandboxResult(
                stdout=str(proof_result.get("stdout") or ""),
                stderr=str(proof_result.get("stderr") or ""),
                exit_code=result.proof_exit_code,
            )
        )["pass_rate"],
        "exit_code": result.proof_exit_code,
        "sealed_packet": {
            "root": str(root),
            "shadow": shadow,
            "proof_command": proof_command,
            "fresh_proof": proof_result,
            "files_changed": files_changed,
            "diff_lines": diff_lines,
            "diff_missing": diff_missing,
        },
    }

    if shadow:
        await engine.evaluate(proposal, test_results=test_results)
        result.archive_entry_id = await engine.archive_result(proposal)
        result.accepted = True
        result.applied = False
        result.reason = "sealed packet archived in shadow mode"
        result.test_results = dict(proposal.test_results)
        return result

    proposal, apply_results = await engine.apply_diff_and_test(
        proposal,
        test_command=proof_command,
        timeout=proof_timeout,
        workspace=workspace,
    )
    test_results.update(apply_results)
    test_results["sealed_packet"]["live_apply"] = dict(apply_results)
    await engine.evaluate(proposal, test_results=test_results)
    result.archive_entry_id = await engine.archive_result(proposal)
    result.accepted = True
    result.applied = (
        not bool(apply_results.get("rolled_back"))
        and float(apply_results.get("pass_rate", 0.0) or 0.0) >= 1.0
    )
    result.reason = (
        "sealed packet applied and archived"
        if result.applied
        else "sealed packet archived after failed live apply"
    )
    result.test_results = dict(proposal.test_results)
    return result


def _read_packet_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _load_sealed_work_packet(root: Path, proof_payload: dict[str, Any]) -> dict[str, Any]:
    work_id = str(proof_payload.get("work_packet_id") or "wp_001")
    candidates = [root / "work_packets" / f"{work_id}.json"]
    candidates.extend(sorted((root / "work_packets").glob("*.json")))
    for candidate in candidates:
        if candidate.is_file():
            try:
                return _read_packet_json(candidate)
            except (OSError, json.JSONDecodeError):
                return {}
    return {}


def _sealed_packet_allowed_paths(
    build_meta: dict[str, Any],
    work_packet: dict[str, Any],
) -> list[str]:
    payload = dict(work_packet.get("payload") or {})
    values: list[Any] = []
    values.extend(payload.get("allowed_paths") or [])
    values.extend(work_packet.get("scope") or [])
    values.extend(build_meta.get("allowed_paths") or [])
    return [str(value).strip() for value in values if str(value).strip()]


def _sealed_packet_proof_command(
    root: Path,
    build_meta: dict[str, Any],
    work_packet: dict[str, Any],
) -> str:
    proof_file = root / "proof_command.txt"
    if proof_file.is_file():
        command = proof_file.read_text(encoding="utf-8").strip()
        if command:
            return command
    payload = dict(work_packet.get("payload") or {})
    scoped_tests = payload.get("scoped_tests") or []
    if scoped_tests:
        return str(scoped_tests[0]).strip()
    return str(build_meta.get("proof_command") or "").strip()


def _sealed_packet_gate_failures(
    review_packet: dict[str, Any],
    proof_payload: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    gate_results = dict(dict(review_packet.get("metadata") or {}).get("gate_results") or {})
    aggregate = dict(proof_payload.get("gate_results_aggregate") or {})
    if not gate_results and not aggregate:
        return ["gate_results_missing"]
    for gate, record in gate_results.items():
        result = str(dict(record or {}).get("result") or "").lower()
        if result != "pass":
            failures.append(f"review_gate:{gate}:{result or 'missing'}")
    for gate, record in aggregate.items():
        data = dict(record or {})
        if int(data.get("fail_count", 0) or 0) > 0:
            failures.append(f"proof_gate:{gate}:fail")
        if int(data.get("hold_count", 0) or 0) > 0:
            failures.append(f"proof_gate:{gate}:hold")
    return failures


def _resolve_packet_artifact(root: Path, ref: str, workspace: Path | None) -> Path | None:
    if not ref:
        return None
    candidate = Path(ref).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    roots = [root.resolve()]
    if workspace is not None:
        roots.append(Path(workspace).resolve())
    else:
        roots.append(Path.cwd().resolve())
    for allowed_root in roots:
        try:
            resolved.relative_to(allowed_root)
            return resolved
        except ValueError:
            continue
    return None


def _read_sealed_packet_diff(
    root: Path,
    diff_ref: str,
    workspace: Path | None,
) -> tuple[str, bool]:
    diff_path = _resolve_packet_artifact(root, diff_ref, workspace)
    if diff_path is None or not diff_path.is_file():
        return "", bool(diff_ref)
    return diff_path.read_text(encoding="utf-8"), False


def _guard_sealed_packet_diff(
    diff_text: str,
    *,
    allowed_paths: list[str],
    max_diff_lines: int,
) -> tuple[list[str], list[str], int]:
    failures: list[str] = []
    try:
        patches = parse_unified_diff(diff_text)
    except ValueError as exc:
        return [f"diff_parse:{exc}"], [], 0
    if not patches:
        return ["diff_parse:no_file_patches"], [], 0

    files_changed = [_normalise_packet_path(patch.target_path) for patch in patches]
    diff_lines = _count_diff_changed_lines(diff_text)
    if diff_lines > max_diff_lines:
        failures.append(f"diff_size:{diff_lines}>{max_diff_lines}")
    if not allowed_paths:
        failures.append("allowed_paths_missing")

    for path in files_changed:
        if not path or path.startswith("../") or "/../" in path:
            failures.append(f"path_escape:{path}")
            continue
        if _path_matches_any(path, _SEALED_PACKET_BLOCKED_PATHS):
            failures.append(f"blocked_path:{path}")
        elif allowed_paths and not _path_matches_any(path, allowed_paths):
            failures.append(f"outside_allowed_paths:{path}")
    return failures, files_changed, diff_lines


def _normalise_packet_path(path: str) -> str:
    return path.strip().replace("\\", "/").lstrip("/")


def _path_matches_any(path: str, patterns: list[str] | tuple[str, ...]) -> bool:
    clean_path = path.strip().replace("\\", "/").lstrip("/")
    for raw in patterns:
        pattern = str(raw).strip().replace("\\", "/").lstrip("/")
        if not pattern:
            continue
        if pattern.endswith("/**") and clean_path.startswith(pattern[:-3]):
            return True
        if any(ch in pattern for ch in "*?[") and fnmatch.fnmatch(clean_path, pattern):
            return True
        if clean_path == pattern or clean_path.startswith(pattern.rstrip("/") + "/"):
            return True
    return False


def _count_diff_changed_lines(diff_text: str) -> int:
    return sum(
        1
        for line in diff_text.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    )


def _first_allowed_path(allowed_paths: list[str]) -> str:
    for value in allowed_paths:
        path = value.strip().replace("\\", "/").lstrip("/")
        if path and not any(ch in path for ch in "*?["):
            return path.rstrip("/")
    return "sealed_packet"


async def _run_sealed_packet_proof(
    command: str,
    *,
    cwd: Path,
    timeout: float,
) -> dict[str, Any]:
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"proof command timed out after {timeout}s",
                "timed_out": True,
            }
        return {
            "exit_code": proc.returncode if proc.returncode is not None else -1,
            "stdout": stdout_bytes.decode(errors="replace"),
            "stderr": stderr_bytes.decode(errors="replace"),
            "timed_out": False,
        }
    except OSError as exc:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"failed to run proof command: {exc}",
            "timed_out": False,
        }


async def _refuse_sealed_packet(
    engine: Any,
    result: SealedPacketApplyResult,
    reason: str,
    checks: str | list[str],
    *,
    proposal_id: str | None = None,
) -> SealedPacketApplyResult:
    result.accepted = False
    result.applied = False
    result.reason = reason
    result.proposal_id = proposal_id or result.proposal_id
    result.refused_checks = [checks] if isinstance(checks, str) else list(checks)
    try:
        await engine.traces.log_entry(
            TraceEntry(
                agent="darwin_engine",
                action="apply_sealed_packet",
                state="refused",
                files_changed=list(result.files_changed),
                metadata={
                    "packet_root": result.packet_root,
                    "reason": result.reason,
                    "refused_checks": list(result.refused_checks),
                    "proposal_id": result.proposal_id,
                },
            )
        )
    except Exception:
        pass
    return result
