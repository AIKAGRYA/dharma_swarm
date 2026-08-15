export const HELM_CONTEXT_SCHEMA = "dharma.helm.context.v1" as const;
export const HELM_CONTEXT_PROJECTION_NAMES = [
  "workspace", "bridge_session", "ui", "mission_control", "task_board", "runtime_state",
  "session", "receipts", "swarm", "a2a", "evolution", "actions",
] as const;
export type HelmContextProjectionName = (typeof HELM_CONTEXT_PROJECTION_NAMES)[number];
export type HelmCollection<T> = Readonly<{
  items: readonly T[];
  total: number;
  truncated: boolean;
}>;
export type HelmWorkspaceData = Readonly<{
  workspace_path: string;
  workspace: string;
  repository: string;
  repository_identity: string | null;
  remote: string | null;
  branch: string | null;
  head: string | null;
  upstream: string | null;
  ahead: number | null;
  behind: number | null;
  staged: number | null;
  unstaged: number | null;
  untracked: number | null;
}>;
export type HelmActivePhase =
  | "starting"
  | "streaming"
  | "finalizing"
  | "cancelling"
  | "complete";
export type HelmBridgeSessionData = Readonly<{
  bridge_status: "connected";
  active_session_id: string | null;
  active_phase: HelmActivePhase | null;
  requested_provider_id: string | null;
  requested_model_id: string | null;
  served_provider_id: string | null;
  served_model_id: string | null;
  served_identity_source: "unavailable" | "provider_response_via_route_evaluator";
  served_identity_observed_at: string | null;
  route_evidence_expires_at: string | null;
  route_evidence_freshness: "unavailable" | "selected_route_mismatch" | "invalid" | "expired" | "fresh";
  route_receipt_ref: string | null;
  route_receipt_sha256: string | null;
  route_verifier_id: string | null;
  route_verifier_version: string | null;
  route_evidence_synthetic: boolean | null;
  route_verdict: "ON_CALL" | "UNKNOWN" | "REJECTED" | "CLOCK_SKEW";
  route_verdict_reason: string;
  route_exact_model_proven: boolean;
  route_seat_id: string | null;
  route_verification_evaluated_at: string | null;
}>;
export type HelmFace = "zen" | "cockpit" | "scroll" | `deck-focus:${HelmFacet}`;
export type HelmPlace = "home" | "conversation" | "activity" | "evidence" | "system";
export type HelmFacet =
  | "chat" | "commands" | "agents" | "models" | "evolution" | "thinking"
  | "tools" | "timeline" | "sessions" | "approvals" | "mission" | "runtime"
  | "repo" | "ontology" | "control";
