"""Typed, dry-run-first multi-page compilation for the knowledge wiki.

The LLM proposes an integration plan; this module is the evaluator.  It binds
every edit to hashed evidence, an authority class, an expected target hash, and
exact replacement counts before it writes any page. A source can extend many
existing pages, while all canonical writes fail closed unless the evidence is
an audited source or canonical ledger under an operator-configured root. This
does not provide immutable raw-source custody or prove semantic entailment.
"""

from __future__ import annotations

import difflib
import fcntl
import hashlib
import json
import os
import re
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Iterable, Literal
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from . import staging as staging_mod
from .backlinks import governing_manifest_paths, manifest_candidate_paths
from .safe_write import (
    AnchoredTextChange,
    AnchoredWriteError,
    AnchorIdentity,
    apply_anchored_text_changes,
    read_anchored_text,
)
from .wiki_log import render_wiki_log_entry


SCHEMA_VERSION = "chetana.integration.v2"
ALLOWED_TARGET_ROOTS = frozenset(
    {"concepts", "connections", "mocs", "research", "tooling"}
)
EvidenceAuthority = Literal[
    "operator",
    "primary-source",
    "audited-source",
    "canonical-ledger",
    "verified-runtime",
    "agent-inference",
]
ClaimMode = Literal["extend", "correct", "qualify", "retract"]
_CANONICAL_WRITE_AUTHORITIES = frozenset({"audited-source", "canonical-ledger"})
_HASH_RE = r"^[0-9a-f]{64}$"
_CLAIM_TOKEN_CHARS = r"A-Za-z0-9_.-"
_RUNTIME_SOURCE_SUFFIXES = frozenset({".json", ".py", ".sh", ".toml", ".yaml", ".yml"})
_CANONICAL_LEDGER_ROOTS_ENV = "CHETANA_CANONICAL_LEDGER_ROOTS"
_AUDITED_SOURCE_ROOTS_ENV = "CHETANA_AUDITED_SOURCE_ROOTS"


class IntegrationPlanError(ValueError):
    """The plan is invalid or one of its proof obligations no longer holds."""


@dataclass(frozen=True)
class AuthorityPolicy:
    """Operator-configured roots that mint canonical evidence capabilities.

    A plan may declare an evidence class, but only a source below one of these
    invocation/environment roots receives write authority.  This is a bounded
    filesystem capability, not a claim-entailment proof or signer identity.
    """

    canonical_ledger_roots: tuple[Path, ...] = ()
    audited_source_roots: tuple[Path, ...] = ()

    @classmethod
    def from_sources(
        cls,
        *,
        canonical_ledger_roots: Iterable[Path | str] | None = None,
        audited_source_roots: Iterable[Path | str] | None = None,
    ) -> "AuthorityPolicy":
        return cls(
            canonical_ledger_roots=_normalise_authority_roots(
                canonical_ledger_roots,
                environment_name=_CANONICAL_LEDGER_ROOTS_ENV,
            ),
            audited_source_roots=_normalise_authority_roots(
                audited_source_roots,
                environment_name=_AUDITED_SOURCE_ROOTS_ENV,
            ),
        )

    def roots_for(self, authority: EvidenceAuthority) -> tuple[Path, ...]:
        if authority == "canonical-ledger":
            return self.canonical_ledger_roots
        if authority == "audited-source":
            return self.audited_source_roots
        return ()


class EvidenceClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
    locator: str = Field(min_length=1)


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,63}$")
    path: str = Field(min_length=1)
    url: str | None = None
    sha256: str = Field(pattern=_HASH_RE)
    observed_at: str
    declared_authority: EvidenceAuthority
    declared_verifier: str = Field(min_length=1)
    claims: list[EvidenceClaim] = Field(min_length=1)

    @field_validator("observed_at")
    @classmethod
    def _valid_observed_at(cls, value: str) -> str:
        observed = datetime.fromisoformat(value)
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        if observed > datetime.now().astimezone() + timedelta(minutes=5):
            raise ValueError("observed_at cannot be in the future")
        return value

    @field_validator("claims")
    @classmethod
    def _unique_claim_ids(cls, value: list[EvidenceClaim]) -> list[EvidenceClaim]:
        claim_ids = [claim.claim_id for claim in value]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("source claim IDs must be unique")
        return value

    @field_validator("url")
    @classmethod
    def _valid_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("source url must be an absolute https URL")
        return value


class ClaimBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,63}$")
    claim_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class ExactReplacement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: ClaimMode
    claim_bindings: list[ClaimBinding] = Field(min_length=1)
    old: str = Field(min_length=1)
    new: str = Field(min_length=1)
    expected_count: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _valid_semantics(self) -> "ExactReplacement":
        if self.old == self.new:
            raise ValueError("old and new text must differ")
        if self.mode in {"extend", "qualify"} and not self.new.startswith(self.old):
            raise ValueError(
                f"{self.mode} must preserve old text verbatim and append new material"
            )
        if self.mode == "retract" and (
            self.old not in self.new
            or not any(
                marker in self.new.casefold()
                for marker in ("retract", "supersed", "withdraw")
            )
        ):
            raise ValueError(
                "retract must preserve the old claim as genealogy and mark its status"
            )
        pairs = [
            (binding.evidence_id, binding.claim_id) for binding in self.claim_bindings
        ]
        if len(pairs) != len(set(pairs)):
            raise ValueError("operation claim_bindings must be unique")
        return self


class PagePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    expected_sha256: str = Field(pattern=_HASH_RE)
    operations: list[ExactReplacement] = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def _bounded_target_path(cls, value: str) -> str:
        pure = PurePosixPath(value)
        if (
            not value
            or "\\" in value
            or pure.is_absolute()
            or ".." in pure.parts
            or len(pure.parts) < 2
            or pure.parts[0] not in ALLOWED_TARGET_ROOTS
            or pure.suffix.lower() != ".md"
        ):
            allowed = ", ".join(sorted(ALLOWED_TARGET_ROOTS))
            raise ValueError(
                "target path must be a relative markdown file under one of: " + allowed
            )
        return pure.as_posix()


class IntegrationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[SCHEMA_VERSION]
    plan_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    sources: list[EvidenceRef] = Field(min_length=1, max_length=10)
    rationale: str = Field(min_length=1)
    pages: list[PagePatch] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def _authority_and_uniqueness(self) -> "IntegrationPlan":
        paths = [page.path for page in self.pages]
        if len(paths) != len(set(paths)):
            raise ValueError("each target path may appear only once")
        sources_by_id = {source.evidence_id: source for source in self.sources}
        if len(sources_by_id) != len(self.sources):
            raise ValueError("each evidence_id may appear only once")
        used_evidence_ids: set[str] = set()
        for page in self.pages:
            for operation in page.operations:
                operation_evidence_ids = {
                    binding.evidence_id for binding in operation.claim_bindings
                }
                used_evidence_ids.update(operation_evidence_ids)
                unknown = operation_evidence_ids - set(sources_by_id)
                if unknown:
                    raise ValueError(
                        "operation references unknown evidence IDs: "
                        + ", ".join(sorted(unknown))
                    )
                forbidden = sorted(
                    {
                        sources_by_id[evidence_id].declared_authority
                        for evidence_id in operation_evidence_ids
                        if sources_by_id[evidence_id].declared_authority
                        not in _CANONICAL_WRITE_AUTHORITIES
                    }
                )
                if forbidden:
                    raise ValueError(
                        "declared evidence classes "
                        + ", ".join(repr(item) for item in forbidden)
                        + " cannot directly rewrite canonical pages; use an "
                        "allowlisted audited source or canonical ledger"
                    )
                for binding in operation.claim_bindings:
                    source_claim_ids = {
                        claim.claim_id
                        for claim in sources_by_id[binding.evidence_id].claims
                    }
                    if binding.claim_id not in source_claim_ids:
                        raise ValueError(
                            "operation claim binding is not declared by its evidence: "
                            f"{binding.evidence_id}:{binding.claim_id}"
                        )
        unused = set(sources_by_id) - used_evidence_ids
        if unused:
            raise ValueError(
                "plan contains unused evidence IDs: " + ", ".join(sorted(unused))
            )
        return self


