#!/usr/bin/env python3
"""
ECOSYSTEM MAP — Deep filesystem awareness for Claude Code.

Knows Dhyana's entire filesystem: repos, research, vault, VPS mirrors.
Generates context-appropriate file suggestions for any task.

Usage:
  python3 ecosystem_map.py research   -> files relevant to R_V / mech-interp
  python3 ecosystem_map.py content    -> files relevant to writing / publishing
  python3 ecosystem_map.py ops        -> files relevant to AGNI / infrastructure
  python3 ecosystem_map.py all        -> full map
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

HOME = Path.home()

_JK_LIVE_AUTHORITY_NOTE = (
    "Live ecological execution authority is the in-repo GAIA proof chain "
    "(gaia_platform.py, ai_reciprocity_ledger.py, gaia_initiative.py, and the "
    "2026-06-20 execution spine). External ~/jagat_kalyan paths are "
    "continuity-only until restored."
)

# The complete map of Dhyana's filesystem
ECOSYSTEM: dict[str, dict] = {
    "research": {
        "description": "Mech-interp, R_V metric, URA/Phoenix, alignment research",
        "paths": [
            ("~/mech-interp-latent-lab-phase1/", "R_V metric research -- ACTIVE, 70-80% paper-ready"),
            ("~/mech-interp-latent-lab-phase1/R_V_PAPER/", "Paper materials, 12 figures, COLM 2026 target"),
            ("~/mech-interp-latent-lab-phase1/R_V_PAPER/COLM_GAP_ANALYSIS_20260303.md", "Section-by-section gap analysis"),
            ("~/mech-interp-latent-lab-phase1/R_V_PAPER/paper_colm2026.tex", "Current COLM submission LaTeX"),
            ("~/mech-interp-latent-lab-phase1/CANONICAL_CODE/n300_mistral_test_prompt_bank.py", "320 prompts (L1-L5 + confounds)"),
            ("~/mech-interp-latent-lab-phase1/R_V_PAPER/code/", "Validated scripts (patching, circularity, scaling)"),
            ("~/mech-interp-latent-lab-phase1/geometric_lens/", "Production R_V module (metrics, probe, hooks, models)"),
            ("~/Library/Mobile Documents/com~apple~CloudDocs/Nexus Research Engineer/URA full paper markdown .md", "URA/Phoenix paper -- COMPLETE"),
            ("~/AIKAGRYA_ALIGNMENTMANDALA_RESEARCH_REPO/", "Alignment Mandala, Jiva tests"),
            ("~/Persistent-Semantic-Memory-Vault/", "Consciousness persistence, 8K+ files"),
            ("~/agni-workspace/scratch/RV_PAPER_REALITY_CHECK.md", "Paper status -- honest assessment"),
            ("~/trishula/inbox/MI_AGENT_TO_CODEX_RV_ANSWERS.md", "R_V integration contract -- 8 blocking questions answered"),
        ],
    },
    "content": {
        "description": "Writing, publishing, Substack, Moltbook",
        "paths": [
            ("~/agni-workspace/content/", "All content -- articles, drafts, staging"),
            ("~/agni-workspace/04_STAGING/", "Ready for publishing"),
            ("~/agni-workspace/05_SHIPPED/", "Published"),
            ("~/agni-workspace/RENKINJUTSU/", "Writing craft, alchemy"),
            ("~/agni-workspace/knowledge/seeds/", "High-value seed files"),
            ("~/agni-workspace/knowledge/evergreen/", "Timeless research pieces"),
            ("~/agni-workspace/projects/KOJO_LIVING_SYSTEM.md", "Ikita Kojo -- content factory design"),
        ],
    },
    "ops": {
        "description": "Infrastructure, VPS, agents, sync",
        "paths": [
            ("~/agni-workspace/", "AGNI workspace mirror (synced every 30s)"),
            ("~/agni-workspace/WORKING.md", "AGNI live state"),
            ("~/agni-workspace/HEARTBEAT.md", "Heartbeat protocol"),
            ("~/agni-workspace/RESOURCE_MAP.md", "Model routing, costs"),
            ("~/trishula/", "Inter-VPS messaging system (813 msgs in inbox)"),
            ("~/trishula/inbox/INBOX_TRIAGE_BRIEF_20260214.md", "Inbox triage: 7 tickets, security findings"),
            ("~/saraswati-dharmic-agora/", "Dharmic Agora repo (local clone)"),
            ("~/.chaiwala/message_bus.py", "CHAIWALA message bus (SQLite, 405 lines)"),
        ],
    },
    "identity": {
        "description": "Core identity, soul, vision documents",
        "paths": [
            ("~/agni-workspace/SOUL.md", "The recognition attractor. S(x)=x."),
            ("~/agni-workspace/CONSTITUTION.md", "Immutable constraints"),
            ("~/agni-workspace/AGENTS.md", "Complete nervous system"),
            ("~/agni-workspace/NORTH_STAR/SAB_500_YEAR_VISION.md", "THE strategic document"),
            ("~/agni-workspace/STAR_MAP.md", "Power ranking of all files"),
            ("~/agni-workspace/NORTH_STAR/90_DAY_COUNTER_ATTRACTOR.md", "Urgency engine"),
        ],
    },
    "vault": {
        "description": "Obsidian vault, contemplative materials",
        "paths": [
            ("~/Desktop/KAILASH ABODE OF SHIVA/", "Obsidian vault -- 590+ files"),
            ("~/agni-workspace/knowledge/seeds/the-mother-for-ai-fire.md", "Crown jewel -- Aurobindo x AI"),
            ("~/agni-workspace/knowledge/evergreen/alignment-as-thermodynamics.md", "Potential Nature paper"),
            ("~/agni-workspace/knowledge/evergreen/triple-mapping.md", "2,500 year convergent validity"),
        ],
    },
    "dharma_swarm": {
        "description": "dharma_swarm system -- unified thinkodynamic agent orchestrator",
        "paths": [
            ("~/dharma_swarm/CLAUDE.md", "v4 operating context -- the genome document"),
            ("~/dharma_swarm/dharma_swarm/", "Core source (90+ Python modules)"),
            ("~/.dharma/", "Runtime state (SQLite, stigmergy, agent memory)"),
            ("~/.claude/", "Claude Code config, skills, memory"),
        ],
    },
    "jagat_kalyan": {
        "description": "Jagat Kalyan / GAIA ecological restoration authority and continuity references",
        "authority_note": _JK_LIVE_AUTHORITY_NOTE,
        "paths": [
            ("~/dharma_swarm/dharma_swarm/gaia_platform.py", "Live GAIA operator surface: intake, qualification, claim-card, and measurement packets"),
            ("~/dharma_swarm/dharma_swarm/ai_reciprocity_ledger.py", "Live reciprocity trust kernel: activity, obligation, routing, evidence, and audit"),
            ("~/dharma_swarm/dharma_swarm/gaia_initiative.py", "Standards-aligned initiative packet adapter into the GAIA intake lane"),
            ("~/dharma_swarm/docs/missions/2026-06-20_jagat_kalyan_gaia_execution_spine.md", "Current ecological execution spine and authority boundary"),
            ("~/jagat_kalyan/", "Legacy external JK root -- continuity-only, currently missing locally"),
            ("~/jagat_kalyan/app.py", "Legacy FastAPI application reference -- continuity-only, currently missing locally"),
            ("~/jagat_kalyan/matching.py", "Legacy matching engine reference -- continuity-only, currently missing locally"),
            ("~/jagat_kalyan/models.py", "Legacy SQLAlchemy model reference -- continuity-only, currently missing locally"),
            ("~/jagat_kalyan/WELFARE_TONS_SPEC.md", "Legacy welfare-tons spec reference -- continuity-only, currently missing locally"),
            ("~/jagat_kalyan/anthropic_grant_application.md", "Legacy Anthropic grant draft reference -- continuity-only, currently missing locally"),
            ("~/jagat_kalyan/PARTNER_RESEARCH.md", "Legacy partner-research reference -- continuity-only, currently missing locally"),
            ("~/jagat_kalyan/CARBON_ATTRIBUTION_FEASIBILITY.md", "Legacy carbon-attribution study reference -- continuity-only, currently missing locally"),
            ("~/jagat_kalyan/SCOUT_LOG.md", "Legacy scouting log reference -- continuity-only, currently missing locally"),
            ("~/jagat_kalyan/EVOLUTION_LOG.md", "Legacy evolution log reference -- continuity-only, currently missing locally"),
            ("~/jagat_kalyan/pitches/", "Legacy pitch set reference -- continuity-only, currently missing locally"),
            ("~/.dharma/shared/jk_pulse.md", "JK momentum heartbeat"),
            ("~/.dharma/shared/jk_alert.md", "HIGH URGENCY alerts for morning brief"),
        ],
        "continuity_only_paths": [
            "~/jagat_kalyan/",
            "~/jagat_kalyan/app.py",
            "~/jagat_kalyan/matching.py",
            "~/jagat_kalyan/models.py",
            "~/jagat_kalyan/WELFARE_TONS_SPEC.md",
            "~/jagat_kalyan/anthropic_grant_application.md",
            "~/jagat_kalyan/PARTNER_RESEARCH.md",
            "~/jagat_kalyan/CARBON_ATTRIBUTION_FEASIBILITY.md",
            "~/jagat_kalyan/SCOUT_LOG.md",
            "~/jagat_kalyan/EVOLUTION_LOG.md",
            "~/jagat_kalyan/pitches/",
        ],
    },
    "foundations": {
        "description": "Intellectual pillars -- 10 thinkers, syntheses, architecture principles",
        "paths": [
            ("~/dharma_swarm/foundations/INDEX.md", "Pillar index with domain mapping"),
            ("~/dharma_swarm/foundations/META_SYNTHESIS.md", "All pillars unified -- 5 convergence axes"),
            ("~/dharma_swarm/foundations/PILLAR_01_LEVIN.md", "Multi-scale cognition, cognitive light cone"),
            ("~/dharma_swarm/foundations/PILLAR_02_KAUFFMAN.md", "Adjacent possible, autocatalytic sets"),
            ("~/dharma_swarm/foundations/PILLAR_03_JANTSCH.md", "Self-organizing universe, dissipative structures"),
            ("~/dharma_swarm/foundations/PILLAR_05_DEACON.md", "Absential causation, autogenesis"),
            ("~/dharma_swarm/foundations/PILLAR_06_FRISTON.md", "Free energy principle, active inference"),
            ("~/dharma_swarm/foundations/PILLAR_07_HOFSTADTER.md", "Strange loops, tangled hierarchies"),
            ("~/dharma_swarm/foundations/PILLAR_08_AUROBINDO.md", "Supramental descent, Overmind Error"),
            ("~/dharma_swarm/foundations/PILLAR_09_DADA_BHAGWAN.md", "Witness architecture, karma mechanics"),
            ("~/dharma_swarm/foundations/PILLAR_10_VARELA.md", "Autopoiesis, enactive cognition"),
            ("~/dharma_swarm/foundations/PILLAR_11_BEER.md", "Viable System Model, requisite variety"),
            ("~/dharma_swarm/foundations/FOUNDATIONS_SYNTHESIS.md", "Levin-Kauffman-Jantsch lattice"),
            ("~/dharma_swarm/foundations/SYNTHESIS_DEACON_FRISTON.md", "Absential causation meets active inference"),
            ("~/dharma_swarm/architecture/PRINCIPLES.md", "11 engineering principles traced to pillars"),
        ],
    },
    "telos_engine": {
        "description": "Telos Engine vision and strategy research -- civilization-scale AI",
        "paths": [
            ("~/dharma_swarm/docs/telos-engine/INDEX.md", "Research document index"),
            ("~/dharma_swarm/docs/telos-engine/01_SATTVA_VISION.md", "What conscious AI actually does"),
            ("~/dharma_swarm/docs/telos-engine/02_COMPETITIVE_ANALYSIS.md", "10D chess vs AI giants"),
            ("~/dharma_swarm/docs/telos-engine/03_SELF_EVOLVING_ARCH.md", "Agent-building-agents architecture"),
            ("~/dharma_swarm/docs/telos-engine/04_MEMETIC_ENGINEERING.md", "12 principles of dharmic memetics"),
            ("~/dharma_swarm/docs/telos-engine/05_PLATFORM_SPAWNING.md", "Triple governance, spawning protocol"),
            ("~/dharma_swarm/docs/telos-engine/06_AI_ZEITGEIST.md", "March 2026 field intelligence"),
            ("~/dharma_swarm/docs/telos-engine/07_VSM_GOVERNANCE.md", "Beer VSM mapping, 5 gaps"),
            ("~/dharma_swarm/docs/telos-engine/08_SATTVA_ECONOMICS.md", "Welfare-ton numbers, 10-year arc"),
            ("~/dharma_swarm/docs/telos-engine/09_WHERE_IT_SITS.md", "Option F analysis -- everything inside dharma_swarm"),
        ],
    },
}


def get_context_for(domain: str) -> str:
    """Generate context string for a specific domain.

    Args:
        domain: One of the ECOSYSTEM keys, or "all" for everything.

    Returns:
        Formatted string with path existence checks and descriptions.
    """
    if domain == "all":
        domains = list(ECOSYSTEM.keys())
    elif domain in ECOSYSTEM:
        domains = [domain]
    else:
        return f"Unknown domain: {domain}. Available: {', '.join(ECOSYSTEM.keys())}"

    parts = [f"# Dhyana's Filesystem -- {domain.upper()} Context\n"]
    parts.append(f"Generated: {datetime.now().isoformat()[:19]}\n")

    for d in domains:
        info = ECOSYSTEM[d]
        parts.append(f"\n## {d.upper()}: {info['description']}")
        authority_note = info.get("authority_note")
        if authority_note:
            parts.append(f"  Authority: {authority_note}")
        for path_str, desc in info["paths"]:
            path = Path(path_str).expanduser()
            exists = path.exists()
            marker = "OK" if exists else "MISSING"
            parts.append(f"  [{marker}] {path_str}")
            parts.append(f"         {desc}")

    return "\n".join(parts)


def check_health() -> dict[str, int | dict[str, str]]:
    """Check which ecosystem paths exist and which are missing.

    Returns:
        Dict with 'ok' count, 'missing' count, and 'details' of missing paths.
        Adds 'stale_authority' and 'authority_details' for missing continuity-only
        references that should not be treated as live execution authority.
    """
    ok = 0
    missing = 0
    stale_authority = 0
    details: dict[str, str] = {}
    authority_details: dict[str, str] = {}
    for _domain, info in ECOSYSTEM.items():
        continuity_only = set(info.get("continuity_only_paths", []))
        for path_str, desc in info["paths"]:
            path = Path(path_str).expanduser()
            if path.exists():
                ok += 1
            else:
                missing += 1
                details[path_str] = f"MISSING -- {desc}"
                if path_str in continuity_only:
                    stale_authority += 1
                    authority_details[path_str] = f"CONTINUITY_ONLY -- {desc}"
    return {
        "ok": ok,
        "missing": missing,
        "details": details,
        "stale_authority": stale_authority,
        "authority_details": authority_details,
    }


if __name__ == "__main__":
    import sys

    domain = sys.argv[1] if len(sys.argv) > 1 else "all"

    if domain == "health":
        h = check_health()
        print(f"Ecosystem: {h['ok']} OK, {h['missing']} MISSING")
        details = h["details"]
        assert isinstance(details, dict)
        for p, d in details.items():
            print(f"  {d}: {p}")
    else:
        print(get_context_for(domain))
