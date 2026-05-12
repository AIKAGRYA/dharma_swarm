"""Read-only census runner for MemoryKernel M0."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

from dharma_swarm.memory_kernel.atoms import (
    AdapterMode,
    AuthorityLevel,
    MemorySurface,
    MemorySurfaceHealth,
    MemorySurfaceRole,
    MigrationStatus,
    RiskLevel,
    SurfaceCategory,
    SurfaceStatus,
    WriteMode,
)
from dharma_swarm.memory_kernel.surfaces import SurfaceSpec, default_surface_specs


_SQLITE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
_JSONL_SUFFIX = ".jsonl"
_SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "_versions",
    "dist",
    "build",
}
_DISCOVERY_SKIP_DIR_NAMES = _SKIP_DIR_NAMES | {
    "conversation_log",
    "extracts",
    "frontier_council",
    "lancedb",
    "terminal_tui",
    "worktree_vault",
}


@dataclass(frozen=True)
class CensusConfig:
    repo_root: Path = Path(".")
    home: Path = Path.home()
    specs: tuple[SurfaceSpec, ...] = ()
    include_discovered: bool = False
    probe_sqlite_counts: bool = False
    max_discovered: int = 256
    max_discovery_entries: int = 4096
    max_dir_entries: int = 2048
    max_dir_depth: int = 2
    allow_memory_surface_output: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "repo_root", Path(self.repo_root))
        object.__setattr__(self, "home", Path(self.home))

    def surface_specs(self) -> tuple[SurfaceSpec, ...]:
        return self.specs or default_surface_specs()


@dataclass(frozen=True)
class CensusResult:
    surfaces: tuple[MemorySurface, ...]
    discovery_stats: dict[str, Any]


class MemorySurfaceCensus:
    """Classify known and bounded-discovered memory surfaces."""

    def __init__(self, config: CensusConfig | None = None) -> None:
        self.config = config or CensusConfig()
        self._discovery_stats: dict[str, Any] = _empty_discovery_stats()
        self._last_result: CensusResult | None = None

    def run(self) -> tuple[MemorySurface, ...]:
        return self.run_result().surfaces

    def run_result(self) -> CensusResult:
        self._discovery_stats = _empty_discovery_stats()
        surfaces = [self._surface_from_spec(spec) for spec in self.config.surface_specs()]
        if self.config.include_discovered:
            self._initialize_discovery_roots()
            known_paths = {surface.path for surface in surfaces}
            surfaces.extend(self._discover_surfaces(known_paths))
        result = CensusResult(
            surfaces=tuple(sorted(surfaces, key=lambda surface: surface.surface_id)),
            discovery_stats=_copy_discovery_stats(self._discovery_stats),
        )
        self._last_result = result
        return result

    def summarize_surface_health(
        self,
        surfaces: tuple[MemorySurface, ...] | CensusResult | None = None,
    ) -> dict[str, Any]:
        if isinstance(surfaces, CensusResult):
            return self._summarize_surface_health(surfaces.surfaces, surfaces.discovery_stats)
        if surfaces is None:
            result = self.run_result()
            return self._summarize_surface_health(result.surfaces, result.discovery_stats)
        return self._summarize_surface_health(surfaces, self._stats_for_surfaces(surfaces))

    def _summarize_surface_health(
        self,
        rows: tuple[MemorySurface, ...],
        discovery_stats: dict[str, Any],
    ) -> dict[str, Any]:
        by_category: dict[str, int] = {}
        by_authority: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for surface in rows:
            by_category[surface.category.value] = by_category.get(surface.category.value, 0) + 1
            by_authority[surface.authority_level.value] = (
                by_authority.get(surface.authority_level.value, 0) + 1
            )
            by_status[surface.active_status.value] = by_status.get(surface.active_status.value, 0) + 1
        existing = sum(1 for surface in rows if surface.health.exists)
        return {
            "surface_count": len(rows),
            "existing_surface_count": existing,
            "missing_surface_count": len(rows) - existing,
            "by_category": by_category,
            "by_authority": by_authority,
            "by_status": by_status,
            "discovered_count": sum(
                1 for surface in rows if surface.surface_id.startswith("discovered.")
            ),
            "discovery_enabled": self.config.include_discovered,
            "discovery_truncated": bool(discovery_stats["discovery_truncated"]),
            "discovery_entries_visited": discovery_stats["discovery_entries_visited"],
            "discovery_roots_scanned": discovery_stats["discovery_roots_scanned"],
            "discovery_roots_skipped": discovery_stats["discovery_roots_skipped"],
            "discovery_roots_unscanned_due_to_truncation": discovery_stats[
                "discovery_roots_unscanned_due_to_truncation"
            ],
            "discovery_root_status": discovery_stats["discovery_root_status"],
            "discovery_stats_source": discovery_stats["discovery_stats_source"],
        }

    def write_json(
        self,
        output_path: Path,
        surfaces: tuple[MemorySurface, ...] | CensusResult | None = None,
    ) -> None:
        result = self._result_for_optional_surfaces(surfaces)
        self._validate_output_path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": _utc_now(),
            "summary": self._summarize_surface_health(result.surfaces, result.discovery_stats),
            "surfaces": [surface.to_json() for surface in result.surfaces],
        }
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def write_markdown(
        self,
        output_path: Path,
        surfaces: tuple[MemorySurface, ...] | CensusResult | None = None,
    ) -> None:
        result = self._result_for_optional_surfaces(surfaces)
        self._validate_output_path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        summary = self._summarize_surface_health(result.surfaces, result.discovery_stats)
        lines = [
            "# Memory Surface Census v3",
            "",
            f"Generated: `{_utc_now()}`",
            "",
            "This is a read-only MemoryKernel M0 census.  It classifies surfaces; it does not migrate, promote, or delete memory.",
            "",
            "## Summary",
            "",
            f"- Surfaces: `{summary['surface_count']}`",
            f"- Existing: `{summary['existing_surface_count']}`",
            f"- Missing: `{summary['missing_surface_count']}`",
            "",
            "## Discovery",
            "",
            f"- Enabled: `{summary['discovery_enabled']}`",
            f"- Discovered surfaces: `{summary['discovered_count']}`",
            f"- Truncated: `{summary['discovery_truncated']}`",
            f"- Entries visited: `{summary['discovery_entries_visited']}`",
            f"- Stats source: `{summary['discovery_stats_source']}`",
            "",
        ]
        if summary["discovery_truncated"]:
            lines.extend(
                [
                    "**Discovery incomplete: cap reached.**",
                    "",
                ]
            )
        if summary["discovery_root_status"]:
            lines.extend(
                [
                    "| Root | Discovery status |",
                    "|---|---|",
                ]
            )
            for root, status in summary["discovery_root_status"].items():
                lines.append(f"| {_md(root)} | {_md(status)} |")
            lines.append("")
        lines.extend(
            [
            "## Surfaces",
            "",
            "| Surface | Path | Role | Category | Authority | Adapter | Status | Records | Notes |",
            "|---|---|---|---|---|---|---:|---:|---|",
            ]
        )
        for surface in result.surfaces:
            records = "" if surface.health.record_count is None else str(surface.health.record_count)
            notes = "; ".join(surface.health.notes)
            if surface.health.probe_error:
                notes = f"{notes}; probe_error={surface.health.probe_error}" if notes else surface.health.probe_error
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md(surface.surface_id),
                        _md(surface.path),
                        _md(surface.role.value),
                        _md(surface.category.value),
                        _md(surface.authority_level.value),
                        _md(surface.adapter_mode.value),
                        _md(surface.active_status.value),
                        _md(records),
                        _md(notes),
                    ]
                )
                + " |"
            )
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _result_for_optional_surfaces(
        self,
        surfaces: tuple[MemorySurface, ...] | CensusResult | None,
    ) -> CensusResult:
        if isinstance(surfaces, CensusResult):
            return surfaces
        if surfaces is None:
            return self.run_result()
        return CensusResult(surfaces=surfaces, discovery_stats=self._stats_for_surfaces(surfaces))

    def _stats_for_surfaces(self, surfaces: tuple[MemorySurface, ...]) -> dict[str, Any]:
        if self._last_result is not None and surfaces is self._last_result.surfaces:
            return self._last_result.discovery_stats
        stats = _empty_discovery_stats()
        stats["discovery_stats_source"] = "external_surfaces"
        return stats

    def _surface_from_spec(self, spec: SurfaceSpec) -> MemorySurface:
        path = _resolve_template(spec.path_template, self.config.repo_root, self.config.home)
        health = self._probe_path(path, sqlite_count_tables=spec.sqlite_count_tables)
        active_status = spec.active_status
        if not health.exists and spec.active_status == SurfaceStatus.ACTIVE:
            active_status = SurfaceStatus.MISSING
        metadata = dict(spec.metadata)
        if spec.sqlite_count_tables:
            metadata["sqlite_count_tables"] = ",".join(spec.sqlite_count_tables)
        return MemorySurface(
            surface_id=spec.surface_id,
            path=path.as_posix(),
            owner_module=spec.owner_module,
            role=spec.role,
            category=spec.category,
            authority_level=spec.authority_level,
            write_mode=spec.write_mode,
            adapter_mode=spec.adapter_mode,
            active_status=active_status,
            health=health,
            provenance_quality=spec.provenance_quality,
            promotion_path=spec.promotion_path,
            canon_risk=spec.canon_risk,
            pii_secrets_risk=spec.pii_secrets_risk,
            latency_risk=spec.latency_risk,
            known_writers=spec.known_writers,
            known_readers=spec.known_readers,
            feeds=spec.feeds,
            source_of_truth_for=spec.source_of_truth_for,
            projection_of=spec.projection_of,
            migration_status=spec.migration_status,
            do_not_migrate_reason=spec.do_not_migrate_reason,
            metadata=metadata,
        )

    def _probe_path(
        self,
        path: Path,
        *,
        sqlite_count_tables: tuple[str, ...] = (),
    ) -> MemorySurfaceHealth:
        if not path.exists():
            return MemorySurfaceHealth(exists=False)
        try:
            stat = path.stat()
            last_modified = _format_mtime(stat.st_mtime)
            if path.is_file():
                schema, record_count, notes, probe_error = self._probe_file(path, sqlite_count_tables)
                return MemorySurfaceHealth(
                    exists=True,
                    path_type="file",
                    size_bytes=stat.st_size,
                    last_modified=last_modified,
                    record_count=record_count,
                    schema=schema,
                    notes=notes,
                    probe_error=probe_error,
                )
            if path.is_dir():
                size_bytes, notes, truncated = self._bounded_dir_stats(path)
                return MemorySurfaceHealth(
                    exists=True,
                    path_type="directory",
                    size_bytes=size_bytes,
                    last_modified=last_modified,
                    notes=notes,
                    probe_truncated=truncated,
                )
            return MemorySurfaceHealth(
                exists=True,
                path_type="other",
                size_bytes=stat.st_size,
                last_modified=last_modified,
                notes=("non-file non-directory path",),
            )
        except OSError as exc:
            return MemorySurfaceHealth(exists=True, probe_error=str(exc))

    def _probe_file(
        self,
        path: Path,
        sqlite_count_tables: tuple[str, ...],
    ) -> tuple[dict[str, Any], int | None, tuple[str, ...], str | None]:
        if _looks_like_sqlite(path):
            return self._probe_sqlite(path, sqlite_count_tables)
        if path.suffix.lower() == _JSONL_SUFFIX:
            return {}, None, ("jsonl_file",), None
        return {}, None, (), None

    def _probe_sqlite(
        self,
        path: Path,
        sqlite_count_tables: tuple[str, ...],
    ) -> tuple[dict[str, Any], int | None, tuple[str, ...], str | None]:
        notes: list[str] = ["sqlite"]
        if Path(str(path) + "-wal").exists():
            notes.append("immutable_probe_may_ignore_live_wal")
        try:
            with _connect_sqlite_readonly(path) as conn:
                conn.execute("PRAGMA query_only=ON")
                table_rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
                tables = [str(row[0]) for row in table_rows]
                schema: dict[str, Any] = {"tables": tables}
                record_count: int | None = None
                if self.config.probe_sqlite_counts and sqlite_count_tables:
                    table_counts: dict[str, int] = {}
                    for table in sqlite_count_tables:
                        if table not in tables:
                            continue
                        count = conn.execute(
                            f"SELECT COUNT(*) FROM {_quote_identifier(table)}"
                        ).fetchone()[0]
                        table_counts[table] = int(count)
                    if table_counts:
                        schema["table_counts"] = table_counts
                        record_count = sum(table_counts.values())
                return schema, record_count, tuple(notes), None
        except sqlite3.Error as exc:
            return {}, None, ("sqlite",), str(exc)

    def _bounded_dir_stats(self, path: Path) -> tuple[int | None, tuple[str, ...], bool]:
        total_size = 0
        file_count = 0
        dir_count = 0
        truncated = False
        root_depth = len(path.parts)
        try:
            for current, dirs, files in os.walk(path):
                current_path = Path(current)
                depth = len(current_path.parts) - root_depth
                dirs[:] = sorted(name for name in dirs if name not in _SKIP_DIR_NAMES)
                if depth >= self.config.max_dir_depth:
                    dirs[:] = []
                dir_count += len(dirs)
                for filename in sorted(files):
                    if file_count >= self.config.max_dir_entries:
                        truncated = True
                        dirs[:] = []
                        break
                    file_count += 1
                    try:
                        total_size += (current_path / filename).stat().st_size
                    except OSError:
                        truncated = True
                if file_count >= self.config.max_dir_entries:
                    truncated = True
                    break
        except OSError:
            return None, ("dir_probe_error",), True
        notes = (f"sampled_files={file_count}", f"sampled_dirs={dir_count}")
        return total_size, notes, truncated

    def _discover_surfaces(self, known_paths: set[str]) -> list[MemorySurface]:
        discovered: list[MemorySurface] = []
        seen_ids: set[str] = set()
        for path, kind in self._iter_discovery_candidates():
            if len(discovered) >= self.config.max_discovered:
                self._discovery_stats["discovery_truncated"] = True
                self._mark_truncated_from_path(path)
                break
            rendered = path.as_posix()
            if rendered in known_paths:
                continue
            surface_id = _discovered_surface_id(path, self.config.repo_root, self.config.home)
            if surface_id in seen_ids:
                continue
            seen_ids.add(surface_id)
            health = self._probe_path(path)
            role, category, active_status, migration_status, do_not_migrate_reason = (
                _classify_discovered(path, kind, health, self.config.repo_root, self.config.home)
            )
            adapter_mode = AdapterMode.METADATA_ONLY
            feeds = (
                ("snapshot_metadata",)
                if category == SurfaceCategory.REPO_LOCAL
                or migration_status == MigrationStatus.DO_NOT_MIGRATE
                else ("discovered_metadata",)
            )
            discovered.append(
                MemorySurface(
                    surface_id=surface_id,
                    path=rendered,
                    owner_module="discovered",
                    role=role,
                    category=category,
                    authority_level=AuthorityLevel.LOW,
                    write_mode=WriteMode.UNKNOWN,
                    adapter_mode=adapter_mode,
                    active_status=active_status,
                    health=health,
                    provenance_quality="unknown",
                    canon_risk=RiskLevel.HIGH,
                    pii_secrets_risk=RiskLevel.HIGH,
                    latency_risk=RiskLevel.MEDIUM,
                    feeds=feeds,
                    migration_status=migration_status,
                    do_not_migrate_reason=do_not_migrate_reason,
                    metadata={"discovered_kind": kind},
                )
            )
            if len(discovered) >= self.config.max_discovered:
                self._discovery_stats["discovery_truncated"] = True
                self._mark_truncated_from_path(path)
                break
        self._discovery_stats["discovered_count"] = len(discovered)
        return discovered

    def _iter_discovery_candidates(self) -> Iterator[tuple[Path, str]]:
        roots = self._discovery_roots()
        jsonl_dirs: set[Path] = set()
        visited_entries = 0
        for root_index, root in enumerate(roots):
            if not root.exists():
                self._discovery_stats["discovery_roots_skipped"].append(root.as_posix())
                self._discovery_stats["discovery_root_status"][root.as_posix()] = "missing"
                continue
            self._discovery_stats["discovery_roots_scanned"].append(root.as_posix())
            self._discovery_stats["discovery_root_status"][root.as_posix()] = "scanned"
            root_depth = len(root.parts)
            for current, dirs, files in os.walk(root):
                if visited_entries >= self.config.max_discovery_entries:
                    self._discovery_stats["discovery_truncated"] = True
                    self._discovery_stats["discovery_root_status"][root.as_posix()] = (
                        "truncated_inside_root"
                    )
                    self._mark_unscanned_roots(roots[root_index + 1 :])
                    return
                current_path = Path(current)
                depth = len(current_path.parts) - root_depth
                dirs[:] = sorted(name for name in dirs if name not in _DISCOVERY_SKIP_DIR_NAMES)
                if depth >= self.config.max_dir_depth:
                    dirs[:] = []
                for filename in sorted(files):
                    visited_entries += 1
                    self._discovery_stats["discovery_entries_visited"] = visited_entries
                    file_path = current_path / filename
                    suffix = file_path.suffix.lower()
                    if suffix in _SQLITE_SUFFIXES:
                        yield file_path, "sqlite"
                    elif suffix == _JSONL_SUFFIX:
                        if current_path not in jsonl_dirs:
                            jsonl_dirs.add(current_path)
                            yield current_path, "jsonl_dir"
                    if visited_entries >= self.config.max_discovery_entries:
                        self._discovery_stats["discovery_truncated"] = True
                        self._discovery_stats["discovery_root_status"][root.as_posix()] = (
                            "truncated_inside_root"
                        )
                        self._mark_unscanned_roots(roots[root_index + 1 :])
                        return

    def _discovery_roots(self) -> tuple[Path, ...]:
        home = self.config.home.expanduser().resolve(strict=False)
        repo_root = self.config.repo_root.expanduser().resolve(strict=False)
        return (
            home / ".dharma",
            home / ".smriti",
            home / ".codex" / "memories",
            repo_root / ".dharma",
            repo_root / ".swarm",
        )

    def _initialize_discovery_roots(self) -> None:
        for root in self._discovery_roots():
            self._discovery_stats["discovery_root_status"][root.as_posix()] = "pending"

    def _mark_truncated_from_path(self, path: Path) -> None:
        roots = self._discovery_roots()
        resolved = path.resolve()
        for index, root in enumerate(roots):
            root_resolved = root.expanduser().resolve(strict=False)
            if resolved.is_relative_to(root_resolved):
                self._discovery_stats["discovery_root_status"][root.as_posix()] = (
                    "truncated_inside_root"
                )
                self._mark_unscanned_roots(roots[index + 1 :])
                return

    def _mark_unscanned_roots(self, roots: tuple[Path, ...]) -> None:
        unscanned = self._discovery_stats["discovery_roots_unscanned_due_to_truncation"]
        for root in roots:
            rendered = root.as_posix()
            current_status = self._discovery_stats["discovery_root_status"].get(rendered)
            if current_status in {"scanned", "missing", "truncated_inside_root"}:
                continue
            self._discovery_stats["discovery_root_status"][rendered] = "truncated_before_scan"
            if rendered not in unscanned:
                unscanned.append(rendered)

    def _validate_output_path(self, output_path: Path) -> None:
        if self.config.allow_memory_surface_output:
            return
        output_resolved = output_path.expanduser().resolve(strict=False)
        for root in _memory_output_blocklist(self.config.repo_root, self.config.home):
            root_resolved = root.expanduser().resolve(strict=False)
            if output_resolved == root_resolved or output_resolved.is_relative_to(root_resolved):
                raise ValueError(
                    "Refusing to write census output inside memory surface "
                    f"{root_resolved}. Use allow_memory_surface_output only for an intentional override."
                )


def surfaces_to_json(surfaces: tuple[MemorySurface, ...]) -> list[dict[str, Any]]:
    return [surface.to_json() for surface in surfaces]


def _empty_discovery_stats() -> dict[str, Any]:
    return {
        "discovered_count": 0,
        "discovery_truncated": False,
        "discovery_entries_visited": 0,
        "discovery_roots_scanned": [],
        "discovery_roots_skipped": [],
        "discovery_roots_unscanned_due_to_truncation": [],
        "discovery_root_status": {},
        "discovery_stats_source": "latest_run",
    }


def _copy_discovery_stats(stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "discovered_count": stats["discovered_count"],
        "discovery_truncated": stats["discovery_truncated"],
        "discovery_entries_visited": stats["discovery_entries_visited"],
        "discovery_roots_scanned": list(stats["discovery_roots_scanned"]),
        "discovery_roots_skipped": list(stats["discovery_roots_skipped"]),
        "discovery_roots_unscanned_due_to_truncation": list(
            stats["discovery_roots_unscanned_due_to_truncation"]
        ),
        "discovery_root_status": dict(stats["discovery_root_status"]),
        "discovery_stats_source": stats["discovery_stats_source"],
    }


def _resolve_template(template: str, repo_root: Path, home: Path) -> Path:
    rendered = template.format(
        repo_root=repo_root.expanduser().resolve().as_posix(),
        home=home.expanduser().resolve().as_posix(),
    )
    return Path(rendered).expanduser()


def _looks_like_sqlite(path: Path) -> bool:
    return path.suffix.lower() in _SQLITE_SUFFIXES


def _connect_sqlite_readonly(path: Path) -> sqlite3.Connection:
    uri_path = quote(path.resolve().as_posix(), safe="/:")
    return sqlite3.connect(f"file:{uri_path}?mode=ro&immutable=1", uri=True, timeout=1.0)


def _classify_discovered(
    path: Path,
    kind: str,
    health: MemorySurfaceHealth,
    repo_root: Path,
    home: Path,
) -> tuple[MemorySurfaceRole, SurfaceCategory, SurfaceStatus, MigrationStatus, str]:
    if _is_repo_local_surface(path, repo_root):
        return (
            MemorySurfaceRole.REPO_LOCAL_STATE,
            SurfaceCategory.REPO_LOCAL,
            SurfaceStatus.SNAPSHOT if health.exists else SurfaceStatus.MISSING,
            MigrationStatus.DO_NOT_MIGRATE,
            "Discovered repo-local memory state is snapshot/fixture state, not live home memory.",
        )
    if path.resolve().is_relative_to((home / ".smriti").expanduser().resolve(strict=False)) or path.resolve().is_relative_to(
        (home / ".codex" / "memories").expanduser().resolve(strict=False)
    ):
        return (
            MemorySurfaceRole.EXTERNAL_EXOCORTEX,
            SurfaceCategory.EXTERNAL,
            SurfaceStatus.ACTIVE if health.exists else SurfaceStatus.MISSING,
            MigrationStatus.ADAPTER_NEEDED,
            "",
        )
    role = MemorySurfaceRole.PROJECTION_INDEX if kind == "sqlite" else MemorySurfaceRole.RAW_EPISODIC_LOG
    category = SurfaceCategory.PROJECTION if kind == "sqlite" else SurfaceCategory.RAW_EVIDENCE
    return (
        role,
        category,
        SurfaceStatus.ACTIVE if health.exists else SurfaceStatus.MISSING,
        MigrationStatus.ADAPTER_NEEDED,
        "",
    )


def _is_repo_local_surface(path: Path, repo_root: Path) -> bool:
    resolved = path.resolve()
    root = repo_root.expanduser().resolve(strict=False)
    repo_state_roots = (root / ".dharma", root / ".swarm", root / "~" / ".dharma")
    return any(resolved.is_relative_to(state_root.resolve(strict=False)) for state_root in repo_state_roots)


def _memory_output_blocklist(repo_root: Path, home: Path) -> tuple[Path, ...]:
    repo = repo_root.expanduser()
    root_home = home.expanduser()
    return (
        root_home / ".dharma",
        root_home / ".smriti",
        root_home / ".claude",
        root_home / ".codex" / "memories",
        root_home / "Persistent-Semantic-Memory-Vault",
        root_home / "m5-handoff",
        repo / ".dharma",
        repo / ".swarm",
        repo / "~" / ".dharma",
    )


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _format_mtime(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _discovered_surface_id(path: Path, repo_root: Path, home: Path) -> str:
    resolved = path.resolve()
    for prefix, label in ((home.expanduser().resolve(), "home"), (repo_root.expanduser().resolve(), "repo")):
        if resolved.is_relative_to(prefix):
            rel = resolved.relative_to(prefix).as_posix()
            return "discovered." + label + "." + _slug(rel)
    return "discovered." + _slug(resolved.as_posix())


def _slug(value: str) -> str:
    chars = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append(".")
    slug = "".join(chars).strip(".")
    while ".." in slug:
        slug = slug.replace("..", ".")
    return slug[:160] or "surface"
