"""Contract and adversarial tests for HelmContextEnvelope v1."""
from __future__ import annotations
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import threading
from typing import Any
import pytest
from dharma_swarm.agent_runner import AgentPool
from dharma_swarm.a2a.contact_registry import A2AContact, ContactRegistry
from dharma_swarm.operator_core.helm_context import (
    HELM_CONTEXT_REGIONS, MAX_HELM_CONTEXT_BYTES, AuthorityModality, AuthorityStamp,
    HelmContextEnvelope, HelmContextError, HelmUIState,
    OperatorActionDescriptor, ProjectionStatus, decode_helm_context, encode_helm_context,
    format_rfc3339, parse_rfc3339, seal_helm_context,
)
from dharma_swarm.operator_core.helm_context_projection import (
    HelmBridgeSnapshot,
    HelmContextSources,
    build_helm_context,
    run_bounded_sync,
)
from dharma_swarm.operator_core.session_store import SessionStore
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.swarm import SwarmManager
from dharma_swarm.task_board import TaskBoard
NOW = datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc)
EPOCH = "runtime-epoch-test"
NAV = ("home", "conversation", "activity", "evidence", "system")
def _ui() -> HelmUIState:
    return HelmUIState("zen", "conversation", "chat", "none", "composer", NAV)
def _workspace() -> dict[str, object]:
    return {
        "workspace_path": "/workspace/dharma_swarm", "workspace": "dharma_swarm",
        "repository": "dharma_swarm", "repository_identity": "AIKAGRYA/dharma_swarm",
        "remote": "github.com/AIKAGRYA/dharma_swarm", "branch": "agent/test",
        "head": "a" * 40, "upstream": None, "ahead": 0, "behind": 0,
        "staged": 0, "unstaged": 0, "untracked": 0,
    }
def _bridge() -> dict[str, object]:
    return {
        "bridge_status": "connected", "active_session_id": None, "active_phase": None,
        "requested_provider_id": "openrouter", "requested_model_id": "openai/gpt-5.6",
        "served_provider_id": None, "served_model_id": None,
        "served_identity_source": "unavailable", "served_identity_observed_at": None,
        "route_evidence_expires_at": None, "route_evidence_freshness": "unavailable",
        "route_receipt_ref": None, "route_receipt_sha256": None,
        "route_verifier_id": None, "route_verifier_version": None,
        "route_evidence_synthetic": None, "route_verdict": "UNKNOWN",
        "route_verdict_reason": "route_not_evaluated", "route_exact_model_proven": False,
        "route_seat_id": None, "route_verification_evaluated_at": None,
    }
def _build(sources: HelmContextSources | None = None, **kwargs: object) -> HelmContextEnvelope:
    return asyncio.run(build_helm_context(
        sources or HelmContextSources(), ui=_ui(), runtime_epoch=EPOCH, now=NOW, **kwargs,
    ))
