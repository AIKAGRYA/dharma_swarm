"""Foundry improvement receipts — the seven-link chain (``foundry_improvement.v1``).

A verified improvement is not a number the swarm asserts; it is a chain a third
party can follow. Each link is minted only when its evidence exists, and a
receipt is "externally confirmed" (ring 3) only once a link nobody in the swarm
controls is present (a merged PR or an independent-leaderboard record). The
stratified fields (domain / counterparty / value-risk / independence / transfer)
are what the One Wire guardian reads when counting quorum.

Runtime receipts live under ``~/.dharma/foundry/receipts/`` and never enter git
(CLAUDE.md: runtime receipts never enter git).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.foundry.artifacts import ArtifactReplayError, verify_lineage
from dharma_swarm.foundry.evaluator import canonical_digest

SCHEMA_VERSION = "foundry_improvement.v1"
_STATE_ROOT = Path.home() / ".dharma" / "foundry" / "receipts"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- link constructors (each returns a plain dict; absent links stay None) ---

def pre_registration_link(
    *, target_id: str, resolved_sha: str, tree_digest: str,
    baseline_metric: float, oracle_cmd: list[str], seed: int,
) -> dict[str, Any]:
    """Link 1: the sealed manifest, registered BEFORE the attempt (anti-Goodhart)."""
    body = {
        "target_id": target_id, "resolved_sha": resolved_sha,
        "tree_digest": tree_digest, "baseline_metric": baseline_metric,
        "oracle_cmd": oracle_cmd, "seed": seed, "registered_at": _utc_now_iso(),
    }
    return {"link": "pre_registration", **body, "digest": canonical_digest(body)}


def benchmark_link(
    *, baseline_metric: float, candidate_metric: float, runs: int,
    coefficient_of_variation: float, repro_cmd: list[str], isolation_level: str,
    isolation_proofs: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Link 2: the multi-run pre/post benchmark with variance + repro command."""
    delta = candidate_metric - baseline_metric
    body = {
        "baseline_metric": baseline_metric, "candidate_metric": candidate_metric,
        "delta": delta, "runs": runs,
        "coefficient_of_variation": coefficient_of_variation,
        "repro_cmd": repro_cmd, "isolation_level": isolation_level,
        "isolation_proofs": isolation_proofs or {},
        "measured_at": _utc_now_iso(),
    }
    return {"link": "benchmark", **body, "digest": canonical_digest(body)}


def disclosure_link(*, ai_assisted: bool = True, duplicate_checked: bool = True,
                    test_results: str = "", diff_sha256: str = "") -> dict[str, Any]:
    """Link 3: the mandatory AI-assist disclosure + duplicate-check evidence.

    ``diff_sha256`` pins the exact candidate payload the receipt is about, so
    a third party can match the receipt to the artifact byte-for-byte.
    """
    return {
        "link": "disclosure", "ai_assisted": ai_assisted,
        "duplicate_checked": duplicate_checked, "test_results": test_results,
        "diff_sha256": diff_sha256,
    }


def external_ci_link(*, url: str, status: str) -> dict[str, Any]:
    """Link 4: the target's own CI (independent infrastructure) result."""
    return {"link": "external_ci", "url": url, "status": status}


def merge_event_link(
    *, repo: str, pr_url: str, state: str, author: str, merged_by: str,
    merge_commit_sha: str, merged_at: str,
) -> dict[str, Any]:
    """Link 5: the merge event — ring 3 when ``merged_by != author``."""
    return {
        "link": "merge_event", "repo": repo, "pr_url": pr_url, "state": state,
        "author": author, "merged_by": merged_by,
        "merge_commit_sha": merge_commit_sha, "merged_at": merged_at,
        "independent": bool(merged_by and merged_by != author),
    }


def guardian_countersign_link(*, cycle_file: str, verified: bool) -> dict[str, Any]:
    """Link 6: the forge-measurement-guardian recheck + drift seal."""
    return {"link": "guardian_countersign", "cycle_file": cycle_file, "verified": verified}


def report_render_link(*, path: str, digest: str) -> dict[str, Any]:
    """Link 7: the rendered report card (pure function of the sealed receipt)."""
    return {"link": "report_render", "path": path, "digest": digest}


@dataclass
class StratifiedFields:
    """The One Wire quorum dimensions the guardian counts."""

    domain: str = "external_code_contribution"
    counterparty: str = ""
    value_risk: str = ""
    independence: str = ""
    transfer: str = ""


