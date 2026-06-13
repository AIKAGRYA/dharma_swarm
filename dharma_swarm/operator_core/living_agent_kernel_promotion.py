"""Promotion receipts for agents entering the LivingAgentKernel OS.

Promotion is the authority membrane between a persistent agent identity and
durable worker/provider execution.  It is deliberately receipt-backed and
separate from provider policy so promotion can be audited without booting a
provider or worker process.
"""

from __future__ import annotations

import fcntl
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from dharma_swarm.operator_core.living_agent_kernel import DEFAULT_KERNEL_RUN_DIR
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash, utc_now

KernelPromotionLevel = Literal["observer", "worker", "executor", "provider_executor"]
KernelPromotionStatus = Literal["promoted", "denied", "revoked"]
KernelPromotionDecision = Literal["allowed", "review", "blocked"]
KernelPromotionWorkKind = Literal[
    "read_only",
    "code_write",
    "long_running",
    "a2a_claim",
    "self_evolution",
    "promotion",
    "provider_execution",
]

_LEVEL_RANK: dict[str, int] = {
    "observer": 0,
    "worker": 1,
    "executor": 2,
    "provider_executor": 3,
}
_PROVIDER_EXECUTION_EVIDENCE_KINDS = {
    "holdout_eval_receipt",
    "operator_review",
    "provider_worker_receipt",
    "q3_context_quorum",
}


class KernelPromotionReceipt(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_promotion.v1"
    agent_uid: str
    level: KernelPromotionLevel = "observer"
    status: KernelPromotionStatus = "promoted"
    allowed_sources: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_work_kinds: list[KernelPromotionWorkKind] = Field(default_factory=list)
    max_lease_seconds: int = 300
    expires_at: str = ""
    reviewer: str = "operator"
    reason: str = ""
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)
    previous_record_hash: str = ""
    record_hash: str = ""