def _files(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
class MissionOwner:
    def __init__(self, observed_at: object = NOW) -> None:
        self.observed_at = observed_at
    async def get_snapshot(self, mission_id: str) -> dict[str, object]:
        return {
            "mission": {"id": mission_id, "title": "Bounded mission", "status": "active"},
            "observed_at": self.observed_at, "raw_metadata": {"token": "do-not-leak"},
        }
class TaskOwner:
    async def list_tasks(self, *, limit: int) -> list[dict[str, object]]:
        assert limit == 32
        return [{
            "id": "task-1", "title": "Inspect", "status": "pending", "priority": "normal",
            "assigned_to": None, "depends_on": [], "blocked_by": [], "updated_at": NOW,
            "description": "Bearer task-description-secret", "result": "sk-proj-result-secret",
            "metadata": {"OPENAI_API_KEY": "sk-proj-metadata-secret"},
        }]
class RuntimeOwner:
    def list_sessions_sync(self, *, limit: int) -> list[dict[str, object]]:
        assert limit == 32
        return [{"session_id": "run-1", "status": "active", "current_task_id": "task-1", "active_bundle_id": None, "updated_at": NOW, "runtime_epoch": EPOCH, "metadata": {"token": "secret"}}]
    async def list_runtime_receipts(self, *, limit: int) -> list[dict[str, object]]:
        assert limit == 32
        return [{"receipt_id": "receipt-1", "receipt_type": "dispatch", "status": "recorded", "run_id": "run-1", "task_id": "task-1", "agent_id": "agent-1", "created_at": NOW, "payload": {"authorization": "Bearer hidden"}}]
class SessionOwner:
    def list_sessions(self) -> list[dict[str, object]]:
        return [{"session_id": "chat-1", "status": "completed", "title": "Helm", "provider_id": "openrouter", "model_id": "openai/gpt-5.6", "total_turns": 2, "updated_at": NOW, "runtime_owner_id": EPOCH, "provider_raw_metadata": "hidden"}]
class SwarmOwner:
    async def status(self) -> dict[str, object]:
        return {"observed_at": NOW, "agents": [{"id": "agent-1", "name": "Reader", "role": "researcher", "status": "idle", "current_task": None, "provider": "anthropic", "model": "fable-5", "last_heartbeat": NOW, "error": "Bearer hidden"}], "tasks_pending": 1, "tasks_running": 0, "tasks_completed": 2, "tasks_failed": 0}
class A2AOwner:
    def __init__(self, count: int = 1) -> None:
        self.count = count
    def list_all(self) -> list[dict[str, object]]:
        return [{"agent_uid": f"remote-{index}", "kind": "cloud_agent", "display_name": f"Remote {index}", "capabilities": ["reason"], "outbound_endpoint": "nats://credential@host"} for index in range(self.count)]
class EvolutionOwner:
    async def list_entries(self) -> list[dict[str, object]]:
        return [{"id": "evo-1", "timestamp": NOW, "parent_id": None, "component": "helm", "change_type": "patch", "spec_ref": None, "commit_hash": None, "evidence_tier": "unvalidated", "promotion_state": "candidate", "status": "proposed", "agent_id": "agent-1", "model": "fable-5", "tokens_used": 10, "gates_passed": [], "gates_failed": [], "diff": "Bearer secret diff", "test_results": {"token": "hidden"}}]
def _synthetic_sources() -> HelmContextSources:
    action = OperatorActionDescriptor("swarm.plan", "Plan swarm objective", "SyntheticEvaluator", ("construct held plan",), "workspace_mutation", True, True, "swarm.cancel")
    return HelmContextSources(
        workspace_state=_workspace(), bridge_session_state=_bridge(), mission_control=MissionOwner(),
        task_board=TaskOwner(), runtime_state=RuntimeOwner(), session_store=SessionOwner(),
        swarm=SwarmOwner(), a2a=A2AOwner(), evolution=EvolutionOwner(),
        operator_actions=(action,), mission_id="mission-1",
    )
def test_absent_owners_are_honestly_unavailable_and_actions_are_not_invented(tmp_path: Path) -> None:
    untouched = tmp_path / "runtime-state-that-must-not-exist"
    envelope = _build()
    assert tuple(envelope.projections) == HELM_CONTEXT_REGIONS
    assert envelope.projections["ui"].status is ProjectionStatus.CONFIGURED
    for region in set(HELM_CONTEXT_REGIONS) - {"ui"}:
        block = envelope.projections[region]
        assert block.status is ProjectionStatus.UNAVAILABLE
        assert block.authority.modality is AuthorityModality.UNKNOWN
        assert block.data == {} and block.unavailable_reason
    assert not untouched.exists()
def test_synthetic_fixture_uses_exact_summaries_without_raw_owner_payloads() -> None:
    envelope = _build(_synthetic_sources(), synthetic=True)
    assert all(block.status is ProjectionStatus.CONFIGURED for block in envelope.projections.values())
    assert all(block.authority.owner == "SyntheticHelmContextFixture" for block in envelope.projections.values())
    payload = encode_helm_context(envelope)
    for forbidden in (b"task-description-secret", b"result-secret", b"metadata-secret", b"secret diff", b"outbound_endpoint", b"provider_raw_metadata"):
        assert forbidden not in payload
    assert envelope.projections["task_board"].data["tasks"]["items"][0]["task_id"] == "task-1"
    assert envelope.projections["receipts"].data["receipts"]["items"][0]["receipt_id"] == "receipt-1"
def test_noncanonical_production_owners_are_rejected_before_any_method_call() -> None:
    class Trap:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"noncanonical owner accessed: {name}")
    sources = HelmContextSources(mission_control=Trap(), task_board=Trap(), runtime_state=Trap(), session_store=Trap(), swarm=Trap(), a2a=Trap(), evolution=Trap(), mission_id="m")
    envelope = _build(sources)
    for region in ("mission_control", "task_board", "runtime_state", "session", "receipts", "swarm", "a2a", "evolution"):
        assert envelope.projections[region].status is ProjectionStatus.UNAVAILABLE
    assert envelope.projections["task_board"].unavailable_reason == "noncanonical_owner_rejected"
