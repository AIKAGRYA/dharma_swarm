"""Atomic deterministic wiki maintenance after chetana approval."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import staging as staging_mod
from .backlinks import (
    DEFAULT_CONTENT_LAYER_NAMES,
    MAX_BACKLINK_APPLY_PAGES,
    BacklinkError,
    discover_markdown_pages,
    exclusive_backlink_lock,
    governing_manifest_paths,
    manifest_candidate_paths,
    plan_backlinks,
    select_backlink_changes,
)
from .governance import current_kernel_signature
from .provenance import (
    SIGNATURE_V2_PREFIX,
    compute_axiom_signature_v2,
    parse_frontmatter,
    signature_matches,
)
from .safe_write import (
    AnchoredTextChange,
    AnchoredWriteError,
    apply_anchored_text_changes,
    capture_anchor_identity,
    read_anchored_text,
)
from .wiki_log import render_wiki_log_entry


CONTRADICTION_MARKERS = ("contradict", "conflict", "supersede", "disagree")
_INDEX_ENTRY_RE = re.compile(
    r"^- (?P<link>\[\[[^\]\r\n]+\]\]) — atom_id=(?P<atom_id>[0-9a-f-]+)[ \t]*$"
)


@dataclass
class CrossUpdateResult:
    atom_path: Path
    index_path: Path
    backlinks_updated: list[Path] = field(default_factory=list)
    missing_related: list[str] = field(default_factory=list)
    contradictions_flagged: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def cross_update_trusted(
    atom_path: Path, *, append_log: bool = True
) -> CrossUpdateResult:
    """Atomically update index, backlink projections, and log for an approved atom.

    The function accepts only a v2-signed, human-approved atom in the trusted
    concepts projection. Keyword matches are never promoted into contradiction
    facts; typed integration plans own that authority boundary.
    """

    atom_path = Path(atom_path).expanduser().resolve()
    return _cross_update_transaction(atom_path, append_log=append_log)


def integrate_approved_atom(
    *,
    source_path: Path,
    source_original_text: str,
    approved_text: str,
    reviewer: str,
    prior_status: str,
) -> CrossUpdateResult:
    """Publish approval plus backlinks/index/log as one anchored transaction.

    Pending atoms are created in ``concepts/`` and removed from ``pending/``
    inside the same rollback boundary. Existing trusted-but-unapproved atoms
    are replaced in place. Active signed manifests fail closed until a
    page-plus-manifest signer transaction is implemented.
    """

    wiki_root = Path(staging_mod.WIKI_ROOT).expanduser().resolve()
    pending_root = (wiki_root / "pending").resolve()
    trusted_root = wiki_root / "concepts"
    # The first approval creates the curated layer directory; content remains
    # invisible until the anchored page/index/log transaction commits.
    trusted_root.mkdir(parents=True, exist_ok=True)
    trusted_root = trusted_root.resolve()
    source_path = Path(source_path).expanduser().resolve()
    try:
        source_path.relative_to(pending_root)
    except ValueError:
        try:
            source_path.relative_to(trusted_root)
        except ValueError as exc:
            raise ValueError(
                "atomic approval accepts only wiki/pending or trusted concepts "
                f"sources: {source_path}"
            ) from exc
        atom_path = source_path
    else:
        atom_path = trusted_root / source_path.name

    return _cross_update_transaction(
        atom_path,
        append_log=True,
        proposed_atom_text=approved_text,
        source_path=source_path,
        source_original_text=source_original_text,
        log_operation="approve-integrate",
        extra_log_details={"reviewer": reviewer, "prior_status": prior_status},
    )


def _cross_update_transaction(
    atom_path: Path,
    *,
    append_log: bool,
    proposed_atom_text: str | None = None,
    source_path: Path | None = None,
    source_original_text: str | None = None,
    log_operation: str = "cross-update",
    extra_log_details: dict[str, str] | None = None,
) -> CrossUpdateResult:
    """Evaluate and commit one trusted projection transaction."""

    wiki_root = Path(staging_mod.WIKI_ROOT).expanduser().resolve()
    trusted_root = (wiki_root / "concepts").resolve()
    try:
        relative_atom = atom_path.relative_to(wiki_root)
        atom_path.relative_to(trusted_root)
    except ValueError as exc:
        raise ValueError(
            f"cross-update target is outside the trusted concepts projection: {atom_path}"
        ) from exc

    index_path = wiki_root / "index.md"
    content_roots = [
        wiki_root / name
        for name in DEFAULT_CONTENT_LAYER_NAMES
        if (wiki_root / name).is_dir()
    ]
    if not content_roots:
        raise BacklinkError("cross-update found no canonical content roots")

    expected_layer_names = tuple(path.name for path in content_roots)

    with exclusive_backlink_lock([wiki_root]) as anchor_identity:
        atom_original = read_anchored_text(wiki_root, relative_atom.as_posix())
        if proposed_atom_text is None:
            if atom_original is None:
                raise ValueError(f"trusted atom disappeared: {atom_path}")
            atom_text = atom_original
        else:
            if source_path is None or source_original_text is None:
                raise ValueError("proposed approval requires its exact source snapshot")
            relative_source = source_path.relative_to(wiki_root).as_posix()
            current_source = read_anchored_text(wiki_root, relative_source)
            if current_source != source_original_text:
                raise ValueError(
                    "approval source changed after verification; refusing integration"
                )
            if source_path != atom_path and atom_original is not None:
                raise FileExistsError(
                    f"slug collision: trusted target already exists: {atom_path}"
                )
            if source_path == atom_path and atom_original != source_original_text:
                raise ValueError(
                    "trusted approval target changed after verification; refusing"
                )
            atom_text = proposed_atom_text
        schema, body = parse_frontmatter(atom_text, source_path=str(atom_path))
        if schema is None:
            raise ValueError(f"{atom_path} has no chetana frontmatter")
        kernel_signature = _require_approved_trusted_atom(schema, body, atom_path)

        active_manifests = governing_manifest_paths(content_roots)
        if active_manifests:
            raise BacklinkError(
                "cross-update requires an atomic page-plus-manifest transaction; "
                "refusing index/backlink/log writes: "
                + ", ".join(str(path) for path in active_manifests)
            )

        baseline_plan = None
        if proposed_atom_text is not None and discover_markdown_pages(content_roots):
            baseline_plan = plan_backlinks(content_roots)
        backlink_plan = plan_backlinks(
            content_roots,
            virtual_pages=(
                {atom_path: atom_text} if proposed_atom_text is not None else None
            ),
        )
        if proposed_atom_text is not None:
            baseline_projected = (
                _projected_page_text(baseline_plan) if baseline_plan is not None else {}
            )
            proposed_projected = _projected_page_text(backlink_plan)
            affected = {atom_path}
            affected.update(
                path
                for path in set(baseline_projected) & set(proposed_projected)
                if baseline_projected[path] != proposed_projected[path]
            )
        else:
            affected = {atom_path}
            affected.update(
                target
                for target, sources in backlink_plan.inbound_by_page.items()
                if atom_path in sources
            )
        backlink_report = select_backlink_changes(backlink_plan, affected)
        if backlink_report.changed_count > MAX_BACKLINK_APPLY_PAGES:
            raise BacklinkError(
                "cross-update backlink batch exceeds the "
                f"{MAX_BACKLINK_APPLY_PAGES}-page migration limit"
            )

        result = CrossUpdateResult(atom_path=atom_path, index_path=index_path)
        result.backlinks_updated.extend(backlink_report.changed_paths)
        result.notes.append(
            "computed backlinks: "
            f"edges={backlink_report.edge_count}, "
            f"written={backlink_report.changed_count}, "
            f"unresolved={backlink_report.unresolved_count}"
        )

        for related in schema.related:
            related_path = staging_mod.trusted_path_for(
                related, root=staging_mod.TRUSTED_DEFAULT
            )
            if not related_path.exists():
                result.missing_related.append(related)

        if any(marker in body.lower() for marker in CONTRADICTION_MARKERS):
            result.notes.append(
                "contradiction language detected; no ledger fact emitted without "
                "a typed claim ID and authoritative evidence"
            )

        index_original = read_anchored_text(wiki_root, "index.md")
        index_updated = _render_index_update(
            index_original,
            atom_path=atom_path,
            title=schema.title,
            atom_id=schema.atom_id,
            wiki_root=wiki_root,
        )
        log_original = read_anchored_text(wiki_root, "log.md") if append_log else None
        log_updated = log_original
        if append_log:
            details = {
                "backlink_pages": str(backlink_report.changed_count),
                "semantic_edges": str(backlink_report.edge_count),
                "unresolved_links": str(backlink_report.unresolved_count),
            }
            details.update(extra_log_details or {})
            entry = render_wiki_log_entry(
                operation=log_operation,
                title=schema.title,
                atom_path=atom_path,
                atom_id=schema.atom_id,
                details=details,
            )
            separator = "" if not log_original or log_original.endswith("\n") else "\n"
            log_updated = (log_original or "") + separator + entry

        transaction_changes = []
        atom_projection_planned = False
        for change in backlink_report.changes:
            projected_text = _resign_projected_page(
                change.original_text,
                change.updated_text,
                kernel_signature=kernel_signature,
                path=change.path,
            )
            transaction_changes.append(
                AnchoredTextChange(
                    relative_path=change.path.relative_to(wiki_root).as_posix(),
                    original_text=(
                        atom_original
                        if proposed_atom_text is not None and change.path == atom_path
                        else change.original_text
                    ),
                    updated_text=projected_text,
                )
            )
            atom_projection_planned = (
                atom_projection_planned or change.path == atom_path
            )
        if proposed_atom_text is not None and not atom_projection_planned:
            transaction_changes.append(
                AnchoredTextChange(
                    relative_path=relative_atom.as_posix(),
                    original_text=atom_original,
                    updated_text=atom_text,
                )
            )
        if source_path is not None and source_path != atom_path:
            transaction_changes.append(
                AnchoredTextChange(
                    relative_path=source_path.relative_to(wiki_root).as_posix(),
                    original_text=source_original_text,
                    updated_text=None,
                )
            )
        if index_updated != index_original:
            transaction_changes.append(
                AnchoredTextChange(
                    relative_path="index.md",
                    original_text=index_original,
                    updated_text=index_updated,
                )
            )
        if append_log and log_updated != log_original:
            transaction_changes.append(
                AnchoredTextChange(
                    relative_path="log.md",
                    original_text=log_original,
                    updated_text=log_updated or "",
                )
            )

        expected_text = {
            path.relative_to(wiki_root).as_posix(): text
            for path, text in backlink_report.page_text.items()
        }
        if proposed_atom_text is not None:
            expected_text[relative_atom.as_posix()] = atom_original
        if source_path is not None:
            expected_text[source_path.relative_to(wiki_root).as_posix()] = (
                source_original_text
            )
        expected_text["index.md"] = index_original
        if append_log:
            expected_text["log.md"] = log_original
        for manifest_path in manifest_candidate_paths(content_roots):
            if not manifest_path.parent.is_dir():
                continue
            try:
                relative_manifest = manifest_path.relative_to(wiki_root).as_posix()
            except ValueError:
                continue
            expected_text[relative_manifest] = None
        try:
            apply_anchored_text_changes(
                wiki_root,
                transaction_changes,
                expected_text=expected_text,
                expected_anchor_identity=anchor_identity,
                final_validator=lambda: _validate_cross_update_projection(
                    backlink_plan, expected_layer_names=expected_layer_names
                ),
            )
        except (AnchoredWriteError, OSError) as exc:
            raise BacklinkError(f"cross-update transaction failed: {exc}") from exc

        if append_log:
            result.notes.append(f"log appended -> {wiki_root / 'log.md'}")
        return result


def _projected_page_text(backlink_plan) -> dict[Path, str]:
    """Return each page's desired bytes for comparing virtual-page effects."""

    projected = dict(backlink_plan.page_text)
    projected.update(
        {change.path: change.updated_text for change in backlink_plan.changes}
    )
    return projected


