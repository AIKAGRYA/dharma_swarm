// Nihonga Mineral truecolor palette (operator pick 2026-06-16) — bold mineral
// pigments on a warm sumi-black canvas: rokushō verdigris is the chrome accent,
// gunjō ultramarine streams, kincha gold marks model identity, shu vermilion is
// danger. Token NAMES + the usage/contrast laws are STABLE across the repaint;
// only the values moved (warmer canvas, mineral accents). ScenicStrip keeps its
// own verbatim art constants (sanctioned exemption).
//
// Usage law (gradeable):
//   - indigo / river appear ONLY as backgroundColor/borderColor (criterion #8).
//   - ink is decoration only — never information.
//   - vermilion is danger only — never expected-offline.
//   - wave is THE chrome accent (brand + active item); ridge is the focused
//     border; parchment aims at seer/model-identity surfaces.
export const THEME = {
  // surfaces (warm sumi-black, not cold indigo)
  night: "#14110E", // app canvas — warm sumi black
  indigo: "#201913", // raised surface (bg/border only)
  harbor: "#2C2218", // selected/overlay surface (stone is meta-only on it)
  // borders
  river: "#3A2C20", // decorative border ONLY (low contrast — never carries meaning)
  ridge: "#9A7C5A", // focused border — warm kincha ridge (~4.8:1)
  // text
  foam: "#E8DCC0", // primary text — gofun cream (12.9:1)
  mist: "#D6C7A2", // secondary text (10.4:1)
  stone: "#A89A7E", // labels / meta — warm stone (7.4:1, above the legibility floor)
  ink: "#80735F", // decoration ONLY (3.9:1)
  // accents
  wave: "#6FA890", // accent-witness — rokushō verdigris, THE chrome accent (7.0:1)
  crest: "#6E90D0", // running/streaming — gunjō ultramarine (6.2:1)
  parchment: "#D2A05A", // accent-seer — kincha gold, model identity (8.6:1)
  sunlit: "#E4C07E", // (10.9:1)
  bengara: "#8F2D12", // FILL ONLY — foam-on-bengara; raw text fails
  // status
  moss: "#9AB46A", // success — byakuroku pale green (8.4:1)
  pine: "#86A492", // done / quiet-ok (7.1:1)
  persimmon: "#E0A24E", // warning — ōdo ochre, expected-offline class (8.7:1)
  vermilion: "#E85A4E", // danger ONLY — shu vermilion (5.6:1)
  iris: "#B488A6", // spawning — murasaki clay (6.0:1)
} as const;

// §7 AGENT_STATES: glyph+color pairs — color is never the sole signal.
export const AGENT_STATES = {
  running: {glyph: "▶", color: THEME.crest},
  thinking: {glyph: "◉", color: THEME.wave},
  spawning: {glyph: "◌", color: THEME.iris},
  blocked: {glyph: "⚠", color: THEME.persimmon},
  error: {glyph: "✖", color: THEME.vermilion},
  done: {glyph: "■", color: THEME.pine},
  idle: {glyph: "·", color: THEME.stone},
  offline: {glyph: "○", color: THEME.ink},
} as const;
