#!/usr/bin/env python3
"""Name-drift gate — static first-party import resolution.

A rename or removal of a public symbol leaves stale callers behind. Python
only raises ``ImportError`` for the stale caller when something actually
imports that module, so a rename slips past the test suite whenever the
stale caller lives in a module no test exercises. This gate closes that hole
by resolving every *first-party* ``from <pkg> import <name>`` / ``import
<pkg>`` statement against the source tree on disk, independently of whether
any test imports it.

It is deliberately conservative — it only reports a drift when it can
resolve the target module on disk **and** confirm the imported name is
absent, and it skips modules it cannot reason about confidently (wildcard
re-exports, ``__getattr__`` dynamic attributes). The goal is zero false
positives so the gate can block.

Drift already present when the gate was introduced is grandfathered via
``scripts/governance/name_drift_allowlist.txt`` (one ``path::kind::detail``
signature per line), exactly like the ``GRANDFATHERED`` set in
``check_module_budget.py``. The scan runs against the **whole** tree on
every invocation, so a rename that breaks a caller in a file the PR never
touched still fails — that caller's signature is not in the allowlist.
Shrinking the allowlist (by fixing the stale reference) is the ratchet
tightening; new drift can never be added to it without an explicit
``--update-baseline`` run.

Scope:
  * First-party imports only (top-level package present in the source tree).
  * Absolute and relative (``from . import x``) imports.
  * ``from pkg import name`` and ``import pkg.sub`` forms.

Out of scope (by design, to stay false-positive-free):
  * Third-party / hallucinated dependencies — see check_import_provenance.py.
  * Attribute access (``mod.symbol``) — too aliased to resolve statically.

Usage:
    python3 scripts/governance/check_name_drift.py
    python3 scripts/governance/check_name_drift.py --json

Exit codes:
    0   every first-party import resolves
    1   at least one first-party import references a missing module/name
    2   environment error
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Module dunders are runtime attributes of the module object, not top-level
# definitions, so ``from pkg import __file__`` resolves at runtime even
# though no AST node defines them. Treat them as always-resolvable.
MODULE_DUNDERS = frozenset({
    "__file__", "__name__", "__doc__", "__path__", "__package__",
    "__spec__", "__loader__", "__builtins__", "__dict__", "__version__",
    "__all__",
})

ALLOWLIST_REL = "scripts/governance/name_drift_allowlist.txt"

EXCLUDE_DIR_FRAGMENTS = (
    "/.venv/",
    "/venv/",
    "/__pycache__/",
    "/migrations/",
    "/_vendor/",
    "/node_modules/",
    "/.git/",
    "/build/",
    "/dist/",
    "/dharma_swarm_old/",
    "/migration_delta/",
)


@dataclass(frozen=True)
class Drift:
    path: str
    line: int
    kind: str  # "missing-module" | "missing-name"
    detail: str

    def signature(self) -> str:
        """Stable identity that ignores line numbers (they shift on edits)."""
        return f"{self.path}::{self.kind}::{self.detail}"


def repo_root() -> Path:
    out = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
    return Path(out)


def _excluded(path: Path, root: Path) -> bool:
    rel = f"/{path.relative_to(root).as_posix()}"
    return any(frag in rel for frag in EXCLUDE_DIR_FRAGMENTS)


def iter_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*.py"):
        if _excluded(p, root):
            continue
        files.append(p)
    return files


def first_party_roots(root: Path) -> set[str]:
    """Top-level import names that resolve to source in this repo.

    A name is first-party if the repo root has a package directory of that
    name (contains ``__init__.py``), a namespace directory of that name that
    itself contains ``.py`` files, or a top-level ``<name>.py`` module.
    """
    roots: set[str] = set()
    for child in root.iterdir():
        name = child.name
        if name.startswith(".") or f"/{name}/" in EXCLUDE_DIR_FRAGMENTS:
            continue
        if child.is_dir():
            if (child / "__init__.py").exists():
                roots.add(name)
            elif any(child.rglob("*.py")):
                roots.add(name)
        elif child.suffix == ".py":
            roots.add(child.stem)
    return roots


@dataclass
class ModuleFacts:
    """What a resolved module file exports, for name-resolution purposes."""

    found: bool
    is_package: bool
    dir_path: Path | None
    defined: set[str]
    has_star_import: bool
    has_dynamic_getattr: bool


def _collect_module_facts(module_file: Path | None, pkg_dir: Path | None) -> ModuleFacts:
    defined: set[str] = set()
    has_star = False
    has_dyn = False
    if module_file is not None and module_file.exists():
        try:
            tree = ast.parse(module_file.read_text(encoding="utf-8"))
        except (SyntaxError, ValueError, OSError):
            # Cannot parse -> treat as opaque (resolve everything; never a false fail).
            return ModuleFacts(True, pkg_dir is not None, pkg_dir, set(), True, True)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.add(node.name)
                if node.name == "__getattr__":
                    has_dyn = True
            elif isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        defined.add(tgt.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    defined.add(node.target.id)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    defined.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        has_star = True
                    else:
                        defined.add(alias.asname or alias.name)
    return ModuleFacts(
        found=module_file is not None and module_file.exists(),
        is_package=pkg_dir is not None,
        dir_path=pkg_dir,
        defined=defined,
        has_star_import=has_star,
        has_dynamic_getattr=has_dyn,
    )


def resolve_module(dotted: str, root: Path) -> ModuleFacts:
    """Resolve a dotted module name to its source file/package on disk."""
    parts = dotted.split(".")
    base = root.joinpath(*parts)
    init = base / "__init__.py"

    if init.exists():
        return _collect_module_facts(init, base)
    if base.with_suffix(".py").exists():
        return _collect_module_facts(base.with_suffix(".py"), None)
    if base.is_dir():  # namespace package (no __init__.py)
        return ModuleFacts(True, True, base, set(), True, False)
    return ModuleFacts(False, False, None, set(), False, False)


def _name_exists(name: str, facts: ModuleFacts, root: Path) -> bool:
    if not facts.found:
        return False
    if name in MODULE_DUNDERS:
        return True  # runtime module attribute, not an AST definition
    if facts.has_star_import or facts.has_dynamic_getattr:
        return True  # opaque module -> never a false fail
    if name in facts.defined:
        return True
    if facts.is_package and facts.dir_path is not None:
        # Submodule import: `from pkg import submodule`.
        if (facts.dir_path / f"{name}.py").exists():
            return True
        if (facts.dir_path / name / "__init__.py").exists():
            return True
        if (facts.dir_path / name).is_dir():
            return True
    return False


def _resolve_relative(node: ast.ImportFrom, current: Path, root: Path) -> str | None:
    """Turn a relative ``from . import`` into an absolute dotted module."""
    pkg_parts = list(current.relative_to(root).parts)
    if current.name == "__init__.py":
        pkg_parts = pkg_parts[:-1]  # the package is the directory
    else:
        pkg_parts = pkg_parts[:-1]  # drop the module file name
    # level=1 -> current package; level=2 -> parent; etc.
    up = node.level - 1
    if up > len(pkg_parts):
        return None
    base = pkg_parts[: len(pkg_parts) - up] if up else pkg_parts
    if node.module:
        base = [*base, *node.module.split(".")]
    return ".".join(base) if base else None


def scan_file(path: Path, root: Path, fp_roots: set[str]) -> list[Drift]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, ValueError, OSError):
        return []
    rel = path.relative_to(root).as_posix()
    drifts: list[Drift] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                dotted = _resolve_relative(node, path, root)
                if dotted is None:
                    continue
            else:
                dotted = node.module or ""
                if dotted.split(".")[0] not in fp_roots:
                    continue  # third-party / stdlib -> not our concern here
            facts = resolve_module(dotted, root)
            if not facts.found:
                drifts.append(
                    Drift(rel, node.lineno, "missing-module",
                          f"`from {dotted} import ...` -> module not found on disk")
                )
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                if not _name_exists(alias.name, facts, root):
                    drifts.append(
                        Drift(rel, node.lineno, "missing-name",
                              f"`from {dotted} import {alias.name}` -> name not defined in module")
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in fp_roots:
                    continue
                facts = resolve_module(alias.name, root)
                if not facts.found:
                    drifts.append(
                        Drift(rel, node.lineno, "missing-module",
                              f"`import {alias.name}` -> module not found on disk")
                    )
    return drifts


def load_allowlist(root: Path) -> set[str]:
    path = root / ALLOWLIST_REL
    if not path.exists():
        return set()
    sigs: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            sigs.add(line)
    return sigs


def write_allowlist(root: Path, drifts: list[Drift]) -> Path:
    path = root / ALLOWLIST_REL
    header = (
        "# name-drift allowlist — pre-existing unresolved first-party imports,\n"
        "# grandfathered when check_name_drift.py was introduced. Each line is a\n"
        "# `path::kind::detail` signature. Shrinking this file (by fixing the\n"
        "# stale reference) tightens the ratchet. Regenerate with:\n"
        "#   python3 scripts/governance/check_name_drift.py --update-baseline\n"
    )
    body = "\n".join(sorted({d.signature() for d in drifts}))
    path.write_text(header + body + ("\n" if body else ""), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument(
        "--update-baseline", action="store_true",
        help="rewrite the allowlist from the current scan (explicit opt-in)",
    )
    parser.add_argument(
        "--no-allowlist", action="store_true",
        help="ignore the allowlist and report every drift (audit/whole-repo mode)",
    )
    args = parser.parse_args(argv)

    try:
        root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"name-drift: environment error: {exc}", file=sys.stderr)
        return 2

    os.chdir(root)
    fp_roots = first_party_roots(root)
    all_drifts: list[Drift] = []
    for path in iter_python_files(root):
        all_drifts.extend(scan_file(path, root, fp_roots))

    if args.update_baseline:
        dest = write_allowlist(root, all_drifts)
        print(f"name-drift: wrote {len(all_drifts)} signature(s) to "
              f"{dest.relative_to(root)}")
        return 0

    allowlist = set() if args.no_allowlist else load_allowlist(root)
    new_drifts = [d for d in all_drifts if d.signature() not in allowlist]
    grandfathered = len(all_drifts) - len(new_drifts)

    if args.json:
        print(json.dumps(
            {"new": [d.__dict__ for d in new_drifts],
             "grandfathered": grandfathered}, indent=2, sort_keys=True,
        ))
        return 1 if new_drifts else 0

    if not new_drifts:
        print(f"name-drift: OK — every first-party import resolves "
              f"({grandfathered} grandfathered; roots: {', '.join(sorted(fp_roots))}).")
        return 0

    print(f"::error::name-drift — {len(new_drifts)} NEW unresolved first-party "
          f"import(s) ({grandfathered} grandfathered):")
    for d in sorted(new_drifts, key=lambda x: (x.path, x.line)):
        print(f"  {d.path}:{d.line}  [{d.kind}]  {d.detail}")
    print("If this is an intentional, reviewed rename, fix the stale reference; "
          "do NOT add it to the allowlist except via --update-baseline.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
