"""Effect-site scanner for the seam ledger (Antithesis v0, Phase A).

Split out of ``seam_ledger.py`` to respect the 500-line module budget.
Owns the symbol tables and the AST scanner; ``seam_ledger.py`` owns the
closure walk, ledger assembly, and CLI.

Review hardening (2026-07-18 Codex round on PR #1034):
- import aliases are resolved before suffix matching
  (``import time as clock; clock.time()`` is a time bypass);
- ``from M import f as g`` bindings are resolved for bare-name matching;
- network call sites are first-class effect sites (category ``network``),
  not just recorded external imports.
"""

from __future__ import annotations

import ast

# Effect-name receivers that mark a call as EffectsProvider-mediated.
_MEDIATED_RECEIVERS = {"effects", "_effects", "active_effects"}
_MEDIATED_METHODS = {"now", "random", "dispatch_order", "now()", "random()", "dispatch_order()"}

# Full dotted-chain suffix -> category. Matched against the END of the
# alias-resolved attribute chain (nested calls render as ``name()``).
CHAIN_SUFFIXES: dict[str, str] = {
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
    **dict.fromkeys(
        (
            "socket.socket", "socket.create_connection", "socket.getaddrinfo",
            "requests.get", "requests.post", "requests.put", "requests.delete",
            "requests.head", "requests.request", "requests.Session",
            "httpx.get", "httpx.post", "httpx.request", "httpx.stream",
            "httpx.Client", "httpx.AsyncClient",
            "aiohttp.ClientSession", "aiohttp.request",
            "urllib.request.urlopen",
            "websockets.connect",
        ),
        "network",
    ),
}

# Attribute-method names (any receiver) that touch the filesystem or the
# host environment. Kept unambiguous on purpose: names shared with str /
# datetime / dict methods (``replace``, ``rename``) are matched only via
# their full ``os.``-prefixed chain above.
ATTR_METHODS: dict[str, str] = {
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
# ``default_factory=uuid4``). Matched on Name nodes in Load context,
# after from-import alias resolution.
BARE_NAMES: dict[str, str] = {
    **dict.fromkeys(("uuid1", "uuid4", "urandom"), "rng"),
    **dict.fromkeys(("mkstemp", "flock"), "filesystem"),
    **dict.fromkeys(("urlopen", "create_connection", "getaddrinfo"), "network"),
}

# ``open(...)`` builtin — matched only as the func of a Call.
CALL_ONLY_NAMES: dict[str, str] = {"open": "filesystem"}

# Third-party / stdlib modules whose import marks a module as touching an
# effectful boundary (recorded, not scanned).
EFFECTFUL_EXTERNALS = {
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
    "websockets",
    "urllib",
}

SEAM_MODULE = "dharma_swarm/graph/effects.py"


class AliasCollector(ast.NodeVisitor):
    """Record local-name bindings created by imports.

    ``module_aliases``: ``import time as clock`` -> {"clock": "time"} (and
    the identity binding "time" -> "time" so dotted-origin rendering is
    uniform). ``name_origins``: ``from uuid import uuid4 as make_id`` ->
    {"make_id": "uuid.uuid4"}.
    """

    def __init__(self) -> None:
        self.module_aliases: dict[str, str] = {}
        self.name_origins: dict[str, str] = {}

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            bound = alias.asname or alias.name.split(".")[0]
            target = alias.name if alias.asname else alias.name.split(".")[0]
            self.module_aliases[bound] = target

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level or not node.module:
            return  # relative / bare — first-party, handled by the closure
        for alias in node.names:
            bound = alias.asname or alias.name
            self.name_origins[bound] = f"{node.module}.{alias.name}"


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


def _resolve_alias(parts: list[str], module_aliases: dict[str, str]) -> list[str]:
    """Expand the chain's leading module alias to its real dotted origin."""
    head = parts[0].removesuffix("()")
    origin = module_aliases.get(head)
    if origin is None or origin == head:
        return parts
    return origin.split(".") + parts[1:]


def _is_mediated(parts: list[str]) -> bool:
    for i in range(len(parts) - 1):
        receiver = parts[i].removesuffix("()")
        method = parts[i + 1]
        if receiver in _MEDIATED_RECEIVERS and method in _MEDIATED_METHODS:
            return True
    return False


class EffectScanner(ast.NodeVisitor):
    """Find effect sites; skip annotations; track function enclosure."""

    def __init__(
        self,
        rel_path: str,
        module_aliases: dict[str, str] | None = None,
        name_origins: dict[str, str] | None = None,
    ) -> None:
        self.rel_path = rel_path
        self.sites: list[dict[str, object]] = []
        self._fn_depth = 0
        self._module_aliases = module_aliases or {}
        self._name_origins = name_origins or {}

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
        elif self.rel_path == SEAM_MODULE:
            # The provider implementation IS the seam: its primitives are
            # what mediation routes through, not bypasses of it.
            classification = "mediated"
        else:
            classification = "bypass"
        self._record(node, symbol, category, classification)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        parts = _chain(node)
        if parts is not None:
            if _is_mediated(parts):
                method = parts[-1].removesuffix("()")
                category = "time" if method == "now" else (
                    "rng" if method in {"random", "getrandbits"} else "ordering"
                )
                self._record(node, ".".join(parts), category, "mediated")
                return
            resolved = _resolve_alias(parts, self._module_aliases)
            dotted = ".".join(resolved)
            matched = False
            for suffix, category in CHAIN_SUFFIXES.items():
                if dotted == suffix or dotted.endswith("." + suffix):
                    self._classify_and_record(node, suffix, category, False)
                    matched = True
                    break
            if not matched and resolved[-1] in ATTR_METHODS and len(resolved) > 1:
                self._classify_and_record(
                    node, f"*.{resolved[-1]}", ATTR_METHODS[resolved[-1]], False
                )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if not isinstance(node.ctx, ast.Load):
            return
        origin = self._name_origins.get(node.id)
        if origin is not None:
            for suffix, category in CHAIN_SUFFIXES.items():
                if origin == suffix or origin.endswith("." + suffix):
                    self._classify_and_record(node, suffix, category, False)
                    return
            leaf = origin.rsplit(".", 1)[-1]
            if leaf in BARE_NAMES:
                self._classify_and_record(node, leaf, BARE_NAMES[leaf], False)
                return
        if node.id in BARE_NAMES:
            self._classify_and_record(node, node.id, BARE_NAMES[node.id], False)

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in CALL_ONLY_NAMES
        ):
            self._classify_and_record(
                node.func,
                node.func.id,
                CALL_ONLY_NAMES[node.func.id],
                False,
            )
        self.generic_visit(node)


def scan_source(source: str, rel_path: str) -> list[dict[str, object]]:
    """Scan Python source for effect sites (alias-aware). Pure function."""
    tree = ast.parse(source)
    aliases = AliasCollector()
    aliases.visit(tree)
    scanner = EffectScanner(
        rel_path,
        module_aliases=aliases.module_aliases,
        name_origins=aliases.name_origins,
    )
    scanner.visit(tree)
    return scanner.sites