@dataclass
class FoundryReceipt:
    """A verified-improvement receipt that accretes its seven links over time."""

    receipt_id: str
    target_id: str
    candidate_id: str
    stratified: StratifiedFields = field(default_factory=StratifiedFields)
    pre_registration: dict[str, Any] | None = None
    benchmark: dict[str, Any] | None = None
    disclosure: dict[str, Any] | None = None
    external_ci: dict[str, Any] | None = None
    merge_event: dict[str, Any] | None = None
    guardian_countersign: dict[str, Any] | None = None
    report_render: dict[str, Any] | None = None
    schema_version: str = SCHEMA_VERSION
    created_at: str = field(default_factory=_utc_now_iso)
    sequence: int = 0
    prev_receipt_digest: str = ""
    artifact_lineage: dict[str, Any] | None = None

    _LINKS = (
        "pre_registration", "benchmark", "disclosure", "external_ci",
        "merge_event", "guardian_countersign", "report_render",
    )

    def links_present(self) -> tuple[str, ...]:
        return tuple(name for name in self._LINKS if getattr(self, name) is not None)

    def externally_confirmed(self) -> bool:
        """Ring 3: a merge by a non-author, or an independent-leaderboard record."""
        me = self.merge_event
        if me and me.get("state") == "MERGED" and me.get("independent"):
            return True
        ci = self.external_ci
        return bool(ci and ci.get("status") == "independent_record")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["links_present"] = list(self.links_present())
        data["externally_confirmed"] = self.externally_confirmed()
        return data

    def seal(self) -> str:
        return canonical_digest(self.to_dict())


def _safe_filename(receipt_id: str) -> str:
    """Filesystem/artifact-safe name: model ids can contain ':' or '/'
    (e.g. ``qwen3-coder-480b:free``) which GitHub artifact upload rejects.
    The receipt payload keeps the true ``receipt_id``; only the filename
    is sanitized.
    """
    return re.sub(r"[^A-Za-z0-9._-]", "-", receipt_id)


class ReceiptChainError(RuntimeError):
    """Receipt history is not safe to extend."""


@dataclass(frozen=True)
class ReceiptAudit:
    ok: bool
    total_receipts: int
    chained_receipts: int
    legacy_receipts: int
    latest_sequence: int
    latest_digest: str
    invalid_receipts: tuple[str, ...] = ()
    missing_artifacts: tuple[str, ...] = ()
    orphan_artifacts: tuple[str, ...] = ()
    duplicate_receipt_ids: tuple[str, ...] = ()
    non_authoritative_lineages: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _receipt_root(state_root: Path | None) -> Path:
    root = Path(state_root) if state_root is not None else _STATE_ROOT
    if root.name == "receipts":
        return root
    nested = root / "receipts"
    if nested.exists() or any(
        (root / marker).exists()
        for marker in ("artifacts", "targets", "live_eval", "service_state.json", "KILL.json")
    ):
        return nested
    return root


def _json_files(root: Path) -> list[Path]:
    return sorted(path for path in root.glob("*.json") if path.is_file())


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("receipt payload is not an object")
    return data


def _sequence_value(data: dict[str, Any]) -> int | None:
    raw = data.get("sequence", 0)
    if isinstance(raw, bool):
        return None
    try:
        value = int(raw or 0)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if value >= 0 else None


def _legacy_anchor(records: list[tuple[Path, dict[str, Any], int]]) -> str:
    legacy = [
        {
            "name": path.name,
            "content_digest": canonical_digest(data),
        }
        for path, data, sequence in records
        if sequence == 0
    ]
    return canonical_digest({"legacy_receipts": legacy}) if legacy else "genesis"


def _sealed_digest(data: dict[str, Any]) -> str:
    return canonical_digest({k: v for k, v in data.items() if k != "sealed_digest"})


@contextmanager
def _chain_lock(root: Path):
    """Serialize writers on macOS/Linux without making the lock an artifact."""
    import fcntl

    lock_path = root / ".receipt-chain.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _artifact_path(foundry_root: Path, raw: Any) -> Path:
    path = Path(str(raw))
    candidate = path.resolve() if path.is_absolute() else (foundry_root / path).resolve()
    try:
        candidate.relative_to(foundry_root.resolve())
    except ValueError as exc:
        raise ValueError(f"artifact path escapes state root: {raw}") from exc
    return candidate


