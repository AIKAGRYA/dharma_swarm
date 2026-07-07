"""G1 — the git-history repo gym: real merged fixes as frozen, scored tasks.

Ratified spec: Inward-Ascent dossier §(b) G1 + elevation spec E5/E1. Every
landed merge that shipped test files is a solved task with ground truth: the
tests that actually landed. The solver sees the repo AT THE MERGE BASE plus
the merge's prompt; the deterministic scorer overlays ONLY the landed test
files and runs them against the candidate diff.

Leak guard (adversary kill-rule): the solver sandbox is a ``git archive``
tree export of the base commit — it contains NO ``.git`` directory, so no
future object (including the landed fix) is reachable by construction. A
sandbox found to contain ``.git`` voids the task.

Trace mandate (E5): ``run_gym`` refuses to score without writing a
``chamber_gym_trace.v1`` corpus and pinning its sha256 in the run receipt.

Aggregation honesty: v0 aggregation is ``oracle_argmax_v0`` (best-scoring
seat) — a TRAIN-SIGNAL rule, never a capability rule; the receipt says so.
Per-seat correctness labels are what the E1 transcendence decomposition
consumes.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from dharma_swarm.chamber.sandbox import (
    DiffPolicyError,
    assert_within,
    diff_policy_reason,
    find_symlinks,
    scrubbed_env,
)
from dharma_swarm.chamber.traces import (
    GymTraceRow,
    SeatAnswer,
    stable_digest,
    write_corpus,
)

ENV_ID = "g1_git_history"
TASKPACK_SCHEMA = "chamber_g1_taskpack.v1"
RUN_RECEIPT_SCHEMA = "chamber_gym_run.v1"
AGGREGATION_RULE = "oracle_argmax_v0 (train-signal only, not a capability rule)"
PASS_THRESHOLD = 1.0  # all landed tests must pass for a candidate to be correct


def _git(repo: Path, *args: str, timeout: int = 120) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:400]}")
    return proc.stdout


def scorer_hash() -> str:
    """sha256 of this module's bytes — the scorer's replay identity."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _is_test_file(path: str) -> bool:
    """pytest's default python_files is BOTH ``test_*.py`` and ``*_test.py`` —
    matching only the former silently drops half the possible ground-truth
    tests, letting an incomplete candidate score correct (review R1-6)."""
    name = path.rsplit("/", 1)[-1]
    return name.endswith(".py") and (name.startswith("test_")
                                     or name.endswith("_test.py"))


