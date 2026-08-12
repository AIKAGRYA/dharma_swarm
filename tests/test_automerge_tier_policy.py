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
        title="chore: routine housekeeping",
        changed_paths=["dharma_swarm/foo.py", "tests/test_foo.py"],
        diff_lines=100,
        diff_text="",
        approved_reviews=[
            {"login": CODEX, "state": "APPROVED", "body": ""},
            {"login": COPILOT, "state": "APPROVED", "body": ""},
        ],
        ai_evidence=[
            {
                "id": 1,
                "login": CODEX,
                "state": "APPROVED",
                "body": "",
                "head_sha": "a" * 40,
            }
        ],
        operator_warrants=[
            {
                "kind": "github_review",
                "id": 77,
                "actor": "amitabhainarunachala",
                "head_sha": "a" * 40,
            }
        ],
        repo="owner/repo",
        pr=12,
        head_sha="a" * 40,
        base_sha="b" * 40,
        base_ref="main",
        author="devin-ai-integration[bot]",
        merged_last_24h=0,
        policy=POLICY,
    )
    base.update(overrides)
    return guard.evaluate(**base)


def _rest_review(login, state, commit="headsha", submitted="t1", body="", review_id=1):
    return {
        "id": review_id,
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
    assert report["authority_class"] == "code"
    assert report["authorization_evidence"]["operator_warrant"]["id"] == 77
    assert report["authorization_evidence"]["actuation_eligible"] is False


def test_tier2_with_quorum_remains_operator_only():
    """Review quantity cannot promote a referee path into Mike authority."""
    report = _evaluate(changed_paths=[".github/workflows/automerge.yml"])
    assert report["tier"] == "tier2"
    assert report["tier2_hits"] == [".github/workflows/automerge.yml"]
    assert report["authority_class"] == "operator_only"
    assert report["passed"] is False
    assert report["authorization_evidence"] is None


def test_tier2_without_quorum_fails():
    report = _evaluate(
        changed_paths=[".github/workflows/automerge.yml"],
        approved_reviews=[{"login": CODEX, "state": "APPROVED", "body": ""}],
    )
    assert report["passed"] is False
    assert any("operator-only authority class" in v for v in report["violations"])


def test_tier2_diff_ceiling_is_400():
    assert _evaluate(
        changed_paths=[".github/workflows/automerge.yml"], diff_lines=401
    )["passed"] is False
    report = _evaluate(
        changed_paths=[".github/workflows/automerge.yml"], diff_lines=400
    )
    assert report["passed"] is False
    assert not any("ceiling" in violation for violation in report["violations"])


def test_tier2_path_on_never_auto_floor_stays_operator_only():
    """A referee path carrying a NEVER_AUTO substring is the hard floor —
    no quorum admits it."""
    report = _evaluate(
        changed_paths=["docs/ops/loop_control/delete_stale_lane.md"],
    )
    assert report["tier"] == "tier2"
    assert report["passed"] is False
    assert any("operator-only authority class" in v for v in report["violations"])


def test_reversibility_floor_blocks_operator_only_title_at_every_tier():
    """The declared intent is gate-classified; never-auto / CRITICAL
    vocabulary bars the unattended lane even at tier1 with a full quorum."""
    report = _evaluate(title="rotate production credentials")
    assert report["passed"] is False
    assert any("reversibility floor" in v for v in report["violations"])
    assert report["reversibility"]["action_class"] == "operator_only"


def test_reversibility_floor_admits_high_risk_verbs():
    """HIGH-risk verbs (deploy/migrate/merge) describe reviewed content; a
    reviewed git merge is single-revert reversible, so the quorum stands in
    for the lease — only OPERATOR_ONLY blocks."""
    report = _evaluate(title="refactor: migrate tests to pytest fixtures")
    assert report["reversibility"]["action_class"] == "irreversible"
    assert report["passed"] is True


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
        # 2026-07-30 door: the floor's own implementations are referee
        # surfaces too — a tier-1 PR must not be able to rewrite the
        # denylist the tier-2 door trusts.
        "docs/ops/OPERATOR_RULING_2026-07-30_SARATHI_AUTONOMY_CEILING.md",
        "dharma_swarm/operator_core/reversibility_gate.py",
        "dharma_swarm/operator_core/autonomy_dial.py",
        "dharma_swarm/risk_patterns.py",
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


def test_code_requires_current_head_trusted_ai_evidence():
    report = _evaluate(approved_reviews=[], ai_evidence=[])
    assert report["passed"] is False
    assert any("current-head trusted AI" in v for v in report["violations"])
    # Trusted AI is evidence, not operator identity. Same-family evidence may
    # prove a review ran but cannot replace the separate operator warrant.
    report = _evaluate(
        author="Copilot",
        approved_reviews=[{"login": COPILOT, "state": "APPROVED", "body": ""}],
        ai_evidence=[
            {
                "id": 2,
                "login": COPILOT,
                "state": "APPROVED",
                "body": "",
                "head_sha": "a" * 40,
            }
        ],
        operator_warrants=[],
    )
    assert report["passed"] is False
    assert any("operator warrant" in v for v in report["violations"])


def test_stale_ai_evidence_and_untrusted_warrant_fail_pure_evaluation():
    report = _evaluate(
        ai_evidence=[
            {
                "id": 1,
                "login": CODEX,
                "state": "COMMENTED",
                "head_sha": "stale",
            }
        ],
        operator_warrants=[
            {
                "kind": "issue_comment",
                "id": 2,
                "actor": "AmitabhainArunachala-lookalike",
                "head_sha": "a" * 40,
            }
        ],
    )
    assert report["passed"] is False
    assert any("current-head trusted AI" in row for row in report["violations"])
    assert any("operator warrant" in row for row in report["violations"])


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
        ],
        ai_evidence=[
            {"id": 1, "login": "codex", "state": "APPROVED", "head_sha": "a" * 40},
            {"id": 2, "login": "copilot", "state": "APPROVED", "head_sha": "a" * 40},
        ],
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
    # A dismissal surfacing as a separate later row (rather than mutating the
    # original review's state) must still clear the standing approval.
    rows = guard.latest_approvals(
        [
            _rest_review(CODEX, "APPROVED", submitted="t1"),
            _rest_review(CODEX, "DISMISSED", submitted="t2"),
        ],
        "headsha",
    )
    assert rows == []


