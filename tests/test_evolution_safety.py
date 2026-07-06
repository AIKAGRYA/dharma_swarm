"""PR-001 fail-closed evolution safety tests.

Proves the polarity inversion: live-checkout mutation is impossible by default;
scratch/shadow experimentation is preserved; every attempt is receipted.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dharma_swarm import evolution_safety as esafe
from dharma_swarm.diff_applier import DiffApplier


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _make_scratch_worktree(root: Path, experiment_id: str = "exp-1") -> Path:
    repo = root / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    marker = repo / esafe.EVOLUTION_MARKER
    marker.write_text(
        json.dumps(
            {
                "experiment_id": experiment_id,
                "git_base_sha": "deadbeef",
                "created_at": "2026-07-06T00:00:00Z",
                "archive_path": str(root / "archive"),
                "parent_id": "parent-0",
                "candidate_id": "cand-1",
            }
        ),
        encoding="utf-8",
    )
    return repo


_HELLO_DIFF = (
    "--- /dev/null\n"
    "+++ b/hello.txt\n"
    "@@ -0,0 +1,1 @@\n"
    "+hello\n"
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in (
        "DHARMA_EVOLUTION_SHADOW", "DHARMA_SELF_IMPROVE", "DHARMA_ALLOW_LIVE_MUTATION",
        "DGC_AUTONOMY_LEVEL", "DHARMA_EVOLUTION_WORKTREE_ROOT", "DHARMA_MODEL_BUDGET_USD",
        "DHARMA_ALLOW_CUSTODIAN_MERGE", "DHARMA_PROMOTION_TARGET_SHA",
    ):
        monkeypatch.delenv(k, raising=False)
    yield


# --------------------------------------------------------------------------- #
# 1 & 2: DiffApplier refuses the live repo root and the ~ / VPS paths
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_diffapplier_refuses_protected_roots(tmp_path):
    for root in (
        Path.home() / "dharma_swarm",
        Path("/root/dharma_swarm"),
        Path("/home/openclaw/dharma_swarm"),
        Path("/Users/dhyana/dharma_swarm"),
    ):
        applier = DiffApplier(workspace=root)
        res = await applier.apply(_HELLO_DIFF)
        assert res.success is False
        assert "protected live checkout" in (res.error or "")


@pytest.mark.asyncio
async def test_diffapplier_refuses_protected_targets_below_safe_ancestor(tmp_path):
    app = tmp_path / "app"
    protected = app / "dharma_swarm"
    (protected / "dharma_swarm").mkdir(parents=True)
    (protected / "dharma_swarm" / "__init__.py").write_text("", encoding="utf-8")
    (protected / ".git").mkdir()
    target = protected / "foo.py"
    target.write_text("old\n", encoding="utf-8")

    diff = (
        "--- a/dharma_swarm/foo.py\n"
        "+++ b/dharma_swarm/foo.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n"
        "+new\n"
    )

    applier = DiffApplier(workspace=app)
    res = await applier.apply(diff)
    assert res.success is False
    assert "protected live checkout" in (res.error or "")
    assert target.read_text(encoding="utf-8") == "old\n"
    assert not target.with_suffix(target.suffix + ".bak").exists()


def test_is_protected_live_root_detects_main_repo(tmp_path):
    # A dir that looks like the main repo (has .git + dharma_swarm/__init__.py)
    repo = tmp_path / "mainrepo"
    (repo / "dharma_swarm").mkdir(parents=True)
    (repo / "dharma_swarm" / "__init__.py").write_text("", encoding="utf-8")
    (repo / ".git").mkdir()
    assert esafe.is_protected_live_root(repo) is True


# --------------------------------------------------------------------------- #
# 3: DiffApplier accepts a marked scratch worktree under the worktree root
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_diffapplier_accepts_marked_scratch_worktree(tmp_path, monkeypatch):
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(tmp_path))
    repo = _make_scratch_worktree(tmp_path)
    ok, marker, why = esafe.is_scratch_worktree(repo)
    assert ok is True, why
    assert marker.experiment_id == "exp-1"
    applier = DiffApplier(workspace=repo)
    res = await applier.apply(_HELLO_DIFF)
    assert res.success is True
    assert (repo / "hello.txt").read_text().strip() == "hello"


def test_unmarked_dir_under_root_is_not_scratch(tmp_path, monkeypatch):
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(tmp_path))
    plain = tmp_path / "no_marker"
    plain.mkdir()
    ok, _m, why = esafe.is_scratch_worktree(plain)
    assert ok is False
    assert "marker" in why


# --------------------------------------------------------------------------- #
# 4: SelfImprovementCycle does not target ~/dharma_swarm by default
# --------------------------------------------------------------------------- #

def test_self_improve_targets_protected_root_by_default():
    from dharma_swarm import self_improve

    # The module constant still points at the live checkout ...
    assert self_improve.DHARMA_SWARM_DIR == Path.home() / "dharma_swarm"
    # ... but the guard classifies that target as protected -> denied.
    decision = esafe.evaluate_mutation(
        target_workspace=self_improve.DHARMA_SWARM_DIR,
        requested_live=True,
        runtime_state_available=False,
    )
    assert decision.allowed is False
    assert decision.denial_reason.startswith("protected_live_root")


# --------------------------------------------------------------------------- #
# 5: free-grind cannot call live auto_evolve by default (shadow forced True)
# --------------------------------------------------------------------------- #

def test_free_grind_shadow_forced_without_lease(monkeypatch):
    # Replicate the exact fail-closed expression used in orchestrate_live grind.
    monkeypatch.setenv("DHARMA_ALLOW_LIVE_MUTATION", "1")  # even with opt-in ...
    lease = esafe.load_live_mutation_lease()  # ... no lease exists
    grind_shadow = not (esafe.allow_live_mutation_env() and lease is not None)
    assert grind_shadow is True


def test_free_grind_source_present_in_orchestrate_live():
    # One-door (U1) tightened PR-001's posture: the grind lane no longer has a
    # lease-conditional live path at all — auto_evolve is hardcoded shadow-only.
    # Live apply exists only via forge_v2.verify_promotion sealed packets.
    src = Path(__file__).resolve().parents[1] / "dharma_swarm" / "orchestrate_live.py"
    text = src.read_text(encoding="utf-8")
    assert "shadow=True,  # one-door" in text
    assert "shadow=_grind_shadow" not in text  # the lease-conditional live call is gone
    assert "shadow=False,  # Real mode" not in text  # the old hardcoded live call is gone


# --------------------------------------------------------------------------- #
# 6: custodians scheduled path cannot merge by default
# --------------------------------------------------------------------------- #

def test_custodians_merge_infra_incomplete_by_default(tmp_path):
    from dharma_swarm import custodians

    ok, why = custodians._promotion_infra_complete(str(tmp_path), "cron")
    assert ok is False
    assert "DHARMA_ALLOW_CUSTODIAN_MERGE!=1" in why or "no_promotion_lease" in why


def test_custodians_git_merge_denied_by_default(tmp_path):
    from dharma_swarm import custodians

    # Even called directly, the merge refuses (returns False) with no infra.
    assert custodians._git_merge_to_main(str(tmp_path), "darwin/cycle-x") is False


# --------------------------------------------------------------------------- #
# 7: CodeIdentity marks dirty/untracked checkout non_promotable
# --------------------------------------------------------------------------- #

def test_code_identity_non_promotable_on_missing_git(tmp_path):
    ident = esafe.RuntimeCodeIdentity.capture(tmp_path)  # not a git repo
    assert ident.mode == "non_promotable"
    assert "git_metadata_unavailable" in ident.reason
    # never crashes; unknowns recorded as 'unknown'
    assert ident.git_sha == "unknown"
    assert ident.branch == "unknown"


# --------------------------------------------------------------------------- #
# 8: blocked mutation writes a receipt / local denial artifact
# --------------------------------------------------------------------------- #

def test_blocked_mutation_writes_receipt(tmp_path):
    archive = tmp_path / "archive"
    decision = esafe.evaluate_mutation(
        target_workspace="/root/dharma_swarm",
        requested_live=True,
        runtime_state_available=False,
    )
    esafe.write_mutation_receipt(
        decision, actor="test", archive_path=archive, experiment_id="exp-9"
    )
    log = archive / "mutation_receipts.jsonl"
    assert log.is_file()
    row = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert row["allowed"] is False
    assert row["denial_reason"].startswith("protected_live_root")
    assert row["experiment_id"] == "exp-9"


# --------------------------------------------------------------------------- #
# 9: live mutation without lease fails closed
# --------------------------------------------------------------------------- #

def test_live_mutation_without_lease_downgrades_to_shadow(tmp_path, monkeypatch):
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(tmp_path))
    monkeypatch.setenv("DHARMA_ALLOW_LIVE_MUTATION", "1")
    repo = _make_scratch_worktree(tmp_path)
    decision = esafe.evaluate_mutation(
        target_workspace=repo, requested_live=True, runtime_state_available=True,
    )
    # allowed only as shadow — never a real live apply — because no lease.
    assert decision.effective_shadow is True
    assert "no_valid_live_mutation_lease" in decision.denial_reason


def test_even_full_env_cannot_enable_live_without_lease(tmp_path, monkeypatch):
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("DGC_AUTONOMY_LEVEL", "2")
    monkeypatch.setenv("DHARMA_EVOLUTION_SHADOW", "0")
    monkeypatch.setenv("DHARMA_ALLOW_LIVE_MUTATION", "1")
    repo = _make_scratch_worktree(tmp_path)
    decision = esafe.evaluate_mutation(
        target_workspace=repo, requested_live=True, runtime_state_available=True,
    )
    assert decision.effective_shadow is True  # lease is the missing, unforgeable key


def test_valid_lease_enables_live_in_scratch_only(tmp_path, monkeypatch):
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(tmp_path))
    monkeypatch.setenv("DHARMA_ALLOW_LIVE_MUTATION", "1")
    lease_dir = tmp_path / "leases"
    lease_dir.mkdir()
    (lease_dir / "L1.json").write_text(json.dumps({
        "lease_id": "L1", "target_sha": "abc", "promotion_receipt": "PR-xyz",
        "granted_by_human": "operator", "expires_at": "2999-01-01T00:00:00Z",
    }), encoding="utf-8")
    repo = _make_scratch_worktree(tmp_path)
    d_scratch = esafe.evaluate_mutation(
        target_workspace=repo, requested_live=True, runtime_state_available=True,
        lease_dir=lease_dir,
    )
    assert d_scratch.allowed is True and d_scratch.effective_shadow is False
    # ... but a lease NEVER unlocks the live checkout.
    d_live = esafe.evaluate_mutation(
        target_workspace="/root/dharma_swarm", requested_live=True,
        runtime_state_available=True, lease_dir=lease_dir,
    )
    assert d_live.allowed is False


def test_expired_lease_is_ignored(tmp_path):
    lease_dir = tmp_path / "leases"
    lease_dir.mkdir()
    (lease_dir / "L1.json").write_text(json.dumps({
        "lease_id": "L1", "target_sha": "abc", "promotion_receipt": "PR-xyz",
        "granted_by_human": "operator", "expires_at": "2000-01-01T00:00:00Z",
    }), encoding="utf-8")
    assert esafe.load_live_mutation_lease(lease_dir=lease_dir) is None


# --------------------------------------------------------------------------- #
# 10: Compose defaults are fail-closed
# --------------------------------------------------------------------------- #

def _compose_text() -> str:
    p = Path(__file__).resolve().parents[1] / "docker-compose.yml"
    return p.read_text(encoding="utf-8")


def test_compose_defaults_failclosed():
    t = _compose_text()
    assert "DHARMA_EVOLUTION_SHADOW: ${DHARMA_EVOLUTION_SHADOW:-1}" in t
    assert "DGC_AUTONOMY_LEVEL: ${DGC_AUTONOMY_LEVEL:-1}" in t
    assert "DHARMA_SELF_IMPROVE: ${DHARMA_SELF_IMPROVE:-0}" in t
    assert "DHARMA_ALLOW_LIVE_MUTATION: ${DHARMA_ALLOW_LIVE_MUTATION:-0}" in t
    # no fail-open defaults remain
    assert "${DHARMA_EVOLUTION_SHADOW:-0}" not in t
    assert "${DGC_AUTONOMY_LEVEL:-2}" not in t


def test_compose_source_mount_readonly_and_separated_volumes():
    t = _compose_text()
    assert "./dharma_swarm:/app/dharma_swarm:ro" in t
    assert "/evolution_worktrees" in t
    assert "/evolution_archive" in t
    assert "/mnt/dharma_eval:ro" in t


def test_env_example_failclosed():
    p = Path(__file__).resolve().parents[1] / ".env.example"
    t = p.read_text(encoding="utf-8")
    assert "DHARMA_EVOLUTION_SHADOW=1" in t
    assert "DGC_AUTONOMY_LEVEL=1" in t
    assert "DHARMA_SELF_IMPROVE=0" in t
    assert "DHARMA_ALLOW_LIVE_MUTATION=0" in t


# --------------------------------------------------------------------------- #
# 11: provider key presence does not enable live mutation
# --------------------------------------------------------------------------- #

def test_provider_key_presence_does_not_enable_live(tmp_path, monkeypatch):
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-anything")
    repo = _make_scratch_worktree(tmp_path)
    d = esafe.evaluate_mutation(
        target_workspace=repo, requested_live=True, runtime_state_available=True,
    )
    assert d.effective_shadow is True  # key alone is irrelevant to the gate


def test_autonomy_alone_does_not_enable_live(tmp_path, monkeypatch):
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(tmp_path))
    monkeypatch.setenv("DGC_AUTONOMY_LEVEL", "2")
    repo = _make_scratch_worktree(tmp_path)
    d = esafe.evaluate_mutation(
        target_workspace=repo, requested_live=True, runtime_state_available=True,
    )
    assert d.effective_shadow is True


def test_shadow_zero_alone_does_not_enable_live(tmp_path, monkeypatch):
    monkeypatch.setenv("DHARMA_EVOLUTION_WORKTREE_ROOT", str(tmp_path))
    monkeypatch.setenv("DHARMA_EVOLUTION_SHADOW", "0")
    repo = _make_scratch_worktree(tmp_path)
    d = esafe.evaluate_mutation(
        target_workspace=repo, requested_live=True, runtime_state_available=True,
    )
    assert d.effective_shadow is True


# --------------------------------------------------------------------------- #
# 12-15: evaluator / source mount contracts
# --------------------------------------------------------------------------- #

def test_evaluator_missing_means_no_promotion_grade(tmp_path):
    st = esafe.evaluator_status(tmp_path / "does_not_exist")
    assert st["mounted"] is False
    assert st["promotion_grade_available"] is False


def test_evaluator_writable_means_no_promotion_grade(tmp_path):
    ev = tmp_path / "eval_rw"
    ev.mkdir()
    (ev / "EVALUATOR_SHA").write_text("abc123", encoding="utf-8")
    st = esafe.evaluator_status(ev)
    assert st["mounted"] is True
    assert st["read_only"] is False   # writable
    assert st["promotion_grade_available"] is False


def test_evaluator_readonly_with_sha_is_protected(tmp_path):
    ev = tmp_path / "eval_ro"
    ev.mkdir()
    (ev / "EVALUATOR_SHA").write_text("sha-777", encoding="utf-8")
    os.chmod(ev, 0o500)  # read+execute, not writable
    try:
        st = esafe.evaluator_status(ev)
        assert st["mounted"] is True
        assert st["read_only"] is True
        assert st["sha"] == "sha-777"
        assert st["promotion_grade_available"] is True
    finally:
        os.chmod(ev, 0o700)  # restore so tmp cleanup works


def test_source_mount_readonly_safer_but_not_sufficient(tmp_path):
    src = tmp_path / "src_ro"
    src.mkdir()
    os.chmod(src, 0o500)
    try:
        st = esafe.source_mount_status(src)
        assert st["read_only"] is True
        assert st["sufficient_alone"] is False
    finally:
        os.chmod(src, 0o700)


# --------------------------------------------------------------------------- #
# budget gate + safety summary sanity
# --------------------------------------------------------------------------- #

def test_model_spend_denied_without_budget_gate():
    ok, reason = esafe.model_spend_allowed()
    assert ok is False
    assert reason == "no_budget_gate"


def test_model_spend_allowed_with_budget_env(monkeypatch):
    monkeypatch.setenv("DHARMA_MODEL_BUDGET_USD", "5")
    ok, reason = esafe.model_spend_allowed()
    assert ok is True


def test_safety_summary_reports_live_denied(tmp_path):
    s = esafe.safety_summary(tmp_path)
    assert s["live_mutation_allowed"] is False
    assert s["evolution_shadow"] is True
    assert s["self_improve_enabled"] is False
    assert s["autonomy_level"] in (0, 1)
