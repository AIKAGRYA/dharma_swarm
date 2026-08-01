#!/usr/bin/env python3
"""Archive retired Palantir Pilot source cards without deleting evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.palantir_pilot import (  # noqa: E402
    RAW_SOURCE_DIR,
    WIKI_SOURCE_DIR,
)
from dharma_swarm.palantir_pilot_manifest import default_dharma_home  # noqa: E402
from scripts.research import palantir_public_source_cards as source_cards  # noqa: E402
from scripts.research.palantir_source_card_quality import build_quality_report  # noqa: E402


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _is_versioned_api_alias(url: str) -> bool:
    return bool(re.search(r"/api/v[0-9]+/", urlparse(url).path))


def _duplicate_keep_key(item: dict[str, object]) -> tuple[bool, int, str]:
    url = str(item.get("url") or "")
    return (_is_versioned_api_alias(url), len(urlparse(url).path), url)


def _append_archive_candidate(
    candidates: dict[str, dict[str, object]],
    *,
    path: str,
    url: str,
    reason: str,
    canonical: str,
) -> None:
    if not path:
        return
    entry = candidates.setdefault(
        path,
        {
            "url": url,
            "path": path,
            "canonical": canonical,
            "reasons": [],
        },
    )
    reasons = entry.get("reasons")
    if not isinstance(reasons, list):
        reasons = []
        entry["reasons"] = reasons
    if reason not in reasons:
        reasons.append(reason)


def build_cleanup_plan(
    *,
    dharma_home: Path,
    observed_at: str | None = None,
) -> dict[str, object]:
    """Build a local-only archive plan for legacy duplicate/disallowed cards."""

    observed = observed_at or iso_now()
    report = build_quality_report(dharma_home=dharma_home, observed_at=observed)
    archive_candidates: dict[str, dict[str, object]] = {}
    kept_duplicate_representatives: list[dict[str, str]] = []

    duplicate_groups = report.get("duplicate_groups")
    for group in duplicate_groups if isinstance(duplicate_groups, list) else []:
        if not isinstance(group, dict):
            continue
        cards = [item for item in group.get("cards", []) if isinstance(item, dict)]
        if len(cards) < 2:
            continue
        sorted_cards = sorted(cards, key=_duplicate_keep_key)
        keep = sorted_cards[0]
        canonical = str(group.get("canonical") or "")
        kept_duplicate_representatives.append(
            {
                "canonical": canonical,
                "url": str(keep.get("url") or ""),
                "path": str(keep.get("path") or ""),
            }
        )
        for item in sorted_cards[1:]:
            _append_archive_candidate(
                archive_candidates,
                path=str(item.get("path") or ""),
                url=str(item.get("url") or ""),
                reason="canonical_duplicate_excess",
                canonical=canonical,
            )

    flagged_cards = report.get("flagged_cards")
    for row in flagged_cards if isinstance(flagged_cards, list) else []:
        if not isinstance(row, dict):
            continue
        flags = {str(item) for item in row.get("flags", []) if item}
        url = str(row.get("url") or "")
        if "deprecated_path" in flags or "now_disallowed_by_selector_policy" in flags:
            _append_archive_candidate(
                archive_candidates,
                path=str(row.get("path") or ""),
                url=url,
                reason="deprecated_or_now_disallowed",
                canonical=source_cards.canonical_source_url(url),
            )
        elif {"missing_title", "missing_short_excerpt", "missing_headings"}.issubset(flags):
            _append_archive_candidate(
                archive_candidates,
                path=str(row.get("path") or ""),
                url=url,
                reason="irreparable_no_signal_card",
                canonical=source_cards.canonical_source_url(url),
            )

    candidates = sorted(
        archive_candidates.values(),
        key=lambda item: (str(item.get("canonical") or ""), str(item.get("url") or "")),
    )
    return {
        "schema_version": "palantir_pilot.source_card_cleanup_plan.v1",
        "observed_at": observed,
        "boundary": "local source-card archive planning only; no page/course fetching and no evidence deletion",
        "quality_report_observed_at": report.get("observed_at", ""),
        "active_card_count_before": report.get("source_card_count", 0),
        "canonical_source_card_count_before": report.get("canonical_source_card_count", 0),
        "duplicate_group_count_before": report.get("duplicate_group_count", 0),
        "flag_counts_before": report.get("flag_counts", {}),
        "kept_duplicate_representatives": kept_duplicate_representatives,
        "archive_candidates": candidates,
        "planned_archive_count": len(candidates),
    }


def _safe_archive_path(archive_dir: Path, source_path: Path) -> Path:
    candidate = archive_dir / source_path.name
    if not candidate.exists():
        return candidate
    stem = source_path.stem
    suffix = source_path.suffix
    for index in range(2, 1000):
        candidate = archive_dir / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate archive path for {source_path}")


def _active_card_count(dharma_home: Path) -> int:
    card_dir = dharma_home / WIKI_SOURCE_DIR / "source-cards"
    if not card_dir.exists():
        return 0
    return sum(1 for path in card_dir.glob("*.md") if path.is_file())


def rebuild_source_card_index(
    *,
    dharma_home: Path,
    observed_at: str,
    receipt_path: Path,
    archived_count: int,
) -> dict[str, object]:
    card_dir = dharma_home / WIKI_SOURCE_DIR / "source-cards"
    index_path = dharma_home / WIKI_SOURCE_DIR / "source-card-index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    card_dir.mkdir(parents=True, exist_ok=True)

    indexed_cards: list[dict[str, str]] = []
    for path in sorted(card_dir.glob("*.md")):
        if not path.is_file():
            continue
        indexed_cards.append(
            {
                "url": source_cards.card_source_url(path) or path.stem,
                "path": str(path),
            }
        )

    lines = [
        "# Palantir Pilot Source Card Index",
        "",
        f"Observed: {observed_at}",
        f"Card count: {len(indexed_cards)}",
        "Latest batch card count: 0",
        f"Latest cleanup archived count: {archived_count}",
        f"Machine receipt: `{receipt_path}`",
        "",
        "Boundary: bounded public docs review cards only. Learn course catalog remains manual-review/link-only.",
        "",
        "## Cards",
        "",
    ]
    if not indexed_cards:
        lines.append("- No source cards written.")
    for item in indexed_cards:
        rel = Path(item["path"]).name
        lines.append(f"- [{item['url']}](source-cards/{rel})")
    lines.append("")
    index_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "index_path": str(index_path),
        "index_card_count": len(indexed_cards),
    }


def _format_cleanup_markdown(receipt: dict[str, object]) -> str:
    archived_cards = receipt.get("archived_cards")
    archived = archived_cards if isinstance(archived_cards, list) else []
    skipped_cards = receipt.get("skipped_cards")
    skipped = skipped_cards if isinstance(skipped_cards, list) else []
    lines = [
        "# Palantir Pilot Source-Card Cleanup",
        "",
        f"Observed: {receipt.get('observed_at', '')}",
        "",
        "Boundary: local archive-only cleanup. No Palantir page bodies, Learn course content, videos, labs, quizzes, private tenant material, or new external fetches are stored here.",
        "",
        "## Summary",
        "",
        f"- Active cards before: {receipt.get('active_card_count_before', 0)}",
        f"- Planned archive count: {receipt.get('planned_archive_count', 0)}",
        f"- Archived cards: {len(archived)}",
        f"- Active cards after: {receipt.get('active_card_count_after', 0)}",
        f"- Archive dir: `{receipt.get('archive_dir', '')}`",
        f"- Machine receipt: `{receipt.get('receipt_path', '')}`",
        "",
        "## Archived Cards",
        "",
    ]
    if not archived:
        lines.append("- No cards archived.")
    for row in archived:
        if not isinstance(row, dict):
            continue
        reasons = ", ".join(str(item) for item in row.get("reasons", []))
        lines.append(f"- `{reasons}` {row.get('url', '')}")
    lines.extend(["", "## Skipped Cards", ""])
    if not skipped:
        lines.append("- No archive candidates skipped.")
    for row in skipped:
        if isinstance(row, dict):
            lines.append(f"- `{row.get('status', '')}` {row.get('path', '')}")
    lines.append("")
    return "\n".join(lines)


def cleanup_source_cards(
    *,
    dharma_home: Path,
    observed_at: str | None = None,
    stamp: str | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    observed = observed_at or iso_now()
    archive_stamp = stamp or utc_stamp()
    plan = build_cleanup_plan(dharma_home=dharma_home, observed_at=observed)
    raw_dir = dharma_home / RAW_SOURCE_DIR / "source-card-cleanup"
    receipt_path = raw_dir / f"source-card-cleanup-{archive_stamp}.json"
    archive_dir = dharma_home / WIKI_SOURCE_DIR / "source-cards-archive" / archive_stamp
    card_dir = dharma_home / WIKI_SOURCE_DIR / "source-cards"

    archived_cards: list[dict[str, object]] = []
    skipped_cards: list[dict[str, object]] = []
    if not dry_run:
        raw_dir.mkdir(parents=True, exist_ok=True)
        archive_dir.mkdir(parents=True, exist_ok=True)

    for item in plan.get("archive_candidates", []):
        if not isinstance(item, dict):
            continue
        source_path = Path(str(item.get("path") or ""))
        if not source_path.exists():
            skipped_cards.append({**item, "status": "skipped:missing_source"})
            continue
        try:
            source_path.relative_to(card_dir)
        except ValueError:
            skipped_cards.append({**item, "status": "skipped:not_active_card_dir"})
            continue
        archive_path = _safe_archive_path(archive_dir, source_path)
        archived_entry = {**item, "archive_path": str(archive_path), "status": "would_archive"}
        if not dry_run:
            source_path.replace(archive_path)
            archived_entry["status"] = "archived"
        archived_cards.append(archived_entry)

    index_result: dict[str, object] = {}
    if not dry_run:
        index_result = rebuild_source_card_index(
            dharma_home=dharma_home,
            observed_at=observed,
            receipt_path=receipt_path,
            archived_count=len(archived_cards),
        )

    receipt = {
        "schema_version": "palantir_pilot.source_card_cleanup_receipt.v1",
        "status": "dry_run" if dry_run else "written",
        "observed_at": observed,
        "boundary": plan["boundary"],
        "archive_dir": str(archive_dir),
        "receipt_path": str(receipt_path) if not dry_run else "",
        "cleanup_report_path": str(dharma_home / WIKI_SOURCE_DIR / "source-card-cleanup-latest.md")
        if not dry_run
        else "",
        "active_card_count_before": plan["active_card_count_before"],
        "canonical_source_card_count_before": plan["canonical_source_card_count_before"],
        "duplicate_group_count_before": plan["duplicate_group_count_before"],
        "flag_counts_before": plan["flag_counts_before"],
        "planned_archive_count": plan["planned_archive_count"],
        "kept_duplicate_representatives": plan["kept_duplicate_representatives"],
        "archived_cards": archived_cards,
        "skipped_cards": skipped_cards,
        "active_card_count_after": _active_card_count(dharma_home),
        "index": index_result,
    }
    if not dry_run:
        receipt_path.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        report_path = dharma_home / WIKI_SOURCE_DIR / "source-card-cleanup-latest.md"
        report_path.write_text(_format_cleanup_markdown(receipt), encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dharma-home", default=str(default_dharma_home()))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    receipt = cleanup_source_cards(
        dharma_home=Path(args.dharma_home).expanduser(),
        dry_run=args.dry_run,
    )
    if args.json or args.dry_run:
        print(json.dumps(receipt, indent=2, ensure_ascii=True))
    else:
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "archived_cards": len(receipt["archived_cards"]),
                    "active_card_count_after": receipt["active_card_count_after"],
                    "receipt_path": receipt["receipt_path"],
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
