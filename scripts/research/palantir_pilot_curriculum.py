#!/usr/bin/env python3
"""Build Palantir Pilot curriculum maps from public-source workspace evidence."""

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
    latest_source_index_path,
)
from dharma_swarm.palantir_pilot_manifest import default_dharma_home  # noqa: E402
from scripts.research import palantir_public_source_cards as source_cards  # noqa: E402
from scripts.research.palantir_public_source_index import classify_url  # noqa: E402


LEARN_COURSE_CATALOG_URL = "https://learn.palantir.com/page/course-catalog"

CURRICULUM_SPECS: list[dict[str, object]] = [
    {
        "slug": "foundry-platform-operator",
        "title": "Foundry Platform Operator Curriculum",
        "audience": "Operators and builders orienting to Foundry from first principles.",
        "families": ["foundry"],
        "terms": [
            "getting-started",
            "overview",
            "platform-overview",
            "architecture",
            "start-with-examples",
            "next-steps",
        ],
        "outcome": "Navigate Foundry public docs, distinguish platform concepts, and know which public anchors to read before tenant-specific work.",
    },
    {
        "slug": "ontology-builder",
        "title": "Ontology Builder Curriculum",
        "audience": "Agents or humans modeling operational objects, links, actions, and interfaces.",
        "families": ["foundry", "api_reference"],
        "terms": [
            "ontology",
            "ontologies",
            "object",
            "objects",
            "object-sets",
            "linked-objects",
            "actions",
            "interface",
        ],
        "outcome": "Build a public-source vocabulary for ontology-backed object/action modeling without inventing private tenant doctrine.",
    },
    {
        "slug": "aip-builder-governance",
        "title": "AIP Builder and Governance Curriculum",
        "audience": "Builders learning AIP workflows, model surfaces, observability, and governance boundaries.",
        "families": ["aip", "foundry"],
        "terms": [
            "aip",
            "security",
            "governance",
            "observability",
            "model",
            "models",
            "evals",
            "prompt",
        ],
        "outcome": "Understand AIP as governed AI execution over operational context, not generic chatbot usage.",
    },
    {
        "slug": "developer-osdk-api",
        "title": "Developer OSDK and API Curriculum",
        "audience": "Developers integrating with Foundry APIs, OSDK surfaces, and ontology resources.",
        "families": ["foundry", "api_reference", "defense_osdk"],
        "terms": [
            "api",
            "osdk",
            "sdk",
            "developer",
            "client",
            "typescript",
            "python",
            "ontologies-v2",
        ],
        "outcome": "Locate developer entry points and API families while preserving the distinction between public docs and authorized tenant implementation.",
    },
    {
        "slug": "apollo-operator",
        "title": "Apollo Operator Curriculum",
        "audience": "Operators learning public Apollo release, product, environment, and deployment vocabulary.",
        "families": ["apollo"],
        "terms": [
            "apollo",
            "release",
            "version",
            "environment",
            "deployment",
            "product",
            "channel",
        ],
        "outcome": "Map public Apollo operational concepts before making any private deployment claims.",
    },
    {
        "slug": "gotham-public-analyst",
        "title": "Gotham Public Analyst Curriculum",
        "audience": "Researchers orienting to public Gotham docs without private operational assumptions.",
        "families": ["gotham"],
        "terms": [
            "gotham",
            "target",
            "gaia",
            "geotime",
            "security",
            "api",
            "third-party",
        ],
        "outcome": "Use only public Gotham anchors to separate documented API/security surfaces from restricted product knowledge.",
    },
]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _receipt_stamp(observed_at: str) -> str:
    return (
        observed_at.replace("-", "")
        .replace(":", "")
        .replace(".", "")
        .replace("Z", "Z")
    )


