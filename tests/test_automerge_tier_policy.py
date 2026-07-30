"""Door policy guard: pure-evaluation tests + policy-file pins (PR-A)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "runtime"))

import check_automerge_tier_policy as guard  # noqa: E402

POLICY = json.loads(
    (REPO_ROOT / "scripts" / "governance" / "automerge_tier_policy.json").read_text()
)

# The REAL trusted reviewer-App logins (TRUSTED_REVIEW_LOGINS,
# scripts/runtime/pr_merge_control.py) — synthetic short names here once hid
# that the matcher could never match production logins (Devin on PR #1160).
CODEX = "chatgpt-codex-connector[bot]"
COPILOT = "copilot-pull-request-reviewer[bot]"


def _evaluate(**overrides):
    base = dict(
        labels=["bot-pr"],
        is_draft=False,
        changed_paths=["dharma_swarm/foo.py", "tests/test_foo.py"],
        diff_lines=100,
        diff_text="",
        approved_reviews=[
            {"login": CODEX, "state": "APPROVED", "body": ""},
            {"login": COPILOT, "state": "APPROVED", "body": ""},
        ],
        author="devin-ai-integration[bot]",
        merged_last_24h=0,
        policy=POLICY,
    )
    base.update(overrides)
    return guard.evaluate(**base)


def _rest_review(login, state, commit="headsha", submitted="t1", body=""):
    return {
        "user": {"login": login},
        "state": state,
        "commit_id": commit,
        "submitted_at": submitted,
        "body": body,
    }


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
        # Executable implementations behind required CI contexts (Codex on
        # PR #1160): freezing the workflow YAML alone left the scripts the
        # workflows delegate their verdicts to amendable at tier 1.
        "scripts/governance/check_pr_coherence_delta.py",
        "scripts/docops/check_docops_integrity.py",
        "scripts/governance/hygiene/check_hygiene_integrity.py",
        "scripts/governance/check_track_status.py",
        "scripts/governance/render_active_track_includes.py",
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
        approved_reviews=[{"login": CODEX, "state": "APPROVED", "body": ""}],
    )
    assert report["tier"] == "tier0"
    assert report["passed"] is True
    report = _evaluate(changed_paths=["docs/plans/X.md"], diff_lines=301)
    assert report["passed"] is False


def test_review_quorum_requires_distinct_families_from_author():
    report = _evaluate(approved_reviews=[{"login": CODEX, "state": "APPROVED", "body": ""}])
    assert report["passed"] is False
    assert any("decorrelated" in v for v in report["violations"])
    # Copilot reviewing a Copilot-authored PR does not count.
    report = _evaluate(
        author="Copilot",
        approved_reviews=[
            {"login": COPILOT, "state": "APPROVED", "body": ""},
            {"login": CODEX, "state": "APPROVED", "body": ""},
        ],
    )
    assert report["passed"] is False


def test_reviewer_families_mirror_trusted_review_logins():
    """Policy identities must stay in lockstep with Mike's trust table —
    the two guards share one trust boundary."""
    import pr_merge_control  # noqa: PLC0415

    trusted = set().union(*pr_merge_control.TRUSTED_REVIEW_LOGINS.values())
    assert set(POLICY["reviewer_families"]) == trusted


def test_lookalike_logins_never_qualify():
    """Prefix/short-name matching admitted spoofable accounts and missed the
    real App logins; only exact trusted logins qualify."""
    report = _evaluate(
        approved_reviews=[
            {"login": "codex", "state": "APPROVED", "body": ""},
            {"login": "copilot", "state": "APPROVED", "body": ""},
            {"login": "chatgpt-codex-connector", "state": "APPROVED", "body": ""},
            {"login": "codex-reviewer[bot]", "state": "APPROVED", "body": ""},
        ]
    )
    assert report["qualifying_reviews"] == []
    assert report["passed"] is False


def test_latest_approvals_pins_to_head_sha():
    rows = guard.latest_approvals(
        [
            _rest_review(CODEX, "APPROVED", commit="stale"),
            _rest_review(COPILOT, "APPROVED", commit="headsha"),
        ],
        "headsha",
    )
    assert [r["login"] for r in rows] == [COPILOT]
    # No head identity at all qualifies nothing (fail closed).
    assert guard.latest_approvals([_rest_review(CODEX, "APPROVED", commit="")], "") == []


def test_latest_approvals_state_transitions():
    # A later COMMENTED review does not erase a standing approval; a later
    # CHANGES_REQUESTED does; a DISMISSED approval never counts.
    rows = guard.latest_approvals(
        [
            _rest_review(COPILOT, "APPROVED", submitted="t1"),
            _rest_review(COPILOT, "COMMENTED", submitted="t2"),
            _rest_review(CODEX, "APPROVED", submitted="t1"),
            _rest_review(CODEX, "CHANGES_REQUESTED", submitted="t2"),
            _rest_review("other[bot]", "DISMISSED", submitted="t1"),
        ],
        "headsha",
    )
    assert [r["login"] for r in rows] == [COPILOT]


def test_assume_unattended_binds_unlabeled_and_draft_prs():
    """The router's arming path must not see 'unlabeled -> policy does not
    bind' — that was the token-synthesis bypass."""
    report = _evaluate(
        labels=[],
        is_draft=True,
        assume_unattended=True,
        changed_paths=[".github/workflows/automerge.yml"],
    )
    assert report["passed"] is False
    assert report["tier2_hits"] == [".github/workflows/automerge.yml"]


