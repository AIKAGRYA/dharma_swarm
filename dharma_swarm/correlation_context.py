"""CorrelationContext — unified trace propagation across all stores.

Carries trace_id, proposal_id, session_id, and cell_id through every
subsystem operation via contextvars. When any store records data, it can read
the current correlation context to tag the record with cross-store
identifiers — enabling queries like "show me everything about trace X."

This is the Python-native version of what a Rust type boundary would
enforce at compile time. It bridges TelicSeam (proposal_id chain) and
RuntimeEnvelope (event_id/trace_id) into one propagation mechanism.

Usage::

    from dharma_swarm.correlation_context import (
        CorrelationContext,
        get_correlation,
        set_correlation,
        correlation_scope,
    )

    # Set context for a task dispatch:
    ctx = CorrelationContext(
        trace_id="trc_abc123",
        proposal_id="prop_xyz",
        session_id="sess_001",
    )
    token = set_correlation(ctx)

    # Any downstream code reads it:
    current = get_correlation()
    assert current.trace_id == "trc_abc123"

    # Or use the context manager:
    async with correlation_scope(trace_id="trc_abc123"):
        # everything in this block sees the context
        ...
"""

from __future__ import annotations

import contextvars
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator, Iterator
from uuid import uuid4


def _new_trace_id() -> str:
    return f"trc_{uuid4().hex[:16]}"


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """Immutable correlation context that flows through async operations.

    Fields:
        trace_id: Unique identifier for this causal chain. Shared across
            all stores that participate in the same operation.
        proposal_id: TelicSeam ActionProposal ID, if one exists for this
            operation. Links to the ontology provenance chain.
        session_id: The active session under which this operation runs.
    """

    trace_id: str = field(default_factory=_new_trace_id)
    proposal_id: str = ""
    session_id: str = ""
    cell_id: str = ""

    def with_proposal(self, proposal_id: str) -> CorrelationContext:
        """Return a new context with the proposal_id set."""
        return CorrelationContext(
            trace_id=self.trace_id,
            proposal_id=proposal_id,
            session_id=self.session_id,
            cell_id=self.cell_id,
        )

    def with_cell(self, cell_id: str) -> CorrelationContext:
        """Return a new context with the cell_id (room) set."""
        return CorrelationContext(
            trace_id=self.trace_id,
            proposal_id=self.proposal_id,
            session_id=self.session_id,
            cell_id=cell_id,
        )

    def as_dict(self) -> dict[str, str]:
        """Serialize to a dict for metadata_json embedding."""
        d: dict[str, str] = {
            "trace_id": self.trace_id,
            "proposal_id": self.proposal_id,
            "session_id": self.session_id,
        }
        if self.cell_id:
            d["cell_id"] = self.cell_id
        return d


_EMPTY = CorrelationContext(trace_id="", proposal_id="", session_id="", cell_id="")

_correlation_var: contextvars.ContextVar[CorrelationContext] = contextvars.ContextVar(
    "dharma_correlation_context",
    default=_EMPTY,
)


def get_correlation() -> CorrelationContext:
    """Read the current correlation context (never None)."""
    return _correlation_var.get()


def set_correlation(ctx: CorrelationContext) -> contextvars.Token[CorrelationContext]:
    """Set the correlation context, returning a reset token."""
    return _correlation_var.set(ctx)


@asynccontextmanager
async def correlation_scope(
    *,
    trace_id: str = "",
    proposal_id: str = "",
    session_id: str = "",
    cell_id: str = "",
) -> AsyncIterator[CorrelationContext]:
    """Async context manager that sets and restores correlation context."""
    ctx = CorrelationContext(
        trace_id=trace_id or _new_trace_id(),
        proposal_id=proposal_id,
        session_id=session_id,
        cell_id=cell_id,
    )
    token = _correlation_var.set(ctx)
    try:
        yield ctx
    finally:
        _correlation_var.reset(token)


@contextmanager
def correlation_scope_sync(
    *,
    trace_id: str = "",
    proposal_id: str = "",
    session_id: str = "",
    cell_id: str = "",
) -> Iterator[CorrelationContext]:
    """Sync context manager that sets and restores correlation context."""
    ctx = CorrelationContext(
        trace_id=trace_id or _new_trace_id(),
        proposal_id=proposal_id,
        session_id=session_id,
        cell_id=cell_id,
    )
    token = _correlation_var.set(ctx)
    try:
        yield ctx
    finally:
        _correlation_var.reset(token)
