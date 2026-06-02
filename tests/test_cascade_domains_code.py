"""Tests for dharma_swarm/cascade_domains/code.py — CODE domain scoring."""

from __future__ import annotations

from typing import Any

import pytest

from dharma_swarm.cascade_domains.code import (
    _find_test_file,
    _read_file,
    generate,
    get_domain,
    mutate,
    score,
    test as code_test,
)


VALID_PYTHON = '''"""Sample module."""

def hello(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''

INVALID_PYTHON = "def broken(:\n    pass"

EMPTY_PYTHON = ""


class TestGetDomain:
    def test_default_config(self) -> None:
        domain = get_domain()
        assert domain.name == "code"
        assert domain.max_iterations == 30
        assert domain.fitness_threshold == 0.6

    def test_custom_config(self) -> None:
        domain = get_domain({"max_iterations": 100, "fitness_threshold": 0.9})
        assert domain.max_iterations == 100
        assert domain.fitness_threshold == 0.9

    def test_function_paths(self) -> None:
        domain = get_domain()
        assert "code.generate" in domain.generate_fn
        assert "code.test" in domain.test_fn
        assert "code.score" in domain.score_fn
        assert "code.mutate" in domain.mutate_fn


class TestGenerate:
    def test_generate_from_content(self) -> None:
        artifact = generate({"content": VALID_PYTHON}, {})
        assert artifact["content"] == VALID_PYTHON
        assert artifact["component"] == "unknown"

    def test_generate_from_path(self, tmp_path) -> None:
        f = tmp_path / "sample.py"
        f.write_text(VALID_PYTHON)
        artifact = generate({"path": str(f)}, {})
        assert artifact["content"] == VALID_PYTHON
        assert artifact["component"] == "sample"

    def test_generate_from_context_path(self, tmp_path) -> None:
        f = tmp_path / "ctx_module.py"
        f.write_text(VALID_PYTHON)
        artifact = generate(None, {"path": str(f)})
        assert artifact["content"] == VALID_PYTHON
        assert artifact["component"] == "ctx_module"

    def test_generate_nonexistent_path(self) -> None:
        artifact = generate({"path": "/nonexistent/module.py"}, {})
        assert artifact["content"] == ""

    def test_generate_empty(self) -> None:
        artifact = generate(None, {})
        assert artifact["content"] == ""
        assert artifact["component"] == "unknown"

    def test_generate_with_change_type(self) -> None:
        artifact = generate({"content": "x=1", "change_type": "fix"}, {})
        assert artifact["change_type"] == "fix"


class TestReadFile:
    def test_read_existing(self, tmp_path) -> None:
        f = tmp_path / "test.py"
        f.write_text("hello")
        assert _read_file(str(f)) == "hello"

    def test_read_nonexistent(self) -> None:
        assert _read_file("/nonexistent/path.py") == ""


class TestTest:
    def test_valid_syntax(self) -> None:
        artifact = {"content": VALID_PYTHON}
        result = code_test(artifact, {})
        assert result["test_passed"] is True
        assert result["test_results"]["syntax_valid"] is True
        assert result["test_results"]["status"] == "pass"

    def test_invalid_syntax(self) -> None:
        artifact = {"content": INVALID_PYTHON}
        result = code_test(artifact, {})
        assert result["test_passed"] is False
        assert result["test_results"]["syntax_valid"] is False
        assert "SyntaxError" in result["test_results"]["error"]

    def test_empty_content(self) -> None:
        artifact = {"content": ""}
        result = code_test(artifact, {})
        assert result["test_passed"] is False
        assert result["test_results"]["status"] == "fail"

    def test_with_pytest_file(self, tmp_path) -> None:
        # Create source and matching test
        src = tmp_path / "dharma_swarm" / "sample_mod.py"
        src.parent.mkdir(parents=True)
        src.write_text(VALID_PYTHON)

        artifact = {"content": VALID_PYTHON, "path": str(src)}
        result = code_test(artifact, {})
        assert result["test_passed"] is True
        assert result["test_results"]["syntax_valid"] is True


class TestFindTestFile:
    def test_finds_existing_test(self, tmp_path, monkeypatch) -> None:
        import dharma_swarm.cascade_domains.code as code_mod

        monkeypatch.setattr(code_mod, "_PROJECT_ROOT", tmp_path)
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_sample.py"
        test_file.write_text("def test_x(): pass")

        result = _find_test_file(str(tmp_path / "dharma_swarm" / "sample.py"))
        assert result == test_file

    def test_returns_none_for_missing(self) -> None:
        result = _find_test_file("/nonexistent/module.py")
        # May return None or a non-existing path
        if result is not None:
            assert not result.exists()


class TestScore:
    def test_score_valid_code(self) -> None:
        artifact = {
            "content": VALID_PYTHON,
            "test_passed": True,
            "test_results": {"syntax_valid": True, "pytest_ran": False},
        }
        result = score(artifact, {})
        assert "fitness" in result
        assert result["fitness"]["correctness"] == 1.0
        assert result["score"] > 0.0

    def test_score_failed_code(self) -> None:
        artifact = {
            "content": INVALID_PYTHON,
            "test_passed": False,
            "test_results": {"syntax_valid": False, "pytest_ran": False},
        }
        result = score(artifact, {})
        assert result["fitness"]["correctness"] == 0.0

    def test_score_empty_code(self) -> None:
        artifact = {
            "content": "",
            "test_passed": False,
            "test_results": {},
        }
        result = score(artifact, {})
        assert isinstance(result["score"], float)


class TestMutate:
    def test_mutate_flags_artifact(self) -> None:
        artifact = {"content": VALID_PYTHON, "change_type": "proposal"}
        result = mutate(artifact, {})
        assert result["metadata"]["mutated"] is True
        assert result["metadata"]["generation"] == 1
        assert result["change_type"] == "mutation"

    def test_mutate_increments_generation(self) -> None:
        artifact = {
            "content": VALID_PYTHON,
            "change_type": "mutation",
            "metadata": {"generation": 3},
        }
        result = mutate(artifact, {})
        assert result["metadata"]["generation"] == 4

    def test_mutate_preserves_content(self) -> None:
        artifact = {"content": VALID_PYTHON, "change_type": "fix"}
        result = mutate(artifact, {})
        assert result["content"] == VALID_PYTHON
