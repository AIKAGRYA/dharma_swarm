"""Sarathi apex source package.

These modules are honest source surfaces. They do not claim unattended liveness;
runtime-home wrappers should import from here.
"""

from .brief import build_operator_brief
from .delegate import DelegationOutcome, delegate_all
from .gateway import gateway_snapshot
from .plan import BootPack, PlannedDelegation, build_plan
from .proof import (
    ProofCycleRecord,
    ProofVerdict,
    evaluate_unattended_proof,
    sakshi_audit_brief,
)
from .pulse import sarathi_pulse
from .roster import load_roster
from .scoreboard import organ_scoreboard
from .wake import make_wake_work_fn, run_wake_unit, sweep_responses

__all__ = [
    "BootPack",
    "DelegationOutcome",
    "PlannedDelegation",
    "build_operator_brief",
    "build_plan",
    "delegate_all",
    "ProofCycleRecord",
    "ProofVerdict",
    "evaluate_unattended_proof",
    "gateway_snapshot",
    "load_roster",
    "make_wake_work_fn",
    "organ_scoreboard",
    "run_wake_unit",
    "sakshi_audit_brief",
    "sarathi_pulse",
    "sweep_responses",
]
