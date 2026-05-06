/**
 * DHARMA COMMAND -- TypeScript types matching the FastAPI backend models.
 * These types match the `data` field unwrapped from ApiResponse.
 */

// ---------------------------------------------------------------------------
// Generic API wrapper (raw response before unwrap)
// ---------------------------------------------------------------------------

export interface ApiResponse<T> {
  status: string;
  data: T;
  error: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Chat status (GET /api/chat/status)
// ---------------------------------------------------------------------------

export interface ChatStatusOut {
  chat_contract_version?: string;
  chat_ws_path_template?: string;
  ready: boolean;
  model: string;
  provider: string;
  tools: number;
  max_tool_rounds: number;
  max_tokens: number;
  timeout_seconds: number;
  tool_result_max_chars: number;
  history_message_limit: number;
  temperature: number;
  persistent_sessions?: boolean;
  default_profile_id?: string;
  profiles?: ChatProfileOut[];
}

export interface ChatProfileOut {
  id: string;
  label: string;
  provider: string;
  model: string;
  accent: string;
  summary: string;
  available?: boolean;
  availability_kind?: string;
  status_note?: string;
}

// ---------------------------------------------------------------------------
// Swarm overview (GET /api/overview)
// ---------------------------------------------------------------------------

export interface SwarmOverview {
  agent_count: number;
  task_count: number;
  tasks_pending: number;
  tasks_running: number;
  tasks_completed: number;
  tasks_failed: number;
  mean_fitness: number;
  uptime_seconds: number;
  health_status: string;
  stigmergy_density: number;
  evolution_entries: number;
}

// ---------------------------------------------------------------------------
// Truth modules (GET /api/modules)
// ---------------------------------------------------------------------------

export interface ModuleProcessOut {
  pid: number;
  live: boolean;
  source: string;
  command: string | null;
  observed_paths: string[];
}

export interface ModuleProjectOut {
  label: string;
  path: string;
  exists: boolean;
  kind: string;
  modified_at: string | null;
}

export interface ModuleWireOut {
  direction: string;
  target: string;
  detail: string;
}

export interface ModuleHistoryOut {
  timestamp: string | null;
  title: string;
  detail: string;
  source: string;
  status: string;
}

export interface ModuleSalientOut {
  kind: string;
  title: string;
  detail: string;
  path: string | null;
  timestamp: string | null;
  reason: string;
  score: number;
}

export interface ModuleTruthOut {
  id: string;
  name: string;
  status: string;
  live: boolean;
  summary: string;
  status_reason: string;
  last_activity: string | null;
  metrics: Record<string, string>;
  processes: ModuleProcessOut[];
  projects: ModuleProjectOut[];
  wiring: ModuleWireOut[];
  history: ModuleHistoryOut[];
  salient: ModuleSalientOut[];
}

// ---------------------------------------------------------------------------
// Agents (GET /api/agents)
// ---------------------------------------------------------------------------

export interface AgentOut {
  id: string;
  name: string;
  agent_slug: string;
  display_name: string;
  role: string;
  status: string;
  current_task: string | null;
  started_at: string | null;
  last_heartbeat: string | null;
  turns_used: number;
  tasks_completed: number;
  provider: string;
  model: string;
  model_label: string;
  model_key: string;
  error: string | null;
}

export interface AgentConfigOut {
  display_name?: string | null;
  role?: string | null;
  provider?: string | null;
  model?: string | null;
  thread?: string | null;
  tier?: string | null;
  strengths?: string[];
  [key: string]: unknown;
}

export interface AgentCostOut {
  daily_spent: number;
  weekly_spent: number;
  budget_status: string;
  [key: string]: unknown;
}

export interface FleetAgentConfig {
  name: string;
  display_name?: string | null;
  role: string;
  model: string;
  tool_name?: string | null;
  thread?: string | null;
}

export interface CoreFileOut {
  file_path: string;
  salience: number;
  count: number;
  last_touch?: string | null;
}

export interface AvailableModelOut {
  model_id: string;
  label: string;
  tier?: string | null;
}

export interface FitnessHistoryEntry {
  composite_fitness: number;
  success_rate: number;
  avg_quality: number;
  speed_score: number;
  total_cost_usd: number;
  total_tokens: number;
  avg_latency: number;
  total_calls: number;
  computed_at: string;
}

export interface TaskLogEntry {
  timestamp: string;
  task: string;
  success: boolean;
  latency_ms: number;
  cost_usd: number;
  response_preview?: string | null;
}

export interface AgentTraceOut {
  id: string;
  timestamp: string;
  action: string;
  state: string;
  metadata: Record<string, unknown>;
}

export interface AgentHealthStatsOut {
  total_actions: number;
  failures: number;
  success_rate: number;
  last_seen: string | null;
}

export interface AgentAssignedTaskOut {
  id: string;
  title: string;
  status: string;
  priority: string;
  created_at: string;
  result: string | null;
}

export interface AgentProviderStatusOut {
  provider: string;
  available: boolean;
}

export interface AgentDetailPayload {
  agent: AgentOut;
  config: AgentConfigOut;
  recent_traces: AgentTraceOut[];
  health_stats: AgentHealthStatsOut;
  assigned_tasks: AgentAssignedTaskOut[];
  fitness_history: FitnessHistoryEntry[];
  cost: AgentCostOut;
  core_files: CoreFileOut[];
  available_models: AvailableModelOut[];
  available_roles: string[];
  provider_status: AgentProviderStatusOut[];
  task_history: TaskLogEntry[];
}

export type AgentMemoryTierEntry = Record<string, unknown>;

export interface AgentMemoryOut {
  working: AgentMemoryTierEntry[];
  archival: AgentMemoryTierEntry[];
  persona: AgentMemoryTierEntry[];
  [tier: string]: AgentMemoryTierEntry[];
}

export interface AgentNoteOut {
  filename: string;
  content: string;
  size: number;
  modified: number;
}

export interface ModelVerificationOut {
  status: string;
  verified_at?: string | null;
  response_preview?: string | null;
  error?: string | null;
}

export interface TopModelOut {
  id: string;
  rank: number;
  provider: string;
  display_name: string;
  ui_label: string;
  custom_label?: string | null;
  short_name?: string | null;
  max_context: number;
  strengths: string[];
  available: boolean;
  available_routes?: string[];
  routes?: string[];
  notes?: string | null;
  docs_url?: string;
  provider_url?: string;
  verification?: ModelVerificationOut | null;
}

export interface ModelProfileOut {
  custom_label?: string | null;
  short_name?: string | null;
}

export interface VerifyTop10Out {
  verified_at: string;
  ok_count: number;
}

// ---------------------------------------------------------------------------
// Tasks (GET /api/commands/tasks)
// ---------------------------------------------------------------------------

export interface TaskOut {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
  result: string | null;
}

// ---------------------------------------------------------------------------
// Health (GET /api/health)
// ---------------------------------------------------------------------------

export interface AgentHealthOut {
  agent_name: string;
  total_actions: number;
  failures: number;
  success_rate: number;
  last_seen: string | null;
  status: string;
}

export interface AnomalyOut {
  id: string;
  detected_at: string;
  anomaly_type: string;
  severity: string;
  description: string;
  related_traces: string[];
}

export interface HealthOut {
  overall_status: string;
  agent_health: AgentHealthOut[];
  anomalies: AnomalyOut[];
  total_traces: number;
  traces_last_hour: number;
  failure_rate: number;
  mean_fitness: number | null;
}

// ---------------------------------------------------------------------------
// Evolution (GET /api/evolution/*)
// ---------------------------------------------------------------------------

export interface FitnessOut {
  correctness: number;
  dharmic_alignment: number;
  performance: number;
  utilization: number;
  economic_value: number;
  elegance: number;
  efficiency: number;
  safety: number;
  weighted: number;
}

export interface ArchiveEntryOut {
  id: string;
  timestamp: string;
  parent_id: string | null;
  component: string;
  change_type: string;
  description: string;
  fitness: FitnessOut;
  status: string;
  gates_passed: string[];
  gates_failed: string[];
  agent_id: string;
  model: string;
}

export interface FitnessTrendPoint {
  timestamp: string;
  fitness: number;
  correctness: number;
  elegance: number;
  component: string;
  id: string;
}

export interface DagNode {
  id: string;
  type: string;
  data: {
    label: string;
    fitness: number;
    status: string;
    change_type: string;
    timestamp: string;
  };
  position: { x: number; y: number };
}

export interface DagEdge {
  id: string;
  source: string;
  target: string;
  animated?: boolean;
  label?: string;
}

export interface DagData {
  nodes: DagNode[];
  edges: DagEdge[];
}

// ---------------------------------------------------------------------------
// Traces (GET /api/commands/traces)
// ---------------------------------------------------------------------------

export interface TraceOut {
  id: string;
  timestamp: string;
  agent: string;
  action: string;
  state: string;
  parent_id: string | null;
  metadata: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Ontology (GET /api/ontology/*)
// ---------------------------------------------------------------------------

export interface OntologyTypeOut {
  name: string;
  description: string;
  telos_alignment: number;
  shakti: string;
  property_count: number;
  link_count: number;
  action_count: number;
  icon: string;
}

export interface PropertyOut {
  name: string;
  property_type: string;
  required: boolean;
  description: string;
  searchable: boolean;
}

export interface LinkDefOut {
  name: string;
  source_type: string;
  target_type: string;
  cardinality: string;
  description: string;
}

export interface ActionDefOut {
  name: string;
  description: string;
  requires_approval: boolean;
  telos_gates: string[];
  is_deterministic: boolean;
}

export interface OntologyDetailOut {
  name: string;
  description: string;
  properties: PropertyOut[];
  links: LinkDefOut[];
  actions: ActionDefOut[];
  security_level: string;
  telos_alignment: number;
  shakti: string;
}

export interface OntologyGraphData {
  nodes: {
    id: string;
    type: string;
    data: {
      label: string;
      description: string;
      propertyCount: number;
      shakti: string;
      telos: number;
      icon: string;
      actionCount?: number;
      linkCount?: number;
      runtimeCount?: number;
      zone?: string;
    };
    position: { x: number; y: number };
  }[];
  edges: {
    id: string;
    source: string;
    target: string;
    label: string;
    data: { cardinality: string };
  }[];
}

// ---------------------------------------------------------------------------
// Lineage (GET /api/lineage/*)
// ---------------------------------------------------------------------------

export interface LineageEdgeOut {
  edge_id: string;
  task_id: string;
  input_artifacts: string[];
  output_artifacts: string[];
  agent: string;
  operation: string;
  timestamp: string;
}

export interface ProvenanceOut {
  artifact_id: string;
  chain: LineageEdgeOut[];
  root_sources: string[];
  depth: number;
}

export interface ImpactOut {
  root_artifact: string;
  affected_artifacts: string[];
  affected_tasks: string[];
  depth: number;
  total_descendants: number;
}

// ---------------------------------------------------------------------------
// Stigmergy (GET /api/stigmergy/*)
// ---------------------------------------------------------------------------

export interface StigmergyMarkOut {
  id: string;
  timestamp: string;
  agent: string;
  file_path: string;
  action: string;
  observation: string;
  salience: number;
  connections: string[];
}

export interface HeatmapCell {
  file_path: string;
  hour: number;
  count: number;
  avg_salience: number;
}

export interface HotPath {
  path: string;
  count: number;
}

export interface StigmergyGraphData {
  nodes: {
    id: string;
    label?: string;
    type?: string;
    data?: Record<string, unknown>;
    position?: { x: number; y: number };
    [key: string]: unknown;
  }[];
  edges: {
    id: string;
    source: string;
    target: string;
    label?: string;
    data?: Record<string, unknown>;
    [key: string]: unknown;
  }[];
}

export type EvolutionStats = Record<string, unknown>;

export interface RoutingManifestOut {
  version: string;
  domain: string;
  selected_route: string;
  strategy: string;
  model_policy: Record<string, unknown>;
  routing_decision: Record<string, unknown>;
  agent_routes: Record<string, unknown>;
  selectable_routes: Record<string, unknown>[];
  adapter_catalog: Record<string, unknown>[];
  legacy_targets: Record<string, unknown>[];
  agent_assignments: Record<string, unknown>[];
  counts: Record<string, number>;
  drift: Record<string, unknown>[];
}

export interface ChatHistoryMessage {
  role: string;
  content: string;
  timestamp: string;
  session_id: string;
}

export interface ChatHistoryPayload {
  messages: ChatHistoryMessage[];
  total: number;
}

export interface ConversationEntry {
  timestamp: string;
  role: string;
  interface: string;
  session_id: string;
  content: string;
  metadata?: Record<string, unknown>;
}

export interface PromiseEntry {
  timestamp: string;
  session_id: string;
  interface: string;
  type: string;
  count: number;
  promises: string[];
}

export interface VizNode {
  id: string;
  label: string;
  node_type: string;
  status: string;
  metrics: Record<string, number>;
  position: { x: number; y: number } | null;
  metadata: Record<string, unknown>;
}

export interface VizEdge {
  id: string;
  source: string;
  target: string;
  edge_type: string;
  weight: number;
  metadata: Record<string, unknown>;
}

export interface VizEvent {
  timestamp: number;
  event_type: string;
  node_id: string | null;
  edge_id: string | null;
  data: Record<string, unknown>;
}

export interface VizSnapshot {
  timestamp: number;
  nodes: VizNode[];
  edges: VizEdge[];
  summary: Record<string, unknown>;
}

export interface SupervisorLoopHealth {
  name: string;
  last_tick: number;
  expected_interval: number;
  tick_count: number;
  error_count: number;
  last_errors: string[];
  last_progress_score: number | null;
  best_progress_score: number | null;
  stagnant_cycles: number;
  stale_seconds: number;
  is_stalled: boolean;
}

export interface SupervisorAlert {
  alert_type: string;
  loop_name: string;
  severity: string;
  message: string;
  intervention: string;
  timestamp: string;
}

export interface SupervisorStatus {
  loops: Record<string, SupervisorLoopHealth>;
  recent_alerts: SupervisorAlert[];
  total_alerts: number;
}

export interface AlgedonicSignal {
  id: string;
  severity: string;
  source_system: string;
  title: string;
  description: string;
  recommended_action: string;
  context: Record<string, unknown>;
  acknowledged: boolean;
  timestamp: string;
}

export interface GatePattern {
  id: string;
  gate_name: string;
  failure_count: number;
  total_checks: number;
  failure_rate: number;
  recent_reasons: string[];
  trending: string;
  timestamp: string;
}

export interface AgentViabilityEntry {
  agent_id: string;
  s1_operations: number;
  s2_coordination: number;
  s3_control: number;
  s4_intelligence: number;
  s5_identity: number;
  overall: number;
  timestamp: string;
}

export interface AuditResultOut {
  id: string;
  agent_id: string;
  audit_type: string;
  passed: boolean;
  findings: string[];
  timestamp: string;
}

export interface GateExpansionProposal {
  id: string;
  proposed_gate: string;
  tier: string;
  rationale: string;
  triggered_by: string;
  proposed_check: string;
  status: string;
  reviewed_by: string;
  timestamp: string;
}

export interface CatalyticSummary {
  nodes?: number;
  edges?: number;
  sccs?: number;
  autocatalytic_sets?: number;
  [key: string]: unknown;
}

export interface CatalyticNode {
  id: string;
  label?: string;
  node_type?: string;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface CatalyticEdge {
  id?: string;
  source: string;
  target: string;
  edge_type?: string;
  weight?: number;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface LoopClosurePriority {
  node_id?: string;
  score?: number;
  reason?: string;
  [key: string]: unknown;
}

export type StrangeLoopStats = Record<string, unknown>;

export interface MutationEntry {
  id?: string;
  timestamp?: string;
  component?: string;
  mutation_type?: string;
  description?: string;
  status?: string;
  fitness_delta?: number;
  [key: string]: unknown;
}

export interface GateDefinition {
  name: string;
  tier: string;
  description?: string;
  trigger_patterns?: string[];
  [key: string]: unknown;
}

export interface GateCheckResult {
  decision: string;
  reason: string;
  gate: string;
  gate_results: Record<string, [string, string]>;
  timestamp: string;
}

export interface GateProposalOut {
  name: string;
  tier: string;
  justification: string;
  trigger_patterns: string[];
  proposed_by: string;
  proposed_at: string;
  status: string;
  reviewed_at: string;
  review_note: string;
}

export interface CascadeDomainConfig {
  name: string;
  generate_fn: string;
  test_fn: string;
  score_fn: string;
  gate_fn: string;
  mutate_fn: string;
  select_fn: string;
  eigenform_fn: string;
  max_iterations: number;
  fitness_threshold: number;
  eigenform_epsilon: number;
  convergence_window: number;
  max_duration_seconds: number;
  mutation_rate: number;
}

export interface CascadeCheckpoint {
  domain: string;
  cycle_id: string;
  iteration: number;
  current: Record<string, unknown> | null;
  previous: Record<string, unknown> | null;
  candidates: Record<string, unknown>[];
  best_score: number;
  fitness_trajectory: number[];
  eigenform_trajectory: number[];
  elapsed_seconds: number;
  converged: boolean;
  convergence_reason: string;
  interrupted: boolean;
  interrupt_reason: string;
  version: string;
  saved_at: string;
}

// ---------------------------------------------------------------------------
// WebSocket events
// ---------------------------------------------------------------------------

export interface WsEvent<T = unknown> {
  event: string;
  data?: T;
  agents?: AgentOut[];
  agent?: AgentOut;
  agent_id?: string;
  timestamp?: string;
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

export interface NavSection {
  label: string;
  level: number;
  items: NavItem[];
}

export interface NavItem {
  label: string;
  href: string;
  icon: string;
  level: number;
  badge?: string | number;
}
