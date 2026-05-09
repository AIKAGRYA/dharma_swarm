from __future__ import annotations

import stat

from scripts import tcs_history_writer


def test_tcs_history_lock_is_owner_only(tmp_path, monkeypatch):
    lock_path = tmp_path / "identity_history.lock"
    monkeypatch.setattr(tcs_history_writer, "LOCK_PATH", lock_path)

    assert tcs_history_writer._try_lock() is True
    try:
        mode = stat.S_IMODE(lock_path.stat().st_mode)
        assert mode == 0o600
    finally:
        tcs_history_writer._release_lock()
