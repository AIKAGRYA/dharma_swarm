"""Dharma governance commands (gates, dharma, foundations, telos, custodians)."""

from __future__ import annotations

import json


from dharma_swarm.terminal_commands._helpers import (
    DHARMA_STATE,
    DHARMA_SWARM,
    _run,
)

def cmd_gates(action: str, *, as_json: bool = False) -> None:
    """Run telos gates on an action."""
    from dharma_swarm.telos_gates import DEFAULT_GATEKEEPER

    result = DEFAULT_GATEKEEPER.check(action=action)

    if as_json:
        data = result.model_dump()
        data["action"] = action
        print(json.dumps(data, indent=2, default=str))
        return

    print(f"Decision: {result.decision.value.upper()}")
    print(f"Reason: {result.reason}")


def cmd_dharma_status() -> None:
    """Show kernel integrity, principle count, and corpus claim counts by status."""
    async def _status() -> None:
        from dharma_swarm.dharma_kernel import KernelGuard
        from dharma_swarm.dharma_corpus import DharmaCorpus, ClaimStatus
        from dharma_swarm.stigmergy import StigmergyStore
        from collections import Counter

        print("=== Dharma Kernel ===")
        guard = KernelGuard(kernel_path=DHARMA_STATE / "kernel.json")
        try:
            kernel = await guard.load()
            integrity = kernel.verify_integrity()
            print(f"  Integrity:  {'OK' if integrity else 'TAMPERED'}")
            print(f"  Principles: {len(kernel.principles)}")
            print(f"  Signature:  {kernel.signature[:16]}...")
            critical = [p for p in kernel.principles.values() if p.severity == "critical"]
            print(f"  Critical:   {len(critical)}  High: {len(kernel.principles) - len(critical)}")
        except FileNotFoundError:
            print("  Kernel not initialized (run swarm init to create default)")
        except ValueError as exc:
            print(f"  Kernel INVALID: {exc}")

        print("\n=== Dharma Corpus ===")
        corpus = DharmaCorpus(path=DHARMA_STATE / "corpus.jsonl")
        await corpus.load()
        all_claims = await corpus.list_claims()
        if not all_claims:
            print("  No claims in corpus.")
        else:
            counts: Counter[str] = Counter()
            for cl in all_claims:
                counts[cl.status.value] += 1
            print(f"  Total claims: {len(all_claims)}")
            for status_val in ClaimStatus:
                c = counts.get(status_val.value, 0)
                if c > 0:
                    print(f"    {status_val.value:<14} {c}")

        print("\n=== Stigmergy ===")
        store = StigmergyStore(base_path=DHARMA_STATE / "stigmergy")
        density = store.density()
        print(f"  Mark density: {density}")
        if density > 0:
            hot = await store.hot_paths(window_hours=48, min_marks=2)
            print(f"  Hot paths (48h): {len(hot)}")

    _run(_status())


def cmd_dharma_corpus(status_filter: str | None = None, category_filter: str | None = None) -> None:
    """List corpus claims with optional status/category filters."""
    async def _corpus() -> None:
        from dharma_swarm.dharma_corpus import DharmaCorpus, ClaimStatus, ClaimCategory

        corpus = DharmaCorpus(path=DHARMA_STATE / "corpus.jsonl")
        await corpus.load()
        s = ClaimStatus(status_filter) if status_filter else None
        c = ClaimCategory(category_filter) if category_filter else None
        claims = await corpus.list_claims(status=s, category=c)
        if not claims:
            print("No claims found.")
        else:
            print(f"{'ID':<16}  {'STATUS':<14}  {'CAT':<18}  {'CONF':>4}  STATEMENT")
            print("-" * 80)
            for cl in claims:
                print(
                    f"{cl.id:<16}  {cl.status.value:<14}  {cl.category.value:<18}  "
                    f"{cl.confidence:.1f}   {cl.statement[:40]}"
                )
            print(f"\n{len(claims)} claim(s) shown.")
    _run(_corpus())


