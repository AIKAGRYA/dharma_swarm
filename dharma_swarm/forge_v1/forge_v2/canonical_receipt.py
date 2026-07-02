"""Workstream 1.2 -- canonical receipt normalization + replay/audit completeness.

The RSI v2.2 objective (Workstream 1, build task 2) requires *one canonical
receipt shape* covering six receipt kinds:

* swebench grade
* pr-suite grade
* scaffold evolution run
* code evolution run
* promotion refusal
* promotion success

with the done-when: "Every receipt has enough fields to replay or audit the
claim."

Each producer in ``forge_v2`` already emits its own richly-typed receipt
(``pr_suite_grader``, ``swebench_real``, ``phase4_alpha`` scaffold/code archive
rows, ``verify_promotion``).  Rewriting those producers to share one dataclass
would be invasive and risk weakening measurement code, so this module is a pure,
read-only *normalizer* instead: it maps any of the six source shapes onto one
canonical envelope and reports, per receipt, whether the fields required to
replay/audit that claim are present.

Design invariants:

* Pure and side-effect free apart from the explicit ``write_*`` helpers.
* Never trusts a model self-report: it only re-expresses fields the producers
  already recorded; it does not re-grade or re-decide anything.
* Never asserts promotion.  ``promotion_gate`` is always ``verify_promotion_only``
  and ``live_apply_allowed`` is always ``False`` in the canonical envelope; a
  promotion-success source receipt is normalized as *reporting* an allow
  decision, not as granting one here.
* Missing replay fields are reported as ``audit_complete=False`` with the exact
  missing field names -- never silently defaulted to look complete.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterable

from .signals import canonical_sha256

SCHEMA_VERSION = "forge_v2.canonical_receipt.v1"
PROMOTION_GATE = "verify_promotion_only"

# The six canonical receipt kinds named by Workstream 1.2.
KIND_SWEBENCH_GRADE = "swebench_grade"
KIND_PR_SUITE_GRADE = "pr_suite_grade"
KIND_SCAFFOLD_RUN = "scaffold_evolution_run"
KIND_CODE_RUN = "code_evolution_run"
KIND_PROMOTION_REFUSAL = "promotion_refusal"
KIND_PROMOTION_SUCCESS = "promotion_success"

CANONICAL_KINDS = frozenset(
    {
        KIND_SWEBENCH_GRADE,
        KIND_PR_SUITE_GRADE,
        KIND_SCAFFOLD_RUN,
        KIND_CODE_RUN,
        KIND_PROMOTION_REFUSAL,
        KIND_PROMOTION_SUCCESS,
    }
)

# Fields every canonical receipt must carry to be replayable/auditable at all.
_BASE_REPLAY_FIELDS = ("kind", "identity", "outcome", "evidence")

# Per-kind evidence fields required to replay/audit the specific claim.  These
# are the minimal inputs a reviewer needs to re-run or re-check the claim.
_KIND_REPLAY_FIELDS: dict[str, tuple[str, ...]] = {
    KIND_SWEBENCH_GRADE: ("instance_id", "resolved", "patch_sha256"),
    KIND_PR_SUITE_GRADE: ("task_id", "resolved", "fail_to_pass", "patch_sha256"),
    KIND_SCAFFOLD_RUN: ("candidate_id", "genome", "closeout"),
    KIND_CODE_RUN: ("candidate_id", "safety_decision", "patch_sha256"),
    KIND_PROMOTION_REFUSAL: ("decision", "blockers"),
    KIND_PROMOTION_SUCCESS: ("decision",),
}

# Evidence fields whose presence is satisfied even by falsey values (False / []).
_FALSEY_OK_FIELDS = frozenset({"resolved", "blockers", "fail_to_pass"})


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _first(mapping: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in mapping and mapping[name] not in (None, ""):
            return mapping[name]
    return default


def _sha_or_none(patch: Any) -> str | None:
    text = str(patch or "")
    if not text.strip():
        return None
    return canonical_sha256({"patch": text})


def audit_canonical_receipt(canonical: dict[str, Any]) -> dict[str, Any]:
    """Report whether a canonical receipt has the fields to replay/audit it.

    A field counts as present only when it is a key in the relevant section and
    its value is not ``None`` and not an empty string.  ``resolved``/``blockers``/
    ``fail_to_pass`` are special: a present ``False`` or ``[]`` is valid evidence.
    """
    kind = str(canonical.get("kind") or "")
    missing: list[str] = []
    for field_name in _BASE_REPLAY_FIELDS:
        value = canonical.get(field_name)
        if value in (None, ""):
            missing.append(field_name)
    evidence = canonical.get("evidence") if isinstance(canonical.get("evidence"), dict) else {}
    for field_name in _KIND_REPLAY_FIELDS.get(kind, ()):
        if field_name in _FALSEY_OK_FIELDS:
            present = field_name in evidence
        else:
            present = field_name in evidence and evidence.get(field_name) not in (None, "")
        if not present:
            missing.append(f"evidence.{field_name}")
    if kind not in CANONICAL_KINDS:
        missing.append(f"kind:{kind or 'unknown'}")
    return {"audit_complete": not missing, "missing_replay_fields": missing}


def _envelope(
    *,
    kind: str,
    identity: dict[str, Any],
    outcome: dict[str, Any],
    evidence: dict[str, Any],
    source_schema: str | None,
) -> dict[str, Any]:
    canonical = {
        "schema": SCHEMA_VERSION,
        "kind": kind,
        "generated_at": utc_now(),
        "identity": dict(identity),
        "outcome": dict(outcome),
        "evidence": dict(evidence),
        "source_schema": source_schema,
        # Normalization never grants authority; it only re-expresses evidence.
        "live_apply_allowed": False,
        "source_of_truth_mutated": False,
        "official_score_claimed": False,
        "promotion_gate": PROMOTION_GATE,
    }
    audit = audit_canonical_receipt(canonical)
    canonical["audit_complete"] = audit["audit_complete"]
    canonical["missing_replay_fields"] = audit["missing_replay_fields"]
    canonical["canonical_sha256"] = canonical_sha256(
        {k: v for k, v in canonical.items() if k != "canonical_sha256"}
    )
    return canonical


def from_swebench_grade(receipt: dict[str, Any]) -> dict[str, Any]:
    """Normalize a SWE-bench grade (``swebench_real``/native worker) receipt."""
    instance_id = str(_first(receipt, "instance_id", "task_id", default="") or "")
    resolved = receipt.get("resolved")
    evidence = {
        "instance_id": instance_id or None,
        "resolved": resolved,
        "patch_sha256": _first(receipt, "patch_sha256", default=_sha_or_none(receipt.get("model_patch"))),
        "swebench_run_id": _first(receipt, "swebench_run_id", "run_id"),
        "swebench_namespace": receipt.get("swebench_namespace"),
        "grade_seconds": receipt.get("grade_seconds"),
        "grade_error": receipt.get("grade_error"),
    }
    return _envelope(
        kind=KIND_SWEBENCH_GRADE,
        identity={"task_id": instance_id or None, "grader": _first(receipt, "grader", default="swebench")},
        outcome={"resolved": bool(resolved) if resolved is not None else None, "status": receipt.get("status")},
        evidence=evidence,
        source_schema=str(_first(receipt, "schema", default="") or "") or None,
    )


def from_pr_suite_grade(receipt: dict[str, Any]) -> dict[str, Any]:
    """Normalize a PR-suite grade (``pr_suite_grader``) receipt."""
    task_id = str(_first(receipt, "task_id", "instance_id", default="") or "")
    resolved = receipt.get("resolved")
    fail_to_pass = list(receipt.get("fail_to_pass") or [])
    evidence = {
        "task_id": task_id or None,
        "resolved": resolved,
        "fail_to_pass": fail_to_pass,
        "patch_sha256": _first(receipt, "patch_sha256", default=None),
        "repo": _first(receipt, "repo", "repository"),
        "resolved_refs": dict(receipt.get("resolved_refs") or {}),
        "grade_error": receipt.get("grade_error"),
        "blockers": list(receipt.get("blockers") or []),
        "validation_receipt": receipt.get("validation_receipt"),
    }
    return _envelope(
        kind=KIND_PR_SUITE_GRADE,
        identity={"task_id": task_id or None, "grader": "pr_suite"},
        outcome={"resolved": bool(resolved) if resolved is not None else None},
        evidence=evidence,
        source_schema=str(_first(receipt, "schema", default="") or "") or None,
    )


def _scaffold_payload(receipt: dict[str, Any]) -> dict[str, Any]:
    # Accept either the phase4 scaffold payload directly or an ArchiveEntry-style
    # row whose ``test_results`` holds that payload.
    if receipt.get("track") == "scaffold_genome" or "genome" in receipt:
        return receipt
    inner = receipt.get("test_results")
    return inner if isinstance(inner, dict) else receipt


def from_scaffold_run(receipt: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Track-A scaffold evolution run/archive receipt."""
    payload = _scaffold_payload(receipt)
    evaluation = dict(payload.get("evaluation") or {})
    evidence = {
        "candidate_id": _first(payload, "candidate_id", default=None),
        "genome": dict(payload.get("genome") or {}),
        "closeout": _first(evaluation, "closeout", default=payload.get("reason")),
        "task_results": dict(payload.get("task_results") or evaluation.get("task_results") or {}),
        "budget": dict(payload.get("budget") or evaluation.get("budget") or {}),
        "ci": dict(evaluation.get("ci") or {}),
        "receipt_links": list(payload.get("receipt_links") or []),
        "parent_id": payload.get("parent_id"),
        "mutation_description": payload.get("mutation_description"),
    }
    return _envelope(
        kind=KIND_SCAFFOLD_RUN,
        identity={
            "candidate_id": _first(payload, "candidate_id", default=None),
            "track": "scaffold_genome",
            "parent_id": payload.get("parent_id"),
        },
        outcome={"decision": payload.get("decision"), "closeout": evidence["closeout"]},
        evidence=evidence,
        source_schema=str(_first(payload, "schema", default="") or "") or None,
    )


