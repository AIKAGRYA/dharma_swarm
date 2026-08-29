from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from dharma_swarm.foundry.evaluator import Candidate, candidate_digest
from dharma_swarm.governed_patch_evidence import (
    GOVERNED_PATCH_REQUEST_SCHEMA,
    GOVERNED_PATCH_REQUEST_V2_SCHEMA,
    MAX_SOURCE_BYTES,
    MAX_VERIFIER_EVIDENCE_BYTES,
    GovernedPatchEvidenceError,
    NativePatchBindings,
    NoEffectOutcome,
    build_candidate_bundle,
    build_governed_patch_request_v2_content,
    canonical_semantic_intent_sha256,
    governed_patch_task_snapshot_sha256,
    load_candidate_bundle,
    parse_governed_patch_request,
    record_no_effect_result,
    verify_candidate_bundle,
    verify_no_effect_bundle,
)

BASE_SHA = "a" * 40
DELIVERY_ID = "d" * 24
SOURCE_PATH = "pkg/example.py"
SOURCE = 'def value():\n    return "old"\n'
DIFF = """--- a/pkg/example.py
+++ b/pkg/example.py
@@ -1,2 +1,2 @@
 def value():
-    return "old"
+    return "new"
"""
SEMANTIC_INTENT = "Change value() to return the new marker."
SEMANTIC_ARTIFACT_SHA = "f" * 64


def _bindings(**overrides: str) -> NativePatchBindings:
    values = {
        "mission_id": "mission-1",
        "task_id": "task-1",
        "attempt_id": "packet-1",
        "lease_id": DELIVERY_ID,
        "packet_id": "packet-1",
        "correlation_id": "a2a_send:codex_composer:packet-1",
        "delivery_id": DELIVERY_ID,
        "proposal_id": "proposal-1",
        "base_sha": BASE_SHA,
        "executor_agent_uid": "codex_composer",
        "executor_run_id": "executor-run-1",
        "executor_process_boot_id": "boot-1",
    }
    values.update(overrides)
    return NativePatchBindings(**values)


def _payload(bindings: NativePatchBindings, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": GOVERNED_PATCH_REQUEST_SCHEMA,
        **bindings.to_dict(),
        "authorized_source_path": SOURCE_PATH,
        "oracle_argv": ["python3", "-m", "pytest", "tests/test_example.py", "-q"],
    }
    payload.update(overrides)
    return payload


def _content(bindings: NativePatchBindings, **overrides: object) -> str:
    return json.dumps(
        _payload(bindings, **overrides), sort_keys=True, separators=(",", ":")
    )


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / SOURCE_PATH).write_text(SOURCE, encoding="utf-8", newline="")
    return repo, tmp_path / "evidence"


def _request(repo: Path, bindings: NativePatchBindings):
    content = _content(bindings)
    return parse_governed_patch_request(
        content,
        repo_root=repo,
        expected=bindings,
        accepted_base_sha=BASE_SHA,
        expected_content_sha256=hashlib.sha256(content.encode()).hexdigest(),
    )


def _task_snapshot(bindings: NativePatchBindings) -> str:
    return governed_patch_task_snapshot_sha256(
        mission_id=bindings.mission_id,
        task_id=bindings.task_id,
        title="Make the bounded change",
        description="Change only the authorized source file.",
        mission_task_creation_hash="e" * 64,
        completion_contract="governed_patch_effect_v1",
        status="pending",
        assigned_to=None,
        result=None,
    )


def _request_v2(repo: Path, bindings: NativePatchBindings):
    task_snapshot = _task_snapshot(bindings)
    content = build_governed_patch_request_v2_content(
        bindings,
        authorized_source_path=SOURCE_PATH,
        oracle_argv=["python3", "-m", "pytest", "tests/test_example.py", "-q"],
        semantic_intent=SEMANTIC_INTENT,
        task_snapshot_sha256=task_snapshot,
    )
    return parse_governed_patch_request(
        content,
        repo_root=repo,
        expected=bindings,
        accepted_base_sha=BASE_SHA,
        expected_content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        expected_semantic_intent=SEMANTIC_INTENT,
        expected_task_snapshot_sha256=task_snapshot,
    )


def _candidate(roots: tuple[Path, Path]):
    repo, evidence = roots
    bindings = _bindings()
    return build_candidate_bundle(
        _request(repo, bindings),
        DIFF,
        bundle_root=evidence,
    )


