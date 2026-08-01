#!/usr/bin/env python3
"""Balanced Palantir Pilot source-card expansion runner.

This is a thin orchestration layer over palantir_public_source_cards. It keeps
the same copyright and access boundary while making repeatable coverage growth
easier for long-run missions.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.palantir_pilot import RAW_SOURCE_DIR  # noqa: E402
from dharma_swarm.palantir_pilot_manifest import default_dharma_home  # noqa: E402
from scripts.research import palantir_public_source_cards as source_cards  # noqa: E402


SCHEMA_VERSION = "palantir_pilot.balanced_source_card_expansion.v1"
DEFAULT_TOPICS = tuple(sorted(source_cards.TOPIC_PROFILES))


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def select_balanced_urls(
    dharma_home: Path,
    *,
    topics: list[str],
    limit_per_topic: int,
    max_total: int | None = None,
) -> tuple[list[dict[str, object]], list[str]]:
    """Select candidate URLs topic-by-topic, then canonical-dedupe the batch."""

    selections: list[dict[str, object]] = []
    selected_urls: list[str] = []
    for topic in topics:
        urls = source_cards.select_index_urls(
            dharma_home,
            topics=[topic],
            limit=max(1, limit_per_topic),
            skip_existing=True,
        )
        selections.append(
            {
                "topic": topic,
                "selected_count": len(urls),
                "urls": urls,
            }
        )
        selected_urls.extend(urls)

    deduped = source_cards.canonical_dedupe_urls(selected_urls)
    if max_total is not None and max_total > 0:
        deduped = deduped[:max_total]
    return selections, deduped


def write_balanced_receipt(dharma_home: Path, receipt: dict[str, object]) -> str:
    raw_dir = dharma_home / RAW_SOURCE_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"source-card-balanced-expansion-{utc_stamp()}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return str(path)


def run_balanced_expansion(
    *,
    dharma_home: Path,
    topics: list[str] | None = None,
    limit_per_topic: int = 4,
    max_total: int | None = None,
    timeout: int = 30,
    write: bool = False,
    observed_at: str | None = None,
) -> dict[str, object]:
    selected_topics = topics or list(DEFAULT_TOPICS)
    observed = observed_at or iso_now()
    topic_selections, selected_urls = select_balanced_urls(
        dharma_home,
        topics=selected_topics,
        limit_per_topic=max(1, limit_per_topic),
        max_total=max_total,
    )
    outputs: dict[str, object] = {}
    fetch_receipts: list[object] = []
    card_count = 0
    if write:
        source_receipt = source_cards.build_source_cards(
            urls=selected_urls,
            timeout=max(1, timeout),
            observed_at=observed,
        )
        outputs = source_cards.write_outputs(dharma_home, source_receipt)
        source_fetch_receipts = source_receipt.get("receipts")
        if isinstance(source_fetch_receipts, list):
            fetch_receipts = source_fetch_receipts
        card_count = int(source_receipt.get("card_count") or 0)

    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "written" if write else "dry_run",
        "observed_at": observed,
        "boundary": "balanced growth over public docs source-card candidates only; Learn remains manual-review/link-only; no full page/course mirroring",
        "topics": selected_topics,
        "limit_per_topic": max(1, limit_per_topic),
        "max_total": max_total or 0,
        "topic_selections": topic_selections,
        "selected_url_count": len(selected_urls),
        "selected_urls": selected_urls,
        "planned_card_count": len(selected_urls),
        "card_count": card_count,
        "fetch_receipts": fetch_receipts,
        "outputs": outputs,
    }
    if write:
        result["balanced_receipt_path"] = write_balanced_receipt(dharma_home, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dharma-home", default=str(default_dharma_home()))
    parser.add_argument("--topic", action="append", choices=sorted(source_cards.TOPIC_PROFILES), default=[])
    parser.add_argument("--limit-per-topic", type=int, default=4)
    parser.add_argument("--max-total", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    receipt = run_balanced_expansion(
        dharma_home=Path(args.dharma_home).expanduser(),
        topics=args.topic or None,
        limit_per_topic=max(1, args.limit_per_topic),
        max_total=args.max_total if args.max_total > 0 else None,
        timeout=max(1, args.timeout),
        write=not args.dry_run,
    )
    if args.json or args.dry_run:
        print(json.dumps(receipt, indent=2, ensure_ascii=True, default=str))
    else:
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "selected_url_count": receipt["selected_url_count"],
                    "card_count": receipt["card_count"],
                    "outputs": receipt["outputs"],
                    "balanced_receipt_path": receipt.get("balanced_receipt_path", ""),
                },
                indent=2,
                ensure_ascii=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
