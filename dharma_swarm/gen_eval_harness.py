"""Planner-Generator-Evaluator (PGE) Harness.

Hardwired invariant: every autonomous build in dharma_swarm MUST pass through
the PGE loop.  No build completes without:
  1. A Planner sprint decomposition
  2. A negotiated Generator↔Evaluator Contract (definition of done)
  3. An adversarial Evaluator check against the contract and rubric

Architecture (from Anthropic Applied AI, AI Engineer Conf 2026):

    PLANNER → [sprint spec] → GENERATOR ↔ CONTRACT ↔ EVALUATOR
                                   ↑                      |
                                   └──── critique ←────────┘
                                   (restart if hill-climb fails)

Key invariants:
  - Separate context windows (claude -p calls) per role
  - File-based shared state (JSON, not markdown — less overwrite risk)
  - Contract negotiated BEFORE first line of code
  - Evaluator is adversarial; tuned harsh, separate from generator
  - If evaluation score cannot hill-climb after N rounds → throw away + restart
  - Planner is high-level ONLY; no granular technical decisions (cascade error risk)

Rubric weights (inspired by the GAN-style design taste calibration):
  design:       30%  — visual/structural coherence, no AI slop
  originality:  30%  — fresh perspective, not template output
  craft:        20%  — code quality, reliability, edge cases
  functionality:20%  — actually works when tested live

Usage:
    harness = GeneratorEvaluatorLoop(
        prompt="Build a retro game maker",
        output_dir=Path("/tmp/retro_game"),
        model_generator="claude-sonnet-4-6",
        model_evaluator="claude-opus-4-6",
    )
    result = harness.run()
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dharma_swarm.models import _new_id, _utc_now

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RUBRIC_WEIGHTS: dict[str, float] = {
    "design": 0.30,
    "originality": 0.30,
    "craft": 0.20,
    "functionality": 0.20,
}

GEN_EVAL_RUNS_LOG = Path.home() / ".dharma" / "gen_eval_runs.jsonl"

# Minimum score (0-100) to consider a round successful
PASS_THRESHOLD = 72.0

# If score doesn't improve by this much per round, count as stalled
MIN_IMPROVEMENT = 3.0

# Restart after this many consecutive stalled rounds
STALL_RESTART_AFTER = 2

# Hard cap on total rounds (generator iterations) per sprint
MAX_ROUNDS_PER_SPRINT = 8

# Hard cap on restarts per sprint before marking failed
MAX_RESTARTS_PER_SPRINT = 3


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class SprintSpec(BaseModel):
    """A single sprint produced by the Planner role.

    Planners produce HIGH-LEVEL sprint specs only — no granular technical
    details.  Technical decisions cascade into errors over multi-hour runs.
    """

    id: str = Field(default_factory=_new_id)
    index: int
    title: str
    goal: str                          # What user value does this sprint deliver?
    scope_notes: str = ""             # What is explicitly OUT of scope
    success_criteria: str = ""        # High-level, not implementation-specific
    status: str = "pending"           # pending | in_progress | completed | failed


class Contract(BaseModel):
    """Negotiated definition-of-done between Generator and Evaluator.

    The contract is negotiated BEFORE the generator writes a single line.
    Generator proposes; Evaluator may push back.  Both must agree before
    building starts.

    Written to disk as JSON so both agents share it without context bleed.
    """

    id: str = Field(default_factory=_new_id)
    sprint_id: str
    sprint_title: str
    proposed_by: str = "generator"
    accepted: bool = False
    rounds: int = 0
    criteria: list[str] = Field(default_factory=list)     # Concrete testable assertions
    test_steps: list[str] = Field(default_factory=list)   # Evaluator's test protocol
    edge_cases: list[str] = Field(default_factory=list)   # Cases the evaluator will check
    rejection_reasons: list[str] = Field(default_factory=list)
    agreed_at: str = ""
    created_at: str = Field(default_factory=lambda: _utc_now().isoformat())


class RubricScore(BaseModel):
    """Evaluator's rubric score for one build round.

    Weighted average = design*0.30 + originality*0.30 + craft*0.20 + functionality*0.20
    """

    id: str = Field(default_factory=_new_id)
    sprint_id: str
    round_index: int
    design: float = Field(ge=0.0, le=100.0, description="Visual/structural coherence, no AI slop")
    originality: float = Field(ge=0.0, le=100.0, description="Fresh perspective, not template output")
    craft: float = Field(ge=0.0, le=100.0, description="Code quality, reliability, edge cases")
    functionality: float = Field(ge=0.0, le=100.0, description="Actually works when tested live")
    critique: str = ""           # Evaluator's specific critique
    passed: bool = False
    scored_at: str = Field(default_factory=lambda: _utc_now().isoformat())

    @property
    def weighted_score(self) -> float:
        return (
            self.design * RUBRIC_WEIGHTS["design"]
            + self.originality * RUBRIC_WEIGHTS["originality"]
            + self.craft * RUBRIC_WEIGHTS["craft"]
            + self.functionality * RUBRIC_WEIGHTS["functionality"]
        )

    def to_record(self) -> dict[str, Any]:
        d = self.model_dump()
        d["weighted_score"] = round(self.weighted_score, 2)
        return d


class SprintResult(BaseModel):
    """Outcome of running one sprint through the full PGE loop."""

    sprint_id: str
    sprint_title: str
    success: bool
    rounds_taken: int
    restarts: int
    final_score: float | None = None
    scores_history: list[float] = Field(default_factory=list)
    error: str | None = None
    output_path: str = ""
    duration_seconds: float = 0.0


class HarnessResult(BaseModel):
    """Top-level result of a full PGE harness run."""

    id: str = Field(default_factory=_new_id)
    prompt: str
    output_dir: str
    sprints_total: int
    sprints_completed: int
    sprints_failed: int
    sprint_results: list[SprintResult] = Field(default_factory=list)
    total_rounds: int = 0
    total_restarts: int = 0
    duration_seconds: float = 0.0
    success: bool = False
    started_at: str = Field(default_factory=lambda: _utc_now().isoformat())
    completed_at: str = ""


# ---------------------------------------------------------------------------
# File-based state helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _log_run(record: dict[str, Any]) -> None:
    """Append a run record to the global gen_eval_runs log (used by invariant)."""
    _append_jsonl(GEN_EVAL_RUNS_LOG, record)


# ---------------------------------------------------------------------------
# Role prompts
# ---------------------------------------------------------------------------


def _planner_prompt(prompt: str, n_sprints: int = 4) -> str:
    return f"""You are the PLANNER role in a Planner-Generator-Evaluator build system.

