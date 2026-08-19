"""Verified Report Card — a Markdown deliverable that is a pure function of a receipt.

Mirrors the audit-kit pattern (``scripts/revenue_wedge/audit_kit.py``): the card
renders ONLY from a sealed :class:`dharma_swarm.foundry.receipts.FoundryReceipt`
dict, so every line traces to sealed evidence. Two rules make it honest:

- The headline verification status is derived from the receipt, never asserted.
  A card renders as EXTERNALLY CONFIRMED only when the receipt cleared ring 3
  (a non-author merge or an independent record); otherwise it says LAB-LOCAL or
  UNVERIFIED and cannot overclaim.
- The published-misses appendix is mandatory. A trust product that hides its
  misses is the thing this Foundry exists to replace.

This renderer serves both Foundry products: code-improvement report cards and
the $2,500 agent-behavior verification receipt ("did this agent do what it
claimed"), which produces the same receipt shape pointed at a customer's agent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CARD_VERSION = "foundry_report_card.v1"


def _status(receipt: dict[str, Any]) -> tuple[str, str]:
    if receipt.get("externally_confirmed"):
        return ("EXTERNALLY CONFIRMED", "ring 3 — independently confirmed by a party we do not control")
    present = set(receipt.get("links_present") or [])
    if {"benchmark"} & present:
        return ("LAB-LOCAL (UNVERIFIED)", "ring 1/2 only — not yet independently confirmed; NOT a claim")
    return ("UNVERIFIED", "no benchmark link present")


def render_report_card(receipt: dict[str, Any], *, misses: list[dict[str, Any]] | None = None) -> str:
    status, status_note = _status(receipt)
    bench = receipt.get("benchmark") or {}
    strat = receipt.get("stratified") or {}
    lines: list[str] = []

    lines.append(f"# Verified Improvement Report Card — `{receipt.get('target_id', '?')}`")
    lines.append("")
    lines.append(f"**Card version:** {CARD_VERSION}  ")
    lines.append(f"**Receipt:** `{receipt.get('receipt_id', '?')}` (schema {receipt.get('schema_version', '?')})  ")
    lines.append(f"**Candidate:** `{receipt.get('candidate_id', '?')}`  ")
    lines.append(f"**Verification status:** {status} — {status_note}")
    lines.append("")

    if bench:
        base = bench.get("baseline_metric")
        cand = bench.get("candidate_metric")
        delta = bench.get("delta")
        lines.append("## Benchmark")
        lines.append("")
        lines.append(f"- Baseline: `{base}`")
        lines.append(f"- Candidate: `{cand}`")
        lines.append(f"- Delta: `{delta}`")
        lines.append(f"- Runs: `{bench.get('runs')}` (coefficient of variation `{bench.get('coefficient_of_variation')}`)")
        lines.append(f"- Isolation: `{bench.get('isolation_level')}`")
        lines.append(f"- Reproduce: `{' '.join(bench.get('repro_cmd', []))}`")
        lines.append("")

    lines.append("## Evidence chain (seven links)")
    lines.append("")
    all_links = ("pre_registration", "benchmark", "disclosure", "external_ci",
                 "merge_event", "guardian_countersign", "report_render")
    present = set(receipt.get("links_present") or [])
    for link in all_links:
        mark = "x" if link in present else " "
        lines.append(f"- [{mark}] {link}")
    lines.append("")

    lines.append("## Stratified fields (One Wire dimensions)")
    lines.append("")
    for key in ("domain", "counterparty", "value_risk", "independence", "transfer"):
        lines.append(f"- **{key}:** {strat.get(key, '')}")
    lines.append("")

    # Mandatory misses appendix — always present.
    lines.append("## Published misses")
    lines.append("")
    misses = misses or []
    if misses:
        for miss in misses:
            lines.append(f"- **{miss.get('what', 'miss')}:** {miss.get('detail', '')}")
    else:
        lines.append("_No misses recorded for this card. (This section is mandatory and is "
                     "never omitted; an empty misses list is itself a claim under review.)_")
    lines.append("")

    lines.append("---")
    lines.append(f"*Sealed digest:* `{receipt.get('sealed_digest', '(unsealed)')}`")
    lines.append("*This card renders only from the sealed receipt; recompute the digest to verify.*")
    return "\n".join(lines)


def card_from_receipt_file(path: Path | str, *, misses: list[dict[str, Any]] | None = None) -> str:
    receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    return render_report_card(receipt, misses=misses)
