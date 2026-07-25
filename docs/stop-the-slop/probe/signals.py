"""Signal implementations. Each routes to a real instrument and returns a
SignalResult carrying the confidence it actually earned. If the named instrument
is absent and no faithful proxy exists, the signal returns UNASSESSED — it never
fabricates a verdict to fill the row. That refusal is the whole product.
"""

from __future__ import annotations

import ast
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from _common import (
    SOURCE_EXTS, Confidence, Grade, SignalResult, git, iter_py_files,
    iter_source_files, parse, run_json, tool_path,
)

# Source extensions whose stems we treat as "code files" for language-agnostic
# signals (god objects by line count, co-change coupling). Excludes header-only
# and markup so the denominator stays meaningful.
_CODE_EXTS = tuple(sorted(set(SOURCE_EXTS)))


def _no_python(root: Path, signal: str, confirm_with: str, instrument: str) -> SignalResult:
    """Uniform UNASSESSED for a Python-AST signal pointed at a tree with no .py
    sources. The distinction from GREEN is the whole point: GREEN means the
    instrument ran and found nothing; UNASSESSED means the instrument could not
    run here at all. A Python-AST probe must never report a Go/Rust repo as
    'clean' — that would be manufacturing the exact false verdict the library
    exists to prevent."""
    return SignalResult(
        signal=signal,
        measured="UNASSESSED (no .py sources at this path)",
        grade=Grade.UNASSESSED, confidence=Confidence.UNASSESSED,
        confirm_with=confirm_with,
        scope=f"{root}/ (0 Python files; this instrument is Python-only)",
        pressure=0.0,
        instrument=instrument,
    )


GOD_OBJECT_LINES = 3000        # Parnas/SRP: a module with one reason to change stays small
COMPLEXITY_THRESHOLD = 20      # McCabe: above this a function is a test-coverage liability
COUPLING_HOTSPOT = 8           # Martin: below this max fan-in there is no coupling hotspot

# Set by the CLI (--online). Hermetic by default: an offline run must never
# *claim* a phantom verdict it can only confirm against a live index.
ONLINE = False

# import-name -> PyPI dist-name aliases (the known blind spot of name-based checks).
# Not exhaustive; it exists so the common cases don't generate false phantoms.
_IMPORT_DIST_ALIASES = {
    "cv2": "opencv-python", "sklearn": "scikit-learn", "PIL": "pillow",
    "yaml": "pyyaml", "bs4": "beautifulsoup4", "dotenv": "python-dotenv",
    "jwt": "pyjwt", "dateutil": "python-dateutil", "google": "google-api-python-client",
    "redis": "redis", "fitz": "pymupdf", "OpenSSL": "pyopenssl",
}


# --------------------------------------------------------------------------- #
# 1. God objects (Parnas / SRP) — AST line count, HIGH confidence.
# --------------------------------------------------------------------------- #
def god_objects(root: Path) -> SignalResult:
    # Language-agnostic: a 3000-line file is a god object in Python, Go, or Rust
    # alike. Route over every source language present, not just .py — this is one
    # of the few signals whose instrument (line count) genuinely travels.
    files = iter_source_files(root)
    if not files:
        return SignalResult(
            signal="God objects",
            measured="UNASSESSED (no source files at this path)",
            grade=Grade.UNASSESSED, confidence=Confidence.UNASSESSED,
            confirm_with="point the probe at a source tree",
            scope=f"{root}/ (0 recognized source files)",
            pressure=0.0, instrument="line-count",
        )
    sizes = []
    for f in files:
        try:
            n = sum(1 for _ in f.open("r", encoding="utf-8", errors="replace"))
        except OSError:
            continue
        sizes.append((n, f))
    big = sorted((s for s in sizes if s[0] >= GOD_OBJECT_LINES), reverse=True)
    worst = big[0][0] if big else 0
    langs = sorted({f.suffix for _, f in sizes})
    grade = Grade.RED if len(big) >= 3 else Grade.AMBER if big else Grade.GREEN
    return SignalResult(
        signal="God objects",
        measured=f"{len(big)} files \u2265{GOD_OBJECT_LINES} ln" + (f" (max {worst:,})" if big else ""),
        grade=grade, confidence=Confidence.HIGH,
        confirm_with="wc -l on the listed files",
        scope=f"{root}/ ({len(sizes):,} source files [{', '.join(langs)}], deps excluded)",
        pressure=min(1.0, len(big) / 8),
        instrument="line-count (language-agnostic)",
        count=len(big),
        detail=[f"{n:>6}  {f.relative_to(root)}" for n, f in big[:8]],
    )


