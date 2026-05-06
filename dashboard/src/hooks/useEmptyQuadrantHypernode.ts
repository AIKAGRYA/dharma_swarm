"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { HypernodePayload } from "@/lib/types";

export function useEmptyQuadrantHypernode() {
  const { data, isLoading, error } = useQuery<HypernodePayload>({
    queryKey: ["hypernodes", "empty-quadrant"],
    queryFn: () => apiFetch<HypernodePayload>("/api/hypernodes/empty-quadrant"),
    refetchInterval: 60_000,
  });

  return { hypernode: data ?? null, isLoading, error };
}
