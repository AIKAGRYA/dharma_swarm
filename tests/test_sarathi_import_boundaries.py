"""Import-graph and compatibility boundaries for canonical Sarathi."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SARATHI_ROOT = REPO_ROOT / "dharma_swarm" / "sarathi"

OLD_SARATHI_EXPORTS = [
    "BootPack",
    "DelegationOutcome",
    "PlannedDelegation",
    "build_operator_brief",
    "build_plan",
    "delegate_all",
    "ProofCycleRecord",
    "ProofVerdict",
    "evaluate_unattended_proof",
    "gateway_snapshot",
    "load_roster",
    "make_wake_work_fn",
    "organ_scoreboard",
    "run_wake_unit",
    "sakshi_audit_brief",
    "sarathi_pulse",
    "sweep_responses",
]

FORBIDDEN_PREFIXES = (
    "api",
    "scripts",
    "fastapi",
    "mcp",
    "nats",
    "subprocess",
    "dharma_swarm.agent_runner",
    "dharma_swarm.autonomous_agent",
    "dharma_swarm.persistent_agent",
    "dharma_swarm.swarm",
    "dharma_swarm.orchestrator",
    "dharma_swarm.mcp_server",
    "dharma_swarm.memory_kernel",
    "dharma_swarm.operator_core.living_agent_kernel",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _matches_prefix(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(f"{prefix}.")


def test_canonical_root_does_not_import_parallel_agent_or_host_runtimes() -> None:
    violations: list[str] = []
    paths = sorted(SARATHI_ROOT.rglob("*.py"))
    assert paths, "canonical Sarathi package is absent"

    for path in paths:
        for module in sorted(_imported_modules(path)):
            if any(_matches_prefix(module, prefix) for prefix in FORBIDDEN_PREFIXES):
                violations.append(f"{path.relative_to(REPO_ROOT)} imports {module}")

    assert violations == []


def test_legacy_holon_sarathi_surface_is_unchanged() -> None:
    import dharma_swarm.holon_system.sarathi as legacy

    before = list(legacy.__all__)
    import dharma_swarm.sarathi as canonical  # noqa: F401

    assert before == OLD_SARATHI_EXPORTS
    assert legacy.__all__ == OLD_SARATHI_EXPORTS
    for export in OLD_SARATHI_EXPORTS:
        assert getattr(legacy, export) is not None


def test_canonical_and_legacy_packages_are_distinct_boundaries() -> None:
    import dharma_swarm.holon_system.sarathi as legacy
    import dharma_swarm.sarathi as canonical

    assert canonical is not legacy
    assert set(canonical.__all__).isdisjoint(
        {"build_plan", "delegate_all", "run_wake_unit"}
    )
