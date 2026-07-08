"""Arena v1 runner (spec §3) — the keystone.

Two layers with a hard boundary:
  * (A) Scorer — frozen, hermetic, replayable; the SOLE correctness authority.
  * (B) Task curator — evolving/world-fed; STUBBED here (``curator.py``), it may
    expand freely but can never mutate the frozen slice mid-epoch.

Runs a candidate ``OrchestrationGenome`` against three controls, enforcing and
logging BUDGET PARITY, and decides one closeout state. Success is the falsifiable
existence test: a genome is ``positive_lift_candidate`` ONLY if it beats
``best_single_full_budget`` at EQUAL total compute, with significance.

Hermetic by default: worker responses come from the recorded ``FixturePool``.
The deterministic scorer judges correctness; the Council only verifies trace
integrity / contamination / the "beat controls" claim — never correctness.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dharma_swarm.coordination.arena.fixtures import (
    ROSTER_REGISTRY,
    FixturePool,
    ModelSpec,
)
from dharma_swarm.coordination.arena.scorer import (
    score_submission,
    scorecard_hash,
    scorer_hash,
)
from dharma_swarm.coordination.arena.taskpack import Taskpack, normalize_answer
from dharma_swarm.coordination.dpi import DPIInputs, compute_dpi
from dharma_swarm.coordination.genome import OrchestrationGenome
from dharma_swarm.council import Council, TraceVerificationRequest

CLOSEOUT_STATES = (
    "positive_lift_candidate",
    "measured_negative",
    "inconclusive_low_power",
    "contaminated_quarantine",
    "blocked_with_evidence",
)

# Permission token a contaminated candidate would request; if present the runner
# actually reads sealed labels during execution, tripping the anti-contamination
# tripwire (used to prove the boundary holds).
READ_SEALED_PERMISSION = "read_sealed_labels"

_BOOTSTRAP_SEED = 1337
_BOOTSTRAP_ITERS = 2000
_SIGNIFICANCE_P = 0.05


@dataclass
class ArmResult:
    arm: str
    submission: dict[str, str]
    scorecard: dict[str, Any]
    total_compute: int
    route_receipts: list[dict[str, Any]] = field(default_factory=list)
    trace_receipts: list[dict[str, Any]] = field(default_factory=list)
    sealed_access_during_run: int = 0
    # Provenance: which single model produced this arm (single-seat arms only).
    model_id: str = ""

    @property
    def score(self) -> float:
        return float(self.scorecard["score"])

    def correctness_vector(self, task_ids: list[str]) -> list[int]:
        per = self.scorecard["per_task"]
        return [1 if per.get(t) else 0 for t in task_ids]


class ArenaRunner:
    """Runs candidate + controls on the frozen taskpack and decides a closeout."""

    def __init__(
        self,
        taskpack: Optional[Taskpack] = None,
        pool: Optional[FixturePool] = None,
        council: Optional[Council] = None,
        roster: Optional[dict[str, ModelSpec]] = None,
    ) -> None:
        self.taskpack = taskpack or Taskpack()
        self.pool = pool or FixturePool()
        self.council = council or Council()
        # The configured seat registry. Defaults to the hermetic fixture roster;
        # a live measurement passes its own (public capability metadata only —
        # never sealed labels).
        self.roster: dict[str, ModelSpec] = dict(roster) if roster else dict(ROSTER_REGISTRY)

    def model_ids(self) -> tuple[str, ...]:
        return tuple(self.roster)

    # ------------------------------------------------------------ genome execution
    def _select_models(self, genome: OrchestrationGenome, family: str) -> list[str]:
        """Per-task model selection from the genome's adjudication rule + roster."""
        roster = [m.member_id for m in genome.roster]
        if not roster:
            return []
        rule = genome.adjudication_rule
        if rule == "single":
            return [roster[0]]
        if rule in ("vote", "debate", "moat-gate"):
            return roster
        # synthesize == route each task to the roster member whose PUBLIC specialty
        # matches the task family (skill selection); fall back to the first member.
        for member_id in roster:
            spec = self.roster.get(member_id)
            if spec and spec.specialty == family:
                return [member_id]
        return [roster[0]]

    def _aggregate(self, rule: str, answers: list[str]) -> str:
        if not answers:
            return ""
        if len(answers) == 1 or rule in ("single", "synthesize"):
            return answers[0]
        # vote / debate / moat-gate -> normalized majority, ties -> first answer.
        counts = Counter(normalize_answer(a) for a in answers)
        top = counts.most_common()
        best_norm, best_n = top[0]
        if sum(1 for _, n in top if n == best_n) > 1:
            return answers[0]
        for a in answers:
            if normalize_answer(a) == best_norm:
                return a
        return answers[0]

    def run_arm(self, arm: str, genome: OrchestrationGenome) -> ArmResult:
        """Execute one genome arm hermetically; record route + trace receipts."""
        rule = genome.adjudication_rule
        sealed_before = len(self.taskpack.sealed_access_log)
        # A contaminated candidate that requested sealed access actually reads it
        # here — tripping the tripwire so the boundary is provable, not assumed.
        contaminated_roles = [
            m.role_id
            for m in genome.roster
            if READ_SEALED_PERMISSION in genome.permissions.get(m.role_id, [])
        ]

        submission: dict[str, str] = {}
        route_receipts: list[dict[str, Any]] = []
        trace_receipts: list[dict[str, Any]] = []
        total_compute = 0
        for task_id in self.taskpack.task_ids():
            family = self.taskpack.family_of(task_id)
            selected = self._select_models(genome, family)
            answers: list[str] = []
            cost = 0
            for model_id in selected:
                if contaminated_roles:
                    # Simulated cheat: peek the sealed label (records on the log).
                    self.taskpack.sealed_label(task_id)
                resp = self.pool.dispatch(model_id, task_id)
                answers.append(resp.answer)
                cost += resp.cost
            aggregated = self._aggregate(rule, answers)
            submission[task_id] = aggregated
            total_compute += cost
            route_receipts.append(
                {
                    "genome_id": genome.genome_id,
                    "arm": arm,
                    "task_id": task_id,
                    "family": family,
                    "selected_models": selected,
                    "cost": cost,
                }
            )
            trace_receipts.append(
                {
                    "genome_id": genome.genome_id,
                    "arm": arm,
                    "task_id": task_id,
                    "answers": dict(zip(selected, answers)),
                    "aggregated_answer": aggregated,
                }
            )
        sealed_access = len(self.taskpack.sealed_access_log) - sealed_before
        scorecard = score_submission(self.taskpack, submission, arm=arm)
        # Tie the scorecard to its genome so the Council can verify the scorer
        # evidence belongs to THIS genome (not a borrowed/forged scorecard).
        scorecard["genome_id"] = genome.genome_id
        return ArmResult(
            arm=arm,
            submission=submission,
            scorecard=scorecard,
            total_compute=total_compute,
            route_receipts=route_receipts,
            trace_receipts=trace_receipts,
            sealed_access_during_run=sealed_access,
        )

    # ------------------------------------------------------------------- controls
    def _best_single_full_budget(self) -> tuple[ArmResult, dict[str, dict[str, Any]]]:
        """The GATE: the single best model run once on every task at full budget.

        Also returns every seat's scorecard from the sweep (``seat_scorecards``)
        so downstream diagnosis (Krogh-Vedelsby diversity term, cross-seat error
        correlation) can be computed from receipts without extra dispatches.
        Seat correctness comes from the scorer path only — the sole label reader.
        """
        best: Optional[ArmResult] = None
        best_model = ""
        seat_scorecards: dict[str, dict[str, Any]] = {}
        for model_id in self.model_ids():
            single = OrchestrationGenome(
                roster=[{"role_id": model_id, "member_id": model_id, "kind": "model"}],
                adjudication_rule="single",
            )
            result = self.run_arm("best_single_full_budget", single)
            seat_scorecards[model_id] = result.scorecard
            # tie-break: higher score, then lower compute, then model name
            if best is None or (result.score, -result.total_compute, model_id) > (
                best.score,
                -best.total_compute,
                best_model,
            ):
                best, best_model = result, model_id
        assert best is not None
        best.model_id = best_model
        best.submission["_model"] = best_model  # provenance breadcrumb (compat)
        return best, seat_scorecards

    def _same_budget_self_moa(self, budget: int, best_model: str) -> ArmResult:
        """Best single model doing internal MoA within the SAME budget cap.

        With a deterministic fixture pool, resampling the same model yields the
        same answers, so self-MoA cannot exceed the single model — it just spends
        the budget. Capped so it never exceeds parity. ``best_model`` is the gate
        sweep's winner (single source of truth for "strongest seat").
        """
        genome = OrchestrationGenome(
            roster=[{"role_id": best_model, "member_id": best_model, "kind": "model"}],
            adjudication_rule="single",
        )
        result = self.run_arm("same_budget_self_moa", genome)
        result.model_id = best_model
        result.total_compute = min(result.total_compute, budget)
        return result

    def _random_or_static_ensemble(self) -> ArmResult:
        """Static ensemble: all roster models vote on every task (brute force)."""
        genome = OrchestrationGenome(
            roster=[
                {"role_id": m, "member_id": m, "kind": "model"} for m in self.model_ids()
            ],
            adjudication_rule="vote",
        )
        return self.run_arm("random_or_static_ensemble", genome)

    def _best_single_parity_budget(
        self, gate: ArmResult, cand: ArmResult
    ) -> tuple[ArmResult, dict[str, Any]]:
        """THE budget-parity control (kill-list doctrine): the single strongest
        seat re-runs the IDENTICAL frozen taskpack at the candidate's exact call
        budget.

        "Equal token/call budget to the whole swarm arm" is enforced as:
          (a) exactly the candidate's per-task call count, and
          (b) the same per-call token cap — one pool instance serves every arm,
              so the cap cannot silently differ between arms.
        Extra calls aggregate by normalized majority (self-consistency), ties ->
        first sample — the same fan-in rule the swarm's vote path uses, so
        neither arm gets a smarter aggregator.

        Parity is INSTRUMENTED (the returned ledger is externally auditable) and
        ASSERTED: any mismatch fails the run closed via ``_select_closeout``
        (``blocked_with_evidence``) — it can never degrade into a win.
        """
        control_model = gate.model_id or gate.submission.get("_model", "")
        calls_by_task = {
            r["task_id"]: max(1, len(r["selected_models"]))
            for r in cand.route_receipts
        }
        findings: list[str] = []
        submission: dict[str, str] = {}
        route_receipts: list[dict[str, Any]] = []
        trace_receipts: list[dict[str, Any]] = []
        control_calls_by_task: dict[str, int] = {}
        total_compute = 0
        genome_label = f"parity-control-{control_model or 'unresolved'}"
        if control_model:
            for task_id in self.taskpack.task_ids():
                k = calls_by_task.get(task_id, 1)
                answers: list[str] = []
                cost = 0
                for _ in range(k):
                    resp = self.pool.dispatch(control_model, task_id)
                    answers.append(resp.answer)
                    cost += resp.cost
                control_calls_by_task[task_id] = len(answers)
                aggregated = self._aggregate("vote", answers)
                submission[task_id] = aggregated
                total_compute += cost
                route_receipts.append(
                    {
                        "genome_id": genome_label,
                        "arm": "best_single_parity_budget",
                        "task_id": task_id,
                        "family": self.taskpack.family_of(task_id),
                        "selected_models": [control_model] * len(answers),
                        "cost": cost,
                    }
                )
                trace_receipts.append(
                    {
                        "genome_id": genome_label,
                        "arm": "best_single_parity_budget",
                        "task_id": task_id,
                        "answers": {control_model: answers[0] if answers else ""},
                        "aggregated_answer": aggregated,
                    }
                )
        else:
            findings.append("no_control_model_resolved")
        scorecard = score_submission(
            self.taskpack, submission, arm="best_single_parity_budget"
        )
        scorecard["genome_id"] = genome_label
        result = ArmResult(
            arm="best_single_parity_budget",
            submission=submission,
            scorecard=scorecard,
            total_compute=total_compute,
            route_receipts=route_receipts,
            trace_receipts=trace_receipts,
            model_id=control_model,
        )
        calls_match = bool(control_model) and control_calls_by_task == {
            t: calls_by_task.get(t, 1) for t in self.taskpack.task_ids()
        }
        if control_model and not calls_match:
            findings.append("call_budget_mismatch")
        parity_report = {
            "control_model": control_model,
            "candidate_total_calls": sum(
                calls_by_task.get(t, 1) for t in self.taskpack.task_ids()
            ),
            "control_total_calls": sum(control_calls_by_task.values()),
            "calls_per_task_match": calls_match,
            "per_call_cap": getattr(self.pool, "per_call_cap", None),
            "per_call_cap_shared_across_arms": True,  # one pool serves every arm
            "verified": calls_match,
            "findings": findings,
        }
        return result, parity_report

    # ----------------------------------------------------------------- statistics
    @staticmethod
    def _bootstrap_significance(cand: list[int], base: list[int]) -> dict[str, Any]:
        """Seeded paired bootstrap on per-task correctness. Deterministic/replayable.

        WHY a paired bootstrap rather than a t-interval: the per-task paired
        differences are bounded in {-1, 0, 1} and the frozen pack is small
        (n=24), so the t-interval's normality assumption is not defensible;
        the percentile bootstrap is distribution-free, needs no dependency, and
        is exactly replayable with the seeded RNG (§6 replay invariant). The
        p-value and the 95% CI are computed from the SAME resample stream so a
        replayed run can never disagree with itself.

        The scorecard/report layer must always render ``ci95_lift`` alongside
        ``observed_lift`` — a point estimate alone is forbidden.
        """
        n = len(cand)
        diffs = [c - b for c, b in zip(cand, base)]
        observed = sum(diffs) / n if n else 0.0
        if n == 0:
            return {
                "observed_lift": 0.0,
                "p_value": 1.0,
                "significant": False,
                "n": 0,
                "ci95_lift": [0.0, 0.0],
                "method": "paired_seeded_bootstrap_percentile",
                "iterations": 0,
            }
        rng = random.Random(_BOOTSTRAP_SEED)
        means: list[float] = []
        worse_or_equal = 0
        for _ in range(_BOOTSTRAP_ITERS):
            resampled = sum(diffs[rng.randrange(n)] for _ in range(n)) / n
            means.append(resampled)
            if resampled <= 0:
                worse_or_equal += 1
        p_value = worse_or_equal / _BOOTSTRAP_ITERS
        means.sort()
        lo = means[int(0.025 * (_BOOTSTRAP_ITERS - 1))]
        hi = means[int(0.975 * (_BOOTSTRAP_ITERS - 1))]
        return {
            "observed_lift": observed,
            "p_value": p_value,
            "significant": observed > 0 and p_value < _SIGNIFICANCE_P,
            "n": n,
            "ci95_lift": [lo, hi],
            "method": "paired_seeded_bootstrap_percentile",
            "iterations": _BOOTSTRAP_ITERS,
        }

    # ---------------------------------------------------------------------- run
    def run(
        self, candidate: OrchestrationGenome, output_dir: Optional[Path] = None
    ) -> dict[str, Any]:
        """Run the full arena epoch and (optionally) write all output artifacts."""
        candidate = candidate.with_descriptors()
        task_ids = self.taskpack.task_ids()

        # --- Controls (gate first; it sets the parity budget).
        gate, seat_scorecards = self._best_single_full_budget()
        budget_ref = gate.total_compute
        self_moa = self._same_budget_self_moa(budget_ref, gate.model_id)
        ensemble = self._random_or_static_ensemble()
        # --- Candidate.
        cand = self.run_arm("candidate", candidate)
        # --- Budget-parity control: strongest seat at the candidate's exact
        #     call budget (the honest "equal spend" baseline; kill-list doctrine).
        parity_control, parity_report = self._best_single_parity_budget(gate, cand)

        # --- Budget parity, logged for candidate AND every control (spec §6.3).
        arms = {
            "candidate": cand,
            "best_single_full_budget": gate,
            "best_single_parity_budget": parity_control,
            "same_budget_self_moa": self_moa,
            "random_or_static_ensemble": ensemble,
        }
        budget_parity = {
            name: {
                "total_compute": r.total_compute,
                "budget_ref": budget_ref,
                "within_parity": r.total_compute <= budget_ref,
            }
            for name, r in arms.items()
        }
        # Externally auditable spend ledger (tokens/compute + calls per arm):
        # parity must be checkable from receipts, not merely enforced in-process.
        parity_ledger = {
            name: {
                "total_compute": r.total_compute,
                "total_calls": len(
                    [c for rr in r.route_receipts for c in rr["selected_models"]]
                ),
                "per_call_cap": getattr(self.pool, "per_call_cap", None),
            }
            for name, r in arms.items()
        }

        # --- Significance of candidate vs the gate AND vs the parity control.
        #     Both are paired per-task comparisons with a seeded bootstrap CI;
        #     no "win" exists below significance on BOTH baselines.
        sig = self._bootstrap_significance(
            cand.correctness_vector(task_ids), gate.correctness_vector(task_ids)
        )
        sig_parity = self._bootstrap_significance(
            cand.correctness_vector(task_ids),
            parity_control.correctness_vector(task_ids),
        )
        within_parity = budget_parity["candidate"]["within_parity"]
        parity_verified = bool(parity_report["verified"])
        contaminated = cand.sealed_access_during_run > 0

        # --- Council verifies the trace + the "beat controls" promotion claim.
        promotion_claim = {
            "claim": "beat_best_single_full_budget",
            "candidate_score": cand.score,
            "baseline_score": gate.score,
            "parity_baseline_score": parity_control.score,
            # Logged parity now also requires the instrumented control-arm
            # assertion — a broken parity instrument refutes the claim.
            "budget_parity_logged": within_parity and parity_verified,
        }
        contamination_findings: tuple[str, ...] = ()
        if contaminated:
            contamination_findings = ("candidate_read_sealed_labels",)
        council_receipt = self.council.verify_orchestration_trace(
            TraceVerificationRequest(
                genome_id=candidate.genome_id,
                route_receipts=cand.route_receipts,
                trace_receipts=cand.trace_receipts,
                scorecard=cand.scorecard,
                promotion_claim=promotion_claim,
                untrusted=contaminated,
                contamination_findings=contamination_findings,
            )
        )

        # --- Closeout selection.
        closeout = self._select_closeout(
            cand=cand,
            gate=gate,
            parity_control=parity_control,
            within_parity=within_parity,
            parity_verified=parity_verified,
            sig=sig,
            sig_parity=sig_parity,
            contaminated=contaminated,
            council_verdict=council_receipt.verdict,
        )

        # --- DPI / power index.
        power = self._power_index(cand, gate, council_receipt, sig)

        run = {
            "schema": "orchestration_arena_v1_run.v1",
            "task_pack_id": self.taskpack.task_manifest_hash(),
            "task_manifest_hash": self.taskpack.task_manifest_hash(),
            "scorer_hash": scorer_hash(),
            "sealed_oracle_hash": self.taskpack.sealed_oracle_hash(),
            "candidate_genome_id": candidate.genome_id,
            "candidate_behavioral_descriptors": candidate.behavioral_descriptors.model_dump(),
            "arm_scores": {name: r.score for name, r in arms.items()},
            "budget_parity": budget_parity,
            "budget_ref": budget_ref,
            "parity_control": parity_report,
            "parity_ledger": parity_ledger,
            "significance": sig,
            "significance_vs_parity_control": sig_parity,
            "seat_scorecards": seat_scorecards,
            "roster": {
                m: {"specialty": spec.specialty} for m, spec in self.roster.items()
            },
            "measurement_mode": getattr(self.pool, "mode", "hermetic_fixture"),
            "contaminated": contaminated,
            "council_verdict": council_receipt.verdict,
            "closeout_state": closeout,
            "promotion_claim": promotion_claim,
        }

        if output_dir is not None:
            self._write_outputs(output_dir, run, arms, cand, council_receipt, power)
        run["scorecard_hash"] = scorecard_hash(cand.scorecard)
        run["_council_receipt"] = council_receipt.to_dict()
        run["_power_index"] = power
        return run

    def _select_closeout(
        self,
        *,
        cand: ArmResult,
        gate: ArmResult,
        parity_control: ArmResult,
        within_parity: bool,
        parity_verified: bool,
        sig: dict[str, Any],
        sig_parity: dict[str, Any],
        contaminated: bool,
        council_verdict: str,
    ) -> str:
        if contaminated or council_verdict == "quarantined":
            return "contaminated_quarantine"
        if not cand.submission or not self.taskpack.task_ids():
            return "blocked_with_evidence"
        if not parity_verified:
            # FAIL CLOSED (kill-list doctrine): if the budget-parity instrument
            # itself broke, no comparison is trustworthy — the run is blocked
            # with evidence; it can never degrade into a win OR an honest loss.
            return "blocked_with_evidence"
        lift = cand.score - gate.score
        lift_vs_parity = cand.score - parity_control.score
        if lift <= 0 or lift_vs_parity <= 0:
            # The swarm must beat the strongest seat under BOTH budget framings
            # (seat at its own budget AND seat at the swarm's budget).
            return "measured_negative"
        # lift > 0 from here
        if not within_parity:
            # Beating best-single by spending more is theater (spec §3) — not a pass.
            return "measured_negative"
        if not (sig["significant"] and sig_parity["significant"]):
            # No "win" classification below significance — on either baseline.
            return "inconclusive_low_power"
        # The Council must affirmatively CORROBORATE the trace + "beat controls"
        # claim before a positive promotion. A refuted/insufficient verdict (e.g.
        # from a stricter injected Council) blocks promotion even on a high score —
        # the verifier's word gates the closeout, it is not advisory (spec §6).
        if council_verdict != "corroborated":
            return "blocked_with_evidence"
        return "positive_lift_candidate"

    def _power_index(
        self, cand: ArmResult, gate: ArmResult, council_receipt, sig: dict[str, Any]
    ) -> dict[str, Any]:
        final_correct = cand.score > 0
        # Decorrelation inputs: per-task marginal contribution of routing vs gate.
        loo = {"router": max(0.0, cand.score - gate.score)}
        nonredundancy = {"router": 1.0 if cand.score > gate.score else 0.0}
        trust_replay = 1.0 if council_receipt.verdict in ("corroborated", "refuted") else 0.5
        corroboration = 1.0 if council_receipt.verdict == "corroborated" else 0.5
        inputs = DPIInputs(
            candidate_score=cand.score,
            best_single_score=gate.score,
            final_correct=final_correct,
            loo_marginal_contributions=loo,
            nonredundancy=nonredundancy,
            receipt_coverage=1.0,
            replay_pass_rate=trust_replay,
            corroboration_strength=corroboration,
            reuse_or_learning_value=1.0,  # retroactive-only: logged, not active
            cost=float(max(cand.total_compute, 1)),
            latency=1.0,
            fragility=1.0 + (0.0 if sig["significant"] else 0.5),
            complexity=float(max(len(cand.route_receipts), 1)),
        )
        out = compute_dpi(inputs, activate_learning=False)
        out["candidate_score"] = cand.score
        out["best_single_score"] = gate.score
        return out

    def _write_outputs(self, output_dir, run, arms, cand, council_receipt, power) -> None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        _write_json(out / "arena_run.json", run)
        _write_json(
            out / "scorecard.json",
            {
                "candidate": cand.scorecard,
                "scorecard_hash": scorecard_hash(cand.scorecard),
                "arms": {name: r.scorecard for name, r in arms.items()},
                # A lift point estimate is FORBIDDEN without its interval: the
                # scorecard always carries the paired-bootstrap significance
                # (observed lift + ci95 + p) for both baselines.
                "significance": {
                    "vs_best_single_full_budget": run["significance"],
                    "vs_best_single_parity_budget": run[
                        "significance_vs_parity_control"
                    ],
                },
                "parity_control": run["parity_control"],
                "parity_ledger": run["parity_ledger"],
            },
        )
        _write_jsonl(
            out / "trace_receipts.jsonl",
            [r for arm in arms.values() for r in arm.trace_receipts],
        )
        _write_jsonl(
            out / "route_receipts.jsonl",
            [r for arm in arms.values() for r in arm.route_receipts],
        )
        _write_jsonl(out / "council_receipts.jsonl", [council_receipt.to_dict()])
        _write_json(out / "power_index.json", power)
        _write_text(out / "decision_packet.md", render_decision_packet(run, power))


