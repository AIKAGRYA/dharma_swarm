from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_populator():
    script = Path(__file__).resolve().parent.parent / "scripts" / "system_map_populator.py"
    spec = importlib.util.spec_from_file_location("system_map_populator", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_system_map_combines_operating_and_audit_organs(tmp_path: Path) -> None:
    populator = _load_populator()
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    (audit_dir / "central_loop_trace_2026-05-07.md").write_text(
        "# Central Loop\n\ncron jobs feed the central loop but value event proof is missing.\n",
        encoding="utf-8",
    )

    payload = populator.build_system_map(repo_root=tmp_path, audit_dir=audit_dir)
    organs = {organ["name"]: organ for organ in payload["organs"]}

    assert payload["schema_version"] == "system_map.v0"
    assert "agentops" in organs
    assert organs["central_loop"]["coherence_state"] == "partial"
    assert organs["central_loop"]["evidence_refs"]
    assert organs["central_loop"]["next_bindable_gap"]


def test_main_writes_latest_json(tmp_path: Path) -> None:
    populator = _load_populator()
    audit_dir = tmp_path / "audit"
    output = tmp_path / "reports" / "system_map" / "latest.json"
    audit_dir.mkdir()
    (audit_dir / "phase_0.md").write_text("omega_divergence belongs to algedonic stream\n", encoding="utf-8")

    result = populator.main(
        [
            "--repo-root",
            str(tmp_path),
            "--audit-dir",
            str(audit_dir),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert any(organ["name"] == "algedonic_stream" for organ in payload["organs"])