def _bound_evidence(candidate, payload: dict[str, object]) -> dict[str, object]:
    return {
        "candidate_digest": candidate.candidate_digest,
        "diff_sha256": candidate.diff_sha256,
        **payload,
    }


def test_candidate_bundle_is_exact_immutable_and_restart_loadable(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    bindings = _bindings()
    request = _request(repo, bindings)
    before = (repo / SOURCE_PATH).read_bytes()
    first = build_candidate_bundle(request, DIFF, bundle_root=evidence)
    second = build_candidate_bundle(request, DIFF, bundle_root=evidence)

    assert first == second
    assert first.manifest_path.is_file()
    assert first.diff_path.read_bytes() == DIFF.encode()
    assert first.diff_bytes == DIFF.encode()
    assert first.source_bytes == before
    assert first.source_snapshot_path.read_bytes() == before
    assert (repo / SOURCE_PATH).read_bytes() == before
    assert first.diff_sha256 == hashlib.sha256(DIFF.encode()).hexdigest()
    candidate_payload = json.loads(first.candidate_path.read_text(encoding="utf-8"))
    assert first.candidate_digest == candidate_digest(Candidate(**candidate_payload))
    assert candidate_payload["metadata"]["executor_run_id"] == "executor-run-1"
    assert candidate_payload["metadata"]["executor_process_boot_id"] == "boot-1"
    assert candidate_payload["metadata"]["repository_effect_authorized"] is False
    assert candidate_payload["metadata"]["repository_effect_performed"] is False
    assert candidate_payload["metadata"]["evidence_storage_effects_performed"] is True
    loaded = load_candidate_bundle(
        evidence,
        first.bundle_sha256,
        repo_root=repo,
        expected=bindings,
        accepted_base_sha=BASE_SHA,
    )
    assert loaded == first


def test_v2_request_and_candidate_bind_reconstructible_semantic_chain(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    bindings = _bindings()
    request = _request_v2(repo, bindings)

    assert request.schema_version == GOVERNED_PATCH_REQUEST_V2_SCHEMA
    assert request.semantic_intent == SEMANTIC_INTENT
    assert request.semantic_intent_sha256 == canonical_semantic_intent_sha256(
        SEMANTIC_INTENT
    )
    assert request.task_snapshot_sha256 == _task_snapshot(bindings)

    candidate = build_candidate_bundle(
        request,
        DIFF,
        bundle_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
    )
    manifest = json.loads(candidate.manifest_path.read_text(encoding="utf-8"))
    candidate_payload = json.loads(
        candidate.candidate_path.read_text(encoding="utf-8")
    )
    for payload in (manifest, candidate_payload["metadata"]):
        assert payload["semantic_intent_sha256"] == request.semantic_intent_sha256
        assert payload["task_snapshot_sha256"] == request.task_snapshot_sha256
        assert payload["semantic_artifact_sha256"] == SEMANTIC_ARTIFACT_SHA
    loaded = load_candidate_bundle(
        evidence,
        candidate.bundle_sha256,
        repo_root=repo,
        expected=bindings,
        accepted_base_sha=BASE_SHA,
    )
    assert loaded == candidate


def test_v2_constructor_is_local_canonical_and_parser_requires_expected_bindings(
    roots: tuple[Path, Path],
) -> None:
    repo, _ = roots
    bindings = _bindings()
    snapshot = _task_snapshot(bindings)
    content = build_governed_patch_request_v2_content(
        bindings,
        authorized_source_path=SOURCE_PATH,
        oracle_argv=["python3", "-m", "pytest"],
        semantic_intent=SEMANTIC_INTENT,
        task_snapshot_sha256=snapshot,
    )
    assert content == json.dumps(
        json.loads(content), sort_keys=True, separators=(",", ":")
    )
    with pytest.raises(GovernedPatchEvidenceError, match="requires expected"):
        parse_governed_patch_request(
            content,
            repo_root=repo,
            expected=bindings,
            accepted_base_sha=BASE_SHA,
        )
    with pytest.raises(GovernedPatchEvidenceError, match="intent binding"):
        parse_governed_patch_request(
            content,
            repo_root=repo,
            expected=bindings,
            accepted_base_sha=BASE_SHA,
            expected_semantic_intent="Different intent",
            expected_task_snapshot_sha256=snapshot,
        )
    with pytest.raises(GovernedPatchEvidenceError, match="snapshot binding"):
        parse_governed_patch_request(
            content,
            repo_root=repo,
            expected=bindings,
            accepted_base_sha=BASE_SHA,
            expected_semantic_intent=SEMANTIC_INTENT,
            expected_task_snapshot_sha256="0" * 64,
        )


def test_task_snapshot_digest_is_closed_reconstructible_and_sensitive() -> None:
    bindings = _bindings()
    first = _task_snapshot(bindings)
    second = _task_snapshot(bindings)
    changed = governed_patch_task_snapshot_sha256(
        mission_id=bindings.mission_id,
        task_id=bindings.task_id,
        title="Make the bounded change",
        description="A changed canonical description.",
        mission_task_creation_hash="e" * 64,
        completion_contract="governed_patch_effect_v1",
        status="pending",
        assigned_to=None,
        result=None,
    )

    assert first == second
    assert first != changed
    assert len(first) == 64
    with pytest.raises(GovernedPatchEvidenceError, match="creation_hash"):
        governed_patch_task_snapshot_sha256(
            mission_id=bindings.mission_id,
            task_id=bindings.task_id,
            title="title",
            description="description",
            mission_task_creation_hash="opaque",
            completion_contract="governed_patch_effect_v1",
            status="pending",
            assigned_to=None,
            result=None,
        )

    for authority_override in (
        {"status": "running", "assigned_to": None, "result": None},
        {"status": "pending", "assigned_to": "codex_composer", "result": None},
        {"status": "pending", "assigned_to": None, "result": "already done"},
    ):
        with pytest.raises(GovernedPatchEvidenceError, match="authority"):
            governed_patch_task_snapshot_sha256(
                mission_id=bindings.mission_id,
                task_id=bindings.task_id,
                title="title",
                description="description",
                mission_task_creation_hash="e" * 64,
                completion_contract="governed_patch_effect_v1",
                **authority_override,
            )


def test_v1_request_cannot_be_reinterpreted_as_intent_bound(
    roots: tuple[Path, Path],
) -> None:
    repo, _ = roots
    bindings = _bindings()
    with pytest.raises(GovernedPatchEvidenceError, match="v1.*cannot bind"):
        parse_governed_patch_request(
            _content(bindings),
            repo_root=repo,
            expected=bindings,
            accepted_base_sha=BASE_SHA,
            expected_semantic_intent=SEMANTIC_INTENT,
            expected_task_snapshot_sha256=_task_snapshot(bindings),
        )


def test_verified_candidate_snapshots_survive_later_path_swap_but_reload_refuses(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    bindings = _bindings()
    candidate = _candidate(roots)
    loaded = load_candidate_bundle(
        evidence,
        candidate.bundle_sha256,
        repo_root=repo,
        expected=bindings,
        accepted_base_sha=BASE_SHA,
    )
    original_diff = loaded.diff_bytes
    original_candidate = loaded.candidate_bytes

    loaded.diff_path.write_text("swapped after verified load", encoding="utf-8")
    loaded.candidate_path.write_text("{}", encoding="utf-8")

    assert loaded.diff_bytes == original_diff
    assert loaded.candidate_bytes == original_candidate
    with pytest.raises(GovernedPatchEvidenceError, match="tampered"):
        verify_candidate_bundle(loaded)


@pytest.mark.parametrize(
    "changed",
    [
        {"authorized_source_path": "../escape.py"},
        {"oracle_argv": ("bash", "-c", "true")},
    ],
)
def test_candidate_reload_revalidates_path_and_oracle_semantics(
    roots: tuple[Path, Path],
    changed: dict[str, object],
) -> None:
    candidate = _candidate(roots)

    with pytest.raises(GovernedPatchEvidenceError):
        verify_candidate_bundle(replace(candidate, **changed))


@pytest.mark.parametrize(
    "field", ["mission_id", "task_id", "proposal_id", "executor_run_id"]
)
def test_request_rejects_native_binding_mismatch(
    roots: tuple[Path, Path],
    field: str,
) -> None:
    repo, _ = roots
    expected = _bindings()
    observed = _bindings(**{field: f"different-{field}"})
    with pytest.raises(GovernedPatchEvidenceError, match="bindings do not match"):
        parse_governed_patch_request(
            _content(observed),
            repo_root=repo,
            expected=expected,
            accepted_base_sha=BASE_SHA,
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"attempt_id": "other"}, "attempt_id must equal packet_id"),
        ({"lease_id": "e" * 24}, "lease_id must equal delivery_id"),
        ({"correlation_id": "a2a_send:other:packet-1"}, "correlation_id"),
    ],
)
def test_request_rejects_broken_native_relations(
    roots: tuple[Path, Path],
    overrides: dict[str, str],
    message: str,
) -> None:
    repo, _ = roots
    malformed = _bindings(**overrides)
    with pytest.raises(GovernedPatchEvidenceError, match=message):
        parse_governed_patch_request(
            _content(malformed),
            repo_root=repo,
            expected=malformed,
            accepted_base_sha=BASE_SHA,
        )


