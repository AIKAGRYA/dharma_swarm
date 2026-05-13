"""External-world zeitgeist awareness.

Zeitgeist means outside-world sensing: public web, feeds, operator drops, and
scout outputs. Internal repo/runtime pressure lives in ``internal_pressure``.

Output: ``~/.dharma/meta/zeitgeist.md`` + ``zeitgeist.jsonl``
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.models import _new_id, _utc_now

logger = logging.getLogger(__name__)

LLM_SCAN_ENABLED_ENV = "DHARMA_ZEITGEIST_LLM_SCAN"
LLM_SCAN_CMD_ENV = "DHARMA_ZEITGEIST_LLM_CMD"
LLM_SCAN_SOURCE_ENV = "DHARMA_ZEITGEIST_LLM_SOURCE"
LLM_SCAN_TIMEOUT_ENV = "DHARMA_ZEITGEIST_LLM_TIMEOUT_S"
LLM_SCAN_TIMEOUT_S = 45.0

WORLD_INBOX_NAME = "world_zeitgeist_inbox.jsonl"
WORLD_FEED_NAME = "world_signal_feed.jsonl"


class ZeitgeistSignal(BaseModel):
    """A detected external-world signal."""

    id: str = Field(default_factory=_new_id)
    source: str
    category: str
    title: str
    relevance_score: float = 0.0
    keywords: list[str] = Field(default_factory=list)
    description: str = ""
    timestamp: datetime = Field(default_factory=_utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


RESEARCH_KEYWORDS: set[str] = {
    "mechanistic interpretability",
    "participation ratio",
    "self-reference",
    "recursive",
    "eigenform",
    "value matrix",
    "attention head",
    "contraction",
    "phase transition",
    "consciousness",
    "self-model",
    "strange loop",
    "geb",
    "fixed point",
    "transformer geometry",
    "representation collapse",
    "sae",
    "sparse autoencoder",
    "circuit",
    "superposition",
    "agent",
    "agents",
    "coding agent",
    "ai engineer",
    "long context",
    "subquadratic",
    "inference",
    "scaffolding",
}

THREAT_KEYWORDS: set[str] = {
    "scooped",
    "preprint",
    "arxiv",
    "competing",
    "similar finding",
    "reproduced",
    "replicated",
    "contradicts",
}

WORLD_SIGNAL_CATEGORIES: set[str] = {
    "competing_research",
    "tool_release",
    "methodology",
    "threat",
    "opportunity",
    "market_movement",
    "product_company",
    "agent_infra",
    "security_regulatory",
    "practitioner_signal",
    "world_signal",
}


class ZeitgeistScanner:
    """Scan external-world inboxes and optional LLM scout output."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or dharma_state_dir()
        self._meta_dir = self._state_dir / "meta"
        self._world_feed_dir = self._state_dir / "world_feeds"
        self._signals: list[ZeitgeistSignal] = []
        self._output_path = self._meta_dir / "zeitgeist.md"
        self._log_path = self._meta_dir / "zeitgeist.jsonl"

    async def scan(self) -> list[ZeitgeistSignal]:
        """Run all external scan sources and persist newly observed signals."""
        self._signals = []
        self._signals.extend(await self._scan_external_feeds())

        if os.environ.get(LLM_SCAN_ENABLED_ENV) == "1":
            try:
                self._signals.extend(await self._scan_llm())
            except Exception as exc:
                logger.debug("LLM zeitgeist scan unavailable: %s", exc)

        self._save()
        return self.signals

    def keyword_relevance(self, text: str) -> float:
        text_lower = text.lower()
        matches = sum(1 for kw in RESEARCH_KEYWORDS if kw.lower() in text_lower)
        return min(1.0, matches / 5.0)

    def detect_threats(self, text: str) -> list[str]:
        text_lower = text.lower()
        return [kw for kw in THREAT_KEYWORDS if kw.lower() in text_lower]

    @property
    def signals(self) -> list[ZeitgeistSignal]:
        return list(self._signals)

    @property
    def latest_threats(self) -> list[ZeitgeistSignal]:
        return [signal for signal in self._signals if signal.category == "threat"]

    async def _scan_external_feeds(self) -> list[ZeitgeistSignal]:
        paths: list[Path] = [
            self._meta_dir / WORLD_INBOX_NAME,
            self._meta_dir / WORLD_FEED_NAME,
        ]
        if self._world_feed_dir.exists():
            paths.extend(sorted(self._world_feed_dir.glob("*.jsonl")))

        signals: list[ZeitgeistSignal] = []
        seen: set[str] = set()
        for path in paths:
            if not path.exists():
                continue
            for row in _read_jsonl_tail(path, max_lines=300):
                signal = self._row_to_signal(row, path=path)
                if signal is None:
                    continue
                dedupe_key = str(
                    row.get("id")
                    or row.get("url")
                    or f"{signal.source}:{signal.category}:{signal.title}"
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                signals.append(signal)
        signals.sort(key=lambda signal: signal.relevance_score, reverse=True)
        return signals[:80]

    def _row_to_signal(self, row: dict[str, Any], *, path: Path) -> ZeitgeistSignal | None:
        title = str(row.get("title") or row.get("name") or "").strip()
        if not title:
            return None
        description = str(
            row.get("description") or row.get("summary") or row.get("body") or ""
        ).strip()
        raw_category = str(row.get("category") or row.get("signal_type") or "world_signal")
        category = raw_category if raw_category in WORLD_SIGNAL_CATEGORIES else "world_signal"
        source = str(row.get("source") or row.get("publisher") or path.stem or "world_feed")
        score = _score(row, default=self.keyword_relevance(f"{title} {description}"))
        keywords = _keywords(row, f"{title} {description}")
        metadata = dict(row.get("metadata") or {})
        for key in (
            "url",
            "source_url",
            "publisher",
            "raw_source",
            "first_principles_questions",
            "iteration_steps",
            "adjacent_searches",
            "strategic_moves",
            "uncertainty",
        ):
            if key in row and key not in metadata:
                metadata[key] = row[key]
        metadata.setdefault("feed_path", str(path))
        return ZeitgeistSignal(
            id=str(row.get("id") or _new_id()),
            source=source,
            category=category,
            title=title[:180],
            relevance_score=round(max(0.0, min(1.0, score)), 3),
            keywords=keywords[:12],
            description=description[:1200],
            metadata=metadata,
        )

    async def _scan_llm(self) -> list[ZeitgeistSignal]:
        prompt = (
            "Return compact JSON only. Produce 3 current outside-world frontier "
            "signals about AI agents, autonomous coding, AI infrastructure, AI "
            "governance, interpretability, or related startups. Schema: "
            "{\"signals\":[{\"category\":\"competing_research|tool_release|"
            "methodology|threat|opportunity|product_company|agent_infra\","
            "\"title\":\"...\",\"relevance_score\":0.0,\"keywords\":[\"...\"],"
            "\"description\":\"...\",\"metadata\":{\"url\":\"...\"}}]}"
        )
        cmd = shlex.split(os.environ.get(LLM_SCAN_CMD_ENV, "claude -p"))
        if "{prompt}" in cmd:
            cmd = [prompt if part == "{prompt}" else part for part in cmd]
        else:
            cmd.append(prompt)

        try:
            timeout_s = float(os.environ.get(LLM_SCAN_TIMEOUT_ENV, LLM_SCAN_TIMEOUT_S))
        except ValueError:
            timeout_s = LLM_SCAN_TIMEOUT_S

        def _run() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )

        try:
            proc = await asyncio.to_thread(_run)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.debug("LLM zeitgeist scan unavailable: %s", exc)
            return []
        if proc.returncode != 0:
            logger.debug("LLM zeitgeist scan failed: %s", proc.stderr.strip())
            return []
        return _parse_llm_signals(proc.stdout)

    def _save(self) -> None:
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "a", encoding="utf-8") as fh:
            for signal in self._signals:
                fh.write(signal.model_dump_json() + "\n")

        now_str = _utc_now().strftime("%Y-%m-%d %H:%M UTC")
        lines = [f"# External Zeitgeist -- {now_str}", ""]
        if not self._signals:
            lines.append("No external signals detected.")
        for signal in self._signals:
            lines.append(
                f"- [{signal.category}] {signal.title} "
                f"(relevance={signal.relevance_score})"
            )
            if signal.keywords:
                lines.append(f"  Keywords: {', '.join(signal.keywords)}")
        self._output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def load_history(self) -> list[ZeitgeistSignal]:
        signals: list[ZeitgeistSignal] = []
        if not self._log_path.exists():
            return signals
        for row in _read_jsonl_tail(self._log_path, max_lines=10_000):
            try:
                signals.append(ZeitgeistSignal.model_validate(row))
            except Exception as exc:
                logger.debug("Skipping malformed zeitgeist history row: %s", exc)
        return signals

    def clear(self) -> None:
        self._signals = []


