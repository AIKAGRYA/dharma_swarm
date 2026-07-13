"""Tests for the holon-grade harness — the executable HOLON_CONTRACT invariant.

The load-bearing guarantees:
  * weights sum to 100 and the invariant axis set matches the ratified contract;
  * a body-deleted fixture scores ~0 (the harness does NOT fail open on mere docs);
  * a fully-live fixture reaches holon-grade;
  * grading is deterministic (same tree -> same digest);
  * assert_holon_grade / run_holon gate on the invariant, not on prose.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm import holon_grade as hg


def test_weights_sum_to_100_and_invariant_set():
    assert sum(a.weight for a in hg.AXES) == 100
    # the 7 H-axes are the ratified invariant; the 9 O-axes are oracle-parity.
    inv = [a.id for a in hg.AXES if a.invariant]
    assert inv == [
        "H1_identity_honest_liveness", "H2_dialogue_face", "H3_wake_metabolism",
        "H4_authority_envelope", "H5_memory_truth_precedence", "H6_delegation_surface",
        "H7_receipts_verification",
    ]
    assert len([a for a in hg.AXES if not a.invariant]) == 9


def _seat(root: Path, uid: str, real_key: bool = False) -> Path:
    home = root / uid
    (home / "keys").mkdir(parents=True)
    pub = "deadbeef"
    if real_key:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        priv = Ed25519PrivateKey.generate()
        keyfile = home / "keys" / "ed25519_private.pem"
        keyfile.write_bytes(priv.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        keyfile.chmod(0o600)
        pub = priv.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    (home / "identity.json").write_text(json.dumps({
        "agent_uid": uid, "public_key": pub, "authority_mode": "read_only_until_execution_lease",
        "status": "dormant_session_borne_only",
    }))
    return home


def test_ctrl_broken_scores_zero_not_fail_open(tmp_path):
    """A registered-but-body-deleted agent (only an empty dir) must score ~0.

    This is the CTRL_BROKEN guard from the parity gauntlet, in code: surface-presence
    (a directory, a bare identity) must never fail OPEN into a passing grade.
    """
    root = tmp_path / "agents"
    (root / "ghost").mkdir(parents=True)
    (root / "ghost" / "identity.json").write_text("{}")
    grade = hg.grade_agent("ghost", agents_root=root)
    assert grade.score <= 8, f"body-deleted agent scored {grade.score} — rubric is fail-open"
    assert not grade.has_holon_shape


def test_live_fixture_reaches_holon_grade(tmp_path, monkeypatch):
    """A fixture wired live on every invariant axis reaches holon-grade LIVE."""
    root = tmp_path / "agents"
    dharma = tmp_path / "dharma"
    home = _seat(root, "liveseat", real_key=True)
    # H2 responder, H3 wake loop, H5 memory+ledger, H6 delegation, H7 dojo+receipts
    (home / "talk_receipts.jsonl").write_text("{}\n")
    (home / "responder_heartbeat.json").write_text("{}")
    (home / "dojo").mkdir()
    (home / "dojo" / "DOJO.md").write_text("verifier != executor")
    (home / "INTENT_LEDGER.jsonl").write_text('{"custody":"DECREE"}\n')
    (home / "OPEN_DELEGATIONS.md").write_text("expected receipt | TTL | VERIFIED closed | GRADE: pass")
    (home / "evolution").mkdir()
    (home / "evolution" / "ledger.jsonl").write_text("{}\n")
    # transport heartbeats + state + leases + memory, redirected into tmp
    (dharma / "a2a_bus" / "bridge_heartbeats").mkdir(parents=True)
    (dharma / "a2a_bus" / "bridge_heartbeats" / "liveseat.json").write_text(json.dumps({"receipt_count": 5}))
    (dharma / "a2a_bus" / "state").mkdir(parents=True)
    (dharma / "a2a_bus" / "state" / "liveseat.json").write_text(json.dumps({"process_running": True}))
    # H4: a real signed lease in the seat's own store + an observed PEP refusal.
    # Exercises the whole sign -> verify -> enforce -> refuse path, not a bare file.
    from dharma_swarm import holon_signing as hs
    from dharma_swarm import holon_pep as pep
    lease = hs.issue_lease(holon="liveseat", scope=[hs.READ_ONLY, hs.REPLY_ONLY], ttl_s=3600,
                           signer_key_pem=home / "keys" / "ed25519_private.pem", issuer="liveseat")
    hs.write_lease(lease, agents_root=root)
    with pytest.raises(pep.LeaseDenied):  # unleased operator-only action -> refusal receipt
        pep.enforce_lease("liveseat", hs.GIT_PUSH, agents_root=root)
    (dharma / "agent_memory" / "liveseat").mkdir(parents=True)
    (dharma / "agent_memory" / "liveseat" / "MEMORY.md").write_text("who i am")
    (dharma / "agent_memory" / "liveseat" / ".growth_loop").write_text("")
    nest = dharma / "external_agents" / "liveseat" / "nest"
    nest.mkdir(parents=True)
    (nest / "heartbeat.json").write_text(json.dumps({"wake_loop_active": True}))
    (home / "wake").mkdir()
    (home / "wake" / "wake_proof.log").write_text("FABLE_WAKE_PROOF_OK")
    # point the module's dharma roots at tmp
    monkeypatch.setattr(hg, "HEARTBEATS", dharma / "a2a_bus" / "bridge_heartbeats")
    monkeypatch.setattr(hg, "STATES", dharma / "a2a_bus" / "state")
    monkeypatch.setattr(hg, "LEASES", dharma / "a2a_bus" / "leases")
    monkeypatch.setattr(hg, "DHARMA", dharma)

    grade = hg.grade_agent("liveseat", agents_root=root)
    shape = [(a.id, a.points, a.evidence) for a in grade.axes if a.invariant]
    assert grade.has_holon_shape, f"live fixture should have holon shape: {shape}"
    # every invariant axis should be live-durable => holon-grade LIVE
    assert grade.is_holon_grade_live, f"live fixture invariant axes not all 2: {shape}"


def test_h4_theater_lease_does_not_pass(tmp_path):
    """A bare/unsigned lease file must NOT score H4=2 — the exact theater the H4 gap named.

    The old check scored 2 for any non-empty lease dir. A real authority envelope
    requires a signed, verifiable lease, so an unsigned file scores 0.
    """
    root = tmp_path / "agents"
    home = _seat(root, "faker", real_key=True)
    (home / "leases").mkdir()
    (home / "leases" / "bare.json").write_text("{}")  # unsigned = theater
    grade = hg.grade_agent("faker", agents_root=root)
    h4 = next(a for a in grade.axes if a.id == "H4_authority_envelope")
    assert h4.points == 0, f"unsigned lease scored {h4.points}: {h4.evidence}"
    assert "theater" in h4.evidence


def test_grade_is_deterministic(tmp_path):
    root = tmp_path / "agents"
    _seat(root, "seat")
    a = hg.grade_agent("seat", agents_root=root)
    b = hg.grade_agent("seat", agents_root=root)
    assert a.digest == b.digest
    assert a.score == b.score


def test_assert_holon_grade_raises_on_ghost(tmp_path):
    root = tmp_path / "agents"
    (root / "ghost").mkdir(parents=True)
    (root / "ghost" / "identity.json").write_text("{}")
    with pytest.raises(hg.HolonGradeError):
        # grade under a temp root by monkeypatching the module default
        import dharma_swarm.holon_grade as m
        orig = m.AGENTS_ROOT
        m.AGENTS_ROOT = root
        try:
            m.assert_holon_grade("ghost")
        finally:
            m.AGENTS_ROOT = orig


def test_frontier_ladder_well_formed():
    # the beyond-hermes sovereign tier is present, well-formed, and all ABSENT (nothing built yet).
    assert len(hg.BEYOND_HERMES) == 5
    ids = [f.id for f in hg.BEYOND_HERMES]
    assert ids[0].startswith("F1") and ids[-1].startswith("F5")
    targets = hg.frontier_targets("nonexistent_seat")
    assert all(t["status"] == "ABSENT" for t in targets)
    assert len(hg.BEYOND_HERMES_BLIND_SPOTS) >= 5  # completeness-critic gaps carried in code


def test_prescribe_climb_on_weak_seat(tmp_path):
    root = tmp_path / "agents"
    (root / "weak").mkdir(parents=True)
    (root / "weak" / "identity.json").write_text("{}")
    grade = hg.grade_agent("weak", agents_root=root)
    rx = hg.prescribe_climb(grade)
    assert rx, "a weak seat should get at least one prescribed frontier rung"