def test_request_rejects_base_and_content_hash_mismatch(
    roots: tuple[Path, Path],
) -> None:
    repo, _ = roots
    bindings = _bindings()
    content = _content(bindings)
    with pytest.raises(GovernedPatchEvidenceError, match="accepted base"):
        parse_governed_patch_request(
            content,
            repo_root=repo,
            expected=bindings,
            accepted_base_sha="b" * 40,
        )
    with pytest.raises(GovernedPatchEvidenceError, match="content sha256"):
        parse_governed_patch_request(
            content,
            repo_root=repo,
            expected=bindings,
            accepted_base_sha=BASE_SHA,
            expected_content_sha256="0" * 64,
        )


def test_request_json_is_closed_duplicate_free_and_finite(
    roots: tuple[Path, Path],
) -> None:
    repo, _ = roots
    bindings = _bindings()
    extra = _payload(bindings)
    extra["surprise"] = True
    with pytest.raises(GovernedPatchEvidenceError, match="non-closed shape"):
        parse_governed_patch_request(
            json.dumps(extra),
            repo_root=repo,
            expected=bindings,
            accepted_base_sha=BASE_SHA,
        )
    duplicate = _content(bindings).replace(
        '"mission_id":"mission-1"',
        '"mission_id":"mission-1","mission_id":"shadow"',
    )
    with pytest.raises(GovernedPatchEvidenceError, match="duplicate JSON key"):
        parse_governed_patch_request(
            duplicate,
            repo_root=repo,
            expected=bindings,
            accepted_base_sha=BASE_SHA,
        )
    nonfinite = _content(bindings).replace('"oracle_argv":[', '"oracle_argv":[NaN,')
    with pytest.raises(GovernedPatchEvidenceError, match="non-finite"):
        parse_governed_patch_request(
            nonfinite,
            repo_root=repo,
            expected=bindings,
            accepted_base_sha=BASE_SHA,
        )


