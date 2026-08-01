#!/usr/bin/env python3
"""Index allowed public Palantir sitemap URLs without mirroring page bodies."""

from __future__ import annotations

import argparse
import json
import ssl
from datetime import datetime, timezone
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.palantir_pilot import (  # noqa: E402
    RAW_SOURCE_DIR,
    WIKI_SOURCE_DIR,
    summarize_source_families,
)
from dharma_swarm.palantir_pilot_manifest import default_dharma_home  # noqa: E402


USER_AGENT = "DharmaSwarmPalantirPilot/0.1 public-source-index"
ROBOTS_URL = "https://www.palantir.com/robots.txt"
SITEMAP_URLS = [
    "https://www.palantir.com/docs/sitemap.xml",
    "https://www.palantir.com/sitemap.xml",
]
LEARN_URL = "https://learn.palantir.com/page/course-catalog"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_text(url: str, *, timeout: int = 30) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context()
    with urlopen(request, timeout=timeout, context=context) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_sitemap(xml_text: str) -> list[dict[str, str]]:
    root = ElementTree.fromstring(xml_text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    rows: list[dict[str, str]] = []
    for url_node in root.findall("sm:url", ns):
        loc = url_node.findtext("sm:loc", default="", namespaces=ns).strip()
        if not loc:
            continue
        rows.append(
            {
                "loc": loc,
                "lastmod": url_node.findtext("sm:lastmod", default="", namespaces=ns).strip(),
                "changefreq": url_node.findtext("sm:changefreq", default="", namespaces=ns).strip(),
                "priority": url_node.findtext("sm:priority", default="", namespaces=ns).strip(),
            }
        )
    return rows


def classify_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path
    if path.startswith("/docs/foundry/aip/"):
        return "aip"
    if path.startswith("/docs/foundry/api-reference/"):
        return "api_reference"
    if path.startswith("/docs/foundry/"):
        return "foundry"
    if path.startswith("/docs/apollo/"):
        return "apollo"
    if path.startswith("/docs/gotham/"):
        return "gotham"
    if path.startswith("/docs/defense-osdk/"):
        return "defense_osdk"
    if path.startswith("/docs/"):
        return "docs_other"
    if path.startswith("/platforms/"):
        return "platform_marketing"
    if path.startswith("/aip") or "/aip" in path:
        return "aip_marketing"
    return "site"


def build_index(*, max_urls_per_sitemap: int | None = None) -> dict[str, object]:
    receipts: list[dict[str, object]] = []
    all_urls: list[dict[str, str]] = []

    try:
        robots_text = fetch_text(ROBOTS_URL)
        robots_status = "fetched"
    except (HTTPError, URLError, TimeoutError) as exc:
        robots_text = ""
        robots_status = f"fetch_failed:{type(exc).__name__}"

    receipts.append(
        {
            "url": ROBOTS_URL,
            "status": robots_status,
            "bytes": len(robots_text.encode("utf-8")),
        }
    )

    for sitemap_url in SITEMAP_URLS:
        try:
            xml_text = fetch_text(sitemap_url)
            rows = parse_sitemap(xml_text)
            if max_urls_per_sitemap is not None:
                rows = rows[:max_urls_per_sitemap]
            for row in rows:
                row["sitemap"] = sitemap_url
                row["family"] = classify_url(row["loc"])
            all_urls.extend(rows)
            receipts.append(
                {
                    "url": sitemap_url,
                    "status": "fetched",
                    "bytes": len(xml_text.encode("utf-8")),
                    "url_count": len(rows),
                }
            )
        except (ElementTree.ParseError, HTTPError, URLError, TimeoutError) as exc:
            receipts.append(
                {
                    "url": sitemap_url,
                    "status": f"fetch_failed:{type(exc).__name__}",
                    "url_count": 0,
                }
            )

    family_counts = summarize_source_families([row["loc"] for row in all_urls])
    classifier_counts: dict[str, int] = {}
    for row in all_urls:
        family = row["family"]
        classifier_counts[family] = classifier_counts.get(family, 0) + 1

    return {
        "schema_version": "palantir_pilot.public_source_index.v1",
        "observed_at": iso_now(),
        "policy": {
            "mode": "sitemap_index_only",
            "robots_url": ROBOTS_URL,
            "learn_course_catalog": LEARN_URL,
            "learn_access_status": "not_fetched_by_this_script; autonomous fetch previously observed robots 403",
            "storage_rule": "URLs and metadata only. No page body mirroring.",
        },
        "receipts": receipts,
        "url_count": len(all_urls),
        "family_counts": family_counts,
        "classifier_counts": dict(sorted(classifier_counts.items())),
        "urls": all_urls,
    }


def write_outputs(dharma_home: Path, payload: dict[str, object]) -> dict[str, str]:
    raw_dir = dharma_home / RAW_SOURCE_DIR
    research_dir = dharma_home / WIKI_SOURCE_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    research_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    json_path = raw_dir / f"source-index-{stamp}.json"
    md_path = research_dir / f"source-index-{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    family_lines = [
        f"- `{family}`: {count}"
        for family, count in sorted((payload.get("classifier_counts") or {}).items())
    ]
    md_path.write_text(
        "\n".join(
            [
                "# Palantir Public Source Index",
                "",
                f"Observed: {payload['observed_at']}",
                f"URL count: {payload['url_count']}",
                "",
                "## Policy",
                "",
                "Sitemap URL and metadata index only. No page body mirroring. Learn course catalog remains link/manual-review only until allowed access is confirmed.",
                "",
                "## Families",
                "",
                *family_lines,
                "",
                "## Machine Artifact",
                "",
                f"`{json_path}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {"json_path": str(json_path), "markdown_path": str(md_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dharma-home", default=str(default_dharma_home()))
    parser.add_argument("--max-urls-per-sitemap", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    limit = args.max_urls_per_sitemap if args.max_urls_per_sitemap > 0 else None
    payload = build_index(max_urls_per_sitemap=limit)
    outputs: dict[str, str] = {}
    if not args.dry_run:
        outputs = write_outputs(Path(args.dharma_home).expanduser(), payload)
    result = {"status": "dry_run" if args.dry_run else "written", "outputs": outputs, **payload}
    if args.json or args.dry_run:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print(json.dumps({"status": result["status"], "outputs": outputs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
