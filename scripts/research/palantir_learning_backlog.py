#!/usr/bin/env python3
"""Build the Palantir Pilot bounded learning backlog.

The backlog turns the local source-card quality queue into an operator-facing
growth loop. It plans the next public-doc learning actions, records the
boundary, and writes receipts without fetching new pages or touching Learn.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.palantir_pilot import (  # noqa: E402
    RAW_SOURCE_DIR,
    WIKI_SOURCE_DIR,
)
from dharma_swarm.palantir_pilot_manifest import default_dharma_home  # noqa: E402
from scripts.research import palantir_public_source_cards as source_cards  # noqa: E402
from scripts.research.palantir_source_card_quality import build_quality_report  # noqa: E402


SCHEMA_VERSION = "palantir_pilot.learning_backlog_receipt.v1"
LEARNING_BACKLOG_PATH = WIKI_SOURCE_DIR / "learning-backlog.md"
LEARNING_LOOP_PATH = WIKI_SOURCE_DIR / "learning-loop-latest.md"


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def receipt_stamp(observed_at: str) -> str:
    return (
        observed_at.replace("-", "")
        .replace(":", "")
        .replace(".", "")
        .replace("+00:00", "Z")
    )


def _safe_candidate_urls(urls: object) -> list[str]:
    rows = urls if isinstance(urls, list) else []
    safe: list[str] = []
    for item in rows:
        url = str(item)
        if source_cards.is_allowed_source_card_url(url):
            safe.append(url)
    return source_cards.canonical_dedupe_urls(safe)


def _topic_command(topic: str, *, limit: int, dry_run: bool) -> str:
    parts = [
        "python3",
        "scripts/research/palantir_source_card_balanced_expand.py",
        "--topic",
        topic,
        "--limit-per-topic",
        str(max(1, limit)),
        "--max-total",
        str(max(1, limit)),
        "--json",
    ]
    if dry_run:
        parts.append("--dry-run")
    return " ".join(parts)


def _topic_verifier(topic: str) -> str:
    return (
        "python3 scripts/research/palantir_pilot_query.py "
        f"\"{topic} learning backlog source-card expansion\" "
        "--json --limit 5 --index-workspace --record-db"
    )


def _build_actions(
    *,
    quality: dict[str, object],
    limit_per_topic: int,
    max_actions: int,
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    flag_counts = quality.get("flag_counts")
    flags = flag_counts if isinstance(flag_counts, dict) else {}
    duplicate_count = int(quality.get("duplicate_group_count") or 0)

    if flags or duplicate_count:
        actions.append(
            {
                "priority": 1,
                "topic": "source-card-quality",
                "action": "repair_before_growth",
                "reason": "Quality flags or canonical duplicates are present, so repair should run before adding more cards.",
                "candidate_urls": [],
                "candidate_count": 0,
                "preview_command": "python3 scripts/research/palantir_source_card_cleanup.py --dry-run --json",
                "execution_command": "python3 scripts/research/palantir_source_card_cleanup.py --json",
                "verifier_command": "python3 scripts/research/palantir_source_card_quality.py --dry-run --json",
            }
        )
        return actions[: max(1, max_actions)]

    queue = quality.get("review_queue")
    review_queue = queue if isinstance(queue, dict) else {}
    priority = 1
    for topic in sorted(review_queue):
        safe_urls = _safe_candidate_urls(review_queue.get(topic))
        if not safe_urls:
            continue
        selected = safe_urls[: max(1, limit_per_topic)]
        actions.append(
            {
                "priority": priority,
                "topic": topic,
                "action": "expand_source_cards",
                "reason": "Public-doc candidate remains in the source-card quality review queue.",
                "candidate_urls": selected,
                "candidate_count": len(selected),
                "preview_command": _topic_command(topic, limit=len(selected), dry_run=True),
                "execution_command": _topic_command(topic, limit=len(selected), dry_run=False),
                "verifier_command": _topic_verifier(topic),
            }
        )
        priority += 1
        if len(actions) >= max(1, max_actions):
            break
    return actions


def _strict_checks(receipt: dict[str, object]) -> dict[str, bool]:
    actions = receipt.get("actions")
    action_rows = actions if isinstance(actions, list) else []
    quality = receipt.get("quality_snapshot")
    snapshot = quality if isinstance(quality, dict) else {}
    canonical_allowed_coverage = float(
        snapshot.get("canonical_coverage_percent_canonical_allowed_card_candidates") or 0
    )
    canonical_growth_exhausted = canonical_allowed_coverage >= 99.99
    candidate_urls = [
        str(url)
        for action in action_rows
        if isinstance(action, dict)
        for url in action.get("candidate_urls", [])
    ]
    return {
        "has_source_index": int(snapshot.get("source_url_count") or 0) > 0,
        "has_source_cards": int(snapshot.get("source_card_count") or 0) > 0,
        "has_learning_actions": bool(action_rows) or canonical_growth_exhausted,
        "candidate_urls_allowed": all(
            source_cards.is_allowed_source_card_url(url) for url in candidate_urls
        ),
        "learn_not_selected": all("learn.palantir.com" not in url for url in candidate_urls),
        "commands_have_verifiers": all(
            bool(action.get("verifier_command")) for action in action_rows if isinstance(action, dict)
        ),
    }


def _format_backlog_markdown(receipt: dict[str, object]) -> str:
    quality = receipt.get("quality_snapshot")
    snapshot = quality if isinstance(quality, dict) else {}
    actions = receipt.get("actions")
    action_rows = actions if isinstance(actions, list) else []
    checks = receipt.get("strict_checks")
    check_rows = checks if isinstance(checks, dict) else {}

    lines = [
        "# Palantir Pilot Learning Backlog",
        "",
        f"Observed: {receipt.get('observed_at', '')}",
        "",
        "Boundary: bounded public-source learning plan only. The backlog uses local source metadata, quality reports, and source-card queues. It does not fetch pages, mirror documents, scrape Learn, enroll in courses, or touch private tenant material.",
        "",
        "## Learning State",
        "",
        f"- State: `{receipt.get('learning_state', '')}`",
        f"- Cadence: {receipt.get('cadence', '')}",
        f"- Source URLs indexed: {snapshot.get('source_url_count', 0)}",
        f"- Allowed source-card candidates: {snapshot.get('allowed_source_card_candidate_count', 0)}",
        f"- Canonical allowed source-card candidates: {snapshot.get('canonical_allowed_source_card_candidate_count', 0)}",
        f"- Canonical source cards: {snapshot.get('canonical_source_card_count', 0)}",
        f"- Raw allowed candidate coverage: {snapshot.get('canonical_coverage_percent_allowed_card_candidates', 0)}%",
        f"- Canonical allowed candidate coverage: {snapshot.get('canonical_coverage_percent_canonical_allowed_card_candidates', 0)}%",
        f"- Quality flags: `{snapshot.get('flag_counts', {})}`",
        "",
        "## Next Actions",
        "",
    ]
    if not action_rows:
        if receipt.get("learning_state") == "canonical_docs_exhausted":
            lines.append(
                "- No learning actions selected because all canonical allowed public-doc source-card candidates are covered. Re-run after source index or quality queue changes."
            )
        else:
            lines.append("- No learning actions selected. Re-run after source index or quality queue changes.")
    for action in action_rows:
        if not isinstance(action, dict):
            continue
        lines.extend(
            [
                f"### {action.get('priority', '')}. {action.get('topic', '')}",
                "",
                f"- Action: `{action.get('action', '')}`",
                f"- Reason: {action.get('reason', '')}",
                f"- Candidate count: {action.get('candidate_count', 0)}",
                "- Candidate URLs:",
            ]
        )
        urls = action.get("candidate_urls")
        for url in urls if isinstance(urls, list) else []:
            lines.append(f"  - {url}")
        lines.extend(
            [
                "- Preview:",
                "",
                "```bash",
                str(action.get("preview_command") or ""),
                "```",
                "",
                "- Execute when assigned:",
                "",
                "```bash",
                str(action.get("execution_command") or ""),
                "```",
                "",
                "- Verify:",
                "",
                "```bash",
                str(action.get("verifier_command") or ""),
                "```",
                "",
            ]
        )
    lines.extend(["## Strict Checks", ""])
    for name, ok in sorted(check_rows.items()):
        lines.append(f"- `{name}`: {ok}")
    lines.append("")
    return "\n".join(lines)


def _format_loop_markdown(receipt: dict[str, object]) -> str:
    actions = receipt.get("actions")
    action_rows = actions if isinstance(actions, list) else []
    lines = [
        "# Palantir Pilot Learning Loop",
        "",
        f"Observed: {receipt.get('observed_at', '')}",
        "",
        "Loop: quality report -> learning backlog -> bounded source-card expansion -> quality recheck -> workspace index -> query smoke.",
        "",
        "Boundary: public URL metadata and bounded source-card facts only; Learn remains manual-review/link-only.",
        "",
        "## Current Queue",
        "",
        f"- Action count: {len(action_rows)}",
        f"- Strict pass: {receipt.get('strict_pass', False)}",
        f"- Backlog: `{receipt.get('backlog_path', '')}`",
        f"- Raw receipt: `{receipt.get('receipt_path', '')}`",
        "",
    ]
    for action in action_rows:
        if isinstance(action, dict):
            lines.append(
                f"- `{action.get('topic', '')}` -> `{action.get('action', '')}` "
                f"({action.get('candidate_count', 0)} candidates)"
            )
    lines.append("")
    return "\n".join(lines)


def build_learning_backlog(
    *,
    dharma_home: Path,
    observed_at: str | None = None,
    limit_per_topic: int = 3,
    max_actions: int = 7,
) -> dict[str, object]:
    observed = observed_at or iso_now()
    quality = build_quality_report(
        dharma_home=dharma_home,
        observed_at=observed,
        limit_per_topic=max(1, limit_per_topic),
    )
    actions = _build_actions(
        quality=quality,
        limit_per_topic=max(1, limit_per_topic),
        max_actions=max(1, max_actions),
    )
    flag_counts = quality.get("flag_counts")
    flags = flag_counts if isinstance(flag_counts, dict) else {}
    duplicate_count = int(quality.get("duplicate_group_count") or 0)
    canonical_allowed_coverage = float(
        quality.get("canonical_coverage_percent_canonical_allowed_card_candidates") or 0
    )
    if flags or duplicate_count:
        learning_state = "repair_first"
    elif canonical_allowed_coverage >= 99.99 and not actions:
        learning_state = "canonical_docs_exhausted"
    else:
        learning_state = "growth_ready"

    receipt: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "observed_at": observed,
        "learning_state": learning_state,
        "cadence": "operator-triggered or long-run periodic; run preview first, execute only inside an assigned Palantir Pilot slice, then re-run quality, audit, registration, query cookbook, and workspace indexing",
        "boundary": "local planning over public URL metadata, quality report queues, and source-card facts only; no page/course fetching and no Learn scraping",
        "quality_snapshot": {
            "source_url_count": quality.get("source_url_count", 0),
            "allowed_source_card_candidate_count": quality.get("allowed_source_card_candidate_count", 0),
            "canonical_allowed_source_card_candidate_count": quality.get(
                "canonical_allowed_source_card_candidate_count", 0
            ),
            "source_card_count": quality.get("source_card_count", 0),
            "canonical_source_card_count": quality.get("canonical_source_card_count", 0),
            "canonical_coverage_percent_allowed_card_candidates": quality.get(
                "canonical_coverage_percent_allowed_card_candidates", 0
            ),
            "canonical_coverage_percent_canonical_allowed_card_candidates": quality.get(
                "canonical_coverage_percent_canonical_allowed_card_candidates", 0
            ),
            "flag_counts": quality.get("flag_counts", {}),
            "duplicate_group_count": quality.get("duplicate_group_count", 0),
        },
        "actions": actions,
        "action_count": len(actions),
    }
    checks = _strict_checks(receipt)
    receipt["strict_checks"] = checks
    receipt["strict_pass"] = all(checks.values())

    wiki_dir = dharma_home / WIKI_SOURCE_DIR
    raw_dir = dharma_home / RAW_SOURCE_DIR
    wiki_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    backlog_path = dharma_home / LEARNING_BACKLOG_PATH
    loop_path = dharma_home / LEARNING_LOOP_PATH
    receipt_path = raw_dir / f"learning-backlog-{receipt_stamp(observed)}.json"
    receipt["backlog_path"] = str(backlog_path)
    receipt["learning_loop_path"] = str(loop_path)
    receipt["receipt_path"] = str(receipt_path)

    backlog_path.write_text(_format_backlog_markdown(receipt), encoding="utf-8")
    loop_path.write_text(_format_loop_markdown(receipt), encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dharma-home", default=str(default_dharma_home()))
    parser.add_argument("--limit-per-topic", type=int, default=3)
    parser.add_argument("--max-actions", type=int, default=7)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    receipt = build_learning_backlog(
        dharma_home=Path(args.dharma_home).expanduser(),
        limit_per_topic=max(1, args.limit_per_topic),
        max_actions=max(1, args.max_actions),
    )
    if args.json:
        print(json.dumps(receipt, indent=2, ensure_ascii=True))
    else:
        print(
            f"wrote learning backlog: {receipt['backlog_path']} "
            f"({receipt['action_count']} actions, strict={receipt['strict_pass']})"
        )
    if args.strict and not bool(receipt["strict_pass"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
