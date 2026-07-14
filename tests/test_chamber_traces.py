"""chamber_gym_trace.v1 — schema freeze, digest determinism, corpus pinning."""

from __future__ import annotations

import hashlib
import json
import pickle
import sys
from dataclasses import FrozenInstanceError, replace
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import pytest

from dharma_swarm.chamber.proof import (
    RUNTIME_VERIFIER_PRINCIPAL,
    Claim,
    EvidenceArm,
    Modality,
    PromotionEvaluator,
    PromotionObligation,
    SubjectKind,
    claim_from_verification,
)
from dharma_swarm.chamber.replay import (
    FORK_PROPERTY_ID,
    ReplayValidationError,
    _SnapshotSourceLoader as ReplaySnapshotSourceLoader,
    _run_checkpoint_type,
    build_fork_alias_bundle,
    execute_world,
    read_bundle,
    run_bundle_once,
    validate_manifest,
    write_bundle,
)
from dharma_swarm.chamber.replay_worker import (
    _SnapshotSourceLoader as WorkerSnapshotSourceLoader,
    _load as load_worker_snapshot,
)
from dharma_swarm.chamber.replay_contract import REPLAY_EXECUTED_SOURCE_PATHS
from dharma_swarm.chamber.verification import (
    FreshProcessVerification,
    verification_is_attested,
    verify_in_fresh_processes,
)
import dharma_swarm.chamber.verification as verification_module
import dharma_swarm.chamber.proof as proof_module
from dharma_swarm.chamber.traces import (
    CHAMBER_GYM_TRACE_SCHEMA,
    GymTraceRow,
    SeatAnswer,
    corpus_sha256,
    read_corpus,
    render_corpus_jsonl,
    stable_digest,
    verify_row_digest,
    write_corpus,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _row(task_id: str = "t1", correct: bool = True) -> GymTraceRow:
    return GymTraceRow(
        env_id="g1_git_history",
        task_id=task_id,
        taskpack_sha="a" * 64,
        scorer_hash="b" * 64,
        seed=7,
        answers=(
            SeatAnswer(seat_id="s1", answer="diff-1", model="m1", provider="p1",
                       correct=True),
            SeatAnswer(seat_id="s2", answer="diff-2", model="m2", provider="p2",
                       correct=False),
        ),
        aggregated_answer="diff-1",
        correct=correct,
    )


def test_schema_is_frozen():
    assert CHAMBER_GYM_TRACE_SCHEMA == "chamber_gym_trace.v1"
    assert _row().to_dict()["schema"] == "chamber_gym_trace.v1"


def test_digest_is_deterministic_and_verifiable():
    d1, d2 = _row().to_dict(), _row().to_dict()
    assert d1["digest"] == d2["digest"]
    assert verify_row_digest(d1)
    d1["correct"] = False  # tamper
    assert not verify_row_digest(d1)


def test_corpus_bytes_and_sha_are_deterministic():
    rows = [_row("t1").to_dict(), _row("t2", correct=False).to_dict()]
    assert render_corpus_jsonl(rows) == render_corpus_jsonl(
        [_row("t1").to_dict(), _row("t2", correct=False).to_dict()]
    )
    assert len(corpus_sha256(rows)) == 64


def test_write_corpus_pins_sha_and_read_roundtrips(tmp_path):
    rows = [_row("t1").to_dict(), _row("t2").to_dict()]
    path = tmp_path / "corpus.jsonl"
    sha = write_corpus(rows, path)
    assert sha == corpus_sha256(rows)
    assert read_corpus(path) == rows


def test_write_corpus_refuses_undigested_rows(tmp_path):
    bad = _row().to_dict()
    bad.pop("digest")
    with pytest.raises(ValueError, match="digest"):
        write_corpus([bad], tmp_path / "c.jsonl")


def test_read_corpus_refuses_tampered_rows(tmp_path):
    rows = [_row().to_dict()]
    path = tmp_path / "corpus.jsonl"
    write_corpus(rows, path)
    text = path.read_text(encoding="utf-8").replace('"correct": true',
                                                    '"correct": false')
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        read_corpus(path)


def _replay_bundle_path(tmp_path: Path) -> Path:
    path = tmp_path / "fork-alias-replay-bundle.json"
    write_bundle(build_fork_alias_bundle(REPO_ROOT), path)
    return path


@pytest.fixture(scope="module")
def verified_report(tmp_path_factory) -> FreshProcessVerification:
    path = tmp_path_factory.mktemp("proof-membrane") / "bundle.json"
    write_bundle(build_fork_alias_bundle(REPO_ROOT), path)
    return verify_in_fresh_processes(path, repo_root=REPO_ROOT, replays=3)


def _claim(
    report: FreshProcessVerification,
    *,
    use_control: bool = True,
) -> Claim:
    return claim_from_verification(
        report,
        FORK_PROPERTY_ID,
        use_control=use_control,
    )


def _obligation(
    report: FreshProcessVerification,
    *,
    candidate_id: str | None = None,
    evidence_arm: EvidenceArm = EvidenceArm.CONTROL,
    proposition_id: str = FORK_PROPERTY_ID,
    effect_binding_id: str = "record-fixture-promotion.v1",
) -> PromotionObligation:
    if candidate_id is None:
        candidate_id = (
            report.control_candidate_id
            if evidence_arm is EvidenceArm.CONTROL
            else report.scenario_candidate_id
        )
    return PromotionObligation(
        candidate_id=candidate_id,
        evidence_arm=evidence_arm,
        proposition_id=proposition_id,
        source_revision=report.source_revision,
        bundle_digest=report.bundle_digest,
        scope_digest=report.scope_digest,
        required_properties=(proposition_id,),
        effect_binding_id=effect_binding_id,
    )


def _evaluator(
    obligation: PromotionObligation,
    invocations: list[str],
) -> PromotionEvaluator:
    return PromotionEvaluator(
        authorized_obligations=(obligation,),
        effect_handlers={
            (obligation.candidate_id, obligation.effect_binding_id): lambda: invocations.append(
                obligation.candidate_id
            )
        },
        allow_worktree_for_tests=True,
    )


def test_fork_alias_bundle_uses_real_defect_and_discriminating_control():
    bundle = build_fork_alias_bundle(REPO_ROOT)
    specimen = execute_world(bundle.world)
    control = execute_world(bundle.control_world)

    assert specimen.parent_values == ("parent-only", "child-only")
    assert specimen.nested_object_aliased is True
    assert specimen.property_verdicts[FORK_PROPERTY_ID] is False
    assert control.parent_values == ("parent-only",)
    assert control.nested_object_aliased is False
    assert control.property_verdicts[FORK_PROPERTY_ID] is True

    replay = run_bundle_once(bundle, REPO_ROOT)
    assert replay["control_valid"] is True
    assert replay["scenario_candidate_id"] == bundle.scenario_candidate_id
    assert replay["control_candidate_id"] == bundle.control_candidate_id
    assert replay["property_verdicts"] == {FORK_PROPERTY_ID: False}
    assert replay["control_property_verdicts"] == {FORK_PROPERTY_ID: True}


@pytest.mark.parametrize(
    "loader_type",
    (ReplaySnapshotSourceLoader, WorkerSnapshotSourceLoader),
)
def test_snapshot_loader_executes_captured_bytes_without_path_reread(
    tmp_path,
    loader_type,
):
    source_path = (tmp_path / "captured.py").resolve()
    source_path.write_text("VALUE = 'before-capture'\n", encoding="utf-8")
    captured = b"VALUE = 'captured-snapshot'\n"
    module_name = f"_chamber_snapshot_{loader_type.__module__.replace('.', '_')}"
    loader = loader_type(module_name, captured, source_path)
    spec = spec_from_loader(module_name, loader)
    assert spec is not None
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    source_path.write_text("VALUE = 'changed-on-disk'\n", encoding="utf-8")
    try:
        loader.exec_module(module)
        assert module.VALUE == "captured-snapshot"
        assert module.__file__ == str(source_path)
        assert module.__package__ == ""
        assert module.__spec__ is spec
        with pytest.raises(OSError, match="refuses undeclared path"):
            loader.get_data(str(tmp_path / "undeclared.py"))
        with pytest.raises(OSError, match="disables bytecode caching"):
            loader.path_stats(str(source_path))
    finally:
        sys.modules.pop(module_name, None)


def test_failed_snapshot_loads_do_not_poison_module_registry(tmp_path):
    source_path = (tmp_path / "failure.py").resolve()
    source_path.write_text("raise SystemExit(7)\n", encoding="utf-8")
    worker_name = "_chamber_worker_snapshot_failure"
    with pytest.raises(SystemExit):
        load_worker_snapshot(worker_name, source_path, {}, tmp_path)
    assert worker_name not in sys.modules

    captured = source_path.read_bytes()
    digest = hashlib.sha256(captured).hexdigest()
    replay_name = f"_dharma_chamber_graph_types_{digest}"
    with pytest.raises(SystemExit):
        _run_checkpoint_type(captured, source_path)
    assert replay_name not in sys.modules


def test_bundle_tamper_and_recomputed_manifest_drift_both_fail_closed(tmp_path):
    path = _replay_bundle_path(tmp_path)
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["world"]["fixtures"]["child_run_id"] = "changed"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ReplayValidationError, match="digest mismatch"):
        read_bundle(path)

    payload = build_fork_alias_bundle(REPO_ROOT).to_dict()
    payload["manifest"][0]["sha256"] = "0" * 64
    body = {key: value for key, value in payload.items() if key != "bundle_digest"}
    payload["bundle_digest"] = stable_digest(body)
    drift_path = tmp_path / "recomputed-drift.json"
    drift_path.write_text(json.dumps(payload), encoding="utf-8")
    drifted = read_bundle(drift_path)
    with pytest.raises(ReplayValidationError, match="manifest scope drift"):
        validate_manifest(drifted, REPO_ROOT)


