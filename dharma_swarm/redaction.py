"""Fail-closed secret/PII redaction — shared write-boundary scanner.

Promoted from ``verifier_ranker_v0.redaction`` (which re-exports for compat):
the strongest scanner in the repo (token prefixes, credential assignments,
high-entropy strings, emails, IPs, paths) is now a core dependency wired at
memory-plane write boundaries, not just training-data export.

Two API tiers:

* ``redact_text`` / ``redact_record`` — the original deterministic redactors
  (``redact_record`` wholesale-replaces sensitive FIELD names; training-export
  semantics, too destructive for replayable event payloads).
* ``scan_text_for_write`` / ``scan_json_values_for_write`` — never-raise
  write-boundary wrappers. Policy: ``sensitive_count > 0`` → persist the
  redacted value and stamp ``pii_risk=high``; scanner ERROR → quarantine lane
  (placeholder value + ``context_admissible=False`` marker). Raw text is never
  persisted on scanner failure. Write boundaries redact secret-shaped material
  and emails only; infrastructure references (paths, URLs, IPs, account ids)
  are detected-but-preserved so the memory plane stays citable — the recall
  admission redactor and ``redact_record`` export keep full scrubbing.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_URL_RE = re.compile(r"\b(?:https?|ssh|git)://[^\s<>'\")]+", re.IGNORECASE)
_HOME_PATH_RE = re.compile(
    r"(?P<prefix>^|[\s:=,;\[\]('\"])(?P<path>(?:/Users|/home)/[^/\s]+(?:/[^\s,;:'\"\])}]+)*)"
)
_WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z]:\\Users\\[^\\\s]+(?:\\[^\s,;:'\"\])}]+)*")
_TOKEN_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|passwd|bearer|authorization|credential)\b\s*[:=]\s*['\"]?([A-Za-z0-9._~+/=-]{8,})"
)
_TOKEN_PREFIX_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|glpat-[A-Za-z0-9_-]{16,}|xox[baprs]-[A-Za-z0-9-]{16,})\b"
)
_HIGH_ENTROPY_RE = re.compile(r"\b[A-Za-z0-9+/=_-]{32,}\b")
_ACCOUNT_ID_RE = re.compile(r"\b(?:acct|account|org|tenant|project|workspace)[_-]?[A-Za-z0-9]{8,}\b", re.IGNORECASE)
_HEX_RUN_RE = re.compile(r"[0-9a-fA-F]{32,}")
_WORDISH_SEGMENT_RE = re.compile(r"[A-Za-z_][A-Za-z_.]*")
# Random 32+-char tokens measure >=3.87 bits/char over base36/base62/base64
# alphabets (7,696-sample floor); benign estate strings surviving the
# structural rules measured <=3.69. 3.8 splits the gap.
_TOKEN_LIKE_ENTROPY_MIN = 3.8


def _shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    total = len(text)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def _slug_segment(segment: str) -> bool:
    return segment.isalpha() or (segment[:1].isdigit() and segment.isalnum())


def _is_high_entropy_token(candidate: str) -> bool:
    """Precision gate over the coarse 32+-char run.

    Length alone is not a secret signal: commit SHAs, UUIDs, kebab/snake
    slugs, repo paths, and long identifiers all match ``_HIGH_ENTROPY_RE``.
    Only candidates that survive the structural benign-shape rules AND carry
    random-token character entropy are treated as secrets. Secrets these
    rules pass over (e.g. pure-hex or slash-bearing tokens) remain covered by
    the assignment-context and known-prefix regexes.
    """
    if "/" in candidate:
        return False
    if _HEX_RUN_RE.fullmatch(candidate):
        return False
    compact = candidate.replace("-", "").replace("_", "")
    if _HEX_RUN_RE.fullmatch(compact):
        return False
    prefixed = re.fullmatch(r"[A-Za-z]{1,16}[_-](.+)", candidate)
    if prefixed:
        # turn_<hex32> / evt-<uuid> style row ids: short alpha prefix + hex
        # body. Known secret prefixes (sk-, ghp_, ...) are already redacted
        # by _TOKEN_PREFIX_RE before this gate runs.
        tail = prefixed.group(1).replace("-", "").replace("_", "")
        if len(tail) >= 16 and re.fullmatch(r"[0-9a-fA-F]+", tail):
            return False
    if not any(ch.isdigit() for ch in candidate) or not any(ch.isalpha() for ch in candidate):
        return False
    segments = [segment for segment in re.split(r"[-_]", candidate) if segment]
    if len(segments) >= 3 and all(_slug_segment(segment) for segment in segments):
        return False
    return _shannon_entropy(candidate) >= _TOKEN_LIKE_ENTROPY_MIN

SENSITIVE_FIELD_NAMES = {
    "body",
    "message_body",
    "raw_body",
    "raw_message",
    "raw_message_body",
    "content",
    "prompt",
    "response",
    "raw_response",
    "provider_payload",
    "payload",
    "payload_json",
    "request_json",
    "response_json",
    "stderr",
    "stdout",
    "error_detail",
    "error_string",
}


@dataclass(frozen=True)
class RedactionFinding:
    """One detected sensitive or uncertain-sensitive span."""

    category: str
    replacement: str
    source_hash: str


@dataclass(frozen=True)
class RedactionResult:
    """Result of a redaction pass."""

    redacted: Any
    findings: list[RedactionFinding] = field(default_factory=list)
    fail_closed: bool = False
    detected: list[RedactionFinding] = field(default_factory=list)

    @property
    def sensitive_count(self) -> int:
        return len(self.findings)


def stable_hash(value: Any) -> str:
    """Return a short deterministic SHA-256 tag for a value."""
    if isinstance(value, str):
        data = value.encode("utf-8", errors="replace")
    else:
        data = json.dumps(value, sort_keys=True, ensure_ascii=True, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:16]


def _replacement(category: str, value: str) -> str:
    return f"<REDACTED_{category.upper()}:sha256:{stable_hash(value)}>"


def _redact_with_regex(
    text: str,
    pattern: re.Pattern[str],
    category: str,
    findings: list[RedactionFinding],
    *,
    group: int | str | None = None,
    gate: Callable[[str], bool] | None = None,
) -> str:
    def repl(match: re.Match[str]) -> str:
        original = match.group(group) if group is not None else match.group(0)
        if gate is not None and not gate(original):
            return match.group(0)
        replacement = _replacement(category, original)
        findings.append(RedactionFinding(category, replacement, stable_hash(original)))
        if group is None:
            return replacement
        start, end = match.span(group)
        prefix = match.string[match.start() : start]
        suffix = match.string[end : match.end()]
        return f"{prefix}{replacement}{suffix}"

    return pattern.sub(repl, text)


def _detect_with_regex(
    text: str,
    pattern: re.Pattern[str],
    category: str,
    findings: list[RedactionFinding],
    *,
    group: int | str | None = None,
) -> None:
    for match in pattern.finditer(text):
        original = match.group(group) if group is not None else match.group(0)
        if not original:
            continue
        findings.append(
            RedactionFinding(category, _replacement(category, original), stable_hash(original))
        )


def redact_text(text: str, *, preserve_infra: bool = False) -> RedactionResult:
    """Redact sensitive spans in free text.

    Long token-like strings are treated as uncertain sensitive material and set
    ``fail_closed=True`` so callers can quarantine the record for review. On
    the default (training-export) path every 32+-char run is redacted — recall
    over precision, matching the pre-promotion ``verifier_ranker_v0`` scrubber.

    ``preserve_infra=True`` is the write-boundary policy: infrastructure
    references (IPs, URLs, home paths, account ids) are recorded in
    ``detected`` but left in place — replacing them was measured to mangle
    nearly every substantive memory-plane row on this estate — and the
    ``token_like`` matcher applies the ``_is_high_entropy_token`` precision
    gate so benign estate identifiers (commit SHAs, UUIDs, row ids, slugs)
    survive.
    """
    findings: list[RedactionFinding] = []
    detected: list[RedactionFinding] = []
    redacted = str(text)

    redacted = _redact_with_regex(redacted, _TOKEN_ASSIGNMENT_RE, "credential", findings, group=2)
    redacted = _redact_with_regex(redacted, _TOKEN_PREFIX_RE, "token", findings)
    redacted = _redact_with_regex(redacted, _EMAIL_RE, "email", findings)
    if preserve_infra:
        _detect_with_regex(redacted, _IPV4_RE, "ip", detected)
        _detect_with_regex(redacted, _URL_RE, "url", detected)
        _detect_with_regex(redacted, _HOME_PATH_RE, "path", detected, group="path")
        _detect_with_regex(redacted, _WINDOWS_PATH_RE, "path", detected)
        _detect_with_regex(redacted, _ACCOUNT_ID_RE, "account_id", detected)
    else:
        redacted = _redact_with_regex(redacted, _IPV4_RE, "ip", findings)
        redacted = _redact_with_regex(redacted, _URL_RE, "url", findings)
        redacted = _redact_with_regex(redacted, _HOME_PATH_RE, "path", findings, group="path")
        redacted = _redact_with_regex(redacted, _WINDOWS_PATH_RE, "path", findings)
        redacted = _redact_with_regex(redacted, _ACCOUNT_ID_RE, "account_id", findings)

    before_entropy = len(findings)
    # The precision gate is write-boundary policy only: ungated, benign
    # 32+-char estate identifiers would mangle nearly every memory row.
    # The default path backs redact_record / training export, where a missed
    # secret is worse than a mangled benign token — no gate there.
    redacted = _redact_with_regex(
        redacted,
        _HIGH_ENTROPY_RE,
        "token_like",
        findings,
        gate=_is_high_entropy_token if preserve_infra else None,
    )
    fail_closed = len(findings) > before_entropy
    return RedactionResult(
        redacted=redacted, findings=findings, fail_closed=fail_closed, detected=detected
    )


def _field_replacement(key: str, value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=True, default=str)
    return f"<REDACTED_FIELD:{key}:sha256:{stable_hash(payload)}:bytes:{len(payload.encode('utf-8'))}>"


def redact_record(record: Any, *, key_hint: str = "") -> RedactionResult:
    """Redact a JSON-compatible record recursively.

    Sensitive field names are replaced wholesale with a hash token instead of
    attempting partial redaction. That is deliberate: prompt, response, body,
    payload, stdout/stderr, and provider error strings may contain arbitrary
    private material.
    """
    findings: list[RedactionFinding] = []
    fail_closed = False

    def walk(value: Any, key: str = "") -> Any:
        nonlocal fail_closed
        lowered = key.lower()
        if lowered in SENSITIVE_FIELD_NAMES and value not in (None, "", [], {}):
            replacement = _field_replacement(lowered, value)
            findings.append(RedactionFinding(f"field:{lowered}", replacement, stable_hash(value)))
            fail_closed = True
            return replacement
        if isinstance(value, dict):
            return {str(k): walk(v, str(k)) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            # json.dumps serializes tuples as arrays — an unscanned tuple
            # would carry its members to disk verbatim
            return [walk(item, key) for item in value]
        if isinstance(value, str):
            result = redact_text(value)
            findings.extend(result.findings)
            fail_closed = fail_closed or result.fail_closed
            return result.redacted
        return value

    redacted = walk(record, key_hint)
    return RedactionResult(redacted=redacted, findings=findings, fail_closed=fail_closed)


PII_RISK_HIGH = "high"

# Categories that are secret-shaped (vs contact/location PII). Boundaries that
# cannot redact in place (e.g. file-path ingest) exclude on these only.
SECRET_CATEGORIES = frozenset({"credential", "token", "token_like"})


@dataclass(frozen=True)
class BoundaryScanResult:
    """Outcome of a write-boundary scan over one text value."""

    text: str
    sensitive_count: int
    quarantined: bool
    categories: tuple[str, ...] = ()
    detected_categories: tuple[str, ...] = ()

    @property
    def has_secret(self) -> bool:
        return bool(SECRET_CATEGORIES.intersection(self.categories))


@dataclass(frozen=True)
class BoundaryRecordScanResult:
    """Outcome of a write-boundary scan over a JSON-compatible value."""

    value: Any
    sensitive_count: int
    quarantined: bool
    categories: tuple[str, ...] = ()
    detected_categories: tuple[str, ...] = ()

    @property
    def has_secret(self) -> bool:
        return bool(SECRET_CATEGORIES.intersection(self.categories))


def quarantine_placeholder(value: Any) -> str:
    """Placeholder persisted instead of raw content when the scanner fails."""
    try:
        return f"<QUARANTINED_SCAN_ERROR:sha256:{stable_hash(value)}>"
    except Exception:
        return "<QUARANTINED_SCAN_ERROR>"


def scan_text_for_write(text: Any) -> BoundaryScanResult:
    """Scan free text at a persistence boundary. Never raises.

    Scanner failure returns ``quarantined=True`` with a hash placeholder as
    ``text`` — callers persist that placeholder plus a
    ``context_admissible=False`` marker, never the raw input.
    """
    try:
        result = redact_text(str(text), preserve_infra=True)
    except Exception:
        return BoundaryScanResult(
            text=quarantine_placeholder(text),
            sensitive_count=0,
            quarantined=True,
        )
    return BoundaryScanResult(
        text=result.redacted,
        sensitive_count=result.sensitive_count,
        quarantined=False,
        categories=tuple(sorted({finding.category for finding in result.findings})),
        detected_categories=tuple(sorted({finding.category for finding in result.detected})),
    )


def scan_json_values_for_write(value: Any) -> BoundaryRecordScanResult:
    """Structure-preserving scan of a JSON-compatible value. Never raises.

    Applies write-policy ``redact_text`` to every string leaf AND every dict
    key. Unlike ``redact_record``, field names are NOT wholesale-redacted —
    event payloads must remain replayable; only secret-shaped material is
    replaced, wherever it appears.
    """
    findings: list[RedactionFinding] = []
    detected: list[RedactionFinding] = []

    def scan_string(item: str) -> str:
        result = redact_text(item, preserve_infra=True)
        findings.extend(result.findings)
        detected.extend(result.detected)
        return result.redacted

    def walk(item: Any) -> Any:
        if isinstance(item, dict):
            return {scan_string(str(key)): walk(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            # json.dumps serializes tuples as arrays — an unscanned tuple
            # would carry its members to disk verbatim
            return [walk(child) for child in item]
        if isinstance(item, str):
            return scan_string(item)
        return item

    try:
        redacted = walk(value)
    except Exception:
        return BoundaryRecordScanResult(value=None, sensitive_count=0, quarantined=True)
    return BoundaryRecordScanResult(
        value=redacted,
        sensitive_count=len(findings),
        quarantined=False,
        categories=tuple(sorted({finding.category for finding in findings})),
        detected_categories=tuple(sorted({finding.category for finding in detected})),
    )
