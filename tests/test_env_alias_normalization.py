"""Tests for dkeys ↔ dharma_swarm env alias normalization.

Covers:
- The ENV_ALIASES table in api_keys.py
- normalize_env_aliases() with dict envs (no os.environ mutation)
- Canonical values are never overwritten
- Dry-run mode returns planned changes without mutation
- The shell-level aliases in load_runtime_env.sh
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from dharma_swarm.api_keys import (
    ENV_ALIASES,
    GOOGLE_AI_API_KEY_ENV,
    KIMI_API_KEY_ENV,
    NVIDIA_NIM_API_KEY_ENV,
    PPLX_API_KEY_ENV,
    ZHIPU_API_KEY_ENV,
    apply_env_assignment,
    bootstrap_runtime_env,
    env_value,
    normalize_env_aliases,
)


class TestEnvAliasTable:
    def test_gemini_maps_to_google_ai(self) -> None:
        assert ENV_ALIASES["GEMINI_API_KEY"] == GOOGLE_AI_API_KEY_ENV

    def test_nvidia_maps_to_nvidia_nim(self) -> None:
        assert ENV_ALIASES["NVIDIA_API_KEY"] == NVIDIA_NIM_API_KEY_ENV

    def test_nim_maps_to_nvidia_nim(self) -> None:
        assert ENV_ALIASES["NIM_API_KEY"] == NVIDIA_NIM_API_KEY_ENV

    def test_perplexity_maps_to_pplx(self) -> None:
        assert ENV_ALIASES["PERPLEXITY_API_KEY"] == PPLX_API_KEY_ENV

    def test_zai_aliases_map_to_zhipu(self) -> None:
        assert ENV_ALIASES["GLM_API_KEY"] == ZHIPU_API_KEY_ENV
        assert ENV_ALIASES["ZAI_API_KEY"] == ZHIPU_API_KEY_ENV
        assert ENV_ALIASES["BIGMODEL_API_KEY"] == ZHIPU_API_KEY_ENV

    def test_kimi_code_alias_maps_to_kimi(self) -> None:
        assert ENV_ALIASES["MOONSHOT_KIMI_API_KEY"] == KIMI_API_KEY_ENV

    def test_self_mapping_is_noop(self) -> None:
        for alias, canonical in ENV_ALIASES.items():
            if alias == canonical:
                continue
            assert alias != canonical


class TestNormalizeEnvAliases:
    def test_copies_gemini_to_google_ai(self) -> None:
        env: dict[str, str] = {"GEMINI_API_KEY": "gk-test-12345"}
        applied = normalize_env_aliases(env)
        assert env["GOOGLE_AI_API_KEY"] == "gk-test-12345"
        assert len(applied) == 1
        assert applied[0][0] == "GEMINI_API_KEY"
        assert applied[0][1] == "GOOGLE_AI_API_KEY"

    def test_copies_nvidia_to_nvidia_nim(self) -> None:
        env: dict[str, str] = {"NVIDIA_API_KEY": "nvapi-abc"}
        applied = normalize_env_aliases(env)
        assert env["NVIDIA_NIM_API_KEY"] == "nvapi-abc"
        assert len(applied) >= 1

    def test_copies_nim_to_nvidia_nim(self) -> None:
        env: dict[str, str] = {"NIM_API_KEY": "nim-xyz"}
        applied = normalize_env_aliases(env)
        assert env["NVIDIA_NIM_API_KEY"] == "nim-xyz"

    def test_copies_perplexity_to_pplx(self) -> None:
        env: dict[str, str] = {"PERPLEXITY_API_KEY": "pplx-test"}
        applied = normalize_env_aliases(env)
        assert env["PPLX_API_KEY"] == "pplx-test"

    def test_copies_glm_to_zhipu(self) -> None:
        env: dict[str, str] = {"GLM_API_KEY": "zhipu-test"}
        applied = normalize_env_aliases(env)
        assert env["ZHIPU_API_KEY"] == "zhipu-test"
        assert ("GLM_API_KEY", "ZHIPU_API_KEY") in applied

    def test_copies_moonshot_kimi_to_kimi(self) -> None:
        env: dict[str, str] = {"MOONSHOT_KIMI_API_KEY": "kimi-test"}
        applied = normalize_env_aliases(env)
        assert env["KIMI_API_KEY"] == "kimi-test"
        assert ("MOONSHOT_KIMI_API_KEY", "KIMI_API_KEY") in applied

    def test_does_not_overwrite_existing_canonical(self) -> None:
        env: dict[str, str] = {
            "GEMINI_API_KEY": "old-gemini-key",
            "GOOGLE_AI_API_KEY": "canonical-value",
        }
        applied = normalize_env_aliases(env)
        assert env["GOOGLE_AI_API_KEY"] == "canonical-value"
        assert len([a for a in applied if a[1] == "GOOGLE_AI_API_KEY"]) == 0

    def test_dry_run_does_not_mutate(self) -> None:
        env: dict[str, str] = {"GEMINI_API_KEY": "test-key"}
        applied = normalize_env_aliases(env, dry_run=True)
        assert "GOOGLE_AI_API_KEY" not in env
        assert len(applied) == 1

    def test_empty_alias_is_ignored(self) -> None:
        env: dict[str, str] = {"GEMINI_API_KEY": "  "}
        applied = normalize_env_aliases(env)
        assert "GOOGLE_AI_API_KEY" not in env
        assert len(applied) == 0

    def test_multiple_aliases_applied(self) -> None:
        env: dict[str, str] = {
            "GEMINI_API_KEY": "gemini-val",
            "NVIDIA_API_KEY": "nvidia-val",
            "PERPLEXITY_API_KEY": "pplx-val",
        }
        applied = normalize_env_aliases(env)
        assert env["GOOGLE_AI_API_KEY"] == "gemini-val"
        assert env["NVIDIA_NIM_API_KEY"] == "nvidia-val"
        assert env["PPLX_API_KEY"] == "pplx-val"
        assert len(applied) >= 3

    def test_nvidia_api_key_does_not_overwrite_nim(self) -> None:
        env: dict[str, str] = {
            "NVIDIA_API_KEY": "stale-nvidia",
            "NIM_API_KEY": "stale-nim",
            "NVIDIA_NIM_API_KEY": "canonical-nim",
        }
        applied = normalize_env_aliases(env)
        assert env["NVIDIA_NIM_API_KEY"] == "canonical-nim"

    def test_first_alias_wins_when_two_share_canonical(self) -> None:
        """When NVIDIA_API_KEY and NIM_API_KEY both map to NVIDIA_NIM_API_KEY,
        only the first one in iteration order should be applied — the second
        must see the canonical as already set and skip."""
        env: dict[str, str] = {
            "NVIDIA_API_KEY": "first-wins",
            "NIM_API_KEY": "second-loses",
        }
        applied = normalize_env_aliases(env)
        assert env["NVIDIA_NIM_API_KEY"] == "first-wins"
        nvidia_applied = [a for a in applied if a[1] == "NVIDIA_NIM_API_KEY"]
        assert len(nvidia_applied) == 1

    def test_unresolved_shell_reference_is_treated_as_absent(self) -> None:
        env: dict[str, str] = {
            "GEMINI_API_KEY": "real-gemini",
            "GOOGLE_AI_API_KEY": "$GEMINI_API_KEY",
        }
        applied = normalize_env_aliases(env)
        assert env["GOOGLE_AI_API_KEY"] == "real-gemini"
        assert applied == [("GEMINI_API_KEY", "GOOGLE_AI_API_KEY")]
        assert env_value("GOOGLE_AI_API_KEY", env) == "real-gemini"


class TestRuntimeEnvBootstrap:
    def test_apply_env_assignment_skips_unresolved_shell_reference(self) -> None:
        env: dict[str, str] = {}
        assert apply_env_assignment("export GOOGLE_AI_API_KEY=$GEMINI_API_KEY", env) is False
        assert "GOOGLE_AI_API_KEY" not in env

    def test_apply_env_assignment_expands_existing_simple_reference(self) -> None:
        env: dict[str, str] = {"GEMINI_API_KEY": "real-gemini"}
        assert apply_env_assignment("export GOOGLE_AI_API_KEY=$GEMINI_API_KEY", env) is True
        assert env["GOOGLE_AI_API_KEY"] == "real-gemini"

    def test_bootstrap_runtime_env_loads_files_then_normalizes(self, tmp_path: Path) -> None:
        env_file = tmp_path / "agent_keys.env"
        env_file.write_text(
            "export GOOGLE_AI_API_KEY=$GEMINI_API_KEY\n"
            "export GEMINI_API_KEY='real-gemini'\n"
            "export OPENROUTER_API_KEY='or-test'\n",
            encoding="utf-8",
        )
        env: dict[str, str] = {}

        bootstrap_runtime_env(env=env, env_paths=(env_file,))

        assert env["GEMINI_API_KEY"] == "real-gemini"
        assert env["GOOGLE_AI_API_KEY"] == "real-gemini"
        assert env["OPENROUTER_API_KEY"] == "or-test"


class TestNormalizeDkeysScript:
    """Smoke-test the CLI wrapper."""

    _SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "normalize_dkeys_env.py"
    _LOAD_RUNTIME_ENV = Path(__file__).resolve().parent.parent / "scripts" / "load_runtime_env.sh"

    def test_load_runtime_env_sources_agent_keys_file(self) -> None:
        text = self._LOAD_RUNTIME_ENV.read_text(encoding="utf-8")
        assert "$HOME/.dharma/agent_keys.env" in text

    def test_dry_run_no_crash(self) -> None:
        result = subprocess.run(
            [sys.executable, str(self._SCRIPT)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0

    def test_emit_exports_with_alias(self) -> None:
        import os as _os

        env = _os.environ.copy()
        env["GEMINI_API_KEY"] = "test-gemini-key"
        env.pop("GOOGLE_AI_API_KEY", None)
        result = subprocess.run(
            [sys.executable, str(self._SCRIPT), "--emit-exports"],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        assert result.returncode == 0
        assert "GOOGLE_AI_API_KEY" in result.stdout
        assert "${GEMINI_API_KEY}" in result.stdout
        assert "test-gemini-key" not in result.stdout

    def test_emit_exports_mirror_alias_table(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("normalize_dkeys_env", self._SCRIPT)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        expected_pairs = {
            (alias, canonical)
            for alias, canonical in ENV_ALIASES.items()
            if alias != canonical
        }
        emitted_pairs = set()
        for line in module._SAFE_EXPORT_LINES:
            for alias, canonical in expected_pairs:
                if f"${{{alias}:-}}" in line and f"export {canonical}=" in line:
                    emitted_pairs.add((alias, canonical))
        assert emitted_pairs == expected_pairs
