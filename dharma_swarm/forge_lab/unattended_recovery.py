"""Pre-spend recovery of parent-owned unattended scratch roots."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from dharma_swarm.forge_lab.state_io import content_digest, safe_json
from dharma_swarm.forge_lab.unattended_child_support import lexical_path
from dharma_swarm.forge_lab.unattended_policy import (
    RECEIPT_SCHEMA,
    RUNNER_SCHEMA,
    UnattendedError,
)
from dharma_swarm.forge_lab.unattended_scratch import (
    ScratchCustodyError,
    cleanup_run_scratch,
    list_run_scratch_ids,
    run_root,
    validate_parent_scratch_proofs,
    validate_scratch_proof,
)


def recover_stale_scratch(
    state_root: Path,
    control_root: Path,
    *,
    read_chain_fn: Callable[..., list[dict[str, Any]]],
    append_receipt_fn: Callable[[Path, dict[str, Any]], dict[str, Any]],
    now_fn: Callable[[], str],
) -> list[dict[str, Any]]:
    """Recover marker-bound prior roots before admission or reservation."""

    try:
        stale_run_ids = list_run_scratch_ids(state_root)
    except (ScratchCustodyError, ValueError) as exc:
        code = exc.code if isinstance(exc, ScratchCustodyError) else "SCRATCH_AUDIT_REFUSED"
        receipt = append_receipt_fn(
            control_root,
            {
                "kind": "stale_scratch_refusal",
                "at": now_fn(),
                "run_id": None,
                "error_code": code,
                "provider_calls": 0,
                "usd_reserved": 0.0,
                "epistemic_modality": "InconclusiveInfrastructure",
                "positive_rsi_claim": False,
            },
        )
        raise UnattendedError(
            "STALE_SCRATCH_REFUSED", receipt["receipt_digest"]
        ) from exc
    if not stale_run_ids:
        return []
    rows = read_chain_fn(
        control_root / "receipts.jsonl",
        schema=RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )
    recovered: list[dict[str, Any]] = []
    for stale_run_id in stale_run_ids:
        scratch_root = run_root(state_root, stale_run_id)
        spec_path = control_root / "runs" / stale_run_id / "child_spec.json"
        spec = None if spec_path.is_symlink() else safe_json(spec_path)
        spec_digest = (
            content_digest(
                {key: value for key, value in spec.items() if key != "spec_digest"}
            )
            if isinstance(spec, dict)
            else None
        )
        valid_spec = bool(
            isinstance(spec, dict)
            and spec.get("schema") == RUNNER_SCHEMA
            and spec.get("run_id") == stale_run_id
            and spec.get("positive_rsi_claim") is False
            and spec.get("spec_digest") == spec_digest
            and lexical_path(str(spec.get("state_root") or "")) == state_root
            and lexical_path(str(spec.get("scratch_root") or "")) == scratch_root
            and isinstance(spec.get("source_commit"), str)
        )
        admission_row = next(
            (
                row
                for row in reversed(rows)
                if row.get("kind") == "run_admitted"
                and row.get("run_id") == stale_run_id
                and row.get("spec") == str(spec_path)
                and row.get("spec_digest") == spec_digest
                and isinstance(row.get("scratch_custody_create"), dict)
            ),
            None,
        )
        create_proof = (
            admission_row.get("scratch_custody_create")
            if isinstance(admission_row, dict)
            else None
        )
        if not (
            valid_spec
            and isinstance(admission_row, dict)
            and admission_row.get("source_commit") == spec.get("source_commit")
            and validate_scratch_proof(
                create_proof,
                operation="create",
                scratch_root=scratch_root,
                run_id=stale_run_id,
            )
        ):
            refusal = append_receipt_fn(
                control_root,
                {
                    "kind": "stale_scratch_refusal",
                    "at": now_fn(),
                    "run_id": stale_run_id,
                    "error_code": "STALE_SCRATCH_AUTHORITY_MISSING",
                    "provider_calls": 0,
                    "usd_reserved": 0.0,
                    "epistemic_modality": "InconclusiveInfrastructure",
                    "positive_rsi_claim": False,
                },
            )
            raise UnattendedError(
                "STALE_SCRATCH_REFUSED",
                refusal["receipt_digest"],
            )
        try:
            cleanup = cleanup_run_scratch(
                state_root,
                stale_run_id,
                source_commit=str(spec["source_commit"]),
                spec_digest=str(spec_digest),
                expected_root_identity=create_proof["root_identity"],
                expected_marker_digest=str(create_proof["marker_digest"]),
            )
        except ScratchCustodyError as exc:
            refusal = append_receipt_fn(
                control_root,
                {
                    "kind": "stale_scratch_refusal",
                    "at": now_fn(),
                    "run_id": stale_run_id,
                    "error_code": exc.code,
                    "scratch_custody": {
                        "create": create_proof,
                        "cleanup": exc.proof,
                    },
                    "provider_calls": 0,
                    "usd_reserved": 0.0,
                    "epistemic_modality": "InconclusiveInfrastructure",
                    "positive_rsi_claim": False,
                },
            )
            raise UnattendedError(
                "STALE_SCRATCH_REFUSED",
                refusal["receipt_digest"],
            ) from exc
        if not validate_parent_scratch_proofs(
            create_proof,
            cleanup,
            state_root=state_root,
            run_id=stale_run_id,
        ):
            refusal = append_receipt_fn(
                control_root,
                {
                    "kind": "stale_scratch_refusal",
                    "at": now_fn(),
                    "run_id": stale_run_id,
                    "error_code": "STALE_SCRATCH_PROOF_CHAIN_INVALID",
                    "scratch_custody": {
                        "create": create_proof,
                        "cleanup": cleanup,
                    },
                    "provider_calls": 0,
                    "usd_reserved": 0.0,
                    "epistemic_modality": "InconclusiveInfrastructure",
                    "positive_rsi_claim": False,
                },
            )
            raise UnattendedError(
                "STALE_SCRATCH_REFUSED",
                refusal["receipt_digest"],
            )
        recovery = append_receipt_fn(
            control_root,
            {
                "kind": "stale_scratch_recovered",
                "at": now_fn(),
                "run_id": stale_run_id,
                "source_commit": spec["source_commit"],
                "spec": str(spec_path),
                "spec_digest": spec_digest,
                "scratch_custody": {
                    "create": create_proof,
                    "cleanup": cleanup,
                },
                "provider_calls": 0,
                "usd_reserved": 0.0,
                "epistemic_modality": "InconclusiveInfrastructureRecovery",
                "positive_rsi_claim": False,
            },
        )
        recovered.append(recovery)
    return recovered
