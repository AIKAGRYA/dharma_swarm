"""Infrastructure commands (agni, model, providers, gateway, compose)."""

from __future__ import annotations

from pathlib import Path
import asyncio
import json
import subprocess
import sys


from dharma_swarm.terminal_commands._helpers import (
    DHARMA_SWARM,
    HOME,
    _get_swarm,
    _run,
)

def cmd_agni(command: str) -> None:
    """Run command on AGNI VPS."""
    from dharma_swarm.telos_gates import check_with_reflective_reroute

    gate = check_with_reflective_reroute(
        action=f"agni:{command}",
        content=command,
        tool_name="dgc_cli_agni",
        think_phase="before_complete",
        reflection=(
            "Remote command execution on AGNI. Validate blast radius, "
            "rollback path, and least-privilege intent."
        ),
        max_reroutes=1,
        requirement_refs=["agni:remote_exec"],
    )
    if gate.result.decision.value == "block":
        print(f"TELOS BLOCK: {gate.result.reason}")
        sys.exit(2)
    if gate.attempts:
        print(f"[witness] reflective reroute applied ({gate.attempts} attempts)")

    ssh_key = HOME / ".ssh" / "openclaw_do"
    result = subprocess.run(
        ["ssh", "-i", str(ssh_key), "-o", "ConnectTimeout=10",
         "root@157.245.193.15", command],
        capture_output=True, text=True, timeout=30,
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"STDERR: {result.stderr}", file=sys.stderr)


def cmd_model(action: str) -> None:
    """Handle model management commands."""
    from dharma_swarm.model_manager import (
        show_current_model,
        list_models,
        format_model_table,
        switch_model,
        MODELS,
    )

    if action == "status" or action is None:
        print(show_current_model())
    elif action == "list":
        models = list_models()
        print(format_model_table(models))
    elif action in MODELS or action.startswith("claude-") or action.startswith("gpt-"):
        success, message = switch_model(action)
        print(message)
        if not success:
            sys.exit(1)
    else:
        print(f"Unknown action or model: {action}")
        print("Usage: dgc model [status|list|opus|sonnet|haiku|gpt-4o]")
        sys.exit(1)


def cmd_model_catalog(
    selector: str | None = None,
    as_json: bool = False,
) -> None:
    """Show the canonical model catalog or a specific named pack."""
    from dharma_swarm.model_catalog import model_catalog_summary

    print(model_catalog_summary(selector=selector, as_json=as_json))


def cmd_model_pool(
    *,
    as_json: bool = False,
    limit: int = 40,
    refresh_nim: bool = False,
    include_ollama_list: bool = True,
) -> None:
    """Show the merged model pool registry."""
    from dharma_swarm.model_pool_registry import model_pool_summary

    print(
        model_pool_summary(
            as_json=as_json,
            limit=limit,
            refresh_nim=refresh_nim,
            include_ollama_list=include_ollama_list,
        )
    )


def cmd_free_fleet(
    tier: int | None = None,
    as_json: bool = False,
    set_env: bool = False,
) -> None:
    """Show free-fleet model configuration, optionally filtered by tier."""
    import json as _json
    from dharma_swarm.free_fleet import FREE_FLEET, TIER_MODELS, ALL_FREE_MODELS

    if set_env:
        print("export DGC_FREE_FLEET=1")
        return

    if tier is not None:
        if tier not in (1, 2, 3):
            print(f"Error: invalid tier {tier!r}. Must be 1, 2, or 3.")
            raise SystemExit(1)
        models = TIER_MODELS.get(tier, [])
        if as_json:
            print(_json.dumps({"tier": tier, "models": models}, indent=2))
        else:
            print(f"Tier {tier} models:")
            for m in models:
                print(f"  {m}")
        return

    if as_json:
        data = {
            "tiers": {str(k): v for k, v in TIER_MODELS.items()},
            "all_models": ALL_FREE_MODELS,
            "default_tier": FREE_FLEET.default_tier,
        }
        print(_json.dumps(data, indent=2))
    else:
        print("FREE_FLEET — zero-cost OpenRouter models")
        print(f"  Default tier: {FREE_FLEET.default_tier}")
        for tier_num, models in TIER_MODELS.items():
            print(f"\n  Tier {tier_num}:")
            for m in models:
                print(f"    {m}")


def cmd_provider_smoke(
    *,
    ollama_model: str | None = None,
    nim_model: str | None = None,
    qwen_provider: str | None = None,
    qwen_task: str | None = None,
    telemetry_db: str | None = None,
    as_json: bool = False,
) -> int:
    """Run best-effort smoke tests for local and external provider lanes."""
    from dharma_swarm.provider_smoke import run_provider_smoke

    payload = run_provider_smoke(
        ollama_model=ollama_model,
        nim_model=nim_model,
        qwen_provider=qwen_provider,
        qwen_task=qwen_task,
        telemetry_db_path=telemetry_db,
    )
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    for label, block in payload.items():
        if label.startswith("_"):
            continue
        print(
            f"[{label}] status={block.get('status')} "
            f"model={block.get('model') or block.get('configured_model')}"
        )
        if label == "ollama":
            installed = block.get("installed_models") or []
            if installed:
                print(f"  installed={', '.join(installed[:10])}")
            if block.get("strongest_installed"):
                print(f"  strongest_installed={block['strongest_installed']}")
            if block.get("root_issue"):
                print(f"  root_issue={block['root_issue']}")
        if block.get("strongest_verified"):
            print(f"  strongest_verified={block['strongest_verified']}")
        verified = block.get("verified_models") or []
        if verified:
            summary = ", ".join(
                f"{item.get('model')}:{item.get('status')}" for item in verified[:6]
            )
            print(f"  verified={summary}")
        if label == "qwen_dashboard":
            if block.get("resolved_provider"):
                print(f"  resolved_provider={block['resolved_provider']}")
            if block.get("tool_names"):
                print(f"  tool_names={', '.join(block['tool_names'])}")
            if block.get("required_env_key") and block.get("status") == "missing_config":
                print(f"  required_env_key={block['required_env_key']}")
        if block.get("configured_base_url"):
            print(f"  base_url={block['configured_base_url']}")
        if block.get("response_preview"):
            print(f"  preview={block['response_preview']}")
        if block.get("error"):
            print(f"  error={block['error']}")
    telemetry = payload.get("_telemetry")
    if isinstance(telemetry, dict):
        print(
            f"[telemetry] status={telemetry.get('status')} "
            f"outcomes={telemetry.get('outcome_count', 0)} "
            f"session_id={telemetry.get('session_id')}"
        )
        if telemetry.get("db_path"):
            print(f"  db_path={telemetry['db_path']}")
        for item in (telemetry.get("errors") or [])[:5]:
            print(f"  error={item}")
    return 0


def cmd_provider_matrix(
    *,
    profile: str,
    corpus: str,
    max_targets: int | None,
    max_prompts: int | None,
    timeout_seconds: float,
    concurrency: int,
    budget_units: int | None,
    artifact_dir: str | None,
    include_unavailable: bool,
    write_artifacts: bool,
    as_json: bool = False,
) -> int:
    """Run the live provider/model matrix harness."""
    from dharma_swarm.provider_matrix import run_provider_matrix

    payload = run_provider_matrix(
        profile=profile,
        corpus=corpus,
        max_targets=max_targets,
        max_prompts=max_prompts,
        timeout_seconds=timeout_seconds,
        concurrency=concurrency,
        budget_units=budget_units,
        artifact_dir=artifact_dir,
        include_unavailable=include_unavailable,
        write_artifacts=write_artifacts,
        working_dir=str(DHARMA_SWARM),
    )
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    counts = payload.get("counts", {})
    budget = payload.get("budget", {})
    print(
        f"[provider-matrix] profile={payload.get('profile')} corpus={payload.get('corpus')} "
        f"attempted={counts.get('attempted', 0)} ok={counts.get('ok', 0)} "
        f"schema_valid={counts.get('schema_valid', 0)} "
        f"budget={budget.get('units_consumed')}/{budget.get('budget_units')}"
    )
    for row in payload.get("leaderboard", [])[:10]:
        print(
            f"  {row.get('provider')} / {row.get('model')} "
            f"[{row.get('lane_role')}, {row.get('tier')}] "
            f"score={row.get('avg_score')} ok={row.get('ok_count')}/{row.get('attempts')} "
            f"latency={row.get('avg_elapsed_sec')}s"
        )
    artifacts = payload.get("artifacts", {})
    if artifacts:
        print(
            f"[artifacts] json={artifacts.get('json_path')} "
            f"md={artifacts.get('markdown_path')}"
        )
    return 0


# ---------------------------------------------------------------------------
# Bootstrap command
# ---------------------------------------------------------------------------


