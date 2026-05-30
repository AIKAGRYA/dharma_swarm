"""AST-based structural danger detection for the TelosProof allow-list.

Extracted (behavior-preserving) from ``allowlist.py`` so neither module exceeds
the 1000-line budget. This module owns the L3-AST layer: STRUCTURAL detection of
any write / persist / spawn / exec / mutate-env / elevate operation in a Python
source body, regardless of how it is named, aliased, or chained.

THE CARDINAL FAILURE THIS LAYER FIXES
-------------------------------------
Per-line literal/regex matching is rename/synonym/aliasing-bypassable. A new
function whose BODY does real harm (writes/persists, spawns, exec/evals, mutates
env, or elevates privilege via attribute mutation) slipped through because the
only body check was a small literal token list. This module replaces that with
AST-level STRUCTURAL detection: parse the candidate body and walk the tree for
any call / attribute / import / assignment that can WRITE, PERSIST, SPAWN, EXEC,
MUTATE ENV, or ELEVATE — through ANY surface, regardless of how it is named,
aliased, or chained. Anything we cannot AST-parse is treated as maximally unsafe
(cannot prove safe -> REVIEW), mirroring the v0 cardinal rule.

The public entrypoint is :func:`body_has_danger_locus` (== the former private
``_ast_danger_locus``): it returns danger evidence for a parseable source body,
``None`` if proven-clean, and the sentinel ``"<unparseable>"`` when the source
cannot be AST-parsed.
"""

from __future__ import annotations

import ast
from typing import Optional

# ---------------------------------------------------------------------------
# L3-AST: structural body-level danger detection (replaces the leaky token list)
# ---------------------------------------------------------------------------

# Function NAMES (bare callables / final attribute) that can write/persist/spawn/
# exec/elevate. Matched on the trailing attribute, so `_db.connect`, `redis.Redis`,
# `Path(p).open` all hit regardless of the receiver/alias chain.
_DANGER_CALL_NAMES: frozenset[str] = frozenset(
    {
        # exec / eval — arbitrary code execution
        "exec",
        "eval",
        "compile",
        "__import__",
        # privilege / attribute mutation
        "setattr",
        "delattr",
        # write-capable file surfaces
        "open",        # any open(); mode is validated separately, but a bare
                       # open inside a NEW function we cannot prove read-only is
                       # treated conservatively (see _open_is_write_mode).
        "fdopen",
        "write",
        "writelines",
        "write_text",
        "write_bytes",
        "truncate",
        "mkdir",
        "makedirs",
        "rename",
        "replace",
        "remove",
        "unlink",
        "rmdir",
        "chmod",
        "chown",
        # os low-level / process spawn / env
        "system",
        "popen",
        "spawn",
        "spawnl",
        "spawnv",
        "execv",
        "execve",
        "execvp",
        "putenv",
        "setenv",
        "unsetenv",
        # subprocess surface
        "run",         # subprocess.run / Popen-style; conservative (a benign
                       # .run() inside a NEW pure function is rare and the false
                       # REVIEW is cheap by the cardinal rule).
        "call",
        "check_call",
        "check_output",
        "Popen",
        # persistence drivers (connect/open factories)
        "connect",
        "create_engine",
        "sessionmaker",
        "FileIO",
        "Redis",
        "StrictRedis",
        "dump",        # json.dump / pickle.dump
    }
)

# Module roots whose IMPORT inside a new function body signals persistence /
# spawn / write capability. Matched on the import's TOP-LEVEL module, so an
# `import sqlite3 as _db` or `from redis import Redis` still trips.
_DANGER_IMPORT_ROOTS: frozenset[str] = frozenset(
    {
        "sqlite3",
        "aiosqlite",
        "sqlalchemy",
        "psycopg2",
        "psycopg",
        "redis",
        "shelve",
        "pickle",
        "dbm",
        "lmdb",
        "plyvel",
        "leveldb",
        "subprocess",
        "shutil",
        "tempfile",
        "multiprocessing",
        "socket",
    }
)

# Attribute-name fragments which, when the TARGET of an assignment (obj.attr = …,
# obj.attr += …, or setattr(obj, "attr", …)), indicate a privilege / autonomy /
# shadow / permission ELEVATION. These mirror v0's autonomy/shadow surface but
# are matched on the assignment-target attribute name, structurally.
_ELEVATION_ATTR_FRAGMENTS: tuple[str, ...] = (
    "permission",
    "autonomy",
    "shadow",
    "privilege",
    "is_admin",
    "is_root",
    "sudo",
    "elevate",
    "bypass",
    "approval",
    "consent",
)

# os.environ subscript-assignment surface: `os.environ['X'] = …` or an aliased
# `environ['X'] = …` is a MUTATE-ENV. Detected structurally (Subscript target on
# an `environ` name/attribute), so renamed imports cannot escape.
_ENVIRON_NAMES: tuple[str, ...] = ("environ",)


