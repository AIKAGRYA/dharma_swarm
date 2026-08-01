#!/usr/bin/env python3
"""Deep-ingest allowed public Palantir docs into internal queryable deep cards.

Legal envelope (verified 2026-06-16):
  www.palantir.com/robots.txt -> User-agent: * / Allow: /  (docs crawl-permitted).
  learn.palantir.com returns 403 to automated access and is SKIPPED.
  Non-palantir hosts and gated/private-tenant material are out of scope.

Storage: full parsed public-doc prose + headings, written as deep-card markdown
under the wiki source dir, where index_workspace_to_memory_plane() ingests it into
the queryable memory plane the Palantir Pilot specialist already reads. Internal
RAG use only; the corpus is not redistributed externally.

This reuses the existing crawler/parser (palantir_public_source_cards.fetch_html +
PageFactParser) rather than adding a second scraper. It only stops discarding the
body the parser already extracts.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.palantir_pilot import (  # noqa: E402
    WIKI_SOURCE_DIR,
    _load_latest_source_index,
)
from dharma_swarm.palantir_pilot_manifest import default_dharma_home  # noqa: E402

_CARDER_PATH = REPO_ROOT / "scripts" / "research" / "palantir_public_source_cards.py"
_spec = importlib.util.spec_from_file_location("_ppsc_deep", str(_CARDER_PATH))
if _spec is None or _spec.loader is None:
    raise ModuleNotFoundError(
        f"cannot load source-card module from {_CARDER_PATH} — file missing or unreadable"
    )
carder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(carder)

classify_url = carder.classify_url
slugify = carder.slugify

DEEP_DIR_NAME = "deep-cards"
SKIP_HOST_SUBSTRINGS = ("learn.palantir.com",)
_BLOCK_PARA = ("all rights reserved", "cookie", "privacy policy", "terms of use")


def utc_stamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def deep_extract(html: str) -> tuple[str, str, list[dict[str, str]], list[str]]:
    parser = carder.PageFactParser()
    parser.feed(html)
    seen: set[str] = set()
    paragraphs: list[str] = []
    for para in parser.paragraphs:
        key = para.lower()
        if len(para) < 40 or key in seen:
            continue
        if any(block in key for block in _BLOCK_PARA):
            continue
        seen.add(key)
        paragraphs.append(para)
    return parser.title, parser.meta_description, parser.headings, paragraphs


def render_deep_card(
    *, url: str, title: str, meta: str, headings: list[dict[str, str]], paragraphs: list[str], observed: str
) -> str:
    lines = [
        f"# Palantir Deep Card: {title or url}",
        "",
        f"Source URL: {url}",
        f"Family: `{classify_url(url)}`",
        f"Observed: {observed}",
        "",
        "Boundary: internal RAG corpus for the in-house Palantir specialist. Full text "
        "of a public www.palantir.com docs page (robots Allow: /). Excludes Learn/course "
        "bodies, gated, and private-tenant material. Not redistributed externally.",
        "",
    ]
    if meta:
        lines += ["## Meta", "", meta, ""]
    if headings:
        lines += ["## Headings", ""]
        lines += [f"- {h.get('level')}: {h.get('text')}" for h in headings]
        lines += [""]
    lines += ["## Content", ""]
    lines += paragraphs if paragraphs else ["(no extractable prose; page is media/diagram-heavy)"]
    lines += [""]
    return "\n".join(lines)


# Exact Palantir-controlled hosts (mirrors palantir_public_source_cards.ALLOWED_HOSTS).
# A bare endswith("palantir.com") would also match unrelated hosts like
# evilpalantir.com — pin to the explicit set instead.
ALLOWED_HOSTS = frozenset({"palantir.com", "www.palantir.com"})


def allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":  # sanctioned public docs surface is https-only
        return False
    host = parsed.netloc.lower()
    if any(skip in host for skip in SKIP_HOST_SUBSTRINGS):
        return False
    return host in ALLOWED_HOSTS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dharma-home", default=str(default_dharma_home()))
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--families", default="", help="comma list to restrict, e.g. foundry,gotham")
    ap.add_argument("--delay", type=float, default=0.6, help="seconds between requests (politeness)")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--refresh", action="store_true", help="re-fetch even if deep card exists")
    args = ap.parse_args(argv)

    home = Path(args.dharma_home).expanduser()
    deep_dir = home / WIKI_SOURCE_DIR / DEEP_DIR_NAME
    deep_dir.mkdir(parents=True, exist_ok=True)

    _index_path, payload = _load_latest_source_index(home)
    rows = payload.get("urls") if isinstance(payload, dict) else None
    rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []

    fam_filter = {f.strip() for f in args.families.split(",") if f.strip()}
    urls: list[str] = []
    for row in rows:
        loc = str(row.get("loc") or "")
        if not loc or not allowed(loc):
            continue
        if fam_filter and str(row.get("family") or "") not in fam_filter:
            continue
        urls.append(loc)
    urls = sorted(dict.fromkeys(urls))
    if args.limit > 0:
        urls = urls[: args.limit]

    skipped = failed = written = total_prose = 0
    failures: list[dict[str, str]] = []
    for url in urls:
        slug = slugify(urlparse(url).path.strip("/") or url)
        # slugify already strips path separators; resolve + contain anyway so a
        # URL-derived slug can never write outside the deep-cards directory.
        card_path = (deep_dir / f"{slug}.md").resolve()
        if deep_dir.resolve() not in card_path.parents:
            failed += 1
            failures.append({"url": url, "error": "path_escape"})
            continue
        if card_path.exists() and not args.refresh:
            skipped += 1
            continue
        try:
            status, html, _n = carder.fetch_html(url, timeout=args.timeout)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            failed += 1
            failures.append({"url": url, "error": type(exc).__name__})
            continue
        if status != 200:
            failed += 1
            failures.append({"url": url, "error": f"http_{status}"})
            continue
        title, meta, headings, paragraphs = deep_extract(html)
        card = render_deep_card(
            url=url, title=title, meta=meta, headings=headings, paragraphs=paragraphs, observed=utc_stamp()
        )
        card_path.write_text(card, encoding="utf-8")
        written += 1
        total_prose += sum(len(p) for p in paragraphs)
        if args.delay:
            time.sleep(args.delay)

    receipt = {
        "schema_version": "palantir_pilot.deep_ingest_receipt.v1",
        "observed_at": utc_stamp(),
        "deep_dir": str(deep_dir),
        "candidate_urls": len(urls),
        "written": written,
        "skipped_existing": skipped,
        "failed": failed,
        "total_prose_chars": total_prose,
        "policy": "www.palantir.com robots Allow:/ ; learn.palantir.com excluded; internal RAG only; no redistribution",
        "failures_sample": failures[:25],
    }
    receipt_path = deep_dir / "_deep_ingest_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k != "failures_sample"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
