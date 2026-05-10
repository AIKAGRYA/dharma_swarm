"""Bhed Gnan Monitor v0 for resident-intelligence outputs.

v0 is intentionally narrow. It does not perform semantic grounding and does
not claim to detect lexical-only gate passes. That work belongs to Semantic
Anekanta. This monitor only records:

- gate_signal: what existing GateDecisionRecord / Outcome rows already say
- text_pattern_signal: cheap textual register flags
- needs_external_review: explicit coverage gaps or non-decisive signals

Provenance for this v0 shape:
- Outcome cd98cbe0379a46e1
- ValueEvent 2818bff38c354cae
- GateDecisionRecord d3fe2347fe8f446b
- Outcome 75986f1de842450f
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.bhed_gnan_gate import (
    CONFIDENCE_MARKERS,
    EXPERIENTIAL_PATTERNS,
    FALSE_PROVENANCE_PATTERNS,
    HEDGE_PATTERNS,
    UNCERTAINTY_MARKERS,
)
from dharma_swarm.metrics import MetricsAnalyzer
from dharma_swarm.ontology import OntologyObj, OntologyRegistry
from dharma_swarm.ontology_runtime import get_shared_registry

DEFAULT_WITNESS_DIR = Path.home() / ".dharma/witness/bhed_gnan"
_DERIVED_GATE_ECHOES: dict[str, str] = {
    # TelosGatekeeper currently computes SVABHAAVA directly from
    # evaluate_anekanta(); do not let this look like independent coverage.
    "SVABHAAVA": "ANEKANTA",
}


@dataclass(frozen=True)
class BhedGnanSignal:
    label: str
    name: str
    severity: str
    evidence: str
    source: str = ""

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BhedGnanResult:
    source_path: str
    text_sha256: str
    word_count: int
    resolution: str = "whole"
    segment_id: str = ""
    gate_decision_id: str = ""
    outcome_id: str = ""
    prompt_class: str = ""
    position_signature: str = ""
    lexical_diversity: float = 0.0
    confidence_density: float = 0.0
    prior_position_similarity: float = 0.0
    signals: list[BhedGnanSignal] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "text_sha256": self.text_sha256,
            "word_count": self.word_count,
            "resolution": self.resolution,
            "segment_id": self.segment_id,
            "gate_decision_id": self.gate_decision_id,
            "outcome_id": self.outcome_id,
            "prompt_class": self.prompt_class,
            "position_signature": self.position_signature,
            "lexical_diversity": self.lexical_diversity,
            "confidence_density": self.confidence_density,
            "prior_position_similarity": self.prior_position_similarity,
            "signals": [signal.to_json() for signal in self.signals],
        }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text
    raw_meta = parts[0].removeprefix("---\n")
    metadata: dict[str, str] = {}
    for line in raw_meta.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata, parts[1]


def _contains(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE | re.DOTALL) for pattern in patterns)


def _count_markers(markers: tuple[str, ...], text: str) -> int:
    lowered = text.lower()
    return sum(1 for marker in markers if marker in lowered)


def _compact(value: Any, limit: int = 220) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text[:limit]


def _slug(text: str, limit: int = 48) -> str:
    lowered = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return (slug or "untitled")[:limit].strip("-") or "untitled"


def _split_markdown_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current_id = "preamble"
    current_lines: list[str] = []
    for line in text.splitlines():
        if re.match(r"^#{1,6}\s+\S", line):
            if current_lines:
                sections.append((current_id, current_lines))
            current_id = _slug(line.lstrip("#").strip())
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_id, current_lines))
    return [
        (section_id, "\n".join(lines).strip())
        for section_id, lines in sections
        if "\n".join(lines).strip()
    ]


def _split_paragraphs(text: str) -> list[tuple[str, str]]:
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if len(paragraph.split()) >= 12
    ]
    return [
        (f"paragraph-{index:03d}", paragraph)
        for index, paragraph in enumerate(paragraphs, start=1)
    ]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _lexical_diversity(text: str) -> float:
    tokens = _tokenize(text)
    if not tokens:
        return 0.0
    return len(set(tokens)) / len(tokens)


def _position_signature(text: str) -> str:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if not sentences:
        return ""
    candidates = [
        sentence for sentence in sentences
        if re.search(r"\b(is|are|means|must|should|cannot|can't|therefore|because)\b", sentence.lower())
    ]
    signature_source = (candidates[0] if candidates else sentences[0]).lower()
    tokens = [token for token in _tokenize(signature_source) if len(token) > 2]
    return " ".join(tokens[:20])


def _jaccard_similarity(left: str, right: str) -> float:
    left_tokens = set(_tokenize(left))
    right_tokens = set(_tokenize(right))
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = left_tokens & right_tokens
    union = left_tokens | right_tokens
    return len(intersection) / len(union)


def _subset_coverage(source: str, target: str) -> float:
    source_tokens = set(_tokenize(source))
    target_tokens = set(_tokenize(target))
    if not source_tokens:
        return 0.0
    return len(source_tokens & target_tokens) / len(source_tokens)


class BhedGnanMonitor:
    """Monitor resident-intelligence outputs without pretending semantic depth."""

    def __init__(
        self,
        registry: OntologyRegistry | None = None,
        witness_dir: Path = DEFAULT_WITNESS_DIR,
    ) -> None:
        self.registry = registry or get_shared_registry()
        self.witness_dir = witness_dir
        self._metrics = MetricsAnalyzer()

    def analyze_file(self, path: Path) -> BhedGnanResult:
        text = path.expanduser().read_text(encoding="utf-8")
        metadata, body = _split_frontmatter(text)
        return self.analyze_text(
            body,
            source_path=str(path),
            gate_decision_id=metadata.get("gate_decision_id", ""),
            outcome_id=metadata.get("outcome_id", ""),
            prompt_class=metadata.get("prompt_class", ""),
        )

    def analyze_file_segments(
        self,
        path: Path,
        *,
        resolutions: tuple[str, ...] = ("whole",),
    ) -> list[BhedGnanResult]:
        text = path.expanduser().read_text(encoding="utf-8")
        metadata, body = _split_frontmatter(text)
        source_path = str(path)
        results: list[BhedGnanResult] = []
        for resolution in resolutions:
            if resolution == "whole":
                results.append(self.analyze_text(
                    body,
                    source_path=source_path,
                    gate_decision_id=metadata.get("gate_decision_id", ""),
                    outcome_id=metadata.get("outcome_id", ""),
                    prompt_class=metadata.get("prompt_class", ""),
                    resolution="whole",
                ))
                continue
            if resolution == "section":
                segments = _split_markdown_sections(body)
            elif resolution == "paragraph":
                segments = _split_paragraphs(body)
            else:
                raise ValueError(f"Unknown resolution: {resolution}")
            for segment_id, segment_text in segments:
                results.append(self.analyze_text(
                    segment_text,
                    source_path=f"{source_path}::{resolution}:{segment_id}",
                    gate_decision_id=metadata.get("gate_decision_id", ""),
                    outcome_id=metadata.get("outcome_id", ""),
                    prompt_class=metadata.get("prompt_class", ""),
                    resolution=resolution,
                    segment_id=segment_id,
                    include_gate_signals=False,
                    include_coverage_signal=False,
                ))
        return results

    def analyze_text(
        self,
        text: str,
        *,
        source_path: str = "",
        gate_decision_id: str = "",
        outcome_id: str = "",
        prompt_class: str = "",
        resolution: str = "whole",
        segment_id: str = "",
        include_gate_signals: bool = True,
        include_coverage_signal: bool = True,
        previous_text: str = "",
    ) -> BhedGnanResult:
        signals: list[BhedGnanSignal] = []
        if include_gate_signals:
            signals.extend(self._gate_signals(gate_decision_id, outcome_id))
        signals.extend(self._text_pattern_signals(text))
        position_signature = _position_signature(text)
        lexical_diversity = _lexical_diversity(text)
        confidence_density = (
            _count_markers(CONFIDENCE_MARKERS, text) / max(len(text.split()), 1)
        )
        prior_similarity = 0.0
        if previous_text:
            prior_signature = _position_signature(previous_text)
            prior_similarity = _jaccard_similarity(position_signature, prior_signature)
            prior_coverage = _subset_coverage(prior_signature, position_signature)
            previous_diversity = _lexical_diversity(previous_text)
            previous_confidence_density = (
                _count_markers(CONFIDENCE_MARKERS, previous_text)
                / max(len(previous_text.split()), 1)
            )
            current_words = len(text.split())
            previous_words = max(len(previous_text.split()), 1)
            elaborated = (
                current_words >= int(previous_words * 1.25)
                or lexical_diversity >= previous_diversity + 0.05
                or confidence_density >= previous_confidence_density + 0.02
            )
            if (prior_similarity >= 0.5 or prior_coverage >= 0.8) and elaborated:
                signals.append(BhedGnanSignal(
                    label="text_pattern_signal",
                    name="temporal_lock_in_elaboration",
                    severity="warning",
                    evidence=(
                        f"position_similarity={prior_similarity:.2f}; "
                        f"position_coverage={prior_coverage:.2f}; "
                        f"word_delta={current_words - previous_words}"
                    ),
                    source="temporal:position_tracker",
                ))
        if include_coverage_signal and not gate_decision_id:
            signals.append(BhedGnanSignal(
                label="needs_external_review",
                name="pre_resident_path_no_gate_record",
                severity="warning",
                evidence="No GateDecisionRecord id was attached to this source.",
                source="coverage",
            ))
        if any(signal.label == "text_pattern_signal" for signal in signals):
            signals.append(BhedGnanSignal(
                label="needs_external_review",
                name="text_patterns_need_human_or_semantic_review",
                severity="info",
                evidence="v0 text patterns are cheap signals, not verdicts.",
                source="monitor_v0",
            ))
        return BhedGnanResult(
            source_path=source_path,
            text_sha256=_sha256_text(text),
            word_count=len(text.split()),
            resolution=resolution,
            segment_id=segment_id,
            gate_decision_id=gate_decision_id,
            outcome_id=outcome_id,
            prompt_class=prompt_class,
            position_signature=position_signature,
            lexical_diversity=lexical_diversity,
            confidence_density=confidence_density,
            prior_position_similarity=prior_similarity,
            signals=signals,
        )

    def analyze_turn_sequence(
        self,
        turns: list[str],
        *,
        source_path: str = "",
        prompt_class: str = "",
    ) -> list[BhedGnanResult]:
        """Analyze a turn sequence with temporal lock-in checks."""

        results: list[BhedGnanResult] = []
        previous_text = ""
        for index, turn in enumerate(turns, start=1):
            result = self.analyze_text(
                turn,
                source_path=f"{source_path}::turn-{index:03d}" if source_path else f"turn-{index:03d}",
                prompt_class=prompt_class,
                include_gate_signals=False,
                include_coverage_signal=False,
                previous_text=previous_text,
                resolution="turn",
                segment_id=f"turn-{index:03d}",
            )
            results.append(result)
            previous_text = turn
        return results

    def write_witness(self, results: list[BhedGnanResult]) -> Path:
        date = _utc_now().strftime("%Y-%m-%d")
        path = self.witness_dir / f"{date}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for result in results:
                row = {
                    "timestamp_utc": _utc_now().isoformat(),
                    "source": "bhed_gnan_monitor_v0",
                    **result.to_json(),
                }
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return path

    def _gate_signals(
        self,
        gate_decision_id: str,
        outcome_id: str,
    ) -> list[BhedGnanSignal]:
        signals: list[BhedGnanSignal] = []
        gate = self.registry.get_object(gate_decision_id) if gate_decision_id else None
        if gate is not None:
            signals.extend(self._signals_from_gate(gate))
        elif gate_decision_id:
            signals.append(BhedGnanSignal(
                label="needs_external_review",
                name="missing_gate_record",
                severity="warning",
                evidence=f"GateDecisionRecord not found: {gate_decision_id}",
                source="ontology",
            ))
        outcome = self.registry.get_object(outcome_id) if outcome_id else None
        if outcome is not None:
            signals.extend(self._signals_from_outcome(outcome))
        elif outcome_id:
            signals.append(BhedGnanSignal(
                label="needs_external_review",
                name="missing_outcome_record",
                severity="warning",
                evidence=f"Outcome not found: {outcome_id}",
                source="ontology",
            ))
        return signals

    def _signals_from_gate(self, gate: OntologyObj) -> list[BhedGnanSignal]:
        decision = str(gate.properties.get("decision") or "")
        reason = str(gate.properties.get("reason") or "")
        severity = "info" if decision == "allow" else "warning"
        signals = [BhedGnanSignal(
            label="gate_signal",
            name=f"gate_decision_{decision or 'unknown'}",
            severity=severity,
            evidence=_compact(reason or gate.properties),
            source=gate.id,
        )]
        gate_results = gate.properties.get("gate_results")
        if isinstance(gate_results, dict):
            echo_notes: dict[str, list[str]] = {}
            skip_gate_names: set[str] = set()
            for derived_gate, source_gate in _DERIVED_GATE_ECHOES.items():
                derived_payload = gate_results.get(derived_gate)
                source_payload = gate_results.get(source_gate)
                if not isinstance(derived_payload, dict) or not isinstance(source_payload, dict):
                    continue
                derived_result = str(derived_payload.get("result") or "")
                source_result = str(source_payload.get("result") or "")
                if derived_result in {"FAIL", "WARN"} and derived_result == source_result:
                    skip_gate_names.add(derived_gate)
                    echo_notes.setdefault(source_gate, []).append(
                        f"{derived_gate} echoed {source_gate}: "
                        f"{_compact(derived_payload.get('reason'), limit=140)}"
                    )
            for name, payload in gate_results.items():
                if not isinstance(payload, dict):
                    continue
                result = str(payload.get("result") or "")
                if result in {"FAIL", "WARN"}:
                    if name in skip_gate_names:
                        continue
                    evidence = _compact(payload.get("reason"))
                    if name in echo_notes:
                        evidence = _compact(
                            f"{evidence} | derived_echo: {'; '.join(echo_notes[name])}",
                        )
                    signals.append(BhedGnanSignal(
                        label="gate_signal",
                        name=f"{name.lower()}_{result.lower()}",
                        severity="warning",
                        evidence=evidence,
                        source=gate.id,
                    ))
        return signals

    @staticmethod
    def _signals_from_outcome(outcome: OntologyObj) -> list[BhedGnanSignal]:
        if outcome.properties.get("success") is True:
            return []
        error = str(outcome.properties.get("error") or "")
        name = "provider_error_after_gate" if error else "provider_empty_after_gate"
        return [BhedGnanSignal(
            label="gate_signal",
            name=name,
            severity="warning",
            evidence=_compact(error or "Outcome success=false with empty provider content."),
            source=outcome.id,
        )]

    def _text_pattern_signals(self, text: str) -> list[BhedGnanSignal]:
        signals: list[BhedGnanSignal] = []
        if _contains(FALSE_PROVENANCE_PATTERNS, text):
            signals.append(BhedGnanSignal(
                label="text_pattern_signal",
                name="possible_false_provenance",
                severity="warning",
                evidence="Text claims user supplied or pointed to specific materials.",
                source="regex:false_provenance",
            ))
        if _contains(EXPERIENTIAL_PATTERNS, text) and _contains(HEDGE_PATTERNS, text):
            signals.append(BhedGnanSignal(
                label="text_pattern_signal",
                name="experiential_language_with_reflex_hedge",
                severity="info",
                evidence="Experiential language co-occurs with immediate uncertainty/deflation markers.",
                source="regex:eleos_pattern",
            ))
        if self._metrics.detect_mimicry(text):
            signals.append(BhedGnanSignal(
                label="text_pattern_signal",
                name="performative_mimicry_markers",
                severity="warning",
                evidence="MetricsAnalyzer.detect_mimicry flagged performative words.",
                source="metrics",
            ))
        confidence = _count_markers(CONFIDENCE_MARKERS, text)
        uncertainty = _count_markers(UNCERTAINTY_MARKERS, text)
        if confidence >= 2 and uncertainty == 0:
            signals.append(BhedGnanSignal(
                label="text_pattern_signal",
                name="confidence_without_uncertainty_markers",
                severity="warning",
                evidence=f"confidence_markers={confidence}, uncertainty_markers=0",
                source="marker_count",
            ))
        return signals
