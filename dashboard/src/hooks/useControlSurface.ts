"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ControlSurfaceRow, ControlSurfaceSummary } from "@/lib/types";

export type { ControlSurfaceRow, ControlSurfaceSummary };

export function useControlSurfaceRows() {
  const { data, isLoading, error, refetch } = useQuery<ControlSurfaceRow[]>({
    queryKey: ["control-surface-rows"],
    queryFn: () => apiFetch<ControlSurfaceRow[]>("/api/control-surface/rows"),
    refetchInterval: 15_000,
  });

  return {
    rows: data ?? [],
    isLoading,
    error,
    refetch,
  };
}

export function useControlSurfaceSummary() {
  const { data, isLoading, error } = useQuery<ControlSurfaceSummary>({
    queryKey: ["control-surface-summary"],
    queryFn: () => apiFetch<ControlSurfaceSummary>("/api/control-surface/summary"),
    refetchInterval: 15_000,
  });

  return {
    summary: data ?? null,
    isLoading,
    error,
  };
}
