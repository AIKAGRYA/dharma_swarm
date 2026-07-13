"""Canonical lifecycle parser for the append-only broken register."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

Lifecycle = Literal[
    "OPEN",
    "PARTIAL",
    "INVESTIGATING",
    "WORKAROUND",
    "FIXED",
    "CLOSED",
    "UNKNOWN",
]

OPEN_LIFECYCLES = frozenset({"OPEN", "PARTIAL", "INVESTIGATING", "WORKAROUND"})
CLOSED_LIFECYCLES = frozenset({"FIXED", "CLOSED"})
KNOWN_LIFECYCLES = OPEN_LIFECYCLES | CLOSED_LIFECYCLES

_H2_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$")
_H3_RE = re.compile(r"^###\s+(?P<id>BR-\d+)\b(?P<rest>.*)$", re.IGNORECASE)
_OPEN_HEADER_RE = re.compile(
    r"^OPEN(?:\s+ITEMS)?(?:\s+\([^)]*\))?$",
    re.IGNORECASE,
)
_STALE_HEADER_RE = re.compile(
    r"^STALE-CLAIM\s+CORRECTIONS(?:\s+\([^)]*\))?$",
    re.IGNORECASE,
)
_CLOSED_HEADER_RE = re.compile(
    r"^CLOSED(?:\s+ITEMS)?(?:\s+\([^)]*\))?$",
    re.IGNORECASE,
)
_DECLARED_OPEN_RE = re.compile(r"\((?P<count>\d+)\s+open(?:/partial)?\b", re.IGNORECASE)
_BOLD_FIELD_RE = re.compile(
    r"^\s*(?:[-*+]\s*)?\*\*(?P<key>[A-Za-z_][\w-]*)\s*:\*\*\s*(?P<value>.*?)\s*$"
)
_PLAIN_FIELD_RE = re.compile(
    r"^\s*(?:[-*+]\s*)?(?P<key>[A-Za-z_][\w-]*)\s*:\s*(?P<value>.*?)\s*$"
)
_REFERENCE_RE = re.compile(r"\bBR-\d+\b")


@dataclass(frozen=True)
class BrokenRegisterDiagnostic:
    code: str
    message: str
    br_id: str = ""
    line: int = 0
    source: str = ""


@dataclass(frozen=True)
class BrokenRegisterOccurrence:
    id: str
    title: str
    heading: str
    line: int
    section: str
    raw_status: str
    status: Lifecycle
    fields: dict[str, str]
    body: str
    diagnostics: tuple[BrokenRegisterDiagnostic, ...] = ()

    @property
    def is_open_like(self) -> bool:
        return self.status in OPEN_LIFECYCLES

    @property
    def is_closed_like(self) -> bool:
        return self.status in CLOSED_LIFECYCLES


@dataclass(frozen=True)
class BrokenRegisterEntry:
    id: str
    title: str
    heading: str
    line: int
    section: str
    raw_status: str
    status: Lifecycle
    fields: dict[str, str]
    body: str
    diagnostics: tuple[BrokenRegisterDiagnostic, ...]
    history: tuple[BrokenRegisterOccurrence, ...]

    @property
    def is_open_like(self) -> bool:
        return self.status in OPEN_LIFECYCLES

    @property
    def is_closed_like(self) -> bool:
        return self.status in CLOSED_LIFECYCLES


@dataclass(frozen=True)
class BrokenRegisterResult:
    present: bool
    source: str
    entries: tuple[BrokenRegisterEntry, ...]
    by_id: dict[str, BrokenRegisterEntry]
    declared_open_count: int | None
    diagnostics: tuple[BrokenRegisterDiagnostic, ...]

    @property
    def total(self) -> int:
        return len(self.entries)

    @property
    def open_entries(self) -> tuple[BrokenRegisterEntry, ...]:
        return tuple(entry for entry in self.entries if entry.is_open_like)

    @property
    def closed_entries(self) -> tuple[BrokenRegisterEntry, ...]:
        return tuple(entry for entry in self.entries if entry.is_closed_like)

    @property
    def unknown_entries(self) -> tuple[BrokenRegisterEntry, ...]:
        return tuple(entry for entry in self.entries if entry.status == "UNKNOWN")

    @property
    def open_count(self) -> int:
        return len(self.open_entries)

    @property
    def closed_count(self) -> int:
        return len(self.closed_entries)

    @property
    def unknown_count(self) -> int:
        return len(self.unknown_entries)


@dataclass
class _OccurrenceDraft:
    br_id: str
    rest: str
    heading: str
    line: int
    section: str
    body_lines: list[str]


def _diagnostic(
    code: str,
    message: str,
    *,
    source: str,
    br_id: str = "",
    line: int = 0,
) -> BrokenRegisterDiagnostic:
    return BrokenRegisterDiagnostic(
        code=code,
        message=message,
        br_id=br_id,
        line=line,
        source=source,
    )


def _normalize_lifecycle(value: str) -> Lifecycle:
    cleaned = value.strip()
    while cleaned.startswith("**"):
        cleaned = cleaned[2:].lstrip()
    match = re.match(r"(?P<status>[A-Za-z_]+)\b", cleaned)
    if match is None:
        return "UNKNOWN"
    status = match.group("status").upper()
    return status if status in KNOWN_LIFECYCLES else "UNKNOWN"  # type: ignore[return-value]


def _heading_lifecycle(rest: str) -> Lifecycle | None:
    match = re.match(
        r"^\s*\(\s*(?P<status>REOPENED|OPEN|PARTIAL|INVESTIGATING|WORKAROUND|FIXED|CLOSED)\b[^)]*\)",
        rest,
        re.IGNORECASE,
    )
    if match is None:
        return None
    status = match.group("status").upper()
    return "OPEN" if status == "REOPENED" else status  # type: ignore[return-value]


def _lifecycles_equivalent(left: Lifecycle, right: Lifecycle) -> bool:
    return left == right or left in CLOSED_LIFECYCLES and right in CLOSED_LIFECYCLES


def _parse_fields(body_lines: list[str]) -> tuple[dict[str, str], dict[str, list[str]]]:
    fields: dict[str, str] = {}
    values: dict[str, list[str]] = {}
    for line in body_lines:
        match = _BOLD_FIELD_RE.match(line) or _PLAIN_FIELD_RE.match(line)
        if match is None:
            continue
        key = match.group("key").lower().replace("-", "_")
        value = match.group("value").strip()
        values.setdefault(key, []).append(value)
        fields.setdefault(key, value)
    return fields, values


def _build_occurrence(draft: _OccurrenceDraft, source: str) -> BrokenRegisterOccurrence:
    fields, values = _parse_fields(draft.body_lines)
    status_values = values.get("status", [])
    heading_status = _heading_lifecycle(draft.rest)
    diagnostics: list[BrokenRegisterDiagnostic] = []
    status: Lifecycle = "UNKNOWN"
    raw_status = status_values[0] if status_values else ""

    if len(status_values) > 1:
        diagnostics.append(
            _diagnostic(
                "duplicate_status_field",
                f"{draft.br_id} has {len(status_values)} anchored status fields",
                source=source,
                br_id=draft.br_id,
                line=draft.line,
            )
        )
    elif status_values:
        status = _normalize_lifecycle(status_values[0])
        if status == "UNKNOWN":
            diagnostics.append(
                _diagnostic(
                    "malformed_status",
                    f"{draft.br_id} has an unrecognized anchored status value",
                    source=source,
                    br_id=draft.br_id,
                    line=draft.line,
                )
            )
        elif (
            heading_status is not None
            and not _lifecycles_equivalent(heading_status, status)
        ):
            diagnostics.append(
                _diagnostic(
                    "contradictory_lifecycle",
                    f"{draft.br_id} heading and status field disagree",
                    source=source,
                    br_id=draft.br_id,
                    line=draft.line,
                )
            )
            status = "UNKNOWN"
    elif heading_status is not None:
        status = heading_status
    elif draft.section == "closed":
        status = "CLOSED"
    else:
        diagnostics.append(
            _diagnostic(
                "missing_current_status",
                f"{draft.br_id} has no anchored current lifecycle",
                source=source,
                br_id=draft.br_id,
                line=draft.line,
            )
        )

    if draft.section == "closed" and status in OPEN_LIFECYCLES:
        diagnostics.append(
            _diagnostic(
                "contradictory_lifecycle",
                f"{draft.br_id} is open-like inside the CLOSED section",
                source=source,
                br_id=draft.br_id,
                line=draft.line,
            )
        )
        status = "UNKNOWN"
    if len(status_values) > 1:
        status = "UNKNOWN"

    title = re.sub(r"^[\s—–-]+", "", draft.rest).strip()
    return BrokenRegisterOccurrence(
        id=draft.br_id,
        title=title,
        heading=draft.heading,
        line=draft.line,
        section=draft.section,
        raw_status=raw_status,
        status=status,
        fields=fields,
        body="\n".join(draft.body_lines).rstrip(),
        diagnostics=tuple(diagnostics),
    )


def _entry_from_occurrence(
    occurrence: BrokenRegisterOccurrence,
    history: tuple[BrokenRegisterOccurrence, ...],
) -> BrokenRegisterEntry:
    return BrokenRegisterEntry(
        id=occurrence.id,
        title=occurrence.title,
        heading=occurrence.heading,
        line=occurrence.line,
        section=occurrence.section,
        raw_status=occurrence.raw_status,
        status=occurrence.status,
        fields=occurrence.fields,
        body=occurrence.body,
        diagnostics=occurrence.diagnostics,
        history=history,
    )


def parse_broken_register_text(
    text: str,
    *,
    source: str = "<memory>",
) -> BrokenRegisterResult:
    occurrences: list[BrokenRegisterOccurrence] = []
    parse_diagnostics: list[BrokenRegisterDiagnostic] = []
    section = "outside"
    declared_open_count: int | None = None
    draft: _OccurrenceDraft | None = None

    def flush() -> None:
        nonlocal draft
        if draft is not None:
            occurrences.append(_build_occurrence(draft, source))
            draft = None

    for line_number, line in enumerate(text.splitlines(), start=1):
        h2 = _H2_RE.match(line)
        if h2 is not None:
            flush()
            title = h2.group("title")
            if _OPEN_HEADER_RE.match(title):
                section = "current"
                declared = _DECLARED_OPEN_RE.search(title)
                if declared is not None:
                    declared_open_count = int(declared.group("count"))
            elif _STALE_HEADER_RE.match(title):
                section = "outside"
            elif _CLOSED_HEADER_RE.match(title):
                section = "closed"
            else:
                section = "outside"
            continue

        h3 = _H3_RE.match(line)
        if h3 is not None:
            flush()
            br_id = h3.group("id").upper()
            if section not in {"current", "closed"}:
                parse_diagnostics.append(
                    _diagnostic(
                        "entry_outside_lifecycle_section",
                        f"{br_id} appears outside an OPEN or CLOSED lifecycle section",
                        source=source,
                        br_id=br_id,
                        line=line_number,
                    )
                )
                continue
            rest = h3.group("rest")
            draft = _OccurrenceDraft(
                br_id=br_id,
                rest=rest,
                heading=f"{br_id}{rest}".strip(),
                line=line_number,
                section=section,
                body_lines=[],
            )
            continue
        if draft is not None:
            draft.body_lines.append(line)
    flush()

    grouped: dict[str, list[BrokenRegisterOccurrence]] = {}
    for occurrence in occurrences:
        grouped.setdefault(occurrence.id, []).append(occurrence)

    entries: list[BrokenRegisterEntry] = []
    diagnostics = list(parse_diagnostics)
    diagnostics.extend(
        diagnostic
        for occurrence in occurrences
        for diagnostic in occurrence.diagnostics
    )
    for br_id, history_items in grouped.items():
        history = tuple(history_items)
        current = [item for item in history if item.section == "current"]
        selected = current[0] if current else history[-1]
        entry = _entry_from_occurrence(selected, history)
        if len(current) > 1:
            duplicate = _diagnostic(
                "duplicate_current_entry",
                f"{br_id} has {len(current)} current occurrences",
                source=source,
                br_id=br_id,
                line=selected.line,
            )
            entry = replace(
                entry,
                status="UNKNOWN",
                diagnostics=entry.diagnostics + (duplicate,),
            )
            diagnostics.append(duplicate)
        entries.append(entry)

    open_count = sum(entry.is_open_like for entry in entries)
    if declared_open_count is not None and declared_open_count != open_count:
        diagnostics.append(
            _diagnostic(
                "open_header_count_drift",
                f"OPEN header declares {declared_open_count}; observed {open_count}",
                source=source,
            )
        )
    entry_tuple = tuple(entries)
    return BrokenRegisterResult(
        present=True,
        source=source,
        entries=entry_tuple,
        by_id={entry.id: entry for entry in entry_tuple},
        declared_open_count=declared_open_count,
        diagnostics=tuple(diagnostics),
    )


def parse_broken_register(path: Path) -> BrokenRegisterResult:
    source = path.as_posix()
    if not path.exists():
        diagnostic = _diagnostic(
            "missing_register",
            f"BROKEN_REGISTER is missing: {source}",
            source=source,
        )
        return BrokenRegisterResult(
            present=False,
            source=source,
            entries=(),
            by_id={},
            declared_open_count=None,
            diagnostics=(diagnostic,),
        )
    return parse_broken_register_text(
        path.read_text(encoding="utf-8", errors="replace"),
        source=source,
    )


def find_broken_register_references(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(match.group(0).upper() for match in _REFERENCE_RE.finditer(text)))


def validate_broken_register_references(
    result: BrokenRegisterResult,
    references: tuple[str, ...] | list[str],
    *,
    source: str,
) -> tuple[BrokenRegisterDiagnostic, ...]:
    return tuple(
        _diagnostic(
            "orphan_reference",
            f"{reference} does not resolve in BROKEN_REGISTER",
            source=source,
            br_id=reference,
        )
        for reference in references
        if reference not in result.by_id
    )
