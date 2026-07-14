"""Receipts → NodeRegistry hydration wire.

Reads onboarding receipts written by ``dharma_swarm.roaming_onboarding`` and
populates a :class:`NodeRegistry` with one :class:`RemoteNode` per registered
agent.

Why this exists
---------------
Before this wire, ``NodeRegistry`` was populated by manual ``register()``
calls. Onboarding receipts and the runtime registry lived on the same disk
but never spoke to each other. This module is the seam: it reads the
receipts trail (the kaizenops paper trail) and produces a registry the
A2A server can ``discover()`` against.

Design choices
--------------
- **Receipts are the source of truth.** The hydrator does not invent
  capabilities; it reads them from the agent card written next to the
  receipt during onboarding.
- **Idempotent.** Re-hydrating updates existing ``RemoteNode`` entries
  rather than failing. Last-write-wins on capability lists.
- **Status default = ``unknown``.** Hydration alone does not assert a
  node is online; ``NodeRegistry.health_check`` is the operational
  witness for that. The hydrator only declares "this agent exists in
  the receipts trail."
- **Local endpoints.** Receipts written by the roaming flow have
  ``endpoint`` strings that may be ``""`` or local-only (e.g.
  ``local://in-process``). The hydrator preserves them verbatim and lets
  the gateway/registry decide reachability separately.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

from ..daemon_config import dharma_state_dir
from .agent_card import CardRegistry
from .node_registry import NodeRegistry, RemoteNode

logger = logging.getLogger(__name__)


def _default_dharma_home() -> Path:
    """Match ``roaming_onboarding._dharma_home`` semantics.

    Delegates to :func:`dharma_swarm.daemon_config.dharma_state_dir`, the
    canonical owner of ``~/.dharma`` path resolution. Honors
    ``DHARMA_HOME`` env override.
    """
    return dharma_state_dir("DHARMA_HOME")


def _iter_receipts(receipts_index: Path) -> Iterable[dict]:
    """Yield receipt dicts from the JSONL index, skipping malformed lines."""
    if not receipts_index.exists():
        return
    for raw in receipts_index.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning("skip malformed receipt line: %s", exc)
            continue


def _capabilities_from_card(cards_dir: Path, callsign: str) -> list[str]:
    """Read capabilities from the agent card written by onboarding."""
    registry = CardRegistry(cards_dir=cards_dir)
    card = registry.get(callsign)
    if card is None:
        return []
    return card.capability_names()


def hydrate_from_receipts(
    registry: NodeRegistry,
    *,
    dharma_home: Path | None = None,
) -> list[RemoteNode]:
    """Populate ``registry`` from onboarding receipts.

    Args:
        registry: The :class:`NodeRegistry` to populate (mutated in place).
        dharma_home: Override DHARMA_HOME for testing. Defaults to the
            same resolution ``roaming_onboarding`` uses.

    Returns:
        List of :class:`RemoteNode` instances that were registered or
        updated, in receipt-order.
    """
    home = dharma_home or _default_dharma_home()
    receipts_index = home / "onboarding" / "receipts.jsonl"
    cards_dir = home / "a2a" / "cards"

    nodes: list[RemoteNode] = []
    seen: set[str] = set()

    for receipt in _iter_receipts(receipts_index):
        callsign = receipt.get("callsign") or receipt.get("agent_uid")
        if not callsign:
            continue
        if callsign in seen:
            # later receipts for the same callsign supersede earlier ones
            existing = registry.get(callsign)
            if existing is not None:
                capabilities = _capabilities_from_card(cards_dir, callsign)
                if capabilities:
                    existing.capabilities = capabilities
                    registry.register(existing)
            continue
        seen.add(callsign)

        capabilities = _capabilities_from_card(cards_dir, callsign)
        node = RemoteNode(
            node_id=callsign,
            endpoint=receipt.get("endpoint") or "",
            status="unknown",  # health_check is the operational witness
            capabilities=capabilities,
            metadata={
                "agent_uid": receipt.get("agent_uid", ""),
                "harness": receipt.get("harness", ""),
                "receipt_id": receipt.get("receipt_id", ""),
                "department": receipt.get("department", ""),
                "team_id": receipt.get("team_id", ""),
                "created_at": receipt.get("created_at", ""),
            },
        )
        registry.register(node)
        nodes.append(node)
        logger.info(
            "hydrated node from receipt: %s (caps=%s)",
            callsign,
            ",".join(capabilities) or "(none)",
        )

    return nodes