def test_direct_bundle_instances_cannot_bypass_registered_contract():
    bundle = build_fork_alias_bundle(REPO_ROOT)
    with pytest.raises(ReplayValidationError, match="bundle schema"):
        run_bundle_once(replace(bundle, schema="unregistered.schema"), REPO_ROOT)
    with pytest.raises(ReplayValidationError, match="bundle id"):
        run_bundle_once(replace(bundle, bundle_id="unregistered.bundle"), REPO_ROOT)
    bad_expectation = replace(
        bundle.expectation,
        property_id="unregistered.property",
        scenario_verdict=0,
        control_verdict=1,
    )
    with pytest.raises(ReplayValidationError, match="expectation proposition"):
        run_bundle_once(replace(bundle, expectation=bad_expectation), REPO_ROOT)
    with pytest.raises(ReplayValidationError, match="invalid field types"):
        run_bundle_once(replace(bundle, manifest=list(bundle.manifest)), REPO_ROOT)


def test_unknown_property_and_declared_nondeterminism_are_rejected():
    bundle = build_fork_alias_bundle(REPO_ROOT)
    unknown_property = replace(
        bundle.world,
        activated_properties=("unknown.property.v1",),
    )
    with pytest.raises(ReplayValidationError, match="activated property"):
        execute_world(unknown_property)

    nondeterministic = replace(
        bundle.world,
        declared_nondeterminism=("host_scheduler",),
    )
    with pytest.raises(ReplayValidationError, match="nondeterminism"):
        execute_world(nondeterministic)

    changed_fixture = replace(
        bundle.world,
        fixtures={**bundle.world.fixtures, "child_run_id": "other-child"},
    )
    with pytest.raises(ReplayValidationError, match="fixture values"):
        execute_world(changed_fixture)

    bool_is_not_registered_integer = replace(
        bundle.world,
        fixtures={
            **bundle.world.fixtures,
            "checkpoint": {**bundle.world.fixtures["checkpoint"], "superstep": True},
        },
    )
    with pytest.raises(ReplayValidationError, match="fixture values"):
        execute_world(bool_is_not_registered_integer)
    with pytest.raises(ReplayValidationError, match="invalid field types"):
        execute_world(replace(bundle.world, declared_nondeterminism=[]))


