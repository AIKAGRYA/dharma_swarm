"""Pydantic models for CashClaw read-only live market intake.

These schemas describe public/source-backed intelligence collection about
agentic builder patterns. They do not fetch URLs, send outreach, mutate revenue
state, or touch payment rails.
"""

from __future__ import annotations

import ipaddress
import re
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dharma_swarm.revenue.action_gateway_models import canonical_hash, utc_now_iso


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class LiveIntakeSourceType(str, Enum):
    """Public source categories supported by the intake schema."""

    LOCAL_FIXTURE = "local_fixture"
    GITHUB = "github"
    HACKER_NEWS = "hacker_news"
    REDDIT = "reddit"
    YOUTUBE = "youtube"
    MARKETPLACE = "marketplace"
    FORUM = "forum"
    SOCIAL = "social"
    BLOG = "blog"
    DOCS = "docs"
    NEWSLETTER = "newsletter"
    JOB_BOARD = "job_board"
    PUBLIC_DATASET = "public_dataset"
    GO_ARCHIVE = "go_archive"
    OTHER = "other"


class LiveIntakeFreshness(str, Enum):
    """Freshness state for a fetched or extracted evidence item."""

    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


class LiveIntakeRiskLevel(str, Enum):
    """Conservative license, terms, or operational risk label."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class LiveIntakeExtractionMethod(str, Enum):
    """How evidence was converted into an intake item or pattern card."""

    MANUAL = "manual"
    HTML_TEXT = "html_text"
    API_JSON = "api_json"
    RSS = "rss"
    SNAPSHOT = "snapshot"
    STRUCTURED_PARSE = "structured_parse"
    OTHER = "other"


def live_intake_content_hash(content: Any) -> str:
    """Return the deterministic canonical hash used for evidence content."""

    return canonical_hash(content)


def live_intake_id(prefix: str, payload: Any) -> str:
    """Build a short deterministic identifier from canonical payload content."""

    safe_prefix = re.sub(r"[^a-z0-9_]+", "_", prefix.lower()).strip("_") or "lintake"
    return f"{safe_prefix}_{canonical_hash(payload)[-24:]}"


class _LiveIntakeReadOnlyModel(BaseModel):
    """Base model with strict schema and read-only side-effect invariant."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    no_external_side_effects: bool = True

    @model_validator(mode="after")
    def _validate_read_only(self) -> "_LiveIntakeReadOnlyModel":
        if self.no_external_side_effects is not True:
            raise ValueError("live intake models must remain read-only")
        return self


class _LiveIntakeEvidenceModel(_LiveIntakeReadOnlyModel):
    """Common evidence provenance, freshness, terms, and extraction fields."""

    source_type: LiveIntakeSourceType
    url: str
    fetched_at: str = Field(default_factory=utc_now_iso)
    content_hash: str
    freshness: LiveIntakeFreshness = LiveIntakeFreshness.UNKNOWN
    license_risk: LiveIntakeRiskLevel = LiveIntakeRiskLevel.UNKNOWN
    terms_risk: LiveIntakeRiskLevel = LiveIntakeRiskLevel.UNKNOWN
    extraction_method: LiveIntakeExtractionMethod = LiveIntakeExtractionMethod.OTHER

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        return _validate_public_url(value, field_name="url")

    @field_validator("content_hash")
    @classmethod
    def _validate_content_hash(cls, value: str) -> str:
        normalized = value.strip()
        if not SHA256_RE.fullmatch(normalized):
            raise ValueError("content_hash must be sha256:<64 lowercase hex chars>")
        return normalized


class LiveIntakeSourceConfig(_LiveIntakeReadOnlyModel):
    """Configuration for one governed public read source."""

    schema_version: str = "cashclaw_live_source_config.v1"
    source_config_id: str
    source_type: LiveIntakeSourceType
    url: str
    label: str = ""
    adapter_name: str = ""
    freshness_window_hours: int = Field(default=168, ge=1)
    extraction_method: LiveIntakeExtractionMethod = LiveIntakeExtractionMethod.OTHER
    license_risk: LiveIntakeRiskLevel = LiveIntakeRiskLevel.UNKNOWN
    terms_risk: LiveIntakeRiskLevel = LiveIntakeRiskLevel.UNKNOWN
    terms_url: str = ""
    local_path: str = ""
    host_allowlist: list[str] = Field(default_factory=list)
    max_bytes: int = Field(default=1_000_000, ge=1, le=10_000_000)
    allowed_use: str = "read_only_public_market_intelligence"
    enabled: bool = True
    network_enabled: bool = False
    notes: str = ""

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        return _validate_public_url(value, field_name="url")

    @field_validator("terms_url")
    @classmethod
    def _validate_terms_url(cls, value: str) -> str:
        if not value.strip():
            return ""
        return _validate_public_url(value, field_name="terms_url")

    @model_validator(mode="after")
    def _validate_source_config(self) -> "LiveIntakeSourceConfig":
        if self.source_type in {LiveIntakeSourceType.LOCAL_FIXTURE, LiveIntakeSourceType.GO_ARCHIVE}:
            if not self.local_path.strip():
                raise ValueError("local source requires local_path")
        if self.network_enabled:
            parsed = urlparse(self.url)
            host = (parsed.hostname or "").strip().lower()
            if not self.host_allowlist or host not in {item.lower() for item in self.host_allowlist}:
                raise ValueError("network source requires explicit host allowlist containing url host")
        if self.source_type in {LiveIntakeSourceType.REDDIT, LiveIntakeSourceType.YOUTUBE} and self.network_enabled:
            if self.terms_risk != LiveIntakeRiskLevel.LOW:
                raise ValueError("reddit/youtube network sources require explicit low terms_risk approval")
        return self

    @property
    def source_config_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


