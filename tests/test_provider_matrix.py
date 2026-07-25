from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.model_hierarchy import LaneRole
from dharma_swarm.models import LLMResponse, ProviderType
from dharma_swarm.provider_matrix import (
    MatrixExecutionResult,
    MatrixPromptSpec,
    MatrixTargetSpec,
    _classify_error,
    _execution_score,
    _execute_target_prompt,
    build_default_matrix_targets,
    build_default_prompt_corpus,
    classify_matrix_response,
    run_provider_matrix,
)


def test_build_default_matrix_targets_keeps_sovereign_lanes_first() -> None:
    # key_oracle=None => FAIL-OPEN (no live filtering) so the matrix keeps its
    # full deterministic shape regardless of the machine's keys_status.json.
    targets = build_default_matrix_targets(profile="live25", env={}, key_oracle=None)

    assert targets[0].provider == ProviderType.CODEX
    assert targets[0].lane_role == LaneRole.PRIMARY_DRIVER
    assert targets[0].model == "gpt-5.4"
    assert targets[1].provider == ProviderType.CLAUDE_CODE
    assert targets[1].lane_role == LaneRole.PRIMARY_DRIVER
    assert targets[1].model == "claude-opus-4-6"

    delegated = [target for target in targets if target.lane_role != LaneRole.PRIMARY_DRIVER]
    assert delegated
    assert any(target.provider == ProviderType.OLLAMA for target in delegated)
    assert any(target.model == "kimi-k2.5:cloud" for target in targets)
    assert any(target.model == "qwen3-coder:480b-cloud" for target in targets)
    assert any(target.model == "minimax-m2.7:cloud" for target in targets)
    assert len(targets) >= 20


def test_build_default_matrix_targets_quick_keeps_ten_live_friendly_lanes(
    monkeypatch,
) -> None:
    def _fake_resolve(provider, *, model=None, env=None, working_dir=None, timeout_seconds=None):
        del env
        del working_dir
        del timeout_seconds
        return SimpleNamespace(
            provider=provider,
            available=provider != ProviderType.ANTHROPIC,
            default_model=model,
            source="binary" if provider in {ProviderType.CODEX, ProviderType.CLAUDE_CODE} else "env",
        )

    monkeypatch.setattr("dharma_swarm.provider_matrix.resolve_runtime_provider_config", _fake_resolve)

    targets = build_default_matrix_targets(
        profile="quick", env={"OPENROUTER_API_KEY": "test-key"}, key_oracle=None
    )

    assert len(targets) >= 10
    assert targets[0].provider == ProviderType.CODEX
    assert targets[1].provider == ProviderType.CLAUDE_CODE
    providers = {target.provider for target in targets}
    assert ProviderType.NVIDIA_NIM in providers
    assert ProviderType.OPENROUTER_FREE in providers
    assert ProviderType.GROQ in providers
    assert ProviderType.CEREBRAS in providers


def test_run_provider_matrix_respects_budget_units(tmp_path: Path) -> None:
    payload = run_provider_matrix(
        profile="quick",
        max_prompts=1,
        timeout_seconds=1.0,
        budget_units=0,
        artifact_dir=tmp_path,
        include_unavailable=True,
        write_artifacts=False,
        env={},
    )

    assert payload["budget"]["units_consumed"] == 0
    assert payload["counts"]["attempted"] == 0
    assert payload["counts"]["skipped_budget"] > 0
    assert payload["leaderboard"] == []


def test_classify_matrix_response_flags_provider_errors_and_schema_misses() -> None:
    status, schema_valid, missing = classify_matrix_response(
        "ERROR (rc=1): provider failed before doing the task",
        ("deployment_case", "recommendation"),
    )
    assert status == "provider_error"
    assert schema_valid is False
    assert missing == ["deployment_case", "recommendation"]

    status, schema_valid, missing = classify_matrix_response(
        '{"deployment_case":"tariff_intelligence"}',
        ("deployment_case", "recommendation"),
    )
    assert status == "schema_invalid"
    assert schema_valid is False
    assert missing == ["recommendation"]


