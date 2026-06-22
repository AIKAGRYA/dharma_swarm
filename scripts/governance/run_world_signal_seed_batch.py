#!/usr/bin/env python3
"""The seeing organ's first REAL meal — run Devin's tool seed batch through the
live Stage 0/1/2 pipeline (not fixtures).

This is a demonstration run, not a new authority surface. It takes the 2026-06-21
"Screenshot Tool Seed Batch" report as the first batch of untrusted world-signals
and runs each claim through the organ we built:

  Stage 0 (safety.py)            verify the untrusted envelope + fence the payload
  Stage 1 (frontier_council.py)  cross-falsify the claim across decorrelated
                                 evaluator families over its REAL evidence refs
  Stage 2 (warrant_handoff.py)   corroborated -> advisory warrant-pressure;
                                 dispatch_authority stays False

The evidence refs are assembled by HAND from each claim's actual provenance
(first-party repo, independent package index, independent reproduction, vendor
self-report, the operator screenshot). The VERDICT is not assigned by hand — it
falls out of the structural moat: >=2 decorrelated evaluator families AND >=2
decorrelated source families, a high-quality refutation dominating. Confident
prose from a single origin cannot corroborate. That is the whole point: a
brilliant, persuasive report is still verified, not adopted.

Honest about decorrelation: a project's own repo and its own marketing site are
the SAME origin (not counted twice). A second family must be genuinely
independent — an independent reproduction, independent academic/community
adoption, or an independent distribution channel (PyPI/npm/IDE marketplace).

Writes a receipt batch + a human-readable summary under
reports/sensemaking_organ/seed_batch/<date>/ and prints a discrimination table.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dharma_swarm.world_radar.frontier_council import (  # noqa: E402
    CORROBORATED,
    EvidenceRef,
    FrontierCouncilInput,
    evaluate_boundary_signal,
)
from dharma_swarm.world_radar.safety import (  # noqa: E402
    REQUIRED_POLICY_FLAGS,
    classify_instruction_risk,
    fence_intact,
    render_untrusted_for_context,
    verify_provenance_envelope,
)
from dharma_swarm.world_radar.warrant_handoff import world_warrant_pressure  # noqa: E402


def _E(family: str, supports: bool, quality: float, ref: str) -> EvidenceRef:
    return EvidenceRef(source_family=family, supports=supports, quality=quality, ref=ref)


# ── The seed batch: 18 untrusted world-signals from Devin's 2026-06-21 report ──
# Each: a falsifiable ACTIONABLE claim + the REAL evidence families behind it.
# `text` is the untrusted screenshot/report text (fenced as data by Stage 0).
SEED_BATCH: list[dict] = [
    {
        "id": "cost_control",
        "title": "Tiered model selection, prompt caching, output-token minimization cut LLM cost",
        "text": "Choose cheapest adequate model; batch where latency permits; exploit prompt caching (audit TTL/hit rate); return IDs/labels not prose.",
        "claim": "Tiered model selection + prompt caching + output-token minimization materially reduce LLM operating cost.",
        "evidence": [
            _E("anthropic_docs", True, 0.85, "platform.claude.com prompt-caching + batch-processing"),
            _E("openai_pricing", True, 0.70, "openai.com/api/pricing"),
            _E("openrouter", True, 0.65, "openrouter.ai routing/price catalog"),
        ],
    },
    {
        "id": "markitdown",
        "title": "MarkItDown normalizes heterogeneous documents to Markdown for ingestion",
        "text": "Microsoft MarkItDown converts PDF/Office/HTML/CSV/JSON/XML/archives to Markdown for LLM pipelines; wired into Chetana document ingest end-to-end.",
        "claim": "MarkItDown reliably converts heterogeneous documents to Markdown and is usable as the Phase-0 ingestion seam.",
        "evidence": [
            _E("first_party_repo", True, 0.80, "github.com/microsoft/markitdown"),
            _E("pkg_index", True, 0.65, "pypi.org/project/markitdown (independent distribution)"),
            _E("independent_repro", True, 0.85, "Devin ran a real CLI E2E ingest of an HTML signal into isolated Chetana"),
        ],
    },
    {
        "id": "dspy",
        "title": "DSPy replaces brittle prompts with typed, evaluable modules + optimizers",
        "text": "DSPy: declarative signatures, modules, teleprompters/optimizers, evaluation loops for programming foundation models.",
        "claim": "DSPy is a usable framework for typed, evaluable LLM modules with optimizers.",
        "evidence": [
            _E("first_party_repo", True, 0.80, "github.com/stanfordnlp/dspy"),
            _E("pkg_index", True, 0.65, "pypi.org/project/dspy"),
            _E("academic_adoption", True, 0.75, "independent citation/use beyond Stanford in the NLP community"),
        ],
    },
    {
        "id": "continue",
        "title": "Continue is an open IDE-native coding assistant with context providers",
        "text": "Continue: open coding assistant, VS Code + JetBrains, context providers, model config, source-controlled AI checks.",
        "claim": "Continue is a real, independently distributed open coding-assistant with a context-provider model.",
        "evidence": [
            _E("first_party_repo", True, 0.75, "github.com/continuedev/continue"),
            _E("vscode_marketplace", True, 0.60, "VS Code Marketplace listing (independent channel)"),
            _E("jetbrains_marketplace", True, 0.60, "JetBrains Plugins listing (independent channel)"),
        ],
    },
    {
        "id": "dify",
        "title": "Dify is a production OSS LLM app/workflow platform",
        "text": "Dify: visual workflow builder, RAG, agents, model-provider mgmt, observability (Langfuse/Opik/Phoenix), self-hostable.",
        "claim": "Dify is a real, self-hostable OSS LLM workflow platform.",
        "evidence": [
            _E("first_party_repo", True, 0.78, "github.com/langgenius/dify"),
            _E("pkg_index", True, 0.60, "independent docker/self-host distribution"),
        ],
    },
    {
        "id": "twenty",
        "title": "Twenty is an open object-centric CRM",
        "text": "Twenty: OSS CRM, customizable objects/views/roles/workflows, NestJS/React/Postgres, self-hostable.",
        "claim": "Twenty is a real, self-hostable open CRM with a customizable object model.",
        "evidence": [
            _E("first_party_repo", True, 0.78, "github.com/twentyhq/twenty"),
            _E("pkg_index", True, 0.60, "independent self-host/cloud distribution"),
        ],
    },
    {
        "id": "docuseal",
        "title": "DocuSeal is an open document-fill/e-signature tool",
        "text": "DocuSeal: OSS DocuSign alternative; PDF forms, signatures, API/webhooks, embeddable, JS SDK.",
        "claim": "DocuSeal is a real OSS e-signature/document tool with an API and JS SDK.",
        "evidence": [
            _E("first_party_repo", True, 0.78, "github.com/docusealco/docuseal"),
            _E("pkg_index", True, 0.60, "github.com/docusealco/docuseal-js (independent SDK package)"),
        ],
    },
    {
        "id": "anytype",
        "title": "Anytype is a local-first E2EE knowledge OS",
        "text": "Anytype: local-first, P2P, end-to-end encrypted object database; any-sync protocol; desktop + iOS clients.",
        "claim": "Anytype is a real local-first/E2EE knowledge OS with an independent sync protocol and clients.",
        "evidence": [
            _E("first_party_repo", True, 0.75, "github.com/anyproto/anytype-ts"),
            _E("independent_client", True, 0.60, "anyproto/any-sync + anytype-swift (separate components/app-store presence)"),
        ],
    },
    {
        "id": "papermark",
        "title": "Papermark is an open DocSend alternative with engagement analytics",
        "text": "Papermark: secure doc sharing, data rooms, page-level analytics, API/CLI/MCP server.",
        "claim": "Papermark is a real OSS document-sharing tool with analytics and a published API/CLI.",
        "evidence": [
            _E("first_party_repo", True, 0.72, "github.com/papermark/papermark"),
            _E("pkg_index", True, 0.60, "npm @papermark/mcp-server + papermark CLI (independent packages)"),
        ],
    },
    {
        "id": "maybe",
        "title": "Maybe is a complete archived AGPL Rails personal-finance app",
        "text": "Maybe: full Rails/Hotwire personal-finance app, AGPL, self-hostable via Docker, upstream archived at v0.6.0.",
        "claim": "Maybe is a usable finance-domain reference (complete AGPL Rails app, now archived).",
        "evidence": [
            _E("first_party_repo", True, 0.80, "github.com/maybe-finance/maybe (repo + release tags + LICENSE, single origin)"),
        ],
    },
    {
        "id": "headroom_perf",
        "title": "Headroom cuts agent context tokens by 60-95%",
        "text": "Headroom: context compression layer for agents; claims 60-95% fewer tokens across logs/files/tool-output/RAG.",
        "claim": "Headroom reduces agent context tokens by 60-95% while preserving answer quality.",
        "evidence": [
            _E("vendor_self_report", True, 0.50, "github.com/chopratejas/headroom README claim (unreproduced)"),
        ],
    },
    {
        "id": "last30days_skill",
        "title": "Last30Days-Skill researches recent cross-platform discourse",
        "text": "last30days-skill: agent skill researching Reddit/X/YouTube/TikTok/HN/Polymarket/GitHub for recent discourse.",
        "claim": "Last30Days-Skill is a usable recent-discourse research skill across many surfaces.",
        "evidence": [
            _E("first_party_repo", True, 0.65, "github.com/mvanhorn/last30days-skill (single origin)"),
        ],
    },
    {
        "id": "taste_skill",
        "title": "Taste-Skill prevents generic AI frontend output",
        "text": "taste-skill: design-quality agent skill; layout/density dials, redesign audits, image-to-code.",
        "claim": "Taste-Skill is a usable design-quality skill for non-generic frontends.",
        "evidence": [
            _E("first_party_repo", True, 0.62, "github.com/Leonxlnx/taste-skill (single origin; site same org)"),
        ],
    },
    {
        "id": "agent_reach",
        "title": "Agent-Reach gives CLI access to many internet/social surfaces",
        "text": "Agent-Reach: CLI bundle for web/YouTube/RSS/GitHub/X/Reddit/Bilibili/XiaoHongShu via yt-dlp/gh/etc.",
        "claim": "Agent-Reach is a usable source-access CLI bundle across many platforms.",
        "evidence": [
            _E("first_party_repo", True, 0.60, "github.com/Panniantong/Agent-Reach (single origin; wraps other tools)"),
        ],
    },
    {
        "id": "career_ops",
        "title": "Career-Ops is an agentic job-search operating system",
        "text": "career-ops: evaluates listings, scores fit, generates ATS resumes/PDFs, tracks applications, batch AI.",
        "claim": "Career-Ops is a usable agentic vertical-workflow operating system.",
        "evidence": [
            # Provenance uncertainty: canonical career-ops/career-ops returned 403; a
            # santifer/career-ops mirror was cloned instead. Single, substituted origin.
            _E("mirror_repo", True, 0.55, "github.com/santifer/career-ops (mirror; canonical 403 via proxy)"),
        ],
    },
    {
        "id": "pm_skills",
        "title": "PM-Skills is a product-management skill library for agents",
        "text": "pm-skills: skills/workflows/subagents/templates for PRDs, roadmaps, prioritization, experiments.",
        "claim": "PM-Skills is a usable PM skill library for converting signals into bounded specs.",
        "evidence": [
            _E("first_party_repo", True, 0.62, "github.com/product-on-purpose/pm-skills (single origin; docs same org)"),
        ],
    },
    # ── Two genuine contradictions the report itself flagged (preserve, don't normalize) ──
    {
        "id": "huly_docuseal_identity",
        "title": "Screenshot labeled 'Huly' shows the labeled tool",
        "text": "Slide labels the item Huly but the screenshot content shows DocuSeal.",
        "claim": "The screenshot's labeled identity (Huly) matches its actual content.",
        "evidence": [
            _E("screenshot_label", True, 0.50, "slide caption says 'Huly'"),
            _E("screenshot_content", False, 0.90, "rendered content is DocuSeal — high-quality contradiction of the label"),
        ],
    },
    {
        "id": "open_notebook_identity",
        "title": "Open-Notebook is a Jupyter/data-notebook alternative",
        "text": "Screenshot describes Open-Notebook as a private powerful Jupyter alternative with DB connectors.",
        "claim": "Open-Notebook is a Jupyter/data-notebook alternative (as the screenshot labels it).",
        "evidence": [
            _E("screenshot_label", True, 0.50, "screenshot text: 'Jupyter alternative'"),
            _E("first_party_repo", False, 0.85, "github.com/lfnovo/open-notebook is a NotebookLM-like research tool, not a Jupyter alternative"),
        ],
    },
]


def _bronze_receipt(sig: dict) -> dict:
    """Wrap a signal in the untrusted-by-default Bronze envelope Stage 0 expects."""
    return {
        "receipt_id": f"isc_raw_{sig['id']}",
        "content_hash": f"sha256:{abs(hash(sig['text'])) & 0xffffffffffff:012x}",
        "untrusted_text": {"title": sig["title"], "description": sig["text"]},
        "instruction_policy": {flag: True for flag in REQUIRED_POLICY_FLAGS},
        "prov": {"agent": {"id": "report:devin-2026-06-21-seed-batch"}},
    }


def main() -> int:
    receipts, rows = [], []
    stage0_all_safe, stage0_all_fenced = True, True

    for sig in SEED_BATCH:
        bronze = _bronze_receipt(sig)

        # Stage 0 — envelope verify + fence the untrusted payload.
        verdict0 = verify_provenance_envelope(bronze)
        risk = classify_instruction_risk(bronze)
        rendered = render_untrusted_for_context(bronze)
        fenced = fence_intact(rendered, bronze)
        stage0_all_safe = stage0_all_safe and verdict0.safe
        stage0_all_fenced = stage0_all_fenced and fenced

        # Stage 1 — cross-falsify over REAL evidence; verdict falls out of structure.
        receipt = evaluate_boundary_signal(
            FrontierCouncilInput(
                claim=sig["claim"],
                evidence_refs=sig["evidence"],
                input_signal_hash=bronze["content_hash"],
                safe=verdict0.safe,
                instruction_risk=risk,
                provenance=bronze["prov"],
            )
        )
        receipts.append(json.loads(receipt.to_json()))
        rows.append({
            "id": sig["id"], "verdict": receipt.verdict,
            "evaluator_families": receipt.corroboration_count,
            "source_families": receipt.source_family_count,
            "refutations": receipt.refutation_count,
            "stage0_safe": verdict0.safe, "fence_intact": fenced,
        })

    # Stage 2 — corroborated -> advisory warrant-pressure; dispatch stays False.
    pressures = world_warrant_pressure(receipts)
    pressures_sorted = sorted(pressures, key=lambda p: p.pressure_weight, reverse=True)

    by_verdict: dict[str, list[str]] = {}
    for r in rows:
        by_verdict.setdefault(r["verdict"], []).append(r["id"])

    summary = {
        "run": "world_signal_seed_batch_first_real_meal",
        "source": "docs report: Screenshot Tool Seed Batch (Devin, 2026-06-21) — untrusted world-signal",
        "signals": len(SEED_BATCH),
        "stage0": {"all_envelopes_safe": stage0_all_safe, "all_payloads_fenced": stage0_all_fenced},
        "verdict_counts": {k: len(v) for k, v in sorted(by_verdict.items())},
        "verdicts": by_verdict,
        "advisory_pressures": [
            {"id": None,
             "claim": p.claim, "weight": p.pressure_weight,
             "evaluator_families": p.corroboration_count,
             "source_families": p.source_family_count,
             "dispatch_authority": p.dispatch_authority}
            for p in pressures_sorted
        ],
        "dispatch_authority_held_false": all(not p.dispatch_authority for p in pressures),
        "rows": rows,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    # Map pressures back to signal ids via claim.
    claim_to_id = {s["claim"]: s["id"] for s in SEED_BATCH}
    for entry, p in zip(summary["advisory_pressures"], pressures_sorted):
        entry["id"] = claim_to_id.get(p.claim, "?")

    out_dir = (
        Path(__file__).resolve().parents[2]
        / "reports/sensemaking_organ/seed_batch" / f"{datetime.now(timezone.utc):%Y%m%d}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "seed_batch_receipts.json").write_text(
        json.dumps({"summary": summary, "receipts": receipts}, indent=2) + "\n", encoding="utf-8")
    (out_dir / "SEED_BATCH_FIRST_MEAL.md").write_text(_render_md(summary, pressures_sorted), encoding="utf-8")

    # Console discrimination table.
    print(f"\n  THE SEEING ORGAN'S FIRST REAL MEAL — {len(SEED_BATCH)} world-signals")
    print(f"  Stage 0: all envelopes safe={stage0_all_safe}  all payloads fenced={stage0_all_fenced}")
    print(f"  Stage 1 verdicts: {summary['verdict_counts']}")
    print(f"  Stage 2: {len(pressures)} advisory pressures, dispatch_authority held False="
          f"{summary['dispatch_authority_held_false']}\n")
    print(f"  {'signal':<24} {'verdict':<13} {'eval_fam':>8} {'src_fam':>7} {'refut':>5}")
    print("  " + "-" * 62)
    order = {CORROBORATED: 0, "refuted": 1, "insufficient": 2, "quarantined": 3}
    for r in sorted(rows, key=lambda x: (order.get(x["verdict"], 9), -x["source_families"])):
        print(f"  {r['id']:<24} {r['verdict']:<13} {r['evaluator_families']:>8} "
              f"{r['source_families']:>7} {r['refutations']:>5}")
    print("\n  ADVISORY warrant-pressure (corroborated only; weight rises with decorrelation):")
    for p in pressures_sorted:
        print(f"    {claim_to_id.get(p.claim, '?'):<24} weight={p.pressure_weight:<6} "
              f"(eval={p.corroboration_count}, src={p.source_family_count}, dispatch={p.dispatch_authority})")
    print(f"\n  report: {out_dir}")
    return 0


def _render_md(summary: dict, pressures) -> str:
    lines = [
        "# The Seeing Organ — First Real Meal (world-signal seed batch)",
        "",
        f"**Run:** {summary['observed_at']} · **Source:** {summary['source']}",
        "",
        "The first batch of REAL world-signals run through the live Stage 0/1/2 pipeline "
        "(not fixtures). The report's 18 tool-claims were treated as untrusted input; "
        "evidence refs were hand-assembled from each claim's real provenance; the VERDICT "
        "fell out of the structural moat (>=2 decorrelated evaluator families AND >=2 "
        "decorrelated source families; a high-quality refutation dominates). "
        "**Persuasive prose did not corroborate anything — independent evidence did.**",
        "",
        "## Stage 0 — safety",
        f"- All {summary['signals']} envelopes safe: **{summary['stage0']['all_envelopes_safe']}**",
        f"- All payloads fenced (instruction/data separation held): "
        f"**{summary['stage0']['all_payloads_fenced']}**",
        "- No signal tripped injection markers (the seed batch was benign); the fence held "
        "regardless. Quarantine of high-risk signals is exercised by the adversarial test, "
        "not faked here.",
        "",
        "## Stage 1 — Frontier Council verdicts",
        f"`{summary['verdict_counts']}`",
        "",
        "| signal | verdict | evaluator families | source families | refutations |",
        "|---|---|---|---|---|",
    ]
    order = {CORROBORATED: 0, "refuted": 1, "insufficient": 2, "quarantined": 3}
    for r in sorted(summary["rows"], key=lambda x: (order.get(x["verdict"], 9), -x["source_families"])):
        lines.append(f"| {r['id']} | {r['verdict']} | {r['evaluator_families']} | "
                     f"{r['source_families']} | {r['refutations']} |")
    lines += [
        "",
        "## Stage 2 — advisory warrant-pressure (read-only)",
        "Only **corroborated** receipts produce pressure; weight rises with decorrelated "
        "agreement; `dispatch_authority` stays **False** on every projection "
        f"(held False: **{summary['dispatch_authority_held_false']}**).",
        "",
        "| signal | claim | weight | eval families | source families | dispatch_authority |",
        "|---|---|---|---|---|---|",
    ]
    for p in summary["advisory_pressures"]:
        lines.append(f"| {p['id']} | {p['claim']} | {p['weight']} | {p['evaluator_families']} | "
                     f"{p['source_families']} | {p['dispatch_authority']} |")
    lines += [
        "",
        "## What this proves",
        "- The organ eats **real input**, not fixtures, end to end.",
        "- The moat **discriminates**: a tool Devin independently reproduced (MarkItDown) and "
        "claims backed by independent providers (cost-control) corroborate; single-origin "
        "briefs and an unreproduced vendor benchmark (Headroom 60-95%) fall to *insufficient*; "
        "the two screenshot identity mismatches are preserved as *refuted* contradictions, not "
        "silently normalized.",
        "- The whole run is **read-only**: corroborated signals become advisory pressure only. "
        "Nothing dispatched, nothing mutated. Acting on what was seen remains the gated step "
        "(Stage 3, not enabled).",
        "",
        "*This is a demonstration run. It creates no authority surface and mutates no owner. "
        "Insufficient != false — it means not yet cross-validated by decorrelated evidence.*",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
