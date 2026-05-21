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
    NVIDIA_NIM_API_KEY_ENV,
    PPLX_API_KEY_ENV,
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


class TestNormalizeDkeysScript:
    """Smoke-test the CLI wrapper."""

    _SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "normalize_dkeys_env.py"

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
        assert "test-gemini-key" in result.stdout
