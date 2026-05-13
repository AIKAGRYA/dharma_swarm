"""Internal repo/runtime pressure sensing.

This keeps internal health signals out of ``zeitgeist`` while preserving the
S4-to-S3 gate pressure feedback path.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.models import _new_id, _utc_now
from dharma_swarm.zeitgeist import RESEARCH_KEYWORDS, THREAT_KEYWORDS

logger = logging.getLogger(__name__)


class InternalPressureSignal(BaseModel):
    """A detected internal pressure signal."""

    id: str = Field(default_factory=_new_id)
    source: str = "internal_pressure"
    category: str
    title: str
    relevance_score: float = 0.0
    keywords: list[str] = Field(default_factory=list)
    description: str = ""
    timestamp: datetime = Field(default_factory=_utc_now)


class InternalPressureScanner:
    """Scan local state and write gate pressure when internal gates are hot."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or dharma_state_dir()
        self._meta_dir = self._state_dir / "meta"
        self._output_path = self._meta_dir / "internal_pressure.md"
        self._log_path = self._meta_dir / "internal_pressure.jsonl"
        self._gate_pressure_path = self._meta_dir / "gate_pressure.json"
        self._signals: list[InternalPressureSignal] = []

    async def scan(self) -> list[InternalPressureSignal]:
        self._signals = []
        self._signals.extend(self._scan_shared_notes())
        self._signals.extend(self._scan_witness_logs())
        self._signals.extend(self._scan_stigmergy_density())
        self._write_gate_pressure()
        self._save()
        return list(self._signals)

    def _scan_shared_notes(self) -> list[InternalPressureSignal]:
        shared_dir = self._state_dir / "shared"
        if not shared_dir.exists():
            return []
        signals: list[InternalPressureSignal] = []
        for note_path in sorted(
            shared_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:10]:
            try:
                text = note_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            text_lower = text.lower()
            matched = [kw for kw in RESEARCH_KEYWORDS if kw.lower() in text_lower]
            threat = [kw for kw in THREAT_KEYWORDS if kw.lower() in text_lower]
            if not matched:
                continue
            signals.append(
                InternalPressureSignal(
                    category="threat" if threat else "methodology",
                    title=f"Internal note pressure in {note_path.name}",
                    relevance_score=min(1.0, len(matched) / 5.0),
                    keywords=matched[:8],
                    description=(
                        f"Found {len(matched)} research keywords"
                        + (f" and {len(threat)} threat keywords" if threat else "")
                    ),
                )
            )
        return signals

    def _scan_witness_logs(self) -> list[InternalPressureSignal]:
        witness_dir = self._state_dir / "witness"
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        log_file = witness_dir / f"witness_{today}.jsonl"
        if not log_file.exists():
            return []
        outcomes = {"BLOCKED": 0, "WARN": 0, "PASS": 0}
        try:
            lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        for line in lines[-200:]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            outcome = str(entry.get("outcome") or "")
            if outcome in outcomes:
                outcomes[outcome] += 1
        total = sum(outcomes.values())
        if total == 0:
            return []
        if outcomes["BLOCKED"] >= 3:
            return [
                InternalPressureSignal(
                    category="threat",
                    title="High gate block rate",
                    relevance_score=min(1.0, outcomes["BLOCKED"] / 10.0),
                    keywords=["gate_block", "witness", "telos_gates"],
                    description=(
                        f"{outcomes['BLOCKED']}/{total} gate checks blocked today."
                    ),
                )
            ]
        if total > 10 and outcomes["WARN"] > total * 0.3:
            return [
                InternalPressureSignal(
                    category="opportunity",
                    title="Elevated gate warnings",
                    relevance_score=0.4,
                    keywords=["gate_warn", "witness"],
                    description=f"{outcomes['WARN']}/{total} gate checks warned today.",
                )
            ]
        return []

    def _scan_stigmergy_density(self) -> list[InternalPressureSignal]:
        marks_path = self._state_dir / "stigmergy" / "marks.jsonl"
        if not marks_path.exists():
            return []
        try:
            lines = marks_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        if len([line for line in lines if line.strip()]) <= 1000:
            return []
        return [
            InternalPressureSignal(
                category="opportunity",
                title="High stigmergy density",
                relevance_score=0.3,
                keywords=["stigmergy", "coordination"],
                description=f"{len(lines)} marks indicate active colony intelligence.",
            )
        ]

    def _write_gate_pressure(self) -> None:
        try:
            self._meta_dir.mkdir(parents=True, exist_ok=True)
            gate_signals = [
                signal for signal in self._signals if "gate_block" in signal.keywords
            ]
            if gate_signals:
                now = time.time()
                self._gate_pressure_path.write_text(
                    json.dumps(
                        {
                            "trust_mode_override": "external_strict",
                            "reason": gate_signals[0].description,
                            "set_at": now,
                            "expires": now + 3600,
                        }
                    ),
                    encoding="utf-8",
                )
                return
            if self._gate_pressure_path.exists():
                data = json.loads(
                    self._gate_pressure_path.read_text(encoding="utf-8")
                )
                if float(data.get("expires") or 0.0) < time.time():
                    self._gate_pressure_path.unlink(missing_ok=True)
        except Exception:
            logger.debug("Gate pressure write failed", exc_info=True)

    def _save(self) -> None:
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "a", encoding="utf-8") as fh:
            for signal in self._signals:
                fh.write(signal.model_dump_json() + "\n")
        lines = [f"# Internal Pressure -- {_utc_now().strftime('%Y-%m-%d %H:%M UTC')}", ""]
        if not self._signals:
            lines.append("No internal pressure detected.")
        for signal in self._signals:
            lines.append(
                f"- [{signal.category}] {signal.title} "
                f"(relevance={signal.relevance_score})"
            )
        self._output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