def test_commented_ai_review_is_evidence_not_operator_authority():
    rows = guard.latest_ai_evidence(
        [_rest_review(CODEX, "COMMENTED", commit="headsha")],
        "headsha",
        POLICY,
    )
    assert [(row["login"], row["state"]) for row in rows] == [
        (CODEX, "COMMENTED")
    ]
    report = _evaluate(
        approved_reviews=[],
        ai_evidence=rows,
        head_sha="headsha",
        operator_warrants=[],
    )
    assert report["passed"] is False
    assert any("operator warrant" in violation for violation in report["violations"])


def test_operator_warrant_is_native_exact_identity_and_current_head():
    reviews = [
        _rest_review(
            "AmitabhainArunachala-lookalike", "APPROVED", commit="a" * 40,
            review_id=1,
        ),
        _rest_review(
            "AmitabhainArunachala", "APPROVED", commit="b" * 40, review_id=2,
        ),
        _rest_review(
            "AmitabhainArunachala", "APPROVED", commit="a" * 40, review_id=3,
        ),
    ]
    warrants = guard.qualifying_operator_warrants(reviews, "a" * 40, POLICY)
    assert warrants == [
        {
            "kind": "github_review",
            "id": 3,
            "actor": "amitabhainarunachala",
            "head_sha": "a" * 40,
        }
    ]


def test_operator_warrant_is_cleared_by_later_changes_requested():
    reviews = [
        _rest_review(
            "AmitabhainArunachala", "APPROVED", commit="a" * 40,
            submitted="t1", review_id=1,
        ),
        _rest_review(
            "AmitabhainArunachala", "CHANGES_REQUESTED", commit="a" * 40,
            submitted="t2", review_id=2,
        ),
    ]
    assert guard.qualifying_operator_warrants(reviews, "a" * 40, POLICY) == []


