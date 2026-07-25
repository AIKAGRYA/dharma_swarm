/**
 * DHARMA COMMAND -- Typed fetch helpers for the FastAPI backend.
 */

import type {
  AgentCardIndexPayload,
  AgentCardExportFormat,
  AgentCardOut,
  AgentCardPublicOut,
  AgentOut,
  AnomalyOut,
  ApiResponse,
  ArchiveEntryOut,
  ChatStatusOut,
  HeatmapCell,
  HealthOut,
  ImpactOut,
  LineageEdgeOut,
  ModuleTruthOut,
  OntologyTypeOut,
  RuntimeAssistantsSnapshot,
  RuntimeBackgroundJobsSnapshot,
  RuntimeControlActionRequest,
  RuntimeControlActionResult,
  ProvenanceOut,
  RuntimeGraphSnapshot,
  RuntimeInterruptsSnapshot,
  StigmergyMarkOut,
  SwarmOverview,
  TaskOut,
  TraceOut,
} from "./types";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const DEFAULT_INTERNAL_API_URL = "http://127.0.0.1:8420";

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function defaultApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return "";
  }
  return DEFAULT_INTERNAL_API_URL;
}

const BASE_URL =
  trimTrailingSlash(
    process.env.NEXT_PUBLIC_API_URL ??
      process.env.DHARMA_API_INTERNAL_URL ??
      defaultApiBaseUrl(),
  );

export const API_TRANSPORT_MODE = BASE_URL ? "direct" : "same-origin";

