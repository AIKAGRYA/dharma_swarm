#!/usr/bin/env python3
"""Read-only PR CI-health triage for dharma_swarm.

Enumerates open pull requests, pulls each PR's check runs, mergeable state,
review decision, and unresolved review conversations, then classifies every
non-green PR into actionable categories. This module never mutates git history
or PRs; it only reads and reports.

Consumers:
- ``.github/workflows/pr-ci-health.yml`` (hourly cron). GitHub runners ship the
  ``gh`` CLI and a ``GITHUB_TOKEN``, so the ``gh``-backed collection path works
  there.
- the ``/pr-ci-health`` agent playbook. In an interactive session ``gh`` may be
  absent; the agent gathers PR data via the GitHub MCP tools instead, but reuses
  the :func:`classify_pr` logic below so classification stays consistent.

Categories (one PR may carry several):
- ``green``           — positive evidence only: at least one check run concluded
                        ``success`` on the head SHA, none failing, the PR is not
                        draft, and mergeability is known and non-blocking. Never
                        assigned by fallback.
- ``draft``           — checks may be healthy, but the PR remains intentionally
                        non-merge-ready. A draft alone is not actionable; any
                        accompanying failure/blocker remains actionable.
- ``ci_never_ran``    — the head SHA has ZERO check runs. This is the bot-rebase
                        stranding signature (GITHUB_TOKEN pushes never trigger
                        workflows). Fail-closed: actionable, never green.
- ``ci_pending``      — check runs exist but none has concluded ``success`` yet
                        (queued/in-progress). Fail-closed placeholder that
                        replaced the old zero-categories→green fallback.
- ``merge_blocked``   — GitHub reports mergeable_state ``blocked`` (required
                        checks missing/failing or required review absent).
                        Previously unhandled, which fail-opened to green.
- ``unresolved_threads`` — one or more review conversations are unresolved;
                           includes outdated threads because branch protection
                           does not waive them automatically.
- ``review_required`` — GitHub's review decision still requires an approval.
- ``changes_requested`` — a submitted review requests changes.
- ``review_state_unknown`` — review-thread state could not be read or was not
                             bound to the same head SHA. Never treated as green
                             by the hosted collector.
- ``policy_blocker_unidentified`` — checks, conversations, and review decision
                                    do not explain GitHub's blocked state.
- ``merge_unknown``   — GitHub has not computed a trustworthy merge state yet.
                        Unknown state is never positive merge-readiness evidence.
- ``behind_main``     — branch is behind base; needs a clean rebase.
- ``merge_conflict``  — branch conflicts with base; needs human/author attention.
- ``docops_drift``    — DocOps integrity gate failed (count drift).
- ``coherence_delta`` — Coherence Delta PR-body gate failed.
- ``fourfold_warrant``— Fourfold Shakti Warrant gate held/blocked.
- ``transient_infra`` — umbrella status (e.g. CodeQL default-setup) flaked while
                        the real job passed; re-run, do not edit code.
- ``real_test_lint``  — a genuine test/lint/build job failed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

DEFAULT_REPO = "AIKAGRYA/dharma_swarm"

# Failing check name -> governance category.
GATE_MAP = {
    "Coherence Delta PR body": "coherence_delta",
    "Fourfold Shakti Warrant": "fourfold_warrant",
    "DocOps integrity gate": "docops_drift",
}

# Umbrella statuses that complete in seconds and flake independently of code.
# We only treat them as transient when their real underlying job succeeded.
UMBRELLA_TRANSIENT = {
    "CodeQL": "codeql / python",
    "Semgrep OSS": "semgrep",
}

REVIEW_GATE_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      headRefOid
      reviewDecision
      reviewThreads(first: 100, after: $after) {
        nodes {
          isResolved
          isOutdated
          path
          comments(first: 1) {
            nodes { author { login } }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
""".strip()


