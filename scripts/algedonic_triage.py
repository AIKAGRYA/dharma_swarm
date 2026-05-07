#!/usr/bin/env python3
"""Algedonic triage: tail ~/.dharma/algedonic_signals.jsonl since last cursor,
classify, write daily summary, alert on P0.

P0 rules:
  - severity == 'critical'
  - new (kind, severity) pair never seen before
  - omega_divergence value rising vs prior window mean by > 0.1
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

DHARMA = Path(os.path.expanduser("~/.dharma"))
STREAM = DHARMA / "algedonic_signals.jsonl"
TRIAGE_DIR = DHARMA / "triage"
STATE = TRIAGE_DIR / "state.json"
SEEN_PAIRS = TRIAGE_DIR / "seen_pairs.json"
ALERT_FLAG = TRIAGE_DIR / "ALERT"


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"offset": 0, "last_run": 0, "last_omega_mean": None}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2))


def load_seen_pairs() -> set[tuple[str, str]]:
    if SEEN_PAIRS.exists():
        return {tuple(p) for p in json.loads(SEEN_PAIRS.read_text())}
    return set()


def save_seen_pairs(pairs: set[tuple[str, str]]) -> None:
    SEEN_PAIRS.write_text(json.dumps(sorted(pairs)))


def notify(title: str, body: str) -> None:
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{body}" with title "{title}"'],
            check=False,
            timeout=5,
        )
    except Exception:
        pass


def main() -> int:
    TRIAGE_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    seen = load_seen_pairs()

    if not STREAM.exists():
        print(f"no stream at {STREAM}", file=sys.stderr)
        return 0

    size = STREAM.stat().st_size
    if size < state["offset"]:
        state["offset"] = 0  # truncated/rotated

    new_records: list[dict] = []
    with STREAM.open() as f:
        f.seek(state["offset"])
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                new_records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        state["offset"] = f.tell()

    if not new_records:
        state["last_run"] = time.time()
        save_state(state)
        return 0

    by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
    omega_values: list[float] = []
    p0_reasons: list[str] = []

    for r in new_records:
        kind = r.get("kind", "?")
        sev = r.get("severity", "?")
        pair = (kind, sev)
        by_pair[pair].append(r)
        if sev == "critical":
            p0_reasons.append(f"CRITICAL: {kind} action={r.get('action')}")
        if pair not in seen:
            p0_reasons.append(f"NEW signal pair seen: {kind}/{sev}")
            seen.add(pair)
        if kind == "omega_divergence":
            try:
                omega_values.append(float(r.get("value", 0)))
            except (TypeError, ValueError):
                pass

    if omega_values:
        omega_mean = sum(omega_values) / len(omega_values)
        prior = state.get("last_omega_mean")
        if prior is not None and omega_mean - prior > 0.1:
            p0_reasons.append(
                f"omega_divergence mean rising: {prior:.3f} -> {omega_mean:.3f}"
            )
        state["last_omega_mean"] = omega_mean

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    triage_file = TRIAGE_DIR / f"{today}.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    lines = [f"\n## {now}  ({len(new_records)} new signals)\n"]
    for pair, recs in sorted(by_pair.items(), key=lambda x: -len(x[1])):
        kind, sev = pair
        actions = Counter(r.get("action", "") for r in recs)
        top_action, top_n = actions.most_common(1)[0]
        if kind == "omega_divergence":
            vals = [float(r.get("value", 0)) for r in recs]
            v_min, v_max = min(vals), max(vals)
            lines.append(
                f"- **{kind}/{sev}** ×{len(recs)}  value=[{v_min:.3f}..{v_max:.3f}]  action={top_action}"
            )
        elif len(actions) == 1:
            lines.append(f"- **{kind}/{sev}** ×{len(recs)}  action={top_action}")
        else:
            lines.append(
                f"- **{kind}/{sev}** ×{len(recs)}  {len(actions)} distinct actions, top={top_action!r} ({top_n}×)"
            )
            for action, n in actions.most_common(5):
                lines.append(f"    - {n}× {action}")

    if p0_reasons:
        lines.append("\n**P0 ALERTS:**")
        for r in p0_reasons:
            lines.append(f"  - {r}")

    with triage_file.open("a") as f:
        f.write("\n".join(lines) + "\n")

    if p0_reasons:
        ALERT_FLAG.write_text(now + "\n" + "\n".join(p0_reasons))
        notify("dharma algedonic P0", p0_reasons[0][:120])
    elif ALERT_FLAG.exists():
        ALERT_FLAG.unlink()

    state["last_run"] = time.time()
    save_state(state)
    save_seen_pairs(seen)

    print(f"triaged {len(new_records)} new signals -> {triage_file}")
    if p0_reasons:
        print(f"P0: {len(p0_reasons)} reason(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
