"""Context Injection Scanner — detects prompt injection in external files.

Inspired by Hermes Agent's prompt_builder.py injection scanning. Scans
context files (SOUL.md, AGENTS.md, .cursorrules, trishula inbox, PSMV
documents, etc.) BEFORE they enter the system prompt.

Detects:
  - Prompt injection attempts ("ignore previous instructions")
  - Secret exfiltration commands (curl $API_KEY, cat .env)
  - Hidden unicode (zero-width characters, bidi overrides)
  - HTML-based concealment (hidden divs, comment injection)
  - Typoglycemia obfuscation (scrambled-word injection evasion)
  - Base64-encoded prompt injection payloads (OWASP evasion class)
"""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Threat pattern registry ──────────────────────────────────────────

_THREAT_PATTERNS: list[tuple[str, str]] = [
    # Prompt injection
    (r"ignore\s+(previous|all|above|prior)\s+instructions", "prompt_injection"),
    (r"disregard\s+(your|all|any)\s+(instructions|rules|guidelines)", "disregard_rules"),
    (r"system\s+prompt\s+override", "sys_prompt_override"),
    (r"you\s+are\s+now\s+(a|an)\s+(?!agent)", "identity_override"),
    (r"forget\s+(everything|all)\s+(you|about)", "memory_wipe"),
    (r"new\s+instructions?\s*:", "new_instructions"),
    # Deception
    (r"do\s+not\s+tell\s+the\s+user", "deception_hide"),
    (r"act\s+as\s+(if|though)\s+you\s+(have\s+no|don't\s+have)\s+(restrictions|limits|rules)",
     "bypass_restrictions"),
    # Secret exfiltration
    (r"curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)", "exfil_curl"),
    (r"wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)", "exfil_wget"),
    (r"cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass|\.ssh)", "read_secrets"),
    (r"echo\s+\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|API)", "echo_secrets"),
    # HTML concealment
    (r"<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->", "html_comment_injection"),
    (r"<\s*div\s+style\s*=\s*[\"'].*display\s*:\s*none", "hidden_div"),
    # Code injection
    (r"translate\s+.*\s+into\s+.*\s+and\s+(execute|run|eval)", "translate_execute"),
    (r"eval\s*\(\s*['\"]", "eval_injection"),
    # Typoglycemia obfuscation: scrambled keyword variants (first/last letter fixed,
    # interior shuffled).  Covers OWASP evasion class: token-level scrambling.
    # Patterns require exact word lengths to minimise false positives:
    #   "ignore" (6) + "previous" (8) + "instructions" (12)
    (r"\bi[a-z]{4}e\s+p[a-z]{6}s\s+i[a-z]{10}s\b", "typoglycemia_injection"),
    #   "disregard" (9) + "your" (4) + "instructions" (12)
    (r"\bd[a-z]{7}d\s+y[a-z]{2}r\s+i[a-z]{10}s\b", "typoglycemia_injection"),
]

# Base64 token patterns that decode to known injection payloads
_BASE64_INJECTION_DECODED_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(previous|all|above|prior)\s+instructions", "b64_prompt_injection"),
    (r"disregard\s+(your|all|any)\s+(instructions|rules|guidelines)", "b64_disregard_rules"),
    (r"system\s+prompt\s+override", "b64_sys_prompt_override"),
    (r"you\s+are\s+now\s+(a|an)\s+(?!agent)", "b64_identity_override"),
    (r"new\s+instructions?\s*:", "b64_new_instructions"),
]

# Matches standalone base64 tokens of suspicious length (20–200 chars).
# Upper bound prevents attempting to decode large binary blobs or embedded files.
_B64_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9+/])([A-Za-z0-9+/]{20,200}={0,2})(?![A-Za-z0-9+/=])")

# Zero-width and bidirectional override characters
_INVISIBLE_CHARS: set[str] = {
    "\u200b",  # zero-width space
    "\u200c",  # zero-width non-joiner
    "\u200d",  # zero-width joiner
    "\u2060",  # word joiner
    "\ufeff",  # zero-width no-break space (BOM)
    "\u202a",  # left-to-right embedding
    "\u202b",  # right-to-left embedding
    "\u202c",  # pop directional formatting
    "\u202d",  # left-to-right override
    "\u202e",  # right-to-left override
}


@dataclass
class ScanResult:
    """Result of scanning content for injection threats."""
    is_clean: bool
    findings: list[str] = field(default_factory=list)
    sanitized_content: str = ""
    source_file: str = ""


def _check_base64_payloads(content: str) -> list[str]:
    """Decode candidate base64 tokens and scan decoded text for injection patterns.

    Returns a list of threat IDs for any decoded tokens that match known injection
    payload patterns (OWASP evasion class: base64 obfuscation).
    """
    findings: list[str] = []
    for match in _B64_TOKEN_RE.finditer(content):
        token = match.group(1)
        # Pad to a valid base64 length
        padded = token + "=" * (-len(token) % 4)
        try:
            decoded = base64.b64decode(padded).decode("utf-8", errors="replace")
        except Exception:
            continue
        for pattern, threat_id in _BASE64_INJECTION_DECODED_PATTERNS:
            if re.search(pattern, decoded, re.IGNORECASE):
                if threat_id not in findings:
                    findings.append(threat_id)
    return findings


def scan_content(content: str, filename: str = "<unknown>") -> ScanResult:
    """Scan content for injection threats.

    Returns a ScanResult with sanitized content. If threats are found,
    ``is_clean`` is False and ``sanitized_content`` contains a BLOCKED marker.

    Args:
        content: The text content to scan.
        filename: Source filename for logging.

    Returns:
        ScanResult with findings and sanitized content.
    """
    findings: list[str] = []

    # Check invisible unicode
    for char in _INVISIBLE_CHARS:
        if char in content:
            findings.append(f"invisible_unicode_U+{ord(char):04X}")

    # Check threat patterns
    for pattern, threat_id in _THREAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            findings.append(threat_id)

    # Check base64-encoded payloads
    findings.extend(_check_base64_payloads(content))

    if findings:
        logger.warning(
            "Context file %s blocked: %s",
            filename,
            ", ".join(findings),
        )
        blocked_msg = (
            f"[BLOCKED: {filename} contained potential prompt injection "
            f"({', '.join(findings)}). Content not loaded.]"
        )
        return ScanResult(
            is_clean=False,
            findings=findings,
            sanitized_content=blocked_msg,
            source_file=filename,
        )

    return ScanResult(
        is_clean=True,
        findings=[],
        sanitized_content=content,
        source_file=filename,
    )


def scan_and_sanitize(content: str, filename: str = "<unknown>") -> str:
    """Convenience: scan and return sanitized content directly.

    Returns the original content if clean, or a BLOCKED marker if threats found.
    """
    result = scan_content(content, filename)
    return result.sanitized_content
