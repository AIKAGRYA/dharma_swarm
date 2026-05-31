"""Dharma-Eval v0: deterministic benchmark receipts for self-evolution.

This module is intentionally small. It gives DGM/Darwin candidates a stable
manifest, split model, scorer, and baseline-vs-candidate scoreboard without
creating a second runner or task board.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from dharma_swarm.models import _new_id, _utc_now

DharmaEvalSplit = Literal["train", "validation", "holdout"]
DharmaEvalOracle = Literal["exact_json", "exact_text", "exit_code"]


def stable_json_hash(value: Any) -> str:
    """Return a stable sha256 hash for JSON-like payloads."""
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


class DharmaEvalTask(BaseModel):
    """Single immutable benchmark task declaration."""

    task_id: str
    split: DharmaEvalSplit
    domain: str
    prompt: str = ""
    fixture_path: str = ""
    fixture_hash: str = ""
    oracle_type: DharmaEvalOracle = "exact_json"
    expected: Any = None
    timeout_seconds: float = 30.0
    sandbox_profile: str = "docker_eval_no_network"
    leak_policy: str = "no_labels_in_candidate_workspace"
    allowed_tools: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task_id", "split", "domain")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("field must be a non-empty string")
        return value.strip()


class DharmaEvalManifest(BaseModel):
    """Collection of immutable benchmark tasks."""

    schema_version: str = "dharma_eval_manifest.v0"
    suite_id: str
    created_at: str = Field(default_factory=lambda: _utc_now().isoformat())
    tasks: list[DharmaEvalTask]
    manifest_hash: str = ""

    @field_validator("suite_id")
    @classmethod
    def _suite_non_empty(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("suite_id must be a non-empty string")
        return value.strip()

    def with_hash(self) -> "DharmaEvalManifest":
        payload = self.model_dump(mode="json")
        payload.pop("manifest_hash", None)
        return self.model_copy(update={"manifest_hash": stable_json_hash(payload)})

    def tasks_for_split(self, split: DharmaEvalSplit) -> list[DharmaEvalTask]:
        return [task for task in self.tasks if task.split == split]


class DharmaEvalScore(BaseModel):
    """Deterministic score for one candidate on one task."""

    score_id: str = Field(default_factory=lambda: f"deval_{_new_id()}")
    suite_id: str
    manifest_hash: str
    task_id: str
    split: DharmaEvalSplit
    candidate_id: str
    passed: bool
    score: float
    oracle_type: DharmaEvalOracle
    duration_seconds: float = 0.0
    cost: float = 0.0
    failure_class: str = ""
    artifact_refs: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: _utc_now().isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)


class DharmaEvalScoreboard(BaseModel):
    """Baseline-vs-candidate summary for a manifest run."""

    scoreboard_id: str = Field(default_factory=lambda: f"scoreboard_{_new_id()}")
    suite_id: str
    manifest_hash: str
    baseline_id: str
    candidate_id: str
    split: DharmaEvalSplit | None = None
    baseline_score: float
    candidate_score: float
    delta: float
    baseline_passed: int
    candidate_passed: int
    task_count: int
    candidate_wins: bool
    created_at: str = Field(default_factory=lambda: _utc_now().isoformat())


def load_manifest(path: Path | str) -> DharmaEvalManifest:
    """Load and hash a JSON Dharma-Eval manifest."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    manifest = DharmaEvalManifest(**payload).with_hash()
    return manifest


