from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import dharma_swarm.governed_patch_effect as effect_impl
import dharma_swarm.governed_patch_effect_target as target_impl
from dharma_swarm.evolution_safety import EVOLUTION_MARKER
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.forge_lab.worktree import create_marked_scratch_worktree
from dharma_swarm.governed_patch_candidate_bundle import (
    CandidateBundle,
    build_candidate_bundle,
)
from dharma_swarm.governed_patch_effect import (
    GovernedPatchEffectError,
    inspect_effect_target,
)
from dharma_swarm.governed_patch_evidence import (
    GOVERNED_PATCH_REQUEST_SCHEMA,
    NativePatchBindings,
    parse_governed_patch_request,
)
from dharma_swarm.mission_control_effect_warrant import scratch_identity_for
from dharma_swarm.mission_control_effect_records import (
    CanaryVerifierBinding,
    OwnerStoreBinding,
)
from dharma_swarm.mission_control_effect_warrant import (
    CanaryPatchBinding,
    EffectBinding,
)

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
    process = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    return process.stdout.strip()


@dataclass(frozen=True, slots=True)
class Harness:
    source_repo: Path
    approved_root: Path
    scratch: Path
    candidate: CandidateBundle
    bindings: NativePatchBindings
    git_executable: Path


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    source_repo = tmp_path / "canonical-source"
    (source_repo / "pkg").mkdir(parents=True)
    (source_repo / SOURCE_PATH).write_text(SOURCE, encoding="utf-8", newline="")
    _git(source_repo, "init", "-b", "main")
    _git(source_repo, "config", "user.email", "effect-test@example.invalid")
    _git(source_repo, "config", "user.name", "Effect Test")
    _git(source_repo, "add", "--", SOURCE_PATH)
    _git(source_repo, "commit", "-m", "base")
    base_sha = _git(source_repo, "rev-parse", "HEAD")
    bindings = NativePatchBindings(
        mission_id="mission-1",
        task_id="task-1",
        attempt_id="packet-1",
        lease_id=DELIVERY_ID,
        packet_id="packet-1",
        correlation_id="a2a_send:codex_composer:packet-1",
        delivery_id=DELIVERY_ID,
        proposal_id="proposal-1",
        base_sha=base_sha,
        executor_agent_uid="codex_composer",
        executor_run_id="executor-run-1",
        executor_process_boot_id="executor-boot-1",
    )
    request_payload = {
        "schema_version": GOVERNED_PATCH_REQUEST_SCHEMA,
        **bindings.to_dict(),
        "authorized_source_path": SOURCE_PATH,
        "oracle_argv": ["python3", "-m", "pytest", "tests/test_example.py", "-q"],
    }
    content = json.dumps(request_payload, sort_keys=True, separators=(",", ":"))
    request = parse_governed_patch_request(
        content,
        repo_root=source_repo,
        expected=bindings,
        accepted_base_sha=base_sha,
        expected_content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )
    candidate = build_candidate_bundle(
        request,
        DIFF,
        bundle_root=tmp_path / "candidate-evidence",
    )
    approved_root = tmp_path / "approved-evolution-root"
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(approved_root))
    scratch = create_marked_scratch_worktree(
        source_repo=source_repo,
        experiment_id="governed-effect-test",
        archive_path=tmp_path / "archive",
        base_ref=base_sha,
    )
    git_executable = Path(shutil.which("git") or "/usr/bin/git").resolve(strict=True)
    return Harness(
        source_repo, approved_root, scratch, candidate, bindings, git_executable
    )


def _inspect(harness: Harness):
    return inspect_effect_target(
        harness.candidate,
        harness.scratch,
        approved_scratch_root=harness.approved_root,
        trusted_canonical_repo=harness.source_repo,
        git_executable=harness.git_executable,
        expected_os_uid=os.getuid(),
    )


