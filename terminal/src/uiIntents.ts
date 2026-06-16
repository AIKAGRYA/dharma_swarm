// F-066 + operator word 2026-06-12: plain-language UI control. The composer is
// the steering wheel — "open the control panel pane", "switch to zen", "give me
// a guided tour" act on the UI directly instead of round-tripping the backend.
// Precision over recall: only imperative phrases with an unambiguous UI noun
// match; everything else falls through to normal chat ({kind: null} is never
// returned — null means "send to the backend like any other prompt").

import type {RouteTarget} from "./types";

export type UiIntent =
  | {kind: "layout"; mode: "zen" | "cockpit" | "scroll"}
  | {kind: "pane"; tabId: string; title: string}
  | {kind: "model"; target: RouteTarget}
  // A clear model-switch ask whose target matched nothing: answered locally
  // with the route menu — NEVER forwarded to a billed backend turn (operator
  // cost incident: "change models to glm 4." ran as an agentic claude turn).
  | {kind: "model_unknown"; query: string}
  | {kind: "tour"};

type PaneRef = {id: string; title: string};

const IMPERATIVE = /\b(open|show|switch|change|go|take|bring|give|jump|move|back)\b/i;

const ZEN_WORDS = /\b(zen|traditional|simple|clean|minimal|normal)\b/i;
const COCKPIT_WORDS = /\b(cockpit|dashboard|fusion|funky|full|mission control)\b/i;
// FACE-3: precise phrases only — bare "scroll" is a TUI verb ("scroll the
// view down") and must never yank the user into the manuscript face.
const SCROLL_WORDS = /\b(manuscript|reading mode|the scroll)\b/i;
const UI_NOUN = /\b(mode|view|screen|layout|ui|tui|interface|dashboard|cockpit)\b/i;

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
  // The tour is NEVER triggered by plain text (operator word 2026-06-16: typing
  // "tour" must reach the chat model, not pop the menu). It opens only via the
  // /tour command or the ^G hotkey — see app.tsx.
  if (!IMPERATIVE.test(text)) {
    return null;
  }

  // Layout intents need BOTH a mode word and a UI noun ("switch to zen mode",
  // "go back to the simple view") so "tell me about zen buddhism" never trips.
  if (IMPERATIVE.test(text) && UI_NOUN.test(text)) {
    if (SCROLL_WORDS.test(text)) {
      return {kind: "layout", mode: "scroll"};
    }
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
  // Up to two filler words ride between the verb and "to" so "change models
  // to claude opus" and "switch the route to grok" both land.
  const switchMatch = text.match(/\b(?:switch|change|move)\b(?:\s+\w+){0,2}?\s+(?:to|over to|onto)\s+(.{1,60})$/i);
  if (switchMatch) {
    // Trailing sentence punctuation must not break matching ("glm 5." — the
    // operator's literal message); digit tokens count ("glm 4" vs "glm-4").
    const query = normalize(switchMatch[1]).replace(/\.+$/g, "").trim();
    const queryTokens = query
      .split(" ")
      .map((token) => token.replace(/\.+$/g, ""))
      .filter((token) => token.length > 1 || /\d/.test(token));
    let best: {target: RouteTarget; score: number} | null = null;
    for (const target of routeTargets) {
      const haystack = normalize(
        `${target.alias} ${target.label} ${target.provider} ${target.model} ${target.provider}:${target.model}`,
      ).replace(/[-_]/g, " ");
      let score = 0;
      for (const token of queryTokens) {
        if (haystack.includes(token)) score += Math.max(token.length, 2);
      }
      if (score > 0 && (!best || score > best.score)) {
        best = {target, score};
      }
    }
    // A real overlap (≥4 matched chars) keeps "switch to plan b" in chat;
    // short alias+digit asks ("glm 5" = 3+2) clear it too.
    if (best && best.score >= 4) {
      return {kind: "model", target: best.target};
    }
    // The ask was unmistakably a model/route switch but nothing matched:
    // answer locally, never bill a backend turn on a mis-parse.
    if (/\b(model|models|route|routes|provider|llm|brain)\b/.test(text) && query) {
      return {kind: "model_unknown", query};
    }
  }

  return null;
}

// Unknown slash commands stay in the conversation with a gentle suggestion
// instead of detonating into the Control pane (gauntlet finding: /hlep yanked
// a zen user into cockpit). Small edit-distance, registered names only.
export function closestCommand(name: string, registered: readonly string[]): string | null {
  const target = name.toLowerCase();
  let best: {command: string; distance: number} | null = null;
  for (const candidate of registered) {
    const distance = editDistance(target, candidate);
    if (!best || distance < best.distance) {
      best = {command: candidate, distance};
    }
  }
  return best && best.distance <= 2 ? best.command : null;
}

function editDistance(a: string, b: string): number {
  const rows = a.length + 1;
  const cols = b.length + 1;
  const dist: number[] = Array.from({length: rows * cols}, (_, i) =>
    i < cols ? i : i % cols === 0 ? Math.floor(i / cols) : 0,
  );
  for (let i = 1; i < rows; i++) {
    for (let j = 1; j < cols; j++) {
      const substitution = a[i - 1] === b[j - 1] ? 0 : 1;
      dist[i * cols + j] = Math.min(
        dist[(i - 1) * cols + j] + 1,
        dist[i * cols + (j - 1)] + 1,
        dist[(i - 1) * cols + (j - 1)] + substitution,
      );
    }
  }
  return dist[rows * cols - 1];
}

// The guided tour transcript (operator example: "give me a guided tour through
// the control plane visually and or with a list of commands i can use or
// hotkeys i can press"). Rendered locally; works offline.
export function tourLines(panes: PaneRef[]): string[] {
  // Compact, one display line per element (no embedded newlines) so it renders
  // cleanly inside the isolated tour box without vertical squeeze.
  const titles = panes.map((pane) => pane.title);
  const half = Math.ceil(titles.length / 2);
  const paneRow1 = "  " + titles.slice(0, half).join(" · ");
  const paneRow2 = "  " + titles.slice(half).join(" · ");
  return [
    "THE HELM — guided tour",
    "",
    "Three layouts  (F2 toggles · /zen /cockpit /scroll · or just ask):",
    "  zen      just this conversation — the boot default, you are here",
    "  cockpit  full instrument panel — tabs, sidebar, telemetry",
    "  scroll   reading manuscript — centered column, ^D telemetry drawer",
    "",
    "Panes  (Tab / Shift-Tab cycle · ^K switcher · or ask “open the models tab”):",
    paneRow1,
    paneRow2,
    "",
    "Talking vs steering:",
    "  Plain prompts go to the model.  Slash commands hit surfaces directly:",
    "  /status /runtime /models /git /memory /approvals /help  (/help lists all)",
    "",
    "Keys  Enter send · Tab panes · ^K switcher · ^T trace · ^B sidebar · ^G tour · ^C quit",
    "",
    "Try /cockpit, then “back to zen” to return here.",
  ];
}
