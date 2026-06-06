from __future__ import annotations

import pytest

from dharma_swarm.operator_core.living_agent_kernel_lessons import (
    EmptyLessonDeltaError,
    KernelLessonStore,
    safe_namespace_filename,
)
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash

NS_A = "agent:codex_composer:lessons"
NS_B = "agent:codex_composer:skills"


def _store(tmp_path) -> KernelLessonStore:
    return KernelLessonStore(tmp_path / "kernel")


# ------------------------- unit -------------------------

def test_append_returns_sealed_receipt_recomputable_with_blanked_entry_hash(tmp_path):
    store = _store(tmp_path)
    receipt = store.append_lesson("codex_composer", NS_A, "learned to chain ledgers", run_id="r1")

    assert receipt.entry_hash.startswith("sha256:")
    assert receipt.ledger_sequence == 1
    assert receipt.previous_entry_hash == ""
    assert receipt.delta_hash == stable_payload_hash("learned to chain ledgers")

    material = receipt.model_dump(mode="json")
    material["entry_hash"] = ""
    assert stable_payload_hash(material) == receipt.entry_hash


def test_two_sequential_appends_chain(tmp_path):
    store = _store(tmp_path)
    first = store.append_lesson("codex_composer", NS_A, "first lesson")
    second = store.append_lesson("codex_composer", NS_A, "second lesson")

    assert first.ledger_sequence == 1
    assert second.ledger_sequence == 2
    assert second.previous_entry_hash == first.entry_hash
    assert first.previous_entry_hash == ""


def test_two_namespaces_same_agent_independent_chains_and_files(tmp_path):
    store = _store(tmp_path)
    a = store.append_lesson("codex_composer", NS_A, "ns A lesson")
    b = store.append_lesson("codex_composer", NS_B, "ns B lesson")

    path_a = store.namespace_path(NS_A)
    path_b = store.namespace_path(NS_B)
    assert path_a != path_b
    assert path_a.exists() and path_b.exists()

    assert a.ledger_sequence == 1
    assert b.ledger_sequence == 1
    assert a.previous_entry_hash == ""
    assert b.previous_entry_hash == ""
    # entry hashes differ because namespace + delta differ
    assert a.entry_hash != b.entry_hash


def test_empty_delta_raises_and_creates_no_file_or_row(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(EmptyLessonDeltaError):
        store.append_lesson("codex_composer", NS_A, "   \n\t  ")
    with pytest.raises(EmptyLessonDeltaError):
        store.append_lesson("codex_composer", NS_A, "")

    assert not store.namespace_path(NS_A).exists()
    assert store.lessons(NS_A) == []


# ------------------------- integration -------------------------

def test_append_five_across_two_namespaces_then_verify_both_pass(tmp_path):
    store = _store(tmp_path)
    for i in range(3):
        store.append_lesson("codex_composer", NS_A, f"A-{i}", run_id=f"rA{i}")
    for i in range(2):
        store.append_lesson("codex_composer", NS_B, f"B-{i}", run_id=f"rB{i}")

    ok_a, errors_a = store.verify_lesson_ledger(NS_A)
    ok_b, errors_b = store.verify_lesson_ledger(NS_B)
    assert (ok_a, errors_a) == (True, [])
    assert (ok_b, errors_b) == (True, [])
    assert len(store.lessons(NS_A)) == 3
    assert len(store.lessons(NS_B)) == 2


def test_chain_durable_across_fresh_store_instances(tmp_path):
    base = tmp_path / "kernel"
    first = KernelLessonStore(base)
    first.append_lesson("codex_composer", NS_A, "persist me 1")
    first.append_lesson("codex_composer", NS_A, "persist me 2")

    reopened = KernelLessonStore(base)
    third = reopened.append_lesson("codex_composer", NS_A, "persist me 3")
    assert third.ledger_sequence == 3

    ok, errors = reopened.verify_lesson_ledger(NS_A)
    assert (ok, errors) == (True, [])


# ------------------------- adversarial -------------------------

def test_rewrite_delta_text_in_line_three_reports_entry_hash_mismatch(tmp_path):
    store = _store(tmp_path)
    for i in range(4):
        store.append_lesson("codex_composer", NS_A, f"lesson-{i}")

    path = store.namespace_path(NS_A)
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[2] = lines[2].replace("lesson-2", "lesson-X")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, errors = store.verify_lesson_ledger(NS_A)
    assert ok is False
    assert any("line 3" in e and "entry_hash mismatch" in e for e in errors)


def test_delete_middle_row_reports_sequence_and_previous_hash_mismatch(tmp_path):
    store = _store(tmp_path)
    for i in range(4):
        store.append_lesson("codex_composer", NS_A, f"lesson-{i}")

    path = store.namespace_path(NS_A)
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]  # drop the second row
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, errors = store.verify_lesson_ledger(NS_A)
    assert ok is False
    assert any("ledger_sequence mismatch" in e for e in errors)
    assert any("previous_entry_hash mismatch" in e for e in errors)


def test_namespace_with_traversal_cannot_escape_lessons_dir(tmp_path):
    store = _store(tmp_path)
    lessons_root = store.lessons_dir.resolve()

    for evil in ("../../etc/passwd", "/abs/escape", "a/../../b", "..\\..\\win"):
        path = store.namespace_path(evil)
        assert path.parent == lessons_root
        store.append_lesson("codex_composer", evil, "contained")
        assert path.exists()
        assert lessons_root in path.parents


def test_safe_filename_is_deterministic_and_collision_resistant():
    assert safe_namespace_filename(NS_A) == safe_namespace_filename(NS_A)
    # two namespaces that slug-sanitize identically still map to distinct files
    assert safe_namespace_filename("a/b") != safe_namespace_filename("a:b")