def _effect_binding(harness: Harness) -> EffectBinding:
    scratch = _inspect(harness)
    candidate = harness.candidate
    native = candidate.bindings
    effect_key = "governed_patch_effect:" + hashlib.sha256(
        scratch.scratch_identity.encode("utf-8")
    ).hexdigest()
    canary = CanaryPatchBinding(
        mission_id=native.mission_id,
        task_id=native.task_id,
        mission_attempt_id="mission-attempt-1",
        mission_claim_id="mission-claim-1",
        packet_id=native.packet_id,
        correlation_id=native.correlation_id,
        delivery_id=native.delivery_id,
        proposal_id=native.proposal_id,
        a2a_content_sha256=candidate.request_content_sha256,
        attempt_key="attempt-key-1",
        operator_id="operator-1",
        assigned_by="supervisor-1",
        candidate_digest=candidate.candidate_digest,
        diff_sha256=candidate.diff_sha256,
        base_sha=native.base_sha,
        artifact_sha256="a" * 64,
        candidate_bundle_sha256=candidate.bundle_sha256,
        authorized_source_files=(candidate.authorized_source_path,),
        executor_agent_uid=native.executor_agent_uid,
        executor_run_id=native.executor_run_id,
        executor_process_boot_id=native.executor_process_boot_id,
        proposal_receipt_id="proposal-receipt-1",
        proposal_receipt_sha256="b" * 64,
        oracle_argv_sha256=canonical_sha256(list(candidate.oracle_argv)),
        effect_key=effect_key,
        scratch=scratch,
        foundry_verifier=CanaryVerifierBinding(
            "foundry_canary", "foundry-verifier", "foundry-run", "foundry-key"
        ),
        vibe_verifier=CanaryVerifierBinding(
            "vibe_canary", "vibe-verifier", "vibe-run", "vibe-key"
        ),
    )
    return EffectBinding(
        canary=canary,
        owner_stores=OwnerStoreBinding(
            runtime_database_path="/runtime.db",
            runtime_database_device=1,
            runtime_database_inode=2,
            runtime_database_mode=0o600,
            runtime_database_uid=os.getuid(),
            runtime_database_gid=os.getgid(),
            runtime_database_nlink=1,
            runtime_ancestry_sha256="3" * 64,
            task_database_path="/tasks.db",
            task_database_device=1,
            task_database_inode=3,
            task_database_mode=0o600,
            task_database_uid=os.getuid(),
            task_database_gid=os.getgid(),
            task_database_nlink=1,
            task_ancestry_sha256="4" * 64,
        ),
        independent_verification_sha256="c" * 64,
        foundry_canary_evidence_sha256="d" * 64,
        foundry_process_receipt_sha256="e" * 64,
        vibe_process_receipt_sha256="f" * 64,
        vibe_patch_receipt_sha256="1" * 64,
        supervisor_authority_sha256="2" * 64,
        supervisor_id="supervisor-1",
        supervisor_process_boot_id="supervisor-boot-1",
    )


def test_inspection_binds_exact_clean_detached_preimage(harness: Harness) -> None:
    binding = _inspect(harness)

    assert binding.resolved_root == str(harness.scratch.resolve())
    assert binding.approved_scratch_root == str(harness.approved_root.resolve())
    assert binding.base_sha == harness.bindings.base_sha
    assert binding.source_path == SOURCE_PATH
    assert binding.preimage_sha256 == hashlib.sha256(SOURCE.encode()).hexdigest()
    assert binding.postimage_sha256 == hashlib.sha256(POSTIMAGE.encode()).hexdigest()
    assert binding.target_inode == (harness.scratch / SOURCE_PATH).stat().st_ino
    assert binding.marker_sha256 == hashlib.sha256(
        (harness.scratch / EVOLUTION_MARKER).read_bytes()
    ).hexdigest()
    assert binding.scratch_identity == scratch_identity_for(binding)
    assert (harness.scratch / SOURCE_PATH).read_text(encoding="utf-8") == SOURCE


def test_private_classifier_accepts_only_original_bound_preimage(
    harness: Harness,
) -> None:
    binding = _effect_binding(harness)

    observed = effect_impl._classify_prevalidated_effect(binding, harness.candidate)

    assert (observed.state, observed.disposition, observed.reason) == (
        "preimage",
        "reissuable",
        "exact_original_preimage",
    )


