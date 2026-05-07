from __future__ import annotations

from dharma_swarm.operator_core.repository_facts import (
    RepositoryStateFact,
    build_repo_cleanup_fact,
    classify_repo_cleanup_worktree,
    is_generated_path,
    norm_repo_path,
)


def test_norm_repo_path_preserves_dot_cache_prefixes() -> None:
    assert norm_repo_path(".pytest_cache/v/cache/nodeids") == ".pytest_cache/v/cache/nodeids"
    assert norm_repo_path("./.ruff_cache/content") == ".ruff_cache/content"
    assert is_generated_path(".pytest_cache/v/cache/nodeids") is True


def test_dot_cache_dirty_worktree_is_generated_not_salvage() -> None:
    assert (
        classify_repo_cleanup_worktree(
            dirty=True,
            changed_files=[".pytest_cache/v/cache/nodeids"],
        )
        == "dirty-generated"
    )


def test_repo_cleanup_fact_surfaces_merged_local_branch_candidate() -> None:
    state = RepositoryStateFact(
        worktrees=[],
        local_branches=[
            {
                "kind": "local-branch",
                "name": "feature/already-merged",
                "merged_into_origin_main": True,
                "origin_main_is_ancestor": None,
            }
        ],
        remote_branches=[],
    )

    cleanup = build_repo_cleanup_fact(state).to_dict()

    assert cleanup["local_branch_merged_count"] == 1
    assert any(
        item["label"] == "feature/already-merged"
        and item["category"] == "superseded-likely"
        for item in cleanup["top_cleanup_candidates"]
    )
