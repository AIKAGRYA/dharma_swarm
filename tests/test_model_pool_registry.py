from __future__ import annotations

import json


def test_model_pool_registry_merges_ollama_a2a_and_key_clusters(tmp_path) -> None:
    from dharma_swarm.model_pool_registry import build_model_pool_snapshot

    dharma_home = tmp_path / ".dharma"
    ollama_home = tmp_path / ".ollama"
    (dharma_home / "a2a" / "cards").mkdir(parents=True)
    (ollama_home / "cache").mkdir(parents=True)

    (dharma_home / "keys_status.json").write_text(
        json.dumps(
            {
                "rows": {
                    "ollama_cloud": {"key_present": True, "http": 200, "status": "live"},
                    "nvidia_nim": {"key_present": True, "http": 200, "status": "live"},
                    "zai_coding": {"key_present": True, "http": 200, "status": "live"},
                }
            }
        ),
        encoding="utf-8",
    )
    (dharma_home / "a2a" / "cards" / "opus.json").write_text(
        json.dumps({"name": "opus", "model": "claude-opus-4-8"}),
        encoding="utf-8",
    )
    (ollama_home / "cache" / "model-recommendations.json").write_text(
        json.dumps(
            {
                "recommendations": [
                    {
                        "model": "glm-5.2:cloud",
                        "context_length": 1_000_000,
                        "max_output_tokens": 131_072,
                        "required_plan": "pro",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    snapshot = build_model_pool_snapshot(
        dharma_home=dharma_home,
        ollama_home=ollama_home,
        include_ollama_list=False,
        refresh_nim=False,
        env={},
    )
    entries = {(entry.provider, entry.model): entry for entry in snapshot.entries}

    assert ("ollama", "glm-5.2:cloud") in entries
    assert entries[("ollama", "glm-5.2:cloud")].context_length == 1_000_000
    assert ("claude_code", "claude-opus-4-8") in entries
    assert ("zai_coding", "z-ai/glm-5") in entries
    assert entries[("zai_coding", "z-ai/glm-5")].availability == "live_verified"


def test_model_pool_registry_can_emit_json_without_live_refresh() -> None:
    from dharma_swarm.model_pool_registry import model_pool_summary

    data = json.loads(
        model_pool_summary(
            as_json=True,
            limit=5,
            refresh_nim=False,
            include_ollama_list=False,
        )
    )

    assert data["total_models"] >= 5
    assert data["entries"]
    assert len(data["entries"]) == 5
    assert {"provider", "model", "power_score", "availability"} <= set(data["entries"][0])


def test_dgc_model_pool_parser_registered() -> None:
    from dharma_swarm.dgc_cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args(["model-pool", "--json", "--limit", "7", "--refresh-nim"])

    assert args.command == "model-pool"
    assert args.json is True
    assert args.limit == 7
    assert args.refresh_nim is True


def test_cmd_model_pool_json_output(capsys, monkeypatch) -> None:
    from dharma_swarm.dgc_cli import cmd_model_pool

    monkeypatch.setattr(
        "dharma_swarm.model_pool_registry.model_pool_summary",
        lambda **kwargs: json.dumps({"entries": [{"model": "glm-5.2:cloud"}], "kwargs": kwargs}),
    )

    cmd_model_pool(as_json=True, limit=3, refresh_nim=False, include_ollama_list=False)
    data = json.loads(capsys.readouterr().out)

    assert data["entries"][0]["model"] == "glm-5.2:cloud"
    assert data["kwargs"]["limit"] == 3