@dataclass
class PRTriage:
    number: int
    title: str
    base: str
    head: str
    draft: bool
    author: str
    mergeable_state: str
    # Commits on the base branch that the head does not contain, from the
    # compare API. -1 means "not measured" (the pure-classification path);
    # it never implies "up to date".
    behind_by: int = -1
    review_decision: str = "NOT_COLLECTED"
    review_state_known: bool = False
    unresolved_threads: int = -1
    outdated_unresolved_threads: int = -1
    unresolved_thread_paths: list[str] = field(default_factory=list)
    unresolved_thread_authors: list[str] = field(default_factory=list)
    review_state_error: str = ""
    failing_checks: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)

    @property
    def actionable(self) -> bool:
        return any(category not in {"green", "draft"} for category in self.categories)


@dataclass
class ReviewGateState:
    """Exact-head review/conversation state read through GitHub GraphQL."""

    review_decision: str
    unresolved_threads: int
    outdated_unresolved_threads: int
    unresolved_thread_paths: list[str] = field(default_factory=list)
    unresolved_thread_authors: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def known(self) -> bool:
        return not self.error and self.unresolved_threads >= 0


def _have_gh() -> bool:
    return shutil.which("gh") is not None


def _gh_json(args: list[str]) -> object:
    proc = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return json.loads(proc.stdout)


def list_open_prs(repo: str) -> list[dict]:
    return list(
        _gh_json(
            [
                "api",
                f"repos/{repo}/pulls?state=open&per_page=100",
                "--paginate",
            ]
        )
    )


def pr_detail(repo: str, number: int) -> dict:
    return dict(_gh_json(["api", f"repos/{repo}/pulls/{number}"]))


def commit_check_runs(repo: str, sha: str) -> list[dict]:
    payload = _gh_json(["api", f"repos/{repo}/commits/{sha}/check-runs?per_page=100"])
    if isinstance(payload, dict):
        return list(payload.get("check_runs", []))
    return []


def compare_behind_by(repo: str, base_ref: str, head_sha: str) -> int:
    """Commits on *base_ref* that *head_sha* does not contain.

    `mergeable_state` cannot answer this. It is a SINGLE value with a
    precedence order, and "blocked" (a required check missing or failing)
    outranks "behind" — so a PR that is both behind main and waiting on CI
    reports `blocked`, and a rebase pass keyed on `mergeable_state ==
    "behind"` silently skipped it. On this repo nearly every behind-main PR
    is also blocked or unstable, which is why the auto-rebase looked
    healthy while the operator still had to press "Update branch" by hand.

    The compare API answers the question directly and independently of
    merge state. -1 on any read failure: unknown is never "up to date".
    """
    try:
        payload = _gh_json(["api", f"repos/{repo}/compare/{base_ref}...{head_sha}"])
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        return -1
    if not isinstance(payload, dict) or "behind_by" not in payload:
        return -1
    try:
        return int(payload["behind_by"])
    except (TypeError, ValueError):
        return -1


def _unknown_review_gate(error: str) -> ReviewGateState:
    return ReviewGateState(
        review_decision="UNKNOWN",
        unresolved_threads=-1,
        outdated_unresolved_threads=-1,
        error=error.replace("\n", " ")[:240],
    )