def test_classify_matrix_response_accepts_embedded_json_payload() -> None:
    status, schema_valid, missing = classify_matrix_response(
        (
            "Here is the answer.\n```json\n"
            '{"deployment_case":"tariff_intelligence","recommendation":"deploy",'
            '"confidence":"high","why_now":"broad_fit"}\n```'
        ),
        ("deployment_case", "recommendation", "confidence", "why_now"),
    )
    assert status == "ok"
    assert schema_valid is True
    assert missing == []


def test_classify_error_marks_blank_timeout_exception() -> None:
    assert _classify_error(TimeoutError()) == "timeout"
    assert _classify_error("HTTP error 429: too many requests") == "rate_limited"
    assert _classify_error("insufficient_quota for this key") == "quota_exhausted"
    assert _classify_error("your credit balance is too low") == "billing_exhausted"

    status, schema_valid, missing = classify_matrix_response(
        "You've hit your limit · resets Mar 27, 9pm (Asia/Tokyo)",
        ("deployment_case", "recommendation"),
    )
    assert status == "provider_error"
    assert schema_valid is False
    assert missing == ["deployment_case", "recommendation"]


@pytest.mark.asyncio
async def test_execute_target_prompt_marks_subprocess_error_banner_as_failure(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeProvider:
        async def complete(self, _request):
            return LLMResponse(
                content="ERROR (rc=1): failed to stat skills entry",
                model="codex",
            )

    def _fake_resolve(*args, **kwargs):
        captured["env"] = kwargs.get("env")
        return object()

    monkeypatch.setattr("dharma_swarm.provider_matrix.resolve_runtime_provider_config", _fake_resolve)
    monkeypatch.setattr(
        "dharma_swarm.provider_matrix.create_runtime_provider",
        lambda _config: _FakeProvider(),
    )

    result = await _execute_target_prompt(
        MatrixTargetSpec(
            target_id="codex:codex",
            provider=ProviderType.CODEX,
            model="codex",
            lane_role=LaneRole.PRIMARY_DRIVER,
            tier="paid",
            available=True,
            availability_reason="configured",
            config_source="binary",
        ),
        MatrixPromptSpec(
            prompt_id="deployment_case_ranker",
            title="Rank deployment cases",
            prompt="Return JSON only.",
            required_keys=("deployment_case", "recommendation"),
        ),
        timeout_seconds=1.0,
        working_dir=None,
        env={"OPENAI_API_KEY": "test-key"},
    )

    assert result.status == "provider_error"
    assert result.schema_valid is False
    assert result.error is not None
    assert captured["env"] == {"OPENAI_API_KEY": "test-key"}


@pytest.mark.asyncio
async def test_execute_target_prompt_repairs_schema_invalid_response_with_second_pass(
    monkeypatch,
) -> None:
    class _FakeProvider:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, _request):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    content=(
                        "I recommend tariff_intelligence because it best fits research-heavy work. "
                        "Confidence: high. Why now: immediate policy volatility."
                    ),
                    model="glm-5:cloud",
                )
            return LLMResponse(
                content=json.dumps(
                    {
                        "deployment_case": "tariff_intelligence",
                        "recommendation": "deploy",
                        "confidence": "high",
                        "why_now": "immediate_policy_volatility",
                    }
                ),
                model="glm-5:cloud",
            )

    fake_provider = _FakeProvider()

    monkeypatch.setattr(
        "dharma_swarm.provider_matrix.resolve_runtime_provider_config",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "dharma_swarm.provider_matrix.create_runtime_provider",
        lambda _config: fake_provider,
    )

    result = await _execute_target_prompt(
        MatrixTargetSpec(
            target_id="ollama:glm-5:cloud",
            provider=ProviderType.OLLAMA,
            model="glm-5:cloud",
            lane_role=LaneRole.RESEARCH_DELEGATE,
            tier="free",
            available=True,
            availability_reason="configured",
            config_source="env",
        ),
        MatrixPromptSpec(
            prompt_id="deployment_case_ranker",
            title="Rank deployment cases",
            prompt="Return JSON only.",
            required_keys=("deployment_case", "recommendation", "confidence", "why_now"),
        ),
        timeout_seconds=5.0,
        working_dir=None,
        env={},
    )

    assert result.status == "ok"
    assert result.schema_valid is True
    assert result.repair_attempted is True
    assert result.repair_strategy == "same_provider_reask"
    assert result.direct_status == "schema_invalid"
    assert result.error is None


