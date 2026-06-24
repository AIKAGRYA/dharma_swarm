from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from dharma_swarm.holon_l4_model_probe_lease import (
    default_model_probe_lease_path,
    issue_model_probe_lease,
    safe_lease_filename,
    write_model_probe_lease,
)
from dharma_swarm.holon_l4_smoke import (
    MODEL_PROBE_LEASE_SCHEMA_VERSION,
    model_probe_lease_digest,
)


def _make_agent(root: Path, name: str = "codex_composer") -> Path:
    agent_dir = root / name
    (agent_dir / "prompt_variants").mkdir(parents=True)
    (agent_dir / "identity.json").write_text(
        json.dumps(
            {
                "model": "gpt-5.5",
                "provider": "codex",
                "system_prompt": "fallback prompt",
            }
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt_variants" / "active.txt").write_text(
        "I am codex_composer.",
        encoding="utf-8",
    )
    return root


def test_issue_model_probe_lease_matches_l4_smoke_gate(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path / "agents")
    payload = issue_model_probe_lease(
        name="codex_composer",
        session_id="l4-model-session",
        lease_id="lease:test:l4-model",
        agents_root=agents_root,
        duration_seconds=600,
        allow_subprocess_provider=True,
        purpose="unit test L4 model probe lease",
        now=datetime(2026, 6, 18, 11, 20, tzinfo=UTC),
    )

    assert payload["schema_version"] == MODEL_PROBE_LEASE_SCHEMA_VERSION
    assert payload["lease_id"] == "lease:test:l4-model"
    assert payload["holon"] == "codex_composer"
    assert payload["provider_type"] == "codex"
    assert payload["model"] == "gpt-5.5"
    assert payload["session_id"] == "l4-model-session"
    assert payload["allow_live_model_probe"] is True
    assert payload["allow_subprocess_provider"] is True
    assert payload["digest"] == model_probe_lease_digest(payload)

    path = write_model_probe_lease(payload, tmp_path / "leases" / "lease.json")
    assert json.loads(path.read_text(encoding="utf-8"))["digest"] == payload["digest"]


def test_default_model_probe_lease_path_sanitizes_lease_id(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"
    assert safe_lease_filename("lease:l4 model/../x") == "lease_l4_model___x"
    path = default_model_probe_lease_path(
        "codex_composer",
        lease_id="lease:l4 model/../x",
        agents_root=agents_root,
    )
    assert path == agents_root / "codex_composer" / "leases" / "lease_l4_model___x.json"
