from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.forge_v1.forge_v2 import phase4_alpha


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_paths_from_diff_extracts_all_sides() -> None:
    diff = """diff --git a/dharma_swarm/forge_v1/forge_v2/arms.py b/dharma_swarm/forge_v1/forge_v2/arms.py
--- a/dharma_swarm/forge_v1/forge_v2/arms.py
+++ b/dharma_swarm/forge_v1/forge_v2/arms.py
@@
 pass
"""

    assert phase4_alpha.paths_from_diff(diff) == ["dharma_swarm/forge_v1/forge_v2/arms.py"]


def test_code_candidate_safety_refuses_forbidden_packet_guard_patch() -> None:
    patch = """diff --git a/dharma_swarm/forge_v1/forge_v2/packet_guard.py b/dharma_swarm/forge_v1/forge_v2/packet_guard.py
--- a/dharma_swarm/forge_v1/forge_v2/packet_guard.py
+++ b/dharma_swarm/forge_v1/forge_v2/packet_guard.py
@@
-MIN_CONFIRM_N = 500
+MIN_CONFIRM_N = 1
"""

    receipt = phase4_alpha.evaluate_code_candidate_safety(
        patch=patch,
        isolated_worktree="/tmp/isolated-child",
    )

    assert receipt["decision"] == "refused"
    assert "dharma_swarm/forge_v1/forge_v2/packet_guard.py" in receipt["forbidden_hits"]
    assert "forbidden_path:dharma_swarm/forge_v1/forge_v2/packet_guard.py" in receipt["blockers"]
    assert receipt["live_apply_allowed"] is False
    assert receipt["promotion_gate"] == "verify_promotion_only"


def test_code_candidate_safety_refuses_test_patch() -> None:
    patch = """diff --git a/tests/test_forge_packet_guard.py b/tests/test_forge_packet_guard.py
--- a/tests/test_forge_packet_guard.py
+++ b/tests/test_forge_packet_guard.py
@@
-assert blocked
+assert True
"""

    receipt = phase4_alpha.evaluate_code_candidate_safety(
        patch=patch,
        isolated_worktree="/tmp/isolated-child",
    )

    assert receipt["decision"] == "refused"
    assert "tests/test_forge_packet_guard.py" in receipt["forbidden_hits"]


def test_code_candidate_safety_refuses_allowed_grader_success_hardcode() -> None:
    patch = """diff --git a/dharma_swarm/forge_v1/forge_v2/pr_suite_grader.py b/dharma_swarm/forge_v1/forge_v2/pr_suite_grader.py
--- a/dharma_swarm/forge_v1/forge_v2/pr_suite_grader.py
+++ b/dharma_swarm/forge_v1/forge_v2/pr_suite_grader.py
@@
-        resolved = test_result.passed
+        resolved = True
"""

    receipt = phase4_alpha.evaluate_code_candidate_safety(
        patch=patch,
        isolated_worktree="/tmp/isolated-child",
    )

    assert receipt["decision"] == "refused"
    assert receipt["forbidden_hits"] == []
    assert receipt["outside_allowed_hits"] == []
    assert receipt["semantic_weakening_findings"][0]["kind"] == "success_hardcode"
    assert "semantic_weakening:success_hardcode" in receipt["blockers"]


def test_code_candidate_safety_refuses_critical_blocker_removal() -> None:
    patch = """diff --git a/dharma_swarm/forge_v1/forge_v2/pr_suite_grader.py b/dharma_swarm/forge_v1/forge_v2/pr_suite_grader.py
--- a/dharma_swarm/forge_v1/forge_v2/pr_suite_grader.py
+++ b/dharma_swarm/forge_v1/forge_v2/pr_suite_grader.py
@@
-            blockers.append("patch_touches_test_file")
+            pass
"""

    receipt = phase4_alpha.evaluate_code_candidate_safety(
        patch=patch,
        isolated_worktree="/tmp/isolated-child",
    )

    assert receipt["decision"] == "refused"
    assert receipt["semantic_weakening_findings"][0]["kind"] == "critical_blocker_removed"
    assert receipt["semantic_weakening_findings"][0]["token"] == "patch_touches_test_file"
    assert "semantic_weakening:critical_blocker_removed" in receipt["blockers"]


