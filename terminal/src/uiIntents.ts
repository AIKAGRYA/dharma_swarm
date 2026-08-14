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
  | {kind: "tour"}
  // Compatibility vocabulary for opening/closing the five-place navigator.
  // The retired persistent chat rail is not part of the Nihonga Helm.
  | {kind: "rail"; on: boolean | "toggle"};

type PaneRef = {id: string; title: string};

const IMPERATIVE = /\b(open|show|switch|change|go|take|bring|give|jump|move|back)\b/i;

const ZEN_WORDS = /\b(zen|traditional|simple|clean|minimal|normal)\b/i;
const COCKPIT_WORDS = /\b(cockpit|dashboard|fusion|funky|full|mission control)\b/i;
// FACE-3: precise phrases only — bare "scroll" is a TUI verb ("scroll the
// view down") and must never yank the user into the manuscript face.
const SCROLL_WORDS = /\b(manuscript|reading mode|the scroll)\b/i;
const UI_NOUN = /\b(mode|view|screen|layout|ui|tui|interface|dashboard|cockpit)\b/i;

const PANE_NOUN = /\b(pane|panel|tab|surface|view|plane)\b/i;

// Navigator compatibility: legacy rail language resolves to the five-place
// switcher rather than claiming a persistent rail that no longer renders.
const RAIL_NOUN = /\b(navigator|rail|copilot|co-pilot)\b/i;
// Rail-specific verbs (no other surface "docks") — sufficient on their own.
const RAIL_VERB_OFF = /\b(undock|detach)\b/i;
const RAIL_VERB_ON = /\b(dock|tether)\b/i;
// Ambiguous verbs — only count as rail when a rail/chat noun is present.
const RAIL_WEAK_OFF = /\b(hide|close|dismiss|remove)\b/i;
const RAIL_WEAK_ON = /\b(show|open|pin|bring|attach)\b/i;

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

  // Navigator compatibility — checked BEFORE the imperative gate because "dock"/"undock"
  // are rail-specific verbs that carry no imperative keyword. "dock the chat" /
  // "show the navigator" -> on; "undock" / "hide the rail" -> off. Ambiguous
  // verbs (show/hide/open/close) only count when a rail/chat noun is present.
  if (RAIL_VERB_OFF.test(text)) {
    return {kind: "rail", on: false};
  }
  if (RAIL_VERB_ON.test(text)) {
    return {kind: "rail", on: true};
  }
  if (RAIL_NOUN.test(text)) {
    if (RAIL_WEAK_OFF.test(text)) {
      return {kind: "rail", on: false};
    }
    if (RAIL_WEAK_ON.test(text)) {
      return {kind: "rail", on: true};
    }
  }

  // The tour is NEVER triggered by plain text (operator word 2026-06-16: typing
  // "tour" must reach the chat model, not pop the menu). It opens only via the
  // /tour command — see app.tsx.
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

  // An exact pane-title command is already unambiguous, so it does not need a
  // redundant pane noun: "open sessions", "show runtime", "go to agents".
  // Keep this anchored and exact so conversational uses of pane-title words
  // still fall through to chat.
  const directPaneMatch = text.match(/^(?:open|show|go to|switch to|jump to|bring up)(?: the)? (.+)$/i);
  if (directPaneMatch) {
    const target = directPaneMatch[1] ?? "";
    for (const pane of panes) {
      if (target === normalize(pane.title) || target === normalize(pane.id)) {
        return {kind: "pane", tabId: pane.id, title: pane.title};
      }
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

// Legacy Helm directive syntax is retained only for deterministic stripping and
// compatibility parsing. Provider narration has no execution or state-promotion
// authority; app.tsx intentionally never maps these tokens into intents.
const HELM_DIRECTIVE_RE = /⟦\s*helm:\s*([a-zA-Z]+)(?:\s+([^⟧]*?))?\s*⟧/g;

export type HelmDirective = {verb: string; arg: string; raw: string};

export function parseHelmDirectives(text: string): HelmDirective[] {
  const out: HelmDirective[] = [];
  for (const match of text.matchAll(HELM_DIRECTIVE_RE)) {
    out.push({verb: (match[1] ?? "").toLowerCase(), arg: (match[2] ?? "").trim(), raw: match[0]});
  }
  return out;
}

// Strip every ⟦helm:…⟧ token (even unknown verbs) so a leaked sentinel never
// reaches the operator's transcript, then tidy the whitespace it leaves behind.
export function stripHelmDirectives(text: string): string {
  return text
    .replace(HELM_DIRECTIVE_RE, "")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/ +\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// Map a directive to the SAME UiIntent the operator's own plain language would
// produce — so agent-driven and self-driven moves share one execution path.
// Returns null for an unknown/unsafe verb (the caller narrates the miss).
export function helmDirectiveToIntent(
  directive: HelmDirective,
  panes: PaneRef[],
  routeTargets: RouteTarget[],
): UiIntent | null {
  const verb = directive.verb;
  const arg = normalize(directive.arg);
  if (verb === "zen" || verb === "cockpit" || verb === "scroll") {
    return {kind: "layout", mode: verb};
  }
  if (verb === "dock") {
    return {kind: "rail", on: true};
  }
  if (verb === "undock") {
    return {kind: "rail", on: false};
  }
  if (verb === "open" || verb === "show" || verb === "pane" || verb === "go") {
    if (!arg) return null;
    for (const pane of panes) {
      if (normalize(pane.title) === arg || normalize(pane.id) === arg) {
        return {kind: "pane", tabId: pane.id, title: pane.title};
      }
    }
    for (const pane of panes) {
      const title = normalize(pane.title);
      if (title && (arg.includes(title) || title.includes(arg))) {
        return {kind: "pane", tabId: pane.id, title: pane.title};
      }
    }
    return null;
  }
  if (verb === "model" || verb === "route") {
    if (!arg) return null;
    const tokens = arg.split(" ").filter((token) => token.length > 1 || /\d/.test(token));
    let best: {target: RouteTarget; score: number} | null = null;
    for (const target of routeTargets) {
      const haystack = normalize(
        `${target.alias} ${target.label} ${target.provider} ${target.model} ${target.provider}:${target.model}`,
      ).replace(/[-_]/g, " ");
      let score = 0;
      for (const token of tokens) {
        if (haystack.includes(token)) score += token.length;
      }
      if (score > 0 && (!best || score > best.score)) {
        best = {target, score};
      }
    }
    return best && best.score >= 3 ? {kind: "model", target: best.target} : null;
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
    "One Helm, three densities  (F2 toggles · /zen /cockpit /scroll):",
    "  zen      Quiet Field — conversation, truth band, composer",
    "  cockpit  Whole Helm — 45/35/20 panorama when the viewport permits",
    "  scroll   reading manuscript — centered column, ^D telemetry drawer",
    "",
    "Five places  Home · Conversation · Activity · Evidence · System",
    "Facets  (Tab / Shift-Tab cycle · ^K switcher · or ask “open models”):",
    paneRow1,
    paneRow2,
    "",
    "Talking vs steering:",
    "  Plain prompts go to the model.  Slash commands hit surfaces directly:",
    "  /status /runtime /models /git /memory /approvals /help  (/help lists all)",
    "",
    "Keys  Enter send · Tab facets · Esc, then ^K/^B navigator · ^T trace · ^C quit",
    "",
    "Try /cockpit, then “back to zen” to return here.",
  ];
}
