// Hokusai-futurist truecolor palette (S4 — FACE-2 command post).
// Design truth: spec-forge/knowledge/DESIGN_FEEDBACK_OPERATOR_20260612.md +
// handoff §7 contrast-verified token table (ratios vs night #10141C /
// indigo #1A2233). Token NAMES are stable across the migration; only the
// values moved to truecolor. ScenicStrip keeps its own verbatim art
// constants (sanctioned exemption).
//
// Usage law (gradeable):
//   - indigo / river appear ONLY as backgroundColor/borderColor (criterion #8).
//   - ink is decoration only — never information.
//   - vermilion is danger only — never expected-offline.
//   - wave is THE chrome accent (brand + active item); ridge is the focused
//     border; parchment aims at seer/model-identity surfaces.
export const THEME = {
  // surfaces
  night: "#10141C", // app canvas
  indigo: "#1A2233", // raised surface (bg/border only)
  harbor: "#223249", // selected/overlay surface (stone is meta-only on it)
  // borders
  river: "#2D4F67", // decorative border ONLY (2.13:1 — never carries meaning)
  ridge: "#658594", // focused border (4.69:1)
  // text
  foam: "#DCD7BA", // primary text (12.71:1)
  mist: "#C8C093", // secondary text (10.02:1)
  stone: "#8992A7", // labels / meta (5.91:1 — the legibility floor)
  ink: "#727169", // decoration ONLY (3.76:1)
  // accents
  wave: "#7E9CD8", // accent-witness — THE one decorative chrome accent (6.70:1)
  crest: "#7FB4CA", // running/streaming (8.15:1)
  parchment: "#DCA561", // accent-seer — model identity (8.43:1)
  sunlit: "#E6C384", // (10.98:1)
  bengara: "#8F2D12", // FILL ONLY — foam-on-bengara 5.67:1; raw text fails
  // status
  moss: "#98BB6C", // success (8.48:1)
  pine: "#7AA89F", // done / quiet-ok (6.96:1)
  persimmon: "#FF9E3B", // warning — expected-offline class (8.96:1)
  vermilion: "#FF5D62", // danger ONLY (6.14:1)
  iris: "#957FB8", // spawning (5.27:1)
} as const;

// §7 AGENT_STATES: glyph+color pairs — color is never the sole signal.
export const AGENT_STATES = {
  running: {glyph: "▶", color: THEME.crest},
  thinking: {glyph: "◉", color: THEME.wave},
  spawning: {glyph: "◌", color: THEME.iris},
  blocked: {glyph: "⚠", color: THEME.persimmon},
  error: {glyph: "✖", color: THEME.vermilion},
  done: {glyph: "✓", color: THEME.moss},
  idle: {glyph: "·", color: THEME.stone},
  offline: {glyph: "○", color: THEME.ink},
} as const;
