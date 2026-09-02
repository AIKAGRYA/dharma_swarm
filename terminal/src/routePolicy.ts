import type {RoutePolicyState, RouteTarget, RouteState} from "./types";

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asRecordList(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.filter((entry): entry is Record<string, unknown> => (
        typeof entry === "object" && entry !== null && !Array.isArray(entry)
      ))
    : [];
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value.trim() || fallback : fallback;
}

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function optionalBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((entry) => asString(entry)).filter(Boolean)
    : [];
}

function fallbackNotice(value: unknown): string | undefined {
  if (typeof value === "string") {
    return asString(value) || undefined;
  }
  const record = asRecord(value);
  return asString(record.message) || undefined;
}

export function routeIdFor(provider: string, model: string, explicitRouteId?: string): string {
  const normalized = explicitRouteId?.trim();
  if (normalized) {
    return normalized;
  }
  return [provider.trim(), model.trim()].filter(Boolean).join(":") || "unknown";
}

function normalizeRouteState(value: unknown, selectable: boolean): RouteState {
  if (typeof value === "boolean") {
    return value ? "degraded" : (selectable ? "unverified" : "unavailable");
  }
  const normalized = asString(value).toLowerCase();
  if (normalized === "ready" || normalized === "unverified" || normalized === "degraded" || normalized === "slow" || normalized === "unavailable" || normalized === "invalid") {
    return normalized;
  }
  return selectable ? "unverified" : "unavailable";
}

function explicitRouteState(value: unknown): RouteState | undefined {
  const normalized = asString(value).toLowerCase();
  return normalized === "ready"
    || normalized === "unverified"
    || normalized === "degraded"
    || normalized === "slow"
    || normalized === "unavailable"
    || normalized === "invalid"
    ? normalized
    : undefined;
}

function conservativeRouteState(states: Array<RouteState | undefined>, selectable: boolean): RouteState {
  const present = new Set(states.filter((state): state is RouteState => Boolean(state)));
  for (const state of ["invalid", "unavailable", "unverified", "degraded", "slow", "ready"] as const) {
    if (present.has(state)) {
      return state;
    }
  }
  return selectable ? "unverified" : "unavailable";
}

function normalizeRouteTarget(target: Record<string, unknown>): RouteTarget | null {
  const provider = asString(target.provider);
  const model = asString(target.model);
  const alias = asString(target.alias);
  const label = asString(target.label);
  if (!provider || !model || !alias) {
    return null;
  }
  const requestedSelectable = asBoolean(target.picker_visible, asBoolean(target.selectable, asBoolean(target.available, true)));
  const routeState = normalizeRouteState(target.route_state, requestedSelectable);
  const selectable = routeState !== "invalid" && routeState !== "unavailable" && requestedSelectable;
  return {
    alias,
    label: label || alias,
    provider,
    model,
    routeId: routeIdFor(provider, model, asString(target.route_id)),
    routeState,
    availabilityReason: asString(target.availability_reason) || undefined,
    selectable,
    usableNow: optionalBoolean(target.usable_now),
    identityVerified: optionalBoolean(target.identity_verified),
    oracleProviders: asStringList(target.oracle_providers),
  };
}

export function defaultRoutePolicy(): RoutePolicyState {
  // Preserve the configured bootstrap identity only as an unverified
  // placeholder. The handshake replaces it with current route authority.
  return {
    routeId: "claude:claude-opus-4.8",
    provider: "claude",
    model: "claude-opus-4.8",
    strategy: "responsive",
    routeState: "unverified",
    selectable: false,
    availabilityReason: "awaiting_bridge_policy",
    fallbackChain: [],
    activeLabel: "Claude Opus 4.8",
    targets: [],
  };
}

export function routePolicyWithConfig(
  current: RoutePolicyState,
  provider: string,
  model: string,
  strategy: string,
): RoutePolicyState {
  const matchingTargets = current.targets.filter((target) => target.provider === provider && target.model === model);
  const matchingTarget = matchingTargets.length === 1 ? matchingTargets[0] : undefined;
  const nextRouteId = matchingTarget?.routeId ?? routeIdFor(provider, model);
  const identityChanged = current.routeId !== nextRouteId || current.provider !== provider || current.model !== model;
  return {
    ...current,
    routeId: nextRouteId,
    provider,
    model,
    strategy,
    // Configuration identifies the requested route; it is not liveness or
    // selection authority. A subsequent typed policy must confirm readiness.
    routeState: identityChanged ? "unverified" : current.routeState,
    selectable: identityChanged ? false : current.selectable,
    availabilityReason: identityChanged
      ? "awaiting_route_authority"
      : current.availabilityReason,
    activeLabel: matchingTarget?.label ?? (identityChanged ? undefined : current.activeLabel),
  };
}

