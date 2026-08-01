#!/usr/bin/env python3
"""Generate Palantir Pilot orientation maps from public sitemap metadata."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
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


MAP_SPECS: list[dict[str, object]] = [
    {
        "slug": "foundry-platform",
        "title": "Foundry Platform Map",
        "families": ["foundry"],
        "terms": ["getting-started", "platform-overview", "architecture-center", "guides-and-workflows"],
        "focus": "Foundry navigation, platform overview, architecture center, and workflow entry points.",
    },
    {
        "slug": "ontology-object-action",
        "title": "Ontology Object/Action Modeling Map",
        "families": ["foundry", "api_reference"],
        "terms": ["ontology", "ontologies", "object", "objects", "action", "actions"],
        "focus": "Ontology system, objects/object sets, actions, and operational modeling vocabulary.",
    },
    {
        "slug": "aip-workflows",
        "title": "AIP Workflow and Governance Map",
        "families": ["aip", "aip_marketing", "foundry"],
        "terms": ["aip", "llm", "prompt", "security", "governance", "evals", "chatbot", "assist"],
        "focus": "AIP capabilities, model/provider surfaces, prompt practice, security/governance, evals, Assist, and chatbot workflows.",
    },
    {
        "slug": "apollo-operations",
        "title": "Apollo Operations Map",
        "families": ["apollo"],
        "terms": ["apollo", "product", "release", "version", "environment", "deployment", "release-channel"],
        "focus": "Apollo public docs around products, releases, versions, channels, environments, and deployment operations.",
    },
    {
        "slug": "gotham-public-docs",
        "title": "Gotham Public Docs Map",
        "families": ["gotham"],
        "terms": ["gotham", "api", "target", "geotime", "gaia", "third-party", "security"],
        "focus": "Gotham public docs visible in the sitemap: security/third-party application docs and API reference families.",
    },
    {
        "slug": "osdk-api-developer",
        "title": "OSDK and API Developer Map",
        "families": ["api_reference", "defense_osdk", "foundry"],
        "terms": ["osdk", "sdk", "api", "developer", "ontologies-v2", "client", "typescript", "python"],
        "focus": "Developer entry points for API reference, Defense OSDK, SDK/client, and Ontologies API surfaces.",
    },
    {
        "slug": "course-path-boundary",
        "title": "Course Path Boundary Map",
        "families": ["foundry", "aip", "apollo", "gotham", "defense_osdk"],
        "terms": ["getting-started", "overview", "training", "examples", "course", "learn"],
        "focus": "Public/manual-review training path: public getting-started pages plus Learn course catalog boundary.",
    },
]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_index(dharma_home: Path) -> tuple[Path, dict[str, object]]:
    path = latest_source_index_path(dharma_home)
    if path is None:
        raise FileNotFoundError(f"No Palantir Pilot source index under {dharma_home / RAW_SOURCE_DIR}")
    return path, json.loads(path.read_text(encoding="utf-8"))


def _score_url(row: dict[str, object], spec: dict[str, object]) -> int:
    url = str(row.get("loc") or "").lower()
    family = str(row.get("family") or "")
    families = set(str(item) for item in spec.get("families", []))
    terms = [str(item).lower() for item in spec.get("terms", [])]
    score = 3 if family in families else 0
    score += sum(url.count(term) for term in terms)
    return score


def _select_sources(
    rows: list[dict[str, object]],
    spec: dict[str, object],
    *,
    limit: int,
) -> list[dict[str, object]]:
    scored: list[dict[str, object]] = []
    for row in rows:
        score = _score_url(row, spec)
        if score <= 0:
            continue
        scored.append(
            {
                "score": score,
                "url": str(row.get("loc") or ""),
                "family": str(row.get("family") or ""),
                "lastmod": str(row.get("lastmod") or ""),
                "sitemap": str(row.get("sitemap") or ""),
            }
        )
    scored.sort(key=lambda item: (-int(item["score"]), item["family"], item["url"]))
    return scored[:limit]


def _map_markdown(
    *,
    spec: dict[str, object],
    observed_at: str,
    index_path: Path,
    total_urls: int,
    hits: list[dict[str, object]],
) -> str:
    lines = [
        f"# {spec['title']}",
        "",
        f"Observed: {observed_at}",
        f"Source index: `{index_path}`",
        f"Indexed URL count: {total_urls}",
        "",
        "Boundary: public sitemap metadata and original synthesis only. This file does not store Palantir page bodies, course content, videos, labs, quizzes, or private tenant material.",
        "",
        "## Focus",
        "",
        str(spec["focus"]),
        "",
        "## Current Source Anchors",
        "",
    ]
    if not hits:
        lines.append("- No source-index matches yet.")
    for hit in hits:
        lines.append(
            "- score={score} family={family} lastmod={lastmod} {url}".format(
                score=hit["score"],
                family=hit["family"],
                lastmod=hit["lastmod"],
                url=hit["url"],
            )
        )

    lines.extend(
        [
            "",
            "## Working Interpretation",
            "",
            "This is a navigation map, not a mastery claim. Palantir Pilot should use these anchors to build source-grounded answers, compare concepts against Dharma Swarm, and record stronger summaries only after reading specific public pages.",
            "",
            "## Next Questions",
            "",
            "- Which anchors are conceptual overview pages versus API reference endpoints?",
            "- Which terms recur across Foundry, AIP, Apollo, Gotham, and OSDK surfaces?",
            "- What is observed directly from public docs, and what is only inferred from URL structure?",
            "",
        ]
    )
    if spec["slug"] == "course-path-boundary":
        lines.extend(
            [
                "## Learn Boundary",
                "",
                "The requested Learn catalog URL remains link/manual-review only: https://learn.palantir.com/page/course-catalog. Autonomous fetch observed a 403 boundary on 2026-06-14, so Palantir Pilot must not scrape it unless an allowed access path is established.",
                "",
            ]
        )
    if spec["slug"] == "gotham-public-docs":
        lines.extend(
            [
                "## Public-Surface Caveat",
                "",
                "The sitemap exposes substantial Gotham API/security anchors, but it does not by itself prove access to full Gotham product training or private operational doctrine. Treat this map as public-doc navigation only.",
                "",
            ]
        )
    return "\n".join(lines)


def build_orientation_maps(
    *,
    dharma_home: Path,
    limit_per_map: int = 24,
) -> dict[str, object]:
    index_path, payload = _load_index(dharma_home)
    rows_raw = payload.get("urls")
    rows = [row for row in rows_raw if isinstance(row, dict)] if isinstance(rows_raw, list) else []
    observed_at = iso_now()
    out_dir = dharma_home / WIKI_SOURCE_DIR / "maps"
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[dict[str, object]] = []
    for spec in MAP_SPECS:
        hits = _select_sources(rows, spec, limit=limit_per_map)
        path = out_dir / f"{spec['slug']}.md"
        path.write_text(
            _map_markdown(
                spec=spec,
                observed_at=observed_at,
                index_path=index_path,
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

    index_path_md = dharma_home / WIKI_SOURCE_DIR / "orientation-index.md"
    index_lines = [
        "# Palantir Pilot Orientation Index",
        "",
        f"Observed: {observed_at}",
        f"Source index: `{index_path}`",
        "",
        "This index links the first durable public-source orientation maps. The maps are generated from sitemap metadata and are navigation scaffolds, not full-page mirrors or private-training substitutes.",
        "",
        "## Maps",
        "",
    ]
    for item in written:
        index_lines.append(f"- [{item['slug']}](maps/{item['slug']}.md) - {item['source_count']} source anchors")
    index_lines.extend(
        [
            "",
            "## Query Surface",
            "",
            "Use `python3 scripts/research/palantir_pilot_query.py \"ontology\" --json --limit 3` to search the local source index and notes.",
            "",
        ]
    )
    index_path_md.write_text("\n".join(index_lines), encoding="utf-8")

    receipt = {
        "schema_version": "palantir_pilot.orientation_receipt.v1",
        "observed_at": observed_at,
        "source_index": str(index_path),
        "output_index": str(index_path_md),
        "maps": written,
        "boundary": "public sitemap metadata only; no full page/course mirroring",
    }
    receipt_path = dharma_home / RAW_SOURCE_DIR / f"orientation-receipt-{observed_at.replace(':', '').replace('-', '')}.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dharma-home", default=str(default_dharma_home()))
    parser.add_argument("--limit-per-map", type=int, default=24)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    receipt = build_orientation_maps(
        dharma_home=Path(args.dharma_home).expanduser(),
        limit_per_map=max(1, args.limit_per_map),
    )
    if args.json:
        print(json.dumps(receipt, indent=2, ensure_ascii=True))
    else:
        print(f"wrote {len(receipt['maps'])} maps: {receipt['output_index']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
