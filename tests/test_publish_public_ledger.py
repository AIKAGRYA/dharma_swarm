"""Lane 3: public miss/hit ledger publisher — append-only GitHub issue log."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "daemon" / "publish_public_ledger.py"

NOW = datetime(2026, 8, 19, 15, 0, 0, tzinfo=timezone.utc)


def load_mod():
    spec = importlib.util.spec_from_file_location("publish_public_ledger", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def heartbeat() -> dict[str, Any]:
    return {
        "schema": "dharma.public_ledger.heartbeat.v1",
        "observed_at": "2026-08-19T14:59:00Z",
        "daemon_id": "outward-engine",
        "status": "alive",
    }


def digest() -> dict[str, Any]:
    return {
        "schema": "dharma.public_ledger.miss_hit.v1",
        "observed_at": "2026-08-19T14:59:00Z",
        "hits": 2,
        "misses": 1,
        "entries": [
            {
                "kind": "hit",
                "invariant_id": "INV-RECEIPT-DIGEST",
                "digest": "sha256:" + "a" * 64,
            },
            {
                "kind": "hit",
                "invariant_id": "INV-TIME-MONOTONE",
                "digest": "sha256:" + "b" * 64,
            },
            {
                "kind": "miss",
                "invariant_id": "INV-HALLUCINATED-COMPLETION",
                "digest": "sha256:" + "c" * 64,
                "transition_id": "t-ghost",
            },
        ],
    }


def test_compose_is_append_only_timestamped_and_chained() -> None:
    mod = load_mod()
    body, entry_digest = mod.compose_entry(
        heartbeat=heartbeat(),
        digest=digest(),
        prev_digest="sha256:" + "e" * 64,
        now=NOW,
    )
    assert "<!-- dharma-public-ledger:v1 -->" in body
    assert "2026-08-19T15:00:00Z" in body
    assert "misses: 1" in body.lower() or "**1**" in body
    assert "INV-HALLUCINATED-COMPLETION" in body
    assert "sha256:" + "e" * 64 in body
    assert entry_digest.startswith("sha256:")
    assert f"digest:{entry_digest}" in body.replace(" ", "")


def test_dry_run_does_not_call_github(tmp_path: Path) -> None:
    mod = load_mod()
    calls: list[dict[str, Any]] = []

    def poster(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        raise AssertionError("dry-run must not post")

    result = mod.publish(
        heartbeat=heartbeat(),
        digest=digest(),
        issue_url="https://github.com/AIKAGRYA/dharma_swarm/issues/42",
        token="secret-token",
        now=NOW,
        last_human_input="2026-08-18T00:00:00Z",
        dry_run=True,
        poster=poster,
        chain_path=tmp_path / "chain.json",
        output_path=tmp_path / "entry.md",
    )
    assert calls == []
    assert result["posted"] is False
    assert result["dry_run"] is True
    assert (tmp_path / "entry.md").is_file()
    assert "INV-HALLUCINATED-COMPLETION" in (tmp_path / "entry.md").read_text(
        encoding="utf-8"
    )


def test_post_appends_comment_and_never_patches() -> None:
    mod = load_mod()
    calls: list[dict[str, Any]] = []

    def poster(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"id": 99, "html_url": "https://github.com/example/comment/99"}

    result = mod.publish(
        heartbeat=heartbeat(),
        digest=digest(),
        issue_url="https://github.com/AIKAGRYA/dharma_swarm/issues/42",
        token="secret-token",
        now=NOW,
        last_human_input="2026-08-18T12:00:00Z",
        dry_run=False,
        poster=poster,
        chain_path=None,
    )
    assert result["posted"] is True
    assert len(calls) == 1
    assert calls[0]["method"] == "POST"
    assert calls[0]["repo"] == "AIKAGRYA/dharma_swarm"
    assert calls[0]["issue_number"] == 42
    assert "secret-token" not in json.dumps(result)
    assert "PATCH" not in str(calls)


def test_thirty_day_silence_fail_closed_does_not_post() -> None:
    mod = load_mod()
    calls: list[dict[str, Any]] = []

    def poster(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {}

    result = mod.publish(
        heartbeat=heartbeat(),
        digest=digest(),
        issue_url="https://github.com/AIKAGRYA/dharma_swarm/issues/42",
        token="secret-token",
        now=NOW,
        last_human_input="2026-07-01T00:00:00Z",
        dry_run=False,
        poster=poster,
    )
    assert result["posted"] is False
    assert result["halted"] is True
    assert result["reason"] == "human_silence"
    assert calls == []


def test_missing_human_input_fail_closed() -> None:
    mod = load_mod()
    result = mod.publish(
        heartbeat=heartbeat(),
        digest=digest(),
        issue_url="https://github.com/AIKAGRYA/dharma_swarm/issues/42",
        token="secret-token",
        now=NOW,
        last_human_input=None,
        dry_run=False,
        poster=lambda **_k: (_ for _ in ()).throw(AssertionError("no post")),
    )
    assert result["halted"] is True
    assert result["reason"] == "human_silence"


def test_missing_token_fail_closed_when_not_dry_run() -> None:
    mod = load_mod()
    with pytest.raises(mod.LedgerPublishError):
        mod.publish(
            heartbeat=heartbeat(),
            digest=digest(),
            issue_url="https://github.com/AIKAGRYA/dharma_swarm/issues/42",
            token="",
            now=NOW,
            last_human_input="2026-08-18T00:00:00Z",
            dry_run=False,
            poster=lambda **_k: {"id": 1},
        )


def test_invalid_digest_fail_closed() -> None:
    mod = load_mod()
    bad = digest()
    bad["misses"] = 0  # lies: entries still contain a miss
    with pytest.raises(mod.LedgerPublishError):
        mod.publish(
            heartbeat=heartbeat(),
            digest=bad,
            issue_url="https://github.com/AIKAGRYA/dharma_swarm/issues/42",
            token="secret-token",
            now=NOW,
            last_human_input="2026-08-18T00:00:00Z",
            dry_run=True,
            poster=lambda **_k: {"id": 1},
        )


def test_chain_file_rewritten_not_appended(tmp_path: Path) -> None:
    mod = load_mod()
    chain = tmp_path / "chain.json"
    first = mod.publish(
        heartbeat=heartbeat(),
        digest=digest(),
        issue_url="https://github.com/AIKAGRYA/dharma_swarm/issues/42",
        token="secret-token",
        now=NOW,
        last_human_input="2026-08-18T00:00:00Z",
        dry_run=True,
        poster=lambda **_k: {"id": 1},
        chain_path=chain,
    )
    payload = json.loads(chain.read_text(encoding="utf-8"))
    assert payload["schema"] == "dharma.public_ledger.chain.v1"
    assert payload["head"] == first["entry_digest"]
    text = chain.read_text(encoding="utf-8")
    assert text.count("{") >= 1
    # second publish should rewrite, not grow a JSONL
    mod.publish(
        heartbeat=heartbeat(),
        digest=digest(),
        issue_url="https://github.com/AIKAGRYA/dharma_swarm/issues/42",
        token="secret-token",
        now=NOW,
        last_human_input="2026-08-18T00:00:00Z",
        dry_run=True,
        poster=lambda **_k: {"id": 1},
        chain_path=chain,
    )
    assert chain.read_text(encoding="utf-8").count("\n{") == 0


def test_compose_includes_sha_of_inputs() -> None:
    mod = load_mod()
    hb = heartbeat()
    dg = digest()
    body, _digest = mod.compose_entry(
        heartbeat=hb, digest=dg, prev_digest=None, now=NOW
    )
    hb_sha = hashlib.sha256(
        json.dumps(hb, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    dg_sha = hashlib.sha256(
        json.dumps(dg, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert hb_sha in body
    assert dg_sha in body
