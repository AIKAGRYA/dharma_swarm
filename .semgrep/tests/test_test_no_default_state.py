from dharma_swarm.runtime_state import RuntimeStateStore


def violation_default_state(tmp_path):
    # ruleid: dharma.test-no-default-state
    store = RuntimeStateStore()
    return store


def ok_explicit_path(tmp_path):
    # ok: dharma.test-no-default-state
    store = RuntimeStateStore(db_path=tmp_path / "test.db")
    return store


def ok_keyword_path(tmp_path):
    # ok: dharma.test-no-default-state
    store = RuntimeStateStore(db_path=str(tmp_path / "test.db"))
    return store
