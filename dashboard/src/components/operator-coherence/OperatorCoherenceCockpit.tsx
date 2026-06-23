"use client";

import { useOperatorCoherence } from "@/hooks/useOperatorCoherence";
import { CockpitV2Board } from "./v2/CockpitV2Board";

export function OperatorCoherenceCockpit() {
  const { report, isLoading, error, refresh } = useOperatorCoherence({
    github: false,
    liveProbes: true,
  });

  if (isLoading && !report) {
    return (
      <div className="rounded-md border border-sumi-800/60 bg-sumi-950/50 p-6 text-sm text-sumi-400">
        Running read-only cockpit probes…
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="rounded-md border border-bengara/40 bg-bengara/10 p-6 text-sm text-bengara">
        Operator coherence report unavailable: {error ? String(error) : "unknown error"}
      </div>
    );
  }

  return <CockpitV2Board report={report} isLoading={isLoading} onRefresh={() => void refresh()} />;
}
