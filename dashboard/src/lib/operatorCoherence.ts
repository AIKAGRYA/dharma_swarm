import { apiPath } from "./api";
import type { ApiResponse } from "./types";

export interface CoherenceEvidence {
  kind: string;
  source: string;
  path?: string;
  detail?: string;
  status?: string;
  observed_at?: string;
  age_hours?: number | null;
}

export interface CoherenceCard {
  kind: string;
  id: string;
  title: string;
  status: string;
  lane: string;
  track: string;
  branch?: string;
  pr?: string;
  risk: string;
  next_action: string;
  decision_type: "operator_decision" | "engineering_task" | string;
  evidence: CoherenceEvidence[];
  facets: {
    tracked: boolean;
    live: boolean;
    stale: boolean;
    preserved: boolean;
    intentional: boolean;
    rogue: boolean;
    local_only: boolean;
    origin_backed: boolean;
    operator_decision: boolean;
    [key: string]: unknown;
  };
  raw?: Record<string, unknown>;
}

export interface ReadinessCategory {
  score: number;
  weight: number;
  why: string;
}

export interface ReadinessReport {
  score: number;
  interpretation: string;
  weights: Record<string, number>;
  categories: Record<string, ReadinessCategory>;
}

export interface KanbanLane {
  lane: string;
  count: number;
  cards: CoherenceCard[];
}

export interface CoherenceAction {
  title: string;
  kind: string;
  risk: string;
  next_action: string;
  evidence: CoherenceEvidence[];
}

export interface CoherenceTrack {
  id?: string;
  name?: string;
  lifecycle?: string;
  status?: string;
  owner?: string;
  branch?: string;
  pr?: string;
  stale?: boolean;
  readiness?: number;
  criteria_pass_rate?: number;
  has_rigorous_evidence?: boolean;
  readiness_basis?: string;
  readiness_capped?: boolean;
  shippable?: boolean;
  evidence_present?: boolean;
  next_items?: unknown[];
  [key: string]: unknown;
}

export interface OperatorCoherenceReport {
  schema_version: string;
  generated_at: string;
  repo_root: string;
  source_errors: { source: string; error: string; timestamp?: string }[];
  executive: {
    health: string;
    prod_readiness_estimate: number;
    top_blockers: CoherenceAction[];
    next_3_actions: CoherenceAction[];
  };
  readiness: ReadinessReport;
  kanban: KanbanLane[];
  cards: CoherenceCard[];
  track_portfolio: {
    active_count: number;
    closed_count: number;
    policy?: {
      max_active?: number;
      [key: string]: unknown;
    };
    tracks: CoherenceTrack[];
    proposed_tracks: Record<string, unknown>[];
    broken_register: Record<string, unknown>;
  };
  rogue_work_radar: {
    cards: CoherenceCard[];
    dirty_worktree_count: number;
    local_only_count: number;
    stash_count: number;
    local_branch_total?: number;
    local_only_branch_count?: number;
    unpushed_branch_count?: number;
    orphaned_branch_count?: number;
  };
  agent_terminal_census: {
    tmux_sessions?: Record<string, unknown>[];
    launchd_jobs?: Record<string, unknown>[];
    processes?: Record<string, unknown>[];
    disabled?: boolean;
  };
  branch_census?: {
    total?: number;
    local_only?: number;
    unpushed_ahead?: number;
    orphaned_gone?: number;
    stale?: number;
    branches?: Record<string, unknown>[];
  };
  git?: {
    main?: {
      branch?: string;
      branch_line?: string;
      head?: string;
      ahead?: number;
      behind?: number;
      dirty_count?: number;
      tracked_dirty_count?: number;
      untracked_count?: number;
      dirty?: boolean;
    };
    worktrees?: Record<string, unknown>[];
  };
  source_refs?: Record<string, unknown>;
  live_ops?: {
    enabled?: boolean;
    reason?: string;
    summary?: { total?: number; by_status?: Record<string, number>; human_authority_required?: number; proof_gap_surfaces?: number; vps_candidates?: number };
    surfaces?: Record<string, unknown>[];
  };
  onboarding?: {
    status?: string;
    target?: string;
    evidence_paths?: Record<string, unknown>[];
  };
  runtime_receipts?: {
    runtime_dbs?: Record<string, unknown>[];
    receipt_count?: number;
    recent_receipts?: Record<string, unknown>[];
  };
  operator_surfaces: {
    surfaces: Record<string, unknown>[];
    abandoned_dashboard_candidates: Record<string, unknown>[];
  };
  preservation_ledger: Record<string, unknown>;
  pr_ci_triage: Record<string, unknown>;
  definition_answers: Record<string, unknown>;
}

export async function fetchOperatorCoherenceReport(options?: {
  github?: boolean;
  liveProbes?: boolean;
}): Promise<ApiResponse<OperatorCoherenceReport>> {
  const sp = new URLSearchParams();
  if (options?.github) sp.set("github", "true");
  if (options?.liveProbes === false) sp.set("live_probes", "false");
  const qs = sp.toString();
  const res = await fetch(apiPath(`/api/operator-coherence/report${qs ? `?${qs}` : ""}`), {
    headers: { Accept: "application/json" },
  });

  if (!res.ok) {
    return {
      status: "error",
      data: undefined as unknown as OperatorCoherenceReport,
      error: `${res.status} ${res.statusText}: ${await res.text().catch(() => "")}`,
      timestamp: new Date().toISOString(),
    };
  }
  const json = await res.json();
  if (json && typeof json === "object" && "data" in json) {
    return {
      status: String(json.status ?? "ok"),
      data: json.data as OperatorCoherenceReport,
      error: Array.isArray(json.source_errors) && json.source_errors.length > 0 ? "source_errors_present" : "",
      timestamp: typeof json.generated_at === "string" ? json.generated_at : new Date().toISOString(),
    };
  }
  return {
    status: "ok",
    data: json as OperatorCoherenceReport,
    error: "",
    timestamp: new Date().toISOString(),
  };
}
