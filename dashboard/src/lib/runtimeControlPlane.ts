import type {
  ApiResponse,
  ChatProfileOut,
  ChatStatusOut,
  HealthOut,
  RuntimeAssistantsSnapshot,
  RuntimeBackgroundJobsSnapshot,
  RuntimeControlActionRequest,
  RuntimeControlActionResult,
  RuntimeGraphSnapshot,
  RuntimeInterruptControlEvent,
  RuntimeInterruptsSnapshot,
} from "./types";

export type RuntimeControlPlaneStatusKind = "ok" | "warn" | "error" | "muted";
export type RuntimeControlActionKind = RuntimeControlActionResult["action"];

export interface RuntimeControlActionOption {
  action: RuntimeControlActionKind;
  label: string;
  title: string;
}

export interface RuntimeControlPlaneData {
  chatStatus: ChatStatusOut | null;
  health: HealthOut | null;
  runtimeGraph: RuntimeGraphSnapshot | null;
  runtimeInterrupts: RuntimeInterruptsSnapshot | null;
  runtimeAssistants: RuntimeAssistantsSnapshot | null;
  runtimeBackgroundJobs: RuntimeBackgroundJobsSnapshot | null;
  chatError: string | null;
  healthError: string | null;
  runtimeGraphError: string | null;
  runtimeInterruptError: string | null;
  runtimeAssistantsError: string | null;
  runtimeBackgroundJobsError: string | null;
  error: string | null;
}

export interface RuntimeControlPlaneSnapshot {
  chatReady: boolean;
  healthReady: boolean;
  statusKind: RuntimeControlPlaneStatusKind;
  statusLabel: string;
  detail: string;
  healthStatusLabel: string;
  defaultProfile: ChatProfileOut | null;
  totalProfileCount: number;
  availableProfileCount: number;
  unavailableProfileCount: number;
  persistentSessions: boolean;
  contractVersion: string;
  sessionFeedReady: boolean;
  sessionFeedLabel: string;
  sessionFeedPathTemplate: string | null;
  runtimeGraphReady: boolean;
  runtimeGraphStatusLabel: string;
  runtimeGraphDetail: string;
  runtimeGraphNodeCount: number;
  runtimeGraphEdgeCount: number;
  runtimeGraphActiveRunCount: number;
  runtimeGraphCheckpointCount: number;
  runtimeGraphActiveAgentCount: number;
  runtimeInterruptReady: boolean;
  runtimeInterruptStatusLabel: string;
  runtimeInterruptDetail: string;
  runtimeControlEventCount: number;
  runtimePendingInterruptCount: number;
  runtimeHumanApprovalRequiredCount: number;
  runtimeApprovedCount: number;
  runtimeResumedCount: number;
  runtimeAssistantsReady: boolean;
  runtimeAssistantsStatusLabel: string;
  runtimeAssistantsDetail: string;
  runtimeAssistantCount: number;
  runtimeConfigurationCount: number;
  runtimeActiveAssistantCount: number;
  runtimeBackgroundReady: boolean;
  runtimeBackgroundStatusLabel: string;
  runtimeBackgroundDetail: string;
  runtimeCronJobCount: number;
  runtimeEnabledCronJobCount: number;
  runtimeBackgroundRunCount: number;
  runtimeActiveBackgroundRunCount: number;
  agentCount: number;
  anomalyCount: number;
  tracesLastHour: number;
  failureRateLabel: string;
  meanFitnessLabel: string;
}

function firstNonEmpty(values: Array<string | null | undefined>): string | null {
  const normalized = values
    .map((value) => value?.trim())
    .filter((value): value is string => Boolean(value));
  if (normalized.length === 0) return null;
  return normalized.join(" | ");
}

function nonEmpty(value: string | null | undefined): string | undefined {
  const normalized = value?.trim();
  return normalized ? normalized : undefined;
}

function isPendingControlEvent(event: RuntimeInterruptControlEvent): boolean {
  const status = event.status.trim().toLowerCase();
  return status === "pending" || status === "requested" || status === "requires_human";
}

