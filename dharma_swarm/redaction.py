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
  persisted on scanner failure.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_URL_RE = re.compile(r"\b(?:https?|ssh|git)://[^\s<>'\")]+", re.IGNORECASE)
_HOME_PATH_RE = re.compile(r"(?P<prefix>^|[\s:=,;\[\]('\"])(?:/Users|/home)/[^/\s]+(?:/[^\s,;:'\"\])}]+)*")
_WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z]:\\Users\\[^\\\s]+(?:\\[^\s,;:'\"\])}]+)*")
_TOKEN_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|passwd|bearer|authorization|credential)\b\s*[:=]\s*['\"]?([A-Za-z0-9._~+/=-]{8,})"
)
_TOKEN_PREFIX_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|glpat-[A-Za-z0-9_-]{16,}|xox[baprs]-[A-Za-z0-9-]{16,})\b"
)
_HIGH_ENTROPY_RE = re.compile(r"\b[A-Za-z0-9+/=_-]{32,}\b")
_ACCOUNT_ID_RE = re.compile(r"\b(?:acct|account|org|tenant|project|workspace)[_-]?[A-Za-z0-9]{8,}\b", re.IGNORECASE)

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
) -> str:
    def repl(match: re.Match[str]) -> str:
        original = match.group(group) if group is not None else match.group(0)
        replacement = _replacement(category, original)
        findings.append(RedactionFinding(category, replacement, stable_hash(original)))
        if group is None:
            return replacement
        start, end = match.span(group)
        prefix = match.string[match.start() : start]
        suffix = match.string[end : match.end()]
        return f"{prefix}{replacement}{suffix}"

    return pattern.sub(repl, text)


def redact_text(text: str) -> RedactionResult:
    """Redact sensitive spans in free text.

    Long token-like strings are treated as uncertain sensitive material and set
    ``fail_closed=True`` so callers can quarantine the record for review.
    """
    findings: list[RedactionFinding] = []
    redacted = str(text)

    redacted = _redact_with_regex(redacted, _TOKEN_ASSIGNMENT_RE, "credential", findings, group=2)
    redacted = _redact_with_regex(redacted, _TOKEN_PREFIX_RE, "token", findings)
    redacted = _redact_with_regex(redacted, _EMAIL_RE, "email", findings)
    redacted = _redact_with_regex(redacted, _IPV4_RE, "ip", findings)
    redacted = _redact_with_regex(redacted, _URL_RE, "url", findings)
    redacted = _redact_with_regex(redacted, _HOME_PATH_RE, "path", findings)
    redacted = _redact_with_regex(redacted, _WINDOWS_PATH_RE, "path", findings)
    redacted = _redact_with_regex(redacted, _ACCOUNT_ID_RE, "account_id", findings)

    before_entropy = len(findings)
    redacted = _redact_with_regex(redacted, _HIGH_ENTROPY_RE, "token_like", findings)
    fail_closed = len(findings) > before_entropy
    return RedactionResult(redacted=redacted, findings=findings, fail_closed=fail_closed)


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
        if isinstance(value, list):
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
        result = redact_text(str(text))
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
    )


def scan_json_values_for_write(value: Any) -> BoundaryRecordScanResult:
    """Structure-preserving scan of a JSON-compatible value. Never raises.

    Applies ``redact_text`` to every string leaf. Unlike ``redact_record``,
    field names are NOT wholesale-redacted — event payloads must remain
    replayable; only secret-shaped values are replaced.
    """
    findings: list[RedactionFinding] = []

    def walk(item: Any) -> Any:
        if isinstance(item, dict):
            return {str(key): walk(child) for key, child in item.items()}
        if isinstance(item, list):
            return [walk(child) for child in item]
        if isinstance(item, str):
            result = redact_text(item)
            findings.extend(result.findings)
            return result.redacted
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
    )
