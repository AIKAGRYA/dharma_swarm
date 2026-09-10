"""Typed bounded no-tools context; owner adapters issue every truth stamp."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import hashlib
import hmac
import json
import re
from types import MappingProxyType
from typing import Any, Final, TypeAlias
import unicodedata
HELM_CONTEXT_SCHEMA_VERSION: Final = "dharma.helm.context.v1"
HELM_CONTEXT_DIGEST_PREFIX: Final = "sha256:"
MAX_HELM_CONTEXT_BYTES: Final = 65_536
MAX_HELM_CONTEXT_STRING_CHARS: Final = 4_096
MAX_HELM_CONTEXT_KEY_CHARS: Final = 128
MAX_HELM_CONTEXT_COLLECTION_ITEMS: Final = 64
MAX_HELM_CONTEXT_DEPTH: Final = 8
MAX_HELM_CONTEXT_NODES: Final = 2_048
MAX_HELM_CONTEXT_INTEGER: Final = 9_007_199_254_740_991
MAX_HELM_CONTEXT_TTL_SECONDS: Final = 3_600
REDACTED_VALUE: Final = "[REDACTED]"
HELM_CONTEXT_REGIONS: Final = ("workspace", "bridge_session", "ui", "mission_control", "task_board", "runtime_state", "session", "receipts", "swarm", "a2a", "evolution", "actions")
HELM_NAVIGATION: Final = ("home", "conversation", "activity", "evidence", "system")
HELM_PLACES: Final = frozenset(HELM_NAVIGATION)
HELM_FACETS: Final = frozenset({"chat", "commands", "agents", "models", "evolution", "thinking", "tools", "timeline", "sessions", "approvals", "mission", "runtime", "repo", "ontology", "control"})
HELM_OVERLAYS: Final = frozenset({"none", "modelPicker", "paneSwitcher", "tour"})
HELM_FOCUSES: Final = frozenset({"composer", "navigation"})
_FACETS_BY_PLACE = {"home": {"mission", "control"}, "conversation": {"chat", "sessions"}, "activity": {"agents", "evolution", "thinking", "tools", "timeline", "approvals"}, "evidence": {"repo", "ontology"}, "system": {"commands", "models", "runtime"}}
JsonValue: TypeAlias = str | int | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
_SECRET_KEYS = frozenset({"access_key", "access_token", "api_key", "apikey", "authorization", "client_secret", "cookie", "credential", "openai_api_key", "password", "private_key", "provider_raw_metadata", "raw", "raw_metadata", "refresh_token", "response_headers", "secret", "secret_key", "session_cookie", "system_info", "token"})
_SECRET_KEY_SUFFIXES = ("_access_key", "_api_key", "_cookie", "_credential", "_password", "_private_key", "_secret", "_token")
_SECRET_KEY_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_SECRET_VALUE_PREFIXES = ("bearer ", "gho_", "ghp_", "github_pat_", "xai-", "xapp-", "xoxa-", "xoxc-", "xoxe-", "xoxr-", "xoxs-", "xoxb-", "xoxp-")
_RESERVED_PROJECTION_KEYS = frozenset({"authority", "authority_modality", "authority_stamp", "modality", "narration_verified", "provider_state_promotion", "state_promotion_allowed"})
_RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$")
_SECRET_VALUE = re.compile(
    r"(?i)(?:\bbearer\s+[a-z0-9._~+/=-]{8,}|\b(?:gh[oprsu]_|github_pat_|xapp-|xox[a-z]-)"
    r"[a-z0-9_-]{8,}|\b(?:xai-|AIza)[a-z0-9_-]{8,}|\bsk-(?:(?:or-v1|proj|ant|live|svcacct)-"
    r"[a-z0-9_-]{8,}|[a-z0-9]{20,})\b|\bAKIA[0-9A-Z]{16}\b|"
    r"https?://[^\s/@]*@|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
_NAVIGATION_KEYS = ("id", "label", "key", "command", "target_kind", "target_id", "resulting_place", "available")
_NAVIGATION_ROWS = (
    ("home", "Home (Control facet)", None, "open control", "facet", "control", "home", True),
    ("conversation", "Conversation", "Esc then Ctrl+G", "open chat", "facet", "chat", "conversation", True),
    ("activity", "Activity (Agents facet)", "Esc then Ctrl+A", "open agents", "facet", "agents", "activity", True),
    ("evidence", "Evidence (Repository facet)", "Esc then Ctrl+R", "open repo", "facet", "repo", "evidence", True),
    ("system", "System (Commands facet)", "Esc then Ctrl+M", "open commands", "facet", "commands", "system", True),
    ("face_toggle", "Quiet Field / Full Helm", "F2", "/cockpit", "face", None, None, True),
    ("pane_switcher", "Pane switcher", "Esc then Ctrl+K", None, "overlay", "paneSwitcher", None, True),
    ("model_picker", "Model picker", "Esc then Ctrl+P", "/model", "overlay", "modelPicker", None, True),
    ("receipts", "Receipts", None, None, "projection", "receipts", "evidence", False),
    ("inspector", "Inspector", None, None, "feature", "inspector", None, False),
)
class HelmContextError(ValueError):
    """The context failed its fail-closed transport contract."""
class AuthorityModality(StrEnum):
    OBSERVED = "observed"
    CONFIGURED = "configured"
    UNVERIFIED = "unverified"
    STALE = "stale"
    UNKNOWN = "unknown"
    HELD = "held"
class ProjectionStatus(StrEnum):
    OBSERVED = "observed"
    CONFIGURED = "configured"
    UNVERIFIED = "unverified"
    STALE = "stale"
    UNKNOWN = "unknown"
    HELD = "held"
    UNAVAILABLE = "unavailable"
def utc_now() -> datetime:
    return datetime.now(timezone.utc)
def format_rfc3339(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HelmContextError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
def parse_rfc3339(value: str, *, field_name: str = "timestamp") -> datetime:
    if not isinstance(value, str) or not value or len(value) > 64 or not _RFC3339.fullmatch(value):
        raise HelmContextError(f"{field_name} must use exact RFC3339 grammar")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        decoded = datetime.fromisoformat(candidate)
        if decoded.tzinfo is None or decoded.utcoffset() is None:
            raise HelmContextError(f"{field_name} must include a timezone")
        return decoded.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise HelmContextError(f"{field_name} must be RFC3339") from exc
def _bounded_text(value: Any, *, field_name: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise HelmContextError(f"{field_name} must be a string")
    if not allow_empty and not value:
        raise HelmContextError(f"{field_name} must not be empty")
    if "\x00" in value or len(value) > MAX_HELM_CONTEXT_STRING_CHARS:
        raise HelmContextError(f"{field_name} exceeds its string bound")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise HelmContextError(f"{field_name} contains a non-Unicode scalar") from exc
    if any(unicodedata.category(character) in {"Cc", "Cf"} for character in value):
        raise HelmContextError(f"{field_name} contains a control character")
    return value
def is_secret_key(key: str) -> bool:
    normalized = _SECRET_KEY_CAMEL_BOUNDARY.sub("_", key).casefold().replace("-", "_")
    return (
        normalized in _SECRET_KEYS
        or normalized.endswith(_SECRET_KEY_SUFFIXES)
        or "provider_raw" in normalized
    )
def looks_like_secret(value: str) -> bool:
    normalized = value.strip().casefold()
    return (
        bool(_SECRET_VALUE.search(value))
        or any(normalized.startswith(prefix) for prefix in _SECRET_VALUE_PREFIXES)
        or (normalized.startswith("eyj") and normalized.count(".") == 2)
    )
def _validate_json_value(
    value: Any, *, path: str, depth: int = 0, nodes: list[int] | None = None,
    reject_reserved: bool = False,
) -> JsonValue:
    nodes = nodes if nodes is not None else [0]
    nodes[0] += 1
    if nodes[0] > MAX_HELM_CONTEXT_NODES:
        raise HelmContextError("context exceeds the total node bound")
    if depth > MAX_HELM_CONTEXT_DEPTH:
        raise HelmContextError(f"{path} exceeds the nesting bound")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if abs(value) > MAX_HELM_CONTEXT_INTEGER:
            raise HelmContextError(f"{path} exceeds the safe integer bound")
        return value
    if isinstance(value, float):
        raise HelmContextError(f"{path} contains a float; bounded context uses integers")
    if isinstance(value, str):
        text = _bounded_text(value, field_name=path, allow_empty=True)
        if looks_like_secret(text):
            raise HelmContextError(f"{path} contains a secret-shaped value")
        return text
    if isinstance(value, Mapping):
        if len(value) > MAX_HELM_CONTEXT_COLLECTION_ITEMS:
            raise HelmContextError(f"{path} exceeds the mapping item bound")
        decoded: dict[str, JsonValue] = {}
        normalized_keys: set[str] = set()
        for key, item in value.items():
            if (
                not isinstance(key, str) or not key or len(key) > MAX_HELM_CONTEXT_KEY_CHARS
                or any(unicodedata.category(character) in {"Cc", "Cf"} for character in key)
            ):
                raise HelmContextError(f"{path} contains an invalid mapping key")
            try:
                key.encode("utf-8", errors="strict")
            except UnicodeError as exc:
                raise HelmContextError(f"{path} contains a non-Unicode mapping key") from exc
            normalized = key.casefold().replace("-", "_")
            if normalized in normalized_keys:
                raise HelmContextError(f"{path} contains a normalized key collision")
            normalized_keys.add(normalized)
            if reject_reserved and normalized in _RESERVED_PROJECTION_KEYS:
                raise HelmContextError(f"{path}.{key} attempts a state promotion")
            if is_secret_key(key):
                if item != REDACTED_VALUE:
                    raise HelmContextError(f"{path}.{key} contains unredacted secret data")
                decoded[key] = REDACTED_VALUE
            else:
                decoded[key] = _validate_json_value(
                    item, path=f"{path}.{key}", depth=depth + 1, nodes=nodes,
                    reject_reserved=reject_reserved,
                )
        return decoded
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) > MAX_HELM_CONTEXT_COLLECTION_ITEMS:
            raise HelmContextError(f"{path} exceeds the sequence item bound")
        return [
            _validate_json_value(
                item, path=f"{path}[{index}]", depth=depth + 1, nodes=nodes,
                reject_reserved=reject_reserved,
            )
            for index, item in enumerate(value)
        ]
    raise HelmContextError(f"{path} contains unsupported value {type(value).__name__}")
def _freeze(value: JsonValue) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value
def _thaw(value: Any) -> JsonValue:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_thaw(item) for item in value]
    return value
def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        missing, extra = sorted(expected - set(value)), sorted(set(value) - expected)
        raise HelmContextError(f"{label} keys mismatch: missing={missing}, extra={extra}")
@dataclass(frozen=True, slots=True)
class OperatorActionDescriptor:
    action_id: str
    label: str
    owner: str
    effects: tuple[str, ...]
    risk: str
    requires_approval: bool
    reversible: bool
    cancel_action_id: str | None = None
    def __post_init__(self) -> None:
        for name in ("action_id", "label", "owner", "risk"):
            if looks_like_secret(_bounded_text(getattr(self, name), field_name=f"action.{name}")):
                raise HelmContextError(f"action.{name} contains protected content")
        if not isinstance(self.effects, tuple) or not self.effects or len(self.effects) > MAX_HELM_CONTEXT_COLLECTION_ITEMS:
            raise HelmContextError("action effects exceed collection bound")
        for effect in self.effects:
            _bounded_text(effect, field_name="action.effects[]")
        if type(self.requires_approval) is not bool or type(self.reversible) is not bool:
            raise HelmContextError("action flags must be booleans")
        if self.risk not in {"safe_read", "workspace_mutation", "cross_boundary_mutation", "shell_or_network", "destructive"}:
            raise HelmContextError("action risk is invalid")
        if (self.risk != "safe_read" and not self.requires_approval) or self.reversible != (self.cancel_action_id is not None):
            raise HelmContextError("action approval or rollback semantics are invalid")
        if self.cancel_action_id is not None:
            _bounded_text(self.cancel_action_id, field_name="action.cancel_action_id")
    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "action_id": self.action_id, "label": self.label, "owner": self.owner,
            "effects": list(self.effects), "risk": self.risk,
            "requires_approval": self.requires_approval, "reversible": self.reversible,
            "cancel_action_id": self.cancel_action_id,
        }
@dataclass(frozen=True, slots=True)
class HelmUIState:
    face: str
    place: str
    facet: str
    overlay: str
    keyboard_focus: str
    available_navigation: tuple[str, ...]
    def __post_init__(self) -> None:
        for name in ("face", "place", "facet", "overlay", "keyboard_focus"):
            _bounded_text(getattr(self, name), field_name=f"ui.{name}")
        face_ok = self.face in {"zen", "cockpit", "scroll"} or (
            self.face.startswith("deck-focus:")
            and self.face.removeprefix("deck-focus:") in HELM_FACETS
        )
        if (
            not face_ok or self.place not in HELM_PLACES or self.facet not in HELM_FACETS
            or self.facet not in _FACETS_BY_PLACE[self.place]
            or self.overlay not in HELM_OVERLAYS or self.keyboard_focus not in HELM_FOCUSES
            or tuple(self.available_navigation) != HELM_NAVIGATION
        ):
            raise HelmContextError("ui coordinates are outside the canonical Helm contract")
        object.__setattr__(self, "available_navigation", tuple(self.available_navigation))
    def to_dict(self) -> dict[str, JsonValue]:
        items = [dict(zip(_NAVIGATION_KEYS, row, strict=True)) for row in _NAVIGATION_ROWS]
        return {
            "face": self.face, "place": self.place, "facet": self.facet,
            "overlay": self.overlay, "keyboard_focus": self.keyboard_focus,
            "navigation": {"items": items, "total": len(items), "truncated": False},
        }
@dataclass(frozen=True, slots=True)
class AuthorityStamp:
    modality: AuthorityModality
    owner: str
    source: str
    observed_at: str
    expires_at: str | None
    runtime_epoch: str
    def __post_init__(self) -> None:
        if not isinstance(self.modality, AuthorityModality):
            raise HelmContextError("authority modality must be typed")
        for name in ("owner", "source", "runtime_epoch"):
            value = _bounded_text(getattr(self, name), field_name=f"authority.{name}")
            if looks_like_secret(value):
                raise HelmContextError("authority metadata contains secret-shaped text")
        if len(self.runtime_epoch) > MAX_HELM_CONTEXT_KEY_CHARS:
            raise HelmContextError("authority.runtime_epoch exceeds its bound")
        observed = parse_rfc3339(self.observed_at, field_name="authority.observed_at")
        if self.expires_at is not None and not timedelta(0) < parse_rfc3339(self.expires_at, field_name="authority.expires_at") - observed <= timedelta(seconds=MAX_HELM_CONTEXT_TTL_SECONDS):
            raise HelmContextError("authority expiry is outside its freshness bound")
    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "modality": self.modality.value, "owner": self.owner, "source": self.source,
            "observed_at": self.observed_at, "expires_at": self.expires_at,
            "runtime_epoch": self.runtime_epoch,
        }
    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AuthorityStamp:
        _exact_keys(value, {"modality", "owner", "source", "observed_at", "expires_at", "runtime_epoch"}, "authority")
        try:
            modality = AuthorityModality(value["modality"])
        except (TypeError, ValueError) as exc:
            raise HelmContextError("unknown authority modality") from exc
        expiry = value["expires_at"]
        if expiry is not None and not isinstance(expiry, str):
            raise HelmContextError("authority.expires_at must be a string or null")
        return cls(modality, value["owner"], value["source"], value["observed_at"], expiry, value["runtime_epoch"])
@dataclass(frozen=True, slots=True)
class HelmProjection:
    region: str
    status: ProjectionStatus
    authority: AuthorityStamp
    data: Mapping[str, JsonValue]
    unavailable_reason: str | None = None
    def __post_init__(self) -> None:
        if self.region not in HELM_CONTEXT_REGIONS or not isinstance(self.status, ProjectionStatus):
            raise HelmContextError("projection region or status is invalid")
        validated = _validate_json_value(
            self.data, path=f"projections.{self.region}.data", reject_reserved=True,
        )
        if not isinstance(validated, dict):
            raise HelmContextError("projection data must be an object")
        object.__setattr__(self, "data", _freeze(validated))
        if self.status is ProjectionStatus.UNAVAILABLE:
            reason = _bounded_text(
                self.unavailable_reason, field_name=f"projections.{self.region}.unavailable_reason",
            )
            if looks_like_secret(reason) or self.authority.modality is not AuthorityModality.UNKNOWN or self.data:
                raise HelmContextError("unavailable projection is inconsistent")
        elif self.unavailable_reason is not None or self.authority.modality.value != self.status.value:
            raise HelmContextError("projection status and authority diverge")
        else:
            from .helm_context_projection import validate_helm_region_data
            validate_helm_region_data(self.region, validated)
    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "region": self.region, "status": self.status.value,
            "authority": self.authority.to_dict(), "data": _thaw(self.data),
            "unavailable_reason": self.unavailable_reason,
        }
    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> HelmProjection:
        _exact_keys(value, {"region", "status", "authority", "data", "unavailable_reason"}, "projection")
        if not isinstance(value["authority"], Mapping) or not isinstance(value["data"], Mapping):
            raise HelmContextError("projection authority and data must be objects")
        try:
            status = ProjectionStatus(value["status"])
        except (TypeError, ValueError) as exc:
            raise HelmContextError("unknown projection status") from exc
        reason = value["unavailable_reason"]
        if reason is not None and not isinstance(reason, str):
            raise HelmContextError("projection unavailable_reason must be string or null")
        return cls(value["region"], status, AuthorityStamp.from_dict(value["authority"]), value["data"], reason)
@dataclass(frozen=True, slots=True)
class HelmContextEnvelope:
    schema_version: str
    generated_at: str
    expires_at: str
    runtime_epoch: str
    synthetic: bool
    projections: Mapping[str, HelmProjection]
    context_digest: str = ""
    provider_state_promotion: bool = False
    def __post_init__(self) -> None:
        if self.schema_version != HELM_CONTEXT_SCHEMA_VERSION:
            raise HelmContextError("unsupported Helm context schema version")
        generated = parse_rfc3339(self.generated_at, field_name="generated_at")
        expires = parse_rfc3339(self.expires_at, field_name="expires_at")
        if not timedelta(0) < expires - generated <= timedelta(seconds=MAX_HELM_CONTEXT_TTL_SECONDS):
            raise HelmContextError("envelope expiry is outside the freshness bound")
        epoch = _bounded_text(self.runtime_epoch, field_name="runtime_epoch")
        if len(epoch) > MAX_HELM_CONTEXT_KEY_CHARS or looks_like_secret(epoch):
            raise HelmContextError("runtime_epoch exceeds its bound")
        if type(self.synthetic) is not bool or not isinstance(self.context_digest, str):
            raise HelmContextError("synthetic or context digest has invalid type")
        if self.provider_state_promotion is not False:
            raise HelmContextError("provider narrative cannot promote runtime state")
        if set(self.projections) != set(HELM_CONTEXT_REGIONS):
            raise HelmContextError("envelope must contain every exact projection region")
        normalized: dict[str, HelmProjection] = {}
        nodes = [0]
        for region in HELM_CONTEXT_REGIONS:
            projection = self.projections[region]
            if not isinstance(projection, HelmProjection) or projection.region != region:
                raise HelmContextError(f"projection region mismatch for {region}")
            if projection.status in {ProjectionStatus.OBSERVED, ProjectionStatus.CONFIGURED, ProjectionStatus.HELD, ProjectionStatus.UNAVAILABLE} and projection.authority.runtime_epoch != epoch:
                raise HelmContextError(f"current projection {region} has a runtime epoch mismatch")
            observed = parse_rfc3339(projection.authority.observed_at)
            expiry = parse_rfc3339(projection.authority.expires_at) if projection.authority.expires_at else None
            if observed > generated:
                raise HelmContextError(f"projection {region} observation is in the future")
            expired = expiry is not None and expiry <= generated
            if (projection.status is ProjectionStatus.STALE) != expired:
                raise HelmContextError(f"projection {region} has inconsistent freshness")
            if expiry is not None and (projection.status is ProjectionStatus.UNAVAILABLE or expiry > expires):
                raise HelmContextError(f"projection {region} expiry is outside the envelope")
            _validate_json_value(projection.data, path=f"projections.{region}.data", nodes=nodes, reject_reserved=True)
            from .helm_context_projection import validate_helm_region_authority, validate_helm_region_times
            validate_helm_region_authority(region, projection.status, projection.authority, self.synthetic)
            if projection.status is not ProjectionStatus.UNAVAILABLE:
                validate_helm_region_times(region, projection.data, observed, generated)
            normalized[region] = projection
        object.__setattr__(self, "projections", MappingProxyType(normalized))
        if self.context_digest:
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.context_digest):
                raise HelmContextError("context digest is malformed")
    def usable_at(self, now: datetime) -> bool:
        if now.tzinfo is None or now.utcoffset() is None:
            raise HelmContextError("freshness check time must be timezone-aware")
        instant = now.astimezone(timezone.utc)
        if not parse_rfc3339(self.generated_at) <= instant < parse_rfc3339(self.expires_at):
            return False
        route_usable = (bridge := self.projections["bridge_session"]).status is ProjectionStatus.UNAVAILABLE or bridge.data.get("route_evidence_freshness") != "fresh" or instant < parse_rfc3339(str(bridge.data["route_evidence_expires_at"]))
        return route_usable and all(
            projection.status is ProjectionStatus.STALE or projection.authority.expires_at is None
            or instant < parse_rfc3339(projection.authority.expires_at)
            for projection in self.projections.values()
        )
    def to_dict(self, *, include_digest: bool = True) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "schema_version": self.schema_version, "generated_at": self.generated_at,
            "expires_at": self.expires_at, "runtime_epoch": self.runtime_epoch,
            "synthetic": self.synthetic, "provider_state_promotion": self.provider_state_promotion,
            "projections": {region: self.projections[region].to_dict() for region in HELM_CONTEXT_REGIONS},
        }
        if include_digest:
            payload["context_digest"] = self.context_digest
        return payload
    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> HelmContextEnvelope:
        _exact_keys(value, {"schema_version", "generated_at", "expires_at", "runtime_epoch", "synthetic", "provider_state_promotion", "projections", "context_digest"}, "envelope")
        raw = value["projections"]
        if not isinstance(raw, Mapping) or not all(isinstance(block, Mapping) for block in raw.values()):
            raise HelmContextError("projections must contain objects")
        envelope = cls(
            value["schema_version"], value["generated_at"], value["expires_at"],
            value["runtime_epoch"], value["synthetic"],
            {region: HelmProjection.from_dict(block) for region, block in raw.items()},
            value["context_digest"], value["provider_state_promotion"],
        )
        if not hmac.compare_digest(envelope.context_digest, context_digest(envelope)):
            raise HelmContextError("context digest mismatch")
        return envelope
def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    except (RecursionError, TypeError, UnicodeError, ValueError) as exc:
        raise HelmContextError("context is not canonical JSON") from exc
    if len(encoded) > MAX_HELM_CONTEXT_BYTES:
        raise HelmContextError("context exceeds the encoded byte bound")
    return encoded
def context_digest(envelope: HelmContextEnvelope) -> str:
    return HELM_CONTEXT_DIGEST_PREFIX + hashlib.sha256(
        _canonical_bytes(envelope.to_dict(include_digest=False))
    ).hexdigest()
def seal_helm_context(envelope: HelmContextEnvelope) -> HelmContextEnvelope:
    sealed = replace(envelope, context_digest=context_digest(envelope))
    _canonical_bytes(sealed.to_dict())
    return sealed
def encode_helm_context(envelope: HelmContextEnvelope) -> bytes:
    expected = context_digest(envelope)
    if not envelope.context_digest or not hmac.compare_digest(envelope.context_digest, expected):
        raise HelmContextError("cannot encode an unsealed or tampered context")
    return _canonical_bytes(envelope.to_dict())
def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise HelmContextError(f"duplicate JSON key: {key}")
        decoded[key] = value
    return decoded
def decode_helm_context(value: bytes | str | Mapping[str, Any]) -> HelmContextEnvelope:
    if isinstance(value, bytes):
        if len(value) > MAX_HELM_CONTEXT_BYTES:
            raise HelmContextError("context exceeds the encoded byte bound")
        try:
            source: Any = value.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise HelmContextError("context must be valid UTF-8") from exc
    else:
        source = value
    if isinstance(source, str):
        try:
            encoded_size = len(source.encode("utf-8"))
        except UnicodeError as exc:
            raise HelmContextError("context must contain Unicode scalar values") from exc
        if encoded_size > MAX_HELM_CONTEXT_BYTES:
            raise HelmContextError("context exceeds the encoded byte bound")
        try:
            decoded = json.loads(source, object_pairs_hook=_reject_duplicate_keys)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise HelmContextError("context is not valid JSON") from exc
    elif isinstance(source, Mapping):
        _canonical_bytes(source)
        decoded = dict(source)
    else:
        raise HelmContextError("context must be bytes, text, or an object")
    if not isinstance(decoded, Mapping):
        raise HelmContextError("context root must be an object")
    return HelmContextEnvelope.from_dict(decoded)
def projection_is_stale(projection: HelmProjection, *, now: datetime) -> bool:
    if now.tzinfo is None or now.utcoffset() is None:
        raise HelmContextError("freshness check time must be timezone-aware")
    expiry = projection.authority.expires_at
    return expiry is not None and parse_rfc3339(expiry) <= now.astimezone(timezone.utc)
