"use client";

import { useOperatorCoherence } from "@/hooks/useOperatorCoherence";
import { CockpitV2Board } from "./v2/CockpitV2Board";

export function OperatorCoherenceCockpit() {
  const { report, isLoading, error, refresh } = useOperatorCoherence({
    github: false,
    liveProbes: true,
  });

  if (isLoading && !report) {
    return <OperatorObservatorySkeleton />;
  }

  if (error || !report) {
    return (
      <div className="space-y-3 rounded-md border border-bengara/45 bg-bengara/10 p-5 text-sm text-bengara">
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em]">source failure · /api/operator-coherence/report</div>
        <h1 className="text-xl font-semibold text-torinoko">Operator observatory report unavailable</h1>
        <p className="max-w-3xl text-sumi-300">
          The cockpit could not load the existing report endpoint. This is an unavailable source state, not a healthy blank dashboard.
        </p>
        <pre className="max-h-40 overflow-auto rounded-md border border-bengara/30 bg-sumi-950/60 p-3 text-xs text-bengara">
          {error ? String(error) : "unknown error"}
        </pre>
        <button
          type="button"
          onClick={() => void refresh()}
          className="rounded-md border border-bengara/45 bg-bengara/10 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-bengara hover:bg-bengara/15"
        >
          Retry report fetch
        </button>
      </div>
    );
  }

  return <CockpitV2Board report={report} isLoading={isLoading} onRefresh={() => void refresh()} />;
}

function OperatorObservatorySkeleton() {
  const cells = Array.from({ length: 8 }, (_, index) => index);
  return (
    <div className="space-y-3 text-torinoko" aria-busy="true" aria-label="Loading operator observatory">
      <div className="rounded-md border border-sumi-800/60 bg-sumi-950/55 p-4">
        <div className="h-3 w-64 rounded bg-sumi-800/80" />
        <div className="mt-4 h-10 w-full max-w-3xl rounded bg-sumi-850/80" />
        <div className="mt-4 grid gap-2 sm:grid-cols-4">
          {cells.slice(0, 4).map((cell) => <div key={cell} className="h-16 rounded-md border border-sumi-800/60 bg-sumi-900/35" />)}
        </div>
      </div>
      <div className="rounded-md border border-bengara/35 bg-bengara/8 p-3 text-xs text-bengara">
        Running read-only `/api/operator-coherence/report` probes… layout skeleton preserves top truth, answer ribbon, observatory surface, inspector, and event tape.
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">
        {cells.map((cell) => <div key={cell} className="h-24 rounded-md border border-sumi-800/60 bg-sumi-950/40" />)}
      </div>
      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.2fr)_360px]">
        <div className="h-[460px] rounded-md border border-sumi-800/60 bg-sumi-950/40" />
        <div className="h-[460px] rounded-md border border-sumi-800/60 bg-sumi-950/40" />
      </div>
      <div className="h-24 rounded-md border border-sumi-800/60 bg-sumi-950/40" />
    </div>
  );
}