@dataclass(frozen=True)
class CompiledOperation:
    """Receipt-safe representation of one validated text transformation."""

    mode: ClaimMode
    claim_bindings: tuple[tuple[str, str], ...]
    old_sha256: str
    new_sha256: str
    expected_count: int


@dataclass(frozen=True)
class CompiledChange:
    path: Path
    relative_path: str
    before_sha256: str
    after_sha256: str
    before: str
    after: str
    diff: str
    evidence_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    operations: tuple[CompiledOperation, ...]


@dataclass(frozen=True)
class CompiledEvidence:
    evidence_id: str
    declared_authority: EvidenceAuthority
    path: Path
    url: str | None
    sha256: str
    observed_at: str
    declared_verifier: str
    claims: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CompilationResult:
    plan_id: str
    plan_sha256: str
    evidence: tuple[CompiledEvidence, ...]
    changes: tuple[CompiledChange, ...]
    applied: bool
    reviewer: str | None = None
    log_path: Path | None = None

    @property
    def diff(self) -> str:
        return (
            "\n".join(change.diff.rstrip() for change in self.changes if change.diff)
            + "\n"
        )


def load_integration_plan(path: Path | str) -> IntegrationPlan:
    plan_path = Path(path).expanduser()
    plan, _plan_sha256 = _load_integration_plan(plan_path)
    return plan


def _load_integration_plan(path: Path) -> tuple[IntegrationPlan, str]:
    try:
        raw = _read_utf8_bytes_no_follow(path, kind="integration plan")
        payload = json.loads(raw.decode("utf-8"))
        return IntegrationPlan.model_validate(payload), _sha256_bytes(raw)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValidationError,
        TypeError,
    ) as exc:
        raise IntegrationPlanError(f"invalid integration plan {path}: {exc}") from exc


def compile_integration_plan(
    plan_path: Path | str,
    *,
    wiki_root: Path | str | None = None,
    apply: bool = False,
    reviewer: str | None = None,
    canonical_ledger_roots: Iterable[Path | str] | None = None,
    audited_source_roots: Iterable[Path | str] | None = None,
) -> CompilationResult:
    """Validate and optionally apply an all-preconditions-first integration plan."""
    plan_file = Path(os.path.abspath(Path(plan_path).expanduser()))
    plan, plan_sha256 = _load_integration_plan(plan_file)
    root = Path(wiki_root or staging_mod.WIKI_ROOT).expanduser().resolve()
    authority_policy = AuthorityPolicy.from_sources(
        canonical_ledger_roots=canonical_ledger_roots,
        audited_source_roots=audited_source_roots,
    )
    if apply and not (reviewer or "").strip():
        raise IntegrationPlanError("apply requires a named reviewer")
    if apply:
        with _exclusive_wiki_lock(root) as anchor_identity:
            return _compile_loaded_plan(
                plan,
                plan_file=plan_file,
                plan_sha256=plan_sha256,
                root=root,
                authority_policy=authority_policy,
                apply=True,
                reviewer=reviewer.strip() if reviewer else None,
                anchor_identity=anchor_identity,
            )
    return _compile_loaded_plan(
        plan,
        plan_file=plan_file,
        plan_sha256=plan_sha256,
        root=root,
        authority_policy=authority_policy,
        apply=False,
        reviewer=None,
        anchor_identity=None,
    )