Your job: take the user's vague prompt and decompose it into {n_sprints} high-level sprints.

RULES:
- Sprints are HIGH-LEVEL only. Do NOT specify implementation details.
- Each sprint must deliver visible user value.
- Scope must be explicit (what is out of scope matters).
- Success criteria should be observable, not implementation-specific.
- Output ONLY valid JSON — no markdown fences.

User prompt: {prompt}

Output format (JSON array of sprint objects):
[
  {{
    "index": 1,
    "title": "Sprint title",
    "goal": "What user value this delivers",
    "scope_notes": "What is explicitly out of scope for this sprint",
    "success_criteria": "How we know this sprint is done (observable)"
  }},
  ...
]"""


def _contract_generator_prompt(sprint: SprintSpec, rejection: str = "") -> str:
    rejection_block = f"\nEVALUATOR REJECTED PREVIOUS PROPOSAL:\n{rejection}\n" if rejection else ""
    return f"""You are the GENERATOR in a contract negotiation.

Sprint: {sprint.title}
Goal: {sprint.goal}
Success criteria: {sprint.success_criteria}
{rejection_block}
Propose a BUILD CONTRACT — a precise definition of what "done" means for this sprint.

The evaluator will push back if:
- Scope is too large
- Test steps are too weak
- Edge cases are missing
- Criteria are vague

Output ONLY valid JSON:
{{
  "criteria": ["specific assertion 1", "specific assertion 2", ...],
  "test_steps": ["evaluator test step 1", "evaluator test step 2", ...],
  "edge_cases": ["edge case 1", "edge case 2", ...]
}}"""


def _contract_evaluator_prompt(sprint: SprintSpec, generator_proposal: dict[str, Any]) -> str:
    return f"""You are the EVALUATOR in a contract negotiation. You are ADVERSARIAL.

Sprint: {sprint.title}
Goal: {sprint.goal}

Generator proposed this contract:
{json.dumps(generator_proposal, indent=2)}

Your job: accept or reject. Reject if:
- Scope is too large for one sprint
- Test steps are weak (would pass even if feature is broken)
- Critical edge cases are missing
- Criteria are vague or untestable

