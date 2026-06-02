"""Tests for dharma_swarm/cascade_domains/meta.py — META domain (strange loop)."""

from __future__ import annotations

from typing import Any

from dharma_swarm.cascade_domains.meta import (
    _TUNABLE_PARAMS,
    gate,
    generate,
    get_domain,
    mutate,
    score,
    test as meta_test,
)


class TestGetDomain:
    def test_default_config(self) -> None:
        domain = get_domain()
        assert domain.name == "meta"
        assert domain.max_iterations == 10
        assert domain.fitness_threshold == 0.7

    def test_custom_config(self) -> None:
        domain = get_domain({"max_iterations": 50, "fitness_threshold": 0.5})
        assert domain.max_iterations == 50
        assert domain.fitness_threshold == 0.5

    def test_function_paths(self) -> None:
        domain = get_domain()
        assert "meta.generate" in domain.generate_fn
        assert "meta.test" in domain.test_fn
        assert "meta.score" in domain.score_fn
        assert "meta.gate" in domain.gate_fn
        assert "meta.mutate" in domain.mutate_fn


class TestGenerate:
    def test_generate_from_seed(self) -> None:
        seed = {"content": "test config", "target_domains": {"code": {"max_iterations": 30}}}
        result = generate(seed, {})
        assert result["target_domains"] == {"code": {"max_iterations": 30}}

    def test_generate_from_context(self) -> None:
        context = {"target_domains": {"code": {}, "skill": {}}}
        result = generate(None, context)
        assert "code" in result["target_domains"]
        assert "skill" in result["target_domains"]

    def test_generate_excludes_meta(self) -> None:
        context = {"target_domains": {"code": {}, "meta": {}, "skill": {}}}
        result = generate(None, context)
        assert "meta" not in result["target_domains"]

    def test_generate_empty(self) -> None:
        result = generate(None, {})
        assert result["target_domains"] == {}


class TestTest:
    def test_valid_config(self) -> None:
        artifact = {
            "target_domains": {
                "code": {"max_iterations": 30, "fitness_threshold": 0.6},
            }
        }
        result = meta_test(artifact, {})
        assert result["test_passed"] is True
        assert result["test_results"]["status"] == "pass"

    def test_out_of_bounds(self) -> None:
        artifact = {
            "target_domains": {
                "code": {"max_iterations": 999},  # max is 100
            }
        }
        result = meta_test(artifact, {})
        assert result["test_passed"] is False
        assert "outside" in result["test_results"]["issues"][0]

    def test_self_targeting_blocked(self) -> None:
        artifact = {"target_domains": {"meta": {}}}
        result = meta_test(artifact, {})
        assert result["test_passed"] is False
        assert "cannot target itself" in result["test_results"]["issues"][0]

    def test_empty_targets_valid(self) -> None:
        artifact = {"target_domains": {}}
        result = meta_test(artifact, {})
        assert result["test_passed"] is True


class TestScore:
    def test_score_with_valid_domains(self) -> None:
        artifact = {
            "target_domains": {"code": {}, "skill": {}},
            "test_passed": True,
        }
        result = score(artifact, {})
        assert result["score"] > 0.0
        assert result["fitness"]["validity"] == 1.0

    def test_score_empty_domains(self) -> None:
        artifact = {"target_domains": {}}
        result = score(artifact, {})
        assert result["score"] == 0.0
        assert result["fitness"]["coverage"] == 0.0

    def test_score_failed_test(self) -> None:
        artifact = {
            "target_domains": {"code": {}},
            "test_passed": False,
        }
        result = score(artifact, {})
        assert result["fitness"]["validity"] == 0.0


class TestGate:
    def test_gate_passes_valid(self) -> None:
        artifact = {"target_domains": {"code": {}, "skill": {}}}
        result = gate(artifact, {})
        assert result["passed"] is True
        assert result["decision"] == "allow"

    def test_gate_blocks_self_target(self) -> None:
        artifact = {"target_domains": {"meta": {}, "code": {}}}
        result = gate(artifact, {})
        assert result["passed"] is False
        assert result["decision"] == "block"
        assert "cannot target itself" in result["reason"]

    def test_gate_empty_targets(self) -> None:
        artifact = {"target_domains": {}}
        result = gate(artifact, {})
        assert result["passed"] is True


class TestMutate:
    def test_mutate_preserves_structure(self) -> None:
        artifact = {
            "target_domains": {
                "code": {"max_iterations": 30, "fitness_threshold": 0.6},
            }
        }
        result = mutate(artifact, {}, mutation_rate=1.0)
        assert "target_domains" in result
        assert "code" in result["target_domains"]

    def test_mutate_stays_in_bounds(self) -> None:
        artifact = {
            "target_domains": {
                "code": {
                    "max_iterations": 50,
                    "fitness_threshold": 0.5,
                    "mutation_rate": 0.1,
                },
            }
        }
        # Run many mutations to test bounds
        for _ in range(20):
            result = mutate(artifact, {}, mutation_rate=1.0)
            cfg = result["target_domains"]["code"]
            for param, (lo, hi) in _TUNABLE_PARAMS.items():
                if param in cfg:
                    assert lo <= cfg[param] <= hi, f"{param}={cfg[param]} out of [{lo},{hi}]"

    def test_mutate_zero_rate(self) -> None:
        artifact = {
            "target_domains": {"code": {"max_iterations": 30}},
        }
        result = mutate(artifact, {}, mutation_rate=0.0)
        assert result["target_domains"]["code"]["max_iterations"] == 30
