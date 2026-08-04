"""Seam ledger generator — DharmaGraph Antithesis v0, Phase A (evidence only).

Enumerates every ambient-effect site statically reachable from the bounded
replay workload (a ``CompiledGraph.invoke`` run with checkpointing on plus a
``DurableInvoker``-wrapped dispatch) and classifies each site ``mediated``
(flows through ``EffectsProvider`` — ``dharma_swarm/graph/effects.py``) or
``bypass`` (direct time / RNG / ordering / network / filesystem / sqlite /
env call).

Reach model: the STATIC runtime-import closure of ``dharma_swarm.graph``
(the workload's front door — importing any submodule executes the package
``__init__``), restricted to first-party namespaces (``dharma_swarm`` plus
repo-local distributions such as ``telos_kernel``), including function-local
imports, excluding ``TYPE_CHECKING``-guarded ones. Static closure
over-approximates dynamic reach; it never under-reports. Imports leaving
the first-party namespaces are recorded per module in ``external_imports``
— their internals are not scanned, but every first-party call INTO them
(``aiosqlite.connect`` ...) is an effect site.

Determinism contract: output is a pure function of the checked-out tree —
sorted walk, sorted entries, sorted JSON keys, no wall-clock anywhere; two
runs on the same tree are byte-identical (Phase A exit gate).
Spec: docs/prompts/DHARMAGRAPH_ANTITHESIS_V0_GOAL_2026-07-18.md §Phase A.
Ratchet law: ``summary.bypass_total`` only ratchets down
(tests/test_graph_seam_ledger.py pins the baseline exactly).

The AST scanner and its symbol tables live in
``tests/antithesis_support/effect_scan.py`` (module line budget).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

SCHEMA_VERSION = 2
REPO_ROOT = Path(__file__).resolve().parents[2]

try:
    from tests.antithesis_support.effect_scan import (
        EFFECTFUL_EXTERNALS,
        scan_source,
    )
except ImportError:  # direct script invocation: repo root not on sys.path
    sys.path.insert(0, str(REPO_ROOT))
    from tests.antithesis_support.effect_scan import (
        EFFECTFUL_EXTERNALS,
        scan_source,
    )
LEDGER_PATH = (
    REPO_ROOT / "reports" / "governance" / "dharmagraph_parity" / "seam_ledger.json"
)

# The workload's import front door. Importing any dharma_swarm.graph
# submodule executes this package __init__, so the closure starts here.
WORKLOAD_ROOTS = ("dharma_swarm.graph",)
WORKLOAD_DESCRIPTION = (
    "Bounded graph run: GraphBuilder.compile() topology invoked via "
    "CompiledGraph.invoke() with SimulatedEffects, a GraphPersistenceKernel "
    "(checkpointing on), and a DurableInvoker-wrapped dispatch "
    "(derive_graph_side_effect_key). Crosses scheduling (executor superstep "
    "barrier), persistence (journal + checkpoint + idempotency store), and "
    "channel boundaries."
)

# First-party namespaces the closure follows and scans. Repo-local
# distributions are first-party even though their import name is not under
# dharma_swarm (Codex review 2026-07-18: graph/telos_bridge.py reaches
# telos_kernel.check, which is effectful by its own declaration).
FIRST_PARTY_PREFIXES = ("dharma_swarm", "telos_kernel")

# Where dotted module names resolve to files, tried in order.
_MODULE_ROOTS = (
    REPO_ROOT,
    REPO_ROOT / "packages" / "telos-kernel",
)


def _exact_case_file(root: Path, rel: Path) -> Path | None:
    """Return ``root / rel`` only when every path component matches case.

    ``Path.is_file()`` follows the host filesystem's case rules.  On default
    macOS filesystems that made an imported symbol such as
    ``telos_kernel.Manifest`` resolve to the real lowercase ``manifest.py``;
    Linux then generated a different closure.  Walking directory entries by
    their recorded names keeps the ledger a pure function of the tree.
    """
    current = root
    for part in rel.parts:
        try:
            current = next(
                child for child in current.iterdir() if child.name == part
            )
        except (FileNotFoundError, NotADirectoryError, StopIteration):
            return None
    return current if current.is_file() else None


def _module_to_path(module: str) -> Path | None:
    """Resolve a dotted first-party module name to a repo file, or None."""
    rel = Path(*module.split("."))
    for root in _MODULE_ROOTS:
        candidate = _exact_case_file(root, rel.with_suffix(".py"))
        if candidate is not None:
            return candidate
        package_init = _exact_case_file(root, rel / "__init__.py")
        if package_init is not None:
            return package_init
    return None


def _is_first_party(module: str) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".")
        for prefix in FIRST_PARTY_PREFIXES
    )


class _ImportCollector(ast.NodeVisitor):
    """Collect runtime imports (function-local included, TYPE_CHECKING excluded)."""

    def __init__(self, module: str, *, is_package: bool) -> None:
        self._module = module
        self._is_package = is_package
        self.imports: set[str] = set()

    def visit_If(self, node: ast.If) -> None:
        test = node.test
        is_type_checking = (
            isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"
        ) or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        )
        if is_type_checking:
            for stmt in node.orelse:
                self.visit(stmt)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.add(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            parts = self._module.split(".")
            # A package __init__ resolves level-1 relative to ITSELF; a
            # plain module resolves it relative to its parent package
            # (Codex review 2026-07-18: dharma_swarm/engine/__init__.py's
            # ``from .artifacts import ...`` is dharma_swarm.engine.artifacts,
            # not dharma_swarm.artifacts).
            anchor = parts if self._is_package else parts[:-1]
            if node.level - 1 > len(anchor):
                return  # malformed beyond the top-level package
            base = anchor[: len(anchor) - (node.level - 1)]
            prefix = ".".join(base + ([node.module] if node.module else []))
        else:
            prefix = node.module or ""
        if prefix:
            self.imports.add(prefix)
            for alias in node.names:
                # ``from pkg import sub`` may name a submodule; resolving is
                # cheap and a miss is harmless (symbols do not resolve).
                self.imports.add(f"{prefix}.{alias.name}")


def _runtime_imports(module: str, path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    collector = _ImportCollector(module, is_package=path.name == "__init__.py")
    collector.visit(tree)
    return collector.imports


def _ancestor_packages(module: str) -> list[str]:
    parts = module.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts))]


def import_closure(roots: tuple[str, ...] = WORKLOAD_ROOTS) -> dict[str, Path]:
    """First-party runtime-import closure: module name -> file path."""
    resolved: dict[str, Path] = {}
    queue = list(roots)
    seen: set[str] = set()
    while queue:
        module = queue.pop()
        if module in seen or not _is_first_party(module):
            continue
        seen.add(module)
        path = _module_to_path(module)
        if path is None:
            continue  # a symbol, not a module
        resolved[module] = path
        for ancestor in _ancestor_packages(module):
            if ancestor not in seen:
                queue.append(ancestor)
        for imported in _runtime_imports(module, path):
            if imported not in seen:
                queue.append(imported)
    return resolved


def _external_imports(module: str, path: Path) -> list[str]:
    tops = {
        name.split(".")[0]
        for name in _runtime_imports(module, path)
        if not _is_first_party(name)
    }
    return sorted(tops)


def _rel_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def scan_module(rel_path: str) -> list[dict[str, object]]:
    source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    return scan_source(source, rel_path)


def _custody(rel_path: str) -> str:
    if rel_path.startswith("dharma_swarm/graph/"):
        return "dharmagraph-engine-2026-07"
    return "outside_track"


def build_ledger() -> dict[str, object]:
    closure = import_closure()
    modules: list[dict[str, object]] = []
    effects: list[dict[str, object]] = []
    for module in sorted(closure):
        path = closure[module]
        rel = _rel_path(path)
        externals = _external_imports(module, path)
        modules.append(
            {
                "module": module,
                "file": rel,
                "custody": _custody(rel),
                "external_imports": externals,
                "effectful_external_imports": sorted(
                    set(externals) & EFFECTFUL_EXTERNALS
                ),
            }
        )
        effects.extend(scan_module(rel))
    effects.sort(key=lambda e: (e["file"], e["line"], e["col"], e["symbol"]))
    for entry in effects:
        entry["id"] = f"{entry['file']}:{entry['line']}:{entry['col']}"
    bypass = [e for e in effects if e["classification"] == "bypass"]
    by_category: dict[str, int] = {}
    for entry in bypass:
        by_category[str(entry["category"])] = (
            by_category.get(str(entry["category"]), 0) + 1
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": "tests/antithesis_support/seam_ledger.py",
        "spec": "docs/prompts/DHARMAGRAPH_ANTITHESIS_V0_GOAL_2026-07-18.md",
        "workload": {
            "description": WORKLOAD_DESCRIPTION,
            "roots": list(WORKLOAD_ROOTS),
            "reach_model": (
                "static runtime-import closure restricted to first-party "
                "namespaces (dharma_swarm + repo-local distributions); "
                "function-local imports included; TYPE_CHECKING-guarded "
                "imports excluded; external packages recorded but not "
                "scanned; import aliases resolved before matching"
            ),
        },
        "modules": modules,
        "effects": effects,
        "summary": {
            "module_count": len(modules),
            "effect_site_count": len(effects),
            "mediated_total": sum(
                1 for e in effects if e["classification"] == "mediated"
            ),
            "bypass_total": len(bypass),
            "bypass_by_category": by_category,
        },
    }


def render_ledger() -> str:
    return json.dumps(build_ledger(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "--write"
    rendered = render_ledger()
    if mode == "--write":
        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEDGER_PATH.write_text(rendered, encoding="utf-8")
        summary = build_ledger()["summary"]
        print(f"wrote {LEDGER_PATH.relative_to(REPO_ROOT)}: {summary}")
        return 0
    if mode == "--check":
        if not LEDGER_PATH.is_file():
            print("seam_ledger.json missing; run with --write", file=sys.stderr)
            return 1
        committed = LEDGER_PATH.read_text(encoding="utf-8")
        if committed != rendered:
            print(
                "seam_ledger.json is stale: regenerated ledger differs from "
                "the committed one (run --write and commit)",
                file=sys.stderr,
            )
            return 1
        print("seam_ledger.json matches the tree")
        return 0
    if mode == "--print":
        sys.stdout.write(rendered)
        return 0
    print(f"unknown mode {mode!r}; use --write | --check | --print", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main(sys.argv))