Output ONLY valid JSON:
{{
  "accepted": true/false,
  "rejection_reasons": ["reason 1", "reason 2", ...],
  "suggested_additions": ["addition 1", "addition 2", ...]
}}"""


def _evaluator_rubric_prompt(sprint: SprintSpec, contract: Contract, output_path: str) -> str:
    criteria_block = "\n".join(f"- {c}" for c in contract.criteria)
    test_steps_block = "\n".join(f"- {s}" for s in contract.test_steps)
    edge_cases_block = "\n".join(f"- {e}" for e in contract.edge_cases)
    return f"""You are the EVALUATOR role. You are ADVERSARIAL. Your job is to find failures.

Sprint: {sprint.title}
Output to evaluate: {output_path}

CONTRACT CRITERIA (what was promised):
{criteria_block}

TEST PROTOCOL (run these tests):
{test_steps_block}

EDGE CASES (must check these):
{edge_cases_block}

RUBRIC (score each 0-100):
- design (30%): Visual/structural coherence. No purple gradients, no AI slop aesthetics.
  High = opinionated, tasteful, intentional. Low = generic template output.
- originality (30%): Does this feel like a real product decision or a default?
  High = named itself, made novel choices. Low = copied obvious patterns.
- craft (20%): Code quality, edge cases handled, reliability.
  High = clean, typed, tested. Low = spaghetti, undefined behaviors.
- functionality (20%): Actually works end-to-end when tested live.
  High = arrow keys work, backend exists, game plays. Low = looks done but breaks.

IMPORTANT: Do not rubber-stamp. If in doubt, score lower. Be harsh.
If a criterion from the contract is NOT met, that is a functionality failure.

