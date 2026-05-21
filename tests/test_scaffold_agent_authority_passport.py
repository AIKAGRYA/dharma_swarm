from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "scaffold_agent_authority_passport.py"
    )
    spec = importlib.util.spec_from_file_location(
        "scaffold_agent_authority_passport_script",
        path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scaffold_authority_passport_for_registered_external_agent(tmp_path):
    module = _load_script_module()
    home = tmp_path / ".dharma"
    root = home / "external_agents" / "demo_worker"
    root.mkdir(parents=True)
    (root / "registration.json").write_text(
        json.dumps(
            {
                "agent_uid": "demo_worker",
                "callsign": "demo-worker",
                "display_name": "Demo Worker",
                "harness": "demo_harness",
                "model_identity": "demo/model",
                "authority": "external_worker_evidence_only",
            }
        ),
        encoding="utf-8",
    )

    passport = module.scaffold_passport(
        dharma_home=home,
        agent_uid="demo_worker",
        rank="operator_candidate",
        lanes=("morning_ops_operator",),
        review_days=14,
        reviewer="operator:test",
        dry_run=False,
    )

    passport_path = root / "authority" / "passport.json"
    reviews_path = root / "authority" / "reviews.jsonl"
    assert passport["rank"] == "operator_candidate"
    assert passport["status"] == "scaffolded_not_promoted"
    assert "morning_ops_operator" in passport["active_lanes"]
    assert "write_repo_files" in passport["capabilities"]["gated"]
    assert "self_promote_authority" in passport["capabilities"]["forbidden"]
    assert passport_path.exists()
    assert reviews_path.exists()
