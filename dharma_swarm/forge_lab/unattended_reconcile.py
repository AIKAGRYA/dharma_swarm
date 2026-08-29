"""Explicit recovery entrypoint for abandoned unattended-run authority."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from dharma_swarm.forge_lab.state_io import forge_state_root, now_utc, validate_safe_id
from dharma_swarm.forge_lab.unattended_explore import (
    _append_receipt,
    _reconcile_crash_closeouts,
    host_lock,
)
from dharma_swarm.forge_lab.unattended_lease import acquire_lease, release_lease


def reconcile_abandoned_runs(*, request_id: str) -> dict[str, object]:
    request_id = validate_safe_id(request_id, field="request_id")
    control_root = forge_state_root() / "unattended_explore"
    run_id = f"reconcile-{uuid4().hex[:16]}"
    holder_id = f"reconciler-{os.getpid()}-{uuid4().hex[:8]}"
    with host_lock(control_root / "runner.lock"):
        lease = acquire_lease(
            control_root,
            run_id=run_id,
            holder_id=holder_id,
            at=now_utc(),
        )
        recovered = _reconcile_crash_closeouts(
            control_root,
            current_run_id=run_id,
            recovery_fence=int(lease["fence"]),
        )
        receipt = _append_receipt(
            control_root,
            {
                "kind": "control_reconciliation",
                "at": now_utc(),
                "run_id": run_id,
                "request_id": request_id,
                "lease_id": lease["lease_id"],
                "fence": lease["fence"],
                "recovered_receipt_digests": [row["receipt_digest"] for row in recovered],
                "recovered_count": len(recovered),
                "positive_rsi_claim": False,
            },
        )
        release_lease(
            control_root,
            lease_id=str(lease["lease_id"]),
            holder_id=holder_id,
            fence=int(lease["fence"]),
            terminal_receipt_digest=str(receipt["receipt_digest"]),
        )
    return {
        "ok": True,
        "request_id": request_id,
        "fence": lease["fence"],
        "recovered_count": len(recovered),
        "receipt_digest": receipt["receipt_digest"],
    }


__all__ = ["reconcile_abandoned_runs"]
