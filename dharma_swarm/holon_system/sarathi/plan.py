"""Deterministic planning organ for the Sarathi apex (PR-S1).

``build_plan`` is a pure function of an injected :class:`BootPack` — no clock,
no randomness, no disk, no model. Model-assisted planning, when it arrives,
feeds PROPOSED items into the boot pack upstream; the planner itself stays
deterministic and every planned action still faces the reversibility gate in
``delegate.py`` before anything moves. Source stays thin per Gate-9: no
runtime paths, no liveness constants, no unattended claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

VALID_KINDS = ("experiment", "build", "review", "publication", "merge")
VALID_CHANNELS = ("mailbox", "invoke", "merge_intent")


@dataclass(frozen=True)
class BootPack:
    """Everything one wake cycle may plan from. Injected, never self-loaded.

    ``audit`` is the parsed runtime-truth payload (latest_audit.json); the
    planner never invents runtime state — a missing audit is carried as None
    and surfaces as such in the operator brief, never as fabricated liveness.
    """

    roster: tuple[str, ...]
    open_items: tuple[Mapping[str, Any], ...] = ()
    ready_summaries: frozenset[str] = frozenset()
    audit: Mapping[str, Any] | None = None
    lodestone_excerpt: str = ""


@dataclass(frozen=True)
class PlannedDelegation:
    """One planned unit of delegated work, ready for gate classification."""

    action: str
    recipient: str
    channel: str
    summary: str
    body: str
    depends_on: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


def _planned_channel(kind: str, raw_channel: Any) -> str:
    if kind == "merge":
        return "merge_intent"
    channel = str(raw_channel or "mailbox")
    return channel if channel in VALID_CHANNELS else "mailbox"


def build_plan(pack: BootPack) -> list[PlannedDelegation]:
    """Map open items onto planned delegations, deterministically.

    Rules (in order, per item):
    - an item must be a mapping with a ``kind`` in :data:`VALID_KINDS` and a
      non-empty ``summary`` — anything else is skipped, never repaired;
    - an item whose summary is already live in the mailbox ready-set
      (``ready_summaries``) is skipped — the mailbox is the dedup surface;
    - ``kind == "merge"`` always routes to the ``merge_intent`` channel
      addressed to Merge Master Mike's lane; Sarathi never plans a direct
      merge or push (those verbs are NEVER_AUTO in the gate anyway);
    - recipient defaults to the first roster member; an explicit recipient
      outside the roster is kept verbatim (the mailbox is cross-harness) but
      flagged in metadata so the brief can show it.

    The action string is the exact text the reversibility gate will classify;
    it is derived from item fields, not free-composed, so a planned action
    can only ADD gate-tripping vocabulary through the item's own words.
    """
    plan: list[PlannedDelegation] = []
    if not pack.roster:
        return plan
    default_recipient = pack.roster[0]
    for item in pack.open_items:
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        summary = str(item.get("summary") or "").strip()
        if kind not in VALID_KINDS or not summary:
            continue
        if summary in pack.ready_summaries:
            continue
        channel = _planned_channel(kind, item.get("channel"))
        if channel == "merge_intent":
            recipient = str(item.get("recipient") or "merge_master_mike")
            pr_number = str(item.get("pr") or "").strip()
            target = f"pull request #{pr_number}" if pr_number else summary
            action = f"queue unattended-lane label request for {target}"
            # The body is CONSTRUCTED, not passed through: a merge item's caller
            # body/summary never becomes a worker-executed instruction, so the
            # gate cannot be smuggled via a merge kind (Greptile/Codex P1).
            body = (
                f"Add the unattended-lane review label to {target} so the "
                "decorrelated-review door can evaluate it."
            )
        else:
            recipient = str(item.get("recipient") or default_recipient)
            action = f"{kind}: {summary}"
            body = str(item.get("body") or summary)
        metadata: dict[str, Any] = dict(item.get("metadata") or {})
        metadata["sarathi_kind"] = kind
        if recipient not in pack.roster and channel != "merge_intent":
            metadata["recipient_outside_roster"] = True
        plan.append(
            PlannedDelegation(
                action=action,
                recipient=recipient,
                channel=channel,
                summary=summary,
                body=body,
                depends_on=tuple(str(dep) for dep in (item.get("depends_on") or [])),
                metadata=metadata,
            )
        )
    return plan


__all__ = [
    "VALID_KINDS",
    "VALID_CHANNELS",
    "BootPack",
    "PlannedDelegation",
    "build_plan",
]