def test_fork_alias_reproduces_in_100_fresh_processes(tmp_path):
    bundle_path = _replay_bundle_path(tmp_path)
    bundle = read_bundle(bundle_path)
    report = verify_in_fresh_processes(
        bundle_path,
        repo_root=REPO_ROOT,
        replays=100,
    )

    assert report.verified is True
    assert report.replays_completed == 100
    assert len(report.replay_pids) == 100
    assert len(set(report.replay_pids)) == 100
    assert report.property_verdicts == {FORK_PROPERTY_ID: False}
    assert report.control_property_verdicts == {FORK_PROPERTY_ID: True}
    assert report.control_valid is True
    assert len(report.process_records) == 100
    assert [record["replay_index"] for record in report.process_records] == list(
        range(1, 101)
    )
    assert all(record["exit_code"] == 0 for record in report.process_records)
    assert report.replay_payload["property_verdicts"] == {FORK_PROPERTY_ID: False}
    assert report.replay_payload["control_property_verdicts"] == {
        FORK_PROPERTY_ID: True
    }
    assert report.process_environment_contract["python_hash_seed"] == "0"
    assert report.process_environment_contract["isolated_worker"] is True
    executed_digests = {
        entry.path: entry.sha256
        for entry in bundle.manifest
        if entry.path in REPLAY_EXECUTED_SOURCE_PATHS
    }
    assert report.process_environment_contract["loaded_project_source_digests"] == (
        executed_digests
    )
    assert len(report.process_environment_contract["git_sha256"]) == 64
    assert report.process_environment_contract["path"]
    assert len({record["home"] for record in report.process_records}) == 100


