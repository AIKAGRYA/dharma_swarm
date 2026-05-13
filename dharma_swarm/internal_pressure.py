"""Internal pressure scanner for local runtime and governance signals.

This owns the inward-facing scan work that used to sit in ``zeitgeist.py``:
shared notes, witness gate pressure, and stigmergy density. Keeping it separate
preserves a clean boundary: zeitgeist sees the world; internal pressure sees the
organism.
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
    """Scan local organism pressure without polluting external zeitgeist."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or dharma_state_dir()
        self._meta_dir = self._state_dir / "meta"
        self._log_path = self._meta_dir / "internal_pressure.jsonl"
        self._output_path = self._meta_dir / "internal_pressure.md"
        self._signals: list[InternalPressureSignal] = []

    async def scan(self) -> list[InternalPressureSignal]:
        self._signals = []
        self._signals.extend(self._scan_shared_notes())
        self._signals.extend(self._scan_witness_pressure())
        self._signals.extend(self._scan_stigmergy_density())
        self._save()
        return self.signals

    @property
    def signals(self) -> list[InternalPressureSignal]:
        return list(self._signals)

    def _scan_shared_notes(self) -> list[InternalPressureSignal]:
        shared_dir = self._state_dir / "shared"
        if not shared_dir.exists():
            return []
        signals: list[InternalPressureSignal] = []
        note_paths = sorted(
            shared_dir.glob("*.md"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:10]
        for note_path in note_paths:
            try:
                text_lower = note_path.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            matched = [kw for kw in RESEARCH_KEYWORDS if kw.lower() in text_lower]
            threats = [kw for kw in THREAT_KEYWORDS if kw.lower() in text_lower]
            if not matched:
                continue
            signals.append(
                InternalPressureSignal(
                    category="threat" if threats else "methodology",
                    title=f"Keywords in {note_path.name}",
                    relevance_score=min(1.0, len(matched) / 5.0),
                    keywords=matched[:5],
                    description=(
                        f"Found {len(matched)} research keywords"
                        + (f", {len(threats)} threat keywords" if threats else "")
                    ),
                )
            )
        return signals

    def _scan_witness_pressure(self) -> list[InternalPressureSignal]:
        witness_dir = self._state_dir / "witness"
        if not witness_dir.exists():
            return []
        try:
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            log_file = witness_dir / f"witness_{today}.jsonl"
            if not log_file.exists():
                return []
            outcomes = {"BLOCKED": 0, "WARN": 0, "PASS": 0}
            lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines[-200:]:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                outcome = str(entry.get("outcome") or "")
                if outcome in outcomes:
                    outcomes[outcome] += 1
            return self._witness_signals(outcomes)
        except Exception:
            logger.debug("Witness pressure scan failed", exc_info=True)
            return []

    def _witness_signals(self, outcomes: dict[str, int]) -> list[InternalPressureSignal]:
        total = sum(outcomes.values())
        block_count = outcomes["BLOCKED"]
        signals: list[InternalPressureSignal] = []
        if total > 0 and block_count >= 3:
            signals.append(
                InternalPressureSignal(
                    category="threat",
                    title="High gate block rate (internal pressure)",
                    relevance_score=min(1.0, block_count / 10.0),
                    keywords=["gate_block", "witness", "telos_gates"],
                    description=(
                        f"{block_count}/{total} gate checks blocked today. "
                        "Indicates governance pressure or agent drift."
                    ),
                )
            )
        elif total > 10 and outcomes["WARN"] > total * 0.3:
            signals.append(
                InternalPressureSignal(
                    category="opportunity",
                    title="Elevated gate warnings (internal pressure)",
                    relevance_score=0.4,
                    keywords=["gate_warn", "witness"],
                    description=f"{outcomes['WARN']}/{total} gate checks warned today.",
                )
            )
        self._write_gate_pressure(signals)
        return signals

    def _write_gate_pressure(self, signals: list[InternalPressureSignal]) -> None:
        try:
            pressure_path = self._meta_dir / "gate_pressure.json"
            pressure_path.parent.mkdir(parents=True, exist_ok=True)
            gate_signals = [signal for signal in signals if "gate_block" in signal.keywords]
            if gate_signals:
                now = time.time()
                pressure_path.write_text(
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
                logger.info("Internal pressure tightened gate mode for one hour")
            elif pressure_path.exists():
                data = json.loads(pressure_path.read_text(encoding="utf-8"))
                if float(data.get("expires", 0) or 0) < time.time():
                    pressure_path.unlink(missing_ok=True)
        except Exception:
            logger.debug("Gate pressure write failed", exc_info=True)

    def _scan_stigmergy_density(self) -> list[InternalPressureSignal]:
        marks_path = self._state_dir / "stigmergy" / "marks.jsonl"
        if not marks_path.exists():
            return []
        try:
            content = marks_path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return []
        if not content:
            return []
        lines = content.splitlines()
        if len(lines) <= 1000:
            return []
        return [
            InternalPressureSignal(
                category="opportunity",
                title="High stigmergy density",
                relevance_score=0.3,
                description=f"{len(lines)} marks indicate active colony intelligence",
            )
        ]

    def _save(self) -> None:
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "a", encoding="utf-8") as fh:
            for signal in self._signals:
                fh.write(signal.model_dump_json() + "\n")
        now_str = _utc_now().strftime("%Y-%m-%d %H:%M UTC")
        lines = [f"# Internal Pressure -- {now_str}", ""]
        if not self._signals:
            lines.append("No internal pressure signals detected.")
        for signal in self._signals:
            lines.append(f"- [{signal.category}] {signal.title}")
        self._output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
