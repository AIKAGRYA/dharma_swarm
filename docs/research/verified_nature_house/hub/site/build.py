#!/usr/bin/env python3
"""Build the (draft, unpublished) Seam site content pages from the hub markdown.

Renders ../01_THE_SEAM.md -> the-seam.html and ../THE_HUNDRED.md -> the-hundred.html,
each wrapped in the shared site shell (draft banner + style.css). Single source of
truth stays the markdown; this only generates preview HTML.

Uses the `markdown` package if installed (richer output); otherwise falls back to a
minimal stdlib renderer covering the constructs these docs use. No network calls.

    python3 build.py            # build both pages
    python3 -m http.server      # then serve this dir to preview locally

SEED-stage. Nothing built here is published; deployment is gated (see README.md).
"""
from __future__ import annotations

import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
HUB = HERE.parent

PAGES = [
    ("01_THE_SEAM.md", "the-seam.html", "The Seam — flagship essay (draft)"),
    ("THE_HUNDRED.md", "the-hundred.html", "The Hundred — connective map (draft)"),
]

BANNER = (
    '<div class="draft-banner">DRAFT — NOT PUBLISHED. Behind the operator\'s '
    "coherence gate; pending the named-person fairness pass and source verifications. "
    'Nothing here is live. <a href="index.html">&larr; back to the hub</a></div>'
)


def _render_with_lib(md_text: str) -> str | None:
    try:
        import markdown  # type: ignore
    except Exception:
        return None
    return markdown.markdown(md_text, extensions=["tables", "fenced_code"])


def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def _render_minimal(md_text: str) -> str:
    """Small fallback: headings, lists, blockquotes, hr, paragraphs, inline marks."""
    out: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in md_text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            close_list()
            continue
        if re.match(r"^#{1,6}\s", line):
            close_list()
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{_inline(line.lstrip('# ').strip())}</h{level}>")
        elif line.strip() in ("---", "***", "___"):
            close_list()
            out.append("<hr />")
        elif re.match(r"^\s*[-*]\s+", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = re.sub(r"^\s*[-*]\s+", "", line)
            out.append(f"<li>{_inline(item)}</li>")
        elif line.startswith(">"):
            close_list()
            out.append(f"<blockquote>{_inline(line.lstrip('> ').strip())}</blockquote>")
        else:
            close_list()
            out.append(f"<p>{_inline(line)}</p>")
    close_list()
    return "\n".join(out)


def _shell(title: str, body_html: str) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        '<meta name="robots" content="noindex, nofollow" />\n'
        f"<title>{html.escape(title)}</title>\n"
        '<link rel="stylesheet" href="style.css" />\n'
        "</head>\n<body>\n"
        f"{BANNER}\n"
        f'<main class="doc">\n{body_html}\n</main>\n'
        "</body>\n</html>\n"
    )


def main() -> None:
    for src_name, out_name, title in PAGES:
        src = HUB / src_name
        if not src.exists():
            print(f"  skip: {src_name} not found")
            continue
        md_text = src.read_text(encoding="utf-8")
        body = _render_with_lib(md_text) or _render_minimal(md_text)
        (HERE / out_name).write_text(_shell(title, body), encoding="utf-8")
        print(f"  built: {out_name}  (from {src_name})")
    print("Done. Preview: python3 -m http.server  (then open index.html). NOT published.")


if __name__ == "__main__":
    main()