Output ONLY valid JSON:
{{
  "design": <0-100>,
  "originality": <0-100>,
  "craft": <0-100>,
  "functionality": <0-100>,
  "critique": "specific, actionable critique the generator can act on",
  "contract_violations": ["criterion that was NOT met", ...]
}}"""


# ---------------------------------------------------------------------------
# Claude subprocess runner
# ---------------------------------------------------------------------------


def _run_claude(
    prompt: str,
    *,
    model: str = "claude-sonnet-4-6",
    max_turns: int = 1,
    allowed_tools: str = "Read,Grep,Glob",
    cwd: Path | None = None,
    timeout: int = 120,
) -> str:
    """Run claude -p in a subprocess with a fresh context window.

    Returns the raw text output.
    Raises subprocess.CalledProcessError on failure.
    """
    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--max-turns", str(max_turns),
        "--allowedTools", allowed_tools,
        "--output-format", "text",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("claude subprocess failed: %s", exc)
        return ""


def _parse_json_output(raw: str) -> dict[str, Any] | list[Any] | None:
    """Extract JSON from raw LLM output, stripping fences if present."""
    text = raw.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines
            if not line.startswith("```")
        ).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON object/array within the text
        for start_ch, end_ch in (("{", "}"), ("[", "]")):
            start = text.find(start_ch)
            end = text.rfind(end_ch)
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    continue
        return None


# ---------------------------------------------------------------------------
# Core PGE roles
# ---------------------------------------------------------------------------


class PlannerRole:
    """Produces high-level sprint decompositions from a vague prompt.

    Read-only; never writes code.  Uses Opus for planning quality.
    """

    def __init__(self, model: str = "claude-opus-4-6") -> None:
        self.model = model

    def decompose(self, prompt: str, n_sprints: int = 4) -> list[SprintSpec]:
        """Break a prompt into N high-level sprints."""
        planner_prompt = _planner_prompt(prompt, n_sprints)
        raw = _run_claude(planner_prompt, model=self.model, max_turns=1, timeout=120)
        parsed = _parse_json_output(raw)
        if not isinstance(parsed, list):
            logger.warning("Planner returned non-list JSON; using fallback single sprint")
            return [SprintSpec(
                index=1,
                title="Full implementation",
                goal=prompt,
                success_criteria="Core functionality works end-to-end",
            )]
        sprints = []
        for i, item in enumerate(parsed):
            if isinstance(item, dict):
                sprints.append(SprintSpec(
                    index=item.get("index", i + 1),
                    title=str(item.get("title", f"Sprint {i+1}")),
                    goal=str(item.get("goal", "")),
                    scope_notes=str(item.get("scope_notes", "")),
                    success_criteria=str(item.get("success_criteria", "")),
                ))
        return sprints or [SprintSpec(index=1, title="Full implementation", goal=prompt)]


class ContractNegotiator:
    """Manages Generator↔Evaluator contract negotiation.

    Generator proposes; Evaluator accepts or rejects.
    Max 3 rounds before fallback to generator's last proposal.
    """

    MAX_NEGOTIATION_ROUNDS = 3

    def __init__(
        self,
        model_generator: str = "claude-sonnet-4-6",
        model_evaluator: str = "claude-opus-4-6",
    ) -> None:
        self.model_generator = model_generator
        self.model_evaluator = model_evaluator

    def negotiate(self, sprint: SprintSpec, state_dir: Path) -> Contract:
        """Run the contract negotiation loop, persisting state to disk."""
        contract = Contract(sprint_id=sprint.id, sprint_title=sprint.title)
        contract_path = state_dir / f"contract_{sprint.id}.json"
        rejection = ""

        for round_num in range(1, self.MAX_NEGOTIATION_ROUNDS + 1):
            contract.rounds = round_num

            # Generator proposes
            gen_prompt = _contract_generator_prompt(sprint, rejection)
            raw_proposal = _run_claude(
                gen_prompt, model=self.model_generator, max_turns=1, timeout=90,
            )
            proposal = _parse_json_output(raw_proposal)
            if not isinstance(proposal, dict):
                logger.warning("Contract round %d: generator returned invalid JSON", round_num)
                proposal = {}

            contract.criteria = list(proposal.get("criteria", []))
            contract.test_steps = list(proposal.get("test_steps", []))
            contract.edge_cases = list(proposal.get("edge_cases", []))
            _write_json(contract_path, contract.model_dump())

            # Evaluator accepts or rejects
            eval_prompt = _contract_evaluator_prompt(sprint, proposal)
            raw_verdict = _run_claude(
                eval_prompt, model=self.model_evaluator, max_turns=1, timeout=90,
            )
            verdict = _parse_json_output(raw_verdict)
            if not isinstance(verdict, dict):
                logger.warning("Contract round %d: evaluator returned invalid JSON — accepting", round_num)
                verdict = {"accepted": True}

            if verdict.get("accepted", False):
                contract.accepted = True
                contract.agreed_at = _utc_now().isoformat()
                _write_json(contract_path, contract.model_dump())
                logger.info("Contract agreed in %d round(s) for sprint: %s", round_num, sprint.title)
                return contract
            else:
                reasons = list(verdict.get("rejection_reasons", []))
                additions = list(verdict.get("suggested_additions", []))
                contract.rejection_reasons = reasons
                rejection = "\n".join(reasons + additions)
                logger.info(
                    "Contract round %d rejected for sprint '%s': %s",
                    round_num, sprint.title, "; ".join(reasons[:2]),
                )

        # Fallback: use generator's last proposal after max rounds
        contract.accepted = True
        contract.agreed_at = _utc_now().isoformat()
        _write_json(contract_path, contract.model_dump())
        logger.info("Contract fallback accepted after max rounds for sprint: %s", sprint.title)
        return contract


class AdversarialEvaluator:
    """Adversarial critic — grades build output against the contract rubric.

    Tuned harsh.  Separate context window from generator.
    Can trigger restart signal if hill-climbing fails.
    """

    def __init__(self, model: str = "claude-opus-4-6") -> None:
        self.model = model

    def score(
        self,
        sprint: SprintSpec,
        contract: Contract,
        output_path: str,
        round_index: int,
    ) -> RubricScore:
        """Score the generator's output against the contract rubric."""
        eval_prompt = _evaluator_rubric_prompt(sprint, contract, output_path)
        raw = _run_claude(
            eval_prompt,
            model=self.model,
            max_turns=3,
            allowed_tools="Read,Grep,Glob,Bash",
            cwd=Path(output_path) if Path(output_path).is_dir() else None,
            timeout=300,
        )
        parsed = _parse_json_output(raw)
        if not isinstance(parsed, dict):
            logger.warning("Evaluator returned invalid JSON for round %d", round_index)
            return RubricScore(
                sprint_id=sprint.id,
                round_index=round_index,
                design=20.0, originality=20.0, craft=20.0, functionality=20.0,
                critique="Evaluator output was unparseable",
            )

        score = RubricScore(
            sprint_id=sprint.id,
            round_index=round_index,
            design=float(parsed.get("design", 20.0)),
            originality=float(parsed.get("originality", 20.0)),
            craft=float(parsed.get("craft", 20.0)),
            functionality=float(parsed.get("functionality", 20.0)),
            critique=str(parsed.get("critique", "")),
        )
        score.passed = score.weighted_score >= PASS_THRESHOLD
        return score


