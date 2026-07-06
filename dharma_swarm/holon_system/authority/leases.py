"""Facade: execution leases (the permission mechanism).

Canonical owner: dharma_swarm/operator_core/execution_lease.py.
"""

from __future__ import annotations

from dharma_swarm.operator_core.execution_lease import (
    ExecutionLeaseError,
    LeaseValidation,
    build_execution_lease,
    find_execution_lease_for_task,
    load_execution_lease,
    load_revoked_lease_ids,
    record_lease_revocation,
    validate_execution_lease,
    write_execution_lease,
)

__all__ = [
    "ExecutionLeaseError",
    "LeaseValidation",
    "build_execution_lease",
    "find_execution_lease_for_task",
    "load_execution_lease",
    "load_revoked_lease_ids",
    "record_lease_revocation",
    "validate_execution_lease",
    "write_execution_lease",
]
