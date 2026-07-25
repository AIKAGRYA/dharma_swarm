"""Stable-UID facade over A2A cards, fleet nodes, onboarding, and telemetry.

The directory is a read model, not a new source of truth.  It merges the
existing registries by durable ``agent_uid`` and deliberately exposes only
credential references (for example ``env:DHARMA_NODE_KEY_AGNI``), never
credential values or arbitrary source metadata.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from dharma_swarm.a2a.agent_card import CardRegistry, resolve_agent_uid
from dharma_swarm.a2a.node_registry import NodeRegistry
from dharma_swarm.daemon_config import dharma_state_dir

logger = logging.getLogger(__name__)
_SOURCE_ORDER = ("card", "node", "onboarding", "telemetry")


@dataclass
class AgentDirectoryEntry:
    """Credential-safe merged projection for one durable agent identity."""

    agent_uid: str
    name: str = ""
    role: str = ""
    status: str = "unknown"
    capabilities: list[str] = field(default_factory=list)
    endpoint: str = ""
    node_id: str = ""
    credential_refs: list[str] = field(default_factory=list)
    onboarding: dict[str, str] = field(default_factory=dict)
    telemetry: dict[str, str] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentDirectory:
    """Read-only facade joining existing agent control-plane projections."""

    def __init__(
        self,
        *,
        card_registry: CardRegistry,
        node_registry: NodeRegistry,
        dharma_home: Path | None = None,
        telemetry_store: Any | None = None,
    ) -> None:
        self.card_registry = card_registry
        self.node_registry = node_registry
        self.dharma_home = dharma_home or dharma_state_dir("DHARMA_HOME")
        self.telemetry_store = telemetry_store
        self._last_entries: list[AgentDirectoryEntry] = []

    @staticmethod
    def _stable_uid(name: str, explicit_uid: str = "") -> str:
        try:
            return resolve_agent_uid(name, agent_uid=explicit_uid)
        except ValueError:
            cleaned = (explicit_uid or name).strip()
            if not cleaned:
                raise
            return cleaned

    @staticmethod
    def _entry(
        entries: dict[str, AgentDirectoryEntry],
        uid: str,
        *,
        name: str = "",
    ) -> AgentDirectoryEntry:
        entry = entries.get(uid)
        if entry is None:
            entry = AgentDirectoryEntry(agent_uid=uid, name=name or uid)
            entries[uid] = entry
        elif name and (not entry.name or entry.name == entry.agent_uid):
            entry.name = name
        return entry

    @staticmethod
    def _mark_source(entry: AgentDirectoryEntry, source: str) -> None:
        if source not in entry.sources:
            entry.sources.append(source)

    def _merge_cards(self, entries: dict[str, AgentDirectoryEntry]) -> None:
        for card in self.card_registry.list_all():
            uid = self._stable_uid(card.name, card.agent_uid)
            entry = self._entry(entries, uid, name=card.name)
            entry.role = card.role or entry.role
            entry.status = card.status or entry.status
            entry.capabilities = sorted(set(card.capability_names()))
            entry.endpoint = card.endpoint or entry.endpoint
            self._mark_source(entry, "card")

    def _merge_nodes(self, entries: dict[str, AgentDirectoryEntry]) -> None:
        for node in self.node_registry.list_all():
            metadata = node.metadata if isinstance(node.metadata, dict) else {}
            explicit_uid = str(metadata.get("agent_uid") or "")
            uid = self._stable_uid(node.node_id, explicit_uid)
            entry = self._entry(entries, uid, name=node.node_id)
            entry.node_id = node.node_id
            entry.endpoint = node.endpoint or entry.endpoint
            entry.status = node.status or entry.status
            if node.capabilities:
                entry.capabilities = sorted(set(entry.capabilities) | set(node.capabilities))
            if node.api_key_env:
                credential_ref = f"env:{node.api_key_env}"
                if credential_ref not in entry.credential_refs:
                    entry.credential_refs.append(credential_ref)
            self._mark_source(entry, "node")

    def _iter_onboarding_receipts(self):
        path = self.dharma_home / "onboarding" / "receipts.jsonl"
        if not path.exists():
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            try:
                receipt = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed onboarding receipt in %s", path)
                continue
            if isinstance(receipt, dict):
                yield receipt

    def _merge_onboarding(self, entries: dict[str, AgentDirectoryEntry]) -> None:
        for receipt in self._iter_onboarding_receipts():
            callsign = str(receipt.get("callsign") or receipt.get("agent_uid") or "")
            explicit_uid = str(receipt.get("agent_uid") or "")
            if not callsign:
                continue
            uid = self._stable_uid(callsign, explicit_uid)
            entry = self._entry(entries, uid, name=callsign)
            entry.onboarding = {
                key: str(receipt.get(key) or "")
                for key in ("receipt_id", "harness", "department", "team_id", "created_at")
                if receipt.get(key)
            }
            self._mark_source(entry, "onboarding")

    async def _merge_telemetry(self, entries: dict[str, AgentDirectoryEntry]) -> None:
        if self.telemetry_store is None:
            return
        records = await self.telemetry_store.list_agent_identities(limit=1000)
        for record in records:
            agent_id = str(getattr(record, "agent_id", "") or "")
            if not agent_id:
                continue
            uid = self._stable_uid(agent_id)
            codename = str(getattr(record, "codename", "") or "")
            entry = self._entry(entries, uid, name=codename or agent_id)
            telemetry: dict[str, str] = {}
            for key in (
                "codename",
                "department",
                "squad_id",
                "specialization",
                "status",
                "last_active",
            ):
                value = getattr(record, key, None)
                if value not in (None, ""):
                    telemetry[key] = str(value)
            entry.telemetry = telemetry
            if "node" not in entry.sources and telemetry.get("status"):
                entry.status = telemetry["status"]
            self._mark_source(entry, "telemetry")

    async def list_entries(self) -> list[AgentDirectoryEntry]:
        entries: dict[str, AgentDirectoryEntry] = {}
        self._merge_cards(entries)
        self._merge_nodes(entries)
        self._merge_onboarding(entries)
        await self._merge_telemetry(entries)
        for entry in entries.values():
            entry.sources.sort(key=_SOURCE_ORDER.index)
            entry.credential_refs.sort()
        self._last_entries = sorted(entries.values(), key=lambda item: item.agent_uid)
        return list(self._last_entries)

    async def get(self, identifier: str) -> AgentDirectoryEntry | None:
        entries = await self.list_entries()
        try:
            resolved = self._stable_uid(identifier)
        except ValueError:
            resolved = identifier
        for entry in entries:
            if identifier in {entry.agent_uid, entry.name, entry.node_id}:
                return entry
            if resolved == entry.agent_uid:
                return entry
        return None
