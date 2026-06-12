from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.runtime.forge_swarm_evolution_arena_v0_preflight import run_preflight
from scripts.runtime.forge_swarm_evolution_arena_v0_taskpack_builder import build_pack


def test_taskpack_builder_produces_green_preflight_gates(tmp_path: Path) -> None:
    run_dir = tmp_path / "measurement-candidate"

    result = build_pack(run_dir, generated_at="2026-06-05T14:10:00Z")
    report = run_preflight(
        run_dir=run_dir,
        repo_root=tmp_path,
        generated_at="2026-06-05T14:15:00Z",
        write_packet=True,
    )

    assert result["task_pack_gate"]["status"] == "green"
    assert result["review_receipt"]["status"] == "pass"
    assert report["closeout_state"] == "preflight_ready"
    assert report["measurement_mode_allowed"] is True
    assert report["task_pack_gate"]["status"] == "green"
    assert report["roster_gate"]["status"] == "green"
    manifest_hash = hashlib.sha256((run_dir / "task_manifest.json").read_bytes()).hexdigest()
    assert report["task_pack_gate"]["normalized_payload"]["task_manifest_sha256"] == f"sha256:{manifest_hash}"
    assert (run_dir / "tasks" / "tabular_cost_model" / "visible" / "challenge_inputs.csv").exists()
    assert not (run_dir / "tasks" / "tabular_cost_model" / "visible" / "hidden_inputs.csv").exists()
