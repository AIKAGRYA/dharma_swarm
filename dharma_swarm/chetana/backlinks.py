"""Deterministic, marker-bounded backlink reconciliation for markdown wikis.

Backlinks are a derived projection of authored wikilinks and explicit
``related:`` frontmatter. Only links outside ``BACKLINKS_BEGIN`` /
``BACKLINKS_END`` blocks create body edges, and recovery-generated metadata is
excluded; otherwise generated material could recursively manufacture graph
connectivity.

Planning is read-only.  Callers must pass ``apply=True`` to
:func:`reconcile_backlinks`, or explicitly pass a plan to
:func:`apply_backlink_plan`, before any file is written.
"""

from __future__ import annotations

import fcntl
import os
import re
import unicodedata
from contextlib import contextmanager
from hashlib import sha256
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Iterable, Mapping
from urllib.parse import unquote

from .backlink_markdown import (
    extract_frontmatter_related_targets as _extract_frontmatter_related_targets,
    extract_wikilink_targets as _extract_wikilink_targets,
    fenced_code_spans as _fenced_code_spans,
    has_signed_provenance as _has_signed_provenance,
    position_in_spans as _position_in_spans,
    without_frontmatter as _without_frontmatter,
)
from .manifest import MANIFEST_ENV
from .safe_write import (
    AnchorIdentity,
    AnchoredTextChange,
    AnchoredWriteError,
    apply_anchored_text_changes,
)


BACKLINKS_BEGIN = "<!-- BACKLINKS_BEGIN -->"
BACKLINKS_END = "<!-- BACKLINKS_END -->"
MAX_BACKLINK_APPLY_PAGES = 25
DEFAULT_CONTENT_LAYER_NAMES = (
    "concepts",
    "connections",
    "mocs",
    "research",
    "tooling",
)

_EXCLUDED_DIRECTORY_NAMES = frozenset(
    {"raw", "meta", "pending", "backup", "backups", "generated"}
)
_BEGIN_RE = re.compile(re.escape(BACKLINKS_BEGIN) + r"(?:[ \t]*\r?\n)?")
_END_RE = re.compile(re.escape(BACKLINKS_END) + r"(?:[ \t]*\r?\n)?")
_H2_RE = re.compile(r"(?m)^##(?!#)[ \t]+[^\r\n]*(?:\r?\n|$)")
_BACKLINK_HEADING_RE = re.compile(r"(?m)^## Backlinks[ \t]*(?:\r?\n|$)")
_PRECEDING_BACKLINK_HEADING_RE = re.compile(
    r"(?m)^## Backlinks[ \t]*\r?\n(?:[ \t]*\r?\n)*\Z"
)
_STRICT_BACKLINK_BULLET_RE = re.compile(r"[ \t]*[-+*][ \t]+\[\[[^\[\]\r\n]+\]\][ \t]*")


class BacklinkError(ValueError):
    """Base class for backlink planning and application failures."""


class BacklinkFormatError(BacklinkError):
    """Raised when a page has malformed or nested backlink markers."""


class BacklinkPlanStaleError(BacklinkError):
    """Raised when a page changed after its backlink plan was computed."""


@dataclass(frozen=True)
class BacklinkChange:
    """One marker-bounded page rewrite proposed by a backlink plan."""

    path: Path
    original_text: str
    updated_text: str
    expected_inbound: tuple[Path, ...]
    missing_inbound: tuple[Path, ...]
    false_references: tuple[str, ...]


@dataclass(frozen=True)
class BacklinkReport:
    """Read-only plan, or the result of explicitly applying that plan."""

    content_roots: tuple[Path, ...]
    scanned_count: int
    edge_count: int
    inbound_by_page: Mapping[Path, tuple[Path, ...]]
    page_sha256: Mapping[Path, str]
    page_text: Mapping[Path, str]
    changes: tuple[BacklinkChange, ...]
    missing_count: int
    false_count: int
    changed_count: int
    unresolved_count: int = 0
    applied: bool = False
    written_count: int = 0
    virtual_paths: tuple[Path, ...] = ()

    @property
    def changed_paths(self) -> tuple[Path, ...]:
        return tuple(change.path for change in self.changes)