class KernelPromotionAdmission(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_promotion_admission.v1"
    decision: KernelPromotionDecision
    agent_uid: str
    requested_level: KernelPromotionLevel
    requested_source: str = ""
    requested_tools: list[str] = Field(default_factory=list)
    requested_work_kind: KernelPromotionWorkKind = "long_running"
    reasons: list[str] = Field(default_factory=list)
    promotion_ref: dict[str, Any] = Field(default_factory=dict)
    reduced_worker_authority: dict[str, Any] = Field(default_factory=dict)
    evaluated_at: str = Field(default_factory=utc_now)


class KernelPromotionStore:
    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir or DEFAULT_KERNEL_RUN_DIR).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.promotion_path = self.base_dir / "promotion_receipts.jsonl"

    def append_promotion(
        self,
        *,
        agent_uid: str,
        level: KernelPromotionLevel,
        status: KernelPromotionStatus = "promoted",
        allowed_sources: list[str] | tuple[str, ...] | None = None,
        allowed_tools: list[str] | tuple[str, ...] | None = None,
        allowed_work_kinds: list[KernelPromotionWorkKind] | tuple[KernelPromotionWorkKind, ...] | None = None,
        max_lease_seconds: int = 300,
        expires_at: str = "",
        reviewer: str = "operator",
        reason: str = "",
        evidence_refs: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> KernelPromotionReceipt:
        receipt = KernelPromotionReceipt(
            agent_uid=_required(agent_uid, "agent_uid"),
            level=level,
            status=status,
            allowed_sources=_sorted_unique(allowed_sources or []),
            allowed_tools=_sorted_unique(allowed_tools or []),
            allowed_work_kinds=sorted(set(allowed_work_kinds or [])),
            max_lease_seconds=max(1, int(max_lease_seconds)),
            expires_at=expires_at,
            reviewer=reviewer or "operator",
            reason=reason,
            evidence_refs=list(evidence_refs or []),
            metadata=dict(metadata or {}),
            created_at=now or utc_now(),
        )
        return _append_hashed(self.promotion_path, receipt, KernelPromotionReceipt)

    def revoke_promotion(
        self,
        *,
        agent_uid: str,
        reviewer: str = "operator",
        reason: str = "promotion_revoked",
        now: str | None = None,
    ) -> KernelPromotionReceipt:
        latest = self.latest_for_agent(agent_uid)
        return self.append_promotion(
            agent_uid=agent_uid,
            level=latest.level if latest is not None else "observer",
            status="revoked",
            allowed_sources=latest.allowed_sources if latest is not None else [],
            allowed_tools=latest.allowed_tools if latest is not None else [],
            allowed_work_kinds=latest.allowed_work_kinds if latest is not None else [],
            max_lease_seconds=latest.max_lease_seconds if latest is not None else 1,
            reviewer=reviewer,
            reason=reason,
            evidence_refs=[_record_ref(self.promotion_path, latest.record_hash)] if latest is not None else [],
            now=now,
        )

    def promotions(self) -> list[KernelPromotionReceipt]:
        return [KernelPromotionReceipt.model_validate(row) for row in _jsonl_rows(self.promotion_path)]

    def latest_promotions(self) -> dict[str, KernelPromotionReceipt]:
        latest: dict[str, KernelPromotionReceipt] = {}
        for receipt in self.promotions():
            latest[receipt.agent_uid] = receipt
        return latest

    def latest_for_agent(self, agent_uid: str) -> KernelPromotionReceipt | None:
        return self.latest_promotions().get(agent_uid)

    def evaluate_worker_admission(
        self,
        *,
        agent_uid: str,
        requested_level: KernelPromotionLevel = "worker",
        source: str = "",
        requested_tools: list[str] | tuple[str, ...] | None = None,
        work_kind: KernelPromotionWorkKind = "long_running",
        requested_lease_seconds: int = 300,
        now: str | None = None,
    ) -> KernelPromotionAdmission:
        evaluated_at = now or utc_now()
        cleaned_agent_uid = _required(agent_uid, "agent_uid")
        tools = _sorted_unique(requested_tools or [])
        receipt = self.latest_for_agent(cleaned_agent_uid)
        if receipt is None:
            return _admission(
                "blocked",
                cleaned_agent_uid,
                requested_level,
                source,
                tools,
                work_kind,
                ["promotion_receipt_missing"],
                evaluated_at,
            )

        reasons: list[str] = []
        if receipt.status != "promoted":
            reasons.append(f"promotion_{receipt.status}")
        if _LEVEL_RANK[receipt.level] < _LEVEL_RANK[requested_level]:
            reasons.append(f"promotion_level_insufficient:{receipt.level}")
        if receipt.expires_at and _parse_utc(receipt.expires_at) <= _parse_utc(evaluated_at):
            reasons.append("promotion_expired")
        if source and source not in set(receipt.allowed_sources):
            reasons.append(f"source_not_promoted:{source}")
        if work_kind not in set(receipt.allowed_work_kinds):
            reasons.append(f"work_kind_not_promoted:{work_kind}")
        if tools:
            allowed_tools = set(receipt.allowed_tools)
            missing_tools = [tool for tool in tools if tool not in allowed_tools]
            if missing_tools:
                reasons.append("tools_not_promoted:" + ",".join(missing_tools))
        if requested_level == "provider_executor":
            if not receipt.allowed_sources:
                reasons.append("provider_executor_requires_explicit_sources")
            evidence_kinds = {
                str(ref.get("kind") or "")
                for ref in receipt.evidence_refs
                if isinstance(ref, dict)
            }
            if not evidence_kinds.intersection(_PROVIDER_EXECUTION_EVIDENCE_KINDS):
                reasons.append("provider_executor_evidence_missing")

        decision: KernelPromotionDecision = "allowed" if not reasons else "blocked"
        authority = {}
        if decision == "allowed":
            lease_seconds = min(max(1, int(requested_lease_seconds)), max(1, int(receipt.max_lease_seconds)))
            authority = {
                "agent_uid": receipt.agent_uid,
                "level": receipt.level,
                "allowed_sources": list(receipt.allowed_sources),
                "allowed_tools": list(receipt.allowed_tools),
                "allowed_work_kinds": list(receipt.allowed_work_kinds),
                "max_lease_seconds": lease_seconds,
                "promotion_receipt_hash": receipt.record_hash,
            }
        return _admission(
            decision,
            cleaned_agent_uid,
            requested_level,
            source,
            tools,
            work_kind,
            reasons,
            evaluated_at,
            promotion_ref=_record_ref(self.promotion_path, receipt.record_hash),
            reduced_worker_authority=authority,
        )

    def verify_promotion_ledger(self) -> tuple[bool, list[str]]:
        if not self.promotion_path.exists():
            return True, []
        return _verify_hash_ledger(self.promotion_path)


def _admission(
    decision: KernelPromotionDecision,
    agent_uid: str,
    requested_level: KernelPromotionLevel,
    source: str,
    requested_tools: list[str],
    work_kind: KernelPromotionWorkKind,
    reasons: list[str],
    evaluated_at: str,
    *,
    promotion_ref: dict[str, Any] | None = None,
    reduced_worker_authority: dict[str, Any] | None = None,
) -> KernelPromotionAdmission:
    return KernelPromotionAdmission(
        decision=decision,
        agent_uid=agent_uid,
        requested_level=requested_level,
        requested_source=source,
        requested_tools=requested_tools,
        requested_work_kind=work_kind,
        reasons=reasons,
        promotion_ref=dict(promotion_ref or {}),
        reduced_worker_authority=dict(reduced_worker_authority or {}),
        evaluated_at=evaluated_at,
    )


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")


def _append_hashed(path: Path, model: BaseModel, model_type: type[Any]) -> Any:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(f"{path.suffix}.lock")
    with lock_path.open("w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        try:
            row = model.model_dump(mode="json")
            rows = _jsonl_rows(path)
            row["previous_record_hash"] = str(rows[-1].get("record_hash") or "") if rows else ""
            row["record_hash"] = ""
            row["record_hash"] = stable_payload_hash(row)
            _append_jsonl(path, row)
        finally:
            fcntl.flock(lock_handle, fcntl.LOCK_UN)
    return model_type.model_validate(row)


def _verify_hash_ledger(path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    previous_hash = ""
    for index, row in enumerate(_jsonl_rows(path), start=1):
        if str(row.get("previous_record_hash") or "") != previous_hash:
            errors.append(f"line {index}: previous_record_hash mismatch")
        observed_hash = str(row.get("record_hash") or "")
        material = dict(row)
        material["record_hash"] = ""
        if observed_hash != stable_payload_hash(material):
            errors.append(f"line {index}: record_hash mismatch")
        previous_hash = observed_hash
    return (len(errors) == 0, errors)


def _parse_utc(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _required(value: str, field: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{field} is required")
    return cleaned


def _sorted_unique(values: list[str] | tuple[str, ...]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


def _record_ref(path: Path, record_hash: str) -> dict[str, Any]:
    if not record_hash:
        return {}
    return {"kind": "kernel_promotion_receipt", "path": str(path), "record_hash": record_hash}


__all__ = [
    "KernelPromotionAdmission",
    "KernelPromotionDecision",
    "KernelPromotionLevel",
    "KernelPromotionReceipt",
    "KernelPromotionStatus",
    "KernelPromotionStore",
    "KernelPromotionWorkKind",
]
