#!/usr/bin/env python3
"""CODEOWNERS auto-routing from measured blast radius.

Doctrine-picked owner files rot: a hand-curated "hot-path" list in
``.github/CODEOWNERS`` drifts away from where the code's real coupling mass
sits, so the highest-leverage modules (the ones a change can break the most
of) can silently end up unprotected. This gate replaces the hand-picked list
with a *measured* one: it builds the intra-package import graph by pure AST
(no imports, no install), computes each module's transitive blast radius
(how many other modules can reach it, i.e. how many are potentially affected
by a change to it), and requires every module whose blast radius clears a
threshold to carry an explicit CODEOWNERS entry.

The number is the policy, not the filenames. As the graph evolves the set of
protected modules is re-derived from measured edges each run, so nothing has
to be hand-tuned and no heavy module can quietly slip out of review routing.

Reference: INTEGRITY_CODEX.md N-1 (CODEOWNERS auto-routed from measured blast
radius). The blast-radius method mirrors dharma_swarm/xray.py import parsing.

Usage:
    python3 scripts/governance/codeowners_blast_radius.py --report
    python3 scripts/governance/codeowners_blast_radius.py --check
    python3 scripts/governance/codeowners_blast_radius.py --emit

Exit codes:
    0   every module at/above the blast-radius threshold is in CODEOWNERS
    1   at least one measured heavy module is missing a CODEOWNERS entry
    2   environment error (package or CODEOWNERS not found)
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections import defaultdict, deque
from pathlib import Path

PACKAGE = "dharma_swarm"
CODEOWNERS_REL = ".github/CODEOWNERS"

# Blast-radius floor (transitive importer count) above which a module must be
# explicitly routed in CODEOWNERS. Derived from measured edges, not per-file
# doctrine: INTEGRITY_CODEX.md N-1 fixes the threshold at 150 importers.
BLAST_THRESHOLD = 150

# The measured top-blast-radius modules named in dive_arch_invariants.md. Held
# as an always-required floor so a threshold nudge can never drop one of them
# below the guarantee; the general check keys off measurement, not this list.
REQUIRED_MODULES = (
    f"{PACKAGE}.models",
    f"{PACKAGE}.correlation_context",
    f"{PACKAGE}.daemon_config",
    f"{PACKAGE}.runtime_contract",
    f"{PACKAGE}.spine.identity",
    f"{PACKAGE}.merkle_log",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _module_map(pkg_dir: Path, repo_root: Path) -> dict[str, Path]:
    """Map dotted internal module name -> repo-relative source path."""
    out: dict[str, Path] = {}
    for f in sorted(pkg_dir.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        rel = f.relative_to(repo_root)
        parts = rel.with_suffix("").parts
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            continue
        out[".".join(parts)] = rel
    return out


def _resolve(candidate: str, internal: set[str]) -> str | None:
    """Longest-prefix resolve a dotted import target to an internal module."""
    cand = candidate
    while cand:
        if cand in internal:
            return cand
        cand = cand.rsplit(".", 1)[0] if "." in cand else ""
    return None


def _import_from_targets(node: ast.ImportFrom, importer_parts: tuple[str, ...]) -> list[str]:
    """Return dotted module candidates for an ImportFrom node.

    The alias-qualified candidate comes first so ``from dharma_swarm import
    model_pool`` resolves to ``dharma_swarm.model_pool`` when that submodule
    exists. If the alias is a class/symbol, longest-prefix resolution falls
    back to the module named in ``from ...``.
    """
    if node.level:
        base = list(importer_parts[:-1])
        for _ in range(node.level - 1):
            base = base[:-1]
        if node.module:
            base.extend(node.module.split("."))
    else:
        base = node.module.split(".") if node.module else []

    base_name = ".".join(base)
    targets: list[str] = []
    for alias in node.names:
        if alias.name == "*":
            continue
        target = ".".join([*base, alias.name])
        if target:
            targets.append(target)
    if base_name:
        targets.append(base_name)
    return targets


def _direct_importers(
    modmap: dict[str, Path], repo_root: Path
) -> dict[str, set[str]]:
    """imported-module -> set of modules that directly import it (AST only)."""
    internal = set(modmap)
    importers: dict[str, set[str]] = defaultdict(set)
    for me, rel in modmap.items():
        try:
            tree = ast.parse((repo_root / rel).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        pkg_parts = rel.with_suffix("").parts
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.ImportFrom):
                targets.extend(_import_from_targets(node, pkg_parts))
            elif isinstance(node, ast.Import):
                targets.extend(a.name for a in node.names)
            for t in targets:
                resolved = _resolve(t, internal)
                if resolved and resolved != me:
                    importers[resolved].add(me)
    return importers


def _blast_radius(importers: dict[str, set[str]], modmap: dict[str, Path]) -> dict[str, int]:
    """Transitive reverse-reachability count per module."""
    out: dict[str, int] = {}
    for target in modmap:
        seen: set[str] = set()
        dq: deque[str] = deque([target])
        while dq:
            n = dq.popleft()
            for imp in importers.get(n, ()):
                if imp not in seen:
                    seen.add(imp)
                    dq.append(imp)
        out[target] = len(seen)
    return out


def _codeowners_patterns(path: Path) -> list[str]:
    """Explicit (non-glob-all) owner patterns, leading slash stripped."""
    patterns: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        pat = s.split()[0]
        if pat == "*":
            continue
        patterns.append(pat.lstrip("/"))
    return patterns


def _is_covered(rel_path: str, patterns: list[str]) -> bool:
    for p in patterns:
        if p == rel_path:
            return True
        if p.endswith("/") and rel_path.startswith(p):
            return True
        if not p.endswith("/") and rel_path.startswith(p + "/"):
            return True
    return False


def _measure() -> tuple[dict[str, Path], dict[str, int]]:
    repo_root = _repo_root()
    pkg_dir = repo_root / PACKAGE
    if not pkg_dir.is_dir():
        print(f"error: package directory not found: {pkg_dir}", file=sys.stderr)
        raise SystemExit(2)
    modmap = _module_map(pkg_dir, repo_root)
    importers = _direct_importers(modmap, repo_root)
    blast = _blast_radius(importers, modmap)
    return modmap, blast


def _heavy_modules(modmap: dict[str, Path], blast: dict[str, int]) -> list[str]:
    measured = {m for m, b in blast.items() if b >= BLAST_THRESHOLD}
    measured.update(m for m in REQUIRED_MODULES if m in modmap)
    return sorted(measured, key=lambda m: (-blast.get(m, 0), m))


def cmd_report(modmap: dict[str, Path], blast: dict[str, int]) -> int:
    ranked = sorted(blast.items(), key=lambda kv: (-kv[1], kv[0]))
    print(f"# measured blast radius (threshold {BLAST_THRESHOLD})")
    for mod, b in ranked[:20]:
        mark = "*" if b >= BLAST_THRESHOLD else " "
        print(f"{mark} {b:4d}  {mod}")
    return 0


def cmd_emit(modmap: dict[str, Path], blast: dict[str, int]) -> int:
    print("# Measured blast-radius owners (auto-derived; see codeowners_blast_radius.py)")
    for mod in _heavy_modules(modmap, blast):
        rel = modmap[mod].as_posix()
        print(f"/{rel:38s} @AmitabhainArunachala  # blast={blast.get(mod, 0)}")
    return 0


def cmd_check(modmap: dict[str, Path], blast: dict[str, int]) -> int:
    repo_root = _repo_root()
    co_path = repo_root / CODEOWNERS_REL
    if not co_path.is_file():
        print(f"error: {CODEOWNERS_REL} not found", file=sys.stderr)
        return 2
    patterns = _codeowners_patterns(co_path)
    missing: list[tuple[str, str, int]] = []
    for mod in _heavy_modules(modmap, blast):
        rel = modmap[mod].as_posix()
        if not _is_covered(rel, patterns):
            missing.append((mod, rel, blast.get(mod, 0)))
    if missing:
        print("FAIL: measured heavy modules missing an explicit CODEOWNERS entry:")
        for mod, rel, b in missing:
            print(f"  blast={b:4d}  {mod}  ->  add  /{rel}  @<owner>")
        print(
            "\nAdd the lines above to .github/CODEOWNERS "
            "(regenerate with --emit) so routing tracks measured coupling."
        )
        return 1
    covered = _heavy_modules(modmap, blast)
    print(f"OK: {len(covered)} measured heavy modules routed in CODEOWNERS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="fail if a heavy module is unrouted")
    group.add_argument("--report", action="store_true", help="print measured blast-radius ranking")
    group.add_argument("--emit", action="store_true", help="print CODEOWNERS lines for heavy modules")
    args = parser.parse_args(argv)

    modmap, blast = _measure()
    if args.report:
        return cmd_report(modmap, blast)
    if args.emit:
        return cmd_emit(modmap, blast)
    return cmd_check(modmap, blast)


if __name__ == "__main__":
    raise SystemExit(main())