@dataclass(frozen=True)
class _Page:
    path: Path
    text: str
    aliases: tuple[tuple[str, str], ...]


def discover_markdown_pages(content_roots: Iterable[Path | str]) -> tuple[Path, ...]:
    """Return safe markdown pages below ``content_roots`` in stable order.

    Directories named ``raw``, ``_meta``, ``pending``, ``backup``/``backups``,
    or ``generated`` (including dated ``backup-*`` / ``generated-*`` variants)
    are excluded at every depth.  Symlinks are deliberately not followed.
    """

    roots = _normalise_roots(content_roots)
    discovered: set[Path] = set()
    for root in roots:
        if root.is_symlink() or _path_has_excluded_directory(
            root, include_leaf=root.is_dir()
        ):
            continue
        if root.is_file():
            candidates = (root,) if root.suffix.casefold() == ".md" else ()
        elif root.is_dir():
            candidates = root.rglob("*.md")
        else:
            continue
        for candidate in candidates:
            if candidate.is_symlink() or not candidate.is_file():
                continue
            try:
                relative = (
                    candidate.relative_to(root)
                    if root.is_dir()
                    else Path(candidate.name)
                )
            except ValueError:
                continue
            if any(_is_excluded_directory(part) for part in relative.parts[:-1]):
                continue
            discovered.add(candidate.resolve())
    return tuple(sorted(discovered, key=_path_sort_key))


def plan_backlinks(
    content_roots: Iterable[Path | str],
    *,
    virtual_pages: Mapping[Path | str, str] | None = None,
) -> BacklinkReport:
    """Compute the exact projection, optionally including proposed page bytes.

    ``virtual_pages`` exists for the atomic approval transaction: it lets the
    evaluator account for a not-yet-published concept without exposing a
    partially integrated page on disk. Standalone backlink apply refuses such
    plans; the approval transaction owns their create/move semantics.
    """

    roots = _normalise_roots(content_roots)
    virtual = _normalise_virtual_pages(virtual_pages or {}, roots=roots)
    paths = tuple(
        sorted(set(discover_markdown_pages(roots)) | set(virtual), key=_path_sort_key)
    )
    if not paths:
        raise BacklinkError(
            "configured content roots contain no eligible markdown pages; "
            "refusing a false-green backlink check"
        )
    common_base = _common_content_base(roots)

    page_aliases = {
        path: _aliases_for_page(path, roots=roots, common_base=common_base)
        for path in paths
    }
    pages = tuple(
        _Page(
            path=path,
            text=virtual[path] if path in virtual else _read_page(path),
            aliases=page_aliases[path],
        )
        for path in paths
    )
    pages_by_path = {page.path: page for page in pages}
    alias_index = _build_alias_index(pages)
    canonical_targets = {
        page.path: _canonical_target(page, alias_index) for page in pages
    }

    inbound: dict[Path, set[Path]] = {page.path: set() for page in pages}
    unresolved_count = 0
    for source in pages:
        authored_text = _without_backlink_projections(source.text, path=source.path)
        authored_targets = set(
            _extract_wikilink_targets(_without_frontmatter(authored_text))
        )
        authored_targets.update(_extract_frontmatter_related_targets(authored_text))
        for raw_target in authored_targets:
            target = _resolve_wikilink(
                raw_target,
                source=source.path,
                alias_index=alias_index,
                pages_by_path=pages_by_path,
            )
            if target is None:
                unresolved_count += 1
                continue
            inbound[target].add(source.path)

    exact_inbound = {
        path: tuple(sorted(sources, key=_path_sort_key))
        for path, sources in inbound.items()
    }
    changes: list[BacklinkChange] = []
    missing_count = 0
    false_count = 0
    for page in pages:
        expected = exact_inbound[page.path]
        missing, false = _compare_existing_block(
            page,
            expected=expected,
            alias_index=alias_index,
            pages_by_path=pages_by_path,
        )
        updated = _updated_page_text(
            page.text,
            expected=expected,
            canonical_targets=canonical_targets,
            path=page.path,
        )
        missing_count += len(missing)
        false_count += len(false)
        if updated != page.text:
            changes.append(
                BacklinkChange(
                    path=page.path,
                    original_text=page.text,
                    updated_text=updated,
                    expected_inbound=expected,
                    missing_inbound=missing,
                    false_references=false,
                )
            )

    frozen_inbound = MappingProxyType(exact_inbound)
    page_sha256 = MappingProxyType(
        {page.path: sha256(page.text.encode("utf-8")).hexdigest() for page in pages}
    )
    page_text = MappingProxyType({page.path: page.text for page in pages})
    return BacklinkReport(
        content_roots=roots,
        scanned_count=len(pages),
        edge_count=sum(len(sources) for sources in exact_inbound.values()),
        inbound_by_page=frozen_inbound,
        page_sha256=page_sha256,
        page_text=page_text,
        changes=tuple(changes),
        missing_count=missing_count,
        false_count=false_count,
        changed_count=len(changes),
        unresolved_count=unresolved_count,
        virtual_paths=tuple(sorted(virtual, key=_path_sort_key)),
    )


