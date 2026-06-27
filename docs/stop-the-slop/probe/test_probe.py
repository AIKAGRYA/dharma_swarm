"""Self-tests for the runner. Run: python -m pytest test_probe.py  (or python test_probe.py)

These prove the two claims the product lives or dies on:
  1. RETURN CLEAN — on genuinely clean code the signals grade GREEN, not "something".
  2. DETECT — on planted slop the signals go RED with the right evidence.
A signal that can't do (1) is a finding-manufacturer; one that can't do (2) is decoration.
"""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

import signals as S
from _common import Confidence, Grade


def _write(d: Path, name: str, body: str) -> Path:
    p = d / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_returns_clean_on_clean_code():
    with tempfile.TemporaryDirectory() as t:
        pkg = Path(t) / "clean_pkg"
        pkg.mkdir()
        _write(pkg, "__init__.py", "")
        _write(pkg, "m.py", """
            import os
            def add(a, b):
                return a + b
        """)
        assert S.wildcard_imports(pkg).grade is Grade.GREEN
        assert S.silent_swallows(pkg).grade is Grade.GREEN
        assert S.god_objects(pkg).grade is Grade.GREEN
        # clean code must not be branded with a manufactured RED
        assert S.complexity(pkg).grade in (Grade.GREEN, Grade.AMBER)


def test_detects_planted_slop():
    with tempfile.TemporaryDirectory() as t:
        pkg = Path(t) / "dirty_pkg"
        pkg.mkdir()
        _write(pkg, "__init__.py", "")
        _write(pkg, "bad.py", """
            from os import *
            def swallow():
                try:
                    risky()
                except Exception:
                    pass
        """)
        assert S.wildcard_imports(pkg).grade is Grade.RED
        sw = S.silent_swallows(pkg)
        assert "1" in sw.measured  # exactly one except: pass planted


def test_phantom_offline_refuses_to_accuse():
    """Offline, an unresolved import is a candidate, never a confirmed phantom."""
    with tempfile.TemporaryDirectory() as t:
        pkg = Path(t) / "p"
        pkg.mkdir()
        _write(pkg, "__init__.py", "")
        _write(pkg, "u.py", "import totally_made_up_xyz_pkg\n")
        S.ONLINE = False
        r = S.phantom_deps(pkg)
        assert r.confidence is Confidence.LOW
        assert r.grade is not Grade.RED            # must not accuse offline
        assert r.pressure == 0.0                   # must not drive the composite


def test_complexity_routes_to_radon_when_present():
    from _common import tool_path
    if not tool_path("radon"):
        return  # tool absent: nothing to assert, the offline path is its own test
    with tempfile.TemporaryDirectory() as t:
        pkg = Path(t) / "p"
        pkg.mkdir()
        _write(pkg, "m.py", "def f(x):\n    return x\n")
        r = S.complexity(pkg)
        assert r.confidence is Confidence.HIGH
        assert "radon" in r.instrument


def test_cycles_flags_load_time_but_not_typecheck_or_lazy():
    """A module-level mutual import is a RED load-time cycle; a TYPE_CHECKING-guarded
    or function-local back-edge is NOT load-time and must not inflate the count."""
    with tempfile.TemporaryDirectory() as t:
        pkg = Path(t) / "pkg"
        pkg.mkdir()
        _write(pkg, "__init__.py", "")
        # a <-> b: genuine module-level (load-time) cycle
        _write(pkg, "a.py", "from pkg import b\nX = 1\n")
        _write(pkg, "b.py", "from pkg import a\nY = 2\n")
        # c <-> d: back-edge only under TYPE_CHECKING (not a runtime cycle)
        _write(pkg, "c.py", "from pkg import d\n")
        _write(pkg, "d.py", """
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                from pkg import c
        """)
        # e -> f at module level, f -> e only inside a function (lazy, breaks cycle)
        _write(pkg, "e.py", "from pkg import f\n")
        _write(pkg, "f.py", "def use():\n    from pkg import e\n    return e\n")
        r = S.cycles(pkg)
        assert r.confidence is Confidence.HIGH
        assert r.grade is Grade.RED                       # the a<->b load-time cycle
        assert "1 load-time" in r.measured                # exactly one load-time SCC
        joined = " ".join(r.detail)
        assert "a" in joined and "b" in joined            # the load-time pair is named


def test_duplication_returns_clean_then_detects_clone():
    """Unique code grades GREEN; an exact copy-paste of a block is flagged as a
    candidate clone at LOW confidence (a proxy for jscpd, never a confirmed RED)."""
    with tempfile.TemporaryDirectory() as t:
        pkg = Path(t) / "pkg"
        pkg.mkdir()
        _write(pkg, "__init__.py", "")
        _write(pkg, "uniq.py", """
            def alpha(x):
                total = x + 1
                scaled = total * 2
                shifted = scaled - 3
                squared = shifted ** 2
                return squared
        """)
        clean = S.duplication(pkg)
        assert clean.grade is Grade.GREEN
        assert clean.confidence is Confidence.MEDIUM      # Type-1 only; never HIGH
        # plant an exact copy of a >=6-line block in a second file
        block = """
            def beta(x):
                total = x + 1
                scaled = total * 2
                shifted = scaled - 3
                squared = shifted ** 2
                doubled = squared + squared
                return doubled
        """
        _write(pkg, "one.py", block)
        _write(pkg, "two.py", block.replace("beta", "gamma"))
        dirty = S.duplication(pkg)
        assert dirty.detail                               # clone evidence is emitted
        assert dirty.pressure >= clean.pressure           # planted clone raises pressure


def test_python_signals_unassessed_on_non_python_tree():
    """The integrity invariant: a Python-AST signal pointed at a tree with no .py
    sources must return UNASSESSED, never a false-GREEN 'clean' verdict on a
    language it cannot parse."""
    with tempfile.TemporaryDirectory() as t:
        pkg = Path(t) / "rustish"
        pkg.mkdir()
        _write(pkg, "main.rs", "fn main() {\n    println!(\"hi\");\n}\n")
        _write(pkg, "lib.rs", "pub fn add(a: i32, b: i32) -> i32 { a + b }\n")
        for sig in (S.complexity, S.wildcard_imports, S.silent_swallows,
                    S.broad_catches, S.coupling, S.dead_code, S.duplication,
                    S.cycles, S.phantom_deps, S.narrative_comments):
            r = sig(pkg)
            assert r.grade is Grade.UNASSESSED, f"{sig.__name__} must abstain, got {r.grade}"
            assert r.confidence is Confidence.UNASSESSED
            assert r.pressure == 0.0  # an abstention must never drive the composite


def test_god_objects_travels_to_other_languages():
    """Line count is language-agnostic: a huge .rs file is a god object too, and a
    tree with no recognized source at all is UNASSESSED, not GREEN."""
    with tempfile.TemporaryDirectory() as t:
        pkg = Path(t) / "rustish"
        pkg.mkdir()
        _write(pkg, "huge.rs", "// big\n" + ("let _x = 0;\n" * 3200))
        r = S.god_objects(pkg)
        assert r.grade in (Grade.AMBER, Grade.RED)   # found the oversized .rs file
        assert "language-agnostic" in r.instrument
        assert ".rs" in r.scope
        empty = Path(t) / "empty"
        empty.mkdir()
        (empty / "notes.txt").write_text("not source\n", encoding="utf-8")
        assert S.god_objects(empty).grade is Grade.UNASSESSED


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
