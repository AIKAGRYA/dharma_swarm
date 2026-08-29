#!/usr/bin/env python3
"""Run one candidate-bound Foundry refusal canary in a separate process.

The process can replay a patch and run its declared oracle in a hardened,
digest-pinned Docker invocation.  A clean oracle is still inconclusive: this
slice has no real Forge trial ledger, Docker-daemon attestation, or effect
authority, and therefore never emits a Foundry ``verified_evidence`` packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256  # noqa: E402
from dharma_swarm.foundry.evaluator import Candidate, candidate_digest  # noqa: E402
from dharma_swarm.foundry.runner_isolation import (  # noqa: E402
    IsolationPolicy,
    RunResult,
    resolve_docker_executable,
)
from dharma_swarm.governed_patch_evidence import (  # noqa: E402
    GovernedPatchEvidenceError,
    NativePatchBindings,
    load_candidate_bundle,
)
from scripts.runtime.governed_patch_verifier_common import (  # noqa: E402
    VerifierCustodyError,
    external_write_path,
    load_role_signing_principal,
    record_verifier_identity,
    verifier_identity,
    write_signed_process_receipt,
)
from scripts.runtime.governed_patch_foundry_workspace import (  # noqa: E402
    FoundryWorkspaceError,
    repo_snapshot,
    replay_candidate,
)

OUTPUT_SCHEMA = "dharma.governed_patch.foundry_verifier_output.v1"
EVIDENCE_SCHEMA = "dharma.governed_patch.foundry_process_evidence.v1"
_BINDING_FIELDS = (
    "mission_id",
    "task_id",
    "attempt_id",
    "lease_id",
    "packet_id",
    "correlation_id",
    "delivery_id",
    "proposal_id",
    "base_sha",
    "executor_agent_uid",
    "executor_run_id",
    "executor_process_boot_id",
)
_PERMANENT_BLOCKERS = (
    "foundry_trial_ledger_unavailable",
    "docker_cli_provenance_unattested",
    "container_cleanup_unattested",
    "ambient_home_exposed",
    "runtime_interpreter_unattested",
    "exclusive_private_key_custody_unproven",
    "candidate_authority_binding_unproven",
    "canonical_runtime_store_unproven",
    "durable_executor_parent_unobserved",
    "verifier_trust_root_unpinned",
    "ignored_release_paths_unobserved",
)
_MAX_DOCKER_BINARY_BYTES = 512 * 1024 * 1024


class FoundryVerifierError(RuntimeError):
    """One admitted no-effect verifier input or runtime fact is invalid."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("command", choices=("once",))
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--expected-bindings-json", required=True)
    parser.add_argument("--runtime-db", required=True)
    parser.add_argument("--receipt-root", required=True)
    parser.add_argument("--verifier-agent-uid", required=True)
    parser.add_argument("--verifier-run-id", required=True)
    parser.add_argument("--docker-image", required=True)
    return parser


def _expected_bindings(raw: str) -> NativePatchBindings:
    if type(raw) is not str or len(raw.encode("utf-8")) > 16 * 1024:
        raise FoundryVerifierError("expected bindings must be a bounded string")

    def reject_constant(value: str) -> None:
        raise FoundryVerifierError(f"non-finite binding value: {value}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise FoundryVerifierError("duplicate expected binding key")
            result[key] = value
        return result

    try:
        payload = json.loads(
            raw,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except (json.JSONDecodeError, TypeError) as exc:
        raise FoundryVerifierError("expected bindings are malformed JSON") from exc
    if type(payload) is not dict or tuple(sorted(payload)) != tuple(
        sorted(_BINDING_FIELDS)
    ):
        raise FoundryVerifierError("expected bindings do not have the closed shape")
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    if raw != canonical:
        raise FoundryVerifierError("expected bindings JSON is not canonical")
    try:
        return NativePatchBindings(**payload)
    except TypeError as exc:
        raise FoundryVerifierError("expected bindings are malformed") from exc


def _candidate_from_bundle(bundle) -> Candidate:
    try:
        payload = json.loads(bundle.candidate_bytes.decode("utf-8"))
        candidate = Candidate(**payload)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise FoundryVerifierError("verified Candidate cannot be reconstructed") from exc
    if (
        candidate_digest(candidate) != bundle.candidate_digest
        or candidate.diff.encode("utf-8") != bundle.diff_bytes
    ):
        raise FoundryVerifierError("verified Candidate snapshot binding changed")
    return candidate


def _docker_descriptor(executable: str) -> dict[str, Any]:
    if not executable:
        return {"resolved_path": "", "binary_sha256": "", "bounded": True}
    path = Path(executable)
    digest = hashlib.sha256()
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        )
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size <= 0
            or metadata.st_size > _MAX_DOCKER_BINARY_BYTES
        ):
            raise FoundryVerifierError("Docker executable exceeds provenance bounds")
        remaining = metadata.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                raise FoundryVerifierError("Docker executable provenance was truncated")
            digest.update(chunk)
            remaining -= len(chunk)
    except OSError as exc:
        raise FoundryVerifierError("Docker executable provenance is unreadable") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return {
        "resolved_path": executable,
        "binary_sha256": digest.hexdigest(),
        "bounded": True,
    }