def apply_backlink_plan(plan: BacklinkReport) -> BacklinkReport:
    """Apply a previously computed plan after validating every target.

    Validation happens for the full change set before the first write.  A page
    that already equals its planned output is skipped, making re-application
    safe; any other post-plan edit fails closed rather than being overwritten.
    """

    with exclusive_backlink_lock(plan.content_roots) as anchor_identity:
        return _apply_backlink_plan_locked(plan, anchor_identity=anchor_identity)


def _apply_backlink_plan_locked(
    plan: BacklinkReport, *, anchor_identity: AnchorIdentity
) -> BacklinkReport:
    """Apply a plan while holding the cooperative wiki-writer lock."""

    if plan.virtual_paths:
        raise BacklinkError(
            "virtual-page backlink plans may only be applied by the atomic "
            "approved-atom transaction"
        )

    current_paths = set(discover_markdown_pages(plan.content_roots))
    planned_paths = set(plan.page_sha256)
    if current_paths != planned_paths:
        added = sorted(current_paths - planned_paths, key=_path_sort_key)
        removed = sorted(planned_paths - current_paths, key=_path_sort_key)
        raise BacklinkPlanStaleError(
            "backlink corpus changed after planning"
            f"; added={len(added)}, removed={len(removed)}"
        )

    changes_by_path = {change.path: change for change in plan.changes}
    current_text: dict[Path, str] = {}
    for path, expected_hash in plan.page_sha256.items():
        text = _read_page(path)
        current_text[path] = text
        if sha256(text.encode("utf-8")).hexdigest() == expected_hash:
            continue
        change = changes_by_path.get(path)
        if change is None or text != change.updated_text:
            raise BacklinkPlanStaleError(
                f"backlink plan is stale; refusing to overwrite {path}"
            )

    pending: list[BacklinkChange] = []
    for change in plan.changes:
        _assert_safe_apply_path(change.path, plan.content_roots)
        current = current_text[change.path]
        if current == change.updated_text:
            continue
        if current != change.original_text:
            raise BacklinkPlanStaleError(
                f"backlink plan is stale; refusing to overwrite {change.path}"
            )
        pending.append(change)

    if len(pending) > MAX_BACKLINK_APPLY_PAGES:
        raise BacklinkError(
            "backlink apply exceeds the "
            f"{MAX_BACKLINK_APPLY_PAGES}-page migration limit"
        )

    signed_targets = [
        change.path
        for change in pending
        if _has_signed_provenance(change.original_text)
    ]
    if signed_targets:
        raise BacklinkError(
            "standalone backlink apply would invalidate signed provenance; "
            "use the atomic approved-atom cross-update path: "
            + ", ".join(str(path) for path in signed_targets)
        )

    active_manifests = _active_manifest_paths(plan.content_roots)
    if pending and active_manifests:
        raise BacklinkError(
            "manifest-governed backlink updates require an atomic "
            "page-plus-manifest transaction; refusing writes: "
            + ", ".join(str(path) for path in active_manifests)
        )

    anchor_root = _common_lock_root(plan.content_roots)
    guarded_corpus: dict[Path, str | None] = dict(current_text)
    for manifest_path in _manifest_candidate_paths(plan.content_roots):
        if not manifest_path.parent.is_dir():
            continue
        try:
            manifest_path.relative_to(anchor_root)
        except ValueError:
            continue
        guarded_corpus[manifest_path] = None
    _apply_atomic_changes(
        pending,
        expected_corpus_text=guarded_corpus,
        anchor_root=anchor_root,
        anchor_identity=anchor_identity,
        final_validator=lambda: _validate_plan_corpus_and_manifest(plan),
    )

    return replace(plan, applied=True, written_count=len(pending))


