"use client";

import { motion } from "framer-motion";
import {
  ArrowRight,
  BadgeCheck,
  DollarSign,
  GitBranch,
  Scale,
  ShieldCheck,
  Target,
  TriangleAlert,
} from "lucide-react";
import { useEmptyQuadrantHypernode } from "@/hooks/useEmptyQuadrantHypernode";
import type { HypernodePayload } from "@/lib/types";
import { colors } from "@/lib/theme";

const metricLabels: Record<string, string> = {
  auto_grade_score: "AutoGrade",
  council_score: "Council",
  provenance_score: "Provenance",
  market_value_score: "Market",
  welfare_score: "Welfare",
};

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export default function EmptyQuadrantHypernodePage() {
  const { hypernode, isLoading, error } = useEmptyQuadrantHypernode();

  if (isLoading) {
    return (
      <div className="glass-panel flex min-h-[520px] items-center justify-center">
        <p className="animate-pulse text-sm text-sumi-600">Loading hypernode...</p>
      </div>
    );
  }

  if (!hypernode || error) {
    return (
      <div className="glass-panel flex min-h-[520px] items-center justify-center">
        <p className="max-w-md text-center text-sm text-status-warn">
          Empty Quadrant hypernode API is not available.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Hero hypernode={hypernode} />
      <QuadrantMap hypernode={hypernode} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <FitnessPanel hypernode={hypernode} />
        <CouncilPanel hypernode={hypernode} />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <RevenuePanel hypernode={hypernode} />
        <ProvenancePanel hypernode={hypernode} />
        <NextActionsPanel hypernode={hypernode} />
      </div>
      <OntologyPanel hypernode={hypernode} />
    </div>
  );
}

function Hero({ hypernode }: { hypernode: HypernodePayload }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="overflow-hidden rounded-lg border border-aozora/20 bg-sumi-900/70"
    >
      <div className="grid gap-0 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="space-y-5 p-6 md:p-8">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded border border-kinpaku/30 px-2 py-1 font-mono text-[10px] uppercase text-kinpaku">
              Hypernode #1
            </span>
            <span className="rounded border border-aozora/30 px-2 py-1 font-mono text-[10px] uppercase text-aozora">
              {hypernode.fitness_vector.promotion_state.replace(/_/g, " ")}
            </span>
          </div>
          <div>
            <h1 className="glow-aozora font-heading text-3xl font-bold text-aozora md:text-4xl">
              {hypernode.title}
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-torinoko/80">
              {hypernode.thesis}
            </p>
          </div>
        </div>
        <div className="grid min-h-[260px] place-items-center border-t border-sumi-700/40 bg-sumi-950/70 p-6 lg:border-l lg:border-t-0">
          <div className="relative aspect-square w-full max-w-[320px]">
            <div className="absolute inset-0 rounded-full border border-aozora/25" />
            <div className="absolute inset-[14%] rounded-full border border-kinpaku/25" />
            <div className="absolute left-1/2 top-0 h-full w-px bg-sumi-700/70" />
            <div className="absolute left-0 top-1/2 h-px w-full bg-sumi-700/70" />
            <div className="absolute right-[9%] top-[8%] flex h-24 w-24 items-center justify-center rounded-full border border-aozora/50 bg-aozora/10 text-center text-xs font-semibold text-aozora shadow-[0_0_28px_rgba(79,209,217,0.18)]">
              Empty quadrant
            </div>
            <div className="absolute bottom-[9%] left-[9%] text-[10px] uppercase text-sumi-600">
              governance
            </div>
            <div className="absolute right-[8%] top-1/2 text-[10px] uppercase text-sumi-600">
              welfare
            </div>
          </div>
        </div>
      </div>
    </motion.section>
  );
}

