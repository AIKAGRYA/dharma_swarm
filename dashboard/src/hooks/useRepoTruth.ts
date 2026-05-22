"use client";

/**
 * useRepoTruth — repo-state single source of truth for the cockpit landing.
 *
 * Pulls three manifest endpoints in parallel:
 *   /api/manifest/summary        — declared-vs-observed health counts
 *   /api/manifest/active-track   — ACTIVE_TRACK.yaml parsed
 *   /api/manifest/recent-commits — git log on current branch
 *
 * Refetches every 30s. The cockpit landing renders a REPO TRUTH ribbon
 * with these three signals — the answer to "is the dashboard SSoT for
 * the repo?".
 */

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

interface ApiResponse<T> {
  status: string;
  data: T;
  error: string;
  timestamp: string;
}

export interface ManifestSummary {
  manifest_version: number;
  last_updated: string;
  summary: {
    total: number;
    live: number;
    degraded: number;
    broken: number;
    stub: number;
    unknown: number;
  };
}

export interface ActiveTrack {
  id: string | null;
  name: string | null;
  status: string | null;
  verified_at: string | null;
  ttl_days: number | null;
  owner: string | null;
  description: string | null;
  surfaces_count: number;
  completion_criteria_count: number;
  completion_criteria: { id: string; kind: string }[];
  non_goals: string[];
  companion_manifest: string | null;
}

export interface RecentCommit {
  sha: string;
  short_sha: string;
  author: string;
  relative: string;
  subject: string;
}

export interface RecentCommits {
  branch: string | null;
  count: number;
  commits: RecentCommit[];
}

async function fetchEnvelope<T>(path: string): Promise<T> {
  const resp = await apiFetch<ApiResponse<T>>(path);
  if (resp && typeof resp === "object" && "data" in resp) {
    return resp.data as T;
  }
  return resp as unknown as T;
}

export function useRepoTruth() {
  const summaryQuery = useQuery<ManifestSummary>({
    queryKey: ["manifest", "summary"],
    queryFn: () => fetchEnvelope<ManifestSummary>("/api/manifest/summary"),
    refetchInterval: 30_000,
  });

  const trackQuery = useQuery<ActiveTrack>({
    queryKey: ["manifest", "active-track"],
    queryFn: () => fetchEnvelope<ActiveTrack>("/api/manifest/active-track"),
    refetchInterval: 30_000,
  });

  const commitsQuery = useQuery<RecentCommits>({
    queryKey: ["manifest", "recent-commits"],
    queryFn: () => fetchEnvelope<RecentCommits>("/api/manifest/recent-commits?limit=12"),
    refetchInterval: 30_000,
  });

  return {
    summary: summaryQuery.data ?? null,
    activeTrack: trackQuery.data ?? null,
    recentCommits: commitsQuery.data ?? null,
    isLoading:
      summaryQuery.isLoading || trackQuery.isLoading || commitsQuery.isLoading,
    error: summaryQuery.error || trackQuery.error || commitsQuery.error,
  };
}