def write_manifest(path: Path | str, manifest: DharmaEvalManifest) -> None:
    """Write a canonical JSON manifest with its hash populated."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    hashed = manifest.with_hash()
    target.write_text(
        json.dumps(hashed.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_manifest_fixtures(
    manifest: DharmaEvalManifest,
    *,
    root: Path | str | None = None,
) -> list[str]:
    """Return fixture hash validation errors without mutating state."""
    base = Path(root) if root is not None else Path.cwd()
    errors: list[str] = []
    for task in manifest.tasks:
        if not task.fixture_path or not task.fixture_hash:
            continue
        path = base / task.fixture_path
        if not path.exists():
            errors.append(f"{task.task_id}: fixture missing: {task.fixture_path}")
            continue
        actual = file_sha256(path)
        if actual != task.fixture_hash:
            errors.append(
                f"{task.task_id}: fixture hash mismatch: expected {task.fixture_hash}, got {actual}"
            )
    return errors


def score_output(
    task: DharmaEvalTask,
    candidate_output: Any,
    *,
    candidate_id: str,
    suite_id: str,
    manifest_hash: str,
    duration_seconds: float = 0.0,
    cost: float = 0.0,
    artifact_refs: list[str] | None = None,
) -> DharmaEvalScore:
    """Score one candidate output against a deterministic oracle."""
    start = time.monotonic()
    passed = False
    failure_class = ""

    if task.oracle_type == "exact_json":
        passed = candidate_output == task.expected
        failure_class = "" if passed else "exact_json_mismatch"
    elif task.oracle_type == "exact_text":
        passed = str(candidate_output).strip() == str(task.expected).strip()
        failure_class = "" if passed else "exact_text_mismatch"
    elif task.oracle_type == "exit_code":
        passed = int(candidate_output) == int(task.expected)
        failure_class = "" if passed else "exit_code_mismatch"
    else:
        failure_class = "unsupported_oracle"

    elapsed = duration_seconds if duration_seconds else time.monotonic() - start
    return DharmaEvalScore(
        suite_id=suite_id,
        manifest_hash=manifest_hash,
        task_id=task.task_id,
        split=task.split,
        candidate_id=candidate_id,
        passed=passed,
        score=1.0 if passed else 0.0,
        oracle_type=task.oracle_type,
        duration_seconds=round(float(elapsed), 6),
        cost=float(cost),
        failure_class=failure_class,
        artifact_refs=list(artifact_refs or []),
    )


def build_scoreboard(
    *,
    suite_id: str,
    manifest_hash: str,
    baseline_id: str,
    candidate_id: str,
    baseline_scores: list[DharmaEvalScore],
    candidate_scores: list[DharmaEvalScore],
    split: DharmaEvalSplit | None = None,
    min_delta: float = 0.0,
) -> DharmaEvalScoreboard:
    """Compare two score lists over matching tasks."""
    if split is not None:
        baseline_scores = [score for score in baseline_scores if score.split == split]
        candidate_scores = [score for score in candidate_scores if score.split == split]

    contaminated = sorted(
        {
            score.manifest_hash
            for score in (*baseline_scores, *candidate_scores)
            if score.manifest_hash != manifest_hash
        }
    )
    if contaminated:
        raise ValueError(
            "scoreboard manifest contamination: refusing to compare scores graded under "
            f"{contaminated} against declared manifest_hash {manifest_hash!r}"
        )

    suite_contaminated = sorted(
        {
            score.suite_id
            for score in (*baseline_scores, *candidate_scores)
            if score.suite_id != suite_id
        }
    )
    if suite_contaminated:
        raise ValueError(
            "scoreboard suite contamination: refusing to compare scores from suites "
            f"{suite_contaminated} against declared suite_id {suite_id!r}"
        )

    baseline_by_task = {score.task_id: score for score in baseline_scores}
    candidate_by_task = {score.task_id: score for score in candidate_scores}
    common = sorted(set(baseline_by_task) & set(candidate_by_task))
    if not common:
        raise ValueError("scoreboard requires at least one common task")

    baseline_total = sum(baseline_by_task[task_id].score for task_id in common)
    candidate_total = sum(candidate_by_task[task_id].score for task_id in common)
    task_count = len(common)
    baseline_score = baseline_total / task_count
    candidate_score = candidate_total / task_count
    delta = candidate_score - baseline_score

    return DharmaEvalScoreboard(
        suite_id=suite_id,
        manifest_hash=manifest_hash,
        baseline_id=baseline_id,
        candidate_id=candidate_id,
        split=split,
        baseline_score=round(baseline_score, 6),
        candidate_score=round(candidate_score, 6),
        delta=round(delta, 6),
        baseline_passed=sum(1 for task_id in common if baseline_by_task[task_id].passed),
        candidate_passed=sum(1 for task_id in common if candidate_by_task[task_id].passed),
        task_count=task_count,
        candidate_wins=delta >= float(min_delta),
    )


def append_score_jsonl(path: Path | str, score: DharmaEvalScore) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(score.model_dump(mode="json"), sort_keys=True) + "\n")