def _process_observation(result: RunResult) -> dict[str, Any]:
    isolation_observation = result.to_dict()
    isolation_observation.pop("promotion_allowed", None)
    return {
        "exit_code": result.exit_code,
        "stdout_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
        "stdout_bytes": len(result.stdout.encode("utf-8")),
        "stderr_bytes": len(result.stderr.encode("utf-8")),
        "duration_s": result.duration_s,
        "timed_out": result.timed_out,
        "blocked": result.blocked,
        "blocked_reason": result.blocked_reason,
        "details": dict(result.details),
        "isolation_observation": isolation_observation,
        "promotion_capability_emitted": False,
    }


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    principal = load_role_signing_principal(
        required_env="DHARMA_FOUNDRY_VERIFIER_KEY_FILE",
        forbidden_env="DHARMA_VIBE_VERIFIER_KEY_FILE",
    )
    os.environ.pop("DHARMA_FOUNDRY_VERIFIER_KEY_FILE", None)
    bindings = _expected_bindings(args.expected_bindings_json)
    release_raw = os.environ.get("DHARMA_RELEASE_ROOT", "")
    expected_commit = os.environ.get("DHARMA_RUNTIME_EXPECTED_COMMIT", "")
    if not release_raw or not Path(release_raw).is_absolute():
        raise FoundryVerifierError("DHARMA_RELEASE_ROOT must be an absolute path")
    release_root = Path(release_raw).resolve(strict=True)
    if expected_commit != bindings.base_sha:
        raise FoundryVerifierError("admitted release commit does not match candidate base")
    if not Path(args.bundle_root).is_absolute():
        raise FoundryVerifierError("bundle root must be an absolute path")
    bundle_root = Path(args.bundle_root).resolve(strict=True)
    runtime_db = external_write_path(
        args.runtime_db,
        release_root=release_root,
        candidate_bundle_root=bundle_root,
        field="runtime DB",
    )
    receipt_root = external_write_path(
        args.receipt_root,
        release_root=release_root,
        candidate_bundle_root=bundle_root,
        field="receipt root",
    )
    scratch_root = external_write_path(
        receipt_root / "workspace",
        release_root=release_root,
        candidate_bundle_root=bundle_root,
        field="Foundry scratch root",
    )
    external_write_path(
        principal.key_path,
        release_root=release_root,
        candidate_bundle_root=bundle_root,
        field="Foundry signing key",
    )
    key_path = Path(principal.key_path).resolve(strict=True)
    if (
        runtime_db == receipt_root
        or runtime_db.is_relative_to(receipt_root)
        or receipt_root.is_relative_to(runtime_db)
        or key_path == runtime_db
        or key_path == receipt_root
        or key_path.is_relative_to(receipt_root)
        or receipt_root.is_relative_to(key_path)
        or scratch_root == runtime_db
        or scratch_root == key_path
        or scratch_root.is_relative_to(key_path)
        or key_path.is_relative_to(scratch_root)
    ):
        raise FoundryVerifierError(
            "runtime DB, receipt root, and Foundry signing key must be distinct"
        )
    if args.verifier_agent_uid == bindings.executor_agent_uid:
        raise FoundryVerifierError("Foundry verifier agent must differ from executor")
    before = repo_snapshot(release_root, expected_commit)
    bundle = load_candidate_bundle(
        bundle_root,
        args.bundle_sha256,
        repo_root=release_root,
        expected=bindings,
        accepted_base_sha=expected_commit,
    )
    identity = verifier_identity(
        mission_id=bindings.mission_id,
        task_id=bindings.task_id,
        correlation_id=bindings.correlation_id,
        proposal_id=bindings.proposal_id,
        candidate_digest=bundle.candidate_digest,
        executor_agent_uid=bindings.executor_agent_uid,
        executor_run_id=bindings.executor_run_id,
        verifier_agent_uid=args.verifier_agent_uid,
        verifier_run_id=args.verifier_run_id,
        role="foundry",
    )
    recorded = record_verifier_identity(
        identity,
        runtime_db=runtime_db,
        role="foundry",
        public_key=principal.public_key,
    )
    docker_executable = resolve_docker_executable()
    if docker_executable and Path(docker_executable).is_relative_to(release_root):
        raise FoundryVerifierError("Docker executable must be outside the release")
    policy = IsolationPolicy(
        docker_image=args.docker_image,
        docker_executable=docker_executable,
        allow_degraded=False,
    )
    docker_descriptor = _docker_descriptor(docker_executable)
    result, replay = replay_candidate(
        bundle,
        policy,
        scratch_parent=scratch_root,
    )
    if _docker_descriptor(docker_executable) != docker_descriptor:
        raise FoundryVerifierError("Docker executable changed during verification")
    after = repo_snapshot(release_root, expected_commit)
    candidate = _candidate_from_bundle(bundle)
    if before != after:
        raise FoundryVerifierError(
            "tracked/nonignored release state changed during verification"
        )
    command = {
        "schema": "dharma.governed_patch.foundry_command.v1",
        "candidate_bundle_sha256": bundle.bundle_sha256,
        "base_sha": bindings.base_sha,
        "authorized_source_path": bundle.authorized_source_path,
        "oracle_argv": list(bundle.oracle_argv),
        "docker_image": args.docker_image,
        "disposable_workspace_parent": str(receipt_root / "workspace"),
        "isolation_policy": asdict(policy),
        "docker_executable": docker_descriptor,
    }
    observed = _process_observation(result)
    blockers = list(_PERMANENT_BLOCKERS)
    if result.blocked or result.timed_out:
        blockers.append("strong_isolation_or_execution_incomplete")
    if result.exit_code != 0:
        blockers.append("oracle_nonzero_or_infrastructure_ambiguous")
    outcome = "foundry_inconclusive"
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "native_bindings": bindings.to_dict(),
        "candidate_bundle_sha256": bundle.bundle_sha256,
        "candidate_digest": bundle.candidate_digest,
        "diff_sha256": bundle.diff_sha256,
        "request_content_sha256": bundle.request_content_sha256,
        "source_sha256": bundle.source_sha256,
        "authorized_source_path": bundle.authorized_source_path,
        "release_before": before,
        "release_after": after,
        "replay": replay,
        "command": command,
        "verified_candidate_snapshot_digest": candidate_digest(candidate),
        "process_observation": observed,
        "trial_ledger_available": False,
        "forge_verified_evidence_emitted": False,
        "blockers": blockers,
        "repository_effect_authorized": False,
        "repository_effect_performed": False,
        "evidence_storage_effects_performed": True,
        "effect_observation_scope": "tracked_and_nonignored_release_paths",
        "effect_observation": "unchanged",
    }
    process_path, process_receipt = write_signed_process_receipt(
        receipt_root=receipt_root,
        role="foundry",
        identity=recorded,
        candidate_digest=bundle.candidate_digest,
        diff_sha256=bundle.diff_sha256,
        outcome=outcome,
        reasons=tuple(blockers),
        evidence=evidence,
        principal=principal,
    )
    return {
        "schema": OUTPUT_SCHEMA,
        "outcome": outcome,
        "candidate_digest": bundle.candidate_digest,
        "diff_sha256": bundle.diff_sha256,
        "verifier_agent_uid": args.verifier_agent_uid,
        "verifier_run_id": args.verifier_run_id,
        "verifier_public_key": principal.public_key,
        "process_receipt_path": str(process_path),
        "process_receipt_sha256": canonical_sha256(process_receipt),
        "repository_effect_authorized": False,
        "repository_effect_performed": False,
        "evidence_storage_effects_performed": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output = run_once(args)
    except (
        FoundryVerifierError,
        FoundryWorkspaceError,
        GovernedPatchEvidenceError,
        VerifierCustodyError,
        OSError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {
                    "schema": OUTPUT_SCHEMA,
                    "outcome": "refused",
                    "error_type": type(exc).__name__,
                    "repository_effect_authorized": False,
                    "repository_effect_performed": "unknown",
                    "evidence_storage_effects_performed": "unknown",
                    "effect_observation": "unknown",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
