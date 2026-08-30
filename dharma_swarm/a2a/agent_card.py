"""A2A Agent Cards -- skill advertisement for dharma_swarm agents.

Each agent publishes a card describing what it can do.
Other agents (local or remote) discover skills via cards.

Implements the Agent Card per A2A 1.0 spec (Linux Foundation):
- AgentSkill with id, tags, examples, inputModes, outputModes, per-skill security
- SecuritySchemes map (APIKey, HTTPAuth, OAuth2, MutualTLS, OpenIdConnect)
- JWS signatures for card authenticity
- supportedInterfaces with protocolBinding declarations
- extensions[] for dharma-specific layers
- Registry for storing and querying cards
- Auto-generation from existing AgentIdentity / AgentConfig
- Persistence to ~/.dharma/a2a/cards/ as JSON files

Backward compat: AgentCapability is preserved as an alias for AgentSkill.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir

logger = logging.getLogger(__name__)

_DHARMA_HOME = dharma_state_dir("DHARMA_HOME")
_DEFAULT_CARDS_DIR = _DHARMA_HOME / "a2a" / "cards"

SEMANTIC_OBJECT_A2A_CARD = "A2ACard"
SEMANTIC_OBJECT_AGENT_UID = "AgentUID"
SEMANTIC_OBJECT_NATS_SUBSTRATE = "NATSSubstrate"
SEMANTIC_OBJECT_A2A_INBOX_ROUTE = "A2AInboxRoute"
A2A_INBOX_ROUTE_ALIAS = "agent-inbox"

AGENT_UID_ALIASES = {
    "codex": "codex_composer",
    "opus": "opus_composer",
    "hermes": "hermes-m5",
    "hermes_m5": "hermes-m5",
    "devin": "devin-roaming-2987d222",
    "fable-5-cursor": "fable_5_cursor",
    "fable-claude-code": "fable_claude_code",
    "fable-composer": "fable_composer",
    "perplexity": "perplexity-computer",
    "codex-rsi-lab-manager": "codex_rsi_lab_manager",
    "codex-rsi-lab": "codex_rsi_lab_manager",
    "codex-rsi": "codex_rsi_lab_manager",
    "rsi-lab-manager": "codex_rsi_lab_manager",
    "rsi_lab_manager": "codex_rsi_lab_manager",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_internal(obj: Any) -> None:
    """Recursively remove internal fields (prefixed with _) from dicts."""
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if key.startswith("_"):
                del obj[key]
            else:
                _strip_internal(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            _strip_internal(item)


def _validate_subject_token(token: str, *, label: str) -> str:
    cleaned = (token or "").strip()
    forbidden = {".", "*", ">", "/", "\\"}
    if not cleaned or any(char.isspace() or char in forbidden for char in cleaned):
        raise ValueError(f"invalid {label} for NATS subject: {cleaned!r}")
    return cleaned


def resolve_agent_uid(name: str, *, agent_uid: str = "") -> str:
    """Resolve a display/card name into the stable AgentUID subject token."""
    raw = agent_uid or AGENT_UID_ALIASES.get(name, name)
    return _validate_subject_token(raw, label="agent uid")


def a2a_inbox_subject(agent_uid: str) -> str:
    return f"dharma.agent.{resolve_agent_uid(agent_uid)}.inbox"


@dataclass(frozen=True)
class A2AInboxRoute:
    """Semantic Commons internal contact route for durable fleet transport."""

    agent_uid: str
    route: str = A2A_INBOX_ROUTE_ALIAS
    substrate: str = SEMANTIC_OBJECT_NATS_SUBSTRATE

    @property
    def subject(self) -> str:
        return a2a_inbox_subject(self.agent_uid)

    @property
    def ack_subject(self) -> str:
        return f"{self.subject}.ack.{{packet_id}}"

    @property
    def reply_subject(self) -> str:
        return f"{self.subject}.reply.{{packet_id}}"

    def to_dict(self) -> dict[str, str]:
        return {
            "route": self.route,
            "substrate": self.substrate,
            "agent_uid": resolve_agent_uid(self.agent_uid),
            "subject": self.subject,
            "ack_subject": self.ack_subject,
            "reply_subject": self.reply_subject,
        }

    def to_supported_interface(self) -> dict[str, str]:
        return {
            "protocolBinding": SEMANTIC_OBJECT_A2A_INBOX_ROUTE,
            **self.to_dict(),
        }


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class SecurityScheme:
    """A2A 1.0 security scheme declaration (card-level metadata only).

    Maps to the spec's securitySchemes object.  These declarations
    advertise which auth mechanisms the agent *accepts* but do NOT
    enforce them at runtime.  Enforcement is handled by the transport
    layer (NodeGateway ``_verify_api_key`` for APIKey).

    Currently enforced:
        - APIKey via X-A2A-Key header (NodeGateway)

    Declared but not yet enforced (TODO — Tier 2):
        - OAuth2 (PKCE flows)
        - HTTPAuth (Bearer / Basic)
        - MutualTLS
        - OpenIdConnect
        - JWS card signatures
    """

    scheme_type: str = "APIKey"  # APIKey, HTTPAuth, OAuth2, MutualTLS, OpenIdConnect
    in_field: str = "header"  # header, query, cookie
    name: str = "X-A2A-Key"  # header/param name
    description: str = ""
    flows: dict[str, Any] = field(default_factory=dict)  # OAuth2 flows


@dataclass
class AgentSkill:
    """A single skill that an agent advertises (A2A 1.0 spec name).

    Field order preserves backward compat with AgentCapability(name, description).

    Attributes:
        name: Human-readable short name (also used as id if id is empty).
        description: What this skill does.
        input_modes: Accepted input types (e.g., ["text", "file", "data"]).
        output_modes: Produced output types.
        id: Unique skill identifier (defaults to name if empty).
        tags: Searchable tags for discovery.
        examples: Example invocations or descriptions.
        security_requirements: Per-skill security scheme references.
    """

    name: str = ""
    description: str = ""
    input_modes: list[str] = field(default_factory=lambda: ["text"])
    output_modes: list[str] = field(default_factory=lambda: ["text"])
    id: str = ""
    tags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    security_requirements: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.name

    def matches(self, query: str) -> bool:
        """Match against name, description, and tags (case-insensitive)."""
        q = query.lower()
        if q in self.name.lower() or q in self.description.lower():
            return True
        return any(q in tag.lower() for tag in self.tags)


# Backward compatibility alias
AgentCapability = AgentSkill


@dataclass
class AgentCard:
    """A2A Agent Card -- structured metadata describing an agent.

    A2A 1.0 spec conformant with skills, security schemes, signatures,
    supported interfaces, and extensions.

    Attributes:
        name: Unique agent identifier within the swarm.
        agent_uid: Stable durable AgentUID used in internal NATS subjects.
        description: What this agent does (1-2 sentences).
        skills: List of advertised skills (A2A 1.0 spec name).
        endpoint: For remote agents, the HTTP URL. For local, "local://".
        auth_type: Authentication method (backward compat shorthand).
        security_schemes: A2A 1.0 security scheme declarations.
        signatures: JWS-signed card authenticity proofs.
        supported_interfaces: Protocol binding declarations.
        extensions: A2A 1.0 extension URIs.
        role: Agent role from dharma_swarm.
        model: LLM model identifier.
        provider: LLM provider.
        status: Current agent status.
        version: Card schema version.
        created_at: ISO-8601 timestamp of card creation.
        updated_at: ISO-8601 timestamp of last update.
        metadata: Arbitrary extra data.
    """

    name: str
    agent_uid: str = ""
    description: str = ""
    skills: list[AgentSkill] = field(default_factory=list)
    capabilities: list[AgentSkill] = field(default_factory=list)
    endpoint: str = "local://"
    auth_type: str = "none"
    security_schemes: list[SecurityScheme] = field(default_factory=list)
    signatures: list[str] = field(default_factory=list)
    supported_interfaces: list[dict[str, str]] = field(default_factory=list)
    extensions: list[dict[str, Any]] = field(default_factory=list)
    role: str = "general"
    model: str = ""
    provider: str = ""
    status: str = "idle"
    version: str = "1.0"
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Merge capabilities into skills for backward compat
        if self.capabilities and not self.skills:
            self.skills = self.capabilities
        self.capabilities = self.skills

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-safe dict."""
        d = asdict(self)
        _strip_internal(d)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentCard:
        """Deserialize from dict, handling nested skills/capabilities."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        skill_fields = {f.name for f in AgentSkill.__dataclass_fields__.values()}
        sec_fields = {f.name for f in SecurityScheme.__dataclass_fields__.values()}
        filtered: dict[str, Any] = {}

        # Accept both "skills" and legacy "capabilities" key
        raw_skills = data.get("skills") or data.get("capabilities") or []

        for k, v in data.items():
            if k == "capabilities":
                continue  # handled via raw_skills above
            if k not in known_fields:
                continue
            if k == "skills" and isinstance(v, list):
                continue  # handled via raw_skills below
            if k == "security_schemes" and isinstance(v, list):
                schemes = []
                for item in v:
                    if isinstance(item, dict):
                        schemes.append(SecurityScheme(
                            **{sk: sv for sk, sv in item.items() if sk in sec_fields}
                        ))
                    elif isinstance(item, SecurityScheme):
                        schemes.append(item)
                filtered[k] = schemes
            else:
                filtered[k] = v

        # Parse skills
        skills: list[AgentSkill] = []
        for item in raw_skills:
            if isinstance(item, dict):
                skills.append(AgentSkill(
                    **{sk: sv for sk, sv in item.items() if sk in skill_fields}
                ))
            elif isinstance(item, AgentSkill):
                skills.append(item)
        filtered["skills"] = skills

        return cls(**filtered)

    @classmethod
    def from_agent_identity(cls, identity: dict[str, Any]) -> AgentCard:
        """Generate an AgentCard from an existing AgentIdentity dict.

        Maps role -> capabilities heuristically. This is the bridge between
        the existing agent_registry.py and the A2A protocol.
        """
        name = identity.get("name", "unknown")
        role = identity.get("role", "general")
        model = identity.get("model", "")
        prompt = identity.get("system_prompt", "")

        # Derive description from system prompt (first sentence or fallback)
        description = ""
        if prompt:
            # Take first sentence (up to 200 chars)
            for end_char in (".", "\n"):
                idx = prompt.find(end_char)
                if 0 < idx <= 200:
                    description = prompt[:idx + 1].strip()
                    break
            if not description:
                description = prompt[:200].strip()
        if not description:
            description = f"{role} agent in dharma_swarm"

        # Derive skills from role
        skills = _skills_for_role(role)

        return cls(
            name=name,
            agent_uid=str(identity.get("agent_uid") or identity.get("uid") or name),
            description=description,
            skills=skills,
            role=role,
            model=model,
            status=identity.get("status", "idle"),
            metadata={
                "tasks_completed": identity.get("tasks_completed", 0),
                "tasks_failed": identity.get("tasks_failed", 0),
                "avg_quality": identity.get("avg_quality", 0.0),
            },
        ).standardize_internal_contact()

    def has_capability(self, query: str) -> bool:
        """Check if this agent has a capability matching the query."""
        return any(cap.matches(query) for cap in self.capabilities)

    def capability_names(self) -> list[str]:
        """Return list of capability name strings."""
        return [cap.name for cap in self.capabilities]

    def a2a_inbox_route(self) -> A2AInboxRoute:
        """Return the canonical Semantic Commons internal inbox route."""
        return A2AInboxRoute(resolve_agent_uid(self.name, agent_uid=self.agent_uid))

    def standardize_internal_contact(self) -> AgentCard:
        """Project this card onto AgentUID + A2AInboxRoute.

        Direct ``AgentCard(...)`` construction remains lightweight for tests and
        external-edge cards. Registry load/register paths call this so persisted
        fleet cards all expose the same internal NATS contact binding.
        """
        route = self.a2a_inbox_route()
        self.agent_uid = route.agent_uid
        self.supported_interfaces = _with_canonical_a2a_inbox_interface(
            self.supported_interfaces,
            route,
        )
        self.metadata = dict(self.metadata or {})
        self.metadata["agent_uid"] = route.agent_uid
        self.metadata["a2a_inbox_route"] = route.to_dict()
        self.metadata["semantic_commons"] = {
            "card": SEMANTIC_OBJECT_A2A_CARD,
            "agent_uid": SEMANTIC_OBJECT_AGENT_UID,
            "route": SEMANTIC_OBJECT_A2A_INBOX_ROUTE,
            "substrate": SEMANTIC_OBJECT_NATS_SUBSTRATE,
            "route_alias": A2A_INBOX_ROUTE_ALIAS,
        }
        return self


def _skill(sid: str, desc: str, tags: list[str]) -> AgentSkill:
    return AgentSkill(id=sid, name=sid, description=desc, tags=tags)


def _skills_for_role(role: str) -> list[AgentSkill]:
    """Map an agent role to a default set of skills."""
    role_lower = role.lower()
    _ROLE_MAP: dict[str, list[AgentSkill]] = {
        "coder": [_skill("code_generation", "Write, modify, and refactor code", ["code", "dev"]),
                  _skill("code_review", "Review code for bugs and improvements", ["review", "quality"]),
                  _skill("testing", "Write and run tests", ["test", "qa"])],
        "reviewer": [_skill("code_review", "Thorough code review with feedback", ["review", "quality"]),
                     _skill("security_review", "Check for security vulnerabilities", ["security", "audit"])],
        "researcher": [_skill("research", "Deep research and analysis", ["research", "analysis"]),
                       _skill("literature_review", "Review academic papers and docs", ["research", "review"]),
                       _skill("synthesis", "Synthesize information from multiple sources", ["synthesis", "integration"])],
        "tester": [_skill("testing", "Write and execute test suites", ["test", "qa"]),
                   _skill("verification", "Verify claims and results", ["verify", "audit"])],
        "orchestrator": [_skill("task_routing", "Route tasks to appropriate agents", ["orchestration", "routing"]),
                         _skill("coordination", "Coordinate multi-agent workflows", ["coordination", "workflow"]),
                         _skill("monitoring", "Monitor agent health and progress", ["monitoring", "health"])],
        "architect": [_skill("architecture", "Design system architecture", ["architecture", "design"]),
                      _skill("code_review", "Review architectural decisions", ["review", "architecture"])],
        "operator": [_skill("deployment", "Deploy and manage services", ["deploy", "ops"]),
                     _skill("monitoring", "System monitoring and alerting", ["monitoring", "ops"]),
                     _skill("infrastructure", "Manage infrastructure", ["infra", "ops"])],
        "witness": [_skill("observation", "Observe and record system state", ["observe", "witness"]),
                    _skill("reflection", "Reflect on system behavior patterns", ["reflect", "insight"])],
        "strategist": [_skill("strategic_planning", "High-level strategic analysis", ["strategy", "planning"]),
                       _skill("prioritization", "Prioritize tasks and goals", ["priority", "planning"])],
    }

    skills = _ROLE_MAP.get(role_lower, [])
    if not skills:
        skills = [
            AgentSkill(
                id=role_lower,
                name=role_lower,
                description=f"General {role_lower} capabilities",
                tags=[role_lower],
            )
        ]
    return skills


# Backward compatibility alias
_capabilities_for_role = _skills_for_role


def _with_canonical_a2a_inbox_interface(
    interfaces: list[dict[str, str]],
    route: A2AInboxRoute,
) -> list[dict[str, str]]:
    """Replace stale internal contact bindings with the canonical route."""
    preserved: list[dict[str, str]] = []
    for item in interfaces:
        if not isinstance(item, dict):
            continue
        if _is_internal_contact_interface(item):
            continue
        preserved.append(dict(item))
    preserved.append(route.to_supported_interface())
    return preserved


def _is_internal_contact_interface(interface: dict[str, Any]) -> bool:
    binding = str(interface.get("protocolBinding") or interface.get("protocol_binding") or "")
    route = str(interface.get("route") or "")
    subject = str(interface.get("subject") or "")
    if binding == SEMANTIC_OBJECT_A2A_INBOX_ROUTE:
        return True
    if route == A2A_INBOX_ROUTE_ALIAS:
        return True
    if subject.startswith("dharma.agent.") and subject.endswith(".inbox"):
        return True
    if subject.startswith("dharma.a2a."):
        return True
    return False


# ---------------------------------------------------------------------------
# Card Registry
# ---------------------------------------------------------------------------


class CardRegistry:
    """Registry for storing, retrieving, and discovering Agent Cards.

    Cards are stored in-memory and persisted to JSON files on disk.
    Supports capability-based discovery queries.

    Attributes:
        cards_dir: Path to directory where cards are persisted.
    """

    def __init__(self, cards_dir: Path | None = None) -> None:
        self.cards_dir = cards_dir or _DEFAULT_CARDS_DIR
        self.cards_dir.mkdir(parents=True, exist_ok=True)
        self._cards: dict[str, AgentCard] = {}
        self._load_from_disk()

    # -- persistence ---------------------------------------------------------

    def _card_path(self, name: str) -> Path:
        """Path to a card's JSON file on disk."""
        # Sanitize name for filesystem safety
        safe_name = name.replace("/", "_").replace("\\", "_")
        return self.cards_dir / f"{safe_name}.json"

    def _load_from_disk(self) -> None:
        """Load all cards from the cards directory."""
        if not self.cards_dir.exists():
            return
        for path in sorted(self.cards_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                card = AgentCard.from_dict(data).standardize_internal_contact()
                self._cards[card.name] = card
            except Exception as exc:
                logger.warning("Failed to load card %s: %s", path, exc)

    def _persist_card(self, card: AgentCard) -> None:
        """Write a single card to disk."""
        path = self._card_path(card.name)
        try:
            path.write_text(
                json.dumps(card.to_dict(), indent=2, default=str) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Failed to persist card %s: %s", card.name, exc)

    # -- registration --------------------------------------------------------

    def register(self, card: AgentCard) -> None:
        """Register or update an agent card.

        Persists to disk immediately.
        """
        card.standardize_internal_contact()
        card.updated_at = _utc_now_iso()
        self._cards[card.name] = card
        self._persist_card(card)
        logger.info("Registered A2A card: %s (%s)", card.name, card.role)

    def unregister(self, name: str) -> bool:
        """Remove an agent card. Returns True if card existed."""
        if name not in self._cards:
            return False
        del self._cards[name]
        path = self._card_path(name)
        if path.exists():
            path.unlink()
        logger.info("Unregistered A2A card: %s", name)
        return True

    # -- retrieval -----------------------------------------------------------

    def get(self, name: str) -> AgentCard | None:
        """Get a card by agent name."""
        direct = self._cards.get(name)
        if direct is not None:
            return direct
        try:
            agent_uid = resolve_agent_uid(name)
        except ValueError:
            return None
        by_uid = self._cards.get(agent_uid)
        if by_uid is not None:
            return by_uid
        for card in self._cards.values():
            if card.agent_uid == agent_uid:
                return card
        return None

    def resolve_a2a_inbox_route(self, name: str) -> A2AInboxRoute | None:
        """Resolve a card/display name to the canonical A2AInboxRoute."""
        card = self.get(name)
        if card is None:
            return None
        return card.a2a_inbox_route()

    def list_all(self) -> list[AgentCard]:
        """Return all registered cards, sorted by name."""
        return sorted(self._cards.values(), key=lambda c: c.name)

    def count(self) -> int:
        """Number of registered cards."""
        return len(self._cards)

    # -- discovery -----------------------------------------------------------

    def discover(self, capability: str) -> list[AgentCard]:
        """Find agents that have a matching capability.

        Args:
            capability: Search query matched against capability names
                and descriptions (case-insensitive substring).

        Returns:
            List of matching AgentCards, sorted by name.
        """
        matches = [
            card
            for card in self._cards.values()
            if card.has_capability(capability)
        ]
        return sorted(matches, key=lambda c: c.name)

    def discover_by_role(self, role: str) -> list[AgentCard]:
        """Find agents with a specific role.

        Args:
            role: Role string to match (case-insensitive).

        Returns:
            List of matching AgentCards.
        """
        role_lower = role.lower()
        return sorted(
            [c for c in self._cards.values() if c.role.lower() == role_lower],
            key=lambda c: c.name,
        )

    def discover_available(self) -> list[AgentCard]:
        """Find agents that are currently available (not busy/dead)."""
        return sorted(
            [c for c in self._cards.values() if c.status in ("idle", "starting")],
            key=lambda c: c.name,
        )

    # -- bulk operations -----------------------------------------------------

    def register_from_agent_registry(
        self,
        agents: list[dict[str, Any]],
    ) -> int:
        """Generate and register cards from a list of AgentIdentity dicts.

        This bridges the existing agent_registry.py to A2A.

        Args:
            agents: List of identity dicts (from AgentRegistry.list_agents()).

        Returns:
            Number of cards registered.
        """
        count = 0
        for identity in agents:
            try:
                card = AgentCard.from_agent_identity(identity)
                self.register(card)
                count += 1
            except Exception as exc:
                name = identity.get("name", "<unknown>")
                logger.warning("Failed to create card for %s: %s", name, exc)
        logger.info("Registered %d A2A cards from agent registry.", count)
        return count

    def sync_status(self, name: str, status: str) -> None:
        """Update the status of a registered card (e.g., idle -> busy).

        No-op if the card doesn't exist.
        """
        card = self._cards.get(name)
        if card is not None:
            card.status = status
            card.updated_at = _utc_now_iso()
            self._persist_card(card)
