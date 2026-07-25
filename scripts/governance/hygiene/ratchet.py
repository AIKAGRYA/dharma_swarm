#!/usr/bin/env python3
"""One-way quality ratchet: repo-wide counters that may only improve.

Each counter (defined in ratchet_counters.py — this module owns the
algebra and persistence) measures one number from the working tree and
compares it against a stored baseline in
``docs/governance/hygiene/ratchet_baselines.json`` (git-tracked,
committed alongside the change that moved it). A ``down`` counter may
only fall; an ``up`` counter may only rise. Any move in the wrong
direction is a regression and the run exits 1.

On a fully green run, ``--tighten`` rewrites improved baselines in
place, so every improvement becomes the new bound. A red run never
mutates the baselines file. This is the helm F-011 mechanism ported to
dharma_swarm, scoped under the hygiene lifecycle that owns this
directory (promotion to blocking CI follows LIFECYCLE.md; see QL-R1).

Guarantees:

* Zero false positives by construction: the baseline IS current reality,
  so the gate is silent on day one and fires only on backsliding.
* Measurement failure is never success: an unmeasurable counter exits 2
  (BROKEN), distinct from regression's exit 1. A crashing gate must
  block, not wave through.
* Baseline writes are atomic (temp file + ``os.replace``) and happen
  only on green ``--tighten`` runs or first ``--init``.
* The counter set in code and the keys in the baselines file must match
  exactly, both directions, so adding or removing a counter is forced to
  be a reviewed, same-commit decision.

Non-goals: it fixes nothing, writes no reports, measures no judgment
qualities (the canon for those lives in docs/quality/SATTVA_STYLE.md),
and replaces no part of the hygiene lifecycle.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from ratchet_counters import COUNTERS, BrokenCounter, Direction  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE_PATH = Path("docs/governance/hygiene/ratchet_baselines.json")
BASELINE_SCHEMA_VERSION = "quality_ratchet_baseline.v1"
REPORT_SCHEMA_VERSION = "quality_ratchet_report.v1"

EXIT_GREEN = 0
EXIT_REGRESSION = 1
EXIT_BROKEN = 2


@dataclass(frozen=True, slots=True)
class Comparison:
    """A counter's fresh reading judged against its stored baseline."""

    name: str
    direction: Direction
    baseline: int
    value: int
    end_target: int
    evidence: tuple[str, ...]

    @property
    def regressed(self) -> bool:
        if self.direction is Direction.DOWN:
            return self.value > self.baseline
        return self.value < self.baseline

    @property
    def improved(self) -> bool:
        if self.direction is Direction.DOWN:
            return self.value < self.baseline
        return self.value > self.baseline

    @property
    def verdict(self) -> str:
        if self.regressed:
            return "REGRESSION"
        if self.improved:
            return "IMPROVED"
        return "OK"

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "direction": str(self.direction),
            "baseline": self.baseline,
            "value": self.value,
            "end_target": self.end_target,
            "verdict": self.verdict,
        }


# ---------------------------------------------------------------------------
# Baseline persistence
# ---------------------------------------------------------------------------


