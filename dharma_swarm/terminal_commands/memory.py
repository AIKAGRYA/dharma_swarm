"""Memory, context, and witness commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os


from dharma_swarm.terminal_commands._helpers import (
    DHARMA_STATE,
    _get_swarm,
    _run,
)

def cmd_memory(
    memory_cmd: str | None = None,
    *,
    text: str = "",
    top_k: int = 5,
    as_json: bool = False,
) -> None:
    """Show memory status, recent entries, and unresolved latent gold."""
    if memory_cmd:
        from dharma_swarm.memory_common import (
            memory_common_summary,
            render_agent_memory_pack,
            render_memory_common_status,
            render_memory_gate,
            render_memory_ingest,
            render_memory_metabolism,
            render_memory_query,
            render_memory_schedule,
        )

        mode = memory_cmd.strip().lower()
        if as_json and mode == "status":
            print(json.dumps(memory_common_summary(state_dir=DHARMA_STATE).to_json(), indent=2, sort_keys=True))
            return
        if mode == "status":
            print(render_memory_common_status(state_dir=DHARMA_STATE))
            return
        if mode in {"query", "search"}:
            print(render_memory_query(text, state_dir=DHARMA_STATE, top_k=top_k))
            return
        if mode in {"common", "brief", "pack"}:
            print(render_agent_memory_pack(text, state_dir=DHARMA_STATE, top_k=top_k))
            return
        if mode == "ingest":
            print(render_memory_ingest(state_dir=DHARMA_STATE))
            return
        if mode == "gate":
            print(render_memory_gate(state_dir=DHARMA_STATE, top_k=top_k))
            return
        if mode in {"metabolize", "metabolism", "cycle"}:
            print(render_memory_metabolism(state_dir=DHARMA_STATE, top_k=top_k))
            return
        if mode == "schedule":
            print(render_memory_schedule(schedule=text or "every 24h", top_k=max(10, top_k)))
            return
        print(
            "Unknown memory mode. Use: "
            "dgc memory [status|query|common|ingest|gate|metabolize|schedule]"
        )
        return

    async def _show():
        from dharma_swarm.memory import StrangeLoopMemory
        from dharma_swarm.context import read_latent_gold_overview
        from dharma_swarm.memory_common import render_memory_common_status
        from dharma_swarm.routing_memory import (
            RoutingMemoryStore,
            default_routing_memory_db_path,
        )

        print(render_memory_common_status(state_dir=DHARMA_STATE))
        print()

        mem = StrangeLoopMemory(db_path=DHARMA_STATE / "db" / "memory.db")
        await mem.init_db()
        entries = await mem.recall(limit=10)
        await mem.close()
        if not entries:
            print("Memory: empty")
        else:
            print(f"=== Strange Loop Memory ({len(entries)} recent) ===\n")
            for e in entries:
                ts = e.timestamp.isoformat()[:19] if hasattr(e.timestamp, "isoformat") else str(e.timestamp)[:19]
                print(f"  [{e.layer.value:>11}] {ts}  {e.content[:100]}")

        latent = read_latent_gold_overview(state_dir=DHARMA_STATE, limit=5)
        if latent:
            print("\n=== Latent Gold (unresolved high-salience ideas) ===\n")
            for line in latent.splitlines():
                print(line)

        routing_db = default_routing_memory_db_path()
        if routing_db.exists():
            routing = RoutingMemoryStore(routing_db)
            top_routes = routing.top_routes(limit=5)
            if top_routes:
                print("\n=== Routing Memory (top learned lanes) ===\n")
                for lane in top_routes:
                    print(
                        "  "
                        f"{lane.provider.value}:{lane.model} "
                        f"[{lane.task_signature}] "
                        f"score={lane.blended_score:.3f} "
                        f"samples={lane.sample_count}"
                    )

        retrospective_path = Path(
            os.environ.get(
                "DGC_ROUTER_RETROSPECTIVE_LOG",
                str(DHARMA_STATE / "logs" / "router" / "route_retrospectives.jsonl"),
            )
        )
        if retrospective_path.exists():
            recent: list[dict[str, Any]] = []
            for line in retrospective_path.read_text(encoding="utf-8").splitlines()[-5:]:
                try:
                    recent.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            if recent:
                print("\n=== Route Retrospectives (recent high-confidence misses) ===\n")
                for item in recent:
                    record = item.get("route_record") or {}
                    provider = str(record.get("selected_provider") or "?")
                    action = str(record.get("action_name") or "?")
                    quality = record.get("quality_score")
                    severity = str(item.get("severity") or "review")
                    quality_text = (
                        f"{float(quality):.2f}"
                        if isinstance(quality, (int, float))
                        else "?"
                    )
                    print(
                        "  "
                        f"[{severity}] {action} -> {provider} "
                        f"quality={quality_text}"
                    )

    _run(_show())


def cmd_context(domain: str = "all") -> None:
    """Load context for a domain."""
    try:
        from dharma_swarm.ecosystem_map import get_context_for

        print(get_context_for(domain))
    except ImportError:
        from dharma_swarm.context import build_agent_context

        print(build_agent_context(role=domain))


def cmd_context_search(query: str, budget: int = 10_000) -> None:
    """Search for task-relevant context."""
    from dharma_swarm.context_search import ContextSearchEngine
    engine = ContextSearchEngine()
    engine.build_index()
    results = engine.search(query, max_results=10)
    if not results:
        print("No relevant context found.")
        return
    print(f"Context search: '{query}'\n")
    for r in results:
        print(f"  [{r.relevance:.1f}] {r.path}")
        if r.snippet:
            print(f"         {r.snippet[:80]}...")
        print()


def cmd_witness(msg: str) -> None:
    """Record a witness observation."""
    async def _witness():
        from dharma_swarm.memory import StrangeLoopMemory
        from dharma_swarm.models import MemoryLayer

        mem = StrangeLoopMemory(db_path=DHARMA_STATE / "db" / "memory.db")
        await mem.init_db()
        entry = await mem.remember(content=msg, layer=MemoryLayer.WITNESS)
        await mem.close()
        ts = entry.timestamp.isoformat()[:19] if hasattr(entry.timestamp, "isoformat") else str(entry.timestamp)[:19]
        print(f"Witnessed: {ts} | quality: {entry.witness_quality:.2f}")
        print(f"  {msg}")

    _run(_witness())


def cmd_develop(what: str, evidence: str) -> None:
    """Record a development marker."""
    async def _develop():
        from dharma_swarm.memory import StrangeLoopMemory
        from dharma_swarm.models import MemoryLayer

        mem = StrangeLoopMemory(db_path=DHARMA_STATE / "db" / "memory.db")
        await mem.init_db()
        content = f"DEVELOPMENT: {what} | Evidence: {evidence}"
        entry = await mem.remember(content=content, layer=MemoryLayer.DEVELOPMENT, development_marker=True)
        await mem.close()
        ts = entry.timestamp.isoformat()[:19] if hasattr(entry.timestamp, "isoformat") else str(entry.timestamp)[:19]
        print(f"Development recorded: {ts}")
        print(f"  What: {what}")
        print(f"  Evidence: {evidence}")

    _run(_develop())


def cmd_agent_memory(agent_name: str) -> None:
    """Show agent memory stats."""
    async def _mem():
        swarm = await _get_swarm()
        stats = await swarm.get_agent_memory(agent_name)
        await swarm.shutdown()
        print(f"Agent Memory: {agent_name}")
        for k, v in stats.items():
            print(f"  {k}: {v}")
    _run(_mem())
