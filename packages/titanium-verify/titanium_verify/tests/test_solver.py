"""Solver-level unit tests: Z3 must return unsat for pure programs and
sat (with a witness) for programs that leak effects."""
from __future__ import annotations

from pathlib import Path

import pytest

from titanium_verify.report import Verdict
from titanium_verify.verifier import verify_package


def test_solver_verifies_pure_toy_package(tmp_path: Path):
    pkg = tmp_path / "toy_pure"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "def mul(a, b):\n"
        "    total = 0\n"
        "    for _ in range(b):\n"
        "        total = add(total, a)\n"
        "    return total\n"
    )
    report = verify_package(pkg, "toy_pure", property_name="purity")
    assert report.verdict == Verdict.VERIFIED, report
    assert report.functions_verified == report.functions_checked
    assert not report.counterexamples


def test_solver_refutes_impure_program(tmp_path: Path):
    pkg = tmp_path / "toy_impure"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "def read_it():\n"
        "    return open('/tmp/x').read()\n"
        "\n"
        "def wrapper():\n"
        "    return read_it()\n"
    )
    report = verify_package(pkg, "toy_impure", property_name="purity")
    assert report.verdict == Verdict.REFUTED, report
    assert len(report.counterexamples) >= 1
    # Both functions should be refuted: read_it directly, wrapper via callee.
    refuted_qnames = {c.function_qualname for c in report.counterexamples}
    assert "toy_impure.read_it" in refuted_qnames


def test_solver_accepts_tagged_rim_function(tmp_path: Path):
    """A rim function that opens files is EXCLUDED from purity checks."""
    pkg = tmp_path / "toy_rim"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "def top_pure(x):\n"
        "    return x\n"
    )
    (pkg / "_io").mkdir()
    (pkg / "_io" / "__init__.py").write_text("")
    (pkg / "_io" / "loader.py").write_text(
        "class Effect:\n"
        "    FS_READ = 'FS_READ'\n"
        "def effect(*e):\n"
        "    def dec(f):\n"
        "        return f\n"
        "    return dec\n"
        "\n"
        "@effect(Effect.FS_READ)\n"
        "def load_it(path):\n"
        "    return open(path).read()\n"
    )
    report = verify_package(pkg, "toy_rim", property_name="purity")
    # The core function is pure; the rim is not checked.
    assert report.verdict == Verdict.VERIFIED, report


def test_solver_reports_rejected_construct(tmp_path: Path):
    pkg = tmp_path / "toy_reject"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "def dyn(s):\n"
        "    return eval(s)\n"
    )
    report = verify_package(pkg, "toy_reject", property_name="purity")
    assert report.verdict == Verdict.REJECTED
    rejected = [f for f in report.per_function if f.verdict == Verdict.REJECTED]
    assert len(rejected) == 1
    assert rejected[0].qualname == "toy_reject.dyn"