export function runtimeControlActionOptions(
  event: RuntimeInterruptControlEvent,
): RuntimeControlActionOption[] {
  if (!isPendingControlEvent(event)) {
    return [];
  }

  const options: RuntimeControlActionOption[] = [];
  if (nonEmpty(event.approval_id) || event.requires_human) {
    options.push(
      {
        action: "approve",
        label: "Approve",
        title: "Approve this runtime interrupt",
      },
      {
        action: "reject",
        label: "Reject",
        title: "Reject this runtime interrupt",
      },
    );
  }
  if (nonEmpty(event.resume_token)) {
    options.push({
      action: "resume",
      label: "Resume",
      title: "Resume this runtime run",
    });
  }
  return options;
}

export function buildRuntimeControlActionRequest(
  event: RuntimeInterruptControlEvent,
  action: RuntimeControlActionKind,
  actor = "runtime-dashboard",
): RuntimeControlActionRequest {
  return {
    session_id: nonEmpty(event.session_id),
    task_id: nonEmpty(event.task_id),
    run_id: nonEmpty(event.run_id),
    approval_id: nonEmpty(event.approval_id),
    interrupt_id: nonEmpty(event.interrupt_id),
    resume_token: nonEmpty(event.resume_token),
    actor,
    reason: `Runtime cockpit ${action} for ${event.event_id}`,
    payload: {
      source: "dashboard.runtime",
      control_event_id: event.event_id,
      checkpoint_id: event.checkpoint_id,
      control_type: event.control_type,
    },
  };
}

function resolveDefaultProfile(chatStatus: ChatStatusOut | null): ChatProfileOut | null {
  const profiles = chatStatus?.profiles ?? [];
  if (profiles.length === 0) return null;
  return (
    profiles.find((profile) => profile.id === chatStatus?.default_profile_id) ??
    profiles[0] ??
    null
  );
}

function sessionFeedPathTemplate(chatStatus: ChatStatusOut | null): string | null {
  const template = chatStatus?.chat_ws_path_template?.trim();
  return template ? template : null;
}

function hasRuntimeSignal(data: RuntimeControlPlaneData): boolean {
  return Boolean(
    data.chatStatus ||
      data.health ||
      data.runtimeGraph ||
      data.runtimeInterrupts ||
      data.runtimeAssistants ||
      data.runtimeBackgroundJobs ||
      data.chatError ||
      data.healthError ||
      data.runtimeGraphError ||
      data.runtimeInterruptError ||
      data.runtimeAssistantsError ||
      data.runtimeBackgroundJobsError ||
      data.error,
  );
}

function hasUnscopedRuntimeQueryFailure(data: RuntimeControlPlaneData): boolean {
  return Boolean(
    data.error &&
      !data.chatStatus &&
      !data.health &&
      !data.runtimeGraph &&
      !data.runtimeInterrupts &&
      !data.runtimeAssistants &&
      !data.runtimeBackgroundJobs &&
      !data.chatError &&
      !data.healthError,
  );
}

const TRANSPORT_FAILURE_PATTERNS = [
  /\bfetch failed\b/i,
  /\bfailed to fetch\b/i,
  /\bnetwork error\b/i,
  /\bnetworkerror\b/i,
  /\bnetwork timeout\b/i,
  /\btimed out\b/i,
  /\btimeout\b/i,
  /\beconnrefused\b/i,
  /\beconnreset\b/i,
  /\benotfound\b/i,
  /\bconnection refused\b/i,
  /\bsocket hang up\b/i,
  /\bupstream connect error\b/i,
  /\bbad gateway\b/i,
  /\bservice unavailable\b/i,
  /\bgateway timeout\b/i,
  /^502\b/i,
  /^503\b/i,
  /^504\b/i,
] as const;

function isTransportFailureError(error: string | null): boolean {
  if (!error) return false;
  return TRANSPORT_FAILURE_PATTERNS.some((pattern) => pattern.test(error));
}

function hasMirroredTransportQueryFailure(data: RuntimeControlPlaneData): boolean {
  return Boolean(
    !data.chatStatus &&
      !data.health &&
      !data.runtimeGraph &&
      isTransportFailureError(data.chatError) &&
      isTransportFailureError(data.healthError),
  );
}