def select_backlink_changes(
    plan: BacklinkReport, target_paths: Iterable[Path | str]
) -> BacklinkReport:
    """Limit writes to explicit pages while retaining the full corpus guard."""
    requested = {Path(path).expanduser().resolve() for path in target_paths}
    unknown = requested - set(plan.page_sha256)
    if unknown:
        rendered = ", ".join(str(path) for path in sorted(unknown, key=_path_sort_key))
        raise BacklinkError(f"selected page is outside the scanned corpus: {rendered}")
    changes = tuple(change for change in plan.changes if change.path in requested)
    return replace(
        plan,
        changes=changes,
        missing_count=sum(len(change.missing_inbound) for change in changes),
        false_count=sum(len(change.false_references) for change in changes),
        changed_count=len(changes),
        applied=False,
        written_count=0,
    )


def reconcile_backlinks(
    content_roots: Iterable[Path | str], *, apply: bool = False
) -> BacklinkReport:
    """Plan backlink reconciliation and optionally apply it explicitly."""

    plan = plan_backlinks(content_roots)
    return apply_backlink_plan(plan) if apply else plan


def check_backlinks(content_roots: Iterable[Path | str]) -> BacklinkReport:
    """Read-only spelling of :func:`plan_backlinks` for operator integrations."""

    return plan_backlinks(content_roots)


def governing_manifest_paths(
    content_roots: Iterable[Path | str],
) -> tuple[Path, ...]:
    """Return manifests governing any configured root or its ancestors."""

    return _active_manifest_paths(_normalise_roots(content_roots))


def manifest_candidate_paths(
    content_roots: Iterable[Path | str],
) -> tuple[Path, ...]:
    """Return every manifest pathname considered by the governance gate."""

    return _manifest_candidate_paths(_normalise_roots(content_roots))


def _normalise_roots(content_roots: Iterable[Path | str]) -> tuple[Path, ...]:
    # ``Path.resolve`` is deliberate here.  Darwin exposes /var as an alias for
    # /private/var; mixing an ``abspath`` root with resolved discovered pages
    # makes a valid page appear to escape its configured root at apply time.
    roots = {Path(root).expanduser().resolve() for root in content_roots}
    if not roots:
        raise BacklinkError("at least one content root is required")
    missing = tuple(
        sorted((root for root in roots if not root.exists()), key=_path_sort_key)
    )
    if missing:
        raise BacklinkError(
            "configured content root does not exist: "
            + ", ".join(str(path) for path in missing)
        )
    return tuple(sorted(roots, key=_path_sort_key))