def _validate_cross_update_projection(
    backlink_plan, *, expected_layer_names: tuple[str, ...]
) -> None:
    wiki_root = Path(staging_mod.WIKI_ROOT).expanduser().resolve()
    current_layer_names = tuple(
        name for name in DEFAULT_CONTENT_LAYER_NAMES if (wiki_root / name).is_dir()
    )
    if current_layer_names != expected_layer_names:
        raise BacklinkError(
            "canonical content-layer set changed during cross-update; refusing success"
        )
    if set(discover_markdown_pages(backlink_plan.content_roots)) != set(
        backlink_plan.page_sha256
    ):
        raise BacklinkError(
            "cross-update corpus membership changed during apply; refusing success"
        )
    active_manifests = governing_manifest_paths(backlink_plan.content_roots)
    if active_manifests:
        raise BacklinkError(
            "manifest appeared during cross-update; refusing writes: "
            + ", ".join(str(path) for path in active_manifests)
        )


def _require_approved_trusted_atom(schema, body: str, atom_path: Path) -> str:
    provenance = schema.provenance
    if provenance is None or provenance.review_status != "approved":
        raise ValueError(
            f"cross-update requires approved provenance for trusted atom: {atom_path}"
        )
    if not provenance.axiom_signature.startswith(SIGNATURE_V2_PREFIX):
        raise ValueError("cross-update requires a v2 signature binding review status")
    kernel_signature = current_kernel_signature()
    if kernel_signature == "0" * 64 or not signature_matches(
        provenance.axiom_signature, schema, body, kernel_signature
    ):
        raise ValueError(
            "cross-update atom signature does not verify under current kernel"
        )
    return kernel_signature


