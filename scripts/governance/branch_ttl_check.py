#!/usr/bin/env python3
"""Branch TTL register — local branches idle past TTL and not merged.

One World (``docs/plans/ONE_WORLD_2026-08-30.md``, Step 4): residue branches
are the archive problem. This script owns
``docs/state/BRANCH_TTL_REGISTER.md``: it lists local branches whose tip
commit is older than ``--ttl-days`` (default 14) and that are not merged
into the local ``--base-ref`` (default ``origin/main``), with ahead/behind
counts and last-commit date. Fetch-free: it reads local refs only and never
touches the network. Advisory by design — it registers drift; it never
deletes anything (that evidence-gated job belongs to
``scripts/governance/branch_janitor.py``).

Modes:
  (default)    recompute and write the register.
  --advisory   compute only; print a bounded summary to stderr and never
               write. ``make onboard`` uses this mode so session status
               stays read-only and stdout stays machine-pure. Always
               exits 0.

Offline fixtures (--branches-json) replace live git collection so tests
never touch a repository:
  [{"name", "tip_oid", "tip_date", "merged", "ahead", "behind"}]
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTER = "docs/state/BRANCH_TTL_REGISTER.md"
DEFAULT_BASE_REF = "origin/main"
DEFAULT_TTL_DAYS = 14
SECONDS_PER_DAY = 24 * 60 * 60


@dataclass(frozen=True)
class BranchRecord:
    name: str
    tip_oid: str
    tip_date: datetime
    merged: bool
    ahead: int | None
    behind: int | None


def parse_rfc3339(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def rfc3339(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        check=check,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _base_exists(base_ref: str) -> bool:
    probe = _git(["rev-parse", "--verify", "--quiet", base_ref], check=False)
    return probe.returncode == 0


def collect_branches(base_ref: str) -> list[BranchRecord]:
    """Live collection over local refs only — no fetch, no network."""
    fmt = "%(refname:short)%00%(objectname)%00%(committerdate:unix)"
    out = _git(["for-each-ref", f"--format={fmt}", "refs/heads/"]).stdout
    merged: set[str] = set()
    base_present = _base_exists(base_ref)
    if base_present:
        merged_out = _git(
            ["branch", "--merged", base_ref, "--format=%(refname:short)"]
        ).stdout
        merged = {line.strip() for line in merged_out.splitlines() if line.strip()}
    records: list[BranchRecord] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        name, oid, raw_ts = line.split("\x00")
        tip_date = datetime.fromtimestamp(int(raw_ts), tz=timezone.utc)
        is_merged = name in merged
        ahead: int | None = None
        behind: int | None = None
        if base_present and not is_merged:
            counts = _git(
                ["rev-list", "--left-right", "--count", f"{base_ref}...{name}"],
                check=False,
            )
            if counts.returncode == 0:
                left, _, right = counts.stdout.strip().partition("\t")
                try:
                    behind, ahead = int(left), int(right)
                except ValueError:
                    ahead = behind = None
        records.append(BranchRecord(name, oid, tip_date, is_merged, ahead, behind))
    return records


def branches_from_fixture(payload: list[dict]) -> list[BranchRecord]:
    records: list[BranchRecord] = []
    for item in payload:
        ahead = item.get("ahead")
        behind = item.get("behind")
        records.append(
            BranchRecord(
                name=str(item["name"]),
                tip_oid=str(item.get("tip_oid", "")),
                tip_date=parse_rfc3339(str(item["tip_date"])),
                merged=bool(item.get("merged", False)),
                ahead=int(ahead) if ahead is not None else None,
                behind=int(behind) if behind is not None else None,
            )
        )
    return records


def stale_branches(
    records: list[BranchRecord],
    now: datetime,
    *,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> list[BranchRecord]:
    """Local branches idle past TTL and not merged into the base ref."""
    stale = [
        record
        for record in records
        if not record.merged
        and (now - record.tip_date).total_seconds() > ttl_days * SECONDS_PER_DAY
    ]
    return sorted(stale, key=lambda record: (record.tip_date, record.name))


def _world_locus() -> str:
    """Dogfood the claim-locus convention: commit + host + branch."""
    head = _git(["rev-parse", "HEAD"], check=False).stdout.strip()[:12] or "unknown"
    branch = (
        _git(["rev-parse", "--abbrev-ref", "HEAD"], check=False).stdout.strip()
        or "unknown"
    )
    host = platform.node() or "unknown"
    return f"commit {head} · host {host} · branch {branch}"


def render_register(
    stale: list[BranchRecord],
    *,
    total: int,
    merged_count: int,
    now: datetime,
    base_ref: str,
    ttl_days: int,
    locus: str,
) -> str:
    lines: list[str] = []
    lines.append("---")
    lines.append("role: report")
    lines.append(f"date: {now.date().isoformat()}")
    lines.append("generated_by: scripts/governance/branch_ttl_check.py")
    lines.append(
        "regenerate: python3 scripts/governance/branch_ttl_check.py"
    )
    lines.append("---")
    lines.append("")
    lines.append("# BRANCH TTL REGISTER")
    lines.append("")
    lines.append(
        "**Generated artifact — do not hand-edit.** The owning generator is "
        "`scripts/governance/branch_ttl_check.py`; regenerate it instead of "
        "editing rows. Advisory register only: listing here is not a deletion "
        "verdict. Evidence-gated cleanup belongs to "
        "`scripts/governance/branch_janitor.py`."
    )
    lines.append("")
    lines.append(f"- Generated: {rfc3339(now)} (fetch-free: local refs only)")
    lines.append(f"- World locus: {locus}")
    lines.append(
        f"- Policy: local branch tip idle > {ttl_days}d and not merged into "
        f"local `{base_ref}` (local ref may lag the remote)"
    )
    lines.append(
        f"- Local branches surveyed: {total} · merged into {base_ref}: "
        f"{merged_count} · stale: {len(stale)}"
    )
    lines.append("")
    lines.append(f"## Stale branches ({len(stale)})")
    lines.append("")
    if not stale:
        lines.append("None.")
        lines.append("")
    else:
        lines.append("| branch | last commit | ahead | behind | tip |")
        lines.append("|---|---|---|---|---|")
        for record in stale:
            ahead = str(record.ahead) if record.ahead is not None else "?"
            behind = str(record.behind) if record.behind is not None else "?"
            lines.append(
                f"| `{record.name}` | {record.tip_date.date().isoformat()} "
                f"| {ahead} | {behind} | {record.tip_oid[:12]} |"
            )
        lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--advisory",
        action="store_true",
        help="compute only; print summary to stderr, write nothing, exit 0",
    )
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF)
    parser.add_argument("--ttl-days", type=int, default=DEFAULT_TTL_DAYS)
    parser.add_argument("--register", default=DEFAULT_REGISTER)
    parser.add_argument(
        "--now", default=None, help="RFC 3339 override for reproducible runs"
    )
    parser.add_argument(
        "--branches-json",
        default=None,
        help="fixture file replacing live git collection (tests)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    now = parse_rfc3339(args.now) if args.now else datetime.now(timezone.utc)

    if args.branches_json:
        payload = json.loads(Path(args.branches_json).read_text(encoding="utf-8"))
        records = branches_from_fixture(payload)
    else:
        records = collect_branches(args.base_ref)

    stale = stale_branches(records, now, ttl_days=args.ttl_days)
    merged_count = sum(1 for record in records if record.merged)

    if args.advisory:
        register_path = REPO_ROOT / args.register
        freshness = (
            "current"
            if register_path.exists()
            else "missing — run: python3 scripts/governance/branch_ttl_check.py"
        )
        print(
            f"branch-ttl: {len(stale)} stale local branch(es) "
            f"(> {args.ttl_days}d idle, unmerged vs {args.base_ref}) · "
            f"register {args.register} ({freshness})",
            file=sys.stderr,
        )
        return 0

    register_path = Path(args.register)
    if not register_path.is_absolute():
        register_path = REPO_ROOT / register_path
    register_path.parent.mkdir(parents=True, exist_ok=True)
    register_path.write_text(
        render_register(
            stale,
            total=len(records),
            merged_count=merged_count,
            now=now,
            base_ref=args.base_ref,
            ttl_days=args.ttl_days,
            locus=_world_locus(),
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"branch_ttl_check surveyed={len(records)} merged={merged_count} "
        f"stale={len(stale)} register={register_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
