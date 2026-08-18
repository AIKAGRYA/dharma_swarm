"""Executable contract for truthful DocOps reconcile delivery.

The workflow cannot run locally, so these tests pin its authority-bearing shell
surface: a rolling PR is actionable only when the exact delivered head exposes
every canonical GitHub Actions context, and only direct-main delivery carries
the loop-suppression marker.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (
    REPO_ROOT / ".github" / "workflows" / "docops-reconcile-main.yml"
).read_text(encoding="utf-8")


def test_exact_head_requires_the_full_canonical_context_set() -> None:
    """One arbitrary check run is not evidence of actionable delivery."""
    assert "required_contexts_present()" in WORKFLOW
    assert "scripts/governance/ci_parity_manifest.json" in WORKFLOW
    assert 'manifest["required_contexts"]' in WORKFLOW
    assert "comm -23" in WORKFLOW
    assert "gh api --paginate --slurp" in WORKFLOW
    assert "filter=all" in WORKFLOW
    assert "| jq -r" in WORKFLOW
    assert "select(.app.id == 15368)" in WORKFLOW
    assert "group_by(.name)" in WORKFLOW
    assert "map(max_by(.id))" in WORKFLOW
    assert '.conclusion == "success"' in WORKFLOW
    assert '.conclusion == "neutral"' in WORKFLOW
    assert '.conclusion == "skipped"' in WORKFLOW
    assert ".total_count" not in WORKFLOW
    assert "verify_head_checks" not in WORKFLOW


def test_check_run_evidence_has_explicit_read_authority() -> None:
    assert "permissions:\n  checks: read\n" in WORKFLOW


def test_both_rolling_pr_paths_verify_the_exact_delivered_head() -> None:
    call = 'verify_required_contexts "$(git rev-parse HEAD)"'
    assert WORKFLOW.count(call) == 2
    assert "verify_required_contexts()" in WORKFLOW


def test_missing_required_context_is_a_red_job() -> None:
    verify_start = WORKFLOW.index("verify_required_contexts() {")
    verify_end = WORKFLOW.index("# Tier 2 uses one rolling PR", verify_start)
    verify_block = WORKFLOW[verify_start:verify_end]
    assert "::error::" in verify_block
    assert "return 1" in verify_block
    assert "::warning::" not in verify_block


def test_byte_identical_rolling_head_is_reused_only_with_full_evidence() -> None:
    reuse_start = WORKFLOW.index("# Tier 2 uses one rolling PR")
    commit_start = WORKFLOW.index("echo \"DocOps counts drifted", reuse_start)
    reuse_block = WORKFLOW[reuse_start:commit_start]
    assert 'remote_head="$(git rev-parse FETCH_HEAD)"' in reuse_block
    assert 'required_contexts_present "$remote_head"' in reuse_block
    assert "its exact head is actionable" in reuse_block


def test_skip_ci_is_added_only_inside_direct_main_delivery() -> None:
    commit_start = WORKFLOW.index('COMMIT_SUBJECT="chore(docops)')
    tier_one = WORKFLOW.index('if [ "$HAS_BYPASS_TOKEN" = "true" ]', commit_start)
    tier_two = WORKFLOW.index("# ---- Tier 2", tier_one)

    neutral_commit = WORKFLOW[commit_start:tier_one]
    direct_main = WORKFLOW[tier_one:tier_two]
    assert "[skip ci]" not in neutral_commit
    assert "git commit --amend" in direct_main
    assert '${COMMIT_SUBJECT} [skip ci]' in direct_main


def test_generated_pr_body_satisfies_coherence_delta_contract() -> None:
    required_fields = (
        "Organ touched:",
        "Declared-vs-actual gap closed:",
        "Proof that re-reads the map:",
        "New drift introduced:",
    )
    for field in required_fields:
        assert field in WORKFLOW
    assert '--body-file "$body_file"' in WORKFLOW


def test_success_requires_delivery_to_main_or_actionable_pr() -> None:
    assert "exit 1" in WORKFLOW
    assert "reconcile could not be delivered" in WORKFLOW
    assert "bypass token present but the direct push was rejected" in WORKFLOW


def test_reconcile_stages_only_the_two_governed_files() -> None:
    assert (
        "git add docs/docops/AUTO_INVENTORY.md "
        "docs/governance/SOVEREIGN_MANIFEST.md" in WORKFLOW
    )
    command_lines = [
        line.strip()
        for line in WORKFLOW.splitlines()
        if not line.strip().startswith("#")
    ]
    assert not any(line.startswith("git add -A") for line in command_lines)


def test_reconcile_runs_are_serialized() -> None:
    assert "concurrency:" in WORKFLOW
    assert "group: docops-reconcile-main" in WORKFLOW
    assert "cancel-in-progress: false" in WORKFLOW