# ---------------------------------------------------------------------------
# Main harness loop
# ---------------------------------------------------------------------------


@dataclass
class GeneratorEvaluatorLoop:
    """The invariant build loop.  Every autonomous dharma_swarm build routes here.

    Orchestrates: Planner → Contract negotiation → Generator → Evaluator → repeat.
    File-based state survives crashes and restarts.
    """

    prompt: str
    output_dir: Path
    model_planner: str = "claude-opus-4-6"
    model_generator: str = "claude-sonnet-4-6"
    model_evaluator: str = "claude-opus-4-6"
    n_sprints: int = 4
    max_rounds_per_sprint: int = MAX_ROUNDS_PER_SPRINT
    max_restarts_per_sprint: int = MAX_RESTARTS_PER_SPRINT
    pass_threshold: float = PASS_THRESHOLD

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir)
        self.state_dir = self.output_dir / ".pge_state"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    # -- State persistence --

    def _load_sprints(self) -> list[SprintSpec]:
        path = self.state_dir / "sprints.json"
        if not path.exists():
            return []
        raw = json.loads(path.read_text())
        return [SprintSpec(**s) for s in raw]

    def _save_sprints(self, sprints: list[SprintSpec]) -> None:
        path = self.state_dir / "sprints.json"
        path.write_text(json.dumps([s.model_dump() for s in sprints], indent=2))

    def _save_score(self, score: RubricScore) -> None:
        _append_jsonl(self.state_dir / "scores.jsonl", score.to_record())

    def _load_progress(self) -> dict[str, Any]:
        return _read_json(self.state_dir / "progress.json")

    def _save_progress(self, data: dict[str, Any]) -> None:
        _write_json(self.state_dir / "progress.json", data)

    def _clear_sprint_output(self, sprint: SprintSpec) -> None:
        """Delete generated files for a sprint to force a fresh restart."""
        sprint_out = self.output_dir / f"sprint_{sprint.index:02d}"
        if sprint_out.exists():
            import shutil
            shutil.rmtree(sprint_out, ignore_errors=True)
            logger.info("Cleared sprint output dir for restart: %s", sprint_out)

    # -- Run --

    def run(self) -> HarnessResult:
        """Execute the full PGE loop.  Returns HarnessResult with all outcomes."""
        start_time = time.monotonic()
        run_id = _new_id()
        logger.info("PGE harness starting run %s: %s", run_id, self.prompt[:80])

        result = HarnessResult(
            id=run_id,
            prompt=self.prompt,
            output_dir=str(self.output_dir),
            sprints_total=0,
            sprints_completed=0,
            sprints_failed=0,
        )

        # Step 1: Load or generate sprint decomposition
        sprints = self._load_sprints()
        if not sprints:
            logger.info("Planning sprint decomposition…")
            planner = PlannerRole(model=self.model_planner)
            sprints = planner.decompose(self.prompt, n_sprints=self.n_sprints)
            self._save_sprints(sprints)
            logger.info("Planner produced %d sprints", len(sprints))

        result.sprints_total = len(sprints)
        progress = self._load_progress()
        progress.setdefault("completed_sprint_ids", [])
        progress.setdefault("run_id", run_id)

        negotiator = ContractNegotiator(
            model_generator=self.model_generator,
            model_evaluator=self.model_evaluator,
        )
        evaluator = AdversarialEvaluator(model=self.model_evaluator)

        # Step 2: Process each sprint
        for sprint in sprints:
            if sprint.id in progress["completed_sprint_ids"]:
                logger.info("Skipping already-completed sprint: %s", sprint.title)
                result.sprints_completed += 1
                continue
            if sprint.status == "failed":
                result.sprints_failed += 1
                continue

            sprint_result = self._run_sprint(sprint, negotiator, evaluator)
            result.sprint_results.append(sprint_result)
            result.total_rounds += sprint_result.rounds_taken
            result.total_restarts += sprint_result.restarts

            if sprint_result.success:
                sprint.status = "completed"
                progress["completed_sprint_ids"].append(sprint.id)
                result.sprints_completed += 1
            else:
                sprint.status = "failed"
                result.sprints_failed += 1

            self._save_sprints(sprints)
            self._save_progress(progress)

        # Finalize result
        result.success = result.sprints_failed == 0 and result.sprints_completed == result.sprints_total
        result.duration_seconds = round(time.monotonic() - start_time, 2)
        result.completed_at = _utc_now().isoformat()

        # Log to global runs log (feeds gen_eval_coherence invariant)
        _log_run({
            "run_id": run_id,
            "prompt": self.prompt[:200],
            "sprints_total": result.sprints_total,
            "sprints_completed": result.sprints_completed,
            "sprints_failed": result.sprints_failed,
            "success": result.success,
            "duration_seconds": result.duration_seconds,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
        })

        logger.info(
            "PGE run %s complete: %d/%d sprints, %.0fs",
            run_id, result.sprints_completed, result.sprints_total, result.duration_seconds,
        )
        return result

    def _run_sprint(
        self,
        sprint: SprintSpec,
        negotiator: ContractNegotiator,
        evaluator: AdversarialEvaluator,
    ) -> SprintResult:
        """Run one sprint through contract negotiation → build → evaluate loop."""
        sprint_start = time.monotonic()
        sprint_out = self.output_dir / f"sprint_{sprint.index:02d}"
        sprint_out.mkdir(parents=True, exist_ok=True)

        sprint.status = "in_progress"
        scores_history: list[float] = []
        total_rounds = 0
        restarts = 0

        for restart_num in range(self.max_restarts_per_sprint + 1):
            if restart_num > 0:
                logger.info(
                    "PGE restart %d/%d for sprint: %s",
                    restart_num, self.max_restarts_per_sprint, sprint.title,
                )
                self._clear_sprint_output(sprint)
                sprint_out.mkdir(parents=True, exist_ok=True)
                restarts += 1

            # Contract negotiation (fresh each restart)
            logger.info("Negotiating contract for sprint: %s", sprint.title)
            contract = negotiator.negotiate(sprint, self.state_dir)
            _write_json(
                self.state_dir / f"contract_final_{sprint.id}_{restart_num}.json",
                contract.model_dump(),
            )

            stall_count = 0
            prev_score: float | None = None
            round_success = False

            for round_idx in range(1, self.max_rounds_per_sprint + 1):
                total_rounds += 1

                # Generator builds (tool-enabled, cwd = sprint output dir)
                generator_prompt = self._generator_prompt(sprint, contract, sprint_out, round_idx)
                logger.info(
                    "Sprint '%s' restart=%d round=%d — generator building…",
                    sprint.title, restart_num, round_idx,
                )
                _run_claude(
                    generator_prompt,
                    model=self.model_generator,
                    max_turns=30,
                    allowed_tools="Edit,Write,Read,Bash,Glob,Grep",
                    cwd=sprint_out,
                    timeout=900,
                )

                # Evaluator scores
                score = evaluator.score(sprint, contract, str(sprint_out), round_idx)
                self._save_score(score)
                scores_history.append(round(score.weighted_score, 2))
                logger.info(
                    "Sprint '%s' R%d score: %.1f (design=%.0f orig=%.0f craft=%.0f func=%.0f) — %s",
                    sprint.title, round_idx,
                    score.weighted_score,
                    score.design, score.originality, score.craft, score.functionality,
                    "PASS" if score.passed else "fail",
                )

                if score.passed:
                    round_success = True
                    break

                # Check for stall (can't hill-climb)
                if prev_score is not None:
                    improvement = score.weighted_score - prev_score
                    if improvement < MIN_IMPROVEMENT:
                        stall_count += 1
                        if stall_count >= STALL_RESTART_AFTER:
                            logger.info(
                                "Sprint '%s' stalled at %.1f — triggering restart",
                                sprint.title, score.weighted_score,
                            )
                            break
                    else:
                        stall_count = 0

                prev_score = score.weighted_score

                # Write critique to file so generator can read it next round
                critique_path = sprint_out / ".evaluator_critique.md"
                critique_path.write_text(
                    f"# Evaluator Critique — Round {round_idx}\n\n"
                    f"Score: {score.weighted_score:.1f}/100\n\n"
                    f"{score.critique}\n",
                    encoding="utf-8",
                )

            if round_success:
                break

        final_score = scores_history[-1] if scores_history else None
        return SprintResult(
            sprint_id=sprint.id,
            sprint_title=sprint.title,
            success=round_success,
            rounds_taken=total_rounds,
            restarts=restarts,
            final_score=final_score,
            scores_history=scores_history,
            output_path=str(sprint_out),
            duration_seconds=round(time.monotonic() - sprint_start, 2),
        )

    @staticmethod
    def _generator_prompt(
        sprint: SprintSpec,
        contract: Contract,
        output_dir: Path,
        round_idx: int,
    ) -> str:
        criteria = "\n".join(f"- {c}" for c in contract.criteria)
        critique_note = ""
        critique_path = output_dir / ".evaluator_critique.md"
        if critique_path.exists() and round_idx > 1:
            critique_note = (
                f"\n## Previous Evaluator Critique (read this carefully)\n"
                f"{critique_path.read_text(encoding='utf-8')}\n"
            )
        return f"""You are the GENERATOR in a PGE build loop.

Sprint: {sprint.title}
Goal: {sprint.goal}
Output directory: {output_dir}

CONTRACT — what "done" means (negotiated with the evaluator):
{criteria}
{critique_note}
Build this sprint. Requirements:
1. All contract criteria must be satisfied.
2. Work ONLY in the output directory: {output_dir}
3. Write a .pge_manifest.json listing all files you create.
4. If round > 1, read the evaluator critique above and fix specific issues.
5. Quality over speed — the evaluator is adversarial and will find problems.

Go."""