def _exists_at(repo_root: Path, sha: str, rel: str) -> bool:
    """Does blob ``rel`` exist at commit ``sha``? A landed test that was
    RENAMED or DELETED by the merge appears in --name-only but is absent at
    merge_sha; scoring it would crash the whole run (review R1-7)."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{sha}:{rel}"],
        capture_output=True, timeout=30,
    )
    return proc.returncode == 0


@dataclass(frozen=True, slots=True)
class Task:
    task_id: str
    merge_sha: str
    base_sha: str
    merged_at: str
    prompt: str
    test_files: tuple[str, ...]


@dataclass(slots=True)
class Taskpack:
    snapshot_sha: str
    tasks: list[Task]
    held_out_ids: tuple[str, ...]
    schema: str = TASKPACK_SCHEMA

    def taskpack_sha(self) -> str:
        body = {
            "schema": self.schema,
            "snapshot_sha": self.snapshot_sha,
            "tasks": [asdict(t) for t in self.tasks],
            "held_out_ids": list(self.held_out_ids),
        }
        return stable_digest(body)

    def train_tasks(self) -> list[Task]:
        held = set(self.held_out_ids)
        return [t for t in self.tasks if t.task_id not in held]


def build_taskpack(repo_root: Path, snapshot_sha: str, *, limit: int | None = None,
                   holdout_fraction: float = 0.3, seed: int = 7) -> Taskpack:
    """Walk first-parent merges at a PINNED snapshot; each merge that landed
    >=1 test file becomes an immutable task. Held-out split is seeded and
    stratified by date order (never trained/selected on — discipline 2)."""
    out = _git(repo_root, "log", "--merges", "--first-parent",
               "--format=%H %P %cI", snapshot_sha)
    tasks: list[Task] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        merge_sha, base_sha, merged_at = parts[0], parts[1], parts[-1]
        changed = _git(repo_root, "diff", "--name-only", base_sha, merge_sha)
        # Only tests that still EXIST at the merge (drop renamed-away/deleted
        # paths that would crash the scorer's `git show merge:path`).
        test_files = tuple(sorted(
            p for p in changed.splitlines()
            if _is_test_file(p) and _exists_at(repo_root, merge_sha, p)))
        if not test_files:
            continue
        prompt = _git(repo_root, "log", "-1", "--format=%B", merge_sha).strip()
        tasks.append(Task(
            task_id=f"g1-{merge_sha[:12]}", merge_sha=merge_sha, base_sha=base_sha,
            merged_at=merged_at, prompt=prompt, test_files=test_files,
        ))
        if limit is not None and len(tasks) >= limit:
            break
    tasks.sort(key=lambda t: (t.merged_at, t.task_id))
    # Stratified-by-date held-out: seeded round-robin over date quartiles up to
    # a GLOBAL target, always leaving >=1 train task (a pack that is all
    # held-out is a pack that cannot train anything).
    held: list[str] = []
    target = min(round(len(tasks) * holdout_fraction), max(0, len(tasks) - 1))
    if tasks and target > 0:
        rng = random.Random(seed)
        quartiles: list[list[Task]] = [[] for _ in range(4)]
        for i, t in enumerate(tasks):
            quartiles[min(3, i * 4 // len(tasks))].append(t)
        pools = [rng.sample(q, len(q)) for q in quartiles if q]
        while len(held) < target and any(pools):
            for pool in pools:
                if pool and len(held) < target:
                    held.append(pool.pop().task_id)
    return Taskpack(snapshot_sha=snapshot_sha, tasks=tasks,
                    held_out_ids=tuple(sorted(held)))


def write_holdout_seal(pack: Taskpack, path: Path) -> dict[str, Any]:
    """Seal the held-out ids OUTSIDE any solver context, digest-stamped."""
    seal = {"schema": "chamber_g1_holdout_seal.v1",
            "taskpack_sha": pack.taskpack_sha(),
            "held_out_ids": list(pack.held_out_ids)}
    seal["digest"] = stable_digest(seal)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return seal


def export_sandbox(repo_root: Path, base_sha: str, dest: Path) -> Path:
    """Solver sandbox = tree export at base. NO .git inside — the leak guard.

    ``git archive`` reads objects from repo_root but the export carries no
    repository, so the landed fix and all future history are unreachable
    from inside the sandbox by construction.

    The sandbox is always a CLEAN tree of exactly ``base_sha``: any existing
    ``dest`` (e.g. from an interrupted retry on a deterministic path) is
    removed first, so stale non-``.git`` files can never contaminate solver
    visibility or the scorer (review: Greptile PR #830)."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "-C", str(repo_root), "archive", base_sha],
        capture_output=True, timeout=300,
    )
    if archive.returncode != 0:
        raise RuntimeError(f"git archive failed: {archive.stderr.decode()[:400]}")
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout,
                   check=True, timeout=300)
    assert_leak_free(dest)
    return dest


def assert_leak_free(sandbox: Path) -> None:
    """A sandbox containing any git repository voids the task (kill rule)."""
    if any(p.name == ".git" for p in sandbox.rglob(".git")):
        raise LeakError(f"sandbox {sandbox} contains a .git — task VOID")


class LeakError(RuntimeError):
    """The leak guard tripped: future history was reachable from a sandbox."""


@dataclass(frozen=True, slots=True)
class ScoreResult:
    passed: int
    failed: int
    errored: bool
    detail: str

    @property
    def total(self) -> int:
        return self.passed + self.failed

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def correct(self) -> bool:
        return not self.errored and self.total > 0 and self.pass_rate >= PASS_THRESHOLD