def test_test_deletion_needs_named_signoff():
    diff = "-    def test_removed_one(self):\n-    def test_removed_two(self):\n"
    report = _evaluate(diff_text=diff)
    assert report["passed"] is False
    assert any("test deletions" in v for v in report["violations"])
    report = _evaluate(
        diff_text=diff,
        approved_reviews=[
            {"login": CODEX, "state": "APPROVED",
             "body": "removing test_removed_one and test_removed_two: superseded"},
            {"login": COPILOT, "state": "APPROVED",
             "body": "sign-off on test_removed_one, test_removed_two"},
        ],
    )
    assert report["passed"] is True


def test_untrusted_approval_cannot_sign_off_test_deletion():
    """An APPROVED review from an arbitrary account naming the deleted tests
    is not a sign-off — only trusted reviewer identities authorize deletions."""
    diff = "-def test_removed(self):\n"
    report = _evaluate(
        diff_text=diff,
        approved_reviews=[
            {"login": CODEX, "state": "APPROVED", "body": ""},
            {"login": COPILOT, "state": "APPROVED", "body": ""},
            {"login": "rando", "state": "APPROVED",
             "body": "sign-off on test_removed"},
        ],
    )
    assert report["passed"] is False
    assert any("test deletions" in v for v in report["violations"])


def test_async_test_deletions_are_detected():
    diff = "-async def test_gone():\n-    async def test_inner_gone(self):\n"
    assert guard.deleted_tests(diff) == ["test_gone", "test_inner_gone"]


def test_rate_limit_count_dedupes_dual_labeled_prs():
    rows_automerge = [{"number": i} for i in range(1, 11)]
    rows_bot_pr = [{"number": i} for i in range(5, 15)]
    assert guard.count_unique_merged([rows_automerge, rows_bot_pr]) == 14


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
    # pull_request_review keeps a required red check from going stale once
    # the quorum's approvals arrive (they are not pull_request activity).
    assert set(triggers) == {"pull_request", "pull_request_review"}
    assert "labeled" in triggers["pull_request"]["types"]
    assert set(triggers["pull_request_review"]["types"]) == {
        "submitted", "edited", "dismissed",
    }
    job = doc["jobs"]["tier-policy"]
    assert job["name"] == "Automerge tier policy"
    checkout = job["steps"][0]
    assert "ref" in checkout["with"], "policy must load from the trusted default branch"
    bootstrap, evaluate = job["steps"][1], job["steps"][2]
    assert bootstrap["id"] == "bootstrap", "introducing-PR bootstrap case must exist"
    assert "check_automerge_tier_policy.py" in bootstrap["run"]
    assert evaluate["if"] == "steps.bootstrap.outputs.bootstrap == 'false'", (
        "real evaluation must be gated on the policy existing on the default branch"
    )


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


def test_router_runs_binding_evaluation_before_arming_token():
    """The token is a policy verdict, not a spelling: the router must run
    the evaluator in --assume-unattended mode before the merge command ever
    sees the token (Codex review on PR #1160)."""
    router = (REPO_ROOT / ".github" / "workflows" / "codex-mention-router.yml").read_text()
    gate_at = router.index("--assume-unattended")
    token_at = router.index("automerge-policy-pass-${PR_NUMBER}")
    assert gate_at < token_at, "evaluator gate must precede the armed token"
    assert "check_automerge_tier_policy.py" in router