@pytest.mark.asyncio
async def test_execute_target_prompt_uses_subprocess_timeout_floor(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeProvider:
        async def complete(self, _request):
            return LLMResponse(
                content=json.dumps(
                    {
                        "deployment_case": "tariff_intelligence",
                        "recommendation": "deploy",
                        "confidence": "high",
                        "why_now": "broad_fit",
                    }
                ),
                model="gpt-5.4",
            )

    def _fake_resolve(*args, **kwargs):
        captured["timeout_seconds"] = kwargs.get("timeout_seconds")
        return object()

    monkeypatch.setattr("dharma_swarm.provider_matrix.resolve_runtime_provider_config", _fake_resolve)
    monkeypatch.setattr(
        "dharma_swarm.provider_matrix.create_runtime_provider",
        lambda _config: _FakeProvider(),
    )

    result = await _execute_target_prompt(
        MatrixTargetSpec(
            target_id="codex:gpt-5.4",
            provider=ProviderType.CODEX,
            model="gpt-5.4",
            lane_role=LaneRole.PRIMARY_DRIVER,
            tier="paid",
            available=True,
            availability_reason="configured",
            config_source="binary",
        ),
        MatrixPromptSpec(
            prompt_id="deployment_case_ranker",
            title="Rank deployment cases",
            prompt="Return JSON only.",
            required_keys=("deployment_case", "recommendation", "confidence", "why_now"),
        ),
        timeout_seconds=5.0,
        working_dir=None,
        env={},
    )

    assert result.status == "ok"
    assert captured["timeout_seconds"] == 180


def test_build_default_prompt_corpus_workspace_uses_curated_snippets(tmp_path: Path) -> None:
    pkg = tmp_path / "dharma_swarm"
    pkg.mkdir()
    (pkg / "provider_matrix.py").write_text(
        ("# filler\n" * 500)
        + "def _execute_target_prompt(...):\n    pass\n"
        + "def _quick_blueprints(...):\n    pass\n",
        encoding="utf-8",
    )
    (pkg / "provider_smoke.py").write_text(
        ("# filler\n" * 500)
        + "async def _probe_openrouter(model):\n    return {}\n",
        encoding="utf-8",
    )
    (pkg / "runtime_provider.py").write_text(
        ("# filler\n" * 500)
        + "def resolve_runtime_provider_config(...):\n    return None\n"
        + "def create_runtime_provider(...):\n    return None\n",
        encoding="utf-8",
    )

    prompts = build_default_prompt_corpus(corpus="workspace", working_dir=str(tmp_path))
    prompt_text = prompts[0].prompt

    assert "_execute_target_prompt" in prompt_text
    assert "_probe_openrouter" in prompt_text
    assert "resolve_runtime_provider_config" in prompt_text


@pytest.mark.asyncio
async def test_execute_target_prompt_can_use_cross_lane_repair(monkeypatch) -> None:
    class _VerboseProvider:
        async def complete(self, _request):
            return LLMResponse(
                content=(
                    "Best choice is diligence_copilot because it is research-heavy, "
                    "supports grading, and keeps humans in review."
                ),
                model="kimi-k2.5:cloud",
            )

    class _RepairProvider:
        async def complete(self, _request):
            return LLMResponse(
                content=json.dumps(
                    {
                        "deployment_case": "diligence_copilot",
                        "recommendation": "deploy",
                        "confidence": "high",
                        "why_now": "strong_human_review_fit",
                    }
                ),
                model="qwen3-coder:480b-cloud",
            )

    def _fake_resolve(provider, *args, **kwargs):
        del args
        del kwargs
        return {"provider": provider.value}

    def _fake_create_runtime_provider(config):
        if config["provider"] == ProviderType.OLLAMA.value:
            return _VerboseProvider()
        return _RepairProvider()

    monkeypatch.setattr("dharma_swarm.provider_matrix.resolve_runtime_provider_config", _fake_resolve)
    monkeypatch.setattr(
        "dharma_swarm.provider_matrix.create_runtime_provider",
        _fake_create_runtime_provider,
    )

    result = await _execute_target_prompt(
        MatrixTargetSpec(
            target_id="ollama:kimi-k2.5:cloud",
            provider=ProviderType.OLLAMA,
            model="kimi-k2.5:cloud",
            lane_role=LaneRole.RESEARCH_DELEGATE,
            tier="free",
            available=True,
            availability_reason="configured",
            config_source="env",
        ),
        MatrixPromptSpec(
            prompt_id="deployment_case_ranker",
            title="Rank deployment cases",
            prompt="Return JSON only.",
            required_keys=("deployment_case", "recommendation", "confidence", "why_now"),
        ),
        timeout_seconds=5.0,
        working_dir=None,
        env={},
        repair_target=MatrixTargetSpec(
            target_id="ollama:qwen3-coder:480b-cloud",
            provider=ProviderType.OPENROUTER,
            model="qwen/qwen3-235b-a22b-04-28",
            lane_role=LaneRole.VALIDATOR,
            tier="free",
            available=True,
            availability_reason="configured",
            config_source="smoke",
        ),
    )

    assert result.status == "ok"
    assert result.schema_valid is True
    assert result.repair_attempted is True
    assert result.repair_strategy == "cross_lane_repair:openrouter:qwen/qwen3-235b-a22b-04-28"


def test_execution_score_penalizes_fast_unknown_model() -> None:
    unknown_model = MatrixExecutionResult(
        target_id="ollama:qwen",
        prompt_id="deployment_case_ranker",
        status="unknown_model",
        response_text="",
        elapsed_sec=0.2,
        schema_valid=False,
        required_keys=["deployment_case", "recommendation"],
    )
    schema_invalid = MatrixExecutionResult(
        target_id="ollama:glm",
        prompt_id="deployment_case_ranker",
        status="schema_invalid",
        response_text="verbose but useful",
        elapsed_sec=6.0,
        schema_valid=False,
        required_keys=["deployment_case", "recommendation"],
    )

    assert _execution_score(unknown_model, timeout_seconds=20.0) == 0.0
    assert _execution_score(schema_invalid, timeout_seconds=20.0) > 0.0


def test_run_provider_matrix_default_budget_reaches_delegated_lanes(tmp_path: Path, monkeypatch) -> None:
    async def _fake_execute(target, prompt, timeout_seconds, working_dir, env, repair_target=None):
        del prompt
        del timeout_seconds
        del working_dir
        del env
        del repair_target
        return MatrixExecutionResult(
            target_id=target.target_id,
            prompt_id="deployment_case_ranker",
            status="ok",
            response_text=json.dumps(
                {
                    "deployment_case": "tariff_intelligence",
                    "recommendation": "deploy",
                    "confidence": "high",
                    "why_now": "broad_fit",
                }
            ),
            elapsed_sec=0.1,
            schema_valid=True,
            required_keys=[],
        )

    monkeypatch.setattr("dharma_swarm.provider_matrix._execute_target_prompt", _fake_execute)

    payload = run_provider_matrix(
        profile="live25",
        artifact_dir=tmp_path,
        include_unavailable=True,
        write_artifacts=False,
        env={},
    )

    delegated_rows = [
        row for row in payload["leaderboard"] if row["lane_role"] != LaneRole.PRIMARY_DRIVER.value
    ]
    assert delegated_rows


def test_run_provider_matrix_uses_smoke_verified_models_for_live_targets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    async def _fake_execute(target, prompt, timeout_seconds, working_dir, env, repair_target=None):
        del prompt
        del timeout_seconds
        del working_dir
        del env
        del repair_target
        return MatrixExecutionResult(
            target_id=target.target_id,
            prompt_id="deployment_case_ranker",
            status="ok",
            response_text=json.dumps(
                {
                    "deployment_case": "tariff_intelligence",
                    "recommendation": "deploy",
                    "confidence": "high",
                    "why_now": "broad_fit",
                }
            ),
            elapsed_sec=0.1,
            schema_valid=True,
            required_keys=[],
        )

    monkeypatch.setattr("dharma_swarm.provider_matrix._execute_target_prompt", _fake_execute)
    monkeypatch.setattr(
        "dharma_swarm.provider_matrix.run_provider_smoke",
        lambda: {
            "ollama": {
                "status": "ok",
                "verified_models": [
                    {"status": "ok", "model": "glm-5:cloud"},
                    {"status": "ok", "model": "deepseek-v3.2:cloud"},
                    {"status": "ok", "model": "kimi-k2.5:cloud"},
                    {"status": "ok", "model": "qwen3-coder:480b-cloud"},
                ],
                "strongest_verified": "glm-5:cloud",
            },
            "nvidia_nim": {
                "status": "ok",
                "verified_models": [
                    {"status": "ok", "model": "meta/llama-3.3-70b-instruct"},
                ],
                "strongest_verified": "meta/llama-3.3-70b-instruct",
            },
            "openrouter": {
                "status": "ok",
                "verified_models": [
                    {"status": "ok", "model": "moonshotai/kimi-k2.5-0127"},
                    {"status": "ok", "model": "z-ai/glm-5-20260211"},
                ],
                "strongest_verified": "moonshotai/kimi-k2.5-0127",
            },
        },
    )

    payload = run_provider_matrix(
        profile="quick",
        max_targets=7,
        max_prompts=1,
        timeout_seconds=1.0,
        artifact_dir=tmp_path,
        include_unavailable=True,
        write_artifacts=False,
        env=None,
    )

    target_models = {target["model"] for target in payload["targets"]}
    assert "qwen3-coder:480b-cloud" in target_models
    assert "qwen3-coder:cloud" not in target_models


def test_build_default_prompt_corpus_workspace_uses_repo_context(tmp_path: Path) -> None:
    (tmp_path / "provider_matrix.py").write_text("def run_provider_matrix():\n    pass\n", encoding="utf-8")
    (tmp_path / "provider_smoke.py").write_text("def run_provider_smoke():\n    pass\n", encoding="utf-8")
    (tmp_path / "runtime_provider.py").write_text("DEFAULT_OPENAI_MODEL = 'gpt-5'\n", encoding="utf-8")

    prompts = build_default_prompt_corpus("workspace", working_dir=str(tmp_path))

    assert prompts
    assert "provider_matrix.py" in prompts[0].prompt
    assert "runtime_provider.py" in prompts[0].prompt


def test_run_provider_matrix_writes_leaderboard_artifacts(tmp_path: Path, monkeypatch) -> None:
    async def _fake_execute(target, prompt, timeout_seconds, working_dir, env, repair_target=None):
        del timeout_seconds
        del working_dir
        del env
        del repair_target
        return MatrixExecutionResult(
            target_id=target.target_id,
            prompt_id=prompt.prompt_id,
            status="ok",
            response_text=json.dumps(
                {
                    "deployment_case": "tariff_intelligence",
                    "recommendation": "deploy",
                    "confidence": "high",
                    "lane": target.provider.value,
                }
            ),
            elapsed_sec=0.25,
            schema_valid=True,
            required_keys=["deployment_case", "recommendation", "confidence"],
        )

    monkeypatch.setattr("dharma_swarm.provider_matrix._execute_target_prompt", _fake_execute)

    payload = run_provider_matrix(
        profile="quick",
        max_targets=2,
        max_prompts=1,
        timeout_seconds=1.0,
        artifact_dir=tmp_path,
        write_artifacts=True,
        include_unavailable=True,
        env={},
    )

    artifacts = payload["artifacts"]
    json_path = Path(artifacts["json_path"])
    markdown_path = Path(artifacts["markdown_path"])

    assert json_path.exists()
    assert markdown_path.exists()

    stored = json.loads(json_path.read_text())
    assert stored["profile"] == "quick"
    assert stored["leaderboard"][0]["provider"] == "codex"
    assert "Provider Matrix Leaderboard" in markdown_path.read_text()


# ---------------------------------------------------------------------------
# STEP 4 — pool projection + live-key oracle filtering
# ---------------------------------------------------------------------------

_LIVE_CORE = {
    "codex",
    "claude_code",
    "anthropic",
    "ollama",
    "nvidia_nim",
    "openai",
    "deepseek",
    "local",
}


def test_matrix_targets_project_from_pool_for_live_providers() -> None:
    """The blueprint model strings come from the model pool, not literals.

    The Ollama cloud lanes (added to the pool in Step 4) must materialise with
    the exact provider-specific model ids the pool holds.
    """
    targets = build_default_matrix_targets(profile="live25", env={}, key_oracle=None)
    ollama_models = {t.model for t in targets if t.provider == ProviderType.OLLAMA}
    assert "kimi-k2.5:cloud" in ollama_models
    assert "deepseek-v3.2:cloud" in ollama_models
    assert "qwen3-coder:480b-cloud" in ollama_models
    assert "minimax-m2.7:cloud" in ollama_models
    # OpenRouter K2.6 floor route projects from the pool entry, not a literal.
    openrouter_models = {t.model for t in targets if t.provider == ProviderType.OPENROUTER}
    assert "moonshotai/kimi-k2.6" in openrouter_models


def test_matrix_shrinks_for_dead_providers_under_live_oracle() -> None:
    """Matrix output is unchanged for live providers and shrinks for dead ones.

    With the GOAL's real live set (openrouter / groq dead), those provider lanes
    are pruned while the live ollama/codex/nim/openai lanes are kept verbatim.
    """
    full = build_default_matrix_targets(profile="live25", env={}, key_oracle=None)
    filtered = build_default_matrix_targets(profile="live25", env={}, key_oracle=_LIVE_CORE)

    full_provs = {t.provider for t in full}
    filt_provs = {t.provider for t in filtered}

    # Dead providers pruned.
    assert ProviderType.OPENROUTER in full_provs
    assert ProviderType.OPENROUTER not in filt_provs
    assert ProviderType.OPENROUTER_FREE not in filt_provs
    assert ProviderType.GROQ not in filt_provs

    # Live providers kept, and their model rows are byte-identical (unchanged).
    assert ProviderType.OLLAMA in filt_provs
    full_ollama = sorted(t.model for t in full if t.provider == ProviderType.OLLAMA)
    filt_ollama = sorted(t.model for t in filtered if t.provider == ProviderType.OLLAMA)
    assert full_ollama == filt_ollama

    # The matrix strictly shrank.
    assert len(filtered) < len(full)
    # Every surviving row is a live provider.
    assert all(t.provider.value in _LIVE_CORE for t in filtered)


def test_matrix_fail_open_when_oracle_unknown() -> None:
    """FAIL-OPEN: an unknown oracle (None) never strands the fleet — every
    blueprint row survives, matching the no-filter full matrix."""
    full = build_default_matrix_targets(profile="quick", env={}, key_oracle=None)
    # An explicit None must equal the full unfiltered set (no pruning at all).
    assert len(full) >= 10
    assert {t.provider for t in full} >= {
        ProviderType.GROQ,
        ProviderType.OPENROUTER_FREE,
        ProviderType.NVIDIA_NIM,
        ProviderType.CEREBRAS,
    }


def test_matrix_marks_dead_key_providers_unavailable_with_reason() -> None:
    """When the oracle prunes, a still-included row (include_unavailable) carries
    an honest availability reason — never a silent live claim."""
    # Force a provider that is config-available but oracle-dead to remain via a
    # generous live set that still excludes groq.
    live = _LIVE_CORE | {"openrouter_free", "cerebras"}
    targets = build_default_matrix_targets(
        profile="quick", env={}, include_unavailable=True, key_oracle=live
    )
    # groq is excluded entirely (blueprint-level prune), so it should be absent.
    assert all(t.provider != ProviderType.GROQ for t in targets)
    # Every surviving target either available or carries a non-live reason.
    for t in targets:
        if not t.available:
            assert t.availability_reason in {"unavailable", "dead_key"}