# --------------------------------------------------------------------------- #
# 2. Complexity inflation (McCabe) — route to radon; refuse to proxy silently.
# --------------------------------------------------------------------------- #
def complexity(root: Path) -> SignalResult:
    if not iter_py_files(root):
        return _no_python(root, "Complexity inflation",
                          "gocyclo (Go) / rust-code-analysis (Rust) / lizard (multi-lang)",
                          "radon is Python-only — not run")
    radon = tool_path("radon")
    if radon:
        data = run_json([radon, "cc", "-s", "-j", str(root)])
        if data is not None:
            rows = []
            for fpath, items in data.items():
                if isinstance(items, dict) and items.get("error"):
                    continue
                for v in items:
                    rows.append((v["complexity"], f"{fpath}:{v['lineno']}", v["name"]))
            rows.sort(reverse=True)
            over = [r for r in rows if r[0] > COMPLEXITY_THRESHOLD]
            worst = rows[0] if rows else (0, "", "")
            grade = Grade.RED if len(over) >= 50 else Grade.AMBER if over else Grade.GREEN
            return SignalResult(
                signal="Complexity inflation",
                measured=f"{len(over)} fns cc>{COMPLEXITY_THRESHOLD}; worst cc={worst[0]} ({worst[2]} @ {worst[1]})",
                grade=grade, confidence=Confidence.HIGH,
                confirm_with="radon cc -n D",
                scope=f"{len(rows):,} functions in {root}/",
                pressure=min(1.0, len(over) / 100),
                instrument=f"radon {_radon_version(radon)}",
                count=len(over),
                detail=[f"cc={c:>4}  {name}  @ {loc}" for c, loc, name in rows[:10]],
            )
    # radon absent: an AST branch-count proxy disagrees with radon (it cannot see
    # cognitive nuance and miscounts dispatch) — so it is explicitly LOW, and the
    # row says "confirm with radon" rather than crowning a winner.
    counts = _ast_branch_counts(root)
    over = [c for c in counts if c[0] > COMPLEXITY_THRESHOLD]
    worst = counts[0] if counts else (0, "", "")
    return SignalResult(
        signal="Complexity inflation",
        measured=f"~{len(over)} fns branch-count>{COMPLEXITY_THRESHOLD} (PROXY; worst ~{worst[0]} {worst[2]})",
        grade=Grade.AMBER, confidence=Confidence.LOW,
        confirm_with="radon cc (pip install radon) \u2014 proxy miscounts dispatch",
        scope=f"{len(counts):,} functions in {root}/",
        pressure=min(1.0, len(over) / 100),
        instrument="AST branch-count proxy (radon ABSENT)",
        count=len(over),
        detail=[f"~{c:>4}  {name}  @ {loc}" for c, loc, name in counts[:10]],
    )


