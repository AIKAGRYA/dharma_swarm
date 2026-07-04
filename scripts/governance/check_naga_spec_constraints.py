#!/usr/bin/env python3
"""Mechanical NAGA-IR constraint checker.

Exit 0 means clean, 1 means violations, and 2 means the checker could not
read the requested markdown files. The script is stdlib-only and intentionally
heuristic: it enforces the binding formatting and phrase constraints that can
be checked mechanically.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Iterable, Iterator, NamedTuple


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC_DIR = REPO_ROOT / "specs" / "naga_ir"
EXIT_CLEAN = 0
EXIT_VIOLATED = 1
EXIT_BROKEN = 2

WALL_SENTENCE_1 = "Cursor owns the acceleration of authorship. Dharma owns the conservation of authority."
WALL_SENTENCE_2 = (
    "A code change is not authoritative because it exists, or because an agent produced it, or because CI passed. "
    "It is authoritative only when its claim is inhabited by admissible evidence, under a known trust base, "
    "inside a live context, without unresolved challenge."
)

EMOJI_RANGES = (
    (0x1F300, 0x1F5FF),
    (0x1F600, 0x1F64F),
    (0x1F680, 0x1F6FF),
    (0x1F900, 0x1F9FF),
    (0x1FA00, 0x1FAFF),
    (0x2600, 0x26FF),
    (0x2700, 0x27BF),
)
EXCLAMATION_CHARS = {"!", "！", "❢", "❗"}
FOOTNOTE_RE = re.compile(r"\[\^[^\]]+\]")
SINGLE_STAR_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
UNDERSCORE_RE = re.compile(r"(?<![\w`])_([^_\n]+)_(?![\w`])")


class BrokenCheck(RuntimeError):
    pass


class Violation(NamedTuple):
    path: Path
    line: int
    code: str
    detail: str

    def render(self, root: Path) -> str:
        try:
            loc = self.path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            loc = str(self.path)
        return f"{loc}:{self.line}:{self.code}: {self.detail}"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower().replace("nāga", "naga").replace("naga ir", "naga-ir")


def spec_paths(inputs: Iterable[Path]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        item = item.resolve()
        if item.is_dir():
            paths.extend(sorted(item.glob("*.md")))
        else:
            paths.append(item)
    if not paths:
        paths = sorted(DEFAULT_SPEC_DIR.glob("*.md"))
    if not paths:
        raise BrokenCheck(f"no markdown files found under {DEFAULT_SPEC_DIR}")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise BrokenCheck(f"missing markdown file(s): {', '.join(missing)}")
    return paths


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise BrokenCheck(f"cannot read {path}: {exc}") from exc


def is_emoji(char: str) -> bool:
    codepoint = ord(char)
    if any(start <= codepoint <= end for start, end in EMOJI_RANGES):
        return True
    name = unicodedata.name(char, "")
    return "EMOJI" in name and unicodedata.category(char) == "So"


def strip_inline_code(line: str) -> str:
    return re.sub(r"`[^`]*`", "`code`", line)


def header_word_count(line: str) -> int:
    text = line.lstrip("#").strip()
    return len(re.findall(r"[\wĀ-ž]+", text, flags=re.UNICODE))


def plain_header(line: str) -> bool:
    text = line.lstrip("#").strip()
    return not any(token in text for token in ("[", "](", "`", "*", "!")) and not any(is_emoji(ch) for ch in text)


def paragraphs(lines: list[str]) -> Iterator[tuple[int, str]]:
    start = 0
    buf: list[str] = []
    in_fence = False
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            if buf:
                yield start, " ".join(buf)
                buf = []
            continue
        if in_fence or not stripped or stripped.startswith("|") or stripped.startswith("#"):
            if buf:
                yield start, " ".join(buf)
                buf = []
            continue
        if not buf:
            start = idx
        buf.append(stripped)
    if buf:
        yield start, " ".join(buf)


def negated_before(text: str, index: int) -> bool:
    window = text[max(0, index - 70):index]
    return any(marker in window for marker in ("not ", "no ", "never ", "without ", "does not ", "is not "))


def check_line(path: Path, line_no: int, line: str, in_fence: bool) -> list[Violation]:
    violations: list[Violation] = []
    for char in line:
        if is_emoji(char):
            violations.append(Violation(path, line_no, "emoji", "emoji codepoint is prohibited"))
            break
    if any(char in line for char in EXCLAMATION_CHARS):
        violations.append(Violation(path, line_no, "exclamation", "exclamation marks are prohibited"))
    if in_fence:
        return violations
    prose = strip_inline_code(line)
    if FOOTNOTE_RE.search(prose):
        violations.append(Violation(path, line_no, "footnote_refs", "footnote citations are prohibited"))
    if SINGLE_STAR_RE.search(prose) or UNDERSCORE_RE.search(prose):
        if not prose.lstrip().startswith("* "):
            violations.append(Violation(path, line_no, "italics", "markdown italics are prohibited"))
    if re.match(r"^\s*#+\s+", line):
        if header_word_count(prose) > 6:
            violations.append(Violation(path, line_no, "header", "header exceeds 6 words"))
        if not plain_header(prose):
            violations.append(Violation(path, line_no, "header", "header must be plain text"))
    return violations


def check_paragraph(path: Path, line_no: int, paragraph: str) -> list[Violation]:
    lower = normalize(paragraph)
    violations: list[Violation] = []
    for pattern in (r"isomorphism between", r"isomorphic to", r"literally the same object", r"identical to"):
        match = re.search(pattern, lower)
        if match and not negated_before(lower, match.start()) and "formal convergence" not in lower:
            violations.append(Violation(path, line_no, "isomorphism_overclaim", "use formal convergence, not isomorphism"))
            break
    prohibited_sunyata = (
        "sunyata is the terminal object",
        "emptiness is terminal",
        "sunyata = terminal",
        "sunyata as terminal",
    )
    if any(pattern in lower for pattern in prohibited_sunyata):
        violations.append(Violation(path, line_no, "sunyata_terminal", "sunyata must not be rendered as terminal"))
    idx = lower.find("no morphism to bottom")
    if idx >= 0 and not negated_before(lower, idx):
        violations.append(Violation(path, line_no, "unbounded_canonization", "canonization must be bounded"))
    conflations = ("naga-ir is nagini", "rename of nagini", "naga-ir = nagini", "naga-ir replaces nagini")
    if any(pattern in lower for pattern in conflations):
        violations.append(Violation(path, line_no, "nagini_conflation", "NAGA-IR is not ETH Nagini"))
    if "moltbook" in lower:
        marked_background = any(term in lower for term in ("background", "non-load-bearing", "non-normative", "not dependency"))
        high_conf = any(int(match) > 60 for match in re.findall(r"\[confidence:\s*(\d+)/100\]", lower))
        if not marked_background or high_conf:
            violations.append(Violation(path, line_no, "moltbook_load_bearing", "Moltbook must not load-bear"))
    if "telos-kernel" in lower and not re.search(r"(?:<=|≤)\s*5000\s+loc", lower):
        violations.append(Violation(path, line_no, "tcb_ceiling", "telos-kernel references need <= 5000 LOC ceiling"))
    return violations


def corpus_checks(paths: list[Path], all_text: str) -> list[Violation]:
    path = paths[0]
    normalized = normalize(all_text)
    violations: list[Violation] = []
    rendering_terms = (
        "no claim has authority by svabhava",
        "context",
        "witness",
        "trust base",
        "freshness",
        "unresolved-challenge status",
    )
    if not all(term in normalized for term in rendering_terms):
        violations.append(Violation(path, 1, "sunyata_rendering", "correct sunyata rendering is absent"))
    bounded_terms = ("canonization is bounded", "trust base", "ttl")
    if not all(term in normalized for term in bounded_terms) or "evidence horizon" not in normalized and "horizon" not in normalized:
        violations.append(Violation(path, 1, "bounded_canonization", "bounded canonization phrasing is absent"))
    nagini_terms = ("dialect-level assurance ir", "nagini", "lift", "evidence")
    if not all(term in normalized for term in nagini_terms):
        violations.append(Violation(path, 1, "nagini_distinction", "Nagini distinction is absent"))
    if WALL_SENTENCE_1 not in all_text:
        violations.append(Violation(path, 1, "wall_sentence_1", "wall sentence 1 missing or altered"))
    if WALL_SENTENCE_2 not in all_text:
        violations.append(Violation(path, 1, "wall_sentence_2", "wall sentence 2 missing or altered"))
    return violations


def check_file(path: Path) -> list[Violation]:
    lines = read_lines(path)
    violations: list[Violation] = []
    in_fence = False
    for line_no, line in enumerate(lines, start=1):
        currently_fence = in_fence
        if line.strip().startswith("```"):
            in_fence = not in_fence
            currently_fence = True
        violations.extend(check_line(path, line_no, line, currently_fence))
    for line_no, paragraph in paragraphs(lines):
        violations.extend(check_paragraph(path, line_no, paragraph))
    return violations


def run(inputs: Iterable[Path]) -> list[Violation]:
    paths = spec_paths(inputs)
    violations: list[Violation] = []
    texts: list[str] = []
    for path in paths:
        texts.append(path.read_text(encoding="utf-8", errors="ignore"))
        violations.extend(check_file(path))
    violations.extend(corpus_checks(paths, "\n".join(texts)))
    return violations


def summary(violations: list[Violation]) -> dict[str, int]:
    categories = [
        "emoji",
        "exclamation",
        "italics",
        "footnote_refs",
        "header",
        "isomorphism_overclaim",
        "sunyata_terminal",
        "unbounded_canonization",
        "nagini_conflation",
        "moltbook_load_bearing",
        "tcb_ceiling",
        "wall_sentences",
    ]
    counts = {category: 0 for category in categories}
    for violation in violations:
        if violation.code.startswith("wall_sentence"):
            counts["wall_sentences"] += 1
        elif violation.code in counts:
            counts[violation.code] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check NAGA-IR binding constraints.")
    parser.add_argument("paths", nargs="*", type=Path, help="markdown files or directories; defaults to specs/naga_ir")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args(argv)
    try:
        violations = run(args.paths)
    except BrokenCheck as exc:
        print(f"broken: {exc}", file=sys.stderr)
        return EXIT_BROKEN
    counts = summary(violations)
    if args.json:
        print(json.dumps({"ok": not violations, "violations": [v._asdict() for v in violations], "summary": counts}, default=str, indent=2))
    else:
        for key, count in counts.items():
            print(f"{key}: {count} violations")
        for violation in violations:
            print(violation.render(REPO_ROOT), file=sys.stderr)
    return EXIT_VIOLATED if violations else EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