def cmd_dharma_review(claim_id: str) -> None:
    """Show full claim details for review."""
    async def _review() -> None:
        from dharma_swarm.dharma_corpus import DharmaCorpus

        corpus = DharmaCorpus(path=DHARMA_STATE / "corpus.jsonl")
        await corpus.load()
        claim = await corpus.get(claim_id)
        if claim is None:
            print(f"Claim not found: {claim_id}")
            return

        print(f"=== Claim {claim.id} ===")
        print(f"  Status:     {claim.status.value}")
        print(f"  Category:   {claim.category.value}")
        print(f"  Confidence: {claim.confidence:.2f}")
        print(f"  Enforcement:{claim.enforcement}")
        print(f"  Created by: {claim.created_by}")
        print(f"  Created at: {claim.created_at}")
        if claim.parent_id:
            print(f"  Parent ID:  {claim.parent_id}")
        if claim.tags:
            print(f"  Tags:       {', '.join(claim.tags)}")
        if claim.parent_axiom:
            print(f"  Axioms:     {', '.join(claim.parent_axiom)}")

        print(f"\n  Statement:\n    {claim.statement}")

        if claim.evidence_links:
            print(f"\n  Evidence ({len(claim.evidence_links)}):")
            for ev in claim.evidence_links:
                print(f"    [{ev.type}] {ev.url_or_ref}")
                print(f"      {ev.description}")

        if claim.counterarguments:
            print(f"\n  Counterarguments ({len(claim.counterarguments)}):")
            for ca in claim.counterarguments:
                print(f"    - {ca}")

        if claim.review_history:
            print(f"\n  Review History ({len(claim.review_history)}):")
            for rr in claim.review_history:
                print(f"    [{rr.timestamp[:19]}] {rr.reviewer}: {rr.action}")
                print(f"      {rr.comment}")

        # Show lineage if this claim has a parent
        lineage = await corpus.get_lineage(claim_id)
        if len(lineage) > 1:
            print(f"\n  Lineage ({len(lineage)} claims):")
            for lc in lineage:
                marker = " <-- current" if lc.id == claim_id else ""
                print(f"    {lc.id} ({lc.status.value}){marker}")

    _run(_review())


def cmd_foundations(pillar: str | None = None) -> None:
    """Show intellectual pillars and syntheses, or preview a specific pillar."""
    fdir = DHARMA_SWARM / "foundations"
    if not fdir.exists():
        print("No foundations/ directory found.")
        return

    if pillar:
        query = pillar.upper()
        matches = sorted(fdir.glob(f"*{query}*.md"))
        if not matches:
            print(f"No pillar matching '{pillar}'")
            available = sorted(f.stem for f in fdir.glob("PILLAR_*.md"))
            print(f"Available: {', '.join(available)}")
            return
        target = matches[0]
        lines = target.read_text().split("\n")
        print(f"=== {target.name} ({len(lines)} lines) ===\n")
        for line in lines[:60]:
            print(line)
        if len(lines) > 60:
            print(f"\n... ({len(lines) - 60} more lines)")
        return

    # List all
    pillars = sorted(fdir.glob("PILLAR_*.md"))
    synths = sorted(fdir.glob("*SYNTHESIS*.md"))
    arch = DHARMA_SWARM / "architecture" / "PRINCIPLES.md"

    print(f"=== Intellectual Pillars ({len(pillars)}) ===\n")
    for p in pillars:
        name = p.stem.replace("PILLAR_", "").replace("_", " ")
        size = len(p.read_text().split("\n"))
        print(f"  {p.name:<35} {name:<25} ({size} lines)")

    if synths:
        print(f"\n=== Syntheses ({len(synths)}) ===\n")
        for s in synths:
            size = len(s.read_text().split("\n"))
            print(f"  {s.name:<35} ({size} lines)")

    if arch.exists():
        size = len(arch.read_text().split("\n"))
        print(f"\n  PRINCIPLES.md  Architecture bridge ({size} lines)")

    total_lines = sum(len(f.read_text().split("\n")) for f in pillars)
    total_lines += sum(len(f.read_text().split("\n")) for f in synths)
    print(f"\n  Total: {len(pillars)} pillars, {len(synths)} syntheses, ~{total_lines} lines")
    print(f"\n  Usage: dgc foundations <name> (e.g. dgc foundations hofstadter)")


