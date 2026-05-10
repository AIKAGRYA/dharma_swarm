#!/usr/bin/env python3
"""Outreach drafter — generates personalized outreach for qualified targets.

Takes qualified RevenueTargets from the EconomicSpine and drafts outreach
messages tailored to each target's pain signals and context.

Rule: NO AUTONOMOUS SPAM. This script only drafts. Every message must be
explicitly approved by a human via ``spine.approve_outreach(draft_id, "name")``
before it can be marked as sent.

Usage::

    # Draft outreach for all qualified targets
    python scripts/revenue/draft_outreach.py

    # Draft for a specific target
    python scripts/revenue/draft_outreach.py --target-id tgt-123456

    # List pending (unapproved) outreach
    python scripts/revenue/draft_outreach.py --list-pending

    # Approve a draft (human action)
    python scripts/revenue/draft_outreach.py --approve out-789 --approver "dhyana"
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from dharma_swarm.revenue.spine import (
    EconomicSpine,
    Offer,
    OutreachChannel,
    OutreachDraft,
    RevenueTarget,
    TargetStatus,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


PAIN_TO_HOOK: dict[str, str] = {
    "no_ci_gates": (
        "I noticed your repo doesn't have required status checks on the default branch. "
        "For teams using AI coding tools, this means generated code can merge without "
        "quality gates — a governance gap that compounds over time."
    ),
    "bot_prs": (
        "Your repo shows a significant fraction of bot-authored or AI-generated PRs. "
        "Without provenance tracking, it becomes impossible to audit which code came "
        "from which agent, model, or prompt."
    ),
    "no_provenance": (
        "Your codebase doesn't enforce commit signing or provenance tracking. "
        "As AI agents become more active in your workflow, the audit trail gap widens."
    ),
    "high_churn": (
        "The high issue count and file churn in your repo suggest potential AI slop "
        "accumulation — generated code that works but creates maintenance debt."
    ),
    "ai_slop": (
        "Code analysis suggests AI-generated patterns that may accumulate technical debt: "
        "duplicated logic, missing type annotations, cargo-culted patterns from training data."
    ),
    "agent_access": (
        "AI agents with write access to your repo but no structured audit trail "
        "creates risk as these agents become more autonomous."
    ),
    "missing_evals": (
        "Your team uses agent tooling but has no evaluation framework to measure "
        "agent quality — defect rate, revert rate, downstream breakage."
    ),
}


def _build_subject(target: RevenueTarget) -> str:
    """Build email subject line."""
    org_name = target.org or (target.name.split("/")[0] if "/" in target.name else target.name)
    return f"Code governance for {org_name}'s AI workflow"


def _build_body(target: RevenueTarget, offer: Offer) -> str:
    """Build personalized outreach body from target pain signals."""
    org_name = target.org or target.name
    hooks: list[str] = []
    for signal in target.pain_signals:
        hook = PAIN_TO_HOOK.get(signal)
        if hook:
            hooks.append(hook)

    if not hooks:
        hooks.append(
            "Teams shipping with AI coding tools often accumulate governance gaps "
            "that compound over time — missing provenance, no quality gates on "
            "generated code, no agent eval framework."
        )

    pain_section = "\n\n".join(hooks)

    body = f"""Hi,

I'm reaching out because I work on AI agent governance tooling and noticed some patterns in {org_name}'s public repos that suggest a potential fit.

{pain_section}

We offer a focused engagement — the **{offer.title}** — where we:

1. Audit your repo for AI slop, dead code, and provenance gaps
2. Install packet provenance, CI gates, and an eval framework
3. Produce a ranked findings report with fix PRs
4. Optionally run governed agent repair loops on the worst findings

The engagement is {offer.duration_days} days, priced ${offer.price_range_low_usd:,.0f}-${offer.price_range_high_usd:,.0f} depending on repo count and scope.

Everything we install lives in your repo — not behind our API. The gates block bad code at merge time. The audit ledger is append-only and exportable.

