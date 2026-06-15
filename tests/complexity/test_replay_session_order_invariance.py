from __future__ import annotations
import random
import pytest
from dharma_swarm.canonical_replay import CanonicalReplayEngine
from dharma_swarm.event_log import EventLog, RuntimeEnvelope
from dharma_swarm.runtime_contract import RuntimeEventType
ET = RuntimeEventType

def _envelopes(session_id):
    mk = lambda et, ts, src, payload: RuntimeEnvelope.create(
        event_type=et, source=src, agent_id=src, session_id=session_id,
        emitted_at=ts, payload=payload)
    return [
        mk(ET.STATE_SNAPSHOT, "2026-01-01T00:00:00Z", "daemon", {"cycle_count":1,"uptime_seconds":10,"runtime_mode":"boot","status":"starting"}),
        mk(ET.MEMORY_EVENT,   "2026-01-01T00:00:01Z", "mem",    {"memory_id":"m1","memory_type":"episodic","importance":3,"summary":"first"}),
        mk(ET.ACTION_EVENT,   "2026-01-01T00:00:02Z", "act",    {"action_name":"evolve","decision":"apply","confidence":0.9}),
        mk(ET.AUDIT_EVENT,    "2026-01-01T00:00:03Z", "gate",   {"gate":"telos","result":"pass","reason":"aligned"}),
        mk(ET.MEMORY_EVENT,   "2026-01-01T00:00:04Z", "mem",    {"memory_id":"m2","memory_type":"semantic","importance":5,"summary":"second"}),
        mk(ET.ACTION_EVENT,   "2026-01-01T00:00:05Z", "act",    {"action_name":"merge","decision":"defer","confidence":0.4}),
        mk(ET.AUDIT_EVENT,    "2026-01-01T00:00:06Z", "gate",   {"gate":"ahimsa","result":"fail","reason":"risk"}),
        mk(ET.STATE_SNAPSHOT, "2026-01-01T00:00:07Z", "daemon", {"cycle_count":2,"uptime_seconds":20,"runtime_mode":"active","status":"ok"}),
    ]

async def _replay_hash(tmp_path, session_id, disk_order):
    log_dir = tmp_path / f"events_{random.randint(0, 1<<30)}"
    log_dir.mkdir()
    log = EventLog(log_dir)
    for env in disk_order:
        log.append_envelope(env, stream="runtime")
    engine = CanonicalReplayEngine(log_dir)
    result = await engine.replay_session(session_id, verify_determinism=False)
    return result.final_state_hash, result

@pytest.mark.asyncio
@pytest.mark.parametrize("seed", list(range(20)))
async def test_replay_session_invariant_under_disk_reordering(tmp_path, seed):
    sid = "proto-session"
    envs = _envelopes(sid)
    canonical_hash, base_result = await _replay_hash(tmp_path, sid, envs)
    assert canonical_hash, "empty hash means no events loaded"
    shuffled = envs[:]
    random.Random(seed).shuffle(shuffled)
    reordered_hash, _ = await _replay_hash(tmp_path, sid, shuffled)
    assert canonical_hash == reordered_hash, (
        f"replay_session hash changed under disk reorder (seed={seed}): "
        f"{canonical_hash[:16]} vs {reordered_hash[:16]}")
