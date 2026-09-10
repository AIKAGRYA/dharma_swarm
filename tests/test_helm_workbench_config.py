"""Exercise generated OpenCode files and the real child-process environment boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dharma_swarm.helm_desktop import workbench_config as workbench
from dharma_swarm.helm_desktop.config import DesktopConfig, DesktopError


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[DesktopConfig, Path]:
    repo = tmp_path / "source tree"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts/start_terminal_tui_tmux.sh").write_text("#!/bin/sh\n")
    (repo / "AGENTS.md").write_text("Read repository instructions.\n")
    home = tmp_path / "operator home"
    (home / ".config/opencode").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    provider = {"npm": "@ai-sdk/openai-compatible", "name": "GLM Coding",
                "options": {"baseURL": "https://coding.example.test/v4", "apiKey": "fixture-coding-credential",
                            "headers": {"Authorization": "Bearer fixture-header-credential"}},
                "models": {"glm-5.3": {"name": "GLM 5.3", "limit": {"context": 120000, "output": 8192},
                                       "options": {"label": "literal // slashes, and commas,}", "max_tokens": 8192}},
                           "glm-5.3-flash": {"name": "GLM 5.3 Flash"}}}
    (home / ".config/opencode/opencode.jsonc").write_text(
        "// Existing user configuration\n" + json.dumps({"model": "glm-coding/glm-5.3",
        "provider": {"glm-coding": provider}, "plugin": ["do-not-inherit"]}, indent=2)[:-1] + ",\n}\n")
    binary = tmp_path / "bin/opencode"
    binary.parent.mkdir()
    binary.write_text(f"""#!{sys.executable}
