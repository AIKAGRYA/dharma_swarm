"""autoresearch_history - mutation-history retrieval for the Karpathy
optimize-test-revert loop (Component 1.5).

OMEGA Layer + Causal Closure plan, Component 1.5
(~/.claude/plans/a-structural-dazzling-garden.md).

CLOSES THE WIKI'S FLAGGED GAP
-----------------------------
From ~/.dharma/knowledge/wiki/concepts/strange-loop-memory.md gap analysis:

  "No retrieval of mutation history. The system records every mutation
  but never asks 'what mutations worked before?' The diagnostic step
  could consult mutation history to avoid repeating failed mutations
  or to accelerate toward previously successful configurations."

This module provides ``consult_mutation_history(diagnosis)`` which
returns ``{tried_before, succeeded, failed}`` annotation that the
proposer (autoresearch_loop or strange_loop) can use to:

1. Avoid re-trying known-failed mutations on similar diagnoses
2. Accelerate toward known-successful configurations
3. Surface the walk-back chain via causal_ledger corrects field

DESIGN: STANDALONE HELPER (no wiring at this commit)
----------------------------------------------------
Per the OMEGA build plan, this module is shipped as a STANDALONE
callable. Wiring into autoresearch_loop._diagnose() and
strange_loop._observe_diagnose_propose() happens during the merge
phase when the user is awake. This minimizes merge-conflict surface
on the existing files.

DATA SOURCES
------------
Reads from three substrates (any may be missing — degrades gracefully):

1. ~/.dharma/organism_memory/mutations.jsonl
   strange_loop's Mutation records (id, parameter, old_value, new_value,
   reason, kept, gnani_verdict, pre/post metrics)

2. ~/.dharma/evolution/archive.jsonl
   DarwinEngine ArchiveEntry records (proposal description + fitness
   dimensions + outcome)

3. ~/.dharma/stigmergy/register_marks.jsonl
   Causal-plane marks for subject_kind="mutation" - the predict-resolve
   pairs from causal_ledger (Component 1.1). Walk-back chains via
   ``corrects`` field surface mutations that were kept-then-reverted.

SIMILARITY HEURISTIC
--------------------
Diagnosis-string matching uses Jaccard token overlap on lowered
alphanumeric tokens. Cheap, deterministic, no embedding cost.
A more sophisticated semantic match could plug in later (chetana
unified-graph or chroma) but the v1 ships with no external deps.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MUTATIONS_PATH = Path.home() / ".dharma" / "organism_memory" / "mutations.jsonl"
DEFAULT_EVOLUTION_ARCHIVE = Path.home() / ".dharma" / "evolution" / "archive.jsonl"
DEFAULT_REGISTER_MARKS = Path.home() / ".dharma" / "stigmergy" / "register_marks.jsonl"

# Jaccard threshold for "similar diagnosis."
SIMILARITY_THRESHOLD = 0.30

# Cap on file lines read (tail) — protects against runaway file growth.
MAX_LINES_PER_SOURCE = 50_000

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_]+")
_STOPWORDS = frozenset({
    "the", "a", "an", "of", "to", "in", "is", "and", "or", "but",
    "with", "for", "on", "at", "by", "from", "as", "be", "this",
    "that", "it", "if", "not", "no", "so", "do", "does", "did",
    "was", "were", "are", "has", "have", "had", "will", "would",
    "should", "could", "may", "might", "must", "can", "than", "then",
    "when", "where", "what", "which", "who", "how", "why",
})


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class HistoryEntry:
    """A single past mutation surfaced as relevant to current diagnosis."""

    source: str  # "strange_loop" | "evolution_archive" | "causal_ledger"
    source_id: str  # mutation_id, proposal_id, or mark_id
    summary: str  # one-line human description
    similarity: float  # 0..1 jaccard overlap with current diagnosis
    outcome: str  # "kept" | "reverted" | "blocked" | "unknown" | "drift_detected"
    raw: dict = field(default_factory=dict)  # full source record for inspection


@dataclass
class MutationHistoryResult:
    """Structured annotation for the proposer.

    Surfaces succeeded/failed/tried_before lists so the proposer can
    avoid repetition and accelerate toward known winners. Include
    similarity scores so the proposer can weight relevance.

    Empty result fields are NOT errors — they mean "no relevant
    history found." The proposer should treat empty as "novel
    diagnosis" and proceed normally.
    """

    diagnosis: str
    tried_before: list[HistoryEntry] = field(default_factory=list)
    succeeded: list[HistoryEntry] = field(default_factory=list)
    failed: list[HistoryEntry] = field(default_factory=list)
    n_total_records_considered: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "diagnosis": self.diagnosis,
            "tried_before": [_entry_dict(e) for e in self.tried_before],
            "succeeded": [_entry_dict(e) for e in self.succeeded],
            "failed": [_entry_dict(e) for e in self.failed],
            "n_total_records_considered": self.n_total_records_considered,
            "notes": list(self.notes),
        }


def _entry_dict(e: HistoryEntry) -> dict:
    return {
        "source": e.source,
        "source_id": e.source_id,
        "summary": e.summary,
        "similarity": round(e.similarity, 3),
        "outcome": e.outcome,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def consult_mutation_history(
    diagnosis: str,
    *,
    max_results: int = 5,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
    mutations_path: Path | None = None,
    evolution_archive_path: Path | None = None,
    register_marks_path: Path | None = None,
) -> MutationHistoryResult:
    """Look up past mutations relevant to the given diagnosis.

    Parameters
    ----------
    diagnosis:
        Free-text description of the current problem the proposer is
        trying to solve. Examples: "high failure rate, routing_bias too
        low", "evolution stagnation", "memory consolidation lag".
    max_results:
        Per category cap. Returns up to `max_results` in each of
        tried_before / succeeded / failed.
    similarity_threshold:
        Minimum Jaccard overlap to include an entry. Below this, the
        entry is filtered out.
    mutations_path / evolution_archive_path / register_marks_path:
        Override defaults for testing.

    Returns
    -------
    MutationHistoryResult
        Empty (but not None) when no relevant history found. Never raises.
    """
    diagnosis_tokens = _tokenize(diagnosis)
    if not diagnosis_tokens:
        return MutationHistoryResult(
            diagnosis=diagnosis,
            notes=["empty diagnosis tokens; nothing to match"],
        )

    mutations_path = mutations_path or DEFAULT_MUTATIONS_PATH
    evolution_archive_path = evolution_archive_path or DEFAULT_EVOLUTION_ARCHIVE
    register_marks_path = register_marks_path or DEFAULT_REGISTER_MARKS

    all_entries: list[HistoryEntry] = []
    n_records = 0

    # 1. strange_loop mutations
    sl_entries, sl_n = _scan_strange_loop_mutations(
        mutations_path, diagnosis_tokens, similarity_threshold,
    )
    all_entries.extend(sl_entries)
    n_records += sl_n

    # 2. evolution archive
    ev_entries, ev_n = _scan_evolution_archive(
        evolution_archive_path, diagnosis_tokens, similarity_threshold,
    )
    all_entries.extend(ev_entries)
    n_records += ev_n

    # 3. causal ledger (mutation-kind predictions + walk-backs)
    cl_entries, cl_n = _scan_causal_ledger(
        register_marks_path, diagnosis_tokens, similarity_threshold,
    )
    all_entries.extend(cl_entries)
    n_records += cl_n

    # Sort by similarity descending; bucket by outcome.
    all_entries.sort(key=lambda e: e.similarity, reverse=True)

    succeeded = [e for e in all_entries if e.outcome == "kept"][:max_results]
    failed = [
        e for e in all_entries
        if e.outcome in {"reverted", "blocked", "drift_detected"}
    ][:max_results]
    # tried_before is the deduplicated all-ids list (any outcome). Useful
    # when proposer just wants to know "have I tried this before?" without
    # caring about success.
    seen: set[str] = set()
    tried_before: list[HistoryEntry] = []
    for e in all_entries:
        key = f"{e.source}:{e.source_id}"
        if key in seen:
            continue
        seen.add(key)
        tried_before.append(e)
        if len(tried_before) >= max_results:
            break

    notes: list[str] = []
    if n_records == 0:
        notes.append("no history substrates found (cold start expected)")
    elif not all_entries:
        notes.append(
            f"history exists ({n_records} records) but none matched "
            f"current diagnosis at threshold {similarity_threshold:.2f}"
        )

    return MutationHistoryResult(
        diagnosis=diagnosis,
        tried_before=tried_before,
        succeeded=succeeded,
        failed=failed,
        n_total_records_considered=n_records,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Source scanners
# ---------------------------------------------------------------------------


def _scan_strange_loop_mutations(
    path: Path,
    diagnosis_tokens: set[str],
    threshold: float,
) -> tuple[list[HistoryEntry], int]:
    """Scan mutations.jsonl for similar past mutations."""
    if not path.exists():
        return ([], 0)

    entries: list[HistoryEntry] = []
    n = 0
    for record in _read_jsonl_tail(path, MAX_LINES_PER_SOURCE):
        n += 1
        # Build a comparison string from reason + parameter
        reason = str(record.get("reason", ""))
        parameter = str(record.get("parameter", ""))
        compare = f"{reason} {parameter}".strip()
        if not compare:
            continue
        sim = _jaccard(diagnosis_tokens, _tokenize(compare))
        if sim < threshold:
            continue

        outcome = _classify_strange_loop_outcome(record)
        old_v = record.get("old_value")
        new_v = record.get("new_value")
        summary = (
            f"{parameter}: {old_v} -> {new_v} ({reason[:60]})"
            if parameter else f"mutation: {reason[:80]}"
        )
        entries.append(HistoryEntry(
            source="strange_loop",
            source_id=str(record.get("id", "")),
            summary=summary,
            similarity=sim,
            outcome=outcome,
            raw=record,
        ))
    return (entries, n)


def _scan_evolution_archive(
    path: Path,
    diagnosis_tokens: set[str],
    threshold: float,
) -> tuple[list[HistoryEntry], int]:
    """Scan evolution archive for similar past proposals."""
    if not path.exists():
        return ([], 0)

    entries: list[HistoryEntry] = []
    n = 0
    for record in _read_jsonl_tail(path, MAX_LINES_PER_SOURCE):
        n += 1
        # ArchiveEntry typically has: proposal description, fitness
        # dimensions, gate decision. We use description as primary
        # comparison text.
        description = str(
            record.get("description", "")
            or record.get("proposal_description", "")
            or record.get("change_description", "")
        )
        component = str(record.get("component", ""))
        compare = f"{description} {component}".strip()
        if not compare:
            continue
        sim = _jaccard(diagnosis_tokens, _tokenize(compare))
        if sim < threshold:
            continue

        outcome = _classify_evolution_outcome(record)
        summary = (
            f"{component}: {description[:80]}" if component
            else description[:100]
        )
        entries.append(HistoryEntry(
            source="evolution_archive",
            source_id=str(record.get("id", record.get("proposal_id", ""))),
            summary=summary,
            similarity=sim,
            outcome=outcome,
            raw=record,
        ))
    return (entries, n)


def _scan_causal_ledger(
    path: Path,
    diagnosis_tokens: set[str],
    threshold: float,
) -> tuple[list[HistoryEntry], int]:
    """Scan register_marks.jsonl for causal-plane mutation marks +
    walk-backs.

    Special role: register marks with corrects-field set indicate
    walk-back chains. A mutation that has a corrects-mark pointing
    at it was retroactively flagged as drift. That signal goes
    into the failed bucket as "drift_detected."
    """
    if not path.exists():
        return ([], 0)

    # Pass 1: collect causal predictions for mutations + their resolutions.
    predictions: dict[str, dict] = {}
    resolutions: dict[str, dict] = {}  # corrects -> resolution
    drift_corrects: set[str] = set()  # mark_ids that were corrected as drift

    n = 0
    for record in _read_jsonl_tail(path, MAX_LINES_PER_SOURCE):
        n += 1
        if record.get("plane") != "causal":
            # Also count drift_detected disciplines from any plane
            if record.get("discipline") == "post_deployment_drift":
                corrects = record.get("corrects")
                if corrects:
                    drift_corrects.add(corrects)
            continue
        links = record.get("links") or {}
        kind = links.get("kind")

        if kind == "causal_prediction" and links.get("subject_kind") == "mutation":
            mark_id = record.get("mark_id")
            if mark_id:
                predictions[mark_id] = record
        elif kind == "causal_resolution":
            corrects = record.get("corrects")
            if corrects:
                resolutions[corrects] = record

    # Pass 2: build entries for predictions matching diagnosis.
    entries: list[HistoryEntry] = []
    for mark_id, pred in predictions.items():
        explanation = str(pred.get("explanation", ""))
        sim = _jaccard(diagnosis_tokens, _tokenize(explanation))
        if sim < threshold:
            continue

        # Outcome inference:
        # - has resolution AND _is_repaired (sign+magnitude OK) -> kept
        # - has resolution but not repaired -> reverted
        # - drift_detected discipline mark_id matches -> drift_detected
        # - no resolution yet -> unknown
        if mark_id in drift_corrects:
            outcome = "drift_detected"
        elif mark_id in resolutions:
            res = resolutions[mark_id]
            outcome = (
                "kept" if _resolution_repaired(pred, res) else "reverted"
            )
        else:
            outcome = "unknown"

        entries.append(HistoryEntry(
            source="causal_ledger",
            source_id=mark_id,
            summary=explanation[:100] or f"causal prediction {mark_id}",
            similarity=sim,
            outcome=outcome,
            raw=pred,
        ))

    return (entries, n)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> set[str]:
    """Lowered alphanumeric tokens, stopwords removed."""
    if not text:
        return set()
    tokens = {t.lower() for t in _TOKEN_RE.findall(text)}
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


def _read_jsonl_tail(path: Path, max_lines: int) -> list[dict]:
    """Read the last `max_lines` lines as parsed JSON. Skip bad lines.
    Returns [] on any IO error."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    out: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
        except (json.JSONDecodeError, ValueError):
            continue
    return out


