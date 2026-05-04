from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "measure_substrate_nativeness.py"


def load_module():
    spec = importlib.util.spec_from_file_location("measure_substrate_nativeness", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_measurement_returns_single_score_and_breakdown():
    module = load_module()

    payload = module.measure(ROOT)

    assert isinstance(payload["score"], float)
    assert 0.0 <= payload["score"] <= 1.0
    assert payload["total_surfaces"] >= 12
    assert any(
        row["name"] == "sqlite:runtime_state.sessions"
        for row in payload["surfaces"]
    )
    assert all("criteria" in row for row in payload["surfaces"])


def test_script_writes_dated_baseline_json(tmp_path):
    module = load_module()
    state_dir = tmp_path / ".dharma"

    exit_code = module.main(
        [
            "--repo-root",
            str(ROOT),
            "--state-dir",
            str(state_dir),
            "--date",
            "2026-05-04",
        ]
    )

    out_path = state_dir / "baselines" / "substrate_nativeness_2026-05-04.json"
    assert exit_code == 0
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert isinstance(data["score"], float)
    assert data["native_surfaces"] <= data["total_surfaces"]
