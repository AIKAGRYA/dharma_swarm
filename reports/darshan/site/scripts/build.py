#!/usr/bin/env python3
"""Build the zero-dependency Darshan static site deterministically."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
from pathlib import Path
from typing import Any


SITE_ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = SITE_ROOT / "content"
OUTPUT_DIR = SITE_ROOT / "public"
REQUIRED_METADATA = ("title", "slug", "desk", "summary", "published_at")

STYLE = """
:root{color-scheme:light dark;--paper:#f4f0e7;--ink:#201f1b;--muted:#68645b;
--line:#b9b1a3;--accent:#6b2c24}*{box-sizing:border-box}body{margin:0;
font:18px/1.72 Georgia,serif;background:var(--paper);color:var(--ink)}
main,header,footer{max-width:780px;margin:auto;padding:2rem 1.2rem}header{padding-top:4rem;
border-bottom:1px solid var(--line)}h1,h2,h3{line-height:1.18}h1{font-size:clamp(2.5rem,8vw,5rem);
letter-spacing:-.04em}h2{margin-top:2.6rem}.kicker,.meta,footer{color:var(--muted);
font:14px/1.5 system-ui,sans-serif;letter-spacing:.04em}.summary{font-size:1.25rem}
a{color:var(--accent);text-underline-offset:.18em}article a{overflow-wrap:anywhere}
blockquote{border-left:3px solid var(--accent);margin-left:0;padding-left:1.2rem}
code,pre{font:14px/1.5 ui-monospace,monospace}pre{overflow:auto;padding:1rem;
border:1px solid var(--line)}.issue-list{list-style:none;padding:0}.issue-list li{
padding:1.2rem 0;border-bottom:1px solid var(--line)}.issue-list h2{margin:.2rem 0}
.register{font:13px/1.4 system-ui,sans-serif;text-transform:uppercase;
letter-spacing:.08em;color:var(--accent)}@media(prefers-color-scheme:dark){:root{
--paper:#171714;--ink:#eee9dd;--muted:#aaa294;--line:#504b43;--accent:#e6a296}}
""".strip()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_source(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: frontmatter is required")
    try:
        raw_meta, body = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError(f"{path}: frontmatter is not terminated") from exc
    metadata: dict[str, str] = {}
    for line in raw_meta.splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"{path}: malformed frontmatter line {line!r}")
        metadata[key.strip()] = value.strip().strip("\"'")
    missing = [key for key in REQUIRED_METADATA if not metadata.get(key)]
    if missing:
        raise ValueError(f"{path}: missing metadata {', '.join(missing)}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", metadata["slug"]):
        raise ValueError(f"{path}: invalid slug {metadata['slug']!r}")
    return metadata, body.strip()


def _inline(text: str) -> str:
    escaped = html.escape(text, quote=True)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)

    def link(match: re.Match[str]) -> str:
        label, url = match.group(1), html.unescape(match.group(2))
        if not (url.startswith(("https://", "http://", "/", "#"))):
            return label
        return f'<a href="{html.escape(url, quote=True)}">{label}</a>'

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, escaped)


def _markdown(body: str) -> str:
    lines = body.splitlines()
    rendered: list[str] = []
    paragraph: list[str] = []
    list_open = False
    code_open = False

    def flush_paragraph() -> None:
        if paragraph:
            rendered.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            rendered.append("</ul>")
            list_open = False

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("```"):
            flush_paragraph()
            close_list()
            rendered.append("</code></pre>" if code_open else "<pre><code>")
            code_open = not code_open
            continue
        if code_open:
            rendered.append(html.escape(line))
            continue
        if not line:
            flush_paragraph()
            close_list()
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            rendered.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue
        if line.startswith("> "):
            flush_paragraph()
            close_list()
            rendered.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
            continue
        if line.startswith("- "):
            flush_paragraph()
            if not list_open:
                rendered.append("<ul>")
                list_open = True
            rendered.append(f"<li>{_inline(line[2:])}</li>")
            continue
        paragraph.append(line)
    flush_paragraph()
    close_list()
    if code_open:
        rendered.append("</code></pre>")
    return "\n".join(rendered)


def _page(*, title: str, body: str, description: str, meta: str = "") -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport"
content="width=device-width,initial-scale=1"><meta name="description"
content="{html.escape(description, quote=True)}"><title>{html.escape(title)} — Darshan</title>
<style>{STYLE}</style></head><body><header><p class="kicker">DARSHAN · ISSUE ONE</p>
<p><a href="../index.html">Clear seeing after the feed</a></p></header>
<main><article>{meta}{body}</article></main><footer>No trackers. No feed. Corrections remain
on the face of each piece.</footer></body></html>
"""


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "build-manifest.json":
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_site(source_dir: Path = CONTENT_DIR, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    articles_dir = output_dir / "articles"
    articles_dir.mkdir(parents=True)
    articles: list[dict[str, str]] = []
    for source in sorted(source_dir.glob("*.md")):
        metadata, markdown = _parse_source(source)
        article_path = articles_dir / f"{metadata['slug']}.html"
        meta = (
            f"<p class=\"register\">{html.escape(metadata['desk'])}</p>"
            f"<h1>{html.escape(metadata['title'])}</h1>"
            f"<p class=\"summary\">{html.escape(metadata['summary'])}</p>"
            f"<p class=\"meta\">Published {html.escape(metadata['published_at'])}</p>"
        )
        article_path.write_text(
            _page(
                title=metadata["title"],
                description=metadata["summary"],
                meta=meta,
                body=_markdown(markdown),
            ),
            encoding="utf-8",
        )
        articles.append(
            {
                **metadata,
                "path": f"articles/{metadata['slug']}.html",
                "content_sha256": _sha256(source.read_bytes()),
            }
        )

    issue_items = "".join(
        f'<li><p class="register">{html.escape(item["desk"])}</p>'
        f'<h2><a href="{item["path"]}">{html.escape(item["title"])}</a></h2>'
        f'<p>{html.escape(item["summary"])}</p></li>'
        for item in articles
    )
    index_body = (
        "<h1>Clear seeing after the feed</h1>"
        "<p class=\"summary\">Six essays held to both fires: factual discipline, "
        "the strongest countercase, visible uncertainty, and work returned to the world.</p>"
        f'<ol class="issue-list">{issue_items}</ol>'
    )
    (output_dir / "index.html").write_text(
        _page(
            title="Issue One",
            description="Darshan Issue One: clear seeing after the feed.",
            body=index_body,
        ),
        encoding="utf-8",
    )
    manifest: dict[str, Any] = {
        "schema": "dharma.darshan.site_build.v1",
        "article_count": len(articles),
        "articles": articles,
        "site_build_sha256": _tree_digest(output_dir),
    }
    (output_dir / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=CONTENT_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(build_site(args.source, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
