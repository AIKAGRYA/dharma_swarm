"""Static registry for known Dharma memory-like surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field

from dharma_swarm.memory_kernel.atoms import (
    AdapterMode,
    AuthorityLevel,
    MemorySurfaceRole,
    MigrationStatus,
    RiskLevel,
    SurfaceCategory,
    SurfaceStatus,
    WriteMode,
)


@dataclass(frozen=True)
class SurfaceSpec:
    surface_id: str
    path_template: str
    owner_module: str
    role: MemorySurfaceRole
    category: SurfaceCategory
    authority_level: AuthorityLevel
    write_mode: WriteMode
    adapter_mode: AdapterMode
    active_status: SurfaceStatus = SurfaceStatus.ACTIVE
    provenance_quality: str = "unknown"
    promotion_path: str = ""
    canon_risk: RiskLevel = RiskLevel.UNKNOWN
    pii_secrets_risk: RiskLevel = RiskLevel.UNKNOWN
    latency_risk: RiskLevel = RiskLevel.UNKNOWN
    known_writers: tuple[str, ...] = ()
    known_readers: tuple[str, ...] = ()
    feeds: tuple[str, ...] = ()
    source_of_truth_for: tuple[str, ...] = ()
    projection_of: tuple[str, ...] = ()
    migration_status: MigrationStatus = MigrationStatus.REGISTER_ONLY
    do_not_migrate_reason: str = ""
    sqlite_count_tables: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)



def default_surface_specs() -> tuple[SurfaceSpec, ...]:
    """Return the known-surface registry.

    Templates support ``{home}`` and ``{repo_root}``.  The registry is explicit
    on purpose: projections, witness logs, runtime state, and external
    exocortex stores need different authority labels before deeper adapters
    touch them.
    """

    from dharma_swarm.memory_kernel.surface_specs_core import core_surface_specs
    from dharma_swarm.memory_kernel.surface_specs_extended import extended_surface_specs

    return (*core_surface_specs(), *extended_surface_specs())