const PLACE_FACETS = {
  home: ["mission", "control"], conversation: ["chat", "sessions"],
  activity: ["agents", "evolution", "thinking", "tools", "timeline", "approvals"],
  evidence: ["repo", "ontology"], system: ["commands", "models", "runtime"],
} as const satisfies Readonly<Record<HelmPlace, readonly HelmFacet[]>>;
export type HelmOverlay = "none" | "modelPicker" | "paneSwitcher" | "tour";
export type HelmKeyboardFocus = "composer" | "navigation";
export type HelmNavigationDescriptor = Readonly<{
  id: string;
  label: string;
  key: string | null;
  command: string | null;
  target_kind: "facet" | "face" | "overlay" | "projection" | "feature";
  target_id: string | null;
  resulting_place: HelmPlace | null;
  available: boolean;
}>;
type HelmPlaceFacet = {
  [Place in HelmPlace]: Readonly<{place: Place; facet: (typeof PLACE_FACETS)[Place][number]}>;
}[HelmPlace];
export type HelmUIData = Readonly<{
  face: HelmFace;
  overlay: HelmOverlay;
  keyboard_focus: HelmKeyboardFocus;
  navigation: HelmCollection<HelmNavigationDescriptor>;
}> & HelmPlaceFacet;
export type HelmOperatorAction = Readonly<{
  action_id: string;
  label: string;
  owner: string;
  effects: readonly string[];
  risk: "safe_read" | "workspace_mutation" | "cross_boundary_mutation" | "shell_or_network" | "destructive";
  requires_approval: boolean;
  reversible: boolean;
  cancel_action_id: string | null;
}>;
export type HelmActionsData = Readonly<{
  actions: HelmCollection<HelmOperatorAction>;
}>;
export type HelmMissionControlData = Readonly<{mission: Readonly<{
  mission_id: string; title: string; status: string; updated_at: string | null;
}>}>;
export type HelmTaskSummary = Readonly<{
  task_id: string; title: string; status: string; priority: string; assigned_to: string | null;
  depends_on_count: number; blocked_by_count: number; updated_at: string;
}>;
export type HelmTaskBoardData = Readonly<{tasks: HelmCollection<HelmTaskSummary>}>;
export type HelmRuntimeSessionSummary = Readonly<{
  session_id: string; status: string; current_task_id: string | null;
  active_bundle_id: string | null; updated_at: string; source_runtime_epoch: string | null;
}>;
export type HelmRuntimeStateData = Readonly<{sessions: HelmCollection<HelmRuntimeSessionSummary>}>;
export type HelmSessionSummary = Readonly<{
  session_id: string; status: string; title: string; provider_id: string; model_id: string;
  total_turns: number; updated_at: string | null; runtime_owner_id: string | null;
}>;
export type HelmSessionData = Readonly<{sessions: HelmCollection<HelmSessionSummary>}>;
export type HelmReceiptSummary = Readonly<{
  receipt_id: string; receipt_type: string; status: string; run_id: string; task_id: string;
  agent_id: string; created_at: string;
}>;
export type HelmReceiptsData = Readonly<{receipts: HelmCollection<HelmReceiptSummary>}>;
export type HelmAgentSummary = Readonly<{
  agent_id: string; name: string; role: string; status: string; current_task: string | null;
  provider: string; model: string; last_heartbeat: string | null;
}>;
export type HelmSwarmData = Readonly<{
  agents: HelmCollection<HelmAgentSummary>;
  tasks_pending: number; tasks_running: number; tasks_completed: number; tasks_failed: number;
  source_runtime_epoch: string | null;
}>;
export type HelmA2AContactSummary = Readonly<{
  agent_uid: string; kind: string; display_name: string; capability_count: number;
}>;
export type HelmA2AData = Readonly<{contacts: HelmCollection<HelmA2AContactSummary>}>;
export type HelmEvolutionEntrySummary = Readonly<{
  entry_id: string; timestamp: string; parent_id: string | null; component: string;
  change_type: string; spec_ref: string | null; commit_hash: string | null; evidence_tier: string;
  promotion_state: string; status: string; agent_id: string; model: string; tokens_used: number;
  gates_passed_count: number; gates_failed_count: number;
}>;
export type HelmEvolutionData = Readonly<{entries: HelmCollection<HelmEvolutionEntrySummary>}>;
export type HelmProjectionDataByRegion = Readonly<{
  workspace: HelmWorkspaceData;
  bridge_session: HelmBridgeSessionData;
  ui: HelmUIData;
  mission_control: HelmMissionControlData;
  task_board: HelmTaskBoardData;
  runtime_state: HelmRuntimeStateData;
  session: HelmSessionData;
  receipts: HelmReceiptsData;
  swarm: HelmSwarmData;
  a2a: HelmA2AData;
  evolution: HelmEvolutionData;
  actions: HelmActionsData;
}>;
type UnknownObject = {[key: string]: unknown};
type ItemValidator = (value: unknown) => boolean;
function objectWithExactKeys(value: unknown, keys: readonly string[]): UnknownObject | undefined {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return undefined;
  }
  const object = value as UnknownObject;
  const actual = Object.keys(object);
  return actual.length === keys.length && keys.every((key) => Object.hasOwn(object, key))
    ? object
    : undefined;
}
function oneOf(value: unknown, choices: readonly string[]): boolean {
  return typeof value === "string" && choices.includes(value);
}
function stringOrNull(value: unknown): boolean {
  return value === null || typeof value === "string";
}
function nonnegativeIntegerOrNull(value: unknown): boolean {
  return value === null || Number.isSafeInteger(value) && (value as number) >= 0;
}
function collectionIsValid(value: unknown, itemIsValid: ItemValidator): boolean {
  const collection = objectWithExactKeys(value, ["items", "total", "truncated"]);
  if (
    !collection
    || !Array.isArray(collection.items)
    || Object.keys(collection.items).length !== collection.items.length
    || !Object.keys(collection.items).every((key, index) => key === String(index))
    || !Number.isSafeInteger(collection.total)
    || (collection.total as number) < collection.items.length
    || typeof collection.truncated !== "boolean"
    || collection.truncated !== ((collection.total as number) > collection.items.length)
  ) {
    return false;
  }
  return collection.items.every(itemIsValid);
}
const WORKSPACE_KEYS = [
  "workspace_path", "workspace", "repository", "repository_identity", "remote",
  "branch", "head", "upstream", "ahead", "behind", "staged", "unstaged", "untracked",
] as const;
const BRIDGE_SESSION_KEYS = [
  "bridge_status", "active_session_id", "active_phase", "requested_provider_id",
  "requested_model_id", "served_provider_id", "served_model_id", "served_identity_source",
  "served_identity_observed_at", "route_evidence_expires_at", "route_evidence_freshness",
  "route_receipt_ref", "route_receipt_sha256", "route_verifier_id", "route_verifier_version",
  "route_evidence_synthetic", "route_verdict", "route_verdict_reason",
  "route_exact_model_proven", "route_seat_id", "route_verification_evaluated_at",
] as const;
const UI_KEYS = ["face", "place", "facet", "overlay", "keyboard_focus", "navigation"] as const;
const NAVIGATION_KEYS = [
  "id", "label", "key", "command", "target_kind", "target_id", "resulting_place", "available",
] as const;
const NAVIGATION_ROWS = [
  ["home", "Home (Control facet)", null, "open control", "facet", "control", "home", true], ["conversation", "Conversation", "Esc then Ctrl+G", "open chat", "facet", "chat", "conversation", true],
  ["activity", "Activity (Agents facet)", "Esc then Ctrl+A", "open agents", "facet", "agents", "activity", true], ["evidence", "Evidence (Repository facet)", "Esc then Ctrl+R", "open repo", "facet", "repo", "evidence", true],
  ["system", "System (Commands facet)", "Esc then Ctrl+M", "open commands", "facet", "commands", "system", true], ["face_toggle", "Quiet Field / Full Helm", "F2", "/cockpit", "face", null, null, true],
  ["pane_switcher", "Pane switcher", "Esc then Ctrl+K", null, "overlay", "paneSwitcher", null, true], ["model_picker", "Model picker", "Esc then Ctrl+P", "/model", "overlay", "modelPicker", null, true],
  ["receipts", "Receipts", null, null, "projection", "receipts", "evidence", false], ["inspector", "Inspector", null, null, "feature", "inspector", null, false],
] as const;
const ACTION_KEYS = [
  "action_id", "label", "owner", "effects", "risk", "requires_approval", "reversible",
  "cancel_action_id",
] as const;
function workspaceDataIsValid(value: unknown): boolean {
  const data = objectWithExactKeys(value, WORKSPACE_KEYS);
  return !!data
    && [data.workspace_path, data.workspace, data.repository].every((item) => (
      typeof item === "string" && item.length > 0
    ))
    && (data.workspace_path as string).startsWith("/")
    && !(data.workspace_path as string).endsWith("/") && !(data.workspace_path as string).includes("//")
    && !(data.workspace_path as string).split("/").some((part) => part === "." || part === "..")
    && (data.workspace_path as string).split("/").at(-1) === data.workspace
    && [data.repository_identity, data.remote, data.branch, data.head, data.upstream]
      .every(stringOrNull)
    && [data.ahead, data.behind, data.staged, data.unstaged, data.untracked]
      .every(nonnegativeIntegerOrNull);
}
function bridgeSessionDataIsValid(value: unknown): boolean {
  const data = objectWithExactKeys(value, BRIDGE_SESSION_KEYS);
  if (!data) {
    return false;
  }
  const nullableStrings = [
    data.active_session_id, data.requested_provider_id, data.requested_model_id,
    data.served_provider_id, data.served_model_id, data.served_identity_observed_at,
    data.route_evidence_expires_at, data.route_receipt_ref, data.route_receipt_sha256,
    data.route_verifier_id, data.route_verifier_version, data.route_seat_id,
    data.route_verification_evaluated_at,
  ];
  return data.bridge_status === "connected"
    && (data.active_phase === null || oneOf(data.active_phase, [
      "starting", "streaming", "finalizing", "cancelling", "complete",
    ]))
    && nullableStrings.every(stringOrNull)
    && oneOf(data.served_identity_source, ["unavailable", "provider_response_via_route_evaluator"])
    && oneOf(data.route_evidence_freshness, [
      "unavailable", "selected_route_mismatch", "invalid", "expired", "fresh",
    ])
    && (data.route_evidence_synthetic === null || typeof data.route_evidence_synthetic === "boolean")
    && oneOf(data.route_verdict, ["ON_CALL", "UNKNOWN", "REJECTED", "CLOCK_SKEW"])
    && typeof data.route_verdict_reason === "string"
    && typeof data.route_exact_model_proven === "boolean"
    && (!data.route_exact_model_proven || (
      data.route_verdict === "ON_CALL" && data.route_evidence_freshness === "fresh"
      && data.route_evidence_synthetic === false && !!data.served_provider_id && !!data.served_model_id
    ));
}
function navigationItemIsValid(value: unknown): boolean {
  const item = objectWithExactKeys(value, NAVIGATION_KEYS);
  return !!item
    && typeof item.id === "string" && typeof item.label === "string"
    && stringOrNull(item.key) && stringOrNull(item.command)
    && oneOf(item.target_kind, ["facet", "face", "overlay", "projection", "feature"])
    && stringOrNull(item.target_id)
    && (item.resulting_place === null || oneOf(item.resulting_place, [
      "home", "conversation", "activity", "evidence", "system",
    ]))
    && typeof item.available === "boolean";
}
function uiDataIsValid(value: unknown): boolean {
  const data = objectWithExactKeys(value, UI_KEYS);
  if (!data) {
    return false;
  }
  const face = typeof data.face === "string" && (
    oneOf(data.face, ["zen", "cockpit", "scroll"])
    || data.face.startsWith("deck-focus:") && oneOf(data.face.slice(11), [
      "chat", "commands", "agents", "models", "evolution", "thinking", "tools", "timeline",
      "sessions", "approvals", "mission", "runtime", "repo", "ontology", "control",
    ])
  );
  const navigation = objectWithExactKeys(data.navigation, ["items", "total", "truncated"]);
  return face
    && typeof data.place === "string" && Object.hasOwn(PLACE_FACETS, data.place)
    && oneOf(data.facet, PLACE_FACETS[data.place as HelmPlace])
    && oneOf(data.overlay, ["none", "modelPicker", "paneSwitcher", "tour"])
    && oneOf(data.keyboard_focus, ["composer", "navigation"])
    && collectionIsValid(data.navigation, navigationItemIsValid)
    && !!navigation && navigation.total === NAVIGATION_ROWS.length && navigation.truncated === false
    && (navigation.items as unknown[]).every((value, rowIndex) => {
      const item = objectWithExactKeys(value, NAVIGATION_KEYS);
      return !!item && NAVIGATION_KEYS.every((key, column) => item[key] === NAVIGATION_ROWS[rowIndex]![column]);
    });
}
function actionItemIsValid(value: unknown): boolean {
  const item = objectWithExactKeys(value, ACTION_KEYS);
  return !!item
    && [item.action_id, item.label, item.owner, item.risk].every((field) => typeof field === "string")
    && Array.isArray(item.effects) && Object.keys(item.effects).length === item.effects.length
    && item.effects.every((effect) => typeof effect === "string")
    && oneOf(item.risk, [
      "safe_read", "workspace_mutation", "cross_boundary_mutation", "shell_or_network", "destructive",
    ])
    && typeof item.requires_approval === "boolean" && typeof item.reversible === "boolean"
    && stringOrNull(item.cancel_action_id);
}
function actionsDataIsValid(value: unknown): boolean {
  const data = objectWithExactKeys(value, ["actions"]);
  return !!data && collectionIsValid(data.actions, actionItemIsValid);
}
type TimestampValidator = (value: unknown) => boolean;
const MISSION_KEYS = ["mission_id", "title", "status", "updated_at"] as const;
const TASK_KEYS = [
  "task_id", "title", "status", "priority", "assigned_to", "depends_on_count",
  "blocked_by_count", "updated_at",
] as const;
const RUNTIME_SESSION_KEYS = [
  "session_id", "status", "current_task_id", "active_bundle_id", "updated_at",
  "source_runtime_epoch",
] as const;
const SESSION_KEYS = [
  "session_id", "status", "title", "provider_id", "model_id", "total_turns", "updated_at",
  "runtime_owner_id",
] as const;
const RECEIPT_KEYS = [
  "receipt_id", "receipt_type", "status", "run_id", "task_id", "agent_id", "created_at",
] as const;
const AGENT_KEYS = [
  "agent_id", "name", "role", "status", "current_task", "provider", "model", "last_heartbeat",
] as const;
const CONTACT_KEYS = ["agent_uid", "kind", "display_name", "capability_count"] as const;
const EVOLUTION_KEYS = [
  "entry_id", "timestamp", "parent_id", "component", "change_type", "spec_ref", "commit_hash",
  "evidence_tier", "promotion_state", "status", "agent_id", "model", "tokens_used",
  "gates_passed_count", "gates_failed_count",
] as const;
function stringFields(object: UnknownObject, keys: readonly string[]): boolean {
  return keys.every((key) => typeof object[key] === "string");
}
function integerFields(object: UnknownObject, keys: readonly string[]): boolean {
  return keys.every((key) => Number.isSafeInteger(object[key]) && (object[key] as number) >= 0);
}
function timestampOrNull(value: unknown, timestamp: TimestampValidator): boolean {
  return value === null || timestamp(value);
}
function missionDataIsValid(value: unknown, timestamp: TimestampValidator): boolean {
  const data = objectWithExactKeys(value, ["mission"]);
  const item = data && objectWithExactKeys(data.mission, MISSION_KEYS);
  return !!item && stringFields(item, ["mission_id", "title", "status"])
    && timestampOrNull(item.updated_at, timestamp);
}
function taskItemIsValid(value: unknown, timestamp: TimestampValidator): boolean {
  const item = objectWithExactKeys(value, TASK_KEYS);
  return !!item && stringFields(item, ["task_id", "title", "status", "priority"])
    && stringOrNull(item.assigned_to) && integerFields(item, ["depends_on_count", "blocked_by_count"])
    && timestamp(item.updated_at);
}
function runtimeSessionIsValid(value: unknown, timestamp: TimestampValidator): boolean {
  const item = objectWithExactKeys(value, RUNTIME_SESSION_KEYS);
  return !!item && stringFields(item, ["session_id", "status"])
    && [item.current_task_id, item.active_bundle_id, item.source_runtime_epoch].every(stringOrNull)
    && timestamp(item.updated_at);
}
function sessionIsValid(value: unknown, timestamp: TimestampValidator): boolean {
  const item = objectWithExactKeys(value, SESSION_KEYS);
  return !!item && stringFields(item, ["session_id", "status", "title", "provider_id", "model_id"])
    && integerFields(item, ["total_turns"]) && timestampOrNull(item.updated_at, timestamp)
    && stringOrNull(item.runtime_owner_id);
}
function receiptIsValid(value: unknown, timestamp: TimestampValidator): boolean {
  const item = objectWithExactKeys(value, RECEIPT_KEYS);
  return !!item && stringFields(item, [
    "receipt_id", "receipt_type", "status", "run_id", "task_id", "agent_id",
  ]) && timestamp(item.created_at);
}
function agentIsValid(value: unknown, timestamp: TimestampValidator): boolean {
  const item = objectWithExactKeys(value, AGENT_KEYS);
  return !!item && stringFields(item, ["agent_id", "name", "role", "status", "provider", "model"])
    && stringOrNull(item.current_task) && timestampOrNull(item.last_heartbeat, timestamp);
}
function contactIsValid(value: unknown): boolean {
  const item = objectWithExactKeys(value, CONTACT_KEYS);
  return !!item && stringFields(item, ["agent_uid", "kind", "display_name"])
    && integerFields(item, ["capability_count"]);
}
function evolutionIsValid(value: unknown, timestamp: TimestampValidator): boolean {
  const item = objectWithExactKeys(value, EVOLUTION_KEYS);
  return !!item && stringFields(item, [
    "entry_id", "component", "change_type", "evidence_tier", "promotion_state", "status",
    "agent_id", "model",
  ]) && timestamp(item.timestamp) && [item.parent_id, item.spec_ref, item.commit_hash].every(stringOrNull)
    && integerFields(item, ["tokens_used", "gates_passed_count", "gates_failed_count"]);
}
function singleCollectionData(
  value: unknown, key: string, itemIsValid: ItemValidator,
): boolean {
  const data = objectWithExactKeys(value, [key]);
  return !!data && collectionIsValid(data[key], itemIsValid);
}
export function helmProjectionDataIsValid(
  region: HelmContextProjectionName, value: unknown, timestamp: TimestampValidator,
): boolean {
  if (region === "workspace") return workspaceDataIsValid(value);
  if (region === "bridge_session") {
    const data = objectWithExactKeys(value, BRIDGE_SESSION_KEYS);
    return bridgeSessionDataIsValid(value) && !!data
      && [data.served_identity_observed_at, data.route_evidence_expires_at,
        data.route_verification_evaluated_at].every((item) => timestampOrNull(item, timestamp));
  }
  if (region === "ui") return uiDataIsValid(value);
  if (region === "mission_control") return missionDataIsValid(value, timestamp);
  if (region === "task_board") {
    return singleCollectionData(value, "tasks", (item) => taskItemIsValid(item, timestamp));
  }
  if (region === "runtime_state") {
    return singleCollectionData(value, "sessions", (item) => runtimeSessionIsValid(item, timestamp));
  }
  if (region === "session") {
    return singleCollectionData(value, "sessions", (item) => sessionIsValid(item, timestamp));
  }
  if (region === "receipts") {
    return singleCollectionData(value, "receipts", (item) => receiptIsValid(item, timestamp));
  }
  if (region === "a2a") return singleCollectionData(value, "contacts", contactIsValid);
  if (region === "evolution") {
    return singleCollectionData(value, "entries", (item) => evolutionIsValid(item, timestamp));
  }
  if (region === "actions") return actionsDataIsValid(value);
  const data = objectWithExactKeys(value, [
    "agents", "tasks_pending", "tasks_running", "tasks_completed", "tasks_failed",
    "source_runtime_epoch",
  ]);
  return !!data && collectionIsValid(data.agents, (item) => agentIsValid(item, timestamp))
    && integerFields(data, ["tasks_pending", "tasks_running", "tasks_completed", "tasks_failed"])
    && stringOrNull(data.source_runtime_epoch);
}
export type AuthorityModality =
  | "observed"
  | "configured"
  | "unverified"
  | "stale"
  | "unknown"
  | "held";