function hasRuntimeTransportFailure(data: RuntimeControlPlaneData): boolean {
  return hasUnscopedRuntimeQueryFailure(data) || hasMirroredTransportQueryFailure(data);
}

function runtimeTransportFailureSummary(data: RuntimeControlPlaneData): string {
  const endpointErrors = [data.chatError, data.healthError]
    .map((value) => value?.trim())
    .filter((value): value is string => Boolean(value));

  if (endpointErrors.length > 0) {
    const uniqueErrors = endpointErrors.filter(
      (value, index, values) =>
        values.findIndex((entry) => entry.toLowerCase() === value.toLowerCase()) === index,
    );
    return uniqueErrors.join(" | ");
  }

  return data.error?.trim() || "unknown transport failure";
}

function countAvailableProfiles(chatStatus: ChatStatusOut | null): number {
  return (chatStatus?.profiles ?? []).filter((profile) => profile.available !== false).length;
}

function hasAdvertisedLaneFailure(data: RuntimeControlPlaneData): boolean {
  const profiles = data.chatStatus?.profiles ?? [];
  return profiles.length > 0 && countAvailableProfiles(data.chatStatus) === 0;
}

function hasUnavailableDefaultProfile(data: RuntimeControlPlaneData): boolean {
  const defaultProfile = resolveDefaultProfile(data.chatStatus);

  return Boolean(
    data.chatStatus?.ready &&
      defaultProfile &&
      defaultProfile.available === false &&
      countAvailableProfiles(data.chatStatus) > 0,
  );
}

function sessionFeedAdvertised(data: RuntimeControlPlaneData): boolean {
  return Boolean(sessionFeedPathTemplate(data.chatStatus));
}

function runtimeTruthFailed(data: RuntimeControlPlaneData): boolean {
  return data.health?.runtime_truth?.passed === false;
}

function runtimeTruthFailureDetail(data: RuntimeControlPlaneData): string {
  const truth = data.health?.runtime_truth;
  if (!truth) return "Runtime truth closeout has not reported.";
  const failedChecks = (truth.checks ?? [])
    .filter((check) => check.passed === false || check.status === "fail")
    .map((check) => {
      const id = check.id?.trim() || "unknown_check";
      const evidence = check.evidence?.trim();
      return evidence ? `${id}: ${evidence}` : id;
    });
  if (failedChecks.length > 0) {
    return `Runtime truth closeout is red: ${failedChecks.slice(0, 3).join(" | ")}`;
  }
  if (truth.error) {
    return `Runtime truth closeout failed to run: ${truth.error}`;
  }
  return `Runtime truth closeout is ${truth.status ?? "unproven"}.`;
}

function blockedLaneDetail(data: RuntimeControlPlaneData): string {
  const defaultProfile = resolveDefaultProfile(data.chatStatus);
  const note = defaultProfile?.status_note?.trim();
  const availability =
    defaultProfile?.availability_kind?.replace(/_/g, " ").trim() ?? "";

  if (defaultProfile && note) {
    return `Chat status is live, but no advertised lanes are currently available. Default lane ${defaultProfile.label} is blocked: ${note}`;
  }

  if (defaultProfile && availability) {
    return `Chat status is live, but no advertised lanes are currently available. Default lane ${defaultProfile.label} is blocked: ${availability}.`;
  }

  if (defaultProfile) {
    return `Chat status is live, but no advertised lanes are currently available. Default lane ${defaultProfile.label} is blocked.`;
  }

  return "Chat status is live, but no advertised lanes are currently available.";
}

function unavailableDefaultLaneDetail(data: RuntimeControlPlaneData): string {
  const defaultProfile = resolveDefaultProfile(data.chatStatus);
  const fallbackCount = countAvailableProfiles(data.chatStatus);
  const fallbackLabel =
    fallbackCount === 1
      ? "1 fallback lane remains live."
      : `${fallbackCount} fallback lanes remain live.`;

  if (!defaultProfile) {
    return `The default lane is blocked, but ${fallbackLabel.toLowerCase()}`;
  }

  const note = defaultProfile.status_note?.trim();
  const availability =
    defaultProfile.availability_kind?.replace(/_/g, " ").trim() ?? "";

  if (note) {
    return `Default lane ${defaultProfile.label} is blocked: ${note} ${fallbackLabel}`;
  }

  if (availability) {
    return `Default lane ${defaultProfile.label} is blocked: ${availability}. ${fallbackLabel}`;
  }

  return `Default lane ${defaultProfile.label} is blocked. ${fallbackLabel}`;
}

