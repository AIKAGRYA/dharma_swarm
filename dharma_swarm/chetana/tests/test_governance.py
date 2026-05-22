"""Tests for chetana.governance.

Note: these tests run against the permissive fallback path, because the test
runner does not pip-install dharma_swarm fully. They verify the WRAPPER works
correctly; the real telos gates have their own tests in dharma_swarm/tests/.
"""

from __future__ import annotations

import builtins

from dharma_swarm.chetana.governance import gate_check_atom


def test_gate_check_returns_governance_check():
    result = gate_check_atom(
        atom_content="harmless atom body",
        atom_title="Test atom",
        requested_action="promote_atom",
    )
    assert result.result in {"ALLOW", "WARN", "BLOCK"}
    assert len(result.axiom_signature) == 64
    assert isinstance(result.can_promote, bool)


def test_gate_check_signature_changes_with_content():
    a = gate_check_atom(atom_content="content A", atom_title="A")
    b = gate_check_atom(atom_content="content B", atom_title="B")
    assert a.axiom_signature != b.axiom_signature


def test_to_provenance_round_trips():
    result = gate_check_atom(atom_content="body", atom_title="t")
    prov = result.to_provenance(promoted_by="tester", review_status="staged")
    assert prov.review_status == "staged"
    assert prov.axiom_signature == result.axiom_signature


def test_governance_import_failure_fails_closed(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "dharma_swarm.telos_gates":
            raise ImportError("simulated missing gates")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = gate_check_atom(atom_content="body", atom_title="t")

    assert result.result == "BLOCK"
    assert result.can_promote is False
    assert "chetana_governance_unavailable" in result.record.gates_blocked