def test_verification_receipt_is_deeply_immutable(verified_report):
    exported = verified_report.to_dict()
    exported["process_environment_contract"]["path"] = "tampered"

    assert verified_report.to_dict() != exported
    assert verification_is_attested(verified_report) is True
    with pytest.raises(TypeError):
        verified_report.process_environment_contract["path"] = "x"


def test_bundle_path_swap_cannot_change_child_input(tmp_path, monkeypatch):
    path = _replay_bundle_path(tmp_path)
    original_run = verification_module.subprocess.run
    swapped = False

    def swap_then_run(*args, **kwargs):
        nonlocal swapped
        if kwargs.get("input") is not None and not swapped:
            path.write_text("{}", encoding="utf-8")
            swapped = True
        return original_run(*args, **kwargs)

    monkeypatch.setattr(verification_module.subprocess, "run", swap_then_run)
    report = verify_in_fresh_processes(path, repo_root=REPO_ROOT, replays=2)

    assert swapped is True
    assert report.verified is True
    assert report.bundle_digest == report.scope_digest


def test_fabricated_verification_cannot_mint_runtime_claim(verified_report):
    fabricated = FreshProcessVerification(
        bundle_id=verified_report.bundle_id,
        scenario_candidate_id=verified_report.scenario_candidate_id,
        control_candidate_id=verified_report.control_candidate_id,
        bundle_digest=verified_report.bundle_digest,
        source_revision=verified_report.source_revision,
        scope_digest=verified_report.scope_digest,
        replays_requested=verified_report.replays_requested,
        replays_completed=verified_report.replays_completed,
        replay_pids=verified_report.replay_pids,
        semantic_digest=verified_report.semantic_digest,
        property_verdicts=verified_report.property_verdicts,
        control_property_verdicts=verified_report.control_property_verdicts,
        control_valid=verified_report.control_valid,
        replay_payload=verified_report.replay_payload,
        process_environment_contract=verified_report.process_environment_contract,
        command=verified_report.command,
        process_records=verified_report.process_records,
        python_executable=verified_report.python_executable,
        python_version=verified_report.python_version,
        schema=verified_report.schema,
    )

    assert fabricated.verified is True
    assert verification_is_attested(fabricated) is False
    with pytest.raises(ValueError, match="lacks a live RuntimeVerifier witness"):
        claim_from_verification(
            fabricated,
            FORK_PROPERTY_ID,
            use_control=True,
        )


