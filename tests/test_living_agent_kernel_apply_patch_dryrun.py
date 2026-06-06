"""apply_patch DRY-RUN E2E hardening.

Verification-only proof matrix for the *pre-existing* apply_patch write-gate
(``_dispatch_apply_patch`` ~L2700). No core logic is added here: this module
owns only the proof that

* the DRY-RUN path is genuinely byte-identical non-mutating, and run() tags it
  ``apply_patch_dry_run_only``;
* every rung of the denial ladder fires with its exact ``denial_reason``;
* the LIVE-APPLY path stays FIXTURE-only - gated on explicit sandbox allowance
  AND a rollback receipt AND not-a-new-file - and the one genuinely-mutating
  live-apply runs ONLY inside a pytest ``tmp_path`` sandbox (never the repo),
  writing a load-bearing ``.bak`` that is provably required for rollback.
"""

from __future__ import annotations

import hashlib

import pytest

from dharma_swarm.operator_core.governed_work_admission import WorkKind
from dharma_swarm.operator_core.living_agent_kernel import (
    AgentRunEnvelope,
    AuthorityPassport,
    KernelRunStore,
    KernelTask,
    LivingAgentKernel,
    MemoryPlan,
    ProofRequest,
    ToolRequest,
    TriggerEnvelope,
)

_TARGET = "note.txt"
_BASE_TEXT = "alpha\nbeta\ngamma\n"
_DIFF = (
    "--- a/note.txt\n"
    "+++ b/note.txt\n"
    "@@ -1,3 +1,3 @@\n"
    " alpha\n"
    "-beta\n"
    "+BETA\n"
    " gamma\n"
)
_NEW_FILE_DIFF = (
    "--- /dev/null\n"
    "+++ b/fresh.txt\n"
    "@@ -0,0 +1,1 @@\n"
    "+hello\n"
)
_DELETE_DIFF = (
    "--- a/note.txt\n"
    "+++ /dev/null\n"
    "@@ -1,3 +0,0 @@\n"
    "-alpha\n"
    "-beta\n"
    "-gamma\n"
)


def _kernel(tmp_path) -> LivingAgentKernel:
    return LivingAgentKernel(
        store=KernelRunStore(tmp_path / "kernel"),
        workspace_root=tmp_path,
    )


def _seed_target(tmp_path):
    target = tmp_path / _TARGET
    target.write_text(_BASE_TEXT)
    return target


