from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import dharma_swarm.governed_patch_effect as effect_impl
from dharma_swarm.forge_lab.worktree import create_marked_scratch_worktree
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.governed_patch_candidate_bundle import (
    CandidateBundle,
    build_candidate_bundle,
)
from dharma_swarm.governed_patch_effect import inspect_effect_target
from dharma_swarm.governed_patch_evidence import (
    GOVERNED_PATCH_REQUEST_SCHEMA,
    NativePatchBindings,
    parse_governed_patch_request,
)
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_a2a import A2A_BINDING_SCHEMA, A2ANativeExecutionRef
from dharma_swarm.mission_control_a2a_candidate import ExactProposalStoreExpectation
from dharma_swarm.mission_control_a2a_owner_readback import (
    observe_exact_proposal_store,
)
from dharma_swarm.mission_control_effect_evidence import (
    FOUNDRY_POSITIVE_OUTCOME,
    SIGNED_PROCESS_RECEIPT_SCHEMA,
    VIBE_POSITIVE_OUTCOME,
    finite_sha256,
    native_binding,
)
from dharma_swarm.mission_control_effect_codec import canonical_json, terminal_from_json
from dharma_swarm.mission_control_effect_fence import (
    GovernedPatchEffectFence,
    _compose_pinned_effect_fence,
    read_effect_fence,
)
from dharma_swarm.mission_control_effect_owner import inspect_owner_stores
from dharma_swarm.mission_control_effect_records import (
    CanaryVerifierBinding,
    EffectRefusal,
    EffectTerminalRecord,
)
from dharma_swarm.mission_control_effect_supervisor import SupervisorAuthorityIssuer
from dharma_swarm.mission_control_effect_verification import (
    IndependentPatchVerifier,
    build_canary_patch_binding,
)
from dharma_swarm.mission_control_effect_warrant import (
    FOUNDRY_CANARY_SCHEMA,
    EffectWarrant,
    IndependentPatchVerification,
)
from dharma_swarm.mission_control_contract import (
    RECOVERY_RECEIPT_TYPE,
    TERMINAL_RECEIPT_TYPE,
    MissionControlError,
)
from dharma_swarm.mission_control_verification import PATCH_VIBE_SCHEMA
from dharma_swarm.models import TaskStatus
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.runtime_state_effect_fence import EFFECT_RECEIPT_ID_PREFIX
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard, TaskBoardError

