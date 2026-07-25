#!/usr/bin/env python3
"""Branch janitor — evidence-gated TTL sweep for remote branch sprawl.

Policy source: the 2026-07-04 branch/sprawl dive (300 remote heads; 46
provably safe; 237 policy-sweep cohort). `delete_branch_on_merge` is already
on and working — the backlog is closed-unmerged-PR branches and direct pushes
that the setting never touches. This script is the janitor the dive
recommended.

Classification (highest precedence first):
  protected            default branch, or head of an OPEN PR — never touched.
  exempt               listed in docs/governance/BRANCH_REGISTRY.yaml — never
                       touched, regardless of any other evidence.
  delete-merged        tip OID == head OID of a MERGED PR. Content is in main
                       by definition. Deletable.
  delete-closed-idle   tip OID == head OID of a CLOSED (never merged) PR, PR
                       closed and tip idle for more than --closed-idle-days
                       (default 14). Deletable.
  candidate-tip-moved  branch has PR history but the tip matches no PR head
                       OID (re-pushed after close/merge). Listed for operator
                       review; NOT deletable — the re-push is unreviewed
                       content the PR record does not describe.
  candidate-no-pr-idle no PR ever, tip idle more than --no-pr-idle-days
                       (default 30). Listed for operator review; NOT deletable
                       — there is no hard evidence for a never-PR'd branch.
  waiting              closed-PR match inside the idle window.
  active               everything else.

A branch is deletable ONLY with hard evidence: tip OID == a merged PR head
OID, or closed-PR head match plus the idle window. Before any deletion the
tip is preserved forever as tag archive/pr<N>--<branch>, and the delete push
uses --force-with-lease pinned to the surveyed tip OID so a branch that moved
after the survey is never deleted.

Modes:
  (default) dry run    classify only; write a receipt to
                       reports/governance/branch_janitor_<date>.md.
  --execute            tag-then-delete every deletable branch, then write an
                       execute receipt. Exit non-zero if any action failed.

Offline fixtures (--branches-json / --prs-json) replace the live git/gh
collectors so tests never touch the network.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = "docs/governance/BRANCH_REGISTRY.yaml"
DEFAULT_REPORT_DIR = "reports/governance"
DEFAULT_BRANCH = "main"
PR_FETCH_LIMIT = 2000

CLASS_PROTECTED = "protected"
CLASS_EXEMPT = "exempt"
CLASS_DELETE_MERGED = "delete-merged"
CLASS_DELETE_CLOSED_IDLE = "delete-closed-idle"
CLASS_CANDIDATE_TIP_MOVED = "candidate-tip-moved"
CLASS_CANDIDATE_NO_PR = "candidate-no-pr-idle"
CLASS_WAITING = "waiting"
CLASS_ACTIVE = "active"

CLASS_ORDER = (
    CLASS_DELETE_MERGED,
    CLASS_DELETE_CLOSED_IDLE,
    CLASS_CANDIDATE_TIP_MOVED,
    CLASS_CANDIDATE_NO_PR,
    CLASS_WAITING,
    CLASS_EXEMPT,
    CLASS_PROTECTED,
    CLASS_ACTIVE,
)
DELETABLE_CLASSES = (CLASS_DELETE_MERGED, CLASS_DELETE_CLOSED_IDLE)
CANDIDATE_CLASSES = DELETABLE_CLASSES + (
    CLASS_CANDIDATE_TIP_MOVED,
    CLASS_CANDIDATE_NO_PR,
)


@dataclass(frozen=True)
class Branch:
    name: str
    tip_oid: str
    tip_date: datetime


@dataclass(frozen=True)
class PullRequest:
    number: int
    state: str  # OPEN | CLOSED | MERGED
    head_ref: str
    head_oid: str
    merged_at: datetime | None
    closed_at: datetime | None


@dataclass(frozen=True)
class RegistryEntry:
    kind: str  # "branch" (exact) or "pattern" (fnmatch glob)
    value: str
    reason: str


@dataclass
class Verdict:
    branch: Branch
    klass: str
    deletable: bool
    evidence: str
    pr_number: int | None = None
    tag_name: str | None = None


@dataclass
class ActionResult:
    verdict: Verdict
    ok: bool
    detail: str


def parse_rfc3339(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def rfc3339(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(
    cmd: list[str], *, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        check=check,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Registry


def parse_registry_text(text: str) -> list[RegistryEntry]:
    """Minimal stdlib parser for the constrained BRANCH_REGISTRY.yaml schema.

    Supports exactly: top-level scalar keys, an `exempt:` list whose items are
    mappings with single-line scalar values (`branch:`/`pattern:`/`reason:`).
    """
    entries: list[RegistryEntry] = []
    in_exempt = False
    current: dict[str, str] | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        if "branch" in current:
            entries.append(
                RegistryEntry("branch", current["branch"], current.get("reason", ""))
            )
        elif "pattern" in current:
            entries.append(
                RegistryEntry("pattern", current["pattern"], current.get("reason", ""))
            )
        current = None

    def parse_kv(fragment: str) -> tuple[str, str] | None:
        if ":" not in fragment:
            return None
        key, _, raw = fragment.partition(":")
        value = raw.strip().strip("\"'")
        return key.strip(), value

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" "):
            flush()
            in_exempt = line.strip() == "exempt:"
            continue
        if not in_exempt:
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            flush()
            current = {}
            kv = parse_kv(stripped[2:])
            if kv:
                current[kv[0]] = kv[1]
        elif current is not None:
            kv = parse_kv(stripped)
            if kv:
                current[kv[0]] = kv[1]
    flush()
    return entries


def load_registry(path: Path) -> list[RegistryEntry]:
    if not path.exists():
        raise SystemExit(f"error: branch registry not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        entries: list[RegistryEntry] = []
        for item in data.get("exempt", []) or []:
            if not isinstance(item, dict):
                continue
            reason = str(item.get("reason", ""))
            if "branch" in item:
                entries.append(RegistryEntry("branch", str(item["branch"]), reason))
            elif "pattern" in item:
                entries.append(RegistryEntry("pattern", str(item["pattern"]), reason))
        return entries
    except ImportError:
        return parse_registry_text(text)


def registry_match(name: str, entries: list[RegistryEntry]) -> RegistryEntry | None:
    for entry in entries:
        if entry.kind == "branch" and name == entry.value:
            return entry
        if entry.kind == "pattern" and fnmatch.fnmatchcase(name, entry.value):
            return entry
    return None


# ---------------------------------------------------------------------------
# Collection (live paths; replaced by fixtures in tests)


def detect_repo_slug(remote: str) -> str:
    url = run(["git", "remote", "get-url", remote]).stdout.strip()
    match = re.search(r"github\.com[:/]+([^/]+)/([^/\s]+?)(?:\.git)?/?$", url)
    if not match:
        raise SystemExit(f"error: cannot derive owner/repo from remote url: {url}")
    return f"{match.group(1)}/{match.group(2)}"


def collect_branches(remote: str, *, fetch: bool = True) -> list[Branch]:
    if fetch:
        run(
            [
                "git",
                "fetch",
                "--prune",
                "--no-tags",
                remote,
                f"+refs/heads/*:refs/remotes/{remote}/*",
            ]
        )
    fmt = "%(refname)%00%(objectname)%00%(committerdate:iso8601-strict)"
    out = run(["git", "for-each-ref", f"--format={fmt}", f"refs/remotes/{remote}/"])
    prefix = f"refs/remotes/{remote}/"
    branches: list[Branch] = []
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        refname, oid, date_str = line.split("\x00")
        name = refname[len(prefix):]
        if name == "HEAD":
            continue
        branches.append(Branch(name, oid, parse_rfc3339(date_str)))
    return branches


def collect_prs(repo: str) -> list[PullRequest]:
    out = run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--limit",
            str(PR_FETCH_LIMIT),
            "--json",
            "number,state,headRefName,headRefOid,mergedAt,closedAt",
        ]
    )
    return [pr_from_dict(item) for item in json.loads(out.stdout)]


def pr_from_dict(item: dict) -> PullRequest:
    def maybe_date(key: str) -> datetime | None:
        value = item.get(key)
        return parse_rfc3339(value) if value else None

    return PullRequest(
        number=int(item["number"]),
        state=str(item["state"]).upper(),
        head_ref=str(item["headRefName"]),
        head_oid=str(item.get("headRefOid") or ""),
        merged_at=maybe_date("mergedAt"),
        closed_at=maybe_date("closedAt"),
    )


def branch_from_dict(item: dict) -> Branch:
    return Branch(
        name=str(item["name"]),
        tip_oid=str(item["tip_oid"]),
        tip_date=parse_rfc3339(item["tip_date"]),
    )


# ---------------------------------------------------------------------------
# Policy


def tag_name_for(pr_number: int, branch_name: str) -> str:
    return f"archive/pr{pr_number}--{branch_name}"


def idle_days(now: datetime, *moments: datetime | None) -> int:
    latest = max(m for m in moments if m is not None)
    return (now - latest).days


def classify_branch(
    branch: Branch,
    prs: list[PullRequest],
    registry: list[RegistryEntry],
    now: datetime,
    *,
    closed_idle_days: int = 14,
    no_pr_idle_days: int = 30,
    default_branch: str = DEFAULT_BRANCH,
) -> Verdict:
    short = branch.tip_oid[:12]

    if branch.name == default_branch:
        return Verdict(branch, CLASS_PROTECTED, False, "default branch — never touched")

    open_prs = [pr for pr in prs if pr.state == "OPEN"]
    if open_prs:
        numbers = ", ".join(f"#{pr.number}" for pr in sorted_prs(open_prs))
        return Verdict(branch, CLASS_PROTECTED, False, f"head of OPEN PR {numbers}")

    entry = registry_match(branch.name, registry)
    if entry is not None:
        label = f"{entry.kind} `{entry.value}`"
        return Verdict(
            branch,
            CLASS_EXEMPT,
            False,
            f"registry {label}: {entry.reason or 'no reason recorded'}",
        )

    merged_matches = [
        pr for pr in prs if pr.state == "MERGED" and pr.head_oid == branch.tip_oid
    ]
    if merged_matches:
        pr = sorted_prs(merged_matches)[-1]
        return Verdict(
            branch,
            CLASS_DELETE_MERGED,
            True,
            f"tip {short} == head OID of MERGED PR #{pr.number}; content in {default_branch}",
            pr_number=pr.number,
            tag_name=tag_name_for(pr.number, branch.name),
        )

    closed_matches = [
        pr for pr in prs if pr.state == "CLOSED" and pr.head_oid == branch.tip_oid
    ]
    if closed_matches:
        pr = sorted_prs(closed_matches)[-1]
        idle = idle_days(now, branch.tip_date, pr.closed_at)
        if idle > closed_idle_days:
            return Verdict(
                branch,
                CLASS_DELETE_CLOSED_IDLE,
                True,
                (
                    f"tip {short} == head OID of CLOSED PR #{pr.number}; "
                    f"idle {idle}d > {closed_idle_days}d window"
                ),
                pr_number=pr.number,
                tag_name=tag_name_for(pr.number, branch.name),
            )
        return Verdict(
            branch,
            CLASS_WAITING,
            False,
            (
                f"tip {short} == head OID of CLOSED PR #{pr.number}; "
                f"idle {idle}d <= {closed_idle_days}d window"
            ),
            pr_number=pr.number,
        )

    if prs:
        history = ", ".join(f"#{pr.number}({pr.state})" for pr in sorted_prs(prs))
        return Verdict(
            branch,
            CLASS_CANDIDATE_TIP_MOVED,
            False,
            (
                f"PR history {history} but tip {short} matches no PR head OID "
                "(re-pushed after close/merge) — operator review"
            ),
        )

    idle = idle_days(now, branch.tip_date)
    if idle > no_pr_idle_days:
        return Verdict(
            branch,
            CLASS_CANDIDATE_NO_PR,
            False,
            (
                f"no PR ever; tip idle {idle}d > {no_pr_idle_days}d window; "
                "no hard evidence — operator review"
            ),
        )
    return Verdict(branch, CLASS_ACTIVE, False, f"tip idle {idle}d — in use")


def sorted_prs(prs: list[PullRequest]) -> list[PullRequest]:
    return sorted(prs, key=lambda pr: pr.number)


def classify_all(
    branches: list[Branch],
    prs: list[PullRequest],
    registry: list[RegistryEntry],
    now: datetime,
    *,
    closed_idle_days: int = 14,
    no_pr_idle_days: int = 30,
    default_branch: str = DEFAULT_BRANCH,
) -> list[Verdict]:
    by_head: dict[str, list[PullRequest]] = {}
    for pr in prs:
        by_head.setdefault(pr.head_ref, []).append(pr)
    return [
        classify_branch(
            branch,
            by_head.get(branch.name, []),
            registry,
            now,
            closed_idle_days=closed_idle_days,
            no_pr_idle_days=no_pr_idle_days,
            default_branch=default_branch,
        )
        for branch in sorted(branches, key=lambda b: b.name)
    ]


# ---------------------------------------------------------------------------
# Execution (tag-then-delete; only reachable via --execute)


def collect_archive_tags(remote: str) -> dict[str, str]:
    out = run(["git", "ls-remote", "--tags", remote, "refs/tags/archive/*"])
    tags: dict[str, str] = {}
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        oid, _, refname = line.partition("\t")
        if refname.endswith("^{}"):
            continue
        tags[refname.strip()] = oid.strip()
    return tags


def execute_deletions(
    verdicts: list[Verdict], remote: str, *, max_deletions: int = 0
) -> list[ActionResult]:
    todo = [v for v in verdicts if v.deletable and v.klass in DELETABLE_CLASSES]
    if max_deletions and len(todo) > max_deletions:
        raise SystemExit(
            f"error: {len(todo)} deletable branches exceed --max-deletions "
            f"{max_deletions}; refusing to act"
        )
    existing_tags = collect_archive_tags(remote)
    results: list[ActionResult] = []
    for verdict in todo:
        branch = verdict.branch
        tag_ref = f"refs/tags/{verdict.tag_name}"
        head_ref = f"refs/heads/{branch.name}"

        check = run(["git", "check-ref-format", tag_ref], check=False)
        if check.returncode != 0:
            results.append(ActionResult(verdict, False, f"invalid tag ref {tag_ref}"))
            continue

        existing = existing_tags.get(tag_ref)
        if existing is not None and existing != branch.tip_oid:
            results.append(
                ActionResult(
                    verdict,
                    False,
                    f"tag {verdict.tag_name} exists at {existing[:12]} != tip — skipped",
                )
            )
            continue
        if existing is None:
            push_tag = run(
                ["git", "push", remote, f"{branch.tip_oid}:{tag_ref}"], check=False
            )
            if push_tag.returncode != 0:
                results.append(
                    ActionResult(
                        verdict,
                        False,
                        f"tag push failed: {push_tag.stderr.strip()[:200]}",
                    )
                )
                continue

        # --force-with-lease pinned to the surveyed tip: if the branch moved
        # after the survey, the delete is rejected by the remote.
        delete = run(
            [
                "git",
                "push",
                f"--force-with-lease={head_ref}:{branch.tip_oid}",
                remote,
                f":{head_ref}",
            ],
            check=False,
        )
        if delete.returncode != 0:
            results.append(
                ActionResult(
                    verdict,
                    False,
                    f"tagged {verdict.tag_name}; delete failed: "
                    f"{delete.stderr.strip()[:200]}",
                )
            )
            continue
        results.append(
            ActionResult(verdict, True, f"tagged {verdict.tag_name}; branch deleted")
        )
    return results


# ---------------------------------------------------------------------------
# Receipt


def render_receipt(
    verdicts: list[Verdict],
    *,
    mode: str,
    now: datetime,
    remote: str,
    repo: str,
    registry_path: str,
    registry_count: int,
    closed_idle_days: int,
    no_pr_idle_days: int,
    actions: list[ActionResult] | None = None,
) -> str:
    by_class: dict[str, list[Verdict]] = {klass: [] for klass in CLASS_ORDER}
    for verdict in verdicts:
        by_class.setdefault(verdict.klass, []).append(verdict)

    deletable = [v for v in verdicts if v.deletable]
    candidates = [v for v in verdicts if v.klass in CANDIDATE_CLASSES]

    lines: list[str] = []
    lines.append("---")
    lines.append(f"title: Branch janitor receipt {now.date().isoformat()}")
    lines.append(f"date: {now.date().isoformat()}")
    lines.append(f"mode: {mode}")
    lines.append("tool: scripts/governance/branch_janitor.py")
    lines.append("---")
    lines.append("")
    lines.append(f"# Branch janitor receipt — {mode}")
    lines.append("")
    lines.append(f"- Generated: {rfc3339(now)}")
    lines.append(f"- Remote: {remote} ({repo})")
    lines.append(f"- Branches surveyed: {len(verdicts)}")
    lines.append(
        f"- Policy: closed-PR idle > {closed_idle_days}d deletable; "
        f"no-PR idle > {no_pr_idle_days}d candidate-only; "
        "deletion requires tip == merged-PR head OID or closed-PR head match "
        "+ idle window; tag archive/pr<N>--<branch> before every delete"
    )
    lines.append(f"- Registry: {registry_path} ({registry_count} entries)")
    lines.append(f"- Deletable now: {len(deletable)}")
    lines.append(f"- Total candidates (incl. review-only): {len(candidates)}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| class | count | deletable |")
    lines.append("|---|---|---|")
    for klass in CLASS_ORDER:
        group = by_class.get(klass, [])
        flag = "yes" if klass in DELETABLE_CLASSES else "no"
        lines.append(f"| {klass} | {len(group)} | {flag} |")
    lines.append("")

    def emit_table(title: str, group: list[Verdict], *, with_tag: bool) -> None:
        lines.append(f"## {title} ({len(group)})")
        lines.append("")
        if not group:
            lines.append("None.")
            lines.append("")
            return
        if with_tag:
            lines.append("| branch | tip | last commit | evidence | planned tag |")
            lines.append("|---|---|---|---|---|")
        else:
            lines.append("| branch | tip | last commit | evidence |")
            lines.append("|---|---|---|---|")
        for verdict in group:
            branch = verdict.branch
            row = [
                f"`{branch.name}`",
                branch.tip_oid[:12],
                branch.tip_date.date().isoformat(),
                verdict.evidence,
            ]
            if with_tag:
                row.append(f"`{verdict.tag_name}`" if verdict.tag_name else "-")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    emit_table(
        "Deletable — merged-PR head evidence",
        by_class[CLASS_DELETE_MERGED],
        with_tag=True,
    )
    emit_table(
        "Deletable — closed-PR idle",
        by_class[CLASS_DELETE_CLOSED_IDLE],
        with_tag=True,
    )
    emit_table(
        "Operator review — tip moved after PR",
        by_class[CLASS_CANDIDATE_TIP_MOVED],
        with_tag=False,
    )
    emit_table(
        "Operator review — never PR'd, idle",
        by_class[CLASS_CANDIDATE_NO_PR],
        with_tag=False,
    )
    emit_table("Waiting — inside idle window", by_class[CLASS_WAITING], with_tag=False)
    emit_table("Exempt — branch registry", by_class[CLASS_EXEMPT], with_tag=False)
    emit_table("Protected", by_class[CLASS_PROTECTED], with_tag=False)

    active = by_class[CLASS_ACTIVE]
    lines.append(f"## Active ({len(active)})")
    lines.append("")
    lines.append(
        "Recent branches with no PR history; listed by name only to keep the "
        "receipt bounded."
    )
    lines.append("")
    for verdict in active:
        lines.append(f"- `{verdict.branch.name}` ({verdict.evidence})")
    lines.append("")

    if actions is not None:
        failed = [a for a in actions if not a.ok]
        lines.append(f"## Actions ({len(actions)} attempted, {len(failed)} failed)")
        lines.append("")
        if actions:
            lines.append("| branch | result | detail |")
            lines.append("|---|---|---|")
            for action in actions:
                status = "ok" if action.ok else "FAILED"
                lines.append(
                    f"| `{action.verdict.branch.name}` | {status} | {action.detail} |"
                )
        else:
            lines.append("No deletable branches; nothing attempted.")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="classify and write a receipt; no writes to the remote (default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="tag archive/pr<N>--<branch> then delete each deletable branch",
    )
    parser.add_argument("--remote", default="origin")
    parser.add_argument(
        "--repo", default=None, help="owner/name (default: derived from remote url)"
    )
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--default-branch", default=DEFAULT_BRANCH)
    parser.add_argument("--closed-idle-days", type=int, default=14)
    parser.add_argument("--no-pr-idle-days", type=int, default=30)
    parser.add_argument(
        "--max-deletions",
        type=int,
        default=0,
        help="abort execute mode if more branches are deletable (0 = no cap)",
    )
    parser.add_argument(
        "--now", default=None, help="RFC 3339 override for reproducible runs"
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="skip git fetch; classify existing refs/remotes/<remote>/*",
    )
    parser.add_argument(
        "--branches-json",
        default=None,
        help="fixture file: [{name, tip_oid, tip_date}] — replaces git collection",
    )
    parser.add_argument(
        "--prs-json",
        default=None,
        help="fixture file: gh pr list --json output — replaces gh collection",
    )
    args = parser.parse_args(argv)
    if args.dry_run and args.execute:
        parser.error("--dry-run and --execute are mutually exclusive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "execute" if args.execute else "dry-run"
    now = parse_rfc3339(args.now) if args.now else datetime.now(timezone.utc)

    registry_path = Path(args.registry)
    if not registry_path.is_absolute():
        registry_path = REPO_ROOT / registry_path
    registry = load_registry(registry_path)

    if args.branches_json:
        payload = json.loads(Path(args.branches_json).read_text(encoding="utf-8"))
        branches = [branch_from_dict(item) for item in payload]
    else:
        branches = collect_branches(args.remote, fetch=not args.no_fetch)

    if args.prs_json:
        payload = json.loads(Path(args.prs_json).read_text(encoding="utf-8"))
        prs = [pr_from_dict(item) for item in payload]
        repo = args.repo or "fixture/fixture"
    else:
        repo = args.repo or detect_repo_slug(args.remote)
        prs = collect_prs(repo)

    verdicts = classify_all(
        branches,
        prs,
        registry,
        now,
        closed_idle_days=args.closed_idle_days,
        no_pr_idle_days=args.no_pr_idle_days,
        default_branch=args.default_branch,
    )

    actions: list[ActionResult] | None = None
    if args.execute:
        actions = execute_deletions(
            verdicts, args.remote, max_deletions=args.max_deletions
        )

    receipt = render_receipt(
        verdicts,
        mode=mode,
        now=now,
        remote=args.remote,
        repo=repo,
        registry_path=args.registry,
        registry_count=len(registry),
        closed_idle_days=args.closed_idle_days,
        no_pr_idle_days=args.no_pr_idle_days,
        actions=actions,
    )

    report_dir = Path(args.report_dir)
    if not report_dir.is_absolute():
        report_dir = REPO_ROOT / report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_execute" if args.execute else ""
    report_path = report_dir / f"branch_janitor_{now.date().isoformat()}{suffix}.md"
    report_path.write_text(receipt + "\n", encoding="utf-8")

    counts = {klass: 0 for klass in CLASS_ORDER}
    for verdict in verdicts:
        counts[verdict.klass] = counts.get(verdict.klass, 0) + 1
    deletable_count = sum(counts[klass] for klass in DELETABLE_CLASSES)
    candidate_count = sum(counts[klass] for klass in CANDIDATE_CLASSES)
    print(f"branch_janitor [{mode}] surveyed={len(verdicts)} " + " ".join(
        f"{klass}={counts[klass]}" for klass in CLASS_ORDER
    ))
    print(
        f"branch_janitor [{mode}] deletable={deletable_count} "
        f"candidates_total={candidate_count} receipt={report_path}"
    )
    if actions is not None:
        failed = [a for a in actions if not a.ok]
        print(
            f"branch_janitor [execute] attempted={len(actions)} failed={len(failed)}"
        )
        if failed:
            for action in failed:
                print(
                    f"branch_janitor [execute] FAILED {action.verdict.branch.name}: "
                    f"{action.detail}",
                    file=sys.stderr,
                )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
