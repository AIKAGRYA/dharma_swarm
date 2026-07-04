#!/usr/bin/env python3
"""NĀGA-IR receipt emitter for the Sattva Assurance Boundary.

This module lifts each Assurance Boundary V0 contract (AB-01..AB-05) plus
one aggregating receipt into `dharma.naga_receipt.v1` wire records, per
the spec triple in `specs/naga_ir/` and the hand-off brief
`specs/naga_ir/IMPLEMENTATION_BRIEF_PR3.md`. It is stdlib-only, matching
the governance-surface law that binds `assurance_boundary.py`: no
third-party imports, no eval/exec/dynamic imports.

Q10 mapping (locked by the brief, reversible in code): one leaf receipt
per contract, five leaves total, plus one aggregate that binds them via
`evidence[0].params.leaf_receipt_hashes`. Six receipts per boundary run.

Canonicalization is a JCS approximation:
    json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
A strict RFC 8785 implementation is not available in the Python stdlib
and the wire spec (specs/naga_ir/receipt_wire.md) permits the
sort_keys+compact-separators subset as a v1-compatible canonical form.
Upgrading to full RFC 8785 (number normalization, Unicode escapes) is a
follow-up PR concern.

Signatures are dev-mode stubs of the shape
    {"alg": "ed25519", "key_id": "unsigned-dev-<host>",
     "sig": "sha256:<jcs_digest_over_signature_input>"}
The signature input is the canonicalized receipt with the `signatures`
field removed. Real ed25519 signing lands in a follow-up PR when key
material is provisioned; the receipt structure is unchanged.

The `challenge_base.base_snapshot_hash` is a documented placeholder
(`sha256:0000...`) until the witness mesh (PR #4+) exists to supply real
snapshot hashes.

Nothing here imports from `packages/telos-kernel/`, from
`dharma_swarm/*`, or from any third-party package. NĀGA-IR is not ETH
Nagini; no `nagini` import appears in this module.
"""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


NAGA_SCHEMA_VERSION = "dharma.naga_receipt.v1"
TRUST_BASE_ID_DEFAULT = "telos-kernel-tcb-v1"
FRAGMENT_ID_DEFAULT = "assurance-boundary-v0"
MESH_ID = "dharma-swarm-main"
EVIDENCE_HORIZON = "P14D"
TTL_DAYS = 14
CLOCK_UNCERTAINTY_MS = 500
MAX_CLOCK_SKEW_MS = 30000

PLACEHOLDER_SNAPSHOT_HASH = "sha256:" + "0" * 64

# Leaf contract metadata: contract_id -> (claim_body, method).
_CONTRACT_META: dict[str, tuple[str, str]] = {
    "AB-01": (
        "boundary_record_classes_frozen_and_versioned",
        "assurance_boundary_ab01_ast_static",
    ),
    "AB-02": (
        "no_silent_exception_swallow_in_boundary",
        "assurance_boundary_ab02_ast_static",
    ),
    "AB-03": (
        "no_fire_and_forget_asyncio_task_in_boundary",
        "assurance_boundary_ab03_ast_static",
    ),
    "AB-04": (
        "no_direct_provider_import_outside_runtime_provider",
        "assurance_boundary_ab04_ast_static",
    ),
    "AB-05": (
        "active_surface_manifest_layers_resolve",
        "assurance_boundary_ab05_ast_static",
    ),
}

_LEAF_ORDER: tuple[str, ...] = ("AB-01", "AB-02", "AB-03", "AB-04", "AB-05")


# ---------------------------------------------------------------------------
# Canonicalization + hashing
# ---------------------------------------------------------------------------