function QuadrantMap({ hypernode }: { hypernode: HypernodePayload }) {
  return (
    <section className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {hypernode.quadrant_map.map((quadrant) => {
        const active = quadrant.id === "high-governance-welfare";
        return (
          <div
            key={quadrant.id}
            className={`rounded-lg border p-4 ${
              active
                ? "border-aozora/45 bg-aozora/10"
                : "border-sumi-700/40 bg-sumi-900/60"
            }`}
          >
            <div className="flex items-start gap-3">
              {active ? (
                <ShieldCheck className="mt-0.5 text-aozora" size={18} />
              ) : (
                <Scale className="mt-0.5 text-sumi-600" size={18} />
              )}
              <div className="min-w-0">
                <p className={`font-heading text-sm font-semibold ${active ? "text-aozora" : "text-torinoko"}`}>
                  {quadrant.label}
                </p>
                <p className="mt-1 text-xs uppercase text-sumi-600">
                  {quadrant.governance} / {quadrant.orientation}
                </p>
                <p className="mt-2 text-sm leading-5 text-torinoko/75">
                  {quadrant.description}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </section>
  );
}

function FitnessPanel({ hypernode }: { hypernode: HypernodePayload }) {
  const fitness = hypernode.fitness_vector;
  const metrics = [
    "auto_grade_score",
    "council_score",
    "provenance_score",
    "market_value_score",
    "welfare_score",
  ] as const;

  return (
    <section className="glass-panel p-5">
      <PanelTitle icon={<BadgeCheck size={16} />} label="Fitness" accent={colors.kinpaku} />
      <div className="mt-5 flex flex-col gap-5 lg:flex-row lg:items-center">
        <div className="grid h-32 w-32 shrink-0 place-items-center rounded-full border border-kinpaku/40 bg-kinpaku/10">
          <div className="text-center">
            <p className="font-heading text-3xl font-bold text-kinpaku">
              {pct(fitness.composite_score)}
            </p>
            <p className="mt-1 font-mono text-[10px] uppercase text-sumi-600">
              threshold {pct(fitness.promotion_threshold)}
            </p>
          </div>
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          {metrics.map((key) => {
            const value = fitness[key];
            return (
              <div key={key}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="text-sumi-600">{metricLabels[key]}</span>
                  <span className="font-mono text-torinoko">{value.toFixed(3)}</span>
                </div>
                <div className="h-2 overflow-hidden rounded bg-sumi-800">
                  <div
                    className="h-full rounded bg-kinpaku"
                    style={{ width: `${Math.max(3, value * 100)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function CouncilPanel({ hypernode }: { hypernode: HypernodePayload }) {
  const verdict = hypernode.council_verdict;

  return (
    <section className="glass-panel p-5">
      <PanelTitle icon={<TriangleAlert size={16} />} label="Council Verdict" accent={colors.aozora} />
      <div className="mt-4 rounded-lg border border-aozora/25 bg-aozora/10 p-4">
        <div className="flex items-center justify-between gap-4">
          <p className="font-heading text-lg font-semibold capitalize text-aozora">
            {verdict.decision}
          </p>
          <span className="rounded bg-sumi-900 px-2 py-1 font-mono text-[10px] text-kinpaku">
            MIROFISH {verdict.mirofish_activated ? "active" : "idle"}
          </span>
        </div>
        <p className="mt-2 text-sm leading-5 text-torinoko/75">{verdict.reason}</p>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        {Object.entries(verdict.gate_results).map(([gate, result]) => (
          <div key={gate} className="flex items-center justify-between rounded bg-sumi-850/70 px-3 py-2">
            <span className="font-mono text-[10px] text-sumi-600">{gate}</span>
            <span className={`font-mono text-[10px] ${result === "PASS" ? "text-status-ok" : "text-status-warn"}`}>
              {result}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-1.5">
        {verdict.quorum_participants.map((participant) => (
          <span key={participant} className="rounded border border-sumi-700/50 px-2 py-1 font-mono text-[10px] text-sumi-600">
            {participant}
          </span>
        ))}
      </div>
    </section>
  );
}

function RevenuePanel({ hypernode }: { hypernode: HypernodePayload }) {
  const cell = hypernode.revenue_cell;

  return (
    <section className="glass-panel p-5">
      <PanelTitle icon={<DollarSign size={16} />} label="Revenue Cell" accent={colors.rokusho} />
      <dl className="mt-4 space-y-3 text-sm">
        <MetricRow label="verified revenue" value={`$${cell.verified_revenue_usd.toFixed(0)}`} />
        <MetricRow label="expected seed value" value={`$${cell.expected_value_usd.toFixed(0)}`} />
        <MetricRow label="evidence tier" value={cell.evidence_tier.replace(/_/g, " ")} />
      </dl>
      <p className="mt-4 text-sm leading-5 text-torinoko/75">{cell.revenue_model}</p>
      <p className="mt-3 text-xs leading-5 text-kitsurubami">{cell.trustee_principle}</p>
    </section>
  );
}

function ProvenancePanel({ hypernode }: { hypernode: HypernodePayload }) {
  return (
    <section className="glass-panel p-5">
      <PanelTitle icon={<GitBranch size={16} />} label="Provenance" accent={colors.fuji} />
      <div className="mt-4 space-y-3">
        {hypernode.provenance.map((item) => (
          <div key={item.id} className="border-b border-sumi-700/30 pb-3 last:border-0 last:pb-0">
            <div className="flex items-center justify-between gap-3">
              <p className="truncate text-sm text-torinoko">{item.label}</p>
              <span className="font-mono text-[10px] text-fuji">{pct(item.confidence)}</span>
            </div>
            <p className="mt-1 truncate font-mono text-[10px] text-sumi-600">{item.reference}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function NextActionsPanel({ hypernode }: { hypernode: HypernodePayload }) {
  return (
    <section className="glass-panel p-5">
      <PanelTitle icon={<Target size={16} />} label="Next Actions" accent={colors.botan} />
      <ol className="mt-4 space-y-3">
        {hypernode.next_actions.map((action, index) => (
          <li key={action} className="flex gap-3 text-sm leading-5 text-torinoko/75">
            <span className="grid h-5 w-5 shrink-0 place-items-center rounded bg-botan/15 font-mono text-[10px] text-botan">
              {index + 1}
            </span>
            <span>{action}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function OntologyPanel({ hypernode }: { hypernode: HypernodePayload }) {
  return (
    <section className="glass-panel p-5">
      <PanelTitle icon={<ArrowRight size={16} />} label="Ontology Trace" accent={colors.aozora} />
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {Object.entries(hypernode.object_chain).map(([chain, ids]) => (
          <div key={chain} className="rounded-lg border border-sumi-700/40 p-4">
            <p className="mb-3 font-mono text-[10px] uppercase text-sumi-600">{chain} chain</p>
            <div className="space-y-2">
              {ids.map((id, index) => (
                <div key={id} className="flex items-center gap-2 text-xs">
                  <span className="w-5 text-right font-mono text-sumi-600">{index + 1}</span>
                  <ArrowRight size={12} className="text-sumi-700" />
                  <span className="truncate font-mono text-torinoko/75">{id}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-4 font-mono text-[10px] uppercase text-sumi-600">
        {hypernode.ontology_counts.objects ?? 0} objects / {hypernode.ontology_counts.links ?? 0} links / {hypernode.typed_links.length} hypernode trace links
      </p>
    </section>
  );
}

function PanelTitle({
  icon,
  label,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  accent: string;
}) {
  return (
    <div className="flex items-center gap-2" style={{ color: accent }}>
      {icon}
      <h2 className="font-heading text-sm font-semibold uppercase">{label}</h2>
    </div>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-sumi-600">{label}</dt>
      <dd className="text-right font-mono text-torinoko">{value}</dd>
    </div>
  );
}
