"""Markdown edge parsing shared by the backlink projection."""

from __future__ import annotations

import re

import yaml


_WIKILINK_RE = re.compile(r"\[\[([^\[\]\r\n]+?)\]\]")
_FENCE_RE = re.compile(r"(?m)^[ \t]{0,3}(`{3,}|~{3,})[^\r\n]*(?:\r?\n|$)")
_INLINE_CODE_RE = re.compile(
    r"(?s)(?<!`)(?P<fence>`+)(?!`)(?P<body>.*?)(?<!`)(?P=fence)(?!`)"
)
_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL
)


def fenced_code_spans(text: str) -> tuple[tuple[int, int], ...]:
    """Return byte-independent character spans occupied by fenced code."""

    spans: list[tuple[int, int]] = []
    opening: tuple[int, str, int] | None = None
    for match in _FENCE_RE.finditer(text):
        fence = match.group(1)
        if opening is None:
            opening = (match.start(), fence[0], len(fence))
            continue
        start, character, minimum_length = opening
        if fence[0] == character and len(fence) >= minimum_length:
            spans.append((start, match.end()))
            opening = None
    if opening is not None:
        spans.append((opening[0], len(text)))
    return tuple(spans)


def position_in_spans(position: int, spans: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= position < end for start, end in spans)


def extract_wikilink_targets(text: str) -> tuple[str, ...]:
    """Extract authored wikilink targets while ignoring code."""

    targets: list[str] = []
    code_spans = list(fenced_code_spans(text))
    code_spans.extend(
        (match.start(), match.end())
        for match in _INLINE_CODE_RE.finditer(text)
        if not position_in_spans(match.start(), tuple(code_spans))
    )
    frozen_code_spans = tuple(sorted(code_spans))
    for match in _WIKILINK_RE.finditer(text):
        if position_in_spans(match.start(), frozen_code_spans):
            continue
        target = re.split(r"[|#]", match.group(1), maxsplit=1)[0].strip()
        if target:
            targets.append(target)
    return tuple(targets)


def without_frontmatter(text: str) -> str:
    """Return Markdown prose only; metadata edges are parsed explicitly."""

    match = _FRONTMATTER_RE.match(text)
    return text[match.end() :] if match else text


def extract_frontmatter_related_targets(text: str) -> tuple[str, ...]:
    """Read explicit authored ``related`` metadata as semantic edges."""

    payload = _parse_frontmatter_mapping(text)
    if payload is None:
        return ()
    status = str(payload.get("epistemic_status", "")).casefold()
    raw_tags = payload.get("tags", ())
    tags = (
        {str(item).casefold() for item in raw_tags}
        if isinstance(raw_tags, list)
        else {str(raw_tags).casefold()}
    )
    if status == "orphan-recovered" or "orphan-recovered" in tags:
        return ()
    raw_related = payload.get("related", ())
    if isinstance(raw_related, str):
        values = (raw_related,)
    elif isinstance(raw_related, list):
        values = tuple(item for item in raw_related if isinstance(item, str))
    else:
        return ()
    targets: list[str] = []
    for value in values:
        linked = extract_wikilink_targets(value)
        if linked:
            targets.extend(linked)
        elif value.strip():
            targets.append(value.strip())
    return tuple(targets)


def has_signed_provenance(text: str) -> bool:
    payload = _parse_frontmatter_mapping(text)
    if payload is None:
        return False
    provenance = payload.get("provenance")
    return isinstance(provenance, dict) and bool(provenance.get("axiom_signature"))


def _parse_frontmatter_mapping(text: str) -> dict[object, object] | None:
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return None
    lines = match.group(0).splitlines()
    if len(lines) < 2:
        return None
    try:
        payload = yaml.safe_load("\n".join(lines[1:-1])) or {}
    except yaml.YAMLError:
        return None
    return payload if isinstance(payload, dict) else None