def _hash(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _envelope(
    *,
    patch: str = _DIFF,
    work_kind: WorkKind = WorkKind.CODE_WRITE,
    mission_contract_present: bool = True,
    workspace_lease_present: bool = True,
    external_worker_authority: str = "",
    allowed_files: list[str] | None = None,
    forbidden_files: list[str] | None = None,
    sandbox_policy: dict | None = None,
) -> AgentRunEnvelope:
    arguments: dict[str, object] = {}
    if patch is not None:
        arguments["patch"] = patch
    return AgentRunEnvelope(
        agent_uid="codex_composer",
        task=KernelTask(text="Dry-run a bounded code patch"),
        trigger=TriggerEnvelope(
            source="persistent_self_wake",
            mission_id="mission-apply",
            task_id="task-apply",
            correlation_id="corr-apply",
            parent_run_id="parent-run",
        ),
        authority=AuthorityPassport(
            work_kind=work_kind,
            risk_tier="Q2",
            mission_contract_present=mission_contract_present,
            workspace_lease_present=workspace_lease_present,
            external_worker_authority=external_worker_authority,
            allowed_files=list(allowed_files if allowed_files is not None else [_TARGET]),
            forbidden_files=list(forbidden_files or []),
        ),
        memory=MemoryPlan(),
        tool_request=ToolRequest(
            requested_tools=["apply_patch"],
            tool_calls=[{"name": "apply_patch", "arguments": arguments}],
            sandbox_policy=dict(sandbox_policy if sandbox_policy is not None else {"mutation_mode": "dry_run"}),
        ),
        proof=ProofRequest(
            verifier_commands=["pytest tests/test_living_agent_kernel_apply_patch_dryrun.py"],
            receipt_refs=[],
        ),
    )


def _dispatch(kernel, envelope):
    arguments = envelope.tool_request.tool_calls[0]["arguments"]
    return kernel._dispatch_apply_patch(envelope, arguments)


# ---------------------------------------------------------------------------
# unit - the full denial ladder, each asserting its exact denial_reason
# ---------------------------------------------------------------------------

_DENIAL_LADDER = [
    pytest.param(
        {"patch": ""},
        "failed",
        "apply_patch_requires_patch_or_diff",
        id="missing_patch",
    ),
    pytest.param(
        {"work_kind": WorkKind.READ_ONLY},
        "denied",
        "apply_patch_requires_code_write_authority",
        id="non_code_write_authority",
    ),
    pytest.param(
        {"mission_contract_present": False, "workspace_lease_present": False},
        "denied",
        "apply_patch_requires_mission_contract_and_workspace_lease",
        id="missing_contract_and_lease",
    ),
    pytest.param(
        {"external_worker_authority": "external_worker_evidence_only"},
        "denied",
        "external_worker_evidence_only",
        id="evidence_only",
    ),
    pytest.param(
        {"sandbox_policy": {"mutation_mode": "frobnicate"}},
        "denied",
        "apply_patch_mutation_mode_invalid",
        id="invalid_mutation_mode",
    ),
]


@pytest.mark.parametrize("overrides,status,reason", _DENIAL_LADDER)
def test_denial_ladder_exact_reasons(tmp_path, overrides, status, reason):
    kernel = _kernel(tmp_path)
    _seed_target(tmp_path)
    result = _dispatch(kernel, _envelope(**overrides))
    assert result.status == status
    assert (result.denial_reason or result.error) == reason


def test_target_outside_workspace_via_relative_traversal_writes_nothing(tmp_path):
    """A literal ``../`` diff path is rejected at the safe-target gate before any
    write. (The path-resolution rung is exercised separately via a symlink.)"""
    kernel = _kernel(tmp_path)
    before = {p.name for p in tmp_path.iterdir()}
    traversal = (
        "--- a/note.txt\n"
        "+++ b/../escape.txt\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n"
        "+new\n"
    )
    result = _dispatch(kernel, _envelope(patch=traversal, allowed_files=["escape.txt"]))
    assert result.status == "denied"
    assert result.denial_reason == "apply_patch_target_path_unsafe"
    assert not (tmp_path.parent / "escape.txt").exists()
    assert {p.name for p in tmp_path.iterdir()} == before


def test_target_resolving_outside_workspace_via_symlink_is_denied(tmp_path):
    """A clean relative target name that *resolves* outside the workspace (via a
    symlink) is denied apply_patch_target_outside_workspace and writes nothing."""
    kernel = _kernel(tmp_path)
    outside_dir = tmp_path.parent / f"{tmp_path.name}_outside"
    outside_dir.mkdir()
    real = outside_dir / "secret.txt"
    real.write_text("untouched\n")
    link = tmp_path / "escape.txt"
    link.symlink_to(real)

    diff = (
        "--- a/escape.txt\n"
        "+++ b/escape.txt\n"
        "@@ -1,1 +1,1 @@\n"
        "-untouched\n"
        "+TAMPERED\n"
    )
    result = _dispatch(kernel, _envelope(patch=diff, allowed_files=["escape.txt"]))
    assert result.status == "denied"
    assert result.denial_reason == "apply_patch_target_outside_workspace"
    assert real.read_text() == "untouched\n"


def test_forbidden_target_denied_even_when_also_allowed(tmp_path):
    """A target matching forbidden_files is denied apply_patch_target_forbidden
    even when it ALSO matches allowed_files (forbidden wins)."""
    kernel = _kernel(tmp_path)
    _seed_target(tmp_path)
    result = _dispatch(
        kernel,
        _envelope(allowed_files=[_TARGET], forbidden_files=[_TARGET]),
    )
    assert result.status == "denied"
    assert result.denial_reason == "apply_patch_target_forbidden"


def test_not_allowed_target_denied(tmp_path):
    kernel = _kernel(tmp_path)
    _seed_target(tmp_path)
    result = _dispatch(kernel, _envelope(allowed_files=["something_else.txt"]))
    assert result.status == "denied"
    assert result.denial_reason == "apply_patch_target_not_allowed"


def test_mutation_mode_normalization(tmp_path):
    """absent policy defaults to dry_run; 'APPLY' uppercases/strips to 'apply'
    (so it advances past the mode-validity gate to the allowance gate); an
    unknown value yields apply_patch_mutation_mode_invalid."""
    kernel = _kernel(tmp_path)
    _seed_target(tmp_path)

    # absent policy -> dry_run default -> completed, non-mutating.
    absent = _dispatch(kernel, _envelope(sandbox_policy={}))
    assert absent.status == "completed"
    assert absent.output["mutation_mode"] == "dry_run"

    # '  APPLY  ' normalizes to 'apply' and is therefore NOT rejected by the
    # mode-validity gate; it falls through to the live-apply allowance gate.
    normalized = _dispatch(
        kernel,
        _envelope(sandbox_policy={"mutation_mode": "  APPLY  "}),
    )
    assert normalized.status == "denied"
    assert normalized.denial_reason == "apply_patch_live_apply_requires_explicit_sandbox_allowance"

    # an unknown value is denied as invalid.
    unknown = _dispatch(
        kernel,
        _envelope(sandbox_policy={"mutation_mode": "wat"}),
    )
    assert unknown.status == "denied"
    assert unknown.denial_reason == "apply_patch_mutation_mode_invalid"


def test_live_apply_gating_ladder_without_repo_writes(tmp_path):
    """Live-apply is denied at each missing precondition without touching disk."""
    kernel = _kernel(tmp_path)
    target = _seed_target(tmp_path)
    before = _hash(target)

    # mutation_mode='apply' but no explicit sandbox allowance.
    no_allow = _dispatch(
        kernel,
        _envelope(sandbox_policy={"mutation_mode": "apply"}),
    )
    assert no_allow.status == "denied"
    assert no_allow.denial_reason == "apply_patch_live_apply_requires_explicit_sandbox_allowance"

    # allowance True but no rollback receipt.
    no_rollback = _dispatch(
        kernel,
        _envelope(
            sandbox_policy={"mutation_mode": "apply", "allow_write_tool_execution": True},
        ),
    )
    assert no_rollback.status == "denied"
    assert no_rollback.denial_reason == "apply_patch_live_apply_requires_rollback_receipt"

    # a new-file diff on apply (with full allowance) is denied - no backup possible.
    new_file = _dispatch(
        kernel,
        _envelope(
            patch=_NEW_FILE_DIFF,
            allowed_files=["fresh.txt"],
            sandbox_policy={
                "mutation_mode": "apply",
                "allow_write_tool_execution": True,
                "rollback_receipt_required": True,
            },
        ),
    )
    assert new_file.status == "denied"
    assert new_file.denial_reason == "apply_patch_new_file_live_apply_lacks_rollback_backup"

    assert _hash(target) == before
    assert not (tmp_path / "note.txt.bak").exists()
    assert not (tmp_path / "fresh.txt").exists()


# ---------------------------------------------------------------------------
# integration - dry-run is observably non-mutating end-to-end through run()
# ---------------------------------------------------------------------------


def test_full_run_dry_run_is_byte_identical_non_mutating(tmp_path):
    kernel = _kernel(tmp_path)
    target = _seed_target(tmp_path)
    before_hash = _hash(target)

    result = kernel.run(_envelope(sandbox_policy={"mutation_mode": "dry_run"}))

    assert result.status == "completed"
    tool_result = result.tool_results[0]
    assert tool_result.tool_name == "apply_patch"
    assert tool_result.status == "completed"
    assert tool_result.output["mutation_mode"] == "dry_run"
    assert tool_result.output["dry_run"] is True
    assert tool_result.output["applied"] is False
    # the diff is *described* (target enumerated) but nothing is applied.
    assert tool_result.output["target_refs"]
    assert tool_result.output["backup_paths"] == {}

    # target byte-identical on disk; no .bak created.
    assert _hash(target) == before_hash
    assert target.read_text() == _BASE_TEXT
    assert not (tmp_path / "note.txt.bak").exists()

    # run-level honest scoping + durable proof-ledger tag.
    assert "apply_patch_dry_run_only" in result.proof_ledger_entry.unsupported_claims
    assert result.proof_ledger_entry.entry_hash.startswith("sha256:")
    assert result.replay_ref["integrity_ok"] is True


# ---------------------------------------------------------------------------
# adversarial
# ---------------------------------------------------------------------------


def test_adversarial_delete_file_diff_denied(tmp_path):
    """A delete-file diff (new_path=='/dev/null') is denied; the file is intact."""
    kernel = _kernel(tmp_path)
    target = _seed_target(tmp_path)
    before = _hash(target)
    result = _dispatch(kernel, _envelope(patch=_DELETE_DIFF))
    assert result.status == "denied"
    assert result.denial_reason == "apply_patch_delete_file_not_supported_in_kernel_v1"
    assert _hash(target) == before


def test_adversarial_dry_run_never_creates_bak_or_writes_outside_tmp(tmp_path):
    """ZERO new files except inside tmp; dry-run leaves no backup artifact."""
    kernel = _kernel(tmp_path)
    _seed_target(tmp_path)
    before = {p.resolve() for p in tmp_path.rglob("*")}

    kernel.run(_envelope(sandbox_policy={"mutation_mode": "dry_run"}))

    after = {p.resolve() for p in tmp_path.rglob("*")}
    new_files = after - before
    for path in new_files:
        assert tmp_path.resolve() in path.parents, f"write leaked outside tmp: {path}"
    assert not any(p.name.endswith(".bak") for p in new_files)


# ---------------------------------------------------------------------------
# tamper - the ONE genuinely-mutating live-apply (tmp_path sandbox ONLY).
# The prod/operator live-apply path is OPERATOR-GATED and intentionally NOT
# auto-run here: this test never touches the repo, only a pytest tmp_path.
# ---------------------------------------------------------------------------


def _live_apply_envelope():
    return _envelope(
        sandbox_policy={
            "mutation_mode": "apply",
            "allow_write_tool_execution": True,
            "rollback_receipt_required": True,
        },
    )


def test_live_apply_in_tmp_sandbox_writes_bak_and_is_rollbackable(tmp_path):
    """The single mutating path: tmp-sandbox only. It writes a .bak rollback,
    changes the target, and the .bak restores the pre-image (load-bearing)."""
    kernel = _kernel(tmp_path)
    target = _seed_target(tmp_path)

    result = kernel.run(_live_apply_envelope())

    tool_result = result.tool_results[0]
    assert tool_result.status == "completed"
    assert tool_result.output["mutation_mode"] == "apply"
    assert tool_result.output["applied"] is True
    assert tool_result.output["rollback_available"] is True

    # the target genuinely changed.
    assert target.read_text() != _BASE_TEXT
    assert "BETA" in target.read_text()

    # a .bak rollback was written and holds the exact pre-image.
    backup = tmp_path / "note.txt.bak"
    assert backup.exists()
    assert backup.read_text() == _BASE_TEXT

    # rollback restores the original byte-for-byte (the receipt is real).
    target.write_bytes(backup.read_bytes())
    assert target.read_text() == _BASE_TEXT


def test_tamper_corrupting_bak_surfaces_rollback_dependency(tmp_path):
    """Deleting/corrupting the .bak after a live-apply makes faithful rollback
    impossible - proving the rollback receipt is load-bearing, not decorative.

    A SECOND live-apply against the same target is then denied, because the
    gate refuses to clobber an already-present .bak path (the rollback receipt
    of the prior run is still nominally on disk / its slot is occupied)."""
    kernel = _kernel(tmp_path)
    target = _seed_target(tmp_path)

    result = kernel.run(_live_apply_envelope())
    assert result.tool_results[0].status == "completed"

    backup = tmp_path / "note.txt.bak"
    assert backup.exists()

    # Corrupt the rollback receipt: faithful restore is now impossible.
    backup.write_text("CORRUPTED ROLLBACK DATA\n")
    mutated = target.read_text()
    target.write_bytes(backup.read_bytes())
    assert target.read_text() != _BASE_TEXT  # cannot recover the pre-image

    # restore a mutated body and a clean second run is BLOCKED on the occupied
    # rollback-backup slot - the gate will not overwrite a live receipt path.
    target.write_text(mutated)
    second = kernel.run(_live_apply_envelope())
    second_tool = second.tool_results[0]
    assert second_tool.status == "denied"
    assert second_tool.denial_reason == "apply_patch_rollback_backup_path_already_exists"


@pytest.mark.skip(
    reason="prod/operator live-apply against a real repo workspace is "
    "OPERATOR-GATED and never auto-run in CI; the gate is proven here only "
    "inside a pytest tmp_path sandbox."
)
def test_operator_gated_prod_live_apply_documented_only():  # pragma: no cover
    raise AssertionError("operator-gated; must never auto-run")
