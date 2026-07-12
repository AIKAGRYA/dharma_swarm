from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import dkeys


@pytest.fixture
def isolated_dkeys(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    monkeypatch.setattr(dkeys, "HOME", home)
    monkeypatch.setattr(dkeys, "KEY_FILE", home / ".dharma" / "agent_keys.env")
    monkeypatch.setattr(dkeys, "HERMES_ENV", home / ".hermes" / ".env")
    monkeypatch.setattr(dkeys, "CACHE_FILE", home / ".dharma" / "keys_status.json")
    return home


def test_atomic_upsert_quotes_values_and_preserves_prior_write(isolated_dkeys: Path) -> None:
    assert dkeys._atomic_upsert_key_file("FIRST_KEY", "first") == ["FIRST_KEY"]
    assert dkeys._atomic_upsert_key_file("SECOND_KEY", "two words") == ["SECOND_KEY"]

    text = dkeys.KEY_FILE.read_text(encoding="utf-8")
    assert "export FIRST_KEY=first" in text
    assert "export SECOND_KEY='two words'" in text
    assert dkeys.KEY_FILE.stat().st_mode & 0o777 == 0o600


def test_inline_secret_and_raw_environment_export_are_refused(
    isolated_dkeys: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as inline:
        dkeys.cmd_add(["TEST_KEY=dummy"])
    with pytest.raises(SystemExit) as raw_env:
        dkeys.cmd_env([])

    assert inline.value.code == 2
    assert raw_env.value.code == 2
    assert not dkeys.KEY_FILE.exists()
    output = capsys.readouterr()
    assert "dummy" not in output.out
    assert "dummy" not in output.err


def test_safe_json_never_emits_mask_or_key_metadata(
    isolated_dkeys: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dkeys.save_cache(
        {
            "last_test_ts": 1.0,
            "rows": {
                "xai": {
                    "glyph": "✓",
                    "http": 200,
                    "status": "live",
                    "masked": "<set:len=99>",
                    "key_present": True,
                }
            },
        }
    )

    dkeys.cmd_safe_json([])

    raw = capsys.readouterr().out
    payload = json.loads(raw)
    assert payload["schema_version"] == "dharma.dkeys.safe_status.v1"
    assert "masked" not in raw
    assert "key_present" not in raw
    assert "len=" not in raw


def test_exec_injects_only_named_stored_reference(
    isolated_dkeys: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dkeys._atomic_upsert_key_file("ONLY_THIS_KEY", "dummy-one")
    dkeys._atomic_upsert_key_file("NOT_THIS_KEY", "dummy-two")
    captured: dict[str, object] = {}

    def fake_exec(file: str, argv: list[str], env: dict[str, str]) -> None:
        captured.update(
            {
                "file": file,
                "argv": list(argv),
                "requested_present": bool(env.get("ONLY_THIS_KEY")),
                "unrequested_present": bool(env.get("NOT_THIS_KEY")),
            }
        )

    monkeypatch.setattr(dkeys.os, "execvpe", fake_exec)
    dkeys.cmd_exec(["ONLY_THIS_KEY", "--", "tool", "--flag"])

    assert captured == {
        "file": "tool",
        "argv": ["tool", "--flag"],
        "requested_present": True,
        "unrequested_present": False,
    }


def test_cache_write_is_atomic_and_private(isolated_dkeys: Path) -> None:
    dkeys.save_cache({"rows": {}})

    assert json.loads(dkeys.CACHE_FILE.read_text(encoding="utf-8")) == {"rows": {}}
    assert dkeys.CACHE_FILE.stat().st_mode & 0o777 == 0o600
    assert not list(dkeys.CACHE_FILE.parent.glob(f".{dkeys.CACHE_FILE.name}.tmp.*"))


def test_qwen_probe_requires_a_credential_file(
    isolated_dkeys: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    qwen = isolated_dkeys / ".qwen"
    qwen.mkdir(parents=True)
    (qwen / "settings.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("HOME", str(isolated_dkeys))

    glyph, status, _ = dkeys._probe_qwen()

    assert glyph == "·"
    assert status == "qwen dir, no creds"
