"""Meta-analysis and housekeeping commands (xray, prune, meta, skills, cross, field)."""

from __future__ import annotations

from pathlib import Path
import asyncio
import subprocess
import sys


from dharma_swarm.terminal_commands._helpers import (
    DHARMA_STATE,
    DHARMA_SWARM,
)

def cmd_xray(
    repo_path: str,
    output: str | None = None,
    as_json: bool = False,
    exclude: list[str] | None = None,
    packet: bool = False,
    buyer: str = "CTO or founder under shipping pressure",
) -> None:
    """Run a Repo X-Ray analysis."""
    from dharma_swarm.xray import (
        analyze_repo,
        render_markdown,
        run_xray,
        run_xray_packet,
    )

    path = Path(repo_path).expanduser().resolve()
    if not path.is_dir():
        print(f"  Error: {path} is not a directory")
        raise SystemExit(1)

    exclude_set = set(exclude) if exclude else None
    print(f"  Scanning {path}...")
    if packet:
        outputs = run_xray_packet(
            path,
            output_dir=output,
            buyer=buyer,
            exclude_patterns=exclude_set,
        )
        print(f"  Packet saved to: {outputs['output_dir']}")
        print(f"  Service brief: {outputs['service_brief']}")
        print(f"  Mission brief: {outputs['mission_brief']}")
        print(f"  Report JSON: {outputs['report_json']}")
        return

    report_path = run_xray(path, output_path=output, as_json=as_json, exclude_patterns=exclude_set)

    if not as_json:
        report = analyze_repo(path, exclude_patterns=exclude_set)
        md = render_markdown(report)
        print(md)

    print(f"\n  Report saved to: {report_path}")


def _run_prune(
    dry_run: bool = False,
    stig_threshold: float = 0.3,
    bridge_threshold: float = 0.2,
    trace_days: int = 14,
) -> None:
    """Sweep the zen garden."""
    try:
        from dharma_swarm.pruner import Pruner

        pruner = Pruner(
            state_dir=DHARMA_STATE,
            stigmergy_threshold=stig_threshold,
            bridge_threshold=bridge_threshold,
            trace_max_days=trace_days,
            dry_run=dry_run,
        )
        report = asyncio.run(pruner.sweep())
        pruner.print_report(report)
    except Exception as exc:
        print(f"Pruner failed: {exc}")
        raise SystemExit(1)


def _run_meta() -> None:
    """Run the Overseeing I wholistic assessment."""
    try:
        from dharma_swarm.overseeing_i import OverseeingI

        oi = OverseeingI(state_dir=DHARMA_STATE)
        assessment = asyncio.run(oi.assess())
        oi.print_assessment(assessment)
    except Exception as exc:
        print(f"Overseeing I failed: {exc}")
        raise SystemExit(1)


def cmd_skills() -> None:
    """List all discovered skills."""
    from dharma_swarm.skills import SkillRegistry
    registry = SkillRegistry()
    skills = registry.discover()
    if not skills:
        print("No skills discovered. Add .skill.md files to dharma_swarm/skills/")
        return
    print(f"Discovered {len(skills)} skills:\n")
    for skill in sorted(skills.values(), key=lambda s: s.priority):
        tags = ", ".join(skill.tags[:5]) if skill.tags else "none"
        print(f"  {skill.name:<16} model={skill.model:<12} "
              f"autonomy={skill.autonomy:<10} tags=[{tags}]")
        if skill.description:
            print(f"  {'':16} {skill.description[:80]}")


def cmd_cross(
    cross_cmd: str | None = None,
    max_edges: int = 5,
    dry_run: bool = False,
) -> None:
    """YATAGARASU cross-pollination engine commands."""
    from dharma_swarm.cross_pollination import CrossPollinationEngine

    engine = CrossPollinationEngine()

    match cross_cmd:
        case "run":
            if dry_run:
                print("  YATAGARASU — dry run (showing candidates only)")
                from dharma_swarm.catalytic_graph import CatalyticGraph
                cg = CatalyticGraph()
                if cg.load():
                    missing = cg.loop_closure_priority()[:max_edges]
                    for src, tgt, score in missing:
                        print(f"  {src} → {tgt}  (score: {score:.3f})")
                else:
                    print("  No catalytic graph data. Run `dgc cross run` (without --dry-run) to seed.")
            else:
                import asyncio
                print(f"  YATAGARASU — cross-pollination session (max_edges={max_edges})")
                results = asyncio.run(engine.run_session(max_edges=max_edges))
                accepted = [r for r in results if r.accepted]
                rejected = [r for r in results if not r.accepted]
                print(f"\n  Results: {len(accepted)} accepted, {len(rejected)} rejected")
                for r in accepted:
                    print(f"  ✅ {r.source} → {r.target} ({r.edge_type}, strength={r.score:.2f}) via {r.model_used}")
                for r in rejected:
                    print(f"  ❌ {r.source} → {r.target} — {r.evidence[:60]}")
        case "status":
            print(engine.format_status())
        case "fly":
            import asyncio as _asyncio_fly
            print("  八咫烏 YATAGARASU — full murder flight")
            print("  GLM-5-Turbo → 5 KARASU on MiniMax M2.7 → TOMBI on coding models")
            print()
            result = _asyncio_fly.run(engine.fly_murder())
            print(f"\n  Flight complete: {result['accepted_edges']}/{result['total_candidates']} edges accepted")
        case _:
            print("Usage: dgc cross {run|status|fly}")
            print("  run [--max-edges N] [--dry-run]  Run cross-pollination session")
            print("  status                           Show catalytic graph health")
            print("  fly                              Full murder flight")