import json, os, sys
print(json.dumps({{
    'argv': sys.argv,
    'private_config': os.environ['OPENCODE_CONFIG'],
    'data': os.environ['XDG_DATA_HOME'],
    'paid_keys': sorted(k for k in os.environ if k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY')),
    'glm_credentials': sum(k.startswith('HELM_WORKBENCH_GLM_') for k in os.environ),
    'inherited_override': 'OPENCODE_CONFIG_CONTENT' in os.environ,
}}))
""")
    binary.chmod(0o700)
    monkeypatch.setenv("PATH", f"{binary.parent}:{os.environ.get('PATH', '')}")
    return DesktopConfig(repo, tmp_path / "private state"), home


def generated(prepared: workbench.PreparedWorkbench) -> tuple[dict, dict]:
    return (json.loads(Path(prepared.config_path).read_text()),
            json.loads(Path(prepared.tui_config_path).read_text()))


def test_default_preparation_is_private_and_secret_free(setup, monkeypatch: pytest.MonkeyPatch) -> None:
    config, home = setup
    source = home / ".config/opencode/opencode.jsonc"
    original = source.read_bytes()
    original_store = home / ".local/share/opencode"
    original_store.mkdir(parents=True)
    (original_store / "auth.json").write_text('{"oauth":"fixture-oauth-credential"}')
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-paid-credential")
    monkeypatch.setenv("OPENCODE_API_KEY", "fixture-zen-credential")
    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", '{"permission":"allow"}')
    monkeypatch.setenv("TMUX", "operator-owned-seat")
    monkeypatch.setattr(workbench, "bootstrap_runtime_env", lambda **_: pytest.fail("default must not bootstrap API keys"))

    prepared = workbench.prepare_workbench(config)
    runtime, tui = generated(prepared)
    assert prepared.model == "glm-coding/glm-5.3"
    assert runtime["enabled_providers"] == ["glm-coding", "opencode", "openai"]
    assert set(runtime["provider"]) == {"glm-coding"}
    assert "plugin" not in runtime and "permission" not in runtime
    assert runtime["provider"]["glm-coding"]["options"]["baseURL"] == "https://coding.example.test/v4"
    assert runtime["provider"]["glm-coding"]["models"]["glm-5.3"]["limit"]["context"] == 120000
    assert runtime["provider"]["glm-coding"]["models"]["glm-5.3"]["options"]["label"].endswith("commas,}")
    assert runtime["provider"]["glm-coding"]["models"]["glm-5.3"]["options"]["max_tokens"] == 8192
    assert "dharma" in runtime["mcp"]
    assert str(config.state_dir / "workbench/HELM.md") in runtime["instructions"]
    assert tui["theme"] == "tokyonight" and tui["mouse"] is True
    assert tui["keybinds"]["model_list"] == "f4,<leader>m"
    assert tui["keybinds"]["model_cycle_recent"] == "f2"
    interrupt = tui["keybinds"]["session_interrupt"].split(",")
    exits = tui["keybinds"]["app_exit"].split(",")
    assert "escape" in interrupt and "ctrl+c" in interrupt
    assert "ctrl+q" in exits and "ctrl+d" in exits and "ctrl+c" not in exits
    assert "environment" not in prepared.public_report()
    assert "environment" not in repr(prepared)
    for path in (config.state_dir / "workbench").rglob("*"):
        if path.is_file():
            assert "credential" not in path.read_text()
            assert path.stat().st_mode & 0o777 == 0o600
    for kind in ("CONFIG", "DATA", "STATE", "CACHE"):
        path = Path(prepared.environment[f"XDG_{kind}_HOME"])
        assert config.state_dir / "workbench" in path.parents
        assert path.stat().st_mode & 0o777 == 0o700
    assert source.read_bytes() == original
    assert (original_store / "auth.json").read_text() == '{"oauth":"fixture-oauth-credential"}'
    assert not any(key in prepared.environment for key in
                   ("OPENAI_API_KEY", "OPENCODE_API_KEY", "TMUX", "OPENCODE_CONFIG_CONTENT"))
    result = subprocess.run(prepared.argv, env=prepared.environment, capture_output=True, text=True, check=True)
    child = json.loads(result.stdout)
    assert child["argv"][1:] == [str(config.repo_root), "--continue", "--model", prepared.model]
    assert child["paid_keys"] == [] and child["glm_credentials"] == 2
    assert child["inherited_override"] is False


def test_api_opt_in_passes_only_the_three_configured_provider_keys(setup, monkeypatch: pytest.MonkeyPatch) -> None:
    config, home = setup
    (home / ".dharma").mkdir()
    (home / ".dharma/agent_keys.env").write_text(
        "OPENAI_API_KEY=fixture-openai-credential\nANTHROPIC_API_KEY=fixture-anthropic-credential\n"
        "OPENROUTER_API_KEY=fixture-openrouter-credential\nZHIPU_API_KEY=fixture-zhipu-credential\n"
        "OTHER_SECRET=fixture-unrelated-credential\n")
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    before = dict(os.environ)
    prepared = workbench.prepare_workbench(config, api_access=True)
    runtime, _ = generated(prepared)
    assert set(prepared.enabled_providers) == {"glm-coding", "opencode", "openai", "anthropic", "openrouter"}
    assert prepared.model == "glm-coding/glm-5.3"
    for name in workbench.API_PROVIDERS:
        key = workbench.PROVIDER_API_KEY_ENV_KEYS[name]
        assert prepared.environment[key] == f"fixture-{name}-credential"
        assert runtime["provider"][name]["options"]["apiKey"] == "{env:" + key + "}"
    assert "ZHIPU_API_KEY" not in prepared.environment and "OTHER_SECRET" not in prepared.environment
    assert os.environ == before
    public = json.dumps(prepared.public_report()) + repr(prepared) + Path(prepared.config_path).read_text()
    assert "credential" not in public
    assert "OAuth is not copied" in prepared.public_report()["subscription_auth"]
    assert "later /connect" in prepared.public_report()["api_access_semantics"]


def test_resume_reuses_private_store_and_preserves_existing_history(setup) -> None:
    config, _ = setup
    first = workbench.prepare_workbench(config)
    history = Path(first.environment["XDG_DATA_HOME"]) / "session-fixture.json"
    history.write_text('{"conversation":"existing"}')
    second = workbench.prepare_workbench(config, model="glm-coding/glm-5.3-flash")
    assert first.environment["XDG_DATA_HOME"] == second.environment["XDG_DATA_HOME"]
    assert second.model == "glm-coding/glm-5.3-flash"
    assert "--continue" in second.argv
    assert history.read_text() == '{"conversation":"existing"}'
    assert workbench.prepare_workbench(config, model="opencode/registry-free-model").model.startswith("opencode/")


@pytest.mark.parametrize("declared_default", ["glm-coding/custom-coding-model", None, "another-provider/model"])
def test_initial_default_identity_comes_from_operator_configuration(setup, declared_default) -> None:
    config, home = setup
    path = home / ".config/opencode/opencode.jsonc"
    source = workbench._jsonc(path.read_text())
    source["provider"]["glm-coding"]["models"] = {"custom-coding-model": {"name": "Operator configured model"}}
    if declared_default is None:
        source.pop("model")
    else:
        source["model"] = declared_default
    path.write_text(json.dumps(source))
    prepared = workbench.prepare_workbench(config)
    assert prepared.model == "glm-coding/custom-coding-model"
    assert generated(prepared)[0]["model"] == prepared.model


def test_empty_configured_model_registry_has_actionable_error(setup) -> None:
    config, home = setup
    path = home / ".config/opencode/opencode.jsonc"
    source = workbench._jsonc(path.read_text())
    source["provider"]["glm-coding"]["models"] = {}
    source.pop("model")
    path.write_text(json.dumps(source))
    with pytest.raises(DesktopError, match="at least one model"):
        workbench.prepare_workbench(config)
    assert not config.state_dir.exists()


def test_routine_reopen_honors_saved_theme_model_and_does_not_force_cli_model(setup) -> None:
    config, _ = setup
    first = workbench.prepare_workbench(config)
    state = Path(first.environment["XDG_STATE_HOME"]) / "opencode"
    state.mkdir()
    (state / "kv.json").write_text('{"theme":"everforest"}')
    (state / "model.json").write_text('{"recent":[{"providerID":"glm-coding","modelID":"glm-5.3-flash"}]}')
    reopened = workbench.prepare_workbench(config)
    runtime, tui = generated(reopened)
    assert reopened.model == runtime["model"] == "glm-coding/glm-5.3-flash"
    assert tui["theme"] == "everforest"
    assert "--model" not in reopened.argv
    explicit = workbench.prepare_workbench(config, model="glm-coding/glm-5.3")
    assert explicit.argv[-2:] == ("--model", "glm-coding/glm-5.3")
    assert generated(explicit)[1]["theme"] == "everforest"


def _roll_provider_models(home: Path, models: dict) -> None:
    path = home / ".config/opencode/opencode.jsonc"
    source = workbench._jsonc(path.read_text())
    source["provider"]["glm-coding"]["models"] = models
    source["model"] = "glm-coding/" + next(iter(models))
    path.write_text(json.dumps(source))


@pytest.mark.parametrize("recent", [
    '{"recent":[{"providerID":"glm-coding","modelID":"glm-9.9-removed"}]}',
    '{"recent":[{"providerID":"not-enabled","modelID":"x"}]}',
    '{"recent":[{"providerID":"glm-coding","modelID":{"nested":"shape"}}]}',
    '{"recent":[{"providerID":"glm-coding","modelID":"has spaces/and*chars"}]}',
    '{"recent":"a string, not a list"}',
])
def test_unusable_recent_model_hint_falls_back_instead_of_blocking_launch(setup, recent: str) -> None:
    config, _ = setup
    first = workbench.prepare_workbench(config)
    state = Path(first.environment["XDG_STATE_HOME"]) / "opencode"
    state.mkdir()
    (state / "model.json").write_text(recent)

    reopened = workbench.prepare_workbench(config)

    assert reopened.model == "glm-coding/glm-5.3"
    assert generated(reopened)[0]["model"] == "glm-coding/glm-5.3"


def test_provider_model_roll_retires_both_stale_generated_and_recent_preferences(setup) -> None:
    config, home = setup
    first = workbench.prepare_workbench(config, model="glm-coding/glm-5.3-flash")
    state = Path(first.environment["XDG_STATE_HOME"]) / "opencode"
    state.mkdir()
    (state / "model.json").write_text('{"recent":[{"providerID":"glm-coding","modelID":"glm-5.3"}]}')
    assert generated(first)[0]["model"] == "glm-coding/glm-5.3-flash"

    _roll_provider_models(home, {"glm-6.0": {"name": "GLM 6.0"}})
    reopened = workbench.prepare_workbench(config)

    assert reopened.model == "glm-coding/glm-6.0"
    assert generated(reopened)[0]["model"] == "glm-coding/glm-6.0"


def test_valid_recent_hint_still_outranks_the_generated_preference(setup) -> None:
    config, _ = setup
    first = workbench.prepare_workbench(config)
    state = Path(first.environment["XDG_STATE_HOME"]) / "opencode"
    state.mkdir()
    (state / "model.json").write_text('{"recent":[{"providerID":"glm-coding","modelID":"glm-5.3-flash"}]}')

    assert workbench.prepare_workbench(config).model == "glm-coding/glm-5.3-flash"


def test_explicitly_requested_unavailable_model_is_still_refused(setup) -> None:
    config, _ = setup
    with pytest.raises(DesktopError, match="not declared in the existing coding provider"):
        workbench.prepare_workbench(config, model="glm-coding/glm-9.9-removed")
    with pytest.raises(DesktopError, match="provider is unavailable"):
        workbench.prepare_workbench(config, model="anthropic/claude-opus-5")


@pytest.mark.parametrize("corrupt", ['{"theme": "everforest"', 'null', '[]', 'not json at all'])
def test_unreadable_foreign_state_is_ignored_without_blocking_launch(setup, corrupt: str) -> None:
    config, _ = setup
    first = workbench.prepare_workbench(config)
    state = Path(first.environment["XDG_STATE_HOME"]) / "opencode"
    state.mkdir()
    (state / "kv.json").write_text(corrupt)
    (state / "model.json").write_text(corrupt)

    reopened = workbench.prepare_workbench(config)

    runtime, tui = generated(reopened)
    assert tui["theme"] == "tokyonight"
    assert reopened.model == runtime["model"] == first.model
    assert (state / "kv.json").read_text() == corrupt
    assert (state / "model.json").read_text() == corrupt


def test_symlinked_foreign_state_directory_is_still_rejected(setup, tmp_path: Path) -> None:
    config, _ = setup
    first = workbench.prepare_workbench(config)
    state = Path(first.environment["XDG_STATE_HOME"])
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "kv.json").write_text('{"theme":"everforest"}')
    (state / "opencode").symlink_to(outside)

    with pytest.raises(DesktopError, match="symlink"):
        workbench.prepare_workbench(config)


@pytest.mark.parametrize("saved", ['{"theme":null}', '{"theme":{"name":"everforest"}}', '{"theme":"bad name!"}'])
def test_unusable_foreign_theme_state_falls_back_instead_of_blocking_launch(setup, saved: str) -> None:
    config, _ = setup
    first = workbench.prepare_workbench(config)
    state = Path(first.environment["XDG_STATE_HOME"]) / "opencode"
    state.mkdir()
    (state / "kv.json").write_text(saved)
    original = (state / "kv.json").read_text()

    reopened = workbench.prepare_workbench(config)

    assert generated(reopened)[1]["theme"] == "tokyonight"
    assert (state / "kv.json").read_text() == original


def test_glm_env_reference_is_resolved_only_into_private_child_env(setup, monkeypatch: pytest.MonkeyPatch) -> None:
    config, home = setup
    path = home / ".config/opencode/opencode.jsonc"
    source = workbench._jsonc(path.read_text())
    source["provider"]["glm-coding"]["options"]["apiKey"] = "{env:FIXTURE_GLM_TOKEN}"
    path.write_text(json.dumps(source))
    monkeypatch.setenv("FIXTURE_GLM_TOKEN", "fixture-referenced-credential")
    prepared = workbench.prepare_workbench(config)
    assert "fixture-referenced-credential" in prepared.environment.values()
    assert "FIXTURE_GLM_TOKEN" not in prepared.environment
    assert "fixture-referenced-credential" not in Path(prepared.config_path).read_text()


def test_glm_alias_reference_falls_back_to_canonical_registry_without_api_access(setup, monkeypatch: pytest.MonkeyPatch) -> None:
    config, home = setup
    path = home / ".config/opencode/opencode.jsonc"
    source = workbench._jsonc(path.read_text())
    source["provider"]["glm-coding"]["options"]["apiKey"] = "{env:GLM_API_KEY}"
    path.write_text(json.dumps(source))
    (home / ".dharma").mkdir()
    (home / ".dharma/agent_keys.env").write_text(
        "ZHIPU_API_KEY=fixture-canonical-credential\nOPENAI_API_KEY=fixture-unselected-credential\n")
    monkeypatch.delenv("GLM_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    before = dict(os.environ)
    prepared = workbench.prepare_workbench(config)
    assert prepared.enabled_providers == ("glm-coding", "opencode", "openai")
    assert "fixture-canonical-credential" in prepared.environment.values()
    assert "fixture-unselected-credential" not in prepared.environment.values()
    assert not any(key in prepared.environment for key in ("GLM_API_KEY", "ZHIPU_API_KEY", "OPENAI_API_KEY"))
    assert "fixture-canonical-credential" not in Path(prepared.config_path).read_text()
    assert "credential" not in repr(prepared) + json.dumps(prepared.public_report())
    assert os.environ == before


def test_openai_is_eligible_for_operator_login_without_importing_existing_api_key(setup, monkeypatch: pytest.MonkeyPatch) -> None:
    config, _ = setup
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-unimported-credential")
    prepared = workbench.prepare_workbench(config, model="openai/operator-login-model")
    runtime, _ = generated(prepared)
    assert "openai" in runtime["enabled_providers"]
    assert "openai" not in runtime["provider"]
    assert "OPENAI_API_KEY" not in prepared.environment
    assert "/connect > OpenAI > ChatGPT Plus/Pro" in prepared.public_report()["subscription_auth"]
    assert "native Claude Code" in prepared.public_report()["subscription_auth"]
    assert prepared.api_access is False


@pytest.mark.parametrize("model", ["anthropic/unavailable", "unrelated/model", "glm-coding/missing", "../bad"])
def test_unavailable_or_invalid_model_does_not_generate_files(setup, model: str) -> None:
    config, _ = setup
    with pytest.raises(DesktopError):
        workbench.prepare_workbench(config, model=model)
    assert not config.state_dir.exists()


def test_later_user_config_edits_are_preserved(setup) -> None:
    config, _ = setup
    prepared = workbench.prepare_workbench(config)
    path = Path(prepared.tui_config_path)
    edit = '{"theme":"everforest"}\n'
    path.write_text(edit)
    with pytest.raises(DesktopError, match="later edits"):
        workbench.prepare_workbench(config)
    assert path.read_text() == edit


def test_generated_paths_reject_symlinks_and_preserve_the_target(setup, tmp_path: Path) -> None:
    config, _ = setup
    target = tmp_path / "unrelated"
    target.mkdir()
    (target / "keep").write_text("unchanged")
    config.state_dir.mkdir()
    (config.state_dir / "workbench").symlink_to(target)
    with pytest.raises(DesktopError, match="symlink"):
        workbench.prepare_workbench(config)
    assert list(target.iterdir()) == [target / "keep"]


def test_legacy_home_config_is_not_discovered_or_modified(setup) -> None:
    config, home = setup
    legacy = home / ".opencode"
    legacy.mkdir()
    sentinel = legacy / "plugin.ts"
    sentinel.write_text("untouched")
    with pytest.raises(DesktopError, match="legacy"):
        workbench.prepare_workbench(config)
    assert sentinel.read_text() == "untouched"
    assert not config.state_dir.exists()


@pytest.mark.parametrize("text", ['{"provider":{},"provider":{}}', '{"provider": NaN}', '{bad json'])
def test_invalid_source_config_never_echoes_credential_content(setup, text: str) -> None:
    config, home = setup
    (home / ".config/opencode/opencode.jsonc").write_text(text + " // fixture-source-credential")
    with pytest.raises(DesktopError) as error:
        workbench.prepare_workbench(config)
    assert "credential" not in str(error.value)
    assert not config.state_dir.exists()
