from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _write_map(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "system_map.v0",
                "organs": [
                    {
                        "name": "agentops",
                        "owns": "bounded repo execution facts",
                        "coherence_state": "bound",
                        "next_bindable_gap": "",
                    },
                    {
                        "name": "metabolic_clock",
                        "owns": "scheduled metabolic jobs",
                        "coherence_state": "partial",
                        "next_bindable_gap": "bind launchd to installed dgc cron verb",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_cmd_map_lists_organs(tmp_path: Path, capsys) -> None:
    from dharma_swarm.dgc_cli import cmd_system_map

    map_path = tmp_path / "latest.json"
    _write_map(map_path)

    assert cmd_system_map("list", map_path=map_path) == 0
    out = capsys.readouterr().out
    assert "agentops\tbound" in out
    assert "metabolic_clock\tpartial" in out


def test_cmd_map_reports_drifted_gaps(tmp_path: Path, capsys) -> None:
    from dharma_swarm.dgc_cli import cmd_system_map

    map_path = tmp_path / "latest.json"
    _write_map(map_path)

    assert cmd_system_map("gaps", map_path=map_path) == 0
    out = capsys.readouterr().out
    assert "metabolic_clock: bind launchd to installed dgc cron verb" in out


def test_cmd_map_missing_map_returns_nonzero(tmp_path: Path, capsys) -> None:
    from dharma_swarm.dgc_cli import cmd_system_map

    assert cmd_system_map("list", map_path=tmp_path / "missing.json") == 2
    err = capsys.readouterr().err
    assert "System map not found" in err


def test_dgc_cli_main_dispatches_map_show(tmp_path: Path, capsys) -> None:
    from dharma_swarm.dgc_cli import cmd_system_map

    map_path = tmp_path / "latest.json"
    _write_map(map_path)

    result = cmd_system_map("show", organ="metabolic_clock", map_path=map_path)

    assert result == 0
    out = capsys.readouterr().out
    assert "name: metabolic_clock" in out
    assert "coherence_state: partial" in out