def fetch_review_gate_state(
    repo: str,
    number: int,
    *,
    expected_head_sha: str,
) -> ReviewGateState:
    """Read review decision and all unresolved conversations for one head.

    Review threads are GraphQL-only. Pagination and exact-head binding are
    deliberate: a first-page-only answer or a branch move during collection
    must not produce a false zero that labels a blocked PR green.
    """
    owner, separator, name = repo.partition("/")
    if separator != "/" or not owner or not name or "/" in name:
        return _unknown_review_gate(f"invalid repository name: {repo!r}")

    after: str | None = None
    seen_cursors: set[str] = set()
    review_decision = "NONE"
    unresolved = 0
    outdated_unresolved = 0
    paths: set[str] = set()
    authors: set[str] = set()

    try:
        for page_number in range(1, 102):
            args = [
                "api",
                "graphql",
                "-f",
                f"query={REVIEW_GATE_QUERY}",
                "-F",
                f"owner={owner}",
                "-F",
                f"name={name}",
                "-F",
                f"number={number}",
            ]
            if after is not None:
                args.extend(["-f", f"after={after}"])
            payload = _gh_json(args)
            if not isinstance(payload, dict):
                raise ValueError("GraphQL response is not an object")
            if payload.get("errors"):
                raise ValueError("GraphQL response contains errors")
            data = payload.get("data")
            if not isinstance(data, dict):
                raise ValueError("GraphQL data payload is missing")
            repository = data.get("repository")
            if not isinstance(repository, dict):
                raise ValueError("GraphQL repository payload is missing")
            pull_request = repository.get("pullRequest")
            if not isinstance(pull_request, dict):
                raise ValueError("GraphQL pull request payload is missing")
            observed_head = pull_request.get("headRefOid")
            if observed_head != expected_head_sha:
                raise ValueError(
                    "review state head moved: "
                    f"expected {expected_head_sha}, observed {observed_head}"
                )

            decision = pull_request.get("reviewDecision")
            current_decision = "NONE" if decision is None else str(decision)
            if current_decision not in {
                "NONE",
                "APPROVED",
                "CHANGES_REQUESTED",
                "REVIEW_REQUIRED",
            }:
                raise ValueError(f"unknown review decision: {current_decision}")
            if page_number == 1:
                review_decision = current_decision
            elif current_decision != review_decision:
                raise ValueError("review decision changed during pagination")

            connection = pull_request.get("reviewThreads")
            if not isinstance(connection, dict):
                raise ValueError("reviewThreads payload is missing")
            nodes = connection.get("nodes")
            if not isinstance(nodes, list):
                raise ValueError("reviewThreads nodes are missing")
            for node in nodes:
                if not isinstance(node, dict):
                    raise ValueError("review thread node is malformed")
                is_resolved = node.get("isResolved")
                is_outdated = node.get("isOutdated")
                if not isinstance(is_resolved, bool) or not isinstance(
                    is_outdated, bool
                ):
                    raise ValueError("review thread resolution state is malformed")
                if is_resolved:
                    continue
                unresolved += 1
                outdated_unresolved += int(is_outdated)
                path = node.get("path")
                paths.add(str(path) if path else "(unknown path)")
                comments_connection = node.get("comments")
                if not isinstance(comments_connection, dict):
                    raise ValueError("review thread comments payload is missing")
                comments = comments_connection.get("nodes")
                if not isinstance(comments, list):
                    raise ValueError("review thread comments are malformed")
                if comments and isinstance(comments[0], dict):
                    author = comments[0].get("author")
                    if isinstance(author, dict) and author.get("login"):
                        authors.add(str(author["login"]))

            page_info = connection.get("pageInfo")
            if not isinstance(page_info, dict):
                raise ValueError("reviewThreads pageInfo is missing")
            has_next = page_info.get("hasNextPage")
            if not isinstance(has_next, bool):
                raise ValueError("reviewThreads hasNextPage is malformed")
            if not has_next:
                break
            cursor = page_info.get("endCursor")
            if not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
                raise ValueError("reviewThreads pagination cursor is invalid")
            seen_cursors.add(cursor)
            after = cursor
        else:
            raise ValueError("reviewThreads pagination exceeded 101 pages")
    except (
        json.JSONDecodeError,
        OSError,
        subprocess.CalledProcessError,
        TypeError,
        ValueError,
    ) as exc:
        return _unknown_review_gate(f"{type(exc).__name__}: {exc}")

    return ReviewGateState(
        review_decision=review_decision,
        unresolved_threads=unresolved,
        outdated_unresolved_threads=outdated_unresolved,
        unresolved_thread_paths=sorted(paths),
        unresolved_thread_authors=sorted(authors),
    )


