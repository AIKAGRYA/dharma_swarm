#!/usr/bin/env python3
"""Import-provenance gate — third-party import declaration ratchet.

A hallucinated dependency (``import faiss_turbo`` for a package that does
not exist) or a silently-undeclared one (relying on a transitive dep) only
fails at runtime, long after review. This gate makes the *set* of
third-party top-level import roots explicit: every non-stdlib, non
first-party import root used in the tree must appear in
``scripts/governance/import_provenance_allowlist.txt``. Introducing a new
import root fails CI until the author either declares the dependency and
regenerates the baseline (``--update-baseline``) or removes the import.

Why an allowlist rather than resolving import names to PyPI distributions:
import names and distribution names diverge (``yaml`` -> ``PyYAML``,
``cv2`` -> ``opencv-python``), so a name->distribution check is inherently
false-positive prone and cannot block safely. The allowlist captures the
roots the code *actually* uses today (all real, since the code imports
them); anything new is, by construction, net-new provenance that a human
must vouch for. The manifests (pyproject / requirements*) are still parsed
to label each new root "declared" vs "undeclared (possibly hallucinated)"
in the failure message.

Usage:
    python3 scripts/governance/check_import_provenance.py
    python3 scripts/governance/check_import_provenance.py --update-baseline
    python3 scripts/governance/check_import_provenance.py --no-allowlist

Exit codes:
    0   no third-party import root outside the allowlist
    1   at least one new third-party import root
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

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - fallback for <3.11
    tomllib = None  # type: ignore[assignment]

ALLOWLIST_REL = "scripts/governance/import_provenance_allowlist.txt"

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

# Import root -> distribution name, for cases where they differ. Used only to
# label a new root "declared" vs "undeclared" in the failure message.
IMPORT_TO_DIST = {
    "yaml": "pyyaml",
    "cv2": "opencv-python",
    "PIL": "pillow",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
    "jose": "python-jose",
    "dateutil": "python-dateutil",
    "git": "gitpython",
    "sklearn": "scikit-learn",
    "google": "google-api-python-client",
}


@dataclass(frozen=True)
class ExternalImport:
    root: str
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


def first_party_roots(root: Path) -> set[str]:
    """Local module roots.

    Includes repo-root-level packages/modules *and* the basename of every
    module anywhere in the tree, because the repo's scripts import siblings
    by bare name (``import ci_truth`` -> ``scripts/governance/ci_truth.py``)
    once their directory is on ``sys.path``. Treating those as first-party
    keeps them out of the third-party provenance surface.
    """
    roots: set[str] = set()
    for child in root.iterdir():
        name = child.name
        if name.startswith(".") or f"/{name}/" in EXCLUDE_DIR_FRAGMENTS:
            continue
        if child.is_dir():
            if (child / "__init__.py").exists() or any(child.rglob("*.py")):
                roots.add(name)
        elif child.suffix == ".py":
            roots.add(child.stem)
    for path in iter_python_files(root):
        roots.add(path.stem)
        parent = path.parent
        if (parent / "__init__.py").exists():
            roots.add(parent.name)
    return roots


def stdlib_roots() -> set[str]:
    names = set(getattr(sys, "stdlib_module_names", set()))
    # A handful of always-present roots not in stdlib_module_names on every
    # minor version; harmless to treat as stdlib for provenance purposes.
    names |= {"__future__", "typing_extensions"}
    # builtin module names too (covers C extensions baked into the interp).
    names |= set(sys.builtin_module_names)
    return names


def collect_external_imports(
    root: Path, fp_roots: set[str], std_roots: set[str]
) -> list[ExternalImport]:
    out: list[ExternalImport] = []
    for path in iter_python_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, ValueError, OSError):
            continue
        rel = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top and top not in fp_roots and top not in std_roots:
                        out.append(ExternalImport(top, rel, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue  # relative -> first-party
                top = (node.module or "").split(".")[0]
                if top and top not in fp_roots and top not in std_roots:
                    out.append(ExternalImport(top, rel, node.lineno))
    return out


def _normalize_dist(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def declared_dists(root: Path) -> set[str]:
    dists: set[str] = set()
    # requirements*.txt
    for req in root.glob("requirements*.txt"):
        for raw in req.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", "-")):
                continue
            token = line.split(";")[0]
            for sep in ("==", ">=", "<=", "~=", ">", "<", "!=", "[", " "):
                token = token.split(sep)[0]
            if token:
                dists.add(_normalize_dist(token))
    # pyproject.toml. This repo also carries installable packages under
    # packages/*, so their pyprojects are dependency manifests too.
    pyprojects = [root / "pyproject.toml"]
    packages_dir = root / "packages"
    if packages_dir.exists():
        pyprojects.extend(sorted(packages_dir.glob("*/pyproject.toml")))
    for pyproject in pyprojects:
        if not pyproject.exists() or tomllib is None:
            continue
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError):
            data = {}
        project = data.get("project", {}) if isinstance(data, dict) else {}
        specs: list[str] = list(project.get("dependencies", []) or [])
        for group in (project.get("optional-dependencies", {}) or {}).values():
            specs.extend(group or [])
        for spec in specs:
            token = str(spec).split(";")[0]
            for sep in ("==", ">=", "<=", "~=", ">", "<", "!=", "[", " "):
                token = token.split(sep)[0]
            if token:
                dists.add(_normalize_dist(token))
    return dists


def _is_declared(root_name: str, dists: set[str]) -> bool:
    candidate = IMPORT_TO_DIST.get(root_name, root_name)
    return _normalize_dist(candidate) in dists or _normalize_dist(root_name) in dists


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


def write_allowlist(root: Path, roots: set[str]) -> Path:
    path = root / ALLOWLIST_REL
    header = (
        "# import-provenance allowlist — third-party top-level import roots the\n"
        "# tree uses today. A new root fails check_import_provenance.py until it\n"
        "# is declared in the dependency manifest and added here. Regenerate with:\n"
        "#   python3 scripts/governance/check_import_provenance.py --update-baseline\n"
    )
    body = "\n".join(sorted(roots))
    path.write_text(header + body + ("\n" if body else ""), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--no-allowlist", action="store_true")
    args = parser.parse_args(argv)

    try:
        root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"import-provenance: environment error: {exc}", file=sys.stderr)
        return 2

    os.chdir(root)
    fp_roots = first_party_roots(root)
    std_roots = stdlib_roots()
    externals = collect_external_imports(root, fp_roots, std_roots)
    used_roots = {e.root for e in externals}

    if args.update_baseline:
        dest = write_allowlist(root, used_roots)
        print(f"import-provenance: wrote {len(used_roots)} root(s) to "
              f"{dest.relative_to(root)}")
        return 0

    allowlist = set() if args.no_allowlist else load_allowlist(root)
    dists = declared_dists(root)
    new_roots = sorted(used_roots - allowlist)

    if args.json:
        print(json.dumps(
            {"new_roots": new_roots, "allowlisted": len(allowlist),
             "declared_dists": sorted(dists)}, indent=2, sort_keys=True))
        return 1 if new_roots else 0

    if not new_roots:
        print(f"import-provenance: OK — {len(used_roots)} third-party import "
              f"root(s), all allowlisted.")
        return 0

    print(f"::error::import-provenance — {len(new_roots)} new third-party import "
          f"root(s) not in the allowlist:")
    # First occurrence per root, for a useful pointer.
    first_seen: dict[str, ExternalImport] = {}
    for e in externals:
        first_seen.setdefault(e.root, e)
    for r in new_roots:
        loc = first_seen[r]
        status = "declared" if _is_declared(r, dists) else "UNDECLARED (possibly hallucinated)"
        print(f"  {r}  [{status}]  first at {loc.path}:{loc.line}")
    print("Declare the dependency in pyproject.toml / requirements*.txt, then "
          "run --update-baseline. If the package name looks invented, it is "
          "likely a hallucinated import — remove it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
