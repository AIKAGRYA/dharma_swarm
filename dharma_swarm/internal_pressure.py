"""Internal runtime pressure sensing.

This is deliberately not zeitgeist. It watches the organism's inside:
witness logs, shared notes, and stigmergy density. Its job is to feed the
internal health window and gate-pressure channel without pretending local
runtime pain is outside-world intelligence.
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
    """A signal from inside the runtime boundary."""

    id: str = Field(default_factory=_new_id)
    source: str
    category: str
    title: str
    severity_score: float = 0.0
    keywords: list[str] = Field(default_factory=list)
    description: str = ""
    timestamp: datetime = Field(default_factory=_utc_now)


class InternalPressureScanner:
    """Scans internal state and writes internal-pressure artifacts."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or dharma_state_dir()
        self._meta_dir = self._state_dir / "meta"
        self._signals: list[InternalPressureSignal] = []
        self._output_path = self._meta_dir / "internal_pressure.md"
        self._log_path = self._meta_dir / "internal_pressure.jsonl"

    async def scan(self) -> list[InternalPressureSignal]:
        """Scan internal state, persist pressure, and update gate pressure."""
        self._signals = []
        self._signals.extend(self._scan_shared_notes())
        self._signals.extend(self._scan_witness_logs())
        self._signals.extend(self._scan_stigmergy_density())
        self._write_gate_pressure()
        self._save()
        return list(self._signals)

    @property
    def signals(self) -> list[InternalPressureSignal]:
        return list(self._signals)

    def _scan_shared_notes(self) -> list[InternalPressureSignal]:
        signals: list[InternalPressureSignal] = []
        shared_dir = self._state_dir / "shared"
        if not shared_dir.exists():
            return signals
        note_paths = sorted(
            shared_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:10]
        for note_path in note_paths:
            try:
                text = note_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            text_lower = text.lower()
            matched_kw = [kw for kw in RESEARCH_KEYWORDS if kw.lower() in text_lower]
            threat_kw = [kw for kw in THREAT_KEYWORDS if kw.lower() in text_lower]
            if not matched_kw:
                continue
            severity = min(1.0, len(matched_kw) / 5.0)
            category = "internal_threat" if threat_kw else "internal_methodology"
            signals.append(
                InternalPressureSignal(
                    source="shared_notes",
                    category=category,
                    title=f"Keywords in {note_path.name}",
                    severity_score=round(severity, 2),
                    keywords=matched_kw[:5],
                    description=(
                        f"Found {len(matched_kw)} research keywords"
                        + (f", {len(threat_kw)} threat keywords" if threat_kw else "")
                    ),
                )
            )
        return signals

    def _scan_witness_logs(self) -> list[InternalPressureSignal]:
        signals: list[InternalPressureSignal] = []
        witness_dir = self._state_dir / "witness"
        if not witness_dir.exists():
            return signals
        try:
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            log_file = witness_dir / f"witness_{today}.jsonl"
            if not log_file.exists():
                return signals
            lines = log_file.read_text(encoding="utf-8", errors="replace").strip().split("\n")
        except OSError:
            logger.debug("Witness log scan failed", exc_info=True)
            return signals

        outcomes = {"BLOCKED": 0, "WARN": 0, "PASS": 0}
        for line in lines[-200:]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            outcome = entry.get("outcome", "")
            if outcome in outcomes:
                outcomes[outcome] += 1

        total = sum(outcomes.values())
        block_count = outcomes["BLOCKED"]
        if total > 0 and block_count >= 3:
            signals.append(
                InternalPressureSignal(
                    source="witness",
                    category="gate_pressure",
                    title="High internal gate block rate",
                    severity_score=min(1.0, block_count / 10.0),
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
                    source="witness",
                    category="gate_warning",
                    title="Elevated internal gate warnings",
                    severity_score=0.4,
                    keywords=["gate_warn", "witness"],
                    description=f"{outcomes['WARN']}/{total} gate checks warned today.",
                )
            )
        return signals

    def _scan_stigmergy_density(self) -> list[InternalPressureSignal]:
        marks_path = self._state_dir / "stigmergy" / "marks.jsonl"
        if not marks_path.exists():
            return []
        try:
            content = marks_path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            logger.debug("Stigmergy density scan failed", exc_info=True)
            return []
        if not content:
            return []
        lines = content.split("\n")
        if len(lines) <= 1000:
            return []
        return [
            InternalPressureSignal(
                source="stigmergy",
                category="internal_load",
                title="High stigmergy density",
                severity_score=0.3,
                description=f"{len(lines)} marks indicate active colony intelligence",
            )
        ]

    def _write_gate_pressure(self) -> None:
        pressure_path = self._meta_dir / "gate_pressure.json"
        pressure_path.parent.mkdir(parents=True, exist_ok=True)
        gate_signals = [s for s in self._signals if "gate_block" in s.keywords]
        try:
            if gate_signals:
                pressure_path.write_text(
                    json.dumps(
                        {
                            "trust_mode_override": "external_strict",
                            "reason": gate_signals[0].description,
                            "source": "internal_pressure",
                            "set_at": time.time(),
                            "expires": time.time() + 3600,
                        }
                    ),
                    encoding="utf-8",
                )
                logger.info("Internal pressure: external_strict gate override")
                return
            if pressure_path.exists():
                data = json.loads(pressure_path.read_text(encoding="utf-8"))
                if data.get("source") == "internal_pressure" and data.get("expires", 0) < time.time():
                    pressure_path.unlink(missing_ok=True)
        except Exception:
            logger.debug("Gate pressure write failed", exc_info=True)

    def _save(self) -> None:
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as fh:
            for sig in self._signals:
                fh.write(sig.model_dump_json() + "\n")

        now_str = _utc_now().strftime("%Y-%m-%d %H:%M UTC")
        lines: list[str] = [f"# Internal Pressure -- {now_str}\n"]
        for sig in self._signals:
            lines.append(f"- [{sig.category}] {sig.title} (severity={sig.severity_score})")
            if sig.keywords:
                lines.append(f"  Keywords: {', '.join(sig.keywords)}")
        if not self._signals:
            lines.append("No internal pressure detected.")
        self._output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = ["InternalPressureScanner", "InternalPressureSignal"]
