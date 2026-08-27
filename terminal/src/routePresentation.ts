import {THEME} from "./theme.ts";
import type {RouteState} from "./types.ts";

export type RouteStatePresentation = {
  glyph: string;
  word: string;
  color: string;
};

/**
 * Render attempt-route state without implying that a provider/model was served.
 * Exact served identity and OnCall verification belong to separate owners.
 */
export function routeStatePresentation(state: RouteState | "stale"): RouteStatePresentation {
  switch (state) {
    case "ready":
      return {glyph: "◇", word: "SELECTABLE", color: THEME.parchment};
    case "stale":
      return {glyph: "~", word: "STALE", color: THEME.persimmon};
    case "unverified":
      return {glyph: "?", word: "UNVERIFIED", color: THEME.persimmon};
    case "degraded":
      return {glyph: "~", word: "DEGRADED", color: THEME.persimmon};
    case "slow":
      return {glyph: "~", word: "SLOW", color: THEME.persimmon};
    case "unavailable":
      return {glyph: "▣", word: "HELD", color: THEME.persimmon};
    case "invalid":
      return {glyph: "×", word: "INVALID", color: THEME.vermilion};
  }
}