def load_baselines(path: Path) -> dict[str, int]:
    """Read and validate the baselines file; raise BrokenCounter on any drift."""
    if not path.exists():
        raise BrokenCounter(
            f"baselines file missing: {path}. Run with --init once to create it "
            "from current reality, then commit it."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BrokenCounter(f"baselines file is not valid JSON: {exc}") from exc
    if payload.get("schema_version") != BASELINE_SCHEMA_VERSION:
        raise BrokenCounter(
            f"baselines schema_version {payload.get('schema_version')!r} != "
            f"{BASELINE_SCHEMA_VERSION!r}"
        )
    counters = payload.get("counters")
    if not isinstance(counters, dict):
        raise BrokenCounter("baselines 'counters' must be an object")
    expected = {counter.name for counter in COUNTERS}
    actual = set(counters)
    if expected != actual:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise BrokenCounter(
            "baseline keys must match the counter set exactly; "
            f"missing={missing} unknown={unknown}. Add or remove baselines in "
            "the same commit that changes the counter set."
        )
    for name, value in counters.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise BrokenCounter(f"baseline {name!r} must be a non-negative integer, got {value!r}")
    return dict(counters)


def parse_baselines_text(text: str, *, source: str) -> dict[str, int]:
    """Validate a baselines JSON blob (from any source) into a counters map.

    Same schema/value rules as ``load_baselines`` but the payload comes from
    a string rather than a working-tree file, and the counter-set is NOT
    required to match the current ``COUNTERS`` — a historical (merge-base)
    baseline may define a different counter set than today's code, and only
    the counters that still exist are consulted by the caller.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BrokenCounter(f"{source} is not valid JSON: {exc}") from exc
    if payload.get("schema_version") != BASELINE_SCHEMA_VERSION:
        raise BrokenCounter(
            f"{source} schema_version {payload.get('schema_version')!r} != "
            f"{BASELINE_SCHEMA_VERSION!r}"
        )
    counters = payload.get("counters")
    if not isinstance(counters, dict):
        raise BrokenCounter(f"{source} 'counters' must be an object")
    for name, value in counters.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise BrokenCounter(
                f"{source} counter {name!r} must be a non-negative integer, got {value!r}"
            )
    return dict(counters)


def resolve_merge_base(repo_root: Path, ref: str) -> str:
    """Return the merge-base SHA of ``ref`` and HEAD, or raise BrokenCounter.

    Fail-closed: if the merge-base cannot be computed (not a git repo, ref
    absent, shallow clone), the caller asked to grade against the immutable
    fork point and we cannot honour that, so the gate must BLOCK rather than
    silently fall back to the PR's own (editable) baseline.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "merge-base", ref, "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise BrokenCounter(f"git merge-base {ref} HEAD could not run: {exc}") from exc
    if result.returncode != 0:
        raise BrokenCounter(
            f"git merge-base {ref} HEAD failed (rc={result.returncode}): "
            f"{result.stderr.strip()}. A merge-base baseline needs full history "
            "(fetch-depth: 0) and a reachable base ref."
        )
    sha = result.stdout.strip()
    if not sha:
        raise BrokenCounter(f"git merge-base {ref} HEAD produced no commit")
    return sha


def load_baselines_at_ref(repo_root: Path, ref: str, path: Path) -> dict[str, int] | None:
    """Read the baselines file as it existed at ``ref``.

    Returns the parsed counters map, or None if the file did not exist at
    that ref (the baseline was first introduced after the merge-base — every
    counter is then new and has no immutable prior bar). A file that exists
    but is malformed raises BrokenCounter: a corrupt historical baseline is a
    broken gate, not an absent one.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{ref}:{path.as_posix()}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return parse_baselines_text(result.stdout, source=f"baselines at {ref}:{path.as_posix()}")


def effective_baselines(
    working: dict[str, int], merge_base: dict[str, int] | None
) -> dict[str, int]:
    """Grade against the merge-base bar for every counter that existed there.

    For a counter present in the merge-base baseline, its immutable value is
    used, so a PR editing the working-tree baselines file cannot loosen its
    own bar. A counter absent from the merge-base (added in this PR) has no
    prior bar and falls back to the working-tree value — a genuinely new
    counter, not a raised ceiling.
    """
    if merge_base is None:
        return dict(working)
    effective = dict(working)
    for name in working:
        if name in merge_base:
            effective[name] = merge_base[name]
    return effective


def read_tightened_on(path: Path) -> str | None:
    """Return the baselines file's ``tightened_on`` date (YYYY-MM-DD), or None.

    Tolerant: any read/parse failure yields None so the caller treats an
    unreadable date as 'cannot trust freshness' (fail-closed) rather than
    crashing the gate."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = payload.get("tightened_on")
    return value if isinstance(value, str) and value.strip() else None


def baseline_age_days(tightened_on: str, today: str) -> int | None:
    """Whole days between ``tightened_on`` and ``today`` (both ISO dates).

    None if either date is unparseable. A negative value means the baseline date
    is in the future; the freshness gate treats that as untrustworthy too.
    """
    try:
        then = date.fromisoformat(tightened_on)
        now = date.fromisoformat(today)
    except ValueError:
        return None
    return (now - then).days


def save_baselines(path: Path, counters: dict[str, int], today: str) -> None:
    """Atomically write the baselines file (temp file + rename)."""
    payload = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "tightened_on": today,
        "counters": {name: counters[name] for name in sorted(counters)},
    }
    text = json.dumps(payload, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=path.name + ".", delete=False
    )
    try:
        with handle:
            handle.write(text)
        os.replace(handle.name, path)
    except BaseException:
        os.unlink(handle.name)
        raise


