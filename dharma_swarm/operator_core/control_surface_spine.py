"""Spine pulse row for the control surface (cockpit projection).

Split out of ``control_surface.py`` (module line budget, Rule 10), following
the existing ``control_surface_go`` / ``control_surface_memory`` row-builder
pattern. Read-only projection over the live EvidenceReceipt stream via
``spine_tail.compute_spine_pulse`` — no new store, no writes.
"""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.operator_core.control_surface_models import ControlSurfaceRow


def _spine_pulse_row(
    repo_root: Path | None = None,
    runtime_db: Path | None = None,
) -> ControlSurfaceRow:
    """Read-only cockpit pulse over the live EvidenceReceipt stream.

    Reuses the spine tail reader (delegation_runs.receipt_json, owner:
    runtime_state) — no new store. Exposes receipts_last_hour,
    last_receipt_age_seconds, and dispatch_dropoff_count in ``row.raw`` so the
    operator can feel the spine working. Graceful absence: when the spine is not
    live on this host the row is declared_only, not an error.
    """
    from dharma_swarm.operator_core.spine_tail import compute_spine_pulse

    pulse = compute_spine_pulse(runtime_db)
    present = bool(pulse.get("present"))
    row = ControlSurfaceRow(
        id="spine.pulse",
        kind="runtime_store",
        label="Spine Pulse (EvidenceReceipt stream)",
        authority_role="observed_authority",
        declared_state="live",
        desired_state="live",
        observed_state="live" if present else "spine not live on this host",
        coherence_state="bound" if present else "declared_only",
        priority="p1",
        owner_module="dharma_swarm/operator_core/spine_tail.py",
        truth_owner="runtime_state",
        gap_codes=[] if present else ["spine_not_live"],
        raw=pulse,
    )
    if present:
        row.add_evidence(
            "db_probe",
            (
                f"receipts_last_hour={pulse['receipts_last_hour']} "
                f"last_receipt_age_seconds={pulse['last_receipt_age_seconds']} "
                f"dispatch_dropoff_count={pulse['dispatch_dropoff_count']}"
            ),
            status="present",
            provenance_chain=["runtime_state", "delegation_runs.receipt_json", "spine_pulse"],
        )
    else:
        row.add_evidence(
            "db_probe",
            str(pulse.get("detail", "")),
            status="missing",
            provenance_chain=["runtime_state", "delegation_runs.receipt_json", "spine_pulse"],
        )
    row.add_source_ref("file", "dharma_swarm/operator_core/spine_tail.py", exists=True)
    return row
