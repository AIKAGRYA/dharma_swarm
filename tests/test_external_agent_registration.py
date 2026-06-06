"""Tests for Stage-1 external roaming worker registration."""

from __future__ import annotations

import json

import pytest

from dharma_swarm.external_agent_registration import (
    AutonomyPolicy,
    ExternalAgentAuthority,
    ExternalAgentStatus,
    ExternalRoamingWorker,
    FORBIDDEN_MUTATION_FILES,
    IDENTITY_INVARIANT_DIGEST_FIELDS,
    IdentityInvariant,
    KIMI_2_6_REGISTRATION,
    STAGE_1_ALLOWED_AUTHORITIES,
    WorkspacePolicy,
    assert_mutation_allowed,
    compute_identity_invariant_digest,
    external_agent_sandbox_root,
    kimi_2_6_registration,
    load_external_worker,
    register_external_worker,
    validate_sandbox_path,
    verify_identity,
)


# ---------------------------------------------------------------------------
# Identity invariant — producer + verifier
# ---------------------------------------------------------------------------

# Ground-truth digest of the live opus_composer seat (frozen 2026-05-31).
# The producer MUST reproduce this exactly so historical records verify rather
# than being silently rewritten.
_OPUS_INVARIANT_FIELDS = {
    "schema_version": "dharma_identity_invariant.v1",
    "agent_uid": "opus_composer",
    "authority_floor": "external_worker_evidence_only",
    "memory_namespace": "agent:opus_composer",
    "trace_identity": "trace:opus_composer",
    "serial": "AGT-OPUS_COMPOSER",
    "created_at": "2026-05-31T17:02:33.129979+00:00",
}
_OPUS_DIGEST = (
    "sha256:8b144f48c9ac2aced0fb80ea5a63bb77911107b1e01b979f4f87cfe69e5487cd"
)


def test_producer_reproduces_live_digest():
    assert compute_identity_invariant_digest(_OPUS_INVARIANT_FIELDS) == _OPUS_DIGEST


def test_identity_invariant_seals_digest():
    inv = IdentityInvariant(**_OPUS_INVARIANT_FIELDS)
    assert inv.digest == _OPUS_DIGEST
    # round-trip
    assert IdentityInvariant.from_record(inv.to_record()).digest == _OPUS_DIGEST
    assert list(inv.to_record().keys()) == [*IDENTITY_INVARIANT_DIGEST_FIELDS, "digest"]


def test_identity_invariant_rejects_tampered_digest():
    with pytest.raises(ValueError, match="digest mismatch"):
        IdentityInvariant(**_OPUS_INVARIANT_FIELDS, digest="sha256:deadbeef")


def test_worker_derives_invariant(tmp_path):
    worker = ExternalRoamingWorker(
        agent_uid="opus_composer",
        callsign="opus_composer",
        display_name="Opus Composer",
        harness="claude_code_headless",
        model_identity="claude-opus-4-8",
        role="lead_orchestrator",
        squad_id="inner_circle",
        workspace_policy=WorkspacePolicy(
            sandbox_root=str(tmp_path / "external_agents" / "opus_composer"),
        ),
        memory_namespace="agent:opus_composer",
        trace_identity="trace:opus_composer",
    )
    assert worker.serial() == "AGT-OPUS_COMPOSER"
    inv = worker.to_identity_invariant(
        created_at="2026-05-31T17:02:33.129979+00:00"
    )
    assert inv.digest == _OPUS_DIGEST


