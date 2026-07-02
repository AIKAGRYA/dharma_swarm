"""Bounded standalone Holon burn-in runner."""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from holon.receipts import build_receipt, utc_now, write_receipt
from holon.source_proof import package_source_proof
from holon.supervisor import SupervisorConfig, run_supervisor


@dataclass(frozen=True)
class BurnInConfig:
    name: str
    prompt: str = "Run one bounded autonomy cycle and report evidence."
    duration_seconds: float = 0.0
    interval_seconds: float = 0.0
    min_cycles: int = 1
    cap_usd: float = 0.0
    agents_root: Path = Path.home() / ".dharma" / "agents"
    service_id: str = "holon-burn-in"
    lease_seconds: int = 300
    multi_hour_threshold_seconds: float = 7200.0
    stop_on_failure: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["agents_root"] = str(self.agents_root)
        return payload


async def run_burn_in(config: BurnInConfig) -> dict[str, Any]:
    """Run supervisor samples until duration and sample count are satisfied."""

    started_monotonic = time.monotonic()
    started_at = utc_now()
    deadline = started_monotonic + max(0.0, float(config.duration_seconds))
    min_cycles = max(1, int(config.min_cycles))
    samples: list[dict[str, Any]] = []
    while True:
        sample_started = utc_now()
        result = await run_supervisor(
            SupervisorConfig(
                name=config.name,
                prompt=config.prompt,
                max_cycles=1,
                cap_usd=config.cap_usd,
                agents_root=config.agents_root,
                lease_seconds=config.lease_seconds,
                service_id=config.service_id,
            )
        )
        sample = {
            "sample_index": len(samples) + 1,
            "started_at": sample_started,
            "completed_at": utc_now(),
            "supervisor_status": result.get("status"),
            "last_cycle_status": _last_cycle_status(result),
            "receipt": result.get("receipt") or {},
            "service_liveness": result.get("service_liveness") or {},
            "lock": result.get("lock") or {},
        }
        samples.append(sample)
        failed = sample["supervisor_status"] not in {"completed"} or sample["last_cycle_status"] != "ran"
        if failed and config.stop_on_failure:
            break
        if time.monotonic() >= deadline and len(samples) >= min_cycles:
            break
        if config.interval_seconds > 0:
            await asyncio.sleep(config.interval_seconds)
    completed_at = utc_now()
    elapsed_seconds = round(time.monotonic() - started_monotonic, 3)
    failed_samples = [
        sample
        for sample in samples
        if sample["supervisor_status"] != "completed" or sample["last_cycle_status"] != "ran"
    ]
    sample_count_met = len(samples) >= min_cycles
    multi_hour_proven = (
        elapsed_seconds >= max(1.0, float(config.multi_hour_threshold_seconds))
        and sample_count_met
        and not failed_samples
    )
    status = "pass" if sample_count_met and not failed_samples else "fail"
    payload = {
        "schema_version": "holon.burn_in.v1",
        "status": status,
        "passed": status == "pass",
        "multi_hour_proven": multi_hour_proven,
        "started_at": started_at,
        "completed_at": completed_at,
        "elapsed_seconds": elapsed_seconds,
        "config": config.to_dict(),
        "sample_count": len(samples),
        "sample_count_met": sample_count_met,
        "failed_sample_count": len(failed_samples),
        "samples": samples,
        "source_proof": package_source_proof(),
    }
    receipt = build_receipt(
        kind="holon_burn_in_run",
        subject=config.name,
        status=status,
        side_effect_key=(
            f"burn-in:{config.name}:{started_at}:"
            f"{config.duration_seconds}:{config.min_cycles}:{config.prompt}"
        ),
        payload=payload,
        verifier_refs=[
            str((sample.get("receipt") or {}).get("path") or "")
            for sample in samples
            if (sample.get("receipt") or {}).get("path")
        ],
    )
    receipt_ref = write_receipt(receipt, agents_root=config.agents_root, holon_name=config.name)
    payload["receipt"] = receipt_ref
    return payload


def run_burn_in_sync(config: BurnInConfig) -> dict[str, Any]:
    return asyncio.run(run_burn_in(config))


def _last_cycle_status(result: dict[str, Any]) -> str:
    results = result.get("results")
    if not isinstance(results, list) or not results:
        return "none"
    last = results[-1]
    if not isinstance(last, dict):
        return "unknown"
    return str(last.get("status") or "unknown")


__all__ = ["BurnInConfig", "run_burn_in", "run_burn_in_sync"]