function appendSessionFeedDetail(
  detail: string,
  data: RuntimeControlPlaneData,
): string {
  if (!data.chatStatus?.ready || sessionFeedAdvertised(data)) {
    return detail;
  }

  return `${detail} /api/chat/status is not advertising chat_ws_path_template for the session relay.`;
}

function runtimeStatusKind(data: RuntimeControlPlaneData): RuntimeControlPlaneStatusKind {
  if (!hasRuntimeSignal(data)) return "muted";
  if (hasRuntimeTransportFailure(data)) return "error";
  if (!data.chatStatus?.ready) return "error";
  if (hasAdvertisedLaneFailure(data)) return "error";
  if (runtimeTruthFailed(data)) return "error";
  if (!data.health) return "warn";
  if (data.health?.overall_status === "degraded") return "warn";
  if (hasUnavailableDefaultProfile(data)) return "warn";
  if (!sessionFeedAdvertised(data)) return "warn";
  if (
    data.runtimeInterruptError ||
    data.runtimeAssistantsError ||
    data.runtimeBackgroundJobsError
  ) {
    return "warn";
  }
  return "ok";
}

function runtimeStatusLabel(data: RuntimeControlPlaneData): string {
  if (!hasRuntimeSignal(data)) return "syncing";
  if (hasRuntimeTransportFailure(data)) return "runtime unreachable";
  if (!data.chatStatus?.ready) return "chat unavailable";
  if (hasAdvertisedLaneFailure(data)) return "lanes unavailable";
  if (runtimeTruthFailed(data)) return "runtime truth red";
  if (!data.health) return "health unavailable";
  if (data.health?.overall_status === "degraded") return "degraded";
  if (hasUnavailableDefaultProfile(data)) return "default lane unavailable";
  if (!sessionFeedAdvertised(data)) return "session feed unavailable";
  if (data.runtimeInterruptError) return "controls unavailable";
  if (data.runtimeAssistantsError) return "assistants unavailable";
  if (data.runtimeBackgroundJobsError) return "background unavailable";
  return data.health?.overall_status ?? "ok";
}

function runtimeDetail(data: RuntimeControlPlaneData): string {
  if (!hasRuntimeSignal(data)) {
    return "Waiting for the canonical runtime sources to report.";
  }
  if (hasRuntimeTransportFailure(data)) {
    return `Canonical runtime query failed: ${runtimeTransportFailureSummary(data)}`;
  }
  if (!data.chatStatus?.ready) {
    if (data.chatError) {
      return `Chat status unavailable: ${data.chatError}`;
    }
    return "The canonical chat lanes are not yet advertised by /api/chat/status.";
  }
  if (hasAdvertisedLaneFailure(data)) {
    return blockedLaneDetail(data);
  }
  if (runtimeTruthFailed(data)) {
    return appendSessionFeedDetail(runtimeTruthFailureDetail(data), data);
  }
  if (!data.health) {
    if (data.healthError) {
      return appendSessionFeedDetail(
        `Chat lanes are live, but /api/health is unavailable: ${data.healthError}`,
        data,
      );
    }
    return appendSessionFeedDetail(
      "Chat lanes are live, but /api/health has not reported yet.",
      data,
    );
  }
  if (data.health?.overall_status === "degraded") {
    return appendSessionFeedDetail(
      "Runtime health is degraded; keep the shell on canonical routes while providers recover.",
      data,
    );
  }
  if (hasUnavailableDefaultProfile(data)) {
    return appendSessionFeedDetail(unavailableDefaultLaneDetail(data), data);
  }
  if (data.runtimeInterruptError) {
    return `Runtime controls are partially unavailable: ${data.runtimeInterruptError}`;
  }
  if (data.runtimeAssistantsError) {
    return `Assistant configuration state is partially unavailable: ${data.runtimeAssistantsError}`;
  }
  if (data.runtimeBackgroundJobsError) {
    return `Background runtime state is partially unavailable: ${data.runtimeBackgroundJobsError}`;
  }
  return appendSessionFeedDetail(
    "Chat status and backend health agree on the canonical runtime path.",
    data,
  );
}

