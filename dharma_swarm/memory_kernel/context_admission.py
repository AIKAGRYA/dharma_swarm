"""Read-only context admission preview for MemoryKernel atoms.

This module plans which atoms could enter a context pack.  It does not inject
prompts, write retrieval feedback, promote facts, or mutate memory surfaces.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable

from dharma_swarm.memory_kernel.atoms import (
    AGENT_OWNER_METADATA_KEYS,
    AuthorityLevel,
    MemoryAtom,
    MemoryAtomType,
    MemoryLane,
    MemoryScope,
    RiskLevel,
    SurfaceCategory,
    TruthState,
)
from dharma_swarm.memory_kernel.tool_exposure import has_tool_exposure


_HIGH_RISKS = {RiskLevel.HIGH, RiskLevel.CRITICAL}
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)
_SECRETISH_RE = re.compile(
    r"(?ix)"
    r"("
    r"\b(?:[A-Z0-9_]*API[_-]?KEY|PASSWORD|PRIVATE[_-]?KEY|"
    r"SECRET[_-]?TOKEN|ACCESS[_-]?TOKEN|REFRESH[_-]?TOKEN|TOKEN)"
    r"\b\s*[:=]\s*[\"']?[^\s,\"'`]+"
    r"|\bAuthorization\s*:\s*Bearer\s+[^\s,\"'`]+"
    r"|\bBearer\s+[A-Za-z0-9._~+/=-]{16,}"
    r"|\bsk-[A-Za-z0-9_-]{8,}"
    r"|\bgh[pousr]_[A-Za-z0-9_]{8,}"
    r")"
)
_DEFAULT_ALLOWED_TRUTH_STATES = (
    TruthState.OBSERVED,
    TruthState.CURATED,
    TruthState.CANONICAL,
)
_STALE_FRESHNESS_VALUES = {"snapshot", "dormant", "missing", "unknown"}
_ISOLATION_MODES = ("unrestricted", "scoped")


@dataclass(frozen=True)
class MemoryContextBudget:
    """Budget and policy for one read-only context pack preview."""

    max_candidate_atoms: int = 50
    max_admitted_atoms: int = 8
    max_total_chars: int = 4000
    max_atom_chars: int = 600
    include_content: bool = False
    require_context_admissible: bool = True
    allow_projections: bool = False
    allow_high_risk: bool = False
    reject_stale: bool = False
    require_source_digest: bool = False
    require_source_row_key: bool = False
    block_tool_exposure: bool = False
    # "scoped": empty allowed_scopes/allowed_memory_lanes DENY every atom and
    # agent ownership is enforced across ALL scopes; "unrestricted" keeps the
    # legacy empty-means-unfiltered semantics for direct callers.
    isolation_mode: str = "unrestricted"
    allowed_truth_states: tuple[TruthState, ...] = _DEFAULT_ALLOWED_TRUTH_STATES
    allowed_scopes: tuple[MemoryScope, ...] = ()
    allowed_agent_ids: tuple[str, ...] = ()
    allowed_memory_lanes: tuple[MemoryLane, ...] = ()
    allowed_atom_types: tuple[MemoryAtomType, ...] = ()

    def __post_init__(self) -> None:
        # An unknown mode must fail loudly at construction; comparing a
        # typo'd value against "scoped" downstream would silently degrade
        # to the legacy allow-all semantics.
        if self.isolation_mode not in _ISOLATION_MODES:
            raise ValueError(
                "isolation_mode must be one of "
                f"{_ISOLATION_MODES}, got {self.isolation_mode!r}"
            )

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["allowed_truth_states"] = tuple(
            item.value for item in self.allowed_truth_states
        )
        payload["allowed_scopes"] = tuple(item.value for item in self.allowed_scopes)
        payload["allowed_agent_ids"] = tuple(self.allowed_agent_ids)
        payload["allowed_memory_lanes"] = tuple(
            item.value for item in self.allowed_memory_lanes
        )
        payload["allowed_atom_types"] = tuple(
            item.value for item in self.allowed_atom_types
        )
        return payload


@dataclass(frozen=True)
class MemoryContextPackItem:
    atom_id: str
    surface_id: str
    atom_type: MemoryAtomType
    admitted: bool
    rank: int | None
    content_ref: str
    content_snippet: str | None
    selected_char_count: int
    authority_level: AuthorityLevel
    truth_state: TruthState
    scope: MemoryScope
    memory_lane: MemoryLane
    surface_category: SurfaceCategory
    canon_risk: RiskLevel
    pii_risk: RiskLevel
    projection_of: tuple[str, ...]
    source_refs: tuple[str, ...]
    selection_reasons: tuple[str, ...] = ()
    omission_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["atom_type"] = self.atom_type.value
        payload["authority_level"] = self.authority_level.value
        payload["truth_state"] = self.truth_state.value
        payload["scope"] = self.scope.value
        payload["memory_lane"] = self.memory_lane.value
        payload["surface_category"] = self.surface_category.value
        payload["canon_risk"] = self.canon_risk.value
        payload["pii_risk"] = self.pii_risk.value
        return payload


@dataclass(frozen=True)
class MemoryContextPack:
    pack_id: str
    budget: MemoryContextBudget
    candidate_count: int
    admitted_count: int
    omitted_count: int
    candidate_truncated: bool
    total_selected_chars: int
    items: tuple[MemoryContextPackItem, ...]
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "budget": self.budget.to_json(),
            "candidate_count": self.candidate_count,
            "admitted_count": self.admitted_count,
            "omitted_count": self.omitted_count,
            "candidate_truncated": self.candidate_truncated,
            "total_selected_chars": self.total_selected_chars,
            "warnings": self.warnings,
            "items": tuple(item.to_json() for item in self.items),
        }


def preview_memory_pack(
    atoms: Iterable[MemoryAtom],
    *,
    budget: MemoryContextBudget | None = None,
) -> MemoryContextPack:
    """Return a bounded, non-authoritative context admission preview."""

    resolved_budget = budget or MemoryContextBudget()
    candidates, truncated = _bounded_candidates(
        atoms,
        resolved_budget.max_candidate_atoms,
    )
    items: list[MemoryContextPackItem] = []
    admitted = 0
    total_chars = 0
    warnings: list[str] = [
        "preview_only_no_runtime_prompt_injection",
        "preview_does_not_promote_or_write_memory",
    ]
    if truncated:
        warnings.append("candidate_atom_limit_reached")

    for atom in candidates:
        omission_reasons = list(_omission_reasons(atom, resolved_budget))
        item_warnings = list(_atom_warnings(atom, resolved_budget))
        content_snippet = _content_snippet(atom, resolved_budget)
        selected_chars = len(content_snippet or "")
        if not omission_reasons and admitted >= max(0, resolved_budget.max_admitted_atoms):
            omission_reasons.append("admitted_atom_cap_reached")
        if (
            not omission_reasons
            and total_chars + selected_chars > max(0, resolved_budget.max_total_chars)
        ):
            omission_reasons.append("total_char_budget_exceeded")

        is_admitted = not omission_reasons
        rank: int | None = None
        if is_admitted:
            admitted += 1
            rank = admitted
            total_chars += selected_chars

        items.append(
            MemoryContextPackItem(
                atom_id=atom.atom_id,
                surface_id=atom.surface_id,
                atom_type=atom.atom_type,
                admitted=is_admitted,
                rank=rank,
                content_ref=_safe_ref(atom.content_ref),
                content_snippet=content_snippet if is_admitted else None,
                selected_char_count=selected_chars if is_admitted else 0,
                authority_level=atom.authority_level,
                truth_state=atom.truth_state,
                scope=atom.scope,
                memory_lane=atom.memory_lane,
                surface_category=atom.surface_category,
                canon_risk=atom.canon_risk,
                pii_risk=atom.pii_risk,
                projection_of=tuple(_safe_ref(ref) for ref in atom.projection_of),
                source_refs=_safe_source_refs(atom),
                selection_reasons=(
                    _selection_reasons(atom, resolved_budget) if is_admitted else ()
                ),
                omission_reasons=tuple(omission_reasons),
                warnings=tuple(item_warnings),
            )
        )

    if admitted == 0:
        warnings.append("no_atoms_admitted_by_policy")
    return MemoryContextPack(
        pack_id=_stable_pack_id(item.atom_id for item in items),
        budget=resolved_budget,
        candidate_count=len(candidates),
        admitted_count=admitted,
        omitted_count=len(items) - admitted,
        candidate_truncated=truncated,
        total_selected_chars=total_chars,
        items=tuple(items),
        warnings=tuple(warnings),
    )


def render_memory_context_pack_markdown(pack: MemoryContextPack) -> str:
    lines = [
        "# Memory Context Pack Preview",
        "",
        "This is a read-only preview. It does not inject prompts, promote memories, or write feedback.",
        "",
        "## Summary",
        "",
        f"- Pack ID: `{pack.pack_id}`",
        f"- Candidates: `{pack.candidate_count}`",
        f"- Admitted: `{pack.admitted_count}`",
        f"- Omitted: `{pack.omitted_count}`",
        f"- Candidate truncated: `{str(pack.candidate_truncated).lower()}`",
        f"- Selected content chars: `{pack.total_selected_chars}`",
        "",
    ]
    if pack.warnings:
        lines.extend(["## Warnings", ""])
        for warning in pack.warnings:
            lines.append(f"- `{warning}`")
        lines.append("")
    admitted = [item for item in pack.items if item.admitted]
    if admitted:
        lines.extend(["## Admitted Atoms", ""])
        for item in admitted:
            lines.append(
                f"- rank=`{item.rank}` atom=`{item.atom_id}` surface=`{item.surface_id}` "
                f"type=`{item.atom_type.value}` truth=`{item.truth_state.value}` "
                f"authority=`{item.authority_level.value}`"
            )
            if item.content_snippet:
                lines.append(f"  - snippet: `{item.content_snippet}`")
        lines.append("")
    omitted = [item for item in pack.items if not item.admitted]
    if omitted:
        lines.extend(["## Omitted Atoms", ""])
        for item in omitted[:20]:
            lines.append(
                f"- atom=`{item.atom_id}` surface=`{item.surface_id}` "
                f"reasons=`{', '.join(item.omission_reasons)}`"
            )
        if len(omitted) > 20:
            lines.append(f"- omitted list truncated: `{len(omitted) - 20}`")
        lines.append("")
    return "\n".join(lines)


def safe_context_ref(value: str) -> str:
    """Return a bounded reference that cannot expose local filesystem paths."""

    return _safe_ref(value)


def redact_context_text(value: str) -> str:
    """Redact local filesystem path tokens from context text."""

    return _redact_local_paths(value)


def has_local_path_ref(value: str) -> bool:
    return _is_local_path(value)


def _bounded_candidates(
    atoms: Iterable[MemoryAtom],
    max_candidate_atoms: int,
) -> tuple[tuple[MemoryAtom, ...], bool]:
    limit = max(0, max_candidate_atoms)
    rows: list[MemoryAtom] = []
    truncated = False
    for index, atom in enumerate(atoms):
        if index >= limit:
            truncated = True
            break
        rows.append(atom)
    return tuple(rows), truncated


def _omission_reasons(atom: MemoryAtom, budget: MemoryContextBudget) -> tuple[str, ...]:
    scoped = budget.isolation_mode == "scoped"
    reasons: list[str] = []
    if budget.allowed_atom_types and atom.atom_type not in budget.allowed_atom_types:
        reasons.append("atom_type_not_allowed")
    if scoped and not budget.allowed_scopes:
        reasons.append("scope_denied_fail_closed")
    elif budget.allowed_scopes and atom.scope not in budget.allowed_scopes:
        reasons.append("scope_not_allowed")
    if budget.allowed_agent_ids or scoped:
        atom_agent_ids = _atom_agent_ids(atom)
        # Scoped mode enforces atom ownership in every scope, not only AGENT:
        # another agent's atoms stay invisible even when shared into
        # SWARM/SESSION/PROJECT rows.
        if atom.scope == MemoryScope.AGENT and not atom_agent_ids:
            reasons.append("agent_owner_unknown")
        elif (atom.scope == MemoryScope.AGENT or (scoped and atom_agent_ids)) and (
            not budget.allowed_agent_ids
            or not set(atom_agent_ids).intersection(budget.allowed_agent_ids)
        ):
            reasons.append("agent_not_allowed")
    if scoped and not budget.allowed_memory_lanes:
        reasons.append("memory_lane_denied_fail_closed")
    elif budget.allowed_memory_lanes and atom.memory_lane not in budget.allowed_memory_lanes:
        reasons.append("memory_lane_not_allowed")
    if budget.require_context_admissible and not atom.context_admissible:
        reasons.append("atom_not_context_admissible")
    if atom.truth_state in {TruthState.REJECTED, TruthState.SUPERSEDED}:
        reasons.append(f"truth_state_{atom.truth_state.value}")
    elif budget.allowed_truth_states and atom.truth_state not in budget.allowed_truth_states:
        reasons.append("truth_state_not_allowed")
    if budget.reject_stale:
        if str(atom.freshness or "").lower() in _STALE_FRESHNESS_VALUES:
            reasons.append("stale_memory_rejected")
        if _is_expired(atom.valid_until):
            reasons.append("valid_until_expired")
    if budget.require_source_digest and not atom.source_digest:
        reasons.append("source_digest_required")
    if budget.require_source_row_key and not atom.source_row_key:
        reasons.append("source_row_key_required")
    if budget.block_tool_exposure and has_tool_exposure(atom):
        reasons.append("tool_exposure_blocked")
    if (
        not budget.allow_projections
        and (
            atom.surface_category == SurfaceCategory.PROJECTION
            or atom.memory_lane == MemoryLane.PROJECTION
            or bool(atom.projection_of)
        )
    ):
        reasons.append("projection_blocked")
    if not budget.allow_high_risk and (
        atom.canon_risk in _HIGH_RISKS or atom.pii_risk in _HIGH_RISKS
    ):
        reasons.append("high_risk_blocked")
    return tuple(dict.fromkeys(reasons))


def _selection_reasons(atom: MemoryAtom, budget: MemoryContextBudget) -> tuple[str, ...]:
    reasons = [
        "context_admissible" if atom.context_admissible else "context_admissible_override",
        f"truth_state:{atom.truth_state.value}",
        f"authority:{atom.authority_level.value}",
    ]
    if budget.include_content and atom.content:
        reasons.append("bounded_content_included")
    else:
        reasons.append("reference_only")
    if budget.allowed_agent_ids and atom.scope == MemoryScope.AGENT:
        reasons.append("agent_scope_allowed")
    return tuple(reasons)


def _atom_warnings(atom: MemoryAtom, budget: MemoryContextBudget) -> tuple[str, ...]:
    warnings: list[str] = []
    if atom.content is not None and not budget.include_content:
        warnings.append("content_available_but_not_included")
    for warning in atom.metadata.get("snapshot_warnings", ()):
        warnings.append(str(warning))
    refs = (*atom.source_refs, atom.source_path, atom.content_ref)
    if any(_is_local_path(ref) for ref in refs):
        warnings.append("local_path_refs_redacted")
    return tuple(dict.fromkeys(warnings))


def _content_snippet(atom: MemoryAtom, budget: MemoryContextBudget) -> str | None:
    if not budget.include_content or atom.content is None:
        return None
    text = _redact_local_paths(atom.content)
    limit = max(0, budget.max_atom_chars)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "...<truncated>"


def _safe_source_refs(atom: MemoryAtom) -> tuple[str, ...]:
    refs = tuple(_safe_ref(ref) for ref in atom.source_refs[:3])
    return refs or (f"surface:{atom.surface_id}",)


def _safe_ref(value: str) -> str:
    if _is_local_path(value):
        return "<local_path_redacted>"
    text = _redact_local_paths(value)
    if len(text) > 180:
        return text[:177].rstrip() + "..."
    return text


def _redact_local_paths(value: str) -> str:
    parts = value.split()
    redacted = ["<local_path_redacted>" if _is_local_path(part) else part for part in parts]
    text = _PRIVATE_KEY_RE.sub("<secret_like_redacted>", " ".join(redacted))
    return _SECRETISH_RE.sub("<secret_like_redacted>", text)


def _is_local_path(value: str) -> bool:
    stripped = value.strip("`'\"(),[]{}<>")
    return (
        stripped.startswith("/")
        or stripped.startswith("~/")
        or "/Users/" in stripped
        or "/private/" in stripped
    )


def _is_expired(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= datetime.now(timezone.utc)


def _stable_pack_id(atom_ids: Iterable[str]) -> str:
    payload = "\n".join(atom_ids)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"memory_context_pack:{digest[:24]}"


def _atom_agent_ids(atom: MemoryAtom) -> tuple[str, ...]:
    ids: list[str] = []
    _extend_agent_ids(ids, atom.metadata)
    for nested_key in ("payload", "row"):
        nested = atom.metadata.get(nested_key)
        if isinstance(nested, dict):
            _extend_agent_ids(ids, nested)
    return tuple(dict.fromkeys(ids))


def _extend_agent_ids(ids: list[str], payload: dict[str, object]) -> None:
    # "owner_agent_ids" is the hoisted key the adapters' redaction boundary
    # writes when it drops a row/payload dict that carried ownership.
    for key in (*AGENT_OWNER_METADATA_KEYS, "owner_agent_ids"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            ids.append(value.strip())
        elif isinstance(value, (list, tuple, set)):
            ids.extend(str(item).strip() for item in value if str(item).strip())