@pytest.mark.parametrize(
    "oracle",
    ["python -m pytest", [], ["bash", "-c", "pytest"], ["python3", "bad\narg"]],
)
def test_request_rejects_non_argv_or_shell_oracle(
    roots: tuple[Path, Path],
    oracle: object,
) -> None:
    repo, _ = roots
    bindings = _bindings()
    with pytest.raises(GovernedPatchEvidenceError, match="oracle_argv"):
        parse_governed_patch_request(
            _content(bindings, oracle_argv=oracle),
            repo_root=repo,
            expected=bindings,
            accepted_base_sha=BASE_SHA,
        )


@pytest.mark.parametrize(
    "path",
    [
        "../escape.py",
        "/tmp/escape.py",
        "missing.py",
        "pkg/space name.py",
        "pkg/back`tick.py",
        "pkg/tab\tname.py",
    ],
)
def test_request_rejects_unsafe_or_missing_source(
    roots: tuple[Path, Path],
    path: str,
) -> None:
    repo, _ = roots
    bindings = _bindings()
    with pytest.raises(GovernedPatchEvidenceError):
        parse_governed_patch_request(
            _content(bindings, authorized_source_path=path),
            repo_root=repo,
            expected=bindings,
            accepted_base_sha=BASE_SHA,
        )