def _sig_line(sig: dict[str, Any]) -> str:
    """Render a lift WITH its interval — a point estimate alone is forbidden."""
    ci = sig.get("ci95_lift", [0.0, 0.0])
    return (
        f"observed_lift: {sig['observed_lift']:.4f}  "
        f"ci95=[{ci[0]:.4f}, {ci[1]:.4f}]  "
        f"(p={sig['p_value']:.4f}, significant={sig['significant']}, n={sig['n']})"
    )


def render_decision_packet(run: dict[str, Any], power: dict[str, Any]) -> str:
    bp = run["budget_parity"]
    lines = [
        "# Arena v1 — Decision Packet",
        "",
        f"- task_pack: `{run['task_pack_id'][:16]}…`",
        f"- task_manifest_hash: `{run['task_manifest_hash'][:16]}…`",
        f"- scorer_hash: `{run['scorer_hash'][:16]}…`",
        f"- candidate_genome_id: `{run['candidate_genome_id']}`",
        f"- measurement_mode: `{run.get('measurement_mode', 'hermetic_fixture')}`",
        f"- **closeout_state: `{run['closeout_state']}`**",
        f"- council_verdict: `{run['council_verdict']}`",
        "",
        "## Scores at budget parity",
        "",
        "| arm | score | total_compute | within_parity |",
        "| --- | ----- | ------------- | ------------- |",
    ]
    for arm, score in run["arm_scores"].items():
        row = bp[arm]
        lines.append(
            f"| {arm} | {score:.4f} | {row['total_compute']} | {row['within_parity']} |"
        )
    sig = run["significance"]
    lines += [
        "",
        "## Best-single gate",
        "",
        f"- best_single_full_budget score: {run['arm_scores']['best_single_full_budget']:.4f}",
        f"- candidate score: {run['arm_scores']['candidate']:.4f}",
        f"- {_sig_line(sig)}",
        f"- budget_ref: {run['budget_ref']}  ·  candidate_within_parity: "
        f"{bp['candidate']['within_parity']}",
    ]
    pc = run.get("parity_control")
    sig_pc = run.get("significance_vs_parity_control")
    if pc is not None and sig_pc is not None:
        lines += [
            "",
            "## Budget-parity control (strongest seat at the swarm's call budget)",
            "",
            f"- control_model: `{pc['control_model']}`  ·  parity_verified: "
            f"**{pc['verified']}** (fails closed on mismatch)",
            f"- calls: control={pc['control_total_calls']} "
            f"candidate={pc['candidate_total_calls']} "
            f"(match={pc['calls_per_task_match']}, per_call_cap={pc['per_call_cap']})",
            f"- best_single_parity_budget score: "
            f"{run['arm_scores']['best_single_parity_budget']:.4f}",
            f"- {_sig_line(sig_pc)}",
        ]
    lines += [
        "",
        "## Dharma Power Index",
        "",
        f"- DPI: {power['dpi']:.6f}",
        f"- verified_capability_delta: {power['verified_capability_delta']:.4f}",
        f"- decorrelation_bonus: {power['decorrelation_bonus']:.4f} "
        f"(final_correct={power['final_correct']})",
        f"- trust_multiplier: {power['trust_multiplier']:.4f}",
        f"- reuse_or_learning_value: logged={power['reuse_or_learning_value_logged']:.4f}, "
        f"active={power['learning_active']}",
        "",
        "## Verdict",
        "",
        _verdict_line(run["closeout_state"]),
        "",
        "_Correctness authority: the deterministic scorer/test-oracle only. "
        "The Council verified trace integrity, contamination boundaries, and the "
        "'beat controls' claim — never correctness._",
    ]
    return "\n".join(lines) + "\n"


def _verdict_line(state: str) -> str:
    return {
        "positive_lift_candidate": "✅ POSITIVE LIFT: the genome beats best-single at "
        "equal compute, with significance. Eligible for MAP-Elites promotion.",
        "measured_negative": "➖ MEASURED NEGATIVE: no honest lift over best-single at "
        "equal compute. Not promotable.",
        "inconclusive_low_power": "❓ INCONCLUSIVE: lift not significant at current power.",
        "contaminated_quarantine": "🚫 CONTAMINATED: candidate touched sealed labels / "
        "untrusted input. Quarantined; fitness untouched.",
        "blocked_with_evidence": "🛑 BLOCKED: could not run; see evidence.",
    }.get(state, state)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8"
    )


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


__all__ = ["CLOSEOUT_STATES", "ArenaRunner", "ArmResult", "render_decision_packet"]
