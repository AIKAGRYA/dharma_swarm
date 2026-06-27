#!/usr/bin/env python3
"""Pramāṇa Probe — runner (v0.0.1).

The answer to the adversarial review: stop trusting the markdown, RUN it. Each
subcommand executes a prompt's *named ground-truth instrument* and prints the
demo table, so any "Demonstration run" can be regenerated and verified — not
believed. This is the anti-slop product made non-hypocritical.

    python3 slop_probe.py complexity --path dharma_swarm   # radon cc (top + counts)
    python3 slop_probe.py cycles     --path dharma_swarm   # AST + Tarjan SCC (load-time)
    python3 slop_probe.py slop-index --path dharma_swarm   # composite, scope-disclosed

Exit code is non-zero when a RED signal is present, so it can gate CI.
Only stdlib + (optionally) radon for `complexity`. Honest when a tool is absent.
"""
from __future__ import annotations

import argparse
import ast
import shutil
import subprocess
import sys
from pathlib import Path


def _py_files(root: Path):
    return [p for p in root.rglob("*.py") if ".venv" not in p.parts]


# --- complexity: route to radon (the named tool), not a homemade proxy --------
def complexity(root: Path) -> int:
    if shutil.which("radon") is None:
        print("UNASSESSED — radon not installed. `pip install radon` (≈3s) then re-run.")
        print("Do NOT substitute a homemade AST proxy — that is the cardinal sin.")
        return 2
    out = subprocess.run(
        ["radon", "cc", str(root), "-s", "-n", "D"], capture_output=True, text=True
    ).stdout
    rows = []  # (cc, "file:line name")
    cur = ""
    for line in out.splitlines():
        if not line.startswith(" "):
            cur = line.strip()
            continue
        s = line.strip()
        if " - " in s and "(" in s:
            try:
                cc = int(s.rsplit("(", 1)[1].rstrip(")"))
            except ValueError:
                continue
            name = s.split(" - ")[0]
            rows.append((cc, f"{cur}:{name}"))
    total = subprocess.run(["radon", "cc", str(root)], capture_output=True, text=True).stdout
    n_funcs = sum(1 for ln in total.splitlines() if ln.lstrip().startswith(("F ", "M ", "C ")))
    over20 = sum(1 for cc, _ in rows if cc > 20)
    rows.sort(reverse=True)
    print(f"complexity (radon cc) — {n_funcs} functions, {over20} with cc>20 (grade D+)")
    for cc, loc in rows[:8]:
        print(f"  cc {cc:>4}  {loc}")
    worst = rows[0][0] if rows else 0
    return 1 if worst > 50 else 0  # RED if a function exceeds cc 50


# --- cycles: AST import graph + Tarjan SCC, TYPE_CHECKING excluded -------------
def _is_typecheck(test) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def cycles(root: Path) -> int:
    pkg = root.name
    mods = {}
    for p in _py_files(root):
        parts = list(p.with_suffix("").parts)
        parts = parts[parts.index(pkg):]
        if parts[-1] == "__init__":
            parts = parts[:-1]
        mods[".".join(parts)] = p
    names = set(mods)

    def resolve(m, level, base):
        if level == 0:
            return m
        b = base[: len(base) - (level - 1)] if level > 1 else base
        return ".".join(b + ([m] if m else []))

    edges: dict[str, set] = {}

    class V(ast.NodeVisitor):
        def __init__(self, m):
            self.m = m
            self.base = m.split(".")
            self.depth = 0

        def _vf(self, n):
            self.depth += 1
            self.generic_visit(n)
            self.depth -= 1

        visit_FunctionDef = _vf
        visit_AsyncFunctionDef = _vf

        def visit_If(self, n):
            if _is_typecheck(n.test):
                for s in n.orelse:
                    self.visit(s)
                return
            self.generic_visit(n)

        def _add(self, t):
            if t in names and t != self.m and self.depth == 0:
                edges.setdefault(self.m, set()).add(t)

        def visit_Import(self, n):
            for a in n.names:
                self._add(a.name)

        def visit_ImportFrom(self, n):
            tgt = resolve(n.module or "", n.level, self.base)
            self._add(tgt)
            for a in n.names:
                self._add(f"{tgt}.{a.name}")

    for m, p in mods.items():
        try:
            V(m).visit(ast.parse(p.read_text(encoding="utf-8")))
        except SyntaxError:
            continue

    index, low, on, stack, idx, sccs = {}, {}, {}, [], [0], []
    sys.setrecursionlimit(50000)

    def sc(v):
        index[v] = low[v] = idx[0]
        idx[0] += 1
        stack.append(v)
        on[v] = True
        for w in edges.get(v, ()):
            if w not in index:
                sc(w)
                low[v] = min(low[v], low[w])
            elif on.get(w):
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on[w] = False
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                sccs.append(comp)

    for v in list(edges):
        if v not in index:
            sc(v)
    print(f"cycles (AST+Tarjan, TYPE_CHECKING excluded) — {len(mods)} modules")
    print(f"  load-time cyclic SCCs: {len(sccs)}")
    for c in sorted(sccs, key=len, reverse=True):
        print(f"    size {len(c)}: {', '.join(sorted(x.split('.')[-1] for x in c))}")
    return 1 if sccs else 0  # RED if any load-time cycle


def slop_index(root: Path) -> int:
    print("=== slop-index composite (scope disclosed per signal) ===")
    over3000 = sum(1 for p in _py_files(root) if len(p.read_text(errors='ignore').splitlines()) > 3000)
    wild = sum(
        1
        for p in _py_files(root)
        for ln in p.read_text(errors="ignore").splitlines()
        if ln.strip().startswith("from ") and ln.strip().endswith("import *")
    )
    print(f"  god objects (>3000 ln) [{root}/]:        {over3000}   {'🔴' if over3000 else '🟢'}")
    print(f"  wildcard imports        [{root}/]:        {wild}   {'🔴' if wild else '🟢'}")
    print("  complexity / cycles: run `complexity` and `cycles` subcommands (radon/Tarjan)")
    print("  NOTE: only god-objects + silent-swallows are ratchet-gated today (2 of 8).")
    return 1 if (over3000 or wild) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Pramāṇa Probe runner — run the instrument, don't trust the prose.")
    ap.add_argument("cmd", choices=["complexity", "cycles", "slop-index"])
    ap.add_argument("--path", default="dharma_swarm")
    a = ap.parse_args(argv)
    root = Path(a.path)
    if not root.exists():
        print(f"path not found: {root}", file=sys.stderr)
        return 2
    return {"complexity": complexity, "cycles": cycles, "slop-index": slop_index}[a.cmd](root)


if __name__ == "__main__":
    raise SystemExit(main())
