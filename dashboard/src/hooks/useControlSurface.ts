"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ControlSurfaceRow, ControlSurfaceSummary } from "@/lib/types";

export type { ControlSurfaceRow, ControlSurfaceSummary };

interface ControlSurfaceEnvelope<T> {
  schema_version: string;
  request_id: string;
  generated_at: string;
  source_errors: Array<{ source: string; error: string; timestamp?: string }>;
  data: T | null;
}

function isControlSurfaceEnvelope<T>(
  value: T | ControlSurfaceEnvelope<T>,
): value is ControlSurfaceEnvelope<T> {
  return (
    typeof value === "object" &&
    value !== null &&
    "schema_version" in value &&
    "source_errors" in value &&
    "data" in value
  );
}

function unwrapControlSurface<T>(
  value: T | ControlSurfaceEnvelope<T>,
  fallback: T,
): T {
  if (isControlSurfaceEnvelope(value)) {
    return value.data ?? fallback;
  }
  return value;
}

export function useControlSurfaceRows() {
  const { data, isLoading, error, refetch } = useQuery<ControlSurfaceRow[]>({
    queryKey: ["control-surface-rows"],
    queryFn: async () => {
      const payload = await apiFetch<
        ControlSurfaceRow[] | ControlSurfaceEnvelope<ControlSurfaceRow[]>
      >("/api/control-surface/rows");
      return unwrapControlSurface(payload, []);
    },
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
    queryFn: async () => {
      const payload = await apiFetch<
        ControlSurfaceSummary | ControlSurfaceEnvelope<ControlSurfaceSummary>
      >("/api/control-surface/summary");
      if (isControlSurfaceEnvelope(payload) && payload.data === null) {
        throw new Error("Control surface summary unavailable");
      }
      return unwrapControlSurface(payload, null as unknown as ControlSurfaceSummary);
    },
    refetchInterval: 15_000,
  });

  return {
    summary: data ?? null,
    isLoading,
    error,
  };
}