def test_reproduced_violation_cannot_authorize_promotion(verified_report):
    claim = _claim(verified_report, use_control=False)
    obligation = _obligation(
        verified_report,
        evidence_arm=EvidenceArm.SCENARIO,
    )
    invocations: list[str] = []
    evaluator = _evaluator(obligation, invocations)
    capability = evaluator.mint_authorization(obligation)

    decision = evaluator.promote(claim, obligation, capability)

    assert claim.subject is SubjectKind.REFUTES
    assert decision.code == "EPI-SUBJECT-REFUTES"
    assert invocations == []


def test_parity_score_cannot_discharge_production_ready(verified_report):
    control_claim = _claim(verified_report)
    claim = replace(control_claim, proposition_id="ParityScore(52)")
    obligation = _obligation(verified_report, proposition_id="ProductionReady")
    invocations: list[str] = []
    evaluator = _evaluator(obligation, invocations)
    capability = evaluator.mint_authorization(obligation)

    decision = evaluator.promote(claim, obligation, capability)

    assert decision.code == "EPI-PROP-MISMATCH"
    assert invocations == []


def test_control_evidence_cannot_be_relabeled_as_a_production_candidate(verified_report):
    claim = _claim(verified_report)
    assert claim.candidate_id == verified_report.control_candidate_id
    assert claim.evidence_arm is EvidenceArm.CONTROL

    relabeled = replace(
        claim,
        candidate_id=verified_report.scenario_candidate_id,
        evidence_arm=EvidenceArm.SCENARIO,
    )
    obligation = _obligation(verified_report, evidence_arm=EvidenceArm.SCENARIO)
    evaluator = _evaluator(obligation, [])
    capability = evaluator.mint_authorization(obligation)

    assert evaluator.promote(relabeled, obligation, capability).code == (
        "EPI-EVIDENCE-UNATTESTED"
    )


def test_direct_claim_and_authority_shapes_create_neither_provenance_nor_permission(
    verified_report,
):
    claim = _claim(verified_report)
    obligation = _obligation(verified_report)
    invocations: list[str] = []
    evaluator = _evaluator(obligation, invocations)
    capability = evaluator.mint_authorization(obligation)
    fabricated_claim = Claim(
        candidate_id=claim.candidate_id,
        evidence_arm=claim.evidence_arm,
        proposition_id=claim.proposition_id,
        subject=claim.subject,
        modality=claim.modality,
        principal_id=claim.principal_id,
        source_revision=claim.source_revision,
        bundle_digest=claim.bundle_digest,
        scope_digest=claim.scope_digest,
        property_verdicts=claim.property_verdicts,
        evidence_digest=claim.evidence_digest,
        fresh_process_count=claim.fresh_process_count,
        control_valid=claim.control_valid,
    )

    fabricated_decision = evaluator.promote(
        fabricated_claim,
        obligation,
        capability,
    )

    assert fabricated_decision.code == "EPI-EVIDENCE-UNATTESTED"
    assert invocations == []

    forged_payload = {
        "authority": RUNTIME_VERIFIER_PRINCIPAL,
        "candidate_id": obligation.candidate_id,
        "proposition_id": obligation.proposition_id,
        "scope_digest": obligation.scope_digest,
        "effect": "Promote",
    }

    decision = evaluator.promote(claim, obligation, forged_payload)

    assert decision.code == "EPI-AUTHORITY-MISSING"
    assert invocations == []
    direct_private_shape = proof_module._OperationalAuthorization(
        object(),
        ("forged",),
        object(),
    )
    assert evaluator.promote(claim, obligation, direct_private_shape).code == (
        "EPI-AUTHORITY-UNISSUED"
    )
    assert invocations == []
    with pytest.raises(TypeError, match="not serializable"):
        pickle.dumps(capability)


