"use client";

import { AlertTriangle, CheckCircle2, Gauge, RefreshCw } from "lucide-react";
import type { OperatorCoherenceReport } from "@/lib/operatorCoherence";

function scoreTone(score: number): string {
  if (score >= 70) return "text-rokusho border-rokusho/40 bg-rokusho/10";
  if (score >= 40) return "text-kinpaku border-kinpaku/40 bg-kinpaku/10";
  return "text-bengara border-bengara/50 bg-bengara/10";
}

export function ExecutiveBoard({
  report,
  isLoading,
  onRefresh,
}: {
  report: OperatorCoherenceReport;
  isLoading: boolean;
  onRefresh: () => void;
}) {
  return (
    <section className="rounded-xl border border-sumi-800/60 bg-sumi-950/60 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-sumi-500">
            <Gauge size={14} />
            Operator Coherence Cockpit
          </div>
          <h1 className="mt-2 text-2xl font-semibold text-torinoko">
            Executive Board
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-sumi-400">
            Projection over git, governance, evidence, runtime/process state,
            dashboard surfaces, preservation, and PR/CI when available. Not a
            new source of truth.
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={isLoading}
          className="inline-flex items-center gap-2 rounded-md border border-sumi-700/70 bg-sumi-900/70 px-3 py-2 text-xs font-semibold text-sumi-200 hover:border-aozora/60 disabled:opacity-50"
        >
          <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
          Refresh probes
        </button>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[220px_minmax(0,1fr)_minmax(0,1fr)]">
        <div className={`rounded-lg border p-4 ${scoreTone(report.readiness.score)}`}>
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em]">
            Prod readiness
          </div>
          <div className="mt-2 text-4xl font-semibold tabular-nums">
            {report.readiness.score}%
          </div>
          <div className="mt-2 text-xs opacity-80">{report.readiness.interpretation}</div>
        </div>

        <div className="rounded-lg border border-sumi-800/60 bg-sumi-900/40 p-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-sumi-500">
            <AlertTriangle size={13} />
            Top blockers
          </div>
          <div className="mt-3 space-y-2">
            {report.executive.top_blockers.slice(0, 4).map((blocker) => (
              <div key={`${blocker.kind}-${blocker.title}`} className="text-xs">
                <span className="font-semibold text-sumi-200">{blocker.risk}</span>
                <span className="text-sumi-500"> — {blocker.title}</span>
              </div>
            ))}
            {report.executive.top_blockers.length === 0 ? (
              <div className="text-xs text-sumi-500">No blocker cards emitted.</div>
            ) : null}
          </div>
        </div>

        <div className="rounded-lg border border-sumi-800/60 bg-sumi-900/40 p-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-sumi-500">
            <CheckCircle2 size={13} />
            Next 3 actions
          </div>
          <ol className="mt-3 list-decimal space-y-2 pl-4">
            {report.executive.next_3_actions.map((action) => (
              <li key={`${action.kind}-${action.title}`} className="text-xs text-sumi-300">
                <span className="font-semibold text-torinoko">{action.next_action}</span>
                <div className="text-[11px] text-sumi-500">
                  {action.risk} · {action.evidence?.[0]?.source ?? "no evidence"}
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <div className="mt-3 text-[10px] text-sumi-600">
        Generated {report.generated_at} · {report.source_errors.length} source
        uncertainty item(s)
      </div>
    </section>
  );
}