Would a 30-minute scope call be useful? Happy to look at your specific repos and estimate what a governance sprint would cover.

Best,
[Your name]
dharma_swarm — Governed AI agent infrastructure"""

    return body


def draft_for_target(
    spine: EconomicSpine,
    target: RevenueTarget,
    offer: Offer | None = None,
    channel: OutreachChannel = OutreachChannel.EMAIL,
) -> OutreachDraft | None:
    """Draft outreach for a single target."""
    if offer is None:
        offer = spine.default_offer()

    subject = _build_subject(target)
    body = _build_body(target, offer)

    draft = spine.draft_outreach(
        target.id,
        offer.id,
        channel=channel,
        subject=subject,
        body=body,
    )
    return draft


def draft_all_qualified(spine: EconomicSpine) -> list[OutreachDraft]:
    """Draft outreach for all qualified targets without existing drafts."""
    qualified = spine.list_targets(status=TargetStatus.QUALIFIED)
    existing_target_ids = {d.target_id for d in spine.pending_outreach()}

    drafts: list[OutreachDraft] = []
    for target in qualified:
        if target.id in existing_target_ids:
            logger.info("  Skipping %s (draft already exists)", target.name)
            continue

        draft = draft_for_target(spine, target)
        if draft:
            drafts.append(draft)
            logger.info("  Drafted: %s -> %s", target.name, draft.id)

    return drafts


def main() -> None:
    parser = argparse.ArgumentParser(description="Draft outreach for revenue targets")
    parser.add_argument("--target-id", default="",
                        help="Draft for a specific target ID")
    parser.add_argument("--list-pending", action="store_true",
                        help="List all pending (unapproved) outreach drafts")
    parser.add_argument("--approve", default="",
                        help="Approve a specific outreach draft ID")
    parser.add_argument("--approver", default="dhyana",
                        help="Name of person approving (default: dhyana)")
    parser.add_argument("--channel", default="email",
                        choices=["email", "github", "twitter", "linkedin", "discord", "direct"],
                        help="Outreach channel")
    args = parser.parse_args()

    spine = EconomicSpine()

    if args.list_pending:
        pending = spine.pending_outreach()
        if not pending:
            logger.info("No pending outreach drafts.")
            return
        logger.info("\n=== %d Pending Outreach Drafts ===\n", len(pending))
        for draft in pending:
            target = spine.get_target(draft.target_id)
            name = target.name if target else draft.target_id
            logger.info("  [%s] -> %s", draft.id, name)
            logger.info("    Subject: %s", draft.subject)
            logger.info("    Channel: %s", draft.channel)
            logger.info("    Created: %s", draft.created_at)
            logger.info("")
        return

    if args.approve:
        ok = spine.approve_outreach(args.approve, args.approver)
        if ok:
            logger.info("Approved: %s (by %s)", args.approve, args.approver)
        else:
            logger.error("Failed to approve %s — not found or already approved", args.approve)
        return

    channel = OutreachChannel(args.channel)

    if args.target_id:
        target = spine.get_target(args.target_id)
        if not target:
            logger.error("Target not found: %s", args.target_id)
            sys.exit(1)
        draft = draft_for_target(spine, target, channel=channel)
        if draft:
            logger.info("Drafted outreach: %s", draft.id)
            logger.info("  Subject: %s", draft.subject)
            logger.info("  Channel: %s", draft.channel)
            logger.info("\n--- Body ---\n%s\n---", draft.body)
            logger.info("\nTo approve: python scripts/revenue/draft_outreach.py --approve %s", draft.id)
        return

    logger.info("Drafting outreach for all qualified targets...")
    drafts = draft_all_qualified(spine)
    logger.info("\nDrafted %d outreach messages.", len(drafts))
    if drafts:
        logger.info(
            "\nTo review and approve:\n"
            "  python scripts/revenue/draft_outreach.py --list-pending\n"
            "  python scripts/revenue/draft_outreach.py --approve <draft-id>"
        )


if __name__ == "__main__":
    main()
