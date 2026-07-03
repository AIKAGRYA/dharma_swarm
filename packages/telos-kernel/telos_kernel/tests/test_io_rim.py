"""Enforce the core/rim trust boundary at the AST level.

Contract
--------
Every Python module under `telos_kernel/` (excluding `_io/` and `tests/`)
is the *verified core*. It must not perform any of these effects:

  - `open(...)` (Effect.FS_READ / FS_WRITE)
  - `subprocess.*` (Effect.SUBPROCESS)
  - `yaml.*` (Effect.FS_READ via parsers we don't control)
  - `Path.rglob`, `Path.glob`, `Path.iterdir` (Effect.FS_READ)
  - `socket.*`, `urllib.*`, `requests.*`, `httpx.*` (Effect.NET)
  - `os.system`, `os.popen`, `os.execv*`, `os.fork`
  - `import subprocess`, `import yaml`, `import socket`, `import requests`,
    `import httpx`

Approved rim imports (`from telos_kernel._io ...`) are allowed anywhere
in core, but the rim function bodies must not be called from a
verified-hot-path function. That call-site check is a runtime property
tested by test_boot; the AST check here catches static drift.

Exemptions
----------
None. Every core file must be effect-free at the AST level; the earlier
`FileBackend` shim was migrated to `_io.merkle_file_backend.FileBackendIO`
in PR #1d, and the core-side `FileBackend` name is now a thin factory
that imports from the rim inside the function body (verified by
`test_rim_reachable_from_core_only_via_local_imports`).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

KERNEL_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_CALL_NAMES = {"open"}
FORBIDDEN_ATTR_ROOTS = {
    "subprocess",
    "yaml",
    "socket",
    "urllib",
    "requests",
    "httpx",
}
FORBIDDEN_PATH_METHODS = {"rglob", "glob", "iterdir"}
FORBIDDEN_OS_METHODS = {"system", "popen", "execv", "execvp", "execvpe", "fork"}
FORBIDDEN_IMPORTS = {
    "subprocess",
    "yaml",
    "socket",
    "urllib",
    "urllib.request",
    "urllib.parse",
    "requests",
    "httpx",
}

# (module_path_suffix, node_predicate_reason) — grep-friendly, one-off exemptions.
# Format: (posix path suffix, minimum line, maximum line, human reason).
# Empty in PR #1d onward — the earlier FileBackend exemption was closed.
EXEMPTIONS: list[tuple[str, int, int, str]] = []


def _is_exempt(path: Path, lineno: int) -> bool:
    suffix = str(path).replace("\\", "/")
    for module_suffix, lo, hi, _reason in EXEMPTIONS:
        if suffix.endswith(module_suffix) and lo <= lineno <= hi:
            return True
    return False


def _core_files():
    for p in sorted(KERNEL_ROOT.rglob("*.py")):
        s = str(p).replace("\\", "/")
        if "/_io/" in s or "/tests/" in s:
            continue
        yield p


@pytest.mark.parametrize("path", list(_core_files()), ids=lambda p: p.name)
def test_core_module_has_no_forbidden_effects(path):
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    violations: list[str] = []

    for node in ast.walk(tree):
        # Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                    if not _is_exempt(path, node.lineno):
                        violations.append(
                            f"line {node.lineno}: forbidden import {alias.name!r}"
                        )
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in FORBIDDEN_IMPORTS:
                if not _is_exempt(path, node.lineno):
                    violations.append(
                        f"line {node.lineno}: forbidden `from {node.module} import ...`"
                    )

        # Calls
        elif isinstance(node, ast.Call):
            if _is_exempt(path, node.lineno):
                continue
            f = node.func
            # open(...)
            if isinstance(f, ast.Name) and f.id in FORBIDDEN_CALL_NAMES:
                violations.append(f"line {node.lineno}: forbidden call {f.id}(...)")
            # subprocess.foo(...), yaml.foo(...), etc.
            elif isinstance(f, ast.Attribute):
                root = f
                while isinstance(root.value, ast.Attribute):
                    root = root.value
                if isinstance(root.value, ast.Name):
                    base = root.value.id
                    if base in FORBIDDEN_ATTR_ROOTS:
                        violations.append(
                            f"line {node.lineno}: forbidden call "
                            f"{base}.{f.attr}(...)"
                        )
                    elif base == "os" and f.attr in FORBIDDEN_OS_METHODS:
                        violations.append(
                            f"line {node.lineno}: forbidden call os.{f.attr}(...)"
                        )
                    # p.rglob, some_path.glob, etc. \u2014 conservative: any
                    # attribute named `rglob`/`glob`/`iterdir` is flagged.
                if f.attr in FORBIDDEN_PATH_METHODS:
                    violations.append(
                        f"line {node.lineno}: forbidden Path.{f.attr}(...) walk"
                    )

    if violations:
        pytest.fail(
            f"{path.name} has forbidden effects in the verified core:\n  "
            + "\n  ".join(violations)
            + "\n\nMove the effectful code into telos_kernel/_io/ and expose "
            "a pure wrapper here."
        )


def test_rim_functions_are_tagged():
    """Every public function in `_io/*.py` has an @effect(...) tag."""
    import inspect
    from telos_kernel import _io

    io_root = Path(_io.__file__).parent
    untagged: list[str] = []
    for p in sorted(io_root.glob("*.py")):
        if p.name == "__init__.py":
            continue
        # Import the module and walk its top-level callables.
        mod_name = f"telos_kernel._io.{p.stem}"
        mod = __import__(mod_name, fromlist=["*"])
        for name, obj in vars(mod).items():
            if name.startswith("_"):
                continue
            if inspect.isfunction(obj) and obj.__module__ == mod_name:
                if not hasattr(obj, "__effects__"):
                    untagged.append(f"{mod_name}.{name}")
    assert not untagged, (
        "Rim functions missing @effect(...) tag:\n  " + "\n  ".join(untagged)
    )


def test_rim_reachable_from_core_only_via_local_imports():
    """Core modules may import from _io only inside function bodies, not at
    top level. This keeps the core module's import graph pure.
    """
    for path in _core_files():
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("telos_kernel._io"):
                    pytest.fail(
                        f"{path.name}:{node.lineno} imports {node.module!r} at "
                        f"module scope; move it into the function body that "
                        f"needs it so the core import graph stays pure."
                    )
