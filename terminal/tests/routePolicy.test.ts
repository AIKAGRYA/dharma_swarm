import {describe, expect, test} from "bun:test";

import {
  defaultRoutePolicy,
  nonSelectableRouteTargets,
  routeLabel,
  routePolicyFromValue,
  routePolicyWithConfig,
  routePolicyWithSuccessfulReceipt,
  routeSummary,
  selectableRouteTargets,
} from "../src/routePolicy";
import type {ProviderRouteReceipt} from "../src/types";

function providerReceipt(overrides: Partial<ProviderRouteReceipt> = {}): ProviderRouteReceipt {
  return {
    requestId: "request-1",
    sessionId: "session-1",
    provider: "codex",
    model: "gpt-5.5",
    routeId: "codex:gpt-5.5",
    evidenceKind: "provider_completion",
    ...overrides,
  };
}

describe("routePolicyFromValue", () => {
  test("normalizes a ready codex route with a truthful fallback chain", () => {
    const policy = routePolicyFromValue({
      version: "v1",
      domain: "routing_decision",
      decision: {
        route_id: "codex:gpt-5.4",
        provider_id: "codex",
        model_id: "gpt-5.4",
        strategy: "responsive",
        route_state: "ready",
        metadata: {
          default_route: "codex:gpt-5.4",
          active_label: "Codex 5.4",
        },
      },
      targets: [
        {
          alias: "codex:gpt-5.4",
          label: "Codex 5.4",
          provider: "codex",
          model: "gpt-5.4",
          route_id: "codex:gpt-5.4",
          route_state: "ready",
          picker_visible: true,
        },
      ],
      fallback_targets: [
        {provider: "claude", model: "sonnet-4.5", route_id: "claude:sonnet-4.5"},
        {provider: "openrouter", model: "anthropic/claude-sonnet-4.5", route_id: "openrouter:anthropic/claude-sonnet-4.5"},
      ],
    });

    expect(policy.provider).toBe("codex");
    expect(policy.model).toBe("gpt-5.4");
    expect(policy.routeState).toBe("ready");
    expect(policy.selectable).toBe(true);
    expect(policy.defaultRouteId).toBe("codex:gpt-5.4");
    expect(policy.fallbackChain).toEqual(["claude:sonnet-4.5", "openrouter:anthropic/claude-sonnet-4.5"]);
    expect(routeLabel(policy)).toBe("codex:gpt-5.4");
  });

  test("accepts a claude route selected through payload.policy", () => {
    const policy = routePolicyFromValue({
      payload: {
        domain: "routing_decision",
        policy: {
          route_id: "claude:sonnet-4.5",
          provider_id: "claude",
          model_id: "sonnet-4.5",
          strategy: "deliberate",
          route_state: "ready",
          selectable: true,
          active_label: "Claude Sonnet 4.5",
        },
        targets: [
          {
            alias: "claude:sonnet-4.5",
            label: "Claude Sonnet 4.5",
            provider: "claude",
            model: "sonnet-4.5",
            route_state: "ready",
            picker_visible: true,
          },
        ],
      },
    });

    expect(policy.routeId).toBe("claude:sonnet-4.5");
    expect(policy.provider).toBe("claude");
    expect(policy.model).toBe("sonnet-4.5");
    expect(policy.strategy).toBe("deliberate");
    expect(policy.activeLabel).toBe("Claude Sonnet 4.5");
  });

  test("keeps degraded ollama routes visible and selectable", () => {
    const policy = routePolicyFromValue({
      version: "v1",
      domain: "routing_decision",
      decision: {
        route_id: "ollama:qwen2.5-coder:14b",
        provider_id: "ollama",
        model_id: "qwen2.5-coder:14b",
        strategy: "responsive",
        route_state: "degraded",
      },
      targets: [
        {
          alias: "ollama:qwen2.5-coder:14b",
          label: "Ollama Qwen 14B",
          provider: "ollama",
          model: "qwen2.5-coder:14b",
          route_state: "degraded",
          availability_reason: "warming local runtime",
          picker_visible: true,
        },
      ],
    });

    expect(policy.routeState).toBe("degraded");
    expect(policy.selectable).toBe(true);
    expect(selectableRouteTargets(policy)).toHaveLength(1);
    expect(routeSummary(policy)).toContain("warming local runtime");
  });

  test("keeps invalid openrouter targets clearly non-selectable", () => {
    const policy = routePolicyFromValue({
      version: "v1",
      domain: "routing_decision",
      decision: {
        route_id: "codex:gpt-5.4",
        provider_id: "codex",
        model_id: "gpt-5.4",
        strategy: "responsive",
        route_state: "ready",
      },
      targets: [
        {
          alias: "codex:gpt-5.4",
          label: "Codex 5.4",
          provider: "codex",
          model: "gpt-5.4",
          route_state: "ready",
          picker_visible: true,
        },
        {
          alias: "openrouter:anthropic/claude-sonnet-4.5",
          label: "OpenRouter Claude Sonnet 4.5",
          provider: "openrouter",
          model: "anthropic/claude-sonnet-4.5",
          route_state: "invalid",
          availability_reason: "missing credential",
          picker_visible: false,
        },
      ],
      fallback_targets: [{provider: "codex", model: "gpt-5.4", route_id: "codex:gpt-5.4"}],
    });

    expect(selectableRouteTargets(policy).map((target) => target.routeId)).toEqual(["codex:gpt-5.4"]);
    expect(nonSelectableRouteTargets(policy).map((target) => target.routeId)).toEqual([
      "openrouter:anthropic/claude-sonnet-4.5",
    ]);
    expect(nonSelectableRouteTargets(policy)[0]?.routeState).toBe("invalid");
    expect(nonSelectableRouteTargets(policy)[0]?.availabilityReason).toBe("missing credential");
    expect(policy.fallbackChain).toEqual(["codex:gpt-5.4"]);
  });

  test("preserves selectable unverified routes without promoting them to ready", () => {
    const policy = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      selected_route: "codex:gpt-5.5",
      targets: [{
        alias: "gpt-5.5",
        label: "GPT-5.5 (Codex)",
        provider: "codex",
        model: "gpt-5.5",
        route_state: "unverified",
        picker_visible: true,
        available: false,
        availability_reason: "local_cli_auth_unverified",
      }],
    });

    expect(policy.routeState).toBe("unverified");
    expect(policy.selectable).toBe(true);
    expect(policy.availabilityReason).toBe("local_cli_auth_unverified");
    expect(selectableRouteTargets(policy)).toHaveLength(1);
  });

  test("preserves a sane default policy baseline", () => {
    const policy = defaultRoutePolicy();

    // The bootstrap identity is visible but cannot claim readiness before the
    // bridge supplies current policy.
    expect(policy.routeId).toBe("claude:claude-opus-4.8");
    expect(policy.provider).toBe("claude");
    expect(policy.model).toBe("claude-opus-4.8");
    expect(policy.routeState).toBe("unverified");
    expect(policy.selectable).toBe(false);
    expect(policy.availabilityReason).toBe("awaiting_bridge_policy");
    expect(policy.targets).toEqual([]);
  });

  test("promotes only the selected target after a successful provider receipt", () => {
    const current = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [
        {alias: "gpt-5.5", label: "GPT-5.5", provider: "codex", model: "gpt-5.5", route_state: "unverified", picker_visible: true},
        {alias: "opus", label: "Opus", provider: "claude", model: "claude-opus-4.8", route_state: "unverified", picker_visible: true},
      ],
    });

    const promoted = routePolicyWithSuccessfulReceipt(current, providerReceipt());

    expect(promoted.routeState).toBe("ready");
    expect(promoted.lastConfirmedRouteId).toBe("codex:gpt-5.5");
    expect(promoted.targets.find((target) => target.provider === "codex")?.routeState).toBe("ready");
    expect(promoted.targets.find((target) => target.provider === "claude")?.routeState).toBe("unverified");
  });

  test("keeps newer success proof across unknown refreshes but yields to explicit unavailability", () => {
    const selected = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "gpt-5.5", label: "GPT-5.5", provider: "codex", model: "gpt-5.5", route_state: "unverified", picker_visible: true}],
    });
    const proven = routePolicyWithSuccessfulReceipt(selected, providerReceipt());

    const unknownRefresh = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "gpt-5.5", label: "GPT-5.5", provider: "codex", model: "gpt-5.5", route_state: "unverified", picker_visible: true}],
    }, proven);
    expect(unknownRefresh.routeState).toBe("ready");

    const deadRefresh = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "gpt-5.5", label: "GPT-5.5", provider: "codex", model: "gpt-5.5", route_state: "unavailable", picker_visible: false}],
    }, unknownRefresh);
    expect(deadRefresh.routeState).toBe("unavailable");
  });

  test("configuration alone never fabricates a confirmed route", () => {
    const configured = routePolicyWithConfig(defaultRoutePolicy(), "codex", "gpt-5.5", "responsive");
    expect(configured.routeId).toBe("codex:gpt-5.5");
    expect(configured.routeState).toBe("unverified");
    expect(configured.selectable).toBe(false);
    expect(configured.lastConfirmedRouteId).toBeUndefined();
  });

  test("configuration changes cannot carry readiness or proof across model identity", () => {
    const selected = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "gpt-5.5", label: "GPT-5.5", provider: "codex", model: "gpt-5.5", route_state: "unverified", picker_visible: true}],
    });
    const proven = routePolicyWithSuccessfulReceipt(selected, providerReceipt());
    const switched = routePolicyWithConfig(proven, "codex", "gpt-5.4", "responsive");

    expect(switched.routeId).toBe("codex:gpt-5.4");
    expect(switched.model).toBe("gpt-5.4");
    expect(switched.routeState).toBe("unverified");
    expect(switched.selectable).toBe(false);
    expect(switched.lastConfirmedRouteId).toBeUndefined();
  });

  test("a proven A route cannot be resurrected after A to B to A transitions", () => {
    const routeA = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "a", label: "A", provider: "codex", model: "gpt-5.5", route_state: "unverified", picker_visible: true}],
    });
    const provenA = routePolicyWithSuccessfulReceipt(routeA, providerReceipt());
    const routeB = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.4",
      targets: [{alias: "b", label: "B", provider: "codex", model: "gpt-5.4", route_state: "ready", picker_visible: true}],
    }, provenA);
    const returnedA = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "a", label: "A", provider: "codex", model: "gpt-5.5", route_state: "unverified", picker_visible: true}],
    }, routeB);

    expect(routeB.lastConfirmedRouteId).toBeUndefined();
    expect(returnedA.routeState).toBe("unverified");
    expect(returnedA.lastConfirmedRouteId).toBeUndefined();
  });

  test("explicit unavailability dominates contradictory unverified targets", () => {
    const selected = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "a", label: "A", provider: "codex", model: "gpt-5.5", route_state: "unverified", picker_visible: true}],
    });
    const proven = routePolicyWithSuccessfulReceipt(selected, providerReceipt());
    const contradicted = routePolicyFromValue({
      version: "v1",
      domain: "routing_decision",
      decision: {
        route_id: "codex:gpt-5.5",
        provider_id: "codex",
        model_id: "gpt-5.5",
        strategy: "responsive",
        metadata: {route_state: "unavailable", availability_reason: "explicit route revocation"},
      },
      targets: [{alias: "a", label: "A", provider: "codex", model: "gpt-5.5", route_state: "unverified", picker_visible: true, availability_reason: "stale unknown"}],
    }, proven);

    expect(contradicted.routeState).toBe("unavailable");
    expect(contradicted.selectable).toBe(false);
    expect(contradicted.availabilityReason).toBe("explicit route revocation");
    expect(contradicted.lastConfirmedRouteId).toBeUndefined();
  });

  test("dead targets cannot remain picker-selectable through contradictory flags", () => {
    const dead = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{
        alias: "dead",
        label: "Dead route",
        provider: "codex",
        model: "gpt-5.5",
        route_state: "invalid",
        picker_visible: true,
      }],
    });

    expect(dead.routeState).toBe("invalid");
    expect(dead.selectable).toBe(false);
    expect(dead.targets[0]?.selectable).toBe(false);
    expect(selectableRouteTargets(dead)).toHaveLength(0);
  });

  test("provider receipts bind to the exact route id, not provider and model alone", () => {
    const current = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      selected_route: "codex:gpt-5.5:primary",
      targets: [
        {alias: "primary", label: "Primary", provider: "codex", model: "gpt-5.5", route_id: "codex:gpt-5.5:primary", route_state: "unverified", picker_visible: true},
        {alias: "shadow", label: "Shadow", provider: "codex", model: "gpt-5.5", route_id: "codex:gpt-5.5:shadow", route_state: "unverified", picker_visible: true},
      ],
    });

    const mismatched = routePolicyWithSuccessfulReceipt(current, providerReceipt({routeId: "codex:gpt-5.5:shadow"}));
    expect(mismatched).toBe(current);

    const promoted = routePolicyWithSuccessfulReceipt(current, providerReceipt({routeId: "codex:gpt-5.5:primary"}));
    expect(promoted.targets.find((target) => target.routeId.endsWith(":primary"))?.routeState).toBe("ready");
    expect(promoted.targets.find((target) => target.routeId.endsWith(":shadow"))?.routeState).toBe("unverified");
  });
});
