"""Door policy guard: pure-evaluation tests + policy-file pins (PR-A)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import check_automerge_tier_policy as guard  # noqa: E402

POLICY = json.loads(
    (REPO_ROOT / "scripts" / "governance" / "automerge_tier_policy.json").read_text()
)


def _evaluate(**overrides):
    base = dict(
        labels=["bot-pr"],
        is_draft=False,
        changed_paths=["dharma_swarm/foo.py", "tests/test_foo.py"],
        diff_lines=100,
        diff_text="",
        approved_reviews=[
            {"login": "codex", "state": "APPROVED", "body": ""},
            {"login": "copilot", "state": "APPROVED", "body": ""},
        ],
        author="devin-ai-integration[bot]",
        merged_last_24h=0,
        policy=POLICY,
    )
    base.update(overrides)
    return guard.evaluate(**base)


def test_unlabeled_pr_always_passes():
    report = _evaluate(labels=["mike-watch"])
    assert report["passed"] is True
    assert not report["labeled_for_unattended"]


def test_draft_pr_never_binds():
    assert _evaluate(is_draft=True)["passed"] is True


def test_clean_tier1_bot_pr_passes():
    report = _evaluate()
    assert report["passed"] is True
    assert report["tier"] == "tier1"


def test_tier2_touch_fails_whatever_else_is_green():
    report = _evaluate(changed_paths=[".github/workflows/automerge.yml"])
    assert report["passed"] is False
    assert report["tier2_hits"] == [".github/workflows/automerge.yml"]


def test_every_ratified_tier2_surface_is_matched():
    # Spot-pin the ruling's §5 list against the policy file patterns.
    for path in (
        ".github/workflows/anything.yml",
        "scripts/runtime/pr_merge_control.py",
        "docs/governance/MMM_CHARTER.md",
        "docs/ops/loop_control/KILLSWITCH",
        "dharma_swarm/forge_v1/forge_v2/verify_promotion.py",
        "dharma_swarm/revenue/spine_models.py",
        "dharma_swarm/a2a/nats_transport.py",
        "docs/sarathi_apex_build/06_PROOF_GATES.md",
        "scripts/governance/automerge_tier_policy.json",
        "docs/governance/ACTIVE_TRACK.yaml",
    ):
        assert guard.tier2_hits([path], POLICY) == [path], f"uncovered referee path: {path}"


def test_diff_ceiling_tier1():
    report = _evaluate(diff_lines=601)
    assert report["passed"] is False
    assert any("ceiling" in v for v in report["violations"])


def test_docs_only_is_tier0_with_lower_ceiling_and_one_review():
    report = _evaluate(
        changed_paths=["docs/plans/X.md"],
        diff_lines=299,
        approved_reviews=[{"login": "codex", "state": "APPROVED", "body": ""}],
    )
    assert report["tier"] == "tier0"
    assert report["passed"] is True
    report = _evaluate(changed_paths=["docs/plans/X.md"], diff_lines=301)
    assert report["passed"] is False


def test_review_quorum_requires_distinct_families_from_author():
    report = _evaluate(approved_reviews=[{"login": "codex", "state": "APPROVED", "body": ""}])
    assert report["passed"] is False
    assert any("decorrelated" in v for v in report["violations"])
    # Copilot reviewing a Copilot-authored PR does not count.
    report = _evaluate(
        author="Copilot",
        approved_reviews=[
            {"login": "copilot", "state": "APPROVED", "body": ""},
            {"login": "codex", "state": "APPROVED", "body": ""},
        ],
    )
    assert report["passed"] is False


def test_test_deletion_needs_named_signoff():
    diff = "-    def test_removed_one(self):\n-    def test_removed_two(self):\n"
    report = _evaluate(diff_text=diff)
    assert report["passed"] is False
    assert any("test deletions" in v for v in report["violations"])
    report = _evaluate(
        diff_text=diff,
        approved_reviews=[
            {"login": "codex", "state": "APPROVED",
             "body": "removing test_removed_one and test_removed_two: superseded"},
            {"login": "copilot", "state": "APPROVED",
             "body": "sign-off on test_removed_one, test_removed_two"},
        ],
    )
    assert report["passed"] is True


def test_rate_limit_blocks_at_twenty():
    assert _evaluate(merged_last_24h=20)["passed"] is False
    assert _evaluate(merged_last_24h=19)["passed"] is True


def test_canary_sandbox_is_never_mergeable_unattended():
    report = _evaluate(labels=["canary-sandbox", "bot-pr"])
    assert report["passed"] is False
    report = _evaluate(labels=["canary-sandbox"], is_draft=True)
    assert report["passed"] is False


def test_policy_file_pins():
    assert POLICY["rate_limit_automerges_per_day"] == 20
    assert POLICY["confirmation_token_prefix"] == "automerge-policy-pass-"
    assert POLICY["tiers"]["tier0"]["max_diff_lines"] == 300
    assert POLICY["tiers"]["tier1"]["max_diff_lines"] == 600
    assert POLICY["tiers"]["tier2"]["merge"] == "operator_hand_merge_forever"


def test_workflow_contract():
    doc = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "automerge-tier-policy.yml").read_text()
    )
    triggers = doc.get("on", doc.get(True))
    assert set(triggers) == {"pull_request"}
    assert "labeled" in triggers["pull_request"]["types"]
    job = doc["jobs"]["tier-policy"]
    assert job["name"] == "Automerge tier policy"
    checkout = job["steps"][0]
    assert "ref" in checkout["with"], "policy must load from the trusted default branch"


def test_confirmation_token_is_honest_everywhere():
    """§0 token verdict: merge-pr-N claimed operator consent CI synthesized.

    The live sites must all use automerge-policy-pass-N; the old token may
    survive only inside an explanatory comment in pr_merge_control.py.
    """
    control = (REPO_ROOT / "scripts" / "runtime" / "pr_merge_control.py").read_text()
    assert 'f"automerge-policy-pass-{args.pr}"' in control
    live_lines = [
        line for line in control.splitlines()
        if "merge-pr-" in line and not line.lstrip().startswith("#")
    ]
    assert live_lines == [], f"old token still live in pr_merge_control.py: {live_lines}"
    router = (REPO_ROOT / ".github" / "workflows" / "codex-mention-router.yml").read_text()
    assert "automerge-policy-pass-${PR_NUMBER}" in router
    assert "merge-pr-${PR_NUMBER}" not in router
    assert POLICY["confirmation_token_prefix"] == "automerge-policy-pass-"