def test_docs_governance_is_not_docs_low():
    report = _evaluate(changed_paths=["docs/governance/policy.md"])
    assert report["authority_class"] == "operator_only"
    assert report["passed"] is False


def test_agent_instruction_and_nested_control_paths_are_operator_only():
    for path in (
        "docs/AGENTS.md",
        ".agents/skills/testing-governance-gates/SKILL.md",
        "mode_pack/claude/autonomous-build/SKILL.md",
        "docs/agents/reviewer/SOUL.md",
        "docs/agent_tasks/review_prompt.md",
        "service/.env.production",
        "service/infra/prod.tf",
        "service/deploy/prod.yml",
        "credentials/token.txt",
        "secrets/key.txt",
        "SKILL.md",
        "SOUL.md",
        "LIVE_FIRE_PROMPT.md",
    ):
        report = _evaluate(changed_paths=[path])
        assert report["authority_class"] == "operator_only", path
        assert report["passed"] is False


def test_protected_path_rename_checks_old_and_new_names():
    report = _evaluate(
        changed_paths=["docs/benign.md", "docs/ops/authority.md"],
        file_changes=[
            {
                "status": "renamed",
                "filename": "docs/benign.md",
                "previous_filename": "docs/ops/authority.md",
            }
        ],
    )
    assert report["authority_class"] == "operator_only"
    assert report["passed"] is False


def test_removed_non_python_tests_and_unsafe_git_modes_are_operator_only():
    removed = _evaluate(
        changed_paths=["web/foo.test.ts"],
        file_changes=[{"status": "removed", "filename": "web/foo.test.ts"}],
    )
    assert removed["authority_class"] == "operator_only"
    for header in (
        "new file mode 100755",
        "new file mode 120000",
        "new file mode 160000",
    ):
        report = _evaluate(changed_paths=["docs/guide.md"], diff_text=header)
        assert report["authority_class"] == "operator_only", header


def test_security_migration_and_secret_paths_are_operator_only():
    for path in (
        "dharma_swarm/security/auth.py",
        "db/migrations/0042_rotate_keys.sql",
        "infra/deploy.yaml",
        "service/secrets/loader.py",
        ".env.production",
    ):
        report = _evaluate(changed_paths=[path])
        assert report["authority_class"] == "operator_only", path
        assert report["passed"] is False


def test_evidence_digest_binds_repo_head_base_ref_policy_and_intent():
    report = _evaluate()
    evidence = report["authorization_evidence"]
    assert evidence["repo"] == "owner/repo"
    assert evidence["head_sha"] == "a" * 40
    assert evidence["base_sha"] == "b" * 40
    assert evidence["base_ref"] == "main"
    assert evidence["policy_sha256"] == guard.policy_digest(POLICY)
    assert evidence["provenance"] == "unsigned-github-snapshot"
    assert evidence["actuation_eligible"] is False
    digest = evidence.pop("digest")
    assert digest == guard.canonical_digest(evidence)


def test_assume_unattended_binds_unlabeled_and_draft_prs():
    """The router's arming path must not see 'unlabeled -> policy does not
    bind' — that was the token-synthesis bypass."""
    report = _evaluate(
        labels=[],
        is_draft=True,
        assume_unattended=True,
        changed_paths=[".github/workflows/automerge.yml"],
        approved_reviews=[],
    )
    assert report["labeled_for_unattended"] is True
    assert report["tier2_hits"] == [".github/workflows/automerge.yml"]
    assert report["passed"] is False
    assert any("operator-only authority class" in v for v in report["violations"])


def test_test_deletion_is_operator_only_even_with_named_ai_signoff():
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
    assert report["passed"] is False
    assert report["authority_class"] == "operator_only"


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


def test_mutable_label_rate_count_is_advisory_not_authority():
    report = _evaluate(merged_last_24h=20)
    assert report["passed"] is True
    assert "mutable and non-atomic" in report["rate_limit_advisory"]


