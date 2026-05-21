from __future__ import annotations

import json
from pathlib import Path

from scripts.runtime import context_quorum as cq


def _policy(tmp_path: Path) -> Path:
    policy = {
        "version": 1,
        "agent_home_root": str(tmp_path / "agents"),
        "risk_levels": {
            "Q0": {"label": "read", "required_families": ["onboard"], "min_families": 1},
            "Q2": {
                "label": "code",
                "required_families": ["onboard", "exact_local", "protected_files"],
                "min_families": 3,
            },
        },
        "tool_families": {"onboard": "state", "exact_local": "search"},
        "protected_files": [
            {"pattern": "tests/**", "tier": "measurement", "reason": "test integrity"},
            {"pattern": "specs/Dharma_Constitution_v0.md", "tier": "sacred", "reason": "HP policy"},
        ],
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    return path


def test_protected_hits_match_globs(tmp_path: Path) -> None:
    policy = cq.load_policy(_policy(tmp_path))

    hits = cq.protected_hits(policy, ["tests/test_x.py", "docs/readme.md"])

    assert hits == [
        {
            "path": "tests/test_x.py",
            "pattern": "tests/**",
            "tier": "measurement",
            "reason": "test integrity",
        }
    ]


def test_init_agent_creates_dense_home(tmp_path: Path) -> None:
    policy_path = _policy(tmp_path)
    args = cq.parser().parse_args([
        "--policy",
        str(policy_path),
        "init-agent",
        "--agent",
        "repo_cartographer",
        "--role",
        "repo-cartographer",
    ])

    assert args.func(args) == 0
    root = tmp_path / "agents/repo_cartographer"
    assert (root / "passport.json").exists()
    assert (root / "context/context_manifest.latest.json").exists()
    assert (root / "tools/tool_registry.json").exists()
    assert (root / "handoff/HANDOFF.md").exists()


def test_check_blocks_protected_file_without_permission(tmp_path: Path) -> None:
    policy_path = _policy(tmp_path)
    cq.main(["--policy", str(policy_path), "init-agent", "--agent", "guardian", "--role", "guardian"])
    args = cq.parser().parse_args([
        "--policy",
        str(policy_path),
        "check",
        "--agent",
        "guardian",
        "--task-id",
        "t1",
        "--risk",
        "Q0",
        "--question",
        "touch test",
        "--changed-file",
        "tests/test_x.py",
        "--no-onboard",
    ])

    assert args.func(args) == 3
    manifest = json.loads((tmp_path / "agents/guardian/context/context_manifest.latest.json").read_text())
    assert manifest["protected_hits"][0]["path"] == "tests/test_x.py"
    assert manifest["allowed_next_action"] == "blocked_needs_context_or_permission"


def test_check_allows_protected_file_with_human_approval(tmp_path: Path) -> None:
    policy_path = _policy(tmp_path)
    cq.main(["--policy", str(policy_path), "init-agent", "--agent", "guardian", "--role", "guardian"])
    args = cq.parser().parse_args([
        "--policy",
        str(policy_path),
        "check",
        "--agent",
        "guardian",
        "--task-id",
        "t2",
        "--risk",
        "Q0",
        "--question",
        "approved test touch",
        "--changed-file",
        "tests/test_x.py",
        "--no-onboard",
        "--human-approval",
        "operator approved protected test inspection",
    ])

    assert args.func(args) == 2
    manifest = json.loads((tmp_path / "agents/guardian/context/context_manifest.latest.json").read_text())
    assert manifest["protected_hits"][0]["path"] == "tests/test_x.py"
    assert manifest["receipts"][-1]["family"] == "human_approval"
