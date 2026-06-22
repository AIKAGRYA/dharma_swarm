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
    ALL_MODEL_IDS,
    ROSTER_REGISTRY,
    FixturePool,
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
    ) -> None:
        self.taskpack = taskpack or Taskpack()
        self.pool = pool or FixturePool()
        self.council = council or Council()

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
            spec = ROSTER_REGISTRY.get(member_id)
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
    def _best_single_full_budget(self) -> ArmResult:
        """The GATE: the single best model run once on every task at full budget."""
        best: Optional[ArmResult] = None
        for model_id in ALL_MODEL_IDS:
            single = OrchestrationGenome(
                roster=[{"role_id": model_id, "member_id": model_id, "kind": "model"}],
                adjudication_rule="single",
            )
            result = self.run_arm("best_single_full_budget", single)
            # tie-break: higher score, then lower compute, then model name
            if best is None or (result.score, -result.total_compute, model_id) > (
                best.score,
                -best.total_compute,
                best.submission.get("_model", ""),
            ):
                result.submission["_model"] = model_id  # provenance breadcrumb
                best = result
        assert best is not None
        return best

    def _same_budget_self_moa(self, budget: int) -> ArmResult:
        """Best single model doing internal MoA within the SAME budget cap.

        With a deterministic fixture pool, resampling the same model yields the
        same answers, so self-MoA cannot exceed the single model — it just spends
        the budget. Capped so it never exceeds parity.
        """
        # pick the best single model id
        best_model = max(
            ALL_MODEL_IDS,
            key=lambda m: self.run_arm(
                "probe",
                OrchestrationGenome(
                    roster=[{"role_id": m, "member_id": m, "kind": "model"}],
                    adjudication_rule="single",
                ),
            ).score,
        )
        genome = OrchestrationGenome(
            roster=[{"role_id": best_model, "member_id": best_model, "kind": "model"}],
            adjudication_rule="single",
        )
        result = self.run_arm("same_budget_self_moa", genome)
        result.total_compute = min(result.total_compute, budget)
        return result

    def _random_or_static_ensemble(self) -> ArmResult:
        """Static ensemble: all roster models vote on every task (brute force)."""
        genome = OrchestrationGenome(
            roster=[
                {"role_id": m, "member_id": m, "kind": "model"} for m in ALL_MODEL_IDS
            ],
            adjudication_rule="vote",
        )
        return self.run_arm("random_or_static_ensemble", genome)

    # ----------------------------------------------------------------- statistics
    @staticmethod
    def _bootstrap_significance(cand: list[int], base: list[int]) -> dict[str, Any]:
        """Seeded paired bootstrap on per-task correctness. Deterministic/replayable."""
        n = len(cand)
        diffs = [c - b for c, b in zip(cand, base)]
        observed = sum(diffs) / n if n else 0.0
        if n == 0:
            return {"observed_lift": 0.0, "p_value": 1.0, "significant": False, "n": 0}
        rng = random.Random(_BOOTSTRAP_SEED)
        worse_or_equal = 0
        for _ in range(_BOOTSTRAP_ITERS):
            resampled = sum(diffs[rng.randrange(n)] for _ in range(n)) / n
            if resampled <= 0:
                worse_or_equal += 1
        p_value = worse_or_equal / _BOOTSTRAP_ITERS
        return {
            "observed_lift": observed,
            "p_value": p_value,
            "significant": observed > 0 and p_value < _SIGNIFICANCE_P,
            "n": n,
        }

    # ---------------------------------------------------------------------- run
    def run(
        self, candidate: OrchestrationGenome, output_dir: Optional[Path] = None
    ) -> dict[str, Any]:
        """Run the full arena epoch and (optionally) write all output artifacts."""
        candidate = candidate.with_descriptors()
        task_ids = self.taskpack.task_ids()

        # --- Controls (gate first; it sets the parity budget).
        gate = self._best_single_full_budget()
        budget_ref = gate.total_compute
        self_moa = self._same_budget_self_moa(budget_ref)
        ensemble = self._random_or_static_ensemble()
        # --- Candidate.
        cand = self.run_arm("candidate", candidate)

        # --- Budget parity, logged for candidate AND every control (spec §6.3).
        arms = {
            "candidate": cand,
            "best_single_full_budget": gate,
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

        # --- Significance of candidate vs the gate.
        sig = self._bootstrap_significance(
            cand.correctness_vector(task_ids), gate.correctness_vector(task_ids)
        )
        within_parity = budget_parity["candidate"]["within_parity"]
        contaminated = cand.sealed_access_during_run > 0

        # --- Council verifies the trace + the "beat controls" promotion claim.
        promotion_claim = {
            "claim": "beat_best_single_full_budget",
            "candidate_score": cand.score,
            "baseline_score": gate.score,
            "budget_parity_logged": within_parity,
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
            within_parity=within_parity,
            sig=sig,
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
            "candidate_genome_id": candidate.genome_id,
            "candidate_behavioral_descriptors": candidate.behavioral_descriptors.model_dump(),
            "arm_scores": {name: r.score for name, r in arms.items()},
            "budget_parity": budget_parity,
            "budget_ref": budget_ref,
            "significance": sig,
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
        within_parity: bool,
        sig: dict[str, Any],
        contaminated: bool,
        council_verdict: str,
    ) -> str:
        if contaminated or council_verdict == "quarantined":
            return "contaminated_quarantine"
        if not cand.submission or not self.taskpack.task_ids():
            return "blocked_with_evidence"
        lift = cand.score - gate.score
        if lift <= 0:
            return "measured_negative"
        # lift > 0 from here
        if not within_parity:
            # Beating best-single by spending more is theater (spec §3) — not a pass.
            return "measured_negative"
        if not sig["significant"]:
            return "inconclusive_low_power"
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


def render_decision_packet(run: dict[str, Any], power: dict[str, Any]) -> str:
    bp = run["budget_parity"]
    lines = [
        "# Arena v1 — Decision Packet",
        "",
        f"- task_pack: `{run['task_pack_id'][:16]}…`",
        f"- task_manifest_hash: `{run['task_manifest_hash'][:16]}…`",
        f"- scorer_hash: `{run['scorer_hash'][:16]}…`",
        f"- candidate_genome_id: `{run['candidate_genome_id']}`",
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
        f"- observed_lift: {sig['observed_lift']:.4f}  (p={sig['p_value']:.4f}, "
        f"significant={sig['significant']}, n={sig['n']})",
        f"- budget_ref: {run['budget_ref']}  ·  candidate_within_parity: "
        f"{bp['candidate']['within_parity']}",
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
