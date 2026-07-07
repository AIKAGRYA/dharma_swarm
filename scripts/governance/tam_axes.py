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
    "Polsia (polsia.com) + Cofounder (cofounder.co) — public data snapshot "
    "2026-06-10, reports/anatomy_altitude_2026-06-10/lane_F_world.md; refresh "
    "of competitor facts is an open next-item, not silently assumed current"
)

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
             comp_claim="departmentalized agents (Engineering/Sales/Marketing/...) "
                        "with managers and shared context",
             sources=_COFOUNDER, verification="vendor-claim"),
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
             comp_claim="~$10M ARR claimed 5 months post-launch, 7,600 customers, 85% "
                        "month-2 retention — unverified, and a 4.4x claimed-vs-actual "
                        "gap is documented (claimed $3M+ vs $689K run-rate)",
             sources=("https://en.ain.ua/2026/05/25/ai-startup-polsia-with-no-employees-raised-30m-in-funding/",
                      "https://aiweekly.co/alerts/polsia-solo-founder-raises-30m-at-250m-valuation",
                      "https://zilla.so/blog/polsia-review"),
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
             comp_claim="no incumbent publishes third-party-verifiable revenue; "
                        "Polsia's documented 4.4x claimed-vs-actual ARR gap shows why "
                        "they cannot",
             sources=("https://zilla.so/blog/polsia-review",),
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
             "Competitor internal architecture quality / production reliability",
             ours="RUNS",
             ours_owner="repo-inspectable: 770+ modules (python3 xray.py), test suite, "
                        "docs/architecture/NAVIGATION.md",
             comp_name="Polsia + Cofounder", comp="UNKNOWN",
             comp_claim=f"SPECULATIVE — neither publishes architecture ({_LANE_F}:18,204); "
                        "no citable claim exists, so this row is UNMEASURED, not guessed",
             sources=(), verification="unverifiable"),
    ]
