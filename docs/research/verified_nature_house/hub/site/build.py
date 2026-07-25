#!/usr/bin/env python3
"""Build the (draft, unpublished) Seam site content pages from the hub markdown.

Renders ../01_THE_SEAM.md -> the-seam.html and ../THE_HUNDRED.md -> the-hundred.html,
each wrapped in the shared site shell (draft banner + style.css). Single source of
truth stays the markdown; this only generates preview HTML.

Uses a minimal stdlib renderer covering the constructs these docs use. No network
calls and no optional third-party imports.

    python3 build.py            # build both pages (names as in source)
    python3 build.py --redact   # build with personal names dropped to affiliation level
    python3 -m http.server      # then serve this dir to preview locally

SEED-stage. Nothing built here is published; deployment is gated (see README.md).
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HUB = HERE.parent

# --- Redaction map (build.py --redact) ------------------------------------------
# Drops personal names to affiliation level for individuals where a person's name
# attaches to a critique. Thinkers/authors cited for a named public work (Dasgupta,
# Raworth, Kimmerer, Shrikanth, the "Taking AI Welfare Seriously" authors, etc.) are
# intentionally NOT redacted — the named book/paper IS the legitimate citation and
# the seams there are respectful. Source markdown stays canonical; this only affects
# the published HTML when --redact is passed.
REDACT_MAP = {
    "NVIDIA / Jensen Huang": "NVIDIA",
    "Sasha Luccioni (Hugging Face / AI Energy Score)": "Hugging Face — AI Energy Score",
    "Shaolei Ren (UC Riverside)": "UC Riverside — AI water-footprint research",
    "Barbara Haya / Berkeley Carbon Trading Project": "Berkeley Carbon Trading Project",
    "Chris Olah (Anthropic interpretability)": "Anthropic interpretability",
    "Neel Nanda (DeepMind mech-interp)": "DeepMind mechanistic interpretability",
    "Kate Crawford": "Atlas of AI (AI-as-extraction scholarship)",
}


def _redact(md_text: str) -> str:
    for name, repl in REDACT_MAP.items():
        md_text = md_text.replace(name, repl)
    return md_text

PAGES = [
    ("01_THE_SEAM.md", "the-seam.html", "The Seam — flagship essay (draft)"),
    ("THE_HUNDRED.md", "the-hundred.html", "The Hundred — connective map (draft)"),
]

BANNER = (
    '<div class="draft-banner">DRAFT — NOT PUBLISHED. Behind the operator\'s '
    "coherence gate; pending the named-person fairness pass and source verifications. "
    'Nothing here is live. <a href="index.html">&larr; back to the hub</a></div>'
)


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
    redact = "--redact" in sys.argv[1:]
    if redact:
        print(f"  --redact ON: dropping {len(REDACT_MAP)} personal names to affiliation level")
    for src_name, out_name, title in PAGES:
        src = HUB / src_name
        if not src.exists():
            print(f"  skip: {src_name} not found")
            continue
        md_text = src.read_text(encoding="utf-8")
        if redact:
            md_text = _redact(md_text)
        body = _render_minimal(md_text)
        (HERE / out_name).write_text(_shell(title, body), encoding="utf-8")
        print(f"  built: {out_name}  (from {src_name})")
    print("Done. Preview: python3 -m http.server  (then open index.html). NOT published.")


if __name__ == "__main__":
    main()
