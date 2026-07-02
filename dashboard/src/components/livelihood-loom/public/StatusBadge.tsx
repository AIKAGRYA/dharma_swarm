import { cn } from "@/lib/utils";

export interface StatusBadgeProps {
  status: string;
  className?: string;
}

type BadgeStyle = {
  badge: string;
};

const badgeStyles: Record<string, BadgeStyle> = {
  rokusho: {
    badge:
      "inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold break-all bg-rokusho/15 text-rokusho",
  },
  kinpaku: {
    badge:
      "inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold break-all bg-kinpaku/15 text-kinpaku",
  },
  bengara: {
    badge:
      "inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold break-all bg-bengara/15 text-bengara",
  },
  aozora: {
    badge:
      "inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold break-all bg-aozora/15 text-aozora",
  },
  sumi: {
    badge:
      "inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold break-all bg-sumi-600/15 text-sumi-600",
  },
};

function statusColorKey(status: string): string {
  const s = status.toLowerCase();

  if (
    s.includes("green") ||
    s === "ok" ||
    s === "allowed" ||
    s === "done" ||
    s === "complete" ||
    s === "completed" ||
    s === "passed" ||
    s === "approved"
  ) {
    return "rokusho";
  }

  if (
    s.includes("red") ||
    s === "error" ||
    s === "blocked" ||
    s === "block" ||
    s === "failed" ||
    s === "rejected"
  ) {
    return "bengara";
  }

  if (
    s.includes("yellow") ||
    s === "warn" ||
    s === "warning" ||
    s === "needs_review" ||
    s === "needs review" ||
    s === "review" ||
    s === "pending" ||
    s === "draft"
  ) {
    return "kinpaku";
  }

  if (s.includes("blue") || s === "info" || s === "unknown") {
    return "aozora";
  }

  return "sumi";
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const key = statusColorKey(status);
  const label = status || "Unknown";

  return <span className={cn(badgeStyles[key]?.badge ?? badgeStyles.sumi.badge, className)}>{label}</span>;
}