function formatFailureRate(health: HealthOut | null): string {
  if (!health) return "unknown";
  return `${(health.failure_rate * 100).toFixed(1)}%`;
}

function formatMeanFitness(health: HealthOut | null): string {
  if (health?.mean_fitness == null) return "n/a";
  return health.mean_fitness.toFixed(2);
}

function healthStatusLabel(data: RuntimeControlPlaneData): string {
  if (hasRuntimeTransportFailure(data)) {
    return "runtime unreachable";
  }
  if (!data.health) {
    return data.healthError ? "health unavailable" : "awaiting health";
  }
  return `${data.health.anomalies.length} anomalies · ${formatMeanFitness(data.health)} fit`;
}

function sessionFeedLabel(data: RuntimeControlPlaneData): string {
  if (!hasRuntimeSignal(data)) return "awaiting session rail";
  if (!data.chatStatus?.ready) return "chat unavailable";
  return sessionFeedPathTemplate(data.chatStatus) ?? "not advertised";
}

function runtimeGraphStatusLabel(data: RuntimeControlPlaneData): string {
  if (data.runtimeGraph) {
    const count = data.runtimeGraph.summary.topology_state_count;
    return count === 1 ? "1 graph" : `${count} graphs`;
  }
  if (data.runtimeGraphError) return "graph unavailable";
  return "awaiting graph";
}

function runtimeGraphDetail(data: RuntimeControlPlaneData): string {
  if (data.runtimeGraph) {
    const summary = data.runtimeGraph.summary;
    return `${summary.active_run_count} active runs, ${summary.active_agent_count} active agents, ${summary.checkpoint_count} checkpoints, ${summary.receipt_count} receipts.`;
  }
  if (data.runtimeGraphError) {
    return `Runtime graph unavailable: ${data.runtimeGraphError}`;
  }
  return "Awaiting RuntimeStateStore graph snapshot.";
}

function runtimeInterruptStatusLabel(data: RuntimeControlPlaneData): string {
  if (data.runtimeInterrupts) {
    const pending = data.runtimeInterrupts.summary.pending_interrupt_count;
    return pending === 1 ? "1 pending" : `${pending} pending`;
  }
  if (data.runtimeInterruptError) return "controls unavailable";
  return "awaiting controls";
}

function runtimeInterruptDetail(data: RuntimeControlPlaneData): string {
  if (data.runtimeInterrupts) {
    const summary = data.runtimeInterrupts.summary;
    return `${summary.control_event_count} control events, ${summary.human_approval_required_count} human approvals required, ${summary.approved_count} approved, ${summary.resumed_count} resumed.`;
  }
  if (data.runtimeInterruptError) {
    return `Runtime interrupts unavailable: ${data.runtimeInterruptError}`;
  }
  return "Awaiting interrupt, resume, and approval state.";
}

function runtimeAssistantsStatusLabel(data: RuntimeControlPlaneData): string {
  if (data.runtimeAssistants) {
    const count = data.runtimeAssistants.summary.assistant_count;
    return count === 1 ? "1 assistant" : `${count} assistants`;
  }
  if (data.runtimeAssistantsError) return "assistants unavailable";
  return "awaiting assistants";
}

function runtimeAssistantsDetail(data: RuntimeControlPlaneData): string {
  if (data.runtimeAssistants) {
    const summary = data.runtimeAssistants.summary;
    return `${summary.configuration_count} configurations, ${summary.active_assistant_count} active assistants.`;
  }
  if (data.runtimeAssistantsError) {
    return `Runtime assistants unavailable: ${data.runtimeAssistantsError}`;
  }
  return "Awaiting assistant and configuration state.";
}

function runtimeBackgroundStatusLabel(data: RuntimeControlPlaneData): string {
  if (data.runtimeBackgroundJobs) {
    const count = data.runtimeBackgroundJobs.summary.enabled_cron_job_count;
    return count === 1 ? "1 enabled" : `${count} enabled`;
  }
  if (data.runtimeBackgroundJobsError) return "background unavailable";
  return "awaiting background";
}

function runtimeBackgroundDetail(data: RuntimeControlPlaneData): string {
  if (data.runtimeBackgroundJobs) {
    const summary = data.runtimeBackgroundJobs.summary;
    return `${summary.cron_job_count} cron jobs, ${summary.background_run_count} background runs, ${summary.background_event_count} events.`;
  }
  if (data.runtimeBackgroundJobsError) {
    return `Runtime background jobs unavailable: ${data.runtimeBackgroundJobsError}`;
  }
  return "Awaiting cron and background run state.";
}

export function normalizeRuntimeControlPlaneResponses(
  chatResponse: ApiResponse<ChatStatusOut>,
  healthResponse: ApiResponse<HealthOut>,
  runtimeGraphResponse?: ApiResponse<RuntimeGraphSnapshot>,
  runtimeInterruptResponse?: ApiResponse<RuntimeInterruptsSnapshot>,
  runtimeAssistantsResponse?: ApiResponse<RuntimeAssistantsSnapshot>,
  runtimeBackgroundJobsResponse?: ApiResponse<RuntimeBackgroundJobsSnapshot>,
): RuntimeControlPlaneData {
  const chatError =
    chatResponse.status === "ok" ? null : chatResponse.error || "chat status unavailable";
  const healthError =
    healthResponse.status === "ok" ? null : healthResponse.error || "health unavailable";
  const runtimeGraphError =
    runtimeGraphResponse == null || runtimeGraphResponse.status === "ok"
      ? null
      : runtimeGraphResponse.error || "runtime graph unavailable";
  const runtimeInterruptError =
    runtimeInterruptResponse == null || runtimeInterruptResponse.status === "ok"
      ? null
      : runtimeInterruptResponse.error || "runtime interrupts unavailable";
  const runtimeAssistantsError =
    runtimeAssistantsResponse == null || runtimeAssistantsResponse.status === "ok"
      ? null
      : runtimeAssistantsResponse.error || "runtime assistants unavailable";
  const runtimeBackgroundJobsError =
    runtimeBackgroundJobsResponse == null || runtimeBackgroundJobsResponse.status === "ok"
      ? null
      : runtimeBackgroundJobsResponse.error || "runtime background jobs unavailable";

  return {
    chatStatus: chatResponse.status === "ok" ? chatResponse.data : null,
    health: healthResponse.status === "ok" ? healthResponse.data : null,
    runtimeGraph:
      runtimeGraphResponse?.status === "ok" ? runtimeGraphResponse.data : null,
    runtimeInterrupts:
      runtimeInterruptResponse?.status === "ok" ? runtimeInterruptResponse.data : null,
    runtimeAssistants:
      runtimeAssistantsResponse?.status === "ok" ? runtimeAssistantsResponse.data : null,
    runtimeBackgroundJobs:
      runtimeBackgroundJobsResponse?.status === "ok"
        ? runtimeBackgroundJobsResponse.data
        : null,
    chatError,
    healthError,
    runtimeGraphError,
    runtimeInterruptError,
    runtimeAssistantsError,
    runtimeBackgroundJobsError,
    error: firstNonEmpty([
      chatError,
      healthError,
      runtimeGraphError,
      runtimeInterruptError,
      runtimeAssistantsError,
      runtimeBackgroundJobsError,
    ]),
  };
}

