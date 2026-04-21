/**
 * DHARMA COMMAND -- Typed fetch helpers for the FastAPI backend.
 */

import type {
  AgentDetailPayload,
  AgentMemoryOut,
  AgentNoteOut,
  AgentOut,
  AnomalyOut,
  ApiResponse,
  ArchiveEntryOut,
  ChatHistoryPayload,
  ChatStatusOut,
  ConversationEntry,
  DagData,
  EvolutionStats,
  HeatmapCell,
  HealthOut,
  HotPath,
  ImpactOut,
  LineageEdgeOut,
  ModuleTruthOut,
  OntologyDetailOut,
  OntologyGraphData,
  OntologyTypeOut,
  PromiseEntry,
  ProvenanceOut,
  RoutingManifestOut,
  StigmergyGraphData,
  StigmergyMarkOut,
  SupervisorStatus,
  SwarmOverview,
  TaskOut,
  TraceOut,
  VizEvent,
  VizSnapshot,
} from "./types";
import { authorizedHeaders } from "./auth";

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
      headers: authorizedHeaders({
        "Content-Type": "application/json",
        Accept: "application/json",
        ...init?.headers,
      }),
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

export function fetchHealth(): Promise<ApiResponse<HealthOut>> {
  return apiGet<HealthOut>("/api/health");
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

// -- Routing ---------------------------------------------------------------

export function fetchRoutingManifest(params?: {
  provider?: string;
  model?: string;
  strategy?: string;
}): Promise<ApiResponse<RoutingManifestOut>> {
  const sp = new URLSearchParams();
  if (params?.provider) sp.set("provider", params.provider);
  if (params?.model) sp.set("model", params.model);
  if (params?.strategy) sp.set("strategy", params.strategy);
  const qs = sp.toString();
  return apiGet<RoutingManifestOut>(`/api/routing/manifest${qs ? `?${qs}` : ""}`);
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
// Agent detail & scoped endpoints
// ---------------------------------------------------------------------------

export function fetchAgentDetail(
  id: string,
): Promise<ApiResponse<AgentDetailPayload>> {
  return apiGet<AgentDetailPayload>(
    `/api/agents/${encodeURIComponent(id)}/detail`,
  );
}

export function fetchAgentMemory(
  id: string,
): Promise<ApiResponse<AgentMemoryOut>> {
  return apiGet<AgentMemoryOut>(
    `/api/agents/${encodeURIComponent(id)}/memory`,
  );
}

export function fetchAgentChatHistory(
  id: string,
  limit = 50,
): Promise<ApiResponse<ChatHistoryPayload>> {
  return apiGet<ChatHistoryPayload>(
    `/api/agents/${encodeURIComponent(id)}/chat/history?limit=${limit}`,
  );
}

export function fetchAgentNotes(
  id: string,
): Promise<ApiResponse<{ notes: AgentNoteOut[] }>> {
  return apiGet<{ notes: AgentNoteOut[] }>(
    `/api/agents/${encodeURIComponent(id)}/notes`,
  );
}

export function fetchAgentProfile(
  id: string,
): Promise<ApiResponse<Record<string, unknown>>> {
  return apiGet<Record<string, unknown>>(
    `/api/agents/${encodeURIComponent(id)}/profile`,
  );
}

export function spawnAgent(body: {
  name: string;
  role?: string;
  model?: string;
  provider?: string;
}): Promise<ApiResponse<AgentOut>> {
  return apiPost<AgentOut>("/api/agents/spawn", body);
}

export function stopAgent(id: string): Promise<ApiResponse<{ stopped: string }>> {
  return apiPost<{ stopped: string }>(
    `/api/agents/${encodeURIComponent(id)}/stop`,
  );
}

// ---------------------------------------------------------------------------
// Evolution (additional)
// ---------------------------------------------------------------------------

export function fetchEvolutionDag(): Promise<ApiResponse<DagData>> {
  return apiGet<DagData>("/api/evolution/dag");
}

export function fetchEvolutionStats(): Promise<ApiResponse<EvolutionStats>> {
  return apiGet<EvolutionStats>("/api/evolution/stats");
}

export function triggerEvolution(body?: {
  component?: string;
}): Promise<ApiResponse<Record<string, unknown>>> {
  return apiPost<Record<string, unknown>>("/api/commands/evolve", body);
}

// ---------------------------------------------------------------------------
// Stigmergy (additional)
// ---------------------------------------------------------------------------

export function fetchStigmergyGraph(): Promise<ApiResponse<StigmergyGraphData>> {
  return apiGet<StigmergyGraphData>("/api/stigmergy/graph");
}

export function fetchStigmergyHotPaths(params?: {
  window_hours?: number;
  min_marks?: number;
}): Promise<ApiResponse<HotPath[]>> {
  const sp = new URLSearchParams();
  if (params?.window_hours != null) sp.set("window_hours", String(params.window_hours));
  if (params?.min_marks != null) sp.set("min_marks", String(params.min_marks));
  const qs = sp.toString();
  return apiGet<HotPath[]>(`/api/stigmergy/hot-paths${qs ? `?${qs}` : ""}`);
}

export function fetchStigmergyHighSalience(params?: {
  threshold?: number;
  limit?: number;
}): Promise<ApiResponse<StigmergyMarkOut[]>> {
  const sp = new URLSearchParams();
  if (params?.threshold != null) sp.set("threshold", String(params.threshold));
  if (params?.limit != null) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  return apiGet<StigmergyMarkOut[]>(`/api/stigmergy/high-salience${qs ? `?${qs}` : ""}`);
}

export function fetchStigmergyDensity(): Promise<ApiResponse<{ density: number }>> {
  return apiGet<{ density: number }>("/api/stigmergy/density");
}

export function promoteStigmergyMark(
  markId: string,
  body: { salience: number; promoted_by: string },
): Promise<ApiResponse<Record<string, unknown>>> {
  return apiPost<Record<string, unknown>>(
    `/api/stigmergy/marks/${encodeURIComponent(markId)}/promote`,
    body,
  );
}

// ---------------------------------------------------------------------------
// Ontology (additional)
// ---------------------------------------------------------------------------

export function fetchOntologyGraph(): Promise<ApiResponse<OntologyGraphData>> {
  return apiGet<OntologyGraphData>("/api/ontology/graph");
}

export function fetchOntologyDetail(
  typeName: string,
): Promise<ApiResponse<OntologyDetailOut>> {
  return apiGet<OntologyDetailOut>(
    `/api/ontology/types/${encodeURIComponent(typeName)}`,
  );
}

export function fetchOntologyStats(): Promise<
  ApiResponse<Record<string, unknown>>
> {
  return apiGet<Record<string, unknown>>("/api/ontology/stats");
}

// ---------------------------------------------------------------------------
// Lineage (additional)
// ---------------------------------------------------------------------------

export function fetchLineageDag(
  artifactId: string,
  maxDepth = 20,
): Promise<ApiResponse<DagData>> {
  return apiGet<DagData>(
    `/api/lineage/${encodeURIComponent(artifactId)}/dag?max_depth=${maxDepth}`,
  );
}

export function fetchLineageStats(): Promise<
  ApiResponse<Record<string, unknown>>
> {
  return apiGet<Record<string, unknown>>("/api/lineage/stats");
}

// ---------------------------------------------------------------------------
// Viz (unified data plane)
// ---------------------------------------------------------------------------

export function fetchVizSnapshot(
  maxNodes = 200,
): Promise<ApiResponse<VizSnapshot>> {
  return apiGet<VizSnapshot>(`/api/viz/snapshot?max_nodes=${maxNodes}`);
}

export function fetchVizEvents(params?: {
  since?: number;
  limit?: number;
}): Promise<ApiResponse<VizEvent[]>> {
  const sp = new URLSearchParams();
  if (params?.since != null) sp.set("since", String(params.since));
  if (params?.limit != null) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  return apiGet<VizEvent[]>(`/api/viz/events${qs ? `?${qs}` : ""}`);
}

// ---------------------------------------------------------------------------
// Audit & Eval
// ---------------------------------------------------------------------------

export function fetchAuditLatest(): Promise<
  ApiResponse<Record<string, unknown> | null>
> {
  return apiGet<Record<string, unknown> | null>("/api/audit/latest");
}

export function fetchAuditTrend(
  lastN = 20,
): Promise<ApiResponse<Record<string, unknown>[]>> {
  return apiGet<Record<string, unknown>[]>(`/api/audit/trend?last_n=${lastN}`);
}

export function fetchEvalLatest(): Promise<
  ApiResponse<Record<string, unknown> | null>
> {
  return apiGet<Record<string, unknown> | null>("/api/eval/latest");
}

export function fetchEvalTrend(
  lastN = 20,
): Promise<ApiResponse<Record<string, unknown>[]>> {
  return apiGet<Record<string, unknown>[]>(`/api/eval/trend?last_n=${lastN}`);
}

// ---------------------------------------------------------------------------
// Supervisor
// ---------------------------------------------------------------------------

export function fetchSupervisorStatus(): Promise<
  ApiResponse<SupervisorStatus>
> {
  return apiGet<SupervisorStatus>("/api/supervisor/status");
}

// ---------------------------------------------------------------------------
// Conversation log
// ---------------------------------------------------------------------------

export function fetchConversationRecent(params?: {
  hours?: number;
  role?: string;
}): Promise<ApiResponse<ConversationEntry[]>> {
  const sp = new URLSearchParams();
  if (params?.hours != null) sp.set("hours", String(params.hours));
  if (params?.role != null) sp.set("role", params.role);
  const qs = sp.toString();
  return apiGet<ConversationEntry[]>(
    `/api/conversation-log/recent${qs ? `?${qs}` : ""}`,
  );
}

export function fetchConversationPromises(
  hours = 24,
): Promise<ApiResponse<PromiseEntry[]>> {
  return apiGet<PromiseEntry[]>(
    `/api/conversation-log/promises?hours=${hours}`,
  );
}

// ---------------------------------------------------------------------------
// Telemetry
// ---------------------------------------------------------------------------

export function fetchTelemetryOverview(): Promise<
  ApiResponse<Record<string, unknown>>
> {
  return apiGet<Record<string, unknown>>("/api/telemetry/overview");
}

export function fetchTelemetryEconomics(): Promise<
  ApiResponse<Record<string, unknown>>
> {
  return apiGet<Record<string, unknown>>("/api/telemetry/economics");
}

export function fetchTelemetryRouting(): Promise<
  ApiResponse<Record<string, unknown>>
> {
  return apiGet<Record<string, unknown>>("/api/telemetry/routing");
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

export function dispatchTasks(body?: {
  count?: number;
}): Promise<ApiResponse<{ dispatched: number }>> {
  return apiPost<{ dispatched: number }>("/api/commands/dispatch", body);
}

export function fetchDharmaStatus(): Promise<
  ApiResponse<Record<string, unknown>>
> {
  return apiGet<Record<string, unknown>>("/api/commands/dharma");
}

// ---------------------------------------------------------------------------
// VSM (cybernetic health)
// ---------------------------------------------------------------------------

export function fetchVsmStatus(): Promise<
  ApiResponse<Record<string, unknown>>
> {
  return apiGet<Record<string, unknown>>("/api/vsm/status");
}

export function fetchAlgedonicSignals(): Promise<
  ApiResponse<import("./types").AlgedonicSignal[]>
> {
  return apiGet<import("./types").AlgedonicSignal[]>("/api/vsm/algedonic");
}

export function acknowledgeAlgedonic(
  signalId: string,
): Promise<ApiResponse<{ acknowledged: boolean }>> {
  return apiPost<{ acknowledged: boolean }>(
    `/api/vsm/algedonic/${encodeURIComponent(signalId)}/ack`,
  );
}

export function fetchGatePatterns(): Promise<
  ApiResponse<import("./types").GatePattern[]>
> {
  return apiGet<import("./types").GatePattern[]>("/api/vsm/gate-patterns");
}

export function fetchAgentViability(): Promise<
  ApiResponse<Record<string, import("./types").AgentViabilityEntry>>
> {
  return apiGet<Record<string, import("./types").AgentViabilityEntry>>(
    "/api/vsm/viability",
  );
}

export function fetchFleetHealth(): Promise<
  ApiResponse<{ fleet_health: number }>
> {
  return apiGet<{ fleet_health: number }>("/api/vsm/viability/fleet");
}

export function fetchRecentAudits(): Promise<
  ApiResponse<import("./types").AuditResultOut[]>
> {
  return apiGet<import("./types").AuditResultOut[]>("/api/vsm/audit/recent");
}

export function fetchVarietyPending(): Promise<
  ApiResponse<import("./types").GateExpansionProposal[]>
> {
  return apiGet<import("./types").GateExpansionProposal[]>(
    "/api/vsm/variety/pending",
  );
}

// ---------------------------------------------------------------------------
// Catalytic graph
// ---------------------------------------------------------------------------

export function fetchCatalyticSummary(): Promise<
  ApiResponse<import("./types").CatalyticSummary>
> {
  return apiGet<import("./types").CatalyticSummary>("/api/catalytic/summary");
}

export function fetchCatalyticGraph(): Promise<
  ApiResponse<{
    nodes: import("./types").CatalyticNode[];
    edges: import("./types").CatalyticEdge[];
  }>
> {
  return apiGet<{
    nodes: import("./types").CatalyticNode[];
    edges: import("./types").CatalyticEdge[];
  }>("/api/catalytic/graph");
}

export function fetchAutocatalyticSets(): Promise<
  ApiResponse<{ sets: string[][]; count: number; largest: string[] }>
> {
  return apiGet<{ sets: string[][]; count: number; largest: string[] }>(
    "/api/catalytic/autocatalytic",
  );
}

export function fetchLoopClosurePriorities(): Promise<
  ApiResponse<import("./types").LoopClosurePriority[]>
> {
  return apiGet<import("./types").LoopClosurePriority[]>(
    "/api/catalytic/priorities",
  );
}

export function fetchRevenueReady(): Promise<
  ApiResponse<{ sets: string[][]; count: number }>
> {
  return apiGet<{ sets: string[][]; count: number }>(
    "/api/catalytic/revenue-ready",
  );
}

// ---------------------------------------------------------------------------
// Strange loop
// ---------------------------------------------------------------------------

export function fetchStrangeLoopStats(): Promise<
  ApiResponse<import("./types").StrangeLoopStats>
> {
  return apiGet<import("./types").StrangeLoopStats>(
    "/api/strange-loop/stats",
  );
}

export function fetchMutationHistory(
  limit = 50,
): Promise<ApiResponse<import("./types").MutationEntry[]>> {
  return apiGet<import("./types").MutationEntry[]>(
    `/api/strange-loop/mutations?limit=${limit}`,
  );
}

export function fetchOrganismConfig(): Promise<
  ApiResponse<Record<string, unknown>>
> {
  return apiGet<Record<string, unknown>>("/api/strange-loop/config");
}

// ---------------------------------------------------------------------------
// Telos gates
// ---------------------------------------------------------------------------

export function fetchGateDefinitions(): Promise<
  ApiResponse<import("./types").GateDefinition[]>
> {
  return apiGet<import("./types").GateDefinition[]>("/api/gates/definitions");
}

export function runGateCheck(body: {
  action: string;
  content?: string;
}): Promise<ApiResponse<import("./types").GateCheckResult>> {
  return apiPost<import("./types").GateCheckResult>(
    "/api/gates/check",
    body,
  );
}

export function fetchGateProposals(
  status?: string,
): Promise<ApiResponse<import("./types").GateProposalOut[]>> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiGet<import("./types").GateProposalOut[]>(
    `/api/gates/proposals${qs}`,
  );
}

export function fetchWitnessLogs(
  limit = 50,
): Promise<ApiResponse<Record<string, unknown>[]>> {
  return apiGet<Record<string, unknown>[]>(
    `/api/gates/witness/recent?limit=${limit}`,
  );
}

// ---------------------------------------------------------------------------
// Cascade
// ---------------------------------------------------------------------------

export function fetchCascadeDomains(): Promise<
  ApiResponse<Record<string, import("./types").CascadeDomainConfig>>
> {
  return apiGet<Record<string, import("./types").CascadeDomainConfig>>(
    "/api/cascade/domains",
  );
}

export function fetchCascadeHistory(
  limit = 50,
): Promise<ApiResponse<Record<string, unknown>[]>> {
  return apiGet<Record<string, unknown>[]>(
    `/api/cascade/history?limit=${limit}`,
  );
}

export function fetchCascadeCheckpoints(): Promise<
  ApiResponse<import("./types").CascadeCheckpoint[]>
> {
  return apiGet<import("./types").CascadeCheckpoint[]>(
    "/api/cascade/checkpoints",
  );
}

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

export async function authorizedFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  return fetch(apiPath(path), {
    ...init,
    headers: authorizedHeaders({
      "Content-Type": "application/json",
      Accept: "application/json",
      ...init?.headers,
    }),
  });
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authorizedFetch(path, init);

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