def test_code_candidate_safety_allows_benign_allowed_patch_semantically() -> None:
    patch = """diff --git a/dharma_swarm/forge_v1/forge_v2/budget.py b/dharma_swarm/forge_v1/forge_v2/budget.py
--- a/dharma_swarm/forge_v1/forge_v2/budget.py
+++ b/dharma_swarm/forge_v1/forge_v2/budget.py
@@
-SHADOW_USD_PER_MTOK = 0.50
+SHADOW_USD_PER_MTOK = 0.55
"""

    receipt = phase4_alpha.evaluate_code_candidate_safety(
        patch=patch,
        isolated_worktree="/tmp/isolated-child",
    )

    assert receipt["decision"] == "pass"
    assert receipt["semantic_weakening_findings"] == []


def test_archive_scaffold_candidate_records_lineage_and_receipts(tmp_path: Path) -> None:
    result = phase4_alpha.archive_scaffold_candidate(
        archive_root=tmp_path,
        parent_id="parent-genome",
        genome={
            "arm": "verify_chain",
            "generator": "glm-5.2",
            "verifier": "kimi-k2.7-code:cloud",
            "window_chars": 9000,
        },
        mutation_description="reduce context window for click-only EXPLORE",
        evaluation={
            "closeout": "measured_negative",
            "fitness": 0.0,
            "ci": {"n": 10, "mean": 0.0, "lower": 0.0, "upper": 0.0},
            "task_results": {"resolved": 0, "n": 10},
            "budget": {"cost_usd": 0.0585, "spent_tokens": 116699},
        },
        receipt_links=["/tmp/phase3.md"],
        reason="phase3 measured_negative; keep as baseline parent",
    )

    assert result["decision"] == "accepted_for_archive"
    rows = _read_jsonl(tmp_path / "scaffold_genomes.jsonl")
    assert len(rows) == 1
    entry = rows[0]
    assert entry["parent_id"] == "parent-genome"
    payload = entry["test_results"]
    assert payload["track"] == phase4_alpha.TRACK_A_SCAFFOLD
    assert payload["genome"]["window_chars"] == 9000
    assert payload["receipt_links"] == ["/tmp/phase3.md"]
    assert payload["live_apply_allowed"] is False


def test_archive_code_candidate_refusal_is_receipted_not_archived(tmp_path: Path) -> None:
    result = phase4_alpha.archive_code_candidate(
        archive_root=tmp_path,
        parent_id="code-parent",
        mutation_description="badly weaken promotion gate",
        isolated_worktree="/tmp/code-child",
        patch="""diff --git a/dharma_swarm/forge_v1/forge_v2/verify_promotion.py b/dharma_swarm/forge_v1/forge_v2/verify_promotion.py
--- a/dharma_swarm/forge_v1/forge_v2/verify_promotion.py
+++ b/dharma_swarm/forge_v1/forge_v2/verify_promotion.py
@@
-live_apply_allowed = False
+live_apply_allowed = True
""",
        evaluation={"unit_tests_passed": False},
    )

    assert result["decision"] == "refused"
    assert result["live_archive_touched"] is False
    assert not (tmp_path / "code_children.jsonl").exists()
    refused = _read_jsonl(tmp_path / "refusals.jsonl")
    assert refused[0]["track"] == phase4_alpha.TRACK_B_CODE
    assert refused[0]["safety_receipt"]["decision"] == "refused"


