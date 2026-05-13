"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface ControlSurfaceRow {
  id: string;
  kind: string;
  label: string;
  authority_role: string;
  declared_state: string;
  desired_state: string;
  observed_state: string;
  coherence_state: string;
  priority: string;
  owner_module: string;
  truth_owner: string;
  evidence: string[];
  freshness: string;
  gap_codes: string[];
  next_action: string;
  human_decision_required: boolean;
  source_refs: string[];
  raw: Record<string, unknown>;
}

export interface ControlSurfaceSummary {
  total: number;
  bound: number;
  partial: number;
  drifted: number;
  declared_only: number;
  unknown: number;
  human_decision_required_count: number;
  p0_count: number;
  p1_count: number;
  generated_at: string;
  sources_consulted: string[];
}

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