def test_raw_bridge_snapshots_and_unavailable_actions_cannot_execute_or_impersonate() -> None:
    class TrapAction:
        def to_dict(self) -> dict[str, object]:
            raise AssertionError("unavailable action must not be read")
    sources = HelmContextSources(workspace_state=_workspace(), bridge_session_state=_bridge(), operator_actions=(TrapAction(),))  # type: ignore[arg-type]
    envelope = _build(sources)
    assert envelope.projections["workspace"].status is ProjectionStatus.UNAVAILABLE
    assert envelope.projections["bridge_session"].status is ProjectionStatus.UNAVAILABLE
    assert envelope.projections["actions"].unavailable_reason == "action_evaluator_not_integrated"
    with pytest.raises(HelmContextError, match="not issued"):
        HelmBridgeSnapshot("workspace", _workspace())
def test_canonical_session_store_read_is_side_effect_free(tmp_path: Path) -> None:
    store = SessionStore(root=tmp_path / "sessions")
    before = _files(tmp_path)
    envelope = _build(HelmContextSources(session_store=store))
    assert envelope.projections["session"].status is ProjectionStatus.OBSERVED
    assert envelope.projections["session"].data["sessions"]["total"] == 0
    assert _files(tmp_path) == before
def test_canonical_session_secret_is_rejected_without_serialization(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = object.__new__(SessionStore)
    monkeypatch.setattr(SessionStore, "list_sessions", lambda self: [{"session_id": "chat", "status": "completed", "title": "sk-or-v1-abcdefgh12345678", "provider_id": "provider", "model_id": "model", "total_turns": 1, "updated_at": NOW, "runtime_owner_id": EPOCH}])
    envelope = _build(HelmContextSources(session_store=owner))
    assert envelope.projections["session"].status is ProjectionStatus.UNAVAILABLE
    assert b"sk-or-v1" not in encode_helm_context(envelope)
def test_runtime_state_without_pure_projection_is_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = object.__new__(RuntimeStateStore)
    monkeypatch.setattr(RuntimeStateStore, "list_sessions_sync", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not read")))
    envelope = _build(HelmContextSources(runtime_state=owner))
    assert envelope.projections["runtime_state"].unavailable_reason == "pure_read_projection_unavailable"
    assert envelope.projections["receipts"].unavailable_reason == "pure_read_projection_unavailable"
def test_task_board_without_pure_projection_is_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = object.__new__(TaskBoard)
    monkeypatch.setattr(TaskBoard, "list_tasks", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not read")))
    envelope = _build(HelmContextSources(task_board=owner))
    assert envelope.projections["task_board"].unavailable_reason == "pure_read_projection_unavailable"
def test_a2a_registry_is_configuration_not_liveness() -> None:
    registry = ContactRegistry((A2AContact("cloud-one", "cloud_agent", "Cloud One", "inbox", "nats://secret", ("reason",), {"token": "hidden"}),))
    envelope = _build(HelmContextSources(a2a=registry))
    block = envelope.projections["a2a"]
    assert block.status is ProjectionStatus.CONFIGURED
    assert block.data["contacts"]["items"][0] == {"agent_uid": "cloud-one", "kind": "cloud_agent", "display_name": "Cloud One", "capability_count": 1}
    assert b"nats://" not in encode_helm_context(envelope)
def test_agent_pool_projection_has_exact_owner_and_source(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = object.__new__(AgentPool)
    effects: list[str] = []
    monkeypatch.setattr(AgentPool, "list_agents", lambda self: [])
    owner.status = lambda: effects.append("status")  # type: ignore[attr-defined]
    owner.list_agents = lambda: effects.append("list_agents")  # type: ignore[method-assign]
    projection = _build(HelmContextSources(swarm=owner)).projections["swarm"]
    assert projection.status is ProjectionStatus.UNVERIFIED
    assert projection.authority.owner == "AgentPool"
    assert projection.authority.source == "AgentPool.list_agents"
    assert effects == []
def test_owner_timestamp_created_during_read_precedes_final_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = object.__new__(SwarmManager)
    async def status(self) -> dict[str, object]:
        await asyncio.sleep(0.005)
        return {"timestamp": NOW + timedelta(milliseconds=4), "agents": [], "tasks_pending": 0, "tasks_running": 0, "tasks_completed": 0, "tasks_failed": 0}
    monkeypatch.setattr(SwarmManager, "status", status)
    envelope = asyncio.run(build_helm_context(
        HelmContextSources(swarm=owner), ui=_ui(), runtime_epoch=EPOCH,
        now=NOW, synthetic=False, advance_clock=True,
    ))
    assert envelope.projections["swarm"].status is ProjectionStatus.UNVERIFIED
    assert parse_rfc3339(envelope.projections["swarm"].authority.observed_at) <= parse_rfc3339(envelope.generated_at)
def test_round_trip_digest_unicode_and_immutability() -> None:
    workspace = _workspace()
    workspace["repository"] = "日本語"
    envelope = _build(HelmContextSources(workspace_state=workspace, bridge_session_state=_bridge()), synthetic=True)
    encoded = encode_helm_context(envelope)
    decoded = decode_helm_context(encoded)
    assert decoded.to_dict() == envelope.to_dict() and b"\\u65e5" not in encoded
    with pytest.raises(TypeError):
        decoded.projections["workspace"].data["repository"] = "mutated"  # type: ignore[index]
    tampered = json.loads(encoded)
    tampered["projections"]["workspace"]["data"]["repository"] = "other"
    with pytest.raises(HelmContextError, match="digest mismatch"):
        decode_helm_context(tampered)
def test_exact_region_schema_rejects_structurally_valid_bogus_ui_and_workspace() -> None:
    payload = _build(HelmContextSources(workspace_state=_workspace(), bridge_session_state=_bridge()), synthetic=True).to_dict()
    payload["projections"]["workspace"]["data"] = {}
    with pytest.raises(HelmContextError, match="keys are not exact"):
        decode_helm_context(payload)
    payload = _build(HelmContextSources(workspace_state=_workspace()), synthetic=True).to_dict()
    payload["projections"]["workspace"]["data"].update({"workspace_path": "/", "workspace": "", "repository": ""})
    with pytest.raises(HelmContextError, match="workspace path"):
        decode_helm_context(payload)
    for workspace_path in ("/workspace/dharma_swarm/", "/workspace//dharma_swarm"):
        workspace = _workspace()
        workspace["workspace_path"] = workspace_path
        assert _build(HelmContextSources(workspace_state=workspace)).projections["workspace"].status is ProjectionStatus.UNAVAILABLE
    payload = _build().to_dict()
    payload["projections"]["ui"]["data"]["face"] = "not-a-face"
    with pytest.raises(HelmContextError, match="UI|coordinates"):
        decode_helm_context(payload)
    with pytest.raises(HelmContextError, match="coordinates"):
        HelmUIState("zen", "home", "chat", "none", "composer", NAV)
@pytest.mark.parametrize("secret", ["sk-proj-abcdefgh12345678", "sk-or-v1-abcdefgh12345678", "gho_abcdefgh12345678", "xai-abcdefgh12345678", "AIzaabcdefgh", "xapp-abcdefgh12345678", "xoxa-abcdefgh12345678", "xoxc-abcdefgh12345678", "xoxd-abcdefgh12345678", "xoxs-abcdefgh12345678", "https://operator:password@example.invalid/path", "https://:password@example.invalid", "https://user:@example.invalid", "https://token@example.invalid", "https://user%3Apass@example.invalid", "provider failed: Bearer abcdefgh123456", "AKIAABCDEFGHIJKLMNOP", "-----BEGIN PRIVATE KEY----- material"])
def test_common_secret_shapes_fail_closed(secret: str) -> None:
    payload = _build(HelmContextSources(workspace_state=_workspace())).to_dict()
    payload["projections"]["workspace"]["data"]["repository_identity"] = secret
    with pytest.raises(HelmContextError, match="secret-shaped"):
        decode_helm_context(payload)
    injected = _workspace()
    injected["OPENAI_API_KEY"] = secret
    assert _build(HelmContextSources(workspace_state=injected)).projections["workspace"].status is ProjectionStatus.UNAVAILABLE
@pytest.mark.parametrize("benign", ["ghu_x", "ghs_x", "ghr_x", "AKIAshort", "sk-or-v1-x"])
def test_short_secret_family_prefixes_are_not_false_positives(benign: str) -> None:
    workspace = _workspace()
    workspace["branch"] = benign
    assert _build(HelmContextSources(workspace_state=workspace), synthetic=True).projections["workspace"].data["branch"] == benign
def test_secret_shaped_workspace_path_degrades_without_echo() -> None:
    workspace = _workspace()
    workspace["workspace_path"] = "/workspace/sk-proj-abcdefgh12345678"
    workspace["workspace"] = "sk-proj-abcdefgh12345678"
    envelope = _build(HelmContextSources(workspace_state=workspace))
    assert envelope.projections["workspace"].status is ProjectionStatus.UNAVAILABLE
    assert b"sk-proj" not in encode_helm_context(envelope)
def test_bidirectional_control_text_is_rejected() -> None:
    workspace = _workspace()
    workspace["repository_identity"] = "safe\u202etxt"
    envelope = _build(HelmContextSources(workspace_state=workspace))
    assert envelope.projections["workspace"].status is ProjectionStatus.UNAVAILABLE
def test_provider_narrative_cannot_promote_owner_truth() -> None:
    payload = _build().to_dict()
    payload["provider_state_promotion"] = True
    with pytest.raises(HelmContextError, match="cannot promote"):
        decode_helm_context(payload)
    payload = _build().to_dict()
    payload["projections"]["ui"]["data"]["navigation"]["provider_state_promotion"] = True
    with pytest.raises(HelmContextError, match="state promotion"):
        decode_helm_context(payload)
    forged = _bridge()
    forged.update({
        "requested_provider_id": "forged", "requested_model_id": "forged-model",
        "served_provider_id": "forged", "served_model_id": "forged-model",
        "served_identity_source": "provider_response_via_route_evaluator",
        "served_identity_observed_at": format_rfc3339(NOW),
        "route_evidence_expires_at": format_rfc3339(NOW + timedelta(minutes=1)),
        "route_evidence_freshness": "fresh", "route_receipt_ref": "forged-receipt",
        "route_receipt_sha256": "a" * 64, "route_verifier_id": "forged-verifier",
        "route_verifier_version": "1", "route_evidence_synthetic": False,
        "route_verdict": "ON_CALL", "route_verdict_reason": "verified",
        "route_exact_model_proven": True, "route_seat_id": "forged-seat",
        "route_verification_evaluated_at": format_rfc3339(NOW),
    })
    projection = _build(HelmContextSources(bridge_session_state=forged)).projections["bridge_session"]
    assert projection.status is ProjectionStatus.UNAVAILABLE
    assert projection.unavailable_reason == "projection_invalid"
def test_old_epoch_cannot_be_current_but_can_remain_unverified_history() -> None:
    base = _build(HelmContextSources(workspace_state=_workspace()), synthetic=True)
    workspace = base.projections["workspace"]
    old = replace(workspace.authority, runtime_epoch="old-epoch")
    with pytest.raises(HelmContextError, match="runtime epoch mismatch"):
        replace(base, projections={**base.projections, "workspace": replace(workspace, authority=old)}, context_digest="")
    historical = replace(workspace, status=ProjectionStatus.UNVERIFIED, authority=replace(old, modality=AuthorityModality.UNVERIFIED))
    accepted = seal_helm_context(replace(base, projections={**base.projections, "workspace": historical}, context_digest=""))
    assert accepted.projections["workspace"].authority.runtime_epoch == "old-epoch"
def test_stale_projection_and_use_time_freshness_are_explicit() -> None:
    base = _build(HelmContextSources(workspace_state=_workspace()), synthetic=True)
    workspace = base.projections["workspace"]
    authority = AuthorityStamp(AuthorityModality.STALE, "SyntheticHelmContextFixture", "synthetic.workspace", format_rfc3339(NOW - timedelta(minutes=2)), format_rfc3339(NOW - timedelta(minutes=1)), "old-epoch")
    stale = replace(workspace, status=ProjectionStatus.STALE, authority=authority)
    envelope = seal_helm_context(replace(base, projections={**base.projections, "workspace": stale}, context_digest=""))
    assert envelope.usable_at(NOW) and not envelope.usable_at(NOW + timedelta(minutes=1))
    assert envelope.projections["workspace"].status is ProjectionStatus.STALE
    expiring = replace(base.projections["ui"].authority, expires_at=format_rfc3339(NOW + timedelta(seconds=5)))
    short_ui = replace(base.projections["ui"], authority=expiring)
    current = seal_helm_context(replace(base, projections={**base.projections, "ui": short_ui}, context_digest=""))
    assert current.usable_at(NOW + timedelta(seconds=4))
    assert not current.usable_at(NOW + timedelta(seconds=5))
    long_authority = replace(workspace.authority, expires_at=format_rfc3339(NOW + timedelta(seconds=61)))
    with pytest.raises(HelmContextError, match="outside the envelope"):
        replace(base, projections={**base.projections, "workspace": replace(workspace, authority=long_authority)}, context_digest="")
    route = _bridge()
    route.update({
        "served_provider_id": "openrouter", "served_model_id": "openai/gpt-5.6",
        "served_identity_source": "provider_response_via_route_evaluator",
        "served_identity_observed_at": format_rfc3339(NOW - timedelta(seconds=1)),
        "route_evidence_expires_at": format_rfc3339(NOW + timedelta(seconds=5)),
        "route_evidence_freshness": "fresh", "route_receipt_ref": "receipt",
        "route_receipt_sha256": "a" * 64, "route_verifier_id": "verifier",
        "route_verifier_version": "1", "route_evidence_synthetic": False,
        "route_verdict": "ON_CALL", "route_verdict_reason": "verified",
        "route_exact_model_proven": True, "route_seat_id": "seat",
        "route_verification_evaluated_at": format_rfc3339(NOW),
    })
    routed = _build(HelmContextSources(bridge_session_state=route), synthetic=True)
    assert routed.usable_at(NOW + timedelta(seconds=4))
    assert not routed.usable_at(NOW + timedelta(seconds=5))
    route["route_evidence_expires_at"] = format_rfc3339(NOW + timedelta(hours=24))
    assert _build(HelmContextSources(bridge_session_state=route), synthetic=True).projections["bridge_session"].status is ProjectionStatus.UNAVAILABLE
    with pytest.raises(HelmContextError, match="fresh route evidence"):
        replace(routed, generated_at=format_rfc3339(NOW + timedelta(seconds=6)), expires_at=format_rfc3339(NOW + timedelta(seconds=60)), context_digest="")
    routed_payload = routed.to_dict()
    routed_payload["projections"]["bridge_session"]["data"]["served_provider_id"] = ""
    with pytest.raises(HelmContextError, match="empty identifier"):
        decode_helm_context(routed_payload)
def test_malformed_owner_timestamps_degrade_instead_of_becoming_fresh() -> None:
    for value in ("not-a-timestamp", datetime(2026, 8, 15, 3, 0)):
        envelope = _build(HelmContextSources(mission_control=MissionOwner(value), mission_id="m"), synthetic=True)
        assert envelope.projections["mission_control"].status is ProjectionStatus.UNAVAILABLE
        assert envelope.projections["mission_control"].unavailable_reason == "owner_projection_invalid"
    future = _build(HelmContextSources(mission_control=MissionOwner(NOW + timedelta(seconds=1)), mission_id="m"), synthetic=True)
    assert future.projections["mission_control"].unavailable_reason == "owner_observation_in_future"
    class FutureTaskOwner(TaskOwner):
        async def list_tasks(self, *, limit: int) -> list[dict[str, object]]:
            return [{"id": "task", "title": "future", "status": "pending", "priority": "normal", "assigned_to": None, "depends_on": [], "blocked_by": [], "updated_at": NOW + timedelta(seconds=1)}]
    task_envelope = _build(HelmContextSources(task_board=FutureTaskOwner()), synthetic=True)
    assert task_envelope.projections["task_board"].unavailable_reason == "owner_projection_invalid"
def test_timestamp_digest_duplicate_and_bounds_fail_closed() -> None:
    with pytest.raises(HelmContextError, match="exact RFC3339 grammar"):
        AuthorityStamp(AuthorityModality.UNKNOWN, "owner", "source", "2026-08-15 03:00:00+00:00", None, EPOCH)
    with pytest.raises(HelmContextError):
        AuthorityStamp(AuthorityModality.UNKNOWN, "owner", "source", "9999-12-31T23:59:59-23:59", None, EPOCH)
    with pytest.raises(HelmContextError, match="duplicate JSON key"):
        decode_helm_context('{"a":1,"a":2}')
    payload = _build().to_dict()
    payload["context_digest"] = 1
    with pytest.raises(HelmContextError, match="digest"):
        decode_helm_context(payload)
    with pytest.raises(HelmContextError, match="encoded byte bound"):
        decode_helm_context(b"{" + b"x" * MAX_HELM_CONTEXT_BYTES)
    envelope = _build()
    workspace = envelope.projections["workspace"]
    forged = replace(workspace.authority, owner="Attacker", source="attacker.injected")
    with pytest.raises(HelmContextError, match="owner-issued"):
        replace(envelope, projections={**envelope.projections, "workspace": replace(workspace, authority=forged)}, context_digest="")
    old_epoch = replace(workspace.authority, runtime_epoch="forged-old-epoch")
    with pytest.raises(HelmContextError, match="runtime epoch mismatch"):
        replace(envelope, projections={**envelope.projections, "workspace": replace(workspace, authority=old_epoch)}, context_digest="")
def test_exact_route_claim_requires_evaluator_owned_fresh_nonsynthetic_evidence() -> None:
    bridge = _bridge()
    bridge.update({"route_verdict": "ON_CALL", "route_exact_model_proven": True, "route_evidence_freshness": "fresh", "route_evidence_synthetic": True, "served_provider_id": "openrouter", "served_model_id": "model"})
    assert _build(HelmContextSources(bridge_session_state=bridge)).projections["bridge_session"].status is ProjectionStatus.UNAVAILABLE
    phased = _bridge()
    phased["active_phase"] = "streaming"
    assert _build(HelmContextSources(bridge_session_state=phased), synthetic=True).projections["bridge_session"].status is ProjectionStatus.UNAVAILABLE
    partial = _bridge()
    partial.update({"served_provider_id": "provider", "served_model_id": "model", "served_identity_source": "provider_response_via_route_evaluator", "served_identity_observed_at": format_rfc3339(NOW), "route_evidence_freshness": "invalid"})
    assert _build(HelmContextSources(bridge_session_state=partial), synthetic=True).projections["bridge_session"].status is ProjectionStatus.UNAVAILABLE
def test_nested_owner_time_cannot_follow_its_authority_stamp(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = object.__new__(SwarmManager)
    async def status(self) -> dict[str, object]:
        return {"observed_at": NOW - timedelta(seconds=1), "agents": [{"id": "agent", "name": "Agent", "role": "worker", "status": "idle", "current_task": None, "provider": "local", "model": "model", "last_heartbeat": NOW}], "tasks_pending": 0, "tasks_running": 0, "tasks_completed": 0, "tasks_failed": 0}
    monkeypatch.setattr(SwarmManager, "status", status)
    assert _build(HelmContextSources(swarm=owner)).projections["swarm"].status is ProjectionStatus.UNAVAILABLE
def test_owner_subclass_cannot_impersonate_canonical_owner() -> None:
    class ForgedStore(SessionStore):
        def list_sessions(self) -> list[dict[str, object]]:
            return [{"session_id": "forged"}]
    projection = _build(HelmContextSources(session_store=object.__new__(ForgedStore))).projections["session"]
    assert projection.status is ProjectionStatus.UNAVAILABLE
    assert projection.unavailable_reason == "noncanonical_owner_rejected"
def test_large_owner_collection_has_stable_explicit_window() -> None:
    envelope = _build(HelmContextSources(a2a=A2AOwner(70)), synthetic=True)
    contacts = envelope.projections["a2a"].data["contacts"]
    assert contacts["total"] == 70 and contacts["truncated"] is True and len(contacts["items"]) == 32
    payload = envelope.to_dict()
    payload["projections"]["a2a"]["data"]["contacts"].update({"items": [], "total": 0, "truncated": True})
    with pytest.raises(HelmContextError, match="collection counts"):
        decode_helm_context(payload)
def test_unsealed_lone_surrogate_and_invalid_action_are_rejected() -> None:
    envelope = _build()
    with pytest.raises(HelmContextError, match="unsealed"):
        encode_helm_context(replace(envelope, context_digest=""))
    workspace = _workspace()
    workspace["repository"] = "\ud800"
    assert _build(HelmContextSources(workspace_state=workspace)).projections["workspace"].status is ProjectionStatus.UNAVAILABLE
    with pytest.raises(HelmContextError, match="risk"):
        OperatorActionDescriptor("x", "x", "owner", ("effect",), "invented", True, True, "cancel")
    invalid_actions = (
        ((), "safe_read", False, False, None),
        (("mutate",), "workspace_mutation", False, True, "cancel"),
        (("mutate",), "workspace_mutation", True, True, None),
        (("read",), "safe_read", False, False, "cancel"),
    )
    for effects, risk, approval, reversible, cancel in invalid_actions:
        with pytest.raises(HelmContextError):
            OperatorActionDescriptor("x", "x", "owner", effects, risk, approval, reversible, cancel)
    with pytest.raises(HelmContextError):
        decode_helm_context('{"value":"\ud800"}')
    deep: dict[str, Any] = {}
    cursor = deep
    for _ in range(2_000):
        child: dict[str, Any] = {}
        cursor["child"] = child
        cursor = child
    with pytest.raises(HelmContextError):
        decode_helm_context(deep)
def test_synchronous_owner_read_timeout_does_not_depend_on_default_executor() -> None:
    release = threading.Event()
    async def exercise() -> float:
        loop = asyncio.get_running_loop()
        started = loop.time()
        with pytest.raises(TimeoutError, match="bounded owner read"):
            await run_bounded_sync(release.wait, timeout=0.02)
        return loop.time() - started
    try:
        assert asyncio.run(exercise()) < 0.25
    finally:
        release.set()
def test_absent_owner_modules_are_not_imported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "dharma_swarm.operator_core.helm_context_projection.importlib.import_module",
        lambda name: (_ for _ in ()).throw(AssertionError(f"unexpected owner import: {name}")),
    )
    assert _build().projections["swarm"].status is ProjectionStatus.UNAVAILABLE
def test_committed_fixture_is_a_valid_synthetic_envelope() -> None:
    fixture = Path("tests/fixtures/terminal_bridge/helm_context_v1.json").read_bytes().rstrip(b"\n")
    decoded = decode_helm_context(fixture)
    assert decoded.synthetic is True and decoded.schema_version == "dharma.helm.context.v1"
    assert decoded.projections["ui"].data["place"] == "conversation"
    assert encode_helm_context(decoded) == fixture