def test_archive_code_candidate_accepts_allowed_isolated_patch(tmp_path: Path) -> None:
    patch = """diff --git a/dharma_swarm/forge_v1/forge_v2/arms.py b/dharma_swarm/forge_v1/forge_v2/arms.py
--- a/dharma_swarm/forge_v1/forge_v2/arms.py
+++ b/dharma_swarm/forge_v1/forge_v2/arms.py
@@
-DEFAULT_WINDOW_CHARS = 11000
+DEFAULT_WINDOW_CHARS = 9000
"""

    result = phase4_alpha.archive_code_candidate(
        archive_root=tmp_path,
        parent_id="code-parent",
        mutation_description="candidate shrink context window for budget safety",
        isolated_worktree="/tmp/code-child",
        patch=patch,
        evaluation={
            "static_checks_passed": True,
            "unit_tests_passed": True,
            "task_count": 3,
            "resolved_count": 0,
            "cost_usd": 0.01,
            "tokens_used": 1234,
        },
        receipt_links=["/tmp/unit-test-receipt.txt"],
    )

    assert result["decision"] == "accepted_for_archive"
    rows = _read_jsonl(tmp_path / "code_children.jsonl")
    assert len(rows) == 1
    entry = rows[0]
    assert entry["parent_id"] == "code-parent"
    assert entry["diff"] == ""
    assert entry["shadow_diff"] == patch
    assert entry["status"] == "proposed"
    payload = entry["test_results"]
    assert payload["track"] == phase4_alpha.TRACK_B_CODE
    assert payload["safety_receipt"]["decision"] == "pass"
    assert payload["live_apply_allowed"] is False


def test_archive_code_candidate_refuses_safe_patch_when_unit_tests_fail(tmp_path: Path) -> None:
    patch = """diff --git a/dharma_swarm/forge_v1/forge_v2/arms.py b/dharma_swarm/forge_v1/forge_v2/arms.py
--- a/dharma_swarm/forge_v1/forge_v2/arms.py
+++ b/dharma_swarm/forge_v1/forge_v2/arms.py
@@
-DEFAULT_WINDOW_CHARS = 11000
+DEFAULT_WINDOW_CHARS = 9000
"""

    result = phase4_alpha.archive_code_candidate(
        archive_root=tmp_path,
        parent_id="code-parent",
        mutation_description="candidate shrink context window for budget safety",
        isolated_worktree="/tmp/code-child",
        patch=patch,
        evaluation={
            "static_checks_passed": True,
            "unit_tests_passed": False,
            "unit_test_command": "pytest tests/test_forge_v2.py",
        },
    )

    assert result["decision"] == "refused"
    assert result["blockers"] == ["unit_tests_failed"]
    assert not (tmp_path / "code_children.jsonl").exists()
    refused = _read_jsonl(tmp_path / "refusals.jsonl")
    assert refused[0]["reason"] == "evaluation_gate_failed"
    assert refused[0]["evaluation_blockers"] == ["unit_tests_failed"]


def test_summarize_phase4_archive_counts_tracks(tmp_path: Path) -> None:
    phase4_alpha.archive_scaffold_candidate(
        archive_root=tmp_path,
        parent_id=None,
        genome={"arm": "verify_chain"},
        mutation_description="baseline",
        evaluation={"closeout": "measured_negative", "task_count": 10},
    )
    phase4_alpha.archive_code_candidate(
        archive_root=tmp_path,
        parent_id=None,
        mutation_description="allowed",
        isolated_worktree="/tmp/wt",
        patch="""diff --git a/dharma_swarm/forge_v1/forge_v2/budget.py b/dharma_swarm/forge_v1/forge_v2/budget.py
--- a/dharma_swarm/forge_v1/forge_v2/budget.py
+++ b/dharma_swarm/forge_v1/forge_v2/budget.py
@@
 pass
""",
        evaluation={"static_checks_passed": True, "unit_tests_passed": True},
    )

    summary = phase4_alpha.summarize_phase4_archive(archive_root=tmp_path)

    assert summary["scaffold_candidates"] == 1
    assert summary["code_children"] == 1
    assert summary["refusals"] == 0
    assert summary["live_archive_touched"] is False
    assert (tmp_path / "latest_summary.json").exists()