SOURCE_PATH = "pkg/example.py"
SOURCE = 'def value():\n    return "old"\n'
POSTIMAGE = 'def value():\n    return "new"\n'
DIFF = """--- a/pkg/example.py
+++ b/pkg/example.py
@@ -1,2 +1,2 @@
 def value():
-    return "old"
+    return "new"
"""
DELIVERY_ID = "d" * 24


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _public_key(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


def _sign(
    body: dict[str, Any], key: Ed25519PrivateKey, *, key_id: str,
) -> dict[str, Any]:
    signed = {**body, "payload_sha256": canonical_sha256(body)}
    message = json.dumps(
        signed,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return {
        **signed,
        "signature": {
            "scheme": "ed25519",
            "key_id": key_id,
            "public_key": _public_key(key),
            "signature": key.sign(message).hex(),
        },
    }


def _foundry_evidence(binding) -> dict[str, Any]:
    run = {
        "docker_image_digest": "sha256:" + "1" * 64,
        "argv_sha256": binding.oracle_argv_sha256,
        "exit_code": 0,
        "timed_out": False,
        "output_truncated": False,
        "stdout_sha256": "2" * 64,
        "stderr_sha256": "3" * 64,
    }
    return {
        "schema": FOUNDRY_CANARY_SCHEMA,
        "outcome": FOUNDRY_POSITIVE_OUTCOME,
        "binding": binding.to_dict(),
        "candidate_bundle_sha256": binding.candidate_bundle_sha256,
        "oracle_argv_sha256": binding.oracle_argv_sha256,
        "replay": {
            "source_path": binding.scratch.source_path,
            "preimage_sha256": binding.scratch.preimage_sha256,
            "postimage_sha256": binding.scratch.postimage_sha256,
            "diff_sha256": binding.diff_sha256,
            "exact_patch_replayed": True,
        },
        "tripwires": {
            "pre_worktree_clean": True,
            "pre_index_clean": True,
            "post_worktree_clean": True,
            "post_index_clean": True,
        },
        "oracle_runs": [{"ordinal": 1, **run}, {"ordinal": 2, **run}],
        "isolation_policy": {
            "network": "none",
            "read_only_root": True,
            "no_new_privileges": True,
            "cap_drop_all": True,
            "memory_limit_bytes": 64 * 1024 * 1024,
            "pids_limit": 32,
            "cpu_limit_millis": 1000,
        },
        "release_snapshot": {"before_sha256": "4" * 64, "after_sha256": "4" * 64},
        "tool_snapshot": {"before_sha256": "5" * 64, "after_sha256": "5" * 64},
        "cleanup": {
            "scratch_worktree_clean": True,
            "containers_removed": True,
            "temporary_files_removed": True,
        },
        "promotion_allowed": False,
        "limitations": [
            "canary_scope_only",
            "exclusive_private_key_custody_unproven",
            "same_uid_process_isolation_unproven",
        ],
        "exclusive_private_key_custody_unproven": True,
        "repository_effect_authorized": False,
        "repository_effect_performed": False,
    }


def _vibe_receipt(binding, key: Ed25519PrivateKey) -> dict[str, Any]:
    return _sign(
        {
            "schema": PATCH_VIBE_SCHEMA,
            "candidate_digest": binding.candidate_digest,
            "diff_sha256": binding.diff_sha256,
            "verifier": {
                "agent_uid": binding.vibe_verifier.agent_uid,
                "run_id": binding.vibe_verifier.run_id,
                "parent_run_id": binding.executor_run_id,
            },
            "ran": True,
            "reported_outcome": "clean",
            "diff_bound": True,
            "calibration_only": False,
            "process": {"exit_code": 0, "timed_out": False, "output_limited": False},
            "findings": [],
            "errors": [],
            "blockers": [],
        },
        key,
        key_id="governed-patch-vibe",
    )


def _process_receipt(
    binding,
    key: Ed25519PrivateKey,
    *,
    role: str,
    outcome: str,
    nested_digest: str,
    pid: int,
    boot_id: str,
    key_path: Path,
) -> dict[str, Any]:
    verifier = binding.foundry_verifier if role == "foundry" else binding.vibe_verifier
    public_key = _public_key(key)
    key_stat = key_path.stat()
    metadata = {
        "authority_semantics": "evidence_only",
        "repository_effect_performed": False,
        "evidence_storage_effects_performed": True,
        "repository_effect_authorized": False,
        "role": role,
        "process_boot_id": boot_id,
        "signer_public_key": public_key,
    }
    return _sign(
        {
            "schema": SIGNED_PROCESS_RECEIPT_SCHEMA,
            "role": role,
            "identity": {
                "trace_id": f"trace:{verifier.run_id}",
                "correlation_id": binding.correlation_id,
                "task_id": binding.task_id,
                "run_id": verifier.run_id,
                "claim_id": f"claim:{verifier.run_id}",
                "idempotency_key": (
                    f"idem:governed_patch:{role}:{binding.proposal_id}:"
                    f"{binding.candidate_digest}"
                ),
                "causation_id": binding.candidate_digest,
                "parent_run_id": binding.executor_run_id,
                "agent_id": verifier.agent_uid,
                "session_id": f"mission:{binding.mission_id}",
                "external_a2a_task_id": "",
                "message_id": "",
                "event_id": "",
                "artifact_id": binding.candidate_digest,
                "proposal_id": binding.proposal_id,
                "metadata": metadata,
            },
            "candidate_digest": binding.candidate_digest,
            "diff_sha256": binding.diff_sha256,
            "outcome": outcome,
            "reasons": [],
            "evidence": {
                "native_bindings": native_binding(binding),
                "candidate_bundle_sha256": binding.candidate_bundle_sha256,
                "canary_binding_sha256": binding.binding_sha256,
                "nested_evidence_sha256": nested_digest,
                "scanner_provenance_sha256": "6" * 64,
            },
            "process": {"pid": pid, "boot_id": boot_id},
            "key_custody": {
                "owner_only_regular_file": True,
                "key_device": key_stat.st_dev,
                "key_inode": key_stat.st_ino,
                "exclusive_private_key_custody_proven": False,
            },
            "repository_effect_authorized": False,
            "repository_effect_performed": False,
            "evidence_storage_effects_performed": True,
        },
        key,
        key_id=f"governed-patch-{role}",
    )


@dataclass(slots=True)
class EffectHarness:
    runtime: RuntimeStateStore
    board: TaskBoard
    control: MissionControl
    runtime_path: Path
    task_path: Path
    source_repo: Path
    scratch: Path
    candidate: CandidateBundle
    expected: ExactProposalStoreExpectation
    binding: Any
    verifier: IndependentPatchVerifier
    issuer: SupervisorAuthorityIssuer
    fence: GovernedPatchEffectFence
    verification: IndependentPatchVerification
    foundry_key: Ed25519PrivateKey
    vibe_key: Ed25519PrivateKey
    foundry_key_path: Path
    vibe_key_path: Path
    foundry_evidence: dict[str, Any]
    foundry_process_receipt: dict[str, Any]
    vibe_receipt: dict[str, Any]
    vibe_process_receipt: dict[str, Any]


@pytest.fixture
async def effect_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> EffectHarness:
    runtime_path = (tmp_path / "owner" / "runtime.db").resolve()
    task_path = (tmp_path / "owner" / "tasks.db").resolve()
    runtime_path.parent.mkdir(mode=0o700)
    runtime = RuntimeStateStore(runtime_path, include_memory_plane=False)
    board = TaskBoard(task_path)
    await runtime.init_db()
    await board.init_db()
    control = MissionControl(board, runtime)
    mission_id = "mission-1"
    agent = "codex_composer"
    packet_id = "packet-1"
    correlation_id = f"a2a_send:{agent}:{packet_id}"
    proposal_id = "proposal-1"
    await control.create_mission(mission_id, title="Governed effect test")
    task = await control.create_task(mission_id, title="Apply one exact patch")

    source_repo = tmp_path / "canonical-source"
    (source_repo / "pkg").mkdir(parents=True)
    (source_repo / SOURCE_PATH).write_text(SOURCE, encoding="utf-8", newline="")
    _git(source_repo, "init", "-b", "main")
    _git(source_repo, "config", "user.email", "effect-test@example.invalid")
    _git(source_repo, "config", "user.name", "Effect Test")
    _git(source_repo, "add", "--", SOURCE_PATH)
    _git(source_repo, "commit", "-m", "base")
    base_sha = _git(source_repo, "rev-parse", "HEAD")
    native = NativePatchBindings(
        mission_id=mission_id,
        task_id=task.task_id,
        attempt_id=packet_id,
        lease_id=DELIVERY_ID,
        packet_id=packet_id,
        correlation_id=correlation_id,
        delivery_id=DELIVERY_ID,
        proposal_id=proposal_id,
        base_sha=base_sha,
        executor_agent_uid=agent,
        executor_run_id="executor-run-1",
        executor_process_boot_id="executor-boot-1",
    )
    request_payload = {
        "schema_version": GOVERNED_PATCH_REQUEST_SCHEMA,
        **native.to_dict(),
        "authorized_source_path": SOURCE_PATH,
        "oracle_argv": ["python3", "-m", "pytest", "tests/test_example.py", "-q"],
    }
    content = json.dumps(request_payload, sort_keys=True, separators=(",", ":"))
    content_sha = hashlib.sha256(content.encode()).hexdigest()
    request = parse_governed_patch_request(
        content,
        repo_root=source_repo,
        expected=native,
        accepted_base_sha=base_sha,
        expected_content_sha256=content_sha,
    )
    candidate = build_candidate_bundle(request, DIFF, bundle_root=tmp_path / "bundle")
    stored = await board.get(task.task_id)
    assert stored is not None
    await board.update_task(
        task.task_id,
        metadata={
            **stored.metadata,
            "a2a_binding": {
                "schema_version": A2A_BINDING_SCHEMA,
                "agent_uid": agent,
                "packet_id": packet_id,
                "correlation_id": correlation_id,
                "delivery_id": DELIVERY_ID,
                "proposal_id": proposal_id,
                "content_sha256": content_sha,
            },
        },
    )
    attempt_key = "effect-attempt"
    assigned_by = "effect-supervisor"
    attempt = await control.start_attempt(
        mission_id,
        task.task_id,
        agent,
        attempt_key=attempt_key,
        assigned_by=assigned_by,
        lease_seconds=120,
    )
    await control.heartbeat_lease(
        mission_id, task.task_id, agent, attempt_id=attempt.attempt_id
    )
    executor = ExecutionIdentity.new(
        task_id=task.task_id,
        trace_id="trace-semantic-executor",
        correlation_id=correlation_id,
        parent_run_id=attempt.attempt_id,
        run_id=native.executor_run_id,
        claim_id=attempt.claim_id,
        idempotency_key="idem-semantic-executor",
        agent_id=agent,
        session_id=f"mission:{mission_id}",
        proposal_id=proposal_id,
        metadata={
            "process_boot_id": native.executor_process_boot_id,
            "role": "governed_patch_semantic_executor",
        },
    )
    runtime.record_execution_identity_exact_sync(
        executor, source="governed_patch_semantic_executor"
    )
    artifact_sha256 = "a" * 64
    await runtime.commit_self_mod_receipt_exact(
        executor,
        stage="proposal",
        proposal_id=proposal_id,
        status="proposed",
        payload={
            "schema_version": "dharma.a2a.patch_candidate.v1",
            "mission_id": native.mission_id,
            "task_id": native.task_id,
            "attempt_id": native.attempt_id,
            "lease_id": native.lease_id,
            "packet_id": native.packet_id,
            "correlation_id": native.correlation_id,
            "delivery_id": native.delivery_id,
            "proposal_id": native.proposal_id,
            "base_sha": native.base_sha,
            "candidate_digest": candidate.candidate_digest,
            "diff_sha256": candidate.diff_sha256,
            "artifact_sha256": artifact_sha256,
            "authorized_source_files": [SOURCE_PATH],
        },
    )
    expected = ExactProposalStoreExpectation(
        native_ref=A2ANativeExecutionRef(
            mission_id=mission_id,
            task_id=task.task_id,
            agent_uid=agent,
            packet_id=packet_id,
            correlation_id=correlation_id,
            delivery_id=DELIVERY_ID,
            proposal_id=proposal_id,
            content_sha256=content_sha,
        ),
        attempt_key=attempt_key,
        operator_id="system",
        assigned_by=assigned_by,
        executor_run_id=native.executor_run_id,
        executor_process_boot_id=native.executor_process_boot_id,
        candidate_digest=candidate.candidate_digest,
        diff_sha256=candidate.diff_sha256,
        base_sha=base_sha,
        artifact_sha256=artifact_sha256,
        authorized_source_files=(SOURCE_PATH,),
    )
    observation = observe_exact_proposal_store(runtime_path, task_path, expected)

    approved_root = tmp_path / "approved-evolution-root"
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(approved_root))
    scratch = create_marked_scratch_worktree(
        source_repo=source_repo,
        experiment_id="governed-effect-fence-test",
        archive_path=tmp_path / "archive",
        base_ref=base_sha,
    )
    git_executable = Path(shutil.which("git") or "/usr/bin/git").resolve(strict=True)
    scratch_binding = inspect_effect_target(
        candidate,
        scratch,
        approved_scratch_root=approved_root,
        trusted_canonical_repo=source_repo,
        git_executable=git_executable,
        expected_os_uid=os.getuid(),
    )

    foundry_key = Ed25519PrivateKey.generate()
    vibe_key = Ed25519PrivateKey.generate()
    supervisor_key = Ed25519PrivateKey.generate()
    foundry_path = tmp_path / "foundry.key"
    vibe_path = tmp_path / "vibe.key"
    for path, key in ((foundry_path, foundry_key), (vibe_path, vibe_key)):
        path.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        path.chmod(0o600)
    binding = build_canary_patch_binding(
        expected,
        observation,
        candidate,
        scratch_binding,
        foundry_verifier=CanaryVerifierBinding(
            "foundry_canary", "foundry-verifier", "foundry-run-1", _public_key(foundry_key)
        ),
        vibe_verifier=CanaryVerifierBinding(
            "vibe_canary", "vibe-verifier", "vibe-run-1", _public_key(vibe_key)
        ),
    )
    foundry = _foundry_evidence(binding)
    vibe = _vibe_receipt(binding, vibe_key)
    foundry_process = _process_receipt(
        binding,
        foundry_key,
        role="foundry",
        outcome=FOUNDRY_POSITIVE_OUTCOME,
        nested_digest=finite_sha256(foundry),
        pid=os.getpid() + 101,
        boot_id="foundry-boot-1",
        key_path=foundry_path,
    )
    vibe_process = _process_receipt(
        binding,
        vibe_key,
        role="vibe_halt",
        outcome=VIBE_POSITIVE_OUTCOME,
        nested_digest=finite_sha256(vibe),
        pid=os.getpid() + 102,
        boot_id="vibe-boot-1",
        key_path=vibe_path,
    )
    verifier = IndependentPatchVerifier(
        trusted_foundry_public_keys=frozenset({_public_key(foundry_key)}),
        trusted_vibe_public_keys=frozenset({_public_key(vibe_key)}),
    )
    verification = verifier.evaluate(
        binding,
        foundry_process_receipt=foundry_process,
        foundry_canary_evidence=foundry,
        vibe_process_receipt=vibe_process,
        vibe_patch_receipt=vibe,
    )
    assert isinstance(verification, IndependentPatchVerification)
    issuer = SupervisorAuthorityIssuer(
        supervisor_key,
        key_id="effect-supervisor-key",
        trusted_public_keys=frozenset({_public_key(supervisor_key)}),
        supervisor_id="effect-supervisor",
    )
    fence = _compose_pinned_effect_fence(verifier, issuer)
    return EffectHarness(
        runtime=runtime,
        board=board,
        control=control,
        runtime_path=runtime_path,
        task_path=task_path,
        source_repo=source_repo,
        scratch=scratch,
        candidate=candidate,
        expected=expected,
        binding=binding,
        verifier=verifier,
        issuer=issuer,
        fence=fence,
        verification=verification,
        foundry_key=foundry_key,
        vibe_key=vibe_key,
        foundry_key_path=foundry_path,
        vibe_key_path=vibe_path,
        foundry_evidence=foundry,
        foundry_process_receipt=foundry_process,
        vibe_receipt=vibe,
        vibe_process_receipt=vibe_process,
    )


def _issue(harness: EffectHarness, *, ttl_seconds: int = 15) -> EffectWarrant:
    owners = inspect_owner_stores(harness.runtime_path, harness.task_path)
    authority = harness.issuer.issue(harness.binding, owners, ttl_seconds=20)
    warrant = harness.fence.issue_effect_warrant(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        harness.candidate,
        harness.verification,
        authority,
        ttl_seconds=ttl_seconds,
    )
    assert isinstance(warrant, EffectWarrant)
    return warrant


def _wait_until_expired(warrant: EffectWarrant) -> None:
    while datetime.now(timezone.utc) <= warrant.expires_at:
        time.sleep(0.01)


def _wait_past(deadline: datetime) -> None:
    while datetime.now(timezone.utc) <= deadline:
        time.sleep(0.01)


async def _shorten_claim(
    harness: EffectHarness,
    claim_id: str,
    *,
    seconds: float,
) -> datetime:
    claim = await harness.runtime.get_task_claim(claim_id)
    assert claim is not None
    deadline = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    await harness.runtime.record_task_claim(replace(claim, stale_after=deadline))
    return deadline


def _fresh_recovery_authority(harness: EffectHarness):
    owners = inspect_owner_stores(harness.runtime_path, harness.task_path)
    return harness.issuer.issue(harness.binding, owners, ttl_seconds=20)


def _assert_one_effect_terminal(harness: EffectHarness) -> None:
    with sqlite3.connect(harness.runtime_path) as database:
        counts = (
            database.execute(
                "SELECT count(*) FROM runtime_receipts WHERE side_effect_key=?",
                (harness.binding.effect_key,),
            ).fetchone()[0],
            database.execute(
                "SELECT count(*) FROM idempotency_records WHERE side_effect_key=?",
                (harness.binding.effect_key,),
            ).fetchone()[0],
            database.execute(
                "SELECT count(*) FROM mission_control_effect_fences"
                " WHERE effect_key=? AND state='consumed'",
                (harness.binding.effect_key,),
            ).fetchone()[0],
        )
    assert counts == (1, 1, 1)


def test_public_issuance_refuses_malformed_target_without_leaking_runtime_error(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    owners = inspect_owner_stores(harness.runtime_path, harness.task_path)
    authority = harness.issuer.issue(harness.binding, owners, ttl_seconds=20)
    target = harness.scratch / SOURCE_PATH
    target.unlink()
    target.mkdir()

    result = harness.fence.issue_effect_warrant(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        harness.candidate,
        harness.verification,
        authority,
    )

    assert result == EffectRefusal(("canonical_effect_issuance_refused",))
    assert read_effect_fence(harness.runtime_path, harness.binding.effect_key) is None


@pytest.mark.parametrize("seam", ["prewrite", "readback"])
def test_terminal_expiry_equality_is_strictly_refused(
    effect_harness: EffectHarness,
    monkeypatch: pytest.MonkeyPatch,
    seam: str,
) -> None:
    import dharma_swarm.mission_control_effect_terminal_store as terminal_store

    harness = effect_harness
    warrant = _issue(harness)
    if seam == "prewrite":
        monkeypatch.setattr(terminal_store, "_now", lambda: warrant.expires_at)
        result = harness.fence.consume_effect_slot(
            harness.runtime_path,
            harness.task_path,
            harness.expected,
            warrant,
            harness.candidate,
            claimed_by="effect-supervisor",
        )
        assert isinstance(result, EffectRefusal)
        issued = read_effect_fence(harness.runtime_path, harness.binding.effect_key)
        assert issued is not None and issued.state == "issued"
        with sqlite3.connect(harness.runtime_path) as database:
            assert database.execute(
                "SELECT count(*) FROM runtime_receipts WHERE side_effect_key=?",
                (harness.binding.effect_key,),
            ).fetchone()[0] == 0
        return

    terminal = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )
    assert isinstance(terminal, EffectTerminalRecord)
    with sqlite3.connect(harness.runtime_path) as database:
        database.execute(
            "UPDATE mission_control_effect_fences SET claim_expires_at=?"
            " WHERE effect_key=?",
            (terminal.consumed_at.isoformat(), harness.binding.effect_key),
        )
        database.commit()

    with pytest.raises(sqlite3.IntegrityError, match="terminal triple conflicts"):
        read_effect_fence(harness.runtime_path, harness.binding.effect_key)


@pytest.mark.asyncio
async def test_test_only_signed_positive_fixtures_issue_consume_and_replay_exact_triple(
    effect_harness: EffectHarness,
) -> None:
    """Test-only positive evidence covers a producer absent from production today."""

    harness = effect_harness
    warrant = _issue(harness)

    first = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )
    replay = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )

    assert isinstance(first, EffectTerminalRecord)
    assert replay == first
    assert (harness.scratch / SOURCE_PATH).read_text(encoding="utf-8") == POSTIMAGE
    durable = read_effect_fence(harness.runtime_path, harness.binding.effect_key)
    assert durable is not None
    assert durable.state == "consumed"
    assert durable.terminal == first
    with sqlite3.connect(harness.runtime_path) as db:
        receipt_count = db.execute(
            "SELECT count(*) FROM runtime_receipts WHERE side_effect_key=?",
            (harness.binding.effect_key,),
        ).fetchone()[0]
        idempotency_count = db.execute(
            "SELECT count(*) FROM idempotency_records WHERE side_effect_key=?",
            (harness.binding.effect_key,),
        ).fetchone()[0]
        fence_count = db.execute(
            "SELECT count(*) FROM mission_control_effect_fences WHERE effect_key=?",
            (harness.binding.effect_key,),
        ).fetchone()[0]
    assert (receipt_count, idempotency_count, fence_count) == (1, 1, 1)


