"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { GoodworksDgmStatus, GoodworksGoalRun, GoodworksReceipt } from "@/lib/types";

export function useGoodworksDgm() {
  const queryClient = useQueryClient();
  const statusQuery = useQuery<GoodworksDgmStatus>({
    queryKey: ["goodworks-dgm", "status"],
    queryFn: () => apiFetch<GoodworksDgmStatus>("/api/goodworks-dgm/status"),
    refetchInterval: 15_000,
  });
  const receiptsQuery = useQuery<GoodworksReceipt[]>({
    queryKey: ["goodworks-dgm", "receipts"],
    queryFn: () => apiFetch<GoodworksReceipt[]>("/api/goodworks-dgm/receipts?limit=12"),
    refetchInterval: 15_000,
  });
  const createDryRun = useMutation<GoodworksGoalRun>({
    mutationFn: () =>
      apiFetch<GoodworksGoalRun>("/api/goodworks-dgm/goal", {
        method: "POST",
        body: JSON.stringify({
          title: "Dashboard Goodworks DGM dry run",
          objective: "Score ledgers, compile wiki context, and bind AutoResearch planning.",
          mutation_mode: "dry_run",
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["goodworks-dgm"] });
    },
  });

  return {
    status: statusQuery.data ?? null,
    receipts: receiptsQuery.data ?? [],
    isLoading: statusQuery.isLoading || receiptsQuery.isLoading,
    isFetching: statusQuery.isFetching || receiptsQuery.isFetching,
    error: statusQuery.error || receiptsQuery.error || createDryRun.error,
    createDryRun,
    refresh: () => {
      void queryClient.invalidateQueries({ queryKey: ["goodworks-dgm"] });
    },
  };
}
