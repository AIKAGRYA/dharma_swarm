#!/usr/bin/env python3
"""First-fire plumbing cycle — the one composition bit.

Named path: DarwinEngine.apply_diff_and_test on a non-empty diff, in a marked
scratch worktree, toy module only. Planted red (must rollback) then real green
(must keep). Receipt invalid unless both diffs hash and green has applied:true.

Never run on meghadharma-cloud. Never target a live checkout.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_HINTS = ("dharma_swarm", "experiments")
TOY_REL = Path("experiments/first_fire/probe.py")
TEST_REL = Path("experiments/first_fire/test_probe.py")
MARKER_NAME = ".dharma_evolution_worktree.json"
FORBIDDEN_HOSTS = {"meghadharma-cloud"}
ALLOWED_PATHS = {str(TOY_REL)}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _die(msg: str, code: int = 2) -> None:
    print(f"FIRST_FIRE_REFUSED: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def load_grant(path: Path) -> dict:
    data = json.loads(path.read_text())
    required = (
        "grant_id",
        "granted_by",
        "expires_at",
        "max_cycles",
        "allowed_paths",
    )
    missing = [k for k in required if not str(data.get(k, "")).strip()]
    if missing:
        _die(f"grant missing fields: {missing}")
    expires = datetime.fromisoformat(str(data["expires_at"]).replace("Z", "+00:00"))
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        _die(f"grant expired at {data['expires_at']}")
    if int(data["max_cycles"]) < 1:
        _die("grant max_cycles < 1")
    if data.get("consumed_at"):
        _die(f"grant already consumed at {data['consumed_at']}")
    allow = set(data["allowed_paths"])
    if allow != ALLOWED_PATHS:
        _die(f"grant allowed_paths {sorted(allow)} != {sorted(ALLOWED_PATHS)}")
    return data


def consume_grant(path: Path, grant: dict) -> None:
    grant = dict(grant)
    grant["consumed_at"] = _utc()
    path.write_text(json.dumps(grant, indent=2) + "\n")


def refuse_host() -> None:
    host = socket.gethostname()
    if host in FORBIDDEN_HOSTS:
        _die(f"forbidden host {host} (halted box is not the runner)")
    extra = os.environ.get("FIRST_FIRE_FORBIDDEN_HOSTS", "")
    banned = {h.strip() for h in extra.split(",") if h.strip()} | FORBIDDEN_HOSTS
    if host in banned:
        _die(f"forbidden host {host}")


def repo_root_from(start: Path) -> Path:
    cur = start.resolve()
    for _ in range(40):
        if (cur / "dharma_swarm" / "__init__.py").is_file() and (
            cur / "experiments" / "first_fire" / "probe.py"
        ).is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    _die(f"could not find repo root with {TOY_REL} from {start}")


def copy_scratch(src: Path, dest: Path, sha: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns(
            ".venv",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".git",
        ),
        symlinks=False,
    )
    marker = {
        "experiment_id": "first-fire-plumbing",
        "git_base_sha": sha,
        "created_at": _utc(),
        "archive_path": str(dest / ".first_fire_archive.jsonl"),
    }
    (dest / MARKER_NAME).write_text(json.dumps(marker, indent=2) + "\n")


def unified_diff(rel: Path, old: str, new: str) -> str:
    import difflib

    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    if old_lines and not old_lines[-1].endswith("\n"):
        old_lines[-1] += "\n"
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"
    # difflib emits --- a/<path> / +++ b/<path>. parse_unified_diff
    # strips exactly one leading a/ or b/ via _strip_prefix — keep that
    # contract; do not add timestamps (they survive strip and break paths).
    body = "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{rel.as_posix()}",
            tofile=f"b/{rel.as_posix()}",
            lineterm="\n",
        )
    )
    if not body.strip():
        _die("produced empty diff — refuse (empty-diff is a fake pass)")
    return body


def assert_paths(diff_text: str, allowed: set[str]) -> None:
    from dharma_swarm.diff_applier import parse_unified_diff

    patches = parse_unified_diff(diff_text)
    if not patches:
        _die("diff parsed to zero patches")
    for patch in patches:
        if patch.target_path not in allowed:
            _die(f"diff touches {patch.target_path} — not in allowlist {sorted(allowed)}")


def assert_not_live_source(src: Path) -> None:
    if src.resolve() == Path("/root/dharma_swarm").resolve():
        _die("refusing to use /root/dharma_swarm as source workspace for mutation")


def normalize_apply_results(results: dict) -> dict:
    """Read the DarwinEngine.apply_diff_and_test *wrapper* dict.

    Not the raw ApplyTestResult. Two shapes exist today
    (evolution.py:2379 and :2424):

      empty-diff skip → {"pass_rate": 1.0, "skipped": True}
      apply path      → {"pass_rate": float, "rolled_back": bool}

    ``skipped`` is absent on the apply path. ``applied`` is never
    returned — infer apply/rollback from ``rolled_back`` + the file.
    """
    skipped = results.get("skipped") is True
    default_rate = 1.0 if skipped else 0.0
    return {
        "pass_rate": float(results.get("pass_rate", default_rate)),
        "skipped": skipped,
        "rolled_back": results.get("rolled_back") is True,
    }


def red_cycle_ok(results: dict, *, file_restored: bool) -> bool:
    """Planted-red is honest only if tests failed *and* the applier rolled back.

    File-still-original alone is not enough: a refused apply leaves the
    toy untouched and would otherwise look like a successful rollback.
    """
    n = normalize_apply_results(results)
    return (
        not n["skipped"]
        and n["pass_rate"] < 1.0
        and n["rolled_back"]
        and file_restored
    )


def green_cycle_ok(results: dict, *, file_applied: bool) -> bool:
    n = normalize_apply_results(results)
    return (
        not n["skipped"]
        and n["pass_rate"] >= 1.0
        and not n["rolled_back"]
        and file_applied
    )


async def run_apply(workspace: Path, diff_text: str, archive: Path, label: str):
    from dharma_swarm.evolution import DarwinEngine, EvolutionStatus, Proposal

    engine = DarwinEngine(
        archive_path=archive,
        traces_path=workspace / ".first_fire_traces",
        predictor_path=workspace / ".first_fire_predictor.jsonl",
        archive_enforce_one_wire=False,
    )
    proposal = Proposal(
        component=str(TOY_REL),
        change_type="mutation",
        description=f"first-fire {label}",
        diff=diff_text,
        status=EvolutionStatus.TESTING,
        experiment_id="first-fire-plumbing",
    )
    _proposal, _results = await engine.apply_diff_and_test(
        proposal,
        test_command="python3 -m pytest experiments/first_fire/test_probe.py -q --tb=short",
        timeout=90.0,
        workspace=workspace,
    )
    return _proposal, normalize_apply_results(_results)


def git_sha(repo: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
    except Exception:
        return "unknown"


async def main_async(args: argparse.Namespace) -> int:
    refuse_host()
    grant_path = Path(args.grant).expanduser().resolve()
    grant = load_grant(grant_path)

    src = repo_root_from(Path(args.repo_root).resolve() if args.repo_root else Path.cwd())
    sha = git_sha(src)

    # Scratch must sit under an evolution_worktrees root (see evolution_safety.py).
    root = Path(
        os.environ.get(
            "DHARMA_EVOLUTION_WORKTREE_ROOT",
            str(Path.home() / ".dharma" / "evolution_worktrees"),
        )
    ).expanduser().resolve()
    scratch = root / f"first-fire-{grant['grant_id']}"
    assert_not_live_source(src)

    copy_scratch(src, scratch, sha)
    os.environ["DHARMA_EVOLUTION_WORKTREE_ROOT"] = str(root)

    probe = scratch / TOY_REL
    original = probe.read_text()
    if "return 1" not in original:
        _die("toy probe does not contain 'return 1' — refuse to guess")

    red_src = original.replace("return 1", 'return "red"', 1)
    green_src = original.replace("return 1", "return 2", 1)
    red_diff = unified_diff(TOY_REL, original, red_src)
    green_diff = unified_diff(TOY_REL, original, green_src)
    assert_paths(red_diff, ALLOWED_PATHS)
    assert_paths(green_diff, ALLOWED_PATHS)

    # Pair starts here. Consume only after the scratch and diffs exist so a
    # failed copy does not burn the one-shot grant.
    consume_grant(grant_path, grant)

    archive = scratch / ".first_fire_archive.jsonl"
    red_proposal, red_results = await run_apply(scratch, red_diff, archive, "planted-red")
    after_red = probe.read_text()
    red_rolled = after_red == original
    red_ok = red_cycle_ok(red_results, file_restored=red_rolled)

    green_proposal, green_results = await run_apply(
        scratch, green_diff, archive, "real-green"
    )
    after_green = probe.read_text()
    green_applied = "return 2" in after_green and after_green != original
    green_ok = green_cycle_ok(green_results, file_applied=green_applied)

    receipt = {
        "schema": "dharma.first_fire.plumbing.v1",
        "ts": _utc(),
        "grant_id": grant["grant_id"],
        "granted_by": grant["granted_by"],
        "named_function": "DarwinEngine.apply_diff_and_test",
        "host": socket.gethostname(),
        "git_base_sha": sha,
        "scratch": str(scratch),
        "allowed_paths": sorted(ALLOWED_PATHS),
        "red": {
            "diff_sha256": _sha256(red_diff),
            "pass_rate": red_results.get("pass_rate"),
            "skipped": red_results.get("skipped", False),
            "rolled_back": red_results.get("rolled_back", False),
            "file_restored": red_rolled,
            "ok": red_ok,
        },
        "green": {
            "diff_sha256": _sha256(green_diff),
            "pass_rate": green_results.get("pass_rate"),
            "skipped": green_results.get("skipped", False),
            "rolled_back": green_results.get("rolled_back", False),
            "applied": green_applied,
            "ok": green_ok,
        },
        "valid": bool(red_ok and green_ok),
        "note": (
            "valid only if planted-red rolled back AND green applied:true "
            "with a non-empty diff hash. This is a plumbing receipt, not DGM."
        ),
    }
    out = Path(args.receipt).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    if not receipt["valid"]:
        _die("receipt invalid — composition bit not purchased", code=1)
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--grant", required=True, help="path to dated one-shot GRANT.json")
    p.add_argument("--repo-root", default=None)
    p.add_argument(
        "--receipt",
        default=str(Path.home() / ".dharma" / "first_fire" / "last_receipt.json"),
    )
    args = p.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
