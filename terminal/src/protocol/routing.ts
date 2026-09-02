import {nonSelectableRouteTargets, routePolicyFromValue, selectableRouteTargets} from "../routePolicy";
import type {
  AgentRoutesPayload,
  CanonicalRoutingDecision,
  RoutePolicyState,
  RoutingDecisionPayload,
  TabPreview,
  TranscriptLine,
} from "../types";

type JsonRecord = Record<string, unknown>;

function asRecord(value: unknown): JsonRecord {
  return typeof value === "object" && value !== null ? (value as JsonRecord) : {};
}

function asRecordList(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((entry): entry is JsonRecord => typeof entry === "object" && entry !== null)
    : [];
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter((item) => item.length > 0) : [];
}

function stringField(record: JsonRecord, key: string, fallback = ""): string {
  const value = record[key];
  return typeof value === "string" ? value.trim() || fallback : fallback;
}

function boolField(record: JsonRecord, key: string, fallback = false): boolean {
  const value = record[key];
  return typeof value === "boolean" ? value : fallback;
}

function makeLine(kind: TranscriptLine["kind"], text: string): TranscriptLine {
  return {
    id: `${kind}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    kind,
    text,
  };
}

function toLines(kind: TranscriptLine["kind"], text: string): TranscriptLine[] {
  return text
    .split("\n")
    .map((line) => line.trimEnd())
    .filter((line, index, lines) => line.length > 0 || (index > 0 && index < lines.length - 1))
    .map((line) => makeLine(kind, line));
}

function truthWord(value: boolean | undefined): string {
  return value === true ? "yes" : value === false ? "no" : "unknown";
}

function appendModelTable(lines: string[], routePolicy: RoutePolicyState): void {
  lines.push("", "## Models", "key | lane | usable now | identity verified");
  if (routePolicy.targets.length === 0) {
    lines.push("none");
    return;
  }
  routePolicy.targets.forEach((entry, index) => {
    const key = index < 9
      ? String(index + 1)
      : index === 9
        ? "0"
        : index < 36 ? String.fromCharCode(87 + index) : "–";
    lines.push(
      `- ${entry.alias} -> ${entry.label} (${entry.provider}:${entry.model}) [${entry.routeState}] | key ${key} | usable now ${truthWord(entry.usableNow)} | identity verified ${truthWord(entry.identityVerified)}${entry.availabilityReason ? ` | ${entry.availabilityReason}` : ""}`,
    );
  });
}

function displayModelRouteLabel(value: string, provider?: string, model?: string): string {
  const normalized = value.trim();
  const providerId = (provider ?? "").trim().toLowerCase();
  const modelId = (model ?? "").trim().toLowerCase();
  const normalizedId = normalized.toLowerCase();
  const routeIdentity = (modelId || normalizedId).replace(/[._\s]+/g, "-");
  const isOpus = (providerId === "claude" && routeIdentity.includes("opus")) || normalizedId.includes("opus");
  if (isOpus && routeIdentity.includes("4-8")) {
    return "Claude Opus 4.8 | high reasoning lane";
  }
  if (isOpus && routeIdentity.includes("4-6")) {
    return "Claude Opus 4.6 | high reasoning lane";
  }
  if ((providerId === "claude" && modelId.includes("sonnet")) || normalized.toLowerCase().includes("sonnet")) {
    return "Claude Sonnet 4.6 | balanced lane";
  }
  const isCodex = providerId === "codex" || routeIdentity.includes("codex") || routeIdentity.includes("gpt-5");
  if (isCodex && routeIdentity.includes("5-5")) {
    return "GPT-5.5 (Codex) | fast operator lane";
  }
  if (isCodex && routeIdentity.includes("5-4")) {
    return "Codex 5.4 | fast operator lane";
  }
  return normalized;
}

function normalizeCanonicalRoutingDecision(value: unknown): CanonicalRoutingDecision | undefined {
  const decision = asRecord(value);
  const routeId = stringField(decision, "route_id");
  if (!routeId) {
    return undefined;
  }
  return {
    route_id: routeId,
    provider_id: stringField(decision, "provider_id"),
    model_id: stringField(decision, "model_id"),
    strategy: stringField(decision, "strategy", "responsive"),
    reason: stringField(decision, "reason"),
    fallback_chain: asStringArray(decision.fallback_chain),
    degraded: boolField(decision, "degraded"),
    metadata: asRecord(decision.metadata),
  };
}

export function routingDecisionPayloadFromEvent(event: JsonRecord): RoutingDecisionPayload | undefined {
  const payload = asRecord(event.payload);
  if (stringField(payload, "domain") !== "routing_decision" || stringField(payload, "version") !== "v1") {
    return undefined;
  }
  const decision = normalizeCanonicalRoutingDecision(payload.decision);
  if (!decision) {
    return undefined;
  }
  return {
    version: "v1",
    domain: "routing_decision",
    decision,
    strategies: asStringArray(payload.strategies),
    targets: asRecordList(payload.targets),
    fallback_targets: asRecordList(payload.fallback_targets),
  };
}

export function handshakeRouteConfigFromEvent(
  value: unknown,
  current: RoutePolicyState,
): {provider: string; model: string; policy?: RoutePolicyState} {
  const event = asRecord(value);
  const providers = asRecordList(event.providers);
  const defaultProviderId = stringField(event, "default_provider");
  const selectedProvider = providers.find(
    (entry) => stringField(entry, "provider_id") === defaultProviderId,
  ) ?? providers[0];
  const provider = selectedProvider ? stringField(selectedProvider, "provider_id", current.provider) : current.provider;
  const model = selectedProvider ? stringField(selectedProvider, "default_model", current.model) : current.model;
  const routingPayload = routingDecisionPayloadFromEvent(event);
  const policyRecord = asRecord(event.policy);
  const policy = routingPayload || Object.keys(policyRecord).length > 0
    ? routePolicyFromValue(routingPayload ?? policyRecord, current)
    : undefined;
  return {provider, model, policy};
}

export function agentRoutesPayloadFromEvent(event: JsonRecord): AgentRoutesPayload | undefined {
  const payload = asRecord(event.payload);
  if (stringField(payload, "domain") !== "agent_routes" || stringField(payload, "version") !== "v1") {
    return undefined;
  }
  return {
    version: "v1",
    domain: "agent_routes",
    routes: asRecordList(payload.routes),
    openclaw: asRecord(payload.openclaw),
    subagent_capabilities: asStringArray(payload.subagent_capabilities),
  };
}

export function modelPolicyToLines(payload: JsonRecord): TranscriptLine[] {
  const routePolicy = routePolicyFromValue(payload);
  const routingPayload = routingDecisionPayloadFromEvent(payload);
  if (routingPayload) {
    const decision = routingPayload.decision;
    const metadata = asRecord(decision.metadata);
    const activeLabel = displayModelRouteLabel(
      stringField(metadata, "active_label", decision.model_id || "unknown"),
      decision.provider_id,
      decision.model_id,
    );
    const lines = [
      "# Model Policy",
      `Active: ${activeLabel}`,
      `Route: ${decision.route_id}`,
      `Strategy: ${decision.strategy}`,
      `Default route: ${stringField(metadata, "default_route", "unknown")}`,
      ...(routePolicy.fallbackNotice ? [`Notice: ${routePolicy.fallbackNotice}`] : []),
      "",
      "## Fallback chain",
    ];
    if (routingPayload.fallback_targets.length === 0) {
      lines.push("none");
    } else {
      for (const entry of routingPayload.fallback_targets.slice(0, 6)) {
        lines.push(
          `- ${stringField(entry, "label", stringField(entry, "alias", "?"))} [${stringField(entry, "provider", "?")} | ${stringField(entry, "route_state", "unknown")}]`,
        );
      }
    }
    appendModelTable(lines, routePolicy);
    return toLines("system", lines.join("\n"));
  }
  const policy =
    typeof payload.policy === "object" && payload.policy !== null ? (payload.policy as JsonRecord) : payload;
  const activeLabel = displayModelRouteLabel(
    String(policy.active_label ?? policy.selected_model ?? "unknown"),
    String(policy.selected_provider ?? ""),
    String(policy.selected_model ?? ""),
  );
  const lines = [
    "# Model Policy",
    `Active: ${activeLabel}`,
    `Route: ${String(policy.selected_route ?? "unknown")}`,
    `Strategy: ${String(policy.strategy ?? "responsive")}`,
    `Default route: ${String(policy.default_route ?? "unknown")}`,
    ...(routePolicy.fallbackNotice ? [`Notice: ${routePolicy.fallbackNotice}`] : []),
    "",
    "## Fallback chain",
  ];
  const chain = Array.isArray(policy.fallback_chain) ? policy.fallback_chain : [];
  if (chain.length === 0) {
    lines.push("none");
  } else {
    for (const entry of chain.slice(0, 6)) {
      const record = typeof entry === "object" && entry !== null ? (entry as JsonRecord) : {};
      lines.push(
        `- ${String(record.label ?? record.alias ?? "?")} [${String(record.provider ?? "?")} | ${String(record.route_state ?? "unknown")}]`,
      );
    }
  }
  appendModelTable(lines, routePolicy);
  return toLines("system", lines.join("\n"));
}

export function modelPolicyToPreview(payload: JsonRecord): TabPreview {
  const routePolicy = routePolicyFromValue(payload);
  const routingPayload = routingDecisionPayloadFromEvent(payload);
  if (routingPayload) {
    const decision = routingPayload.decision;
    const metadata = asRecord(decision.metadata);
    return {
      Active: displayModelRouteLabel(
        stringField(metadata, "active_label", decision.model_id || "unknown"),
        decision.provider_id,
        decision.model_id,
      ),
      Route: decision.route_id,
      "Route state": routePolicy.routeState,
      Strategy: decision.strategy,
      "Default route": stringField(metadata, "default_route", "unknown"),
      Fallbacks: String(routingPayload.fallback_targets.length),
      Targets: String(selectableRouteTargets(routePolicy).length),
      "Non-primary routes": String(nonSelectableRouteTargets(routePolicy).length),
    };
  }
  const policy =
    typeof payload.policy === "object" && payload.policy !== null ? (payload.policy as JsonRecord) : payload;
  const chain = Array.isArray(policy.fallback_chain) ? policy.fallback_chain : [];
  const activeLabel = displayModelRouteLabel(
    String(policy.active_label ?? policy.selected_model ?? "unknown"),
    String(policy.selected_provider ?? ""),
    String(policy.selected_model ?? ""),
  );
  return {
    Active: activeLabel,
    Route: String(policy.selected_route ?? "unknown"),
    "Route state": routePolicy.routeState,
    Strategy: String(policy.strategy ?? "responsive"),
    "Default route": String(policy.default_route ?? "unknown"),
    Fallbacks: String(chain.length),
    Targets: String(selectableRouteTargets(routePolicy).length),
    "Non-primary routes": String(nonSelectableRouteTargets(routePolicy).length),
  };
}

export function agentRoutesToLines(payload: JsonRecord): TranscriptLine[] {
  const typedPayload = agentRoutesPayloadFromEvent(payload);
  const routes =
    typedPayload ??
    (typeof payload.routes === "object" && payload.routes !== null ? (payload.routes as JsonRecord) : payload);
  const routeItems = Array.isArray(routes.routes) ? routes.routes : [];
  const openclaw =
    typeof routes.openclaw === "object" && routes.openclaw !== null ? (routes.openclaw as JsonRecord) : {};
  const lines = ["# Agent Routes", "", "## Route profiles"];
  for (const entry of routeItems) {
    const record = typeof entry === "object" && entry !== null ? (entry as JsonRecord) : {};
    lines.push(
      `- ${String(record.intent ?? "?")} -> ${String(record.provider ?? "?")}:${String(record.model_alias ?? "?")} | effort ${String(record.reasoning ?? "?")} | role ${String(record.role ?? "?")}`,
    );
  }
  lines.push(
    "",
    "## OpenClaw",
    `Present: ${String(openclaw.present ?? false)}`,
    `Readable: ${String(openclaw.readable ?? false)}`,
    `Agents: ${String(openclaw.agents_count ?? 0)}`,
    `Providers: ${Array.isArray(openclaw.providers) ? openclaw.providers.map(String).join(", ") || "none" : "none"}`,
  );
  return toLines("system", lines.join("\n"));
}

export function agentRoutesToPreview(payload: JsonRecord): TabPreview {
  const typedPayload = agentRoutesPayloadFromEvent(payload);
  const routes =
    typedPayload ??
    (typeof payload.routes === "object" && payload.routes !== null ? (payload.routes as JsonRecord) : payload);
  const routeItems = Array.isArray(routes.routes) ? routes.routes : [];
  const openclaw =
    typeof routes.openclaw === "object" && routes.openclaw !== null ? (routes.openclaw as JsonRecord) : {};
  return {
    Routes: String(routeItems.length),
    "OpenClaw agents": String(openclaw.agents_count ?? 0),
    Providers: Array.isArray(openclaw.providers) ? openclaw.providers.map(String).join(", ") || "none" : "none",
    "Primary route": routeItems.length > 0 ? String((routeItems[0] as JsonRecord).intent ?? "none") : "none",
  };
}
