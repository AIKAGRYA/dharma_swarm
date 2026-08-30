"""Repo self-graph projection generator (SVAYAM-CHAKRA Wave 0).

Materializes the repository's own structural graph as deterministic,
agent-queryable projections under ``reports/self_graph/``:

- ``modules.tsv``   — one row per Python module: lines, Rule 10 budget
                      status, in/out degree, PageRank centrality, SCC id
                      and size, CODEOWNERS owner.
- ``edges.tsv``     — internal import edges (module -> module).
- ``sccs.tsv``      — strongly connected components with more than one
                      member: the circular-dependency clusters that are
                      the principled decomposition targets.
- ``refactor_targets.tsv`` — ranked refactor queue combining SCC
                      membership, centrality, and budget overrun.
- ``summary.md``    — human-readable projection with ratchet counters.
- ``self_graph.json`` — full machine payload for downstream agents.

Design laws (GOAL_SPEC SVAYAM-CHAKRA §6):
- stdlib only; must run on a bare CI runner with no repo imports
  (Tarjan SCC is implemented here in parity with
  ``dharma_swarm/catalytic_graph.py`` rather than imported, to avoid
  dragging the ``dharma_swarm.models`` dependency chain into CI).
- deterministic output (sorted rows, fixed float precision) so the
  nightly workflow can detect drift with a plain ``git diff``.
- TSV projections, never JSON, for anything concurrent writers may
  touch (Notion ratchet lesson).

Rule 10 lockstep: the grandfather baseline is parsed from
``scripts/governance/check_module_budget.py`` (the canonical gate) so
this projection can never disagree with CI about budget status.

Usage:
    python3 scripts/graph/repo_self_graph.py [--repo-root PATH]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCAN_ROOTS = ("dharma_swarm", "scripts", "api", "tests")
REFACTOR_SCOPE = ("dharma_swarm", "api")  # roots eligible as refactor targets
OUT_DIR = Path("reports/self_graph")
BUDGET_GATE = Path("scripts/governance/check_module_budget.py")
LINE_BUDGET = 1000
GROWTH_TOLERANCE = 0.10
PAGERANK_DAMPING = 0.85
PAGERANK_ITERATIONS = 50
SKIP_MARKER = re.compile(r"\bskipif\b|\bskip\(|pytest\.mark\.skip\b")
EXCLUDE_PARTS = {"__pycache__", "migrations", "dharma_swarm_old", "migration_delta"}


def iter_py_files(root: Path) -> list[Path]:
    files = []
    for scan in SCAN_ROOTS:
        base = root / scan
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if EXCLUDE_PARTS.intersection(path.parts):
                continue
            files.append(path.relative_to(root))
    return files


def module_name(rel_path: Path) -> str:
    parts = list(rel_path.parts)
    parts[-1] = parts[-1][:-3]  # strip .py
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def parse_imports(root: Path, rel_path: Path) -> set[str]:
    """Return raw imported module strings (absolute form) for one file."""
    try:
        tree = ast.parse((root / rel_path).read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    package_parts = list(rel_path.parts[:-1])
    if rel_path.name == "__init__.py":
        package_parts = list(rel_path.parts[:-1])
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                anchor = package_parts[: len(package_parts) - (node.level - 1)]
                base = ".".join(anchor + ([node.module] if node.module else []))
            if base:
                imports.add(base)
                for alias in node.names:
                    imports.add(f"{base}.{alias.name}")
    return imports


def resolve_edges(modules: dict[str, Path], raw_imports: dict[str, set[str]]) -> dict[str, set[str]]:
    """Resolve raw import strings to known internal modules."""
    known = set(modules)
    edges: dict[str, set[str]] = defaultdict(set)
    for src, imps in raw_imports.items():
        for imp in imps:
            candidate = imp
            while candidate:
                if candidate in known and candidate != src:
                    edges[src].add(candidate)
                    break
                candidate = candidate.rpartition(".")[0]
    return edges


def tarjan_scc(nodes: list[str], edges: dict[str, set[str]]) -> list[list[str]]:
    """Iterative Tarjan (parity with dharma_swarm/catalytic_graph.py)."""
    index_of: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    sccs: list[list[str]] = []
    counter = [0]

    for start in nodes:
        if start in index_of:
            continue
        work = [(start, iter(sorted(edges.get(start, ()))))]
        index_of[start] = lowlink[start] = counter[0]
        counter[0] += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, it = work[-1]
            advanced = False
            for succ in it:
                if succ not in index_of:
                    index_of[succ] = lowlink[succ] = counter[0]
                    counter[0] += 1
                    stack.append(succ)
                    on_stack.add(succ)
                    work.append((succ, iter(sorted(edges.get(succ, ())))))
                    advanced = True
                    break
                if succ in on_stack:
                    lowlink[node] = min(lowlink[node], index_of[succ])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
            if lowlink[node] == index_of[node]:
                comp = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    comp.append(member)
                    if member == node:
                        break
                sccs.append(sorted(comp))
    return sccs


def pagerank(nodes: list[str], edges: dict[str, set[str]]) -> dict[str, float]:
    n = len(nodes)
    if n == 0:
        return {}
    rank = {node: 1.0 / n for node in nodes}
    incoming: dict[str, list[str]] = defaultdict(list)
    out_degree = {node: len(edges.get(node, ())) for node in nodes}
    for src, dsts in edges.items():
        for dst in dsts:
            incoming[dst].append(src)
    for _ in range(PAGERANK_ITERATIONS):
        dangling = sum(rank[node] for node in nodes if out_degree[node] == 0)
        new_rank = {}
        for node in nodes:
            acc = sum(rank[src] / out_degree[src] for src in incoming[node])
            new_rank[node] = (1 - PAGERANK_DAMPING) / n + PAGERANK_DAMPING * (
                acc + dangling / n
            )
        rank = new_rank
    return rank


def load_grandfathered(root: Path) -> dict[str, int]:
    """Parse the GRANDFATHERED dict out of the canonical Rule 10 gate."""
    gate = root / BUDGET_GATE
    if not gate.is_file():
        return {}
    text = gate.read_text(encoding="utf-8")
    match = re.search(r"GRANDFATHERED[^=]*=\s*\{(.*?)\}", text, re.DOTALL)
    if not match:
        return {}
    entries = re.findall(r'"([^"]+)"\s*:\s*(\d+)', match.group(1))
    return {path: int(count) for path, count in entries}


def budget_status(rel_path: str, lines: int, grandfathered: dict[str, int]) -> str:
    if not rel_path.startswith(("dharma_swarm/", "api/")):
        return "out_of_scope"
    if rel_path in grandfathered:
        ceiling = int(grandfathered[rel_path] * (1 + GROWTH_TOLERANCE))
        if lines > ceiling:
            return "grandfathered_over_ceiling"
        return "grandfathered"
    if lines > LINE_BUDGET:
        return "over_budget"
    return "within_budget"


def load_codeowners(root: Path) -> list[tuple[str, str]]:
    path = root / ".github" / "CODEOWNERS"
    rules: list[tuple[str, str]] = []
    if not path.is_file():
        return rules
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            rules.append((parts[0], " ".join(parts[1:])))
    return rules


def owner_for(rel_path: str, rules: list[tuple[str, str]]) -> str:
    owner = ""
    for pattern, owners in rules:  # last match wins, per CODEOWNERS semantics
        pat = pattern.lstrip("/")
        if pat.endswith("/"):
            if rel_path.startswith(pat):
                owner = owners
        elif pat == rel_path or rel_path.startswith(pat.rstrip("*")):
            owner = owners
    return owner


def count_skips(root: Path, rel_path: Path) -> int:
    if not rel_path.parts or rel_path.parts[0] != "tests":
        return 0
    text = (root / rel_path).read_text(encoding="utf-8", errors="replace")
    return len(SKIP_MARKER.findall(text))


def write_tsv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("\t".join(header) + "\n")
        for row in rows:
            fh.write("\t".join(str(cell) for cell in row) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", type=Path)
    args = parser.parse_args()
    root = args.repo_root.resolve()

    files = iter_py_files(root)
    modules: dict[str, Path] = {}
    for rel in files:
        modules.setdefault(module_name(rel), rel)

    raw_imports = {mod: parse_imports(root, rel) for mod, rel in modules.items()}
    edges = resolve_edges(modules, raw_imports)
    node_list = sorted(modules)
    sccs = tarjan_scc(node_list, edges)
    scc_id: dict[str, int] = {}
    scc_size: dict[str, int] = {}
    multi_sccs = []
    for i, comp in enumerate(sorted(sccs, key=lambda c: (-len(c), c[0]))):
        for member in comp:
            scc_id[member] = i
            scc_size[member] = len(comp)
        if len(comp) > 1:
            multi_sccs.append((i, comp))

    ranks = pagerank(node_list, edges)
    grandfathered = load_grandfathered(root)
    owner_rules = load_codeowners(root)
    in_degree: dict[str, int] = defaultdict(int)
    for src, dsts in edges.items():
        for dst in dsts:
            in_degree[dst] += 1

    line_counts = {
        mod: sum(1 for _ in (root / rel).open(encoding="utf-8", errors="replace"))
        for mod, rel in modules.items()
    }

    module_rows = []
    for mod in node_list:
        rel = str(modules[mod])
        module_rows.append([
            mod,
            rel,
            line_counts[mod],
            budget_status(rel, line_counts[mod], grandfathered),
            in_degree.get(mod, 0),
            len(edges.get(mod, ())),
            f"{ranks.get(mod, 0.0):.8f}",
            scc_id.get(mod, -1),
            scc_size.get(mod, 1),
            count_skips(root, modules[mod]),
            owner_for(rel, owner_rules),
        ])

    edge_rows = sorted(
        [src, dst] for src, dsts in edges.items() for dst in dsts
    )
    scc_rows = [
        [i, len(comp), ";".join(comp)] for i, comp in multi_sccs
    ]

    # Refactor queue: rank = normalized(centrality) + budget pressure + SCC entanglement.
    max_rank = max((ranks.get(m, 0.0) for m in node_list), default=1.0) or 1.0
    targets = []
    for mod in node_list:
        rel = str(modules[mod])
        if not rel.startswith(tuple(f"{r}/" for r in REFACTOR_SCOPE)):
            continue
        status = budget_status(rel, line_counts[mod], grandfathered)
        budget_pressure = max(0.0, (line_counts[mod] - LINE_BUDGET) / LINE_BUDGET)
        entanglement = scc_size.get(mod, 1) - 1
        score = (
            ranks.get(mod, 0.0) / max_rank
            + budget_pressure
            + 0.5 * entanglement
        )
        if score > 0.25:
            targets.append([
                f"{score:.4f}", mod, rel, line_counts[mod], status,
                scc_size.get(mod, 1), f"{ranks.get(mod, 0.0):.8f}",
            ])
    targets.sort(key=lambda r: (-float(r[0]), r[1]))

    out = root / OUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    write_tsv(out / "modules.tsv",
              ["module", "path", "lines", "budget_status", "in_degree",
               "out_degree", "pagerank", "scc_id", "scc_size", "test_skips",
               "owner"],
              module_rows)
    write_tsv(out / "edges.tsv", ["src", "dst"], edge_rows)
    write_tsv(out / "sccs.tsv", ["scc_id", "size", "members"], scc_rows)
    write_tsv(out / "refactor_targets.tsv",
              ["score", "module", "path", "lines", "budget_status",
               "scc_size", "pagerank"],
              targets[:50])

    over_budget = sum(1 for r in module_rows if r[3] in ("over_budget", "grandfathered_over_ceiling"))
    grandfathered_count = sum(1 for r in module_rows if str(r[3]).startswith("grandfathered"))
    skip_total = sum(int(r[9]) for r in module_rows)
    payload = {
        "schema_version": 1,
        "generated_by": "scripts/graph/repo_self_graph.py",
        "node_count": len(node_list),
        "edge_count": len(edge_rows),
        "scc_multi_count": len(multi_sccs),
        "largest_scc": max((len(c) for _, c in multi_sccs), default=1),
        "over_budget_modules": over_budget,
        "grandfathered_modules": grandfathered_count,
        "test_skip_markers": skip_total,
        "top_refactor_targets": [row[1] for row in targets[:10]],
    }
    (out / "self_graph.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines_md = [
        "# Repo Self-Graph — generated projection",
        "",
        "Generated by `scripts/graph/repo_self_graph.py` (SVAYAM-CHAKRA Wave 0).",
        f"Data date: {generated}. Do not edit by hand; regenerate instead.",
        "",
        "## Ratchet counters",
        "",
        f"- Python modules scanned: **{len(node_list)}**",
        f"- Internal import edges: **{len(edge_rows)}**",
        f"- Circular-dependency clusters (SCC > 1): **{len(multi_sccs)}**"
        f" (largest: {payload['largest_scc']} modules)",
        f"- Modules over Rule 10 budget (incl. over-ceiling grandfathers): **{over_budget}**",
        f"- Grandfathered modules: **{grandfathered_count}**",
        f"- Test skip markers: **{skip_total}**",
        "",
        "## Top refactor targets (SCC + centrality + budget)",
        "",
        "| score | module | lines | budget | scc_size |",
        "|---|---|---|---|---|",
    ]
    for row in targets[:15]:
        lines_md.append(f"| {row[0]} | `{row[1]}` | {row[3]} | {row[4]} | {row[5]} |")
    lines_md += [
        "",
        "Full projections: `modules.tsv`, `edges.tsv`, `sccs.tsv`,",
        "`refactor_targets.tsv`, `self_graph.json` in this directory.",
        "",
    ]
    (out / "summary.md").write_text("\n".join(lines_md), encoding="utf-8")

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