def _resign_projected_page(
    original_text: str,
    updated_text: str,
    *,
    kernel_signature: str,
    path: Path,
) -> str:
    """Preserve valid approved provenance after changing a derived block."""

    original_schema, original_body = parse_frontmatter(
        original_text, source_path=str(path)
    )
    if original_schema is None or original_schema.provenance is None:
        return updated_text
    provenance = original_schema.provenance
    if provenance.review_status != "approved":
        raise ValueError(f"refusing projection write to unapproved atom: {path}")
    old_signature = provenance.axiom_signature
    if not old_signature.startswith(SIGNATURE_V2_PREFIX) or not signature_matches(
        old_signature, original_schema, original_body, kernel_signature
    ):
        raise ValueError(f"refusing projection write to signature-invalid atom: {path}")

    updated_schema, updated_body = parse_frontmatter(
        updated_text, source_path=str(path)
    )
    if updated_schema is None or updated_schema.provenance is None:
        raise ValueError(f"projection removed signed provenance: {path}")
    new_signature = compute_axiom_signature_v2(
        updated_schema, updated_body, kernel_signature
    )
    signature_line = re.compile(
        r"(?m)^(?P<prefix>[ \t]*axiom_signature:[ \t]*)"
        r"(?P<quote>['\"]?)" + re.escape(old_signature) + r"(?P=quote)[ \t]*$"
    )
    rewritten, count = signature_line.subn(
        lambda match: (
            f"{match.group('prefix')}{match.group('quote')}"
            f"{new_signature}{match.group('quote')}"
        ),
        updated_text,
    )
    if count != 1:
        raise ValueError(
            f"expected one signed provenance field in {path}, found {count}"
        )
    return rewritten