def test_private_classifier_resumes_only_exact_recovery_temp(harness: Harness) -> None:
    binding = _effect_binding(harness)
    operation_id = hashlib.sha256(binding.effect_key.encode("utf-8")).hexdigest()
    temporary = (
        (harness.scratch / SOURCE_PATH).parent / f".foundry-replay-{operation_id}"
    )
    temporary.write_text(POSTIMAGE, encoding="utf-8", newline="")
    temporary.chmod((harness.scratch / SOURCE_PATH).stat().st_mode & 0o777)

    observed = effect_impl._classify_prevalidated_effect(binding, harness.candidate)

    assert (observed.state, observed.disposition, observed.reason) == (
        "preimage",
        "reissuable",
        "exact_original_preimage_with_recovery_temp",
    )
    mutation = effect_impl._perform_prevalidated_effect(binding, harness.candidate)
    assert mutation.postimage_sha256 == hashlib.sha256(POSTIMAGE.encode()).hexdigest()
    assert (harness.scratch / SOURCE_PATH).read_text(encoding="utf-8") == POSTIMAGE


def test_private_classifier_quarantines_mismatched_recovery_temp(
    harness: Harness,
) -> None:
    binding = _effect_binding(harness)
    operation_id = hashlib.sha256(binding.effect_key.encode("utf-8")).hexdigest()
    temporary = (
        (harness.scratch / SOURCE_PATH).parent / f".foundry-replay-{operation_id}"
    )
    temporary.write_text("forged recovery bytes\n", encoding="utf-8")

    observed = effect_impl._classify_prevalidated_effect(binding, harness.candidate)

    assert (observed.state, observed.disposition, observed.reason) == (
        "preimage",
        "quarantine",
        "invalid_recovery_temp",
    )


def test_private_classifier_finalizes_only_atomic_replacement_postimage(
    harness: Harness,
) -> None:
    binding = _effect_binding(harness)
    mutation = effect_impl._perform_prevalidated_effect(binding, harness.candidate)

    observed = effect_impl._classify_prevalidated_effect(binding, harness.candidate)

    assert mutation.target_inode_after != mutation.target_inode_before
    assert mutation.target_mode_after == mutation.target_mode_before
    assert mutation.target_uid_after == mutation.target_uid_before
    assert mutation.target_gid_after == mutation.target_gid_before
    assert mutation.target_nlink_after == mutation.target_nlink_before == 1
    assert (observed.state, observed.disposition, observed.reason) == (
        "postimage",
        "recovery_finalizable",
        "exact_atomic_postimage",
    )


def test_private_classifier_quarantines_ambiguous_bytes(harness: Harness) -> None:
    binding = _effect_binding(harness)
    (harness.scratch / SOURCE_PATH).write_text("ambiguous\n", encoding="utf-8")

    observed = effect_impl._classify_prevalidated_effect(binding, harness.candidate)

    assert (observed.state, observed.disposition, observed.reason) == (
        "ambiguous",
        "quarantine",
        "ambiguous_target_bytes",
    )


def test_private_classifier_quarantines_in_place_postimage(harness: Harness) -> None:
    binding = _effect_binding(harness)
    target = harness.scratch / SOURCE_PATH
    original_inode = target.stat().st_ino
    target.write_text(POSTIMAGE, encoding="utf-8", newline="")
    assert target.stat().st_ino == original_inode

    observed = effect_impl._classify_prevalidated_effect(binding, harness.candidate)

    assert (observed.state, observed.disposition, observed.reason) == (
        "postimage",
        "quarantine",
        "postimage_on_original_inode",
    )


