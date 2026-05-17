"""Metadata-only file snapshot MemoryKernel adapters."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from dharma_swarm.memory_kernel.adapters.read_only import (
    BaseReadOnlyAdapter,
    _after_cursor,
    _file_snapshot_digest,
    _format_mtime,
    _ordered_atoms,
    _ordered_paths,
)
from dharma_swarm.memory_kernel.atoms import (
    MemoryAtom,
    MemoryAtomType,
    MemoryQuery,
    ReadMode,
    stable_digest,
)


class FileSnapshotMetadataAdapter(BaseReadOnlyAdapter):
    adapter_name = "file_snapshot_metadata_adapter"
    read_mode = ReadMode.METADATA_ONLY
    atom_type = MemoryAtomType.METADATA
    include_suffixes: tuple[str, ...] = ()

    def iter_atoms(
        self,
        *,
        query: MemoryQuery | None = None,
        limit: int | None = None,
    ) -> Iterable[MemoryAtom]:
        resolved_query = self._query(query, limit)
        surface_limit = self._surface_limit(resolved_query)
        if (
            surface_limit <= 0
            or not self.path.exists()
            or not resolved_query.allows_atom_type(MemoryAtomType.METADATA)
        ):
            return
        files = tuple(
            _ordered_paths(
                _metadata_files(
                    self.path,
                    self.config.max_files,
                    include_suffixes=self.include_suffixes,
                ),
                resolved_query.order_by,
            )
        )
        atoms: list[MemoryAtom] = []
        if not files:
            atoms.append(
                self._atom(
                    MemoryAtomType.METADATA,
                    query=resolved_query,
                    content_ref=f"{self.surface_id}:surface_snapshot",
                    content=None,
                    timestamp=self.surface.health.last_modified,
                    source_path=self.path.as_posix(),
                    metadata={
                        "metadata_only": True,
                        "reason": "surface exists but no bounded files matched",
                        "path_type": self.surface.health.path_type,
                        "size_bytes": self.surface.health.size_bytes,
                    },
                    source_digest=_file_snapshot_digest(self.path),
                    source_row_key=f"{self.surface_id}:surface_snapshot",
                    source_last_modified=self.surface.health.last_modified,
                )
            )
        for file_path in files:
            try:
                stat = file_path.stat()
            except OSError as exc:
                atoms.append(
                    self._atom(
                        MemoryAtomType.METADATA,
                        query=resolved_query,
                        content_ref=f"{file_path.as_posix()}:stat_error",
                        content=None,
                        source_path=file_path.as_posix(),
                        metadata={
                            "metadata_only": True,
                            "read_error": str(exc),
                        },
                        source_digest=stable_digest(
                            {
                                "path": file_path.as_posix(),
                                "stat_error": str(exc),
                            }
                        ),
                        source_row_key=f"{file_path.as_posix()}:stat_error",
                    )
                )
                continue
            atoms.append(
                self._atom(
                    MemoryAtomType.METADATA,
                    query=resolved_query,
                    content_ref=file_path.as_posix(),
                    content=None,
                    timestamp=_format_mtime(stat.st_mtime),
                    source_path=file_path.as_posix(),
                    metadata={
                        "metadata_only": True,
                        "reason": "file-level metadata only; payload not ingested",
                        "file_name": file_path.name,
                        "suffix": file_path.suffix,
                        "size_bytes": stat.st_size,
                    },
                    source_digest=_file_snapshot_digest(file_path, stat=stat),
                    source_row_key=file_path.as_posix(),
                    source_last_modified=_format_mtime(stat.st_mtime),
                )
            )
        for atom in _after_cursor(_ordered_atoms(atoms, resolved_query.order_by), resolved_query.cursor)[
            :surface_limit
        ]:
            yield atom


class ArtifactsMetadataAdapter(FileSnapshotMetadataAdapter):
    adapter_name = "artifacts_metadata_adapter"


def _metadata_files(
    path: Path,
    max_files: int,
    *,
    include_suffixes: tuple[str, ...] = (),
) -> tuple[Path, ...]:
    suffixes = {suffix.lower() for suffix in include_suffixes}
    if path.is_file():
        if not suffixes or path.suffix.lower() in suffixes:
            return (path,)
        return ()
    if not path.is_dir():
        return ()
    files: list[Path] = []
    for current, dirs, filenames in os.walk(path):
        dirs[:] = sorted(
            name for name in dirs if name not in {".git", "__pycache__", ".pytest_cache"}
        )
        for filename in sorted(filenames):
            file_path = Path(current) / filename
            if suffixes and file_path.suffix.lower() not in suffixes:
                continue
            files.append(file_path)
            if len(files) >= max_files:
                return tuple(files)
    return tuple(files)
