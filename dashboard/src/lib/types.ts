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

export interface ModelVerificationOut {
  status: string;
  verified_at?: string | null;
  response_preview?: string | null;
  error?: string | null;
}

export interface RouteStatusOut {
  provider: string;
  model_id: string;
  route: string;
  status: string;
  reason?: string | null;
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
  status?: string;
  unavailable_reason?: string | null;
  lane?: string;
  below_floor?: boolean;
  available_routes?: string[];
  routes?: string[];
  route_statuses?: RouteStatusOut[];
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
  skipped_count?: number;
  live_calls_attempted?: boolean;
  reason?: string;
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
// Runtime graph (GET /api/runtime/graph)
// ---------------------------------------------------------------------------

export interface RuntimeGraphSummary {
  topology_state_count: number;
  run_count: number;
  active_run_count: number;
  receipt_count: number;
  node_count: number;
  edge_count: number;
  checkpoint_count: number;
  active_agent_count: number;
}

export interface RuntimeGraphNode {
  id: string;
  kind: string;
  label: string;
  run_id?: string;
  task_id?: string;
  session_id?: string;
  status?: string;
  agent_id?: string;
  topology?: string;
  checkpoint_id?: string;
  active?: boolean;
  [key: string]: unknown;
}

export interface RuntimeGraphEdge {
  id: string;
  kind: string;
  source: string;
  target: string;
  label: string;
  run_id?: string;
  receipt_id?: string;
  parent_run_id?: string;
  child_run_id?: string;
  metadata?: Record<string, unknown>;
}

export interface RuntimeGraphCheckpoint {
  checkpoint_id: string;
  run_id: string;
  task_id: string;
  topology: string;
  active_agent: string;
  current_node: string;
  updated_at: string | null;
}

export interface RuntimeGraphTopologyState {
  schema_version: string;
  run_id: string;
  session_id: string;
  task_id: string;
  topology: string;
  active_agent: string;
  current_node: string;
  checkpoint_id: string;
  parent_run_id: string;
  child_run_ids: string[];
  allowed_handoffs: Record<string, string[]>;
  handoff_receipts: Record<string, unknown>[];
  state: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface RuntimeGraphRun {
  run_id: string;
  session_id: string;
  task_id: string;
  claim_id: string;
  parent_run_id: string;
  assigned_by: string;
  assigned_to: string;
  requested_output: string[];
  current_artifact_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  failure_code: string;
  metadata: Record<string, unknown>;
}

export interface RuntimeGraphReceipt {
  receipt_id: string;
  receipt_type: string;
  run_id: string;
  task_id: string;
  trace_id: string;
  correlation_id: string;
  causation_id: string;
  parent_run_id: string;
  agent_id: string;
  idempotency_key: string;
  side_effect_key: string;
  status: string;
  payload: Record<string, unknown>;
  created_at: string | null;
}

export interface RuntimeGraphSnapshot {
  schema_version: string;
  generated_at: string;
  runtime_db: string;
  filters: Record<string, unknown>;
  summary: RuntimeGraphSummary;
  active_agents: string[];
  checkpoints: RuntimeGraphCheckpoint[];
  topology_states: RuntimeGraphTopologyState[];
  runs: RuntimeGraphRun[];
  receipts: RuntimeGraphReceipt[];
  nodes: RuntimeGraphNode[];
  edges: RuntimeGraphEdge[];
}

// ---------------------------------------------------------------------------
// Runtime interrupts (GET /api/runtime/interrupts)
// ---------------------------------------------------------------------------

export interface RuntimeEvent {
  event_id: string;
  session_id: string;
  ledger_kind: string;
  event_name: string;
  task_id?: string;
  run_id?: string;
  agent_id?: string;
  summary?: string;
  event_text?: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface RuntimeInterruptSummary {
  control_event_count: number;
  pending_interrupt_count: number;
  human_approval_required_count: number;
  approved_count: number;
  resumed_count: number;
}

export interface RuntimeInterruptControlEvent {
  event_id: string;
  session_id: string;
  task_id: string;
  run_id: string;
  agent_id: string;
  event_name: string;
  control_type: string;
  status: string;
  requires_human: boolean;
  interrupt_id: string;
  approval_id: string;
  resume_token: string;
  checkpoint_id: string;
  summary: string;
  created_at: string;
  event: RuntimeEvent;
}

export interface RuntimeInterruptsSnapshot {
  schema_version: string;
  generated_at: string;
  runtime_db: string;
  filters: Record<string, unknown>;
  summary: RuntimeInterruptSummary;
  control_events: RuntimeInterruptControlEvent[];
}

export interface RuntimeControlActionRequest {
  session_id?: string;
  task_id?: string;
  run_id?: string;
  approval_id?: string;
  interrupt_id?: string;
  resume_token?: string;
  actor?: string;
  reason?: string;
  payload?: Record<string, unknown>;
}

export interface RuntimeControlActionResult {
  schema_version: string;
  generated_at: string;
  runtime_db: string;
  action: "approve" | "reject" | "resume";
  status: string;
  target_found: boolean;
  target_control_event: RuntimeInterruptControlEvent | null;
  operator_action: Record<string, unknown>;
  event: RuntimeEvent;
  interrupt_transport: Record<string, unknown>;
  interrupts: RuntimeInterruptsSnapshot;
}

// ---------------------------------------------------------------------------
// Runtime Agent Server surfaces
// ---------------------------------------------------------------------------

export interface RuntimeAssistantSummary {
  assistant_count: number;
  configuration_count: number;
  active_assistant_count: number;
}

export interface RuntimeAssistant {
  assistant_id: string;
  name: string;
  configuration_ids: string[];
  session_ids: string[];
  latest_run_id: string;
  latest_session_id: string;
  run_count: number;
  active_run_count: number;
  status: string;
  metadata: Record<string, unknown>;
}

export interface RuntimeAssistantConfiguration {
  configuration_id: string;
  assistant_ids: string[];
  provider: string;
  model: string;
  tool_count: number;
  system_prompt_hash: string;
  run_count: number;
  session_count: number;
  metadata: Record<string, unknown>;
}

export interface RuntimeAssistantsSnapshot {
  schema_version: string;
  generated_at: string;
  runtime_db: string;
  filters: Record<string, unknown>;
  summary: RuntimeAssistantSummary;
  assistants: RuntimeAssistant[];
  configurations: RuntimeAssistantConfiguration[];
}

export interface RuntimeBackgroundSummary {
  cron_job_count: number;
  enabled_cron_job_count: number;
  background_run_count: number;
  active_background_run_count: number;
  background_event_count: number;
}

export interface RuntimeCronJob {
  job_id: string;
  name: string;
  enabled: boolean;
  urgent: boolean;
  schedule: Record<string, unknown>;
  schedule_display: string;
  deliver: string;
  next_run_at: string;
  last_run_at: string;
  last_status: string;
  last_error: string;
  repeat: Record<string, unknown>;
  output_count: number;
  output_dir: string;
  metadata: Record<string, unknown>;
}

export interface RuntimeBackgroundRun {
  run_id: string;
  session_id: string;
  task_id: string;
  assigned_to: string;
  assigned_by: string;
  status: string;
  cron_job_id: string;
  run_kind: string;
  metadata: Record<string, unknown>;
  [key: string]: unknown;
}

export interface RuntimeBackgroundJobsSnapshot {
  schema_version: string;
  generated_at: string;
  runtime_db: string;
  cron_jobs_file: string;
  filters: Record<string, unknown>;
  summary: RuntimeBackgroundSummary;
  cron_jobs: RuntimeCronJob[];
  background_runs: RuntimeBackgroundRun[];
  background_events: RuntimeEvent[];
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

// ---------------------------------------------------------------------------
// Control Surface (GET /api/control-surface/*)
// ---------------------------------------------------------------------------

export interface ControlSurfaceEvidenceItem {
  kind: string;
  source: string;
  line_range?: [number, number] | null;
  observed_at?: string;
  raw_content?: string | null;
  status?: string | null;
  provenance_chain?: string[];
}

export interface ControlSurfaceSourceRef {
  kind: string;
  path: string;
  exists?: boolean;
  line_range?: [number, number] | null;
}

export interface ControlSurfaceRow {
  id: string;
  kind: string;
  label: string;
  authority_role: string;
  declared_state: string;
  desired_state: string;
  observed_state: string;
  coherence_state: string;
  priority: string;
  owner_module: string;
  truth_owner: string;
  evidence: ControlSurfaceEvidenceItem[];
  evidence_labels?: string[];
  freshness: string;
  gap_codes: string[];
  next_action: string;
  human_decision_required: boolean;
  source_refs: ControlSurfaceSourceRef[];
  source_ref_labels?: string[];
  raw: Record<string, unknown>;
}

export interface ControlSurfaceSummary {
  total: number;
  bound: number;
  partial: number;
  drifted: number;
  declared_only: number;
  unknown: number;
  human_decision_required_count: number;
  p0_count: number;
  p1_count: number;
  generated_at: string;
  sources_consulted: string[];
  memory_depth?: string;
}

export interface ControlSurfaceSourceError {
  source: string;
  error: string;
}

export interface ControlSurfaceEnvelope<T> {
  schema_version: string;
  request_id: string;
  generated_at: string;
  source_errors: ControlSurfaceSourceError[];
  data: T;
}

export interface MissionControlMissionView {
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

export interface MissionControlTaskView {
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

export interface MissionControlAttemptView {
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

export interface MissionControlLeaseView {
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

export interface MissionControlReceiptView {
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

export interface MissionControlSnapshot {
  mission: MissionControlMissionView;
  tasks: MissionControlTaskView[];
  attempts: MissionControlAttemptView[];
  leases: MissionControlLeaseView[];
  receipts: MissionControlReceiptView[];
  reconciliation: string;
  observed_at: string;
  authority: "TaskBoard+RuntimeStateStore";
  proves_executor_liveness: false;
}

export interface MissionSnapshotProjection {
  schema_version: "dharma.control_surface.mission_snapshot_projection.v1";
  mission_id: string;
  state: "observed" | "uninitialized" | "unknown";
  authority: "TaskBoard+RuntimeStateStore";
  source_mode: "injected_read_only";
  runtime_projection_mode: "immutable_copy" | "owner_supplied_read_only" | "unavailable";
  simulation: false;
  snapshot: MissionControlSnapshot | null;
  proves_executor_liveness: false;
}

export interface BoardReceiptRef {
  receipt_id: string;
  kind: string;
  store: string;
  uri: string;
  checksum: string;
  created_at: string;
  summary: string;
}

export interface BoardAcceptanceCriterion {
  id: string;
  text: string;
  kind: string;
  required: boolean;
  verifier: string;
  evidence_ref: string;
}

export interface BoardRenderHints {
  view_priority: number;
  color_key: string;
  icon_key: string;
  column_hint: string;
  lane_hint: string;
  thread_hint: string;
  map_node_kind: string;
}

export interface BoardCard {
  id: string;
  parent_objective: string | null;
  title: string;
  body: string;
  status: string;
  assignee_kind: string;
  capability_required: string[];
  acceptance_criteria: BoardAcceptanceCriterion[];
  receipt_refs: BoardReceiptRef[];
  arjuna_weight: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  source_surface: string;
  render_hints: BoardRenderHints;
}

export type DsGoalBoardCard = BoardCard;
export type AgentOpsBoardCard = BoardCard;
export type A2ASendBoardCard = BoardCard;
export type SemanticReceiptBoardCard = BoardCard;

export interface DsGoalCardsPayload {
  state_root: string;
  mission_id: string | null;
  card_count: number;
  cards: DsGoalBoardCard[];
}

export interface AgentOpsCardsPayload {
  work_packet_root: string;
  packet_id: string | null;
  card_count: number;
  cards: AgentOpsBoardCard[];
}

export interface A2ASendCardsPayload {
  receipt_root: string;
  bridge_receipt_root?: string;
  domain_reply_receipt_root?: string;
  reply_receipt_root?: string;
  target: string | null;
  card_count: number;
  cards: A2ASendBoardCard[];
}

export interface SemanticReceiptCardsPayload {
  receipt_root: string;
  model: string | null;
  verdict: string | null;
  card_count: number;
  cards: SemanticReceiptBoardCard[];
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