def score_candidate(repo_root: Path, task: Task, candidate_diff: str,
                    workdir: Path, *, timeout: int = 300) -> ScoreResult:
    """Deterministic scorer: base tree + candidate diff + ONLY the landed test
    files at the merge sha -> pytest pass-rate. The landed source diff (the
    answer key) is never materialized."""
    scoring_dir = export_sandbox(repo_root, task.base_sha, workdir / "scoring")
    env = scrubbed_env(scoring_dir)
    try:
        if candidate_diff.strip():
            reason = diff_policy_reason(candidate_diff)
            if reason:
                return ScoreResult(0, 0, True, f"diff policy: {reason}")
            apply = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", "-"],
                input=candidate_diff, text=True, capture_output=True,
                cwd=scoring_dir, timeout=60, env=env,
            )
            if apply.returncode != 0:
                return ScoreResult(0, 0, True,
                                   f"diff does not apply: {apply.stderr.strip()[:300]}")
            # Defense in depth: a diff that slipped a symlink past the policy
            # (or an in-tree symlink) must void the task before any write.
            leaks = find_symlinks(scoring_dir)
            if leaks:
                return ScoreResult(0, 0, True,
                                   f"diff introduced symlink(s): {leaks[0]} — VOID")
        for rel in task.test_files:
            if not _exists_at(repo_root, task.merge_sha, rel):
                return ScoreResult(0, 0, True,
                                   f"landed test {rel} absent at merge — task VOID")
            blob = _git(repo_root, "show", f"{task.merge_sha}:{rel}")
            target = scoring_dir / rel
            assert_within(scoring_dir, target.parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            assert_within(scoring_dir, target)
            target.write_text(blob, encoding="utf-8")
        proc = subprocess.run(
            ["python3", "-m", "pytest", *task.test_files, "-q", "--no-header",
             "-p", "no:cacheprovider"],
            capture_output=True, text=True, cwd=scoring_dir, timeout=timeout,
            env=env,
        )
        passed, failed, errored = _parse_pytest_summary(proc.stdout)
        tail = (proc.stdout + proc.stderr)[-400:]
        if errored or (passed == 0 and failed == 0):
            return ScoreResult(0, 0, True, f"no tests collected/ran: {tail}")
        return ScoreResult(passed, failed, False, tail)
    except DiffPolicyError as exc:
        return ScoreResult(0, 0, True, f"sandbox policy: {exc}")
    except subprocess.TimeoutExpired:
        return ScoreResult(0, 0, True, "scorer timeout")
    finally:
        shutil.rmtree(scoring_dir, ignore_errors=True)


_SUMMARY_RE = re.compile(r"(\d+) (passed|failed|error|errors|xfailed|xpassed)\b")


def _parse_pytest_summary(stdout: str) -> tuple[int, int, bool]:
    """Parse (passed, failed, errored) from pytest's SUMMARY line only.

    pytest prints the tally on the last non-empty output line (e.g.
    ``1 failed, 2 passed in 0.3s``). Scanning all of stdout would let a test
    body that prints ``5 passed`` poison the count (review R1-4), so we read
    only the summary line and word-boundary-match to avoid xfailed/xpassed
    bleeding into failed/passed."""
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    if not lines:
        return 0, 0, False
    summary = lines[-1]
    counts: dict[str, int] = {}
    for n, word in _SUMMARY_RE.findall(summary):
        counts[word] = counts.get(word, 0) + int(n)
    passed = counts.get("passed", 0)
    failed = counts.get("failed", 0)
    errored = counts.get("error", 0) + counts.get("errors", 0) > 0
    return passed, failed, errored


class Solver(Protocol):
    def __call__(self, seat_id: str, task_payload: dict[str, Any],
                 sandbox: Path) -> dict[str, Any]: ...


def fixture_solver(answers: dict[str, dict[str, str]]) -> Solver:
    """Deterministic test solver: answers[task_id][seat_id] -> diff."""
    def _solve(seat_id: str, task_payload: dict[str, Any],
               sandbox: Path) -> dict[str, Any]:
        diff = answers.get(task_payload["task_id"], {}).get(seat_id, "")
        return {"answer": diff, "model": f"fixture:{seat_id}", "provider": "fixture"}
    return _solve


def live_solver_status() -> tuple[bool, str]:
    """Live seats go through the ONE model door only when keys dispatch.
    The live solver lane itself is track next-item 2 (operator keys/compute);
    reporting honestly beats pretending."""
    try:
        from dharma_swarm.key_oracle import dispatchable_now
        ready = bool(dispatchable_now())
    except Exception as exc:  # noqa: BLE001 — status probe, reason is recorded
        return False, f"key_oracle unavailable: {type(exc).__name__}"
    if not ready:
        return False, "no dispatchable provider keys on this host (needs_host)"
    return False, "keys dispatchable but live solver lane lands with track next-item 2"


def run_gym(repo_root: Path, pack: Taskpack, solver: Solver, seats: list[str],
            out_dir: Path, *, seed: int = 7, task_ids: list[str] | None = None,
            timeout: int = 300) -> dict[str, Any]:
    """Run solver seats over TRAIN tasks, score deterministically, write the
    E5 trace corpus, and return a digest-stamped run receipt that pins it."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pack_sha, oracle = pack.taskpack_sha(), scorer_hash()
    wanted = set(task_ids) if task_ids else None
    rows: list[dict[str, Any]] = []
    per_task: dict[str, bool] = {}
    task_seconds: dict[str, float] = {}
    scored_iterations = 0
    for task in pack.train_tasks():
        if wanted is not None and task.task_id not in wanted:
            continue
        task_start = time.perf_counter()
        sandbox = export_sandbox(repo_root, task.base_sha,
                                 out_dir / "sandbox" / task.task_id)
        payload = {"task_id": task.task_id, "prompt": task.prompt,
                   "base_sha": task.base_sha, "sandbox": str(sandbox)}
        seat_answers: list[SeatAnswer] = []
        best: tuple[float, str, bool] = (-1.0, "", False)
        try:
            for seat in seats:
                result = solver(seat, payload, sandbox)
                diff = str(result.get("answer", ""))
                score = score_candidate(repo_root, task, diff,
                                        out_dir / "score" / task.task_id / seat,
                                        timeout=timeout)
                seat_answers.append(SeatAnswer(
                    seat_id=seat, answer=diff,
                    model=str(result.get("model", "")),
                    provider=str(result.get("provider", "")),
                    correct=score.correct,
                ))
                scored_iterations += 1
                if score.pass_rate > best[0]:
                    best = (score.pass_rate, diff, score.correct)
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)
        task_seconds[task.task_id] = round(time.perf_counter() - task_start, 3)
        per_task[task.task_id] = best[2]
        rows.append(GymTraceRow(
            env_id=ENV_ID, task_id=task.task_id, taskpack_sha=pack_sha,
            scorer_hash=oracle, seed=seed, answers=tuple(seat_answers),
            aggregated_answer=best[1], correct=best[2],
            attributes={"aggregation_rule": AGGREGATION_RULE},
        ).to_dict())
    corpus_path = out_dir / "trace_corpus.jsonl"
    corpus_sha = write_corpus(rows, corpus_path)  # E5: refuses to skip
    receipt: dict[str, Any] = {
        "schema": RUN_RECEIPT_SCHEMA,
        "env_id": ENV_ID,
        "taskpack_sha": pack_sha,
        "scorer_hash": oracle,
        "seed": seed,
        "seats": list(seats),
        "aggregation_rule": AGGREGATION_RULE,
        "tasks_run": len(rows),
        "tasks_correct": sum(1 for v in per_task.values() if v),
        "per_task": per_task,
        "trace_corpus": {"file": corpus_path.name, "rows": len(rows),
                         "sha256": corpus_sha},
        "live_solver": dict(zip(("available", "reason"), live_solver_status())),
        # Compute-ROI declaration (discipline 9): cost-per-scored-iteration
        # measured before any live iteration may claim compliance. Wall-time
        # is host-variable (excluded from the deterministic trace corpus, only
        # in this receipt); token/USD are 0 for fixture/control solvers and
        # populated once the live solver lane (track item 2) runs.
        "compute_roi": {
            "scored_iterations": scored_iterations,
            "wall_seconds_total": round(sum(task_seconds.values()), 3),
            "wall_seconds_per_task": task_seconds,
            "wall_seconds_per_scored_iteration": (
                round(sum(task_seconds.values()) / scored_iterations, 3)
                if scored_iterations else None),
            "tokens_total": 0,
            "usd_total": 0.0,
            "note": "fixture/control solver — zero inference cost; live seats "
                    "populate tokens/usd via the ONE model door.",
        },
        "capability_claim": "NONE — internal gym numbers under a train-signal "
                            "aggregation rule; never a benchmark claim.",
    }
    receipt["digest"] = stable_digest({k: v for k, v in receipt.items()
                                       if k != "digest"})
    (out_dir / "run_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


__all__ = [
    "AGGREGATION_RULE", "ENV_ID", "LeakError", "RUN_RECEIPT_SCHEMA",
    "ScoreResult", "Task", "TASKPACK_SCHEMA", "Taskpack", "assert_leak_free",
    "build_taskpack", "export_sandbox", "fixture_solver", "live_solver_status",
    "run_gym", "score_candidate", "scorer_hash", "write_holdout_seal",
]