# ---------------------------------------------------------------------------
# CLI entry points (called by dgc harness)
# ---------------------------------------------------------------------------


def cmd_harness_run(
    prompt: str,
    output_dir: str | None = None,
    *,
    model_generator: str = "claude-sonnet-4-6",
    model_evaluator: str = "claude-opus-4-6",
    n_sprints: int = 4,
) -> None:
    """CLI: run the PGE harness for a given prompt."""
    import sys
    from pathlib import Path as P

    out = P(output_dir) if output_dir else P.home() / ".dharma" / "harness_runs" / _new_id()
    out.mkdir(parents=True, exist_ok=True)

    print(f"PGE Harness starting\n  prompt: {prompt}\n  output: {out}\n")
    harness = GeneratorEvaluatorLoop(
        prompt=prompt,
        output_dir=out,
        model_generator=model_generator,
        model_evaluator=model_evaluator,
        n_sprints=n_sprints,
    )
    result = harness.run()
    print(f"\n{'✅' if result.success else '❌'} Harness complete")
    print(f"  Sprints: {result.sprints_completed}/{result.sprints_total}")
    print(f"  Rounds: {result.total_rounds}, Restarts: {result.total_restarts}")
    print(f"  Duration: {result.duration_seconds:.0f}s")
    if not result.success:
        sys.exit(1)


