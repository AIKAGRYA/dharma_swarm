"""chetana.provenance — frontmatter schema, validation, and signing.

The provenance schema is the contract that distinguishes a STAGED atom (untrusted)
from a PROMOTED atom (trusted). Every promoted atom MUST carry:

    source           — where the content came from (kind, path, span, captured)
    chain            — who/what processed it (agent_id, model, job, captured_at)
    gate_check       — telos gate result (ALLOW/WARN/BLOCK + which gates fired)
    axiom_signature  — SHA-256 hash signing atom content + active kernel manifest
    review_status    — staged | approved | rejected | auto_promoted
    stale_after      — re-verification trigger (default +90 days)

All atoms are markdown files with YAML frontmatter. This module owns the schema
contract; ingest/promote enforce it; decay watches stale_after.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field, field_validator


PARAClass = Literal["P", "A", "R", "Ar"]
SourceKind = Literal[
    "session", "webclip", "pdf", "document", "note", "wiki_extract", "voice", "external", "synthesis",
    "receipt",
]
_SOURCE_KIND_VALUES = set(get_args(SourceKind))
GateResult = Literal["ALLOW", "WARN", "BLOCK"]
ReviewStatus = Literal["staged", "approved", "rejected", "auto_promoted"]
# NOTE on `approved`: as of 2026-04-28, the promote/staging code path never sets
# review_status="approved". Atoms transition staged → auto_promoted (on ALLOW +
# auto_promote=True), staged → staged (on WARN or ALLOW without auto_promote),
# or staged → rejected (on BLOCK). The `approved` literal is reserved for a
# future `chetana approve <atom>` CLI/MCP surface — when human review explicitly
# accepts a staged atom into the trusted tier (distinct from auto_promoted,
# which means "no human ever looked at this").
AtomType = Literal[
    "atomic", "reference", "method", "framework", "spec", "tool", "concept", "decision"
]


_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(?P<frontmatter>.*?)\n---\s*\n(?P<body>.*)$", re.DOTALL
)


class AtomSource(BaseModel):
    kind: SourceKind
    path: str
    span: str | None = None
    captured: str
    captured_by: str

    @field_validator("captured")
    @classmethod
    def _validate_captured(cls, v: str) -> str:
        # accept ISO date or ISO datetime
        try:
            date.fromisoformat(v)
        except ValueError:
            datetime.fromisoformat(v)
        return v


_SOURCE_RECORD_KEYS = set(AtomSource.model_fields) | {"source"}


def _is_source_kind(value: Any) -> bool:
    return isinstance(value, str) and value in _SOURCE_KIND_VALUES


def _looks_like_source_record(value: dict[str, Any]) -> bool:
    keys = set(value)
    return (
        "path" in keys
        or keys <= set(AtomSource.model_fields)
        or ("source" in keys and len(keys & _SOURCE_RECORD_KEYS) > 1)
    )


def _normalize_source_entries(
    src: Any, *, source_path: str | None, captured_by: str
) -> list[dict[str, Any]]:
    captured = date.today().isoformat()

    def fallback(path: Any = None, *, span: str | None = None) -> dict[str, Any]:
        record = {
            "kind": "external",
            "path": str(path if path not in (None, "") else source_path or "<unknown>"),
            "captured": captured,
            "captured_by": captured_by,
        }
        if span:
            record["span"] = span
        return record

    def coerce_record(item: Any, *, span: str | None = None) -> dict[str, Any]:
        if isinstance(item, AtomSource):
            data = item.model_dump()
            if span and not data.get("span"):
                data["span"] = span
            return data
        if not isinstance(item, dict):
            return fallback(item, span=span)

        data = dict(item)
        source_value = data.pop("source", None)
        kind = data.get("kind")
        if not _is_source_kind(kind):
            if _is_source_kind(source_value):
                data["kind"] = source_value
            else:
                if kind and not data.get("span"):
                    data["span"] = str(kind)
                elif source_value and "path" in data and not data.get("span"):
                    data["span"] = str(source_value)
                data["kind"] = "external"
        if not data.get("path"):
            if source_value and not _is_source_kind(source_value):
                data["path"] = str(source_value)
            else:
                data["path"] = source_path or "<unknown>"
        if span and not data.get("span"):
            data["span"] = span
        data.setdefault("captured", captured)
        data.setdefault("captured_by", captured_by)
        return {k: v for k, v in data.items() if k in AtomSource.model_fields}

    if not src:
        return [fallback()]
    if isinstance(src, list):
        return [coerce_record(item) for item in src] or [fallback()]
    if isinstance(src, dict):
        if _looks_like_source_record(src):
            return [coerce_record(src)]
        entries: list[dict[str, Any]] = []
        for category, items in src.items():
            span = str(category)
            if not items:
                continue
            if isinstance(items, list):
                entries.extend(coerce_record(item, span=span) for item in items)
            else:
                entries.append(coerce_record(items, span=span))
        return entries or [fallback()]
    return [fallback(src)]


class GateCheckRecord(BaseModel):
    result: GateResult
    gates_passed: list[str] = Field(default_factory=list)
    gates_warned: list[str] = Field(default_factory=list)
    gates_blocked: list[str] = Field(default_factory=list)
    rationale: str | None = None
    checked_at: str

    @field_validator("checked_at")
    @classmethod
    def _validate_checked_at(cls, v: str) -> str:
        datetime.fromisoformat(v)
        return v


class AtomProvenance(BaseModel):
    promoted_by: str
    promoted_at: str
    gate_check: GateCheckRecord
    axiom_signature: str
    review_status: ReviewStatus
    reviewer: str | None = None
    # revival_chain: append-only audit trail of every revival event.
    # Each entry is a free-form dict (revival_id, revived_at, reviewed_by,
    # prior_signature, neighbors_added, questions_resolved, etc.) — kept
    # untyped at this layer so revival v0.x can iterate without schema PRs.
    revival_chain: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("axiom_signature")
    @classmethod
    def _validate_signature_format(cls, v: str) -> str:
        if not re.fullmatch(r"(?:v2:)?[0-9a-f]{64}", v):
            raise ValueError(
                "axiom_signature must be a 64-char lowercase sha256 hex digest, "
                "optionally prefixed with 'v2:'"
            )
        return v


class FrontmatterSchema(BaseModel):
    title: str
    chetana_version: str = "0.1.0"
    atom_id: str
    type: AtomType
    para_class: PARAClass | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source: list[AtomSource] = Field(min_length=1)
    provenance: AtomProvenance | None = None  # only on PROMOTED atoms
    stale_after: str
    related: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("source", mode="before")
    @classmethod
    def _normalize_source(cls, v: Any) -> list[dict[str, Any]]:
        return _normalize_source_entries(v, source_path=None, captured_by="schema_normalize")

    @field_validator("stale_after")
    @classmethod
    def _validate_stale_after_format(cls, v: str) -> str:
        date.fromisoformat(v)
        return v

    @field_validator("atom_id")
    @classmethod
    def _validate_atom_id(cls, v: str) -> str:
        # must be a uuid4 string
        try:
            uuid.UUID(v, version=4)
        except ValueError as e:
            raise ValueError(f"atom_id must be uuid4: {e}")
        return v


def new_atom_id() -> str:
    return str(uuid.uuid4())


def default_stale_after(today: date | None = None, days: int = 90) -> str:
    today = today or date.today()
    return (today + timedelta(days=days)).isoformat()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_axiom_signature(content: str, kernel_signature: str) -> str:
    """Sign atom content with the active dharma kernel signature.

    The signature is sha256(kernel_sig || NUL || content_bytes). This binds
    the atom to the exact kernel manifest that authorized its promotion.
    Verification: re-compute and compare.
    """
    h = hashlib.sha256()
    h.update(kernel_signature.encode("utf-8"))
    h.update(b"\x00")
    h.update(content.encode("utf-8"))
    return h.hexdigest()


SIGNATURE_V2_PREFIX = "v2:"


def compute_axiom_signature_v2(
    schema: "FrontmatterSchema", body: str, kernel_signature: str
) -> str:
    """Version-2 signature: covers normalized frontmatter (incl. review_status) + body.

    v1 (compute_axiom_signature) binds only the body, so review_status could be
    flipped on disk without breaking verification. v2 hashes the canonical JSON
    of the whole frontmatter (minus the signature field itself, which would be
    circular) plus the body, domain-separated and version-tagged.
    """
    import json as _json

    payload = _json.loads(schema.model_dump_json(exclude_none=True))
    prov = payload.get("provenance")
    if isinstance(prov, dict):
        prov.pop("axiom_signature", None)
    canonical = _json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    h = hashlib.sha256()
    for part in (
        kernel_signature.encode("utf-8"),
        b"chetana-axiom-signature-v2",
        canonical.encode("utf-8"),
        body.encode("utf-8"),
    ):
        h.update(part)
        h.update(b"\x00")
    return SIGNATURE_V2_PREFIX + h.hexdigest()


def signature_matches(
    stored: str, schema: "FrontmatterSchema", body: str, kernel_signature: str
) -> bool:
    """Verify a stored axiom_signature under the given kernel, either version."""
    if stored.startswith(SIGNATURE_V2_PREFIX):
        return compute_axiom_signature_v2(schema, body, kernel_signature) == stored
    return compute_axiom_signature(body, kernel_signature) == stored


PLACEHOLDER_SIGNATURE = "0" * 64

VERIFY_BUCKETS = ("verified", "zero-sig", "kernel-drift", "no-provenance", "schema-error")

# Buckets that fail `verify --mode production`. Compat mode fails only on
# zero-sig/schema-error so the ~251 pre-chetana wiki pages stay reportable.
PRODUCTION_FAIL_BUCKETS = ("zero-sig", "kernel-drift", "no-provenance", "schema-error")


def classify_atom_text(
    text: str, *, kernel_signature: str, source_path: str | None = None
) -> tuple[str, str | None]:
    """Classify one atom's verification bucket under the given kernel.

    Returns ``(bucket, review_status)`` where bucket ∈ VERIFY_BUCKETS and
    review_status is None unless the atom carries parseable provenance.
    Shared by the CLI and MCP verify surfaces so the two can never disagree.
    """
    try:
        schema, body = parse_frontmatter(text, source_path=source_path)
    except Exception:
        # Most likely a v1 wiki atom missing chetana-strict fields.
        # Distinguish that from genuinely malformed content.
        if text.lstrip().startswith("---"):
            return "no-provenance", None
        return "schema-error", None
    if schema is None:
        return "schema-error", None
    if schema.provenance is None:
        return "no-provenance", None
    review_status = schema.provenance.review_status
    stored = schema.provenance.axiom_signature or ""
    if not stored or stored == PLACEHOLDER_SIGNATURE:
        return "zero-sig", review_status
    if signature_matches(stored, schema, body, kernel_signature):
        return "verified", review_status
    if signature_matches(stored, schema, body, PLACEHOLDER_SIGNATURE):
        return "zero-sig", review_status
    return "kernel-drift", review_status


def scan_verify_targets(
    targets: list, *, kernel_signature: str
) -> tuple[dict[str, list[str]], list[str]]:
    """Bucket every target path, plus the overlapping ``unapproved`` list.

    ``unapproved`` collects atoms whose provenance parsed but whose
    review_status is not "approved" — an independent axis from the signature
    buckets (a verified auto_promoted atom is verified AND unapproved).
    """
    buckets: dict[str, list[str]] = {label: [] for label in VERIFY_BUCKETS}
    unapproved: list[str] = []
    for p in targets:
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            buckets["schema-error"].append(str(p))
            continue
        bucket, review_status = classify_atom_text(
            text, kernel_signature=kernel_signature, source_path=str(p)
        )
        buckets[bucket].append(str(p))
        if review_status is not None and review_status != "approved":
            unapproved.append(str(p))
    return buckets, unapproved


def production_verdict(
    buckets: dict[str, list[str]], unapproved: list[str], *, kernel_signature: str
) -> tuple[str, list[str]]:
    """Fail-closed verdict for production mode: ("pass"|"fail", reasons).

    Fails on any PRODUCTION_FAIL_BUCKETS hit, any unapproved review_status,
    or an unavailable kernel (placeholder signature makes verification
    meaningless, so an empty/clean scan must not pass on it).
    """
    reasons: list[str] = []
    if kernel_signature == PLACEHOLDER_SIGNATURE:
        reasons.append("kernel-unavailable")
    for label in PRODUCTION_FAIL_BUCKETS:
        if buckets.get(label):
            reasons.append(f"{label}: {len(buckets[label])}")
    if unapproved:
        reasons.append(f"unapproved review_status: {len(unapproved)}")
    return ("pass" if not reasons else "fail"), reasons


def validate_frontmatter(fm: dict[str, Any]) -> FrontmatterSchema:
    """Validate a parsed frontmatter dict. Raises pydantic ValidationError on failure."""
    return FrontmatterSchema.model_validate(fm)


def render_frontmatter_yaml(schema: FrontmatterSchema) -> str:
    """Render a FrontmatterSchema instance to a YAML frontmatter block (with --- delimiters)."""
    import json as _json

    import yaml

    payload = _json.loads(schema.model_dump_json(exclude_none=True))
    body = yaml.safe_dump(
        payload, sort_keys=False, default_flow_style=False, allow_unicode=True, width=120
    )
    return f"---\n{body}---\n"


def parse_frontmatter(
    text: str, *, lenient: bool = False, source_path: str | None = None
) -> tuple[FrontmatterSchema | None, str]:
    """Parse an atom's full text into (frontmatter, body).

    Returns (None, full_text) if no frontmatter is present.
    Raises pydantic ValidationError if frontmatter is present but invalid
    (unless ``lenient=True``, in which case missing/loose fields get
    sensible defaults so chetana can read older Karpathy-style atoms).

    YAML auto-coerces ISO-shaped strings to ``date`` objects; we coerce them
    back to ISO strings before validation so the schema stays string-only.
    """
    import yaml

    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    fm_raw = yaml.safe_load(m.group("frontmatter"))
    if fm_raw is None or not isinstance(fm_raw, dict):
        return None, m.group("body")
    fm_raw = _coerce_temporal_strings(fm_raw)
    if lenient:
        fm_raw = _legacy_normalize(fm_raw, source_path=source_path)
    return validate_frontmatter(fm_raw), m.group("body")


def _legacy_normalize(fm: dict[str, Any], *, source_path: str | None) -> dict[str, Any]:
    """Coerce legacy / Karpathy-style frontmatter into the chetana schema.

    Makes chetana able to read 100+ existing wiki atoms that predate it:
      - missing ``atom_id`` → deterministic uuid5 from the source_path
      - missing ``type``    → "atomic"
      - missing ``confidence`` → 0.5
      - missing ``stale_after`` → today + 90d
      - ``source: [str, str, ...]`` → list[AtomSource(kind="external", path=str)]
      - ``sources:`` (alt key) → ``source:``
      - ``cross_links:`` (alt key) → ``related:``
    """
    fm = dict(fm)  # copy

    # alt-key normalizations
    if "sources" in fm and "source" not in fm:
        fm["source"] = fm.pop("sources")
    if "cross_links" in fm and "related" not in fm:
        fm["related"] = fm.pop("cross_links")

    # atom_id default — deterministic from source_path so re-reads stay stable
    if not fm.get("atom_id"):
        if source_path:
            fm["atom_id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, source_path))
        else:
            fm["atom_id"] = str(uuid.uuid4())

    fm.setdefault("type", "atomic")
    if "confidence" not in fm:
        fm["confidence"] = 0.5
    fm.setdefault("stale_after", default_stale_after())
    if isinstance(fm.get("stale_after"), str) and fm["stale_after"].strip().lower() in {
        "never", "none", "n/a", "-",
    }:
        fm["stale_after"] = default_stale_after(days=36500)
    fm.setdefault("title", "Untitled")

    fm["source"] = _normalize_source_entries(
        fm.get("source"), source_path=source_path, captured_by="legacy_normalize"
    )

    # confidence float coercion
    try:
        fm["confidence"] = float(fm["confidence"])
    except (TypeError, ValueError):
        fm["confidence"] = 0.5

    # related must be list[str] of [[wikilinks]]
    related = fm.get("related") or []
    if isinstance(related, str):
        related = [related]
    fm["related"] = [str(r) for r in related]

    # tags must be list[str]
    tags = fm.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    fm["tags"] = [str(t) for t in tags]

    return fm


def _coerce_temporal_strings(value: Any) -> Any:
    """Recursively convert date/datetime values in a parsed YAML dict to ISO strings."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _coerce_temporal_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce_temporal_strings(v) for v in value]
    return value


def assemble_atom(schema: FrontmatterSchema, body: str) -> str:
    """Combine a frontmatter schema and body markdown into a complete atom file."""
    fm_block = render_frontmatter_yaml(schema)
    body = body.lstrip("\n")
    return f"{fm_block}\n{body}\n" if not body.endswith("\n") else f"{fm_block}\n{body}"