export type HelmProjectionStatus =
  | AuthorityModality
  | "unavailable";
export type AuthorityStamp = Readonly<{
  modality: AuthorityModality;
  owner: string;
  source: string;
  observed_at: string;
  expires_at: string | null;
  runtime_epoch: string;
}>;
type AvailableHelmProjectionStatus = Exclude<HelmProjectionStatus, "unavailable">;
type EmptyProjectionData = Readonly<Record<string, never>>;
export type HelmContextProjection<
  Region extends HelmContextProjectionName = HelmContextProjectionName,
> = Readonly<{
  region: Region; status: AvailableHelmProjectionStatus; authority: AuthorityStamp;
  data: HelmProjectionDataByRegion[Region]; unavailable_reason: null;
}> | Readonly<{
  region: Region; status: "unavailable"; authority: AuthorityStamp;
  data: EmptyProjectionData; unavailable_reason: string;
}>;

export type HelmContextProjections = Readonly<{
  [Region in HelmContextProjectionName]: HelmContextProjection<Region>;
}>;

export type HelmContextEnvelope = Readonly<{
  schema_version: typeof HELM_CONTEXT_SCHEMA;
  context_digest: string;
  generated_at: string;
  expires_at: string;
  runtime_epoch: string;
  synthetic: boolean;
  provider_state_promotion: false;
  projections: HelmContextProjections;
}>;

export type HelmContextResultEvent = Readonly<{
  type: "helm.context.result";
  request_id: string;
  envelope: HelmContextEnvelope;
}>;