def _radon_version(radon: str) -> str:
    import subprocess
    try:
        return subprocess.check_output([radon, "--version"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "?"


def _ast_branch_counts(root: Path):
    rows = []
    branch = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.BoolOp,
              ast.IfExp, ast.comprehension, ast.ExceptHandler)
    for f in iter_py_files(root):
        tree = parse(f)
        if not tree:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                c = 1 + sum(1 for n in ast.walk(node) if isinstance(n, branch))
                rows.append((c, f"{f}:{node.lineno}", node.name))
    rows.sort(reverse=True)
    return rows


# --------------------------------------------------------------------------- #
# 3. Wildcard imports (Parnas — explicit interfaces) — AST, HIGH, return-clean.
# --------------------------------------------------------------------------- #
def wildcard_imports(root: Path) -> SignalResult:
    if not iter_py_files(root):
        return _no_python(root, "Wildcard imports",
                          "language-specific import linter", "AST is Python-only — not run")
    hits = []
    for f in iter_py_files(root):
        tree = parse(f)
        if not tree:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                hits.append(f"{f.relative_to(root)}:{node.lineno}  from {node.module or '.'} import *")
    return SignalResult(
        signal="Wildcard imports",
        measured=str(len(hits)),
        grade=Grade.GREEN if not hits else Grade.RED,
        confidence=Confidence.HIGH,
        confirm_with="grep -rn 'import \\*'",
        scope=f"{root}/ (.py, deps excluded)",
        pressure=min(1.0, len(hits) / 20),
        instrument="AST",
        count=len(hits),
        detail=hits[:10],
    )


# --------------------------------------------------------------------------- #
# 4/5. Silent swallows & broad catches (Goodenough — an error is information).
# --------------------------------------------------------------------------- #
def _except_stats(root: Path):
    silent = 0
    broad = 0
    silent_locs, broad_locs = [], []
    for f in iter_py_files(root):
        tree = parse(f)
        if not tree:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            body = node.body
            is_silent = len(body) == 1 and isinstance(body[0], ast.Pass)
            t = node.type
            is_broad = t is None or (isinstance(t, ast.Name) and t.id in {"Exception", "BaseException"})
            if is_silent:
                silent += 1
                silent_locs.append(f"{f.relative_to(root)}:{node.lineno}")
            if is_broad:
                broad += 1
                broad_locs.append(f"{f.relative_to(root)}:{node.lineno}")
    return silent, broad, silent_locs, broad_locs


def silent_swallows(root: Path) -> SignalResult:
    if not iter_py_files(root):
        return _no_python(root, "Silent swallows",
                          "language-specific error-handling lint", "AST is Python-only — not run")
    silent, _broad, locs, _ = _except_stats(root)
    return SignalResult(
        signal="Silent swallows",
        measured=f"{silent} (except\u2026: pass)",
        grade=Grade.RED if silent >= 100 else Grade.AMBER if silent else Grade.GREEN,
        confidence=Confidence.HIGH,
        confirm_with="ratchet silent_exception_swallows",
        scope=f"{root}/",
        pressure=min(1.0, silent / 300),
        instrument="AST (ExceptHandler with sole Pass)",
        count=silent,
        detail=locs[:8],
    )


def broad_catches(root: Path) -> SignalResult:
    if not iter_py_files(root):
        return _no_python(root, "Broad catches",
                          "language-specific error-handling lint", "AST is Python-only — not run")
    _silent, broad, _, locs = _except_stats(root)
    return SignalResult(
        signal="Broad catches",
        measured=f"{broad} (except Exception/bare)",
        # zero broad catches is genuinely clean (return-clean); any present are
        # AMBER not RED, because broad-but-logged-and-re-raised is legitimate and
        # needs review, not an auto-fail.
        grade=Grade.GREEN if broad == 0 else Grade.AMBER,
        confidence=Confidence.HIGH,
        confirm_with="review each for log + re-raise vs swallow",
        scope=f"{root}/",
        pressure=min(1.0, broad / 3000),
        instrument="AST (ExceptHandler type in {Exception,BaseException,None})",
        count=broad,
        detail=locs[:8],
    )


# --------------------------------------------------------------------------- #
# 6. Coupling hotspots (Parnas / Martin instability) — static import graph.
# --------------------------------------------------------------------------- #
def coupling(root: Path) -> SignalResult:
    if not iter_py_files(root):
        return _no_python(root, "Coupling",
                          "language-specific import graph (e.g. go list, cargo-modules)",
                          "AST import graph is Python-only — not run")
    pkg = root.name
    fan_out: dict[str, set[str]] = defaultdict(set)
    fan_in: Counter = Counter()
    mods = {}
    for f in iter_py_files(root):
        mod = ".".join(f.relative_to(root.parent).with_suffix("").parts)
        mods[f] = mod
    for f, mod in mods.items():
        tree = parse(f)
        if not tree:
            continue
        for node in ast.walk(tree):
            target = None
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(pkg):
                target = node.module
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith(pkg):
                        target = a.name
            if target:
                fan_out[mod].add(target)
                fan_in[target] += 1
    top_in = fan_in.most_common(1)
    top_out = max(((len(v), k) for k, v in fan_out.items()), default=(0, ""))
    max_in = top_in[0][1] if top_in else 0
    measured = (f"max fan-in {max_in} "
                f"({top_in[0][0].split('.')[-1] if top_in else '-'}); "
                f"max fan-out {top_out[0]} ({top_out[1].split('.')[-1]})")
    # GREEN floor: a module set with no coupling hotspot is genuinely clean on
    # this axis — coupling must be allowed to return clean, not pinned at AMBER
    # forever (a signal that can never say GREEN is the "always finds something"
    # smell this library exists to kill). The ceiling stays AMBER, never RED:
    # static fan-in is a lead to confirm with a real import graph, not a verdict.
    grade = Grade.GREEN if max_in < COUPLING_HOTSPOT else Grade.AMBER
    return SignalResult(
        signal="Coupling",
        measured=measured,
        grade=grade,
        confidence=Confidence.MEDIUM,   # static imports only; dynamic wiring invisible
        confirm_with="grimp / pydeps import graph",
        scope=f"intra-{pkg} import edges (static)",
        pressure=min(1.0, (top_in[0][1] if top_in else 0) / 150),
        instrument="AST import graph",
        count=max_in,
        detail=[f"fan-in {c:>4}  {m}" for m, c in fan_in.most_common(6)],
    )


# --------------------------------------------------------------------------- #
# 7. Dead code (Aho–Sethi–Ullman reachability) — vulture if present, else honest.
# --------------------------------------------------------------------------- #
def dead_code(root: Path) -> SignalResult:
    if not iter_py_files(root):
        return _no_python(root, "Dead code",
                          "language-specific dead-code analysis (e.g. staticcheck, cargo-udeps)",
                          "vulture is Python-only — not run")
    vulture = tool_path("vulture")
    if vulture:
        import subprocess
        try:
            out = subprocess.run([vulture, str(root), "--min-confidence", "80"],
                                 capture_output=True, text=True, timeout=180).stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            out = ""
        n = sum(1 for ln in out.splitlines() if ln.strip())
        return SignalResult(
            signal="Dead code",
            measured=f"{n} items (vulture \u226580%)",
            grade=Grade.AMBER if n else Grade.GREEN,
            confidence=Confidence.MEDIUM,   # dynamic/string refs defeat static reachability
            confirm_with="vulture + string-ref grep before delete",
            scope=f"{root}/",
            pressure=min(1.0, n / 200),
            instrument="vulture",
            count=n,
            detail=out.splitlines()[:8],
        )
    return SignalResult(
        signal="Dead code",
        measured="UNASSESSED (vulture absent)",
        grade=Grade.UNASSESSED, confidence=Confidence.UNASSESSED,
        confirm_with="pip install vulture; then re-run",
        scope=f"{root}/",
        pressure=0.0,
        instrument="(none \u2014 vulture ABSENT, no faithful proxy)",
    )


# --------------------------------------------------------------------------- #
# 8. Churn / revert (Lehman evolution) — git history, HIGH where history exists.
# --------------------------------------------------------------------------- #
def churn(root: Path, days: int = 90) -> SignalResult:
    log = git(["log", f"--since={days} days ago", "--pretty=%H%x09%s"], root)
    if not log.strip():
        return SignalResult(
            signal="Churn/revert", measured="UNASSESSED (no git history in window)",
            grade=Grade.UNASSESSED, confidence=Confidence.UNASSESSED,
            confirm_with="git log --since", scope=f"last {days}d", pressure=0.0,
            instrument="(none)")
    commits = [ln for ln in log.splitlines() if ln.strip()]
    reverts = [ln for ln in commits if re.search(r"\brevert\b|^Revert ", ln.split("\t", 1)[-1], re.I)]
    rate = len(reverts) / max(1, len(commits))
    return SignalResult(
        signal="Churn/revert",
        measured=f"{len(reverts)}/{len(commits)} commits are reverts ({rate:.1%}) in {days}d",
        grade=Grade.RED if rate > 0.05 else Grade.AMBER if rate > 0.01 else Grade.GREEN,
        confidence=Confidence.HIGH,
        confirm_with="git log --grep=revert --since",
        scope=f"whole repo, last {days}d",
        pressure=min(1.0, rate / 0.1),
        instrument="git log",
        count=len(reverts),
        detail=[ln.split('\t', 1)[-1][:80] for ln in reverts[:6]],
    )


# --------------------------------------------------------------------------- #
# 9. Import cycles (Tarjan SCC) — load-time vs lazy. HIGH: a found cycle is real.
#   The static import graph can only UNDER-count edges (dynamic imports are
#   invisible), so every SCC it reports is a genuine cycle — no false positives.
#   Load-time cycles (module-level imports) are the dangerous ones: they can
#   deadlock import or force partial-module states. Lazy (function-local) edges
#   break the cycle at import time and are reported separately.
# --------------------------------------------------------------------------- #
def _module_name(f: Path, root: Path) -> str:
    rel = f.relative_to(root.parent).with_suffix("")
    parts = [p for p in rel.parts if p != "__init__"]
    return ".".join(parts)


def _import_edges(root: Path) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return (load_time_edges, all_edges) over intra-package modules."""
    pkg = root.name
    names: dict[Path, str] = {f: _module_name(f, root) for f in iter_py_files(root)}
    known = set(names.values())
    load: dict[str, set[str]] = defaultdict(set)
    alle: dict[str, set[str]] = defaultdict(set)

    def targets(node: ast.AST) -> list[str]:
        out = []
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(pkg):
            out.append(node.module)
            # `from pkg import sub` names the package as module and the submodule
            # as an imported name — resolve `pkg.sub` so the edge isn't missed.
            out += [f"{node.module}.{a.name}" for a in node.names]
        elif isinstance(node, ast.Import):
            out += [a.name for a in node.names if a.name.startswith(pkg)]
        return out

    def nearest(t: str) -> str | None:
        # map an import target onto a known module (exact, or its package head)
        if t in known:
            return t
        while "." in t:
            t = t.rsplit(".", 1)[0]
            if t in known:
                return t
        return None

    def is_type_checking(test: ast.AST) -> bool:
        # `if TYPE_CHECKING:` / `if typing.TYPE_CHECKING:` blocks never execute at
        # runtime, so their imports are type-only edges — not load-time ones.
        return ((isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
                or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"))

    for f, mod in names.items():
        tree = parse(f)
        if not tree:
            continue
        # walk tracking (inside def/lambda) and (inside TYPE_CHECKING) so we can
        # split load-time edges from lazy and type-only ones.
        def visit(node: ast.AST, in_func: bool, type_only: bool) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.If) and is_type_checking(child.test):
                    for n in child.body:
                        visit(n, in_func, True)
                    for n in child.orelse:
                        visit(n, in_func, type_only)
                    continue
                deeper = in_func or isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    for t in targets(child):
                        m = nearest(t)
                        if m and m != mod:
                            alle[mod].add(m)
                            if not in_func and not type_only:
                                load[mod].add(m)
                visit(child, deeper, type_only)
        visit(tree, False, False)
    return load, alle


def _tarjan(edges: dict[str, set[str]]) -> list[list[str]]:
    """Iterative Tarjan SCC. Returns SCCs of size>1 (true cycles), largest first."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    sccs: list[list[str]] = []
    counter = 0
    nodes = set(edges) | {t for ts in edges.values() for t in ts}

    for start in nodes:
        if start in index:
            continue
        work = [(start, iter(sorted(edges.get(start, ()))))]
        index[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter
                    counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(sorted(edges.get(nxt, ())))))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == node:
                        break
                if len(comp) > 1:
                    sccs.append(sorted(comp))
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
    sccs.sort(key=len, reverse=True)
    return sccs


