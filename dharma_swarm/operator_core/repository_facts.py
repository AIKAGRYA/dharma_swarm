"""Repository state and cleanup-pressure facts.

Operator Ground Truth collects local git/worktree evidence. This module keeps
the cleanup policy pure and testable so that collection, interpretation, and
brief rendering do not collapse into one script.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


REPO_CLEANUP_CATEGORIES: tuple[str, ...] = (
    "clean-current",
    "dirty-hot",
    "dirty-docops",
    "dirty-generated",
    "superseded-likely",
    "salvage-candidate",
    "quarantine",
)

HOT_CODE_ROOTS: tuple[str, ...] = ("api/", "dashboard/", "dharma_swarm/", "terminal/")
HOT_PATH_PARTS: frozenset[str] = frozenset(
    {
        "agent_runner.py",
        "runtime",
        "runtime_state.py",
        "provider",
        "providers",
        "ontology",
    }
)
GENERATED_PREFIXES: tuple[str, ...] = (
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    "reports/generated/",
    "reports/repo_runway/",
    "results/",
)
GENERATED_SUFFIXES: tuple[str, ...] = (".log", ".pyc")
DOC_PREFIXES: tuple[str, ...] = ("docs/", "reports/", "specs/", "spec-forge/")
DOC_SUFFIXES: tuple[str, ...] = (".md", ".rst", ".txt")
BROAD_CHANGE_FILE_THRESHOLD = 20
BROAD_CHANGE_ROOT_THRESHOLD = 4

MAIN_BRANCHES: frozenset[str] = frozenset({"main", "master", "origin/main", "origin/master"})


@dataclass(frozen=True)
class RepositoryStateFact:
    """Raw local repository state facts.

    The branch facts are intentionally plain dicts because they are emitted by a
    script and written as JSON. Required keys are:
    ``kind``, ``name``, ``merged_into_origin_main``, and
    ``origin_main_is_ancestor``.
    """

    repo: dict[str, Any] = field(default_factory=dict)
    worktrees: list[dict[str, Any]] = field(default_factory=list)
    local_branches: list[dict[str, Any]] = field(default_factory=list)
    remote_branches: list[dict[str, Any]] = field(default_factory=list)
    fact_type: str = "RepositoryStateFact"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_type": self.fact_type,
            "repo": self.repo,
            "worktrees": self.worktrees,
            "local_branches": self.local_branches,
            "remote_branches": self.remote_branches,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RepositoryStateFact":
        return cls(
            repo=payload.get("repo") if isinstance(payload.get("repo"), dict) else {},
            worktrees=_dict_records(payload.get("worktrees")),
            local_branches=_dict_records(payload.get("local_branches")),
            remote_branches=_dict_records(payload.get("remote_branches")),
        )


@dataclass(frozen=True)
class RepoCleanupFact:
    """Interpreted cleanup pressure derived from RepositoryStateFact."""

    category_counts: dict[str, int]
    worktree_count: int
    dirty_worktree_count: int
    dirty_hot_lane_count: int
    local_branch_count: int
    local_branch_not_merged_count: int
    local_branch_merged_count: int
    remote_branch_not_merged_count: int
    top_cleanup_candidates: list[dict[str, Any]]
    fact_type: str = "RepoCleanupFact"
    source_fact: str = "RepositoryStateFact"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_type": self.fact_type,
            "source_fact": self.source_fact,
            "category_counts": self.category_counts,
            "worktree_count": self.worktree_count,
            "dirty_worktree_count": self.dirty_worktree_count,
            "dirty_hot_lane_count": self.dirty_hot_lane_count,
            "local_branch_count": self.local_branch_count,
            "local_branch_not_merged_count": self.local_branch_not_merged_count,
            "local_branch_merged_count": self.local_branch_merged_count,
            "remote_branch_not_merged_count": self.remote_branch_not_merged_count,
            "top_cleanup_candidates": self.top_cleanup_candidates,
        }


def build_repo_cleanup_fact(state: RepositoryStateFact) -> RepoCleanupFact:
    """Build cleanup pressure from raw repository state facts."""

    annotated_worktrees: list[dict[str, Any]] = []
    for worktree in state.worktrees:
        item = dict(worktree)
        category = str(item.get("category") or classify_repo_cleanup_worktree(
            dirty=bool(item.get("dirty")),
            changed_files=_string_list(item.get("changed_files")),
            ahead=_int_or_none(item.get("ahead")),
            behind=_int_or_none(item.get("behind")),
            branch=_string_or_none(item.get("branch_name") or item.get("branch")),
        ))
        item["category"] = category
        item["has_hot_changes"] = any(is_hot_repo_path(path) for path in _string_list(item.get("changed_files")))
        item["recommendation"] = str(item.get("recommendation") or repo_cleanup_recommendation(category))
        annotated_worktrees.append(item)

    category_counts: dict[str, int] = {category: 0 for category in REPO_CLEANUP_CATEGORIES}
    for item in annotated_worktrees:
        category = str(item.get("category") or "quarantine")
        category_counts[category] = category_counts.get(category, 0) + 1

    branch_candidates = [
        _branch_cleanup_candidate(branch)
        for branch in [*state.local_branches, *state.remote_branches]
    ]
    branch_candidates = [
        candidate for candidate in branch_candidates
        if candidate is not None
    ]
    worktree_candidates = [
        {
            "kind": "worktree",
            "label": str(item.get("branch_name") or item.get("branch") or item.get("path") or "unknown"),
            "path": str(item.get("path") or ""),
            "category": str(item.get("category") or "quarantine"),
            "recommendation": str(item.get("recommendation") or ""),
        }
        for item in annotated_worktrees
        if item.get("category") in {"quarantine", "salvage-candidate", "dirty-hot"}
    ]
    candidates = sorted(
        [*worktree_candidates, *branch_candidates],
        key=lambda item: (
            repo_cleanup_rank(str(item.get("category"))),
            str(item.get("kind")),
            str(item.get("label")),
        ),
    )

    local_branches = [
        branch for branch in state.local_branches
        if _branch_name(branch) not in {"main", "master"}
    ]
    local_not_merged = [
        branch for branch in local_branches
        if not bool(branch.get("merged_into_origin_main"))
    ]
    local_merged = [
        branch for branch in local_branches
        if bool(branch.get("merged_into_origin_main"))
    ]
    remote_not_merged = [
        branch for branch in state.remote_branches
        if _branch_name(branch) not in MAIN_BRANCHES
        and " -> " not in _branch_name(branch)
        and not bool(branch.get("merged_into_origin_main"))
    ]
    dirty_worktree_count = sum(1 for item in annotated_worktrees if item.get("dirty"))
    dirty_hot_lane_count = sum(
        1
        for item in annotated_worktrees
        if item.get("dirty") and item.get("category") == "dirty-hot"
    )
    return RepoCleanupFact(
        category_counts=category_counts,
        worktree_count=len(annotated_worktrees),
        dirty_worktree_count=dirty_worktree_count,
        dirty_hot_lane_count=dirty_hot_lane_count,
        local_branch_count=len(local_branches),
        local_branch_not_merged_count=len(local_not_merged),
        local_branch_merged_count=len(local_merged),
        remote_branch_not_merged_count=len(remote_not_merged),
        top_cleanup_candidates=candidates[:5],
    )


def classify_repo_cleanup_worktree(
    *,
    dirty: bool,
    changed_files: list[str],
    ahead: int | None = None,
    behind: int | None = None,
    branch: str | None = None,
) -> str:
    """Deterministically classify one worktree for cleanup triage."""

    if not dirty:
        if branch in {"main", "master"} and not ahead and not behind:
            return "clean-current"
        if ahead == 0 and behind == 0:
            return "clean-current"
        if ahead == 0 and (behind or 0) > 0:
            return "superseded-likely"
        return "salvage-candidate"

    if changed_files and all(is_generated_path(path) for path in changed_files):
        return "dirty-generated"
    if changed_files and all(is_docops_path(path) for path in changed_files):
        return "dirty-docops"
    if any(is_hot_repo_path(path) for path in changed_files):
        return "dirty-hot"
    if is_broad_change(changed_files):
        return "quarantine"
    return "salvage-candidate"


def classify_branch_cleanup(
    *,
    merged_into_origin_main: bool,
    origin_main_is_ancestor: bool | None,
) -> str:
    if merged_into_origin_main:
        return "superseded-likely"
    if origin_main_is_ancestor:
        return "salvage-candidate"
    return "quarantine"


def is_generated_path(path: str) -> bool:
    normalized = norm_repo_path(path)
    return normalized.startswith(GENERATED_PREFIXES) or normalized.endswith(GENERATED_SUFFIXES)


def is_docops_path(path: str) -> bool:
    normalized = norm_repo_path(path)
    return (
        normalized.startswith(DOC_PREFIXES)
        or normalized.endswith(DOC_SUFFIXES)
        or normalized in {"readme.md", "claude.md", "agents.md"}
    )


def is_hot_repo_path(path: str) -> bool:
    normalized = norm_repo_path(path)
    if is_docops_path(normalized) or is_generated_path(normalized):
        return False
    if not normalized.startswith(HOT_CODE_ROOTS):
        return False
    parts = normalized.split("/")
    if normalized in {"dharma_swarm/agent_runner.py"}:
        return True
    return any(part in HOT_PATH_PARTS or "provider" in part for part in parts)


def is_broad_change(changed_files: list[str]) -> bool:
    if len(changed_files) >= BROAD_CHANGE_FILE_THRESHOLD:
        return True
    roots = {norm_repo_path(path).split("/", 1)[0] for path in changed_files if path}
    return len(roots) >= BROAD_CHANGE_ROOT_THRESHOLD


def norm_repo_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lower()


def repo_cleanup_rank(category: str) -> int:
    return {
        "dirty-hot": 0,
        "quarantine": 1,
        "salvage-candidate": 2,
        "dirty-docops": 3,
        "dirty-generated": 4,
        "superseded-likely": 5,
        "clean-current": 6,
    }.get(category, 9)


def repo_cleanup_recommendation(category: str) -> str:
    return {
        "clean-current": "Keep as baseline; no cleanup action needed.",
        "dirty-hot": "Pause parallel hot-lane work and reconcile manually before merge.",
        "dirty-docops": "Review doc/report-only diff and either archive or fold into DocOps.",
        "dirty-generated": "Archive or ignore generated artifacts after confirming no source edits.",
        "superseded-likely": "Verify merged state, then retire branch/worktree manually.",
        "salvage-candidate": "Salvage with a scoped test run before opening more work.",
        "quarantine": "Quarantine until overlap and blast radius are manually reviewed.",
    }.get(category, "Review manually.")


def _branch_cleanup_candidate(branch: dict[str, Any]) -> dict[str, Any] | None:
    name = _branch_name(branch)
    if not name or name in MAIN_BRANCHES or " -> " in name:
        return None
    category = classify_branch_cleanup(
        merged_into_origin_main=bool(branch.get("merged_into_origin_main")),
        origin_main_is_ancestor=(
            bool(branch.get("origin_main_is_ancestor"))
            if branch.get("origin_main_is_ancestor") is not None
            else None
        ),
    )
    return {
        "kind": str(branch.get("kind") or "branch"),
        "label": name,
        "category": category,
        "recommendation": repo_cleanup_recommendation(category),
    }


def _branch_name(branch: dict[str, Any]) -> str:
    return str(branch.get("name") or branch.get("label") or "").strip()


def _dict_records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _string_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


__all__ = [
    "REPO_CLEANUP_CATEGORIES",
    "RepoCleanupFact",
    "RepositoryStateFact",
    "build_repo_cleanup_fact",
    "classify_branch_cleanup",
    "classify_repo_cleanup_worktree",
    "is_broad_change",
    "is_docops_path",
    "is_generated_path",
    "is_hot_repo_path",
    "norm_repo_path",
    "repo_cleanup_rank",
    "repo_cleanup_recommendation",
]