function failClosedRoutePolicy(current: RoutePolicyState, reason: string): RoutePolicyState {
  const retainTerminalNegative = current.routeState === "invalid" || current.routeState === "unavailable";
  return {
    ...current,
    routeState: retainTerminalNegative ? current.routeState : "unverified",
    selectable: false,
    availabilityReason: retainTerminalNegative ? current.availabilityReason ?? reason : reason,
    targets: current.targets.map((target) => {
      const targetIsTerminalNegative = target.routeState === "invalid" || target.routeState === "unavailable";
      return {
        ...target,
        routeState: targetIsTerminalNegative ? target.routeState : "unverified",
        selectable: false,
        availabilityReason: targetIsTerminalNegative
          ? target.availabilityReason
          : reason,
      };
    }),
  };
}

export function routePolicyFromValue(value: unknown, current: RoutePolicyState = defaultRoutePolicy()): RoutePolicyState {
  const record = asRecord(value);
  if (Object.keys(record).length === 0) {
    return failClosedRoutePolicy(current, "malformed_route_policy");
  }
  const payload =
    asString(record.domain) === "routing_decision" && Object.keys(asRecord(record.decision)).length > 0
      ? record
      : asRecord(record.payload).domain === "routing_decision"
        ? asRecord(record.payload)
        : record;

  const decisionRecord = asRecord(payload.decision);
  const metadata = asRecord(decisionRecord.metadata);
  const payloadPolicy = asRecord(payload.policy);
  const policy = Object.keys(decisionRecord).length > 0 ? decisionRecord : Object.keys(payloadPolicy).length > 0 ? payloadPolicy : payload;

  const targets = asRecordList(payload.targets ?? policy.targets)
    .map(normalizeRouteTarget)
    .filter((target): target is RouteTarget => Boolean(target));
  const explicitRouteId = asString(policy.route_id ?? policy.selected_route);
  const routeIdentityTargets = explicitRouteId
    ? targets.filter((target) => target.routeId === explicitRouteId)
    : [];
  const routeIdentityTarget = routeIdentityTargets.length === 1 ? routeIdentityTargets[0] : undefined;
  const provider = asString(policy.provider_id ?? policy.selected_provider, routeIdentityTarget?.provider ?? "");
  const model = asString(policy.model_id ?? policy.selected_model, routeIdentityTarget?.model ?? "");
  if (!provider || !model) {
    return failClosedRoutePolicy(current, "malformed_route_identity");
  }
  const strategy = asString(policy.strategy, current.strategy);
  const routeId = routeIdFor(provider, model, explicitRouteId);
  const identityTargets = targets.filter((target) => target.provider === provider && target.model === model);
  const matchingTarget = targets.find((target) => target.routeId === routeId)
    ?? (identityTargets.length === 1 ? identityTargets[0] : undefined);
  const explicitNonSelectable = matchingTarget?.selectable === false
    || policy.selectable === false
    || metadata.selectable === false;
  const selectable = explicitNonSelectable
    ? false
    : matchingTarget?.selectable ?? asBoolean(policy.selectable ?? metadata.selectable, false);
  const fallbackTargets = asRecordList(payload.fallback_targets ?? policy.fallback_chain);
  const fallbackChain = fallbackTargets
    .map((entry) => routeIdFor(asString(entry.provider), asString(entry.model), asString(entry.route_id ?? entry.alias)))
    .filter((entry) => entry !== "unknown");
  const incomingRouteState = conservativeRouteState([
    explicitRouteState(policy.route_state),
    explicitRouteState(metadata.route_state),
    matchingTarget?.routeState,
    policy.degraded === true ? "degraded" : undefined,
  ], selectable);
  const effectiveIncomingRouteState = explicitNonSelectable
    && incomingRouteState !== "invalid"
    && incomingRouteState !== "unavailable"
    ? "unavailable"
    : incomingRouteState;
  const routeExplicitlyDead = effectiveIncomingRouteState === "invalid" || effectiveIncomingRouteState === "unavailable";
  return {
    routeId,
    provider,
    model,
    strategy,
    routeState: effectiveIncomingRouteState,
    selectable: !routeExplicitlyDead && selectable,
    availabilityReason: routeExplicitlyDead
      ? asString(policy.availability_reason ?? metadata.availability_reason) || matchingTarget?.availabilityReason
      : matchingTarget?.availabilityReason
        ?? (asString(policy.availability_reason ?? metadata.availability_reason) || undefined),
    defaultRouteId: asString(metadata.default_route ?? policy.default_route) || undefined,
    fallbackChain,
    activeLabel: asString(metadata.active_label ?? policy.active_label) || matchingTarget?.label || undefined,
    fallbackNotice: fallbackNotice(metadata.fallback_notice ?? policy.fallback_notice ?? payload.fallback_notice),
    targets,
  };
}

export function routeLabel(policy: RoutePolicyState): string {
  return `${policy.provider}:${policy.model.replace(/:cloud$/, "")}`;
}

export function routeSummary(policy: RoutePolicyState): string {
  const parts = [policy.routeState, routeLabel(policy)];
  if (policy.availabilityReason) {
    parts.push(policy.availabilityReason);
  }
  return parts.join(" | ");
}

export function selectableRouteTargets(policy: RoutePolicyState): RouteTarget[] {
  return policy.targets.filter((target) => target.selectable);
}

export function nonSelectableRouteTargets(policy: RoutePolicyState): RouteTarget[] {
  return policy.targets.filter((target) => !target.selectable);
}