def _jcs_bytes(obj: Any) -> bytes:
    """JCS-approximation: sorted keys, compact separators, UTF-8.

    Not full RFC 8785 (no number renormalization, no Unicode escape
    rewriting), but a v1-compatible canonical subset per receipt_wire.md.
    """
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256_uri(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _hash_object(obj: Any) -> str:
    return _sha256_uri(_jcs_bytes(obj))


def _hash_bytes(data: bytes) -> str:
    return _sha256_uri(data)


# ---------------------------------------------------------------------------
# Boundary content hashing (stdlib-only substitute for git tree hash)
# ---------------------------------------------------------------------------


def _boundary_packages_union(packages: tuple[str, ...], modules: tuple[str, ...]) -> str:
    """Stable identifier for the union of boundary packages and modules."""
    return "|".join(list(packages) + list(modules))


def _boundary_content_hash(
    repo_root: Path, packages: tuple[str, ...], modules: tuple[str, ...]
) -> str:
    """Content hash across every .py file under the boundary.

    A git tree hash would be preferable but the stdlib cannot compute one
    without shelling out. We instead take SHA-256 over a sorted stream of
    (relative_path, file_sha256) pairs. Deterministic and dependency-free.
    """
    entries: list[tuple[str, str]] = []
    seen: set[Path] = set()
    for package in packages:
        root = repo_root / package
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            if path in seen:
                continue
            seen.add(path)
            try:
                data = path.read_bytes()
            except OSError:
                data = b""
            rel = path.relative_to(repo_root).as_posix()
            entries.append((rel, hashlib.sha256(data).hexdigest()))
    for module in modules:
        path = repo_root / module
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            data = path.read_bytes()
        except OSError:
            data = b""
        rel = path.relative_to(repo_root).as_posix()
        entries.append((rel, hashlib.sha256(data).hexdigest()))
    entries.sort()
    hasher = hashlib.sha256()
    for rel, digest in entries:
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(digest.encode("ascii"))
        hasher.update(b"\n")
    return "sha256:" + hasher.hexdigest()


def _module_git_sha(repo_root: Path) -> str:
    """Best-effort git SHA of this file. Falls back to content hash."""
    module_path = Path(__file__).resolve()
    try:
        rel = module_path.relative_to(repo_root).as_posix()
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", f"HEAD:{rel}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return "git:" + result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        return _hash_bytes(module_path.read_bytes())
    except OSError:
        return _sha256_uri(b"")


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def rfc3339_utc_now() -> str:
    """RFC 3339 UTC timestamp with `Z` suffix, millisecond precision."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _add_days_rfc3339(now_iso: str, days: int) -> str:
    ts = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    future = ts + timedelta(days=days)
    return future.isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Report shape adapter
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ContractOutcome:
    contract_id: str
    result: str  # "pass" or "fail"
    violations: tuple[str, ...]


def _contract_outcomes(report: Any) -> dict[str, _ContractOutcome]:
    """Extract per-contract pass/fail + violation text from a BoundaryReport.

    Accepts the `BoundaryReport` dataclass defined in
    `scripts/governance/assurance_boundary.py`. Duck-typed so tests can
    supply lightweight fakes.
    """
    outcomes: dict[str, _ContractOutcome] = {}
    measured = dict(getattr(report, "measured", {}) or {})
    hold = tuple(getattr(report, "hold_at_zero", ()) or ())

    for contract_id in ("AB-01", "AB-02", "AB-03"):
        items = tuple(measured.get(contract_id, ()) or ())
        # Measured contracts are ratchet-banked: they never fail this
        # gate on their own. The receipt records the observation.
        outcomes[contract_id] = _ContractOutcome(
            contract_id=contract_id,
            result="pass",
            violations=tuple(_render_violation(v) for v in items),
        )

    for contract_id in ("AB-04", "AB-05"):
        items = tuple(v for v in hold if getattr(v, "contract", None) == contract_id)
        outcomes[contract_id] = _ContractOutcome(
            contract_id=contract_id,
            result="fail" if items else "pass",
            violations=tuple(_render_violation(v) for v in items),
        )
    return outcomes


def _render_violation(violation: Any) -> str:
    render = getattr(violation, "render", None)
    if callable(render):
        return render()
    return str(violation)


# ---------------------------------------------------------------------------
# Receipt construction
# ---------------------------------------------------------------------------


def _deterministic_receipt_id(boundary_run_id: str, tag: str) -> str:
    """Derive a UUIDv5 receipt_id from the boundary run id and a tag.

    Deterministic so re-emitting the same boundary observation yields the
    same receipt id; makes tests reproducible without freezing time.
    """
    namespace = uuid.uuid5(uuid.NAMESPACE_URL, "dharma.naga_receipt.v1/boundary")
    return "urn:uuid:" + str(uuid.uuid5(namespace, f"{boundary_run_id}|{tag}"))


def _claim_object(contract_id: str, body: str) -> dict[str, Any]:
    return {
        "class": "contract",
        "id": contract_id,
        "body": body,
    }


def _authority_key(claim_hash: str, trust_base_id: str, fragment_id: str) -> str:
    return _hash_object(
        {
            "claim_hash": claim_hash,
            "trust_base_id": trust_base_id,
            "fragment_id": fragment_id,
        }
    )


def _signature_stub(receipt: dict[str, Any], key_id: str) -> dict[str, Any]:
    """Dev-mode signature stub over the JCS-approximation signing input."""
    unsigned = {k: v for k, v in receipt.items() if k != "signatures"}
    sig = _hash_bytes(_jcs_bytes(unsigned))
    return {"alg": "ed25519", "key_id": key_id, "sig": sig}


def _receipt_self_hash(receipt: dict[str, Any]) -> str:
    """SHA-256 hash URI of the fully canonicalized receipt (all fields)."""
    return _hash_bytes(_jcs_bytes(receipt))


def _build_leaf(
    *,
    contract_id: str,
    outcome: _ContractOutcome,
    boundary_run_id: str,
    now_utc_iso: str,
    trust_base_id: str,
    fragment_id: str,
    subject_id: str,
    subject_hash: str,
    boundary_packages: tuple[str, ...],
    boundary_modules: tuple[str, ...],
    python_version: str,
    module_version: str,
    prev_receipt_hash: str | None,
    key_id: str,
) -> dict[str, Any]:
    claim_body, method = _CONTRACT_META[contract_id]
    claim = _claim_object(contract_id, claim_body)
    claim_hash = _hash_object(claim)
    authority_key = _authority_key(claim_hash, trust_base_id, fragment_id)
    verdict_hash = _hash_object({"violations": list(outcome.violations)})
    receipt: dict[str, Any] = {
        "schema_version": NAGA_SCHEMA_VERSION,
        "receipt_id": _deterministic_receipt_id(boundary_run_id, contract_id),
        "subject": {
            "kind": "code-fragment",
            "id": subject_id,
            "hash": subject_hash,
        },
        "claim": claim,
        "claim_hash": claim_hash,
        "evidence": [
            {
                "modality": "Proven_by",
                "method": method,
                "params": {
                    "boundary_packages": list(boundary_packages),
                    "boundary_modules": list(boundary_modules),
                    "python_version": python_version,
                },
                "result": outcome.result,
                "verdict_hash": verdict_hash,
            }
        ],
        "authority": {
            "trust_base_id": trust_base_id,
            "fragment_id": fragment_id,
            "authority_key": authority_key,
        },
        "causal_origin": {
            "agent": "assurance_boundary",
            "version": module_version,
            "invocation": boundary_run_id,
            "agent_trace": None,
        },
        "epistemic_origin": {
            "trust_base_id": trust_base_id,
            "fragment_id": fragment_id,
            "verifier_pass": "assurance_boundary_v0",
        },
        "ttl": {
            "observed_at": now_utc_iso,
            "expires_at": _add_days_rfc3339(now_utc_iso, TTL_DAYS),
            "clock_uncertainty_ms": CLOCK_UNCERTAINTY_MS,
            "max_clock_skew_ms": MAX_CLOCK_SKEW_MS,
        },
        "challenge_base": {
            "mesh_id": MESH_ID,
            "query_key": authority_key,
            "evidence_horizon": EVIDENCE_HORIZON,
            "base_snapshot_hash": PLACEHOLDER_SNAPSHOT_HASH,
        },
        "challenge_state": {
            "authoritative": False,
            "unresolved_count": 0,
            "queried_at": now_utc_iso,
        },
        "prev_receipt_hash": prev_receipt_hash,
    }
    receipt["signatures"] = [_signature_stub(receipt, key_id)]
    return receipt


def _build_aggregate(
    *,
    leaves: list[dict[str, Any]],
    outcomes: dict[str, _ContractOutcome],
    boundary_run_id: str,
    now_utc_iso: str,
    trust_base_id: str,
    fragment_id: str,
    subject_id: str,
    subject_hash: str,
    module_version: str,
    prev_receipt_hash: str | None,
    key_id: str,
) -> dict[str, Any]:
    leaf_hashes = [_receipt_self_hash(leaf) for leaf in leaves]
    aggregate_pass = all(o.result == "pass" for o in outcomes.values())
    claim = _claim_object(
        "AB-AGG", "assurance_boundary_v0_holds_under_telos_kernel_tcb_v1"
    )
    claim_hash = _hash_object(claim)
    authority_key = _authority_key(claim_hash, trust_base_id, fragment_id)
    receipt: dict[str, Any] = {
        "schema_version": NAGA_SCHEMA_VERSION,
        "receipt_id": _deterministic_receipt_id(boundary_run_id, "AGGREGATE"),
        "subject": {
            "kind": "code-fragment",
            "id": subject_id,
            "hash": subject_hash,
        },
        "claim": claim,
        "claim_hash": claim_hash,
        "evidence": [
            {
                "modality": "Proven_by",
                "method": "assurance_boundary_aggregator",
                "params": {"leaf_receipt_hashes": leaf_hashes},
                "result": "pass" if aggregate_pass else "fail",
            }
        ],
        "authority": {
            "trust_base_id": trust_base_id,
            "fragment_id": fragment_id,
            "authority_key": authority_key,
        },
        "causal_origin": {
            "agent": "assurance_boundary",
            "version": module_version,
            "invocation": boundary_run_id,
            "agent_trace": None,
        },
        "epistemic_origin": {
            "trust_base_id": trust_base_id,
            "fragment_id": fragment_id,
            "verifier_pass": "assurance_boundary_v0",
        },
        "ttl": {
            "observed_at": now_utc_iso,
            "expires_at": _add_days_rfc3339(now_utc_iso, TTL_DAYS),
            "clock_uncertainty_ms": CLOCK_UNCERTAINTY_MS,
            "max_clock_skew_ms": MAX_CLOCK_SKEW_MS,
        },
        "challenge_base": {
            "mesh_id": MESH_ID,
            "query_key": authority_key,
            "evidence_horizon": EVIDENCE_HORIZON,
            "base_snapshot_hash": PLACEHOLDER_SNAPSHOT_HASH,
        },
        "challenge_state": {
            "authoritative": False,
            "unresolved_count": 0,
            "queried_at": now_utc_iso,
        },
        "prev_receipt_hash": prev_receipt_hash,
    }
    receipt["signatures"] = [_signature_stub(receipt, key_id)]
    return receipt


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def emit_boundary_receipts(
    report: Any,
    *,
    boundary_run_id: str,
    trust_base_id: str = TRUST_BASE_ID_DEFAULT,
    fragment_id: str = FRAGMENT_ID_DEFAULT,
    now_utc_iso: str,
    prev_receipt_hash: str | None = None,
    key_id: str = "unsigned-dev",
    repo_root: Path | None = None,
    boundary_packages: tuple[str, ...] | None = None,
    boundary_modules: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Emit six `dharma.naga_receipt.v1` receipts for one boundary run.

    Order: AB-01, AB-02, AB-03, AB-04, AB-05 (leaves), then the aggregate.
    The aggregate binds the five leaves via
    `evidence[0].params.leaf_receipt_hashes` and shares the caller's
    `prev_receipt_hash` (typically null for a first run).

    Q10 mapping (from IMPLEMENTATION_BRIEF_PR3.md §3): one leaf per
    contract plus one aggregate. Reversible in code if PR #4 discovers a
    different mapping is needed; the spec does not forbid the reverse.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]
    # Late import to avoid a circular import at module load time. Try
    # the package-qualified path first; fall back to a sibling module
    # when this file is loaded without `scripts` on sys.path.
    if boundary_packages is None or boundary_modules is None:
        try:
            from scripts.governance.assurance_boundary import (  # type: ignore
                BOUNDARY_MODULES,
                BOUNDARY_PACKAGES,
            )
        except ImportError:
            import sys as _sys_local

            _here = Path(__file__).resolve().parent
            if str(_here) not in _sys_local.path:
                _sys_local.path.insert(0, str(_here))
            from assurance_boundary import (  # type: ignore
                BOUNDARY_MODULES,
                BOUNDARY_PACKAGES,
            )

        if boundary_packages is None:
            boundary_packages = BOUNDARY_PACKAGES
        if boundary_modules is None:
            boundary_modules = BOUNDARY_MODULES

    outcomes = _contract_outcomes(report)
    subject_id = _boundary_packages_union(boundary_packages, boundary_modules)
    subject_hash = _boundary_content_hash(repo_root, boundary_packages, boundary_modules)
    module_version = _module_git_sha(repo_root)

    import sys as _sys

    python_version = _sys.version.split()[0]
    resolved_key_id = key_id
    if key_id == "unsigned-dev":
        try:
            resolved_key_id = f"unsigned-dev-{socket.gethostname() or 'unknown'}"
        except OSError:
            resolved_key_id = "unsigned-dev-unknown"

    leaves: list[dict[str, Any]] = []
    for contract_id in _LEAF_ORDER:
        leaves.append(
            _build_leaf(
                contract_id=contract_id,
                outcome=outcomes[contract_id],
                boundary_run_id=boundary_run_id,
                now_utc_iso=now_utc_iso,
                trust_base_id=trust_base_id,
                fragment_id=fragment_id,
                subject_id=subject_id,
                subject_hash=subject_hash,
                boundary_packages=boundary_packages,
                boundary_modules=boundary_modules,
                python_version=python_version,
                module_version=module_version,
                prev_receipt_hash=prev_receipt_hash,
                key_id=resolved_key_id,
            )
        )
    aggregate = _build_aggregate(
        leaves=leaves,
        outcomes=outcomes,
        boundary_run_id=boundary_run_id,
        now_utc_iso=now_utc_iso,
        trust_base_id=trust_base_id,
        fragment_id=fragment_id,
        subject_id=subject_id,
        subject_hash=subject_hash,
        module_version=module_version,
        prev_receipt_hash=prev_receipt_hash,
        key_id=resolved_key_id,
    )
    return leaves + [aggregate]


# ---------------------------------------------------------------------------
# Filesystem writer
# ---------------------------------------------------------------------------


def _boundary_run_short(boundary_run_id: str) -> str:
    """First 12 hex chars of the UUID inside `urn:uuid:...` for the filename."""
    stripped = boundary_run_id.replace("urn:uuid:", "")
    compact = stripped.replace("-", "")
    return compact[:12] if compact else "unknown"


def write_receipts_jsonl(
    receipts: list[dict[str, Any]],
    *,
    repo_root: Path,
    boundary_run_id: str,
    now_utc_iso: str,
) -> Path:
    """Write receipts to reports/naga_receipts/YYYY/MM/DD/boundary_<short>.jsonl.

    One receipt per line, aggregate last (caller's responsibility to pass
    them in that order — `emit_boundary_receipts` already does).
    """
    ts = datetime.fromisoformat(now_utc_iso.replace("Z", "+00:00"))
    dated_dir = (
        repo_root
        / "reports"
        / "naga_receipts"
        / f"{ts.year:04d}"
        / f"{ts.month:02d}"
        / f"{ts.day:02d}"
    )
    dated_dir.mkdir(parents=True, exist_ok=True)
    short = _boundary_run_short(boundary_run_id)
    out_path = dated_dir / f"boundary_{short}.jsonl"
    with out_path.open("w", encoding="utf-8") as fh:
        for receipt in receipts:
            fh.write(json.dumps(receipt, sort_keys=True, ensure_ascii=False))
            fh.write("\n")
    return out_path


__all__ = [
    "NAGA_SCHEMA_VERSION",
    "emit_boundary_receipts",
    "rfc3339_utc_now",
    "write_receipts_jsonl",
]