export function apiPath(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${BASE_URL}${normalizedPath}`;
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

async function _fetchWrapped<T>(
  path: string,
  init?: RequestInit,
): Promise<ApiResponse<T>> {
  const url = apiPath(path);

  try {
    const res = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...init?.headers,
      },
    });

    if (!res.ok) {
      const body = await res.text().catch(() => "Unknown error");
      return {
        status: "error",
        data: undefined as unknown as T,
        error: `${res.status} ${res.statusText}: ${body}`,
        timestamp: new Date().toISOString(),
      };
    }

    const json = await res.json();
    if (
      json &&
      typeof json === "object" &&
      "data" in json &&
      "status" in json
    ) {
      return {
        status: String(json.status ?? "ok"),
        data: json.data as T,
        error: String(json.error ?? ""),
        timestamp:
          typeof json.timestamp === "string"
            ? json.timestamp
            : new Date().toISOString(),
      };
    }

    return {
      status: "ok",
      data: json as T,
      error: "",
      timestamp: new Date().toISOString(),
    };
  } catch (err) {
    return {
      status: "error",
      data: undefined as unknown as T,
      error: err instanceof Error ? err.message : String(err),
      timestamp: new Date().toISOString(),
    };
  }
}

// ---------------------------------------------------------------------------
// GET helper
// ---------------------------------------------------------------------------

function apiGet<T>(path: string): Promise<ApiResponse<T>> {
  return _fetchWrapped<T>(path, { method: "GET" });
}

// ---------------------------------------------------------------------------
// POST helper
// ---------------------------------------------------------------------------

function apiPost<T>(path: string, body?: unknown): Promise<ApiResponse<T>> {
  return _fetchWrapped<T>(path, {
    method: "POST",
    body: body != null ? JSON.stringify(body) : undefined,
  });
}

// ---------------------------------------------------------------------------
// Endpoint functions
// ---------------------------------------------------------------------------

// -- Swarm ------------------------------------------------------------------

export function fetchSwarmOverview(): Promise<ApiResponse<SwarmOverview>> {
  return apiGet<SwarmOverview>("/api/overview");
}

// -- Agents -----------------------------------------------------------------

export function fetchAgents(): Promise<ApiResponse<AgentOut[]>> {
  return apiGet<AgentOut[]>("/api/agents");
}

export function fetchAgent(id: string): Promise<ApiResponse<AgentOut>> {
  return apiGet<AgentOut>(`/api/agents/${encodeURIComponent(id)}`);
}

// -- Agent Cards ------------------------------------------------------------

export function fetchAgentCards(): Promise<ApiResponse<AgentCardIndexPayload>> {
  return apiGet<AgentCardIndexPayload>("/api/agent-cards");
}

export function fetchAgentCard(id: string): Promise<ApiResponse<AgentCardOut>> {
  return apiGet<AgentCardOut>(`/api/agent-cards/${encodeURIComponent(id)}`);
}

export function fetchPublicAgentCard(
  id: string,
): Promise<ApiResponse<AgentCardPublicOut>> {
  return apiGet<AgentCardPublicOut>(
    `/api/agent-cards/${encodeURIComponent(id)}/public`,
  );
}

export async function fetchAgentCardExportText(
  id: string,
  format: AgentCardExportFormat,
): Promise<string> {
  const res = await fetch(
    apiPath(
      `/api/agent-cards/${encodeURIComponent(id)}/exports/${encodeURIComponent(format)}`,
    ),
    {
      headers: {
        Accept: "text/plain, text/markdown, text/vcard, application/json",
      },
    },
  );
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(`API ${res.status}: ${res.statusText}`, res.status, body);
  }
  return res.text();
}

// -- Tasks ------------------------------------------------------------------

export function fetchTasks(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<ApiResponse<TaskOut[]>> {
  void params;
  // API serves tasks at /api/commands/tasks
  return apiGet<TaskOut[]>("/api/commands/tasks");
}

export function fetchTask(id: string): Promise<ApiResponse<TaskOut>> {
  void id;
  // No individual task endpoint yet — fetch all and filter client-side
  return apiGet<TaskOut>(`/api/commands/tasks`);
}

export function createTask(body: {
  title: string;
  description?: string;
  priority?: string;
}): Promise<ApiResponse<TaskOut>> {
  return apiPost<TaskOut>("/api/commands/task", body);
}

// -- Health -----------------------------------------------------------------

export function fetchHealth(options?: {
  deep?: boolean;
  runtimeTruth?: boolean;
}): Promise<ApiResponse<HealthOut>> {
  const sp = new URLSearchParams();
  if (options?.deep) sp.set("deep", "true");
  if (options?.runtimeTruth) sp.set("runtime_truth", "true");
  const qs = sp.toString();
  return apiGet<HealthOut>(`/api/health${qs ? `?${qs}` : ""}`);
}

export function fetchRuntimeGraph(params?: {
  session_id?: string;
  task_id?: string;
  topology?: string;
  limit?: number;
  receipt_limit?: number;
}): Promise<ApiResponse<RuntimeGraphSnapshot>> {
  const sp = new URLSearchParams();
  if (params?.session_id) sp.set("session_id", params.session_id);
  if (params?.task_id) sp.set("task_id", params.task_id);
  if (params?.topology) sp.set("topology", params.topology);
  if (params?.limit != null) sp.set("limit", String(params.limit));
  if (params?.receipt_limit != null) sp.set("receipt_limit", String(params.receipt_limit));
  const qs = sp.toString();
  return apiGet<RuntimeGraphSnapshot>(`/api/runtime/graph${qs ? `?${qs}` : ""}`);
}

export function fetchRuntimeInterrupts(params?: {
  session_id?: string;
  status?: string;
  limit?: number;
}): Promise<ApiResponse<RuntimeInterruptsSnapshot>> {
  const sp = new URLSearchParams();
  if (params?.session_id) sp.set("session_id", params.session_id);
  if (params?.status) sp.set("status", params.status);
  if (params?.limit != null) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  return apiGet<RuntimeInterruptsSnapshot>(`/api/runtime/interrupts${qs ? `?${qs}` : ""}`);
}

export function postRuntimeControlAction(
  action: RuntimeControlActionResult["action"],
  body: RuntimeControlActionRequest,
): Promise<ApiResponse<RuntimeControlActionResult>> {
  return apiPost<RuntimeControlActionResult>(
    `/api/runtime/interrupts/${encodeURIComponent(action)}`,
    body,
  );
}

export function approveRuntimeInterrupt(
  body: RuntimeControlActionRequest,
): Promise<ApiResponse<RuntimeControlActionResult>> {
  return postRuntimeControlAction("approve", body);
}

export function rejectRuntimeInterrupt(
  body: RuntimeControlActionRequest,
): Promise<ApiResponse<RuntimeControlActionResult>> {
  return postRuntimeControlAction("reject", body);
}

export function resumeRuntimeInterrupt(
  body: RuntimeControlActionRequest,
): Promise<ApiResponse<RuntimeControlActionResult>> {
  return postRuntimeControlAction("resume", body);
}

export function fetchRuntimeAssistants(params?: {
  limit?: number;
}): Promise<ApiResponse<RuntimeAssistantsSnapshot>> {
  const sp = new URLSearchParams();
  if (params?.limit != null) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  return apiGet<RuntimeAssistantsSnapshot>(`/api/runtime/assistants${qs ? `?${qs}` : ""}`);
}

export function fetchRuntimeBackgroundJobs(params?: {
  limit?: number;
}): Promise<ApiResponse<RuntimeBackgroundJobsSnapshot>> {
  const sp = new URLSearchParams();
  if (params?.limit != null) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  return apiGet<RuntimeBackgroundJobsSnapshot>(
    `/api/runtime/background-jobs${qs ? `?${qs}` : ""}`,
  );
}

export function runtimeEventsStreamPath(params?: {
  session_id?: string;
  ledger_kind?: string;
  event_name?: string;
  limit?: number;
}): string {
  const sp = new URLSearchParams();
  if (params?.session_id) sp.set("session_id", params.session_id);
  if (params?.ledger_kind) sp.set("ledger_kind", params.ledger_kind);
  if (params?.event_name) sp.set("event_name", params.event_name);
  if (params?.limit != null) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  return apiPath(`/api/runtime/events/stream${qs ? `?${qs}` : ""}`);
}

export function backendLivenessPath(): string {
  return apiPath("/api/verify/health");
}

export function fetchAnomalies(): Promise<ApiResponse<AnomalyOut[]>> {
  return apiGet<AnomalyOut[]>("/api/health/anomalies");
}

// -- Evolution --------------------------------------------------------------

export function fetchEvolutionArchive(params?: {
  limit?: number;
  offset?: number;
}): Promise<ApiResponse<ArchiveEntryOut[]>> {
  const sp = new URLSearchParams();
  if (params?.limit != null) sp.set("limit", String(params.limit));
  if (params?.offset != null) sp.set("offset", String(params.offset));
  const qs = sp.toString();
  return apiGet<ArchiveEntryOut[]>(`/api/evolution/archive${qs ? `?${qs}` : ""}`);
}

export function fetchFitnessTrend(): Promise<
  ApiResponse<{ generation: number; fitness: number }[]>
> {
  return apiGet<{ generation: number; fitness: number }[]>(
    "/api/evolution/fitness-trend",
  );
}

// -- Traces / Lineage -------------------------------------------------------

export function fetchTraces(params?: {
  agent_id?: string;
  task_id?: string;
  limit?: number;
}): Promise<ApiResponse<TraceOut[]>> {
  const sp = new URLSearchParams();
  if (params?.limit != null) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  return apiGet<TraceOut[]>(`/api/commands/traces${qs ? `?${qs}` : ""}`);
}

export function fetchLineage(entryId: string): Promise<ApiResponse<LineageEdgeOut[]>> {
  return apiGet<LineageEdgeOut[]>(
    `/api/evolution/lineage/${encodeURIComponent(entryId)}`,
  );
}

// -- Ontology ---------------------------------------------------------------

export function fetchOntology(): Promise<ApiResponse<OntologyTypeOut[]>> {
  return apiGet<OntologyTypeOut[]>("/api/ontology/types");
}

// -- Stigmergy --------------------------------------------------------------

export function fetchStigmergy(params?: {
  limit?: number;
  min_salience?: number;
}): Promise<ApiResponse<StigmergyMarkOut[]>> {
  const sp = new URLSearchParams();
  if (params?.limit != null) sp.set("limit", String(params.limit));
  if (params?.min_salience != null) sp.set("min_salience", String(params.min_salience));
  const qs = sp.toString();
  return apiGet<StigmergyMarkOut[]>(`/api/stigmergy/marks${qs ? `?${qs}` : ""}`);
}

// -- Heatmap ----------------------------------------------------------------

export function fetchHeatmap(windowHours = 168): Promise<ApiResponse<HeatmapCell[]>> {
  return apiGet<HeatmapCell[]>(
    `/api/stigmergy/heatmap?window_hours=${encodeURIComponent(String(windowHours))}`,
  );
}

// -- Provenance -------------------------------------------------------------

export function fetchProvenance(
  artifactId: string,
): Promise<ApiResponse<ProvenanceOut>> {
  return apiGet<ProvenanceOut>(
    `/api/lineage/${encodeURIComponent(artifactId)}/provenance`,
  );
}

// -- Impact -----------------------------------------------------------------

export function fetchImpact(
  artifactId: string,
): Promise<ApiResponse<ImpactOut>> {
  return apiGet<ImpactOut>(
    `/api/lineage/${encodeURIComponent(artifactId)}/impact`,
  );
}

// -- Chat -------------------------------------------------------------------

export function fetchChatStatus(): Promise<ApiResponse<ChatStatusOut>> {
  return apiGet<ChatStatusOut>("/api/chat/status");
}

// -- Truth modules ----------------------------------------------------------

export function fetchModules(): Promise<ApiResponse<ModuleTruthOut[]>> {
  return apiGet<ModuleTruthOut[]>("/api/modules");
}

// ---------------------------------------------------------------------------
// Export base URL for WebSocket derivation
// ---------------------------------------------------------------------------

export function wsBaseUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_WS_URL?.trim();
  if (explicit) {
    return trimTrailingSlash(explicit);
  }

  if (BASE_URL) {
    return BASE_URL.replace(/^http/, "ws");
  }

  if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}`;
  }

  return DEFAULT_INTERNAL_API_URL.replace(/^http/, "ws");
}

export { BASE_URL };

// ---------------------------------------------------------------------------
// Legacy apiFetch -- backward-compatible with existing hooks.
// Returns T directly (unwrapped) and throws on failure.
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  body: string;

  constructor(message: string, status: number, body: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = apiPath(path);
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(`API ${res.status}: ${res.statusText}`, res.status, body);
  }

  const json = await res.json();
  // Backend wraps responses in {status, data, error, timestamp}
  // Unwrap if present, otherwise return as-is
  if (json && typeof json === "object" && "data" in json && "status" in json) {
    if (json.status === "error") {
      throw new ApiError(json.error || "Unknown error", res.status, JSON.stringify(json));
    }
    return json.data as T;
  }
  return json as T;
}