@pytest.mark.asyncio
async def test_verify_identity_round_trip_and_loader(tmp_path):
    home = tmp_path / ".dharma"
    worker = ExternalRoamingWorker(
        agent_uid="opus_composer",
        callsign="opus_composer",
        display_name="Opus Composer",
        harness="claude_code_headless",
        model_identity="claude-opus-4-8",
        role="lead_orchestrator",
        squad_id="inner_circle",
        workspace_policy=WorkspacePolicy(
            sandbox_root=str(home / "external_agents" / "opus_composer"),
        ),
        memory_namespace="agent:opus_composer",
        trace_identity="trace:opus_composer",
    )
    await register_external_worker(worker, dharma_home=home)

    # Loader reads registration.json back through the schema (re-validates).
    loaded = load_external_worker("opus_composer", dharma_home=home)
    assert loaded.model_identity == "claude-opus-4-8"
    assert loaded.role == "lead_orchestrator"
    assert loaded.memory_namespace == "agent:opus_composer"

    # Stamp the derived invariant onto registration.json + a flat copy + the
    # card, exactly as the live reconciliation does, then verify coherence.
    import json as _json

    base = home / "external_agents" / "opus_composer"
    reg = _json.loads((base / "registration.json").read_text())
    inv = loaded.to_identity_invariant(created_at=reg["created_at"]).to_record()
    reg["identity_invariant"] = inv
    (base / "registration.json").write_text(_json.dumps(reg, indent=2))
    (base / "identity_invariant.json").write_text(_json.dumps(inv, indent=2))

    card_path = home / "a2a" / "cards" / "opus_composer.json"
    card = _json.loads(card_path.read_text())
    card.setdefault("metadata", {})["identity_invariant"] = inv
    card["role"] = "lead_orchestrator"
    card["model"] = "claude-opus-4-8"
    card_path.write_text(_json.dumps(card, indent=2))

    dock_path = home / "agents" / "opus_composer" / "living_agent.json"
    dock = _json.loads(dock_path.read_text())
    dock["identity_invariant"] = inv
    dock_path.write_text(_json.dumps(dock, indent=2))

    # Stamp the runtime.db row metadata (the canonical onboarding created it).
    import sqlite3

    db_path = home / "state" / "runtime.db"
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT metadata_json FROM agent_identity WHERE agent_id='opus_composer'"
    ).fetchone()
    meta = _json.loads(row[0] or "{}")
    meta["identity_invariant"] = inv
    conn.execute(
        "UPDATE agent_identity SET metadata_json=?, specialization=? "
        "WHERE agent_id='opus_composer'",
        (_json.dumps(meta), "lead_orchestrator"),
    )
    conn.commit()
    conn.close()

    report = verify_identity("opus_composer", dharma_home=home)
    assert report["ok"], report["mismatches"]
    assert report["expected_digest"] == report["surfaces"]["registration.json"]["digest"]
    assert report["surfaces"]["a2a_card"]["digest"] == report["expected_digest"]
    assert report["surfaces"]["living_agent.json"]["digest"] == report["expected_digest"]
    assert report["surfaces"]["runtime_db"]["digest"] == report["expected_digest"]


@pytest.mark.asyncio
async def test_verify_identity_catches_drift(tmp_path):
    home = tmp_path / ".dharma"
    worker = ExternalRoamingWorker(
        agent_uid="opus_composer",
        callsign="opus_composer",
        display_name="Opus Composer",
        harness="claude_code_headless",
        model_identity="claude-opus-4-8",
        role="lead_orchestrator",
        squad_id="inner_circle",
        workspace_policy=WorkspacePolicy(
            sandbox_root=str(home / "external_agents" / "opus_composer"),
        ),
        memory_namespace="agent:opus_composer",
        trace_identity="trace:opus_composer",
    )
    await register_external_worker(worker, dharma_home=home)
    import json as _json

    base = home / "external_agents" / "opus_composer"
    reg = _json.loads((base / "registration.json").read_text())
    inv = worker.to_identity_invariant(created_at=reg["created_at"]).to_record()
    reg["identity_invariant"] = inv
    (base / "registration.json").write_text(_json.dumps(reg, indent=2))
    # Inject a drifted role onto the a2a card.
    card_path = home / "a2a" / "cards" / "opus_composer.json"
    card = _json.loads(card_path.read_text())
    card.setdefault("metadata", {})["identity_invariant"] = inv
    card["role"] = "traverse-fix-wiring"  # the historical conflict
    card_path.write_text(_json.dumps(card, indent=2))

    report = verify_identity("opus_composer", dharma_home=home)
    assert not report["ok"]
    assert any("a2a card role" in m for m in report["mismatches"])


# ---------------------------------------------------------------------------
# Schema basics
# ---------------------------------------------------------------------------


def _good_workspace(tmp_path) -> WorkspacePolicy:
    return WorkspacePolicy(
        sandbox_root=str(tmp_path / ".dharma" / "external_agents" / "demo"),
    )


def test_minimum_valid_external_worker(tmp_path):
    worker = ExternalRoamingWorker(
        agent_uid="demo_worker",
        callsign="demo-worker",
        display_name="Demo external worker",
        harness="demo_harness",
        workspace_policy=_good_workspace(tmp_path),
        memory_namespace="agent:demo_worker",
        trace_identity="trace:demo_worker",
    )
    assert worker.authority is ExternalAgentAuthority.EXTERNAL_WORKER_EVIDENCE_ONLY
    assert worker.status is ExternalAgentStatus.REGISTERED
    assert worker.autonomy_policy.requires_approval is True
    assert worker.autonomy_policy.explicit_task_assignment_required is True


