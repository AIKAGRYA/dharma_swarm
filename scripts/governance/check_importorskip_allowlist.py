#!/usr/bin/env python3
"""First-party ``importorskip`` allowlist gate (TV-01 / F3).

``pytest.importorskip("dharma_swarm...")`` on a *first-party* module is a
silent-deletion hazard: if the module is later renamed or deleted, the test
does not FAIL, it SKIPS, and the suite stays green while coverage quietly
vanishes. A first-party module that the repo ships should be a hard ``import``
so its disappearance breaks collection loudly.

This gate makes the set of first-party ``importorskip`` call sites explicit and
fail-closed in two directions:

1. **Net-new masking** — every ``importorskip("dharma_swarm...")`` call site
   must have its target module listed in
   ``scripts/governance/importorskip_allowlist.txt``. A new guard on a
   first-party module fails CI until a human either justifies it (adds it to
   the allowlist) or removes it. A deleted internal module re-masked behind a
   fresh ``importorskip`` is therefore caught.

2. **Deletion behind an existing guard** — every allowlisted module must still
   resolve to a source file on disk. If an allowlisted module's file is gone,
   the guard would now be silently skipping a real deletion, so the gate FAILS.

Third-party guards (``importorskip("hypothesis")``, ``importorskip("torch")``,
stdlib, etc.) are out of scope: skipping on a genuinely-optional dependency is
legitimate. Only the ``dharma_swarm`` first-party root is policed here.

Usage:
    python3 scripts/governance/check_importorskip_allowlist.py
    python3 scripts/governance/check_importorskip_allowlist.py --json
    python3 scripts/governance/check_importorskip_allowlist.py --update-baseline

Exit codes:
    0   every first-party importorskip is allowlisted and resolves
    1   at least one un-allowlisted guard, or an allowlisted module is missing
    2   environment error
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ALLOWLIST_REL = "scripts/governance/importorskip_allowlist.txt"
FIRST_PARTY_ROOT = "dharma_swarm"

EXCLUDE_DIR_FRAGMENTS = (
    "/.venv/",
    "/venv/",
    "/__pycache__/",
    "/_vendor/",
    "/node_modules/",
    "/.git/",
    "/build/",
    "/dist/",
    "/dharma_swarm_old/",
    "/migration_delta/",
)


@dataclass(frozen=True)
class Guard:
    module: str
    path: str
    line: int


def repo_root() -> Path:
    out = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
    return Path(out)


def _excluded(path: Path, root: Path) -> bool:
    rel = f"/{path.relative_to(root).as_posix()}"
    return any(frag in rel for frag in EXCLUDE_DIR_FRAGMENTS)


def iter_python_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if not _excluded(p, root)]


def _is_importorskip_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "importorskip"
    if isinstance(func, ast.Name):
        return func.id == "importorskip"
    return False


def collect_first_party_guards(root: Path) -> list[Guard]:
    guards: list[Guard] = []
    for path in iter_python_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, ValueError, OSError):
            continue
        rel = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_importorskip_call(node):
                continue
            if not node.args:
                continue
            first = node.args[0]
            if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
                continue
            module = first.value
            top = module.split(".")[0]
            if top == FIRST_PARTY_ROOT:
                guards.append(Guard(module, rel, node.lineno))
    return guards


def module_resolves(root: Path, dotted: str) -> bool:
    parts = dotted.split(".")
    base = root.joinpath(*parts)
    return base.with_suffix(".py").exists() or (base / "__init__.py").exists()


def load_allowlist(root: Path) -> set[str]:
    path = root / ALLOWLIST_REL
    if not path.exists():
        return set()
    out: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.add(line)
    return out


def write_allowlist(root: Path, modules: set[str]) -> Path:
    path = root / ALLOWLIST_REL
    header = (
        "# importorskip allowlist — first-party (dharma_swarm.*) modules that the\n"
        "# test suite currently guards with pytest.importorskip. A NEW first-party\n"
        "# guard not listed here fails check_importorskip_allowlist.py, and an\n"
        "# allowlisted module whose source file disappears also fails (a deleted\n"
        "# internal module must break collection, not silently skip). Regenerate\n"
        "# the frozen baseline with:\n"
        "#   python3 scripts/governance/check_importorskip_allowlist.py --update-baseline\n"
    )
    body = "\n".join(sorted(modules))
    path.write_text(header + body + ("\n" if body else ""), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args(argv)

    try:
        root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"importorskip-allowlist: environment error: {exc}", file=sys.stderr)
        return 2

    guards = collect_first_party_guards(root)
    used_modules = {g.module for g in guards}

    if args.update_baseline:
        dest = write_allowlist(root, used_modules)
        print(
            f"importorskip-allowlist: wrote {len(used_modules)} first-party "
            f"module(s) to {dest.relative_to(root)}"
        )
        return 0

    allowlist = load_allowlist(root)
    unlisted = sorted(g for g in guards if g.module not in allowlist)
    missing_files = sorted(m for m in allowlist if not module_resolves(root, m))
    stale = sorted(allowlist - used_modules - set(missing_files))

    if args.json:
        print(json.dumps(
            {
                "guards": [
                    {"module": g.module, "path": g.path, "line": g.line}
                    for g in guards
                ],
                "unlisted": [
                    {"module": g.module, "path": g.path, "line": g.line}
                    for g in unlisted
                ],
                "missing_files": missing_files,
                "stale_allowlist_entries": stale,
            },
            indent=2,
            sort_keys=True,
        ))
        return 1 if (unlisted or missing_files) else 0

    if not unlisted and not missing_files:
        print(
            f"importorskip-allowlist: OK — {len(guards)} first-party guard(s), "
            f"all allowlisted and resolving."
        )
        if stale:
            print(
                f"  note: {len(stale)} stale allowlist entr(y/ies) no longer used: "
                f"{', '.join(stale)} (safe to prune via --update-baseline)."
            )
        return 0

    if unlisted:
        print(
            f"::error::importorskip-allowlist — {len(unlisted)} first-party "
            f"importorskip guard(s) not in the allowlist:"
        )
        for g in unlisted:
            print(f"  {g.module}  (importorskip at {g.path}:{g.line})")
        print(
            "A first-party module should be a hard import. If this guard is "
            "genuinely justified (e.g. an optional cross-lane module), add the "
            "module to "
            f"{ALLOWLIST_REL}; otherwise convert it to a plain import."
        )

    if missing_files:
        print(
            f"::error::importorskip-allowlist — {len(missing_files)} allowlisted "
            f"module(s) no longer resolve to a source file (a deletion would now "
            f"be silently skipped):"
        )
        for m in missing_files:
            print(f"  {m}")
        print(
            "Remove the dead importorskip + its allowlist entry, or restore the "
            "module. A deleted internal module must FAIL collection, not skip."
        )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
