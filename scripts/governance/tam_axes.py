#!/usr/bin/env python3
"""tam_axes.py — the frozen capability axes for the TAM Company-Builder Parity board.

DATA ONLY. Logic (validation, lane assignment, parity math, receipt, replay
check) lives in scripts/governance/tam_ledger.py. Every "ours" cell cites a
repo owner; every competitor cell cites a public source URL with a
verification label per the NORTH_STAR §5 source-pending rule. Competitor
facts are a dated snapshot (2026-06-10 world triangulation); refreshing them
is an explicit next-item, never silently assumed current.
"""

from __future__ import annotations

from typing import Any

BASELINE = (
    "Polsia (polsia.com) + Cofounder (cofounder.co) — 2026-06-10 world "
    "triangulation (reports/anatomy_altitude_2026-06-10/lane_F_world.md) "
    "refreshed 2026-07-07 by the adversarially-verified blueprint/genealogy "
    "dossier (docs/research/POLSIA_COFOUNDER_BLUEPRINT_GENEALOGY_2026-07-07.md; "
    "20 confirmed / 5 refuted claims — incl. the retired 4.4x ARR-gap framing)"
)

_DOSSIER = "docs/research/POLSIA_COFOUNDER_BLUEPRINT_GENEALOGY_2026-07-07.md"

_LANE_F = "reports/anatomy_altitude_2026-06-10/lane_F_world.md"
_COFOUNDER = ("https://cofounder.co",)
_POLSIA = ("https://polsia.com/",)


def _row(key: str, capability: str, *, ours: str, ours_owner: str,
         ours_note: str = "", comp_name: str, comp: str, comp_claim: str,
         sources: tuple[str, ...], verification: str,
         exceed_cite: str = "") -> dict[str, Any]:
    return {
        "key": key, "capability": capability,
        "ours_status": ours, "ours_owner": ours_owner, "ours_note": ours_note,
        "comp_name": comp_name, "comp_status": comp, "comp_claim": comp_claim,
        "comp_sources": list(sources), "comp_verification": verification,
        "structural_exceed_cite": exceed_cite,
    }


