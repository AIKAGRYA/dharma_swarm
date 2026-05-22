"use client";

/**
 * useCommandPlaneTruth — single source of truth for the cockpit landing.
 *
 * Hits the consolidated backend contract at /api/manifest/command-plane that
 * codex prepared as the dashboard handoff: manifest health, active-track
 * evidence with per-criterion pass/fail and shippable state, control surface
 * summary, broken register rows, needs-human queue, PR queue placeholder,
 * working swarm pointers, frontend rules, next-PR ladder.
 *
 * Per docs/plans/2026-05-22-dashboard-frontend-claude-handoff.md.
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
  total: number;
  live: number;
  degraded: number;
  broken: number;
  stub: number;
  unknown: number;
}

export interface BrokenEntity {
  id: string;
  label: string;
  entity_type: string;
  declared_status: string;
  observed_status: string;
  gap: string;
}

export interface CompletionCriterion {
  id: string;
  kind: string;
  passed?: boolean;
  detail?: string;
}

export interface ActiveTrackEvidence {
  generated_at: string;
  active_track_id: string;
  shippable: boolean;
  prerequisites_ok: boolean;
  completion_progress: { passed: number; total: number };
  criteria: CompletionCriterion[];
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
  completion_criteria: CompletionCriterion[];
  non_goals: string[];
  next_items: { id: number | string; what: string; kind: string; blocker?: boolean }[];
  companion_manifest: string | null;
  evidence: ActiveTrackEvidence | null;
}

export interface NeedsHumanRow {
  id: string;
  kind: string;
  label: string;
  priority: string;
  coherence_state: string;
  declared_state: string;
  observed_state: string;
  owner_module: string;
  truth_owner: string;
  human_decision_required: boolean;
  next_action: string;
  gap_codes?: string[];
}

export interface BrokenRegisterRow {
  id: string;
  kind: string;
  label: string;
  priority: string;
  coherence_state: string;
  declared_state: string;
  next_action?: string;
}

export interface PrQueue {
  status: string;
  source: string;
  next_action: string;
  count?: number;
  rows?: { number: number; title: string; author?: string; state?: string }[];
}

export interface NextPrLadderItem {
  rank: number;
  id: string;
  title: string;
  why: string;
  scope: string[];
  proof?: string[];
}

export interface CommandPlaneTruth {
  schema_version: string;
  generated_at: string;
  root_route: string;
  primary_frontend_url: string;
  source_doc: string;
  repo_build: {
    manifest: {
      manifest_version: number;
      last_updated: string;
      summary: ManifestSummary;
      broken_entities: BrokenEntity[];
    };
    active_track: ActiveTrack;
    control_surface: Record<string, unknown>;
    broken_register: BrokenRegisterRow[];
    needs_human: NeedsHumanRow[];
    pr_queue: PrQueue;
  };
  working_swarm: {
    telemetry: { source: string; placement: string; frontend_action: string };
    goodworks: { source: string; placement: string; frontend_action: string };
    fleet: { source: string; placement: string; frontend_action: string };
  };
  frontend_rules: {
    root: string;
    must_show: string[];
    must_not: string[];
  };
  next_pr_ladder: NextPrLadderItem[];
  tui_discovery?: Record<string, unknown>;
  reconciled_inputs?: Record<string, unknown>;
}

async function fetchEnvelope<T>(path: string): Promise<T> {
  const resp = await apiFetch<ApiResponse<T>>(path);
  if (resp && typeof resp === "object" && "data" in resp) {
    return (resp as ApiResponse<T>).data;
  }
  return resp as unknown as T;
}

export function useCommandPlaneTruth() {
  const query = useQuery<CommandPlaneTruth>({
    queryKey: ["manifest", "command-plane"],
    queryFn: () => fetchEnvelope<CommandPlaneTruth>("/api/manifest/command-plane"),
    refetchInterval: 20_000,
  });

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error,
  };
}
