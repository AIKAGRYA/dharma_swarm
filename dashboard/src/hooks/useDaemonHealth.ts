"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { DaemonHealthOut } from "@/lib/types";

export function useDaemonHealth() {
  const { data, isLoading, error } = useQuery<DaemonHealthOut>({
    queryKey: ["daemon-health"],
    queryFn: () => apiFetch<DaemonHealthOut>("/api/daemon/health"),
    refetchInterval: 5_000,
  });

  return {
    daemonHealth: data ?? null,
    isLoading,
    error,
  };
}
