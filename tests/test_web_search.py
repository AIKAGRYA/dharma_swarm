from __future__ import annotations

from dharma_swarm.web_search import JinaSearchBackend


def test_jina_auth_disable_is_process_wide(monkeypatch) -> None:
    monkeypatch.setattr(JinaSearchBackend, "_process_auth_disabled", False)

    first = JinaSearchBackend()
    second = JinaSearchBackend()

    assert first.available is True
    assert second.available is True
    assert first._disable_after_auth_failure(401, action="search") is True
    assert first.available is False
    assert second.available is False
    assert JinaSearchBackend().available is False
