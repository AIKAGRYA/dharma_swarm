"""S4 world intelligence -- external zeitgeist awareness.

Zeitgeist means outside-world sensing: products, papers, companies, funding,
model releases, social/practitioner signals, customer pain, and adjacent
market or technical movement. Internal runtime pressure belongs to
``InternalPressureScanner``.

World adapters feed this scanner through ``~/.dharma/world_feeds/*.jsonl`` or
``~/.dharma/meta/world_zeitgeist_inbox.jsonl``. An opt-in LLM subprocess can
also perform broader landscape scanning when enabled.
"""

from __future__ import annotations

import asyncio
import hashlib
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
    "GEB",
    "fixed point",
    "transformer geometry",
    "representation collapse",
    "SAE",
    "sparse autoencoder",
    "circuit",
    "superposition",
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
    "company",
    "funding",
    "model_release",
    "tool_release",
    "paper",
    "social_signal",
    "competing_research",
    "methodology",
    "threat",
    "opportunity",
}


class ZeitgeistSignal(BaseModel):
    """A detected outside-world signal."""

    id: str = Field(default_factory=_new_id)
    source: str
    category: str
    title: str
    relevance_score: float = 0.0
    keywords: list[str] = Field(default_factory=list)
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)


class ZeitgeistScanner:
    """S4 scanner for external-world environmental signals."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or dharma_state_dir()
        self._meta_dir = self._state_dir / "meta"
        self._signals: list[ZeitgeistSignal] = []
        self._output_path = self._meta_dir / "zeitgeist.md"
        self._log_path = self._meta_dir / "zeitgeist.jsonl"

    async def scan(self) -> list[ZeitgeistSignal]:
        """Run all external scan sources and persist results."""
        self._signals = []
        self._signals.extend(await self._scan_world_feeds())

        if os.environ.get(LLM_SCAN_ENABLED_ENV) == "1":
            try:
                self._signals.extend(await self._scan_llm())
            except Exception as exc:
                logger.debug("LLM scan unavailable: %s", exc)

        self._save()
        return self._signals

    def keyword_relevance(self, text: str) -> float:
        """Score *text* relevance against research keywords."""
        text_lower = text.lower()
        matches = sum(1 for kw in RESEARCH_KEYWORDS if kw.lower() in text_lower)
        return min(1.0, matches / 5.0)

    def detect_threats(self, text: str) -> list[str]:
        """Return threat keywords found in *text*."""
        text_lower = text.lower()
        return [kw for kw in THREAT_KEYWORDS if kw.lower() in text_lower]

    @property
    def signals(self) -> list[ZeitgeistSignal]:
        """Return a copy of the most-recently scanned signals."""
        return list(self._signals)

    @property
    def latest_threats(self) -> list[ZeitgeistSignal]:
        """Return signals classified as ``threat``."""
        return [s for s in self._signals if s.category == "threat"]

    async def _scan_world_feeds(self) -> list[ZeitgeistSignal]:
        """Read external-world observations staged by feed adapters."""
        signals: list[ZeitgeistSignal] = []
        feed_paths = [self._meta_dir / "world_zeitgeist_inbox.jsonl"]
        feed_dir = self._state_dir / "world_feeds"
        if feed_dir.exists():
            feed_paths.extend(sorted(feed_dir.glob("*.jsonl")))

        for path in feed_paths:
            if not path.exists():
                continue
            for line_number, row in enumerate(_read_jsonl_tail(path, 500), start=1):
                signal = _signal_from_world_row(row, path=path, line_number=line_number)
                if signal is not None:
                    signals.append(signal)
        return signals

    async def _scan_llm(self) -> list[ZeitgeistSignal]:
        """Use an opt-in LLM command for external landscape scanning."""
        prompt = (
            "Return only compact JSON for DHARMA SWARM external zeitgeist. "
            "Be hungry and current. Produce 5 outside-world signals about AI "
            "startups, model releases, coding-agent tools, frontier papers, "
            "funding, practitioner chatter, open-source repos, product launches, "
            "customer pain, or adjacent market movement that could affect what "
            "the swarm should build. Do not report internal repo health. Schema: "
            "{\"signals\":[{\"category\":\"company|funding|model_release|"
            "tool_release|paper|social_signal|threat|opportunity\","
            "\"title\":\"...\",\"relevance_score\":0.0,"
            "\"keywords\":[\"...\"],\"description\":\"...\"}]}"
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
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.debug("LLM zeitgeist scan unavailable: %s", exc)
            return []
        if proc.returncode != 0:
            logger.debug("LLM zeitgeist scan failed: %s", proc.stderr.strip())
            return []
        return _parse_llm_signals(proc.stdout)

    def _save(self) -> None:
        """Persist signals to disk as JSONL log and Markdown summary."""
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as fh:
            for sig in self._signals:
                fh.write(sig.model_dump_json() + "\n")

        lines = [f"# Zeitgeist -- {_utc_now().strftime('%Y-%m-%d %H:%M UTC')}\n"]
        for sig in self._signals:
            lines.append(f"- [{sig.category}] {sig.title} (relevance={sig.relevance_score})")
            if sig.keywords:
                lines.append(f"  Keywords: {', '.join(sig.keywords)}")
        if not self._signals:
            lines.append("No signals detected.")
        self._output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def load_history(self) -> list[ZeitgeistSignal]:
        """Load all previously logged signals from the JSONL file."""
        signals: list[ZeitgeistSignal] = []
        for row in _read_jsonl_tail(self._log_path, 100000):
            try:
                signals.append(ZeitgeistSignal.model_validate(row))
            except Exception as exc:
                logger.debug("Skipping invalid zeitgeist history row: %s", exc)
        return signals

    def clear(self) -> None:
        """Reset in-memory signal list."""
        self._signals = []


def _signal_from_world_row(row: dict[str, Any], *, path: Path, line_number: int) -> ZeitgeistSignal | None:
    title = str(row.get("title") or row.get("name") or "").strip()
    if not title:
        return None

    category = _category(row.get("category") or row.get("type") or "opportunity")
    relevance = _safe_relevance(row.get("relevance_score", row.get("score", 0.3)))
    keywords = _keywords(row.get("keywords", []))
    source_url = str(row.get("source_url") or row.get("url") or "").strip()
    source = str(row.get("source") or f"world_feed:{path.stem}").strip()
    metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}
    metadata.update({"feed_path": str(path), "feed_line": line_number})
    if source_url:
        metadata["source_url"] = source_url
    for key in ("observed_at", "published_at", "publisher", "source_id"):
        if row.get(key):
            metadata[key] = str(row.get(key))

    signal_id = str(row.get("id") or row.get("signal_id") or "").strip()
    if not signal_id:
        signal_id = _stable_world_signal_id(source, source_url, title, row)
    timestamp = row.get("timestamp") or row.get("observed_at")
    kwargs = {"timestamp": timestamp} if timestamp else {}

    try:
        return ZeitgeistSignal(
            id=signal_id,
            source=source,
            category=category,
            title=title[:140],
            relevance_score=relevance,
            keywords=keywords[:8],
            description=str(row.get("description") or row.get("summary") or "").strip()[:800],
            metadata=metadata,
            **kwargs,
        )
    except Exception as exc:
        logger.debug("Skipping invalid world signal in %s:%s: %s", path, line_number, exc)
        return None


def _parse_llm_signals(raw: str) -> list[ZeitgeistSignal]:
    """Parse strict JSON or a CLI transcript containing a final JSON payload."""
    payload = _loads_signal_payload(_extract_json(raw.strip()))
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
        signals.append(
            ZeitgeistSignal(
                source=os.environ.get(LLM_SCAN_SOURCE_ENV, "world_llm_scan"),
                category=_category(row.get("category") or "opportunity"),
                title=title[:140],
                relevance_score=_safe_relevance(row.get("relevance_score", 0.0)),
                keywords=_keywords(row.get("keywords", []))[:8],
                description=str(row.get("description") or "").strip()[:800],
                metadata={"scan_type": "external_llm"},
            )
        )
    return signals


def _read_jsonl_tail(path: Path, max_lines: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Skipping malformed world feed row in %s", path)
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _extract_json(text: str) -> str:
    if text.startswith(("{", "[")):
        return text
    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if candidate.startswith(("{", "[")):
            return candidate
    match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
    return match.group(1) if match else ""


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


def _stable_world_signal_id(source: str, source_url: str, title: str, row: dict[str, Any]) -> str:
    observed_at = str(row.get("observed_at") or row.get("timestamp") or "")
    raw = "|".join((source, source_url, title, observed_at))
    return f"world_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _category(value: Any) -> str:
    category = str(value or "opportunity").strip()
    return category if category in WORLD_SIGNAL_CATEGORIES else "opportunity"


def _safe_relevance(value: Any) -> float:
    try:
        relevance = float(value)
    except (TypeError, ValueError):
        relevance = 0.3
    return max(0.0, min(1.0, relevance))


def _keywords(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(k).strip() for k in value if str(k).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []
