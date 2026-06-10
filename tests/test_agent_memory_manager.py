"""Tests for dharma_swarm.agent_memory_manager -- SQLite-backed self-managing memory."""

import importlib
import sys
import time
from pathlib import Path

import pytest

# Avoid triggering dharma_swarm.__init__ (which has a pre-existing circular
# import in the provider chain). Import the module directly via its file path.
_MOD_PATH = Path(__file__).resolve().parent.parent / "dharma_swarm" / "agent_memory_manager.py"
_spec = importlib.util.spec_from_file_location("dharma_swarm.agent_memory_manager", _MOD_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("dharma_swarm.agent_memory_manager", _mod)
_spec.loader.exec_module(_mod)

AgentMemoryManager = _mod.AgentMemoryManager
Memory = _mod.Memory
Scope = _mod.Scope
MemoryLane = _mod.MemoryLane
COGNITIVE_LANES = _mod.COGNITIVE_LANES


@pytest.fixture
def db_path(tmp_path):
    """Return a temp SQLite DB path."""
    return tmp_path / "test_memories.db"


@pytest.fixture
def mgr(db_path):
    """Create a fresh AgentMemoryManager."""
    m = AgentMemoryManager("test_agent", db_path=db_path)
    yield m
    m.close()


@pytest.fixture
def mgr_b(db_path):
    """A second agent sharing the same database."""
    m = AgentMemoryManager("agent_b", db_path=db_path)
    yield m
    m.close()


# ---------------------------------------------------------------------------
# 1. Remember / Recall / Forget cycle
# ---------------------------------------------------------------------------


async def test_remember_and_recall_by_key(mgr):
    """remember() stores, recall_by_key() retrieves."""
    mem = await mgr.remember("goal", "finish R_V paper", scope=Scope.WORKING)
    assert mem.key == "goal"
    assert mem.content == "finish R_V paper"
    assert mem.scope == Scope.WORKING

    recalled = await mgr.recall_by_key("goal")
    assert recalled is not None
    assert recalled.content == "finish R_V paper"
    assert recalled.access_count >= 1


async def test_remember_upserts(mgr):
    """Second remember() with same key+scope updates content."""
    await mgr.remember("fact", "water is wet", scope=Scope.WORKING)
    await mgr.remember("fact", "water is very wet", scope=Scope.WORKING)

    recalled = await mgr.recall_by_key("fact", scope=Scope.WORKING)
    assert recalled is not None
    assert recalled.content == "water is very wet"


async def test_forget_removes(mgr):
    """forget() deletes from the correct scope."""
    await mgr.remember("temp", "temporary value", scope=Scope.SHORT_TERM)
    assert await mgr.forget("temp", scope=Scope.SHORT_TERM) is True
    assert await mgr.recall_by_key("temp", scope=Scope.SHORT_TERM) is None


async def test_forget_missing_returns_false(mgr):
    """forget() returns False for nonexistent key."""
    assert await mgr.forget("nonexistent") is False


async def test_forget_all_scopes(mgr):
    """forget() without scope deletes from all scopes."""
    await mgr.remember("multi", "in working", scope=Scope.WORKING)
    await mgr.remember("multi", "in long_term", scope=Scope.LONG_TERM)

    assert await mgr.forget("multi") is True
    assert await mgr.recall_by_key("multi", scope=Scope.WORKING) is None
    assert await mgr.recall_by_key("multi", scope=Scope.LONG_TERM) is None


# ---------------------------------------------------------------------------
# 2. Scope isolation
# ---------------------------------------------------------------------------


async def test_scope_isolation(mgr):
    """Memories in different scopes with same key are independent."""
    await mgr.remember("data", "working version", scope=Scope.WORKING)
    await mgr.remember("data", "long term version", scope=Scope.LONG_TERM)

    w = await mgr.recall_by_key("data", scope=Scope.WORKING)
    lt = await mgr.recall_by_key("data", scope=Scope.LONG_TERM)

    assert w is not None
    assert lt is not None
    assert w.content == "working version"
    assert lt.content == "long term version"


async def test_recall_keyword_scope_filter(mgr):
    """recall() with scope= filters to that scope only."""
    await mgr.remember("rv_working", "R_V in working", scope=Scope.WORKING)
    await mgr.remember("rv_longterm", "R_V in long_term", scope=Scope.LONG_TERM)

    working_only = await mgr.recall("R_V", scope=Scope.WORKING, limit=10)
    assert all(m.scope == Scope.WORKING for m in working_only)
    assert len(working_only) == 1


# ---------------------------------------------------------------------------
# 3. Shared memory visibility
# ---------------------------------------------------------------------------


async def test_shared_memory_cross_agent(mgr, mgr_b):
    """Shared memories are visible to all agents."""
    await mgr.share("solved:auth_bug", "Use refresh tokens", tags="auth,security")

    # Agent B can find it
    results = await mgr_b.recall("auth_bug", scope=Scope.SHARED, limit=5)
    assert len(results) >= 1
    assert results[0].content == "Use refresh tokens"
    assert "auth" in results[0].tags


async def test_share_overwrites_by_key(mgr, mgr_b):
    """Shared memory upserts on key collision."""
    await mgr.share("strategy", "old strategy")
    await mgr_b.share("strategy", "new strategy from B")

    # Both agents see the latest version
    result_a = await mgr.recall_by_key("strategy")
    assert result_a is not None
    assert result_a.content == "new strategy from B"
    assert result_a.agent_id == "agent_b"  # Last writer wins


async def test_shared_via_remember(mgr):
    """remember() with scope=SHARED delegates to share()."""
    mem = await mgr.remember(
        "shared_insight", "patterns converge", scope=Scope.SHARED, tags="meta"
    )
    assert mem.scope == Scope.SHARED
    assert mem.tags == "meta"

    recalled = await mgr.recall_by_key("shared_insight")
    assert recalled is not None
    assert recalled.content == "patterns converge"


# ---------------------------------------------------------------------------
# 4. Consolidation
# ---------------------------------------------------------------------------


async def test_consolidate_expires_ttl(mgr):
    """consolidate() removes expired TTL memories."""
    # Insert with TTL of 1 second
    await mgr.remember("ephemeral", "gone soon", scope=Scope.SHORT_TERM, ttl=1)

    # Wait for expiry
    time.sleep(1.1)

    affected = await mgr.consolidate()
    assert affected >= 1

    recalled = await mgr.recall_by_key("ephemeral", scope=Scope.SHORT_TERM)
    assert recalled is None


async def test_consolidate_enforces_limits(mgr):
    """consolidate() evicts excess memories beyond scope limits."""
    # Insert 10 items at default limit (50)
    for i in range(10):
        await mgr.remember(f"item_{i}", f"value_{i}", scope=Scope.WORKING)

    stats_before = await mgr.get_stats()
    assert stats_before["working_count"] == 10

    # NOW lower the limit and run consolidation
    original = mgr.MAX_WORKING
    mgr.MAX_WORKING = 5

    affected = await mgr.consolidate()
    assert affected >= 5  # At least 5 should be evicted

    stats = await mgr.get_stats()
    assert stats["working_count"] <= 5

    mgr.MAX_WORKING = original


async def test_consolidate_promotes_frequent(mgr):
    """consolidate() promotes frequently-accessed short-term to long-term."""
    # Insert a short-term memory
    await mgr.remember("freq_item", "accessed a lot", scope=Scope.SHORT_TERM)

    # Simulate multiple accesses and age > 1 hour
    with mgr._lock:
        conn = mgr._get_conn()
        conn.execute(
            """UPDATE memories SET access_count=5, created_at=?
               WHERE agent_id=? AND key='freq_item'""",
            (time.time() - 7200, mgr.agent_id),  # 2 hours ago
        )
        conn.commit()

    affected = await mgr.consolidate()
    assert affected >= 1

    # Should now be in long_term
    lt = await mgr.recall_by_key("freq_item", scope=Scope.LONG_TERM)
    assert lt is not None
    assert lt.content == "accessed a lot"


# ---------------------------------------------------------------------------
# 5. Context building with token budget
# ---------------------------------------------------------------------------


async def test_get_context_basic(mgr):
    """get_context() returns formatted markdown with memories."""
    await mgr.remember("goal", "ship R_V paper", scope=Scope.WORKING)
    await mgr.remember("finding", "L27 is causal", scope=Scope.SHORT_TERM)
    await mgr.remember("principle", "telos governs action", scope=Scope.LONG_TERM)

    ctx = await mgr.get_context(budget_tokens=2000)
    assert "## Memory Context (test_agent)" in ctx
    assert "goal" in ctx
    assert "ship R_V paper" in ctx


async def test_get_context_respects_budget(mgr):
    """get_context() stops adding memories when budget is exhausted."""
    # Add many large memories
    for i in range(50):
        await mgr.remember(
            f"big_item_{i}",
            "A very long content string that takes up space " * 10,
            scope=Scope.WORKING,
        )

    # Tiny budget
    ctx = await mgr.get_context(budget_tokens=100)
    # 100 tokens ~= 400 chars, should be much shorter than all 50 items
    assert len(ctx) < 1000


async def test_get_context_includes_shared(mgr):
    """get_context() includes shared memories."""
    await mgr.share("swarm_strategy", "divide and conquer")

    ctx = await mgr.get_context(budget_tokens=2000)
    assert "Shared" in ctx
    assert "swarm_strategy" in ctx


# ---------------------------------------------------------------------------
# 6. TTL expiry
# ---------------------------------------------------------------------------


async def test_ttl_memory_is_expired(mgr):
    """Memory with TTL is marked expired after TTL passes."""
    await mgr.remember("quick", "fast thought", scope=Scope.SHORT_TERM, ttl=1)

    # Immediately should not be expired
    mem = await mgr.recall_by_key("quick", scope=Scope.SHORT_TERM)
    assert mem is not None
    assert not mem.is_expired

    # After TTL
    time.sleep(1.1)
    mem2 = await mgr.recall_by_key("quick", scope=Scope.SHORT_TERM)
    # The record still exists in DB (consolidate hasn't run)
    # but is_expired should be True
    if mem2 is not None:
        assert mem2.is_expired


async def test_ttl_none_never_expires(mgr):
    """Memory without TTL never expires."""
    await mgr.remember("permanent", "always here", scope=Scope.LONG_TERM)
    mem = await mgr.recall_by_key("permanent")
    assert mem is not None
    assert not mem.is_expired


# ---------------------------------------------------------------------------
# 7. Keyword search
# ---------------------------------------------------------------------------


async def test_recall_keyword_match(mgr):
    """recall() finds memories by keyword in key and content."""
    await mgr.remember("rv_finding", "R_V contraction at Layer 27", scope=Scope.WORKING)
    await mgr.remember("weather", "sunny today", scope=Scope.WORKING)
    await mgr.remember("rv_method", "participation ratio method", scope=Scope.LONG_TERM)

    results = await mgr.recall("R_V contraction", limit=10)
    keys = {m.key for m in results}
    assert "rv_finding" in keys
    # "weather" should not match
    assert "weather" not in keys


async def test_recall_empty_query(mgr):
    """recall() with empty query returns nothing."""
    await mgr.remember("item", "some content", scope=Scope.WORKING)
    results = await mgr.recall("", limit=5)
    assert results == []


async def test_recall_shared_by_tags(mgr):
    """recall() on shared scope matches tags."""
    await mgr.share("pattern:caching", "Use LRU cache for hot paths", tags="performance,optimization")

    results = await mgr.recall("performance", scope=Scope.SHARED, limit=5)
    assert len(results) >= 1
    assert "caching" in results[0].key


# ---------------------------------------------------------------------------
# 8. Stats
# ---------------------------------------------------------------------------


async def test_stats(mgr):
    """get_stats() returns correct counts."""
    await mgr.remember("w1", "working 1", scope=Scope.WORKING)
    await mgr.remember("w2", "working 2", scope=Scope.WORKING)
    await mgr.remember("s1", "short 1", scope=Scope.SHORT_TERM)
    await mgr.remember("l1", "long 1", scope=Scope.LONG_TERM)
    await mgr.share("shared1", "shared content")

    stats = await mgr.get_stats()
    assert stats["agent_id"] == "test_agent"
    assert stats["working_count"] == 2
    assert stats["short_term_count"] == 1
    assert stats["long_term_count"] == 1
    assert stats["shared_count"] == 1
    assert stats["total_count"] == 5


# ---------------------------------------------------------------------------
# 9. List keys
# ---------------------------------------------------------------------------


async def test_list_keys(mgr):
    """list_keys() returns all keys, optionally filtered by scope."""
    await mgr.remember("alpha", "a", scope=Scope.WORKING)
    await mgr.remember("beta", "b", scope=Scope.LONG_TERM)
    await mgr.share("gamma", "c")

    all_keys = await mgr.list_keys()
    assert "alpha" in all_keys
    assert "beta" in all_keys
    # Shared keys are in a separate table, not returned by default
    # unless scope=SHARED
    shared_keys = await mgr.list_keys(scope=Scope.SHARED)
    assert "gamma" in shared_keys

    working_keys = await mgr.list_keys(scope=Scope.WORKING)
    assert "alpha" in working_keys
    assert "beta" not in working_keys


# ---------------------------------------------------------------------------
# 10. Agent isolation in same DB
# ---------------------------------------------------------------------------


async def test_agent_isolation(mgr, mgr_b):
    """Two agents sharing a DB have isolated private memories."""
    await mgr.remember("secret", "agent A secret", scope=Scope.WORKING)
    await mgr_b.remember("secret", "agent B secret", scope=Scope.WORKING)

    a_mem = await mgr.recall_by_key("secret", scope=Scope.WORKING)
    b_mem = await mgr_b.recall_by_key("secret", scope=Scope.WORKING)

    assert a_mem is not None
    assert b_mem is not None
    assert a_mem.content == "agent A secret"
    assert b_mem.content == "agent B secret"
    assert a_mem.agent_id == "test_agent"
    assert b_mem.agent_id == "agent_b"


# ---------------------------------------------------------------------------
# 11. Memory dataclass
# ---------------------------------------------------------------------------


def test_memory_to_dict():
    """Memory.to_dict() produces a serializable dict."""
    mem = Memory(
        id=1,
        agent_id="test",
        key="k",
        content="c",
        scope=Scope.WORKING,
        created_at=1000.0,
        accessed_at=1000.0,
    )
    d = mem.to_dict()
    assert d["scope"] == "working"
    assert d["key"] == "k"
    assert isinstance(d, dict)


def test_memory_is_expired():
    """Memory.is_expired checks TTL correctly."""
    # No TTL = never expires
    mem = Memory(created_at=time.time() - 9999)
    assert not mem.is_expired

    # TTL expired
    mem_expired = Memory(created_at=time.time() - 100, ttl=50)
    assert mem_expired.is_expired

    # TTL not expired
    mem_fresh = Memory(created_at=time.time(), ttl=9999)
    assert not mem_fresh.is_expired


# ---------------------------------------------------------------------------
# D2: Identity-namespace binding (cross-session persistent memory)
# ---------------------------------------------------------------------------


def test_resolve_agent_id_strips_prefix():
    """agent:<uid> resolves to the bare uid."""
    assert AgentMemoryManager.resolve_agent_id("agent:opus_composer") == "opus_composer"


def test_resolve_agent_id_bare_passthrough():
    """A bare uid resolves to itself (backward-compatible)."""
    assert AgentMemoryManager.resolve_agent_id("opus_composer") == "opus_composer"
    assert AgentMemoryManager.resolve_agent_id("operator") == "operator"


def test_resolve_agent_id_folds_subscope():
    """A sub-namespace folds onto the owning uid -> ONE store."""
    assert AgentMemoryManager.resolve_agent_id("agent:opus_composer:planning") == "opus_composer"


def test_resolve_agent_id_idempotent():
    """resolve(resolve(x)) == resolve(x)."""
    once = AgentMemoryManager.resolve_agent_id("agent:opus_composer")
    assert AgentMemoryManager.resolve_agent_id(once) == once


def test_resolve_agent_id_rejects_empty():
    """Empty / whitespace / prefix-only namespaces are rejected."""
    for bad in ("", "   ", "agent:"):
        try:
            AgentMemoryManager.resolve_agent_id(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


def test_for_namespace_binds_one_store(db_path):
    """All identity forms of one agent resolve to the SAME store key."""
    a = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    b = AgentMemoryManager.for_namespace("opus_composer", db_path=db_path)
    c = AgentMemoryManager.for_namespace("agent:opus_composer:sub", db_path=db_path)
    try:
        assert a.agent_id == b.agent_id == c.agent_id == "opus_composer"
    finally:
        a.close()
        b.close()
        c.close()


async def test_cross_session_recall_through_namespace(db_path):
    """Learnings written via the namespace in one 'session' are recalled in a
    later 'session' (a fresh manager instance bound by the same namespace)."""
    # Session 1: write a learning via the prefixed namespace form.
    sess1 = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    await sess1.remember(
        "lesson:d2", "bind memory_namespace to one store", scope=Scope.LONG_TERM,
    )
    sess1.close()

    # Session 2: a brand-new instance (and a different identity form) recalls it.
    sess2 = AgentMemoryManager.for_namespace("opus_composer", db_path=db_path)
    try:
        by_key = await sess2.recall_by_key("lesson:d2", scope=Scope.LONG_TERM)
        assert by_key is not None
        assert by_key.content == "bind memory_namespace to one store"

        hits = await sess2.recall("memory_namespace store", scope=Scope.LONG_TERM)
        assert any(m.key == "lesson:d2" for m in hits)
    finally:
        sess2.close()


# ---------------------------------------------------------------------------
# D4: Episodic / semantic / procedural separation
# ---------------------------------------------------------------------------


async def test_default_lane_is_episodic(mgr):
    """A memory stored without a lane defaults to EPISODIC (and the old API
    signature still works -- backward compatible)."""
    mem = await mgr.remember("evt", "the build went green", scope=Scope.WORKING)
    assert mem.lane == MemoryLane.EPISODIC


async def test_remember_types_each_lane(mgr):
    """remember(lane=...) stores the requested cognitive type."""
    ep = await mgr.remember("e", "ran the suite at 3pm", scope=Scope.SHORT_TERM, lane=MemoryLane.EPISODIC)
    se = await mgr.remember("s", "L27 is the causal site", scope=Scope.LONG_TERM, lane=MemoryLane.SEMANTIC)
    pr = await mgr.remember("p", "to ship: branch, test, PR", scope=Scope.LONG_TERM, lane=MemoryLane.PROCEDURAL)
    assert ep.lane == MemoryLane.EPISODIC
    assert se.lane == MemoryLane.SEMANTIC
    assert pr.lane == MemoryLane.PROCEDURAL


async def test_lane_accepts_string(mgr):
    """A lane may be passed as a string and is coerced to the enum."""
    mem = await mgr.remember("k", "v", scope=Scope.LONG_TERM, lane="semantic")
    assert mem.lane == MemoryLane.SEMANTIC


async def test_unknown_lane_falls_back_to_default(mgr):
    """An out-of-set lane never raises; it falls back to EPISODIC."""
    mem = await mgr.remember("k", "v", scope=Scope.WORKING, lane="reflection")
    assert mem.lane == MemoryLane.EPISODIC  # reflection is not a cognitive lane here


async def test_recall_filters_by_lane(mgr):
    """recall(lane=...) returns only memories of that cognitive type."""
    await mgr.remember("fact_rv", "R_V contracts at L27", scope=Scope.LONG_TERM, lane=MemoryLane.SEMANTIC)
    await mgr.remember("did_rv", "I measured R_V today", scope=Scope.SHORT_TERM, lane=MemoryLane.EPISODIC)
    await mgr.remember("how_rv", "R_V how-to: load model, patch L27", scope=Scope.LONG_TERM, lane=MemoryLane.PROCEDURAL)

    sem = await mgr.recall("R_V", lane=MemoryLane.SEMANTIC, limit=10)
    assert {m.key for m in sem} == {"fact_rv"}
    assert all(m.lane == MemoryLane.SEMANTIC for m in sem)

    proc = await mgr.recall_by_lane("R_V", MemoryLane.PROCEDURAL, limit=10)
    assert {m.key for m in proc} == {"how_rv"}

    epi = await mgr.recall("R_V", lane="episodic", limit=10)
    assert {m.key for m in epi} == {"did_rv"}


async def test_recall_all_lanes_when_unfiltered(mgr):
    """recall() without a lane filter searches every cognitive lane."""
    await mgr.remember("a", "R_V fact", scope=Scope.LONG_TERM, lane=MemoryLane.SEMANTIC)
    await mgr.remember("b", "R_V episode", scope=Scope.SHORT_TERM, lane=MemoryLane.EPISODIC)
    results = await mgr.recall("R_V", limit=10)
    assert {m.key for m in results} == {"a", "b"}


async def test_episodic_retrieval_is_recency_weighted(mgr):
    """Two equally-matching EPISODIC memories: the most recently accessed ranks
    first (episodic = recency-dominant)."""
    await mgr.remember("old_evt", "deploy event alpha", scope=Scope.SHORT_TERM, lane=MemoryLane.EPISODIC)
    await mgr.remember("new_evt", "deploy event alpha", scope=Scope.SHORT_TERM, lane=MemoryLane.EPISODIC)
    # Make old_evt clearly older in accessed_at.
    with mgr._lock:
        conn = mgr._get_conn()
        conn.execute(
            "UPDATE memories SET accessed_at=? WHERE agent_id=? AND key='old_evt'",
            (time.time() - 10_000, mgr.agent_id),
        )
        conn.commit()
    results = await mgr.recall("deploy event", lane=MemoryLane.EPISODIC, limit=2)
    assert results[0].key == "new_evt"


async def test_semantic_retrieval_is_frequency_weighted(mgr):
    """Two equally-matching SEMANTIC facts: the more-reused (higher access_count)
    ranks first even if it was accessed less recently (semantic = reuse-dominant)."""
    await mgr.remember("fact_a", "telos governs action", scope=Scope.LONG_TERM, lane=MemoryLane.SEMANTIC)
    await mgr.remember("fact_b", "telos governs action", scope=Scope.LONG_TERM, lane=MemoryLane.SEMANTIC)
    with mgr._lock:
        conn = mgr._get_conn()
        # fact_a: heavily reused but accessed long ago.
        conn.execute(
            "UPDATE memories SET access_count=50, accessed_at=? WHERE agent_id=? AND key='fact_a'",
            (time.time() - 10_000, mgr.agent_id),
        )
        # fact_b: barely reused but accessed just now.
        conn.execute(
            "UPDATE memories SET access_count=0, accessed_at=? WHERE agent_id=? AND key='fact_b'",
            (time.time(), mgr.agent_id),
        )
        conn.commit()
    results = await mgr.recall("telos governs", lane=MemoryLane.SEMANTIC, limit=2)
    assert results[0].key == "fact_a"  # reuse beats recency for semantic memory


async def test_same_key_different_lanes_coexist_fresh_store(mgr):
    """On a fresh store, the same key can hold distinct rows per lane
    (type-appropriate storage), and each is retrievable by its lane."""
    await mgr.remember("rv", "I ran R_V at noon", scope=Scope.LONG_TERM, lane=MemoryLane.EPISODIC)
    await mgr.remember("rv", "R_V is a participation ratio", scope=Scope.LONG_TERM, lane=MemoryLane.SEMANTIC)

    epi = await mgr.recall_by_lane("R_V", MemoryLane.EPISODIC, scope=Scope.LONG_TERM, limit=5)
    sem = await mgr.recall_by_lane("participation R_V", MemoryLane.SEMANTIC, scope=Scope.LONG_TERM, limit=5)
    assert any(m.content == "I ran R_V at noon" for m in epi)
    assert any(m.content == "R_V is a participation ratio" for m in sem)


async def test_convenience_methods(mgr):
    """record_episode / learn_fact / learn_procedure store the right lanes
    with sensible default scopes."""
    e = await mgr.record_episode("e1", "session started")
    f = await mgr.learn_fact("f1", "constraint enables emergence")
    p = await mgr.learn_procedure("p1", "branch -> test -> PR")
    assert (e.lane, e.scope) == (MemoryLane.EPISODIC, Scope.SHORT_TERM)
    assert (f.lane, f.scope) == (MemoryLane.SEMANTIC, Scope.LONG_TERM)
    assert (p.lane, p.scope) == (MemoryLane.PROCEDURAL, Scope.LONG_TERM)


async def test_lane_counts_in_stats(mgr):
    """get_stats() reports per-lane counts."""
    await mgr.learn_fact("f1", "fact one")
    await mgr.learn_fact("f2", "fact two")
    await mgr.record_episode("e1", "event one")
    await mgr.learn_procedure("p1", "how to one")

    stats = await mgr.get_stats()
    assert "lane_counts" in stats
    assert stats["lane_counts"]["semantic"] == 2
    assert stats["lane_counts"]["episodic"] == 1
    assert stats["lane_counts"]["procedural"] == 1


async def test_memory_to_dict_includes_lane(mgr):
    """Memory.to_dict() serialises the lane."""
    mem = await mgr.learn_fact("f", "a fact")
    d = mem.to_dict()
    assert d["lane"] == "semantic"


async def test_consolidate_preserves_lane(mgr):
    """A frequently-accessed PROCEDURAL short-term memory keeps its lane when
    promoted to long-term by consolidate()."""
    await mgr.remember("proc", "how to ship", scope=Scope.SHORT_TERM, lane=MemoryLane.PROCEDURAL)
    with mgr._lock:
        conn = mgr._get_conn()
        conn.execute(
            "UPDATE memories SET access_count=5, created_at=? WHERE agent_id=? AND key='proc'",
            (time.time() - 7200, mgr.agent_id),
        )
        conn.commit()
    await mgr.consolidate()
    lt = await mgr.recall_by_key("proc", scope=Scope.LONG_TERM)
    assert lt is not None
    assert lt.lane == MemoryLane.PROCEDURAL


async def test_lane_uses_canonical_kernel_enum():
    """D4 reuses the canonical MemoryLane from memory_kernel.atoms (no parallel
    enum). The cognitive set is exactly working/episodic/semantic/procedural."""
    from dharma_swarm.memory_kernel.atoms import MemoryLane as KernelLane
    assert MemoryLane is KernelLane
    assert {l.value for l in COGNITIVE_LANES} == {
        "working", "episodic", "semantic", "procedural",
    }


async def test_cross_session_typed_recall_through_namespace(db_path):
    """A SEMANTIC fact written via the opus namespace in one session is recalled,
    typed, through the same namespace in a later session (D4 bound to identity)."""
    sess1 = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    await sess1.learn_fact("axiom:1", "self-reference creates identity")
    await sess1.learn_procedure("howto:evolve", "modify substrate, not reports")
    sess1.close()

    sess2 = AgentMemoryManager.for_namespace("opus_composer", db_path=db_path)
    try:
        facts = await sess2.recall_by_lane("self reference identity", MemoryLane.SEMANTIC, limit=5)
        assert any(m.key == "axiom:1" for m in facts)
        # Procedural query for the same agent does not surface the semantic fact.
        procs = await sess2.recall_by_lane("modify substrate", MemoryLane.PROCEDURAL, limit=5)
        assert any(m.key == "howto:evolve" for m in procs)
        assert all(m.lane == MemoryLane.PROCEDURAL for m in procs)
    finally:
        sess2.close()


# ---------------------------------------------------------------------------
# D3: Self-editing memory blocks (append / replace_block)
# ---------------------------------------------------------------------------


async def test_append_creates_block_when_absent(mgr):
    """append() to a missing key behaves as a first write."""
    mem = await mgr.append("notes", "first line", scope=Scope.WORKING)
    assert mem.content == "first line"
    got = await mgr.recall_by_key("notes", scope=Scope.WORKING)
    assert got.content == "first line"


async def test_append_grows_existing_block_in_place(mgr):
    """append() concatenates onto the existing block, same key (no new row)."""
    await mgr.remember("notes", "alpha", scope=Scope.WORKING)
    await mgr.append("notes", "beta", scope=Scope.WORKING)
    await mgr.append("notes", "gamma", scope=Scope.WORKING, sep=" | ")
    got = await mgr.recall_by_key("notes", scope=Scope.WORKING)
    assert got.content == "alpha\nbeta | gamma"
    # Still one block, not three.
    keys = await mgr.list_keys(scope=Scope.WORKING)
    assert keys.count("notes") == 1


async def test_append_preserves_lane(mgr):
    """append() keeps the block's existing cognitive lane."""
    await mgr.learn_procedure("howto", "step 1", scope=Scope.LONG_TERM)
    await mgr.append("howto", "step 2", scope=Scope.LONG_TERM)
    got = await mgr.recall_by_key("howto", scope=Scope.LONG_TERM)
    assert got.lane == MemoryLane.PROCEDURAL
    assert got.content == "step 1\nstep 2"


async def test_append_rejects_shared(mgr):
    """append() refuses SHARED scope (cross-agent, not an own block)."""
    with pytest.raises(ValueError):
        await mgr.append("k", "v", scope=Scope.SHARED)


async def test_replace_block_substring(mgr):
    """replace_block() surgically edits a substring in place."""
    await mgr.remember("status", "build is RED on main", scope=Scope.WORKING)
    updated = await mgr.replace_block("status", "RED", "GREEN", scope=Scope.WORKING)
    assert updated.content == "build is GREEN on main"


async def test_replace_block_delete_substring(mgr):
    """replace_block() with new='' deletes the substring."""
    await mgr.remember("note", "draft: ship it", scope=Scope.WORKING)
    updated = await mgr.replace_block("note", "draft: ", "", scope=Scope.WORKING)
    assert updated.content == "ship it"


async def test_replace_block_empty_old_appends(mgr):
    """replace_block() with old='' appends new at the end (Letta semantics)."""
    await mgr.remember("note", "line1", scope=Scope.WORKING)
    updated = await mgr.replace_block("note", "", " line2", scope=Scope.WORKING)
    assert updated.content == "line1 line2"


async def test_replace_block_missing_is_noop(mgr):
    """replace_block() on a missing block returns None (no error)."""
    result = await mgr.replace_block("ghost", "a", "b", scope=Scope.WORKING)
    assert result is None


# ---------------------------------------------------------------------------
# D3: Sleep-time consolidation (decay / revive / merge)
# ---------------------------------------------------------------------------


async def test_sleep_consolidate_merges_near_duplicates(mgr):
    """sleep_consolidate() folds near-duplicate blocks within (scope, lane)."""
    await mgr.remember(
        "obs_a", "the build pipeline is failing on the lint step", scope=Scope.WORKING
    )
    await mgr.remember(
        "obs_b", "the build pipeline is failing on the lint step too", scope=Scope.WORKING
    )
    before = await mgr.get_stats()
    assert before["working_count"] == 2

    result = await mgr.sleep_consolidate(similarity_threshold=0.6)
    assert result["merged"] >= 1

    after = await mgr.get_stats()
    assert after["working_count"] < before["working_count"]


async def test_sleep_consolidate_keeps_distinct_blocks(mgr):
    """Distinct blocks are NOT merged."""
    await mgr.remember("a", "ship the R_V paper to NeurIPS", scope=Scope.WORKING)
    await mgr.remember("b", "buy groceries on the way home", scope=Scope.WORKING)
    result = await mgr.sleep_consolidate(similarity_threshold=0.6)
    assert result["merged"] == 0
    stats = await mgr.get_stats()
    assert stats["working_count"] == 2


async def test_sleep_consolidate_decays_idle_working(mgr):
    """A long-idle, never-reused WORKING block is demoted to SHORT_TERM."""
    await mgr.remember("stale", "old working note", scope=Scope.WORKING)
    # Force it idle: accessed long ago, access_count stays 0.
    with mgr._lock:
        conn = mgr._get_conn()
        conn.execute(
            "UPDATE memories SET accessed_at=?, access_count=0 WHERE agent_id=? AND key='stale'",
            (time.time() - 30 * 86400, mgr.agent_id),
        )
        conn.commit()

    result = await mgr.sleep_consolidate(decay_idle_days=14.0)
    assert result["decayed"] >= 1
    assert await mgr.recall_by_key("stale", scope=Scope.WORKING) is None
    assert await mgr.recall_by_key("stale", scope=Scope.SHORT_TERM) is not None


async def test_sleep_consolidate_revives_rediscovered(mgr):
    """A recently-accessed non-WORKING block is revived back into WORKING."""
    await mgr.remember("rediscovered", "useful pattern", scope=Scope.LONG_TERM)
    # Simulate a recent rediscovery: accessed just now, with a reuse hit.
    with mgr._lock:
        conn = mgr._get_conn()
        conn.execute(
            "UPDATE memories SET accessed_at=?, access_count=2 WHERE agent_id=? AND key='rediscovered'",
            (time.time(), mgr.agent_id),
        )
        conn.commit()

    result = await mgr.sleep_consolidate(revive_window_days=1.0)
    assert result["revived"] >= 1
    assert await mgr.recall_by_key("rediscovered", scope=Scope.WORKING) is not None


async def test_sleep_consolidate_runs_base_consolidate(mgr):
    """sleep_consolidate() still performs base TTL expiry (reuses consolidate)."""
    await mgr.remember("ephemeral", "gone soon", scope=Scope.SHORT_TERM, ttl=1)
    time.sleep(1.1)
    result = await mgr.sleep_consolidate()
    assert result["base_consolidated"] >= 1
    assert await mgr.recall_by_key("ephemeral", scope=Scope.SHORT_TERM) is None


async def test_sleep_consolidate_never_loses_content(mgr):
    """Merge keeps the survivor's content; nothing is silently dropped."""
    await mgr.remember("d1", "alpha beta gamma delta epsilon", scope=Scope.LONG_TERM)
    await mgr.remember("d2", "alpha beta gamma delta epsilon zeta", scope=Scope.LONG_TERM)
    await mgr.sleep_consolidate(similarity_threshold=0.6)
    survivors = await mgr.recall("alpha beta gamma", scope=Scope.LONG_TERM, limit=5)
    assert len(survivors) >= 1
    assert any("alpha beta gamma delta epsilon" in m.content for m in survivors)


# ---------------------------------------------------------------------------
# 11. Reflection / self-model (D7)
# ---------------------------------------------------------------------------


async def test_reflect_self_model_first_write_creates_dock_file(db_path, tmp_path):
    """First reflection performs the dock's required first write of self_model.md."""
    dock_home = tmp_path / "dharma"
    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        path = dock_home / "agents" / "opus_composer" / "self_model.md"
        assert not path.exists()
        report = await m.reflect_self_model(dock_home=dock_home)
        assert report["written"] is True
        assert report["reflection_count"] == 1
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "# Self-Model" in text
        assert "reflection_count: 1" in text
    finally:
        m.close()


async def test_reflect_self_model_reads_accrued_memory(db_path, tmp_path):
    """The self-model is derived from accrued memory: facts and know-how surface."""
    dock_home = tmp_path / "dharma"
    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        await m.remember(
            "rv_site", "L5 residual is the primary causal site for R_V",
            scope=Scope.LONG_TERM, lane=MemoryLane.SEMANTIC,
        )
        await m.remember(
            "run_tests", "always run pytest before claiming a fix is done",
            scope=Scope.LONG_TERM, lane=MemoryLane.PROCEDURAL,
        )
        report = await m.reflect_self_model(dock_home=dock_home)
        text = Path(report["path"]).read_text(encoding="utf-8")
        assert "What I know to be true" in text
        assert "L5 residual" in text
        assert "How I work" in text
        assert "pytest" in text
        assert "total memories: 2" in text
    finally:
        m.close()


async def test_reflect_self_model_updates_across_runs(db_path, tmp_path):
    """A later reflection updates from newly-accrued memory and bumps the count."""
    dock_home = tmp_path / "dharma"
    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        await m.remember(
            "fact_one", "the first established fact about my work",
            scope=Scope.LONG_TERM, lane=MemoryLane.SEMANTIC,
        )
        r1 = await m.reflect_self_model(dock_home=dock_home)
        assert r1["reflection_count"] == 1

        # New learning accrues, then we reflect again (simulating a later run).
        await m.remember(
            "fact_two", "a second fact learned in a later run entirely",
            scope=Scope.LONG_TERM, lane=MemoryLane.SEMANTIC,
        )
        r2 = await m.reflect_self_model(dock_home=dock_home)
        assert r2["written"] is True
        assert r2["reflection_count"] == 2
        text = Path(r2["path"]).read_text(encoding="utf-8")
        assert "fact_two" in text
        assert "second fact learned in a later run" in text
        assert "reflection_count: 2" in text
    finally:
        m.close()


async def test_reflect_self_model_idempotent_on_unchanged_store(db_path, tmp_path):
    """Re-reflecting over an unchanged store does not rewrite or bump the count."""
    dock_home = tmp_path / "dharma"
    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        await m.remember(
            "stable", "an unchanging established fact",
            scope=Scope.LONG_TERM, lane=MemoryLane.SEMANTIC,
        )
        r1 = await m.reflect_self_model(dock_home=dock_home)
        assert r1["written"] is True and r1["reflection_count"] == 1
        r2 = await m.reflect_self_model(dock_home=dock_home)
        assert r2["written"] is False
        assert r2["reflection_count"] == 1  # unchanged substance => count held
    finally:
        m.close()


async def test_reflect_self_model_uses_living_agent_identity(db_path, tmp_path):
    """When a dock living_agent.json exists, its stable identity heads the file."""
    import json as _json

    dock_home = tmp_path / "dharma"
    dock_dir = dock_home / "agents" / "opus_composer"
    dock_dir.mkdir(parents=True, exist_ok=True)
    (dock_dir / "living_agent.json").write_text(
        _json.dumps({
            "agent_uid": "opus_composer",
            "callsign": "opus_composer",
            "role": "lead_orchestrator",
            "serial": "AGT-OPUS_COMPOSER",
            "memory_namespace": "agent:opus_composer",
            "current_embodiment": {"model": "claude-opus-4-8", "harness": "claude_code_headless"},
            "identity_invariant": {"authority_floor": "external_worker_evidence_only"},
        }),
        encoding="utf-8",
    )
    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        report = await m.reflect_self_model(dock_home=dock_home)
        text = Path(report["path"]).read_text(encoding="utf-8")
        assert "## Identity" in text
        assert "lead_orchestrator" in text
        assert "claude-opus-4-8" in text
        assert "external_worker_evidence_only" in text
    finally:
        m.close()


# ---------------------------------------------------------------------------
# D5: Skill / capability accumulation (named, identity-bound procedures)
# ---------------------------------------------------------------------------


async def test_learn_skill_stores_procedural_under_skill_key(mgr):
    """learn_skill stores a PROCEDURAL memory keyed skill:<name>, LONG_TERM."""
    s = await mgr.learn_skill("open a PR against a worktree", "branch -> test -> gh pr create")
    assert s.lane == MemoryLane.PROCEDURAL
    assert s.scope == Scope.LONG_TERM
    assert s.key == "skill:open a PR against a worktree"
    assert s.content == "branch -> test -> gh pr create"


async def test_learn_skill_normalises_already_prefixed_name(mgr):
    """Passing an already-prefixed name does not double the prefix."""
    s = await mgr.learn_skill("skill:run the suite", "pytest -q")
    assert s.key == "skill:run the suite"


async def test_learn_skill_rejects_empty_name(mgr):
    with pytest.raises(ValueError):
        await mgr.learn_skill("   ", "anything")


async def test_recall_skill_retrieves_relevant_skill(mgr):
    """A learned skill is retrieved on a relevant task; non-skill procedures and
    irrelevant skills are excluded."""
    await mgr.learn_skill("measure R_V", "load Mistral, patch L27, read residual")
    await mgr.learn_skill("draft a paper section", "outline, cite, write, verify")
    # A plain procedure (not a named skill) must NOT show up in a skills view.
    await mgr.learn_procedure("misc_proc", "R_V trivia that is not a skill")

    hits = await mgr.recall_skill("how do I measure R_V on Mistral", limit=5)
    keys = {m.key for m in hits}
    assert "skill:measure R_V" in keys
    assert "skill:draft a paper section" not in keys
    assert "misc_proc" not in keys  # plain procedure excluded from skills view


async def test_recall_skill_reinforces_reuse(mgr):
    """Recalling a skill for a relevant task bumps its reuse count (the reward
    signal): reuse is how a useful skill rises in the capability profile."""
    await mgr.learn_skill("ship a fix", "branch, test, PR, verify")
    # accrued_skills reads via _top_lane_blocks, which does NOT perturb access
    # stats -- the honest baseline (recall_by_key would itself touch the row).
    before = (await mgr.accrued_skills())[0]
    assert before.key == "skill:ship a fix"
    assert before.access_count == 0

    # Two relevant recalls: each is a reuse of the skill.
    await mgr.recall_skill("how do I ship a fix", limit=5)
    await mgr.recall_skill("ship the fix now", limit=5)

    after = (await mgr.accrued_skills())[0]
    assert after.access_count == before.access_count + 2  # exactly two reuses


async def test_accrued_skills_ranks_by_reuse(mgr):
    """accrued_skills enumerates the capability profile, most-reused first, and
    excludes plain (non-skill) procedures."""
    await mgr.learn_skill("rarely used", "...")
    await mgr.learn_skill("workhorse", "the skill I lean on")
    await mgr.learn_procedure("not_a_skill", "plain procedure, not a capability")
    # Make 'workhorse' clearly the most-reused.
    with mgr._lock:
        conn = mgr._get_conn()
        conn.execute(
            "UPDATE memories SET access_count=42 WHERE agent_id=? AND key='skill:workhorse'",
            (mgr.agent_id,),
        )
        conn.commit()

    profile = await mgr.accrued_skills()
    keys = [m.key for m in profile]
    assert keys[0] == "skill:workhorse"  # reuse-ranked
    assert "skill:rarely used" in keys
    assert "not_a_skill" not in keys  # plain procedure is not a skill


async def test_accrued_skills_min_uses_filter(mgr):
    """min_uses filters to skills reused at least N times."""
    await mgr.learn_skill("never reused", "...")
    await mgr.learn_skill("seasoned", "...")
    with mgr._lock:
        conn = mgr._get_conn()
        conn.execute(
            "UPDATE memories SET access_count=5 WHERE agent_id=? AND key='skill:seasoned'",
            (mgr.agent_id,),
        )
        conn.commit()
    seasoned = await mgr.accrued_skills(min_uses=1)
    assert {m.key for m in seasoned} == {"skill:seasoned"}
    all_skills = await mgr.accrued_skills(min_uses=0)
    assert {m.key for m in all_skills} == {"skill:seasoned", "skill:never reused"}


async def test_skill_persists_and_is_retrieved_across_sessions(db_path):
    """D5 acceptance: a skill learned in one session persists and is retrieved on
    a relevant task in a later session (a fresh manager, same namespace)."""
    # Session 1: opus learns a skill.
    sess1 = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    await sess1.learn_skill(
        "register an external roaming worker",
        "load_external_worker -> verify_identity -> onboard_roaming_agent",
    )
    sess1.close()

    # Session 2: a brand-new instance retrieves the skill for a relevant task.
    sess2 = AgentMemoryManager.for_namespace("opus_composer", db_path=db_path)
    try:
        hits = await sess2.recall_skill("how do I register an external roaming worker", limit=5)
        assert any(m.key == "skill:register an external roaming worker" for m in hits)
        retrieved = next(m for m in hits if m.key == "skill:register an external roaming worker")
        assert "onboard_roaming_agent" in retrieved.content
        # The skill shows up in the accrued capability profile too.
        profile = await sess2.accrued_skills()
        assert any(m.key == "skill:register an external roaming worker" for m in profile)
    finally:
        sess2.close()


async def test_reflect_self_model_surfaces_accrued_skills(db_path, tmp_path):
    """Accrued skills bind to identity: they surface in the dock self-model as an
    'Accrued skills' capability section with reuse counts, separate from plain
    'How I work' procedures."""
    dock_home = tmp_path / "dharma"
    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        await m.learn_skill("run the test suite", "pytest -q against the worktree")
        await m.learn_procedure("plain_habit", "read the file before editing it")
        # Give the skill some reuse so the count renders.
        with m._lock:
            conn = m._get_conn()
            conn.execute(
                "UPDATE memories SET access_count=7 WHERE agent_id=? AND key='skill:run the test suite'",
                (m.agent_id,),
            )
            conn.commit()
        report = await m.reflect_self_model(dock_home=dock_home)
        text = Path(report["path"]).read_text(encoding="utf-8")
        assert "## Accrued skills" in text
        assert "run the test suite" in text
        assert "reused 7x" in text
        # Plain procedure lands under 'How I work', not in the skills section.
        assert "## How I work" in text
        assert "plain_habit" in text
    finally:
        m.close()


# ---------------------------------------------------------------------------
# D8. Verify-before-done (self-verification loop)
# ---------------------------------------------------------------------------


async def test_verify_before_done_passes_substantive_text(db_path):
    """Non-code work with a substantive result verifies (structural mode)."""
    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        result = (
            "I reviewed the module, traced the call path, and confirmed the "
            "behaviour matches the contract. The change adds a bounded method "
            "and a dock receipt writer, both isolated and best-effort. This is "
            "a substantive completed work product comfortably past the short "
            "non-result gate that the runtime uses to reject empty output."
        )
        assert len(result) > 200  # comfortably past the short-result gate
        verdict = await m.verify_before_done("t-pass", result)
        assert verdict["verified"] is True
        assert verdict["status"] == "passed"
        assert verdict["mode"] == "structural"
    finally:
        m.close()


async def test_verify_before_done_fails_empty_result(db_path):
    """An empty result is not completed work -> verification fails."""
    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        verdict = await m.verify_before_done("t-empty", "")
        assert verdict["verified"] is False
        assert verdict["status"] == "failed"
        assert verdict["mode"] == "structural"
    finally:
        m.close()


async def test_verify_before_done_fails_error_string(db_path):
    """An error-prefixed result is caught and fails the verification gate."""
    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        verdict = await m.verify_before_done("t-err", "Error: API error: provider down")
        assert verdict["verified"] is False
        assert verdict["status"] == "failed"
        assert "error" in verdict["reason"].lower()
    finally:
        m.close()


async def test_verify_before_done_records_episode(db_path):
    """The verdict is recorded as an episodic verification:<id> memory."""
    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        await m.verify_before_done(
            "t-ep", "A genuine, substantive completed result that clears the gate."
        )
        rec = await m.recall_by_key("verification:t-ep")
        assert rec is not None
        assert rec.lane == MemoryLane.EPISODIC
        assert "passed" in rec.content
    finally:
        m.close()


async def test_verify_before_done_writes_dock_receipt(db_path, tmp_path):
    """The latest verdict is mirrored to the dock last_receipt.json."""
    import json

    dock_home = tmp_path / "dharma"
    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        await m.verify_before_done(
            "t-rcpt",
            "A substantive completed result clearing the structural gate cleanly.",
            dock_home=dock_home,
        )
        receipt = dock_home / "agents" / "opus_composer" / "last_receipt.json"
        assert receipt.exists()
        data = json.loads(receipt.read_text())
        assert data["last_verification"]["task_id"] == "t-rcpt"
        assert data["last_verification"]["status"] == "passed"
    finally:
        m.close()


async def test_verify_receipt_preserves_existing_fields(db_path, tmp_path):
    """Writing the verification verdict keeps any pre-existing receipt fields."""
    import json

    dock_home = tmp_path / "dharma"
    dock_dir = dock_home / "agents" / "opus_composer"
    dock_dir.mkdir(parents=True)
    (dock_dir / "last_receipt.json").write_text(json.dumps({"last_wake": "2026-06-06"}))

    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        await m.verify_before_done(
            "t-keep",
            "Another substantive completed result that clears the gate cleanly.",
            dock_home=dock_home,
        )
        data = json.loads((dock_dir / "last_receipt.json").read_text())
        # Prior field preserved, verification added alongside it.
        assert data["last_wake"] == "2026-06-06"
        assert data["last_verification"]["task_id"] == "t-keep"
    finally:
        m.close()


async def test_verify_before_done_code_clean_passes(db_path, monkeypatch):
    """Code work routes through dual_audit; a clean audit verifies (mode=dual_audit)."""
    import dharma_swarm.dual_audit as da

    class _FakeReport:
        agreements: list = []
        claude_only: list = []
        codex_only: list = []

    class _FakeAudit:
        def __init__(self, *a, **k):
            pass

        async def run(self, *targets):
            return _FakeReport()

    monkeypatch.setattr(da, "DualAudit", _FakeAudit)

    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        verdict = await m.verify_before_done(
            "t-code-ok",
            "Implemented the feature and ran the suite.",
            code_targets=[str(_MOD_PATH)],
        )
        assert verdict["verified"] is True
        assert verdict["mode"] == "dual_audit"
    finally:
        m.close()


async def test_verify_before_done_code_blocking_fails(db_path, monkeypatch):
    """A blocking finding both models agree on fails verification."""
    import dharma_swarm.dual_audit as da

    class _FakeReport:
        agreements = [
            {"severity": "critical", "location": "f.py:10", "title": "SQL injection"}
        ]
        claude_only: list = []
        codex_only: list = []

    class _FakeAudit:
        def __init__(self, *a, **k):
            pass

        async def run(self, *targets):
            return _FakeReport()

    monkeypatch.setattr(da, "DualAudit", _FakeAudit)

    m = AgentMemoryManager.for_namespace("agent:opus_composer", db_path=db_path)
    try:
        verdict = await m.verify_before_done(
            "t-code-bad",
            "Implemented the feature.",
            code_targets=[str(_MOD_PATH)],
        )
        assert verdict["verified"] is False
        assert verdict["status"] == "failed"
        assert verdict["mode"] == "dual_audit"
        assert verdict["blocking_findings"]
    finally:
        m.close()
