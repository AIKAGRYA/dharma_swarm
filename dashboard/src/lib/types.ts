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

export interface ChatHistoryPayload {
  entries?: ConversationEntry[];
  [key: string]: unknown;
}

export interface ConversationEntry {
  id?: string;
  timestamp?: string;
  role?: string;
  content?: string;
  [key: string]: unknown;
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

export interface AgentDetailPayload {
  agent?: AgentOut;
  [key: string]: unknown;
}

export interface AgentMemoryOut {
  memories?: unknown[];
  [key: string]: unknown;
}

export interface AgentNoteOut {
  id?: string;
  text?: string;
  created_at?: string;
  [key: string]: unknown;
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

export interface EvolutionStats {
  [key: string]: unknown;
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
// Hypernodes (GET /api/hypernodes/empty-quadrant)
// ---------------------------------------------------------------------------

export interface HypernodeQuadrantFrame {
  id: string;
  label: string;
  governance: string;
  orientation: string;
  description: string;
  occupied: boolean;
}

export interface HypernodeProvenanceRecord {
  id: string;
  label: string;
  source_type: string;
  reference: string;
  confidence: number;
}

export interface HypernodeCouncilVerdict {
  id: string;
  decision: string;
  reason: string;
  gate_results: Record<string, string>;
  anekanta_frames: string[];
  steelman_summary: string;
  dogma_drift_summary: string;
  mirofish_activated: boolean;
  mirofish_reason: string;
  quorum_participants: string[];
}

export interface HypernodeFitnessVector {
  id: string;
  auto_grade_score: number;
  council_score: number;
  provenance_score: number;
  market_value_score: number;
  welfare_score: number;
  composite_score: number;
  promotion_threshold: number;
  threshold_met: boolean;
  promotion_state: string;
  scoring_method: string;
}

export interface HypernodeRevenueCell {
  id: string;
  name: string;
  market_category: string;
  target_customer: string;
  revenue_model: string;
  verified_revenue_usd: number;
  expected_value_usd: number;
  evidence_tier: string;
  trustee_principle: string;
  status: string;
  next_actions: string[];
}

export interface HypernodeTypedLink {
  source_id: string;
  source_type: string;
  link_name: string;
  target_id: string;
  target_type: string;
}

export interface HypernodePayload {
  id: string;
  slug: string;
  title: string;
  thesis: string;
  public_path: string;
  quadrant_map: HypernodeQuadrantFrame[];
  provenance: HypernodeProvenanceRecord[];
  council_verdict: HypernodeCouncilVerdict;
  fitness_vector: HypernodeFitnessVector;
  revenue_cell: HypernodeRevenueCell;
  object_chain: Record<string, string[]>;
  typed_links: HypernodeTypedLink[];
  next_actions: string[];
  ontology_counts: Record<string, number>;
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
  nodes: unknown[];
  edges: unknown[];
  [key: string]: unknown;
}

export interface RoutingManifestOut {
  routes?: unknown[];
  [key: string]: unknown;
}

export interface SupervisorStatus {
  status?: string;
  [key: string]: unknown;
}

export interface PromiseEntry {
  id?: string;
  text?: string;
  status?: string;
  [key: string]: unknown;
}

export interface VizSnapshot {
  nodes?: unknown[];
  edges?: unknown[];
  [key: string]: unknown;
}

export interface VizEvent {
  event?: string;
  timestamp?: string;
  [key: string]: unknown;
}

export interface AlgedonicSignal { [key: string]: unknown; }
export interface GatePattern { [key: string]: unknown; }
export interface AgentViabilityEntry { [key: string]: unknown; }
export interface AuditResultOut { [key: string]: unknown; }
export interface GateExpansionProposal { [key: string]: unknown; }
export interface CatalyticSummary { [key: string]: unknown; }
export interface CatalyticNode { [key: string]: unknown; }
export interface CatalyticEdge { [key: string]: unknown; }
export interface LoopClosurePriority { [key: string]: unknown; }
export interface StrangeLoopStats { [key: string]: unknown; }
export interface MutationEntry { [key: string]: unknown; }
export interface GateDefinition { [key: string]: unknown; }
export interface GateCheckResult { [key: string]: unknown; }
export interface GateProposalOut { [key: string]: unknown; }
export interface CascadeDomainConfig { [key: string]: unknown; }
export interface CascadeCheckpoint { [key: string]: unknown; }

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
