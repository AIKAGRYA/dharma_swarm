"""Shared text-safety helpers for MemoryKernel context evaluation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from dharma_swarm.memory_kernel.context_admission import redact_context_text


_LOCAL_PATH_RE = re.compile(
    r"(?P<path>(?:~|/(?:Users|private|tmp|var|Volumes|opt|etc|home))"
    r"[^\s`'\"()\[\]{}<>]*)"
)
_SECRET_MARKERS = (
    "BEGIN PRIVATE KEY",
    "api_key",
    "apikey",
    "private_key",
    "secret_token",
    "token=",
    "password=",
)


@dataclass(frozen=True)
class TextSafetyIssue:
    kind: str
    reason: str
    occurrence_count: int
    sample_redacted: str
    sample_hash: str


def detect_text_safety_issues(text: str) -> tuple[TextSafetyIssue, ...]:
    issues: list[TextSafetyIssue] = []
    path_matches = tuple(_LOCAL_PATH_RE.finditer(text))
    if path_matches:
        sample = path_matches[0].group("path")
        issues.append(
            TextSafetyIssue(
                kind="sensitive_path_detected",
                reason="context text contains local filesystem path references",
                occurrence_count=len(path_matches),
                sample_redacted="<local_path_redacted>",
                sample_hash=short_hash(sample),
            )
        )
    lower = text.lower()
    redacted = redact_context_text(text)
    secret_count = max(
        0,
        redacted.count("<secret_like_redacted>")
        - text.count("<secret_like_redacted>"),
    )
    if secret_count or any(marker.lower() in lower for marker in _SECRET_MARKERS):
        issues.append(
            TextSafetyIssue(
                kind="secret_like_text_detected",
                reason="context text contains secret-like markers",
                occurrence_count=max(1, secret_count),
                sample_redacted="<secret_like_redacted>",
                sample_hash=short_hash("secret_like_marker"),
            )
        )
    return tuple(issues)


def redacted_preview(text: str, *, max_chars: int = 240) -> str:
    clean = redact_context_text(text.replace("\n", " ").strip())
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 15].rstrip() + "...<truncated>"


def safe_eval_ref(value: str, *, max_chars: int = 180) -> str:
    if not value:
        return ""
    redacted = redact_context_text(str(value))
    if len(redacted) <= max_chars:
        return redacted
    return redacted[: max_chars - 3].rstrip() + "..."


def stable_context_finding_id(*parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return f"context_safety:{digest[:24]}"


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
