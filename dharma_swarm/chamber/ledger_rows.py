"""Frontier Ledger row construction — the capability list and its owners.

Split from scripts/governance/frontier_ledger.py (module line budget). Rows
are keyed to the SAME capability list as the ratchet surfaces in the
inward-ascent baseline receipt (Codex review, PR #830: every baseline
surface renders, none hidden), plus the chamber's own instruments. Field
numbers REQUIRE receipt URLs; internal lift is never presented as
benchmark-commensurable (trust-gate C2 admissibility rule).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = REPO_ROOT / "reports/governance/inward_ascent/baseline_receipt.json"
TRANSCENDENCE_PATH = REPO_ROOT / "reports/governance/chamber/transcendence_receipt.json"
TRUST_GATE_SCRIPT = REPO_ROOT / "scripts/governance/trust_gate_status.py"

# Field comparators: ONLY entries with a receipt URL may carry a number
# (NORTH_STAR §10 is the seed source; refreshing these is the ingest lane's
# job — chamber doctrine F5).
FIELD_COMPARATORS: dict[str, dict[str, Any]] = {
    "coding_benchmark_self_improvement": {
        "value": 50.0,
        "unit": "% SWE-bench-verified (DGM final, self-improved 20->50)",
        "receipt": "https://arxiv.org/abs/2505.22954",
    },
}


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_baseline() -> tuple[dict[str, Any] | None, str | None]:
    """The committed inward-ascent baseline receipt is the 'ours' owner for
    every ratchet surface it measures. Absent -> every surface UNKNOWN."""
    digest = sha256_file(BASELINE_PATH)
    if digest is None:
        return None, None
    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8")), digest
    except (OSError, json.JSONDecodeError):
        return None, digest


def trust_gate_payload() -> dict[str, Any] | None:
    """Run the trust-gate owner script ONCE. Any failure -> None; callers
    render an UNKNOWN door, never a fabricated one."""
    try:
        proc = subprocess.run(
            [sys.executable, str(TRUST_GATE_SCRIPT), "--json-only"],
            capture_output=True, text=True, timeout=180, cwd=REPO_ROOT,
        )
        return json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def trust_gate_snapshot(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Reduce the trust-gate payload to the door panel."""
    if payload is None:
        return {"available": False, "gate_open": None, "conditions": []}
    conditions = [
        {"id": c.get("id"), "score": c.get("score"), "verdict": c.get("verdict")}
        for c in payload.get("conditions", [])
    ]
    return {
        "available": True,
        "gate_open": bool(payload.get("gate_open", False)),
        "owner": str(payload.get("fact_owner", "docs/vision_maps/NORTH_STAR.md §8")),
        "conditions": conditions,
    }


def swarm_lift(payload: dict[str, Any] | None) -> tuple[float | None, str]:
    """C2's evidence names the last real lift measurement and its receipt.
    Parsed, not remembered; unparseable -> UNKNOWN with the gap named."""
    if payload is None:
        return None, "trust-gate owner unavailable on this host"
    for cond in payload.get("conditions", []):
        if cond.get("id") != "C2":
            continue
        for line in cond.get("evidence", []):
            m = re.search(r"latest measured lift = (-?\d+(?:\.\d+)?)\s*\((\S+?)\)", line)
            if m:
                return float(m.group(1)), m.group(2)
    return None, "no measured-lift line in C2 evidence"


def _baseline_surface(baseline: dict[str, Any] | None, sid: str) -> dict[str, Any]:
    for s in (baseline or {}).get("surfaces", []):
        if s.get("id") == sid:
            return {"value": s.get("value"), "unit": s.get("unit"),
                    "measured": bool(s.get("measured")),
                    "receipt": "reports/governance/inward_ascent/baseline_receipt.json"}
    return {"value": None, "unit": None, "measured": False,
            "receipt": "reports/governance/inward_ascent/baseline_receipt.json (surface absent)"}


def _field_for(capability: str) -> dict[str, Any]:
    row = FIELD_COMPARATORS.get(capability)
    if row is None:
        return {"value": None, "unit": None,
                "receipt": "UNKNOWN_PENDING_INGEST — the ingest lane supplies field numbers (F5)"}
    return dict(row)


def transcendence_ours() -> dict[str, Any]:
    """The E1 instrument's headline number, if a decomposition receipt exists."""
    if not TRANSCENDENCE_PATH.exists():
        return {"value": None, "unit": None, "measured": False,
                "receipt": "no gym decomposition receipt yet — run "
                           "transcendence_ledger.py after a gym run"}
    try:
        data = json.loads(TRANSCENDENCE_PATH.read_text(encoding="utf-8"))
        lifts = [b["lift_vs_best_seat"] for b in data.get("decomposition", [])]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return {"value": None, "unit": None, "measured": False,
                "receipt": f"transcendence receipt unreadable: {type(exc).__name__}"}
    if not lifts:
        return {"value": None, "unit": None, "measured": False,
                "receipt": "transcendence receipt has no decomposition blocks"}
    return {"value": max(lifts), "unit": "lift vs best seat (internal gym)",
            "measured": True,
            "receipt": "reports/governance/chamber/transcendence_receipt.json"}


