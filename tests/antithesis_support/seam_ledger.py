"""Seam ledger generator — DharmaGraph Antithesis v0, Phase A (evidence only).

Enumerates every ambient-effect site statically reachable from the bounded
replay workload (a ``CompiledGraph.invoke`` run with checkpointing on plus a
``DurableInvoker``-wrapped dispatch) and classifies each site ``mediated``
(flows through ``EffectsProvider`` — ``dharma_swarm/graph/effects.py``) or
``bypass`` (direct time / RNG / ordering / filesystem / sqlite / env call).

Reach model: the STATIC runtime-import closure of ``dharma_swarm.graph``
(the workload's front door — importing any submodule executes the package
``__init__``), restricted to the ``dharma_swarm`` namespace, including
function-local imports, excluding ``TYPE_CHECKING``-guarded ones. Static
closure over-approximates dynamic reach; it never under-reports. Imports
leaving the namespace are recorded per module in ``external_imports`` —
their internals are not scanned, but every first-party call INTO them
(``aiosqlite.connect`` ...) is an effect site.

Determinism contract: output is a pure function of the checked-out tree —
sorted walk, sorted entries, sorted JSON keys, no wall-clock anywhere; two
runs on the same tree are byte-identical (Phase A exit gate).
Spec: docs/prompts/DHARMAGRAPH_ANTITHESIS_V0_GOAL_2026-07-18.md §Phase A.
Ratchet law: ``summary.bypass_total`` only ratchets down
(tests/test_graph_seam_ledger.py pins the baseline).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

SCHEMA_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parents[2]
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

FIRST_PARTY_PREFIX = "dharma_swarm"

# Effect-name receivers that mark a call as EffectsProvider-mediated.
_MEDIATED_RECEIVERS = {"effects", "_effects", "active_effects"}
_MEDIATED_METHODS = {"now", "random", "dispatch_order", "now()", "random()", "dispatch_order()"}

# Full dotted-chain suffix -> category. Matched against the END of the
# rendered attribute chain (nested calls render as ``name()``).
_CHAIN_SUFFIXES: dict[str, str] = {
    **dict.fromkeys(
        (
            "datetime.now", "datetime.utcnow", "date.today", "time.time",
            "time.time_ns", "time.monotonic", "time.monotonic_ns",
            "time.perf_counter", "time.sleep", "asyncio.sleep",
            "asyncio.timeout",
        ),
        "time",
    ),
    **dict.fromkeys(
        (
            "asyncio.wait", "asyncio.wait_for", "asyncio.gather",
            "asyncio.as_completed", "asyncio.to_thread",
        ),
        "ordering",
    ),
    **dict.fromkeys(
        (
            "random.random", "random.shuffle", "random.choice",
            "random.randint", "random.getrandbits", "random.Random",
            "random.SystemRandom", "uuid.uuid1", "uuid.uuid4", "os.urandom",
            "secrets.token_bytes", "secrets.token_hex", "secrets.SystemRandom",
        ),
        "rng",
    ),
    **dict.fromkeys(("os.environ", "os.getenv", "Path.home"), "env"),
    **dict.fromkeys(("os.getpid", "os.getppid"), "process"),
    **dict.fromkeys(
        (
            "os.fdopen", "os.replace", "os.fsync", "os.unlink", "os.makedirs",
            "tempfile.mkstemp", "tempfile.mkdtemp",
            "tempfile.NamedTemporaryFile", "fcntl.flock", "fcntl.lockf",
            "shutil.rmtree",
        ),
        "filesystem",
    ),
    **dict.fromkeys(("sqlite3.connect", "aiosqlite.connect"), "sqlite"),
}

# Attribute-method names (any receiver) that touch the filesystem or the
# host environment. Kept unambiguous on purpose: names shared with str /
# datetime / dict methods (``replace``, ``rename``) are matched only via
# their full ``os.``-prefixed chain above.
_ATTR_METHODS: dict[str, str] = {
    **dict.fromkeys(
        (
            "read_text", "write_text", "read_bytes", "write_bytes", "mkdir",
            "rmdir", "unlink", "open", "touch", "exists", "stat", "glob",
            "iterdir", "is_file", "is_dir",
        ),
        "filesystem",
    ),
    "expanduser": "env",
}

# Bare-name references (``from uuid import uuid4`` then ``uuid4`` /
# ``default_factory=uuid4``). Matched on Name nodes in Load context.
_BARE_NAMES: dict[str, str] = {
    **dict.fromkeys(("uuid1", "uuid4", "urandom"), "rng"),
    **dict.fromkeys(("mkstemp", "flock"), "filesystem"),
}

# ``open(...)`` builtin — matched only as the func of a Call.
_CALL_ONLY_NAMES: dict[str, str] = {"open": "filesystem"}

# Third-party / stdlib modules whose import marks a module as touching an
# effectful boundary (recorded, not scanned).
_EFFECTFUL_EXTERNALS = {
    "aiosqlite",
    "sqlite3",
    "fcntl",
    "tempfile",
    "socket",
    "shutil",
    "subprocess",
    "requests",
    "httpx",
    "aiohttp",
    "aiofiles",
}

_SEAM_MODULE = "dharma_swarm/graph/effects.py"


def _module_to_path(module: str) -> Path | None:
    """Resolve a dotted dharma_swarm module name to a repo file, or None."""
    rel = Path(*module.split("."))
    candidate = REPO_ROOT / rel.with_suffix(".py")
    if candidate.is_file():
        return candidate
    package_init = REPO_ROOT / rel / "__init__.py"
    if package_init.is_file():
        return package_init
    return None


class _ImportCollector(ast.NodeVisitor):
    """Collect runtime imports (function-local included, TYPE_CHECKING excluded)."""

    def __init__(self, module: str) -> None:
        self._module = module
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
            base = parts[: len(parts) - node.level]
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
    collector = _ImportCollector(module)
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
        if module in seen or not module.startswith(FIRST_PARTY_PREFIX):
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
        if not name.startswith(FIRST_PARTY_PREFIX)
    }
    return sorted(tops)


def _chain(node: ast.expr) -> list[str] | None:
    """Render an attribute chain; nested calls become ``name()`` components."""
    parts: list[str] = []
    current: ast.expr = node
    while True:
        if isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        elif isinstance(current, ast.Call):
            inner = _chain(current.func)
            if inner is None:
                return None
            parts.extend([inner[-1] + "()"] + inner[:-1][::-1])
            break
        elif isinstance(current, ast.Name):
            parts.append(current.id)
            break
        else:
            return None
    return parts[::-1]


def _is_mediated(parts: list[str]) -> bool:
    for i in range(len(parts) - 1):
        receiver = parts[i].removesuffix("()")
        method = parts[i + 1]
        if receiver in _MEDIATED_RECEIVERS and method in _MEDIATED_METHODS:
            return True
    return False


class _EffectScanner(ast.NodeVisitor):
    """Find effect sites; skip annotations; track function enclosure."""

    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        self.sites: list[dict[str, object]] = []
        self._fn_depth = 0

    # -- context management -------------------------------------------------
    def _visit_function(self, node: ast.AST) -> None:
        self._fn_depth += 1
        self.generic_visit(node)
        self._fn_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        self._scan_defaults(node.args)
        self._visit_body(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        self._scan_defaults(node.args)
        self._visit_body(node)

    def _scan_defaults(self, args: ast.arguments) -> None:
        for default in list(args.defaults) + [
            d for d in args.kw_defaults if d is not None
        ]:
            self.visit(default)

    def _visit_body(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._fn_depth += 1
        for stmt in node.body:
            self.visit(stmt)
        self._fn_depth -= 1

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._visit_function(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        # Annotation skipped; value still scanned (dataclass field defaults).
        if node.value is not None:
            self.visit(node.value)

    def visit_arg(self, node: ast.arg) -> None:
        return  # annotation-only node

    # -- matching -----------------------------------------------------------
    def _record(
        self,
        node: ast.expr,
        symbol: str,
        category: str,
        classification: str,
    ) -> None:
        self.sites.append(
            {
                "file": self.rel_path,
                "line": node.lineno,
                "col": node.col_offset,
                "symbol": symbol,
                "category": category,
                "classification": classification,
                "scope": "runtime" if self._fn_depth else "module",
            }
        )

    def _classify_and_record(
        self, node: ast.expr, symbol: str, category: str, mediated: bool
    ) -> None:
        if mediated:
            classification = "mediated"
        elif self.rel_path == _SEAM_MODULE:
            # The provider implementation IS the seam: its primitives are
            # what mediation routes through, not bypasses of it.
            classification = "mediated"
        else:
            classification = "bypass"
        self._record(node, symbol, category, classification)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        parts = _chain(node)
        if parts is not None:
            dotted = ".".join(parts)
            if _is_mediated(parts):
                method = parts[-1].removesuffix("()")
                category = "time" if method == "now" else (
                    "rng" if method in {"random", "getrandbits"} else "ordering"
                )
                self._record(node, dotted, category, "mediated")
                return
            matched = False
            for suffix, category in _CHAIN_SUFFIXES.items():
                if dotted == suffix or dotted.endswith("." + suffix):
                    self._classify_and_record(node, suffix, category, False)
                    matched = True
                    break
            if not matched and parts[-1] in _ATTR_METHODS and len(parts) > 1:
                self._classify_and_record(
                    node, f"*.{parts[-1]}", _ATTR_METHODS[parts[-1]], False
                )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id in _BARE_NAMES:
            self._classify_and_record(
                node, node.id, _BARE_NAMES[node.id], False
            )

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in _CALL_ONLY_NAMES
        ):
            self._classify_and_record(
                node.func,
                node.func.id,
                _CALL_ONLY_NAMES[node.func.id],
                False,
            )
        self.generic_visit(node)


def scan_module(rel_path: str) -> list[dict[str, object]]:
    tree = ast.parse((REPO_ROOT / rel_path).read_text(encoding="utf-8"))
    scanner = _EffectScanner(rel_path)
    scanner.visit(tree)
    return scanner.sites


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
        rel = path.relative_to(REPO_ROOT).as_posix()
        externals = _external_imports(module, path)
        modules.append(
            {
                "module": module,
                "file": rel,
                "custody": _custody(rel),
                "external_imports": externals,
                "effectful_external_imports": sorted(
                    set(externals) & _EFFECTFUL_EXTERNALS
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
                "static runtime-import closure restricted to the "
                "dharma_swarm namespace; function-local imports included; "
                "TYPE_CHECKING-guarded imports excluded; external packages "
                "recorded but not scanned"
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