@contextmanager
def _replay_base(
    foundry_root: Path,
    lineage: dict[str, Any],
    replay_roots: dict[str, Path] | None,
):
    target_id = str(lineage.get("target_id", ""))
    if replay_roots and target_id in replay_roots:
        yield Path(replay_roots[target_id])
        return
    checkout = foundry_root / "targets" / target_id
    resolved_sha = str(lineage.get("resolved_sha", ""))
    evolve_file = str(lineage.get("evolve_file", ""))
    if not (checkout / ".git").exists() or not resolved_sha or not evolve_file:
        yield None
        return
    try:
        proc = subprocess.run(
            ["git", "-C", str(checkout), "show", f"{resolved_sha}:{evolve_file}"],
            capture_output=True,
            timeout=30,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        yield None
        return
    with tempfile.TemporaryDirectory(prefix="foundry_audit_base_") as temp_root:
        base = Path(temp_root)
        target = base / evolve_file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(proc.stdout)
        yield base


def audit_receipts(
    state_root: Path,
    *,
    pending_receipt: dict[str, Any] | None = None,
    replay_roots: dict[str, Path] | None = None,
) -> ReceiptAudit:
    """Verify compatibility receipts, the append-only chain, and artifacts.

    Pre-v2 receipt filenames remain immutable compatibility inputs. Their
    ordered names/content form the genesis anchor for the new sequence chain;
    they are never rewritten in place.
    """
    supplied = Path(state_root)
    root = _receipt_root(supplied)
    loaded: list[tuple[Path, dict[str, Any], int]] = []
    invalid: list[str] = []
    for path in _json_files(root) if root.exists() else []:
        try:
            data = _load_json(path)
            sequence = _sequence_value(data)
            if sequence is None:
                invalid.append(f"{path.name}: malformed sequence")
                sequence = 0
            loaded.append((path, data, sequence))
        except (OSError, ValueError, TypeError) as exc:
            invalid.append(f"{path.name}: unreadable {type(exc).__name__}")

    pending_path = Path("<pending-receipt>")
    if pending_receipt is not None:
        loaded_with_pending = loaded + [(pending_path, pending_receipt, 0)]
    else:
        loaded_with_pending = loaded

    legacy = [(path, data, seq) for path, data, seq in loaded if seq == 0]
    chained = [(path, data, seq) for path, data, seq in loaded if seq > 0]
    chained.sort(key=lambda item: item[2])

    # Validate seals on legacy records that carried one. Older bare campaign
    # fixtures without a seal remain readable, but are visibly counted legacy.
    for path, data, _ in legacy:
        claimed = str(data.get("sealed_digest", ""))
        if claimed and claimed != _sealed_digest(data):
            invalid.append(f"{path.name}: legacy sealed_digest mismatch")

    expected_prev = _legacy_anchor(legacy)
    latest_sequence = 0
    latest_digest = expected_prev
    for expected_sequence, (path, data, sequence) in enumerate(chained, start=1):
        if sequence != expected_sequence:
            invalid.append(
                f"{path.name}: missing/out-of-order sequence "
                f"expected={expected_sequence} actual={sequence}"
            )
        if str(data.get("prev_receipt_digest", "")) != expected_prev:
            invalid.append(f"{path.name}: prev_receipt_digest mismatch")
        claimed = str(data.get("sealed_digest", ""))
        actual = _sealed_digest(data)
        if not claimed or claimed != actual:
            invalid.append(f"{path.name}: sealed_digest mismatch")
        filename_prefix = path.name.split("__", 1)[0]
        if filename_prefix.isdigit() and int(filename_prefix) != sequence:
            invalid.append(f"{path.name}: filename sequence mismatch")
        expected_prev = claimed or actual
        latest_sequence = max(latest_sequence, sequence)
        latest_digest = expected_prev

    counts = Counter(str(data.get("receipt_id", "")) for _, data, _ in loaded_with_pending)
    duplicate_ids = sorted(receipt_id for receipt_id, count in counts.items() if receipt_id and count > 1)

    foundry_root = root.parent if root.name == "receipts" else supplied
    artifacts_root = foundry_root / "artifacts"
    referenced: set[Path] = set()
    missing: list[str] = []
    non_authoritative: list[str] = []
    known_lineages: dict[str, tuple[str, str]] = {}
    for path, data, _ in loaded_with_pending:
        lineage = data.get("artifact_lineage") or {}
        lineage_paths = [
            lineage.get("cumulative_artifact"),
            lineage.get("delta_artifact"),
            lineage.get("manifest_path"),
        ]
        sha = str((data.get("disclosure") or {}).get("diff_sha256", ""))
        if sha and not lineage_paths[0]:
            lineage_paths.append(f"artifacts/{sha}.patch")
        for raw in lineage_paths:
            if not raw:
                continue
            try:
                candidate = _artifact_path(foundry_root, raw)
            except ValueError as exc:
                invalid.append(f"{path.name}: {exc}")
                continue
            referenced.add(candidate.resolve())
            if not candidate.is_file():
                missing.append(f"{path.name}: {candidate}")

        schema = str(lineage.get("schema_version", ""))
        if schema and schema != "foundry_artifact_lineage.v1":
            non_authoritative.append(f"{path.name}: {schema}")
        if schema != "foundry_artifact_lineage.v1":
            continue
        try:
            cumulative = _artifact_path(foundry_root, lineage["cumulative_artifact"])
            delta = _artifact_path(foundry_root, lineage["delta_artifact"])
            manifest_path = _artifact_path(foundry_root, lineage["manifest_path"])
            if cumulative.is_file() and hashlib.sha256(cumulative.read_bytes()).hexdigest() != lineage.get("cumulative_sha256"):
                invalid.append(f"{path.name}: cumulative artifact sha256 mismatch")
            if delta.is_file() and hashlib.sha256(delta.read_bytes()).hexdigest() != lineage.get("delta_sha256"):
                invalid.append(f"{path.name}: delta artifact sha256 mismatch")
            if manifest_path.is_file():
                manifest = _load_json(manifest_path)
                if manifest != lineage:
                    invalid.append(f"{path.name}: manifest differs from embedded lineage")
            parent_sha = str(lineage.get("parent_artifact_sha256", ""))
            parent_tree = str(lineage.get("parent_candidate_tree_digest", ""))
            if parent_sha:
                known_parent = known_lineages.get(parent_sha)
                if known_parent is None:
                    invalid.append(f"{path.name}: parent artifact not in prior receipt lineage")
                elif known_parent[1] != parent_tree:
                    invalid.append(f"{path.name}: parent candidate tree digest mismatch")
            elif parent_tree:
                invalid.append(f"{path.name}: parent tree declared without parent artifact")
            if cumulative.is_file() and delta.is_file():
                with _replay_base(foundry_root, lineage, replay_roots) as base:
                    if base is None:
                        invalid.append(f"{path.name}: lineage replay base unavailable")
                    else:
                        try:
                            verify_lineage(
                                base,
                                lineage,
                                artifact_path=cumulative,
                                delta_path=delta,
                                expected_parent_artifact_sha256=parent_sha,
                            )
                        except ArtifactReplayError as exc:
                            invalid.append(f"{path.name}: {exc}")
            cumulative_sha = str(lineage.get("cumulative_sha256", ""))
            if cumulative_sha:
                known_lineages[cumulative_sha] = (
                    str(lineage.get("target_id", data.get("target_id", ""))),
                    str(lineage.get("candidate_tree_digest", "")),
                )
        except (KeyError, OSError, ValueError, TypeError) as exc:
            invalid.append(f"{path.name}: invalid lineage {type(exc).__name__}")

    on_disk = {
        path.resolve()
        for pattern in ("*.patch", "*.json")
        for path in artifacts_root.rglob(pattern)
        if path.is_file()
    } if artifacts_root.is_dir() else set()
    orphan = sorted(str(path) for path in on_disk - referenced)
    problems = bool(invalid or missing or orphan or duplicate_ids or non_authoritative)
    return ReceiptAudit(
        ok=not problems,
        total_receipts=len(loaded),
        chained_receipts=len(chained),
        legacy_receipts=len(legacy),
        latest_sequence=latest_sequence,
        latest_digest=latest_digest,
        invalid_receipts=tuple(sorted(set(invalid))),
        missing_artifacts=tuple(sorted(set(missing))),
        orphan_artifacts=tuple(orphan),
        duplicate_receipt_ids=tuple(duplicate_ids),
        non_authoritative_lineages=tuple(sorted(set(non_authoritative))),
    )


def verify_receipt_chain(state_root: Path) -> tuple[bool, str]:
    audit = audit_receipts(state_root)
    if not audit.ok:
        details = (
            list(audit.invalid_receipts)
            + list(audit.missing_artifacts)
            + list(audit.orphan_artifacts)
            + [f"duplicate receipt_id: {item}" for item in audit.duplicate_receipt_ids]
            + list(audit.non_authoritative_lineages)
        )
        return False, "; ".join(details)
    return True, (
        f"chain intact over {audit.chained_receipts} append-only receipts "
        f"({audit.legacy_receipts} compatibility receipts)"
    )


def quarantine_legacy_state(state_root: Path, *, apply: bool = False) -> dict[str, Any]:
    """Plan or apply a lossless quarantine for pre-chain broken evidence.

    Chained receipts are never moved because doing so would rewrite history.
    The helper is intended for the known pre-v2 VPS state: missing-reference
    legacy receipts and orphan artifacts. Applying it leaves a durable
    ``QUARANTINE.json`` marker, so automation remains stopped until an operator
    reviews the manifest and explicitly clears the marker.
    """
    foundry_root = Path(state_root).resolve()
    audit = audit_receipts(foundry_root)
    if audit.ok:
        return {"needed": False, "applied": False, "moves": [], "audit": audit.to_dict()}
    if audit.chained_receipts:
        raise ReceiptChainError(
            "automatic quarantine refuses append-only chained receipts; manual repair required"
        )

    receipt_root = foundry_root / "receipts"
    receipt_names: set[str] = set()
    for detail in (
        list(audit.invalid_receipts)
        + list(audit.missing_artifacts)
        + list(audit.non_authoritative_lineages)
    ):
        name = detail.split(":", 1)[0]
        if name and name != "<pending-receipt>":
            receipt_names.add(name)

    # For duplicate legacy logical IDs, preserve the oldest and quarantine all
    # later copies. No append-only sequence exists yet, so filename order is
    # the only compatibility ordering available.
    seen_ids: set[str] = set()
    for path in _json_files(receipt_root) if receipt_root.exists() else []:
        try:
            receipt_id = str(_load_json(path).get("receipt_id", ""))
        except (OSError, ValueError, TypeError):
            continue
        if receipt_id and receipt_id in seen_ids:
            receipt_names.add(path.name)
        seen_ids.add(receipt_id)

    sources = [receipt_root / name for name in sorted(receipt_names)]
    sources += [Path(raw) for raw in audit.orphan_artifacts]
    unique_sources = sorted({path.resolve() for path in sources if path.exists()})
    moves = []
    for source in unique_sources:
        try:
            relative = source.relative_to(foundry_root)
        except ValueError as exc:
            raise ReceiptChainError(f"quarantine source escapes state root: {source}") from exc
        moves.append({
            "source": str(relative),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        })

    plan: dict[str, Any] = {
        "schema_version": "foundry_legacy_quarantine.v1",
        "needed": bool(moves),
        "applied": False,
        "moves": moves,
        "pre_audit": audit.to_dict(),
    }
    if not apply or not moves:
        return plan

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    quarantine_root = foundry_root / "quarantine" / stamp
    for entry in moves:
        source = foundry_root / entry["source"]
        destination = quarantine_root / entry["source"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ReceiptChainError(f"quarantine destination already exists: {destination}")
        source.replace(destination)
        entry["destination"] = str(destination.relative_to(foundry_root))

    plan["applied"] = True
    plan["applied_at"] = datetime.now(timezone.utc).isoformat()
    manifest = quarantine_root / "manifest.json"
    manifest_bytes = (json.dumps(plan, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_immutable_receipt_file(manifest, manifest_bytes)
    marker = foundry_root / "QUARANTINE.json"
    marker_payload = {
        "schema_version": "foundry_quarantine_marker.v1",
        "manifest": str(manifest.relative_to(foundry_root)),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "reason": "legacy evidence quarantined; operator review required",
    }
    _write_immutable_receipt_file(
        marker,
        (json.dumps(marker_payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return plan


def _write_immutable_receipt_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ReceiptChainError(f"refusing to overwrite immutable file: {path}") from exc


def write_receipt(
    receipt: FoundryReceipt,
    *,
    state_root: Path | None = None,
    lineage_base_root: Path | None = None,
) -> Path:
    """Append a uniquely named receipt; never overwrite prior evidence."""
    root = Path(state_root) if state_root is not None else _STATE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    with _chain_lock(root):
        pending = receipt.to_dict()
        replay_roots = (
            {receipt.target_id: Path(lineage_base_root)}
            if lineage_base_root is not None
            else None
        )
        audit = audit_receipts(
            root,
            pending_receipt=pending,
            replay_roots=replay_roots,
        )
        if not audit.ok:
            raise ReceiptChainError(
                "refusing to append while receipt/artifact audit is not clean: "
                + json.dumps(audit.to_dict(), sort_keys=True)
            )
        receipt.sequence = audit.latest_sequence + 1
        receipt.prev_receipt_digest = audit.latest_digest
        payload = receipt.to_dict()
        payload["sealed_digest"] = receipt.seal()
        digest_short = payload["sealed_digest"].removeprefix("sha256:")[:16]
        path = root / (
            f"{receipt.sequence:08d}__{_safe_filename(receipt.receipt_id)}"
            f"__{digest_short}.json"
        )
        # x-mode is the invariant: a stale clock, repeated candidate id, or
        # concurrent writer cannot overwrite an existing receipt.
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return path