def test_direct_fence_constructor_is_not_an_authority_surface() -> None:
    with pytest.raises(TypeError, match="trusted composition root"):
        GovernedPatchEffectFence()


def test_fabricated_nominal_warrant_cannot_consume(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    real = _issue(harness)
    forged = EffectWarrant(
        real.fence_id,
        real.binding,
        real.issued_at,
        real.expires_at,
        real.warrant_token,
    )
    object.__setattr__(forged, "_seal", real._seal)  # noqa: SLF001

    refused = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        forged,
        harness.candidate,
        claimed_by="effect-supervisor",
    )

    assert refused == EffectRefusal(("fresh_registered_effect_warrant_required",))
    assert (harness.scratch / SOURCE_PATH).read_text(encoding="utf-8") == SOURCE


def test_test_only_verifier_accepts_same_device_distinct_key_inodes(
    effect_harness: EffectHarness,
) -> None:
    """The test fixture proves inode separation, not private-key exclusivity."""

    foundry = effect_harness.foundry_key_path.stat()
    vibe = effect_harness.vibe_key_path.stat()
    assert foundry.st_dev == vibe.st_dev
    assert foundry.st_ino != vibe.st_ino
    assert effect_harness.verifier.validates(effect_harness.verification)


@pytest.mark.parametrize("overlap", ["pid", "key_custody"])
def test_verifier_refuses_process_or_key_custody_overlap(
    effect_harness: EffectHarness, overlap: str,
) -> None:
    harness = effect_harness
    body = {
        key: value
        for key, value in harness.vibe_process_receipt.items()
        if key not in {"payload_sha256", "signature"}
    }
    if overlap == "pid":
        body["process"] = {
            **body["process"],
            "pid": harness.foundry_process_receipt["process"]["pid"],
        }
    else:
        body["key_custody"] = harness.foundry_process_receipt["key_custody"]
    overlapped = _sign(
        body, harness.vibe_key, key_id="governed-patch-vibe_halt"
    )

    refused = harness.verifier.evaluate(
        harness.binding,
        foundry_process_receipt=harness.foundry_process_receipt,
        foundry_canary_evidence=harness.foundry_evidence,
        vibe_process_receipt=overlapped,
        vibe_patch_receipt=harness.vibe_receipt,
    )

    assert isinstance(refused, EffectRefusal)
    assert "canary_process_or_key_custody_not_separated" in refused.blockers


