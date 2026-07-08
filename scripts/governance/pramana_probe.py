#!/usr/bin/env python3
"""pramana_probe.py — the tiered verification CONDUCTOR (self-improvement loop, slice 1).

Composes the repo's modular quality engines (ruff, mypy, pytest, cargo clippy,
hygiene, verify-corral, ...) into ONE evidence-tiered epistemic verdict. Each
gate is mapped to a *pramana* (a means of valid knowledge) and the per-gate
results are aggregated through ``dharma_swarm.pramana`` — the existing epistemic
SSOT — so we reuse its weighting and its arthapatti-is-BLOCKING semantics rather
than forking a second scheme.

Design doctrine (inherited from the reconciliation lane):
    Read models PROJECT truth from owners; they do not become authority.
This conductor owns no truth. It runs the engines, reads their exit status,
maps each to a pramana, and emits a CompositeValidation + a receipt. The
engines and the tests remain the owners; welding happens at the JUDGMENT layer,
never at the engine layer (engines stay modular and independently runnable).

Why this is the keystone of "close the self-improvement loop": unattended
self-improvement is only safe if every candidate change is gated by trustworthy,
multi-pramana verification with a hard blocking floor. This is that gate.

Tiers (escalating cost; deeper tiers include the cheaper ones):
    fast    every change   — pratyaksha (scoped tests), anumana (ruff; clippy
                             when the native crate is present), upamana
                             (reference vectors, when present)
    medium  pre-commit     — agama (hygiene, module-budget, verify-corral, trust)
    deep    pre-PR/period  — arthapatti (invariant/property/adversarial) — BLOCKING

Registry integrity (post the 2026-07-04 phantom-gate audit): every path a
default gate depends on is declared in ``GateSpec.requires`` and asserted to
exist by ``validate_gates()`` before anything runs. A gate pointing at a
nonexistent target is a CONFIG ERROR (exit 3), never a silent instant failure
that masquerades as a REFUTED code verdict.

The pure core (GateSpec -> PramanaResult -> CompositeValidation -> tier) has no
I/O and is unit-tested with an injected runner; the subprocess shell is a thin
edge. CLI: ``python3 scripts/governance/pramana_probe.py --tier fast --json``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.pramana import (  # noqa: E402
    CompositeValidation,
    PramanaResult,
    PramanaValidator,
)

# The five pramanas, ordered cheap -> dear. arthapatti is the BLOCKING floor.
PRATYAKSHA = "pratyaksha"  # direct perception: tests, runtime observation
ANUMANA = "anumana"        # inference from signs: static analysis, types
UPAMANA = "upamana"        # comparison to a standard: golden/reference vectors
AGAMA = "agama"            # trusted testimony: signatures, hygiene, governance
ARTHAPATTI = "arthapatti"  # postulation (what MUST hold): invariants/adversarial

TIERS = ("fast", "medium", "deep")
_TIER_RANK = {"fast": 0, "medium": 1, "deep": 2}

# Evidence-tier verdict vocabulary (aligned with the repo's semantic-receipt
# verdicts: verified / supported / weak / refuted).
VERIFIED = "VERIFIED"
SUPPORTED = "SUPPORTED"
WEAK = "WEAK"
REFUTED = "REFUTED"


@dataclass(frozen=True)
class GateSpec:
    """One verification engine to run, and the pramana it provides evidence for."""

    name: str
    mode: str          # one of the five pramanas
    tier: str          # fast | medium | deep
    argv: Sequence[str]
    cwd: Path | None = None
    # If True, a failure of THIS gate cannot be outweighed (true blocking).
    blocking: bool = False
    # Repo-relative paths this gate targets. validate_gates() asserts each
    # exists BEFORE anything runs, so a phantom target is a config error
    # rather than an instant gate failure that reads as a code verdict.
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateOutcome:
    """The result of running one gate (pure data; no I/O)."""

    name: str
    mode: str
    tier: str
    ok: bool
    exit_code: int
    duration_ms: int
    blocking: bool
    detail: str = ""


# --------------------------------------------------------------------------- #
# Pure core — no I/O, fully unit-testable                                      #
# --------------------------------------------------------------------------- #


def gate_to_pramana(outcome: GateOutcome) -> PramanaResult:
    """Project one gate outcome onto a PramanaResult.

    A passing gate contributes full confidence for its pramana; a failing gate
    contributes a failed result. arthapatti gates carry the blocking semantics
    that ``dharma_swarm.pramana`` already honours (any failed arthapatti ->
    composite fails with score 0).
    """
    return PramanaResult(
        mode=outcome.mode,
        passed=outcome.ok,
        confidence=1.0 if outcome.ok else 0.0,
        claim=f"gate:{outcome.name}",
        evidence=(
            f"{outcome.name} exit={outcome.exit_code} "
            f"({outcome.duration_ms}ms){' [blocking]' if outcome.blocking else ''}"
        ),
        details={
            "tier": outcome.tier,
            "exit_code": outcome.exit_code,
            "duration_ms": outcome.duration_ms,
            "blocking": outcome.blocking,
            "detail": outcome.detail[:500],
        },
    )


def aggregate(outcomes: Sequence[GateOutcome], *, claim: str = "pramana_probe") -> CompositeValidation:
    """Aggregate gate outcomes via the pramana SSOT.

    A failed *blocking* gate is mapped to a failed arthapatti result so the
    existing composite logic (arthapatti fail -> overall fail, score 0) enforces
    the hard floor — we do not re-implement the blocking algebra.
    """
    results: list[PramanaResult] = []
    for o in outcomes:
        pr = gate_to_pramana(o)
        if o.blocking and not o.ok:
            # Force the blocking floor through the engine's own arthapatti rule.
            pr = PramanaResult(
                mode=ARTHAPATTI,
                passed=False,
                confidence=0.0,
                claim=pr.claim,
                evidence=pr.evidence + " [forced-blocking]",
                details=pr.details,
            )
        results.append(pr)
    return PramanaValidator().validate_composite(claim, results=results)


def evidence_tier(composite: CompositeValidation) -> str:
    """Map a CompositeValidation to a single evidence-tier verdict.

    REFUTED is reserved for a breached BLOCKING floor (a failed arthapatti /
    forced-blocking gate) or a total absence of supporting evidence (score 0).
    A non-blocking gate failure DEGRADES the tier (VERIFIED -> SUPPORTED ->
    WEAK) rather than refuting — the distinction the self-improvement loop needs
    so a lint nit is not mistaken for an invariant breach.
    """
    if composite.blocking_failures:
        return REFUTED
    score = composite.overall_score
    if score >= 0.9:
        return VERIFIED
    if score >= 0.7:
        return SUPPORTED
    if score > 0.0:
        return WEAK
    return REFUTED  # nothing passed and no floor to point at => refuted


def select_gates(gates: Iterable[GateSpec], tier: str) -> list[GateSpec]:
    """Gates at or below the requested tier (deeper tiers include cheaper ones)."""
    if tier not in _TIER_RANK:
        raise ValueError(f"unknown tier {tier!r}; expected one of {TIERS}")
    ceiling = _TIER_RANK[tier]
    return [g for g in gates if _TIER_RANK[g.tier] <= ceiling]


def validate_gates(gates: Iterable[GateSpec], root: Path | None = None) -> list[str]:
    """Assert every gate's declared targets exist. Returns config errors.

    A phantom gate (one whose ``requires`` path or ``cwd`` is missing) must be
    a DISTINCT config error, not a REFUTED verdict: on 2026-07-04 the registry
    shipped three gates pointing at files that existed only on a review branch,
    and the probe reported REFUTED 0.0 on main for reasons that had nothing to
    do with code truth. Callers must refuse to run when this returns errors.
    """
    base = root if root is not None else REPO_ROOT
    errors: list[str] = []
    for g in gates:
        if g.cwd is not None and not g.cwd.is_dir():
            errors.append(f"gate {g.name!r}: cwd does not exist: {g.cwd}")
        for req in g.requires:
            if not (base / req).exists():
                errors.append(f"gate {g.name!r}: required target does not exist: {req}")
    return errors


# --------------------------------------------------------------------------- #
# I/O shell — thin; the runner is injectable so the core stays pure            #
# --------------------------------------------------------------------------- #

# A runner maps (argv, cwd) -> (exit_code, duration_ms, detail).
Runner = Callable[[Sequence[str], "Path | None"], "tuple[int, int, str]"]


def subprocess_runner(argv: Sequence[str], cwd: Path | None) -> tuple[int, int, str]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            list(argv), cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=900,
        )
        dur = int((time.monotonic() - started) * 1000)
        tail = (proc.stdout or "")[-400:] + (proc.stderr or "")[-400:]
        return proc.returncode, dur, tail.strip()
    except FileNotFoundError as exc:
        dur = int((time.monotonic() - started) * 1000)
        return 127, dur, f"gate binary not found: {exc}"
    except subprocess.TimeoutExpired:
        dur = int((time.monotonic() - started) * 1000)
        return 124, dur, "gate timed out"


def run_gate(spec: GateSpec, runner: Runner) -> GateOutcome:
    code, dur, detail = runner(spec.argv, spec.cwd)
    return GateOutcome(
        name=spec.name, mode=spec.mode, tier=spec.tier, ok=(code == 0),
        exit_code=code, duration_ms=dur, blocking=spec.blocking, detail=detail,
    )


@dataclass
class ProbeReport:
    tier: str
    verdict: str
    blocking_floor_held: bool   # no arthapatti/blocking gate failed (the safety floor)
    all_gates_passed: bool      # every gate, blocking or not, exited 0 (CI signal)
    overall_score: float
    outcomes: list[GateOutcome] = field(default_factory=list)
    blocking_failures: list[str] = field(default_factory=list)

    def to_receipt(self) -> dict:
        return {
            "schema": "dharma.pramana_probe.receipt.v1",
            "kind": "verification_projection",
            "note": "projection over modular engines; owns no truth",
            "tier": self.tier,
            "verdict": self.verdict,
            "blocking_floor_held": self.blocking_floor_held,
            "all_gates_passed": self.all_gates_passed,
            "overall_score": round(self.overall_score, 4),
            "blocking_failures": self.blocking_failures,
            "gates": [
                {
                    "name": o.name, "pramana": o.mode, "tier": o.tier,
                    "ok": o.ok, "exit_code": o.exit_code,
                    "duration_ms": o.duration_ms, "blocking": o.blocking,
                }
                for o in self.outcomes
            ],
        }


def run_probe(gates: Sequence[GateSpec], *, tier: str, runner: Runner) -> ProbeReport:
    selected = select_gates(gates, tier)
    outcomes = [run_gate(g, runner) for g in selected]
    composite = aggregate(outcomes)
    return ProbeReport(
        tier=tier,
        verdict=evidence_tier(composite),
        blocking_floor_held=composite.overall_passed,
        all_gates_passed=all(o.ok for o in outcomes),
        overall_score=composite.overall_score,
        outcomes=outcomes,
        blocking_failures=list(composite.blocking_failures),
    )


# --------------------------------------------------------------------------- #
# Default gate registry — real, runnable engines (extensible: it's just data)  #
# --------------------------------------------------------------------------- #

_NATIVE_CRATE = REPO_ROOT / "native" / "dharma_kernels"


def default_gates(target: str = "dharma_swarm/") -> list[GateSpec]:
    """A representative, runnable gate set. `target` scopes the path-based gates.

    Registry rules (2026-07-04 phantom-gate fix):
    - Every path a gate depends on is declared in ``requires`` so
      ``validate_gates()`` can refuse to run a phantom registry.
    - The native-crate gates (cargo test/clippy) are existence-GUARDED: the
      crate is deferred work absent on main (A2A_LOCAL_RECONCILIATION_HANDOFF),
      so they join the registry only on checkouts that actually have it.
    - mypy was dropped: it is not installed in the repo venv or CI, so the old
      gate exited in ~36ms having verified nothing. Re-add it together with the
      dependency, or not at all.
    """
    gates = [
        # fast — pratyaksha (direct perception: scoped tests actually executed;
        # the highest-weighted pramana previously had NO gate at all)
        GateSpec("pytest-scoped", PRATYAKSHA, "fast",
                 ["python3", "-m", "pytest",
                  "tests/test_pramana.py", "tests/test_pramana_probe.py", "-q"],
                 requires=("tests/test_pramana.py", "tests/test_pramana_probe.py")),
        # fast — anumana (inference from static signs)
        GateSpec("ruff", ANUMANA, "fast",
                 ["ruff", "check", target, "--select=E,F,W", "--ignore=E501"],
                 requires=(target,)),
        # medium — agama (trusted testimony: governance/hygiene owners)
        GateSpec("hygiene-check", AGAMA, "medium",
                 ["python3", "scripts/governance/hygiene/check_hygiene_integrity.py"],
                 requires=("scripts/governance/hygiene/check_hygiene_integrity.py",)),
        GateSpec("module-budget", AGAMA, "medium",
                 ["python3", "scripts/governance/check_module_budget.py",
                  "--base-ref", "origin/main", "--head-ref", "HEAD"],
                 requires=("scripts/governance/check_module_budget.py",)),
        GateSpec("verify-corral", AGAMA, "medium",
                 ["python3", "scripts/governance/verify_corral_findings.py"],
                 requires=("scripts/governance/verify_corral_findings.py",)),
        # deep — anumana (inference from measured signs): the Stop-the-Slop
        # probe (docs/stop-the-slop/probe, 13 instrument-routed signals) as a
        # delta-ratchet against the committed baseline. New regressions fail;
        # pre-existing findings and LOW/UNASSESSED axes stay advisory.
        GateSpec("slop-ratchet", ANUMANA, "deep",
                 ["python3", "scripts/governance/slop_ratchet.py"],
                 requires=("scripts/governance/slop_ratchet.py",
                           "docs/stop-the-slop/probe/probe.py",
                           "docs/governance/hygiene/slop_index_baseline.json")),
        # deep — arthapatti (what MUST hold): the computable invariants plus
        # the NATS substrate contract — both real on main, both fast (<1s).
        # BLOCKING: a failure here cannot be outweighed by any amount of green.
        GateSpec("invariant-tests", ARTHAPATTI, "deep",
                 ["python3", "-m", "pytest",
                  "tests/test_invariants.py", "tests/test_nats_substrate_contract.py", "-q"],
                 blocking=True,
                 requires=("tests/test_invariants.py", "tests/test_nats_substrate_contract.py")),
    ]
    if (_NATIVE_CRATE / "Cargo.toml").is_file():
        gates.extend([
            # fast — upamana (comparison to a frozen reference): native vectors
            GateSpec("cargo-test", UPAMANA, "fast",
                     ["cargo", "test", "--release", "--quiet"], cwd=_NATIVE_CRATE),
            GateSpec("cargo-clippy", ANUMANA, "fast",
                     ["cargo", "clippy", "--release", "--all-targets", "--", "-D", "warnings"],
                     cwd=_NATIVE_CRATE),
        ])
    return gates


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Tiered pramana verification conductor")
    p.add_argument("--tier", choices=TIERS, default="fast")
    p.add_argument("--target", default="dharma_swarm/", help="path scope for path-based gates")
    p.add_argument("--json", action="store_true", help="emit the receipt as JSON")
    p.add_argument("--receipt", default=None, help="also write the receipt to this path")
    args = p.parse_args(argv)

    gates = default_gates(args.target)
    config_errors = validate_gates(gates)
    if config_errors:
        for err in config_errors:
            print(f"PRAMANA PROBE CONFIG ERROR: {err}", file=sys.stderr)
        print("refusing to run: a phantom gate is a config error, not a verdict",
              file=sys.stderr)
        return 3

    report = run_probe(gates, tier=args.tier, runner=subprocess_runner)
    receipt = report.to_receipt()

    if args.receipt:
        Path(args.receipt).expanduser().parent.mkdir(parents=True, exist_ok=True)
        Path(args.receipt).expanduser().write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(receipt, indent=2))
    else:
        print(f"PRAMANA PROBE [{args.tier}] -> {report.verdict}  "
              f"(score={report.overall_score:.3f}, all_gates_passed={report.all_gates_passed}, "
              f"blocking_floor_held={report.blocking_floor_held})")
        for o in report.outcomes:
            mark = "ok " if o.ok else "FAIL"
            blk = " BLOCKING" if o.blocking else ""
            print(f"  [{mark}] {o.mode:<11} {o.name:<16} exit={o.exit_code} {o.duration_ms}ms{blk}")
        if report.blocking_failures:
            print(f"  blocking failures: {report.blocking_failures}")

    # CI semantics: 0 only when every gate passed (the verdict label still
    # carries the nuanced tier for humans); 1 = at least one gate failed;
    # 3 = phantom registry (config error — nothing ran, no verdict exists).
    return 0 if report.all_gates_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
