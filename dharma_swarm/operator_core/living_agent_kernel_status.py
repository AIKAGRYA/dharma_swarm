"""Operator status view for the LivingAgentKernel OS."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dharma_swarm.operator_core.living_agent_kernel import (
    DEFAULT_KERNEL_RUN_DIR,
    KernelControlSnapshot,
    KernelRunStore,
)
from dharma_swarm.operator_core.living_agent_kernel_activation import KernelActivationStore
from dharma_swarm.operator_core.living_agent_kernel_promotion import KernelPromotionReceipt, KernelPromotionStore
from dharma_swarm.operator_core.living_agent_kernel_provider_worker import KernelProviderWorkerStore
from dharma_swarm.operator_core.living_agent_kernel_workers import KernelExternalWorkerState, KernelExternalWorkerStore
from dharma_swarm.operator_core.runtime_truth import utc_now


class KernelOSStatus(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_os_status.v1"
    generated_at: str = Field(default_factory=utc_now)
    store_dir: str
    wake_snapshot: KernelControlSnapshot
    worker_states: list[KernelExternalWorkerState] = Field(default_factory=list)
    latest_promotions: list[KernelPromotionReceipt] = Field(default_factory=list)
    activation_count: int = 0
    provider_worker_receipt_count: int = 0
    ledger_integrity: dict[str, Any] = Field(default_factory=dict)


def living_agent_os_status(
    *,
    store_dir: Path | str | None = None,
    now: str | None = None,
    latest_limit: int = 20,
    stale_after_seconds: int = 120,
    offline_after_seconds: int = 3600,
) -> KernelOSStatus:
    observed_at = now or utc_now()
    store_root = Path(store_dir or DEFAULT_KERNEL_RUN_DIR).expanduser()
    kernel = KernelRunStore(store_root)
    workers = KernelExternalWorkerStore(store_root)
    promotions = KernelPromotionStore(store_root)
    activation = KernelActivationStore(store_root)
    provider_workers = KernelProviderWorkerStore(store_root)

    wake_ok, wake_errors = kernel.verify_wake_ledger() if kernel.wake_ledger_path.exists() else (True, [])
    worker_ok, worker_errors = workers.verify_worker_ledgers()
    promotion_ok, promotion_errors = promotions.verify_promotion_ledger()
    activation_ok, activation_errors = activation.verify_activation_ledger()
    provider_ok, provider_errors = provider_workers.verify_provider_worker_ledger()

    return KernelOSStatus(
        generated_at=observed_at,
        store_dir=str(store_root),
        wake_snapshot=kernel.control_snapshot(now=observed_at, latest_limit=latest_limit),
        worker_states=workers.worker_states(
            stale_after_seconds=stale_after_seconds,
            offline_after_seconds=offline_after_seconds,
            now=observed_at,
        ),
        latest_promotions=sorted(promotions.latest_promotions().values(), key=lambda receipt: receipt.agent_uid),
        activation_count=len(activation.activations()),
        provider_worker_receipt_count=len(provider_workers.receipts()),
        ledger_integrity={
            "wake": {"ok": wake_ok, "errors": wake_errors},
            "worker": {"ok": worker_ok, "errors": worker_errors},
            "promotion": {"ok": promotion_ok, "errors": promotion_errors},
            "activation": {"ok": activation_ok, "errors": activation_errors},
            "provider_worker": {"ok": provider_ok, "errors": provider_errors},
        },
    )


__all__ = ["KernelOSStatus", "living_agent_os_status"]