def tighten(baselines: dict[str, int], comparisons: list[Comparison]) -> dict[str, int]:
    """Pure: return baselines with every improvement adopted as the new bound.

    Idempotent (tightening twice with the same readings changes nothing)
    and monotone (never loosens a bound). Must only be called on a green
    run; regressions are the caller's responsibility to reject first.
    """
    tightened = dict(baselines)
    for comparison in comparisons:
        if comparison.improved:
            tightened[comparison.name] = comparison.value
    return tightened


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def measure_or_broken(counter, repo_root: Path):
    """Run one counter's measurement under the fail-closed contract.

    Any crash — not just a deliberate BrokenCounter — must surface as
    BROKEN (exit 2), never as a traceback and never as a pass: an
    unmeasured counter is an open gate.
    """
    try:
        return counter.measure(repo_root)
    except BrokenCounter:
        raise
    except Exception as exc:
        raise BrokenCounter(f"{counter.name} measurement crashed: {exc!r}") from exc


def compare_all(repo_root: Path, baselines: dict[str, int]) -> list[Comparison]:
    comparisons = []
    for counter in COUNTERS:
        reading = measure_or_broken(counter, repo_root)
        comparisons.append(
            Comparison(
                name=counter.name,
                direction=counter.direction,
                baseline=baselines[counter.name],
                value=reading.value,
                end_target=counter.end_target,
                evidence=reading.evidence,
            )
        )
    return comparisons