def classify_pr(
    pr: dict,
    check_runs: list[dict],
    behind_by: int = -1,
    review_gate: ReviewGateState | None = None,
) -> PRTriage:
    """Pure classification from a PR payload + its head-commit check runs."""
    triage = PRTriage(
        number=int(pr["number"]),
        title=str(pr.get("title", "")),
        base=str(pr.get("base", {}).get("ref", "")),
        head=str(pr.get("head", {}).get("ref", "")),
        draft=bool(pr.get("draft", False)),
        author=str(pr.get("user", {}).get("login", "")),
        mergeable_state=str(pr.get("mergeable_state", "unknown")),
        behind_by=behind_by,
    )
    if review_gate is not None:
        triage.review_decision = review_gate.review_decision
        triage.review_state_known = review_gate.known
        triage.unresolved_threads = review_gate.unresolved_threads
        triage.outdated_unresolved_threads = review_gate.outdated_unresolved_threads
        triage.unresolved_thread_paths = list(review_gate.unresolved_thread_paths)
        triage.unresolved_thread_authors = list(review_gate.unresolved_thread_authors)
        triage.review_state_error = review_gate.error

    # A check name can appear multiple times when a check is re-run. Keep only
    # the most recent run per name (by started_at) so a passing re-run supersedes
    # an earlier failure.
    latest: dict[str, dict] = {}
    for run in check_runs:
        name = str(run.get("name", ""))
        started = str(run.get("started_at") or "")
        prev = latest.get(name)
        if prev is None or started >= str(prev.get("started_at") or ""):
            latest[name] = run
    conclusions = {
        name: str(run.get("conclusion") or run.get("status") or "")
        for name, run in latest.items()
    }
    failing = sorted(
        name
        for name, concl in conclusions.items()
        if concl
        in {
            "failure",
            "timed_out",
            "cancelled",
            "action_required",
            "startup_failure",
            "stale",
        }
    )
    triage.failing_checks = failing

    categories: list[str] = []
    for name in failing:
        if name in GATE_MAP:
            categories.append(GATE_MAP[name])
        elif name in UMBRELLA_TRANSIENT:
            deep_job = UMBRELLA_TRANSIENT[name]
            if conclusions.get(deep_job) == "success":
                categories.append("transient_infra")
            else:
                categories.append("real_test_lint")
        else:
            categories.append("real_test_lint")

    state = triage.mergeable_state
    # behind_by is authoritative and mergeable_state is only a fallback for
    # when it could not be measured (-1). "blocked" outranks "behind" in
    # GitHub's single-value state, so keying on the state hid most behind-main
    # PRs — but the state is also computed asynchronously and goes stale, so a
    # measured behind_by == 0 must not be overridden by a leftover "behind"
    # either. The measurement wins in BOTH directions (Greptile on PR #1178).
    if triage.behind_by > 0 or (triage.behind_by < 0 and state == "behind"):
        categories.append("behind_main")
    if state == "dirty":
        categories.append("merge_conflict")
    elif state == "blocked":
        # GitHub computes "blocked" when required checks are missing/failing
        # or a required review is absent. Left unhandled, a stranded PR
        # (blocked + zero checks) fell through to the green fallback.
        categories.append("merge_blocked")
    elif state == "unknown":
        # Mergeability is computed asynchronously. Until GitHub returns a known
        # state, there is no positive evidence that the head is merge-ready.
        categories.append("merge_unknown")

    if review_gate is not None:
        if not review_gate.known:
            categories.append("review_state_unknown")
        else:
            if triage.unresolved_threads > 0:
                categories.append("unresolved_threads")
            if triage.review_decision == "REVIEW_REQUIRED":
                categories.append("review_required")
            elif triage.review_decision == "CHANGES_REQUESTED":
                categories.append("changes_requested")
            if (
                state == "blocked"
                and not failing
                and bool(latest)
                and all(conclusion == "success" for conclusion in conclusions.values())
                and triage.behind_by == 0
                and triage.unresolved_threads == 0
                and triage.review_decision in {"NONE", "APPROVED"}
            ):
                categories.append("policy_blocker_unidentified")

    if triage.draft or state == "draft":
        categories.append("draft")

    if not latest:
        # ZERO check runs on the head SHA: the bot-rebase stranding signature
        # (GITHUB_TOKEN pushes never trigger workflows). Fail-closed —
        # actionable, never green.
        categories.append("ci_never_ran")

    if not categories:
        # Green requires positive evidence, not absence of failure evidence:
        # at least one check run must have concluded "success". The old
        # `not categories -> green` fallback reported zero-CI PRs as green.
        if any(concl == "success" for concl in conclusions.values()):
            categories = ["green"]
        else:
            categories = ["ci_pending"]

    # de-dup, stable order
    seen: dict[str, None] = {}
    for cat in categories:
        seen.setdefault(cat, None)
    triage.categories = list(seen)
    return triage