def test_canary_sandbox_is_never_mergeable_unattended():
    report = _evaluate(labels=["canary-sandbox", "bot-pr"])
    assert report["passed"] is False
    report = _evaluate(labels=["canary-sandbox"], is_draft=True)
    assert report["passed"] is False


def test_policy_file_pins():
    assert POLICY["schema"] == "dharma.automerge_tier_policy.v3"
    assert POLICY["rate_observation_advisory_per_day"] == 20
    assert POLICY["confirmation_token_prefix"] == "automerge-policy-pass-"
    assert POLICY["tiers"]["tier0"]["max_diff_lines"] == 300
    assert POLICY["tiers"]["tier1"]["max_diff_lines"] == 600
    assert POLICY["tiers"]["tier2"]["merge"] == "operator_only"
    assert POLICY["tiers"]["tier2"]["max_diff_lines"] == 400
    assert POLICY["authority_policy"]["actuation_enabled"] is False
    assert POLICY["authority_policy"]["classes"]["docs_low"]["candidate_for_unattended"] is True
    assert POLICY["authority_policy"]["classes"]["code"]["operator_warrant"] is True
    assert POLICY["authority_policy"]["classes"]["operator_only"]["candidate_for_unattended"] is False
    dial = POLICY["autonomy_dial"]
    assert dial["env"] == "DGC_SARATHI_AUTONOMY"
    assert dial["levels"] == ["shadow", "propose", "dispatch", "full"]
    assert dial["default"] == "propose"
    assert dial["invalid_value_behavior"] == "shadow"


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


def test_router_passes_typed_permit_to_gate_and_merge_and_disarms_backlog():
    router = (REPO_ROOT / ".github/workflows/codex-mention-router.yml").read_text()
    evaluator_at = router.index("--output \"${authorization_report}\"")
    gate_at = router.index("gate \\")
    merge_at = router.index("merge \\")
    assert evaluator_at < gate_at < merge_at
    assert router.count('--merge-authorization "${authorization_report}"') == 2
    backlog_block = router[router.index('if [ "${BACKLOG_REQUESTED}"') : gate_at]
    assert "merge_mode=off" in backlog_block
    assert "merge_mode=auto-when-clean" not in backlog_block
    assert "--human-approved" not in router
    assert "merge-master-mike-pr-${{" in router
    assert "cancel-in-progress: true" in router


def test_same_family_ai_cannot_promote_test_deletion():
    """No AI review, same-family or otherwise, promotes a deletion out of
    the operator-only class."""
    diff = "-def test_removed(self):\n"
    report = _evaluate(
        author="Copilot",
        diff_text=diff,
        approved_reviews=[
            {"login": CODEX, "state": "APPROVED", "body": ""},
            {"login": COPILOT, "state": "APPROVED",
             "body": "sign-off on test_removed"},
        ],
    )
    assert any("test deletions" in v for v in report["violations"])


def test_fetch_all_pages_concatenates_and_fails_closed(monkeypatch):
    """A 100-row page must trigger a next-page fetch (a truncated file list
    could hide a tier-2 path at position 101); any failed page fails the
    whole fetch (Greptile P1 on PR #1160)."""
    pages = {
        1: [{"filename": f"f{i}"} for i in range(100)],
        2: [{"filename": "scripts/runtime/pr_merge_control.py"}],
    }

    def fake(args):
        query = args[-1]
        page = int(query.rsplit("page=", 1)[-1])
        return pages.get(page)

    monkeypatch.setattr(guard, "_gh_json", fake)
    rows = guard._fetch_all_pages("repos/o/r/pulls/1/files")
    assert rows is not None and len(rows) == 101
    assert rows[-1]["filename"] == "scripts/runtime/pr_merge_control.py"
    # A failed second page fails the whole fetch, never a silent 100-row cap.
    monkeypatch.setattr(
        guard, "_gh_json",
        lambda args: pages[1] if args[-1].endswith("page=1") else None,
    )
    assert guard._fetch_all_pages("repos/o/r/pulls/1/files") is None