def cmd_telos(doc: str | None = None) -> None:
    """Show telos engine research documents, or preview a specific document."""
    tdir = DHARMA_SWARM / "docs" / "telos-engine"
    if not tdir.exists():
        print("No docs/telos-engine/ directory found.")
        return

    if doc:
        query = doc.lower()
        matches = sorted(f for f in tdir.glob("*.md") if query in f.name.lower())
        if not matches:
            print(f"No document matching '{doc}'")
            available = sorted(f.stem for f in tdir.glob("[0-9]*.md"))
            print(f"Available: {', '.join(available)}")
            return
        target = matches[0]
        lines = target.read_text().split("\n")
        print(f"=== {target.name} ({len(lines)} lines) ===\n")
        for line in lines[:60]:
            print(line)
        if len(lines) > 60:
            print(f"\n... ({len(lines) - 60} more lines)")
        return

    docs = sorted(f for f in tdir.glob("*.md") if f.name != "INDEX.md")
    print(f"=== Telos Engine Research ({len(docs)} documents) ===\n")
    for d in docs:
        display = d.stem.lstrip("0123456789_").replace("_", " ")
        size = len(d.read_text().split("\n"))
        print(f"  {d.name:<35} {display:<30} ({size} lines)")

    total_lines = sum(len(f.read_text().split("\n")) for f in docs)
    print(f"\n  Total: {len(docs)} documents, ~{total_lines} lines")
    print(f"\n  Usage: dgc telos <name> (e.g. dgc telos competitive)")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def cmd_custodians(
    custodians_cmd: str | None = None,
    roles: str | None = None,
    dry_run: bool = True,
) -> None:
    """Autonomous code maintenance fleet commands."""
    from dharma_swarm.custodians import (
        run_custodian_cycle, format_status, create_custodian_cron_jobs, ROLES,
    )

    match custodians_cmd:
        case "run":
            role_list = [r.strip() for r in roles.split(",")] if roles else None
            if role_list:
                invalid = [r for r in role_list if r not in ROLES]
                if invalid:
                    print(f"  Unknown roles: {', '.join(invalid)}")
                    print(f"  Valid: {', '.join(ROLES)}")
                    return
            mode = "DRY RUN" if dry_run else "LIVE"
            print(f"  Custodian fleet — {mode}")
            results = run_custodian_cycle(roles=role_list, dry_run=dry_run)
            for r in results:
                icon = "✅" if r.success else "❌"
                dry_tag = " [DRY]" if r.dry_run else ""
                print(f"  {icon} {r.role}{dry_tag}  model={r.model}  {r.duration_seconds}s")
                if r.files_targeted:
                    print(f"    targets: {', '.join(r.files_targeted[:5])}")
                if r.files_changed:
                    print(f"    changed: {', '.join(r.files_changed[:5])}")
                if r.committed:
                    print(f"    committed: yes")
                if r.error:
                    print(f"    error: {r.error}")
                if r.agent_output and not r.dry_run:
                    print(f"    output: {r.agent_output[:200]}")
        case "status":
            print(format_status())
        case "schedule":
            created = create_custodian_cron_jobs()
            if created:
                print(f"  Created {len(created)} custodian cron job(s):")
                for j in created:
                    print(f"    - {j.get('name', j.get('id', '?'))}")
            else:
                print("  All custodian cron jobs already exist.")
            # Install launchd service so daemon survives reboots
            from dharma_swarm.custodians import install_launchd_service
            if install_launchd_service():
                print("  Launchd service installed — daemon will auto-start on boot.")
            else:
                print("  Launchd service not installed (run `dgc cron daemon` manually).")
        case _:
            print("Usage: dgc custodians {run|status|schedule}")