def test_verifier_refuses_nonfinite_mapping_instead_of_throwing(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    malformed = {**harness.foundry_evidence, "promotion_allowed": float("nan")}

    refused = harness.verifier.evaluate(
        harness.binding,
        foundry_process_receipt=harness.foundry_process_receipt,
        foundry_canary_evidence=malformed,
        vibe_process_receipt=harness.vibe_process_receipt,
        vibe_patch_receipt=harness.vibe_receipt,
    )

    assert isinstance(refused, EffectRefusal)
    assert "foundry_canary_evidence_not_positive_or_exact" in refused.blockers


def test_expired_warrant_refuses_without_effect(
    effect_harness: EffectHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dharma_swarm.mission_control_effect_fence as fence_impl

    harness = effect_harness
    warrant = _issue(harness, ttl_seconds=1)
    monkeypatch.setattr(fence_impl, "_now", lambda: warrant.expires_at)

    refused = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )

    assert isinstance(refused, EffectRefusal)
    assert (harness.scratch / SOURCE_PATH).read_text(encoding="utf-8") == SOURCE


def test_stale_task_owner_refuses_without_effect(effect_harness: EffectHarness) -> None:
    harness = effect_harness
    warrant = _issue(harness)
    with sqlite3.connect(harness.task_path) as db:
        db.execute(
            "UPDATE tasks SET status='pending' WHERE id=?",
            (harness.expected.native_ref.task_id,),
        )
        db.commit()

    refused = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )

    assert isinstance(refused, EffectRefusal)
    assert (harness.scratch / SOURCE_PATH).read_text(encoding="utf-8") == SOURCE


