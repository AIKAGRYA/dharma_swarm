"""Inventory and ratchet helpers for the routing-fusion spine.

This module is intentionally outside the hot routing path. It answers two
questions for the fusion program:

1. How much of the repository is already adjacent to routing/provider calls?
2. Did any new direct provider-call bypass appear without being acknowledged?

Fusion here means shared routing contracts and witness semantics, not merging
hundreds of files into a single router.
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SOURCE_ROOTS: tuple[str, ...] = ("dharma_swarm", "api", "scripts")

CORE_ROUTING_MODULES: tuple[str, ...] = (
    "dharma_swarm.providers",
    "dharma_swarm.provider_policy",
    "dharma_swarm.telemetry_plane",
    "dharma_swarm.runtime_provider",
    "dharma_swarm.routing_memory",
    "dharma_swarm.decision_router",
    "dharma_swarm.router_v1",
    "dharma_swarm.model_hierarchy",
    "dharma_swarm.agent_runner",
    "dharma_swarm.agent_registry",
    "dharma_swarm.stigmergy",
)

# Current known direct provider-call surfaces. Production entries should be
# ported toward routing_contract/ModelRouter in batches; smoke/probe/demo files
# may remain explicit if they emit probe witness.
DIRECT_PROVIDER_CALL_ALLOWLIST: tuple[str, ...] = (
    "api/routers/chat.py",
    "dharma_swarm/agent_runner.py",
    "dharma_swarm/api_key_audit.py",
    "dharma_swarm/autonomous_agent.py",
    "dharma_swarm/autoresearch_loop.py",
    "dharma_swarm/consolidation.py",
    "dharma_swarm/context_agent.py",
    "dharma_swarm/dgm_loop.py",
    "dharma_swarm/evolution.py",
    "dharma_swarm/inquiry_substrate_chew.py",
    "dharma_swarm/jikoku_instrumentation.py",
    "dharma_swarm/knowledge_extractor.py",
    "dharma_swarm/monitor.py",
    "dharma_swarm/neural_consolidator.py",
    "dharma_swarm/orchestrate_live.py",
    "dharma_swarm/orchestrator.py",
    "dharma_swarm/planner.py",
    "dharma_swarm/provider_matrix.py",
    "dharma_swarm/provider_policy.py",
    "dharma_swarm/provider_smoke.py",
    "dharma_swarm/providers.py",
    "dharma_swarm/providers_extended.py",
    "dharma_swarm/quality_gates.py",
    "dharma_swarm/runtime_provider.py",
    "dharma_swarm/scout_framework.py",
    "dharma_swarm/subconscious_hum.py",
    "dharma_swarm/thinkodynamic_director.py",
    "dharma_swarm/witness.py",
    "dharma_swarm/worker_spawn.py",
    "scripts/demos/demo_jikoku.py",
    "scripts/dgc_max_stress.py",
    "scripts/mimo_explorer.py",
    "scripts/organism_council.py",
    "scripts/organism_live_multimodel.py",
    "scripts/shakti_discovery.py",
    "scripts/system_integration_probe.py",
)

FIRST_BYPASS_SURFACES: tuple[str, ...] = (
    "api/routers/chat.py",
    "dharma_swarm/autonomous_agent.py",
    "dharma_swarm/consolidation.py",
    "dharma_swarm/context_agent.py",
    "dharma_swarm/inquiry_substrate_chew.py",
    "dharma_swarm/neural_consolidator.py",
    "dharma_swarm/provider_matrix.py",
    "dharma_swarm/provider_smoke.py",
    "dharma_swarm/scout_framework.py",
    "dharma_swarm/subconscious_hum.py",
    "dharma_swarm/thinkodynamic_director.py",
    "scripts/system_integration_probe.py",
)

RUST_CANDIDATE_HINTS: tuple[str, ...] = (
    "redaction",
    "error classifier",
    "route scoring",
    "routing memory",
    "jsonl schema validation",
    "circuit breaker",
    "graph aggregation",
)

PROVIDER_MODEL_MARKERS: tuple[str, ...] = (
    "ProviderType",
    "LLMRequest",
    "LLMResponse",
)

DIRECT_PROVIDER_MARKERS: tuple[str, ...] = (
    "create_runtime_provider(",
    "OpenAIProvider(",
    "OllamaProvider(",
    "NVIDIANIMProvider(",
    "AnthropicProvider(",
    "OpenRouterProvider(",
)


@dataclass(frozen=True, slots=True)
class ModuleScan:
    path: str
    module: str
    imports: tuple[str, ...]
    lines: int
    provider_model_contract: bool = False
    direct_provider_call_suspect: bool = False
    core_routing_importer: bool = False


def _is_python_source(path: Path, root: Path) -> bool:
    if path.suffix != ".py":
        return False
    rel_parts = path.relative_to(root).parts
    if not rel_parts or rel_parts[0] not in SOURCE_ROOTS:
        return False
    return ".venv" not in rel_parts and "__pycache__" not in rel_parts


def _module_name(root: Path, path: Path) -> str:
    return ".".join(path.relative_to(root).with_suffix("").parts)


def _safe_parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def _imports_from_tree(tree: ast.AST | None) -> tuple[str, ...]:
    if tree is None:
        return ()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return tuple(sorted(imports))


def _imports_core_routing(imports: Iterable[str]) -> bool:
    return any(
        item == core or item.startswith(f"{core}.")
        for item in imports
        for core in CORE_ROUTING_MODULES
    )


def _direct_provider_call_suspect(text: str) -> bool:
    if any(marker in text for marker in DIRECT_PROVIDER_MARKERS):
        return True
    providerish = "provider" in text.lower() or "Provider(" in text
    return providerish and ".complete(" in text


def scan_modules(root: Path | str) -> list[ModuleScan]:
    repo = Path(root).resolve()
    scans: list[ModuleScan] = []
    for path in sorted(repo.rglob("*.py")):
        if not _is_python_source(path, repo):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        imports = _imports_from_tree(_safe_parse(path))
        rel = path.relative_to(repo).as_posix()
        direct_provider_suspect = (
            False
            if rel == "dharma_swarm/routing_fusion_inventory.py"
            else _direct_provider_call_suspect(text)
        )
        scans.append(
            ModuleScan(
                path=rel,
                module=_module_name(repo, path),
                imports=imports,
                lines=text.count("\n") + 1,
                provider_model_contract=any(
                    marker in text for marker in PROVIDER_MODEL_MARKERS
                ),
                direct_provider_call_suspect=direct_provider_suspect,
                core_routing_importer=_imports_core_routing(imports),
            )
        )
    return scans


def build_inventory(root: Path | str) -> dict[str, Any]:
    repo = Path(root).resolve()
    scans = scan_modules(repo)
    all_py = [
        path
        for path in repo.rglob("*.py")
        if ".venv" not in path.parts and "__pycache__" not in path.parts
    ]
    source_modules = [scan for scan in scans if scan.path.split("/", 1)[0] in SOURCE_ROOTS]
    direct_provider = sorted(
        scan.path for scan in scans if scan.direct_provider_call_suspect
    )
    core_importers = sorted(
        scan.path
        for scan in scans
        if scan.core_routing_importer and scan.module not in CORE_ROUTING_MODULES
    )
    provider_contract = sorted(
        scan.path for scan in scans if scan.provider_model_contract
    )

    return {
        "captured_at": "generated",
        "workspace_scanned": str(repo),
        "counts": {
            "python_files_total_including_tests": len(all_py),
            "source_python_modules": len(source_modules),
            "dharma_swarm_python_modules": sum(
                1 for scan in scans if scan.path.startswith("dharma_swarm/")
            ),
            "tests_python_files": sum(
                1
                for path in all_py
                if path.relative_to(repo).parts
                and path.relative_to(repo).parts[0] == "tests"
            ),
            "core_routing_modules": len(CORE_ROUTING_MODULES),
            "non_core_direct_routing_importers": len(core_importers),
            "provider_model_contract_consumers": len(provider_contract),
            "direct_provider_call_suspects": len(direct_provider),
            "first_bypass_surfaces": len(FIRST_BYPASS_SURFACES),
            "rust_candidate_hints": len(RUST_CANDIDATE_HINTS),
        },
        "core_routing_modules": [
            f"{module.replace('.', '/')}.py" for module in CORE_ROUTING_MODULES
        ],
        "first_bypass_surfaces": list(FIRST_BYPASS_SURFACES),
        "direct_provider_call_suspects": direct_provider,
        "non_core_direct_routing_importers": core_importers,
        "provider_model_contract_consumers": provider_contract,
        "direct_provider_call_allowlist": list(DIRECT_PROVIDER_CALL_ALLOWLIST),
        "rust_candidate_hints": list(RUST_CANDIDATE_HINTS),
        "notes": [
            "Generated by dharma_swarm.routing_fusion_inventory.",
            "Fusion means shared routing contract and witness semantics, not file collapse.",
        ],
    }


def unallowlisted_provider_bypasses(root: Path | str) -> list[str]:
    allowed = set(DIRECT_PROVIDER_CALL_ALLOWLIST)
    found = {
        scan.path
        for scan in scan_modules(root)
        if scan.direct_provider_call_suspect
    }
    return sorted(found - allowed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    inventory = build_inventory(args.root)
    payload = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
