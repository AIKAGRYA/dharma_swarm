"""Unit tests for the effect-analysis pass."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from titanium_verify.effects import Effect, EffectSet, analyze_effects
from titanium_verify.frontend import parse_package


def test_effect_set_pure_join_is_pure():
    p = EffectSet.pure()
    assert p.is_pure()
    assert (p | p).is_pure()


def test_effect_set_join_removes_pure_when_others_present():
    p = EffectSet.pure()
    fs = EffectSet.of(Effect.FS_READ)
    joined = p | fs
    assert Effect.PURE not in joined.effects
    assert Effect.FS_READ in joined.effects
    assert not joined.is_pure()


def test_effect_set_join_is_associative():
    a = EffectSet.of(Effect.FS_READ)
    b = EffectSet.of(Effect.NET)
    c = EffectSet.of(Effect.SUBPROCESS)
    left = (a | b) | c
    right = a | (b | c)
    assert left.effects == right.effects


def test_effect_analysis_flags_open_call_as_impure(tmp_path: Path):
    pkg = tmp_path / "impure_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "def leaky():\n"
        "    return open('/etc/passwd').read()\n"
    )
    modules = parse_package(pkg, "impure_pkg")
    analysis = analyze_effects(modules)
    assert not analysis.is_pure("impure_pkg.leaky")
    assert Effect.FS_READ in analysis.effect_of("impure_pkg.leaky").effects


def test_effect_analysis_write_mode_open_is_fs_write(tmp_path: Path):
    pkg = tmp_path / "write_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "def write_file():\n"
        "    with open('/tmp/out', 'w', encoding='utf-8') as f:\n"
        "        return f.write('x')\n"
    )
    modules = parse_package(pkg, "write_pkg")
    analysis = analyze_effects(modules)
    assert Effect.FS_WRITE in analysis.effect_of("write_pkg.write_file").effects


def test_effect_analysis_pure_function_stays_pure(tmp_path: Path):
    pkg = tmp_path / "pure_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n"
        "def double(x):\n"
        "    return add(x, x)\n"
    )
    modules = parse_package(pkg, "pure_pkg")
    analysis = analyze_effects(modules)
    assert analysis.is_pure("pure_pkg.add")
    assert analysis.is_pure("pure_pkg.double")


def test_effect_analysis_subprocess_call_is_impure(tmp_path: Path):
    pkg = tmp_path / "sp_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "import subprocess\n"
        "def run_git():\n"
        "    return subprocess.run(['git', 'rev-parse', 'HEAD'])\n"
    )
    modules = parse_package(pkg, "sp_pkg")
    analysis = analyze_effects(modules)
    assert not analysis.is_pure("sp_pkg.run_git")
    effs = analysis.effect_of("sp_pkg.run_git").effects
    assert Effect.SUBPROCESS in effs


def test_effect_analysis_subprocess_from_import_is_impure(tmp_path: Path):
    pkg = tmp_path / "sp_from_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "from subprocess import run\n"
        "def run_git():\n"
        "    return run(['git', 'rev-parse', 'HEAD'])\n"
    )
    modules = parse_package(pkg, "sp_from_pkg")
    analysis = analyze_effects(modules)
    assert not analysis.is_pure("sp_from_pkg.run_git")
    assert Effect.SUBPROCESS in analysis.effect_of("sp_from_pkg.run_git").effects


def test_effect_analysis_subprocess_alias_is_impure(tmp_path: Path):
    pkg = tmp_path / "sp_alias_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "import subprocess as sp\n"
        "def run_git():\n"
        "    return sp.run(['git', 'rev-parse', 'HEAD'])\n"
    )
    modules = parse_package(pkg, "sp_alias_pkg")
    analysis = analyze_effects(modules)
    assert not analysis.is_pure("sp_alias_pkg.run_git")
    assert Effect.SUBPROCESS in analysis.effect_of("sp_alias_pkg.run_git").effects