def build_rows(baseline: dict[str, Any] | None,
               trust_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    lift, lift_receipt = swarm_lift(trust_payload)
    rows: list[dict[str, Any]] = []

    def add(capability: str, ours: dict[str, Any], *, commensurable: bool,
            note: str) -> None:
        field = _field_for(capability)
        delta = None
        if commensurable and isinstance(ours.get("value"), (int, float)) \
                and isinstance(field.get("value"), (int, float)):
            delta = round(float(ours["value"]) - float(field["value"]), 6)
        rows.append({"capability": capability, "ours": ours, "field": field,
                     "delta": delta, "commensurable": commensurable, "note": note})

    add("coding_benchmark_self_improvement",
        {"value": None, "unit": "% SWE-bench-verified", "measured": False,
         "receipt": "never run — env 15 is operator-gated compute (decision queue)"},
        commensurable=True,
        note="The literal trust-gate C2 bar. Ours stays UNKNOWN until a real "
             "public-benchmark run under budget-parity controls exists.")
    add("swarm_lift_vs_best_single",
        {"value": lift, "unit": "lift vs own best seat", "measured": lift is not None,
         "receipt": lift_receipt},
        commensurable=False,
        note="Internal measurement owned by the RSI/arena lab; NOT "
             "benchmark-commensurable (trust_gate_status admissibility rule). "
             "Negative = the transcendence conditions currently fail in wiring.")
    add("ingest_metabolism",
        _baseline_surface(baseline, "ingest_volume"),
        commensurable=False,
        note="Bronze receipts landed under corroboration. Field column is N/A "
             "by construction (internal capacity surface).")
    add("ingest_quality",
        _baseline_surface(baseline, "ingest_quality"),
        commensurable=False,
        note="Fraction of bronze receipts reaching corroboration k>=2; "
             "undefined until receipts land.")
    add("forecast_brier",
        _baseline_surface(baseline, "forecast_brier"),
        commensurable=False,
        note="Time-lagged reality grading (gym G2); resolution from ingest "
             "ONLY (oracle rule, discipline 10). Ratchets DOWN.")
    add("memory_hit_rate",
        _baseline_surface(baseline, "memory_hit_rate"),
        commensurable=False,
        note="G3 arm-A held-out accuracy — the first measured C5 instrument.")
    add("gate_catch_rate",
        _baseline_surface(baseline, "gate_catch_rate"),
        commensurable=False,
        note="Deferred with the gate gym until the attack corpus is IMPORTED "
             "(class-2), never self-generated.")
    add("ontology_coverage",
        _baseline_surface(baseline, "ontology_coverage"),
        commensurable=False,
        note="ontology.db lives on the daemon host (BR-007); daemon-host "
             "baseline run is in the decision queue.")
    add("routing_regret",
        _baseline_surface(baseline, "routing_regret"),
        commensurable=False,
        note="G4 off-policy regret vs ~2k real delegation_runs; operator-gated "
             "on a sanitized runtime.db snapshot. Ratchets DOWN.")
    add("self_model_accuracy",
        _baseline_surface(baseline, "self_model_accuracy"),
        commensurable=False,
        note="Does the organism know itself (env 7) — folds into G1 as a "
             "secondary scorer arm.")
    add("git_history_gym_substrate",
        _baseline_surface(baseline, "git_history_gym"),
        commensurable=False,
        note="G1's raw substrate (commits/landed merges at the baseline's "
             "pinned snapshot sha).")
    add("distilled_seat_cost_per_iteration",
        {"value": None, "unit": "USD / scored iteration", "measured": False,
         "receipt": "env 12 (trace distillation) not built — no cost ledger yet"},
        commensurable=False,
        note="The compute-ROI denominator (discipline 9). Every environment "
             "must declare cost-per-scored-iteration before its first "
             "evolution run; this row aggregates them.")
    add("transcendence_decomposition",
        transcendence_ours(),
        commensurable=False,
        note="E1: realized Krogh-Vedelsby lift vs best single seat on the "
             "latest gym trace corpus (internal-gym number under a "
             "train-signal aggregation rule — never a C2 claim).")
    return rows


def capability_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-capability numeric snapshot recorded into the E6 history chain."""
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        ours = r["ours"].get("value")
        out[r["capability"]] = {
            "delta": r["delta"] if isinstance(r["delta"], (int, float)) else None,
            "ours": ours if isinstance(ours, (int, float)) else None,
        }
    return out


__all__ = [
    "BASELINE_PATH", "FIELD_COMPARATORS", "TRANSCENDENCE_PATH",
    "build_rows", "capability_summary", "load_baseline", "sha256_file",
    "swarm_lift", "transcendence_ours", "trust_gate_payload",
    "trust_gate_snapshot",
]
