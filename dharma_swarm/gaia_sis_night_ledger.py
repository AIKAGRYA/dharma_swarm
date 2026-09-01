"""SIS night ledger — the swarm metering one bounded window of its own sessions.

SEED-1 (``gaia_sis_projection``) built the converter from a dispatch receipt to an
ecological-cost band, but nothing feeds it from the estate's *actual* session
receipts. This module is that missing wire for the session store: it reads the
per-session ``meta.json`` records the terminal bridge already persists under
``~/.dharma/sessions/`` (schema: ``dharma_swarm/operator_core/session_store.py``),
maps them onto the projection's duck-type, and renders one honest ledger for a
bounded time window — the strange loop showing up as accounting for a single
night of work.

Doctrine (binding, inherited from the SIS field):
  * **Projection only.** Pure reads over already-persisted receipts; imports no
    owned surface beyond the sibling projection; mutates nothing.
  * **Never a single number.** Every total carries the lower–upper band.
  * **Mints nothing.** A debit is gross emitted carbon, not a welfare-ton.
  * **Stored zeros are not proof.** A session whose token counters are zero is
    reported as unmetered coverage, never as proof of zero usage; an empty
    window is reported as absence of receipts, never as zero compute.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.gaia_sis_projection import REBUTTABLE_NOTE, SisDebit, aggregate

_META_NAME = "meta.json"


def default_session_root() -> Path:
    """The estate's session store, routed through the state-dir helper."""
    return dharma_state_dir() / "sessions"


@dataclass(frozen=True, slots=True)
class NightWindow:
    """Half-open, timezone-aware observation window [since, until)."""

    since: datetime
    until: datetime

    def contains(self, ts: datetime) -> bool:
        return self.since <= ts < self.until

    @classmethod
    def last_hours(cls, hours: float, *, now: datetime | None = None) -> "NightWindow":
        anchor = now or datetime.now(timezone.utc)
        return cls(since=anchor - timedelta(hours=hours), until=anchor)


@dataclass(frozen=True, slots=True)
class NightGather:
    """Receipts admitted to the window plus honest accounting of what was not."""

    receipts: tuple[dict[str, Any], ...]
    skipped_unreadable: int
    skipped_outside_window: int

    @property
    def unmetered(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            r for r in self.receipts
            if not (r.get("input_tokens") or r.get("output_tokens"))
        )


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _receipt_from_meta(meta: dict[str, Any], session_dir: str) -> dict[str, Any] | None:
    ts = _parse_ts(meta.get("updated_at")) or _parse_ts(meta.get("created_at"))
    if ts is None:
        return None
    return {
        "provider": str(meta.get("provider_id") or ""),
        "model": str(meta.get("model_id") or ""),
        "input_tokens": meta.get("total_input_tokens"),
        "output_tokens": meta.get("total_output_tokens"),
        "trace_id": str(meta.get("session_id") or session_dir),
        "status": str(meta.get("status") or ""),
        "cost_usd": float(meta.get("total_cost_usd") or 0.0),
        "observed_at": ts,
    }


def gather_night(roots: Iterable[Path], window: NightWindow) -> NightGather:
    """Collect in-window session receipts from ``<root>/*/meta.json`` stores."""
    admitted: list[dict[str, Any]] = []
    unreadable = 0
    outside = 0
    for root in roots:
        root = Path(root).expanduser()
        if not root.is_dir():
            continue
        for meta_path in sorted(root.glob(f"*/{_META_NAME}")):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                unreadable += 1
                continue
            if not isinstance(meta, dict):
                unreadable += 1
                continue
            receipt = _receipt_from_meta(meta, meta_path.parent.name)
            if receipt is None:
                unreadable += 1
                continue
            if not window.contains(receipt["observed_at"]):
                outside += 1
                continue
            admitted.append(receipt)
    return NightGather(
        receipts=tuple(admitted),
        skipped_unreadable=unreadable,
        skipped_outside_window=outside,
    )


def night_ledger_markdown(gather: NightGather, window: NightWindow, label: str) -> str:
    """Render the window's SIS debit as a self-contained, band-carrying ledger."""
    lines = [
        f"# SIS night ledger — {label}",
        f"Window: {window.since.isoformat()} → {window.until.isoformat()} (half-open, UTC-normalized)",
        "",
    ]
    if not gather.receipts:
        lines += [
            "No metered session receipts fell inside this window.",
            "Absence of receipts is absence of evidence, not proof of zero compute.",
            f"(unreadable receipt files skipped: {gather.skipped_unreadable}; "
            f"sessions outside window: {gather.skipped_outside_window})",
            "",
            f"Method note: {REBUTTABLE_NOTE}.",
        ]
        return "\n".join(lines)

    debit: SisDebit = aggregate(gather.receipts)
    cost = sum(r["cost_usd"] for r in gather.receipts)
    by_provider: dict[str, int] = {}
    for r in gather.receipts:
        key = r["provider"] or "unknown"
        by_provider[key] = by_provider.get(key, 0) + 1

    lines += [debit.footprint_report(), ""]
    lines.append("Sessions by provider:")
    for provider, n in sorted(by_provider.items(), key=lambda kv: -kv[1]):
        lines.append(f"  - {provider}: {n} session(s)")
    lines += [
        "",
        f"Recorded provider cost across window: USD {cost:.4f} "
        "(as persisted by the session store; recorded, not billed-proof).",
        f"Unmetered sessions (zero stored token counters): {len(gather.unmetered)} of "
        f"{debit.count} — stored zeros are not promoted as proof of zero usage.",
        f"Unreadable receipt files skipped: {gather.skipped_unreadable}; "
        f"sessions outside window: {gather.skipped_outside_window}.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", action="append", dest="roots",
        help="session-store root holding <session>/meta.json (repeatable; "
        "default: the estate session store under the dharma state dir)",
    )
    parser.add_argument("--since-hours", type=float, default=12.0)
    parser.add_argument("--label", default="unnamed window")
    args = parser.parse_args(argv)
    roots = (
        [Path(r) for r in args.roots] if args.roots else [default_session_root()]
    )
    window = NightWindow.last_hours(args.since_hours)
    print(night_ledger_markdown(gather_night(roots, window), window, args.label))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
