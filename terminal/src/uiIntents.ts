// F-066 + operator word 2026-06-12: plain-language UI control. The composer is
// the steering wheel — "open the control panel pane", "switch to zen", "give me
// a guided tour" act on the UI directly instead of round-tripping the backend.
// Precision over recall: only imperative phrases with an unambiguous UI noun
// match; everything else falls through to normal chat ({kind: null} is never
// returned — null means "send to the backend like any other prompt").

import type {RouteTarget} from "./types";

export type UiIntent =
  | {kind: "layout"; mode: "zen" | "cockpit"}
  | {kind: "pane"; tabId: string; title: string}
  | {kind: "model"; target: RouteTarget}
  | {kind: "tour"};

type PaneRef = {id: string; title: string};

const IMPERATIVE = /\b(open|show|switch|go|take|bring|give|jump|move|back)\b/i;

const ZEN_WORDS = /\b(zen|traditional|simple|clean|minimal|normal)\b/i;
const COCKPIT_WORDS = /\b(cockpit|dashboard|fusion|funky|full|mission control)\b/i;
const UI_NOUN = /\b(mode|view|screen|layout|ui|tui|interface|dashboard|cockpit)\b/i;

const TOUR_RE =
  /\b(guided tour|tour|walk me through|show me (all )?(the )?(options|commands|hotkeys|keys|panes|surfaces))\b/i;

const PANE_NOUN = /\b(pane|panel|tab|surface|view|plane)\b/i;

function normalize(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9.\s-]/g, " ").replace(/\s+/g, " ").trim();
}

export function matchUiIntent(
  prompt: string,
  panes: PaneRef[],
  routeTargets: RouteTarget[],
): UiIntent | null {
  const text = normalize(prompt);
  if (!text || text.startsWith("/")) {
    return null;
  }
  if (!IMPERATIVE.test(text) && !TOUR_RE.test(text)) {
    return null;
  }

  if (TOUR_RE.test(text)) {
    return {kind: "tour"};
  }

  // Layout intents need BOTH a mode word and a UI noun ("switch to zen mode",
  // "go back to the simple view") so "tell me about zen buddhism" never trips.
  if (IMPERATIVE.test(text) && UI_NOUN.test(text)) {
    if (COCKPIT_WORDS.test(text)) {
      return {kind: "layout", mode: "cockpit"};
    }
    if (ZEN_WORDS.test(text)) {
      return {kind: "layout", mode: "zen"};
    }
  }

  // Pane intents need an imperative + the pane's title + a pane noun
  // ("open the control panel pane for me", "show me the models tab").
  if (PANE_NOUN.test(text)) {
    for (const pane of panes) {
      const title = normalize(pane.title);
      if (!title) continue;
      const titleRe = new RegExp(`\\b${title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
      if (titleRe.test(text)) {
        return {kind: "pane", tabId: pane.id, title: pane.title};
      }
    }
  }

  // Model intents: "switch to <something>" where <something> fuzzy-matches a
  // selectable route target (alias, label, model, or provider:model tokens).
  const switchMatch = text.match(/\b(?:switch|change|move)\s+(?:to|over to|onto)\s+(.{2,60})$/i);
  if (switchMatch) {
    const query = normalize(switchMatch[1]);
    const queryTokens = query.split(" ").filter((token) => token.length > 1);
    let best: {target: RouteTarget; score: number} | null = null;
    for (const target of routeTargets) {
      const haystack = normalize(
        `${target.alias} ${target.label} ${target.provider} ${target.model} ${target.provider}:${target.model}`,
      );
      let score = 0;
      for (const token of queryTokens) {
        if (haystack.includes(token)) score += token.length;
      }
      if (score > 0 && (!best || score > best.score)) {
        best = {target, score};
      }
    }
    // Demand a real overlap (≥4 matched chars) so "switch to plan b" stays chat.
    if (best && best.score >= 4) {
      return {kind: "model", target: best.target};
    }
  }

  return null;
}

// The guided tour transcript (operator example: "give me a guided tour through
// the control plane visually and or with a list of commands i can use or
// hotkeys i can press"). Rendered locally; works offline.
export function tourLines(panes: PaneRef[]): string[] {
  const paneList = panes.map((pane) => `  ${pane.title}`).join("\n");
  return [
    "THE HELM — guided tour",
    "",
    "Two layouts:",
    "  zen      just this conversation (you are here; boot default)",
    "  cockpit  full instrument panel — tabs, sidebar, telemetry",
    "  Switch any time: F2, /zen, /cockpit — or just ask in plain language",
    '  ("switch to the dashboard view", "back to the simple screen").',
    "",
    "Panes (Tab / Shift-Tab cycle, ^K opens the switcher, or ask):",
    paneList,
    '  Plain language works: "open the control panel pane", "show me the models tab".',
    "",
    "Talking vs steering:",
    "  Plain prompts go to the swarm. Slash commands hit surfaces directly:",
    "  /status /runtime /models /git /memory /approvals /help ... (/help lists all)",
    "",
    "Keys that matter:",
    "  Enter send · Tab/Shift-Tab panes · ^K pane switcher · ^T expand/collapse trace",
    "  ^B sidebar · ↑/↓ scroll · F2 zen/cockpit · ^C quit",
    "",
    "Try: /cockpit — then \"back to zen\" to return here.",
  ];
}
