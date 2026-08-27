#!/usr/bin/env python3
"""Emit candidate-bound, signed Vibe-unavailable evidence without effects.

This process deliberately has no scanner execution path.  It binds one frozen
candidate to a durable child identity and records that candidate-bound Vibe
Halt capability is unavailable.  Neither receipt is a promotion warrant, and
neither claims repository-effect authority.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.foundry.patches import write_immutable_beneath
from dharma_swarm.governed_patch_evidence import (
    GovernedPatchEvidenceError,
    NativePatchBindings,
    load_candidate_bundle,
)
from dharma_swarm.mission_control_verification import PATCH_VIBE_SCHEMA
from scripts.runtime.governed_patch_verifier_common import (
    SigningPrincipal,
    VerifierCustodyError,
    external_write_path,
    load_role_signing_principal,
    record_verifier_identity,
    sign_closed_payload,
    verifier_identity,
    write_signed_process_receipt,
)
from scripts.runtime.governed_patch_foundry_workspace import (
    FoundryWorkspaceError,
    repo_snapshot,
)

_VIBE_KEY_ENV = "DHARMA_VIBE_VERIFIER_KEY_FILE"
_FOUNDRY_KEY_ENV = "DHARMA_FOUNDRY_VERIFIER_KEY_FILE"
_RELEASE_ROOT_ENV = "DHARMA_RELEASE_ROOT"
_EXPECTED_COMMIT_ENV = "DHARMA_RUNTIME_EXPECTED_COMMIT"
_OUTPUT_SCHEMA = "dharma.governed_patch.vibe_verifier_output.v1"
_CAPABILITY_BLOCKER = "candidate_bound_vibe_capability_unavailable"
_PROCESS_BLOCKERS = (
    _CAPABILITY_BLOCKER,
    "ambient_home_exposed",
    "runtime_interpreter_unattested",
    "exclusive_private_key_custody_unproven",
    "candidate_authority_binding_unproven",
    "canonical_runtime_store_unproven",
    "durable_executor_parent_unobserved",
    "verifier_trust_root_unpinned",
    "ignored_release_paths_unobserved",
)
_BINDING_FIELDS = frozenset(
    {
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
    }
)
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,255}$")


class VibeVerifierError(RuntimeError):
    """The refusal verifier could not establish its exact evidence boundary."""


def _strict_object(raw: str) -> dict[str, Any]:
    """Parse one bounded, canonical, duplicate-free JSON object."""

    if type(raw) is not str:
        raise VibeVerifierError("expected bindings JSON is not a bounded string")
    try:
        encoded = raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise VibeVerifierError("expected bindings JSON is not valid UTF-8") from exc
    if len(encoded) > 16 * 1024:
        raise VibeVerifierError("expected bindings JSON is not a bounded string")

    def reject_constant(value: str) -> None:
        raise VibeVerifierError(f"non-finite JSON constant is forbidden: {value}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise VibeVerifierError(
                    f"duplicate expected bindings key is forbidden: {key}"
                )
            result[key] = value
        return result

    try:
        value = json.loads(
            raw,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except VibeVerifierError:
        raise
    except (ValueError, RecursionError, UnicodeError) as exc:
        raise VibeVerifierError("expected bindings JSON is malformed") from exc
    if type(value) is not dict or frozenset(value) != _BINDING_FIELDS:
        raise VibeVerifierError("expected bindings JSON does not have a closed shape")
    if any(type(value[field]) is not str for field in _BINDING_FIELDS):
        raise VibeVerifierError("expected binding values must be exact strings")
    try:
        canonical = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise VibeVerifierError("expected bindings JSON is not canonical JSON") from exc
    if raw != canonical:
        raise VibeVerifierError("expected bindings JSON must be canonical")
    return value


def _expected_bindings(raw: str) -> NativePatchBindings:
    try:
        return NativePatchBindings(**_strict_object(raw))
    except TypeError as exc:
        raise VibeVerifierError("expected bindings JSON is malformed") from exc


def _required_environment_path(name: str, *, directory: bool) -> Path:
    raw = os.environ.get(name, "").strip()
    if not raw:
        raise VibeVerifierError(f"{name} is required")
    path = Path(raw)
    if not path.is_absolute():
        raise VibeVerifierError(f"{name} must be an absolute path")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise VibeVerifierError(f"{name} is unavailable") from exc
    if directory and not resolved.is_dir():
        raise VibeVerifierError(f"{name} must name a directory")
    return resolved


def _validate_verifier_token(value: str, *, field: str) -> str:
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        raise VibeVerifierError(f"invalid {field}")
    return value


def _write_vibe_receipt(
    *,
    receipt_root: Path,
    candidate_digest: str,
    diff_sha256: str,
    verifier_agent_uid: str,
    verifier_run_id: str,
    executor_run_id: str,
    principal: SigningPrincipal,
) -> tuple[Path, str, dict[str, Any]]:
    """Write the exact signed capability-unavailable PATCH_VIBE receipt."""

    unsigned = {
        "schema": PATCH_VIBE_SCHEMA,
        "candidate_digest": candidate_digest,
        "diff_sha256": diff_sha256,
        "verifier": {
            "agent_uid": verifier_agent_uid,
            "run_id": verifier_run_id,
            "parent_run_id": executor_run_id,
        },
        "ran": False,
        "reported_outcome": "unchecked",
        "diff_bound": True,
        "calibration_only": False,
        "process": {
            "exit_code": -1,
            "timed_out": False,
            "output_limited": False,
        },
        "findings": [],
        "errors": [_CAPABILITY_BLOCKER],
        "blockers": [_CAPABILITY_BLOCKER],
    }
    signed = sign_closed_payload(
        unsigned,
        principal=principal,
        key_id="governed-patch-vibe-halt-verifier",
    )
    digest = canonical_sha256(signed)
    encoded = (
        json.dumps(signed, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    path = write_immutable_beneath(
        receipt_root,
        f"vibe_halt/evidence/{digest}.json",
        encoded,
    )
    return path, digest, signed


def _run_once(args: argparse.Namespace) -> dict[str, Any]:
    release_root = _required_environment_path(_RELEASE_ROOT_ENV, directory=True)
    expected_commit = os.environ.get(_EXPECTED_COMMIT_ENV, "")
    bindings = _expected_bindings(args.expected_bindings_json)
    if (
        not expected_commit
        or expected_commit != expected_commit.strip()
        or expected_commit != bindings.base_sha
    ):
        raise VibeVerifierError(
            f"{_EXPECTED_COMMIT_ENV} must exactly match the candidate base"
        )

    bundle_root = Path(args.bundle_root)
    if not bundle_root.is_absolute():
        raise VibeVerifierError("bundle root must be an absolute path")
    try:
        bundle_root = bundle_root.resolve(strict=True)
    except OSError as exc:
        raise VibeVerifierError("bundle root is unavailable") from exc
    verifier_agent_uid = _validate_verifier_token(
        args.verifier_agent_uid,
        field="verifier_agent_uid",
    )
    verifier_run_id = _validate_verifier_token(
        args.verifier_run_id,
        field="verifier_run_id",
    )

    try:
        principal = load_role_signing_principal(
            required_env=_VIBE_KEY_ENV,
            forbidden_env=_FOUNDRY_KEY_ENV,
        )
    finally:
        os.environ.pop(_VIBE_KEY_ENV, None)
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
    key_path = external_write_path(
        principal.key_path,
        release_root=release_root,
        candidate_bundle_root=bundle_root,
        field="Vibe signing key",
    )
    if (
        runtime_db == receipt_root
        or runtime_db.is_relative_to(receipt_root)
        or receipt_root.is_relative_to(runtime_db)
        or key_path == runtime_db
        or key_path == receipt_root
        or key_path.is_relative_to(receipt_root)
        or receipt_root.is_relative_to(key_path)
    ):
        raise VibeVerifierError(
            "runtime DB, receipt root, and Vibe signing key must be distinct"
        )
    if verifier_agent_uid == bindings.executor_agent_uid:
        raise VibeVerifierError("Vibe verifier agent must differ from executor agent")
    if verifier_run_id == bindings.executor_run_id:
        raise VibeVerifierError("Vibe verifier run must differ from executor run")

    release_before = repo_snapshot(release_root, expected_commit)
    candidate = load_candidate_bundle(
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
        candidate_digest=candidate.candidate_digest,
        executor_agent_uid=bindings.executor_agent_uid,
        executor_run_id=bindings.executor_run_id,
        verifier_agent_uid=verifier_agent_uid,
        verifier_run_id=verifier_run_id,
        role="vibe_halt",
    )
    recorded_identity = record_verifier_identity(
        identity,
        runtime_db=runtime_db,
        role="vibe_halt",
        public_key=principal.public_key,
    )
    vibe_path, vibe_sha256, _vibe_receipt = _write_vibe_receipt(
        receipt_root=receipt_root,
        candidate_digest=candidate.candidate_digest,
        diff_sha256=candidate.diff_sha256,
        verifier_agent_uid=verifier_agent_uid,
        verifier_run_id=verifier_run_id,
        executor_run_id=bindings.executor_run_id,
        principal=principal,
    )
    release_after = repo_snapshot(release_root, expected_commit)
    if release_before != release_after:
        raise VibeVerifierError("release Git state changed during Vibe verification")
    process_path, _process_receipt = write_signed_process_receipt(
        receipt_root=receipt_root,
        role="vibe_halt",
        identity=recorded_identity,
        candidate_digest=candidate.candidate_digest,
        diff_sha256=candidate.diff_sha256,
        outcome="vibe_inconclusive",
        reasons=_PROCESS_BLOCKERS,
        evidence={
            "native_bindings": bindings.to_dict(),
            "candidate_bundle_sha256": candidate.bundle_sha256,
            "vibe_receipt_sha256": vibe_sha256,
            "release_before": release_before,
            "release_after": release_after,
            "ran": False,
            "reported_outcome": "unchecked",
            "diff_bound": True,
            "calibration_only": False,
            "ambient_home_present": bool(os.environ.get("HOME", "").strip()),
            "runtime_interpreter_attested": False,
            "exclusive_private_key_custody_proven": False,
            "repository_effect_authorized": False,
            "repository_effect_performed": False,
            "evidence_storage_effects_performed": True,
            "effect_observation_scope": "tracked_and_nonignored_release_paths",
            "effect_observation": "unchanged",
        },
        principal=principal,
    )
    output = {
        "schema": _OUTPUT_SCHEMA,
        "outcome": "vibe_inconclusive",
        "candidate_digest": candidate.candidate_digest,
        "diff_sha256": candidate.diff_sha256,
        "verifier_agent_uid": verifier_agent_uid,
        "verifier_run_id": verifier_run_id,
        "verifier_public_key": principal.public_key,
        "vibe_receipt_path": str(vibe_path),
        "vibe_receipt_sha256": vibe_sha256,
        "process_receipt_path": str(process_path),
        "process_receipt_sha256": process_path.stem,
        "repository_effect_authorized": False,
        "repository_effect_performed": False,
        "evidence_storage_effects_performed": True,
    }
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="governed-patch-vibe-verifier",
        description="Record candidate-bound Vibe capability unavailability.",
        allow_abbrev=False,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    once = commands.add_parser("once", allow_abbrev=False)
    once.add_argument("--bundle-root", required=True)
    once.add_argument("--bundle-sha256", required=True)
    once.add_argument("--expected-bindings-json", required=True)
    once.add_argument("--runtime-db", required=True)
    once.add_argument("--receipt-root", required=True)
    once.add_argument("--verifier-agent-uid", required=True)
    once.add_argument("--verifier-run-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command != "once":
            raise VibeVerifierError("unsupported verifier command")
        output = _run_once(args)
    except (
        FoundryWorkspaceError,
        GovernedPatchEvidenceError,
        VerifierCustodyError,
        VibeVerifierError,
        OSError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {
                    "schema": _OUTPUT_SCHEMA,
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
    print(
        json.dumps(
            output,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
