"""Goodworks-first DGM service.

This is the first executable slice of the product thesis:

    Dharma Swarm is a telos-gated DGM Goodworks Intelligence Core.

The service scores real Goodworks MRV substrate from existing ledgers, compiles
small wiki/context receipts from existing docs, and can invoke the existing DGM
loop only in shadow mode. It intentionally avoids creating a new agent runner,
task board, ledger, or evolution engine.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dharma_swarm.ai_reciprocity_ledger import AIReciprocityLedger, OutcomeStatus
from dharma_swarm.api_key_audit import configured_key_names
from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.gaia_ledger import GaiaLedger
from dharma_swarm.goodworks_dgm.models import (
    AutoResearchReceipt,
    DGMRunReceipt,
    GoalRun,
    GoalRunStatus,
    GoalSpec,
    GoodworksMetricSnapshot,
    MutationMode,
    WikiContextReceipt,
    utc_now_iso,
)

GOODWORKS_DGM_THESIS = (
    "Dharma Swarm is a telos-gated DGM Goodworks Intelligence Core: "
    "agent-first infrastructure for verifiable welfare, ecological MRV, "
    "and regenerative coordination."
)

WIKI_CONTEXT_SOURCES = (
    "WHAT_IT_WANTS_TO_BECOME.md",
    "CLAUDE.md",
    "docs/loomwork/wiki_weaving_engine.md",
    "docs/reports/JAGAT_KALYAN_RECIPROCITY_COMMONS_2026-03-11.md",
    "docs/reports/GAIA_ECO_CONCEPTUAL_FRAMEWORK_2026-03-27.md",
    "docs/telos-engine/08_SATTVA_ECONOMICS.md",
    "docs/governance/SOVEREIGN_MANIFEST.md",
)

WIKI_KEYWORDS = (
    "goodworks",
    "jagat",
    "kalyan",
    "mrv",
    "gaia",
    "reciprocity",
    "ledger",
    "dgm",
    "telos",
    "welfare",
    "carbon",
    "verification",
)


class GoodworksDGMService:
    """Bounded Goodworks goal loop over the existing Dharma substrate."""

    def __init__(
        self,
        state_dir: Path | None = None,
        ledger_root: Path | None = None,
        repo_root: Path | None = None,
    ) -> None:
        env_state_dir = os.getenv("DHARMA_GOODWORKS_DGM_STATE_DIR")
        self.state_dir = (
            state_dir
            or (Path(env_state_dir) if env_state_dir else dharma_state_dir() / "goodworks_dgm")
        )
        self.ledger_root = ledger_root or dharma_state_dir()
        self.repo_root = repo_root or Path(__file__).resolve().parents[2]
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.receipt_dir = self.state_dir / "receipts"
        self.receipt_dir.mkdir(parents=True, exist_ok=True)
        self.goals_path = self.state_dir / "goals.jsonl"
        self.runs_path = self.state_dir / "runs.jsonl"
        self.receipts_path = self.state_dir / "receipts.jsonl"

    async def create_goal(self, spec: GoalSpec, run_now: bool = True) -> GoalRun:
        self._append_jsonl(self.goals_path, spec.model_dump(mode="json"))
        run = GoalRun(spec=spec)
        if run_now:
            run = await self.run_goal(run)
        else:
            run.next_required_action = "Call run_goal or POST with run_now=true."
            self._persist_run(run)
        return run

    async def run_goal(self, run: GoalRun) -> GoalRun:
        run.status = GoalRunStatus.RUNNING
        try:
            run.metrics = self.score_goodworks_mrv()
            run.latest_score = self._score_snapshot(run.metrics)
            run.wiki_receipt = self.compile_wiki_context(run.spec)
            run.receipts.append(run.wiki_receipt.model_dump(mode="json"))
            self._persist_receipt(run.wiki_receipt.model_dump(mode="json"))
            run.autoresearch_receipt = self.compile_autoresearch_plan(run.spec)
            run.receipts.append(run.autoresearch_receipt.model_dump(mode="json"))
            self._persist_receipt(run.autoresearch_receipt.model_dump(mode="json"))

            if run.spec.mutation_mode == MutationMode.SHADOW:
                run.dgm_receipt = await self._run_shadow_dgm(run.spec, run.metrics)
                run.receipts.append(run.dgm_receipt.model_dump(mode="json"))
                self._persist_receipt(run.dgm_receipt.model_dump(mode="json"))
                if not run.dgm_receipt.success and run.dgm_receipt.error:
                    run.status = GoalRunStatus.BLOCKED
                    run.error = run.dgm_receipt.error
                    run.next_required_action = (
                        "Inspect the shadow DGM error; no code was mutated."
                    )
                else:
                    run.status = GoalRunStatus.SUCCEEDED
                    run.next_required_action = (
                        "Review the shadow DGM receipt before considering live autonomy gates."
                    )
            else:
                run.status = GoalRunStatus.SUCCEEDED
                run.next_required_action = (
                    "Dry-run complete. Use shadow mode only after reviewing metrics and wiki receipt."
                )
        except Exception as exc:
            run.status = GoalRunStatus.FAILED
            run.error = f"{type(exc).__name__}: {exc}"
            run.next_required_action = "Fix the failing Goodworks DGM substrate check."
        run.completed_at = run.completed_at or utc_now_iso()
        self._persist_run(run)
        return run

    def status(self, limit: int = 10) -> dict[str, Any]:
        runs = [GoalRun.model_validate(item) for item in self._read_jsonl(self.runs_path)]
        recent = runs[-limit:]
        latest = recent[-1] if recent else None
        current_metrics = self.score_goodworks_mrv()
        return {
            "thesis": GOODWORKS_DGM_THESIS,
            "state_dir": str(self.state_dir),
            "allowed_mutation_modes": [mode.value for mode in MutationMode],
            "live_mutation_exposed": False,
            "default_domain": "goodworks_mrv",
            "provider_key_truth": self.provider_key_truth(),
            "current_metrics": current_metrics.model_dump(mode="json"),
            "run_count": len(runs),
            "last_run": latest.model_dump(mode="json") if latest else None,
            "recent_runs": [run.model_dump(mode="json") for run in recent],
        }

    def recent_receipts(self, limit: int = 20) -> list[dict[str, Any]]:
        receipts = self._read_jsonl(self.receipts_path)
        return receipts[-limit:]

    def provider_key_truth(self) -> dict[str, Any]:
        configured = configured_key_names()
        return {
            "repo_contains_key_values": False,
            "local_configured_key_names": configured,
            "local_configured_key_count": len(configured),
            "remote_agent_note": (
                "GitHub only proves code and env-var names. Provider key presence is "
                "machine-local; remote agents must not infer missing keys from the repo."
            ),
        }

    def score_goodworks_mrv(self) -> GoodworksMetricSnapshot:
        warnings: list[str] = []

        reciprocity = AIReciprocityLedger(
            data_dir=self.ledger_root / "ai_reciprocity_ledger"
        )
        reciprocity.load()
        reciprocity_summary = reciprocity.summary()

        gaia = GaiaLedger(data_dir=self.ledger_root / "gaia_ledger")
        gaia.load()
        gaia_summary = gaia.summary()

        if reciprocity_summary["entries"] == 0:
            warnings.append("ai_reciprocity_ledger has no entries")
        if gaia_summary["entries"] == 0:
            warnings.append("gaia_ledger has no entries")

        verified_outcomes = sum(
            1
            for outcome in reciprocity._outcomes.values()
            if outcome.status == OutcomeStatus.VERIFIED
        )

        issue_codes = [
            str(issue.get("code", "unknown_reciprocity_issue"))
            for issue in reciprocity_summary.get("issues", [])
        ]
        issue_codes.extend(
            str(violation.get("law", "unknown_conservation_violation"))
            for violation in gaia_summary.get("violations", [])
        )

        return GoodworksMetricSnapshot(
            reciprocity_chain_valid=bool(reciprocity_summary["chain_valid"]),
            gaia_chain_valid=bool(gaia_summary["chain_valid"]),
            reciprocity_entries=int(reciprocity_summary["entries"]),
            gaia_entries=int(gaia_summary["entries"]),
            verified_outcomes=verified_outcomes,
            evidence_records=int(reciprocity_summary["evidence"]),
            audit_records=int(reciprocity_summary["audits"]),
            verified_offsets_tco2e=float(gaia_summary["total_verified_offset"]),
            net_carbon_position_tco2e=float(gaia_summary["net_carbon_position"]),
            routed_usd=float(reciprocity_summary["total_routed_usd"]),
            obligation_usd=float(reciprocity_summary["total_obligation_usd"]),
            invariant_issue_count=int(reciprocity_summary["invariant_issues"]),
            conservation_violation_count=int(gaia_summary["conservation_violations"]),
            issue_codes=issue_codes,
            warnings=warnings,
        )

    def compile_wiki_context(self, spec: GoalSpec) -> WikiContextReceipt:
        selected_sources: list[str] = []
        patterns: list[str] = []
        atom_count = 0
        warnings: list[str] = []
        requested = f"{spec.title}\n{spec.objective}\n{spec.success_metric}".lower()

        for relative_path in WIKI_CONTEXT_SOURCES:
            path = self.repo_root / relative_path
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            lower_text = text.lower()
            source_hits = [
                keyword
                for keyword in WIKI_KEYWORDS
                if keyword in lower_text or keyword in requested
            ]
            if not source_hits:
                continue
            selected_sources.append(relative_path)
            patterns.extend(source_hits[:5])
            atom_count += self._count_context_atoms(text, source_hits)

        if not selected_sources:
            warnings.append("no wiki/context source matched the Goodworks DGM goal")

        return WikiContextReceipt(
            goal_id=spec.goal_id,
            source_count=len(selected_sources),
            atom_count=atom_count,
            selected_sources=selected_sources,
            patterns=sorted(set(patterns)),
            warnings=warnings,
        )

    def compile_autoresearch_plan(self, spec: GoalSpec) -> AutoResearchReceipt:
        """Bind the Karpathy-style AutoResearch loop into the goal surface.

        V1 does not invoke the loop from the API. It records the exact mutable
        modules the existing loop would be allowed to inspect for this goal,
        keeping execution dry-run until an operator explicitly opens shadow
        or live evolution gates.
        """
        warnings: list[str] = []
        try:
            from dharma_swarm.autoresearch_loop import (
                IMMUTABLE_FILES,
                LoopConfig,
                get_mutable_modules,
            )

            target_names = {
                "service.py",
                "ai_reciprocity_ledger.py",
                "gaia_ledger.py",
                "gaia_platform.py",
                "dgm_loop.py",
                "evaluation_registry.py",
            }
            candidates = [
                path
                for path in get_mutable_modules()
                if path.name in target_names or "goodworks_dgm" in path.parts
            ]
            config = LoopConfig(
                dry_run=True,
                max_iterations=min(spec.budget_iterations, 5),
                sleep_between_sec=0.0,
                target_modules=sorted({path.name for path in candidates}),
            )
            if not candidates:
                warnings.append("autoresearch_loop found no Goodworks candidate modules")
            return AutoResearchReceipt(
                goal_id=spec.goal_id,
                dry_run=config.dry_run,
                loop_invoked=False,
                candidate_count=len(candidates),
                target_modules=[
                    str(path.relative_to(self.repo_root))
                    if path.is_relative_to(self.repo_root)
                    else str(path)
                    for path in candidates[:20]
                ],
                immutable_files=sorted(IMMUTABLE_FILES),
                summary=(
                    "AutoResearch loop bound as dry-run candidate planner; "
                    "no mutation or test loop invoked by the API."
                ),
                warnings=warnings,
            )
        except Exception as exc:
            return AutoResearchReceipt(
                goal_id=spec.goal_id,
                summary="AutoResearch planning failed before invocation.",
                warnings=[f"{type(exc).__name__}: {exc}"],
            )

    async def _run_shadow_dgm(
        self, spec: GoalSpec, metrics: GoodworksMetricSnapshot
    ) -> DGMRunReceipt:
        from dharma_swarm.dgm_loop import run_dgm_evolution_task

        context = (
            f"Goodworks MRV goal: {spec.title}. Objective: {spec.objective}. "
            f"Current score: {self._score_snapshot(metrics):.3f}. "
            f"Ledger entries: reciprocity={metrics.reciprocity_entries}, "
            f"gaia={metrics.gaia_entries}. Issues: {metrics.issue_codes or 'none'}. "
            "Operate only in shadow mode and prefer existing Goodworks MRV wiring."
        )
        result = await run_dgm_evolution_task(
            source_file=None,
            fitness_context=context,
            n_generations=spec.budget_iterations,
            shadow=True,
            state_dir=self.state_dir,
        )
        return DGMRunReceipt(
            goal_id=spec.goal_id,
            shadow_mode=bool(result.get("shadow_mode", True)),
            source_file=str(result.get("source_file") or ""),
            fitness_delta=float(result.get("fitness_delta", result.get("avg_fitness_delta", 0.0)) or 0.0),
            applied=bool(result.get("applied", False)),
            rolled_back=bool(result.get("rolled_back", False)),
            lineage_depth=int(result.get("lineage_depth", 0) or 0),
            archive_growth=int(result.get("archive_growth", 0) or 0),
            success=bool(result.get("success", False)),
            error=result.get("error"),
        )

    def _score_snapshot(self, metrics: GoodworksMetricSnapshot) -> float:
        score = 0.0
        score += min(metrics.reciprocity_entries, 50) / 250
        score += min(metrics.gaia_entries, 50) / 250
        score += min(metrics.evidence_records, 20) / 100
        score += min(metrics.audit_records, 20) / 100
        score += min(metrics.verified_outcomes, 20) / 100
        score += 0.1 if metrics.reciprocity_chain_valid else -0.2
        score += 0.1 if metrics.gaia_chain_valid else -0.2
        score -= min(metrics.invariant_issue_count, 10) / 100
        score -= min(metrics.conservation_violation_count, 10) / 100
        return max(0.0, min(1.0, score))

    def _count_context_atoms(self, text: str, keywords: list[str]) -> int:
        count = 0
        for line in text.splitlines():
            stripped = line.strip()
            lower = stripped.lower()
            if stripped.startswith("#") and any(keyword in lower for keyword in keywords):
                count += 1
            elif any(keyword in lower for keyword in keywords):
                count += 1
        return count

    def _persist_run(self, run: GoalRun) -> None:
        self._append_jsonl(self.runs_path, run.model_dump(mode="json"))

    def _persist_receipt(self, receipt: dict[str, Any]) -> None:
        self._append_jsonl(self.receipts_path, receipt)

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    rows.append(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
        return rows
