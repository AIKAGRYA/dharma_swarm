"""Internal pressure sensing separated from external zeitgeist."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.daemon_config import dharma_state_dir

INTERNAL_RESEARCH_KEYWORDS = {
    "mechanistic interpretability",
    "participation ratio",
    "self-reference",
    "recursive",
    "eigenform",
    "value matrix",
    "attention head",
    "contraction",
    "phase transition",
    "fixed point",
    "superposition",
}

INTERNAL_THREAT_KEYWORDS = {
    "scooped",
    "preprint",
    "arxiv",
    "competing",
    "contradicts",
    "blocked",
    "failed",
}


@dataclass(frozen=True)
class InternalPressureSignal:
    """A detected internal runtime or repo pressure signal."""

    source: str
    category: str
    title: str
    relevance_score: float = 0.0
    keywords: list[str] = field(default_factory=list)
    description: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InternalPressureScanner:
    """Scanner for local shared notes, witness logs, and stigmergy pressure."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or dharma_state_dir()
        self._meta_dir = self._state_dir / "meta"
        self._signals: list[InternalPressureSignal] = []
        self._log_path = self._meta_dir / "internal_pressure.jsonl"
        self._summary_path = self._meta_dir / "internal_pressure.md"
        self._gate_pressure_path = self._meta_dir / "gate_pressure.json"

    async def scan(self) -> list[InternalPressureSignal]:
        """Run internal pressure scans and persist results."""
        self._signals = []
        self._signals.extend(self._scan_shared_notes())
        self._signals.extend(self._scan_witness_logs())
        self._signals.extend(self._scan_stigmergy())
        self._save()
        return list(self._signals)

    def _scan_shared_notes(self) -> list[InternalPressureSignal]:
        signals: list[InternalPressureSignal] = []
        shared_dir = self._state_dir / "shared"
        if not shared_dir.exists():
            return signals
        note_paths = sorted(shared_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
        for note_path in note_paths:
            try:
                text = note_path.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            matched = [kw for kw in INTERNAL_RESEARCH_KEYWORDS if kw.lower() in text]
            threats = [kw for kw in INTERNAL_THREAT_KEYWORDS if kw.lower() in text]
            if not matched:
                continue
            category = "internal_threat" if threats else "internal_methodology"
            signals.append(
                InternalPressureSignal(
                    source="shared_notes",
                    category=category,
                    title=f"Keywords in {note_path.name}",
                    relevance_score=round(min(1.0, len(matched) / 5.0), 2),
                    keywords=matched[:5],
                    description=f"Found {len(matched)} internal research keyword(s).",
                )
            )
        return signals

    def _scan_witness_logs(self) -> list[InternalPressureSignal]:
        witness_dir = self._state_dir / "witness"
        if not witness_dir.exists():
            return []
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
                outcome = json.loads(line).get("outcome", "")
            except json.JSONDecodeError:
                continue
            if outcome in outcomes:
                outcomes[outcome] += 1

        total = sum(outcomes.values())
        if total <= 0:
            return []
        block_count = outcomes["BLOCKED"]
        if block_count >= 3:
            signal = InternalPressureSignal(
                source="witness",
                category="gate_pressure",
                title="High gate block rate",
                relevance_score=min(1.0, block_count / 10.0),
                keywords=["gate_block", "witness", "telos_gates"],
                description=f"{block_count}/{total} gate checks blocked today.",
            )
            self._write_gate_pressure(outcomes)
            return [signal]
        if total > 10 and outcomes["WARN"] > total * 0.3:
            return [
                InternalPressureSignal(
                    source="witness",
                    category="gate_warning",
                    title="Elevated gate warnings",
                    relevance_score=0.4,
                    keywords=["gate_warn", "witness"],
                    description=f"{outcomes['WARN']}/{total} gate checks warned today.",
                )
            ]
        return []

    def _scan_stigmergy(self) -> list[InternalPressureSignal]:
        marks_path = self._state_dir / "stigmergy" / "marks.jsonl"
        if not marks_path.exists():
            return []
        try:
            count = sum(1 for line in marks_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
        except OSError:
            return []
        if count <= 1000:
            return []
        return [
            InternalPressureSignal(
                source="stigmergy",
                category="stigmergy_pressure",
                title="High stigmergy density",
                relevance_score=0.5,
                keywords=["stigmergy", "coordination"],
                description=f"{count} stigmergy marks detected.",
            )
        ]

    def _save(self) -> None:
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as fh:
            for signal in self._signals:
                fh.write(json.dumps(asdict(signal), sort_keys=True) + "\n")
        lines = [f"# Internal Pressure -- {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"]
        for signal in self._signals:
            lines.append(f"- [{signal.category}] {signal.title} (relevance={signal.relevance_score})")
        if not self._signals:
            lines.append("No internal pressure detected.")
        self._summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_gate_pressure(self, outcomes: dict[str, int]) -> None:
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        self._gate_pressure_path.write_text(
            json.dumps(
                {
                    "source": "internal_pressure",
                    "outcomes": outcomes,
                    "trust_mode_override": "external_strict",
                    "set_at": time.time(),
                    "expires": time.time() + 3600,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


__all__ = ["InternalPressureScanner", "InternalPressureSignal"]
