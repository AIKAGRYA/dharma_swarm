import {describe, expect, test} from "bun:test";

import {
  defaultRoutePolicy,
  nonSelectableRouteTargets,
  routeLabel,
  routePolicyFromValue,
  routePolicyWithConfig,
  routeSummary,
  selectableRouteTargets,
} from "../src/routePolicy";

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

  test("does not preserve a prior ready claim across an unverified refresh", () => {
    const ready = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "gpt-5.5", label: "GPT-5.5", provider: "codex", model: "gpt-5.5", route_state: "ready", picker_visible: true}],
    });

    const refreshed = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "gpt-5.5", label: "GPT-5.5", provider: "codex", model: "gpt-5.5", route_state: "unverified", picker_visible: true}],
    }, ready);

    expect(ready.routeState).toBe("ready");
    expect(refreshed.routeState).toBe("unverified");
    expect(refreshed.targets[0]?.routeState).toBe("unverified");
  });

  test("configuration alone never fabricates a confirmed route", () => {
    const configured = routePolicyWithConfig(defaultRoutePolicy(), "codex", "gpt-5.5", "responsive");
    expect(configured.routeId).toBe("codex:gpt-5.5");
    expect(configured.routeState).toBe("unverified");
    expect(configured.selectable).toBe(false);
  });

  test("configuration changes cannot carry readiness across model identity", () => {
    const selected = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "gpt-5.5", label: "GPT-5.5", provider: "codex", model: "gpt-5.5", route_state: "ready", picker_visible: true}],
    });
    const switched = routePolicyWithConfig(selected, "codex", "gpt-5.4", "responsive");

    expect(switched.routeId).toBe("codex:gpt-5.4");
    expect(switched.model).toBe("gpt-5.4");
    expect(switched.routeState).toBe("unverified");
    expect(switched.selectable).toBe(false);
  });

  test("configuration cannot promote a previously advertised ready target", () => {
    const current = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [
        {alias: "a", label: "A", provider: "codex", model: "gpt-5.5", route_state: "ready", picker_visible: true},
        {alias: "b", label: "B", provider: "codex", model: "gpt-5.4", route_state: "ready", picker_visible: true},
      ],
    });

    const configured = routePolicyWithConfig(current, "codex", "gpt-5.4", "responsive");

    expect(configured.routeId).toBe("codex:gpt-5.4");
    expect(configured.routeState).toBe("unverified");
    expect(configured.selectable).toBe(false);
    expect(configured.availabilityReason).toBe("awaiting_route_authority");
  });

  test("malformed policy refreshes fail closed without preserving ready targets", () => {
    const ready = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "a", label: "A", provider: "codex", model: "gpt-5.5", route_state: "ready", picker_visible: true}],
    });

    for (const malformed of [undefined, null, [], {}, {route_state: "ready"}]) {
      const rejected = routePolicyFromValue(malformed, ready);
      expect(rejected.routeId).toBe("codex:gpt-5.5");
      expect(rejected.routeState).toBe("unverified");
      expect(rejected.selectable).toBe(false);
      expect(rejected.targets[0]?.routeState).toBe("unverified");
      expect(rejected.targets[0]?.selectable).toBe(false);
    }
  });

  test("an old ready route cannot be resurrected after A to B to A transitions", () => {
    const routeA = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "a", label: "A", provider: "codex", model: "gpt-5.5", route_state: "ready", picker_visible: true}],
    });
    const routeB = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.4",
      targets: [{alias: "b", label: "B", provider: "codex", model: "gpt-5.4", route_state: "ready", picker_visible: true}],
    }, routeA);
    const returnedA = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "a", label: "A", provider: "codex", model: "gpt-5.5", route_state: "unverified", picker_visible: true}],
    }, routeB);

    expect(returnedA.routeState).toBe("unverified");
  });

  test("explicit unavailability dominates contradictory unverified targets", () => {
    const current = routePolicyFromValue({
      selected_provider: "codex",
      selected_model: "gpt-5.5",
      targets: [{alias: "a", label: "A", provider: "codex", model: "gpt-5.5", route_state: "ready", picker_visible: true}],
    });
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
    }, current);

    expect(contradicted.routeState).toBe("unavailable");
    expect(contradicted.selectable).toBe(false);
    expect(contradicted.availabilityReason).toBe("explicit route revocation");
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

  test("retains explicit usability and evaluator identity truth without inferring either", () => {
    const policy = routePolicyFromValue({
      selected_provider: "kimi_code",
      selected_model: "k3",
      selected_route: "kimi_code:k3",
      targets: [
        {
          alias: "explicit",
          label: "Explicit truth",
          provider: "kimi_code",
          model: "k3",
          route_state: "ready",
          picker_visible: true,
          usable_now: false,
          identity_verified: true,
        },
        {
          alias: "unstated",
          label: "No truth supplied",
          provider: "claude",
          model: "claude-opus-4.8",
          route_state: "ready",
          picker_visible: true,
        },
      ],
    });

    expect(policy.targets[0]?.usableNow).toBe(false);
    expect(policy.targets[0]?.identityVerified).toBe(true);
    expect(policy.targets[1]?.usableNow).toBeUndefined();
    expect(policy.targets[1]?.identityVerified).toBeUndefined();
  });

  test("carries the backend's bounded fallback notice without treating it as route authority", () => {
    const policy = routePolicyFromValue({
      version: "v1",
      domain: "routing_decision",
      decision: {
        route_id: "kimi_code:k3",
        provider_id: "kimi_code",
        model_id: "k3",
        strategy: "responsive",
        metadata: {
          route_state: "unverified",
          selectable: true,
          fallback_notice: {
            kind: "live_fallback",
            message: "Live fallback: dead:route -> kimi_code:k3",
          },
        },
      },
      targets: [{
        alias: "kimi",
        label: "Kimi K3",
        provider: "kimi_code",
        model: "k3",
        route_state: "unverified",
        picker_visible: true,
        usable_now: true,
        identity_verified: false,
      }],
    });

    expect(policy.fallbackNotice).toBe("Live fallback: dead:route -> kimi_code:k3");
    expect(policy.routeState).toBe("unverified");
  });

});
