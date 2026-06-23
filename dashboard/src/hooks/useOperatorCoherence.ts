"use client";

import { useQuery } from "@tanstack/react-query";
import {
  fetchOperatorCoherenceReport,
  type OperatorCoherenceReport,
} from "@/lib/operatorCoherence";

export function useOperatorCoherence(options?: { github?: boolean; liveProbes?: boolean }) {
  const github = options?.github ?? false;
  const liveProbes = options?.liveProbes ?? true;
  const { data, isLoading, error, refetch } = useQuery<OperatorCoherenceReport>({
    queryKey: ["operator-coherence", github, liveProbes],
    queryFn: async () => {
      const response = await fetchOperatorCoherenceReport({ github, liveProbes });
      if (response.status === "error" || !response.data) {
        throw new Error(response.error || "Operator coherence report unavailable");
      }
      return response.data;
    },
    refetchInterval: 30_000,
  });

  return { report: data ?? null, isLoading, error, refresh: refetch };
}