@pytest.mark.parametrize("tamper", ["default", "timestamp"])
def test_tampered_issued_lifecycle_refuses_without_effect(
    effect_harness: EffectHarness, tamper: str,
) -> None:
    harness = effect_harness
    warrant = _issue(harness)
    with sqlite3.connect(harness.runtime_path) as db:
        if tamper == "default":
            db.execute(
                "UPDATE mission_control_effect_fences SET claimed_by='intruder'"
                " WHERE effect_key=?",
                (harness.binding.effect_key,),
            )
        else:
            db.execute(
                "UPDATE mission_control_effect_fences"
                " SET warrant_expires_at=warrant_issued_at WHERE effect_key=?",
                (harness.binding.effect_key,),
            )
        db.commit()

    refused = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )

    assert isinstance(refused, EffectRefusal)
    assert (harness.scratch / SOURCE_PATH).read_text(encoding="utf-8") == SOURCE


def test_terminal_triple_collision_quarantines_without_effect(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    warrant = _issue(harness)
    digest = hashlib.sha256(harness.binding.effect_key.encode()).hexdigest()
    receipt_id = EFFECT_RECEIPT_ID_PREFIX + digest
    with sqlite3.connect(harness.runtime_path) as db:
        db.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id,receipt_type,run_id,task_id,trace_id,correlation_id,"
            " causation_id,parent_run_id,agent_id,idempotency_key,side_effect_key,"
            " status,payload_json,created_at)"
            " VALUES (?,?,'','','','','','','','','','occupied','{}',datetime('now'))",
            (receipt_id, "hostile_alias"),
        )
        db.commit()

    refused = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )

    assert isinstance(refused, EffectRefusal)
    assert refused.blockers[:2] == ("effect_slot_quarantined", "terminal_triple_collision")
    assert (harness.scratch / SOURCE_PATH).read_text(encoding="utf-8") == SOURCE


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork")
def test_actual_fork_inherited_composition_refuses_without_effect(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    warrant = _issue(harness)
    read_fd, write_fd = os.pipe()
    child = os.fork()
    if child == 0:  # pragma: no cover - assertion is returned through the pipe
        try:
            os.close(read_fd)
            refused = harness.fence.consume_effect_slot(
                harness.runtime_path,
                harness.task_path,
                harness.expected,
                warrant,
                harness.candidate,
                claimed_by="effect-supervisor",
            )
            os.write(
                write_fd,
                b"refused"
                if refused
                == EffectRefusal(("fresh_registered_effect_warrant_required",))
                else b"unexpected",
            )
        finally:
            os.close(write_fd)
            os._exit(0)
    os.close(write_fd)
    outcome = os.read(read_fd, 32)
    os.close(read_fd)
    waited, status = os.waitpid(child, 0)

    assert waited == child and os.waitstatus_to_exitcode(status) == 0
    assert outcome == b"refused"
    assert (harness.scratch / SOURCE_PATH).read_text(encoding="utf-8") == SOURCE


def test_consumed_terminal_replay_refuses_when_current_target_drifted(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    warrant = _issue(harness)
    first = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )
    assert isinstance(first, EffectTerminalRecord)
    target = harness.scratch / SOURCE_PATH
    target.write_text("tampered after terminal\n", encoding="utf-8")

    replay = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )

    assert isinstance(replay, EffectRefusal)