def axes() -> list[dict[str, Any]]:
    """Fresh copies of the frozen axis rows (callers may annotate them)."""
    return [
        _row("org_orchestration",
             "Org-shaped multi-agent orchestration (departments, roster, routing)",
             ours="WIRED_BUT_DORMANT",
             ours_owner=f"dharma_swarm/orchestrator.py + dharma_swarm/spine/invoke.py ({_LANE_F}:21)",
             ours_note="deeper than the department metaphor, but live spine-dispatch "
                       "persistence on the daemon host is still operator-pending "
                       "(organism-rewire-2026-07 D1)",
             comp_name="Cofounder", comp="CLAIMED",
             comp_claim="departmentalized agents (Engineering/Sales/Marketing/...) with "
                        "managers and shared context ('superoptimizer' doctrine; engine "
                        "internals UNKNOWN). Polsia's verified equivalent is shallower: "
                        "scheduled Claude-CLI subprocesses, orchestrator itself just one "
                        f"scheduled agent ({_DOSSIER} §2)",
             sources=_COFOUNDER + ("https://github.com/PolsiaAI/Polsia",),
             verification="vendor-claim"),
        _row("hitl_approval",
             "Exception-based human-in-the-loop approval of dangerous actions",
             ours="RUNS",
             ours_owner=f"dharma_swarm/telos_gates.py + evolution gate PEP ({_LANE_F}:22)",
             comp_name="Cofounder", comp="CLAIMED",
             comp_claim="approval required when potentially dangerous actions are taken",
             sources=_COFOUNDER, verification="vendor-claim"),
        _row("typed_gate_audit",
             "Typed, witnessed decision gates (auditable approval records)",
             ours="RUNS",
             ours_owner="dharma_swarm/telos_gates.py (GateRegistry/TelosGatekeeper) "
                        f"+ ~/.dharma/witness/ ({_LANE_F}:28)",
             comp_name="Cofounder", comp="CLAIMED",
             comp_claim="'potentially dangerous' vibes-based approval; no typed or "
                        "witnessed decision record published",
             sources=_COFOUNDER, verification="vendor-claim",
             exceed_cite=f"{_LANE_F}:28 — 'auditable in a way Cofounder structurally is not'"),
        _row("customer_execution",
             "Customer-facing execution (inbox warming, outbound, Stripe, support)",
             ours="ABSENT",
             ours_owner=f"clean negative — {_LANE_F}:25 (venture_cell/ holds only darshan/ + operator_os/)",
             comp_name="Cofounder", comp="CLAIMED",
             comp_claim="inbox warming, outbound, paid marketing, Stripe, support automation",
             sources=_COFOUNDER, verification="vendor-claim"),
        _row("gtm_scaffold",
             "Go-to-market milestone scaffold (incorporation -> product -> sales -> scale)",
             ours="ABSENT",
             ours_owner=f"clean negative — {_LANE_F}:26 (no staged GTM state machine in the repo)",
             comp_name="Cofounder", comp="CLAIMED",
             comp_claim="milestone scaffold from incorporation to scale",
             sources=_COFOUNDER, verification="vendor-claim"),
        _row("extensibility",
             "Extensibility: MCP, custom APIs, skills, custom codebase",
             ours="RUNS",
             ours_owner="dharma_swarm/skills.py (SkillRegistry) + the four tracked "
                        "skill registries (CLAUDE.md §Skills & Agent Role Registries)",
             comp_name="Cofounder", comp="CLAIMED",
             comp_claim="connect MCP, custom APIs, custom skills, or an entire custom codebase",
             sources=_COFOUNDER, verification="vendor-claim"),
        _row("pricing_billing",
             "Public pricing + billing surface (revenue-share alignment)",
             ours="ABSENT",
             ours_owner=f"clean negative — {_LANE_F}:42 (no billing surface, customer object, or funnel)",
             comp_name="Polsia", comp="SHIPPED",
             comp_claim="$49/mo + 20% revenue share, publicly priced",
             sources=_POLSIA + (
                 "https://www.contextstudios.ai/blog/polsia-how-a-solo-founder-hit-1m-arr-in-30-days-with-ai-agents",),
             verification="vendor-claim"),
        _row("distribution_arr",
             "Distribution, paying customers, ARR",
             ours="ABSENT",
             ours_owner=f"$0 revenue across every economic surface — {_LANE_F}:199 "
                        "(clean negative #1); docs/governance/VENTURE_CELL_PORTFOLIO.yaml revenue_usd: 0",
             comp_name="Polsia", comp="CLAIMED",
             comp_claim="~$10M 'ARR' claimed around the $30M raise at $250M (round "
                        "itself verified). 36kr decomposition: ~$4.6M true "
                        "subscription ARR (~7,600 x $49/mo) + ~$2M one-time task "
                        "packages + ~$2M pass-through ad spend counted as revenue "
                        "(~2.2x headline-vs-recurring); best-case customer company "
                        "~$50/mo gross MRR; all figures founder-dominated, no "
                        "independent audit. (Prior 4.4x-gap framing REFUTED "
                        f"2026-07-07 — see {_DOSSIER} §5)",
             sources=("https://eu.36kr.com/en/p/3825813697565316",
                      "https://gtmnow.com/gtm-192-inside-the-company-that-raised-30m-at-a-250m-valuation-with-0-employees-ben-cera-polsia/",
                      "https://en.ain.ua/2026/05/25/ai-startup-polsia-with-no-employees-raised-30m-in-funding/"),
             verification="source-pending"),
        _row("e2e_company",
             "End-to-end company operation by agents (research -> code -> ads -> support -> sales)",
             ours="ASPIRATION",
             ours_owner="docs/governance/VENTURE_CELL_PORTFOLIO.yaml (live cell "
                        "statuses read at render time; see portfolio_live_read)",
             ours_note="one externally-serving publication cell; no full-company loop",
             comp_name="Polsia", comp="CLAIMED",
             comp_claim="nine AI agents end-to-end (research, code, ads, support, sales)",
             sources=_POLSIA, verification="vendor-claim"),
        _row("honest_arr",
             "Verifiable (receipted) revenue — 'honest ARR' a third party can check",
             ours="WIRED_BUT_DORMANT",
             ours_owner="dharma_swarm/spine/receipt.py (EvidenceReceipt) RUNS at the "
                        f"dispatch chokepoint; $0 receipted revenue to date ({_LANE_F}:28,44)",
             ours_note="THE HEADLINE DIFFERENTIATOR: incumbents structurally cannot "
                       "publish receipted revenue without exposing their claims gap; "
                       "unrealized until real dollars flow through the receipt spine",
             comp_name="Polsia + Cofounder", comp="ABSENT",
             comp_claim="no incumbent publishes third-party-verifiable revenue — "
                        "confirmed 2026-07-07: Polsia's figures are founder-dominated "
                        "and decomposition-disputed (36kr: ~$10M claimed vs ~$4.6M "
                        "true subscription ARR), Cofounder publishes none; no audit "
                        f"of any incumbent figure exists ({_DOSSIER} §4-5)",
             sources=("https://eu.36kr.com/en/p/3825813697565316",
                      "https://github.com/PolsiaAI/Polsia"),
             verification="third-party-report"),
        _row("self_evolution",
             "Governed self-evolution of the operating substrate (DGM-class)",
             ours="WIRED_BUT_DORMANT",
             ours_owner="dharma_swarm/evolution.py + dgm_loop.py — 'Semi-working / "
                        "dangerous overclaim risk' (reports/swarm_genome/2026-06-11/"
                        "SYNTHESIS.md §Organ Health Table)",
             comp_name="Polsia + Cofounder", comp="ABSENT",
             comp_claim="no public evidence either system self-modifies its own "
                        f"substrate under governance (public surfaces checked 2026-06-10, {_LANE_F})",
             sources=_COFOUNDER + _POLSIA, verification="vendor-claim"),
        _row("internal_architecture",
             "Substrate architecture depth (orchestration engine, durability, memory)",
             ours="RUNS",
             ours_owner="repo-inspectable: 770+ modules (python3 xray.py), spine "
                        "receipts, crash-resume graph engine lane (dharmagraph track), "
                        "docs/architecture/NAVIGATION.md",
             ours_note="was UNMEASURED until 2026-07-07: Polsia's own GitHub dump made "
                       "the competitor cell citable (measurement improved, not us)",
             comp_name="Polsia + Cofounder", comp="CLAIMED",
             comp_claim="Polsia (repo self-description, one-shot 2-commit dump, core "
                        "app/ package missing, production parity unproven): nine agents "
                        "shelling out to Claude Code CLI on Celery Beat schedules over "
                        "Next.js/FastAPI/PostgreSQL/Redis/ChromaDB — commodity assembly, "
                        "no framework or Temporal-class durability. Cofounder: "
                        "'superoptimizer' departments + MemGPT-lineage 3-tier memory "
                        f"(vendor doctrine; engine internals UNKNOWN). {_DOSSIER} §2-4",
             sources=("https://github.com/PolsiaAI/Polsia",
                      "https://www.generalintelligencecompany.com/writing/introducing-cofounder-our-state-of-the-art-memory-system-in-an-agent"),
             verification="vendor-claim"),
    ]
