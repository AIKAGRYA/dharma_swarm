"""S4 external-world intelligence for Dharma Swarm."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import subprocess
from datetime import datetime, timedelta, timezone
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
ZEITGEIST_DEDUPE_TTL_DAYS = 14

RESEARCH_KEYWORDS: set[str] = {
    "agent",
    "agentic",
    "autonomous coding",
    "benchmark",
    "capability",
    "company",
    "computer use",
    "evaluation",
    "frontier",
    "github",
    "governance",
    "mechanistic interpretability",
    "open source",
    "research",
    "runtime",
    "tool use",
}

THREAT_KEYWORDS: set[str] = {
    "arxiv",
    "competitor",
    "preprint",
    "release",
    "scooped",
    "seed round",
    "similar",
    "startup",
}

WORLD_SIGNAL_FEEDS = (
    "world_zeitgeist_inbox.jsonl",
    "world_signal_feed.jsonl",
    "world_scout_observations.jsonl",
    "world_radar_observations.jsonl",
    "world_operator_drops.jsonl",
)


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


class ZeitgeistScanner:
    """Read external signal receipts and persist the canonical zeitgeist feed."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or dharma_state_dir()
        self._meta_dir = self._state_dir / "meta"
        self._signals: list[ZeitgeistSignal] = []
        self._output_path = self._meta_dir / "zeitgeist.md"
        self._log_path = self._meta_dir / "zeitgeist.jsonl"

    async def scan(self) -> list[ZeitgeistSignal]:
        """Run available external scan sources and persist normalized signals."""
        self._signals = self._scan_world_feeds()
        if os.environ.get(LLM_SCAN_ENABLED_ENV) == "1":
            try:
                self._signals.extend(await self._scan_llm())
            except Exception as exc:  # noqa: BLE001
                logger.debug("LLM scan unavailable: %s", exc)
        self._save()
        return self.signals

    def keyword_relevance(self, text: str) -> float:
        text_lower = text.lower()
        matches = sum(1 for keyword in RESEARCH_KEYWORDS if keyword in text_lower)
        return min(1.0, matches / 5.0)

    def detect_threats(self, text: str) -> list[str]:
        text_lower = text.lower()
        return [keyword for keyword in THREAT_KEYWORDS if keyword in text_lower]

    @property
    def signals(self) -> list[ZeitgeistSignal]:
        return list(self._signals)

    @property
    def latest_threats(self) -> list[ZeitgeistSignal]:
        return [signal for signal in self._signals if signal.category == "threat"]

    def _scan_world_feeds(self) -> list[ZeitgeistSignal]:
        signals: list[ZeitgeistSignal] = []
        seen: set[str] = set()
        for path in self._world_feed_paths():
            for row in _read_jsonl(path):
                signal = _row_to_signal(row, feed_path=path)
                if signal is None:
                    continue
                key = str(signal.metadata.get("dedupe_key") or signal.id)
                if key in seen:
                    continue
                seen.add(key)
                signals.append(signal)
        return signals

    def _world_feed_paths(self) -> list[Path]:
        paths = [self._meta_dir / name for name in WORLD_SIGNAL_FEEDS]
        feed_dir = self._meta_dir / "world_feeds"
        if feed_dir.exists():
            paths.extend(sorted(feed_dir.glob("*.jsonl")))
        radar_dir = self._meta_dir / "world_radar" / "feeds"
        if radar_dir.exists():
            paths.extend(sorted(radar_dir.glob("*.jsonl")))
        return paths

    async def _scan_llm(self) -> list[ZeitgeistSignal]:
        prompt = (
            "Return only compact JSON for Dharma Swarm external zeitgeist. "
            "Produce 3 current public-world signals about agentic AI systems, "
            "autonomous coding, AI infrastructure startups, governance, benchmarks, "
            "or mechanistic interpretability. Include URLs when known."
        )
        cmd = shlex.split(os.environ.get(LLM_SCAN_CMD_ENV, "claude -p"))
        cmd = [prompt if part == "{prompt}" else part for part in cmd]
        if prompt not in cmd:
            cmd.append(prompt)
        try:
            timeout_s = float(os.environ.get(LLM_SCAN_TIMEOUT_ENV, LLM_SCAN_TIMEOUT_S))
        except ValueError:
            timeout_s = LLM_SCAN_TIMEOUT_S

        def _run() -> subprocess.CompletedProcess[str]:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)

        try:
            proc = await asyncio.to_thread(_run)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
        if proc.returncode != 0:
            return []
        return _parse_llm_signals(proc.stdout)

    def _save(self) -> None:
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        recent_keys = self._recent_history_keys()
        with open(self._log_path, "a", encoding="utf-8") as fh:
            for signal in self._signals:
                key = _signal_dedupe_key(signal)
                if key in recent_keys:
                    continue
                fh.write(signal.model_dump_json() + "\n")
                recent_keys.add(key)
        now_str = _utc_now().strftime("%Y-%m-%d %H:%M UTC")
        lines = [f"# External Zeitgeist -- {now_str}", ""]
        for signal in self._signals:
            lines.append(
                f"- [{signal.category}] {signal.title} "
                f"(relevance={signal.relevance_score:.2f}, source={signal.source})"
            )
            url = signal.metadata.get("url") or signal.metadata.get("source_url")
            if url:
                lines.append(f"  Source: {url}")
        if not self._signals:
            lines.append("No external world signals detected.")
        self._output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _recent_history_keys(self) -> set[str]:
        cutoff = _utc_now() - timedelta(days=ZEITGEIST_DEDUPE_TTL_DAYS)
        keys: set[str] = set()
        for signal in self.load_history():
            timestamp = signal.timestamp
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            if timestamp < cutoff:
                continue
            keys.add(_signal_dedupe_key(signal))
        return keys

    def load_history(self) -> list[ZeitgeistSignal]:
        signals: list[ZeitgeistSignal] = []
        for row in _read_jsonl(self._log_path):
            try:
                signals.append(ZeitgeistSignal.model_validate(row))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Skipping malformed zeitgeist history row: %s", exc)
        return signals

    def clear(self) -> None:
        self._signals = []


