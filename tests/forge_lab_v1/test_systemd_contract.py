from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "scripts" / "ops" / "systemd" / "rsi-lab-run.service"
TIMER = ROOT / "scripts" / "ops" / "systemd" / "rsi-lab-run.timer"


def _directives(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";", "[")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def test_service_is_nonroot_bounded_foreground_and_fail_closed() -> None:
    text = SERVICE.read_text(encoding="utf-8")
    values = _directives(SERVICE)

    assert values["ExecStart"] == (
        "/root/rsi-lab/current/repo/scripts/forge_lab/rsi run --unattended"
    )
    assert values["ExecCondition"] == (
        "/usr/bin/test -x /root/rsi-lab/current/repo/scripts/forge_lab/rsi"
    )
    assert values["Type"] == "exec"
    assert values["User"] not in {"", "0", "root"}
    assert values["Group"] not in {"", "0", "root"}
    assert values["Restart"].lower() == "no"
    assert values["KillMode"] in {"control-group", "mixed"}
    assert values["UMask"] == "0077"
    assert values["RuntimeMaxSec"] not in {"", "0", "infinity"}
    assert values["TimeoutStopSec"] not in {"", "0", "infinity"}
    assert values["NoNewPrivileges"].lower() == "yes"
    assert values["ProtectSystem"] == "strict"
    assert values["PrivateTmp"].lower() == "yes"
    assert values["PrivateDevices"].lower() == "yes"
    assert values["CapabilityBoundingSet"] == ""
    assert values["AmbientCapabilities"] == ""
    assert values["MemoryMax"] not in {"", "infinity"}
    assert values["CPUQuota"].endswith("%")
    assert int(values["TasksMax"]) > 0
    for name in ("LimitNOFILE", "LimitNPROC", "LimitCORE", "LimitFSIZE"):
        assert name in values
    assert values["ReadWritePaths"] == "/root/rsi-lab/current/state"
    assert "[Install]" not in text


def test_service_contains_no_legacy_or_route_literals() -> None:
    text = SERVICE.read_text(encoding="utf-8").lower()

    assert "tmux" not in text
    assert "current-main" not in text
    assert "moonshot" not in text
    assert "kimi" not in text
    assert "glm-" not in text
    assert "environmentfile" not in text


def test_timer_is_inert_by_default_and_never_catches_up() -> None:
    text = TIMER.read_text(encoding="utf-8")
    values = _directives(TIMER)

    assert values["Unit"] == "rsi-lab-run.service"
    assert values["Persistent"].lower() == "false"
    assert "OnCalendar" in values
    assert "[Install]" not in text
