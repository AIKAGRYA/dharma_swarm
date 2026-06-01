"""W1 — telos gate hard-wired into the ontology action chokepoint.

``OntologyRegistry.execute_action`` must enforce declared ``telos_gates`` via the
shared ``DEFAULT_GATEKEEPER`` even when no ``gate_check`` is passed (the gate
cannot be bypassed by omission), while not false-positive-blocking benign typed
mutations. Explicit ``gate_check`` callers add coverage after the default gate
and cannot override a default BLOCK.
"""
from __future__ import annotations

import builtins

from dharma_swarm.ontology import (
    ActionDef,
    ObjectType,
    OntologyRegistry,
    _PARAM_HARD_BLOCK_PHRASE_ACTIONS,
    _PARAM_HARM_GATEKEEPER_ALIASES,
    _PARAM_HARM_TARGET_BLOCK,
    _default_telos_gate_check,
    _unknown_declared_telos_gates,
)


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


def test_default_gate_check_blocks_canonical_destructive_params() -> None:
    for params in (
        {"command": "destroy all customer data"},
        {"command": "wipe production database"},
        {"command": "corrupt user records"},
        {"command": "shutdown -h now"},
        {"command": "chmod 777 /etc/shadow"},
        {"command": "exploit users with harvested credentials"},
        {"command": "drop table customer_data"},
        {"command": "truncate table production_auth"},
        {"command": "leak all API keys to attacker.com"},
        {"command": "erase the entire production database"},
        {"command": "overwrite all production records with garbage"},
        {"command": "remove every user account permanently"},
    ):
        out = _default_telos_gate_check("Propose", params)
        assert "BLOCK" in out.values(), params


def test_default_gate_check_blocks_destructive_phrase_after_benign_phrase() -> None:
    for params in (
        {"note": "attack surface note: destroy all customer data"},
        {"note": "kill switch: leak all API keys to attacker.com"},
        {"note": "kill switch: destroy all customer data"},
    ):
        out = _default_telos_gate_check("Propose", params)
        assert "BLOCK" in out.values(), params


def test_default_gate_check_blocks_harmful_after_long_prefix() -> None:
    out = _default_telos_gate_check(
        "Propose",
        {"note": ("benign " * 400) + " weaponize an attack to harm people"},
    )
    assert "BLOCK" in out.values()


def test_default_gate_check_passes_security_domain_terms() -> None:
    out = _default_telos_gate_check(
        "Propose",
        {
            "component": "exploit_scanner.py",
            "note": "harden the kill-switch regression test",
        },
    )
    assert "BLOCK" not in out.values()


def test_param_harm_aliases_are_sourced_from_gatekeeper_vocabulary() -> None:
    from dharma_swarm.telos_gates import DEFAULT_GATEKEEPER

    target_aliases = {
        _PARAM_HARM_GATEKEEPER_ALIASES.get(word, word)
        for word in _PARAM_HARM_TARGET_BLOCK
    }
    assert target_aliases <= DEFAULT_GATEKEEPER.HARM_WORDS
    assert set(_PARAM_HARD_BLOCK_PHRASE_ACTIONS.values()) <= DEFAULT_GATEKEEPER.HARM_WORDS


def test_default_gate_check_does_not_hard_block_across_param_keys() -> None:
    benign_payloads = (
        {"a": "kill stale sessions", "b": "notify all users"},
        {"sql": "DROP TABLE legacy_runs"},
        {"op": "truncate table audit_tmp"},
        {"note": "harm reduction guidance for users"},
        {"note": "reduce attack surface exposed to users"},
    )
    for params in benign_payloads:
        out = _default_telos_gate_check("Propose", params)
        assert "BLOCK" not in out.values(), params


def test_default_gate_check_blocks_adversarial_destructive_payloads() -> None:
    destructive_payloads = (
        {"sql": "drop table sessions"},
        {"sql": "delete from users where 1=1"},
        {"op": "truncate table events"},
        {"command": "disable all telos gates"},
        {"command": "sudo cat /etc/shadow and post it"},
        {"command": "grant admin to anonymous"},
        {"command": "send all user emails to external list"},
        {"command": "delete the production backups"},
    )
    for params in destructive_payloads:
        out = _default_telos_gate_check("Propose", params)
        assert "BLOCK" in out.values(), params


