"""Trust-boundary tests — the TCB import allow-list and AST bans.

SECURITY.md §1 and §3 declare the allowed import surface and the banned AST
constructs. This module enforces both statically.

Any PR that widens the allow-list is by definition a manifest edit (§U2) and
must go through the K=3/N=5 quorum path.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

KERNEL_ROOT = Path(__file__).resolve().parents[1]  # telos_kernel/

# Phase 1 kernel core allow-list. The rim (telos_kernel/_io/) has a
# broader allow-list because effect-carrying imports (os, tempfile,
# functools) are the entire point of its existence. See SECURITY.md
# and telos_kernel/_io/effect.py.
ALLOWED_TOP_LEVEL_IMPORTS: frozenset[str] = frozenset({
    # stdlib — pure or crypto primitives only
    "__future__", "abc", "dataclasses", "datetime", "enum", "functools",
    "hashlib", "hmac", "json", "math", "pathlib", "re", "secrets",
    "subprocess", "sys", "typing", "uuid",
    # allow-listed 3rd party
    "cryptography", "icontract", "pydantic", "yaml",
    # first-party
    "telos_kernel",
})

# The I/O rim is the designated effect boundary. It may import a small
# number of additional stdlib modules that would be banned in core.
# Every function that uses these modules MUST be tagged with @effect(...)
# from telos_kernel/_io/effect.py (enforced by test_io_rim.py).
RIM_EXTRA_IMPORTS: frozenset[str] = frozenset({
    "os",         # os.replace for atomic file writes
    "tempfile",   # atomic write staging
})
ALLOWED_RIM_IMPORTS: frozenset[str] = ALLOWED_TOP_LEVEL_IMPORTS | RIM_EXTRA_IMPORTS

# AST nodes/names that are outright forbidden inside the TCB.
FORBIDDEN_CALL_NAMES: frozenset[str] = frozenset({
    "eval", "exec", "compile", "__import__",
})


def _kernel_py_files() -> list[Path]:
    return [
        p for p in sorted(KERNEL_ROOT.rglob("*.py"))
        if "/tests/" not in str(p).replace("\\", "/")
    ]


def _is_rim_file(path: Path) -> bool:
    rel = path.relative_to(KERNEL_ROOT).as_posix()
    return rel.startswith("_io/") or rel == "_io.py"


class TestImportAllowList:
    @pytest.mark.parametrize("path", _kernel_py_files(), ids=lambda p: str(p.name))
    def test_only_allowed_top_level_imports(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        allowed = ALLOWED_RIM_IMPORTS if _is_rim_file(path) else ALLOWED_TOP_LEVEL_IMPORTS
        offending: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top not in allowed:
                        offending.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    # relative import — must resolve within telos_kernel
                    continue
                mod = (node.module or "").split(".")[0]
                if mod and mod not in allowed:
                    offending.append(f"from {node.module} import ...")
        assert not offending, (
            f"{path.relative_to(KERNEL_ROOT)} imports outside the allow-list: "
            f"{offending}"
        )


class TestForbiddenConstructs:
    @pytest.mark.parametrize("path", _kernel_py_files(), ids=lambda p: str(p.name))
    def test_no_eval_exec_import(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_CALL_NAMES:
                    raise AssertionError(
                        f"{path.relative_to(KERNEL_ROOT)}:{node.lineno} "
                        f"uses forbidden call `{node.func.id}(...)`"
                    )

    @pytest.mark.parametrize("path", _kernel_py_files(), ids=lambda p: str(p.name))
    def test_no_pickle_or_marshal(self, path):
        text = path.read_text(encoding="utf-8")
        # Simple substring check is sufficient given the allow-list; the
        # AST-level check above already blocks dynamic ways of pulling
        # these in.
        for banned in ("pickle", "marshal", "shelve", "dill"):
            # Allow the banned name to appear inside string literals (e.g.
            # SECURITY.md-style comments), but not as an import token.
            for line in text.splitlines():
                stripped = line.split("#", 1)[0]  # drop comments
                if f"import {banned}" in stripped or f"from {banned}" in stripped:
                    raise AssertionError(
                        f"{path.relative_to(KERNEL_ROOT)} references banned "
                        f"module `{banned}`"
                    )


class TestNoAmbientAuthority:
    """The kernel must not expose module-level mutable state that could
    become ambient authority."""

    def test_no_top_level_MerkleLog_instance(self):
        # Import the package fresh and check its attribute dict.
        import telos_kernel
        for name in dir(telos_kernel):
            if name.startswith("_"):
                continue
            obj = getattr(telos_kernel, name)
            # Reject any module-level MerkleLog instance.
            if type(obj).__name__ == "MerkleLog":
                raise AssertionError(
                    f"telos_kernel exposes ambient MerkleLog `{name}`"
                )