def cycles(root: Path) -> SignalResult:
    if not iter_py_files(root):
        return _no_python(root, "Import cycles",
                          "language-specific cycle check (go vet, cargo-modules)",
                          "AST import graph + Tarjan is Python-only — not run")
    load, alle = _import_edges(root)
    scc_all = _tarjan(alle)
    scc_load = _tarjan(load)
    n_all, n_load = len(scc_all), len(scc_load)
    biggest_load = scc_load[0] if scc_load else []
    measured = (f"{n_load} load-time cyclic SCC(s); {n_all} total cyclic SCC(s)"
                + (f"; largest load-time = {len(biggest_load)} modules" if biggest_load else ""))
    grade = Grade.RED if n_load else Grade.AMBER if n_all else Grade.GREEN
    detail = []
    for comp in scc_load[:3]:
        detail.append("LOAD-TIME: " + " \u2192 ".join(m.split(".")[-1] for m in comp))
    for comp in scc_all[:5 - len(detail)]:
        if comp not in scc_load:
            detail.append("lazy-broken: " + ", ".join(m.split(".")[-1] for m in comp[:6]))
    return SignalResult(
        signal="Import cycles",
        measured=measured,
        grade=grade,
        confidence=Confidence.HIGH,   # a statically-found cycle is a real cycle
        confirm_with="grimp / import-linter contract",
        scope=f"intra-{root.name} import graph ({len(alle)} modules with edges)",
        pressure=min(1.0, n_load / 2 + n_all / 20),
        instrument="AST import graph + Tarjan SCC",
        count=n_all,
        detail=detail,
    )


