#!/usr/bin/env python3
"""check_claim_evidence_binding.py — report the graded claim/evidence binding.

A THIN CLI over the graded evaluator in check_track_status.py. It does NOT
re-implement evaluate_track; it renders, per active track, the strongest passing
evidence grade vs the required min_evidence_grade and a binding verdict
(BOUND / UNDERGRADED / NOT-SHIPPABLE). This is the operator-facing read of the
Pudgala Autopoiesis Protostar anti-slop bar:

    A claim ships only when its strongest evidence meets the required grade.

Enforcement is STAGE-DRIVEN: by default the gate blocks iff the AI-M1 hygiene
pattern is at stage `enforced` (so an operator promotes advisory->enforced via
scripts/governance/hygiene/promote.py, never the gate auto-escalating). The
flags override the stage: `--warn-only` forces advisory (exit 0), `--enforce`
forces blocking. While AI-M1 is `advisory` the bare gate is advisory, which is
why it is safe to wire into governance-all today.
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

# Import the single owner of the evaluation logic; never re-derive it here.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_track_status import (  # noqa: E402
    ACTIVE_TRACK_PATH,
    evaluate_track,
    grade_name,
    load_active_track,
    normalize_portfolio,
)

# The hygiene pattern whose lifecycle stage drives enforcement (observed ->
# measured -> advisory -> enforced -> resolved). Read fail-safe (see binding_stage).
BINDING_PATTERN_PATH = (
    Path(__file__).resolve().parents[2] / "docs/governance/hygiene/patterns/AI-M1.yaml"
)


def binding_stage(path: Path | None = None) -> str:
    """Read the AI-M1 hygiene pattern's lifecycle stage. FAIL-SAFE: any problem
    (missing/malformed file) returns 'advisory' so the gate never accidentally
    blocks on bad config — escalation must be a deliberate, readable promotion."""
    target = path or BINDING_PATTERN_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return (str(data.get("stage", "advisory")).strip().lower() or "advisory")
    except (OSError, ValueError):
        return "advisory"


def resolve_enforcement(*, enforce_flag: bool, warn_only_flag: bool, stage: str) -> bool:
    """Return True iff the gate should BLOCK (exit non-zero on any UNDERGRADED
    track). Precedence: explicit --warn-only wins (advisory), then explicit
    --enforce (block), else the hygiene stage drives it (block iff 'enforced')."""
    if warn_only_flag:
        return False
    if enforce_flag:
        return True
    return stage == "enforced"


def _git_context(repo_root: Path) -> tuple[str, bool]:
    """Best-effort HEAD sha + dirty flag for the machine receipt (INV-1). Never
    raises — a receipt with empty git context is still valid, just weaker."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root,
            capture_output=True, text=True, timeout=10,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo_root,
            capture_output=True, text=True, timeout=10,
        )
        git_sha = sha.stdout.strip() if sha.returncode == 0 else ""
        git_dirty = bool(status.stdout.strip()) if status.returncode == 0 else False
        return git_sha, git_dirty
    except (OSError, subprocess.SubprocessError):
        return "", False


def _verdict(r: dict) -> str:
    if r["shippable"]:
        return "BOUND"
    if r.get("strongest_grade", 0) < r.get("min_evidence_grade", 2):
        return "UNDERGRADED"
    return "NOT-SHIPPABLE"


def receipt_command_line(
    argv: list[str] | None = None,
    *,
    executable: str | None = None,
) -> str:
    """Return the actual Python command line that produced the receipt."""
    parts = [executable or sys.executable, *(argv if argv is not None else sys.argv)]
    return " ".join(shlex.quote(part) for part in parts)


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--warn-only", action="store_true",
                    help="force advisory (exit 0) regardless of hygiene stage")
    ap.add_argument("--enforce", action="store_true",
                    help="force blocking (exit non-zero if any track UNDERGRADED)")
    ap.add_argument("--emit-receipt", action="store_true",
                    help="append a VerifiedMachineReceipt of this binding run "
                         "to ~/.dharma/witness/claim_evidence_receipts.jsonl")
    args = ap.parse_args(argv)

    stage = binding_stage()
    blocking = resolve_enforcement(
        enforce_flag=args.enforce, warn_only_flag=args.warn_only, stage=stage,
    )

    if not ACTIVE_TRACK_PATH.exists():
        print(f"ERROR: {ACTIVE_TRACK_PATH} not found", file=sys.stderr)
        return 2 if blocking else 0

    portfolio = normalize_portfolio(load_active_track(ACTIVE_TRACK_PATH))
    tracks = portfolio["active_tracks"]
    undergraded = 0

    mode = "ENFORCED (blocking)" if blocking else "advisory"
    print("Claim/Evidence binding (graded anti-slop bar)\n" + "=" * 46)
    print(f"  AI-M1 stage={stage}  mode={mode}")
    for t in tracks:
        if str(t.get("status", "")).upper() not in {"ACTIVE", "SHIPPABLE"}:
            continue
        r = evaluate_track(t)
        verdict = _verdict(r)
        if verdict == "UNDERGRADED":
            undergraded += 1
        sg = grade_name(r.get("strongest_grade", 0))
        mg = grade_name(r.get("min_evidence_grade", 2))
        print(f"  [{verdict:>14}] {t.get('id')}")
        print(f"                   strongest={sg}  required={mg}"
              f"  rigorous={r.get('has_rigorous_evidence')}")
        for blk in r.get("ship_blocks", []):
            print(f"                   - {blk}")

    print("-" * 46)
    print(f"{len(tracks)} active track(s); {undergraded} undergraded "
          f"(below required evidence grade).")

    exit_code = (1 if undergraded else 0) if blocking else 0

    if args.emit_receipt:
        _emit_receipt(undergraded=undergraded, exit_code=exit_code, stage=stage, blocking=blocking)

    return exit_code


def _emit_receipt(*, undergraded: int, exit_code: int, stage: str, blocking: bool) -> None:
    """Append a hash-chained VerifiedMachineReceipt of this binding run. The
    receipt IS the proof the gate ran — verifiable by check_receipt_valid. It
    carries the machine context (command, cwd, git sha/dirty, exit code, INV-1)."""
    try:
        from dharma_swarm.spine.receipt import (
            VerifiedMachineReceipt,
            append_machine_receipt,
        )
        from dharma_swarm.memory_kernel.write_receipts import utc_now
    except ImportError as exc:  # advisory: never crash the gate on a missing dep
        print(f"(receipt skipped: {exc})", file=sys.stderr)
        return
    repo_root = ACTIVE_TRACK_PATH.parent.parent.parent
    git_sha, git_dirty = _git_context(repo_root)
    receipt = VerifiedMachineReceipt(
        claim_id="claim-evidence-binding",
        command=receipt_command_line(),
        cwd=str(repo_root),
        git_sha=git_sha,
        git_dirty=git_dirty,
        actor="make claim-evidence",
        exit_code=exit_code,
        finished_at=utc_now(),
        generated_by="check_claim_evidence_binding.py",
        attributes={"undergraded_tracks": undergraded, "stage": stage, "blocking": blocking},
    )
    chained = append_machine_receipt(receipt)
    print(f"receipt appended (digest {chained.digest[:12]}…, verify={chained.verify()}, "
          f"git_sha={git_sha[:8] or 'n/a'})")


if __name__ == "__main__":
    raise SystemExit(run())