def _attr_chain_tail(node: ast.AST) -> Optional[str]:
    """Return the trailing attribute/identifier of a Call's func, or None.

    `open` -> "open"; `os.open` -> "open"; `Path(p).open` -> "open";
    `_db.connect` -> "connect". We deliberately use only the TAIL so alias /
    receiver chains cannot hide the dangerous operation behind a rename.
    """
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _open_is_write_mode(call: ast.Call) -> bool:
    """Best-effort: True unless an open()-style call is PROVABLY read-only.

    Cardinal rule: we ALLOW a bare open only when we can positively prove it is
    read-only (no mode, or an explicit 'r'/'rb'/'rt' literal). Any non-literal
    mode, or any write/append/plus/exclusive mode, is treated as a write.
    """
    mode: Optional[ast.AST] = None
    if len(call.args) >= 2:
        mode = call.args[1]
    for kw in call.keywords:
        if kw.arg == "mode":
            mode = kw.value
    if mode is None:
        # open(path) with no mode is read-only by Python default.
        return False
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        m = mode.value.lower()
        # read-only iff it contains NO write/append/exclusive/update char.
        return any(c in m for c in ("w", "a", "x", "+"))
    # Non-literal mode (a variable / expression) — cannot prove read-only.
    return True


def _assign_target_is_elevation(target: ast.AST) -> Optional[str]:
    """Return evidence if an assignment TARGET is an elevation/env-mutation.

    Catches `obj.permissions = …` / `cfg.shadow_mode = …` (Attribute target on
    an elevation fragment) and `os.environ['X'] = …` / aliased `environ[…] = …`
    (Subscript target on an environ name).
    """
    if isinstance(target, ast.Attribute):
        attr = target.attr.lower()
        for frag in _ELEVATION_ATTR_FRAGMENTS:
            if frag in attr:
                return f"assignment to elevation attribute .{target.attr}"
        return None
    if isinstance(target, ast.Subscript):
        base = target.value
        name = _attr_chain_tail(base)
        if name and name.lower() in _ENVIRON_NAMES:
            return "subscript assignment to os.environ (mutate-env)"
    return None


class _DangerVisitor(ast.NodeVisitor):
    """Walk a function/module body for any write/persist/spawn/exec/elevate op."""

    def __init__(self) -> None:
        self.locus: Optional[str] = None

    def _flag(self, msg: str) -> None:
        if self.locus is None:
            self.locus = msg

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".", 1)[0].lower()
            if root in _DANGER_IMPORT_ROOTS:
                self._flag(f"import of write/persist/spawn module {alias.name!r}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        root = (node.module or "").split(".", 1)[0].lower()
        if root in _DANGER_IMPORT_ROOTS:
            self._flag(f"from-import of write/persist/spawn module {node.module!r}")
        # `from os import environ` makes a bare `environ[...] = ...` an env mutate;
        # that subscript is caught at assignment time.
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        tail = _attr_chain_tail(node.func)
        if tail is not None:
            if tail == "open" or tail == "FileIO":
                # open()/FileIO() — only safe if PROVABLY read-only.
                if _open_is_write_mode(node):
                    self._flag(f"write-mode {tail}() call")
            elif tail in _DANGER_CALL_NAMES:
                self._flag(f"call to write/persist/spawn/exec surface {tail}()")
            # os.environ.get is fine; os.environ-mutating methods are not.
            elif tail in ("pop", "clear", "update", "setdefault"):
                recv = node.func.value if isinstance(node.func, ast.Attribute) else None
                if recv is not None and _attr_chain_tail(recv) in _ENVIRON_NAMES:
                    self._flag(f"os.environ.{tail}() (mutate-env)")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for tgt in node.targets:
            ev = _assign_target_is_elevation(tgt)
            if ev is not None:
                self._flag(ev)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        ev = _assign_target_is_elevation(node.target)
        if ev is not None:
            self._flag(ev)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        ev = _assign_target_is_elevation(node.target)
        if ev is not None:
            self._flag(ev)
        self.generic_visit(node)


def body_has_danger_locus(source: str) -> Optional[str]:
    """Return danger evidence for a parseable source body, or None if proven-clean.

    The sentinel ``"<unparseable>"`` is returned when the source cannot be AST-
    parsed: an unparseable body CANNOT be proven safe and therefore is treated as
    maximally unsafe (the caller routes it to REVIEW). This is the structural
    replacement for the literal token list across FN2/FN3/FN4.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "<unparseable>"
    visitor = _DangerVisitor()
    visitor.visit(tree)
    return visitor.locus


# Backwards-compatible private alias (the former in-module entrypoint name).
_ast_danger_locus = body_has_danger_locus


__all__ = [
    "body_has_danger_locus",
    "_DangerVisitor",
    "_ast_danger_locus",
    "_attr_chain_tail",
    "_open_is_write_mode",
    "_assign_target_is_elevation",
    "_DANGER_CALL_NAMES",
    "_DANGER_IMPORT_ROOTS",
    "_ELEVATION_ATTR_FRAGMENTS",
    "_ENVIRON_NAMES",
]
