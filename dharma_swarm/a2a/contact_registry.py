"""A2A contact registry for local and cloud-resident agent endpoints.

The registry is intentionally small and read-only by default. It identifies
which agents belong in the A2A routing denominator without claiming that every
registered contact is currently live.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

CONTACT_KIND_LOCAL_AGENT = "local_agent"
CONTACT_KIND_CLOUD_AGENT = "cloud_agent"
CONTACT_KINDS = frozenset({CONTACT_KIND_LOCAL_AGENT, CONTACT_KIND_CLOUD_AGENT})
_AGENT_UID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class ContactRegistryError(ValueError):
    """Raised when an A2A contact record violates the registry contract."""


@dataclass(frozen=True)
class A2AContact:
    """A routable A2A contact identity.

    `kind="cloud_agent"` means the agent is part of the denominator but cannot
    be assumed to have a local launchd/tmux process. Liveness still needs a
    transport receipt from the verifier layer.
    """

    agent_uid: str
    kind: str
    display_name: str = ""
    inbox_subject: str = ""
    outbound_endpoint: str = ""
    capabilities: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        cleaned_uid = self.agent_uid.strip()
        if cleaned_uid != self.agent_uid:
            raise ContactRegistryError(f"agent_uid must be normalized: {self.agent_uid!r}")
        if not _AGENT_UID_RE.match(cleaned_uid):
            raise ContactRegistryError(f"invalid agent_uid: {self.agent_uid!r}")
        if self.kind not in CONTACT_KINDS:
            raise ContactRegistryError(f"unsupported contact kind: {self.kind!r}")
        if self.kind == CONTACT_KIND_CLOUD_AGENT and not self.inbox_subject:
            raise ContactRegistryError("cloud_agent contacts require inbox_subject")

    @property
    def is_cloud_agent(self) -> bool:
        return self.kind == CONTACT_KIND_CLOUD_AGENT

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_uid": self.agent_uid,
            "kind": self.kind,
            "display_name": self.display_name,
            "inbox_subject": self.inbox_subject,
            "outbound_endpoint": self.outbound_endpoint,
            "capabilities": list(self.capabilities),
            "metadata": dict(self.metadata),
        }


class ContactRegistry:
    """In-memory A2A population registry."""

    def __init__(self, contacts: list[A2AContact] | tuple[A2AContact, ...] = ()) -> None:
        self._contacts: dict[str, A2AContact] = {}
        for contact in contacts:
            self.register(contact)

    def register(self, contact: A2AContact) -> None:
        if contact.agent_uid in self._contacts:
            raise ContactRegistryError(f"duplicate A2A contact: {contact.agent_uid}")
        self._contacts[contact.agent_uid] = contact

    def get(self, agent_uid: str) -> A2AContact | None:
        return self._contacts.get(agent_uid)

    def require(self, agent_uid: str) -> A2AContact:
        contact = self.get(agent_uid)
        if contact is None:
            raise ContactRegistryError(f"unknown A2A contact: {agent_uid}")
        return contact

    def list_all(self) -> list[A2AContact]:
        return sorted(self._contacts.values(), key=lambda item: item.agent_uid)

    def by_kind(self, kind: str) -> list[A2AContact]:
        if kind not in CONTACT_KINDS:
            raise ContactRegistryError(f"unsupported contact kind: {kind!r}")
        return [contact for contact in self.list_all() if contact.kind == kind]

    def cloud_agents(self) -> list[A2AContact]:
        return self.by_kind(CONTACT_KIND_CLOUD_AGENT)


def default_contacts() -> tuple[A2AContact, ...]:
    """Return the current declared A2A population.

    These records are denominator declarations, not live-contact claims.
    """

    return (
        A2AContact(
            agent_uid="operator_guide_cursor",
            kind=CONTACT_KIND_LOCAL_AGENT,
            display_name="Operator Guide (Cursor)",
            inbox_subject="dharma.agent.operator_guide_cursor.inbox",
            capabilities=(
                "operator_teaching",
                "fleet_synthesis",
                "workspace_triage",
                "trans_chat_continuity",
            ),
            metadata={
                "d_level": "D2_seed",
                "harness": "cursor_ide",
                "aligned_apex_object": "semobj.sarathi",
            },
        ),
        A2AContact(
            agent_uid="codex_composer",
            kind=CONTACT_KIND_LOCAL_AGENT,
            display_name="codex_composer",
            inbox_subject="dharma.agent.codex_composer.inbox",
            capabilities=("composition", "implementation", "synthesis"),
        ),
        A2AContact(
            agent_uid="claude-code",
            kind=CONTACT_KIND_LOCAL_AGENT,
            display_name="claude-code",
            inbox_subject="dharma.agent.claude-code.inbox",
            capabilities=("review", "implementation", "synthesis"),
        ),
        A2AContact(
            agent_uid="hermes-m5",
            kind=CONTACT_KIND_LOCAL_AGENT,
            display_name="hermes-m5",
            inbox_subject="dharma.agent.hermes-m5.inbox",
            capabilities=("transport", "operator-contact", "coordination"),
        ),
        A2AContact(
            agent_uid="perplexity-computer",
            kind=CONTACT_KIND_CLOUD_AGENT,
            display_name="perplexity-computer",
            inbox_subject="dharma.a2a.cloud.perplexity-computer.inbox",
            capabilities=("research", "triage", "cross-agent-synthesis"),
            metadata={"first_cloud_agent": True},
        ),
    )


def default_contact_registry() -> ContactRegistry:
    return ContactRegistry(default_contacts())
