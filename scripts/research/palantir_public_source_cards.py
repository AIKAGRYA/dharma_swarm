#!/usr/bin/env python3
"""Build copyright-safe source cards for selected public Palantir docs pages."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import re
import ssl
from datetime import datetime, timezone
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.palantir_pilot import (  # noqa: E402
    RAW_SOURCE_DIR,
    WIKI_SOURCE_DIR,
    latest_source_index_path,
)
from dharma_swarm.palantir_pilot_manifest import default_dharma_home  # noqa: E402
from scripts.research.palantir_public_source_index import classify_url  # noqa: E402


USER_AGENT = "DharmaSwarmPalantirPilot/0.1 public-source-cards"
ALLOWED_HOSTS = {"palantir.com", "www.palantir.com"}
DEFAULT_ANCHOR_SUFFIXES = (
    "/docs/foundry/getting-started/overview/",
    "/docs/foundry/platform-overview/architecture/",
    "/docs/foundry/architecture-center/ontology-system/",
    "/docs/foundry/aip/overview/",
    "/docs/foundry/aip/ethics-governance/",
    "/docs/foundry/ontology-sdk/overview/",
    "/docs/foundry/api-reference/",
    "/docs/apollo/",
    "/docs/gotham/",
    "/docs/defense-osdk/",
)

TOPIC_PROFILES: dict[str, dict[str, tuple[str, ...]]] = {
    "foundry-core": {
        "families": ("foundry",),
        "terms": (
            "getting-started",
            "platform-overview",
            "architecture-center",
            "projects",
            "resources",
            "application",
            "workflow",
        ),
    },
    "ontology": {
        "families": ("foundry", "api_reference"),
        "terms": (
            "ontology",
            "ontologies",
            "object",
            "objects",
            "action",
            "actions",
            "interface",
            "link",
            "properties",
        ),
    },
    "aip": {
        "families": ("aip", "foundry"),
        "terms": (
            "aip",
            "llm",
            "prompt",
            "governance",
            "security",
            "evals",
            "observability",
            "assist",
            "chatbot",
            "model",
        ),
    },
    "osdk-api": {
        "families": ("foundry", "api_reference", "defense_osdk"),
        "terms": (
            "osdk",
            "sdk",
            "api",
            "developer",
            "ontologies-v2",
            "client",
            "typescript",
            "python",
            "developer-console",
        ),
    },
    "apollo": {
        "families": ("apollo",),
        "terms": (
            "apollo",
            "release",
            "version",
            "deployment",
            "environment",
            "product",
            "change-management",
        ),
    },
    "gotham": {
        "families": ("gotham",),
        "terms": (
            "gotham",
            "security",
            "api",
            "third-party",
            "geotime",
            "gaia",
            "target",
        ),
    },
    "course-path": {
        "families": ("foundry", "aip", "apollo", "gotham", "defense_osdk"),
        "terms": (
            "getting-started",
            "overview",
            "training",
            "examples",
            "start-with-examples",
            "next-steps",
        ),
    },
}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:120] or "source-card"


def normalize_space(value: str) -> str:
    ascii_value = (
        value.replace("\u2022", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    ascii_value = ascii_value.encode("ascii", errors="ignore").decode("ascii")
    return " ".join(ascii_value.split()).strip()


def is_allowed_source_card_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path
    blocked_prefixes = (
        "/docs/500/",
        "/docs/feedback/",
        "/docs/jp/",
        "/docs/kr/",
        "/docs/zh/",
        "/docs/versions/",
    )
    return (
        parsed.scheme == "https"
        and parsed.netloc in ALLOWED_HOSTS
        and path.startswith("/docs/")
        and not any(path.startswith(prefix) for prefix in blocked_prefixes)
        and not has_deprecated_path(path)
        and "/search/" not in path
    )


def has_deprecated_path(value: str) -> bool:
    path = urlparse(value).path or value
    return any("deprecated" in segment.lower() for segment in path.split("/") if segment)


def canonical_source_url(url: str) -> str:
    parsed = urlparse(url)
    path = re.sub(r"/api/v[0-9]+/", "/api/", parsed.path)
    path = re.sub(r"/+", "/", path).rstrip("/")
    return f"{parsed.netloc.lower()}{path}"


def fetch_html(url: str, *, timeout: int = 30) -> tuple[int, str, int]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context()
    with urlopen(request, timeout=timeout, context=context) as response:
        body = response.read()
        return int(response.status), body.decode("utf-8", errors="replace"), len(body)


class PageFactParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self.headings: list[dict[str, str]] = []
        self.paragraphs: list[str] = []
        self._tag_stack: list[str] = []
        self._current: list[str] = []
        self._capture_tag = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript"}:
            self._tag_stack.append(tag)
            return
        if tag == "meta" and attr_map.get("name", "").lower() == "description":
            self.meta_description = normalize_space(attr_map.get("content", ""))
            return
        if tag in {"title", "h1", "h2", "h3", "p"}:
            self._capture_tag = tag
            self._current = []

    def handle_endtag(self, tag: str) -> None:
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
            return
        if tag != self._capture_tag:
            return
        text = normalize_space("".join(self._current))
        if text:
            if tag == "title" and not self.title:
                self.title = text
            elif tag in {"h1", "h2", "h3"}:
                self.headings.append({"level": tag, "text": text})
            elif tag == "p":
                self.paragraphs.append(text)
        self._capture_tag = ""
        self._current = []

    def handle_data(self, data: str) -> None:
        if self._tag_stack:
            return
        if self._capture_tag:
            self._current.append(data)


def extract_page_facts(html: str) -> dict[str, object]:
    parser = PageFactParser()
    parser.feed(html)
    unique_paragraphs: list[str] = []
    seen: set[str] = set()
    for paragraph in parser.paragraphs:
        paragraph_lower = paragraph.lower()
        if any(
            blocked in paragraph_lower
            for blocked in (
                "all rights reserved",
                "cookie",
                "privacy policy",
                "terms of use",
            )
        ):
            continue
        if len(paragraph) < 40:
            continue
        key = paragraph_lower
        if key in seen:
            continue
        seen.add(key)
        unique_paragraphs.append(paragraph)
    short_excerpt = unique_paragraphs[0][:280] if unique_paragraphs else ""
    if not short_excerpt and parser.meta_description:
        short_excerpt = parser.meta_description[:280]
    return {
        "title": parser.title,
        "meta_description": parser.meta_description,
        "headings": parser.headings[:18],
        "short_excerpt": short_excerpt,
    }


def source_card_from_html(
    *,
    url: str,
    html: str,
    status: int,
    bytes_fetched: int,
    observed_at: str,
) -> dict[str, object]:
    facts = extract_page_facts(html)
    parsed = urlparse(url)
    return {
        "schema_version": "palantir_pilot.source_card.v1",
        "url": url,
        "family": classify_url(url),
        "slug": slugify(parsed.path.strip("/") or url),
        "observed_at": observed_at,
        "fetch": {
            "status": status,
            "bytes": bytes_fetched,
            "user_agent": USER_AGENT,
            "policy": "public docs page fetched under www.palantir.com robots Allow: /",
        },
        "facts": facts,
        "storage_boundary": (
            "Stores title, meta description, headings, one short excerpt, and original "
            "orientation only. Does not store full page body, course body, videos, labs, "
            "quizzes, private tenant material, or gated Learn content."
        ),
    }


def load_source_index_rows(dharma_home: Path) -> list[dict[str, object]]:
    path = latest_source_index_path(dharma_home)
    if path is None:
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("urls")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def existing_card_urls(dharma_home: Path) -> set[str]:
    card_dir = dharma_home / WIKI_SOURCE_DIR / "source-cards"
    urls: set[str] = set()
    if not card_dir.exists():
        return urls
    for path in card_dir.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            if line.startswith("Source URL: "):
                url = line.split("Source URL: ", 1)[1].strip()
                if url:
                    urls.add(url)
                break
    return urls


def select_default_urls(dharma_home: Path, *, limit: int) -> list[str]:
    rows = load_source_index_rows(dharma_home)
    by_suffix: dict[str, str] = {}
    for row in rows:
        loc = str(row.get("loc") or "")
        if not is_allowed_source_card_url(loc):
            continue
        parsed = urlparse(loc)
        by_suffix[parsed.path] = loc

    urls: list[str] = []
    for suffix in DEFAULT_ANCHOR_SUFFIXES:
        url = by_suffix.get(suffix) or f"https://palantir.com{suffix}"
        if is_allowed_source_card_url(url):
            urls.append(url)
    return urls[: max(1, limit)]


def expand_topic_filters(
    *,
    topics: list[str],
    families: list[str],
    terms: list[str],
) -> tuple[list[str], list[str]]:
    family_values = list(families)
    term_values = list(terms)
    for topic in topics:
        profile = TOPIC_PROFILES.get(topic)
        if not profile:
            continue
        family_values.extend(profile["families"])
        term_values.extend(profile["terms"])
    deduped_families = list(dict.fromkeys(item for item in family_values if item))
    deduped_terms = list(dict.fromkeys(item.lower() for item in term_values if item))
    return deduped_families, deduped_terms


def _source_card_candidate_score(
    row: dict[str, object],
    *,
    families: set[str],
    terms: list[str],
) -> int:
    url = str(row.get("loc") or "")
    if not is_allowed_source_card_url(url):
        return 0
    family = str(row.get("family") or "")
    path = urlparse(url).path.lower()
    score = 0
    if families and family in families:
        score += 20
    if not families:
        score += 1
    for term in terms:
        score += path.count(term.lower()) * 5
    if path.count("/") <= 4:
        score += 2
    if path.endswith("/overview/") or path.endswith("/"):
        score += 2
    return score


def select_index_urls(
    dharma_home: Path,
    *,
    limit: int,
    families: list[str] | None = None,
    terms: list[str] | None = None,
    topics: list[str] | None = None,
    include_defaults: bool = False,
    skip_existing: bool = True,
) -> list[str]:
    effective_families, effective_terms = expand_topic_filters(
        topics=topics or [],
        families=families or [],
        terms=terms or [],
    )
    family_filter = set(effective_families)
    existing = existing_card_urls(dharma_home) if skip_existing else set()
    existing_canonical = {canonical_source_url(url) for url in existing}
    rows = load_source_index_rows(dharma_home)

    candidates: list[dict[str, object]] = []
    for row in rows:
        url = str(row.get("loc") or "")
        canonical = canonical_source_url(url)
        if skip_existing and (url in existing or canonical in existing_canonical):
            continue
        score = _source_card_candidate_score(
            row,
            families=family_filter,
            terms=effective_terms,
        )
        if score <= 0:
            continue
        candidates.append(
            {
                "score": score,
                "url": url,
                "canonical": canonical,
                "family": str(row.get("family") or ""),
            }
        )
    candidates.sort(key=lambda item: (-int(item["score"]), str(item["family"]), str(item["url"])))
    urls: list[str] = []
    selected_canonical: set[str] = set()
    for item in candidates:
        canonical = str(item.get("canonical") or canonical_source_url(str(item["url"])))
        if canonical in selected_canonical:
            continue
        selected_canonical.add(canonical)
        urls.append(str(item["url"]))
    if include_defaults:
        default_urls = select_default_urls(dharma_home, limit=limit)
        urls = canonical_dedupe_urls([*default_urls, *urls])
    return urls[: max(1, limit)]


def canonical_dedupe_urls(urls: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        canonical = canonical_source_url(url)
        if canonical in seen:
            continue
        seen.add(canonical)
        deduped.append(url)
    return deduped


def card_source_url(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in text.splitlines():
        if line.startswith("Source URL: "):
            return line.split("Source URL: ", 1)[1].strip()
    return ""


def card_markdown(card: dict[str, object]) -> str:
    facts = card.get("facts")
    facts_map = facts if isinstance(facts, dict) else {}
    headings = facts_map.get("headings")
    heading_rows = [item for item in headings if isinstance(item, dict)] if isinstance(headings, list) else []
    heading_lines = [
        f"- `{item.get('level', '')}` {item.get('text', '')}"
        for item in heading_rows[:12]
    ]
    if not heading_lines:
        heading_lines = ["- No headings extracted from the fetched public page."]

    title = str(facts_map.get("title") or "")
    description = str(facts_map.get("meta_description") or "")
    excerpt = str(facts_map.get("short_excerpt") or "")
    url = str(card.get("url") or "")
    family = str(card.get("family") or "")

    lines = [
        f"# Palantir Source Card: {title or url}",
        "",
        f"Observed: {card.get('observed_at', '')}",
        f"Source URL: {url}",
        f"Family: `{family}`",
        "",
        "Boundary: title, metadata, headings, one short excerpt, and original orientation only. No full page/course mirroring.",
        "",
        "## Source Summary",
        "",
        f"- Title: {title or 'not extracted'}",
        f"- Meta description: {description or 'not extracted'}",
        f"- Short excerpt: {excerpt or 'not extracted'}",
        "",
        "## Extracted Headings",
        "",
        *heading_lines,
        "",
        "## Practical Orientation",
        "",
        (
            f"This public docs page is a reviewed Palantir Pilot anchor for `{family}`. "
            "Use it to ground answers, then follow the source URL directly for exact "
            "implementation details."
        ),
        "",
        "## Storage Boundary",
        "",
        str(card.get("storage_boundary") or ""),
        "",
    ]
    return "\n".join(lines)


def build_source_cards(
    *,
    urls: list[str],
    timeout: int = 30,
    observed_at: str | None = None,
) -> dict[str, object]:
    observed = observed_at or iso_now()
    cards: list[dict[str, object]] = []
    receipts: list[dict[str, object]] = []
    for url in urls:
        if not is_allowed_source_card_url(url):
            receipts.append({"url": url, "status": "skipped:not_allowed"})
            continue
        try:
            status, html, byte_count = fetch_html(url, timeout=timeout)
        except (HTTPError, URLError, TimeoutError, ssl.SSLError) as exc:
            receipts.append({"url": url, "status": f"fetch_failed:{type(exc).__name__}"})
            continue
        card = source_card_from_html(
            url=url,
            html=html,
            status=status,
            bytes_fetched=byte_count,
            observed_at=observed,
        )
        cards.append(card)
        receipts.append({"url": url, "status": "card_written", "bytes": byte_count})

    return {
        "schema_version": "palantir_pilot.source_card_receipt.v1",
        "observed_at": observed,
        "policy": {
            "mode": "bounded_public_docs_source_cards",
            "allowed_hosts": sorted(ALLOWED_HOSTS),
            "learn_course_catalog": "manual-review/link-only; not fetched",
            "storage_rule": "No full page body mirroring. Store facts, tiny excerpts, original summaries, and citations only.",
        },
        "cards": cards,
        "receipts": receipts,
        "card_count": len(cards),
    }


def write_outputs(dharma_home: Path, receipt: dict[str, object]) -> dict[str, object]:
    stamp = utc_stamp()
    raw_dir = dharma_home / RAW_SOURCE_DIR / "source-cards"
    card_dir = dharma_home / WIKI_SOURCE_DIR / "source-cards"
    raw_dir.mkdir(parents=True, exist_ok=True)
    card_dir.mkdir(parents=True, exist_ok=True)

    cards = receipt.get("cards")
    card_rows = [item for item in cards if isinstance(item, dict)] if isinstance(cards, list) else []
    written_cards: list[dict[str, str]] = []
    for card in card_rows:
        slug = str(card.get("slug") or slugify(str(card.get("url") or "source-card")))
        path = card_dir / f"{slug}.md"
        path.write_text(card_markdown(card), encoding="utf-8")
        written_cards.append({"url": str(card.get("url") or ""), "path": str(path)})

    receipt_path = raw_dir / f"source-cards-{stamp}.json"
    receipt_with_paths = {**receipt, "written_cards": written_cards}
    receipt_path.write_text(
        json.dumps(receipt_with_paths, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    index_path = dharma_home / WIKI_SOURCE_DIR / "source-card-index.md"
    all_cards = sorted(card_dir.glob("*.md"))
    indexed_cards: list[dict[str, str]] = []
    for path in all_cards:
        indexed_cards.append(
            {
                "url": card_source_url(path) or path.stem,
                "path": str(path),
            }
        )

    lines = [
        "# Palantir Pilot Source Card Index",
        "",
        f"Observed: {receipt.get('observed_at', '')}",
        f"Card count: {len(indexed_cards)}",
        f"Latest batch card count: {len(written_cards)}",
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
        "receipt_path": str(receipt_path),
        "index_path": str(index_path),
        "card_paths": [item["path"] for item in written_cards],
        "index_card_count": len(indexed_cards),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dharma-home", default=str(default_dharma_home()))
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--topic", action="append", choices=sorted(TOPIC_PROFILES), default=[])
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--term", action="append", default=[])
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--include-default-anchors", action="store_true")
    parser.add_argument("--include-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    dharma_home = Path(args.dharma_home).expanduser()
    if args.url:
        urls = args.url
    elif args.topic or args.family or args.term:
        urls = select_index_urls(
            dharma_home,
            limit=max(1, args.limit),
            families=args.family,
            terms=args.term,
            topics=args.topic,
            include_defaults=args.include_default_anchors,
            skip_existing=not args.include_existing,
        )
    else:
        urls = select_default_urls(dharma_home, limit=max(1, args.limit))
    receipt = build_source_cards(
        urls=urls[: max(1, args.limit)],
        timeout=max(1, args.timeout),
    )
    outputs: dict[str, object] = {}
    if not args.dry_run:
        outputs = write_outputs(dharma_home, receipt)
    result = {"status": "dry_run" if args.dry_run else "written", "outputs": outputs, **receipt}
    if args.json or args.dry_run:
        print(json.dumps(result, indent=2, ensure_ascii=True, default=str))
    else:
        print(json.dumps({"status": result["status"], "outputs": outputs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