# --------------------------------------------------------------------------- #
# 10. Duplication (copy-paste convergence) — clone CLUSTERS, not text diff.
#   Instrument: AST function/method body hashing (docstring-stripped, decorator-
#   and-signature-independent). This is a real Type-1 clone detector — identical
#   logic clusters even across different enclosing classes. Its structural blind
#   spot is Type-2/3 (renamed-variable / near-miss) clones, which only a token
#   detector like jscpd/pmd-cpd sees — hence MEDIUM, not HIGH, and jscpd is the
#   named confirm. Copy-paste convergence is a core AI-slop tell: models
#   regenerate near-identical bodies instead of factoring a shared helper.
# --------------------------------------------------------------------------- #
def _func_body_key(node: ast.AST) -> tuple[str, int] | None:
    """A structural key for a function/method body, docstring stripped. Returns
    (key, n_statements) or None for trivially-short bodies not worth clustering."""
    body = list(getattr(node, "body", []))
    if body and isinstance(body[0], ast.Expr) and isinstance(
            getattr(body[0], "value", None), ast.Constant) and isinstance(
            body[0].value.value, str):
        body = body[1:]  # drop docstring
    if len(body) < 3:
        return None
    dump = "\n".join(ast.dump(b, annotate_fields=False) for b in body)
    if len(dump) < 160:  # skip trivial getters/setters/passthroughs
        return None
    return dump, len(body)