def test_request_rejects_symlink_and_non_utf8_source(
    roots: tuple[Path, Path],
) -> None:
    repo, _ = roots
    bindings = _bindings()
    (repo / "pkg" / "link.py").symlink_to(repo / SOURCE_PATH)
    with pytest.raises(GovernedPatchEvidenceError, match="symlink"):
        parse_governed_patch_request(
            _content(bindings, authorized_source_path="pkg/link.py"),
            repo_root=repo,
            expected=bindings,
            accepted_base_sha=BASE_SHA,
        )
    (repo / "pkg" / "binary.py").write_bytes(b"\xff\xfe")
    with pytest.raises(GovernedPatchEvidenceError, match="strict UTF-8"):
        parse_governed_patch_request(
            _content(bindings, authorized_source_path="pkg/binary.py"),
            repo_root=repo,
            expected=bindings,
            accepted_base_sha=BASE_SHA,
        )


def test_request_rejects_oversized_source(roots: tuple[Path, Path]) -> None:
    repo, _ = roots
    bindings = _bindings()
    (repo / SOURCE_PATH).write_bytes(b"x" * (MAX_SOURCE_BYTES + 1))
    with pytest.raises(GovernedPatchEvidenceError, match="bounded size"):
        parse_governed_patch_request(
            _content(bindings),
            repo_root=repo,
            expected=bindings,
            accepted_base_sha=BASE_SHA,
        )