@pytest.mark.parametrize(
    "callsign",
    ["", "Bad Caps", "ends-", "-starts", "x", "with/slash", "kimi claw"],
)
def test_callsign_shape_rejected(tmp_path, callsign):
    with pytest.raises(Exception):
        ExternalRoamingWorker(
            agent_uid="demo_worker",
            callsign=callsign,
            display_name="x",
            harness="h",
            workspace_policy=_good_workspace(tmp_path),
            memory_namespace="agent:demo_worker",
            trace_identity="trace:demo_worker",
        )


def test_memory_namespace_must_be_scoped(tmp_path):
    with pytest.raises(Exception):
        ExternalRoamingWorker(
            agent_uid="demo_worker",
            callsign="demo-worker",
            display_name="x",
            harness="h",
            workspace_policy=_good_workspace(tmp_path),
            memory_namespace="agent:other",
            trace_identity="trace:demo_worker",
        )


def test_workspace_policy_rejects_non_sandbox_root(tmp_path):
    with pytest.raises(Exception):
        WorkspacePolicy(sandbox_root=str(tmp_path / "outside"))


# ---------------------------------------------------------------------------
# Authority guards
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "level",
    [
        ExternalAgentAuthority.ASSIGNED_TASK_ONLY,
        ExternalAgentAuthority.FULL_RUNTIME,
    ],
)
def test_high_authority_levels_rejected_at_stage_1(tmp_path, level):
    with pytest.raises(Exception):
        ExternalRoamingWorker(
            agent_uid="demo_worker",
            callsign="demo-worker",
            display_name="x",
            harness="h",
            authority=level,
            workspace_policy=_good_workspace(tmp_path),
            memory_namespace="agent:demo_worker",
            trace_identity="trace:demo_worker",
        )


def test_stage_1_allowed_authorities_set():
    assert ExternalAgentAuthority.EXTERNAL_WORKER_EVIDENCE_ONLY in STAGE_1_ALLOWED_AUTHORITIES
    assert ExternalAgentAuthority.SANDBOX_WRITE in STAGE_1_ALLOWED_AUTHORITIES
    assert ExternalAgentAuthority.FULL_RUNTIME not in STAGE_1_ALLOWED_AUTHORITIES


@pytest.mark.parametrize(
    "field_name",
    [
        "can_approve_prs",
        "can_write_source",
        "can_mutate_meta_dharma",
        "can_mutate_telos",
        "can_mutate_dharma_kernel",
        "can_mutate_dgm_protected",
        "can_author_context_bundles",
    ],
)
def test_autonomy_policy_refuses_dangerous_flag(field_name):
    with pytest.raises(Exception):
        AutonomyPolicy(**{field_name: True})


def test_autonomy_policy_requires_approval_at_stage_1():
    with pytest.raises(Exception):
        AutonomyPolicy(requires_approval=False)


@pytest.mark.parametrize(
    "field_name",
    [
        "repo_writes_allowed",
        "canonical_dharma_dir_writes_allowed",
    ],
)
def test_workspace_policy_refuses_non_sandbox_writes(tmp_path, field_name):
    with pytest.raises(Exception):
        WorkspacePolicy(
            sandbox_root=str(tmp_path / ".dharma" / "external_agents" / "demo"),
            **{field_name: True},
        )


# ---------------------------------------------------------------------------
# Forbidden-mutation guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "telos_gates.py",
        "dharma_kernel.py",
        "meta_dharma.py",
        "evolution.py",
        "config.py",
        "context_bundle.py",
        "context_bundles.py",
    ],
)
def test_assert_mutation_allowed_blocks_protected(name):
    assert name in FORBIDDEN_MUTATION_FILES
    with pytest.raises(PermissionError):
        assert_mutation_allowed(name)
    with pytest.raises(PermissionError):
        assert_mutation_allowed(f"some/sub/dir/{name}")


def test_assert_mutation_allowed_passes_normal_target():
    assert_mutation_allowed("dharma_swarm/external_agent_registration.py")
    assert_mutation_allowed("README.md")


# ---------------------------------------------------------------------------
# Sandbox path validator
# ---------------------------------------------------------------------------


