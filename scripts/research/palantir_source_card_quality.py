#!/usr/bin/env python3
"""Audit Palantir Pilot source-card coverage and quality without fetching pages."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
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
from scripts.research.palantir_public_source_index import classify_url  # noqa: E402


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_card_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def source_card_rows(dharma_home: Path) -> list[dict[str, object]]:
    card_dir = dharma_home / WIKI_SOURCE_DIR / "source-cards"
    rows: list[dict[str, object]] = []
    if not card_dir.exists():
        return rows
    for path in sorted(card_dir.glob("*.md")):
        text = _read_card_text(path)
        url = source_cards.card_source_url(path)
        if not url:
            continue
        title = ""
        summary_title = ""
        short_excerpt = ""
        for line in text.splitlines():
            if line.startswith("# Palantir Source Card: "):
                title = line.split("# Palantir Source Card: ", 1)[1].strip()
            elif line.startswith("- Title: "):
                summary_title = line.split("- Title: ", 1)[1].strip()
            elif line.startswith("- Short excerpt: "):
                short_excerpt = line.split("- Short excerpt: ", 1)[1].strip()
        title_value = summary_title or title
        has_title = bool(
            title_value
            and title_value.lower() != "not extracted"
            and title_value != url
            and not title_value.startswith(("http://", "https://"))
        )
        has_short_excerpt = bool(
            short_excerpt and short_excerpt.lower() != "not extracted"
        )
        rows.append(
            {
                "url": url,
                "path": str(path),
                "family": classify_url(url),
                "title": title,
                "has_title": has_title,
                "has_short_excerpt": has_short_excerpt,
                "has_headings": "No headings extracted from the fetched public page." not in text,
                "byte_count": len(text.encode("utf-8")),
            }
        )
    return rows


def card_quality_flags(row: dict[str, object]) -> list[str]:
    url = str(row.get("url") or "")
    path = urlparse(url).path.lower()
    flags: list[str] = []
    if source_cards.has_deprecated_path(path):
        flags.append("deprecated_path")
    if not source_cards.is_allowed_source_card_url(url):
        flags.append("now_disallowed_by_selector_policy")
    if not row.get("has_title"):
        flags.append("missing_title")
    if not row.get("has_short_excerpt"):
        flags.append("missing_short_excerpt")
    if not row.get("has_headings"):
        flags.append("missing_headings")
    if int(row.get("byte_count") or 0) < 400:
        flags.append("thin_card")
    return flags


def _family_counts_from_source_index(dharma_home: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in source_cards.load_source_index_rows(dharma_home):
        family = str(row.get("family") or "unknown")
        counts[family] += 1
    return dict(sorted(counts.items()))


def _allowed_url_count(dharma_home: Path) -> int:
    count = 0
    for row in source_cards.load_source_index_rows(dharma_home):
        if source_cards.is_allowed_source_card_url(str(row.get("loc") or "")):
            count += 1
    return count


def _allowed_canonical_url_count(dharma_home: Path) -> int:
    canonical_urls: set[str] = set()
    for row in source_cards.load_source_index_rows(dharma_home):
        url = str(row.get("loc") or "")
        if source_cards.is_allowed_source_card_url(url):
            canonical_urls.add(source_cards.canonical_source_url(url))
    return len(canonical_urls)


def _review_queue(dharma_home: Path, *, limit_per_topic: int) -> dict[str, list[str]]:
    queue: dict[str, list[str]] = {}
    for topic in sorted(source_cards.TOPIC_PROFILES):
        queue[topic] = source_cards.select_index_urls(
            dharma_home,
            topics=[topic],
            limit=limit_per_topic,
        )
    return queue


def build_quality_report(
    *,
    dharma_home: Path,
    observed_at: str | None = None,
    limit_per_topic: int = 8,
) -> dict[str, object]:
    observed = observed_at or iso_now()
    cards = source_card_rows(dharma_home)
    source_rows = source_cards.load_source_index_rows(dharma_home)
    allowed_count = _allowed_url_count(dharma_home)
    canonical_allowed_count = _allowed_canonical_url_count(dharma_home)
    total_urls = len(source_rows)

    duplicate_groups_raw: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in cards:
        duplicate_groups_raw[source_cards.canonical_source_url(str(row.get("url") or ""))].append(row)
    duplicate_groups = [
        {
            "canonical": canonical,
            "cards": [
                {
                    "url": str(item.get("url") or ""),
                    "path": str(item.get("path") or ""),
                }
                for item in rows
            ],
        }
        for canonical, rows in sorted(duplicate_groups_raw.items())
        if len(rows) > 1
    ]
    duplicate_excess_count = sum(
        max(0, len(group["cards"]) - 1)
        for group in duplicate_groups
        if isinstance(group.get("cards"), list)
    )

    card_rows: list[dict[str, object]] = []
    flag_counts: Counter[str] = Counter()
    duplicate_urls = {
        str(item["url"])
        for group in duplicate_groups
        for item in group["cards"]
        if isinstance(item, dict)
    }
    for row in cards:
        flags = card_quality_flags(row)
        if str(row.get("url") or "") in duplicate_urls:
            flags.append("canonical_duplicate_group")
        flag_counts.update(flags)
        card_rows.append({**row, "flags": flags})

    card_family_counts: Counter[str] = Counter(str(row.get("family") or "unknown") for row in cards)
    carded_urls = {str(row.get("url") or "") for row in cards}
    canonical_card_count = max(0, len(carded_urls) - duplicate_excess_count)
    coverage_percent = round((len(carded_urls) / total_urls * 100), 2) if total_urls else 0.0
    allowed_coverage_percent = round((len(carded_urls) / allowed_count * 100), 2) if allowed_count else 0.0
    canonical_coverage_percent = (
        round((canonical_card_count / total_urls * 100), 2) if total_urls else 0.0
    )
    canonical_allowed_coverage_percent = (
        round((canonical_card_count / allowed_count * 100), 2) if allowed_count else 0.0
    )
    canonical_allowed_candidate_coverage_percent = (
        round((canonical_card_count / canonical_allowed_count * 100), 2)
        if canonical_allowed_count
        else 0.0
    )

    return {
        "schema_version": "palantir_pilot.source_card_quality.v1",
        "observed_at": observed,
        "boundary": "quality analysis over local URL metadata and source-card markdown only; no page/course fetching",
        "source_url_count": total_urls,
        "allowed_source_card_candidate_count": allowed_count,
        "canonical_allowed_source_card_candidate_count": canonical_allowed_count,
        "source_card_count": len(cards),
        "canonical_source_card_count": canonical_card_count,
        "duplicate_excess_card_count": duplicate_excess_count,
        "coverage_percent_all_indexed_urls": coverage_percent,
        "coverage_percent_allowed_card_candidates": allowed_coverage_percent,
        "canonical_coverage_percent_all_indexed_urls": canonical_coverage_percent,
        "canonical_coverage_percent_allowed_card_candidates": canonical_allowed_coverage_percent,
        "canonical_coverage_percent_canonical_allowed_card_candidates": canonical_allowed_candidate_coverage_percent,
        "source_index_family_counts": _family_counts_from_source_index(dharma_home),
        "source_card_family_counts": dict(sorted(card_family_counts.items())),
        "flag_counts": dict(sorted(flag_counts.items())),
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_groups": duplicate_groups,
        "flagged_cards": [
            {
                "url": str(row.get("url") or ""),
                "path": str(row.get("path") or ""),
                "family": str(row.get("family") or ""),
                "flags": row.get("flags") or [],
            }
            for row in card_rows
            if row.get("flags")
        ],
        "review_queue": _review_queue(dharma_home, limit_per_topic=max(1, limit_per_topic)),
    }


def _format_quality_markdown(report: dict[str, object]) -> str:
    flag_counts = report.get("flag_counts")
    flags = flag_counts if isinstance(flag_counts, dict) else {}
    family_counts = report.get("source_card_family_counts")
    card_families = family_counts if isinstance(family_counts, dict) else {}
    source_family_counts = report.get("source_index_family_counts")
    source_families = source_family_counts if isinstance(source_family_counts, dict) else {}
    duplicate_groups = report.get("duplicate_groups")
    duplicates = duplicate_groups if isinstance(duplicate_groups, list) else []
    flagged_cards = report.get("flagged_cards")
    flagged = flagged_cards if isinstance(flagged_cards, list) else []
    review_queue = report.get("review_queue")
    queue = review_queue if isinstance(review_queue, dict) else {}

    lines = [
        "# Palantir Pilot Source-Card Quality Report",
        "",
        f"Observed: {report.get('observed_at', '')}",
        "",
        "Boundary: local quality analysis only. No Palantir page bodies, Learn course content, videos, labs, quizzes, private tenant material, or new external fetches are stored here.",
        "",
        "## Coverage",
        "",
        f"- Indexed public URLs: {report.get('source_url_count', 0)}",
        f"- Allowed source-card candidates: {report.get('allowed_source_card_candidate_count', 0)}",
        f"- Canonical allowed source-card candidates: {report.get('canonical_allowed_source_card_candidate_count', 0)}",
        f"- Source cards: {report.get('source_card_count', 0)}",
        f"- Canonical source cards: {report.get('canonical_source_card_count', 0)}",
        f"- Duplicate excess cards: {report.get('duplicate_excess_card_count', 0)}",
        f"- Coverage of all indexed URLs: {report.get('coverage_percent_all_indexed_urls', 0)}%",
        f"- Coverage of allowed source-card candidates: {report.get('coverage_percent_allowed_card_candidates', 0)}%",
        f"- Canonical coverage of all indexed URLs: {report.get('canonical_coverage_percent_all_indexed_urls', 0)}%",
        f"- Canonical coverage of allowed source-card candidates: {report.get('canonical_coverage_percent_allowed_card_candidates', 0)}%",
        f"- Canonical coverage of canonical allowed source-card candidates: {report.get('canonical_coverage_percent_canonical_allowed_card_candidates', 0)}%",
        "",
        "## Card Families",
        "",
    ]
    for family, count in card_families.items():
        lines.append(f"- `{family}`: {count} cards")
    lines.extend(["", "## Indexed URL Families", ""])
    for family, count in source_families.items():
        lines.append(f"- `{family}`: {count} URLs")
    lines.extend(["", "## Quality Flags", ""])
    if not flags:
        lines.append("- No quality flags.")
    for flag, count in flags.items():
        lines.append(f"- `{flag}`: {count}")

    lines.extend(["", "## Duplicate Canonical Groups", ""])
    if not duplicates:
        lines.append("- No canonical duplicate groups detected.")
    for group in duplicates:
        if not isinstance(group, dict):
            continue
        lines.append(f"- `{group.get('canonical', '')}`")
        cards = group.get("cards")
        for item in cards if isinstance(cards, list) else []:
            if isinstance(item, dict):
                lines.append(f"  - {item.get('url', '')}")

    lines.extend(["", "## Flagged Cards", ""])
    if not flagged:
        lines.append("- No flagged cards.")
    for row in flagged:
        if not isinstance(row, dict):
            continue
        flags_text = ", ".join(str(item) for item in row.get("flags", []))
        lines.append(f"- `{flags_text}` {row.get('url', '')}")

    lines.extend(["", "## Next Review Queue", ""])
    for topic, urls in sorted(queue.items()):
        lines.append(f"### {topic}")
        lines.append("")
        if not isinstance(urls, list) or not urls:
            lines.append("- No remaining candidates selected.")
            lines.append("")
            continue
        for url in urls:
            lines.append(f"- {url}")
        lines.append("")
    return "\n".join(lines)


def write_quality_outputs(dharma_home: Path, report: dict[str, object]) -> dict[str, str]:
    raw_dir = dharma_home / RAW_SOURCE_DIR
    wiki_dir = dharma_home / WIKI_SOURCE_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    wiki_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    receipt_path = raw_dir / f"source-card-quality-{stamp}.json"
    report_path = wiki_dir / "source-card-quality-report.md"
    receipt_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(_format_quality_markdown(report), encoding="utf-8")
    return {"receipt_path": str(receipt_path), "report_path": str(report_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dharma-home", default=str(default_dharma_home()))
    parser.add_argument("--limit-per-topic", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    dharma_home = Path(args.dharma_home).expanduser()
    report = build_quality_report(
        dharma_home=dharma_home,
        limit_per_topic=max(1, args.limit_per_topic),
    )
    outputs: dict[str, str] = {}
    if not args.dry_run:
        outputs = write_quality_outputs(dharma_home, report)
    result = {"status": "dry_run" if args.dry_run else "written", "outputs": outputs, **report}
    if args.json or args.dry_run:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print(json.dumps({"status": result["status"], "outputs": outputs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
