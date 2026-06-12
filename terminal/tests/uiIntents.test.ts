import {describe, expect, test} from "bun:test";

import {closestCommand, matchUiIntent, tourLines} from "../src/uiIntents";
import {reduceApp} from "../src/state";
import {initialState} from "../src/state";
import type {RouteTarget} from "../src/types";

const PANES = [
  {id: "chat", title: "Chat"},
  {id: "control", title: "Control"},
  {id: "models", title: "Models"},
  {id: "agents", title: "Agents"},
  {id: "runtime", title: "Runtime"},
];

const TARGETS: RouteTarget[] = [
  {alias: "codex", label: "Codex responsive", provider: "codex", model: "gpt-5.4", routeId: "r1", routeState: "ready", selectable: true},
  {alias: "grok", label: "Grok build", provider: "xai", model: "grok-build-0.1", routeId: "r2", routeState: "ready", selectable: true},
  {alias: "opus", label: "Claude Opus", provider: "claude_code", model: "opus", routeId: "r3", routeState: "ready", selectable: true},
];

describe("F-066 natural-language UI intents", () => {
  test("at least 3 layout phrasings map to mode intents", () => {
    expect(matchUiIntent("switch to zen mode", PANES, TARGETS)).toEqual({kind: "layout", mode: "zen"});
    expect(matchUiIntent("go back to the simple view", PANES, TARGETS)).toEqual({kind: "layout", mode: "zen"});
    expect(matchUiIntent("switch to the funky fusion dashboard", PANES, TARGETS)).toEqual({kind: "layout", mode: "cockpit"});
    expect(matchUiIntent("open the cockpit layout", PANES, TARGETS)).toEqual({kind: "layout", mode: "cockpit"});
  });

  test("operator example: open the control panel pane", () => {
    const intent = matchUiIntent("can you open the control panel pane for me", PANES, TARGETS);
    expect(intent).toEqual({kind: "pane", tabId: "control", title: "Control"});
  });

  test("pane intents need a pane noun — bare titles stay chat", () => {
    expect(matchUiIntent("show me the models tab", PANES, TARGETS)).toEqual({kind: "pane", tabId: "models", title: "Models"});
    expect(matchUiIntent("show me what control means in cybernetics", PANES, TARGETS)).toBeNull();
  });

  test("filler words ride between verb and 'to': change models to claude opus", () => {
    const intent = matchUiIntent("change models to claude opus", PANES, TARGETS);
    expect(intent?.kind).toBe("model");
    if (intent?.kind === "model") {
      expect(intent.target.provider).toBe("claude_code");
    }
  });

  test("operator literal: 'change models to glm 4.' and 'glm 5.' resolve or answer locally — never a backend turn", () => {
    const targets = [
      ...TARGETS,
      {alias: "glm", label: "GLM 5", provider: "openrouter", model: "glm-5", routeId: "r4", routeState: "ready", selectable: true} as const,
    ];
    const four = matchUiIntent("change models to glm 4.", PANES, targets);
    expect(four).not.toBeNull();
    const five = matchUiIntent("change models to glm 5.", PANES, targets);
    expect(five?.kind).toBe("model");
    if (five?.kind === "model") {
      expect(five.target.model).toBe("glm-5");
    }
    const nothing = matchUiIntent("change models to fancypants ultra", PANES, targets);
    expect(nothing?.kind).toBe("model_unknown");
  });

  test("typo'd commands resolve to the nearest registered command", () => {
    expect(closestCommand("hlep", ["help", "git", "model"])).toBe("help");
    expect(closestCommand("modle", ["help", "git", "model"])).toBe("model");
    expect(closestCommand("zzzzzz", ["help", "git", "model"])).toBeNull();
  });

  test("operator example: switch to grok build 0.1 resolves a route target", () => {
    const intent = matchUiIntent("switch to grok build 0.1", PANES, TARGETS);
    expect(intent?.kind).toBe("model");
    if (intent?.kind === "model") {
      expect(intent.target.provider).toBe("xai");
      expect(intent.target.model).toBe("grok-build-0.1");
    }
  });

  test("operator example: guided tour", () => {
    expect(matchUiIntent("give me a guided tour through the control plane", PANES, TARGETS)).toEqual({kind: "tour"});
    expect(matchUiIntent("show me all the options and hotkeys", PANES, TARGETS)).toEqual({kind: "tour"});
  });

  test("non-intent control phrases route to chat (null)", () => {
    expect(matchUiIntent("tell me about zen buddhism and its history", PANES, TARGETS)).toBeNull();
    expect(matchUiIntent("what is the control plane architecture of this swarm?", PANES, TARGETS)).toBeNull();
    expect(matchUiIntent("switch to plan b for the deployment", PANES, TARGETS)).toBeNull();
    expect(matchUiIntent("hello, can you hear me?", PANES, TARGETS)).toBeNull();
  });

  test("tour lines list every pane and both layouts", () => {
    const lines = tourLines(PANES).join("\n");
    for (const pane of PANES) {
      expect(lines).toContain(pane.title);
    }
    expect(lines).toContain("zen");
    expect(lines).toContain("cockpit");
    expect(lines).toContain("F2");
  });
});

describe("F-063 layout-mode reducer", () => {
  test("zen is the boot default", () => {
    expect(initialState.uiMode.layoutMode).toBe("zen");
  });

  test("every transition lands exactly", () => {
    const toCockpit = reduceApp(initialState, {type: "layout.mode.set", mode: "cockpit"});
    expect(toCockpit.uiMode.layoutMode).toBe("cockpit");
    const toDeck = reduceApp(toCockpit, {type: "layout.mode.set", mode: "deck-focus:agents"});
    expect(toDeck.uiMode.layoutMode).toBe("deck-focus:agents");
    const backToZen = reduceApp(toDeck, {type: "layout.mode.set", mode: "zen"});
    expect(backToZen.uiMode.layoutMode).toBe("zen");
    expect(backToZen.uiMode.activeTabId).toBe(initialState.uiMode.activeTabId);
  });
});
