import type { ControlSurfaceRow } from "@/lib/types";

export type DecisionBucketKey =
  | "needs_john"
  | "live_unauthorized"
  | "stale_refresh"
  | "blocked"
  | "pr_queue"
  | "vps_candidates"
  | "heavy_local_load"
  | "other";

export interface DecisionBucket {
  key: DecisionBucketKey;
  label: string;
  count: number;
}

export interface ProposalPreview {
  kind: string;
  commandText: string;
  sourceRefCount: number;
  evidenceCount: number;
  forbiddenInlineExecution: true;
}

const BUCKET_LABELS: Record<DecisionBucketKey, string> = {
  needs_john: "Needs John",
  live_unauthorized: "Live But Unauthorized",
  stale_refresh: "Stale / Needs Refresh",
  blocked: "Blocked",
  pr_queue: "PR Queue",
  vps_candidates: "VPS Candidates",
  heavy_local_load: "Heavy Local Load",
  other: "Other",
};

function gap(row: ControlSurfaceRow, prefix: string): string {
  return row.gap_codes.find((code) => code.startsWith(prefix)) ?? "";
}

export function decisionBucketForRow(row: ControlSurfaceRow): DecisionBucketKey {
  if (row.human_decision_required || row.gap_codes.includes("human_authority_required")) {
    return "needs_john";
  }
  if (row.kind === "pr_queue") {
    return "pr_queue";
  }
  if (row.gap_codes.includes("vps_candidate")) {
    return "vps_candidates";
  }
  if (row.gap_codes.includes("heavy_local_load")) {
    return "heavy_local_load";
  }
  if (row.observed_state === "blocked" || row.coherence_state === "drifted") {
    return "blocked";
  }
  if (row.observed_state === "stale" || gap(row, "freshness_state:") === "freshness_state:stale") {
    return "stale_refresh";
  }
  if (
    row.observed_state === "healthy" &&
    ["authority_tier:direct_probe", "authority_tier:projection_only", "authority_tier:mirror_only"].some((code) =>
      row.gap_codes.includes(code),
    )
  ) {
    return "live_unauthorized";
  }
  return "other";
}

export function decisionBuckets(rows: ControlSurfaceRow[]): DecisionBucket[] {
  const counts = new Map<DecisionBucketKey, number>();
  for (const row of rows) {
    const key = decisionBucketForRow(row);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return (Object.keys(BUCKET_LABELS) as DecisionBucketKey[]).map((key) => ({
    key,
    label: BUCKET_LABELS[key],
    count: counts.get(key) ?? 0,
  }));
}

export function proposalPreviewForRow(row: ControlSurfaceRow | null): ProposalPreview | null {
  if (!row) {
    return null;
  }
  const nextAction = row.next_action || "review row evidence";
  const queueStatus = String(row.raw?.queue_status ?? "");
  const prNumber = row.raw?.pr_number;
  let kind = "operator_hold_proposal";
  let commandText = `operator hold for ${row.id}: ${nextAction}`;

  if (row.kind === "pr_queue") {
    if (queueStatus === "GITHUB_GREEN_NEEDS_PACKET") {
      kind = "pr_packet_proposal";
      commandText = `make pr-packet PR=${prNumber}`;
    } else if (queueStatus === "NEEDS_REFRESH" || queueStatus === "BLOCKED_CONFLICT") {
      kind = "pr_rebase_proposal";
      commandText = `prepare rebase/refresh packet for PR #${prNumber}; do not mutate from cockpit`;
    }
  } else if (row.gap_codes.includes("vps_candidate")) {
    kind = "vps_migration_proposal";
    commandText = `draft VPS migration packet for ${row.id}; no migration from cockpit`;
  } else if (/stop|kill|quiet/i.test(nextAction)) {
    kind = "runtime_stop_proposal";
    commandText = `operator-approved stop proposal for ${row.id}: ${nextAction}`;
  } else if (/restart|start/i.test(nextAction)) {
    kind = "runtime_restart_proposal";
    commandText = `operator-approved restart proposal for ${row.id}: ${nextAction}`;
  }

  return {
    kind,
    commandText,
    sourceRefCount: row.source_refs?.length ?? 0,
    evidenceCount: row.evidence?.length ?? 0,
    forbiddenInlineExecution: true,
  };
}
