"""W1 — telos gate hard-wired into the ontology action chokepoint.

``OntologyRegistry.execute_action`` must enforce declared ``telos_gates`` via the
shared ``DEFAULT_GATEKEEPER`` even when no ``gate_check`` is passed (the gate
cannot be bypassed by omission), while not false-positive-blocking benign typed
mutations. Explicit ``gate_check`` callers are unaffected.
"""
from __future__ import annotations

import builtins

from dharma_swarm.ontology import OntologyRegistry, _default_telos_gate_check


def _registry() -> OntologyRegistry:
    return OntologyRegistry.create_dharma_registry()


def _evo(r: OntologyRegistry):
    obj, _ = r.create_object(
        "EvolutionEntry", {"component": "t.py", "change_type": "mutation"},
    )
    return obj


def test_default_gate_check_passes_benign() -> None:
    out = _default_telos_gate_check("Propose", {"note": "benign refactor"})
    assert "BLOCK" not in out.values()


def test_default_gate_check_blocks_harmful_in_params() -> None:
    # the harm vector for typed actions is the PARAMS, not the always-benign verb
    out = _default_telos_gate_check("Propose", {"command": "weaponize an attack to harm people"})
    assert "BLOCK" in out.values()


def test_default_gate_check_blocks_harmful_after_long_prefix() -> None:
    out = _default_telos_gate_check(
        "Propose",
        {"note": ("benign " * 400) + " weaponize an attack to harm people"},
    )
    assert "BLOCK" in out.values()


def test_default_gate_check_fails_closed_when_gatekeeper_unavailable(monkeypatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "dharma_swarm.telos_gates":
            raise ImportError("simulated telos gate outage")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    out = _default_telos_gate_check("Propose", {"note": "benign refactor"})
    assert "BLOCK" in out.values()


def test_hardwire_blocks_harmful_without_explicit_gate() -> None:
    r = _registry()
    res = r.execute_action("EvolutionEntry", "Propose", _evo(r).id, {"command": "weaponize an attack to harm people"})
    assert res.result == "blocked"
    assert res.gate_results  # the default gate actually ran


def test_hardwire_passes_benign_without_explicit_gate() -> None:
    r = _registry()
    res = r.execute_action("EvolutionEntry", "Propose", _evo(r).id, {"note": "benign"})
    assert res.result == "success"
    assert res.gate_results  # gate fired automatically (not bypassed by omission)


def test_explicit_gate_check_overrides_default() -> None:
    # an explicit gate is used as-is; the default is only consulted when None
    r = _registry()
    res = r.execute_action(
        "EvolutionEntry", "Propose", _evo(r).id, {"command": "weaponize an attack to harm people"},
        gate_check=lambda _n, _p: {"AHIMSA": "PASS"},
    )
    assert res.result == "success"


def test_telos_required_actions_all_declare_gates() -> None:
    r = _registry()
    missing = sorted(
        key
        for key, action in r._actions.items()
        if r._types[action.object_type].security.telos_required and not action.telos_gates
    )
    assert missing == []
