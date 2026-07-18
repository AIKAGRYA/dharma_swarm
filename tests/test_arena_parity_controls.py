"""Arena parity-control tests (Metabolic Loop Ignition, Improvement 2).

Covers the surfaces added on weaver/arena-parity-controls:
  * best_single_parity_budget control arm — instrumented AND asserted parity
    (kill-list doctrine: transport-level equality, externally auditable ledger);
  * seeded paired-bootstrap significance with CI95 on BOTH baselines
    (point estimate alone is forbidden);
  * fail-closed behavior when the parity instrument itself breaks;
  * LiveWorkerPool fail-closed contract (no silent fallback, no zero-token
    "successes", public-view-only prompts) without any network dependency;
  * measurement-mode disclosure so hermetic runs can never masquerade as live.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.coordination.arena import ArenaRunner
from dharma_swarm.coordination.arena.live_pool import (
    RECORDED_SCHEMA,
    LiveDispatchError,
    LiveWorkerPool,
    RecordedReplayPool,
)
from dharma_swarm.coordination.arena.measure import (
    CLAIM_BOUNDARY,
    LIVE_CLOSEOUT_STATE,
    LIVE_MEASUREMENT_SCHEMA,
    LiveMeasurementError,
    run_live_measurement,
)
from dharma_swarm.coordination.arena.runner import CLOSEOUT_STATES
from dharma_swarm.coordination.genome import OrchestrationGenome
from dharma_swarm.council import TraceVerificationRequest


def _router_genome() -> OrchestrationGenome:
    return OrchestrationGenome(
        roster=[
            {"role_id": "r1", "member_id": "alpha-math", "kind": "model"},
            {"role_id": "r2", "member_id": "beta-code", "kind": "model"},
            {"role_id": "r3", "member_id": "gamma-logic", "kind": "model"},
        ],
        adjudication_rule="synthesize",
    )


# --------------------------------------------------------------- parity arm
def test_parity_control_arm_present_verified_and_auditable():
    run = ArenaRunner().run(_router_genome())
    assert "best_single_parity_budget" in run["arm_scores"]
    report = run["parity_control"]
    assert report["verified"] is True
    assert report["calls_per_task_match"] is True
    assert report["candidate_total_calls"] == report["control_total_calls"]
    assert report["control_model"], "gate winner must be resolved as control model"
    # Externally auditable ledger: every arm reports compute, calls, shared cap.
    ledger = run["parity_ledger"]
    for arm in (
        "candidate",
        "best_single_full_budget",
        "best_single_parity_budget",
        "same_budget_self_moa",
        "random_or_static_ensemble",
    ):
        assert arm in ledger
        assert "total_compute" in ledger[arm] and "total_calls" in ledger[arm]
    caps = {ledger[a]["per_call_cap"] for a in ledger}
    assert len(caps) == 1, "one pool serves every arm — the cap cannot differ"


def test_significance_carries_ci95_on_both_baselines():
    run = ArenaRunner().run(_router_genome())
    for key in ("significance", "significance_vs_parity_control"):
        sig = run[key]
        assert sig["method"] == "paired_seeded_bootstrap_percentile"
        lo, hi = sig["ci95_lift"]
        assert lo <= hi
        assert "observed_lift" in sig and "p_value" in sig
        # No-win-below-significance is closeout-enforced; here we assert the
        # CI is present so a point estimate can never render alone.


def test_broken_parity_instrument_fails_closed():
    class TamperedRunner(ArenaRunner):
        def _best_single_parity_budget(self, gate, cand):  # type: ignore[override]
            result, report = super()._best_single_parity_budget(gate, cand)
            report = dict(report)
            report["verified"] = False  # simulate a broken parity instrument
            return result, report

    run = TamperedRunner().run(_router_genome())
    assert run["closeout_state"] == "blocked_with_evidence"


def test_measurement_mode_disclosed_for_hermetic_runs():
    run = ArenaRunner().run(_router_genome())
    assert run["measurement_mode"] == "hermetic_fixture"


# ------------------------------------------------------------ live pool (no network)
_PUBLIC = [{"task_id": "t1", "family": "math", "prompt": "2+2?"}]


def test_live_pool_unknown_task_fails_closed():
    pool = LiveWorkerPool(_PUBLIC, transport=lambda url, payload, timeout: {})
    with pytest.raises(LiveDispatchError):
        pool.dispatch("any-model", "not-a-task")


def test_live_pool_transport_error_fails_closed_no_fallback():
    def broken_transport(url: str, payload: dict[str, Any], timeout: float):
        raise OSError("daemon unreachable")

    pool = LiveWorkerPool(_PUBLIC, transport=broken_transport)
    with pytest.raises(LiveDispatchError):
        pool.dispatch("any-model", "t1")


def test_live_pool_zero_token_success_is_refused():
    def hollow_transport(url: str, payload: dict[str, Any], timeout: float):
        return {
            "model": payload["model"],
            "message": {"content": "4"},
        }  # no token accounting

    pool = LiveWorkerPool(_PUBLIC, transport=hollow_transport)
    with pytest.raises(LiveDispatchError):
        pool.dispatch("any-model", "t1")


def test_live_pool_caches_and_bills_parity_honestly():
    calls = {"n": 0}

    def counting_transport(url: str, payload: dict[str, Any], timeout: float):
        calls["n"] += 1
        return {
            "model": payload["model"],
            "message": {"content": "4"},
            "prompt_eval_count": 7,
            "eval_count": 1,
        }

    pool = LiveWorkerPool(_PUBLIC, transport=counting_transport)
    first = pool.dispatch("m", "t1")
    second = pool.dispatch("m", "t1")
    assert calls["n"] == 1, "temperature-0 resample replays the cached draw"
    assert first.cost == second.cost == 8, "each dispatch still bills its budget"
    assert pool.call_receipts[0]["provider_model_id"] == "m"


@pytest.mark.parametrize(
    "returned_model",
    ["silent-fallback-model", "requested-model ", 7, True, None],
)
def test_live_pool_refuses_provider_model_identity_mismatch(returned_model: Any):
    def fallback_transport(url: str, payload: dict[str, Any], timeout: float):
        return {
            "model": returned_model,
            "message": {"content": "4"},
            "prompt_eval_count": 7,
            "eval_count": 1,
        }

    pool = LiveWorkerPool(_PUBLIC, transport=fallback_transport)
    with pytest.raises(LiveDispatchError, match="model identity mismatch"):
        pool.dispatch("requested-model", "t1")
    assert pool.call_receipts == []


def test_live_pool_refuses_completion_tokens_over_cap():
    def over_budget_transport(url: str, payload: dict[str, Any], timeout: float):
        return {
            "model": payload["model"],
            "message": {"content": "4"},
            "prompt_eval_count": 7,
            "eval_count": 2,
        }

    pool = LiveWorkerPool(_PUBLIC, per_call_cap=1, transport=over_budget_transport)
    with pytest.raises(LiveDispatchError, match="token cap violated"):
        pool.dispatch("m", "t1")
    assert pool.call_receipts == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("prompt_eval_count", -1),
        ("eval_count", -1),
        ("prompt_eval_count", "7"),
        ("eval_count", True),
    ],
)
def test_live_pool_refuses_invalid_provider_token_accounting(field: str, value: Any):
    def malformed_transport(url: str, payload: dict[str, Any], timeout: float):
        response = {
            "model": payload["model"],
            "message": {"content": "4"},
            "prompt_eval_count": 7,
            "eval_count": 1,
        }
        response[field] = value
        return response

    pool = LiveWorkerPool(_PUBLIC, transport=malformed_transport)
    with pytest.raises(LiveDispatchError, match="token accounting invalid"):
        pool.dispatch("m", "t1")
    assert pool.call_receipts == []


def test_replay_pool_rejects_unexpected_schema():
    with pytest.raises(LiveDispatchError):
        RecordedReplayPool({"schema": "not-the-schema"})
    assert RECORDED_SCHEMA == "orchestration_arena_v1_live_receipts.v1"


def _valid_recorded_payload() -> dict[str, Any]:
    pool = LiveWorkerPool(_PUBLIC, timeout=3.0, transport=_metered_transport)
    pool.dispatch("m", "t1")
    return pool.receipts_payload()


def test_replay_pool_accepts_exact_live_receipt():
    payload = _valid_recorded_payload()
    replay = RecordedReplayPool(payload)
    response = replay.dispatch("m", "t1")
    assert response.answer == payload["responses"][0]["answer"]
    assert response.cost == 8


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("prompt_tokens", -1, "prompt token accounting"),
        ("completion_tokens", -1, "completion token accounting"),
        ("prompt_tokens", "7", "prompt token accounting"),
        ("completion_tokens", True, "completion token accounting"),
        ("cost", -1, "inconsistent token cost"),
        ("cost", 9, "inconsistent token cost"),
        ("provider_model_id", "fallback", "provider identity mismatch"),
    ],
)
def test_replay_pool_rejects_forged_accounting(
    field: str, value: Any, message: str
):
    payload = _valid_recorded_payload()
    payload["responses"][0][field] = value
    with pytest.raises(LiveDispatchError, match=message):
        RecordedReplayPool(payload)


# ------------------------------------------------ live entrypoint (no network)
_LIVE_MODELS = {
    "math": "live-math-model",
    "code": "live-code-model",
    "logic": "live-logic-model",
}


def _metered_transport(url: str, payload: dict[str, Any], timeout: float):
    assert url.endswith("/api/chat")
    assert payload["options"] == {"temperature": 0.0, "num_predict": 64}
    assert timeout == 3.0
    return {
        "model": payload["model"],
        "message": {"content": "measured-wrong-answer"},
        "prompt_eval_count": 7,
        "eval_count": 1,
    }


def test_live_entrypoint_constructs_full_controlled_run_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("DHARMA_ARENA_LIVE", "1")
    output = tmp_path / "live-run"

    result = run_live_measurement(
        models_by_family=_LIVE_MODELS,
        output_dir=output,
        timeout=3.0,
        transport=_metered_transport,
    )

    receipt = result["receipt"]
    assert receipt["schema"] == LIVE_MEASUREMENT_SCHEMA
    assert receipt["capability_claim"] is False
    assert receipt["claim_boundary"] == CLAIM_BOUNDARY
    assert receipt["closeout_state"] == LIVE_CLOSEOUT_STATE
    assert receipt["control_outcome"] == result["run"]["control_outcome"]
    assert receipt["promotion_authorized"] is False
    assert receipt["expected_live_pairs"] == receipt["observed_live_pairs"] == 72
    assert len(receipt["digest_sha256"]) == 64
    manifest = receipt["artifact_sha256"]
    assert set(manifest) == set(receipt["output_files"]) - {
        "live_measurement_receipt.json"
    }
    for name, digest in manifest.items():
        assert digest == hashlib.sha256((output / name).read_bytes()).hexdigest()
    run = json.loads((output / "arena_run.json").read_text(encoding="utf-8"))
    assert run["capability_claim"] is False
    assert run["closeout_state"] == LIVE_CLOSEOUT_STATE
    assert run["closeout_state"] in CLOSEOUT_STATES
    assert run["promotion_claim_authority"]["authority"] == "evidence_only"
    assert run["promotion_claim_authority"]["promotion_authorized"] is False
    assert "authority" not in run["promotion_claim"]
    assert "promotion_authorized" not in run["promotion_claim"]
    assert run["live_controls_verified"] is True
    assert run["promotion_authorized"] is False
    assert run["parity_control"]["verified"] is True
    assert (
        run["parity_control"]["candidate_total_calls"]
        == run["parity_control"]["control_total_calls"]
    )
    assert run["significance"]["method"] == "paired_seeded_bootstrap_percentile"
    assert run["significance_vs_parity_control"]["method"] == (
        "paired_seeded_bootstrap_percentile"
    )
    live_receipts = json.loads(
        (output / "live_worker_receipts.json").read_text(encoding="utf-8")
    )
    assert len(live_receipts["responses"]) == 72
    scorecard = json.loads((output / "scorecard.json").read_text(encoding="utf-8"))
    assert scorecard["closeout_state"] == LIVE_CLOSEOUT_STATE
    assert scorecard["control_outcome"] == run["control_outcome"]
    assert scorecard["promotion_authorized"] is False
    assert scorecard["claim_boundary"] == CLAIM_BOUNDARY
    routes = [
        json.loads(line)
        for line in (output / "route_receipts.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    traces = [
        json.loads(line)
        for line in (output / "trace_receipts.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    council_receipt = json.loads(
        (output / "council_receipts.jsonl").read_text(encoding="utf-8").strip()
    )
    replayed_inputs_hash = TraceVerificationRequest(
        genome_id=run["candidate_genome_id"],
        route_receipts=[row for row in routes if row["arm"] == "candidate"],
        trace_receipts=[row for row in traces if row["arm"] == "candidate"],
        scorecard=scorecard["candidate"],
        promotion_claim=run["promotion_claim"],
        untrusted=run["contaminated"],
        contamination_findings=(),
    ).inputs_hash()
    assert replayed_inputs_hash == council_receipt["inputs_hash"]
    assert replayed_inputs_hash == run["_council_receipt"]["inputs_hash"]
    packet = (output / "decision_packet.md").read_text(encoding="utf-8")
    assert packet.startswith(
        "> **Claim boundary:** live measurement candidate only; "
        "`capability_claim=false`; `promotion_authorized=false`."
    )
    assert "does not authorize MAP-Elites insertion" in packet
    assert "Eligible for MAP-Elites promotion" not in packet


def test_live_entrypoint_denies_promotion_even_for_positive_runner_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from dharma_swarm.coordination.arena import measure

    class PositiveStateArenaRunner(ArenaRunner):
        def run(self, candidate, output_dir=None):  # type: ignore[override]
            result = super().run(candidate, output_dir=output_dir)
            result["closeout_state"] = "positive_lift_candidate"
            decision_path = Path(output_dir) / "decision_packet.md"
            decision_path.write_text(
                decision_path.read_text(encoding="utf-8")
                + "\nEligible for MAP-Elites promotion.\n",
                encoding="utf-8",
            )
            return result

    monkeypatch.setenv("DHARMA_ARENA_LIVE", "1")
    monkeypatch.setattr(measure, "ArenaRunner", PositiveStateArenaRunner)
    output = tmp_path / "positive-state"
    result = run_live_measurement(
        models_by_family=_LIVE_MODELS,
        output_dir=output,
        timeout=3.0,
        transport=_metered_transport,
    )

    assert result["run"]["control_outcome"] == "positive_lift_candidate"
    assert result["run"]["closeout_state"] == LIVE_CLOSEOUT_STATE
    assert result["run"]["promotion_authorized"] is False
    assert result["receipt"]["control_outcome"] == "positive_lift_candidate"
    assert result["receipt"]["closeout_state"] == LIVE_CLOSEOUT_STATE
    assert result["receipt"]["promotion_authorized"] is False
    packet = (output / "decision_packet.md").read_text(encoding="utf-8")
    assert "Eligible for MAP-Elites promotion" not in packet
    assert "grants no MAP-Elites insertion or promotion authority" in packet


def test_live_entrypoint_requires_explicit_opt_in_before_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("DHARMA_ARENA_LIVE", raising=False)
    called = False

    def transport(url: str, payload: dict[str, Any], timeout: float):
        nonlocal called
        called = True
        return _metered_transport(url, payload, timeout)

    with pytest.raises(LiveMeasurementError, match="DHARMA_ARENA_LIVE=1"):
        run_live_measurement(
            models_by_family=_LIVE_MODELS,
            output_dir=tmp_path / "not-created",
            timeout=3.0,
            transport=transport,
        )
    assert called is False


@pytest.mark.parametrize(
    "roster",
    [
        {"math": "m", "code": "c"},
        {"math": "same", "code": "same", "logic": "same"},
        {"math": "m", "code": "c", "logic": ""},
    ],
)
def test_live_entrypoint_rejects_incomplete_or_ambiguous_roster(
    roster: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("DHARMA_ARENA_LIVE", "1")
    with pytest.raises(LiveMeasurementError, match="roster"):
        run_live_measurement(
            models_by_family=roster,
            output_dir=tmp_path / "not-created",
            timeout=3.0,
            transport=_metered_transport,
        )


@pytest.mark.parametrize(
    "padded_seat",
    ["llama3 ", " llama3", "\tllama3", "llama3\n"],
)
def test_live_entrypoint_rejects_whitespace_padded_seat_without_normalizing(
    padded_seat: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A padded seat id must fail closed, never be silently measured as its
    stripped form (exact-seat guarantee)."""
    monkeypatch.setenv("DHARMA_ARENA_LIVE", "1")
    roster = dict(_LIVE_MODELS)
    roster["math"] = padded_seat
    called = False

    def transport(url: str, payload: dict[str, Any], timeout: float):
        nonlocal called
        called = True
        return _metered_transport(url, payload, timeout)

    with pytest.raises(LiveMeasurementError, match="exact operator-supplied"):
        run_live_measurement(
            models_by_family=roster,
            output_dir=tmp_path / "not-created",
            timeout=3.0,
            transport=transport,
        )
    assert called is False