def test_candidate_rejects_wrong_path_stale_context_and_source_drift(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    request = _request(repo, _bindings())
    wrong_path = DIFF.replace("pkg/example.py", "pkg/other.py")
    with pytest.raises(GovernedPatchEvidenceError, match="path"):
        build_candidate_bundle(request, wrong_path, bundle_root=evidence)
    stale = DIFF.replace('return "old"', 'return "absent"')
    with pytest.raises(GovernedPatchEvidenceError, match="not replayable"):
        build_candidate_bundle(request, stale, bundle_root=evidence)
    (repo / SOURCE_PATH).write_text(SOURCE + "# drift\n", encoding="utf-8")
    with pytest.raises(GovernedPatchEvidenceError, match="changed after request"):
        build_candidate_bundle(request, DIFF, bundle_root=evidence)


def test_candidate_rejects_oversized_postimage_before_any_effect_or_evidence_write(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    bindings = _bindings()
    large_line = "x" * (MAX_SOURCE_BYTES - 100)
    large_source = large_line + "\n"
    (repo / SOURCE_PATH).write_text(large_source, encoding="utf-8", newline="")
    content = _content(bindings)
    request = parse_governed_patch_request(
        content,
        repo_root=repo,
        expected=bindings,
        accepted_base_sha=BASE_SHA,
        expected_content_sha256=hashlib.sha256(content.encode()).hexdigest(),
    )
    added_line = "y" * 200
    # This custom parser treats an ``old_count=0`` hunk as a pure insertion
    # anchored after ``old_start`` (see ``_replay`` in foundry/patches.py),
    # so ``@@ -1,0 +2,1 @@`` inserts one line after the file's first line
    # without requiring any removed/context lines in the diff body itself.
    diff = (
        "--- a/pkg/example.py\n"
        "+++ b/pkg/example.py\n"
        "@@ -1,0 +2,1 @@\n"
        f"+{added_line}\n"
    )
    assert len(diff.encode("utf-8")) < 1024  # far below any diff size bound
    assert len(large_source.encode("utf-8")) + len(added_line) + 1 > MAX_SOURCE_BYTES
    target = repo / SOURCE_PATH
    before = target.stat()

    with pytest.raises(GovernedPatchEvidenceError, match="bounded source size"):
        build_candidate_bundle(request, diff, bundle_root=evidence)

    after = target.stat()
    assert target.read_bytes() == large_source.encode("utf-8")
    assert (after.st_dev, after.st_ino, after.st_ctime_ns) == (
        before.st_dev,
        before.st_ino,
        before.st_ctime_ns,
    )
    assert not evidence.exists()


def test_verify_rejects_oversized_postimage_for_a_bundle_built_before_the_bound(
    roots: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verification alone must catch an oversized postimage in an existing bundle."""
    import dharma_swarm.governed_patch_candidate_bundle as bundle_module

    repo, evidence = roots
    bindings = _bindings()
    large_line = "x" * (MAX_SOURCE_BYTES - 100)
    large_source = large_line + "\n"
    (repo / SOURCE_PATH).write_text(large_source, encoding="utf-8", newline="")
    content = _content(bindings)
    request = parse_governed_patch_request(
        content,
        repo_root=repo,
        expected=bindings,
        accepted_base_sha=BASE_SHA,
        expected_content_sha256=hashlib.sha256(content.encode()).hexdigest(),
    )
    added_line = "y" * 200
    diff = (
        "--- a/pkg/example.py\n"
        "+++ b/pkg/example.py\n"
        "@@ -1,0 +2,1 @@\n"
        f"+{added_line}\n"
    )
    with monkeypatch.context() as patch:
        # Simulate a bundle materialized under a lenient historical bound.
        patch.setattr(bundle_module, "MAX_SOURCE_BYTES", MAX_SOURCE_BYTES * 2)
        bundle = build_candidate_bundle(request, diff, bundle_root=evidence)

    target = repo / SOURCE_PATH
    before = target.stat()

    with pytest.raises(GovernedPatchEvidenceError, match="bounded source size"):
        verify_candidate_bundle(bundle)

    after = target.stat()
    assert target.read_bytes() == large_source.encode("utf-8")
    assert (after.st_dev, after.st_ino, after.st_ctime_ns) == (
        before.st_dev,
        before.st_ino,
        before.st_ctime_ns,
    )


def test_candidate_rejects_noop_diff_before_any_effect_or_evidence_write(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    request = _request(repo, _bindings())
    noop = DIFF.replace('+    return "new"', '+    return "old"')
    target = repo / SOURCE_PATH
    before = target.stat()

    with pytest.raises(GovernedPatchEvidenceError, match="change the exact source"):
        build_candidate_bundle(request, noop, bundle_root=evidence)

    after = target.stat()
    assert target.read_bytes() == SOURCE.encode("utf-8")
    assert (after.st_dev, after.st_ino, after.st_ctime_ns) == (
        before.st_dev,
        before.st_ino,
        before.st_ctime_ns,
    )
    assert not evidence.exists()


def test_candidate_refuses_repository_bundle_root_and_detects_tamper(
    roots: tuple[Path, Path],
) -> None:
    repo, _ = roots
    request = _request(repo, _bindings())
    for unsafe_root in (repo, repo / ".evidence", repo.parent, Path("/")):
        with pytest.raises(GovernedPatchEvidenceError, match="disjoint"):
            build_candidate_bundle(request, DIFF, bundle_root=unsafe_root)
    candidate = build_candidate_bundle(request, DIFF, bundle_root=repo.parent / "safe")
    candidate.diff_path.write_text("tampered", encoding="utf-8")
    with pytest.raises(GovernedPatchEvidenceError, match="tampered"):
        verify_candidate_bundle(candidate)


@pytest.mark.parametrize(
    ("outcome", "foundry", "vibe"),
    [
        (NoEffectOutcome.CANDIDATE_PRODUCED, None, None),
        (NoEffectOutcome.FOUNDRY_REJECTED, {"decision": "reject"}, None),
        (NoEffectOutcome.FOUNDRY_INCONCLUSIVE, {"decision": "unknown"}, None),
        (NoEffectOutcome.VIBE_REJECTED, {"decision": "pass"}, {"decision": "reject"}),
        (
            NoEffectOutcome.VIBE_INCONCLUSIVE,
            {"decision": "pass"},
            {"decision": "unknown"},
        ),
        (
            NoEffectOutcome.CALLER_ASSERTED_NO_EFFECT,
            {"decision": "pass"},
            {"decision": "clean"},
        ),
    ],
)
def test_result_sum_type_is_content_addressed_and_always_no_effect(
    roots: tuple[Path, Path],
    outcome: NoEffectOutcome,
    foundry: dict[str, str] | None,
    vibe: dict[str, str] | None,
) -> None:
    candidate = _candidate(roots)
    bound_foundry = None if foundry is None else _bound_evidence(candidate, foundry)
    bound_vibe = None if vibe is None else _bound_evidence(candidate, vibe)
    result = record_no_effect_result(
        candidate,
        outcome=outcome,
        foundry_evidence=bound_foundry,
        vibe_evidence=bound_vibe,
        reasons=("bounded observation",),
    )
    assert result.outcome is outcome
    assert result.repository_effect_authorized is False
    assert result.repository_effect_performed is False
    assert result.evidence_storage_effects_performed is True
    payload = json.loads(result.result_path.read_text(encoding="utf-8"))
    assert payload["repository_effect_authorized"] is False
    assert payload["repository_effect_performed"] is False
    assert payload["evidence_storage_effects_performed"] is True
    assert payload["authority_semantics"] == (
        "storage_only_unvalidated_signatures_no_warrant"
    )
    assert verify_no_effect_bundle(result) == result
    with pytest.raises(FrozenInstanceError):
        result.repository_effect_performed = True  # type: ignore[misc]


def test_result_rejects_invalid_evidence_shape_nonfinite_and_tamper(
    roots: tuple[Path, Path],
) -> None:
    candidate = _candidate(roots)
    with pytest.raises(GovernedPatchEvidenceError, match="evidence shape"):
        record_no_effect_result(
            candidate, outcome=NoEffectOutcome.CALLER_ASSERTED_NO_EFFECT
        )
    with pytest.raises(GovernedPatchEvidenceError, match="non-finite"):
        record_no_effect_result(
            candidate,
            outcome=NoEffectOutcome.FOUNDRY_INCONCLUSIVE,
            foundry_evidence=_bound_evidence(candidate, {"score": float("nan")}),
        )
    with pytest.raises(GovernedPatchEvidenceError, match="candidate-bound"):
        record_no_effect_result(
            candidate,
            outcome=NoEffectOutcome.FOUNDRY_INCONCLUSIVE,
            foundry_evidence={"decision": "unknown"},
        )
    with pytest.raises(GovernedPatchEvidenceError, match="bounded size"):
        record_no_effect_result(
            candidate,
            outcome=NoEffectOutcome.FOUNDRY_INCONCLUSIVE,
            foundry_evidence=_bound_evidence(
                candidate,
                {"blob": "x" * (MAX_VERIFIER_EVIDENCE_BYTES + 1)},
            ),
        )
    result = record_no_effect_result(
        candidate,
        outcome=NoEffectOutcome.CALLER_ASSERTED_NO_EFFECT,
        foundry_evidence=_bound_evidence(candidate, {"decision": "pass"}),
        vibe_evidence=_bound_evidence(candidate, {"decision": "clean"}),
    )
    assert result.vibe_evidence_path is not None
    result.vibe_evidence_path.write_text("{}", encoding="utf-8")
    with pytest.raises(GovernedPatchEvidenceError, match="tampered"):
        verify_no_effect_bundle(result)


def test_cold_result_verification_rejects_self_consistent_cross_candidate_evidence(
    roots: tuple[Path, Path],
) -> None:
    candidate = _candidate(roots)
    result = record_no_effect_result(
        candidate,
        outcome=NoEffectOutcome.CALLER_ASSERTED_NO_EFFECT,
        foundry_evidence=_bound_evidence(candidate, {"decision": "pass"}),
        vibe_evidence=_bound_evidence(candidate, {"decision": "clean"}),
    )
    assert result.foundry_evidence_path is not None
    assert result.vibe_evidence_path is not None

    foundry = json.loads(result.foundry_evidence_path.read_text(encoding="utf-8"))
    foundry["candidate_digest"] = "sha256:" + "f" * 64
    foundry_raw = json.dumps(
        foundry,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()
    payload = json.loads(result.result_path.read_text(encoding="utf-8"))
    payload["foundry_evidence_sha256"] = hashlib.sha256(foundry_raw).hexdigest()
    body = {key: value for key, value in payload.items() if key != "result_bundle_sha256"}
    body_raw = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()
    result_sha = hashlib.sha256(body_raw).hexdigest()
    payload["result_bundle_sha256"] = result_sha
    result_raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()
    relative_dir = f"results/sha256/{result_sha}"
    destination = result.bundle_root / relative_dir
    destination.mkdir(parents=True)
    (destination / "foundry_evidence.json").write_bytes(foundry_raw)
    (destination / "vibe_evidence.json").write_bytes(
        result.vibe_evidence_path.read_bytes()
    )
    (destination / "result.json").write_bytes(result_raw)
    forged = replace(
        result,
        relative_dir=relative_dir,
        result_bundle_sha256=result_sha,
        foundry_evidence_sha256=hashlib.sha256(foundry_raw).hexdigest(),
    )

    with pytest.raises(GovernedPatchEvidenceError, match="candidate-bound"):
        verify_no_effect_bundle(forged)