def _normalise_virtual_pages(
    virtual_pages: Mapping[Path | str, str], *, roots: tuple[Path, ...]
) -> dict[Path, str]:
    normalised: dict[Path, str] = {}
    for raw_path, text_value in virtual_pages.items():
        if not isinstance(text_value, str):
            raise BacklinkError(f"virtual page text must be a string: {raw_path}")
        lexical = Path(raw_path).expanduser()
        if lexical.is_symlink():
            raise BacklinkError(f"virtual page cannot target a symlink: {lexical}")
        path = lexical.resolve()
        if path.suffix.casefold() != ".md":
            raise BacklinkError(f"virtual page must be markdown: {path}")
        if _path_has_excluded_directory(path, include_leaf=False):
            raise BacklinkError(f"virtual page is in an excluded directory: {path}")
        if not any(
            (root.is_dir() and path.is_relative_to(root)) or path == root
            for root in roots
        ):
            raise BacklinkError(f"virtual page is outside the scanned roots: {path}")
        if path in normalised:
            raise BacklinkError(f"duplicate virtual page: {path}")
        normalised[path] = text_value
    return normalised


@contextmanager
def exclusive_backlink_lock(roots: Iterable[Path | str]):
    """Serialize cooperative writers using the nearest shared directory.

    The directory descriptor is the lock object, so no generated lock file is
    introduced into the wiki.  Page-level roots use their parent directory.
    """

    normalised_roots = _normalise_roots(roots)
    lock_root = _common_lock_root(normalised_roots)
    if not lock_root.is_dir():
        raise BacklinkError(f"backlink lock directory missing: {lock_root}")
    descriptor: int | None = None
    try:
        descriptor = os.open(lock_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        metadata = os.fstat(descriptor)
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise BacklinkError(
            f"cannot acquire backlink lock for {lock_root}: {exc}"
        ) from exc
    try:
        yield (metadata.st_dev, metadata.st_ino)
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _common_lock_root(roots: tuple[Path, ...]) -> Path:
    directory_roots = tuple(root if root.is_dir() else root.parent for root in roots)
    if not directory_roots:
        raise BacklinkError("at least one content root is required")
    try:
        common = Path(os.path.commonpath(directory_roots)).resolve()
    except ValueError as exc:
        raise BacklinkError("content roots do not share a lockable directory") from exc
    # A scoped canonical-layer plan still writes a projection governed by the
    # wiki root. Anchor at that root so ancestor manifests can be pinned in the
    # same descriptor transaction.
    for candidate in (common, *common.parents):
        if candidate.name in DEFAULT_CONTENT_LAYER_NAMES:
            return candidate.parent
    return common


def _read_page(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise BacklinkError(f"cannot read markdown page {path}: {exc}") from exc


def _apply_atomic_changes(
    changes: Iterable[BacklinkChange],
    *,
    expected_corpus_text: Mapping[Path, str | None],
    anchor_root: Path,
    anchor_identity: AnchorIdentity,
    final_validator: Callable[[], None],
) -> None:
    """Apply a descriptor-anchored batch; pathname swaps cannot redirect it."""

    try:
        anchored_changes = tuple(
            AnchoredTextChange(
                relative_path=change.path.relative_to(anchor_root).as_posix(),
                original_text=change.original_text,
                updated_text=change.updated_text,
            )
            for change in changes
        )
        anchored_expected = {
            path.relative_to(anchor_root).as_posix(): text
            for path, text in expected_corpus_text.items()
        }
    except ValueError as exc:
        raise BacklinkError(
            f"backlink path escaped the anchored transaction root: {exc}"
        ) from exc
    try:
        apply_anchored_text_changes(
            anchor_root,
            anchored_changes,
            expected_text=anchored_expected,
            expected_anchor_identity=anchor_identity,
            final_validator=final_validator,
        )
    except (AnchoredWriteError, OSError) as exc:
        raise BacklinkError(f"backlink apply failed: {exc}") from exc


def _validate_plan_corpus_and_manifest(plan: BacklinkReport) -> None:
    current_paths = set(discover_markdown_pages(plan.content_roots))
    planned_paths = set(plan.page_sha256)
    if current_paths != planned_paths:
        raise BacklinkPlanStaleError(
            "backlink corpus membership changed during apply; refusing success"
        )
    active_manifests = _active_manifest_paths(plan.content_roots)
    if active_manifests:
        raise BacklinkError(
            "manifest appeared during backlink apply; refusing writes: "
            + ", ".join(str(path) for path in active_manifests)
        )


def _path_sort_key(path: Path) -> str:
    return path.as_posix().casefold()


def _is_excluded_directory(name: str) -> bool:
    normalised = name.casefold().strip("._-").replace("_", "-")
    if normalised in _EXCLUDED_DIRECTORY_NAMES:
        return True
    return normalised.startswith(("backup-", "backups-", "generated-"))


def _path_has_excluded_directory(path: Path, *, include_leaf: bool) -> bool:
    parts = path.parts if include_leaf else path.parts[:-1]
    return any(_is_excluded_directory(part) for part in parts)


def _common_content_base(roots: tuple[Path, ...]) -> Path | None:
    directory_roots = tuple(root if root.is_dir() else root.parent for root in roots)
    if not directory_roots:
        return None
    if len(directory_roots) == 1:
        return directory_roots[0]
    try:
        return Path(os.path.commonpath(directory_roots))
    except ValueError:
        return None


def _active_manifest_paths(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    candidates = _manifest_candidate_paths(roots)
    configured = os.environ.get(MANIFEST_ENV, "").strip()
    configured_path = Path(configured).expanduser().resolve() if configured else None
    return tuple(
        path for path in candidates if path.is_file() or path == configured_path
    )


def _manifest_candidate_paths(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    candidate_bases: set[Path] = set()
    for root in roots:
        base = root if root.is_dir() else root.parent
        candidate_bases.update((base, *base.parents))
    candidates: set[Path] = {
        candidate
        for base in candidate_bases
        for candidate in (base / "MANIFEST.jsonl", base / "concepts" / "MANIFEST.jsonl")
    }
    configured = os.environ.get(MANIFEST_ENV, "").strip()
    configured_path = Path(configured).expanduser().resolve() if configured else None
    if configured_path is not None:
        candidates.add(configured_path)
    return tuple(sorted(candidates, key=_path_sort_key))


def _aliases_for_page(
    path: Path, *, roots: tuple[Path, ...], common_base: Path | None
) -> tuple[tuple[str, str], ...]:
    rendered: set[str] = {path.stem}
    for root in roots:
        base = root if root.is_dir() else root.parent
        try:
            relative = path.relative_to(base).with_suffix("")
        except ValueError:
            continue
        rendered.add(relative.as_posix())
        if root.is_dir():
            rendered.add((Path(root.name) / relative).as_posix())
    if common_base is not None:
        try:
            rendered.add(path.relative_to(common_base).with_suffix("").as_posix())
        except ValueError:
            pass
    rendered.add(path.with_suffix("").as_posix())

    aliases: dict[str, str] = {}
    for value in sorted(
        rendered, key=lambda item: (item.count("/"), len(item), item.casefold())
    ):
        normalised = _normalise_alias(value)
        if normalised:
            aliases.setdefault(normalised, value)
    return tuple(aliases.items())


def _build_alias_index(pages: tuple[_Page, ...]) -> dict[str, tuple[Path, ...]]:
    candidates: dict[str, set[Path]] = {}
    for page in pages:
        for normalised, _rendered in page.aliases:
            candidates.setdefault(normalised, set()).add(page.path)
    return {
        alias: tuple(sorted(paths, key=_path_sort_key))
        for alias, paths in candidates.items()
    }


def _canonical_target(page: _Page, alias_index: Mapping[str, tuple[Path, ...]]) -> str:
    unique = [
        (normalised, rendered)
        for normalised, rendered in page.aliases
        if alias_index.get(normalised) == (page.path,)
    ]
    if not unique:
        raise BacklinkError(f"no unambiguous wikilink alias for {page.path}")
    _normalised, rendered = min(
        unique,
        key=lambda item: (item[1].count("/"), len(item[1]), item[1].casefold()),
    )
    return rendered


def _normalise_alias(value: str) -> str:
    value = unquote(value).strip().replace("\\", "/")
    value = re.sub(r"(?i)\.md$", "", value).strip("/")
    segments: list[str] = []
    for raw_segment in value.split("/"):
        segment = unicodedata.normalize("NFKC", raw_segment).casefold().strip()
        if segment in {"", "."}:
            continue
        if segment == "..":
            if segments:
                segments.pop()
            continue
        segment = re.sub(r"[\s_]+", "-", segment)
        segment = re.sub(r"[^\w-]+", "-", segment, flags=re.UNICODE)
        segment = re.sub(r"-+", "-", segment).strip("-")
        if segment:
            segments.append(segment)
    return "/".join(segments)


def _marker_spans(text: str, *, path: Path) -> tuple[tuple[int, int], ...]:
    fenced = _fenced_code_spans(text)
    events = sorted(
        [
            (match.start(), match.end(), "begin")
            for match in _BEGIN_RE.finditer(text)
            if not _position_in_spans(match.start(), fenced)
        ]
        + [
            (match.start(), match.end(), "end")
            for match in _END_RE.finditer(text)
            if not _position_in_spans(match.start(), fenced)
        ]
    )
    spans: list[tuple[int, int]] = []
    open_start: int | None = None
    for start, end, kind in events:
        if kind == "begin":
            if open_start is not None:
                raise BacklinkFormatError(f"nested backlink markers in {path}")
            open_start = start
            continue
        if open_start is None:
            raise BacklinkFormatError(
                f"BACKLINKS_END without BACKLINKS_BEGIN in {path}"
            )
        spans.append((open_start, end))
        open_start = None
    if open_start is not None:
        raise BacklinkFormatError(f"BACKLINKS_BEGIN without BACKLINKS_END in {path}")
    return tuple(spans)


def _strict_manual_backlink_spans(
    text: str, *, marker_spans: tuple[tuple[int, int], ...]
) -> tuple[tuple[int, int], ...]:
    fenced = _fenced_code_spans(text)
    headings = [
        match
        for match in _H2_RE.finditer(text)
        if not _position_in_spans(match.start(), fenced)
    ]
    backlink_headings = {
        match.start(): match
        for match in _BACKLINK_HEADING_RE.finditer(text)
        if not _position_in_spans(match.start(), fenced)
    }
    spans: list[tuple[int, int]] = []
    for index, heading in enumerate(headings):
        backlink_heading = backlink_headings.get(heading.start())
        if backlink_heading is None:
            continue
        section_end = (
            headings[index + 1].start() if index + 1 < len(headings) else len(text)
        )
        if any(
            heading.start() <= marker_start < section_end
            for marker_start, _marker_end in marker_spans
        ):
            continue
        body = text[backlink_heading.end() : section_end]
        content_lines = [line for line in body.splitlines() if line.strip()]
        if all(_STRICT_BACKLINK_BULLET_RE.fullmatch(line) for line in content_lines):
            spans.append((heading.start(), section_end))
    return tuple(spans)


def _backlink_projection_spans(text: str, *, path: Path) -> tuple[tuple[int, int], ...]:
    marker_spans = _marker_spans(text, path=path)
    expanded_markers: list[tuple[int, int]] = []
    for start, end in marker_spans:
        preceding_heading = _PRECEDING_BACKLINK_HEADING_RE.search(text[:start])
        expanded_markers.append(
            (preceding_heading.start() if preceding_heading else start, end)
        )
    manual_spans = _strict_manual_backlink_spans(text, marker_spans=marker_spans)
    return tuple(sorted((*expanded_markers, *manual_spans)))


def _without_backlink_projections(text: str, *, path: Path) -> str:
    spans = _backlink_projection_spans(text, path=path)
    if not spans:
        return text
    chunks: list[str] = []
    cursor = 0
    for start, end in spans:
        chunks.extend((text[cursor:start], " " * (end - start)))
        cursor = end
    chunks.append(text[cursor:])
    return "".join(chunks)


def _resolve_wikilink(
    raw_target: str,
    *,
    source: Path,
    alias_index: Mapping[str, tuple[Path, ...]],
    pages_by_path: Mapping[Path, _Page],
) -> Path | None:
    target = unquote(raw_target).strip().replace("\\", "/")
    target_without_suffix = re.sub(r"(?i)\.md$", "", target)
    if target.startswith(("./", "../")) or target.startswith("/"):
        candidate = Path(target_without_suffix)
        if not candidate.is_absolute():
            candidate = source.parent / candidate
        resolved = candidate.with_suffix(".md").resolve()
        if resolved in pages_by_path:
            return resolved

    normalised = _normalise_alias(target)
    candidates = alias_index.get(normalised, ())
    return candidates[0] if len(candidates) == 1 else None


def _compare_existing_block(
    page: _Page,
    *,
    expected: tuple[Path, ...],
    alias_index: Mapping[str, tuple[Path, ...]],
    pages_by_path: Mapping[Path, _Page],
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    expected_set = set(expected)
    valid: set[Path] = set()
    false: list[str] = []
    for start, end in _backlink_projection_spans(page.text, path=page.path):
        for raw_target in _extract_wikilink_targets(page.text[start:end]):
            resolved = _resolve_wikilink(
                raw_target,
                source=page.path,
                alias_index=alias_index,
                pages_by_path=pages_by_path,
            )
            if resolved is None or resolved not in expected_set or resolved in valid:
                false.append(raw_target)
                continue
            valid.add(resolved)
    missing = tuple(sorted(expected_set - valid, key=_path_sort_key))
    return missing, tuple(false)


def _render_backlink_section(
    expected: tuple[Path, ...], *, canonical_targets: Mapping[Path, str]
) -> str:
    links = sorted(
        (canonical_targets[source] for source in expected),
        key=lambda value: (value.casefold(), value),
    )
    lines = [
        "## Backlinks",
        "",
        BACKLINKS_BEGIN,
        *(f"- [[{link}]]" for link in links),
        BACKLINKS_END,
    ]
    return "\n".join(lines) + "\n"


def _updated_page_text(
    text: str,
    *,
    expected: tuple[Path, ...],
    canonical_targets: Mapping[Path, str],
    path: Path,
) -> str:
    spans = _backlink_projection_spans(text, path=path)
    if not spans:
        if not expected:
            return text
        separator = (
            ""
            if not text or text.endswith("\n\n")
            else "\n"
            if text.endswith("\n")
            else "\n\n"
        )
        return (
            text
            + separator
            + _render_backlink_section(expected, canonical_targets=canonical_targets)
        )

    replacement = (
        _render_backlink_section(expected, canonical_targets=canonical_targets)
        if expected
        else ""
    )
    chunks: list[str] = []
    cursor = 0
    for index, (start, end) in enumerate(spans):
        chunks.append(text[cursor:start])
        if index == 0:
            chunks.append(replacement)
        cursor = end
    chunks.append(text[cursor:])
    return "".join(chunks)


def _assert_safe_apply_path(path: Path, roots: tuple[Path, ...]) -> None:
    if path.is_symlink() or _path_has_excluded_directory(path, include_leaf=False):
        raise BacklinkError(f"refusing to write excluded or symlinked page {path}")
    resolved = path.resolve()
    for root in roots:
        if root.is_file():
            if resolved == root.resolve():
                return
            continue
        base = root
        try:
            relative = resolved.relative_to(base)
        except ValueError:
            continue
        if not any(_is_excluded_directory(part) for part in relative.parts[:-1]):
            return
    raise BacklinkError(
        f"refusing to write page outside configured content roots: {path}"
    )