def _compile_loaded_plan(
    plan: IntegrationPlan,
    *,
    plan_file: Path,
    plan_sha256: str,
    root: Path,
    authority_policy: AuthorityPolicy,
    apply: bool,
    reviewer: str | None,
    anchor_identity: AnchorIdentity | None,
) -> CompilationResult:
    evidence = tuple(
        _compile_evidence(
            source,
            plan_dir=plan_file.parent,
            authority_policy=authority_policy,
        )
        for source in plan.sources
    )

    changes = tuple(_compile_page(root, page) for page in plan.pages)
    output_paths = {change.path for change in changes} | {root / "log.md"}
    input_paths = {plan_file, *(item.path for item in evidence)}
    overlapping_inputs = sorted(
        {
            input_path
            for input_path in input_paths
            if any(
                _paths_alias(input_path, output_path) for output_path in output_paths
            )
        },
        key=str,
    )
    if overlapping_inputs:
        raise IntegrationPlanError(
            "plan/evidence inputs may not alias explicit or implicit write targets: "
            + ", ".join(str(path) for path in overlapping_inputs)
        )

    if not apply:
        return CompilationResult(
            plan_id=plan.plan_id,
            plan_sha256=plan_sha256,
            evidence=evidence,
            changes=changes,
            applied=False,
            reviewer=None,
        )

    active_manifests = governing_manifest_paths([root])
    if active_manifests:
        raise IntegrationPlanError(
            "manifest-governed wiki updates require an atomic page-plus-manifest "
            "approval transaction; refusing standalone compile apply: "
            + ", ".join(str(path) for path in active_manifests)
        )

    current_plan_sha = _sha256_bytes(
        _read_utf8_bytes_no_follow(plan_file, kind="integration plan")
    )
    if current_plan_sha != plan_sha256:
        raise IntegrationPlanError("integration plan changed during compilation")
    for source in plan.sources:
        _compile_evidence(
            source,
            plan_dir=plan_file.parent,
            authority_policy=authority_policy,
        )
    for change in changes:
        current_sha = _sha256_bytes(change.path.read_bytes())
        if current_sha != change.before_sha256:
            raise IntegrationPlanError(
                "target changed during compilation; refusing all writes: "
                f"{change.relative_path}"
            )

    claim_ids = sorted({claim_id for c in changes for claim_id in c.claim_ids})
    operation_receipt = json.dumps(
        [
            {
                "target": change.relative_path,
                "before_sha256": change.before_sha256,
                "after_sha256": change.after_sha256,
                "operations": [
                    {
                        "mode": operation.mode,
                        "claim_bindings": [
                            {"evidence_id": evidence_id, "claim_id": claim_id}
                            for evidence_id, claim_id in operation.claim_bindings
                        ],
                        "old_sha256": operation.old_sha256,
                        "new_sha256": operation.new_sha256,
                        "expected_count": operation.expected_count,
                    }
                    for operation in change.operations
                ],
            }
            for change in changes
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    evidence_receipt = json.dumps(
        [
            {
                "evidence_id": item.evidence_id,
                "declared_authority": item.declared_authority,
                "path": str(item.path),
                "url": item.url,
                "sha256": item.sha256,
                "observed_at": item.observed_at,
                "declared_verifier": item.declared_verifier,
                "claims": [
                    {"claim_id": claim_id, "locator": locator}
                    for claim_id, locator in item.claims
                ],
            }
            for item in evidence
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    log_details = {
        "evidence": "; ".join(
            f"{item.evidence_id}:{item.declared_authority}:{item.path}@{item.sha256}"
            for item in evidence
        ),
        "evidence_bindings": evidence_receipt,
        "authority_roots": json.dumps(
            [
                {
                    "kind": kind,
                    "roots": [str(path) for path in roots],
                }
                for kind, roots in (
                    ("canonical-ledger", authority_policy.canonical_ledger_roots),
                    ("audited-source", authority_policy.audited_source_roots),
                )
            ],
            sort_keys=True,
            separators=(",", ":"),
        ),
        "plan": str(plan_file),
        "plan_sha256": plan_sha256,
        "claim_ids": ", ".join(claim_ids) or "none",
        "operation_bindings": operation_receipt,
        "targets": ", ".join(change.relative_path for change in changes),
        "reviewer": reviewer or "<missing>",
    }
    try:
        log_original = read_anchored_text(root, "log.md")
    except (AnchoredWriteError, OSError) as exc:
        raise IntegrationPlanError(f"unsafe wiki log target: {exc}") from exc
    log_entry = render_wiki_log_entry(
        operation="compile",
        title=plan.plan_id,
        details=log_details,
    )
    log_separator = "" if not log_original or log_original.endswith("\n") else "\n"
    log_updated = (log_original or "") + log_separator + log_entry
    transaction_changes = [
        AnchoredTextChange(
            relative_path=change.relative_path,
            original_text=change.before,
            updated_text=change.after,
        )
        for change in changes
    ]
    transaction_changes.append(
        AnchoredTextChange(
            relative_path="log.md",
            original_text=log_original,
            updated_text=log_updated,
        )
    )
    expected_text = {change.relative_path: change.before for change in changes}
    expected_text["log.md"] = log_original
    for manifest_path in manifest_candidate_paths([root]):
        if not manifest_path.parent.is_dir():
            continue
        try:
            relative_manifest = manifest_path.relative_to(root).as_posix()
        except ValueError:
            continue
        expected_text[relative_manifest] = None
    try:
        apply_anchored_text_changes(
            root,
            transaction_changes,
            expected_text=expected_text,
            expected_anchor_identity=anchor_identity,
            final_validator=lambda: _validate_final_compile_preconditions(
                root=root,
                plan_file=plan_file,
                plan_sha256=plan_sha256,
                sources=plan.sources,
                authority_policy=authority_policy,
            ),
        )
    except (AnchoredWriteError, OSError) as exc:
        raise IntegrationPlanError(f"integration apply failed: {exc}") from exc
    log_path = root / "log.md"

    return CompilationResult(
        plan_id=plan.plan_id,
        plan_sha256=plan_sha256,
        evidence=evidence,
        changes=changes,
        applied=True,
        reviewer=reviewer,
        log_path=log_path,
    )


def _refuse_active_manifest(root: Path) -> None:
    active_manifests = governing_manifest_paths([root])
    if active_manifests:
        raise IntegrationPlanError(
            "manifest appeared during compilation; refusing canonical writes: "
            + ", ".join(str(path) for path in active_manifests)
        )


def _validate_final_compile_preconditions(
    *,
    root: Path,
    plan_file: Path,
    plan_sha256: str,
    sources: tuple[EvidenceRef, ...],
    authority_policy: AuthorityPolicy,
) -> None:
    """Pin plan, evidence, and manifest state at the commit linearization point."""

    current_plan_sha = _sha256_bytes(
        _read_utf8_bytes_no_follow(plan_file, kind="integration plan")
    )
    if current_plan_sha != plan_sha256:
        raise IntegrationPlanError("integration plan changed during apply")
    for source in sources:
        _compile_evidence(
            source,
            plan_dir=plan_file.parent,
            authority_policy=authority_policy,
        )
    _refuse_active_manifest(root)


def compilation_summary(result: CompilationResult) -> str:
    state = "APPLIED" if result.applied else "DRY-RUN"
    lines = [
        f"# chetana compile — {state}",
        f"- plan_id: {result.plan_id}",
        f"- plan_sha256: {result.plan_sha256}",
        f"- evidence_sources: {len(result.evidence)}",
    ]
    lines.extend(
        f"  - {item.evidence_id}: {item.declared_authority} @ {item.sha256}"
        for item in result.evidence
    )
    lines.extend(
        [
            f"- reviewer: {result.reviewer or 'not-yet-reviewed'}",
            f"- pages_changed: {len(result.changes)}",
        ]
    )
    lines.extend(f"  - {change.relative_path}" for change in result.changes)
    return "\n".join(lines)


def _resolve_source(raw_path: str, plan_dir: Path) -> Path:
    source = Path(raw_path).expanduser()
    if not source.is_absolute():
        source = plan_dir / source
    return Path(os.path.abspath(source))


def _compile_evidence(
    source: EvidenceRef,
    *,
    plan_dir: Path,
    authority_policy: AuthorityPolicy,
) -> CompiledEvidence:
    source_path = _resolve_source(source.path, plan_dir)
    source_bytes = _read_utf8_bytes_no_follow(source_path, kind="source file")
    actual = _sha256_bytes(source_bytes)
    if actual != source.sha256:
        raise IntegrationPlanError(
            f"source hash mismatch for {source_path}: expected {source.sha256}, got {actual}"
        )
    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeError as exc:
        raise IntegrationPlanError(
            f"text evidence is not UTF-8: {source_path}"
        ) from exc
    for claim in source.claims:
        claim_pattern = (
            rf"(?<![{_CLAIM_TOKEN_CHARS}]){re.escape(claim.claim_id)}"
            rf"(?![{_CLAIM_TOKEN_CHARS}])"
        )
        if not re.search(claim_pattern, claim.locator):
            raise IntegrationPlanError(
                f"claim locator does not contain exact claim ID {claim.claim_id}: "
                f"{source.evidence_id}"
            )
        locator_count = source_text.count(claim.locator)
        if locator_count != 1:
            raise IntegrationPlanError(
                "claim locator must occur exactly once in hashed evidence: "
                f"{source.evidence_id}:{claim.claim_id} (found {locator_count})"
            )
        locator_start = source_text.index(claim.locator)
        locator_end = locator_start + len(claim.locator)
        bound_claim_matches = [
            match
            for match in re.finditer(claim_pattern, source_text)
            if locator_start <= match.start() and match.end() <= locator_end
        ]
        if len(bound_claim_matches) != 1:
            raise IntegrationPlanError(
                "claim ID must be an exact token inside its unique evidence locator: "
                f"{source.evidence_id}:{claim.claim_id}"
            )
    _verify_declared_authority(
        source,
        source_path=source_path,
        source_text=source_text,
        authority_policy=authority_policy,
    )
    return CompiledEvidence(
        evidence_id=source.evidence_id,
        declared_authority=source.declared_authority,
        path=source_path,
        url=source.url,
        sha256=source.sha256,
        observed_at=source.observed_at,
        declared_verifier=source.declared_verifier,
        claims=tuple((claim.claim_id, claim.locator) for claim in source.claims),
    )


def _verify_declared_authority(
    source: EvidenceRef,
    *,
    source_path: Path,
    source_text: str,
    authority_policy: AuthorityPolicy,
) -> None:
    """Enforce observable constraints for each declared authority class.

    The reviewer name is an unauthenticated audit field, not a source of
    authority. These checks prevent a plan from relabeling an arbitrary blob as
    a stronger evidence class unless its path is also confined to an
    operator-configured root. They do not prove that the evidence entails the
    proposed replacement.
    """

    if source.declared_authority == "primary-source" and source.url is None:
        raise IntegrationPlanError(
            "primary-source evidence requires a pinned https URL"
        )
    if source.declared_authority in _CANONICAL_WRITE_AUTHORITIES:
        configured_roots = authority_policy.roots_for(source.declared_authority)
        if not configured_roots:
            raise IntegrationPlanError(
                f"{source.declared_authority} has no configured authority root"
            )
        if not any(
            _is_relative_to(source_path, authority_root)
            for authority_root in configured_roots
        ):
            raise IntegrationPlanError(
                f"{source.declared_authority} evidence is outside configured "
                f"authority roots: {source_path}"
            )
    if source.declared_authority == "canonical-ledger":
        canonical_name = source_path.name.upper()
        if "LEDGER" not in canonical_name and "REGISTER" not in canonical_name:
            raise IntegrationPlanError(
                "canonical-ledger evidence path must name a ledger or register: "
                f"{source_path}"
            )
    if (
        source.declared_authority == "audited-source"
        and "## Audited" not in source_text
    ):
        raise IntegrationPlanError(
            "audited-source evidence must contain an explicit '## Audited' section"
        )
    if (
        source.declared_authority == "verified-runtime"
        and source_path.suffix.casefold() not in _RUNTIME_SOURCE_SUFFIXES
    ):
        raise IntegrationPlanError(
            "verified-runtime evidence must be executable code or structured config: "
            f"{source_path}"
        )


def _compile_page(root: Path, page: PagePatch) -> CompiledChange:
    relative = PurePosixPath(page.path)
    lexical_target = root.joinpath(*relative.parts)
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise IntegrationPlanError(f"target path traverses a symlink: {page.path}")
    target = lexical_target.resolve()
    try:
        target.relative_to((root / relative.parts[0]).resolve())
    except ValueError as exc:
        raise IntegrationPlanError(
            f"target path escapes its allowed wiki layer: {page.path}"
        ) from exc
    if not target.is_file():
        raise IntegrationPlanError(f"target file missing: {page.path}")

    before_bytes = target.read_bytes()
    before_sha = _sha256_bytes(before_bytes)
    if before_sha != page.expected_sha256:
        raise IntegrationPlanError(
            f"target hash mismatch for {page.path}: expected {page.expected_sha256}, got {before_sha}"
        )
    try:
        before = before_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IntegrationPlanError(
            f"target is not UTF-8 markdown: {page.path}"
        ) from exc

    after = before
    evidence_ids: set[str] = set()
    claim_ids: set[str] = set()
    compiled_operations: list[CompiledOperation] = []
    for op in page.operations:
        bindings = tuple(
            (binding.evidence_id, binding.claim_id) for binding in op.claim_bindings
        )
        actual_count = after.count(op.old)
        if actual_count != op.expected_count:
            raise IntegrationPlanError(
                f"replacement count mismatch for {page.path}"
                f" ({','.join(claim_id for _evidence, claim_id in bindings)}): "
                f"expected {op.expected_count}, got {actual_count}"
            )
        after = after.replace(op.old, op.new, op.expected_count)
        evidence_ids.update(evidence_id for evidence_id, _claim_id in bindings)
        claim_ids.update(claim_id for _evidence_id, claim_id in bindings)
        compiled_operations.append(
            CompiledOperation(
                mode=op.mode,
                claim_bindings=bindings,
                old_sha256=_sha256_bytes(op.old.encode("utf-8")),
                new_sha256=_sha256_bytes(op.new.encode("utf-8")),
                expected_count=op.expected_count,
            )
        )

    if after == before:
        raise IntegrationPlanError(
            f"operations cancel to a no-op for {page.path}; refusing a false change receipt"
        )

    after_sha = _sha256_bytes(after.encode("utf-8"))
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{page.path}",
            tofile=f"b/{page.path}",
        )
    )
    return CompiledChange(
        path=target,
        relative_path=page.path,
        before_sha256=before_sha,
        after_sha256=after_sha,
        before=before,
        after=after,
        diff=diff,
        evidence_ids=tuple(sorted(evidence_ids)),
        claim_ids=tuple(sorted(claim_ids)),
        operations=tuple(compiled_operations),
    )


@contextmanager
def _exclusive_wiki_lock(root: Path):
    """Serialize cooperative wiki writers without creating a vault artifact."""
    if not root.is_dir():
        raise IntegrationPlanError(f"wiki root missing: {root}")
    descriptor: int | None = None
    try:
        descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        metadata = os.fstat(descriptor)
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise IntegrationPlanError(
            f"cannot acquire wiki lock for {root}: {exc}"
        ) from exc
    try:
        yield (metadata.st_dev, metadata.st_ino)
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_utf8_bytes_no_follow(path: Path, *, kind: str) -> bytes:
    """Read a regular UTF-8 input without following file or directory symlinks."""

    try:
        text = read_anchored_text(path.parent, path.name)
    except (AnchoredWriteError, OSError) as exc:
        raise IntegrationPlanError(f"unsafe {kind} {path}: {exc}") from exc
    if text is None:
        raise IntegrationPlanError(f"{kind} missing: {path}")
    return text.encode("utf-8")


def _paths_alias(left: Path, right: Path) -> bool:
    """Detect lexical aliases and existing hard-link aliases."""

    if os.path.normcase(os.path.abspath(left)) == os.path.normcase(
        os.path.abspath(right)
    ):
        return True
    try:
        return os.path.samestat(
            left.stat(follow_symlinks=False), right.stat(follow_symlinks=False)
        )
    except OSError:
        return False


def _normalise_authority_roots(
    explicit: Iterable[Path | str] | None, *, environment_name: str
) -> tuple[Path, ...]:
    raw_values: Iterable[Path | str]
    if explicit is None:
        configured = os.environ.get(environment_name, "").strip()
        raw_values = configured.split(os.pathsep) if configured else ()
    else:
        raw_values = explicit
    roots = tuple(
        sorted(
            {Path(value).expanduser().resolve() for value in raw_values if str(value)},
            key=lambda path: path.as_posix().casefold(),
        )
    )
    missing = tuple(path for path in roots if not path.is_dir())
    if missing:
        raise IntegrationPlanError(
            f"configured {environment_name} root is not a directory: "
            + ", ".join(str(path) for path in missing)
        )
    return roots


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
