"use client";

import type { ReadinessReport } from "@/lib/operatorCoherence";

export function ReadinessScorePanel({ readiness }: { readiness: ReadinessReport }) {
  return (
    <section className="rounded-xl border border-sumi-800/60 bg-sumi-950/50 p-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sumi-500">
        Prod Readiness
      </div>
      <h2 className="mt-1 text-lg font-semibold text-torinoko">
        {readiness.score}% computed from probe evidence
      </h2>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {Object.entries(readiness.categories).map(([key, item]) => (
          <div key={key} className="rounded-lg border border-sumi-800/50 bg-sumi-900/35 p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="text-[11px] font-semibold text-sumi-300">
                {key.replaceAll("_", " ")}
              </div>
              <div className="text-xs font-semibold text-aozora">{item.score}%</div>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-sumi-800">
              <div
                className="h-full rounded-full bg-aozora"
                style={{ width: `${Math.max(0, Math.min(100, item.score))}%` }}
              />
            </div>
            <div className="mt-2 text-[10px] text-sumi-500">
              Weight {(item.weight * 100).toFixed(0)}% · {item.why}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

