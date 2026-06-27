"""Aggressive end-to-end gauntlet for the Thinkodynamic Director remix exemplar.

This is NOT a unit test — it is a hard, full-surface deep-dive that drives the
remix (``ThinkodynamicDirectorRemix``) through *every* prompt family the engine
knows (the eight ``THEME_TEMPLATES``) and exercises the complete public surface
on each one:

    survey -> opportunity model -> plan_workflow -> enqueue -> review
    + self_audit() + verify_invariants() on every single pass
    + one full think_once() cycle (the real engine run loop)
    + a deliberate fault-injection pass to prove fail-closed/witnessed behaviour

The point is to find out *what really survives* when the remix is run hard, and
to prove the Leveson envelope (no silent harm, witnessed failure) holds across
the whole family matrix rather than just the happy path. Run it directly:

    .venv/bin/python tests/_remix/run_remix_gauntlet.py

It exits non-zero if any invariant breaks or any pass is not accounted for, and
overwrites a stable markdown report at
reports/_remix/GAUNTLET_thinkodynamic_director_remix_latest.md.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from dharma_swarm._remix.thinkodynamic_director_remix_v0_0_0_1 import (  # noqa: E402
    InvariantViolation,
    ThinkodynamicDirectorRemix,
)
from dharma_swarm.thinkodynamic_director import (  # noqa: E402
    THEME_TEMPLATES,
    DirectorOpportunity,
    ThinkodynamicDirector,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _build_rich_engine(root: Path) -> ThinkodynamicDirector:
    """Build a real engine over a synthetic repo whose files carry keywords for
    every theme, so the opportunity model is genuinely exercised (not a stub)."""
    repo_root = root / "repo"
    state_dir = root / ".dharma"
    _write(
        repo_root / "docs" / "reports" / "VISION.md",
        "# World Impact Autonomy\n\n"
        "Thinkodynamic director for swarm workflow delegate task board world impact.\n"
        "Research packet, deployment, product, revenue, validation, autonomy.\n"
        "Cybernetics control plane, telos policy, audit pressure, governance.\n"
        "Durable memory retention and context reuse across long-running loops.\n"
        "Ecological restoration, carbon offset, mangrove, biodiversity, jagat kalyan.\n"
        "Service health, retry semantics, observability, reliability, falsify.\n"
        "Monetization, offers, distribution, partnerships, revenue lanes.\n",
    )
    _write(
        repo_root / "dharma_swarm" / "runtime.py",
        "def run():\n"
        "    # TODO: delegate workflow and validate runtime health, autonomy\n"
        "    return 'swarm autonomy cybernetics memory reliability'\n",
    )
    _write(repo_root / "tests" / "test_runtime.py", "def test_runtime():\n    assert True\n")
    return ThinkodynamicDirector(
        repo_root=repo_root,
        state_dir=state_dir,
        scan_roots=("docs", "dharma_swarm", "tests"),
        external_roots=(),
        mission_brief=(
            "Find the highest-leverage workflow for autonomy, cybernetics, "
            "research, infrastructure, monetization, memory, sustainability "
            "impact, and reliability."
        ),
        signal_limit=8,
        max_candidates=24,
        max_active_tasks=64,
    )


def _opportunity_for(theme: str) -> DirectorOpportunity:
    tpl = THEME_TEMPLATES[theme]
    return DirectorOpportunity(
        opportunity_id=f"gauntlet-{theme}-{int(time.time())}",
        theme=theme,
        title=tpl.title,
        thesis=tpl.thesis,
        why_now=tpl.why_now,
        score=10.0,
        expected_duration_min=tpl.expected_duration_min,
        evidence_paths=[],
        role_sequence=list(tpl.roles),
    )


@dataclass
class FamilyResult:
    theme: str
    workflow_id: str = ""
    task_count: int = 0
    enqueued: int = 0
    review_note: str = ""
    audit_passed: bool = False
    invariants_held: bool = False
    error: str = ""
    lines: list[str] = field(default_factory=list)

    @property
    def survived(self) -> bool:
        return (
            not self.error
            and self.task_count > 0
            and self.audit_passed
            and self.invariants_held
        )


async def _drive_family(remix: ThinkodynamicDirectorRemix, theme: str) -> FamilyResult:
    res = FamilyResult(theme=theme)
    try:
        opp = _opportunity_for(theme)
        plan = remix.planner.plan_workflow(opp, cycle_id=f"gauntlet-{theme}")
        res.workflow_id = plan.workflow_id
        res.task_count = len(plan.tasks)
        res.lines.append(
            f"plan {plan.workflow_id}: {len(plan.tasks)} tasks "
            f"[{', '.join(t.key for t in plan.tasks)}]"
        )
        res.lines.append(f"title: {plan.opportunity_title[:70]}")
        steward = sum(len(t.preferred_agents) for t in plan.tasks)
        res.lines.append(
            f"differentiation: steward_agents={steward} "
            f"council_members={len(plan.council_members)} "
            f"roles={[t.role_hint for t in plan.tasks]}"
        )

        tasks = await remix.ledger.enqueue_workflow(plan)
        res.enqueued = len(tasks)
        res.lines.append(f"enqueued {len(tasks)} tasks onto the board")

        review = remix.ledger.review_workflow(plan, tasks)
        res.review_note = review.note or "(no note)"
        res.lines.append(
            f"review active={review.active_count} needs_resynthesis="
            f"{review.needs_resynthesis} blockers={len(review.blockers)}"
        )

        report = remix.self_audit()
        res.audit_passed = report.passed
        if not report.passed:
            res.lines.append(f"AUDIT FAIL: {[c.name for c in report.failures]}")

        remix.verify_invariants()
        res.invariants_held = True
    except InvariantViolation as exc:
        res.error = f"InvariantViolation: {exc}"
    except Exception as exc:  # noqa: BLE001 — gauntlet must report, not crash
        res.error = f"{type(exc).__name__}: {exc}"
        res.lines.append(traceback.format_exc(limit=3))
    return res


class _ExplodingEngine(ThinkodynamicDirector):
    """A real engine that satisfies every capability seam but raises on the hot
    path — to prove the remix fails closed and witnesses, rather than leaking the
    exception. Subclasses the engine so the Protocol seams are genuinely met."""

    def rank_file_signals(self):  # type: ignore[override]
        raise RuntimeError("induced fault: signal ranking unavailable")


async def main() -> int:
    started = datetime.now(timezone.utc)
    work = REPO / "reports" / "_remix" / "_gauntlet_tmp"
    work.mkdir(parents=True, exist_ok=True)

    engine = _build_rich_engine(work)
    # The task board is a durable sqlite owner; initialise its schema before the
    # direct enqueue path drives it (run_cycle does this internally).
    (engine.state_dir / "db").mkdir(parents=True, exist_ok=True)
    await engine._task_board.init_db()
    remix = ThinkodynamicDirectorRemix(engine=engine, strict=True)

    out: list[str] = []

    def emit(line: str = "") -> None:
        out.append(line)
        print(line, flush=True)

    emit("=" * 72)
    emit("THINKODYNAMIC DIRECTOR REMIX — AGGRESSIVE END-TO-END GAUNTLET")
    emit("=" * 72)
    emit(f"started   : {started.isoformat()}")
    emit(f"families  : {len(THEME_TEMPLATES)} -> {sorted(THEME_TEMPLATES)}")
    emit("")

    # --- global survey + construction-time audit -----------------------------
    survey = remix.survey()
    emit(f"survey.ok = {survey.ok}")
    if survey.ok:
        s = survey.unwrap()
        emit(
            f"  signals={len(s.signals)} opportunities={len(s.opportunities)} "
            f"primary={s.primary.theme if s.primary else None} "
            f"ecosystem_keys={len(s.ecosystem)}"
        )
    else:
        emit(f"  survey error: {survey.error}")

    pre_audit = remix.self_audit()
    emit(f"construction self_audit passed = {pre_audit.passed}")
    for c in pre_audit.checks:
        emit(f"  [{'PASS' if c.passed else 'FAIL'}] {c.name}: {c.detail[:90]}")
    emit("")

    # --- per-family deep drive ----------------------------------------------
    results: list[FamilyResult] = []
    for theme in sorted(THEME_TEMPLATES):
        emit(f"--- FAMILY: {theme} " + "-" * (60 - len(theme)))
        res = await _drive_family(remix, theme)
        results.append(res)
        for ln in res.lines:
            emit(f"  {ln}")
        verdict = "SURVIVED" if res.survived else "BROKE"
        emit(f"  => {verdict}  (audit={res.audit_passed} invariants={res.invariants_held}"
             f"{' error=' + res.error if res.error else ''})")
        emit("")

    # --- one full think_once cycle (real engine run loop) --------------------
    emit("--- FULL CYCLE: think_once(delegate=False) " + "-" * 27)
    cycle = await remix.think_once(delegate=False, model="sonnet")
    emit(f"  think_once.ok = {cycle.ok}")
    if cycle.ok:
        payload = cycle.unwrap()
        emit(f"  cycle keys: {sorted(payload)[:10]}")
    else:
        emit(f"  think_once failed-closed (witnessed): {cycle.error[:120]}")
        for inc in cycle.witness:
            emit(f"    witness: where={inc.where} type={inc.error_type} recovered={inc.recovered}")
    emit("")

    # --- deliberate fault injection (fail-closed proof) ----------------------
    emit("--- FAULT INJECTION: exploding engine " + "-" * 32)
    fault_ok = False
    try:
        fault_engine = _build_rich_engine(work / "fault")
        (fault_engine.state_dir / "db").mkdir(parents=True, exist_ok=True)
        await fault_engine._task_board.init_db()
        fault_engine.__class__ = _ExplodingEngine
        fault_remix = ThinkodynamicDirectorRemix(engine=fault_engine, strict=False)
        outcome = fault_remix.survey()
        fault_ok = (not outcome.ok) and bool(outcome.witness)
        emit(f"  survey.ok = {outcome.ok} (expected False)")
        emit(f"  witnessed = {len(outcome.witness)} incident(s); error={outcome.error[:80]}")
        # unwrap() on a failed outcome must fail closed
        try:
            outcome.unwrap()
            emit("  unwrap() did NOT fail closed — BUG")
            fault_ok = False
        except InvariantViolation:
            emit("  unwrap() failed closed as designed (InvariantViolation)")
    except Exception as exc:  # noqa: BLE001
        emit(f"  fault path leaked exception: {type(exc).__name__}: {exc}")
    emit(f"  => fault injection {'HANDLED' if fault_ok else 'NOT HANDLED'}")
    emit("")

    # --- witness ledger ------------------------------------------------------
    emit("--- WITNESS LEDGER " + "-" * 51)
    incidents = remix.witness
    emit(f"  {len(incidents)} incident(s) recorded on the main remix")
    for inc in incidents:
        emit(f"    {inc.when} where={inc.where} type={inc.error_type} recovered={inc.recovered}")
    emit("")

    # --- summary -------------------------------------------------------------
    survived = [r for r in results if r.survived]
    broke = [r for r in results if not r.survived]
    emit("=" * 72)
    emit("SUMMARY")
    emit("=" * 72)
    emit(f"families survived : {len(survived)}/{len(results)}")
    if broke:
        for r in broke:
            emit(f"  BROKE {r.theme}: {r.error or 'see log'}")
    emit(f"think_once         : {'ok' if cycle.ok else 'fail-closed (witnessed)'}")
    emit(f"fault injection    : {'handled' if fault_ok else 'NOT handled'}")
    total_tasks = sum(r.task_count for r in results)
    emit(f"total tasks planned: {total_tasks} across {len(results)} families")

    ok = len(broke) == 0 and fault_ok
    emit("")
    emit(f"GAUNTLET RESULT: {'PASS' if ok else 'FAIL'}")

    # write report (stable filename; overwritten each run so it never accretes)
    report_path = REPO / "reports" / "_remix" / "GAUNTLET_thinkodynamic_director_remix_latest.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "# Remix gauntlet — thinkodynamic_director v0.0.0.1 (latest run)\n\n"
        "Role: report (no runtime authority). "
        "Run: `python tests/_remix/run_remix_gauntlet.py`\n\n"
        "```\n" + "\n".join(out) + "\n```\n",
        encoding="utf-8",
    )
    # The synthetic repo + sqlite scratch is disposable; do not leave it behind.
    shutil.rmtree(work, ignore_errors=True)
    print(f"\nreport written: {report_path.relative_to(REPO)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
