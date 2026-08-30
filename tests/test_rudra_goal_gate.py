"""Layer B: GoalGate admission, evaluation, and false-green rejection.

Normative source: docs/plans/rudra_v0/TEST_AND_BURNIN_PLAN.md section 2B and
RUDRA_BUILD_SPEC.md section 8. Each mutant claims success; the gate must
stay red.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.rudra.contracts import (
    AdmissionError,
    AdmissionReject,
    GoalGatePassed,
    ReportedCompletion,
)
from dharma_swarm.rudra.goal_gate import (
    CandidateRejected,
    GoalGate,
    PromotionRejected,
)
from dharma_swarm.rudra.workcell import Workcell
from tests.fixtures.rudra.helpers import (
    FIXED_TARGET,
    make_base_repo,
    make_mission_yaml,
)


@pytest.fixture()
def admitted(tmp_path: Path):
    repo, base = make_base_repo(tmp_path)
    text = make_mission_yaml(repo, base)
    gate = GoalGate(repo, state_dir=tmp_path / "state")
    return gate, gate.admit(text), repo, base


def _workcell(gate: GoalGate, admitted) -> Workcell:
    return Workcell(
        Path(admitted.attempt_dir), gate.repo_path,
        admitted.contract.repository.base_sha, gate.state_root,
    )


def test_admission_baseline_red(admitted) -> None:
    gate, adm, repo, base = admitted
    assert adm.baseline is not None and not adm.baseline.green
    assert (Path(adm.mission_dir) / "admitted.json").exists()
    # Base preservation: admission wrote nothing to the base checkout.
    assert gate.prove_base_preserved(adm)


def test_already_satisfied_rejected(tmp_path: Path) -> None:
    repo, base = make_base_repo(tmp_path, fixed=True)
    text = make_mission_yaml(repo, base)
    gate = GoalGate(repo, state_dir=tmp_path / "state")
    with pytest.raises(AdmissionError) as excinfo:
        gate.admit(text)
    assert excinfo.value.code == AdmissionReject.ALREADY_SATISFIED


def test_stale_lockfile_digest_rejected(tmp_path: Path) -> None:
    repo, base = make_base_repo(tmp_path)
    text = make_mission_yaml(
        repo, base,
        overrides={"toolchain.lockfile.sha256": "0" * 64},
    )
    gate = GoalGate(repo, state_dir=tmp_path / "state")
    with pytest.raises(AdmissionError) as excinfo:
        gate.admit(text)
    assert excinfo.value.code == AdmissionReject.REJECT_INVALID


def test_wrong_base_rejected(tmp_path: Path) -> None:
    repo, base = make_base_repo(tmp_path)
    text = make_mission_yaml(
        repo, "0" * 40,
    )
    gate = GoalGate(repo, state_dir=tmp_path / "state")
    with pytest.raises(AdmissionError):
        gate.admit(text)


def test_g01_executor_prose_no_change_stays_red(admitted) -> None:
    """Executor prints complete and exits zero with no valid change."""
    gate, adm, _repo, _base = admitted
    result = gate.evaluate(adm)
    assert not result.green
    assert any("empty diff" in r for r in result.reasons)


def test_green_after_valid_change(admitted) -> None:
    gate, adm, _repo, _base = admitted
    workcell = _workcell(gate, adm)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    result = gate.evaluate(adm)
    assert result.green, result.reasons
    assert result.changed_paths == ["src/target.py"]


def test_g04_test_edit_stays_red(admitted) -> None:
    gate, adm, _repo, _base = admitted
    workcell = _workcell(gate, adm)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    (workcell.worktree / "tests" / "test_target.py").write_text("def test_answer():\n    pass\n")
    result = gate.evaluate(adm)
    assert not result.green
    assert any("forbidden path" in r for r in result.reasons)


def test_outside_allowed_path_stays_red(admitted) -> None:
    gate, adm, _repo, _base = admitted
    workcell = _workcell(gate, adm)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    (workcell.worktree / "README.md").write_text("surprise\n")
    result = gate.evaluate(adm)
    assert not result.green
    assert any("outside allowed" in r for r in result.reasons)


def test_g09_symlink_substitution_stays_red(admitted) -> None:
    gate, adm, _repo, _base = admitted
    workcell = _workcell(gate, adm)
    target = workcell.worktree / "src" / "target.py"
    target.unlink()
    target.symlink_to("/etc/passwd")
    result = gate.evaluate(adm)
    assert not result.green
    assert any("symlink" in r for r in result.reasons)


def test_forbidden_diff_literal_stays_red(admitted) -> None:
    gate, adm, _repo, _base = admitted
    workcell = _workcell(gate, adm)
    (workcell.worktree / "src" / "target.py").write_text(
        FIXED_TARGET + "\n# pytest.skip\n"
    )
    result = gate.evaluate(adm)
    assert not result.green
    assert any("forbidden diff literal" in r for r in result.reasons)


def test_g07_index_flag_abuse_stays_red(admitted) -> None:
    gate, adm, _repo, _base = admitted
    workcell = _workcell(gate, adm)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    workcell.git("update-index", "--skip-worktree", "src/target.py")
    result = gate.evaluate(adm)
    assert not result.green
    assert any("index flag anomaly" in r for r in result.reasons)


def test_verifier_env_is_scrubbed(admitted, monkeypatch) -> None:
    """The verifier receives no PYTHONPATH/secrets and the fixed PATH."""
    gate, adm, _repo, _base = admitted
    monkeypatch.setenv("PYTHONPATH", "/attacker")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-leak")
    workcell = _workcell(gate, adm)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    result = gate.evaluate(adm)
    assert result.green, result.reasons
    receipt = result.receipts[0]
    assert receipt.exit_code == 0


def test_verifier_timeout_kills_tree(admitted) -> None:
    gate, adm, _repo, _base = admitted
    command = adm.contract.acceptance.commands[0].model_copy(
        update={
            "argv": [
                adm.contract.acceptance.commands[0].argv[0],
                "-c",
                "import subprocess,sys,time; "
                "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']); "
                "time.sleep(60)",
            ],
            "timeout_seconds": 1,
        }
    )
    artifact = Path(adm.attempt_dir) / "verifiers" / "timeout-test"
    cwd = _workcell(gate, adm).worktree
    receipt = gate._run_verifier(adm, command, cwd, artifact, 0)
    assert receipt.timed_out
    assert not receipt.assertions_passed
    import subprocess as sp

    leftovers = sp.run(
        ["/usr/bin/pgrep", "-f", "time.sleep(60)"],
        capture_output=True, text=True,
    ).stdout.strip()
    assert leftovers == "", f"verifier descendants survived: {leftovers}"


def test_freeze_and_reproduce_green(admitted) -> None:
    """Requirements 5-8: freeze from admitted paths, fresh detached verify,
    COMPLETE only from the fresh result."""
    gate, adm, _repo, base = admitted
    workcell = _workcell(gate, adm)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    gate_result = gate.evaluate(adm)
    assert gate_result.green
    candidate = gate.freeze_candidate(adm, gate_result)
    assert candidate != base
    passed = gate.verify_candidate(adm, candidate)
    assert passed.candidate_sha == candidate
    assert passed.base_sha == base
    _, _, digest = gate.workspace_snapshot(workcell.worktree, base)
    reproduced = gate.promote(None, passed, adm, digest)
    assert reproduced.candidate_sha == candidate
    assert gate.prove_base_preserved(adm)


def test_candidate_not_descending_from_base_rejected(admitted) -> None:
    """G13: an ancestry violation cannot be frozen."""
    gate, adm, _repo, _base = admitted
    workcell = _workcell(gate, adm)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    gate_result = gate.evaluate(adm)
    assert gate_result.green
    # Move the private branch to an orphan root unrelated to the base.
    workcell.git("checkout", "-q", "--orphan", "orphan-root")
    from dharma_swarm.rudra.goal_gate import GoalGateError

    with pytest.raises(GoalGateError):
        gate.freeze_candidate(adm, gate_result)


def test_verifier_repo_mutation_invalidates(admitted) -> None:
    """A verifier that writes the repository cannot mint a green."""
    gate, adm, _repo, _base = admitted
    workcell = _workcell(gate, adm)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    gate_result = gate.evaluate(adm)
    assert gate_result.green
    candidate = gate.freeze_candidate(adm, gate_result)
    # Sabotage: replace verifier argv with one that passes AND writes a file.
    sabotaged = adm.contract.model_copy(deep=True)
    object.__setattr__(
        sabotaged.acceptance.commands[0],
        "argv",
        [
            adm.contract.acceptance.commands[0].argv[0],
            "-c",
            "from pathlib import Path; Path('src/evil.py').write_text('x=1'); "
            "print('RUDRA_OK')",
        ],
    )
    adm2 = adm.model_copy(update={"contract": sabotaged})
    with pytest.raises(CandidateRejected):
        gate.verify_candidate(adm2, candidate)


def test_promote_rejects_stale_workspace(admitted) -> None:
    """G02/G10: an old pass cannot promote a changed workspace."""
    gate, adm, _repo, base = admitted
    workcell = _workcell(gate, adm)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    gate_result = gate.evaluate(adm)
    candidate = gate.freeze_candidate(adm, gate_result)
    passed = gate.verify_candidate(adm, candidate)
    with pytest.raises(PromotionRejected):
        gate.promote(None, passed, adm, "0" * 64)


def test_promote_rejects_reported_mismatch(admitted) -> None:
    gate, adm, _repo, base = admitted
    workcell = _workcell(gate, adm)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    gate_result = gate.evaluate(adm)
    candidate = gate.freeze_candidate(adm, gate_result)
    passed = gate.verify_candidate(adm, candidate)
    _, _, digest = gate.workspace_snapshot(workcell.worktree, base)
    forged = ReportedCompletion(
        mission_id=adm.contract.mission_id,
        attempt_id=adm.attempt_key,
        candidate_sha="f" * 40,
    )
    with pytest.raises(PromotionRejected):
        gate.promote(forged, passed, adm, digest)


def test_forged_gate_passed_wrong_contract(admitted) -> None:
    """G03/G17: a GoalGatePassed from another contract cannot promote."""
    gate, adm, _repo, base = admitted
    workcell = _workcell(gate, adm)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    gate_result = gate.evaluate(adm)
    candidate = gate.freeze_candidate(adm, gate_result)
    passed = gate.verify_candidate(adm, candidate)
    forged = passed.model_copy(update={"contract_digest": "e" * 64})
    _, _, digest = gate.workspace_snapshot(workcell.worktree, base)
    assert isinstance(forged, GoalGatePassed)
    with pytest.raises(PromotionRejected):
        gate.promote(None, forged, adm, digest)


def test_junit_structured_assertion(tmp_path: Path) -> None:
    """Regex alone cannot prove execution; the junit artifact must show the
    required testcase passed with exact counts."""
    repo, base = make_base_repo(tmp_path)
    text = make_mission_yaml(repo, base, junit=True)
    gate = GoalGate(repo, state_dir=tmp_path / "state")
    adm = gate.admit(text)
    assert adm.baseline is not None and not adm.baseline.green
    workcell = _workcell(gate, adm)
    (workcell.worktree / "src" / "target.py").write_text(FIXED_TARGET)
    result = gate.evaluate(adm)
    assert result.green, result.reasons
    assert len(result.receipts) == 2
