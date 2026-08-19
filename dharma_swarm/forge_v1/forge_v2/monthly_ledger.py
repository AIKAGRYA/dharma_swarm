"""Cumulative monthly spend meter for the Forge benchmark compute cap.

``budget.py`` enforces PER-RUN caps (tokens + $ per ``Budget`` instance);
nothing aggregated spend ACROSS runs against the $200/month benchmark compute
cap (yes-sheet 2026-08-18 row 1; that cap sits inside the $500/month total
burn ceiling). This module is that aggregate: an append-only monthly ledger
JSONL under ``~/.dharma/forge_v1/spend/`` (runtime state — never in git) plus
a refuse-to-start admission check the runners call before spending anything.

Design rules honored:
  * One ledger file per month key (``2026-08.jsonl``); the filename template
    ``YYYY-MM.jsonl`` is a literal so the store-inventory census counts it.
  * No hidden clock in the pure helpers: month keys derive from an explicit
    POSIX timestamp argument; callers pass ``time.time()`` themselves.
  * Fail closed: a malformed ledger row raises instead of silently lowering
    measured spend, and an UNCAPPED run is never admitted against the cap.
  * Charged dollars = real ``usd`` + ``shadow_usd`` (``SHADOW_USD_PER_MTOK``
    pricing in ``budget.py``), so free routes stay non-infinite at month scale.
  * Only runs that actually charge a ``Budget`` append rows; a run blocked
    before any model call has nothing to meter.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.daemon_config import dharma_state_dir

# The benchmark compute cap ratified 2026-08-18 (yes-sheet row 1).
DEFAULT_MONTHLY_CAP_USD = 200.0

# One ledger file per month; the placeholder is replaced by a validated month
# key (e.g. 2026-08.jsonl). Kept as a literal for the store-inventory census.
SPEND_LEDGER_NAME_TEMPLATE = "YYYY-MM.jsonl"

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def month_key(timestamp: float) -> str:
    """UTC ``YYYY-MM`` key for an explicit POSIX timestamp (no hidden clock)."""
    return time.strftime("%Y-%m", time.gmtime(timestamp))


def spend_dir(root: Path | None = None) -> Path:
    """Ledger directory; ``root`` overrides for tests. Runtime state only."""
    if root is not None:
        return Path(root)
    return dharma_state_dir() / "forge_v1" / "spend"


def ledger_path(month: str, *, root: Path | None = None) -> Path:
    """Path of the month's ledger file. Rejects malformed month keys so a bad
    key can never scatter spend across unaccounted files."""
    if not _MONTH_RE.match(month):
        raise ValueError(f"month key must be YYYY-MM, got {month!r}")
    return spend_dir(root) / SPEND_LEDGER_NAME_TEMPLATE.replace("YYYY-MM", month)


def record_run_spend(
    *,
    usd: float,
    shadow_usd: float,
    month: str,
    timestamp: float,
    label: str = "",
    run_dir: str = "",
    root: Path | None = None,
) -> dict:
    """Append one run's total charged spend (real + shadow $) to the month's
    ledger and return the appended row."""
    row = {
        "kind": "forge_run_spend",
        "ts": int(timestamp),
        "month": month,
        "label": label,
        "run_dir": run_dir,
        "usd": round(float(usd), 6),
        "shadow_usd": round(float(shadow_usd), 6),
        "total_usd": round(float(usd) + float(shadow_usd), 6),
    }
    path = ledger_path(month, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def month_spend_usd(month: str, *, root: Path | None = None) -> float:
    """Total charged spend (real + shadow $) recorded for ``month``.

    Fail closed: a row that cannot be parsed raises instead of being skipped —
    skipping would silently understate spend and admit runs past the cap.
    """
    path = ledger_path(month, root=root)
    if not path.exists():
        return 0.0
    total = 0.0
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed spend ledger row {path}:{lineno}: {exc}") from exc
        if "total_usd" in row:
            total += float(row["total_usd"])
        elif "usd" in row or "shadow_usd" in row:
            total += float(row.get("usd", 0.0)) + float(row.get("shadow_usd", 0.0))
        else:
            raise ValueError(f"spend ledger row without usd fields at {path}:{lineno}")
    return total


def remaining_monthly_usd(cap_usd: float, month: str, *, root: Path | None = None) -> float:
    """Dollars left under ``cap_usd`` for ``month`` (never negative)."""
    return max(0.0, float(cap_usd) - month_spend_usd(month, root=root))


def worst_case_run_usd(
    per_attempt_cap_usd: float, *, n_instances: int, replicates: int, arms: int = 2
) -> float:
    """Worst-case charged $ for one runner invocation: every (instance,
    replicate, arm) attempt gets its own ``Budget(cap_usd=per_attempt_cap_usd)``
    (runner.py builds ``b_sm`` and ``b_arm`` per replicate), so the run-level
    exposure is the product. Admission is judged on this, spend on actuals."""
    if per_attempt_cap_usd < 0:
        raise ValueError("per_attempt_cap_usd must be >= 0")
    if n_instances < 0 or replicates < 0 or arms < 0:
        raise ValueError("counts must be >= 0")
    return float(per_attempt_cap_usd) * n_instances * replicates * arms


@dataclass(frozen=True)
class MonthlyGate:
    """Admission verdict for one run against the monthly cap."""

    allowed: bool
    reason: str
    month: str
    monthly_cap_usd: float
    spent_usd: float
    remaining_usd: float
    run_cap_usd: float | None


def check_run_admission(
    run_cap_usd: float | None,
    *,
    monthly_cap_usd: float,
    month: str,
    root: Path | None = None,
) -> MonthlyGate:
    """Refuse-to-start check: a run is admitted only when its worst-case $
    exposure fits inside the month's remaining budget. Uncapped runs (``None``)
    are always refused — an unbounded run cannot be metered against a cap."""
    spent = month_spend_usd(month, root=root)
    remaining = max(0.0, float(monthly_cap_usd) - spent)
    if monthly_cap_usd <= 0:
        return MonthlyGate(
            False,
            f"monthly cap {monthly_cap_usd} is not positive; nothing can be admitted",
            month, float(monthly_cap_usd), spent, remaining, run_cap_usd,
        )
    if run_cap_usd is None:
        return MonthlyGate(
            False,
            "run has no per-run $ cap (budget_usd=None); an uncapped run cannot "
            "be admitted against the monthly cap",
            month, float(monthly_cap_usd), spent, remaining, None,
        )
    if run_cap_usd < 0:
        return MonthlyGate(
            False, f"run cap {run_cap_usd} is negative",
            month, float(monthly_cap_usd), spent, remaining, float(run_cap_usd),
        )
    if run_cap_usd > remaining + 1e-9:
        return MonthlyGate(
            False,
            f"worst-case run spend ${run_cap_usd:.2f} exceeds the remaining "
            f"${remaining:.2f} of the ${monthly_cap_usd:.2f}/month cap for {month} "
            f"(already spent ${spent:.2f}); lower --budget-usd / instances / "
            "replicates, or wait for the next month",
            month, float(monthly_cap_usd), spent, remaining, float(run_cap_usd),
        )
    return MonthlyGate(
        True,
        f"worst-case run spend ${run_cap_usd:.2f} fits in remaining "
        f"${remaining:.2f} of ${monthly_cap_usd:.2f}/month for {month}",
        month, float(monthly_cap_usd), spent, remaining, float(run_cap_usd),
    )
