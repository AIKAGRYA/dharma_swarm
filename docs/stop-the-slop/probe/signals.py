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
    Confidence, Grade, SignalResult, git, iter_py_files, parse, run_json, tool_path,
)

GOD_OBJECT_LINES = 3000        # Parnas/SRP: a module with one reason to change stays small
COMPLEXITY_THRESHOLD = 20      # McCabe: above this a function is a test-coverage liability

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
    sizes = []
    for f in iter_py_files(root):
        try:
            n = sum(1 for _ in f.open("r", encoding="utf-8", errors="replace"))
        except OSError:
            continue
        sizes.append((n, f))
    big = sorted((s for s in sizes if s[0] >= GOD_OBJECT_LINES), reverse=True)
    worst = big[0][0] if big else 0
    grade = Grade.RED if len(big) >= 3 else Grade.AMBER if big else Grade.GREEN
    return SignalResult(
        signal="God objects",
        measured=f"{len(big)} modules \u2265{GOD_OBJECT_LINES} ln" + (f" (max {worst:,})" if big else ""),
        grade=grade, confidence=Confidence.HIGH,
        confirm_with="wc -l on the listed files",
        scope=f"{root}/ (.py, deps excluded)",
        pressure=min(1.0, len(big) / 8),
        instrument="AST/line-count",
        detail=[f"{n:>6}  {f.relative_to(root)}" for n, f in big[:8]],
    )


# --------------------------------------------------------------------------- #
# 2. Complexity inflation (McCabe) — route to radon; refuse to proxy silently.
# --------------------------------------------------------------------------- #
def complexity(root: Path) -> SignalResult:
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
        detail=locs[:8],
    )


def broad_catches(root: Path) -> SignalResult:
    _silent, broad, _, locs = _except_stats(root)
    return SignalResult(
        signal="Broad catches",
        measured=f"{broad} (except Exception/bare)",
        grade=Grade.AMBER,   # broad-but-logged is legitimate; this needs review, not auto-RED
        confidence=Confidence.HIGH,
        confirm_with="review each for log + re-raise vs swallow",
        scope=f"{root}/",
        pressure=min(1.0, broad / 3000),
        instrument="AST (ExceptHandler type in {Exception,BaseException,None})",
        detail=locs[:8],
    )


# --------------------------------------------------------------------------- #
# 6. Coupling hotspots (Parnas / Martin instability) — static import graph.
# --------------------------------------------------------------------------- #
def coupling(root: Path) -> SignalResult:
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
    measured = (f"max fan-in {top_in[0][1] if top_in else 0} "
                f"({top_in[0][0].split('.')[-1] if top_in else '-'}); "
                f"max fan-out {top_out[0]} ({top_out[1].split('.')[-1]})")
    return SignalResult(
        signal="Coupling",
        measured=measured,
        grade=Grade.AMBER,
        confidence=Confidence.MEDIUM,   # static imports only; dynamic wiring invisible
        confirm_with="grimp / pydeps import graph",
        scope=f"intra-{pkg} import edges (static)",
        pressure=min(1.0, (top_in[0][1] if top_in else 0) / 150),
        instrument="AST import graph",
        detail=[f"fan-in {c:>4}  {m}" for m, c in fan_in.most_common(6)],
    )


# --------------------------------------------------------------------------- #
# 7. Dead code (Aho–Sethi–Ullman reachability) — vulture if present, else honest.
# --------------------------------------------------------------------------- #
def dead_code(root: Path) -> SignalResult:
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
        detail=[ln.split('\t', 1)[-1][:80] for ln in reverts[:6]],
    )


# --------------------------------------------------------------------------- #
# NEW DIMENSION A — Phantom dependencies / slopsquatting surface.
#   LLMs hallucinate import names at 5–21% (Spracklen et al.); attackers
#   pre-register them. Ground truth: does every imported top-level name resolve
#   to the stdlib or an installed distribution? Unresolved = audit-before-install.
# --------------------------------------------------------------------------- #
def phantom_deps(root: Path) -> SignalResult:
    import importlib.metadata as im
    # Build the set of importable top-level names provided by installed dists.
    provided: set[str] = set(sys.stdlib_module_names)
    try:
        mapping = im.packages_distributions()  # top-level module -> [dist,...]
        provided |= set(mapping.keys())
    except Exception:
        pass
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
        elif ln.strip().endswith(".py"):
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
        detail=[f"{conf:4.0%} ({c}x)  {Path(a).name}  \u2194  {Path(b).name}" for conf, c, a, b in coupled[:8]],
    )


# --------------------------------------------------------------------------- #
# NEW DIMENSION C — Narrative comments (the #1 AI-slop tell).
#   Comments that restate the next line of code add entropy, not information.
#   Proxy is explicit (LOW): comment-to-code ratio + obvious restatement regex.
# --------------------------------------------------------------------------- #
def narrative_comments(root: Path) -> SignalResult:
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
        detail=locs,
    )