def cross_update_summary(result: CrossUpdateResult) -> str:
    return "\n".join(
        [
            "# chetana cross-update",
            f"- atom: {result.atom_path}",
            f"- index: {result.index_path}",
            f"- backlinks_updated: {len(result.backlinks_updated)}",
            f"- missing_related: {len(result.missing_related)}",
            f"- contradictions_flagged: {len(result.contradictions_flagged)}",
        ]
    )


def _upsert_index_entry(
    index_path: Path, atom_path: Path, title: str, atom_id: str
) -> None:
    """Compatibility helper for one exact, descriptor-anchored index upsert."""

    wiki_root = Path(staging_mod.WIKI_ROOT).expanduser().resolve()
    anchor_identity = capture_anchor_identity(wiki_root)
    relative_index = index_path.resolve().relative_to(wiki_root).as_posix()
    original = read_anchored_text(wiki_root, relative_index)
    updated = _render_index_update(
        original,
        atom_path=atom_path,
        title=title,
        atom_id=atom_id,
        wiki_root=wiki_root,
    )
    if updated == original:
        return
    apply_anchored_text_changes(
        wiki_root,
        [
            AnchoredTextChange(
                relative_path=relative_index,
                original_text=original,
                updated_text=updated,
            )
        ],
        expected_text={relative_index: original},
        expected_anchor_identity=anchor_identity,
    )


def _render_index_update(
    original: str | None,
    *,
    atom_path: Path,
    title: str,
    atom_id: str,
    wiki_root: Path,
) -> str:
    line = f"- {_wiki_link(atom_path, title, wiki_root)} — atom_id={atom_id}"
    initial = original if original is not None else "# Index\n\n## Concepts\n\n"
    lines = initial.splitlines()
    link_target = _wikilink_target(_wiki_link(atom_path, title, wiki_root))
    matching_indices = [
        index
        for index, existing in enumerate(lines)
        if _generated_index_target(existing) == link_target
    ]
    if len(matching_indices) > 1:
        raise ValueError(f"duplicate generated index entries for {link_target}")
    if matching_indices:
        lines[matching_indices[0]] = line
    else:
        if "## Concepts" not in lines:
            lines.extend(["", "## Concepts"])
        lines.append(line)
    return "\n".join(lines).rstrip() + "\n"


def _generated_index_target(text: str) -> str | None:
    match = _INDEX_ENTRY_RE.fullmatch(text)
    return _wikilink_target(match.group("link")) if match else None


def _wikilink_target(text: str) -> str | None:
    match = re.search(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]", text)
    return match.group(1).strip() if match else None


def _wiki_link(path: Path, title: str, wiki_root: Path) -> str:
    wiki_root = wiki_root.resolve()
    path = path.resolve()
    try:
        rel = path.relative_to(wiki_root).with_suffix("")
    except ValueError:
        raise ValueError(f"cannot index a path outside the wiki root: {path}") from None
    target = rel.as_posix()
    if any(character in target for character in "[]|#\r\n"):
        raise ValueError(f"unsafe wikilink target for index entry: {target!r}")
    safe_title = " ".join(str(title).splitlines()).strip()
    safe_title = safe_title.replace("|", "¦").replace("[", "(").replace("]", ")")
    return f"[[{target}|{safe_title}]]"