def duplication(root: Path) -> SignalResult:
    if not iter_py_files(root):
        return _no_python(root, "Duplication",
                          "jscpd / pmd-cpd (multi-language token clone detectors)",
                          "AST body-hashing is Python-only — not run")
    import hashlib
    # hash -> list of (qualname, file:line)
    clusters: dict[str, list[str]] = defaultdict(list)
    total_funcs = 0
    for f in iter_py_files(root):
        tree = parse(f)
        if not tree:
            continue
        rel = str(f.relative_to(root))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total_funcs += 1
                key = _func_body_key(node)
                if key is None:
                    continue
                h = hashlib.blake2b(key[0].encode(), digest_size=16).hexdigest()
                clusters[h].append(f"{node.name} @ {rel}:{node.lineno}")
    dup_clusters = {h: locs for h, locs in clusters.items() if len(locs) > 1}
    n_clusters = len(dup_clusters)
    cloned_funcs = sum(len(locs) - 1 for locs in dup_clusters.values())
    ratio = cloned_funcs / max(1, total_funcs)
    grade = (Grade.RED if ratio >= 0.03 else Grade.AMBER if n_clusters else Grade.GREEN)
    detail = []
    for locs in sorted(dup_clusters.values(), key=len, reverse=True)[:6]:
        name = locs[0].split(" @ ")[0]
        detail.append(f"{len(locs)}x  {name}  ({locs[0].split(' @ ')[1]} == {locs[1].split(' @ ')[1]})")
    return SignalResult(
        signal="Duplication",
        measured=(f"{n_clusters} clone clusters; {cloned_funcs} cloned fns "
                  f"({ratio:.1%} of {total_funcs:,})"),
        grade=grade,
        confidence=Confidence.MEDIUM,   # Type-1 exact bodies; Type-2/3 need jscpd
        confirm_with="jscpd / pmd-cpd for Type-2/3 (renamed/near-miss) clones",
        scope=f"{root}/ ({total_funcs:,} functions)",
        pressure=min(1.0, cloned_funcs / 150),
        instrument="AST function-body hashing (Type-1)",
        count=cloned_funcs,
        detail=detail,
    )


