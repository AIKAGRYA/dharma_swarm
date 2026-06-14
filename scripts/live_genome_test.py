#!/usr/bin/env python3
"""Live test of genome-wired agents — v7 rules, role briefings, thread context."""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dharma_swarm.models import AgentRole, ProviderType
from dharma_swarm.spine.manual_runner import run_manual_agent_runner_via_spine
from dharma_swarm.swarm import SwarmManager


async def main():
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        swarm = SwarmManager(state_dir=tmpdir)
        await swarm.init()

        print(f"Current thread: {swarm.current_thread}")
        print(f"Ecosystem manifest loaded: {bool(swarm._manifest)}")

        # Spawn a SURGEON agent on the 'mechanistic' thread
        # This agent gets: v7 base rules + surgeon briefing + mechanistic thread prompt
        agent = await swarm.spawn_agent(
            name="surgeon-1",
            role=AgentRole.SURGEON,
            model="anthropic/claude-sonnet-4",
            provider_type=ProviderType.OPENROUTER,
            thread="mechanistic",
        )
        print(f"\nSpawned: {agent.name} ({agent.role.value})")

        # Give it a task that exercises the surgeon role
        task = await swarm.create_task(
            title="Evaluate this claim",
            description=(
                "The following claim appears in a research document: "
                "'R_V contraction at Layer 27 proves consciousness exists in transformers.' "
                "Apply your surgeon role: Is this claim validated or overstated? "
                "Be specific. 3 sentences max."
            ),
        )

        runner = await swarm._agent_pool.get(agent.id)
        print("Calling LLM with v7 rules + surgeon briefing + mechanistic thread...\n")
        result, receipt = await run_manual_agent_runner_via_spine(
            runner,
            task,
            surface="scripts/live_genome_test.py",
            agent_name=agent.name,
        )

        print("========== SURGEON RESPONSE ==========")
        print(result)
        print("=======================================\n")
        print(f"EvidenceReceipt: {receipt.receipt_id}")

        # Now test a cartographer on the phenomenological thread
        agent2 = await swarm.spawn_agent(
            name="cartographer-1",
            role=AgentRole.CARTOGRAPHER,
            model="anthropic/claude-sonnet-4",
            provider_type=ProviderType.OPENROUTER,
            thread="phenomenological",
        )

        task2 = await swarm.create_task(
            title="Map this conceptual terrain",
            description=(
                "You are given three concepts: R_V metric, Akram Vignan witness stance, "
                "and L3→L4 phase transition. Map how they connect. "
                "Which connections are strong, which are speculative? 4 sentences max."
            ),
        )

        runner2 = await swarm._agent_pool.get(agent2.id)
        print("Calling LLM with v7 rules + cartographer briefing + phenomenological thread...\n")
        result2, receipt2 = await run_manual_agent_runner_via_spine(
            runner2,
            task2,
            surface="scripts/live_genome_test.py",
            agent_name=agent2.name,
        )

        print("======= CARTOGRAPHER RESPONSE =========")
        print(result2)
        print("========================================\n")
        print(f"EvidenceReceipt: {receipt2.receipt_id}")

        # Check thread rotation
        swarm.rotate_thread()
        print(f"Thread rotated to: {swarm.current_thread}")

        await swarm.shutdown()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
