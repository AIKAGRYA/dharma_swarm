#!/usr/bin/env python3
"""Target finder — scouts GitHub for teams with AI slop and governance gaps.

Searches for public signals of AI-heavy codebases that lack governance:
    - Repos with high copilot/AI commit patterns but no CI gates
    - Repos with bot-authored PRs but no review enforcement
    - Repos with high churn in AI-generated files
    - Open-source projects with agent integrations but no eval framework

Rule: NO AUTONOMOUS SPAM. This script scouts and qualifies targets.
All outreach requires explicit human approval via EconomicSpine.approve_outreach().

Usage::

    # Scout GitHub for targets
    python scripts/revenue/find_targets.py --query "uses:copilot language:python" --max-results 20

    # Scout with specific pain signals
    python scripts/revenue/find_targets.py --pain "ai-slop,no-ci-gates,bot-prs"

    # Qualify existing targets
    python scripts/revenue/find_targets.py --qualify --min-score 0.6
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

# Ensure dharma_swarm is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from dharma_swarm.revenue.spine import (
    EconomicSpine,
    RevenueTarget,
    TargetStatus,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

GITHUB_API = "https://api.github.com"

# Pain signal patterns to look for in repos
PAIN_SIGNAL_PATTERNS: dict[str, str] = {
    "ai_slop": "Large repos with AI-generated code but low test coverage",
    "no_ci_gates": "No branch protection or required status checks",
    "bot_prs": "High volume of bot/copilot-authored PRs without review",
    "no_provenance": "No commit signing, no provenance tracking",
    "high_churn": "Frequent reverts or high file churn in generated code",
    "agent_access": "AI agents with write access but no audit trail",
    "missing_evals": "Agent tooling but no evaluation framework",
}


@dataclass
class GHRepoSignals:
    """Signals extracted from a GitHub repository."""

    full_name: str
    description: str
    stars: int
    open_issues: int
    language: str
    has_ci: bool
    has_branch_protection: bool
    bot_pr_ratio: float
    recent_commit_count: int
    pain_signals: list[str]
    raw_data: dict[str, Any]


def _github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _github_get(endpoint: str) -> Any:
    """Make a GET request to GitHub API with rate-limit awareness."""
    url = f"{GITHUB_API}{endpoint}" if endpoint.startswith("/") else endpoint
    req = Request(url, headers=_github_headers())
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        logger.warning("GitHub API error for %s: %s", endpoint, exc)
        return None


def search_repos(query: str, max_results: int = 20) -> list[dict[str, Any]]:
    """Search GitHub for repos matching query."""
    encoded = quote_plus(query)
    per_page = min(max_results, 30)
    data = _github_get(f"/search/repositories?q={encoded}&sort=stars&per_page={per_page}")
    if not data or "items" not in data:
        return []
    return data["items"][:max_results]


def analyze_repo(repo_data: dict[str, Any]) -> GHRepoSignals:
    """Analyze a repo for pain signals."""
    full_name = repo_data.get("full_name", "")
    signals: list[str] = []

    has_ci = False
    workflows = _github_get(f"/repos/{full_name}/actions/workflows")
    if workflows and workflows.get("total_count", 0) > 0:
        has_ci = True
    if not has_ci:
        signals.append("no_ci_gates")

    has_protection = False
    default_branch = repo_data.get("default_branch", "main")
    protection = _github_get(f"/repos/{full_name}/branches/{default_branch}/protection")
    if protection and "required_status_checks" in protection:
        has_protection = True
    if not has_protection:
        signals.append("no_provenance")

    bot_pr_ratio = 0.0
    pulls = _github_get(f"/repos/{full_name}/pulls?state=closed&per_page=30")
    if pulls and isinstance(pulls, list):
        total = len(pulls)
        bot_prs = sum(
            1 for pr in pulls
            if pr.get("user", {}).get("type") == "Bot"
            or "[bot]" in (pr.get("user", {}).get("login", ""))
            or "copilot" in (pr.get("title", "")).lower()
            or "ai-generated" in (pr.get("title", "")).lower()
        )
        if total > 0:
            bot_pr_ratio = bot_prs / total
        if bot_pr_ratio > 0.3:
            signals.append("bot_prs")

    open_issues = repo_data.get("open_issues_count", 0)
    if open_issues > 100:
        signals.append("high_churn")

    return GHRepoSignals(
        full_name=full_name,
        description=repo_data.get("description", "") or "",
        stars=repo_data.get("stargazers_count", 0),
        open_issues=open_issues,
        language=repo_data.get("language", "") or "",
        has_ci=has_ci,
        has_branch_protection=has_protection,
        bot_pr_ratio=bot_pr_ratio,
        recent_commit_count=0,
        pain_signals=signals,
        raw_data=repo_data,
    )


def compute_qualification_score(signals: GHRepoSignals) -> float:
    """Score a target 0-1 based on pain signals and repo characteristics."""
    score = 0.0

    pain_weight = {
        "no_ci_gates": 0.2,
        "no_provenance": 0.15,
        "bot_prs": 0.25,
        "high_churn": 0.1,
        "ai_slop": 0.2,
        "agent_access": 0.15,
        "missing_evals": 0.15,
    }
    for signal in signals.pain_signals:
        score += pain_weight.get(signal, 0.05)

    if signals.stars > 1000:
        score += 0.1
    elif signals.stars > 100:
        score += 0.05

    if signals.language in ("Python", "TypeScript", "JavaScript"):
        score += 0.05

    return min(score, 1.0)


def scout_targets(
    query: str = "copilot agent language:python stars:>50",
    max_results: int = 20,
    min_score: float = 0.3,
) -> list[RevenueTarget]:
    """Scout GitHub for potential governance sprint targets."""
    logger.info("Scouting with query: %s", query)
    repos = search_repos(query, max_results)
    logger.info("Found %d repos to analyze", len(repos))

    targets: list[RevenueTarget] = []
    for repo_data in repos:
        signals = analyze_repo(repo_data)
        score = compute_qualification_score(signals)

        if score < min_score:
            logger.debug("Skipping %s (score %.2f < %.2f)", signals.full_name, score, min_score)
            continue

        estimated_value = 5000.0
        if signals.stars > 1000:
            estimated_value = 15000.0
        elif signals.stars > 100:
            estimated_value = 10000.0

        target = RevenueTarget(
            name=signals.full_name,
            org=signals.full_name.split("/")[0] if "/" in signals.full_name else "",
            domain=signals.language.lower() if signals.language else "general",
            pain_signals=signals.pain_signals,
            repo_urls=[f"https://github.com/{signals.full_name}"],
            estimated_value_usd=estimated_value,
            status=TargetStatus.SCOUTED if score < 0.5 else TargetStatus.QUALIFIED,
            qualification_score=score,
            intelligence={
                "stars": signals.stars,
                "open_issues": signals.open_issues,
                "has_ci": signals.has_ci,
                "has_branch_protection": signals.has_branch_protection,
                "bot_pr_ratio": round(signals.bot_pr_ratio, 3),
                "description": signals.description,
            },
        )
        targets.append(target)
        time.sleep(0.5)

    targets.sort(key=lambda t: t.qualification_score, reverse=True)
    return targets


def main() -> None:
    parser = argparse.ArgumentParser(description="Scout GitHub for revenue targets")
    parser.add_argument("--query", default="copilot agent language:python stars:>50",
                        help="GitHub search query")
    parser.add_argument("--max-results", type=int, default=20,
                        help="Maximum repos to analyze")
    parser.add_argument("--min-score", type=float, default=0.3,
                        help="Minimum qualification score")
    parser.add_argument("--pain", default="",
                        help="Comma-separated pain signals to filter for")
    parser.add_argument("--qualify", action="store_true",
                        help="Re-qualify existing scouted targets")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print targets without saving to spine")
    args = parser.parse_args()

    spine = EconomicSpine()

    if args.qualify:
        scouted = spine.list_targets(status=TargetStatus.SCOUTED)
        logger.info("Re-qualifying %d scouted targets", len(scouted))
        for target in scouted:
            if target.qualification_score >= args.min_score:
                spine.qualify_target(
                    target.id,
                    target.qualification_score,
                    {"requalified": True},
                )
                logger.info(
                    "  Qualified: %s (%.2f)", target.name, target.qualification_score
                )
        return

    targets = scout_targets(args.query, args.max_results, args.min_score)

    if not targets:
        logger.info("No qualifying targets found.")
        return

    logger.info("\n=== %d Targets Found ===\n", len(targets))
    for t in targets:
        logger.info(
            "  [%.2f] %s — $%.0f est. — signals: %s",
            t.qualification_score,
            t.name,
            t.estimated_value_usd,
            ", ".join(t.pain_signals) or "none",
        )
        if not args.dry_run:
            spine.add_target(t)

    if not args.dry_run:
        snap = spine.snapshot()
        logger.info(
            "\nPipeline: %d scouted, %d qualified, $%.0f pipeline value",
            snap.targets_scouted,
            snap.targets_qualified,
            snap.total_pipeline_value_usd,
        )
    else:
        logger.info("\n(dry run — targets not saved)")


if __name__ == "__main__":
    main()
