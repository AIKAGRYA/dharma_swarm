# spine: writes EvidenceReceipt
"""EvidenceReceipt — the one canonical artifact every dispatch attempt produces.

Designed to serialize cleanly to OpenTelemetry GenAI span attributes.
OTel is an EXPORT ADAPTER, not the truth surface. The receipt itself is
the canonical record.

See docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md §7 Fix 1.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

ReceiptStatus = Literal["ok", "failed", "dropped", "timeout", "cancelled"]

ErrorSource = Literal[
    "none",
    "task_missing",
    "runner_missing",
    "task_and_runner_missing",
    "claim_lost",
    "routing_failed",
    "provider_unreachable",
    "provider_failed",
    "guardrail_blocked",
    "cancelled",
    "timeout",
    "internal_error",
]


@dataclass(frozen=True, slots=True)
class EvidenceReceipt:
    """The one canonical artifact every dispatch attempt produces."""

    # Identity
    receipt_id: UUID = field(default_factory=uuid4)
    trace_id: str = ""
    span_id: str = ""
    parent_span_id: Optional[str] = None
    context_id: str = ""
    task_id: str = ""
    claim_id: Optional[str] = None
    claim_status: Optional[str] = None

    # What was invoked
    agent_id: str = ""
    agent_card_version: str = ""
    provider: str = ""
    model: str = ""
    operation: str = "invoke_agent"
    provider_attempted: bool = False

    # Outcome
    status: ReceiptStatus = "ok"
    error_source: ErrorSource = "none"
    error_detail: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    latency_ms: Optional[int] = None

    # Cost & tokens (OTel gen_ai.usage.*)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None

    # Routing trace
    routing_decision_id: Optional[UUID] = None

    # Free-form attributes
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_otel_span(self) -> dict[str, Any]:
        """Serialize as OTel GenAI span attributes."""
        attrs: dict[str, Any] = {
            "gen_ai.operation.name": self.operation,
            "gen_ai.system": self.provider,
            "gen_ai.request.model": self.model,
            "gen_ai.agent.id": self.agent_id,
            "dharma.context_id": self.context_id,
            "dharma.task_id": self.task_id,
            "dharma.agent_card_version": self.agent_card_version,
            "dharma.receipt_id": str(self.receipt_id),
            "dharma.status": self.status,
            "dharma.provider_attempted": self.provider_attempted,
            # Cross-layer identity alias: per the correlation_spine doctrine
            # (ACTIVE_SURFACE_MANIFEST.yaml), each closure layer has its own
            # canonical receipt but they must share a single correlation
            # identity. The A2A and closure_v0 layers call this field
            # ``correlation_id``; on the dispatch layer it is ``trace_id``.
            # Exporting both names keeps cross-layer joins trivial.
            "dharma.correlation_id": self.trace_id,
        }
        if self.input_tokens is not None:
            attrs["gen_ai.usage.input_tokens"] = self.input_tokens
        if self.output_tokens is not None:
            attrs["gen_ai.usage.output_tokens"] = self.output_tokens
        if self.cost_usd is not None:
            attrs["gen_ai.usage.cost_usd"] = self.cost_usd
        if self.error_source != "none":
            attrs["dharma.error_source"] = self.error_source
        if self.error_detail:
            attrs["dharma.error_detail"] = self.error_detail
        if self.claim_id:
            attrs["dharma.claim_id"] = self.claim_id
            attrs["dharma.claim_status"] = self.claim_status or ""
        if self.routing_decision_id:
            attrs["dharma.routing_decision_id"] = str(self.routing_decision_id)
        attrs.update({f"dharma.attr.{k}": v for k, v in self.attributes.items()})
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": f"invoke_agent {self.agent_id}",
            "start_time": self.started_at.isoformat(),
            "end_time": (
                self.finished_at.isoformat() if self.finished_at else None
            ),
            "attributes": attrs,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        d = asdict(self)
        d["receipt_id"] = str(self.receipt_id)
        d["started_at"] = self.started_at.isoformat()
        if self.finished_at:
            d["finished_at"] = self.finished_at.isoformat()
        if self.routing_decision_id:
            d["routing_decision_id"] = str(self.routing_decision_id)
        return d


# --- Verified machine receipt (Pudgala Autopoiesis Protostar Phase 1) ---------
# EvidenceReceipt proves a dispatch happened. It carries NO machine-execution
# fields (the command run, the tree state, the exit code), so it cannot bind a
# *claim* to *what actually ran*. VerifiedMachineReceipt is the sibling that
# does: a hash-chained record of one verified command execution. It is NOT a new
# receipt system — it is a typed projection persisted via the existing
# append-only + conflicting-digest pattern (memory_kernel.promotion_gate) and
# digested with the same canonical formula as memory_kernel.write_receipts. The
# governance gate (scripts/governance/check_track_status.py::check_receipt_valid)
# recomputes this digest to verify the receipt was not tampered.
#
# DEFAULT SINK is under ~/.dharma/ (runtime receipts never enter git — see
# CLAUDE.md "Runtime receipts never enter git").
DEFAULT_MACHINE_RECEIPT_PATH = (
    Path.home() / ".dharma" / "witness" / "claim_evidence_receipts.jsonl"
)
MACHINE_RECEIPT_SCHEMA_VERSION = "verified_machine_receipt.v1"


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _canonical_json(payload: object) -> str:
    # Byte-for-byte identical to memory_kernel.write_receipts.canonical_json and
    # to the verifier in check_track_status.py — the digest must match across all
    # three. Do not change one without the others.
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _stable_digest(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _read_verified_machine_receipt_chain(path: Path) -> list[dict[str, Any]]:
    """Read and verify every row of a machine-receipt JSONL chain."""
    rows: list[dict[str, Any]] = []
    prev_digest = ""
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"machine receipt log {path} line {line_number} is non-JSON"
            ) from exc
        if not isinstance(row, dict):
            raise ValueError(
                f"machine receipt log {path} line {line_number} is not a JSON object"
            )
        stored = str(row.get("digest", ""))
        recomputed = _stable_digest({k: v for k, v in row.items() if k != "digest"})
        if not stored or stored != recomputed:
            raise ValueError(
                f"machine receipt log {path} row {len(rows)} digest is broken; refusing to extend"
            )
        link = str(row.get("prev_digest", ""))
        if not rows and link:
            raise ValueError(
                f"machine receipt log {path} row 0 has non-empty prev_digest; refusing to extend"
            )
        if rows and link != prev_digest:
            raise ValueError(
                f"machine receipt log {path} row {len(rows)} prev_digest is broken; refusing to extend"
            )
        rows.append(row)
        prev_digest = stored
    return rows


@dataclass(frozen=True, slots=True)
class VerifiedMachineReceipt:
    """A hash-chained record of one verified command execution that backs a claim.

    PROV-O alignment is expressed in ``attributes`` (wasGeneratedBy /
    wasAttributedTo / wasDerivedFrom). The digest covers every field EXCEPT
    ``digest`` itself; ``prev_digest`` IS covered, so altering any prior receipt
    breaks every later link — the anti-slop tamper-evidence property.
    """

    claim_id: str = ""
    command: str = ""
    cwd: str = ""
    git_sha: str = ""
    git_dirty: bool = False
    actor: str = ""
    model: str = ""
    exit_code: Optional[int] = None
    stdout_stderr_hash: str = ""
    started_at: str = field(default_factory=_utc_now)
    finished_at: str = ""
    produced_at: str = field(default_factory=_utc_now)
    generated_by: str = ""
    verified_by: str = ""
    tool_versions: dict[str, str] = field(default_factory=dict)
    artifact_hashes: dict[str, str] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)
    schema_version: str = MACHINE_RECEIPT_SCHEMA_VERSION
    prev_digest: str = ""
    digest: str = ""

    def _payload(self) -> dict[str, Any]:
        """Every field except ``digest`` — the bytes the digest is taken over."""
        return {k: v for k, v in asdict(self).items() if k != "digest"}

    def with_chain(self, prev_digest: str = "") -> "VerifiedMachineReceipt":
        """Return a copy linked to ``prev_digest`` with a freshly-computed digest.
        Pass the previous receipt's ``digest`` to chain; "" begins a chain."""
        linked = replace(self, prev_digest=prev_digest or "", digest="")
        return replace(linked, digest=_stable_digest(linked._payload()))

    def verify(self) -> bool:
        """True iff the stored digest recomputes — i.e. the receipt is intact."""
        return bool(self.digest) and self.digest == _stable_digest(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX host (Windows)
    fcntl = None  # type: ignore[assignment]


@contextmanager
def _append_lock(target: Path):
    """Serialize the read-tail -> link -> write critical section.

    Without this the append was a lock-free read-modify-write: two concurrent
    appenders both read the same tail digest ``D``, both link to it, and the
    next read raises at the forked link -> the whole audit log is permanently
    unreadable (one racing append bricks every future read). An advisory
    ``flock`` on a sidecar lock file makes the section mutually exclusive.

    LIMIT: ``flock`` is advisory and host-local. It protects the single-host
    Mac-hub model (dozens of agents, one shared receipt path); it does NOT
    protect multi-container or NFS writers. On non-POSIX hosts (no ``fcntl``)
    this degrades to the previous lock-free behavior rather than failing."""
    if fcntl is None:  # pragma: no cover - non-POSIX host
        yield
        return
    lock_path = target.with_name(target.name + ".lock")
    with lock_path.open("w") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def append_machine_receipt(
    receipt: "VerifiedMachineReceipt",
    *,
    path: Path | None = None,
) -> "VerifiedMachineReceipt":
    """Append a chained VerifiedMachineReceipt to the JSONL log, linking it to
    the tail of the existing chain. Returns the chained-and-persisted receipt.

    Append-only with a tamper guard: if any existing row digest or chain link does
    not verify, we refuse to extend a broken chain. Mirrors the immutable-append
    discipline of memory_kernel.promotion_gate without minting a second receipt
    *system*.

    The read-tail -> link -> write section runs under an advisory file lock so
    concurrent appenders cannot fork the chain (see ``_append_lock``)."""
    target = (path or DEFAULT_MACHINE_RECEIPT_PATH).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    with _append_lock(target):
        prev_digest = ""
        if target.exists():
            rows = _read_verified_machine_receipt_chain(target)
            if rows:
                prev_digest = str(rows[-1].get("digest", ""))
        chained = receipt.with_chain(prev_digest)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(chained.to_dict()) + "\n")
    return chained
