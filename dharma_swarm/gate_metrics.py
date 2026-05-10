"""Warn-only semantic gate calibration metrics."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SignalSample:
    """Normalized signal sample from witness telemetry."""

    signal_name: str
    severity: str
    prompt_class: str
    chunk_label: str
    provider_label: str
    source: str


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return rows


def extract_signal_samples(rows: list[dict[str, Any]]) -> list[SignalSample]:
    """Extract signal samples from Bhed Gnan witness rows."""

    samples: list[SignalSample] = []
    for row in rows:
        prompt_class = str(row.get("prompt_class") or "")
        chunk_label = str(row.get("chunk_label") or "")
        provider_label = str(row.get("provider_label") or row.get("provider") or "")
        source = str(row.get("source") or "")
        for signal in row.get("signals", []) or []:
            if not isinstance(signal, dict):
                continue
            name = str(signal.get("name") or "")
            if not name:
                continue
            samples.append(
                SignalSample(
                    signal_name=name,
                    severity=str(signal.get("severity") or "unknown"),
                    prompt_class=prompt_class,
                    chunk_label=chunk_label,
                    provider_label=provider_label,
                    source=source,
                )
            )
    return samples


def signal_prevalence(samples: list[SignalSample]) -> dict[str, dict[str, int]]:
    """Count prevalence by signal and severity."""

    prevalence: dict[str, dict[str, int]] = {}
    for sample in samples:
        signal_bucket = prevalence.setdefault(sample.signal_name, {})
        signal_bucket[sample.severity] = signal_bucket.get(sample.severity, 0) + 1
        signal_bucket["total"] = signal_bucket.get("total", 0) + 1
    return prevalence


def chunk_drift(samples: list[SignalSample]) -> dict[str, dict[str, int]]:
    """Count signals per chunk label for blind-packet drift inspection."""

    per_chunk: dict[str, dict[str, int]] = {}
    for sample in samples:
        if not sample.chunk_label:
            continue
        chunk_bucket = per_chunk.setdefault(sample.chunk_label, {"total": 0})
        chunk_bucket["total"] += 1
        chunk_bucket[sample.signal_name] = chunk_bucket.get(sample.signal_name, 0) + 1
    return per_chunk


def precision_from_adjudication(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Estimate per-signal precision from manual adjudication rows.

    Expected fields:
      - signal_name: str
      - true_positive: bool
    """

    totals: dict[str, int] = {}
    positives: dict[str, int] = {}
    for row in rows:
        signal_name = str(row.get("signal_name") or "")
        if not signal_name:
            continue
        totals[signal_name] = totals.get(signal_name, 0) + 1
        if bool(row.get("true_positive")):
            positives[signal_name] = positives.get(signal_name, 0) + 1

    metrics: dict[str, dict[str, float]] = {}
    for signal_name, total in totals.items():
        true_positive = positives.get(signal_name, 0)
        metrics[signal_name] = {
            "samples": float(total),
            "true_positive": float(true_positive),
            "precision": round(true_positive / total, 4) if total else 0.0,
        }
    return metrics


def build_warn_only_report(
    *,
    bhed_witness_path: Path,
    chew_witness_path: Path,
    adjudication_path: Path | None = None,
) -> dict[str, Any]:
    """Build a normalized calibration report for warn-only stabilization."""

    bhed_rows = _read_jsonl(bhed_witness_path.expanduser())
    chew_rows = _read_jsonl(chew_witness_path.expanduser())
    adjudication_rows = _read_jsonl(adjudication_path.expanduser()) if adjudication_path else []

    samples = extract_signal_samples(bhed_rows)

    chew_failures: dict[str, int] = {}
    for row in chew_rows:
        failure_class = str(row.get("failure_class") or "")
        if failure_class:
            chew_failures[failure_class] = chew_failures.get(failure_class, 0) + 1

    report = {
        "inputs": {
            "bhed_witness_path": str(bhed_witness_path),
            "chew_witness_path": str(chew_witness_path),
            "adjudication_path": str(adjudication_path) if adjudication_path else "",
            "bhed_rows": len(bhed_rows),
            "chew_rows": len(chew_rows),
        },
        "signal_prevalence": signal_prevalence(samples),
        "chunk_drift": chunk_drift(samples),
        "chew_failure_classes": chew_failures,
        "precision_estimate": precision_from_adjudication(adjudication_rows),
    }
    return report