def test_visible_rename_without_parent_fsync_stays_issued_then_recovers_once(
    effect_harness: EffectHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A visible rename is not durable authority until its directory is synced."""

    import dharma_swarm.foundry.patches_atomic as atomic_impl

    harness = effect_harness
    warrant = _issue(harness, ttl_seconds=1)
    real_fsync = atomic_impl.os.fsync
    parent_fsync_calls = 0
    fail_parent_sync = True

    def injected_fsync(descriptor: int) -> None:
        nonlocal fail_parent_sync, parent_fsync_calls
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            parent_fsync_calls += 1
            if fail_parent_sync:
                raise OSError(errno.EIO, "injected parent directory fsync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(atomic_impl.os, "fsync", injected_fsync)
    refused = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )

    assert isinstance(refused, EffectRefusal)
    assert parent_fsync_calls == 1
    assert (harness.scratch / SOURCE_PATH).read_text(encoding="utf-8") == POSTIMAGE
    issued = read_effect_fence(harness.runtime_path, harness.binding.effect_key)
    assert issued is not None and issued.state == "issued" and issued.terminal is None
    with sqlite3.connect(harness.runtime_path) as db:
        assert db.execute(
            "SELECT count(*) FROM runtime_receipts WHERE side_effect_key=?",
            (harness.binding.effect_key,),
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT count(*) FROM idempotency_records WHERE side_effect_key=?",
            (harness.binding.effect_key,),
        ).fetchone()[0] == 0

    remaining = (warrant.expires_at.timestamp() - time.time()) + 0.02
    if remaining > 0:
        time.sleep(remaining)
    fail_parent_sync = False
    owners = inspect_owner_stores(harness.runtime_path, harness.task_path)
    recovery_authority = harness.issuer.issue(
        harness.binding, owners, ttl_seconds=15
    )
    recovered = harness.fence.recover_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        harness.binding.effect_key,
        harness.candidate,
        recovery_authority,
        claimed_by="effect-supervisor",
    )
    replay = harness.fence.recover_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        harness.binding.effect_key,
        harness.candidate,
        recovery_authority,
        claimed_by="effect-supervisor",
    )

    assert isinstance(recovered, EffectTerminalRecord)
    assert recovered.recovery_finalized is True
    assert replay == recovered
    assert parent_fsync_calls == 2
    durable = read_effect_fence(harness.runtime_path, harness.binding.effect_key)
    assert durable is not None and durable.state == "consumed"
    assert durable.terminal == recovered
    with sqlite3.connect(harness.runtime_path) as db:
        assert db.execute(
            "SELECT count(*) FROM runtime_receipts WHERE side_effect_key=?",
            (harness.binding.effect_key,),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM idempotency_records WHERE side_effect_key=?",
            (harness.binding.effect_key,),
        ).fetchone()[0] == 1


def test_terminal_readback_rejects_tampered_path_projection(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    warrant = _issue(harness)
    consumed = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )
    assert isinstance(consumed, EffectTerminalRecord)
    with sqlite3.connect(harness.runtime_path) as db:
        raw = db.execute(
            "SELECT terminal_record_json FROM mission_control_effect_fences"
            " WHERE effect_key=?",
            (harness.binding.effect_key,),
        ).fetchone()[0]
        payload = json.loads(raw)
        payload["path"] = "pkg/not-the-authorized-target.py"
        db.execute(
            "UPDATE mission_control_effect_fences SET terminal_record_json=?"
            " WHERE effect_key=?",
            (
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                harness.binding.effect_key,
            ),
        )
        db.commit()

    with pytest.raises(sqlite3.IntegrityError, match="terminal triple conflicts"):
        read_effect_fence(harness.runtime_path, harness.binding.effect_key)


def test_expired_issued_postimage_recovers_once_with_fresh_authority(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    warrant = _issue(harness, ttl_seconds=1)
    mutation = effect_impl._perform_prevalidated_effect(
        warrant.binding, harness.candidate,
    )
    assert mutation.postimage_sha256 == warrant.binding.scratch.postimage_sha256
    with sqlite3.connect(harness.runtime_path) as database:
        assert database.execute(
            "SELECT state FROM mission_control_effect_fences WHERE effect_key=?",
            (warrant.binding.effect_key,),
        ).fetchone()[0] == "issued"

    _wait_until_expired(warrant)
    owners = inspect_owner_stores(harness.runtime_path, harness.task_path)
    recovery_authority = harness.issuer.issue(
        harness.binding, owners, ttl_seconds=20,
    )
    terminal = harness.fence.recover_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant.binding.effect_key,
        harness.candidate,
        recovery_authority,
        claimed_by="effect-supervisor",
    )
    replay = harness.fence.recover_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant.binding.effect_key,
        harness.candidate,
        recovery_authority,
        claimed_by="effect-supervisor",
    )

    assert isinstance(terminal, EffectTerminalRecord)
    assert replay == terminal
    assert terminal.recovery_finalized is True
    assert terminal.recovery_supervisor_id == recovery_authority.supervisor_id
    assert terminal.claimed_by == recovery_authority.supervisor_id
    target = harness.scratch / SOURCE_PATH
    assert target.stat().st_ino == terminal.target_inode_after
    with sqlite3.connect(harness.runtime_path) as database:
        receipt = database.execute(
            "SELECT agent_id FROM runtime_receipts WHERE side_effect_key=?",
            (warrant.binding.effect_key,),
        ).fetchone()
        counts = tuple(database.execute(
            f"SELECT count(*) FROM {table} WHERE side_effect_key=?",
            (warrant.binding.effect_key,),
        ).fetchone()[0] for table in ("runtime_receipts", "idempotency_records"))
    assert receipt == (terminal.claimed_by,)
    assert counts == (1, 1)


def test_expired_issued_preimage_requires_fresh_reissue(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    expired = _issue(harness, ttl_seconds=1)
    _wait_until_expired(expired)
    owners = inspect_owner_stores(harness.runtime_path, harness.task_path)
    fresh_authority = harness.issuer.issue(harness.binding, owners, ttl_seconds=20)

    fresh = harness.fence.issue_effect_warrant(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        harness.candidate,
        harness.verification,
        fresh_authority,
        ttl_seconds=15,
    )

    assert isinstance(fresh, EffectWarrant)
    assert fresh.warrant_token != expired.warrant_token
    terminal = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        fresh,
        harness.candidate,
        claimed_by="effect-supervisor",
    )
    assert isinstance(terminal, EffectTerminalRecord)
    assert terminal.recovery_finalized is False
    assert (harness.scratch / SOURCE_PATH).read_text(encoding="utf-8") == POSTIMAGE


def test_repeated_issuance_prunes_expired_entries_from_in_process_registries(
    effect_harness: EffectHarness,
) -> None:
    """Bound in-process warrant/authority registries across repeated issuance."""
    harness = effect_harness
    rotations = 5
    for _ in range(rotations):
        owners = inspect_owner_stores(harness.runtime_path, harness.task_path)
        authority = harness.issuer.issue(harness.binding, owners, ttl_seconds=1)
        warrant = harness.fence.issue_effect_warrant(
            harness.runtime_path,
            harness.task_path,
            harness.expected,
            harness.candidate,
            harness.verification,
            authority,
            ttl_seconds=1,
        )
        assert isinstance(warrant, EffectWarrant)
        _wait_past(max(warrant.expires_at, authority.expires_at))
        assert len(harness.fence._warrants) <= 1  # noqa: SLF001
        assert len(harness.issuer._issued) <= 1  # noqa: SLF001


@pytest.mark.asyncio
async def test_exact_postimage_recovers_after_genuine_expired_active_owner_lease(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    deadline = await _shorten_claim(
        harness, harness.binding.mission_claim_id, seconds=2.0
    )
    warrant = _issue(harness)
    assert warrant.expires_at <= deadline
    mutation = effect_impl._perform_prevalidated_effect(
        warrant.binding, harness.candidate
    )
    assert mutation.postimage_sha256 == warrant.binding.scratch.postimage_sha256
    _wait_past(deadline)

    terminal = harness.fence.recover_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        harness.binding.effect_key,
        harness.candidate,
        _fresh_recovery_authority(harness),
        claimed_by="effect-supervisor",
    )

    assert isinstance(terminal, EffectTerminalRecord)
    assert terminal.recovery_finalized is True
    assert terminal.recovery_owner_basis == "expired_active"
    assert len(terminal.recovery_owner_observation_sha256) == 64
    assert all(
        character in "0123456789abcdef"
        for character in terminal.recovery_owner_observation_sha256
    )
    _assert_one_effect_terminal(harness)
    task = await harness.board.get(harness.binding.task_id)
    run = await harness.runtime.get_delegation_run(harness.binding.mission_attempt_id)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert task is not None and task.status == TaskStatus.RUNNING
    assert run is not None and run.status == "running"
    assert claim is not None and claim.status == "active"
    assert await harness.runtime.list_runtime_receipts(
        run_id=harness.binding.mission_attempt_id,
        receipt_type=TERMINAL_RECEIPT_TYPE,
    ) == []


@pytest.mark.asyncio
async def test_two_public_takeovers_preserve_old_effect_recovery_graph(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    original_deadline = await _shorten_claim(
        harness, harness.binding.mission_claim_id, seconds=2.0
    )
    warrant = _issue(harness)
    effect_impl._perform_prevalidated_effect(warrant.binding, harness.candidate)
    _wait_past(original_deadline)

    first_successor = await harness.control.start_attempt(
        harness.binding.mission_id,
        harness.binding.task_id,
        "successor-agent-one",
        attempt_key="effect-successor-one",
        assigned_by="effect-takeover-test",
    )
    first_deadline = await _shorten_claim(
        harness, first_successor.claim_id, seconds=0.2
    )
    _wait_past(first_deadline)
    final_successor = await harness.control.start_attempt(
        harness.binding.mission_id,
        harness.binding.task_id,
        "successor-agent-two",
        attempt_key="effect-successor-two",
        assigned_by="effect-takeover-test",
    )
    projected = await harness.board.get(harness.binding.task_id)
    assert first_successor.status == final_successor.status == "queued"
    assert projected is not None and projected.status == TaskStatus.ASSIGNED
    assert projected.assigned_to == "successor-agent-two"

    from dharma_swarm.mission_control_effect_owner import owner_transaction
    from dharma_swarm.mission_control_effect_owner_recovery import (
        observe_expired_proposal_for_effect_recovery_from_connection,
    )

    owners = inspect_owner_stores(harness.runtime_path, harness.task_path)
    with owner_transaction(owners) as database:
        owner_observation = (
            observe_expired_proposal_for_effect_recovery_from_connection(
                database,
                harness.expected,
                mission_attempt_id=harness.binding.mission_attempt_id,
                mission_claim_id=harness.binding.mission_claim_id,
                proposal_receipt_id=harness.binding.proposal_receipt_id,
                proposal_receipt_sha256=harness.binding.proposal_receipt_sha256,
            )
        )
        database.rollback()
    assert owner_observation.owner_transition == "canonical_stale_recovery"
    assert owner_observation.successor_attempt_ids == (
        first_successor.attempt_id,
        final_successor.attempt_id,
    )

    terminal = harness.fence.recover_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        harness.binding.effect_key,
        harness.candidate,
        _fresh_recovery_authority(harness),
        claimed_by="effect-supervisor",
    )

    assert isinstance(terminal, EffectTerminalRecord)
    assert terminal.recovery_owner_basis == "canonical_stale_recovery"
    assert len(terminal.recovery_owner_observation_sha256) == 64
    assert all(
        character in "0123456789abcdef"
        for character in terminal.recovery_owner_observation_sha256
    )
    _assert_one_effect_terminal(harness)
    old_run = await harness.runtime.get_delegation_run(
        harness.binding.mission_attempt_id
    )
    old_claim = await harness.runtime.get_task_claim(
        harness.binding.mission_claim_id
    )
    first_run = await harness.runtime.get_delegation_run(first_successor.attempt_id)
    final_run = await harness.runtime.get_delegation_run(final_successor.attempt_id)
    assert old_run is not None and old_run.status == "stale_recovered"
    assert old_claim is not None and old_claim.status == "stale_recovered"
    assert first_run is not None and first_run.status == "stale_recovered"
    assert final_run is not None and final_run.status == "queued"
    recovery_receipts = await harness.runtime.list_runtime_receipts(
        run_id=harness.binding.mission_attempt_id,
        receipt_type=RECOVERY_RECEIPT_TYPE,
    )
    assert len(recovery_receipts) == 1
    assert recovery_receipts[0].status == "stale_recovered"
    assert await harness.runtime.list_runtime_receipts(
        run_id=harness.binding.mission_attempt_id,
        receipt_type=TERMINAL_RECEIPT_TYPE,
    ) == []
    projected = await harness.board.get(harness.binding.task_id)
    assert projected is not None and projected.status == TaskStatus.ASSIGNED
    assert projected.result == "mission control lease reassigned"


@pytest.mark.asyncio
async def test_exact_postimage_recovers_after_original_attempt_finishes_normally(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    warrant = _issue(harness, ttl_seconds=1)
    mutation = effect_impl._perform_prevalidated_effect(
        warrant.binding, harness.candidate
    )
    assert mutation.postimage_sha256 == warrant.binding.scratch.postimage_sha256

    parent_receipt = await harness.control.finish_attempt(
        harness.binding.mission_id,
        harness.binding.task_id,
        harness.binding.executor_agent_uid,
        attempt_id=harness.binding.mission_attempt_id,
        status="succeeded",
        result="ordinary parent completion",
    )
    assert parent_receipt.status == "succeeded"
    _wait_until_expired(warrant)

    terminal = harness.fence.recover_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        harness.binding.effect_key,
        harness.candidate,
        _fresh_recovery_authority(harness),
        claimed_by="effect-supervisor",
    )

    assert isinstance(terminal, EffectTerminalRecord)
    assert terminal.recovery_finalized is True
    assert terminal.recovery_owner_basis == "canonical_terminal"
    assert len(terminal.recovery_owner_observation_sha256) == 64
    assert all(
        character in "0123456789abcdef"
        for character in terminal.recovery_owner_observation_sha256
    )
    _assert_one_effect_terminal(harness)
    task = await harness.board.get(harness.binding.task_id)
    run = await harness.runtime.get_delegation_run(harness.binding.mission_attempt_id)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    parent_terminals = await harness.runtime.list_runtime_receipts(
        run_id=harness.binding.mission_attempt_id,
        receipt_type=TERMINAL_RECEIPT_TYPE,
    )
    assert task is not None and task.status == TaskStatus.COMPLETED
    assert task.result == "ordinary parent completion"
    assert run is not None and run.status == "completed"
    assert claim is not None and claim.status == "completed"
    assert [receipt.receipt_id for receipt in parent_terminals] == [
        parent_receipt.receipt_id
    ]


@pytest.mark.asyncio
async def test_exact_postimage_recovers_from_terminal_task_projection_crash(
    effect_harness: EffectHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = effect_harness
    warrant = _issue(harness, ttl_seconds=1)
    mutation = effect_impl._perform_prevalidated_effect(
        warrant.binding, harness.candidate
    )
    assert mutation.postimage_sha256 == warrant.binding.scratch.postimage_sha256

    async def crash_before_task_projection(*args: Any, **kwargs: Any) -> None:
        raise TaskBoardError("simulated terminal task projection crash")

    monkeypatch.setattr(harness.board, "complete", crash_before_task_projection)
    with pytest.raises(MissionControlError, match="terminal task projection crash"):
        await harness.control.finish_attempt(
            harness.binding.mission_id,
            harness.binding.task_id,
            harness.binding.executor_agent_uid,
            attempt_id=harness.binding.mission_attempt_id,
            status="succeeded",
            result="durable parent result",
        )

    parent_terminals = await harness.runtime.list_runtime_receipts(
        run_id=harness.binding.mission_attempt_id,
        receipt_type=TERMINAL_RECEIPT_TYPE,
    )
    task = await harness.board.get(harness.binding.task_id)
    run = await harness.runtime.get_delegation_run(harness.binding.mission_attempt_id)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert len(parent_terminals) == 1
    assert task is not None and task.status == TaskStatus.RUNNING
    assert run is not None and run.status == "completed"
    assert claim is not None and claim.status == "active"

    from dharma_swarm.mission_control_effect_owner import owner_transaction
    from dharma_swarm.mission_control_effect_owner_recovery import (
        observe_expired_proposal_for_effect_recovery_from_connection,
    )

    owners = inspect_owner_stores(harness.runtime_path, harness.task_path)
    with owner_transaction(owners) as database:
        owner_observation = (
            observe_expired_proposal_for_effect_recovery_from_connection(
                database,
                harness.expected,
                mission_attempt_id=harness.binding.mission_attempt_id,
                mission_claim_id=harness.binding.mission_claim_id,
                proposal_receipt_id=harness.binding.proposal_receipt_id,
                proposal_receipt_sha256=harness.binding.proposal_receipt_sha256,
            )
        )
        database.rollback()
    assert owner_observation.owner_transition == "canonical_terminal"
    assert owner_observation.owner_reconciliation == "needs_task_projection"
    assert owner_observation.successor_attempt_ids == ()

    _wait_until_expired(warrant)
    terminal = harness.fence.recover_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        harness.binding.effect_key,
        harness.candidate,
        _fresh_recovery_authority(harness),
        claimed_by="effect-supervisor",
    )

    assert isinstance(terminal, EffectTerminalRecord)
    assert terminal.recovery_finalized is True
    assert terminal.recovery_owner_basis == "canonical_terminal"
    _assert_one_effect_terminal(harness)
    task = await harness.board.get(harness.binding.task_id)
    run = await harness.runtime.get_delegation_run(harness.binding.mission_attempt_id)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert task is not None and task.status == TaskStatus.RUNNING
    assert run is not None and run.status == "completed"
    assert claim is not None and claim.status == "active"
    assert await harness.runtime.list_runtime_receipts(
        run_id=harness.binding.mission_attempt_id,
        receipt_type=TERMINAL_RECEIPT_TYPE,
    ) == parent_terminals


@pytest.mark.asyncio
async def test_direct_recover_expired_claim_refuses_unexpired_owner(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert claim is not None and claim.stale_after is not None
    assert claim.stale_after > datetime.now(timezone.utc)

    with pytest.raises(MissionControlError, match="not an expired open lineage"):
        await harness.control._recover_expired_claim(  # noqa: SLF001
            harness.binding.mission_id,
            claim,
            recovered_at=datetime.now(timezone.utc),
        )

    unchanged = await harness.runtime.get_task_claim(claim.claim_id)
    run = await harness.runtime.get_delegation_run(harness.binding.mission_attempt_id)
    assert unchanged is not None and unchanged.status == "active"
    assert run is not None and run.status == "running"
    assert await harness.runtime.list_runtime_receipts(
        run_id=harness.binding.mission_attempt_id,
        receipt_type=RECOVERY_RECEIPT_TYPE,
    ) == []


def test_owner_transaction_pins_full_runtime_durability(
    effect_harness: EffectHarness,
) -> None:
    from dharma_swarm.mission_control_effect_owner import owner_transaction

    harness = effect_harness
    owners = inspect_owner_stores(harness.runtime_path, harness.task_path)
    with owner_transaction(owners) as database:
        assert database.execute("PRAGMA main.synchronous").fetchone()[0] == 2
        database.rollback()


def test_terminal_codec_rejects_bool_integer_and_recovery_aliases(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    warrant = _issue(harness)
    terminal = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )
    assert isinstance(terminal, EffectTerminalRecord)

    for field, forged in (
        ("recovery_finalized", 1),
        ("recovery_supervisor_authority_sha256", 1),
        ("claimed_by", 1),
        ("effect_key", 1),
        ("target_nlink_after", True),
    ):
        payload = terminal.to_dict()
        payload[field] = forged
        with pytest.raises(ValueError):
            terminal_from_json(canonical_json(payload))