export function buildRuntimeControlPlaneSnapshot(
  data: RuntimeControlPlaneData,
): RuntimeControlPlaneSnapshot {
  const profiles = data.chatStatus?.profiles ?? [];
  const availableProfileCount = countAvailableProfiles(data.chatStatus);
  const defaultProfile = resolveDefaultProfile(data.chatStatus);
  const advertisedSessionFeedPathTemplate = sessionFeedPathTemplate(data.chatStatus);

  return {
    chatReady: Boolean(data.chatStatus?.ready),
    healthReady: Boolean(data.health),
    statusKind: runtimeStatusKind(data),
    statusLabel: runtimeStatusLabel(data),
    detail: runtimeDetail(data),
    healthStatusLabel: healthStatusLabel(data),
    defaultProfile,
    totalProfileCount: profiles.length,
    availableProfileCount,
    unavailableProfileCount: Math.max(0, profiles.length - availableProfileCount),
    persistentSessions: Boolean(data.chatStatus?.persistent_sessions),
    contractVersion: data.chatStatus?.chat_contract_version ?? "unknown",
    sessionFeedReady: Boolean(data.chatStatus?.ready) && Boolean(advertisedSessionFeedPathTemplate),
    sessionFeedLabel: sessionFeedLabel(data),
    sessionFeedPathTemplate: advertisedSessionFeedPathTemplate,
    runtimeGraphReady: Boolean(data.runtimeGraph),
    runtimeGraphStatusLabel: runtimeGraphStatusLabel(data),
    runtimeGraphDetail: runtimeGraphDetail(data),
    runtimeGraphNodeCount: data.runtimeGraph?.summary.node_count ?? 0,
    runtimeGraphEdgeCount: data.runtimeGraph?.summary.edge_count ?? 0,
    runtimeGraphActiveRunCount: data.runtimeGraph?.summary.active_run_count ?? 0,
    runtimeGraphCheckpointCount: data.runtimeGraph?.summary.checkpoint_count ?? 0,
    runtimeGraphActiveAgentCount: data.runtimeGraph?.summary.active_agent_count ?? 0,
    runtimeInterruptReady: Boolean(data.runtimeInterrupts),
    runtimeInterruptStatusLabel: runtimeInterruptStatusLabel(data),
    runtimeInterruptDetail: runtimeInterruptDetail(data),
    runtimeControlEventCount: data.runtimeInterrupts?.summary.control_event_count ?? 0,
    runtimePendingInterruptCount: data.runtimeInterrupts?.summary.pending_interrupt_count ?? 0,
    runtimeHumanApprovalRequiredCount:
      data.runtimeInterrupts?.summary.human_approval_required_count ?? 0,
    runtimeApprovedCount: data.runtimeInterrupts?.summary.approved_count ?? 0,
    runtimeResumedCount: data.runtimeInterrupts?.summary.resumed_count ?? 0,
    runtimeAssistantsReady: Boolean(data.runtimeAssistants),
    runtimeAssistantsStatusLabel: runtimeAssistantsStatusLabel(data),
    runtimeAssistantsDetail: runtimeAssistantsDetail(data),
    runtimeAssistantCount: data.runtimeAssistants?.summary.assistant_count ?? 0,
    runtimeConfigurationCount: data.runtimeAssistants?.summary.configuration_count ?? 0,
    runtimeActiveAssistantCount:
      data.runtimeAssistants?.summary.active_assistant_count ?? 0,
    runtimeBackgroundReady: Boolean(data.runtimeBackgroundJobs),
    runtimeBackgroundStatusLabel: runtimeBackgroundStatusLabel(data),
    runtimeBackgroundDetail: runtimeBackgroundDetail(data),
    runtimeCronJobCount: data.runtimeBackgroundJobs?.summary.cron_job_count ?? 0,
    runtimeEnabledCronJobCount:
      data.runtimeBackgroundJobs?.summary.enabled_cron_job_count ?? 0,
    runtimeBackgroundRunCount:
      data.runtimeBackgroundJobs?.summary.background_run_count ?? 0,
    runtimeActiveBackgroundRunCount:
      data.runtimeBackgroundJobs?.summary.active_background_run_count ?? 0,
    agentCount: data.health?.agent_health.length ?? 0,
    anomalyCount: data.health?.anomalies.length ?? 0,
    tracesLastHour: data.health?.traces_last_hour ?? 0,
    failureRateLabel: formatFailureRate(data.health),
    meanFitnessLabel: formatMeanFitness(data.health),
  };
}