def test_exact_matching_capability_runs_only_registered_effect_once(verified_report):
    claim = _claim(verified_report)
    obligation = _obligation(verified_report)
    invocations: list[str] = []
    evaluator = _evaluator(obligation, invocations)
    capability = evaluator.mint_authorization(obligation)

    allowed = evaluator.promote(claim, obligation, capability)
    replayed = evaluator.promote(claim, obligation, capability)
    with pytest.raises(PermissionError, match="already minted"):
        evaluator.mint_authorization(obligation)

    assert allowed.allowed is True
    assert allowed.code == "ALLOW"
    assert replayed.code == "EPI-AUTHORITY-UNISSUED"
    assert invocations == [obligation.candidate_id]


def test_capability_is_immutable_and_evaluator_instance_bound(verified_report):
    claim = _claim(verified_report)
    obligation = _obligation(verified_report)
    invocations: list[str] = []
    source = _evaluator(obligation, invocations)
    other = _evaluator(obligation, invocations)
    capability = source.mint_authorization(obligation)

    with pytest.raises((FrozenInstanceError, AttributeError)):
        capability.obligation_key = ("retargeted",)
    assert other.evaluate(claim, obligation, capability).code == (
        "EPI-AUTHORITY-UNISSUED"
    )
    object.__setattr__(capability, "obligation_key", ("retargeted",))
    assert source.evaluate(claim, obligation, capability).code == (
        "EPI-AUTHORITY-MISMATCH"
    )


def test_evidence_cannot_authorize_a_new_obligation(verified_report):
    authorized = _obligation(verified_report)
    unauthorized = replace(authorized, candidate_id="other-candidate")
    evaluator = _evaluator(authorized, [])

    with pytest.raises(PermissionError, match="not evaluator-authorized"):
        evaluator.mint_authorization(unauthorized)
    with pytest.raises(PermissionError, match="not evaluator-authorized"):
        evaluator.mint_authorization(
            replace(authorized, effect_binding_id="other-effect-binding.v1")
        )


def test_promotion_obligation_refuses_a_different_effect(verified_report):
    with pytest.raises(ValueError, match="effect must be"):
        replace(_obligation(verified_report), effect="Delete")


@pytest.mark.parametrize(
    ("claim_overrides", "expected_code"),
    [
        ({"candidate_id": "other"}, "EPI-CANDIDATE-MISMATCH"),
        ({"evidence_arm": EvidenceArm.SCENARIO}, "EPI-ARM-MISMATCH"),
        ({"source_revision": "f" * 40}, "EPI-REVISION-MISMATCH"),
        ({"bundle_digest": "b" * 64}, "EPI-BUNDLE-MISMATCH"),
        ({"scope_digest": "d" * 64}, "EPI-SCOPE-MISMATCH"),
        ({"property_verdicts": (("other", True),)}, "EPI-PROPERTIES-MISSING"),
        ({"property_verdicts": ((FORK_PROPERTY_ID, False),)}, "EPI-PROPERTIES-FAILED"),
        ({"control_valid": False}, "EPI-CONTROL-INVALID"),
        ({"fresh_process_count": 0}, "EPI-FRESH-PROCESS-MISSING"),
        ({"modality": Modality.OBSERVED}, "EPI-MODALITY-MISMATCH"),
        ({"_witness": None}, "EPI-EVIDENCE-UNATTESTED"),
    ],
)
def test_gate_refuses_each_semantic_coercion(
    verified_report,
    claim_overrides,
    expected_code,
):
    claim = replace(_claim(verified_report), **claim_overrides)
    obligation = _obligation(verified_report)
    evaluator = _evaluator(obligation, [])
    capability = evaluator.mint_authorization(obligation)

    decision = evaluator.evaluate(claim, obligation, capability)

    assert decision.code == expected_code
