"""Read-only writer sentinel runtime for MemoryKernel."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from dharma_swarm.memory_kernel.surfaces import default_surface_specs
from dharma_swarm.memory_kernel.write_policy import (
    MemoryWritePolicy,
    WriteDecisionOutcome,
    WriteRequest,
    reviewed_write_key,
)
from dharma_swarm.memory_kernel.writer_discovery import (
    _MemoryWriteVisitor,
    _matching_writer_ids,
    _relative_path,
    _skip_scan_path,
    _symbol_exists,
    _triage_discovered_write,
)
from dharma_swarm.memory_kernel.writer_models import (
    DiscoveredMemoryWrite,
    DiscoveredWriteStatus,
    DiscoveryTriageCategory,
    MemoryWriterObservation,
    MemoryWriterSpec,
    WriterDiscoverySummary,
    WriterSentinelSummary,
    WriterStatus,
)
from dharma_swarm.memory_kernel.writer_specs import default_writer_specs


class MemoryWriterSentinel:
    """Inventory registered memory-like write paths."""

    def __init__(
        self,
        *,
        repo_root: Path | str,
        specs: Iterable[MemoryWriterSpec] | None = None,
        known_surface_ids: Iterable[str] | None = None,
        write_policy: MemoryWritePolicy | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.specs = tuple(specs or default_writer_specs())
        self.write_policy = write_policy or MemoryWritePolicy()
        self.known_surface_ids = set(
            known_surface_ids
            if known_surface_ids is not None
            else (surface.surface_id for surface in default_surface_specs())
        )

    def run(self) -> tuple[MemoryWriterObservation, ...]:
        return tuple(self._observe(spec) for spec in self.specs)

    def summarize(self, observations: Iterable[MemoryWriterObservation]) -> WriterSentinelSummary:
        rows = tuple(observations)
        by_classification: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for row in rows:
            by_classification[row.spec.classification.value] = (
                by_classification.get(row.spec.classification.value, 0) + 1
            )
            by_status[row.status.value] = by_status.get(row.status.value, 0) + 1
        return WriterSentinelSummary(
            writer_count=len(rows),
            present_count=sum(1 for row in rows if row.present),
            missing_count=sum(1 for row in rows if row.status == WriterStatus.MISSING),
            unregistered_surface_count=sum(
                len(row.unregistered_surfaces) for row in rows
            ),
            error_count=sum(1 for row in rows if row.status == WriterStatus.ERROR),
            by_classification=by_classification,
            by_status=by_status,
        )

    def discover_write_paths(
        self,
        *,
        scan_roots: Iterable[Path | str] | None = None,
        max_files: int = 2000,
    ) -> tuple[DiscoveredMemoryWrite, ...]:
        files = tuple(self._iter_scan_files(scan_roots=scan_roots, max_files=max_files))
        registered = self._registered_symbol_index()
        specs_by_id = {spec.writer_id: spec for spec in self.specs}
        policy_occurrences: dict[tuple[str, str, str, str], int] = {}
        discovered: list[DiscoveredMemoryWrite] = []
        for source_path in files:
            try:
                tree = ast.parse(source_path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            visitor = _MemoryWriteVisitor(source_path=source_path, repo_root=self.repo_root)
            visitor.visit(tree)
            for candidate in visitor.discovered:
                matches = _matching_writer_ids(candidate, registered)
                status = (
                    DiscoveredWriteStatus.REGISTERED
                    if matches
                    else DiscoveredWriteStatus.UNREGISTERED
                )
                triage_category, triage_reason = _triage_discovered_write(
                    candidate,
                    status=status,
                )
                matched_specs = tuple(
                    specs_by_id[writer_id]
                    for writer_id in matches
                    if writer_id in specs_by_id
                )
                identity = self.write_policy.identity_for_writer_specs(
                    matched_specs,
                    source_path=candidate.source_path,
                    symbol=candidate.symbol,
                )
                request = WriteRequest(
                    source_path=candidate.source_path,
                    symbol=candidate.symbol,
                    operation=candidate.operation,
                    target=candidate.target,
                    mode=candidate.mode,
                    writer_identity=identity,
                )
                policy_key = reviewed_write_key(
                    candidate.source_path,
                    candidate.symbol,
                    candidate.operation,
                    candidate.target,
                )
                occurrence_index = policy_occurrences.get(policy_key, 0) + 1
                policy_occurrences[policy_key] = occurrence_index
                request = replace(request, occurrence_index=occurrence_index)
                write_decision = self.write_policy.decide(request)
                discovered.append(
                    DiscoveredMemoryWrite(
                        source_path=candidate.source_path,
                        symbol=candidate.symbol,
                        line=candidate.line,
                        operation=candidate.operation,
                        target=candidate.target,
                        mode=candidate.mode,
                        reason=candidate.reason,
                        status=status,
                        triage_category=triage_category,
                        triage_reason=triage_reason,
                        matched_writer_ids=matches,
                        write_decision=write_decision.to_json(),
                    )
                )
        return tuple(discovered)

    def summarize_discoveries(
        self,
        discoveries: Iterable[DiscoveredMemoryWrite],
        *,
        scanned_file_count: int | None = None,
        parse_error_count: int = 0,
    ) -> WriterDiscoverySummary:
        rows = tuple(discoveries)
        by_operation: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_triage: dict[str, int] = {}
        by_decision: dict[str, int] = {}
        by_unregistered_source: dict[str, int] = {}
        for row in rows:
            by_operation[row.operation] = by_operation.get(row.operation, 0) + 1
            by_status[row.status.value] = by_status.get(row.status.value, 0) + 1
            by_triage[row.triage_category.value] = by_triage.get(row.triage_category.value, 0) + 1
            decision = _discovery_decision(row)
            if decision:
                by_decision[decision] = by_decision.get(decision, 0) + 1
            if row.status == DiscoveredWriteStatus.UNREGISTERED:
                by_unregistered_source[row.source_path] = (
                    by_unregistered_source.get(row.source_path, 0) + 1
                )
        top_unregistered_sources = tuple(
            {"source_path": source_path, "count": count}
            for source_path, count in sorted(
                by_unregistered_source.items(),
                key=lambda item: (-item[1], item[0]),
            )[:10]
        )
        return WriterDiscoverySummary(
            scanned_file_count=scanned_file_count if scanned_file_count is not None else 0,
            parse_error_count=parse_error_count,
            discovered_write_count=len(rows),
            registered_discovery_count=sum(
                1 for row in rows if row.status == DiscoveredWriteStatus.REGISTERED
            ),
            unregistered_discovery_count=sum(
                1 for row in rows if row.status == DiscoveredWriteStatus.UNREGISTERED
            ),
            action_required_count=sum(
                1
                for row in rows
                if (
                    (
                        row.triage_category
                        in {
                            DiscoveryTriageCategory.MEMORY_WRITER_NEEDS_SPEC,
                            DiscoveryTriageCategory.SURFACE_NEEDS_REGISTRY,
                        }
                        and not _discovery_reviewed(row)
                    )
                    or (
                        _discovery_decision(row) == WriteDecisionOutcome.DENY.value
                        and not _discovery_reviewed(row)
                    )
                )
            ),
            top_unregistered_sources=top_unregistered_sources,
            by_operation=by_operation,
            by_status=by_status,
            by_triage=by_triage,
            by_decision=by_decision,
            policy_denied_count=sum(
                1
                for row in rows
                if _discovery_decision(row) == WriteDecisionOutcome.DENY.value
            ),
            unreviewed_discovery_count=sum(
                1
                for row in rows
                if row.status == DiscoveredWriteStatus.UNREGISTERED
                and _discovery_decision(row) == WriteDecisionOutcome.DENY.value
                and not _discovery_reviewed(row)
            ),
        )

    def _observe(self, spec: MemoryWriterSpec) -> MemoryWriterObservation:
        source_path = self._module_path(spec.owner_module)
        unregistered = tuple(
            surface_id for surface_id in spec.writes_to if surface_id not in self.known_surface_ids
        )
        if source_path is None or not source_path.exists():
            return MemoryWriterObservation(
                spec=spec,
                source_path=str(source_path or ""),
                present=False,
                status=WriterStatus.MISSING,
                unregistered_surfaces=unregistered,
            )
        try:
            present = _symbol_exists(source_path, spec.symbol)
        except (OSError, SyntaxError) as exc:
            return MemoryWriterObservation(
                spec=spec,
                source_path=source_path.as_posix(),
                present=False,
                status=WriterStatus.ERROR,
                unregistered_surfaces=unregistered,
                error=str(exc),
            )
        if not present:
            return MemoryWriterObservation(
                spec=spec,
                source_path=source_path.as_posix(),
                present=False,
                status=WriterStatus.MISSING,
                unregistered_surfaces=unregistered,
            )
        status = WriterStatus.UNREGISTERED_SURFACE if unregistered else WriterStatus.PRESENT
        return MemoryWriterObservation(
            spec=spec,
            source_path=source_path.as_posix(),
            present=True,
            status=status,
            unregistered_surfaces=unregistered,
        )

    def _module_path(self, owner_module: str) -> Path | None:
        if owner_module.endswith(".py") or "/" in owner_module:
            return self.repo_root / owner_module
        return self.repo_root / Path(*owner_module.split(".")).with_suffix(".py")

    def _iter_scan_files(
        self,
        *,
        scan_roots: Iterable[Path | str] | None,
        max_files: int,
    ) -> Iterable[Path]:
        roots = tuple(scan_roots or ("dharma_swarm", "scripts"))
        emitted = 0
        for root in roots:
            root_path = Path(root)
            if not root_path.is_absolute():
                root_path = self.repo_root / root_path
            if root_path.is_file() and root_path.suffix == ".py":
                yield root_path
                emitted += 1
                if emitted >= max_files:
                    return
                continue
            if not root_path.is_dir():
                continue
            for path in sorted(root_path.rglob("*.py")):
                if _skip_scan_path(path):
                    continue
                yield path
                emitted += 1
                if emitted >= max_files:
                    return

    def count_scan_files(
        self,
        *,
        scan_roots: Iterable[Path | str] | None = None,
        max_files: int = 2000,
    ) -> int:
        return sum(1 for _ in self._iter_scan_files(scan_roots=scan_roots, max_files=max_files))

    def count_parse_errors(
        self,
        *,
        scan_roots: Iterable[Path | str] | None = None,
        max_files: int = 2000,
    ) -> int:
        errors = 0
        for path in self._iter_scan_files(scan_roots=scan_roots, max_files=max_files):
            try:
                ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                errors += 1
        return errors

    def _registered_symbol_index(self) -> dict[str, tuple[MemoryWriterSpec, ...]]:
        by_path: dict[str, list[MemoryWriterSpec]] = {}
        for spec in self.specs:
            source_path = self._module_path(spec.owner_module)
            if source_path is None:
                continue
            key = _relative_path(source_path, self.repo_root)
            by_path.setdefault(key, []).append(spec)
        return {path: tuple(specs) for path, specs in by_path.items()}


def _discovery_decision(row: DiscoveredMemoryWrite) -> str:
    if not row.write_decision:
        return ""
    decision = row.write_decision.get("decision")
    return decision if isinstance(decision, str) else ""


def _discovery_reviewed(row: DiscoveredMemoryWrite) -> bool:
    if not row.write_decision:
        return False
    return bool(row.write_decision.get("reviewed_baseline"))
