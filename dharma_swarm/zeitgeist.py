"""S4 world intelligence -- external zeitgeist awareness.

Zeitgeist means outside-world sensing: products, papers, companies, funding,
model releases, social/practitioner signals, customer pain, and adjacent
market/technical movement. It is not repo health and not internal runtime
pressure.

World adapters feed this scanner through ``~/.dharma/world_feeds/*.jsonl`` or
``~/.dharma/meta/world_zeitgeist_inbox.jsonl``. An opt-in LLM subprocess can
also perform broader landscape scanning when enabled.

Output: ``~/.dharma/meta/zeitgeist.md`` + ``zeitgeist.jsonl``
Orchestrated cadence: every 600 s (ZEITGEIST_INTERVAL in orchestrate_live).
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
from dharma_swarm.daemon_config import dharma_state_dir
from typing import Any

from pydantic import BaseModel, Field

from dharma_swarm.models import _new_id, _utc_now

logger = logging.getLogger(__name__)

LLM_SCAN_ENABLED_ENV = "DHARMA_ZEITGEIST_LLM_SCAN"
LLM_SCAN_CMD_ENV = "DHARMA_ZEITGEIST_LLM_CMD"
LLM_SCAN_SOURCE_ENV = "DHARMA_ZEITGEIST_LLM_SOURCE"
LLM_SCAN_TIMEOUT_ENV = "DHARMA_ZEITGEIST_LLM_TIMEOUT_S"
LLM_SCAN_TIMEOUT_S = 45.0


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class ZeitgeistSignal(BaseModel):
    """A detected outside-world signal.

    Attributes:
        id: Unique signal identifier.
        source: Origin of the signal (world_feed, world_llm_scan, manual, adapter name).
        category: Signal classification bucket.
        title: Human-readable summary.
        relevance_score: Relevance to active research, 0.0--1.0.
        keywords: Matched keywords that triggered the signal.
        description: Extended explanation.
        timestamp: UTC timestamp of detection.
    """

    id: str = Field(default_factory=_new_id)
    source: str  # "world_feed", "world_llm_scan", "manual", or adapter name
    category: str
    title: str
    relevance_score: float = 0.0
    keywords: list[str] = Field(default_factory=list)
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)


# ---------------------------------------------------------------------------
# Keyword dictionaries
# ---------------------------------------------------------------------------

# Keywords relevant to the two active research tracks (R_V + URA).
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

# Keywords that indicate competitive or contradictory external work.
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


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


class ZeitgeistScanner:
    """S4 scanner that detects outside-world environmental signals.

    The scanner reads world-feed inbox files written by external adapters and
    optionally delegates to a configured LLM command for broader landscape
    awareness. It intentionally does not inspect repo files, witness logs, or
    internal health state; those belong to ``InternalPressureScanner``.
    Results are persisted as a Markdown summary and a JSONL log.

    Args:
        state_dir: Root of the ``.dharma`` state tree.  Defaults to
            ``~/.dharma``.
    """

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or (dharma_state_dir())
        self._meta_dir = self._state_dir / "meta"
        self._signals: list[ZeitgeistSignal] = []
        self._output_path = self._meta_dir / "zeitgeist.md"
        self._log_path = self._meta_dir / "zeitgeist.jsonl"

    # -- public API ---------------------------------------------------------

    async def scan(self) -> list[ZeitgeistSignal]:
        """Run all available scan sources and persist results.

        Returns:
            List of newly detected signals.
        """
        self._signals = []

        world_signals = await self._scan_world_feeds()
        self._signals.extend(world_signals)

        # Try an LLM scan only when explicitly enabled. S4 should be able to
        # run unattended without surprise network/model calls.
        if os.environ.get(LLM_SCAN_ENABLED_ENV) == "1":
            try:
                llm_signals = await self._scan_llm()
                self._signals.extend(llm_signals)
            except Exception as exc:
                logger.debug("LLM scan unavailable: %s", exc)

        # Persist
        self._save()

        return self._signals

    def keyword_relevance(self, text: str) -> float:
        """Score *text* relevance against ``RESEARCH_KEYWORDS``.

        Returns:
            Float in [0.0, 1.0].  One point per keyword match, capped
            at 5 (= 1.0).
        """
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

    # -- scan sources -------------------------------------------------------

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
            try:
                rows = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                logger.debug("World feed read failed: %s", path, exc_info=True)
                continue
            for line_number, line in enumerate(rows[-500:], start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("Skipping malformed world feed row in %s:%s", path, line_number)
                    continue
                if not isinstance(row, dict):
                    continue
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

    # -- persistence --------------------------------------------------------

    def _save(self) -> None:
        """Persist signals to disk as JSONL log and Markdown summary."""
        self._meta_dir.mkdir(parents=True, exist_ok=True)

        # Append to JSONL log
        with open(self._log_path, "a") as fh:
            for sig in self._signals:
                fh.write(sig.model_dump_json() + "\n")

        # Write summary markdown
        now_str = _utc_now().strftime("%Y-%m-%d %H:%M UTC")
        lines: list[str] = [f"# Zeitgeist -- {now_str}\n"]
        for sig in self._signals:
            lines.append(
                f"- [{sig.category}] {sig.title} (relevance={sig.relevance_score})"
            )
            if sig.keywords:
                lines.append(f"  Keywords: {', '.join(sig.keywords)}")
        if not self._signals:
            lines.append("No signals detected.")
        self._output_path.write_text("\n".join(lines) + "\n")

    # -- loading historical signals -----------------------------------------

    def load_history(self) -> list[ZeitgeistSignal]:
        """Load all previously logged signals from the JSONL file.

        Returns:
            List of ``ZeitgeistSignal`` instances, oldest first.
        """
        signals: list[ZeitgeistSignal] = []
        if not self._log_path.exists():
            return signals
        try:
            for line in self._log_path.read_text().strip().split("\n"):
                if line.strip():
                    signals.append(ZeitgeistSignal.model_validate_json(line))
        except Exception as exc:
            logger.warning("Failed to load zeitgeist history: %s", exc)
        return signals

    def clear(self) -> None:
        """Reset in-memory signal list (does not delete persisted files)."""
        self._signals = []


def _signal_from_world_row(
    row: dict[str, Any],
    *,
    path: Path,
    line_number: int,
) -> ZeitgeistSignal | None:
    title = str(row.get("title") or row.get("name") or "").strip()
    if not title:
        return None

    category = _category(row.get("category") or row.get("type") or "opportunity")
    relevance = _safe_relevance(row.get("relevance_score", row.get("score", 0.3)))
    keywords = _keywords(row.get("keywords", []))
    source_url = str(row.get("source_url") or row.get("url") or "").strip()
    source = str(row.get("source") or f"world_feed:{path.stem}").strip()
    description = str(row.get("description") or row.get("summary") or "").strip()
    metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}
    metadata.update({"feed_path": str(path), "feed_line": line_number})
    if source_url:
        metadata["source_url"] = source_url
    if row.get("observed_at"):
        metadata["observed_at"] = str(row.get("observed_at"))

    signal_id = str(row.get("id") or row.get("signal_id") or "").strip()
    if not signal_id:
        signal_id = _stable_world_signal_id(source, source_url, title, row)

    kwargs: dict[str, Any] = {}
    timestamp = row.get("timestamp") or row.get("observed_at")
    if timestamp:
        kwargs["timestamp"] = timestamp

    try:
        return ZeitgeistSignal(
            id=signal_id,
            source=source,
            category=category,
            title=title[:140],
            relevance_score=relevance,
            keywords=keywords[:8],
            description=description[:800],
            metadata=metadata,
            **kwargs,
        )
    except Exception as exc:
        logger.debug("Skipping invalid world signal in %s:%s: %s", path, line_number, exc)
        return None


def _stable_world_signal_id(
    source: str,
    source_url: str,
    title: str,
    row: dict[str, Any],
) -> str:
    observed_at = str(row.get("observed_at") or row.get("timestamp") or "")
    raw = "|".join((source, source_url, title, observed_at))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"world_{digest}"


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


def _parse_llm_signals(raw: str) -> list[ZeitgeistSignal]:
    """Parse strict JSON, or a CLI transcript containing a final JSON payload."""
    text = raw.strip()
    if not text:
        return []

    if not text.startswith(("{", "[")):
        for line in reversed(text.splitlines()):
            candidate = line.strip()
            if (
                candidate.startswith(("{", "["))
                and _loads_signal_payload(candidate) is not None
            ):
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
        category = _category(row.get("category") or "opportunity")
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        relevance = _safe_relevance(row.get("relevance_score", 0.0))
        keywords = _keywords(row.get("keywords", []))
        signals.append(
            ZeitgeistSignal(
                source=os.environ.get(LLM_SCAN_SOURCE_ENV, "world_llm_scan"),
                category=category,
                title=title[:140],
                relevance_score=relevance,
                keywords=keywords[:8],
                description=str(row.get("description") or "").strip()[:800],
                metadata={"scan_type": "external_llm"},
            )
        )
    return signals


def _loads_signal_payload(text: str) -> Any | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.debug("LLM zeitgeist JSON parse failed: %s", exc)
        return None
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "signals" in payload:
        return payload
    return None
