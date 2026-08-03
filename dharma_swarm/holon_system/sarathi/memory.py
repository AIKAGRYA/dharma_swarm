"""Memory organ for the Sarathi apex — a governed, scoped read; never a write.

Sarathi had no memory at all: before this organ, ``grep -c memory_kernel`` over
``dharma_swarm/holon_system/sarathi/*.py`` returned 0, even though
``MemoryKernel`` is the canonical front door for agent memory per ``CLAUDE.md``.

This organ delegates the whole admission decision to the repo's supported
entrypoint, ``memory_kernel.default_context.build_memory_kernel_default_context``.
It does NOT hand-roll a :class:`MemoryContextBudget`. An earlier revision did,
and got two things wrong that three independent reviewers caught:

* ``require_context_admissible=True`` rejected **every** production atom. No
  adapter ever sets that flag and ``MemoryAtom.build`` defaults it to ``False``
  (``memory_kernel/atoms.py:424``), so recall was a permanent no-op. Measured on
  the same 13 live atoms: the hand-rolled budget admitted **0** with
  ``atom_not_context_admissible`` on all 13; the supported policy admits **3**.
* ``isolation_mode="unrestricted"`` with no allowed agent ids let another
  agent's atoms into Sarathi's brief with no owner provenance rendered —
  demonstrated with a live repro (Greptile, P1/security).

The supported entrypoint fixes both, and enforces more than the hand-rolled
budget did (``require_source_digest``, ``require_source_row_key``,
``block_tool_exposure``). It also **never raises**: it returns a status, which
is why :class:`MemoryRecall` can carry ``read_failed`` as a distinct outcome
instead of collapsing it into an empty string.

Source stays thin per Gate-9: no runtime paths, no liveness constants, no
unattended claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from dharma_swarm.memory_kernel.default_context import (
    build_memory_kernel_default_context,
    memory_kernel_isolation_policy_from_metadata,
)

# Sarathi is an apex seat that delegates to sub-holons, so she reads under the
# `supervisor` topology -> `supervisor_scoped` isolation semantics. Verified
# live: this yields applied=True, allowed_agent_ids=('sarathi',), zero warnings.
# Any other agent's atoms are then omitted with `agent_not_allowed`.
SARATHI_TOPOLOGY = "supervisor"
SARATHI_AGENT_ID = "sarathi"

# Token budget for one wake cycle's recall. The supported entrypoint derives the
# atom/char caps from this, so there is exactly one knob here and no second
# vocabulary to drift from the kernel's.
DEFAULT_RECALL_TOKEN_BUDGET = 1200

# Statuses a brief must be able to tell apart. `not_configured` and `read_failed`
# are DIFFERENT facts: one means no read was attempted, the other means a read
# ran and broke. Collapsing them hides a live fault.
RECALL_NOT_CONFIGURED = "not_configured"
RECALL_UNAVAILABLE = "unavailable"
RECALL_READ_FAILED = "read_failed"
RECALL_USED = "used"


@dataclass(frozen=True)
class MemoryRecall:
    """One cycle's recall attempt, with its outcome carried explicitly.

    ``status`` is a field, not an inference from ``excerpt`` being empty. An
    empty excerpt is produced by four different situations and only one of them
    is benign; a consumer that infers from emptiness reports a broken read as
    "never attempted".
    """

    status: str
    excerpt: str = ""
    detail: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def consulted(self) -> bool:
        return self.status == RECALL_USED

    @property
    def admitted(self) -> int:
        return int(self.metadata.get("admitted_count") or 0)

    @property
    def candidates(self) -> int:
        return int(self.metadata.get("candidate_count") or 0)


def sarathi_isolation_policy(agent_id: str = SARATHI_AGENT_ID):
    """The scoped read policy for the apex seat.

    Derived through the kernel's own topology policy rather than assembled by
    hand, so an unknown topology fails closed to minimal shared allowances with
    a stamped warning instead of silently reading everything.
    """
    return memory_kernel_isolation_policy_from_metadata(
        {"topology": SARATHI_TOPOLOGY, "agent_id": agent_id}
    )


def recall_memory(
    kernel: Any | None,
    *,
    recall_query: str = "",
    token_budget: int = DEFAULT_RECALL_TOKEN_BUDGET,
    isolation_policy: Any | None = None,
) -> MemoryRecall:
    """Read governed, agent-scoped recall through the supported entrypoint.

    Never raises: every outcome is a status. A caller with no kernel gets
    ``not_configured``; a read that breaks gets ``read_failed`` carrying the
    error, which the brief must surface rather than render as silence.
    """
    if kernel is None:
        return MemoryRecall(status=RECALL_NOT_CONFIGURED)

    section, metadata = build_memory_kernel_default_context(
        kernel,
        recall_query=recall_query,
        token_budget=token_budget,
        isolation_policy=isolation_policy or sarathi_isolation_policy(),
    )
    status = str((metadata or {}).get("status") or "")

    if status == "used":
        return MemoryRecall(
            status=RECALL_USED,
            excerpt=section.content if section is not None else "",
            metadata=dict(metadata or {}),
        )
    if status == "not_configured":
        return MemoryRecall(status=RECALL_NOT_CONFIGURED, metadata=dict(metadata or {}))

    # "failed" -- or any status this organ does not recognise. Fail LOUD in the
    # brief rather than quietly: an unknown status must not read as success.
    meta = dict(metadata or {})
    detail = str(meta.get("error") or meta.get("error_type") or status or "unknown")
    return MemoryRecall(status=RECALL_READ_FAILED, detail=detail, metadata=meta)