def _parse_llm_signals(raw: str) -> list[ZeitgeistSignal]:
    text = raw.strip()
    if not text:
        return []
    if not text.startswith(("{", "[")):
        for line in reversed(text.splitlines()):
            candidate = line.strip()
            if candidate.startswith(("{", "[")) and _loads_signal_payload(candidate) is not None:
                text = candidate
                break
        else:
            match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
            if not match:
                return []
            text = match.group(1)

    payload = _loads_signal_payload(text)
    if payload is None:
        return []
    rows = payload.get("signals", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []

    signals: list[ZeitgeistSignal] = []
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        category = str(row.get("category") or "world_signal").strip()
        if category not in WORLD_SIGNAL_CATEGORIES:
            category = "world_signal"
        signals.append(
            ZeitgeistSignal(
                source=os.environ.get(LLM_SCAN_SOURCE_ENV, "llm_scan"),
                category=category,
                title=title[:180],
                relevance_score=_score(row, default=0.0),
                keywords=_keywords(row, f"{title} {row.get('description') or ''}")[:12],
                description=str(row.get("description") or "").strip()[:1200],
                metadata=dict(row.get("metadata") or {}),
            )
        )
    return signals


def _loads_signal_payload(text: str) -> Any | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.debug("Zeitgeist JSON parse failed: %s", exc)
        return None
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "signals" in payload:
        return payload
    return None


def _read_jsonl_tail(path: Path, *, max_lines: int) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines[-max_lines:]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _score(row: dict[str, Any], *, default: float) -> float:
    for key in ("relevance_score", "score", "final_score", "confidence"):
        try:
            return max(0.0, min(1.0, float(row[key])))
        except (KeyError, TypeError, ValueError):
            continue
    return max(0.0, min(1.0, default))


def _keywords(row: dict[str, Any], text: str) -> list[str]:
    raw = row.get("keywords")
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    text_lower = text.lower()
    return [kw for kw in sorted(RESEARCH_KEYWORDS) if kw.lower() in text_lower]
