"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface DharmaHealth {
  kernel: boolean;
  corpus: boolean;
  compiler: boolean;
  canary: boolean;
  stigmergy: boolean;
  kernel_axioms?: number;
  kernel_integrity?: boolean;
  corpus_claims?: number;
  stigmergy_density?: number;
}

export function useGates() {
  const { data, isLoading, error } = useQuery<DharmaHealth>({
    queryKey: ["gates"],
    queryFn: () => apiFetch<DharmaHealth>("/api/commands/dharma"),
    refetchInterval: 10_000,
  });

  return { health: data ?? null, isLoading, error };
}