# --------------------------------------------------------------------------- #
# NEW DIMENSION A — Phantom dependencies / slopsquatting surface.
#   LLMs hallucinate import names at 5–21% (Spracklen et al.); attackers
#   pre-register them. Ground truth: does every imported top-level name resolve
#   to the stdlib or an installed distribution? Unresolved = audit-before-install.
# --------------------------------------------------------------------------- #
def phantom_deps(root: Path) -> SignalResult:
    if not iter_py_files(root):
        return _no_python(root, "Phantom deps",
                          "language-specific dependency resolver (e.g. cargo, go mod)",
                          "Python import resolution is Python-only — not run")
    import importlib.metadata as im
    # Build the set of importable top-level names provided by installed dists.
    provided: set[str] = set(sys.stdlib_module_names)
    try:
        mapping = im.packages_distributions()  # top-level module -> [dist,...]
        provided |= set(mapping.keys())
    except Exception as e:  # noqa: BLE001 — best-effort enrichment, surfaced not swallowed
        print(f"phantom_deps: packages_distributions() unavailable ({e!r}); "
              "proceeding with stdlib-only provider set", file=sys.stderr)
    # First-party names importable from within the repo: every package dir and
    # every module stem anywhere in the tree (repos routinely insert subdirs onto
    # sys.path, so a nested module name can be imported top-level). Missing these
    # is what turns a local module into a false "phantom".
    repo_root = root.parent
    for f in iter_py_files(repo_root):
        provided.add(f.stem)
        if (f.parent / "__init__.py").exists():
            provided.add(f.parent.name)
    provided.add(root.name)

    unresolved: dict[str, list[str]] = defaultdict(list)
    for f in iter_py_files(root):
        tree = parse(f)
        if not tree:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    _maybe_unresolved(a.name.split(".")[0], provided, unresolved, f, node, root)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                _maybe_unresolved(node.module.split(".")[0], provided, unresolved, f, node, root)

    names = sorted(unresolved)
    n = len(names)
    if not ONLINE:
        # Offline: we found imports we can't resolve locally, but "unresolved" is
        # NOT "hallucinated" — most are real, uninstalled optional deps. Refuse to
        # call them phantom without the ground truth (PyPI). LOW, not RED.
        return SignalResult(
            signal="Phantom deps",
            measured=f"{n} unresolved imports (NOT phantom-confirmed \u2014 run --online)",
            grade=Grade.AMBER if n else Grade.GREEN,
            confidence=Confidence.LOW,
            confirm_with="re-run with --online (checks PyPI existence) or pip show <name>",
            scope=f"{root}/ top-level imports not in stdlib/installed/first-party",
            pressure=0.0,   # an unconfirmed candidate must not drive the composite
            instrument="local resolution only (PyPI NOT queried)",
            count=n,
            detail=[f"{name}  \u2190 {unresolved[name][0]}" for name in names[:10]],
        )
    # Online: PyPI is the ground truth for existence. A name that 404s (after
    # alias normalization) is a genuine phantom candidate — the slopsquatting risk.
    phantom, real = [], []
    for name in names:
        dist = _IMPORT_DIST_ALIASES.get(name, name)
        (real if _exists_on_pypi(dist) else phantom).append(name)
    np = len(phantom)
    return SignalResult(
        signal="Phantom deps",
        measured=f"{np} hallucinated/phantom of {n} unresolved ({len(real)} real-but-uninstalled)",
        grade=Grade.RED if np else Grade.GREEN,
        confidence=Confidence.MEDIUM,  # import-name != dist-name aliasing is the blind spot
        confirm_with="verify the package exists AND predates this project on PyPI",
        scope=f"{root}/ unresolved imports cross-checked against PyPI",
        pressure=min(1.0, np / 5),
        instrument="PyPI existence check (live)",
        count=np,
        detail=([f"PHANTOM: {p}  \u2190 {unresolved[p][0]}" for p in phantom]
                or [f"all {len(real)} unresolved names exist on PyPI (uninstalled optional deps)"]),
    )


def _maybe_unresolved(top, provided, unresolved, f, node, root):
    if not top or top in provided:
        return
    norm = top.lower().replace("_", "-")
    if any(norm == p.lower().replace("_", "-") for p in provided):
        return
    unresolved[top].append(f"{f.relative_to(root)}:{node.lineno}")


def _exists_on_pypi(name: str) -> bool:
    import urllib.error
    import urllib.request
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        return True   # transient/other: don't accuse on a non-404
    except Exception:
        return True   # network failure must not manufacture a phantom verdict


