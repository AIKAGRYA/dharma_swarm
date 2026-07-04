#!/usr/bin/env python3
"""Mechanical NĀGA-IR spec constraint gate.

The checker is intentionally small and stdlib-only. It reads the
`specs/naga_ir/*.md` triple by default and reports file:line evidence for
formatting and binding-constraint violations. Exit codes match the governance
gate convention: 0 clean, 1 violations, 2 broken.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC_DIR = REPO_ROOT / "specs" / "naga_ir"

EXIT_CLEAN = 0
EXIT_VIOLATED = 1
EXIT_BROKEN = 2
REPORT_SCHEMA_VERSION = "naga_spec_constraint_report.v1"

INLINE_LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")
FOOTNOTE_RE = re.compile(r"\[\^[^\]]+\]")
SINGLE_STAR_RE = re.compile(r"(?<!\*)\*[^*\n]+\*(?!\*)")
UNDERSCORE_EMPH_RE = re.compile(r"(?<![\w`])_[^_\n]+_(?![\w`])")
CONFIDENCE_RE = re.compile(r"\[confidence:\s*\d+/100\]", re.IGNORECASE)
TCB_CEILING_RE = re.compile(r"(?:<=|≤)\s*5000\s+LOC", re.IGNORECASE)

LOAD_BEARING_TERMS = {
    "mlir",
    "viper",
    "nagini",
    "curry",
    "howard",
    "lambek",
    "cartesian",
    "linear dependent",
    "crdt",
    "rfc",
    "madhyamaka",
    "kyoto",
    "śūnyatā",
    "sunyata",
}

DEFINITION_MARKERS = (
    "defines ",
    "specifies ",
    "is defined as",
    "is a ",
    "is an ",
    "means ",
    "names ",
    "records ",
    "identifies ",
    "the threshold is",
    "the measured object is",
    "the admission threshold is",
    "the shared threshold is",
    "the normative",
    "this example",
    "this draft",
    "this pr #2",
    "does not ",
    "not ",
    "non-normative",
    "target properties only",
    "may add",
    "later prs may",
)


class BrokenCheck(RuntimeError):
    """The checker could not read or parse the requested files."""


@dataclass(frozen=True)
class Violation:
    code: str
    path: Path
    line: int
    detail: str

    def render(self, root: Path) -> str:
        location = self.path.relative_to(root).as_posix() if self.path.is_relative_to(root) else str(self.path)
        return f"{self.code} {location}:{self.line}: {self.detail}"


def spec_paths(inputs: Iterable[Path]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
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
        raise BrokenCheck(f"missing spec file(s): {', '.join(missing)}")
    return paths


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise BrokenCheck(f"cannot read {path}: {exc}") from exc


def mask_code(lines: list[str]) -> list[str]:
    masked: list[str] = []
    in_fence = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            masked.append("")
            continue
        if in_fence:
            masked.append("")
            continue
        masked.append(re.sub(r"`[^`]*`", "`code`", line))
    return masked


def has_emoji(text: str) -> bool:
    for char in text:
        if unicodedata.category(char) != "So":
            continue
        name = unicodedata.name(char, "")
        if "EMOJI" in name or "FACE" in name or "HEART" in name or "SIGN" in name:
            return True
    return False


def header_words(header: str) -> list[str]:
    cleaned = re.sub(r"^#{2,3}\s*", "", header).strip()
    return re.findall(r"[\wĀ-ž]+", cleaned, flags=re.UNICODE)


def is_plain_header(header: str) -> bool:
    text = re.sub(r"^#{2,3}\s*", "", header).strip()
    return not any(token in text for token in ("[", "](", "`", "*", "#", "!"))


def paragraph_blocks(lines: list[str]) -> Iterator[tuple[int, str]]:
    start = 0
    buf: list[str] = []
    in_fence = False
    for idx, line in enumerate(lines, start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            if buf:
                yield start, " ".join(buf)
                buf = []
            continue
        if in_fence or not line.strip() or line.startswith("#") or line.startswith("|"):
            if buf:
                yield start, " ".join(buf)
                buf = []
            continue
        if not buf:
            start = idx
        buf.append(line.strip())
    if buf:
        yield start, " ".join(buf)


def split_sentences(paragraph: str) -> list[str]:
    without_links = re.sub(r"\[[^\]]+\]\([^)]+\)", "", paragraph)
    parts = re.split(r"(?<=[.!?])\s+", without_links)
    return [part.strip() for part in parts if part.strip()]


def sentence_is_load_bearing(sentence: str) -> bool:
    lower = sentence.lower()
    if not CONFIDENCE_RE.search(sentence):
        return False
    if any(marker in lower for marker in DEFINITION_MARKERS):
        return False
    return any(term in lower for term in LOAD_BEARING_TERMS)


def paragraph_has_external_citation(paragraph: str) -> bool:
    return bool(INLINE_LINK_RE.search(paragraph))


def negated_near(text: str, phrase_start: int) -> bool:
    window = text[max(0, phrase_start - 35):phrase_start].lower()
    return any(word in window for word in ("not ", "no ", "never ", "without ", "isn't ", "does not "))


def check_line_format(path: Path, line_no: int, line: str) -> Iterator[Violation]:
    if has_emoji(line):
        yield Violation("NAGA-FMT-EMOJI", path, line_no, "emoji codepoint is not allowed")
    if "!" in line:
        yield Violation("NAGA-FMT-BANG", path, line_no, "exclamation marks are not allowed")
    if FOOTNOTE_RE.search(line):
        yield Violation("NAGA-FMT-FOOTNOTE", path, line_no, "footnote-style citation refs are not allowed")
    if SINGLE_STAR_RE.search(line):
        yield Violation("NAGA-FMT-ITALIC", path, line_no, "single-asterisk emphasis is not allowed")
    if UNDERSCORE_EMPH_RE.search(line):
        yield Violation("NAGA-FMT-ITALIC", path, line_no, "underscore emphasis is not allowed")
    if re.match(r"^#{2,3}\s+", line):
        words = header_words(line)
        if len(words) > 6:
            yield Violation("NAGA-FMT-HEADER", path, line_no, "##/### header exceeds 6 words")
        if not is_plain_header(line):
            yield Violation("NAGA-FMT-HEADER", path, line_no, "##/### header must be plain text")


def check_semantics(path: Path, start: int, paragraph: str) -> Iterator[Violation]:
    lower = paragraph.lower()
    for match in re.finditer(r"\bisomorphism\b|\bisomorphic\b|literally the same object", lower):
        if not negated_near(lower, match.start()) and "formal convergence" not in lower:
            yield Violation(
                "NAGA-CONSTRAINT-ISOMORPHISM",
                path,
                start,
                "do not overclaim isomorphism; use formal convergence only",
            )
            break
    for match in re.finditer(r"(śūnyatā|sunyata)[^.]{0,80}terminal object", lower):
        if " not " not in match.group(0) and not negated_near(lower, match.start()):
            yield Violation("NAGA-CONSTRAINT-SUNYATA", path, start, "Śūnyatā must not be phrased as terminal object")
            break
    phrase = "no morphism to bottom exists"
    idx = lower.find(phrase)
    if idx >= 0 and not negated_near(lower, idx):
        yield Violation("NAGA-CONSTRAINT-CANON", path, start, "canonization must be bounded, not absolute")
    if "nagini" in lower and "naga-ir is nagini" in lower.replace("nāga", "naga"):
        yield Violation("NAGA-CONSTRAINT-NAGINI", path, start, "NĀGA-IR must not be conflated with ETH Nagini")
    if "nagini" in lower and "naga-ir" in lower.replace("nāga", "naga") and "rename" in lower and not negated_near(lower, lower.find("rename")):
        yield Violation("NAGA-CONSTRAINT-NAGINI", path, start, "Nagini is evidence that lifts into NĀGA-IR, not a rename")
    if "packages/telos-kernel/" in paragraph and not TCB_CEILING_RE.search(paragraph):
        yield Violation("NAGA-CONSTRAINT-TCB", path, start, "`packages/telos-kernel/` mention lacks TCB <= 5000 LOC ceiling")
    if "moltbook" in lower and not ("background motivation" in lower and "not dependency" in lower):
        yield Violation("NAGA-CONSTRAINT-MOLTBOOK", path, start, "Moltbook must not be load-bearing")
    if any(sentence_is_load_bearing(sentence) for sentence in split_sentences(paragraph)):
        if not paragraph_has_external_citation(paragraph):
            yield Violation("NAGA-CONSTRAINT-CITATION", path, start, "load-bearing claim lacks inline markdown-link citation")


def check_file(path: Path) -> list[Violation]:
    lines = read_lines(path)
    masked = mask_code(lines)
    violations: list[Violation] = []
    for line_no, line in enumerate(masked, start=1):
        violations.extend(check_line_format(path, line_no, line))
    for start, paragraph in paragraph_blocks(lines):
        violations.extend(check_semantics(path, start, paragraph))
    return violations


def run(paths: Iterable[Path]) -> list[Violation]:
    violations: list[Violation] = []
    for path in spec_paths(paths):
        violations.extend(check_file(path))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check NĀGA-IR spec formatting and binding constraints.")
    parser.add_argument("paths", nargs="*", type=Path, help="spec files or directories; defaults to specs/naga_ir/*.md")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        violations = run(args.paths)
    except BrokenCheck as exc:
        print(f"naga-spec-constraint: BROKEN: {exc}", file=sys.stderr)
        return EXIT_BROKEN
    if args.json:
        print(json.dumps({"schema_version": REPORT_SCHEMA_VERSION, "violations": [v.render(REPO_ROOT) for v in violations]}, indent=2))
    else:
        if not violations:
            print("naga-spec-constraint: clean")
        for violation in violations:
            print(violation.render(REPO_ROOT))
    return EXIT_VIOLATED if violations else EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
