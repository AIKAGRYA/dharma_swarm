from __future__ import annotations

import subprocess

from dharma_swarm.terminal_commands import surfaces


def test_cmd_tui_stops_cleanly_on_bun_keyboard_interrupt(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    terminal_dir = tmp_path / "terminal"
    terminal_dir.mkdir()
    (terminal_dir / "package.json").write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        del kwargs
        calls.append([str(part) for part in cmd])
        if cmd[:2] == ["/bin/zsh", "-lc"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")
        raise KeyboardInterrupt

    monkeypatch.setattr(surfaces, "DHARMA_SWARM", tmp_path)
    monkeypatch.setattr(surfaces.shutil, "which", lambda name: "/usr/local/bin/bun")
    monkeypatch.setattr(surfaces.subprocess, "run", _fake_run)

    surfaces.cmd_tui()

    out = capsys.readouterr().out
    assert "DGC dashboard stopped." in out
    assert calls[-1] == ["/usr/local/bin/bun", "run", "start"]


def test_cmd_tui_stops_cleanly_on_legacy_keyboard_interrupt(
    monkeypatch,
    capsys,
) -> None:
    import dharma_swarm.tui as tui

    def _raise_keyboard_interrupt() -> None:
        raise KeyboardInterrupt

    monkeypatch.setenv("DGC_USE_LEGACY_TUI", "1")
    monkeypatch.setattr(tui, "run", _raise_keyboard_interrupt)

    surfaces.cmd_tui()

    out = capsys.readouterr().out
    assert "DGC dashboard stopped." in out