def cmd_gateway(config_path: str | None = None) -> None:
    """Start the messaging gateway."""

    async def _run_gateway() -> None:
        from dharma_swarm.gateway.runner import GatewayRunner, load_gateway_config

        config = load_gateway_config(
            Path(config_path) if config_path else None
        )
        if not config:
            print("  No gateway config found. Create ~/.dharma/gateway.yaml")
            print("  Example:")
            print("    telegram:")
            print("      enabled: true")
            print("      token: ${TELEGRAM_BOT_TOKEN}")
            return

        runner = GatewayRunner(config=config)
        print("  Starting gateway...")
        await runner.start()
        print(f"  Gateway running with {len(runner.adapters)} adapter(s). Press Ctrl+C to stop.")

        try:
            while runner.is_running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n  Stopping gateway...")
        finally:
            await runner.stop()
            print("  Gateway stopped.")

    asyncio.run(_run_gateway())


def cmd_bootstrap() -> None:
    """Generate and display the bootstrap manifest (NOW.json)."""
    from dharma_swarm.bootstrap import generate_manifest, print_manifest
    manifest = generate_manifest()
    print_manifest(manifest)


# ---------------------------------------------------------------------------
# D3 Field Intelligence commands
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Cron and Gateway commands (v0.6.0)
# ---------------------------------------------------------------------------


def cmd_route(description: str) -> None:
    """Route a task to the best skill."""
    from dharma_swarm.skills import SkillRegistry
    from dharma_swarm.intent_router import IntentRouter
    registry = SkillRegistry()
    registry.discover()
    router = IntentRouter(registry=registry)
    skill_name, intent = router.route(description)
    print(f"Task: {description}")
    print(f"  Skill:      {skill_name}")
    print(f"  Confidence: {intent.confidence:.0%}")
    print(f"  Complexity: {intent.complexity}")
    print(f"  Risk:       {intent.risk_level}")
    print(f"  Agents:     {intent.recommended_agents}")
    if intent.parallel:
        print(f"  Parallel:   yes")


def cmd_autonomy(action: str) -> None:
    """Check autonomy decision for an action."""
    from dharma_swarm.adaptive_autonomy import AdaptiveAutonomy
    auto = AdaptiveAutonomy(base_level="balanced")
    decision = auto.should_auto_approve(action)
    status = "AUTO-APPROVE" if decision.auto_approve else "REQUIRES APPROVAL"
    print(f"Action: {action}")
    print(f"  Risk:     {decision.risk.value}")
    print(f"  Decision: {status}")
    if decision.reason:
        print(f"  Reason:   {decision.reason}")
    if decision.escalate_to:
        print(f"  Escalate: {decision.escalate_to}")


def cmd_compose(description: str) -> None:
    """Compose a task into a DAG execution plan."""
    async def _compose():
        swarm = await _get_swarm()
        result = await swarm.compose_task(description)
        await swarm.shutdown()
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        print(f"Task: {result['task']}")
        print(f"Status: {result['status']}")
        print(f"\nSteps ({len(result['steps'])}):")
        for s in result["steps"]:
            deps = f" (depends on: {', '.join(s['deps'])})" if s["deps"] else ""
            print(f"  {s['id']}: [{s['skill']}] {s['task']}{deps}")
        print(f"\nExecution waves: {len(result['waves'])}")
        for i, wave in enumerate(result["waves"]):
            print(f"  Wave {i+1}: {', '.join(wave)}")
        if result["ready"]:
            print(f"\nReady now: {', '.join(result['ready'])}")
    _run(_compose())


def cmd_execute_compose(description: str) -> None:
    """Compose and execute a task DAG end-to-end."""
    async def _exec():
        swarm = await _get_swarm()
        result = await swarm.execute_composition(description)
        await swarm.shutdown()
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        print(f"Task: {result['task']}")
        print(f"Status: {result['status']}")
        print(f"Completed: {result['steps_completed']}  "
              f"Failed: {result['steps_failed']}  "
              f"Skipped: {result['steps_skipped']}  "
              f"Duration: {result['duration']}s")
        for s in result.get("steps", []):
            icon = "+" if s["success"] else "x"
            line = f"  [{icon}] {s['id']}: [{s['skill']}]"
            if s["error"]:
                line += f" ERROR: {s['error']}"
            elif s["output"]:
                line += f" {s['output'][:100]}"
            print(line)
    _run(_exec())


def cmd_handoff(from_agent: str, to_agent: str, context: str, content: str) -> None:
    """Create a structured handoff between agents."""
    async def _handoff():
        swarm = await _get_swarm()
        result = await swarm.create_handoff(
            from_agent=from_agent, to_agent=to_agent,
            task_context=context,
            artifacts=[{"type": "context", "content": content, "summary": content[:60]}],
        )
        await swarm.shutdown()
        print(f"Handoff created: {result.get('id', 'unknown')}")
        print(f"  {result.get('summary', '')}")
    _run(_handoff())