class LiveIntakeSourceItem(_LiveIntakeEvidenceModel):
    """One fetched public item that can support a market pattern claim."""

    schema_version: str = "cashclaw_live_source_item.v1"
    source_item_id: str
    source_config_id: str = ""
    title: str = ""
    author_or_org: str = ""
    published_at: str = ""
    summary: str = ""
    evidence_ref: str = ""
    raw_excerpt: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def source_item_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


class LiveIntakePatternCard(_LiveIntakeEvidenceModel):
    """Extracted agentic builder pattern backed by source item references."""

    schema_version: str = "cashclaw_live_pattern_card.v1"
    pattern_card_id: str
    source_item_ids: list[str] = Field(default_factory=list, min_length=1)
    what_is_being_built: str = Field(min_length=1)
    buyer_pain: str = Field(min_length=1)
    buyer_segment: str = Field(min_length=1)
    tool_stack: list[str] = Field(default_factory=list)
    revenue_evidence: list[str] = Field(default_factory=list)
    pricing_evidence: list[str] = Field(default_factory=list)
    delivery_window_hours: int = Field(default=72, ge=1)
    dharma_experiment: str = ""
    risks: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list, min_length=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_source_backing(self) -> "LiveIntakePatternCard":
        if not self.source_item_ids:
            raise ValueError("pattern card requires at least one source_item_id")
        if not self.evidence_refs:
            raise ValueError("pattern card requires at least one evidence_ref")
        return self

    @property
    def pattern_card_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


class LiveIntakeAdapterReceipt(_LiveIntakeEvidenceModel):
    """Receipt emitted by an adapter after a governed read-only intake step."""

    schema_version: str = "cashclaw_live_adapter_receipt.v1"
    receipt_id: str
    run_id: str = ""
    adapter_name: str
    source_config_id: str = ""
    started_at: str = Field(default_factory=utc_now_iso)
    finished_at: str = ""
    duration_seconds: float = Field(default=0.0, ge=0.0)
    items_seen: int = Field(default=0, ge=0)
    source_items_emitted: int = Field(default=0, ge=0)
    pattern_cards_emitted: int = Field(default=0, ge=0)
    outreach_attempted: bool = False
    payments_attempted: bool = False
    external_side_effects_performed: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_no_side_effect_receipt(self) -> "LiveIntakeAdapterReceipt":
        if self.external_side_effects_performed:
            raise ValueError("live intake adapter receipt cannot include external side effects")
        if self.outreach_attempted:
            raise ValueError("live intake adapter receipt cannot include outreach attempts")
        if self.payments_attempted:
            raise ValueError("live intake adapter receipt cannot include payment attempts")
        return self

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


class LiveIntakeRunResult(_LiveIntakeReadOnlyModel):
    """Result envelope for one governed read-only live intake run."""

    schema_version: str = "cashclaw_live_intake_run_result.v1"
    run_id: str
    started_at: str = Field(default_factory=utc_now_iso)
    finished_at: str = ""
    source_configs: list[LiveIntakeSourceConfig] = Field(default_factory=list)
    source_items: list[LiveIntakeSourceItem] = Field(default_factory=list)
    pattern_cards: list[LiveIntakePatternCard] = Field(default_factory=list)
    adapter_receipts: list[LiveIntakeAdapterReceipt] = Field(default_factory=list)
    top_pattern_card_ids: list[str] = Field(default_factory=list)
    network_reads_performed: bool = False
    blocked_sources: int = 0
    outreach_attempted: bool = False
    payments_attempted: bool = False
    external_side_effects_performed: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_run_invariants(self) -> "LiveIntakeRunResult":
        if self.external_side_effects_performed:
            raise ValueError("live intake run cannot include external side effects")
        if self.outreach_attempted:
            raise ValueError("live intake run cannot include outreach attempts")
        if self.payments_attempted:
            raise ValueError("live intake run cannot include payment attempts")
        if self.network_reads_performed:
            for config in self.source_configs:
                if config.network_enabled and not config.host_allowlist:
                    raise ValueError("network reads require allowlisted source configs")
        for receipt in self.adapter_receipts:
            if receipt.no_external_side_effects is not True:
                raise ValueError("adapter receipt must remain read-only")
        return self

    @property
    def source_count(self) -> int:
        return len(self.source_configs)

    @property
    def source_item_count(self) -> int:
        return len(self.source_items)

    @property
    def pattern_card_count(self) -> int:
        return len(self.pattern_cards)

    @property
    def run_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


def _validate_public_url(value: str, *, field_name: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError(f"{field_name} is required")
    parsed = urlparse(candidate)
    if parsed.scheme == "artifact":
        if not parsed.netloc:
            raise ValueError(f"{field_name} artifact URL requires a namespace")
        return candidate
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must be an http(s) or artifact URL")
    host = (parsed.hostname or "").strip().lower()
    if _host_is_private_or_local(host):
        raise ValueError(f"{field_name} cannot target local or private hosts")
    return candidate


def _host_is_private_or_local(host: str) -> bool:
    if host in {"localhost", "0.0.0.0"} or host.endswith(".localhost"):
        return True
    try:
        parsed = ipaddress.ip_address(host)
    except ValueError:
        return False
    return parsed.is_private or parsed.is_loopback or parsed.is_link_local or parsed.is_reserved


__all__ = [
    "LiveIntakeAdapterReceipt",
    "LiveIntakeExtractionMethod",
    "LiveIntakeFreshness",
    "LiveIntakePatternCard",
    "LiveIntakeRiskLevel",
    "LiveIntakeRunResult",
    "LiveIntakeSourceConfig",
    "LiveIntakeSourceItem",
    "LiveIntakeSourceType",
    "live_intake_content_hash",
    "live_intake_id",
]
