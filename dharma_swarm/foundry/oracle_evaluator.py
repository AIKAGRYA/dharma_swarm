"""The real evaluator — applies a candidate diff and runs the target's oracle.

This is the muscle the readiness audit found missing: the bridge from a
:class:`~dharma_swarm.foundry.evaluator.Candidate` (a unified diff) to an
actual score from the target's own test/benchmark command, executed under the
strongest available isolation.

Discipline per evaluation:

1. Fresh scratch copy of the pinned tree (the pinned checkout is never touched).
2. ``git apply --check`` then ``git apply`` — a diff that does not apply cleanly
   scores zero (``apply_failed``), it does not crash the loop.
3. The oracle runs via :func:`run_isolated` — Docker ``--network none``,
   read-only workdir when the suite tolerates it (prevention), otherwise
   read-write with a post-run tamper digest over every non-evolve path
   (detection). Either way, a candidate that rewrites the oracle mid-run
   cannot keep a score: ``oracle_tampered`` zeroes it.
4. Fitness is gated on correctness: the oracle must exit 0 (zero regressions)
   before any score counts.
5. The receipt gets the truth: the ACTUAL isolation level and tamper mode that
   ran are reported in ``EvalMetrics.metrics`` / ``notes`` — never asserted.

Baseline: :meth:`OracleEvaluator.prepare` runs the oracle once on the clean
tree and refuses to proceed if the target is already broken.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from dharma_swarm.foundry.evaluator import Candidate, EvalMetrics
from dharma_swarm.foundry.runner_isolation import (
    IsolationPolicy,
    RunResult,
    promotion_allowed,
    run_isolated,
)

# Sentinel line an oracle command can print to hand structured metrics back:
#   FOUNDRY_METRICS {"combined_score": 0.87, ...}
METRICS_SENTINEL = "FOUNDRY_METRICS"
_SENTINEL_RE = re.compile(re.escape(METRICS_SENTINEL) + r"\s+(\{.*\})")

MetricParser = Callable[[RunResult], EvalMetrics]


def sentinel_metrics_parser(primary_key: str = "combined_score") -> MetricParser:
    """Parse ``FOUNDRY_METRICS {json}`` from oracle stdout.

    Correctness requires exit 0 AND a parseable sentinel with ``primary_key``.
    """

    def parse(result: RunResult) -> EvalMetrics:
        if result.exit_code != 0 or result.timed_out:
            return EvalMetrics(0.0, False, notes=f"oracle exit={result.exit_code}"
                                                 f"{' timeout' if result.timed_out else ''}")
        m = _SENTINEL_RE.search(result.stdout)
        if not m:
            return EvalMetrics(0.0, False, notes="no FOUNDRY_METRICS sentinel in oracle output")
        try:
            data = json.loads(m.group(1))
            score = float(data[primary_key])
        except (ValueError, KeyError, TypeError) as exc:
            return EvalMetrics(0.0, False, notes=f"bad sentinel payload: {type(exc).__name__}")
        return EvalMetrics(
            primary_score=score,
            correctness_passed=True,
            metrics={k: float(v) for k, v in data.items()
                     if isinstance(v, (int, float))},
            wall_clock_s=result.duration_s,
        )

    return parse


def suite_pass_parser() -> MetricParser:
    """Zero-regression oracle: exit 0 = correct; score is inverse duration.

    Suitable when the objective is 'make the suite faster without breaking it'.
    The loop compares scores across candidates; the baseline anchors deltas.
    """

    def parse(result: RunResult) -> EvalMetrics:
        ok = result.exit_code == 0 and not result.timed_out
        score = (1.0 / result.duration_s) if ok and result.duration_s > 0 else 0.0
        return EvalMetrics(primary_score=score, correctness_passed=ok,
                           metrics={"duration_s": result.duration_s},
                           wall_clock_s=result.duration_s)

    return parse


def apply_diff(tree: Path, diff: str,
               runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
               *, check_only: bool = False) -> str | None:
    """Apply a unified diff to ``tree``. Returns None on success, reason on failure.

    Two appliers, strict first: ``git apply`` (exact context), then
    ``patch --fuzz=3`` (tolerates the slightly-shifted line numbers LLM diffs
    commonly carry — 74/78 candidates died at ring 1 in the first campaign,
    largely as apply failures). Fuzz never changes WHAT is applied, only how
    much surrounding drift is tolerated; the oracle still judges the result.
    """
    if not diff.strip():
        return "empty diff"
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as fh:
        fh.write(diff if diff.endswith("\n") else diff + "\n")
        patch_path = fh.name

    def _run(cmd: list[str]) -> tuple[int, str]:
        proc = runner(cmd, capture_output=True, text=True, timeout=30)
        return (getattr(proc, "returncode", 1),
                (getattr(proc, "stderr", "") or getattr(proc, "stdout", "") or "").strip()[:200])

    try:
        rc, err_git = _run(["git", "apply", "--check", "--unsafe-paths",
                            "--directory", str(tree), patch_path])
        if rc == 0:
            if check_only:
                return None
            rc, err = _run(["git", "apply", "--unsafe-paths",
                            "--directory", str(tree), patch_path])
            return None if rc == 0 else f"apply failed: {err}"

        # Fallback: fuzz-tolerant patch(1).
        rc, err_patch = _run(["patch", "-p1", "--forward", "--fuzz=3", "--dry-run",
                              "-d", str(tree), "-i", patch_path])
        if rc != 0:
            return f"apply --check failed: {err_git} | patch fallback: {err_patch}"
        if check_only:
            return None
        rc, err = _run(["patch", "-p1", "--forward", "--fuzz=3",
                        "-d", str(tree), "-i", patch_path])
        return None if rc == 0 else f"patch apply failed: {err}"
    except (subprocess.SubprocessError, OSError) as exc:
        return f"apply error: {type(exc).__name__}"
    finally:
        Path(patch_path).unlink(missing_ok=True)


@dataclass
class OracleEvaluator:
    """Evaluator protocol implementation backed by the target's own oracle."""

    evaluator_id: str
    pinned_root: Path
    oracle_cmd: list[str] | str
    evolve_paths: list[str] = field(default_factory=list)
    metric_parser: MetricParser = field(default_factory=sentinel_metrics_parser)
    policy: IsolationPolicy = field(default_factory=IsolationPolicy)
    scratch_root: Path | None = None
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run
    docker_ok: bool | None = None

    baseline: EvalMetrics | None = None
    last_isolation_level: str = ""
    last_promotion_allowed: bool = False
    _oracle_digest_baseline: str = ""

    def _scratch(self) -> Path:
        root = Path(self.scratch_root) if self.scratch_root else Path(tempfile.gettempdir()) / "foundry_scratch"
        root.mkdir(parents=True, exist_ok=True)
        dest = Path(tempfile.mkdtemp(prefix="cand_", dir=root))
        shutil.rmtree(dest)
        shutil.copytree(self.pinned_root, dest,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv"))
        return dest

    def _digest_excluding_evolve(self, tree: Path) -> str:
        """Digest over everything OUTSIDE the evolve scope (the oracle+tests).

        This is the tamper reference: these files must be byte-identical
        before and after an oracle run, or the score cannot be trusted.
        """
        import hashlib

        tree = Path(tree)
        prefixes = [p.rstrip("*").rstrip("/") for p in (self.evolve_paths or [])]
        entries: list[str] = []
        for file in sorted(tree.rglob("*")):
            if not file.is_file():
                continue
            rel = file.relative_to(tree).as_posix()
            if any(part in {".git", "__pycache__", ".venv"} for part in file.relative_to(tree).parts):
                continue
            if any(rel == p or rel.startswith(p + "/") for p in prefixes):
                continue  # evolve scope: the candidate is ALLOWED to differ here
            entries.append(f"{rel}:{hashlib.sha256(file.read_bytes()).hexdigest()}")
        return "sha256:" + hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()

    def _run_oracle(self, tree: Path) -> RunResult:
        result = run_isolated(self.oracle_cmd, str(tree), self.policy,
                              docker_ok=self.docker_ok, runner=self.runner)
        self.last_isolation_level = result.isolation_level
        self.last_promotion_allowed = promotion_allowed(result)
        return result

    def prepare(self) -> None:
        """Capture the clean-tree baseline; refuse a target that is already red."""
        tree = self._scratch()
        try:
            pre_excl = self._digest_excluding_evolve(tree)
            result = self._run_oracle(tree)
            metrics = self.metric_parser(result)
            if not metrics.correctness_passed:
                raise RuntimeError(
                    f"baseline oracle failed on clean tree ({metrics.notes}); "
                    "target is broken or oracle_cmd is wrong — refusing to campaign"
                )
            self._oracle_digest_baseline = pre_excl
            # A suite that writes into its own tree defeats the digest-based
            # tamper gate; record it honestly so evaluate() knows detection is
            # weakened and only prevention-mode (:ro) results may promote.
            if self._digest_excluding_evolve(tree) != pre_excl:
                metrics = EvalMetrics(
                    metrics.primary_score, True, metrics.metrics,
                    metrics.wall_clock_s,
                    notes=(metrics.notes + " | oracle writes to its own tree; "
                           "digest tamper-detection unavailable — require "
                           "readonly_workdir for promotion").strip(" |"),
                )
            self.baseline = metrics
        finally:
            shutil.rmtree(tree, ignore_errors=True)

    def evaluate(self, candidate: Candidate, *, seed: int) -> EvalMetrics:
        tree = self._scratch()
        try:
            failure = apply_diff(tree, candidate.diff, self.runner)
            if failure is not None:
                return EvalMetrics(0.0, False, notes=f"apply_failed: {failure}")

            pre_excl = self._digest_excluding_evolve(tree)
            result = self._run_oracle(tree)
            metrics = self.metric_parser(result)

            # Tamper gate: files outside the evolve scope must be byte-identical
            # after the run. Prevention (:ro mount) makes this impossible by
            # construction; detection (digest) zeroes the score after the fact.
            baseline_writes = bool(self.baseline and "writes to its own tree" in (self.baseline.notes or ""))
            if (not self.policy.readonly_workdir
                    and not baseline_writes
                    and self._digest_excluding_evolve(tree) != pre_excl):
                return EvalMetrics(0.0, False, metrics=metrics.metrics,
                                   notes="oracle_tampered: non-evolve files changed during run")

            return EvalMetrics(
                primary_score=metrics.primary_score,
                correctness_passed=metrics.correctness_passed,
                metrics={**metrics.metrics,
                         "promotion_allowed": 1.0 if self.last_promotion_allowed else 0.0},
                wall_clock_s=metrics.wall_clock_s,
                notes=(metrics.notes + f" | isolation={self.last_isolation_level}").strip(" |"),
            )
        finally:
            shutil.rmtree(tree, ignore_errors=True)
