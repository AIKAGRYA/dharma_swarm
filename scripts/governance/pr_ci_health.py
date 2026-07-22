#!/usr/bin/env python3
"""Read-only PR CI-health triage for dharma_swarm.

Enumerates open pull requests, pulls each PR's check runs and mergeable state,
and classifies every non-green PR into actionable categories. This module never
mutates git history or PRs; it only reads and reports.

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

DEFAULT_REPO = "AmitabhainArunachala/dharma_swarm"

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


@dataclass
class PRTriage:
    number: int
    title: str
    base: str
    head: str
    draft: bool
    author: str
    mergeable_state: str
    failing_checks: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)

    @property
    def actionable(self) -> bool:
        return any(category not in {"green", "draft"} for category in self.categories)


def _have_gh() -> bool:
    return shutil.which("gh") is not None


def _gh_json(args: list[str]) -> object:
    proc = subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True
    )
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


def classify_pr(pr: dict, check_runs: list[dict]) -> PRTriage:
    """Pure classification from a PR payload + its head-commit check runs."""
    triage = PRTriage(
        number=int(pr["number"]),
        title=str(pr.get("title", "")),
        base=str(pr.get("base", {}).get("ref", "")),
        head=str(pr.get("head", {}).get("ref", "")),
        draft=bool(pr.get("draft", False)),
        author=str(pr.get("user", {}).get("login", "")),
        mergeable_state=str(pr.get("mergeable_state", "unknown")),
    )

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
    if state == "behind":
        categories.append("behind_main")
    elif state == "dirty":
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
        rows.append(classify_pr(detail, runs))
    return rows


def render_markdown(rows: list[PRTriage]) -> str:
    rows_sorted = sorted(rows, key=lambda r: (not r.actionable, r.number))
    lines = [
        "| PR | draft | base | mergeable | categories | failing checks |",
        "|---:|:-----:|:-----|:----------|:-----------|:---------------|",
    ]
    for r in rows_sorted:
        checks = ", ".join(r.failing_checks) if r.failing_checks else "—"
        lines.append(
            f"| #{r.number} | {'yes' if r.draft else 'no'} | `{r.base}` | "
            f"{r.mergeable_state} | {', '.join(r.categories)} | {checks} |"
        )
    actionable = sum(1 for r in rows if r.actionable)
    green = sum(1 for r in rows if r.categories == ["green"])
    never_ran = sum(1 for r in rows if "ci_never_ran" in r.categories)
    lines.append("")
    summary = f"**{len(rows)} open PRs — {green} green, {actionable} actionable"
    if never_ran:
        summary += (
            f", {never_ran} ci_never_ran (zero check runs on head — "
            "CI-stranded, never green)"
        )
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
        print(
            json.dumps([r.__dict__ for r in rows], indent=2, sort_keys=True)
        )
    else:
        print(render_markdown(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