def _load_source_index(dharma_home: Path) -> tuple[Path, dict[str, object], list[dict[str, object]]]:
    path = latest_source_index_path(dharma_home)
    if path is None:
        raise FileNotFoundError(f"No Palantir Pilot source index under {dharma_home / RAW_SOURCE_DIR}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows_raw = payload.get("urls")
    rows = [row for row in rows_raw if isinstance(row, dict)] if isinstance(rows_raw, list) else []
    return path, payload, rows


def _read_source_card_index(dharma_home: Path) -> dict[str, str]:
    index_path = dharma_home / WIKI_SOURCE_DIR / "source-card-index.md"
    if not index_path.exists():
        return {}
    card_urls: dict[str, str] = {}
    for line in index_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("- [") or "](" not in stripped:
            continue
        url = stripped.split("- [", 1)[1].split("](", 1)[0]
        rel = stripped.split("](", 1)[1].rstrip(")")
        if url.startswith("https://"):
            card_urls[url] = str(dharma_home / WIKI_SOURCE_DIR / rel)
    return card_urls


def _score_url(url: str, family: str, spec: dict[str, object]) -> int:
    terms = [str(item).lower() for item in spec.get("terms", [])]
    families = {str(item) for item in spec.get("families", [])}
    path = url.lower()
    score = 0
    if family in families:
        score += 12
    for term in terms:
        score += path.count(term) * 4
    if path.endswith("/overview/") or path.endswith("/getting-started/"):
        score += 2
    if source_cards.has_deprecated_path(path) or "/search/" in path:
        score -= 50
    return score


def _select_evidence(
    rows: list[dict[str, object]],
    source_cards: dict[str, str],
    spec: dict[str, object],
    *,
    limit: int,
) -> list[dict[str, object]]:
    by_url: dict[str, dict[str, object]] = {}
    for row in rows:
        url = str(row.get("loc") or "")
        if not url:
            continue
        family = str(row.get("family") or classify_url(url))
        score = _score_url(url, family, spec)
        if score <= 0:
            continue
        by_url[url] = {
            "score": score,
            "url": url,
            "family": family,
            "lastmod": str(row.get("lastmod") or ""),
            "sitemap": str(row.get("sitemap") or ""),
            "source_card": "",
            "evidence": "public_sitemap_metadata",
        }
    for url, card_path in source_cards.items():
        family = classify_url(url)
        score = _score_url(url, family, spec)
        if score <= 0:
            continue
        if url in by_url:
            by_url[url]["score"] = int(by_url[url]["score"]) + 8
            by_url[url]["source_card"] = card_path
            by_url[url]["evidence"] = "public_sitemap_metadata_and_bounded_source_card"
        else:
            by_url[url] = {
                "score": score + 8,
                "url": url,
                "family": family,
                "lastmod": "",
                "sitemap": "",
                "source_card": card_path,
                "evidence": "bounded_source_card",
            }
    hits = list(by_url.values())
    hits.sort(key=lambda item: (-int(item["score"]), str(item["family"]), str(item["url"])))
    return hits[: max(1, limit)]


def _stage_lines(spec: dict[str, object], hits: list[dict[str, object]]) -> list[str]:
    top_urls = [str(item.get("url") or "") for item in hits[:6]]
    lines = [
        "1. Orientation: read public overview/getting-started anchors and record exact source URLs.",
        "2. Vocabulary: extract terms only from cited public anchors and source cards.",
        "3. Practice boundary: do hands-on work only in an authorized tenant or sandbox supplied by the operator.",
        "4. Governance: mark what is observed from public sources versus inferred from URL structure.",
        "5. Contribution: translate the pattern into a Dharma Swarm note with citations and limitations.",
    ]
    if top_urls:
        lines.append("6. Review queue: promote the strongest anchors into richer source cards after direct public-page review.")
    if spec["slug"] == "aip-builder-governance":
        lines.append("7. AIP guardrail: treat security, observability, evals, and model access as mandatory governance topics.")
    if spec["slug"] == "developer-osdk-api":
        lines.append("7. Developer guardrail: verify API version and tenant authorization before implementation decisions.")
    if spec["slug"] == "gotham-public-analyst":
        lines.append("7. Gotham caveat: do not infer restricted operational doctrine from public API names.")
    return lines


def _curriculum_markdown(
    *,
    spec: dict[str, object],
    observed_at: str,
    source_index: Path,
    total_urls: int,
    hits: list[dict[str, object]],
) -> str:
    lines = [
        f"# {spec['title']}",
        "",
        f"Observed: {observed_at}",
        f"Source index: `{source_index}`",
        f"Indexed URL count: {total_urls}",
        f"Learn catalog: {LEARN_COURSE_CATALOG_URL}",
        "",
        "Boundary: original curriculum synthesis from public URL metadata and bounded source cards only. No Learn course scraping, no full docs mirroring, no videos, no labs, no quizzes, and no private tenant material.",
        "",
        "## Audience",
        "",
        str(spec["audience"]),
        "",
        "## Outcome",
        "",
        str(spec["outcome"]),
        "",
        "## Learning Stages",
        "",
        *_stage_lines(spec, hits),
        "",
        "## Evidence Anchors",
        "",
    ]
    if not hits:
        lines.append("- No public-source anchors selected yet.")
    for hit in hits:
        source_card = str(hit.get("source_card") or "")
        card_note = f" source_card={source_card}" if source_card else ""
        lines.append(
            "- score={score} family={family} evidence={evidence} lastmod={lastmod} {url}{card_note}".format(
                score=hit.get("score", 0),
                family=hit.get("family", ""),
                evidence=hit.get("evidence", ""),
                lastmod=hit.get("lastmod", ""),
                url=hit.get("url", ""),
                card_note=card_note,
            )
        )
    lines.extend(
        [
            "",
            "## Learn Catalog Handling",
            "",
            f"`{LEARN_COURSE_CATALOG_URL}` is intentionally not fetched by this script. If an authorized human reviews it, record only course titles, public URLs, short original summaries, observed dates, and source-rights notes in the manual intake queue. Do not paste course bodies, transcripts, labs, quizzes, or gated materials.",
            "",
            "## Mastery Gap",
            "",
            "This curriculum is a route map, not a certificate. Palantir Pilot may answer from it only with citations and must tell the operator when stronger public-page review or authorized training is required.",
            "",
        ]
    )
    return "\n".join(lines)


def _manual_intake_markdown(*, observed_at: str) -> str:
    return "\n".join(
        [
            "# Palantir Learn Course Catalog Manual Intake",
            "",
            f"Observed: {observed_at}",
            f"Learn catalog URL: {LEARN_COURSE_CATALOG_URL}",
            "",
            "Boundary: manual-review/link-only. Autonomous fetch of Learn robots returned 403 on 2026-06-14. Do not use browser automation, scraping, credential bypass, enrollment bypass, copied course bodies, videos, transcripts, labs, or quizzes.",
            "",
            "## Allowed Intake Fields",
            "",
            "- `course_title`: title observed by an authorized human reviewer.",
            "- `course_url`: public or authorized catalog URL.",
            "- `observed_at`: ISO timestamp of human observation.",
            "- `observed_by`: reviewer or agent receiving operator-provided notes.",
            "- `source_rights`: why this metadata can be stored.",
            "- `public_summary`: short original summary in the reviewer's own words.",
            "- `related_public_docs`: public docs URLs that can ground follow-up answers.",
            "- `confidence`: low, medium, or high with reason.",
            "",
            "## Empty Intake Template",
            "",
            "```json",
            "{",
            '  "course_title": "",',
            '  "course_url": "",',
            '  "observed_at": "",',
            '  "observed_by": "",',
            '  "source_rights": "operator-provided metadata only",',
            '  "public_summary": "",',
            '  "related_public_docs": [],',
            '  "confidence": "low"',
            "}",
            "```",
            "",
            "## Current Status",
            "",
            "No Learn course catalog entries have been ingested autonomously. Palantir Pilot can still build public-doc curriculum paths and can merge operator-provided course metadata later under this schema.",
            "",
        ]
    )


def build_curriculum_maps(
    *,
    dharma_home: Path,
    limit_per_path: int = 12,
) -> dict[str, object]:
    source_index, payload, rows = _load_source_index(dharma_home)
    observed_at = iso_now()
    source_cards = _read_source_card_index(dharma_home)
    out_dir = dharma_home / WIKI_SOURCE_DIR / "curriculum"
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[dict[str, object]] = []
    for spec in CURRICULUM_SPECS:
        hits = _select_evidence(
            rows,
            source_cards,
            spec,
            limit=limit_per_path,
        )
        path = out_dir / f"{spec['slug']}.md"
        path.write_text(
            _curriculum_markdown(
                spec=spec,
                observed_at=observed_at,
                source_index=source_index,
                total_urls=int(payload.get("url_count") or len(rows)),
                hits=hits,
            ),
            encoding="utf-8",
        )
        written.append(
            {
                "slug": spec["slug"],
                "path": str(path),
                "source_count": len(hits),
            }
        )

    intake_path = dharma_home / WIKI_SOURCE_DIR / "learn-course-catalog-intake.md"
    intake_path.write_text(_manual_intake_markdown(observed_at=observed_at), encoding="utf-8")

    index_path = dharma_home / WIKI_SOURCE_DIR / "curriculum-index.md"
    index_lines = [
        "# Palantir Pilot Curriculum Index",
        "",
        f"Observed: {observed_at}",
        f"Source index: `{source_index}`",
        f"Learn catalog URL: {LEARN_COURSE_CATALOG_URL}",
        "",
        "Boundary: public-source curriculum synthesis only. Learn remains manual-review/link-only until an allowed autonomous access path is established.",
        "",
        "## Curriculum Paths",
        "",
    ]
    for item in written:
        index_lines.append(
            f"- [{item['slug']}](curriculum/{item['slug']}.md) - {item['source_count']} evidence anchors"
        )
    index_lines.extend(
        [
            "",
            "## Learn Intake",
            "",
            "- [learn-course-catalog-intake](learn-course-catalog-intake.md) - manual metadata schema and boundary.",
            "",
            "## Query Surface",
            "",
            "Use `python3 scripts/research/palantir_pilot_query.py \"course curriculum ontology\" --answer --json --index-workspace --record-db` to refresh the database and query this layer.",
            "",
        ]
    )
    index_path.write_text("\n".join(index_lines), encoding="utf-8")

    receipt = {
        "schema_version": "palantir_pilot.curriculum_receipt.v1",
        "observed_at": observed_at,
        "source_index": str(source_index),
        "output_index": str(index_path),
        "learn_intake": str(intake_path),
        "curriculum_paths": written,
        "source_card_count": len(source_cards),
        "indexed_url_count": int(payload.get("url_count") or len(rows)),
        "boundary": "public metadata/source-card synthesis only; Learn manual-review/link-only; no full page/course mirroring",
    }
    receipt_path = (
        dharma_home
        / RAW_SOURCE_DIR
        / f"curriculum-receipt-{_receipt_stamp(observed_at)}.json"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dharma-home", default=str(default_dharma_home()))
    parser.add_argument("--limit-per-path", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    receipt = build_curriculum_maps(
        dharma_home=Path(args.dharma_home).expanduser(),
        limit_per_path=max(1, args.limit_per_path),
    )
    if args.json:
        print(json.dumps(receipt, indent=2, ensure_ascii=True))
    else:
        print(f"wrote {len(receipt['curriculum_paths'])} curriculum paths: {receipt['output_index']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