def test_validate_sandbox_path_accepts_inside(tmp_path):
    home = tmp_path / ".dharma"
    inside = external_agent_sandbox_root(home) / "demo" / "heartbeat.json"
    inside.parent.mkdir(parents=True, exist_ok=True)
    inside.write_text("{}", encoding="utf-8")
    resolved = validate_sandbox_path(inside, dharma_home=home)
    assert resolved.exists()


def test_validate_sandbox_path_rejects_repo_root(tmp_path):
    home = tmp_path / ".dharma"
    with pytest.raises(PermissionError):
        validate_sandbox_path(tmp_path / "some_repo_file.py", dharma_home=home)


def test_validate_sandbox_path_rejects_repo_dot_dharma(tmp_path):
    home = tmp_path / ".dharma"
    repo_root_dot_dharma = tmp_path / "repo" / ".dharma" / "ginko" / "agents" / "kimi" / "id.json"
    repo_root_dot_dharma.parent.mkdir(parents=True, exist_ok=True)
    repo_root_dot_dharma.write_text("{}", encoding="utf-8")
    with pytest.raises(PermissionError):
        validate_sandbox_path(repo_root_dot_dharma, dharma_home=home)


# ---------------------------------------------------------------------------
# Kimi 2.6 record
# ---------------------------------------------------------------------------


def test_kimi_2_6_registration_evidence_only():
    rec = KIMI_2_6_REGISTRATION
    assert rec.agent_uid == "kimi_2_6_claw"
    assert rec.callsign == "kimi-claw-phone"
    assert rec.authority is ExternalAgentAuthority.EXTERNAL_WORKER_EVIDENCE_ONLY
    assert rec.is_returning_historical_embodiment is True
    assert rec.metadata.get("automatic_authority_inheritance") is False
    assert rec.metadata.get("mailbox_is_transport_only") is True
    # No high authority leaks through autonomy_policy.
    pol = rec.autonomy_policy
    assert pol.can_approve_prs is False
    assert pol.can_write_source is False
    assert pol.can_mutate_meta_dharma is False
    assert pol.can_mutate_telos is False
    assert pol.can_mutate_dharma_kernel is False
    assert pol.can_mutate_dgm_protected is False
    assert pol.can_author_context_bundles is False
    assert pol.explicit_task_assignment_required is True


def test_kimi_2_6_factory_uses_dharma_home(tmp_path):
    rec = kimi_2_6_registration(dharma_home=tmp_path / ".dharma")
    sandbox = rec.workspace_policy.sandbox_root
    assert "external_agents" in sandbox
    assert sandbox.endswith("kimi_2_6_claw")
    assert rec.workspace_policy.repo_writes_allowed is False
    assert rec.workspace_policy.canonical_dharma_dir_writes_allowed is False


# ---------------------------------------------------------------------------
# Registration helper end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_external_worker_writes_record_and_onboards_kimi(tmp_path):
    home = tmp_path / ".dharma"
    rec = kimi_2_6_registration(dharma_home=home)
    result = await register_external_worker(rec, dharma_home=home)

    record_path = home / "external_agents" / "kimi_2_6_claw" / "registration.json"
    assert record_path.exists()
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    assert payload["agent_uid"] == "kimi_2_6_claw"
    assert payload["authority"] == "external_worker_evidence_only"
    assert payload["is_returning_historical_embodiment"] is True

    receipt = result["onboarding_receipt"]
    assert receipt["agent_uid"] == "kimi_2_6_claw"
    assert receipt["callsign"] == "kimi-claw-phone"

    dock = json.loads(
        (home / "agents" / "kimi_2_6_claw" / "living_agent.json").read_text(
            encoding="utf-8"
        )
    )
    md = dock["current_embodiment"]["metadata"]
    assert md["authority"] == "external_worker_evidence_only"
    assert md["registration_stage"] == "stage_1_external_evidence_only"
    assert md["autonomy_policy"]["can_approve_prs"] is False
    assert md["autonomy_policy"]["can_mutate_meta_dharma"] is False


@pytest.mark.asyncio
async def test_register_external_worker_skip_canonical(tmp_path):
    home = tmp_path / ".dharma"
    rec = kimi_2_6_registration(dharma_home=home)
    result = await register_external_worker(
        rec, dharma_home=home, write_canonical_onboarding=False
    )
    assert "onboarding_receipt" not in result
    record_path = home / "external_agents" / "kimi_2_6_claw" / "registration.json"
    assert record_path.exists()
    # Canonical living_agent.json should not have been created.
    assert not (home / "agents" / "kimi_2_6_claw" / "living_agent.json").exists()