def test_private_mutation_never_terminalizes_in_place_postimage(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _effect_binding(harness)
    target = harness.scratch / SOURCE_PATH
    original_inode = target.stat().st_ino

    def in_place_then_fail(*_args, **_kwargs) -> None:
        target.write_text(POSTIMAGE, encoding="utf-8", newline="")
        raise effect_impl.PatchReplayError("simulated non-atomic writer")

    monkeypatch.setattr(effect_impl, "apply_unified_diff", in_place_then_fail)
    with pytest.raises(GovernedPatchEffectError, match="exact atomic postimage"):
        effect_impl._perform_prevalidated_effect(binding, harness.candidate)
    assert target.stat().st_ino == original_inode


def test_private_classifier_quarantines_preimage_on_replacement_inode(
    harness: Harness,
) -> None:
    binding = _effect_binding(harness)
    target = harness.scratch / SOURCE_PATH
    replacement = target.with_name("replacement")
    replacement.write_text(SOURCE, encoding="utf-8", newline="")
    replacement.chmod(target.stat().st_mode & 0o777)
    replacement.replace(target)

    observed = effect_impl._classify_prevalidated_effect(binding, harness.candidate)

    assert (observed.state, observed.disposition, observed.reason) == (
        "preimage",
        "quarantine",
        "preimage_on_replacement_inode",
    )


def test_private_classifier_rejects_replaced_target_parent(harness: Harness) -> None:
    binding = _effect_binding(harness)
    parent = (harness.scratch / SOURCE_PATH).parent
    displaced = harness.approved_root / "displaced-pkg"
    parent.rename(displaced)
    parent.mkdir()
    (parent / Path(SOURCE_PATH).name).write_text(SOURCE, encoding="utf-8", newline="")

    with pytest.raises(GovernedPatchEffectError, match="scratch target binding drifted"):
        effect_impl._classify_prevalidated_effect(binding, harness.candidate)


@pytest.mark.parametrize(
    "surface",
    ["approved_parent", "approved", "scratch", "target_parent", "target"],
)
def test_inspection_rejects_group_writable_custody(
    harness: Harness,
    surface: str,
) -> None:
    paths = {
        "approved_parent": harness.approved_root.parent,
        "approved": harness.approved_root,
        "scratch": harness.scratch,
        "target_parent": (harness.scratch / SOURCE_PATH).parent,
        "target": harness.scratch / SOURCE_PATH,
    }
    paths[surface].chmod(paths[surface].stat().st_mode | 0o020)

    with pytest.raises(GovernedPatchEffectError, match="custody is unsafe"):
        _inspect(harness)


@pytest.mark.parametrize(("mode", "accepted"), [(0o1777, True), (0o0777, False)])
def test_root_owned_writable_ancestor_requires_sticky_bit(
    mode: int, accepted: bool,
) -> None:
    directory = Mock()
    directory.stat.return_value = SimpleNamespace(
        st_mode=stat.S_IFDIR | mode,
        st_uid=0,
        st_gid=0,
        st_dev=1,
        st_ino=2,
    )
    if accepted:
        identity = target_impl._directory_identity(
            directory, expected_uid=os.getuid(), allow_root_owner=True,
        )
        assert identity["mode"] == mode
    else:
        with pytest.raises(GovernedPatchEffectError, match="custody is unsafe"):
            target_impl._directory_identity(
                directory, expected_uid=os.getuid(), allow_root_owner=True,
            )


@pytest.mark.parametrize("surface", ["marker", "target"])
def test_inspection_rejects_hardlinked_authority_file(
    harness: Harness,
    surface: str,
) -> None:
    source = (
        harness.scratch / EVOLUTION_MARKER
        if surface == "marker"
        else harness.scratch / SOURCE_PATH
    )
    os.link(source, harness.approved_root / f"{surface}-alias")

    with pytest.raises(GovernedPatchEffectError, match="custody is unsafe"):
        _inspect(harness)


def test_inspection_requires_current_supervisor_uid(harness: Harness) -> None:
    with pytest.raises(GovernedPatchEffectError, match="OS uid is not current"):
        inspect_effect_target(
            harness.candidate,
            harness.scratch,
            approved_scratch_root=harness.approved_root,
            trusted_canonical_repo=harness.source_repo,
            git_executable=harness.git_executable,
            expected_os_uid=os.getuid() + 1,
        )


def test_inspection_rejects_wrong_bundle_sha_and_marker_base(harness: Harness) -> None:
    with pytest.raises(GovernedPatchEffectError, match="bundle revalidation"):
        inspect_effect_target(
            replace(harness.candidate, bundle_sha256="f" * 64),
            harness.scratch,
            approved_scratch_root=harness.approved_root,
            trusted_canonical_repo=harness.source_repo,
            git_executable=harness.git_executable,
            expected_os_uid=os.getuid(),
        )

    marker_path = harness.scratch / EVOLUTION_MARKER
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["git_base_sha"] = "b" * 40
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    with pytest.raises(GovernedPatchEffectError, match="marker.*candidate base"):
        _inspect(harness)


def test_ambient_root_cannot_widen_pinned_authority(
    harness: Harness,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrong_root = tmp_path / "wrong-approved-root"
    wrong_root.mkdir()
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", "/")

    with pytest.raises(GovernedPatchEffectError, match="pinned approved root"):
        inspect_effect_target(
            harness.candidate,
            harness.scratch,
            approved_scratch_root=wrong_root,
            trusted_canonical_repo=harness.source_repo,
            git_executable=harness.git_executable,
            expected_os_uid=os.getuid(),
        )
    with pytest.raises(GovernedPatchEffectError, match="canonical/live"):
        inspect_effect_target(
            harness.candidate,
            harness.source_repo,
            approved_scratch_root=tmp_path,
            trusted_canonical_repo=harness.source_repo,
            git_executable=harness.git_executable,
            expected_os_uid=os.getuid(),
        )


def test_inspection_rejects_attached_symlink_and_path_drift(harness: Harness) -> None:
    _git(harness.scratch, "switch", "-c", "unsafe-attached")
    with pytest.raises(GovernedPatchEffectError, match="not detached"):
        _inspect(harness)
    _git(harness.scratch, "switch", "--detach", harness.bindings.base_sha)

    target = harness.scratch / SOURCE_PATH
    external = harness.approved_root / "external.py"
    external.write_text(SOURCE, encoding="utf-8")
    target.unlink()
    target.symlink_to(external)
    with pytest.raises(GovernedPatchEffectError, match="symlink|unsafe|escapes"):
        _inspect(harness)

    target.unlink()
    target.write_text(SOURCE, encoding="utf-8")
    target.rename(target.with_name("moved.py"))
    with pytest.raises(GovernedPatchEffectError, match="unavailable"):
        _inspect(harness)


def test_inspection_rejects_foreign_registered_worktree(
    harness: Harness, tmp_path: Path
) -> None:
    foreign = tmp_path / "foreign-canonical"
    _git(tmp_path, "clone", "--no-hardlinks", str(harness.source_repo), str(foreign))
    foreign_scratch = create_marked_scratch_worktree(
        source_repo=foreign,
        experiment_id="foreign-effect-test",
        archive_path=tmp_path / "foreign-archive",
        base_ref=harness.bindings.base_sha,
    )

    with pytest.raises(GovernedPatchEffectError, match="trusted repo"):
        inspect_effect_target(
            harness.candidate,
            foreign_scratch,
            approved_scratch_root=harness.approved_root,
            trusted_canonical_repo=harness.source_repo,
            git_executable=harness.git_executable,
            expected_os_uid=os.getuid(),
        )


@pytest.mark.parametrize("ignored", [False, True])
def test_inspection_rejects_extra_untracked_or_ignored_file(
    harness: Harness, ignored: bool
) -> None:
    rogue = harness.scratch / "rogue.txt"
    if ignored:
        exclude = Path(_git(harness.scratch, "rev-parse", "--git-path", "info/exclude"))
        exclude.write_text(
            exclude.read_text(encoding="utf-8") + "\nrogue.txt\n", encoding="utf-8"
        )
    rogue.write_text("not authorized\n", encoding="utf-8")

    with pytest.raises(GovernedPatchEffectError, match="inventory.*allowlist"):
        _inspect(harness)


@pytest.mark.parametrize("flag", ["--skip-worktree", "--assume-unchanged"])
def test_inspection_rejects_non_default_index_flags(
    harness: Harness, flag: str
) -> None:
    _git(harness.scratch, "update-index", flag, "--", SOURCE_PATH)

    with pytest.raises(GovernedPatchEffectError, match="non-default tracked-file flags"):
        _inspect(harness)


def test_inspection_rejects_gitlink_in_authorized_source_slot(harness: Harness) -> None:
    _git(
        harness.scratch,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{harness.bindings.base_sha},{SOURCE_PATH}",
    )

    with pytest.raises(GovernedPatchEffectError, match="stage-0 regular Git blob"):
        _inspect(harness)


def test_candidate_boundary_rejects_multi_path_effect(harness: Harness) -> None:
    second = """--- a/pkg/other.py
+++ b/pkg/other.py
@@ -1 +1 @@
-old
+new
"""
    request = json.loads(harness.candidate.request_bytes.decode("utf-8"))
    content = json.dumps(request, sort_keys=True, separators=(",", ":"))
    parsed = parse_governed_patch_request(
        content,
        repo_root=harness.source_repo,
        expected=harness.bindings,
        accepted_base_sha=harness.bindings.base_sha,
    )
    with pytest.raises(Exception, match="exactly one file"):
        build_candidate_bundle(
            parsed,
            DIFF + second,
            bundle_root=harness.candidate.bundle_root.parent / "multi",
        )
