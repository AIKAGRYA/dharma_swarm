/**
 * Motion vocabulary tokens for the command-plane redesign.
 * Per docs/plans/2026-05-21-command-plane-design-lock.md §VII.
 *
 * Motion is information, not decoration. Three vocabularies:
 *   instant — state transitions (badge change, row select)
 *   navigate — route change, panel slide
 *   ambient — slow data cadence, fresh-value dot
 *
 * No spring physics. Use these tokens in Motion / Framer Motion calls
 * and CSS animations. Adding a 4th vocabulary requires an ADR.
 */

export const motion = {
  instant: {
    duration: 0.1,           // 100ms (range 80-120)
    ease: [0.2, 0, 0, 1] as const,
    cssEase: "cubic-bezier(0.2, 0, 0, 1)",
    cssDuration: "100ms",
  },
  navigate: {
    duration: 0.22,          // 220ms (range 200-240)
    ease: [0.4, 0, 0.2, 1] as const,
    cssEase: "cubic-bezier(0.4, 0, 0.2, 1)",
    cssDuration: "220ms",
  },
  ambient: {
    duration: 1.0,           // 1000ms (range 800-1200)
    ease: "linear" as const,
    cssEase: "linear",
    cssDuration: "1000ms",
  },
} as const;

export type MotionToken = keyof typeof motion;