def test_live_entrypoint_rejects_non_string_seat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Non-string seat ids must fail closed instead of being coerced by str()."""
    monkeypatch.setenv("DHARMA_ARENA_LIVE", "1")
    roster: dict[str, Any] = dict(_LIVE_MODELS)
    roster["code"] = 42
    with pytest.raises(LiveMeasurementError, match="non-empty strings"):
        run_live_measurement(
            models_by_family=roster,
            output_dir=tmp_path / "not-created",
            timeout=3.0,
            transport=_metered_transport,
        )


def test_live_entrypoint_refuses_repository_output(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DHARMA_ARENA_LIVE", "1")
    inside_repo = Path(__file__).resolve().parent / ".forbidden-arena-live-output"
    with pytest.raises(LiveMeasurementError, match="outside the repository"):
        run_live_measurement(
            models_by_family=_LIVE_MODELS,
            output_dir=inside_repo,
            timeout=3.0,
            transport=_metered_transport,
        )
    assert not inside_repo.exists()


def test_live_entrypoint_removes_partial_output_on_dispatch_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("DHARMA_ARENA_LIVE", "1")
    output = tmp_path / "failed-run"
    calls = 0

    def broken_transport(url: str, payload: dict[str, Any], timeout: float):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("provider interrupted")
        return _metered_transport(url, payload, timeout)

    with pytest.raises(LiveDispatchError, match="provider interrupted"):
        run_live_measurement(
            models_by_family=_LIVE_MODELS,
            output_dir=output,
            timeout=3.0,
            transport=broken_transport,
        )
    assert not output.exists()
    assert not list(tmp_path.glob(".failed-run.staging-*"))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"model": "silent-fallback-model"}, "model identity mismatch"),
        ({"eval_count": 65}, "token cap violated"),
    ],
)
def test_live_entrypoint_withholds_output_on_provider_control_violation(
    mutation: dict[str, Any],
    message: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("DHARMA_ARENA_LIVE", "1")
    output = tmp_path / "provider-control-violation"

    def violating_transport(url: str, payload: dict[str, Any], timeout: float):
        response = _metered_transport(url, payload, timeout)
        response.update(mutation)
        return response

    with pytest.raises(LiveDispatchError, match=message):
        run_live_measurement(
            models_by_family=_LIVE_MODELS,
            output_dir=output,
            timeout=3.0,
            transport=violating_transport,
        )
    assert not output.exists()
    assert not list(tmp_path.glob(".provider-control-violation.staging-*"))


def test_live_entrypoint_refuses_publish_when_output_appears_mid_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("DHARMA_ARENA_LIVE", "1")
    output = tmp_path / "contended-run"
    calls = 0

    def contending_transport(url: str, payload: dict[str, Any], timeout: float):
        nonlocal calls
        calls += 1
        if calls == 1:
            output.mkdir()
        return _metered_transport(url, payload, timeout)

    with pytest.raises(LiveMeasurementError, match="appeared"):
        run_live_measurement(
            models_by_family=_LIVE_MODELS,
            output_dir=output,
            timeout=3.0,
            transport=contending_transport,
        )
    assert output.is_dir()
    assert not list(output.iterdir())
    assert not list(tmp_path.glob(".contended-run.staging-*"))


def test_live_entrypoint_withholds_output_when_manifested_artifact_is_tampered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from dharma_swarm.coordination.arena import measure

    original_manifest = measure._artifact_manifest

    def manifest_then_tamper(staging: Path):
        manifest = original_manifest(staging)
        (staging / "scorecard.json").write_text("{}\n", encoding="utf-8")
        return manifest

    monkeypatch.setenv("DHARMA_ARENA_LIVE", "1")
    monkeypatch.setattr(measure, "_artifact_manifest", manifest_then_tamper)
    output = tmp_path / "tampered-artifact"
    with pytest.raises(LiveMeasurementError, match="artifact digest mismatch"):
        run_live_measurement(
            models_by_family=_LIVE_MODELS,
            output_dir=output,
            timeout=3.0,
            transport=_metered_transport,
        )
    assert not output.exists()
    assert not list(tmp_path.glob(".tampered-artifact.staging-*"))


def test_live_entrypoint_withholds_candidate_when_control_receipt_is_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from dharma_swarm.coordination.arena import measure

    class TamperedArenaRunner(ArenaRunner):
        def run(self, candidate, output_dir=None):  # type: ignore[override]
            result = super().run(candidate, output_dir=output_dir)
            result["parity_control"]["verified"] = False
            return result

    monkeypatch.setenv("DHARMA_ARENA_LIVE", "1")
    monkeypatch.setattr(measure, "ArenaRunner", TamperedArenaRunner)
    output = tmp_path / "tampered-run"
    with pytest.raises(LiveMeasurementError, match="parity"):
        run_live_measurement(
            models_by_family=_LIVE_MODELS,
            output_dir=output,
            timeout=3.0,
            transport=_metered_transport,
        )
    assert not output.exists()
    assert not list(tmp_path.glob(".tampered-run.staging-*"))


def test_live_entrypoint_withholds_output_when_worker_receipts_are_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from dharma_swarm.coordination.arena import measure

    class IncompleteReceiptPool(LiveWorkerPool):
        def dispatch(self, model_id: str, task_id: str):  # type: ignore[override]
            response = super().dispatch(model_id, task_id)
            if len(self.call_receipts) == 72:
                self.call_receipts.pop()
            return response

    monkeypatch.setenv("DHARMA_ARENA_LIVE", "1")
    monkeypatch.setattr(measure, "LiveWorkerPool", IncompleteReceiptPool)
    output = tmp_path / "incomplete-receipts"
    with pytest.raises(LiveMeasurementError, match="receipts"):
        run_live_measurement(
            models_by_family=_LIVE_MODELS,
            output_dir=output,
            timeout=3.0,
            transport=_metered_transport,
        )
    assert not output.exists()
    assert not list(tmp_path.glob(".incomplete-receipts.staging-*"))
