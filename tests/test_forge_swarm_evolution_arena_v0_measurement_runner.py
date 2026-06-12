from __future__ import annotations

import json
from pathlib import Path

import scripts.runtime.forge_swarm_evolution_arena_v0_measurement_runner as runner
from scripts.runtime.forge_swarm_evolution_arena_v0_measurement_runner import (
    aggregate_average_submissions,
    blocker_signature,
    bootstrap_ci,
    extract_json_object,
    non_roi_blocker,
    normalize_submission,
)


def test_extract_json_object_handles_markdown_fence() -> None:
    payload, error = extract_json_object('```json\n{"predictions": [], "method_summary": "x"}\n```')
    assert error == ""
    assert payload["method_summary"] == "x"


def test_normalize_submission_keeps_known_ids_only() -> None:
    payload = {
        "predictions": [
            {"id": "a", "target": "1.5"},
            {"id": "extra", "target": 9},
        ],
        "method_summary": "ok",
    }
    normalized = normalize_submission(payload, ["a", "b"], "fallback")
    assert normalized["predictions"] == [{"id": "a", "target": 1.5}, {"id": "b", "target": 0.0}]


def test_aggregate_average_submissions(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    out = tmp_path / "out.json"
    a.write_text(json.dumps({"predictions": [{"id": "x", "target": 1}, {"id": "y", "target": 3}]}))
    b.write_text(json.dumps({"predictions": [{"id": "x", "target": 3}, {"id": "y", "target": 5}]}))
    aggregate_average_submissions([a, b], ["x", "y"], out, "avg")
    payload = json.loads(out.read_text())
    assert payload["predictions"] == [{"id": "x", "target": 2.0}, {"id": "y", "target": 4.0}]


def test_bootstrap_ci_reports_n_and_mean() -> None:
    ci = bootstrap_ci([1.0, 0.0, -1.0], samples=50)
    assert ci["n"] == 3
    assert ci["mean"] == 0.0
    assert ci["lower"] <= ci["upper"]


def test_blocker_signature_classifies_common_runtime_failures() -> None:
    assert blocker_signature({"candidate_ok": False, "candidate_error": "RuntimeError: HTTP 503"}) == "provider_http_503"
    assert blocker_signature({"candidate_ok": False, "candidate_error": "RuntimeError: HTTP 429 RESOURCE_EXHAUSTED"}) == "provider_http_429"
    assert blocker_signature({"candidate_ok": False, "candidate_error": "TimeoutExpired: command"}) == "codex_timeout"
    assert blocker_signature({"candidate_ok": False, "candidate_error": "TimeoutExpired: prompt mentions HTTP 429"}) == "codex_timeout"
    assert blocker_signature({"candidate_ok": False, "candidate_error": "json_object_not_found"}) == "non_json_response"
    assert blocker_signature({"candidate_ok": True, "candidate_error": "TimeoutExpired: command"}) == ""


def test_non_roi_blocker_stops_repeated_runtime_failures() -> None:
    rows = [
        {"task_id": "t1", "arm": "best_single_full_budget", "result_kind": "final", "candidate_ok": False, "candidate_error": "TimeoutExpired"},
        {"task_id": "t1", "arm": "labels_only_sham_swarm", "result_kind": "final", "candidate_ok": False, "candidate_error": "TimeoutExpired"},
        {"task_id": "t1", "arm": "same_budget_self_moa_samples", "result_kind": "sample", "candidate_ok": False, "candidate_error": "HTTP 503"},
        {"task_id": "t1", "arm": "same_budget_self_moa_samples", "result_kind": "sample", "candidate_ok": False, "candidate_error": "HTTP 503"},
        {"task_id": "t1", "arm": "same_budget_self_moa_samples", "result_kind": "sample", "candidate_ok": False, "candidate_error": "HTTP 503"},
        {"task_id": "t1", "arm": "full_live_dharma_swarm", "result_kind": "final", "candidate_ok": False, "candidate_error": "TimeoutExpired"},
    ]
    blocker = non_roi_blocker(rows, completed_task_count=1)
    assert blocker is not None
    assert "codex_timeout" in blocker["blocker_signature"]
    assert "provider_http_503" in blocker["blocker_signature"]


def test_run_measurement_blocks_on_repeated_sample_failures(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "task_manifest.json").write_text(
        json.dumps({"rubric_item_count": 30, "tasks": [{"task_id": "t1"}]}),
        encoding="utf-8",
    )
    roles = [
        runner.LiveRole("builder", "codex-cli", "codex_cli", "gpt-5.5", "s1", "codex"),
        runner.LiveRole("verifier_adversary", "gemini-api", "gemini", "gemini-flash-latest", "s2", "gemini"),
        runner.LiveRole("alternate_builder", "zai-api", "zai_coding", "glm-5.1", "s3", "zai"),
    ]

    monkeypatch.setattr(runner, "load_env_files", lambda: {})
    monkeypatch.setattr(runner, "current_live_roles", lambda: (roles, []))
    monkeypatch.setattr(runner, "repair_roster_gate", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(runner, "run_preflight", lambda **_kwargs: {"measurement_mode_allowed": True})
    monkeypatch.setattr(runner, "append_liveness_receipts", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runner, "run_closed_book", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runner, "challenge_ids", lambda *_args, **_kwargs: ["x"])

    def fake_run_candidate(
        _run_dir: Path,
        measurement_root: Path,
        task: dict,
        arm: str,
        role: runner.LiveRole,
        _variant: str,
        _env: dict,
        _timeout_s: int,
        extra_context: str = "",
    ) -> runner.CandidateResult:
        out_dir = measurement_root / "fake" / arm / role.role
        out_dir.mkdir(parents=True, exist_ok=True)
        response_path = out_dir / "response.txt"
        submission_path = out_dir / "submission.json"
        response_path.write_text("{}", encoding="utf-8")
        submission_path.write_text(json.dumps({"predictions": [{"id": "x", "target": 0.0}]}), encoding="utf-8")
        error = "RuntimeError: HTTP 503" if arm == "same_budget_self_moa_samples" else ""
        return runner.CandidateResult(
            arm=arm,
            task_id=task["task_id"],
            role=role.role,
            provider=role.provider,
            model=role.model,
            prompt_path=out_dir / "prompt.md",
            response_path=response_path,
            submission_path=submission_path,
            ok=not error,
            elapsed_ms=1,
            error=error,
            usage={},
        )

    def fake_write_score_rows(
        _run_dir: Path,
        measurement_root: Path,
        task: dict,
        result: runner.CandidateResult,
        result_kind: str = "final",
    ) -> dict:
        return {
            "measurement_run_id": measurement_root.name,
            "arm": result.arm,
            "task_id": task["task_id"],
            "result_kind": result_kind,
            "candidate_ok": result.ok,
            "candidate_error": result.error,
            "score": 0.5,
        }

    def fake_aggregate_average_submissions(_paths: list[Path], _ids: list[str], output: Path, summary: str) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps({"predictions": [{"id": "x", "target": 0.0}], "method_summary": summary}),
            encoding="utf-8",
        )

    monkeypatch.setattr(runner, "run_candidate", fake_run_candidate)
    monkeypatch.setattr(runner, "write_score_rows", fake_write_score_rows)
    monkeypatch.setattr(runner, "aggregate_average_submissions", fake_aggregate_average_submissions)

    report = runner.run_measurement(run_dir, timeout_s=1, max_tasks=1)

    assert report["status"] == "blocked_with_evidence"
    assert report["blocker"]["blocker_counts"]["provider_http_503"] == 3
