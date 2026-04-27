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
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


PARAClass = Literal["P", "A", "R", "Ar"]
SourceKind = Literal[
    "session", "webclip", "pdf", "note", "wiki_extract", "voice", "external", "synthesis"
]
GateResult = Literal["ALLOW", "WARN", "BLOCK"]
ReviewStatus = Literal["staged", "approved", "rejected", "auto_promoted"]
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
        if not re.fullmatch(r"[0-9a-f]{64}", v):
            raise ValueError("axiom_signature must be a 64-char lowercase sha256 hex digest")
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


def parse_frontmatter(text: str) -> tuple[FrontmatterSchema | None, str]:
    """Parse an atom's full text into (frontmatter, body).

    Returns (None, full_text) if no frontmatter is present.
    Raises pydantic ValidationError if frontmatter is present but invalid.

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
    return validate_frontmatter(fm_raw), m.group("body")


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