def cmd_field_scan() -> None:
    """Run full D3 field intelligence scan."""

    script = DHARMA_SWARM / "scripts" / "field_scan.py"
    if not script.exists():
        print(f"[field scan] Script not found: {script}")
        raise SystemExit(2)
    result = subprocess.run([sys.executable, str(script)], cwd=str(DHARMA_SWARM))
    raise SystemExit(result.returncode)


def cmd_field_gaps() -> None:
    """Show DGC capability gaps vs external field."""
    from dharma_swarm.field_graph import gap_report

    gp = gap_report()
    print(f"  {gp['title']}")
    print(f"  Hard gaps: {gp['hard_gap_count']}  |  Integration opportunities: {gp['integration_count']}")
    print()
    for item in gp["hard_gaps"]:
        print(f"  ✗ {item['id']} ({item['field']})")
        print(f"    → {item['source']}")
        print(f"    {item['relevance'][:140]}")
        print()
    for item in gp["integration_opportunities"]:
        print(f"  ⊕ {item['id']} ({item['field']})")
        print(f"    → {item['source']}")
        print()


def cmd_field_position() -> None:
    """Show DGC competitive positioning."""
    from dharma_swarm.field_graph import competitive_position

    cp = competitive_position()
    sa = cp["strategic_assessment"]
    print(f"  {cp['title']}")
    print(f"  Overall: {sa['overall']}  |  Moats: {sa['moat_count']}  "
          f"Gaps: {sa['gap_count']}  Validated: {sa['validated_count']}  "
          f"Threats: {sa['threat_count']}")
    print()
    for t in cp["competitive_threats"]:
        print(f"  [{t['threat_level']}] {t['id']}: {t['source']}")
    print()
    for domain, info in cp["domain_coverage"].items():
        print(f"  {domain:<24} [{info['strength']:<12}] "
              f"unique={info['unique']} gaps={info['gaps']} validated={info['validated']}")


def cmd_field_unique() -> None:
    """Show DGC unique moats."""
    from dharma_swarm.field_graph import uniqueness_report

    un = uniqueness_report()
    print(f"  {un['title']}")
    print(f"  Moat count: {un['count']}")
    print()
    for item in un["moats"]:
        print(f"  ★ {item['id']}")
        print(f"    {item['summary'][:140]}")
        print()


def cmd_field_summary() -> None:
    """Field KB summary statistics."""
    from dharma_swarm.field_knowledge_base import field_summary

    s = field_summary()
    print(f"  D3 Field KB: {s['total_entries']} entries")
    print(f"  Unique: {s['dgc_unique']}  Gaps: {s['dgc_gaps']}  Competitors: {s['dgc_competitors']}")
    print()
    print("  By relation:")
    for r, c in sorted(s["by_relation"].items(), key=lambda x: -x[1]):
        print(f"    {r:<16} {c}")
    print("  By field:")
    for f, c in sorted(s["by_field"].items(), key=lambda x: -x[1]):
        print(f"    {f:<32} {c}")


def cmd_orchestrate(description: str) -> None:
    """Decompose a task and show the orchestration plan."""
    from dharma_swarm.skills import SkillRegistry
    from dharma_swarm.intent_router import IntentRouter
    registry = SkillRegistry()
    registry.discover()
    router = IntentRouter(registry=registry)
    result = router.decompose(description)
    print(f"Task: {result.original}")
    print(f"Complexity: {result.estimated_complexity}")
    print(f"Total agents: {result.total_agents}")
    print(f"Parallel: {'yes' if result.has_parallel_work else 'no'}")
    print(f"\nSub-tasks ({len(result.sub_tasks)}):")
    for i, st in enumerate(result.sub_tasks, 1):
        print(f"  {i}. [{st.primary_skill or 'general'}] {st.task}")
        print(f"     complexity={st.complexity} risk={st.risk_level}")
