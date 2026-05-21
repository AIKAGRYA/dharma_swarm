/**
 * DHARMA COMMAND -- Color constants and theme helpers.
 * All values mirror the CSS custom properties in globals.css.
 *
 * Palette: Nihonga / iwa-enogu (mineral pigments).
 * Per docs/plans/2026-05-21-command-plane-design-lock.md §VII.
 */

// ---------------------------------------------------------------------------
// Base palette — Nihonga mineral pigments (revalued 2026-05-21, PR 1)
// ---------------------------------------------------------------------------

export const colors = {
  sumi: {
    // 墨 — warm ink substrate (not cool graphite)
    950: "#0F0D0B",
    900: "#1A1715",
    850: "#211E1B",
    800: "#292621",
    700: "#3A352F", // Tetsu-iro adjacent (hairlines)
    600: "#4F4A42", // idle / muted text
  },
  aozora: "#1F4F8C",     // 群青 Gunjō — azurite blue (identity / actuation)
  botan: "#5B3E72",      // 紫 Murasaki — Heian gentian purple (recall / contemplation)
  kinpaku: "#A57A35",    // 黄土 Ōdo — aged ochre (STALE / warn)
  rokusho: "#6C8E7A",    // 緑青 — muted malachite (OK / fresh / done)
  bengara: "#7A3E2A",    // 弁柄 — weathered iron oxide (earthen depth / weight)
  fuji: "#5B5070",       // 藤 — deeper wisteria (secondary purple)
  torinoko: "#F2EDE3",   // 胡粉 Gofun — oyster-shell washi cream (paper-white)
  kitsurubami: "#B89E7D",// 黄橡 — aged paper-tan (secondary)

  // -------------------------------------------------------------------------
  // ALARM-ONLY — DO NOT add `shu` to accentCycle or accentTwAt.
  // Reserved for genuine FAIL/urgent semantic only. If shu leaks into
  // the decorative accent rotation, alarm-red will pull into routine UI
  // and destroy the semantic split (bengara = depth, shu = real urgency).
  // -------------------------------------------------------------------------
  shu: "#9C2A1F",        // 朱 — lacquer-shrine vermillion (FAIL / urgent)
} as const;

// ---------------------------------------------------------------------------
// Status mapping
// ---------------------------------------------------------------------------

export type StatusKey = "ok" | "warn" | "error" | "info" | "idle" | "running" | "done" | "failed";

const statusColorMap: Record<StatusKey, string> = {
  ok: colors.rokusho,
  warn: colors.kinpaku,
  error: colors.shu,       // was bengara — semantic split: bengara = depth, shu = alarm
  info: colors.aozora,
  idle: colors.sumi[600],
  running: colors.aozora,
  done: colors.rokusho,
  failed: colors.shu,      // was bengara
};

export function statusColor(status: string): string {
  const key = status.toLowerCase() as StatusKey;
  return statusColorMap[key] ?? colors.sumi[600];
}

/** Tailwind-compatible class suffix for a given status. */
export function statusTwColor(status: string): string {
  const map: Record<string, string> = {
    ok: "rokusho",
    warn: "kinpaku",
    error: "shu",          // was "bengara"
    info: "aozora",
    idle: "sumi-600",
    running: "aozora",
    done: "rokusho",
    failed: "shu",         // was "bengara"
  };
  return map[status.toLowerCase()] ?? "sumi-600";
}

// ---------------------------------------------------------------------------
// Glow shadow generators
// (Note: helpers retained for compatibility; Phase 1.5 will remove them.
//  Subtler glow on muted Nihonga hex is closer to locked aesthetic than
//  punchy glow on saturated cyan / hot-pink.)
// ---------------------------------------------------------------------------

/**
 * Returns a CSS `text-shadow` string that produces a neon glow effect.
 * @param hex -- hex color string (e.g. "#1F4F8C")
 * @param intensity -- multiplier 0..1 (default 0.6)
 */
export function glowText(hex: string, intensity = 0.6): string {
  const inner = Math.round(intensity * 100);
  const outer = Math.round(intensity * 50);
  return `0 0 6px color-mix(in srgb, ${hex} ${inner}%, transparent), 0 0 20px color-mix(in srgb, ${hex} ${outer}%, transparent)`;
}

/**
 * Returns a CSS `box-shadow` string for glowing panels / cards.
 * @param hex -- hex color string
 * @param intensity -- multiplier 0..1 (default 0.4)
 */
export function glowBox(hex: string, intensity = 0.4): string {
  const inner = Math.round(intensity * 100);
  const outer = Math.round(intensity * 40);
  return `0 0 8px color-mix(in srgb, ${hex} ${inner}%, transparent), 0 0 24px color-mix(in srgb, ${hex} ${outer}%, transparent)`;
}

/**
 * Returns a CSS `box-shadow` for a subtle border glow (used on cards).
 */
export function glowBorder(hex: string, intensity = 0.25): string {
  const alpha = Math.round(intensity * 100);
  return `inset 0 0 0 1px color-mix(in srgb, ${hex} ${alpha}%, transparent)`;
}

// ---------------------------------------------------------------------------
// Accent color cycle (for sequential items like agent cards)
// ALARM-ONLY tokens (shu) MUST NOT appear in this cycle.
// ---------------------------------------------------------------------------

export const accentCycle = [
  colors.aozora,
  colors.botan,
  colors.kinpaku,
  colors.rokusho,
  colors.bengara,
  colors.fuji,
] as const;

export function accentAt(index: number): string {
  return accentCycle[index % accentCycle.length];
}

/** Tailwind class name for the accent at a given index. */
export function accentTwAt(index: number): string {
  // shu is omitted intentionally — alarm-only, must not enter the cycle.
  const names = ["aozora", "botan", "kinpaku", "rokusho", "bengara", "fuji"] as const;
  return names[index % names.length];
}
