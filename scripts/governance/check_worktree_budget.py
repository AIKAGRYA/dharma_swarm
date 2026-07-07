#!/usr/bin/env python3
"""check_worktree_budget.py — make the worktree-budget rule real.

CLAUDE.md declares: open git worktrees must be <= active-track count
(docs/governance/ACTIVE_TRACK.yaml) + 1 canonical checkout + <=2 TTL-tagged
scratch trees. Until 2026-07-07 the rule carried an "(enforced 2026-06-18)"
label while nothing enforced it. This script is the enforcer.

Modes:
  (default)   human report on stdout, always exit 0 — safe for onboarding
  --strict    exit 1 when over budget (loop / cron / self-hosted CI use)
  --json      machine-readable verdict on stdout
  --receipt   also write the verdict to ~/.dharma/hygiene/
              worktree_budget_receipt.json (runtime receipts never enter git)

Read-only with respect to the repo: it never creates, prunes, or removes
worktrees. Disposal stays an operator decision; this closes the sensing
half of the loop and makes the violation impossible to not-see.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ACTIVE_TRACK_PATH = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"
CANONICAL_ALLOWANCE = 1
SCRATCH_ALLOWANCE = 2
# Track ids end in a date stamp (…-2026-06); worktree branch names use looser
# stamps (…-20260702) or none. Strip the stamp before substring matching.
_DATE_SUFFIX = re.compile(r"-20\d{2}(-\d{2})?$")


def parse_worktree_porcelain(text: str) -> list[dict]:
    """Parse `git worktree list --porcelain` output into worktree dicts."""
    trees: list[dict] = []
    cur: dict = {}
    for line in text.splitlines():
        line = line.rstrip()
        if not line:
            if cur:
                trees.append(cur)
                cur = {}
            continue
        if line.startswith("worktree "):
            if cur:  # tolerate missing blank-line separators
                trees.append(cur)
            cur = {"path": line.split(" ", 1)[1], "branch": None, "detached": False}
        elif line.startswith("branch ") and cur:
            ref = line.split(" ", 1)[1]
            cur["branch"] = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        elif line == "detached" and cur:
            cur["detached"] = True
    if cur:
        trees.append(cur)
    return trees


def load_active_track_ids(path: Path = ACTIVE_TRACK_PATH) -> list[str]:
    """Ids of tracks occupying the portfolio (status active/shippable)."""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        return [
            str(t.get("id"))
            for t in (data.get("active_tracks") or [])
            if isinstance(t, dict)
            and t.get("id")
            and str(t.get("status", "active")).lower() in {"active", "shippable"}
        ]
    except ImportError:
        # Stdlib fallback: `- id:` entries inside the active_tracks block only.
        ids: list[str] = []
        in_block = False
        for line in text.splitlines():
            if line.startswith("active_tracks:"):
                in_block = True
                continue
            if in_block and line and not line.startswith((" ", "\t", "#")):
                break
            m = re.match(r"\s{2}- id:\s*(\S+)", line)
            if in_block and m:
                ids.append(m.group(1).strip("'\""))
        return ids


def _track_stem(track_id: str) -> str:
    return _DATE_SUFFIX.sub("", track_id)


def evaluate(trees: list[dict], active_ids: list[str], repo_root: Path = REPO_ROOT) -> dict:
    """Budget verdict. Mapping is a substring heuristic (informational):
    a tree maps to a track when its branch or directory name contains the
    track id minus the date stamp."""
    stems = {_track_stem(t): t for t in active_ids}
    budget = len(active_ids) + CANONICAL_ALLOWANCE + SCRATCH_ALLOWANCE
    unmapped: list[dict] = []
    for w in trees:
        if str(w.get("path")) == str(repo_root):
            w["maps_to"] = "(canonical)"
            continue
        hay = f"{w.get('branch') or ''} {Path(str(w.get('path'))).name}".lower()
        hit = next((tid for stem, tid in stems.items() if stem.lower() in hay), None)
        w["maps_to"] = hit
        if hit is None:
            unmapped.append(w)
    return {
        "count": len(trees),
        "budget": budget,
        "active_tracks": len(active_ids),
        "canonical": CANONICAL_ALLOWANCE,
        "scratch": SCRATCH_ALLOWANCE,
        "over_budget": len(trees) > budget,
        "over_by": max(0, len(trees) - budget),
        "unmapped_count": len(unmapped),
        "unmapped": [
            {"path": w["path"], "branch": w.get("branch"), "detached": w.get("detached", False)}
            for w in unmapped
        ],
    }


def evaluate_for_repo(repo_root: Path = REPO_ROOT) -> dict:
    res = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True, timeout=30, cwd=str(repo_root),
    )
    if res.returncode != 0:
        raise RuntimeError(f"git worktree list failed: {res.stderr.strip()[:200]}")
    trees = parse_worktree_porcelain(res.stdout)
    ids = load_active_track_ids(repo_root / "docs/governance/ACTIVE_TRACK.yaml")
    verdict = evaluate(trees, ids, repo_root=repo_root)
    verdict["repo_root"] = str(repo_root)
    verdict["active_track_ids"] = ids
    return verdict


def write_receipt(verdict: dict) -> Path:
    out_dir = Path.home() / ".dharma" / "hygiene"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "worktree_budget_receipt.json"
    payload = dict(verdict)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 when over budget")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--receipt", action="store_true",
                        help="write verdict to ~/.dharma/hygiene/")
    args = parser.parse_args()

    v = evaluate_for_repo(args.repo)
    if args.receipt:
        write_receipt(v)
    if args.as_json:
        print(json.dumps(v, indent=2))
    else:
        state = f"OVER BUDGET by {v['over_by']}" if v["over_budget"] else "within budget"
        print(f"worktree-budget: {v['count']}/{v['budget']} ({state})  "
              f"[{v['active_tracks']} active tracks + {v['canonical']} canonical "
              f"+ {v['scratch']} scratch]")
        if v["unmapped"]:
            print(f"  {v['unmapped_count']} tree(s) map to no active track "
                  "(rule: every non-canonical worktree maps to an active track):")
            for w in v["unmapped"][:20]:
                print(f"    - {w['path']}  branch={w['branch'] or '(detached)'}")
            if v["unmapped_count"] > 20:
                print(f"    ... ({v['unmapped_count'] - 20} more)")
    return 1 if (args.strict and v["over_budget"]) else 0


if __name__ == "__main__":
    sys.exit(main())