def collect(repo: str) -> list[PRTriage]:
    rows: list[PRTriage] = []
    for pr in list_open_prs(repo):
        # The list endpoint omits mergeable_state; fetch per-PR detail.
        detail = pr_detail(repo, int(pr["number"]))
        sha = str(detail.get("head", {}).get("sha", ""))
        runs = commit_check_runs(repo, sha) if sha else []
        base_ref = str(detail.get("base", {}).get("ref", ""))
        behind = compare_behind_by(repo, base_ref, sha) if sha and base_ref else -1
        review_gate = (
            fetch_review_gate_state(
                repo,
                int(pr["number"]),
                expected_head_sha=sha,
            )
            if sha
            else _unknown_review_gate("pull request head SHA is missing")
        )
        rows.append(
            classify_pr(
                detail,
                runs,
                behind_by=behind,
                review_gate=review_gate,
            )
        )
    return rows


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _compact_list(values: list[str], *, limit: int = 3) -> str:
    visible = values[:limit]
    summary = ", ".join(_markdown_cell(value) for value in visible)
    if len(values) > limit:
        summary += f", +{len(values) - limit} more"
    return summary


def _conversation_summary(item: PRTriage) -> str:
    if not item.review_state_known:
        if item.review_decision == "NOT_COLLECTED":
            return "not collected"
        detail = (
            f": {_markdown_cell(item.review_state_error)}"
            if item.review_state_error
            else ""
        )
        return f"unknown{detail}"
    if item.unresolved_threads == 0:
        return "0"
    summary = str(item.unresolved_threads)
    if item.outdated_unresolved_threads:
        summary += f" ({item.outdated_unresolved_threads} outdated)"
    if item.unresolved_thread_paths:
        summary += f"; paths: {_compact_list(item.unresolved_thread_paths)}"
    if item.unresolved_thread_authors:
        summary += f"; authors: {_compact_list(item.unresolved_thread_authors)}"
    return summary


def render_markdown(rows: list[PRTriage]) -> str:
    rows_sorted = sorted(rows, key=lambda row: (not row.actionable, row.number))
    lines = [
        "| PR | draft | base | mergeable | review | unresolved conversations | categories | failing checks |",
        "|---:|:-----:|:-----|:----------|:-------|:-------------------------|:-----------|:---------------|",
    ]
    for item in rows_sorted:
        checks = ", ".join(item.failing_checks) if item.failing_checks else "—"
        conversation_summary = _conversation_summary(item)
        lines.append(
            f"| #{item.number} | {'yes' if item.draft else 'no'} | `{_markdown_cell(item.base)}` | "
            f"{_markdown_cell(item.mergeable_state)} | {_markdown_cell(item.review_decision)} | "
            f"{conversation_summary} | {', '.join(item.categories)} | "
            f"{_markdown_cell(checks)} |"
        )
    actionable = sum(1 for item in rows if item.actionable)
    green = sum(1 for item in rows if item.categories == ["green"])
    never_ran = sum(1 for item in rows if "ci_never_ran" in item.categories)
    conversation_blocked = sum(1 for item in rows if item.unresolved_threads > 0)
    review_unknown = sum(
        1 for item in rows if "review_state_unknown" in item.categories
    )
    lines.append("")
    summary = f"**{len(rows)} open PRs — {green} green, {actionable} actionable"
    if never_ran:
        summary += (
            f", {never_ran} ci_never_ran (zero check runs on head — "
            "CI-stranded, never green)"
        )
    if conversation_blocked:
        summary += f", {conversation_blocked} with unresolved conversations"
    if review_unknown:
        summary += f", {review_unknown} review state unknown"
    summary += ".**"
    lines.append(summary)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a Markdown table."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="No-op flag for clarity; this script is always read-only.",
    )
    args = parser.parse_args(argv)

    if not _have_gh():
        print(
            "gh CLI not available; this collector needs gh + GITHUB_TOKEN "
            "(GitHub Actions). In an interactive session, gather PR data via the "
            "GitHub MCP tools and reuse classify_pr().",
            file=sys.stderr,
        )
        return 0

    rows = collect(args.repo)
    if args.json:
        print(json.dumps([r.__dict__ for r in rows], indent=2, sort_keys=True))
    else:
        print(render_markdown(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
