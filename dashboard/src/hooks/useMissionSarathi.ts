"use client";

import { useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import {
  classifyCampaignTaskEvidence,
  parseCampaignEvidence,
  type CampaignEvidenceProjection,
} from "@/lib/missionCampaignEvidence";
import type {
  ControlSurfaceEnvelope,
  RuntimeEvent,
  RuntimeGraphRun,
  RuntimeGraphSnapshot,
} from "@/lib/types";

const BASE_REFRESH_MS = 5_000;
const MAX_REFRESH_MS = 60_000;
const RECENT_EVIDENCE_MS = 120_000;
const SNAPSHOT_STALE_MS = 45_000;
const OWNER_EXECUTION_SCHEMA = "dharma.mission_control.owner_execution.v1";
const SUBSTANTIVE_EVENT =
  /(artifact|checkpoint|evidence|output|progress|result|test|tool|verification|work_delta)/i;
const CONNECTIVITY_EVENT =
  /(^|[_-])(ack(nowledged)?|claim(ed)?|connect(ed)?|heartbeat|lease|presence)([_-]|$)/i;

export interface MissionView {
  mission_id: string;
  session_id: string;
  title: string;
  goal: string;
  operator_id: string;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface MissionTaskView {
  task_id: string;
  mission_id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  assigned_to: string;
  result: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface MissionAttemptView {
  attempt_id: string;
  mission_id: string;
  session_id: string;
  task_id: string;
  claim_id: string;
  assigned_to: string;
  assigned_by: string;
  status: string;
  failure_code: string;
  idempotency_key: string;
  metadata: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
}

export interface MissionLeaseView {
  claim_id: string;
  mission_id: string;
  session_id: string;
  task_id: string;
  agent_id: string;
  attempt_id: string;
  status: string;
  active: boolean;
  expired: boolean;
  heartbeat_at: string | null;
  stale_after: string | null;
  metadata: Record<string, unknown>;
}

export interface MissionReceiptView {
  receipt_id: string;
  mission_id: string;
  task_id: string;
  attempt_id: string;
  agent_id: string;
  receipt_type: string;
  status: string;
  idempotency_key: string;
  payload: Record<string, unknown>;
  created_at: string | null;
}

export interface MissionSnapshot {
  mission: MissionView;
  tasks: MissionTaskView[];
  attempts: MissionAttemptView[];
  leases: MissionLeaseView[];
  receipts: MissionReceiptView[];
  reconciliation: string;
  observed_at: string;
  authority: string;
  proves_executor_liveness: boolean;
  campaign_evidence?: CampaignEvidenceProjection;
}

export interface MissionSnapshotProjection {
  schema_version: string;
  mission_id: string;
  state: "observed" | "uninitialized" | "unknown";
  source_mode: "injected_read_only";
  snapshot: MissionSnapshot | null;
  runtime_projection_ready: boolean;
  runtime_projection_mode: "immutable_copy" | "unavailable";
  proves_executor_liveness: false;
}

export interface RuntimeEventsSnapshot {
  schema_version: string;
  generated_at: string;
  runtime_db: string;
  filters: Record<string, unknown>;
  summary: { event_count: number };
  events: RuntimeEvent[];
}

export type TaskTruthState =
  | "verified_complete"
  | "verified_working"
  | "active_unverified"
  | "candidate_unverified"
  | "rejected"
  | "lease_only"
  | "queued"
  | "stale"
  | "expired"
  | "orphan"
  | "join_unknown"
  | "conflict"
  | "terminal_receipted"
  | "terminal_unverified"
  | "unknown";

export interface TaskTruthRow {
  task: MissionTaskView;
  attempt: MissionAttemptView | null;
  lease: MissionLeaseView | null;
  ownerRunId: string;
  runtimeRun: RuntimeGraphRun | null;
  evidenceEvent: RuntimeEvent | null;
  terminalReceipt: MissionReceiptView | null;
  acceptance: "accepted" | "rejected" | "not_observed";
  state: TaskTruthState;
  label: string;
  detail: string;
}

export interface EvidenceTimelineItem {
  id: string;
  source: "mission_receipt" | "runtime_event" | "campaign_evidence";
  taskId: string;
  executionId: string;
  agentId: string;
  kind: string;
  status: string;
  summary: string;
  createdAt: string | null;
}

interface MissionSarathiData {
  envelope: ControlSurfaceEnvelope<MissionSnapshotProjection> | null;
  graph: RuntimeGraphSnapshot | null;
  events: RuntimeEventsSnapshot | null;
  sourceErrors: string[];
  runtimeSuppressedReason: string | null;
}

function timestamp(value: string | null | undefined): number {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function newestAttempt(
  attempts: MissionAttemptView[],
  taskId: string,
): MissionAttemptView | null {
  return (
    attempts
      .filter((attempt) => attempt.task_id === taskId)
      .sort(
        (left, right) =>
          timestamp(right.started_at ?? right.completed_at) -
          timestamp(left.started_at ?? left.completed_at),
      )[0] ?? null
  );
}

function matchingLease(
  leases: MissionLeaseView[],
  taskId: string,
  attemptId: string,
  claimId: string,
): MissionLeaseView | null {
  return (
    leases.find(
      (lease) =>
        lease.task_id === taskId &&
        (claimId
          ? lease.claim_id === claimId
          : !attemptId || !lease.attempt_id || lease.attempt_id === attemptId),
    ) ?? null
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Return the sole canonical join from a Mission Control task to its owner run.
 * Attempt IDs are a different identity domain and must never be used as a
 * fallback. A missing or incompatible stamp therefore stays unknown.
 */
export function canonicalOwnerRunId(task: MissionTaskView): string | null {
  const stamp = task.metadata.mission_control_owner_execution;
  if (!isRecord(stamp)) return null;
  if (
    stamp.schema_version !== OWNER_EXECUTION_SCHEMA ||
    stamp.backend !== "orchestrator" ||
    stamp.mission_id !== task.mission_id ||
    stamp.task_id !== task.task_id ||
    typeof stamp.dispatch_key !== "string" ||
    stamp.dispatch_key.length === 0 ||
    typeof stamp.run_id !== "string" ||
    stamp.run_id.length === 0
  ) {
    return null;
  }
  const compatibilityRunId = task.metadata.runtime_run_id;
  if (
    compatibilityRunId !== undefined &&
    compatibilityRunId !== stamp.run_id
  ) {
    return null;
  }
  return stamp.run_id;
}

function matchingRun(
  graph: RuntimeGraphSnapshot | null,
  taskId: string,
  ownerRunId: string,
): RuntimeGraphRun | null {
  if (!graph || !ownerRunId) return null;
  return (
    graph.runs.find(
      (run) => run.run_id === ownerRunId && run.task_id === taskId,
    ) ?? null
  );
}

function recentSubstantiveEvent(
  events: RuntimeEventsSnapshot | null,
  taskId: string,
  ownerRunId: string,
  now: number,
): RuntimeEvent | null {
  if (!events || !ownerRunId) return null;
  return (
    events.events.find(
      (event) =>
        event.task_id === taskId &&
        event.run_id === ownerRunId &&
        SUBSTANTIVE_EVENT.test(event.event_name) &&
        !CONNECTIVITY_EVENT.test(event.event_name) &&
        now - timestamp(event.created_at) <= RECENT_EVIDENCE_MS,
    ) ?? null
  );
}

function terminalEvidence(
  receipts: MissionReceiptView[],
  task: MissionTaskView,
  attempt: MissionAttemptView | null,
): {
  terminal: MissionReceiptView | null;
  acceptance: TaskTruthRow["acceptance"];
} {
  if (!attempt) return { terminal: null, acceptance: "not_observed" };
  const attemptId = attempt.attempt_id;
  const exact = receipts.filter(
    (receipt) =>
      receipt.mission_id === task.mission_id &&
      receipt.task_id === task.task_id &&
      receipt.attempt_id === attemptId,
  );
  const terminal =
    exact.find((receipt) => {
      const metadata = receipt.payload.metadata;
      return (
        receipt.receipt_type === "mission_attempt_terminal" &&
        (receipt.status === "succeeded" || receipt.status === "failed") &&
        receipt.agent_id === attempt.assigned_to &&
        receipt.idempotency_key === attempt.idempotency_key &&
        receipt.payload.schema_version === "dharma.mission_control.v1" &&
        receipt.payload.mission_id === task.mission_id &&
        receipt.payload.attempt_id === attemptId &&
        typeof receipt.payload.result === "string" &&
        typeof receipt.payload.failure_code === "string" &&
        isRecord(metadata) &&
        metadata.schema_version === "dharma.mission_control.v1" &&
        metadata.mission_id === task.mission_id &&
        metadata.attempt_id === attemptId &&
        metadata.attempt_key === attempt.idempotency_key
      );
    }) ?? null;

  // MissionSnapshot currently exposes no typed independent-acceptance receipt
  // carrying a verifier identity. Arbitrary receipt names/statuses cannot be
  // promoted to acceptance; add support only when that backend contract exists.
  return { terminal, acceptance: "not_observed" };
}

export function buildTaskTruth(
  snapshot: MissionSnapshot | null,
  graph: RuntimeGraphSnapshot | null,
  events: RuntimeEventsSnapshot | null,
  now = Date.now(),
): TaskTruthRow[] {
  if (!snapshot) return [];
  const snapshotStale = now - timestamp(snapshot.observed_at) > SNAPSHOT_STALE_MS;
  const reconciliationConflict =
    snapshot.reconciliation.includes("conflicting") ||
    snapshot.reconciliation === "foreign_runtime_record" ||
    snapshot.reconciliation === "evidence_scan_saturated";

  return snapshot.tasks.map((task) => {
    const attempt = newestAttempt(snapshot.attempts, task.task_id);
    const attemptId = attempt?.attempt_id ?? "";
    const ownerRunId = canonicalOwnerRunId(task) ?? "";
    const runtimeRun = matchingRun(graph, task.task_id, ownerRunId);
    const lease = matchingLease(
      snapshot.leases,
      task.task_id,
      attemptId,
      runtimeRun?.claim_id ?? "",
    );
    const evidenceEvent = recentSubstantiveEvent(
      events,
      task.task_id,
      ownerRunId,
      now,
    );
    const { terminal: terminalReceipt, acceptance } = terminalEvidence(
      snapshot.receipts,
      task,
      attempt,
    );
    const campaignVerdict = classifyCampaignTaskEvidence(
      snapshot.campaign_evidence,
      task,
    );
    const effectiveAcceptance =
      campaignVerdict.acceptance !== "not_observed"
        ? campaignVerdict.acceptance
        : acceptance;
    const leaseExpired =
      Boolean(lease?.expired) ||
      (Boolean(lease?.stale_after) && timestamp(lease?.stale_after) <= now);
    const leaseActive = Boolean(lease?.active) && !leaseExpired;
    const attemptTerminal =
      attempt?.status === "succeeded" || attempt?.status === "failed";
    const taskTerminal = task.status === "completed" || task.status === "failed";
    const terminalMatches =
      Boolean(terminalReceipt) &&
      terminalReceipt?.status === attempt?.status &&
      snapshot.reconciliation === "coherent" &&
      effectiveAcceptance !== "rejected";
    const runActive =
      runtimeRun?.status === "running" ||
      runtimeRun?.status === "working" ||
      runtimeRun?.status === "active";
    const ownerRunConflict = Boolean(
      graph &&
        ownerRunId &&
        graph.runs.some(
          (run) => run.run_id === ownerRunId && run.task_id !== task.task_id,
        ),
    );
    const ownerLeaseConflict = Boolean(
      runtimeRun &&
        lease &&
        (lease.claim_id !== runtimeRun.claim_id ||
          lease.agent_id !== runtimeRun.assigned_to),
    );
    const hasExecutionProjection = Boolean(attempt || lease);

    let state: TaskTruthState = "unknown";
    let label = "Unknown";
    let detail = "Canonical task state is present without sufficient execution evidence.";

    if (
      reconciliationConflict ||
      ownerRunConflict ||
      ownerLeaseConflict ||
      campaignVerdict.state === "conflict"
    ) {
      state = "conflict";
      label = "Conflict";
      detail = campaignVerdict.state === "conflict"
        ? campaignVerdict.detail
        : ownerRunConflict
        ? "The stamped owner run resolves to a foreign task; no work claim is promoted."
        : ownerLeaseConflict
          ? "The owner run and lease disagree on claim or agent identity."
          : `Mission reconciliation is ${snapshot.reconciliation}; no work claim is promoted.`;
    } else if (campaignVerdict.state === "rejected") {
      state = "rejected";
      label = campaignVerdict.label;
      detail = campaignVerdict.detail;
    } else if (campaignVerdict.state === "verified_complete") {
      state = "verified_complete";
      label = campaignVerdict.label;
      detail = campaignVerdict.detail;
    } else if (campaignVerdict.state === "candidate_unverified") {
      state = "candidate_unverified";
      label = campaignVerdict.label;
      detail = campaignVerdict.detail;
    } else if (attemptTerminal || taskTerminal) {
      if (terminalMatches) {
        state = "terminal_receipted";
        label = attempt?.status === "failed" ? "Failed · receipted" : "Terminal · receipted";
        detail =
          effectiveAcceptance === "accepted"
            ? "Terminal receipt and independent acceptance are coherent."
            : "Terminal receipt is coherent; independent acceptance was not observed.";
      } else {
        state = "terminal_unverified";
        label = "Terminal · unverified";
        detail =
          effectiveAcceptance === "rejected"
            ? "Independent acceptance rejected the terminal claim."
            : "Terminal state lacks a matching canonical terminal receipt.";
      }
    } else if (leaseExpired) {
      state = "expired";
      label = "Lease expired";
      detail = "Lease freshness expired; heartbeat history is not current work proof.";
    } else if (snapshotStale) {
      state = "stale";
      label = "Stale";
      detail = "The canonical mission snapshot is older than the freshness window.";
    } else if (!ownerRunId && hasExecutionProjection) {
      state = "join_unknown";
      label = "Owner join unknown";
      detail =
        "Attempt or lease state exists, but no schema-bound owner-run reference is present.";
    } else if (
      leaseActive &&
      runtimeRun &&
      runActive &&
      evidenceEvent
    ) {
      state = "verified_working";
      label = "Verified working";
      detail = `Active lease and run match recent substantive event ${evidenceEvent.event_name}.`;
    } else if (campaignVerdict.state === "active_unverified") {
      state = "active_unverified";
      label = campaignVerdict.label;
      detail = campaignVerdict.detail;
    } else if (
      graph &&
      ownerRunId &&
      ((leaseActive && !runtimeRun) ||
        (runtimeRun && runActive && !leaseActive) ||
        (attempt?.status === "running" && !runtimeRun))
    ) {
      state = "orphan";
      label = "Orphan";
      detail = "A stamped owner identity does not have a coherent run and lease projection.";
    } else if (leaseActive) {
      state = "lease_only";
      label = "Lease only";
      detail = "Connected/leased, but no matching recent substantive work evidence exists.";
    } else {
      state = "queued";
      label = "Queued";
      detail = "Task exists canonically and has no active verified execution.";
    }

    return {
      task,
      attempt,
      lease,
      ownerRunId,
      runtimeRun,
      evidenceEvent,
      terminalReceipt,
      acceptance: effectiveAcceptance,
      state,
      label,
      detail,
    };
  });
}

export function buildEvidenceTimeline(
  snapshot: MissionSnapshot | null,
  events: RuntimeEventsSnapshot | null,
): EvidenceTimelineItem[] {
  const campaignEvidence = parseCampaignEvidence(snapshot?.campaign_evidence);
  const campaignItems: EvidenceTimelineItem[] = (
    campaignEvidence?.owner_executions ?? []
  ).map((owner) => {
    const task = snapshot?.tasks.find(
      (candidate) => candidate.task_id === owner.ref.task_id,
    );
    const evidenceVerdict = task
      ? classifyCampaignTaskEvidence(campaignEvidence, task)
      : null;
    return {
      id: `campaign:${owner.ref.run_id}:${owner.observed_at}`,
      source: "campaign_evidence",
      taskId: owner.ref.task_id,
      executionId: owner.ref.run_id,
      agentId: owner.ref.agent_id,
      kind: "owner_execution",
      status: evidenceVerdict?.state ?? "owner_observed",
      summary:
        evidenceVerdict?.detail ??
        "Owner execution was projected without a matching task identity.",
      createdAt: owner.observed_at,
    };
  });
  const receipts: EvidenceTimelineItem[] = (snapshot?.receipts ?? []).map(
    (receipt) => ({
      id: `mission:${receipt.receipt_id}`,
      source: "mission_receipt",
      taskId: receipt.task_id,
      executionId: receipt.attempt_id,
      agentId: receipt.agent_id,
      kind: receipt.receipt_type,
      status: receipt.status,
      summary:
        typeof receipt.payload.summary === "string"
          ? receipt.payload.summary
          : "Canonical Mission Control receipt",
      createdAt: receipt.created_at,
    }),
  );
  const runtimeEvents: EvidenceTimelineItem[] = (events?.events ?? []).map(
    (event) => ({
      id: `runtime:${event.event_id}`,
      source: "runtime_event",
      taskId: event.task_id ?? "",
      executionId: event.run_id ?? "",
      agentId: event.agent_id ?? "",
      kind: event.event_name,
      status: event.ledger_kind,
      summary: event.summary || event.event_text || "Runtime event",
      createdAt: event.created_at,
    }),
  );
  return [...campaignItems, ...receipts, ...runtimeEvents]
    .sort((left, right) => timestamp(right.createdAt) - timestamp(left.createdAt))
    .slice(0, 24);
}

async function loadMissionSarathi(missionId: string): Promise<MissionSarathiData> {
  const sourceErrors: string[] = [];
  let envelope: ControlSurfaceEnvelope<MissionSnapshotProjection> | null = null;

  try {
    envelope = await apiFetch<
      ControlSurfaceEnvelope<MissionSnapshotProjection>
    >(
      `/api/control-surface/missions/${encodeURIComponent(missionId)}/snapshot`,
    );
    sourceErrors.push(
      ...envelope.source_errors.map(
        (error) => `${error.source}: ${error.error}`,
      ),
    );
  } catch (error) {
    sourceErrors.push(
      `mission_snapshot: ${error instanceof Error ? error.message : String(error)}`,
    );
    return {
      envelope: null,
      graph: null,
      events: null,
      sourceErrors,
      runtimeSuppressedReason:
        "Mission snapshot source is unavailable; runtime projection reads were not attempted.",
    };
  }

  const projection = envelope.data;
  if (
    projection.state !== "observed" ||
    !projection.runtime_projection_ready ||
    projection.runtime_projection_mode !== "immutable_copy"
  ) {
    return {
      envelope,
      graph: null,
      events: null,
      sourceErrors,
      runtimeSuppressedReason:
        "Runtime graph/events are withheld until an immutable projection copy is explicitly injected.",
    };
  }

  const sessionId = `mission:${missionId}`;
  const [graphResult, eventsResult] = await Promise.allSettled([
    apiFetch<RuntimeGraphSnapshot>(
      `/api/runtime/graph?session_id=${encodeURIComponent(sessionId)}&limit=200&receipt_limit=500`,
    ),
    apiFetch<RuntimeEventsSnapshot>(
      `/api/runtime/events?session_id=${encodeURIComponent(sessionId)}&limit=200`,
    ),
  ]);
  const graph = graphResult.status === "fulfilled" ? graphResult.value : null;
  const events = eventsResult.status === "fulfilled" ? eventsResult.value : null;
  if (graphResult.status === "rejected") {
    sourceErrors.push(
      `runtime_graph: ${graphResult.reason instanceof Error ? graphResult.reason.message : String(graphResult.reason)}`,
    );
  }
  if (eventsResult.status === "rejected") {
    sourceErrors.push(
      `runtime_events: ${eventsResult.reason instanceof Error ? eventsResult.reason.message : String(eventsResult.reason)}`,
    );
  }
  return {
    envelope,
    graph,
    events,
    sourceErrors,
    runtimeSuppressedReason: null,
  };
}

export function useMissionSarathi(missionId: string) {
  const transportFailureCount = useRef(0);
  const query = useQuery<MissionSarathiData>({
    queryKey: ["mission-sarathi", missionId],
    queryFn: async () => {
      const loaded = await loadMissionSarathi(missionId);
      const hasTransportFailure = loaded.sourceErrors.some((error) =>
        /API \d{3}|fetch|network|timeout|refused|unavailable/i.test(error),
      );
      transportFailureCount.current = hasTransportFailure
        ? Math.min(transportFailureCount.current + 1, 4)
        : 0;
      return loaded;
    },
    enabled: Boolean(missionId),
    retry: false,
    refetchInterval: () => {
      if (
        typeof document !== "undefined" &&
        document.visibilityState !== "visible"
      ) {
        return false;
      }
      return Math.min(
        BASE_REFRESH_MS * 2 ** transportFailureCount.current,
        MAX_REFRESH_MS,
      );
    },
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });

  const projection = query.data?.envelope?.data ?? null;
  const snapshot = projection?.snapshot ?? null;
  const graph = query.data?.graph ?? null;
  const events = query.data?.events ?? null;
  return {
    ...query,
    projection,
    snapshot,
    graph,
    events,
    taskTruth: buildTaskTruth(snapshot, graph, events),
    timeline: buildEvidenceTimeline(snapshot, events),
    sourceErrors: query.data?.sourceErrors ?? [],
    runtimeSuppressedReason: query.data?.runtimeSuppressedReason ?? null,
    generatedAt: query.data?.envelope?.generated_at ?? null,
    refresh: query.refetch,
  };
}
