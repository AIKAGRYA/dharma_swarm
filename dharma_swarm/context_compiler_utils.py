"""Small helpers shared by the runtime context compiler."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContextSection:
    name: str
    priority: int
    content: str
    source_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "priority": self.priority,
            "content": self.content,
            "source_refs": list(self.source_refs),
            "metadata": dict(self.metadata),
        }


def canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def approx_char_budget(token_budget: int) -> int:
    return max(800, max(1, int(token_budget)) * 4)


def dedupe_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= 20:
        return text[:max_chars]
    return text[: max_chars - 15].rstrip() + "\n... [truncated]"


def context_scan_metadata(rendered_text: str) -> dict[str, Any]:
    try:
        from dharma_swarm.injection_scanner import scan_content

        result = scan_content(rendered_text, "context_bundle")
    except Exception:
        logger.debug("Context bundle scan failed", exc_info=True)
        return {
            "status": "scanner_unavailable",
            "findings": [],
            "scanner": "dharma_swarm.injection_scanner.scan_content",
        }
    return {
        "status": "clean" if result.is_clean else "blocked",
        "findings": list(result.findings),
        "scanner": "dharma_swarm.injection_scanner.scan_content",
    }
