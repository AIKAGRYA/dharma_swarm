"""Unit tests for the AST frontend."""
from __future__ import annotations

import ast
import tempfile
from pathlib import Path

import pytest

from titanium_verify.frontend import (
    Function,
    Module,
    _extract_function,
    _import_aliases,
    _module_functions,
    _module_imports,
    parse_package,
)


def _parse_source(src: str) -> ast.Module:
    return ast.parse(src)


def test_frontend_parses_simple_function():
    src = "def foo(x: int) -> int:\n    return x + 1\n"
    tree = _parse_source(src)
    fns = _module_functions(tree, "test_module")
    assert len(fns) == 1
    assert fns[0].name == "foo"
    assert fns[0].qualname == "test_module.foo"
    assert fns[0].args[0].name == "x"
    assert fns[0].args[0].annotation == "int"
    assert fns[0].return_annotation == "int"
    assert not fns[0].is_rejected


def test_frontend_rejects_lambda():
    src = "def foo():\n    f = lambda x: x + 1\n    return f(3)\n"
    tree = _parse_source(src)
    fns = _module_functions(tree, "m")
    assert len(fns) == 1
    assert fns[0].is_rejected
    assert "lambda" in fns[0].rejected_reason


def test_frontend_rejects_eval():
    src = "def foo(s):\n    return eval(s)\n"
    tree = _parse_source(src)
    fns = _module_functions(tree, "m")
    assert fns[0].is_rejected
    assert "eval" in fns[0].rejected_reason


def test_frontend_captures_effect_decorator():
    src = (
        "from telos_kernel._io.effect import Effect, effect\n"
        "class Effect:\n"
        "    FS_READ = 'FS_READ'\n"
        "\n"
        "@effect(Effect.FS_READ)\n"
        "def read_file(path):\n"
        "    return path\n"
    )
    tree = _parse_source(src)
    fns = _module_functions(tree, "m")
    # Find the function 'read_file'.
    read_file = next(f for f in fns if f.name == "read_file")
    assert "FS_READ" in read_file.effect_tags


def test_frontend_extracts_class_methods():
    src = (
        "class Foo:\n"
        "    def bar(self, x):\n"
        "        return x\n"
        "    def baz(self):\n"
        "        return 42\n"
    )
    tree = _parse_source(src)
    fns = _module_functions(tree, "m")
    assert {f.qualname for f in fns} == {"m.Foo.bar", "m.Foo.baz"}


def test_frontend_module_imports():
    src = (
        "import json\n"
        "import z3\n"
        "from pathlib import Path\n"
        "from dataclasses import dataclass\n"
    )
    tree = _parse_source(src)
    assert set(_module_imports(tree)) == {"json", "z3", "pathlib", "dataclasses"}


def test_frontend_records_import_aliases():
    src = (
        "import subprocess as sp\n"
        "from pathlib import Path\n"
        "from subprocess import run as sprun\n"
    )
    tree = _parse_source(src)
    assert _import_aliases(list(tree.body)) == {
        "sp": "subprocess",
        "Path": "pathlib.Path",
        "sprun": "subprocess.run",
    }


def test_frontend_rejects_unknown_decorator():
    src = (
        "@some_random_decorator\n"
        "def foo():\n"
        "    return 1\n"
    )
    tree = _parse_source(src)
    fns = _module_functions(tree, "m")
    assert fns[0].is_rejected
    assert "some_random_decorator" in fns[0].rejected_reason


def test_frontend_accepts_dataclass_decorator():
    src = (
        "@dataclass\n"
        "class Foo:\n"
        "    def bar(self):\n"
        "        return 1\n"
    )
    tree = _parse_source(src)
    fns = _module_functions(tree, "m")
    # dataclass is on the class, not the function; the method itself is fine.
    assert not fns[0].is_rejected


def test_parse_package_end_to_end(tmp_path: Path):
    pkg = tmp_path / "toy_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("def top():\n    return 1\n")
    (pkg / "_io").mkdir()
    (pkg / "_io" / "__init__.py").write_text("")
    (pkg / "_io" / "reader.py").write_text(
        "def read_it():\n    return open('x').read()\n"
    )
    (pkg / "tests").mkdir()
    (pkg / "tests" / "test_foo.py").write_text(
        "def test_it():\n    assert eval('1+1') == 2\n"
    )
    modules = parse_package(pkg, "toy_pkg")
    # Tests are excluded.
    assert not any("tests" in m.dotted_name for m in modules)
    # We have the top-level module and _io.reader.
    names = {m.dotted_name for m in modules}
    assert "toy_pkg" in names or "toy_pkg." in "|".join(names)
    rim = [m for m in modules if m.is_rim]
    assert len(rim) >= 1
    core = [m for m in modules if not m.is_rim]
    assert len(core) >= 1