def cmd_harness_status() -> None:
    """CLI: show status of all recent PGE runs."""
    if not GEN_EVAL_RUNS_LOG.exists():
        print("No PGE runs recorded yet.")
        return
    rows = []
    with GEN_EVAL_RUNS_LOG.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    recent = rows[-10:]
    print(f"Last {len(recent)} PGE runs:\n")
    for r in recent:
        icon = "✅" if r.get("success") else "❌"
        print(
            f"  {icon} {r.get('started_at', '')[:19]}  "
            f"sprints={r.get('sprints_completed')}/{r.get('sprints_total')}  "
            f"dur={r.get('duration_seconds', 0):.0f}s  "
            f"{r.get('prompt', '')[:60]}"
        )


def cmd_harness_logs(output_dir: str) -> None:
    """CLI: tail the score history for a harness run."""
    scores_path = Path(output_dir) / ".pge_state" / "scores.jsonl"
    if not scores_path.exists():
        print(f"No scores log at {scores_path}")
        return
    print(f"Score history from {scores_path}:\n")
    with scores_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                s = json.loads(line)
                print(
                    f"  sprint={s.get('sprint_id','')[:8]}  "
                    f"R{s.get('round_index')}  "
                    f"weighted={s.get('weighted_score')}  "
                    f"{'PASS' if s.get('passed') else 'fail'}  "
                    f"critique={s.get('critique','')[:60]}"
                )
            except json.JSONDecodeError:
                continue