def render_table(comparisons: list[Comparison]) -> str:
    width = max(len(c.name) for c in comparisons)
    arrow = {Direction.DOWN: "v", Direction.UP: "^"}
    lines = [
        f"  {c.name:<{width}}  {arrow[c.direction]}  baseline={c.baseline:<5d} "
        f"current={c.value:<5d} target={c.end_target:<5d} {c.verdict}"
        for c in comparisons
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One-way quality ratchet: counters may only improve.",
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument(
        "--tighten",
        action="store_true",
        help="on a green run, adopt improvements as new baselines (writes the baselines file)",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="create the baselines file from current reality (refuses to overwrite)",
    )
    parser.add_argument(
        "--baseline-merge-base-of",
        metavar="REF",
        default=None,
        help="grade counters against the baseline as it existed at the merge-base "
        "of REF and HEAD, not the working tree. A PR cannot raise its own ceiling: "
        "editing the baselines file in the same diff cannot loosen the gate. "
        "Fail-closed (BROKEN) if the merge-base cannot be resolved.",
    )
    parser.add_argument("--explain", metavar="COUNTER", help="show the evidence behind one counter")
    parser.add_argument("--list", action="store_true", help="list counters and definitions")
    parser.add_argument(
        "--max-baseline-age-days",
        type=int,
        default=None,
        metavar="N",
        help="fail (BROKEN) if the baselines file's tightened_on is older than N "
        "days — a freshness gate so a stale baseline cannot silently mask drift",
    )
    parser.add_argument(
        "--refresh-baseline-date",
        action="store_true",
        help="with --tighten, rewrite tightened_on even when counters are unchanged; "
        "use only for reviewed stale-but-green baseline refreshes",
    )
    parser.add_argument(
        "--today",
        default=datetime.now(timezone.utc).date().isoformat(),
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    baseline_path = repo_root / BASELINE_PATH

    if args.list:
        for counter in COUNTERS:
            print(f"{counter.name} ({counter.direction}, target {counter.end_target})")
            print(f"  {counter.definition}")
        return EXIT_GREEN

    try:
        if args.explain:
            by_name = {counter.name: counter for counter in COUNTERS}
            counter = by_name.get(args.explain)
            if counter is None:
                print(f"unknown counter: {args.explain} (use --list)", file=sys.stderr)
                return EXIT_BROKEN
            reading = measure_or_broken(counter, repo_root)
            print(f"{counter.name} = {reading.value}")
            print(counter.definition)
            for line in reading.evidence:
                print(f"  {line}")
            return EXIT_GREEN

        if args.init:
            if baseline_path.exists():
                print(
                    f"refusing to overwrite existing {BASELINE_PATH}; loosening a "
                    "ratchet is a reviewed manual edit, not a re-init.",
                    file=sys.stderr,
                )
                return EXIT_BROKEN
            values = {
                counter.name: measure_or_broken(counter, repo_root).value
                for counter in COUNTERS
            }
            save_baselines(baseline_path, values, args.today)
            print(f"initialized {BASELINE_PATH} from current reality:")
            for name in sorted(values):
                print(f"  {name}={values[name]}")
            return EXIT_GREEN

        baselines = load_baselines(baseline_path)
        judged_baselines = baselines
        if args.baseline_merge_base_of is not None:
            merge_base_sha = resolve_merge_base(repo_root, args.baseline_merge_base_of)
            merge_base_baselines = load_baselines_at_ref(
                repo_root, merge_base_sha, BASELINE_PATH
            )
            judged_baselines = effective_baselines(baselines, merge_base_baselines)
        comparisons = compare_all(repo_root, judged_baselines)
    except BrokenCounter as exc:
        print(f"ratchet: BROKEN — {exc}", file=sys.stderr)
        return EXIT_BROKEN

    # Freshness gate: a baseline that is never re-measured silently masks
    # drift (the watcher needs a watcher). When asked, fail closed if the
    # stored tightened_on is older than the allowed window or unreadable.
    if args.max_baseline_age_days is not None:
        tightened = read_tightened_on(baseline_path)
        age = baseline_age_days(tightened, args.today) if tightened else None
        if age is None:
            print(
                "ratchet: BROKEN — baselines file has no readable tightened_on "
                "date; a freshness gate cannot trust it.",
                file=sys.stderr,
            )
            return EXIT_BROKEN
        if age < 0:
            print(
                f"ratchet: BROKEN — baseline tightened_on={tightened} is after "
                f"today={args.today}; future baseline dates cannot be trusted.",
                file=sys.stderr,
            )
            return EXIT_BROKEN
        stale_refresh_requested = args.tighten and args.refresh_baseline_date
        if age > args.max_baseline_age_days and not stale_refresh_requested:
            print(
                f"ratchet: BROKEN — baseline is {age}d old "
                f"(tightened_on={tightened}) and exceeds the "
                f"--max-baseline-age-days {args.max_baseline_age_days} freshness "
                "gate. A stale baseline silently masks drift; re-measure and run "
                "`ratchet.py --tighten --refresh-baseline-date` only as a reviewed "
                "stale-but-green baseline refresh.",
                file=sys.stderr,
            )
            return EXIT_BROKEN

    regressions = [c for c in comparisons if c.regressed]
    improvements = [c for c in comparisons if c.improved]

    if args.json:
        print(
            json.dumps(
                {
                    "schema_version": REPORT_SCHEMA_VERSION,
                    "green": not regressions,
                    "comparisons": [c.to_dict() for c in comparisons],
                },
                indent=2,
            )
        )
    else:
        print(render_table(comparisons))

    if regressions:
        for comparison in regressions:
            print(
                f"ratchet: FAIL — {comparison.name} moved {comparison.baseline} -> "
                f"{comparison.value} against direction {comparison.direction}; "
                f"run --explain {comparison.name} for the evidence.",
                file=sys.stderr,
            )
        return EXIT_REGRESSION

    refresh_requested = args.tighten and args.refresh_baseline_date
    if args.tighten and (improvements or refresh_requested):
        save_baselines(baseline_path, tighten(baselines, comparisons), args.today)
        for comparison in improvements:
            print(f"ratchet: tightened {comparison.name} {comparison.baseline} -> {comparison.value}")
        if refresh_requested and not improvements:
            print(f"ratchet: refreshed {BASELINE_PATH} tightened_on to {args.today}.")
            print(f"ratchet: commit {BASELINE_PATH} as a reviewed baseline refresh.")
        else:
            print(f"ratchet: commit {BASELINE_PATH} together with the improving change.")
    elif improvements:
        names = ", ".join(c.name for c in improvements)
        print(f"ratchet: improvements available ({names}); run with --tighten to adopt.")

    return EXIT_GREEN


if __name__ == "__main__":
    raise SystemExit(main())