def _code_payload(receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("track") == "code_child" or "safety_receipt" in receipt:
        return receipt
    inner = receipt.get("test_results")
    return inner if isinstance(inner, dict) else receipt


def from_code_run(receipt: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Track-B code evolution run/archive receipt."""
    payload = _code_payload(receipt)
    safety = dict(payload.get("safety_receipt") or {})
    evaluation = dict(payload.get("evaluation") or {})
    evidence = {
        "candidate_id": _first(payload, "candidate_id", default=None),
        "safety_decision": _first(safety, "decision", default=payload.get("safety_decision")),
        "patch_sha256": _first(safety, "patch_sha256", default=payload.get("patch_sha256")),
        "safety_blockers": list(safety.get("blockers") or []),
        "forbidden_hits": list(safety.get("forbidden_hits") or []),
        "semantic_weakening_findings": list(safety.get("semantic_weakening_findings") or []),
        "isolated_worktree": _first(safety, "isolated_worktree", default=payload.get("isolated_worktree")),
        "evaluation": evaluation,
        "receipt_links": list(payload.get("receipt_links") or []),
        "parent_id": payload.get("parent_id"),
        "mutation_description": payload.get("mutation_description"),
    }
    return _envelope(
        kind=KIND_CODE_RUN,
        identity={
            "candidate_id": _first(payload, "candidate_id", default=None),
            "track": "code_child",
            "parent_id": payload.get("parent_id"),
        },
        outcome={
            "decision": payload.get("decision"),
            "safety_decision": evidence["safety_decision"],
        },
        evidence=evidence,
        source_schema=str(_first(payload, "schema", default="") or "") or None,
    )


def from_promotion(receipt: dict[str, Any]) -> dict[str, Any]:
    """Normalize a ``verify_promotion`` verdict into refusal/success canonically.

    A verdict with ``decision == "allow"`` is a promotion success *report*; any
    other decision is a promotion refusal.  Either way the canonical envelope
    still carries ``live_apply_allowed=False`` because this module never grants
    authority; the source ``decision``/``live_apply_allowed`` is preserved inside
    ``outcome``/``evidence`` for audit.
    """
    decision = str(_first(receipt, "decision", default="") or "")
    is_success = decision == "allow"
    kind = KIND_PROMOTION_SUCCESS if is_success else KIND_PROMOTION_REFUSAL
    evidence = {
        "decision": decision or None,
        "blockers": list(receipt.get("blockers") or []),
        "source_live_apply_allowed": bool(receipt.get("live_apply_allowed", False)),
        "operator_lease_present": bool(receipt.get("operator_lease_present", False)),
        "signed_receipts": dict(receipt.get("signed_receipts") or {}),
        "payload_sha256": receipt.get("payload_sha256"),
        "promotion_packet_decision": (receipt.get("promotion_packet") or {}).get("decision"),
    }
    return _envelope(
        kind=kind,
        identity={
            "candidate_id": (receipt.get("promotion_packet") or {}).get("candidate_id"),
            "payload_sha256": receipt.get("payload_sha256"),
        },
        outcome={"decision": decision or None, "refused": not is_success},
        evidence=evidence,
        source_schema=str(_first(receipt, "schema", default="") or "") or None,
    )


_KIND_ADAPTERS = {
    KIND_SWEBENCH_GRADE: from_swebench_grade,
    KIND_PR_SUITE_GRADE: from_pr_suite_grade,
    KIND_SCAFFOLD_RUN: from_scaffold_run,
    KIND_CODE_RUN: from_code_run,
}


def infer_kind(receipt: dict[str, Any]) -> str | None:
    """Best-effort detection of a source receipt's canonical kind.

    Detection uses only structural fields the producers already emit, never a
    caller-provided ``kind`` label, so an untrusted receipt cannot mislabel
    itself into a weaker audit path.
    """
    schema = str(receipt.get("schema") or "")
    track = str(receipt.get("track") or "")
    inner = receipt.get("test_results") if isinstance(receipt.get("test_results"), dict) else {}
    inner_track = str(inner.get("track") or "")
    is_promotion = schema == "forge_v2.promotion_verification.v1" or (
        "decision" in receipt and "blockers" in receipt and "promotion_packet" in receipt
    )
    if is_promotion:
        return KIND_PROMOTION_SUCCESS if receipt.get("decision") == "allow" else KIND_PROMOTION_REFUSAL
    if track == "scaffold_genome" or inner_track == "scaffold_genome" or "genome" in receipt:
        return KIND_SCAFFOLD_RUN
    if track == "code_child" or inner_track == "code_child" or "safety_receipt" in receipt or "shadow_diff" in receipt:
        return KIND_CODE_RUN
    if "pr_suite" in schema or receipt.get("grader") == "pr_suite" or str(receipt.get("task_id") or "").startswith("pr::"):
        return KIND_PR_SUITE_GRADE
    if "swebench" in schema or receipt.get("grader") == "swebench" or "instance_id" in receipt:
        return KIND_SWEBENCH_GRADE
    return None


def normalize_receipt(receipt: dict[str, Any], *, kind: str | None = None) -> dict[str, Any]:
    """Normalize any supported source receipt into the canonical envelope."""
    if not isinstance(receipt, dict):
        raise TypeError("receipt must be a dict")
    resolved_kind = kind or infer_kind(receipt)
    if resolved_kind in (KIND_PROMOTION_REFUSAL, KIND_PROMOTION_SUCCESS):
        return from_promotion(receipt)
    adapter = _KIND_ADAPTERS.get(resolved_kind or "")
    if adapter is None:
        raise ValueError(f"unrecognized_receipt_kind: {resolved_kind!r}")
    return adapter(receipt)


def normalize_and_audit(receipt: dict[str, Any], *, kind: str | None = None) -> dict[str, Any]:
    canonical = normalize_receipt(receipt, kind=kind)
    audit = audit_canonical_receipt(canonical)
    return {"canonical": canonical, **audit}


def normalize_batch(receipts: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Normalize many receipts and summarize per-kind audit completeness."""
    canonical_rows: list[dict[str, Any]] = []
    unrecognized: list[dict[str, Any]] = []
    for index, receipt in enumerate(receipts):
        if not isinstance(receipt, dict):
            unrecognized.append({"index": index, "reason": "not_a_dict"})
            continue
        try:
            canonical_rows.append(normalize_receipt(receipt))
        except (ValueError, TypeError) as exc:
            unrecognized.append({"index": index, "reason": str(exc)})
    by_kind: dict[str, dict[str, int]] = {}
    complete = 0
    for row in canonical_rows:
        bucket = by_kind.setdefault(row["kind"], {"count": 0, "audit_complete": 0})
        bucket["count"] += 1
        if row.get("audit_complete"):
            bucket["audit_complete"] += 1
            complete += 1
    return {
        "schema": f"{SCHEMA_VERSION}.batch",
        "generated_at": utc_now(),
        "total": len(canonical_rows),
        "audit_complete_count": complete,
        "unrecognized": unrecognized,
        "by_kind": by_kind,
        "canonical_receipts": canonical_rows,
        "kinds": sorted(CANONICAL_KINDS),
        "source_of_truth_mutated": False,
        "promotion_gate": PROMOTION_GATE,
    }


def write_canonical_receipt(path: Path | str, receipt: dict[str, Any], *, kind: str | None = None) -> dict[str, Any]:
    """Normalize ``receipt`` and write the canonical envelope to ``path``."""
    canonical = normalize_receipt(receipt, kind=kind)
    out = Path(path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(canonical, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(out)
    return canonical


__all__ = [
    "CANONICAL_KINDS",
    "KIND_CODE_RUN",
    "KIND_PR_SUITE_GRADE",
    "KIND_PROMOTION_REFUSAL",
    "KIND_PROMOTION_SUCCESS",
    "KIND_SCAFFOLD_RUN",
    "KIND_SWEBENCH_GRADE",
    "PROMOTION_GATE",
    "SCHEMA_VERSION",
    "audit_canonical_receipt",
    "from_code_run",
    "from_promotion",
    "from_pr_suite_grade",
    "from_scaffold_run",
    "from_swebench_grade",
    "infer_kind",
    "normalize_and_audit",
    "normalize_batch",
    "normalize_receipt",
    "write_canonical_receipt",
]