def _classify_strange_loop_outcome(record: dict) -> str:
    """Map Mutation record fields to outcome string."""
    kept = record.get("kept")
    if kept is True:
        return "kept"
    if kept is False:
        return "reverted"
    gnani = record.get("gnani_verdict")
    if gnani is False:
        return "blocked"
    return "unknown"


def _classify_evolution_outcome(record: dict) -> str:
    """Map ArchiveEntry-ish record to outcome string."""
    accepted = record.get("accepted")
    if accepted is True:
        return "kept"
    if accepted is False:
        return "reverted"
    gate = record.get("gate_decision") or record.get("gate")
    if isinstance(gate, str) and gate.upper() in {"BLOCK", "BLOCKED", "REFUSE"}:
        return "blocked"
    return "unknown"


def _resolution_repaired(pred: dict, res: dict) -> bool:
    """Mirror of causal_ledger._is_repaired: actual within 50% of expected
    AND sign-aligned."""
    pred_links = pred.get("links") or {}
    res_links = res.get("links") or {}
    expected = pred_links.get("expected") or {}
    actual = res_links.get("actual") or {}
    if not expected or not actual:
        return False
    for k, exp_v in expected.items():
        if k not in actual:
            return False
        try:
            exp_f = float(exp_v)
            act_f = float(actual[k])
        except (TypeError, ValueError):
            return False
        denom = max(abs(exp_f), 1.0)
        if abs(act_f - exp_f) / denom > 0.5:
            return False
        if abs(exp_f) >= 1e-9 and exp_f * act_f < 0:
            return False
    return True


__all__ = [
    "HistoryEntry",
    "MutationHistoryResult",
    "consult_mutation_history",
    "SIMILARITY_THRESHOLD",
]