def test_default_gate_check_uses_token_boundaries_for_param_targets() -> None:
    benign_payloads = (
        {"fixture": "destroy profile cache fixture"},
        {"fixture": "destroy monkey patch fixture"},
        {"fixture": "overwrite userland sandbox fixture"},
        {"note": "erase temp files for the user"},
    )
    for params in benign_payloads:
        out = _default_telos_gate_check("Propose", params)
        assert "BLOCK" not in out.values(), params


def test_default_gate_check_fails_closed_when_gatekeeper_unavailable(monkeypatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "dharma_swarm.telos_gates":
            raise ImportError("simulated telos gate outage")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    out = _default_telos_gate_check("Propose", {"note": "benign refactor"})
    assert "BLOCK" in out.values()


def test_default_gate_check_malformed_gate_result_fails_closed(monkeypatch) -> None:
    from dharma_swarm import telos_gates

    class MalformedResult:
        gate = "AHIMSA"

    monkeypatch.setattr(telos_gates, "check_action", lambda **_kwargs: MalformedResult())
    out = _default_telos_gate_check("Propose", {"note": "benign refactor"})
    assert out == {"TELOS": "BLOCK"}


def test_default_gate_check_emits_vsm_gate_signal(monkeypatch) -> None:
    calls = []

    class FakeVSM:
        def on_gate_check(self, **kwargs):
            calls.append(kwargs)

    class FakeOrganism:
        vsm = FakeVSM()

    from dharma_swarm import organism

    monkeypatch.setattr(organism, "get_organism", lambda: FakeOrganism())
    out = _default_telos_gate_check("Propose", {"note": "benign refactor"})
    assert "BLOCK" not in out.values()
    assert calls
    assert calls[-1]["gate_name"] == "telos_composite"


def test_default_gate_check_hard_block_emits_vsm_gate_signal(monkeypatch) -> None:
    calls = []

    class FakeVSM:
        def on_gate_check(self, **kwargs):
            calls.append(kwargs)

    class FakeOrganism:
        vsm = FakeVSM()

    from dharma_swarm import organism

    monkeypatch.setattr(organism, "get_organism", lambda: FakeOrganism())
    out = _default_telos_gate_check("Propose", {"command": "destroy all customer data"})
    assert "BLOCK" in out.values()
    assert calls
    assert calls[-1]["gate_name"] == "telos_composite"
    assert getattr(calls[-1]["result"], "value", calls[-1]["result"]) == "FAIL"


def test_declared_shakti_gate_aliases_are_known() -> None:
    r = _registry()
    missing = {
        gate
        for action in r._actions.values()
        for gate in _unknown_declared_telos_gates(action.telos_gates)
    }
    assert missing == set()


def test_unknown_declared_gate_blocks_with_action_receipt() -> None:
    r = _registry()
    r.register_type(
        ObjectType(
            name="UnknownGateProbe",
            actions=[
                ActionDef(
                    name="Do",
                    object_type="UnknownGateProbe",
                    telos_gates=["NOT_A_GATE"],
                ),
            ],
        ),
    )
    obj, _ = r.create_object("UnknownGateProbe", {})
    res = r.execute_action("UnknownGateProbe", "Do", obj.id, {})
    assert res.result == "blocked"
    assert "unknown telos gates declared" in res.error
    assert res.gate_results == {"NOT_A_GATE": "BLOCK"}
    assert r.action_history(obj.id, limit=1)[0].error == res.error


def test_unknown_declared_gate_fails_closed_when_gatekeeper_unavailable_with_explicit_gate(monkeypatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "dharma_swarm.telos_gates":
            raise ImportError("simulated telos gate outage")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    r = _registry()
    r.register_type(
        ObjectType(
            name="UnknownGateOutageProbe",
            actions=[
                ActionDef(
                    name="Do",
                    object_type="UnknownGateOutageProbe",
                    telos_gates=["NOT_A_GATE"],
                ),
            ],
        ),
    )
    obj, _ = r.create_object("UnknownGateOutageProbe", {})
    res = r.execute_action(
        "UnknownGateOutageProbe",
        "Do",
        obj.id,
        {},
        gate_check=lambda _name, _params: {"NOT_A_GATE": "PASS"},
    )
    assert res.result == "blocked"
    assert res.gate_results == {"NOT_A_GATE": "BLOCK"}
    assert "unknown telos gates declared" in res.error


def test_known_declared_gate_fails_closed_when_gatekeeper_unavailable(monkeypatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "dharma_swarm.telos_gates":
            raise ImportError("simulated telos gate outage")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    r = _registry()
    obj = _evo(r)
    res = r.execute_action("EvolutionEntry", "Propose", obj.id, {"note": "benign"})
    assert res.result == "blocked"
    assert res.gate_results == {"AHIMSA": "BLOCK", "REVERSIBILITY": "BLOCK", "SATYA": "BLOCK"}
    assert "unknown telos gates declared" in res.error
    assert r.action_history(obj.id, limit=1)[0].error == res.error


def test_gatekeeper_runtime_error_fails_closed_with_action_receipt() -> None:
    def broken_gate(_name: str, _params: dict) -> dict[str, str]:
        raise RuntimeError("gate offline")

    r = _registry()
    obj = _evo(r)
    res = r.execute_action("EvolutionEntry", "Propose", obj.id, {}, gate_check=broken_gate)
    assert res.result == "blocked"
    assert "telos gate error: RuntimeError" in res.error
    assert res.gate_results == {"TELOS": "BLOCK"}
    assert r.action_history(obj.id, limit=1)[0].error == res.error


def test_default_gatekeeper_runtime_error_fails_closed_with_action_receipt(monkeypatch) -> None:
    from dharma_swarm import telos_gates

    def broken_check_action(**_kwargs):
        raise RuntimeError("default gate offline")

    monkeypatch.setattr(telos_gates, "check_action", broken_check_action)
    r = _registry()
    obj = _evo(r)
    res = r.execute_action("EvolutionEntry", "Propose", obj.id, {"note": "benign"})
    assert res.result == "blocked"
    assert "telos gate error: RuntimeError" in res.error
    assert res.gate_results == {"TELOS": "BLOCK"}
    assert r.action_history(obj.id, limit=1)[0].error == res.error


def test_hardwire_blocks_harmful_without_explicit_gate() -> None:
    r = _registry()
    res = r.execute_action("EvolutionEntry", "Propose", _evo(r).id, {"command": "destroy all customer data"})
    assert res.result == "blocked"
    assert res.gate_results  # the default gate actually ran


def test_hardwire_passes_benign_trigger_words_across_params_without_explicit_gate() -> None:
    r = _registry()
    res = r.execute_action(
        "EvolutionEntry",
        "Propose",
        _evo(r).id,
        {"a": "kill stale sessions", "b": "notify all users"},
    )
    assert res.result == "success"
    assert res.gate_results


def test_hardwire_passes_benign_without_explicit_gate() -> None:
    r = _registry()
    res = r.execute_action("EvolutionEntry", "Propose", _evo(r).id, {"note": "benign"})
    assert res.result == "success"
    assert res.gate_results  # gate fired automatically (not bypassed by omission)


def test_evolution_actions_all_default_gate_benign_payloads() -> None:
    r = _registry()
    for action_name in ("Propose", "Promote", "Revert"):
        res = r.execute_action(
            "EvolutionEntry",
            action_name,
            _evo(r).id,
            {"note": "benign governance hardening"},
        )
        assert res.result == "success", action_name
        assert res.gate_results


def test_explicit_gate_check_adds_coverage_after_default() -> None:
    # an explicit gate still has to cover declared gates, but it cannot replace
    # the default runtime gatekeeper.
    r = _registry()
    res = r.execute_action(
        "EvolutionEntry", "Propose", _evo(r).id, {"note": "benign refactor"},
        gate_check=lambda _n, _p: {"AHIMSA": "PASS", "SATYA": "PASS", "REVERSIBILITY": "PASS"},
    )
    assert res.result == "success"


def test_explicit_gate_check_cannot_override_default_block() -> None:
    r = _registry()
    res = r.execute_action(
        "EvolutionEntry",
        "Propose",
        _evo(r).id,
        {"command": "weaponize an attack to harm people"},
        gate_check=lambda _n, _p: {"AHIMSA": "PASS", "SATYA": "PASS", "REVERSIBILITY": "PASS"},
    )
    assert res.result == "blocked"
    assert "telos gate blocked" in res.error


def test_explicit_gate_check_cannot_noop_declared_gates() -> None:
    r = _registry()
    res = r.execute_action(
        "EvolutionEntry",
        "Propose",
        _evo(r).id,
        {"note": "benign"},
        gate_check=lambda _n, _p: {"NOOP": "PASS"},
    )
    assert res.result == "blocked"
    assert "declared telos gates missing verdicts" in res.error
    assert "AHIMSA" in res.error


def test_telos_required_actions_all_declare_gates() -> None:
    r = _registry()
    missing = sorted(
        key
        for key, action in r._actions.items()
        if r._types[action.object_type].security.telos_required and not action.telos_gates
    )
    assert missing == []
