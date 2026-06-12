"""Provider-backed external worker for LivingAgentKernel wakes.

This adapter is the first live provider execution boundary for the kernel OS.
It leases an already-queued wake only after promotion admission succeeds, calls
a supplied or runtime-resolved provider, records the provider response, and
then completes the wake through the existing external-worker ledger.
"""

from __future__ import annotations

import asyncio
import fcntl
import inspect
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.operator_core.living_agent_kernel import (
    DEFAULT_KERNEL_RUN_DIR,
    KernelWakeRecord,
)
from dharma_swarm.operator_core.living_agent_kernel_promotion import (
    KernelPromotionAdmission,
    KernelPromotionStore,
)
from dharma_swarm.operator_core.living_agent_kernel_workers import (
    KernelExternalWorkerLease,
    KernelExternalWorkerResult,
    KernelExternalWorkerStore,
)
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash, utc_now

KernelProviderWorkerStatus = Literal["completed", "idle", "denied", "failed"]


class KernelProviderToolBoundary(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_provider_tool_boundary.v1"
    worker_id: str
    agent_uid: str
    wake_id: str
    run_id: str
    provider_may_execute_tools: bool = False
    requested_wake_tools: list[str] = Field(default_factory=list)
    requested_tool_call_names: list[str] = Field(default_factory=list)
    promoted_tools: list[str] = Field(default_factory=list)
    delegated_tools: list[str] = Field(default_factory=list)
    denied_delegated_tools: list[str] = Field(default_factory=list)
    context_visible_tools: list[str] = Field(default_factory=list)
    decision: Literal["context_only", "blocked"] = "context_only"
    reason: str = "provider_tool_calls_not_delegated"


class KernelProviderWorkerReceipt(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_provider_worker.v1"
    status: KernelProviderWorkerStatus
    worker_id: str
    agent_uid: str
    wake_id: str = ""
    run_id: str = ""
    provider: str = ""
    model: str = ""
    request_hash: str = ""
    response_hash: str = ""
    response_content: str = ""
    response_usage: dict[str, int] = Field(default_factory=dict)
    response_stop_reason: str = ""
    summary: str = ""
    promotion_ref: dict[str, Any] = Field(default_factory=dict)
    lease_ref: dict[str, Any] = Field(default_factory=dict)
    tool_boundary: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    created_at: str = Field(default_factory=utc_now)
    previous_record_hash: str = ""
    record_hash: str = ""


class KernelProviderWorkerCycleResult(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_provider_worker_cycle.v1"
    status: KernelProviderWorkerStatus
    worker_id: str
    agent_uid: str
    admission: KernelPromotionAdmission
    lease_ref: dict[str, Any] = Field(default_factory=dict)
    provider_receipt_ref: dict[str, Any] = Field(default_factory=dict)
    worker_result_ref: dict[str, Any] = Field(default_factory=dict)
    message: str = ""


class KernelProviderWorkerStore:
    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir or DEFAULT_KERNEL_RUN_DIR).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.provider_result_path = self.base_dir / "provider_worker_results.jsonl"

    def append_receipt(self, receipt: KernelProviderWorkerReceipt) -> KernelProviderWorkerReceipt:
        return _append_hashed(self.provider_result_path, receipt, KernelProviderWorkerReceipt)

    def receipts(self) -> list[KernelProviderWorkerReceipt]:
        return [KernelProviderWorkerReceipt.model_validate(row) for row in _jsonl_rows(self.provider_result_path)]

    def verify_provider_worker_ledger(self) -> tuple[bool, list[str]]:
        if not self.provider_result_path.exists():
            return True, []
        return _verify_hash_ledger(self.provider_result_path)


def build_provider_request(
    wake_record: KernelWakeRecord,
    *,
    provider: ProviderType | str,
    model: str,
    tool_boundary: KernelProviderToolBoundary | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> LLMRequest:
    provider_type = _provider_type(provider)
    envelope = wake_record.envelope
    payload = {
        "wake_id": wake_record.wake_id,
        "run_id": wake_record.run_id,
        "agent_uid": envelope.agent_uid,
        "provider": provider_type.value,
        "task": envelope.task.model_dump(mode="json"),
        "trigger": envelope.trigger.model_dump(mode="json"),
        "memory": envelope.memory.model_dump(mode="json"),
        "tool_request": {
            "requested_tools": list(envelope.tool_request.requested_tools),
            "late_bound_tools": list(envelope.tool_request.late_bound_tools),
            "tool_call_names": _tool_call_names(envelope.tool_request.tool_calls),
            "provider_may_execute_tools": False,
        },
        "provider_tool_boundary": tool_boundary.model_dump(mode="json") if tool_boundary is not None else {},
        "proof": envelope.proof.model_dump(mode="json"),
        "metadata": dict(envelope.metadata),
    }
    return LLMRequest(
        model=model,
        system=(
            "You are a promoted LivingAgentKernel provider worker. Execute the wake "
            "inside the authority described by its envelope. Return a concise result, "
            "explicit uncertainty, and proof or verification suggestions. You may not "
            "execute tools, filesystem actions, network actions, or subprocess actions; "
            "requested wake tools are context only unless an external kernel receipt "
            "executes them."
        ),
        messages=[
            {
                "role": "user",
                "content": json.dumps(payload, sort_keys=True, ensure_ascii=True),
            }
        ],
        max_tokens=max(1, int(max_tokens)),
        temperature=float(temperature),
    )


def evaluate_provider_tool_boundary(
    wake_record: KernelWakeRecord,
    *,
    worker_id: str,
    agent_uid: str,
    admission: KernelPromotionAdmission,
) -> KernelProviderToolBoundary:
    envelope = wake_record.envelope
    requested_tools = _sorted_unique(
        [
            *envelope.tool_request.requested_tools,
            *envelope.tool_request.late_bound_tools,
            *_tool_call_names(envelope.tool_request.tool_calls),
        ]
    )
    promoted_tools = _sorted_unique(list(admission.reduced_worker_authority.get("allowed_tools") or []))
    delegated_tools = ["provider_complete"] if "provider_complete" in set(promoted_tools) else []
    return KernelProviderToolBoundary(
        worker_id=worker_id,
        agent_uid=agent_uid,
        wake_id=wake_record.wake_id,
        run_id=wake_record.run_id,
        requested_wake_tools=requested_tools,
        requested_tool_call_names=_tool_call_names(envelope.tool_request.tool_calls),
        promoted_tools=promoted_tools,
        delegated_tools=delegated_tools,
        denied_delegated_tools=[tool for tool in requested_tools if tool not in set(delegated_tools)],
        context_visible_tools=requested_tools,
    )


async def execute_provider_worker_cycle(
    *,
    store_dir: Path | str | None = None,
    workspace_root: Path | str | None = None,
    worker_id: str,
    agent_uid: str,
    provider: ProviderType | str,
    model: str,
    allowed_sources: list[str] | tuple[str, ...] | None = None,
    lease_seconds: int = 300,
    heartbeat_max_age_seconds: int = 120,
    now: str | None = None,
    provider_client: Any | None = None,
    fixture_response: str | None = None,
    live_provider: bool = False,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> KernelProviderWorkerCycleResult:
    observed_at = now or utc_now()
    provider_type = _provider_type(provider)
    store_root = Path(store_dir or DEFAULT_KERNEL_RUN_DIR).expanduser()
    workspace = Path(workspace_root or Path.cwd()).expanduser()
    promotions = KernelPromotionStore(store_root)
    workers = KernelExternalWorkerStore(store_root)
    provider_store = KernelProviderWorkerStore(store_root)

    admission = promotions.evaluate_worker_admission(
        agent_uid=agent_uid,
        requested_level="provider_executor",
        requested_tools=["provider_complete"],
        work_kind="provider_execution",
        requested_lease_seconds=lease_seconds,
        now=observed_at,
    )
    if admission.decision != "allowed":
        receipt = provider_store.append_receipt(
            KernelProviderWorkerReceipt(
                status="denied",
                worker_id=worker_id,
                agent_uid=agent_uid,
                provider=provider_type.value,
                model=model,
                promotion_ref=dict(admission.promotion_ref),
                error=";".join(admission.reasons) or "promotion_admission_denied",
                created_at=observed_at,
            )
        )
        return KernelProviderWorkerCycleResult(
            status="denied",
            worker_id=worker_id,
            agent_uid=agent_uid,
            admission=admission,
            provider_receipt_ref=_provider_receipt_ref(provider_store.provider_result_path, receipt.record_hash),
            message=receipt.error,
        )

    authority = dict(admission.reduced_worker_authority)
    promoted_sources = list(authority.get("allowed_sources") or [])
    requested_sources = _sorted_unique(allowed_sources or promoted_sources)
    denied_sources = [source for source in requested_sources if source not in set(promoted_sources)]
    if not requested_sources or denied_sources:
        reason = "provider_sources_not_authorized"
        if denied_sources:
            reason += ":" + ",".join(denied_sources)
        receipt = provider_store.append_receipt(
            KernelProviderWorkerReceipt(
                status="denied",
                worker_id=worker_id,
                agent_uid=agent_uid,
                provider=provider_type.value,
                model=model,
                promotion_ref=dict(admission.promotion_ref),
                error=reason,
                created_at=observed_at,
            )
        )
        return KernelProviderWorkerCycleResult(
            status="denied",
            worker_id=worker_id,
            agent_uid=agent_uid,
            admission=admission,
            provider_receipt_ref=_provider_receipt_ref(provider_store.provider_result_path, receipt.record_hash),
            message=reason,
        )

    workers.register_worker(
        worker_id,
        role="provider_executor",
        allowed_sources=requested_sources,
        max_lease_seconds=int(authority.get("max_lease_seconds") or lease_seconds),
        metadata={
            "agent_uid": agent_uid,
            "provider": provider_type.value,
            "model": model,
            "promotion_receipt_hash": str(authority.get("promotion_receipt_hash") or ""),
        },
        now=observed_at,
    )
    workers.heartbeat_worker(
        worker_id,
        metadata={"agent_uid": agent_uid, "provider": provider_type.value},
        now=observed_at,
    )
    lease = workers.lease_worker_wake(
        worker_id,
        lease_seconds=lease_seconds,
        heartbeat_max_age_seconds=heartbeat_max_age_seconds,
        now=observed_at,
    )
    lease_ref = _lease_ref(workers.lease_path, lease)
    if lease.status != "leased" or lease.wake_record is None:
        receipt = provider_store.append_receipt(
            KernelProviderWorkerReceipt(
                status="idle" if lease.status == "idle" else "denied",
                worker_id=worker_id,
                agent_uid=agent_uid,
                provider=provider_type.value,
                model=model,
                promotion_ref=dict(admission.promotion_ref),
                lease_ref=lease_ref,
                error=lease.reason,
                created_at=observed_at,
            )
        )
        status: KernelProviderWorkerStatus = "idle" if lease.status == "idle" else "denied"
        return KernelProviderWorkerCycleResult(
            status=status,
            worker_id=worker_id,
            agent_uid=agent_uid,
            admission=admission,
            lease_ref=lease_ref,
            provider_receipt_ref=_provider_receipt_ref(provider_store.provider_result_path, receipt.record_hash),
            message=lease.reason,
        )

    wake = lease.wake_record
    source_admission = promotions.evaluate_worker_admission(
        agent_uid=agent_uid,
        requested_level="provider_executor",
        source=wake.envelope.trigger.source,
        requested_tools=["provider_complete"],
        work_kind="provider_execution",
        requested_lease_seconds=lease_seconds,
        now=observed_at,
    )
    if source_admission.decision != "allowed":
        receipt = provider_store.append_receipt(
            KernelProviderWorkerReceipt(
                status="denied",
                worker_id=worker_id,
                agent_uid=agent_uid,
                wake_id=wake.wake_id,
                run_id=wake.run_id,
                provider=provider_type.value,
                model=model,
                promotion_ref=dict(source_admission.promotion_ref),
                lease_ref=lease_ref,
                error=";".join(source_admission.reasons),
                created_at=observed_at,
            )
        )
        worker_result = workers.complete_worker_wake(
            worker_id,
            wake.wake_id,
            status="blocked",
            summary="Provider worker source admission denied.",
            result_ref={
                "kind": "kernel_provider_worker_result",
                "provider_execution": False,
                "provider_worker_receipt_hash": receipt.record_hash,
                "promotion_admission": source_admission.model_dump(mode="json"),
            },
            now=observed_at,
        )
        return KernelProviderWorkerCycleResult(
            status="denied",
            worker_id=worker_id,
            agent_uid=agent_uid,
            admission=source_admission,
            lease_ref=lease_ref,
            provider_receipt_ref=_provider_receipt_ref(provider_store.provider_result_path, receipt.record_hash),
            worker_result_ref=_worker_result_ref(workers.result_path, worker_result),
            message="provider_worker_source_admission_denied",
        )

    tool_boundary = evaluate_provider_tool_boundary(
        wake,
        worker_id=worker_id,
        agent_uid=agent_uid,
        admission=source_admission,
    )
    request = build_provider_request(
        wake,
        provider=provider_type,
        model=model,
        tool_boundary=tool_boundary,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    request_hash = stable_payload_hash(request.model_dump(mode="json"))
    try:
        response = await _complete_provider(
            provider_client=provider_client,
            fixture_response=fixture_response,
            live_provider=live_provider,
            provider=provider_type,
            model=model,
            request=request,
            workspace_root=workspace,
        )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        receipt = provider_store.append_receipt(
            KernelProviderWorkerReceipt(
                status="failed",
                worker_id=worker_id,
                agent_uid=agent_uid,
                wake_id=wake.wake_id,
                run_id=wake.run_id,
                provider=provider_type.value,
                model=model,
                request_hash=request_hash,
                promotion_ref=dict(source_admission.promotion_ref),
                lease_ref=lease_ref,
                tool_boundary=tool_boundary.model_dump(mode="json"),
                error=error,
                created_at=observed_at,
            )
        )
        worker_result = workers.complete_worker_wake(
            worker_id,
            wake.wake_id,
            status="failed",
            summary="Provider worker execution failed.",
            result_ref={
                "kind": "kernel_provider_worker_result",
                "provider_execution": True,
                "provider": provider_type.value,
                "model": model,
                "request_hash": request_hash,
                "provider_worker_receipt_hash": receipt.record_hash,
                "tool_boundary": tool_boundary.model_dump(mode="json"),
                "error": error,
            },
            now=observed_at,
        )
        return KernelProviderWorkerCycleResult(
            status="failed",
            worker_id=worker_id,
            agent_uid=agent_uid,
            admission=source_admission,
            lease_ref=lease_ref,
            provider_receipt_ref=_provider_receipt_ref(provider_store.provider_result_path, receipt.record_hash),
            worker_result_ref=_worker_result_ref(workers.result_path, worker_result),
            message=error,
        )

    response_hash = stable_payload_hash(response.model_dump(mode="json"))
    summary = _summary(response.content)
    receipt = provider_store.append_receipt(
        KernelProviderWorkerReceipt(
            status="completed",
            worker_id=worker_id,
            agent_uid=agent_uid,
            wake_id=wake.wake_id,
            run_id=wake.run_id,
            provider=response.provider or provider_type.value,
            model=response.model or model,
            request_hash=request_hash,
            response_hash=response_hash,
            response_content=response.content,
            response_usage=dict(response.usage),
            response_stop_reason=response.stop_reason or "",
            summary=summary,
            promotion_ref=dict(source_admission.promotion_ref),
            lease_ref=lease_ref,
            tool_boundary=tool_boundary.model_dump(mode="json"),
            created_at=observed_at,
        )
    )
    worker_result = workers.complete_worker_wake(
        worker_id,
        wake.wake_id,
        status="completed",
        summary=summary,
        result_ref={
            "kind": "kernel_provider_worker_result",
            "provider_execution": True,
            "provider": response.provider or provider_type.value,
            "model": response.model or model,
            "request_hash": request_hash,
            "response_hash": response_hash,
            "provider_worker_receipt_hash": receipt.record_hash,
            "promotion_receipt_hash": str(source_admission.promotion_ref.get("record_hash") or ""),
            "tool_boundary": tool_boundary.model_dump(mode="json"),
        },
        now=observed_at,
    )
    return KernelProviderWorkerCycleResult(
        status="completed",
        worker_id=worker_id,
        agent_uid=agent_uid,
        admission=source_admission,
        lease_ref=lease_ref,
        provider_receipt_ref=_provider_receipt_ref(provider_store.provider_result_path, receipt.record_hash),
        worker_result_ref=_worker_result_ref(workers.result_path, worker_result),
        message=summary,
    )


def execute_provider_worker_cycle_sync(**kwargs: Any) -> KernelProviderWorkerCycleResult:
    return asyncio.run(execute_provider_worker_cycle(**kwargs))


async def _complete_provider(
    *,
    provider_client: Any | None,
    fixture_response: str | None,
    live_provider: bool,
    provider: ProviderType,
    model: str,
    request: LLMRequest,
    workspace_root: Path,
) -> LLMResponse:
    if fixture_response is not None:
        return LLMResponse(content=fixture_response, model=model, provider=provider.value)
    client = provider_client
    if client is None and live_provider:
        from dharma_swarm.runtime_provider import create_runtime_provider, resolve_runtime_provider_config

        config = resolve_runtime_provider_config(provider, model=model, working_dir=str(workspace_root))
        if not config.available:
            raise RuntimeError(f"runtime provider is not available: {provider.value}")
        client = create_runtime_provider(config)
    if client is None:
        raise RuntimeError("provider execution requires fixture_response, provider_client, or live_provider=True")
    if hasattr(client, "complete"):
        result = client.complete(request)
    elif callable(client):
        result = client(request)
    else:
        raise TypeError("provider_client must be callable or expose complete(request)")
    if inspect.isawaitable(result):
        result = await result
    if isinstance(result, LLMResponse):
        return result
    if isinstance(result, dict):
        return LLMResponse.model_validate(result)
    raise TypeError(f"provider returned unsupported response type: {type(result).__name__}")


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


def _provider_type(provider: ProviderType | str) -> ProviderType:
    if isinstance(provider, ProviderType):
        return provider
    return ProviderType(str(provider))


def _sorted_unique(values: list[str] | tuple[str, ...]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


def _tool_call_names(tool_calls: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        name = str(call.get("name") or "").strip()
        if name:
            names.append(name)
    return _sorted_unique(names)


def _summary(content: str) -> str:
    cleaned = " ".join(str(content or "").split())
    if not cleaned:
        return "Provider returned an empty response."
    return cleaned[:240]


def _lease_ref(path: Path, lease: KernelExternalWorkerLease) -> dict[str, Any]:
    return {
        "kind": "kernel_external_worker_lease",
        "path": str(path),
        "record_hash": lease.record_hash,
        "status": lease.status,
        "wake_id": lease.wake_id,
        "run_id": lease.run_id,
    }


def _worker_result_ref(path: Path, result: KernelExternalWorkerResult) -> dict[str, Any]:
    return {
        "kind": "kernel_external_worker_result",
        "path": str(path),
        "record_hash": result.record_hash,
        "wake_id": result.wake_id,
        "run_id": result.run_id,
    }


def _provider_receipt_ref(path: Path, record_hash: str) -> dict[str, Any]:
    return {"kind": "kernel_provider_worker_receipt", "path": str(path), "record_hash": record_hash}


__all__ = [
    "KernelProviderToolBoundary",
    "KernelProviderWorkerCycleResult",
    "KernelProviderWorkerReceipt",
    "KernelProviderWorkerStatus",
    "KernelProviderWorkerStore",
    "build_provider_request",
    "evaluate_provider_tool_boundary",
    "execute_provider_worker_cycle",
    "execute_provider_worker_cycle_sync",
]