def _row_to_signal(row: dict[str, Any], *, feed_path: Path) -> ZeitgeistSignal | None:
    title = str(row.get("title") or row.get("headline") or "").strip()
    if not title:
        return None
    source = str(row.get("source") or row.get("raw_source") or feed_path.stem).strip()
    category = str(row.get("category") or row.get("kind") or "opportunity").strip()
    description = str(row.get("description") or row.get("summary") or "").strip()
    try:
        relevance = float(row.get("relevance_score", row.get("score", 0.0)) or 0.0)
    except (TypeError, ValueError):
        relevance = 0.0
    keywords = _string_list(row.get("keywords") or row.get("tags") or [])
    metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}
    for key in (
        "url",
        "source_url",
        "raw_source",
        "source_type",
        "promotion_status",
        "first_principles_questions",
        "iteration_steps",
        "adjacent_searches",
        "strategic_moves",
        "incubation_path",
    ):
        if key in row and key not in metadata:
            metadata[key] = row[key]
    metadata["feed_path"] = str(feed_path)
    metadata.setdefault("dedupe_key", _dedupe_key(row, title=title, feed_path=feed_path))
    return ZeitgeistSignal(
        id=str(row.get("id") or row.get("signal_id") or _new_id()),
        source=source or "world_feed",
        category=category or "opportunity",
        title=title[:160],
        relevance_score=max(0.0, min(1.0, relevance)),
        keywords=keywords[:12],
        description=description[:1200],
        metadata=metadata,
    )


def _parse_llm_signals(raw: str) -> list[ZeitgeistSignal]:
    text = raw.strip()
    if not text:
        return []
    if not text.startswith(("{", "[")):
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
        signal = _row_to_signal(row, feed_path=Path("llm_scan"))
        if signal is None:
            continue
        signal.source = os.environ.get(LLM_SCAN_SOURCE_ENV, "llm_scan")
        signals.append(signal)
    return signals


def _loads_signal_payload(text: str) -> Any | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "signals" in payload:
        return payload
    return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed reading world feed %s: %s", path, exc)
    return rows


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _dedupe_key(row: dict[str, Any], *, title: str, feed_path: Path) -> str:
    url = str(row.get("url") or row.get("source_url") or "").strip().lower()
    if url:
        return url
    source = str(row.get("source") or row.get("raw_source") or feed_path.stem).lower()
    return f"{source}:{title.lower()}"


def _signal_dedupe_key(signal: ZeitgeistSignal) -> str:
    metadata_key = str(signal.metadata.get("dedupe_key") or "").strip().lower()
    if metadata_key:
        return metadata_key
    url = str(signal.metadata.get("url") or signal.metadata.get("source_url") or "").strip().lower()
    if url:
        return url
    return f"{signal.source.lower()}:{signal.title.lower()}"
