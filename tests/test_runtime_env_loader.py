"""Tests for dharma_swarm/runtime_env_loader.py — the ONE loader seam."""

from __future__ import annotations

import os

import pytest

from dharma_swarm import runtime_env_loader as rel


# ---------------------------------------------------------------------------
# keychain fallback
# ---------------------------------------------------------------------------


def test_keychain_noop_off_darwin():
    env: dict[str, str] = {}
    assert rel.load_keychain_fallbacks(env, platform="linux") == 0
    assert env == {}


def test_keychain_fills_only_missing_keys():
    calls: list[tuple[str, str]] = []

    def fake_lookup(account: str, service: str) -> str:
        calls.append((account, service))
        return "kc-value" if service == "groq-api-key" else ""

    env = {"ANTHROPIC_API_KEY": "already-set"}
    loaded = rel.load_keychain_fallbacks(env, platform="darwin", lookup=fake_lookup)

    assert loaded == 1
    assert env["GROQ_API_KEY"] == "kc-value"
    assert env["ANTHROPIC_API_KEY"] == "already-set"
    # present key was skipped entirely — no lookup issued for it
    assert all(service != "anthropic-api-key" for _, service in calls)


def test_keychain_lookup_errors_never_raise():
    def broken_lookup(account: str, service: str) -> str:
        raise RuntimeError("keychain unavailable")

    env: dict[str, str] = {}
    assert rel.load_keychain_fallbacks(env, platform="darwin", lookup=broken_lookup) == 0


# ---------------------------------------------------------------------------
# split-key-store guard
# ---------------------------------------------------------------------------


def test_detect_project_env_secret_names(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "WIKI_PATH=/some/path\n"
        "OPENAI_API_KEY=sk-broken\n"
        "export GITHUB_TOKEN=ghp_x\n"
        "EMPTY_API_KEY=\n"
        "LITESTREAM_SECRET_ACCESS_KEY=abc\n"
    )
    names = rel.detect_project_env_secret_names(env_file)
    assert names == [
        "OPENAI_API_KEY",
        "GITHUB_TOKEN",
        "LITESTREAM_SECRET_ACCESS_KEY",
    ]


def test_split_store_warns_when_both_exist(tmp_path, caplog):
    project = tmp_path / ".env"
    project.write_text("OPENAI_API_KEY=sk-broken\n")
    vault = tmp_path / "agent_keys.env"
    vault.write_text("OPENAI_API_KEY=real\n")

    with caplog.at_level("WARNING"):
        names = rel.warn_on_split_key_stores(project, vault, force=True)

    assert names == ["OPENAI_API_KEY"]
    assert any("SPLIT KEY STORES" in rec.message for rec in caplog.records)
    # names only — the value must never be logged
    assert all("sk-broken" not in rec.getMessage() for rec in caplog.records)


def test_split_store_silent_without_vault(tmp_path, caplog):
    project = tmp_path / ".env"
    project.write_text("OPENAI_API_KEY=sk-fine-on-vps\n")
    vault = tmp_path / "agent_keys.env"  # does not exist (VPS-style host)

    with caplog.at_level("WARNING"):
        names = rel.warn_on_split_key_stores(project, vault, force=True)

    assert names == []
    assert not caplog.records


# ---------------------------------------------------------------------------
# emit_shell_exports (the shell-wrapper contract)
# ---------------------------------------------------------------------------


@pytest.fixture()
def restore_environ():
    snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snapshot)


def test_emit_shell_exports_quotes_newly_set_vars(tmp_path, restore_environ):
    env_file = tmp_path / "agent_keys.env"
    env_file.write_text('DHARMA_TEST_LOADER_VAR="value with spaces"\n')
    os.environ.pop("DHARMA_TEST_LOADER_VAR", None)
    # The loaded marker is asserted as newly set below, but import-time
    # bootstraps elsewhere in the suite may have already set it; emit diffs
    # against the current environ, so it must be absent going in.
    os.environ.pop("DHARMA_RUNTIME_ENV_LOADED", None)

    output = rel.emit_shell_exports(env_paths=[env_file])

    assert "export DHARMA_TEST_LOADER_VAR='value with spaces'" in output
    assert "export DHARMA_RUNTIME_ENV_LOADED=1" in output


def test_emit_shell_exports_skips_already_set_vars(tmp_path, restore_environ):
    env_file = tmp_path / "agent_keys.env"
    env_file.write_text("DHARMA_TEST_LOADER_VAR2=from-file\n")
    os.environ["DHARMA_TEST_LOADER_VAR2"] = "from-process"

    output = rel.emit_shell_exports(env_paths=[env_file])

    # never-overwrite semantics: process env wins, so nothing to export
    assert "DHARMA_TEST_LOADER_VAR2" not in output


def test_main_emit_exports_exit_codes():
    assert rel.main(["bogus-command"]) == 2