# --------------------------------------------------------------------------- #
# NEW DIMENSION B — Change coupling (logical/evolutionary coupling).
#   D'Ambros/Lanza: files that co-change frequently are coupled even with no
#   import edge; strong change coupling predicts defects. Ground truth: git.
# --------------------------------------------------------------------------- #
def change_coupling(root: Path, window: int = 400, min_support: int = 8) -> SignalResult:
    log = git(["log", f"-n{window}", "--no-merges", "--pretty=format:@@%H", "--name-only"], root)
    if not log.strip():
        return SignalResult(
            signal="Change coupling", measured="UNASSESSED (no git history)",
            grade=Grade.UNASSESSED, confidence=Confidence.UNASSESSED,
            confirm_with="git log --name-only", scope=f"last {window} commits",
            pressure=0.0, instrument="(none)")
    commits: list[list[str]] = []
    cur: list[str] = []
    for ln in log.splitlines():
        if ln.startswith("@@"):
            if cur:
                commits.append(cur)
            cur = []
        elif ln.strip().endswith(_CODE_EXTS):
            # language-agnostic: co-change coupling is a property of git history,
            # not of any one language. Route over every source extension present.
            cur.append(ln.strip())
    if cur:
        commits.append(cur)
    pair_count: Counter = Counter()
    file_count: Counter = Counter()
    for files in commits:
        files = [f for f in set(files) if len(set(files)) <= 30]  # ignore mega-commits
        for f in files:
            file_count[f] += 1
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                pair_count[tuple(sorted((files[i], files[j])))] += 1
    coupled = []
    for (a, b), c in pair_count.items():
        if c < min_support:
            continue
        conf = c / min(file_count[a], file_count[b])  # confidence of co-change
        if conf >= 0.6:
            coupled.append((conf, c, a, b))
    coupled.sort(reverse=True)
    n = len(coupled)
    return SignalResult(
        signal="Change coupling",
        measured=f"{n} file-pairs co-change \u2265{min_support}x at \u226560% confidence",
        grade=Grade.RED if n >= 10 else Grade.AMBER if n else Grade.GREEN,
        confidence=Confidence.HIGH,
        confirm_with="git log --name-only; inspect the pairs for a hidden contract",
        scope=f"last {len(commits)} non-merge commits",
        pressure=min(1.0, n / 20),
        instrument="git co-change association rules",
        count=n,
        detail=[f"{conf:4.0%} ({c}x)  {Path(a).name}  \u2194  {Path(b).name}" for conf, c, a, b in coupled[:8]],
    )


# --------------------------------------------------------------------------- #
# NEW DIMENSION C — Narrative comments (the #1 AI-slop tell).
#   Comments that restate the next line of code add entropy, not information.
#   Proxy is explicit (LOW): comment-to-code ratio + obvious restatement regex.
# --------------------------------------------------------------------------- #
def narrative_comments(root: Path) -> SignalResult:
    if not iter_py_files(root):
        return _no_python(root, "Narrative comments",
                          "language-aware comment analysis",
                          "#-comment regex is Python-only — not run")
    restate = 0
    total_comments = 0
    locs = []
    pat = re.compile(r"#\s*(returns?|sets?|gets?|creates?|initializ|loops? over|increment|"
                     r"call|imports?|defines?|assigns?)\b", re.I)
    for f in iter_py_files(root):
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, ln in enumerate(lines):
            s = ln.strip()
            if s.startswith("#"):
                total_comments += 1
                if pat.match(s) and i + 1 < len(lines) and lines[i + 1].strip():
                    restate += 1
                    if len(locs) < 8:
                        locs.append(f"{f.relative_to(root)}:{i+1}  {s[:50]}")
    ratio = restate / max(1, total_comments)
    return SignalResult(
        signal="Narrative comments",
        measured=f"~{restate} restate-the-code comments ({ratio:.1%} of {total_comments})",
        grade=Grade.AMBER if restate >= 50 else Grade.GREEN,
        confidence=Confidence.LOW,   # regex proxy; flags candidates, not proof
        confirm_with="human read of the flagged lines",
        scope=f"{root}/ comment lines",
        pressure=min(1.0, ratio / 0.2),
        instrument="comment-restatement regex (PROXY)",
        count=restate,
        detail=locs,
    )
